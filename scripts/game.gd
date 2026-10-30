class_name PinGame
extends Control
## Game screen - Pinball Fantasies style:
##  - one DMD strip across the top (score, ball, bonus, mission, animated messages)
##  - below it the 320-unit table scaled to the FULL screen width on every aspect ratio
##    (scale = width / 320). Style "modern" renders the HD lit table at the physical screen
##    resolution (SubViewport in device pixels, camera zoom); style "pixel" renders the
##    320-px Amiga art and scales it up (nearest, F10 = smooth).
##  - ball pace = Settings.tempo x view factor: the bigger the on-screen zoom (short visible
##    slice on wide screens) the slower the ball runs, so its on-screen speed stays readable.
##  - the visible table height is just a window; the camera scrolls vertically after the
##    lowest ball with velocity look-ahead and a hard keep-in-view margin, so even the
##    short slice of a 32:9 screen always shows the ball.

const ANIM_TIME := 2.2
var TABLE_ID := "midnight_funfair"   # set from Settings.table_id in _ready
const INITIAL_CHARS := "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
## Fallback rules; the table's rules.json overrides any of these keys.
const DEFAULT_RULES := {
	"balls": 3,
	"ball_save": 8.0,            # seconds of ball save after the plunge
	"ball_save_once": true,      # ball save works once per ball (real-machine rule)
	"max_extra_balls": 2,        # pending extra balls are capped
	"match": {
		"enabled": true,
		"place": 10,             # compare from this place: 10 = the score's TENS digit
		"digits": 1,             # how many digits from that place (scores end in 0)
		"step": 1,               # drawn numbers 0, 1 ... 9 (step 10 + place 1 + digits 2 = 00-90)
		"odds": -1.0,            # <0: uniform over the numbers (1 in 10); else P(match)
		"award": "extra_ball",   # extra_ball = one more ball, same game, table state kept
		"max_per_game": 1,
		"min_score": 0,
		"spin_time": 2.0,
	},
	"game_over_time": 3.2,
	"final_score_time": 2.8,
	"entry_timeout": 40.0,
	"attract_after": 12.0,       # seconds on the game-over screen before the menu returns
}

signal finished                  # game over sequence complete (used when not the main scene)

var table: PinTable
var svc: SubViewportContainer
var sv: SubViewport
var vign: ColorRect
var glass: ColorRect        # M10_GLASS: faint glass reflections over the table (modern)
var cam: Camera2D
var strip_bg: ColorRect
var strip_line: ColorRect
var dmd: DotMatrix

var score := 0
var ball_no := 1
var state := "play"            # play | drain | match | gameover | final | entry | over
var rules: Dictionary = {}
var BALLS := 3
var match_seed := -1           # >=0: deterministic MATCH roll (tests, --match-seed=N)
var _match_rng := RandomNumberGenerator.new()
var _match_used := 0
var _match_num := 0            # final rolled number
var _match_show := 0           # number on the DMD while spinning
var _match_hit := false
var _match_tick := 0.0
var _save_armed := true
var _initials := PackedInt32Array([0, 0, 0])
var _entry_pos := 0
var _entry_rank := 0
var _last_rank := -1
var _preview_hold := -1.0       # --end-preview=NAME@SECONDS freezes the sequence there
var ball_save := 0.0
var _msg := ""
var _msg_t := 0.0
var _anim := ""
var _anim_text := ""
var _anim_t := 0.0
var _cam_y := 590.0
var _view_h := 200.0
var _state_t := 0.0
var _bumpers_at_ball := 0
var _ramps_at_ball := 0
var _new_high := false
var _time := 0.0
var _mission_t := 0.0
var _sparks: Array = []
var _probe := OS.get_cmdline_user_args().has("--probe")
var _extra := 0
var _view_factor := 1.0
var _style := ""
var _px_per_unit := 4.0


func _ready() -> void:
	_load_rules()
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.0, 0.0, 0.0)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	svc = SubViewportContainer.new()
	svc.stretch = false
	svc.process_mode = Node.PROCESS_MODE_PAUSABLE
	add_child(svc)
	sv = SubViewport.new()
	sv.size = Vector2i(320, 200)
	sv.snap_2d_transforms_to_pixel = true
	sv.snap_2d_vertices_to_pixel = true
	svc.add_child(sv)
	# subtle 2.5D vignette over the table (stepped in pixel style)
	vign = ColorRect.new()
	vign.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var vm := ShaderMaterial.new()
	vm.shader = load("res://shaders/vignette.gdshader")
	vign.material = vm
	add_child(vign)
	glass = ColorRect.new()
	glass.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var gm := ShaderMaterial.new()
	gm.shader = load("res://shaders/glass.gdshader")
	glass.material = gm
	add_child(glass)
	table = PinTable.new()
	table.table_id = Settings.table_id
	sv.add_child(table)
	TABLE_ID = table.table_id
	cam = Camera2D.new()
	cam.position = Vector2(PinTable.W * 0.5, _cam_y)
	sv.add_child(cam)
	cam.make_current()

	strip_bg = ColorRect.new()
	strip_bg.color = Color(0.05, 0.02, 0.04)
	add_child(strip_bg)
	strip_line = ColorRect.new()
	strip_line.color = Color(0.78, 0.72, 0.85)
	add_child(strip_line)
	dmd = DotMatrix.new()
	add_child(dmd)

	table.scored.connect(_on_scored)
	table.announce.connect(_say)
	table.dmd_anim.connect(_on_anim)
	table.drained.connect(_on_drained)
	table.extra_ball.connect(func() -> void: _extra = mini(_extra + 1, int(rules.max_extra_balls)))
	table.launched.connect(_on_launched)
	table.save_request.connect(func(sec: float) -> void:   # M11_MODES
		if state == "play":
			ball_save = maxf(ball_save, sec))

	get_viewport().size_changed.connect(_layout)
	Settings.changed.connect(_layout)
	Sound.play_music(_table_music())
	_start_game()
	_layout()
	_end_preview()
	_still_setup()


