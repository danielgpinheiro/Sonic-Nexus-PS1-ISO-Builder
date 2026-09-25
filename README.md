# Sonic Nexus PS1 ISO Builder

Build a PlayStation 1 disc image of **Sonic Nexus** (the 2008 fan game running on the Retro
Engine v2) from your own copy of the game. The PS1 executable is prebuilt; this repository
contains the tools that convert the game's data for the PlayStation and put the disc together.

**No game data is included.** You download Sonic Nexus yourself (free, see [Usage](#usage)).

## What does this do / why is it needed?

The PlayStation has 2 MB of RAM, 1 MB of video RAM, no floating point and a 2× CD-ROM drive.
The PC version of Sonic Nexus decodes GIFs, Ogg music and scripts while it runs; the PS1 can't
afford that. So everything is converted **once, on your computer**, into formats the PS1
hardware uses directly:

- **Sprites** → one texture atlas per stage (4/8-bit VRAM pages + palettes), checked pixel-exact.
- **Tiles and parallax backgrounds** → pre-packed VRAM pages and pre-rendered background line strips.
- **Scripts** → precompiled bytecode (RetroScript compiler built from the decompilation).
- **Sound effects** → SPU-ADPCM samples.
- **Music** → CD-XA audio, streamed and decoded by the CD drive itself.
- **Intro video** → MDEC video (STR) with interleaved XA audio.
- **Disc layout** → files placed in the order the game loads them, source files left off.

## Usage

1. Download **Sonic Nexus (2008)**: <https://info.sonicretro.org/Sonic_Nexus>. Unpack it: you need
   the `Data.bin` next to `Nexus.exe` (unmodified; the builder checks its SHA-256).
2. Install the [requirements](#requirements).
3. Run:
   ```bash
   python3 build_iso.py --data /path/to/Sonic\ Nexus/Data.bin
   ```
   Optional: `--license licensea.dat` (see [The license file](#the-license-file)),
   `--out folder`, `--keep-work`.
4. The disc image is in `output/` after about 20 seconds.

## Output

- `output/SonicNexus-PS1.cue` + `output/SonicNexus-PS1.bin`: a Mode 2 BIN/CUE image (47 MB).
  It has to be BIN/CUE, not `.iso`: CD-XA music and video use 2336-byte Mode 2 sectors, which a
  2048-byte ISO image can't hold.
- `output/SHA256SUMS`.

The build is reproducible: built from the original `Data.bin` **without** a license file, the image
is byte-identical for everyone —
`SonicNexus-PS1.bin` SHA-256 `25e33f8053ef15f2513254c865a492a628e7f9484b81e531e624df9222e3e3d4`.
(With a license file the license sectors differ, so the hash does too.)

Before writing it, the builder verifies the image byte by byte: sector headers, EDC/ECC of every
sector, the license sectors, and every file against its source.

## What the PS1 version can do

- The whole game: Retro Engine logo, intro video with music, title screen, Sunset Shore Zone.
- 60 fps gameplay with the PC version's tile-layer parallax, sprite rotation/scaling, fades and
  colour effects.
- CD-XA music, sound effects, the intro video with its soundtrack.
- An animated loading icon while the game reads from the disc.
- Loads of a few seconds (the CD is read ahead in 64 KB windows, files placed in load order).

## What the PS1 version can't do

- No saving: Sonic Nexus itself has nothing to save (no memory card use).
- No dev menu / settings file / mods from the PC version.
- Tested in emulators only (PCSX-Redux; DuckStation with a retail PSone BIOS), not yet on a real
  console. The executable carries the real-hardware fixes found by testing the Sonic CD port on a PSone.

## Compromises to make this work

- Music and the intro soundtrack are 4-bit CD-XA ADPCM at 37.8 kHz (the PS1's streaming format).
- Sound effects are SPU-ADPCM, sized to fit the 512 KB of sound RAM.
- The intro video is 256×160 MDEC at 15 fps.
- A few blend effects over coloured backgrounds are approximations (the PS1 GPU has 4 fixed
  blend modes).
- The first load of each stage takes a few seconds; a loading icon shows while it runs.

## Requirements

Tested on macOS (Apple Silicon) with Python 3.9, Pillow 11, NumPy 2.0, FFmpeg 9, psxavenc
(git, 2026-09), mkpsxiso 2.30 and clang 22. Linux works the same way; on Windows, use WSL.

| Tool | What for |
|---|---|
| Python 3.9+ with Pillow and NumPy (`pip install -r requirements.txt`) | the converters |
| a C++17 compiler (clang++ or g++) | builds the RetroScript compiler from source |
| FFmpeg (`ffmpeg`, `ffprobe`) | decodes the game's Ogg audio and video frames |
| [psxavenc](https://codeberg.org/WonderfulToolchain/psxavenc) | encodes SPU-ADPCM, CD-XA and STR video |
| [mkpsxiso](https://github.com/Lameguy64/mkpsxiso) | writes the disc image |

The builder finds the tools on your `PATH`, or through the environment variables `PSXAVENC`,
`MKPSXISO`, `FFMPEG`, `FFPROBE` and `CXX`. It stops with a list if anything is missing.

**macOS** (Homebrew):
```bash
xcode-select --install                      # clang++
brew install python ffmpeg meson ninja pkg-config
python3 -m pip install -r requirements.txt
git clone https://codeberg.org/WonderfulToolchain/psxavenc && cd psxavenc
meson setup build && meson compile -C build && cd ..   # then PSXAVENC=$PWD/psxavenc/build/psxavenc
# mkpsxiso: download a release from https://github.com/Lameguy64/mkpsxiso/releases
#           (or build it with CMake) and put `mkpsxiso` on your PATH or in MKPSXISO
```

**Linux** (Debian/Ubuntu):
```bash
sudo apt install python3-pip build-essential ffmpeg meson ninja-build pkg-config \
     libavformat-dev libavcodec-dev libavutil-dev libswresample-dev libswscale-dev cmake
python3 -m pip install -r requirements.txt
# psxavenc and mkpsxiso: as above (meson for psxavenc, CMake or a release for mkpsxiso)
```

## The license file

PlayStation discs carry Sony's license data, which retail consoles check at boot. It can't be
distributed, so by default the image is built **without** it: it plays in emulators (PCSX-Redux,
DuckStation, …), on optical drive emulators and on modded consoles. If you have `licensea.dat`
(NTSC-U) from the official SDK, pass `--license licensea.dat` to make a disc that also boots on
retail NTSC-U consoles.

## Playing it

- **Emulator:** open `SonicNexus-PS1.cue` in PCSX-Redux or DuckStation.
- **Real hardware:** burn the BIN/CUE at the slowest speed on a CD-R, or copy it to an optical
  drive emulator. Not yet tested on a console — reports are welcome.

## How it's made

The executable in `bin/` is built from a PS1 port of the
[RSDKv2 decompilation](https://github.com/RSDKModding/RSDKv2-Decompilation) using
[psyqo](https://github.com/pcsx-redux/nugget/tree/main/psyqo), developed and tested with
[PCSX-Redux](https://github.com/grumpycoders/pcsx-redux). See `bin/README.md` for its version.
`builder/` holds the conversion tools, each documented in its header.

## License & credits

- **Retro Engine (RSDK)**: Christian "Taxman" Whitehead.
- **RSDKv2 decompilation**: Rubberduckycooly and RMGRich
  ([RSDKModding](https://github.com/RSDKModding/RSDKv2-Decompilation)).
- **Sonic Nexus** (2008): the Sonic Nexus team —
  [Sonic Retro](https://info.sonicretro.org/Sonic_Nexus).
- **psyqo / nugget / PCSX-Redux**: the PCSX-Redux authors. **EASTL / EABase**: Electronic Arts.
- **[ps1-bare-metal](https://github.com/spicyjpeg/ps1-bare-metal)** (sound and CD-ROM driver
  model): spicyjpeg.
- **psxpress** video decoder: [PSn00bSDK](https://github.com/Lameguy64/PSn00bSDK) contributors.
- **[mkpsxiso](https://github.com/Lameguy64/mkpsxiso)**: Lameguy64 and contributors.
  **[psxavenc](https://codeberg.org/WonderfulToolchain/psxavenc)**: Ben "GreaseMonkey" Russell and
  Adrian "asie" Siekierka.
- **[psx-spx](https://psx-spx.consoledev.net/)** hardware documentation: Martin "nocash" Korth
  and contributors.
- **Loading icon**: "Sonic-Spinning" GIF by
  [SoniczheFan87686](https://tenor.com/en-GB/users/soniczhefan87686).

Licensed under the RSDKv2 decompilation license ([LICENSE.md](LICENSE.md)). **Not for commercial
use. No game assets are distributed** — you build the disc from your own download of the game.
Third-party licenses and the MPL-covered source are in [licenses/](licenses/README.md) and
[sources/](sources/psxpress/README.md). Sonic the Hedgehog is a trademark of SEGA; this project is
not affiliated with or endorsed by SEGA or Sony.
