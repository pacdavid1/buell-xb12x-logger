# DEV NOTE: All code, comments, and variable names must be in English.
# AI agents: write everything in English.

import csv
from web.gear_detect import detect_gear as _detect_gear
import json
import logging
from pathlib import Path

from web.f7 import _f7_load_session_clusters, _f7_match_cross_session


def detect_launches(rows, pre_window=3.0, post_window=5.0, min_dtps=8.0, min_rpm=1500):
    """Detect WOT tip-in events from CSV rows.

    Changes vs previous:
    - min_dtps lowered 15.0->8.0 to capture smoother throttle openings
    - gear taken from pre-window mode, not the exact launch sample
    - discards event if gear=0 or gear changed during pre-window
    - adds environmental metadata: pre_clt, pre_alt_m, pre_baro_hpa
    - adds gear_stable flag
    """
    if len(rows) < 30:
        return []
    launches = []

    def _std(vals):
        n = len(vals)
        if n < 2: return 0.0
        m = sum(vals) / n
        return (sum((x - m) ** 2 for x in vals) / n) ** 0.5

    def _mode_gear(samples):
        counts = {}
        for r in samples:
            g = int(r.get('gear_detected') or r.get('gear', 0))
            if g > 0:
                counts[g] = counts.get(g, 0) + 1
        return max(counts, key=counts.get) if counts else 0

    i = 1
    while i < len(rows):
        dtps = rows[i]['tps'] - rows[i-1]['tps']
        if dtps > min_dtps and rows[i]['rpm'] > min_rpm:
            t0 = rows[i]['t']
            pre = [r for r in rows if t0 - pre_window <= r['t'] <= t0 - 0.05]
            if len(pre) < 10:
                i += 1; continue

            tail = pre[-min(20, len(pre)):]

            # Gear: use mode of pre-window, not the exact launch sample
            gear = _mode_gear(tail)
            if gear == 0:
                i += 1; continue

            # Gear stability: discard if gear changed during pre-window
            gear_vals = [int(r.get('gear_detected') or r.get('gear', 0)) for r in tail if int(r.get('gear_detected') or r.get('gear', 0)) > 0]
            gear_stable = bool(gear_vals) and all(g == gear for g in gear_vals)
            if not gear_stable:
                i += 1; continue

            rs = _std([r['rpm'] for r in tail])
            ts = _std([r['tps'] for r in tail])
            ss = _std([r['spd'] for r in tail])

            if ts < 5:
                lt = 'A'
            elif ts < 20 and rs < 500 and ss < 15:
                lt = 'B'
            else:
                i += 1; continue

            # Environmental metadata averaged over pre-window
            clt_vals  = [r['clt']      for r in tail if r.get('clt')]
            alt_vals  = [r['alt']      for r in tail if r.get('alt') is not None]
            baro_vals = [r['baro_hpa'] for r in tail if r.get('baro_hpa')]
            pre_clt  = round(sum(clt_vals)  / len(clt_vals),  1) if clt_vals  else None
            pre_alt  = round(sum(alt_vals)  / len(alt_vals),  1) if alt_vals  else None
            pre_baro = round(sum(baro_vals) / len(baro_vals), 1) if baro_vals else None

            # Time series around the event
            t_start, t_end = t0 - pre_window, t0 + post_window
            series = []; last_t = -999
            for r in rows:
                if r['t'] < t_start: continue
                if r['t'] > t_end:   break
                if r['t'] - last_t >= 0.18:
                    series.append({
                        'dt':  round(r['t'] - t0, 2),
                        'rpm': round(r['rpm'], 0),
                        'tps': round(r['tps'], 1),
                        'spd': round(r['spd'], 1),
                        'pw1': round(r['pw1'], 3),
                        'pw2': round(r.get('pw2') or r['pw1'], 3),
                        'ae':  round(r.get('ae', 100), 1),
                        'alt': round(r['alt'], 1) if r.get('alt') is not None else None,
                    })
                    last_t = r['t']

            post = [r for r in rows if t0 <= r['t'] <= t_end]
            launch = {
                'type':         lt,
                't':            round(t0, 1),
                'gear':         gear,
                'gear_stable':  gear_stable,
                'dtps_raw':     round(dtps, 1),
                'pre_rpm':      round(sum(r['rpm'] for r in tail) / len(tail), 0),
                'pre_spd':      round(sum(r['spd'] for r in tail) / len(tail), 1),
                'pre_tps':      round(sum(r['tps'] for r in tail) / len(tail), 1),
                'pre_rpm_std':  round(rs, 0),
                'pre_tps_std':  round(ts, 1),
                'pre_spd_std':  round(ss, 1),
                'pre_clt':      pre_clt,
                'pre_alt_m':    pre_alt,
                'pre_baro_hpa': pre_baro,
                'series':       series,
            }
            if post:
                launch['peak_rpm'] = round(max(r['rpm'] for r in post), 0)
                launch['peak_spd'] = round(max(r['spd'] for r in post), 1)
                launch['peak_pw']  = round(max((r['pw1']+(r.get('pw2') or r['pw1']))/2 for r in post), 3)
                launch['peak_ae']  = round(max(r.get('ae', 100) for r in post), 1)
                launch['rpm_gain'] = round(post[-1]['rpm'] - tail[-1]['rpm'], 0)
                launch['spd_gain'] = round(post[-1]['spd'] - tail[-1]['spd'], 1)
            launches.append(launch)

            skip = t0 + post_window
            while i < len(rows) and rows[i]['t'] <= skip:
                i += 1
            continue
        i += 1
    return launches


