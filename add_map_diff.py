import re

t = open('/home/pi/buell/ddfi2_logger.py', 'r').read()

# 1. Agregar función de comparación de mapas después de decode_eeprom_maps
insert_after = '    except Exception as e:\n        return {"error": str(e)}'

new_func = '''    except Exception as e:
        return {"error": str(e)}

MAP_REGIONS = {
    "spark_front": (670, 100),
    "spark_rear":  (770, 100),
    "fuel_front":  (870, 156),
    "fuel_rear":   (1038, 156),
}

def diff_eeprom_maps(prev_bytes, curr_bytes):
    """Compara dos dumps EEPROM y retorna qué mapa(s) cambiaron.
    Retorna list of changed map names, o None si no hay prev."""
    if not prev_bytes or not curr_bytes:
        return None
    changed = []
    for name, (off, size) in MAP_REGIONS.items():
        prev_slice = prev_bytes[off:off+size]
        curr_slice = curr_bytes[off:off+size]
        if prev_slice != curr_slice:
            changed.append(name)
    return changed if changed else []'''

if insert_after in t:
    t = t.replace(insert_after, new_func)
    print("OK: diff_eeprom_maps agregada")
else:
    print("ERROR: no encontrado insert point")
    exit(1)

# 2. Guardar dump en sesión - después de leer EEPROM
old_save = '''                    self.dashboard.eeprom_maps   = decode_eeprom_maps(eeprom_bytes)
                    # Log límites críticos de temperatura'''

new_save = '''                    self.dashboard.eeprom_maps   = decode_eeprom_maps(eeprom_bytes)
                    # Guardar dump raw para comparación entre sesiones
                    dump_path = Path(self.session.session_dir) / "eeprom_raw.bin"
                    with open(dump_path, 'wb') as _f: _f.write(eeprom_bytes)
                    # Comparar con sesión anterior
                    prev_dump = self._find_prev_eeprom_dump()
                    if prev_dump:
                        changed = diff_eeprom_maps(prev_dump, eeprom_bytes)
                        self.dashboard.map_changes = changed
                        if changed is not None:
                            if len(changed) == 0:
                                self.logger.info("EEPROM: sin cambios vs sesión anterior")
                            elif len(changed) == 1:
                                self.logger.info(f"EEPROM: cambió solo {changed[0]} — atribuible")
                            else:
                                self.logger.warning(f"EEPROM: cambiaron {changed} — NO atribuible")
                        self.session.set_metadata("eeprom_map_changes", changed)
                    # Log límites críticos de temperatura'''

if old_save in t:
    t = t.replace(old_save, new_save)
    print("OK: save dump + diff al iniciar")
else:
    print("ERROR: no encontrado save point")
    exit(1)

# 3. Agregar método _find_prev_eeprom_dump en Dashboard.__init__ o como función
# Lo ponemos como método de BuellLogger, buscar un buen spot
init_spot = '    def _load_json(self, path, default=None):'

find_method = '''    def _find_prev_eeprom_dump(self):
        """Busca eeprom_raw.bin en la sesión anterior."""
        try:
            sessions_dir = Path(self.buell_dir) / "rides"
            if not sessions_dir.exists():
                return None
            current = self.session.session_dir
            sessions = sorted([d for d in sessions_dir.iterdir() if d.is_dir() and d != current])
            if not sessions:
                return None
            prev = sessions[-1]
            dump = prev / "eeprom_raw.bin"
            if dump.exists():
                self.logger.info(f"EEPROM prev: {dump.name} de sesión {prev.name}")
                return dump.read_bytes()
        except Exception as e:
            self.logger.debug(f"find_prev_dump: {e}")
        return None

    def _load_json(self, path, default=None):'''

if init_spot in t:
    t = t.replace(init_spot, find_method)
    print("OK: _find_prev_eeprom_dump agregado")
else:
    print("ERROR: no encontrado _load_json")
    exit(1)

# 4. Inicializar map_changes en Dashboard.__init__
old_init = 'self.eeprom_maps     = {}'
new_init = 'self.eeprom_maps     = {}\\n        self.map_changes     = None'

if old_init in t:
    t = t.replace(old_init, new_init)
    print("OK: map_changes inicializado")
else:
    print("ERROR: no encontrado init")
    exit(1)

open('/home/pi/buell/ddfi2_logger.py', 'w').write(t)
print("\nListo")
