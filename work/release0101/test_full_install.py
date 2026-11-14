"""Exercise the full setup from the published-format ZIPs in isolated profiles."""
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
import importlib.util
import types

ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory()as temporary:
    root=Path(temporary)
    with ZipFile(ROOT/'cbrwindows.zip')as archive:archive.extractall(root/'addons')
    with ZipFile(ROOT/'full.zip')as archive:archive.extractall(root/'addons')
    addon=root/'addons/plugin.video.stremio.bridge'
    wizard=root/'addons/script.crb.wizard'
    sys.path[:0]=[str(addon),str(wizard)]
    from resources.lib.core import Store
    from resources.lib.defaults import ensure_defaults
    from resources.lib import pvr,programmes
    from cbr_full_setup import FullInstall
    profile=root/'profile';iptv=root/'iptv';iptv.mkdir()
    other=iptv/'instance-settings-77.xml'
    unrelated=b'<settings><setting id="kodi_addon_instance_name">My other provider</setting></settings>'
    other.write_bytes(unrelated)
    task=FullInstall(str(addon),str(profile),str(iptv))
    status=task.run()
    assert status['state']=='ready' and status['channels']>=250,status
    assert status['guide_channels']>=250,status
    assert other.read_bytes()==unrelated
    configs=list(iptv.glob('instance-settings-*.xml'))
    assert len(configs)==2,configs
    own=next(p for p in configs if p!=other)
    values={n.get('id'):n.text for n in ET.parse(own).getroot()}
    assert values['kodi_addon_instance_name']=='CBR TV' and values['kodi_addon_instance_enabled']=='true'
    assert values['m3uPath'].endswith('/pvr/channels.m3u')
    assert (profile/'pvr/channels.m3u').exists() and (profile/'pvr/guide.xml').exists()
    assert pvr.config(task.store)['enabled']
    assert not task.store.read(task.flag)
    print('Clean full setup:',status['channels'],'channels,',status['guide_channels'],'with guide;',status['programmes'],'programme entries')
    print('Other IPTV instance preserved; service pause cleared after completion')
    # Cancel before touching settings; no IPTV instance may be created.
    cancelled=FullInstall(str(addon),str(root/'cancelled'),str(root/'cancelled-iptv'))
    cancelled.cancel()
    try:cancelled.run()
    except InterruptedError:pass
    else:raise AssertionError('Cancelled setup reported success')
    assert not cancelled.store.read(cancelled.flag)
    assert not Path(cancelled.iptv_profile).exists()
    during=FullInstall(str(addon),str(root/'during-cancel'),str(root/'during-cancel-iptv'))
    def cancel_guide(feeds):
        during.store.write(str(Path(during.store.root)/'programme-status.json'),{'test':{'state':'updating'}})
        during.cancel()
    with patch.object(during.guide,'refresh',cancel_guide):
        try:during.run()
        except InterruptedError:pass
        else:raise AssertionError('Mid-download cancellation reported success')
    assert during.store.read(str(Path(during.store.root)/'programme-status.json'))['test']['state']=='cancelled'
    assert not during.store.read(during.flag)
    # A failed channel build must not configure IPTV or claim completion.
    failed=FullInstall(str(addon),str(root/'failed'),str(root/'failed-iptv'))
    ensure_defaults(failed.store,str(addon))
    config=programmes.settings(failed.store);config['enabled']=False;programmes.save_settings(failed.store,config)
    def fail_build(collect=True):
        failed.store.write(str(Path(failed.store.root)/'pvr-status.json'),{'state':'error','channels':0})
    with patch.object(failed.tv,'build',fail_build):
        try:failed.run()
        except RuntimeError as error:assert 'could not be built'in str(error)
        else:raise AssertionError('Failed setup reported success')
    assert not failed.store.read(failed.flag)
    assert not Path(failed.iptv_profile).exists()
    print('Cancellation and failed-build recovery passed')
    # Execute the actual wizard entry point with Kodi API stand-ins, checking
    # the client reload, previous-skin backup and completion report ordering.
    calls=[]
    gui_root=root/'gui-profile';state_root=root/'wizard-state'
    def translate(path):
        if path.endswith('script.crb.wizard'):return str(state_root)
        if 'pvr.iptvsimple'in path:return str(root/'gui-iptv')
        return path
    class File:
        def __init__(self,path,mode='r'):self.file=open(path,mode,encoding='utf8')
        def __enter__(self):return self.file
        def __exit__(self,*args):self.file.close()
    class Dialog:
        def ok(self,*args):calls.append(('dialog',args))
        def notification(self,*args):pass
        def select(self,*args):return 0
    class Progress:
        def create(self,*args):pass
        def update(self,*args):pass
        def iscanceled(self):return False
        def close(self):pass
    def execute(raw):
        req=json.loads(raw);calls.append((req['method'],req['params']))
        result={'value':'skin.estuary'} if req['method']=='Settings.GetSettingValue'else True
        return json.dumps({'jsonrpc':'2.0','id':1,'result':result})
    def addon_info(identity):
        return types.SimpleNamespace(getAddonInfo=lambda key:str(addon if key=='path'else gui_root))
    modules={
        'xbmc':types.SimpleNamespace(executeJSONRPC=execute,executebuiltin=lambda value:calls.append(('builtin',value)),
            Player=lambda:types.SimpleNamespace(isPlaying=lambda:False),
            Monitor=lambda:types.SimpleNamespace(abortRequested=lambda:False,waitForAbort=lambda seconds:False)),
        'xbmcaddon':types.SimpleNamespace(Addon=addon_info),
        'xbmcgui':types.SimpleNamespace(Dialog=Dialog,DialogProgress=Progress,NOTIFICATION_INFO=1),
        'xbmcvfs':types.SimpleNamespace(translatePath=translate,mkdirs=lambda p:Path(p).mkdir(parents=True,exist_ok=True),
            exists=lambda p:Path(p).exists(),File=File)}
    with patch.dict(sys.modules,modules):
        spec=importlib.util.spec_from_file_location('cbr_wizard_test',wizard/'default.py')
        entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
        with patch.object(FullInstall,'run',return_value={'channels':279,'guide_channels':257}):entry.full_install()
        with patch.object(entry,'full_install',side_effect=RuntimeError('Kodi could not enable IPTV Simple')):
            entry.main()
    assert json.loads((state_root/'previous-skin.json').read_text())['skin']=='skin.estuary'
    assert json.loads((state_root/'full-install.json').read_text())['channels']==279
    toggles=[p['enabled']for method,p in calls if method=='Addons.SetAddonEnabled']
    assert toggles==[False,True],toggles
    assert any(method=='Settings.SetSettingValue'and p.get('value')=='skin.crimsonbloodrequiem'for method,p in calls)
    assert any(method=='dialog'and 'complete'in p[0]for method,p in calls)
    assert not json.loads((gui_root/'full-setup-active.json').read_text())
    assert any(method=='dialog'and 'needs attention'in p[0]and 'could not enable'in p[1]for method,p in calls)
    print('Wizard entry point: dependency checks, client reload, skin backup/apply and completion report passed')
