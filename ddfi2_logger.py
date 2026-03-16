#!/usr/bin/env python3
"""
====================================================================
  BUELL XB12X — DDFI2 ECU Logger
  Raspberry Pi Zero 2W + FT232RL → Serial 9600,8N1
====================================================================
  VERSION: ver constante LOGGER_VERSION (única fuente de verdad)
  CHANGELOG: últimas versiones con módulo y línea de cada cambio
  ─────────────────────────────────────────────────────────────────
  v1.17.0  (2026-03-15)  — MODO FORENSE: catálogo MYSTERY_BYTES + columnas dirty_byte_hex, dirty_byte_name, forensic_event

    [Python MYSTERY_BYTES]       ln 331+ — Diccionario para catalogar bytes sucios observados (0xFF,0x40,0x60,etc.)
    [Python CSV_COLUMNS]         ln 338+ — Añadidas tres columnas al CSV para registrar el último byte sucio y su nombre
    
  v1.16.1  (2026-03-13)  — DIAGNÓSTICO ECU + NOTAS AL CERRAR + VERSIÓN EN CSV

    [Python LOGGER_VERSION]        ln 301 — Bump a v1.16.1
    [Python _waiting_loop()]       ln 4178— Fix BUG-2: llama update_state() con live_data={}
                                            en cada iteración del loop de espera; el dashboard
                                            mantiene estado válido (waiting=True) antes de que
                                            el motor arranque — bigCHT/TPS/KPH visibles si ECU
                                            responde pero RPM=0
    [Python RideErrorLog]          new    — Método counts(): retorna {dirty, timeout, serial, total}
                                            para exponer en live.json sin leer el archivo
    [Python update_state()]        ln 2866— Agrega "ride_errors" al estado: dirty/timeout/serial/total
                                            contados sobre los eventos del ride activo
    [Python _sync_to_soh()]        ln 3309— Retry: si no encuentra SOH en 0.5s, hace flush del buffer
                                            + reenvía PDU_RT_DATA + reintenta con 0.4s; reduce
                                            dirty no-recovered de datos residuales en el buffer
    [Python start_new_csv()]       ln 3686— Escribe "# logger=LOGGER_VERSION" como primera línea
                                            del CSV antes del header; permite identificar versión
                                            sin abrir el archivo completo
    [JS parseCSVtoRows()]          ln 1955— Filtra líneas que empiezan con "#" para compatibilidad
                                            con el nuevo comentario de versión en CSV
    [JS closeRide()]               ln 1576— Cuando d.ok=false (ride ya fue auto-cerrado por reconexión),
                                            busca el último ride en /rides y abre el modal de notas
                                            automáticamente — el usuario nunca pierde la oportunidad
                                            de documentar la vuelta
    [HTML header]                  new    — Celda "ERR" (id=hErr) junto a Batt: muestra
                                            dirty+timeout del ride activo; color verde→naranja→rojo
                                            según densidad de errores (0/min→>2/min→>5/min)
    [JS fetchLive()]               ln 1274— Actualiza hErr con ride_errors del live.json;
                                            calcula errores/min para color dinámico

  v1.16.0  (2026-03-13)  — HTTP IMPROVEMENTS + GRÁFICAS v1.15.1 FUSIONADAS

    [Python imports]               ln 278 — ThreadingHTTPServer importado junto a HTTPServer;
                                            zlib importado para compresión gzip built-in
    [Python LiveDashboard.start()] ln 2950 — HTTPServer → ThreadingHTTPServer: requests
                                            paralelas (live.json + CSV + POST simultáneos)
                                            sin bloqueo mutuo
    [Python LiveHandler._json()]   ln 2450 — Cache-Control: no-store en todas las respuestas
                                            JSON (datos dinámicos, nunca cachear)
    [Python do_GET /live.json]     ln 2460 — Cache-Control: no-cache, no-store además del
                                            header en _json(); doble seguro anti-cache
    [Python do_GET /csv/]          ln 2505 — Gzip automático si cliente soporta
                                            Accept-Encoding: gzip; comprime CSV con zlib
                                            (nivel 6); reduce transferencia 5-10x en WiFi
    [Python do_POST body]          ln 2555 — JSON parse errors logeados con logging.warning
                                            en lugar de silenciarse; payload queda {}
    [Python do_POST /keepalive]    ln 2600 — Rate limiting: ignora requests más frecuentes
                                            que cada 10s; evita spam desde múltiples tabs
    [Python open() sin with]       ln varios — 8 instancias de json.load(open(...)) y
                                            _csv.DictReader(open(...)) reemplazadas por
                                            with open(...) as f; evita resource leaks
                                            si hay excepción durante la lectura

  v1.15.0  (2026-03-12)  — DETECTOR MARCHA · TPS CAPTURA AUTO · LATENCY TIMER · VSS_RPM_RATIO

    [Python RT_VARIABLES]          ln 322 — Añade VSS_RPM_Ratio (offset 100, 1 byte): ratio
                                            interno calculado por la ECU para reducción de chispa
                                            a alta velocidad (Speed-RPM Ratio RPM Sample Duration
                                            confirmado en BUEIB.xml off=405)
    [Python CSV_COLUMNS]           ln 338 — Añade VSS_RPM_Ratio y Gear al CSV
    [Python constantes]            ln 363 — GEAR_KPH_PER_KRPM y GEAR_THRESHOLDS: ratios km/h por
                                            cada 1000 RPM para 5 marchas XB12X (transmisión stock)
    [Python parse_rt_data()]       ln 499 — Calcula Gear (0=neutro/desconocido, 1-5) con ratio
                                            VS_KPH / (RPM/1000) comparado contra GEAR_THRESHOLDS;
                                            requiere RPM > 500 y VS_KPH > 3 para activarse
    [Python DDFI2Connection.connect()] ln 3162 — Intenta configurar latency timer FT232RL a 2ms
                                            via sysfs tras abrir puerto; busca en
                                            /sys/bus/usb-serial/devices/ttyUSB*/latency_timer y
                                            /sys/bus/usb/drivers/ftdi_sio/*/latency_timer;
                                            silencioso si no encuentra el path
    [HTML header live]             ln 785 — Añade celda "Marcha" (id=hGear) con color #a8f entre
                                            Batt y Ride; muestra 1ª–5ª o N (neutro)
    [JS fetchLive()]               ln 1258 — Actualiza hGear con Gear de lv; muestra Nª o N
    [HTML Config TPS]              ln 1035 — Botón "⏺ Captura Auto (10s)" con barra de progreso
                                            y mensaje de estado; captura TPS_10Bit min/max durante
                                            10s polling live.json; rellena campos MIN/MAX automático
    [JS startTpsCapture()]         ln 2390 — Lógica de captura: 500ms polling de live.json durante
                                            10s, trackea min/max de TPS_10Bit (d.live.TPS_10Bit),
                                            rellena inputs y muestra resultado; requiere rango > 20
                                            para considerar captura válida

  v1.14.0  (2026-03-12)  — FECHA EN GRAF · VE ORDENADO · USB RESET · FIX SESIONES→GRAF

    [JS _rideDate()]               ln 2095 — Helper nuevo: formatea opened_utc → YYMMDDHHMM
                                             local (ej: 2603071410); fallback a closed_utc
    [JS _fillGraphSelect()]        ln 2081 — Opciones del dropdown Graf muestran fecha,
                                             duración y muestras por ride
    [JS loadGraphRide()]           ln 2106 — Acepta parámetro directFile opcional;
                                             muestra fecha en graphRideTitle (·  dd/mm/aa HH:MM)
    [JS openRideGraph()]           ln 1715 — Pasa r.filename directo a loadGraphRide() —
                                             elimina dependencia del select y race condition
    [JS openLiveRideGraph()]       ln 1723 — Mismo fix: filename directo, timeout 120ms
    [JS showMap()]                 ln 1340 — Eje RPM reordenado: período→RPM real (60M/período),
                                             columnas con período=0 descartadas, sorteo por
                                             RPM ascendente (izq=bajo, der=alto); celdas valor=0
                                             se muestran como · sobre fondo oscuro (sin datos)
    [Python get_rides()]           ln 2715 — Expone opened_utc y closed_utc por ride;
                                             corrige close_reason: lee "reason" del summary
                                             (campo real) con fallback a "close_reason"
    [Python SessionManager.start_ride()] ln 3458 — Guarda self._ride_start_utc al inicio
    [Python SessionManager.close_ride()] ln 3527 — Escribe opened_utc en summary JSON
    [Python DDFI2Connection.usb_reset()] ln 3045 — Método nuevo: busca FT232RL en sysfs
                                             (vendor=0403 product=6001), hace authorized=0
                                             → sleep(0.8) → authorized=1 → sleep(2.0)
    [Python _reading_loop]         ln 3815 — Escalación USB reset: si lost_total ≥ 60s y
                                             consecutive_errors % 60 == 0, llama conn.usb_reset()
                                             antes del intento de reconexión por DTR

  v1.13.1  (2026-03-11)  — ERRORLOG CTX + HARD RECONNECT

    [Python RideErrorLog.update_last_sample]  ln 3208 — Agrega vss (VS_KPH),
                                              seconds (Seconds ECU) y fl_learn
                                              al ctx de cada evento del errorlog
    [Python _reading_loop]                    ln 3708 — Hard reconnect automático:
                                              tras 30s de pérdida hace disconnect()
                                              + connect() (DTR toggle) aunque haya
                                              ride activo; registra intento en errorlog
                                              con trigger="auto_30s"; la lógica VERSION
                                              simple queda como fallback cuando no hay
                                              ride activo

  v1.13.0  (2026-03-10)  — RIDE ERROR LOG
    NUEVO FEATURE: registro estructurado de errores por ride.
    Archivo ride_NNN_errorlog.json solo se crea si hubo errores.
    Ride limpio = sin archivo = diagnóstico inmediato.

    [Python RideErrorLog]   ln ~3120 — Clase nueva: start/flush/clear + 5 métodos:
                                        serial_exception, dirty_bytes, bad_checksum,
                                        ecu_timeout, ecu_reset, reconnect_attempt
    [Python BuellLogger]    ln ~3440 — self.error_log = RideErrorLog() en __init__
    [Python _handle_sample] ln ~3500 — error_log.start() al arrancar ride
                                        error_log.update_last_sample() con cada sample
    [Python BuellLogger]    ln ~3478 — _flush_ride() helper: cierra ride + flushea
                                        errorlog en un solo punto — reemplaza todos
                                        los session.close_current_ride() directos
    [Python _reading_loop]  ln ~3590 — Hook serial_exception en except Exception
    [Python _reading_loop]  ln ~3600 — Hook dirty_bytes tras get_rt_data()
    [Python _reading_loop]  ln ~3615 — Hook ecu_timeout cada 10s de pérdida
    [Python _handle_sample] ln ~3500 — Hook ecu_reset cuando Seconds retrocede
    [Python get_rt_data]    ln ~2956 — self.last_dirty_byte: expone byte sucio al caller
    [Python LiveDashboard]  ln ~2591 — _errorlog_meta(): lee has_errorlog,
                                        errorlog_events, errorlog_summary
    [Python get_rides]      ln ~2614 — Incluye errorlog_meta en cada ride del listado
    [HTTP GET /errorlog]    ln ~2105 — Endpoint: retorna ride_NNN_errorlog.json
    [JS Sesiones]           ln ~1559 — Badge 🔴N en lista de rides si tiene errorlog
                                        tooltip muestra resumen (3ser 2dirty 1timeout)

  v1.12.1  (2026-03-10)
    [HTML pane-graph]       — graphRideTitle movido ANTES de graphStatus
                              (era invisible al quedar bajo el scroll de gráficas)
    [HTML graphRideTitle]   — Borde inferior sutil, padding top para separación visual
    [JS loadGraphRide]      — replace('_',' ') → replace(/_/g,' ') para todos los underscores

  v1.12.0  (2026-03-10)
    [CSS]                   ln 461  — .pill-dot: puntito de estado, quita texto "EN RIDE"
    [HTML header]           ln 633  — hPill: ahora pill-dot (sin texto)
    [JS updateHeader]       ln 1101 — ride activo = puntito verde parpadeante, sin letrero
    [HTML pane-graph]       ln 750  — div#graphRideTitle: muestra nombre del ride cargado
    [JS loadGraphRide]      ln 1887 — Muestra "▶ RIDE NNN" al cargar gráfica
    [HTML pane-rides]       ln 707  — Banner #liveRideBanner: ride activo visible en Sesiones
                                       con botón "Ver Graf" y timer
    [JS fetchLive]          ln 1203 — Actualiza liveRideBanner cada 2s
    [JS openLiveRideGraph]  ln ~1487 — Abre el ride más reciente en Graf
    [HTML pane-ve]          ln 797  — Reemplaza "coming soon" con tablas EEPROM reales
                                       4 mapas: Fuel Front/Rear, Spark Front/Rear
                                       Heatmap por celda, ejes RPM y TPS
    [tab VE onclick]        ln 651  — Auto-carga mapas al entrar por primera vez
    [JS loadMaps]           ln 1214 — GET /maps → renderiza tabla activa
    [JS showMap(which)]     ln 1236 — Render heatmap con ejes correctos, colores azul→rojo
    [JS heatColor]          ln 1296 — Gradiente 5 pasos para mapa de calor
    [Python /maps]          ln 2101 — Endpoint nuevo: retorna eeprom_maps
    [Python decode_eeprom_maps] ln 2935 — Lee 4 tablas + 4 ejes del EEPROM BUEIB
                                           offsets verificados vs ecmdroid.db
    [Dashboard.__init__]    ln 2337 — self.eeprom_maps = {} inicializado
    [BuellLogger init]      ln 3398 — Llama decode_eeprom_maps al leer EEPROM
    [BuellLogger reconex]   ln 3447 — Idem en reconexión

  v1.11.2  (2026-03-10)
    [HTML pane-graph]       ln 757  — Chart 5 renombrado "AFV & WUE %"
    [HTML pane-graph]       ln 762  — Chart 6 nuevo: "VOLTAJE BATERÍA (V)"
                                       canvas id=chartBatt height=70
    [C palette JS]          ln 1561 — Colores wue:#f90 y batt:#7df agregados
    [buildCharts JS]        ln 1742 — WUE agregado al chart AFV como serie
                                       punteada naranja; misma escala 85-115
    [buildCharts JS]        ln 1766 — Chart Batt_V nuevo; eje Y auto desde
                                       min/max del ride ±0.3V; línea ref 12.5V

  v1.11.1  (2026-03-10)
    [_reading_loop]         ln 3109 — try/except en get_rt_data(): captura
                                       excepciones de puerto serial roto;
                                       antes crasheaba silencioso sin llegar
                                       a estado waiting ni al botón Forzar
    [_reading_loop]         ln 3115 — _force_reconnect checkeado AL INICIO
                                       de cada iteración, antes de llamar
                                       get_rt_data(); antes podía bloquearse
                                       en timeout sin leer el flag
    [_reading_loop]         ln 3145 — Log "ECU recuperada" al volver de
                                       pérdida + reset _last_logged_lost_interval
    [buildCharts JS]        ln 1685 — Línea punteada EGO 100% en gráfica
                                       TPS%/EGO como dataset horizontal en y2

  v1.11.0  (2026-03-09)
    [HTML tab-bar]           ln 604  — trackUsage() en cada tab
    [HTML tab-bar]           ln 605  — Tab "Rides" renombrado a "Sesiones"
    [HTML tab-bar]           ln 608  — Tab Config carga loadUsageStats()
    [HTML pane-rides]        ln 647  — Rediseño completo: rides agrupados
                                       por sesión/checksum, colapsables,
                                       ordenados por ride más reciente arriba
    [HTML pane-rides]        ln 647  — Botones [Ver][Graf][📝] por ride
                                       directo, sin selección previa
    [HTML #noteModal]        ln 658  — Modal textarea para escribir/editar
                                       nota de bitácora por ride
    [HTML pane-graph]        ln 675  — dropdown graphRideSelect oculto;
                                       se pre-llena desde [Graf] en Sesiones
    [HTML cfg Uso]           ln 832  — Sección "Uso de funciones": barras
                                       de conteo, botón descargar JSON,
                                       botón limpiar contadores
    [Config btn reconexión]  ln 809  — Texto actualizado a descripción
                                       técnica del proceso completo
    [fetchLive JS]           ln 1083 — Actualiza cfgVersion desde live.json
    [JS closeRide()]         ln 1138 — Tras cerrar ride abre modal de nota
                                       automáticamente (800ms delay)
                                       + trackUsage('btn_close_ride')
    [JS loadSessions()]      ln 1262 — Reemplaza loadRidesList(); agrupa
                                       por sesión, colapsa/expande
    [JS toggleSession()]     ln 1325 — Colapsa/expande grupo de sesión
    [JS openNoteModal()]     ln 1330 — Abre modal, carga nota existente
    [JS closeNoteModal()]    ln 1343 — Cierra modal y recarga lista
    [JS saveNote()]          ln 1348 — POST /ride_note + trackUsage
    [JS viewSingleRide()]    ln 1361 — Ver cobertura + trackUsage
    [JS openRideGraph()]     ln 1366 — Manda ride a Graf + trackUsage
    [JS loadRidesList()]     ln 1377 — Alias → loadSessions()
    [JS trackUsage()]        ln 1454 — POST /usage fire-and-forget
    [JS loadUsageStats()]    ln 1459 — GET /usage_stats, renderiza barras
    [JS clearUsageStats()]   ln 1482 — POST /usage_clear, recarga lista
    [JS doShutdown()]        ln 1792 — trackUsage('btn_poweroff')
    [JS doReconnect()]       ln 1843 — trackUsage('btn_reconnect_ecu')
    [JS doRestartLogger()]   ln 1853 — trackUsage('btn_restart_logger')
    [JS doRebootPi()]        ln 1862 — trackUsage('btn_reboot_pi')
    [HTTP GET /usage_stats]  ln 1966 — Devuelve usage_stats dict
    [HTTP POST /usage]       ln 2137 — Incrementa contador + guarda JSON
    [HTTP POST /usage_clear] ln 2145 — Limpia usage_stats.json
    [LiveDashboard.__init__] ln 2196 — Carga usage_stats.json al arrancar
    [HTTP GET /ride_note]    ln 1909 — Devuelve nota de ride (txt)
    [HTTP POST /close_ride]  ln 2050 — Respuesta incluye session+ride_num
    [HTTP POST /ride_note]   ln 2068 — Guarda nota en ride_NNN_notes.txt
    [get_rides()]            ln 2221 — Agrega has_note + note_preview
                                       (primera línea, máx 60 chars)

  v1.10.3  (2026-03-09)
    [LOGGER_VERSION]     ln~70   — constante única; cambia solo aquí
                                   se refleja en log, live.json y Config
    [BUEIB_PARAMS]       ln~2533 — Fix Fan_On/Off translate 200→50
                                   (mostraba 370/330, correcto 220/180°C)
    [BUEIB_PARAMS]       ln~2543 — Fix Fan_KO_On/Off translate 200→0
    [HTML pane-cfg]      ln~688  — Bloque LOGGER VERSION con id=cfgVersion
    [LiveDashboard.__init__] ln~2007 — _state inicia con logger_version
                                       para mostrarla antes de conectar ECU
    [fetchLive JS]       ln~1039 — Actualiza cfgVersion desde live.json
    [live.json dict]     ln~2094 — Agrega campo logger_version
    [HTML hdr-stats]     ln~537  — KPH eliminado del header superior
    [updateHeader JS]    ln~931  — Línea hKPH eliminada del update

  v1.10.2  (2026-03-09)
    [BuellLogger.__init__] ln~2726 — Agrega _shutting_down=False
    [BuellLogger.__init__] ln~2727 — Agrega _last_logged_lost_interval=-1
    [_handle_signal]       ln~2750 — Marca _shutting_down=True en SIGTERM
    [_reading_loop]        ln~2862 — Fix spam: lost_interval//10 vs %10
    [_handle_sample]       ln~2769 — Reset _last_logged_lost_interval al
                                     recuperar ECU
    [run() while loop]     ln~2973 — reason="shutdown" si _shutting_down
    [run() while loop]     ln~2979 — Reset _last_logged_lost_interval
                                     al cerrar ride
    [run() elif waiting]   ln~2990 — Reconexión limpia: disconnect→sleep
                                     1s→connect→get_version→read_eeprom
                                     antes de open_session (igual arranque)

  v1.10.1  (2026-03-08)
    [SessionManager]     ln~2633 — duration_s usa last_elapsed_s (tiempo
                                   real de datos, no reloj del sistema)
    [initGraphPane JS]   ln~1053 — Carga lista rides si caché vacío
    [NetworkManager]     ln~2266 — Métodos scan/saved/connect/add/forget
    [HTTP handlers]      ln~1876 — Endpoints /wifi/scan /wifi/saved
                                   /wifi/connect /wifi/forget /wifi/add
    [HTML pane-net]      ln~820  — Pestaña Redes completa
    [HTML pane-cfg]      ln~750  — Botones WiFi/Hotspot movidos a Redes

  v1.10.0  (2026-03-08)
    [HTML/HTTP]          —       — Pestaña Redes añadida (base)
                                   Renombrada a v1.10.1 sin release

  v1.9.3  (2026-03-07)
    [NetworkManager.setup]      — Arranca siempre en hotspot
    [NetworkManager.switch_to_wifi] — nmcli con up casa explícito,
                                      timeout 35s, fallback a hotspot

  v1.9.x  (base)
    — CellTracker, Dashboard HTTP :8080, SessionManager CSV/JSON
    — EEPROM decode BUEIB 1206 bytes al arrancar
    — Detector DTC en tiempo real
    — Bits sucios: sync SOH, reset_input_buffer, PDU_VERSION recovery
====================================================================
"""

import serial
import struct
import time
import csv
import json
import os
import signal
import hashlib
import argparse
import logging
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
import zlib
import socket

LOGGER_VERSION = "v1.17.0-FORENSIC"  # ← único lugar a cambiar en cada release

# NUEVO v1.17.0: Catálogo de bytes misteriosos de DDFI2
MYSTERY_BYTES = {
    0xFF: {"name": "EOH_or_IDLE", "desc": "End of Header o línea idle", "sospechoso": False},
    0x01: {"name": "SOH", "desc": "Start of Header válido", "sospechoso": False},
    0x40: {"name": "BIT6_TPS_HIGH", "desc": "Bit 6 - posible DTC TPS alto", "sospechoso": True},
    0x60: {"name": "BITS_5_6_DUAL", "desc": "Bits 5+6 - error dual TPS", "sospechoso": True},
    0x06: {"name": "ACK", "desc": "Acknowledge válido", "sospechoso": False},
    0x00: {"name": "NULL_PAD", "desc": "Null padding", "sospechoso": True},
}
# ─────────────────────────────────────────────────────────────────
# PROTOCOLO PDU
# ─────────────────────────────────────────────────────────────────
SOH=0x01;EOH=0xFF;SOT=0x02;EOT=0x03;ACK=0x06
DROID_ID=0x00;STOCK_ECM_ID=0x42;CMD_GET=0x52
PDU_VERSION  = bytes([0x01,0x00,0x42,0x02,0xFF,0x02,0x56,0x03,0xE8])
PDU_RT_DATA  = bytes([0x01,0x00,0x42,0x02,0xFF,0x02,0x43,0x03,0xFD])
RT_RESPONSE_SIZE = 107

def build_pdu(payload_bytes):
    length=len(payload_bytes)+1
    frame=bytes([SOH,DROID_ID,STOCK_ECM_ID,length,EOH,SOT])+bytes(payload_bytes)+bytes([EOT])
    cs=0
    for b in frame[1:]: cs ^= b
    return frame+bytes([cs&0xFF])

RT_VARIABLES = {
    "RPM":(11,2,1.0,0.0),"Seconds":(9,2,1.0,0.0),"MilliSec":(8,1,0.01,0.0),
    "TPD":(25,2,0.1,0.0),"Load":(27,1,1.0,0.0),"TPS_10Bit":(90,2,1.0,0.0),
    "Batt_V":(28,2,0.01,0.0),"CLT":(30,2,0.1,-40.0),"MAT":(32,2,0.1,-40.0),
    "O2_ADC":(34,2,1.0,0.0),"WUE":(38,2,0.1,0.0),"IAT_Corr":(40,2,0.1,0.0),
    "Accel_Corr":(42,2,0.1,0.0),"Decel_Corr":(44,2,0.1,0.0),
    "WOT_Corr":(46,2,0.1,0.0),"Idle_Corr":(48,2,0.1,0.0),
    "OL_Corr":(50,2,0.1,0.0),"AFV":(52,2,0.1,0.0),"EGO_Corr":(54,2,0.1,0.0),
    "spark1":(13,2,0.0025,0.0),"spark2":(15,2,0.0025,0.0),
    "veCurr1_RAW":(17,2,1.0,0.0),"veCurr2_RAW":(19,2,1.0,0.0),
    "pw1":(21,2,0.00133,0.0),"pw2":(23,2,0.00133,0.0),
    "Flags0":(56,1,1.0,0.0),"Flags1":(57,1,1.0,0.0),"Flags2":(58,1,1.0,0.0),
    "Flags3":(59,1,1.0,0.0),"Flags4":(60,1,1.0,0.0),"Flags5":(61,1,1.0,0.0),
    "Flags6":(62,1,1.0,0.0),"Unk63":(63,1,1.0,0.0),
    "CDiag0":(67,1,1.0,0.0),"CDiag1":(68,1,1.0,0.0),"CDiag2":(69,1,1.0,0.0),
    "CDiag3":(70,1,1.0,0.0),"CDiag4":(71,1,1.0,0.0),
    "HDiag0":(75,1,1.0,0.0),"HDiag1":(76,1,1.0,0.0),"HDiag2":(77,1,1.0,0.0),
    "HDiag3":(78,1,1.0,0.0),"HDiag4":(79,1,1.0,0.0),
    "Unk80":(80,1,1.0,0.0),"Unk81":(81,1,1.0,0.0),"Unk82":(82,1,1.0,0.0),
    "Rides":(83,1,1.0,0.0),"DOut":(84,1,1.0,0.0),"DIn":(85,1,1.0,0.0),
    "ETS_ADC":(94,1,1.0,0.0),"IAT_ADC":(95,1,1.0,0.0),
    "SysConfig":(7,1,1.0,0.0),"BAS_ADC":(65,2,1.0,0.0),
    # VSS (counts per 39ms sample — proporcional a velocidad)
    "VSS_Count":(99,1,1.0,0.0),
    "Fan_Duty_Pct":(98,1,1.0,0.0),
    # Ratio VSS/RPM calculado por la ECU (byte raw, sin escala conocida)
    # Usado internamente por DDFI2 para reducción de chispa a alta velocidad
    "VSS_RPM_Ratio":(100,1,1.0,0.0),
}

CSV_COLUMNS = [
    "ride_num","timestamp_iso","time_elapsed_s",
    "RPM","Load","TPD","TPS_10Bit","CLT","MAT","Batt_V",
    "spark1","spark2","veCurr1_RAW","veCurr2_RAW","pw1","pw2",
    "EGO_Corr","WUE","AFV","IAT_Corr","Accel_Corr","Decel_Corr",
    "WOT_Corr","Idle_Corr","OL_Corr","O2_ADC",
    "Flags0","Flags1","Flags2","Flags3","Flags4","Flags5","Flags6","Unk63",
    "CDiag0","CDiag1","CDiag2","CDiag3","CDiag4",
    "HDiag0","HDiag1","HDiag2","HDiag3","HDiag4",
    "Unk80","Unk81","Unk82","Rides","DIn","DOut","ETS_ADC","IAT_ADC","BAS_ADC","SysConfig",
    # TPS calibrado
    "TPS_V","TPS_pct",
    # Velocidad y marcha
    "VSS_Count","VS_KPH","Fan_Duty_Pct","VSS_RPM_Ratio","Gear",
    # NUEVO v1.17.0: Columnas forenses
    "dirty_byte_hex","dirty_byte_name","forensic_event",
    # Flags decodificados — Flags1
    "fl_engine_run","fl_o2_active","fl_accel","fl_decel","fl_engine_stop","fl_wot","fl_ignition",
    # Flags2
    "fl_closed_loop","fl_rich","fl_learn",
    # Flags3
    "fl_cam_active","fl_kill","fl_immob",
    # Flags4
    "fl_fuel_cut",
    # Flags6
    "fl_hot",
    # DOut bits
    "do_coil1","do_coil2","do_inj1","do_inj2","do_fuel_pump","do_tacho","do_cel","do_fan",
    # DIn bits
    "di_cam","di_tacho_fb","di_vss","di_clutch","di_neutral","di_crank",
]

