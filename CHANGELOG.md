# Changelog

Updates to the Sonic Nexus PS1 ISO Builder, newest first. To get an update, rebuild your disc image with the new
version of the builder (same steps as in the [README](README.md)).

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
