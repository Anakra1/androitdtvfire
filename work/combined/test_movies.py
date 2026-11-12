import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))
from resources.lib import core

MANIFEST = {'id': 'test.bridge', 'name': 'Test', 'version': '1.0.0',
            'types': ['movie', 'series', 'tv'], 'resources': ['catalog', 'meta', 'stream', 'subtitles'],
            'catalogs': [{'type': 'movie', 'id': 'popular', 'name': 'Popular',
                          'extra': [{'name': 'search'}, {'name': 'skip'}]}]}
MOVIE = {'id': 'tt1', 'type': 'movie', 'name': 'Fixture Movie', 'description': 'Description',
         'poster': 'https://example.org/poster.jpg', 'background': 'https://example.org/fanart.jpg',
         'releaseInfo': '2024', 'imdbRating': '7.4', 'genres': ['Drama']}
SERIES = {'id': 'tt2', 'type': 'series', 'name': 'Fixture Series', 'videos': [
    {'id': 'tt2:1:1', 'title': 'Pilot', 'season': 1, 'episode': 1,
     'streams': [{'url': 'https://example.org/episode.mp4'}]}]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.endswith('/manifest.json'):
            data = MANIFEST
        elif '/catalog/' in self.path:
            data = {'metas': [MOVIE, SERIES]}
        elif '/meta/series/' in self.path:
            data = {'meta': SERIES}
        elif '/meta/' in self.path:
            data = {'meta': MOVIE}
        elif '/stream/' in self.path:
            data = {'streams': [{'name': '1080p', 'url': 'https://example.org/video.mp4',
                                  'behaviorHints': {'proxyHeaders': {'request': {'Referer': 'https://example.org/'}}}},
                                 {'infoHash': 'a' * 40, 'fileIdx': 0},
                                 {'externalUrl': 'https://example.org/watch'}, {'ytId': 'abc'}]}
        elif '/subtitles/' in self.path:
            data = {'subtitles': [{'id': '1', 'url': 'https://example.org/eng.srt', 'lang': 'eng'}]}
        elif self.path == '/invalid':
            data = []
        else:
            self.send_error(404)
            return
        raw = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(raw)


class ServerFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:{}/config/token/manifest.json'.format(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()


class ProtocolTests(ServerFixture):
    def test_manifest_url_normalization_and_rejection(self):
        self.assertEqual(core.normalize_url('stremio://example.org/token/manifest.json'), 'https://example.org/token/manifest.json')
        self.assertEqual(core.normalize_url('https://example.org/token'), 'https://example.org/token/manifest.json')
        for value in ['file:///etc/passwd', 'https://example.org/configure', 'https://u:p@example.org/manifest.json', 'https://example.org/manifest.json#token=x']:
            with self.assertRaises(ValueError):
                core.normalize_url(value)

    def test_query_config_survives_store_and_resource_requests(self):
        url = 'https://example.org/manifest.json?genres=News%2CTop+News&token=a%2Bb'
        with tempfile.TemporaryDirectory() as directory:
            store = core.Store(directory)
            seen = []
            entry = store.add(url, fetch=lambda requested: seen.append(requested) or MANIFEST)
            self.assertEqual(seen, [url])
            self.assertEqual(entry['url'], url)
            self.assertEqual(core.resource_url(entry['url'], 'catalog', 'tv', 'news', {'skip': 100}),
                             'https://example.org/catalog/tv/news/skip=100.json?genres=News%2CTop+News&token=a%2Bb')
            self.assertEqual(core.resource_url(entry['url'], 'stream', 'tv', 'ABC.us'),
                             'https://example.org/stream/tv/ABC.us.json?genres=News%2CTop+News&token=a%2Bb')

    def test_resource_url_preserves_configuration_and_escapes_ids(self):
        url = core.resource_url(self.url, 'stream', 'series', 'tt1:1:2/a', {'filename': 'x&y + z', 'videoSize': 10})
        self.assertIn('/config/token/stream/series/tt1%3A1%3A2%2Fa/', url)
        self.assertIn('filename=x%26y%20%2B%20z', url)

    def test_resource_specific_filters_override_global_prefixes(self):
        manifest = dict(MANIFEST, idPrefixes=['tt'], resources=[{'name': 'stream', 'types': ['tv']}, 'meta'])
        self.assertTrue(core.supports(manifest, 'stream', 'tv', 'custom:1'))
        self.assertFalse(core.supports(manifest, 'stream', 'movie', 'tt1'))
        self.assertFalse(core.supports(manifest, 'meta', 'tv', 'custom:1'))
        self.assertTrue(core.supports(manifest, 'meta', 'movie', 'tt1'))

    def test_live_http_store_and_aggregation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = core.Store(directory)
            entry = store.add(self.url)
            store.add(self.url)
            self.assertEqual(len(store.providers()), 1)
            results = core.aggregate(store.providers(), 'stream', 'movie', 'tt1')
            self.assertEqual(len(results[0][1]['streams']), 4)
            self.assertIsNone(results[0][2])
            entries = [dict(entry, enabled=False)]
            self.assertEqual(core.aggregate(entries, 'stream', 'movie', 'tt1'), [])
            key = store.put({'secret': 'test'})
            self.assertEqual(store.get(key), {'secret': 'test'})
            with self.assertRaises(ValueError):
                store.get('../providers')
            store.prune(days=-1)
            with self.assertRaises(ValueError):
                store.get(key)

    def test_provider_failure_does_not_expose_tokens(self):
        entry = {'key': 'a', 'label': 'Test', 'url': self.url, 'manifest': MANIFEST}
        def fail(url):
            raise RuntimeError('secret-token-in-url')
        result = core.aggregate([entry], 'stream', 'movie', 'tt1', fetch=fail)
        self.assertEqual(result[0][2], 'Provider request failed')

    def test_invalid_http_response_and_manifest(self):
        with self.assertRaises(ValueError):
            core.fetch_json(self.url.split('/config/')[0] + '/invalid')
        with self.assertRaises(ValueError):
            core.validate_manifest({})
        with self.assertRaises(ValueError):
            core.validate_manifest(dict(MANIFEST, behaviorHints={'configurationRequired': True}))

    def test_playback_headers_youtube_and_unsupported_sources(self):
        stream = {'url': 'https://example.org/a.m3u8', 'behaviorHints': {'proxyHeaders': {'request': {'User-Agent': 'A B', 'Referer': 'https://example.org/'}}}}
        resolved = core.playback_url(stream)
        self.assertIn('|User-Agent=A+B&Referer=', resolved)
        self.assertIn('video_id=abc', core.playback_url({'ytId': 'abc'}))
        for stream in [{'infoHash': 'a' * 40}, {'url': 'file:///private'}, {'externalUrl': 'https://example.org'}]:
            with self.assertRaises(ValueError):
                core.playback_url(stream)
        with self.assertRaises(ValueError):
            core.playback_url({'url': 'https://example.org/a', 'behaviorHints': {'proxyHeaders': {'response': {'x': 'y'}}}})


class FakeListItem:
    def __init__(self, label='', path=''):
        self.label, self.path, self.subtitles = label, path, []
        self.art, self.context, self.properties, self.info = {}, [], {}, {}
    def getVideoInfoTag(self):
        return self
    def __getattr__(self, name):
        return lambda *args, **kwargs: None
    def setSubtitles(self, values):
        self.subtitles = values
    def setArt(self, art):
        self.art = art
    def addContextMenuItems(self, values):
        self.context.extend(values)
    def setProperty(self, name, value):
        self.properties[name] = value
    def setTitle(self, value):
        self.info['title'] = value
    def setMediaType(self, value):
        self.info['mediatype'] = value
    def setPlot(self, value):
        self.info['plot'] = value
    def setRating(self, value):
        self.info['rating'] = value


class KodiRouteTests(ServerFixture):
    # Reuse the real HTTP fixture, with Kodi's boundary replaced by recording stubs.
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.items, self.resolved, self.ended, self.messages = [], [], [], []
        self.content, self.rpc_calls = [], []
        self.selection = 0
        self.input_value = 'test'
        dialog = types.SimpleNamespace(
            select=lambda *args: self.selection, input=lambda *args: self.input_value,
            notification=lambda *args: None, ok=lambda *args: self.messages.append(args),
            textviewer=lambda *args: None, browse=lambda *args: '')
        addon = types.SimpleNamespace(getAddonInfo=lambda key: self.temp.name if key == 'profile' else str(ROOT))
        modules = {
            'xbmc': types.SimpleNamespace(getCondVisibility=lambda value: False, Player=lambda: types.SimpleNamespace(play=lambda value: None),
                executeJSONRPC=lambda payload: self.record_rpc(payload), executebuiltin=lambda value: None),
            'xbmcaddon': types.SimpleNamespace(Addon=lambda: addon),
            'xbmcgui': types.SimpleNamespace(Dialog=lambda: dialog, ListItem=FakeListItem, NOTIFICATION_INFO='info'),
            'xbmcplugin': types.SimpleNamespace(addDirectoryItem=lambda *args, **kwargs: self.items.append((args, kwargs)),
                setContent=lambda *args: self.content.append(args[1]), setPluginCategory=lambda *args: None,
                endOfDirectory=lambda *args, **kwargs: self.ended.append((args, kwargs)),
                setResolvedUrl=lambda *args: self.resolved.append(args)),
            'xbmcvfs': types.SimpleNamespace(translatePath=lambda value: value),
        }
        self.old_modules = {k: sys.modules.get(k) for k in modules}
        sys.modules.update(modules)
        self.addCleanup(self.restore_modules)
        self.old_argv = sys.argv[:]
        sys.argv = ['plugin://plugin.video.stremio.bridge', '1', '']
        self.addCleanup(lambda: setattr(sys, 'argv', self.old_argv))
        spec = importlib.util.spec_from_file_location('bridge_addon_test', ROOT / 'addon.py')
        self.app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.app)
        self.entry = self.app.STORE.add(self.url)
        self.app.STORE.write(os.path.join(self.temp.name, 'combined-defaults-v1.json'), True)
        self.app.STORE.write(os.path.join(self.temp.name, 'live-defaults-v1.json'), True)

    def restore_modules(self):
        for key, value in self.old_modules.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value

    def record_rpc(self, payload):
        self.rpc_calls.append(json.loads(payload))
        return json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': 'OK'})

    def follow(self, index):
        url = self.items[index][0][1]
        self.items.clear()
        sys.argv[2] = '?' + urlsplit(url).query
        self.app.main()

    def test_movie_browse_to_playback(self):
        self.app.catalogues()
        self.follow(0)  # catalogue
        self.assertEqual(len(self.items), 4)  # movie, series, library export, pagination
        self.follow(0)  # movie -> streams
        self.assertEqual(len(self.items), 4)
        self.selection = 1  # English subtitle
        self.follow(0)
        self.assertTrue(self.resolved[-1][1])
        self.assertIn('|Referer=', self.resolved[-1][2].path)
        self.assertEqual(self.resolved[-1][2].subtitles, ['https://example.org/eng.srt'])
        self.assertFalse(self.messages)

    def test_series_season_episode_inline_stream(self):
        self.app.catalogues()
        self.follow(0)
        self.follow(1)  # series
        self.assertIn('Season 1', self.items[0][0][2].label)
        self.follow(0)  # season
        self.assertIn('Pilot', self.items[0][0][2].label)
        self.follow(0)  # episode with embedded stream
        self.assertEqual(len(self.items), 1)
        self.follow(0)
        self.assertEqual(self.resolved[-1][2].path, 'https://example.org/episode.mp4')

    def test_search_and_private_routes(self):
        self.app.search()
        self.assertEqual(len(self.items), 2)
        for args, kwargs in self.items:
            self.assertNotIn('token', args[1])
            self.assertNotIn(self.url, args[1])
        self.assertTrue(self.ended)

    def test_torrent_external_and_missing_youtube_fail_cleanly(self):
        for stream in [{'externalUrl': 'https://example.org/watch'}, {'ytId': 'abc'}]:
            key = self.app.STORE.put({'stream': stream, 'type': 'movie', 'id': 'tt1', 'meta': MOVIE})
            self.app.play(key)
            self.assertFalse(self.resolved[-1][1])
        self.assertEqual(len(self.messages), 2)

    def test_expired_route_is_reported(self):
        sys.argv[2] = '?action=play&key=' + 'a' * 64
        self.app.main()
        self.assertFalse(self.resolved[-1][1])
        self.assertIn('expired', self.messages[-1][1])

    def test_movie_home_displays_posters_and_movie_content(self):
        self.app.home()
        self.assertEqual(self.content[-1], 'movies')
        movies = [args[2] for args, _ in self.items if args[2].info.get('mediatype') == 'movie']
        self.assertEqual(len(movies), 1)
        self.assertEqual(movies[0].art['poster'], MOVIE['poster'])
        self.assertEqual(movies[0].art['thumb'], MOVIE['poster'])
        self.assertEqual(movies[0].art['fanart'], MOVIE['background'])
        self.assertEqual(movies[0].info['plot'], MOVIE['description'])
        self.assertEqual(movies[0].info['rating'], 7.4)
        self.assertTrue(any('Add to Kodi Movies library' in label for label, command in movies[0].context))

    def test_library_export_has_metadata_and_durable_playback(self):
        key = self.app.STORE.put({'meta': MOVIE, 'provider': self.entry['key']})
        self.app.export_movie(key)
        folder = next(Path(self.app.LIBRARY.root).iterdir())
        strm = (folder / 'movie.strm').read_text(encoding='utf-8').strip()
        self.assertNotIn('token', strm)
        nfo = ET.fromstring((folder / 'movie.nfo').read_text(encoding='utf-8'))
        self.assertEqual(nfo.findtext('title'), MOVIE['name'])
        self.assertEqual(nfo.findtext('thumb'), MOVIE['poster'])
        self.assertEqual(nfo.findtext('plot'), MOVIE['description'])
        self.assertEqual(nfo.findtext('year'), '2024')
        self.app.STORE.prune(days=-1)  # Playback must survive cache expiration.
        sys.argv[2] = '?' + urlsplit(strm).query
        self.app.main()
        self.assertTrue(self.resolved[-1][1])
        self.assertIn('https://example.org/video.mp4', self.resolved[-1][2].path)

    def test_library_export_is_idempotent_and_safe(self):
        from resources.lib.library import MovieLibrary
        library = MovieLibrary(self.app.STORE)
        library.export(dict(MOVIE, name='../../evil < &'))
        library.export(dict(MOVIE, name='Renamed'))
        self.assertEqual(len(list(Path(library.root).iterdir())), 1)
        with self.assertRaises(ValueError):
            library.load('../../private')
        with self.assertRaises(ValueError):
            library.export(SERIES)
        self.assertTrue(Path(library.root).is_relative_to(Path(self.temp.name)))

    def test_movies_shortcut_uses_kodi_favourites_api(self):
        sys.argv[2] = '?action=favourite'
        self.app.main()
        self.assertEqual(self.rpc_calls[-1]['method'], 'Favourites.AddFavourite')
        self.assertEqual(self.rpc_calls[-1]['params']['type'], 'window')
        self.assertEqual(self.rpc_calls[-1]['params']['windowparameter'], 'plugin://plugin.video.stremio.bridge/')


if __name__ == '__main__':
    unittest.main(verbosity=2)


