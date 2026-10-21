# SonicNexus-PS1.exe

The PlayStation executable (PS-X EXE, 212992 bytes) that `build_iso.py` puts on the disc as
`NEXUS.EXE`: Retro Engine v2 (RSDKv2 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv2-ps1 port at commit `fb5acab` (2026-10-21; the loading icon waits for a level load's own video
  memory upload; psyqo from nugget `4b125c1b`), natural boot, retail 2 MB RAM.
- SHA-256 `1e537ddc0b89379d416209cd273ee7d1ba001c7c6b4f9c79f5809b837e688b2c` (also in `SHA256SUMS`).
- `VERSION.TXT` (`fb5acab4`) goes on the disc; the title screen shows it bottom-left.
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must
  match this executable's formats, so use the builder from the same release.
- Real-hardware fixes, found by testing the Sonic CD port on a PSone (SCPH-101):
  - The CPU drives the MDEC for the intro video, because the MDEC's output DMA failed on that console.
  - It guards against CD and DMA interrupts lost by psyqo's interrupt acknowledge.
  - The loading icon no longer aborts the boot when a slow CD read delays its timer.
  - The loading icon waits while a level load is copying graphics to video memory (a second copy at the same time
    stops the game; it froze Sonic 1's credits in PCSX-ReARMed).
