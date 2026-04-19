#!/usr/bin/env python3
path = "/home/pi/buell/gps/reader.py"
content = open(path).read()

OLD = "    def _run(self):\n        while not self._stop.is_set():\n            try:"
NEW = "    def _run(self):\n        while not self._stop.is_set():\n            try:\n                import os, stat\n                try:\n                    os.chmod(self.port, 0o666)\n                except Exception:\n                    pass  # best-effort, may fail if not root"

assert OLD in content, "NOT FOUND"
content = content.replace(OLD, NEW)
open(path, "w").write(content)
print("OK")