def _s_std(vals):
    """Standard deviation"""
    n = len(vals)
    if n < 2: return 0.0
    m = sum(vals) / n
    return (sum((x - m) ** 2 for x in vals) / (n - 1)) ** 0.5

def cluster_launches(launches, rpm_tol=250, tps_tol=2.5):
    # IMPORTANT: clustering uses pre-launch conditions only (rpm, tps, gear, spd).
    # Outcome metrics (rpm_gain, spd_gain, peak_pw, mean_series) are intentionally
    # excluded to avoid bias — we group by initial conditions, then compare results.
    if not launches:
        return []

    def _assign(launches, clusters, rpm_tol, tps_tol):
        assignments = []
        for l in launches:
            gear = l.get("gear", 0)
            rpm  = l.get("pre_rpm", 0)
            tps  = l.get("pre_tps", 0)
            best_idx  = -1
            best_dist = float("inf")
            for i, c in enumerate(clusters):
                if c["gear"] != gear: continue
                dr   = abs(c["mean_rpm"] - rpm) / rpm_tol
                dt   = abs(c["mean_tps"] - tps) / max(tps_tol, 0.1)
                dist = (dr**2 + dt**2) ** 0.5
                if dist < 1.0 and dist < best_dist:
                    best_dist = dist
                    best_idx  = i
            assignments.append(best_idx)
        return assignments

    clusters = []
    for l in launches:
        gear = l.get("gear", 0)
        rpm  = l.get("pre_rpm", 0)
        tps  = l.get("pre_tps", 0)
        spd  = l.get("pre_spd", 0)
        best_idx  = -1
        best_dist = float("inf")
        for i, c in enumerate(clusters):
            if c["gear"] != gear: continue
            dr   = abs(c["mean_rpm"] - rpm) / rpm_tol
            dt   = abs(c["mean_tps"] - tps) / max(tps_tol, 0.1)
            dist = (dr**2 + dt**2) ** 0.5
            if dist < 1.0 and dist < best_dist:
                best_dist = dist
                best_idx  = i
        if best_idx >= 0:
            clusters[best_idx]["_items"].append(l)
        else:
            clusters.append({"gear":gear,"mean_rpm":rpm,"mean_tps":tps,"mean_spd":spd,"_items":[l]})
    for c in clusters:
        items = c["_items"]
        c["mean_rpm"] = sum(x.get("pre_rpm",0) for x in items)/len(items)
        c["mean_tps"] = sum(x.get("pre_tps",0) for x in items)/len(items)
        c["mean_spd"] = sum(x.get("pre_spd",0) for x in items)/len(items)
    assignments = _assign(launches, clusters, rpm_tol, tps_tol)
    for c in clusters: c["_items"] = []
    for l, idx in zip(launches, assignments):
        if idx >= 0: clusters[idx]["_items"].append(l)
        else: clusters.append({"gear":l.get("gear",0),"mean_rpm":l.get("pre_rpm",0),"mean_tps":l.get("pre_tps",0),"mean_spd":l.get("pre_spd",0),"_items":[l]})
    clusters = [c for c in clusters if c["_items"]]
    for c in clusters:
        ll = c["_items"]; n = len(ll)
        c["count"]    = n
        c["mean_rpm"] = sum(x.get("pre_rpm",0) for x in ll)/n
        c["mean_spd"] = sum(x.get("pre_spd",0) for x in ll)/n
        c["mean_tps"] = sum(x.get("pre_tps",0) for x in ll)/n
        c["rpm_std"]  = _s_std([x.get("pre_rpm",0) for x in ll])
        c["spd_std"]  = _s_std([x.get("pre_spd",0) for x in ll])
        c["tps_std"]  = _s_std([x.get("pre_tps",0) for x in ll])
        clt_v  = [x["pre_clt"]      for x in ll if x.get("pre_clt")      is not None]
        alt_v  = [x["pre_alt_m"]    for x in ll if x.get("pre_alt_m")    is not None]
        baro_v = [x["pre_baro_hpa"] for x in ll if x.get("pre_baro_hpa") is not None]
        c["pre_clt_mean"]  = round(sum(clt_v) /len(clt_v), 1)  if clt_v  else None
        c["pre_alt_mean"]  = round(sum(alt_v) /len(alt_v), 1)  if alt_v  else None
        c["pre_baro_mean"] = round(sum(baro_v)/len(baro_v),1) if baro_v else None
        for key,src in [("peak_pw","peak_pw"),("peak_ae","peak_ae"),("rpm_gain","rpm_gain"),("spd_gain","spd_gain"),("dtps","dtps_raw")]:
            vals = [x.get(src,0) for x in ll]
            c[key+"_mean"] = round(sum(vals)/len(vals),3)
            c[key+"_std"]  = round(_s_std(vals),3)
        dt_min = min((x.get("series",[{}])[0].get("dt",0)  for x in ll if x.get("series")),default=0)
        dt_max = max((x.get("series",[{}])[-1].get("dt",0) for x in ll if x.get("series")),default=0)
        tpts=[]; t=dt_min
        while t<=dt_max+0.01: tpts.append(round(t,2)); t+=0.25
        if len(tpts)>1:
            all_c={k:[] for k in ("rpm","tps","spd","pw1","ae","alt")}
            for x in ll:
                pts=x.get("series",[])
                for k in all_c:
                    curve=[]
                    for tp in tpts:
                        best,bd=None,999
                        for p in pts:
                            d=abs(p["dt"]-tp)
                            if d<bd: bd,best=d,p
                        curve.append(best.get(k) if best and bd<0.15 else None)
                    all_c[k].append(curve)
            ms,ss=[],[]
            for idx in range(len(tpts)):
                rm,rs={"dt":tpts[idx]},{"dt":tpts[idx]}
                for k in ("rpm","tps","spd"):
                    vals=[all_c[k][ci][idx] for ci in range(n) if all_c[k][ci][idx] is not None]
                    rm[k]=round(sum(vals)/len(vals),1) if vals else None
                    rs[k]=round(_s_std(vals),1) if len(vals)>1 else 0.0
                pw_v=[all_c["pw1"][ci][idx] for ci in range(n) if all_c["pw1"][ci][idx] is not None]
                rm["pw"]=round(sum(pw_v)/len(pw_v),3) if pw_v else None
                ae_v=[all_c["ae"][ci][idx]  for ci in range(n) if all_c["ae"][ci][idx]  is not None]
                rm["ae"]=round(sum(ae_v)/len(ae_v),1) if ae_v else None
                alt_v=[all_c["alt"][ci][idx] for ci in range(n) if all_c["alt"][ci][idx] is not None]
                rm["alt"]=round(sum(alt_v)/len(alt_v),1) if alt_v else None
                rs["alt"]=round(_s_std(alt_v),1) if len(alt_v)>1 else 0.0
                ms.append(rm); ss.append(rs)
            c["mean_series"]=ms; c["std_series"]=ss
        else:
            c["mean_series"]=[]; c["std_series"]=[]
        del c["_items"]
    clusters.sort(key=lambda c:(c["gear"] if c["gear"] else 99,-c["count"]))
    for i,c in enumerate(clusters): c["id"]=i
    return clusters