# Factor VSS — actualizado desde vss_cal.json al arrancar y via /vss_cal
# CPKM25=1368 calibrado con ride_015 a 50mph (80.5 kph) en dos marchas
VSS_CPKM25 = 1368.0

# Detección de marcha XB12X (5 velocidades)
# Umbral VS_KPH / (RPM/1000) — km/h por cada 1000 RPM por marcha
# Calculado con transmisión stock: primaria 34:46, corona 28:68, llanta 19"
# Ajustado empíricamente — calibrar con rides reales si difiere
GEAR_KPH_PER_KRPM = [0.0, 7.0, 11.8, 15.4, 19.1, 23.0]  # [0=neutro, 1-5]
GEAR_THRESHOLDS   = [
    (GEAR_KPH_PER_KRPM[1] + GEAR_KPH_PER_KRPM[2]) / 2,   # entre 1a y 2a
    (GEAR_KPH_PER_KRPM[2] + GEAR_KPH_PER_KRPM[3]) / 2,   # entre 2a y 3a
    (GEAR_KPH_PER_KRPM[3] + GEAR_KPH_PER_KRPM[4]) / 2,   # entre 3a y 4a
    (GEAR_KPH_PER_KRPM[4] + GEAR_KPH_PER_KRPM[5]) / 2,   # entre 4a y 5a
]  # = [9.4, 13.6, 17.25, 21.05]


# ─────────────────────────────────────────────────────────────────
# DTC MAP — CDiag bytes (offsets 67-74) → descripción + DTC number
# CDiag = errores ACTIVOS en tiempo real (bit=1 → error presente)
# HDiag (offsets 75-82) = mismos bits pero históricos (persistidos)
# Fuente: ecmdroid.db tabla adxbits + bits (EDiag)
# ─────────────────────────────────────────────────────────────────
DTC_MAP = {
    # (byte_name, bit): (dtc_num, description_corta)
    ("CDiag0",0): (14,  "ETS voltaje bajo"),
    ("CDiag0",1): (14,  "ETS voltaje alto"),
    ("CDiag0",2): (13,  "O2 trasero siempre rico"),
    ("CDiag0",3): (13,  "O2 trasero siempre pobre"),
    ("CDiag0",4): (13,  "O2 trasero inactivo"),
    ("CDiag0",5): (11,  "TPS voltaje bajo"),
    ("CDiag0",6): (11,  "TPS voltaje alto"),
    ("CDiag0",7): (36,  "Ventilador 1 corto a tierra"),
    ("CDiag1",0): (25,  "Bobina 1 voltaje bajo"),
    ("CDiag1",1): (25,  "Bobina 1 voltaje alto"),
    ("CDiag1",2): (23,  "Inyector 1 voltaje bajo"),
    ("CDiag1",3): (23,  "Inyector 1 voltaje alto"),
    ("CDiag1",4): (16,  "Batería voltaje bajo"),
    ("CDiag1",5): (16,  "Batería voltaje alto"),
    ("CDiag1",6): (15,  "IAT voltaje bajo"),
    ("CDiag1",7): (15,  "IAT voltaje alto"),
    ("CDiag2",0): (35,  "Tacómetro voltaje bajo"),
    ("CDiag2",1): (35,  "Tacómetro voltaje alto"),
    ("CDiag2",2): (33,  "Bomba combustible voltaje bajo"),
    ("CDiag2",3): (33,  "Bomba combustible voltaje alto"),
    ("CDiag2",4): (32,  "Inyector 2 voltaje bajo"),
    ("CDiag2",5): (32,  "Inyector 2 voltaje alto"),
    ("CDiag2",6): (24,  "Bobina 2 voltaje bajo"),
    ("CDiag2",7): (24,  "Bobina 2 voltaje alto"),
    ("CDiag3",0): (56,  "Sync failure"),
    ("CDiag3",1): (55,  "ECM ADC error"),
    ("CDiag3",2): (54,  "ECM EEPROM error"),
    ("CDiag3",3): (53,  "ECM Flash checksum error"),
    ("CDiag3",4): (52,  "ECM RAM failure"),
    ("CDiag3",5): (36,  "Ventilador 1 voltaje alto"),
    ("CDiag3",6): (44,  "BAS voltaje bajo"),
    ("CDiag3",7): (44,  "BAS voltaje alto"),
    ("CDiag4",0): (21,  "AMC siempre abierto"),
    ("CDiag4",1): (21,  "AMC siempre cerrado"),
    ("CDiag4",2): (21,  "AMC corto a tierra"),
    ("CDiag4",3): (21,  "AMC corto a alimentación"),
    ("CDiag4",4): (0,   "AIC failure"),
    ("CDiag4",5): (0,   "Caballete siempre bajo"),
    ("CDiag4",6): (0,   "Caballete siempre alto"),
    ("CDiag4",7): (0,   "Caballete failure"),
}
# HDiag0-4 tienen los mismos bits que CDiag0-4 pero son históricos
# Los usamos para detectar errores que ya no están activos pero ocurrieron
HDIAG_NAMES = ["HDiag0","HDiag1","HDiag2","HDiag3","HDiag4"]

def decode_rt_packet(raw_bytes):
    if len(raw_bytes)<RT_RESPONSE_SIZE: return None
    if raw_bytes[0]!=SOH or raw_bytes[4]!=EOH or raw_bytes[5]!=SOT: return None
    if raw_bytes[6]!=ACK or raw_bytes[-2]!=EOT: return None
    cs=0
    for b in raw_bytes[1:-1]: cs ^= b
    if (cs&0xFF)!=raw_bytes[-1]: return None
    result={}
    for name,(offset,nbytes,scale,val_offset) in RT_VARIABLES.items():
        if offset+nbytes>len(raw_bytes): result[name]=None; continue
        raw=struct.unpack_from('<H',raw_bytes,offset)[0] if nbytes==2 else raw_bytes[offset]
        result[name]=round(raw*scale+val_offset,4)

    # ── Flags decodificados como columnas nombradas ──────────────
    f1   = int(result.get('Flags1',0) or 0)
    f2   = int(result.get('Flags2',0) or 0)
    f3   = int(result.get('Flags3',0) or 0)
    f4   = int(result.get('Flags4',0) or 0)
    f6   = int(result.get('Flags6',0) or 0)
    dout = int(result.get('DOut',0)   or 0)
    din  = int(result.get('DIn',0)    or 0)
    # Flags1
    result['fl_engine_run']  = (f1>>0)&1
    result['fl_o2_active']   = (f1>>1)&1
    result['fl_accel']       = (f1>>2)&1
    result['fl_decel']       = (f1>>3)&1
    result['fl_engine_stop'] = (f1>>4)&1
    result['fl_wot']         = (f1>>5)&1
    result['fl_ignition']    = (f1>>7)&1
    # Flags2
    result['fl_closed_loop'] = (f2>>7)&1
    result['fl_rich']        = (f2>>6)&1
    result['fl_learn']       = (f2>>4)&1
    # Flags3
    result['fl_cam_active']  = (f3>>3)&1
    result['fl_kill']        = (f3>>4)&1  # Engine Kill (Flags3 bit 4)
    result['fl_immob']       = (f3>>5)&1
    # Flags4
    result['fl_fuel_cut']    = (f4>>4)&1
    # Flags6
    result['fl_hot']         = (f6>>3)&1  # Hot Condition
    # DOut bits (offset 84)
    result['do_coil1']       = (dout>>0)&1
    result['do_coil2']       = (dout>>1)&1
    result['do_inj1']        = (dout>>2)&1
    result['do_inj2']        = (dout>>3)&1
    result['do_fuel_pump']   = (dout>>4)&1
    result['do_tacho']       = (dout>>5)&1
    result['do_cel']         = (dout>>6)&1  # Check Engine Light
    result['do_fan']         = (dout>>7)&1
    # DIn bits (offset 85)
    result['di_cam']         = (din>>0)&1
    result['di_tacho_fb']    = (din>>1)&1
    result['di_vss']         = (din>>2)&1
    # bit 3 = Front Wheel Speed — sensor no instalado en XB12X stock
    # (si se instala algún día: di_fws vs di_vss para detección de wheelspin)
    result['di_clutch']      = (din>>4)&1
    result['di_neutral']     = (din>>5)&1
    result['di_crank']       = (din>>7)&1

    # ── TPS calibrado con valores reales de la moto ──────────────
    # Escala ATPS_V: TPS_10Bit × 0.004887585 = voltaje real
    # 0.66V = 0° verdadero (tope físico sin tornillo de ajuste)
    # 4.54V = 85° WOT mecánico → rango = 3.88V
    tps10   = result.get('TPS_10Bit') or 0
    tps_v   = round(tps10 * 0.004887585, 3)
    tps_pct = round(max(0.0, min(100.0, (tps_v - 0.66) / 3.88 * 100)), 1)
    result['TPS_V']   = tps_v
    result['TPS_pct'] = tps_pct

    # VS_KPH — velocidad calculada con factor configurable
    vss = result.get('VSS_Count') or 0
    if vss > 0 and VSS_CPKM25 > 0:
        result['VS_KPH'] = round((vss / 0.039) * 3600 / (VSS_CPKM25 / 25 * 1000), 1)
    else:
        result['VS_KPH'] = 0.0

    # Gear — estimación por ratio VS_KPH/RPM (XB12X 5 velocidades)
    rpm_k = (result.get('RPM') or 0) / 1000.0
    kph   = result['VS_KPH']
    if rpm_k > 0.5 and kph > 3.0:
        ratio = kph / rpm_k
        gear = 1
        for thr in GEAR_THRESHOLDS:
            if ratio > thr:
                gear += 1
            else:
                break
        result['Gear'] = gear
    else:
        result['Gear'] = 0  # neutro / desconocido

    return result

# ─────────────────────────────────────────────────────────────────
# CELL TRACKER — mapa VE: segundos + EGO por celda
# ─────────────────────────────────────────────────────────────────
RPM_BINS  = [0,800,1000,1350,1900,2400,2900,3400,4000,5000,6000,7000,8000]
LOAD_BINS = [10,15,20,30,40,50,60,80,100,125,175,255]

def find_bin(val, bins):
    """Retorna el bin inferior más cercano."""
    best = bins[0]
    for b in bins:
        if val >= b: best = b
        else: break
    return best

def cell_key(rpm, load):
    return f"{find_bin(rpm, RPM_BINS)}_{find_bin(load, LOAD_BINS)}"

class CellTracker:
    """Acumula tiempo y EGO promedio por celda del mapa VE 13×12."""

    def __init__(self):
        self.cells  = {}   # key → {seconds, ego_sum, count}
        self.active = None
        self._lock  = threading.Lock()
        self._dt    = 1.0 / 8.0   # 8Hz → 0.125s por muestra

    def reset(self):
        with self._lock:
            self.cells  = {}
            self.active = None

    def update(self, data):
        rpm  = data.get("RPM",  0) or 0
        load = data.get("Load", 0) or 0
        ego  = data.get("EGO_Corr", 100) or 100
        if rpm < 300:
            with self._lock:
                self.active = None
            return
        key = cell_key(rpm, load)
        with self._lock:
            self.active = key
            c = self.cells.setdefault(key, {"seconds":0.0,"ego_sum":0.0,"count":0})
            c["seconds"]  += self._dt
            c["ego_sum"]  += ego
            c["count"]    += 1

    def snapshot(self):
        """Retorna copia thread-safe del estado."""
        with self._lock:
            snap_cells = {}
            for k,v in self.cells.items():
                avg = round(v["ego_sum"]/v["count"],1) if v["count"] else 100.0
                snap_cells[k] = {"seconds":round(v["seconds"],1),"ego_avg":avg}
            return snap_cells, self.active

# ─────────────────────────────────────────────────────────────────
# LIVE DASHBOARD — HTTP :8080
# ─────────────────────────────────────────────────────────────────

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Buell XB12X</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.4.1/papaparse.min.js"></script>
<style>
:root{
  --bg:#0a0a0b;--panel:#111114;--border:#1e1e24;
  --accent:#e8420a;--accent2:#f5a623;--green:#2cdd6e;
  --blue:#3d9eff;--dim:#55555e;--text:#c8c8cc;
  --red:#ff4444;--mono:'Share Tech Mono',monospace;
}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--text);font-family:'Barlow Condensed',sans-serif;
     font-size:14px;height:100dvh;display:flex;flex-direction:column;overflow:hidden}

/* HEADER */
.hdr{background:var(--panel);border-bottom:2px solid var(--accent);
     padding:6px 10px;display:flex;align-items:center;gap:8px;flex-shrink:0}
.hdr-stats{display:flex;gap:0;flex:1;overflow:hidden}
.hs{display:flex;flex-direction:column;align-items:center;padding:2px 8px;
    border-right:1px solid var(--border);min-width:50px}
.hs:last-child{border-right:none}
.hs-label{font-family:var(--mono);font-size:7px;color:var(--dim);letter-spacing:.12em;text-transform:uppercase}
.hs-val{font-size:22px;font-weight:900;line-height:1.1}
.ac{color:var(--accent)} .gn{color:var(--green)} .bl{color:var(--blue)}
.wh{color:#fff}          .yw{color:var(--accent2)}
.pill{padding:3px 7px;font-family:var(--mono);font-size:8px;border:1px solid;
      letter-spacing:.1em;text-transform:uppercase;flex-shrink:0}
.pill.on{color:var(--green);border-color:var(--green)}
.pill.off{color:var(--dim);border-color:var(--border)}
.pill.yw{color:var(--accent2);border-color:var(--accent2)}
.pill-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;display:inline-block}
.pill-dot.on{background:var(--green);animation:blink 1.4s ease-in-out infinite}
.pill-dot.yw{background:var(--accent2);animation:blink 2.2s ease-in-out infinite}
.pill-dot.off{background:#333}
.rdot{width:5px;height:5px;border-radius:50%;background:var(--green);
      display:inline-block;animation:blink 2s infinite;flex-shrink:0}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.15}}

/* TABS */
.tabs{display:flex;background:var(--panel);border-bottom:1px solid var(--border);flex-shrink:0}
.tab{flex:1;padding:8px 2px;text-align:center;font-family:var(--mono);font-size:8px;
     letter-spacing:.06em;text-transform:uppercase;color:var(--dim);cursor:pointer;
     border-bottom:2px solid transparent;transition:all .15s}
