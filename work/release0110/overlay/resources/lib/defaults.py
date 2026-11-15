"""Install public defaults once, without network access or private tokens."""
import json
import os
import hashlib
import time

from .core import normalize_url, validate_manifest


DEFAULTS = (
    ('Cinemeta', 'https://v3-cinemeta.strem.io/manifest.json', 'cinemeta.json'),
    ('Torrentio', 'https://torrentio.strem.fun/manifest.json', 'torrentio.json'),
)


def ensure_defaults(store, addon_path, force=False):
    from .daddylive import ensure_default
    ensure_default(store)
    ensure_live_defaults(store, addon_path, force)
    ensure_tv_0103(store, addon_path, force)
    from .pluto_defaults import ensure as ensure_pluto
    ensure_pluto(store, force)
    marker = os.path.join(store.root, 'combined-defaults-v1.json')
    if not force and store.read(marker):
        return
    entries = store.providers()
    for label, url, filename in DEFAULTS:
        path = os.path.join(addon_path, 'resources', 'defaults', filename)
        with open(path, encoding='utf-8-sig') as source:
            bundled = validate_manifest(json.load(source))
        # Keep personalised URLs, labels and enabled/disabled preferences intact.
        if any(e.get('manifest', {}).get('id') == bundled['id'] or
               normalize_url(e['url']) == url for e in entries):
            continue
        store.add(url, label, fetch=lambda ignored, manifest=bundled: manifest)
        entries = store.providers()
    store.write(marker, True)


def ensure_live_defaults(store, addon_path, force=False):
    marker = os.path.join(store.root, 'live-defaults-baseline-0100.json')
    if not force and store.read(marker):
        return
    path = os.path.join(addon_path, 'resources', 'defaults', 'live-providers.json')
    with open(path, encoding='utf-8-sig') as source:
        defaults = json.load(source)
    # Retire only the old public presets. Personal configured providers survive.
    retired = {
        'https://mediafusion.elfhosted.com/manifest.json',
        'https://tvvoo.stremio-italia.eu/cfg-it-uk-fr-de-pt-es-al-tr-nl-ar-bk-ru-ro-pl-bg/manifest.json',
    }
    entries = store.providers()
    for entry in entries:
        if normalize_url(entry['url']) in retired:
            entry['enabled'] = False
    store.save_providers(entries)
    for default in defaults:
        with open(os.path.join(os.path.dirname(path), default['manifest_file']), encoding='utf-8-sig') as source:
            bundled = validate_manifest(json.load(source))
        entries = store.providers()
        existing = next((e for e in entries if normalize_url(e['url']) == default['url'] or
                         e.get('manifest', {}).get('id') == bundled['id']), None)
        if existing:
            for name in ('live_group', 'scope_types', 'extra_catalogs', 'guide_country', 'kind'):
                if name in default:
                    existing.setdefault(name, default[name])
            store.save_providers(entries)
            continue
        if default.get('kind') == 'm3u':
            # Seed the synthetic manifest offline; fetch the playlist on browsing.
            entry = dict(key=hashlib.sha256(default['url'].encode()).hexdigest()[:24],
                         url=default['url'], label=default['label'], manifest=bundled, enabled=True)
            store.save_providers(entries + [entry])
        else:
            entry = store.add(default['url'], default['label'], fetch=lambda ignored, manifest=bundled: manifest)
        for name in ('live_group', 'scope_types', 'extra_catalogs', 'guide_country', 'kind'):
            if name in default:
                entry[name] = default[name]
        store.save_providers([entry if e['key'] == entry['key'] else e for e in store.providers()])
    _baseline_tv(store)
    store.write(marker, True)


def _baseline_tv(store):
    from . import pvr, programmes
    url = 'https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/gb.xml.gz'
    path = os.path.join(store.root, 'programme-settings.json')
    config = store.read(path, {'enabled': True, 'feeds': [], 'mappings': {}})
    if not any(feed.get('url') == url for feed in config['feeds']):
        config['feeds'].append(dict(key=programmes.feed_key(url), label='Samsung TV Plus UK guide',
                                   url=url, country='GB', enabled=True))
        programmes.save_settings(store, config)
        programmes.request_refresh(store)
    config = pvr.config(store)
    sources = pvr.sources(store)
    selected = config.get('selected')
    if selected is None:
        selected = [s['key'] for s in sources if s['default']]
    baseline = [s['key'] for s in sources if
                (s['provider_id'] == 'org.cbr.m3u.4b79acea3e313425' and s['catalog']['id'] == 'm3u_uk') or
                (s['provider_id'] == 'community.sports.fly' and s['catalog']['id'] == 'sports_live')]
    config['selected'] = list(dict.fromkeys(selected + baseline))
    pvr.save_config(store, config)
    if config.get('enabled'):
        store.write(os.path.join(store.root, 'pvr-request.json'), {'time': time.time(), 'collect': True})


def ensure_tv_0103(store, addon_path, force=False):
    marker = os.path.join(store.root, 'bbc-uk-tv-defaults-0103.json')
    if not force and store.read(marker):
        return
    from . import pvr, programmes
    path = os.path.join(addon_path, 'resources', 'defaults', 'bbc-duckkota.json')
    with open(path, encoding='utf8') as source:
        bundled = json.load(source)
    entries = store.providers()
    keys = []
    for template in bundled:
        existing = next((e for e in entries if e['url'] == template['url']), None)
        if existing is None:
            existing = dict(template, key=hashlib.sha256(template['url'].encode()).hexdigest()[:24], enabled=True)
            entries.append(existing)
        else:
            for name in ('include_tvg_ids', 'epg_ids', 'priority'):
                if name in template:
                    existing.setdefault(name, template[name])
        keys.append(existing['key'])
    store.save_providers(entries)
    config = pvr.config(store)
    sources = pvr.sources(store)
    selected = config.get('selected')
    if selected is None:
        selected = [s['key'] for s in sources if s['default']]
    config['selected'] = list(dict.fromkeys(selected + [s['key'] for s in sources if s['provider'] in keys and s['catalog']['id'] == 'm3u_uk']))
    for row in store.read(os.path.join(store.root, 'pvr-channels.json'), []):
        if programmes.normalized(row['name'], True) in {'channel 4', 'channel 5', 'sky news weather'} and any(programmes.country_for(v['meta'], v) == 'GB' for v in row['variants']):
            previous = config.setdefault('overrides', {}).get(row['id'], {})
            config['overrides'][row['id']] = dict(name=previous.get('name', row['name']), number=previous.get('number', row['number']),
                groups=[g for g in previous.get('groups', row['groups']) if g != 'Sky'] or ['UK TV'], visible=False)
    pvr.save_config(store, config)
    guide = programmes.settings(store)
    url = 'https://duckkota.github.io/iptv/epg/uk.xml.gz'
    if not any(f['url'] == url for f in guide['feeds']):
        guide['feeds'].append(dict(key=programmes.feed_key(url), label='UK TV guide', url=url, country='GB', enabled=True))
        programmes.save_settings(store, guide)
        programmes.request_refresh(store)
    if config.get('enabled'):
        pvr.refresh(store)
    store.write(marker, True)
