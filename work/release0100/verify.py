"""Verify release archives, fresh profiles, upgrades and dependency closure."""
from pathlib import Path
from zipfile import ZipFile
import ast
import hashlib
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ADDON = 'plugin.video.stremio.bridge'
VERSION = '0.10.0'
prefix = ADDON + '/'
packages = {p: ROOT/p/'packages'/ADDON/f'{ADDON}-{VERSION}.zip' for p in ('windows','android')}
contents = {}
for platform, package in packages.items():
    with ZipFile(package) as archive:
        assert archive.testzip() is None
        contents[platform] = {name: archive.read(name) for name in archive.namelist()}
    files = contents[platform]
    root = ET.fromstring(files[prefix+'addon.xml'])
    assert root.get('version') == VERSION
    assert root.find("extension[@point='xbmc.addon.metadata']/platform").text == platform
    requirements = {i.get('addon'):i.get('version') for i in root.find('requires')}
    assert ('script.module.cbr.engine' in requirements) == (platform == 'android')
    assert any(name.endswith('TorrServer.exe') for name in files) == (platform == 'windows')
    for name, raw in files.items():
        assert name.startswith(prefix) and '..' not in Path(name).parts
        if name.endswith('.py'):ast.parse(raw.decode('utf-8-sig'),filename=name)
        if name.endswith('.json'):json.loads(raw.decode('utf-8-sig'))
        if name.endswith(('.py','.json','.md','.txt','.xml')):
            assert not re.search(rb'sports\.highfly\.(?:dev|to)/[0-9a-f]{8}-',raw),name
    defaults=json.loads(files[prefix+'resources/defaults/live-providers.json'])
    assert [x['label'] for x in defaults]==['Pluto TV','Samsung TV Plus UK','Sports Streams']
    assert not any('mediafusion' in n or 'tvvoo' in n for n in files if '/resources/defaults/'in n)
    feed_path=ROOT/platform/'addons.xml'
    assert feed_path.with_suffix('.xml.md5').read_text().strip()==hashlib.md5(feed_path.read_bytes()).hexdigest()
    feed=ET.parse(feed_path).getroot()
    assert feed.find(f"addon[@id='{ADDON}']").get('version')==VERSION
    ids={a.get('id') for a in feed}
    for item in feed:
        identity=item.get('id');version=item.get('version')
        path=ROOT/platform/'packages'/identity/f'{identity}-{version}.zip'
        with ZipFile(path) as archive:
            assert archive.testzip() is None
            manifest=ET.fromstring(archive.read(identity+'/addon.xml'))
            assert manifest.get('version')==version
            for dependency in list(manifest.find('requires')):
                dep=dependency.get('addon')
                assert dep.startswith(('xbmc.','kodi.')) or dep in ids,(platform,identity,dep)
    print(platform,'ZIP, version, source hygiene and dependency closure passed')

for name, raw in contents['android'].items():
    if name != prefix+'addon.xml':assert contents['windows'][name]==raw,name
with ZipFile(ROOT/'android/packages/script.module.cbr.engine/script.module.cbr.engine-0.1.0.zip') as archive:
    libraries=[n for n in archive.namelist() if n.endswith('.so')]
    assert {Path(n).parent.name for n in libraries}=={'android-arm7','android-arm64','android-amd64'},libraries
    machines={'android-arm7':(1,40),'android-arm64':(2,183),'android-amd64':(2,62)}
    for name in libraries:
        raw=archive.read(name)
        assert raw.startswith(b'\x7fELF'),name
        assert (raw[4],int.from_bytes(raw[18:20],'little'))==machines[Path(name).parent.name],name
print('Shared Python code matches; Android engine contains',len(libraries),'ELF libraries')

