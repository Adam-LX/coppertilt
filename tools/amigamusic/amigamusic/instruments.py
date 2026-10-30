"""Biblioteka instrumentów – wszystko syntezowane proceduralnie (clean-room, zero cudzych sampli).

Konwencja strojenia (jak w PT): instrument "melodyczny" ma 32 próbki na okres przy nucie C-2
(8287 Hz) => C-2 brzmi ~C4 (środkowe C, ok. 17 centów nisko – tak samo w całym utworze).
Presety basowe (`*bass*`) mają 64 próbki na okres => brzmią oktawę niżej niż zapisana nuta.
Perkusja jest projektowana pod nutę C-3 (16574 Hz).

Każdy preset: funkcja(**opcje) -> paula.Sample. Opcje wspólne: vol (0..64), gain (mnożnik).
"""
import numpy as np
from .paula import Sample

C2_RATE = 8287.0
C3_RATE = 16574.0
_rng = np.random.default_rng(1987)


def _to8(x, gain=1.0):
    x = np.asarray(x, np.float64) * gain
    pk = np.max(np.abs(x)) or 1.0
    return np.clip(np.round(x / pk * 127), -128, 127).astype(np.int8)


def _cycle(kind, L=32, duty=0.5, harm=None):
    t = np.arange(L) / L
    if kind == "square":
        return np.where(t < duty, 1.0, -1.0)
    if kind == "saw":
        return 2 * t - 1
    if kind == "tri":
        return 1 - 4 * np.abs(t - 0.5)
    if kind == "sine":
        return np.sin(2 * np.pi * t)
    if kind == "harm":                         # suma harmonicznych (organy / kaliope)
        return sum(a * np.sin(2 * np.pi * (i + 1) * t) for i, a in enumerate(harm))
    raise ValueError(kind)


def _looped(name, cyc, vol, reps=1, attack=None, gain=1.0):
    body = np.tile(cyc, reps)
    if attack is not None:
        data = np.concatenate([attack, body])
        ls = len(attack)
    else:
        data, ls = body, 0
    return Sample(name, _to8(data, gain) if attack is None else _to8(data, gain),
                  volume=vol, loop_start=ls, loop_len=len(body))


# ---------------------------------------------------------------- fale chip (krótkie pętle)
def chip_square(vol=48, duty=0.5, L=32, **_):
    return _looped(f"chip sq {int(duty*100)}%", _cycle("square", L, duty), vol)


def chip_pulse(vol=44, duty=0.125, L=32, **_):
    return _looped("chip pulse", _cycle("square", L, duty), vol)


def chip_saw(vol=44, L=32, **_):
    return _looped("chip saw", _cycle("saw", L), vol)


def chip_tri(vol=56, L=32, **_):
    return _looped("chip tri", _cycle("tri", L), vol)


def chip_sine(vol=56, L=32, **_):
    return _looped("chip sine", _cycle("sine", L), vol)


def chip_bass(vol=56, duty=0.4, **_):
    """Kwadrat 64 próbki/okres – bas chip (oktawa niżej niż zapis)."""
    return _looped("chip bass", _cycle("square", 64, duty), vol)


# ---------------------------------------------------------------- "samplowane" (dłuższe)
def pulse_bass(vol=60, **_):
    """Bas pulsowy z przemiataniem wypełnienia (0.25 -> 0.40), potem pętla – jak w intro."""
    L, cycles = 64, 40
    out = []
    for c in range(cycles):
        duty = 0.40 - 0.15 * np.exp(-c / 6)
        cyc = _cycle("square", L, duty) * (1 + 0.35 * np.exp(-c / 3))
        out.append(cyc)
    att = np.concatenate(out[:-4])
    body = np.concatenate(out[-4:])
    return Sample("pulse bass", _to8(np.concatenate([att, body])), vol, len(att), len(body))


def slap_bass(vol=60, **_):
    """Bas „syntezatorowy” – piła z opadającym filtrem (wypieczony w samplu) + pętla."""
    L, cycles = 64, 48
    t = np.arange(L) / L
    out = []
    for c in range(cycles):
        nh = int(2 + 18 * np.exp(-c / 7))
        cyc = sum(np.sin(2 * np.pi * k * t) / k for k in range(1, nh + 1))
        out.append(cyc * (1 + 0.5 * np.exp(-c / 4)))
    att, body = np.concatenate(out[:-2]), np.concatenate(out[-2:])
    return Sample("synth bass", _to8(np.concatenate([att, body])), vol, len(att), len(body))


