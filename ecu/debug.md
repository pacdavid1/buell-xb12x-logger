La verdad incómoda primero: main.py es el archivo más limpio del proyecto. Si esto es lo que me mandas primero, estás protegiéndome de los archivos que realmente tienen riesgo — ecu/logger_process.py, ecu/session.py, y web/server.py. Ahí es donde están tus bugs históricos. Auditemos esos.

Dicho eso, sí hay problemas reales aquí:

[Seguro] BUG 1 — Race condition en _ipc_reader_loop leyendo live.json

live = json.loads(live_path.read_text())


read_text() no es atómica. El subprocess escribe live.json via atomic rename (correcto), pero si el rename ocurre durante el read_text() en un filesystem tmpfs bajo carga, puedes leer un archivo parcial. El resultado es un json.JSONDecodeError que cae al except Exception as e: self.logger.debug(...) — silencioso. El web server sirve datos stale sin que nadie lo sepa.

Fix: Wrap en retry con backoff corto, o valida el JSON antes de usarlo.

[Seguro] BUG 2 — os.execv en sysmon mata el ride sin garantía

if stats['mem_pct'] > 90:
    self._stop_logger_subprocess(timeout=5.0)
    os.execv(sys.executable, [sys.executable] + sys.argv)


_stop_logger_subprocess manda SIGTERM y espera hasta 5s. Pero os.execv reemplaza el proceso inmediatamente después — no espera a que el subprocess confirme que cerró el ride limpiamente. Si el subprocess tarda más de 5s en hacer flush del CSV (ride largo, SD lenta), el ride se trunca y session_metadata.json queda corrupto. Esto es exactamente BACKLOG-INF1.

[Probable] BUG 3 — Heartbeat inicial en _check_threads es 0

self._ipc_reader_heartbeat = time.monotonic()  # en __init__


El heartbeat se inicializa en __init__, pero los threads arrancan segundos después en run(). Si _check_threads corre antes de que el thread actualice su heartbeat (posible si el thread tarda en iniciar), el watchdog calcula now - heartbeat > 10.0 como falso positivo y lo reinicia prematuramente. Poco probable en práctica pero el fix es inicializar el heartbeat dentro del thread, no en __init__.

[Suposición] DISEÑO — _sysmon_loop duerme GPS_RESTART_DELAY = 2.0s en lugar de su propio intervalo

El sysmon hace lecturas de CPU, RAM, BMP280, AHT20, CW2015, escribe 2 archivos IPC, y luego duerme… 2 segundos que se llaman GPS_RESTART_DELAY. Eso es una constante semánticamente equivocada usada en el lugar incorrecto. Si alguien cambia GPS_RESTART_DELAY por razones de GPS, cambia sin querer el polling rate del sysmon. Necesita su propia constante SYSMON_INTERVAL_S.

Mándame ecu/logger_process.py y ecu/session.py. Ahí es donde vale la pena auditar de verdad.

---

La verdad incómoda: este archivo está sorprendentemente limpio para ser el corazón del sistema. Los bugs reales están en session.py — este archivo es casi un wrapper que delega todo lo crítico. Aún así, hay problemas concretos:

[Seguro] BUG 1 — Double-count de consecutive_errors

except Exception as e:
    ...
    consecutive_errors += 1   # ← aquí
    data = None

if data is None:
    consecutive_errors += 1   # ← y aquí otra vez


Cuando get_rt_data() lanza excepción, consecutive_errors se incrementa dos veces por frame. MAX_CONSEC_ERRORS = 30 se alcanza en 15 frames reales (~1.9s) en lugar de 30 (~3.75s). La desconexión forzada ocurre el doble de rápido de lo que diseñaste.

[Seguro] BUG 2 — Hard reconnect no restaura ecu_version

ecu.connect()
if ecu.get_version():
    log.info("ECU back after hard reconnect")
    consecutive_errors = 0
    ecu_lost_since = None


ecu.get_version() regresa la versión pero no la asignas a ecu_version. Si después de este reconnect hay un burn request, el subprocess usa el ecu_version stale del connect anterior — o None si nunca se asignó. El burn queda registrado como 'post-burn' incluso cuando la versión es conocida.

