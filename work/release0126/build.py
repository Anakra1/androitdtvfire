"""Build optional Real-Debrid support on 0.12.5; stage only, no publication."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast
import hashlib
import json
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ADDON = 'plugin.video.stremio.bridge'
VERSION = '0.12.6'
OUT = ROOT / 'outputs/release0126-stage'


def replace(text, before, after):
    assert text.count(before) == 1, 'Upstream code changed; review the Real-Debrid integration'
    return text.replace(before, after, 1)


def build():
    report = {}
    for platform in ('windows','android'):
        baseline = ROOT / 'outputs/release0125-stage' / platform / (ADDON + '-0.12.5.zip')
        with ZipFile(baseline) as archive:
            previous = {n:archive.read(n) for n in archive.namelist() if not n.endswith('/')}
        files = dict(previous)
        for path in (HERE / 'overlay').rglob('*'):
            if path.is_file():
                files[ADDON + '/' + path.relative_to(HERE / 'overlay').as_posix()] = path.read_bytes()
        entry = ADDON + '/addon.py'
        code = files[entry].decode('utf-8-sig').replace('\r\n','\n')
        code = replace(code, "        item('Setup status', 'command_setup_status', artwork='settings')", "        item('Real-Debrid (optional)', 'rd_menu', artwork='settings')\n        item('Setup status', 'command_setup_status', artwork='settings')")
        code = replace(code, "        item('Player settings', 'configure', artwork='settings')", "        item('Real-Debrid (optional)', 'rd_menu', artwork='settings')\n        item('Player settings', 'configure', artwork='settings')")
        code = replace(code, 'def render_stream_links(media_type,item_id,meta,streams,channel=None):\n', "def render_stream_links(media_type,item_id,meta,streams,channel=None):\n    from resources.lib.real_debrid_ui import available as rd_available\n    rd_ready = (ADDON.getSetting('rd_playback') or 'Built-in torrent player') != 'Built-in torrent player' and rd_available(ADDON, STORE)\n")
        code = replace(code, "            label = '[Built-in torrent player] ' + label", "            label = ('[Real-Debrid / built-in player] ' if rd_ready and media_type in ('movie','series') else '[Built-in torrent player] ') + label")
        before = "    if kind == 'torrent':\n        from torrent_player import prepare_item\n        li = prepare_item(ADDON, stream, saved['meta'])"
        after = "    if kind == 'torrent':\n        from resources.lib.real_debrid_ui import prepare_item as rd_prepare\n        handled, li = rd_prepare(ADDON, STORE, stream, saved['meta']) if saved.get('type') in ('movie','series') else (False, None)\n        if not handled:\n            from torrent_player import prepare_item\n            li = prepare_item(ADDON, stream, saved['meta'])"
        code = replace(code, before, after)
        code = replace(code, "    elif action=='command_setup':command_setup()", "    elif action=='rd_menu':rd_menu()\n    elif action=='rd_action':\n        from resources.lib.real_debrid_ui import action as rd_action\n        rd_action(ADDON, STORE, params.get('operation', ''))\n        if HANDLE >= 0:rd_menu()\n    elif action=='command_setup':command_setup()")
        menu = '''def rd_menu():
    from resources.lib.real_debrid import Client
    state = Client(STORE.root).summary()
    xbmcplugin.setPluginCategory(HANDLE, 'CBR Setup - Real-Debrid (optional)')
    item('Back to Kodi Settings', 'command_kodi_settings', artwork='settings')
    status = 'Connected' if state['connected'] else 'Not connected'
    status += ' / Enabled' if ADDON.getSetting('rd_enabled') == 'true' else ' / Disabled'
    item('Status: ' + status, 'rd_action', operation='account', artwork='settings')
    item('Connect / reauthorise Real-Debrid', 'rd_action', operation='connect', artwork='settings')
    item('Enable / disable Real-Debrid in CBR', 'rd_action', operation='toggle', artwork='settings')
    item('Playback choice: ' + (ADDON.getSetting('rd_playback') or 'Built-in torrent player'), 'rd_action', operation='preference', artwork='settings')
    item('Check account / subscription', 'rd_action', operation='account', artwork='settings')
    item('Disconnect Real-Debrid', 'rd_action', operation='disconnect', artwork='settings')
    finish()


'''
        code = replace(code, 'def command_setup():', menu + 'def command_setup():')
        files[entry] = code.encode('utf-8')
        settings_path = ADDON + '/resources/settings.xml'
        settings = ET.fromstring(files[settings_path])
        category = ET.SubElement(settings, 'category', label='Real-Debrid (optional)')
        ET.SubElement(category, 'setting', id='rd_enabled', type='bool', label='Enable optional Real-Debrid playback', default='false')
        ET.SubElement(category, 'setting', id='rd_playback', type='select', label='Movie / series torrent player', values='Ask each time|Prefer Real-Debrid|Built-in torrent player', default='Built-in torrent player')
        ET.SubElement(category, 'setting', id='rd_connect', type='action', label='Connect / reauthorise Real-Debrid', action='RunPlugin(plugin://plugin.video.stremio.bridge/?action=rd_action&operation=connect)')
        ET.SubElement(category, 'setting', id='rd_account', type='action', label='Check account / subscription', action='RunPlugin(plugin://plugin.video.stremio.bridge/?action=rd_action&operation=account)')
        ET.SubElement(category, 'setting', id='rd_disconnect', type='action', label='Disconnect Real-Debrid', action='RunPlugin(plugin://plugin.video.stremio.bridge/?action=rd_action&operation=disconnect)')
        files[settings_path] = ET.tostring(settings, encoding='utf-8', xml_declaration=True)
        meta = ET.fromstring(files[ADDON + '/addon.xml'])
        meta.set('version', VERSION)
        meta.find("extension[@point='xbmc.addon.metadata']/news").text = 'Optional Real-Debrid device-code sign-in, account status, disconnect and explicit movie/series torrent playback choice. Disabled by default. Includes Back to Kodi Settings.'
        files[ADDON + '/addon.xml'] = ET.tostring(meta, encoding='utf-8', xml_declaration=True)
        component = ADDON + '/resources/defaults/release-components.json'
        versions = json.loads(files[component]); versions[ADDON] = VERSION
        files[component] = json.dumps(versions).encode('utf-8')
        changed = sorted(n.removeprefix(ADDON + '/') for n in files if files[n] != previous.get(n))
        assert changed == ['addon.py','addon.xml','resources/defaults/release-components.json',
                           'resources/lib/real_debrid.py','resources/lib/real_debrid_ui.py','resources/settings.xml'], changed
        target = OUT / platform / (ADDON + '-' + VERSION + '.zip')
        target.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=7) as archive:
            for name, raw in files.items():
                if name.endswith('.py'):ast.parse(raw.decode('utf-8-sig'), feature_version=(3,8))
                elif name.endswith('.xml'):ET.fromstring(raw)
                archive.writestr(name, raw)
        with ZipFile(target) as archive:assert archive.testzip() is None
        if platform == 'windows':
            for name, raw in files.items():
                path = HERE / 'stage' / name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
        report[platform] = dict(version=VERSION, changed=changed, zip=str(target), sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (OUT / 'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Windows and Android 0.12.6 staged; six intended files changed. Nothing published.')


if __name__ == '__main__':build()