def detune_lead(vol=48, detune=1.004, mix=0.6, **_):
    """Piła + kwadrat odstrojone (×1.004) – wielocyklowa pętla 250 okresów (dudnienie zapętlone)."""
    L, cycles = 32, 250
    n = L * cycles
    ph = np.arange(n) / L
    saw = 2 * (ph % 1) - 1
    sq = np.where((ph * (cycles + 1) / cycles) % 1 < 0.5, 1.0, -1.0)
    return Sample("detune lead", _to8(mix * saw + (1 - mix) * 0.7 * sq), vol, 0, n)


def pwm_lead(vol=46, **_):
    """Kwadrat z wolną modulacją szerokości impulsu – pętla 128 okresów."""
    L, cycles = 32, 128
    out = [_cycle("square", L, 0.5 - 0.38 * (0.5 - 0.5 * np.cos(2 * np.pi * c / cycles)))
           for c in range(cycles)]
    d = np.concatenate(out)
    return Sample("pwm lead", _to8(d), vol, 0, len(d))


def calliope(vol=50, **_):
    """Kaliope / organy jarmarczne: harmoniczne 1-4 (+ lekki „chiff” na ataku)."""
    L = 32
    cyc = _cycle("harm", L, harm=[1.0, 0.55, 0.32, 0.18])
    n_att = L * 6
    noise = _rng.uniform(-1, 1, n_att) * np.linspace(0.5, 0, n_att)
    att = np.tile(cyc, 6) + noise
    return Sample("calliope", _to8(np.concatenate([att, np.tile(cyc, 2)])), vol, n_att, 2 * L)


def organ(vol=48, **_):
    """Organy (drawbar 8'+4'+2 2/3') – krótka pętla."""
    return _looped("organ", _cycle("harm", 32, harm=[1.0, 0.7, 0.45, 0.0, 0.0, 0.3]), vol)


def bell(vol=52, decay=0.6, **_):
    """Dzwonek/glockenspiel FM, jednorazowy (one-shot)."""
    n = int(C2_RATE * 2 * decay) & ~1
    t = np.arange(n) / 32.0
    env = np.exp(-np.arange(n) / (n / 5))
    x = np.sin(2 * np.pi * t + 2.2 * env * np.sin(2 * np.pi * 3.5 * t)) * env
    return Sample("bell", _to8(x), vol)


def pluck(vol=52, **_):
    """Szarpana struna (Karplus-Strong) – one-shot z pętlą ostatniego wygaszonego okresu."""
    L, n = 32, 32 * 120
    buf = _rng.uniform(-1, 1, L)
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % L]
        buf[i % L] = 0.5 * (buf[i % L] + buf[(i + 1) % L]) * 0.996
    return Sample("pluck", _to8(out), vol)


def strings_pad(vol=40, **_):
    """Pad smyczkowy: 3 odstrojone piły (pętla ~6 tys. próbek)."""
    L, cycles = 32, 200
    ph = np.arange(L * cycles) / L
    x = sum(2 * ((ph * r) % 1) - 1 for r in (1.0, 1.0 + 1 / cycles, 1.0 - 1 / cycles))
    # łagodne wygładzenie (pad)
    k = np.array([0.25, 0.5, 0.25])
    x = np.convolve(np.concatenate([x[-1:], x, x[:1]]), k, "valid")
    return Sample("strings pad", _to8(x), vol, 0, len(x))


def tri_pad(vol=44, **_):
    L, cycles = 32, 200
    ph = np.arange(L * cycles) / L
    x = sum(1 - 4 * np.abs(((ph * r) % 1) - 0.5) for r in (1.0, 1.0 + 1 / cycles))
    return Sample("tri pad", _to8(x), vol, 0, len(x))


def orch_hit(vol=58, chord=(0, 4, 7, 12), **_):
    """Uderzenie orkiestrowe (syntezowane): akord pił + szum, ostry atak, one-shot."""
    n = int(C2_RATE * 0.7) & ~1
    t = np.arange(n) / 32.0
    env = np.exp(-np.arange(n) / (n / 4))
    x = sum(2 * ((t * 2 ** (s / 12)) % 1) - 1 for s in chord)
    x = x + _rng.uniform(-1, 1, n) * np.exp(-np.arange(n) / 300) * 2
    return Sample("orch hit", _to8(x * env), vol)


