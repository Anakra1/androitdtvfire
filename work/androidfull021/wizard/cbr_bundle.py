"""Install the Android wizard's bundled add-ons without repository lookup."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile


def version(value):
    return tuple(int(x) for x in value.split('+', 1)[0].split('.'))


def selected_components(bundle, cpu, kodi_major):
    with open(Path(bundle)/'packages.json', encoding='utf8') as source:
        manifest = json.load(source)
    return [item for item in manifest['packages']
            if (not item.get('cpu') or item['cpu'] == cpu)
            and (not item.get('kodi_major') or item['kodi_major'] == kodi_major)]


def install(bundle, home, cpu, kodi_major, installed, cancelled, progress):
    """Write only named add-on code folders. Kodi profile data is untouched.

    Each ZIP is verified before any writes. Files are replaced atomically and
    addon.xml is installed last, so a cancelled fresh install is not registered.
    Kodi's UpdateLocalAddons / enable APIs perform registration afterwards.
    """
    home = Path(home).resolve()
    home.mkdir(parents=True, exist_ok=True)
    items = selected_components(bundle, cpu, kodi_major)
    pending = []
    for item in items:
        current = installed(item['id'])
        if current and version(current) >= version(item['version']):
            continue
        path = Path(bundle)/item['file']
        if path.parent.resolve() != Path(bundle).resolve():
            raise RuntimeError('Invalid bundled package location.')
        digest = hashlib.sha256()
        with open(path, 'rb') as source:
            for chunk in iter(lambda: source.read(1024*1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != item['sha256']:
            raise RuntimeError('A bundled package is damaged. Install the new fulla.zip again.')
        with ZipFile(path) as archive:
            info = ET.fromstring(archive.read(item['id']+'/addon.xml'))
            if info.get('id') != item['id'] or info.get('version') != item['version']:
                raise RuntimeError('Bundled add-on metadata does not match.')
            size = 0
            for member in archive.infolist():
                parts = PurePosixPath(member.filename).parts
                if (not parts or parts[0] != item['id'] or '..' in parts or
                        '\\' in member.filename or ':' in member.filename or
                        (member.external_attr >> 16) & 0o170000 == 0o120000):
                    raise RuntimeError('Unsafe path in bundled add-on.')
                size += member.file_size
            if size > 512*1024*1024:
                raise RuntimeError('Bundled package exceeds the install limit.')
        pending.append((item, path, size))
    for index, (item, path, size) in enumerate(pending):
        if cancelled():
            raise InterruptedError('Installation cancelled. Run Full install again to finish.')
        if shutil.disk_usage(home).free < size + 16*1024*1024:
            raise RuntimeError('Not enough free device storage for '+item['label']+'. Free some space and run Full install again.')
        progress(int(100*index/max(1,len(pending))), 'Installing included '+item['label']+'…')
        with ZipFile(path) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            members.sort(key=lambda m: m.filename == item['id']+'/addon.xml')
            for member in members:
                if cancelled():
                    raise InterruptedError('Installation cancelled. Run Full install again to finish.')
                target = home.joinpath(*PurePosixPath(member.filename).parts)
                if home not in target.resolve().parents:
                    raise RuntimeError('Add-on destination is outside Kodi add-ons.')
                target.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary = tempfile.mkstemp(dir=str(target.parent), prefix='.cbr-')
                try:
                    with os.fdopen(descriptor, 'wb') as output, archive.open(member) as source:
                        shutil.copyfileobj(source, output, 1024*1024)
                    os.replace(temporary, target)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
    progress(100, 'Included components installed. Registering them with Kodi…')
    return items
