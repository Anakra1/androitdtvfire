"""Exercise migration, grouping, stable Pluto IDs and gap-only XMLTV notices."""
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
import copy, os, sys, tempfile, time, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(dir=ROOT/'outputs',prefix='verified-live-tv-')as tmp:
    tmp=Path(tmp)
    with ZipFile(ROOT/'cbr0120.zip')as z:z.extractall(tmp/'code')
    addon=tmp/'code/plugin.video.stremio.bridge';sys.path.insert(0,str(addon))
    from resources.lib.core import Store
    from resources.lib.defaults import ensure_defaults
    from resources.lib import m3u, pvr, tv_defaults, programmes
    store=Store(str(tmp/'profile'))
    ensure_defaults(store,str(addon));first=copy.deepcopy(store.providers());ensure_defaults(store,str(addon))
    assert store.providers()==first
    for url in [m3u.DEFAULT_URL,m3u.UK_URL,m3u.PLUTO_URL]:assert sum(e['url']==url for e in first)==1
    pluto=next(e for e in first if e['url']==m3u.PLUTO_URL)
    assert len(pluto['manifest']['catalogs'])==1
    assert any(s['key'] in pvr.config(store)['selected'] for s in pvr.sources(store) if s['provider']==pluto['key'])
    assert pluto['live_group']=='internet' and pluto['pvr_groups']==['Pluto TV']
    assert {f['url']for f in programmes.settings(store)['feeds']} >= {tv_defaults.PLUTO_EPG}
    private=store.add('https://private.example/manifest.json','Personal',fetch=lambda u:dict(id='private',name='Private',version='1',resources=[],catalogs=[]))
    entries=store.providers();next(e for e in entries if e['url']==m3u.PLUTO_URL)['enabled']=False;store.save_providers(entries)
    ensure_defaults(store,str(addon),force=True)
    assert not next(e for e in store.providers()if e['url']==m3u.PLUTO_URL)['enabled']
    assert store.provider(private['key'])==private
    # Restore only this test source for fixture collection.
    entries=store.providers();next(e for e in entries if e['url']==m3u.PLUTO_URL)['enabled']=True;store.save_providers(entries)
    raw='#EXTM3U\n#EXTINF:0 channel-id="movies" tvg-logo="https://images.pluto.tv/channels/abcdef0123456789abcdef01/colorLogoPNG.png" group-title="Movies",Pluto Cinema\nhttps://example.org/movie.m3u8?session=old\n'
    rows=m3u.parse(raw,m3u.PLUTO_URL)
    assert rows[0]['streams'][0]['behaviorHints']['proxyHeaders']['request']['User-Agent']=='CBR/0.11.3'
    assert rows[0]['tvg_id']=='abcdef0123456789abcdef01'
    assert rows[0]['id']==m3u.parse(raw.replace('session=old','session=new'),m3u.PLUTO_URL)[0]['id']
    source=next(s for s in pvr.sources(store)if s['provider']==pluto['key']and s['catalog']['id']=='m3u_US')
    with patch.object(m3u,'load',return_value=rows):variants=pvr.collect_source(store,source)
    assert len(variants)==1 and variants[0]['live_country']=='US'
    merged=pvr.merge_channels(variants);assert {'Pluto TV','Movies'} <= set(merged[0]['groups'])
    assert 'UK TV' not in merged[0]['groups']
    store.write(os.path.join(store.root,'pvr-channels.json'),merged)
    start,stop=100,1000
    real=[dict(start=200,stop=300,title='Real show',description='Actual listing'),dict(start=500,stop=600,title='Next show')]
    filled=pvr.programme_slots(real,start,stop)
    assert [p for p in filled if not p.get('placeholder')]==real
    assert [(p['start'],p['stop'])for p in filled]==[(100,200),(200,300),(300,500),(500,600),(600,1000)]
    assert sum(p['stop']-p['start']for p in filled)==900
    assert len(pvr.programme_slots([],0,86400*9))==9
    with patch.object(pvr.ProgrammeGuide,'schedule',return_value=[]):result=pvr.export(store)
    assert result['channels']==1 and result['guide_channels']==0 and result['programmes']==0 and result['unavailable_slots']==9
    xml=ET.parse(Path(store.root)/'pvr/guide.xml').getroot();assert len(xml.findall('programme'))==9
    assert all(p.findtext('title')==pvr.UNAVAILABLE for p in xml.findall('programme'))
    assert 'Pluto TV' in (Path(store.root)/'pvr/channels.m3u').read_text()
    with patch.object(pvr.ProgrammeGuide,'schedule',return_value=[dict(start=time.time()-60,stop=time.time()+3600,title='Genuine listing')]):
        result=pvr.export(store)
    assert result['guide_channels']==1 and result['programmes']==1
    print('Defaults idempotent, private/disabled sources preserved; Pluto identities and country correct; group exported; gap notices preserve real EPG and real coverage counts.')
with ZipFile(ROOT/'android/packages/skin.crimsonbloodrequiem/skin.crimsonbloodrequiem-0.2.0.zip')as z:
    for name in ['MyPVRChannels.xml','MyPVRGuide.xml']:
        root=ET.fromstring(z.read('skin.crimsonbloodrequiem/xml/'+name))
        assert len(root.findall(".//control[@id='11']"))==1
        assert root.find('defaultcontrol').text=='11'
        assert root.find(".//control[@id='11']/orientation").text=='horizontal'
    home=z.read('skin.crimsonbloodrequiem/xml/Home.xml').decode()
    assert 'ActivateWindow(TVGuide)' in home
    assert b'CBRLiveGuideTitle' in z.read('skin.crimsonbloodrequiem/xml/Variables.xml')
print('Skin has a native group-tab selector on both screens and TV opens the CBR guide.')
