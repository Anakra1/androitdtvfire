"""Validate the shipped Android loader fix, automatic dependency and ARM full installer."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import hashlib,json,sys,xml.etree.ElementTree as E,subprocess,ast
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE))
from elf_checks import symbols
ENGINE='script.module.cbr.engine';VIDEO='plugin.video.stremio.bridge';WIZARD='script.crb.wizard'
with ZipFile(ROOT/'android/packages'/ENGINE/(ENGINE+'-0.1.1.zip')) as z:
 old=z.read(ENGINE+'/resources/lib/android-arm7/libcbrengine.so')
 assert hashlib.sha256(old).hexdigest()=='1c7186a2f097d8060afd2f967bda7a4da2056ef440578b704effa62a64fb84f0'
 try:symbols(old)
 except AssertionError as error:assert 'DT_HASH missing' in str(error)
 else:raise AssertionError('Original reported failure was not reproduced')
print('Original screenshot library reproduced: DT_HASH missing')
with ZipFile(ROOT/'engine.zip') as z:
 assert z.testzip() is None
 assert E.fromstring(z.read(ENGINE+'/addon.xml')).get('version')=='0.1.2'
 checks=json.loads(z.read(ENGINE+'/resources/checksums.json'))
 for cpu,klass,machine in [('android-arm7',1,40),('android-arm64',2,183),('android-amd64',2,62)]:
  raw=z.read(ENGINE+'/resources/lib/'+cpu+'/libcbrengine.so');assert hashlib.sha256(raw).hexdigest()==checks[cpu]
  result=symbols(raw);assert result['elf_class']==klass and result['machine']==machine
  if klass==2:assert result['page_alignment']>=16384
  print(cpu,'valid SysV and GNU hash lookup for CBRStart/CBRStop, matching ABI/checksum')
 for name in z.namelist():
  if name.endswith('.py'):ast.parse(z.read(name).decode('utf-8-sig'),feature_version=(3,8))
with ZipFile(ROOT/'cbr0123.zip') as z:
 assert z.testzip() is None
 manifest=E.fromstring(z.read(VIDEO+'/addon.xml'));assert manifest.get('version')=='0.12.3'
 assert manifest.find("requires/import[@addon='"+ENGINE+"']").get('version')=='0.1.2'
 assert json.loads(z.read(VIDEO+'/resources/defaults/release-components.json'))[ENGINE]=='0.1.2'
print('Video update requires the fixed engine automatically')
with ZipFile(ROOT/'fulla043.zip') as z:
 assert z.testzip() is None
 assert E.fromstring(z.read(WIZARD+'/addon.xml')).get('version')=='0.4.3'
 prefix=WIZARD+'/resources/bundle/'
 for item in json.loads(z.read(prefix+'packages.json'))['packages']:
  raw=z.read(prefix+item['file']);assert hashlib.sha256(raw).hexdigest()==item['sha256']
  if item['id']==ENGINE:
   assert item['version']=='0.1.2'
   with ZipFile(BytesIO(raw)) as nested:
    checks=json.loads(nested.read(ENGINE+'/resources/checksums.json'));assert set(checks)=={'android-arm7','android-arm64'}
    for cpu in checks:
     data=nested.read(ENGINE+'/resources/lib/'+cpu+'/libcbrengine.so');assert hashlib.sha256(data).hexdigest()==checks[cpu];symbols(data)
assert (ROOT/'fulla043.zip').stat().st_size<100*1024*1024
assert (ROOT/'fulla043.zip').read_bytes()==(ROOT/'fulla.zip').read_bytes()
assert (ROOT/'cbr0123.zip').read_bytes()==(ROOT/'video.zip').read_bytes()
p=ROOT/'android/addons.xml';raw=p.read_bytes();assert hashlib.md5(raw).hexdigest()==p.with_suffix('.xml.md5').read_text().strip()
feed=E.fromstring(raw)
for identity,version in [(VIDEO,'0.12.3'),(ENGINE,'0.1.2'),(WIZARD,'0.4.3'),('skin.crimsonbloodrequiem','0.2.1')]:assert feed.find("addon[@id='"+identity+"']").get('version')==version
unchanged=subprocess.check_output(['git','-c','safe.directory='+str(ROOT).replace('\\','/'),'diff','--name-only','--','windows','cbrwindows.zip','full.zip'],cwd=ROOT,text=True)
assert not unchanged,'Windows release unexpectedly changed'
print('ARM full installer, nested checksums, size limit, aliases and Android repository feed pass; Windows unchanged')