# --- layout ------------------------------------------------------------------

func _layout() -> void:
	var s := get_viewport_rect().size
	# DMD: 16 dot rows; dot size from height (~10 %) but never fewer than ~176 columns
	var dotp := minf(s.y * 0.10 / 16.0, s.x / 176.0)
	var strip_h := dotp * 16.0 + 6.0
	var cols := int(floor((s.x - 8.0) / dotp))
	dmd.resize_grid(cols, 16)
	dmd.position = Vector2((s.x - cols * dotp) * 0.5, 3.0)
	dmd.size = Vector2(cols * dotp, dotp * 16.0)
	strip_bg.position = Vector2.ZERO
	strip_bg.size = Vector2(s.x, strip_h)
	strip_line.position = Vector2(0, strip_h)
	strip_line.size = Vector2(s.x, 2.0)
	# table: full width, always
	if _style != Settings.style:
		_style = Settings.style
		if table.style != _style:
			table.set_style(_style)
	# M11_3D: view 3D <-> 2D switches live (rebuilds the table visuals); shadows/lights apply in place
	if table.view3d != (_style != "pixel" and Settings.use_3d()):
		table.set_style(_style)
	table.apply_3d_options()
	var k := s.x / PinTable.W
	var top := strip_h + 2.0
	_view_h = minf(PinTable.H, ceilf((s.y - top) / k))
	sv.snap_2d_transforms_to_pixel = _style == "pixel"
	sv.snap_2d_vertices_to_pixel = _style == "pixel"
	if _style == "pixel":
		_px_per_unit = 1.0
		sv.size = Vector2i(int(PinTable.W), int(_view_h))
		cam.zoom = Vector2.ONE
		svc.size = Vector2(sv.size)
		svc.scale = Vector2(k, k)
		svc.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR if Settings.smooth_scale else CanvasItem.TEXTURE_FILTER_NEAREST
	else:
		# render in device pixels: virtual canvas -> window factor f
		var win := Vector2(get_window().size)
		var f := win.x / s.x if s.x > 0.0 and win.x > 0.0 else 1.0
		_px_per_unit = k * f
		sv.size = Vector2i(int(ceil(PinTable.W * _px_per_unit)), int(ceil(_view_h * _px_per_unit)))
		cam.zoom = Vector2(_px_per_unit, _px_per_unit)
		svc.size = Vector2(sv.size)
		svc.scale = Vector2(1.0 / f, 1.0 / f)
		svc.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	svc.position = Vector2(0.0, top + maxf(0.0, (s.y - top - _view_h * k) * 0.5))
	vign.position = svc.position
	vign.size = Vector2(s.x, _view_h * k)
	(vign.material as ShaderMaterial).set_shader_parameter("steps", 4.0 if _style == "pixel" else 0.0)
	(vign.material as ShaderMaterial).set_shader_parameter("aspect", vign.size.x / maxf(1.0, vign.size.y))
	glass.position = vign.position
	glass.size = vign.size
	(glass.material as ShaderMaterial).set_shader_parameter("aspect", vign.size.x / maxf(1.0, vign.size.y))
	glass.visible = _style != "pixel"
	# pace: Settings.tempo x view factor (240 visible units ~ a PF screen = 1.0)
	_view_factor = clampf(pow(_view_h / 240.0, 0.35), 0.75, 1.0)
	table.pace = Settings.tempo * _view_factor
	_cam_y = clampf(_cam_y, _view_h * 0.5, PinTable.H - _view_h * 0.5)


## Music of this table through the audio manager (table.json "music"); tables whose track is not
## rendered yet play the Funfair theme instead of silence.
func _table_music() -> String:
	var m := "funfair"
	var p := table.dir + "table.json"
	if FileAccess.file_exists(p):
		var d = JSON.parse_string(FileAccess.get_file_as_string(p))
		if d is Dictionary and d.has("music"):
			m = str(d.music)
	if Sound.has_method("_has_music") and not Sound.call("_has_music", m):
		m = "funfair"
	return m


