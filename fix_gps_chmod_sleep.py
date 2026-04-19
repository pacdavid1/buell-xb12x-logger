#!/usr/bin/env python3
path = "/home/pi/buell/gps/reader.py"
content = open(path).read()

OLD = "                import subprocess as _sp\n                _sp.run(['sudo', '/bin/chmod', '666', self.port], check=False)"
NEW = "                import subprocess as _sp, time as _t\n                _sp.run(['sudo', '/bin/chmod', '666', self.port], check=False)\n                _t.sleep(0.2)"

assert OLD in content, "NOT FOUND"
content = content.replace(OLD, NEW)
open(path, "w").write(content)
print("OK")