def brass(vol=50, **_):
    """„Blacha” – piła z otwierającym się filtrem na ataku, potem pętla."""
    L, cycles = 32, 30
    t = np.arange(L) / L
    out = []
    for c in range(cycles):
        nh = int(2 + 12 * (1 - np.exp(-c / 5)))
        out.append(sum(np.sin(2 * np.pi * k * t) / k for k in range(1, nh + 1)))
    att, body = np.concatenate(out[:-2]), np.concatenate(out[-2:])
    return Sample("brass", _to8(np.concatenate([att, body])), vol, len(att), len(body))


# ---------------------------------------------------------------- perkusja (pod C-3)
def kick(vol=64, punch=1.0, **_):
    n = int(C3_RATE * 0.26) & ~1
    tt = np.arange(n) / C3_RATE
    f = 45 + 110 * np.exp(-tt * 38) * punch
    ph = 2 * np.pi * np.cumsum(f) / C3_RATE
    x = np.sin(ph) * np.exp(-tt * 11) + 0.4 * _rng.uniform(-1, 1, n) * np.exp(-tt * 300)
    return Sample("kick", _to8(np.tanh(1.6 * x)), vol)


def snare(vol=56, **_):
    n = int(C3_RATE * 0.2) & ~1
    tt = np.arange(n) / C3_RATE
    tone = np.sin(2 * np.pi * 185 * tt) * np.exp(-tt * 30)
    noise = _rng.uniform(-1, 1, n) * np.exp(-tt * 17)
    noise = noise - 0.5 * np.concatenate([[0], noise[:-1]])
    return Sample("snare", _to8(0.55 * tone + noise), vol)


def clap(vol=52, **_):
    n = int(C3_RATE * 0.22) & ~1
    tt = np.arange(n) / C3_RATE
    env = np.zeros(n)
    for d in (0, 0.011, 0.022):
        env += (tt >= d) * np.exp(-np.maximum(tt - d, 0) * 90)
    env += (tt >= 0.03) * np.exp(-np.maximum(tt - 0.03, 0) * 14) * 0.6
    x = _rng.uniform(-1, 1, n)
    x = x - np.concatenate([[0], x[:-1]])
    return Sample("clap", _to8(x * env), vol)


def hat_closed(vol=36, **_):
    n = int(C3_RATE * 0.05) & ~1
    tt = np.arange(n) / C3_RATE
    x = _rng.uniform(-1, 1, n)
    x = x - np.concatenate([[0], x[:-1]])
    return Sample("hat closed", _to8(x * np.exp(-tt * 75)), vol)


def hat_open(vol=32, **_):
    n = int(C3_RATE * 0.3) & ~1
    tt = np.arange(n) / C3_RATE
    x = _rng.uniform(-1, 1, n)
    x = x - np.concatenate([[0], x[:-1]])
    return Sample("hat open", _to8(x * np.exp(-tt * 10)), vol)


def crash(vol=34, **_):
    n = int(C3_RATE * 1.2) & ~1
    tt = np.arange(n) / C3_RATE
    x = _rng.uniform(-1, 1, n)
    x = x - 0.8 * np.concatenate([[0], x[:-1]])
    return Sample("crash", _to8(x * np.exp(-tt * 3.2)), vol)


def tom(vol=56, **_):
    n = int(C3_RATE * 0.3) & ~1
    tt = np.arange(n) / C3_RATE
    f = 110 + 90 * np.exp(-tt * 25)
    x = np.sin(2 * np.pi * np.cumsum(f) / C3_RATE) * np.exp(-tt * 12)
    return Sample("tom", _to8(x), vol)


def rim(vol=44, **_):
    n = int(C3_RATE * 0.04) & ~1
    tt = np.arange(n) / C3_RATE
    x = (np.sin(2 * np.pi * 1700 * tt) + 0.6 * _rng.uniform(-1, 1, n)) * np.exp(-tt * 140)
    return Sample("rim", _to8(x), vol)


PRESETS = {
    # chip
    "chip_square": chip_square, "chip_pulse": chip_pulse, "chip_saw": chip_saw,
    "chip_tri": chip_tri, "chip_sine": chip_sine, "chip_bass": chip_bass,
    # basy
    "pulse_bass": pulse_bass, "slap_bass": slap_bass,
    # leady
    "detune_lead": detune_lead, "pwm_lead": pwm_lead, "calliope": calliope, "organ": organ,
    "brass": brass, "bell": bell, "pluck": pluck,
    # pady / akordy
    "strings_pad": strings_pad, "tri_pad": tri_pad, "orch_hit": orch_hit,
    # perkusja
    "kick": kick, "snare": snare, "clap": clap, "hat_closed": hat_closed, "hat_open": hat_open,
    "crash": crash, "tom": tom, "rim": rim,
}