# --- rules ---------------------------------------------------------------------

func _load_rules() -> void:
	rules = DEFAULT_RULES.duplicate(true)
	var p := PinTable.dir_for(Settings.table_id) + "rules.json"
	if table != null:
		p = table.dir + "rules.json"
	if FileAccess.file_exists(p):
		var d = JSON.parse_string(FileAccess.get_file_as_string(p))
		if d is Dictionary:
			for k in d:
				if d[k] is Dictionary and rules.get(k) is Dictionary:
					(rules[k] as Dictionary).merge(d[k], true)
				else:
					rules[k] = d[k]
	BALLS = int(rules.balls)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--match-seed="):
			match_seed = int(a.get_slice("=", 1))


func _on_launched() -> void:
	if ball_save <= 0.0 and (_save_armed or not bool(rules.ball_save_once)):
		ball_save = float(rules.ball_save)
	_save_armed = false


func _start_game() -> void:
	_match_used = 0
	_save_armed = true
	_last_rank = -1
	score = 0
	ball_no = 1
	state = "play"
	ball_save = 0.0
	_new_high = false
	_extra = 0
	table.reset_game()
	table.input_enabled = true
	_bumpers_at_ball = 0
	_ramps_at_ball = 0
	_say("BALL 1", "start")


func _on_scored(points: int) -> void:
	if state == "play" and not table.tilted:
		score += points


func _say(text: String, sfx := "") -> void:
	if _probe:
		print("[probe] msg ", text)
	_msg = text
	_msg_t = 1.8
	if sfx != "":
		Sound.play(sfx)


func _on_anim(kind: String, text: String) -> void:
	if _probe:
		print("[probe] anim ", kind, " ", text)
	_anim = kind
	_anim_text = text
	_anim_t = ANIM_TIME
	_msg_t = 0.0


func _on_drained() -> void:
	if _probe:
		print("[probe] drained save=%.1f score=%d" % [ball_save, score])
	if state != "play":
		return
	if ball_save > 0.0 and not table.tilted:
		ball_save = 0.0
		_say("BALL SAVED", "save")
		table.reset_ball()
		return
	state = "drain"
	_state_t = 0.0
	Sound.play("drain")
	var bonus := 0
	if not table.tilted:
		bonus = ((table.ramp_hits - _ramps_at_ball) * 2000 + (table.bumper_hits - _bumpers_at_ball) * 100 + 1000) * table.multiplier
		score += bonus
	if _extra > 0:
		_extra -= 1
		ball_no -= 1
		_say("BONUS %s - SHOOT AGAIN" % Util.fmt_score(bonus))
	else:
		_say("BONUS %s" % Util.fmt_score(bonus))
	_msg_t = 2.2
	table.reset_ball()
	table.input_enabled = false


func _next_ball() -> void:
	ball_no += 1
	_save_armed = true
	if ball_no > BALLS:
		table.input_enabled = false
		table.clear_balls()
		var m: Dictionary = rules.match
		if bool(m.enabled) and _match_used < int(m.max_per_game) and score >= int(m.get("min_score", 0)):
			_begin_match()
		else:
			_begin_game_over()
	else:
		state = "play"
		table.multiplier = maxi(1, table.multiplier - 1)
		_bumpers_at_ball = table.bumper_hits
		_ramps_at_ball = table.ramp_hits
		table.input_enabled = true
		_say("BALL %d" % ball_no, "start")


func _mission_lines() -> PackedStringArray:
	if state == "play" and not Settings.demo and table.balls.size() > 0 and table._in_lane(table.balls[0]):
		return PackedStringArray(["HOLD SPACE", "TO LAUNCH"])
	var ml: PackedStringArray = table.rules.mission_lines()
	var mlin: String = table.rules.mode_line()
	if mlin != "":
		ml[0] = mlin
	return ml


# --- frame -------------------------------------------------------------------------

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(&"back"):
		get_tree().paused = false
		get_tree().change_scene_to_file("res://scenes/title.tscn")
	elif state == "entry":
		if event is InputEventKey and event.pressed and not event.echo:
			var k := OS.get_keycode_string((event as InputEventKey).physical_keycode)
			if k.length() == 1 and INITIAL_CHARS.contains(k):
				entry_input("char:" + k)
				return
			if (event as InputEventKey).physical_keycode == KEY_BACKSPACE:
				entry_input("back")
				return
		if event.is_action_pressed(&"flip_left") or event.is_action_pressed(&"nudge_left"):
			entry_input("prev")
		elif event.is_action_pressed(&"flip_right") or event.is_action_pressed(&"nudge_right"):
			entry_input("next")
		elif event.is_action_pressed(&"start") or event.is_action_pressed(&"plunger"):
			entry_input("ok")
	elif event.is_action_pressed(&"pause") and state in ["play", "drain"]:
		get_tree().paused = not get_tree().paused
	elif event.is_action_pressed(&"start") and state in ["gameover", "final"] and _state_t > 0.8:
		_state_t = 999.0           # skip ahead
	elif event.is_action_pressed(&"start") and state == "over" and _state_t > 1.5:
		_start_game()