[Seguro] BUG 3 — elapsed_s en el path de error es incorrecto

elapsed_s = (time.monotonic() - session.ride_start_time
             if ride_active and session.ride_start_time else 0.0)
try:
    data = ecu.get_rt_data()
except Exception as e:
    error_log.serial_exception(elapsed_s=elapsed_s, ...)


elapsed_s se calcula antes del read, al inicio del loop. Si el read tarda (timeout serial de 200ms+), el timestamp del error en el log está desplazado hacia atrás. Menor, pero contamina el error log para análisis forense.

[Probable] BUG 4 — VSS calibration se guarda en disco cada frame que cambia significativamente

if vss_changed_significantly():
    save_vss_calibration(str(buell_dir / 'vss_cal.json'))


save_vss_calibration escribe a la SD card. Si la moto está en un rango donde VSS fluctúa (curva, aceleración no lineal), esto puede dispararse 3-4 veces por segundo — cada vez una escritura a SD. A 8 Hz con rides de 45 minutos, estás potencialmente acortando la vida de la SD con escrituras innecesarias. Necesita un cooldown mínimo de 30s entre saves.

[Suposición] DISEÑO — _read(ipc_dir / 'sysmon.json') dentro del ride loop sin caché

Cada frame activo lee sysmon.json del tmpfs. El tmpfs está en RAM así que no es un problema de I/O, pero si sysmon.json no existe todavía (boot temprano), _read regresa {} silenciosamente y el CSV queda con cpu_pct=0, baro_hPa=None en las primeras filas. No es un bug, pero deberías tener un valor sentinel (-1 o similar) para distinguir “sensor no disponible” de “lectura legítima de cero”.

Mándame session.py. Los bugs 1 y 2 son los que yo parchearía hoy.

---

La verdad incómoda: session.py es el archivo más peligroso del stack y tiene un bug silencioso que puede corromper tu tuning report sin que te enteres.

[Seguro] BUG CRÍTICO — Variable v en _update_tuning_report referencia el loop anterior

for k, a in agg.items():
    ...
    "o2_adc_avg": round(v["o2_adc_sum"] / n, 1) if n else None,  # ← v no existe aquí


v es la variable del loop for k, v in cells.items() que ya terminó. En _update_tuning_report el loop activo es for k, a in agg.items(). Cuando llegas a o2_adc_avg, v es el último elemento del loop de cells del ride anterior, no la celda actual. Cada celda del tuning report tiene el o2_adc_avg de otra celda. Es un bug de scope silencioso — no lanza excepción, solo produce datos incorrectos.

Fix:

"o2_adc_avg": round(a["o2_adc_sum"] / n, 1) if n else None,


[Seguro] BUG 2 — _load_or_create no reinicializa meta cuando la corrupción es parcial

except Exception as e:
    self.logger.warning(f"session_metadata.json corrupted, reinitializing: {e}")
    meta = None


Cuando meta = None, el caller open_session recibe (sdir, None) y asigna self.session_metadata = None. Cualquier llamada posterior a self.session_metadata.get(...) en start_ride o close_current_ride lanza AttributeError. El ride no arranca y el error se traga en el except RuntimeError de logger_process.py. Pierdes el ride silenciosamente.

Fix: En el except, inicializa meta con el dict vacío completo, no None.

[Seguro] BUG 3 — recover_orphan_rides actualiza session_metadata.json sin atomic write

with open(meta_file,"w") as f: json.dump(meta,f,indent=2)


Todo el resto del código usa tmp.replace(). Este es el único lugar que escribe directo. Si el Pi pierde poder durante recover_orphan_rides (que corre en boot), session_metadata.json queda truncado — exactamente el escenario que BACKLOG-INF1 intenta prevenir. La ironía: el código de recuperación es el que puede causar corrupción.

[Probable] BUG 4 — close_current_ride puede llamarse dos veces sin protección

def close_current_ride(self, reason="", ...):
    if not self.current_csv_fh:
        return
    ...
    self.current_csv_fh.close()
    self.current_csv_fh = None


