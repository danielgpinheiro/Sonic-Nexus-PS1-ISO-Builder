# SonicNexus-PS1.exe

The PlayStation executable (PS-X EXE, 208896 bytes) that `build_iso.py` puts on the disc as
`NEXUS.EXE`: Retro Engine v2 (RSDKv2 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv2-ps1 port at commit `544f817` (2026-10-18; the main stack on its own 16 KB area, out of the
  heap; psyqo from nugget `4b125c1b`), natural boot, retail 2 MB RAM.
- SHA-256 `147a83d18e21a52206d8e1227973d238e10c20df5411bdfc9ac7592d5559caed` (also in `SHA256SUMS`).
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must
  match this executable's formats, so use the builder from the same release.
- Real-hardware fixes, found by testing the Sonic CD port on a PSone (SCPH-101):
  - The CPU drives the MDEC for the intro video, because the MDEC's output DMA failed on that console.
  - It guards against CD and DMA interrupts lost by psyqo's interrupt acknowledge.
  - The loading icon no longer aborts the boot when a slow CD read delays its timer.
