# CBR Playback Engine 0.1.0

A Kodi module dependency for Crimson Blood Requiem 0.6.0. Kodi installs and updates this module automatically from the same repository. The parent add-on service loads the bundled Android shared library using ctypes; it runs TorrServer in embedded mode and serves Kodi over 127.0.0.1:8767.

The loader selects the ABI of the Kodi process, verifies SHA-256, and copies the library into Kodi’s private internal storage so it can be mapped as executable code even when add-ons are stored on emulated storage. Go shared libraries stay loaded until Kodi exits. Torrents are removed after playback or cancellation.

Build from the pinned source/TorrServer-MatriX.150-source.zip using work/combined/build_native_engine.ps1. Supply the paths to Go and Android NDK. The script copies native/main.go into the source tree and uses TorrServer’s documented -checklinkname=0 linker flag. The production libraries were built with Go 1.27.4 and Android NDK r30 for API 23, with nosqlite and c-shared modes. ARMv7, ARM64 and x86_64 are packaged.

GPL-3.0-or-later. Upstream: https://github.com/YouROK/TorrServer/tree/MatriX.150
