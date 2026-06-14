web/server.py es casi solo un router — el código real está en los mixins (web/handlers/). Lo que sí hay aquí vale la pena auditar.

[Seguro] BUG CRÍTICO — DashboardHandler.server_instance es un atributo de clase compartido globalmente

class DashboardHandler(...):
    server_instance = None

def start(self):
    DashboardHandler.server_instance = self


ThreadingHTTPServer crea un nuevo DashboardHandler por cada request en su propio thread. Todos comparten el mismo server_instance de clase. Cuando _get_live hace:

self.server_instance.ecu_live
self.server_instance.serial_stats


…está leyendo atributos que el IPC reader thread modifica concurrentemente sin lock consistente. _data_lock existe pero _get_live no lo adquiere — lo hace solo el IPC reader al escribir. Lectura sin lock de dict que se reemplaza atomicamente en CPython funciona por casualidad del GIL, no por diseño. En PyPy o Python 3.13+ con free-threading esto explota.

[Seguro] BUG — _get_rides abre cada archivo CSV dos veces innecesariamente

with open(rf) as f:
    # lee header + primera línea
n = sum(1 for _ in open(rf) if not _.startswith('#')) - 1


Abre rf dos veces. La segunda apertura no tiene with — si el proceso muere entre las dos aperturas, el file descriptor queda abierto hasta que el GC lo recoja. En un Pi Zero con 50+ rides, son 100+ file descriptors abiertos simultáneamente durante el scan.

[Seguro] BUG — import os está en la línea 1 pero fuera del bloque de module docstring

import os
"""
WebServer - HTTP server...
"""


El docstring del módulo tiene que ser la primera expresión del archivo. Al poner import os antes, el módulo técnicamente no tiene docstring — web.server.__doc__ es None. Menor, pero indica que este archivo fue editado con prisa.

[Probable] BUG — _rides_cache_lock y _data_lock son locks distintos que protegen datos solapados

_rides_cache_lock protege _rides_cache. _data_lock protege ecu_live y serial_stats. Pero _get_live lee serial_stats sin ningún lock y _get_rides lee el filesystem sin lock. Si un endpoint llama _get_live mientras el IPC reader reemplaza serial_stats, la lectura puede ver el dict viejo o el nuevo dependiendo del scheduling. No es un crash — es una inconsistencia silenciosa de datos en el dashboard.

[Suposición] Los handlers en web/handlers/ probablemente tienen los bugs más gordos

Este archivo es limpio porque delega todo. FuelHandlerMixin, TunerHandlerMixin, EepromHandlerMixin — esos mixins son donde viven los endpoints que tocan session y cell_tracker directamente. Si quieres encontrar race conditions reales, necesito ver al menos web/handlers/tuner.py y web/handlers/eeprom.py.

¿Los mandas?