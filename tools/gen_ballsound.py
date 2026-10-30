#!/usr/bin/env python3
"""Copper Tilt - pinball ball sounds, synthesised from scratch (numpy). No recordings are used:
the parameters come from spectral statistics of real-machine footage (docs/DZWIEK-KULKI.md).

Writes assets/audio/ball/:
  roll_playfield.ogg  seamless loop: wood playfield roll (80-250 Hz rumble + granular mid band)
  roll_plastic.ogg    seamless loop: hollow plastic ramp roll (body resonances)
  roll_wire.ogg       seamless loop: wireform rattle and rail ringing (inharmonic steel ticks)
  roll_shimmer.ogg    seamless loop: speed layer, steel sheen 3-6 kHz (mixed in with speed)
  ramp_drop.ogg       ball leaves a ramp and lands on the playfield (thud + clack + bounce)
  ball_click.ogg      ball-on-ball steel click
  hit_flipper.ogg     ball on a flipper rubber
  hit_rubber.ogg      ball on a rubber ring/post
  hit_metal.ogg       ball on a metal guide/rail
  ball.json           loop lengths, loudness and seam check

Loops are built in the frequency domain / with circular convolution over exactly N samples, so
the end joins the start sample-exactly (no crossfade needed). Usage:
  python3 tools/gen_ballsound.py [--out DIR] [--preview DIR]   (needs numpy + ffmpeg)
"""
import argparse
import json
import os
import shutil
import subprocess
import wave

import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "audio", "ball")
LOOP_S = 2.4                     # loop length; texture modulation uses whole cycles of it
rng = np.random.default_rng(1993)


# --- helpers ---------------------------------------------------------------------------------

def shaped_noise(n, shape):
    """Periodic noise with |H(f)| = shape(f): one FFT period, so it loops seamlessly."""
    f = np.fft.rfftfreq(n, 1.0 / SR)
    spec = (rng.standard_normal(f.size) + 1j * rng.standard_normal(f.size)) * shape(f)
    spec[0] = 0.0
    x = np.fft.irfft(spec, n)
    return x / (np.abs(x).max() + 1e-12)


def peak(f, fc, q, g=1.0):
    """Resonance bump (magnitude) centred on fc."""
    return g / np.sqrt(1.0 + (q * (f / fc - fc / np.maximum(f, 1.0))) ** 2)


def lp(f, fc, order=2):
    return 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * order))


def hp(f, fc, order=2):
    return 1.0 / np.sqrt(1.0 + (fc / np.maximum(f, 1e-3)) ** (2 * order))


def periodic_mod(n, rates_hz, depth):
    """Slow periodic loudness wobble (ball spin / table texture) with whole cycles per loop."""
    t = np.arange(n) / SR
    L = n / SR
    m = np.zeros(n)
    for r in rates_hz:
        k = max(1, round(r * L))
        m += np.sin(2 * np.pi * k * t / L + rng.uniform(0, 2 * np.pi))
    m /= len(rates_hz)
    return 1.0 + depth * m


def circ_conv(x, h):
    n = len(x)
    return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(h, n), n)


