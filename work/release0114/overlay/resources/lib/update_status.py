"""Read this project's public repository metadata; Kodi owns installation."""
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET
ALLOWED={'plugin.video.stremio.bridge','script.crb.wizard','skin.crimsonbloodrequiem','script.module.cbr.engine'}

def latest(platform):
    if platform not in ('windows','android'):raise ValueError('Unsupported platform')
    address='https://anakra1.github.io/androitdtvfire/'+platform+'/addons.xml'
    with urlopen(Request(address,headers={'User-Agent':'CBR-update-status/0.11.4'}),timeout=10)as response:raw=response.read(2*1024*1024+1)
    if len(raw)>2*1024*1024 or b'<!ENTITY'in raw.upper() or b'<!DOCTYPE'in raw.upper():raise ValueError('Invalid repository metadata')
    root=ET.fromstring(raw)
    if root.tag!='addons':raise ValueError('Invalid repository metadata')
    versions={a.get('id'):a.get('version')for a in root if a.get('id')in ALLOWED and (platform=='android'or a.get('id')!='script.module.cbr.engine')}
    if 'plugin.video.stremio.bridge'not in versions:raise ValueError('CBR version not found')
    return versions
