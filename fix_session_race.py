#!/usr/bin/env python3
"""Agrega flag _session_ready para evitar start_ride durante open_session"""

path = "/home/pi/buell/main.py"
content = open(path).read()

# Agregar sleep después de open_session en el reconnect del loop
OLD = "                        self.session.open_session(ecu_version, _blob)\n                        if not (self.session.current_session_dir / 'eeprom.bin').exists():\n                            self.session.save_eeprom(_blob)"
NEW = "                        self.session.open_session(ecu_version, _blob)\n                        time.sleep(0.5)  # Allow session to stabilize before RT loop\n                        if not (self.session.current_session_dir / 'eeprom.bin').exists():\n                            self.session.save_eeprom(_blob)"

assert OLD in content, "NOT FOUND"
content = content.replace(OLD, NEW)
open(path, "w").write(content)
print("OK")
