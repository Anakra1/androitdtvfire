"""Prepare reviewed release artifacts, full installers and public repository metadata."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
from io import BytesIO
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VIDEO, WIZARD = 'plugin.video.stremio.bridge', 'script.crb.wizard'
STAGED = ROOT / 'outputs/release0124-stage'


def read(path):
    with ZipFile(path) as z:
        assert z.testzip() is None
        return {n: z.read(n) for n in z.namelist() if not n.endswith('/')}


def meta(files, identity, version, news):
    node = ET.fromstring(files[identity + '/addon.xml'])
    node.set('version', version)
    node.find("extension[@point='xbmc.addon.metadata']/news").text = news
    files[identity + '/addon.xml'] = ET.tostring(node, encoding='utf-8', xml_declaration=True)
    return node


def write_zip(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w', ZIP_DEFLATED, compresslevel=7) as z:
        for name, raw in files.items():
            z.writestr(name, raw, compress_type=ZIP_STORED if name.endswith('.zip') else ZIP_DEFLATED)
    assert path.stat().st_size < 100 * 1024 * 1024


paths, aliases, report = [], {}, {}
for platform, old_wizard, folder in [('windows', '0.4.2', 'Windows'), ('android', '0.4.3', 'Fire-TV-Android')]:
    video = ROOT / platform / 'packages' / VIDEO / (VIDEO + '-0.12.4.zip')
    shutil.copy2(STAGED / platform / video.name, video)
    video_files = read(video)
    video_meta = ET.fromstring(video_files[VIDEO + '/addon.xml'])
    original = ROOT / platform / 'packages' / WIZARD / (WIZARD + '-' + old_wizard + '.zip')
    wizard_files = read(original)
    wizard_meta = meta(wizard_files, WIZARD, '0.4.4', 'Includes CBR 0.12.4 with categorised native and phone/PC source setup.')
    if platform == 'android':
        prefix = WIZARD + '/resources/bundle/'
        bundle = json.loads(wizard_files[prefix + 'packages.json'])
        entry = next(p for p in bundle['packages'] if p['id'] == VIDEO)
        payload = video.read_bytes()
        entry.update(version='0.12.4', sha256=hashlib.sha256(payload).hexdigest())
        wizard_files[prefix + entry['file']] = payload
        wizard_files[prefix + 'packages.json'] = json.dumps(bundle, indent=2).encode()
        # Preserve the exact tested ARM-only engine and all other nested components.
        for name, raw in read(original).items():
            if name.endswith('.zip') and name != prefix + entry['file']:
                assert wizard_files[name] == raw
    else:
        for dependency in wizard_meta.find('requires'):
            if dependency.get('addon') == VIDEO:
                dependency.set('version', '0.12.4')
        wizard_files[WIZARD + '/addon.xml'] = ET.tostring(wizard_meta, encoding='utf-8', xml_declaration=True)
    wizard = ROOT / platform / 'packages' / WIZARD / (WIZARD + '-0.4.4.zip')
    write_zip(wizard, wizard_files)
    if platform == 'android':
        for entry in bundle['packages']:
            raw = wizard_files[prefix + entry['file']]
            assert hashlib.sha256(raw).hexdigest() == entry['sha256']
            with ZipFile(BytesIO(raw)) as nested:
                nested_meta = ET.fromstring(nested.read(entry['id'] + '/addon.xml'))
                assert nested_meta.get('version') == entry['version']
    feed_path = ROOT / platform / 'addons.xml'
    feed = ET.parse(feed_path).getroot()
    for item in (video_meta, wizard_meta):
        for old in list(feed):
            if old.get('id') == item.get('id'):
                feed.remove(old)
        feed.append(item)
    raw = ET.tostring(feed, encoding='utf-8', xml_declaration=True)
    feed_path.write_bytes(raw)
    checksum = feed_path.with_suffix('.xml.md5')
    checksum.write_text(hashlib.md5(raw).hexdigest(), encoding='ascii')
    download_video = ROOT / 'downloads' / folder / video.name
    download_wizard = ROOT / 'downloads' / folder / 'CBR-Full-Install-0.4.4.zip'
    shutil.copy2(video, download_video)
    shutil.copy2(wizard, download_wizard)
    paths.extend([video, wizard, feed_path, checksum, download_video, download_wizard])
    if platform == 'android':
        aliases.update({'cbr0124.zip': video, 'video.zip': video, 'fulla044.zip': wizard, 'fulla.zip': wizard})
    else:
        aliases.update({'cbrwindows.zip': video, 'full.zip': wizard})
    report[platform] = {'video': '0.12.4', 'wizard': '0.4.4', 'bundle_verified': True,
                        'video_sha256': hashlib.sha256(video.read_bytes()).hexdigest(),
                        'wizard_sha256': hashlib.sha256(wizard.read_bytes()).hexdigest()}
for alias, source in aliases.items():
    path = ROOT / alias
    shutil.copy2(source, path)
    paths.append(path)
index = ROOT / 'index.html'
text = index.read_text(encoding='utf-8')
for name in aliases:
    size = (ROOT / name).stat().st_size
    pattern = r'(<a href="' + re.escape(name) + r'">' + re.escape(name) + r'</a></td><td>)\d+ B'
    if re.search(pattern, text):
        text = re.sub(pattern, lambda m: m[1] + str(size) + ' B', text)
    else:
        text = text.replace('</table>', '<tr><td><a href="{0}">{0}</a></td><td>{1} B</td></tr>\n</table>'.format(name, size))
index.write_text(text, encoding='utf-8')
paths.append(index)
for path in (ROOT / 'website').glob('*.html'):
    before = path.read_text(encoding='utf-8')
    text = re.sub(r'(data-version="(?:android|windows)">)0\.12\.[23]', r'\g<1>0.12.4', before)
    text = text.replace('0.4.2', '0.4.4').replace('0.4.3', '0.4.4').replace('fulla042', 'fulla044').replace('fulla043', 'fulla044').replace('cbr0123', 'cbr0124').replace('cbr0122', 'cbr0124')
    text = text.replace('CBR 0.12.2', 'CBR 0.12.4').replace('CBR 0.12.3', 'CBR 0.12.4')
    text = text.replace('Automatic updates from CBR 0.12.4', 'Automatic updates from CBR 0.12.2')
    if path.name in ('windows.html', 'android.html'):
        anchor = '<h2>Update without starting over.</h2>'
        note = '<div class="callout"><p><strong>New in CBR 0.12.4:</strong> open <strong>CBR Setup</strong> for separate Live TV, Movies, TV Series, Channel Listings, Programmes and Tools categories. The paired phone / PC page uses the same categories.</p></div>'
        if note not in text:
            text = text.replace(anchor, anchor + note)
    if text != before:
        path.write_text(text, encoding='utf-8')
        paths.append(path)
(STAGED / 'publish-verification.json').write_text(json.dumps(report, indent=2))
(STAGED / 'publish-paths.json').write_text(json.dumps([str(p.relative_to(ROOT)).replace('\\', '/') for p in paths], indent=2))
print('Prepared both repository feeds, full installers, aliases and website links; nested bundle hashes verified.')
