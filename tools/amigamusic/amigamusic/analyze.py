"""Analiza offline (bez odsłuchu): LUFS (ITU-R BS.1770), true-peak, szew pętli, PNG,
kontrola harmonii symboliczna (nuty vs `chords:`) i audio (chroma vs akord)."""
import re, struct, zlib
import numpy as np

# ------------------------------------------------------------------ głośność
def _biquad_resp(b, a, w):
    z = np.exp(-1j * w)
    return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)


def _kweight(x, rate):
    """Filtr K z BS.1770 (półka +4 dB @1682 Hz + górnoprzepustowy 38 Hz), parametry jak w
    pyloudnorm, przeliczane dla dowolnej częstotliwości; stosowany jako |H| w dziedzinie FFT."""
    n = len(x)
    nfft = 1 << (n + 1024 - 1).bit_length()
    w = 2 * np.pi * np.fft.rfftfreq(nfft, 1 / rate) / rate
    G, Q, fc = 3.99984385397, 0.7071752369554193, 1681.9744509555319
    A = 10 ** (G / 40); w0 = 2 * np.pi * fc / rate; al = np.sin(w0) / (2 * Q); c = np.cos(w0)
    b1 = [A * ((A + 1) + (A - 1) * c + 2 * np.sqrt(A) * al), -2 * A * ((A - 1) + (A + 1) * c),
          A * ((A + 1) + (A - 1) * c - 2 * np.sqrt(A) * al)]
    a1 = [(A + 1) - (A - 1) * c + 2 * np.sqrt(A) * al, 2 * ((A - 1) - (A + 1) * c),
          (A + 1) - (A - 1) * c - 2 * np.sqrt(A) * al]
    Q2, fc2 = 0.5003270373253953, 38.13547087613982
    w0 = 2 * np.pi * fc2 / rate; al = np.sin(w0) / (2 * Q2); c = np.cos(w0)
    b2 = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    a2 = [1 + al, -2 * c, 1 - al]
    H = np.abs(_biquad_resp(b1, a1, w) * _biquad_resp(b2, a2, w))
    X = np.fft.rfft(x, nfft, axis=0)
    return np.fft.irfft(X * H[:, None], nfft, axis=0)[:n]


def lufs(x, rate):
    x = np.atleast_2d(x.T).T if x.ndim == 1 else x
    y = _kweight(x.astype(np.float64), rate)
    blk, hop = int(0.4 * rate), int(0.1 * rate)
    if len(y) < blk:
        ms = np.mean(y ** 2, axis=0).sum()
        return -0.691 + 10 * np.log10(ms + 1e-12)
    c = np.cumsum(np.concatenate([np.zeros((1, y.shape[1])), y ** 2]), axis=0)
    starts = np.arange(0, len(y) - blk + 1, hop)
    ms = ((c[starts + blk] - c[starts]) / blk).sum(axis=1)
    L = -0.691 + 10 * np.log10(ms + 1e-12)
    ms = ms[L > -70]
    if not len(ms):
        return -np.inf
    rel = -0.691 + 10 * np.log10(ms.mean()) - 10
    ms2 = ms[(-0.691 + 10 * np.log10(ms)) > rel]
    return float(-0.691 + 10 * np.log10(ms2.mean()))


def true_peak(x, os_=4):
    m = 0.0
    seg = 1 << 16
    for i in range(0, len(x), seg):
        s = x[max(0, i - 64):i + seg + 64]
        n = len(s)
        X = np.fft.rfft(s, axis=0)
        y = np.fft.irfft(X, n * os_, axis=0) * os_
        m = max(m, float(np.max(np.abs(y))))
    return m


