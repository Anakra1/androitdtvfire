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

news='0.11.3: UK IPTV and NoCords Pluto live TV, dedicated Pluto channel group, real US guide and clear availability notices where listings are missing.'
videos={};manifests={};skins={};skin_meta={}
for platform in ['android','windows']:
    files=read(ROOT/platform/'packages'/VIDEO/(VIDEO+'-0.11.2.zip'))
    for source in (HERE/'overlay').rglob('*'):
        if source.is_file():files[VIDEO+'/'+source.relative_to(HERE/'overlay').as_posix()]=source.read_bytes()
    manifests[platform]=set_meta(files,VIDEO,'0.11.3',news)
    videos[platform]=package(platform,VIDEO,'0.11.3',files)
    files=read(ROOT/platform/'packages'/SKIN/(SKIN+'-0.1.2.zip'))
    for source in (HERE/'skin-overlay').rglob('*'):
        if source.is_file():files[SKIN+'/'+source.relative_to(HERE/'skin-overlay').as_posix()]=source.read_bytes()
    skin_meta[platform]=set_meta(files,SKIN,'0.1.3','Native channel-group tabs on TV channels and guide. TV opens the CBR guide. Clear missing-programme information.')
    skins[platform]=package(platform,SKIN,'0.1.3',files)

wizards={};wizard_meta={}
for platform in ['android','windows']:
    files=read(ROOT/platform/'packages'/WIZARD/(WIZARD+'-0.3.2.zip'))
    meta=set_meta(files,WIZARD,'0.3.3','Includes CBR 0.11.3 and skin 0.1.3: UK and Pluto live TV, native group tabs and programme availability notices.')
    if platform=='android':
        prefix=WIZARD+'/resources/bundle/';bundle=json.loads(files[prefix+'packages.json'])
        for identity,version,path in [(VIDEO,'0.11.3',videos[platform]),(SKIN,'0.1.3',skins[platform])]:
            item=next(i for i in bundle['packages']if i['id']==identity);raw=path.read_bytes()
            item.update(version=version,sha256=hashlib.sha256(raw).hexdigest());files[prefix+item['file']]=raw
        files[prefix+'packages.json']=json.dumps(bundle,indent=2).encode()
    else:
        for dep in meta.find('requires'):
            if dep.get('addon')==VIDEO:dep.set('version','0.11.3')
            if dep.get('addon')==SKIN:dep.set('version','0.1.3')
        files[WIZARD+'/addon.xml']=ET.tostring(meta,encoding='utf-8',xml_declaration=True)
    wizard_meta[platform]=meta
    wizards[platform]=package(platform,WIZARD,'0.3.3',files)
for platform in ['android','windows']:
    path=ROOT/platform/'addons.xml';feed=ET.parse(path).getroot()
    for meta in [manifests[platform],wizard_meta[platform],skin_meta[platform]]:
        for old in list(feed):
            if old.get('id')==meta.get('id'):feed.remove(old)
        feed.append(meta)
    raw=ET.tostring(feed,encoding='utf-8',xml_declaration=True);path.write_bytes(raw)
    path.with_suffix('.xml.md5').write_text(hashlib.md5(raw).hexdigest(),encoding='ascii')
for alias,source in [('cbr0113.zip',videos['android']),('video.zip',videos['android']),('cbrwindows.zip',videos['windows']),
                     ('fulla033.zip',wizards['android']),('fulla.zip',wizards['android']),('full.zip',wizards['windows'])]:
    shutil.copy2(source,ROOT/alias)
for platform,folder in [('android','Fire-TV-Android'),('windows','Windows')]:
    shutil.copy2(videos[platform],ROOT/'downloads'/folder/videos[platform].name)
    shutil.copy2(wizards[platform],ROOT/'downloads'/folder/'CBR-Full-Install-0.3.3.zip')
index=(ROOT/'index.html').read_text(encoding='utf8')
for name in ['cbr0113.zip','video.zip','cbrwindows.zip','fulla033.zip','fulla.zip','full.zip']:
    size=(ROOT/name).stat().st_size;pattern=r'(<a href="'+re.escape(name)+r'">'+re.escape(name)+r'</a></td><td>)\d+ B'
    if re.search(pattern,index):index=re.sub(pattern,lambda m:m[1]+str(size)+' B',index)
    else:index=index.replace('</table>',f'<tr><td><a href="{name}">{name}</a></td><td>{size} B</td></tr>\n</table>')
(ROOT/'index.html').write_text(index,encoding='utf8')
for path in (ROOT/'website').glob('*.html'):
    text=path.read_text(encoding='utf8').replace('0.11.2','0.11.3').replace('0.3.2','0.3.3').replace('cbr0112','cbr0113').replace('fulla032','fulla033')
    path.write_text(text,encoding='utf8')
print('Built CBR 0.11.3, skin 0.1.3 and wizard 0.3.3 for Windows and Android.')
