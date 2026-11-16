# CBR 0.11.2 / Playback Engine 0.1.1 / Wizard 0.3.2

The Fire TV screenshot reports `This Android device architecture (armv8l) is not supported`. The video engine gate and shared-library dependency both omitted this ARM alias; the full installer already recognised it. Accept armv8l in both runtime layers and choose the native ABI using Kodi Python pointer size, so 32-bit Kodi on ARMv8 hardware loads the ARM32 library.

Build from frozen video 0.11.1, wizard 0.3.1 and engine 0.1.0. Preserve all native library bytes/checksums, channel lists, manifests, PVR clients, skin and Pluto fix. Android video requires engine 0.1.1. The full installer embeds both updated components and keeps its ARM-only engine payload to remain below GitHub's file limit. Windows engine native payload is unchanged.

Validation: actual packaged architecture selection for armv8l and existing ARM aliases in both 32/64-bit processes; unknown architectures rejected; original native libraries and checksums retained. Feed/package validation, fresh bundled ARM32/ARM64 installation and maintenance/Pluto regression checks. No physical Fire TV playback claim: Stuart must update and retest the device. This fix addresses the reported rejection before native loading; it is not a guarantee of all subsequent playback behavior.
