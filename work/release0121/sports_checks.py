"""Protect provider isolation and playback identities in the prototype sports routes."""
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'test-kodi-tv/portable_data/addons/plugin.video.stremio.bridge'))
from resources.lib import live
primary=dict(key='primary',enabled=True,url='https://example.test/manifest.json',manifest={'id':'community.sports.fly'},label='Sports Streams')
other=dict(key='other',enabled=True,url='https://other.test/manifest.json',manifest={'id':'other'},label='Other')
cat=dict(id='sports_live',type='sport',name='Live Now')
media=dict(id='provider-specific-17',type='tv',name='Example match',genres=['Sports'],poster='https://example.test/art.png',logo='https://example.test/logo.png')
calls=[];items=[];saved=[]
store=SimpleNamespace(providers=lambda:[primary,other],put=lambda x:saved.append(x) or str(len(saved)))
def fetch(e,*args):calls.append(e['key']);return {'metas':[media,dict(id='news',name='Sky News',type='tv')] if e['key']=='other' else [media]}
class Cache:
 def __init__(self,s):pass
 def get(self,u,fn,**kw):return fn(u)
live.LiveCatalogueCache=Cache
ns=dict(STORE=store,entry_catalogs=lambda e:[cat],catalogue_group=lambda e,c:'sports',
        item=lambda *a,**kw:items.append((a,kw)),finish=lambda *a:None,notify=lambda *a:None,
        LIVE_LIBRARY=SimpleNamespace(begin_listing=lambda:None),fetch_resource=fetch,
        HANDLE=1,xbmcplugin=SimpleNamespace(setPluginCategory=lambda *a:None),
        xbmc=SimpleNamespace(executebuiltin=lambda *a:None,sleep=lambda *a:None,getSkinDir=lambda:'skin.crimsonbloodrequiem'),xbmcgui=SimpleNamespace(getCurrentWindowId=lambda:10025),DIALOG=SimpleNamespace(input=lambda *a:'sky'),
        catalogs=lambda query:[(primary,cat),(other,cat)],crew_sport_link=lambda *a:None)
exec(Path(__file__).with_name('sports_routes.py').read_text(encoding='utf-8'),ns)
ns['prototype_sports_catalog']()
assert calls==['primary'],calls
assert saved[-1]['resource_type']=='sport' and saved[-1]['meta']['id']==media['id']
assert items[-1][1]['meta']['poster']==media['poster']
assert 'logo' not in items[-1][1]['meta']
calls.clear();ns['catalogue_group']=lambda e,c:'sports' if e['key']=='primary' else 'tv'
ns['prototype_other_sports_search']()
assert calls==['other'],calls
assert not any(x['meta']['id']=='news' for x in saved)
primary['enabled']=False
assert ns['prototype_sports_entry']() is None
print('PASS: primary browsing isolated, other-source search excludes primary, provider resource IDs and posters preserved, disabled provider respected')
