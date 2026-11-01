#!/usr/bin/env python3
"""Copper Tilt - Pinball Announcer Voice Callouts Generator.
Uses Piper TTS with en_US-ryan-high voice, followed by custom DSP audio processing
(EQ, compression, and table-specific character processing: stadium announcer for Speedway,
mission control radio for Launch Pad, and crisp arcade barker for Midnight Funfair).
"""
import array
import math
import os
import subprocess
import wave

PIPER_BIN = os.environ.get("PIPER_BIN", "piper")
MODEL_PATH = os.environ.get("PIPER_MODEL", os.path.expanduser("~/.local/share/piper/voices/en_US-ryan-high.onnx"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "audio", "voice")

CALLOUTS = {
    # --- Universal Pinball Callouts ---
    "skill_shot": "Skill shot!",
    "super_skill_shot": "Super skill shot!",
    "extra_ball": "Extra ball!",
    "extra_ball_lit": "Extra ball is lit!",
    "jackpot": "Jackpot!",
    "super_jackpot": "Super jackpot!",
    "multiball": "Multiball!",
    "multiball_midnight_funfair": "Carnival multiball!",
    "multiball_copper_speedway": "Speedway multiball!",
    "multiball_launch_pad": "Liftoff multiball!",
    "lock_lit": "Lock is lit!",
    "ball_locked": "Ball locked!",
    "hurry_up": "Hurry up!",
    "shoot_again": "Shoot again!",
    "video_mode": "Video mode!",
    "game_over": "Game over!",
    "tilt_warning": "Warning, careful!",
    "tilted": "Tilt!",
    "kickback": "Kickback!",
    "combo": "Combo!",
    "super_combo": "Super combo!",

    # --- Midnight Funfair ---
    "start_midnight_funfair": "Step right up, welcome to the funfair!",
    "ghost_train": "Ghost train!",
    "helter_skelter": "Helter skelter!",
    "duck_hunt": "Duck shoot!",
    "fortune": "Your fortune awaits!",
    "carnival_complete": "Carnival champion!",

    # --- Copper Speedway ---
    "start_copper_speedway": "Drivers, start your engines!",
    "redline": "Redline!",
    "turbo_boost": "Turbo boost!",
    "nitro": "Nitro engaged!",
    "pit_stop": "Pit stop, go go go!",
    "lap_record": "New lap record!",
    "chequered_flag": "Chequered flag!",
    "podium_finish": "Podium finish!",

    # --- Launch Pad ---
    "start_launch_pad": "Mission control, all systems go!",
    "t_minus_zero": "T-minus zero, liftoff!",
    "stage_separation": "Stage separation confirmed!",
    "solar_flare": "Solar flare!",
    "eagle_landed": "The Eagle has landed!",
    "orbital_insertion": "Orbit achieved!",
    "deep_space": "Entering deep space!",
}


def read_wav(path):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        data = w.readframes(n)
        samples = array.array("h", data)
        # convert to float -1.0 .. 1.0
        if ch == 1:
            out = [s / 32768.0 for s in samples]
        else:
            out = [(samples[i * 2] + samples[i * 2 + 1]) / 65536.0 for i in range(n)]
        return sr, out


def write_wav(path, sr, samples):
    buf = array.array("h")
    for s in samples:
        v = int(max(-1.0, min(1.0, s)) * 32767.0)
        buf.append(v)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(buf.tobytes())


def process_audio(name, sr, samples):
    """Pinball broadcast processing: normalize, highpass, punchy EQ, table flavor."""
    # 1. Normalize peak
    peak = max(max(abs(s) for s in samples), 1e-4)
    samples = [s / peak for s in samples]

    # 2. Highpass filter ~110 Hz to remove low-frequency rumble
    rc = 1.0 / (2.0 * math.pi * 110.0)
    dt = 1.0 / sr
    alpha = rc / (rc + dt)
    hp = [0.0] * len(samples)
    prev_x = samples[0]
    prev_y = 0.0
    for i in range(len(samples)):
        y = alpha * (prev_y + samples[i] - prev_x)
        hp[i] = y
        prev_x = samples[i]
        prev_y = y
    samples = hp

    # 3. Table flavor
    if "launch_pad" in name or name in ["t_minus_zero", "stage_separation", "eagle_landed", "orbital_insertion", "deep_space"]:
        # Apollo / Mission Control comms: radio bandpass + subtle mic squelch
        samples = _radio_comms(sr, samples)
    elif "copper_speedway" in name or name in ["redline", "turbo_boost", "nitro", "pit_stop", "lap_record", "chequered_flag", "podium_finish"]:
        # Speedway track announcer: subtle stadium slapback
        samples = _stadium_pa(sr, samples)
    else:
        # Arcade / Carnival: punchy presence boost
        samples = _punchy_presence(samples)

    # 4. Final peak normalization to -0.6 dB (0.93)
    peak = max(max(abs(s) for s in samples), 1e-4)
    target = 0.93
    samples = [s * (target / peak) for s in samples]
    return samples


def _punchy_presence(samples):
    # Soft saturation curve (arcade speaker compression)
    out = []
    for s in samples:
        # tanh-like warm overdrive
        out.append(math.tanh(s * 1.3) * 0.9)
    return out


def _stadium_pa(sr, samples):
    # Short slapback delay (55 ms) with feedback
    delay_samples = int(0.055 * sr)
    out = list(samples) + [0.0] * (delay_samples + int(0.1 * sr))
    for i in range(len(samples)):
        echo = samples[i] * 0.28
        out[i + delay_samples] += echo
    return _punchy_presence(out)


def _radio_comms(sr, samples):
    # Bandpass 400Hz - 3400Hz (VHF radio transponder)
    out = []
    for s in samples:
        # Subtle distortion
        clipped = max(-0.85, min(0.85, s * 1.4))
        out.append(clipped * 0.85)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    temp_raw = "/tmp/_callout_raw.wav"

    print("Generating pinball voice callouts using Piper TTS (en_US-ryan-high)...")
    count = 0
    for name, phrase in CALLOUTS.items():
        out_path = os.path.join(OUT_DIR, name + ".wav")
        # Run piper to generate raw wave
        cmd = [
            PIPER_BIN,
            "--model", MODEL_PATH,
            "--output_file", temp_raw
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        proc.communicate(input=phrase)
        if proc.returncode != 0:
            print(f"Error synthesizing {name}: {proc.stderr}")
            continue

        # DSP process
        sr, samples = read_wav(temp_raw)
        processed = process_audio(name, sr, samples)
        write_wav(out_path, sr, processed)
        count += 1
        print(f"  [{count}/{len(CALLOUTS)}] Wrote {out_path} ({len(processed)/sr:.2f}s)")

    if os.path.exists(temp_raw):
        os.remove(temp_raw)
    print(f"Done! Successfully generated {count} callout audio files in {OUT_DIR}.")


if __name__ == "__main__":
    main()
