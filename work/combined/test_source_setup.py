import http.client
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))
from resources.lib.core import Store
from resources.lib.setup_web import SetupController, SetupServer
from resources.lib import setup_web, pvr


def manifest(url):
    if 'invalid' in url:
        raise ValueError('The URL did not return a valid Stremio manifest.')
    return {'id': 'sports' if 'sports' in url else 'torrentio', 'name': 'Test provider',
            'version': '1.0', 'resources': ['stream'], 'types': ['movie', 'sport'], 'catalogs': []}


class SourceSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        sports = self.store.add('https://sports.example/old/manifest.json', 'Sports', fetch=manifest)
        sports.update(live_group='sports', scope_types=['sport'], enabled=False)
        other = self.store.add('https://torrentio.example/manifest.json', 'Torrentio', fetch=manifest)
        self.store.save_providers([sports, other])
        self.sports_key = sports['key']
        self.server = SetupServer(self.store, str(ROOT / 'resources/setup'), '127.0.0.1',
                                  host='127.0.0.1', port=0, fetch=manifest)
        self.cookie = ''

    def tearDown(self):
        self.server.close()
        self.temp.cleanup()

    def request(self, path, data=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.port, timeout=3)
        values = {'Cookie': self.cookie} if self.cookie else {}
        raw = None
        if data is not None:
            raw = json.dumps(data)
            values['Content-Type'] = 'application/json'
        values.update(headers or {})
        connection.request('POST' if data is not None else 'GET', path, body=raw, headers=values)
        response = connection.getresponse()
        body = response.read()
        cookie = response.getheader('Set-Cookie')
        status = response.status
        connection.close()
        return status, body, cookie

    def pair(self):
        status, _, cookie = self.request('/api/pair', {'code': self.server.code})
        self.assertEqual(status, 200)
        self.cookie = cookie.split(';')[0]
        return cookie

    def test_private_sources_require_pairing(self):
        status, body, _ = self.request('/api/sources')
        self.assertEqual(status, 401)
        self.assertNotIn(b'sports.example', body)
        cookie = self.pair()
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Strict', cookie)
        status, body, _ = self.request('/api/sources')
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)['sources']), 2)

    def test_programme_feeds_require_pairing_and_do_not_change_stream_sources(self):
        self.assertEqual(self.request('/api/programmes')[0], 401)
        self.assertEqual(self.request('/api/programmes/save', {})[0], 401)
        self.pair()
        before = self.store.providers()
        self.assertEqual(self.request('/api/programmes/save', {'url': 'file:///private', 'country': 'GB'})[0], 400)
        self.assertEqual(self.request('/api/programmes/save', {'url': 'https://example.org/guide.xml.gz',
                        'label': 'My guide', 'country': 'GB', 'enabled': True})[0], 200)
        result = json.loads(self.request('/api/programmes')[1])
        added = next(f for f in result['settings']['feeds'] if f['label'] == 'My guide')
        self.assertEqual(self.request('/api/programmes/remove', {'key': added['key']})[0], 200)
        self.assertEqual(self.store.providers(), before)

    def test_wrong_codes_are_rate_limited(self):
        wrong = 'wrong'
        for _ in range(5):
            self.assertEqual(self.request('/api/pair', {'code': wrong})[0], 403)
        self.assertEqual(self.request('/api/pair', {'code': self.server.code})[0], 429)

    def test_pvr_pairing_source_selection_and_channel_edits(self):
        self.assertEqual(self.request('/api/pvr')[0], 401)
        self.assertEqual(self.request('/api/pvr/guide', {})[0], 401)
        self.assertEqual(self.request('/api/pvr/sources', {'selected': []})[0], 401)
        tv = dict(id='test.tv', name='Test TV', version='1', resources=['catalog', 'stream'],
                  types=['tv'], catalogs=[dict(id='channels_uk', name='UK', type='tv')])
        entry = self.store.add('https://tv.example/private-token/manifest.json', fetch=lambda url: tv)
        variant = dict(provider=entry['key'], provider_id=tv['id'], provider_label=entry['label'],
                       resource_type='tv', live_country='GB', live_group='tv',
                       meta=dict(id='sky', name='Sky Atlantic', type='tv'))
        rows = pvr.merge_channels([variant])
        self.store.write(str(Path(self.temp.name) / 'pvr-channels.json'), rows)
        self.pair()
        result = json.loads(self.request('/api/pvr')[1])
        self.assertNotIn('private-token', json.dumps(result))
        self.assertEqual(result['channels'][0]['visible'], True)
        self.assertIn('guide_options', result)
        self.assertEqual(result['channels'][0]['alternatives'], 1)
        self.assertFalse(result['channels'][0]['has_programmes'])
        self.assertEqual(self.request('/api/pvr/guide', {'id': rows[0]['id'], 'mapping': {'feed': 'bad', 'channel': 'bad'}})[0], 400)
        self.assertEqual(self.request('/api/pvr/guide', {'id': rows[0]['id'], 'mapping': None})[0], 200)
        for selected in ([], ['missing'], [{}]):
            self.assertEqual(self.request('/api/pvr/sources', {'selected': selected})[0], 400)
        selected = [result['sources'][0]['key']]
        self.assertEqual(self.request('/api/pvr/sources', {'selected': selected})[0], 200)
        self.assertEqual(pvr.config(self.store)['selected'], selected)
        self.assertEqual(self.request('/api/pvr/channels', {'channels': ['invalid']})[0], 400)
        edit = dict(id=rows[0]['id'], name='Atlantic', number=150, groups=['Sky'], visible=True)
        self.assertEqual(self.request('/api/pvr/channels', {'channels': [edit]})[0], 200)
        self.assertEqual(pvr.channels(self.store)[0]['number'], 150)
        self.assertFalse(self.store.read(str(Path(self.temp.name) / 'pvr-request.json'))['collect'])

    def test_foreign_origin_and_rebinding_host_are_rejected(self):
        self.pair()
        self.assertEqual(self.request('/api/sources', headers={'Host': 'attacker.example'})[0], 403)
        self.assertEqual(self.request('/api/save', {}, headers={'Origin': 'https://attacker.example'})[0], 403)

    def test_expired_pairing_session_cannot_read_or_write(self):
        self.pair()
        self.server.expires = time.time() - 1
        self.assertEqual(self.request('/api/sources')[0], 410)
        self.assertEqual(self.request('/api/remove', {'key': self.sports_key})[0], 410)
        self.assertEqual(len(self.store.providers()), 2)

    def test_edit_replaces_expired_url_preserving_other_sources_and_scope(self):
        self.pair()
        status, _, _ = self.request('/api/save', {'key': self.sports_key, 'label': 'Sports current',
                                   'url': 'https://sports.example/new/manifest.json', 'group': 'sports', 'enabled': True})
        self.assertEqual(status, 200)
        entries = self.store.providers()
        self.assertEqual(len(entries), 2)
        updated = next(entry for entry in entries if entry['label'] == 'Sports current')
        self.assertEqual(updated['scope_types'], ['sport'])
        self.assertEqual(updated['live_group'], 'sports')
        self.assertTrue(updated['enabled'])
        self.assertFalse(any('/old/' in entry['url'] for entry in entries))
        self.assertTrue(any(entry['label'] == 'Torrentio' for entry in entries))

    def test_invalid_manifest_does_not_overwrite_working_source(self):
        self.pair()
        before = self.store.providers()
        status, _, _ = self.request('/api/save', {'key': self.sports_key, 'url': 'https://invalid.example/manifest.json'})
        self.assertEqual(status, 400)
        self.assertEqual(self.store.providers(), before)

    def test_static_assets_are_served_but_filesystem_paths_are_not(self):
        for path in ('/', '/style.css', '/setup.js'):
            self.assertEqual(self.request(path)[0], 200)
        self.assertEqual(self.request('/../../providers.json')[0], 404)

    def test_controller_does_not_open_listener_until_requested(self):
        controller = SetupController(self.temp.name, str(ROOT), lambda: '127.0.0.1')
        controller.poll()
        self.assertIsNone(controller.server)
        self.assertEqual(self.store.read(controller.endpoint), {})
        controller.close()

    def test_kodi_request_opens_setup_and_close_request_stops_it(self):
        controller = SetupController(self.temp.name, str(ROOT), lambda: '127.0.0.1')
        self.store.write(controller.request, {'nonce': 'test-request', 'time': time.time()})
        factory = lambda store, assets, address: SetupServer(store, assets, address, host='127.0.0.1', port=0, fetch=manifest)
        with patch.object(setup_web, 'SetupServer', side_effect=factory):
            controller.poll()
        endpoint = self.store.read(controller.endpoint)
        self.assertEqual(endpoint['nonce'], 'test-request')
        self.assertEqual(endpoint['code'], controller.server.code)
        self.assertTrue(controller.server.active)
        self.store.write(controller.request, {'nonce': 'test-request', 'stop': True})
        controller.poll()
        self.assertIsNone(controller.server)
        self.assertEqual(self.store.read(controller.endpoint), {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
