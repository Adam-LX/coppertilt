extends Node
## Global settings, input map and display toggles (autoload "Settings").
##
## Command-line user args (after `--`):
##   --autostart  skip title, go straight to the table
##   --demo       autopilot plays the table (attract mode / screenshots)
##   --windowed   run in a window this time (never saved)
##   --shot=PATH  save a PNG of the whole window after --shot-frame=N frames (default 420), then quit
##   --style=modern|pixel   override the table style for this run (not saved)
##   --tempo=0.85           override the game tempo for this run (not saved)
##   --table=<id>           play assets/tables/<id> this run (not saved)
##   --view=3d|2d  --shadows=0|1  --lightfx=0|1|2   override the 3D view options this run (not saved)
##
## Keys: F9 table style (Modern / Amiga pixel), F7/F8 tempo -/+ 5 %, F10 smooth scaling
## (pixel style), F11 / Alt+Enter toggle fullscreen for this session.
## Fullscreen (borderless, native resolution of the current monitor) is the default; only an
## explicit WINDOW choice in OPTIONS is remembered (display/window_mode = "window").

signal changed

const PATH := "user://settings.cfg"

var fullscreen := true
var _saved_fullscreen := true   # persisted choice (only changed from the OPTIONS menu)
var _migrate := false
var smooth_scale := false     # F10: linear filtering of the scaled table in pixel style
var style := "modern"         # F9: "modern" (HD lit table) or "pixel" (Amiga 32-colour art)
## modern style only: "3d" = real 3D table objects + lights over the 2D physics (default),
## "2d" = the classic painted 2.5D sprites. Pixel style is always 2D.
var view := "3d"
var shadows3d := true         # 3D view: the directional light casts real shadows
var lightfx := 2              # 3D view: 0 = off, 1 = low (flashers + bumpers), 2 = high (inserts, glow, light show)
var _saved_view := "3d"
var _saved_shadows := true
var _saved_lightfx := 2
var tempo := 0.85             # F7/F8: game tempo 0.70-1.20 (ball time scale)
const TEMPO_MIN := 0.70
const TEMPO_MAX := 1.20
var music_volume := 0.6   # leaves room for the ball roll (docs/DZWIEK-KULKI.md)
var sfx_volume := 0.9
var high_score := 0          # best score over all tables (title screen)
var high_scores := {}         # table id -> [[initials, score], ...] best first
var last_initials := "AAA"
var table_id := "midnight_funfair"   # menu table carousel selection
var _table_arg := ""                 # --table=<id>: this run only, settings.cfg keeps its table
var persist := true           # tests set false so they never touch the player's saves
const HS_COUNT := 5
const HS_DEFAULT := [["CPR", 2000000], ["AGA", 1500000], ["OCS", 1000000], ["ECS", 750000], ["PAU", 500000]]
var autostart := false
var demo := false
var _shot_path := ""
var _shot_frame := 420
var _frames := 0
## still shots: `--still --still-cam=Y --still-ball=X,Y` freezes the table (no physics, fixed lamp
## time, fixed camera centre) so before/after shots show the exact same frame
var still := false
var still_cam := -1.0
var still_ball := Vector2(-1, -1)
var _bench := 0.0             # --bench=SEC: print the average/min FPS + GPU frame time, then quit
var _bench_t := 0.0
var _bench_n := 0
var _bench_worst := 0.0
var _bench_gpu := 0.0
var _bench_dts := PackedFloat32Array()
var _saved_style := "modern"   # persisted values (command-line overrides are not saved)
var _saved_tempo := 0.85


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_setup_input()
	_load()
	_saved_style = style
	_saved_tempo = tempo
	_saved_fullscreen = fullscreen
	_saved_view = view
	_saved_shadows = shadows3d
	_saved_lightfx = lightfx
	if _migrate:
		_save()   # old settings.cfg (stale fullscreen=false) -> window_mode = fullscreen
	var args := OS.get_cmdline_user_args()
	autostart = args.has("--autostart")
	demo = args.has("--demo")
	if args.has("--windowed"):
		fullscreen = false
	for a in args:
		if a.begins_with("--shot="):
			_shot_path = a.substr(7)
		elif a.begins_with("--shot-frame="):
			_shot_frame = a.substr(13).to_int()
		elif a.begins_with("--style="):
			style = "pixel" if a.substr(8) == "pixel" else "modern"
		elif a.begins_with("--view="):
			view = "2d" if a.substr(7) == "2d" else "3d"
		elif a.begins_with("--shadows="):
			shadows3d = a.substr(10) != "0"
		elif a.begins_with("--lightfx="):
			lightfx = clampi(a.substr(10).to_int(), 0, 2)
		elif a.begins_with("--tempo="):
			tempo = clampf(a.substr(8).to_float(), TEMPO_MIN, TEMPO_MAX)
		elif a.begins_with("--still-cam="):
			still = true
			still_cam = a.get_slice("=", 1).to_float()
		elif a.begins_with("--still-ball="):
			still = true
			var xy := a.get_slice("=", 1).split(",")
			still_ball = Vector2(xy[0].to_float(), xy[1].to_float())
		elif a == "--still":
			still = true
		elif a.begins_with("--bench="):
			_bench = a.get_slice("=", 1).to_float()
		elif a.begins_with("--table="):
			_table_arg = table_id
			table_id = a.substr(8)
	set_process(_shot_path != "" or _bench > 0.0)
	_apply_window()
	_apply_volumes()


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var k := event as InputEventKey
		if k.keycode == KEY_F11 or (k.alt_pressed and (k.keycode == KEY_ENTER or k.keycode == KEY_KP_ENTER)):
			toggle_fullscreen()
			get_viewport().set_input_as_handled()
		elif k.keycode == KEY_F10:
			smooth_scale = not smooth_scale
			_save()
			changed.emit()
		elif k.keycode == KEY_F9:
			toggle_style()
			get_viewport().set_input_as_handled()
		elif k.keycode == KEY_F7 or k.keycode == KEY_F8:
			set_tempo(tempo + (0.05 if k.keycode == KEY_F8 else -0.05))
			get_viewport().set_input_as_handled()


