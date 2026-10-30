# Muzyka w stylu Amigi: przewodnik (krok po kroku)

Narzędzie: `tools/amigamusic/` (Python + numpy, bez GPU i bez sieci). Ten dokument opisuje, jak
napisać, sprawdzić i wyrenderować nowy utwór oraz jak gra przełącza muzykę.
Intro/cracktro (`assets/audio/music/title.ogg`) jest **osobnym, nietykanym plikiem**. Generator go
nie nadpisuje i to on wyznacza styl.

## 0. Uruchamianie
```bash
cd tools/amigamusic
# NixOS (brak numpy w systemie):
nix-shell -p python3Packages.numpy ffmpeg --run 'python3 -m amigamusic check songs/midnight_funfair/midnight_funfair.song'
```
Polecenia:

| polecenie | co robi |
|---|---|
| `new NAZWA --template T -o plik.song` | nowy utwór z szablonu `minimal / cracktro / pinball-table / stinger / unreal` |
| `check plik.song [-v]` | harmonia (nuty vs `chords:`, symbolicznie **i** z dźwięku), długości, szew pętli, LUFS; kod wyjścia 1 = popraw |
| `render plik.song -o katalog [-s sekcja] [--png] [--wav] [--mod x.mod] [--s3m x.s3m] [--prefix p_]` | OGG + JSON dla każdej sekcji, opcjonalnie PNG (fala + spektrogram z markerem pętli) |
| `dump plik.song` | wzory w postaci siatki trackera (`C-3 05 A02`) |
| `instruments [--profile P]` | lista presetów i profili |

Zasada OOM na maszynie Adama: ciężkie rendery uruchamiaj przez
`systemd-run --user --scope -p MemoryMax=6G nice -n 15 python3 -m amigamusic render …`.
Odsłuch nie jest potrzebny do weryfikacji, bo `check` i `--png` sprawdzają wszystko offline.

## 1. Procedura komponowania (rób dokładnie w tej kolejności)
1. **Lead sheet najpierw.** W sekcji `[leadsheet]` zapisz tonację, tempo, formę (np.
   `IN | A A' B BR A''`), siatkę akordów na każdy takt i **motyw** do zanucenia (4–8 taktów).
   Bez lead sheetu nie piszemy nut.
2. **Motyw.** Ma 2–4 dźwięki rozpoznawcze (np. skok w górę po dźwiękach akordu), rytmicznie prosty.
   Na mocnych częściach taktu (wiersze 0/4/8/12) gra dźwięki akordu, a przejściowe stawia na
   słabych. Ostatni takt frazy kończy się „pytaniem” (dominanta) albo „odpowiedzią” (tonika).
3. **Akordy i prowadzenie głosów.** Pady i arpeggio przechodzą najbliższą drogą (np. A-C-E →
   A-C-F → G-C-E → G-B-D). Funkcje: T–Tp–S–D (C–Am–F–G7), w części B subdominanta i jej moll (F–Fm),
   w bridge'u równoległa moll z dominantą (Am–E7).
4. **Bas** trzyma się prymy i kwinty akordu i gra razem ze stopą („oom-pah”: pryma na 1 i 3,
   akord na 2 i 4, albo skoki oktawowe ósemkami jak w modułach Amigi).
5. **Pytanie i odpowiedź.** Lead gra frazę, a w jej pauzie odpowiada arpeggio albo dzwonek.
   Kanał 4 w PT jest rzadszy, bo zostawia miejsce na SFX gry.
6. **Przejścia i dynamika.** Na końcu frazy wstaw przejście bębnów (`fill`), a na początku nowej
   części talerz. Głośności układaj warstwami: intro cicho, A pełniej, bridge lżej, A'' najpełniej.
7. **`check` i poprawki**, aż `WYNIK: OK`: ≥ 80% mocnych nut w akordzie, ≤ 3% nut poza tonacją,
   ≥ 75% taktów, których chroma z dźwięku pasuje do zapisanego akordu.