func _process(delta: float) -> void:
	_time += delta
	if glass and table:
		(glass.material as ShaderMaterial).set_shader_parameter("t", table._time)
	if get_tree().paused:
		_draw_dmd(0.0)
		return
	_state_t += delta
	if _preview_hold >= 0.0:
		_state_t = minf(_state_t, _preview_hold)
	ball_save = maxf(0.0, ball_save - delta)
	table.save_lit = ball_save > 0.0 and state == "play"
	_msg_t -= delta
	_anim_t -= delta
	table.autopilot = Settings.demo and state == "play"
	_end_flow(delta)
	_update_camera(delta)
	_draw_dmd(delta)


func _update_camera(delta: float) -> void:
	var half := _view_h * 0.5
	if _view_h >= PinTable.H:
		_cam_y = PinTable.H * 0.5
	else:
		var lo := half
		var hi := PinTable.H - half
		var by := table.focus_y()
		var vy := 0.0
		for b in table.balls:
			if b.pos.y >= by - 0.5:
				vy = b.vel.y
		# look-ahead along the vertical velocity, slight bias to show what is below the ball
		# short (ultrawide) views: less look-ahead upward (the ball comes back), more downward so the
		# flippers come into view early; near the flippers, hold them in frame
		var sv := clampf((_view_h - 80.0) / 200.0, 0.0, 1.0)
		var ahead := clampf(vy * lerpf(0.15, 0.22, sv), -_view_h * lerpf(0.22, 0.32, sv), _view_h * lerpf(0.38, 0.32, sv))
		var target := by + ahead + _view_h * 0.08
		if by > 470.0 and vy > -200.0:
			target = maxf(target, 600.0 - half + minf(24.0, _view_h * 0.2))
		target = clampf(target, lo, hi)
		# PF-style easing (delta/4 per 50 Hz frame), quicker on short (ultrawide) slices
		var keep := lerpf(0.62, 0.75, clampf((_view_h - 80.0) / 160.0, 0.0, 1.0))
		_cam_y += (target - _cam_y) * (1.0 - pow(keep, delta * 50.0))
		# never lose the ball on short (ultrawide) slices
		var margin := minf(28.0, _view_h * 0.22)
		_cam_y = clampf(_cam_y, by - half + margin, by + half - margin)
		_cam_y = clampf(_cam_y, lo, hi)
	if Settings.still and Settings.still_cam >= 0.0:
		_cam_y = clampf(Settings.still_cam, half, maxf(half, PinTable.H - half))
	if _style == "pixel":
		cam.position = Vector2(PinTable.W * 0.5, roundf(_cam_y)) + table.shake.round()
	else:
		cam.position = Vector2(PinTable.W * 0.5, _cam_y) + table.shake
	table.sync_3d(cam.position, cam.zoom.x, sv.size)


# --- DMD ---------------------------------------------------------------------------

func _draw_dmd(delta: float) -> void:
	var d := dmd
	d.clear()
	var c := d.cols
	var mid := c / 2
	var sc := Util.fmt_score(score)
	if get_tree().paused:
		_big_or_small("PAUSED", mid, 255)
	elif state in ["match", "gameover", "final", "entry", "over"]:
		_draw_end(delta)
	elif _anim_t > 0.0:
		_draw_anim(delta)
	elif _msg_t > 0.0:
		var t := _msg if _msg_t > 0.0 else ("PRESS START" if fmod(_time, 2.0) < 1.0 else sc)
		if not (state == "over" and _msg_t > 9000.0 and fmod(_time, 2.4) > 1.6):
			_big_or_small(t, mid, 255 if fmod(_time, 0.3) < 0.2 or _msg_t > 0.9 else 120)
		else:
			_big_or_small(sc, mid, 255)
	else:
		var ml0 := _mission_lines()
		var side_w := maxi(maxi(d.text_width(ml0[0], 1), d.text_width(ml0[1], 1)), d.text_width("BONUS 6X", 1))
		var wide := d.text_width(sc, 2) + 2 * side_w + 16 <= c
		if table.charging:
			var n := int(table.charge * (c - 4))
			for x in n:
				for y in range(13, 16):
					d.dot(2 + x, y, 255 if (x / 3) % 2 == 0 else 140)
			# skill-shot zone bracket above the power bar
			for x in range(int(PinTable.SKILL_LO * (c - 4)), int(PinTable.SKILL_HI * (c - 4))):
				d.dot(2 + x, 11, 255 if fmod(_time, 0.4) < 0.25 else 120)
		if wide:
			d.text("BALL %d/%d" % [mini(ball_no, BALLS), BALLS], 2, 1)
			d.text("BONUS %dX" % table.multiplier, 2, 9, 1, -1, 200)
			var ml := _mission_lines()
			d.text(ml[0], c - 2, 1, 1, 1)
			d.text(ml[1], c - 2, 9, 1, 1, 200)
			_big_or_small(sc, mid, 255)
			if table.tilt > 0.6:
				d.text("DANGER" if table.tilt >= 1.9 else "TILT " + "#".repeat(int(table.tilt + 0.5)), 2, 9, 1, -1, 255)
		else:
			# narrow screens: score + ball, mission text rotates in every few seconds
			_mission_t += delta
			if fmod(_mission_t, 9.0) > 6.5:
				var ml := _mission_lines()
				d.text(ml[0], mid, 1, 1, 0)
				d.text(ml[1], mid, 9, 1, 0, 200)
			else:
				d.text("B%d" % mini(ball_no, BALLS), 1, 1)
				d.text("%dX" % table.multiplier, 1, 9, 1, -1, 200)
				_big_or_small(sc, mid + 8, 255)
	d.present()


