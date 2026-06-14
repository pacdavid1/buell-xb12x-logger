# DEV NOTE: All code, comments, and variable names must be in English.
import csv
import datetime
import io
import json
import logging
import urllib.parse
import zlib
from pathlib import Path

from web.utils import _get_version

_TEMPLATES = Path(__file__).resolve().parent.parent / 'templates'


class RidesHandlerMixin:
    def _handle_index(self, path=None):
        self._html(self._load_html())

    def _handle_live_json(self, path=None):
        self._json(self._get_live())

    def _handle_rides(self, path=None):
        self._json({'rides': self.server_instance._get_rides()})

    def _handle_ride_launch_event(self, path=None):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            session_dir = (self.server_instance.session.current_session_dir
                           if self.server_instance.session else None)
            if session_dir and isinstance(body, dict):
                body['captured_utc'] = datetime.datetime.utcnow().isoformat() + 'Z'
                log_path = session_dir / 'launch_events.jsonl'
                with open(log_path, 'a') as f:
                    f.write(json.dumps(body) + '\n')
            self._json({'ok': True})
        except Exception as e:
            logging.getLogger('WebServer').warning('launch_event save failed: %s', e)
            self._json({'ok': False, 'error': str(e)})

    def _handle_coverage_json(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        fmt = params.get('format', [None])[0]
        report = self.server_instance._get_coverage()
        if fmt == 'csv':
            cells = report.get('cells', {})
            flavors = list(report.get('summary', {}).keys())
            buf = io.StringIO()
            w = csv.writer(buf)
            header = ['cell', 'seconds', 'ego_avg', 'confidence']
            for fl in flavors:
                header += [fl + '_s', fl + '_pct', fl + '_done']
            w.writerow(header)
            for key, cell in sorted(cells.items()):
                row = [key, cell.get('seconds', 0), cell.get('ego_avg', 100),
                       cell.get('confidence', 0)]
                for fl in flavors:
                    fd = cell.get('flavors', {}).get(fl, {})
                    row += [fd.get('seconds', 0), fd.get('pct', 0),
                            1 if fd.get('done') else 0]
                w.writerow(row)
            body = buf.getvalue().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename=coverage.csv')
            self.end_headers()
            self.wfile.write(body)
            return
        self._json(report)

    def _handle_coverage_targets(self, path=None):
        try:
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if not isinstance(body, dict):
                self._json({'error': 'expected JSON object'}, 400)
                return
            self.server_instance._set_coverage_targets(body)
            self._json({'ok': True})
        except Exception as e:
            self._json({'error': str(e)}, 400)

    def _handle_csv(self, path=None):
        fname = path.split('/csv/')[-1].split('?')[0]
        rides = self.server_instance._get_rides()
        fname_summary = fname.replace('.csv', '_summary.json')
        match = next((r for r in rides if r['filename'] == fname or r['filename'] == fname_summary), None)
        if not match:
            self._json({'error': 'not found'}, 404)
            return
        try:
            sdir = self.server_instance.buell_dir / 'sessions' / match['session']
            parts = match.get('parts', 1)
            chunks = []
            first = True
            for part in range(1, parts + 1):
                suffix = f'_p{part}' if part > 1 else ''
                csv_stem = match['filename'].replace('_summary.json', '').replace('.csv', '')
                csv_path = sdir / f'{csv_stem}{suffix}.csv'
                if not csv_path.exists():
                    continue
                with open(csv_path, 'rb') as fh:
                    if not first:
                        fh.readline()
                        fh.readline()
                    chunks.append(fh.read())
                first = False
            if not chunks:
                self._json({'error': 'CSV file not found for this ride'}, 404)
                return
            raw = b''.join(chunks)
            use_gzip = 'gzip' in self.headers.get('Accept-Encoding', '')
            body = zlib.compress(raw, level=6, wbits=31) if use_gzip else raw
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            if use_gzip:
                self.send_header('Content-Encoding', 'gzip')
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle_ride(self, path=None):
        fname = path.split('/ride/')[-1].split('?')[0]
        rides = self.server_instance._get_rides()
        fname_summary = fname.replace('.csv', '_summary.json')
        match = next((r for r in rides if r['filename'] == fname or r['filename'] == fname_summary), None)
        if not match:
            self._json({'error': 'not found'}, 404)
            return
        sdir = self.server_instance.buell_dir / 'sessions' / match['session']
        fpath = sdir / fname
        if not fpath.exists():
            fpath = sdir / fname.replace('_summary.json', '.csv')
        try:
            if fpath.suffix == '.json':
                with open(fpath) as fh:
                    s = json.load(fh)
                self._json({'cells': s.get('cells', {}), 'objectives': s.get('objectives', [])})
            else:
                self._json({'cells': {}, 'objectives': []})
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle_graf2(self, path=None):
        try:
            html = (_TEMPLATES / 'graf2.html').read_text(encoding='utf-8')
            self._html(html.replace('--LOGGER_VERSION--', _get_version()))
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _annotations_path(self, ride):
        if not ride:
            return None
        rides = self.server_instance._get_rides()
        fname_summary = ride.replace('.csv', '_summary.json')
        match = next((x for x in rides if x['filename'] == ride or x['filename'] == fname_summary), None)
        if not match:
            return None
        sdir = self.server_instance.buell_dir / 'sessions' / match['session']
        stem = ride.replace('_summary.json', '').replace('.csv', '')
        return sdir / (stem + '_annotations.json')

    def _load_annotations(self, ride):
        ann_path = self._annotations_path(ride)
        if ann_path is None:
            return None, None
        if ann_path.exists():
            try:
                with open(ann_path) as fh:
                    return ann_path, json.load(fh)
            except Exception:
                pass
        return ann_path, {'ride': ride, 'annotations': []}

    def _handle_annotations(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        ride = params.get('ride', [''])[0]
        ann_path, data = self._load_annotations(ride)
        if ann_path is None:
            self._json({'error': 'ride not found'}, 404)
            return
        self._json(data)

    def _handle_post_annotations(self, path=None, payload=None):
        payload = payload or {}
        ride = payload.get('ride', '')
        ann_path, data = self._load_annotations(ride)
        if ann_path is None:
            self._json({'error': 'ride not found'}, 404)
            return
        if payload.get('action') == 'delete':
            aid = str(payload.get('id', ''))
            data['annotations'] = [a for a in data['annotations'] if str(a.get('id')) != aid]
        else:
            try:
                t0 = float(payload.get('t0_s', 0))
                t1 = float(payload.get('t1_s', 0))
            except (TypeError, ValueError):
                self._json({'error': 'invalid t0_s/t1_s'}, 400)
                return
            if t1 < t0:
                t0, t1 = t1, t0
            data['annotations'].append({
                'id': str(payload.get('id') or datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')),
                't0_s': round(t0, 3),
                't1_s': round(t1, 3),
                'note': str(payload.get('note', ''))[:500],
                'created_utc': datetime.datetime.utcnow().isoformat() + 'Z',
            })
        try:
            tmp = ann_path.with_name(ann_path.name + '.tmp')
            with open(tmp, 'w') as fh:
                json.dump(data, fh, indent=2)
            tmp.replace(ann_path)
        except Exception as e:
            self._json({'error': str(e)}, 500)
            return
        self._json({'ok': True, 'annotations': data['annotations']})

    def _handle_errorlog_viz(self, path=None):
        try:
            html = (_TEMPLATES / 'errorlog_viz.html').read_text(encoding='utf-8')
            self._html(html.replace('--LOGGER_VERSION--', _get_version()))
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle_errorlog(self, path=None):
        parts = path.split('/errorlog/')[-1].split('?')[0].strip('/').split('/')
        if len(parts) >= 2:
            session = parts[0]
            fname = parts[1]
        else:
            fname = parts[0] if parts else ''
            session = None
        rides = self.server_instance._get_rides()
        ride_num = int(fname.replace('_errorlog.json', '').replace('ride_', '').replace('.csv', '')) if fname else 0
        match = None
        if session:
            match = next((r for r in rides if r.get('ride_num') == ride_num and r.get('session') == session), None)
        if not match:
            match = next((r for r in rides if r.get('ride_num') == ride_num), None)
        if not match:
            self._json({'error': 'not found'}, 404)
            return
        sdir = self.server_instance.buell_dir / 'sessions' / match['session']
        el_path = sdir / f'ride_{ride_num:03d}_errorlog.json'
        if el_path.exists():
            try:
                with open(el_path) as fh:
                    self._json(json.load(fh))
            except Exception as e:
                self._json({'error': str(e)}, 500)
        else:
            self._json({'has_errorlog': False, 'events': [], 'summary': {}})

    def _handle_ride_note(self, path=None):
        try:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            session_id = params.get('session', [''])[0]
            ride_num = int(params.get('ride', [0])[0])
            note_path = (self.server_instance.buell_dir / 'sessions' / session_id /
                         f'ride_{session_id}_{ride_num:03d}_notes.txt')
            note = note_path.read_text(encoding='utf-8') if note_path.exists() else ''
            self._json({'ok': True, 'note': note})
        except Exception as e:
            self._json({'ok': False, 'note': '', 'error': str(e)})

    def _handle_post_ride_note(self, path, payload):
        try:
            session_id = payload.get('session', '')
            ride_num = int(payload.get('ride_num', 0))
            note = payload.get('note', '').strip()
            note_path = (self.server_instance.buell_dir / 'sessions' / session_id /
                         f'ride_{session_id}_{ride_num:03d}_notes.txt')
            note_path.write_text(note, encoding='utf-8')
            self._json({'ok': True})
        except Exception as e:
            self._json({'ok': False, 'error': str(e)})

    def _handle_tuning_report(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        fmt = params.get('format', [None])[0]
        session = params.get('session', [None])[0]
        if not session:
            session = self.server_instance.session.current_checksum
        if not session:
            self._json({'error': 'no session specified and no active session'})
            return
        report_path = (self.server_instance.buell_dir / 'sessions' / session /
                       f'tuning_report_{session}.json')
        if not report_path.exists():
            self._json({'error': 'no tuning report for this session'})
            return
        try:
            report = json.loads(report_path.read_text())
        except Exception as e:
            self._json({'error': f'tuning report corrupted: {e}'}, 500)
            return
        if fmt == 'csv':
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(['rpm', 'load', 'seconds', 'count', 'ego_sum', 'clt_sum',
                        'wue_sum', 'afv_sum', 'valid_seconds', 'valid_ego_sum',
                        'valid_count', 'inv_reasons'])
            for key, cell in sorted(report.get('agg_cells', {}).items()):
                kparts = key.split('_')
                rpm = kparts[0] if len(kparts) == 2 else key
                load = kparts[1] if len(kparts) == 2 else ''
                inv_str = '; '.join(f'{k}:{v}' for k, v in cell.get('inv_reasons', {}).items())
                w.writerow([rpm, load, cell.get('seconds', 0), cell.get('count', 0),
                            cell.get('ego_sum', 0), cell.get('clt_sum', 0),
                            cell.get('wue_sum', 0), cell.get('afv_sum', 0),
                            cell.get('valid_seconds', 0), cell.get('valid_ego_sum', 0),
                            cell.get('valid_count', 0), inv_str])
            body = buf.getvalue().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename=tuning_report_{session}.csv')
            self.end_headers()
            self.wfile.write(body)
            return
        self._json(report)