8. **`render --png`**. Obejrzyj PNG: równy poziom w pętli, brak dziury lub piku na markerze pętli,
   spektrum bez pustych pasm. Sprawdź `seam.verdict == OK` i LUFS ≈ -14.

## 2. Format `.song`
Plik tekstowy. Komentarz to `#` na początku linii albo po spacji (`C#3` to nuta). Bloki:
- **nagłówek** `klucz wartość`: `title, author, profile, speed, tempo, channels, pan (L R R L
  albo liczby 0..1 na kanał), stereo (0..1), filter (none|a500|led|a1200), key ("C major",
  "A minor"), reverb, send (lista 0..1 na kanał), delay ("rzędy feedback mix"), interp (zoh|linear),
  rate, normalize (LUFS), tail (s, dla dżingli)`;
- `[instruments]`: `NN nazwa preset [opcja=wartość]`, np. `05 lead calliope vol=60`;
- `[leadsheet]`: dowolny tekst (zachowywany dosłownie);
- `[track nazwa]`: sekwencja tokenów wielokrotnego użytku. W wzorze wołasz ją przez `nazwa`,
  `nazwa+5` (transpozycja), `nazwa*4` (powtórzenie) albo `nazwa-2*2`;
- `[pattern NAZWA rows=64]`: linia `chords: C Am F,G G7` (akord na takt po 16 wierszy,
  `F,G` = pół na pół, `N` = bez akordu), potem `chN: tokeny…`;
- `[order NAZWA opcje]`: lista wzorów, gdzie `|` oddziela intro od pętli. Opcje to `speed=`,
  `tempo=`, `tail=`, `normalize=`. Każda sekcja daje osobny plik audio.

Token = jeden wiersz (albo N wierszy z `*N`). Kolejność: **nuta, vNN, @instrument, !efekt, \*N**.

| token | znaczenie |
|---|---|
| `C-2`, `C#3` | nuta (PT: C-1..B-3; `unreal`: C-0..B-7); C-2 = 8287 Hz jak w ProTrackerze |
| `.` / `.*7` | pusty wiersz / 7 pustych |
| `^` | wycięcie nuty |
| `v40` | głośność 0..64 (w `.mod` jako Cxx albo wariant sampla) |
| `@lead` / `@05` | instrument (zmiana instrumentu resetuje głośność do domyślnej sampla, jak w PT) |
| `!A02` | efekt tylko w pierwszym wierszu tokenu |
| `!!047` | efekt w każdym wierszu tokenu (arpeggio, vibrato, slide) |

Efekty (semantyka ProTrackera, tick po ticku):
`0xy` arpeggio, `1xx/2xx` portamento w górę i w dół, `3xx` tone-porta, `4xy` vibrato, `5xy/6xy`,
`8xx` panorama, `9xx` offset sampla, `Axy` przesuw głośności, `Cxx` głośność, `Dxx` przerwa wzoru,
`E1x/E2x` drobna porta, `E9x` retrigger, `EAx/EBx`, `ECx` cięcie, `EDx` opóźnienie,
`Fxx` speed (<32) / tempo (≥32). Czas wiersza = speed × 2,5 / tempo s, a BPM = tempo × 6 / speed.

Przykład:
```
[pattern A1 rows=64]
chords: C Am F G7
ch1: bt bt bt fill
ch2: oom oom+9 oom+5 oom+7
ch3: G-2@lead*4 C-3*4 E-3*4 G-3*4 A-3*16 F-3*4 E-3*4 C-3*8 D-3*8 B-2*8
ch4: C-2v20@arp!!047*16 A-1v20@arp!!037*16 F-1v20@arp!!047*16 G-1v20@arp!!04A*16
```

