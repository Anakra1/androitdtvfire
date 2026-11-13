"""Stable M3U/plugin channel routes and XMLTV exports for Kodi IPTV Simple."""
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import threading
import time
from urllib.parse import urlencode, urlsplit
import xml.etree.ElementTree as ET

from .core import fetch_json, resource_url
from .live import entry_catalogs, LiveLibrary, search_only
from .programmes import ProgrammeGuide, country_for, normalized

BASE = 'plugin://plugin.video.stremio.bridge/'
FREEVIEW = {'bbc one': 1, 'bbc two': 2, 'itv1': 3, 'itv': 3, 'channel 4': 4, 'channel 5': 5,
            'bbc three': 23, 'bbc four': 9, 'itv2': 6, 'itv3': 10, 'itv4': 26,
            'e4': 13, 'more4': 18, 'film4': 14, 'cbbc': 201, 'cbeebies': 202,
            'bbc news': 231, 'bbc parliament': 232}
GROUPS = ('Freeview', 'Sky', 'Entertainment', 'Movies', 'Sports', 'News', 'Kids', 'Music', 'Other channels')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:24]


def config(store):
    return store.read(os.path.join(store.root, 'pvr-settings.json'),
                      dict(enabled=False, selected=None, overrides={}))


def save_config(store, value):
    store.write(os.path.join(store.root, 'pvr-settings.json'), value)


def refresh(store, collect=True):
    value = config(store)
    value['enabled'] = True
    save_config(store, value)
    store.write(os.path.join(store.root, 'pvr-request.json'), {'time': time.time(), 'collect': collect})


def sources(store):
    result = {}
    for entry in store.providers():
        if not entry.get('enabled', True):
            continue
        for cat in entry_catalogs(entry):
            if cat['type'] not in ('tv', 'channel', 'channels', 'live') or search_only(cat):
                continue
            genres = next((x.get('options', []) for x in cat.get('extra', []) if x.get('name') == 'genre'), [])
            uk = [str(g) for g in genres if str(g).upper() in ('UK', 'UNITED KINGDOM') or str(g).upper().startswith('UK ')]
            selections = uk if uk else [None]
            for genre in selections:
                extras = {'genre': genre} if genre else {}
                country = 'GB' if genre or re.search(r'(?:_uk(?:\s|$)|\bUK\b|united kingdom)', cat['id'] + ' ' + cat.get('name', ''), re.I) else ''
                key = digest([entry['manifest']['id'], cat['type'], cat['id'], extras])
                result[key] = dict(key=key, label=entry['label'] + ' / ' + cat.get('name', cat['id']) + (' / ' + genre if genre else ''),
                                   provider=entry['key'], provider_id=entry['manifest']['id'], catalog=cat,
                                   extras=extras, country=country, default=country == 'GB')
    return list(result.values())


def group_names(name, genres, country='GB'):
    name = normalized(name, True)
    text = name + ' ' + ' '.join(str(g).lower() for g in genres)
    groups = []
    if country == 'GB' and (name in FREEVIEW or name.startswith(('bbc one ', 'bbc two '))):
        groups.append('Freeview')
    if country == 'GB' and name.startswith('sky '):
        groups.append('Sky')
    if any(x in text for x in ('sport', 'tnt ', 'eurosport', 'racing', 'premier', 'football')):
        groups.append('Sports')
    elif any(x in text for x in ('cinema', 'movie', 'film4', 'film 4')):
        groups.append('Movies')
    elif any(x in text for x in ('news', 'parliament', 'bloomberg', 'cnbc')):
        groups.append('News')
    elif any(x in text for x in ('kids', 'cbbc', 'cbeebies', 'nick', 'cartoon', 'boomerang', 'baby')):
        groups.append('Kids')
    elif any(x in text for x in ('music', 'mtv', 'kerrang', 'clubland')):
        groups.append('Music')
    else:
        groups.append('Entertainment')
    if not any(g in groups for g in ('Freeview', 'Sky')):
        groups.insert(0, 'Other channels')
    return groups


def safe_meta(meta):
    allowed = ('id', 'type', 'name', 'logo', 'poster', 'thumbnail', 'background', 'description', 'genres',
               'country', 'tvg_id', 'tvgId', 'epg_id', 'epgId')
    return {key: meta[key] for key in allowed if key in meta}