El guard es if not self.current_csv_fh. Pero entre el check y el close() no hay lock. SessionManager no tiene threading.Lock(). En el subprocess esto es single-threaded así que es seguro — pero main.py también tiene un SessionManager como “sync target” y el IPC reader lo modifica desde su thread. Si algún día un endpoint web llama close_current_ride directamente, esto explota.

[Suposición] DISEÑO — Health score es frágil para tu caso de uso real

warm_factor = 40 if any_warm else 0  # binario: 0 o 40


En Tijuana en verano arrancas caliente en 3 minutos. En invierno tardas 8. El score salta de 0 a 40 en el frame exacto donde clt >= 70, creando un cliff que hace que rides cortos de verano parezcan menos saludables que rides largos de invierno. Considera un ramp: warm_factor = min(40, clt_max_seen / 70 * 40).

Prioridad de fixes:

	1.	BUG CRÍTICO de v vs a — tus sugerencias VE de o2_adc son basura ahora mismo
	2.	BUG 2 — meta = None puede silenciar rides enteros
	3.	BUG 3 — atomic write en recover_orphan_rides

¿Quieres que te genere los tres patches con el patrón fix_*.py + assert guards que usas?

---

La verdad incómoda: connection.py es el archivo más sólido que has mandado. Los bugs reales aquí son sutiles, no estructurales. Si esperabas hallazgos dramáticos, el problema está en otra parte del stack.

[Seguro] BUG 1 — _send y _read_exact no comparten el mismo lock

def _send(self, pdu):
    with self._lock:          # adquiere RLock
        ...
        self.ser.write(pdu)

def _read_exact(self, n, timeout_s):
    # sin lock
    ...
    chunk = self.ser.read(...)


_get_rt_data_impl ya corre bajo self._lock via get_rt_data(), así que en práctica el RLock reentrant lo protege. Pero _read_exact se llama también desde get_version, read_eeprom_page, y write_eeprom_page — algunos bajo lock, algunos no. El contrato implícito es frágil. Si alguien añade un caller nuevo sin lock, la corrupción serial es silenciosa.

[Seguro] BUG 2 — _sync_to_soh tiene el docstring DESPUÉS de la primera línea de código

def _sync_to_soh(self, timeout_s: float = 0.5) -> bool:
    if not self.ser:
        return False
    """Descarta basura del buffer hasta encontrar SOH (0x01)."""


El docstring es una string literal flotante — no es el docstring de la función, es una expresión que Python evalúa y descarta. No afecta el comportamiento pero cualquier herramienta que genere docs (help(), Sphinx, pylsp) reporta esta función sin documentación. Mueve el docstring antes del if.

[Seguro] BUG 3 — usb_power_cycle no hace power cycle real

with open(f'{h}/power/autosuspend_delay_ms', 'w') as f: f.write('0')
time.sleep(1.0)
with open(f'{h}/power/level', 'w') as f: f.write('on')


Esto configura autosuspend y fuerza on — no desconecta y reconecta el USB. Un power cycle real requiere escribir auto → esperar → on, o usar authorized (0 → 1). Lo que tienes actualmente solo asegura que el hub no entre en suspend. Si el dwc2 está hung, esto no lo recupera. El log dice “power cycle completado” pero es mentira — es un no-op en el escenario exacto donde lo necesitas.

[Probable] BUG 4 — write_full_eeprom con safe_end=1205 incluye el byte 1205 que no existe en ninguna página

BUEIB_PAGES = [
    (6, 1182, 24),   # cubre 1182..1205 inclusive
]
diffs = [i for i in range(safe_start, safe_end + 1) ...]  # incluye 1205


range(670, 1206) incluye offset 1205. La página 6 cubre 1182 + 24 = 1206 bytes, entonces 1182..1205 es correcto — 1205 sí existe. Falsa alarma, pero el off-by-one es suficientemente sutil para merecer un comentario en el código.

[Suposición] DISEÑO — Chunk merging con gap de 4 bytes puede escribir bytes no modificados

if next_abs - chunk_end > 4:  # gap too large — new chunk
    break
chunk_end = next_abs


