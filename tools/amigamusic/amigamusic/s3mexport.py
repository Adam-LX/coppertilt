"""Eksport piosenki do ScreamTracker 3 .s3m (dowolny profil, do 16 kanałów, sample 8/16-bit).

    python3 -m amigamusic render SONG --s3m out.s3m

Mapowanie efektów PT -> S3M: 0xy->J, 1xx->F, 2xx->E, 3xx->G, 4xy->H, 5->L, 6->K, 8xx->X, 9->O,
Axy->D, B->B, C->kolumna głośności, D->C, F<0x20->A (speed), F>=0x20->T (tempo),
E1x->FFx, E2x->EFx, E9x->Q0x, EAx->DxF, EBx->DFx, ECx->SCx, EDx->SDx, E6x->SBx, EEx->SEx.
Nuta: oktawa S3M = oktawa w pliku piosenki + 2 (C-2 w piosence = C-4 w S3M), C4SPD = c2spd sampla.
Echo/pogłos/panorama-pogłos z nagłówka piosenki nie są częścią S3M (kanały mają tylko panoramę).
"""
import struct

import numpy as np

from .player import Renderer
from .songtext import SongError
from . import _export

SIMPLE = {0x0: "J", 0x1: "F", 0x2: "E", 0x3: "G", 0x4: "H", 0x5: "L", 0x6: "K", 0x9: "O",
          0xA: "D", 0xB: "B", 0xD: "C"}


def _cmd(letter):
    return ord(letter) - ord("A") + 1


def _effect(eff, par):
    """-> (cmd, info, vol_override) albo (None, None, vol)."""
    if eff == 0 and par == 0:
        return None, None, None
    if eff == 0xC:
        return None, None, min(64, par)
    if eff == 0xF:
        return (_cmd("A"), par, None) if par < 0x20 else (_cmd("T"), par, None)
    if eff == 0x8:
        return _cmd("X"), par // 2, None
    if eff in (0x1, 0x2):
        return _cmd(SIMPLE[eff]), min(par, 0xDF), None
    if eff == 0xA and par == 0:
        return None, None, None
    if eff == 0xE:
        x, y = par >> 4, par & 0xF
        m = {0x1: ("F", 0xF0 | y), 0x2: ("E", 0xF0 | y), 0x9: ("Q", y), 0xA: ("D", (y << 4) | 0xF),
             0xB: ("D", 0xF0 | y), 0xC: ("S", 0xC0 | y), 0xD: ("S", 0xD0 | y), 0x6: ("S", 0xB0 | y),
             0xE: ("S", 0xE0 | y)}
        if x in m:
            l, v = m[x]
            return _cmd(l), v, None
        return None, None, None
    if eff in SIMPLE:
        return _cmd(SIMPLE[eff]), par, None
    return None, None, None


