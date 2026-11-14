"""CBR setup wizard: applies and restores the optional Kodi skin."""
import json
import os
import sys
import threading
import time

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
        raise RuntimeError('Kodi could not complete this setup step: ' + method)
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


def apply_skin(confirm=True):
    try:
        xbmcaddon.Addon(SKIN_ID)
    except Exception:
        DIALOG.ok(BRAND, 'The CBR skin is not installed yet. Install CBR Setup Wizard from the CBR repository, then try again.')
        return
    previous = current_skin()
    if previous != SKIN_ID:
        save_previous(previous)
    if not confirm or DIALOG.yesno(BRAND, 'Apply the Crimson Blood Requiem space interface?\n\n'
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


def full_install():
    if xbmc.Player().isPlaying():
        DIALOG.ok(BRAND, 'Stop the current video, then run Full install again.')
        return
    required = (ADDON_ID, SKIN_ID, 'pvr.iptvsimple')
    missing = []
    for identity in required:
        try:
            xbmcaddon.Addon(identity)
        except Exception:
            missing.append(identity)
    if missing:
        DIALOG.ok(BRAND, 'Install CBR Setup Wizard from the matching CBR repository so Kodi can install its dependencies. Missing: ' + ', '.join(missing))
        return
    addon = xbmcaddon.Addon(ADDON_ID)
    addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))
    sys.path.insert(0, addon_path)
    from cbr_full_setup import FullInstall
    task = FullInstall(addon_path, xbmcvfs.translatePath(addon.getAddonInfo('profile')),
                       xbmcvfs.translatePath('special://profile/addon_data/pvr.iptvsimple/'))
    result = {}

    def run():
        try:
            result['status'] = task.run()
        except Exception as error:
            result['error'] = error

    progress, monitor = xbmcgui.DialogProgress(), xbmc.Monitor()
    progress.create('CBR Full Install', 'Setting up your channels and programme guide…')
    task.heartbeat()
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    last_heartbeat = time.monotonic()
    try:
        while worker.is_alive():
            if progress.iscanceled() or monitor.abortRequested():
                task.cancel()
            if time.monotonic() - last_heartbeat > 5:
                task.heartbeat()
                last_heartbeat = time.monotonic()
            progress.update(task.progress, 'Stopping setup…' if task.tv.stop.is_set() else task.message)
            worker.join(0.2)
    finally:
        progress.close()
        task.store.write(task.flag, {})
    if monitor.abortRequested():
        return
    if result.get('error'):
        DIALOG.ok(BRAND, str(result['error']))
        return
    status = result['status']
    # Reload this client to pick up CBR's instance, preserving its other instances.
    rpc('Addons.SetAddonEnabled', {'addonid': 'pvr.iptvsimple', 'enabled': False})
    monitor.waitForAbort(0.5)
    rpc('Addons.SetAddonEnabled', {'addonid': 'pvr.iptvsimple', 'enabled': True})
    apply_skin(confirm=False)
    state = {'completed': time.time(), 'channels': status['channels'],
             'guide_channels': status.get('guide_channels', 0)}
    xbmcvfs.mkdirs(STATE_DIR)
    with xbmcvfs.File(os.path.join(STATE_DIR, 'full-install.json'), 'w') as output:
        output.write(json.dumps(state))
    message = '{} TV entries are ready; {} have programme guide data.\n\n'.format(state['channels'], state['guide_channels'])
    if status.get('failed'):
        message += 'Some sources could not refresh. Existing cached channels were kept.\n\n'
    if not state['guide_channels']:
        message += 'Programme information could not be downloaded. Run Full install again to retry the guide.\n\n'
    message += ('Movies and series use Torrentio. For sports, add your configured Sports Streams link through Source setup (phone / PC).\n\n'
                'Close and reopen Kodi once to finish loading all services, then use Movies, TV Series or TV → Channels / Guide.')
    DIALOG.ok('CBR Full Install complete', message)


def main():
    options = ['Full install / repair (TV guide and CBR interface)', 'Apply CBR space interface only',
               'Restore previous Kodi interface', 'Open Crimson Blood Requiem', 'Close']
    choice = DIALOG.select('CBR Setup Wizard', options)
    if choice == 0:
        try:
            full_install()
        except Exception as error:
            DIALOG.ok('CBR setup needs attention', str(error)[:500] + '\n\nRun Full install again after checking the required add-ons are enabled.')
    elif choice == 1:
        apply_skin()
    elif choice == 2:
        restore_skin()
    elif choice == 3:
        open_crb()


if __name__ == '__main__':
    main()
