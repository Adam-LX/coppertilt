#!/usr/bin/env bash
# Regenerates CopperTilt music + stingers from songs/ into assets/audio/ (never touches title.ogg).
# Usage (repo root or anywhere):  tools/amigamusic/build_coppertilt.sh
# NixOS:  nix-shell -p "python3.withPackages(p: [p.numpy])" ffmpeg --run tools/amigamusic/build_coppertilt.sh
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$KIT/../.." && pwd)"
MUS="$ROOT/assets/audio/music"; STI="$ROOT/assets/audio/stingers"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$MUS" "$STI"
cd "$KIT"

export PYTHONPATH="$KIT"
python3 -m amigamusic render songs/midnight_funfair/midnight_funfair.song -o "$TMP/ff"
python3 -m amigamusic render songs/launch_pad/launch_pad.song -o "$TMP/lp"
python3 -m amigamusic render songs/copper_speedway/copper_speedway.song -o "$TMP/cs"
python3 -m amigamusic render songs/menu/menu_unreal.song -o "$TMP/menu"
python3 -m amigamusic render songs/midnight_funfair/stingers.song -o "$TMP/st"

put() { cp "$1.ogg" "$MUS/$2.ogg"; sed "s/\"file\": \"[^\"]*\"/\"file\": \"$2.ogg\"/" "$1.json" > "$MUS/$2.json"; }
put "$TMP/ff/main" funfair
put "$TMP/ff/multiball" funfair_multiball
put "$TMP/lp/main" launch_pad
put "$TMP/lp/multiball" launch_pad_multiball
put "$TMP/cs/main" copper_speedway
put "$TMP/cs/multiball" copper_speedway_multiball
put "$TMP/menu/ambient" menu
put "$TMP/menu/action" hiscore
cp "$TMP"/st/*.ogg "$STI/"
echo "OK: $MUS (funfair, launch_pad, copper_speedway + multiballs, menu, hiscore) + $STI ($(ls "$STI"/*.ogg | wc -l) stingers); title.ogg untouched"
