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
from resources.lib.defaults import ensure_defaults
from resources.lib.live import LiveLibrary
from resources.lib.live_player import LiveAutoplay
from resources.lib.playback_memory import queue_retry, poll_retry
from resources.lib.programmes import ProgrammeGuide, ProgrammeUpdater, ProgrammePlaybackInfo, programme_text
from resources.lib.pvr import PVRUpdater
from resources.lib.startup_updates import StartupUpdates
from resources.lib.maintenance import runtime_snapshot, request_repair


from resources.lib.command_service import CommandTracker

class PlaybackPlayer(xbmc.Player):
    def __init__(self, autoplay):
        super().__init__()
        self.autoplay = autoplay
        self.command = CommandTracker(autoplay.store)

    def onAVStarted(self):
        try:self.command.started(self)
        except Exception:pass
        self.autoplay.signal('started')
        try: self.autoplay.memory.confirm(self.getPlayingFile(),xbmc.getInfoLabel('VideoPlayer.ChannelName'))
        except Exception: pass
        try:
            from resources.lib.maintenance import record_playback
            pending = read_json(os.path.join(self.autoplay.store.root, 'live-confirmation.json'))
            if pending.get('name') and 0 <= time.time() - pending.get('time', 0) < 120 and xbmc.getInfoLabel('VideoPlayer.ChannelName') == pending['name']:
                record_playback(self.autoplay.store, pending['channel'])
                write_json(os.path.join(self.autoplay.store.root, 'live-confirmation.json'), {})
        except Exception:
            pass

    def onPlayBackError(self):
        try:self.command.event('error')
        except Exception:pass
        self.autoplay.signal('error')
        try: queue_retry(self.autoplay.store,self.autoplay.memory.failed())
        except Exception: pass
        try:
            self.autoplay.store.write(os.path.join(self.autoplay.store.root, 'recent-errors.json'),
                [dict(time=time.time(), action='playback', summary='Kodi could not play this source. Try another stream or check the source status.')])
        except Exception:
            pass

    def onPlayBackEnded(self):
        try:self.command.event('ended')
        except Exception:pass
        self.autoplay.signal('ended')
        try: queue_retry(self.autoplay.store,self.autoplay.memory.failed())
        except Exception: pass

    def onPlayBackStopped(self):
        try:self.command.event('stopped')
        except Exception:pass
        self.autoplay.signal('stopped')
        self.autoplay.memory.clear()
        self.autoplay.store.write(os.path.join(self.autoplay.store.root,'pvr-retry.json'),{})
        try: write_json(os.path.join(self.autoplay.store.root, 'live-confirmation.json'), {})
        except Exception: pass


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
    ensure_defaults(Store(root), addon.getAddonInfo('path'))
    def maintenance_rpc(method, params):
        import json
        value = json.loads(xbmc.executeJSONRPC(json.dumps(dict(jsonrpc='2.0', id=1, method=method, params=params))))
        if value.get('error'): raise RuntimeError('Kodi status unavailable')
        return value['result']
    def save_runtime():
        value = runtime_snapshot(maintenance_rpc, xbmcvfs.translatePath('special://database/'),
                                 'android' if xbmc.getCondVisibility('System.Platform.Android') else 'windows')
        Store(root).write(os.path.join(root, 'maintenance-runtime.json'), value)
    save_runtime()
    last_maintenance = read_json(os.path.join(root, 'maintenance-result.json')).get('requested', 0)
    last_runtime = time.monotonic()
    maintenance_reload = False
    last_confirmed_playback = None
    endpoint_path = os.path.join(root, 'engine-endpoint.json')
    request_path = os.path.join(root, 'engine-request.json')
    session_path = os.path.join(root, 'engine-session.json')
    autoplay = LiveAutoplay(Store(root))
    autoplay.clear()
    monitor, player = xbmc.Monitor(), PlaybackPlayer(autoplay)
    startup_updates = StartupUpdates(Store(root), addon, xbmc.executebuiltin,
                                     lambda: xbmc.getIPAddress() not in ('', '0.0.0.0', '127.0.0.1', '::1'))
    setup = SetupController(root, addon.getAddonInfo('path'), xbmc.getIPAddress)
    live_library = LiveLibrary(Store(root))
    programmes = ProgrammeUpdater(Store(root))
    pvr = PVRUpdater(Store(root))
    programme_info = ProgrammePlaybackInfo(Store(root))
    live_library.store.write(live_library.path('playing'), {})
    engine, last_request, touched, current_hash, started = None, 0, 0, '', False
    write_json(endpoint_path, {})
    try:
        while not monitor.abortRequested():
            setup.poll()
            player.command.poll(player)
            if time.monotonic() - last_runtime > 60:
                try: save_runtime()
                except Exception: pass
                last_runtime = time.monotonic()
            maintenance = read_json(os.path.join(root, 'maintenance-request.json')).get('time', 0)
            if maintenance > last_maintenance and not player.isPlaying() and time.time() - read_json(os.path.join(root, 'full-setup-active.json')).get('time', 0) > 45:
                last_maintenance = maintenance
                try:
                    ensure_defaults(Store(root), addon.getAddonInfo('path'))
                    save_runtime()
                    from resources.lib import pvr as pvr_module, programmes as programme_module
                    repo = 'repository.crb.android' if xbmc.getCondVisibility('System.Platform.Android') else 'repository.crb.windows'
                    try: maintenance_rpc('Addons.SetAddonEnabled', {'addonid':repo, 'enabled':True})
                    except Exception: pass
                    programme_module.request_refresh(Store(root))
                    pvr_module.refresh(Store(root))
                    maintenance_reload = True
                    Store(root).write(os.path.join(root, 'maintenance-result.json'), {'state':'queued', 'requested':maintenance, 'time':time.time()})
                except Exception:
                    Store(root).write(os.path.join(root, 'maintenance-result.json'), {'state':'error', 'requested':maintenance, 'time':time.time()})
            # The full-install wizard owns schedule/channel writes while its
            # heartbeat is fresh. Resume normal updates if it exits or crashes.
            installing = read_json(os.path.join(root, 'full-setup-active.json')).get('time', 0)
            try:
                startup_updates.poll(player, installing=time.time() - installing <= 45)
            except Exception:
                startup_updates.done = True
                xbmc.log('CBR startup repository check could not run; normal Kodi updates remain available.', xbmc.LOGWARNING)
            if time.time() - installing > 45:
                programmes.poll()
                pvr.poll()
                status = read_json(os.path.join(root, 'pvr-status.json'))
                if maintenance_reload and status.get('state') == 'ready' and status.get('exported', 0) >= last_maintenance and not player.isPlaying() and not (pvr.thread and pvr.thread.is_alive()) and not (programmes.thread and programmes.thread.is_alive()):
                    try:
                        from resources.lib import pvr as pvr_module
                        maintenance_rpc('Addons.GetAddonDetails', {'addonid':'pvr.iptvsimple', 'properties':['enabled']})
                        maintenance_rpc('Addons.SetAddonEnabled', {'addonid':'pvr.iptvsimple','enabled':False})
                        monitor.waitForAbort(0.5)
                        try:
                            pvr_module.configure_instance(xbmcvfs.translatePath('special://profile/addon_data/pvr.iptvsimple/'),
                                'special://profile/addon_data/plugin.video.stremio.bridge/pvr/channels.m3u',
                                'special://profile/addon_data/plugin.video.stremio.bridge/pvr/guide.xml', refresh_guide=True)
                        finally:
                            maintenance_rpc('Addons.SetAddonEnabled', {'addonid':'pvr.iptvsimple','enabled':True})
                        Store(root).write(os.path.join(root, 'maintenance-result.json'), {'state':'ready', 'requested':last_maintenance, 'time':time.time()})
                    except Exception:
                        Store(root).write(os.path.join(root, 'maintenance-result.json'), {'state':'needs_tv_setup', 'requested':last_maintenance, 'time':time.time()})
                    maintenance_reload = False
            autoplay.poll(player, live_item, lambda message: xbmcgui.Dialog().notification(
                'Crimson Blood Requiem', message, xbmcgui.NOTIFICATION_INFO, 4000))
            poll_retry(Store(root),player,maintenance_rpc)
            live_library.poll(player)
            observed = read_json(live_library.path('playing'))
            if observed.get('fingerprint') and observed['fingerprint'] != last_confirmed_playback:
                from resources.lib.maintenance import record_playback
                try: record_playback(Store(root), observed['channel'])
                except Exception: pass
                last_confirmed_playback = observed['fingerprint']
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
        player.command.close()
        programmes.close()
        pvr.close()
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
