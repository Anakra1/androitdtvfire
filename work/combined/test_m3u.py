import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))
from resources.lib import m3u, pvr
from resources.lib.core import Store, aggregate, normalize_url, playback_url
from resources.lib.setup_web import SetupServer

PLAYLIST = '''#EXTM3U
#EXTINF:-1 tvg-id="Example.uk@HD" tvg-logo="https://example.org/a,b.png" group-title="News",Example (720p)
#EXTVLCOPT:http-user-agent=CBR Test
https://example.org/old.m3u8
#EXTINF:-1 tvg-id="Example.uk@HD",Example HD
https://example.org/second.m3u8|Referer=https%3A%2F%2Fexample.org
#EXTINF:-1 tvg-id="Other.us@SD",Other channel
https://example.org/us.m3u8
'''


class PlaylistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                raw = cls.body.encode(); self.send_response(200)
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True); cls.thread.start()
        cls.url = 'http://127.0.0.1:{}/channels.m3u?token=a%2Bb'.format(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name); type(self).body = PLAYLIST
        with m3u._lock: m3u._cache.clear()

    def test_parser_preserves_headers_logos_alternatives_and_stable_ids(self):
        rows = m3u.parse(PLAYLIST, self.url)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['country'], 'GB')
        self.assertEqual(rows[0]['logo'], 'https://example.org/a,b.png')
        self.assertEqual(rows[0]['name'], 'Example')
        self.assertEqual(len(rows[0]['streams']), 2)
        self.assertIn('User-Agent=CBR+Test', playback_url(rows[0]['streams'][0]))
        self.assertIn('Referer=', playback_url(rows[0]['streams'][1]))
        renewed = m3u.parse(PLAYLIST.replace('/old.m3u8', '/new.m3u8'), self.url)
        self.assertEqual(rows[0]['id'], renewed[0]['id'])

    def test_hls_html_unsupported_schemes_and_explicit_drm_are_not_channel_sources(self):
        for text in ['<html>Login</html>', '#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\na.ts',
                     '#EXTM3U\n#EXTINF:-1,File\nfile:///private',
                     '#EXTM3U\n#EXTINF:-1,DRM\n#KODIPROP:inputstream.adaptive.license_type=widevine\nhttps://example.org/drm.mpd']:
            with self.assertRaises(ValueError): m3u.parse(text, self.url)

    def test_store_and_aggregate_use_playlist_without_appending_manifest_and_reload_at_playback(self):
        entry = self.store.add(self.url)
        self.assertEqual(normalize_url(self.url), self.url)
        self.assertEqual(entry['kind'], 'm3u')
        cat = entry['manifest']['catalogs'][0]
        self.assertEqual(cat['country'], 'GB')
        rows = m3u.resource(entry, 'catalog', 'tv', cat['id'])['metas']
        self.assertEqual(len(rows), 1)
        self.assertNotIn('streams', rows[0])
        type(self).body = PLAYLIST.replace('/old.m3u8', '/fresh.m3u8')
        result = aggregate([entry], 'stream', 'tv', rows[0]['id'])
        self.assertIn('/fresh.m3u8', result[0][1]['streams'][0]['url'])
        self.assertEqual(aggregate([entry], 'stream', 'movie', 'tt1'), [])

    def test_official_country_catalogues_use_specific_playlist_and_country_scoped_playback(self):
        entry = dict(url=m3u.DEFAULT_URL, kind='m3u')
        with patch.object(m3u, 'load', return_value=m3u.parse(PLAYLIST, self.url)) as load:
            channels = m3u.resource(entry, 'catalog', 'tv', 'm3u_uk')['metas']
            self.assertEqual(len(channels), 2)  # Includes international services in the UK list.
            self.assertTrue(all(r['country'] == 'GB' and r['id'].startswith('m3u.GB.') for r in channels))
            self.assertEqual(load.call_args.args[0], m3u.UK_URL)
            result = m3u.resource(entry, 'stream', 'tv', channels[0]['id'])
            self.assertEqual(len(result['streams']), 2)
            self.assertEqual(load.call_args.args[0], m3u.UK_URL)
            self.assertTrue(load.call_args.kwargs['force'])

    def test_default_is_offline_safe_preserves_other_sources_and_adds_only_uk_to_existing_selection(self):
        value = pvr.config(self.store); value.update(enabled=True, selected=['existing-source'])
        pvr.save_config(self.store, value)
        m3u.ensure_default(self.store)
        source = self.store.providers()[0]
        uk = [s for s in pvr.sources(self.store) if s['default']]
        self.assertEqual(len(uk), 1)
        self.assertEqual(pvr.config(self.store)['selected'], ['existing-source', uk[0]['key']])
        self.assertEqual(source['manifest']['catalogs'][0]['country'], 'GB')
        self.store.save_providers([]); m3u.ensure_default(self.store)
        self.assertEqual(self.store.providers(), [])

    def test_pvr_exports_metadata_only_and_maintains_source_identity(self):
        entry = self.store.add(self.url)
        pvr.PVRUpdater(self.store).build()
        path = Path(self.temp.name) / 'pvr/channels.m3u'
        self.assertIn('action=pvr_play', path.read_text())
        self.assertNotIn('old.m3u8', path.read_text())
        row = pvr.channels(self.store)[0]
        self.assertEqual(pvr.channel(self.store, row['id'])[1][0]['provider'], entry['key'])
        self.assertNotIn('streams', row['variants'][0]['meta'])

    def test_paired_setup_accepts_m3u_without_changing_other_sources(self):
        server = SetupServer(self.store, str(ROOT / 'resources/setup'), '127.0.0.1', host='127.0.0.1', port=0)
        self.addCleanup(server.close)
        def post(path, body, cookie=''):
            conn = http.client.HTTPConnection('127.0.0.1', server.port, timeout=3)
            conn.request('POST', path, json.dumps(body), {'Content-Type': 'application/json', 'Cookie': cookie})
            response = conn.getresponse(); response.read(); result=response.status, response.getheader('Set-Cookie'); conn.close(); return result
        code, cookie = post('/api/pair', {'code': server.code}); self.assertEqual(code, 200)
        code, _ = post('/api/save', {'url': self.url, 'label': 'My TV', 'enabled': True}, cookie.split(';')[0])
        self.assertEqual(code, 200)
        self.assertEqual(self.store.providers()[0]['kind'], 'm3u')


if __name__ == '__main__': unittest.main()
