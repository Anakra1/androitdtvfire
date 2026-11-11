# Crimson Blood Requiem Kodi Setup

CRB has a Windows package and a separate Android TV/Fire TV package. Both include the crimson space skin, setup wizard, movie and series catalogues, Live TV categories, and provider settings.

## Windows

1. In Kodi, choose **Add-ons → Install from zip file** and select `repository.crb-0.1.4.zip`.
2. Open **Install from repository → CRB Add-on Repository → Video add-ons** and install **Crimson Blood Requiem**.
3. Install **CRB Setup Wizard** and **Crimson Blood Requiem Skin** from the same repository.
4. Launch the wizard and choose **Apply CRB space interface**.

## Fire TV and Android TV boxes

1. Copy `repository.crb.android-0.1.0.zip` to the device or a USB drive. Use Kodi's **Add-ons → Install from zip file** to install it.
2. Open **Install from repository → CRB Android Add-on Repository** and install **Crimson Blood Requiem**, **CRB Setup Wizard**, and **Crimson Blood Requiem Skin**.
3. Launch the wizard and choose **Apply CRB space interface**.
4. The first time you choose a torrent source, CRB downloads the matching Android torrent engine (about 61 MB) and verifies it. Allow that first setup to finish before retrying playback.

The Android package supports ARM64, ARMv7, x86_64 and x86 Kodi devices. Fire TV and most current Android boxes use ARM64. The engine is stored in Kodi's add-on data and reused on later plays. The device needs internet access for the first engine download. Some newer Android versions prevent Kodi from launching a downloaded native executable; CRB reports this clearly, but those devices need an Android companion service app for torrent playback. This package does not include that helper yet, and playback has not been tested on Fire TV hardware.

The packages are made for Kodi 21 or newer. Installing the repository does not replace Kodi; the optional wizard applies the CRB skin and can restore your previous interface later. Provider URLs and settings remain on the device.

Kodi must be allowed to install add-ons from zip files. This setup does not install a separate Android app or require sideloading an APK.
