extends Control
## Main menu - Amiga style, large and high contrast:
##  table carousel (preview image per table), START, OPTIONS (styl, tempo gry, screen,
##  volumes, controls), HIGH SCORES, QUIT. Keyboard (arrows / Enter / Esc, flippers = left /
##  right) and gamepad (d-pad / stick, A, B). Copper bars, painted art, bouncing logo and
##  the sine scroller stay behind it.

const SCROLL_TEXT := "      COPPER TILT  *  A LOVE LETTER TO THE AMIGA PINBALL ERA  *  PICK A TABLE, HOLD SPACE TO PLUNGE, FLIPPERS ON SHIFT / CTRL / Z / M  -  NUDGE WITH X, N AND UP, BUT MIND THE TILT  *  AFTER THE LAST BALL WATCH THE MATCH: THE SCORE'S TENS DIGIT AGAINST THE ROLL, A HIT IS ONE MORE BALL  *  F9 FLIPS THE LOOK: MODERN OR AMIGA PIXEL  -  F7 / F8 GAME SPEED  -  F11 FULLSCREEN  *  ALL GRAPHICS AND MUSIC ARE ORIGINAL  *  GREETINGS TO EVERY TRACKER MUSICIAN AND DEMO CODER OUT THERE  *  "
const C_SEL := Color(1.0, 0.92, 0.25)
const C_TXT := Color(1, 1, 1)
const C_DIM := Color(0.62, 0.66, 0.8)
const C_ACC := Color(0.35, 1.0, 1.0)

var backdrop: CopperBackdrop
var _time := 0.0
var _font: Font
var _scroll_x := 0.0
var _art: Texture2D = preload("res://assets/art/title_art.png")
var _logo: Texture2D = preload("res://assets/art/logo.png")
var _tables: Array = []
var _previews: Dictionary = {}
var _ti := 0                   # selected table
var _slide := 0.0              # carousel slide animation (-1..1)
var page := "main"             # main | options | scores | controls
var sel := 0
var _idle := 0.0


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_font = ThemeDB.fallback_font
	backdrop = CopperBackdrop.new()
	backdrop.floor_start = 1.5
	backdrop.show_behind_parent = true
	add_child(backdrop)
	_tables = Settings.tables()
	for i in _tables.size():
		var t: Dictionary = _tables[i]
		var p: String = t.dir + str(t.get("preview", "preview.png"))
		if ResourceLoader.exists(p):
			_previews[t.id] = load(p)
		if t.id == Settings.table_id:
			_ti = i
	get_viewport().size_changed.connect(_fit)
	_fit()
	Sound.play_music("title")
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--menu-page="):
			page = a.get_slice("=", 1)
		elif a.begins_with("--menu-sel="):
			sel = int(a.get_slice("=", 1))
	if Settings.autostart:
		_go.call_deferred()


func _fit() -> void:
	backdrop.position = Vector2.ZERO
	backdrop.size = get_viewport_rect().size


func _sting(n: String, fallback := "") -> void:
	if Sound.has_method("play_stinger"):
		Sound.call("play_stinger", n)
	elif fallback != "":
		Sound.play(fallback)


func _table() -> Dictionary:
	return _tables[_ti] if _tables.size() > 0 else {"id": "midnight_funfair", "name": "MIDNIGHT FUNFAIR", "subtitle": "", "playable": true}


func _go() -> void:
	if not bool(_table().get("playable", true)):
		_sting("menu_denied", "warn")
		return
	Settings.table_id = str(_table().id)
	Settings.set_tempo(Settings.tempo)       # saves the selection too
	get_tree().change_scene_to_file("res://scenes/game.tscn")


# --- menu model ----------------------------------------------------------------

func _items() -> Array:
	match page:
		"options":
			return [
				["STYLE", Settings.style_name()],
				["VIEW", Settings.view_name() if Settings.style == "modern" else "2D (PIXEL)"],
				["3D SHADOWS", Settings.shadows_name()],
				["LIGHT FX", Settings.lightfx_name()],
				["GAME SPEED", "%d%%" % roundi(Settings.tempo * 100.0)],
				["SCREEN", "FULLSCREEN" if Settings.fullscreen else "WINDOW"],
				["MUSIC", _bar(Settings.music_volume)],
				["EFFECTS", _bar(Settings.sfx_volume)],
				["CONTROLS", ""],
				["BACK", ""]]
		"scores", "controls":
			return [["BACK", ""]]
	return [["TABLE", str(_table().name)], ["START", ""], ["OPTIONS", ""], ["HIGH SCORES", ""], ["QUIT", ""]]


