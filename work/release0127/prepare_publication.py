"""Prepare approved public download aliases, repository feeds and release notes."""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,re,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
OUT=ROOT/'outputs/release0127-stage'
VIDEO='plugin.video.stremio.bridge';WIZARD='script.crb.wizard'
source=(ROOT/'work/release0126/prepare_installers.py').read_text(encoding='utf-8')
source=source.replace('release0126-stage','release0127-stage').replace('0.12.6','0.12.7').replace('0.4.5','0.4.6')
source=source.replace('optional Real-Debrid device sign-in and Back to Kodi Settings.','boxing main events with expected link windows, optional Real-Debrid device sign-in and Back to Kodi Settings.')
script=HERE/'prepare_installers.py';script.write_text(source,encoding='utf-8')
exec(compile(source,str(script),'exec'),{'__file__':str(script),'__name__':'__main__'})
paths=[]
for platform in ('windows','android'):
    for addon,version in ((VIDEO,'0.12.7'),(WIZARD,'0.4.6')):
        src=OUT/platform/(addon+'-'+version+'.zip')
        with ZipFile(src) as archive:
            assert archive.testzip() is None
            assert ET.fromstring(archive.read(addon+'/addon.xml')).get('version')==version
            assert not any('/addon_data/' in name or name.endswith('/real-debrid-auth.json') for name in archive.namelist())
        dest=ROOT/platform/'packages'/addon/src.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);paths.append(dest)
    for name in ('addons.xml','addons.xml.md5'):
        dest=ROOT/platform/name;shutil.copy2(OUT/platform/name,dest);paths.append(dest)
    raw=(ROOT/platform/'addons.xml').read_bytes()
    assert hashlib.md5(raw).hexdigest()==(ROOT/platform/'addons.xml.md5').read_text().strip()
aliases={
 'video.zip':('android',VIDEO,'0.12.7'),'cbr0127.zip':('android',VIDEO,'0.12.7'),
 'cbrwindows.zip':('windows',VIDEO,'0.12.7'),
 'fulla.zip':('android',WIZARD,'0.4.6'),'fulla046.zip':('android',WIZARD,'0.4.6'),
 'full.zip':('windows',WIZARD,'0.4.6')}
for name,(platform,addon,version) in aliases.items():
    dest=ROOT/name;shutil.copy2(OUT/platform/(addon+'-'+version+'.zip'),dest);paths.append(dest)
index=ROOT/'index.html';text=index.read_text(encoding='utf-8')
for name in aliases:
    size=(ROOT/name).stat().st_size
    pattern=r'(<a href="'+re.escape(name)+r'">[^<]+</a></td><td>)[^<]+'
    if re.search(pattern,text):text=re.sub(pattern,lambda m:m[1]+str(size)+' B',text)
    else:text=text.replace('</table>',f'<tr><td><a href="{name}">{name}</a></td><td>{size} B</td></tr>\n</table>')
index.write_text(text,encoding='utf-8');paths.append(index)
# Keep existing GitHub Pages download instructions pointed at this release.
for name in ('index.html','android.html','windows.html','guide.html','help.html'):
    page=ROOT/'website'/name
    text=page.read_text(encoding='utf-8')
    text=text.replace('0.12.4','0.12.7').replace('0.4.4','0.4.6').replace('cbr0124.zip','cbr0127.zip').replace('fulla044.zip','fulla046.zip')
    page.write_text(text,encoding='utf-8');paths.append(page)
page=ROOT/'website/updates.html';text=page.read_text(encoding='utf-8')
marker='<h2>Updates &amp; release history.</h2>'
entry='<article class="release-row"><div class="release-number">0.12.7</div><div><h3>23 November 2026 — Boxing main events</h3><p>Sports now includes a Boxing PPV main-event box with provider event pictures, local start times and an estimated link window from one hour before broadcast. Listings refresh every minute while the box is open; selecting an event checks fresh links. Missing links are reported clearly. Availability and PPV playback are not guaranteed.</p><p>Also includes Back to Kodi Settings and optional Real-Debrid device authorisation. The built-in player remains the default. Full installers use Setup Wizard 0.4.6; no personal source settings or sign-in credentials are bundled.</p><p><a href="../cbr0127.zip" download>Android add-on update</a> · <a href="../fulla046.zip" download>Android full installer</a> · <a href="../cbrwindows.zip" download>Windows add-on update</a></p></div></article>'
assert marker in text
if entry not in text:text=text.replace(marker,marker+entry,1)
text=text.replace('Latest install: CBR 0.12.4','Latest install: CBR 0.12.7').replace('Setup Wizard <strong>0.4.4','Setup Wizard <strong>0.4.6')
page.write_text(text,encoding='utf-8');paths.append(page)
(OUT/'publication-files.json').write_text(json.dumps([str(p.relative_to(ROOT)).replace('\\','/') for p in paths],indent=2),encoding='utf-8')
print('Prepared',len(paths),'public release files; source credentials and local audit files excluded.')
