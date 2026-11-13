# Crimson Blood Requiem (CBR) 0.9.2 — Windows, Android TV and Fire TV

**One Kodi add-on includes movies, TV series, a torrent player and Live TV split into TV Channels, Internet TV and Live Sports.** No Elementum, separate Stream Bridge installation, or manual script copying is required.

CBR uses a crimson and dark-red palette, a CBR add-on thumbnail, matching menu artwork and original deep-space fleet fanart. Kodi skins control the navigation highlight colours.

These packages use public provider defaults and contain no personalized MediaFusion URL or account tokens. Add any private manifest URL in Kodi's source settings on each device.

## Install

1. On Windows, use **Add-ons → Install from zip file** and choose `plugin.video.stremio.bridge-0.9.2.zip`. On Android TV or Fire TV, install `CBR-Fire-TV-Android-Repository-0.1.7.zip`, then install Crimson Blood Requiem, the skin and the setup wizard from **Install from repository → CBR Android Add-on Repository**.
2. Restart Kodi once to start the new background player service.
3. Open **Video add-ons → Crimson Blood Requiem** (the crimson **CBR** thumbnail).
4. Choose a movie or TV episode and a source, or open **Live TV** and select a category, catalogue, channel/event and source.

On Fire TV/Android, Kodi automatically installs **CBR Playback Engine** with the video add-on. It loads the bundled shared library inside Kodi and buffers torrent pieces for Kodi’s player. All installation and updates use the CBR Kodi repository.

On a fresh profile, **Cinemeta** supplies movie/TV listings and posters, and **Torrentio** supplies stream results. They are enabled automatically on first launch; no account or default-URL entry is needed. Manifests describe sources and catalogues; the package does not contain movies or guarantee that every listed title has a working source. Playback depends on available peers, providers, network and Kodi codec support.

## Windows install dependency fix (0.9.2)

The Windows package now uses only its bundled Windows engine and no longer requires the Android CBR Playback Engine module. Platform-specific manifests prevent the Android package from being offered as a Windows update. To recover a failed Windows install, choose **Install from zip file → CBR → cbrwindows.zip**, then restart Kodi. Android/Fire TV retains its existing native-engine dependency; working 0.9.1 installations do not need this fix.

## Windows repository installation

Use the same Kodi source: `https://anakra1.github.io/androitdtvfire/` (name it CBR). Choose **Install from zip file → CBR → windowsrepo.zip**, then **Install from repository → CBR Windows Add-on Repository → Video add-ons → Crimson Blood Requiem**. This separate feed keeps the Windows playback engine in subsequent updates. Existing installations can use **Install from zip file → CBR → cbrwindows.zip** after installing the Windows repository. Android/Fire TV continues to use `repository.cbr.zip`.

## Add or update manifests from a phone or PC

In CBR choose **Source setup (phone / PC)**. This button is also in **Live TV** and **Manage sources**. Kodi shows a local web address and a six-digit pairing code. Keep that screen open.

On a phone or computer connected to the same home network, open the displayed address in its browser and enter the code. Choose **Edit** next to the source you want to update, paste its full configured manifest URL, and save. You can add different providers, select their Live TV categories, enable/disable entries, remove old sources, and refresh enabled source catalogues. When finished, select OK on the Kodi screen and reopen the catalogue.

Kodi hosts this page only while source setup is active, for up to ten minutes. Provider configurations remain on the Kodi device. Pairing is required before a browser can read or change them. No website hosting account is needed for this local setup mode. Guest Wi-Fi isolation or a VPN that blocks local-network access can prevent a phone or PC from reaching the device.

## Channel cleanup and guide editor (0.9.1)

CBR now combines spacing-only channel duplicates while keeping alternative streams. Existing channel numbers, old channel routes, regional/+1 services and individually edited rows are preserved. Enabled Kodi TV lineups rebuild automatically after restarting the updated add-on; **Build / update TV channels and guide** can also refresh immediately.

Programme matching understands known UK guide abbreviations and spacing differences. Ambiguous HD/SD entries are used only when their upcoming 24-hour schedules are nonempty and identical. Generic BBC channels are not assigned a regional schedule automatically, and obsolete brands are not assumed to be their replacements.

Open **Source setup (phone / PC)** and use **Kodi TV and guide**. Filter by group, missing programme listings, hidden channels or channels with alternatives. Browse with Previous/Next. **Hide/Show displayed channels** stages changes to the current page; **Save channel changes** applies up to 100 edits at once. Expand **Choose programme guide match** on a channel and select a schedule, then **Apply programme match**. Choose Automatic matching to clear a manual choice. Programme matches apply to all of that channel's alternatives and also work for hidden channels. Reload TV status/channel list after background work finishes. Restart Kodi to apply PVR changes sooner than its 30-minute refresh.