func _bar(v: float) -> String:
	var n := roundi(v * 10.0)
	return "|".repeat(n) + ".".repeat(10 - n) + "  %d%%" % roundi(v * 100.0)


func _activate(label: String, dir: int) -> void:
	# dir: 0 = accept, -1 / +1 = left / right
	match label:
		"TABLE":
			if dir != 0 and _tables.size() > 1:
				_ti = (_ti + dir + _tables.size()) % _tables.size()
				_slide = float(dir)
				_sting("menu_move", "flipper")
			elif dir == 0:
				_start()
		"START":
			if dir == 0:
				_start()
		"OPTIONS":
			if dir == 0:
				_page("options")
		"HIGH SCORES":
			if dir == 0:
				_page("scores")
			elif _tables.size() > 1:
				_ti = (_ti + dir + _tables.size()) % _tables.size()
		"QUIT":
			if dir == 0:
				get_tree().quit()
		"STYLE":
			Settings.toggle_style()
		"VIEW":
			Settings.toggle_view()
		"3D SHADOWS":
			Settings.toggle_shadows()
		"LIGHT FX":
			var n := Settings.lightfx + (dir if dir != 0 else 1)
			if dir == 0 and n > 2:
				n = 0
			Settings.set_lightfx(n)
		"GAME SPEED":
			var t := Settings.tempo + 0.05 * (dir if dir != 0 else 1)
			if dir == 0 and Settings.tempo >= Settings.TEMPO_MAX - 0.001:
				t = Settings.TEMPO_MIN
			Settings.set_tempo(t)
		"SCREEN":
			Settings.toggle_fullscreen(true)
		"MUSIC", "EFFECTS":
			var k := "music" if label == "MUSIC" else "sfx"
			var v: float = Settings.music_volume if k == "music" else Settings.sfx_volume
			v += 0.1 * (dir if dir != 0 else 1)
			if dir == 0 and v > 1.05:
				v = 0.0
			Settings.set_volume(k, v)
			Sound.play("bumper")
		"CONTROLS":
			if dir == 0:
				_page("controls")
		"BACK":
			if dir == 0:
				_back()


func _start() -> void:
	_sting("menu_start", "start")
	_go()


func _page(p: String) -> void:
	page = p
	sel = 0
	_sting("menu", "rollover")


func _back() -> void:
	match page:
		"main":
			pass
		"controls":
			page = "options"
			sel = 5
		_:
			sel = 2 if page == "options" else 3
			page = "main"
	_sting("menu_back", "flipper_down")


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and (event as InputEventKey).echo and not (event.is_action(&"ui_up") or event.is_action(&"ui_down")):
		return
	var items := _items()
	var moved := false
	if event.is_action_pressed(&"ui_up", true):
		sel = (sel - 1 + items.size()) % items.size()
		moved = true
	elif event.is_action_pressed(&"ui_down", true):
		sel = (sel + 1) % items.size()
		moved = true
	elif event.is_action_pressed(&"ui_left") or event.is_action_pressed(&"flip_left"):
		_activate(items[sel][0], -1)
	elif event.is_action_pressed(&"ui_right") or event.is_action_pressed(&"flip_right"):
		_activate(items[sel][0], 1)
	elif event.is_action_pressed(&"back") or event.is_action_pressed(&"ui_cancel"):
		if page == "main":
			sel = items.size() - 1          # jump to QUIT, a second Esc quits
			if _idle < 0.0:
				get_tree().quit()
			_idle = -1.5
		else:
			_back()
	elif event.is_action_pressed(&"ui_accept") or event.is_action_pressed(&"start"):
		_activate(items[sel][0], 0)
	else:
		return
	if moved:
		_sting("menu_move", "rollover")
	get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	_time += delta
	_idle = minf(_idle + delta, 0.0) if _idle < 0.0 else _idle
	_slide = move_toward(_slide, 0.0, delta * 4.0)
	queue_redraw()


# --- drawing ---------------------------------------------------------------------

func _text(text: String, p: Vector2, fs: int, col: Color, outline := -1) -> void:
	var o := outline if outline >= 0 else maxi(4, fs / 7)
	draw_string_outline(_font, p, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, o, Color.BLACK)
	draw_string(_font, p, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)


