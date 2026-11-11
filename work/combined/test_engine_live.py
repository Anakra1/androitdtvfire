"""Real-engine test with a generated local torrent, tracker and libtorrent seed.
Only this opt-in test needs the development dependency libtorrent.
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request

ROOT = Path(__file__).parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent.parent / 'test-deps'))
from engine import Engine, OPENER, prepare_torrent


@unittest.skipUnless(os.environ.get('STREAM_BRIDGE_LIVE_TEST') == '1', 'Explicit local-engine integration run only')
class LiveEngineTest(unittest.TestCase):
    def test_download_buffer_range_and_cleanup(self):
        import libtorrent as lt
        payload = os.urandom(2 * 1024 * 1024)
        state, announces = {}, []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith('/announce'):
                    announces.append(self.path.split('?')[0])
                    data = lt.bencode({b'interval': 5, b'complete': 1, b'incomplete': 0,
                                       b'peers': socket.inet_aton('127.0.0.1') + struct.pack('!H', state['port'])})
                elif self.path == '/test.torrent':
                    data = state['torrent']
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = 'http://127.0.0.1:{}'.format(server.server_port)
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
                seed_dir = Path(temp) / 'seed'
                seed_dir.mkdir()
                (seed_dir / 'test.mp4').write_bytes(payload)
                files = lt.file_storage()
                files.add_file('test.mp4', len(payload))
                builder = lt.create_torrent(files, 262144, lt.create_torrent.v1_only)
                builder.add_tracker(origin + '/announce')
                lt.set_piece_hashes(builder, str(seed_dir))
                state['torrent'] = lt.bencode(builder.generate())
                ti = lt.torrent_info(lt.bdecode(state['torrent']))
                expected_hash = str(ti.info_hashes().v1)
                seed = lt.session({'listen_interfaces': '127.0.0.1:0', 'enable_dht': False,
                                   'enable_lsd': False, 'enable_upnp': False, 'enable_natpmp': False,
                                   'alert_mask': 0x7fffffff})
                listen_deadline = time.monotonic() + 5
                while seed.listen_port() == 0 and time.monotonic() < listen_deadline:
                    time.sleep(0.05)
                state['port'] = seed.listen_port()
                self.assertGreater(state['port'], 0)
                handle = seed.add_torrent({'ti': ti, 'save_path': str(seed_dir), 'trackers': [],
                                          'flags': lt.torrent_flags.seed_mode | lt.torrent_flags.override_trackers})
                engine = Engine(str(ROOT.resolve()), str(Path(temp) / 'engine'), cache_mb=64)
                engine.diagnostic_path = str((Path(__file__).parent / 'engine-diagnostic.log').resolve())
                try:
                    client = engine.start()
                    self.assertTrue(client.alive())
                    settings = client.call('/settings', {'action': 'get'})
                    self.assertEqual(settings['CacheSize'], 64 * 1024 * 1024)
                    self.assertTrue(settings['DisableUpload'])
                    self.assertFalse(settings['UseDisk'])
                    settings.update({'DisableDHT': True, 'DisablePEX': True, 'RetrackersMode': 0,
                                     'EnableDebug': True, 'DisableUTP': True, 'ForceEncrypt': False})
                    client.call('/settings', {'action': 'set', 'sets': settings}, timeout=30)
                    progress = []
                    try:
                        url, torrent_hash = prepare_torrent(client, origin + '/test.torrent', 0,
                                                             lambda percent, message: progress.append(percent), timeout=40)
                    except Exception:
                        print('Seed port:', state['port'], 'seed state:', handle.status().state,
                              'seed peers:', handle.status().num_peers, 'announces:', len(announces))
                        print('Seed alerts:', [str(alert) for alert in seed.pop_alerts() if any(s in type(alert).__name__ for s in ('error','disconnect','connect','blocked'))][-20:])
                        raise
                    self.assertEqual(torrent_hash, expected_hash)
                    self.assertTrue(announces)
                    self.assertIn(100, progress)
                    for start, end in ((0, 1023), (1048576, 1049599), (len(payload) - 1024, len(payload) - 1)):
                        req = Request(url, headers={'Range': 'bytes={}-{}'.format(start, end)})
                        with OPENER.open(req, timeout=10) as response:
                            self.assertEqual(response.status, 206)
                            self.assertEqual(response.read(), payload[start:end + 1])
                    self.assertGreater(handle.status().total_upload, 0, 'Data must have come from the BitTorrent seed')
                    client.remove(torrent_hash)
                    self.assertFalse(client.call('/torrents', {'action': 'list'}))
                    with self.assertRaises(InterruptedError):
                        prepare_torrent(client, origin + '/test.torrent', 0, cancelled=lambda: True, timeout=10)
                    self.assertFalse(client.call('/torrents', {'action': 'list'}))
                    process = engine.process
                finally:
                    engine.stop()
                    seed.pause()
                    seed.remove_torrent(handle)
                    del handle
                    del seed
                self.assertIsNotNone(process.poll())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        print('Verified real engine startup, BitTorrent peer download, buffering, HTTP seeking, cancellation and shutdown.')


if __name__ == '__main__':
    unittest.main(verbosity=2)

