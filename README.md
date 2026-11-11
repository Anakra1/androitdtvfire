# Crimson Blood Requiem for Kodi

CRB is a Kodi add-on with movie and TV catalogues, search, Live TV categories, multiple Stremio-compatible manifest sources, a built-in torrent player, a crimson space skin, and an optional setup wizard.

## Download packages

Use the repository ZIP for your Kodi platform. It installs the CRB repository; from there install the video add-on, skin and setup wizard.

| Platform | Kodi repository installer | Direct add-on installer |
| --- | --- | --- |
| Windows x64 | [`repository.crb-0.1.4.zip`](downloads/Windows/repository.crb-0.1.4.zip) | [`plugin.video.stremio.bridge-0.5.3.zip`](downloads/Windows/plugin.video.stremio.bridge-0.5.3.zip) |
| Fire TV / Android TV | [`repository.crb.android-0.1.0.zip`](downloads/Fire-TV-Android/repository.crb.android-0.1.0.zip) | [`plugin.video.stremio.bridge-0.5.3-android.zip`](downloads/Fire-TV-Android/plugin.video.stremio.bridge-0.5.3-android.zip) |

The [setup guide](outputs/CRB-Kodi-Build-README.md) covers both installs. The wizard and skin ZIPs are also in each platform's download folder.

## Install on Kodi

1. Copy the platform repository ZIP to the Kodi device.
2. In Kodi, select **Add-ons → Install from zip file** and choose the repository ZIP.
3. Open **Install from repository** and select **CRB Add-on Repository** on Windows or **CRB Android Add-on Repository** on Fire TV/Android.
4. Install **Crimson Blood Requiem**, **CRB Setup Wizard**, and **Crimson Blood Requiem Skin**.
5. Launch the wizard and choose **Apply CRB space interface**.

You can install the direct add-on ZIP instead of the repository, then install the wizard and skin from their separate ZIPs in the same folder.

## Android / Fire TV note

The Android add-on downloads the matching official TorrServer MatriX.150 binary on first torrent playback and checks its SHA-256. That download is about 61 MB. Some newer Android builds block Kodi from launching binaries stored in add-on data; those devices need a companion service app for torrent playback. The current package does not include that helper, and it has not been tested on Fire TV hardware. Kodi-native HTTP/HLS playback and the catalogue UI remain available.

The project supports Android ARM64, ARMv7, x86_64 and x86. Most Fire TV devices use ARM64.

## Provider settings and privacy

This repository uses public defaults and does not contain the personalized MediaFusion URL or any account tokens. Add any private or device-specific manifest from **Sources and player settings → Manage sources / add manifest URL** on each Kodi device. Keep personalized URLs out of public commits.

## Source and packaging

- `work/combined/plugin.video.stremio.bridge` — Kodi add-on source.
- `work/combined/skin.crimsonbloodrequiem` — CRB Kodi skin.
- `work/combined/script.crb.wizard` — interface setup and restore wizard.
- `work/combined/build_combined.py` and `build_crb_setup.py` — package builders.
- `downloads/` — ready-to-install platform packages.
- `source/TorrServer-MatriX.150-source.zip` — corresponding TorrServer source distribution.

To rebuild the packages on Windows, install Python 3 and run `build_combined.py`, then `build_crb_setup.py` from `work/combined`. The builds create the plugin, repository, skin and wizard ZIPs in `outputs/`.

The Kodi integration is GPL-3.0-or-later and includes earlier MIT-licensed components with their notices. TorrServer is GPL-3.0; its license and matching source are included. Provider manifests supply listings and streams; CRB does not include media files.
