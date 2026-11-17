"""Prepare isolated portable Windows Kodi with real public sources for visual QA."""
from pathlib import Path
from zipfile import ZipFile
import sys, json, os, threading, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
HOME=ROOT/'work/test-kodi-tv/portable_data'
for path in [ROOT/'windows/packages/plugin.video.stremio.bridge/plugin.video.stremio.bridge-0.11.3.zip',ROOT/'windows/packages/skin.crimsonbloodrequiem/skin.crimsonbloodrequiem-0.1.3.zip']:
    with ZipFile(path)as z:z.extractall(HOME/'addons')
addon=HOME/'addons/plugin.video.stremio.bridge';sys.path.insert(0,str(addon))
from resources.lib.core import Store
from resources.lib.defaults import ensure_defaults
from resources.lib import m3u,pvr,programmes,tv_defaults
profile=HOME/'userdata/addon_data/plugin.video.stremio.bridge'
# Use a separate test profile, backed up before this script is run.
store=Store(str(profile));ensure_defaults(store,str(addon))
selected=[]
for source in pvr.sources(store):
    entry=store.provider(source['provider'])
    if entry['url']in [m3u.UK_URL,m3u.PLUTO_URL] and source['catalog']['id']in ['m3u_uk','m3u_US']:selected.append(source['key'])
config=pvr.config(store);config.update(enabled=True,selected=selected);pvr.save_config(store,config)
feed=next(f for f in programmes.settings(store)['feeds']if f['url']==tv_defaults.PLUTO_EPG)
count=programmes.download_feed(store,feed,threading.Event());print('US programme feed imported:',count,flush=True)
pvr.PVRUpdater(store).build(collect=True)
status=store.read(os.path.join(store.root,'pvr-status.json'),{});assert status['state']=='ready',status
rows=pvr.channels(store);groups={g for r in rows if r.get('visible',True)for g in r['groups']}
assert {'UK TV','Pluto TV','Movies','Sports','News','Kids'}<=groups,groups
assert status['guide_channels']>100,status
print('Actual sources:',json.dumps({k:status[k]for k in ['channels','guide_channels','programmes','unavailable_slots','failed']}),flush=True)
print('Actual groups:',sorted(groups),flush=True)
pvr.configure_instance(str(HOME/'userdata/addon_data/pvr.iptvsimple'),
    'special://profile/addon_data/plugin.video.stremio.bridge/pvr/channels.m3u',
    'special://profile/addon_data/plugin.video.stremio.bridge/pvr/guide.xml')
settings=HOME/'userdata/guisettings.xml';tree=ET.parse(settings)
for setting in tree.getroot().iter('setting'):
    if setting.get('id')=='lookandfeel.skin':setting.text='skin.crimsonbloodrequiem';setting.set('default','false')
tree.write(settings,encoding='utf8',xml_declaration=True)
