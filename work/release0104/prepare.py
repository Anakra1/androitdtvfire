"""Rebase the tested Windows sports patches onto Android 0.10.3."""
from pathlib import Path
from zipfile import ZipFile
import ast, shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
base=ROOT/'outputs/verified-live-release0104-base'
base.mkdir(exist_ok=True)
with ZipFile(ROOT/'android/packages/plugin.video.stremio.bridge/plugin.video.stremio.bridge-0.10.3.zip')as archive:
    for name in ('addon.py','resources/lib/core.py','resources/lib/live.py','resources/lib/pvr.py','resources/lib/defaults.py','resources/lib/setup_web.py'):
        target=base/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(archive.read('plugin.video.stremio.bridge/'+name).decode('utf-8-sig'),encoding='utf8',newline='\n')
source=(ROOT/'work/sports-menu/prepare.py').read_text(encoding='utf8')
patches=source[source.index('def write(name,text):'):]
exec(compile(patches,'reviewed-sports-patches','exec'),dict(Path=Path,ast=ast,HERE=HERE,ROOT=ROOT,BACKUP=base))
for name in ('sports.py','daddylive.py','daddy_resolvers.py'):
    shutil.copy2(ROOT/'work/sports-menu/overlay/resources/lib'/name,HERE/'overlay/resources/lib'/name)
addon=(HERE/'overlay/addon.py').read_text(encoding='utf8')
assert 'def new_movies():'in addon and "cached.get('version') == 2"in addon
assert 'def crew_sport_link(sport):'in addon and 'def sports_category('in addon
assert 'def ensure_tv_0103('in (HERE/'overlay/resources/lib/defaults.py').read_text(encoding='utf8')
assert 'cbr-guide-0103.json'in (HERE/'overlay/resources/lib/pvr.py').read_text(encoding='utf8')
print('Android 0.10.4 overlay prepared; previous BBC, guide and movie improvements retained.')
