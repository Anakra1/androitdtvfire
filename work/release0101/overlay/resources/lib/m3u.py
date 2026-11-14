"""M3U channel-list adapter. No external player, server or Stremio proxy."""
import hashlib
import json
import os
import re
import threading
import time
from urllib.parse import parse_qsl, urljoin, urlsplit
from urllib.request import Request, urlopen

DEFAULT_URL = 'https://iptv-org.github.io/iptv/index.m3u'
UK_URL = 'https://iptv-org.github.io/iptv/countries/uk.m3u'
_cache, _lock = {}, threading.RLock()


def is_playlist(url):
    return urlsplit(url).path.lower().endswith(('.m3u', '.m3u8'))


def countries():
    with open(os.path.join(os.path.dirname(__file__), '../defaults/m3u-countries.json'), encoding='utf8') as source:
        return json.load(source)


def clean_name(value):
    value = re.sub(r'\s*\(\d{2,4}p\)\s*', ' ', value)
    return re.sub(r'\s*\[(?:Geo-blocked|Not 24/7)\]\s*', ' ', value, flags=re.I).strip()


def parse(text, base):
    if not text.lstrip('\ufeff\r\n ').startswith('#EXTM3U') or '#EXT-X-' in text:
        raise ValueError('Use an M3U channel list, not a video playlist or web page.')
    rows, current = {}, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF:'):
            quoted, comma = False, None
            for i, char in enumerate(line):
                if char == '"': quoted = not quoted
                if char == ',' and not quoted: comma = i; break
            if comma is None: current = None; continue
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', line[:comma]))
            name = clean_name(line[comma + 1:]) or attrs.get('tvg-name', '')
            identity = attrs.get('tvg-id') or name.casefold()
            match = re.search(r'\.([a-z]{2})(?:@|$)', attrs.get('tvg-id', ''), re.I)
            country = match[1].upper() if match else ''
            if country == 'UK': country = 'GB'
            if not country and re.fullmatch(r'GB[A-Z0-9]{6,}', attrs.get('tvg-id', '')):
                country = 'GB'  # Samsung TV Plus's UK channel identifiers.
            current = dict(id='m3u.' + hashlib.sha256(identity.encode()).hexdigest()[:24], type='tv', name=name,
                           tvg_id=attrs.get('tvg-id', '').split('@')[0], country=country,
                           logo=attrs.get('tvg-logo', ''), genres=attrs.get('group-title', '').split(';'),
                           description=line[comma + 1:], streams=[], headers={})
        elif current and line.startswith('#EXTVLCOPT:'):
            key, _, value = line[len('#EXTVLCOPT:'):].partition('=')
            header = {'http-user-agent': 'User-Agent', 'http-referrer': 'Referer'}.get(key)
            if header and '\r' not in value and '\n' not in value: current['headers'][header] = value
        elif current and line.startswith('#KODIPROP:') and any(x in line.lower() for x in ('license_key', 'license_type', 'drm')):
            current['unsupported'] = True
        elif current and line and not line.startswith('#'):
            address, _, encoded_headers = line.partition('|')
            address = urljoin(base, address)
            if current['name'] and not current.get('unsupported') and urlsplit(address).scheme in ('http', 'https', 'rtmp', 'rtsp'):
                headers = dict(current['headers'])
                headers.update({k: v for k, v in parse_qsl(encoded_headers) if k in ('User-Agent', 'Referer', 'Origin', 'Cookie', 'Authorization') and '\r' not in v and '\n' not in v})
                stream = dict(url=address, name='M3U', behaviorHints=dict(isLive=True, proxyHeaders={'request': headers}))
                row = rows.setdefault(current['id'], {k: v for k, v in current.items() if k not in ('headers', 'unsupported')})
                if not any(s['url'] == address and s['behaviorHints'] == stream['behaviorHints'] for s in row['streams']): row['streams'].append(stream)
                if len(rows) > 25000: raise ValueError('Playlist exceeds 25,000 channels.')
            current = None
    if not rows: raise ValueError('The playlist has no supported HTTP/RTMP/RTSP TV channels.')
    return list(rows.values())


