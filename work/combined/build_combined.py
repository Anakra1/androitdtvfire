from pathlib import Path
import hashlib
import json
import py_compile
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

here = Path(__file__).resolve().parent
source = here / 'plugin.video.stremio.bridge'
outputs = here.parent.parent / 'outputs' if here.parent.name == 'work' else here / 'outputs'
outputs.mkdir(exist_ok=True)
readme = outputs / 'Crimson-Blood-Requiem-README.md' if here.parent.name == 'work' else here / 'README.md'
version = ET.parse(source / 'addon.xml').getroot().attrib['version']
assert version == '0.9.4'
assert 'plugin.video.stremio.bridge' in (source / 'service.py').read_text(encoding='utf-8-sig')
for path in source.rglob('*.py'):
    py_compile.compile(str(path), doraise=True)
ET.parse(source / 'resources/settings.xml')
for path in (source / 'resources/defaults').glob('*.json'):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if path.name == 'live-providers.json':
        assert isinstance(data, list) and len(data) == 3
    elif path.name == 'm3u-countries.json':
        assert data.get('GB') == 'United Kingdom'
    else:
        assert all(key in data for key in ('id', 'name', 'version'))
binary = source / 'resources/bin/windows-x64/TorrServer.exe'
assert hashlib.sha256(binary.read_bytes()).hexdigest() == '3a96b97a24d86a90c0712a6ec47d4ed52edc7eabac1bce6a0d9bbc8fd30de5bb'
readme.write_text((source / 'README.md').read_text(encoding='utf-8-sig'), encoding='utf-8')
files = [path for path in source.rglob('*') if path.is_file() and '__pycache__' not in path.parts]
installer = outputs / ('plugin.video.stremio.bridge-' + version + '.zip')
with ZipFile(installer, 'w', ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, path.relative_to(here).as_posix())
bundle = outputs / 'Crimson-Blood-Requiem-source.zip'
with ZipFile(bundle, 'w', ZIP_DEFLATED) as archive:
    for path in files:
        name = path.relative_to(here).as_posix()
        if path.name == 'live-providers.json':
            # Never copy device-specific or account-token URLs into the source archive.
            defaults = json.loads(path.read_text(encoding='utf-8-sig'))
            for provider in defaults:
                public_url = provider.pop('public_fallback_url', None)
                if not public_url:
                    raise ValueError('Add a public_fallback_url before packaging {}'.format(provider.get('label', 'provider')))
                provider['url'] = public_url
            archive.writestr(name, json.dumps(defaults, indent=2))
        else:
            archive.write(path, name)
    for path in here.glob('test_*.py'):
        archive.write(path, path.name)
    for path in (here / 'tests').rglob('*'):
        if path.is_file():
            archive.write(path, path.relative_to(here).as_posix())
    archive.write(here / 'build_combined.py', 'build_combined.py')
    archive.write(here / 'build_crb_setup.py', 'build_crb_setup.py')
    archive.write(here / 'publish_packages.py', 'publish_packages.py')
    archive.write(here / 'build_native_engine.ps1', 'build_native_engine.ps1')
    for path in (here / 'script.module.cbr.engine').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and not ('resources' in path.parts and 'lib' in path.parts):
            archive.write(path, path.relative_to(here).as_posix())
    upstream = here.parent.parent / 'source/TorrServer-MatriX.150-source.zip'
    if upstream.is_file():
        archive.write(upstream, 'source/TorrServer-MatriX.150-source.zip')
    archive.write(readme, 'README.md')
for path in (installer, bundle):
    with ZipFile(path) as archive:
        assert archive.testzip() is None
    print('{}: {} bytes'.format(path.name, path.stat().st_size))
print('Verified Python, XML, public default manifests, engine checksum and ZIP integrity.')
