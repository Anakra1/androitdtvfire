"""Local XMLTV schedules and conservative channel matching for Now/Next and EPG."""
from datetime import datetime, timezone
import gzip
import hashlib
import os
import re
import sqlite3
import tempfile
import threading
import time
import unicodedata
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from .channel_names import uk_guide_name

DEFAULT_FEED = 'https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz'
COUNTRIES = {'GB': 'United Kingdom', 'IE': 'Ireland', 'US': 'United States', 'CA': 'Canada',
             'AU': 'Australia', 'IT': 'Italy', 'FR': 'France', 'DE': 'Germany', 'ES': 'Spain',
             'PT': 'Portugal', 'NL': 'Netherlands', 'PL': 'Poland', 'RO': 'Romania', 'BG': 'Bulgaria'}


def feed_key(url):
    return hashlib.sha256(url.encode()).hexdigest()[:24]


def settings(store):
    return store.read(os.path.join(store.root, 'programme-settings.json'), {
        'enabled': True, 'feeds': [dict(key=feed_key(DEFAULT_FEED), label='UK programmes',
                                      url=DEFAULT_FEED, country='GB', enabled=True)], 'mappings': {}})


def save_settings(store, data):
    store.write(os.path.join(store.root, 'programme-settings.json'), data)


def request_refresh(store):
    store.write(os.path.join(store.root, 'programme-refresh.json'), {'time': time.time()})


def save_feed(store, data):
    url = str(data.get('url', '')).strip()
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise ValueError('Enter a full HTTP(S) XMLTV schedule URL.')
    country = str(data.get('country', '')).upper()
    if country not in COUNTRIES:
        raise ValueError('Choose the schedule country.')
    config = settings(store)
    key, old = feed_key(url), data.get('key', '')
    feed = dict(key=key, label=str(data.get('label', '')).strip()[:100] or COUNTRIES[country],
                url=url, country=country, enabled=bool(data.get('enabled', True)))
    feeds, inserted = [], False
    for previous in config['feeds']:
        if previous['key'] in (key, old):
            if not inserted:
                feeds.append(feed)
                inserted = True
        else:
            feeds.append(previous)
    config['feeds'] = feeds if inserted else feeds + [feed]
    if old and old != key:
        for mapping in config.get('mappings', {}).values():
            if mapping.get('feed') == old:
                mapping['feed'] = key
    config['enabled'] = True
    save_settings(store, config)
    request_refresh(store)


