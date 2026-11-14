"""Short-lived device-local TV links and longer-lived source preferences."""
import hashlib
import os
import time

from .core import playback_url

LINK_TTL = 90
SOURCE_TTL = 24 * 3600


def identity(variant):
    return [variant['provider_id'], variant['resource_type'], variant['meta']['id']]


class ChannelHints:
    def __init__(self, store, channel):
        self.store = store
        key = hashlib.sha256(str(channel).encode()).hexdigest()
        self.path = os.path.join(store.root, 'live-source-hints', key + '.json')
        try:
            self.value = store.read(self.path, {})
            if not isinstance(self.value, dict): self.value = {}
        except (OSError, ValueError):
            self.value = {}

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self.store.write(self.path, self.value)
        except OSError:
            # A full/read-only cache must not prevent channel playback.
            pass

    def age(self):
        try: return time.time() - float(self.value.get('checked', 0))
        except (TypeError, ValueError): return float('inf')

    def preferred(self, variant):
        age = self.age()
        return 0 <= age < SOURCE_TTL and self.value.get('variant') == identity(variant)

    def order(self, variants):
        return sorted(variants, key=lambda v: not self.preferred(v))

    def player(self, variant):
        return self.value.get('player', '') if self.preferred(variant) else ''

    def cached(self, variants, probe):
        age = self.age()
        variant = next((v for v in variants if self.preferred(v) and v['provider'] == self.value.get('provider')), None)
        stream = self.value.get('stream')
        if variant is None or not isinstance(stream, dict) or not 0 <= age < LINK_TTL:
            return None
        try:
            path = playback_url(stream)
            if probe(stream) is True:
                # Keep the original expiry: repeated uses must not extend a token's life.
                return path, variant
        except Exception:
            pass
        self.value.pop('stream', None)
        self.save()
        return None

    def remember(self, variant, stream):
        # These URLs can carry tokens. Keep them only in the Kodi profile, never
        # in exported M3Us, logs, programme data or a public playlist.
        self.value = dict(checked=time.time(), variant=identity(variant), provider=variant['provider'],
                          player=stream.get('name', ''), stream=stream)
        self.save()