## Every table folder with a table.json (name, subtitle, preview, music), sorted by "order".
func tables() -> Array:
	var out: Array = []
	var root := "res://assets/tables/"
	var da := DirAccess.open(root)
	if da == null:
		return out
	for id in da.get_directories():
		var p := root + id + "/table.json"
		if not FileAccess.file_exists(p):
			continue
		var d = JSON.parse_string(FileAccess.get_file_as_string(p))
		if d is Dictionary:
			d["id"] = id
			d["dir"] = root + id + "/"
			out.append(d)
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.get("order", 99)) < int(b.get("order", 99)))
	return out


func set_volume(kind: String, v: float) -> void:
	v = clampf(snappedf(v, 0.1), 0.0, 1.0)
	if kind == "music":
		music_volume = v
	else:
		sfx_volume = v
	_save()
	if Sound.has_method("refresh_volume"):
		Sound.call("refresh_volume")
	elif kind == "music" and Sound.get("_music") is AudioStreamPlayer:
		(Sound.get("_music") as AudioStreamPlayer).volume_db = linear_to_db(maxf(music_volume, 0.001)) + Sound.MUSIC_DB
	changed.emit()


func style_name() -> String:
	return "MODERN" if style == "modern" else "AMIGA PIXEL"


## True when the table draws its 3D layer (modern style, 3D view, a real renderer).
func use_3d() -> bool:
	return style == "modern" and view == "3d" and DisplayServer.get_name() != "headless"


func view_name() -> String:
	return "3D" if view == "3d" else "2D CLASSIC"


func shadows_name() -> String:
	return "ON" if shadows3d else "OFF"


func lightfx_name() -> String:
	return ["OFF", "LOW", "HIGH"][clampi(lightfx, 0, 2)]


