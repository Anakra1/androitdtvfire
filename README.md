# Crimson Blood Requiem for Kodi

CBR provides movie and TV catalogues, posters, separate searches, Live TV categories, multiple Stremio-compatible manifests, and integrated torrent buffering. The optional skin and wizard provide the crimson space interface.

## Fire TV and Android installation

1. In Kodi File Manager, add `https://anakra1.github.io/androitdtvfire/` as a source named CBR.
2. Select **Add-ons → Install from zip file → CBR → repository.cbr.zip**.
3. Select **Install from repository → CBR Android Add-on Repository → Video add-ons → Crimson Blood Requiem**.
4. Accept Kodi’s dependency list, including **CBR Playback Engine**. Kodi installs the playback engine with the video add-on.
5. Open CBR and select a movie or episode and a source. On upgrades from older CBR versions, restart Kodi once so its old service unloads.

Current Android versions: repository **0.1.7**, video add-on **0.7.2**, playback engine **0.1.0**. All playback installation and updates use this one Kodi repository.

Version 0.7.2 checks HTTP availability before automatic live playback and skips explicitly blocked links, allowing a working third or later link to be chosen without a source-selection screen. Checks run on the Kodi device and do not save playback URLs to the catalogue cache. Upstream picture loops cannot be detected reliably from HTTP availability alone.

If Kodi's cached repository listing does not show the latest version, existing Fire TV/Android installations can update directly using **Install from zip file → CBR → cbr072.zip** from the same source. This is the identical 0.7.2 video add-on package, with no uninstall or new source required. Restart Kodi after installing it. Fresh installs should use the repository steps above to install dependencies.

Version 0.7.2 speeds up Live TV navigation with short-lived local catalogue caching, 100-channel pages, fewer file reads/writes and source-specific live playback requests. Use **Refresh channels** to reload a list immediately. The listing cache does not store playback URLs.

Choosing a live channel starts playback directly, without displaying its links. If Kodi reports a startup failure, CBR tries the next compatible direct stream. Stop cancels retries. A manual stream chooser remains available from the channel's long-press context menu. Restart Kodi after updating so the callback monitor loads.

CBR 0.7.2 adds source/country/category browsing for Live TV, a separate search entry, provider channel logos, persistent channel favourites and recently watched channels. Long-press a channel to add or remove a favourite. Restart Kodi after updating to load the playback-history monitor. Programme schedules and a grid EPG require a future schedule-feed integration.

Install **Crimson Blood Requiem Skin** and **CBR Setup Wizard** from the same repository for the optional interface, then run the wizard. The video add-on also works with Kodi’s normal skin.

The existing Windows packages are in [downloads/Windows](downloads/Windows).

## Add or update manifests from a phone or PC

In CBR choose **Source setup (phone / PC)**. This button is also in **Live TV** and **Manage sources**. Kodi shows a local web address and a six-digit pairing code. Keep that screen open.

On a phone or computer connected to the same home network, open the displayed address in its browser and enter the code. Choose **Edit** next to the source you want to update, paste its full configured manifest URL, and save. You can add different providers, select their Live TV categories, enable/disable entries, remove old sources, and refresh enabled source catalogues. When finished, select OK on the Kodi screen and reopen the catalogue.

Kodi hosts this page only while source setup is active, for up to ten minutes. Provider configurations remain on the Kodi device. Pairing is required before a browser can read or change them. No website hosting account is needed for this local setup mode. Guest Wi-Fi isolation or a VPN that blocks local-network access can prevent a phone or PC from reaching the device.

## Sources

Open **Sources and player settings → Manage sources / add manifest URL** to add, rename, disable or remove providers. Private configured manifests belong in device settings and are not included in distributed installers. Public defaults supply catalogues and stream results; availability depends on the provider and peers.

## Implementation and build

Android playback uses a shared engine library loaded inside Kodi through the CBR Playback Engine module. The engine buffers torrents in memory and provides a seekable HTTP stream on loopback for Kodi’s player. Libraries are included in the Kodi dependency and verified before loading. The loader respects the bitness of Kodi’s process.

The source is in `work/combined`. Build native libraries with `build_native_engine.ps1` using Go and Android NDK, then run `build_combined.py` and `build_crb_setup.py`. The Android repository uses its own HTTPS metadata and packages under `android/`, avoiding the former shared localhost repository service.

The integration and TorrServer-derived engine are GPL-3.0-or-later. Earlier MIT notices are preserved. Matching upstream source is included at `source/TorrServer-MatriX.150-source.zip`; CBR’s C ABI wrapper and native build script are included in the repository.