## Centred text, 2x when it fits, else 1x.
func _big_or_small(t: String, x: int, v: int) -> void:
	var s := 2 if dmd.text_width(t, 2) <= dmd.cols - 4 else 1
	var y := 1 if s == 2 else 4
	dmd.text(t, x, y, s, 0, v)


func _draw_anim(delta: float) -> void:
	var d := dmd
	var c := d.cols
	var rows := d.rows
	var p := 1.0 - _anim_t / ANIM_TIME          # 0..1
	var mid := c / 2
	match _anim:
		"coaster":
			# a car riding a sine track across the display, then the words
			var car_x := int(p * 1.6 * c) - 10
			for x in c:
				var y := 12 + int(round(sin(x * 0.09) * 2.5))
				d.dot(x, y, 110)
				if x % 6 == 0:
					for yy in range(y + 1, rows):
						d.dot(x, yy, 50)
			for i in 3:
				var cx := car_x - i * 9
				var cy := 12 + int(round(sin(cx * 0.09) * 2.5))
				for yy in range(cy - 4, cy):
					for xx in range(cx - 3, cx + 4):
						d.dot(xx, yy, 255)
			if p > 0.35:
				d.text(_anim_text, mid, 1, 1, 0, 255)
		"wheel":
			var r := 7
			for side in [10, c - 11]:
				for i in 8:
					var a: float = _time * 6.0 + i * TAU / 8.0
					for k in range(2, r + 1):
						d.dot(side + int(round(cos(a) * k)), 8 + int(round(sin(a) * k)), 160 if k < r else 255)
			_big_or_small(_anim_text, mid, 255 if fmod(_time, 0.25) < 0.17 else 90)
		"jackpot":
			var inv := fmod(_time, 0.2) < 0.1 and p < 0.5
			if inv:
				for y in rows:
					for x in c:
						d.dot(x, y, 200)
			_big_or_small(_anim_text, mid, 0 if inv else 255)
			_spark(delta, 3)
		"sparkle":
			_spark(delta, 2)
			_big_or_small(_anim_text, mid, 255)
		"big":
			var x := int(lerpf(c + 60.0, mid, minf(1.0, p * 3.0)))
			_big_or_small(_anim_text, x, 255)
		"tilt":
			_big_or_small(_anim_text, mid, 255 if fmod(_time, 0.4) < 0.25 else 0)
		"rocket":
			# a rocket climbs out of a smoke cloud through a scrolling starfield, then the words
			for i in 14:
				var sx := (i * 37 + 11) % c
				var sy := int(fmod(i * 5.3 + _time * 30.0, float(rows)))
				d.dot(sx, sy, 90)
			var rx := c - 14
			var ry := int(lerpf(rows + 6.0, -14.0, p))
			for yy in range(ry, ry + 9):
				var w := 0 if yy < ry + 2 else (1 if yy < ry + 4 else 2)
				for xx in range(rx - w, rx + w + 1):
					d.dot(xx, yy, 255)
			d.dot(rx - 3, ry + 8, 200)
			d.dot(rx + 3, ry + 8, 200)
			for k in 7:
				var fy := ry + 9 + k
				for xx in range(rx - 1 - int(k / 3.0), rx + 2 + int(k / 3.0)):
					if randf() < 0.75 - k * 0.08:
						d.dot(xx, fy, 230 - k * 25)
			_big_or_small(_anim_text, (c - 18) / 2, 255 if p > 0.2 else 120)
		"race":
			# two cars dash across a scrolling road, chequered flag text
			var off := int(_time * 60.0)
			for x in c:
				if (x + off) % 8 < 4:
					d.dot(x, rows - 1, 120)
					d.dot(x, 7, 50)
			for k in 2:
				var cx := int(p * 1.8 * c) - 16 - k * 22
				var cy := rows - 6
				for yy in range(cy - 2, cy + 2):
					for xx in range(cx - 5, cx + 6):
						d.dot(xx, yy - k * 7, 255 if k == 0 else 170)
				d.dot(cx - 3, cy + 2 - k * 7, 255)
				d.dot(cx + 3, cy + 2 - k * 7, 255)
			if p > 0.3:
				_big_or_small(_anim_text, mid, 255 if fmod(_time, 0.3) < 0.2 else 140)
		_:
			_big_or_small(_anim_text, mid, 255)


