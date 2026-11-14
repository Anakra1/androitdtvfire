# CBR 0.9.0 clean-install baseline

The original 0.9.0 playback Python files come unchanged from commit `05f482f`. Windows has its Android engine dependency removed and platform metadata corrected. Android retains CBR Playback Engine 0.1.0. Both retain the original sources, plus the same TVVoo configuration used with the working 0.9.0 setup. No DaddyLive, IPTV-org import or later link-caching code is included.

Use the existing Kodi source: `https://anakra1.github.io/androitdtvfire/`.

## Clean install

1. Switch to Kodi's Estuary skin before removing the CBR skin.
2. Disable/remove the old CBR TV instance in PVR IPTV Simple Client. Leave other providers' instances alone.
3. Uninstall CBR Setup Wizard, then the CBR skin, then the CBR video addon. Choose to remove the CBR addon data when Kodi asks for a fresh configuration. This removes personal CBR manifests, favourites and channel customisations; save any personal links you need first.
4. Uninstall or disable the normal CBR Windows/Android repositories so they cannot offer 0.9.6 over this baseline. Restart Kodi.
5. Install from ZIP using the existing CBR source:
   - **Windows:** `w090repo.zip`.
   - **Android/Fire TV:** `a090repo.zip`.
6. Install from repository → **CBR 0.9.0 Windows Repository** or **CBR 0.9.0 Android Repository** → Video addons → Crimson Blood Requiem. Kodi installs the Android playback dependency where needed.
7. Verify the video addon Information screen shows **0.9.0**. Turn its **Auto-update** option off if a newer CBR repository remains enabled.
8. Restart Kodi, open CBR, then Live TV → Kodi TV and guide → Set up Kodi TV / IPTV Simple Client. Install IPTV Simple from Kodi's own repository first if missing.
9. Optionally install the CBR skin and setup wizard from the same 0.9.0 repository.

`w090.zip` and `a090.zip` are direct video-addon packages. For a clean Fire TV install, use the repository steps so Kodi can obtain the playback dependency.

This restores the earlier addon code and configuration, not historical upstream stream availability. Personal sports/provider configurations may still need their own valid links.

Matching runtime source is available at commit `05f482f`; packaging is reproducible with `work/build_090_release.py`. The engine's matching upstream source remains at `source/TorrServer-MatriX.150-source.zip`.
