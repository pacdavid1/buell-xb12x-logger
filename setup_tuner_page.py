filepath = 'web/server.py'
with open(filepath, 'r') as f:
    content = f.read()

# Buscar el handler de "/" para copiar su lógica y crear "/tuner"
old_index = """        if path in ('/', '/index.html'):
            self._html(self._load_html())
            return"""

new_index = """        if path == '/tuner' or path == '/tuner.html':
            try:
                tuner_file = Path(__file__).parent / 'templates' / 'tuner.html'
                if tuner_file.exists():
                    self._html(tuner_file.read_text(encoding='utf-8').replace('--LOGGER_VERSION--', _get_version()))
                else:
                    self._html("<h1>Buell Tuner - Página no encontrada</h1>")
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return

        if path in ('/', '/index.html'):
            self._html(self._load_html())
            return"""

if old_index in content:
    content = content.replace(old_index, new_index)
    print("EXITO: Ruta /tuner agregada a server.py")
else:
    print("AVISO: No se encontró el bloque de index.html")

with open(filepath, 'w') as f:
    f.write(content)

# 2. Crear la estructura base de tuner.html
tuner_html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Buell Tuner Studio</title>
<style>
:root{
  --bg:#0a0a0b;--panel:#111114;--border:#1e1e24;
  --accent:#e8420a;--accent2:#f5a623;--green:#2cdd6e;
  --blue:#3d9eff;--dim:#55555e;--text:#c8c8cc;
  --red:#ff4444;--mono:'Share Tech Mono',monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'Barlow Condensed',sans-serif;font-size:14px;min-height:100dvh;display:flex;flex-direction:column}
.hdr{background:var(--panel);border-bottom:2px solid var(--accent);padding:10px 15px;display:flex;justify-content:space-between;align-items:center;flex-shrink:0}
.hdr h1{font-size:18px;font-weight:900;letter-spacing:.05em;color:#fff}
.hdr a{font-family:var(--mono);font-size:10px;color:var(--dim);text-decoration:none;border:1px solid var(--border);padding:4px 8px;border-radius:2px}
.hdr a:hover{color:var(--blue);border-color:var(--blue)}
.content{flex:1;padding:20px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:15px}
.card{background:var(--panel);border:1px solid var(--border);padding:25px;border-radius:4px;max-width:500px;width:90%;text-align:center}
.card h2{font-family:var(--mono);font-size:12px;color:var(--accent);letter-spacing:.15em;margin-bottom:15px;text-transform:uppercase}
.card p{font-family:var(--mono);font-size:11px;color:var(--dim);line-height:1.6}
.badge{display:inline-block;padding:4px 10px;border-radius:3px;font-family:var(--mono);font-size:10px;margin-top:10px;color:var(--green);border:1px solid var(--green)}
</style>
</head>
<body>

<div class="hdr">
  <h1>⚙ BUELL TUNER STUDIO</h1>
  <a href="/">← Volver al Logger</a>
</div>

<div class="content">
  <div class="card">
    <h2>Módulo de Análisis y Modificación</h2>
    <p>
      Aquí se procesarán los mapas de VE, se aplicará el algoritmo 
      <strong>Delta Blend + Smoothing</strong> y se generarán los archivos <code>.msq</code> 
      para TunerStudio sin escalones ni aplanamiento no deseado.
    </p>
    <p>
      Funcionará 100% offline, cargando los <code>tuning_report.json</code> 
      generados por el Logger durante los rides.
    </p>
    <div class="badge">PRÓXIMAMENTE: Motor de Smoothing V3 + Visor de Deltas</div>
  </div>
</div>

</body>
</html>"""

with open('web/templates/tuner.html', 'w') as f:
    f.write(tuner_html)

print("EXITO: tuner.html creado")