func _spark(delta: float, n: int) -> void:
	for i in n:
		_sparks.append([randi() % dmd.cols, randi() % dmd.rows, 1.0])
	for s in _sparks:
		s[2] -= delta * 2.5
		dmd.dot(s[0], s[1], int(255 * maxf(0.0, s[2])))
	_sparks = _sparks.filter(func(s: Array) -> bool: return s[2] > 0.0)


func _physics_process(_delta: float) -> void:
	# headless test hook: `godot --headless --path . --quit-after 7200 -- --autostart --demo --probe`
	if _probe and (Engine.get_physics_frames() % 400 == 0):
		var b: PinTable.Ball = table.balls[0] if table.balls.size() > 0 else null
		if Engine.get_physics_frames() == 400:
			print("[probe] style=%s view_h=%d pace=%.3f (tempo %.2f x view %.3f) px/unit=%.2f" % [_style, _view_h, table.pace, Settings.tempo, _view_factor, _px_per_unit])
		print("[probe] t=%ds state=%s ball=%d score=%d balls=%d pos=%s speed=%d bumpers=%d ramps=%d lanes=%d ride=%d mult=%d mb=%s lock=%s tilt=%.1f shots=%s" % [
			Engine.get_physics_frames() / 200, state, ball_no, score, table.balls.size(),
			b.pos.round() if b else Vector2.ZERO, int(b.vel.length()) if b else 0,
			table.bumper_hits, table.ramp_hits, table.lanes_lit(), table.targets_lit(),
			table.multiplier, table.multiball, table.lock_lit, table.tilt, table.shot_n])


# --- end of game: MATCH -> GAME OVER -> final score -> initials -> attract / menu ----

## Deterministic MATCH roll (rules dict: digits, step, odds). Returns the drawn number.
static func match_roll(rng: RandomNumberGenerator, final_score: int, m: Dictionary) -> int:
	var mod := int(pow(10, int(m.digits)))
	var step := maxi(1, int(m.step))
	var n := maxi(1, mod / step)
	var target := match_target(final_score, m)
	var odds := float(m.get("odds", -1.0))
	if odds < 0.0:
		return rng.randi_range(0, n - 1) * step
	if n == 1 or rng.randf() < odds:
		return target
	var v := rng.randi_range(0, n - 2) * step
	if v >= target:
		v += step
	return v


## The score's last `digits` digits, rounded down to the match step.
static func match_target(final_score: int, m: Dictionary) -> int:
	var mod := int(pow(10, int(m.digits)))
	var step := maxi(1, int(m.step))
	return (final_score / maxi(1, int(m.get("place", 1))) % mod) / step * step


func _set_state(s: String) -> void:
	state = s
	_state_t = 0.0
	print("[gameover] state=%s ball=%d score=%d" % [s, ball_no, score])


func _begin_match() -> void:
	_set_state("match")
	_match_used += 1
	if match_seed >= 0:
		_match_rng.seed = match_seed
	else:
		_match_rng.randomize()
	var m: Dictionary = rules.match
	_match_num = match_roll(_match_rng, score, m)
	_match_hit = _match_num == match_target(score, m)
	_match_show = 0
	_match_tick = 0.0
	_sparks.clear()
	print("[match] score=%d target=%d roll=%d hit=%s" % [score, match_target(score, m), _match_num, _match_hit])


func _award_match() -> void:
	# award "extra_ball": one more ball in the same game
	ball_no = BALLS
	_set_state("play")
	_save_armed = true
	table.reset_ball()
	table.input_enabled = true
	_bumpers_at_ball = table.bumper_hits
	_ramps_at_ball = table.ramp_hits
	_say("EXTRA CHANCE")
	_sting("extra_chance", "start")


func _begin_game_over() -> void:
	_set_state("gameover")
	table.input_enabled = false
	_sparks.clear()
	_sting("game_over", "tilt")


func _begin_final() -> void:
	_set_state("final")
	_new_high = Settings.qualifies(TABLE_ID, score)
	_sting("final_score", "bonus")


func _begin_entry() -> void:
	_set_state("entry")
	_entry_rank = Settings.rank_for(TABLE_ID, score)
	_entry_pos = 0
	_sting("highscore", "")
	var last := Settings.last_initials
	for i in 3:
		var ch := last[i] if i < last.length() else "A"
		_initials[i] = maxi(0, INITIAL_CHARS.find(ch))


## Initials entry: "prev" / "next" change the letter, "ok" confirms it, "back" goes back,
## "char:X" types a letter directly.
func entry_input(cmd: String) -> void:
	if state != "entry":
		return
	var n := INITIAL_CHARS.length()
	if cmd == "prev":
		_initials[_entry_pos] = (_initials[_entry_pos] + n - 1) % n
		Sound.play("flipper")
	elif cmd == "next":
		_initials[_entry_pos] = (_initials[_entry_pos] + 1) % n
		Sound.play("flipper")
	elif cmd == "back":
		_entry_pos = maxi(0, _entry_pos - 1)
	elif cmd.begins_with("char:"):
		_initials[_entry_pos] = maxi(0, INITIAL_CHARS.find(cmd.substr(5, 1)))
		_entry_advance()
	elif cmd == "ok":
		_entry_advance()


