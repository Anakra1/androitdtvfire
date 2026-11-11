# Crimson Blood Requiem for Kodi

CBR provides movie and TV catalogues, posters, separate searches, Live TV categories, multiple Stremio-compatible manifests, and integrated torrent buffering. The optional skin and wizard provide the crimson space interface.

## Fire TV and Android installation

1. In Kodi File Manager, add `https://anakra1.github.io/androitdtvfire/` as a source named CBR.
2. Select **Add-ons → Install from zip file → CBR → repository.cbr.zip**.
3. Select **Install from repository → CBR Android Add-on Repository → Video add-ons → Crimson Blood Requiem**.
4. Accept Kodi’s dependency list, including **CBR Playback Engine**. Kodi installs the playback engine with the video add-on.
5. Open CBR and select a movie or episode and a source. On upgrades from older CBR versions, restart Kodi once so its old service unloads.

Current Android versions: repository **0.1.6**, video add-on **0.6.0**, playback engine **0.1.0**. All playback installation and updates use this one Kodi repository.

Install **Crimson Blood Requiem Skin** and **CBR Setup Wizard** from the same repository for the optional interface, then run the wizard. The video add-on also works with Kodi’s normal skin.

The existing Windows packages are in [downloads/Windows](downloads/Windows).

## Sources

Open **Sources and player settings → Manage sources / add manifest URL** to add, rename, disable or remove providers. Private configured manifests belong in device settings and are not included in distributed installers. Public defaults supply catalogues and stream results; availability depends on the provider and peers.

## Implementation and build

Android playback uses a shared engine library loaded inside Kodi through the CBR Playback Engine module. The engine buffers torrents in memory and provides a seekable HTTP stream on loopback for Kodi’s player. Libraries are included in the Kodi dependency and verified before loading. The loader respects the bitness of Kodi’s process.

The source is in `work/combined`. Build native libraries with `build_native_engine.ps1` using Go and Android NDK, then run `build_combined.py` and `build_crb_setup.py`. The Android repository uses its own HTTPS metadata and packages under `android/`, avoiding the former shared localhost repository service.

The integration and TorrServer-derived engine are GPL-3.0-or-later. Earlier MIT notices are preserved. Matching upstream source is included at `source/TorrServer-MatriX.150-source.zip`; CBR’s C ABI wrapper and native build script are included in the repository.