with tempfile.TemporaryDirectory() as temp:
    stage=Path(temp)/'source';stage.mkdir()
    with ZipFile(packages['windows']) as archive:archive.extractall(stage)
    source=stage/ADDON
    sys.path.insert(0,str(source))
    from resources.lib.core import Store
    from resources.lib.defaults import ensure_defaults
    from resources.lib import pvr,programmes
    fresh=Store(str(Path(temp)/'fresh'))
    ensure_defaults(fresh,str(source))
    entries=fresh.providers()
    assert len(entries)==5,len(entries)
    assert {e['label'] for e in entries}=={'Cinemeta','Torrentio','Pluto TV','Samsung TV Plus UK','Sports Streams'}
    samsung=next(e for e in entries if e['label']=='Samsung TV Plus UK')
    assert samsung['kind']=='m3u' and samsung['guide_country']=='GB'
    assert len(pvr.config(fresh)['selected'])==2
    assert not pvr.config(fresh)['enabled'] # Official IPTV Simple setup is explicit.
    feeds=programmes.settings(fresh)['feeds']
    assert len(feeds)==1 and 'SamsungTVPlus' in feeds[0]['url']
    ensure_defaults(fresh,str(source))
    assert fresh.providers()==entries
    # Simulate a configured sports link, disabled preferences and selected channels.
    sports=next(e for e in entries if e['manifest']['id']=='community.sports.fly')
    sports.update(url='https://sports.highfly.dev/personal-test-config/manifest.json',enabled=False)
    fresh.save_providers(entries)
    config=pvr.config(fresh);config['overrides']={'test':{'name':'My channel','number':700}};pvr.save_config(fresh,config)
    ensure_defaults(fresh,str(source),force=True)
    updated=fresh.provider(sports['key'])
    assert updated['url']==sports['url'] and updated['enabled'] is False
    assert pvr.config(fresh)['overrides']==config['overrides']
    existing=fresh.providers()
    for key,url in [('old-mf','https://mediafusion.elfhosted.com/manifest.json'),
                    ('old-tvvoo','https://tvvoo.stremio-italia.eu/cfg-it-uk-fr-de-pt-es-al-tr-nl-ar-bk-ru-ro-pl-bg/manifest.json'),
                    ('personal-mf','https://mediafusion.elfhosted.com/personal-test-config/manifest.json')]:
        existing.append(dict(key=key,url=url,label=key,enabled=True,
                             manifest={'id':key,'types':['tv'],'resources':[],'catalogs':[]}))
    fresh.save_providers(existing)
    ensure_defaults(fresh,str(source),force=True)
    assert fresh.provider('old-mf')['enabled'] is False
    assert fresh.provider('old-tvvoo')['enabled'] is False
    assert fresh.provider('personal-mf')['enabled'] is True
    # Verify a real accepted-profile upgrade without printing private links.
    snapshot=ROOT/'work/accepted-baseline'
    if (snapshot/'providers.json').exists():
        upgrade=Store(str(Path(temp)/'upgrade'))
        for name in ('providers.json','pvr-settings.json','programme-settings.json'):
            if (snapshot/name).exists():upgrade.write(str(Path(upgrade.root)/name),json.loads((snapshot/name).read_text(encoding='utf8')))
        before=upgrade.providers()
        ensure_defaults(upgrade,str(source))
        after=upgrade.providers()
        assert {e['key']:e['url'] for e in before}=={e['key']:e['url'] for e in after}
        assert len(programmes.settings(upgrade)['feeds'])==2
    print('Offline clean install, repeat startup and personalised upgrade passed')

assert (ROOT/'video.zip').read_bytes()==packages['android'].read_bytes()
assert (ROOT/'cbr0100.zip').read_bytes()==packages['android'].read_bytes()
assert (ROOT/'cbrwindows.zip').read_bytes()==packages['windows'].read_bytes()
html=(ROOT/'index.html').read_text(encoding='utf8')
for name in ('cbr0100.zip','cbrwindows.zip','repository.cbr.zip','windowsrepo.zip'):
    assert f'href="{name}">{name}</a>'in html
for name in ('index.html','windows.html','android.html','help.html'):
    assert VERSION in (ROOT/'website'/name).read_text(encoding='utf8'),name
print('Download aliases, Kodi directory labels and website versions passed')
print('CBR 0.10.0 release checks passed. Android device playback remains unverified.')
