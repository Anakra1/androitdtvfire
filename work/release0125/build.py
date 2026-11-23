"""Add a visible Kodi Settings shortcut to the current setup; stage only, never publish."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast
import hashlib
import json
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ADDON = 'plugin.video.stremio.bridge'
VERSION = '0.12.5'
OUT = ROOT / 'outputs/release0125-stage'


def build():
    report = {}
    for platform in ('windows', 'android'):
        baseline = ROOT / platform / 'packages' / ADDON / (ADDON + '-0.12.4.zip')
        with ZipFile(baseline) as archive:
            assert archive.testzip() is None
            previous = {n: archive.read(n) for n in archive.namelist() if not n.endswith('/')}
        files = dict(previous)
        entry = ADDON + '/addon.py'
        code = files[entry].decode('utf-8-sig').replace('\r\n', '\n')
        anchors = [
            ("        xbmcplugin.setPluginCategory(HANDLE, 'CBR Setup')\n",
             "        xbmcplugin.setPluginCategory(HANDLE, 'CBR Setup')\n"
             "        item('Back to Kodi Settings', 'command_kodi_settings', artwork='settings')\n"),
            ("    if category == 'tools':\n",
             "    if category == 'tools':\n"
             "        item('Back to Kodi Settings', 'command_kodi_settings', artwork='settings')\n")
        ]
        for before, after in anchors:
            assert code.count(before) == 1, 'Setup changed: review the patch before rebuilding'
            code = code.replace(before, after, 1)
        assert "finish();xbmc.executebuiltin('ActivateWindow(Settings)')" in code
        files[entry] = code.encode('utf-8')
        meta = ET.fromstring(files[ADDON + '/addon.xml'])
        meta.set('version', VERSION)
        meta.find("extension[@point='xbmc.addon.metadata']/news").text = (
            'Back to Kodi Settings is now visible at the top of CBR Setup and Setup Tools. '
            'Opens Kodi settings without switching skins or changing sources.')
        files[ADDON + '/addon.xml'] = ET.tostring(meta, encoding='utf-8', xml_declaration=True)
        component_path = ADDON + '/resources/defaults/release-components.json'
        components = json.loads(files[component_path])
        components[ADDON] = VERSION
        files[component_path] = json.dumps(components).encode('utf-8')
        changed = sorted(n.removeprefix(ADDON + '/') for n in files if files[n] != previous.get(n))
        assert changed == ['addon.py', 'addon.xml', 'resources/defaults/release-components.json']
        target = OUT / platform / (ADDON + '-' + VERSION + '.zip')
        target.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=7) as archive:
            for name, content in files.items():
                if name.endswith('.py'):
                    ast.parse(content.decode('utf-8-sig'), feature_version=(3, 8))
                elif name.endswith('.xml'):
                    ET.fromstring(content)
                archive.writestr(name, content)
        with ZipFile(target) as archive:
            assert archive.testzip() is None
        assert target.stat().st_size < 100 * 1024 * 1024
        if platform == 'windows':
            for name, content in files.items():
                path = HERE / 'stage' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        report[platform] = {'version': VERSION, 'baseline': '0.12.4', 'changed': changed,
                            'zip': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    (OUT / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Staged Windows and Android 0.12.5. Only setup entry points and version metadata changed; nothing published.')


if __name__ == '__main__':
    build()
