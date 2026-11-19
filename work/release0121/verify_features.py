"""Exercise actual packaged maintenance features and paired HTTP boundaries."""
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
import copy, hashlib, importlib.util, json, os, sqlite3, sys, tempfile
import urllib.request, urllib.error
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(dir=ROOT/'outputs',prefix='verified-live-0110-')as temp:
    temp=Path(temp)
    with ZipFile(ROOT/'cbr0121.zip')as z:z.extractall(temp/'code')
    addon=temp/'code/plugin.video.stremio.bridge';sys.path.insert(0,str(addon))
    from resources.lib.core import Store
    from resources.lib.defaults import ensure_defaults
    from resources.lib import maintenance as care, pluto_defaults, pvr, m3u
    from resources.lib.setup_web import SetupServer
    profile=temp/'profile';profile.mkdir();store=Store(str(profile))
    ensure_defaults(store,str(addon));before=copy.deepcopy(store.providers());ensure_defaults(store,str(addon))
    assert before==store.providers()
    pluto=next(e for e in before if e['url']==pluto_defaults.URL)
    assert pluto['enabled'] and pluto['live_group']=='internet'
    assert not next(e for e in before if e['url']==pluto_defaults.OLD)['enabled']
    assert {f['url']for f in care.read(store,'programme-settings.json')['feeds']} >= {pluto_defaults.EPG,pluto_defaults.FREEVIEW_EPG}
    print('Fresh/upgrade defaults: idempotent public Pluto migration and UK guide feeds passed')

    # A signed URL changing must not change a channel's identity.
    template='#EXTM3U\n#EXTINF:-1 tvg-id="abc123" group-title="Movies",Pluto TV Movies\nhttps://video.example/master.m3u8?token={}'
    assert m3u.parse(template.format('old'),pluto_defaults.URL)[0]['id']==m3u.parse(template.format('new'),pluto_defaults.URL)[0]['id']

    private='https://sports.example/private-configuration/manifest.json'
    manifest={'id':'test.sports','name':'Test sports','version':'1.0','types':['sport'],'resources':['catalog','stream'],
              'catalogs':[{'id':'live','type':'sport','name':'Live'}]}
    entry=store.add(private,'Personal sports',fetch=lambda u:manifest)
    variant=dict(provider=entry['key'],provider_id='test.sports',provider_label=entry['label'],resource_type='sport',live_group='sports',live_country='GB',meta=dict(id='s1',type='sport',name='Sample channel'))
    row=dict(id='cbr.'+'a'*24,name='Sample channel',number=101,groups=['UK TV','Sports'],visible=True,logo='',variants=[variant])
    store.write(str(profile/'pvr-channels.json'),[row])
    pvr.save_channels(store,[dict(id=row['id'],name=row['name'],number=101,groups=row['groups'],visible=True,favourite=True)])
    assert pvr.channels(store)[0]['favourite'] and pvr.channels(store)[0]['groups'][0]=='Favourites'
    assert len(care.read(store,'live-favourites.json'))==1
    pvr.export(store);assert 'Favourites;CBR TV' in (profile/'pvr/channels.m3u').read_text()
    from resources.lib.live import LiveLibrary
    library=LiveLibrary(store)
    assert library.toggle(variant) is False
    assert not pvr.channels(store)[0]['favourite']
    assert library.toggle(variant) is True
    assert pvr.channels(store)[0]['favourite']
    original=care.read(store,'pvr-settings.json')
    try:pvr.save_channels(store,[dict(id=row['id'],name='Bad',number=0,groups=['Sports'])])
    except ValueError:pass
    else:raise AssertionError('Invalid channel number accepted')
    assert original==care.read(store,'pvr-settings.json')
    print('TV favourites, exported group and invalid-edit preservation passed')

    layout=care.export_backup(store,False);full=care.export_backup(store,True)
    assert private not in json.dumps(layout) and private in json.dumps(full)
    assert 'providers.json'not in layout['files'] and 'live-favourites.json'in full['files']
    for bad in [dict(full,files={'../guisettings.xml':{}}),dict(full,schema=99),dict(full,files={'providers.json':[{'url':'file:///secret'}]})]:
        snapshot={p.name:p.read_bytes()for p in profile.glob('*.json')}
        try:care.restore_backup(store,bad)
        except (ValueError,KeyError):pass
        else:raise AssertionError('Malformed backup accepted')
        assert snapshot=={p.name:p.read_bytes()for p in profile.glob('*.json')}
    for settings in [dict(feeds=[dict(url='file:///guide.xml',country='GB',key='bad')]),dict(feeds=[],mappings={'bad':dict(feed='a',channel='b')})]:
        bad=copy.deepcopy(full);bad['files']['programme-settings.json']=settings
        snapshot={p.name:p.read_bytes()for p in profile.glob('*.json')}
        try:care.restore_backup(store,bad)
        except ValueError:pass
        else:raise AssertionError('Invalid guide backup accepted')
        assert snapshot=={p.name:p.read_bytes()for p in profile.glob('*.json')}
    other=temp/'other-profile';other.mkdir();target=Store(str(other));care.restore_backup(target,full)
    assert target.providers()==store.providers() and care.read(target,'live-favourites.json')==care.read(store,'live-favourites.json')
    old=copy.deepcopy(target.providers());badwrite=target.write;counter=[0]
    def fail_once(path,data):
        if Path(path).name in full['files']:
            counter[0]+=1
            if counter[0]==2:raise OSError('simulated full disk')
        badwrite(path,data)
    with patch.object(target,'write',side_effect=fail_once):
        try:care.restore_backup(target,full)
        except OSError:pass
        else:raise AssertionError('Failed restore unexpectedly succeeded')
    assert target.providers()==old
    store.write(str(profile/'recent-errors.json'),[dict(time=1,action='test',summary='Failed '+private)])
    report=care.diagnose(store,str(addon));assert private not in json.dumps(report)
    assert '[address removed]'in json.dumps(report)
    print('Private/layout backup, cross-device restore, malformed-backup rejection, rollback and diagnostic redaction passed')

    def fetch_resource(e,kind,*args):
        return {'metas':[{'id':'channel1','name':'Sample'}]}if kind=='catalog'else {'streams':[{'url':'https://video.example/test.m3u8'}]}
    with patch.object(care,'fetch_resource',side_effect=fetch_resource):
        status=care.probe_source(entry,fetch=lambda u:manifest,sample=lambda *args:True)
        assert status['stream']=='sample_responded'and not status['native_playback']
        status=care.probe_source(entry,fetch=lambda u:manifest,sample=lambda *args:False)
        assert status['stream']=='sample_failed'
    def renewal(e,kind,*args):
        return {'metas':[{'id':'channel1','name':'Sample'}]}if kind=='catalog'else {'streams':[{'name':'Please reinstall','url':'https://video.example/notice.mp4'}]}
    with patch.object(care,'fetch_resource',side_effect=renewal):
        assert care.probe_source(entry,fetch=lambda u:manifest)['stream']=='renew_manifest'
    assert care.probe_source(dict(entry,enabled=False),fetch=lambda u:1/0)['catalogue']=='disabled'
    print('Source tests distinguish catalogue, small sample, renewal notice and disabled provider')

    server=SetupServer(store,str(addon/'resources/setup'),'127.0.0.1',host='127.0.0.1',port=0)
    cookie=''
    def request(path,data=None,origin=None):
        headers={'Cookie':cookie}
        if data is not None:headers['Content-Type']='application/json'
        if origin:headers['Origin']=origin
        req=urllib.request.Request(server.url+path.lstrip('/'),data=json.dumps(data).encode()if data is not None else None,headers=headers)
        with urllib.request.urlopen(req,timeout=5)as response:return json.load(response),response.headers
    try:
        for path in ['/api/diagnostics','/api/sources']:
            try:request(path)
            except urllib.error.HTTPError as e:assert e.code==401
            else:raise AssertionError('Unpaired access accepted')
        paired,headers=request('/api/pair',{'code':server.code});cookie=headers['Set-Cookie'].split(';',1)[0]
        assert request('/api/diagnostics')[0]['version']=='0.12.1'
        assert private not in json.dumps(request('/api/backup',{'personal':False})[0])
        assert private in json.dumps(request('/api/backup',{'personal':True})[0])
        try:request('/api/restore',{'backup':full})
        except urllib.error.HTTPError as e:assert e.code==400
        else:raise AssertionError('Restore without confirmation accepted')
        try:request('/api/backup',{'personal':True},'https://unrelated.example')
        except urllib.error.HTTPError as e:assert e.code==403
        else:raise AssertionError('Cross-origin access accepted')
        assert 'restored'in request('/api/restore',{'backup':full,'confirmed':True})[0]['message']
    finally:server.close()
    print('Paired HTTP diagnostics/backup/restore: authentication, same-origin guard and explicit restore confirmation passed')

    spec=importlib.util.spec_from_file_location('cbr_uninstall',ROOT/'work/release0110/cbr_uninstall.py')
    removal=importlib.util.module_from_spec(spec);spec.loader.exec_module(removal)
    home=temp/'removal';addons=home/'addons';data=home/'userdata';addons.mkdir(parents=True);data.mkdir()
    for identity in removal.IDS:
        folder=addons/identity;folder.mkdir();(folder/'addon.xml').write_text('<addon id="'+identity+'"/>')
        folder=data/identity;folder.mkdir();(folder/'settings.json').write_text('private')
    unrelated=addons/'plugin.video.thecrew';unrelated.mkdir();(unrelated/'sentinel').write_text('keep')
    assert removal.blockers([dict(addonid='other',name='Other',dependencies=[dict(addonid='plugin.video.stremio.bridge')])])==['Other']
    # Entire removal plan is validated before the first directory is touched.
    (addons/removal.IDS[-1]/'addon.xml').write_text('<addon id="wrong"/>')
    try:removal.remove_files(addons,data)
    except ValueError:pass
    else:raise AssertionError('Unexpected component identity accepted')
    assert all((addons/i).exists()for i in removal.IDS)
    (addons/removal.IDS[-1]/'addon.xml').write_text('<addon id="script.crb.wizard"/>')
    removal.remove_files(addons,data)
    assert (unrelated/'sentinel').read_text()=='keep'
    assert all((data/i/'settings.json').exists()for i in removal.IDS)
    tv=data/'pvr.iptvsimple';tv.mkdir()
    for i,path in [(1,'special://profile/addon_data/plugin.video.stremio.bridge/pvr/channels.m3u'),(2,'https://other.example/tv.m3u')]:
        (tv/f'instance-settings-{i}.xml').write_text('<settings><setting id="m3uPath">'+path+'</setting><setting id="kodi_addon_instance_enabled">true</setting></settings>')
    removal.disable_tv(tv)
    assert ET.parse(tv/'instance-settings-1.xml').find("setting[@id='kodi_addon_instance_enabled']").text=='false'
    assert ET.parse(tv/'instance-settings-2.xml').find("setting[@id='kodi_addon_instance_enabled']").text=='true'
    print('CBR-only removal: full-plan validation, dependency blockers, settings preservation and unrelated TV/addon preservation passed')
