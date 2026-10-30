"""Wspólne przygotowanie danych dla eksportu do formatów trackerowych (.mod / .s3m).

Plik piosenki ma wzory o dowolnej długości i nazwane sekcje (`[order X]`). Formaty trackerowe
mają wzory po 64 wiersze i jedną listę kolejności. Tutaj:
  * wzory dłuższe niż 64 wiersze dzielimy na kawałki po 64,
  * krótsze kończymy efektem Dxx (pattern break) w ostatnim wierszu,
  * sekcje kładziemy po kolei na liście pozycji; ostatni wzór pętli dostaje Bxx (skok do początku
    pętli tej sekcji), więc odtwarzacz zapętla PIERWSZĄ sekcję tak jak gra; pozostałe sekcje są
    dostępne od swoich pozycji (wypisanych w raporcie),
  * na początku każdej sekcji wstawiamy Fxx (speed) i Fxx (tempo) w wolnych kolumnach efektu.
"""
import copy

from .songtext import Cell


def _free_slot(row, prefer=None):
    order = list(range(len(row)))
    if prefer is not None:
        order.remove(prefer)
        order.insert(0, prefer)
    for strict in (True, False):
        for c in order:
            x = row[c]
            if not x.eff and not x.par and (not strict or (x.vol is None and x.note != -1)):
                return c
    return None


def build(song, speed0, tempo0):
    """Zwraca (chunks, positions, sections, warnings).
    chunks: lista wzorów 64-wierszowych, każdy = lista 64 wierszy, wiersz = lista Cell (nch).
    positions: lista indeksów chunków.  sections: [(nazwa, pozycja_startu, pozycja_pętli|None)]."""
    nch = song.head["channels"]
    chunks, positions, sections, warn = [], [], [], []

    def add_pattern(pname):
        pat = song.patterns[pname]
        rows = pat["rows"]
        grid = [[copy.copy(pat["ch"][c][r]) for c in range(nch)] for r in range(rows)]
        idxs = []
        for start in range(0, rows, 64):
            part = grid[start:start + 64]
            n = len(part)
            part += [[Cell() for _ in range(nch)] for _ in range(64 - n)]
            if n < 64:
                c = _free_slot(part[n - 1], prefer=nch - 1)
                if c is None:
                    warn.append(f"{pname}: brak wolnej kolumny efektu na Dxx (wiersz {start + n - 1}) – nadpisano kanał {nch}")
                    c = nch - 1
                part[n - 1][c].eff, part[n - 1][c].par = 0xD, 0
            chunks.append(part)
            idxs.append(len(chunks) - 1)
        return idxs

    for sname in song.order_names:
        intro, loop = song.orders[sname]
        oo = song.order_opts.get(sname, {})
        speed, tempo = int(oo.get("speed", speed0)), int(oo.get("tempo", tempo0))
        start = len(positions)
        seq = []
        for p in intro:
            seq += add_pattern(p)
        loop_pos = None
        if loop:
            loop_pos = start + len(seq)
            for p in loop:
                seq += add_pattern(p)
        # speed/tempo na początku sekcji
        first = chunks[seq[0]]
        first[0] = [copy.copy(x) for x in first[0]]
        for val in (speed, tempo):
            c = _free_slot(first[0])
            if c is None:
                warn.append(f"{sname}: brak miejsca na Fxx w pierwszym wierszu")
                break
            first[0][c].eff, first[0][c].par = 0xF, val
        # skok pętli
        if loop:
            last = chunks[seq[-1]]
            # znajdź ostatni wiersz grany (tam gdzie Dxx, albo 63)
            end = 63
            for r in range(64):
                if any(x.eff == 0xD for x in last[r]):
                    end = r
                    break
            c = next((k for k in range(nch) if last[end][k].eff == 0xD), None)
            if c is None:
                c = _free_slot(last[end], prefer=nch - 1)
            if c is None:
                warn.append(f"{sname}: brak miejsca na Bxx – nadpisano kanał {nch}")
                c = nch - 1
            last[end][c].eff, last[end][c].par = 0xB, loop_pos & 0xFF
        positions += seq
        sections.append((sname, start, loop_pos))
    return chunks, positions, sections, warn
