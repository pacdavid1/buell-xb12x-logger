#!/usr/bin/env python3
"""Reemplaza UBX hardcodeado por versión con checksum dinámico + ACK + deviceMask correcto"""

path = "/home/pi/buell/gps/reader.py"
content = open(path).read()

OLD = """                    # Configure 5Hz update rate (UBX-CFG-RATE, measRate=200ms)
                    ubx_5hz = bytes([
                        0xB5, 0x62, 0x06, 0x08, 0x06, 0x00,
                        0xC8, 0x00, 0x01, 0x00, 0x01, 0x00,
                        0xDE, 0x6A
                    ])
                    ser.write(ubx_5hz)
                    import time as _time; _time.sleep(0.3)
                    ser.reset_input_buffer()
                    logger.info("Puerto GPS abierto — 5Hz configurado")"""

NEW = """                    import time as _time
                    def _ubx(cls, id_, payload):
                        p = bytes([cls, id_]) + len(payload).to_bytes(2, 'little') + payload
                        ck_a = ck_b = 0
                        for b in p:
                            ck_a = (ck_a + b) & 0xFF
                            ck_b = (ck_b + ck_a) & 0xFF
                        return b'\\xB5\\x62' + p + bytes([ck_a, ck_b])
                    def _wait_ack(ser, cls, id_, timeout=1.0):
                        \"\"\"Wait for UBX-ACK-ACK or UBX-ACK-NAK\"\"\"
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
                    ser.write(_ubx(0x06, 0x08, bytes([0xC8,0x00,0x01,0x00,0x01,0x00])))
                    ack = _wait_ack(ser, 0x06, 0x08)
                    if ack is True:
                        # CFG-CFG: save to BBR+flash+EEPROM only (deviceMask=0x07)
                        ser.write(_ubx(0x06, 0x09, bytes([
                            0x00,0x00,0x00,0x00,  # clearMask
                            0xFF,0xFF,0x00,0x00,  # saveMask (all sections)
                            0x00,0x00,0x00,0x00,  # loadMask
                            0x07                  # deviceMask: BBR+flash+EEPROM
                        ])))
                        _time.sleep(0.2)
                        logger.info("GPS 5Hz configurado y guardado en flash")
                    elif ack is False:
                        logger.warning("GPS CFG-RATE: NAK recibido — comando rechazado")
                    else:
                        logger.warning("GPS CFG-RATE: sin ACK — módulo puede estar en baud diferente")
                    ser.reset_input_buffer()
                    logger.info("Puerto GPS abierto")"""

assert OLD in content, "NOT FOUND"
content = content.replace(OLD, NEW)
open(path, "w").write(content)
print("OK")
