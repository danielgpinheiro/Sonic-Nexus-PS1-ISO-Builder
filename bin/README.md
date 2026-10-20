# SonicNexus-PS1.exe

The PlayStation executable (PS-X EXE, 212992 bytes) that `build_iso.py` puts on the disc as
`NEXUS.EXE`: Retro Engine v2 (RSDKv2 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv2-ps1 port at commit `9d77341` (2026-10-19; GPU type detection + flip-bit rectangles; psyqo from nugget
  `4b125c1b`), natural boot, retail 2 MB RAM.
- SHA-256 `3e225bd0602b72f5956ec5a3577949a19ccf5f9e4f15c654df511fced917eed8` (also in `SHA256SUMS`).
- `VERSION.TXT` (`9d773415`) goes on the disc; the title screen shows it bottom-left.
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must
  match this executable's formats, so use the builder from the same release.
- Real-hardware fixes, found by testing the Sonic CD port on a PSone (SCPH-101):
  - The CPU drives the MDEC for the intro video, because the MDEC's output DMA failed on that console.
  - It guards against CD and DMA interrupts lost by psyqo's interrupt acknowledge.
  - The loading icon no longer aborts the boot when a slow CD read delays its timer.
