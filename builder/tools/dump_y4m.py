#!/usr/bin/env python3
"""Dump Intro.rsv frames as a YUV4MPEG2 (.y4m) stream (15 fps) for psxavenc.

Phase 5: the STR carries the intro music (XA) and plays in real time from LoadVideo, while the
intro script shows video frame 1 through its 3.6 s fade-in before advancing 1 frame / 4 game
frames (15 fps). So the stream starts with --hold copies of frame 1 (54 = 3.6 s) and ends with
the last frame repeated up to --min-seconds (the music is longer than the video).

Usage: dump_y4m.py [--rsv build/fmv-src/Intro.rsv] [--out /tmp/intro.y4m] [--hold 0] [--min-seconds 0]
"""
import argparse, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from convert_fmv import parse_rsv, rgb_to_ycbcr


def frame_bytes(palette, indices, ww, hh):
    idx = np.frombuffer(indices, dtype=np.uint8).reshape(hh, ww)
    rgb = np.zeros((hh, ww, 3), dtype=np.uint8)
    for c in range(3):
        lut = np.zeros(256, dtype=np.uint8)
        for k in range(0x80):
            lut[k] = palette[k * 3 + c]
        rgb[:, :, c] = lut[idx]
    ycbcr = rgb_to_ycbcr(rgb)
    return (ycbcr[:, :, 0].astype(np.uint8).tobytes() + ycbcr[0::2, 0::2, 1].astype(np.uint8).tobytes()
            + ycbcr[0::2, 0::2, 2].astype(np.uint8).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rsv', default=os.path.join(HERE, '..', 'build', 'fmv-src', 'Intro.rsv'))
    ap.add_argument('--out', default='/tmp/intro.y4m')
    ap.add_argument('--hold', type=int, default=0, help='extra copies of frame 1 at the start')
    ap.add_argument('--min-seconds', type=float, default=0, help='repeat the last frame up to this length')
    a = ap.parse_args()
    frames = parse_rsv(a.rsv)
    w, h = frames[0][2], frames[0][3]
    seq = [0] * a.hold + list(range(len(frames)))
    while len(seq) < a.min_seconds * 15:
        seq.append(len(frames) - 1)
    cache = {}
    with open(a.out, 'wb') as out:
        out.write(f"YUV4MPEG2 W{w} H{h} F15:1 Ip A1:1 C420jpeg\n".encode())
        for i in seq:
            if i not in cache:
                cache = {i: frame_bytes(*frames[i])}
            out.write(b"FRAME\n" + cache[i])
    print(f"wrote {a.out} ({len(seq)} frames = {len(seq) / 15:.2f} s: hold {a.hold} + {len(frames)} rsv frames + "
          f"{len(seq) - a.hold - len(frames)} tail, {w}x{h})")


if __name__ == "__main__":
    main()
