#!/usr/bin/env python3
"""
Buell Logger - Main Entry Point (Modular v1.0)
Solo red + web por ahora. ECU logging viene después.
"""

import argparse
import logging
import time
import signal
import sys
import subprocess
import threading
from pathlib import Path

# Añadir paths para imports
sys.path.insert(0, str(Path(__file__).parent))

from network.manager import NetworkManager
from web.server import WebServer
from ecu.connection import DDFI2Connection
from ecu.eeprom import decode_eeprom_maps, decode_eeprom_params


def _get_version():
    try:
        import re
        cl = open("/home/pi/buell/CHANGELOG.md").read()
        m = re.search(r"## \[([^\]]+)\]", cl)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"

LOGGER_VERSION = _get_version()


class BuellLogger:
    """Orquestador principal - versión mínima para prueba de red."""
    
    def __init__(self, port="/dev/ttyUSB0", sessions_dir="/home/pi/buell/sessions", 
                 buell_dir="/home/pi/buell", no_poweroff=False):
        self.port = port
        self.sessions_dir = Path(sessions_dir)
        self.buell_dir = Path(buell_dir)
        self.no_poweroff = no_poweroff
        self.logger = logging.getLogger("BuellLogger")
        
        # Crear dirs si no existen
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.buell_dir.mkdir(parents=True, exist_ok=True)
        
        self._running = False
        self._shutting_down = False
        self._poweroff_requested = False
        self._ecu_thread = None
        
        # Componentes modulares
        self.network = NetworkManager()
        self.web = WebServer(host='0.0.0.0', port=8080, buell_dir=self.buell_dir)
        self.web.network = self.network
        self.ecu = DDFI2Connection(self.port)
        
        # Señales
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        self.logger.info(f"Señal {signum} recibida - deteniendo...")
        self._running = False
    
    def _ecu_loop(self):
        """Thread de lectura RT — 8Hz, actualiza web.ecu_live.
        Reintenta conectar si el puerto no estaba disponible al arrancar."""
        import time
        TARGET_HZ = 8.0
        INTERVAL  = 1.0 / TARGET_HZ
        self.logger.info("ECU loop iniciado")
        while self._running:
            t0 = time.monotonic()
            # Reconectar si el puerto no está abierto
            if self.ecu.ser is None or not self.ecu.ser.is_open:
                try:
                    self.logger.info("ECU loop — intentando conectar...")
                    self.ecu.connect()
                    ver = self.ecu.get_version()
                    if ver:
                        self.logger.info(f"ECU reconectada: {ver}")
                    else:
                        self.logger.warning("ECU no respondió — reintento en 5s")
                        time.sleep(5)
                        continue
                except Exception as e:
                    self.logger.debug(f"ECU no disponible: {e} — reintento en 5s")
                    time.sleep(5)
                    continue
            try:
                data = self.ecu.get_rt_data()
                if data:
                    self.web.ecu_live = data
            except Exception as e:
                self.logger.debug(f"ecu_loop: {e}")
                self.ecu.disconnect()
            elapsed = time.monotonic() - t0
            sleep_t = INTERVAL - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)
        self.logger.info("ECU loop detenido")

    def run(self):
        """Loop principal."""
        self._running = True
        self.logger.info(f"Buell Logger {LOGGER_VERSION}")
        self.logger.info(f"Sessions: {self.sessions_dir}")
        self.logger.info(f"Buell dir: {self.buell_dir}")
        
        # 1. Conectar ECU
        self.logger.info("Conectando a ECU...")
        try:
            self.ecu.connect()
            ver = self.ecu.get_version()
            if ver:
                self.logger.info(f"ECU conectada: {ver}")
                self.logger.info("Leyendo EEPROM...")
                eeprom = self.ecu.read_full_eeprom()
                if eeprom:
                    self.web.eeprom_maps   = decode_eeprom_maps(eeprom)
                    self.web.eeprom_params = decode_eeprom_params(eeprom)
                    self.logger.info("EEPROM leido — mapas disponibles")
                else:
                    self.logger.warning("EEPROM no pudo leerse")
            else:
                self.logger.warning("ECU no respondió — continuando sin ECU")
        except Exception as e:
            self.logger.warning(f"ECU no disponible: {e}")

        # 2. Arrancar thread RT
        self._ecu_thread = threading.Thread(
            target=self._ecu_loop, daemon=True, name="ecu-rt"
        )
        self._ecu_thread.start()

        # 3. Configurar red (hotspot por defecto)
        self.logger.info("Iniciando NetworkManager...")
        self.network.setup()
        
        # 2. Iniciar servidor web
        self.logger.info("Iniciando servidor web...")
        self.web.start()
        
        # 3. Loop principal (solo mantiene vivo + status)
        self.logger.info("Sistema listo. Esperando conexiones...")
        self.logger.info(f"Accede al dashboard en: http://{self.network.get_ip()}:8080")
        
        last_status = 0
        while self._running:
            time.sleep(1)
            
            # Log de status cada 30 segundos
            now = time.time()
            if now - last_status > 30:
                mode = self.network.current_mode()
                ip = self.network.get_ip()
                self.logger.info(f"Status: modo={mode} ip={ip}")
                last_status = now
            
            # Check shutdown desde web
            if self.web.pending_shutdown:
                self.logger.info("Shutdown solicitado desde web")
                self._poweroff_requested = True
                self._running = False
        
        # Cleanup
        self.shutdown()
    
    def shutdown(self):
        """Limpieza al salir."""
        self.logger.info("Deteniendo servicios...")
        self.web.stop()
        self.network.stop_monitor()
        
        if self._poweroff_requested and not self.no_poweroff:
            self.logger.info("Apagando sistema...")
            subprocess.run(["/usr/sbin/poweroff"], check=False)
        else:
            self.logger.info("Logger detenido (sin apagar)")


def main():
    parser = argparse.ArgumentParser(description=f"Buell Logger {LOGGER_VERSION}")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Puerto serial ECU")
    parser.add_argument("--sessions-dir", default="/home/pi/buell/sessions", help="Directorio de sesiones")
    parser.add_argument("--buell-dir", default="/home/pi/buell", help="Directorio de configuración")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--no-poweroff", action="store_true", help="No apagar al salir")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    logger = BuellLogger(
        port=args.port,
        sessions_dir=args.sessions_dir,
        buell_dir=args.buell_dir,
        no_poweroff=args.no_poweroff
    )
    logger.run()


if __name__ == "__main__":
    main()
