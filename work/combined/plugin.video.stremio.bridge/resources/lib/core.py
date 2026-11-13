"""Stremio protocol client. No Kodi imports, credentials in logs, or third-party dependencies."""
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

MAX_RESPONSE = 12 * 1024 * 1024
DEFAULT_URL = 'https://v3-cinemeta.strem.io/manifest.json'
PRESETS = [
    'Cinemeta', 'YouTube', 'WatchHub', 'Public Domain Movies',
    'OpenSubtitles v3', 'OpenSubtitles', 'MediaFusion | ElfHosted',
    'M3U/EPG TV Addon', 'Comet | ElfHosted | RD', 'Torrentio',
    'PlavioLive', 'Streaming Catalogs', 'Other add-on',
    'Pluto TV', 'Sports Streams', 'StreamsPPV', 'M3U IPTV playlist',
]


def normalize_url(value):
    value = value.strip()
    if value.startswith('stremio://'):
        value = 'https://' + value[len('stremio://'):]
    parts = urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        raise ValueError('Enter an HTTP(S) or stremio:// manifest URL.')
    if parts.username or parts.password or parts.fragment:
        raise ValueError('Use the full manifest URL without credentials or a fragment.')
    path = parts.path.rstrip('/')
    if path.lower().endswith(('.m3u', '.m3u8')):
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ''))
    if path.endswith('/configure'):
        raise ValueError('This is a configuration page. Copy the Share addon manifest URL instead.')
    if not path.endswith('/manifest.json'):
        path += '/manifest.json'
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ''))


def resource_url(manifest_url, resource, media_type, item_id, extras=None):
    parts = urlsplit(normalize_url(manifest_url))
    if parts.path.lower().endswith(('.m3u', '.m3u8')):
        # An opaque catalogue-cache key; never sent to the remote playlist host.
        return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query,
                           urlencode(dict(resource=resource, type=media_type, id=item_id, **(extras or {})))))
    base_path = parts.path[:-len('/manifest.json')]
    path = '/'.join(quote(str(x), safe='') for x in (resource, media_type, item_id))
    if extras:
        path += '/' + urlencode(extras, quote_via=quote)
    return urlunsplit((parts.scheme, parts.netloc, base_path + '/' + path + '.json', parts.query, ''))


def fetch_json(url, timeout=20):
    request = Request(url, headers={'User-Agent': 'Kodi-Stremio-Bridge/0.2', 'Accept': 'application/json'})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError('Response exceeds the size limit.')
    data = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object.')
    return data


def validate_manifest(manifest):
    if not all(isinstance(manifest.get(k), str) and manifest[k] for k in ('id', 'name', 'version')):
        raise ValueError('The URL did not return a valid Stremio manifest.')
    for key in ('resources', 'types', 'catalogs'):
        if not isinstance(manifest.get(key, []), list):
            raise ValueError('Invalid manifest: ' + key)
    if manifest.get('behaviorHints', {}).get('configurationRequired'):
        raise ValueError('Configure this add-on in Stremio first, then copy its installed manifest URL.')
    return manifest


def load_manifest(url, fetch=fetch_json):
    from . import daddylive
    if daddylive.is_source(url):
        return daddylive.manifest()
    from . import m3u
    return m3u.manifest(url, m3u.load(url, force=True)) if m3u.is_playlist(url) else validate_manifest(fetch(url))


def fetch_resource(entry, resource, media_type, identity, extras=None, fetch=fetch_json):
    if entry.get('kind') == 'daddylive':
        from . import daddylive
        return daddylive.resource(entry, resource, media_type, identity, extras)
    if entry.get('kind') == 'm3u':
        from . import m3u
        return m3u.resource(entry, resource, media_type, identity, extras)
    return fetch(resource_url(entry['url'], resource, media_type, identity, extras))


def supports(manifest, resource, media_type, item_id):
    for entry in manifest.get('resources', []):
        if isinstance(entry, str):
            name, types, prefixes = entry, manifest.get('types', []), manifest.get('idPrefixes')
        elif isinstance(entry, dict):
            name, types, prefixes = entry.get('name'), entry.get('types', manifest.get('types', [])), entry.get('idPrefixes')
        else:
            continue
        if name == resource and media_type in types and (prefixes is None or any(item_id.startswith(p) for p in prefixes)):
            return True
    return False