def collect_source(store, source, fetch=fetch_json):
    entry, cat = store.provider(source['provider']), source['catalog']
    extras, result, seen, pages = dict(source['extras']), [], set(), set()
    for _ in range(25):
        data = fetch(resource_url(entry['url'], 'catalog', cat['type'], cat['id'], extras))
        metas = data.get('metas', [])
        signature = digest([m.get('id') for m in metas if isinstance(m, dict)])
        if not metas or signature in pages:
            break
        pages.add(signature)
        before = len(result)
        for meta in metas:
            if not isinstance(meta, dict) or not meta.get('id') or not meta.get('name') or meta['id'] in seen:
                continue
            seen.add(meta['id'])
            meta = dict(safe_meta(meta), type=cat['type'])
            country = country_for(meta, provider=entry) or source['country']
            # The first preset is deliberately UK only. Explicitly selected
            # catalogues can contain other countries without being relabelled UK.
            if source['country'] == 'GB' and country != 'GB':
                continue
            result.append(dict(provider=entry['key'], provider_id=entry['manifest']['id'], provider_label=entry['label'],
                               resource_type=cat['type'], live_group='tv', live_country=country, meta=meta))
        if len(result) == before or not any(x.get('name') == 'skip' for x in cat.get('extra', [])) or len(result) >= 3000:
            break
        extras['skip'] = int(extras.get('skip', 0)) + len(metas)
    return result[:3000]


def merge_channels(variants, previous=None, overrides=None):
    overrides = overrides or {}
    previous = {r['id']: r['number'] for r in previous or []}
    merged = {}
    for channel in variants:
        meta = channel['meta']
        country = country_for(meta, channel) or 'ZZ'
        name = normalized(meta['name'], True)
        key = 'cbr.' + digest([country, name, channel['provider_id'] if country == 'ZZ' else ''])
        row = merged.setdefault(key, dict(id=key, name=meta['name'], logo=meta.get('logo') or meta.get('poster', ''),
                                          groups=group_names(meta['name'], meta.get('genres') or [], country), variants=[]))
        identity = (channel['provider_id'], channel['resource_type'], meta['id'])
        if not any((c['provider_id'], c['resource_type'], c['meta']['id']) == identity for c in row['variants']):
            row['variants'].append(channel)
    used = {o['number'] for key, o in overrides.items() if key in merged}
    reserved = used | {number for key, number in previous.items() if key in merged}
    for row in merged.values():
        row['variants'].sort(key=lambda c: 2 if re.search(r'\b(4K|UHD)\b', c['meta']['name'], re.I)
                             else 0 if re.search(r'\b(FHD|HD)\b', c['meta']['name'], re.I) else 1)
        best = row['variants'][0]['meta']
        row['name'], row['logo'] = best['name'], best.get('logo') or best.get('poster', row['logo'])
    for row in sorted(merged.values(), key=lambda r: (FREEVIEW.get(normalized(r['name'], True), 999), r['name'].casefold())):
        if row['id'] in overrides:
            row['number'] = overrides[row['id']]['number']
            continue
        preferred = FREEVIEW.get(normalized(row['name'], True))
        old = previous.get(row['id'])
        number = old if old and old not in used else preferred if preferred and preferred not in used else 101
        while number in used or number in reserved and number != old or number in FREEVIEW.values() and number != preferred and number != old:
            number += 1
        row['number'] = number
        used.add(number)
    return list(merged.values())


def channels(store):
    rows = store.read(os.path.join(store.root, 'pvr-channels.json'), [])
    overrides = config(store).get('overrides', {})
    return [dict(row, **overrides.get(row['id'], {})) for row in rows]


def resolve_variant(store, variant):
    entries = [e for e in store.providers() if e.get('enabled', True)]
    entry = next((e for e in entries if e['key'] == variant['provider']), None)
    if entry is None:
        entry = next((e for e in entries if e['manifest']['id'] == variant['provider_id']
                      and e['label'] == variant.get('provider_label', e['label'])), None)
    if entry is None:
        same = [e for e in entries if e['manifest']['id'] == variant['provider_id']]
        entry = same[0] if len(same) == 1 else None
    return dict(variant, provider=entry['key']) if entry else None


