#!/usr/bin/env bash
# Menu carousel previews: renders each table in the 3D view (staged still frame, whole table
# visible) in an invisible Xvfb and writes assets/tables/<id>/preview3d.png (600 x 1200).
# usage: tools/make_preview3d.sh [table_id ...]   (default: all tables)
set -euo pipefail
cd "$(dirname "$0")/.."
GODOT=${GODOT:-$HOME/.local/bin/godot}
DISP=${DISP:-:95}
IDS=${*:-$(ls assets/tables)}
W=960; H=2016
Xvfb $DISP -screen 0 ${W}x${H}x24 -nolisten tcp >/dev/null 2>&1 &
XPID=$!
trap 'kill $XPID 2>/dev/null || true' EXIT
sleep 1.5
for id in $IDS; do
	[ -f assets/tables/$id/table.json ] || continue
	case $id in
		copper_speedway) B=160,262;;
		launch_pad) B=150,180;;
		*) B=140,178;;
	esac
	env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE DISPLAY=$DISP \
		timeout 120 "$GODOT" --display-driver x11 --rendering-driver opengl3 --audio-driver Dummy \
		--path . --resolution ${W}x${H} --position 0,0 -- --autostart --windowed --style=modern \
		--view=3d --shadows=1 --lightfx=2 --table=$id --still --still-cam=320 --still-ball=$B \
		--grab-table="$PWD/assets/tables/$id/preview3d.png" 2>&1 | grep -E "\[grab\]|SCRIPT ERROR|SHADER ERROR" || true
done
