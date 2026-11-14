from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent / 'plugin.video.stremio.bridge'))
from resources.lib.core import Store
from resources.lib.live_hints import ChannelHints


class HintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.variant = dict(provider='configured-key', provider_id='tv', resource_type='tv', meta={'id':'channel'})
        self.stream = dict(url='https://example.org/video.m3u8?token=short-lived', name='Player 6')
        self.hints = ChannelHints(self.store, 'channel')

    def test_reuses_recent_link_after_probe_without_extending_expiry(self):
        with patch('resources.lib.live_hints.time.time', return_value=1000): self.hints.remember(self.variant,self.stream)
        with patch('resources.lib.live_hints.time.time', return_value=1050):
            probe=Mock(return_value=True)
            self.assertEqual(self.hints.cached([self.variant],probe)[0],self.stream['url'])
            probe.assert_called_once_with(self.stream)
        self.assertEqual(self.store.read(self.hints.path)['checked'],1000)
        with patch('resources.lib.live_hints.time.time', return_value=1100):
            probe=Mock();self.assertIsNone(self.hints.cached([self.variant],probe));probe.assert_not_called()
            self.assertEqual(self.hints.player(self.variant),'Player 6')

    def test_failed_cache_removes_url_but_keeps_recipe_and_never_crosses_sources(self):
        self.hints.remember(self.variant,self.stream)
        self.assertIsNone(self.hints.cached([self.variant],lambda s:False))
        self.assertNotIn('stream',self.store.read(self.hints.path))
        self.assertEqual(self.hints.player(self.variant),'Player 6')
        self.hints.remember(self.variant,self.stream)
        probe=Mock(return_value=True)
        self.assertIsNone(self.hints.cached([],probe))
        self.assertIsNone(self.hints.cached([dict(self.variant,provider='new-account')],probe))
        probe.assert_not_called()

    def test_expired_preferences_and_other_channels_do_not_reuse_links(self):
        with patch('resources.lib.live_hints.time.time', return_value=1000): self.hints.remember(self.variant,self.stream)
        self.assertFalse(ChannelHints(self.store,'other-channel').preferred(self.variant))
        with patch('resources.lib.live_hints.time.time', return_value=100000):
            self.assertFalse(self.hints.preferred(self.variant))
