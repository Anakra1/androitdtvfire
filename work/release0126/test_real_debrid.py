"""Credential-free regression tests; all account/transfer operations use local fixtures."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
import ast
from urllib.parse import urlsplit, parse_qs

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'stage/plugin.video.stremio.bridge'))
from resources.lib.real_debrid import Client, DebridError, choose_video, PUBLIC_CLIENT, GRANT, transport, NoRedirect
from resources.lib.maintenance import export_backup
from resources.lib.core import Store


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.pending = 0
        self.fail_auth_once = False
        self.free = False
        self.statuses = ['waiting_files_selection', 'downloaded']

    def __call__(self, method, url, data=None, token=None):
        self.calls.append((method, url, data, token))
        path = urlsplit(url).path
        if path.endswith('/device/code'):
            return dict(device_code='fake-device-private', user_code='FAKE-CODE', verification_url='https://real-debrid.com/device', expires_in=30, interval=5)
        if path.endswith('/device/credentials'):
            query = parse_qs(urlsplit(url).query)
            assert query['client_id'] == [PUBLIC_CLIENT] and query['code'] == ['fake-device-private']
            if self.pending:
                self.pending -= 1
                raise DebridError(403, error='authorization_pending')
            return dict(client_id='fake-user-client', client_secret='fake-client-secret')
        if path.endswith('/token'):
            assert data['grant_type'] == GRANT
            return dict(access_token='fake-refreshed-access' if data['code'] == 'fake-refresh' else 'fake-access', refresh_token='fake-refresh', expires_in=3600)
        if path.endswith('/user'):
            if self.fail_auth_once:
                self.fail_auth_once = False
                raise DebridError(401, 8)
            return dict(username='fixture-user', type='free' if self.free else 'premium', expiration='2030-01-01', email='never-store@example.invalid')
        if path.endswith('/disable_access_token'):
            return {}
        if path.endswith('/addMagnet'):
            return {'id':'fake-transfer'}
        if '/torrents/info/' in path:
            status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            return dict(status=status, progress=100 if status=='downloaded' else 0,
                files=[{'id':3,'path':'/sample.txt','selected':0}, {'id':7,'path':'/show.S01E02.mkv','selected':1}],
                links=['https://real-debrid.com/d/fake-file'])
        if '/selectFiles/' in path:
            assert data == {'files':'7'}
            return {}
        if path.endswith('/unrestrict/link'):
            return {'download':'https://fixture.download.example/video.mkv'}
        raise AssertionError('Unexpected fixture request: ' + path)


class Checks(unittest.TestCase):
    def setUp(self):
        (HERE / 'test-data').mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=HERE / 'test-data')
        self.api = FakeAPI()
        self.now = 1000
        self.client = Client(self.directory.name, self.api, lambda:self.now)

    def tearDown(self):
        self.directory.cleanup()

    def wait(self, seconds):
        self.now += seconds

    def connected(self):
        self.client.save(dict(client_id='fake-user-client', client_secret='fake-client-secret', access_token='fake-access', refresh_token='fake-refresh', expires_at=self.now+3600))

    def test_connect_uses_documented_device_credentials_workflow(self):
        self.api.pending = 1
        account = self.client.complete(self.client.begin(), wait=self.wait)
        self.assertTrue(self.client.connected())
        self.assertEqual(account['username'], 'fixture-user')
        self.assertGreaterEqual(self.now, 1010)
        self.assertNotIn('email', self.client.load()['account'])
        self.assertNotIn('device_code', self.client.load())
        self.assertNotIn('fake-access', json.dumps(self.client.summary()))
        self.assertTrue(all(c[1].startswith('https://api.real-debrid.com/') for c in self.api.calls))
        self.assertIn('new_credentials=yes', self.api.calls[0][1])

    def test_cancel_keeps_previous_connection(self):
        self.connected()
        previous = Path(self.client.path).read_bytes()
        with self.assertRaises(InterruptedError):
            self.client.complete(self.client.begin(), cancelled=lambda:True, wait=self.wait)
        self.assertEqual(previous, Path(self.client.path).read_bytes())

    def test_device_code_expiry_does_not_store_partial_secrets(self):
        self.api.pending = 99
        with self.assertRaisesRegex(RuntimeError, 'expired'):
            self.client.complete(self.client.begin(), wait=self.wait)
        self.assertFalse(os.path.exists(self.client.path))

    def test_expired_access_token_refreshes_and_retries_401_once(self):
        self.connected()
        state = self.client.load(); state['expires_at'] = self.now-1; self.client.save(state)
        self.client.account()
        self.assertEqual(self.client.load()['access_token'], 'fake-refreshed-access')
        self.api.fail_auth_once = True
        self.client.account()
        self.assertEqual(len([c for c in self.api.calls if c[1].endswith('/token')]), 2)

    def test_disconnect_clears_local_credentials(self):
        self.connected(); self.client.disconnect()
        self.assertFalse(self.client.connected())
        self.assertFalse(os.path.exists(self.client.path))
        self.assertTrue(self.api.calls[-1][1].endswith('/disable_access_token'))

    def test_backup_never_exports_rd_credentials_even_with_personal_sources(self):
        self.connected()
        store = Store(self.directory.name)
        for include in (False, True):
            backup = json.dumps(export_backup(store, include_personal=include))
            for secret in ('fake-access','fake-client-secret','fake-refresh','real-debrid-auth'):
                self.assertNotIn(secret, backup)

    def test_selected_torrent_is_resolved_and_only_selected_file_is_unrestricted(self):
        self.connected()
        url = self.client.resolve({'infoHash':'a'*40,'fileIdx':1}, choose=lambda files:None, wait=self.wait)
        self.assertEqual(url, 'https://fixture.download.example/video.mkv')
        request = next(c for c in self.api.calls if c[1].endswith('unrestrict/link'))
        self.assertEqual(request[2], {'link':'https://real-debrid.com/d/fake-file'})
        self.assertFalse(any(c[0]=='DELETE' for c in self.api.calls))

    def test_nonpremium_account_never_submits_torrent(self):
        self.connected(); self.api.free = True
        with self.assertRaisesRegex(RuntimeError, 'Premium'):
            self.client.resolve({'infoHash':'a'*40}, choose=lambda files:None, wait=self.wait)
        self.assertFalse(any(c[1].endswith('addMagnet') for c in self.api.calls))

    def test_cancelled_resolution_does_not_submit_torrent(self):
        self.connected()
        with self.assertRaises(InterruptedError):
            self.client.resolve({'infoHash':'a'*40}, choose=lambda files:None, cancelled=lambda:True, wait=self.wait)
        self.assertEqual(self.api.calls, [])

    def test_timeout_does_not_delete_cloud_transfers_or_retry_upload(self):
        self.connected(); self.api.statuses = ['queued']
        with self.assertRaisesRegex(RuntimeError, 'still preparing'):
            self.client.resolve({'infoHash':'a'*40}, choose=lambda files:None, wait=self.wait, timeout=7)
        self.assertEqual(len([c for c in self.api.calls if c[1].endswith('addMagnet')]), 1)
        self.assertFalse(any(c[0]=='DELETE' for c in self.api.calls))

    def test_ambiguous_pack_asks_and_cancellation_never_guesses_episode(self):
        files=[{'id':1,'path':'/episode1.mkv'}, {'id':5,'path':'/episode2.mkv'}]
        self.assertEqual(choose_video(files, {}, lambda rows:rows[1]), 5)
        with self.assertRaises(InterruptedError):choose_video(files, {}, lambda rows:None)
        with self.assertRaises(RuntimeError):choose_video(files, {'fileIdx':50}, lambda rows:rows[0])
        self.assertEqual(choose_video(files, {'fileIdx':0,'behaviorHints':{'filename':'episode2.mkv'}}, lambda rows:None), 5)

    def test_invalid_input_and_wrong_auth_host_are_rejected(self):
        self.connected()
        for stream in ({'infoHash':'invalid'}, {'infoHash':'a'*40,'fileIdx':True}):
            with self.assertRaises(ValueError):self.client.resolve(stream, choose=lambda files:None)
        with self.assertRaises(ValueError):transport('GET','https://example.invalid/user',token='fake-access')
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://example.invalid'))
        error=DebridError(401,8,error='fake-access')
        self.assertNotIn('fake-access',str(error))

    def test_disabled_ui_makes_no_network_calls(self):
        # Import the UI with inert Kodi modules; disabled mode must not request an account or token.
        import types
        sys.modules.setdefault('xbmc',types.SimpleNamespace())
        sys.modules.setdefault('xbmcgui',types.SimpleNamespace())
        from resources.lib.real_debrid_ui import prepare_item
        addon=types.SimpleNamespace(getSetting=lambda name:'false')
        self.assertEqual(prepare_item(addon,Store(self.directory.name),{'infoHash':'a'*40},{}),(False,None))
        self.assertFalse(os.path.exists(self.client.path))

    def test_configure_actions_work_without_a_directory_handle(self):
        import types
        sys.modules.setdefault('xbmc',types.SimpleNamespace())
        sys.modules.setdefault('xbmcgui',types.SimpleNamespace())
        from resources.lib import real_debrid_ui
        original=real_debrid_ui.action
        calls=[]
        real_debrid_ui.action=lambda addon,store,operation:calls.append(operation)
        try:
            source=ast.parse((HERE/'stage/plugin.video.stremio.bridge/addon.py').read_text(encoding='utf-8'))
            function=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='command_dispatch')
            values={'ADDON':None,'STORE':None,'HANDLE':-1,'rd_menu':lambda:calls.append('menu')}
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<dispatch>','exec'),values)
            self.assertTrue(values['command_dispatch']('rd_action',{'operation':'connect'}))
            self.assertEqual(calls,['connect'])
            values['HANDLE']=1
            self.assertTrue(values['command_dispatch']('rd_action',{'operation':'account'}))
            self.assertEqual(calls,['connect','account','menu'])
        finally:
            real_debrid_ui.action=original

    def test_oauth_rate_limit_obeys_retry_interval(self):
        original=self.api
        throttled=[False]
        def request(method,url,data=None,token=None):
            if '/device/credentials?' in url and not throttled[0]:
                throttled[0]=True
                raise DebridError(429,retry_after=12)
            return original(method,url,data,token)
        self.client.request=request
        self.client.complete(self.client.begin(),wait=self.wait)
        self.assertTrue(self.client.connected())
        self.assertGreaterEqual(self.now,1017)

    def test_download_mapping_does_not_choose_an_unselected_file(self):
        self.connected()
        original=self.api
        def request(method,url,data=None,token=None):
            response=original(method,url,data,token)
            if '/torrents/info/' in url:
                response['status']='downloaded'
                response['files'][1]['selected']=0
            return response
        self.client.request=request
        with self.assertRaisesRegex(RuntimeError,'not selected'):
            self.client.resolve({'infoHash':'a'*40,'fileIdx':1},choose=lambda files:None,wait=self.wait)
        self.assertFalse(any(c[1].endswith('unrestrict/link') for c in self.api.calls))


if __name__=='__main__':unittest.main(verbosity=2)
