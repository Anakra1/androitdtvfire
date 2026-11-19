# CBR 0.12.2 — Exit controls

Video 0.12.2, skin 0.2.1, wizard 0.4.2 for Windows and Android / Fire TV. Adds Exit CBR and Quit Kodi on Home, the shared CBR browsing sidebar, the video addon menu and CBR Setup.

Exit CBR opens Kodi’s native Add-on Browser. It keeps the selected skin and does not reset settings. Quit Kodi asks whether to close the application, defaults to Stay in Kodi, and uses Kodi’s normal Quit action. It does not shut down/restart the computer or device. The same addon menu actions work with other skins. The new skin requires video 0.12.2 so the actions cannot be installed against an older addon.

Remote focus navigation includes both new controls. Existing movie progress, quality filters, provider settings and TV data are retained. No personal manifests or profile data are included.

Validation: packaged Python 3.8 syntax/XML/checksums, both-platform 41 Command checks and Sports isolation/default-skin guards, quality-filter checks, and fresh ARM32/ARM64 bundled-install checks pass. Isolated Windows Kodi verified Home buttons, Exit to the native Add-on Browser, cancelled Quit leaving Kodi open, and confirmed Quit closing normally. No physical Fire TV execution claim.

Update video and skin together from the repository. Alternatively use Android fulla042.zip or Windows full.zip, run CBR Setup Wizard → Full install / repair, confirm the skin selection if prompted and restart Kodi. Video-only cbr0122.zip / cbrwindows.zip does not add new skin buttons by itself, but includes Exit/Quit in CBR’s own addon menus.

Build from immutable video 0.12.1, skin 0.2.0 and wizard 0.4.1 using explicit overlays. Existing numbered archives are preserved.