CATEGORY = {
    "chip": ["chip_square", "chip_pulse", "chip_saw", "chip_tri", "chip_sine", "chip_bass"],
    "bass": ["pulse_bass", "slap_bass", "chip_bass"],
    "lead": ["detune_lead", "pwm_lead", "calliope", "organ", "brass", "bell", "pluck"],
    "pad/arp": ["strings_pad", "tri_pad", "orch_hit", "chip_square", "chip_pulse"],
    "drums": ["kick", "snare", "clap", "hat_closed", "hat_open", "crash", "tom", "rim"],
}

# ---------------------------------------------------------------- presety stylów
# Liczby pochodzą z pomiarów modułów referencyjnych (docs/research/amiga-music-reference.md).
STYLES = {
    "cracktro": dict(
        speed=6, tempo=125, stereo=1.0, filter="led", loop=True,
        desc="Krótki loop (1-8 pozycji), chipowe pętle 16-64 B, arpeggio 0xy, twarde stereo.",
        kit={1: "kick", 2: "snare", 3: "hat_closed", 4: "chip_bass", 5: "chip_square",
             6: "chip_pulse", 7: "chip_tri", 8: "detune_lead"}),
    "demo": dict(
        speed=6, tempo=125, stereo=0.8, filter="a500", loop=True,
        desc="Dłuższa forma, 'samplowane' leady z vibrato 4xy, obwiednie Axy/Cxx.",
        kit={1: "kick", 2: "snare", 3: "hat_closed", 4: "slap_bass", 5: "detune_lead",
             6: "strings_pad", 7: "pwm_lead", 8: "hat_open", 9: "crash"}),
    "pinball-table": dict(
        speed=6, tempo=132, stereo=0.7, filter="a500", loop=True,
        desc="Temat stołu 60-90 s, pętla bez szwu; kanał 4 rzadki (miejsce na SFX).",
        kit={1: "kick", 2: "snare", 3: "hat_closed", 4: "pulse_bass", 5: "calliope",
             6: "chip_square", 7: "bell", 8: "detune_lead", 9: "hat_open", 10: "crash",
             11: "orch_hit", 12: "clap"}),
    "multiball": dict(
        speed=5, tempo=132, stereo=0.7, filter="a500", loop=True,
        desc="Ten sam tempo-takt co stół, speed o 1 niższy (×1.2 szybciej), gęstsza perkusja.",
        kit={1: "kick", 2: "snare", 3: "hat_closed", 4: "pulse_bass", 5: "calliope",
             6: "chip_square", 7: "bell", 8: "detune_lead", 9: "hat_open", 10: "crash",
             11: "orch_hit", 12: "clap"}),
    "stinger": dict(
        speed=4, tempo=125, stereo=0.7, filter="a500", loop=False,
        desc="Dżingiel 1-4 s bez pętli, ogon 1.5 s; 1 wzór, 3-6 instrumentów.",
        kit={1: "kick", 2: "snare", 3: "crash", 4: "pulse_bass", 5: "brass",
             6: "chip_square", 7: "bell", 8: "orch_hit"}),
}


STYLES["unreal"] = dict(
    pt=False, speed=6, tempo=125, stereo=1.0, filter="none", interp="linear",
    reverb=0.35, delay="3 0.35 0.22", loop=True, channels=16,
    desc="16-32 kanały, sample 16-bit HQ, panorama per kanał, echo+pogłos, sekcje ambient/akcja "
         "(osobne [order] = osobne pętle, przełączane w grze). Eksport .s3m.",
    kit={1: "hq_kick", 2: "hq_snare", 3: "hq_hat", 4: "hq_bass", 5: "hq_pad", 6: "hq_choir",
         7: "hq_strings", 8: "hq_epiano", 9: "hq_glass", 10: "hq_flute", 11: "hq_harp",
         12: "hq_taiko", 13: "hq_cymbal", 14: "hq_shaker", 15: "hq_boom", 16: "hq_saw_lead"})

from .instruments_hq import PRESETS_HQ  # noqa: E402
PRESETS.update(PRESETS_HQ)
CATEGORY["hq (unreal)"] = list(PRESETS_HQ)


def make(preset, **opts):
    if preset not in PRESETS:
        raise KeyError(f"nieznany preset instrumentu '{preset}'. Dostępne: {', '.join(PRESETS)}")
    return PRESETS[preset](**opts)
