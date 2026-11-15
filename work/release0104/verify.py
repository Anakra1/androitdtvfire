"""Verify Android archives, fresh/upgrade profiles and TV cleanup behavior."""
from pathlib import Path
from zipfile import ZipFile
import ast, hashlib, json, re, sys, tempfile, xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ADDON='plugin.video.stremio.bridge'
P=ADDON+'/'
feedpath=ROOT/'android/addons.xml'
assert hashlib.md5(feedpath.read_bytes()).hexdigest()==feedpath.with_suffix('.xml.md5').read_text().strip()
feed=ET.parse(feedpath).getroot()
for identity,version in ((ADDON,'0.10.4'),('skin.crimsonbloodrequiem','0.1.2'),('script.crb.wizard','0.2.3')):
    assert feed.find("addon[@id='"+identity+"']").get('version')==version
    path=ROOT/'android/packages'/identity/(identity+'-'+version+'.zip')
    with ZipFile(path)as z:
        assert z.testzip()is None
        for n in z.namelist():
            assert n.startswith(identity+'/')and'..'not in Path(n).parts
            if n.endswith('.py'):ast.parse(z.read(n).decode('utf-8-sig'),feature_version=(3,8))
            if n.endswith('.json'):json.loads(z.read(n))
            if n.endswith('.xml'):ET.fromstring(z.read(n))
            if n.endswith(('.py','.json','.xml','.md')):
                assert not re.search(rb'sports\.highfly\.(?:dev|to)/[0-9a-f]{8}-',z.read(n)),n
        assert 'TorrServer.exe'not in ' '.join(z.namelist())
for name,digest in json.loads((HERE/'unchanged.json').read_text()).items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name

with tempfile.TemporaryDirectory(dir=ROOT/'outputs',prefix='verified-live-0103-')as tmp:
    tmp=Path(tmp)
    with ZipFile(ROOT/'cbr0104.zip')as z:z.extractall(tmp/'source')
    addon=tmp/'source'/ADDON;sys.path.insert(0,str(addon))
    from resources.lib.core import Store
    from resources.lib.defaults import ensure_defaults
    from resources.lib import pvr,m3u,programmes
    store=Store(str(tmp/'profile'));ensure_defaults(store,str(addon))
    entries=store.providers();assert len(entries)==8
    dad=next(e for e in entries if e['manifest']['id']=='org.cbr.daddylive')
    assert dad['enabled'] is False and dad['pvr_enabled'] is False
    bbc=next(e for e in entries if e['label']=='BBC UK (Free-TV)')
    assert len(bbc['include_tvg_ids'])==10 and bbc['priority']==10
    selected=pvr.config(store)['selected'];assert len(selected)==4
    assert len(programmes.settings(store)['feeds'])==2
    ensure_defaults(store,str(addon));assert entries==store.providers()
    sports=next(e for e in entries if e['manifest']['id']=='community.sports.fly')
    sports.update(url='https://sports.highfly.dev/personal-test/manifest.json',enabled=False)
    store.save_providers(entries);ensure_defaults(store,str(addon),force=True)
    assert store.provider(sports['key'])['url']==sports['url'] and not store.provider(sports['key'])['enabled']
    assert 'Sky'not in pvr.GROUPS
    assert 'UK TV'in pvr.group_names('BBC One',[],'GB')
    assert 'UK TV'not in pvr.group_names('ABC',[],'US')
    variants=[dict(provider='fixture',provider_id='fixture',resource_type='tv',live_country='GB',meta=dict(id=n,name=n,country='GB'))
              for n in ('BBC One','BBC Two','Channel 4','Channel 5','Sky News Weather','Sky Sports F1')]
    rows=pvr.merge_channels(variants)
    assert {r['name']for r in rows if not r['visible']}=={'Channel 4','Channel 5','Sky News Weather'}
    assert all('Sky'not in r['groups']for r in rows)
    assert next(r for r in rows if r['name']=='Sky Sports F1')['visible']
    other=dict(variants[2],live_country='US',meta=dict(id='us-c4',name='Channel 4',country='US'))
    assert pvr.merge_channels([other])[0]['visible']
    bad=next(r for r in rows if r['name']=='Channel 4')
    config=pvr.config(store);config['overrides']={bad['id']:dict(visible=True,name='Channel 4',number=4,groups=['Sky'])};pvr.save_config(store,config)
    store.write(str(Path(store.root)/'pvr-channels.json'),rows)
    assert next(r for r in pvr.channels(store)if r['id']==bad['id'])['visible']
    assert all('Sky'not in r['groups']for r in pvr.channels(store))
    sample='#EXTM3U\n#EXTINF:-1 tvg-id="BBCOne.uk",BBC One Ⓖ\nhttps://example.org/bbc.m3u8\n#EXTINF:-1 tvg-id="ITV1.uk",ITV1\nhttps://example.org/itv.m3u8\n'
    rows=m3u.parse(sample,bbc['url']);assert rows[0]['name']=='BBC One'
    m3u.load=lambda *a,**k:rows
    data=m3u.resource(bbc,'catalog','tv','m3u_uk')['metas']
    assert len(data)==1 and data[0]['epg_id']=='BBC.One.Yorks.HD.uk'
    assert m3u.resource(bbc,'stream','tv',rows[1]['id'])=={'streams':[]}
    ensure_defaults(store,str(addon),force=True)
    assert pvr.config(store)['overrides'][bad['id']]['visible'] is False
    assert 'Sky'not in pvr.config(store)['overrides'][bad['id']]['groups']
    iptv=tmp/'iptv';iptv.mkdir()
    other=iptv/'instance-settings-1.xml';other.write_text('<settings><setting id="kodi_addon_instance_name">Other TV</setting></settings>')
    original=other.read_bytes()
    legacy=iptv/'instance-settings-1908001.xml'
    legacy.write_text('<settings><setting id="kodi_addon_instance_name">CBR TV</setting><setting id="m3uPath">cbr-list</setting></settings>')
    new=pvr.configure_instance(str(iptv),'cbr-list','cbr-guide')
    assert Path(new)!=legacy and other.read_bytes()==original
    previous={n.get('id'):n.text for n in ET.parse(legacy).getroot()}
    assert previous['kodi_addon_instance_enabled']=='false' and previous['kodi_addon_instance_name']=='CBR TV (previous)'
    assert pvr.configure_instance(str(iptv),'cbr-list','cbr-guide')==new
    assert len(list(iptv.glob('instance-settings-*.xml')))==3
print('Android ZIPs, Python 3.8 syntax, private-token hygiene, BBC filters, Sky removal, failed-channel hiding, fresh setup and upgrade preservation passed.')
