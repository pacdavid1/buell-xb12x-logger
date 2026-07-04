# DEV NOTE: All code, comments, and variable names must be in English.
# AI agents: write everything in English.

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ecu.eeprom import decode_eeprom_maps as _decode_eeprom_maps
from web.launch import _compare_sessions
from web.utils import _session_version
from ecu.version_resolver import resolve_ecu as _resolve_ecu


def _maps_differ(a,b):
    if len(a)!=len(b) or (a and len(a[0])!=len(b[0])): return True
    for i in range(len(a)):
        for j in range(len(a[0])):
            if abs(a[i][j]-b[i][j])>0.5: return True
    return False


RPM_BINS=[800,1200,1600,2000,2400,2800,3200,3600,4000,4400,4800,5200,5600,6000,6400,6800]
TPS_BINS=[0,5,10,15,20,25,30,35,40,50,60,70,80,90,100,101]


def _bin_index(v,bins):
    for i in range(len(bins)-1):
        if bins[i]<=v<bins[i+1]: return i
    return len(bins)-2


def _zone_by_tps_peak(tps_peak):
    """WOT: trust VS only (few F7 WOT events). MID: F7+VS fusion.
    LIGHT: F7 preferred (VS is poor at low TPS)."""
    if tps_peak>=85: return 'WOT'
    if tps_peak>=40: return 'MID'
    return 'LIGHT'


def _f7_delta_to_cells(f7_matches):
    """Map F7 cross-session matches to EEPROM cells using the same RPM/TPS
    binning as vs_delta.

    Approximation: each match is filed under ONE cell keyed by
    (bucket_a rpm_center, max tps_peak reached) -- the RPM at the start of
    the pull and the throttle position actually reached during it -- not a
    per-instant curve-resolution mapping. delta_pw is a resampled curve
    over the whole event; we use its mean as a single scalar, on the same
    ms scale as vs_delta's dpw_eff (both baro-normalized, both B-minus-A).
    """
    buckets={}
    for m in f7_matches:
        ba=m.get('bucket_a') or {}
        bb=m.get('bucket_b') or {}
        rpm_center=ba.get('rpm_center')
        delta_pw=m.get('delta_pw') or []
        if rpm_center is None or not delta_pw:
            continue
        tps_peak=max(ba.get('tps_peak',0), bb.get('tps_peak',0))
        key=(_bin_index(rpm_center,RPM_BINS),_bin_index(tps_peak,TPS_BINS))
        b=buckets.setdefault(key,{'deltas':[],'tps_dtw':[],'tps_peak':tps_peak})
        b['deltas'].append(sum(delta_pw)/len(delta_pw))
        b['tps_dtw'].append(m.get('tps_dtw',0))
    out={}
    for key,b in buckets.items():
        n=len(b['deltas'])
        out[key]={
            'f7_delta': sum(b['deltas'])/n,
            'n_matches': n,
            'confidence': round(min(1.0,n/2)*(sum(b['tps_dtw'])/n),3),
            'zone': _zone_by_tps_peak(b['tps_peak']),
        }
    return out


_GP_MIN_POINTS = 10


def _gpr_make_training_data(delta, flavor='SWEET', min_n=10):
    """Extract (rpm_lo, tps_lo) -> dpw_eff training points for one flavor.

    Includes ALL rows with enough samples, significant or not -- GAP1's
    hard significance gate is bypassed here on purpose. The GP's
    heteroscedastic noise (dpw_eff_se^2 per point) lets it naturally trust
    noisy cells less instead of excluding them outright.
    """
    X, y, noise = [], [], []
    for r in delta:
        if r.get('na', 0) < min_n or r.get('nb', 0) < min_n:
            continue
        if r.get('flavor') != flavor:
            continue
        se = r.get('dpw_eff_se')
        if se is None:
            continue
        X.append([r['rpm_lo'], r['tps_lo']])
        y.append(r.get('dpw_eff', 0))
        noise.append(max(se, 1e-3) ** 2)
    return X, y, noise


