"""Verify the release feeds and actual packages, including Windows payloads."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import ast
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote

ROOT=Path(__file__).resolve().parents[2]
VIDEO, WIZARD, SKIN='plugin.video.stremio.bridge','script.crb.wizard','skin.crimsonbloodrequiem'
for platform, wizard in [('android','0.3.4'),('windows','0.3.4')]:
    path=ROOT/platform/'addons.xml'; raw=path.read_bytes()
    assert hashlib.md5(raw).hexdigest()==path.with_suffix('.xml.md5').read_text().strip()
    feed=ET.fromstring(raw)
    for identity, version in [(VIDEO,'0.11.4'),(WIZARD,wizard),(SKIN,'0.1.3')]:
        manifest=feed.find("addon[@id='"+identity+"']"); assert manifest.get('version')==version
        package=ROOT/platform/'packages'/identity/(identity+'-'+version+'.zip')
        with ZipFile(package) as z:
            assert z.testzip() is None
            for name in z.namelist():
                assert name.startswith(identity+'/') and '..' not in Path(name).parts
                data=z.read(name)
                if name.endswith('.py'): ast.parse(data.decode('utf8'),feature_version=(3,8))
                if name.endswith('.json'): json.loads(data)
                if name.endswith('.xml'): ET.fromstring(data)
                if name.endswith(('.py','.json','.xml','.md')):
                    assert not re.search(rb'sports\.highfly\.(?:dev|to)/[0-9a-f]{8}-',data),name
            if identity==VIDEO:
                service=z.read(VIDEO+'/service.py').decode()
                assert 'startup_updates.poll(player' in service and 'except Exception:' in service
                assert 'startup_update_check' in z.read(VIDEO+'/resources/settings.xml').decode()
                native=ET.fromstring(z.read(VIDEO+'/addon.xml'))
                deps={d.get('addon')for d in native.find('requires')}
                assert ('script.module.cbr.engine'in deps)==(platform=='android')
                if platform=='windows':
                    old=ZipFile(ROOT/'windows/packages'/VIDEO/(VIDEO+'-0.10.1.zip'))
                    # Retain the original engine/tool payloads and setup module.
                    for name in old.namelist():
                        if name.lower().endswith(('.exe','.dll')) or name==VIDEO+'/cbr_full_setup.py':
                            assert z.read(name)==old.read(name),name
                    old.close()
    print(platform,'feed, versions, dependencies, code and native payloads passed')

with ZipFile(ROOT/'fulla034.zip') as z:
    prefix=WIZARD+'/resources/bundle/'
    for item in json.loads(z.read(prefix+'packages.json'))['packages']:
        raw=z.read(prefix+item['file'])
        assert hashlib.sha256(raw).hexdigest()==item['sha256']
        if item['id']==VIDEO:
            assert item['version']=='0.11.4'
            with ZipFile(BytesIO(raw)) as nested:
                assert 'startup_updates.poll' in nested.read(VIDEO+'/service.py').decode()
assert (ROOT/'fulla034.zip').read_bytes()==(ROOT/'fulla.zip').read_bytes()
assert (ROOT/'cbr0114.zip').read_bytes()==(ROOT/'video.zip').read_bytes()

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('href','src') and value:self.links.append(value)

for name in ['index.html','android.html','windows.html','help.html']:
    path=ROOT/'website'/name; parser=Links();parser.feed(path.read_text(encoding='utf8'))
    for link in parser.links:
        parts=urlsplit(link)
        if parts.scheme or parts.netloc or not parts.path:continue
        assert (path.parent/unquote(parts.path)).exists(),(name,link)
print('Bundled checksums, platform aliases and website download targets passed.')
