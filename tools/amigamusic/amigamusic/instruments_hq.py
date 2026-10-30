"""Instrumenty HQ (16-bit, wyższe częstotliwości) dla profilu 'unreal' – też w 100% syntezowane.

Strojenie jak w module PT: C-2 brzmi ~C4. Sample HQ mają Lc próbek na okres przy C-2,
więc c2spd = 8287 * Lc / 32 (Lc=128 -> 33 148 Hz). Basy (`hq_bass*`) brzmią oktawę niżej.
Perkusja projektowana pod C-3 przy 44,1 kHz (c2spd 22 050).
"""
import numpy as np
from .paula import Sample

_rng = np.random.default_rng(1997)
C3HQ = 44100.0


def _to16(x, peak=0.98):
    x = np.asarray(x, np.float64)
    pk = np.max(np.abs(x)) or 1.0
    return np.round(x / pk * 32767 * peak).astype(np.int16)


def _hq(name, data, vol, ls=0, ll=0, lc=128):
    return Sample(name, _to16(data), vol, ls, ll, bits=16, c2spd=8287.0 * lc / 32)


def _additive(ph, amps):
    return sum(a * np.sin(2 * np.pi * (k + 1) * ph) for k, a in enumerate(amps) if a)


def _ensemble(lc, cycles, voices, amps_fn, spread=1.0):
    n = lc * cycles
    ph = np.arange(n) / lc
    x = np.zeros(n)
    for v in range(voices):
        det = (v - (voices - 1) / 2) * spread        # całkowite cykle różnicy => pętla bez szwu
        r = (cycles + det) / cycles
        x += amps_fn(ph * r + _rng.uniform())
    return x


def hq_pad(vol=40, lc=128, cycles=240, voices=5, bright=0.6, **_):
    """Ciepły pad „supersaw” (5 głosów, harmoniczne łagodnie obcięte), długa pętla bez szwu."""
    amps = [bright ** (k / 3) / (k + 1) for k in range(24)]
    x = _ensemble(lc, cycles, voices, lambda p: _additive(p, amps), 1.0)
    n_att = lc * 40
    att = x[:n_att] * np.linspace(0, 1, n_att) ** 2
    return _hq("hq pad", np.concatenate([att, x]), vol, n_att, len(x), lc)


def hq_choir(vol=40, lc=128, cycles=240, **_):
    """Chór „aah”: harmoniczne ważone formantami (≈700/1150/2700 Hz przy C4), 4 głosy."""
    f0 = 261.6
    def amps_for():
        a = []
        for k in range(1, 30):
            f = f0 * k
            g = sum(w * np.exp(-((f - F) / bw) ** 2) for F, bw, w in
                    ((700, 180, 1.0), (1150, 220, 0.6), (2700, 300, 0.25)))
            a.append(0.15 / k + g)
        return a
    amps = amps_for()
    x = _ensemble(lc, cycles, 4, lambda p: _additive(p, amps), 1.0)
    n_att = lc * 50
    att = x[:n_att] * np.linspace(0, 1, n_att)
    return _hq("hq choir", np.concatenate([att, x]), vol, n_att, len(x), lc)


def hq_strings(vol=42, lc=128, cycles=240, **_):
    amps = [1.0 / (k + 1) * (0.92 ** k) for k in range(28)]
    x = _ensemble(lc, cycles, 6, lambda p: _additive(p, amps), 0.7)
    n_att = lc * 70
    att = x[:n_att] * (1 - np.exp(-np.arange(n_att) / (n_att / 3)))
    return _hq("hq strings", np.concatenate([att, x]), vol, n_att, len(x), lc)


