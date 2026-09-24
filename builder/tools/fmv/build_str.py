#!/usr/bin/env python3
"""Build Intro.str with the intro music interleaved as XA audio (phase 5 step 4).

PC plays Intro.ogg (PlayMusic) and starts the video (LoadVideo) on the same frame, shows video
frame 1 through a 3.6 s fade-in, then advances 1 frame per 4 game frames (15 fps). The PS1 STR
streams in real time from LoadVideo with the music in it, so the video starts with frame 1 held
for the fade-in (54 frames) minus the PS1 player's ~4-frame pipeline latency: STR frame k = .rsv
frame max(1, k - 50) at stream time (k - 1) / 15 s, which puts it on screen when PC shows it. The
last frame is repeated until the music ends (the music is longer than the video).

Steps: tools/dump_y4m.py (hold + tail) -> ffmpeg mux with the XOR-decoded Ogg -> psxavenc -t str
(v2, 256x160, 15 fps, 2x, XA 37.8 kHz stereo 4-bit, file 1 channel 0) -> Intro.str (2336-byte
sectors, mkpsxiso type="mixed") + Intro.sti sidecar for ps1/video.cpp:
  'STRI', u32 frames, u32 video (data) sectors, u8 xa file, u8 xa channel, u8 1 (audio), u8 0.

Usage: build_str.py [DATA_DIR] [INTRO_RSV]   (defaults: build/iso/Data, build/fmv-src/Intro.rsv)
Tools: PSXAVENC, FFMPEG, FFPROBE environment variables override the default locations.
"""
import os, struct, subprocess, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'audio'))
import xa_adpcm  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
PSXAVENC = os.environ.get('PSXAVENC') or os.path.join(REPO, '..', 'psxavenc', 'build', 'psxavenc')
FFMPEG = os.environ.get('FFMPEG') or 'ffmpeg'
FFPROBE = os.environ.get('FFPROBE') or 'ffprobe'
FADE_FRAMES = 54      # the intro script's fade-in: (432 / 2) frames at 60 fps = 3.6 s at 15 fps
PLAYER_LATENCY = 2    # PS1 player (stream-driven in XA mode): decode + upload + chain delay, in STR
                      # frames. Measured with 0: the shown frame trailed PC by 1.1-2.6 frames (2 runs)
HOLD_FRAMES = FADE_FRAMES - PLAYER_LATENCY
XA_FILE, XA_CHANNEL = 1, 0


def main():
    data = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'build', 'iso', 'Data'))
    rsv = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO, 'build', 'fmv-src', 'Intro.rsv'))
    ogg = os.path.join(data, 'Music', 'Nexus', 'Intro.ogg')
    out_dir = os.path.join(data, 'Sprites', 'Videos')
    with tempfile.TemporaryDirectory() as tmp:
        d = open(ogg, 'rb').read()
        audio = os.path.join(tmp, 'intro.ogg')
        open(audio, 'wb').write(d if d[:4] == b'OggS' else bytes(b ^ 0xFF for b in d))
        dur = float(subprocess.run([FFPROBE, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', audio],
                                   capture_output=True, text=True, check=True).stdout)
        y4m, nut, st = os.path.join(tmp, 'intro.y4m'), os.path.join(tmp, 'intro.nut'), os.path.join(out_dir, 'Intro.str')
        subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'dump_y4m.py'), '--rsv', rsv, '--out', y4m,
                        '--hold', str(HOLD_FRAMES), '--min-seconds', '%.2f' % (dur + 0.2)], check=True)
        subprocess.run([FFMPEG, '-loglevel', 'error', '-y', '-i', y4m, '-i', audio, '-map', '0:v', '-map', '1:a',
                        '-c:v', 'rawvideo', '-c:a', 'pcm_s16le', nut], check=True)
        subprocess.run([PSXAVENC, '-q', '-t', 'str', '-v', 'v2', '-f', '37800', '-b', '4', '-c', '2', '-F', str(XA_FILE),
                        '-C', str(XA_CHANNEL), '-s', '256x160', '-r', '15', '-x', '2', nut, st], check=True)
    s = bytes(xa_adpcm.clear_unused(open(st, 'rb').read()))  # psxavenc's padding is uninitialised
    open(st, 'wb').write(s)
    S = 2336
    assert len(s) % S == 0
    n = len(s) // S
    video = audio_n = 0
    frames = set()
    for i in range(n):
        if s[i * S + 2] & 0x04:
            audio_n += 1
            assert s[i * S] == XA_FILE and s[i * S + 1] == XA_CHANNEL and i % 8 == 0, 'audio sector %d' % i
        else:
            video += 1
            magic, _, _, _, fr = struct.unpack_from('<HHHHI', s, i * S + 8)
            assert magic == 0x0160, 'video sector %d' % i
            frames.add(fr)
    assert frames == set(range(1, len(frames) + 1))
    open(os.path.join(out_dir, 'Intro.sti'), 'wb').write(struct.pack('<4sIIBBBB', b'STRI', len(frames), video, XA_FILE, XA_CHANNEL, 1, 0))
    print('Intro.str: %d sectors (%d video, %d XA audio = 1 in 8), %d frames (%.2f s; hold %d), music %.2f s' % (
        n, video, audio_n, len(frames), len(frames) / 15, HOLD_FRAMES, dur))


if __name__ == '__main__':
    main()
