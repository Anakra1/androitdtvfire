"""Short-lived live stream attempts, driven by Kodi's actual player callbacks."""
import os
import queue
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .core import playback_url, stream_kind
from .live import LiveLibrary


def probe_stream(stream):
    """Reject explicit HTTP failures without downloading video or trusting HEAD."""
    if urlsplit(stream.get('url', '')).scheme not in ('http', 'https'):
        return None
    headers = {'User-Agent': 'Kodi/21.2'}
    headers.update(((stream.get('behaviorHints') or {}).get('proxyHeaders') or {}).get('request') or {})
    try:
        with urlopen(Request(stream['url'], headers=headers), timeout=4) as response:
            return 200 <= response.getcode() < 300
    except HTTPError as error:
        error.close()
        return False
    except Exception:
        # A probe timeout is inconclusive; Kodi can still try this alternative.
        return None


class LiveAutoplay:
    def __init__(self, store):
        self.store = store
        self.path = os.path.join(store.root, 'live-autoplay.json')
        self.events = queue.SimpleQueue()

    def clear(self):
        self.store.write(self.path, {})

    def begin(self, meta, channel, streams, probe=None):
        candidates, seen = [], set()
        for stream in streams:
            if stream_kind(stream) != 'direct':
                continue
            try:
                path = playback_url(stream)
            except ValueError:
                continue
            if path not in seen:
                candidates.append((path, stream))
                seen.add(path)
        candidates = candidates[:8]
        if probe and candidates:
            with ThreadPoolExecutor(max_workers=4) as executor:
                states = list(executor.map(probe, [stream for _, stream in candidates]))
            # A successful response comes before an inconclusive probe. Explicit
            # 403/404/etc. responses must not prevent reaching a working option.
            candidates = ([pair for pair, state in zip(candidates, states) if state is True]
                          + [pair for pair, state in zip(candidates, states) if state is None])
        targets = [path for path, _ in candidates]
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
