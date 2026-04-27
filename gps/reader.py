#!/usr/bin/env python3
import logging, threading, time, socket, json
logger = logging.getLogger("GPS")
GPSD_HOST = "127.0.0.1"
GPSD_PORT = 2947
class GPSFix:
    __slots__ = ("lat","lon","alt_m","speed_kmh","heading","satellites","timestamp_utc","valid")
    def __init__(self):
        self.lat=None;self.lon=None;self.alt_m=None;self.speed_kmh=None
        self.heading=None;self.satellites=0;self.timestamp_utc=None;self.valid=False
    def as_dict(self):
        return {"gps_lat":round(self.lat,6) if self.lat is not None else None,"gps_lon":round(self.lon,6) if self.lon is not None else None,"gps_alt_m":round(self.alt_m,1) if self.alt_m is not None else None,"gps_speed_kmh":round(self.speed_kmh,1) if self.speed_kmh is not None else None,"gps_heading":round(self.heading,1) if self.heading is not None else None,"gps_satellites":self.satellites,"gps_valid":self.valid}
class GPSReader:
    def __init__(self,host=GPSD_HOST,port=GPSD_PORT):
        self.host=host;self.port=port;self._lock=threading.Lock();self._fix=GPSFix()
        self._stop=threading.Event();self._thread=threading.Thread(target=self._run,name="GPSReader",daemon=True);self.running=False
    def start(self):
        self._stop.clear();self._thread.start();self.running=True
        logger.info(f"GPS reader iniciado via gpsd {self.host}:{self.port}")
    def stop(self):
        self._stop.set();self.running=False;logger.info("GPS reader detenido")
    def get_fix(self):
        with self._lock:
            f=GPSFix()
            for s in GPSFix.__slots__: setattr(f,s,getattr(self._fix,s))
            return f
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
                    except: continue
                    cls=msg.get('class')
                    if cls=='TPV':
                        valid=msg.get('mode',0)>=2
                        with self._lock:
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
                            else: self._fix.speed_kmh=0.0
                    elif cls=='SKY':
                        sats=sum(1 for s in msg.get('satellites',[]) if s.get('used'))
                        with self._lock: self._fix.satellites=sats
                sock.close()
            except Exception as e:
                logger.warning(f"GPS gpsd error: {e} — reintentando en 3s");time.sleep(3)
