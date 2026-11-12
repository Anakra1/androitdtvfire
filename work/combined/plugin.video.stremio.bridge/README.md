# Crimson Blood Requiem (CBR) 0.6.2 — Windows, Android TV and Fire TV

**One Kodi add-on includes movies, TV series, a torrent player and Live TV split into TV Channels, Internet TV and Live Sports.** No Elementum, separate Stream Bridge installation, or manual script copying is required.

CBR uses a crimson and dark-red palette, a CBR add-on thumbnail, matching menu artwork and original deep-space fleet fanart. Kodi skins control the navigation highlight colours.

These packages use public provider defaults and contain no personalized MediaFusion URL or account tokens. Add any private manifest URL in Kodi's source settings on each device.

## Install

1. On Windows, use **Add-ons → Install from zip file** and choose `plugin.video.stremio.bridge-0.6.2.zip`. On Android TV or Fire TV, install `CBR-Fire-TV-Android-Repository-0.1.7.zip`, then install Crimson Blood Requiem, the skin and the setup wizard from **Install from repository → CBR Android Add-on Repository**.
2. Restart Kodi once to start the new background player service.
3. Open **Video add-ons → Crimson Blood Requiem** (the crimson **CBR** thumbnail).
4. Choose a movie or TV episode and a source, or open **Live TV** and select a category, catalogue, channel/event and source.

On Fire TV/Android, Kodi automatically installs **CBR Playback Engine** with the video add-on. It loads the bundled shared library inside Kodi and buffers torrent pieces for Kodi’s player. All installation and updates use the CBR Kodi repository.

On a fresh profile, **Cinemeta** supplies movie/TV listings and posters, and **Torrentio** supplies stream results. They are enabled automatically on first launch; no account or default-URL entry is needed. Manifests describe sources and catalogues; the package does not contain movies or guarantee that every listed title has a working source. Playback depends on available peers, providers, network and Kodi codec support.

## Add or update manifests from a phone or PC

In CBR choose **Source setup (phone / PC)**. This button is also in **Live TV** and **Manage sources**. Kodi shows a local web address and a six-digit pairing code. Keep that screen open.

On a phone or computer connected to the same home network, open the displayed address in its browser and enter the code. Choose **Edit** next to the source you want to update, paste its full configured manifest URL, and save. You can add different providers, select their Live TV categories, enable/disable entries, remove old sources, and refresh enabled source catalogues. When finished, select OK on the Kodi screen and reopen the catalogue.

Kodi hosts this page only while source setup is active, for up to ten minutes. Provider configurations remain on the Kodi device. Pairing is required before a browser can read or change them. No website hosting account is needed for this local setup mode. Guest Wi-Fi isolation or a VPN that blocks local-network access can prevent a phone or PC from reaching the device.

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

The Windows x64 engine starts automatically when needed. On Android, the CBR Playback Engine Kodi dependency supplies checksum-verified native shared libraries. CBR loads the matching library for Kodi’s process ABI inside Kodi, including 32-bit Kodi on a 64-bit ARM device. Torrent pieces enter a memory cache and are served over a seekable loopback HTTP stream to Kodi’s player.

**Sources and player settings → Built-in player settings** controls the memory cache: 64, 128 (default), 256 or 512 MB. Restart Kodi after changing it. Engine and Kodi memory usage is higher than the cache alone.

Buffering progress shows download speed and peers. Initial buffering targets 10% of cache, capped by file length; slow sources can time out after two minutes. Seeking can require more buffering. For torrent packs, a supplied filename is matched; otherwise an ambiguous provider index opens a file chooser rather than silently playing the wrong episode.

Cancelling preparation or stopping playback removes the active torrent. The Windows child process stops after the idle timeout. The Android shared library remains resident without an active torrent until Kodi exits. Uploading is disabled; downloads still contact peers.

## Platforms and validation

Version 0.3.1 fixes TV playback for ongoing series such as Nocturne: Cinemeta's `hasScheduledVideos` flag no longer bypasses season/episode selection. An empty embedded stream list also falls back to configured providers instead of displaying no sources. Nocturne's first-episode request returned 74 torrent results during diagnosis; availability can change.

The Android package includes the CBR listings, manifest setup, crimson skin and setup wizard. Add-on 0.6.2 requires the integrated CBR Playback Engine module; Kodi installs it automatically from repository 0.1.7. The engine uses TorrServer’s embedded mode and remains inside the Kodi process. Android ARMv7, ARM64 and x86_64 libraries are included.

Tests cover fresh-profile defaults, migration, multiple enabled sources, poster browsing, TV navigation, library exports, HTTP playback/subtitles, the torrent resolver, cancellation, repeated playback requests and service cleanup. A real-engine test downloads a generated local torrent from a local BitTorrent seed, verifies buffering and byte-correct HTTP range seeking, and checks cancellation/shutdown. The public default endpoints were also checked: Cinemeta returned 50 poster listings and Torrentio returned 14 torrent results for the openly licensed Big Buck Bunny test film. These checks do not establish playback of every source or Kodi codec compatibility.

From the source archive, run `python -m unittest discover -s . -p 'test_*.py' -v`. The opt-in real-engine test needs the **development-only** dependency `libtorrent==2.1.1`: set `STREAM_BRIDGE_LIVE_TEST=1` to include it. Kodi users do not need to install that Python library.

## Source and license

The integration is GPL-3.0-or-later and includes earlier MIT-licensed Movies components, with notices preserved. TorrServer MatriX.150 retains GPL-3.0. The shared-engine wrapper and native build script are included alongside the pinned upstream source archive.

`Crimson-Blood-Requiem-source.zip` contains our source, public defaults, build script and tests. `TorrServer-MatriX.150-source.zip` contains matching upstream engine source and build information. Keep both with the binary when redistributing it.

- [TorrServer release and source](https://github.com/YouROK/TorrServer/releases/tag/MatriX.150)
- [Stremio add-on protocol](https://github.com/Stremio/stremio-addon-sdk/blob/master/docs/protocol.md)
