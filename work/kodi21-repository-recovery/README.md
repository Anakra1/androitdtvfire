# Restore the Kodi 21 repository

kodirepo.zip repackages the unchanged repository.xbmc.org/addon.xml and icon.png from official xbmc/xbmc tag 21.3-Omega, with upstream LICENSE.md and provenance. This is a CBR-packaged recovery ZIP, not a Team Kodi release archive. It points exclusively to the official Omega mirrors, retaining SHA256 verification. Optional UI language resources are omitted; the repository manifest retains its embedded translations.

Install from ZIP using the existing CBR file source. Restart Kodi, then check Install from repository for Kodi Add-on repository. Install IPTV Simple Client from that repository so Kodi selects its own platform build. No Kodi database, personal settings, channels or unrelated add-ons are changed by this archive. Device-side restoration still needs confirmation.
