#!/usr/bin/env bash
# Screenshots of the game at several aspect ratios, rendered in an invisible Xvfb
# (never touches Adam's Wayland session). Output: shots/<WxH><SUFFIX>.png (gitignored).
# Examples:
#   tools/screenshots.sh
#   RESOLUTIONS=2560x1080 SUFFIX=-b FRAME=900 tools/screenshots.sh
#   RESOLUTIONS=1920x1080 SUFFIX=-title GAME_ARGS= tools/screenshots.sh
set -euo pipefail
cd "$(dirname "$0")/.."
GODOT=${GODOT:-$HOME/.local/bin/godot}
OUT=${OUT:-$PWD/shots}
FRAME=${FRAME:-420}
GAME_ARGS=${GAME_ARGS---autostart --demo}
DISP=${DISP:-:93}
mkdir -p "$OUT"
for RES in ${RESOLUTIONS:-1920x1080 2560x1080 3840x1080 1920x1200 1024x768 1080x1920}; do
	W=${RES%x*}; H=${RES#*x}
	Xvfb $DISP -screen 0 ${W}x${H}x24 -nolisten tcp >/dev/null 2>&1 &
	XPID=$!
	sleep 1.5
	F="$OUT/${RES}${SUFFIX:-}.png"
	rm -f "$F"
	env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE DISPLAY=$DISP \
		timeout 120 "$GODOT" --display-driver x11 --rendering-driver opengl3 --audio-driver Dummy \
		--path . --resolution "${W}x${H}" --position 0,0 \
		-- $GAME_ARGS --windowed --shot="$F" --shot-frame="$FRAME" ${EXTRA:-} >"${F%.png}.log" 2>&1 || true
	[ -f "$F" ] && echo "$F" || echo "FAILED $RES (see ${F%.png}.log)"
	kill $XPID 2>/dev/null || true
	wait $XPID 2>/dev/null || true
done
