from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))
from resources.lib import pvr, programmes, m3u, daddylive
from resources.lib.core import Store
from test_programmes import XML, NOW
import test_movies as fixtures


class PVRTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.manifest = dict(id='org.tv.fixture', name='TV', version='1', resources=['catalog', 'meta', 'stream'], types=['tv'],
                             catalogs=[dict(id='tv_uk', type='tv', name='UK')])
        self.entry = self.store.add('https://example.org/private-token/manifest.json', fetch=lambda url: self.manifest)
        self.variant = dict(provider=self.entry['key'], provider_id=self.manifest['id'], provider_label=self.entry['label'],
                            resource_type='tv', live_country='GB', live_group='tv',
                            meta=dict(id='sky', type='tv', name='Sky Atlantic HD', logo='https://example.org/logo.png'))

    def test_default_source_selection_excludes_movies_and_retains_configuration_query(self):
        options = pvr.sources(self.store)
        self.assertEqual(len(options), 1)
        self.assertTrue(options[0]['default'])
        seen = []
        rows = pvr.collect_source(self.store, options[0], fetch=lambda url: seen.append(url) or {'metas': [self.variant['meta']]})
        self.assertEqual(rows[0]['live_country'], 'GB')
        self.assertIn('/private-token/catalog/tv/tv_uk.json', seen[0])

    def test_duplicate_channels_keep_alternatives_and_stable_numbers_across_rebuild(self):
        plain = dict(self.variant, meta=dict(self.variant['meta'], id='sd', name='Sky Atlantic'))
        shifted = dict(self.variant, meta=dict(self.variant['meta'], id='plus', name='Sky Atlantic+1'))
        rows = pvr.merge_channels([plain, self.variant, shifted])
        self.assertEqual(len(rows), 2)
        main = next(r for r in rows if len(r['variants']) == 2)
        self.assertEqual(main['variants'][0]['meta']['name'], 'Sky Atlantic HD')
        new = dict(self.variant, meta=dict(self.variant['meta'], id='new', name='A new channel'))
        updated = pvr.merge_channels([new, plain, self.variant, shifted], previous=rows)
        self.assertEqual(next(r for r in updated if r['id'] == main['id'])['number'], main['number'])

    def test_mediafusion_cinema_alias_keeps_existing_route_and_distinct_channels(self):
        old = dict(self.variant, meta=dict(id='old', name='Sky Premiere HD', type='tv'))
        media = dict(self.variant, provider_id='mediafusion', meta=dict(id='new', name='Sky Cinema Premiere', type='tv'))
        previous = pvr.merge_channels([old]); previous[0]['number'] = 410
        shifted = dict(media, meta=dict(media['meta'], id='plus', name='Sky Cinema Premiere+1'))
        foreign = dict(media, live_country='IT')
        rows = pvr.merge_channels([old, media, shifted, foreign], previous)
        self.assertEqual(len(rows), 3)
        main = next(r for r in rows if len(r['variants']) == 2)
        self.assertEqual((main['id'], main['number']), (previous[0]['id'], 410))

    def test_mediafusion_migration_adds_uk_sources_once_without_replacing_private_url(self):
        mf = dict(self.manifest, id='stremio.addons.mediafusion|elfhosted', catalogs=[])
        entry = self.store.add('https://example.org/configured/manifest.json', fetch=lambda url: mf)
        entries = self.store.providers()
        next(e for e in entries if e['key'] == entry['key'])['scope_types'] = ['tv']
        self.store.save_providers(entries)
        original = pvr.sources(self.store)[0]['key']
        pvr.save_config(self.store, dict(enabled=True, selected=[original], overrides={}))
        pvr.ensure_mediafusion_fallbacks(self.store, str(ROOT))
        selected = pvr.config(self.store)['selected']
        self.assertIn(original, selected)
        self.assertTrue(any(s['provider'] == entry['key'] and s['key'] in selected for s in pvr.sources(self.store)))
        self.assertEqual(self.store.provider(entry['key'])['url'], entry['url'])
        value = pvr.config(self.store); value['selected'] = [original]; pvr.save_config(self.store, value)
        pvr.ensure_mediafusion_fallbacks(self.store, str(ROOT))
        self.assertEqual(pvr.config(self.store)['selected'], [original])

    def test_mediafusion_migration_respects_disabled_and_movie_only_sources(self):
        for enabled, scope in [(False, ['tv']), (True, ['movie'])]:
            entry = self.store.add('https://example.org/' + str(enabled) + '/manifest.json',
                fetch=lambda url: dict(self.manifest, id='mediafusion.' + str(enabled), catalogs=[]))
            entries = self.store.providers()
            current = next(e for e in entries if e['key'] == entry['key'])
            current.update(enabled=enabled, scope_types=scope)
            self.store.save_providers(entries)
        pvr.save_config(self.store, dict(enabled=True, selected=[], overrides={}))
        pvr.ensure_mediafusion_fallbacks(self.store, str(ROOT))
        self.assertEqual(pvr.config(self.store)['selected'], [])

    def test_m3u_uses_non_expiring_plugin_routes_and_xmltv_ids_match(self):
        rows = pvr.merge_channels([self.variant])
        self.store.write(str(Path(self.temp.name) / 'pvr-channels.json'), rows)
        xml = Path(self.temp.name) / 'fixture.xml'; xml.write_text(XML)
        feed = dict(key='uk', country='GB', label='UK', enabled=True)
        programmes.save_settings(self.store, dict(enabled=True, feeds=[feed], mappings={}))
        programmes.import_xml(self.store, feed, xml, now=NOW)
        with patch.object(pvr.time, 'time', return_value=NOW):
            result = pvr.export(self.store)
        self.assertEqual(result['guide_channels'], 1)
        playlist = (Path(self.temp.name) / 'pvr/channels.m3u').read_text()
        self.assertIn('action=pvr_play', playlist)
        self.assertNotIn('private-token', playlist)
        self.assertNotIn('.m3u8', playlist)
        guide = ET.parse(Path(self.temp.name) / 'pvr/guide.xml').getroot()
        self.assertEqual(guide.find('channel').get('id'), rows[0]['id'])
        self.assertTrue(all(n.get('channel') == rows[0]['id'] for n in guide.findall('programme')))
        self.assertEqual(guide.find('programme/title').text, 'Current show')

    def test_spacing_duplicates_preserve_numbers_old_routes_and_manual_choices(self):
        a = dict(self.variant, meta=dict(self.variant['meta'], id='a', name='5 ACTION'))
        b = dict(self.variant, meta=dict(self.variant['meta'], id='b', name='5ACTION HD'))
        old_a = pvr.merge_channels([a])[0]; old_a['number'] = 104
        old_b = pvr.merge_channels([b])[0]; old_b['number'] = 205
        rows = pvr.merge_channels([a, b], [old_a, old_b])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], old_a['id'])
        self.assertEqual(rows[0]['number'], 104)
        self.store.write(str(Path(self.temp.name) / 'pvr-channels.json'), rows)
        self.assertEqual(pvr.channel(self.store, old_b['id'])[0]['id'], old_a['id'])
        override = {old_a['id']: dict(name='Action', number=900, groups=['Movies'], visible=False)}
        rebuilt = pvr.merge_channels([a, b], rows, override)
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0]['number'], 900)
        # Independently edited duplicates remain independent.
        overrides = {r['id']: dict(number=r['number']) for r in [old_a, old_b]}
        self.assertEqual(len(pvr.merge_channels([a, b], [old_a, old_b], overrides)), 2)

    def test_spacing_dedup_never_combines_countries_regions_or_timeshifts(self):
        variants = [dict(self.variant, meta=dict(self.variant['meta'], id=str(i), name=name), live_country=country)
                    for i, (name, country) in enumerate([('BBC One London', 'GB'), ('BBC One Wales', 'GB'),
                                                         ('BBC One London+1', 'GB'), ('BBC One London', 'IE')])]
        self.assertEqual(len(pvr.merge_channels(variants)), 4)

    def test_editor_can_map_all_alternatives_including_hidden_channels_and_reset(self):
        second = dict(self.variant, meta=dict(self.variant['meta'], id='second', name='Sky Atlantic'))
        rows = pvr.merge_channels([self.variant, second])
        self.store.write(str(Path(self.temp.name) / 'pvr-channels.json'), rows)
        xml = Path(self.temp.name) / 'fixture.xml'; xml.write_text(XML, encoding='utf8')
        feed = dict(key='uk', country='GB', label='UK', enabled=True)
        programmes.save_settings(self.store, dict(enabled=True, feeds=[feed], mappings={}))
        programmes.import_xml(self.store, feed, xml, now=NOW)
        pvr.save_channels(self.store, [dict(id=rows[0]['id'], name='Atlantic', number=150, groups=['Sky'], visible=False)])
        with self.assertRaises(ValueError):
            pvr.save_mapping(self.store, rows[0]['id'], dict(feed='bad', channel='bad'))
        pvr.save_mapping(self.store, rows[0]['id'], dict(feed='uk', channel='atlantic.uk'))
        value = programmes.settings(self.store)
        self.assertEqual(len(value['mappings']), 2)
        with patch.object(pvr.time, 'time', return_value=NOW):
            result = pvr.editor(self.store)
        row = result['channels'][0]
        self.assertFalse(row['visible'])
        self.assertTrue(row['has_programmes'])
        self.assertEqual(row['guide']['channel'], 'atlantic.uk')
        self.assertEqual(row['alternatives'], 2)
        pvr.save_mapping(self.store, rows[0]['id'], None)
        self.assertEqual(programmes.settings(self.store)['mappings'], {})

    def test_renaming_and_numbering_does_not_change_stream_identity_or_allow_collisions(self):
        second = dict(self.variant, meta=dict(self.variant['meta'], id='news', name='Sky News'))
        rows = pvr.merge_channels([self.variant, second])
        self.store.write(str(Path(self.temp.name) / 'pvr-channels.json'), rows)
        pvr.save_channels(self.store, [dict(id=rows[0]['id'], name='My Sky', number=900, groups=['Sky'], visible=True)])
        row, variants = pvr.channel(self.store, rows[0]['id'])
        self.assertEqual(row['name'], 'My Sky')
        self.assertEqual(variants[0]['meta']['id'], 'sky')
        with self.assertRaises(ValueError):
            pvr.save_channels(self.store, [dict(id=rows[1]['id'], name='News', number=900, groups=['News'], visible=True)])

    def test_manifest_url_replacement_keeps_channel_and_selected_source_valid(self):
        source = pvr.sources(self.store)[0]['key']
        rows = pvr.merge_channels([self.variant])
        self.store.write(str(Path(self.temp.name) / 'pvr-channels.json'), rows)
        updated = self.store.add('https://example.org/new-token/manifest.json', fetch=lambda url: self.manifest)
        self.store.save_providers([updated])
        self.assertEqual(pvr.sources(self.store)[0]['key'], source)
        self.assertEqual(pvr.channel(self.store, rows[0]['id'])[1][0]['provider'], updated['key'])

    def test_instance_configuration_preserves_other_instances_and_existing_custom_settings(self):
        profile = Path(self.temp.name) / 'iptv'; profile.mkdir()
        other = profile / 'instance-settings-1.xml'
        original = '<settings version="2"><setting id="kodi_addon_instance_name">Other TV</setting></settings>'
        other.write_text(original)
        path = pvr.configure_instance(str(profile), 'special://profile/cbr/channels.m3u', 'special://profile/cbr/guide.xml')
        root = ET.parse(path).getroot()
        ET.SubElement(root, 'setting', {'id': 'custom-option'}).text = 'keep'
        ET.ElementTree(root).write(path)
        self.assertEqual(pvr.configure_instance(str(profile), 'new.m3u', 'new.xml'), path)
        self.assertEqual(other.read_text(), original)
        values = {n.get('id'): n.text for n in ET.parse(path).getroot()}
        self.assertEqual(values['custom-option'], 'keep')
        self.assertEqual(values['m3uPathType'], '0')
        self.assertEqual(values['m3uPath'], 'new.m3u')

    def test_failed_refresh_keeps_last_working_channels_and_outputs(self):
        value = pvr.config(self.store); value['enabled'] = True; pvr.save_config(self.store, value)
        updater = pvr.PVRUpdater(self.store)
        updater.build(fetch=lambda url: {'metas': [self.variant['meta']]})
        path = Path(self.temp.name) / 'pvr/channels.m3u'; original = path.read_bytes()
        def fail(url): raise RuntimeError('secret-url')
        updater.build(fetch=fail)
        self.assertEqual(path.read_bytes(), original)
        status = self.store.read(str(Path(self.temp.name) / 'pvr-status.json'))
        self.assertEqual(len(status['failed']), 1)
        self.assertNotIn('secret-url', str(status))


class PVRRouteTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.ServerFixture.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.ServerFixture.tearDownClass.__func__)
    setUp = fixtures.KodiRouteTests.setUp
    restore_modules = fixtures.KodiRouteTests.restore_modules
    record_rpc = fixtures.KodiRouteTests.record_rpc
    follow = fixtures.KodiRouteTests.follow

    def test_pvr_channel_resolves_fresh_url_without_video_addon_retry_hijacking_pvr(self):
        variant = dict(provider=self.entry['key'], provider_id=self.entry['manifest']['id'], provider_label=self.entry['label'],
                       resource_type='tv', live_country='GB', live_group='tv', meta=dict(id='bbc', type='tv', name='BBC News'))
        rows = pvr.merge_channels([variant]); self.app.STORE.write(str(Path(self.temp.name) / 'pvr-channels.json'), rows)
        self.app.pvr_play(rows[0]['id'])
        self.assertTrue(self.resolved[-1][1])
        self.assertIn('https://example.org/video.mp4', self.resolved[-1][2].path)
        self.assertEqual(self.app.STORE.read(self.app.LIVE_AUTOPLAY.path), {})

    def test_reachable_m3u_alternative_wins_over_timed_out_manifest_source(self):
        rows = m3u.parse('#EXTM3U\n#EXTINF:-1 tvg-id="BBCNews.uk",BBC News\nhttps://example.org/fresh.m3u8', 'https://example.org/list.m3u')
        with patch.object(m3u, 'load', return_value=rows):
            entry = self.app.STORE.add('https://example.org/list.m3u')
            old = dict(provider=self.entry['key'], provider_id=self.entry['manifest']['id'], provider_label=self.entry['label'],
                       resource_type='tv', live_country='GB', live_group='tv', meta=dict(id='bbc', type='tv', name='BBC News HD'))
            new = dict(old, provider=entry['key'], provider_id=entry['manifest']['id'], provider_label=entry['label'],
                       meta={k:v for k,v in rows[0].items() if k!='streams'})
            merged = pvr.merge_channels([old, new]); self.app.STORE.write(str(Path(self.temp.name)/'pvr-channels.json'),merged)
            with patch.object(self.app, 'probe_stream', side_effect=lambda stream: True if stream['url'].endswith('fresh.m3u8') else None):
                self.app.pvr_play(merged[0]['id'])
        self.assertTrue(self.resolved[-1][1])
        self.assertIn('/fresh.m3u8',self.resolved[-1][2].path)

    def test_mediafusion_plays_after_both_primary_links_fail(self):
        mf = self.app.STORE.add('https://example.org/mediafusion/manifest.json',
            fetch=lambda url: dict(self.entry['manifest'], id='mediafusion', catalogs=[]))
        primary = dict(provider=self.entry['key'], provider_id=self.entry['manifest']['id'], provider_label=self.entry['label'],
                       resource_type='tv', live_country='GB', live_group='tv', meta=dict(id='old', type='tv', name='Sky Premiere HD'))
        backup = dict(primary, provider=mf['key'], provider_id=mf['manifest']['id'], provider_label=mf['label'],
                      meta=dict(id='new', type='tv', name='Sky Cinema Premiere'))
        rows = pvr.merge_channels([primary, backup])
        self.assertEqual(len(rows), 1)
        self.app.STORE.write(str(Path(self.temp.name)/'pvr-channels.json'),rows)
        def streams(entries, *args):
            urls = ['https://example.org/fail1.m3u8', 'https://example.org/fail2.m3u8'] if entries[0]['key'] == self.entry['key'] else ['https://example.org/backup.m3u8']
            return [(entries[0], {'streams':[{'url':url} for url in urls]}, None)]
        with patch.object(self.app, 'aggregate', side_effect=streams), patch.object(self.app,'probe_stream',
                side_effect=lambda s: s['url'].endswith('backup.m3u8')):
            self.app.pvr_play(rows[0]['id'])
        self.assertTrue(self.resolved[-1][1])
        self.assertIn('/backup.m3u8',self.resolved[-1][2].path)
        self.assertEqual(self.app.STORE.read(self.app.LIVE_AUTOPLAY.path), {})

    def test_m3u_backup_browsing_to_automatic_playback(self):
        rows = m3u.parse('#EXTM3U\n#EXTINF:-1 tvg-id="BBCNews.uk",BBC News\nhttps://example.org/fresh.m3u8', 'https://example.org/list.m3u')
        with patch.object(m3u, 'load', return_value=rows), patch.object(self.app,'probe_stream',return_value=True):
            entry = self.app.STORE.add('https://example.org/list.m3u')
            self.items.clear()
            self.app.catalog_page(entry['key'],self.app.STORE.put(entry['manifest']['catalogs'][0]))
            self.assertEqual(self.items[0][0][2].label,'BBC News')
            self.follow(0)
        self.assertTrue(self.resolved[-1][1])
        self.assertIn('/fresh.m3u8',self.resolved[-1][2].path)

    def test_daddylive_browsing_to_automatic_playback_without_source_picker(self):
        page = '<a class="card" href="watch.php?id=362" data-title="sky atlantic"></a>'
        daddylive._cache.clear()
        entry = self.app.STORE.add(daddylive.DEFAULT_URL)
        with patch.object(daddylive.decoders, 'fetch_page', return_value=page), \
             patch.object(daddylive, 'resolve', return_value=[{'url':'https://example.org/daddy-fresh.m3u8'}]), \
             patch.object(self.app, 'probe_stream', return_value=True):
            self.items.clear()
            self.app.catalog_page(entry['key'], self.app.STORE.put(entry['manifest']['catalogs'][0]))
            self.assertEqual(self.items[0][0][2].label, 'Sky Atlantic')
            self.follow(0)
        self.assertTrue(self.resolved[-1][1])
        self.assertIn('/daddy-fresh.m3u8', self.resolved[-1][2].path)