def _gpr_predict_grid(delta, flavor='SWEET'):
    """Fit a GP on flavor's delta rows, predict mean/std at every
    RPM_BINS x TPS_BINS grid center. Returns {} (caller must fall back to
    discrete logic) when scikit-learn is unavailable or there isn't enough
    training data.
    """
    X, y, noise = _gpr_make_training_data(delta, flavor)
    if len(X) < _GP_MIN_POINTS:
        return {}
    try:
        import numpy as np
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import Matern, ConstantKernel
    except ImportError:
        return {}
    kernel = ConstantKernel(1.0) * Matern(
        length_scale=[2000, 20],
        length_scale_bounds=[(500, 5000), (5, 50)],
        nu=2.5,
    )
    gpr = GaussianProcessRegressor(kernel=kernel, alpha=np.array(noise), n_restarts_optimizer=5, random_state=42)
    try:
        gpr.fit(np.array(X), np.array(y))
    except Exception:
        return {}
    grid_rpm = [(RPM_BINS[i] + RPM_BINS[i + 1]) / 2 for i in range(len(RPM_BINS) - 1)]
    grid_tps = [(TPS_BINS[j] + TPS_BINS[j + 1]) / 2 for j in range(len(TPS_BINS) - 1)]
    points = [(gr, gt) for gr in grid_rpm for gt in grid_tps]
    means, stds = gpr.predict(np.array(points), return_std=True)
    out = {}
    for (gr, gt), mean, std in zip(points, means, stds):
        key = (_bin_index(gr, RPM_BINS), _bin_index(gt, TPS_BINS))
        out[key] = {'mean': float(mean), 'std': float(std)}
    return out


def _build_ci(buell_dir, sa, sb):
    """VS + F7-zone-fusion + GP-gap-fill, shared by _merge_maps (discrete A/B/AVG
    picker) and web/proposal.py (continuous delta-to-EEPROM conversion).

    Returns (ci, delta, stats). ci[key] = {
      'eco': 'A'/'B'/None, 'eco_delta': signed ms delta behind the eco decision
      (None if no decision), 'pw_eff_a'/'pw_eff_b': reference PW at this cell
      (for pct conversion), 'sport': 'A'/'B'/None, 'gp_filled': bool (optional).
    }
    """
    RB=RPM_BINS
    TB=TPS_BINS
    MN=10
    bk=_bin_index
    try:
        vd=_compare_sessions_cached(buell_dir,sa,sb)
        delta=vd.get('delta',[])
        f7_cells=_f7_delta_to_cells(vd.get('f7_matches',[]))
    except Exception:
        delta=[]
        f7_cells={}
    ci={}
    skipped_insig=0
    fused_with_f7=0
    for r in delta:
        if r['na']<MN or r['nb']<MN: continue
        fl=r['flavor']
        if fl not in ('SWEET','SPICY_WOT'): continue
        key=(bk(r['rpm_lo'],RB),bk(r['tps_lo'],TB))
        if key not in ci:
            ci[key]={'eco':None,'eco_delta':None,'sport':None,
                     'pw_eff_a':r.get('pw_eff_a'),'pw_eff_b':r.get('pw_eff_b')}
        if fl=='SWEET':
            # GAP1 gate: only pick an eco winner when the Welch 95% CI on
            # dpw_eff does not cross zero. Without this, a cell could win
            # purely from ride-to-ride noise (see BACKLOG.md GAP 1).
            if not r.get('dpw_eff_sig', False):
                skipped_insig+=1
                continue
            vs_delta=r.get('dpw_eff',0)
            f7c=f7_cells.get(key)
            if f7c and f7c['zone']!='WOT' and f7c['confidence']>0:
                f7_delta=f7c['f7_delta']
                if (vs_delta<0)!=(f7_delta<0):
                    # Signs disagree: bias toward the richer verdict (higher
                    # PW = more fuel = safer in open-loop without a wideband).
                    fused=max(vs_delta,f7_delta)
                else:
                    w=f7c['confidence']
                    fused=(vs_delta+f7_delta*w)/(1.0+w)
                fused_with_f7+=1
                ci[key]['eco']='A' if fused<0 else 'B'
                ci[key]['eco_delta']=fused
            else:
                ci[key]['eco']='A' if vs_delta<0 else 'B'
                ci[key]['eco_delta']=vs_delta
        elif fl=='SPICY_WOT':
            # ddvss has no GAP1-equivalent significance test yet, so the
            # sport winner is still picked from raw sign — gating this needs
            # its own CI calculation (not built; see BACKLOG.md GAP 1).
            ci[key]['sport']='A' if r['ddvss']<0 else 'B'
    filled_by_gp=0
    for key,g in _gpr_predict_grid(delta,'SWEET').items():
        if key in ci: continue  # never override a cell that already has real votes
        margin=1.96*g['std']
        lo,hi=g['mean']-margin,g['mean']+margin
        if not (lo>0 or hi<0): continue  # GP posterior CI crosses zero -- leave unfilled
        ci[key]={'eco':'A' if g['mean']<0 else 'B','eco_delta':g['mean'],
                 'sport':None,'gp_filled':True,'pw_eff_a':None,'pw_eff_b':None}
        filled_by_gp+=1
    stats={'skipped_insignificant':skipped_insig,'fused_with_f7':fused_with_f7,'filled_by_gp':filled_by_gp}
    return ci, delta, stats


