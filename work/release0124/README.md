# CBR 0.12.4 — Categorised source setup

Builds from immutable Windows video 0.12.2 and Android video 0.12.3. Native Kodi Setup and Manage sources now provide Live TV, Movies, TV Series, Channel Listings, Programmes and Tools. Provider folders filter by metadata and existing live overrides, retaining disabled sources and one saved configuration for shared movie/series providers. Returning from a provider action preserves the selected category.

The paired phone/PC setup page has six accessible tabs. Its source list and editor are shared rather than duplicated, preserving form values across tab switches. Live-specific guide fields are hidden in movie/series views. Channel listings provide a guide-group filter, search and result counts; the existing pending-edit map is retained across tab changes. Pairing, backup, repair and programme-feed controls remain available in their respective categories.

No manifests, guide URLs, player binaries, skin or stored provider settings are changed. `publish.py` prepares both platform repositories, video 0.12.4, full wizard 0.4.4, public aliases and website download instructions. Android's existing ARM engine and other nested components are preserved byte for byte. Windows wizard requires video 0.12.4. Repository feed checksums and every Android nested bundle hash/version are verified during publication preparation.

Run `prepare_setup.py`, then `build.py`, then `verify_setup.py` with the existing Python toolchain. The build checks Python 3.8 syntax/XML, package size and exactly seven changed files. `verify_setup.py` passes five behavioral checks: category classification, source privacy and read-only listing, shared-source URL replacement preserving settings, unique controls, and native menu generation. JavaScript syntax passes `node --check`.

`verify_kodi.py` executed the actual plugin directories and paired setup service in the isolated portable Windows Kodi 21.3 runtime, using package 0.12.4. Native category routing and native/web provider membership match (11 live providers, two shared movie/series providers in the test profile). It caught and fixed a CRLF-sensitive route transformation before passing. The detailed local report is `outputs/verified-live-setup0124-kodi.json` and contains no source URLs or pairing credentials.

Browser visual testing was unavailable because the Windows browser automation surface rejected URL-policy enforcement. No physical Android/Fire TV test is claimed. The regular Windows Kodi installation remains unchanged. The isolated test add-on was backed up before installation.
