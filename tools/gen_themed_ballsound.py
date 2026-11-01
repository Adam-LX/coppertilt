#!/usr/bin/env python3
"""Generate themed sound effects and loops for Copper Tilt:
- Engine sounds, turbo blow-off, tire screeches, exhaust backfire for Copper Speedway
- Rocket thruster loops, telemetry chirps, countdown beeps, plasma shields for Launch Pad
"""
import math
import os
import random
import subprocess
import wave
import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BALL_DIR = os.path.join(ROOT, "assets", "audio", "ball")
SFX_DIR = os.path.join(ROOT, "assets", "audio", "sfx")

os.makedirs(BALL_DIR, exist_ok=True)
os.makedirs(SFX_DIR, exist_ok=True)

def save_wav(path, data, sr=SR):
    data = np.clip(data, -1.0, 1.0)
    int_data = (data * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(int_data.tobytes())

def save_ogg(path, data, sr=SR):
    wav_tmp = path.replace(".ogg", "_tmp.wav")
    save_wav(wav_tmp, data, sr)
    subprocess.run(["ffmpeg", "-y", "-i", wav_tmp, "-c:a", "libvorbis", "-q:a", "4", path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(wav_tmp):
        os.remove(wav_tmp)
    print("Saved OGG:", path)

# 1. Engine sound loop for Copper Speedway (seamless 2.4s loop)
def make_engine_loop(dur=2.4):
    n = int(dur * SR)
    t = np.arange(n) / float(SR)
    
    # Fundamental engine firing frequency ~ 65 Hz (approx 2000 RPM idle for a 4-cylinder/V8)
    # Exact integer number of cycles so it loops seamlessly without a glitch
    f0 = round(65.0 * dur) / dur
    
    # Engine harmonics: fundamental + subharmonics + uneven firing pulses
    sig = np.zeros(n, dtype=np.float32)
    # Cylinder combustion pulses (distorted pulse train)
    phase = 2.0 * np.pi * f0 * t
    pulse = np.sin(phase) + 0.6 * np.sin(phase * 2.0 + 0.5) + 0.45 * np.sin(phase * 3.0 + 1.2) + 0.3 * np.sin(phase * 4.0)
    # Non-linear saturation (exhaust pipe resonance)
    pulse = np.tanh(pulse * 2.2)
    
    # Mechanical intake / cam rattle (high-order harmonics + noise)
    cam = 0.25 * np.sin(phase * 6.0) + 0.15 * np.sin(phase * 8.0)
    
    # Throaty exhaust rumble (sub-bass)
    sub = 0.4 * np.sin(phase * 0.5)
    
    # Add subtle broadband airflow noise
    rng = np.random.default_rng(101)
    noise = rng.standard_normal(n)
    # Bandpass noise around 800-2400 Hz (induction rush)
    fft_noise = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    bp = np.exp(-((freqs - 1200.0) / 600.0) ** 2)
    air = np.fft.irfft(fft_noise * bp, n)
    air /= (np.max(np.abs(air)) + 1e-6)
    
    sig = pulse * 0.6 + cam * 0.2 + sub * 0.3 + air * 0.18
    # Normalize to -3 dB
    sig = sig / (np.max(np.abs(sig)) + 1e-6) * 0.75
    return sig

# 2. Rocket thruster ion drive loop for Launch Pad (seamless 2.4s loop)
def make_thruster_loop(dur=2.4):
    n = int(dur * SR)
    t = np.arange(n) / float(SR)
    
    # Deep rumble: 45 Hz sub-bass flame + 180 Hz turbine drone
    f_rumble = round(42.0 * dur) / dur
    f_drone = round(168.0 * dur) / dur
    
    rumble = np.sin(2.0 * np.pi * f_rumble * t) * 0.5 + np.sin(2.0 * np.pi * f_rumble * 2.0 * t) * 0.3
    drone = np.sin(2.0 * np.pi * f_drone * t) * 0.35 + np.sin(2.0 * np.pi * f_drone * 3.0 * t) * 0.2
    
    # Cryogenic gas hiss (high frequency noise)
    rng = np.random.default_rng(202)
    noise = rng.standard_normal(n)
    fft_noise = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    bp = np.exp(-((freqs - 3200.0) / 1400.0) ** 2)
    hiss = np.fft.irfft(fft_noise * bp, n)
    hiss /= (np.max(np.abs(hiss)) + 1e-6)
    
    sig = rumble * 0.5 + drone * 0.3 + hiss * 0.25
    sig = sig / (np.max(np.abs(sig)) + 1e-6) * 0.7
    return sig

# 3. Speedway SFX: Turbo blow-off valve (pssshhhh-t!)
def make_turbo_blowoff(dur=0.45):
    n = int(dur * SR)
    t = np.arange(n) / float(SR)
    rng = np.random.default_rng(303)
    noise = rng.standard_normal(n)
    # High-pitch resonant whistle sweeping down from 3500 Hz to 1200 Hz
    sweep_f = 3500.0 * np.exp(-t * 6.0) + 800.0
    phase = 2.0 * np.pi * np.cumsum(sweep_f) / SR
    whistle = np.sin(phase) * np.exp(-t * 5.0)
    # Compressed air hiss bursting then fading
    env = (t / 0.04) * np.exp(-t * 9.0)
    hiss = noise * env
    sig = whistle * 0.45 + hiss * 0.75
    return sig / (np.max(np.abs(sig)) + 1e-6) * 0.85

# 4. Speedway SFX: Gear shift / throttle blip
def make_gear_shift(dur=0.35):
    n = int(dur * SR)
    t = np.arange(n) / float(SR)
    # Mechanical transmission engagement clack
    clack = np.sin(2.0 * np.pi * 320.0 * t) * np.exp(-t * 40.0)
    # Rapid throttle blip (frequency ramp up then sudden drop)
    f = 180.0 + 350.0 * np.exp(-((t - 0.08) / 0.05) ** 2)
    phase = 2.0 * np.pi * np.cumsum(f) / SR
    blip = np.sin(phase) * np.exp(-t * 8.0)
    sig = clack * 0.6 + blip * 0.65
    return sig / (np.max(np.abs(sig)) + 1e-6) * 0.85

# 5. Speedway SFX: Exhaust backfire (pop-pop-bang!)
def make_backfire(dur=0.30):
    n = int(dur * SR)
    t = np.arange(n) / float(SR)
    rng = np.random.default_rng(404)
    # Sharp crack + low thud
    pop1 = rng.standard_normal(n) * np.exp(-t * 35.0)
    pop2 = rng.standard_normal(n) * np.exp(-np.maximum(0, t - 0.08) * 45.0) * (t > 0.08)
    thud = np.sin(2.0 * np.pi * 85.0 * t) * np.exp(-t * 18.0)
    sig = pop1 * 0.7 + pop2 * 0.5 + thud * 0.6
    return sig / (np.max(np.abs(sig)) + 1e-6) * 0.9

# 6. Speedway SFX: Tire screech on hard banking
def make_tire_screech(dur=0.45):
    n = int(dur * SR)
    t = np.arange(n) / float(SR)
    rng = np.random.default_rng(505)
    noise = rng.standard_normal(n)
    # Dual resonant frequencies modulating like scrubbing rubber
    f1 = 1850.0 + 150.0 * np.sin(2.0 * np.pi * 18.0 * t)
    f2 = 2450.0 + 200.0 * np.cos(2.0 * np.pi * 24.0 * t)
    phase1 = 2.0 * np.pi * np.cumsum(f1) / SR
    phase2 = 2.0 * np.pi * np.cumsum(f2) / SR
    screech = (np.sin(phase1) + 0.7 * np.sin(phase2)) * (0.6 + 0.4 * noise)
    env = np.sin(np.pi * t / dur) ** 0.8
    sig = screech * env
    return sig / (np.max(np.abs(sig)) + 1e-6) * 0.8

# 7. Launch Pad SFX: Telemetry radar chirp
def make_telemetry_chirp(dur=0.25):
    n = int(dur * SR)
    t = np.arange(n) / float(SR)
    # Linear FM chirp from 1200 Hz to 3600 Hz
    f = 1200.0 + (3600.0 - 1200.0) * (t / dur)
    phase = 2.0 * np.pi * np.cumsum(f) / SR
    sig = np.sin(phase) * np.exp(-t * 6.0)
    return sig / (np.max(np.abs(sig)) + 1e-6) * 0.8

# 8. Launch Pad SFX: Apollo countdown telemetry beep
def make_countdown_beep(dur=0.20):
    n = int(dur * SR)
    t = np.arange(n) / float(SR)
    # Quindar tone ~ 2525 Hz with soft attack/decay
    sig = np.sin(2.0 * np.pi * 2525.0 * t)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.5
    return sig * env * 0.75

# 9. Launch Pad SFX: Plasma deflector shield pulse
def make_plasma_shield(dur=0.30):
    n = int(dur * SR)
    t = np.arange(n) / float(SR)
    f = 950.0 * np.exp(-t * 8.0) + 120.0
    phase = 2.0 * np.pi * np.cumsum(f) / SR
    mod = 1.0 + 0.4 * np.sin(2.0 * np.pi * 80.0 * t)
    sig = np.sin(phase) * mod * np.exp(-t * 9.0)
    return sig / (np.max(np.abs(sig)) + 1e-6) * 0.85

def main():
    print("Synthesizing engine & thruster loops...")
    save_ogg(os.path.join(BALL_DIR, "engine_speedway.ogg"), make_engine_loop())
    save_ogg(os.path.join(BALL_DIR, "thruster_launch_pad.ogg"), make_thruster_loop())
    
    print("Synthesizing speedway SFX...")
    save_wav(os.path.join(SFX_DIR, "turbo_blowoff.wav"), make_turbo_blowoff())
    save_wav(os.path.join(SFX_DIR, "engine_shift.wav"), make_gear_shift())
    save_wav(os.path.join(SFX_DIR, "backfire.wav"), make_backfire())
    save_wav(os.path.join(SFX_DIR, "tire_screech.wav"), make_tire_screech())
    
    print("Synthesizing launch pad SFX...")
    save_wav(os.path.join(SFX_DIR, "telemetry_chirp.wav"), make_telemetry_chirp())
    save_wav(os.path.join(SFX_DIR, "countdown_beep.wav"), make_countdown_beep())
    save_wav(os.path.join(SFX_DIR, "plasma_shield.wav"), make_plasma_shield())
    
    print("Done generating themed sounds!")

if __name__ == "__main__":
    main()
