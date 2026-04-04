with open('ddfi2_logger.py', 'r') as f:
    content = f.read()

old = 'LOGGER_VERSION = "v1.17.0-FORENSIC"  # ← único lugar a cambiar en cada release'
new = '''def _read_version():
    try:
        import re
        cl = open("/home/pi/buell/CHANGELOG.md").read()
        m = re.search(r"## \\[([^\\]]+)\\]", cl)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"
LOGGER_VERSION = _read_version()'''

content = content.replace(old, new, 1)

with open('ddfi2_logger.py', 'w') as f:
    f.write(content)

print("Done")
