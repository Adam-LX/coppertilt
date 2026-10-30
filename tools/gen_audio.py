#!/usr/bin/env python3
"""Copper Tilt - procedural audio generator. 100% original, no samples, stdlib only.

Paula-style: 4 channels, 8-bit quantised instrument waveforms, hard Amiga panning
(ch0+ch3 left, ch1+ch2 right) with crossfeed so it is pleasant on headphones.

Usage:  python3 tools/gen_audio.py                         # SFX only
        python3 tools/gen_audio.py --legacy-music DIR      # + the old 2-track music sketch into DIR
Writes: assets/audio/sfx/*.wav. With --legacy-music also DIR/{title,funfair}_legacy.ogg
(WAV fallback if no ffmpeg/vorbis).

The game music no longer comes from here: assets/audio/music/title.ogg is the hand-kept intro
(never regenerated) and the other themes/stingers come from tools/amigamusic/build_coppertilt.sh.
This script refuses to write anything into assets/audio/music/ or assets/audio/stingers/ and
never overwrites an existing music file.
"""
import array
import math
import os
import random
import shutil
import subprocess
import wave

SR = 22050
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SFX_DIR = os.path.join(ROOT, "assets", "audio", "sfx")
MUS_DIR = None   # set only by --legacy-music; never the game's music folder
PROTECTED_DIRS = [os.path.join(ROOT, "assets", "audio", d) for d in ("music", "stingers")]
rnd = random.Random(1987)


