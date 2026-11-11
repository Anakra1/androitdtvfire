# CBR Kodi Companion 0.2.0 for Fire TV and ARM Android TV

The APK includes pinned TorrServer MatriX.150 engines for ARMv7 and ARM64. The build downloads and verifies each binary; Android installs the selected binary into its native library directory. The service verifies it again before execution. No executable is downloaded into writable app data at runtime.

Kodi add-on 0.5.6 launches the companion through cbr://start when a torrent source is selected. The foreground service buffers the torrent and exposes a seekable HTTP stream on 127.0.0.1:8766 for Kodi's player. Stop controls remain in the app and its notification.

Build with Gradle 8.6, Android SDK 34 and JDK 17 or newer: gradle assembleDebug. The APK is app/build/outputs/apk/debug/app-debug.apk. Network access is required for the initial build to obtain the checksum-pinned native engines. The build retains the engines unchanged and packages them using legacy native-library extraction.

Sideload cbr.apk once. Version 0.2.0 has the same package and signing certificate as 0.1.0 so Android can update it in place. The Kodi repository cannot install Android APKs.

The APK has compiled and its contents, engine hashes, manifest and signature have been checked. Playback still needs verification on physical Fire TV hardware.