func toggle_view() -> void:
	view = "2d" if view == "3d" else "3d"
	_saved_view = view
	_save()
	changed.emit()


func toggle_shadows() -> void:
	shadows3d = not shadows3d
	_saved_shadows = shadows3d
	_save()
	changed.emit()


func set_lightfx(n: int) -> void:
	lightfx = clampi(n, 0, 2)
	_saved_lightfx = lightfx
	_save()
	changed.emit()


func toggle_style() -> void:
	style = "pixel" if style == "modern" else "modern"
	_saved_style = style
	_save()
	changed.emit()


func set_tempo(t: float) -> void:
	tempo = clampf(snappedf(t, 0.05), TEMPO_MIN, TEMPO_MAX)
	_saved_tempo = tempo
	_save()
	changed.emit()


var _bench_work := 0.0


func _bench_step(delta: float) -> void:
	if _frames == 2:
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
		for v in get_tree().root.find_children("*", "SubViewport", true, false):
			RenderingServer.viewport_set_measure_render_time((v as SubViewport).get_viewport_rid(), true)
		RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
	_bench_t += delta
	if _bench_t < 3.0:
		return
	_bench_n += 1
	if _bench_n > 1:
		_bench_worst = maxf(_bench_worst, delta)
		if delta > 1.0 / 62.0:   # BENCH_SPIKE: log slow frames to find hitches
			print("[spike] t=%.2f dt=%.1fms" % [_bench_t - 3.0, delta * 1000.0])
		_bench_dts.append(delta)
	var gpu := RenderingServer.viewport_get_measured_render_time_gpu(get_viewport().get_viewport_rid())
	for v in get_tree().root.find_children("*", "SubViewport", true, false):
		gpu += RenderingServer.viewport_get_measured_render_time_gpu((v as SubViewport).get_viewport_rid())
	_bench_gpu += gpu
	if _bench_n > 1:   # BENCH_WORK: worst real work per frame (cpu process+physics + gpu), compositor waits excluded
		_bench_work = maxf(_bench_work, gpu + 1000.0 * (Performance.get_monitor(Performance.TIME_PROCESS) + Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)))
	if _bench_t >= 3.0 + _bench:
		var n := float(_bench_n)
		_bench_dts.sort()
		var p99 := _bench_dts[int(_bench_dts.size() * 0.99)] if _bench_dts.size() > 0 else 0.0
		print("[bench] %s frames=%d avg_fps=%.1f p99_fps=%.1f min_fps=%.1f gpu_ms=%.2f worst_work_ms=%.2f size=%s" % [
			RenderingServer.get_video_adapter_name(), _bench_n, n / (_bench_t - 3.0),
			1.0 / maxf(p99, 0.0001), 1.0 / maxf(_bench_worst, 0.0001), _bench_gpu / n, _bench_work, str(get_window().size)])
		get_tree().quit()


func _process(_delta: float) -> void:
	_frames += 1
	if _bench > 0.0:
		_bench_step(_delta)
	if _frames == _shot_frame and _shot_path != "":
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		img.save_png(_shot_path)
		for bs in get_tree().get_nodes_in_group("ct_ball"):
			var n2 := bs as Node2D
			var o: Vector2 = n2.get_global_transform_with_canvas().origin
			var vp := n2.get_viewport()
			var k := 1.0
			if vp is SubViewport and vp.get_parent() is SubViewportContainer:
				var c := vp.get_parent() as SubViewportContainer
				k = c.get_global_rect().size.x / float((vp as SubViewport).size.x)
				o = c.get_global_rect().position + o * k
			print("[shot] ball at %d %d k %.3f" % [o.x, o.y, k])
		print("[shot] %s %dx%d" % [_shot_path, img.get_width(), img.get_height()])
		get_tree().quit()


