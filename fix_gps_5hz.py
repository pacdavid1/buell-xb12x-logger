#!/usr/bin/env python3
"""Agrega configuración 5Hz al GPSReader al abrir el puerto"""

path = "/home/pi/buell/gps/reader.py"
content = open(path).read()

OLD = "                with serial.Serial(self.port, self.baud, timeout=GPS_TIMEOUT,\n                                   xonxoff=False, rtscts=False, dsrdtr=False) as ser:\n                    logger.info(\"Puerto GPS abierto\")"
NEW = """                with serial.Serial(self.port, self.baud, timeout=GPS_TIMEOUT,
                                   xonxoff=False, rtscts=False, dsrdtr=False) as ser:
                    # Configure 5Hz update rate (UBX-CFG-RATE, measRate=200ms)
                    ubx_5hz = bytes([
                        0xB5, 0x62, 0x06, 0x08, 0x06, 0x00,
                        0xC8, 0x00, 0x01, 0x00, 0x01, 0x00,
                        0xDE, 0x6A
                    ])
                    ser.write(ubx_5hz)
                    import time as _time; _time.sleep(0.3)
                    ser.reset_input_buffer()
                    logger.info("Puerto GPS abierto — 5Hz configurado")"""

assert OLD in content, "NOT FOUND"
content = content.replace(OLD, NEW)
open(path, "w").write(content)
print("OK")
