"""DaddyLive player decoders, adapted from The Crew DaddyLive 5.2.7.
Copyright 2024 The Crew. GPL-3.0-or-later.
Upstream: https://github.com/thecrewwh/zips/tree/master/matrix/_zip/plugin.video.daddylive
Only deterministic page/URL decoders are included; no remote JavaScript is executed.
"""
import base64
import html
import json
import math
import re
import time
from urllib.parse import urljoin, urlparse, parse_qsl, quote_plus
from urllib.request import Request, urlopen

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'

class Reply:
    def __init__(self, response):
        self.url, self.status_code = response.url, response.status
        self.content = response.read(4 * 1024 * 1024 + 1)
        if len(self.content) > 4 * 1024 * 1024:
            raise ValueError('Provider response exceeds size limit.')
        self.text = self.content.decode('utf-8-sig', 'replace')
    def json(self):
        return json.loads(self.text)

class Requests:
    def get(self, url, headers=None, timeout=10):
        if urlparse(url).scheme not in ('http', 'https'):
            raise ValueError('Unsupported provider URL.')
        with urlopen(Request(url, headers=headers or {}), timeout=timeout) as response:
            return Reply(response)

requests = Requests()

def log(*args):
    # Provider URLs can contain short-lived tokens; never log them.
    pass

def normalize_origin(url):
    parts = urlparse(url)
    return '{}://{}/'.format(parts.scheme, parts.netloc)

def fetch_page(url, referer=None):
    return requests.get(url, headers=dict({'User-Agent': UA}, **({'Referer': referer} if referer else {})), timeout=8).text

def decode_econfig(encoded):
    s = base64.b64decode(encoded).decode('utf-8')
    size = math.ceil(len(s) / 4)
    chunks = [s[i * size:(i + 1) * size] for i in range(4)]
    perm = [2, 0, 3, 1]
    reordered = [''] * 4
    for i in range(4):
        c = chunks[i]
        c = c[:3] + c[4:]
        reordered[perm[i]] = base64.b64decode(c).decode('utf-8')
    return json.loads(base64.b64decode(''.join(reordered)).decode('utf-8'))

def iframe_src(page, page_url):
    m = re.search(r'<iframe[^>]+src="([^"]+)"', page, re.I)
    if not m:
        return None
    return urljoin(page_url, html.unescape(m.group(1)).strip())

def resolve_cast(player_url, referer):
    embed_url = iframe_src(fetch_page(player_url, referer), player_url)
    if not embed_url:
        log(f'[resolve_cast] No iframe found: {player_url}')
        return None
    page = fetch_page(embed_url, player_url)
    stream_url = None
    m = re.search(r"window\._econfig='([^']+)'", page)
    if m:
        try:
            cfg = decode_econfig(m.group(1))
            stream_url = cfg.get('stream_url_nop2p') or cfg.get('stream_url')
        except Exception as e:
            log(f'[resolve_cast] _econfig decode failed: {e}')
    stream_url = stream_url or decode_payload(page, embed_url)
    if not stream_url:
        log(f'[resolve_cast] No stream found: {embed_url}')
        return None
    return stream_url, embed_url

def decode_payload(page, page_url=None):
    m = re.search(r'(?:var|let|const)\s+\w+\s*=\s*\[([\d,\s]+)\]\s*,\s*\w+\s*=\s*(\d+)\s*,\s*\w+\s*=\s*(\d+)', page)
    if not m:
        return None
    key1 = int(m.group(2))
    key2 = int(m.group(3))
    decoded = ''.join(chr(((int(n) ^ key1) - key2 + 256) % 256) for n in m.group(1).split(','))
    lm = re.search(r'loadStreamUrl\(\s*"([^"]+)"', decoded)
    if lm and page_url:
        return token_stream_url(lm.group(1).replace('\\/', '/'), page_url)
    m = re.search(r'SIGNED_URL\s*=\s*"([^"]+)"', decoded) or re.search(r'\burl\s*=\s*"([^"]+)"', decoded)
    if not m:
        return None
    return m.group(1).replace('\\/', '/')

def token_stream_url(token_url, page_url):
    origin = normalize_origin(page_url).rstrip('/')
    tk = token_url.rstrip('/').rsplit('/', 1)[-1]
    try:
        resp = requests.get(token_url, headers={'User-Agent': UA, 'Referer': origin + '/', 'Origin': origin}, timeout=10)
    except Exception as e:
        log(f'[token_stream_url] fetch failed: {e}')
        return None
    raw = resp.content
    if resp.status_code != 200 or len(raw) < 2 or not tk:
        log(f'[token_stream_url] bad token reply {resp.status_code} | {token_url}')
        return None
    seed = raw[0]
    url = ''.join(chr(raw[i] ^ ord(tk[(i - 1) % len(tk)]) ^ ((seed + i - 1) & 255)) for i in range(1, len(raw))).strip()
    return url if url.startswith('http') else None

def resolve_plus(player_url, referer):
    embed_url = iframe_src(fetch_page(player_url, referer), player_url)
    if not embed_url:
        log(f'[resolve_plus] No iframe found: {player_url}')
        return None
    stream_url = decode_payload(fetch_page(embed_url, player_url), embed_url)
    if not stream_url:
        log(f'[resolve_plus] No stream url in payload: {embed_url}')
        return None
    return stream_url, embed_url