Cuando el gap entre diffs es ≤4, el chunk incluye esos bytes intermedios y los escribe con los valores de proposed aunque sean idénticos al actual. En una EEPROM Flash esto cuenta como ciclo de escritura innecesario. En tu ECU específicamente no sé si importa — depende del tipo de memoria. Si es EEPROM byte-rewritable sin wear leveling, acorta su vida en zonas calientes del mapa.

Siguiente: web/server.py o ecu/protocol.py — ¿cuál?

---

La pregunta que deberías hacerte antes de defender este diseño: ¿de dónde sacaste los offsets 870, 1038, 670, 770, 632, 644? Si la respuesta es “los reverse-engineereé del EEPROM”, entonces tu código es una fotografía de tu ECU específica, no una implementación del protocolo DDFI2.

[Seguro] PROBLEMA ESTRUCTURAL — Los offsets están hardcodeados contra lo que dices que no debe estar hardcodeado

"fuel_front":  read_map(870,  12, 13, 1.0),
"fuel_rear":   read_map(1038, 12, 13, 1.0),
"spark_front": read_map_spark(670, 10, 10, 0.25),


Tú mismo me acabas de decir que el EEPROM debería decodificarse desde los XML de EcmSpy. Pero aquí tienes exactamente lo contrario — offsets fijos que coinciden con una versión de firmware (BUEIB). Si alguien conecta una ECU con firmware BUEIB2 o una variante regional, decode_eeprom_maps lee basura y la retorna como datos válidos porque _validate_eeprom no valida los offsets de los mapas, solo los ejes.

[Seguro] BUG 1 — _validate_eeprom valida el eje de fuel (offset 632) pero decode_eeprom_maps no usa ese resultado para los mapas

if any(eeprom_bytes[632 + i] == 0 for i in range(12)):
    return False


La validación checa que los 12 load bins no sean cero. Pero decode_eeprom_maps llama _validate_eeprom y si pasa, asume que todos los offsets son válidos — incluyendo 870 para fuel_front. Un EEPROM con load bins correctos pero mapa de fuel corrupto pasa la validación y produce VE values basura que van directo al tuning report.

[Seguro] BUG 2 — encode_eeprom_maps no toca el separator byte pero tampoco lo valida

# separator byte at row_off + cols is NOT touched


El comentario dice que no toca el separator. Pero en read_map el separator se asume que siempre es 0x00. Si algún burn anterior corrompió un separator byte, read_map lo ignora porque lee por offset fijo — correcto. Pero encode_eeprom_maps escribe el nuevo mapa sin verificar que el separator sigue siendo 0x00 después del write. Si el separator se corrompió a un valor no-cero, el round-trip decode→encode→decode produce resultados distintos silenciosamente.

[Probable] BUG 3 — BUEIB_PARAMS tiene KMFG_Year en offset 3 pero _validate_eeprom valida Manufacturing Year en offset 9

"KMFG_Year": (3, 1.0, 0.0, "", "Anio fabricacion ECM"),
# vs
if not (0 <= eeprom_bytes[9] <= 99):  # offset 9 en _validate_eeprom


Son dos offsets distintos para el mismo concepto. Uno de los dos está equivocado, o son campos distintos que el comentario describe igual. Si offset 9 no es Manufacturing Year sino otra cosa, la validación está chequeando el campo equivocado.

[Suposición] Lo que debería hacer este archivo si quisieras ser fiel a los XML de EcmSpy

EcmSpy exporta un .xml con <constant name="veBins1"> que define el offset, rows, cols, y scale de cada tabla. El diseño correcto sería:

def decode_eeprom_maps(eeprom_bytes, xml_def):
    fuel_front_def = xml_def['veBins1']
    return read_map(eeprom_bytes, 
                    fuel_front_def['offset'],
                    fuel_front_def['rows'],
                    fuel_front_def['cols'],
                    fuel_front_def['scale'])


Donde xml_def viene de parsear el XML de EcmSpy una sola vez al detectar la versión del firmware. Los offsets dejan de estar en el código y viven en los XML que ya tienes. Eso es lo que me dijiste que debería ser — y no lo es.

