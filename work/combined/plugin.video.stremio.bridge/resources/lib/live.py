"""Live catalogue grouping without changing provider protocol types."""
import hashlib
import os
import time

GROUPS = (('tv', 'TV Channels'), ('internet', 'Internet TV'), ('sports', 'Live Sports'))
GROUP_NAMES = dict(GROUPS)
ON_DEMAND_TYPES = {'movie', 'series', 'anime', 'other'}
LIVE_TYPES = {'tv', 'channel', 'channels', 'live', 'event', 'events', 'sport', 'sports', 'streamsppv'}


def entry_catalogs(entry):
    seen = set()
    for catalog in list(entry.get('manifest', {}).get('catalogs', [])) + entry.get('extra_catalogs', []):
        if not isinstance(catalog, dict) or not catalog.get('id') or not catalog.get('type'):
            continue
        identity = (catalog['type'], catalog['id'])
        if identity not in seen:
            seen.add(identity)
            yield catalog


def catalogue_group(entry, catalog):
    kind = catalog.get('type', '').lower()
    if kind in ON_DEMAND_TYPES:
        return None
    assigned = entry.get('live_group')
    if assigned in GROUP_NAMES:
        return assigned
    identity = str(entry.get('manifest', {}).get('id', '')).lower()
    name = str(catalog.get('name', '')).lower()
    if kind not in LIVE_TYPES and not any(x in identity for x in ('streamsppv', 'plutotv', 'sports')):
        return None
    if kind in ('sport', 'sports', 'event', 'events', 'streamsppv') or 'sport' in name or 'streamsppv' in identity:
        return 'sports'
    if any(x in identity for x in ('pluto', 'plex', 'samsung', 'roku', 'freevee')):
        return 'internet'
    return 'tv'


def grouped_catalogues(entries, group):
    if group not in GROUP_NAMES:
        raise ValueError('Unknown Live TV category.')
    for entry in entries:
        if not entry.get('enabled', True):
            continue
        for catalog in entry_catalogs(entry):
            if catalogue_group(entry, catalog) == group:
                yield entry, catalog


def search_only(catalog):
    return any(x.get('name') == 'search' and x.get('isRequired') for x in catalog.get('extra', []))


def browse_title(catalog):
    # TV Voo uses a provider prefix on browse entries and a magnifier on search.
    name = catalog.get('name', catalog['id'])
    return name.split('•', 1)[-1].strip() if '•' in name else name


class LiveLibrary:
    """Persistent channel bookmarks; always resolve fresh sources at playback."""
    def __init__(self, store):
        self.store = store

    def path(self, name):
        return os.path.join(self.store.root, 'live-' + name + '.json')

    def entries(self, name):
        return self.store.read(self.path(name), [])

    def channel(self, saved):
        provider = self.store.provider(saved['provider'])
        meta = {k: v for k, v in saved['meta'].items() if k in (
            'id', 'type', 'name', 'poster', 'logo', 'thumbnail', 'background', 'description', 'genres')}
        return dict(provider=saved['provider'], provider_id=provider['manifest']['id'], meta=meta,
                    resource_type=saved.get('resource_type', meta['type']), live_group=saved['live_group'])

    @staticmethod
    def identity(channel):
        return (channel['provider_id'], channel['resource_type'], channel['meta']['id'])

    def is_favourite(self, channel):
        return any(self.identity(x) == self.identity(channel) for x in self.entries('favourites'))

    def toggle(self, channel):
        entries = self.entries('favourites')
        exists = self.is_favourite(channel)
        entries = [x for x in entries if self.identity(x) != self.identity(channel)]
        if not exists:
            entries.append(channel)
        self.store.write(self.path('favourites'), entries)
        return not exists

    def resolve(self, channel):
        entries = [e for e in self.store.providers() if e.get('enabled', True)]
        entry = next((e for e in entries if e['key'] == channel['provider']), None)
        if entry is None:
            entry = next((e for e in entries if e['manifest']['id'] == channel['provider_id']), None)
        if entry is None:
            return None
        return dict(channel, provider=entry['key'])

    def pending(self, channel, path):
        self.store.write(self.path('pending'), dict(channel=channel, created=time.time(),
                         fingerprint=hashlib.sha256(path.split('|')[0].encode()).hexdigest()))

    def poll(self, player):
        pending = self.store.read(self.path('pending'), {})
        if not pending:
            return
        if time.time() - pending.get('created', 0) > 120:
            self.store.write(self.path('pending'), {})
            return
        try:
            if not player.isPlayingVideo():
                return
            fingerprint = hashlib.sha256(player.getPlayingFile().split('|')[0].encode()).hexdigest()
            if fingerprint != pending['fingerprint']:
                return
        except Exception:
            return
        channel = pending['channel']
        entries = [x for x in self.entries('recent') if self.identity(x) != self.identity(channel)]
        self.store.write(self.path('recent'), [channel] + entries[:49])
        self.store.write(self.path('pending'), {})
