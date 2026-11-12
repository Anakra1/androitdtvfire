"""Build Windows and Android CBR Kodi repositories, skin and setup wizard."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import hashlib
import shutil
import xml.etree.ElementTree as ET


ROOT = Path(__file__).parent
OUTPUTS = ROOT.parent.parent / 'outputs' if ROOT.parent.name == 'work' else ROOT / 'outputs'
OUTPUTS.mkdir(exist_ok=True)
SKIN = ROOT / 'skin.crimsonbloodrequiem'
WIZARD = ROOT / 'script.crb.wizard'
ENGINE = ROOT / 'script.module.cbr.engine'
VIDEO_ZIP = OUTPUTS / 'plugin.video.stremio.bridge-0.6.2.zip'
ANDROID_VIDEO_ZIP = OUTPUTS / 'plugin.video.stremio.bridge-0.6.2-android.zip'

if not VIDEO_ZIP.is_file():
    raise SystemExit('Missing the current CBR video add-on installer.')


def addon_xml(source):
    return ET.parse(source / 'addon.xml').getroot()


def create_addon_zip(source, destination):
    addon_id = addon_xml(source).attrib['id']
    with ZipFile(destination, 'w', ZIP_DEFLATED, compresslevel=7) as archive:
        for path in source.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            archive.write(path, (Path(addon_id) / path.relative_to(source)).as_posix())


skin_zip = OUTPUTS / 'CBR-Space-Skin-0.1.1.zip'
wizard_zip = OUTPUTS / 'CBR-Setup-Wizard-0.1.1.zip'
create_addon_zip(SKIN, skin_zip)
create_addon_zip(WIZARD, wizard_zip)
engine_zip = OUTPUTS / 'script.module.cbr.engine-0.1.0.zip'
create_addon_zip(ENGINE, engine_zip)

# The Android package gets shared libraries through its Kodi dependency.
# Keep the Windows engine bundled, while omitting its EXE from Android.
with ZipFile(VIDEO_ZIP) as source, ZipFile(ANDROID_VIDEO_ZIP, 'w', ZIP_DEFLATED, compresslevel=7) as target:
    for item in source.infolist():
        if item.filename.endswith('/resources/bin/windows-x64/TorrServer.exe'):
            continue
        target.writestr(item, source.read(item.filename))

SERVICE = '''import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import xbmc
import xbmcaddon


PORT = 8765
addon_path = xbmcaddon.Addon().getAddonInfo("path")
handler = functools.partial(SimpleHTTPRequestHandler, directory=addon_path)
server = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
monitor = xbmc.Monitor()
try:
    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
finally:
    server.shutdown()
    server.server_close()
'''


def create_repository(repo_id, title, version, video_zip, summary, description):
    repository = ROOT / repo_id
    if repository.exists():
        shutil.rmtree(repository)
    packages = repository / 'packages'
    packages.mkdir(parents=True)
    for addon_id, package in (
        ('skin.crimsonbloodrequiem', skin_zip),
        ('script.crb.wizard', wizard_zip),
        ('plugin.video.stremio.bridge', video_zip),
        ('script.module.cbr.engine', engine_zip),
    ):
        directory = packages / addon_id
        directory.mkdir(parents=True, exist_ok=True)
        # Kodi resolves repository package URLs from the add-on ID and version.
        # Keep the platform-specific download name outside the repository, and
        # publish every repo package under Kodi's canonical <id>-<version>.zip.
        addon_source = SKIN if addon_id == 'skin.crimsonbloodrequiem' else WIZARD if addon_id == 'script.crb.wizard' else ENGINE if addon_id == 'script.module.cbr.engine' else ROOT / 'plugin.video.stremio.bridge'
        addon_version = addon_xml(addon_source).attrib['version']
        shutil.copy2(package, directory / '{}-{}.zip'.format(addon_id, addon_version))

    (repository / 'service.py').write_text(SERVICE, encoding='utf-8')
    repo_manifest = '''<?xml version="1.0" encoding="UTF-8"?>
<addon id="{repo_id}" name="{title}" version="{version}" provider-name="CBR Project">
  <requires><import addon="xbmc.python" version="3.0.0"/></requires>
  <extension point="xbmc.addon.repository">
    <dir minversion="21.0.0">
      <info>http://127.0.0.1:8765/addons.xml</info>
      <checksum>http://127.0.0.1:8765/addons.xml.md5</checksum>
      <datadir zip="true">http://127.0.0.1:8765/packages/</datadir>
    </dir>
  </extension>
  <extension point="xbmc.service" library="service.py" start="startup"/>
  <extension point="xbmc.addon.metadata">
    <platform>all</platform>
    <license>GPL-3.0-or-later</license>
    <summary lang="en_GB">{summary}</summary>
    <description lang="en_GB">{description}</description>
    <assets><icon>resources/icon.png</icon><fanart>resources/fanart.jpg</fanart></assets>
  </extension>
</addon>
'''.format(repo_id=repo_id, title=title, version=version, summary=summary, description=description)
    (repository / 'addon.xml').write_text(repo_manifest, encoding='utf-8')
    if repo_id == 'repository.crb.android':
        repo_manifest = repo_manifest.replace('http://127.0.0.1:8765/', 'https://anakra1.github.io/androitdtvfire/android/')
        repo_manifest = repo_manifest.replace('  <extension point="xbmc.service" library="service.py" start="startup"/>\n', '')
        (repository / 'addon.xml').write_text(repo_manifest, encoding='utf-8')
    resources = repository / 'resources'
    resources.mkdir()
    shutil.copy2(SKIN / 'resources' / 'icon.png', resources / 'icon.png')
    shutil.copy2(SKIN / 'resources' / 'fanart.jpg', resources / 'fanart.jpg')

    addon_roots = [addon_xml(SKIN), addon_xml(WIZARD), addon_xml(ENGINE)]
    with ZipFile(video_zip) as archive:
        manifest = next(name for name in archive.namelist() if name.endswith('/addon.xml'))
        addon_roots.append(ET.fromstring(archive.read(manifest)))
    metadata_root = ET.Element('addons')
    metadata_root.extend(addon_roots)
    metadata = ET.tostring(metadata_root, encoding='utf-8', xml_declaration=True)
    (repository / 'addons.xml').write_bytes(metadata)
    (repository / 'addons.xml.md5').write_text(hashlib.md5(metadata).hexdigest(), encoding='ascii')
    ET.parse(repository / 'addon.xml')
    ET.parse(repository / 'addons.xml')

    if repo_id == 'repository.crb.android':
        published = ROOT.parent.parent / 'android'
        published.mkdir(exist_ok=True)
        shutil.copytree(packages, published / 'packages', dirs_exist_ok=True)
        for name in ('addons.xml', 'addons.xml.md5'):
            shutil.copy2(repository / name, published / name)

    package_name = 'CBR-Windows-Repository-{}.zip'.format(version) if repo_id == 'repository.crb' else 'CBR-Fire-TV-Android-Repository-{}.zip'.format(version)
    destination = OUTPUTS / package_name
    with ZipFile(destination, 'w', ZIP_DEFLATED, compresslevel=7) as archive:
        for path in repository.rglob('*'):
            if path.is_file():
                if repo_id == 'repository.crb.android' and (path.name in ('service.py', 'addons.xml', 'addons.xml.md5') or 'packages' in path.relative_to(repository).parts):
                    continue
                archive.write(path, (Path(repo_id) / path.relative_to(repository)).as_posix())
    return destination


windows_repo = create_repository(
    'repository.crb', 'CBR Add-on Repository', '0.1.9', VIDEO_ZIP,
    "CBR's local Windows setup repository",
    'Provides the CBR skin, setup wizard and Windows video add-on package.',
)
android_repo = create_repository(
    'repository.crb.android', 'CBR Android Add-on Repository', '0.1.7', ANDROID_VIDEO_ZIP,
    "CBR's Android TV and Fire TV repository",
    'Provides the CBR skin, setup wizard, video add-on and integrated playback-engine dependency through one HTTPS repository.',
)

for path in (skin_zip, wizard_zip, windows_repo, android_repo, ANDROID_VIDEO_ZIP):
    with ZipFile(path) as archive:
        assert archive.testzip() is None
    print('{}: {:,} bytes'.format(path.name, path.stat().st_size))
print('Built Windows and Android Kodi repositories, CBR skin, setup wizard and platform-specific add-on packages.')
