# SonicNexus-PS1.exe

The PlayStation executable (PS-X EXE, 204800 bytes) that `build_iso.py` puts on the disc as
`PSX.EXE`: Retro Engine v2 (RSDKv2 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv2-ps1 port at commit `deb1c42` (2026-09-24), natural boot, retail 2 MB RAM.
- SHA-256 `cc04e24acfc1d828f8b1afa1bdeba101aa84c37450b6851e4f8ff2032f21c6e2` (also in `SHA256SUMS`).
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must
  match this executable's formats, so use the builder from the same release.
