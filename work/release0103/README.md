# CBR Android / Fire TV 0.10.3

Adds the BBC-only Free-TV feeds and DuckKota UK channels alongside the existing Samsung UK and Sports Streams sources. Existing private configured manifests and disabled-provider preferences are retained. UK TV is available as a guide group; the Sky guide tab is removed. Channel 4, Channel 5 and Sky News Weather are hidden by default because their currently supplied streams failed testing. They can be made visible through the channel editor if working alternatives become available. Untested channels are retained.

Includes the New movies Â· CBR home shelf and Movies directory, using the connected Cinemeta New catalogue and normal CBR source selection. Metadata refreshes after 15 minutes. Old release years and explicit future release dates are filtered out.

For an existing Android / Fire TV installation, install **fulla022.zip** from the existing CBR source, then open **Program add-ons â†’ CBR Setup Wizard â†’ Full install / repair**. Restart Kodi once it completes. This updates the bundled video add-on to 0.10.3 and skin to 0.1.2 and configures the channels/guide. The installer itself is 0.2.2. The source URL remains https://anakra1.github.io/androitdtvfire/ . No companion APK or new source URL is required.

The repository also exposes the video, skin and wizard updates separately. Kodi's built-in Python is the full installer's only pre-install requirement. The verified ARM playback engine and Kodi 21 ARM native IPTV/inputstream dependencies remain bundled. Windows public installers and frozen rollback packages are unchanged.

Full install performs a one-time refresh of CBR's IPTV configuration so Kodi drops the cached empty Sky group and imports the corrected BBC One schedule. The previous CBR configuration is retained disabled; other IPTV configurations are untouched. Repeating setup reuses the new CBR configuration.

BBC One, BBC Two and CBBC playback, the UK guide group and movie/source navigation were checked on Windows. Other added BBC manifests responded, but some channels are part-time. Android ARM32/ARM64 installation and profile checks are automated; playback on Stuart's actual Fire TV remains a device-side test. Provider availability and configured Sports Streams expiry still apply.

Private profiles and test outputs stay under ignored outputs folders. No personal manifest tokens belong in the public ZIPs.
