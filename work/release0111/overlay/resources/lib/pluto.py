"""Resolve Pluto channels with a fresh anonymous session for each selection."""
import json
import re
import uuid
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

BOOT = 'https://boot.pluto.tv/v4/start'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0',
    'Origin': 'https://pluto.tv', 'Referer': 'https://pluto.tv/',
}


def supported(source):
    address = urlsplit(source)
    return (address.hostname == 'raw.githubusercontent.com'
            and address.path in ('/BuddyChewChew/pluto/main/pluto_gb.m3u',
                                 '/BuddyChewChew/pluto/refs/heads/main/pluto_gb.m3u'))


def fetch_boot(url):
    with urlopen(Request(url, headers=HEADERS), timeout=15) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Pluto session response exceeds the limit.')
    return json.loads(raw.decode('utf8'))


def streams(channel_id, fetch=None):
    if not isinstance(channel_id, str) or not re.fullmatch(r'[a-f0-9]{24}', channel_id):
        raise ValueError('Invalid Pluto channel identity.')
    params = dict(appName='web', appVersion='8.1.0', clientID=str(uuid.uuid4()),
                  clientModelNumber='1.0.0', deviceType='web', deviceModel='web',
                  deviceMake='firefox', deviceVersion='145.0.0', serverSideAds='true',
                  blockingMode='', notificationVersion='1', appLaunchCount='0',
                  channelSlug=channel_id)
    try:
        data = (fetch or fetch_boot)(BOOT + '?' + urlencode(params))
        token = data.get('sessionToken')
        if not isinstance(token, str) or not token:
            raise ValueError('Missing session')
        # Only play a channel actually returned for this session/location.
        channel = next((row for row in data.get('EPG', [])
                        if isinstance(row, dict) and row.get('id') == channel_id), None)
        if channel is None:
            raise ValueError('Channel unavailable')
        expected = '/stitch/hls/channel/' + channel_id + '/master.m3u8'
        stitched = channel.get('stitched', {})
        if not isinstance(stitched, dict) or stitched.get('path') != expected:
            raise ValueError('Unsupported playback path')
        server = data.get('servers', {}).get('stitcher', '')
        address = urlsplit(server)
        if (address.scheme != 'https' or not address.hostname or address.username or address.password
                or not address.hostname.endswith('.pluto.tv')):
            raise ValueError('Unexpected playback server')
        query = dict(parse_qsl(data.get('stitcherParams', '')))
        # The server provides the session/region. Do not spoof IP or region,
        # reuse public playlist JWTs, suppress ads, or alter token claims.
        query.update(jwt=token, includeExtendedEvents='true', masterJWTPassthrough='true')
        url = urljoin(server, 'v2' + expected) + '?' + urlencode(query)
        return [dict(url=url, name='Pluto TV', behaviorHints=dict(
            isLive=True, proxyHeaders={'request': dict(HEADERS)}))]
    except Exception:
        # Bootstrap errors and redirect URLs may contain session credentials.
        raise ValueError('Pluto TV could not start a fresh session for this channel. Try again later.') from None
