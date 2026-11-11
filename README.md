# Crimson Blood Requiem for Kodi

CBR is a Kodi add-on with movie and TV catalogues, search, Live TV categories, multiple Stremio-compatible manifest sources, a built-in torrent player, a crimson space skin, and an optional setup wizard.

## Download packages

Use the repository ZIP for your Kodi platform. It installs the CBR repository; from there install the video add-on, skin and setup wizard.

| Platform | Kodi repository installer | Direct add-on installer |
| --- | --- | --- |
| Windows x64 | [`CBR-Windows-Repository-0.1.7.zip`](downloads/Windows/CBR-Windows-Repository-0.1.7.zip) | [`plugin.video.stremio.bridge-0.5.5.zip`](downloads/Windows/plugin.video.stremio.bridge-0.5.5.zip) |
| Fire TV / Android TV | [`CBR-Fire-TV-Android-Repository-0.1.3.zip`](downloads/Fire-TV-Android/CBR-Fire-TV-Android-Repository-0.1.3.zip) | [`plugin.video.stremio.bridge-0.5.5-android.zip`](downloads/Fire-TV-Android/plugin.video.stremio.bridge-0.5.5-android.zip) |

Fire TV torrent playback also needs the separate [CBR Kodi Companion APK](downloads/Fire-TV-Android/CBR-Kodi-Companion-0.1.0.apk). Install that Android app once; the Kodi add-on starts its foreground service automatically when a torrent source is selected. The APK must be sideloaded on Fire TV and cannot be installed by Kodi's add-on repository.

The [setup guide](outputs/CBR-Kodi-Build-README.md) covers both installs. The wizard and skin ZIPs are also in each platform's download folder.

## Install on Kodi

1. Copy the platform repository ZIP to the Kodi device.
2. In Kodi, select **Add-ons → Install from zip file** and choose the repository ZIP.
3. Open **Install from repository** and select **CBR Add-on Repository** on Windows or **CBR Android Add-on Repository** on Fire TV/Android.
4. Install **Crimson Blood Requiem**, **CBR Setup Wizard**, and **Crimson Blood Requiem Skin**.
5. Launch the wizard and choose **Apply CBR space interface**.

You can install the direct add-on ZIP instead of the repository, then install the wizard and skin from their separate ZIPs in the same folder.

### Fire TV source install

Add this as a Kodi File Manager source:

`https://anakra1.github.io/androitdtvfire/`

Name it `CBR Fire TV`, then choose **Add-ons → Install from zip file → CBR Fire TV → CBR-Fire-TV-Android-Repository-0.1.3.zip**. The root `index.html` lists the repository ZIP in a format Kodi can browse.

## Android / Fire TV note

The separate CBR Kodi Companion app downloads the matching official TorrServer MatriX.150 binary on first torrent playback and checks its SHA-256. It runs TorrServer as an Android foreground service on `127.0.0.1:8766`; the Kodi add-on launches it when needed and uses Kodi's normal player. Install the companion APK once before playing torrent sources. Kodi-native HTTP/HLS playback and the catalogue UI remain available without it.

The project supports Android ARM64, ARMv7, x86_64 and x86. Most Fire TV devices use ARM64.

## Provider settings and privacy

This repository uses public defaults and does not contain the personalized MediaFusion URL or any account tokens. Add any private or device-specific manifest from **Sources and player settings → Manage sources / add manifest URL** on each Kodi device. Keep personalized URLs out of public commits.

## Source and packaging

- `work/combined/plugin.video.stremio.bridge` — Kodi add-on source.
- `work/combined/skin.crimsonbloodrequiem` — CBR Kodi skin.
- `work/combined/script.crb.wizard` — interface setup and restore wizard.
- `work/combined/build_combined.py` and `build_crb_setup.py` — package builders.
- `downloads/` — ready-to-install platform packages.
- `source/TorrServer-MatriX.150-source.zip` — corresponding TorrServer source distribution.

To rebuild the packages on Windows, install Python 3 and run `build_combined.py`, then `build_crb_setup.py` from `work/combined`. The builds create the plugin, repository, skin and wizard ZIPs in `outputs/`.

The Kodi integration is GPL-3.0-or-later and includes earlier MIT-licensed components with their notices. TorrServer is GPL-3.0; its license and matching source are included. Provider manifests supply listings and streams; CBR does not include media files.
