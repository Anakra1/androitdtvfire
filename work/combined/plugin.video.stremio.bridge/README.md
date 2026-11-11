# Crimson Blood Requiem (CBR) 0.5.6 — Windows, Android TV and Fire TV

**One Kodi add-on includes movies, TV series, a torrent player and Live TV split into TV Channels, Internet TV and Live Sports.** No Elementum, separate Stream Bridge installation, or manual script copying is required.

CBR uses a crimson and dark-red palette, a CBR add-on thumbnail, matching menu artwork and original deep-space fleet fanart. Kodi skins control the navigation highlight colours.

These packages use public provider defaults and contain no personalized MediaFusion URL or account tokens. Add any private manifest URL in Kodi's source settings on each device.

## Install

1. On Windows, use **Add-ons → Install from zip file** and choose `plugin.video.stremio.bridge-0.5.5.zip`. On Android TV or Fire TV, install `CBR-Fire-TV-Android-Repository-0.1.4.zip`, then install Crimson Blood Requiem, the skin and the setup wizard from **Install from repository → CBR Android Add-on Repository**.
2. Restart Kodi once to start the new background player service.
3. Open **Video add-ons → Crimson Blood Requiem** (the crimson **CBR** thumbnail).
4. Choose a movie or TV episode and a source, or open **Live TV** and select a category, catalogue, channel/event and source.

For torrent playback on Fire TV/Android TV, install `CBR-Kodi-Companion-0.1.0.apk` separately. Kodi's add-on repository cannot install an Android APK; sideload the companion once, then CBR launches its service automatically when you select a torrent stream.

On a fresh profile, **Cinemeta** supplies movie/TV listings and posters, and **Torrentio** supplies stream results. They are enabled automatically on first launch; no account or default-URL entry is needed. Manifests describe sources and catalogues; the package does not contain movies or guarantee that every listed title has a working source. Playback depends on available peers, providers, network and Kodi codec support.

## Add more sources

Open **Sources and player settings → Manage sources / add manifest URL → Add another source / manifest URL**. Choose the provider name or **Other add-on**, then paste its Stremio-compatible manifest URL. Add as many as you need. Kodi requests matching streams from **all enabled providers**, and results are labelled with the provider name.

In the same screen, select a provider to **disable/enable**, **refresh**, **rename**, or **remove** it. Extra catalogues appear under **Movies**, **TV series**, or **Browse all catalogues**. The home menu and Tools menu provide separate **Search movies**, **Search TV series**, and **Search Live TV** entries. Each searches enabled catalogues of that type that advertise search support.

The included defaults are:

- Cinemeta: `https://v3-cinemeta.strem.io/manifest.json`
- Torrentio: `https://torrentio.strem.fun/manifest.json`

Personalised providers can require their own account setup. Their URLs may contain private tokens; keep them in Kodi settings, not in redistributed installers. YouTube results still require Kodi's YouTube add-on. External service webpages and DRM streams are not supplied by the torrent engine.

## Updating an existing installation

This ZIP updates the existing `plugin.video.stremio.bridge` add-on (previously named **Stremio Bridge — Movies**, then **Movie Bridge**) to **Crimson Blood Requiem**. Kodi keeps existing library exports and provider settings because the add-on ID is unchanged. If a customised Cinemeta or Torrentio provider already exists, it is preserved, including its enabled/disabled state. The default provider is added only if that provider is missing during the one-time migration. Removed defaults stay removed on later launches; **Restore missing default providers** adds them back without replacing custom providers.

The older separate **Stream Bridge** add-on is not required by this package. It is not automatically uninstalled. Live TV sources are added once on first launch of version 0.4.0; this rebrand update does not replace configured providers or movie-library exports.

## Live TV

Open **Live TV** from the Crimson Blood Requiem home screen. The home screen also has a dedicated **Search Live TV** option, alongside movie and series search:

- **TV Channels:** your supplied MediaFusion configuration. Its documented `live_tv` endpoint was verified and is exposed as a supplemental catalogue because the manifest does not advertise it. Refreshing the manifest preserves that catalogue and its grouping.
- **Internet TV:** Pluto TV, providing free internet channels in the style of Plex/Pluto services. This is not a connection to a personal Plex server or a Plex account.
- **Live Sports:** the configured Sports Streams service at `sports.highfly.to`, using the configuration ID supplied during setup. It includes Live Now, Today and sport-specific catalogues. The earlier `sports.highfly.dev` address returns a reinstall notice and is not used for playback. StreamsPPV's published endpoint did not return a valid manifest during setup; the supplied Sports Streams replacement is used instead.

