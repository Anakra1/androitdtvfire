"""Control the isolated portable Kodi test instance through its local JSON-RPC API."""
from pathlib import Path
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET,json,base64,sys
ROOT=Path(__file__).resolve().parents[2]
s={e.get('id'):e.text or ''for e in ET.parse(ROOT/'work/test-kodi-tv/portable_data/userdata/guisettings.xml').getroot().iter('setting')}
h={'Content-Type':'application/json','Authorization':'Basic '+base64.b64encode((s['services.webserverusername']+':'+s['services.webserverpassword']).encode()).decode()}
params=json.loads(sys.argv[2])if len(sys.argv)>2 else {}
with urlopen(Request('http://127.0.0.1:'+s['services.webserverport']+'/jsonrpc',data=json.dumps(dict(jsonrpc='2.0',id=1,method=sys.argv[1],params=params)).encode(),headers=h),timeout=10)as r:print(r.read(2000).decode())
