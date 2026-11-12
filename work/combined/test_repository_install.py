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
        self.assertEqual(entries, ['repository.cbr.zip'])
        self.assertTrue((PROJECT / entries[0]).is_file())

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
        self.assertEqual(video.attrib['version'], '0.6.2')
        requirements = {item.attrib['addon']: item.attrib.get('version') for item in video.find('requires')}
        self.assertEqual(requirements['script.module.cbr.engine'], '0.1.0')
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