func _tw(text: String, fs: int) -> float:
	return _font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x


func _centered(text: String, cx: float, y: float, fs: int, col: Color) -> void:
	_text(text, Vector2(cx - _tw(text, fs) * 0.5, y), fs, col)


func _fit_fs(text: String, fs: int, max_w: float) -> int:
	var w := _tw(text, fs)
	return fs if w <= max_w else maxi(12, int(fs * max_w / w))


func _draw() -> void:
	var s := size
	# painted panorama behind everything, darkened for contrast
	var ak := maxf(s.y / _art.get_height(), s.x / _art.get_width())
	var aw := _art.get_size() * ak
	draw_texture_rect(_art, Rect2((s - aw) * 0.5, aw), false)
	draw_rect(Rect2(Vector2.ZERO, s), Color(0, 0, 0.06, 0.45))
	var landscape := s.x >= s.y * 1.15
	var fs := int(clampf(s.y / 15.0, 26.0, 120.0))
	var scroll_h := clampf(s.y / 9.0, 50.0, 150.0)
	var area := Rect2(0, 0, s.x, s.y - scroll_h)
	var prev_rect: Rect2
	var menu_rect: Rect2
	if landscape:
		var pw := minf(area.size.y * 0.74 * 0.5, s.x * 0.36)
		prev_rect = Rect2(s.x * 0.27 - pw * 0.5, area.size.y * 0.05, pw, pw * 2.0)
		menu_rect = Rect2(s.x * 0.5, area.size.y * 0.04, s.x * 0.47, area.size.y * 0.94)
	else:
		var ph := area.size.y * 0.32
		prev_rect = Rect2(s.x * 0.5 - ph * 0.25, area.size.y * 0.15, ph * 0.5, ph)
		menu_rect = Rect2(s.x * 0.05, area.size.y * 0.62, s.x * 0.9, area.size.y * 0.38)
		fs = int(clampf(s.x / 14.0, 26.0, 110.0))
	# logo
	var lk := minf(menu_rect.size.x * 0.9 / _logo.get_width(), area.size.y * (0.2 if landscape else 0.13) / _logo.get_height())
	var lw := _logo.get_size() * lk
	var ly := (menu_rect.position.y if landscape else area.size.y * 0.015) + sin(_time * 2.0) * lw.y * 0.04
	var lcx := menu_rect.get_center().x if landscape else s.x * 0.5
	draw_texture_rect(_logo, Rect2(Vector2(lcx - lw.x * 0.5, ly), lw), false)
	_draw_carousel(prev_rect, fs)
	var top := (ly + lw.y + fs * 0.6) if landscape else menu_rect.position.y
	match page:
		"scores":
			_draw_scores(Rect2(menu_rect.position.x, top, menu_rect.size.x, menu_rect.end.y - top), fs)
		"controls":
			_draw_controls(Rect2(menu_rect.position.x, top, menu_rect.size.x, menu_rect.end.y - top), fs)
		_:
			_draw_items(Rect2(menu_rect.position.x, top, menu_rect.size.x, menu_rect.end.y - top), fs)
	_draw_scroller(s, scroll_h)


