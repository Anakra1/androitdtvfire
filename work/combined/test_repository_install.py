"""Validate the Kodi HTTP listing and complete Android install dependency graph."""
import hashlib
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

PROJECT = Path(__file__).resolve().parents[2]


class RepositoryInstallTests(unittest.TestCase):
    def test_source_listing_matches_kodis_http_directory_parser(self):
        html = (PROJECT / 'index.html').read_text(encoding='utf-8-sig')
        # Exact item expression used by Kodi's HTTPDirectory.cpp; intentionally
        # no DOTALL flag, so each entry is also valid without multiline matching.
        pattern = re.compile(r'<a href="([^"]*)"[^>]*>\s*(.*?)\s*</a>(.+?)(?=<a|</tr|$)', re.I)
        entries = [link for link, name, _ in pattern.findall(html) if link.rstrip('/') == name.strip().rstrip('/')]
        self.assertEqual(entries, ['repository.cbr.zip', 'windowsrepo.zip', 'cbr095.zip', 'cbrwindows.zip'])
        for entry in entries:
            self.assertTrue((PROJECT / entry).is_file())
        self.assertEqual((PROJECT / 'cbr095.zip').read_bytes(),
                         (PROJECT / 'android/packages/plugin.video.stremio.bridge/plugin.video.stremio.bridge-0.9.5.zip').read_bytes())

    def test_windows_repository_keeps_the_windows_player_in_future_updates(self):
        with ZipFile(PROJECT / 'windowsrepo.zip') as archive:
            manifest = ET.fromstring(archive.read('repository.crb.windows/addon.xml'))
        directory = manifest.find("extension[@point='xbmc.addon.repository']/dir")
        self.assertEqual(directory.findtext('info'), 'https://anakra1.github.io/androitdtvfire/windows/addons.xml')
        self.assertEqual(directory.findtext('datadir'), 'https://anakra1.github.io/androitdtvfire/windows/packages/')
        feed = PROJECT / 'windows/addons.xml'
        self.assertEqual(hashlib.md5(feed.read_bytes()).hexdigest(), (PROJECT / 'windows/addons.xml.md5').read_text().strip())
        for item in ET.parse(feed).getroot():
            package = PROJECT / 'windows/packages' / item.get('id') / '{}-{}.zip'.format(item.get('id'), item.get('version'))
            self.assertTrue(package.is_file())
        video = PROJECT / 'windows/packages/plugin.video.stremio.bridge/plugin.video.stremio.bridge-0.9.5.zip'
        self.assertEqual(video.read_bytes(), (PROJECT / 'cbrwindows.zip').read_bytes())
        with ZipFile(video) as archive:
            self.assertTrue(archive.read('plugin.video.stremio.bridge/resources/bin/windows-x64/TorrServer.exe').startswith(b'MZ'))
            packaged = ET.fromstring(archive.read('plugin.video.stremio.bridge/addon.xml'))
            self.assertEqual(packaged.find("extension[@point='xbmc.addon.metadata']/platform").text, 'windows')
            self.assertEqual([r.get('addon') for r in packaged.find('requires')], ['xbmc.python'])
        listed = ET.parse(feed).getroot().find("addon[@id='plugin.video.stremio.bridge']")
        self.assertEqual(ET.tostring(listed), ET.tostring(packaged))
        self.assertIsNone(ET.parse(feed).getroot().find("addon[@id='script.module.cbr.engine']"))

    def test_repository_installs_video_and_embedded_engine_from_one_feed(self):
        with ZipFile(PROJECT / 'repository.cbr.zip') as repository:
            manifest = ET.fromstring(repository.read('repository.crb.android/addon.xml'))
        self.assertEqual(manifest.attrib['version'], '0.1.7')
        self.assertFalse(manifest.findall("extension[@point='xbmc.service']"))
        directory = manifest.find("extension[@point='xbmc.addon.repository']/dir")
        self.assertEqual(directory.findtext('info'), 'https://anakra1.github.io/androitdtvfire/android/addons.xml')
        feed = PROJECT / 'android/addons.xml'
        self.assertEqual(hashlib.md5(feed.read_bytes()).hexdigest(),
                         (PROJECT / 'android/addons.xml.md5').read_text().strip())
        addons = {item.attrib['id']: item for item in ET.parse(feed).getroot()}
        video = addons['plugin.video.stremio.bridge']
        self.assertEqual(video.attrib['version'], '0.9.5')
        requirements = {item.attrib['addon']: item.attrib.get('version') for item in video.find('requires')}
        self.assertEqual(requirements['script.module.cbr.engine'], '0.1.0')
        self.assertEqual(video.find("extension[@point='xbmc.addon.metadata']/platform").text, 'android')
        for addon_id, item in addons.items():
            archive = PROJECT / 'android/packages' / addon_id / '{}-{}.zip'.format(addon_id, item.attrib['version'])
            with ZipFile(archive) as package:
                self.assertIsNone(package.testzip())
                packaged = ET.fromstring(package.read(addon_id + '/addon.xml'))
                self.assertEqual(packaged.attrib['version'], item.attrib['version'])
                if addon_id == 'plugin.video.stremio.bridge':
                    player = package.read(addon_id + '/torrent_player.py').decode()
                    engine = package.read(addon_id + '/engine.py').decode()
                    self.assertNotIn('StartAndroidActivity', player + engine)
                    self.assertNotIn('CBR Kodi Companion', player + engine)
                if addon_id == 'script.module.cbr.engine':
                    checksums = json.loads(package.read(addon_id + '/resources/checksums.json'))
                    for arch, expected in checksums.items():
                        raw = package.read(addon_id + '/resources/lib/' + arch + '/libcbrengine.so')
                        self.assertEqual(raw[:4], b'\x7fELF')
                        self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
