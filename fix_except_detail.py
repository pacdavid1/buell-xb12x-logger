#!/usr/bin/env python3
path = "/home/pi/buell/main.py"
content = open(path).read()

OLD = '        except Exception as e:\n            self.logger.warning(f"ECU no disponible: {e}")\n\n        # 2. Start RT and sysmon threads'
NEW = '        except Exception as e:\n            import traceback\n            self.logger.warning(f"ECU no disponible: {e}\\n{traceback.format_exc()}")\n\n        # 2. Start RT and sysmon threads'

assert OLD in content, "NOT FOUND"
content = content.replace(OLD, NEW)
open(path, "w").write(content)
print("OK")
