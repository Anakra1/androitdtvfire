"""Temporary, paired source setup page served by Kodi on the home network."""
from collections import defaultdict
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import threading
import time
from urllib.parse import urlsplit

from .core import Store, fetch_json, normalize_url, validate_manifest
from .programmes import COUNTRIES, settings as programme_settings, save_settings as save_programme_settings, save_feed, request_refresh
from . import pvr


class SetupServer:
    def __init__(self, store, assets, address, host='0.0.0.0', port=8768, lifetime=600, fetch=fetch_json):
        address = str(ipaddress.IPv4Address(address))
        self.store, self.assets, self.fetch = store, assets, fetch
        self.code = '{:06d}'.format(secrets.randbelow(1000000))
        self.expires = time.time() + lifetime
        self.closed = False
        self.sessions, self.failures = set(), defaultdict(list)
        self.lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def log_message(self, *args):
                pass  # Provider URLs and pairing credentials must not enter logs.

            def reply(self, status, data, content_type='application/json', cookie=None):
                raw = json.dumps(data).encode('utf-8') if content_type == 'application/json' else data
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
                if cookie:
                    self.send_header('Set-Cookie', cookie)
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def allowed(self):
                if not owner.active:
                    self.reply(410, {'error': 'Source setup has closed. Open it again in CBR.'})
                    return False
                if self.headers.get('Host', '').lower() not in owner.hosts:
                    self.reply(403, {'error': 'Invalid setup address.'})
                    return False
                origin = self.headers.get('Origin')
                if origin and origin != 'http://' + self.headers.get('Host', ''):
                    self.reply(403, {'error': 'Open the setup page directly in your browser.'})
                    return False
                return True

            def paired(self):
                cookie = SimpleCookie()
                try:
                    cookie.load(self.headers.get('Cookie', ''))
                    token = cookie['cbr_setup'].value
                except (KeyError, ValueError, CookieError):
                    token = ''
                if token not in owner.sessions:
                    self.reply(401, {'error': 'Enter the pairing code shown in Kodi.'})
                    return False
                return True

            def do_GET(self):
                if not self.allowed():
                    return
                if self.path == '/api/sources':
                    if self.paired():
                        self.reply(200, {'sources': owner.sources(), 'seconds': max(0, int(owner.expires - time.time()))})
                    return
                if self.path == '/api/programmes':
                    if self.paired():
                        self.reply(200, {'settings': programme_settings(owner.store), 'countries': COUNTRIES,
                                         'status': owner.store.read(os.path.join(owner.store.root, 'programme-status.json'), {})})
                    return
                if self.path == '/api/pvr':
                    if self.paired():
                        self.reply(200, {'config': pvr.config(owner.store), 'groups': pvr.GROUPS,
                            'sources': [{key: source[key] for key in ('key', 'label', 'default')} for source in pvr.sources(owner.store)],
                            'status': owner.store.read(os.path.join(owner.store.root, 'pvr-status.json'), {}),
                            **pvr.editor(owner.store)})
                    return
                assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                          '/setup.js': ('setup.js', 'text/javascript; charset=utf-8'),
                          '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if self.path not in assets:
                    self.reply(404, {'error': 'Page not found.'})
                    return
                filename, kind = assets[self.path]
                with open(os.path.join(owner.assets, filename), 'rb') as source:
                    self.reply(200, source.read(), kind)

            def do_POST(self):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if length < 1 or length > 65536:
                        raise ValueError('Request is too large or empty.')
                    # Consume bounded request bodies before rejecting headers.
                    # Closing with unread bytes can reset the connection on
                    # Windows and discard the useful error response.
                    raw = self.rfile.read(length)
                    if not self.allowed():
                        return
                    if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                        self.reply(415, {'error': 'Expected JSON.'})
                        return
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        raise ValueError('Invalid request.')
                except (ValueError, UnicodeDecodeError, OSError):
                    self.reply(400, {'error': 'Invalid setup request.'})
                    return
                if self.path == '/api/pair':
                    now = time.time()
                    attempts = owner.failures[self.client_address[0]]
                    attempts[:] = [stamp for stamp in attempts if stamp > now - 60]
                    if len(attempts) >= 5:
                        self.reply(429, {'error': 'Too many attempts. Wait one minute and try again.'})
                        return
                    if not hmac.compare_digest(str(data.get('code', '')), owner.code):
                        attempts.append(now)
                        self.reply(403, {'error': 'That code does not match the code on your TV.'})
                        return
                    token = secrets.token_urlsafe(32)
                    owner.sessions.add(token)
                    self.reply(200, {'paired': True}, cookie='cbr_setup={}; Path=/; HttpOnly; SameSite=Strict; Max-Age=600'.format(token))
                    return
                if not self.paired():
                    return
                try:
                    with owner.lock:
                        if self.path == '/api/save':
                            owner.save(data)
                            result = {'message': 'Source saved. Return to CBR and reopen its catalogue.'}
                        elif self.path == '/api/remove':
                            owner.store.save_providers([entry for entry in owner.store.providers() if entry['key'] != data.get('key')])
                            result = {'message': 'Source removed.'}
                        elif self.path == '/api/refresh':
                            result = owner.refresh()
                        elif self.path == '/api/programmes/save':
                            save_feed(owner.store, data)
                            result = {'message': 'Programme feed saved. Schedules will update in the background.'}
                        elif self.path == '/api/programmes/remove':
                            config = programme_settings(owner.store)
                            config['feeds'] = [f for f in config['feeds'] if f['key'] != data.get('key')]
                            save_programme_settings(owner.store, config)
                            result = {'message': 'Programme feed removed. Your streaming sources are unchanged.'}
                        elif self.path == '/api/programmes/refresh':
                            request_refresh(owner.store)
                            result = {'message': 'Programme update requested. Return to Kodi and reopen the channel list shortly.'}
                        elif self.path == '/api/pvr/sources':
                            selected = data.get('selected')
                            valid = {s['key'] for s in pvr.sources(owner.store)}
                            if not isinstance(selected, list) or not selected or any(not isinstance(key, str) or key not in valid for key in selected):
                                raise ValueError('Select at least one available TV source.')
                            value = pvr.config(owner.store)
                            value['selected'] = list(dict.fromkeys(selected))
                            pvr.save_config(owner.store, value)
                            pvr.refresh(owner.store)
                            result = {'message': 'TV sources saved. Channels will rebuild in the background.'}
                        elif self.path == '/api/pvr/refresh':
                            pvr.refresh(owner.store)
                            result = {'message': 'Kodi TV channels and guide will update in the background.'}
                        elif self.path == '/api/pvr/channels':
                            edits = data.get('channels')
                            if not isinstance(edits, list) or len(edits) > 100:
                                raise ValueError('Save up to 100 channel edits at a time.')
                            pvr.save_channels(owner.store, edits)
                            result = {'message': 'Channel changes saved. IPTV Simple will read them on its next refresh; restart Kodi to apply sooner.'}
                        elif self.path == '/api/pvr/guide':
                            pvr.save_mapping(owner.store, data.get('id'), data.get('mapping'))
                            result = {'message': 'Programme match saved. The guide will rebuild in the background. Restart Kodi to apply it sooner.'}
                        else:
                            self.reply(404, {'error': 'Unknown setup action.'})
                            return
                    self.reply(200, result)
                except ValueError as error:
                    self.reply(400, {'error': str(error)})
                except Exception:
                    self.reply(502, {'error': 'The provider could not be reached. Check the manifest URL and try again.'})

        self.http = ThreadingHTTPServer((host, port), Handler)
        self.http.daemon_threads = True
        self.port = self.http.server_address[1]
        self.url = 'http://{}:{}/'.format(address, self.port)
        self.hosts = {'{}:{}'.format(value, self.port) for value in (address, '127.0.0.1', 'localhost')}
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    @property
    def active(self):
        return not self.closed and time.time() < self.expires

    def sources(self):
        return [{'key': entry['key'], 'label': entry['label'], 'url': entry['url'],
                 'enabled': entry.get('enabled', True), 'group': entry.get('live_group', ''),
                 'guide_country': entry.get('guide_country', ''),
                 'provider': entry.get('manifest', {}).get('name', '')}
                for entry in self.store.providers()]

    def save(self, data):
        url = normalize_url(str(data.get('url', '')))
        label = str(data.get('label', '')).strip()[:100]
        group = data.get('group', '')
        if group not in ('', 'tv', 'internet', 'sports'):
            raise ValueError('Choose a valid category.')
        manifest = validate_manifest(self.fetch(url))
        entries = self.store.providers()
        previous_key = data.get('key', '')
        previous = next((entry for entry in entries if entry['key'] == previous_key), None)
        if previous_key and previous is None:
            raise ValueError('This source changed. Reload the source list and try again.')
        key = hashlib.sha256(url.encode()).hexdigest()[:24]
        entry = dict(previous or {}, key=key, url=url, label=label or manifest['name'],
                     manifest=manifest, enabled=bool(data.get('enabled', True)))
        if 'guide_country' in data:
            country = data.get('guide_country', '')
            if country and country not in COUNTRIES:
                raise ValueError('Choose a valid programme country.')
            entry['guide_country'] = country
        entry.pop('live_group', None)
        if group:
            entry['live_group'] = group
        # An edited URL replaces that entry. Do not leave an expired duplicate.
        result, inserted = [], False
        for current in entries:
            if current['key'] in (key, previous_key):
                if not inserted:
                    result.append(entry)
                    inserted = True
            else:
                result.append(current)
        if not inserted:
            result.append(entry)
        self.store.save_providers(result)

    def refresh(self):
        updated, failed = 0, []
        entries = self.store.providers()
        for entry in entries:
            if not entry.get('enabled', True):
                continue
            try:
                entry['manifest'] = validate_manifest(self.fetch(entry['url']))
                updated += 1
            except Exception:
                failed.append(entry['label'])
        self.store.save_providers(entries)
        return {'message': '{} source catalogues refreshed.'.format(updated), 'failed': failed}

    def close(self):
        self.closed = True
        self.sessions.clear()
        self.http.shutdown()
        self.http.server_close()


