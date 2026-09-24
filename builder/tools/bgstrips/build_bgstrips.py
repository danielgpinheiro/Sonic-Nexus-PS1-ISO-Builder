#!/usr/bin/env python3
"""Build-time BG line strips for the PS1 tile renderer (phase 3c).

A BG tile layer is drawn per line (PC DrawHLineScrollLayer): lines that share an X scroll form a
band. With tiles a band costs ~21 primitives per 16 lines, and parallax gradients (a new X
scroll every 1-2 lines) cost ~21 per line. This tool pre-renders layer lines at build time into
VRAM the stage's sprite atlas leaves free, as 8-bit rows of one horizontal period of the layer
(visual plane of its draw slot and tile flips baked in, index 0 = transparent), so a band of any
height costs 1-3 sprites.

Lines are chosen per 16-line tile row: rows with thin runs (lineScroll runs < 16 lines) first,
then the other rows nearest to them, until the free VRAM is used. Rows left out are drawn with
tiles. Fails if the stage's layers disagree across acts (plane baking) or a layout is invalid.

Output Data/Stages/<Stage>/BGStrips.bin (little endian):
  char[4] 'BGS1', u16 regionCount, u16 0
  region (28 B): u8 layer, u8 plane, u16 line0, u16 lines (multiple of 16), u16 period (texels),
                 u8 pieceCount, u8 0, 3 x { u16 vramX (halfwords), u16 vramY, u16 width (texels) }
  then per region, per piece: lines rows x width bytes (8-bit indices), rows top to bottom.
A piece starts at a 64-halfword column (texture page pageX = vramX / 64, u = 0) and stays inside
one 256-row page (v = vramY & 255); pieces split the period into <= 256-texel parts.

Usage: build_bgstrips.py DATA_DIR [--stage NAME]
"""
import os, struct, sys

ATLAS_COLUMNS = [5, 6, 7, 8, 13, 14, 15]  # tools/atlas/build_atlas.py COLUMNS
FMV_RECT = (320, 256, 256, 160)          # tools/atlas/build_atlas.py FMV_XY + 256x160
SCROLL_MAX = 0x10 * 128
MAX_REGIONS = 64


class StripError(Exception):
    pass