def b64_parts_url(page):
    m = re.search(r"function\s+(\w+)\(s\)\{s=s\.replace.*?\};((?:var\s+\w+='[^']*';)+)var\s+\w+=((?:\1\(\w+\)\+?)+);", page, re.S)
    if not m:
        return None
    parts = dict(re.findall(r"var\s+(\w+)='([^']*)'", m.group(2)))
    out = ''
    for name in re.findall(r'\((\w+)\)', m.group(3)):
        s = parts.get(name, '').replace('-', '+').replace('_', '/')
        out += base64.b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', 'ignore')
    return out if out.startswith('http') else None

def resolve_casting(player_url, referer):
    outer_url = iframe_src(re.sub(r'<!--.*?-->', '', fetch_page(player_url, referer), flags=re.S), player_url)
    if not outer_url:
        log(f'[resolve_casting] No iframe found: {player_url}')
        return None
    outer_page = fetch_page(outer_url, player_url)
    embed_url = iframe_src(outer_page, outer_url)
    if not embed_url:
        stream_url = b64_parts_url(outer_page)
        if stream_url:
            return stream_url, outer_url
        log(f'[resolve_casting] No inner iframe found: {outer_url}')
        return None
    m = re.search(r'const\s+streamUrls\s*=\s*(\[[^\]]*\])', fetch_page(embed_url, outer_url))
    if not m:
        log(f'[resolve_casting] No streamUrls found: {embed_url}')
        return None
    for entry in json.loads(m.group(1)):
        if isinstance(entry, dict):
            entry = next((entry[k] for k in ('url', 'src', 'file', 'stream_url') if isinstance(entry.get(k), str) and entry[k]), None)
        if isinstance(entry, str) and entry:
            return entry, embed_url
    log(f'[resolve_casting] No usable URL in streamUrls: {embed_url}')
    return None

def resolve_watch(player_url, referer):
    embed_url = iframe_src(fetch_page(player_url, referer), player_url)
    if not embed_url:
        log(f'[resolve_watch] No iframe found: {player_url}')
        return None
    page = fetch_page(embed_url, player_url)
    m = re.search(r'const\s+SRC\s*=\s*"([^"]+)"', page)
    if not m:
        log(f'[resolve_watch] No SRC found: {embed_url}')
        return None
    src = m.group(1).replace('\\/', '/')
    edge = re.search(r'const\s+EDGE\s*=\s*"([^"]+)"', page)
    channel = re.search(r'const\s+CHANNEL\s*=\s*"([^"]+)"', page)
    ticket = re.search(r'const\s+TICKET\s*=\s*"([^"]+)"', page)
    if edge and channel and ('playlist-token' in page or ticket):
        token_url = f'{edge.group(1).rstrip("/")}/api/playlist-token?slug={quote_plus(channel.group(1))}'
        if ticket:
            token_url += f'&tk={quote_plus(ticket.group(1))}'
        return src, embed_url, token_url
    return src, embed_url

def b64_url(encoded):
    try:
        text = base64.b64decode(encoded + '=' * (-len(encoded) % 4)).decode('utf-8', 'ignore')
    except Exception:
        return None
    m = re.search(r"atob\('([^']+)'\)", text)
    if m:
        return b64_url(m.group(1))
    m = re.search(r'(?:https?:)?//[^\s"\'<>]+', text)
    return m.group(0) if m else None

def next_hop(page, page_url):
    m = re.search(r'data-encoded="([^"]+)"', page)
    if m and b64_url(m.group(1)):
        return urljoin(page_url, b64_url(m.group(1)))
    m = re.search(r'"([A-Za-z0-9+/=]{40,})"\s*;\s*eval\(atob', page)
    if m and b64_url(m.group(1)):
        return urljoin(page_url, b64_url(m.group(1)))
    m = re.search(r"iframe\.src\s*=\s*'([^']+)'\s*\+\s*encodeURIComponent", page)
    if m:
        channel = re.sub(r'[/\\.?&=]', '', dict(parse_qsl(urlparse(page_url).query)).get('id', '').strip())
        if channel:
            return urljoin(page_url, m.group(1) + quote_plus(channel))
    m = re.search(r'f\.src\s*=\s*"([^"]+)"', page) or re.search(r'<ifr(?:\'\+\')?ame[^>]+src="((?:https?:)?//[^"]+)"', page, re.I)
    if m:
        return urljoin(page_url, html.unescape(m.group(1)).strip())
    return None

def resolve_player(player_url, referer):
    url = player_url
    for _ in range(10):
        page = fetch_page(url, referer)
        stream_url = decode_payload(page, url)
        if not stream_url:
            m = re.search(r'streamUrl\s*:\s*"([^"]+)"', page)
            if m:
                stream_url = m.group(1).replace('\\/', '/')
        if stream_url:
            return stream_url, url
        nxt = next_hop(page, url)
        if not nxt:
            log(f'[resolve_player] Chain ended without a stream: {url}')
            return None
        referer = None if 'referrerpolicy="no-referrer"' in page else normalize_origin(url)
        url = nxt
    log(f'[resolve_player] Chain too long: {player_url}')
    return None

def fetch_playlist_token(token_url, headers):
    try:
        data = requests.get(token_url, headers=headers, timeout=10).json()
        return data.get('token') or ''
    except Exception as e:
        log(f'[fetch_playlist_token] failed: {e}')
        return ''

def with_token(stream_url, token):
    if not token:
        return stream_url
    sep = '&' if '?' in stream_url else '?'
    return f'{stream_url}{sep}t={quote_plus(token)}&_={int(time.time() * 1000)}'
