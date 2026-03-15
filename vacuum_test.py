# vacuum_test.py - Prueba 10min SIN tocar nada tuyo
import serial
import time
from collections import deque

print("🚀 Test Hz REAL - Buell DDFI2")

# Config TUYA (cambia puerto si hace falta)
ser = serial.Serial('/dev/ttyUSB0', 19200, timeout=0.01)

msgs = 0
start = time.time()
dirty = 0

try:
    print("🔄 Conectando... (Ctrl+C para parar)")
    while True:
        data = ser.read(256)  # Lee todo lo que hay
        if data:
            msgs += 1
            # Cuenta dirty bytes
            dirty += sum(1 for b in data if b in [0x40, 0x60, 0xFF])
            
            # Cada 1000 mensajes = stats
            if msgs % 1000 == 0:
                elapsed = time.time() - start
                hz = msgs / elapsed
                dirty_pct = (dirty/msgs)*100
                print(f"📊 Msgs:{msgs:,} | Hz:{hz:.1f} | Dirty:{dirty_pct:.1f}%")
                
except KeyboardInterrupt:
    elapsed = time.time() - start
    hz_final = msgs / elapsed
    print(f"\n🏁 FINAL: {msgs:,} msgs | {hz_final:.1f}Hz | {elapsed:.0f}s")
