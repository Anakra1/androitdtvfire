# Android engine compatibility fix — CBR 0.12.3 / Playback Engine 0.1.2

The reported cached library SHA-256 matched the shipped ARM32 engine 0.1.1. That ELF contained only GNU_HASH; the device loader rejected it with empty/missing DT_HASH. Android's linker documentation specifies --hash-style=both for older-loader compatibility.

All three supported engine ABIs (ARMv7, ARM64, x86_64) are rebuilt with the existing Go 1.27.4 / NDK r30 toolchains, targeting API 21, --hash-style=both and --pack-dyn-relocs=none. Server sources match the checked-in MatriX.150 source archive; the C ABI entry point is included here. Build uses -buildvcs=false and -trimpath. ARM64 and x86_64 retain 16 KB load alignment. ARMv7 retains its 4 KB alignment.

Engine 0.1.2 includes new native checksums. Existing content-addressed library installation selects a new internal filename, so an old cached library cannot be mistaken for the corrected one. CBR Android 0.12.3 requires engine 0.1.2; full installer 0.4.3 bundles it for ARM32/ARM64. The repository engine ZIP also supports x86_64. The ARM-only full installer retains its existing under-100-MiB packaging layout. Windows remains video 0.12.2 / wizard 0.4.2 and the skin remains 0.2.1.

## Validation

verify_engine.py reproduces rejection of the exact old library, validates actual SysV hash-chain resolution of CBRStart/CBRStop in every rebuilt library, GNU hash presence, permitted relocation formats, ABI identity, page alignment, native hashes, addon dependencies, nested bundle hashes and public aliases. verify_arch.py exercises the actual packaged CPU selectors including armv8l. verify_full.py checks fresh ARM32/ARM64 installation, cancellation, rollback and settings preservation. No personal manifests or profile data are packaged.

runtime_probe.py checks native library load/start, actual loaded checksum, repeated /echo responses and process survival in the isolated Android x86_64 emulator. Runtime evidence is recorded separately under outputs/verified-live-engine012-runtime.json. Initial emulator runs were terminated by Android LOW_MEMORY; use 4 GB emulator RAM. Physical Fire TV execution and pre-23 runtime execution are not claimed; the older-loader contract is checked directly from the binary hash tables.

## Update

From the existing CBR Kodi file source, install engine.zip, wait for CBR Playback Engine 0.1.2, then fully quit/reopen Kodi. No Kodi reinstall or companion application is required. Alternatively update the CBR video addon to Android 0.12.3; Kodi installs its required engine automatically. Full new installations use fulla043.zip. Existing manifests, quality filters, progress and skin settings are retained.

Primary technical reference: https://android.googlesource.com/platform/bionic/+/master/android-changes-for-ndk-developers.md#gnu-hashes-available-in-api-level-23
