"""Publish matching Windows/Android startup-check releases, retaining old ZIPs."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import ast
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VIDEO, WIZARD, SKIN = 'plugin.video.stremio.bridge', 'script.crb.wizard', 'skin.crimsonbloodrequiem'

def read(path):
    with ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith('/') and '__pycache__' not in n}

def package(platform, identity, version, files):
    path = ROOT/platform/'packages'/identity/(identity+'-'+version+'.zip')
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w', ZIP_DEFLATED, compresslevel=7) as z:
        for name, raw in sorted(files.items()):
            if name.endswith('.py'): ast.parse(raw.decode('utf-8-sig'), feature_version=(3, 8))
            if name.endswith('.xml'): ET.fromstring(raw)
            if name.endswith('.json'): json.loads(raw)
            z.writestr(name, raw, compress_type=ZIP_STORED if name.endswith('.zip') else ZIP_DEFLATED)
    return path

def meta(files, identity, version, platform):
    key=identity+'/addon.xml'; root=ET.fromstring(files[key]); root.set('version', version)
    root.find("extension[@point='xbmc.addon.metadata']/platform").text=platform
    files[key]=ET.tostring(root, encoding='utf8', xml_declaration=True)
    return root

android = read(ROOT/'cbr0104.zip')
service=android[VIDEO+'/service.py'].decode('utf8')
assert 'startup_updates' not in service
service=service.replace('from resources.lib.pvr import PVRUpdater',
    'from resources.lib.pvr import PVRUpdater\nfrom resources.lib.startup_updates import StartupUpdates')
service=service.replace('    setup = SetupController(',
    "    startup_updates = StartupUpdates(Store(root), addon, xbmc.executebuiltin,\n"
    "                                     lambda: xbmc.getIPAddress() not in ('', '0.0.0.0', '127.0.0.1', '::1'))\n"
    '    setup = SetupController(', 1)
service=service.replace("            if time.time() - installing > 45:",
    "            try:\n"
    "                startup_updates.poll(player, installing=time.time() - installing <= 45)\n"
    "            except Exception:\n"
    "                startup_updates.done = True\n"
    "                xbmc.log('CBR startup repository check could not run; normal Kodi updates remain available.', xbmc.LOGWARNING)\n"
    "            if time.time() - installing > 45:", 1)
android[VIDEO+'/service.py']=service.encode()
android[VIDEO+'/resources/lib/startup_updates.py']=(HERE/'overlay/resources/lib/startup_updates.py').read_bytes()
settings=android[VIDEO+'/resources/settings.xml'].decode('utf8')
settings=settings.replace('</settings>', '''  <category label="Updates">
    <setting id="startup_update_check" type="bool" label="Check repositories after Kodi starts" default="true" />
  </category>
</settings>''')
android[VIDEO+'/resources/settings.xml']=settings.encode()
am=meta(android, VIDEO, '0.10.5', 'android')
am.find("extension[@point='xbmc.addon.metadata']/news").text='0.10.5: Check Kodi repositories after an idle startup. Kodi handles automatic installation for repository-linked add-ons according to your update settings. Manual ZIP installs need a one-time repository selection.'
android[VIDEO+'/addon.xml']=ET.tostring(am, encoding='utf8', xml_declaration=True)
av=package('android', VIDEO, '0.10.5', android)

# Keep Windows native binaries and its full-setup module, then overlay current
# shared Python/resources. Android's engine dependency is not needed on Windows.
windows=read(ROOT/'cbrwindows.zip'); windows.update(android)
wm=meta(windows, VIDEO, '0.10.5', 'windows')
requires=wm.find('requires')
for dep in list(requires):
    if dep.get('addon')=='script.module.cbr.engine': requires.remove(dep)
windows[VIDEO+'/addon.xml']=ET.tostring(wm, encoding='utf8', xml_declaration=True)
wv=package('windows', VIDEO, '0.10.5', windows)
skin=ROOT/'android/packages'/SKIN/(SKIN+'-0.1.2.zip')
ws=ROOT/'windows/packages'/SKIN/skin.name
shutil.copy2(skin, ws)
sm=ET.fromstring(read(skin)[SKIN+'/addon.xml'])

awfiles=read(ROOT/'fulla023.zip')
awm=meta(awfiles, WIZARD, '0.2.4', 'android')
prefix=WIZARD+'/resources/bundle/'
items=json.loads(awfiles[prefix+'packages.json'])
entry=next(x for x in items['packages'] if x['id']==VIDEO)
raw=av.read_bytes(); entry.update(version='0.10.5', sha256=hashlib.sha256(raw).hexdigest())
awfiles[prefix+entry['file']]=raw
awfiles[prefix+'packages.json']=json.dumps(items, indent=2).encode()
aw=package('android', WIZARD, '0.2.4', awfiles)
wwfiles=read(ROOT/'full.zip')
wwm=meta(wwfiles, WIZARD, '0.2.1', 'windows')
for dep in wwm.find('requires'):
    if dep.get('addon')==VIDEO: dep.set('version', '0.10.5')
    if dep.get('addon')==SKIN: dep.set('version', '0.1.2')
wwfiles[WIZARD+'/addon.xml']=ET.tostring(wwm, encoding='utf8', xml_declaration=True)
ww=package('windows', WIZARD, '0.2.1', wwfiles)

for platform, manifests in [('android',[am,awm]),('windows',[wm,wwm,sm])]:
    path=ROOT/platform/'addons.xml'; feed=ET.parse(path).getroot()
    for new in manifests:
        for old in list(feed):
            if old.get('id')==new.get('id'): feed.remove(old)
        feed.append(new)
    raw=ET.tostring(feed, encoding='utf8', xml_declaration=True); path.write_bytes(raw)
    path.with_suffix('.xml.md5').write_text(hashlib.md5(raw).hexdigest(), encoding='ascii')
for alias, path in [('video.zip',av),('cbr0105.zip',av),('fulla.zip',aw),('fulla024.zip',aw),
                    ('cbrwindows.zip',wv),('full.zip',ww)]:
    shutil.copy2(path, ROOT/alias)
for folder, paths in [('Fire-TV-Android',[av,aw]),('Windows',[wv,ww])]:
    for path in paths: shutil.copy2(path, ROOT/'downloads'/folder/path.name)
index=(ROOT/'index.html').read_text(encoding='utf8')
import re
for name in ['video.zip','fulla.zip','cbrwindows.zip','full.zip','cbr0105.zip','fulla024.zip']:
    size=(ROOT/name).stat().st_size
    pattern=r'(<a href="'+re.escape(name)+r'">'+re.escape(name)+r'</a></td><td>)\d+ B'
    if re.search(pattern,index): index=re.sub(pattern,lambda m:m[1]+str(size)+' B',index)
    else: index=index.replace('</table>',f'<tr><td><a href="{name}">{name}</a></td><td>{size} B</td></tr>\n</table>')
(ROOT/'index.html').write_text(index, encoding='utf8')
print('Built CBR 0.10.5 for Windows/Android; full installers Android 0.2.4 / Windows 0.2.1.')
