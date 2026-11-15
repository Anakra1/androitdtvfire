# CBR 0.11.0 / Setup Wizard 0.3.0

Matching Windows and Android maintenance release. Build from the frozen platform-specific 0.10.5 archives; shared changes live in overlay/. Run build.py with the project Python 3.12 runtime.

## Included

- Check/repair screen with runtime versions, repository origin, update policy, player and guide state.
- Bounded source checks distinguish catalogue availability, small HTTP video samples, renewal notices and observed native playback. A sample response does not prove full playback or audio language.
- Public Pluto UK M3U migration and Pluto/Freeview guide feeds, preserving custom sources and user preferences. BBC programme mappings corrected.
- Favourites-first TV groups, synchronized favourites, editable channel names/numbers/groups and visibility through paired setup.
- Paired, redacted diagnostics and recent errors; authentication, origin checks and restore confirmation required.
- Layout-only backups by default, explicit personal-source export, validated cross-device restore with saved previous settings and rollback on write failure.
- Wizard removal of explicitly identified CBR components, with native skin-switch instructions, unrelated dependency checks and optional CBR settings removal. Other Kodi add-ons and independent TV instances remain.

## Validation

verify_features.py exercises the actual packaged code, including malformed guide backup rejection before writes, backup rollback, migration idempotence, paired HTTP guards and isolated uninstall boundaries.

verify_packages.py checks both feeds/checksums, archive syntax, platform dependencies, preserved Windows native payloads, nested bundle digests, aliases and website targets. verify_full.py exercises fresh ARMv7/aarch64 bootstrap, repeated install, cancellation/corrupt archives and online TV/guide preparation.

Windows Kodi 21.3 decoded Pluto UK H.264 720p and English AAC across two samples; observed playback was recorded. Native guide contains BBC One and BBC Two schedules. Real Windows paired diagnostics/backup/channel-edit/repair endpoints were exercised. Final platform packages installed on Windows with personal settings preserved.

## Limits

Physical Fire TV playback and uninstall remain device-side tests; automated ARM package checks do not establish hardware playback. The paired web page passed JavaScript/API checks but browser visual QA was unavailable because browser launch approval timed out. Source availability can change. Native Kodi sorting may override playlist order. Users still control Kodi automatic-update settings and must link manually installed packages to the appropriate repository once.

FilmOn was discarded at Stuart's request and is not included in this release. No private manifest, playback session, pairing secret or machine-specific diagnostic output belongs in published packages.
