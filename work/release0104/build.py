"""Android sports-menu update; retain the existing skin and native components."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import ast, hashlib, json, re, shutil, xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
VIDEO='plugin.video.stremio.bridge'
WIZARD='script.crb.wizard'
unchanged={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in
    ('windows/addons.xml','windows/addons.xml.md5','cbrwindows.zip','full.zip','w090.zip','a090.zip','fulla022.zip',
     'android/packages/skin.crimsonbloodrequiem/skin.crimsonbloodrequiem-0.1.2.zip')}

def read_zip(path):
    with ZipFile(path)as archive:return {n:archive.read(n)for n in archive.namelist()if not n.endswith('/')and'__pycache__'not in n}

def package(identity,version,files):
    path=ROOT/'android/packages'/identity/(identity+'-'+version+'.zip')
    path.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(path,'w',ZIP_DEFLATED,compresslevel=7)as archive:
        for name,raw in sorted(files.items()):
            if name.endswith('.py'):ast.parse(raw.decode('utf-8-sig'),feature_version=(3,8))
            if name.endswith('.json'):json.loads(raw)
            if name.endswith('.xml'):ET.fromstring(raw)
            archive.writestr(name,raw,compress_type=ZIP_STORED if name.endswith('.zip')else ZIP_DEFLATED)
    with ZipFile(path)as archive:assert archive.testzip()is None
    return path

files=read_zip(ROOT/'android/packages'/VIDEO/(VIDEO+'-0.10.3.zip'))
for source in (HERE/'overlay').rglob('*.py'):
    files[VIDEO+'/'+source.relative_to(HERE/'overlay').as_posix()]=source.read_bytes()
files[VIDEO+'/README.md']=(HERE/'README.md').read_bytes()
metadata=ET.fromstring(files[VIDEO+'/addon.xml']);metadata.set('version','0.10.4')
metadata.find("extension[@point='xbmc.addon.metadata']/news").text='0.10.4: Sport-first event/channel menus, merged compatible source alternatives and optional links to installed Crew sports menus. DaddyLive remains disabled after failed playback tests. Restart Kodi after updating.'
files[VIDEO+'/addon.xml']=ET.tostring(metadata,encoding='utf8',xml_declaration=True)
assert not any('daddy_proxy' in n or 'daddy_vendor'in n for n in files)
video=package(VIDEO,'0.10.4',files)

wizard_files=read_zip(ROOT/'android/packages'/WIZARD/(WIZARD+'-0.2.2.zip'))
wizard_meta=ET.fromstring(wizard_files[WIZARD+'/addon.xml']);wizard_meta.set('version','0.2.3')
wizard_files[WIZARD+'/addon.xml']=ET.tostring(wizard_meta,encoding='utf8',xml_declaration=True)
prefix=WIZARD+'/resources/bundle/'
bundled=json.loads(wizard_files[prefix+'packages.json'])
item=next(i for i in bundled['packages']if i['id']==VIDEO)
raw=video.read_bytes();item.update(version='0.10.4',sha256=hashlib.sha256(raw).hexdigest())
wizard_files[prefix+item['file']]=raw
wizard_files[prefix+'packages.json']=json.dumps(bundled,indent=2).encode()
wizard=package(WIZARD,'0.2.3',wizard_files)
assert wizard.stat().st_size<100*1024*1024

feed=ET.parse(ROOT/'android/addons.xml').getroot()
for new in (metadata,wizard_meta):
    for old in list(feed):
        if old.get('id')==new.get('id'):feed.remove(old)
    feed.append(new)
raw=ET.tostring(feed,encoding='utf8',xml_declaration=True)
(ROOT/'android/addons.xml').write_bytes(raw)
(ROOT/'android/addons.xml.md5').write_text(hashlib.md5(raw).hexdigest(),encoding='ascii')
for name,source in (('video.zip',video),('cbr0104.zip',video),('fulla.zip',wizard),('fulla023.zip',wizard)):
    shutil.copy2(source,ROOT/name)
download=ROOT/'downloads/Fire-TV-Android'
shutil.copy2(video,download/(VIDEO+'-0.10.4-android.zip'))
shutil.copy2(wizard,download/'CBR-Full-Install-0.2.3.zip')
index=(ROOT/'index.html').read_text(encoding='utf8')
index=re.sub(r'(<a href="fulla.zip">fulla.zip</a></td><td>)\d+ B',lambda m:m[1]+str(wizard.stat().st_size)+' B',index)
for name,path in (('fulla023.zip',wizard),('cbr0104.zip',video)):
    if f'href="{name}"'not in index:
        index=index.replace('</table>',f'<tr><td><a href="{name}">{name}</a></td><td>{path.stat().st_size} B</td></tr>\n</table>')
(ROOT/'index.html').write_text(index,encoding='utf8')
for name,digest in unchanged.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
(HERE/'unchanged.json').write_text(json.dumps(unchanged,indent=2),encoding='utf8')
print('Built Android video 0.10.4 and full installer 0.2.3; skin/native components and Windows release archives retained.')
