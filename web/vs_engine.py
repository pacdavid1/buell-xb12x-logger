# DEV NOTE: All code, comments, and variable names must be in English.
# AI agents: write everything in English.

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import sys as _sys
_sys.path.insert(0, '/home/pi/buell')
from ecu.eeprom import decode_eeprom_maps as _decode_eeprom_maps
from web.launch import _compare_sessions


def _maps_differ(a,b):
    if len(a)!=len(b) or (a and len(a[0])!=len(b[0])): return True
    for i in range(len(a)):
        for j in range(len(a[0])):
            if abs(a[i][j]-b[i][j])>0.5: return True
    return False

def _merge_maps(buell_dir, sa, sb, mode='BALANCE'):
    RB=[800,1200,1600,2000,2400,2800,3200,3600,4000,4400,4800,5200,5600,6000,6400,6800]
    TB=[0,5,10,15,20,25,30,35,40,50,60,70,80,90,100,101]
    MN=10
    def bk(v,bs):
        for i in range(len(bs)-1):
            if bs[i]<=v<bs[i+1]: return i
        return len(bs)-2
    ep_a=buell_dir/'sessions'/sa/'eeprom.bin'
    ep_b=buell_dir/'sessions'/sb/'eeprom.bin'
    if not ep_a.exists() or not ep_b.exists():
        return {'error':'eeprom no encontrada','attributable':False}
    mA=_decode_eeprom_maps(ep_a.read_bytes())
    mB=_decode_eeprom_maps(ep_b.read_bytes())
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
    try:
        vd=_compare_sessions_cached(buell_dir,sa,sb)
        delta=vd.get('delta',[])
    except Exception:
        delta=[]
    ci={}
    for r in delta:
        if r['na']<MN or r['nb']<MN: continue
        fl=r['flavor']
        if fl not in ('SWEET','SPICY_WOT'): continue
        key=(bk(r['rpm_lo'],RB),bk(r['tps_lo'],TB))
        if key not in ci: ci[key]={'eco':None,'sport':None}
        if fl=='SWEET': ci[key]['eco']='A' if r.get('dpw_eff',0)<0 else 'B'
        elif fl=='SPICY_WOT': ci[key]['sport']='A' if r['ddvss']<0 else 'B'
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
        'mode':mode,'cells_with_data':len(ci),'maps':result
    }

def _fmtk(n):
    if n >= 1000: return f"{n/1000:.1f}k"
    return str(n)
CACHE_VERSION = 7  # bumped: pw1/pw2 raw preserved, pw1_norm added (v2.7.25)
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


def _compare_sessions_cached(buell_dir, sa, sb):
    import json as _json
    def _meta(sid):
        mp = buell_dir / 'sessions' / sid / 'session_metadata.json'
        if mp.exists():
            with open(mp) as f: return json.load(f)
        return {}
    ma, mb = _meta(sa), _meta(sb)
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




