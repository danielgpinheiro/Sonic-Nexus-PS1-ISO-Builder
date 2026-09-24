#!/usr/bin/env python3
"""Extract the Data.bin VFS into a loose Data/ tree under build/iso/ (raw, no XOR).

The VFS dirs already carry the "Data/" prefix (e.g. "Data/Stages/SSZ/"), so the
loose tree lands at build/iso/Data/... which becomes the ISO9660 root-relative
paths the engine's forceFolder path fopens (e.g. "Data/Stages/SSZ/Act1.bin").
"""
import struct, os

SRC = 'build/iso/Data.bin'
OUT = 'build/iso/'


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


def main():
    data = open(SRC, 'rb').read()
    headerSize, dirs = parse(data)
    blks = blocks(data, headerSize, dirs)
    count = 0
    for dirname, files in blks:
        for fname, fdata in files:
            path = os.path.join(OUT, dirname.strip('/'), fname)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(bytes(b ^ 0xFF for b in fdata))
            count += 1
    print(f'extracted {count} files under {OUT}Data/')


if __name__ == '__main__':
    main()
