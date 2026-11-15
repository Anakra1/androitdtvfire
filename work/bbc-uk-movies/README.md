# Windows BBC feeds, UK TV group and Movies home

Applied to Stuart's local Windows CBR 0.9.0.1 trial on 15 November 2026. Public packages and Android are unchanged.

The Free-TV UK playlist is imported as a BBC-only provider: BBC One, Two, Three, Four, Alba, Scotland, News, Parliament, CBBC and CBeebies. Other Free-TV channels and radio are excluded. The remote playlist is reloaded for stream resolution. Its trailing circled availability markers are removed from display names so BBC channels merge with existing alternatives. Provider priority puts these feeds first while keeping old alternatives. Kodi still handles PVR playback through the existing resolver.

`UK TV` is an additional M3U/PVR group for GB channels. Existing category groups and guide mappings remain available. BBC One is explicitly mapped to the Yorkshire schedule matching the selected stream; ambiguous regional names are not guessed. Cached sporting event listings had changed since the earlier export; the existing source selections are retained.

Both the CBR Movies home item and Kodi's Movies home section show a new poster shelf. Movies opens a poster-only CBR directory; existing local-library shelves remain on home when populated. It uses the connected Cinemeta New/year catalogue, excludes incorrect release years and explicit future release dates, caches metadata for 15 minutes, and opens the normal CBR source selection on click. It does not bulk import movies into the Kodi library or download video in the background.

Checks: Python/XML parsing; BBC-only filtering; UK vs international grouping; preferred-provider merging; ten BBC HLS manifests returned HTTP 200. Windows Kodi loaded the UK TV group with 452 channels, and the full export contained 470 channels. BBC One, BBC Two and CBBC produced native PVR video and audio; BBC One's moving picture was checked across captures. Other BBC feeds were checked at manifest level only and some are part-time. Kodi returned 43 current-year movie entries with poster art; opening The Mongoose returned 138 source entries without starting a movie.

The BBC One Yorkshire mapping exports 69 programme entries, including today's schedule. Kodi's existing EPG cache still showed an empty BBC One row at final inspection; its next EPG import has not been confirmed. Other tested BBC guide rows were populated. Do not claim every guide row is already complete.

`prepare.py` stages reviewed code from the original backups. `install_windows.py` deploys while Kodi is closed, backs up profile files, selects the BBC source, merges cached existing sources and exports the guide. Private profile backups and verification records are under ignored `outputs/verified-live-bbc-uk-movies-20261115/`; never include those in release packages. Merge these changes into the release tree rather than copying the older Windows entry point wholesale.
