#!/usr/bin/env python3
import logging, threading, time, socket, json, math
logger = logging.getLogger("GPS")
GPSD_HOST = "127.0.0.1"
GPSD_PORT = 2947

class GPSConfig:
    """Dynamic configuration for GPSReader."""
    __slots__ = ("stale_timeout", "turn_rate_threshold", "min_snr")
    def __init__(self, stale_timeout=5.0, turn_rate_threshold=30.0, min_snr=0):
        self.stale_timeout = stale_timeout
        self.turn_rate_threshold = turn_rate_threshold
        self.min_snr = min_snr
    def as_dict(self):
        return {"stale_timeout": self.stale_timeout,
                "turn_rate_threshold": self.turn_rate_threshold,
                "min_snr": self.min_snr}

class GPSFix:
    __slots__ = ("lat","lon","alt_m","speed_kmh","heading","satellites","timestamp_utc","valid",
                 "epx","epy","epv","mode","stale","stale_ts",
                 "snr_avg","heading_rate","turning","heading_prev","heading_ts")
    def __init__(self):
        self.lat=None;self.lon=None;self.alt_m=None;self.speed_kmh=None
        self.heading=None;self.satellites=0;self.timestamp_utc=None;self.valid=False
        self.epx=None;self.epy=None;self.epv=None;self.mode=0;self.stale=False;self.stale_ts=0.0
        self.snr_avg=None;self.heading_rate=None;self.turning=False
        self.heading_prev=None;self.heading_ts=0.0
    def as_dict(self):
        d={"gps_lat":round(self.lat,6) if self.lat is not None else None,
           "gps_lon":round(self.lon,6) if self.lon is not None else None,
           "gps_alt_m":round(self.alt_m,1) if self.alt_m is not None else None,
           "gps_speed_kmh":round(self.speed_kmh,1) if self.speed_kmh is not None else None,
           "gps_heading":round(self.heading,1) if self.heading is not None else None,
           "gps_satellites":self.satellites,
           "gps_valid":self.valid,
           "gps_mode":self.mode}
        if self.epx is not None: d["gps_epx"]=round(self.epx,2)
        if self.epy is not None: d["gps_epy"]=round(self.epy,2)
        if self.epv is not None: d["gps_epv"]=round(self.epv,2)
        if self.snr_avg is not None: d["gps_snr_avg"]=round(self.snr_avg,1)
        if self.heading_rate is not None: d["gps_heading_rate"]=round(self.heading_rate,1)
        d["gps_turning"]=self.turning
        d["gps_stale"]=self.stale
        return d

class GPSReader:
    def __init__(self, host=GPSD_HOST, port=GPSD_PORT, config=None):
        self.host=host;self.port=port
        self.config=config if config is not None else GPSConfig()
        self._lock=threading.Lock();self._fix=GPSFix()
        self._stop=threading.Event()
        self._thread=threading.Thread(target=self._run,name="GPSReader",daemon=True)
        self.running=False
    def start(self):
        self._stop.clear();self._thread.start();self.running=True
        logger.info(f"GPS reader iniciado via gpsd {self.host}:{self.port}")
    def stop(self):
        self._stop.set();self.running=False;logger.info("GPS reader detenido")
    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()
    def get_fix(self):
        with self._lock:
            f=GPSFix()
            for s in GPSFix.__slots__: setattr(f,s,getattr(self._fix,s))
            # Compute stale using config timeout
            f.stale = True if f.stale_ts<=0 else time.time()-f.stale_ts > self.config.stale_timeout
            return f
    def get_config(self):
        return self.config
    def set_config(self, **kwargs):
        for k,v in kwargs.items():
            if hasattr(self.config, k):
                setattr(self.config, k, v)
        logger.info(f"GPS config updated: {kwargs}")
    def _update_heading_rate(self, heading, ts):
        """Calculate heading rate of change (deg/s). Detects turns."""
        prev = self._fix.heading_prev
        pts = self._fix.heading_ts
        if prev is not None and pts > 0 and ts > pts:
            dt = ts - pts
            if dt > 0:
                # Handle heading wrap (0-360)
                d = heading - prev
                if d > 180: d -= 360
                elif d < -180: d += 360
                rate = abs(d) / dt
                self._fix.heading_rate = rate
                self._fix.turning = rate >= self.config.turn_rate_threshold
            else:
                self._fix.heading_rate = None
                self._fix.turning = False
        else:
            self._fix.heading_rate = None
            self._fix.turning = False
        self._fix.heading_prev = heading
        self._fix.heading_ts = ts
    def _snr_from_sat_list(self, sat_list):
        """Average SNR of used satellites with valid signal."""
        used = [s.get('ss', 0) for s in sat_list if s.get('used') and s.get('ss', 0) > 0]
        return sum(used) / len(used) if used else None
    def _run(self):
        while not self._stop.is_set():
            try:
                sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                sock.connect((self.host,self.port));sock.settimeout(5.0)
                sf=sock.makefile('r')
                sock.sendall(b'?WATCH={"enable":true,"json":true}\n')
                logger.info("Conectado a gpsd")
                while not self._stop.is_set():
                    line=sf.readline()
                    if not line: break
                    try: msg=json.loads(line)
                    except Exception as e: logger.debug(f"gpsd parse: {e}"); continue
                    cls=msg.get('class')
                    if cls=='TPV':
                        with self._lock:
                            self._fix.mode=msg.get('mode',0)
                            valid=self._fix.mode>=2
                            self._fix.valid=valid
                            if valid:
                                if 'lat' in msg: self._fix.lat=msg['lat']
                                if 'lon' in msg: self._fix.lon=msg['lon']
                                if 'altMSL' in msg: self._fix.alt_m=msg['altMSL']
                                elif 'alt' in msg: self._fix.alt_m=msg['alt']
                                spd=msg.get('speed',0)
                                self._fix.speed_kmh=round(spd*3.6,1) if spd else 0.0
                                if 'track' in msg: self._fix.heading=msg['track']
                                if 'time' in msg: self._fix.timestamp_utc=msg['time']
                                if 'epx' in msg: self._fix.epx=msg['epx']
                                if 'epy' in msg: self._fix.epy=msg['epy']
                                if 'epv' in msg: self._fix.epv=msg['epv']
                                self._fix.stale_ts=time.time()
                                if self._fix.heading is not None:
                                    self._update_heading_rate(self._fix.heading, time.time())
                            else:
                                self._fix.speed_kmh=0.0
                                self._fix.epx=None;self._fix.epy=None;self._fix.epv=None
                    elif cls=='SKY':
                        sat_list=msg.get('satellites',[])
                        usat=msg.get('uSat')
                        with self._lock:
                            if usat is not None:
                                self._fix.satellites=int(usat)
                            elif sat_list:
                                self._fix.satellites=sum(1 for s in sat_list if s.get('used'))
                            snr = self._snr_from_sat_list(sat_list)
                            self._fix.snr_avg = snr
                            if self.config.min_snr > 0 and snr is not None and snr < self.config.min_snr:
                                self._fix.valid = False
                sock.close()
            except Exception as e:
                logger.warning(f"GPS gpsd error: {e} --- reintentando en 3s")
                time.sleep(3)
