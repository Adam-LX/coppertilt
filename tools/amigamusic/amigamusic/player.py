"""Odtwarzacz .song z semantyką efektów ProTrackera (tick po ticku).

Obsługiwane efekty (kolumna efektu, jak w PT):
  0xy arpeggio   1xx porta w górę   2xx porta w dół   3xx tone-porta   4xy vibrato
  5xy 3+Axy      6xy 4+Axy          8xx panorama (00 lewo .. FF prawo; rozszerzenie)
  9xx offset sampla (xx*256)        Axy przesuw głośności  Cxx głośność  Dxx przerwa wzoru
  E1x/E2x drobna porta  E9x retrigger  EAx/EBx drobna głośność  ECx cięcie  EDx opóźnienie
  Fxx speed (<32) / tempo (>=32).  Bxx jest ignorowane – pętlą rządzi [order].
"""
import numpy as np
from . import paula
from .paula import PAL_CLOCK
from .instruments import make, STYLES
from .songtext import SongError

SINE = [int(round(255 * np.sin(np.pi * i / 32))) for i in range(32)]   # tabela vibrato PT


def period_for(idx, sample, pt_mode):
    """idx: półtony od C-0 (PT C-1 = 12). Zwraca okres w jednostkach Pauli."""
    if pt_mode:
        k = idx - 12
        if not 0 <= k < 36:
            raise SongError(f"nuta {idx} poza zakresem PT C-1..B-3 (użyj profilu 'unreal' albo zmień oktawę)")
        return paula.period_of(k, sample.finetune if sample else 0)
    return 428.0 * 2 ** (-(idx - 24) / 12.0)


class Chan:
    def __init__(self, pan):
        self.smp = None; self.inst = 0
        self.pos = 0.0; self.on = False
        self.period = 428.0; self.target = 428.0; self.note = 24
        self.vol = 0; self.prev_vol = 0.0
        self.pan = pan
        self.porta = 0; self.vib_speed = 0; self.vib_depth = 0; self.vib_pos = 0
        self.offset = 0; self.volslide = 0
        self.arp = 0; self.eff = 0; self.par = 0
        self.delay_cell = None; self.cut_tick = -1; self.retrig = 0
        self.out_period = 428.0


