"""Install public defaults once, without network access or private tokens."""
import json
import os

from .core import normalize_url, validate_manifest


DEFAULTS = (
    ('Cinemeta', 'https://v3-cinemeta.strem.io/manifest.json', 'cinemeta.json'),
    ('Torrentio', 'https://torrentio.strem.fun/manifest.json', 'torrentio.json'),
)


def ensure_defaults(store, addon_path, force=False):
    ensure_live_defaults(store, addon_path, force)
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
    from .m3u import ensure_default
    ensure_default(store, force)
    from .pvr import ensure_mediafusion_fallbacks
    ensure_mediafusion_fallbacks(store, addon_path)
    marker = os.path.join(store.root, 'live-defaults-v1.json')
    if not force and store.read(marker):
        return
    path = os.path.join(addon_path, 'resources', 'defaults', 'live-providers.json')
    with open(path, encoding='utf-8-sig') as source:
        defaults = json.load(source)
    for default in defaults:
        entries = store.providers()
        existing = next((e for e in entries if normalize_url(e['url']) == default['url']), None)
        if existing:
            for name in ('live_group', 'scope_types', 'extra_catalogs'):
                if name in default:
                    existing.setdefault(name, default[name])
            store.save_providers(entries)
            continue
        with open(os.path.join(os.path.dirname(path), default['manifest_file']), encoding='utf-8-sig') as source:
            bundled = validate_manifest(json.load(source))
        entry = store.add(default['url'], default['label'], fetch=lambda ignored, manifest=bundled: manifest)
        for name in ('live_group', 'scope_types', 'extra_catalogs'):
            if name in default:
                entry[name] = default[name]
        store.save_providers([entry if e['key'] == entry['key'] else e for e in store.providers()])
    store.write(marker, True)