.tab.active{color:#fff;border-bottom-color:var(--accent)}

/* CONTENT */
.content{flex:1;overflow-y:auto;overflow-x:hidden}
.pane{display:none;padding:8px}
.pane.active{display:block}

/* BIG DISPLAY */
.big-display{display:flex;gap:8px;margin-bottom:8px}
.big-card{flex:1;background:var(--panel);border:1px solid var(--border);
          padding:8px 10px;display:flex;flex-direction:column;align-items:center;
          border-top:2px solid var(--border)}
.big-card.hot{border-top-color:var(--accent)}
.big-card.tps{border-top-color:var(--blue)}
.big-label{font-family:var(--mono);font-size:8px;color:var(--dim);
           letter-spacing:.15em;text-transform:uppercase;margin-bottom:2px}
.big-num{font-size:56px;font-weight:900;line-height:1;letter-spacing:-.02em}
.big-unit{font-family:var(--mono);font-size:10px;color:var(--dim);margin-top:2px}

/* INDICADORES */
.ind-row{display:flex;gap:6px;margin-bottom:8px}
.ind{flex:1;background:var(--panel);padding:6px 8px;display:flex;align-items:center;
     gap:6px;border:1px solid var(--border)}
.dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.dot.ok{background:var(--green)}.dot.warn{background:var(--accent2)}.dot.bad{background:var(--red)}
.ind-text{font-size:11px;line-height:1.3}
.ind-val{font-family:var(--mono);font-weight:700;color:#fff}

/* OBJETIVOS — una línea */
.obj-row-compact{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
.obj-chip{display:flex;flex-direction:column;flex:1;min-width:80px;
          background:var(--panel);border:1px solid var(--border);
          border-left:3px solid var(--dim);padding:5px 8px;border-radius:0 3px 3px 0}
.obj-chip.done{border-left-color:var(--green)}
.obj-chip.partial{border-left-color:var(--accent2)}
.obj-chip-label{font-family:var(--mono);font-size:7px;color:var(--dim);
                text-transform:uppercase;letter-spacing:.08em;margin-bottom:2px;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.obj-chip-pct{font-size:20px;font-weight:900;font-family:var(--mono);color:#fff}
.obj-chip-sub{font-family:var(--mono);font-size:7px;color:var(--dim);margin-top:1px}
.obj-bar{height:2px;background:rgba(255,255,255,.08);border-radius:1px;margin-top:3px}
.obj-fill{height:2px;border-radius:1px;background:var(--accent2);transition:width .5s}
.obj-fill.done{background:var(--green)}

/* VE GRID */
.grid-section{margin-bottom:4px}
.grid-label{font-family:var(--mono);font-size:8px;color:var(--dim);letter-spacing:.15em;
             text-transform:uppercase;margin-bottom:6px}
.grid-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;padding-bottom:4px}
table.veg{border-collapse:collapse;font-family:var(--mono);white-space:nowrap}
table.veg th{font-size:7px;color:var(--dim);padding:2px 3px;text-align:center;font-weight:400;min-width:28px}
table.veg th.rh{text-align:right;min-width:26px;padding-right:4px}
table.veg td{width:32px;height:28px;border:1px solid rgba(255,255,255,.04);
             text-align:center;vertical-align:middle;cursor:pointer;position:relative}
table.veg td:active{filter:brightness(1.6)}
.cv{font-size:8px;font-weight:700;line-height:1}
.c0{background:#141417}.c1{background:#2a1f08}.c2{background:#3a3000}
.c3{background:#0f2e0f}.c4{background:#0a420a}
.ca{background:#3d0800 !important;animation:pulse .7s infinite alternate}
@keyframes pulse{from{filter:brightness(1)}to{filter:brightness(2.2)}}

/* LEYENDA */
.legend{display:flex;gap:8px;margin-top:6px;flex-wrap:wrap}
.leg{display:flex;align-items:center;gap:4px;font-family:var(--mono);font-size:8px;color:var(--dim)}
.leg-dot{width:10px;height:10px;flex-shrink:0}

/* CONFIG */
.cfg-section{margin-bottom:14px}
.cfg-title{font-family:var(--mono);font-size:8px;color:var(--dim);letter-spacing:.15em;
           text-transform:uppercase;margin-bottom:8px;padding-bottom:4px;
           border-bottom:1px solid var(--border)}
.cfg-textarea{width:100%;background:#0a0a0b;border:1px solid var(--border);
              color:var(--text);font-family:var(--mono);font-size:10px;
              padding:8px;resize:vertical;height:160px;border-radius:2px}
.btn{display:inline-block;padding:6px 16px;background:transparent;
     border:1px solid var(--border);color:var(--dim);font-family:var(--mono);
     font-size:9px;cursor:pointer;text-transform:uppercase;letter-spacing:.1em;border-radius:2px}
.btn:active{opacity:.7}
.btn.p{border-color:var(--accent);color:var(--accent)}
.btn.g{border-color:var(--green);color:var(--green)}
.msq-drop{border:2px dashed var(--border);padding:16px;text-align:center;cursor:pointer;
          font-family:var(--mono);font-size:9px;color:var(--dim);letter-spacing:.1em;border-radius:2px}
.msq-drop.loaded{border-color:var(--green);color:var(--green)}
.status-row{display:flex;align-items:center;gap:8px;padding:6px 0;
            font-family:var(--mono);font-size:9px;color:var(--dim)}

/* RIDES */
.ride-item{background:var(--panel);border:1px solid var(--border);padding:8px 10px;
           display:flex;justify-content:space-between;align-items:center;
           margin-bottom:4px;transition:all .15s;cursor:pointer}
.ride-item.selected{border-color:var(--accent2);background:rgba(245,166,35,.06)}
.ride-item.disabled{opacity:.4;cursor:default}
.ride-name{font-family:var(--mono);font-size:11px;color:#fff;font-weight:700}
.ride-meta{font-family:var(--mono);font-size:9px;color:var(--dim);margin-top:2px}
.ride-check{width:16px;height:16px;border:1px solid var(--border);border-radius:2px;
            display:flex;align-items:center;justify-content:center;font-size:10px;flex-shrink:0}
.ride-item.selected .ride-check{border-color:var(--accent2);color:var(--accent2);background:rgba(245,166,35,.12)}

/* RED / SISTEMA */
.net-row{display:flex;gap:8px;margin-bottom:8px}
.btn-net{flex:1;padding:10px 4px;border:1px solid var(--border);background:var(--panel);
         color:var(--dim);font-family:var(--mono);font-size:9px;cursor:pointer;
         text-transform:uppercase;text-align:center;transition:all .2s}
.btn-net.on{border-color:var(--green);color:var(--green);background:rgba(44,221,110,.07)}
.btn-net:active{opacity:.6}
.btn-danger{width:100%;padding:12px;background:transparent;border:1px solid var(--red);
            color:var(--red);font-family:var(--mono);font-size:10px;cursor:pointer;
            text-transform:uppercase;margin-top:6px;letter-spacing:.1em}
.btn-danger:active{background:rgba(255,68,68,.12)}
.net-status{font-family:var(--mono);font-size:9px;padding:4px 0 8px;color:var(--dim);
            display:flex;align-items:center;gap:6px}

/* GRÁFICAS */
.chart-wrap{background:var(--panel);border:1px solid var(--border);
            padding:8px;margin-bottom:8px;border-radius:2px}
.chart-title{font-family:var(--mono);font-size:8px;color:var(--dim);letter-spacing:.12em;
             text-transform:uppercase;margin-bottom:6px}
.chart-wrap canvas{width:100%!important;max-height:130px;height:130px}
.gauge-row{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.gauge{flex:1;min-width:70px;background:var(--panel);border:1px solid var(--border);
       padding:6px 8px;text-align:center;border-top:2px solid var(--border)}
.gauge-label{font-family:var(--mono);font-size:7px;color:var(--dim);text-transform:uppercase;letter-spacing:.1em}
.gauge-value{font-size:22px;font-weight:900;color:#fff;line-height:1.1}
.gauge-unit{font-family:var(--mono);font-size:8px;color:var(--dim)}
.chart-controls{display:flex;gap:6px;align-items:center;margin-bottom:8px;flex-wrap:wrap}
.range-wrap{flex:1;display:flex;align-items:center;gap:4px;font-family:var(--mono);font-size:9px;color:var(--dim)}
.range-wrap input{flex:1;accent-color:var(--accent)}
.graph-warn{font-family:var(--mono);font-size:10px;color:var(--dim);
            padding:30px;text-align:center}

/* VE placeholder */
.coming-soon{display:flex;flex-direction:column;align-items:center;justify-content:center;
             min-height:200px;gap:12px;color:var(--dim);text-align:center}
.coming-soon p{font-family:var(--mono);font-size:10px;letter-spacing:.1em;line-height:1.8}

/* BOTTOM SHEET */
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100}
.overlay.open{display:flex;align-items:flex-end}
.overlay-close{position:absolute;top:12px;right:16px;font-size:24px;color:#fff;cursor:pointer;z-index:101;padding:8px;}
.sheet{background:#18181c;border-top:2px solid var(--accent);padding:16px;
       width:100%;max-height:60vh;overflow-y:auto}
.sheet-title{font-size:14px;font-weight:700;color:#fff;margin-bottom:12px;
             display:flex;justify-content:space-between;align-items:center}
.sheet-close{font-size:20px;color:var(--dim);cursor:pointer;padding:4px}
.sheet-row{display:flex;justify-content:space-between;padding:5px 0;
           border-bottom:1px solid var(--border);font-family:var(--mono);font-size:11px}
.sheet-key{color:var(--dim)}.sheet-val{color:#fff;font-weight:700}
</style>
</head>
<body>

<!-- HEADER -->
<div class="hdr">
  <div class="hdr-stats">
    <div class="hs"><div class="hs-label">EGO</div><div class="hs-val gn" id="hEGO">--</div></div>
    <div class="hs"><div class="hs-label">MAT</div><div class="hs-val bl" id="hMAT">--</div></div>
    <div class="hs"><div class="hs-label">Batt</div><div class="hs-val yw" id="hBatt">--</div></div>
    <div class="hs"><div class="hs-label">ERR</div><div class="hs-val gn" id="hErr" title="Eventos de error del ride actual (dirty+timeout)">0</div></div>
    <div class="hs"><div class="hs-label">Marcha</div><div class="hs-val" id="hGear" style="color:#a8f">--</div></div>
    <div class="hs"><div class="hs-label" id="hRideLabel">Ride</div><div class="hs-val wh" id="hRide">--</div></div>
  </div>
  <div id="hPill" class="pill-dot off"></div>
  <button id="btnCloseRide" onclick="closeRide()"
    style="display:none;margin-left:8px;padding:4px 12px;background:#c0392b;color:#fff;border:none;border-radius:6px;font-size:0.85rem;cursor:pointer;">
    ⏹ CERRAR RIDE
  </button>
  <span class="rdot"></span>
</div>
<div id="ecuLostBanner" style="display:none;pointer-events:none;background:#c0392b;color:#fff;text-align:center;
  padding:8px;font-size:0.9rem;font-weight:bold;letter-spacing:1px;">
  ⚠️ ECU SIN RESPUESTA — <span id="ecuLostSecs">0</span>s —
  <span onclick="doReconnect()" style="cursor:pointer;text-decoration:underline;pointer-events:auto">RECONECTAR</span>
</div>

<!-- TABS -->
<div class="tabs">
  <div class="tab active" onclick="showTab('ride');trackUsage('tab_ride')">Ride</div>
  <div class="tab" onclick="showTab('rides');trackUsage('tab_sesiones')">Sesiones</div>
  <div class="tab" onclick="showTab('graph');trackUsage('tab_graph')">Graf</div>
  <div class="tab" onclick="showTab('ve');trackUsage('tab_ve');if(!_mapsData)loadMaps()">VE</div>
  <div class="tab" onclick="showTab('cfg');trackUsage('tab_config');loadUsageStats()">Config</div>
  <div class="tab" onclick="showTab('net');loadNetPane();trackUsage('tab_redes')">Redes</div>
</div>

<!-- PANE RIDE -->
<div class="pane active content" id="pane-ride">
  <div class="big-display">
    <div class="big-card hot">
      <div class="big-label">CHT</div>
      <div class="big-num ac" id="bigCHT">--</div>
      <div class="big-unit">grados C</div>
    </div>
    <div class="big-card" style="border-top-color:#2ecc71">
      <div class="big-label">KPH</div>
      <div class="big-num" style="color:#2ecc71" id="bigKPH">--</div>
      <div class="big-unit">km/h</div>
    </div>
    <div class="big-card tps">
      <div class="big-label">TPS</div>
      <div class="big-num bl" id="bigTPS">--%</div>
      <div class="big-unit">apertura</div>
      <div style="font-family:var(--mono);font-size:14px;color:var(--dim);margin-top:4px">
        <span id="bigTPSPct" style="color:var(--blue);font-weight:700">--°</span>
        <span style="font-size:9px">grados</span>
      </div>
    </div>
  </div>

  <div class="ind-row" id="indicators"></div>

  <div class="grid-section">
    <div class="grid-label">Cobertura de celdas VE</div>
    <div class="grid-wrap">
      <table class="veg" id="veGrid"></table>
    </div>
    <div class="legend">
      <div class="leg"><div class="leg-dot c0"></div>Sin datos</div>
      <div class="leg"><div class="leg-dot c1"></div>&lt;2s</div>
      <div class="leg"><div class="leg-dot c2"></div>2-5s</div>
      <div class="leg"><div class="leg-dot c3"></div>5-10s</div>
      <div class="leg"><div class="leg-dot c4"></div>&gt;10s</div>
      <div class="leg"><div class="leg-dot ca"></div>Activa</div>
    </div>
  </div>

  <div class="obj-row-compact" id="objList"></div>
</div>

<!-- PANE RIDES -->
<div class="pane content" id="pane-rides">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div class="cfg-title" style="margin:0;border:none;padding:0">Sesiones</div>
    <button class="btn" onclick="loadSessions()">Actualizar</button>
  </div>
  <!-- Banner ride activo — aparece solo cuando hay ride en curso -->
  <div id="liveRideBanner" style="display:none;background:rgba(44,221,110,.08);
       border:1px solid var(--green);border-radius:4px;padding:8px 10px;margin-bottom:10px;
       font-family:var(--mono);font-size:9px;color:var(--green)">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span>● RIDE ACTIVO — <span id="liveRideNum">---</span></span>
      <button class="btn" style="font-size:9px;padding:3px 8px;color:var(--green);
              border-color:var(--green)" onclick="openLiveRideGraph()">Ver Graf</button>
    </div>
    <div style="color:var(--dim);font-size:8px;margin-top:3px">Los rides anteriores están disponibles abajo</div>
  </div>
  <div id="ridesList">
    <div style="font-family:var(--mono);font-size:10px;color:var(--dim);padding:20px;text-align:center">Cargando...</div>
  </div>
</div>

<!-- Modal nota de ride -->
<div id="noteModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;
     background:rgba(0,0,0,0.7);z-index:9999;align-items:center;justify-content:center">
  <div style="background:#1a1a1a;border:1px solid var(--border);padding:16px;width:90%;max-width:360px;border-radius:4px">
    <div style="font-family:var(--mono);font-size:9px;color:var(--dim);letter-spacing:.1em;margin-bottom:8px" id="noteModalTitle">NOTA DEL RIDE</div>
    <textarea id="noteText" style="width:100%;height:100px;background:#111;border:1px solid var(--border);
              color:#fff;font-family:var(--mono);font-size:11px;padding:8px;resize:vertical;box-sizing:border-box"
              placeholder="Escribe tus notas aquí..."></textarea>
    <div style="display:flex;gap:8px;margin-top:8px">
      <button class="btn g" style="flex:1" onclick="saveNote()">Guardar</button>
      <button class="btn" style="flex:1" onclick="closeNoteModal()">Cerrar</button>
    </div>
    <div id="noteStatus" style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-top:6px;min-height:12px"></div>
  </div>
</div>


<!-- PANE GRAPH -->
<div class="pane content" id="pane-graph">
  <div class="chart-controls" style="display:none">
    <select id="graphRideSelect" style="flex:1;background:var(--bg);border:1px solid var(--border);
            color:#fff;font-family:var(--mono);font-size:10px;padding:6px 8px">
      <option value="">-- Selecciona un ride --</option>
    </select>
    <button class="btn p" onclick="loadGraphRide()">&#9654; Ver</button>
  </div>
  <!-- Título del ride graficado — visible siempre arriba -->
  <div id="graphRideTitle" style="font-family:var(--mono);font-size:11px;color:#7df;
       font-weight:700;letter-spacing:.08em;padding:6px 0 2px;
       border-bottom:1px solid rgba(125,223,255,0.2);margin-bottom:6px;display:none"></div>
  <div id="graphStatus" style="font-family:var(--mono);font-size:9px;color:var(--dim);
       margin-bottom:6px;min-height:14px"></div>

  <!-- Leyenda de marcadores -->
  <div id="graphLegend" style="display:none;font-family:var(--mono);font-size:8px;
       color:var(--dim);margin-bottom:8px;display:flex;gap:10px;flex-wrap:wrap">
    <span><span style="color:#f80">●</span> fl_hot</span>
    <span><span style="color:#f44">●</span> fl_kill</span>
    <span><span style="color:#ff0">▲</span> DTC nuevo</span>
    <span><span style="color:#8af">●</span> do_cel</span>
    <span><span style="color:#0f8">●</span> WOT&gt;80%</span>
    <span><span style="color:#a8f">●</span> Cambio marcha</span>
  </div>

  <!-- Chart 1: RPM + KPH + CLT triple eje -->
  <div class="chart-wrap">
    <div class="chart-title">RPM · VELOCIDAD · TEMPERATURA</div>
    <canvas id="chartRPM" height="120"></canvas>
  </div>
  <!-- Chart 2: EGO + AFV + WUE + promedio -->
  <div class="chart-wrap">
    <div class="chart-title">CORRECCIONES COMBUSTIBLE — EGO · AFV · WUE · PROMEDIO</div>
    <canvas id="chartFuel" height="100"></canvas>
  </div>
  <!-- Chart 3: TPS solo -->
  <div class="chart-wrap">
    <div class="chart-title">TPS %</div>
    <canvas id="chartTPS" height="85"></canvas>
  </div>
  <!-- Chart 4: Spark + Pulse Width doble eje -->
  <div class="chart-wrap">
    <div class="chart-title">ENCENDIDO (°) · PULSO INYECTOR (ms)</div>
    <canvas id="chartSPK" height="95"></canvas>
  </div>
  <!-- Chart 5: Batt V -->
  <div class="chart-wrap">
    <div class="chart-title">VOLTAJE BATERÍA (V)</div>
    <canvas id="chartBatt" height="70"></canvas>
  </div>
</div>

<!-- PANE VE -->
<div class="pane content" id="pane-ve">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div class="cfg-title" style="margin:0;border:none;padding:0">Mapas EEPROM</div>
    <button class="btn" onclick="loadMaps()">&#8635; Recargar</button>
  </div>
  <div id="veMapStatus" style="font-family:var(--mono);font-size:9px;color:var(--dim);
       margin-bottom:8px;min-height:12px">Conecta la ECU para cargar los mapas</div>

  <!-- Selector de mapa -->
  <div style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap">
    <button class="btn" id="mapBtnFuelF" onclick="showMap('fuel_front')" style="font-size:9px;padding:4px 8px">Fuel Front</button>
    <button class="btn" id="mapBtnFuelR" onclick="showMap('fuel_rear')"  style="font-size:9px;padding:4px 8px">Fuel Rear</button>
    <button class="btn" id="mapBtnSpkF" onclick="showMap('spark_front')" style="font-size:9px;padding:4px 8px">Spark Front</button>
    <button class="btn" id="mapBtnSpkR" onclick="showMap('spark_rear')"  style="font-size:9px;padding:4px 8px">Spark Rear</button>
  </div>

  <!-- Tabla del mapa -->
  <div id="mapContainer" style="overflow-x:auto">
    <div style="font-family:var(--mono);font-size:9px;color:var(--dim);text-align:center;padding:20px">
      Conecta la ECU · los mapas se leen del EEPROM al arrancar
    </div>
  </div>

  <!-- Leyenda -->
  <div id="mapLegend" style="display:none;margin-top:10px;font-family:var(--mono);font-size:8px;color:var(--dim)">
    <span style="display:inline-block;width:12px;height:12px;background:#1a3a6a;margin-right:4px;vertical-align:middle"></span>bajo ·
    <span style="display:inline-block;width:12px;height:12px;background:#c85000;margin-right:4px;margin-left:8px;vertical-align:middle"></span>alto ·
    Eje X = RPM · Eje Y = TPS (Load)
  </div>
</div>

<!-- PANE CONFIG -->
<div class="pane content" id="pane-cfg">
  <div class="cfg-section" style="border-bottom:1px solid var(--border);padding-bottom:10px;margin-bottom:10px">
    <div style="font-family:var(--mono);font-size:9px;color:var(--dim);letter-spacing:.1em">LOGGER VERSION</div>
    <div style="font-family:var(--mono);font-size:14px;color:#7df;margin-top:4px;font-weight:bold" id="cfgVersion">--</div>
    <div style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-top:2px">Buell XB12X DDFI2 · Pi Zero 2W · FT232RL</div>
  </div>
  
  <!-- BOTÓN DE DESCARGA DEL LOGGER -->
  <div class="cfg-section">
    <div class="cfg-title">Actualizar Logger</div>
    <div style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-bottom:8px;line-height:1.8">
      Descarga la última versión desde GitHub.<br>
      Reemplaza manualmente en /home/pi/buell/
    </div>
    <a href="https://raw.githubusercontent.com/pacdavid1/buell-xb12x-logger/main/ddfi2_logger.py" 
       download="ddfi2_logger.py" 
       style="display:inline-block;padding:8px 16px;background:#e94560;color:#fff;text-decoration:none;border-radius:4px;font-family:var(--mono);font-size:10px;font-weight:600">
      ⬇ Descargar ddfi2_logger.py
    </a>
    <div style="margin-top:12px">
      <button class="btn g" onclick="gitPull()" style="width:100%; padding:10px;">🔄 Git Pull (actualizar desde GitHub)</button>
      <div id="gitPullStatus" style="font-family:var(--mono); font-size:9px; color:var(--dim); margin-top:6px; text-align:center;"></div>
    </div>
  </div>

  <div class="cfg-section">
    <div class="cfg-title">Estado ECU</div>
    <div class="status-row">
      <span class="rdot"></span>
      <span id="cfgRide">Sin datos -- esperando conexion</span>
    </div>
    <div class="status-row" id="cfgVeStatus" style="color:var(--dim)">Mapa VE: no cargado</div>
  </div>

  <div class="cfg-section">
    <div class="cfg-title">Mapa VE (opcional)</div>
    <div class="msq-drop" id="msqDrop"
         onclick="document.getElementById('msqInput').click()"
         ondragover="event.preventDefault()"
         ondrop="handleMsqDrop(event)">
      Subir .msq -- si no hay EEPROM disponible
    </div>
    <input type="file" id="msqInput" accept=".msq,.xml" style="display:none"
           onchange="handleMsqFile(this.files[0])">
  </div>

  <div class="cfg-section">
    <div class="cfg-title">Objetivos del ride</div>
    <textarea class="cfg-textarea" id="objJson" placeholder="Cargando..."></textarea>
    <div style="display:flex;gap:8px;margin-top:6px">
      <button class="btn p" onclick="saveObj()">Guardar</button>
      <button class="btn" onclick="loadObj()">Recargar</button>
    </div>
  </div>

  <div class="cfg-section">
    <div class="cfg-title">Calibracion TPS</div>
    <div style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-bottom:8px;line-height:1.8">Motor apagado, llave ON:<br>Acelerador cerrado = MIN &nbsp; WOT = MAX</div>
    <div style="display:flex;gap:8px;margin-bottom:6px;align-items:center">
      <span style="font-family:var(--mono);font-size:9px;color:var(--dim);width:36px">MIN</span>
      <input type="number" id="tpsMin" value="" min="0" max="1023" placeholder="135" style="flex:1;background:var(--bg);border:1px solid var(--border);color:#fff;font-family:var(--mono);font-size:13px;padding:7px 8px">
    </div>
    <div style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
      <span style="font-family:var(--mono);font-size:9px;color:var(--dim);width:36px">MAX</span>
      <input type="number" id="tpsMax" value="" min="0" max="1023" placeholder="929" style="flex:1;background:var(--bg);border:1px solid var(--border);color:#fff;font-family:var(--mono);font-size:13px;padding:7px 8px">
    </div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <button class="btn g" onclick="saveTpsCal()">Guardar</button>
      <button class="btn" id="btnTpsCapture" onclick="startTpsCapture()"
        style="background:#8e44ad;flex:1;padding:7px 0">
        ⏺ Captura Auto (10s)
      </button>
    </div>
    <div id="tpsCaptureBar" style="display:none;margin-bottom:6px">
      <div style="font-family:var(--mono);font-size:8px;color:#a8f;margin-bottom:4px" id="tpsCaptureMsg">Mueve el acelerador de MIN a MAX...</div>
      <div style="background:#333;border-radius:3px;height:6px">
        <div id="tpsCaptureProgress" style="background:#8e44ad;height:6px;border-radius:3px;width:0%;transition:width 0.5s"></div>
      </div>
    </div>
    <span style="font-family:var(--mono);font-size:8px" id="tpsCalStatus"></span>
  </div>

  <div class="cfg-section">
    <div class="cfg-title">Calibracion Velocidad</div>
    <div style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-bottom:8px;line-height:1.8">Factor VSS (pulsos/25km):<br>Cambia si cambias de llanta o rueda</div>
    <div style="display:flex;gap:8px;margin-bottom:6px;align-items:center">
      <span style="font-family:var(--mono);font-size:9px;color:var(--dim);width:46px">CPKM25</span>
      <input type="number" id="vssFactorInput" value="" min="100" max="9999" placeholder="1368" style="flex:1;background:var(--bg);border:1px solid var(--border);color:#fff;font-family:var(--mono);font-size:13px;padding:7px 8px">
    </div>
    <div style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-bottom:8px">Calibrado a 50mph (80.5 kph) — ride_015</div>
    <div style="display:flex;align-items:center;gap:8px">
      <button class="btn g" onclick="saveVssCal()">Guardar</button>
      <span style="font-family:var(--mono);font-size:8px" id="vssCalStatus"></span>
    </div>
  </div>

  <div class="cfg-section">
    <div class="cfg-title">Sistema</div>
    <button class="btn g" style="width:100%;padding:10px;margin-bottom:8px" onclick="doKeepalive()">
      Mantener encendido (5 min)
    </button>
    <button class="btn p" style="width:100%;padding:10px;margin-bottom:8px" onclick="doReconnect()">
      &#x21BA; Forzar reconexión ECU
    </button>
    <div style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-bottom:8px">
      Reconexión completa: cierra puerto, espera 1s, reconecta, verifica ECU y relee EEPROM
    </div>
    <button class="btn" style="width:100%;padding:10px;margin-bottom:4px;background:#e67e22"
      onclick="if(confirm('¿Reiniciar el logger? El ride activo se guardará.')) doRestartLogger()">
      &#x1F504; Reiniciar Logger
    </button>
    <div style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-bottom:8px">
      Reinicia solo el proceso — vuelve a detectar la ECU automáticamente
    </div>
    <button class="btn-danger" style="margin-bottom:4px" onclick="doRebootPi()">&#x1F501; Reiniciar Pi</button>
    <button class="btn-danger" onclick="confirmShutdown()">Apagar Pi</button>
  </div>

  <div class="cfg-section">
    <div class="cfg-title">Uso de funciones</div>
    <div id="usageList" style="margin-bottom:8px">
      <div style="font-family:var(--mono);font-size:9px;color:var(--dim)">Cargando...</div>
    </div>
    <div style="display:flex;gap:6px">
      <a href="/usage_stats" download="usage_stats.json"
         style="flex:1;text-align:center;font-family:var(--mono);font-size:9px;color:var(--blue);
                text-decoration:none;border:1px solid var(--blue);padding:6px 0"
         onclick="trackUsage('btn_download_usage')">⬇ Descargar JSON</a>
      <button class="btn" style="flex:1;font-size:9px" onclick="clearUsageStats()">Limpiar</button>
    </div>
  </div>

  <div class="cfg-section">
    <div class="cfg-title" style="cursor:pointer" onclick="toggleEcu()">
      Config ECU
      <span id="ecuToggleIcon" style="font-size:10px;color:var(--dim)">&#9660;</span>
    </div>
    <div id="ecuPanel">
      <div style="font-family:var(--mono);font-size:9px;color:var(--dim);margin-bottom:8px">
        Leido de EEPROM al arrancar · <span id="ecuVersion" style="color:#8af">--</span>
      </div>
      <!-- Proteccion termica -->
      <div style="font-family:var(--mono);font-size:9px;color:var(--amber);margin:8px 0 4px">TEMPERATURA</div>
      <div id="ecuTempRows"></div>
      <!-- RPM limites -->
      <div style="font-family:var(--mono);font-size:9px;color:var(--amber);margin:8px 0 4px">RPM LIMITES</div>
      <div id="ecuRpmRows"></div>
      <!-- O2/EGO -->
      <div style="font-family:var(--mono);font-size:9px;color:var(--amber);margin:8px 0 4px">O2 / EGO</div>
      <div id="ecuEgoRows"></div>
      <div style="margin-top:8px">
        <button class="btn" style="font-size:9px;padding:5px 10px" onclick="loadEcu()">Refrescar</button>
      </div>
    </div>
  </div>
</div>

<div class="pane content" id="pane-net">
  <!-- Estado de red -->
  <div class="cfg-section">
    <div class="cfg-title">Red activa</div>
    <div class="net-status">
      <span class="rdot" id="netDot" style="animation:none"></span>
      <span id="netLabel">--</span>
    </div>
    <div class="net-row" style="margin-top:8px">
      <div class="btn-net" id="btnWifi" onclick="switchNet('wifi')">WiFi</div>
      <div class="btn-net" id="btnHotspot" onclick="switchNet('hotspot')">Hotspot</div>
    </div>
  </div>

  <!-- Redes guardadas -->
  <div class="cfg-section">
    <div class="cfg-title">Redes guardadas</div>
    <div id="savedList" style="margin-bottom:4px"></div>
  </div>

  <!-- Escanear -->
  <div class="cfg-section">
    <div class="cfg-title">Escanear redes</div>
    <button class="btn" style="width:100%;padding:10px;margin-bottom:8px"
            onclick="doWifiScan(event)">📶 Buscar redes</button>
    <div id="scanList"></div>
  </div>

  <!-- Agregar red nueva -->
  <div class="cfg-section">
    <div class="cfg-title">Agregar red nueva</div>
    <input id="newSsid" placeholder="Nombre de red (SSID)"
           style="width:100%;box-sizing:border-box;background:var(--bg);border:1px solid var(--border);
                  color:#fff;font-family:var(--mono);font-size:11px;padding:8px;margin-bottom:6px">
    <input id="newPass" type="password" placeholder="Contraseña"
           style="width:100%;box-sizing:border-box;background:var(--bg);border:1px solid var(--border);
                  color:#fff;font-family:var(--mono);font-size:11px;padding:8px;margin-bottom:8px">
    <button class="btn g" style="width:100%;padding:10px" onclick="doAddWifi()">
      Conectar y guardar
    </button>
  </div>
</div>

<!-- BOTTOM SHEET -->
<div class="overlay" id="overlay" onclick="closeSheet()">
  <span class="overlay-close" onclick="closeSheet()">✕</span>
  <div class="sheet" onclick="event.stopPropagation()">
    <div class="sheet-title">
      <span id="sheetTitle">Celda</span>
      <span class="sheet-close" onclick="closeSheet()">x</span>
    </div>
    <div id="sheetBody"></div>
  </div>
</div>

<script>
const RPM_BINS  = [0,800,1000,1350,1900,2400,2900,3400,4000,5000,6000,7000,8000];
const LOAD_BINS = [10,15,20,30,40,50,60,80,100,125,175,255];
let lastData = null;

// ── TABS ──────────────────────────────────────────────────────────
function showTab(id) {
  const ids = ['ride','rides','graph','ve','cfg'];
  document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', ids[i]===id));
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
  document.getElementById('pane-'+id).classList.add('active');
  if(id==='cfg')     { loadObj(); loadTpsCal(); loadVssCal(); loadEcu(); }
  if(id==='rides')   loadRidesList();
  if(id==='graph')   initGraphPane();
}

// ── GRID ──────────────────────────────────────────────────────────
function buildGrid() {
  const t = document.getElementById('veGrid');
  let html = '<thead><tr><th class="rh">L\\R</th>';
  for(const r of RPM_BINS)
    html += `<th>${r===0?'0':r>=1000?(r/1000)+'k':r}</th>`;
  html += '</tr></thead><tbody>';
  for(let li=LOAD_BINS.length-1; li>=0; li--) {
    html += `<tr><th class="rh">${LOAD_BINS[li]}</th>`;
    for(let ri=0; ri<RPM_BINS.length; ri++) {
      const key = `${RPM_BINS[ri]}_${LOAD_BINS[li]}`;
      html += `<td id="c_${key}" class="c0" onclick="openSheet('${key}',${ri},${li})">
        <div class="cv" id="s_${key}"></div></td>`;
    }
    html += '</tr>';
  }
  html += '</tbody>';
  t.innerHTML = html;
}

function updateGrid(cells, activeCell) {
  for(let li=0; li<LOAD_BINS.length; li++) {
    for(let ri=0; ri<RPM_BINS.length; ri++) {
      const key = `${RPM_BINS[ri]}_${LOAD_BINS[li]}`;
      const td  = document.getElementById(`c_${key}`);
      if(!td) continue;
      const secs = cells[key]?.seconds || 0;
      td.className = key===activeCell ? 'ca' :
                     secs<=0 ? 'c0' : secs<2  ? 'c1' :
                     secs<5  ? 'c2' : secs<10 ? 'c3' : 'c4';
      const sv = document.getElementById(`s_${key}`);
      sv.textContent = secs>0 ? (secs<10?secs.toFixed(1):Math.round(secs))+'s' : '';
    }
  }
}

// ── BOTTOM SHEET ──────────────────────────────────────────────────
function openSheet(key, ri, li) {
  const cell = lastData?.cells?.[key];
  document.getElementById('sheetTitle').textContent = `RPM ${RPM_BINS[ri]}  Load ${LOAD_BINS[li]}`;
  let rows = '';
  const add = (k,v) => rows += `<div class="sheet-row"><span class="sheet-key">${k}</span><span class="sheet-val">${v}</span></div>`;
  if(cell) {
    add('Tiempo', cell.seconds.toFixed(1)+' s');
    add('EGO promedio', cell.ego_avg.toFixed(1)+' %');
    const st = cell.ego_avg>106?'LEAN':cell.ego_avg<94?'RICH':'OK';
    add('Estado EGO', st);
  } else {
    add('Estado','Sin datos este ride');
  }
  document.getElementById('sheetBody').innerHTML = rows;
  document.getElementById('overlay').classList.add('open');
}
function closeSheet() { document.getElementById('overlay').classList.remove('open'); }

// ── HEADER ────────────────────────────────────────────────────────
function fmtTime(s){ return `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`; }

function updateHeader(d) {
  const lv = d.live || {};
  document.getElementById('hEGO').textContent  = lv.EGO_Corr != null ? lv.EGO_Corr.toFixed(0)+'%' : '--';
  document.getElementById('hMAT').textContent  = lv.MAT      != null ? lv.MAT.toFixed(0)+'`'        : '--';
  document.getElementById('hBatt').textContent = lv.Batt_V   != null ? lv.Batt_V.toFixed(1)+'V'     : '--';
  const errEl = document.getElementById('hErr');
  if(errEl){
    const re = d.ride_errors || {};
    const total = re.total || 0;
    const elapsedMin = (d.elapsed_s || 0) / 60;
    const errPerMin = (d.ride_active && elapsedMin > 0.1) ? (total / elapsedMin) : 0;
    errEl.textContent = d.ride_active ? total : '—';
    errEl.className   = 'hs-val ' + (errPerMin > 5 ? 'ac' : errPerMin > 2 ? 'yw' : 'gn');
    errEl.title = d.ride_active
      ? `Dirty: ${re.dirty||0}  Timeout: ${re.timeout||0}  Serial: ${re.serial||0}  (${errPerMin.toFixed(1)}/min)`
      : 'Sin ride activo';
  }
  const gearEl = document.getElementById('hGear');
  if(gearEl){
    const g = lv.Gear;
    gearEl.textContent = (g!=null && g>0) ? g+'ª' : (g===0 ? 'N' : '--');
  }
  // Ride: muestra numero + timer cuando está activo
  if(d.ride_active){
    document.getElementById('hRideLabel').textContent = 'R'+String(d.ride_num||0).padStart(3,'0');
    document.getElementById('hRide').textContent = fmtTime(d.elapsed_s||0);
  } else {
    document.getElementById('hRideLabel').textContent = 'Ride';
    document.getElementById('hRide').textContent = d.ride_num ? 'R'+String(d.ride_num).padStart(3,'0') : '--';
  }

  const pill = document.getElementById('hPill');
  if(d.ride_active)     { pill.textContent=''; pill.className='pill-dot on'; }
  else if(d.waiting)    { pill.textContent=''; pill.className='pill-dot yw'; }
  else                  { pill.textContent=''; pill.className='pill-dot off'; }

  // Botón cerrar ride
  const btnClose = document.getElementById('btnCloseRide');
  if(btnClose) btnClose.style.display = d.ride_active ? 'inline-block' : 'none';

  // EGO color
  const egoEl = document.getElementById('hEGO');
  if(lv.EGO_Corr != null)
    egoEl.className = 'hs-val '+(lv.EGO_Corr>106?'ac':lv.EGO_Corr<94?'bl':'gn');

  // Big CHT
  const bcht = document.getElementById('bigCHT');
  if(lv.CLT != null){
    bcht.textContent = lv.CLT.toFixed(0);
    bcht.className = 'big-num '+(lv.CLT>260?'ac':lv.CLT>220?'yw':'wh');
  } else { bcht.textContent='--'; bcht.className='big-num ac'; }

  // Big KPH
  const bkph = document.getElementById('bigKPH');
  if(bkph) bkph.textContent = lv.VS_KPH != null ? lv.VS_KPH.toFixed(0) : '--';

  // Big TPS — muestra % (ya calibrado en Python) y grados
  const tpsPct = lv.TPS_pct;
  const tpsDeg = lv.TPD;
  const bigTpsEl = document.getElementById('bigTPS');
  const bigTpsPctEl = document.getElementById('bigTPSPct');
  if(tpsPct != null){
    bigTpsEl.textContent = tpsPct.toFixed(0)+'%';
    bigTpsEl.style.color = tpsPct>80?'var(--accent)':tpsPct>50?'var(--accent2)':'var(--blue)';
    if(bigTpsPctEl) bigTpsPctEl.textContent = tpsDeg!=null ? tpsDeg.toFixed(1)+'°' : '';
  } else {
    bigTpsEl.textContent='--';
    if(bigTpsPctEl) bigTpsPctEl.textContent='';
  }

  // Config
  document.getElementById('cfgRide').textContent =
    d.ride_active ? `Ride R${d.ride_num} activo -- ${fmtTime(d.elapsed_s||0)}` : 'Standby -- esperando motor';
  if(d.ve_loaded)
    document.getElementById('cfgVeStatus').textContent = 'Mapa VE: cargado del EEPROM';
}

// ── OBJETIVOS compactos ───────────────────────────────────────────
function renderObjectives(objs) {
  const el = document.getElementById('objList');
  if(!objs?.length){ el.innerHTML=''; return; }
  el.innerHTML = objs.map(o => {
    const pct = Math.min(100, Math.round(o.pct));
    const cls = pct>=100?'done':pct>0?'partial':'';
    const shortLabel = o.label.replace('Zona ','').replace('Calentamiento ','Cal. ');
    return `<div class="obj-chip ${cls}">
      <div class="obj-chip-label">${shortLabel}</div>
      <div class="obj-chip-pct">${pct}%</div>
      <div class="obj-bar"><div class="obj-fill ${pct>=100?'done':''}" style="width:${pct}%"></div></div>
      <div class="obj-chip-sub">${o.done_cells}/${o.total_cells} &gt;=${o.target_s}s</div>
    </div>`;
  }).join('');
}

// ── INDICADORES ────────────────────────────────────────────────────
function renderIndicators(ind) {
  const el = document.getElementById('indicators');
  if(!ind || !Object.keys(ind).length){ el.innerHTML=''; return; }
  let html='';
  if(ind.max_cht){
    const cls=ind.max_cht.actual>260?'bad':ind.max_cht.actual>220?'warn':'ok';
    html+=`<div class="ind"><div class="dot ${cls}"></div>
      <div class="ind-text">CHT <span class="ind-val">${ind.max_cht.actual.toFixed(0)}</span>/${ind.max_cht.limit}</div></div>`;
  }
  if(ind.min_duration){
    html+=`<div class="ind"><div class="dot ${ind.min_duration.ok?'ok':'warn'}"></div>
      <div class="ind-text">Tiempo <span class="ind-val">${fmtTime(ind.min_duration.actual)}</span>/${fmtTime(ind.min_duration.limit)}</div></div>`;
  }
  el.innerHTML=html;
}

// ── FETCH LOOP ────────────────────────────────────────────────────
async function fetchLive() {
  if(window._viewingHistory) return;
  try {
    const r = await fetch('/live.json?t='+Date.now());
    if(!r.ok) return;
    const d = await r.json();
    lastData = d;
    updateHeader(d);
    updateGrid(d.cells||{}, d.active_cell);
    renderObjectives(d.objectives);
    renderIndicators(d.indicators);
    if(d.network_mode) updateNetStatus(d.network_mode);
    if(d.logger_version){ const el=document.getElementById('cfgVersion'); if(el) el.textContent=d.logger_version; }
    // Banner ECU desconectada
    const banner = document.getElementById('ecuLostBanner');
    if(banner){
      const lost = !d.ecu_connected && d.ride_active;
      banner.style.display = lost ? 'block' : 'none';
      banner.style.pointerEvents = lost ? 'auto' : 'none';
      if(lost) document.getElementById('ecuLostSecs').textContent = Math.round(d.ecu_lost_s||0);
    }
    // Banner ride activo en Sesiones
    const liveBanner = document.getElementById('liveRideBanner');
    if(liveBanner){
      liveBanner.style.display = d.ride_active ? 'block' : 'none';
      if(d.ride_active){
        const el = document.getElementById('liveRideNum');
        if(el) el.textContent = 'R'+String(d.ride_num||0).padStart(3,'0') + ' · ' + fmtTime(d.elapsed_s||0);
      }
    }
  } catch(e){}
}
setInterval(fetchLive, 2000);

// ── MAPAS EEPROM ──────────────────────────────────────────────────
let _mapsData = null;
let _activeMap = 'fuel_front';

async function loadMaps(){
  const status = document.getElementById('veMapStatus');
  if(status) status.textContent = 'Leyendo EEPROM...';
  try{
    const r = await fetch('/maps?t='+Date.now());
    if(!r.ok) throw new Error('HTTP '+r.status);
    _mapsData = await r.json();
    if(_mapsData && _mapsData.error){
      if(status) status.textContent = 'Error: '+_mapsData.error;
      return;
    }
    if(!_mapsData || !_mapsData.fuel_front){
      if(status) status.textContent = 'Sin mapas — conecta la ECU primero';
      return;
    }
    if(status) status.textContent = 'Mapas leídos del EEPROM ✓';
    document.getElementById('mapLegend').style.display='block';
    showMap(_activeMap);
  }catch(e){
    if(status) status.textContent = 'Error: '+e;
  }
}

function showMap(which){
  _activeMap = which;
  if(!_mapsData) return;
  const axes  = _mapsData.axes || {};
  const table = _mapsData[which];
  if(!table){ return; }

  // Ejes según tipo de mapa
  const isFuel  = which.startsWith('fuel');
  const unit    = isFuel ? '' : '°';
  const label   = {'fuel_front':'Fuel Front (VE)','fuel_rear':'Fuel Rear (VE)',
                   'spark_front':'Spark Advance Front (°)','spark_rear':'Spark Advance Rear (°)'}[which];
  const rawXAxis = isFuel ? (axes.fuel_rpm  || []) : (axes.spark_rpm  || []);
  const yAxis    = isFuel ? (axes.fuel_load || []) : (axes.spark_load || []);

  // ── Ordenar columnas: eje RPM guardado como período (μs/rev)
  //    Período > 0 → convertir a RPM real. Columnas con período=0 se descartan.
  //    Ordenar por período DESCENDENTE = RPM ASCENDENTE (izq=bajo, der=alto).
  const validColIdx = rawXAxis.map((v,i)=>i).filter(i=>rawXAxis[i]>0);
  validColIdx.sort((a,b)=>rawXAxis[b]-rawXAxis[a]);   // desc período = asc RPM
  const sortedRPM   = validColIdx.map(i=>Math.round(60000000/rawXAxis[i]));
  const sortedTable = table.map(row=>validColIdx.map(i=>row[i]));

  // Min/max para heatmap (ignorar ceros estructurales para escala de color)
  const allVals = sortedTable.flat().filter(v=>v>0);
  const vMin = allVals.length ? Math.min(...allVals) : 0;
  const vMax = allVals.length ? Math.max(...allVals) : 1;

  // Highlight botón activo
  ['FuelF','FuelR','SpkF','SpkR'].forEach(k=>{
    const btn = document.getElementById('mapBtn'+k);
    if(btn) btn.style.borderColor = '';
  });
  const btnMap = {'fuel_front':'FuelF','fuel_rear':'FuelR','spark_front':'SpkF','spark_rear':'SpkR'};
  const activeBtn = document.getElementById('mapBtn'+btnMap[which]);
  if(activeBtn) activeBtn.style.borderColor = 'var(--accent2)';

  // Construir tabla HTML
  const cellW = 40, cellH = 22;
  let html = `<div style="font-family:var(--mono);font-size:9px;color:#aaa;margin-bottom:6px">${label}</div>`;
  html += '<table style="border-collapse:collapse;font-family:monospace;font-size:9px">';

  // Header fila — RPM real
  html += '<tr><td style="padding:2px 4px;color:var(--dim);font-size:8px">TPS↓ RPM→</td>';
  for(const rpm of sortedRPM){
    const rpmLabel = rpm>=1000 ? (rpm/1000).toFixed(1)+'k' : rpm;
    html += `<td style="padding:2px 3px;color:var(--dim);font-size:8px;text-align:center;
             min-width:${cellW}px">${rpmLabel}</td>`;
  }
  html += '</tr>';

  // Filas — iterar de arriba hacia abajo (load alto arriba)
  const yReversed    = [...yAxis].reverse();
  const tableReversed= [...sortedTable].reverse();
  for(let ri=0; ri<tableReversed.length; ri++){
    const row     = tableReversed[ri];
    const loadVal = yReversed[ri] !== undefined ? yReversed[ri] : ri;
    html += '<tr>';
    html += `<td style="padding:2px 4px;color:var(--dim);font-size:8px;white-space:nowrap">${loadVal}%</td>`;
    for(const val of row){
      if(val === 0){
        // Celda sin datos en el EEPROM — fondo oscuro, sin número
        html += `<td style="background:#1a1a22;color:#333;padding:1px 2px;text-align:center;
                 min-width:${cellW}px;height:${cellH}px;border:1px solid rgba(255,255,255,0.04);
                 font-size:7px" title="sin datos">·</td>`;
      } else {
        const t  = (val - vMin) / (vMax - vMin || 1);
        const bg = heatColor(t);
        const fg = t > 0.55 ? '#000' : '#fff';
        html += `<td style="background:${bg};color:${fg};padding:1px 2px;text-align:center;
                 min-width:${cellW}px;height:${cellH}px;border:1px solid rgba(255,255,255,0.06)">${val.toFixed(isFuel?0:1)}${unit}</td>`;
      }
    }
    html += '</tr>';
  }
  html += '</table>';

  const container = document.getElementById('mapContainer');
  if(container) container.innerHTML = html;
}

function heatColor(t){
  // Azul oscuro → naranja → rojo
  const stops = [
    [0.00, [10, 30, 80]],
    [0.35, [20, 80,160]],
    [0.60, [50,160, 80]],
    [0.80, [200,120,  0]],
    [1.00, [200, 30,  0]],
  ];
  let lo=stops[0], hi=stops[stops.length-1];
  for(let i=0;i<stops.length-1;i++){
    if(t>=stops[i][0] && t<=stops[i+1][0]){ lo=stops[i]; hi=stops[i+1]; break; }
  }
  const f=(t-lo[0])/(hi[0]-lo[0]||1);
  const r=Math.round(lo[1][0]+(hi[1][0]-lo[1][0])*f);
  const g=Math.round(lo[1][1]+(hi[1][1]-lo[1][1])*f);
  const b=Math.round(lo[1][2]+(hi[1][2]-lo[1][2])*f);
  return `rgb(${r},${g},${b})`;
}

// ── OBJETIVOS EDITOR ──────────────────────────────────────────────
async function loadObj() {
  try {
    const d = await (await fetch('/live.json?t='+Date.now())).json();
    document.getElementById('objJson').value = JSON.stringify(d.raw_objectives||{}, null, 2);
  } catch(e){ document.getElementById('objJson').value='{}'; }
}
async function saveObj() {
  try {
    const v = JSON.parse(document.getElementById('objJson').value);
    await fetch('/obj',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(v)});
    showTab('ride');
  } catch(e){ alert('JSON invalido: '+e); }
}

// ── MSQ ────────────────────────────────────────────────────────────
function handleMsqDrop(e){ e.preventDefault(); handleMsqFile(e.dataTransfer.files[0]); }
function handleMsqFile(file){
  if(!file) return;
  const r=new FileReader();
  r.onload=e=>parseMsq(e.target.result,file.name);
  r.readAsText(file);
}
function parseMsq(xml,fname){
  try{
    const doc=new DOMParser().parseFromString(xml,'text/xml');
    let front=null,rear=null;
    doc.querySelectorAll('*').forEach(el=>{
      const n=el.getAttribute&&el.getAttribute('name');
      if(n==='veBins1'&&!front) front=el.textContent.trim();
      if(n==='veBins2'&&!rear)  rear =el.textContent.trim();
    });
    if(!front){alert('No se encontraron tablas VE');return;}
    const parse=s=>{const nums=s.trim().split(/\s+/).map(Number);const rows=[];for(let i=0;i<nums.length;i+=13)rows.push(nums.slice(i,i+13));return rows;};
    fetch('/ve',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({front:parse(front),rear:rear?parse(rear):parse(front),source:'msq',filename:fname})});
    document.getElementById('msqDrop').textContent='Cargado: '+fname;
    document.getElementById('msqDrop').className='msq-drop loaded';
  }catch(err){alert('Error: '+err);}
}

// ── CERRAR RIDE ─────────────────────────────────────────────────────
async function closeRide(){
  if(!confirm('¿Cerrar el ride actual?')) return;
  trackUsage('btn_close_ride');
  try{
    const r=await fetch('/close_ride',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const d=await r.json();
    if(d.ok && d.session && d.ride_num){
      setTimeout(()=>{ openNoteModal(d.session, d.ride_num); }, 800);
    } else {
      // El ride ya fue auto-cerrado (reconexión automática) — abrir notas del último ride
      setTimeout(async()=>{
        try{
          const lr = await (await fetch('/rides?t='+Date.now())).json();
          const rides = lr.rides || [];
          if(rides.length){
            const last = rides[rides.length-1];
            openNoteModal(last.session, last.ride_num);
          }
        }catch(e){}
      }, 800);
    }
  }catch(e){}
  setTimeout(fetchLive,1000);
}

// ── RED ────────────────────────────────────────────────────────────
async function switchNet(action){
  const lbl=document.getElementById('netLabel');
  if(lbl) lbl.textContent=action==='wifi'?'Buscando WiFi...':'Activando hotspot...';
  try{await fetch('/network',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});}catch(e){}
  setTimeout(fetchLive,5000);
}
function updateNetStatus(mode){
  const label=document.getElementById('netLabel');
  const dot  =document.getElementById('netDot');
  if(!label) return;
  document.getElementById('btnWifi')    ?.classList.toggle('on',mode==='wifi');
  document.getElementById('btnHotspot') ?.classList.toggle('on',mode==='hotspot');
  if(mode==='wifi')      {label.textContent='WiFi conectado';    dot.style.background='var(--green)';dot.style.animation='';}
  else if(mode==='hotspot'){label.textContent='Hotspot 10.42.0.1';dot.style.background='var(--blue)'; dot.style.animation='';}
  else                   {label.textContent='Sin red';           dot.style.background='var(--dim)'; dot.style.animation='none';}
}

async function loadNetPane(){
  // Cargar redes guardadas
  const sv = await fetch('/wifi/saved').then(r=>r.json()).catch(()=>({saved:[]}));
  const el = document.getElementById('savedList');
  if(!el) return;
  if(!sv.saved.length){
    el.innerHTML='<div style="font-family:var(--mono);font-size:9px;color:var(--dim)">Sin redes guardadas</div>';
    return;
  }
  el.innerHTML = sv.saved.map(s=>`
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:7px 0;border-bottom:1px solid var(--border)">
      <div>
        <span style="font-family:var(--mono);font-size:10px">${s.ssid}</span>
        <span style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-left:6px">${s.name}</span>
      </div>
      <div style="display:flex;gap:6px">
        <button class="btn g" style="font-size:9px;padding:4px 8px"
          onclick="doConnect('${s.name.replace(/'/g,"\\'")}')">Conectar</button>
        <button class="btn" style="font-size:9px;padding:4px 8px;color:var(--red)"
          onclick="doForget('${s.name.replace(/'/g,"\\'")}','${s.ssid.replace(/'/g,"\\'")}')">✕</button>
      </div>
    </div>`).join('');
}

async function doConnect(profileName){
  if(!confirm(`¿Conectar a "${profileName}"?\nEl hotspot se apagará.`)) return;
  await fetch('/wifi/connect',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({profile:profileName})});
  setTimeout(()=>{fetchLive();loadNetPane();}, 6000);
}

async function doForget(name, ssid){
  if(!confirm(`¿Eliminar red "${ssid}"?`)) return;
  await fetch('/wifi/forget',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name})});
  setTimeout(loadNetPane, 1000);
}

async function doWifiScan(e){
  const btn=e.target;
  btn.textContent='Escaneando...'; btn.disabled=true;
  const sv = await fetch('/wifi/saved').then(r=>r.json()).catch(()=>({saved:[]}));
  const savedSsids = new Set(sv.saved.map(s=>s.ssid));
  const r = await fetch('/wifi/scan',{method:'POST',
    headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.json()).catch(()=>({networks:[]}));
  btn.textContent='📶 Buscar redes'; btn.disabled=false;
  const el=document.getElementById('scanList');
  if(!r.networks.length){
    el.innerHTML='<div style="font-family:var(--mono);font-size:9px;color:var(--dim)">No se encontraron redes</div>';
    return;
  }
  el.innerHTML=r.networks.map(n=>{
    const saved=savedSsids.has(n.ssid);
    return `
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:6px 0;border-bottom:1px solid var(--border)">
      <div>
        <span style="font-family:var(--mono);font-size:10px">${n.ssid}</span>
        <span style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-left:6px">${n.signal}%</span>
        ${saved?'<span style="font-family:var(--mono);font-size:8px;color:var(--green);margin-left:4px">✓</span>':''}
      </div>
      <button class="btn ${saved?'g':''}" style="font-size:9px;padding:4px 8px"
        onclick="prefillWifi('${n.ssid.replace(/'/g,"\\'")}')">
        ${saved?'Conectar':'Agregar'}</button>
    </div>`}).join('');
}

function prefillWifi(ssid){
  document.getElementById('newSsid').value=ssid;
  document.getElementById('newPass').value='';
  document.getElementById('newPass').focus();
}

async function doAddWifi(){
  const ssid=document.getElementById('newSsid').value.trim();
  const pass=document.getElementById('newPass').value;
  if(!ssid||!pass){alert('Falta SSID o contraseña');return;}
  if(!confirm(`¿Conectar a "${ssid}"?\nEl hotspot se apagará.`)) return;
  await fetch('/wifi/add',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ssid,password:pass})});
  document.getElementById('newSsid').value='';
  document.getElementById('newPass').value='';
  setTimeout(()=>{fetchLive();loadNetPane();}, 8000);
}

// ── RIDES (selección múltiple + sumatoria) ────────────────────────
let ridesCache=[];
let selectedRides=new Set();
let _noteCtx={session:'',ride_num:0};

async function loadSessions(){
  const el=document.getElementById('ridesList'); if(!el) return;
  el.innerHTML='<div style="font-family:var(--mono);font-size:10px;color:var(--dim);padding:20px;text-align:center">Cargando...</div>';
  try{
    const d=await(await fetch('/rides?t='+Date.now())).json();
    const rides=(d.rides||[]);
    ridesCache=rides.slice().reverse();
    if(!ridesCache.length){
      el.innerHTML='<div style="font-family:var(--mono);font-size:10px;color:var(--dim);padding:20px;text-align:center">Sin rides guardados</div>';
      return;
    }
    const sessions={};
    for(const r of ridesCache){
      if(!sessions[r.session]) sessions[r.session]={rides:[],latest:0};
      sessions[r.session].rides.push(r);
      if((r.ride_num||0)>sessions[r.session].latest) sessions[r.session].latest=r.ride_num||0;
    }
    const sesKeys=Object.keys(sessions).sort((a,b)=>sessions[b].latest-sessions[a].latest);
    const live=lastData?.ride_active;
    let html='';
    if(live) html+='<div style="font-family:var(--mono);font-size:9px;color:var(--accent);padding:4px 0 10px">⚡ Ride activo — historial disponible al terminar</div>';
    for(const sk of sesKeys){
      const s=sessions[sk];
      html+=`<div style="margin-bottom:12px">
        <div onclick="toggleSession('ses_${sk}')" style="cursor:pointer;display:flex;justify-content:space-between;
             align-items:center;background:#1a1a1a;border:1px solid var(--border);padding:7px 10px;margin-bottom:2px">
          <span style="font-family:var(--mono);font-size:10px;color:var(--dim);letter-spacing:.1em">${sk}</span>
          <span style="font-family:var(--mono);font-size:9px;color:var(--dim)">${s.rides.length} rides ▾</span>
        </div>
        <div id="ses_${sk}">`;
      for(const r of s.rides){
        const ri=ridesCache.indexOf(r);
        const dur=r.duration_s?Math.round(r.duration_s)+'s':'--';
        const dtcBadge=(r.dtc_events&&r.dtc_events.length)?`<span style="color:var(--accent);font-size:9px">⚠${r.dtc_events.length}</span>`:'';
        const noteBadge=r.has_note?'<span style="color:#7df;font-size:9px">📝</span>':'';
        const errBadge=r.has_errorlog?`<span style="color:#f90;font-size:9px" title="${r.errorlog_summary||'errores'}">🔴${r.errorlog_events||''}</span>`:'';
        const closeR=r.close_reason?` · ${r.close_reason}`:'';
        html+=`<div class="ride-item" style="gap:4px;opacity:${live?0.5:1};pointer-events:${live?'none':'auto'}">
          <div style="flex:1;min-width:0">
            <div class="ride-name" style="display:flex;align-items:center;gap:5px">
              ride_${String(r.ride_num).padStart(3,'0')} ${dtcBadge} ${noteBadge} ${errBadge}
            </div>
            <div class="ride-meta">${dur} · ${r.samples} muestras${closeR}</div>
            ${r.has_note?`<div style="font-family:var(--mono);font-size:8px;color:#888;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${r.note_preview}</div>`:''}
          </div>
          <div style="display:flex;gap:4px;flex-shrink:0">
            <button class="btn" style="font-size:9px;padding:4px 7px" onclick="viewSingleRide(${ri})">Ver</button>
            <button class="btn p" style="font-size:9px;padding:4px 7px" onclick="openRideGraph(${ri})">Graf</button>
            <button class="btn" style="font-size:9px;padding:4px 7px" onclick="openNoteModal('${sk}',${r.ride_num})">📝</button>
            <a href="/csv/${r.filename}?t=${Date.now()}" download="ride_${r.ride_num}.csv"
               onclick="event.stopPropagation()"
               style="font-family:var(--mono);font-size:9px;color:var(--blue);text-decoration:none;
                      border:1px solid var(--blue);padding:4px 6px">CSV</a>
          </div>
        </div>`;
      }
      html+=`</div></div>`;
    }
    el.innerHTML=html;
  }catch(e){
    el.innerHTML='<div style="font-family:var(--mono);font-size:10px;color:var(--dim);padding:20px">Error: '+e+'</div>';
  }
}

function toggleSession(id){
  const el=document.getElementById(id); if(!el) return;
  el.style.display=el.style.display==='none'?'':'none';
}

function openNoteModal(session,ride_num){
  _noteCtx={session,ride_num};
  document.getElementById('noteModalTitle').textContent=`NOTA — ${session} ride_${String(ride_num).padStart(3,'0')}`;
  document.getElementById('noteText').value='';
  document.getElementById('noteStatus').textContent='Cargando...';
  document.getElementById('noteModal').style.display='flex';
  fetch(`/ride_note?session=${encodeURIComponent(session)}&ride=${ride_num}&t=${Date.now()}`)
    .then(r=>r.json()).then(d=>{
      document.getElementById('noteText').value=d.note||'';
      document.getElementById('noteStatus').textContent='';
    }).catch(()=>{ document.getElementById('noteStatus').textContent=''; });
}

function closeNoteModal(){
  document.getElementById('noteModal').style.display='none';
  loadSessions();
}

async function saveNote(){
  const text=document.getElementById('noteText').value;
  trackUsage('btn_guardar_nota');
  document.getElementById('noteStatus').textContent='Guardando...';
  try{
    const r=await fetch('/ride_note',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({session:_noteCtx.session,ride_num:_noteCtx.ride_num,note:text})});
    const d=await r.json();
    document.getElementById('noteStatus').textContent=d.ok?'✓ Guardado':'Error al guardar';
    if(d.ok) setTimeout(()=>{ document.getElementById('noteStatus').textContent=''; },1500);
  }catch(e){ document.getElementById('noteStatus').textContent='Error: '+e; }
}

async function viewSingleRide(idx){
  trackUsage('btn_ver_ride');
  selectedRides=new Set([idx]);
  await viewSelectedRides();
}

function openRideGraph(idx){
  trackUsage('btn_graf_ride');
  const r=ridesCache[idx]; if(!r) return;
  showTab('graph');
  // Pasar filename directo — no depender de que el select esté populado
  setTimeout(()=>{ loadGraphRide(r.filename); },120);
}

function openLiveRideGraph(){
  if(!ridesCache || !ridesCache.length){ alert('Cargando rides...'); loadSessions(); return; }
  showTab('graph');
  setTimeout(()=>{ loadGraphRide(ridesCache[0].filename); },120);
}

// loadRidesList alias para compatibilidad con initGraphPane
function loadRidesList(){ return loadSessions(); }

async function viewSelectedRides(){
  if(!selectedRides.size) return;
  const indices=[...selectedRides];
  const rides=indices.map(i=>ridesCache[i]).filter(Boolean);
  const summaries=await Promise.all(rides.map(r=>
    fetch('/ride/'+r.filename+'?t='+Date.now()).then(x=>x.json()).catch(()=>null)
  ));
  const merged={};
  for(const s of summaries){
    if(!s) continue;
    for(const [key,val] of Object.entries(s.cells||{})){
      if(!merged[key]) merged[key]={seconds:0,ego_sum:0,count:0};
      merged[key].seconds+=val.seconds;
      merged[key].ego_sum+=val.ego_avg*(val.seconds||1);
      merged[key].count+=(val.seconds||1);
    }
  }
  const cells={};
  for(const [k,v] of Object.entries(merged))
    cells[k]={seconds:parseFloat(v.seconds.toFixed(1)),ego_avg:parseFloat((v.ego_sum/v.count).toFixed(1))};
  const objCfg=lastData?.raw_objectives||{};
  const objectives=(objCfg.cell_targets||[]).map(ct=>{
    const matching=RPM_BINS.flatMap(r=>LOAD_BINS.filter(l=>r>=ct.rpm_min&&r<=ct.rpm_max&&l>=ct.load_min&&l<=ct.load_max).map(l=>`${r}_${l}`));
    const done=matching.filter(k=>cells[k]?.seconds>=(ct.seconds||5)).length;
    return {label:ct.label,target_s:ct.seconds,done_cells:done,total_cells:matching.length,pct:matching.length?done/matching.length*100:0};
  });
  const rideLabel=rides.length===1?rides[0].filename.replace('.csv','').replace('_',' '):
                  `${rides.length} rides sumados`;
  lastData={...(lastData||{}),cells,objectives,ride_active:false,
            ride_num:null,elapsed_s:0,active_cell:null};
  updateGrid(cells,null);
  renderObjectives(objectives);
  window._viewingHistory=true;
  showTab('ride');
  document.getElementById('objList').insertAdjacentHTML('afterbegin',
    `<div style="background:rgba(232,66,10,.12);border:1px solid var(--accent);padding:8px 10px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;font-family:var(--mono);font-size:9px;color:var(--accent);width:100%">
      <span>${rideLabel}</span>
      <span onclick="exitHistory()" style="cursor:pointer;padding:2px 8px;border:1px solid var(--accent)">LIVE</span>
    </div>`);
}

function exitHistory(){
  window._viewingHistory=false;
  fetchLive();
}

// ── USAGE TRACKER ─────────────────────────────────────────────────
function trackUsage(action){
  fetch('/usage',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action})}).catch(()=>{});
}

async function loadUsageStats(){
  const el=document.getElementById('usageList'); if(!el) return;
  try{
    const d=await(await fetch('/usage_stats?t='+Date.now())).json();
    const entries=Object.entries(d).filter(([k])=>k!=='last_updated')
      .sort((a,b)=>b[1]-a[1]);
    if(!entries.length){ el.innerHTML='<div style="color:var(--dim);font-size:9px">Sin datos aún</div>'; return; }
    const max=entries[0][1]||1;
    el.innerHTML=entries.map(([k,v])=>{
      const pct=Math.round(v/max*100);
      return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
        <div style="font-family:var(--mono);font-size:8px;color:var(--dim);width:130px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${k}</div>
        <div style="flex:1;background:#222;height:6px;border-radius:2px">
          <div style="width:${pct}%;background:#7df;height:100%;border-radius:2px"></div>
        </div>
        <div style="font-family:var(--mono);font-size:8px;color:#fff;width:24px;text-align:right">${v}</div>
      </div>`;
    }).join('');
    const upd=d.last_updated||'';
    if(upd) el.insertAdjacentHTML('beforeend',`<div style="font-family:var(--mono);font-size:7px;color:var(--dim);margin-top:6px">${upd}</div>`);
  }catch(e){ el.innerHTML='<div style="color:var(--dim);font-size:9px">Error</div>'; }
}

async function clearUsageStats(){
  if(!confirm('¿Limpiar todos los contadores de uso?')) return;
  await fetch('/usage',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'__clear__'})}).catch(()=>{});
  // limpiar en servidor vía endpoint dedicado
  await fetch('/usage_clear',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).catch(()=>{});
  loadUsageStats();
}


