import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))
from resources.lib.core import Store
from resources.lib.live_player import LiveAutoplay


class LiveAutoplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.autoplay = LiveAutoplay(self.store)
        self.channel = dict(provider='tv', provider_id='fixture', resource_type='tv', live_group='tv',
                            meta={'id': 'channel', 'type': 'tv', 'name': 'Channel'})
        self.player, self.item, self.notify = MagicMock(), MagicMock(), MagicMock()

    def begin(self):
        return self.autoplay.begin(self.channel['meta'], self.channel, [
            {'url': 'https://example.org/first.m3u8'}, {'url': 'https://example.org/second.m3u8'}])

    def poll(self):
        self.autoplay.poll(self.player, self.item, self.notify)

    def test_filters_setup_notices_and_duplicates_without_testing_urls_on_the_network(self):
        path = self.autoplay.begin(self.channel['meta'], self.channel, [
            {'url': 'https://example.org/configure'}, {'externalUrl': 'https://example.org/'},
            {'infoHash': 'a' * 40}, {'url': 'https://example.org/good.m3u8'},
            {'url': 'https://example.org/good.m3u8'},
            {'url': 'https://example.org/proxy', 'behaviorHints': {'proxyHeaders': {'response': {'x': 'y'}}}}])
        self.assertEqual(path, 'https://example.org/good.m3u8')
        self.assertEqual(self.store.read(self.autoplay.path)['targets'], [path])

    def test_error_tries_next_link_then_exhausts_without_looping(self):
        self.begin()
        self.autoplay.signal('error')
        self.poll()
        self.player.play.assert_called_once_with('https://example.org/second.m3u8', self.item.return_value)
        self.assertEqual(self.store.read(self.autoplay.path)['index'], 1)
        self.autoplay.signal('error')
        self.poll()
        self.assertEqual(self.store.read(self.autoplay.path), {})
        self.poll()
        self.assertEqual(self.player.play.call_count, 1)

    def test_stop_cancels_retry_even_if_an_error_arrives_at_the_same_time(self):
        self.begin()
        self.autoplay.signal('error')
        self.autoplay.signal('stopped')
        self.poll()
        self.player.play.assert_not_called()
        self.assertEqual(self.store.read(self.autoplay.path), {})

    def test_real_video_start_clears_retry_urls_and_later_errors_do_not_restart_it(self):
        self.begin()
        self.autoplay.signal('started')
        self.poll()
        self.assertEqual(self.store.read(self.autoplay.path), {})
        self.autoplay.signal('error')
        self.poll()
        self.player.play.assert_not_called()

    def test_old_events_and_expired_plans_cannot_interrupt_other_playback(self):
        with patch('resources.lib.live_player.time.time', return_value=1000):
            self.autoplay.signal('error')
        with patch('resources.lib.live_player.time.time', return_value=1001):
            self.begin()
            self.poll()
        self.player.play.assert_not_called()
        with patch('resources.lib.live_player.time.time', return_value=1200):
            self.autoplay.signal('error')
            self.poll()
        self.player.play.assert_not_called()
        self.assertEqual(self.store.read(self.autoplay.path), {})