## F11 / Alt+Enter: this session only. OPTIONS > SCREEN passes remember = true.
func toggle_fullscreen(remember := false) -> void:
	fullscreen = not fullscreen
	_apply_window()
	if remember:
		_saved_fullscreen = fullscreen
		_save()
	changed.emit()


func scores_for(table_id: String) -> Array:
	if not high_scores.has(table_id) or not (high_scores[table_id] is Array):
		high_scores[table_id] = HS_DEFAULT.duplicate(true)
	return high_scores[table_id]


## Index (0-based) the score would take in the table, or -1 if it does not qualify.
func rank_for(table_id: String, score: int) -> int:
	var l := scores_for(table_id)
	for i in l.size():
		if score > int(l[i][1]):
			return i
	return l.size() if l.size() < HS_COUNT else -1


func qualifies(table_id: String, score: int) -> bool:
	return score > 0 and rank_for(table_id, score) >= 0


func add_high_score(table_id: String, initials: String, score: int) -> int:
	var r := rank_for(table_id, score)
	if r < 0:
		return -1
	var l := scores_for(table_id)
	l.insert(r, [initials, score])
	while l.size() > HS_COUNT:
		l.pop_back()
	last_initials = initials
	high_score = maxi(high_score, score)
	_save()
	return r


func submit_score(score: int) -> bool:
	if score > high_score:
		high_score = score
		_save()
		return true
	return false


func _apply_window() -> void:
	if DisplayServer.get_name() == "headless":
		return
	if fullscreen:
		# borderless fullscreen on the monitor the window is on, at its native resolution
		# (any aspect: 16:9, 21:9 / 32:9 ultrawide, portrait - the layout adapts)
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		var scr := DisplayServer.window_get_current_screen()
		var ss := DisplayServer.screen_get_size(scr)
		var ws := Vector2i(maxi(960, int(ss.x * 0.7)), maxi(540, int(ss.y * 0.7)))
		ws = Vector2i(mini(ws.x, ss.x), mini(ws.y, ss.y))
		DisplayServer.window_set_size(ws)
		DisplayServer.window_set_position(DisplayServer.screen_get_position(scr) + (ss - ws) / 2)
	if OS.get_cmdline_user_args().has("--probe"):
		print("[window] fullscreen=%s mode=%d size=%s screen=%s" % [fullscreen, DisplayServer.window_get_mode(),
			DisplayServer.window_get_size(), DisplayServer.screen_get_size(DisplayServer.window_get_current_screen())])


func _apply_volumes() -> void:
	var bus := AudioServer.get_bus_index("Master")
	AudioServer.set_bus_volume_db(bus, 0.0)


func _load() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	# only an explicit WINDOW choice is honoured; older files (plain "fullscreen" key, which
	# --windowed test runs could overwrite) migrate to fullscreen
	if cfg.has_section_key("display", "window_mode"):
		fullscreen = str(cfg.get_value("display", "window_mode")) != "window"
	else:
		fullscreen = true
		_migrate = true
	smooth_scale = cfg.get_value("display", "smooth_scale", smooth_scale)
	style = cfg.get_value("display", "style", style)
	# 3D view options (older files have none -> 3D view, shadows on, lighting high)
	view = "2d" if str(cfg.get_value("display", "view", "3d")) == "2d" else "3d"
	shadows3d = bool(cfg.get_value("display", "shadows3d", true))
	lightfx = clampi(int(cfg.get_value("display", "lightfx", 2)), 0, 2)
	tempo = clampf(cfg.get_value("game", "tempo", tempo), TEMPO_MIN, TEMPO_MAX)
	music_volume = cfg.get_value("audio", "music", music_volume)
	sfx_volume = cfg.get_value("audio", "sfx", sfx_volume)
	high_score = cfg.get_value("game", "high_score", high_score)
	last_initials = cfg.get_value("game", "last_initials", last_initials)
	table_id = cfg.get_value("game", "table", table_id)
	if cfg.has_section("scores"):
		for k in cfg.get_section_keys("scores"):
			var v = cfg.get_value("scores", k)
			if v is Array:
				high_scores[k] = v