def load_tiles(sdir):
    raw = open(os.path.join(sdir, '16x16Tiles.raw'), 'rb').read()
    gfx = raw[4 + 768:]
    t = open(os.path.join(sdir, '128x128Tiles.bin'), 'rb').read()
    tiles = []
    for i in range(len(t) // 3):
        e0, e1 = t[3 * i] & 0x3F, t[3 * i + 1]
        plane = e0 >> 4
        e0 &= 0xF
        tiles.append((e1 + ((e0 & 3) << 8), e0 >> 2, plane))
    return gfx, tiles


def load_backgrounds(sdir):
    b = open(os.path.join(sdir, 'Backgrounds.bin'), 'rb').read()
    j = 0

    def rb():
        nonlocal j
        v = b[j]
        j += 1
        return v
    lc = rb()
    for _ in range(rb()):
        rb(), rb(), rb()
    for _ in range(rb()):
        rb(), rb(), rb()
    layers = {}
    for L in range(1, lc + 1):
        xs, ys, ty, pf, sp = rb(), rb(), rb(), rb(), rb()
        ls = []
        while True:
            c = rb()
            if c == 0xFF:
                c1 = rb()
                if c1 == 0xFF:
                    break
                ls += [c1] * (rb() - 1)
            else:
                ls.append(c)
        ls = (ls + [0] * SCROLL_MAX)[:SCROLL_MAX]
        grid = [[rb() for _ in range(xs)] for _ in range(ys)]
        layers[L] = dict(xsize=xs, ysize=ys, type=ty, lineScroll=ls, tiles=grid)
    return layers


def act_layers(sdir):
    """(activeTileLayers, midpoint) of every Act*.bin; they must agree for the baked planes."""
    cfgs = set()
    for f in sorted(os.listdir(sdir)):
        if f.startswith('Act') and f.endswith('.bin'):
            a = open(os.path.join(sdir, f), 'rb').read()
            i = 1 + a[0]
            cfgs.add((tuple(a[i:i + 4]), a[i + 4]))
    if len(cfgs) != 1:
        raise StripError('acts disagree on active layers %s' % sorted(cfgs))
    return cfgs.pop()


def period_chunks(L):
    for p in range(1, L['xsize'] + 1):
        if L['xsize'] % p == 0 and all(row[x] == row[x % p] for row in L['tiles'] for x in range(L['xsize'])):
            return p
    return L['xsize']


def render_line(gfx, tiles, L, plane, ly, period):
    cy, ty, ty16 = ly >> 7, (ly & 0x7F) >> 4, ly & 0xF
    out = bytearray(period)
    for t in range(period):
        ch = L['tiles'][cy][t >> 7]
        tile, d, pl = tiles[(ch << 6) + ((t & 0x7F) >> 4) + 8 * ty]
        if pl != plane or not tile:
            continue
        tx, tyy = t & 0xF, ty16
        if d & 1:
            tx = 15 - tx
        if d & 2:
            tyy = 15 - tyy
        out[t] = gfx[(tile << 8) + tyy * 16 + tx]
    return bytes(out)


def free_grid(atl_path):
    """used[y][x] (halfwords) from the .atl blocks + FMV reservation; only atlas columns are free."""
    used = [bytearray(1024) for _ in range(512)]
    for y in range(512):
        row = used[y]
        for x in range(1024):
            row[x] = 0 if (x // 64) in ATLAS_COLUMNS else 1
    if os.path.exists(atl_path):
        d = open(atl_path, 'rb').read()
        _, ns, nc, ncl, nb, fx, fy, _ = struct.unpack_from('<4sHHHHHHI', d, 0)
        o = 20 + ns * 56 + nc * 16 + ncl * 20
        rects = [struct.unpack_from('<HHHHI', d, o + 12 * k)[:4] for k in range(nb)]
        if fx != 0xFFFF:
            rects.append(FMV_RECT)
        for x, y, w, h in rects:
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    used[yy][xx] = 1
    return used


def fits(used, x, y, w, h):
    if x < 0 or y < 0 or x + w > 1024 or y + h > 512:
        return False
    return all(not any(used[yy][x:x + w]) for yy in range(y, y + h))


def mark(used, x, y, w, h):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            used[yy][xx] = 1


def alloc(used, w_hw, h, prefer=()):
    """A w_hw x h rect at a column start, inside one 256-row page and one texture page."""
    for pr in prefer:
        if fits(used, pr[0], pr[1], w_hw, h) and (pr[1] & 255) + h <= 256:
            return pr
    for py in (1, 0):
        for c in ATLAS_COLUMNS:
            x = c * 64
            if w_hw > 64 and (c + 1) not in ATLAS_COLUMNS:
                continue
            for y in range(py * 256, py * 256 + 256 - h + 1, 16):
                if fits(used, x, y, w_hw, h):
                    return (x, y)
    return None


def build_stage(data, name):
    sdir = os.path.join(data, 'Stages', name)
    if not os.path.exists(os.path.join(sdir, 'Backgrounds.bin')):
        return None, '%-7s no Backgrounds.bin' % name
    layers = load_backgrounds(sdir)
    active, mid = act_layers(sdir)
    gfx, tiles = load_tiles(sdir)
    used = free_grid(os.path.join(data, 'Sprites', 'Atlas', name + '.atl'))

    # (layer, plane) drawn by the BG slots
    jobs = []
    for slot, li in enumerate(active):
        if 1 <= li < 4 and li in layers and layers[li]['type'] == 1 and layers[li]['xsize']:
            key = (li, 1 if slot >= mid else 0)
            if key not in [(j['layer'], j['plane']) for j in jobs]:
                L = layers[li]
                p = period_chunks(L) * 128
                pieces = [min(256, p - s) for s in range(0, p, 256)]
                if len(pieces) > 3:
                    raise StripError('%s layer %d period %d > 768 texels' % (name, li, p))
                full_h = L['ysize'] * 128
                ls = L['lineScroll'][:full_h]
                thin = set()
                i = 0
                while i < full_h:
                    j = i
                    while j < full_h and ls[j] == ls[i]:
                        j += 1
                    if j - i < 16:
                        thin.update(range(i >> 4, ((j - 1) >> 4) + 1))
                    i = j
                jobs.append(dict(layer=li, plane=key[1], L=L, period=p, pieces=pieces, rows=full_h >> 4, thin=thin))

    # candidate tile rows, thin ones first, then nearest to a thin row
    cands = []
    for ji, j in enumerate(jobs):
        for r in range(j['rows']):
            d = 0 if r in j['thin'] else (min(abs(r - t) for t in j['thin']) if j['thin'] else 1000 + r)
            cands.append((d, ji, r))
    cands.sort()

    chosen = {}  # (ji, row) -> [(x, y) per piece]
    for d, ji, r in cands:
        j = jobs[ji]
        above, below = chosen.get((ji, r - 1)), chosen.get((ji, r + 1))
        spots = []
        ok = True
        for k, w in enumerate(j['pieces']):
            pref = []
            if above and (above[k][1] & 255) + 16 < 256:  # continue under the row above (same page)
                pref.append((above[k][0], above[k][1] + 16))
            if below and (below[k][1] & 255) >= 16:       # or on top of the row below
                pref.append((below[k][0], below[k][1] - 16))
            spot = alloc(used, w // 2, 16, pref)
            if not spot:
                ok = False
                break
            mark(used, spot[0], spot[1], w // 2, 16)
            spots.append(spot)
        if not ok:
            for k, s in enumerate(spots):  # undo a partial row
                for yy in range(s[1], s[1] + 16):
                    for xx in range(s[0], s[0] + j['pieces'][k] // 2):
                        used[yy][xx] = 0
            continue
        chosen[(ji, r)] = spots

    # Placement: the priority pass above only selects rows (it fragments). Re-place the selected
    # rows in line order, one piece at a time, so consecutive rows land contiguously.
    selected = sorted(chosen)
    used = free_grid(os.path.join(data, 'Sprites', 'Atlas', name + '.atl'))
    placed = {key: [] for key in selected}
    for ji, j in enumerate(jobs):
        for k, w in enumerate(j['pieces']):
            for key in [key for key in selected if key[0] == ji]:
                if len(placed[key]) != k:  # an earlier piece of this row failed
                    continue
                prev = placed.get((ji, key[1] - 1))
                pref = [(prev[k][0], prev[k][1] + 16)] if prev and len(prev) > k and (prev[k][1] & 255) + 16 < 256 else []
                spot = alloc(used, w // 2, 16, pref)
                if spot:
                    mark(used, spot[0], spot[1], w // 2, 16)
                    placed[key].append(spot)
    chosen = {key: v for key, v in placed.items() if len(v) == len(jobs[key[0]]['pieces'])}
    for key, v in placed.items():  # free the pieces of incomplete rows (not needed: file only)
        pass

    # merge consecutive rows stored contiguously into regions
    regions = []
    for ji, j in enumerate(jobs):
        r = 0
        while r < j['rows']:
            if (ji, r) not in chosen:
                r += 1
                continue
            start, spots = r, chosen[(ji, r)]
            r += 1
            while (ji, r) in chosen and all(chosen[(ji, r)][k] == (spots[k][0], spots[k][1] + 16 * (r - start))
                                            for k in range(len(spots))) and ((spots[0][1] & 255) + 16 * (r - start + 1)) <= 256 \
                    and all((s[1] & 255) + 16 * (r - start + 1) <= 256 for s in spots):
                r += 1
            regions.append(dict(job=j, line0=start * 16, lines=(r - start) * 16, spots=spots))
    if len(regions) > MAX_REGIONS:
        raise StripError('%s: %d regions > %d' % (name, len(regions), MAX_REGIONS))

    out = bytearray(b'BGS1' + struct.pack('<HH', len(regions), 0))
    blob = bytearray()
    for g in regions:
        j = g['job']
        ent = struct.pack('<BBHHHBB', j['layer'], j['plane'], g['line0'], g['lines'], j['period'], len(j['pieces']), 0)
        for k in range(3):
            if k < len(j['pieces']):
                ent += struct.pack('<HHH', g['spots'][k][0], g['spots'][k][1], j['pieces'][k])
            else:
                ent += struct.pack('<HHH', 0, 0, 0)
        assert len(ent) == 28
        out += ent
        lines = [render_line(gfx, tiles, j['L'], j['plane'], ly, j['period']) for ly in range(g['line0'], g['line0'] + g['lines'])]
        s0 = 0
        for w in j['pieces']:
            for row in lines:
                blob += row[s0:s0 + w]
            s0 += w
    out += blob

    summary = []
    for j in jobs:
        rows = sorted(r for (ji, r) in chosen if jobs[ji] is j)
        summary.append('L%d/p%d period %d: %d/%d rows (thin %d)' % (j['layer'], j['plane'], j['period'], len(rows), j['rows'], len(j['thin'])))
    vram = sum(g['lines'] * sum(w // 2 for w in g['job']['pieces']) for g in regions)
    return bytes(out), '%-7s regions %2d | %s | VRAM %6d hw | file %6d B' % (name, len(regions), '; '.join(summary), vram, len(out))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    data = args[0]
    names = [args[args.index('--stage') + 1]] if '--stage' in args else sorted(os.listdir(os.path.join(data, 'Stages')))
    for name in names:
        try:
            blob, report = build_stage(data, name)
        except StripError as e:
            print('ERROR', e)
            sys.exit(1)
        print(report)
        path = os.path.join(data, 'Stages', name, 'BGStrips.bin')
        if blob and len(blob) > 8:
            open(path, 'wb').write(blob)
        elif os.path.exists(path):
            os.remove(path)


if __name__ == '__main__':
    main()
