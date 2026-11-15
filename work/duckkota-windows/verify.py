"""Focused checks for the Windows DuckKota adapter overlay."""
from pathlib import Path
import importlib.util,json,hashlib
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('duckkota_adapter',ROOT/'m3u.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
base='https://DuckKota.github.io/iptv/playlists/best.m3u'
text='#EXTM3U\n#EXTINF:-1 tvg-id="Example.uk",Example (720p)\n#EXTVLCOPT:http-referrer=https://example.com/\nhttps://example.com/live.m3u8\n'
row=m.parse(text,base)[0]
assert row['id']=='m3u.duck.Example.uk'and row['country']=='GB'
old=m.parse(text,'https://example.com/list.m3u')[0]
assert old['id']=='m3u.'+hashlib.sha256(b'Example.uk').hexdigest()[:24]
assert old['streams'][0]['behaviorHints']['proxyHeaders']['request']['Referer']=='https://example.com/'
class Response:
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,*args):return json.dumps({'id':'Example.uk','streams':[{'url':'https://example.com/live.mpd'},{'url':'https://example.com/live.m3u8','user_agent':'Test/1','referrer':'https://example.com/'}]}).encode()
m.urlopen=lambda *a,**k:Response()
m.load=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Stream resolution downloaded the full channel list'))
result=m.resource({'url':base},'stream','tv',row['id'])['streams']
assert len(result)==2 and result[0]['url'].endswith('.m3u8')
assert result[0]['behaviorHints']['proxyHeaders']['request']['User-Agent']=='Test/1'
def unavailable(*args,**kwargs):raise OSError('API offline')
m.urlopen=unavailable;m.load=lambda *a,**k:[row]
assert m.resource({'url':base},'stream','tv',row['id'])['streams']==row['streams']
print('DuckKota targeted resolution, HLS preference, API outage fallback, country mapping, headers and legacy M3U identities passed.')