def _merge_maps(buell_dir, sa, sb, mode='BALANCE'):
    RB=RPM_BINS
    TB=TPS_BINS
    bk=_bin_index
    ep_a=buell_dir/'sessions'/sa/'eeprom.bin'
    ep_b=buell_dir/'sessions'/sb/'eeprom.bin'
    if not ep_a.exists() or not ep_b.exists():
        return {'error':'eeprom no encontrada','attributable':False}
    mA=_decode_eeprom_maps(ep_a.read_bytes(), _session_version(ep_a))
    mB=_decode_eeprom_maps(ep_b.read_bytes(), _session_version(ep_b))
    FK=['fuel_front','fuel_rear']
    SK=['spark_front','spark_rear']
    fc=[k for k in FK if k in mA and k in mB and _maps_differ(mA[k],mB[k])]
    sc=[k for k in SK if k in mA and k in mB and _maps_differ(mA[k],mB[k])]
    ac=fc+sc
    if not ac:
        return {'error':'No changes between sessions','changed':[],'attributable':False}
    if fc and sc:
        attr=False
    else:
        attr=True
    ci, delta, stats = _build_ci(buell_dir, sa, sb)
    def winner(key):
        info=ci.get(key)
        if not info: return None
        ew,sw=info['eco'],info['sport']
        if mode=='ECO': return ew
        if mode=='SPORT': return sw
        if ew and sw and ew!=sw: return 'AVG'
        return ew or sw
    def m2ck(i,j,ra,la):
        rv=ra[j];lv=la[i]
        if rv==0: return None
        rc=(rv+ra[j+1])/2 if j<len(ra)-1 else (rv+(rv-ra[j-1])/2 if j>0 else rv)
        lc=(lv+la[i+1])/2 if i<len(la)-1 else (lv+(lv-la[i-1])/2 if i>0 else lv)
        if rc<RB[0] or lc<TB[0]: return None
        return (bk(rc,RB),bk(lc,TB))
    result={}
    for ck in ac:
        if ck.startswith('fuel'): ra=mA['axes']['fuel_rpm'];la=mA['axes']['fuel_load']
        else: ra=mA['axes']['spark_rpm'];la=mA['axes']['spark_load']
        rows=len(la);cols=len(ra)
        merged=[];st={'A':0,'B':0,'AVG':0,'ORIG':0}
        for i in range(rows):
            row=[]
            for j in range(cols):
                ck_key=m2ck(i,j,ra,la)
                if ck_key is None:
                    row.append({'v':mA[ck][i][j],'s':'ORIG'});st['ORIG']+=1;continue
                w=winner(ck_key)
                if w is None or w=='AVG':
                    avg=round((mA[ck][i][j]+mB[ck][i][j])/2,1)
                    row.append({'v':avg,'s':'AVG'});st['AVG']+=1
                else:
                    row.append({'v':mA[ck][i][j] if w=='A' else mB[ck][i][j],'s':w});st[w]+=1
            merged.append(row)
        result[ck]={'merged':merged,'axes':{'rpm':ra,'load':la},'stats':st,'base':mA[ck],'mod':mB[ck]}
    return {
        'attributable':attr,'changed':ac,
        'unchanged':[k for k in FK+SK if k not in ac],
        'mode':mode,'cells_with_data':len(ci),
        'skipped_insignificant':stats['skipped_insignificant'],'fused_with_f7':stats['fused_with_f7'],
        'filled_by_gp':stats['filled_by_gp'],'maps':result
    }

def _fmtk(n):
    if n >= 1000: return f"{n/1000:.1f}k"
    return str(n)
CACHE_VERSION = 10  # bumped: removed baro normalization of PW (DDFI2 Alpha-N, v2.7.276)
_cache_lock = threading.Lock()

