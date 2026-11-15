# DuckKota Windows development overlay

Applied locally to the existing Windows CBR 0.9.0.1 installation on 15 November 2026. Android and public installer ZIPs are unchanged.

The user profile now has DuckKota TV (`https://DuckKota.github.io/iptv/playlists/best.m3u`). Its UK catalogue is selected in CBR's Kodi TV export; other countries remain browsable from CBR. The existing Samsung UK and configured sports selections are retained. The DuckKota UK XMLTV feed is added alongside existing guides. The combined build produced 471 TV channels and 320 guide matches.

`m3u.py` overlays `resources/lib/m3u.py`. It removes a Python 3.9-only string call to support this Kodi's Python 3.8, gives DuckKota channels reversible identifiers, resolves fresh per-channel API alternatives without redownloading the worldwide playlist, preserves required headers, and prefers HLS while retaining DASH alternatives. Legacy M3U identities stay unchanged.

`addon.py` is the installed Windows entry point with DASH/inputstream properties added to its PVR resolver. Merge the small PVR resolver change with the release entry point before building a future package; do not blindly replace a newer release with this older installed entry point.

`verify.py` checks targeted stream resolution, API outage fallback, required headers, UK mapping and existing M3U identities. Native Kodi TV/PVR testing confirmed moving BBC One picture and an English audio track. Kodi's PVR elapsed-time API remains zero for this stream, so native window captures provided the moving-picture evidence. An earlier renderer stall was resolved by restarting Kodi and waiting for its interface to load before retesting.

DuckKota provides no ITV1 stream. Its sole Channel 4 and Channel 5 links fail DNS from this PC and are reported offline by DuckKota. Do not describe all four requested channels as working.

Private profile/code backups and test results are under ignored `outputs/verified-live-duckkota-20261115/`. Never include those profile backups in public packages. No private provider URLs belong in this overlay.