// ── GRÁFICAS ──────────────────────────────────────────────────────

// ═══════════════════════════════════════════════════════════════
// GRÁFICAS — Chart.js con marcadores de eventos
// ═══════════════════════════════════════════════════════════════

const CHART_DEFAULTS = {
  animation: false,
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode:'index', intersect:false },
  plugins: { legend:{ display:false }, tooltip:{ enabled:true,
    callbacks:{ label: ctx => `${ctx.dataset.label||''}: ${ctx.parsed.y!=null?ctx.parsed.y.toFixed(1):''}` }
  }},
  scales:{
    x:{ type:'linear', ticks:{ font:{family:'monospace',size:8}, color:'#555',
          callback: v => v%30===0 ? (v+'s') : '' },
        grid:{ color:'rgba(255,255,255,.04)' }},
    y:{ ticks:{ font:{family:'monospace',size:8}, color:'#777' },
        grid:{ color:'rgba(255,255,255,.06)' }}
  }
};

let _charts = {};

function destroyCharts(){
  for(const ch of Object.values(_charts)) try{ ch.destroy(); }catch(e){}
  _charts={};
}

// Color palette
const C = {
  rpm:'#e8420a', kph:'#4af', clt:'#fa0', clt_hot:'#f80',
  tps:'#38f', ego:'#0f8', spk1:'#a8f', spk2:'#c8f',
  afv:'#ff0', wue:'#f90', batt:'#7df', cel:'#8af', dtc:'#ff4', kill:'#f44',
  wot:'#0f8', gear:'#a8f', hot:'#f80', cold:'#4af',
};

// Scatter marker dataset
function markerSet(label, data, color, symbol='circle', r=4){
  return { label, data, type:'scatter', pointStyle:symbol,
           pointRadius:r, pointHoverRadius:r+2,
           backgroundColor:color+'cc', borderColor:color,
           borderWidth:1, showLine:false, order:-1 };
}

