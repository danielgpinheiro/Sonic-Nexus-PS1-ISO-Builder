#!/usr/bin/env python3
"""Stage 2: decode Intro.rsv (GIF-sequence video) -> raw MDEC RLE bitstream.

Golden rule: no runtime decode. This runs at BUILD time and emits the MDEC's
raw run-length bitstream (the same format encode_image.py produces), which the
MDEC hardware feeds directly -- zero CPU decode on the PS1.

Usage:
  python3 convert_fmv.py --input build/fmv-src/Intro.rsv [--limit N] [--out out.bin]
"""
import struct
import sys
import numpy as np

# ---------------------------------------------------------------------------
# GIF LZW decode (the RSDKv2 Sprite.cpp ReadGifCode/ReadGifLine algorithm)
# ---------------------------------------------------------------------------
def gif_lzw_decode(blocks, code_size, width, height):
    clear_code = 1 << code_size
    eof_code = clear_code + 1
    running_code = eof_code + 1
    running_bits = code_size + 1
    max_code = 1 << running_bits

    prefix = [0] * 4096
    suffix = [0] * 4096   # the appended (last) pixel of each code's string
    valid = [False] * 4096

    out = bytearray()
    bit_buf = 0
    bit_count = 0
    idx = 0
    n = len(blocks)

    def read_code():
        nonlocal bit_buf, bit_count, idx
        while bit_count < running_bits:
            if idx >= n:
                return None
            bit_buf |= blocks[idx] << bit_count
            idx += 1
            bit_count += 8
        code = bit_buf & ((1 << running_bits) - 1)
        bit_buf >>= running_bits
        bit_count -= running_bits
        return code

    prev_code = -1
    prev_entry = None
    prev_first = 0
    target = width * height

    while len(out) < target:
        code = read_code()
        if code is None or code == eof_code:
            break
        if code == clear_code:
            prefix = [0] * 4096
            suffix = [0] * 4096
            valid = [False] * 4096
            running_code = eof_code + 1
            running_bits = code_size + 1
            max_code = 1 << running_bits
            prev_code = -1
            prev_entry = None
            continue

        if code < clear_code:
            entry = [code]
            first = code
        elif valid[code]:
            entry = []
            c = code
            while c > clear_code:
                entry.append(suffix[c])
                c = prefix[c]
            entry.append(c)
            entry.reverse()
            first = entry[0]
        elif code == running_code and prev_entry is not None:
            entry = prev_entry + [prev_first]
            first = entry[0]
        else:
            break

        out.extend(entry)

        if prev_code != -1 and running_code < 4096:
            prefix[running_code] = prev_code
            suffix[running_code] = first
            valid[running_code] = True
            running_code += 1
            if running_code >= max_code and running_bits < 12:
                running_bits += 1
                max_code = 1 << running_bits

        prev_code = code
        prev_entry = entry
        prev_first = first

    return bytes(out[:target])


# ---------------------------------------------------------------------------
# MDEC RLE encoder (ported verbatim from PSn00bSDK encode_image.py)
# ---------------------------------------------------------------------------
ZIGZAG_TABLE = np.array((
    0,  1,  5,  6, 14, 15, 27, 28,
    2,  4,  7, 13, 16, 26, 29, 42,
    3,  8, 12, 17, 25, 30, 41, 43,
    9, 11, 18, 24, 31, 40, 44, 53,
    10, 19, 23, 32, 39, 45, 52, 54,
    20, 22, 33, 38, 46, 51, 55, 60,
    21, 34, 37, 47, 50, 56, 59, 61,
    35, 36, 48, 49, 57, 58, 62, 63
), np.uint8).argsort()

# MPEG-1 quantization table with the first value 2 (must be fed back via MDEC(2)).
QUANT_TABLE = np.array((
    2, 16, 19, 22, 26, 27, 29, 34,
    16, 16, 22, 24, 27, 29, 34, 37,
    19, 22, 26, 27, 29, 34, 34, 38,
    22, 22, 26, 27, 29, 34, 37, 40,
    22, 26, 27, 29, 32, 35, 40, 48,
    26, 27, 29, 32, 35, 40, 48, 58,
    26, 27, 29, 34, 38, 46, 56, 69,
    27, 29, 35, 38, 46, 56, 69, 83
), np.uint8).reshape((8, 8))