class Renderer:
    def __init__(self, song):
        self.song = song
        h = song.head
        style = STYLES.get(h["profile"])
        if style is None:
            raise SongError(f"nieznany profil '{h['profile']}'. Dostępne: {', '.join(STYLES)}")
        self.style = style
        self.pt_mode = style.get("pt", True)
        self.nch = h["channels"]
        if self.pt_mode and self.nch != 4:
            raise SongError("profil Amiga/PT = dokładnie 4 kanały (channels 4). Więcej kanałów: profil 'unreal'.")
        self.rate = h["rate"]
        self.speed0 = h["speed"] or style["speed"]
        self.tempo0 = h["tempo"] or style["tempo"]
        self.stereo = style["stereo"] if h["stereo"] is None else h["stereo"]
        self.filter = h["filter"] or style["filter"]
        self.interp = h["interp"] or style.get("interp", "zoh")
        self.reverb = h["reverb"] or style.get("reverb", 0.0)
        self.delay = h["delay"] or style.get("delay")
        self.pans = self._pans(h["pan"])
        self.sends = [float(x) for x in h["send"]] if h["send"] else [1.0] * self.nch
        if len(self.sends) < self.nch:
            self.sends += [self.sends[-1]] * (self.nch - len(self.sends))
        self.samples = {}
        for num, ins in song.instruments.items():
            smp = make(ins["preset"], **ins["opts"])
            self.samples[num] = smp

    def _pans(self, spec):
        n = self.nch
        if not spec:
            if self.pt_mode:
                return [0.0, 1.0, 1.0, 0.0]
            base = [0.2, 0.8, 0.35, 0.65, 0.5, 0.1, 0.9, 0.5]
            return [base[i % len(base)] for i in range(n)]
        out = []
        for x in spec:
            out.append({"L": 0.0, "R": 1.0, "C": 0.5}.get(x.upper(), None) if x.upper() in "LRC" else float(x))
        while len(out) < n:
            out.append(0.5)
        return out[:n]

    # ------------------------------------------------------------------ odtwarzanie
    def play(self, positions, extra_tail=0.0, speed=None, tempo=None):
        """positions: lista nazw patternów. Zwraca (chans[nch, N] float32, marks)
        marks: lista (pozycja, wiersz, sample_index) na początku każdego wiersza."""
        song = self.song
        chans = [Chan(self.pans[c]) for c in range(self.nch)]
        self._chans = chans
        speed, tempo = speed or self.speed0, tempo or self.tempo0
        bufs = [[] for _ in range(self.nch)]
        marks = []
        t = 0
        frac = 0.0
        pi = 0
        row0 = 0
        self.tempo_log = set()
        while pi < len(positions):
            pat = song.patterns[positions[pi]]
            brk = None
            r = row0
            row0 = 0
            while r < pat["rows"]:
                marks.append((pi, r, t))
                cells = [pat["ch"][c][r] for c in range(self.nch)]
                # Fxx najpierw (wpływa na długość tego wiersza)
                for cell in cells:
                    if cell.eff == 0xF and cell.par:
                        if cell.par < 32:
                            speed = cell.par
                        else:
                            tempo = cell.par
                    if cell.eff == 0xD:
                        brk = (cell.par >> 4) * 10 + (cell.par & 15)
                self.tempo_log.add((speed, tempo))
                for c, cell in enumerate(cells):
                    self._row(chans[c], cell)
                for tick in range(speed):
                    exact = self.rate * 2.5 / tempo + frac
                    n = int(exact)
                    frac = exact - n
                    for c in range(self.nch):
                        ch = chans[c]
                        self._tick(ch, tick, pat["ch"][c][r])
                        bufs[c].append(self._render(ch, n))
                    t += n
                r += 1
                if brk is not None:
                    row0 = brk
                    break
            pi += 1
        # ogon (wybrzmienie) – bez nowych nut
        tail = int(extra_tail * self.rate)
        if tail:
            for c in range(self.nch):
                bufs[c].append(self._render(chans[c], tail))
        out = np.stack([np.concatenate(b) if b else np.zeros(0, np.float32) for b in bufs])
        return out, marks

    def _row(self, ch, cell):
        ch.cut_tick = -1
        ch.delay_cell = None
        ch.retrig = 0
        e, p = cell.eff, cell.par
        if e == 0xE and (p >> 4) == 0xD and (p & 15):
            ch.delay_cell = cell
            ch.eff, ch.par = e, p
            return
        self._trigger(ch, cell)

    def _trigger(self, ch, cell):
        e, p = cell.eff, cell.par
        if cell.inst:
            smp = self.samples[cell.inst]
            ch.inst = cell.inst
            ch.vol = smp.volume
            ch.next_smp = smp
            if ch.smp is None:
                ch.smp = smp
        if cell.note is not None:
            if cell.note == -1:
                ch.vol = 0
            elif e in (3, 5) and ch.on:
                ch.target = period_for(cell.note, ch.smp, self.pt_mode)
                ch.note = cell.note
            else:
                if getattr(ch, "next_smp", None) is not None:
                    ch.smp = ch.next_smp
                if ch.smp is None:
                    raise SongError("nuta bez instrumentu na początku kanału – dodaj @instrument")
                ch.period = ch.target = period_for(cell.note, ch.smp, self.pt_mode)
                ch.note = cell.note
                ch.pos = 0.0
                ch.on = True
                ch.vib_pos = 0
                ch.prev_vol = 0.0          # mikro-narastanie (bez trzasków)
                if e == 9:
                    if p:
                        ch.offset = p
                    ch.pos = float(ch.offset * 256)
                    if not ch.smp.looped and ch.pos >= len(ch.smp.f):
                        ch.on = False
        if cell.vol is not None:
            ch.vol = cell.vol
        ch.eff, ch.par = e, p
        if e == 0xC:
            ch.vol = min(p, 64)
        elif e == 8:
            ch.pan = p / 255.0
        elif e == 3 and p:
            ch.porta = p
        elif e == 4:
            if p >> 4:
                ch.vib_speed = p >> 4
            if p & 15:
                ch.vib_depth = p & 15
        elif e == 0xE:
            x, y = p >> 4, p & 15
            if x == 1:
                ch.period = max(ch.period - y, self._pmin())
            elif x == 2:
                ch.period = min(ch.period + y, self._pmax())
            elif x == 0xA:
                ch.vol = min(64, ch.vol + y)
            elif x == 0xB:
                ch.vol = max(0, ch.vol - y)
            elif x == 0xC:
                ch.cut_tick = y
                if y == 0:
                    ch.vol = 0
            elif x == 9:
                ch.retrig = y

    def _pmin(self):
        return 113.0 if self.pt_mode else 14.0

    def _pmax(self):
        return 856.0 if self.pt_mode else 6848.0

    def _tick(self, ch, tick, cell):
        e, p = ch.eff, ch.par
        ch.out_period = ch.period
        if ch.delay_cell is not None and tick == (ch.delay_cell.par & 15):
            dc = ch.delay_cell
            ch.delay_cell = None
            self._trigger(ch, dc)
            ch.out_period = ch.period
            return
        if ch.cut_tick == tick and tick > 0:
            ch.vol = 0
        if ch.retrig and tick and tick % ch.retrig == 0:
            ch.pos = 0.0
            ch.on = True
        if e == 0 and p:
            k = tick % 3
            semis = 0 if k == 0 else (p >> 4 if k == 1 else p & 15)
            ch.out_period = ch.period * 2 ** (-semis / 12)
            return
        if tick == 0:
            return
        if e == 1:
            ch.period = max(ch.period - p, self._pmin())
        elif e == 2:
            ch.period = min(ch.period + p, self._pmax())
        elif e in (3, 5):
            sp = ch.porta
            if ch.period < ch.target:
                ch.period = min(ch.period + sp, ch.target)
            elif ch.period > ch.target:
                ch.period = max(ch.period - sp, ch.target)
        if e in (4, 6):
            d = SINE[ch.vib_pos & 31] * ch.vib_depth / 128.0
            if ch.vib_pos & 32:
                d = -d
            ch.out_period = ch.period + d
            ch.vib_pos = (ch.vib_pos + ch.vib_speed) & 63
        else:
            ch.out_period = ch.period
        if e in (5, 6, 0xA):
            x, y = p >> 4, p & 15
            if x:
                ch.vol = min(64, ch.vol + x)
            else:
                ch.vol = max(0, ch.vol - y)

    def _render(self, ch, n):
        out = np.zeros(n, np.float32)
        if not ch.on or ch.smp is None or n <= 0:
            ch.prev_vol = ch.vol
            return out
        rate = PAL_CLOCK / max(ch.out_period, 1.0) * (ch.smp.c2spd / 8287.0)
        step = rate / self.rate
        y, ch.pos, ch.on = ch.smp.render(ch.pos, step, n, self.interp)
        v1 = ch.vol / 64.0
        v0 = ch.prev_vol / 64.0 if ch.prev_vol is not None else v1
        if v0 != v1:
            r = min(n, 48)
            env = np.full(n, v1, np.float32)
            env[:r] = np.linspace(v0, v1, r, endpoint=False)
            y = y * env
        else:
            y = y * v1
        ch.prev_vol = ch.vol
        return y.astype(np.float32)

    # ------------------------------------------------------------------ miks i efekty
    def mix(self, chans, pans=None):
        pans = pans or self.pans
        n = chans.shape[1]
        if self.pt_mode:
            st = mix_pt(chans, self.stereo)
        else:
            st = np.zeros((n, 2), np.float32)
            for c in range(self.nch):
                pn = 0.5 + (pans[c] - 0.5) * self.stereo
                st[:, 0] += chans[c] * np.cos(pn * np.pi / 2)
                st[:, 1] += chans[c] * np.sin(pn * np.pi / 2)
            st *= 0.5
        st = paula.amiga_filter(st, self.rate, self.filter)
        if self.reverb or self.delay:
            wet_in = np.zeros((n, 2), np.float32)
            for c in range(self.nch):
                pn = pans[c]
                wet_in[:, 0] += chans[c] * self.sends[c] * (1 - pn)
                wet_in[:, 1] += chans[c] * self.sends[c] * pn
            wet_in *= 0.5
            wet = np.zeros_like(st)
            if self.delay:
                wet += echo(wet_in, self.rate, self.delay, self.speed0, self.tempo0)
            if self.reverb:
                wet += self.reverb * reverb(wet_in, self.rate)
            st = st + wet
        return st


