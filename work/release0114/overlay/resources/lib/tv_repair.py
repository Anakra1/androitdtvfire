"""Prepare CBR's own profile and IPTV instance; keep unrelated Kodi data."""
import os
import time

from .core import Store
from .defaults import ensure_defaults
from . import pvr, programmes


class RepairTask:
    def __init__(self, addon_path, profile, iptv_profile):
        self.addon_path = addon_path
        self.store = Store(profile)
        self.iptv_profile = iptv_profile
        self.guide = programmes.ProgrammeUpdater(self.store)
        self.tv = pvr.PVRUpdater(self.store)
        self.flag = os.path.join(profile, 'full-setup-active.json')
        self.message, self.progress = 'Preparing CBR setup…', 0
        self.started = time.monotonic()
        self.report_path = os.path.join(profile, 'tv-repair-result.json')

    def guide_progress(self, done, total, label):
        self.progress = 15 + int(35 * done / max(1,total))
        self.message = 'Programme guide {}/{}: {}'.format(done+1,total,label)

    def channel_progress(self, done, total, label):
        self.progress = 55 + int(30 * done / max(1,total))
        self.message = 'Channel source {}/{}: {}'.format(done+1,total,label)

    def elapsed_message(self):
        elapsed = int(time.monotonic()-self.started)
        message = 'Stopping after the current network request…' if self.tv.stop.is_set() else self.message
        return '{}  |  {}m {:02d}s elapsed'.format(message,elapsed//60,elapsed%60)

    def heartbeat(self):
        self.store.write(self.flag, {'time': time.time()})

    def cancel(self):
        self.guide.stop.set()
        self.tv.stop.set()

    def check_cancelled(self):
        if self.tv.stop.is_set():
            raise InterruptedError('Setup cancelled. You can run Full install again.')

    def run(self):
        owns_updates = False
        self.store.write(self.report_path, dict(state='running',started=time.time()))
        try:
            self.heartbeat()
            # Let any update already started by the service finish before taking
            # ownership. Its next poll sees our heartbeat and pauses.
            deadline = time.monotonic() + 120
            while True:
                self.check_cancelled()
                guide = self.store.read(os.path.join(self.store.root, 'programme-status.json'), {})
                tv = self.store.read(os.path.join(self.store.root, 'pvr-status.json'), {})
                now = time.time()
                busy = tv.get('state') == 'updating' and now - tv.get('attempted', 0) < 120
                busy = busy or any(s.get('state') == 'updating' and now - s.get('attempted', 0) < 120 for s in guide.values())
                if not busy:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError('An existing TV update is still running. Restart Kodi, then run Full install again.')
                self.message = 'Waiting for the current TV update to finish…'
                time.sleep(0.25)
            owns_updates = True
            ensure_defaults(self.store, self.addon_path)
            self.message, self.progress = 'Downloading the programme guide…', 15
            config = programmes.settings(self.store)
            if config.get('enabled', True):
                self.guide.refresh([feed for feed in config['feeds'] if feed.get('enabled', True)], progress=self.guide_progress)
            self.check_cancelled()
            self.message, self.progress = 'Building your TV channels and guide…', 55
            config = pvr.config(self.store)
            config['enabled'] = True
            pvr.save_config(self.store, config)
            self.tv.build(collect=True, progress=self.channel_progress)
            self.check_cancelled()
            state = self.store.read(os.path.join(self.store.root, 'pvr-status.json'), {})
            if state.get('state') != 'ready' or not state.get('channels'):
                raise RuntimeError('TV channels could not be built. Check the internet connection and run Full install again. Your other Kodi add-ons are unchanged.')
            self.message, self.progress = 'Connecting Kodi TV…', 90
            pvr.configure_instance(self.iptv_profile,
                'special://profile/addon_data/plugin.video.stremio.bridge/pvr/channels.m3u',
                'special://profile/addon_data/plugin.video.stremio.bridge/pvr/guide.xml')
            self.progress = 100
            feeds = self.store.read(os.path.join(self.store.root,'programme-status.json'),{})
            result = dict(state, state='ready', completed=time.time(), elapsed=int(time.monotonic()-self.started),
                guide_failed=[f.get('label','Programme guide') for f in feeds.values() if f.get('state')=='error'])
            self.store.write(self.report_path,result)
            return result
        except InterruptedError:
            self.store.write(self.report_path,dict(state='cancelled',completed=time.time(),message='Repair cancelled. Previous usable TV files are kept.'))
            raise
        except Exception:
            self.store.write(self.report_path,dict(state='error',completed=time.time(),message='TV repair did not finish. Previous usable TV files are kept.'))
            raise
        finally:
            if owns_updates and self.tv.stop.is_set():
                path = os.path.join(self.store.root, 'programme-status.json')
                states = self.store.read(path, {})
                for state in states.values():
                    if state.get('state') == 'updating':
                        state['state'] = 'cancelled'
                self.store.write(path, states)
                path = os.path.join(self.store.root, 'pvr-status.json')
                state = self.store.read(path, {})
                if state.get('state') == 'updating':
                    state['state'] = 'cancelled'
                    self.store.write(path, state)
            self.store.write(self.flag, {})
