"""Optional Real-Debrid OAuth and explicit torrent resolution; no Kodi dependencies.

Protocol: https://api.real-debrid.com/ (opensource application/device workflow).
Credentials stay in the local profile, outside backup/diagnostic allowlists.
"""
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote, urlsplit, unquote
from urllib.request import Request, build_opener, HTTPRedirectHandler

PUBLIC_CLIENT = 'X245A4XAIBGVM'  # Official, documented open-source client, not another add-on's ID.
OAUTH = 'https://api.real-debrid.com/oauth/v2/'
REST = 'https://api.real-debrid.com/rest/1.0/'
GRANT = 'http://oauth.net/grant_type/device/1.0'
VIDEO = ('.mkv', '.mp4', '.m4v', '.avi', '.mov', '.ts', '.m2ts', '.webm', '.mpg', '.mpeg')
MESSAGES = {8:'Real-Debrid sign-in expired. Connect again in Setup.',
    14:'The Real-Debrid account is locked.', 20:'This Real-Debrid operation needs Premium.',
    21:'Real-Debrid has too many active transfers.', 22:'Real-Debrid does not allow this IP address.',
    23:'Real-Debrid traffic allowance is exhausted.', 24:'This file is unavailable on Real-Debrid.',
    34:'Real-Debrid rate limit reached. Please wait before retrying.',
    35:'Real-Debrid has blocked this file.', 36:'Real-Debrid fair-use limit reached.'}


class DebridError(RuntimeError):
    def __init__(self, status=0, code=None, error='', retry_after=5):
        self.status, self.code, self.error = status, code, error
        self.retry_after = max(5, min(60, int(retry_after or 5)))
        message = MESSAGES.get(code)
        if not message:
            message = ('Real-Debrid sign-in expired. Connect again in Setup.' if status == 401 else
                       'Real-Debrid rate limit reached. Please wait before retrying.' if status == 429 else
                       'Real-Debrid could not complete this request. Check account status or try again later.')
        super().__init__(message)  # Never include response bodies, tokens, device secrets or URLs.


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a Bearer token to a redirected host.


def transport(method, url, data=None, token=None):
    if urlsplit(url).scheme != 'https' or urlsplit(url).hostname != 'api.real-debrid.com':
        raise ValueError('Real-Debrid credentials may only be sent to its official HTTPS API.')
    headers = {'Accept':'application/json', 'User-Agent':'CBR-Kodi/0.12.6'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    body = urlencode(data).encode('utf-8') if data is not None else None
    if body is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    try:
        with build_opener(NoRedirect()).open(Request(url, data=body, headers=headers, method=method), timeout=15) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise DebridError()
            return json.loads(raw.decode('utf-8')) if raw else {}
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read(65536).decode('utf-8'))
        except (ValueError, UnicodeError):
            payload = {}
        try:
            retry = int(exc.headers.get('Retry-After', '5'))
        except (ValueError, TypeError):
            retry = 5
        raise DebridError(exc.code, payload.get('error_code'), payload.get('error', ''), retry) from None
    except (URLError, OSError, ValueError):
        raise DebridError() from None


