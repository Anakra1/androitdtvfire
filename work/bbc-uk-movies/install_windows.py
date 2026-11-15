"""Apply the reviewed overlay while Kodi is closed; retain existing TV sources."""
from pathlib import Path
import sys, shutil, json

ROOT = Path(__file__).resolve().parent
KODI = Path('C:/Users/Chris/AppData/Roaming/Kodi')
ADDON = KODI/'addons/plugin.video.stremio.bridge'
PROFILE = KODI/'userdata/addon_data/plugin.video.stremio.bridge'
OUT = ROOT.parent.parent/'outputs/verified-live-bbc-uk-movies-20261115'
BACKUP = OUT/'backup'
for name in ('providers.json', 'pvr-settings.json', 'pvr-channels.json', 'pvr-status.json', 'programme-settings.json'):
    if (PROFILE/name).exists() and not (BACKUP/name).exists(): shutil.copy2(PROFILE/name, BACKUP/name)
for name, destination in {'m3u.py':ADDON/'resources/lib/m3u.py', 'pvr.py':ADDON/'resources/lib/pvr.py',
                          'addon.py':ADDON/'addon.py', 'Home.xml':KODI/'addons/skin.crimsonbloodrequiem/xml/Home.xml'}.items():
    shutil.copy2(ROOT/name, destination)
sys.path.insert(0, str(ADDON))
from resources.lib.core import Store
from resources.lib import pvr
from resources.lib.m3u import load, resource
store = Store(str(PROFILE))
url = 'https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_uk.m3u8'
ids = ['BBCOne.uk','BBCTwo.uk','BBCThree.uk','BBCFour.uk','BBCAlba.uk','BBCScotland.uk',
       'BBCNews.uk','BBCParliament.uk','CBBC.uk','CBeebies.uk']
entry = store.add(url, 'BBC UK (Free-TV)')
entry.update(include_tvg_ids=ids, priority=10)
entry['manifest']['catalogs'] = [dict(id='m3u_uk', type='tv', name='BBC UK', country='GB',
                                   extra=[dict(name='search', isRequired=False)])]
store.save_providers([entry if e['key']==entry['key'] else e for e in store.providers()])
settings = pvr.config(store)
all_sources = pvr.sources(store)
source = next(s for s in all_sources if s['provider']==entry['key'])
if settings.get('selected') is not None and source['key'] not in settings['selected']:
    settings['selected'].append(source['key'])
pvr.save_config(store, settings)
fresh = pvr.collect_source(store, source)
assert len(fresh)==10 and {v['meta']['tvg_id'] for v in fresh}==set(ids)
assert all('Ⓖ' not in v['meta']['name'] for v in fresh)
store.write(str(PROFILE/('pvr-source-'+source['key']+'.json')), fresh)
# The selected BBC One feed is explicitly Yorkshire. Match its regional guide
# rather than guessing between the many BBC One regions with similar names.
from resources.lib.programmes import ProgrammeGuide
guide=ProgrammeGuide(store)
try:
    yorks=[c for c in guide.channels() if c['channel']=='BBC.One.Yorks.HD.uk']
    if yorks:
        guide.map_channel(next(v for v in fresh if v['meta']['tvg_id']=='BBCOne.uk'), yorks[0])
finally:
    guide.close()
variants=[]
for s in all_sources:
    if s['default'] if settings['selected'] is None else s['key'] in settings['selected']:
        variants.extend(store.read(str(PROFILE/('pvr-source-'+s['key']+'.json')), []))
rows = pvr.merge_channels(variants, store.read(str(PROFILE/'pvr-channels.json'), []), settings.get('overrides'))
for label in ('BBC One','BBC Two'):
    row=next(r for r in rows if r['name']==label)
    assert row['variants'][0]['provider']==entry['key'] and 'UK TV' in row['groups']
store.write(str(PROFILE/'pvr-channels.json'), rows)
result=pvr.export(store)
result.update(bbc_channels=len(fresh), uk_channels=sum('UK TV' in r['groups'] for r in rows), state='ready')
(OUT/'installation-results.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