## 3. Profile
| profil | kanały | sample | speed/tempo | stereo/filtr | do czego |
|---|---|---|---|---|---|
| `cracktro` | 4, LRRL | 8-bit chip (pętle 16–64 B) | 6/125 | 1.0 / LED | intra, krótkie pętle |
| `demo` | 4 | 8-bit „samplowane” | 6/125 | 0.8 / A500 | dłuższe formy |
| `pinball-table` | 4 | 8-bit | 6/132 | 0.7 / A500 | temat stołu 60–90 s, pętla bez szwu |
| `multiball` | 4 | 8-bit | 5/132 (×1,2) | 0.7 / A500 | szybsza wersja tematu |
| `stinger` | 4 | 8-bit | 4/125 | 0.7 / A500 | dżingle bez pętli, z ogonem |
| `unreal` | 16 (do 32) | 16-bit HQ, interpolacja liniowa | 6/125 | panorama per kanał, echo + pogłos | menu (styl PC-trackerów końca lat 90.) |

Zasada projektu: **Midnight Funfair zostaje klasycznie 4-kanałowy (PT)**. Profil `unreal` służy
tylko do menu (ambient) i ekranu rekordów (action). Rozwijając `unreal`, dodawaj sekcje ambient
i action na tej samej siatce akordów, a echo pisz na kanale `send` (w oryginalnych modułach
robiono to ręcznie, kopiując nuty ciszej o 3–6 wierszy później).

Presety: `python3 -m amigamusic instruments`. Bas (`chip_bass`, `pulse_bass`, `slap_bass`,
`hq_bass`) brzmi oktawę niżej niż zapis. Perkusja jest strojona pod C-3.

## 4. Pliki w grze i przełączanie
> **Status:** podłączone w grze (`scripts/autoload/sound.gd`, pliki w `assets/audio/`, test
> `tests/sound_test.tscn`). Pliki odtworzysz skryptem `tools/amigamusic/build_coppertilt.sh`.

```
assets/audio/music/title.ogg                  intro/cracktro – NIETYKANE (osobny plik)
assets/audio/music/menu.ogg (+.json)          menu, profil unreal, sekcja ambient
assets/audio/music/hiscore.ogg (+.json)       ekran wyników / wpis rekordu, unreal, sekcja action
assets/audio/music/funfair.ogg (+.json)       Midnight Funfair, temat stołu (intro + pętla)
assets/audio/music/funfair_multiball.ogg      Midnight Funfair, multiball (ta sama tonacja)
assets/audio/stingers/<nazwa>.ogg             dżingle wołane przez Sound.play_stinger(nazwa)
```
`scripts/autoload/sound.gd`:
- `play_music(nazwa)` czyta sidecar JSON (`loop_offset`, `bar_s`). Pętla OGG zaczyna się od
  `loop_offset`, więc intro gra raz, a pętla bez szwu. Zmiana utworu to crossfade ok. 0,6 s.
- `"title"`: najpierw gra `title.ogg` (intro/cracktro) w całości. Gdy się skończy, menu płynnie
  przechodzi w `menu.ogg`. Po powrocie z gry `"title"` od razu oznacza `menu`.
- Multiball: `sound.gd` obserwuje `table.multiball` (zmienna stołu) i przełącza
  `funfair` ↔ `funfair_multiball` **na najbliższej granicy taktu** (`bar_s` z JSON) z krótkim
  crossfade'em. Oba utwory są w C-dur przy 132 BPM (multiball ×1,2), więc przejście nie zgrzyta.
- `play_stinger(nazwa)`: jeśli plik nie istnieje, nic się nie dzieje (cisza, bez błędu). Dżingle
  muzyczne przyciszają muzykę (ducking) na czas trwania. Blipy UI (`menu_*`, `match_tick`)
  idą głośnością efektów.
- `refresh_volume()` czyta `Settings.music_volume` i `Settings.sfx_volume` i stosuje je od razu
  do muzyki i grających dżingli (woła to `Settings.set_volume`).