S = [np.cos((i or 4) / 16 * np.pi) / 2 for i in range(8)]
DCT_MATRIX = np.array((
    S[0],  S[0],  S[0],  S[0],  S[0],  S[0],  S[0],  S[0],
    S[1],  S[3],  S[5],  S[7], -S[7], -S[5], -S[3], -S[1],
    S[2],  S[6], -S[6], -S[2], -S[2], -S[6],  S[6],  S[2],
    S[3], -S[7], -S[1], -S[5],  S[5],  S[1],  S[7], -S[3],
    S[4], -S[4], -S[4],  S[4],  S[4], -S[4], -S[4],  S[4],
    S[5], -S[1],  S[7],  S[3], -S[3], -S[7],  S[1], -S[5],
    S[6], -S[2],  S[2], -S[6], -S[6],  S[2], -S[2],  S[6],
    S[7], -S[5],  S[3], -S[1],  S[1], -S[3],  S[5], -S[7]
), np.float32).reshape((8, 8))

LUMA_SCALE = 8
CHROMA_SCALE = 16


def to_int10(value):
    clamped = min(max(int(value), -0x200), 0x1ff)
    return clamped + (0 if clamped >= 0 else 0x400)


def encode_block(buffer, block, scale):
    _block = block.astype(np.float32) - 128.0
    coeffs = (DCT_MATRIX @ _block @ DCT_MATRIX.T) / QUANT_TABLE
    coeffs = coeffs.reshape((64,))[ZIGZAG_TABLE]

    buffer[0] = (scale << 10) | to_int10(round(coeffs[0]))
    offset = 1

    ac_values = coeffs[1:] * 8.0 / scale
    run_length = 0
    for ac in ac_values.round().astype(np.int32):
        if ac:
            buffer[offset] = (run_length << 10) | to_int10(ac)
            offset += 1
            run_length = 0
        else:
            run_length += 1
    if run_length:
        buffer[offset] = (run_length - 1) << 10
        offset += 1

    buffer[offset] = 0xfe00
    offset += 1
    if offset % 2:
        buffer[offset] = 0xfe00
        offset += 1
    return offset


def encode_macroblock(buffer, block, y_scale, c_scale):
    y, cb, cr = block.transpose((2, 0, 1))
    offset = 0
    offset += encode_block(buffer[offset:], cr[0:16:2, 0:16:2], c_scale)
    offset += encode_block(buffer[offset:], cb[0:16:2, 0:16:2], c_scale)
    offset += encode_block(buffer[offset:], y[0:8, 0:8], y_scale)
    offset += encode_block(buffer[offset:], y[0:8, 8:16], y_scale)
    offset += encode_block(buffer[offset:], y[8:16, 0:8], y_scale)
    offset += encode_block(buffer[offset:], y[8:16, 8:16], y_scale)
    return offset


# ---------------------------------------------------------------------------
# RSV parse
# ---------------------------------------------------------------------------
def rgb_to_ycbcr(rgb):
    # BT.601 (matches PIL "YCbCr" used by encode_image.py).
    scaled = rgb.astype(np.float32) / 255.0
    r, g, b = scaled[:, :, 0], scaled[:, :, 1], scaled[:, :, 2]
    y = 16 + r * 65.481 + g * 128.553 + b * 24.966
    cb = 128 - r * 37.797 - g * 74.203 + b * 112.0
    cr = 128 + r * 112.0 - g * 93.786 - b * 18.214
    return np.stack([y, cb, cr], axis=-1).astype(np.uint8)


