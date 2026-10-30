"""Parser formatu .song – czytelny tekst „jak tracker”.

Pełna specyfikacja: docs/MUZYKA-AMIGA.md (rozdz. „Format .song”). Skrót:

  (komentarz: '#' na początku linii albo po spacji – 'C#3' to nuta, nie komentarz)
  title  Nazwa            # nagłówek: klucz wartość
  profile pinball-table   # cracktro | demo | pinball-table | multiball | stinger | unreal
  speed 6 / tempo 132 / channels 4 / pan L R R L / stereo 0.7 / filter a500 / key C major

  [instruments]           # NN nazwa preset [opcja=wartość ...]
  01 kick kick
  05 lead calliope vol=48

  [leadsheet]             # dowolny tekst: motyw, akordy, forma (dla ludzi i agentów)

  [track bas_C]           # wielokrotnego użytku sekwencja tokenów (wiersze)
  C-1@bass*2 C-2*2 G-1*2 C-2*2

  [pattern A1 rows=64]
  chords: C Am F G7       # akord na takt (16 wierszy); „C,G” = pół taktu C, pół G
  ch1: bęben*4            # odwołanie do ścieżki, *N = powtórz, +N/-N = transpozycja
  ch2: bas_C bas_C+5

  [order main]            # sekcja = osobny plik audio; '|' = punkt pętli (przed nim intro)
                          # opcje: [order multiball speed=5 tempo=132] – startowe speed/tempo sekcji
  A1 A2 B1 | A1 A2 B1 B2

Tokeny (każdy to 1 wiersz, chyba że *N):
  .  albo ...             pusty wiersz;  .*7 = 7 pustych
  C-2 C#3 D-1             nuta (PT: C-1..B-3; profil unreal: C-0..B-7)
  @nazwa / @05            instrument (nazwa z [instruments] albo numer dziesiętny)
  !A02                    efekt PT (3 znaki hex) tylko w pierwszym wierszu tokenu
  !!A02                   efekt powtarzany w każdym z N wierszy tokenu
  v40                     kolumna głośności 0..64 (PT: eksportowana jako Cxx)
  ^                       wycięcie nuty (EC0)
  *N                      token zajmuje N wierszy (nuta + N-1 pustych)
Kolejność w tokenie: nuta, vNN, @instrument, !efekt, *N   (np. C-3v40@snare!A02*2)
Przykład:  C-3@lead!!401*4   E-3*2   G-3v32!A02*2
"""
import re
from .paula import NOTE_NAMES

TOKEN_RE = re.compile(
    r"^(?P<note>[A-Ga-g][-#][0-9]|\^|\.{1,3})?"
    r"(?:v(?P<vol>\d{1,2}))?"
    r"(?:@(?P<inst>[A-Za-z0-9_]+))?"
    r"(?:(?P<rep>!!)|!)?(?P<eff>[0-9A-Fa-f]{3})?"
    r"(?:\*(?P<n>\d+))?$")


class Cell:
    __slots__ = ("note", "inst", "vol", "eff", "par")

    def __init__(self, note=None, inst=0, vol=None, eff=0, par=0):
        self.note, self.inst, self.vol, self.eff, self.par = note, inst, vol, eff, par

    def empty(self):
        return self.note is None and not self.inst and self.vol is None and not self.eff and not self.par

    def __repr__(self):
        n = "---" if self.note is None else ("^^^" if self.note == -1 else note_str(self.note))
        return f"{n} {self.inst:02d} {self.eff:X}{self.par:02X}"


def note_to_idx(s):
    """'C-2' -> indeks półtonu względem C-0 (C-0 = 0). PT C-1 = 12."""
    s = s.upper()
    key, octv = s[:2], int(s[2])
    return octv * 12 + NOTE_NAMES.index(key)


