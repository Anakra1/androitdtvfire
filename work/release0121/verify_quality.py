"""Exercise quality classification and actual packaged directory routing without networks."""
from pathlib import Path
from zipfile import ZipFile
from types import SimpleNamespace
import tempfile,ast,sys,copy
ROOT=Path(__file__).resolve().parents[2]
for platform in ('android','windows'):
 with tempfile.TemporaryDirectory(dir=ROOT/'outputs',prefix='verified-live-quality-') as temp:
  with ZipFile(ROOT/platform/'packages/plugin.video.stremio.bridge/plugin.video.stremio.bridge-0.12.1.zip') as z:z.extractall(temp)
  addon=Path(temp)/'plugin.video.stremio.bridge';sys.path.insert(0,str(addon))
  import resources.lib.stream_quality as q
  cases=[('2160p','4k'),('4K UHD','4k'),('movie_2160p_WEB-DL','4k'),('3840x2160','4k'),('1080p','1080p'),('1080i','1080p'),('FHD','1080p'),('1920x1080','1080p'),('movie_1080p_x265','1080p'),('720p','720p'),('1280x720','720p'),('1440p','1440p'),('2K','1440p'),('480p','sd'),('576i','sd'),('SD','sd'),('1080p HDCAM','cam'),('4K CAM','cam'),('HDTS','cam'),('HD-TS','cam'),('TELESYNC','cam'),('TC','cam'),('WEB-DL','other'),('HD','other'),('CAMBRIDGE WEB-DL','other'),('2026','other')]
  for text,expected in cases:assert q.classify({'name':text})==expected,(text,q.classify({'name':text}))
  assert q.classify({'behaviorHints':{'filename':'movie.1080p.mkv'}})=='1080p'
  assert q.classify({'url':'https://example.test/1080p.m3u8?quality=4k'})=='other'
  assert q.classify({'filename':'movie.WEB-DL.1080p.ts'})=='1080p'
  assert q.classify({'filename':'movie.HDCAM.ts'})=='cam'
  assert q.classify({'resolution':{'bad':'data'},'behaviorHints':None})=='other'
  streams=[('provider',{'name':'1080p','url':'https://example.test/'+str(i)}) for i in range(2)]+[('provider',{'name':'1080p HDCAM','url':'https://example.test/cam'+str(i)}) for i in range(8)]
  original=copy.deepcopy(streams);shown,counts=q.select(streams,'hd')
  assert len(shown)==2 and counts=={'1080p':2,'cam':8} and streams==original
  assert q.summary('hd',2,counts)=='2 of 10 links shown · 8 hidden (8 CAM/TS/TC)'
  assert len(q.select(streams,'all')[0])==10 and len(q.select(streams,'4k')[0])==0
  assert len(q.select(streams,'cam')[0])==8 and q.mode('invalid')=='hd'
  # Execute the packaged listing functions, checking remembered choices and notice preservation.
  code=(addon/'addon.py').read_text(encoding='utf-8');tree=ast.parse(code);choice=[''];items=[];rendered=[];notices=[];saves=[]
  fixture=dict(type='series',id='episode',meta=dict(name='Fixture episode'),streams=streams+[('setup',{'kind':'configuration','name':'Renew provider'})])
  ns=dict(STORE=SimpleNamespace(get=lambda key:fixture),ADDON=SimpleNamespace(getSetting=lambda key:choice[0],setSetting=lambda key,value:(choice.__setitem__(0,value),saves.append(value))),
   DIALOG=SimpleNamespace(select=lambda *a,**kw:-1,textviewer=lambda *a:None),stream_kind=lambda s:s.get('kind','direct'),
   item=lambda *a,**kw:items.append((a,kw)),notify=notices.append,render_stream_links=lambda *a:rendered.extend(a[3]),
   xbmcplugin=SimpleNamespace(setPluginCategory=lambda *a:None),HANDLE=1,finish=lambda:None)
  nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('quality_list','quality_info')]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),'quality-routes','exec'),ns)
  ns['quality_list']('fixture');assert len(rendered)==3 and rendered[-1][1]['kind']=='configuration'
  assert '2 of 10 links shown' in items[1][0][0] and '8 CAM' in notices[-1]
  rendered.clear();ns['quality_list']('fixture',True);assert not saves and len(rendered)==3
  ns['DIALOG'].select=lambda *a,**kw:1
  rendered.clear();ns['quality_list']('fixture',True);assert saves==['4K only'] and len(rendered)==1 and 'No links match' in notices[-1]
  ns['DIALOG'].select=lambda *a,**kw:8
  rendered.clear();ns['quality_list']('fixture',True);assert choice[0]=='Show all qualities' and len(rendered)==11
  # Live TV and non-VOD types never enter this filter path.
  fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='show_streams')
  live=[];guard=dict(render_stream_links=lambda *a:live.append(a),finish=lambda:None,stream_kind=lambda s:'direct',notify=lambda *a:None)
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'streams','exec'),guard)
  guard['show_streams']('tv','channel',{},inline=[{'url':'https://example.test/live'}],channel={'provider':'live'})
  assert len(live)==1
  print(platform,'PASS: 26 label cases, metadata/URL isolation, CAM precedence, counts, cancellation, remembered choices, source notices and live-TV isolation')
  # Clear package modules so the next platform really imports its own ZIP contents.
  for name in list(sys.modules):
   if name=='resources' or name.startswith('resources.'):sys.modules.pop(name,None)
  sys.path.remove(str(addon))
