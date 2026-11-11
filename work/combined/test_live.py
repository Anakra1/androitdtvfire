import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))
from resources.lib.core import Store, aggregate, stream_kind, playback_url
from resources.lib.defaults import ensure_defaults, ensure_live_defaults
from resources.lib.live import catalogue_group, entry_catalogs, grouped_catalogues
import test_movies as fixtures


class LiveConfigurationTests(unittest.TestCase):
    def test_setup_notices_and_offline_videos_are_not_treated_as_live_media(self):
        notice = {'url': 'https://sports.example/configure', 'name': 'Please reinstall the addon'}
        offline = {'url': 'https://tv.example/static/exceptions/no_streams_live.mp4'}
        self.assertEqual(stream_kind(notice), 'configuration')
        self.assertEqual(stream_kind(offline), 'unavailable')
        with self.assertRaises(ValueError):
            playback_url(notice)
        self.assertEqual(stream_kind({'url': 'https://example.org/channel.m3u8'}), 'direct')

    def test_defaults_populate_three_separate_live_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            ensure_defaults(store, str(ROOT))
            entries = store.providers()
            tv = list(grouped_catalogues(entries, 'tv'))
            internet = list(grouped_catalogues(entries, 'internet'))
            sports = list(grouped_catalogues(entries, 'sports'))
            self.assertEqual([c['id'] for _, c in tv], ['live_tv'])
            self.assertEqual({e['label'] for e, _ in internet}, {'Pluto TV'})
            self.assertEqual(len(sports), 17)
            self.assertEqual({e['label'] for e, _ in sports}, {'Sports Streams'})
            # Live-only MediaFusion configuration must not be queried for movies.
            queried = []
            aggregate(entries, 'stream', 'movie', 'tt1', fetch=lambda url: queried.append(url) or {})
            self.assertEqual(len(queried), 1)
            self.assertIn('torrentio.strem.fun', queried[0])

    def test_disabled_and_removed_live_defaults_stay_disabled_or_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            ensure_defaults(store, str(ROOT))
            entries = store.providers()
            for entry in entries:
                if entry.get('live_group'):
                    entry['enabled'] = False
            store.save_providers(entries)
            ensure_defaults(store, str(ROOT))
            self.assertEqual(list(grouped_catalogues(store.providers(), 'sports')), [])
            store.save_providers([e for e in entries if not e.get('live_group')])
            ensure_defaults(store, str(ROOT))
            self.assertEqual(len(store.providers()), 2)
            ensure_live_defaults(store, str(ROOT), force=True)
            self.assertEqual(len(store.providers()), 5)

    def test_refresh_preserves_live_group_scope_and_supplemental_catalogue(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            manifest = {'id': 'local.live', 'name': 'Live', 'version': '1', 'types': ['tv'], 'resources': ['stream'], 'catalogs': []}
            entry = store.add('https://example.org/manifest.json', fetch=lambda url: manifest)
            entry.update(live_group='internet', scope_types=['tv'], enabled=False,
                         extra_catalogs=[{'id': 'live', 'type': 'tv', 'name': 'Channels'}])
            store.save_providers([entry])
            refreshed = store.add(entry['url'], fetch=lambda url: dict(manifest, version='2'))
            self.assertFalse(refreshed['enabled'])
            self.assertEqual(refreshed['live_group'], 'internet')
            self.assertEqual(refreshed['scope_types'], ['tv'])
            self.assertEqual(list(entry_catalogs(refreshed))[0]['id'], 'live')

    def test_automatic_grouping_supports_custom_sports_types_and_manual_override(self):
        entry = {'manifest': {'id': 'org.streamsppv.stremio'}}
        self.assertEqual(catalogue_group(entry, {'type': 'streamsppv'}), 'sports')
        self.assertEqual(catalogue_group({'manifest': {'id': 'org.plutotv'}}, {'type': 'tv'}), 'internet')
        self.assertIsNone(catalogue_group(dict(entry, live_group='sports'), {'type': 'movie'}))
        self.assertEqual(catalogue_group({'live_group': 'internet'}, {'type': 'custom-channel'}), 'internet')


class LiveRouteTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.ServerFixture.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.ServerFixture.tearDownClass.__func__)
    setUp = fixtures.KodiRouteTests.setUp
    restore_modules = fixtures.KodiRouteTests.restore_modules
    record_rpc = fixtures.KodiRouteTests.record_rpc
    follow = fixtures.KodiRouteTests.follow

    def test_live_home_has_requested_categories(self):
        self.app.live_home()
        self.assertEqual([args[2].label for args, _ in self.items],
                         ['Source setup (phone / PC)', 'TV Channels', 'Internet TV', 'Live Sports'])
        self.assertIn('action=web_setup', self.items[0][0][1])

    def test_sports_catalogue_to_live_stream_preserves_custom_type_and_skips_schedule(self):
        manifest = {'id': 'fixture.sports', 'name': 'Sports', 'version': '1', 'types': ['sport'],
                    'resources': ['catalog', 'meta', 'stream'],
                    'catalogs': [{'type': 'sport', 'id': 'sports_live', 'name': 'Live Now'}]}
        entry = self.app.STORE.add(self.url, fetch=lambda url: manifest)
        entry['live_group'] = 'sports'
        self.app.STORE.save_providers([entry])
        preview = {'id': 'event:1', 'type': 'sport', 'name': 'Fixture Match'}
        calls = []
        def query(entries, resource, kind, ident, extras=None):
            calls.append((resource, kind, ident))
            if resource == 'meta':
                # Some live providers return TV-shaped metadata and a programme list.
                # Neither is allowed to change /stream/sport/ into /stream/tv/.
                data = {'meta': dict(preview, type='tv', videos=[{'id': 'programme:1', 'season': 1}],
                                     behaviorHints={'hasScheduledVideos': True})}
            elif resource == 'stream':
                data = {'streams': [{'url': 'https://example.org/live.m3u8'}]}
            else:
                data = {'subtitles': []}
            return [(entry, data, None)]
        with patch.object(self.app, 'request', return_value={'metas': [preview]}), patch.object(self.app, 'aggregate', side_effect=query):
            self.app.live_catalogues('sports')
            self.follow(0)  # category -> catalogue
            self.follow(0)  # event -> sources, not a season folder
            self.assertEqual(len(self.items), 1)
            self.follow(0)  # source -> Kodi playback resolver
        self.assertIn(('stream', 'sport', 'event:1'), calls)
        self.assertTrue(self.resolved[-1][1])
        self.assertEqual(self.resolved[-1][2].path, 'https://example.org/live.m3u8')

    def test_additional_manifest_can_be_assigned_to_category(self):
        self.input_value = self.url
        self.app.add_provider('internet')
        self.assertEqual(self.app.STORE.provider(self.entry['key'])['live_group'], 'internet')


if __name__ == '__main__':
    unittest.main(verbosity=2)