func _save() -> void:
	if not persist:
		return
	var cfg := ConfigFile.new()
	cfg.set_value("display", "window_mode", "fullscreen" if _saved_fullscreen else "window")
	cfg.set_value("display", "smooth_scale", smooth_scale)
	cfg.set_value("display", "style", _saved_style)
	cfg.set_value("display", "view", _saved_view)
	cfg.set_value("display", "shadows3d", _saved_shadows)
	cfg.set_value("display", "lightfx", _saved_lightfx)
	cfg.set_value("game", "tempo", _saved_tempo)
	cfg.set_value("audio", "music", music_volume)
	cfg.set_value("audio", "sfx", sfx_volume)
	cfg.set_value("game", "high_score", high_score)
	cfg.set_value("game", "last_initials", last_initials)
	cfg.set_value("game", "table", _table_arg if _table_arg != "" else table_id)
	for k in high_scores:
		cfg.set_value("scores", k, high_scores[k])
	cfg.save(PATH)


# --- input map -------------------------------------------------------------

func _key(code: Key, loc: KeyLocation = KEY_LOCATION_UNSPECIFIED) -> InputEventKey:
	var e := InputEventKey.new()
	e.physical_keycode = code
	e.location = loc
	return e


func _joy(button: JoyButton) -> InputEventJoypadButton:
	var e := InputEventJoypadButton.new()
	e.button_index = button
	return e


func _axis(axis: JoyAxis, value: float) -> InputEventJoypadMotion:
	var e := InputEventJoypadMotion.new()
	e.axis = axis
	e.axis_value = value
	return e


func _bind(action: StringName, events: Array, deadzone := 0.4) -> void:
	if InputMap.has_action(action):
		InputMap.erase_action(action)
	InputMap.add_action(action, deadzone)
	for e in events:
		InputMap.action_add_event(action, e)


func _setup_input() -> void:
	_bind(&"flip_left", [
		_key(KEY_SHIFT, KEY_LOCATION_LEFT), _key(KEY_CTRL, KEY_LOCATION_LEFT),
		_key(KEY_Z), _key(KEY_LEFT),
		_joy(JOY_BUTTON_LEFT_SHOULDER), _axis(JOY_AXIS_TRIGGER_LEFT, 1.0)])
	_bind(&"flip_right", [
		_key(KEY_SHIFT, KEY_LOCATION_RIGHT), _key(KEY_CTRL, KEY_LOCATION_RIGHT),
		_key(KEY_M), _key(KEY_SLASH), _key(KEY_RIGHT),
		_joy(JOY_BUTTON_RIGHT_SHOULDER), _axis(JOY_AXIS_TRIGGER_RIGHT, 1.0)])
	_bind(&"plunger", [
		_key(KEY_SPACE), _key(KEY_ENTER), _key(KEY_KP_ENTER), _key(KEY_DOWN),
		_joy(JOY_BUTTON_A), _joy(JOY_BUTTON_DPAD_DOWN)])
	_bind(&"nudge_left", [_key(KEY_X), _joy(JOY_BUTTON_DPAD_LEFT), _joy(JOY_BUTTON_X)])
	_bind(&"nudge_right", [_key(KEY_N), _joy(JOY_BUTTON_DPAD_RIGHT), _joy(JOY_BUTTON_B)])
	_bind(&"nudge_up", [_key(KEY_UP), _key(KEY_B), _joy(JOY_BUTTON_Y), _joy(JOY_BUTTON_DPAD_UP)])
	_bind(&"start", [
		_key(KEY_SPACE), _key(KEY_ENTER), _key(KEY_KP_ENTER),
		_joy(JOY_BUTTON_START), _joy(JOY_BUTTON_A)])
	_bind(&"pause", [_key(KEY_P), _joy(JOY_BUTTON_START)])
	_bind(&"back", [_key(KEY_ESCAPE), _joy(JOY_BUTTON_BACK)])
