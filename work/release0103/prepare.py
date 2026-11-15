"""Merge reviewed Windows changes into the released Android entry point."""
from pathlib import Path
from zipfile import ZipFile
import ast, json, shutil, sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OVER=HERE/'overlay'
P='plugin.video.stremio.bridge/'
with ZipFile(ROOT/'android/packages/plugin.video.stremio.bridge/plugin.video.stremio.bridge-0.10.1.zip')as z:
    base=z.read(P+'addon.py').decode('utf8').replace('\r\n','\n')
    defaults=z.read(P+'resources/lib/defaults.py').decode('utf8').replace('\r\n','\n')
windows=(ROOT/'work/bbc-uk-movies/addon.py').read_text(encoding='utf8')
function=windows[windows.index('def new_movies():'):windows.index('def manage():')]
base=base.replace('def manage():',function+'def manage():',1)
base=base.replace("        elif action == 'tools':","        elif action == 'new_movies':\n            new_movies()\n        elif action == 'tools':",1)
base=base.replace("    li = xbmcgui.ListItem(path=path)\n    li.getVideoInfoTag().setTitle(row['name'])",
    "    li = xbmcgui.ListItem(path=path)\n    if urlsplit(path.split('|', 1)[0]).path.lower().endswith('.mpd'):\n        li.setContentLookup(False)\n        li.setMimeType('application/dash+xml')\n        li.setProperty('inputstream', 'inputstream.adaptive')\n    li.getVideoInfoTag().setTitle(row['name'])")
(OVER/'addon.py').write_text(base,encoding='utf8')
s=(ROOT/'work/bbc-uk-movies/m3u.py').read_text(encoding='utf8')
s=s.replace("        rows = [row for row in rows if row['tvg_id'] in allowed]", "        rows = [dict(row, epg_id=entry.get('epg_ids', {}).get(row['tvg_id'], row['tvg_id']))\n                for row in rows if row['tvg_id'] in allowed]")
(OVER/'resources/lib/m3u.py').write_text(s,encoding='utf8')
s=(ROOT/'work/bbc-uk-movies/pvr.py').read_text(encoding='utf8')
s=s.replace("'Freeview', 'Sky',", "'Freeview',")
s=s.replace("    if country == 'GB' and name.startswith('sky '):\n        groups.append('Sky')\n",'')
s=s.replace("if not any(g in groups for g in ('Freeview', 'Sky')):", "if not any(g in groups for g in ('Freeview', 'UK TV')):")
s=s.replace("groups=group_names(meta['name'], meta.get('genres') or [], country), variants=[]))",
    "groups=group_names(meta['name'], meta.get('genres') or [], country),\n                                          visible=not (country == 'GB' and name in {'channel 4', 'channel 5', 'sky news weather'}), variants=[]))")
s=s.replace("    return [dict(row, **overrides.get(row['id'], {})) for row in rows]", "    result = []\n    for row in rows:\n        row = dict(row, **overrides.get(row['id'], {}))\n        row['groups'] = [g for g in row['groups'] if g != 'Sky'] or ['Other channels']\n        result.append(row)\n    return result")
s=s.replace("    if not filename:\n        number = 1908001", """    revision = os.path.join(profile, 'cbr-guide-0103.json')
    if filename and not os.path.exists(revision) and existing.get('m3uPath') == m3u:
        # Kodi retains empty backend groups. Retire only the CBR-owned instance
        # and create a fresh instance on this one-time guide revision. Keep the
        # previous configuration disabled for rollback; never touch TV databases.
        retired = ET.Element('settings', {'version': '2'})
        for key, value in dict(existing, kodi_addon_instance_name='CBR TV (previous)',
                               kodi_addon_instance_enabled='false').items():
            ET.SubElement(retired, 'setting', {'id': key}).text = value
        atomically(filename, ET.tostring(retired, encoding='utf-8', xml_declaration=True))
        filename = None
    if not filename:
        number = 1908001""")
