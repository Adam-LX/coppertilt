"""Renderowanie sekcji [order] do audio: pętla bez szwu, ogony, normalizacja, OGG + sidecar JSON."""
import json, os, shutil, subprocess, tempfile, wave
import numpy as np
from .player import Renderer
from . import analyze


def render_section(song, name, renderer=None):
    """Zwraca (stereo float32 [N,2], meta dict)."""
    r = renderer or Renderer(song)
    intro, loop = song.orders[name]
    oo = song.order_opts.get(name, {})
    sp, tp = int(oo.get("speed", r.speed0)), int(oo.get("tempo", r.tempo0))
    meta = dict(section=name, title=song.head["title"], profile=song.head["profile"],
                rate=r.rate, speed=sp, tempo=tp, bpm=round(tp * 6 / sp, 3))
    rows_per_bar = int(oo.get("bar", 16))
    meta["bar_s"] = round(rows_per_bar * sp * 2.5 / tp, 6)
    if loop:
        # intro + pętla + pętla; wynik = intro (przebieg 1) + pętla (przebieg 2):
        # stan kanałów, wybrzmienia, echo i pogłos na początku pętli = jak po jej końcu => szew idealny
        pos = intro + loop + loop
        ch, marks = r.play(pos, speed=sp, tempo=tp)
        st = r.mix(ch)
        start = {}
        for pi, row, t in marks:
            start.setdefault(pi, t)
        a = start[len(intro)] if intro else 0
        b = start[len(intro) + len(loop)]
        out = np.concatenate([st[:a], st[b:]]) if intro else st[b:]
        meta.update(loop=True, loop_offset_samples=int(a), loop_offset=round(a / r.rate, 6),
                    loop_len_s=round((len(st) - b) / r.rate, 3))
    else:
        tail = float(oo.get("tail", song.head["tail"] if song.head["tail"] is not None else r.style.get("tail", 1.5)))
        ch, marks = r.play(intro, extra_tail=tail, speed=sp, tempo=tp)
        st = r.mix(ch)
        out = _trim_tail(st, r.rate)
        meta.update(loop=False, loop_offset=0.0)
    meta["length_s"] = round(len(out) / r.rate, 3)
    meta["bars"] = round(meta["length_s"] / meta["bar_s"], 2)
    meta["tempo_changes"] = sorted(list(r.tempo_log))
    return out.astype(np.float32), meta


def _trim_tail(x, rate, thresh_db=-60):
    a = np.max(np.abs(x), axis=1)
    thr = 10 ** (thresh_db / 20) * max(a.max(), 1e-9)
    idx = np.nonzero(a > thr)[0]
    end = int(idx[-1]) + int(0.05 * rate) if len(idx) else len(x)
    end = min(end, len(x))
    y = x[:end].copy()
    f = min(int(0.03 * rate), end)
    y[end - f:] *= np.linspace(1, 0, f)[:, None]
    return y


def normalize(x, rate, target=-14.0, ceiling=-1.0, loop=True):
    """Głośność do target LUFS; jeśli true-peak > ceiling – miękkie nasycenie powyżej kolana
    (bezstanowe, więc nie psuje pętli)."""
    l = analyze.lufs(x, rate)
    g = 10 ** ((target - l) / 20) if np.isfinite(l) else 1.0
    y = x * g
    lim = 10 ** (ceiling / 20)
    for _ in range(4):
        tp = analyze.true_peak(y)
        if tp <= lim * 1.0001:
            break
        knee = lim * 0.6
        a = np.abs(y)
        over = a > knee
        y = np.where(over, np.sign(y) * (knee + (lim - knee) * np.tanh((a - knee) / (lim - knee))), y)
        y = y * 0.995
    return y.astype(np.float32)


def write_wav(path, x, rate):
    d = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(d.tobytes())


def write_audio(path, x, rate, quality=6):
    """.wav albo .ogg (ffmpeg + libvorbis; gdy brak ffmpeg -> zostaje .wav obok)."""
    if path.endswith(".wav"):
        write_wav(path, x, rate)
        return path
    ff = shutil.which("ffmpeg")
    if not ff:
        alt = path.rsplit(".", 1)[0] + ".wav"
        write_wav(alt, x, rate)
        print(f"  ! brak ffmpeg – zapisano {alt} (zakoduj do OGG ręcznie)")
        return alt
    with tempfile.TemporaryDirectory() as td:
        wp = os.path.join(td, "x.wav")
        write_wav(wp, x, rate)
        subprocess.run([ff, "-v", "error", "-y", "-i", wp, "-c:a", "libvorbis", "-q:a", str(quality),
                        "-map_metadata", "-1", path], check=True)
    return path


def render_song(song, outdir, sections=None, fmt="ogg", prefix=None, normalize_to=None, report=True):
    os.makedirs(outdir, exist_ok=True)
    r = Renderer(song)
    prefix = prefix if prefix is not None else ""
    results = []
    for name in sections or song.order_names:
        x, meta = render_section(song, name, r)
        tgt = normalize_to if normalize_to is not None else float(song.order_opts.get(name, {}).get("normalize", song.head["normalize"]))
        x = normalize(x, r.rate, tgt)
        fn = os.path.join(outdir, f"{prefix}{name}.{fmt}")
        fn = write_audio(fn, x, r.rate)
        meta["lufs"] = round(analyze.lufs(x, r.rate), 2)
        meta["true_peak_dbtp"] = round(20 * np.log10(max(analyze.true_peak(x), 1e-9)), 2)
        if meta["loop"]:
            meta["seam"] = analyze.seam_check(x, r.rate, meta["loop_offset_samples"])
        meta["file"] = os.path.basename(fn)
        with open(fn.rsplit(".", 1)[0] + ".json", "w") as f:
            json.dump(meta, f, indent=1, ensure_ascii=False)
        results.append((fn, x, meta))
        if report:
            s = f"  {os.path.basename(fn)}: {meta['length_s']} s, {meta['bpm']} BPM, {meta['bars']} taktów, " \
                f"{meta['lufs']} LUFS, TP {meta['true_peak_dbtp']} dBTP"
            if meta["loop"]:
                s += f", pętla od {meta['loop_offset']} s, szew {meta['seam']['verdict']}"
            print(s)
    return results
