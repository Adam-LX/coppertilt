#!/usr/bin/env bash
# Copper Tilt: publikacja na GitHub (kod + binarki).
#   tools/publish.sh stage    czysty snapshot HEAD -> build/publish/src + skan (nic prywatnego / z referencji)
#   tools/publish.sh build    eksport Godot (Linux + Windows) + wersja terminalowa -> build/publish/assets
#   tools/publish.sh push     snapshot jako nowy commit na github.com/Adam-LX/coppertilt (bez force)
#   tools/publish.sh release  release vX.Y.Z w Adam-LX/coppertilt-releases (+ Adam-LX/coppertilt)
#   tools/publish.sh all      wszystko po kolei
# Wersja: config/version w project.godot. Publikowane jest tylko to, co jest w commicie HEAD
# (niezacommitowane zmiany i katalogi Grab/ research/ shots/ dist/ nigdy nie trafiają do snapshotu).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
GH_USER="${GH_USER:-Adam-LX}"
SRC_REPO="${SRC_REPO:-coppertilt}"
REL_REPO="${REL_REPO:-coppertilt-releases}"
GODOT="${GODOT:-$HOME/.local/bin/godot}"
PUB="$ROOT/build/publish"
SRC="$PUB/src"
OUT="$PUB/assets"
HEAVY_LOCK="${HEAVY_LOCK:-/tmp/ct_heavy.lock}"
PY_EMBED_VER="${PY_EMBED_VER:-3.12.10}"
VERSION="$(sed -n 's/^config\/version="\(.*\)"/\1/p' project.godot)"
TAG="v$VERSION"

# Ścieżki, które nigdy nie idą do publicznego repo (notatki wewnętrzne / o referencjach).
EXCLUDE=(AGENTS.md docs/STATUS.md docs/research docs/DZWIEK-KULKI.md Grab research shots dist .godot build)
# Wzorce treści, które blokują publikację (ERE, case-insensitive).
DENY_RE='/home/[a-z]+/|ghp_[A-Za-z0-9]|github_pat_|gho_[A-Za-z0-9]|BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key *[:=]|nosana|basal-serve|ollama|nixos-config|pitchspan|crypto-tv|inj-live|Grab/'
DENY_EXT='\.(mp4|mkv|webm|avi|mov|mod|xm|s3m|it|adf|dms|rom|bin|iso|zip|7z|rar|exe|dll|so|pyz|blend)$'

mkdir -p "$PUB"
exec 8>"$PUB/.publish.lock"
flock -n 8 || { echo "Inny publish.sh już działa." >&2; exit 1; }

gh_() {
	if command -v gh >/dev/null 2>&1; then gh "$@"; else nix shell nixpkgs#gh -c gh "$@" 2> >(grep -v -E "untrusted substituter|man nix.conf|trusted-public-keys" >&2); fi
}

heavy() { # ciężkie zadanie: jedno naraz, >= 8 GB wolnego, limit 6 GB
	exec 7>"$HEAVY_LOCK"; flock -w 3600 7
	local avail; avail=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)
	if (( avail < 8 )); then echo "Za mało pamięci (${avail} GB < 8 GB), przerywam." >&2; exit 1; fi
	systemd-run --user --scope -q -p MemoryMax=6G nice -n 15 "$@"
	local rc=$?; exec 7>&-; return $rc
}

stage() { # stage [katalog]: czysty snapshot HEAD (domyślnie $SRC; build importuje w nim i dokłada .godot)
	local dst="${1:-$SRC}"
	echo "== stage $TAG (HEAD $(git rev-parse --short HEAD)) -> ${dst#$ROOT/} =="
	rm -rf "$dst"; mkdir -p "$dst"
	git archive HEAD | tar -x -C "$dst"
	for p in "${EXCLUDE[@]}"; do rm -rf "${dst:?}/$p"; done
	scan "$dst"
	echo "OK: $(find "$dst" -type f | wc -l) plików, $(du -sh "$dst" | awk '{print $1}')"
}

scan() {
	local dir="$1" bad=0 hits
	hits=$(cd "$dir" && find . -name .git -prune -o -type f -print | sed 's#^\./##' | grep -E -i "$DENY_EXT|(^|/)(Grab|research|shots|dist|\.godot)/" || true)
	[[ -n "$hits" ]] && { echo "BŁĄD: zakazane pliki:" >&2; echo "$hits" >&2; bad=1; }
	hits=$(grep -rIl -i -E "$DENY_RE" "$dir" --exclude-dir=.git --exclude=.gitignore --exclude=publish.sh --exclude=export_presets.cfg || true)
	[[ -n "$hits" ]] && { echo "BŁĄD: prywatne/zakazane wzorce w:" >&2; echo "$hits" >&2; bad=1; }
	local pf="${PRIVATE_PATTERNS:-$HOME/.config/ignite/mirror-private-patterns}"
	if [[ -f "$pf" ]]; then
		hits=$(grep -rIl -i -E -f "$pf" "$dir" --exclude-dir=.git || true)
		[[ -n "$hits" ]] && { echo "BŁĄD: dane prywatne ($pf) w:" >&2; echo "$hits" >&2; bad=1; }
	fi
	hits=$(find "$dir" -name .git -prune -o -type f -size +20M -print)
	[[ -n "$hits" ]] && { echo "BŁĄD: pliki > 20 MB:" >&2; echo "$hits" >&2; bad=1; }
	(( bad == 0 )) || exit 1
	echo "Skan OK (bez Grab/research, bez sekretów i ścieżek prywatnych)."
}