Lista dżingli: `match, match_miss, match_tick, extra_chance, game_over, final_score, highscore,
menu, menu_move, menu_back, menu_start, menu_denied` oraz `ball_lost, extra_ball, jackpot`.

## 5. Weryfikacja offline (bez odsłuchu)
- `check`: harmonia, szew (`ratio` skoku na szwie vs typowe różnice próbek, `rms_jump_db`), LUFS.
- `render --png`: obejrzyj PNG.
- LUFS kontrolnie ffmpeg-iem: `ffmpeg -i x.ogg -af ebur128=peak=true -f null -` (nasz pomiar
  bywa ok. 0,1–0,25 dB niższy).
- `.mod`/`.s3m`: `ffmpeg -i x.mod x.wav` (libopenmpt) i porównaj chroma i obwiednię z naszym
  renderem. Dla Midnight Funfair zgodność chroma wynosi ok. 1,00.

## 6. Notatki stylu na kolejne stoły (tylko kierunek, jeszcze nie skomponowane)
**Launch Pad (kosmos).** Profil `demo` albo `pinball-table`, 4 kanały, D-dorycka lub
e-eolska z podwyższonym 4. stopniem (lidyjski blask). Tempo 120–125 BPM (speed 6). Instrumenty:
`pwm_lead` z wolnym vibrato `4xy` (x=2..3, y=3..4), `strings_pad` / `tri_pad` jako tło, `bell`
na odpowiedziach, bas `chip_bass` ósemkami z oktawą. Motyw w kwartach i kwintach (fanfara
„startu”), w bridge'u odliczanie: repetycje jednej nuty z `E9x` i crescendo `Axy`. Multiball:
speed 5 i stopa na każdą ćwierćnutę. Dżingiel „lift-off” to portamento `1xx` w górę na całym
akordzie.

**Copper Speedway (wyścigi).** Profil `pinball-table`/`multiball`, 4 kanały, a-moll lub e-moll
z mocną dominantą, 140–150 BPM (speed 5 / tempo 125, albo speed 6 / tempo 150). Bas szesnastkami
w oktawach (`slap_bass`), werbel na 2 i 4 z podwójnymi uderzeniami, lead `detune_lead` z krótkim
`3xx` (podjazdy jak zmiana biegów). Arpeggio `0xy` szybkie i jasne (047/037). Przejścia to
tom-tomy i `orch_hit`. Pętla krótsza (32 takty ≈ 55 s), bo wyścig męczy. Multiball/„nitro”
modulują o cały ton w górę (transpozycja ścieżek `+2`).

**Mapowanie nastroju (dla generatora z promptu):**

| nastrój | tryb | tempo | profil | instrumenty |
|---|---|---|---|---|
| wesoły, jarmarczny | dur | 125–140 | pinball-table | calliope, bell, chip_square |
| tajemniczy | moll/dorycki | 85–100 | unreal | hq_pad, hq_choir, hq_glass |
| akcja | moll | 125–150 | unreal/multiball | hq_taiko, hq_strings, hq_saw_lead |
| retro-intro | dur/moll | 125 | cracktro | chip_square, chip_pulse, pulse_bass, arpeggio 0xy |

## 7. Pułapki
- Po wyjściu z trybu PT (nuta > B-3 w profilu 4-kanałowym) dostaniesz błąd. Przenieś nutę o
  oktawę albo użyj `unreal`.
- Wzór, który zaczyna się nutą bez instrumentu, gra instrumentem z poprzedniego wzoru (jak w PT).
  `check` to uwzględnia, ale bezpieczniej jest dać `@instrument` na starcie wzoru.
- Arpeggio `!!047` na akordzie molowym to błąd. Moll to `037`, dominanta septymowa to `04A`.
- Dżingle UI renderuj z `normalize=-20` lub niżej, bo blip na -14 LUFS byłby głośniejszy od muzyki.
