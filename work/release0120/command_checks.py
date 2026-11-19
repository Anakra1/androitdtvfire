"""Behavioural checks for history ownership, resume, next episode and local UI state."""
from pathlib import Path
from types import SimpleNamespace,ModuleType
import datetime,importlib.util,json,sys,tempfile,time,threading,xml.etree.ElementTree as ET
HERE=Path(__file__).parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE));from command_state import CommandState,identity,next_episode,upcoming,fingerprint,clean_meta
checks=0
def check(value):
 global checks;assert value;checks+=1
meta=dict(id='series',type='series',name='A series',poster='https://public.test/poster.jpg',stream={'url':'secret-resolved-url'},videos=[dict(id='e1',season=1,episode=1,released='2020-01-01T00:00:00Z'),dict(id='e2',season=1,episode=2,released='2020-01-02T00:00:00Z'),dict(id='future',season=1,episode=3,released='2099-01-01T00:00:00Z')])
with tempfile.TemporaryDirectory(dir=HERE) as temp:
 state=CommandState(temp)
 state.record('movie','a',dict(meta,type='movie'),10,200);check(not state.continuing())
 state.record('movie','a',dict(meta,type='movie'),60,200);check(state.continuing()[0]['position']==60)
 state.record('movie','a',dict(meta,type='movie'),190,200);check(not state.continuing())
 state.record('movie','nan',meta,float('nan'),200);check(state.get('movie','nan') is None)
 check('stream' not in clean_meta(meta))
 with state.connect() as c:check('secret-resolved-url' not in '\n'.join(c.iterdump()))
 state.record('series','e1',meta,190,200);row=state.continuing()[0]
 check(row['media_id']=='e2' and row['next_ready'] and row['position']==0)
 check(next_episode(meta,'e2') is None);check(next_episode(meta,'unknown') is None)
 state.record('series','e2',dict(meta,name='Episode two'),40,200)
 check(len(state.continuing())==1 and state.continuing()[0]['media_id']=='e2')
 check(state.toggle('watchlist','series:series',{'meta':clean_meta(meta)}));check(state.contains('watchlist','series:series'))
 check(not state.toggle('watchlist','series:series',{}));check(not state.saved('watchlist'))
 threads=[threading.Thread(target=state.record,args=('movie',str(i),meta,40,200)) for i in range(8)]
 [t.start() for t in threads];[t.join() for t in threads]
 check(all(state.get('movie',str(i)) is not None for i in range(8)))
 now=datetime.datetime(2026,11,18,18,0,tzinfo=datetime.timezone.utc)
 check(upcoming({'releaseInfo':'18 Nov 2026 • 21:30 UTC'},now));check(not upcoming({'releaseInfo':'LIVE'},now))
 check(not upcoming({'releaseInfo':'18 Nov 2026 • 17:30 UTC'},now));check(upcoming({'released':'2026-11-19T12:00:00Z'},now))
 # Actual player matching: late/stale callbacks and unrelated video cannot claim a CBR bookmark.
 props={}
 class Window:
  def __init__(self,*a):pass
  def getProperty(self,k):return props.get(k,'')
  def setProperty(self,k,v):props[k]=v
  def clearProperty(self,k):props.pop(k,None)
 sys.modules['xbmc']=SimpleNamespace(getCondVisibility=lambda *a:False)
 sys.modules['xbmcgui']=SimpleNamespace(Window=Window,WindowXMLDialog=object)
 package=ModuleType('commandtest');package.__path__=[str(HERE)];sys.modules['commandtest']=package
 for name in ['command_state','command_service']:
  spec=importlib.util.spec_from_file_location('commandtest.'+name,HERE/(name+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
 tracker_class=sys.modules['commandtest.command_service'].CommandTracker
 class Store:
  root=temp
  def read(self,path,default=None):
   try:return json.loads(Path(path).read_text())
   except FileNotFoundError:return default
  def write(self,path,data):Path(path).write_text(json.dumps(data))
 store=Store();tracker=tracker_class(store)
 class Player:
  path='owned.mp4';position=65;duration=200;seeks=[]
  def getPlayingFile(self):return self.path
  def getTime(self):return self.position
  def getTotalTime(self):return self.duration
  def isPlayingVideo(self):return True
  def seekTime(self,v):self.seeks.append(v)
 player=Player();pending=dict(kind='movie',media_id='owned',meta=clean_meta(meta),fingerprint=fingerprint('owned.mp4'),resume=45,created=time.time())
 store.write(tracker.pending,pending);player.path='unrelated.mp4';tracker.started(player)
 check(tracker.active is None and not player.seeks)
 player.path='owned.mp4';tracker.started(player);check(tracker.active is not None and player.seeks==[45])
 check(props.get('CBR.PlaybackFingerprint')==fingerprint('owned.mp4'))
 tracker.started(player);check(tracker.active is not None and player.seeks==[45])
 tracker.poll(player);tracker.event('stopped');check(tracker.state.get('movie','owned')['position']==65)
 check(tracker.active is None and not props.get('CBR.PlaybackFingerprint'))
 store.write(tracker.pending,pending);player.position=0;tracker.started(player);tracker.poll(player);tracker.event('stopped')
 check(tracker.state.get('movie','owned')['position']==65)
 player.position=65
 store.write(tracker.pending,dict(pending,created=time.time()-181));tracker.started(player);check(tracker.active is None)
 # Source resolution cancellation cannot hand a late video to Kodi.
 addon=ROOT/'work/test-kodi-tv/portable_data/addons/plugin.video.stremio.bridge'
 sys.path.insert(0,str(addon));ns=dict(STORE=store,xbmcgui=sys.modules['xbmcgui'])
 ns['HANDLE']=-1
 exec((HERE/'command_routes.py').read_text(encoding='utf-8'),ns)
 labels={}
 class Text:
  def setText(self,v):labels[self.id]=v
 class Label:
  def setLabel(self,v):labels[self.id]=v
 class Image:
  def setImage(self,v):labels[self.id]=v
 controls={}
 for number in [10,11,12,13,14,1201,1202,1203,1204,1205]:
  c=(Image() if number in (10,11) else Text() if number in (12,14) else Label());c.id=number;controls[number]=c
 detail=object.__new__(ns['CommandDetail']);detail.meta=meta;detail.caption='Play episode';detail.resume=0;detail.following=None;detail.favourite=False
 detail.getControl=lambda n:controls[n];detail.setFocusId=lambda *a:None
 ns['ART']=temp;detail.onInit();check(labels[12]=='A series' and labels[1201]=='Play episode')
 class Item:
  properties={}
  def getPath(self):return 'owned.mp4'
  def setProperty(self,k,v):self.properties[k]=v
 item=Item();saved=dict(type='movie',id='cancelled',meta=meta)
 props['CBR.PlaybackRequested']=str(time.time());store.write(str(Path(temp)/'command-cancel.json'),{'time':time.time()+1})
 check(ns['command_prepare'](saved,item) is False)
 store.write(str(Path(temp)/'command-cancel.json'),{})
 store.write(str(Path(temp)/'command-resume.json'),dict(id='cancelled',seconds=45,time=time.time()))
 check(ns['command_prepare'](saved,item));check(item.properties['StartOffset']=='45')
 record=store.read(str(Path(temp)/'command-pending.json'));check('path' not in record and 'stream' not in record)
 stopped=[]
 external=SimpleNamespace(isPlaying=lambda:True,getPlayingFile=lambda:'unrelated.mp4',stop=lambda:stopped.append(True))
 ns['xbmc']=SimpleNamespace(Player=lambda:external)
 ns['LIVE_AUTOPLAY']=SimpleNamespace(clear=lambda:None)
 ns['command_cancel']();check(not stopped)
 props['CBR.PlaybackFingerprint']=fingerprint('owned.mp4')
 external.getPlayingFile=lambda:'owned.mp4';ns['command_cancel']();check(stopped==[True])
 # A cancelled network job returns without waiting for the source response.
 closed=[]
 class Progress:
  def create(self,*a):pass
  def iscanceled(self):return True
  def update(self,*a):pass
  def close(self):closed.append(True)
 ns['xbmcgui'].DialogProgress=Progress
 ns['xbmc'].Monitor=lambda:SimpleNamespace(abortRequested=lambda:False,waitForAbort=lambda s:time.sleep(s))
 ns['BRAND']='CBR'
 start=time.monotonic();check(ns['command_job']('Test',lambda:time.sleep(.2)) is None)
 check(time.monotonic()-start<.15 and closed)
 # Validate all generated skin XML, including the common navigation and detail dialog.
 for path in (ROOT/'work/test-kodi-tv/portable_data/addons/skin.cbr.prototype/xml').glob('*.xml'):ET.parse(path)
 home=ET.parse(ROOT/'work/test-kodi-tv/portable_data/addons/skin.cbr.prototype/xml/Home.xml').getroot()
 rows=next(c for c in home.iter('control') if c.get('id')=='705')
 check(int(rows.findtext('height'))>=sum(int(g.findtext('height')) for g in rows.findall('control')[:2]))
 check(True)
# Exercise the actual built widget: outage uses matching cache, never another provider.
import ast,datetime
source=(ROOT/'work/test-kodi-tv/portable_data/addons/plugin.video.stremio.bridge/addon.py').read_text(encoding='utf-8')
fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='new_movies')
year=str(datetime.date.today().year);added=[]
cache=dict(version=2,provider='test-provider',year=year,time=0,movies=[{'id':'test','name':'Cached title'}])
widget_ns=dict(os=__import__('os'),STORE=SimpleNamespace(root='',read=lambda *a:cache),
 movie_catalogs=lambda:[({'key':'test-provider','manifest':{}},{'id':'year'})],
 fetch_resource=lambda *a:(_ for _ in ()).throw(OSError('offline')),
 add_metas=lambda *a:added.append(a),xbmcplugin=SimpleNamespace(setPluginCategory=lambda *a:None),HANDLE=1,finish=lambda *a:None)
exec(compile(ast.Module(body=[fn],type_ignores=[]),'widget','exec'),widget_ns)
widget_ns['new_movies']();check(len(added)==1)
added.clear();cache['provider']='different-provider';widget_ns['new_movies']();check(not added)
cache['provider']='test-provider';cache['year']=str(int(year)-1);widget_ns['new_movies']();check(not added)
print('PASS:',checks,'behavioural checks: history ownership, concurrency, resume, next episode, sports dates, cancellation and XML')