def channel(store, identity):
    if not re.fullmatch(r'cbr\.[a-f0-9]{24}', identity):
        raise ValueError('Invalid TV channel.')
    row = next((r for r in channels(store) if r['id'] == identity and r.get('visible', True)), None)
    if not row:
        raise ValueError('This TV channel has changed. Refresh CBR TV channels.')
    variants = [current for v in row['variants'] if (current := resolve_variant(store, v))]
    if not variants:
        raise ValueError('This channel source is disabled or removed. Check CBR sources.')
    return row, variants


def atomically(path, raw):
    temporary = path + '.tmp'
    with open(temporary, 'wb') as target:
        target.write(raw)
    os.replace(temporary, path)


def export(store):
    folder = os.path.join(store.root, 'pvr')
    os.makedirs(folder, exist_ok=True)
    rows = [r for r in channels(store) if r.get('visible', True)
            and any(resolve_variant(store, v) for v in r['variants'])]
    rows.sort(key=lambda r: (r['number'], r['name'].casefold()))
    def escaped(value):
        return str(value).replace('\r', ' ').replace('\n', ' ').replace('"', "'")
    playlist, xml = ['#EXTM3U'], ET.Element('tv', {'generator-info-name': 'CBR Kodi TV'})
    guide = ProgrammeGuide(store)
    mapped = programme_count = 0
    try:
        for row in rows:
            if urlsplit(row['logo']).scheme not in ('http', 'https'):
                row = dict(row, logo='')
            playlist.append('#EXTINF:-1 tvg-id="{}" tvg-name="{}" tvg-chno="{}" tvg-logo="{}" group-title="{}",{}'.format(
                row['id'], escaped(row['name']), row['number'], escaped(row['logo']), ';'.join(['CBR TV'] + row['groups']), escaped(row['name'])))
            playlist.append(BASE + '?' + urlencode(dict(action='pvr_play', channel=row['id'])))
            node = ET.SubElement(xml, 'channel', {'id': row['id']})
            ET.SubElement(node, 'display-name').text = row['name']
            if row['logo']:
                ET.SubElement(node, 'icon', {'src': row['logo']})
            programmes = []
            for variant in row['variants']:
                current = resolve_variant(store, variant)
                if current:
                    programmes = guide.schedule(current, time.time() - 3600, time.time() + 7 * 86400)
                    if programmes:
                        break
            mapped += bool(programmes)
            for programme in programmes:
                stamp = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime('%Y%m%d%H%M%S +0000')
                node = ET.SubElement(xml, 'programme', {'channel': row['id'], 'start': stamp(programme['start']), 'stop': stamp(programme['stop'])})
                ET.SubElement(node, 'title').text = programme['title']
                if programme.get('description'):
                    ET.SubElement(node, 'desc').text = programme['description']
                programme_count += 1
    finally:
        guide.close()
    atomically(os.path.join(folder, 'channels.m3u'), ('\n'.join(playlist) + '\n').encode('utf-8'))
    atomically(os.path.join(folder, 'guide.xml'), ET.tostring(xml, encoding='utf-8', xml_declaration=True))
    return dict(channels=len(rows), guide_channels=mapped, programmes=programme_count, exported=time.time())


def save_channels(store, edits):
    existing = {r['id'] for r in channels(store)}
    value = config(store)
    overrides = value.setdefault('overrides', {})
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError('Invalid channel edit. Reload the TV channel editor.')
        if edit.get('id') not in existing:
            raise ValueError('A channel has changed. Reload the TV channel editor.')
        number = int(edit.get('number', 0))
        groups = edit.get('groups', [])
        if not 1 <= number <= 9999 or not isinstance(groups, list) or any(g not in GROUPS for g in groups):
            raise ValueError('Use channel numbers 1–9999 and the listed groups.')
        overrides[edit['id']] = dict(name=str(edit.get('name', '')).strip()[:100], number=number,
                                      groups=groups, visible=bool(edit.get('visible', True)))
        if not overrides[edit['id']]['name'] or not groups:
            raise ValueError('Each channel needs a name and at least one group.')
    rows = [dict(row, **overrides.get(row['id'], {})) for row in store.read(os.path.join(store.root, 'pvr-channels.json'), [])]
    numbers = [r['number'] for r in rows if r.get('visible', True)]
    if len(numbers) != len(set(numbers)):
        raise ValueError('Visible channels must have different channel numbers.')
    save_config(store, value)
    refresh(store, collect=False)


