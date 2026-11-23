"""Stage the boxing event box for Windows and Android; no publication."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
ADDON='plugin.video.stremio.bridge'
OUT=ROOT/'outputs/release0127-stage'

UI='''
def sports_ppv():
    from resources.lib.ppv import events,status
    entry=prototype_sports_entry()
    if not entry:
        item('Connect Sports Streams','web_setup',artwork='settings');finish();return
    rows,errors=events(STORE,entry)
    if errors:notify('Some event listings could not be reached. Refresh to try again.')
    if not rows:
        item('No boxing main event listed yet · check again','sports_ppv',artwork='live',meta={'name':'Boxing PPV main event','description':'Listings and links depend on the provider. Links may appear about one hour before broadcast; this is not guaranteed.'})
    for saved in rows:
        meta=dict(saved['meta'])
        meta['description']=status(meta)+'\\n\\n'+meta.get('description','')+'\\n\\nSelect to check fresh links. No stream is confirmed until playback starts.'
        saved=dict(saved,meta=meta)
        item(meta['name'],'sports_ppv_event',meta=meta,key=STORE.put(saved))
    item('Check again · refreshes every minute while open','sports_ppv',artwork='settings')
    xbmcplugin.setPluginCategory(HANDLE,'Boxing PPV · Main event')
    finish();prototype_sports_view()
    helper=os.path.join(ADDON.getAddonInfo('path'),'resources','lib','ppv_refresh.py')
    xbmc.executebuiltin('AlarmClock(CBRPPVRefresh,RunScript("{}"),00:01,silent)'.format(helper))


def sports_ppv_event(key):
    from resources.lib.ppv import status
    saved=STORE.get(key)
    entry=next((e for e in STORE.providers() if e['key']==saved['provider'] and e.get('enabled',True)),None)
    if entry is None:notify('This source is disabled.');finish();return
    try:
        data=fetch_resource(entry,'stream',saved['resource_type'],saved['meta']['id'])
    except Exception:
        DIALOG.ok(BRAND,'The provider could not be reached. Try again shortly.');finish();return
    streams=[s for s in data.get('streams',[]) if isinstance(s,dict) and any(s.get(k) for k in ('url','infoHash','externalUrl','ytId'))]
    if not streams:
        DIALOG.ok(BRAND,'No links available yet.\\n\\n'+status(saved['meta'])+'\\n\\nProviders may publish links around one hour before broadcast, later, or not at all. Use Back, then Check again.');finish();return
    show_streams(saved['resource_type'],saved['meta']['id'],saved['meta'],inline=streams,channel=saved,autoplay=False)


'''

for platform in ('windows','android'):
    with ZipFile(ROOT/'outputs/release0126-stage'/platform/(ADDON+'-0.12.6.zip')) as archive:
        files={n:archive.read(n) for n in archive.namelist() if not n.endswith('/')}
    code=files[ADDON+'/addon.py'].decode('utf-8-sig').replace('\r\n','\n')
    code=code.replace('def sports_home():\n','def sports_home():\n    item("Boxing PPV · Main event", "sports_ppv", artwork="live")\n',1)
    code=code.replace('def prototype_sports_categories():\n','def prototype_sports_categories():\n    item("Boxing PPV · Main event", "sports_ppv", artwork="live")\n',1)
    code=code.replace('    entry=prototype_sports_entry()\n    if not entry:\n        if not widget:', '    if widget and not identity:\n        item("Boxing PPV · Main event", "sports_ppv", artwork="live", meta={"name":"Boxing PPV · Main event","description":"Event pictures, start times and fresh link checks. Links may appear around one hour before broadcast."})\n    entry=prototype_sports_entry()\n    if not entry:\n        if not widget:',1)
    code=code.replace('def prototype_other_sports_search():',UI+'def prototype_other_sports_search():',1)
    code=code.replace("        elif action == 'prototype_sports_categories':", "        elif action == 'sports_ppv':\n            sports_ppv()\n        elif action == 'sports_ppv_event':\n            sports_ppv_event(params['key'])\n        elif action == 'prototype_sports_categories':",1)
    assert 'def sports_ppv():' in code and 'elif action == \'sports_ppv\':' in code
    files[ADDON+'/addon.py']=code.encode('utf-8')
    components=json.loads(files[ADDON+'/resources/defaults/release-components.json'])
    components[ADDON]='0.12.7'
    components['script.crb.wizard']='0.4.6'
    files[ADDON+'/resources/defaults/release-components.json']=json.dumps(components).encode('utf-8')
    for path in (HERE/'overlay').rglob('*.py'):files[ADDON+'/'+path.relative_to(HERE/'overlay').as_posix()]=path.read_bytes()
    manifest=ET.fromstring(files[ADDON+'/addon.xml']);manifest.set('version','0.12.7')
    news=manifest.find("extension[@point='xbmc.addon.metadata']/news")
    if news is not None:news.text='Boxing main-event box with expected link windows and fresh availability checks. Optional Real-Debrid sign-in; built-in playback stays the default. Back to Kodi Settings.'
    files[ADDON+'/addon.xml']=ET.tostring(manifest,encoding='utf-8',xml_declaration=True)
    for name,content in files.items():
        if name.endswith('.py'):ast.parse(content.decode('utf-8-sig'),filename=name,feature_version=(3,8))
    folder=OUT/platform;folder.mkdir(parents=True,exist_ok=True)
    with ZipFile(folder/(ADDON+'-0.12.7.zip'),'w',ZIP_DEFLATED) as archive:
        for name,content in files.items():archive.writestr(name,content)
    if platform=='windows':
        for name,content in files.items():
            path=HERE/'stage'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    print(platform,'0.12.7 syntax and ZIP built')