Each category has **Add another source** and **Manage sources**. Adding a manifest from a category assigns its live catalogues to that section. In **Manage sources**, select a source and choose **Live TV category** to change the assignment or return to automatic grouping. Multiple providers can coexist, and disabled providers stay disabled when refreshed.

Live events and channel programme lists open their stream sources directly; they are not treated as TV-series seasons. The provider's original media type (for example `sport`) is preserved in its API requests. Playback uses Kodi's native HTTP/HLS player. This feature is an in-add-on browser, not a native Kodi PVR channel grid or full EPG.

Live sources change and may be offline or restricted by their provider. Provider setup notices and known MediaFusion offline-status videos are identified as notices rather than treated as working channel media. During validation, MediaFusion returned 100 catalogue entries; the first tested entry reported no currently live stream. Pluto's Popular catalogue returned 59 channels, and Sports Streams returned 21 Live Now entries and 17 catalogues. Sample Pluto and configured sports URLs both returned HTTP 200 HLS playlists using Kodi-style requests. Video decoding in Kodi still needs channel-by-channel testing.

## Torrent player

The bundled Windows x64 TorrServer engine starts automatically when needed. On Android, install the separate CBR Kodi Companion APK once. It downloads the official Android build matching the device CPU (ARM64, ARMv7, x86_64 or x86) the first time you play a torrent, verifies its pinned SHA-256, and keeps it in the companion app's private data folder. That one-time download is about 61 MB and requires internet access. Both versions download torrent pieces into a memory cache and serve a seekable HTTP video stream to Kodi over `127.0.0.1`. No download-folder selection is needed. Kodi handles video decoding and playback controls.

**Sources and player settings → Built-in player settings** controls the memory cache: 64, 128 (default), 256 or 512 MB. Restart Kodi after changing it. Engine and Kodi memory usage is higher than the cache alone.

Buffering progress shows download speed and peers. Initial buffering targets 10% of cache, capped by file length; slow sources can time out after two minutes. Seeking can require more buffering. For torrent packs, a supplied filename is matched; otherwise an ambiguous provider index opens a file chooser rather than silently playing the wrong episode.

Cancelling preparation or stopping playback removes the active torrent. Abandoned preparations expire, and the child engine stops when idle or when Kodi exits normally. Uploading is disabled in this configuration; torrent downloads still contact peers. Engine and playback logs are disabled by default.

## Platforms and validation

Version 0.3.1 fixes TV playback for ongoing series such as Nocturne: Cinemeta's `hasScheduledVideos` flag no longer bypasses season/episode selection. An empty embedded stream list also falls back to configured providers instead of displaying no sources. Nocturne's first-episode request returned 74 torrent results during diagnosis; availability can change.

The Android package includes the same CBR listings, manifest setup, crimson skin and setup wizard. Torrent playback uses the separate CBR Kodi Companion app; the add-on now requests its launch directly from Kodi's foreground source-selection action, avoiding a launch from the background service. The companion downloads and verifies the matching official TorrServer MatriX.150 Android executable for the device ABI, then runs it in an Android foreground service. Install the companion APK separately; non-torrent HTTP/HLS sources continue to use Kodi's native player.

Tests cover fresh-profile defaults, migration, multiple enabled sources, poster browsing, TV navigation, library exports, HTTP playback/subtitles, the torrent resolver, cancellation, repeated playback requests and service cleanup. A real-engine test downloads a generated local torrent from a local BitTorrent seed, verifies buffering and byte-correct HTTP range seeking, and checks cancellation/shutdown. The public default endpoints were also checked: Cinemeta returned 50 poster listings and Torrentio returned 14 torrent results for the openly licensed Big Buck Bunny test film. These checks do not establish playback of every source or Kodi codec compatibility.

From the source archive, run `python -m unittest discover -s . -p 'test_*.py' -v`. The opt-in real-engine test needs the **development-only** dependency `libtorrent==2.1.1`: set `STREAM_BRIDGE_LIVE_TEST=1` to include it. Kodi users do not need to install that Python library.

## Source and license

The new integration is GPL-3.0-or-later and includes earlier MIT-licensed Movies components, with notices preserved. TorrServer MatriX.150 retains its GPL-3.0 license. Windows includes its engine binary in the add-on ZIP; the Android companion fetches the matching official binary and checks its pinned SHA-256 before launch.

`Crimson-Blood-Requiem-source.zip` contains our source, public defaults, build script and tests. `TorrServer-MatriX.150-source.zip` contains matching upstream engine source and build information. Keep both with the binary when redistributing it.

- [TorrServer release and source](https://github.com/YouROK/TorrServer/releases/tag/MatriX.150)
- [Stremio add-on protocol](https://github.com/Stremio/stremio-addon-sdk/blob/master/docs/protocol.md)
