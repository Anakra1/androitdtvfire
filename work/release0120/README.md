# CBR 0.12.0 — Command interface release

19 November 2026. Video 0.12.0, skin 0.2.0, wizard 0.4.0 for Windows and Android / Fire TV (Kodi 21).

## Changes

Title pages with artwork, synopsis and play/season choices; local watchlist; confirmed Continue Watching with resume, start-over and next released episode; sports event/channel artwork, favourites, team/competition pins and upcoming events; cancellable metadata/source loading and playback feedback; shared navigation and Setup dashboard. Last-good current-year movie listings survive temporary provider failures. Default Kodi skins use native title choices and retain normal directory views.

Existing repository/addon identities, native engines, provider settings and PVR guide remain in place. No new providers, personal links, test records or private profile files are bundled. Existing settings are not replaced. Older numbered archives are unchanged.

## Install / update

Repository users update video, skin and wizard, then restart Kodi. For all components together use the matching full installer: Android `fulla040.zip`, Windows `full.zip`, then run CBR Setup Wizard → Full install / repair. Confirm the native skin-change prompt. If necessary select Crimson Blood Requiem under Kodi Settings → Interface → Skin. Android `cbr0120.zip` and Windows `cbrwindows.zip` update only video; they do not install the new skin by themselves.

## Build and checks

`build.py` starts from the immutable platform video 0.11.4, wizard 0.3.4 and skin 0.1.3 archives, applies the explicit source overlays, updates feeds/checksums, aliases, nested Android bundle and website links. No prototype profile, private backup, library cache or userdata is copied. Release overlay source is included here for repeatability.

`verify_packages.py`, `verify_full.py`, `verify_features.py`, `verify_arch.py`, `verify_pluto.py`, `verify_reliability.py`, `verify_tv.py` and `verify_command.py` pass. Both actual video ZIPs pass 41 Command behavioural checks, sports source-isolation checks and default-skin view guards. Fresh bundled Android installation is checked for ARM32 and ARM64, including dependencies/checksums and cancellation/rollback. Existing native engine payloads are unchanged.

The actual packaged Windows release was installed only into isolated portable Kodi 21.3. Native fixture video passed decoding, stop/bookmark, resume, unrelated-player isolation, released next-episode readiness and cancellation preserving progress. Windows UI navigation is checked separately. Physical Android/Fire TV playback is not claimed. Provider availability, verification and language remain upstream-dependent.