class Client:
    def __init__(self, root, request=transport, clock=time.time):
        self.path = os.path.join(root, 'real-debrid-auth.json')
        self.request, self.clock = request, clock
        os.makedirs(root, exist_ok=True)

    def load(self):
        try:
            with open(self.path, encoding='utf-8') as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self, value):
        fd, temporary = tempfile.mkstemp(dir=os.path.dirname(self.path), prefix='.rd-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(value, handle)
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

    @contextmanager
    def locked(self):
        lock = self.path + '.lock'
        deadline = time.monotonic() + 25
        while True:
            try:
                descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                break
            except FileExistsError:
                try:
                    if self.clock() - os.path.getmtime(lock) > 120:
                        os.remove(lock)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() > deadline:
                    raise RuntimeError('Real-Debrid is busy. Please try again.')
                time.sleep(.1)
        try:
            yield
        finally:
            try:
                os.remove(lock)
            except FileNotFoundError:
                pass

    def connected(self):
        state = self.load()
        return all(isinstance(state.get(k), str) and state[k] for k in ('client_id','client_secret','access_token','refresh_token'))

    def summary(self):
        state = self.load()
        return dict(connected=self.connected(), **{k:state.get('account', {}).get(k, '') for k in ('username','type','expiration')})

    def begin(self):
        result = self.request('GET', OAUTH + 'device/code?' + urlencode({'client_id':PUBLIC_CLIENT, 'new_credentials':'yes'}))
        if not all(result.get(k) for k in ('device_code','user_code','verification_url','expires_in')):
            raise DebridError()
        url = urlsplit(result['verification_url'])
        if url.scheme != 'https' or url.hostname != 'real-debrid.com' or url.path.rstrip('/') != '/device':
            raise DebridError()
        return result

    def complete(self, device, cancelled=lambda:False, wait=time.sleep):
        expires = min(1800, max(1, int(device['expires_in'])))
        interval = max(5, min(60, int(device.get('interval', 5))))
        deadline = self.clock() + expires
        credentials = None
        while self.clock() < deadline:
            if cancelled():
                raise InterruptedError('Real-Debrid sign-in cancelled.')
            wait(min(interval, max(0, deadline-self.clock())))
            if cancelled():
                raise InterruptedError('Real-Debrid sign-in cancelled.')
            if self.clock() >= deadline:
                break
            try:
                credentials = self.request('GET', OAUTH + 'device/credentials?' + urlencode({
                    'client_id':PUBLIC_CLIENT, 'code':device['device_code']}))
                if credentials.get('client_id') and credentials.get('client_secret'):
                    break
            except DebridError as exc:
                if exc.error in ('expired_token','expired_device_code','invalid_client','invalid_grant'):
                    raise RuntimeError('Real-Debrid sign-in expired or was rejected. Start Connect again.') from None
                if exc.status == 429 or exc.code == 5:
                    interval = max(interval + 5, exc.retry_after)
                elif exc.status not in (400, 403):
                    raise
                credentials = None
        if not credentials or not credentials.get('client_secret'):
            raise RuntimeError('Real-Debrid device code expired. Start Connect again.')
        if cancelled():
            raise InterruptedError('Real-Debrid sign-in cancelled.')
        tokens = self.request('POST', OAUTH + 'token', dict(client_id=credentials['client_id'],
            client_secret=credentials['client_secret'], code=device['device_code'], grant_type=GRANT))
        state = self.token_state(credentials, tokens)
        # Only replace a previous connection after the new sign-in has succeeded.
        with self.locked():
            self.save(state)
        return self.account()

    def token_state(self, previous, tokens):
        if not tokens.get('access_token') or not tokens.get('refresh_token', previous.get('refresh_token')):
            raise DebridError()
        result = dict(previous)
        result.update(access_token=tokens['access_token'], refresh_token=tokens.get('refresh_token', previous.get('refresh_token')),
                      expires_at=self.clock() + max(1, int(tokens.get('expires_in', 3600))))
        return result

    def refresh(self, failed_token=None):
        with self.locked():
            state = self.load()
            if not self.connected():
                raise RuntimeError('Connect Real-Debrid in CBR Setup first.')
            if failed_token and state['access_token'] != failed_token:
                return state['access_token']
            tokens = self.request('POST', OAUTH + 'token', dict(client_id=state['client_id'],
                client_secret=state['client_secret'], code=state['refresh_token'], grant_type=GRANT))
            state = self.token_state(state, tokens)
            self.save(state)
            return state['access_token']

    def api(self, method, route, data=None):
        state = self.load()
        if not self.connected():
            raise RuntimeError('Connect Real-Debrid in CBR Setup first.')
        token = state['access_token']
        if state.get('expires_at', 0) <= self.clock() + 30:
            token = self.refresh()
        try:
            return self.request(method, REST + route, data, token)
        except DebridError as exc:
            if exc.status != 401 and exc.code != 8:
                raise
            # Never retry non-idempotent torrent/unrestrict requests after a transport timeout.
            return self.request(method, REST + route, data, self.refresh(failed_token=token))

    def account(self):
        result = self.api('GET', 'user')
        safe = {k:result.get(k, '') for k in ('username','type','expiration')}
        with self.locked():
            state = self.load()
            state['account'] = safe
            self.save(state)
        return safe

    def disconnect(self):
        with self.locked():
            state = self.load()
            try:
                if state.get('access_token'):
                    self.request('GET', REST + 'disable_access_token', None, state['access_token'])
            except DebridError:
                pass
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass

    def resolve(self, stream, choose, cancelled=lambda:False, progress=lambda p,m:None, wait=time.sleep, timeout=120):
        torrent_hash = stream.get('infoHash', '')
        index = stream.get('fileIdx')
        if not isinstance(torrent_hash, str) or not re.fullmatch(r'[a-fA-F0-9]{40}', torrent_hash):
            raise ValueError('Real-Debrid needs a supported v1 torrent hash.')
        if index is not None and (isinstance(index, bool) or not isinstance(index, int) or index < 0):
            raise ValueError('The provider returned an invalid torrent file index.')
        if cancelled():
            raise InterruptedError()
        if self.account().get('type') != 'premium':
            raise RuntimeError('Real-Debrid Premium is needed for torrent playback. The built-in player is still available.')
        if cancelled():
            raise InterruptedError()
        # Only an explicitly selected stream reaches this API; no background link uploads.
        result = self.api('POST', 'torrents/addMagnet', {'magnet':'magnet:?' + urlencode({'xt':'urn:btih:' + torrent_hash})})
        torrent_id = result.get('id')
        if not isinstance(torrent_id, str) or not torrent_id:
            raise DebridError()
        route = 'torrents/info/' + quote(torrent_id, safe='')
        deadline = self.clock() + timeout
        wanted, selected = None, False
        while self.clock() < deadline:
            if cancelled():
                raise InterruptedError('Stopped waiting. The transfer may remain in your Real-Debrid account.')
            info = self.api('GET', route)
            status = info.get('status')
            if status in ('magnet_error','error','virus','dead'):
                raise RuntimeError('Real-Debrid could not prepare this torrent. Choose another source.')
            files = info.get('files') or []
            if files and wanted is None:
                wanted = choose_video(files, stream, choose)
            if status == 'waiting_files_selection' and wanted is not None and not selected:
                self.api('POST', 'torrents/selectFiles/' + quote(torrent_id, safe=''), {'files':str(wanted)})
                selected = True
            elif status == 'downloaded' and wanted is not None:
                chosen = [f for f in files if f.get('selected')]
                matches = [i for i,f in enumerate(chosen) if f.get('id') == wanted]
                links = info.get('links') or []
                if len(matches) != 1 or len(links) != len(chosen):
                    raise RuntimeError('This file is not selected in the existing Real-Debrid transfer. Choose another source or manage that transfer on Real-Debrid.')
                link = links[matches[0]]
                address = urlsplit(link)
                if address.scheme != 'https' or address.hostname not in ('real-debrid.com','www.real-debrid.com'):
                    raise DebridError()
                unrestrict = self.api('POST', 'unrestrict/link', {'link':link})
                download = unrestrict.get('download', '')
                address = urlsplit(download)
                if address.scheme not in ('http','https') or not address.hostname or address.username or '|' in download:
                    raise DebridError()
                return download
            progress(max(0, min(99, int(info.get('progress') or 0))), 'Real-Debrid: ' + str(status or 'preparing').replace('_',' '))
            wait(3)
        raise RuntimeError('Real-Debrid is still preparing this file. Try again later; the transfer may remain in your account.')


def choose_video(files, stream, choose):
    videos = [f for f in files if str(f.get('path','')).lower().endswith(VIDEO)]
    if not videos:
        raise RuntimeError('No supported video file was returned by Real-Debrid.')
    filename = (stream.get('behaviorHints') or {}).get('filename') or stream.get('filename')
    if filename:
        basename = unquote(str(filename)).replace('\\','/').rsplit('/',1)[-1].casefold()
        matches = [f for f in videos if str(f['path']).replace('\\','/').rsplit('/',1)[-1].casefold() == basename]
        if len(matches) == 1:
            return matches[0]['id']
    index = stream.get('fileIdx')
    if index is not None:
        if index >= len(files) or files[index] not in videos:
            raise RuntimeError('The torrent file index does not match a playable video. Choose another source.')
        return files[index]['id']
    if len(videos) == 1:
        return videos[0]['id']
    result = choose(videos)
    if result is None:
        raise InterruptedError()
    if result not in videos:
        raise ValueError('Invalid Real-Debrid file choice.')
    return result['id']