In the same UK test snapshot, 572 channel rows became 557, and channels with upcoming schedules increased from 122 to 158. Guide coverage is still partial. A missing schedule does not mean a stream is dead; no channels are hidden automatically based on guide coverage.

## Kodi TV channels and timeline guide (0.9.0)

1. Update the **video add-on** to 0.9.0 and fully restart Kodi.
2. Open **CBR → Live TV → Kodi TV and guide → Set up Kodi TV / IPTV Simple Client**. Allow Kodi to install its official PVR IPTV Simple Client if needed. CBR builds the channel playlist and connects a separate **CBR TV** instance.
3. Open Kodi's main **TV → Channels** or **TV → Guide**. Select the **CBR TV**, **Freeview**, **Sky** or other channel groups. The existing CBR Live TV browser remains available as a backup.

UK catalogues are selected initially. Use the paired **Source setup (phone / PC)** page's **Kodi TV and guide** section to choose other linear-TV catalogues, change names/numbers/groups, or hide channels. Build/refresh runs in the background; use **Reload status / channels** to see the result. IPTV Simple reads changes every 30 minutes; restarting Kodi applies them sooner. If Kodi already has other IPTV instances, their files and global numbering preference are preserved. Use **Use CBR channel numbers in Kodi TV** if you want backend channel numbers across Kodi.

CBR creates a local M3U playlist of stable channel routes and matching XMLTV programme IDs. Selecting a channel requests fresh streams from its current manifest and selects an available HTTP link. Expiring playback links are not written to the playlist. No companion APK or separate server is required. Channel catalogues refresh every six hours; programme updates rebuild the XMLTV file. Existing IPTV instances are not overwritten.

Freeview/Sky are editable channel groups with starter numbering, not an exact regional provider lineup. Guide coverage depends on XMLTV matches; channels with missing schedules can still play. Sports event catalogues and movie/series catalogues remain in CBR rather than being treated as linear TV channels. The existing CBR skin already styles Kodi's TV and guide windows.

Validated with a separate Kodi 21 profile: native TV groups, channel numbers, current/next programme import, and live playback through a test channel. A public TVVoo UK catalogue exported 572 merged channels and schedules for 122 channels in the test snapshot. This does not guarantee every provider stream or programme schedule is available.

## Programme information: Now / Next (0.8.0)

Restart Kodi after updating. CBR downloads the included **UK programmes** XMLTV feed in the background and refreshes it every six hours. Channel lists use the local indexed schedule database, so opening a country does not download programme data for every channel. The first download must finish before schedules are available. Check **Live TV → Programme information settings → View update status** or choose **Update programmes now**.

Highlight a channel to see programme details in skins that show the item's plot or second label. Long-press a channel and select **Programme information** for the current/next title, start/end times and descriptions. Channel selection still starts live playback directly. The playback information overlay is refreshed every 30 seconds for CBR's active channel without restarting video. Times use the device's local time zone; XMLTV offsets, including daylight-saving changes, are converted before display.

Matching uses explicit XMLTV channel IDs when provided, otherwise country-scoped names. Quality suffixes such as HD may be ignored when the remaining match is unique; regional variants and +1 services are kept distinct. Missing or ambiguous schedules show **Programme information unavailable**. To assign a channel yourself, long-press it and choose **Match programme channel**, then select the correct channel and feed. Choosing **Use automatic matching** removes the override. Overrides survive a streaming manifest URL change and edits to the schedule-feed URL.

The paired **Source setup (phone / PC)** page now has a separate **Programme information** section for XMLTV (.xml/.xml.gz) feeds. Add feeds for other supported countries there; streaming manifests remain separate. Mixed-country sources should keep **Programme country: Automatic from channel**. Only assign a fixed country when the streaming source really contains that country's channels. Multiple feeds for a country use their configured order. Structured native provider schedules are also supported where returned.

The default feed is supplied by [EPGShare01](https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz). Schedules are downloaded to the device, not bundled or hosted in this repository. Availability and channel coverage depend on the feed. Failed, empty or malformed updates preserve the previous schedule database. The native timeline guide is available through Kodi TV setup in version 0.9.0.

## Live stream selection fix (0.7.2)

