# DEV NOTE: All code, comments, and variable names must be in English.
import re


def _get_version():
    try:
        cl = open("/home/pi/buell/CHANGELOG.md").read()
        end_comment = cl.find("-->")
        if end_comment != -1:
            cl = cl[end_comment:]
        m = re.search(r"## \[([^\]]+)\]", cl)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"