def modal(dur, modes, noise_ms=0.0, noise_fc=3000.0, noise_g=0.0, attack_ms=0.3):
    """Damped-sine body: modes = [(freq, decay_s, gain, glide)], plus an optional noise burst."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for fr, dec, g, glide in modes:
        ph = 2 * np.pi * np.cumsum(fr * (1.0 + glide * np.exp(-t / 0.02))) / SR
        y += g * np.sin(ph + rng.uniform(0, 2 * np.pi)) * np.exp(-t / dec)
    if noise_g > 0:
        nb = rng.standard_normal(n) * np.exp(-t / (noise_ms / 1000.0))
        F = np.fft.rfftfreq(n, 1 / SR)
        nb = np.fft.irfft(np.fft.rfft(nb) * peak(F, noise_fc, 1.2), n)
        y += noise_g * nb / (np.abs(nb).max() + 1e-12)
    a = int(attack_ms / 1000 * SR)
    if a > 1:
        y[:a] *= np.linspace(0, 1, a)
    y[-64:] *= np.linspace(1, 0, 64)
    return y


def ticks(n, rate, jitter=0.9):
    """Circular impulse train with random spacing/strength (grains of texture)."""
    x = np.zeros(n)
    pos = 0.0
    while pos < n:
        x[int(pos)] += rng.uniform(0.3, 1.0) * rng.choice([-1, 1])
        pos += SR / rate * (1.0 + jitter * rng.uniform(-0.5, 0.5))
    return x


# --- sounds ----------------------------------------------------------------------------------

def grains(n, rate, modes, alpha=2.2, jitter=1.0):
    """Dense micro-impacts (surface roughness under the steel ball): Poisson-like tick train with
    heavy-tailed strengths, each tick exciting a few short damped modes. Circular, so it loops."""
    x = np.zeros(n)
    pos = rng.uniform(0, SR / rate)
    while pos < n:
        x[int(pos)] += min(rng.pareto(alpha) + 0.15, 6.0) * rng.choice([-1, 1])
        pos += rng.exponential(SR / rate) if jitter >= 1.0 else SR / rate * (1.0 + jitter * rng.uniform(-0.5, 0.5))
    y = circ_conv(x, modal(0.03, modes))
    return y / (np.abs(y).max() + 1e-12)


def roll_playfield(n):
    # steel ball on a clear-coated wood playfield (real-machine footage, docs/DZWIEK-KULKI.md):
    # 1) wood/cabinet resonance 80-250 Hz - the continuous low rumble,
    # 2) mid band 400-2500 Hz with granular micro-ticks - the "rrrr" that says ball, not wind,
    # 3) a little steel in the top end (the speed-dependent shimmer is roll_shimmer.ogg),
    # 4) fluctuations: ball spin (~11-14 Hz) and slow texture changes.
    wood = shaped_noise(n, lambda f: hp(f, 55) * (0.9 * peak(f, 92, 2.2) + 1.0 * peak(f, 150, 2.6)
                                                  + 0.8 * peak(f, 232, 2.2)) * lp(f, 400, 2))
    mid = shaped_noise(n, lambda f: hp(f, 350, 2) * (0.7 * peak(f, 620, 1.4) + 0.75 * peak(f, 1250, 1.6)
                                                     + 0.45 * peak(f, 2100, 1.8)) * lp(f, 3200, 2))
    grain = grains(n, 700, [(780, 0.0022, 0.7, 0), (1320, 0.0018, 1.0, 0), (2150, 0.0012, 0.6, 0),
                            (3400, 0.0008, 0.25, 0)])
    steel = grains(n, 160, [(3900, 0.003, 1.0, 0), (5300, 0.0022, 0.7, 0)])
    spin = periodic_mod(n, [12.5], 0.28) * periodic_mod(n, [0.9, 2.2, 4.8], 0.22)
    y = 0.62 * wood * periodic_mod(n, [0.7, 1.9], 0.18) + 0.62 * mid * spin + 0.8 * grain * spin + 0.08 * steel
    return y


def roll_shimmer(n):
    # speed layer (mixed in by sound.gd with speed): the bright metallic sheen of a fast steel ball,
    # 3-6 kHz: fine tinkly contacts plus a thin band of hiss with a spin flutter
    tink = grains(n, 380, [(3150, 0.006, 0.8, 0), (4380, 0.0045, 1.0, 0), (5650, 0.0035, 0.8, 0),
                           (7300, 0.0025, 0.4, 0)], alpha=1.8)
    F = np.fft.rfftfreq(n, 1.0 / SR)
    tink = np.fft.irfft(np.fft.rfft(tink) * hp(F, 2400, 3), n)   # keep the clicks out of the mid band
    tink /= np.abs(tink).max() + 1e-12
    band = shaped_noise(n, lambda f: hp(f, 2800, 3) * (peak(f, 4200, 1.3) + 0.5 * peak(f, 5800, 2.0)) * lp(f, 8000, 3))
    return 0.75 * tink + 0.35 * band * periodic_mod(n, [13.75, 23.0], 0.35)


def roll_plastic(n):
    # hollow ramp: thinner low end, marked plastic body modes, brighter and grainier than wood
    body = shaped_noise(n, lambda f: hp(f, 110) * (0.35 * peak(f, 160, 1.5) + 0.9 * peak(f, 430, 3.0)
                                                   + 0.8 * peak(f, 980, 3.5) + 0.5 * peak(f, 1850, 3.0)
                                                   + 0.3 * peak(f, 3300, 2.0)) * lp(f, 6000, 2))
    grain = grains(n, 420, [(980, 0.006, 1, 0), (1850, 0.004, 0.7, 0), (3100, 0.002, 0.35, 0)])
    return body * periodic_mod(n, [2.4, 6.0, 12.5], 0.25) + 0.38 * grain


def roll_wire(n):
    # wireform: the ball rattles between two steel rails - loud inharmonic ringing 1-8 kHz with a
    # sustained "zing" of the rails, plus a little low rumble from the ramp mounts
    tk = ticks(n, 46, 1.2) + 0.6 * ticks(n, 93, 1.4) + 0.25 * ticks(n, 260, 1.6)
    ring = modal(0.16, [(2140, 0.06, 1.0, 0), (3420, 0.045, 0.85, 0), (5230, 0.032, 0.65, 0),
                         (7880, 0.02, 0.4, 0), (1180, 0.04, 0.45, 0), (2890, 0.05, 0.5, 0)])
    rattle = circ_conv(tk, ring)
    rattle /= np.abs(rattle).max() + 1e-12
    zing = shaped_noise(n, lambda f: 0.15 * hp(f, 1500) * lp(f, 9000) + peak(f, 2140, 14) + 0.8 * peak(f, 3420, 14)
                        + 0.6 * peak(f, 5230, 12) + 0.5 * peak(f, 1180, 10))
    rumble = shaped_noise(n, lambda f: peak(f, 180, 1.2) * lp(f, 600) + 0.5 * peak(f, 520, 1.5))
    return 0.85 * rattle + 0.2 * zing * periodic_mod(n, [3.0, 7.0, 12.5], 0.45) + 0.22 * rumble


def ramp_drop():
    a = modal(0.22, [(105, 0.045, 1.0, 0.25), (190, 0.03, 0.6, 0.1), (1650, 0.008, 0.35, 0),
                     (2900, 0.005, 0.25, 0)], noise_ms=6, noise_fc=2400, noise_g=0.35)
    b = modal(0.12, [(120, 0.03, 0.4, 0.2), (1800, 0.006, 0.18, 0)], noise_ms=4, noise_fc=2600, noise_g=0.15)
    y = np.zeros(int(0.32 * SR))
    y[:a.size] += a
    o = int(0.075 * SR)
    y[o:o + b.size] += b[: y.size - o]
    return y


def ball_click():
    return modal(0.06, [(4150, 0.006, 1.0, 0), (6900, 0.004, 0.7, 0), (9300, 0.003, 0.45, 0),
                        (2600, 0.008, 0.3, 0)], noise_ms=1.2, noise_fc=7000, noise_g=0.3)


def hit_flipper():
    return modal(0.14, [(170, 0.03, 1.0, 0.3), (310, 0.02, 0.5, 0), (720, 0.012, 0.45, 0),
                        (1500, 0.006, 0.2, 0)], noise_ms=3, noise_fc=1400, noise_g=0.3)


def hit_rubber():
    return modal(0.18, [(135, 0.05, 1.0, 0.35), (240, 0.035, 0.45, 0.2), (560, 0.015, 0.2, 0)],
                 noise_ms=2.5, noise_fc=900, noise_g=0.2, attack_ms=0.8)


def hit_metal():
    return modal(0.35, [(1230, 0.09, 0.8, 0), (2870, 0.07, 1.0, 0), (4610, 0.05, 0.7, 0),
                        (6340, 0.035, 0.45, 0), (420, 0.03, 0.4, 0)], noise_ms=1.5, noise_fc=5000, noise_g=0.35)


# --- output ----------------------------------------------------------------------------------

def lufs(x):
    """Integrated loudness via ffmpeg ebur128 (mono file is treated as dual-mono)."""
    tmp = "/tmp/_ct_ball_lufs.wav"
    write_wav(tmp, x)
    r = subprocess.run(["ffmpeg", "-nostats", "-i", tmp, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    os.remove(tmp)
    v = [ln for ln in r.splitlines() if "I:" in ln and "LUFS" in ln]
    return float(v[-1].split("I:")[1].split("LUFS")[0]) if v else -99.0


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def to_ogg(path_base, x):
    wav = path_base + ".wav"
    write_wav(wav, x)
    if shutil.which("ffmpeg"):
        if subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", "5",
                           path_base + ".ogg"]).returncode == 0:
            os.remove(wav)
            return path_base + ".ogg"
    return wav


def normalise(x, target_lufs, loop=False):
    x = x - x.mean() if loop else x
    x = x / (np.abs(x).max() + 1e-12) * 0.5
    for _ in range(3):
        g = 10 ** ((target_lufs - lufs(np.tile(x, 3) if loop else x)) / 20)
        x = x * g
    if np.abs(x).max() > 0.97:
        x *= 0.97 / np.abs(x).max()
    return x


def seam(x):
    """Jump at the loop point relative to the typical sample-to-sample step."""
    d = np.abs(np.diff(x))
    return float(abs(x[0] - x[-1]) / (np.percentile(d, 99) + 1e-12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--preview", help="also write spectrum/waveform PNGs here (needs matplotlib)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    n = int(LOOP_S * SR)
    meta = {"sr": SR, "loops": {}, "oneshots": {}}
    sounds = {}
    for name, fn in (("roll_playfield", roll_playfield), ("roll_plastic", roll_plastic), ("roll_wire", roll_wire),
                     ("roll_shimmer", roll_shimmer)):
        x = normalise(fn(n), -18.0, loop=True)
        sounds[name] = x
        to_ogg(os.path.join(a.out, name), x)
        meta["loops"][name] = {"length_s": LOOP_S, "lufs": round(lufs(np.tile(x, 3)), 1),
                               "seam_ratio": round(seam(x), 3)}
    # one-shots are shorter than the 400 ms LUFS gate: normalised by peak, levels set in sound.gd
    for name, fn, pk in (("ramp_drop", ramp_drop, -3.0), ("ball_click", ball_click, -6.0),
                         ("hit_flipper", hit_flipper, -4.0), ("hit_rubber", hit_rubber, -4.0),
                         ("hit_metal", hit_metal, -6.0)):
        x = fn()
        x = x / (np.abs(x).max() + 1e-12) * 10 ** (pk / 20)
        sounds[name] = x
        to_ogg(os.path.join(a.out, name), x)
        rms = 20 * np.log10(np.sqrt(np.mean(x[: int(0.05 * SR)] ** 2)) + 1e-12)
        meta["oneshots"][name] = {"length_s": round(x.size / SR, 3), "peak_dbfs": pk,
                                  "rms50ms_dbfs": round(float(rms), 1)}
    with open(os.path.join(a.out, "ball.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(json.dumps(meta, indent=1))
    if a.preview:
        preview(sounds, a.preview)


def preview(sounds, d):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(d, exist_ok=True)
    fig, ax = plt.subplots(len(sounds), 2, figsize=(12, 2.2 * len(sounds)))
    for i, (k, x) in enumerate(sounds.items()):
        ax[i, 0].plot(np.arange(x.size) / SR, x, lw=0.4)
        ax[i, 0].set_title(k, fontsize=8)
        F = np.fft.rfftfreq(x.size, 1 / SR)
        P = 20 * np.log10(np.abs(np.fft.rfft(x * np.hanning(x.size))) + 1e-9)
        ax[i, 1].semilogx(F[1:], P[1:], lw=0.4)
        ax[i, 1].set_xlim(30, 16000)
    fig.tight_layout()
    fig.savefig(os.path.join(d, "ballsound_preview.png"), dpi=80)


if __name__ == "__main__":
    main()
