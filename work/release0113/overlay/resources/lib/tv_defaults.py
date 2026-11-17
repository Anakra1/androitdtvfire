"""Public TV additions: UK-first IPTV-org and NoCords Pluto; no private links."""
import hashlib
import os
import time
from . import m3u, pvr, programmes

PLUTO_EPG = 'https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/us.xml.gz'


def ensure(store, force=False):
    marker = os.path.join(store.root, 'tv-groups-defaults-0113.json')
    if not force and store.read(marker):
        return
    # Keep the worldwide list browsable by country; only its UK catalogue is a default.
    m3u.ensure_default(store)
    entries, added = store.providers(), []
    for url, label, country, groups in [(m3u.UK_URL, 'IPTV-org UK', 'GB', []),
                                       (m3u.PLUTO_URL, 'Pluto TV (NoCords)', 'US', ['Pluto TV'])]:
        entry = next((e for e in entries if e.get('url') == url), None)
        if entry is None:
            entry = dict(key=hashlib.sha256(url.encode()).hexdigest()[:24], url=url,
                         label=label, manifest=m3u.manifest(url), enabled=True, kind='m3u',
                         scope_types=['tv'], live_group='internet' if groups else 'tv',
                         guide_country=country, priority=110)
            entries.append(entry)
            added.append(entry['key'])
        entry.setdefault('pvr_groups', groups)
    # Apply the provider group to the existing UK Pluto source as well.
    for entry in entries:
        if entry.get('url') == 'https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_gb.m3u':
            entry.setdefault('pvr_groups', ['Pluto TV'])
    store.save_providers(entries)
    value = pvr.config(store)
    if added:
        sources = pvr.sources(store)
        selected = value.get('selected')
        if selected is None:
            selected = [s['key'] for s in sources if s['default']]
        value['selected'] = list(dict.fromkeys(selected + [s['key'] for s in sources if s['provider'] in added]))
        pvr.save_config(store, value)
    guide = programmes.settings(store)
    if not any(f['url'] == PLUTO_EPG for f in guide['feeds']):
        guide['feeds'].append(dict(key=programmes.feed_key(PLUTO_EPG), label='Pluto TV US programme guide',
                                  url=PLUTO_EPG, country='US', enabled=True))
        programmes.save_settings(store, guide)
    programmes.request_refresh(store)
    if value.get('enabled'):
        pvr.refresh(store)
    store.write(marker, {'time': time.time()})