def normalized(name, quality=False):
    name = unicodedata.normalize('NFKC', str(name)).casefold().replace('&', ' and ')
    name = re.sub(r'[^\w+]+', ' ', name)
    if quality:
        name = re.sub(r'\b(?:hd|sd|fhd|uhd|4k|hevc)\b', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


def country_for(meta, saved=None, provider=None):
    saved, provider = saved or {}, provider or {}
    identity = unquote(str(meta.get('id', ''))).lower()
    group = re.search(r'\|group:([a-z]{2})(?:$|[|:])', identity)
    if group:
        return 'GB' if group[1] == 'uk' else group[1].upper()
    for value in [meta.get('country', ''), saved.get('live_country', '')] + list(meta.get('genres') or []):
        value = str(value).upper().strip()
        if value in ('UK', 'UNITED KINGDOM', 'GREAT BRITAIN') or value.startswith('UK '):
            return 'GB'
        if value in COUNTRIES:
            return value
        for code, label in COUNTRIES.items():
            if value == label.upper():
                return code
    for key in ('tvg_id', 'tvgId', 'epg_id', 'epgId', 'id'):
        suffix = str(meta.get(key, '')).rsplit('.', 1)[-1].upper()
        if suffix == 'UK':
            return 'GB'
        if suffix in COUNTRIES:
            return suffix
    return provider.get('guide_country', '')


def channel_key(channel):
    value = '\n'.join((channel.get('provider_id', ''), channel.get('resource_type', ''), str(channel['meta']['id'])))
    return hashlib.sha256(value.encode()).hexdigest()


def timestamp(value):
    if isinstance(value, (int, float)):
        return value / 1000 if value > 10**11 else value
    value = str(value or '').strip()
    match = re.fullmatch(r'(\d{14}|\d{12})(?:\s*([+-]\d{4}|Z))?', value)
    try:
        if match:
            pattern = '%Y%m%d%H%M%S' if len(match[1]) == 14 else '%Y%m%d%H%M'
            return datetime.strptime(match[1] + (match[2] or '+0000').replace('Z', '+0000'), pattern + '%z').timestamp()
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return date.timestamp() if date.tzinfo else None
    except (ValueError, OverflowError):
        return None


def now_next(programmes, now=None):
    now = time.time() if now is None else now
    programmes = sorted(programmes, key=lambda p: p['start'])
    current = next((p for p in reversed(programmes) if p['start'] <= now < p['stop']), None)
    following = next((p for p in programmes if p['start'] >= (current['stop'] if current else now)), None)
    return {'now': current, 'next': following}


def provider_programmes(meta):
    programmes = []
    for video in meta.get('videos') or []:
        start, stop = timestamp(video.get('startTime') or video.get('released')), timestamp(video.get('endTime'))
        if start is not None and stop is not None and stop > start and video.get('title'):
            programmes.append(dict(start=start, stop=stop, title=str(video['title']),
                                   description=str(video.get('overview', ''))))
    return programmes


def embedded(meta):
    result = now_next(provider_programmes(meta))
    return result if result['now'] or result['next'] else None


def clock(stamp):
    date = datetime.fromtimestamp(stamp)
    return date.strftime('%H:%M' if date.date() == datetime.now().date() else '%a %H:%M')


def programme_text(result):
    lines = []
    for key, label in (('now', 'Now'), ('next', 'Next')):
        programme = (result or {}).get(key)
        if programme:
            lines.append('{} {}–{}: {}'.format(label, clock(programme['start']), clock(programme['stop']), programme['title']))
            if programme.get('description'):
                lines.append(programme['description'])
        else:
            lines.append('{}: Programme information unavailable'.format(label))
        lines.append('')
    return '\n'.join(lines).strip()


class ProgrammeGuide:
    def __init__(self, store):
        self.store = store
        self.path = os.path.join(store.root, 'programme-guide.sqlite3')
        self.config = settings(store)
        self.providers = {entry['key']: entry for entry in store.providers()}
        self.connection = None
        self.memo = {}
        self.alias_index = {}

    def database(self):
        if self.connection is None and os.path.isfile(self.path):
            self.connection = sqlite3.connect(self.path, timeout=0.1)
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None

    def match(self, channel):
        db = self.database()
        if db is None or not self.config.get('enabled', True):
            return None
        feeds = [f for f in self.config['feeds'] if f.get('enabled', True)]
        active = {f['key'] for f in feeds}
        mapping = self.config.get('mappings', {}).get(channel_key(channel))
        if mapping:
            if mapping['feed'] in active and db.execute('SELECT 1 FROM channels WHERE source=? AND id=?',
                                                       (mapping['feed'], mapping['channel'])).fetchone():
                return mapping['feed'], mapping['channel']
            return None
        meta = channel['meta']
        provider = self.providers.get(channel['provider'])
        if provider is None:
            try:
                provider = self.store.provider(channel['provider'])
                self.providers[channel['provider']] = provider
            except StopIteration:
                provider = {}
        country = country_for(meta, channel, provider)
        ordered = [f for f in feeds if not country or f['country'] == country]
        active = {f['key'] for f in ordered}
        for name in ('tvg_id', 'tvgId', 'epg_id', 'epgId', 'id'):
            identity = meta.get(name)
            if not identity:
                continue
            candidates = [tuple(row) for row in db.execute('SELECT source,id FROM channels WHERE id=?', (identity,)) if row['source'] in active]
            sources = {candidate[0] for candidate in candidates}
            if candidates and len({f['country'] for f in ordered if f['key'] in sources}) == 1:
                for feed in ordered:
                    if feed['key'] in sources:
                        return feed['key'], str(identity)
        if not country or not active:
            return None
        for feed in ordered:
            for field, value in (('exact', normalized(meta.get('name', ''))), ('folded', normalized(meta.get('name', ''), True))):
                candidates = {tuple(row) for row in db.execute('SELECT DISTINCT source,id FROM aliases WHERE source=? AND ' + field + '=?', (feed['key'], value))}
                if len(candidates) == 1:
                    return next(iter(candidates))
                if len(candidates) > 1:
                    return self.equivalent(candidates)
        if country == 'GB':
            # Known spelling/abbreviation differences only, within a UK feed.
            # No fuzzy matching or generic-to-regional substitutions.
            value = uk_guide_name(meta.get('name', ''))
            for feed in ordered:
                if feed['key'] not in self.alias_index:
                    index = {}
                    for row in db.execute('SELECT id,name FROM channels WHERE source=?', (feed['key'],)):
                        index.setdefault(uk_guide_name(row['name']), set()).add((feed['key'], row['id']))
                    self.alias_index[feed['key']] = index
                candidates = self.alias_index[feed['key']].get(value, set())
                if len(candidates) == 1:
                    return next(iter(candidates))
                if candidates:
                    return self.equivalent(candidates)
        return None

    def equivalent(self, candidates):
        """HD/SD alternatives are safe only when their next-day schedules agree."""
        schedules = []
        now = time.time()
        for source, identity in sorted(candidates):
            rows = self.database().execute('SELECT start,stop,title FROM programmes WHERE source=? AND channel=? AND stop>? AND start<? ORDER BY start',
                                           (source, identity, now, now + 86400)).fetchall()
            schedules.append([tuple(row) for row in rows])
        if schedules and schedules[0] and all(s == schedules[0] for s in schedules):
            return sorted(candidates)[0]
        return None

    def lookup(self, channel, meta=None):
        if not self.config.get('enabled', True):
            return None
        native = embedded(meta or channel['meta'])
        if not native and channel.get('native_schedule'):
            candidate = now_next(channel['native_schedule'])
            native = candidate if candidate['now'] or candidate['next'] else None
        if native:
            return native
        if meta:
            channel = dict(channel, meta=dict(meta, **channel['meta']))
        key = channel_key(channel)
        if key in self.memo:
            return self.memo[key]
        try:
            matched = self.match(channel)
            if not matched:
                return None
            now = time.time()
            db = self.database()
            current = db.execute('SELECT start,stop,title,description FROM programmes WHERE source=? AND channel=? AND start<=? AND stop>? ORDER BY start DESC LIMIT 1',
                                 (*matched, now, now)).fetchone()
            following = db.execute('SELECT start,stop,title,description FROM programmes WHERE source=? AND channel=? AND start>=? ORDER BY start LIMIT 1',
                                   (*matched, current['stop'] if current else now)).fetchone()
            result = dict(now=dict(current) if current else None, next=dict(following) if following else None)
            self.memo[key] = result
            return result
        except sqlite3.Error:
            return None

    def channels(self):
        try:
            db = self.database()
            active = {f['key']: f['label'] for f in self.config['feeds'] if f.get('enabled', True)}
            return [dict(feed=row['source'], channel=row['id'], name=row['name'], label=active[row['source']])
                    for row in db.execute('SELECT source,id,name FROM channels ORDER BY name COLLATE NOCASE')
                    if row['source'] in active] if db else []
        except sqlite3.Error:
            return []

    def schedule(self, channel, start, stop):
        try:
            matched = self.match(channel)
            if not matched:
                return []
            return [dict(row) for row in self.database().execute(
                'SELECT start,stop,title,description FROM programmes WHERE source=? AND channel=? AND start<? AND stop>? ORDER BY start',
                (*matched, stop, start))]
        except sqlite3.Error:
            return []

    def map_channel(self, channel, mapping):
        config = settings(self.store)
        key = channel_key(channel)
        if mapping:
            config.setdefault('mappings', {})[key] = dict(feed=mapping['feed'], channel=mapping['channel'])
        else:
            config.setdefault('mappings', {}).pop(key, None)
        save_settings(self.store, config)
        self.config, self.memo = config, {}


def import_xml(store, feed, path, now=None):
    now = time.time() if now is None else now
    database = sqlite3.connect(os.path.join(store.root, 'programme-guide.sqlite3'), timeout=5)
    channels = programmes = 0
    try:
        database.execute('PRAGMA journal_mode=WAL')
        database.executescript('''CREATE TABLE IF NOT EXISTS channels(source TEXT,id TEXT,name TEXT,PRIMARY KEY(source,id));
            CREATE TABLE IF NOT EXISTS aliases(source TEXT,id TEXT,exact TEXT,folded TEXT,PRIMARY KEY(source,id,exact));
            CREATE INDEX IF NOT EXISTS aliases_exact ON aliases(exact);
            CREATE INDEX IF NOT EXISTS aliases_folded ON aliases(folded);
            CREATE TABLE IF NOT EXISTS programmes(source TEXT,channel TEXT,start INTEGER,stop INTEGER,title TEXT,description TEXT,
                PRIMARY KEY(source,channel,start,stop,title));
            CREATE INDEX IF NOT EXISTS programme_time ON programmes(source,channel,start,stop);''')
        with database:
            for table in ('channels', 'aliases', 'programmes'):
                database.execute('DELETE FROM ' + table + ' WHERE source=?', (feed['key'],))
            iterator = ET.iterparse(path, events=('start', 'end'))
            _, root = next(iterator)
            if root.tag != 'tv':
                raise ValueError('The schedule URL did not return XMLTV data.')
            for event, node in iterator:
                if event != 'end' or node.tag not in ('channel', 'programme'):
                    continue
                identity = node.get('id') if node.tag == 'channel' else node.get('channel')
                if node.tag == 'channel' and identity:
                    names = [n.text.strip() for n in node.findall('display-name') if n.text and n.text.strip()]
                    database.execute('INSERT OR REPLACE INTO channels VALUES(?,?,?)', (feed['key'], identity, names[0] if names else identity))
                    for name in names:
                        database.execute('INSERT OR IGNORE INTO aliases VALUES(?,?,?,?)',
                                         (feed['key'], identity, normalized(name), normalized(name, True)))
                    channels += 1
                elif identity:
                    start, stop = timestamp(node.get('start')), timestamp(node.get('stop'))
                    title = node.findtext('title')
                    if start is not None and stop is not None and start < stop and stop > now - 3600 and start < now + 7 * 86400 and title:
                        database.execute('INSERT OR IGNORE INTO programmes VALUES(?,?,?,?,?,?)',
                            (feed['key'], identity, start, stop, title[:1000], (node.findtext('desc') or '')[:8000]))
                        programmes += 1
                root.remove(node)
                node.clear()
                if channels > 20000 or programmes > 150000:
                    raise ValueError('The schedule feed is too large for this device.')
            if not channels or not programmes:
                raise ValueError('The feed contains no current or upcoming programme data.')
        return dict(channels=channels, programmes=programmes, updated=time.time(), state='ready')
    finally:
        database.close()


def download_feed(store, feed, stop):
    directory = os.path.join(store.root, 'programme-downloads')
    os.makedirs(directory, exist_ok=True)
    paths = []
    try:
        for _ in range(2):
            descriptor, path = tempfile.mkstemp(dir=directory)
            os.close(descriptor)
            paths.append(path)
        with urlopen(Request(feed['url'], headers={'User-Agent': 'CBR-Kodi-Programme-Guide/0.1'}), timeout=10) as response, open(paths[0], 'wb') as target:
            size, deadline = 0, time.monotonic() + 90
            while not stop.is_set():
                chunk = response.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > 16 * 1024 * 1024 or time.monotonic() > deadline:
                    raise ValueError('Schedule download exceeds the size limit.')
                target.write(chunk)
        if stop.is_set():
            return None
        with open(paths[0], 'rb') as source:
            compressed = source.read(2) == b'\x1f\x8b'
        opener = gzip.open if compressed else open
        with opener(paths[0], 'rb') as source, open(paths[1], 'wb') as target:
            size, tail = 0, b''
            while not stop.is_set():
                chunk = source.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > 96 * 1024 * 1024 or b'<!ENTITY' in (tail + chunk).replace(b'\0', b'').upper():
                    raise ValueError('Schedule XML is too large or contains unsupported entities.')
                tail = chunk[-64:]
                target.write(chunk)
        return None if stop.is_set() else import_xml(store, feed, paths[1])
    finally:
        for path in paths:
            if os.path.exists(path):
                os.remove(path)


class ProgrammeUpdater:
    def __init__(self, store):
        self.store = store
        self.thread, self.last_poll, self.last_request = None, 0, 0
        self.stop = threading.Event()

    def poll(self):
        if time.monotonic() - self.last_poll < 5 or self.thread and self.thread.is_alive():
            return
        self.last_poll = time.monotonic()
        config = settings(self.store)
        if not config.get('enabled', True):
            return
        request = self.store.read(os.path.join(self.store.root, 'programme-refresh.json'), {}).get('time', 0)
        force = request > self.last_request
        self.last_request = request
        status = self.store.read(os.path.join(self.store.root, 'programme-status.json'), {})
        feeds = [f for f in config['feeds'] if f.get('enabled', True) and (force or (
            time.time() - status.get(f['key'], {}).get('updated', 0) > 6 * 3600
            and time.time() - status.get(f['key'], {}).get('attempted', 0) > 1800))]
        if feeds:
            self.thread = threading.Thread(target=self.refresh, args=(feeds,), daemon=True)
            self.thread.start()

    def refresh(self, feeds):
        path = os.path.join(self.store.root, 'programme-status.json')
        for feed in feeds:
            if self.stop.is_set():
                return
            status = self.store.read(path, {})
            previous = status.get(feed['key'], {})
            status[feed['key']] = dict(previous, attempted=time.time(), state='updating')
            self.store.write(path, status)
            try:
                result = download_feed(self.store, feed, self.stop)
                if result:
                    status[feed['key']].update(result)
            except Exception:
                status[feed['key']].update(state='error', message='Programme information could not be updated. Previous schedules are kept.')
            self.store.write(path, status)

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)


class ProgrammePlaybackInfo:
    """Refresh the information overlay as shows change, without restarting video."""
    def __init__(self, store):
        self.store, self.last_poll = store, 0

    def poll(self, player, make_item):
        if time.monotonic() - self.last_poll < 30:
            return
        self.last_poll = time.monotonic()
        path = os.path.join(self.store.root, 'live-playing.json')
        playing = self.store.read(path, {})
        if not playing:
            return
        try:
            current = player.getPlayingFile() if player.isPlayingVideo() else ''
            fingerprint = hashlib.sha256(current.split('|')[0].encode()).hexdigest()
            if fingerprint != playing['fingerprint']:
                self.store.write(path, {})
                return
            channel = playing['channel']
            item = make_item(current, channel['meta'].get('name', 'Live TV'), channel)
            player.updateInfoTag(item)
        except Exception:
            pass  # A stopped video or unavailable guide must never affect playback.
