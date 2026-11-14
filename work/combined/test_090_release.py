from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import subprocess
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
BASE = 'https://anakra1.github.io/androitdtvfire/'
ADDON = 'plugin.video.stremio.bridge'


class BaselineTests(unittest.TestCase):
    def test_runtime_is_original_090_and_only_old_configured_sources_are_present(self):
        original = subprocess.check_output(['git','show','05f482f:downloads/Windows/' + ADDON + '-0.9.0.zip'],cwd=ROOT)
        with ZipFile(BytesIO(original)) as old:
            for short, platform in [('a','android'),('w','windows')]:
                with ZipFile(ROOT/(short+'090.zip')) as package:
                    self.assertIsNone(package.testzip())
                    for name in old.namelist():
                        if name.endswith('.py'): self.assertEqual(package.read(name),old.read(name),name)
                    manifest=ET.fromstring(package.read(ADDON+'/addon.xml'))
                    self.assertEqual(manifest.get('version'),'0.9.0')
                    self.assertEqual(manifest.find("extension[@point='xbmc.addon.metadata']/platform").text,platform)
                    dependencies={r.get('addon') for r in manifest.find('requires')}
                    self.assertEqual('script.module.cbr.engine' in dependencies,platform=='android')
                    self.assertEqual(any(n.endswith('TorrServer.exe') for n in package.namelist()),platform=='windows')
                    live=json.loads(package.read(ADDON+'/resources/defaults/live-providers.json'))
                    self.assertEqual([p['label'] for p in live],['MediaFusion TV','Pluto TV','Sports Streams','TvVoo | ElfHosted'])
                    old_live=json.loads(old.read(ADDON+'/resources/defaults/live-providers.json'))
                    self.assertEqual(live[:3],old_live)
                    self.assertEqual(live[-1]['url'],'https://tvvoo.stremio-italia.eu/cfg-it-uk-fr-de-pt-es-al-tr-nl-ar-bk-ru-ro-pl-bg/manifest.json')
                    self.assertFalse(any(n.endswith(('/daddylive.py','/m3u.py','/live_hints.py')) for n in package.namelist()))

    def test_frozen_repositories_resolve_complete_dependency_graph_without_newer_video(self):
        for short,platform in [('a','android'),('w','windows')]:
            with ZipFile(ROOT/(short+'090repo.zip')) as package:
                repository=ET.fromstring(package.read('repository.cbr090.'+platform+'/addon.xml'))
            available={}
            for directory in repository.findall("extension[@point='xbmc.addon.repository']/dir"):
                info=directory.findtext('info');self.assertIn('/090/'+platform+'/',info)
                path=ROOT/info.removeprefix(BASE);raw=path.read_bytes()
                self.assertEqual(hashlib.md5(raw).hexdigest(),(ROOT/directory.findtext('checksum').removeprefix(BASE)).read_text())
                for addon in ET.fromstring(raw):
                    identity=addon.get('id');version=addon.get('version')
                    if identity==ADDON:self.assertEqual(version,'0.9.0')
                    available[identity]=addon
                    filename=identity+'/'+identity+'-'+version+'.zip'
                    path=ROOT/(directory.findtext('datadir').removeprefix(BASE)+filename)
                    self.assertTrue(path.is_file(),str(path))
                    with ZipFile(path) as archive:
                        self.assertEqual(ET.fromstring(archive.read(identity+'/addon.xml')).get('version'),version)
            self.assertEqual(set(available),{ADDON,'script.crb.wizard','skin.crimsonbloodrequiem'} |
                             ({'script.module.cbr.engine'} if platform=='android' else set()))
            for addon in available.values():
                for dependency in addon.find('requires'):
                    if dependency.get('addon').startswith('xbmc.'):continue
                    supplied=available[dependency.get('addon')]
                    numeric=lambda s:tuple(int(x) for x in s.split('.'))
                    self.assertGreaterEqual(numeric(supplied.get('version')),numeric(dependency.get('version','0')))


if __name__=='__main__':unittest.main()