def clamp(x, lo=-1.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def q8(x):
    """8-bit quantise, like a Paula sample."""
    return round(clamp(x) * 127.0) / 127.0


def write_wav(path, left, right=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    buf = array.array("h")
    if right is None:
        for s in left:
            buf.append(int(clamp(s) * 32000))
    else:
        for l, r in zip(left, right):
            buf.append(int(clamp(l) * 32000))
            buf.append(int(clamp(r) * 32000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1 if right is None else 2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(buf.tobytes())


def osc(kind, p, duty=0.5):
    if kind == "square":
        return 1.0 if p < duty else -1.0
    if kind == "saw":
        return 2.0 * p - 1.0
    if kind == "tri":
        return 4.0 * abs(p - 0.5) - 1.0
    return math.sin(p * 2.0 * math.pi)


def mtof(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


# ---------------------------------------------------------------- SFX ----

def tone(dur, f0, f1=None, kind="square", vol=0.8, attack=0.002, duty=0.5, power=2.0, vib=0.0):
    n = int(dur * SR)
    out = []
    ph = 0.0
    att = max(1, int(attack * SR))
    for i in range(n):
        t = i / n
        f = f0 * ((f1 / f0) ** t) if f1 else f0
        if vib:
            f *= 1.0 + vib * math.sin(i / SR * 2 * math.pi * 7.0)
        ph = (ph + f / SR) % 1.0
        env = min(1.0, i / att) * (1.0 - t) ** power
        out.append(q8(osc(kind, ph, duty) * vol * env))
    return out


def noise(dur, vol=0.6, lp0=0.5, lp1=None, power=2.0):
    n = int(dur * SR)
    out = []
    y = 0.0
    for i in range(n):
        t = i / n
        lp = lp0 + ((lp1 if lp1 is not None else lp0) - lp0) * t
        y += lp * (rnd.uniform(-1, 1) - y)
        out.append(q8(y * vol * (1.0 - t) ** power * 1.6))
    return out


def mix(*sigs):
    n = max(len(s) for s in sigs)
    out = [0.0] * n
    for s in sigs:
        for i, v in enumerate(s):
            out[i] += v
    return [clamp(v) for v in out]


def cat(*sigs):
    out = []
    for s in sigs:
        out.extend(s)
    return out


def silence(dur):
    return [0.0] * int(dur * SR)


def arp(freqs, step, kind="square", vol=0.5, duty=0.5, power=1.0):
    return cat(*[tone(step, f, None, kind, vol, duty=duty, power=power) for f in freqs])


def make_sfx():
    s = {}
    s["flipper"] = mix(tone(0.07, 190, 55, "square", 0.6, duty=0.3), noise(0.035, 0.55, 0.7))
    s["flipper_down"] = tone(0.05, 110, 50, "square", 0.3, duty=0.3)
    s["bumper"] = mix(tone(0.2, 1500, 480, "square", 0.35, duty=0.25), tone(0.22, 760, 240, "tri", 0.6),
                      noise(0.05, 0.4, 0.9))
    s["sling"] = mix(tone(0.09, 950, 280, "saw", 0.45), noise(0.07, 0.6, 0.75))
    s["rollover"] = arp([880, 1318, 1760], 0.045, "tri", 0.6)
    s["target"] = mix(tone(0.08, 520, 340, "square", 0.45, duty=0.2), noise(0.035, 0.5, 0.4))
    s["post"] = tone(0.06, 1250, 900, "tri", 0.45)
    s["launch"] = mix(noise(0.5, 0.7, 0.03, 0.9, power=1.5), tone(0.45, 90, 420, "saw", 0.3, power=1.2))
    s["plunger"] = tone(0.025, 2100, 1500, "square", 0.2)
    s["drain"] = tone(1.0, 440, 55, "saw", 0.5, power=1.2, vib=0.03)
    s["tilt"] = mix(tone(0.7, 70, 62, "square", 0.55, power=0.7, vib=0.08), noise(0.7, 0.25, 0.2, power=0.8))
    s["warn"] = cat(tone(0.09, 988, None, "square", 0.45, power=0.3), silence(0.05),
                    tone(0.09, 988, None, "square", 0.45, power=0.3))
    s["bonus"] = arp([mtof(m) for m in (72, 76, 79, 84, 88, 91, 96)], 0.055, "square", 0.4, 0.25)
    s["start"] = cat(arp([mtof(m) for m in (69, 72, 76, 81)], 0.08, "square", 0.45, 0.5),
                     tone(0.35, mtof(84), None, "square", 0.45, power=1.5, vib=0.01))
    up = [mtof(m) for m in (69, 72, 76, 81, 84, 88, 93, 96)]
    s["jackpot"] = cat(arp(up, 0.05, "square", 0.45), arp(up[::-1], 0.05, "square", 0.4),
                       arp(up, 0.05, "saw", 0.4), tone(0.4, mtof(93), None, "square", 0.45, power=1.3))
    s["save"] = arp([mtof(m) for m in (76, 81, 88)], 0.07, "tri", 0.6)
    os.makedirs(SFX_DIR, exist_ok=True)
    for name, sig in s.items():
        write_wav(os.path.join(SFX_DIR, name + ".wav"), sig)
    print("sfx:", ", ".join(sorted(s)))


# -------------------------------------------------------------- MUSIC ----

class Song:
    def __init__(self, bpm, bars, speed=6):
        self.row = int(SR * 60 / bpm / 4)          # one tracker row = 1/16 note
        self.tick = self.row // speed              # tracker tick (arpeggio speed)
        self.n = self.row * 16 * bars
        self.ch = [[0.0] * self.n for _ in range(4)]

    def note(self, ch, row, rows, inst, midi, vol=1.0, chord=None):
        start = row * self.row
        length = min(rows * self.row, self.n - start)
        if length <= 0:
            return
        buf = self.ch[ch]
        f = mtof(midi) if midi else 0.0
        ph = ph2 = 0.0
        y = 0.0
        for i in range(length):
            t = i / SR
            if inst == "kick":
                ff = 45 + 130 * math.exp(-t * 35)
                ph = (ph + ff / SR) % 1.0
                v = math.sin(ph * 2 * math.pi) * math.exp(-t * 9) + (rnd.uniform(-1, 1) * 0.3 if i < 80 else 0)
            elif inst == "snare":
                y += 0.55 * (rnd.uniform(-1, 1) - y)
                ph = (ph + 190 / SR) % 1.0
                v = (y * 1.3 + 0.4 * osc("tri", ph)) * math.exp(-t * 16)
            elif inst == "hat":
                x = rnd.uniform(-1, 1)
                v = (x - y) * math.exp(-t * (40 if rows < 2 else 14)) * 0.5
                y += 0.5 * (x - y)
            elif inst == "bass":
                ph = (ph + f / SR) % 1.0
                env = 0.55 + 0.45 * math.exp(-t * 12)
                v = osc("square", ph, 0.25 + 0.15 * math.exp(-t * 6)) * env
            elif inst == "arp":
                steps = chord or (0, 4, 7)
                k = (i // self.tick) % len(steps)
                ph = (ph + f * 2 ** (steps[k] / 12) / SR) % 1.0
                v = osc("square", ph, 0.5) * (0.6 + 0.4 * math.exp(-t * 3))
            elif inst == "lead":
                vib = 1.0 + (0.012 * math.sin(t * 2 * math.pi * 6) if t > 0.12 else 0)
                ph = (ph + f * vib / SR) % 1.0
                ph2 = (ph2 + f * 1.004 * vib / SR) % 1.0
                v = (0.6 * osc("saw", ph) + 0.4 * osc("square", ph2, 0.5)) * (0.75 + 0.25 * math.exp(-t * 5))
            elif inst == "pad":
                ph = (ph + f / SR) % 1.0
                ph2 = (ph2 + f * 1.006 / SR) % 1.0
                v = (osc("tri", ph) + osc("tri", ph2)) * 0.5 * min(1.0, t / 0.25)
            else:
                v = 0.0
            rel = min(1.0, (length - i) / 220.0)        # tiny release, no clicks
            buf[start + i] = q8(v * vol * rel)

    def render(self, path_base):
        _guard(path_base)
        l, r = [], []
        a, b = self.ch[0], self.ch[3]          # left pair (Paula 0+3)
        c, d = self.ch[1], self.ch[2]          # right pair (Paula 1+2)
        yl = yr = 0.0
        for i in range(self.n):
            left = (a[i] + b[i]) * 0.5
            right = (c[i] + d[i]) * 0.5
            ml = left + 0.45 * right
            mr = right + 0.45 * left
            yl += 0.62 * (ml - yl)                 # gentle "LED filter"
            yr += 0.62 * (mr - yr)
            l.append(yl)
            r.append(yr)
        peak = max(max(abs(x) for x in l), max(abs(x) for x in r), 1e-6)
        g = 0.89 / peak
        l = [x * g for x in l]
        r = [x * g for x in r]
        wav = path_base + ".wav"
        write_wav(wav, l, r)
        ogg = path_base + ".ogg"
        if shutil.which("ffmpeg"):
            res = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis",
                                  "-q:a", "6", ogg])
            if res.returncode == 0 and os.path.exists(ogg):
                os.remove(wav)
                print("music:", os.path.relpath(ogg, ROOT))
                return
        print("music (wav):", os.path.relpath(wav, ROOT))


def _guard(path_base):
    """Refuse to touch the game's music (title.ogg intro, amigamusic themes) or overwrite anything."""
    real = os.path.realpath(os.path.dirname(path_base))
    for d in PROTECTED_DIRS:
        d = os.path.realpath(d)
        if real == d or real.startswith(d + os.sep):
            raise SystemExit("gen_audio: refusing to write into %s (game music is kept by hand / "
                             "tools/amigamusic)" % os.path.relpath(d, ROOT))
    for ext in (".ogg", ".wav"):
        if os.path.exists(path_base + ext):
            raise SystemExit("gen_audio: %s exists, not overwriting" % (path_base + ext))


MINOR = (0, 3, 7, 12)
MAJOR = (0, 4, 7, 12)


def drums(s, bar, busy):
    r0 = bar * 16
    for k in (0, 8) + ((6, 10) if busy else ()):
        s.note(0, r0 + k, 2, "kick", 0, 1.0)
    for k in (4, 12):
        s.note(0, r0 + k, 2, "snare", 0, 0.8)
    for k in range(0, 16, 2):
        if k not in (0, 4, 8, 12) and not (busy and k in (6, 10)):
            s.note(0, r0 + k, 1 if k % 4 else 2, "hat", 0, 0.5)


def make_funfair():
    """Midnight Funfair: 138 BPM, bouncy major-key calliope lead over oom-pah tracker bass."""
    s = Song(bpm=138, bars=24)
    A = [(48, MAJOR), (48, MAJOR), (53, MAJOR), (55, MAJOR),
         (57, MINOR), (53, MAJOR), (55, MAJOR), (55, MAJOR)]
    B = [(53, MAJOR), (55, MAJOR), (52, MINOR), (57, MINOR),
         (50, MINOR), (55, MAJOR), (48, MAJOR), (55, MAJOR)]
    prog = A[:4] + A + B + A[4:]
    # calliope hook (16th steps, midi, length)
    hook = [
        [(0, 72, 2), (2, 76, 2), (4, 79, 2), (6, 84, 4), (10, 83, 2), (12, 79, 2), (14, 76, 2)],
        [(0, 77, 3), (3, 76, 1), (4, 74, 2), (6, 72, 2), (8, 74, 4), (12, 79, 4)],
        [(0, 77, 2), (2, 81, 2), (4, 84, 2), (6, 81, 2), (8, 77, 2), (10, 81, 2), (12, 86, 4)],
        [(0, 83, 4), (4, 79, 2), (6, 74, 2), (8, 71, 4), (12, 74, 2), (14, 79, 2)],
        [(0, 81, 2), (2, 84, 2), (4, 88, 4), (8, 84, 2), (10, 81, 2), (12, 76, 4)],
        [(0, 77, 2), (2, 81, 2), (4, 84, 2), (6, 89, 2), (8, 88, 4), (12, 84, 4)],
        [(0, 86, 2), (2, 83, 2), (4, 79, 2), (6, 83, 2), (8, 86, 2), (10, 91, 2), (12, 89, 2), (14, 86, 2)],
        [(0, 84, 8), (8, 79, 2), (10, 83, 2), (12, 86, 4)],
    ]
    for bar in range(24):
        root, chord = prog[bar]
        r0 = bar * 16
        intro = bar < 4
        drums(s, bar, busy=not intro and bar % 4 == 3)
        if not intro:
            for k in (2, 6, 10, 14):
                s.note(0, r0 + k, 1, "hat", 0, 0.45)
        # oom-pah: root on the beat, fifth/octave on the off-beats, a walking pickup
        for k, off in ((0, 0), (4, 7), (8, 0), (12, 7), (14, 12)):
            s.note(1, r0 + k, 2 if k != 14 else 2, "bass", root - 12 + off, 0.95)
        for k in range(0, 16, 2):
            s.note(2, r0 + k, 2, "arp", root + 12, 0.36 if intro else 0.42, chord)
        if intro:
            if bar >= 2:
                for k, m, ln in hook[bar - 2][:4]:
                    s.note(3, r0 + k, ln, "lead", m - 12, 0.45)
        else:
            sec = (bar - 4) % 8
            for k, m, ln in hook[sec]:
                s.note(3, r0 + k, ln, "lead", m + (0 if bar < 12 or bar >= 20 else -5), 0.6)
    s.render(os.path.join(MUS_DIR, "funfair_legacy"))


def make_title():
    s = Song(bpm=112, bars=8)
    prog = [(48, MAJOR), (45, MINOR), (41, MAJOR), (43, MAJOR),
            (48, MAJOR), (52, MINOR), (41, MAJOR), (43, MAJOR)]
    for bar in range(8):
        root, chord = prog[bar]
        r0 = bar * 16
        s.note(0, r0 + 0, 2, "kick", 0, 0.8)
        s.note(0, r0 + 10, 2, "kick", 0, 0.6)
        s.note(0, r0 + 4, 2, "snare", 0, 0.55)
        s.note(0, r0 + 12, 2, "snare", 0, 0.55)
        for k in (2, 6, 8, 14):
            s.note(0, r0 + k, 1, "hat", 0, 0.35)
        s.note(1, r0, 6, "bass", root - 12, 0.9)
        s.note(1, r0 + 6, 2, "bass", root, 0.7)
        s.note(1, r0 + 8, 8, "bass", root - 12, 0.9)
        for k in range(0, 16, 4):
            s.note(2, r0 + k, 4, "arp", root + 24, 0.32, chord)
        s.note(3, r0, 16, "pad", root + 12 + chord[1], 0.5)
    s.render(os.path.join(MUS_DIR, "title_legacy"))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Copper Tilt SFX generator (+ optional legacy music sketch)")
    ap.add_argument("--legacy-music", metavar="DIR",
                    help="also render the old title/funfair sketch into DIR (not assets/audio/music)")
    args = ap.parse_args()
    if args.legacy_music:
        MUS_DIR = os.path.abspath(args.legacy_music)
        _guard(os.path.join(MUS_DIR, "title_legacy"))
        _guard(os.path.join(MUS_DIR, "funfair_legacy"))
    make_sfx()
    if MUS_DIR:
        os.makedirs(MUS_DIR, exist_ok=True)
        make_title()
        make_funfair()
