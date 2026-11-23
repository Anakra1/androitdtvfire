from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import json,re,hashlib,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/release0127-stage'
private=re.compile(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}[.][0-9a-f]{16}',re.I)
def scan(raw):
    with ZipFile(BytesIO(raw)) as z:
        assert z.testzip() is None
        for name in z.namelist():
            assert not name.endswith('/real-debrid-auth.json') and '/addon_data/' not in name,name
            content=z.read(name)
            if name.endswith('.zip'):scan(content)
            elif name.endswith(('.json','.xml','.py','.html','.js')):
                assert not private.search(content),'Personalised endpoint detected in '+name
for platform in ('windows','android'):
    for path in (OUT/platform).glob('*.zip'):scan(path.read_bytes())
    raw=(ROOT/platform/'addons.xml').read_bytes();assert hashlib.md5(raw).hexdigest()==(ROOT/platform/'addons.xml.md5').read_text().strip()
    addons={a.get('id'):a for a in ET.fromstring(raw)}
    assert addons['plugin.video.stremio.bridge'].get('version')=='0.12.7'
    assert addons['script.crb.wizard'].get('version')=='0.4.6'
class Links(HTMLParser):
    def __init__(self,page):super().__init__();self.page=page
    def handle_starttag(self,tag,attrs):
        for name,value in attrs:
            if name!='href' or not value:continue
            parsed=urlsplit(value)
            if parsed.scheme or parsed.netloc or not parsed.path:continue
            assert (self.page.parent/unquote(parsed.path)).exists(),str(self.page)+': '+value
for page in (ROOT/'index.html',ROOT/'website/index.html',ROOT/'website/android.html',ROOT/'website/windows.html',ROOT/'website/updates.html'):
    Links(page).feed(page.read_text(encoding='utf-8'))
print('Both feeds, nested bundle integrity, private-data exclusion and download links verified.')
