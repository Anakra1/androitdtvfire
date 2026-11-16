# CBR 0.11.1 / Wizard 0.3.1

Fix Pluto UK channels ending after approximately 25–30 seconds. The public BuddyChewChew UK list supplies session-bearing links. A local continuity check reproduced Movies switching from a five-segment live playlist to an empty ENDLIST within ten seconds; Kids initially returned an empty ENDLIST. This proves the supplied stream termination occurs outside Kodi, but does not establish a universal failure or the provider's internal reason.

The M3U adapter retains the public list for listings, artwork and stable channel IDs. Only stream resolution for the two recognised BuddyChewChew UK raw URLs changes: request a fresh anonymous Pluto session with a unique client ID on each selection, require the requested channel in the returned EPG, and use the returned official stitcher server/path/session parameters. The compatibility fields follow the current public web-client protocol. Ads remain enabled; no region/IP overrides, shared JWTs, decryption, or ad filtering are used. Bootstrap errors are sanitised and the known failing shared session is not used as a fallback. Other M3U sources are unchanged.

The source API shape was checked against Streamlink's maintained Pluto plugin and the publicly available Pluto responses. No external Python dependency or proxy/service is required.

## Validation

- verify_pluto.py exercises the actual packaged code: unique client per selection, ads enabled, no country override/X-Forwarded-For, channel/host validation, generic credential-safe errors, stable catalogue IDs, no session fetch for catalogue browsing, and other M3U sources unaffected.
- Concurrent live checks for Pluto TV Movies and Pluto TV Kids: eight playlist/1 KB video samples over 70 seconds each, advancing media sequence, no ENDLIST or HTTP failures. This is stream continuity, not full decoder or Fire TV hardware playback validation.
- verify_features.py retains maintenance, backup/restore, HTTP pairing, migration, favourites and removal boundary checks.
- verify_packages.py checks both platform feeds, native payload preservation, nested bundle hashes, syntax, aliases and website download paths.
- verify_full.py checks both bundled Android ARM installation paths and fresh guide preparation.

Build only from frozen CBR 0.11.0 and Wizard 0.3.0 archives using build.py. Skin, engine and bundled PVR/inputstream binaries are unchanged. Previous versioned download packages remain available. Only the normal latest aliases and feed entries advance. Private session tokens and resolved stream URLs are never included in these source/test reports or packages.
