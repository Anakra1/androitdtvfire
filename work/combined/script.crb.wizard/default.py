"""CBR setup wizard: applies and restores the optional Kodi skin."""
import json
import os

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


BRAND = 'Crimson Blood Requiem'
SKIN_ID = 'skin.crimsonbloodrequiem'
ADDON_ID = 'plugin.video.stremio.bridge'
STATE_DIR = xbmcvfs.translatePath('special://profile/addon_data/script.crb.wizard')
STATE_FILE = os.path.join(STATE_DIR, 'previous-skin.json')
DIALOG = xbmcgui.Dialog()


def rpc(method, params):
    result = json.loads(xbmc.executeJSONRPC(json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params,
    })))
    if result.get('error'):
        raise RuntimeError('Kodi could not change the interface setting.')
    return result.get('result')


def current_skin():
    result = rpc('Settings.GetSettingValue', {'setting': 'lookandfeel.skin'})
    return result.get('value', 'skin.estuary') if isinstance(result, dict) else 'skin.estuary'


def save_previous(skin_id):
    xbmcvfs.mkdirs(STATE_DIR)
    with xbmcvfs.File(STATE_FILE, 'w') as output:
        output.write(json.dumps({'skin': skin_id}))


def read_previous():
    if not xbmcvfs.exists(STATE_FILE):
        return 'skin.estuary'
    with xbmcvfs.File(STATE_FILE) as source:
        saved = json.loads(source.read())
    skin_id = saved.get('skin', 'skin.estuary')
    try:
        xbmcaddon.Addon(skin_id)
        return skin_id
    except Exception:
        return 'skin.estuary'


def set_skin(skin_id):
    changed = rpc('Settings.SetSettingValue', {'setting': 'lookandfeel.skin', 'value': skin_id})
    if changed is not True:
        raise RuntimeError('Kodi rejected the interface change. Open Interface settings and select the skin there.')
    xbmc.executebuiltin('ReloadSkin()')


def apply_skin():
    try:
        xbmcaddon.Addon(SKIN_ID)
    except Exception:
        DIALOG.ok(BRAND, 'The CBR skin is not installed yet. Install CBR Setup Wizard from the CBR repository, then try again.')
        return
    previous = current_skin()
    if previous != SKIN_ID:
        save_previous(previous)
    if DIALOG.yesno(BRAND, 'Apply the Crimson Blood Requiem space interface?\n\n'
                    'Your Kodi libraries, add-ons and provider settings stay in place. '
                    'You can restore the previous skin from this wizard.'):
        set_skin(SKIN_ID)
        DIALOG.notification(BRAND, 'CBR interface applied', xbmcgui.NOTIFICATION_INFO, 5000)


def restore_skin():
    target = read_previous()
    if target == SKIN_ID:
        target = 'skin.estuary'
    if DIALOG.yesno(BRAND, 'Restore the previous Kodi interface?\n\nThe CBR add-on and its settings will stay installed.'):
        set_skin(target)
        DIALOG.notification(BRAND, 'Previous interface restored', xbmcgui.NOTIFICATION_INFO, 5000)


def open_crb():
    xbmc.executebuiltin('ActivateWindow(Videos,plugin://{}/,return)'.format(ADDON_ID))


def main():
    options = ['Apply CBR space interface', 'Restore previous Kodi interface', 'Open Crimson Blood Requiem', 'Close']
    choice = DIALOG.select('CBR Setup Wizard', options)
    if choice == 0:
        apply_skin()
    elif choice == 1:
        restore_skin()
    elif choice == 2:
        open_crb()


if __name__ == '__main__':
    main()
