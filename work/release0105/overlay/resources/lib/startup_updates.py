"""Ask Kodi's repository manager to check once after an idle startup.

Kodi owns downloading, dependency checks and installation. This module never
changes update preferences, installs ZIPs or writes Kodi's addon database.
"""
import os
import time


class StartupUpdates:
    def __init__(self, store, addon, builtin, connected, clock=time.monotonic,
                 wall=time.time):
        self.store, self.addon = store, addon
        self.builtin, self.connected = builtin, connected
        self.clock, self.wall = clock, wall
        self.ready = clock() + 30
        self.deadline = clock() + 300
        self.done = False

    def poll(self, player, installing=False):
        if self.done or self.clock() < self.ready:
            return
        if self.addon.getSetting('startup_update_check') == 'false':
            self.done = True
            return
        if self.clock() > self.deadline:
            self.done = True
            return
        # Do not interrupt viewing, the setup wizard, or network startup.
        if installing or player.isPlaying() or not self.connected():
            return
        path = os.path.join(self.store.root, 'startup-update-check.json')
        previous = self.store.read(path, {})
        # Updating CBR restarts its service. Avoid triggering an update loop.
        age = self.wall() - previous.get('requested', 0)
        if 0 <= age < 300:
            self.done = True
            return
        self.builtin('UpdateAddonRepos')
        self.store.write(path, {'requested': self.wall(), 'version':
                               self.addon.getAddonInfo('version')})
        self.done = True
