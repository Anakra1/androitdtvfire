"""Short-lived live stream attempts, driven by Kodi's actual player callbacks."""
import os
import queue
import time
import uuid

from .core import playback_url, stream_kind
from .live import LiveLibrary


class LiveAutoplay:
    def __init__(self, store):
        self.store = store
        self.path = os.path.join(store.root, 'live-autoplay.json')
        self.events = queue.SimpleQueue()

    def clear(self):
        self.store.write(self.path, {})

    def begin(self, meta, channel, streams):
        targets = []
        for stream in streams:
            if stream_kind(stream) != 'direct':
                continue
            try:
                path = playback_url(stream)
            except ValueError:
                continue
            if path not in targets:
                targets.append(path)
        if not targets:
            self.clear()
            return None
        self.store.write(self.path, dict(session=uuid.uuid4().hex, created=time.time(), index=0,
                         targets=targets[:8], channel=channel, title=meta.get('name', 'Live TV')))
        return targets[0]

    def signal(self, event):
        self.events.put((time.time(), event))

    def poll(self, player, make_item, notify):
        plan = self.store.read(self.path, {})
        events = []
        while not self.events.empty():
            timestamp, event = self.events.get_nowait()
            if plan and timestamp >= plan.get('created', 0):
                events.append(event)
        if not plan:
            return
        # A stale plan must never interrupt unrelated playback later.
        if time.time() - plan.get('created', 0) > 120 or 'started' in events or 'stopped' in events:
            self.clear()
            return
        if not any(event in events for event in ('error', 'ended')):
            return
        if self.store.read(self.path, {}).get('session') != plan['session']:
            return
        index = plan['index'] + 1
        if index >= len(plan['targets']):
            self.clear()
            notify('This channel is currently unavailable. Please try again later.')
            return
        plan['index'] = index
        self.store.write(self.path, plan)
        path = plan['targets'][index]
        LiveLibrary(self.store).pending(plan['channel'], path)
        notify('Connecting to ' + plan['title'])
        try:
            player.play(path, make_item(path, plan['title'], plan['channel']['meta']))
        except Exception:
            self.signal('error')