def _eeprom_to_msq(eeprom, session=''):
    """Serialize eeprom_decoded.json dict to MSQ XML (EcmSpy format, no modifications)."""
    from datetime import datetime, timezone
    maps       = eeprom.get('maps', {})
    axes       = maps.get('axes', {})
    fuel_front = maps.get('fuel_front', [])
    fuel_rear  = maps.get('fuel_rear',  [])
    spark_front= maps.get('spark_front',[])
    spark_rear = maps.get('spark_rear', [])
    fuel_load  = axes.get('fuel_load', [])
    fuel_rpm   = axes.get('fuel_rpm',  [])
    sl         = axes.get('spark_load',[])
    sr         = axes.get('spark_rpm', [])

    def ax1b(v): return '\n'.join('      '+str(x) for x in v)
    def ax2b(v): return '\n'.join('    '+str(x)   for x in v)
    def mapfuel(t):
        return '\n'.join('      '+' '.join(str(int(c)) if c is not None else '0' for c in row) for row in t)
    def mapspark(t):
        return '\n'.join('      '+' '.join('{:.2f}'.format(c) if c is not None else '0.00' for c in row) for row in t)

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    nfl = len(fuel_load); nfr = len(fuel_rpm)
    nsl = len(sl);        nsr = len(sr)
    nff_c = len(fuel_front[0]) if fuel_front else 0
    nfr_c = len(fuel_rear[0])  if fuel_rear  else 0
    nsf_c = len(spark_front[0])if spark_front else 0
    nsr_c = len(spark_rear[0]) if spark_rear  else 0

    lines = [
        '<?xml version="1.0"?>',
        '<msq xmlns="http://www.ecmspy.com/">',
        '  <bibliography author="BuellLogger/'+now+' session='+session+'" writeDate="'+now+'" />',
        '  <versionInfo fileFormat="4" nPages="1" signature="BUEIB" />',
        '  <page number="0">',
        '    <constant name="z_factor">4.00</constant>',
        '    <constant name="tpsBins1" rows="'+str(nfl)+'" units="TPS">',
        ax1b(fuel_load),'</constant>',
        '    <constant name="rpmBins1" rows="'+str(nfr)+'" units="RPM">',
        ax2b(fuel_rpm),'</constant>',
        '    <constant name="veBins1" rows="'+str(len(fuel_front))+'" cols="'+str(nff_c)+'" units="fuel">',
        mapfuel(fuel_front),'','</constant>',
        '    <constant name="tpsBins2" rows="'+str(nfl)+'" units="TPS">',
        ax1b(fuel_load),'</constant>',
        '    <constant name="rpmBins2" rows="'+str(nfr)+'" units="RPM">',
        ax2b(fuel_rpm),'</constant>',
        '    <constant name="veBins2" rows="'+str(len(fuel_rear))+'" cols="'+str(nfr_c)+'" units="fuel">',
        mapfuel(fuel_rear),'','</constant>',
        '    <constant name="tpsBins3" rows="'+str(nsl)+'" units="TPS">',
        ax1b(sl),'</constant>',
        '    <constant name="rpmBins3" rows="'+str(nsr)+'" units="RPM">',
        ax2b(sr),'</constant>',
        '    <constant name="advTable1" rows="'+str(len(spark_front))+'" cols="'+str(nsf_c)+'" units="deg BTDC">',
        mapspark(spark_front),'','</constant>',
        '    <constant name="tpsBins4" rows="'+str(nsl)+'" units="TPS">',
        ax1b(sl),'</constant>',
        '    <constant name="rpmBins4" rows="'+str(nsr)+'" units="RPM">',
        ax2b(sr),'</constant>',
        '    <constant name="advTable2" rows="'+str(len(spark_rear))+'" cols="'+str(nsr_c)+'" units="deg BTDC">',
        mapspark(spark_rear),'','</constant>',
        '  </page>',
        '</msq>',
    ]
    return '\n'.join(lines)


CONVERGENCE_THRESHOLD = 0.002  # ~0.2% PW diff; pairs below this are considered converged


def _pair_residual_variance(buell_dir: Path, sa: str, sb: str) -> dict:
    """Compute residual variance of dpw_eff for one consecutive session pair.

    Returns a dict with keys: session_a, session_b, residual_variance, n_cells, converged.
    residual_variance and converged are None when fewer than 3 valid cells exist.
    """
    try:
        result = _compare_sessions_cached(buell_dir, sa, sb)
    except Exception:
        return {"session_a": sa, "session_b": sb, "residual_variance": None, "n_cells": 0, "converged": None}

    delta = result.get("delta", [])
    values = [row["dpw_eff"] for row in delta if row.get("dpw_eff") is not None]
    n = len(values)

    if n < 3:
        return {"session_a": sa, "session_b": sb, "residual_variance": None, "n_cells": n, "converged": None}

    variance = sum(v * v for v in values) / n
    return {
        "session_a": sa,
        "session_b": sb,
        "residual_variance": round(variance, 6),
        "n_cells": n,
        "converged": variance < CONVERGENCE_THRESHOLD,
    }


