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

Release **0.10.0** packages this baseline for Windows and Android/Fire TV. It replaces obsolete fresh-install live defaults, adds Samsung UK programme data and native sports catalogue support, and keeps existing personalised manifests when updating. Android declares its existing script.module.cbr.engine dependency and omits the Windows executable. The frozen 0.9.0 rollback archives and archived 0.9.6 packages remain unchanged.

Both ZIPs passed syntax, archive, version, matching-code and dependency checks. Isolated fresh-profile and upgrade checks passed, including retention of the accepted PC's configured links. The Windows ZIP's online source checks returned 257 Samsung UK channels and 32 Sintel movie streams. Android's ARMv7, ARM64 and x86-64 native libraries were checked for their expected ELF architectures. Playback on the actual Android/Fire TV device remains required; package checks are not an Android playback test.

The configured sports link is private device configuration; keep it out of public source archives. Preserve the ability to replace expired links through PC/phone setup. Local settings snapshots are stored in ignored work/accepted-baseline/ for recovery.