def parse_rsv(path):
    data = open(path, "rb").read()
    frame_count, width, height = struct.unpack("<HHH", data[:6])
    pos = 6
    video_file_pos = pos
    frames = []
    for _ in range(frame_count):
        delta = struct.unpack("<I", data[pos:pos + 4])[0]
        pos += 4
        video_file_pos += delta

        palette = data[pos:pos + 384]
        pos += 384

        while data[pos] != 0x2C:  # ','
            pos += 1
        pos += 1  # skip ','

        left, top, iw, ih = struct.unpack("<HHHH", data[pos:pos + 8])
        pos += 8
        palette_type = data[pos]
        pos += 1

        if palette_type >> 7 == 1:
            pos += 128 * 3  # skip local color table (RSDKv2 discards it)

        code_size = data[pos]
        pos += 1
        blocks = bytearray()
        while True:
            n = data[pos]
            pos += 1
            if n == 0:
                break
            blocks += data[pos:pos + n]
            pos += n

        indices = gif_lzw_decode(bytes(blocks), code_size, iw, ih)
        frames.append((palette, indices, width, height))
        pos = video_file_pos
    return frames


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="build/fmv-src/Intro.rsv")
    ap.add_argument("--limit", type=int, default=0, help="only process N frames (0 = all)")
    ap.add_argument("--out", default=None, help="write raw MDEC bitstream (all frames)")
    ap.add_argument("--luma", type=int, default=LUMA_SCALE)
    ap.add_argument("--chroma", type=int, default=CHROMA_SCALE)
    args = ap.parse_args()

    frames = parse_rsv(args.input)
    print(f"frames={len(frames)}")

    limit = args.limit if args.limit else len(frames)
    total_bytes = 0
    all_out = bytearray()
    frame_meta = []  # (offset, size) per frame; offsets relative to bitstream start
    vw, vh = frames[0][2], frames[0][3]

    for i, (palette, indices, w, h) in enumerate(frames[:limit]):
        # Build RGB image from indices + palette (index 0 forced black, like RSDKv2).
        idx = np.frombuffer(indices, dtype=np.uint8).reshape(h, w)
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        for c in range(3):
            lut = np.zeros(256, dtype=np.uint8)
            for k in range(0x80):
                lut[k] = palette[k * 3 + c]
            rgb[:, :, c] = lut[idx]

        ycbcr = rgb_to_ycbcr(rgb)

        buf = np.empty(0x20000, np.uint16)
        off = 0
        for y in range(0, h, 16):
            for x in range(0, w, 16):
                block = ycbcr[y:y + 16, x:x + 16]
                off += encode_macroblock(buf[off:], block, args.luma, args.chroma)

        length = (off + 63) & 0xFFFFFFC0
        nbytes = length * 2
        if args.out:
            frame_meta.append((total_bytes, nbytes))
        total_bytes += nbytes
        if args.out:
            all_out += buf[:length].tobytes()

        if i == 0:
            print(f"  frame0: {w}x{h}, {w//16}x{h//16} macroblocks, RLE words={off}, bytes={nbytes}")

    avg = total_bytes / limit if limit else 0
    print(f"processed {limit} frames, total={total_bytes} bytes, avg/frame={avg:.0f}")
    # Extrapolate + CD rate check.
    if args.limit and len(frames) > limit:
        est = total_bytes / limit * len(frames)
        print(f"  extrapolated full video = {est/1e6:.2f} MB over {len(frames)} frames")
    full_mb = (total_bytes / limit * len(frames)) / 1e6
    sec_at_2x = full_mb / 0.3  # ~300 KB/s
    print(f"  full-video est: {full_mb:.2f} MB -> {sec_at_2x:.0f}s at 2x CD (300 KB/s)")

    if args.out:
        with open(args.out, "wb") as f:
            f.write(struct.pack("<III", limit, vw, vh))  # frameCount, width, height
            for off_, size_ in frame_meta:
                f.write(struct.pack("<II", off_, size_))  # per-frame offset + size
            f.write(all_out)  # the bitstream
        print(f"wrote {args.out} ({limit} frames, {len(all_out)} bytes bitstream)")


if __name__ == "__main__":
    main()