func _entry_advance() -> void:
	Sound.play("rollover")
	_entry_pos += 1
	if _entry_pos >= 3:
		_finish_entry()


func entry_name() -> String:
	var s := ""
	for i in 3:
		s += INITIAL_CHARS[_initials[i]]
	return s


func _finish_entry() -> void:
	var nm := entry_name()
	_last_rank = Settings.add_high_score(TABLE_ID, nm, score)
	print("[gameover] saved %s %d rank %d" % [nm, score, _last_rank + 1])
	Sound.play("start")
	_begin_over()


func _begin_over() -> void:
	_set_state("over")


func _leave() -> void:
	_set_state("done")
	finished.emit()
	if get_tree().current_scene == self:
		get_tree().change_scene_to_file.call_deferred("res://scenes/title.tscn")


func _end_flow(delta: float) -> void:
	match state:
		"drain":
			if _state_t > 2.4:
				_next_ball()
		"match":
			var m: Dictionary = rules.match
			var spin := float(m.spin_time)
			if _state_t < spin:
				_match_tick -= delta
				if _match_tick <= 0.0:
					var p := _state_t / spin
					_match_tick = lerpf(0.05, 0.34, p * p)
					var step := maxi(1, int(m.step))
					var n := maxi(1, int(pow(10, int(m.digits))) / step)
					_match_show = ((_match_show / step + 1 + randi() % maxi(1, n - 1)) % n) * step
					_sting("match_tick", "rollover")
			elif _state_t - delta < spin:
				_match_show = _match_num
				_sting("match" if _match_hit else "match_miss", "jackpot" if _match_hit else "post")
				if _match_hit:
					_sparks.clear()
			elif _match_hit and _state_t > spin + 3.0:
				_award_match()
			elif not _match_hit and _state_t > spin + 1.4:
				_begin_game_over()
		"gameover":
			if _state_t > float(rules.game_over_time):
				_begin_final()
		"final":
			if _state_t > float(rules.final_score_time):
				if not Settings.demo and Settings.qualifies(TABLE_ID, score):
					_begin_entry()
				else:
					_begin_over()
		"entry":
			if _state_t > float(rules.entry_timeout):
				_finish_entry()
		"over":
			if Settings.demo and _state_t > 4.0:
				_start_game()
			elif not Settings.demo and _state_t > float(rules.attract_after):
				_leave()


