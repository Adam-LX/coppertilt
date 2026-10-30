"""CLI:  python3 -m amigamusic <polecenie> ...

  render  PLIK.song [-o KATALOG|plik.ogg] [-s SEKCJA ...] [--wav] [--png] [--mod X.mod] [--s3m X.s3m]
  check   PLIK.song [-v]          # składnia, zakresy, harmonia (symbolicznie + audio), szew, LUFS
  dump    PLIK.song [-p PATTERN]  # wzory jak w trackerze (do przeglądu)
  instruments [--profile P]       # lista presetów i profili
  new     NAZWA --template T -o PLIK.song   # szablon: minimal | pinball-table | stinger | cracktro | unreal
"""
import argparse, os, sys, shutil
from . import songtext, render, analyze
from .player import Renderer
from .instruments import PRESETS, CATEGORY, STYLES

DRUMS = set(CATEGORY.get("drums", [])) | {"hq_kick", "hq_snare", "hq_taiko", "hq_shaker", "hq_hat",
                                         "hq_cymbal", "hq_boom", "orch_hit"}
TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def cmd_render(a):
    song = songtext.load(a.song)
    secs = a.section or song.order_names
    fmt = "wav" if a.wav else "ogg"
    if a.output and a.output.endswith((".ogg", ".wav")):
        if len(secs) != 1:
            sys.exit("-o plik.ogg wymaga jednej sekcji (-s NAZWA); dla wielu sekcji podaj katalog")
        outdir = os.path.dirname(a.output) or "."
        res = render.render_song(song, outdir, secs, a.output.rsplit(".", 1)[1])
        os.replace(res[0][0], a.output)
        j = res[0][0].rsplit(".", 1)[0] + ".json"
        if os.path.exists(j):
            os.replace(j, a.output.rsplit(".", 1)[0] + ".json")
        res = [(a.output, res[0][1], res[0][2])]
    else:
        res = render.render_song(song, a.output or "out", secs, fmt, prefix=a.prefix or "")
    if a.png:
        for fn, x, meta in res:
            marks = [meta["loop_offset"]] if meta.get("loop") and meta["loop_offset"] else []
            analyze.plot_png(fn.rsplit(".", 1)[0] + ".png", x, meta["rate"], marks)
    if a.mod:
        from . import modexport
        modexport.write_mod(song, a.mod)
        print(f"  .mod -> {a.mod}")
    if a.s3m:
        from . import s3mexport
        s3mexport.write_s3m(song, a.s3m)
        print(f"  .s3m -> {a.s3m}")


def cmd_check(a):
    song = songtext.load(a.song)
    r = Renderer(song)
    print(f"{song.head['title']}: profil {song.head['profile']}, {r.nch} kan., "
          f"{len(song.patterns)} wzorów, sekcje: {', '.join(song.order_names)}")
    if not song.leadsheet.strip():
        print("  ! brak [leadsheet] – zapisz motyw i akordy PRZED nutami")
    lines, st = analyze.symbolic_check(song, DRUMS, a.verbose)
    print(f"  harmonia (symbolicznie): mocne części w akordzie {st['strong_in_chord']*100:.0f}%, "
          f"poza tonacją {st['out_of_key']*100:.1f}% z {st['notes']} nut")
    for l in lines:
        print("   -", l)
    pats = [p for p in song.patterns if song.patterns[p]["chords"]]
    res = analyze.audio_chord_check(song, r, pats, DRUMS)
    if res:
        okn = sum(x["ok"] for x in res)
        print(f"  harmonia (audio, chroma): {okn}/{len(res)} taktów zgodnych z `chords:`")
        for x in res:
            if not x["ok"] or a.verbose:
                print(f"   - {x['pattern']} takt {x['bar']}: zamierzony {x['chord']}, słychać {x['top3']} (score {x['score']})")
    for name in song.order_names:
        x, meta = render.render_section(song, name, r)
        x = render.normalize(x, r.rate, song.head["normalize"])
        s = f"  [{name}] {meta['length_s']} s, {meta['bars']} taktów @ {meta['bpm']} BPM, " \
            f"{analyze.lufs(x, r.rate):.1f} LUFS"
        if meta["loop"]:
            s += f", szew: {analyze.seam_check(x, r.rate, meta['loop_offset_samples'])}"
        print(s)
    bad = st["strong_in_chord"] < 0.8 or st["out_of_key"] > 0.03 or (res and okn / len(res) < 0.75)
    print("  WYNIK:", "UWAGA – popraw nuty/akordy" if bad else "OK")
    return 1 if bad else 0


def cmd_dump(a):
    song = songtext.load(a.song)
    for name, pat in song.patterns.items():
        if a.pattern and name != a.pattern:
            continue
        print(f"== {name} ({pat['rows']} wierszy) akordy: {' '.join(pat['chords'])}")
        for r in range(pat["rows"]):
            cells = " | ".join(repr(pat["ch"][c][r]) for c in range(song.head["channels"]))
            print(f"{r:02d} {cells}")


def cmd_instruments(a):
    for cat, names in CATEGORY.items():
        print(f"[{cat}]")
        for n in names:
            doc = (PRESETS[n].__doc__ or "").strip().split("\n")[0]
            print(f"  {n:14s} {doc}")
    print("\nprofile:")
    for k, v in STYLES.items():
        if a.profile and k != a.profile:
            continue
        print(f"  {k:14s} speed {v['speed']} tempo {v['tempo']} – {v['desc']}")


def cmd_new(a):
    src = os.path.join(TEMPLATES, a.template + ".song")
    if not os.path.exists(src):
        sys.exit(f"brak szablonu {a.template}; dostępne: " + ", ".join(f[:-5] for f in os.listdir(TEMPLATES)))
    txt = open(src, encoding="utf-8").read().replace("{{TITLE}}", a.name)
    if os.path.exists(a.output):
        sys.exit(f"{a.output} już istnieje")
    open(a.output, "w", encoding="utf-8").write(txt)
    print(f"utworzono {a.output} z szablonu {a.template}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="amigamusic", description="Tracker-owy syntezator muzyki w stylu Amigi (numpy).")
    sp = p.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("render"); r.add_argument("song"); r.add_argument("-o", "--output")
    r.add_argument("-s", "--section", action="append"); r.add_argument("--wav", action="store_true")
    r.add_argument("--png", action="store_true"); r.add_argument("--mod"); r.add_argument("--s3m")
    r.add_argument("--prefix")
    c = sp.add_parser("check"); c.add_argument("song"); c.add_argument("-v", "--verbose", action="store_true")
    d = sp.add_parser("dump"); d.add_argument("song"); d.add_argument("-p", "--pattern")
    i = sp.add_parser("instruments"); i.add_argument("--profile")
    n = sp.add_parser("new"); n.add_argument("name"); n.add_argument("--template", default="minimal")
    n.add_argument("-o", "--output", required=True)
    a = p.parse_args(argv)
    try:
        rc = {"render": cmd_render, "check": cmd_check, "dump": cmd_dump,
              "instruments": cmd_instruments, "new": cmd_new}[a.cmd](a)
    except songtext.SongError as e:
        sys.exit(f"BŁĄD: {e}")
    sys.exit(rc or 0)
