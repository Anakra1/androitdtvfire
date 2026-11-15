from pathlib import Path
from unittest.mock import patch
import ast, json, sys, tempfile, types

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
lib=HERE/'overlay/resources/lib'
for path in (HERE/'overlay').rglob('*.py'):ast.parse(path.read_text(encoding='utf8'),feature_version=(3,8))
resources=types.ModuleType('resources');resources.__path__=[str(HERE/'overlay/resources')];sys.modules['resources']=resources
library=types.ModuleType('resources.lib');library.__path__=[str(lib),'C:/Users/Chris/AppData/Roaming/Kodi/addons/plugin.video.stremio.bridge/resources/lib'];sys.modules['resources.lib']=library
from resources.lib.core import Store
from resources.lib import sports,pvr,daddylive
from resources.lib.live import LiveLibrary

def entry(key,kind,cats):
    return dict(key=key,url='https://example.org/'+key+'/manifest.json',label=key,kind=kind,enabled=True,
        live_group='sports'if key=='events'else'tv',manifest=dict(id=key,name=key,version='1',types=['tv','sport'],resources=['catalog','stream'],catalogs=cats))

with tempfile.TemporaryDirectory(dir=ROOT/'outputs',prefix='verified-live-sportstest-')as tmp:
    store=Store(tmp)
    events=entry('events','stremio',[dict(id='sports_football',type='sport'),dict(id='sports_live',type='sport')])
    tv=entry('tv','m3u',[dict(id='m3u_uk',type='tv')])
    dad=entry('daddy','daddylive',[dict(id='daddy_uk',type='tv'),dict(id='daddy_all',type='tv')]);dad['pvr_enabled']=False
    store.save_providers([events,tv,dad])
    def fetch(e,kind,media,identity,extras=None):
        if e['key']=='events'and identity=='sports_football':return {'metas':[dict(id='match',name='City vs United',type='sport',genres=['Football'])]}
        if e['key']=='events':return {'metas':[dict(id='main',name='(FHD) : SKY SPORTS MAIN EVENT',type='sport',genres=['Darts'])]}
        if e['key']=='tv':return {'metas':[dict(id='main-tv',name='Sky Sports Main Event',type='tv',country='GB'),dict(id='nfl',name='NFL Network',type='tv',country='US')]}
        return {'metas':[dict(id='daddy-main',name='Sky Sports Main Event',type='tv',country='GB'),dict(id='f1',name='Sky Sports F1',type='tv',country='GB'),dict(id='us-main',name='Sky Sports Main Event',type='tv',country='US')]}
    with patch.object(sports,'fetch_resource',side_effect=fetch):rows,errors=sports.listing(store,'football',True)
    assert not errors
    assert [r['meta']['name']for r in rows if not r['is_channel']]==['City vs United']
    assert not any('NFL'in r['meta']['name']or'F1'in r['meta']['name']for r in rows)
    main=next(r for r in rows if r['is_channel']and r['live_country']=='GB');assert len(main['sports_variants'])==3
    assert len([r for r in rows if r['is_channel']and r['live_country']=='US'])==1
    assert all(v['provider']!='daddy'for v in pvr.sources(store))
    saved=LiveLibrary(store).channel(main);assert len(saved['sports_variants'])==3
    tv['enabled']=False;store.save_providers([events,tv,dad])
    assert len(LiveLibrary(store).resolve(saved)['sports_variants'])==2
    def aggregate(entries,*args):
        e=entries[0];return [(e,{'streams':[dict(url='https://example.org/'+e['key']+'/'+str(i)+'.m3u8')for i in (1,2)]},None)]
    with patch.object(sports,'aggregate',side_effect=aggregate):streams=sports.streams(store,main)
    assert [s['name'].split(' / ')[0]for s in streams[:2]]==['events','daddy']
    before=pvr.config(store);daddylive.ensure_default(store);assert pvr.config(store)==before
    added=next(e for e in store.providers()if e['manifest']['id']=='org.cbr.daddylive');assert added['enabled']is False and added['pvr_enabled']is False
    legacy=Store(str(Path(tmp)/'legacy'));legacy.save_providers([dict(added,enabled=True,pvr_enabled=True)])
    daddylive.ensure_default(legacy)
    assert legacy.providers()[0]['enabled']is False and legacy.providers()[0]['pvr_enabled']is False

# Test the Crew handoff without installing or executing third-party software.
tree=ast.parse((HERE/'overlay/addon.py').read_text(encoding='utf8'))
function=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='crew_sport_link')
calls=[]
from urllib.parse import urlencode
scope={'rpc':lambda *args:{'addon':{'enabled':True}},'xbmcgui':types.SimpleNamespace(ListItem=lambda **kw:types.SimpleNamespace(setArt=lambda art:None)),
       'xbmcplugin':types.SimpleNamespace(addDirectoryItem=lambda handle,url,*args,**kwargs:calls.append(url)),
       'HANDLE':1,'ART':'art','os':__import__('os'),'urlencode':urlencode}
exec(compile(ast.Module(body=[function],type_ignores=[]),'crew-handoff','exec'),scope)
scope['crew_sport_link']('football');assert calls==['plugin://plugin.video.thecrew/?action=fifa']
calls.clear();scope['rpc']=lambda *args:{'addon':{'enabled':False}};scope['crew_sport_link']('football');assert not calls
print('Sport classification, event/channel separation, country-safe merging, provider diversity, disabled-source filtering, bookmarks, PVR isolation and Crew handoff passed.')
