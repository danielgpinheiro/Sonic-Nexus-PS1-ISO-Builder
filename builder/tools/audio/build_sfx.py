#!/usr/bin/env python3
"""Build-time SFX conversion for the PS1 (phase 5): Data/SoundFX/**/*.wav -> *.vag.

The engine loads sound effects by name (GameConfig.bin: global list; StageConfig.bin: per stage)
and the PS1 LoadSfx maps `X.wav` to `X.vag` (SPU-ADPCM, psxavenc `-t vag`: 48-byte header, data
padded to 64 bytes, ends with a silent loop-trap block). The .wav files in the loose tree are XOR
0xFF encoded (Data.bin heritage); they are decoded here.

Sample rate: the highest of 44100 / 32000 / 22050 Hz at which the global set plus the largest
stage set fits the SPU RAM left for samples (0x1000 .. 0x80000 - 32: capture buffers below,
dummy block above). Nexus sources are 44.1 kHz mono 8-bit.

Usage: build_sfx.py DATA_DIR   (e.g. build/iso/Data; needs psxavenc + ffmpeg)
"""
import os, struct, subprocess, sys, tempfile

PSXAVENC = os.environ.get('PSXAVENC') or os.path.join(os.path.dirname(__file__), '../../../psxavenc/build/psxavenc')
SPU_SAMPLE_START = 0x1000
SPU_SAMPLE_END = 0x80000 - 32
RATES = (44100, 32000, 22050)


def read_str(d, i):
    n = d[i]
    return d[i + 1:i + 1 + n].decode('latin1'), i + 1 + n


def global_sfx(data):
    d = open(os.path.join(data, 'Game', 'GameConfig.bin'), 'rb').read()
    i = 0
    for _ in range(3):
        _, i = read_str(d, i)
    n = d[i]; i += 1
    for _ in range(n):
        _, i = read_str(d, i)
    n = d[i]; i += 1
    for _ in range(n):
        _, i = read_str(d, i)
        i += 4
    n = d[i]; i += 1
    names = []
    for _ in range(n):
        s, i = read_str(d, i)
        names.append(s)
    return names


def stage_sfx(path):
    d = open(path, 'rb').read()
    i = 1 + 32 * 3
    n = d[i]; i += 1
    for _ in range(n):
        _, i = read_str(d, i)
    n = d[i]; i += 1
    names = []
    for _ in range(n):
        s, i = read_str(d, i)
        names.append(s)
    return names


def wav_bytes(path):
    d = open(path, 'rb').read()
    return d if d[:4] == b'RIFF' else bytes(b ^ 0xFF for b in d)


def wav_frames(d):
    # minimal RIFF walk: frames = data bytes / block align
    i, align, size = 12, 1, 0
    while i + 8 <= len(d):
        cid, cs = d[i:i + 4], struct.unpack_from('<I', d, i + 4)[0]
        if cid == b'fmt ':
            align = struct.unpack_from('<H', d, i + 20)[0]
        elif cid == b'data':
            size = cs
        i += 8 + cs + (cs & 1)
    return size // align


def vag_size(frames, src_rate, rate):
    samples = -(-frames * rate // src_rate)
    blocks = -(-samples // 28) + 2  # + leading dummy block + trailing loop-trap block
    return -(-blocks * 16 // 64) * 64


def main():
    data = sys.argv[1]
    sfx_root = os.path.join(data, 'SoundFX')
    groups = {'global': global_sfx(data)}
    for st in sorted(os.listdir(os.path.join(data, 'Stages'))):
        p = os.path.join(data, 'Stages', st, 'StageConfig.bin')
        if os.path.exists(p):
            groups[st] = stage_sfx(p)
    frames = {}
    for names in groups.values():
        for n in names:
            if n not in frames:
                frames[n] = wav_frames(wav_bytes(os.path.join(sfx_root, n)))
    budget = SPU_SAMPLE_END - SPU_SAMPLE_START
    rate = None
    for r in RATES:
        g = sum(vag_size(frames[n], 44100, r) for n in groups['global'])
        worst = max(sum(vag_size(frames[n], 44100, r) for n in names) for k, names in groups.items() if k != 'global')
        if g + worst <= budget:
            rate = r
            break
    if rate is None:
        sys.exit('ERROR: SFX do not fit SPU RAM even at %d Hz' % RATES[-1])
    total = {}
    with tempfile.TemporaryDirectory() as tmp:
        for n in sorted(frames):
            src = os.path.join(sfx_root, n)
            wav = os.path.join(tmp, 'in.wav')
            open(wav, 'wb').write(wav_bytes(src))
            out = os.path.splitext(src)[0] + '.vag'
            subprocess.run([PSXAVENC, '-q', '-t', 'vag', '-f', str(rate), wav, out], check=True)
            v = open(out, 'rb').read()
            assert v[:4] == b'VAGp', out
            size = struct.unpack_from('>I', v, 12)[0]
            assert len(v) - 48 >= size and (len(v) - 48) % 64 == 0, out
            total[n] = len(v) - 48
    for k, names in groups.items():
        print('%-7s %2d sfx  %7d B SPU RAM' % (k, len(names), sum(total[n] for n in names)))
    worst = max(sum(total[n] for n in names) for k, names in groups.items() if k != 'global')
    print('rate %d Hz | global + largest stage %d of %d B' % (rate, sum(total[n] for n in groups['global']) + worst, budget))


if __name__ == '__main__':
    main()
