"""Prepare both complete installers and draft feeds locally. Does not publish or replace aliases."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
from io import BytesIO
import hashlib
import json
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'outputs/release0127-stage'
VIDEO = 'plugin.video.stremio.bridge'
WIZARD = 'script.crb.wizard'


def read(path):
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        return {n:archive.read(n) for n in archive.namelist() if not n.endswith('/')}


report = {}
for platform in ('windows','android'):
    video = OUT / platform / (VIDEO + '-0.12.7.zip')
    video_files = read(video)
    video_meta = ET.fromstring(video_files[VIDEO + '/addon.xml'])
    previous = read(ROOT / platform / 'packages' / WIZARD / (WIZARD + '-0.4.4.zip'))
    files = dict(previous)
    meta_path = WIZARD + '/addon.xml'
    meta = ET.fromstring(files[meta_path]); meta.set('version','0.4.6')
    meta.find("extension[@point='xbmc.addon.metadata']/news").text = 'Includes CBR 0.12.7: boxing main events with expected link windows, optional Real-Debrid device sign-in and Back to Kodi Settings. No account credentials are bundled.'
    if platform == 'android':
        prefix = WIZARD + '/resources/bundle/'
        bundle = json.loads(files[prefix + 'packages.json'])
        entry = next(e for e in bundle['packages'] if e['id'] == VIDEO)
        raw = video.read_bytes()
        entry.update(version='0.12.7',sha256=hashlib.sha256(raw).hexdigest())
        files[prefix + entry['file']] = raw
        files[prefix + 'packages.json'] = json.dumps(bundle,indent=2).encode('utf-8')
        for name, content in previous.items():
            if name.endswith('.zip') and name != prefix + entry['file']:
                assert files[name] == content
        for nested in bundle['packages']:
            raw = files[prefix + nested['file']]
            assert hashlib.sha256(raw).hexdigest() == nested['sha256']
            with ZipFile(BytesIO(raw)) as archive:
                assert ET.fromstring(archive.read(nested['id'] + '/addon.xml')).get('version') == nested['version']
    else:
        for entry in meta.find('requires'):
            if entry.get('addon') == VIDEO:entry.set('version','0.12.7')
    files[meta_path] = ET.tostring(meta,encoding='utf-8',xml_declaration=True)
    target = OUT / platform / (WIZARD + '-0.4.6.zip')
    with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=7) as archive:
        for name, raw in files.items():
            archive.writestr(name,raw,compress_type=ZIP_STORED if name.endswith('.zip') else ZIP_DEFLATED)
    assert target.stat().st_size < 100 * 1024 * 1024
    assert read(target)[meta_path] == files[meta_path]
    feed = ET.parse(ROOT / platform / 'addons.xml').getroot()
    for item in (video_meta,meta):
        for old in list(feed):
            if old.get('id') == item.get('id'):feed.remove(old)
        feed.append(item)
    raw = ET.tostring(feed,encoding='utf-8',xml_declaration=True)
    (OUT/platform/'addons.xml').write_bytes(raw)
    (OUT/platform/'addons.xml.md5').write_text(hashlib.md5(raw).hexdigest(),encoding='ascii')
    report[platform] = dict(video='0.12.7',wizard='0.4.6',full_installer=str(target),
        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),other_android_bundles_unchanged=True if platform=='android' else None,
        feed='draft only',published=False)
(OUT/'installers-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Both full installers and draft repository feeds prepared locally; nothing published or replaced.')