def mix_pt(chans, stereo):
    return paula.mix_lrrl([chans[i] for i in range(4)], stereo) * 0.5


def echo(x, rate, spec, speed, tempo):
    """spec: 'wiersze sprzężenie poziom', np. '3 0.4 0.3' – echo ping-pong zsynchronizowane z wierszami."""
    parts = str(spec).split()
    rows = float(parts[0]); fb = float(parts[1]) if len(parts) > 1 else 0.4
    lvl = float(parts[2]) if len(parts) > 2 else 0.3
    d = int(rows * speed * rate * 2.5 / tempo)
    y = np.zeros_like(x)
    buf = x.copy()
    # blokowo: y[n] = x[n-d] + fb*y[n-d] (z zamianą kanałów = ping-pong)
    n = len(x)
    out = np.zeros((n + d, 2), np.float32)
    out[d:d + n] += x * lvl
    for s in range(d, n, d):
        e = min(s + d, n)
        out[s + d:e + d] += out[s:e][:, ::-1] * fb
    return out[:n]


def reverb(x, rate):
    """Lekki pogłos (Schroeder/Freeverb-like): 4 grzebienie + 2 all-pass na kanał, liczone blokowo."""
    combs = [1557, 1617, 1491, 1422]
    aps = [225, 556]
    k = rate / 44100.0
    out = np.zeros_like(x)
    for c in range(2):
        sig = x[:, c].astype(np.float32)
        acc = np.zeros(len(sig), np.float32)
        for i, dl in enumerate(combs):
            d = int((dl + 23 * c) * k)
            g = 0.80
            y = sig.copy()
            for s in range(d, len(sig), d):
                e = min(s + d, len(sig))
                y[s:e] += g * y[s - d:e - d]
            acc += y * 0.25
        for dl in aps:
            d = int(dl * k)
            g = 0.5
            y = np.zeros_like(acc)
            buf = acc.copy()
            # all-pass: y[n] = -g*x[n] + x[n-d] + g*y[n-d]
            y[:d] = -g * buf[:d]
            for s in range(d, len(buf), d):
                e = min(s + d, len(buf))
                y[s:e] = -g * buf[s:e] + buf[s - d:e - d] + g * y[s - d:e - d]
            acc = y
        # łagodne tłumienie wysokich w pogłosie
        out[:, c] = acc
    return paula.amiga_filter(out, rate, "a500") * 0.6
