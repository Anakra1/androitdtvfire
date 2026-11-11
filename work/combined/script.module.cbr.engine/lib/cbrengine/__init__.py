"""Run CBR's bundled shared engine within Kodi. GPL-3.0-or-later."""
import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import struct
import threading
import time
from urllib.request import ProxyHandler, build_opener

PORT = 8767
_library = None
_lock = threading.Lock()
_opener = build_opener(ProxyHandler({}))


def architecture(machine=None, pointer_size=None):
    machine = (machine or platform.machine()).lower()
    bits = (pointer_size or struct.calcsize('P')) * 8
    if machine in ('arm64', 'aarch64', 'armv7l', 'armv7', 'arm'):
        return 'android-arm64' if bits == 64 else 'android-arm7'
    if machine in ('x86_64', 'amd64', 'i686', 'i386', 'x86'):
        return 'android-amd64' if bits == 64 else 'android-386'
    raise RuntimeError('CBR does not support this Android CPU: {}'.format(machine))


def digest(path):
    result = hashlib.sha256()
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def internal_directory():
    # Kodi's add-ons can live on emulated storage where libraries cannot be
    # mapped executable. Use Kodi's own private internal files directory.
    with open('/proc/self/cmdline', 'rb') as command:
        package = command.read(256).split(b'\0', 1)[0].decode('utf-8')
    if not re.fullmatch(r'[a-zA-Z0-9_.]+', package):
        raise RuntimeError('Cannot identify Kodi private storage.')
    for base in ('/data/data', '/data/user/0'):
        path = os.path.join(base, package, 'files', 'cbr-engine')
        try:
            os.makedirs(path, mode=0o700, exist_ok=True)
            return path
        except OSError:
            continue
    raise RuntimeError('Kodi cannot access its internal playback-engine folder.')


def install_library(addon_path, destination):
    arch = architecture()
    with open(os.path.join(addon_path, 'resources', 'checksums.json'), encoding='utf-8') as source:
        expected = json.load(source).get(arch)
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise RuntimeError('The CBR engine package does not include this CPU.')
    source = os.path.join(addon_path, 'resources', 'lib', arch, 'libcbrengine.so')
    if digest(source) != expected:
        raise RuntimeError('The CBR playback engine failed its integrity check. Reinstall CBR Playback Engine.')
    path = os.path.join(destination, 'libcbrengine-{}.so'.format(expected))
    if not os.path.isfile(path) or digest(path) != expected:
        temporary = path + '.tmp'
        try:
            shutil.copyfile(source, temporary)
            if digest(temporary) != expected:
                raise RuntimeError('Could not copy the CBR playback engine intact.')
            os.chmod(temporary, 0o500)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return path


def alive():
    try:
        with _opener.open('http://127.0.0.1:{}/echo'.format(PORT), timeout=1) as response:
            return response.read(100).startswith(b'MatriX.')
    except Exception:
        return False


def start(data_path):
    global _library
    import xbmcaddon
    with _lock:
        if _library is None:
            addon = xbmcaddon.Addon('script.module.cbr.engine')
            path = install_library(addon.getAddonInfo('path'), internal_directory())
            try:
                _library = ctypes.CDLL(path)
                _library.CBRStart.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int]
                _library.CBRStart.restype = ctypes.c_int
                _library.CBRStop.argtypes = []
                _library.CBRStop.restype = None
            except (OSError, AttributeError) as error:
                _library = None
                raise RuntimeError('Kodi could not load the CBR playback library: {}'.format(error)) from error
        error_buffer = ctypes.create_string_buffer(2048)
        result = _library.CBRStart(PORT, os.fsencode(data_path), error_buffer, len(error_buffer))
        if result:
            raise RuntimeError(error_buffer.value.decode('utf-8', errors='replace') or 'CBR engine startup failed.')
    deadline = time.monotonic() + 30
    while not alive():
        if time.monotonic() >= deadline:
            raise RuntimeError('The integrated CBR playback engine did not become ready.')
        time.sleep(0.1)
    return 'http://127.0.0.1:{}'.format(PORT)


def shutdown():
    with _lock:
        if _library is not None:
            _library.CBRStop()
    # Go shared libraries must remain loaded until Kodi exits. Never dlclose.
