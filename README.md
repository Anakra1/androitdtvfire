# Crimson Blood Requiem

Kodi 21+ for Windows, Android TV and Fire TV. Uses the accepted Samsung UK / Sports Streams baseline, with Cinemeta listings and Torrentio movie and episode sources. The crimson space skin and wizard remain optional.

Install the matching CBR repository from https://anakra1.github.io/androitdtvfire/ and install the video add-on from that repository. On Android/Fire TV, Kodi installs the CBR Playback Engine dependency automatically. No companion APK is needed. Windows includes its own engine and has no Android dependency.

Restart Kodi after updating. Existing personalised manifests and channel settings are retained. Only obsolete public MediaFusion and TVVoo presets are disabled. Fresh installs include Samsung TV Plus UK and its programme guide, Cinemeta, Torrentio, Pluto TV and the public Sports Streams manifest. Sports needs a current configured provider manifest; add it through Sources and player settings or the PC/phone setup page. Configured sports links are not shared in these public packages.

For native TV, open CBR → Live TV → Kodi TV and guide → Set up Kodi TV / IPTV Simple Client, then build/update channels and guide. The Samsung UK and Sports Streams Live Now catalogues are selected. Provider channel availability changes, and sports programme information may be unavailable.

Windows playback was checked with Samsung Sky News / Sky Sports Classics, Sports Streams Sky Sports News, Sintel and Pioneer One S01E01. Torrent seeking, pause/resume and stop cleanup passed. TNT Sport 1 showed an upstream feed interruption. Not all channels or full-length films were tested. Android packages share the same Python code and existing native engine dependency; playback still needs checking on the actual device.

This release does not overwrite the original 0.9.0 rollback packages.

## Full new installation

Install the matching repository, then install CBR Setup Wizard from Program add-ons. Kodi resolves the video add-on, skin, IPTV Simple Client and Android engine dependency automatically. Alternatively install full.zip after the matching repository is installed. Open the wizard and choose Full install / repair, wait for the channel/guide build, then restart Kodi once. Sports Streams still needs a configured provider link.

Release source and checks: work/release0120/.

## Command interface update

Video 0.12.0, skin 0.2.0 and wizard 0.4.0 add title pages, watchlist, confirmed Continue Watching/resume/next episode, sports artwork/favourites/team pins, cancellable loading and a shared Setup dashboard. Both platforms retain their existing playback engines and private settings. Use the matching full installer to update all components together; a video-only ZIP does not update the skin. See the website guide for usage. Android installer/ABI checks pass; physical Fire TV playback validation remains outstanding.

Movie and episode quality filtering (0.12.1): default 4K + 1080p, remembered per device; change from the link list or Configure → Movies and series links. Link counts and hidden CAM notices stay visible. Quality comes from provider labels, not a playback test. Source and checks: work/release0121/.

Exit controls (video 0.12.2 / skin 0.2.1): Exit CBR opens Kodi Add-ons; Quit Kodi confirms before closing the application. Update both video and skin for the Home/sidebar buttons. Current wizard/full installer is 0.4.2. Release source: work/release0122/.

Android compatibility update: video 0.12.3, Playback Engine 0.1.2, wizard 0.4.3. Fixes the empty/missing DT_HASH native-loader error. Install engine.zip from the existing source and restart Kodi, or update the Android video addon. Windows remains 0.12.2; skin remains 0.2.1. Source/checks: work/release0123/.