s=s.replace("    return filename\n", "    atomically(revision, json.dumps({'instance': os.path.basename(filename)}).encode('utf8'))\n    return filename\n")
(OVER/'resources/lib/pvr.py').write_text(s,encoding='utf8')
defaults=defaults.replace('    ensure_live_defaults(store, addon_path, force)', '    ensure_live_defaults(store, addon_path, force)\n    ensure_tv_0103(store, addon_path, force)',1)
defaults+='''

def ensure_tv_0103(store, addon_path, force=False):
    marker = os.path.join(store.root, 'bbc-uk-tv-defaults-0103.json')
    if not force and store.read(marker):
        return
    from . import pvr, programmes
    path = os.path.join(addon_path, 'resources', 'defaults', 'bbc-duckkota.json')
    with open(path, encoding='utf8') as source:
        bundled = json.load(source)
    entries = store.providers()
    keys = []
    for template in bundled:
        existing = next((e for e in entries if e['url'] == template['url']), None)
        if existing is None:
            existing = dict(template, key=hashlib.sha256(template['url'].encode()).hexdigest()[:24], enabled=True)
            entries.append(existing)
        else:
            for name in ('include_tvg_ids', 'epg_ids', 'priority'):
                if name in template:
                    existing.setdefault(name, template[name])
        keys.append(existing['key'])
    store.save_providers(entries)
    config = pvr.config(store)
    sources = pvr.sources(store)
    selected = config.get('selected')
    if selected is None:
        selected = [s['key'] for s in sources if s['default']]
    config['selected'] = list(dict.fromkeys(selected + [s['key'] for s in sources if s['provider'] in keys and s['catalog']['id'] == 'm3u_uk']))
    for row in store.read(os.path.join(store.root, 'pvr-channels.json'), []):
        if programmes.normalized(row['name'], True) in {'channel 4', 'channel 5', 'sky news weather'} and any(programmes.country_for(v['meta'], v) == 'GB' for v in row['variants']):
            previous = config.setdefault('overrides', {}).get(row['id'], {})
            config['overrides'][row['id']] = dict(name=previous.get('name', row['name']), number=previous.get('number', row['number']),
                groups=[g for g in previous.get('groups', row['groups']) if g != 'Sky'] or ['UK TV'], visible=False)
    pvr.save_config(store, config)
    guide = programmes.settings(store)
    url = 'https://duckkota.github.io/iptv/epg/uk.xml.gz'
    if not any(f['url'] == url for f in guide['feeds']):
        guide['feeds'].append(dict(key=programmes.feed_key(url), label='UK TV guide', url=url, country='GB', enabled=True))
        programmes.save_settings(store, guide)
        programmes.request_refresh(store)
    if config.get('enabled'):
        pvr.refresh(store)
    store.write(marker, True)
'''
(OVER/'resources/lib/defaults.py').write_text(defaults,encoding='utf8')
sys.path.insert(0,str(ROOT/'work/samsung090pc/plugin.video.stremio.bridge'))
from resources.lib.m3u import manifest
duck='https://duckkota.github.io/iptv/playlists/best.m3u'
bbc='https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_uk.m3u8'
bmanifest=manifest(bbc,[{'country':'GB'}]);bmanifest['catalogs']=[dict(id='m3u_uk',type='tv',name='BBC UK',country='GB',extra=[dict(name='search',isRequired=False)])]
items=[dict(url=duck,label='DuckKota TV',kind='m3u',scope_types=['tv'],live_group='tv',manifest=manifest(duck)),
       dict(url=bbc,label='BBC UK (Free-TV)',kind='m3u',scope_types=['tv'],live_group='tv',priority=10,
            include_tvg_ids=['BBCOne.uk','BBCTwo.uk','BBCThree.uk','BBCFour.uk','BBCAlba.uk','BBCScotland.uk','BBCNews.uk','BBCParliament.uk','CBBC.uk','CBeebies.uk'],
            epg_ids={'BBCOne.uk':'BBC.One.Yorks.HD.uk'},manifest=bmanifest)]
(OVER/'resources/defaults/bbc-duckkota.json').write_text(json.dumps(items,indent=2),encoding='utf8')
for path in OVER.rglob('*'):
    if path.suffix not in ('.py', '.json'):continue
    text='\n'.join(line.rstrip()for line in path.read_text(encoding='utf8').splitlines()).rstrip()+'\n'
    path.write_text(text,encoding='utf8',newline='\n')
    if path.suffix=='.py':ast.parse(text)
assert "li.setProperty('inputstream', 'inputstream.adaptive')" in (OVER/'addon.py').read_text()
print('Android 0.10.3 overlay prepared')