def hq_bass(vol=56, lc=256, **_):
    """Bas: sinus + łagodna piła, krótki „pluck” na ataku; oktawa niżej niż zapis."""
    cyc_n = 24
    ph = np.arange(lc * cyc_n) / lc
    bright = np.exp(-np.arange(len(ph)) / (lc * 4))
    x = np.sin(2 * np.pi * ph) + (0.15 + 0.45 * bright) * _additive(ph, [0, 0.5, 0.33, 0.25, 0.2, 0.16])
    body = np.sin(2 * np.pi * ph[:lc * 2]) + 0.15 * _additive(ph[:lc * 2], [0, 0.5, 0.33, 0.25, 0.2, 0.16])
    return _hq("hq bass", np.concatenate([x, body]), vol, len(x), len(body), lc // 2)


def hq_epiano(vol=50, lc=128, dur=2.6, **_):
    """Fortepian elektryczny FM (one-shot)."""
    n = int(8287 * lc / 32 * dur)
    ph = np.arange(n) / lc
    t = np.arange(n) / n
    env = np.exp(-t * 4.5)
    idx = 1.8 * np.exp(-t * 10)
    x = np.sin(2 * np.pi * ph + idx * np.sin(2 * np.pi * ph)) * env
    x += 0.25 * np.sin(2 * np.pi * 14 * ph) * np.exp(-t * 40)
    return _hq("hq epiano", x, vol, 0, 0, lc)


def hq_glass(vol=46, lc=128, dur=3.0, **_):
    """Szklany dzwonek (FM o niecałkowitym stosunku) – one-shot."""
    n = int(8287 * lc / 32 * dur)
    ph = np.arange(n) / lc
    t = np.arange(n) / n
    x = np.sin(2 * np.pi * ph + 1.2 * np.exp(-t * 6) * np.sin(2 * np.pi * 3.51 * ph)) * np.exp(-t * 3.5)
    return _hq("hq glass", x, vol, 0, 0, lc)


def hq_flute(vol=44, lc=128, cycles=200, **_):
    n = lc * cycles
    ph = np.arange(n) / lc
    x = np.sin(2 * np.pi * ph) + 0.12 * np.sin(4 * np.pi * ph) + 0.05 * np.sin(6 * np.pi * ph)
    breath = _rng.normal(0, 1, n)
    breath = np.convolve(breath, np.ones(6) / 6, "same")
    x = x + 0.05 * breath
    n_att = lc * 20
    att = x[:n_att] * np.linspace(0, 1, n_att) + 0.25 * breath[:n_att] * np.linspace(1, 0, n_att)
    # pętla: ostatnie 150 cykli (szum w pętli jest nieperiodyczny – zostawiamy go słabym)
    return _hq("hq flute", np.concatenate([att, x]), vol, n_att, n, lc)


def hq_harp(vol=50, lc=128, dur=2.5, **_):
    """Harfa/gitara – Karplus-Strong w 16 bit."""
    n = int(8287 * lc / 32 * dur)
    L = lc
    buf = _rng.uniform(-1, 1, L)
    buf = np.convolve(buf, [0.25, 0.5, 0.25], "same")
    out = np.zeros(n)
    i = 0
    while i < n:
        e = min(i + L, n)
        out[i:e] = buf[:e - i]
        buf = 0.5 * (buf + np.roll(buf, -1)) * 0.998
        i = e
    return _hq("hq harp", out, vol, 0, 0, lc)


def hq_saw_lead(vol=44, lc=128, cycles=200, **_):
    amps = [1.0 / (k + 1) for k in range(40)]
    x = _ensemble(lc, cycles, 2, lambda p: _additive(p, amps), 1.0)
    return _hq("hq lead", x, vol, 0, len(x), lc)


# ---------------------------------------------------------------- perkusja HQ (C-3 @ 44.1 kHz)
def _drum(name, x, vol):
    return Sample(name, _to16(x), vol, 0, 0, bits=16, c2spd=C3HQ / 2)


def hq_kick(vol=64, **_):
    n = int(C3HQ * 0.5)
    t = np.arange(n) / C3HQ
    f = 42 + 95 * np.exp(-t * 30)
    x = np.sin(2 * np.pi * np.cumsum(f) / C3HQ) * np.exp(-t * 7)
    x += 0.3 * _rng.uniform(-1, 1, n) * np.exp(-t * 400)
    return _drum("hq kick", np.tanh(1.3 * x), vol)


def hq_snare(vol=54, **_):
    n = int(C3HQ * 0.45)
    t = np.arange(n) / C3HQ
    noise = _rng.uniform(-1, 1, n)
    noise = noise - 0.6 * np.concatenate([[0], noise[:-1]])
    x = 0.6 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 28) + noise * (np.exp(-t * 20) + 0.15 * np.exp(-t * 5))
    return _drum("hq snare", x, vol)


def hq_taiko(vol=60, **_):
    n = int(C3HQ * 1.0)
    t = np.arange(n) / C3HQ
    f = 70 + 40 * np.exp(-t * 15)
    x = np.sin(2 * np.pi * np.cumsum(f) / C3HQ) * np.exp(-t * 4.5)
    x += 0.4 * np.convolve(_rng.uniform(-1, 1, n), np.ones(30) / 30, "same") * np.exp(-t * 12)
    return _drum("hq taiko", x, vol)


def hq_shaker(vol=30, **_):
    n = int(C3HQ * 0.12)
    t = np.arange(n) / C3HQ
    x = _rng.uniform(-1, 1, n)
    x = x - np.concatenate([[0], x[:-1]])
    return _drum("hq shaker", x * np.sin(np.pi * t / t[-1]) ** 2, vol)


def hq_hat(vol=30, **_):
    n = int(C3HQ * 0.08)
    t = np.arange(n) / C3HQ
    x = _rng.uniform(-1, 1, n)
    x = x - np.concatenate([[0], x[:-1]])
    return _drum("hq hat", x * np.exp(-t * 60), vol)


def hq_cymbal(vol=30, **_):
    n = int(C3HQ * 2.5)
    t = np.arange(n) / C3HQ
    x = _rng.uniform(-1, 1, n)
    x = x - 0.85 * np.concatenate([[0], x[:-1]])
    return _drum("hq cymbal", x * np.exp(-t * 1.6) * (1 - np.exp(-t * 200)), vol)


def hq_boom(vol=60, **_):
    """Uderzenie/„impact” – nisko, długo (przejścia ambient -> akcja)."""
    n = int(C3HQ * 2.0)
    t = np.arange(n) / C3HQ
    f = 30 + 60 * np.exp(-t * 6)
    x = np.sin(2 * np.pi * np.cumsum(f) / C3HQ) * np.exp(-t * 2)
    x += 0.5 * np.convolve(_rng.uniform(-1, 1, n), np.ones(60) / 60, "same") * np.exp(-t * 3)
    return _drum("hq boom", x, vol)


PRESETS_HQ = {
    "hq_pad": hq_pad, "hq_choir": hq_choir, "hq_strings": hq_strings, "hq_bass": hq_bass,
    "hq_epiano": hq_epiano, "hq_glass": hq_glass, "hq_flute": hq_flute, "hq_harp": hq_harp,
    "hq_saw_lead": hq_saw_lead, "hq_kick": hq_kick, "hq_snare": hq_snare, "hq_taiko": hq_taiko,
    "hq_shaker": hq_shaker, "hq_hat": hq_hat, "hq_cymbal": hq_cymbal, "hq_boom": hq_boom,
}
