# CBR 0.11.3 / Skin 0.1.3 / Wizard 0.3.3

Add the public IPTV-org UK list and NoCords Pluto M3U while preserving the worldwide list for country browsing and existing personal sources. Default native TV selection adds UK and Pluto sources only; it does not import the entire 11k worldwide list. Migration is offline and idempotent, respects disabled/existing providers and channel overrides, and retains all earlier playback fixes.

NoCords Pluto uses stable official Pluto IDs from its logo metadata, the maintained public US XMLTV guide, and an honest CBR/0.11.3 request header. Native testing found the upstream returns HTTP 403 for Kodi's default header; the CBR header succeeds. Supplied explicit playlist headers are retained. Stream selections still refresh the upstream playlist; no expiring session URLs are bundled or published.

Pluto UK and NoCords variants join a Pluto TV group. Existing category groups remain available (UK TV, Movies, Sports, News, Kids, Music, favourites where present). The skin adds native Kodi channel-group selector control 11 as a horizontal tab row on Channels and Guide, with directional remote navigation. TV on Home opens the guide. Tabs are supplied by Kodi, including other installed backend groups; no hardcoded database group IDs are used.

Guide export fills only gaps between genuine programmes with clearly labelled availability notices. Empty schedules get bounded daily notices, not invented programme titles. Real programme coverage counts exclude notices. Notice text does not promise that an upstream stream works. A skin fallback covers empty titles before EPG import.

Build from frozen video 0.11.2, skin 0.1.2 and wizard 0.3.2; keep Playback Engine 0.1.1 and all native binaries unchanged. Android full installer embeds both new video and skin; Windows wizard requires their new versions. Earlier versioned archives remain available.

Validation: migration/disabled/private preservation, stable Pluto identity/header, exported groups, gap-only placeholders/no overlap, accurate real coverage counts, native selector wiring; package/feed checks, maintenance, Pluto-session and ARMv8l regression tests; fresh bundled ARM32/ARM64 installation. Actual public source build loaded 718 visible channels and matched 411 to genuine US guide data with no source failures at test time. Windows Kodi 21.3 imported the channels/groups/EPG, native group switching selected UK TV and Pluto TV, displayed genuine Pluto schedules and missing-information notices, and started NoCords playback with H.264/AAC. No Fire TV hardware validation claimed.

Primary Kodi API references:
- https://kodi.wiki/view/List_of_Built_In_Controls
- https://raw.githubusercontent.com/xbmc/xbmc/21.3-Omega/xbmc/pvr/windows/GUIWindowPVRBase.cpp
