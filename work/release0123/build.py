"""CBR maintenance release: matching Windows and Android packages."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import ast, hashlib, json, re, shutil
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
VIDEO,WIZARD,SKIN='plugin.video.stremio.bridge','script.crb.wizard','skin.crimsonbloodrequiem'

def read(path):
    with ZipFile(path)as z:return {n:z.read(n)for n in z.namelist()if not n.endswith('/')and'__pycache__'not in n}

def package(platform,identity,version,files):
    path=ROOT/platform/'packages'/identity/(identity+'-'+version+'.zip');path.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(path,'w',ZIP_DEFLATED,compresslevel=7)as z:
        for name,raw in sorted(files.items()):
            if name.endswith('.py'):ast.parse(raw.decode('utf-8-sig'),feature_version=(3,8))
            if name.endswith('.xml'):ET.fromstring(raw)
            if name.endswith('.json'):json.loads(raw)
            z.writestr(name,raw,compress_type=ZIP_STORED if name.endswith('.zip')else ZIP_DEFLATED)
    assert path.stat().st_size<100*1024*1024
    return path

def set_meta(files,identity,version,news):
    a=ET.fromstring(files[identity+'/addon.xml']);a.set('version',version)
    extension=a.find("extension[@point='xbmc.addon.metadata']")
    node=extension.find('news')
    if node is None:node=ET.SubElement(extension,'news')
    node.text=news
    files[identity+'/addon.xml']=ET.tostring(a,encoding='utf-8',xml_declaration=True)
    return a


ENGINE='script.module.cbr.engine'
# Rebuild only Android packages. Windows and the shared skin are unchanged.
files=read(ROOT/'android/packages'/ENGINE/(ENGINE+'-0.1.1.zip'))
checks={}
import sys
sys.path.insert(0,str(HERE))
from elf_checks import symbols
for cpu in ('arm7','arm64','amd64'):
    raw=(HERE/'native-libs'/('android-'+cpu)/'libcbrengine.so').read_bytes()
    symbols(raw)
    files[ENGINE+'/resources/lib/android-'+cpu+'/libcbrengine.so']=raw
    checks['android-'+cpu]=hashlib.sha256(raw).hexdigest()
files[ENGINE+'/resources/checksums.json']=json.dumps(checks,indent=2).encode()
files[ENGINE+'/README.md']+=b'\nVersion 0.1.2: Android API 21 native builds include both legacy DT_HASH and GNU hash tables; ARM64 and x86_64 retain 16 KB load alignment.\n'
engine_meta=set_meta(files,ENGINE,'0.1.2','Compatibility fix: include legacy Android DT_HASH plus GNU hashes. Built against API 21 for older Fire TV/Android loaders.')
engine=package('android',ENGINE,'0.1.2',files)
files=read(ROOT/'android/packages'/VIDEO/(VIDEO+'-0.12.2.zip'))
video_meta=set_meta(files,VIDEO,'0.12.3','Requires CBR Playback Engine 0.1.2: fixes missing DT_HASH loader errors on older Fire TV/Android devices.')
for dep in video_meta.find('requires'):
    if dep.get('addon')==ENGINE:dep.set('version','0.1.2')
files[VIDEO+'/addon.xml']=ET.tostring(video_meta,encoding='utf-8',xml_declaration=True)
files[VIDEO+'/resources/defaults/release-components.json']=json.dumps({VIDEO:'0.12.3',WIZARD:'0.4.3',SKIN:'0.2.1',ENGINE:'0.1.2'}).encode()
video=package('android',VIDEO,'0.12.3',files)
files=read(ROOT/'android/packages'/WIZARD/(WIZARD+'-0.4.2.zip'))
wizard_meta=set_meta(files,WIZARD,'0.4.3','Android full installer includes Playback Engine 0.1.2 legacy-loader fix and CBR 0.12.3.')
prefix=WIZARD+'/resources/bundle/';bundle=json.loads(files[prefix+'packages.json'])
# The Fire TV full installer supports ARM32/ARM64, as before; keep x86_64
# in the repository engine but out of the self-contained ARM installer.
from io import BytesIO
arm_files={name:raw for name,raw in read(engine).items() if '/android-amd64/' not in name}
arm_files[ENGINE+'/resources/checksums.json']=json.dumps({k:v for k,v in checks.items() if k!='android-amd64'},indent=2).encode()
arm_buffer=BytesIO()
with ZipFile(arm_buffer,'w',ZIP_DEFLATED,compresslevel=7) as archive:
    for name,raw in sorted(arm_files.items()):archive.writestr(name,raw)
arm_payload=arm_buffer.getvalue()
for identity,version,path in [(VIDEO,'0.12.3',video),(ENGINE,'0.1.2',engine)]:
    item=next(p for p in bundle['packages'] if p['id']==identity);raw=arm_payload if identity==ENGINE else path.read_bytes()
    item.update(version=version,sha256=hashlib.sha256(raw).hexdigest());files[prefix+item['file']]=raw
files[prefix+'packages.json']=json.dumps(bundle,indent=2).encode()
wizard=package('android',WIZARD,'0.4.3',files)
path=ROOT/'android/addons.xml';feed=ET.parse(path).getroot()
for meta in (video_meta,wizard_meta,engine_meta):
    for old in list(feed):
        if old.get('id')==meta.get('id'):feed.remove(old)
    feed.append(meta)
raw=ET.tostring(feed,encoding='utf-8',xml_declaration=True);path.write_bytes(raw)
path.with_suffix('.xml.md5').write_text(hashlib.md5(raw).hexdigest(),encoding='ascii')
for alias,source in [('cbr0123.zip',video),('video.zip',video),('engine.zip',engine),('fulla043.zip',wizard),('fulla.zip',wizard)]:shutil.copy2(source,ROOT/alias)
for source,name in [(video,video.name),(engine,engine.name),(wizard,'CBR-Full-Install-0.4.3.zip')]:shutil.copy2(source,ROOT/'downloads/Fire-TV-Android'/name)
index=(ROOT/'index.html').read_text(encoding='utf-8')
for name in ['cbr0123.zip','video.zip','engine.zip','fulla043.zip','fulla.zip']:
    size=(ROOT/name).stat().st_size;pattern=r'(<a href="'+re.escape(name)+r'">'+re.escape(name)+r'</a></td><td>)\d+ B'
    if re.search(pattern,index):index=re.sub(pattern,lambda m:m[1]+str(size)+' B',index)
    else:index=index.replace('</table>',f'<tr><td><a href="{name}">{name}</a></td><td>{size} B</td></tr>\n</table>')
(ROOT/'index.html').write_text(index,encoding='utf-8')
p=ROOT/'website/android.html';text=p.read_text(encoding='utf-8').replace('0.12.2','0.12.3').replace('0.4.2','0.4.3').replace('cbr0122','cbr0123').replace('fulla042','fulla043');p.write_text(text,encoding='utf-8')
print('Built Android CBR 0.12.3, Playback Engine 0.1.2, full installer 0.4.3. Windows is unchanged.')