func _draw_end(delta: float) -> void:
	var d := dmd
	var c := d.cols
	var rows := d.rows
	var mid := c / 2
	var t := _state_t
	match state:
		"match":
			var m: Dictionary = rules.match
			var dg := int(m.digits)
			var spin := float(m.spin_time)
			var q := t - spin
			if _match_hit and q > 0.0:
				if q < 1.4:
					var inv := fmod(t, 0.2) < 0.1
					if inv:
						for y in rows:
							for x in c:
								d.dot(x, y, 200)
					_big_or_small("MATCH!", mid, 0 if inv else 255)
				else:
					_big_or_small("EXTRA CHANCE", mid, 255 if fmod(t, 0.3) < 0.2 else 140)
				_spark(delta, 4)
				return
			# left: the score's digit(s) to match; right: the rolling number in a chasing frame
			var num := str(_match_show).pad_zeros(dg)
			var tg := str(match_target(score, m)).pad_zeros(dg)
			var w := d.text_width(num, 2)
			var x0 := mid + 8
			var x1 := x0 + w + 5
			if c < 90:
				x0 = c - w - 7
				x1 = c - 2
			var per := 2 * (x1 - x0) + 2 * (rows - 1)
			var head := int(t * 40.0)
			for i in per:
				var px: int
				var py: int
				if i < x1 - x0:
					px = x0 + i; py = 0
				elif i < x1 - x0 + rows - 1:
					px = x1; py = i - (x1 - x0)
				elif i < 2 * (x1 - x0) + rows - 1:
					px = x1 - (i - (x1 - x0 + rows - 1)); py = rows - 1
				else:
					px = x0; py = rows - 1 - (i - (2 * (x1 - x0) + rows - 1))
				var on := (i + head) % 6 < 3 if q < 0.0 else true
				d.dot(px, py, 255 if on else 60)
			d.text(num, x0 + 3, 1, 2, -1, 255 if q < 0.0 or fmod(t, 0.5) < 0.35 else 120)
			# score digit, big, left of centre
			d.text(tg, mid - 8, 1, 2, 1, 255)
			if mid - 12 - d.text_width(tg, 2) >= d.text_width("MATCH", 1) + 2:
				d.text("MATCH", 2, 1)
				d.text("NO MATCH" if q > 0.0 else "SCORE", 2, 9, 1, -1, 200)
		"gameover":
			var txt := "GAME OVER"
			var s := 2 if d.text_width(txt, 2) <= c - 4 else 1
			var w := d.text_width(txt, s)
			var x0 := mid - w / 2
			var y_end := 1 if s == 2 else 4
			var inv := t > 1.5 and t < 2.1 and fmod(t, 0.2) < 0.1
			if inv:
				for y in rows:
					for x in c:
						d.dot(x, y, 200)
			for i in txt.length():
				var ti := t - i * 0.09
				if ti <= 0.0:
					continue
				var f := minf(1.0, ti * 3.2)
				var y := y_end - int(round((1.0 - f) * (1.0 - f) * 18.0))
				if f >= 1.0 and ti < 0.55:
					y -= int(round(sin((ti - 0.31) / 0.24 * PI) * 2.0))
				d.text(txt[i], x0 + i * 6 * s, y, s, -1, 0 if inv else 255)
			if t > 2.1:
				_spark(delta, 2)
				# expanding rings from both sides
				var r := fmod(t - 2.1, 1.0) * 24.0
				for side in [3, c - 4]:
					for a in 24:
						var ang := a * TAU / 24.0
						d.dot(side + int(round(cos(ang) * r * 0.4)), rows / 2 + int(round(sin(ang) * r * 0.3)), 90)
		"final":
			if t < 0.9:
				_big_or_small("FINAL SCORE", mid, 255)
			elif _new_high and t > 1.9 and fmod(t, 0.6) < 0.3:
				_big_or_small("HIGH SCORE!", mid, 255)
			else:
				_big_or_small(Util.fmt_score(score), mid, 255)
				if _new_high:
					_spark(delta, 2)
		"entry":
			var nm := entry_name()
			var iw := d.text_width("WWW", 2)
			var ix := c - 2 - iw if c >= 100 else mid - iw / 2
			if c >= 100:
				d.text("#%d HIGH SCORE" % (_entry_rank + 1), 2, 1)
				d.text("ENTER INITIALS", 2, 9, 1, -1, 200)
			for i in 3:
				var ch := nm[i]
				var xx := ix + i * 12
				var cur := i == _entry_pos
				d.text("-" if ch == " " and not cur else ch, xx, 1, 2, -1, 255 if (not cur or fmod(t, 0.5) < 0.35) else 110)
				if cur:
					for x in 10:
						d.dot(xx + x, rows - 1, 255)
		"over", "done":
			var pages: Array = ["GAME OVER", Util.fmt_score(score), "PRESS START", "HIGH SCORES"]
			var hs := Settings.scores_for(TABLE_ID)
			for i in hs.size():
				pages.append("%d %s %s" % [i + 1, hs[i][0], Util.fmt_score(int(hs[i][1]))])
			var pi := int(t / 2.2) % pages.size()
			var v := 255
			if pi == 2 or (pi >= 4 and pi - 4 == _last_rank):
				v = 255 if fmod(t, 0.5) < 0.35 else 90
			_big_or_small(pages[pi], mid, v)


## Still shots (`--still-cam=Y --still-ball=X,Y`): a frozen, staged frame (ball placed, one bumper
## flashing, fixed score and lamp time) so before/after art comparisons use the identical frame.
func _still_setup() -> void:
	if not Settings.still:
		return
	Settings.persist = false
	table.frozen = true
	table._time = 7.0
	table.input_enabled = false
	score = 1234560
	if table.balls.size() > 0 and Settings.still_ball.x >= 0.0:
		table.balls[0].pos = Settings.still_ball
		table.balls[0].vel = Vector2.ZERO
	if table.bumper_flash.size() > 0:
		table.bumper_flash[0] = 0.9


## Screenshot hook: `-- --autostart --end-preview=match-hit|match-miss|gameover|final|entry|over[@SEC]`
## jumps straight into the end-of-game sequence (nothing is saved).
func _end_preview() -> void:
	var arg := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--end-preview="):
			arg = a.get_slice("=", 1)
	if arg == "":
		return
	if arg.contains("@"):
		_preview_hold = float(arg.get_slice("@", 1))
		arg = arg.get_slice("@", 0)
	Settings.persist = false
	score = 2345670
	ball_no = BALLS + 1
	table.clear_balls()
	table.input_enabled = false
	match arg:
		"match-hit", "match-miss":
			var rng := RandomNumberGenerator.new()
			for sd in 1000:
				rng.seed = sd
				if (match_roll(rng, score, rules.match) == match_target(score, rules.match)) == (arg == "match-hit"):
					match_seed = sd
					break
			_begin_match()
		"gameover":
			_begin_game_over()
		"final":
			_begin_final()
		"entry":
			_begin_entry()
			_initials[0] = INITIAL_CHARS.find("A")
			_entry_pos = 1
		_:
			_begin_over()


## Named stinger through the audio manager ('match', 'game_over', 'highscore', ...);
## falls back to a plain sound effect, silently when that is missing too.
func _sting(stinger: String, fallback := "") -> void:
	if Sound.has_method("play_stinger"):
		Sound.call("play_stinger", stinger)
	elif fallback != "":
		Sound.play(fallback)
