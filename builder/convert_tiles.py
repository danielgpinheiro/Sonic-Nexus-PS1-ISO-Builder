#!/usr/bin/env python3
"""Convert 16x16Tiles.gif -> 16x16Tiles.raw (palette + raw 8-bit strip) and
16x16Tiles.vram (palette + tiles pre-packed in PS1 texture-page layout), and repack Data.bin.

Usage:
  python3 convert_tiles.py                 # Data.bin mode: add .raw + .vram into build/iso/Data.bin
  python3 convert_tiles.py --loose DIR     # convert every DIR/**/16x16Tiles.raw -> 16x16Tiles.vram

.vram format (loaded by PS1UploadTileSet / LoadStageGIFFile on PS1):
  u16 BE width (256), u16 BE height (1024), 256*3 palette, then 4 texture pages of
  256x256 8-bit texels (65536 bytes each, row-major). Page p holds tiles p*256..p*256+255
  in a 16x16 grid: tile n (within the page) at texel (16*(n%16), 16*(n/16)). Each page is
  uploaded with a single DMA to VRAM (128 halfwords x 256 lines) — no CPU re-pack at runtime.

Raw format (matched by LoadStageGIFFile on PS1):
  u16 BE width, u16 BE height, 256*3 palette (GCT), then width*height raw pixels.
The strip is 16x16384 (1024 tiles); tile N sits at byte N*256 of the pixel block,
the same layout as TileGfx[].
"""
import struct, io, os
from PIL import Image

SRC = 'build/iso/Data.bin'
DST = 'build/iso/Data.bin'
BAK = 'build/Data.bin.bak'  # outside build/iso: never shipped on the disc


def parse(data):
    headerSize = struct.unpack('<I', data[0:4])[0]
    dirCount = data[4]
    pos = 5
    dirs = []
    for _ in range(dirCount):
        nameLen = data[pos]; pos += 1
        name = data[pos:pos + nameLen].decode('latin1'); pos += nameLen
        offset = struct.unpack('<I', data[pos:pos + 4])[0]; pos += 4
        dirs.append([name, offset])
    return headerSize, dirs


def blocks(data, headerSize, dirs):
    out = []
    for i, (name, offset) in enumerate(dirs):
        start = offset + headerSize
        nxt = dirs[i + 1][1] + headerSize if i + 1 < len(dirs) else len(data)
        p = start
        files = []
        while p < nxt - 8:
            nameLen = data[p]; p += 1
            if nameLen == 0 or nameLen > 64:
                break
            fname = data[p:p + nameLen].decode('latin1'); p += nameLen
            size = struct.unpack('<I', data[p:p + 4])[0]; p += 4
            files.append((fname, data[p:p + size]))
            p += size
        out.append((name, files))
    return out


def gif_to_raw(raw):
    im = Image.open(io.BytesIO(raw)).convert('P')
    w, h = im.size
    pal = im.getpalette() or []
    pal = bytes(pal[:768])
    pal = pal.ljust(768, b'\x00')
    px = im.tobytes()
    assert len(px) == w * h, (len(px), w * h)
    out = bytearray()
    out += struct.pack('>H', w)
    out += struct.pack('>H', h)
    out += pal
    out += px
    return bytes(out)


TILES_PER_PAGE = 256
PAGES = 4


def raw_to_vram(raw):
    """16x16Tiles.raw (header + 16x16384 strip) -> 16x16Tiles.vram (header + 4 pages)."""
    hdr = raw[4:4 + 768]
    strip = raw[4 + 768:]
    assert len(strip) == 16 * 16 * TILES_PER_PAGE * PAGES, len(strip)
    out = bytearray(struct.pack('>HH', 256, 256 * PAGES)) + hdr
    for page in range(PAGES):
        pg = bytearray(256 * 256)
        for n in range(TILES_PER_PAGE):
            tile = page * TILES_PER_PAGE + n
            tx, ty = (n & 15) * 16, (n >> 4) * 16
            src = tile * 256
            for y in range(16):
                row = (ty + y) * 256 + tx
                pg[row:row + 16] = strip[src + y * 16:src + y * 16 + 16]
        out += pg
    return bytes(out)


def loose(root):
    n = 0
    for dirpath, _, files in os.walk(root):
        if '16x16Tiles.raw' in files:
            raw = open(os.path.join(dirpath, '16x16Tiles.raw'), 'rb').read()
            open(os.path.join(dirpath, '16x16Tiles.vram'), 'wb').write(raw_to_vram(raw))
            n += 1
            print('wrote', os.path.join(dirpath, '16x16Tiles.vram'))
    print(f'{n} .vram files')


def main():
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == '--loose':
        loose(sys.argv[2])
        return
    data = open(SRC, 'rb').read()
    headerSize, dirs = parse(data)
    blks = blocks(data, headerSize, dirs)

    added = 0
    for dirname, files in blks:
        newfiles = []
        for fname, fdata in files:
            if fname == '16x16Tiles.gif':
                raw = gif_to_raw(bytes(b ^ 0xFF for b in fdata))
                newfiles.append(('16x16Tiles.raw', bytes(b ^ 0xFF for b in raw)))
                newfiles.append(('16x16Tiles.vram', bytes(b ^ 0xFF for b in raw_to_vram(raw))))
                added += 1
        files.extend(newfiles)

    offsets = []
    running = 0
    for dirname, files in blks:
        offsets.append(running)
        for fname, fdata in files:
            running += 1 + len(fname.encode('latin1')) + 4 + len(fdata)

    out = bytearray()
    out += struct.pack('<I', headerSize)
    out += bytes([len(dirs)])
    for (dirname, _), offset in zip(dirs, offsets):
        nb = dirname.encode('latin1')
        out += bytes([len(nb)]) + nb + struct.pack('<I', offset)
    while len(out) < headerSize:
        out += b'\x00'
    for dirname, files in blks:
        for fname, fdata in files:
            nb = fname.encode('latin1')
            out += bytes([len(nb)]) + nb + struct.pack('<I', len(fdata)) + fdata

    os.replace(SRC, BAK)
    with open(DST, 'wb') as f:
        f.write(out)
    print(f'wrote {DST} ({len(out)} bytes), added {added} 16x16Tiles.raw/.vram pairs, backed up to {BAK}')


if __name__ == '__main__':
    main()
