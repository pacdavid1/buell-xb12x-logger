#!/usr/bin/env python3
"""
tools/test_ecu.py - Diagnóstico de conexión ECU
Corre a mano: python3 tools/test_ecu.py
No modifica el servicio ni imports del proyecto.
"""
import serial
import time
import sys

PORT     = "/dev/ttyUSB0"
BAUD     = 9600
SOH      = 0x01
EOH      = 0xFF
SOT      = 0x02
EOT      = 0x03
ACK      = 0x06

PDU_VERSION = bytes([0x01,0x00,0x42,0x02,0xFF,0x02,0x56,0x03,0xE8])

def open_port():
    print(f"[1] Abriendo {PORT} a {BAUD},8N1...")
    ser = serial.Serial(
        port=PORT, baudrate=BAUD,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1.0,
        xonxoff=False, rtscts=False, dsrdtr=False
    )
    print(f"    OK — puerto abierto")
    return ser

def toggle_dtr(ser):
    print("[2] Toggle DTR (reset estado ECU)...")
    ser.dtr = False
    time.sleep(0.05)
    ser.dtr = True
    time.sleep(0.2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)
    print("    OK — DTR toggle completo")

def read_exact(ser, n, timeout_s=2.0):
    buf = bytearray()
    deadline = time.time() + timeout_s
    while len(buf) < n:
        rem = deadline - time.time()
        if rem <= 0:
            raise TimeoutError(f"Timeout — recibidos {len(buf)}/{n} bytes")
        ser.timeout = min(rem, 0.1)
        chunk = ser.read(n - len(buf))
        if chunk:
            buf.extend(chunk)
    return bytes(buf)

def get_version(ser):
    print("[3] Enviando PDU_VERSION...")
    print(f"    PDU: {PDU_VERSION.hex(' ').upper()}")
    for attempt in range(5):
        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(PDU_VERSION)
            ser.flush()
            print(f"    Intento {attempt+1}/5 — esperando respuesta...")
            h = read_exact(ser, 6, 2.0)
            print(f"    Header recibido: {h.hex(' ').upper()}")
            if h[0] != SOH:
                print(f"    byte[0]=0x{h[0]:02x} esperaba SOH=0x01 — retry")
                time.sleep(0.3)
                continue
            rest = read_exact(ser, h[3] - 1 + 2, 2.0)
            full = h + rest
            print(f"    Frame completo: {full.hex(' ').upper()}")
            if full[6] != ACK:
                print(f"    byte[6]=0x{full[6]:02x} esperaba ACK=0x06 — retry")
                time.sleep(0.3)
                continue
            ver = full[7:-2].decode("ascii", errors="replace").strip()
            print(f"\n    ECU VERSION: [{ver}]")
            return ver
        except TimeoutError as e:
            print(f"    {e}")
            time.sleep(0.3)
        except Exception as e:
            print(f"    Error inesperado: {e}")
            time.sleep(0.3)
    return None

def main():
    print("=" * 50)
    print("  Buell DDFI2 — Test de conexión ECU")
    print("=" * 50)
    ser = None
    try:
        ser = open_port()
        toggle_dtr(ser)
        ver = get_version(ser)
        if ver:
            print("\n[RESULTADO] CONEXION OK — ECU respondió")
        else:
            print("\n[RESULTADO] FALLO — ECU no respondió en 5 intentos")
            print("  Verificar: moto encendida, conector OBD conectado")
            sys.exit(1)
    except serial.SerialException as e:
        print(f"\n[ERROR] Puerto serial: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INTERRUMPIDO]")
    finally:
        if ser and ser.is_open:
            ser.close()
            print("[4] Puerto cerrado")

if __name__ == "__main__":
    main()
