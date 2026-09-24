#!/usr/bin/python3
"""Per-stage sprite atlas for the RSDKv2 PS1 port (phase 3d, golden rule: build time only).

For every stage manifest written by `rsdkscript --manifest DIR` (script paths in load order +
player .ani files) this collects every sprite frame the stage can draw:
  * `SpriteFrame(pivotX, pivotY, w, h, sprX, sprY)` in each script's `ObjectStartup`
    (all compile-time constants in Sonic Nexus; anything else is an error), attributed to
    the sheet that startup loads with `LoadSpriteSheet`;
  * every frame of the player animation files (.ani), attributed to their own sheets.
Frames that overlap merge into clusters (bounding boxes); clusters larger than a texture
page (256x256 texels) are cut at 256. A cluster with <= 15 colours becomes a 4-bit
texture (clusters share 16-entry CLUTs of master-palette indices, entry 0 = transparent),
otherwise 8-bit. Clusters are packed into the free VRAM columns (64 halfwords x 256 lines;
an 8-bit page spans 2 columns) and the 4-bit CLUTs go in the rows under the framebuffers.
Stages whose scripts call LoadVideo keep X 320-575 / Y 256-415 free for the FMV texture.

Output: <Data>/Sprites/Atlas/<Stage>.atl (little-endian):
  header : 'ATL1', u16 sheetCount, clusterCount, clutCount, blockCount,
           u16 fmvX, fmvY (0xFFFF = no FMV reservation), u32 dataOffset
  sheet  : char name[48] (path under Data/Sprites/, lower case), u16 firstCluster,
           clusterCount, width, height                                  (56 B)
  cluster: u16 srcX, srcY, w, h, u8 tpageX, tpageY, depth (4|8), u, v, pad, u16 clut
           (clut = CLUT index for 4-bit, 0xFFFF = master CLUT)             (16 B)
  clut   : u16 vramX, vramY, u8 map[16] (master palette index per 4-bit value) (20 B)
  block  : u16 x, y, w, h (VRAM halfwords), u32 offset of w*h u16 at dataOffset + offset
Every frame is decoded back from the atlas and compared with its GIF (must be exact).

Usage: build_atlas.py DATA_DIR MANIFEST_DIR [--stage NAME] [--cols N]  (--cols: test budget)
"""
import os, re, struct, sys
import numpy as np
from PIL import Image

PAGE = 256
# Free VRAM columns (64 halfwords wide) per page row: X 320-575 and 832-1023 (tiles use
# 576-831, the framebuffers 0-319). Adjacent pairs host 8-bit pages.
COLUMNS = [5, 6, 7, 8, 13, 14, 15]
PAIRS = [(5, 6), (7, 8), (13, 14)]
FMV_RESERVED = {(5, 1), (6, 1), (7, 1), (8, 1)}  # (column, pageY) -> 15-bit video page
FMV_XY = (320, 256)
# 4-bit CLUT slots (16 halfwords): row 240 right of the master CLUT, rows 241-255 and 496-503
# (rows 504-511 hold the runtime INK_BLEND CLUTs, Drawing.cpp PS1_BLEND_*)
CLUT_SLOTS = [(x, 240) for x in range(256, 320, 16)] + \
             [(x, y) for y in list(range(241, 256)) + list(range(496, 504)) for x in range(0, 320, 16)]


class AtlasError(Exception):
    pass


def startup_frames(path):
    txt = open(path, encoding='latin1').read().replace('\r', '')
    m = re.search(r'^sub ObjectStartup\b(.*?)^end sub', txt, re.S | re.M)
    if not m:
        return None, []
    body = re.sub(r'//[^\n]*', '', m.group(1))
    sheets = re.findall(r'LoadSpriteSheet\("([^"]+)"\)', body)
    frames = []
    for args in re.findall(r'SpriteFrame\(([^)]*)\)', body):
        parts = [a.strip() for a in args.split(',')]
        if len(parts) != 6 or not all(re.fullmatch(r'-?\d+', a) for a in parts):
            raise AtlasError('%s: non-constant SpriteFrame(%s)' % (path, args))
        px, py, w, h, x, y = map(int, parts)
        frames.append((x, y, w, h))
    if frames and not sheets and 'LoadVideo(' in txt:
        return None, []  # frames of the FMV surface (LoadVideo), not of a sprite sheet
    if frames and len(sheets) != 1:
        raise AtlasError('%s: %d LoadSpriteSheet calls for %d frames' % (path, len(sheets), len(frames)))
    return (sheets[0] if sheets else None), frames