// ── PARSEAR CSV ──────────────────────────────────────────────
function parseCSVtoRows(text){
  const lines = text.trim().split('\n').filter(l=>!l.startsWith('#'));
  const headers = lines[0].split(',').map(h=>h.trim());
  const rows = [];
  for(let i=1;i<lines.length;i++){
    const vals = lines[i].split(',');
    const row = {};
    headers.forEach((h,j) => {
      const v = vals[j]?.trim();
      row[h] = (v===''||v===undefined||v==='None') ? null : isNaN(v) ? v : parseFloat(v);
    });
    rows.push(row);
  }
  return rows;
}

// ── EXTRAER EVENTOS DE CAMBIO DE BIT ─────────────────────────
function extractTransitions(rows, field, targetVal=1){
  const events=[]; let prev=null;
  for(const r of rows){
    const v = r[field];
    if(prev!=null && prev!==targetVal && v===targetVal)
      events.push({x: r.time_elapsed_s, y: null});
    prev = v;
  }
  return events;
}

// Detectar cambios de marcha por saltos de RPM con VSS estable
function detectGearChanges(rows){
  const events=[];
  for(let i=2;i<rows.length;i++){
    const r=rows[i], p=rows[i-2];
    const drpm = Math.abs((r.RPM||0)-(p.RPM||0));
    const vss  = r.VSS_Count||0;
    if(drpm>400 && vss>10) events.push({x:r.time_elapsed_s, y:null});
  }
  return events;
}

// Detectar WOT (TPS > 80%)
function detectWOT(rows){
  const ev=[]; let inWOT=false;
  for(const r of rows){
    if(!inWOT && (r.TPS_pct||0)>80){ ev.push({x:r.time_elapsed_s,y:null}); inWOT=true; }
    if(inWOT  && (r.TPS_pct||0)<60){ inWOT=false; }
  }
  return ev;
}

// Detectar DTC nuevo (CDiag0-4 cambia a nonzero)
function detectDTC(rows){
  const ev=[]; let prev=0;
  for(const r of rows){
    const sum=(r.CDiag0||0)+(r.CDiag1||0)+(r.CDiag2||0)+(r.CDiag3||0)+(r.CDiag4||0);
    if(sum>0 && prev===0) ev.push({x:r.time_elapsed_s,y:null});
    prev=sum;
  }
  return ev;
}

// ── CREAR GRÁFICAS ────────────────────────────────────────────
function buildCharts(rows){
  destroyCharts();
  const t      = rows.map(r=>r.time_elapsed_s);
  const tFirst = t[0] ?? 0;
  const tLast  = t[t.length-1] ?? 1;

  // ── 1. RPM + KPH + CLT  (triple eje) ──────────────────────
  const rpmData  = rows.map(r=>({x:r.time_elapsed_s, y:r.RPM}));
  const kphData  = rows.map(r=>({x:r.time_elapsed_s, y:r.VS_KPH}));
  const cltData  = rows.map(r=>({x:r.time_elapsed_s, y:r.CLT}));
  const wotEvts  = detectWOT(rows).map(e=>({...e, y: rows.find(r=>r.time_elapsed_s>=e.x)?.RPM||0}));
  const dtcEvts  = detectDTC(rows).map(e=>({...e, y: rows.find(r=>r.time_elapsed_s>=e.x)?.RPM||0}));
  const celEvts  = extractTransitions(rows,'do_cel',1).map(e=>({...e, y: rows.find(r=>r.time_elapsed_s>=e.x)?.RPM||0}));
  const gearEvts = detectGearChanges(rows).map(e=>({...e, y: rows.find(r=>r.time_elapsed_s>=e.x)?.RPM||0}));
  const hotEvts  = extractTransitions(rows,'fl_hot',1).map(e=>({...e, y: rows.find(r=>r.time_elapsed_s>=e.x)?.RPM||0}));
  const killEvts = extractTransitions(rows,'fl_kill',1).map(e=>({...e, y: rows.find(r=>r.time_elapsed_s>=e.x)?.RPM||0}));
  const cltVals  = rows.map(r=>r.CLT||0).filter(v=>v>0);
  const cltMin   = cltVals.length ? Math.min(...cltVals) : 100;
  const cltMax   = cltVals.length ? Math.max(...cltVals) : 300;

  const ctxRPM = document.getElementById('chartRPM').getContext('2d');
  _charts.rpm = new Chart(ctxRPM, { type:'line', data:{ datasets:[
    { label:'RPM',   data:rpmData, borderColor:C.rpm, borderWidth:1.5,
      pointRadius:0, fill:false, tension:0.1, yAxisID:'y' },
    { label:'KPH',   data:kphData, borderColor:C.kph, borderWidth:1.5,
      pointRadius:0, fill:false, tension:0.1, yAxisID:'y2' },
    { label:'CLT°F', data:cltData, borderColor:C.clt, borderWidth:1.2,
      borderDash:[3,2], pointRadius:0, fill:false, tension:0.1, yAxisID:'y3' },
    { label:'250°F (lim)', data:[{x:tFirst,y:250},{x:tLast,y:250}],
      borderColor:'#f804', borderWidth:1, borderDash:[4,4],
      pointRadius:0, fill:false, yAxisID:'y3' },
    markerSet('WOT',    wotEvts,  C.wot,  'triangle', 5),
    markerSet('Cambio', gearEvts, C.gear, 'rectRot',  4),
    markerSet('DTC',    dtcEvts,  C.dtc,  'triangle', 6),
    markerSet('CEL',    celEvts,  C.cel,  'circle',   5),
    markerSet('fl_hot', hotEvts,  C.hot,  'triangle', 5),
    markerSet('Kill',   killEvts, C.kill, 'crossRot', 6),
  ]}, options:{...CHART_DEFAULTS, scales:{
    ...CHART_DEFAULTS.scales,
    y:{  ...CHART_DEFAULTS.scales.y, position:'left',
         title:{display:true,text:'RPM',font:{family:'monospace',size:7},color:C.rpm}},
    y2:{ type:'linear', position:'right',
         ticks:{font:{family:'monospace',size:8},color:C.kph},
         grid:{drawOnChartArea:false},
         title:{display:true,text:'KPH',font:{family:'monospace',size:7},color:C.kph}},
    y3:{ type:'linear', position:'right',
         min: Math.max(0, cltMin-15), max: Math.max(cltMax+20, 280),
         ticks:{font:{family:'monospace',size:8},color:C.clt},
         grid:{drawOnChartArea:false},
         title:{display:true,text:'CLT°F',font:{family:'monospace',size:7},color:C.clt}}
  }}});

  // ── 2. Correcciones combustible: EGO + AFV + WUE + Promedio ─
  const egoData  = rows.map(r=>({x:r.time_elapsed_s, y:r.EGO_Corr}));
  const afvData  = rows.map(r=>({x:r.time_elapsed_s, y:r.AFV}));
  const wueData  = rows.map(r=>({x:r.time_elapsed_s, y:r.WUE}));
  const avgData  = rows.map(r=>{
    const ego = r.EGO_Corr ?? 100;
    const afv = r.AFV      ?? 100;
    const wue = r.WUE      ?? 100;
    return {x:r.time_elapsed_s, y: parseFloat(((ego+afv+wue)/3).toFixed(2))};
  });
  const fuelRef  = [{x:tFirst,y:100},{x:tLast,y:100}];
  const fuelVals = [...egoData,...afvData,...wueData].map(d=>d.y).filter(v=>v!=null);
  const fuelMin  = fuelVals.length ? Math.min(...fuelVals) : 80;
  const fuelMax  = fuelVals.length ? Math.max(...fuelVals) : 120;
  const richEvts = rows.filter(r=>(r.EGO_Corr??100)>106)
    .map(r=>({x:r.time_elapsed_s, y:r.EGO_Corr}));
  const leanEvts = rows.filter(r=>(r.EGO_Corr??100)<94)
    .map(r=>({x:r.time_elapsed_s, y:r.EGO_Corr}));

  const ctxFuel = document.getElementById('chartFuel').getContext('2d');
  _charts.fuel = new Chart(ctxFuel, { type:'line', data:{ datasets:[
    { label:'EGO Corr %', data:egoData, borderColor:C.ego, borderWidth:1.5,
      pointRadius:0, fill:false, tension:0.1 },
    { label:'AFV %',      data:afvData, borderColor:C.afv, borderWidth:1.5,
      pointRadius:0, fill:false, tension:0.1 },
    { label:'WUE %',      data:wueData, borderColor:C.wue, borderWidth:1.2,
      borderDash:[3,2], pointRadius:0, fill:false, tension:0.1 },
    { label:'Promedio',   data:avgData, borderColor:'#fff', borderWidth:2,
      borderDash:[6,3], pointRadius:0, fill:false, tension:0.1 },
    { label:'100%', data:fuelRef, borderColor:'#5556',
      borderWidth:1, borderDash:[4,4], pointRadius:0, fill:false },
    markerSet('Rico',  richEvts, '#f44', 'circle', 2),
    markerSet('Pobre', leanEvts, '#4af', 'circle', 2),
  ]}, options:{...CHART_DEFAULTS, scales:{
    ...CHART_DEFAULTS.scales,
    y:{...CHART_DEFAULTS.scales.y,
       min: Math.floor(fuelMin-5), max: Math.ceil(fuelMax+5)}
  }}});

  // ── 3. TPS % (solo) ──────────────────────────────────────
  const tpsData    = rows.map(r=>({x:r.time_elapsed_s, y:r.TPS_pct}));
  const decelEvts  = extractTransitions(rows,'fl_decel',1)
    .map(e=>({...e, y: rows.find(r=>r.time_elapsed_s>=e.x)?.TPS_pct||0}));
  const wotTpsEvts = detectWOT(rows)
    .map(e=>({...e, y: rows.find(r=>r.time_elapsed_s>=e.x)?.TPS_pct||0}));

  const ctxTPS = document.getElementById('chartTPS').getContext('2d');
  _charts.tps = new Chart(ctxTPS, { type:'line', data:{ datasets:[
    { label:'TPS%', data:tpsData, borderColor:C.tps, borderWidth:1.5,
      pointRadius:0, fill:false, tension:0.1 },
    markerSet('Decel', decelEvts,  '#aaf', 'triangle', 3),
    markerSet('WOT',   wotTpsEvts, C.wot,  'triangle', 5),
  ]}, options:{...CHART_DEFAULTS, scales:{
    ...CHART_DEFAULTS.scales,
    y:{...CHART_DEFAULTS.scales.y, min:0, max:100,
       title:{display:true,text:'TPS%',font:{family:'monospace',size:7},color:C.tps}}
  }}});

  // ── 4. Spark (°) + Pulse Width (ms)  doble eje ───────────
  const spk1Data    = rows.map(r=>({x:r.time_elapsed_s, y:r.spark1}));
  const spk2Data    = rows.map(r=>({x:r.time_elapsed_s, y:r.spark2}));
  const pw1Data     = rows.map(r=>({x:r.time_elapsed_s, y:r.pw1}));
  const pw2Data     = rows.map(r=>({x:r.time_elapsed_s, y:r.pw2}));
  const spkZeroEvts = rows.filter(r=>(r.spark1??1)===0 && (r.fl_decel??0)===0)
    .map(r=>({x:r.time_elapsed_s, y:0}));
  const cutEvts     = extractTransitions(rows,'fl_fuel_cut',1)
    .map(e=>({...e, y: rows.find(r=>r.time_elapsed_s>=e.x)?.spark1||0}));
  const pwVals      = rows.map(r=>r.pw1||0).filter(v=>v>0);
  const pwMax       = pwVals.length ? Math.max(...pwVals) : 14;

  const ctxSPK = document.getElementById('chartSPK').getContext('2d');
  _charts.spk = new Chart(ctxSPK, { type:'line', data:{ datasets:[
    { label:'Spark1 °BTDC', data:spk1Data, borderColor:C.spk1, borderWidth:1.5,
      pointRadius:0, fill:false, tension:0.1, yAxisID:'y' },
    { label:'Spark2 °BTDC', data:spk2Data, borderColor:C.spk2, borderWidth:1.2,
      borderDash:[3,2], pointRadius:0, fill:false, tension:0.1, yAxisID:'y' },
    { label:'PW1 ms',       data:pw1Data,  borderColor:'#f90', borderWidth:1.5,
      pointRadius:0, fill:false, tension:0.1, yAxisID:'y2' },
    { label:'PW2 ms',       data:pw2Data,  borderColor:'#fa6', borderWidth:1.2,
      borderDash:[3,2], pointRadius:0, fill:false, tension:0.1, yAxisID:'y2' },
    markerSet('Fuel Cut', cutEvts,     C.kill, 'crossRot', 6),
    markerSet('Spark=0°', spkZeroEvts, '#f44', 'circle',   4),
  ]}, options:{...CHART_DEFAULTS, scales:{
    ...CHART_DEFAULTS.scales,
    y:{  ...CHART_DEFAULTS.scales.y, min:0, max:35, position:'left',
         title:{display:true,text:'° BTDC',font:{family:'monospace',size:7},color:C.spk1}},
    y2:{ type:'linear', position:'right', min:0, max:Math.ceil(pwMax+1),
         ticks:{font:{family:'monospace',size:8},color:'#f90'},
         grid:{drawOnChartArea:false},
         title:{display:true,text:'PW ms',font:{family:'monospace',size:7},color:'#f90'}}
  }}});

  // ── 5. Batt V ────────────────────────────────────────────
  const battData = rows.map(r=>({x:r.time_elapsed_s, y:r.Batt_V}));
  const battVals = battData.map(d=>d.y).filter(v=>v!=null);
  const battMin  = battVals.length ? Math.min(...battVals) : 11;
  const battMax  = battVals.length ? Math.max(...battVals) : 15;

  const ctxBatt = document.getElementById('chartBatt').getContext('2d');
  _charts.batt = new Chart(ctxBatt, { type:'line', data:{ datasets:[
    { label:'Batt V', data:battData, borderColor:C.batt, borderWidth:1.2,
      pointRadius:0, fill:false, tension:0.1 },
    { label:'12.5V', data:[{x:tFirst,y:12.5},{x:tLast,y:12.5}],
      borderColor:'rgba(255,255,255,0.25)', borderWidth:1,
      borderDash:[4,4], pointRadius:0, fill:false },
  ]}, options:{...CHART_DEFAULTS, scales:{
    ...CHART_DEFAULTS.scales,
    y:{...CHART_DEFAULTS.scales.y,
       min: Math.min(battMin-0.3, 11.5),
       max: Math.max(battMax+0.3, 14.5)}
  }}});

  // Mostrar leyenda
  document.getElementById('graphLegend').style.display='flex';
}

// ── CARGAR RIDES EN SELECTOR ──────────────────────────────────
function initGraphPane(){
  if(!ridesCache || !ridesCache.length){
    loadRidesList().then(()=>_fillGraphSelect());
    return;
  }
  _fillGraphSelect();
}
function _fillGraphSelect(){
  const sel = document.getElementById('graphRideSelect');
  if(!ridesCache || !ridesCache.length){
    sel.innerHTML='<option value="">Sin rides guardados</option>';
    return;
  }
  sel.innerHTML = '<option value="">-- Selecciona un ride --</option>' +
    ridesCache.map(r=>{
      const dateStr = _rideDate(r);
      const label = r.filename.replace('_summary.json','').replace(/_/g,' ').toUpperCase();
      return `<option value="${r.filename}">${label} · ${dateStr} · ${Math.round(r.duration_s||0)}s · ${r.samples} muestras${(r.dtc_events&&r.dtc_events.length)?'  ⚠':''}</option>`;
    }).join('');
}

function _rideDate(r){
  // Usar opened_utc (inicio del ride) con fallback a closed_utc
  const iso = r.opened_utc || r.closed_utc || '';
  if(!iso) return '';
  try{
    const d = new Date(iso);
    const yy = String(d.getFullYear()).slice(2);
    const MM = String(d.getMonth()+1).padStart(2,'0');
    const dd = String(d.getDate()).padStart(2,'0');
    const hh = String(d.getHours()).padStart(2,'0');
    const mm = String(d.getMinutes()).padStart(2,'0');
    return yy+MM+dd+hh+mm;
  }catch(e){ return ''; }
}

// ── CARGAR CSV Y RENDERIZAR ───────────────────────────────────
async function loadGraphRide(directFile){
  const sel   = document.getElementById('graphRideSelect');
  const fname = directFile || sel.value;
  const status= document.getElementById('graphStatus');
  if(!fname){ status.textContent='Selecciona un ride'; return; }
  // Sincronizar el select si viene de openRideGraph
  if(directFile && sel) sel.value = directFile;

  const csvName = fname.replace('_summary.json','.csv');
  const cleanName = fname.replace('_summary.json','').replace(/_/g,' ');
  const rideLabel = cleanName.toUpperCase();

  // Buscar fecha en ridesCache
  const rideInfo = (ridesCache||[]).find(r=>r.filename===fname);
  const dateStr = rideInfo ? _rideDate(rideInfo) : '';

  status.textContent='Cargando...';
  const titleEl = document.getElementById('graphRideTitle');
  if(titleEl){ titleEl.textContent=''; titleEl.style.display='none'; }
  destroyCharts();
  document.getElementById('graphLegend').style.display='none';
  try{
    const resp = await fetch('/csv/'+csvName+'?t='+Date.now());
    if(!resp.ok) throw new Error('HTTP '+resp.status);
    const text = await resp.text();
    const rows = parseCSVtoRows(text);
    const dur = Math.round(rows[rows.length-1]?.time_elapsed_s||0);
    status.textContent = `${rows.length} muestras · ${dur}s`;
    if(titleEl){
      const datePart = dateStr ? `  <span style="color:#888;font-size:10px">${dateStr}</span>` : '';
      titleEl.innerHTML = '▶ ' + rideLabel + datePart;
      titleEl.style.display='block';
    }
    buildCharts(rows);
  }catch(e){
    status.textContent = 'Error: '+e;
  }
}


