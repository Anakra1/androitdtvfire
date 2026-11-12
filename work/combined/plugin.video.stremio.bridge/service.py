"""Own the child engine for Kodi's lifetime; stop downloads after playback."""
import os
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from engine import Engine, read_json, write_json
from resources.lib.setup_web import SetupController
from resources.lib.core import Store
from resources.lib.live import LiveLibrary
from resources.lib.live_player import LiveAutoplay
from resources.lib.programmes import ProgrammeGuide, ProgrammeUpdater, ProgrammePlaybackInfo, programme_text


class PlaybackPlayer(xbmc.Player):
    def __init__(self, autoplay):
        super().__init__()
        self.autoplay = autoplay

    def onAVStarted(self):
        self.autoplay.signal('started')

    def onPlayBackError(self):
        self.autoplay.signal('error')

    def onPlayBackEnded(self):
        self.autoplay.signal('ended')

    def onPlayBackStopped(self):
        self.autoplay.signal('stopped')


def live_item(path, title, channel):
    meta = channel['meta']
    item = xbmcgui.ListItem(path=path)
    item.getVideoInfoTag().setTitle(title)
    item.setArt({'thumb': meta.get('logo') or meta.get('poster', '')})
    profile = xbmcvfs.translatePath(xbmcaddon.Addon('plugin.video.stremio.bridge').getAddonInfo('profile'))
    guide = ProgrammeGuide(Store(profile))
    try:
        item.getVideoInfoTag().setPlot(programme_text(guide.lookup(channel))
                                       if guide.config.get('enabled', True) else meta.get('description', ''))
    finally:
        guide.close()
    return item


def main():
    addon = xbmcaddon.Addon('plugin.video.stremio.bridge')
    root = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    os.makedirs(root, exist_ok=True)
    endpoint_path = os.path.join(root, 'engine-endpoint.json')
    request_path = os.path.join(root, 'engine-request.json')
    session_path = os.path.join(root, 'engine-session.json')
    autoplay = LiveAutoplay(Store(root))
    autoplay.clear()
    monitor, player = xbmc.Monitor(), PlaybackPlayer(autoplay)
    setup = SetupController(root, addon.getAddonInfo('path'), xbmc.getIPAddress)
    live_library = LiveLibrary(Store(root))
    programmes = ProgrammeUpdater(Store(root))
    programme_info = ProgrammePlaybackInfo(Store(root))
    live_library.store.write(live_library.path('playing'), {})
    engine, last_request, touched, current_hash, started = None, 0, 0, '', False
    write_json(endpoint_path, {})
    try:
        while not monitor.abortRequested():
            setup.poll()
            programmes.poll()
            autoplay.poll(player, live_item, lambda message: xbmcgui.Dialog().notification(
                'Crimson Blood Requiem', message, xbmcgui.NOTIFICATION_INFO, 4000))
            live_library.poll(player)
            programme_info.poll(player, live_item)
            request = read_json(request_path).get('time', 0)
            if request > last_request:
                last_request, touched, started = request, time.monotonic(), False
                if engine is None:
                    try:
                        engine = Engine(addon.getAddonInfo('path'), os.path.join(root, 'engine-data'),
                                        addon.getSetting('cache_mb') or '128')
                        client = engine.start(progress=lambda percent, message: write_json(
                            endpoint_path, {'request': request, 'progress': percent, 'message': message}))
                        write_json(endpoint_path, {'endpoint': client.endpoint, 'request': request})
                    except Exception as error:
                        if engine:
                            engine.stop()
                        engine = None
                        write_json(endpoint_path, {'error': str(error), 'request': request})
                if engine is not None:
                    # Acknowledge every request, including subsequent videos using
                    # the same child process; otherwise the next caller times out.
                    write_json(endpoint_path, {'endpoint': engine.client.endpoint, 'request': request})
            if engine:
                session = read_json(session_path)
                new_hash = session.get('hash', '')
                if new_hash != current_hash:
                    current_hash, started, touched = new_hash, False, time.monotonic()
                try:
                    own_playback = player.isPlaying() and player.getPlayingFile().startswith(engine.client.endpoint + '/')
                except Exception:
                    own_playback = False
                if own_playback:
                    started, touched = True, time.monotonic()
                elif current_hash and (started or time.monotonic() - touched > 180):
                    try:
                        engine.client.remove(current_hash)
                    except Exception:
                        pass
                    write_json(session_path, {})
                    current_hash, started = '', False
                if not current_hash and time.monotonic() - touched > 180:
                    engine.stop()
                    engine = None
                    write_json(endpoint_path, {})
            monitor.waitForAbort(0.5)
    finally:
        programmes.close()
        autoplay.clear()
        setup.close()
        if engine:
            engine.stop()
        if os.name != 'nt':
            try:
                from cbrengine import shutdown
                shutdown()
            except Exception as error:
                xbmc.log('CBR playback shutdown: {}'.format(error), xbmc.LOGWARNING)
        write_json(endpoint_path, {})
        write_json(session_path, {})


if __name__ == '__main__':
    main()

