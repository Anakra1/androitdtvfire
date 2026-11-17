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
from .playback_memory import PlaybackMemory, channel_key, stream_key


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
        self.memory = PlaybackMemory(store)

    def clear(self):
        self.store.write(self.path, {})

    def begin(self, meta, channel, streams, probe=None, context=None):
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
        candidates = self.memory.rank(channel,candidates)[:8]
        excluded=(context or {}).get('failed',[])
        candidates=[pair for pair in candidates if channel_key(channel)+stream_key(pair[1]) not in excluded]
        preferred = bool(candidates and self.memory.preferred(channel,candidates[0][1]))
        if probe and preferred:
            result = probe(candidates[0][1])
            if result is False: candidates=candidates[1:];preferred=False
        if probe and candidates and not preferred:
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
                         targets=targets[:8], streams=[stream for _,stream in candidates], channel=channel, title=meta.get('name', 'Live TV')))
        self.memory.prepare(channel,candidates[0][1],targets[0],context)
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
        self.memory.prepare(plan['channel'],plan['streams'][index],path)
        LiveLibrary(self.store).pending(plan['channel'], path)
        notify('Connecting to ' + plan['title'])
        try:
            player.play(path, make_item(path, plan['title'], plan['channel']))
        except Exception:
            self.signal('error')