// ── KEEPALIVE ──────────────────────────────────────────────────────
async function doKeepalive(){
  try{
    await fetch('/keepalive',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const btn=document.querySelector('.btn.g');
    if(btn){const o=btn.textContent;btn.textContent='5 min activos';setTimeout(()=>btn.textContent=o,2500);}
  }catch(e){}
}
setInterval(()=>{try{fetch('/keepalive',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}catch(e){}},240000);

// ── APAGADO ────────────────────────────────────────────────────────
function confirmShutdown(){
  document.getElementById('sheetTitle').textContent='Apagar Pi';
  document.getElementById('sheetBody').innerHTML=`
    <div style="text-align:center;padding:8px 0 16px;font-size:13px;line-height:1.7">
      Se cerrara el ride activo y la Pi se apagara.<br>
      <span style="font-family:var(--mono);font-size:9px;color:var(--dim)">Asegurate de estar detenido.</span>
    </div>
    <div style="display:flex;gap:8px">
      <button class="btn" style="flex:1;padding:10px" onclick="closeSheet()">Cancelar</button>
      <button class="btn-danger" style="flex:1;margin:0;padding:10px" onclick="doShutdown()">Apagar</button>
    </div>`;
  document.getElementById('overlay').classList.add('open');
}
async function doShutdown(){
  trackUsage('btn_poweroff');
  closeSheet();
  try{await fetch('/shutdown',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}catch(e){}
  document.body.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100dvh;font-family:var(--mono);font-size:12px;color:var(--dim);background:#0a0a0b">Apagando Pi...</div>';
}

// ── ECU CONFIG (EEPROM) ───────────────────────────────────────────
let ecuPanelOpen = true;
function toggleEcu(){
  ecuPanelOpen = !ecuPanelOpen;
  document.getElementById('ecuPanel').style.display = ecuPanelOpen ? '' : 'none';
  document.getElementById('ecuToggleIcon').innerHTML = ecuPanelOpen ? '&#9660;' : '&#9654;';
}
function ecuRow(label, val, units, color){
  const c = color || '#ccc';
  return `<div style="display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;padding:3px 0;border-bottom:1px solid #1e1e1e"><span style="color:var(--dim)">${label}</span><span style="color:${c};font-weight:600">${val} <span style="color:var(--dim);font-weight:400">${units}</span></span></div>`;
}
async function loadEcu(){
  try{
    const d = await (await fetch('/eeprom?t='+Date.now())).json();
    if(!d || Object.keys(d).length===0){
      document.getElementById('ecuVersion').textContent='No disponible (llave ON y reiniciar)'; return;
    }
    document.getElementById('ecuVersion').textContent='OK';
    const tempMap=[['Fan ON','KTemp_Fan_On','#ccc'],['Fan OFF','KTemp_Fan_Off','#ccc'],
      ['CEL ON','KTemp_CEL_Flash_Hi','#fa0'],['Soft limit','KTemp_Soft_Hi','#ff0'],
      ['Hard limit','KTemp_Hard_Hi','#fa0'],['Kill limit','KTemp_Kill_Hi','#f55'],
      ['RPM min soft','KTemp_RPM_Soft','#8af'],['RPM min hard','KTemp_RPM_Hard','#8af'],
      ['TPS min soft','KTemp_TP_Soft','#8af'],['TPS min hard','KTemp_TP_Hard','#8af']];
    let h='';
    for(const [lbl,k,col] of tempMap){if(d[k]) h+=ecuRow(lbl,d[k].val.toFixed(0),d[k].units,col);}
    document.getElementById('ecuTempRows').innerHTML=h;
    const rpmMap=[['Soft trigger','KRPM_Soft_Hi','#ff0'],['Soft release','KRPM_Soft_Lo','#ff0'],
      ['Hard trigger','KRPM_Hard_Hi','#fa0'],['Hard release','KRPM_Hard_Lo','#fa0'],
      ['Kill trigger','KRPM_Kill_Hi','#f55'],['Kill release','KRPM_Kill_Lo','#f55']];
    h='';
    for(const [lbl,k,col] of rpmMap){if(d[k]) h+=ecuRow(lbl,d[k].val.toFixed(0),d[k].units,col);}
    document.getElementById('ecuRpmRows').innerHTML=h;
    const egoMap=[['O2 target','KO2_Midpoint','#6ef'],['O2 rich','KO2_Rich','#f88'],
      ['O2 lean','KO2_Lean','#8f8'],['CL min RPM','KO2_Min_RPM','#8af'],
      ['EGO max','KFBFuel_Max','#6ef'],['EGO min','KFBFuel_Min','#6ef'],
      ['AFV max','KLFuel_Max','#6ef'],['AFV min','KLFuel_Min','#6ef']];
    h='';
    for(const [lbl,k,col] of egoMap){if(d[k]) h+=ecuRow(lbl,d[k].val.toFixed(3),d[k].units,col);}
    document.getElementById('ecuEgoRows').innerHTML=h;
  }catch(e){ document.getElementById('ecuVersion').textContent='Error: '+e.message; }
}

// VSS CALIBRACION
let vssCal={cpkm25:1368};
async function doReconnect(){
  trackUsage('btn_reconnect_ecu');
  try{
    const r=await fetch('/reconnect',{method:'POST',
      headers:{'Content-Type':'application/json'},body:'{}'});
    const d=await r.json();
    alert(d.msg||'Reconexión solicitada — espera unos segundos');
  }catch(e){alert('Error al reconectar: '+e);}
}

async function doRestartLogger(){
  trackUsage('btn_restart_logger');
  try{
    await fetch('/restart_logger',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    alert('Logger reiniciando... reconecta en ~10 segundos');
  }catch(e){ /* normal — el proceso muere antes de responder */ }
}

async function doRebootPi(){
  if(!confirm('¿Reiniciar la Pi completa?')) return;
  trackUsage('btn_reboot_pi');
  try{
    await fetch('/reboot_pi',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    alert('Pi reiniciando... reconecta en ~30 segundos');
  }catch(e){ /* normal */ }
}

async function loadVssCal(){
  try{
    const d=await(await fetch('/live.json?t='+Date.now())).json();
    if(d.vss_cal){
      vssCal=d.vss_cal;
      const el=document.getElementById('vssFactorInput');
      if(el) el.value=vssCal.cpkm25;
    }
  }catch(e){}
}

// NUEVA función para Git Pull
async function gitPull() {
  const status = document.getElementById('gitPullStatus');
  status.textContent = 'Ejecutando git pull...';
  status.style.color = 'var(--dim)';
  try {
    const res = await fetch('/git_pull', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      if (data.changes) {
        status.innerHTML = '✅ Git pull completado. Hubo cambios.<br>Reinicia el logger para aplicarlos.';
      } else {
        status.textContent = '✅ Ya estaba actualizado.';
      }
      status.style.color = 'var(--green)';
    } else {
      status.textContent = '❌ Error: ' + (data.error || 'desconocido');
      status.style.color = 'var(--red)';
    }
    if (data.output) console.log(data.output);
  } catch (e) {
    status.textContent = 'Error de red: ' + e;
    status.style.color = 'var(--red)';
  }
}
async function saveVssCal(){
  const el=document.getElementById('vssFactorInput');
  const st=document.getElementById('vssCalStatus');
  const v=parseFloat(el.value);
  if(isNaN(v)||v<100||v>9999){st.textContent='Error: valor inválido';st.style.color='var(--accent)';return;}
  vssCal={cpkm25:v};
  try{
    await fetch('/vss_cal',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(vssCal)});
    st.textContent='Guardado';
    st.style.color='var(--green)';
    setTimeout(()=>st.textContent='',2500);
  }catch(e){st.textContent='Error al guardar';}
}

// TPS CALIBRACION
let tpsCal={min:139,max:479};
async function loadTpsCal(){
  try{
    const d=await(await fetch('/live.json?t='+Date.now())).json();
    if(d.tps_cal){
      tpsCal=d.tps_cal;
      const mn=document.getElementById('tpsMin');
      const mx=document.getElementById('tpsMax');
      if(mn) mn.value=tpsCal.min;
      if(mx) mx.value=tpsCal.max;
    }
  }catch(e){}
}
function calcTpsPct(raw){
  if(tpsCal.max<=tpsCal.min) return 0;
  return Math.max(0,Math.min(100,(raw-tpsCal.min)/(tpsCal.max-tpsCal.min)*100));
}
async function saveTpsCal(){
  const mn=parseInt(document.getElementById('tpsMin').value);
  const mx=parseInt(document.getElementById('tpsMax').value);
  const st=document.getElementById('tpsCalStatus');
  if(isNaN(mn)||isNaN(mx)||mn>=mx){
    st.textContent='Error: MIN debe ser menor que MAX';
    st.style.color='var(--accent)'; return;
  }
  tpsCal={min:mn,max:mx};
  try{
    await fetch('/tps_cal',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(tpsCal)});
    st.textContent='Guardado';
    st.style.color='var(--green)';
    setTimeout(()=>st.textContent='',2500);
  }catch(e){ st.textContent='Error al guardar'; }
}

let _tpsCaptureActive=false;
async function startTpsCapture(){
  if(_tpsCaptureActive) return;
  _tpsCaptureActive=true;
  const btn=document.getElementById('btnTpsCapture');
  const bar=document.getElementById('tpsCaptureBar');
  const msg=document.getElementById('tpsCaptureMsg');
  const prog=document.getElementById('tpsCaptureProgress');
  const st=document.getElementById('tpsCalStatus');
  btn.disabled=true; bar.style.display='block';
  msg.textContent='Mueve el acelerador de MIN a MAX y suéltalo...';
  // 10 segundos capturando TPS_10Bit min/max
  const DURATION_MS=10000; const START=Date.now();
  let capMin=9999, capMax=0;
  const iv=setInterval(async()=>{
    const elapsed=Date.now()-START;
    prog.style.width=Math.min(100,elapsed/DURATION_MS*100)+'%';
    try{
      const d=await(await fetch('/live.json?t='+Date.now())).json();
      const raw=d.live&&d.live.TPS_10Bit!=null ? d.live.TPS_10Bit : null;
      if(raw!=null){ capMin=Math.min(capMin,raw); capMax=Math.max(capMax,raw); }
      msg.textContent=`Capturando... MIN=${capMin===9999?'--':capMin}  MAX=${capMax}`;
    }catch(e){}
    if(elapsed>=DURATION_MS){
      clearInterval(iv);
      bar.style.display='none';
      btn.disabled=false; _tpsCaptureActive=false;
      if(capMin<capMax-20){
        document.getElementById('tpsMin').value=capMin;
        document.getElementById('tpsMax').value=capMax;
        st.textContent=`Capturado: MIN=${capMin} MAX=${capMax} — presiona Guardar`;
        st.style.color='#a8f';
      } else {
        st.textContent='Captura inválida — rango muy pequeño, intenta de nuevo';
        st.style.color='var(--accent)';
        setTimeout(()=>st.textContent='',3000);
      }
    }
  },500);
}

loadTpsCal();

// cargar cal al arrancar (no solo al abrir tab)
document.addEventListener("DOMContentLoaded", ()=>{ loadTpsCal(); loadVssCal(); buildGrid(); fetchLive(); });
</script>
</body>
</html>

"""
""

class LiveHandler(BaseHTTPRequestHandler):
    """Handler HTTP minimalista. state viene del LiveDashboard."""
    dashboard = None  # referencia al LiveDashboard, se asigna antes de arrancar

    def log_message(self, *a): pass  # silenciar logs

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith('/live.json'):
            data = self.dashboard.get_live_json()
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Access-Control-Allow-Origin','*')
            self.send_header('Cache-Control','no-cache, no-store, must-revalidate')
            self.send_header('Pragma','no-cache')
            self.send_header('Expires','0')
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith('/eeprom'):
            self._json(self.dashboard.eeprom_params)
        elif self.path.startswith('/maps'):
            self._json(self.dashboard.eeprom_maps)
        elif self.path.startswith('/errorlog'):
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            session  = qs.get('session',[''])[0]
            ride_num = int(qs.get('ride',['0'])[0])
            el_path  = Path(self.dashboard._sessions_dir)/session/f"ride_{ride_num:03d}_errorlog.json"
            if el_path.exists():
                with open(el_path) as _f:
                    self._json(json.load(_f))
            else:
                self._json({"error": "Sin errorlog — ride limpio"})
        elif self.path.startswith('/wifi/saved'):
            self._json({"saved": NetworkManager.saved_wifi()})
        elif self.path.startswith('/rides'):
            rides = self.dashboard.get_rides(self.dashboard._sessions_dir)
            self._json({"rides": rides})
        elif self.path.startswith('/usage_stats'):
            self._json(self.dashboard.usage_stats)
        elif self.path.startswith('/ride_note'):
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            session = qs.get('session',[''])[0]
            ride_num = int(qs.get('ride',['0'])[0])
            note_path = Path(self.dashboard._sessions_dir)/session/f"ride_{ride_num:03d}_notes.txt"
            note = note_path.read_text(encoding='utf-8') if note_path.exists() else ''
            self._json({'note': note})
        elif self.path.startswith('/csv/'):
            # fname puede ser ride_NNN_summary.json o ride_NNN.csv
            fname = self.path.split('/csv/')[-1].split('?')[0]
            rides = self.dashboard.get_rides(self.dashboard._sessions_dir)
            # Aceptar tanto ride_019.csv como ride_019_summary.json
            fname_summary = fname.replace(".csv","_summary.json")
            match = next((r for r in rides
                          if r["filename"]==fname or r["filename"]==fname_summary), None)
            if match:
                try:
                    sessions_path = Path(self.dashboard._sessions_dir)
                    sdir = sessions_path / match["session"]
                    ride_num = match.get("ride_num",0)
                    parts = match.get("parts",1)
                    # Concatenar todas las partes en memoria
                    chunks = []
                    first = True
                    for part in range(1, parts+1):
                        suffix = f"_p{part}" if part > 1 else ""
                        csv_path = sdir/f"ride_{ride_num:03d}{suffix}.csv"
                        if not csv_path.exists(): continue
                        with open(csv_path,'rb') as f:
                            if not first:
                                f.readline()  # Saltar header en partes 2+
                            chunks.append(f.read())
                        first = False
                    raw = b''.join(chunks)
                    # Gzip si el cliente lo soporta — reduce 5-10x en WiFi
                    accept_enc = self.headers.get('Accept-Encoding','')
                    use_gzip = 'gzip' in accept_enc
                    body = zlib.compress(raw, level=6, wbits=31) if use_gzip else raw
                    self.send_response(200)
                    self.send_header('Content-Type','text/csv; charset=utf-8')
                    self.send_header('Access-Control-Allow-Origin','*')
                    self.send_header('Cache-Control','no-store')
                    self.send_header('Content-Length', str(len(body)))
                    if use_gzip:
                        self.send_header('Content-Encoding','gzip')
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as e:
                    pass
            else:
                self._json({"error":"not found"}, 404)
        elif self.path.startswith('/ride/'):
            fname = self.path.split('/ride/')[-1].split('?')[0]
            rides = self.dashboard.get_rides(self.dashboard._sessions_dir)
            # Aceptar tanto ride_019.csv como ride_019_summary.json
            fname_summary = fname.replace(".csv","_summary.json")
            match = next((r for r in rides
                          if r["filename"]==fname or r["filename"]==fname_summary), None)
            if match:
                # Buscar el archivo real (summary JSON o CSV)
                sessions_path = Path(self.dashboard._sessions_dir)
                sdir = sessions_path / match["session"]
                fpath = sdir / fname
                if not fpath.exists():
                    # Buscar CSV base para rides viejos
                    fpath = sdir / fname.replace("_summary.json",".csv")
                summary = self.dashboard.get_ride_summary(
                    str(fpath), self.dashboard.objectives)
                self._json(summary)
            else:
                self._json({"error":"not found"}, 404)
        else:
            html = DASHBOARD_HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html)

    def do_POST(self):
        length = int(self.headers.get('Content-Length',0))
        body   = self.rfile.read(length) if length else b''
        try:
            payload = json.loads(body)
        except Exception as _json_err:
            if body:
                logging.getLogger("HTTP").warning(
                    f"POST {self.path}: JSON inválido ({_json_err}) — body={body[:80]!r}")
            payload = {}
        if self.path == '/ve':
            self.dashboard.save_ve_tables(payload)
            self._json({"ok":True})
        elif self.path == '/obj':
            self.dashboard.save_objectives(payload)
            self._json({"ok":True})
        elif self.path == '/network':
            action = payload.get("action","")
            if action == "wifi":
                NetworkManager.switch_to_wifi()
            elif action == "hotspot":
                NetworkManager.switch_to_hotspot()
            self._json({"ok":True,"action":action})
        elif self.path == '/wifi/scan':
            networks = NetworkManager.scan_wifi()
            self._json({"networks": networks})
        elif self.path == '/wifi/saved':
            saved = NetworkManager.saved_wifi()
            self._json({"saved": saved})
        elif self.path == '/wifi/connect':
            profile = payload.get("profile","")
            if profile:
                NetworkManager.connect_to_profile(profile)
                self._json({"ok":True})
            else:
                self._json({"ok":False,"error":"sin perfil"})
        elif self.path == '/wifi/add':
            ssid = payload.get("ssid","")
            password = payload.get("password","")
            if ssid and password:
                NetworkManager.add_and_connect(ssid, password)
                self._json({"ok":True})
            else:
                self._json({"ok":False,"error":"ssid o password faltante"})
        elif self.path == '/wifi/forget':
            name = payload.get("name","")
            ok = NetworkManager.forget_wifi(name) if name else False
            self._json({"ok":ok})
        elif self.path == '/keepalive':
            # Rate limiting: acepta máximo 1 keepalive cada 10s por servidor
            now = time.monotonic()
            last = getattr(LiveHandler, '_last_keepalive_ts', 0.0)
            if now - last >= 10.0:
                LiveHandler._last_keepalive_ts = now
                self.dashboard.keepalive()
            self._json({"ok":True})
        elif self.path == '/shutdown':
            self.dashboard.request_shutdown()
            self._json({"ok":True,"msg":"Apagando en 3s..."})
        elif self.path == '/tps_cal':
            self.dashboard.tps_cal = payload
            cal_path = os.path.join(self.dashboard.buell_dir,'tps_cal.json')
            with open(cal_path,'w') as _f: json.dump(payload,_f)
            self._json({'ok':True})
        elif self.path == '/reconnect':
            # Funciona tanto en waiting_loop como en reading_loop
            bl = getattr(self.dashboard, '_buell_logger_ref', None)
            if bl:
                bl._force_reconnect = True
                # Si hay ride activo, cerrarlo para salir del reading_loop a waiting
                if bl._ride_active:
                    bl._ride_active = False
                    bl._ecu_lost_since = None
                    bl._flush_ride(
                        "Reconexión forzada por usuario",
                        tracker_snap = bl.tracker.snapshot(),
                        objectives   = bl.dashboard.objectives,
                        dtc          = list(bl._dtc_log))
                    bl._dtc_log.clear()
            self._json({'ok': True, 'msg': 'Reconexión solicitada'})
        elif self.path == '/restart_logger':
            self._json({'ok': True, 'msg': 'Reiniciando logger...'})
            threading.Thread(target=lambda: (time.sleep(1),
                subprocess.run(['sudo','systemctl','restart','buell-logger'])),
                daemon=True).start()
        elif self.path == '/reboot_pi':
            self._json({'ok': True, 'msg': 'Reiniciando Pi...'})
            threading.Thread(target=lambda: (time.sleep(1),
                subprocess.run(['sudo','reboot'])),
                daemon=True).start()
        elif self.path == '/close_ride':
            bl = getattr(self.dashboard, '_buell_logger_ref', None)
            if bl and bl._ride_active:
                closed_session = bl.session.current_checksum
                closed_ride_num = bl.session.current_ride_num
                bl._ride_active = False
                bl._ecu_lost_since = None
                bl._flush_ride(
                    "Cerrado por usuario",
                    tracker_snap = bl.tracker.snapshot(),
                    objectives   = bl.dashboard.objectives,
                    dtc          = list(bl._dtc_log))
                bl._dtc_log.clear()
                self._json({'ok': True, 'msg': 'Ride cerrado',
                            'session': closed_session,
                            'ride_num': closed_ride_num})
            else:
                self._json({'ok': False, 'msg': 'Sin ride activo'})
        elif self.path == '/usage':
            action = payload.get('action','')
            if action and action != '__clear__':
                stats = self.dashboard.usage_stats
                stats[action] = stats.get(action, 0) + 1
                stats['last_updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
                self.dashboard._save_json('usage_stats.json', stats)
            self._json({'ok': True})
        elif self.path == '/usage_clear':
            self.dashboard.usage_stats = {}
            self.dashboard._save_json('usage_stats.json', {})
            self._json({'ok': True})
        elif self.path == '/ride_note':
            session = payload.get('session','')
            ride_num = int(payload.get('ride_num',0))
            note = payload.get('note','')
            try:
                note_path = Path(self.dashboard._sessions_dir)/session/f"ride_{ride_num:03d}_notes.txt"
                note_path.write_text(note, encoding='utf-8')
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif self.path == '/vss_cal':
            cpkm = float(payload.get('cpkm25',1368))
            self.dashboard.vss_cal = {'cpkm25':cpkm}
            # Actualizar factor global para nuevas muestras en vivo
            import sys
            sys.modules[__name__].VSS_CPKM25 = cpkm
            cal_path = os.path.join(self.dashboard.buell_dir,'vss_cal.json')
            with open(cal_path,'w') as _f: json.dump({'cpkm25':cpkm},_f)
            self._json({'ok':True,'cpkm25':cpkm})
                elif self.path == '/git_pull':
            try:
                result = subprocess.run(
                    ['git', 'pull'],
                    cwd='/home/pi/buell',
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                output = result.stdout + result.stderr
                changes = 'Already up to date' not in output
                self._json({'ok': result.returncode == 0, 'output': output, 'changes': changes})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
        else:
            self._json({"error":"unknown endpoint"},404)
             
         try:
             result = subprocess.run(
                 ['git', 'pull'],
                 cwd='/home/pi/buell',
                 capture_output=True,
                 text=True,
                 timeout=30
             )
             output = result.stdout + result.stderr
             changes = 'Already up to date' not in output
             self._json({'ok': result.returncode == 0, 'output': output, 'changes': changes})
         except Exception as e:
             self._json({'ok': False, 'error': str(e)})
           
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()


class LiveDashboard:
    PORT = 8080

    def __init__(self, buell_dir, tracker):
        self.buell_dir    = Path(buell_dir)
        self.tracker      = tracker
        self.logger       = logging.getLogger("Dashboard")
        self._lock        = threading.Lock()
        self._state       = {"logger_version": LOGGER_VERSION}
        self.ve_tables    = self._load_json("ve_tables.json", {})
        self.objectives   = self._load_json("objectives.json", self._default_objectives())
        self._server         = None
        self._keepalive_ts   = 0.0   # último keepalive del browser
        self._pending_shutdown = False
        self.tps_cal         = self._load_json("tps_cal.json", {"min":139,"max":479})
        self.vss_cal         = self._load_json("vss_cal.json", {"cpkm25":1368})
        self.eeprom_params   = self._load_json("eeprom_snapshot.json", {})
        self.eeprom_maps     = {}   # poblado cuando se lee EEPROM completo
        self.usage_stats     = self._load_json("usage_stats.json", {})

    def _load_json(self, name, default):
        p = self.buell_dir / name
        if p.exists():
            try:
                with open(p) as f: return json.load(f)
            except Exception: pass
        return default

    def _save_json(self, name, data):
        p  = self.buell_dir / name
        tmp = p.with_suffix('.tmp')
        with open(tmp,'w') as f: json.dump(data, f, indent=2)
        tmp.replace(p)

    def _default_objectives(self):
        return {
            "cell_targets": [
                {"label":"Zona media (2900-4000, Load 40-80)","rpm_min":2900,"rpm_max":4000,"load_min":40,"load_max":80,"seconds":10},
                {"label":"WOT media (2900-4000, Load 80+)","rpm_min":2900,"rpm_max":4000,"load_min":80,"load_max":255,"seconds":5}
            ],
            "indicators": {"max_cht":250,"min_duration_s":300}
        }

    def save_ve_tables(self, payload):
        self.ve_tables = payload
        self._save_json("ve_tables.json", payload)
        self.logger.info("Tablas VE guardadas desde browser")

    def save_objectives(self, payload):
        self.objectives = payload
        self._save_json("objectives.json", payload)
        self.logger.info("Objetivos actualizados desde browser")

    def update_state(self, ride_active, ride_num, elapsed_s, live_data):
        """Llamado desde el reading loop del logger, ~1Hz."""
        cells, active_cell = self.tracker.snapshot()
        obj_cfg = self.objectives

        # Evaluar objetivos
        objectives_out = []
        for ct in obj_cfg.get("cell_targets", []):
            rpm_min  = ct.get("rpm_min",0);    rpm_max  = ct.get("rpm_max",9999)
            load_min = ct.get("load_min",0);   load_max = ct.get("load_max",255)
            target_s = ct.get("seconds",5)
            matching = []
            for ri, r in enumerate(RPM_BINS):
                for li, l in enumerate(LOAD_BINS):
                    if rpm_min<=r<=rpm_max and load_min<=l<=load_max:
                        matching.append(f"{r}_{l}")
            done = sum(1 for k in matching if cells.get(k,{}).get("seconds",0)>=target_s)
            pct  = (done/len(matching)*100) if matching else 0
            objectives_out.append({
                "label":ct.get("label",f"RPM {rpm_min}-{rpm_max} Load {load_min}-{load_max}"),
                "target_s":target_s,"done_cells":done,"total_cells":len(matching),"pct":pct
            })

        # Indicadores
        ind_cfg = obj_cfg.get("indicators", {})
        cht_now = live_data.get("CLT",0) or 0
        ind_out = {}
        if "max_cht" in ind_cfg:
            ind_out["max_cht"] = {"limit":ind_cfg["max_cht"],"actual":cht_now,
                                   "ok":cht_now<=ind_cfg["max_cht"]}
        if "min_duration_s" in ind_cfg:
            ind_out["min_duration"] = {"limit":ind_cfg["min_duration_s"],"actual":elapsed_s,
                                        "ok":elapsed_s>=ind_cfg["min_duration_s"]}

        with self._lock:
            self._state = {
                "ts":           datetime.now(timezone.utc).isoformat(),
                "ride_active":  ride_active,
                "waiting":       not ride_active,
                "ride_num":     ride_num,
                "elapsed_s":    round(elapsed_s, 1),
                "live":         {k: round(v,3) if isinstance(v,float) else v
                                 for k,v in live_data.items() if v is not None},
                "active_cell":  active_cell,
                "cells":        cells,
                "objectives":   objectives_out,
                "raw_objectives": obj_cfg,
                "indicators":   ind_out,
                "network_mode": NetworkManager.current_mode(),
                "ecu_connected": getattr(getattr(self,"_buell_logger_ref",None),"_ecu_lost_since",None) is None,
                "ecu_lost_s":   round(time.monotonic() - getattr(getattr(self,"_buell_logger_ref",None),"_ecu_lost_since", time.monotonic()),1) if getattr(getattr(self,"_buell_logger_ref",None),"_ecu_lost_since",None) else 0,
                "tps_cal":    self.tps_cal,
                "vss_cal":    self.vss_cal,
                "logger_version": LOGGER_VERSION,
                "active_dtcs":  getattr(state_owner,"_active_dtcs",[]) if (state_owner:=getattr(self,"_buell_logger_ref",None)) else [],
                "dtc_log":     (getattr(state_owner,"_dtc_log",[])[-20:]) if (state_owner:=getattr(self,"_buell_logger_ref",None)) else [],
                "ride_errors": (getattr(state_owner,"error_log").counts()
                                if (state_owner:=getattr(self,"_buell_logger_ref",None)) and getattr(state_owner,"_ride_active",False)
                                else {"dirty":0,"timeout":0,"serial":0,"total":0}),
            }

    def get_live_json(self):
        with self._lock:
            return dict(self._state)

    def keepalive(self):
        self._keepalive_ts = time.monotonic()

    def browser_alive(self, window_s=300):
        """True si el browser hizo keepalive en los últimos window_s segundos."""
        return (time.monotonic() - self._keepalive_ts) < window_s

    def request_shutdown(self):
        self._pending_shutdown = True

    def _errorlog_meta(self, session_dir, ride_num):
        """Retorna has_errorlog, errorlog_events, errorlog_summary para un ride."""
        path = Path(session_dir) / f"ride_{ride_num:03d}_errorlog.json"
        if not path.exists():
            return {"has_errorlog": False, "errorlog_events": 0, "errorlog_summary": ""}
        try:
            with open(path) as _f:
                data = json.load(_f)
            s = data.get("summary", {})
            total = s.get("total_events", 0)
            parts = []
            if s.get("serial_exceptions"): parts.append(f"{s['serial_exceptions']}ser")
            if s.get("dirty_bytes"):       parts.append(f"{s['dirty_bytes']}dirty")
            if s.get("ecu_timeouts"):      parts.append(f"{s['ecu_timeouts']}timeout")
            if s.get("ecu_resets"):        parts.append(f"{s['ecu_resets']}reset")
            if s.get("reconnects"):        parts.append(f"{s['reconnects']}reconx")
            return {"has_errorlog": True,
                    "errorlog_events": total,
                    "errorlog_summary": " ".join(parts)}
        except Exception:
            return {"has_errorlog": True, "errorlog_events": "?", "errorlog_summary": "error leyendo"}

    def get_rides(self, sessions_dir):
        """Lista rides usando summary JSON — sin leer CSVs."""
        rides = []
        sessions_path = Path(sessions_dir)
        for session_dir in sorted(sessions_path.iterdir()):
            if not session_dir.is_dir(): continue
            meta_file = session_dir / "session_metadata.json"
            fw = ""
            if meta_file.exists():
                try:
                    with open(meta_file) as _f:
                        fw = json.load(_f).get("version_string","")
                except Exception: pass
            for sf in sorted(session_dir.glob("ride_*_summary.json")):
                try:
                    with open(sf) as _f:
                        summary = json.load(_f)
                    ride_num = summary.get("ride_num",0)
                    note_path = session_dir / f"ride_{ride_num:03d}_notes.txt"
                    has_note = note_path.exists()
                    note_preview = ""
                    if has_note:
                        try:
                            note_preview = note_path.read_text(encoding='utf-8').split('\n')[0][:60]
                        except Exception: pass
                    rides.append({
                        "session":         session_dir.name,
                        "firmware":        fw,
                        "filename":        f"ride_{ride_num:03d}_summary.json",
                        "ride_num":        ride_num,
                        "samples":         summary.get("samples",0),
                        "duration_s":      summary.get("duration_s",0),
                        "parts":           summary.get("parts",1),
                        "close_reason":    summary.get("reason", summary.get("close_reason","")),
                        "opened_utc":      summary.get("opened_utc",""),
                        "closed_utc":      summary.get("closed_utc",""),
                        "has_note":        has_note,
                        "note_preview":    note_preview,
                        "dtc_events":      summary.get("dtc_events",[]),
                        **self._errorlog_meta(session_dir, ride_num),
                    })
                except Exception:
                    pass
            # Fallback: rides sin summary (rides viejos o ride activo)
            summary_nums = set()
            for _sf in session_dir.glob("ride_*_summary.json"):
                try:
                    with open(_sf) as _f:
                        summary_nums.add(json.load(_f).get("ride_num", 0))
                except Exception:
                    pass
            for rf in sorted(session_dir.glob("ride_[0-9]*.csv")):
                try:
                    # Solo incluir si no tiene summary (ride viejo sin summary)
                    rnum = int(rf.stem.split("_")[1])
                    if rnum in summary_nums: continue
                    with open(rf) as f: n = sum(1 for _ in f) - 1
                    rides.append({
                        "session": session_dir.name, "firmware": fw,
                        "filename": rf.name, "ride_num": rnum,
                        "samples": n, "duration_s": 0, "parts": 1,
                    })
                except Exception: pass
        return sorted(rides, key=lambda r: (r["session"], r.get("ride_num",0)))

    def get_ride_summary(self, ride_path, objectives):
        """Carga el summary JSON del ride — sin leer el CSV."""
        # ride_path puede ser la ruta al summary JSON o al CSV
        p = Path(ride_path)
        # Si es summary JSON, cargarlo directo
        if p.suffix == ".json" and "_summary" in p.name:
            try:
                with open(p) as _f:
                    s = json.load(_f)
                return {"cells": s.get("cells",{}), "objectives": s.get("objectives",[])}
            except Exception as e:
                self.logger.warning(f"Error leyendo summary: {e}")
                return {"cells":{}, "objectives":[]}
        # Fallback: buscar summary JSON del mismo ride
        summary_path = p.parent / (p.stem.replace("_p1","").replace("_p2","").replace("_p3","") + "_summary.json")
        if summary_path.exists():
            try:
                with open(summary_path) as _f:
                    s = json.load(_f)
                return {"cells": s.get("cells",{}), "objectives": s.get("objectives",[])}
            except Exception: pass
        # Último recurso: calcular desde CSV (rides viejos sin summary)
        cells = {}
        try:
            import csv as _csv
            with open(ride_path) as _f:
                rows = list(_csv.DictReader(l for l in _f if not l.startswith('#')))
            dt = 1.0/8.0
            for row in rows:
                try:
                    rpm=float(row.get("RPM",0) or 0); load=float(row.get("Load",0) or 0)
                    ego=float(row.get("EGO_Corr",100) or 100)
                    if rpm<300: continue
                    key=f"{find_bin(rpm,RPM_BINS)}_{find_bin(load,LOAD_BINS)}"
                    c=cells.setdefault(key,{"seconds":0.0,"ego_sum":0.0,"count":0})
                    c["seconds"]+=dt; c["ego_sum"]+=ego; c["count"]+=1
                except Exception: pass
        except Exception as e:
            self.logger.warning(f"get_ride_summary fallback: {e}")
        cells_out={k:{"seconds":round(v["seconds"],1),
                      "ego_avg":round(v["ego_sum"]/v["count"],1) if v["count"] else 100.0}
                   for k,v in cells.items()}
        objectives_out=[]
        for ct in objectives.get("cell_targets",[]):
            matching=[f"{r}_{l}" for r in RPM_BINS for l in LOAD_BINS
                      if ct.get("rpm_min",0)<=r<=ct.get("rpm_max",9999)
                      and ct.get("load_min",0)<=l<=ct.get("load_max",255)]
            done=sum(1 for k in matching if cells_out.get(k,{}).get("seconds",0)>=ct.get("seconds",5))
            pct=(done/len(matching)*100) if matching else 0
            objectives_out.append({"label":ct.get("label",""),"target_s":ct.get("seconds",5),
                                   "done_cells":done,"total_cells":len(matching),"pct":round(pct,1)})
        return {"cells":cells_out,"objectives":objectives_out}

    def start(self, sessions_dir):
        self._sessions_dir = sessions_dir
        LiveHandler.dashboard = self
        self._server = ThreadingHTTPServer(('0.0.0.0', self.PORT), LiveHandler)
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()
        NetworkManager.start_monitor()
        self.logger.info(f"Dashboard en http://10.42.0.1:{self.PORT}")

    def stop(self):
        if self._server:
            self._server.shutdown()

# ─────────────────────────────────────────────────────────────────
# CONECTIVIDAD  R16-R18
# ─────────────────────────────────────────────────────────────────
class NetworkManager:
    HOTSPOT_CON    = "buell-hotspot"
    WIFI_TIMEOUT_S = 60
    logger         = logging.getLogger("Network")
  
    @classmethod
    def ensure_hotspot(cls):
        """Crea el perfil buell-hotspot si no existe."""
        ok, out = cls._run(["nmcli", "con", "show", cls.HOTSPOT_CON])
        if ok:
            cls.logger.debug("Perfil hotspot ya existe")
            return True
        # No existe, crearlo
        cls.logger.info("Creando perfil hotspot...")
        # Generar un SSID único basado en algo (ej. hostname)
        ssid = f"buell-{socket.gethostname()[-4:]}"
        password = "buell2024"
        cmd = [
            "sudo", "nmcli", "con", "add", "type", "wifi",
            "ifname", "wlan0", "mode", "ap",
            "con-name", cls.HOTSPOT_CON,
            "ssid", ssid,
            "password", password
        ]
        ok, out = cls._run(cmd, timeout=20)
        if not ok:
            cls.logger.error("No se pudo crear el perfil hotspot")
            return False
        # Configurar banda y método IP
        cls._run(["sudo", "nmcli", "con", "modify", cls.HOTSPOT_CON, "802-11-wireless.band", "bg"])
        cls._run(["sudo", "nmcli", "con", "modify", cls.HOTSPOT_CON, "ipv4.method", "shared"])
        cls.logger.info(f"Hotspot creado: SSID={ssid} pass={password}")
        return True

    @staticmethod
    def _run(cmd, timeout=10):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode==0, r.stdout.strip()
        except Exception: return False,""

    @classmethod
    def _wifi_connected(cls):
        ok,out = cls._run(["nmcli","-t","-f","DEVICE,TYPE,STATE,CONNECTION","dev","status"])
        if not ok: return False
        for line in out.splitlines():
            p = line.split(":")
            if len(p)>=4 and p[0]=="wlan0" and p[1]=="wifi" and p[2]=="connected" and p[3]!=cls.HOTSPOT_CON:
                return True
        return False

    @classmethod
    def _hotspot_active(cls):
        ok,out = cls._run(["nmcli","-t","-f","NAME,STATE","con","show","--active"])
        return ok and cls.HOTSPOT_CON in out

    @classmethod
    def setup(cls):
        """Configura red al arrancar: crea hotspot si no hay WiFi, o deja WiFi si existe."""
        cls.ensure_hotspot()  # Asegurar que el perfil hotspot existe
        
        # Si ya hay WiFi conectado, dejarlo así
        if cls._wifi_connected():
            cls.logger.info("WiFi ya conectado — manteniendo")
            return
            
        # Si el hotspot ya está activo, todo bien
        if cls._hotspot_active():
            cls.logger.info("Hotspot ya activo")
            return
            
        # Intentar activar hotspot (modo por defecto seguro)
        cls.logger.info("Activando hotspot por defecto...")
        ok, _ = cls._run(["sudo", "nmcli", "con", "up", cls.HOTSPOT_CON], timeout=15)
        if ok:
            cls.logger.info("Hotspot activo: SSID=buell-XXXX pass=buell2024")
        else:
            cls.logger.error("No se pudo activar hotspot — revisar nmcli")
          
    @classmethod
    def ssh_active(cls):
        ok,out = cls._run(["ss","-tn","state","established","sport","=",":22"])
        if not ok: return False
        return any(l.strip() and not l.startswith("Recv") for l in out.splitlines())

    @classmethod
    def current_mode(cls):
        """Retorna 'wifi', 'hotspot' o 'none'."""
        if cls._wifi_connected():  return "wifi"
        if cls._hotspot_active():  return "hotspot"
        return "none"

    @classmethod
    def switch_to_wifi(cls):
        """Baja hotspot y conecta al perfil WiFi guardado explícitamente."""
        def _do():
            cls.logger.info("Browser: cambio a WiFi solicitado")
            if cls._hotspot_active():
                cls._run(["sudo","nmcli","con","down",cls.HOTSPOT_CON])
                time.sleep(2)
            cls._run(["sudo","nmcli","con","up","casa"], timeout=35)
            time.sleep(4)
            if cls._wifi_connected():
                cls.logger.info("Conectado a WiFi OK")
            else:
                cls.logger.info("No se encontró WiFi — regresando a hotspot")
                cls._run(["sudo","nmcli","con","up",cls.HOTSPOT_CON])
        threading.Thread(target=_do, daemon=True).start()

    @classmethod
    def switch_to_hotspot(cls):
        """Baja WiFi y activa hotspot."""
        def _do():
            cls.logger.info("Browser: cambio a hotspot solicitado")
            if cls._wifi_connected():
                cls._run(["sudo","nmcli","dev","disconnect","wlan0"])
                time.sleep(1)
            cls._run(["sudo","nmcli","con","up",cls.HOTSPOT_CON])
            cls.logger.info("Hotspot activo")
        threading.Thread(target=_do, daemon=True).start()

    @classmethod
    def connect_to_profile(cls, profile_name):
        """Conecta a un perfil NM guardado por nombre."""
        def _do():
            cls.logger.info(f"Conectando a perfil: {profile_name}")
            if cls._hotspot_active():
                cls._run(["sudo","nmcli","con","down",cls.HOTSPOT_CON])
                time.sleep(2)
            cls._run(["sudo","nmcli","con","up", profile_name], timeout=35)
            time.sleep(4)
            if cls._wifi_connected():
                cls.logger.info(f"Conectado a {profile_name} OK")
            else:
                cls.logger.warning(f"No conectó a {profile_name} — regresando a hotspot")
                cls._run(["sudo","nmcli","con","up",cls.HOTSPOT_CON])
        threading.Thread(target=_do, daemon=True).start()

    @classmethod
    def add_and_connect(cls, ssid, password):
        """Agrega perfil nuevo y conecta."""
        def _do():
            cls.logger.info(f"Agregando red: {ssid}")
            if cls._hotspot_active():
                cls._run(["sudo","nmcli","con","down",cls.HOTSPOT_CON])
                time.sleep(2)
            cls._run(["sudo","nmcli","dev","wifi","rescan"], timeout=8)
            time.sleep(2)
            ok,out = cls._run(["sudo","nmcli","dev","wifi","connect", ssid,
                               "password", password], timeout=35)
            time.sleep(4)
            if cls._wifi_connected():
                cls.logger.info(f"Red {ssid} agregada y conectada OK")
            else:
                cls.logger.warning(f"No conectó a {ssid} — regresando a hotspot")
                cls._run(["sudo","nmcli","con","up",cls.HOTSPOT_CON])
        threading.Thread(target=_do, daemon=True).start()

    @classmethod
    def scan_wifi(cls):
        """Escanea redes disponibles."""
        cls._run(["sudo","nmcli","dev","wifi","rescan"], timeout=8)
        ok, out = cls._run(["nmcli","--terse","--fields","SSID,SIGNAL,SECURITY",
                             "dev","wifi","list"], timeout=8)
        networks, seen = [], set()
        if ok:
            for line in out.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 2:
                    ssid = parts[0].strip()
                    if not ssid or ssid in seen or ssid == "buell-logger": continue
                    seen.add(ssid)
                    try: signal = int(parts[1].strip())
                    except: signal = 0
                    security = parts[2].strip() if len(parts) > 2 else ""
                    networks.append({"ssid":ssid,"signal":signal,"security":security})
        networks.sort(key=lambda x: -x["signal"])
        return networks

    @classmethod
    def saved_wifi(cls):
        """Lista perfiles WiFi guardados con su SSID."""
        ok, out = cls._run(["nmcli","--terse","--fields","NAME,TYPE","con","show"], timeout=8)
        saved = []
        if ok:
            for line in out.strip().splitlines():
                parts = line.split(":")
                if len(parts)>=2 and "wifi" in parts[1].lower():
                    name = parts[0].strip()
                    if name == cls.HOTSPOT_CON: continue
                    ok2,out2 = cls._run(["nmcli","--terse","--fields",
                                         "802-11-wireless.ssid","con","show",name], timeout=5)
                    ssid = out2.split(":")[-1].strip() if ok2 and ":" in out2 else name
                    saved.append({"name":name,"ssid":ssid})
        return saved

    @classmethod
    def forget_wifi(cls, name):
        """Elimina un perfil guardado."""
        ok, _ = cls._run(["sudo","nmcli","con","delete", name], timeout=10)
        return ok

    @classmethod
    def start_monitor(cls):
        """Thread que vigila la conexión cada 30s y activa hotspot si se cae el WiFi."""
        def _monitor():
            time.sleep(90)  # esperar arranque completo
            while True:
                try:
                    if not cls._wifi_connected() and not cls._hotspot_active():
                        cls.logger.warning("Sin red — activando hotspot automático")
                        cls._run(["sudo","nmcli","con","up",cls.HOTSPOT_CON])
                except Exception as e:
                    cls.logger.debug(f"monitor: {e}")
                time.sleep(30)
        threading.Thread(target=_monitor, daemon=True, name="net-monitor").start()
        cls.logger.info("Monitor de red iniciado (intervalo 30s)")

# ─────────────────────────────────────────────────────────────────
# SERIAL
# ─────────────────────────────────────────────────────────────────
class DDFI2Connection:
    def __init__(self, port):
        self.port=port; self.ser=None; self.logger=logging.getLogger("DDFI2")

    def connect(self):
        deadline = time.time()+15.0
        while not os.path.exists(self.port):
            if time.time()>deadline: raise serial.SerialException(f"{self.port} no aparece")
            time.sleep(0.5)
        self.ser = serial.Serial(port=self.port,baudrate=9600,bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_ONE,timeout=1.0,
            xonxoff=False,rtscts=False,dsrdtr=False)
        # Toggle DTR para resetear estado serial de la ECU (igual que reboot Pi)
        self.ser.dtr = False; time.sleep(0.05)
        self.ser.dtr = True;  time.sleep(0.2)
        self.ser.reset_input_buffer(); self.ser.reset_output_buffer()
        time.sleep(0.1)  # settle
        # Intentar bajar latency timer FT232RL de 16ms → 2ms via sysfs
        try:
            import glob as _g
            _lt_paths = _g.glob('/sys/bus/usb-serial/devices/ttyUSB*/latency_timer')
            if not _lt_paths:
                _lt_paths = _g.glob('/sys/bus/usb/drivers/ftdi_sio/*/latency_timer')
            if _lt_paths:
                with open(_lt_paths[0], 'w') as _f: _f.write('2')
                self.logger.info(f"Latency timer FT232RL → 2ms ({_lt_paths[0]})")
        except Exception as _e:
            self.logger.debug(f"Latency timer no configurable: {_e}")
        self.logger.info(f"Puerto serial abierto: {self.port}")

    def disconnect(self):
        try:
            if self.ser and self.ser.is_open: self.ser.close()
        except Exception: pass

    def usb_reset(self):
        """Fuerza un reset USB del FT232RL via sysfs (authorized toggle).
        Necesario cuando el chip queda en estado hung y DTR toggle no alcanza.
        Retorna True si el device fue reseteado, False si no se encontró."""
        import glob as _glob
        try:
            for path in _glob.glob('/sys/bus/usb/devices/*/idVendor'):
                vendor = open(path).read().strip()
                product = open(path.replace('idVendor','idProduct')).read().strip()
                if vendor == '0403' and product == '6001':
                    auth = path.replace('idVendor','authorized')
                    open(auth,'w').write('0')
                    time.sleep(0.8)
                    open(auth,'w').write('1')
                    time.sleep(2.0)   # esperar re-enumeración
                    self.logger.info("USB reset FT232RL completado via sysfs")
                    return True
            self.logger.warning("USB reset: FT232RL (0403:6001) no encontrado en sysfs")
            return False
        except Exception as e:
            self.logger.warning(f"USB reset falló: {e}")
            return False

    def _send(self,pdu): self.ser.reset_input_buffer(); self.ser.write(pdu); self.ser.flush()

    def _read_exact(self,n,timeout_s=1.0):
        buf=bytearray(); deadline=time.time()+timeout_s
        while len(buf)<n:
            rem=deadline-time.time()
            if rem<=0: raise TimeoutError(f"{len(buf)}/{n}")
            self.ser.timeout=min(rem,0.1)
            chunk=self.ser.read(n-len(buf))
            if chunk: buf.extend(chunk)
        return bytes(buf)

    def get_version(self):
        """Reintentar hasta 5 veces con flush — ECU puede estar en modo RT."""
        for attempt in range(5):
            try:
                self.ser.reset_input_buffer(); self.ser.reset_output_buffer()
                self._send(PDU_VERSION); h=self._read_exact(6,2.0)
                if h[0]!=SOH:
                    self.logger.debug(f"get_version intento {attempt+1}: byte0=0x{h[0]:02x}, flush+retry")
                    time.sleep(0.3); continue
                rest=self._read_exact(h[3]-1+2,2.0); full=h+rest
                if full[6]!=ACK: time.sleep(0.3); continue
                ver = full[7:-2].decode("ascii",errors="replace").strip()
                if ver: return ver
            except Exception as e:
                self.logger.debug(f"get_version intento {attempt+1}: {e}")
                time.sleep(0.3)
        return None

    def _sync_to_soh(self, timeout_s=0.5):
        """Descarta basura del buffer hasta encontrar SOH (0x01)."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            self.ser.timeout = 0.05
            b = self.ser.read(1)
            if b and b[0] == SOH:
                return True
        return False

    def _flush_and_retry_soh(self, timeout_s=0.4):
        """Segundo intento: vacía el buffer, reenvía PDU_RT_DATA y busca SOH."""
        try:
            self.ser.reset_input_buffer()
            self._send(PDU_RT_DATA)
            return self._sync_to_soh(timeout_s)
        except Exception:
            return False

    def get_rt_data(self):
        self.last_dirty_byte = None   # reset — None = sin bytes sucios este ciclo
        try:
            self._send(PDU_RT_DATA)
            # Leer primer byte — si no es SOH hay basura en el buffer
            self.ser.timeout = 0.3
            first = self.ser.read(1)
            if not first: return None
            if first[0] != SOH:
                self.last_dirty_byte = f"0x{first[0]:02x}"
                self.logger.debug(f"get_rt: byte0={self.last_dirty_byte} — sincronizando SOH")
                recovered = self._sync_to_soh()
                if not recovered:
                    # Segundo intento: vaciar buffer + reenviar PDU y buscar SOH
                    recovered = self._flush_and_retry_soh()
                    if not recovered: return None
                # Ya tenemos SOH, leer el resto
                raw = bytes([SOH]) + self._read_exact(RT_RESPONSE_SIZE - 1, 0.3)
            else:
                raw = first + self._read_exact(RT_RESPONSE_SIZE - 1, 0.3)
            return decode_rt_packet(raw)
        except TimeoutError: return None
        except Exception as e: self.logger.debug(f"get_rt: {e}"); return None

    def read_eeprom_page(self,page_nr,offset,length):
        try:
            payload=bytes([CMD_GET,offset&0xFF,page_nr&0xFF,length&0xFF])
            self._send(build_pdu(payload)); h=self._read_exact(6,2.0)
            if h[0]!=SOH or h[4]!=EOH or h[5]!=SOT: return None
            rest=self._read_exact(h[3]-1+2,2.0); full=h+rest
            return bytes(full[7:-2]) if full[6]==ACK else None
        except Exception as e: self.logger.error(f"eeprom: {e}"); return None

    def read_full_eeprom(self):
        """Lee las 6 páginas del BUEIB/DDFI-2 → 1206 bytes."""
        BUEIB_PAGES = [
            (1, 0,    256),
            (2, 256,  256),
            (3, 512,  158),
            (4, 670,  256),
            (5, 926,  256),
            (6, 1182, 24),
        ]
        eeprom = bytearray(1206)
        try:
            for page_nr, start, length in BUEIB_PAGES:
                i = 0
                while i < length:
                    chunk = min(16, length - i)
                    data = self.read_eeprom_page(page_nr, i, chunk)
                    if data is None:
                        self.logger.error(f"EEPROM: fallo page {page_nr} offset {i}")
                        return None
                    eeprom[start+i : start+i+len(data)] = data
                    i += chunk
                self.logger.debug(f"EEPROM page {page_nr} leida ({length} bytes)")
            # Pagina 0 — 4 bytes especiales al final (0xFC..0xFF)
            for i in range(4):
                d = self.read_eeprom_page(0, 0xFC + i, 1)
                if d and len(d) >= 1:
                    pass  # estos 4 bytes son metadata interna, ignorar
            self.logger.info("EEPROM leida completa (1206 bytes)")
            return bytes(eeprom)
        except Exception as e:
            self.logger.error(f"read_full_eeprom: {e}")
            return None


# ─────────────────────────────────────────────────────────────────
# EEPROM DECODER
# ─────────────────────────────────────────────────────────────────
# Offsets absolutos cat=8 (BUEIB). Formula: val = raw * scale + translate
# Verificados contra BUEIB.eeprom stock (ecmdroid.db category=8)
BUEIB_PARAMS = {
    # Temperatura — proteccion termica
    "KTemp_Fan_On":      (498, 1.0,  50.0, "\u00b0C",  "Fan ON temperatura (key-on)"),
    "KTemp_Fan_Off":     (499, 1.0,  50.0, "\u00b0C",  "Fan OFF temperatura (key-on)"),
    "KTemp_Soft_Hi":     (488, 1.0, 200.0, "\u00b0C",  "Soft limit trigger (EGO baja)"),
    "KTemp_Soft_Lo":     (489, 1.0, 200.0, "\u00b0C",  "Soft limit release"),
    "KTemp_Hard_Hi":     (490, 1.0, 200.0, "\u00b0C",  "Hard limit trigger (corta chispa)"),
    "KTemp_Hard_Lo":     (491, 1.0, 200.0, "\u00b0C",  "Hard limit release"),
    "KTemp_Kill_Hi":     (494, 1.0, 200.0, "\u00b0C",  "Kill limit trigger (apaga motor)"),
    "KTemp_Kill_Lo":     (495, 1.0, 200.0, "\u00b0C",  "Kill limit release"),
    "KTemp_CEL_Flash_Hi":(496, 1.0, 200.0, "\u00b0C",  "CEL encendido temperatura"),
    "KTemp_Fan_KO_On":   (521, 1.0,   0.0, "\u00b0C",  "Fan key-off ON temp"),
    "KTemp_Fan_KO_Off":  (522, 1.0,   0.0, "\u00b0C",  "Fan key-off OFF temp"),
    "KTemp_RPM_Soft":    (485, 50.0, 0.0,  "RPM",       "RPM min para soft limit temp"),
    "KTemp_RPM_Hard":    (487, 50.0, 0.0,  "RPM",       "RPM min para hard limit temp"),
    "KTemp_TP_Soft":     (484, 1.0,  0.0,  "TPS",       "TPS min para soft limit temp"),
    "KTemp_TP_Hard":     (486, 1.0,  0.0,  "TPS",       "TPS min para hard limit temp"),
    # RPM — limites
    "KRPM_Soft_Hi":      (458, 50.0, 0.0,  "RPM",  "RPM soft limit trigger"),
    "KRPM_Soft_Lo":      (459, 50.0, 0.0,  "RPM",  "RPM soft limit release"),
    "KRPM_Hard_Hi":      (460, 50.0, 0.0,  "RPM",  "RPM hard limit trigger"),
    "KRPM_Hard_Lo":      (461, 50.0, 0.0,  "RPM",  "RPM hard limit release"),
    "KRPM_Kill_Hi":      (464, 50.0, 0.0,  "RPM",  "RPM kill limit trigger"),
    "KRPM_Kill_Lo":      (465, 50.0, 0.0,  "RPM",  "RPM kill limit release"),
    # O2 / EGO
    "KO2_Midpoint":      (186, 0.00196, 0.0, "V",   "O2 target voltage"),
    "KO2_Rich":          (187, 0.00196, 0.0, "V",   "O2 rich threshold"),
    "KO2_Lean":          (188, 0.00196, 0.0, "V",   "O2 lean threshold"),
    "KO2_Min_RPM":       (190, 50.0,    0.0, "RPM", "Closed loop min RPM"),
    "KFBFuel_Max":       (379, 0.4,     0.0, "%",   "EGO correction max"),
    "KFBFuel_Min":       (380, 0.4, -102.0,  "%",   "EGO correction min"),
    "KLFuel_Max":        (395, 0.4,     0.0, "%",   "AFV max"),
    "KLFuel_Min":        (396, 0.4, -102.0,  "%",   "AFV min"),
    # TPS
    "KTPS0":             (200, 0.00244, 0.0, "V",   "TPS cerrado voltage"),
    "KTPSV_Range":       (201, 0.00244, 0.0, "V",   "TPS voltage range"),
    # Manufactura
    "KMFG_Year":         (3,   1.0,   0.0, "",    "Anio fabricacion ECM"),
    "KMFG_Day":          (4,   1.0,   0.0, "",    "Dia fabricacion ECM"),
    "KEngineRun":        (6,   50.0,  0.0, "RPM", "RPM minimo motor encendido"),
    "Ride_Counter":      (1,   1.0,   0.0, "",    "Contador de rides"),
}

def decode_eeprom_params(eeprom_bytes):
    """Decodifica parametros del dump EEPROM BUEIB.
    Retorna dict {varname: {val, raw, units, desc}}"""
    if not eeprom_bytes or len(eeprom_bytes) < 600:
        return {}
    result = {}
    for varname, (offset, scale, translate, units, desc) in BUEIB_PARAMS.items():
        if offset >= len(eeprom_bytes):
            continue
        raw = eeprom_bytes[offset]
        val = round(raw * scale + translate, 3)
        result[varname] = {"val": val, "raw": raw, "units": units, "desc": desc}
    return result


def decode_eeprom_maps(eeprom_bytes):
    """Decodifica los 4 mapas principales del EEPROM BUEIB.
    Offsets verificados contra ecmdroid.db cat=8.
    Retorna dict con axes y tables listos para JSON."""
    if not eeprom_bytes or len(eeprom_bytes) < 1206:
        return {}
    import struct

    def read_axis_1b(off, count):
        return [eeprom_bytes[off+i] for i in range(count)]

    def read_axis_2b(off, count):
        return [struct.unpack_from('>H', eeprom_bytes, off+i*2)[0] for i in range(count)]

    def read_map(off, rows, cols, scale):
        table = []
        for r in range(rows):
            row = [round(eeprom_bytes[off + r*cols + c] * scale, 2) for c in range(cols)]
            table.append(row)
        return table

    try:
        return {
            "axes": {
                "spark_load": read_axis_1b(602, 10),   # TPS axis spark (10 valores)
                "spark_rpm":  read_axis_2b(612, 10),   # RPM axis spark (10 valores x2B)
                "fuel_load":  read_axis_1b(632, 12),   # TPS axis fuel  (12 valores)
                "fuel_rpm":   read_axis_2b(644, 13),   # RPM axis fuel  (13 valores x2B)
            },
            "fuel_front":  read_map(870,  12, 13, 1.0),   # 12×13, scale=1
            "fuel_rear":   read_map(1038, 12, 13, 1.0),   # 12×13, scale=1
            "spark_front": read_map(670,  10, 10, 0.25),  # 10×10, scale=0.25 → grados
            "spark_rear":  read_map(770,  10, 10, 0.25),  # 10×10, scale=0.25 → grados
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────
# RIDE ERROR LOG
# ─────────────────────────────────────────────────────────────────
class RideErrorLog:
    """Registra eventos de error durante un ride.
    Solo escribe archivo si ocurrieron eventos — ride limpio = sin archivo.
    Archivo: ride_NNN_errorlog.json junto al CSV del ride.
    """

    def __init__(self):
        self._events = []
        self._ride_num = None
        self._session = None
        self._session_dir = None
        self._opened_utc = None
        self._last_data = {}   # último sample válido para contexto
        self.logger = logging.getLogger("ErrorLog")

    def start(self, ride_num, session_checksum, session_dir):
        self._events = []
        self._ride_num = ride_num
        self._session = session_checksum
        self._session_dir = session_dir
        self._opened_utc = datetime.now(timezone.utc).isoformat()
        self._last_data = {}

    def update_last_sample(self, data):
        """Llamar con cada sample válido para tener contexto en caso de error."""
        if data:
            self._last_data = {
                "rpm":      data.get("RPM"),
                "clt":      data.get("CLT"),
                "tps":      data.get("TPS_pct"),
                "ego":      data.get("EGO_Corr"),
                "afv":      data.get("AFV"),
                "batt":     data.get("Batt_V"),
                "vss":      data.get("VS_KPH"),
                "seconds":  data.get("Seconds"),
                "fl_learn": data.get("fl_learn"),
            }

    def _elapsed(self):
        """Tiempo elapsed actual — se lo pasa el caller."""
        return None  # siempre se pasa explícitamente

    def _event(self, elapsed_s, etype, **kwargs):
        evt = {
            "t":    round(elapsed_s, 2),
            "ts":   datetime.now(timezone.utc).isoformat(),
            "type": etype,
        }
        evt.update(kwargs)
        # Agregar contexto del último sample válido si es relevante
        if self._last_data:
            evt["ctx"] = dict(self._last_data)
        self._events.append(evt)
        self.logger.info(f"[R{self._ride_num:03d} t={elapsed_s:.1f}s] ERROR: {etype} — {kwargs}")

    # ── Tipos de error ────────────────────────────────────────────

    def serial_exception(self, elapsed_s, exc_msg, consecutive_before=0):
        """SerialException — puerto físicamente roto o USB dropout."""
        self._event(elapsed_s, "serial_exception",
                    msg=str(exc_msg)[:120],
                    consecutive_errors_before=consecutive_before)

    def dirty_bytes(self, elapsed_s, byte0_hex, sync_recovered):
        """Primer byte del paquete no es SOH — interferencia eléctrica."""
        self._event(elapsed_s, "dirty_bytes",
                    byte0_hex=byte0_hex,
                    sync_recovered=sync_recovered)

    def bad_checksum(self, elapsed_s, cs_got, cs_expected):
        """Paquete completo recibido pero checksum incorrecto."""
        self._event(elapsed_s, "bad_checksum",
                    cs_got=f"0x{cs_got:02x}",
                    cs_expected=f"0x{cs_expected:02x}")

    def ecu_timeout(self, elapsed_s, lost_s, last_valid_t):
        """ECU dejó de responder — timeout acumulado."""
        self._event(elapsed_s, "ecu_timeout",
                    lost_s=round(lost_s, 1),
                    last_valid_t=round(last_valid_t, 2))

    def ecu_reset(self, elapsed_s, seconds_prev, seconds_now):
        """Contador seconds de la ECU retrocedió — killswitch o reset ECU."""
        self._event(elapsed_s, "ecu_reset",
                    seconds_prev=seconds_prev,
                    seconds_now=seconds_now)

    def reconnect_attempt(self, elapsed_s, trigger, attempt_n, success, time_s):
        """Intento de reconexión — manual o automático."""
        self._event(elapsed_s, "reconnect",
                    trigger=trigger,
                    attempt=attempt_n,
                    success=success,
                    time_s=round(time_s, 1))

    # ── Guardar ───────────────────────────────────────────────────

    def flush(self, closed_utc=None):
        """Escribe el archivo solo si hubo eventos. Retorna path o None."""
        if not self._events or not self._session_dir or self._ride_num is None:
            return None
        try:
            from collections import Counter
            type_counts = Counter(e["type"] for e in self._events)
            payload = {
                "ride_num":   self._ride_num,
                "session":    self._session,
                "opened_utc": self._opened_utc,
                "closed_utc": closed_utc or datetime.now(timezone.utc).isoformat(),
                "events":     self._events,
                "summary": {
                    "total_events":      len(self._events),
                    "serial_exceptions": type_counts.get("serial_exception", 0),
                    "dirty_bytes":       type_counts.get("dirty_bytes", 0),
                    "bad_checksums":     type_counts.get("bad_checksum", 0),
                    "ecu_timeouts":      type_counts.get("ecu_timeout", 0),
                    "ecu_resets":        type_counts.get("ecu_reset", 0),
                    "reconnects":        type_counts.get("reconnect", 0),
                },
            }
            path = Path(self._session_dir) / f"ride_{self._ride_num:03d}_errorlog.json"
            tmp  = path.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(payload, f, indent=2)
            tmp.replace(path)
            self.logger.info(f"ErrorLog guardado: {path.name} ({len(self._events)} eventos)")
            return path
        except Exception as e:
            self.logger.error(f"ErrorLog flush: {e}")
            return None

    def counts(self):
        """Conteo rápido en memoria para live.json — sin I/O de disco."""
        from collections import Counter
        c = Counter(e["type"] for e in self._events)
        return {
            "dirty":   c.get("dirty_bytes", 0),
            "timeout": c.get("ecu_timeout", 0),
            "serial":  c.get("serial_exception", 0),
            "total":   len(self._events),
        }

    def has_events(self):
        return len(self._events) > 0

    def clear(self):
        self._events = []
        self._last_data = {}


# ─────────────────────────────────────────────────────────────────
# SESSION MANAGER
# ─────────────────────────────────────────────────────────────────
class SessionManager:
    def __init__(self, sessions_dir):
        self.sessions_dir=Path(sessions_dir); self.sessions_dir.mkdir(parents=True,exist_ok=True)
        self.logger=logging.getLogger("Session")
        self.current_checksum=None; self.current_session_dir=None
        self.current_ride_num=0; self.current_csv_fh=None
        self.current_writer=None; self.ride_start_time=None
        self.ride_sample_count=0; self.session_metadata={}
        self.last_elapsed_s=0
        self.current_part=1; self.current_part_rows=0
        self.MAX_CSV_ROWS=10000  # ~20 min a 8Hz

    def _checksum(self,v): return hashlib.md5(v.encode()).hexdigest()[:6].upper()

    def _load_or_create(self,cs,version_str):
        sdir=self.sessions_dir/cs; meta_file=sdir/"session_metadata.json"
        if sdir.exists() and meta_file.exists():
            with open(meta_file) as f: meta=json.load(f)
            self.logger.info(f"Sesión existente: {cs} ({meta.get('total_rides',0)} rides)")
        else:
            sdir.mkdir(parents=True,exist_ok=True)
            meta={"checksum":cs,"version_string":version_str,
                  "created_utc":datetime.now(timezone.utc).isoformat(),
                  "total_rides":0,"total_samples":0,"total_runtime_seconds":0,
                  "rpm_min_seen":99999,"rpm_max_seen":0}
            self.logger.info(f"Nueva sesión: {cs} firmware={version_str}")
        return sdir, meta

    def open_session(self,version_str):
        new_cs=self._checksum(version_str)
        if new_cs==self.current_checksum: return
        if self.current_checksum is not None:
            self.logger.info(f"Checksum cambió {self.current_checksum}→{new_cs}")
            self.close_current_ride("cambio de mapa")  # sin tracker — sesión cambió
        self.current_checksum=new_cs
        self.current_session_dir,self.session_metadata=self._load_or_create(new_cs,version_str)
        self.logger.info(f"Sesión activa: {new_cs}")
        self._generate_consolidated()

    def start_ride(self):
        if not self.current_session_dir: raise RuntimeError("Sin sesión")
        self.session_metadata["total_rides"]=self.session_metadata.get("total_rides",0)+1
        self.current_ride_num=self.session_metadata["total_rides"]
        self.current_part=1; self.current_part_rows=0
        self._open_csv_part()
        self.ride_start_time=time.monotonic(); self.ride_sample_count=0
        self._ride_start_utc = datetime.now(timezone.utc).isoformat()
        self._save_metadata()
        self.logger.info(f"Ride {self.current_ride_num:03d} iniciado")

    def _open_csv_part(self):
        """Abre el archivo CSV de la parte actual del ride."""
        suffix = f"_p{self.current_part}" if self.current_part > 1 else ""
        ride_file = self.current_session_dir/f"ride_{self.current_ride_num:03d}{suffix}.csv"
        if self.current_csv_fh:
            self.current_csv_fh.close()
        self.current_csv_fh = open(ride_file,"w",newline="",buffering=1)
        self.current_csv_fh.write(f"# logger={LOGGER_VERSION}\n")
        self.current_writer = csv.DictWriter(self.current_csv_fh,fieldnames=CSV_COLUMNS,extrasaction="ignore")
        self.current_writer.writeheader()
        self.current_part_rows = 0
        if self.current_part > 1:
            self.logger.info(f"Ride {self.current_ride_num:03d} parte {self.current_part} iniciada ({ride_file.name})")

    def write_sample(self,data_dict,wall_time):
        if not self.current_writer: return
        row=dict(data_dict)
        row["ride_num"]=self.current_ride_num
        row["timestamp_iso"]=datetime.fromtimestamp(wall_time,tz=timezone.utc).isoformat()
        row["time_elapsed_s"]=round(time.monotonic()-self.ride_start_time,3)
        self.last_elapsed_s=row["time_elapsed_s"]
        self.current_writer.writerow(row)
        self.ride_sample_count+=1; self.current_part_rows+=1
        rpm=data_dict.get("RPM",0) or 0
        if rpm>self.session_metadata.get("rpm_max_seen",0): self.session_metadata["rpm_max_seen"]=rpm
        if 0<rpm<self.session_metadata.get("rpm_min_seen",99999): self.session_metadata["rpm_min_seen"]=rpm
        # Split CSV si supera el límite
        if self.current_part_rows >= self.MAX_CSV_ROWS:
            self.current_part+=1
            self._open_csv_part()

    def close_current_ride(self,reason="",tracker_snapshot=None,objectives_cfg=None,dtc_log=None):
        if not self.current_csv_fh: return
        dur = self.last_elapsed_s if self.last_elapsed_s else (time.monotonic()-self.ride_start_time if self.ride_start_time else 0)
        self.current_csv_fh.close(); self.current_csv_fh=None; self.current_writer=None
        self.session_metadata["total_samples"]=self.session_metadata.get("total_samples",0)+self.ride_sample_count
        self.session_metadata["total_runtime_seconds"]=self.session_metadata.get("total_runtime_seconds",0)+dur
        self.logger.info(f"Ride {self.current_ride_num:03d} cerrado — {self.ride_sample_count} muestras, {dur:.0f}s, {self.current_part} parte(s)" + (f" ({reason})" if reason else ""))
        # Guardar summary JSON desde el CellTracker (no releer el CSV)
        if tracker_snapshot is not None and self.current_session_dir:
            cells, _ = tracker_snapshot
            # Evaluar objetivos
            objectives_out = []
            for ct in (objectives_cfg or {}).get("cell_targets", []):
                rpm_min=ct.get("rpm_min",0); rpm_max=ct.get("rpm_max",9999)
                load_min=ct.get("load_min",0); load_max=ct.get("load_max",255)
                target_s=ct.get("seconds",5)
                matching=[f"{r}_{l}" for r in RPM_BINS for l in LOAD_BINS
                          if rpm_min<=r<=rpm_max and load_min<=l<=load_max]
                done=sum(1 for k in matching if cells.get(k,{}).get("seconds",0)>=target_s)
                pct=(done/len(matching)*100) if matching else 0
                objectives_out.append({"label":ct.get("label",""),"target_s":target_s,
                                       "done_cells":done,"total_cells":len(matching),"pct":round(pct,1)})
            summary = {
                "ride_num": self.current_ride_num,
                "session":  self.current_checksum,
                "samples":  self.ride_sample_count,
                "parts":    self.current_part,
                "duration_s": round(dur,1),
                "opened_utc": self._ride_start_utc if hasattr(self,'_ride_start_utc') else "",
                "closed_utc": datetime.now(timezone.utc).isoformat(),
                "reason":   reason,
                "cells":    cells,
                "objectives": objectives_out,
                "dtc_events": dtc_log or [],
            }
            sfile = self.current_session_dir/f"ride_{self.current_ride_num:03d}_summary.json"
            try:
                tmp = sfile.with_suffix(".tmp")
                with open(tmp,"w") as f: json.dump(summary,f)
                tmp.replace(sfile)
                self.logger.info(f"Summary guardado: {sfile.name}")
            except Exception as e:
                self.logger.warning(f"Error guardando summary: {e}")
        self._save_metadata(); self._generate_consolidated()

    def _save_metadata(self):
        if not self.current_session_dir: return
        meta_file=self.current_session_dir/"session_metadata.json"
        tmp=meta_file.with_suffix(".tmp")
        with open(tmp,"w") as f: json.dump(self.session_metadata,f,indent=2)
        tmp.replace(meta_file)

    def _generate_consolidated(self):
        if not self.current_session_dir: return
        ride_files=sorted(self.current_session_dir.glob("ride_*.csv"))
        if not ride_files: return
        consolidated=self.current_session_dir/"consolidated.csv"
        tmp=self.current_session_dir/"consolidated.tmp"
        try:
            with open(tmp,"w",newline="") as out_fh:
                writer=None
                for rf in ride_files:
                    with open(rf,newline="") as in_fh:
                        filtered=(l for l in in_fh if not l.startswith('#'))
                        reader=csv.DictReader(filtered)
                        if writer is None:
                            writer=csv.DictWriter(out_fh,fieldnames=reader.fieldnames,extrasaction="ignore")
                            writer.writeheader()
                        for row in reader: writer.writerow(row)
            tmp.replace(consolidated); self.logger.debug("consolidated.csv regenerado")
        except Exception as e: self.logger.warning(f"Error consolidated: {e}")

# ─────────────────────────────────────────────────────────────────
# BUELL LOGGER — MÁQUINA DE ESTADOS
# ─────────────────────────────────────────────────────────────────
class BuellLogger:
    TARGET_LOOP_HZ         = 8.0
    MAX_CONSECUTIVE_ERRORS = 30
    RPM_START_THRESHOLD    = 300
    RPM_STOP_THRESHOLD     = 100
    STOP_CONFIRM_SECS      = 5.0
    ECU_LOST_TOLERANCE_S   = 10.0
    WAITING_POLL_SECS      = 3.0
    POWEROFF_AFTER_SECS    = 60
    INIT_WAIT_SECS         = 5.0
    DASHBOARD_UPDATE_HZ    = 1.0   # actualizar live.json 1 vez/s

    def __init__(self, port, sessions_dir, buell_dir, no_poweroff=False):
        self.port=port; self.sessions_dir=sessions_dir
        self.buell_dir=buell_dir; self.no_poweroff=no_poweroff
        self.conn=DDFI2Connection(port); self.session=SessionManager(sessions_dir)
        self.logger=logging.getLogger("BuellLogger")
        self._running=False; self._ride_active=False
        self._low_rpm_since=None; self._ecu_lost_since=None
        self._force_reconnect=False  # set via /reconnect para forzar salida del waiting_loop
        self._shutting_down=False        # True cuando llega SIGTERM/SIGINT
        self._last_logged_lost_interval=-1  # para evitar spam de log ECU perdida
        self._prev_cdiag = [0]*5      # últimos CDiag0-4 para detectar cambios
        self._prev_seconds = None     # detector ECU reset (Seconds retrocede)
        self._active_dtcs = []         # lista de DTCs activos ahora mismo
        self._dtc_log = []             # [(elapsed_s, dtc_num, desc, active)] del ride actual
        self.tracker=CellTracker()
        self.error_log = RideErrorLog()  # ErrorLog del ride actual
        self.dashboard=LiveDashboard(buell_dir, self.tracker)
        self.dashboard._buell_logger_ref = self  # para endpoint /reconnect
        self._last_dashboard_update=0.0
        # Cargar factor VSS al arrancar
        global VSS_CPKM25
        _vss_path = Path(buell_dir) / "vss_cal.json"
        if _vss_path.exists():
            try:
                import json as _json
                _vc = _json.loads(_vss_path.read_text())
                VSS_CPKM25 = float(_vc.get("cpkm25", 1368))
            except Exception: pass
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT,  self._handle_signal)

    def _handle_signal(self, signum, frame):
        self.logger.info(f"Señal {signum} — shutdown limpio (R15)")
        self._running=False; self._shutting_down=True

    def _update_dashboard(self, live_data):
        now = time.monotonic()
        if now - self._last_dashboard_update < 1.0/self.DASHBOARD_UPDATE_HZ:
            return
        self._last_dashboard_update = now
        elapsed = time.monotonic()-self.session.ride_start_time if self.session.ride_start_time and self._ride_active else 0
        self.dashboard.update_state(
            ride_active=self._ride_active,
            ride_num=self.session.current_ride_num,
            elapsed_s=elapsed,
            live_data=live_data or {}
        )

    def _flush_ride(self, reason, tracker_snap=None, objectives=None, dtc=None):
        """Cierra el ride + flushea el errorlog. Usar en lugar de llamar
        session.close_current_ride() directamente desde el loop."""
        closed_utc = datetime.now(timezone.utc).isoformat()
        self.session.close_current_ride(
            reason,
            tracker_snapshot = tracker_snap,
            objectives_cfg   = objectives,
            dtc_log          = dtc,
        )
        self.error_log.flush(closed_utc=closed_utc)
        self.error_log.clear()

    def _handle_sample(self, data, wall_time):
        if self._ecu_lost_since is not None:
            lost=time.monotonic()-self._ecu_lost_since
            self.logger.info(f"ECU recuperada tras {lost:.1f}s — ride continúa (R6)")
            self._ecu_lost_since=None; self._last_logged_lost_interval=-1

        # ── Detector ECU reset por Seconds retrocede ─────────────
        secs_now = data.get("Seconds", None)
        if secs_now is not None and self._prev_seconds is not None:
            if secs_now < self._prev_seconds - 2:
                self.logger.warning(f"ECU reset detectado: Seconds {self._prev_seconds}→{secs_now} — killswitch físico")
                data["ecu_reset"] = 1
                # ── ERROR LOG: ecu_reset ─────────────────────────
                if self._ride_active:
                    elapsed_s = (time.monotonic()-self.session.ride_start_time
                                 if self.session.ride_start_time else 0.0)
                    self.error_log.ecu_reset(
                        elapsed_s   = elapsed_s,
                        seconds_prev= self._prev_seconds,
                        seconds_now = secs_now)
            else:
                data["ecu_reset"] = 0
        else:
            data["ecu_reset"] = 0
        self._prev_seconds = secs_now
        rpm=data.get("RPM",0) or 0
        if self._ride_active:
            self.tracker.update(data)
        # ── Detección DTC en tiempo real ─────────────────────────
        cdiag_now = [
            int(data.get("CDiag0",0) or 0),
            int(data.get("CDiag1",0) or 0),
            int(data.get("CDiag2",0) or 0),
            int(data.get("CDiag3",0) or 0),
            int(data.get("CDiag4",0) or 0),
        ]
        active = []
        for bi, bname in enumerate([f"CDiag{i}" for i in range(5)]):
            byte_now  = cdiag_now[bi]
            byte_prev = self._prev_cdiag[bi]
            for bit in range(8):
                bit_now  = (byte_now  >> bit) & 1
                bit_prev = (byte_prev >> bit) & 1
                dtc_num, desc = DTC_MAP.get((bname, bit), (0, None))
                if desc is None: continue
                if bit_now:
                    active.append({"dtc": dtc_num, "desc": desc, "byte": bname, "bit": bit})
                if bit_now and not bit_prev:
                    t0 = self.session.ride_start_time
                    elapsed = round(time.monotonic()-t0, 1) if self._ride_active and t0 else 0
                    self.logger.warning(f"DTC NUEVO: {bname} bit{bit} → DTC{dtc_num} [{desc}] @ t={elapsed}s")
                    self._dtc_log.append({"t": elapsed, "event":"new",
                                          "dtc": dtc_num, "desc": desc, "byte": bname, "bit": bit,
                                          "RPM": data.get("RPM"), "CLT": data.get("CLT")})
                elif not bit_now and bit_prev:
                    t0 = self.session.ride_start_time
                    elapsed = round(time.monotonic()-t0, 1) if self._ride_active and t0 else 0
                    self.logger.info(f"DTC limpiado: {bname} bit{bit} → DTC{dtc_num} [{desc}] @ t={elapsed}s")
                    self._dtc_log.append({"t": elapsed, "event":"cleared",
                                          "dtc": dtc_num, "desc": desc, "byte": bname, "bit": bit,
                                          "RPM": data.get("RPM"), "CLT": data.get("CLT")})
        self._prev_cdiag = cdiag_now
        self._active_dtcs = active
        if not self._ride_active and rpm>=self.RPM_START_THRESHOLD:
            self._ride_active=True; self._low_rpm_since=None
            self._dtc_log.clear()  # limpiar log de ride anterior al arrancar
            self.tracker.reset()
            self.session.start_ride()
            # Iniciar ErrorLog para este ride
            self.error_log.start(
                ride_num     = self.session.current_ride_num,
                session_checksum = self.session.current_checksum,
                session_dir  = self.session.current_session_dir,
            )
            self.logger.info(f"Motor detectado {rpm:.0f} RPM — ride iniciado (R1)")
        if self._ride_active:
            self.error_log.update_last_sample(data)   # contexto siempre fresco
            self.session.write_sample(data,wall_time)
            self._update_dashboard(data)
            if rpm<self.RPM_STOP_THRESHOLD:
                if self._low_rpm_since is None: self._low_rpm_since=time.monotonic()
                elif (time.monotonic()-self._low_rpm_since)>=self.STOP_CONFIRM_SECS:
                    self._ride_active=False; self._low_rpm_since=None
                    self._flush_ride(
                        "RPM=0 por 5s",
                        tracker_snap = self.tracker.snapshot(),
                        objectives   = self.dashboard.objectives,
                        dtc          = list(self._dtc_log))
                    self._dtc_log.clear()
                    self.logger.info("Motor apagado — ride cerrado (R4)")
                    return False
            else:
                self._low_rpm_since=None
        else:
            self._update_dashboard(data)
        return True

    def _reading_loop(self):
        self.logger.info("Lectura RT @ ~8Hz")
        consecutive_errors=0; loop_interval=1.0/self.TARGET_LOOP_HZ
        while self._running:
            # Chequear reconexión forzada AL INICIO — antes de tocar el puerto
            if self._force_reconnect:
                self.logger.info("Reconexión forzada — saliendo de reading_loop")
                return "waiting"
            t0=time.monotonic(); wall_time=time.time()
            elapsed_s = (time.monotonic()-self.session.ride_start_time
                         if self.session.ride_start_time and self._ride_active else 0.0)
            try:
                data=self.conn.get_rt_data()
            except Exception as e:
                self.logger.warning(f"Excepción en get_rt_data: {e}")
                # ── ERROR LOG: serial exception ──────────────────
                if self._ride_active:
                    self.error_log.serial_exception(
                        elapsed_s       = elapsed_s,
                        exc_msg         = e,
                        consecutive_before = consecutive_errors)
                data=None
                consecutive_errors+=1
                # Puerto roto — salir inmediatamente si no hay ride activo
                if not self._ride_active:
                    self.logger.info("Puerto roto sin ride activo — modo espera")
                    return "waiting"
                # Con ride activo: registrar pérdida y seguir intentando
                if self._ecu_lost_since is None:
                    self._ecu_lost_since=time.monotonic()
                    self.logger.warning("Puerto serial roto durante ride — esperando recuperación")
                time.sleep(0.2); continue
            # ── ERROR LOG: dirty bytes (detectado dentro de get_rt_data) ──
            if self._ride_active and getattr(self.conn,'last_dirty_byte',None):
                self.error_log.dirty_bytes(
                    elapsed_s      = elapsed_s,
                    byte0_hex      = self.conn.last_dirty_byte,
                    sync_recovered = (data is not None))
            if data is None:
                consecutive_errors+=1
                if self._ride_active:
                    # Con ride activo: nunca auto-cerrar, el usuario decide
                    if self._ecu_lost_since is None:
                        self._ecu_lost_since=time.monotonic()
                        self.logger.info("ECU sin respuesta durante ride — esperando recuperación (sin auto-cierre)")
                    lost=time.monotonic()-self._ecu_lost_since
                    # ── ERROR LOG: ecu_timeout — cada 10s nuevo evento ──
                    lost_interval=int(lost)//10
                    if lost_interval != self._last_logged_lost_interval:
                        self._last_logged_lost_interval=lost_interval
                        self.logger.info(f"ECU sin respuesta {lost:.0f}s — ride sigue abierto, esperando...")
                        if self._ride_active:
                            self.error_log.ecu_timeout(
                                elapsed_s   = elapsed_s,
                                lost_s      = lost,
                                last_valid_t= elapsed_s - lost)
                else:
                    if consecutive_errors>=self.MAX_CONSECUTIVE_ERRORS:
                        self.logger.info("ECU no responde — modo espera"); return "waiting"
                # Hard reconnect tras 30s de pérdida — close+open+DTR aunque haya ride activo
                if self._ecu_lost_since is not None:
                    lost_total = time.monotonic() - self._ecu_lost_since
                    if lost_total >= 30.0 and consecutive_errors % 30 == 0:
                        self.logger.info(f"Hard reconnect — {lost_total:.0f}s sin ECU, cerrando/abriendo puerto")
                        if self._ride_active:
                            self.error_log.reconnect_attempt(
                                elapsed_s = elapsed_s,
                                trigger   = "auto_30s",
                                attempt_n = consecutive_errors // 30,
                                success   = False,
                                time_s    = lost_total)
                        # ── Escalación USB reset tras 60s: FT232RL puede estar hung ──
                        if lost_total >= 60.0 and consecutive_errors % 60 == 0:
                            self.logger.info(f"USB reset FT232RL — {lost_total:.0f}s sin recuperar por DTR")
                            self.conn.usb_reset()
                            time.sleep(0.5)  # esperar re-enumeración extra
                        try:
                            self.conn.disconnect()
                            time.sleep(0.5)
                            self.conn.connect()
                            self.conn._send(PDU_VERSION)
                            h = self.conn._read_exact(6, 1.0)
                            if h and h[0] == SOH:
                                self.logger.info("ECU responde tras hard reconnect — retomando")
                                consecutive_errors = 0
                                self._ecu_lost_since = None
                                if self._ride_active:
                                    self.error_log.reconnect_attempt(
                                        elapsed_s = elapsed_s,
                                        trigger   = "auto_30s",
                                        attempt_n = consecutive_errors // 30,
                                        success   = True,
                                        time_s    = lost_total)
                        except Exception as e:
                            self.logger.warning(f"Hard reconnect falló: {e}")
                # Fallback: VERSION simple cada 30 fallos si no hay ride activo
                elif consecutive_errors > 0 and consecutive_errors % 30 == 0:
                    self.logger.debug(f"Mandando VERSION tras {consecutive_errors} fallos")
                    try:
                        self.conn._send(PDU_VERSION)
                        h = self.conn._read_exact(6, 1.0)
                        if h and h[0] == SOH:
                            self.logger.info("ECU responde a VERSION — retomando RT")
                            consecutive_errors = 0
                            self._ecu_lost_since = None
                    except Exception: pass
                time.sleep(0.05); continue
            consecutive_errors=0
            if self._ecu_lost_since is not None:
                self.logger.info("ECU recuperada — retomando ride")
                try: self.conn.ser.reset_input_buffer()
                except Exception: pass
                self._ecu_lost_since=None
                self._last_logged_lost_interval=-1
            if not self._handle_sample(data,wall_time): return "waiting"
            elapsed=time.monotonic()-t0
            s=loop_interval-elapsed
            if s>0: time.sleep(s)
        return "stop"

    def _waiting_loop(self):
        self.logger.info(f"Modo espera — poweroff en {self.POWEROFF_AFTER_SECS}s sin ECU ni SSH")
        time_sin_ecu=0.0; attempt=0
        while self._running:
            # Pausa entre intentos para no saturar el bus
            if attempt > 0: time.sleep(self.WAITING_POLL_SECS)
            try:
                self.conn.connect()
                version=self.conn.get_version()
                self.conn.disconnect()
                if version:
                    self.logger.info(f"ECU detectada en intento {attempt+1}: {version}")
                    return version
                else:
                    self.logger.info(f"Intento {attempt+1}: ECU no responde a VERSION — reintentando")
            except Exception as e:
                self.logger.debug(f"Intento {attempt+1} error: {e}")
            finally: self.conn.disconnect()
            if self.dashboard._pending_shutdown:
                self.logger.info("Apagado solicitado desde browser")
                return "poweroff"
            if self._force_reconnect:
                self._force_reconnect = False
                self.logger.info("Reconexión forzada desde dashboard — intentando conectar ahora")
                continue  # salta el sleep y reintenta inmediato
            # Mantener dashboard vivo en modo espera (sin ECU): CLT/TPS/etc. visibles
            self.dashboard.update_state(ride_active=False, ride_num=0, elapsed_s=0, live_data={})
            if NetworkManager.ssh_active() or self.dashboard.browser_alive():
                if attempt%10==0:
                    src = "SSH" if NetworkManager.ssh_active() else "browser"
                    self.logger.info(f"{src} activo — poweroff pausado | sin ECU {time_sin_ecu:.0f}s")
            else:
                time_sin_ecu+=self.WAITING_POLL_SECS
                if time_sin_ecu>=self.POWEROFF_AFTER_SECS: return "poweroff"
                if attempt%5==0 and attempt>0:
                    self.logger.info(f"Sin ECU {time_sin_ecu:.0f}s — poweroff en {self.POWEROFF_AFTER_SECS-time_sin_ecu:.0f}s")
            attempt+=1; time.sleep(self.WAITING_POLL_SECS)
        return "stop"

    def _do_poweroff(self):
        if self.no_poweroff:
            self.logger.info("--no-poweroff: reiniciando espera"); return False
        self.logger.info("Apagando Pi (R12)")
        if self._ride_active:
            self._flush_ride("poweroff"); self._ride_active=False
        self.conn.disconnect(); os.system("sudo poweroff"); return True

    def run(self):
        self._running=True
        self.logger.info(f"BuellLogger {LOGGER_VERSION} | puerto={self.port} | sessions={self.sessions_dir}")
        NetworkManager.setup()
        self.dashboard.start(sessions_dir=self.sessions_dir)
        self.logger.info(f"Esperando {self.INIT_WAIT_SECS}s para ECU (R10)...")
        time.sleep(self.INIT_WAIT_SECS)
        state="waiting"
        try:
            self.conn.connect(); version=self.conn.get_version()
            if version:
                self.session.open_session(version); state="reading"
                self.logger.info(f"ECU lista: {version}")
                # ── Leer EEPROM al arrancar ──────────────────
                self.logger.info("Leyendo EEPROM completa...")
                eeprom_bytes = self.conn.read_full_eeprom()
                if eeprom_bytes:
                    params = decode_eeprom_params(eeprom_bytes)
                    snap_path = Path(self.buell_dir) / "eeprom_snapshot.json"
                    with open(snap_path, 'w') as f:
                        json.dump(params, f, indent=2)
                    self.dashboard.eeprom_params = params
                    self.dashboard.eeprom_maps   = decode_eeprom_maps(eeprom_bytes)
                    # Log límites críticos de temperatura
                    t_soft = params.get("KTemp_Soft_Hi",{}).get("val","?")
                    t_hard = params.get("KTemp_Hard_Hi",{}).get("val","?")
                    t_kill = params.get("KTemp_Kill_Hi",{}).get("val","?")
                    self.logger.info(f"EEPROM decodificada: Soft={t_soft}°C Hard={t_hard}°C Kill={t_kill}°C")
                else:
                    self.logger.warning("No se pudo leer la EEPROM — usando snapshot anterior si existe")
            else:
                self.logger.info("Sin ECU al arrancar → WAITING (R3)")
            self.conn.disconnect()
        except Exception as e: self.logger.info(f"Sin ECU ({e}) → WAITING (R3)"); self.conn.disconnect()
        while self._running:
            if state=="reading":
                try: self.conn.connect()
                except Exception as e: self.logger.error(f"No abrió puerto: {e}"); state="waiting"; continue
                result=self._reading_loop()
                if self._ride_active:
                    reason="shutdown" if self._shutting_down else "salida loop"
                    self._flush_ride(reason,
                        tracker_snap = self.tracker.snapshot(),
                        objectives   = self.dashboard.objectives,
                        dtc          = list(self._dtc_log))
                    self._ride_active=False; self._ecu_lost_since=None
                    self._last_logged_lost_interval=-1
                    self._dtc_log.clear()
                self.conn.disconnect()
                if result=="stop": break
                state="waiting"
            elif state=="waiting":
                result=self._waiting_loop()
                if result=="poweroff":
                    if self._do_poweroff(): break
                elif result=="stop": break
                else:
                    # Reconexión limpia — igual que arranque inicial
                    self.logger.info("Reconexión limpia — reiniciando puerto FT232...")
                    try:
                        self.conn.disconnect()
                        time.sleep(1.0)
                        self.conn.connect()
                        version=self.conn.get_version()
                        if version:
                            self.logger.info(f"ECU confirmada en reconexión: {version}")
                            eeprom_bytes=self.conn.read_full_eeprom()
                            if eeprom_bytes:
                                params=decode_eeprom_params(eeprom_bytes)
                                snap_path=Path(self.buell_dir)/"eeprom_snapshot.json"
                                with open(snap_path,'w') as _f: json.dump(params,_f,indent=2)
                                self.dashboard.eeprom_params=params
                                self.dashboard.eeprom_maps=decode_eeprom_maps(eeprom_bytes)
                                self.logger.info("EEPROM releída OK en reconexión")
                            self.conn.disconnect()
                            self.session.open_session(version)
                            state="reading"
                        else:
                            self.logger.warning("ECU no confirmó en reconexión — regresando a espera")
                            self.conn.disconnect()
                            state="waiting"
                    except Exception as e:
                        self.logger.error(f"Error en reconexión limpia: {e}")
                        self.conn.disconnect()
                        state="waiting"
        if self._ride_active: self._flush_ride("shutdown"); self._ride_active=False
        self.conn.disconnect(); self.dashboard.stop()
        self.logger.info("BuellLogger detenido.")

# ─────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────────────
def main():
    p=argparse.ArgumentParser(description="Buell DDFI2 ECU Logger v4")
    p.add_argument("--port",         default="/dev/ttyUSB0")
    p.add_argument("--sessions-dir", default="/home/pi/buell/sessions")
    p.add_argument("--buell-dir",    default="/home/pi/buell")
    p.add_argument("--log-level",    default="INFO", choices=["DEBUG","INFO","WARNING","ERROR"])
    p.add_argument("--no-poweroff",  action="store_true")
    args=p.parse_args()
    logging.basicConfig(level=getattr(logging,args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",datefmt="%Y-%m-%d %H:%M:%S")
    BuellLogger(port=args.port, sessions_dir=args.sessions_dir,
                buell_dir=args.buell_dir, no_poweroff=args.no_poweroff).run()

if __name__=="__main__":
    main()
