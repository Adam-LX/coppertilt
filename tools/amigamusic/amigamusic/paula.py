"""Paula (Amiga) – okresy ProTrackera, generowanie dźwięku kanału, miks i filtry."""
import numpy as np

PAL_CLOCK = 3546895.0          # Hz, zegar Pauli (PAL) używany przez PT
NOTE_NAMES = ["C-", "C#", "D-", "D#", "E-", "F-", "F#", "G-", "G#", "A-", "A#", "B-"]

# Oryginalna tabela okresów PT dla finetune 0, oktawy 1..3 (C-1 .. B-3)
PERIODS = [856, 808, 762, 720, 678, 640, 604, 570, 538, 508, 480, 453,
           428, 404, 381, 360, 339, 320, 302, 285, 269, 254, 240, 226,
           214, 202, 190, 180, 170, 160, 151, 143, 135, 127, 120, 113]
PERIOD_MIN, PERIOD_MAX = 113, 856


def note_index(name):
    """'C-2' -> 12 (indeks w PERIODS). Zwraca None dla pustej nuty."""
    name = name.strip().upper()
    if name in ("", "---", "..."):
        return None
    if len(name) == 2:                       # 'C2' -> 'C-2'
        name = name[0] + "-" + name[1]
    key, octv = name[:2], int(name[2])
    if key not in NOTE_NAMES:
        raise ValueError(f"nieznana nuta: {name}")
    idx = (octv - 1) * 12 + NOTE_NAMES.index(key)
    if not 0 <= idx < 36:
        raise ValueError(f"nuta poza zakresem PT (C-1..B-3): {name}")
    return idx


def note_name(idx):
    return NOTE_NAMES[idx % 12] + str(idx // 12 + 1)


def period_of(idx, finetune=0):
    p = PERIODS[idx]
    if finetune:
        p = p * 2 ** (-finetune / (12 * 8))
    return float(p)


def period_to_index(period):
    """Najbliższy indeks nuty dla okresu (eksport .mod)."""
    return int(np.argmin([abs(p - period) for p in PERIODS]))


def rate_of(period):
    return PAL_CLOCK / max(period, 1)


class Sample:
    """Sampel PCM. bits=8: int8 (PT/Paula). bits=16: int16 (profil 'unreal', eksport S3M).
    Pętla w próbkach (loop_len <= 2 => brak pętli). c2spd = częstotliwość odtwarzania nuty C-2
    (PT: 8287 Hz; sample HQ mają więcej próbek na okres i proporcjonalnie wyższy c2spd)."""

    def __init__(self, name, data, volume=64, loop_start=0, loop_len=0, finetune=0,
                 bits=8, c2spd=8287.0):
        d = np.asarray(data)
        self.bits = bits
        if bits == 8 and d.dtype != np.int8:
            d = np.clip(np.round(d), -128, 127).astype(np.int8)
        if bits == 16 and d.dtype != np.int16:
            d = np.clip(np.round(d), -32768, 32767).astype(np.int16)
        if len(d) % 2:
            d = np.concatenate([d, np.zeros(1, d.dtype)])
        self.name = name[:22]
        self.data = d
        self.f = d.astype(np.float32) / (128.0 if bits == 8 else 32768.0)
        self.volume = int(volume)
        self.loop_start = int(loop_start) & ~1
        self.loop_len = int(loop_len) & ~1
        if self.loop_len > 2 and self.loop_start + self.loop_len > len(d):
            self.loop_len = len(d) - self.loop_start
        self.finetune = int(finetune)
        self.c2spd = float(c2spd)
        # bufor z „dobiegiem” dla interpolacji liniowej przez punkt pętli
        if self.looped:
            ext = self.f[self.loop_start:self.loop_start + 1]
        else:
            ext = np.zeros(1, np.float32)
        self._fx = np.concatenate([self.f, ext])

    @property
    def looped(self):
        return self.loop_len > 2

    def render(self, pos, step, n, interp="zoh"):
        """Zwraca (wyjście[n], nowa_pozycja, czy_gra).
        interp='zoh' – zero-order hold (aliasing jak Paula), 'linear' – czystsze (profil unreal)."""
        if n <= 0:
            return np.zeros(0, np.float32), pos, True
        p = pos + step * np.arange(n, dtype=np.float64)
        end = len(self.f)
        playing = True
        if self.looped:
            ls, ll = self.loop_start, self.loop_len
            le = ls + ll
            m = p >= le
            if m.any():
                p[m] = ls + np.mod(p[m] - ls, ll)
            newpos = pos + step * n
            if newpos >= le:
                newpos = ls + (newpos - ls) % ll
            valid = None
        else:
            valid = p < end
            newpos = pos + step * n
            playing = newpos < end
            p = np.where(valid, p, 0)
        idx = p.astype(np.int64)
        if interp == "linear":
            fr = (p - idx).astype(np.float32)
            nxt = idx + 1
            if self.looped:
                nxt = np.where(nxt >= self.loop_start + self.loop_len, self.loop_start, nxt)
            out = self._fx[idx] * (1 - fr) + self._fx[nxt] * fr
        else:
            out = self.f[idx]
        if valid is not None:
            out = np.where(valid, out, 0).astype(np.float32)
        return out, newpos, playing


def mix_lrrl(chans, stereo=0.75):
    """Kanały 0,3 -> L, 1,2 -> R (jak w Amidze). stereo: 1 = twarde Amiga, 0 = mono."""
    L = chans[0] + chans[3]
    R = chans[1] + chans[2]
    a, b = (1 + stereo) / 2, (1 - stereo) / 2
    return np.stack([a * L + b * R, a * R + b * L], axis=1)


def _fft_filter(x, rate, response):
    pad = int(rate * 0.25)
    n = len(x) + pad
    nfft = 1 << (n - 1).bit_length()
    X = np.fft.rfft(x, nfft, axis=0)
    f = np.fft.rfftfreq(nfft, 1 / rate)
    H = response(f)
    y = np.fft.irfft(X * H[:, None], nfft, axis=0)[:len(x)]
    return y.astype(np.float32)


def amiga_filter(x, rate, mode="a500"):
    """mode: none | a500 (stały RC ~4.4 kHz, 6 dB/okt) | led (a500 + Butterworth 2-bieg. 3.3 kHz)
    | a1200 (bardzo łagodny ~28 kHz)."""
    if mode in (None, "none", "off"):
        return x
    def resp(f):
        s = 1j * f
        if mode == "a1200":
            return 1 / (1 + s / 28000.0)
        H = 1 / (1 + s / 4420.0)
        if mode == "led":
            fc = 3275.0
            w = s / fc
            H = H / (w * w + np.sqrt(2) * w + 1)
        return H
    return _fft_filter(x, rate, resp)
