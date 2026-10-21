# Changelog

Updates to the Sonic Nexus PS1 ISO Builder, newest first. To get an update, rebuild your disc image with the new
version of the builder (same steps as in the [README](README.md)).

## Loading icon protection (October 2026)

- **The loading icon now waits while a level load is copying graphics into video memory.** Two copies at the same
  time stop the game; in the Sonic 1 port this froze the end credits on a black screen in the PCSX-ReARMed emulator.
  It never happened in Sonic Nexus, but Nexus had the same weak spot, so it gets the same fix. Nothing else changes.
- The title screen shows the new build, `v fb5acab4` (the RSDKv2-ps1 port's commit `fb5acab`).
- Checked with the port's automated tests in PCSX-Redux and DuckStation. The image's SHA-256 changes (the new value is
  in the README's Output section).

## Flip-bit tiles and sprites on newer consoles, Sonic facing left at his size (October 2026)

- **On consoles with the newer GPU (every PSone, most later PlayStations), mirrored level tiles and mirrored sprites
  are now drawn with the GPU's own flip feature** instead of as textured four-corner shapes, which costs the GPU less.
  The game checks the GPU at start-up (nocash's GPU detection, then a tiny test drawing read back from video memory):
  on the earliest consoles, whose GPU lacks the feature, and on emulators that don't draw it, everything is drawn as
  before. The picture is the same either way (checked frame by frame in the DuckStation preview build, which draws
  the feature, against the old way of drawing). Not yet tested on a console.
- **Sonic facing left on flat ground is drawn at his real size:** he was drawn 4 pixels wider than facing right, and
  his frame started one column too far (a texel from beyond the frame). He is now the exact mirror of facing right, as
  on the PC version; mirrored sprites drawn at their own size are exact too.
- The title screen shows the new build, `v 9d773415` (the RSDKv2-ps1 port's commit `9d77341`).
- Checked with the port's automated tests in PCSX-Redux and DuckStation. The image's SHA-256 changes (the new value is
  in the README's Output section).

## Build stamp on the title screen (October 2026)

- **The title screen shows which build you are playing:** a small grey line in its bottom-left corner, e.g.
  `v f6503e87`. It is the commit of the RSDKv2-ps1 port the executable was built from, so a screenshot or a quick look
  tells which version runs in DuckStation, PCSX-Redux or on a console. It appears only on the title screen and fades
  in with it.
- The builder writes it to a small `VERSION.TXT` file at the root of the disc (from `bin/VERSION.TXT`, which comes
  with each update together with the executable). A disc without that file shows `v unknown`.
- Checked with the port's automated tests in PCSX-Redux and DuckStation, and the builder's disc boots through the
  BIOS with the stamp on the title. Not yet tested on a console.
- The image's SHA-256 changes (the new value is in the README's Output section).

## Memory safety fix: the stack has its own area (October 2026)

- **The main stack moved out of the heap** (port issue NX-070): the processor's working data (the stack) now lives in
  a separate, fixed 16 KB area. Before, nothing kept it apart from the memory the game loads into, so with little
  memory left a load could be placed on the stack and corrupt it. No such crash was seen in normal play (the game keeps
  more than 250 KB free), but the port's tests produced one with memory held back on purpose.
- When memory runs out, a request for more now fails cleanly instead of being handed the stack's memory.
- This uses 16 KB of the console's 2 MB RAM; the deepest the stack was measured to reach is under 3 KB.
- Checked with the port's automated tests in PCSX-Redux and DuckStation. Not yet tested on a console.
- The image's SHA-256 changes (the new value is in the README's Output section).

## The disc's executable is named after the game (October 2026)

- The disc now boots **`NEXUS.EXE`** instead of `PSX.EXE` (the `BOOT` line of `SYSTEM.CNF`).
  Emulators and optical drive emulators that show a disc's executable name now show the game's. Nothing in the
  game itself changes.
- The image's SHA-256 changes with it (the new value is in the README's Output section).

## The BIOS screen no longer stays behind the first frames (October 2026)

- The executable clears the video RAM at boot (psyqo from upstream nugget `05b9bc30`): the PlayStation logo screen no
  longer shows behind the game's first frames.

## Real-hardware fixes (September 2026)

- Fixes found testing the Sonic CD port on a PSone, carried over to Sonic Nexus (CD reading, video and interrupt
  handling on real consoles).

## First release (September 2026)

- The prebuilt PS1 executable and the tools that convert the game's data and build the disc.
