"""Execute native categories and paired setup through the running portable Kodi."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlsplit, parse_qs
import base64
import http.client
import json
import secrets
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / 'work/test-kodi-tv/portable_data'
settings = {e.get('id'): e.text or '' for e in ET.parse(PROFILE / 'userdata/guisettings.xml').getroot().iter('setting')}
headers = {'Content-Type': 'application/json', 'Authorization': 'Basic ' + base64.b64encode(
    (settings['services.webserverusername'] + ':' + settings['services.webserverpassword']).encode()).decode()}


def rpc(method, params=None):
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}).encode()
    request = Request('http://127.0.0.1:' + settings['services.webserverport'] + '/jsonrpc', data=body, headers=headers)
    with urlopen(request, timeout=20) as response:
        result = json.load(response)
    if 'error' in result:
        raise RuntimeError(result['error']['message'])
    return result['result']


def directory(action, **params):
    path = 'plugin://plugin.video.stremio.bridge/?' + urlencode(dict(action=action, **params))
    return rpc('Files.GetDirectory', {'directory': path, 'media': 'files'})['files']


details = rpc('Addons.GetAddonDetails', {'addonid': 'plugin.video.stremio.bridge', 'properties': ['version', 'enabled']})['addon']
assert details['version'] == '0.12.4' and details['enabled']
menu = directory('command_setup')
expected = ['Live TV sources', 'Movie sources', 'TV Series sources', 'Channel Listings / numbers and groups',
            'Programmes / guide feeds', 'Tools / updates, backup and repair']
assert [r['label'] for r in menu[:6]] == expected
provider_keys = {}
for category in ('live', 'movies', 'series', 'tools'):
    rows = directory('manage', category=category)
    assert rows
    keys = []
    for row in rows:
        query = parse_qs(urlsplit(row['file']).query)
        if query.get('action') == ['provider']:
            assert query.get('category') == [category]
            keys.append(query['key'][0])
    provider_keys[category] = keys
assert directory('pvr')

# Start the real Kodi service's paired page without opening a browser or changing sources.
data = PROFILE / 'userdata/addon_data/plugin.video.stremio.bridge'
request_path, endpoint_path = data / 'web-setup-request.json', data / 'web-setup-endpoint.json'
previous = request_path.read_bytes() if request_path.exists() else None
nonce = secrets.token_hex(16)
request_path.write_text(json.dumps({'nonce': nonce, 'time': time.time()}))
endpoint = {}
try:
    for _ in range(45):
        try:
            endpoint = json.loads(endpoint_path.read_text())
        except (OSError, ValueError):
            endpoint = {}
        if endpoint.get('nonce') == nonce:
            break
        time.sleep(.4)
    assert endpoint.get('nonce') == nonce and not endpoint.get('error'), 'Kodi paired setup service did not start'
    host = urlsplit(endpoint['url'])
    # Service listens on LAN for normal phone use; verify via loopback locally.
    connection = http.client.HTTPConnection('127.0.0.1', host.port, timeout=5)
    connection.request('GET', '/')
    response = connection.getresponse()
    html = response.read().decode()
    assert response.status == 200
    assert html.count('role="tab"') == 6
    for category in ('live', 'movies', 'series', 'listings', 'programmes', 'tools'):
        assert 'id="panel-' + category + '"' in html
    connection.request('POST', '/api/pair', json.dumps({'code': endpoint['code']}), {'Content-Type': 'application/json'})
    response = connection.getresponse()
    response.read()
    assert response.status == 200
    cookie = response.getheader('Set-Cookie').split(';')[0]
    connection.request('GET', '/api/sources', headers={'Cookie': cookie})
    response = connection.getresponse()
    assert response.status == 200
    sources = json.loads(response.read())['sources']
    for category in ('live', 'movies', 'series'):
        wanted = {s['key'] for s in sources if category in s['sections']}
        assert set(provider_keys[category]) == wanted, (category, len(provider_keys[category]), len(wanted))
    connection.close()
finally:
    request_path.write_text(json.dumps({'nonce': nonce, 'stop': True}))
    time.sleep(1)
    if previous is not None:
        request_path.write_bytes(previous)

report = {'kodi_version': rpc('Application.GetProperties', {'properties': ['version']})['version'],
          'addon_version': details['version'], 'native_categories': expected, 'native_category_navigation': 'passed',
          'paired_setup_served_by_kodi': 'passed', 'native_and_web_source_categories_match': True,
          'provider_counts': {key: len(value) for key, value in provider_keys.items()},
          'personal_sources_changed': False, 'browser_visual_test': False}
(ROOT / 'outputs/verified-live-setup0124-kodi.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, ensure_ascii=True))
