import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent / 'plugin.video.stremio.bridge'
sys.path.insert(0, str(ROOT))


class ServiceTests(unittest.TestCase):
    def load(self, profile):
        mocks = {key: MagicMock() for key in ('xbmc', 'xbmcaddon', 'xbmcgui', 'xbmcvfs')}
        player = MagicMock()
        class FakePlayer:
            def __getattr__(self, name):
                return getattr(player, name)
        mocks['xbmc'].Player = FakePlayer
        mocks['xbmcvfs'].translatePath.return_value = profile
        mocks['xbmcaddon'].Addon.return_value.getSetting.return_value = '128'
        with patch.dict(sys.modules, mocks):
            spec = importlib.util.spec_from_file_location('bridge_service', ROOT / 'service.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        module.ProgrammeUpdater = MagicMock()
        mocks['player'] = player
        return module, mocks

    def test_playback_stop_and_kodi_shutdown_cleanup(self):
        with tempfile.TemporaryDirectory() as profile:
            module, mocks = self.load(profile)
            monitor = mocks['xbmc'].Monitor.return_value
            monitor.abortRequested.side_effect = [False, False, False, False, True]
            player = mocks['player']
            player.isPlaying.side_effect = [False, True, False, False]
            player.getPlayingFile.return_value = 'http://127.0.0.1:9000/stream/video.mp4'
            state = {'engine-request.json': {'time': 1}, 'engine-session.json': {'hash': 'a' * 40}}
            def read(path):
                return state.get(Path(path).name, {})
            def write(path, value):
                state[Path(path).name] = value
            with patch.object(module, 'read_json', side_effect=read), patch.object(module, 'write_json', side_effect=write), patch.object(module, 'Engine') as engine_type:
                engine = engine_type.return_value
                engine.client.endpoint = 'http://127.0.0.1:9000'
                engine.start.return_value = engine.client
                module.main()
                engine.client.remove.assert_called_once_with('a' * 40)
                engine.stop.assert_called_once()
            self.assertEqual(state['engine-session.json'], {})
            self.assertEqual(state['engine-endpoint.json'], {})

    def test_failed_start_releases_child_and_reports_error(self):
        with tempfile.TemporaryDirectory() as profile:
            module, mocks = self.load(profile)
            mocks['xbmc'].Monitor.return_value.abortRequested.side_effect = [False, True]
            with patch.object(module, 'read_json', return_value={'time': 1}), patch.object(module, 'write_json') as write, patch.object(module, 'Engine') as engine_type:
                engine_type.return_value.start.side_effect = RuntimeError('Startup failed')
                module.main()
                engine_type.return_value.stop.assert_called_once()
                self.assertTrue(any(call.args[1].get('error') == 'Startup failed' for call in write.call_args_list))

    def test_second_video_request_reuses_engine_and_is_acknowledged(self):
        with tempfile.TemporaryDirectory() as profile:
            module, mocks = self.load(profile)
            mocks['xbmc'].Monitor.return_value.abortRequested.side_effect = [False, False, True]
            mocks['player'].isPlaying.return_value = False
            times = iter([1, 2])
            def read(path):
                return {'time': next(times)} if Path(path).name == 'engine-request.json' else {}
            with patch.object(module, 'read_json', side_effect=read), patch.object(module, 'write_json') as write, patch.object(module, 'Engine') as engine_type:
                engine = engine_type.return_value
                engine.client.endpoint = 'http://127.0.0.1:9000'
                engine.start.return_value = engine.client
                module.main()
                engine.start.assert_called_once()
                self.assertTrue(any(call.args[1].get('request') == 2 for call in write.call_args_list))


if __name__ == '__main__':
    unittest.main(verbosity=2)