Mándame ecu/protocol.py. Necesito ver cómo RPM_BINS y LOAD_BINS se relacionan con los ejes que acabas de mostrar en decode_eeprom_maps — sospecho que hay una inconsistencia entre los bins del tracker y los bins reales del mapa de la ECU.

---


La inconsistencia que sospechaba existe y es peor de lo que esperaba.

[Seguro] INCONSISTENCIA CRÍTICA — RPM_BINS en protocol.py no coincide con los ejes reales del mapa ECU

# protocol.py — bins del CellTracker
RPM_BINS = [0, 800, 1000, 1350, 1900, 2400, 2900, 3400, 4000, 5000, 6000, 7000, 8000]
# 13 valores = 12 intervalos

# eeprom.py — eje real leído del EEPROM
"fuel_rpm": read_axis_2b(644, 13)  # 13 valores leídos del hardware


El CellTracker acumula tiempo y EGO usando RPM_BINS hardcodeado. El mapa VE real de la ECU usa los ejes que decode_eeprom_maps lee del EEPROM. Si los ejes del EEPROM no son exactamente [0, 800, 1000, 1350, ...], tus sugerencias de tuning están apuntando a celdas equivocadas del mapa. El _generate_suggested_msq busca rpm_v in fuel_rpm — si RPM_BINS[i] != fuel_rpm[i], la sugerencia no aplica y applied cuenta cero silenciosamente.

¿Has comparado RPM_BINS contra lo que decode_eeprom_maps realmente retorna en tu ECU?

[Seguro] BUG — decode_rt_packet retorna None explícitamente pero está tipado como dict

def decode_rt_packet(raw_bytes: bytes) -> dict[str, Any]:
    if len(raw_bytes) < RT_RESPONSE_SIZE:
        return None  # viola el type hint


logger_process.py llama decode_rt_packet desde dentro de get_rt_data_impl que ya atrapa None. Pero cualquier caller futuro que confíe en el type hint y haga data['RPM'] sin checar None primero explota con TypeError. El tipo correcto es dict[str, Any] | None.

[Seguro] BUG — elapsed_s en decode_rt_packet usa Seconds del ECU, no time.monotonic()

elapsed_s=result.get('Seconds', 0.0) + result.get('MilliSec', 0.0) / 1000.0,


Seconds es el contador interno del ECU — se resetea cuando el ECU se resetea, no cuando arranca el ride. Si el ECU se cuelga y reconecta mid-ride, elapsed_s retrocede a cero. El GearFilter usa este valor para su ventana temporal de 3 segundos y el cliff detector. Un reset del ECU hace que todos los samples del buffer sean “del futuro” respecto al nuevo elapsed_s, el cutoff no evicta nada, y el detector queda con datos mezclados de antes y después del reset.

[Probable] BUG — _gear_filter y _vss_calibrator son singletons de módulo

_gear_filter    = GearFilter()
_vss_calibrator = VSSCalibrator(initial=VSS_CPKM25)


Si en algún momento importas protocol.py en dos contextos distintos dentro del mismo proceso — digamos un test runner o un futuro modo multi-bike — ambos comparten el mismo filtro de marcha y calibrador VSS. No es un bug hoy porque el subprocess es single-threaded, pero es una bomba de tiempo arquitectural. El estado debería vivir en el caller, no en el módulo.

[Suposición] LOAD_BINS probablemente sí coincide con el EEPROM pero no lo puedes saber sin compararlo

LOAD_BINS = [10, 15, 20, 30, 40, 50, 60, 80, 100, 125, 175, 255]


decode_eeprom_maps lee fuel_load desde offset 632 con 12 valores. Si el EEPROM de tu ECU tiene exactamente esos 12 valores en ese orden, estás bien. Si no, mismo problema que RPM_BINS. La validación en _validate_eeprom solo checa que no sean cero, no que coincidan con LOAD_BINS.

La fix correcta para todo esto: cuando decode_eeprom_maps carga los ejes del EEPROM, esos valores deberían reemplazar RPM_BINS y LOAD_BINS en el CellTracker — no coexistir con ellos como duplicados potencialmente inconsistentes. Mándame web/server.py o dime si quieres atacar esta inconsistencia primero.

---