def configure_instance(profile, m3u, xmltv):
    """Create/update only CBR's own instance; preserve all unrelated instances."""
    os.makedirs(profile, exist_ok=True)
    filename, existing = None, {}
    for name in os.listdir(profile):
        if not re.fullmatch(r'instance-settings-\d+\.xml', name):
            continue
        path = os.path.join(profile, name)
        try:
            values = {n.get('id'): n.text for n in ET.parse(path).getroot().findall('setting')}
            if values.get('kodi_addon_instance_name') == 'CBR TV':
                filename = path
                existing = values
                break
        except (ET.ParseError, OSError):
            continue
    if not filename:
        number = 1908001
        while os.path.exists(os.path.join(profile, 'instance-settings-{}.xml'.format(number))):
            number += 1
        filename = os.path.join(profile, 'instance-settings-{}.xml'.format(number))
    values = dict(kodi_addon_instance_name='CBR TV', kodi_addon_instance_enabled='true',
                  m3uPathType='0', m3uPath=m3u, epgPathType='0', epgPath=xmltv,
                  m3uCache='false', epgCache='false', numberByOrder='false',
                  m3uRefreshMode='1', m3uRefreshIntervalMins='30', defaultProviderName='CBR',
                  tvGroupMode='0')
    existing.update(values)
    root = ET.Element('settings', {'version': '2'})
    for key, value in existing.items():
        ET.SubElement(root, 'setting', {'id': key}).text = value
    atomically(filename, ET.tostring(root, encoding='utf-8', xml_declaration=True))
    return filename


class PVRUpdater:
    def __init__(self, store):
        self.store, self.thread = store, None
        self.last_poll, self.last_request, self.last_guide = 0, 0, ''
        self.stop = threading.Event()

    def poll(self):
        if time.monotonic() - self.last_poll < 10 or self.thread and self.thread.is_alive():
            return
        self.last_poll = time.monotonic()
        self.store.write(os.path.join(self.store.root, 'pvr-service.json'), {'time': time.time()})
        value = config(self.store)
        if not value.get('enabled'):
            return
        message = self.store.read(os.path.join(self.store.root, 'pvr-request.json'), {})
        request = message.get('time', 0)
        forced = request > self.last_request
        state = self.store.read(os.path.join(self.store.root, 'pvr-status.json'), {})
        guide = digest([self.store.read(os.path.join(self.store.root, name), {}) for name in
                        ('programme-status.json', 'programme-settings.json')])
        collect = forced and message.get('collect', True) or time.time() - state.get('updated', 0) > 6 * 3600
        if collect and time.time() - state.get('attempted', 0) < 300 and request <= self.last_request:
            return
        if forced or collect or guide != self.last_guide:
            self.last_request, self.last_guide = request, guide
            self.thread = threading.Thread(target=self.build, args=(collect,), daemon=True)
            self.thread.start()

    def build(self, collect=True, fetch=fetch_json):
        path = os.path.join(self.store.root, 'pvr-status.json')
        previous = self.store.read(path, {})
        self.store.write(path, dict(previous, state='updating', attempted=time.time()))
        try:
            failed = []
            if collect:
                value, variants = config(self.store), []
                for source in sources(self.store):
                    if self.stop.is_set():
                        return
                    if not (source['default'] if value['selected'] is None else source['key'] in value['selected']):
                        continue
                    cached = os.path.join(self.store.root, 'pvr-source-' + source['key'] + '.json')
                    try:
                        collected = collect_source(self.store, source, fetch)
                        if not collected:
                            raise ValueError('No channels returned')
                        self.store.write(cached, collected)
                    except Exception:
                        collected = self.store.read(cached, [])
                        failed.append(source['label'])
                    variants.extend(collected)
                if not variants:
                    raise ValueError('No channels available')
                self.store.write(os.path.join(self.store.root, 'pvr-channels.json'), merge_channels(variants,
                    self.store.read(os.path.join(self.store.root, 'pvr-channels.json'), []), value.get('overrides', {})))
            result = export(self.store)
            self.store.write(path, dict(result, state='ready', updated=time.time() if collect else previous.get('updated', 0),
                                       attempted=time.time(), failed=failed))
        except Exception:
            self.store.write(path, dict(previous, attempted=time.time(), state='error',
                                       message='TV channels could not be updated. Previous files are kept. Check the selected sources.'))

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)