def note_str(idx):
    return NOTE_NAMES[idx % 12] + str(idx // 12)


class SongError(Exception):
    pass


class Song:
    def __init__(self):
        self.head = dict(title="untitled", author="", profile="demo", speed=None, tempo=None,
                         channels=4, pan=None, stereo=None, filter=None, key="C major",
                         reverb=0.0, send=None, delay=None, interp=None, rate=44100,
                         normalize=-14.0, tail=None)
        self.instruments = {}      # num -> dict(name, preset, opts)
        self.inst_by_name = {}
        self.leadsheet = ""
        self.tracks = {}           # name -> list[str tokens]
        self.patterns = {}         # name -> dict(rows, chords, ch: list[Cell])
        self.orders = {}           # name -> (intro list, loop list or None)
        self.order_names = []
        self.order_opts = {}       # name -> {speed, tempo, tail, normalize} z [order NAME speed=5 ...]
        self.source = ""


def _split_items(line):
    return [t for t in line.split() if t]


def parse(text, path="<song>"):
    s = Song()
    s.source = path
    sect, sname, sargs = "head", None, {}
    raw_patterns = {}
    for ln, raw in enumerate(text.splitlines(), 1):
        line = re.sub(r"(^|\s)#.*$", "", raw).rstrip() if sect != "leadsheet" else raw.rstrip()
        st = line.strip()
        m = re.match(r"^\[(\w+)\s*([^\]\s]*)\s*([^\]]*)\]$", st)
        if m:
            sect, sname = m.group(1).lower(), m.group(2) or None
            sargs = dict(kv.split("=", 1) for kv in m.group(3).split() if "=" in kv)
            if sect == "track":
                s.tracks[sname] = []
            elif sect == "pattern":
                raw_patterns[sname] = dict(rows=int(sargs.get("rows", 64)), chords=[], ch={}, line=ln)
            elif sect == "order":
                s.orders[sname] = []
                s.order_names.append(sname)
                s.order_opts[sname] = {k: int(v) if v.isdigit() else v for k, v in sargs.items()}
            elif sect not in ("instruments", "leadsheet"):
                raise SongError(f"{path}:{ln}: nieznana sekcja [{sect}]")
            continue
        if sect == "leadsheet":
            s.leadsheet += raw + "\n"
            continue
        if not st:
            continue
        try:
            if sect == "head":
                k, _, v = st.partition(" ")
                k = k.lower()
                v = v.strip()
                if k not in s.head:
                    raise SongError(f"nieznany klucz nagłówka '{k}'")
                if k in ("speed", "tempo", "channels", "rate"):
                    v = int(v)
                elif k in ("stereo", "reverb", "normalize", "tail"):
                    v = float(v)
                elif k in ("pan", "send"):
                    v = v.split()
                s.head[k] = v
            elif sect == "instruments":
                parts = st.split()
                num, name, preset = int(parts[0]), parts[1], parts[2]
                opts = {}
                for kv in parts[3:]:
                    a, b = kv.split("=", 1)
                    try:
                        b = float(b) if "." in b else int(b)
                    except ValueError:
                        pass
                    opts[a] = b
                if not 1 <= num <= 99:
                    raise SongError("numer instrumentu 1..99")
                s.instruments[num] = dict(name=name, preset=preset, opts=opts)
                s.inst_by_name[name.lower()] = num
            elif sect == "track":
                s.tracks[sname] += _split_items(st)
            elif sect == "pattern":
                k, _, v = st.partition(":")
                k = k.strip().lower()
                if k == "chords":
                    raw_patterns[sname]["chords"] += v.split()
                elif re.match(r"^ch\d+$", k):
                    raw_patterns[sname]["ch"].setdefault(int(k[2:]), []).extend(_split_items(v))
                else:
                    raise SongError(f"w [pattern] oczekiwano 'chN:' albo 'chords:', jest '{k}'")
            elif sect == "order":
                s.orders[sname] += _split_items(st)
        except SongError as e:
            raise SongError(f"{path}:{ln}: {e}") from None
        except (ValueError, IndexError) as e:
            raise SongError(f"{path}:{ln}: błąd składni: {e} | {raw.strip()}") from None

    for name, rp in raw_patterns.items():
        rows = rp["rows"]
        chans = {}
        for c, items in rp["ch"].items():
            if not 1 <= c <= s.head["channels"]:
                raise SongError(f"{path}: pattern {name}: ch{c} poza 'channels {s.head['channels']}'")
            cells = expand(s, items, f"pattern {name} ch{c}")
            if len(cells) > rows:
                raise SongError(f"{path}: pattern {name} ch{c}: {len(cells)} wierszy > rows={rows}")
            cells += [Cell() for _ in range(rows - len(cells))]
            chans[c - 1] = cells
        for c in range(s.head["channels"]):
            chans.setdefault(c, [Cell() for _ in range(rows)])
        s.patterns[name] = dict(rows=rows, chords=rp["chords"], ch=chans)
    for oname, items in s.orders.items():
        intro, loop = [], None
        for it in items:
            if it == "|":
                loop = []
                continue
            if it not in s.patterns:
                raise SongError(f"{path}: [order {oname}]: brak patternu '{it}'")
            (intro if loop is None else loop).append(it)
        if loop is None:
            s.orders[oname] = ([], intro) if _profile_loops(s) else (intro, None)
        else:
            s.orders[oname] = (intro, loop)
    return s


def _profile_loops(s):
    from .instruments import STYLES
    st = STYLES.get(s.head["profile"], {})
    return st.get("loop", True)


def expand(song, items, where, transpose=0, depth=0):
    if depth > 8:
        raise SongError(f"{where}: zbyt głęboka rekurencja ścieżek")
    out = []
    for it in items:
        m = re.match(r"^([A-Za-z_][\w]*?)([+-]\d+)?(?:\*(\d+))?$", it)
        if m and m.group(1) in song.tracks:
            tr = int(m.group(2) or 0)
            rep = int(m.group(3) or 1)
            for _ in range(rep):
                out += expand(song, song.tracks[m.group(1)], f"{where}>{m.group(1)}", transpose + tr, depth + 1)
            continue
        out += token_cells(song, it, where, transpose)
    return out


def token_cells(song, tok, where, transpose=0):
    m = TOKEN_RE.match(tok)
    if not m or tok == "":
        raise SongError(f"{where}: nie rozumiem tokenu '{tok}' (ścieżka nieznana albo zła składnia)")
    n = int(m.group("n") or 1)
    note = None
    nt = m.group("note")
    if nt and nt not in (".", "..", "..."):
        if nt == "^":
            note = -1
        else:
            note = note_to_idx(nt) + transpose
    inst = 0
    if m.group("inst"):
        k = m.group("inst")
        if k.isdigit():
            inst = int(k)
        elif k.lower() in song.inst_by_name:
            inst = song.inst_by_name[k.lower()]
        else:
            raise SongError(f"{where}: nieznany instrument '@{k}'")
        if inst not in song.instruments:
            raise SongError(f"{where}: instrument {inst} nie zdefiniowany w [instruments]")
    vol = int(m.group("vol")) if m.group("vol") else None
    if vol is not None and vol > 64:
        raise SongError(f"{where}: głośność v{vol} > 64")
    eff = par = 0
    if m.group("eff"):
        e = m.group("eff").upper()
        eff, par = int(e[0], 16), int(e[1:], 16)
    first = Cell(note, inst, vol, eff, par)
    cells = [first]
    for _ in range(n - 1):
        cells.append(Cell(None, 0, None, eff, par) if m.group("rep") else Cell())
    return cells


def load(path):
    with open(path, encoding="utf-8") as f:
        return parse(f.read(), path)
