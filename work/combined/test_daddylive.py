from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / 'plugin.video.stremio.bridge'))
from resources.lib import daddylive as daddy, pvr
from resources.lib.core import Store, aggregate, load_manifest

PAGE = '''<a class="card" href="watch.php?id=362" data-title="sky atlantic"></a>
<a class="card" href="watch.php?id=1" data-title="sky sports football uk"></a>
<a class="card" href="watch.php?id=2" data-title="sky sport 1 nz"></a>
<a class="card" href="watch.php?id=3" data-title="18+ channel"></a>
<a class="card" href="watch.php?id=362" data-title="duplicate"></a>'''


class DaddyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        daddy._cache.clear()

    def test_catalogue_separates_uk_from_unknown_countries_and_filters_adult_duplicates(self):
        entry = self.store.add(daddy.DEFAULT_URL)
        with patch.object(daddy.decoders, 'fetch_page', return_value=PAGE) as fetch:
            uk = daddy.resource(entry, 'catalog', 'tv', 'daddy_uk')['metas']
            all_rows = daddy.resource(entry, 'catalog', 'tv', 'daddy_all')['metas']
            self.assertEqual(fetch.call_count, 1)
        self.assertEqual([m['id'] for m in uk], ['daddy.362', 'daddy.1'])
        self.assertEqual(len(all_rows), 3)
        self.assertEqual(uk[0]['country'], 'GB')
        self.assertEqual(all_rows[-1]['country'], '')

    def test_resolves_fresh_each_play_and_ignores_bad_or_proxy_dependent_players(self):
        entry = self.store.add(daddy.DEFAULT_URL)
        watch = ('<button data-url="/player/362" title="Player 6">'
                 '<button data-url="/watch/362" title="Player 3">'
                 '<button data-url="/plus/362" title="Player 4">')
        with patch.object(daddy.decoders, 'fetch_page', return_value=watch), \
             patch.object(daddy.decoders, 'resolve_player', side_effect=[('https://example.org/one.m3u8','https://example.org/'), ('https://example.org/two.m3u8','https://example.org/')]), \
             patch.object(daddy.decoders, 'resolve_watch', return_value=('https://example.org/needs-renewal.m3u8','https://example.org/','https://example.org/token')), \
             patch.object(daddy.decoders, 'resolve_plus', side_effect=RuntimeError('private-token')):
            first = aggregate([entry], 'stream', 'tv', 'daddy.362')[0][1]['streams']
            second = aggregate([entry], 'stream', 'tv', 'daddy.362')[0][1]['streams']
        self.assertEqual([s['url'] for s in first], ['https://example.org/one.m3u8'])
        self.assertEqual([s['url'] for s in second], ['https://example.org/two.m3u8'])
        self.assertEqual(first[0]['behaviorHints']['proxyHeaders']['request']['Referer'], 'https://example.org/')
        self.assertFalse(any('one.m3u8' in p.read_text() for p in Path(self.temp.name).rglob('*.json')))

    def test_one_time_migration_keeps_choices_and_export_has_stable_routes(self):
        pvr.save_config(self.store, dict(enabled=True, selected=[], overrides={}))
        with patch.object(daddy.decoders, 'fetch_page', side_effect=AssertionError('migration must be offline')):
            daddy.ensure_default(self.store)
        entry = self.store.providers()[0]
        choice = next(s for s in pvr.sources(self.store) if s['default'])
        self.assertEqual(pvr.config(self.store)['selected'], [choice['key']])
        with patch.object(daddy.decoders, 'fetch_page', return_value=PAGE):
            variants = pvr.collect_source(self.store, choice)
        self.store.write(str(Path(self.temp.name)/'pvr-channels.json'), pvr.merge_channels(variants))
        pvr.export(self.store)
        playlist = (Path(self.temp.name)/'pvr/channels.m3u').read_text()
        self.assertIn('action=pvr_play', playlist)
        self.assertNotIn('thedaddy.li', playlist)
        value = pvr.config(self.store); value['selected'] = []; pvr.save_config(self.store, value)
        daddy.ensure_default(self.store)
        self.assertEqual(pvr.config(self.store)['selected'], [])

    def test_input_validation_and_provider_failures_do_not_execute_pages(self):
        self.assertEqual(daddy.resolve(daddy.DEFAULT_URL, 'daddy../bad'), [])
        self.assertEqual(load_manifest(daddy.DEFAULT_URL)['id'], daddy.IDENTITY)
        with patch.object(daddy.decoders, 'fetch_page', return_value='<html>no catalogue</html>'):
            with self.assertRaises(ValueError): daddy.catalogue(daddy.DEFAULT_URL)

    def test_preferred_player_avoids_slow_players_and_fails_over_if_blocked(self):
        page = '<button data-url="/player/362" title="PLAYER 6"><button data-url="/cast/362" title="PLAYER 2">'
        good = ('https://example.org/good.m3u8','https://example.org/')
        with patch.object(daddy.decoders,'fetch_page',return_value=page), \
             patch.object(daddy.decoders,'resolve_player',return_value=good), \
             patch.object(daddy.decoders,'resolve_cast',return_value=('https://example.org/backup.m3u8','https://example.org/')) as backup, \
             patch('resources.lib.live_player.probe_stream',return_value=True):
            self.assertEqual(daddy.resolve(daddy.DEFAULT_URL,'daddy.362','DaddyLive / PLAYER 6')[0]['url'],good[0])
            backup.assert_not_called()
        with patch.object(daddy.decoders,'fetch_page',return_value=page), \
             patch.object(daddy.decoders,'resolve_player',return_value=good), \
             patch.object(daddy.decoders,'resolve_cast',return_value=('https://example.org/backup.m3u8','https://example.org/')), \
             patch('resources.lib.live_player.probe_stream',return_value=False):
            self.assertEqual(daddy.resolve(daddy.DEFAULT_URL,'daddy.362','DaddyLive / PLAYER 6')[0]['url'],'https://example.org/backup.m3u8')


if __name__ == '__main__': unittest.main()
