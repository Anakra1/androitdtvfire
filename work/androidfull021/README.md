# Android / Fire TV full installer 0.2.1

Install **fulla.zip** directly from the existing CBR Kodi file source, then open Program add-ons → CBR Setup Wizard → Full install / repair. No CBR repository installation is needed first. Restart Kodi after setup completes.

The ZIP includes the actual CBR skin, video add-on 0.10.1, ARM torrent engine, update repository, Kodi 21 ARM IPTV Simple Client and its three inputstream dependencies. Its only pre-install dependency is Kodi's built-in Python interface, so a missing skin cannot block the wizard from installing.

The installer verifies package hashes, selects the matching ARMv7 or ARM64 binaries, copies only the named add-on code folders and uses Kodi's UpdateLocalAddons / Addons.SetAddonEnabled APIs to register them. Kodi userdata, personal manifests and unrelated add-ons remain in place. Existing same/newer component versions are retained. Components are enabled in dependency order. ZIP path validation, atomic file writes and manifest-last installation protect against invalid paths and interrupted fresh installs.

This package supports ARM Android/Fire TV devices. Its bundled TV binaries match Kodi 21; other Kodi versions use their installed compatible client or obtain one from Kodi's official repository. The separate Windows installers and feeds are unchanged.

The package is about 87 MiB because it includes the components. Allow the download/install to finish. Fresh-profile checks passed for both ARM variants, including complete dependency closure, skin files, native ELF architecture, repeat setup, damaged archives, cancellation, bootstrap registration flow and channel/guide generation. Native playback on a physical Fire TV is still a device-side test.

Sports Streams still needs a working configured manifest link. Existing links are preserved.

Official bundled IPTV/inputstream packages come from https://mirrors.kodi.tv/addons/omega/ and retain their original metadata and licence files. Sources: https://github.com/kodi-pvr/pvr.iptvsimple, https://github.com/xbmc/inputstream.adaptive, https://github.com/xbmc/inputstream.ffmpegdirect, https://github.com/xbmc/inputstream.rtmp.

Release verification (15 November 2026): both ARM variants and the repository-independent bootstrap passed; a fresh profile built 279 current TV entries with 257 guide matches. ARMv8 32-bit Kodi selects ARMv7 binaries. Windows packages, feed and install-page content are unchanged. Native Fire TV playback still needs a device test.