# ------------------------------------------------------------------ szew pętli
def seam_check(x, rate, loop_off):
    """Porównuje przejście koniec->początek pętli z typowymi skokami w pliku.
    ratio = |skok na szwie| / 99,9 percentyl |różnic sąsiednich próbek|; rms_jump = zmiana RMS 10 ms (dB)."""
    loop = x[loop_off:]
    if len(loop) < rate:
        return dict(verdict="za krótka pętla")
    d = np.abs(np.diff(loop, axis=0)).max(axis=1)
    p999 = float(np.percentile(d, 99.9)) or 1e-9
    jump = float(np.abs(loop[0] - loop[-1]).max())
    w = int(0.01 * rate)
    r_end = np.sqrt(np.mean(loop[-w:] ** 2) + 1e-12)
    r_beg = np.sqrt(np.mean(loop[:w] ** 2) + 1e-12)
    rms_jump = float(20 * np.log10(r_beg / r_end))
    ratio = jump / p999
    ok = ratio < 1.0 and abs(rms_jump) < 9
    return dict(jump=round(jump, 4), p999=round(p999, 4), ratio=round(ratio, 3),
                rms_jump_db=round(rms_jump, 2), verdict="OK" if ok else "UWAGA")


# ------------------------------------------------------------------ PNG
def _png(path, img):
    h, w = img.shape[:2]
    raw = b"".join(b"\x00" + img[y].astype(np.uint8).tobytes() for y in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def plot_png(path, x, rate, marks_s=(), width=1200):
    """Górna połowa: przebieg L/R (min/max), dolna: spektrogram (log, 0-11 kHz). Czerwone linie = marks_s."""
    H1, H2 = 160, 200
    img = np.full((H1 + H2, width, 3), 16, np.uint8)
    n = len(x)
    cols = np.linspace(0, n, width + 1).astype(int)
    mono = x.mean(axis=1)
    for i in range(width):
        s = mono[cols[i]:max(cols[i + 1], cols[i] + 1)]
        lo, hi = s.min(), s.max()
        y0 = int((1 - (hi + 1) / 2) * (H1 - 1)); y1 = int((1 - (lo + 1) / 2) * (H1 - 1))
        img[max(0, y0):min(H1, y1 + 1), i] = (90, 200, 255)
    img[H1 // 2, :] = (60, 60, 60)
    nfft = 1024
    for i in range(width):
        c = cols[i]
        s = mono[c:c + nfft]
        if len(s) < nfft:
            s = np.pad(s, (0, nfft - len(s)))
        sp = np.abs(np.fft.rfft(s * np.hanning(nfft)))[: int(11000 / rate * nfft)]
        db = 20 * np.log10(sp + 1e-6)
        v = np.clip((db + 40) / 70, 0, 1)
        idx = np.linspace(0, len(v) - 1, H2).astype(int)[::-1]
        col = v[idx]
        img[H1:, i, 0] = (col * 255).astype(np.uint8)
        img[H1:, i, 1] = (col ** 2 * 200).astype(np.uint8)
        img[H1:, i, 2] = ((1 - col) * 60 + col * 40).astype(np.uint8)
    for m in marks_s:
        px = int(m * rate / n * width)
        if 0 <= px < width:
            img[:, px] = (255, 40, 40)
    _png(path, img)


# ------------------------------------------------------------------ harmonia
NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
QUAL = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10),
        "dim": (0, 3, 6), "dim7": (0, 3, 6, 9), "aug": (0, 4, 8), "sus4": (0, 5, 7), "sus2": (0, 2, 7),
        "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9), "add9": (0, 2, 4, 7), "9": (0, 2, 4, 7, 10),
        "m9": (0, 2, 3, 7, 10), "7sus4": (0, 5, 7, 10), "5": (0, 7), "m7b5": (0, 3, 6, 10)}
SCALES = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10, 11),
          "dorian": (0, 2, 3, 5, 7, 9, 10), "mixolydian": (0, 2, 4, 5, 7, 9, 10)}


def chord_pcs(name):
    """'Am7', 'F#dim', 'C/G', 'N' (bez akordu) -> zbiór klas wysokości lub None."""
    if name in ("N", "-", "x", "NC"):
        return None
    name = name.split("/")[0]
    m = re.match(r"^([A-G])([#b]?)(.*)$", name)
    if not m or m.group(3) not in QUAL:
        raise ValueError(f"nieznany akord '{name}' (obsługiwane: {', '.join(k or 'dur' for k in QUAL)})")
    root = (NOTE_PC[m.group(1)] + {"#": 1, "b": -1, "": 0}[m.group(2)]) % 12
    return {(root + i) % 12 for i in QUAL[m.group(3)]}, root