build() {
	[[ -d "$SRC" ]] || stage
	rm -rf "$OUT" "$PUB/dist"; mkdir -p "$OUT" "$PUB/dist/linux" "$PUB/dist/windows"
	local tdir; tdir="$HOME/.local/share/godot/export_templates/$("$GODOT" --version | head -1)"
	[[ -e "$tdir" ]] || ln -s "4.7.2.stable" "$tdir"
	echo "== import (Godot headless) =="
	heavy env -u DISPLAY -u WAYLAND_DISPLAY "$GODOT" --headless --audio-driver Dummy --path "$SRC" --import >"$PUB/import.log" 2>&1 || true
	echo "== export Linux / Windows =="
	heavy env -u DISPLAY -u WAYLAND_DISPLAY "$GODOT" --headless --audio-driver Dummy --path "$SRC" --export-release "Linux" "$PUB/dist/linux/CopperTilt.x86_64" >"$PUB/export-linux.log" 2>&1
	heavy env -u DISPLAY -u WAYLAND_DISPLAY "$GODOT" --headless --audio-driver Dummy --path "$SRC" --export-release "Windows" "$PUB/dist/windows/CopperTilt.exe" >"$PUB/export-windows.log" 2>&1
	for d in linux windows; do cp "$SRC/LICENSE" "$SRC/README.md" "$PUB/dist/$d/"; done
	(cd "$PUB/dist/linux" && python3 -c 'import sys,zipfile,os
z=zipfile.ZipFile(sys.argv[1],"w",zipfile.ZIP_DEFLATED)
for f in sorted(os.listdir(".")):
    zi=zipfile.ZipInfo("CopperTilt/"+f); st=os.stat(f); zi.external_attr=(st.st_mode&0xFFFF)<<16; zi.compress_type=zipfile.ZIP_DEFLATED
    z.writestr(zi,open(f,"rb").read())' "$OUT/CopperTilt-linux-x86_64.zip")
	(cd "$PUB/dist/windows" && python3 -c 'import sys,zipfile,os
z=zipfile.ZipFile(sys.argv[1],"w",zipfile.ZIP_DEFLATED)
for f in sorted(os.listdir(".")): z.write(f,"CopperTilt/"+f)' "$OUT/CopperTilt-windows-x86_64.zip")
	cp "$PUB/dist/windows/CopperTilt.exe" "$OUT/CopperTilt.exe"
	build_cli
	(cd "$OUT" && sha256sum CopperTilt* coppertilt_tty.pyz > SHA256SUMS)
	ls -la "$OUT"
}

build_cli() {
	local w="$PUB/cli"; rm -rf "$w"; mkdir -p "$w/pyz"
	cp "$SRC/tools/terminal/coppertilt_tty.py" "$w/pyz/"
	printf 'import coppertilt_tty, sys\nsys.exit(coppertilt_tty.main())\n' > "$w/pyz/__main__.py"
	python3 -m zipapp "$w/pyz" -p "/usr/bin/env python3" -o "$OUT/coppertilt_tty.pyz"
	echo "== CLI Linux (PyInstaller, przenośny Python) =="
	heavy env -C "$w" uv run --no-project --python 3.12 --python-preference only-managed --with pyinstaller -- \
		pyinstaller --onefile --clean --noconfirm --name CopperTilt-terminal-linux-x86_64 \
		--distpath "$w/dist" --workpath "$w/work" --specpath "$w" "$w/pyz/coppertilt_tty.py" >"$PUB/cli-linux.log" 2>&1
	cp "$w/dist/CopperTilt-terminal-linux-x86_64" "$OUT/"
	echo "== CLI Windows (Python embeddable + windows-curses) =="
	local wd="$w/win/CopperTilt-terminal"; mkdir -p "$wd/python"
	curl -fsSL -o "$w/embed.zip" "https://www.python.org/ftp/python/$PY_EMBED_VER/python-$PY_EMBED_VER-embed-amd64.zip"
	python3 -c 'import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$w/embed.zip" "$wd/python"
	uv pip install --quiet --target "$wd/python/site-packages" --python-platform x86_64-pc-windows-msvc \
		--python-version "${PY_EMBED_VER%.*}" --only-binary :all: windows-curses
	local pth; pth=$(ls "$wd"/python/python3*._pth); printf 'site-packages\n' >> "$pth"
	cp "$SRC/tools/terminal/coppertilt_tty.py" "$wd/"
	cp "$SRC/LICENSE" "$wd/"
	printf '@echo off\r\ncd /d "%%~dp0"\r\nmode con: cols=120 lines=50\r\n"%%~dp0python\\python.exe" "%%~dp0coppertilt_tty.py" %%*\r\n' > "$wd/CopperTilt-terminal.bat"
	printf 'Copper Tilt - wersja terminalowa (Windows)\r\nUruchom CopperTilt-terminal.bat. Python %s jest w paczce (python.org, licencja PSF).\r\n' "$PY_EMBED_VER" > "$wd/CZYTAJ.txt"
	(cd "$w/win" && python3 -c 'import sys,zipfile,os
z=zipfile.ZipFile(sys.argv[1],"w",zipfile.ZIP_DEFLATED)
for r,_,fs in os.walk("CopperTilt-terminal"):
    for f in sorted(fs): z.write(os.path.join(r,f))' "$OUT/CopperTilt-terminal-windows-x86_64.zip")
}

push() {
	local snap="$PUB/pushsrc"
	stage "$snap" # świeży snapshot (src/ po buildzie ma .godot i pliki importu)
	local repo="$PUB/repo" url="git@github.com:$GH_USER/$SRC_REPO.git"
	gh_ repo view "$GH_USER/$SRC_REPO" >/dev/null 2>&1 || gh_ repo create "$GH_USER/$SRC_REPO" --public \
		--description "Copper Tilt — pinball 2D/3D w stylu Amigi (Godot 4.7) + wersja terminalowa"
	if [[ ! -d "$repo/.git" ]]; then
		git clone -q "$url" "$repo" 2>/dev/null || { mkdir -p "$repo"; git -C "$repo" init -q -b main; git -C "$repo" remote add origin "$url"; }
	fi
	git -C "$repo" fetch -q origin 2>/dev/null || true
	if git -C "$repo" rev-parse -q --verify origin/main >/dev/null; then git -C "$repo" checkout -q -B main origin/main; fi
	rsync -a --delete --exclude .git "$snap/" "$repo/"
	scan "$repo" # przed commitem
	git -C "$repo" add -A
	if git -C "$repo" diff --cached --quiet; then echo "Repo bez zmian."; else
		git -C "$repo" -c user.name="$GH_USER" -c user.email="$GH_USER@users.noreply.github.com" \
			commit -q -m "Copper Tilt $VERSION"
	fi
	scan "$repo"
	git -C "$repo" tag -f "$TAG" >/dev/null
	git -C "$repo" push -q origin main
	git -C "$repo" push -q origin "refs/tags/$TAG" 2>/dev/null || echo "(tag $TAG już jest na GitHubie)"
	git remote get-url github >/dev/null 2>&1 || git remote add github "$url"
	echo "Kod: https://github.com/$GH_USER/$SRC_REPO"
}

release() {
	local slug="$GH_USER/$REL_REPO" a=()
	mapfile -t a < <(ls "$OUT"/CopperTilt* "$OUT"/coppertilt_tty.pyz "$OUT"/SHA256SUMS)
	gh_ repo view "$slug" >/dev/null 2>&1 || gh_ repo create "$slug" --public \
		--description "Copper Tilt — binaria (Windows / Linux) + wersja terminalowa"
	local rr="$PUB/rel-repo"
	if [[ ! -d "$rr/.git" ]]; then
		git clone -q "git@github.com:$slug.git" "$rr" 2>/dev/null || { mkdir -p "$rr"; git -C "$rr" init -q -b main; git -C "$rr" remote add origin "git@github.com:$slug.git"; }
	fi
	git -C "$rr" fetch -q origin 2>/dev/null || true
	if git -C "$rr" rev-parse -q --verify origin/main >/dev/null; then git -C "$rr" checkout -q -B main origin/main; fi
	cp "$SRC/DOWNLOADS.md" "$rr/README.md"; cp "$SRC/LICENSE" "$rr/"
	git -C "$rr" add -A
	git -C "$rr" diff --cached --quiet || git -C "$rr" -c user.name="$GH_USER" -c user.email="$GH_USER@users.noreply.github.com" commit -q -m "Copper Tilt $VERSION — pobieranie"
	git -C "$rr" push -q origin main
	local notes="Copper Tilt $VERSION — gra (Windows / Linux) + wersja terminalowa. Kod: https://github.com/$GH_USER/$SRC_REPO · instrukcje: README / DOWNLOADS.md"
	for s in "$slug" "$GH_USER/$SRC_REPO"; do
		if gh_ release view "$TAG" -R "$s" >/dev/null 2>&1; then
			gh_ release upload "$TAG" "${a[@]}" -R "$s" --clobber
		else
			gh_ release create "$TAG" "${a[@]}" -R "$s" --title "Copper Tilt $VERSION" --notes "$notes"
		fi
	done
	echo "Release: https://github.com/$slug/releases/tag/$TAG"
}

case "${1:-}" in
	stage) stage ;;
	build) build ;;
	push) push ;;
	release) release ;;
	all) stage; build; push; release ;;
	*) sed -n '2,9p' "$0"; exit 1 ;;
esac