Automatic live playback checks HTTP responses before choosing a stream. Explicit HTTP errors such as 403/404 are excluded, so two blocked links no longer prevent a working third link from being selected. Checks follow redirects, preserve provider request headers and stop after response headers without downloading video. Up to four checks run together, with a four-second socket timeout; inconclusive timeouts remain available after verified responses. Stream availability can still change after a check, so Kodi playback callbacks retain startup fallback. A successful response does not prove that a channel's video is correct or free of loops.

## Faster Live TV browsing (0.7.1)

Select a live channel to start it directly, without a stream-selection screen. CBR tries compatible direct streams in provider order and uses Kodi's playback callbacks to try the next if startup fails. A working video or a user Stop cancels pending retries. Up to eight alternatives are tried; the short-lived retry plan expires after two minutes and is cleared when video starts. Retry URLs are kept only in the temporary playback plan, not in favourites or catalogue caches. Unsupported transport types and setup notices are not automatically selected. For advanced troubleshooting, long-press the channel and choose **Choose stream manually**.

Live catalogue responses are cached locally for five minutes (one minute in Live Sports). Large responses display 100 channels at a time; **Next page** uses the saved response until more data is needed from the provider. Pressing Back reuses that listing. **Refresh channels** bypasses the cache immediately. Category and configured-URL changes use separate cache entries.

Channel items share one local page record instead of creating two files per channel. Favourites are loaded once per displayed page, and routine cache cleanup runs at most hourly. Selecting a live channel requests metadata and fresh playback sources from its originating provider; movie and TV episode source aggregation is unchanged. Playback URLs and stream responses are not cached by this feature.

## Live TV browsing and saved channels (0.7.0)

Open **Live TV** for **Favourite channels**, **Recently watched**, **Search Live TV**, and the three live sections. Inside a section, choose a source, then a country or catalogue. Providers such as TV Voo show their country browse lists separately from **Search this source**. When a catalogue supplies genres, each genre is a folder alongside **All channels**. Sources that have no country data keep their own catalogue names.

Channel logos appear as thumbnails when supplied by the provider. Long-press a channel on the Fire TV remote (right-click or press C on a PC) and select **Add to CBR favourites**. The same menu removes it. Favourites stay in the Kodi profile and request fresh playback links when opened; they do not save expiring stream URLs. If a source is disabled or removed, its saved channel is marked unavailable.

**Recently watched** keeps the latest 50 live channels whose playback Kodi has started. Failed or cancelled playback does not add an entry. Restart Kodi after this update to load the history monitor. The existing crimson artwork and skin remain in use. Programme information is provided by the schedule layer described above; a grid EPG is not included yet.

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

The Android package includes the CBR listings, manifest setup, crimson skin and setup wizard. Add-on 0.9.1 requires the integrated CBR Playback Engine module; Kodi installs it automatically from repository 0.1.7. The engine uses TorrServer’s embedded mode and remains inside the Kodi process. Android ARMv7, ARM64 and x86_64 libraries are included.

Tests cover fresh-profile defaults, migration, multiple enabled sources, poster browsing, TV navigation, library exports, HTTP playback/subtitles, the torrent resolver, cancellation, repeated playback requests and service cleanup. A real-engine test downloads a generated local torrent from a local BitTorrent seed, verifies buffering and byte-correct HTTP range seeking, and checks cancellation/shutdown. The public default endpoints were also checked: Cinemeta returned 50 poster listings and Torrentio returned 14 torrent results for the openly licensed Big Buck Bunny test film. These checks do not establish playback of every source or Kodi codec compatibility.

From the source archive, run `python -m unittest discover -s . -p 'test_*.py' -v`. The opt-in real-engine test needs the **development-only** dependency `libtorrent==2.1.1`: set `STREAM_BRIDGE_LIVE_TEST=1` to include it. Kodi users do not need to install that Python library.

## Source and license

The integration is GPL-3.0-or-later and includes earlier MIT-licensed Movies components, with notices preserved. TorrServer MatriX.150 retains GPL-3.0. The shared-engine wrapper and native build script are included alongside the pinned upstream source archive.

`Crimson-Blood-Requiem-source.zip` contains our source, public defaults, build script and tests. `TorrServer-MatriX.150-source.zip` contains matching upstream engine source and build information. Keep both with the binary when redistributing it.

- [TorrServer release and source](https://github.com/YouROK/TorrServer/releases/tag/MatriX.150)
- [Stremio add-on protocol](https://github.com/Stremio/stremio-addon-sdk/blob/master/docs/protocol.md)
