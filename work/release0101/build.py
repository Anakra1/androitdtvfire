"""Package the accepted baseline without altering the frozen 0.9.0 installers."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
VERSION = '0.10.1'
ADDON = 'plugin.video.stremio.bridge'
PREFIX = ADDON + '/'
BASE_HASH = '0fce710047b4171bd997ef3f54b83f3245a498d8080e671256430e28eb1e53ec'
base = ROOT / 'w090.zip'
assert hashlib.sha256(base.read_bytes()).hexdigest() == BASE_HASH
with ZipFile(base) as archive:
    files = {name: archive.read(name) for name in archive.namelist() if not name.endswith('/') and '__pycache__' not in name}
for path in (HERE / 'overlay').rglob('*'):
    if path.is_file():
        files[PREFIX + path.relative_to(HERE / 'overlay').as_posix()] = path.read_bytes()
keep_defaults = {'cinemeta.json', 'torrentio.json', 'pluto.json', 'sports.json', 'samsung.json',
                 'live-providers.json', 'm3u-countries.json', 'samsung-unsupported.json'}
files = {name: raw for name, raw in files.items() if
         not name.startswith(PREFIX + 'resources/defaults/') or name.rsplit('/', 1)[-1] in keep_defaults}
files.pop(PREFIX + 'README-090.txt', None)
files[PREFIX + 'README.md'] = (HERE / 'README.md').read_bytes()
for name, raw in files.items():
    if name.endswith('.py'):
        ast.parse(raw.decode('utf-8-sig'), filename=name)
    elif name.endswith('.json'):
        json.loads(raw.decode('utf-8-sig'))
    elif name.endswith('.xml'):
        ET.fromstring(raw)
assert hashlib.sha256(files[PREFIX + 'resources/bin/windows-x64/TorrServer.exe']).hexdigest() == \
    '3a96b97a24d86a90c0712a6ec47d4ed52edc7eabac1bce6a0d9bbc8fd30de5bb'

def manifest(platform):
    root = ET.fromstring(files[PREFIX + 'addon.xml'])
    root.set('version', VERSION)
    root.find("extension[@point='xbmc.addon.metadata']/platform").text = platform
    requires = root.find('requires')
    for dependency in list(requires):
        if dependency.get('addon') == 'script.module.cbr.engine':
            requires.remove(dependency)
    if platform == 'android':
        ET.SubElement(requires, 'import', {'addon': 'script.module.cbr.engine', 'version': '0.1.0'})
    metadata = root.find("extension[@point='xbmc.addon.metadata']")
    metadata.find('description').text = ('CBR movies and TV episodes with Torrentio and integrated torrent buffering. '
        'Samsung TV Plus UK channels and guide, configured Sports Streams, and PC/phone source setup. '
        'Sports playback requires a working configured provider link. Android uses the automatically installed CBR Playback Engine dependency.')
    news = metadata.find('news')
    if news is None:
        news = ET.SubElement(metadata, 'news')
    news.text = '0.10.1: Accepted Samsung UK / Sports Streams baseline; matching Windows and Android packages; obsolete public TV presets retired. Restart Kodi after updating.'
    return root

def xml(path, tree):
    raw = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
    path.write_bytes(raw)
    path.with_suffix('.xml.md5').write_text(hashlib.md5(raw).hexdigest(), encoding='ascii')

packages = {}
# Full setup is the install entry point. Kodi resolves video, skin and the
# platform-specific official IPTV Simple client before the wizard can run.
WIZARD = 'script.crb.wizard'
wizard_base = ROOT/'android/packages'/WIZARD/f'{WIZARD}-0.1.1.zip'
assert hashlib.sha256(wizard_base.read_bytes()).hexdigest() == '0da2db733058624546aad3b7f5142893c6776ff72c896e29cb7e036030ce6fd2'
with ZipFile(wizard_base) as archive:
    wizard_files = {n:archive.read(n) for n in archive.namelist() if not n.endswith('/')}
wizard_manifest = ET.fromstring(wizard_files[WIZARD+'/addon.xml'])
wizard_manifest.set('version','0.2.0')
for dependency in wizard_manifest.find('requires'):
    if dependency.get('addon') == ADDON:dependency.set('version',VERSION)
ET.SubElement(wizard_manifest.find('requires'),'import',{'addon':'pvr.iptvsimple','version':'21.0.0'})
wizard_meta=wizard_manifest.find("extension[@point='xbmc.addon.metadata']")
wizard_meta.find('summary').text='Full CBR install: movies, TV, channels, guide and crimson interface'
wizard_meta.find('description').text='Installs the required CBR video add-on, skin and official IPTV Simple client. Run Full install to configure sources, build the channels and programme guide, and apply the CBR interface. Existing personal settings are retained.'
wizard_files[WIZARD+'/addon.xml']=ET.tostring(wizard_manifest,encoding='utf8',xml_declaration=True)
for path in (HERE/'wizard').glob('*.py'):
    ast.parse(path.read_text(encoding='utf8'))
    wizard_files[WIZARD+'/'+path.name]=path.read_bytes()
for platform in ('windows','android'):
    folder=ROOT/platform/'packages'/WIZARD
    folder.mkdir(parents=True,exist_ok=True)
    with ZipFile(folder/f'{WIZARD}-0.2.0.zip','w',ZIP_DEFLATED,compresslevel=7)as archive:
        for name,raw in sorted(wizard_files.items()):archive.writestr(name,raw)
shutil.copy2(ROOT/'android/packages'/WIZARD/f'{WIZARD}-0.2.0.zip',ROOT/'full.zip')

for platform in ('windows', 'android'):
    metadata = manifest(platform)
    folder = ROOT / platform / 'packages' / ADDON
    folder.mkdir(parents=True, exist_ok=True)
    package = folder / f'{ADDON}-{VERSION}.zip'
    with ZipFile(package, 'w', ZIP_DEFLATED, compresslevel=7) as archive:
        for name, raw in sorted(files.items()):
            if platform == 'android' and '/resources/bin/windows-x64/' in name:
                continue
            if name == PREFIX + 'addon.xml':
                raw = ET.tostring(metadata, encoding='utf-8', xml_declaration=True)
            archive.writestr(name, raw)
    with ZipFile(package) as archive:
        assert archive.testzip() is None
    packages[platform] = package
    # Update only the video entry; retain the working skin, wizard and engine.
    feed = ET.parse(ROOT / platform / 'addons.xml').getroot()
    for old in list(feed):
        if old.get('id') in (ADDON,WIZARD):
            feed.remove(old)
    feed.append(metadata)
    feed.append(ET.fromstring(ET.tostring(wizard_manifest)))
    xml(ROOT / platform / 'addons.xml', feed)
    for asset in metadata.findall("extension[@point='xbmc.addon.metadata']/assets/*"):
        if asset.text:
            path = folder / asset.text
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[PREFIX + asset.text])
    download = ROOT / 'downloads' / ('Windows' if platform == 'windows' else 'Fire-TV-Android')
    download.mkdir(parents=True, exist_ok=True)
    name = f'{ADDON}-{VERSION}' + ('-android' if platform == 'android' else '') + '.zip'
    shutil.copy2(package, download / name)
    shutil.copy2(ROOT/'full.zip',download/'CBR-Full-Install-0.2.0.zip')

for name in ('video.zip', 'cbr0101.zip'):
    shutil.copy2(packages['android'], ROOT / name)
shutil.copy2(packages['windows'], ROOT / 'cbrwindows.zip')
names = ['repository.cbr.zip', 'windowsrepo.zip', 'full.zip', 'cbr0101.zip', 'cbrwindows.zip',
         'a090repo.zip', 'w090repo.zip', 'a090.zip', 'w090.zip']
listing = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>CBR Kodi repository</title></head>',
           '<body><h1>Crimson Blood Requiem</h1><table><tr><th>Name</th><th>Size</th></tr>']
for name in names:
    listing.append(f'<tr><td><a href="{name}">{name}</a></td><td>{(ROOT/name).stat().st_size} B</td></tr>')
listing.append('</table></body></html>')
(ROOT / 'index.html').write_text('\n'.join(listing)+'\n', encoding='utf8')
subprocess.run([sys.executable, str(ROOT / 'work/build_website.py')], check=True)
print('Built CBR 0.10.1 for Windows and Android; feeds, aliases and website updated.')
