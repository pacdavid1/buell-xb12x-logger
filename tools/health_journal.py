import json, os, time

HEALTH_FILE = '/home/pi/buell/system_health.json'
MAX_ENTRIES = 100
COOLDOWN = 300

def check(serial_stats, ecu_alive):
    data = {'issues': [], 'counts': {}, 'last_seen': {}}
    if os.path.exists(HEALTH_FILE):
        try:
            with open(HEALTH_FILE) as f:
                data = json.load(f)
        except Exception:
            pass
    now = time.time()
    new = []
    v = serial_stats.get('bat_voltage')
    soc = serial_stats.get('bat_soc')
    if v is not None and v < 3.15:
        new.append(('bat', 'CRIT', f'{v:.2f}V', 'Battery critical'))
    elif v is not None and v < 3.5:
        new.append(('bat', 'WARN', f'{v:.2f}V', 'Battery low'))
    if soc is not None and soc < 10:
        new.append(('bat_soc', 'CRIT', f'{soc:.0f}%', 'SOC critical'))
    elif soc is not None and soc < 30:
        new.append(('bat_soc', 'WARN', f'{soc:.0f}%', 'SOC low'))
    t = serial_stats.get('cpu_temp')
    if t is not None and t > 85:
        new.append(('cpu_temp', 'CRIT', f'{t:.1f}C', 'CPU overheating'))
    elif t is not None and t > 75:
        new.append(('cpu_temp', 'WARN', f'{t:.1f}C', 'CPU hot'))
    if not ecu_alive:
        new.append(('ecu', 'WARN', 'No', 'ECU disconnected'))
    for typ, sev, val, desc in new:
        key = typ + sev
        if now - data.get('last_seen', {}).get(key, 0) < COOLDOWN:
            continue
        data.setdefault('issues', []).append({'ts': now, 'type': typ, 'severity': sev, 'value': val, 'desc': desc})
        data.setdefault('counts', {})[key] = data['counts'].get(key, 0) + 1
        data.setdefault('last_seen', {})[key] = now
    if len(data['issues']) > MAX_ENTRIES:
        data['issues'] = data['issues'][-MAX_ENTRIES:]
    with open(HEALTH_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_summary():
    data = {}
    if os.path.exists(HEALTH_FILE):
        try:
            with open(HEALTH_FILE) as f:
                data = json.load(f)
        except Exception:
            data = {}
    recent = []
    for i in data.get('issues', []):
        if time.time() - i['ts'] < 86400:
            recent.append(i)
    crits = [i for i in recent if i.get('severity') == 'CRIT']
    return {'issues_24h': len(recent), 'crits': len(crits), 'latest': recent[-1] if recent else None}

if __name__ == '__main__':
    ss = {'bat_voltage': 3.1, 'bat_soc': 4, 'cpu_temp': 45}
    check(ss, True)
    print(json.dumps(get_summary(), indent=2))
    print('Test passed - system_health.json created')