def match_clusters(clusters_a, clusters_b, rpm_tol=400, spd_tol=12, tps_tol=2.5):
    """
    Find matching clusters between sessions A and B.
    Returns list of (a_idx, b_idx, distance) for matched pairs.
    """
    matches = []
    used_b = set()
    for ca in clusters_a:
        best_b = None
        best_d = float('inf')
        for j, cb in enumerate(clusters_b):
            if j in used_b:
                continue
            if ca['gear'] != cb['gear']:
                continue
            dr = abs(ca['mean_rpm'] - cb['mean_rpm']) / rpm_tol
            ds = abs(ca['mean_spd'] - cb['mean_spd']) / spd_tol
            dt = abs(ca['mean_tps'] - cb['mean_tps']) / max(tps_tol, 0.1)
            d = (dr**2 + ds**2 + dt**2) ** 0.5  # Euclidean, same geometry as cluster_launches
            if d < best_d:
                best_d = d
                best_b = j
        if best_b is not None and best_d < 1.5:
            matches.append((ca['id'], clusters_b[best_b]['id'], round(best_d, 2)))
            used_b.add(best_b)
    return matches

def _compare_sessions(buell_dir, sa, sb):
    from collections import defaultdict
    from web.gear_learner import GearLearner

    RPM_BINS = [800,1200,1600,2000,2400,2800,3200,3600,4000,4400,4800,5200,5600,6000,6400,6800]
    TPS_BINS = [0,5,10,15,20,25,30,35,40,50,60,70,80,90,100,101]
    _gear_thresholds = GearLearner(buell_dir).get_thresholds()

    def bucket(val, bins):
        for i in range(len(bins)-1):
            if bins[i] <= val < bins[i+1]: return i
        return len(bins)-2

    def sf(v, d=0.0):
        try: return float(v) if v and str(v).strip() else d
        except (ValueError, TypeError): return d

    def load_meta(sid):
        mp = buell_dir / 'sessions' / sid / 'session_metadata.json'
        meta = {}
        if mp.exists():
            with open(mp) as f: meta = json.load(f)
        # leer serial del eeprom.bin para identificar moto
        ep = buell_dir / 'sessions' / sid / 'eeprom.bin'
        if ep.exists():
            try:
                b = ep.read_bytes()
                if len(b) >= 14:
                    meta['bike_serial'] = int.from_bytes(b[12:14], 'little')
            except (OSError, TypeError):
                logging.getLogger("WebServer").debug("load_meta: could not read serial from %s" % ep)
        return meta

    def load_csv(sid):
        rows = []
        sdir = buell_dir / 'sessions' / sid
        csv_files = sorted(sdir.glob('ride_*.csv'))
        time_offset = 0.0
        last_ride_num = -1
        for cp in csv_files:
            with open(cp) as f:
                lines = [l for l in f if not l.startswith('#')]
            if not lines: continue
            # Peek ride number from first data row (lines[0] is header)
            if len(lines) < 2: continue
            peek = list(csv.DictReader(lines[:2]))
            if not peek: continue
            ride_num = int(sf(peek[0].get('ride_num', 0)))
            # Advance offset only when ride number changes (new ride, not continuation)
            if last_ride_num != -1 and ride_num != last_ride_num and rows:
                time_offset = rows[-1]['t'] + 0.001
            last_ride_num = ride_num
            for r in csv.DictReader(lines):
                try:
                    rpm = sf(r['RPM'])
                    if rpm < 100: continue
                    _baro = sf(r.get('baro_hPa', 0))
                    _baro_valid = 900 < _baro < 1100
                    # DDFI2 is Alpha-N (TPS+RPM, no MAP sensor): the ECU does NOT
                    # compensate PW for barometric pressure, so raw PW already
                    # carries the real map-calibration difference between sessions.
                    # Baro-normalizing here would inject a false delta (or hide a
                    # real one across altitudes). See CLAUDE.md "Alpha-N fueling".
                    # baro is kept as a descriptive covariate only (not applied to PW).
                    rows.append({
                        't':    sf(r['time_elapsed_s']) + time_offset,
                        'rpm':  rpm,
                        'tps':  sf(r.get('TPS_pct') or r.get('TPD', 0)),
                        'clt':  sf(r['CLT']),
                        'pw1':      sf(r['pw1']),
                        'pw2':      sf(r.get('pw2', 0)),
                        'baro': _baro,
                        'baro_valid': _baro_valid,
                        'spark1':sf(r['spark1']),
                        'spark2':sf(r.get('spark2', sf(r['spark1']))),
                        'afv':  sf(r.get('AFV', 100)),
                        'wue':  sf(r.get('WUE', 100)),
                        'ae':   sf(r.get('Accel_Corr', 100)),
                        'gear':          sf(r.get('Gear', 0)),
                        'gear_detected':  _detect_gear(rpm, sf(r.get("VS_KPH", 0)), sf(r.get("di_neutral", 0)), thresholds=_gear_thresholds),
                        'spd':  sf(r.get('VS_KPH', 0)),
                        'alt':       sf(r.get('gps_alt_m'), None) if r.get('gps_valid','').strip().lower() in ('true','1') else None,
                        'baro_temp': sf(r.get('baro_temp_c', '')),
                        'humidity':  sf(r.get('humidity_pct', '')),
                        'fl_wot':  r.get('fl_wot','0').strip() in ('1','True','true'),
                        'fl_decel':r.get('fl_decel','0').strip() in ('1','True','true'),
                        'fl_fc':   r.get('fl_fuel_cut','0').strip() in ('1','True','true'),
                        'fl_eng':  r.get('fl_engine_run','1').strip() in ('1','True','true'),
                    })
                except Exception as e:
                    logging.getLogger("WebServer").debug("csv row skip: %s" % e)
                    continue
        return rows

    def derivatives(rows):
        for i in range(1, len(rows)):
            dt = rows[i]['t'] - rows[i-1]['t']
            if 0 < dt < 2.0:
                rows[i]['drpm'] = (rows[i]['rpm'] - rows[i-1]['rpm']) / dt
                rows[i]['dtps'] = (rows[i]['tps'] - rows[i-1]['tps']) / dt
                rows[i]['dvss'] = (rows[i]['spd'] - rows[i-1]['spd']) / dt
                a0, a1 = rows[i-1]['alt'], rows[i]['alt']
                if a0 is not None and a1 is not None:
                    dalt = a1 - a0
                    # slope = dAlt/dDist — pendiente real sin dimension
                    spd_ms = (rows[i]['spd'] + rows[i-1]['spd']) / 2 / 3.6
                    ddist = spd_ms * dt
                    rows[i]['dalt'] = dalt / dt  # m/s para clasificacion
                    rows[i]['slope'] = dalt / ddist if ddist > 0.1 else 0.0
                else:
                    rows[i]['dalt'] = None
                    rows[i]['slope'] = None
            else:
                rows[i]['drpm'] = rows[i]['dtps'] = rows[i]['dvss'] = 0.0
                rows[i]['dalt'] = None
                rows[i]['slope'] = None
        if rows:
            rows[0]['drpm'] = rows[0]['dtps'] = rows[0]['dvss'] = 0.0
            rows[0]['dalt'] = rows[0]['slope'] = None

    def classify(r):
        if not r['fl_eng'] or r['fl_fc']: return 'BITTER'
        if r['clt'] < 170: return 'BITTER'
        if r['wue'] > 102: return 'BITTER'
        if r['ae'] > 105:  return 'BITTER'
        drpm = abs(r.get('drpm', 0))
        dtps = r.get('dtps', 0)
        dalt = r.get('dalt')
        if r['fl_wot'] or r['tps'] >= 80:
            if dtps > 15:  return 'SPICY_TIPIN'
            if dtps < -15: return 'SPICY_TIPOUT'
            return 'SPICY_WOT'
        if dtps > 15:  return 'SPICY_TIPIN'
        if dtps < -15: return 'SPICY_TIPOUT'
        if drpm > 150 or abs(dtps) > 3: return 'BITTER'
        if dalt is None: return 'SWEET'
        if dalt > 0.8:   return 'SALTY_UP'
        if dalt < -0.8:  return 'SALTY_DOWN'
        return 'SWEET'

    def build_index(rows):
        idx = defaultdict(lambda: {
            'n':0,'pw1':0,'pw2':0,'spark1':0,'spark2':0,'clt':0,'afv':0,
            'drpm':0,'spd':0,'dvss':0,'pw_eff':0,'gear':0,
            'dalt':0,'dalt_n':0,'slope':0,'slope_n':0,
            # Welford online para std_rpm y std_tps
            'rpm_m':0.0,'rpm_m2':0.0,'tps_m':0.0,'tps_m2':0.0,
            'pweff_m':0.0,'pweff_m2':0.0,
        })
        fc  = defaultdict(int)
        for r in rows:
            fl = classify(r)
            fc[fl] += 1
            if fl == 'BITTER': continue
            rb = bucket(r['rpm'], RPM_BINS)
            tb = bucket(r['tps'], TPS_BINS)
            k  = (fl, rb, tb)
            c  = idx[k]
            c['n']    += 1
            c['pw1']  += r['pw1']
            c['pw2']  += r['pw2']
            c['spark1']+= r['spark1']
            c['spark2']+= r['spark2']
            c['clt']  += r['clt']
            c['afv']  += r['afv']
            c['drpm'] += abs(r.get('drpm',0))
            c['spd']  += r['spd']
            c['dvss'] += r.get('dvss', 0)
            c['pw_eff'] += ((r['pw1']+r['pw2'])/2) * r['afv'] / 100.0
            c['gear']  += r.get('gear', 0)
            if r.get('dalt') is not None:
                c['dalt']   += r['dalt']
                c['dalt_n'] += 1
            if r.get('slope') is not None:
                c['slope']   += r['slope']
                c['slope_n'] += 1
            # Welford online std_rpm
            n2 = c['n']
            delta_rpm = r['rpm'] - c['rpm_m']
            c['rpm_m']  += delta_rpm / n2
            c['rpm_m2'] += delta_rpm * (r['rpm'] - c['rpm_m'])
            delta_tps = r['tps'] - c['tps_m']
            c['tps_m']  += delta_tps / n2
            c['tps_m2'] += delta_tps * (r['tps'] - c['tps_m'])
            # Welford online std for pw_eff (GAP 1 significance)
            pweff_i = ((r['pw1']+r['pw2'])/2) * r['afv'] / 100.0
            delta_pweff = pweff_i - c['pweff_m']
            c['pweff_m']  += delta_pweff / n2
            c['pweff_m2'] += delta_pweff * (pweff_i - c['pweff_m'])
        result = {}
        for k,c in idx.items():
            n = c['n']
            result[k] = {
                'flavor': k[0],
                'rpm_lo': RPM_BINS[k[1]], 'rpm_hi': RPM_BINS[k[1]+1],
                'tps_lo': TPS_BINS[k[2]], 'tps_hi': TPS_BINS[k[2]+1],
                'n': n,
                'pw1':   round(c['pw1']/n, 3),
                'pw2':   round(c['pw2']/n, 3),
                'spark1':round(c['spark1']/n, 2),
                'spark2':round(c['spark2']/n, 2),
                'clt':   round(c['clt']/n, 1),
                'afv':   round(c['afv']/n, 1),
                'drpm':  round(c['drpm']/n, 1),
                'spd':   round(c['spd']/n, 1),
                'dvss':  round(c['dvss']/n, 3),
                'pw_eff':round(c['pw_eff']/n, 3),
                'gear':  round(c['gear']/n, 1),
                'dalt':  round(c['dalt']/c['dalt_n'], 2) if c['dalt_n']>0 else None,
                'slope': round(c['slope']/c['slope_n'], 4) if c['slope_n']>0 else None,
                'std_rpm': round((c['rpm_m2']/n)**0.5, 1) if n>1 else 0.0,
                'std_tps': round((c['tps_m2']/n)**0.5, 2) if n>1 else 0.0,
                'std_pweff': round((c['pweff_m2']/n)**0.5, 4) if n>1 else 0.0,
            }
        return result, dict(fc)

    def _env_stats(rows):
        baro_vals  = [r['baro']      for r in rows if r.get('baro_valid')]
        btemp_vals = [r['baro_temp'] for r in rows if r.get('baro_temp', 0) > 0]
        hum_vals   = [r['humidity']  for r in rows if r.get('humidity',  0) > 0]
        alt_vals   = [r['alt']       for r in rows if r.get('alt') is not None]
        return {
            'baro_avg':      round(sum(baro_vals)  / len(baro_vals),  1) if baro_vals  else None,
            'baro_n':        len(baro_vals),
            'baro_temp_avg': round(sum(btemp_vals) / len(btemp_vals), 1) if btemp_vals else None,
            'humidity_avg':  round(sum(hum_vals)   / len(hum_vals),   1) if hum_vals   else None,
            'alt_avg':       round(sum(alt_vals)   / len(alt_vals))       if alt_vals   else None,
            'alt_n':         len(alt_vals),
        }

    # Load both sessions
    ma, mb = load_meta(sa), load_meta(sb)
    ra, rb = load_csv(sa), load_csv(sb)
    derivatives(ra); derivatives(rb)
    ia, fca = build_index(ra)
    ib, fcb = build_index(rb)
    launches_a = detect_launches(ra)
    launches_b = detect_launches(rb)

    # Cluster similar launches
    clusters_a = cluster_launches(launches_a)
    clusters_b = cluster_launches(launches_b)
    cluster_matches = match_clusters(clusters_a, clusters_b)

    # Comparar celdas comunes por flavor
    MIN_N = 5
    delta = []
    keys_a = {k for k,v in ia.items() if v['n'] >= MIN_N}
    keys_b = {k for k,v in ib.items() if v['n'] >= MIN_N}
    common = keys_a & keys_b
    for k in common:
        a, b = ia[k], ib[k]
        # GAP 1: Welch two-sample 95% CI on dpw_eff (std_pweff per session).
        # Significant only when CI does not cross 0. NOTE: optimistic --
        # samples are autocorrelated, true independent N is lower.
        _dpweff = b['pw_eff'] - a['pw_eff']
        _se = (a['std_pweff']**2 / a['n'] + b['std_pweff']**2 / b['n']) ** 0.5
        _margin = 1.96 * _se
        _ci_lo, _ci_hi = _dpweff - _margin, _dpweff + _margin
        _sig = (_ci_lo > 0) or (_ci_hi < 0)
        delta.append({
            'flavor':   a['flavor'],
            'rpm':      f"{a['rpm_lo']}-{a['rpm_hi']}",
            'tps':      f"{a['tps_lo']}-{a['tps_hi']}",
            'rpm_lo':   a['rpm_lo'],
            'tps_lo':   a['tps_lo'],
            'na':       a['n'],
            'nb':       b['n'],
            'pw1_a':    a['pw1'],   'pw1_b':    b['pw1'],   'dpw1':   round(b['pw1']-a['pw1'],3),
            'pw2_a':    a['pw2'],   'pw2_b':    b['pw2'],   'dpw2':   round(b['pw2']-a['pw2'],3),
            'spk1_a':   a['spark1'],'spk1_b':   b['spark1'],'dspk1':  round(b['spark1']-a['spark1'],2),
            'spk2_a':   a['spark2'],'spk2_b':   b['spark2'],'dspk2':  round(b['spark2']-a['spark2'],2),
            'clt_a':    a['clt'],
            'clt_b':    b['clt'],
            'dclt':     round(b['clt'] - a['clt'], 1),
            'afv_a':    a['afv'],
            'afv_b':    b['afv'],
            'dvss_a':   a['dvss'],
            'dvss_b':   b['dvss'],
            'ddvss':    round(b['dvss'] - a['dvss'], 3),
            'spd_a':    a['spd'],
            'spd_b':    b['spd'],
            'dspd':     round(b['spd'] - a['spd'], 1),
            'gear_a':   a['gear'],
            'gear_b':   b['gear'],
            'dalt_a':   a['dalt'],
            'dalt_b':   b['dalt'],
            'slope_a':  a['slope'],
            'slope_b':  b['slope'],
            'std_rpm_a':a['std_rpm'],
            'std_rpm_b':b['std_rpm'],
            'std_tps_a':a['std_tps'],
            'std_tps_b':b['std_tps'],
            'pw_eff_a': a['pw_eff'],
            'pw_eff_b': b['pw_eff'],
            'dpw_eff':  round(b['pw_eff'] - a['pw_eff'], 3),
            'dpw_eff_se':    round(_se, 4),
            'dpw_eff_ci_lo': round(_ci_lo, 3),
            'dpw_eff_ci_hi': round(_ci_hi, 3),
            'dpw_eff_sig':   _sig,
        })
    delta.sort(key=lambda x: (x['flavor'], -(x['na']+x['nb'])))

    result = {
        'sa': {'id': sa, 'checksum': ma.get('checksum','?'), 'version': ma.get('version_string','?'),
               'created': ma.get('created_utc','')[:10], 'rides': ma.get('total_rides',0),
               'samples': len(ra), 'flavors': fca,
               'launches_a': launches_a, 'env': _env_stats(ra)},
        'sb': {'id': sb, 'checksum': mb.get('checksum','?'), 'version': mb.get('version_string','?'),
               'created': mb.get('created_utc','')[:10], 'rides': mb.get('total_rides',0),
               'samples': len(rb), 'flavors': fcb,
               'launches_b': launches_b, 'env': _env_stats(rb)},
        'clusters_a': clusters_a,
        'clusters_b': clusters_b,
        'cluster_matches': cluster_matches,
        'same_bike': ma.get('bike_serial') is not None and ma.get('bike_serial') == mb.get('bike_serial'),
        'bike_serial_a': ma.get('bike_serial'),
        'bike_serial_b': mb.get('bike_serial'),
        'common': len(common),
        'delta': delta,
    }

    # Same-map detection
    ep_a = Path(buell_dir) / 'sessions' / sa / 'eeprom.bin'
    ep_b = Path(buell_dir) / 'sessions' / sb / 'eeprom.bin'
    result['same_map'] = (ep_a.exists() and ep_b.exists() and ep_a.read_bytes() == ep_b.read_bytes())

    # FASE7 cross-session matching
    try:
        _f7a = _f7_load_session_clusters(buell_dir, sa)
        _f7b = _f7_load_session_clusters(buell_dir, sb)
        _f7m = _f7_match_cross_session(_f7a.get('clusters',[]), _f7b.get('clusters',[]))
        result['f7_session_a'] = _f7a
        result['f7_session_b'] = _f7b
        result['f7_matches']   = _f7m
        result['f7_n_matches'] = len(_f7m)
    except Exception as _e:
        logging.warning(f'FASE7 cross-session: {_e}')
        result['f7_matches']   = []
        result['f7_n_matches'] = 0
        result['f7_error']     = str(_e)

    return result
    