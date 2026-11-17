# CBR 0.11.4 / Wizard 0.3.4 reliability tools

Build from frozen video 0.11.3 and wizard 0.3.3. Skin remains 0.1.3 and Playback Engine 0.1.1. Never rewrite their versioned archives. Both Windows and Android full installers include the matching video/wizard versions and existing native components. No new providers or channel URLs are bundled.

## Changes

- Primary addon and Live TV entry points expose Help, repair, updates and recovery. Existing backup/restore, diagnostics and CBR-only guided uninstall remain accessible; the wizard adds a backup/restore entry. Active CBR skin still requires the user's native Kodi skin confirmation before removal. Unrelated addons, settings and TV instances are kept.
- Interactive Check and repair TV uses the same task as both full-install wizards. It names the programme feed/channel source being refreshed, shows elapsed time and supports cancellation between bounded network requests. Android extraction reports package/file progress and checks cancellation during checksum/copy work. The summary separates cached retained channels, source failures and guide failures.
- Channel status supports name search, absent-channel explanation, hidden status, timestamped samples, guide availability and confirmed native playback. Optional channel tests run in batches of three with cancellation and never hide/remove channels. Source errors distinguish no links, renewal notices, HTTP failures, DNS and timeouts. Missing guide data does not stop playback. Existing paired diagnostics include the channel results.
- Confirmed-link preference stores only channel/stream fingerprints and time for six hours, not resolved session URLs. Each selection still resolves fresh links. A confirmed candidate is probed first; otherwise existing concurrent checks select a responding backup. Actual matching Kodi AV-start callbacks confirm preference. Unrelated or stale playback cannot confirm it. Initial PVR decoder errors and early EOF can retry the same uniquely identified native channel up to three times within a short session, excluding failed candidates. User stops, unrelated active playback and ambiguous channel identity cancel retry. Normal CBR Live TV retains its own fallback. Continuous/late stream recovery after established playback is not guaranteed.
- Current component versions, missing/disabled components, repository availability and Kodi update policy are visible together. The check reads only this project's HTTPS repository feed; Kodi owns installation and update settings. Offline results clearly distinguish expected installed-release versions from an online latest check. Full installers update the required components together.
- Channel metadata/M3U/XMLTV exports are staged as a set and rolled back on replacement failure. Failed sources keep cached channels; empty/failed refreshes do not replace usable TV output. Genuine EPG titles and missing-information notices are retained.

## Validation

Packaged unit/integration tests cover confirmed fresh-link preference without long-term URLs, native retry ownership/caps, DNS/HTTP classification, missing channels, component mismatches, cancellation and unchanged visibility, failed-refresh preservation, simulated export failure rollback, task progress and heartbeat cleanup. Existing migration, private settings, backups, restoration, CBR-only removal boundaries, Pluto, group tabs, ARMv8l/native payload and fresh ARM32/ARM64 full-installer checks remain required.

Isolated Windows Kodi 21.3 visual checks showed the tools menu, per-guide progress with elapsed time, successful repair summary (718 channels; 524 matched real listings), explicit failed test-feed reporting and component-version screen. A local fixture returned HTTP 200 with unusable video first, followed by a real public Channel 4 stream: native PVR retried once and decoded 1920x1080 H.264. Test-only sources/channel files were restored afterwards. No Fire TV hardware validation claimed.

Kodi channel/retry API fields checked against the primary 21.3-Omega JSON-RPC schema:
https://raw.githubusercontent.com/xbmc/xbmc/21.3-Omega/xbmc/interfaces/json-rpc/schema/types.json
