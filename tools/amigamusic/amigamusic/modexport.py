"""Eksport piosenki (profil 4-kanałowy, tryb PT) do ProTracker .mod (sygnatura M.K.).

    python3 -m amigamusic render SONG --mod out.mod

Ograniczenia formatu: 4 kanały, nuty C-1..B-3, 31 sampli 8-bit, kolumna głośności nie istnieje
(wpisujemy ją jako Cxx, gdy w komórce nie ma innego efektu). Efekty miksu (pogłos, echo, filtr
„a500”) nie są częścią .mod – to ustawienia odtwarzacza.
"""
import struct

import numpy as np

from .paula import PERIODS
from .player import Renderer
from .songtext import SongError
from . import _export


def _cell_bytes(cell, warn, where):
    period, eff, par = 0, cell.eff & 0xF, cell.par & 0xFF
    if cell.note is not None and cell.note >= 0:
        i = cell.note - 12
        if not 0 <= i < 36:
            raise SongError(f"{where}: nuta poza zakresem .mod (C-1..B-3)")
        period = PERIODS[i]
    if cell.note == -1:                      # cięcie nuty -> C00
        if eff or par:
            warn.append(f"{where}: cięcie nuty i efekt w jednej komórce – zostawiono efekt")
        else:
            eff, par = 0xC, 0
    if cell.vol is not None:
        if not eff and not par:
            eff, par = 0xC, min(64, int(cell.vol))
        else:
            warn.append(f"{where}: głośność v{cell.vol} i efekt {eff:X}{par:02X} – .mod ma jedną kolumnę, zostawiono efekt")
    inst = cell.inst & 0x1F
    return bytes([(inst & 0x10) | (period >> 8), period & 0xFF, ((inst & 0xF) << 4) | eff, par])


def write_mod(song, path):
    r = Renderer(song)
    if not r.pt_mode or r.nch != 4:
        raise SongError("eksport .mod tylko dla profili 4-kanałowych PT; dla 'unreal' użyj --s3m")
    if any(n > 31 for n in song.instruments):
        raise SongError(".mod ma maks. 31 sampli")
    chunks, positions, sections, warn = _export.build(song, r.speed0, r.tempo0)
    # .mod nie ma kolumny głośności: komórka z nutą+instrumentem+głośnością+efektem dostaje
    # wariant sampla z domyślną głośnością = vNN (sztuczka znana z PT: ten sam sampel w kilku slotach)
    samples = dict(r.samples)
    variants = {}
    free = [n for n in range(1, 32) if n not in samples]
    for ch in chunks:
        for row in ch:
            for cell in row:
                if cell.vol is not None and (cell.eff or cell.par) and cell.note is not None and cell.note >= 0:
                    base = cell.inst or None
                    if base is None:
                        continue
                    key = (base, int(cell.vol))
                    if key not in variants and free:
                        import copy as _c
                        v = _c.copy(samples[base])
                        v.volume = min(64, int(cell.vol))
                        variants[key] = free.pop(0)
                        samples[variants[key]] = v
                    if key in variants:
                        cell.inst = variants[key]
                        cell.vol = None
    r.samples = samples
    if len(positions) > 128:
        raise SongError(f".mod: {len(positions)} pozycji > 128")
    out = bytearray(song.head["title"].encode("ascii", "replace")[:20].ljust(20, b"\0"))
    for n in range(1, 32):
        smp = r.samples.get(n)
        if smp is None:
            out += b"\0" * 22 + struct.pack(">HBBHH", 0, 0, 0, 0, 1)
            continue
        if smp.bits != 8:
            raise SongError(f"sampel {n} jest 16-bit – .mod obsługuje tylko 8-bit")
        ln = min(len(smp.data), 0x1FFFE) // 2
        if smp.loop_len > 2:
            ls, ll = smp.loop_start // 2, smp.loop_len // 2
        else:
            ls, ll = 0, 1
        out += smp.name.encode("ascii", "replace")[:22].ljust(22, b"\0")
        out += struct.pack(">HBBHH", ln, smp.finetune & 0xF, min(64, smp.volume), ls, ll)
    out += bytes([len(positions), 127])
    out += bytes(positions + [0] * (128 - len(positions)))
    out += b"M.K."
    for ci, ch in enumerate(chunks):
        for ri, row in enumerate(ch):
            for c, cell in enumerate(row):
                out += _cell_bytes(cell, warn, f"wzór {ci} wiersz {ri} kanał {c + 1}")
    for n in range(1, 32):
        smp = r.samples.get(n)
        if smp is not None:
            d = smp.data[: min(len(smp.data), 0x1FFFE)].astype(np.int8)
            d = d.copy()
            if smp.loop_len <= 2 and len(d) >= 2:
                d[:2] = 0                    # konwencja PT: pierwsze 2 bajty = cisza dla one-shotów
            out += d.tobytes()
    with open(path, "wb") as f:
        f.write(out)
    for w in warn[:12]:
        print("  uwaga:", w)
    if len(warn) > 12:
        print(f"  ... i {len(warn) - 12} innych uwag")
    for s, st, lp in sections:
        print(f"  sekcja {s}: pozycja {st}" + (f", pętla od {lp}" if lp is not None else ""))
    return sections
