"""Website-backed TV catalogue. Playback URLs are resolved afresh, never saved."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import json
import os
import re
import time
from urllib.parse import parse_qsl, urljoin, urlsplit

from . import daddy_resolvers as decoders

IDENTITY = 'org.cbr.daddylive'
DEFAULT_URL = 'https://thedaddy.li/cbr-daddylive/manifest.json'
_cache = {}
KNOWN_UK = {'sky atlantic', 'sky crime', 'sky history', 'sky witness hd',
            'sky sports main event', 'sky sports premier league',
            'sky sports cricket', 'sky sports+ plus'}


def is_source(url):
    return urlsplit(url).path.rstrip('/') == '/cbr-daddylive/manifest.json'


def origin(url):
    parts = urlsplit(url)
    return '{}://{}/'.format(parts.scheme, parts.netloc)


def manifest():
    return dict(id=IDENTITY, name='DaddyLive', version='1.0.0', types=['tv'],
                resources=['catalog', 'meta', 'stream'], idPrefixes=['daddy.'],
                catalogs=[dict(id='daddy_uk', type='tv', name='United Kingdom', extra=[dict(name='search')]),
                          dict(id='daddy_all', type='tv', name='All countries', extra=[dict(name='search')])])


def parse_channels(page):
    cards = re.findall(r'<a\s+class="card"[^>]*?href="([^"]+)"[^>]*?data-title="([^"]*)"', page, re.I)
    rows, seen = [], set()
    for href, title in cards[:5000]:
        cid = dict(parse_qsl(urlsplit(html.unescape(href)).query)).get('id', '')
        name = html.unescape(title).strip()
        if not cid.isdigit() or cid in seen or not name or '18+' in name:
            continue
        seen.add(cid)
        uk = bool(re.search(r'\buk$', name, re.I)) or name.casefold() in KNOWN_UK
        name = re.sub(r'\s+uk$', '', name, flags=re.I)
        rows.append(dict(id='daddy.' + cid, type='tv', name=name.title(), country='GB' if uk else '',
                         description='DaddyLive channel. Availability depends on the upstream source.'))
    return rows


def catalogue(url, force=False):
    base = origin(url)
    saved = _cache.get(base)
    if not force and saved and time.monotonic() - saved[0] < 300:
        return saved[1]
    rows = parse_channels(decoders.fetch_page(urljoin(base, '24-7-channels.php'), base))
    if not rows:
        raise ValueError('DaddyLive returned no channel list. Refresh its source or try another provider.')
    _cache.clear()
    _cache[base] = time.monotonic(), rows
    return rows


def resolve(url, identity):
    if not re.fullmatch(r'daddy\.\d+', identity):
        return []
    base, cid = origin(url), identity.split('.')[1]
    watch = urljoin(base, 'watch.php?id=' + cid)
    page = decoders.fetch_page(watch, base)
    players = {'stream': decoders.resolve_watch, 'cast': decoders.resolve_cast,
               'watch': decoders.resolve_watch, 'plus': decoders.resolve_plus,
               'casting': decoders.resolve_casting, 'player': decoders.resolve_player,
               'hub': decoders.resolve_watch}
    jobs, seen = [], set()
    for raw, title in re.findall(r'data-url="([^"]+)"\s+title="([^"]+)"', page):
        target = urljoin(watch, html.unescape(raw))
        kind = urlsplit(target).path.strip('/').split('/')[0]
        if kind in players and target not in seen:
            jobs.append((target, html.unescape(title), kind)); seen.add(target)
    if not jobs:
        jobs = [(urljoin(base, 'cast/stream-' + cid + '.php'), 'Player', 'cast')]

    def attempt(job):
        target, title, kind = job
        try:
            result = players[kind](target, base)
            if not result:
                return None
            stream, referer, *renewal = result
            # Token-renewal recipes need a proxy during playback; do not publish
            # them as ordinary stable HTTP streams until that is supported.
            if renewal or urlsplit(stream).scheme not in ('http', 'https'):
                return None
            return dict(name='DaddyLive / ' + title, url=stream,
                        behaviorHints=dict(proxyHeaders=dict(request={
                            'User-Agent': decoders.UA, 'Referer': referer,
                            'Origin': origin(referer).rstrip('/')})))
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, jobs[:8]))
    unique = {}
    for stream in results:
        if stream:
            unique.setdefault((stream['url'], json.dumps(stream['behaviorHints'], sort_keys=True)), stream)
    return list(unique.values())


def resource(entry, kind, media_type, identity, extras=None):
    if media_type != 'tv':
        return {}
    if kind == 'stream':
        return {'streams': resolve(entry['url'], identity)}
    extras = extras or {}
    rows = catalogue(entry['url'], force=bool(extras.get('_refresh')))
    if kind == 'catalog':
        if identity == 'daddy_uk':
            rows = [r for r in rows if r['country'] == 'GB']
        elif identity != 'daddy_all':
            return {'metas': []}
        query = str(extras.get('search', '')).casefold()
        return {'metas': [r for r in rows if query in r['name'].casefold()]}
    return {'meta': next((r for r in rows if r['id'] == identity), {})}


def ensure_default(store, force=False):
    marker = os.path.join(store.root, 'daddylive-defaults-v1.json')
    if not force and store.read(marker):
        return
    entries = store.providers()
    if not any(e.get('manifest', {}).get('id') == IDENTITY for e in entries):
        entry = dict(key=hashlib.sha256(DEFAULT_URL.encode()).hexdigest()[:24], url=DEFAULT_URL,
                     label='DaddyLive', manifest=manifest(), kind='daddylive', enabled=True,
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