def write_s3m(song, path):
    r = Renderer(song)
    nch = r.nch
    if nch > 16:
        raise SongError(".s3m: eksport do 16 kanałów PCM")
    ninst = max(song.instruments) if song.instruments else 0
    chunks, positions, sections, warn = _export.build(song, r.speed0, r.tempo0)
    if len(positions) > 254:
        raise SongError(".s3m: za dużo pozycji")
    orders = positions + [255]
    if len(orders) % 2:
        orders.append(255)

    # --- wzory (spakowane) ---
    pat_blobs = []
    for ch in chunks:
        b = bytearray()
        for row in ch:
            for c, cell in enumerate(row):
                what, data = 0, bytearray()
                note = None
                if cell.note is not None:
                    if cell.note == -1:
                        note = 254
                    else:
                        octv, semi = cell.note // 12 + 2, cell.note % 12
                        if not 0 <= octv <= 7:
                            raise SongError(".s3m: nuta poza oktawami 0..7")
                        note = (octv << 4) | semi
                if note is not None or cell.inst:
                    what |= 0x20
                    data += bytes([note if note is not None else 255, cell.inst & 0xFF])
                cmd, info, vov = _effect(cell.eff, cell.par)
                vol = cell.vol if cell.vol is not None else vov
                if vol is not None:
                    what |= 0x40
                    data += bytes([min(64, int(vol))])
                if cmd is not None:
                    what |= 0x80
                    data += bytes([cmd, info & 0xFF])
                if what:
                    b += bytes([what | c]) + data
            b += b"\0"
        pat_blobs.append(struct.pack("<H", len(b) + 2) + bytes(b))

    # --- układ pliku ---
    head_len = 0x60
    off = head_len + len(orders) + 2 * ninst + 2 * len(pat_blobs) + 32
    off = (off + 15) & ~15
    inst_off = []
    for _ in range(ninst):
        inst_off.append(off)
        off += 80
    pat_off = []
    for pb in pat_blobs:
        pat_off.append(off)
        off = (off + len(pb) + 15) & ~15
    smp_off = {}
    smp_data = {}
    for n in range(1, ninst + 1):
        smp = r.samples.get(n)
        if smp is None:
            continue
        if smp.bits == 16:
            d = (smp.data.astype(np.int32) + 32768).astype("<u2").tobytes()
        else:
            d = (smp.data.astype(np.int16) + 128).astype(np.uint8).tobytes()
        smp_off[n] = off
        smp_data[n] = d
        off = (off + len(d) + 15) & ~15

    buf = bytearray(off)
    title = song.head["title"].encode("ascii", "replace")[:27]
    # ST3: 0-7 = L1..L8, 8-15 = R1..R8; kanały muszą być unikalne
    used, fixed = set(), []
    for c in range(32):
        if c >= nch:
            fixed.append(255)
            continue
        want_right = r.pans[c] >= 0.5
        pool = list(range(8, 16)) + list(range(0, 8)) if want_right else list(range(0, 8)) + list(range(8, 16))
        v = next(x for x in pool if x not in used)
        used.add(v)
        fixed.append(v)
    struct.pack_into("<28sBBH", buf, 0, title, 0x1A, 16, 0)
    struct.pack_into("<HHHHHH", buf, 0x20, len(orders), ninst, len(pat_blobs), 0, 0x1320, 2)
    buf[0x2C:0x30] = b"SCRM"
    buf[0x30] = 64                              # global volume
    buf[0x31] = r.speed0
    buf[0x32] = r.tempo0
    buf[0x33] = 0x80 | 0x30                     # stereo, master 48
    buf[0x34] = 0
    buf[0x35] = 252                             # czytaj tablicę panoramy
    buf[0x40:0x60] = bytes(fixed)
    p = head_len
    buf[p:p + len(orders)] = bytes(orders)
    p += len(orders)
    for o in inst_off:
        struct.pack_into("<H", buf, p, o >> 4)
        p += 2
    for o in pat_off:
        struct.pack_into("<H", buf, p, o >> 4)
        p += 2
    for c in range(32):
        buf[p + c] = 0x20 | int(round(r.pans[c] * 15)) if c < nch else 0x08
    for i, o in enumerate(inst_off):
        n = i + 1
        smp = r.samples.get(n)
        if smp is None:
            struct.pack_into("<B12s", buf, o, 0, b"")
            buf[o + 0x4C:o + 0x50] = b"SCRS"
            continue
        seg = smp_off[n] >> 4
        length = len(smp.data)
        looped = smp.loop_len > 2
        flags = (1 if looped else 0) | (4 if smp.bits == 16 else 0)
        struct.pack_into("<B12sBHIIIBBBBI12s28s4s", buf, o, 1, smp.name.encode("ascii", "replace")[:12],
                         (seg >> 16) & 0xFF, seg & 0xFFFF, length,
                         smp.loop_start if looped else 0, smp.loop_start + smp.loop_len if looped else 0,
                         min(64, smp.volume), 0, 0, flags, int(round(smp.c2spd)), b"",
                         smp.name.encode("ascii", "replace")[:27], b"SCRS")
    for pb, o in zip(pat_blobs, pat_off):
        buf[o:o + len(pb)] = pb
    for n, d in smp_data.items():
        o = smp_off[n]
        buf[o:o + len(d)] = d
    with open(path, "wb") as f:
        f.write(buf)
    for w in warn[:12]:
        print("  uwaga:", w)
    for s, st, lp in sections:
        print(f"  sekcja {s}: pozycja {st}" + (f", pętla od {lp}" if lp is not None else ""))
    return sections
