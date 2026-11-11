# Crimson Blood Requiem Kodi Setup

CBR has a Windows package and a separate Android TV/Fire TV package. Both include the crimson space skin, setup wizard, movie and series catalogues, Live TV categories, and provider settings.

## Windows

1. In Kodi, choose **Add-ons → Install from zip file** and select `CBR-Windows-Repository-0.1.7.zip`.
2. Open **Install from repository → CBR Add-on Repository → Video add-ons** and install **Crimson Blood Requiem**.
3. Install **CBR Setup Wizard** and **Crimson Blood Requiem Skin** from the same repository.
4. Launch the wizard and choose **Apply CBR space interface**.

## Fire TV and Android TV boxes

1. Install the updated CBR Android repository ZIP from the Kodi source, or use **Add-ons → Install from zip file** and choose `CBR-Fire-TV-Android-Repository-0.1.4.zip`.
2. Open **Install from repository → CBR Android Add-on Repository** and install **Crimson Blood Requiem**, **CBR Setup Wizard**, and **Crimson Blood Requiem Skin**.
3. Launch the wizard and choose **Apply CBR space interface**.
4. Install `CBR-Kodi-Companion-0.1.0.apk` separately on Fire TV. When you choose a torrent source, CBR launches the companion from Kodi's foreground playback action; the first start downloads the matching Android torrent engine (about 61 MB) and verifies it.

The companion supports ARM64, ARMv7, x86_64 and x86 Android devices. Fire TV and most current Android boxes use ARM64. The engine is stored in the companion app's private data and reused on later plays. The device needs internet access for the first engine download. The companion runs the torrent engine in its own foreground service because some Android versions prevent Kodi from launching a downloaded native executable.

The packages are made for Kodi 21 or newer. Installing the repository does not replace Kodi; the optional wizard applies the CBR skin and can restore your previous interface later. Provider URLs and settings remain on the device.

Kodi must be allowed to install add-ons from zip files. The companion is a separate Android APK and must be installed once through a Fire TV APK installer or ADB; Kodi's add-on repository cannot install it.
