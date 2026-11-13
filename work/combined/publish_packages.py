"""Prepare the public Windows/Android feeds and Kodi-browsable source listing."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import shutil
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
OUTPUTS = PROJECT / 'outputs'
ADDON = 'plugin.video.stremio.bridge'
version = ET.parse(HERE / ADDON / 'addon.xml').getroot().get('version')
windows_zip = OUTPUTS / '{}-{}.zip'.format(ADDON, version)
android_zip = PROJECT / 'android/packages' / ADDON / windows_zip.name
with ZipFile(windows_zip) as source, ZipFile(android_zip, 'w', ZIP_DEFLATED, compresslevel=7) as target:
    for entry in source.infolist():
        if not entry.filename.endswith('/resources/bin/windows-x64/TorrServer.exe'):
            target.writestr(entry, source.read(entry.filename))

alias = 'cbr{}.zip'.format(version.replace('.', ''))
for path in [PROJECT / 'video.zip', PROJECT / alias,
             OUTPUTS / '{}-{}-android.zip'.format(ADDON, version),
             PROJECT / 'downloads/Fire-TV-Android' / '{}-{}-android.zip'.format(ADDON, version)]:
    shutil.copy2(android_zip, path)
for path in [PROJECT / 'cbrwindows.zip', PROJECT / 'downloads/Windows' / windows_zip.name]:
    shutil.copy2(windows_zip, path)

feed = ET.parse(PROJECT / 'android/addons.xml').getroot()
for old in list(feed):
    if old.get('id') == ADDON:
        feed.remove(old)
feed.append(ET.parse(HERE / ADDON / 'addon.xml').getroot())
raw = ET.tostring(feed, encoding='utf8', xml_declaration=True)
for folder in [PROJECT / 'android', HERE / 'repository.crb.android', PROJECT / 'windows']:
    folder.mkdir(exist_ok=True)
    (folder / 'addons.xml').write_bytes(raw)
    (folder / 'addons.xml.md5').write_text(hashlib.md5(raw).hexdigest(), encoding='ascii')

# Windows has its own feed so automatic updates retain the bundled EXE.
for item in feed:
    identity = item.get('id')
    filename = '{}-{}.zip'.format(identity, item.get('version'))
    destination = PROJECT / 'windows/packages' / identity / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = windows_zip if identity == ADDON else PROJECT / 'android/packages' / identity / filename
    shutil.copy2(source, destination)

repository = HERE / 'repository.crb.windows'
repository.mkdir(exist_ok=True)
manifest = (HERE / 'repository.crb.android/addon.xml').read_text(encoding='utf8')
manifest = manifest.replace('repository.crb.android', 'repository.crb.windows').replace(
    'CBR Android Add-on Repository', 'CBR Windows Add-on Repository').replace(
    'version="0.1.7"', 'version="0.1.0"').replace('/androitdtvfire/android/', '/androitdtvfire/windows/')
manifest = manifest.replace('Android TV and Fire TV', 'Windows').replace('Android torrent buffering', 'Windows torrent buffering')
(repository / 'addon.xml').write_text(manifest, encoding='utf8')
shutil.copytree(HERE / 'repository.crb.android/resources', repository / 'resources', dirs_exist_ok=True)
with ZipFile(PROJECT / 'windowsrepo.zip', 'w', ZIP_DEFLATED, compresslevel=7) as archive:
    for path in repository.rglob('*'):
        if path.is_file():
            archive.write(path, (Path(repository.name) / path.relative_to(repository)).as_posix())

names = ['repository.cbr.zip', 'windowsrepo.zip', alias, 'cbrwindows.zip']
listing = ['<!doctype html>', '<html lang="en"><head><meta charset="utf-8"><title>CBR Kodi repository</title></head>',
           '<body><h1>Crimson Blood Requiem</h1>', '<table><tr><th>Name</th><th>Size</th></tr>']
for name in names:
    listing.append('<tr><td><a href="{0}">{0}</a></td><td>{1} B</td></tr>'.format(name, (PROJECT / name).stat().st_size))
listing.extend(['</table>', '</body></html>'])
(PROJECT / 'index.html').write_text('\n'.join(listing) + '\n', encoding='utf8')
for path in [android_zip, windows_zip, PROJECT / 'windowsrepo.zip']:
    with ZipFile(path) as archive:
        assert archive.testzip() is None
print('Prepared public packages and separate Windows/Android feeds for CBR {}.'.format(version))
