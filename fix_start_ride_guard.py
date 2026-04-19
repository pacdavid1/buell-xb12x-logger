#!/usr/bin/env python3
"""Atrapa RuntimeError de start_ride para que no mate el thread ECU"""

path = "/home/pi/buell/main.py"
content = open(path).read()

OLD = """                else:
                    ride_active    = True
                    rpm_zero_since = None
                    self.session.start_ride()
                    self.error_log.start(
                        ride_num=self.session.current_ride_num,
                        session_checksum=self.session.current_checksum,
                        session_dir=str(self.session.current_session_dir))
                    self.logger.info(f"Ride {self.session.current_ride_num:03d} iniciado")"""

NEW = """                else:
                    try:
                        self.session.start_ride()
                        ride_active    = True
                        rpm_zero_since = None
                        self.error_log.start(
                            ride_num=self.session.current_ride_num,
                            session_checksum=self.session.current_checksum,
                            session_dir=str(self.session.current_session_dir))
                        self.logger.info(f"Ride {self.session.current_ride_num:03d} iniciado")
                    except RuntimeError as e:
                        self.logger.warning(f"start_ride falló: {e} — esperando sesión activa")"""

assert OLD in content, "NOT FOUND"
content = content.replace(OLD, NEW)
open(path, "w").write(content)
print("OK")
