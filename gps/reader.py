#!/usr/bin/env python3
"""
gps/reader.py — NEO-M8N NMEA reader thread
Parses $GNRMC and $GNGGA sentences from /dev/ttyS0
Thread-safe: expone get_fix() para leer el último fix válido.
"""

import logging
import threading
import time

import serial
import pynmea2

logger = logging.getLogger("GPS")

GPS_BAUD    = 9600
GPS_PORT    = "/dev/ttyS0"
GPS_TIMEOUT = 2.0


class GPSFix:
    __slots__ = ("lat", "lon", "alt_m", "speed_kmh", "heading", "satellites", "timestamp_utc", "valid")

    def __init__(self):
        self.lat           = None
        self.lon           = None
        self.alt_m         = None
        self.speed_kmh     = None
        self.heading       = None
        self.satellites    = 0
        self.timestamp_utc = None
        self.valid         = False

    def as_dict(self):
        return {
            "gps_lat":        round(self.lat, 6)       if self.lat       is not None else None,
            "gps_lon":        round(self.lon, 6)       if self.lon       is not None else None,
            "gps_alt_m":      round(self.alt_m, 1)     if self.alt_m     is not None else None,
            "gps_speed_kmh":  round(self.speed_kmh, 1) if self.speed_kmh is not None else None,
            "gps_heading":    round(self.heading, 1)   if self.heading   is not None else None,
            "gps_satellites": self.satellites,
            "gps_valid":      self.valid,
        }


class GPSReader:
    def __init__(self, port=GPS_PORT, baud=GPS_BAUD):
        self.port    = port
        self.baud    = baud
        self._lock   = threading.Lock()
        self._fix    = GPSFix()
        self._stop   = threading.Event()
        self._thread = threading.Thread(target=self._run, name="GPSReader", daemon=True)
        self.running = False

    def start(self):
        self._stop.clear()
        self._thread.start()
        self.running = True
        logger.info(f"GPS reader iniciado en {self.port} @ {self.baud}")

    def stop(self):
        self._stop.set()
        self.running = False
        logger.info("GPS reader detenido")

    def get_fix(self):
        with self._lock:
            f = GPSFix()
            for s in GPSFix.__slots__:
                setattr(f, s, getattr(self._fix, s))
            return f

    def _run(self):
        while not self._stop.is_set():
            try:
                import subprocess
                subprocess.run(['stty', '-F', self.port, str(self.baud), 'raw'], check=False)
                with serial.Serial(self.port, self.baud, timeout=GPS_TIMEOUT,
                                   xonxoff=False, rtscts=False, dsrdtr=False) as ser:
                    import time as _time
                    def _ubx(cls, id_, payload):
                        p = bytes([cls, id_]) + len(payload).to_bytes(2, 'little') + payload
                        ck_a = ck_b = 0
                        for b in p:
                            ck_a = (ck_a + b) & 0xFF
                            ck_b = (ck_b + ck_a) & 0xFF
                        return b'\xB5\x62' + p + bytes([ck_a, ck_b])
                    def _wait_ack(ser, cls, id_, timeout=1.0):
                        """Wait for UBX-ACK-ACK or UBX-ACK-NAK"""
                        deadline = _time.monotonic() + timeout
                        buf = b''
                        while _time.monotonic() < deadline:
                            buf += ser.read(ser.in_waiting or 1)
                            # ACK-ACK: B5 62 05 01 02 00 <cls> <id>
                            ack = bytes([0xB5,0x62,0x05,0x01,0x02,0x00,cls,id_])
                            nak = bytes([0xB5,0x62,0x05,0x00,0x02,0x00,cls,id_])
                            if ack in buf: return True
                            if nak in buf: return False
                        return None  # timeout
                    # CFG-RATE: 200ms = 5Hz, navRate=1, timeRef=GPS
                    _time.sleep(1.0)
                    ser.reset_input_buffer()
                    ser.write(_ubx(0x06, 0x08, bytes([0xC8,0x00,0x01,0x00,0x01,0x00])))
                    ack = _wait_ack(ser, 0x06, 0x08, timeout=2.0)
                    if ack is True:
                        logger.info("GPS 5Hz configurado (solo RAM)")
                    elif ack is False:
                        logger.warning("GPS CFG-RATE: NAK recibido — comando rechazado")
                    else:
                        logger.warning("GPS CFG-RATE: sin ACK — módulo puede estar en baud diferente")
                    ser.reset_input_buffer()
                    logger.info("Puerto GPS abierto")
                    while not self._stop.is_set():
                        line = ser.readline().decode("ascii", errors="replace").strip()
                        if line:
                            self._parse(line)
            except serial.SerialException as e:
                logger.warning(f"GPS serial error: {e} — reintentando en 3s")
                time.sleep(3)
            except Exception as e:
                logger.error(f"GPS error inesperado: {e}")
                time.sleep(3)

    def _parse(self, line):
        try:
            msg = pynmea2.parse(line)
        except pynmea2.ParseError:
            return
        with self._lock:
            if isinstance(msg, pynmea2.types.talker.RMC):
                new_valid = (msg.status == "A")
                if new_valid:
                    self._fix.lat        = msg.latitude
                    self._fix.lon        = msg.longitude
                    self._fix.speed_kmh  = msg.spd_over_grnd * 1.852 if msg.spd_over_grnd else 0.0
                    self._fix.heading    = float(msg.true_course) if msg.true_course else self._fix.heading
                    self._fix.timestamp_utc = str(msg.datetime)
                    self._fix.valid      = True
                else:
                    # Keep last known position, just mark as not fresh
                    self._fix.valid      = False
            elif isinstance(msg, pynmea2.types.talker.GGA):
                self._fix.satellites = int(msg.num_sats) if msg.num_sats else 0
                if msg.altitude is not None:
                    self._fix.alt_m = float(msg.altitude)
