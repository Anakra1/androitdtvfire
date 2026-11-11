"""Checks for Android process ABI selection and verified library installation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parent / 'script.module.cbr.engine'
spec = importlib.util.spec_from_file_location('embedded_engine', ROOT / 'lib/cbrengine/__init__.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class EmbeddedEngineTests(unittest.TestCase):
    def test_32bit_kodi_on_64bit_arm_kernel_uses_arm7(self):
        self.assertEqual(engine.architecture('aarch64', 4), 'android-arm7')
        self.assertEqual(engine.architecture('aarch64', 8), 'android-arm64')

    def test_x86_process_bitness_is_respected(self):
        self.assertEqual(engine.architecture('x86_64', 4), 'android-386')
        self.assertEqual(engine.architecture('x86_64', 8), 'android-amd64')

    def test_corrupted_bundled_library_is_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'resources/lib/android-arm7/libcbrengine.so'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'original library')
            expected = engine.digest(source)
            (root / 'resources/checksums.json').write_text(json.dumps({'android-arm7': expected}))
            source.write_bytes(b'corrupt library')
            with patch.object(engine, 'architecture', return_value='android-arm7'):
                with self.assertRaisesRegex(RuntimeError, 'integrity check'):
                    engine.install_library(str(root), str(root / 'internal'))

    def test_existing_corrupt_copy_is_repaired_from_verified_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'resources/lib/android-arm7/libcbrengine.so'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'valid packaged library')
            expected = engine.digest(source)
            (root / 'resources/checksums.json').write_text(json.dumps({'android-arm7': expected}))
            internal = root / 'internal'
            internal.mkdir()
            damaged = internal / ('libcbrengine-{}.so'.format(expected))
            damaged.write_bytes(b'damaged previous copy')
            with patch.object(engine, 'architecture', return_value='android-arm7'):
                installed = engine.install_library(str(root), str(internal))
            self.assertEqual(engine.digest(installed), expected)
            self.assertFalse(list(internal.glob('*.tmp')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
