# amigamusic: syntezator muzyki w stylu trackerów Amigi/PC (numpy)

*English summary:* this is a self-contained, numpy-only tracker synth. It renders readable
`.song` text files (ProTracker semantics: 4 channels LRRL, 8-bit samples, Paula resampling) to
seamless OGG loops with JSON sidecars. It can also export `.mod` and `.s3m`. Profiles cover
cracktro, demo, pinball-table, multiball and stinger, plus `unreal`, which gives you 16 channels,
16-bit HQ samples, echo and reverb. It needs no GPU, no network and no external samples.

## Wymagania
- Python ≥ 3.9 i **numpy** (jedyna zależność). Na NixOS: `nix-shell -p python3Packages.numpy`.
- `ffmpeg` z libvorbis. Jest opcjonalny: bez niego dostajesz WAV zamiast OGG.

## Szybki start
```bash
cd tools/amigamusic
python3 -m amigamusic new "Mój utwór" --template minimal -o /tmp/moj.song
python3 -m amigamusic check  /tmp/moj.song           # harmonia (symbolicznie + audio), szew, LUFS
python3 -m amigamusic render /tmp/moj.song -o /tmp/out --png --mod /tmp/moj.mod
python3 -m amigamusic instruments --profile unreal   # lista presetów i profili
python3 -m amigamusic dump /tmp/moj.song             # wzory jako siatka trackera
```
`render` zapisuje dla każdej sekcji `[order X]` plik `X.ogg` i `X.json`. Pole `-o` przyjmuje
katalog albo `plik.ogg`, gdy sekcja jest jedna. Dodaj `--prefix`, żeby dostać nazwy
`prefix_X.ogg`. Sidecar JSON zawiera:
`bpm, bar_s, loop, loop_offset (s), loop_offset_samples, loop_len_s, length_s, lufs, true_peak_dbtp, seam`.

## Struktura
| plik | rola |
|---|---|
| `amigamusic/paula.py` | zegar PAL, tablica okresów, `Sample` (8/16-bit, pętla), miks LRRL, filtr A500/LED |
| `amigamusic/instruments.py` | presety chip/„samplowane” 8-bit (`make()`), profile `STYLES` |
| `amigamusic/instruments_hq.py` | presety 16-bit dla profilu `unreal` |
| `amigamusic/songtext.py` | parser formatu `.song` (spec w docstringu) |
| `amigamusic/player.py` | odtwarzacz tick po ticku z efektami PT, echo i pogłos |
| `amigamusic/render.py` | render sekcji, bezszwowa pętla, normalizacja -14 LUFS, OGG + JSON |
| `amigamusic/analyze.py` | LUFS, true-peak, test szwu, PNG (fala + spektrogram), kontrola harmonii |
| `amigamusic/modexport.py`, `s3mexport.py`, `_export.py` | eksport `.mod` (M.K.) i `.s3m` |
| `templates/*.song` | szablony: minimal, cracktro, pinball-table, stinger, unreal |
| `songs/` | przykłady: `example/minimal.song`, `midnight_funfair/*.song`, `menu/menu_unreal.song` |

Pełny przewodnik (format, efekty, profile, procedura komponowania krok po kroku) znajdziesz w
`docs/MUZYKA-AMIGA.md` w repo CopperTilt. Skrót formatu jest w docstringu `songtext.py`.

## Dla aplikacji „prompt → muzyka” (np. Paula Bot)
Zestaw jest samowystarczalny: skopiuj cały katalog `tools/amigamusic/` i niczego więcej nie
potrzebujesz. Zalecany przepływ:
1. Z promptu ustal profil, tonację, tempo, długość pętli i nastrój. Mapowanie nastroju znajdziesz w
   `docs/MUZYKA-AMIGA.md`, rozdz. 6.
2. Wygeneruj `[leadsheet]`: motyw 4–8 taktów, siatkę akordów i formę (intro, A, B, bridge, A').
3. Zacznij od `amigamusic new … --template <profil>`, potem wypełnij wzory. Bas trzyma się
   pryma/kwinta akordu, a na mocnych częściach taktu melodia gra dźwięki akordu.
4. `python3 -m amigamusic check plik.song` zwraca kod 1, gdy harmonia lub szew są złe. Poprawiaj,
   aż wyjdzie `WYNIK: OK`.
5. `render` da OGG gotowe do pętli (`loop_offset` z JSON) oraz opcjonalnie `.mod`/`.s3m`.
API w Pythonie:
```python
from amigamusic import songtext
from amigamusic.render import render_song
song = songtext.parse(text)          # albo songtext.load(path)
render_song(song, "out/", sections=None, fmt="ogg", prefix="", normalize_to=None)
```

## Zasady (clean-room)
Wszystkie sample powstają syntetycznie w kodzie, a wszystkie nuty w `songs/` to własne
kompozycje. Do repo nie trafiają żadne zripowane sample ani moduły. Cudzych modułów wolno używać
tylko do pomiaru statystyk, poza repo.
