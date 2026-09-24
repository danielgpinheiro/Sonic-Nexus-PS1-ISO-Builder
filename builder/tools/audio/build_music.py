#!/usr/bin/env python3
"""Build-time CD-XA music for the PS1 (phase 5): Data/Music/**/*.ogg -> Data/Music/Music.xa + Music.bin.

Each track (Ogg Vorbis, XOR 0xFF on disc) becomes one XA-ADPCM channel: psxavenc -t xa, 37.8 kHz
stereo 4-bit (18.75 sectors/s). At 2x CD speed (150 sectors/s) one channel takes 1 sector in 8,
so up to 8 tracks share one file: physical sector i*8 + k carries sector i of channel k. The drive
decodes only the channel selected with Setfilter (file 1, channel k) and plays it through the SPU.

Per channel, after its last audio sector comes one Form-1 **data** sector (file 1, channel k,
payload b'RSDKXAEND' + k): data sectors reach the CPU (INT1) even in XA mode, which is how
ps1/xa_music.cpp detects the end of a track (loop -> Setloc again, else Pause). Slots after that
are silent XA audio on channel 31 (never selected, filtered out by the drive). psxavenc's EOF
submode bits are cleared (the end is marked by our data sector).

Intro.ogg is not in Music.xa: it plays under the FMV, interleaved in Intro.str (tools/fmv/build_str.py).
Its Music.bin entry has channel 0xFF = "in the video stream": PlayMusic sets the music state and
volume (fades) while the STR's XA sectors play.

Output: Data/Music/Music.xa (2336-byte sectors, mkpsxiso type="mixed") and Data/Music/Music.bin:
  'XAM1', u16 count, u16 interleave (8), u32 file sectors;
  count x { char[48] path relative to Data/Music (as in SetMusicTrack), u8 channel, u8 0, u16 0,
            u32 audio sectors }
Usage: build_music.py DATA_DIR [--exclude Nexus/Intro.ogg]
"""
import os, struct, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xa_adpcm  # noqa: E402

PSXAVENC = os.environ.get('PSXAVENC') or os.path.join(os.path.dirname(__file__), '../../../psxavenc/build/psxavenc')
SECTOR = 2336
INTERLEAVE = 8
FILE_NO = 1
FILLER_CHANNEL = 31


def subheader(channel, submode, coding):
    return bytes([FILE_NO, channel, submode, coding] * 2)


def end_sector(channel):
    payload = (b'RSDKXAEND' + bytes([channel])).ljust(2048, b'\0')
    return (subheader(channel, 0x08, 0) + payload).ljust(SECTOR, b'\0')  # Form 1 data; EDC/ECC by mkpsxiso


def filler_sector(coding):
    return (subheader(FILLER_CHANNEL, 0x64, coding)).ljust(SECTOR, b'\0')  # silent XA audio


def main():
    data = sys.argv[1]
    exclude = {'nexus/intro.ogg'}
    if '--exclude' in sys.argv:
        exclude = {x.lower() for x in sys.argv[sys.argv.index('--exclude') + 1].split(',')}
    root = os.path.join(data, 'Music')
    tracks = []
    for dp, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith('.ogg'):
                rel = os.path.relpath(os.path.join(dp, f), root).replace(os.sep, '/')
                if rel.lower() not in exclude:
                    tracks.append(rel)
    tracks.sort()
    if len(tracks) > INTERLEAVE:
        sys.exit('ERROR: %d tracks > %d channels in one file' % (len(tracks), INTERLEAVE))
    chans = []
    with tempfile.TemporaryDirectory() as tmp:
        for k, rel in enumerate(tracks):
            d = open(os.path.join(root, rel), 'rb').read()
            if d[:4] != b'OggS':
                d = bytes(b ^ 0xFF for b in d)
            src, out = os.path.join(tmp, 'in.ogg'), os.path.join(tmp, 'out.xa')
            open(src, 'wb').write(d)
            subprocess.run([PSXAVENC, '-q', '-t', 'xa', '-f', '37800', '-c', '2', '-b', '4', '-F', str(FILE_NO), '-C', str(k), src, out],
                           check=True)
            x = open(out, 'rb').read()
            assert len(x) % SECTOR == 0, rel
            secs = [bytearray(x[i:i + SECTOR]) for i in range(0, len(x), SECTOR)]
            for s in secs:
                assert s[0] == FILE_NO and s[1] == k and s[2] & 0x04, (rel, s[:8].hex())
                s[2] &= 0x7F  # clear EOF
                s[6] &= 0x7F
            chans.append(secs)
    coding = chans[0][0][3]
    rows = max(len(c) for c in chans) + 1  # + the end-marker row
    out = bytearray()
    for i in range(rows):
        for k in range(INTERLEAVE):
            if k < len(chans) and i < len(chans[k]):
                out += chans[k][i]
            elif k < len(chans) and i == len(chans[k]):
                out += end_sector(k)
            else:
                out += filler_sector(coding)
    open(os.path.join(root, 'Music.xa'), 'wb').write(xa_adpcm.clear_unused(out))  # reproducible build
    video_tracks = sorted(exclude)
    table = struct.pack('<4sHHI', b'XAM1', len(tracks) + len(video_tracks), INTERLEAVE, len(out) // SECTOR)
    for k, rel in enumerate(tracks):
        table += struct.pack('<48sBBHI', rel.encode(), k, 0, 0, len(chans[k]))
    for rel in video_tracks:  # played by the STR stream (channel 0xFF)
        match = [os.path.relpath(os.path.join(dp, f), root).replace(os.sep, '/') for dp, _, fs in os.walk(root) for f in fs
                 if os.path.relpath(os.path.join(dp, f), root).replace(os.sep, '/').lower() == rel]
        table += struct.pack('<48sBBHI', (match[0] if match else rel).encode(), 0xFF, 0, 0, 0)
    open(os.path.join(root, 'Music.bin'), 'wb').write(table)
    for k, rel in enumerate(tracks):
        print('ch%d %-28s %5d sectors %6.2f s' % (k, rel, len(chans[k]), len(chans[k]) / 18.75))
    print('Music.xa: %d sectors (%.1f MB on disc), %d tracks, interleave %d, 37.8 kHz stereo 4-bit' % (
        len(out) // SECTOR, len(out) / SECTOR * 2352 / 1048576, len(tracks), INTERLEAVE))


if __name__ == '__main__':
    main()