def stream_kind(stream):
    if stream.get('url'):
        parts = urlsplit(stream['url'])
        if parts.path.rstrip('/').endswith('/configure'):
            return 'configuration'
        if '/static/exceptions/' in parts.path:
            return 'unavailable'
        return 'direct' if parts.scheme in ('http', 'https', 'rtmp', 'rtsp', 'ftp', 'ftps') else 'unsupported'
    if stream.get('ytId'):
        return 'youtube'
    if stream.get('externalUrl'):
        return 'external'
    if stream.get('infoHash'):
        return 'torrent'
    return 'unsupported'


def playback_url(stream):
    kind = stream_kind(stream)
    if kind == 'youtube':
        return 'plugin://plugin.video.youtube/play/?' + urlencode({'video_id': stream['ytId']})
    if kind != 'direct':
        raise ValueError('This source requires a separate player or service.')
    url = stream['url']
    hints = stream.get('behaviorHints') or {}
    if (hints.get('proxyHeaders') or {}).get('response'):
        raise ValueError('This stream requires a response-header proxy, which this bridge does not provide.')
    headers = (hints.get('proxyHeaders') or {}).get('request') or {}
    if headers and urlsplit(url).scheme in ('http', 'https'):
        separator = '&' if '|' in url else '|'
        url += separator + urlencode({str(k): str(v) for k, v in headers.items()})
    return url


class Store:
    def __init__(self, root):
        self.root = root
        self.cache = os.path.join(root, 'cache')
        os.makedirs(self.cache, exist_ok=True)

    def read(self, path, default=None):
        try:
            with open(path, encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            return default

    def write(self, path, data):
        # Unique temporary names also permit concurrent Kodi invocations.
        import tempfile
        fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

    def providers(self):
        return self.read(os.path.join(self.root, 'providers.json'), [])

    def save_providers(self, entries):
        self.write(os.path.join(self.root, 'providers.json'), entries)

    def add(self, url, label='', fetch=fetch_json):
        url = normalize_url(url)
        manifest = load_manifest(url, fetch)
        entries = self.providers()
        key = hashlib.sha256(url.encode()).hexdigest()[:24]
        previous = next((x for x in entries if x['key'] == key), {})
        entry = dict(previous, key=key, url=url, manifest=manifest,
                     label=label or previous.get('label') or manifest['name'],
                     enabled=previous.get('enabled', True))
        if urlsplit(url).path.lower().endswith(('.m3u', '.m3u8')):
            entry['kind'] = 'm3u'
            entry.setdefault('live_group', 'tv')
            entry['scope_types'] = ['tv']
        else:
            if previous.get('kind') == 'm3u': entry.pop('scope_types', None)
            entry.pop('kind', None)
        if manifest['id'] == 'org.cbr.daddylive':
            entry.update(kind='daddylive', live_group='tv', scope_types=['tv'])
        entries = [entry if x['key'] == key else x for x in entries]
        if not any(x['key'] == key for x in entries):
            entries.append(entry)
        self.save_providers(entries)
        return entry

    def provider(self, key):
        return next(x for x in self.providers() if x['key'] == key)

    def put(self, data):
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        self.write(os.path.join(self.cache, digest + '.json'), {'created': time.time(), 'data': data})
        return digest

    def get(self, key):
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('Invalid cached item.')
        value = self.read(os.path.join(self.cache, key + '.json'))
        if value is None:
            raise ValueError('This item has expired. Reopen its catalogue or stream list.')
        return value['data']

    def prune(self, days=7):
        maintenance = os.path.join(self.root, 'cache-maintenance.json')
        if days == 7 and time.time() - self.read(maintenance, {}).get('pruned', 0) < 3600:
            return
        for name in os.listdir(self.cache):
            path = os.path.join(self.cache, name)
            try:
                if name.endswith('.json') and os.path.getmtime(path) < time.time() - days * 86400:
                    os.remove(path)
            except OSError:
                pass
        if days == 7:
            self.write(maintenance, {'pruned': time.time()})


def aggregate(entries, resource, media_type, item_id, extras=None, fetch=fetch_json):
    candidates = [x for x in entries if x.get('enabled', True)
                  and media_type in x.get('scope_types', [media_type])
                  and supports(x['manifest'], resource, media_type, item_id)]
    def query(entry):
        try:
            return entry, fetch_resource(entry, resource, media_type, item_id, extras, fetch=fetch), None
        except Exception:
            # Never return exception strings: urllib errors can contain configured URLs/tokens.
            return entry, {}, 'Provider request failed'
    with ThreadPoolExecutor(max_workers=6) as executor:
        return list(executor.map(query, candidates))
