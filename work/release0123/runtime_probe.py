"""Probe the rebuilt library in an isolated emulator; never target a physical device."""
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
import subprocess,sys,time,json,hashlib
ROOT=Path(__file__).resolve().parents[2];adb=sys.argv[1];serial='emulator-5554'
def call(*args,check=True):
    r=subprocess.run([adb,'-s',serial,*args],capture_output=True,text=True,timeout=10)
    if check and r.returncode:raise RuntimeError('Android test command failed: '+args[0])
    return r.stdout.strip()
for attempt in range(90):
    if call('shell','getprop','sys.boot_completed',check=False)=='1':break
    if attempt%20==0:print('Waiting for isolated Android boot',flush=True)
    time.sleep(1)
else:raise RuntimeError('Test emulator did not finish booting')
call('shell','am','force-stop','com.cbr.nativetest')
call('shell','am','start','-n','com.cbr.nativetest/.MainActivity')
call('forward','tcp:19767','tcp:8767')
opener=build_opener(ProxyHandler({}));samples=[];first=None
for attempt in range(80):
    try:
        with opener.open('http://127.0.0.1:19767/echo',timeout=1) as r:data=r.read(100).decode()
        assert data.startswith('MatriX.');samples.append(data)
        if first is None:first=time.monotonic();print('Native Android engine responded',flush=True)
        if time.monotonic()-first>=20:break
    except Exception:pass
    time.sleep(.5)
else:raise RuntimeError('Android engine did not remain healthy')
assert len(samples)>10 and call('shell','pidof','com.cbr.nativetest')
actual=call('shell','run-as','com.cbr.nativetest','sha256sum','files/libcbrengine.so').split()[0]
expected=hashlib.sha256((ROOT/'work/release0123/native-libs/android-amd64/libcbrengine.so').read_bytes()).hexdigest();assert actual==expected
result=dict(engine='0.1.2',runtime='isolated Android x86_64 emulator',android_api=call('shell','getprop','ro.build.version.sdk'),native_load=True,hash_match=True,echo=samples[-1],healthy_samples=len(samples),sustained_seconds=round(time.monotonic()-first),physical_fire_tv_tested=False)
(ROOT/'outputs/verified-live-engine012-runtime.json').write_text(json.dumps(result,indent=2))
print('PASS: rebuilt engine loaded, started and served sustained health requests in Android',flush=True)