func _draw_carousel(r: Rect2, fs: int) -> void:
	var n := _tables.size()
	var on_table := page == "main" and sel == 0
	# neighbours, small and dim, behind
	if n > 1:
		for d in [-1, 1]:
			var t: Dictionary = _tables[(_ti + d + n) % n]
			var nr := Rect2(r.position + Vector2(d * r.size.x * 0.62 + r.size.x * 0.2, r.size.y * 0.1), r.size * 0.6)
			var tex: Texture2D = _previews.get(t.id)
			if tex:
				draw_texture_rect(tex, nr, false, Color(0.45, 0.45, 0.55))
			draw_rect(nr, Color(0.4, 0.4, 0.6), false, 3.0)
	var t0 := _table()
	var rr := Rect2(r.position + Vector2(_slide * r.size.x * 0.4, 0), r.size)
	draw_rect(rr.grow(fs * 0.18), Color(0, 0, 0, 0.75))
	var tex0: Texture2D = _previews.get(t0.id)
	if tex0:
		draw_texture_rect(tex0, rr, false)
	else:
		draw_rect(rr, Color(0.08, 0.05, 0.2))
		_centered("NO PREVIEW", rr.get_center().x, rr.get_center().y, fs / 2, C_DIM)
	if not bool(t0.get("playable", true)):
		draw_rect(rr, Color(0, 0, 0, 0.55))
		_centered("COMING SOON", rr.get_center().x, rr.get_center().y, fs, C_SEL)
	var frame_col := C_SEL if on_table and fmod(_time, 0.6) < 0.4 else Color(0.85, 0.85, 1.0)
	draw_rect(rr.grow(fs * 0.12), frame_col, false, maxf(4.0, fs * 0.1))
	# name plate under the preview
	var tname: String = str(t0.name)
	var nfs := _fit_fs(tname, int(fs * 0.8), r.size.x * 1.5)
	var ny := rr.end.y + fs * 0.25
	draw_rect(Rect2(rr.get_center().x - r.size.x * 0.8, ny, r.size.x * 1.6, nfs * 1.35), Color(0, 0, 0, 0.8))
	_centered(tname, rr.get_center().x, ny + nfs * 1.05, nfs, C_ACC)
	if n > 1:
		var afs := int(fs * 1.3)
		var ay := rr.get_center().y + afs * 0.35
		var pulse := sin(_time * 6.0) * fs * 0.1
		_text("<", Vector2(rr.position.x - afs * 0.9 - pulse, ay), afs, C_SEL if on_table else C_TXT)
		_text(">", Vector2(rr.end.x + afs * 0.35 + pulse, ay), afs, C_SEL if on_table else C_TXT)
		# dots: which table of how many
		for i in n:
			var c := Vector2(rr.get_center().x + (i - (n - 1) * 0.5) * fs * 0.6, ny + nfs * 1.35 + fs * 0.45)
			draw_circle(c, fs * 0.16, C_SEL if i == _ti else Color(0.5, 0.5, 0.6))


func _draw_items(r: Rect2, fs: int) -> void:
	var items := _items()
	var gap := minf(fs * 1.45, r.size.y / (items.size() + 0.5))
	var ifs := int(minf(fs, gap / 1.4))
	var y := r.position.y
	if page == "options":
		_centered("OPTIONS", r.get_center().x, y + ifs, ifs, C_ACC)
		y += gap * 1.05
		gap = minf(gap, (r.end.y - y) / (items.size() + 0.3))
		ifs = int(minf(ifs, gap / 1.4))
	for i in items.size():
		var label: String = items[i][0]
		var value: String = items[i][1]
		var is_sel := i == sel
		var bar := Rect2(r.position.x, y + gap * 0.06, r.size.x, gap * 0.88)
		if is_sel:
			draw_rect(bar, Color(0.1, 0.05, 0.45, 0.92))
			draw_rect(bar, C_SEL, false, maxf(3.0, ifs * 0.08))
		else:
			draw_rect(bar, Color(0, 0, 0, 0.55))
		var by := bar.position.y + bar.size.y * 0.5 + ifs * 0.36
		var col := C_SEL if is_sel else C_TXT
		if value == "":
			_centered(label, r.get_center().x, by, ifs, col)
		else:
			var lx := r.position.x + ifs * 0.5
			_text(label, Vector2(lx, by), ifs, col)
			var vfs := _fit_fs(value, ifs, r.size.x - _tw(label, ifs) - ifs * 2.6)
			var vx := r.end.x - ifs * 0.5 - _tw(value, vfs)
			_text(value, Vector2(vx, by), vfs, C_ACC if not is_sel else C_SEL)
			if is_sel:
				_text("<", Vector2(vx - ifs * 0.75, by), ifs, C_SEL)
		y += gap
	# hint line
	var hint := "ARROWS / D-PAD   ENTER / A = OK   ESC / B = BACK"
	if page == "options":
		hint = "LEFT / RIGHT CHANGES THE VALUE"
	var hfs := _fit_fs(hint, int(ifs * 0.62), r.size.x)
	if y + hfs * 1.6 < r.end.y + hfs:
		_centered(hint, r.get_center().x, y + hfs * 1.5, hfs, C_DIM)


