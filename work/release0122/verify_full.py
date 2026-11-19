"""Verify bundled Android installation without relying on any CBR repository."""
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
import ast
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
ID='script.crb.wizard'
with ZipFile(ROOT/'fulla.zip')as archive:
    assert archive.testzip()is None
    manifest=ET.fromstring(archive.read(ID+'/addon.xml'))
    assert manifest.get('version')=='0.4.2'
    assert [d.get('addon')for d in manifest.find('requires')]==['xbmc.python']
    assert manifest.find("extension[@point='xbmc.addon.metadata']/platform").text=='android'
    for name in archive.namelist():
        if name.endswith('.py'):ast.parse(archive.read(name).decode('utf8'))
    with tempfile.TemporaryDirectory(dir=ROOT/'outputs',prefix='verified-live-full022-')as temporary:
        root=Path(temporary)
        archive.extractall(root)
        wizard=root/ID;bundle=wizard/'resources/bundle'
        sys.path.insert(0,str(wizard))
        from cbr_bundle import install,selected_components
        for cpu in ('android-armv7','android-aarch64'):
            home=root/cpu/'addons'
            profile=home.parent/'userdata';profile.mkdir(parents=True)
            sentinel=profile/'settings.json';sentinel.write_text('personal settings')
            items=install(bundle,home,cpu,21,lambda identity:None,lambda:False,lambda p,m:None)
            ids={item['id']for item in items}
            assert ids=={'script.module.cbr.engine','plugin.video.stremio.bridge','skin.crimsonbloodrequiem','repository.crb.android','pvr.iptvsimple',
                         'inputstream.ffmpegdirect','inputstream.adaptive','inputstream.rtmp'}
            for item in items:
                meta=ET.parse(home/item['id']/'addon.xml').getroot()
                assert meta.get('version')==item['version']
                for dep in meta.find('requires'):
                    assert dep.get('optional')=='true' or dep.get('addon')in ids or dep.get('addon').startswith(('xbmc.','kodi.')),dep.attrib
            assert (home/'skin.crimsonbloodrequiem/xml/Home.xml').exists()
            assert len(list((home/'skin.crimsonbloodrequiem').rglob('*.xml')))>50
            native=home/'pvr.iptvsimple/pvr.iptvsimple.so'
            if not native.exists():native=next((home/'pvr.iptvsimple').rglob('*.so'))
            raw=native.read_bytes()
            assert raw.startswith(b'\x7fELF')
            assert (raw[4],int.from_bytes(raw[18:20],'little'))==((1,40)if cpu.endswith('armv7')else(2,183))
            assert sentinel.read_text()=='personal settings'
            mtimes={p:p.stat().st_mtime_ns for p in home.rglob('*')if p.is_file()}
            existing=lambda identity:ET.parse(home/identity/'addon.xml').getroot().get('version')
            install(bundle,home,cpu,21,existing,lambda:False,lambda p,m:None)
            assert all(p.stat().st_mtime_ns==stamp for p,stamp in mtimes.items())
            print(cpu,'fresh install: skin, video, engine, repository and matching TV client present; repeat preserves files',flush=True)
        # A damaged skin package must be rejected before writing any component.
        path=bundle/'packages.json';original=path.read_bytes();data=json.loads(original)
        next(item for item in data['packages']if item['id']=='skin.crimsonbloodrequiem')['sha256']='0'*64
        path.write_text(json.dumps(data))
        try:
            try:install(bundle,root/'damaged','android-armv7',21,lambda i:None,lambda:False,lambda p,m:None)
            except RuntimeError as error:assert 'damaged'in str(error)
            else:raise AssertionError('Damaged package accepted')
            assert not list((root/'damaged').iterdir())
        finally:path.write_bytes(original)
        calls=[0]
        def cancel():
            calls[0]+=1
            return calls[0]>2
        try:install(bundle,root/'cancelled','android-armv7',21,lambda i:None,cancel,lambda p,m:None)
        except InterruptedError:pass
        else:raise AssertionError('Cancellation ignored')
        assert not (root/'cancelled/script.module.cbr.engine/addon.xml').exists()
        print('Damaged archive rejected before writes; cancellation leaves no registered partial component',flush=True)
        # Drive the actual wizard bootstrap with a Kodi API stand-in that starts
        # with no repositories or CBR components registered at all.
        gui_home=root/'gui-addons';registered={};enabled=[];builtins=[]
        def execute(raw):
            req=json.loads(raw);method=req['method'];params=req['params']
            response={'jsonrpc':'2.0','id':1}
            if method=='Application.GetProperties':response['result']={'version':{'major':21}}
            elif method=='Addons.GetAddonDetails':
                if params['addonid']in registered:response['result']={'addon':{'version':registered[params['addonid']]}}
                else:response['error']={'code':-32602,'message':'not installed'}
            elif method=='Addons.SetAddonEnabled':
                assert params['addonid']in registered;enabled.append(params['addonid']);response['result']='OK'
            return json.dumps(response)
        def builtin(value,*args):
            builtins.append(value)
            if value=='UpdateLocalAddons':
                registered.update({p.parent.name:ET.parse(p).getroot().get('version')for p in gui_home.glob('*/addon.xml')})
        class Progress:
            def create(self,*args):pass
            def update(self,*args):pass
            def iscanceled(self):return False
            def close(self):pass
        modules={
            'xbmc':types.SimpleNamespace(executeJSONRPC=execute,executebuiltin=builtin,getCondVisibility=lambda x:True,
                Monitor=lambda:types.SimpleNamespace(abortRequested=lambda:False,waitForAbort=lambda n:False)),
            'xbmcaddon':types.SimpleNamespace(Addon=lambda identity:types.SimpleNamespace(getAddonInfo=lambda key:str(wizard))),
            'xbmcgui':types.SimpleNamespace(Dialog=lambda:None,DialogProgress=Progress),
            'xbmcvfs':types.SimpleNamespace(translatePath=lambda value:str(gui_home)if value=='special://home/addons/'else value)}
        with patch.dict(sys.modules,modules),patch('platform.machine',return_value='aarch64'):
            spec=importlib.util.spec_from_file_location('android_wizard_test',wizard/'default.py')
            entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
            for machine,bits,expected in [('aarch64',4,'android-armv7'),('aarch64',8,'android-aarch64'),('armv8l',4,'android-armv7'),('armv7l',4,'android-armv7')]:
                with patch('platform.machine',return_value=machine),patch.object(entry.struct,'calcsize',return_value=bits):
                    assert entry.android_cpu()==expected
            with patch('platform.machine',return_value='x86_64'):
                try:entry.android_cpu()
                except RuntimeError:pass
                else:raise AssertionError('Unsupported CPU accepted')
            entry.install_included()
        assert set(enabled)==set(registered)and'skin.crimsonbloodrequiem'in enabled
        assert not any(b.startswith('InstallAddon')for b in builtins)
        print('Wizard bootstrap: no CBR repository required, included skin registered/enabled, no dependency download',flush=True)
        print('Guide networking unchanged; no live provider check required for ABI fix.')
