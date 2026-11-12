import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))
from resources.lib.core import Store, aggregate, stream_kind, playback_url
from resources.lib.defaults import ensure_defaults, ensure_live_defaults
from resources.lib.live import LiveCatalogueCache, LiveLibrary, catalogue_group, entry_catalogs, grouped_catalogues
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

    def test_large_channel_list_reuses_cache_and_writes_one_batch_per_page(self):
        manifest = dict(fixtures.MANIFEST, types=['tv'])
        entry = self.app.STORE.add(self.url, fetch=lambda url: manifest)
        cat = self.app.STORE.put({'id': 'uk', 'type': 'tv', 'name': 'UK'})
        metas = [{'id': 'channel:' + str(i), 'name': 'Channel ' + str(i), 'type': 'tv'} for i in range(547)]
        with patch.object(self.app, 'request', return_value={'metas': metas}) as request, \
             patch.object(self.app.STORE, 'write', wraps=self.app.STORE.write) as write, \
             patch.object(self.app.STORE, 'providers', wraps=self.app.STORE.providers) as providers:
            self.app.catalog_page(entry['key'], cat)
            self.assertEqual(len(self.items), 102)  # 100 channels, next, refresh
            self.assertEqual(write.call_count, 2)  # one listing cache and one channel batch
            self.assertLessEqual(providers.call_count, 2)
            first = self.items[0][0][1]
            self.follow(100)
            self.assertEqual(self.items[0][0][2].label, 'Channel 100')
            self.assertEqual(request.call_count, 1)
            self.items.clear()
            self.app.catalog_page(entry['key'], cat)  # Back to the first page
            self.assertEqual(self.items[0][0][1], first)
            self.assertEqual(request.call_count, 1)
            self.follow(101)  # manual refresh
            self.assertEqual(request.call_count, 2)
            # The last local page retains the remaining channels.
            self.items.clear()
            self.app.catalog_page(entry['key'], cat, offset=500)
            self.assertEqual(len(self.items), 48)
            self.assertEqual(self.items[46][0][2].label, 'Channel 546')
            command = self.items[46][0][2].context[0][1]
            import sys
            sys.argv[2] = '?' + command.split('?', 1)[1][:-1]
            self.app.main()
            self.assertEqual(self.app.LIVE_LIBRARY.entries('favourites')[0]['meta']['id'], 'channel:546')

    def test_live_channel_only_queries_its_own_provider_and_resolves_fresh_streams(self):
        entry = self.app.STORE.add(self.url, fetch=lambda url: dict(fixtures.MANIFEST, types=['tv']))
        self.app.STORE.add('https://other.example/manifest.json', fetch=lambda url: fixtures.MANIFEST)
        saved = dict(provider=entry['key'], resource_type='tv', live_group='tv',
                     meta={'id': 'bbc', 'type': 'tv', 'name': 'BBC'})
        key = self.app.STORE.put([saved])
        calls = []
        def query(entries, resource, kind, ident, extras=None):
            calls.append((resource, [e['key'] for e in entries]))
            data = {'meta': saved['meta']} if resource == 'meta' else {'streams': [{'url': 'https://example.org/fresh.m3u8'}]}
            return [(entry, data, None)]
        with patch.object(self.app, 'aggregate', side_effect=query):
            self.app.metadata(key, '0')
            self.app.metadata(key, '0')
        self.assertEqual(calls, [('meta', [entry['key']]), ('stream', [entry['key']])] * 2)
        with self.assertRaises(ValueError):
            self.app.cached_item(key, '-1')

    def test_channel_click_plays_directly_and_manual_sources_remain_in_context_menu(self):
        entry = self.app.STORE.add(self.url, fetch=lambda url: dict(fixtures.MANIFEST, types=['tv']))
        preview = {'id': 'channel', 'type': 'tv', 'name': 'Sky Atlantic'}
        self.app.add_metas([preview], entry['key'], 'tv', live_group='tv')
        self.assertFalse(self.items[0][1]['isFolder'])
        self.assertEqual(self.items[0][0][2].properties['IsPlayable'], 'true')
        manual = self.items[0][0][2].context[1][1]
        def query(entries, resource, kind, ident, extras=None):
            data = {'meta': preview} if resource == 'meta' else {'streams': [
                {'url': 'https://example.org/first.m3u8'}, {'url': 'https://example.org/second.m3u8'}]}
            return [(entry, data, None)]
        with patch.object(self.app, 'aggregate', side_effect=query):
            self.follow(0)
            self.assertEqual(self.items, [])  # no source chooser is displayed
            self.assertTrue(self.resolved[-1][1])
            self.assertEqual(self.resolved[-1][2].path, 'https://example.org/first.m3u8')
            import sys
            sys.argv[2] = '?' + manual.split('?', 1)[1][:-1]
            self.app.main()
        self.assertEqual(len(self.items), 2)
        self.assertEqual(self.app.STORE.read(self.app.LIVE_AUTOPLAY.path), {})

    def test_now_next_is_visible_on_channel_and_playback_without_changing_selection(self):
        from resources.lib import programmes as epg
        from test_programmes import XML, NOW
        path = Path(self.temp.name) / 'schedule.xml'
        path.write_text(XML)
        feed = dict(key='uk', country='GB', label='UK', enabled=True)
        epg.save_settings(self.app.STORE, dict(enabled=True, feeds=[feed], mappings={}))
        epg.import_xml(self.app.STORE, feed, path, now=NOW)
        self.app.PROGRAMMES = epg.ProgrammeGuide(self.app.STORE)
        self.addCleanup(self.app.PROGRAMMES.close)
        preview = {'id': 'vavoo_SKY%20ATLANTIC|group:uk', 'type': 'tv', 'name': 'SKY ATLANTIC'}
        def query(entries, resource, kind, ident, extras=None):
            return [(self.entry, {'meta': preview} if resource == 'meta' else
                     {'streams': [{'url': 'https://example.org/live.m3u8'}]}, None)]
        with patch.object(epg.time, 'time', return_value=NOW), patch.object(self.app, 'aggregate', side_effect=query):
            self.app.add_metas([preview], self.entry['key'], 'tv', live_group='tv')
            self.assertEqual(self.items[0][0][2].properties['CBR.Now'], 'Current show')
            self.assertIn('Next show', self.items[0][0][2].info['plot'])
            self.follow(0)
            self.assertEqual(self.items, [])
            self.assertTrue(self.resolved[-1][1])
            self.assertIn('Current synopsis', self.resolved[-1][2].info['plot'])

    def test_live_home_has_requested_categories(self):
        self.app.live_home()
        self.assertEqual([args[2].label for args, _ in self.items],
                         ['Favourite channels', 'Recently watched', 'Search Live TV',
                          'Source setup (phone / PC)', 'TV Channels', 'Internet TV', 'Live Sports', 'Programme information settings'])
        self.assertIn('action=web_setup', self.items[3][0][1])

    def test_country_browse_has_genre_folders_and_search_separate(self):
        manifest = dict(fixtures.MANIFEST, types=['tv'], catalogs=[
            {'id': 'uk', 'type': 'tv', 'name': 'TvVoo • United Kingdom',
             'extra': [{'name': 'genre', 'options': ['Tutti', 'News', 'Kids']}]},
            {'id': 'find_uk', 'type': 'tv', 'name': '🔎 United Kingdom',
             'extra': [{'name': 'search', 'isRequired': True}]}])
        entry = self.app.STORE.add(self.url, fetch=lambda url: manifest)
        self.app.STORE.save_providers([entry])
        self.app.live_catalogues('tv')
        self.follow(0)
        self.assertEqual([a[2].label for a, _ in self.items], ['United Kingdom', 'Search this source'])
        self.follow(0)
        self.assertEqual([a[2].label for a, _ in self.items], ['All channels', 'Kids', 'News'])
        preview = {'id': 'bbc', 'name': 'BBC', 'logo': 'https://example.org/bbc.png'}
        with patch.object(self.app, 'request', return_value={'metas': [preview]}) as request:
            self.follow(2)
        self.assertIn('/genre=News.json', request.call_args.args[0])
        self.assertEqual(self.items[0][0][2].art['thumb'], preview['logo'])
        self.assertIn('Add to CBR favourites', self.items[0][0][2].context[0][0])

    def test_empty_live_streams_reports_unavailable_without_asking_for_setup(self):
        with patch.object(self.app, 'aggregate', return_value=[(self.entry, {'streams': []}, None)]), \
             patch.object(self.app, 'notify') as notify:
            self.app.show_streams('tv', 'bbc', {'id': 'bbc', 'type': 'tv'}, channel={'live_group': 'tv'})
        self.assertIn('No playback links', notify.call_args.args[0])
        self.assertNotIn('configured', notify.call_args.args[0])

    def test_favourite_reopens_channel_with_fresh_stream_and_tracks_started_playback(self):
        entry = self.app.STORE.add(self.url, fetch=lambda url: dict(fixtures.MANIFEST, types=['tv']))
        preview = {'id': 'bbc', 'type': 'tv', 'name': 'BBC'}
        saved = dict(meta=preview, provider=entry['key'], resource_type='tv', live_group='tv')
        self.app.LIVE_LIBRARY.toggle(self.app.LIVE_LIBRARY.channel(saved))
        self.app.STORE.prune(days=-1)
        self.app.live_saved('favourites')
        def query(entries, resource, kind, ident, extras=None):
            data = {'meta': preview} if resource == 'meta' else {'streams': [{'url': 'https://example.org/fresh.m3u8'}]}
            return [(entry, data if resource != 'subtitles' else {}, None)]
        with patch.object(self.app, 'aggregate', side_effect=query):
            self.follow(0)
        self.assertTrue(self.resolved[-1][1])
        self.assertEqual(self.app.LIVE_LIBRARY.entries('recent'), [])
        player = MagicMock()
        player.isPlayingVideo.return_value = True
        player.getPlayingFile.return_value = 'https://example.org/fresh.m3u8'
        self.app.LIVE_LIBRARY.poll(player)
        self.assertEqual(self.app.LIVE_LIBRARY.entries('recent')[0]['meta']['id'], 'bbc')

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
            self.follow(0)  # category -> source
            self.follow(0)  # source -> catalogue -> events
            self.follow(0)  # event -> automatic Kodi playback resolver
        self.assertIn(('stream', 'sport', 'event:1'), calls)
        self.assertTrue(self.resolved[-1][1])
        self.assertEqual(self.resolved[-1][2].path, 'https://example.org/live.m3u8')
        self.assertEqual(self.app.LIVE_LIBRARY.entries('recent'), [])  # resolving is not playback


    def test_additional_manifest_can_be_assigned_to_category(self):
        self.input_value = self.url
        self.app.add_provider('internet')
        self.assertEqual(self.app.STORE.provider(self.entry['key'])['live_group'], 'internet')


