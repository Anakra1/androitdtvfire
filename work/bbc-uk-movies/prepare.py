"""Stage the Windows BBC / UK guide / Movies home changes with backups."""
from pathlib import Path
import shutil, ast, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
KODI = Path('C:/Users/Chris/AppData/Roaming/Kodi')
ADDON = KODI/'addons/plugin.video.stremio.bridge'
SKIN = KODI/'addons/skin.crimsonbloodrequiem'
BACKUP = ROOT.parent.parent/'outputs/verified-live-bbc-uk-movies-20261115/backup'
FILES = {'m3u.py': ADDON/'resources/lib/m3u.py', 'pvr.py': ADDON/'resources/lib/pvr.py',
         'addon.py': ADDON/'addon.py', 'Home.xml': SKIN/'xml/Home.xml'}
for name, source in FILES.items():
    if not (BACKUP/name).exists(): shutil.copy2(source, BACKUP/name)

s = (BACKUP/'m3u.py').read_text(encoding='utf8')
s = s.replace('def clean_name(value):\n', "def clean_name(value):\n    value = re.sub(r'(?:\\s*[\\u24b6-\\u24e9])+\\s*$', '', value)\n")
s = s.replace("    if country_list:\n        rows =", "    if entry.get('include_tvg_ids') is not None:\n        allowed = set(entry['include_tvg_ids'])\n        rows = [row for row in rows if row['tvg_id'] in allowed]\n    if country_list:\n        rows =")
(ROOT/'m3u.py').write_text(s, encoding='utf8')

s = (BACKUP/'pvr.py').read_text(encoding='utf8')
s = s.replace("GROUPS = ('Freeview'", "GROUPS = ('UK TV', 'Freeview'")
s = s.replace("    groups = []\n", "    groups = ['UK TV'] if country == 'GB' else []\n")
s = s.replace("resource_type=cat['type'], live_group='tv', live_country=country, meta=meta)",
              "resource_type=cat['type'], live_group='tv', live_country=country, priority=entry.get('priority', 100), meta=meta)")
s = s.replace("row['variants'].sort(key=lambda c: 2 if", "row['variants'].sort(key=lambda c: (c.get('priority', 100), 2 if")
s = s.replace("else 1)\n        best =", "else 1))\n        best =")
(ROOT/'pvr.py').write_text(s, encoding='utf8')

s = (BACKUP/'addon.py').read_text(encoding='utf8')
function = '''def new_movies():
    """Poster-only directory for Kodi home widgets and the Movies menu."""
    import datetime
    import time
    year = str(datetime.date.today().year)
    candidates = [(e, c) for e, c in movie_catalogs() if c['id'] == 'year']
    candidates.sort(key=lambda pair: pair[0]['manifest'].get('id') != 'com.linvo.cinemeta')
    for entry, cat in candidates:
        path = os.path.join(STORE.root, 'new-movies-widget.json')
        cached = STORE.read(path, {})
        try:
            if cached.get('version') == 2 and cached.get('provider') == entry['key'] and cached.get('year') == year and time.time() - cached.get('time', 0) < 900:
                movies = cached['movies']
            else:
                data = fetch_resource(entry, 'catalog', 'movie', cat['id'], {'genre': year})
                movies = [dict(m, type='movie') for m in data.get('metas', [])
                          if isinstance(m, dict) and m.get('id') and m.get('name') and m.get('type', 'movie') == 'movie'
                          and str(m.get('releaseInfo', ''))[:4] == year
                          and (not m.get('released') or str(m['released'])[:10] <= datetime.date.today().isoformat())][:60]
                if not movies:
                    continue
                STORE.write(path, dict(version=2, provider=entry['key'], year=year, time=time.time(), movies=movies))
            add_metas(movies, entry['key'], 'movie')
            break
        except Exception:
            continue
    xbmcplugin.setPluginCategory(HANDLE, 'New movies · CBR')
    finish('movies')


'''
s = s.replace('def manage():', function + 'def manage():', 1)
s = s.replace("        elif action == 'tools':", "        elif action == 'new_movies':\n            new_movies()\n        elif action == 'tools':", 1)
(ROOT/'addon.py').write_text(s, encoding='utf8')

s = (BACKUP/'Home.xml').read_text(encoding='utf8')
s = s.replace('String.IsEqual(Container(9000).ListItem.Property(id),movies)</visible>',
              'String.IsEqual(Container(9000).ListItem.Property(id),movies) | String.IsEqual(Container(9000).ListItem.Property(id),crb_0)</visible>', 1)
marker = '<pagecontrol>5010</pagecontrol>'
widget = '''
                        <include content="WidgetListPoster">
                            <param name="content_path" value="plugin://plugin.video.stremio.bridge/?action=new_movies"/>
                            <param name="widget_header" value="New movies · CBR"/>
                            <param name="widget_target" value="videos"/>
                            <param name="browse_mode" value="never"/>
                            <param name="list_id" value="5700"/>
                        </include>'''
s = s.replace(marker, marker + widget, 1)
# Keep the existing local-library shelves, but remove the empty-library notice.
start = s.index('\t\t\t\t\t<include content="ImageWidget" condition="!Library.HasContent(movies)">')
end = s.index('</include>', start) + len('</include>')
s = s[:start] + s[end:]
start = s.index('<label>CBR Movies</label>')
end = s.index('</item>', start)
block = s[start:end].replace('$NUMBER[9000]', '$NUMBER[5000]')
s = s[:start] + block + s[end:]
start = s.index('<property name="id">movies</property>')
item_start = s.rfind('<item>', 0, start)
prefix = s[item_start:start]
import re
prefix = re.sub(r'<onclick[^>]*>.*?</onclick>', '', prefix)
prefix += '<onclick>ActivateWindow(Videos,plugin://plugin.video.stremio.bridge/?action=new_movies,return)</onclick>\n'
s = s[:item_start] + prefix + s[start:]
(ROOT/'Home.xml').write_text(s, encoding='utf8')
for name in FILES:
    if name.endswith('.py'): ast.parse((ROOT/name).read_text())
    else: ET.parse(ROOT/name)
print('Staged and syntax checked:', ', '.join(FILES))