def load(url, force=False):
    with _lock:
        value = _cache.get(url)
        if not force and value and time.time() - value[0] < 300: return value[1]
    try:
        with urlopen(Request(url, headers={'User-Agent': 'Kodi-CBR/0.9', 'Accept': 'audio/x-mpegurl,text/plain,*/*'}), timeout=20) as response:
            raw = response.read(12 * 1024 * 1024 + 1)
    except Exception:
        raise ValueError('The M3U playlist could not be downloaded. Check its URL and your connection.') from None
    if len(raw) > 12 * 1024 * 1024: raise ValueError('Playlist exceeds 12 MB.')
    rows = parse(raw.decode('utf-8-sig'), url)
    if 'samsungtvplus_' in urlsplit(url).path.lower():
        # Samsung's maintained Kodi integration excludes channels whose
        # license server refuses playback. Keep those out of the TV guide.
        with open(os.path.join(os.path.dirname(__file__), '../defaults/samsung-unsupported.json'), encoding='utf8') as source:
            unsupported = json.load(source)
        rows = [row for row in rows if row['tvg_id'] not in unsupported]
    with _lock:
        if len(_cache) >= 2: _cache.pop(next(iter(_cache)))
        _cache[url] = time.time(), rows
    return rows


def manifest(url, rows=None):
    labels = countries()
    codes = {'GB'} if url == UK_URL else set(r['country'] for r in rows) if rows is not None else set(labels) | {''}
    ordered = sorted(codes, key=lambda code: (code != 'GB', labels.get(code, code)))
    catalogues = [dict(id='m3u_' + ('uk' if code == 'GB' else code or 'other'), type='tv',
                       name=labels.get(code, code) if code else 'Other / unspecified country',
                       country=code, extra=[dict(name='search', isRequired=False)]) for code in ordered]
    catalogues.append(dict(id='m3u_all', type='tv', name='All countries', extra=[dict(name='search', isRequired=False)]))
    parts = urlsplit(url)
    return dict(id='org.cbr.m3u.' + hashlib.sha256((parts.netloc + parts.path).encode()).hexdigest()[:16],
                name='IPTV-org' if url == DEFAULT_URL else 'M3U TV channels', version='1.0.0',
                types=['tv'], resources=['catalog', 'meta', 'stream'], idPrefixes=['m3u.'], catalogs=catalogues)


def resource(entry, kind, media_type, identity, extras=None):
    if media_type != 'tv': return {}
    code = identity.removeprefix('m3u_') if kind == 'catalog' else ''
    code = 'GB' if code == 'uk' else '' if code == 'other' else code
    scoped = re.fullmatch(r'm3u\.([A-Z]{2})\.([a-f0-9]{24})', identity)
    if scoped: code = scoped[1]
    country_list = entry['url'] == DEFAULT_URL and re.fullmatch(r'[A-Z]{2}', code or '')
    url = ('https://iptv-org.github.io/iptv/countries/' + ('uk' if code == 'GB' else code.lower()) + '.m3u') if country_list else entry['url']
    rows = load(url, force=kind == 'stream' or bool((extras or {}).get('_refresh')))
    if country_list:
        rows = [dict(row, id='m3u.' + code + '.' + row['id'].split('.')[-1], country=code) for row in rows]
    elif url == UK_URL:
        rows = [dict(row, country='GB') for row in rows]
    if kind == 'catalog':
        query = (extras or {}).get('search', '').casefold()
        return {'metas': [{k: v for k, v in row.items() if k != 'streams'} for row in rows
                          if (country_list or code == 'all' or row['country'] == code) and query in row['name'].casefold()]}
    row = next((r for r in rows if r['id'] == identity), None)
    if row is None: return {'streams': []} if kind == 'stream' else {}
    return {'streams': row['streams']} if kind == 'stream' else {'meta': {k: v for k, v in row.items() if k != 'streams'}}


def ensure_default(store, force=False):
    marker = os.path.join(store.root, 'm3u-defaults-v1.json')
    if not force and store.read(marker): return
    entries = store.providers()
    if not any(e['url'] == DEFAULT_URL for e in entries):
        entry = dict(key=hashlib.sha256(DEFAULT_URL.encode()).hexdigest()[:24], url=DEFAULT_URL,
                     label='IPTV-org', kind='m3u', manifest=manifest(DEFAULT_URL), enabled=True,
                     live_group='tv', scope_types=['tv'])
        store.save_providers(entries + [entry])
        from . import pvr
        value = pvr.config(store)
        if value.get('enabled'):
            if value.get('selected') is not None:
                value['selected'] += [s['key'] for s in pvr.sources(store) if s['provider'] == entry['key'] and s['default'] and s['key'] not in value['selected']]
                pvr.save_config(store, value)
            pvr.refresh(store)
    store.write(marker, True)