class LiveLibraryTests(unittest.TestCase):
    def test_catalogue_cache_expires_refreshes_and_separates_provider_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            cache = LiveCatalogueCache(store)
            fetch = MagicMock(return_value={'metas': [{'id': 'bbc', 'streams': [{'url': 'expired'}]}]})
            url = 'https://example.org/catalog/tv/uk.json?token=one'
            with patch('resources.lib.live.time.time', return_value=1000):
                cached = cache.get(url, fetch)
            self.assertNotIn('streams', cached['metas'][0])
            with patch('resources.lib.live.time.time', return_value=1100):
                cache.get(url, fetch)
                self.assertEqual(fetch.call_count, 1)
                cache.get(url + '&genre=news', fetch)
                self.assertEqual(fetch.call_count, 2)
                cache.get(url, fetch, refresh=True)
                self.assertEqual(fetch.call_count, 3)
            with patch('resources.lib.live.time.time', return_value=1500):
                cache.get(url, fetch)
            self.assertEqual(fetch.call_count, 4)

    def test_favourites_survive_cache_pruning_and_manifest_url_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            manifest = dict(fixtures.MANIFEST, id='live.fixture')
            old = store.add('https://example.org/old/manifest.json', fetch=lambda url: manifest)
            library = LiveLibrary(store)
            saved = {'provider': old['key'], 'live_group': 'tv', 'resource_type': 'tv',
                     'meta': {'id': 'bbc', 'type': 'tv', 'name': 'BBC', 'streams': [{'url': 'expired'}]}}
            channel = library.channel(saved)
            self.assertNotIn('streams', channel['meta'])
            self.assertTrue(library.toggle(channel))
            store.prune(days=-1)
            new = store.add('https://example.org/new/manifest.json', fetch=lambda url: manifest)
            store.save_providers([new])
            self.assertEqual(library.resolve(library.entries('favourites')[0])['provider'], new['key'])
            self.assertTrue(library.is_favourite(library.channel(dict(saved, provider=new['key']))))
            self.assertFalse(library.toggle(channel))
            self.assertEqual(library.entries('favourites'), [])

    def test_history_only_records_matching_started_playback_and_resolves_fresh_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            library = LiveLibrary(store)
            channel = dict(provider='one', provider_id='live', resource_type='tv', live_group='tv',
                           meta={'id': 'bbc', 'type': 'tv', 'name': 'BBC'})
            library.pending(channel, 'https://example.org/live?token=secret|User-Agent=Kodi')
            self.assertNotIn('secret', Path(library.path('pending')).read_text())
            player = MagicMock()
            player.isPlayingVideo.return_value = False
            library.poll(player)
            self.assertEqual(library.entries('recent'), [])
            player.isPlayingVideo.return_value = True
            player.getPlayingFile.return_value = 'https://example.org/other'
            library.poll(player)
            self.assertEqual(library.entries('recent'), [])
            player.getPlayingFile.return_value = 'https://example.org/live?token=secret'
            library.poll(player)
            self.assertEqual(library.entries('recent'), [channel])
            library.pending(channel, player.getPlayingFile.return_value)
            library.poll(player)
            self.assertEqual(len(library.entries('recent')), 1)
            library.pending(channel, player.getPlayingFile.return_value)
            with patch('resources.lib.live.time.time', return_value=10**12):
                library.poll(player)
            self.assertEqual(store.read(library.path('pending')), {})

if __name__ == '__main__':
    unittest.main(verbosity=2)
