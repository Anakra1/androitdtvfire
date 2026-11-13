import gzip
import io
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))
from resources.lib.core import Store
from resources.lib import programmes as epg

NOW = epg.timestamp('20261112123000 +0000')
XML = '''<tv>
<channel id="atlantic.uk"><display-name>Sky Atlantic HD</display-name></channel>
<channel id="atlanticplus.uk"><display-name>Sky Atlantic+1</display-name></channel>
<channel id="examplehd.uk"><display-name>Example HD</display-name></channel>
<channel id="examplesd.uk"><display-name>Example SD</display-name></channel>
<programme channel="atlantic.uk" start="20261112120000 +0000" stop="20261112130000 +0000"><title>Current show</title><desc>Current synopsis</desc></programme>
<programme channel="atlantic.uk" start="20261112130000 +0000" stop="20261112140000 +0000"><title>Next show</title></programme>
<programme channel="atlanticplus.uk" start="20261112120000 +0000" stop="20261112130000 +0000"><title>Timeshifted show</title></programme>
</tv>'''


class ProgrammeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.feed = dict(key='uk', country='GB', label='UK', url='https://example.org/guide.xml.gz', enabled=True)
        epg.save_settings(self.store, dict(enabled=True, feeds=[self.feed], mappings={}))
        self.xml = Path(self.temp.name) / 'guide.xml'
        self.xml.write_text(XML, encoding='utf-8')
        epg.import_xml(self.store, self.feed, self.xml, now=NOW)
        self.entry = self.store.add('https://example.org/manifest.json', fetch=lambda url:
            dict(id='live.fixture', name='TV', version='1', resources=['meta', 'stream'], types=['tv'], catalogs=[]))
        self.channel = dict(provider=self.entry['key'], provider_id='live.fixture', resource_type='tv', live_group='tv',
                            meta=dict(id='vavoo_SKY%20ATLANTIC|group:uk', type='tv', name='SKY ATLANTIC'))
        self.guide = epg.ProgrammeGuide(self.store)
        self.addCleanup(self.guide.close)

    def test_now_next_exact_boundaries_and_timezone_offsets(self):
        self.assertEqual(epg.timestamp('20261025013000 +0100') + 3600, epg.timestamp('20261025013000 +0000'))
        self.assertEqual(epg.timestamp('20261112123000 +0000'), epg.timestamp('2026-11-12T12:30:00Z'))
        self.assertIsNone(epg.timestamp('2026-11-12T12:30:00'))
        with patch.object(epg.time, 'time', return_value=NOW):
            result = self.guide.lookup(self.channel)
        self.assertEqual(result['now']['title'], 'Current show')
        self.assertEqual(result['next']['title'], 'Next show')
        self.assertIn('Current synopsis', epg.programme_text(result))
        boundary = epg.now_next([result['now'], result['next']], result['now']['stop'])
        self.assertEqual(boundary['now']['title'], 'Next show')

    def test_quality_suffix_is_allowed_but_timeshifts_and_countries_are_not_guessed(self):
        with patch.object(epg.time, 'time', return_value=NOW):
            shifted = dict(self.channel, meta=dict(self.channel['meta'], name='SKY ATLANTIC+1'))
            self.assertEqual(self.guide.lookup(shifted)['now']['title'], 'Timeshifted show')
        foreign = dict(self.channel, meta=dict(self.channel['meta'], id='vavoo_SKY%20ATLANTIC|group:it'))
        self.assertIsNone(self.guide.match(foreign))
        ambiguous = dict(self.channel, meta=dict(self.channel['meta'], name='Example'))
        self.assertIsNone(self.guide.match(ambiguous))

    def test_manual_mapping_survives_provider_url_change_and_can_be_reset(self):
        channel = dict(self.channel, meta=dict(self.channel['meta'], name='Example'))
        self.guide.map_channel(channel, dict(feed='uk', channel='atlantic.uk'))
        self.assertEqual(self.guide.match(channel), ('uk', 'atlantic.uk'))
        other = self.store.add('https://example.org/new/manifest.json', fetch=lambda url: self.entry['manifest'])
        self.assertEqual(self.guide.match(dict(channel, provider=other['key'])), ('uk', 'atlantic.uk'))
        self.guide.map_channel(channel, None)
        self.assertIsNone(self.guide.match(channel))

    def test_uk_abbreviations_and_spacing_match_without_guessing_regions_or_rebrands(self):
        names = ['SkySp Cricket HD', 'SkySpMainEvHD', '5ACTION', 'BBC One Lon HD',
                 'BBC One Wal HD', 'Sky Action HD', 'Cartoon Net HD']
        xml = '<tv>' + ''.join('<channel id="c{}"><display-name>{}</display-name></channel>'.format(i, n)
                               for i, n in enumerate(names)) + '</tv>'
        # Keep one programme so the import is a valid complete feed.
        xml = xml.replace('</tv>', '<programme channel="c0" start="20261112120000 +0000" stop="20261112130000 +0000"><title>Cricket</title></programme></tv>')
        self.xml.write_text(xml, encoding='utf8'); epg.import_xml(self.store, self.feed, self.xml, now=NOW)
        expected = [('Sky Sports Cricket', 'c0'), ('Sky Sports Main Event', 'c1'), ('5 ACTION', 'c2'),
                    ('BBC One London', 'c3'), ('BBC One Wales', 'c4'), ('Sky Cinema Action', 'c5'),
                    ('Cartoon Network', 'c6')]
        for name, identity in expected:
            channel = dict(self.channel, meta=dict(self.channel['meta'], name=name))
            self.assertEqual(self.guide.match(channel), ('uk', identity), name)
        for name in ['BBC One', 'BBC One Northern Ireland', 'Sky Sports Cricket+1', 'BT Sport 1']:
            self.assertIsNone(self.guide.match(dict(self.channel, meta=dict(self.channel['meta'], name=name))), name)
        foreign = dict(self.channel, meta=dict(self.channel['meta'], name='5 ACTION', country='IT', id='foreign.it'))
        self.assertIsNone(self.guide.match(foreign))

    def test_ambiguous_quality_matches_require_identical_nonempty_upcoming_schedules(self):
        db = self.guide.database()
        channel = dict(self.channel, meta=dict(self.channel['meta'], name='Example'))
        self.assertIsNone(self.guide.match(channel))
        for identity in ('examplehd.uk', 'examplesd.uk'):
            db.execute('INSERT INTO programmes VALUES(?,?,?,?,?,?)', ('uk', identity, NOW-100, NOW+100, 'Same show', ''))
        db.commit()
        with patch.object(epg.time, 'time', return_value=NOW):
            self.assertIsNotNone(self.guide.match(channel))
            db.execute('UPDATE programmes SET title=? WHERE channel=?', ('Different regional show', 'examplesd.uk')); db.commit()
            self.assertIsNone(self.guide.match(channel))

    def test_failed_or_empty_import_keeps_last_working_schedule(self):
        for data in ('<tv><programme', '<tv></tv>'):
            self.xml.write_text(data)
            with self.assertRaises((ValueError, epg.ET.ParseError)):
                epg.import_xml(self.store, self.feed, self.xml, now=NOW)
            with patch.object(epg.time, 'time', return_value=NOW):
                self.assertEqual(self.guide.lookup(self.channel)['now']['title'], 'Current show')

    def test_expired_programmes_are_not_shown_as_current(self):
        with patch.object(epg.time, 'time', return_value=NOW + 86400):
            result = self.guide.lookup(self.channel)
        self.assertIsNone(result['now'])
        self.assertIsNone(result['next'])

    def test_native_provider_schedule_works_without_a_country_match(self):
        meta = dict(self.channel['meta'], videos=[dict(title='Native show', overview='Synopsis',
            startTime='2026-11-12T12:00:00Z', endTime='2026-11-12T13:00:00Z')])
        with patch.object(epg.time, 'time', return_value=NOW):
            self.assertEqual(self.guide.lookup(self.channel, meta)['now']['title'], 'Native show')
        remembered = dict(self.channel, native_schedule=epg.provider_programmes(meta))
        with patch.object(epg.time, 'time', return_value=NOW):
            self.assertEqual(self.guide.lookup(remembered)['now']['title'], 'Native show')

    def test_two_same_country_feeds_have_stable_priority_without_disabling_matching(self):
        secondary = dict(self.feed, key='secondary', label='Another UK feed')
        epg.import_xml(self.store, secondary, self.xml, now=NOW)
        epg.save_settings(self.store, dict(enabled=True, feeds=[self.feed, secondary], mappings={}))
        guide = epg.ProgrammeGuide(self.store)
        self.addCleanup(guide.close)
        self.assertEqual(guide.match(self.channel), ('uk', 'atlantic.uk'))

    def test_gzip_download_import_and_entity_rejection_preserve_existing_data(self):
        with patch.object(epg, 'urlopen', return_value=io.BytesIO(gzip.compress(XML.encode()))), \
             patch.object(epg.time, 'time', return_value=NOW):
            result = epg.download_feed(self.store, self.feed, threading.Event())
        self.assertEqual(result['programmes'], 3)
        payload = b'<!DOCTYPE tv [<!ENTITY bad "secret">]><tv></tv>'
        with patch.object(epg, 'urlopen', return_value=io.BytesIO(gzip.compress(payload))):
            with self.assertRaises(ValueError):
                epg.download_feed(self.store, self.feed, threading.Event())
        self.assertEqual(list((Path(self.temp.name) / 'programme-downloads').iterdir()), [])
        with patch.object(epg.time, 'time', return_value=NOW):
            self.assertEqual(self.guide.lookup(self.channel)['now']['title'], 'Current show')

    def test_feed_url_edit_preserves_manual_channel_matches(self):
        self.guide.map_channel(self.channel, dict(feed='uk', channel='atlantic.uk'))
        epg.save_feed(self.store, dict(key='uk', url='https://example.org/new.xml.gz', label='UK', country='GB'))
        config = epg.settings(self.store)
        self.assertEqual(config['mappings'][epg.channel_key(self.channel)]['feed'], epg.feed_key('https://example.org/new.xml.gz'))

    def test_playing_information_refresh_never_starts_or_interrupts_video(self):
        url = 'https://example.org/live.m3u8'
        active = dict(channel=self.channel, fingerprint=hashlib.sha256(url.encode()).hexdigest())
        self.store.write(os.path.join(self.temp.name, 'live-playing.json'), active)
        player, make_item = MagicMock(), MagicMock()
        player.isPlayingVideo.return_value = True
        player.getPlayingFile.return_value = url
        monitor = epg.ProgrammePlaybackInfo(self.store)
        monitor.poll(player, make_item)
        player.updateInfoTag.assert_called_once_with(make_item.return_value)
        player.play.assert_not_called()
        monitor.last_poll = 0
        player.getPlayingFile.return_value = 'https://other.example/another-video'
        monitor.poll(player, make_item)
        self.assertEqual(self.store.read(os.path.join(self.temp.name, 'live-playing.json')), {})
        self.assertEqual(player.updateInfoTag.call_count, 1)

    def test_updater_downloads_in_background_and_preserves_status_on_failure(self):
        updater = epg.ProgrammeUpdater(self.store)
        self.addCleanup(updater.close)
        entered, release = threading.Event(), threading.Event()
        def download(*args):
            entered.set()
            release.wait(2)
            return dict(updated=NOW, state='ready', channels=4, programmes=3)
        with patch.object(epg, 'download_feed', side_effect=download):
            updater.poll()
            self.assertTrue(entered.wait(1))
            self.assertTrue(updater.thread.is_alive())
            release.set()
            updater.thread.join(2)
        with patch.object(epg, 'download_feed', side_effect=ValueError('private-url')):
            updater.refresh([self.feed])
        status = self.store.read(os.path.join(self.temp.name, 'programme-status.json'))['uk']
        self.assertEqual(status['updated'], NOW)
        self.assertEqual(status['state'], 'error')
        self.assertNotIn('private-url', str(status))