def ani_frames(path):
    d = open(path, 'rb').read()
    p, names = 5, []
    for _ in range(4):
        n = d[p]; p += 1
        names.append(d[p:p + n].decode('latin1') if n else None); p += n
    out = []
    count = d[p]; p += 1
    for _ in range(count):
        fc = d[p]; p += 3
        for _ in range(fc):
            sh, hb, x, y, w, h = d[p:p + 6]; p += 8
            out.append((names[sh], (x, y, w, h)))
    return out


def uses_video(path):
    return 'LoadVideo(' in open(path, encoding='latin1').read()


def merge(rects):
    """Merge overlapping rects into bounding boxes until none overlap."""
    rects = [list(r) for r in rects]
    changed = True
    while changed:
        changed = False
        out = []
        for r in rects:
            for o in out:
                if r[0] < o[0] + o[2] and o[0] < r[0] + r[2] and r[1] < o[1] + o[3] and o[1] < r[1] + r[3]:
                    x0, y0 = min(r[0], o[0]), min(r[1], o[1])
                    x1, y1 = max(r[0] + r[2], o[0] + o[2]), max(r[1] + r[3], o[1] + o[3])
                    o[:] = [x0, y0, x1 - x0, y1 - y0]
                    changed = True
                    break
            else:
                out.append(r)
        rects = out
    return [tuple(r) for r in rects]


def split(r):
    x, y, w, h = r
    return [(x + i, y + j, min(PAGE, w - i), min(PAGE, h - j)) for j in range(0, h, PAGE) for i in range(0, w, PAGE)]


class Bin:
    """One texture page (256 x 256 texels): skyline packer."""
    def __init__(self, tpx, tpy, depth, width, cols):
        self.tpx, self.tpy, self.depth, self.width, self.cols = tpx, tpy, depth, width, cols
        self.sky = [0] * width

    def place(self, w, h):
        best = None
        for u in range(0, self.width - w + 1):
            v = max(self.sky[u:u + w])
            if v + h <= PAGE and (best is None or v < best[1] or (v == best[1] and u < best[0])):
                best = (u, v)
        if best:
            u, v = best
            for i in range(u, u + w):
                self.sky[i] = v + h
        return best