def _count_trailing_converged(pairs: list) -> int:
    """Count how many recent consecutive pairs have converged=True (from the end)."""
    count = 0
    for pair in reversed(pairs):
        if pair.get("converged") is True:
            count += 1
        else:
            break
    return count


def compute_convergence(buell_dir: str, session_ids: list) -> dict:
    """Compute map convergence across consecutive session pairs.

    Args:
        buell_dir: Root directory of the buell project (str or Path).
        session_ids: Ordered list of session IDs (oldest first). Minimum 2.

    Returns:
        Dict with keys: pairs, global_variance, converged, threshold, consecutive_converged.
    """
    buell_path = Path(buell_dir)
    pairs = [
        _pair_residual_variance(buell_path, session_ids[i], session_ids[i + 1])
        for i in range(len(session_ids) - 1)
    ]

    # global_variance: mean of last min(3, n_pairs) valid residual_variances
    recent = [p["residual_variance"] for p in pairs[-3:] if p["residual_variance"] is not None]
    global_variance = round(sum(recent) / len(recent), 6) if recent else None

    consecutive_converged = _count_trailing_converged(pairs)
    # Overall converged: last 3 consecutive pairs all converged (or all pairs if fewer than 3)
    n_check = min(3, len(pairs))
    tail = pairs[-n_check:] if n_check else []
    converged = bool(tail) and all(p.get("converged") is True for p in tail)

    return {
        "pairs": pairs,
        "global_variance": global_variance,
        "converged": converged,
        "threshold": CONVERGENCE_THRESHOLD,
        "consecutive_converged": consecutive_converged,
    }


def _compare_sessions_cached(buell_dir, sa, sb):
    import json as _json
    def _meta(sid):
        mp = buell_dir / 'sessions' / sid / 'session_metadata.json'
        if mp.exists():
            with open(mp) as f: return json.load(f)
        return {}
    ma, mb = _meta(sa), _meta(sb)
    # Block comparison when fuel map dimensions differ (DDFI-2 vs DDFI-3)
    _va = ma.get("version_string", "")
    _vb = mb.get("version_string", "")
    _ia = _resolve_ecu(_va) if _va else None
    _ib = _resolve_ecu(_vb) if _vb else None
    _da = _ia.get("ddfi") if _ia else None
    _db = _ib.get("ddfi") if _ib else None
    if _da and _db and _da != _db:
        _na = _va.split()[0] if _va else "?"
        _nb = _vb.split()[0] if _vb else "?"
        return {"error": f"Map mismatch: {_da} ({_na}) vs {_db} ({_nb}) — incompatible fuel map dimensions",
                "map_mismatch": True, "ddfi_a": _da, "ddfi_b": _db,
                "same_bike": False, "common": 0, "cells": [], "delta": []}
    fname = f"sessions_vs_v{CACHE_VERSION}_{sa}-{_fmtk(ma.get('total_samples',0))}_{sb}-{_fmtk(mb.get('total_samples',0))}.json"
    cache_dir = buell_dir / 'sessions' / '_cache'
    cache_file = cache_dir / fname
    if cache_file.exists():
        try:
            with _cache_lock:
                if not cache_file.exists():
                    raise FileNotFoundError
                with open(cache_file) as _cf:
                    cached = json.load(_cf)
            # Accept cached data even without clusters_a (legacy caches)
            if 'sa' in cached and 'clusters_a' in cached and cached.get('_cache_version') == CACHE_VERSION:
                return cached
        except Exception:
            pass
    result = _compare_sessions(buell_dir, sa, sb)
    result["_cache_version"] = CACHE_VERSION
    cache_dir.mkdir(parents=True, exist_ok=True)
    with _cache_lock:
        with open(cache_file, 'w') as f:
            json.dump(result, f)
        # Remove stale versions of the same session pair
        pair_suffix = f"{sa}-{_fmtk(ma.get('total_samples',0))}_{sb}-{_fmtk(mb.get('total_samples',0))}.json"
        for stale in cache_dir.glob(f"sessions_vs_v*_{pair_suffix}"):
            if stale != cache_file:
                stale.unlink(missing_ok=True)
    return result




