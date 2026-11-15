"""Android-only update and self-contained installer; Windows releases stay frozen."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import ast, hashlib, json, re, shutil, xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
VIDEO='plugin.video.stremio.bridge'
SKIN='skin.crimsonbloodrequiem'
WIZARD='script.crb.wizard'
unchanged={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('windows/addons.xml','windows/addons.xml.md5','cbrwindows.zip','full.zip','w090.zip','a090.zip')}

def read_zip(path):
    with ZipFile(path)as z:return {n:z.read(n)for n in z.namelist()if not n.endswith('/') and '__pycache__'not in n}
def write_zip(identity,version,files):
    folder=ROOT/'android/packages'/identity;folder.mkdir(parents=True,exist_ok=True)
    path=folder/(identity+'-'+version+'.zip')
    with ZipFile(path,'w',ZIP_DEFLATED,compresslevel=7)as z:
        for n,raw in sorted(files.items()):
            if n.endswith('.py'):ast.parse(raw.decode('utf-8-sig'))
            if n.endswith('.json'):json.loads(raw.decode('utf-8-sig'))
            if n.endswith('.xml'):ET.fromstring(raw)
            z.writestr(n,raw,compress_type=ZIP_STORED if n.endswith('.zip')else ZIP_DEFLATED)
    with ZipFile(path)as z:assert z.testzip()is None
    return path

files=read_zip(ROOT/'android/packages'/VIDEO/(VIDEO+'-0.10.1.zip'))
for path in (HERE/'overlay').rglob('*'):
    if path.is_file()and'__pycache__'not in path.parts:files[VIDEO+'/'+path.relative_to(HERE/'overlay').as_posix()]=path.read_bytes()
manifest=ET.fromstring(files[VIDEO+'/addon.xml']);manifest.set('version','0.10.3')
meta=manifest.find("extension[@point='xbmc.addon.metadata']")
meta.find('news').text='0.10.3: BBC UK feeds and UK TV guide group; confirmed broken channels hidden; Sky guide tab removed; new CBR movie posters on home. Restart Kodi after updating.'
files[VIDEO+'/addon.xml']=ET.tostring(manifest,encoding='utf8',xml_declaration=True)
files[VIDEO+'/README.md']=(HERE/'README.md').read_bytes()
video=write_zip(VIDEO,'0.10.3',files)

skinfiles=read_zip(ROOT/'android/packages'/SKIN/(SKIN+'-0.1.1.zip'))
skinfiles[SKIN+'/xml/Home.xml']=(ROOT/'work/bbc-uk-movies/Home.xml').read_bytes()
skinmanifest=ET.fromstring(skinfiles[SKIN+'/addon.xml']);skinmanifest.set('version','0.1.2')
for dep in skinmanifest.find('requires'):
    if dep.get('addon')==VIDEO:dep.set('version','0.10.3')
skinfiles[SKIN+'/addon.xml']=ET.tostring(skinmanifest,encoding='utf8',xml_declaration=True)
skin=write_zip(SKIN,'0.1.2',skinfiles)

# Reuse the verified ARM bootstrap and native components without rebuilding them.
wizardfiles=read_zip(ROOT/'android/packages'/WIZARD/(WIZARD+'-0.2.1.zip'))
wizardmanifest=ET.fromstring(wizardfiles[WIZARD+'/addon.xml']);wizardmanifest.set('version','0.2.2')
wizardfiles[WIZARD+'/addon.xml']=ET.tostring(wizardmanifest,encoding='utf8',xml_declaration=True)
bundle=WIZARD+'/resources/bundle/'
packages=json.loads(wizardfiles[bundle+'packages.json'])
for identity,path in ((VIDEO,video),(SKIN,skin)):
    item=next(i for i in packages['packages']if i['id']==identity)
    raw=path.read_bytes();item['version']='0.10.3'if identity==VIDEO else'0.1.2';item['sha256']=hashlib.sha256(raw).hexdigest()
    wizardfiles[bundle+item['file']]=raw
wizardfiles[bundle+'packages.json']=json.dumps(packages,indent=2).encode()
wizard=write_zip(WIZARD,'0.2.2',wizardfiles)
assert wizard.stat().st_size<100*1024*1024

feed=ET.parse(ROOT/'android/addons.xml').getroot()
for new in (manifest,skinmanifest,wizardmanifest):
    for old in list(feed):
        if old.get('id')==new.get('id'):feed.remove(old)
    feed.append(new)
raw=ET.tostring(feed,encoding='utf8',xml_declaration=True)
(ROOT/'android/addons.xml').write_bytes(raw)
(ROOT/'android/addons.xml.md5').write_text(hashlib.md5(raw).hexdigest(),encoding='ascii')
for new,path in ((manifest,video),(skinmanifest,skin),(wizardmanifest,wizard)):
    folder=path.parent;content=read_zip(path)
    for a in new.findall("extension[@point='xbmc.addon.metadata']/assets/*"):
        if a.text and not a.text.startswith(('http:','https:')):
            target=folder/a.text;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content[new.get('id')+'/'+a.text])
for name,path in (('video.zip',video),('cbr0103.zip',video),('fulla.zip',wizard),('fulla022.zip',wizard)):
    shutil.copy2(path,ROOT/name)
download=ROOT/'downloads/Fire-TV-Android'
shutil.copy2(video,download/(VIDEO+'-0.10.3-android.zip'))
shutil.copy2(wizard,download/'CBR-Full-Install-0.2.2.zip')
index=(ROOT/'index.html').read_text(encoding='utf8')
index=re.sub(r'(<a href="fulla.zip">fulla.zip</a></td><td>)\d+ B',lambda m:m[1]+str(wizard.stat().st_size)+' B',index)
if 'href="cbr0103.zip"'not in index:index=index.replace('</table>',f'<tr><td><a href="cbr0103.zip">cbr0103.zip</a></td><td>{video.stat().st_size} B</td></tr>\n</table>')
if 'href="fulla022.zip"'not in index:index=index.replace('</table>',f'<tr><td><a href="fulla022.zip">fulla022.zip</a></td><td>{wizard.stat().st_size} B</td></tr>\n</table>')
(ROOT/'index.html').write_text(index,encoding='utf8')
for name,digest in unchanged.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
(HERE/'unchanged-windows.json').write_text(json.dumps(unchanged,indent=2))
print('Android video 0.10.3, skin 0.1.2, full installer 0.2.2 built. Windows release archives unchanged.')
