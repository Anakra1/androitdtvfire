"""Publish frozen 0.9.0 code with platform packaging and its saved TVVoo source."""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://anakra1.github.io/androitdtvfire/'
ADDON = 'plugin.video.stremio.bridge'
REVISION = '05f482f'
original = subprocess.check_output(['git', 'show', REVISION + ':downloads/Windows/' + ADDON + '-0.9.0.zip'], cwd=ROOT)
with ZipFile(BytesIO(original)) as archive:
    files = {n: archive.read(n) for n in archive.namelist() if not n.endswith('/')}
prefix = ADDON + '/'
assert ET.fromstring(files[prefix + 'addon.xml']).get('version') == '0.9.0'
assert prefix + 'resources/lib/pvr.py' in files
assert not any(n.endswith(('/m3u.py', '/daddylive.py', '/live_hints.py')) for n in files)
old_defaults = json.loads(files[prefix + 'resources/defaults/live-providers.json'].decode('utf-8-sig'))
assert len(old_defaults) == 3
tvvoo_url = 'https://tvvoo.stremio-italia.eu/cfg-it-uk-fr-de-pt-es-al-tr-nl-ar-bk-ru-ro-pl-bg/manifest.json'
old_defaults.append(dict(label='TvVoo | ElfHosted', url=tvvoo_url, public_fallback_url=tvvoo_url,
                         manifest_file='tvvoo-090.json', live_group='tv', scope_types=['tv']))
files[prefix + 'resources/defaults/live-providers.json'] = json.dumps(old_defaults, indent=2).encode()
files[prefix + 'resources/defaults/tvvoo-090.json'] = (ROOT / 'work/legacy090/tvvoo.json').read_bytes()
files[prefix + 'README-090.txt'] = (
    'CBR 0.9.0 clean-install baseline. Playback Python code is byte-for-byte from commit 05f482f.\n'
    'Only platform addon.xml packaging and the previously used TVVoo default configuration differ.\n'
    'No DaddyLive, IPTV-org or later caching code is included.\n'
    'Use only the matching CBR 0.9.0 repository on a clean install to avoid updating to a newer branch.\n'
).encode()


def xml(path, root):
    raw = ET.tostring(root, encoding='UTF-8', xml_declaration=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.with_suffix(path.suffix + '.md5').write_text(hashlib.md5(raw).hexdigest(), encoding='ascii')


for platform, short in [('windows', 'w'), ('android', 'a')]:
    folder = ROOT / '090' / platform
    manifest = ET.fromstring(files[prefix + 'addon.xml'])
    manifest.find("extension[@point='xbmc.addon.metadata']/platform").text = platform
    if platform == 'windows':
        requires = manifest.find('requires')
        for requirement in list(requires):
            if requirement.get('addon') == 'script.module.cbr.engine': requires.remove(requirement)
    package_folder = folder / 'packages' / ADDON
    package_folder.mkdir(parents=True, exist_ok=True)
    package = package_folder / (ADDON + '-0.9.0.zip')
    with ZipFile(package, 'w', ZIP_DEFLATED, compresslevel=7) as target:
        for name, raw in files.items():
            if platform == 'android' and name.endswith('/resources/bin/windows-x64/TorrServer.exe'): continue
            if name == prefix + 'addon.xml': raw = ET.tostring(manifest, encoding='UTF-8', xml_declaration=True)
            target.writestr(name, raw)
    (ROOT / (short + '090.zip')).write_bytes(package.read_bytes())
    for asset in manifest.findall("extension[@point='xbmc.addon.metadata']/assets/*"):
        if asset.text and prefix + asset.text in files:
            path = package_folder / asset.text; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[prefix + asset.text])
    feed = ET.Element('addons'); feed.append(manifest); xml(folder / 'addons.xml', feed)
    dependency_feed = ET.Element('addons')
    allowed = {'script.crb.wizard', 'skin.crimsonbloodrequiem'}
    if platform == 'android': allowed.add('script.module.cbr.engine')
    for item in ET.parse(ROOT / platform / 'addons.xml').getroot():
        if item.get('id') in allowed:
            assert item.get('version') == ('0.1.0' if item.get('id') == 'script.module.cbr.engine' else '0.1.1')
            dependency_feed.append(item)
    assert {a.get('id') for a in dependency_feed} == allowed
    xml(folder / 'dependencies.xml', dependency_feed)
    repository_id = 'repository.cbr090.' + platform
    repository = ET.Element('addon', dict(id=repository_id, name='CBR 0.9.0 ' + platform.title() + ' Repository',
                                        version='0.1.0', **{'provider-name':'CBR Project'}))
    requires = ET.SubElement(repository, 'requires'); ET.SubElement(requires, 'import', dict(addon='xbmc.python', version='3.0.0'))
    extension = ET.SubElement(repository, 'extension', dict(point='xbmc.addon.repository'))
    for filename, data_path in [('addons.xml', '090/' + platform + '/packages/'),
                                ('dependencies.xml', platform + '/packages/')]:
        directory = ET.SubElement(extension, 'dir', dict(minversion='21.0.0'))
        ET.SubElement(directory, 'info').text = BASE + '090/' + platform + '/' + filename
        ET.SubElement(directory, 'checksum').text = BASE + '090/' + platform + '/' + filename + '.md5'
        ET.SubElement(directory, 'datadir', dict(zip='true')).text = BASE + data_path
    metadata = ET.SubElement(repository, 'extension', dict(point='xbmc.addon.metadata'))
    ET.SubElement(metadata, 'platform').text = 'all'
    ET.SubElement(metadata, 'license').text = 'GPL-3.0-or-later'
    ET.SubElement(metadata, 'summary', {'lang':'en_GB'}).text = 'Frozen CBR 0.9.0 clean-install repository'
    ET.SubElement(metadata, 'description', {'lang':'en_GB'}).text = 'Supplies CBR 0.9.0 and its existing skin, wizard and platform dependencies.'
    with ZipFile(ROOT / (short + '090repo.zip'), 'w', ZIP_DEFLATED) as target:
        target.writestr(repository_id + '/addon.xml', ET.tostring(repository, encoding='UTF-8', xml_declaration=True))
    with ZipFile(package) as target:
        assert target.testzip() is None
        for name, raw in files.items():
            if name.endswith('.py'): assert target.read(name) == raw, name
    print(platform + ': frozen 0.9.0 playback code and package integrity verified.')

current = ET.parse(ROOT / 'work/combined' / ADDON / 'addon.xml').getroot().get('version').replace('.', '')
names = ['repository.cbr.zip', 'windowsrepo.zip', 'cbr' + current + '.zip', 'cbrwindows.zip',
         'a090repo.zip', 'w090repo.zip', 'a090.zip', 'w090.zip']
listing = ['<!doctype html>', '<html lang="en"><head><meta charset="utf-8"><title>CBR Kodi repository</title></head>',
           '<body><h1>Crimson Blood Requiem</h1>', '<table><tr><th>Name</th><th>Size</th></tr>']
for name in names:
    listing.append('<tr><td><a href="{0}">{0}</a></td><td>{1} B</td></tr>'.format(name, (ROOT/name).stat().st_size))
(ROOT/'index.html').write_text('\n'.join(listing + ['</table>', '</body></html>']) + '\n', encoding='utf8')
print('Added 0.9.0 installers to the existing Kodi source listing.')
