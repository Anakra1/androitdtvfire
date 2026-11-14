# Accepted CBR baseline — 14 November 2026

Stuart selected the current PC configuration as the basis for Windows and Android/Fire TV.

## Features and sources

- Cinemeta movie and TV series listings, artwork and episode information.
- Torrentio movie and episode torrent sources, with CBR's integrated torrent downloading, buffering and Kodi playback.
- Samsung TV Plus UK as the main native Kodi TV source: 257 channels with XMLTV guide data at verification. The 21 protected channels currently unsupported by the maintained Samsung Kodi integration are excluded.
- Configured Sports Streams Live Now catalogue alongside Samsung: 22 merged entries at verification, grouped under Sports. Counts change as events change. Sports programme guide coverage has not been established.
- Existing crimson space-themed CBR interface and PC/phone source configuration tool.

## Verification and limits

Windows PC: Samsung Sky News and Sky Sports Classics played. Sports Streams Sky Sports News played through adverts into Soccer Saturday. TNT Sport 1 displayed an upstream Stream Interrupted message; remaining feeds are not all verified.

Torrent playback: Pioneer One S01E01 selected the correct filename from a season pack and played through the installed CBR route. Sintel played using WebTorrent's official test torrent. Seeking, pause/resume and session cleanup passed. The first Torrentio Sintel source stalled on metadata and was cancelled. Full-length playback was not tested.

## Packaging status

The verified local PC add-on reports 0.9.0.1. Its source is preserved in work/samsung090pc/plugin.video.stremio.bridge, including the sport catalogue support in resources/lib/pvr.py.

Release **0.10.1**, with **CBR Setup Wizard 0.2.0**, packages this baseline for Windows and Android/Fire TV. The full-install entry point installs the video add-on, skin and official IPTV Simple Client, prepares CBR's own TV instance, downloads the guide, builds channels and applies the crimson interface. Android also receives the in-Kodi engine dependency. The standalone video package remains available for updates. Existing personalised manifests are retained; the original 0.9.0 rollback archives remain unchanged.

Both ZIPs passed syntax, archive, version, matching-code and dependency checks. Isolated fresh-profile and upgrade checks passed, including retention of the accepted PC's configured links. The Windows ZIP's online source checks returned 257 Samsung UK channels and 32 Sintel movie streams. Android's ARMv7, ARM64 and x86-64 native libraries were checked for their expected ELF architectures. Playback on the actual Android/Fire TV device remains required; package checks are not an Android playback test.

The configured sports link is private device configuration; keep it out of public source archives. Preserve the ability to replace expired links through PC/phone setup. Local settings snapshots are stored in ignored work/accepted-baseline/ for recovery.

Full-install verification: actual ZIP contents configured a fresh isolated profile with 291 current TV entries, 257 guide matches and 2,234 programme entries. An unrelated IPTV instance was preserved. Cancellation, failed channel-build handling and wizard entry-point checks passed, including client reload, previous-skin backup and completion reporting. Official IPTV Simple packages were available for Windows x86-64, Android ARMv7 and Android ARM64. This is not an Android hardware playback test.
