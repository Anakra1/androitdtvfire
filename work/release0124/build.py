"""Build video-only setup updates without publishing or changing repository feeds."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast
import hashlib
import json
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ADDON = 'plugin.video.stremio.bridge'
OUT = ROOT / 'outputs/release0124-stage'
VERSION = '0.12.4'


def build():
    report = {}
    for platform, baseline in [('windows', '0.12.2'), ('android', '0.12.3')]:
        old = ROOT / platform / 'packages' / ADDON / (ADDON + '-' + baseline + '.zip')
        with ZipFile(old) as z:
            previous = {n: z.read(n) for n in z.namelist() if not n.endswith('/')}
        files = dict(previous)
        for path in (HERE / 'overlay').rglob('*'):
            if path.is_file():
                files[ADDON + '/' + path.relative_to(HERE / 'overlay').as_posix()] = path.read_bytes()
        meta = ET.fromstring(files[ADDON + '/addon.xml'])
        meta.set('version', VERSION)
        meta.find("extension[@point='xbmc.addon.metadata']/news").text = 'Source setup categories: Live TV, Movies, TV Series, Channel Listings, Programmes and Tools. Shared source settings and unsaved channel edits are preserved.'
        files[ADDON + '/addon.xml'] = ET.tostring(meta, encoding='utf-8', xml_declaration=True)
        component_path = ADDON + '/resources/defaults/release-components.json'
        components = json.loads(files[component_path])
        components[ADDON] = VERSION
        components['script.crb.wizard'] = '0.4.4'
        files[component_path] = json.dumps(components).encode()
        target = OUT / platform / (ADDON + '-' + VERSION + '.zip')
        target.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=7) as z:
            for name, raw in files.items():
                if name.endswith('.py'):
                    ast.parse(raw.decode('utf-8-sig'), feature_version=(3, 8))
                if name.endswith('.xml'):
                    ET.fromstring(raw)
                z.writestr(name, raw)
        changed = sorted(n.removeprefix(ADDON + '/') for n in files if files[n] != previous.get(n))
        assert set(changed) == {'addon.py', 'addon.xml', 'resources/defaults/release-components.json', 'resources/lib/setup_web.py',
                                'resources/setup/index.html', 'resources/setup/setup.js', 'resources/setup/style.css'}
        assert target.stat().st_size < 100 * 1024 * 1024
        report[platform] = {'baseline': baseline, 'version': VERSION, 'file': str(target),
                            'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'changed': changed}
        if platform == 'windows':
            stage = HERE / 'stage' / ADDON
            for name, raw in files.items():
                if name.endswith(('.py', '.json', '.html', '.css', '.js')):
                    path = stage / name.removeprefix(ADDON + '/')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
    (OUT / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Built Windows and Android 0.12.4 setup updates; only seven intended files changed.')


if __name__ == '__main__':
    build()