def key_pcs(key):
    parts = key.split()
    root = NOTE_PC[parts[0][0]] + (1 if "#" in parts[0] else -1 if "b" in parts[0][1:] else 0)
    sc = SCALES.get(parts[1] if len(parts) > 1 else "major", SCALES["major"])
    return {(root + i) % 12 for i in sc}


def _bar_chords(pat):
    """Lista akordów na każdy wiersz (16 wierszy na takt; 'C,G' = pół na pół)."""
    rows = pat["rows"]
    out = [None] * rows
    for b, tok in enumerate(pat["chords"]):
        parts = tok.split(",")
        span = 16 // len(parts)
        for j, p in enumerate(parts):
            for r in range(b * 16 + j * span, min(rows, b * 16 + (j + 1) * span)):
                out[r] = p
    return out


def symbolic_check(song, drum_presets, verbose=False):
    """Dla każdego patternu: nuty na mocnych częściach taktu (wiersze 0,4,8,12) w kanałach
    melodycznych muszą należeć do akordu; reszta – do skali (z alteracjami akordu).
    Zwraca (raport tekstowy, statystyki)."""
    inst_drum = {n for n, i in song.instruments.items() if i["preset"] in drum_presets}
    kp = key_pcs(song.head["key"])
    lines = []
    tot_strong = ok_strong = tot = out_key = 0
    for pname, pat in song.patterns.items():
        if not pat["chords"]:
            continue
        chords = _bar_chords(pat)
        bad = []
        for c, cells in pat["ch"].items():
            cur_inst = 0
            for r, cell in enumerate(cells):
                if cell.inst:
                    cur_inst = cell.inst
                if cell.note is None or cell.note < 0 or cur_inst in inst_drum:
                    continue
                ch = chords[r]
                if ch is None or chord_pcs(ch) is None:
                    continue
                pcs, _ = chord_pcs(ch)
                notes = [cell.note % 12]
                if cell.eff == 0 and cell.par:
                    notes += [(cell.note + (cell.par >> 4)) % 12, (cell.note + (cell.par & 15)) % 12]
                allowed = kp | pcs
                for pc in notes:
                    tot += 1
                    if pc not in allowed:
                        out_key += 1
                        bad.append(f"{pname} ch{c+1} w{r}: {_pcn(pc)} poza tonacją/akordem {ch}")
                if r % 4 == 0:
                    tot_strong += 1
                    if all(pc in pcs for pc in notes):
                        ok_strong += 1
                    elif r % 16 == 0 or r % 16 == 8:
                        bad.append(f"{pname} ch{c+1} w{r}: {_pcn(notes[0])} nie w akordzie {ch} (mocna część)")
        if bad:
            lines += bad if verbose else bad[:6] + ([f"  … +{len(bad)-6}"] if len(bad) > 6 else [])
    st = dict(strong_in_chord=round(ok_strong / max(tot_strong, 1), 3),
              out_of_key=round(out_key / max(tot, 1), 3), notes=tot)
    return lines, st


def _pcn(pc):
    return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][pc]


