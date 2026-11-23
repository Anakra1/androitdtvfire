"""Kodi controls for an optional Real-Debrid account. No passwords or embedded account keys."""
import xbmc
import xbmcgui
from .real_debrid import Client


def available(addon, store):
    return addon.getSetting('rd_enabled') == 'true' and Client(store.root).connected()


def connect(addon, store):
    client = Client(store.root)
    dialog = xbmcgui.DialogProgress()
    monitor = xbmc.Monitor()
    try:
        device = client.begin()
        message = 'On your phone or PC open:\n{}\nEnter code: {}\nApprove the connection there. Cancel stops sign-in.'.format(
            device['verification_url'], device['user_code'])
        dialog.create('Connect Real-Debrid (optional)', message)
        cancelled = lambda: dialog.iscanceled() or monitor.abortRequested()
        account = client.complete(device, cancelled=cancelled, wait=lambda seconds: monitor.waitForAbort(seconds))
        addon.setSetting('rd_enabled', 'true')
        dialog.close()
        xbmcgui.Dialog().ok('Real-Debrid connected', 'Account: {}\nType: {}\nExpires: {}\nYou can disable or disconnect it from CBR Setup.'.format(
            account.get('username',''), account.get('type',''), account.get('expiration','Unknown')))
    except InterruptedError:
        pass
    except (RuntimeError, ValueError, OSError):
        xbmcgui.Dialog().ok('Real-Debrid sign-in', 'Sign-in could not finish. Check your internet connection, approve the device code, and try Connect again. Existing credentials are kept until a new connection succeeds.')
    finally:
        dialog.close()


def action(addon, store, operation):
    client = Client(store.root)
    dialog = xbmcgui.Dialog()
    if operation == 'connect':
        connect(addon, store)
    elif operation == 'account':
        try:
            account = client.account()
            dialog.ok('Real-Debrid account', 'Account: {}\nType: {}\nExpires: {}\nCBR use: {}'.format(
                account.get('username',''), account.get('type',''), account.get('expiration','Unknown'),
                'Enabled' if addon.getSetting('rd_enabled') == 'true' else 'Disabled'))
        except RuntimeError as error:
            dialog.ok('Real-Debrid account', str(error))
    elif operation == 'disconnect':
        if dialog.yesno('Disconnect Real-Debrid?', 'Remove this device\'s saved Real-Debrid connection? CBR\'s built-in player and other sources remain available.'):
            client.disconnect()
            addon.setSetting('rd_enabled', 'false')
            dialog.ok('Real-Debrid', 'Local connection removed. For full authorisation revocation, also remove this app on the Real-Debrid website.')
    elif operation == 'toggle':
        if addon.getSetting('rd_enabled') == 'true':
            addon.setSetting('rd_enabled', 'false')
        elif client.connected():
            addon.setSetting('rd_enabled', 'true')
        else:
            dialog.ok('Real-Debrid', 'Choose Connect Real-Debrid first. You can keep using CBR without it.')
    elif operation == 'preference':
        values = ['Built-in torrent player', 'Ask each time', 'Prefer Real-Debrid']
        current = addon.getSetting('rd_playback') or 'Built-in torrent player'
        selected = dialog.select('Movie / series torrent player', values, preselect=values.index(current) if current in values else 0)
        if selected >= 0:
            addon.setSetting('rd_playback', values[selected])


def prepare_item(addon, store, stream, meta):
    """(handled, ListItem): cancel/failure never silently changes playback transport."""
    preference = addon.getSetting('rd_playback') or 'Built-in torrent player'
    if preference == 'Built-in torrent player':
        return False, None
    if not available(addon, store):
        return False, None
    dialog = xbmcgui.Dialog()
    if preference == 'Ask each time':
        selected = dialog.select('Play this source using', ['Real-Debrid', 'Built-in torrent player'])
        if selected < 0:
            return True, None
        if selected == 1:
            return False, None
    progress = xbmcgui.DialogProgress()
    monitor = xbmc.Monitor()
    progress.create('Real-Debrid', 'Preparing the selected file. Cancel stops waiting; the transfer may remain in your account.')
    try:
        def choose(files):
            selected = dialog.select('Choose the episode or video file', [f['path'] for f in files])
            return files[selected] if selected >= 0 else None
        path = Client(store.root).resolve(stream, choose=choose,
            cancelled=lambda: progress.iscanceled() or monitor.abortRequested(),
            progress=lambda percent, text: progress.update(percent, text),
            wait=lambda seconds: monitor.waitForAbort(seconds))
        li = xbmcgui.ListItem(label=meta.get('name','Video'), path=path)
        li.setProperty('IsPlayable', 'true')
        return True, li
    except InterruptedError:
        return True, None
    except (RuntimeError, ValueError) as error:
        progress.close()
        if dialog.yesno('Real-Debrid could not play this source', str(error) + '\n\nTry the built-in torrent player instead?'):
            return False, None
        return True, None
    except Exception:
        dialog.ok('Real-Debrid', 'Unable to prepare this file. Try another source or reconnect in CBR Setup.')
        return True, None
    finally:
        progress.close()
