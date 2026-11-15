# CBR 0.10.5 — startup repository checks

Windows and Android share the current CBR browsing code. About 30 seconds after startup, the service asks Kodi to refresh enabled repositories once while idle. It waits for network startup and full setup, times out after five minutes and avoids repeated checks when its own service restarts after an update. Disable in CBR Configure / Updates.

Kodi owns package verification, dependencies and installation; the service does not modify update preferences, native databases, provider URLs or userdata. Automatic installation requires Kodi automatic updates, component Auto-update enabled, and the component installed from its CBR repository. Manual/full-bundle installations need a one-time Versions / Update selection from the matching CBR repository. The startup check is not an independent ZIP downloader and cannot silently convert manual origins.

Android video: cbr0105.zip; complete ARM setup: fulla024.zip / wizard 0.2.4. Windows: cbrwindows.zip / full.zip / wizard 0.2.1. Old versioned archives and 0.9.0 rollback files are retained. Windows receives the shared 0.10.4 browsing features and skin 0.1.2 in this release.

Validation: verify_startup.py covers timing, idle/setup/network guards, one request, cooldown, opt-out and offline timeout. verify_packages.py checks feed versions/checksums, dependencies, package syntax, website targets and bundled digests. verify_full.py checks ARM32/64 bootstrap, cancellation and upgrade preservation; its final guide check needs network access. Fire TV native playback remains a device test.
