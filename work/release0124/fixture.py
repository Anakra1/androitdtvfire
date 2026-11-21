"""Local UI fixture using the actual packaged setup server and synthetic data."""
from pathlib import Path
import sys
import json

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'stage/plugin.video.stremio.bridge'))
from resources.lib.core import Store
from resources.lib.setup_web import SetupServer
from resources.lib import pvr

DATA = HERE / 'fixture-data'
DATA.mkdir(exist_ok=True)
store = Store(str(DATA))


def manifest(url):
    if 'films' in url:
        types, name = ['movie'], 'Film catalogue'
    elif 'shared' in url:
        types, name = ['movie', 'series'], 'Shared films and series'
    elif 'series' in url:
        types, name = ['series'], 'Episode catalogue'
    else:
        types, name = ['tv'], 'UK channels'
    return {'id': name, 'name': name, 'version': '1.0.0', 'resources': ['stream'], 'types': types, 'catalogs': []}


if not store.providers():
    for key in ('films', 'series', 'shared', 'live'):
        store.add('https://' + key + '.example/manifest.json', fetch=manifest)
channels = [dict(id='bbc-test', name='BBC Test', number=1, visible=True, favourite=False, groups=['UK TV']),
            dict(id='sports-test', name='Sports Test', number=2, visible=True, favourite=True, groups=['Sports'])]
pvr.channels = lambda *a: channels
pvr.sources = lambda *a: []
pvr.GROUPS = ['UK TV', 'Sports', 'Internet TV']
server = SetupServer(store, str(HERE / 'stage/plugin.video.stremio.bridge/resources/setup'),
                     '127.0.0.1', host='127.0.0.1', port=18768, fetch=manifest)
(DATA / 'connection.json').write_text(json.dumps({'port': server.port, 'code': server.code}))
print('Local setup fixture ready.', flush=True)
try:
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    server.close()
