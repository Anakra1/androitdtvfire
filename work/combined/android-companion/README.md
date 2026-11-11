# CBR Kodi Companion for Android TV

CBR Kodi Companion runs the pinned TorrServer MatriX.150 Android binary in its own foreground service. Kodi's video add-on starts the companion through the `cbr://start` Android activity and connects to TorrServer at `http://127.0.0.1:8766`.

The app downloads the binary for the device ABI on first use, verifies the SHA-256 value shared with the Kodi add-on, and keeps it in the app's private storage. The server listens on loopback only and disables torrent uploads and peer discovery services. A notification remains visible while the engine runs; Kodi stops the service after its idle timeout, and users can stop it from the companion app or notification.

## Build

Open this directory in Android Studio or run `gradle assembleDebug`. The current build uses Android Gradle Plugin 8.4.1, compile SDK 34, min SDK 23 and target SDK 33. The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`.

## Install

This is a separate Android app. Kodi's repository can install the CBR add-on but cannot install this APK. Sideload the APK once on Fire TV/Android TV, then install the updated CBR add-on package. Torrent playback launches the companion automatically.

The project uses GPL-3.0 TorrServer MatriX.150. See the Kodi add-on's `resources/TorrServer-LICENSE.txt` and `resources/ENGINE-NOTICE.txt` for its license and notices.
