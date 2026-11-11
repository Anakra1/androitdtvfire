import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))
from resources.lib.core import Store, aggregate
from resources.lib.defaults import ensure_defaults
import test_movies as fixtures
from test_movies import FakeListItem, MOVIE


class DefaultsTests(unittest.TestCase):
    def test_clean_install_has_catalogue_and_torrents_without_network(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            ensure_defaults(store, str(ROOT))
            entries = store.providers()
            self.assertEqual({e['label'] for e in entries}, {'Cinemeta', 'Torrentio', 'MediaFusion TV', 'Pluto TV', 'Sports Streams'})
            streams = aggregate(entries, 'stream', 'movie', 'tt1', fetch=lambda url: {'streams': [{'infoHash': 'a' * 40}]})
            self.assertEqual(len(streams), 1)
            self.assertEqual(streams[0][0]['label'], 'Torrentio')
            ensure_defaults(store, str(ROOT))
            self.assertEqual(len(store.providers()), 5)

    def test_migration_preserves_personalised_and_disabled_providers(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            bundled = json.loads((ROOT / 'resources/defaults/torrentio.json').read_text(encoding='utf-8-sig'))
            store.add('https://example.org/personal-token/manifest.json', 'My configured provider', fetch=lambda url: bundled)
            entries = store.providers()
            entries[0]['enabled'] = False
            store.save_providers(entries)
            ensure_defaults(store, str(ROOT))
            entries = store.providers()
            self.assertEqual(len(entries), 5)
            self.assertFalse(entries[0]['enabled'])
            self.assertEqual(entries[0]['url'], 'https://example.org/personal-token/manifest.json')
            self.assertEqual(entries[0]['label'], 'My configured provider')

    def test_removals_respected_and_defaults_can_be_restored(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            ensure_defaults(store, str(ROOT))
            store.save_providers([])
            ensure_defaults(store, str(ROOT))
            self.assertEqual(store.providers(), [])
            ensure_defaults(store, str(ROOT), force=True)
            self.assertEqual(len(store.providers()), 5)

    def test_multiple_sources_aggregate_and_disabled_source_is_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            manifest = json.loads((ROOT / 'resources/defaults/torrentio.json').read_text(encoding='utf-8-sig'))
            first = store.add('https://first.example/manifest.json', fetch=lambda url: manifest)
            second = store.add('https://second.example/manifest.json', fetch=lambda url: dict(manifest, id='other.provider'))
            seen = []
            results = aggregate(store.providers(), 'stream', 'series', 'tt1:1:1', fetch=lambda url: seen.append(url) or {'streams': []})
            self.assertEqual(len(results), 2)
            store.save_providers([first, dict(second, enabled=False)])
            self.assertEqual(len(aggregate(store.providers(), 'stream', 'movie', 'tt1', fetch=lambda url: {})), 1)


class TorrentRouteTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.ServerFixture.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.ServerFixture.tearDownClass.__func__)
    setUp = fixtures.KodiRouteTests.setUp
    restore_modules = fixtures.KodiRouteTests.restore_modules
    record_rpc = fixtures.KodiRouteTests.record_rpc
    follow = fixtures.KodiRouteTests.follow

    def test_ongoing_series_uses_episode_sources_and_torrent_player(self):
        # Nocturne's real metadata uses this flag even for normal TV episodes.
        videos = [{'id': 'tt2:1:1', 'title': 'Pilot', 'season': 1, 'episode': 1}]
        with patch.dict(fixtures.SERIES, {'behaviorHints': {'hasScheduledVideos': True}, 'videos': videos}):
            self.app.catalogues()
            self.follow(0)  # catalogue
            self.follow(1)  # series -> seasons, NOT stream/series/tt2.json
            self.assertIn('Season 1', self.items[0][0][2].label)
            self.follow(0)  # season -> episodes
            self.assertIn('Pilot', self.items[0][0][2].label)
            self.follow(0)  # episode -> stream/series/tt2:1:1.json
        self.assertEqual(len(self.items), 4)
        from urllib.parse import parse_qs, urlsplit
        key = parse_qs(urlsplit(self.items[1][0][1]).query)['key'][0]
        selected = self.app.STORE.get(key)
        self.assertEqual(selected['id'], 'tt2:1:1')
        self.assertEqual(selected['type'], 'series')
        self.assertEqual(selected['stream']['infoHash'], 'a' * 40)
        import torrent_player
        prepared = FakeListItem(path='http://127.0.0.1:9123/stream/episode.mkv?play=true')
        with patch.object(torrent_player, 'prepare_item', return_value=prepared):
            self.follow(1)
        self.assertTrue(self.resolved[-1][1])
        self.assertIs(self.resolved[-1][2], prepared)

    def test_empty_embedded_streams_fall_back_to_enabled_providers(self):
        self.app.show_streams('series', 'tt2:1:1', fixtures.SERIES, inline=[])
        self.assertEqual(len(self.items), 4)
        self.assertIn('Built-in torrent player', self.items[1][0][2].label)
    def test_torrent_uses_built_in_player_and_kodi_resolver(self):
        import torrent_player
        key = self.app.STORE.put({'stream': {'infoHash': 'a' * 40}, 'type': 'movie', 'id': 'tt1', 'meta': MOVIE})
        prepared = FakeListItem(path='http://127.0.0.1:9123/stream/movie.mp4?play=true')
        with patch.object(torrent_player, 'prepare_item', return_value=prepared) as prepare:
            self.app.play(key)
        prepare.assert_called_once()
        self.assertTrue(self.resolved[-1][1])
        self.assertIs(self.resolved[-1][2], prepared)

    def test_cancelled_torrent_resolves_failure_without_external_player(self):
        import torrent_player
        key = self.app.STORE.put({'stream': {'infoHash': 'a' * 40}, 'type': 'movie', 'id': 'tt1', 'meta': MOVIE})
        with patch.object(torrent_player, 'prepare_item', return_value=None):
            self.app.play(key)
        self.assertFalse(self.resolved[-1][1])

    def test_magnet_preserves_trackers_and_rejects_bad_indexes(self):
        from torrent_player import torrent_magnet
        from urllib.parse import parse_qs, urlsplit
        uri = torrent_magnet({'infoHash': 'a' * 40, 'fileIdx': 0, 'sources': ['tracker:udp://example.org:80']})
        self.assertEqual(parse_qs(urlsplit(uri).query)['tr'], ['udp://example.org:80'])
        for source in ({'infoHash': '../invalid'}, {'infoHash': 'a' * 40, 'fileIdx': -1}):
            with self.assertRaises(ValueError):
                torrent_magnet(source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
