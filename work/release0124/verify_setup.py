"""Behaviour checks against the packaged setup server and native menu functions."""
from pathlib import Path
import ast
import http.client
import json
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
STAGE = HERE / 'stage/plugin.video.stremio.bridge'
sys.path.insert(0, str(STAGE))
from resources.lib.core import Store
from resources.lib.setup_web import SetupServer, source_sections


def manifest(url):
    return {'id': 'fixture', 'name': 'Fixture', 'version': '1', 'resources': ['stream'],
            'types': ['movie', 'series'], 'catalogs': []}


class SetupChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=HERE / 'fixture-data')
        self.store = Store(self.temp.name)
        self.entry = self.store.add('https://fixture.example/manifest.json', 'Shared fixture', fetch=manifest)
        self.entry.update(enabled=False, custom_option='keep-me')
        self.store.save_providers([self.entry])
        self.server = SetupServer(self.store, str(STAGE / 'resources/setup'), '127.0.0.1', host='127.0.0.1', port=0, fetch=manifest)
        self.cookie = ''

    def tearDown(self):
        self.server.close()
        self.temp.cleanup()

    def request(self, path, data=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.port, timeout=4)
        headers = {'Cookie': self.cookie}
        body = None
        if data is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(data)
        connection.request('POST' if data is not None else 'GET', path, body, headers)
        response = connection.getresponse()
        raw, cookie, code = response.read(), response.getheader('Set-Cookie'), response.status
        connection.close()
        return code, raw, cookie

    def pair(self):
        status, _, cookie = self.request('/api/pair', {'code': self.server.code})
        self.assertEqual(status, 200)
        self.cookie = cookie.split(';')[0]

    def test_categories_respect_live_overrides_and_shared_sources(self):
        self.assertEqual(source_sections(self.entry), ['movies', 'series'])
        self.assertEqual(source_sections(dict(self.entry, live_group='sports')), ['live'])
        self.assertEqual(source_sections(dict(self.entry, kind='m3u')), ['live'])
        self.assertEqual(source_sections(dict(self.entry, manifest={'types':['movie']})), ['movies'])
        self.assertEqual(source_sections(dict(self.entry, manifest={'types':['series']})), ['series'])
        self.assertEqual(source_sections(dict(self.entry, manifest={'types':['tv']})), ['live'])

    def test_paired_listing_is_read_only_and_keeps_disabled_sources(self):
        self.assertEqual(self.request('/api/sources')[0], 401)
        self.pair()
        before = self.store.providers()
        status, raw, _ = self.request('/api/sources')
        rows = json.loads(raw)['sources']
        self.assertEqual(status, 200)
        self.assertEqual(rows[0]['sections'], ['movies', 'series'])
        self.assertFalse(rows[0]['enabled'])
        self.assertEqual(before, self.store.providers())

    def test_edit_replaces_one_shared_source_without_losing_options(self):
        self.pair()
        status, raw, _ = self.request('/api/save', {'key': self.entry['key'], 'label': 'Shared fixture',
                 'url': 'https://fixture.example/new/manifest.json', 'group': '', 'enabled': False, 'guide_country': ''})
        self.assertEqual(status, 200, raw)
        rows = self.store.providers()
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['enabled'])
        self.assertEqual(rows[0]['custom_option'], 'keep-me')
        self.assertEqual(source_sections(rows[0]), ['movies', 'series'])

    def test_all_static_controls_still_exist_once(self):
        import re
        html = (STAGE / 'resources/setup/index.html').read_text(encoding='utf-8')
        script = (STAGE / 'resources/setup/setup.js').read_text(encoding='utf-8')
        ids = re.findall(r'\bid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)))
        referenced = set(re.findall(r"\$\('([^']+)'\)", script))
        self.assertTrue(referenced.issubset(ids), referenced - set(ids))
        self.assertEqual(html.count('role="tabpanel"'), 6)
        self.assertEqual(html.count('role="tab"'), 6)

    def test_native_category_navigation_filters_the_same_sources(self):
        addon = ast.parse((STAGE / 'addon.py').read_text(encoding='utf-8-sig'))
        functions = [n for n in addon.body if isinstance(n, ast.FunctionDef) and n.name in ('manage', 'command_setup')]
        emitted = []
        values = {'STORE': self.store, 'HANDLE': 1,
                  'xbmcplugin': types.SimpleNamespace(setPluginCategory=lambda *a: None),
                  'item': lambda label, action, **kwargs: emitted.append((label, action, kwargs)),
                  'finish': lambda: None}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<native menu>', 'exec'), values)
        values['command_setup']()
        self.assertEqual([r[0] for r in emitted[:6]], ['Live TV sources', 'Movie sources', 'TV Series sources',
                         'Channel Listings / numbers and groups', 'Programmes / guide feeds', 'Tools / updates, backup and repair'])
        emitted.clear()
        values['manage']('movies')
        self.assertTrue(any(r[0] == 'OFF  Shared fixture' for r in emitted))
        self.assertTrue(all(r[2].get('category') == 'movies' for r in emitted if r[1] == 'provider'))
        emitted.clear()
        values['manage']('live')
        self.assertFalse(any(r[1] == 'provider' for r in emitted))


if __name__ == '__main__':
    unittest.main(verbosity=2)
