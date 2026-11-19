"""Run Command behavioural checks against both actual release ZIPs."""
from pathlib import Path
from zipfile import ZipFile
import tempfile,subprocess,sys,ast
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
for platform in ('android','windows'):
    with tempfile.TemporaryDirectory(dir=ROOT/'outputs',prefix='verified-live-command-') as temp:
        root=Path(temp); addons=root/'work/test-kodi-tv/portable_data/addons';addons.mkdir(parents=True)
        with ZipFile(ROOT/platform/'packages/plugin.video.stremio.bridge/plugin.video.stremio.bridge-0.12.0.zip') as z:z.extractall(addons)
        with ZipFile(ROOT/platform/'packages/skin.crimsonbloodrequiem/skin.crimsonbloodrequiem-0.2.0.zip') as z:z.extractall(addons)
        (addons/'skin.crimsonbloodrequiem').rename(addons/'skin.cbr.prototype')
        source=addons/'plugin.video.stremio.bridge'; tests=root/'work/checks';tests.mkdir()
        for name in ('command_state.py','command_service.py'):(tests/name).write_bytes((source/'resources/lib'/name).read_bytes())
        code=(source/'addon.py').read_text(encoding='utf-8')
        routes=code[code.index('"""Command browsing and playback routes'):code.index('def command_dispatch(')]
        (tests/'command_routes.py').write_text(routes,encoding='utf-8')
        (tests/'verify.py').write_bytes((HERE/'command_checks.py').read_bytes())
        result=subprocess.run([sys.executable,str(tests/'verify.py')],capture_output=True,text=True)
        print(platform,result.stdout.strip());assert result.returncode==0,result.stderr
        # Skin-specific views must be skipped under Estuary, leaving normal browsing usable.
        funcs=ast.parse(code);namespace={'xbmc':type('X',(),{'getSkinDir':lambda:'skin.estuary'})}
        for name in ('command_set_view','prototype_sports_view'):
            fn=next(n for n in funcs.body if isinstance(n,ast.FunctionDef) and n.name==name)
            exec(compile(ast.Module(body=[fn],type_ignores=[]),name,'exec'),namespace)
        namespace['command_set_view']('movies');namespace['prototype_sports_view']()
        from types import SimpleNamespace
        decisions=[]
        fallback=dict(xbmc=SimpleNamespace(getSkinDir=lambda:'skin.estuary',executebuiltin=lambda s:decisions.append(s)),
            STORE=SimpleNamespace(get=lambda key:dict(meta=dict(id='fixture',type='movie',name='Fixture'),type='movie'),providers=lambda:[]),
            COMMAND=SimpleNamespace(get=lambda *a:None,contains=lambda *a:False),identity=lambda k,i:k+':'+i,
            DIALOG=SimpleNamespace(select=lambda *a:-1),finish=lambda:decisions.append('finished'))
        fn=next(n for n in funcs.body if isinstance(n,ast.FunctionDef) and n.name=='command_detail')
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'detail','exec'),fallback)
        fallback['command_detail']('fixture');assert decisions==['finished','Action(Back)']
        print(platform,'default-skin title menu, cancellation and browsing guards passed')
        # Run provider isolation checks against functions extracted from this archive.
        sports=ast.Module(body=[n for n in funcs.body if isinstance(n,ast.FunctionDef) and n.name.startswith('prototype_') and ('sports' in n.name)],type_ignores=[])
        (tests/'sports_routes.py').write_text(ast.unparse(sports),encoding='utf-8')
        sports_test=(HERE/'sports_checks.py').read_text(encoding='utf-8').replace("parents[1]/'test-kodi-tv", "parents[1]/'test-kodi-tv")
        (tests/'sports_verify.py').write_text(sports_test,encoding='utf-8')
        result=subprocess.run([sys.executable,str(tests/'sports_verify.py')],capture_output=True,text=True)
        print(platform,result.stdout.strip());assert result.returncode==0,result.stderr

print('Packaged Command features verified on both platform archives.')