def chroma(x, rate):
    mono = x.mean(axis=1) if x.ndim == 2 else x
    n = 8192
    acc = np.zeros(12)
    f = np.fft.rfftfreq(n, 1 / rate)
    sel = (f > 80) & (f < 2000)
    midi = 69 + 12 * np.log2(f[sel] / 440.0)
    pcs = np.round(midi).astype(int) % 12
    for i in range(0, max(1, len(mono) - n), n // 2):
        s = mono[i:i + n]
        if len(s) < n:
            s = np.pad(s, (0, n - len(s)))
        sp = np.abs(np.fft.rfft(s * np.hanning(n)))[sel] ** 2
        acc += np.bincount(pcs, sp, 12)
    return acc / (acc.sum() + 1e-12)


def audio_chord_check(song, renderer, pattern_names, drum_presets):
    """Renderuje każdy pattern osobno BEZ perkusji i sprawdza, czy chroma taktu pasuje do akordu
    (akord zamierzony w top-3 spośród 24 dur/moll + 7, korelacja z szablonem)."""
    inst_drum = {n for n, i in song.instruments.items() if i["preset"] in drum_presets}
    templates = {}
    for r in range(12):
        for q in ("", "m", "7"):
            nm = _pcn(r) + q
            v = np.zeros(12)
            for i in QUAL[q]:
                v[(r + i) % 12] = 1
            v[r] += 0.5
            templates[nm] = v / np.linalg.norm(v)
    # instrument „wchodzący” do każdego kanału patternu (z kolejności sekcji) – wzór renderowany
    # osobno musi wiedzieć, jaki instrument grał w poprzednim
    entry = {}
    for on, (intro, loop) in song.orders.items():
        cur = {}
        for pn in intro + (loop or []) * 2:
            for c, cells in song.patterns[pn]["ch"].items():
                entry.setdefault((pn, c), cur.get(c, 0))
                for cell in cells:
                    if cell.inst:
                        cur[c] = cell.inst
    res = []
    for pname in pattern_names:
        pat = song.patterns[pname]
        if not pat["chords"]:
            continue
        # wycisz perkusję: tymczasowa kopia patternu bez nut perkusyjnych
        import copy
        p2 = copy.deepcopy(pat)
        for c, cells in p2["ch"].items():
            first = next((x for x in cells if x.note is not None and x.note >= 0 or x.inst), None)
            if first is not None and not first.inst and entry.get((pname, c)):
                first.inst = entry[(pname, c)]
            cur = 0
            for cell in cells:
                if cell.inst:
                    cur = cell.inst
                if cur in inst_drum:
                    cell.note = None; cell.inst = 0
        sp, tp = renderer.speed0, renderer.tempo0
        for on, (intro, loop) in song.orders.items():
            if pname in intro + (loop or []):
                oo = song.order_opts.get(on, {})
                sp, tp = int(oo.get("speed", sp)), int(oo.get("tempo", tp))
                break
        song.patterns["__chk"] = p2
        ch, marks = renderer.play(["__chk"], speed=sp, tempo=tp)
        del song.patterns["__chk"]
        x = ch.sum(axis=0)
        bar_n = int(16 * sp * renderer.rate * 2.5 / tp)
        for b, tok in enumerate(pat["chords"]):
            nm = tok.split(",")[0]
            cp = chord_pcs(nm)
            if cp is None:
                continue
            pcs, root = cp
            # takt z jedną klasą wysokości (np. blip UI) nie definiuje akordu – pomijamy
            heard = set()
            for cc in p2["ch"].values():
                for cell in cc[b * 16:(b + 1) * 16]:
                    if cell.note is not None and cell.note >= 0:
                        heard.add(cell.note % 12)
                        if cell.eff == 0 and cell.par:
                            heard |= {(cell.note + (cell.par >> 4)) % 12, (cell.note + (cell.par & 15)) % 12}
            if len(heard) < 2:
                continue
            seg = x[b * bar_n:(b + 1) * bar_n] if "," not in tok else x[b * bar_n:b * bar_n + bar_n // 2]
            c = chroma(seg[:, None], renderer.rate)
            c = c / (np.linalg.norm(c) + 1e-12)
            tv = np.zeros(12)
            for i in pcs:
                tv[i] = 1
            tv[root] += 0.5
            tv /= np.linalg.norm(tv)
            score = float(c @ tv)
            ranking = sorted(templates.items(), key=lambda kv: -(c @ kv[1]))
            top = [k for k, _ in ranking[:3]]
            match = any(set(np.nonzero(templates[k] > 0)[0]) <= pcs | {root} or k == nm for k in top)
            res.append(dict(pattern=pname, bar=b + 1, chord=tok, score=round(score, 2), top3=top, ok=bool(match or score > 0.8)))
    return res