func _draw_scores(r: Rect2, fs: int) -> void:
	var t0 := _table()
	var hs := Settings.scores_for(str(t0.id))
	var gap := minf(fs * 1.25, r.size.y / (hs.size() + 3.2))
	var ifs := int(minf(fs, gap / 1.25))
	var y := r.position.y + ifs
	_centered("HIGH SCORES", r.get_center().x, y, ifs, C_ACC)
	y += gap * 0.75
	var sfs := _fit_fs(str(t0.name), int(ifs * 0.6), r.size.x)
	_centered(str(t0.name), r.get_center().x, y, sfs, C_DIM)
	y += gap * 0.9
	for i in hs.size():
		var col := C_SEL if i == 0 else C_TXT
		draw_rect(Rect2(r.position.x, y - ifs * 1.0, r.size.x, gap * 0.9), Color(0, 0, 0, 0.6))
		_text("%d." % (i + 1), Vector2(r.position.x + ifs * 0.4, y), ifs, col)
		_text(str(hs[i][0]), Vector2(r.position.x + ifs * 1.8, y), ifs, col)
		var sc := Util.fmt_score(int(hs[i][1]))
		_text(sc, Vector2(r.end.x - ifs * 0.4 - _tw(sc, ifs), y), ifs, col)
		y += gap
	var bfs := int(ifs * 0.8)
	draw_rect(Rect2(r.position.x, y - bfs * 0.9, r.size.x, bfs * 1.3), Color(0.1, 0.05, 0.45, 0.92))
	draw_rect(Rect2(r.position.x, y - bfs * 0.9, r.size.x, bfs * 1.3), C_SEL, false, 3.0)
	_centered("BACK", r.get_center().x, y + bfs * 0.2, bfs, C_SEL)


func _draw_controls(r: Rect2, fs: int) -> void:
	var rows := [
		["FLIPPERS", "SHIFT / CTRL / Z, M  -  LB, RB"],
		["PLUNGER", "HOLD SPACE / DOWN  -  A"],
		["NUDGE", "X, N, UP  -  X, B, Y"],
		["PAUSE", "P  -  START"],
		["STYLE / SPEED", "F9  /  F7, F8"],
		["FULLSCREEN", "F11, ALT+ENTER"],
		["MENU", "ESC  -  BACK"]]
	var gap := minf(fs * 1.1, r.size.y / (rows.size() + 2.4))
	var ifs := int(minf(fs * 0.62, gap / 1.25))
	var y := r.position.y + fs * 0.9
	_centered("CONTROLS", r.get_center().x, y, int(fs * 0.9), C_ACC)
	y += gap
	for row in rows:
		draw_rect(Rect2(r.position.x, y - ifs * 1.0, r.size.x, gap * 0.9), Color(0, 0, 0, 0.6))
		_text(row[0], Vector2(r.position.x + ifs * 0.4, y), ifs, C_SEL)
		var v: String = row[1]
		var vfs := _fit_fs(v, ifs, r.size.x * 0.58)
		_text(v, Vector2(r.end.x - ifs * 0.4 - _tw(v, vfs), y), vfs, C_TXT)
		y += gap
	var bfs := int(fs * 0.7)
	draw_rect(Rect2(r.position.x, y - bfs * 0.9, r.size.x, bfs * 1.3), Color(0.1, 0.05, 0.45, 0.92))
	draw_rect(Rect2(r.position.x, y - bfs * 0.9, r.size.x, bfs * 1.3), C_SEL, false, 3.0)
	_centered("BACK", r.get_center().x, y + bfs * 0.2, bfs, C_SEL)


func _draw_scroller(s: Vector2, h: float) -> void:
	draw_rect(Rect2(0, s.y - h, s.x, h), Color(0, 0, 0.04, 0.6))
	var sfs := int(h * 0.55)
	_scroll_x -= get_process_delta_time() * sfs * 4.0
	var text_w := _tw(SCROLL_TEXT, sfs)
	if _scroll_x < -text_w:
		_scroll_x += text_w
	var sx := _scroll_x
	var sy := s.y - h * 0.32
	for rep in 2:
		for i in SCROLL_TEXT.length():
			var ch := SCROLL_TEXT[i]
			var cw := _tw(ch, sfs)
			if sx > -cw and sx < s.x:
				var yy := sy + sin(sx * 0.006 + _time * 3.0) * h * 0.12
				var col := Color.from_hsv(fposmod(sx / s.x * 0.5 + _time * 0.2, 1.0), 0.6, 1.0)
				draw_string_outline(_font, Vector2(sx, yy), ch, HORIZONTAL_ALIGNMENT_LEFT, -1, sfs, sfs / 7, Color.BLACK)
				draw_string(_font, Vector2(sx, yy), ch, HORIZONTAL_ALIGNMENT_LEFT, -1, sfs, col)
			sx += cw
