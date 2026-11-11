"""Prepare a torrent for Kodi's normal setResolvedUrl playback route."""
import os
import re
import time
from urllib.parse import urlencode

import xbmc
import xbmcgui
import xbmcvfs

from engine import (ANDROID_COMPANION_PACKAGE, ANDROID_COMPANION_PORT, Client,
                    prepare_torrent, read_json, write_json)


def launch_android_companion():
    if os.name == 'nt':
        return
    client = Client('http://127.0.0.1:{}'.format(ANDROID_COMPANION_PORT))
    if client.alive():
        return
    try:
        # This is called from Kodi's foreground playback selection, not its
        # background add-on service. Fire OS can reject background activity starts.
        xbmc.executebuiltin(
            'StartAndroidActivity({},android.intent.action.VIEW,,cbr://start)'.format(
                ANDROID_COMPANION_PACKAGE), True)
    except Exception as error:
        raise RuntimeError(
            'Fire TV could not open CBR Kodi Companion. Check that it is installed and enabled.') from error


def torrent_magnet(stream):
    torrent_hash = stream.get('infoHash', '')
    if not isinstance(torrent_hash, str) or not re.fullmatch(r'[a-fA-F0-9]{40}', torrent_hash):
        raise ValueError('This source does not contain a supported v1 torrent hash.')
    index = stream.get('fileIdx')
    if index is not None and (isinstance(index, bool) or not isinstance(index, int) or index < 0):
        raise ValueError('The provider returned an invalid torrent file index.')
    params = [('xt', 'urn:btih:' + torrent_hash)]
    for source in stream.get('sources') or []:
        if isinstance(source, str) and source.startswith('tracker:'):
            params.append(('tr', source[len('tracker:'):]))
    return 'magnet:?' + urlencode(params)


def prepare_item(addon, stream, meta):
    magnet = torrent_magnet(stream)
    root = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    monitor = xbmc.Monitor()
    dialog = xbmcgui.DialogProgress()
    dialog.create('Crimson Blood Requiem', 'Starting the built-in torrent player…')
    session_path = os.path.join(root, 'engine-session.json')
    client, torrent_hash = None, None
    try:
        launch_android_companion()
        stamp = time.time()
        write_json(os.path.join(root, 'engine-request.json'), {'time': stamp})
        deadline = time.monotonic() + 300
        while True:
            if dialog.iscanceled() or monitor.abortRequested():
                return None
            state = read_json(os.path.join(root, 'engine-endpoint.json'))
            if state.get('request', 0) >= stamp:
                if state.get('error'):
                    raise RuntimeError(state['error'])
                if state.get('endpoint'):
                    client = Client(state['endpoint'])
                    break
                if state.get('message'):
                    dialog.update(state.get('progress', 0), state['message'])
            if time.monotonic() > deadline:
                raise RuntimeError('The torrent player did not start in time. Check the device internet connection and try again.')
            monitor.waitForAbort(0.1)
        old_session = read_json(session_path)
        if old_session.get('hash'):
            try:
                client.remove(old_session['hash'])
            except Exception:
                pass  # A previous torrent may already have expired in the engine.
        write_json(session_path, {'hash': stream['infoHash'], 'time': stamp})

        def choose_file(files):
            choice = xbmcgui.Dialog().select('Choose the episode or video file', [f['path'] for f in files])
            return files[choice] if choice >= 0 else None

        path, torrent_hash = prepare_torrent(
            client, magnet, stream.get('fileIdx'),
            progress=lambda percent, message: dialog.update(percent, message),
            cancelled=lambda: dialog.iscanceled() or monitor.abortRequested(),
            filename=(stream.get('behaviorHints') or {}).get('filename'), file_selector=choose_file)
        write_json(session_path, {'hash': torrent_hash, 'time': stamp})
        li = xbmcgui.ListItem(label=meta.get('name', 'Video'), path=path)
        li.setProperty('IsPlayable', 'true')
        li.setArt({k: meta.get(v, '') for k, v in (
            ('poster', 'poster'), ('thumb', 'thumbnail'), ('fanart', 'background'))})
        return li
    except InterruptedError:
        write_json(session_path, {})
        return None
    except Exception as error:
        write_json(session_path, {})
        if client:
            try:
                client.remove(torrent_hash or stream['infoHash'])
            except Exception:
                pass
        message = str(error) if isinstance(error, RuntimeError) else 'Unable to start torrent playback. Try another source.'
        xbmcgui.Dialog().ok('Crimson Blood Requiem', message)
        return None
    finally:
        dialog.close()
