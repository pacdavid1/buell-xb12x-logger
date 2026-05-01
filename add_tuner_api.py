filepath = 'web/server.py'
with open(filepath, 'r') as f:
    content = f.read()

# Agregar endpoints de la herramienta de tuning ANTES de las rutas estáticas
old_tuner = """        if path == '/tuner' or path == '/tuner.html':"""
new_tuner = """        if path == '/tuner/sessions':
            sessions = []
            for d in sorted(self.buell_dir.glob('sessions/*/session_metadata.json')):
                try:
                    with open(d) as mf: meta = json.load(mf)
                    sessions.append({
                        'id': d.parent.name,
                        'version': meta.get('version_string', '?'),
                        'rides': meta.get('total_rides', 0),
                        'created': meta.get('created_utc', '')[:10]
                    })
                except Exception: pass
            self._json({'sessions': sessions})
            return

        if path.startswith('/tuner/maps?session='):
            import urllib.parse
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            sess = params.get('session', [''])[0]
            if not sess: self._json({'error': 'Falta parámetro session'}, 400); return
            blob_path = self.buell_dir / 'sessions' / sess / 'eeprom.bin'
            if not blob_path.exists(): self._json({'error': 'No hay eeprom.bin'}, 404); return
            maps = _decode_eeprom_maps(blob_path.read_bytes())
            self._json(maps)
            return

        if path == '/tuner' or path == '/tuner.html':"""

if old_tuner in content:
    content = content.replace(old_tuner, new_tuner)
    print("EXITO: Endpoints de Tuner agregados a server.py")
else:
    print("AVISO: No se encontró la ruta /tuner")

with open(filepath, 'w') as f:
    f.write(content)
