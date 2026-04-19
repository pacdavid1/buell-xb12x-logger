#!/usr/bin/env python3
path = "/home/pi/buell/gps/reader.py"
content = open(path).read()

OLD = "                import os, stat\n                try:\n                    os.chmod(self.port, 0o666)\n                except Exception:\n                    pass  # best-effort, may fail if not root"
NEW = "                import subprocess as _sp\n                _sp.run(['sudo', '/bin/chmod', '666', self.port], check=False)"

assert OLD in content, "NOT FOUND"
content = content.replace(OLD, NEW)
open(path, "w").write(content)
print("OK")