class SetupController:
    def __init__(self, root, addon_path, address):
        self.store = Store(root)
        self.request = os.path.join(root, 'web-setup-request.json')
        self.endpoint = os.path.join(root, 'web-setup-endpoint.json')
        self.assets = os.path.join(addon_path, 'resources', 'setup')
        self.address = address
        self.nonce, self.server = None, None
        self.store.write(self.endpoint, {})

    def poll(self):
        try:
            request = self.store.read(self.request, {})
        except (OSError, ValueError):
            request = {}
        if not isinstance(request, dict):
            request = {}
        if request.get('stop') and self.server:
            self.close()
        if self.server and not self.server.active:
            self.close()
        nonce = request.get('nonce')
        stamp = request.get('time', 0)
        if isinstance(nonce, str) and 0 < len(nonce) <= 64 and nonce != self.nonce and not request.get('stop') and isinstance(stamp, (int, float)) and stamp > time.time() - 60:
            self.close()
            self.nonce = nonce
            try:
                self.server = SetupServer(self.store, self.assets, self.address())
                self.store.write(self.endpoint, {'nonce': nonce, 'url': self.server.url,
                                               'code': self.server.code, 'expires': self.server.expires})
            except Exception:
                self.store.write(self.endpoint, {'nonce': nonce, 'error': 'Could not open source setup. Check Kodi has a home-network connection and try again.'})

    def close(self):
        if self.server:
            self.server.close()
            self.server = None
        self.store.write(self.endpoint, {})
