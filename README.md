# Crimson Blood Requiem 0.10.1

Kodi 21+ for Windows, Android TV and Fire TV. Uses the accepted Samsung UK / Sports Streams baseline, with Cinemeta listings and Torrentio movie and episode sources. The crimson space skin and wizard remain optional.

Install the matching CBR repository from https://anakra1.github.io/androitdtvfire/ and install the video add-on from that repository. On Android/Fire TV, Kodi installs the CBR Playback Engine dependency automatically. No companion APK is needed. Windows includes its own engine and has no Android dependency.

Restart Kodi after updating. Existing personalised manifests and channel settings are retained. Only obsolete public MediaFusion and TVVoo presets are disabled. Fresh installs include Samsung TV Plus UK and its programme guide, Cinemeta, Torrentio, Pluto TV and the public Sports Streams manifest. Sports needs a current configured provider manifest; add it through Sources and player settings or the PC/phone setup page. Configured sports links are not shared in these public packages.

For native TV, open CBR → Live TV → Kodi TV and guide → Set up Kodi TV / IPTV Simple Client, then build/update channels and guide. The Samsung UK and Sports Streams Live Now catalogues are selected. Provider channel availability changes, and sports programme information may be unavailable.

Windows playback was checked with Samsung Sky News / Sky Sports Classics, Sports Streams Sky Sports News, Sintel and Pioneer One S01E01. Torrent seeking, pause/resume and stop cleanup passed. TNT Sport 1 showed an upstream feed interruption. Not all channels or full-length films were tested. Android packages share the same Python code and existing native engine dependency; playback still needs checking on the actual device.

This release does not overwrite the original 0.9.0 rollback packages.

## Full new installation

Install the matching repository, then install CBR Setup Wizard from Program add-ons. Kodi resolves the video add-on, skin, IPTV Simple Client and Android engine dependency automatically. Alternatively install full.zip after the matching repository is installed. Open the wizard and choose Full install / repair, wait for the channel/guide build, then restart Kodi once. Sports Streams still needs a configured provider link.

Release source and checks: work/release0101/.
