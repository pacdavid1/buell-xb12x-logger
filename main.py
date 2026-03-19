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
from pathlib import Path

# Añadir paths para imports
sys.path.insert(0, str(Path(__file__).parent))

from network.manager import NetworkManager
from web.server import WebServer


LOGGER_VERSION = "v2.0.0-MODULAR"


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
        
        # Componentes modulares
        self.network = NetworkManager()
        self.web = WebServer(host='0.0.0.0', port=8080, buell_dir=self.buell_dir)
        self.web.network = self.network
        
        # Señales
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        self.logger.info(f"Señal {signum} recibida - deteniendo...")
        self._shutting_down = True
        self._running = False
    
    def run(self):
        """Loop principal."""
        self._running = True
        self.logger.info(f"Buell Logger {LOGGER_VERSION} - MODO RED+WEB (sin ECU)")
        self.logger.info(f"Sessions: {self.sessions_dir}")
        self.logger.info(f"Buell dir: {self.buell_dir}")
        
        # 1. Configurar red (hotspot por defecto)
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
                self._shutting_down = True
                self._running = False
        
        # Cleanup
        self.shutdown()
    
    def shutdown(self):
        """Limpieza al salir."""
        self.logger.info("Deteniendo servicios...")
        self.web.stop()
        self.network.stop_monitor()
        
        if self._shutting_down and not self.no_poweroff:
            self.logger.info("Apagando sistema...")
            import os
            os.system("sudo poweroff")
        else:
            self.logger.info("Logger detenido (sin apagar)")


def main():
    parser = argparse.ArgumentParser(description=f"Buell Logger {LOGGER_VERSION}")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Puerto serial (no usado aún)")
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
