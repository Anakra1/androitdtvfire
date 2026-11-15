"""Build the Android-only, repository-independent full installer."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
ID='script.crb.wizard'
VERSION='0.2.1'
unchanged={name:hashlib.sha256((ROOT/name).read_bytes()).digest() for name in
           ('cbrwindows.zip','windows/addons.xml','windows/addons.xml.md5','full.zip')}
with ZipFile(ROOT/'full.zip')as archive:
    files={n:archive.read(n)for n in archive.namelist() if not n.endswith('/')}
manifest=ET.fromstring(files[ID+'/addon.xml'])
manifest.set('version',VERSION)
requires=manifest.find('requires')
for dependency in list(requires):
    if dependency.get('addon')!='xbmc.python':requires.remove(dependency)
metadata=manifest.find("extension[@point='xbmc.addon.metadata']")
metadata.find('platform').text='android'
metadata.find('summary').text='Android / Fire TV full install with the CBR skin included'
metadata.find('description').text='Self-contained Android setup. Includes the CBR skin, video add-on, torrent engine, repository and Kodi 21 ARM IPTV clients. Install this ZIP, open CBR Setup Wizard and run Full install. No CBR repository installation is required first.'
files[ID+'/addon.xml']=ET.tostring(manifest,encoding='utf8',xml_declaration=True)
for path in (HERE/'wizard').glob('*.py'):
    ast.parse(path.read_text(encoding='utf8'))
    files[ID+'/'+path.name]=path.read_bytes()

packages=[]
def include(path,identity,label,name,**options):
    raw=path.read_bytes()
    with ZipFile(path)as archive:component=ET.fromstring(archive.read(identity+'/addon.xml'))
    files[ID+'/resources/bundle/'+name]=raw
    packages.append(dict(id=identity,label=label,file=name,version=component.get('version'),
                         sha256=hashlib.sha256(raw).hexdigest(),**options))

engine=ROOT/'outputs/verified-live-full021-arm-engine.zip'
with ZipFile(ROOT/'android/packages/script.module.cbr.engine/script.module.cbr.engine-0.1.0.zip')as source,ZipFile(engine,'w',ZIP_DEFLATED,compresslevel=7)as target:
    for item in source.infolist():
        if '/resources/lib/android-amd64/'not in item.filename and not item.is_dir():
            target.writestr(item,source.read(item.filename))
include(engine,
        'script.module.cbr.engine','CBR Playback Engine','engine.zip')
include(ROOT/'android/packages/plugin.video.stremio.bridge/plugin.video.stremio.bridge-0.10.1.zip',
        'plugin.video.stremio.bridge','CBR movies, series and TV','video.zip')
include(ROOT/'android/packages/skin.crimsonbloodrequiem/skin.crimsonbloodrequiem-0.1.1.zip',
        'skin.crimsonbloodrequiem','CBR crimson space skin','skin.zip')
include(ROOT/'repository.cbr.zip','repository.crb.android','CBR update repository','repository.zip')
for dependency in json.loads((HERE/'official-inputstreams.json').read_text(encoding='utf8')):
    path=ROOT/'outputs'/dependency['cache']
    if not path.exists():
        with urllib.request.urlopen(dependency['source'],timeout=45)as response:path.write_bytes(response.read())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==dependency['sha256']
    include(path,dependency['id'],dependency['id'],dependency['id']+'-'+dependency['cpu']+'.zip',
            cpu=dependency['cpu'],kodi_major=21)
checksums={'android-armv7':'b5684b422f9b6ed3ed38263e77ffae8dabfcf23659d511c88dc0ab154035c02b',
           'android-aarch64':'c0281820953fbc16014472ddf5ca911720500a090ca9816bab7fd85da47c6a50'}
for cpu,checksum in checksums.items():
    path=ROOT/'outputs'/('verified-live-full021-'+cpu+'.zip')
    if not path.exists():
        url='https://mirrors.kodi.tv/addons/omega/pvr.iptvsimple+'+cpu+'/pvr.iptvsimple-21.11.0.zip'
        with urllib.request.urlopen(url,timeout=45)as response:path.write_bytes(response.read())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==checksum
    include(path,'pvr.iptvsimple','Kodi TV client',cpu+'.zip',cpu=cpu,kodi_major=21)
files[ID+'/resources/bundle/packages.json']=json.dumps({'platform':'android','packages':packages},indent=2).encode()
folder=ROOT/'android/packages'/ID;folder.mkdir(parents=True,exist_ok=True)
package=folder/(ID+'-'+VERSION+'.zip')
with ZipFile(package,'w',ZIP_DEFLATED,compresslevel=7)as archive:
    for name,raw in sorted(files.items()):
        archive.writestr(name,raw,compress_type=ZIP_STORED if name.endswith('.zip')else ZIP_DEFLATED)
assert package.stat().st_size<100*1024*1024
with ZipFile(package)as archive:assert archive.testzip()is None
for path in (ROOT/'fulla.zip',ROOT/'downloads/Fire-TV-Android/CBR-Full-Install-0.2.1.zip'):
    shutil.copy2(package,path)
feed=ET.parse(ROOT/'android/addons.xml').getroot()
for old in list(feed):
    if old.get('id')==ID:feed.remove(old)
feed.append(manifest)
raw=ET.tostring(feed,encoding='utf8',xml_declaration=True)
(ROOT/'android/addons.xml').write_bytes(raw)
(ROOT/'android/addons.xml.md5').write_text(hashlib.md5(raw).hexdigest(),encoding='ascii')
index=(ROOT/'index.html').read_text(encoding='utf8')
index=re.sub(r'<tr><td><a href="fulla\.zip">.*?</tr>\s*','',index)
row=f'<tr><td><a href="fulla.zip">fulla.zip</a></td><td>{package.stat().st_size} B</td></tr>\n'
index=index.replace('<tr><td><a href="full.zip">',row+'<tr><td><a href="full.zip">')
(ROOT/'index.html').write_text(index,encoding='utf8')
subprocess.run([sys.executable,str(ROOT/'work/build_website.py')],check=True)
for name,digest in unchanged.items():assert hashlib.sha256((ROOT/name).read_bytes()).digest()==digest,name
print('Built Android fulla.zip:',round(package.stat().st_size/1048576,1),'MiB; Windows packages unchanged')
