# SonicNexus-PS1.exe

The PlayStation executable (PS-X EXE, 208896 bytes) that `build_iso.py` puts on the disc as
`PSX.EXE`: Retro Engine v2 (RSDKv2 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv2-ps1 port at commit `6feee50` (2026-09-25), natural boot, retail 2 MB RAM.
- SHA-256 `fbcdd7ac548ac7e4f10c1d10d253861e1ef13477439f80f75b5c7cff6601e2ce` (also in `SHA256SUMS`).
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must
  match this executable's formats, so use the builder from the same release.
- Real-hardware fixes, found by testing the Sonic CD port on a PSone (SCPH-101):
  - The CPU drives the MDEC for the intro video, because the MDEC's output DMA failed on that console.
  - It guards against CD and DMA interrupts lost by psyqo's interrupt acknowledge.
  - The loading icon no longer aborts the boot when a slow CD read delays its timer.
