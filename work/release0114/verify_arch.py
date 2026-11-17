"""Check actual packaged CPU selection, native ABI and installation integrity."""
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
import types, sys, hashlib, json, struct
ROOT=Path(__file__).resolve().parents[2]
VIDEO='plugin.video.stremio.bridge'
ENGINE='script.module.cbr.engine'
def module(code,name):
    m=types.ModuleType(name);exec(compile(code,name,'exec'),m.__dict__);return m
with ZipFile(ROOT/'cbr0114.zip') as z:
    video=module(z.read(VIDEO+'/engine.py'),'video_engine')
with ZipFile(ROOT/'android/packages'/ENGINE/(ENGINE+'-0.1.1.zip')) as z:
    engine=module(z.read(ENGINE+'/lib/cbrengine/__init__.py'),'cbrengine')
    checks=json.loads(z.read(ENGINE+'/resources/checksums.json'))
    for cpu,machine_id,elf_class in [('android-arm7',40,1),('android-arm64',183,2)]:
        raw=z.read(ENGINE+'/resources/lib/'+cpu+'/libcbrengine.so')
        assert hashlib.sha256(raw).hexdigest()==checks[cpu]
        assert raw[:4]==b'\x7fELF' and raw[4]==elf_class and int.from_bytes(raw[18:20],'little')==machine_id
    with ZipFile(ROOT/'android/packages'/ENGINE/(ENGINE+'-0.1.0.zip')) as old:
        for name in z.namelist():
            if name.endswith('.so'):assert z.read(name)==old.read(name)
with patch.dict(sys.modules,{'xbmc':types.SimpleNamespace(getCondVisibility=lambda _:True)}):
    for cpu in ['armv8l','aarch64','arm64','armv7l','armv7','arm']:
        for size in [4,8]:
            with patch.object(video.platform,'machine',return_value=cpu),patch.object(struct,'calcsize',return_value=size):
                assert video._android_arch()==('arm64' if size==8 else 'arm7')
                assert engine.architecture()==('android-arm64' if size==8 else 'android-arm7')
    with patch.object(video.platform,'machine',return_value='mips'):
        for fn in [video._android_arch,engine.architecture]:
            try:fn()
            except RuntimeError:pass
            else:raise AssertionError('Unsupported architecture accepted')
    with patch.dict(sys.modules,{'xbmc':types.SimpleNamespace(getCondVisibility=lambda _:False)}):
        assert video._android_arch() is None
print('ARMv8l and legacy ARM aliases select matching 32/64-bit ABI in BOTH packaged layers; unknown CPUs rejected; original native libraries and checksums preserved.')