def build_stage(data, manifest, name, cols_limit=None):
    scripts, anis = [], []
    for line in open(manifest):
        kind, _, arg = line.strip().partition(' ')
        (scripts if kind == 'script' else anis).append(arg)
    frames = {}  # sheet -> set of rects
    video = False
    for s in scripts:
        path = os.path.join(data, 'Scripts', s)
        sheet, fr = startup_frames(path)
        video |= uses_video(path)
        if sheet and fr:
            frames.setdefault(sheet, set()).update(fr)
    for a in anis:
        for sheet, r in ani_frames(os.path.join(data, 'Animations', a)):
            frames.setdefault(sheet, set()).add(r)

    images = {}
    clusters = []  # dict(sheet, rect, depth, colors, clut, tpx, tpy, u, v)
    for sheet in sorted(frames):
        im = np.array(Image.open(os.path.join(data, 'Sprites', sheet)))
        images[sheet] = im
        H, W = im.shape
        rects = []
        for (x, y, w, h) in frames[sheet]:
            x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
            if x1 > x0 and y1 > y0:
                rects.append((x0, y0, x1 - x0, y1 - y0))
        for r in merge(rects):
            for piece in split(r):
                x, y, w, h = piece
                cols = set(np.unique(im[y:y + h, x:x + w]).tolist()) - {0}
                clusters.append(dict(sheet=sheet, rect=piece, colors=cols, depth=4 if len(cols) <= 15 else 8))

    # CLUT groups for 4-bit clusters (greedy: biggest colour sets first, least growth).
    groups = []
    for c in sorted((c for c in clusters if c['depth'] == 4), key=lambda c: -len(c['colors'])):
        best = None
        for gi, g in enumerate(groups):
            u = g | c['colors']
            if len(u) <= 15 and (best is None or len(u) - len(g) < best[1]):
                best = (gi, len(u) - len(g))
        if best:
            groups[best[0]] |= c['colors']
            c['clut'] = best[0]
        else:
            groups.append(set(c['colors']))
            c['clut'] = len(groups) - 1
    if len(groups) > len(CLUT_SLOTS):
        raise AtlasError('%s: %d CLUTs > %d slots' % (name, len(groups), len(CLUT_SLOTS)))
    clut_maps = [[0] + sorted(g) + [0] * (15 - len(g)) for g in groups]

    # Columns available (column, pageY); FMV page reserved when the stage plays a video.
    free = [(c, py) for py in (0, 1) for c in COLUMNS]
    if video:
        free = [cp for cp in free if cp not in FMV_RESERVED]
    if cols_limit is not None:
        free = free[:cols_limit]
    bins = []

    def new_bin(depth):
        if depth == 8:
            for a, b in PAIRS:
                for py in (0, 1):
                    if (a, py) in free and (b, py) in free:
                        free.remove((a, py)); free.remove((b, py))
                        return Bin(a, py, 8, PAGE, [(a, py), (b, py)])
            for cp in list(free):  # a lone column: an 8-bit page with u < 128
                free.remove(cp)
                return Bin(cp[0], cp[1], 8, 128, [cp])
            return None
        if free:
            cp = free.pop(0)
            return Bin(cp[0], cp[1], 4, PAGE, [cp])
        return None

    for depth in (8, 4):
        todo = sorted((c for c in clusters if c['depth'] == depth), key=lambda c: (-c['rect'][3], -c['rect'][2]))
        for c in todo:
            w, h = c['rect'][2], c['rect'][3]
            spot = None
            for b in bins:
                if b.depth == depth and w <= b.width:
                    spot = b.place(w, h)
                    if spot:
                        break
            if not spot:
                b = new_bin(depth)
                while b is not None and w > b.width:  # a half-width 8-bit page can't take it
                    b = new_bin(depth)
                if b is None:
                    raise AtlasError('%s: out of VRAM placing %s %s (%d-bit)' % (name, c['sheet'], c['rect'], depth))
                bins.append(b)
                spot = b.place(w, h)
            c['tpx'], c['tpy'], (c['u'], c['v']) = b.tpx, b.tpy, spot

    # Render the VRAM image of the sprite columns.
    vram = np.zeros((512, 1024), np.uint16)
    used_lines = {}
    for c in clusters:
        x, y, w, h = c['rect']
        idx = images[c['sheet']][y:y + h, x:x + w].astype(np.uint16)
        X0, Y0 = c['tpx'] * 64, c['tpy'] * 256 + c['v']
        if c['depth'] == 8:
            if c['u'] % 2 or w % 2:  # keep whole halfwords: pad with transparent texels
                idx = np.pad(idx, ((0, 0), (c['u'] % 2, (c['u'] + w) % 2)))
            hx = X0 + c['u'] // 2
            words = idx[:, 0::2] | (idx[:, 1::2] << 8)
        else:
            lut = {v: i for i, v in enumerate(clut_maps[c['clut']])}
            lut[0] = 0
            q = np.vectorize(lambda v: lut[v])(idx).astype(np.uint16) if idx.size else idx
            lead, trail = c['u'] % 4, (-(c['u'] + w)) % 4
            q = np.pad(q, ((0, 0), (lead, trail)))
            hx = X0 + c['u'] // 4
            words = q[:, 0::4] | (q[:, 1::4] << 4) | (q[:, 2::4] << 8) | (q[:, 3::4] << 12)
        region = vram[Y0:Y0 + h, hx:hx + words.shape[1]]
        region |= words  # padding texels are 0, neighbours never overlap real texels
        key = (c['tpx'], c['tpy'])
        used_lines[key] = max(used_lines.get(key, 0), c['v'] + h)

    blocks = []
    for b in bins:
        lines = used_lines.get((b.tpx, b.tpy), 0)
        if lines:
            w = 64 * len(b.cols)
            blocks.append((b.tpx * 64, b.tpy * 256, w, lines))

    # Self-check: decode every cluster from the VRAM image + CLUT maps into a reconstructed
    # sheet, then every frame region must equal the GIF (and be fully covered).
    recon = {sh: np.full(im.shape, -1, np.int32) for sh, im in images.items()}
    for c in clusters:
        x, y, w, h = c['rect']
        X0, Y0 = c['tpx'] * 64, c['tpy'] * 256 + c['v']
        if c['depth'] == 8:
            words = vram[Y0:Y0 + h, X0 + c['u'] // 2:X0 + (c['u'] + w + 1) // 2 + 1].astype(np.int32)
            tex = np.stack([words & 0xFF, words >> 8], -1).reshape(h, -1)[:, c['u'] % 2:c['u'] % 2 + w]
        else:
            words = vram[Y0:Y0 + h, X0 + c['u'] // 4:X0 + (c['u'] + w + 3) // 4 + 1].astype(np.int32)
            nib = np.stack([(words >> s_) & 0xF for s_ in (0, 4, 8, 12)], -1).reshape(h, -1)[:, c['u'] % 4:c['u'] % 4 + w]
            tex = np.array(clut_maps[c['clut']], np.int32)[nib]
        recon[c['sheet']][y:y + h, x:x + w] = tex
    checked = 0
    for sheet, rects in frames.items():
        im, rc_ = images[sheet], recon[sheet]
        H, W = im.shape
        for (x, y, w, h) in rects:
            x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
            if x1 <= x0 or y1 <= y0:
                continue
            a, b = rc_[y0:y1, x0:x1], im[y0:y1, x0:x1].astype(np.int32)
            if (a < 0).any():
                raise AtlasError('%s: %s frame %s not fully in the atlas' % (name, sheet, (x, y, w, h)))
            if (a != b).any():
                yy, xx = np.argwhere(a != b)[0]
                raise AtlasError('%s: %s frame %s texel (%d,%d) atlas %d != gif %d' % (
                    name, sheet, (x, y, w, h), x0 + xx, y0 + yy, a[yy, xx], b[yy, xx]))
            checked += a.size

    # Write the file.
    sheets = sorted(frames)
    order = sorted(clusters, key=lambda c: (sheets.index(c['sheet']), c['rect'][1], c['rect'][0]))
    out = bytearray()
    sheet_tab, cl_tab = bytearray(), bytearray()
    for s in sheets:
        mine = [i for i, c in enumerate(order) if c['sheet'] == s]
        H, W = images[s].shape
        sheet_tab += struct.pack('<48sHHHH', s.lower().encode()[:47], mine[0], len(mine), W, H)
    for c in order:
        x, y, w, h = c['rect']
        cl_tab += struct.pack('<HHHHBBBBBBH', x, y, w, h, c['tpx'], c['tpy'], c['depth'], c['u'], c['v'], 0,
                              c['clut'] if c['depth'] == 4 else 0xFFFF)
    clut_tab = bytearray()
    for i, m in enumerate(clut_maps):
        clut_tab += struct.pack('<HH', *CLUT_SLOTS[i]) + bytes(m)
    blk_tab, pixels = bytearray(), bytearray()
    for (x, y, w, h) in blocks:
        blk_tab += struct.pack('<HHHHI', x, y, w, h, len(pixels))
        pixels += vram[y:y + h, x:x + w].astype('<u2').tobytes()
    head_len = 20 + len(sheet_tab) + len(cl_tab) + len(clut_tab) + len(blk_tab)
    data_off = (head_len + 2047) // 2048 * 2048  # pixel data starts on a sector
    fx, fy = FMV_XY if video else (0xFFFF, 0xFFFF)
    out += struct.pack('<4sHHHHHHI', b'ATL1', len(sheets), len(order), len(clut_maps), len(blocks), fx, fy, data_off)
    out += sheet_tab + cl_tab + clut_tab + blk_tab
    out += bytes(data_off - len(out)) + pixels

    n4 = sum(c['rect'][2] * c['rect'][3] for c in clusters if c['depth'] == 4)
    n8 = sum(c['rect'][2] * c['rect'][3] for c in clusters if c['depth'] == 8)
    report = ('%-7s sheets %2d clusters %3d (4-bit %3d / 8-bit %3d) texels 4-bit %6d 8-bit %6d | pages 8-bit %d 4-bit %d '
              '| VRAM %6d hw | CLUTs %2d | FMV %s | file %6d B | self-check %d texels OK' % (
                  name, len(sheets), len(order), sum(c['depth'] == 4 for c in clusters),
                  sum(c['depth'] == 8 for c in clusters), n4, n8,
                  sum(b.depth == 8 for b in bins), sum(b.depth == 4 for b in bins),
                  sum(w * h for (_, _, w, h) in blocks), len(clut_maps), 'reserved' if video else '-', len(out), checked))
    return bytes(out), report


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 2
    data, mdir = args[0], args[1]
    only = args[args.index('--stage') + 1] if '--stage' in args else None
    cols = int(args[args.index('--cols') + 1]) if '--cols' in args else None
    outdir = os.path.join(data, 'Sprites', 'Atlas')
    os.makedirs(outdir, exist_ok=True)
    rc = 0
    for f in sorted(os.listdir(mdir)):
        if not f.endswith('.txt'):
            continue
        name = f[:-4]
        if only and name != only:
            continue
        try:
            blob, report = build_stage(data, os.path.join(mdir, f), name, cols)
        except AtlasError as e:
            print('ERROR', e)
            rc = 1
            continue
        if cols is None:
            open(os.path.join(outdir, name + '.atl'), 'wb').write(blob)
        print(report)
    return rc


if __name__ == '__main__':
    sys.exit(main())
