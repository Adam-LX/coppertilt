class_name VideoModes
extends RefCounted
## DMD Video Modes (Mini-Games) for Copper Tilt:
## - "duck_hunt" (Midnight Funfair): Carnival shooting gallery with moving ducks and rabbits
## - "redline_overtake" (Copper Speedway): 3-lane arcade highway racer with traffic, nitro and overtakes
## - "lunar_lander" (Launch Pad): Apollo lunar lander with gravity, RCS thrusters and landing pad
##
## Controlled by flipper buttons (left/right) and plunger/action button.
## Runs on the DotMatrix (128x16) while the ball is safely held in a hole.

signal finished(score: int, award_type: String, award_text: String)

const MODE_TIME := 15.0

var active := false
var mode_id := ""
var time_left := 0.0
var score := 0
var completed := false
var game_over := false
var end_delay := 0.0

# --- Duck Hunt state ---
var _cross_x := 64.0
var _cross_y := 8.0
var _ducks: Array = []        # [{x, y, vx, kind, hit, points}]
var _shots_left := 12
var _ducks_hit := 0
var _shot_flash := 0.0

# --- Redline Overtake state ---
var _player_lane := 1         # 0 = top (y=2), 1 = mid (y=7), 2 = bot (y=12)
var _player_x := 16
var _traffic: Array = []      # [{x, lane, speed, kind}]
var _spawn_timer := 0.0
var _nitro_active := 0.0
var _overtakes := 0
var _crashes := 0
var _crash_timer := 0.0

# --- Lunar Lander state ---
var _lander_x := 64.0
var _lander_y := 2.0
var _lander_vx := 0.0
var _lander_vy := 0.0
var _fuel := 100.0
var _pad_x := 56
var _pad_w := 18
var _touchdown := false
var _thrust_main := false
var _thrust_left := false
var _thrust_right := false
var _crashed := false
var _debris: Array = []


func start(id: String) -> void:
	mode_id = id
	active = true
	time_left = MODE_TIME
	score = 0
	completed = false
	game_over = false
	end_delay = 0.0
	match id:
		"duck_hunt":
			_init_duck_hunt()
		"redline_overtake":
			_init_redline_overtake()
		"lunar_lander":
			_init_lunar_lander()


func handle_input(action: String) -> void:
	if not active or game_over:
		return
	match mode_id:
		"duck_hunt":
			match action:
				"left":
					_cross_x = maxf(8.0, _cross_x - 14.0)
				"right":
					_cross_x = minf(120.0, _cross_x + 14.0)
				"action":
					_fire_duck_shot()
		"redline_overtake":
			if _crash_timer > 0.0:
				return
			match action:
				"left":
					if _player_lane > 0:
						_player_lane -= 1
						Sound.play("tire_screech", 1.2, -6.0)
				"right":
					if _player_lane < 2:
						_player_lane += 1
						Sound.play("tire_screech", 1.0, -6.0)
				"action":
					if _nitro_active <= 0.0:
						_nitro_active = 2.5
						Sound.play("turbo_blowoff", 1.2, -4.0)
		"lunar_lander":
			if _touchdown or _crashed:
				return
			match action:
				"left":
					_thrust_right = true
					Sound.play("telemetry_chirp", 1.3, -8.0)
				"right":
					_thrust_left = true
					Sound.play("telemetry_chirp", 1.3, -8.0)
				"action":
					_thrust_main = true
					Sound.play("launch", 1.4, -6.0)


func handle_input_release(action: String) -> void:
	if not active or game_over:
		return
	if mode_id == "lunar_lander":
		match action:
			"left":
				_thrust_right = false
			"right":
				_thrust_left = false
			"action":
				_thrust_main = false


func update(delta: float, dmd: DotMatrix) -> bool:
	if not active:
		return false

	dmd.clear()

	if game_over:
		end_delay -= delta
		_draw_game_over(dmd)
		dmd.present()
		if end_delay <= 0.0:
			active = false
			var aw_type := "points"
			var aw_text := "%d PTS" % score
			if completed:
				aw_type = "extra_ball"
				aw_text = "EXTRA BALL"
			finished.emit(score, aw_type, aw_text)
			return false
		return true

	time_left = maxf(0.0, time_left - delta)

	match mode_id:
		"duck_hunt":
			_update_duck_hunt(delta, dmd)
		"redline_overtake":
			_update_redline_overtake(delta, dmd)
		"lunar_lander":
			_update_lunar_lander(delta, dmd)

	# Global HUD overlay: remaining time & score
	_draw_hud(dmd)

	dmd.present()

	if time_left <= 0.0 and not game_over:
		_end_mode(score >= 80000)

	return true


# =========================================================================
# HUD & COMMON
# =========================================================================
func _draw_hud(dmd: DotMatrix) -> void:
	# Small 1-row text for timer and score
	var t_sec := ceili(time_left)
	dmd.text("T:%d" % t_sec, 2, 0, 1, -1, 160)
	dmd.text("%d" % score, dmd.cols - 2, 0, 1, 1, 240)


func _end_mode(win: bool) -> void:
	game_over = true
	completed = win
	end_delay = 2.4
	if win:
		Sound.play("jackpot", 1.0)
	else:
		Sound.play("bonus", 0.9)


func _draw_game_over(dmd: DotMatrix) -> void:
	var mid := dmd.cols / 2
	if completed:
		dmd.text("PERFECT WIN!", mid, 1, 1, 0, 255)
		dmd.text("+%d EXTRA BALL" % score, mid, 8, 1, 0, 220)
	else:
		dmd.text("TIME UP!", mid, 1, 1, 0, 255)
		dmd.text("FINAL: %d" % score, mid, 8, 1, 0, 190)


# =========================================================================
# 1. DUCK HUNT (Midnight Funfair)
# =========================================================================
const DUCK_SPR := [
	" 0110 ",
	"011110",
	" 11111",
	"  110 "
]

const RABBIT_SPR := [
	" 1 1 ",
	" 111 ",
	"11111",
	" 111 "
]

func _init_duck_hunt() -> void:
	_cross_x = 64.0
	_cross_y = 8.0
	_shots_left = 12
	_ducks_hit = 0
	_shot_flash = 0.0
	_ducks.clear()
	# Row 1 (top shelf, moves right)
	for i in 4:
		_ducks.append({"x": float(i * 32), "y": 3, "vx": 24.0, "kind": "duck", "hit": 0.0})
	# Row 2 (bottom shelf, moves left)
	for i in 4:
		_ducks.append({"x": float(128 - i * 32), "y": 9, "vx": -20.0, "kind": "duck", "hit": 0.0})
	# Golden rabbit
	_ducks.append({"x": -20.0, "y": 3, "vx": 42.0, "kind": "rabbit", "hit": 0.0})


func _fire_duck_shot() -> void:
	_shot_flash = 0.12
	Sound.play("target", 1.3, -2.0)
	var hit_any := false
	for d in _ducks:
		if d.hit > 0.0:
			continue
		var dx := absf(float(d.x) + 3.0 - _cross_x)
		var dy := absf(float(d.y) + 2.0 - _cross_y)
		if dx < 6.0 and dy < 5.0:
			d.hit = 0.8
			hit_any = true
			var pts := 25000 if d.kind == "rabbit" else 10000
			score += pts
			_ducks_hit += 1
			Sound.play("rollover", 1.4, -2.0)
			break
	if not hit_any:
		Sound.play("post", 0.9, -4.0)


func _update_duck_hunt(delta: float, dmd: DotMatrix) -> void:
	# Flash effect when firing
	if _shot_flash > 0.0:
		_shot_flash -= delta

	# Draw shelf rails
	dmd.line(0, 7, dmd.cols - 1, 7, 70)
	dmd.line(0, 14, dmd.cols - 1, 14, 70)

	# Update and draw targets
	for d in _ducks:
		if d.hit > 0.0:
			d.hit -= delta
			# Hit explosion / spin
			var fx: int = int(d.x)
			var fy: int = int(d.y)
			dmd.circle(fx + 3, fy + 2, 2, 255)
			dmd.text("+%d" % (25 if d.kind == "rabbit" else 10), fx - 2, fy - 2, 1, -1, 180)
			continue

		d.x += float(d.vx) * delta
		if float(d.vx) > 0.0 and float(d.x) > dmd.cols + 6:
			d.x = -12.0
		elif float(d.vx) < 0.0 and float(d.x) < -12.0:
			d.x = float(dmd.cols + 6)

		var spr := RABBIT_SPR if d.kind == "rabbit" else DUCK_SPR
		var val := 255 if d.kind == "rabbit" else 200
		dmd.sprite(int(d.x), int(d.y), spr, val)

	# Draw crosshair target
	var cx := int(_cross_x)
	var cy := int(_cross_y)
	dmd.line(cx - 3, cy, cx + 3, cy, 255)
	dmd.line(cx, cy - 3, cx, cy + 3, 255)
	dmd.circle(cx, cy, 3, 160)

	if _ducks_hit >= 8 and not game_over:
		_end_mode(true)


# =========================================================================
# 2. REDLINE OVERTAKE (Copper Speedway)
# =========================================================================
const CAR_PLAYER_SPR := [
	"0111110",
	"1111111",
	"0111110",
	" 10001 "
]

const CAR_RIVAL_SPR := [
	"011110",
	"111111",
	"011110"
]

const NITRO_SPR := [
	" 11 ",
	"1111",
	" 11 "
]

func _init_redline_overtake() -> void:
	_player_lane = 1
	_traffic.clear()
	_spawn_timer = 0.0
	_nitro_active = 0.0
	_overtakes = 0
	_crashes = 0
	_crash_timer = 0.0


func _update_redline_overtake(delta: float, dmd: DotMatrix) -> void:
	if _nitro_active > 0.0:
		_nitro_active -= delta

	if _crash_timer > 0.0:
		_crash_timer -= delta

	# Scrolling track lane lines (at y=5 and y=10)
	var road_spd := 110.0 if _nitro_active > 0.0 else 60.0
	var offset := int(time_left * road_spd) % 10
	for x in range(-10 + offset, dmd.cols + 10, 10):
		dmd.line(x, 5, x + 4, 5, 80)
		dmd.line(x, 10, x + 4, 10, 80)

	# Spawn traffic & nitro
	_spawn_timer -= delta
	if _spawn_timer <= 0.0:
		_spawn_timer = randf_range(0.8, 1.4)
		var lane := randi() % 3
		var is_nitro := randf() < 0.25
		_traffic.append({
			"x": float(dmd.cols + 10),
			"lane": lane,
			"speed": 35.0 if not is_nitro else 45.0,
			"kind": "nitro" if is_nitro else "rival",
			"passed": false
		})

	# Player car y coordinates per lane
	var lane_y: Array[int] = [1, 6, 11]
	var py: int = lane_y[_player_lane]

	# Update traffic
	var i := 0
	while i < _traffic.size():
		var tr: Dictionary = _traffic[i]
		var spd: float = float(tr.speed) + (40.0 if _nitro_active > 0.0 else 0.0)
		tr.x -= spd * delta
		var ty: int = lane_y[int(tr.lane)]

		# Collision detection
		var dist_x := absf(float(tr.x) - float(_player_x))
		if tr.lane == _player_lane and dist_x < 7.0 and _crash_timer <= 0.0:
			if tr.kind == "nitro":
				score += 25000
				_nitro_active = 3.0
				Sound.play("turbo_blowoff", 1.25)
				_traffic.remove_at(i)
				continue
			else:
				# Crash with rival
				_crashes += 1
				_crash_timer = 0.8
				Sound.play("backfire", 0.9, 0.0)
				dmd.circle(_player_x + 3, py + 2, 4, 255)
				_traffic.remove_at(i)
				continue

		# Overtake check
		if not tr.passed and float(tr.x) < float(_player_x) and tr.kind == "rival":
			tr.passed = true
			_overtakes += 1
			score += 15000
			Sound.play("engine_shift", 1.1, -4.0)

		# Draw obstacle
		if tr.kind == "nitro":
			dmd.sprite(int(tr.x), ty, NITRO_SPR, 255 if fmod(time_left, 0.2) < 0.1 else 160)
		else:
			dmd.sprite(int(tr.x), ty, CAR_RIVAL_SPR, 160)

		if float(tr.x) < -16.0:
			_traffic.remove_at(i)
		else:
			i += 1

	# Draw player car
	if _crash_timer <= 0.0 or fmod(_crash_timer, 0.15) < 0.08:
		dmd.sprite(_player_x, py, CAR_PLAYER_SPR, 255)
		# Exhaust flame if nitro
		if _nitro_active > 0.0:
			dmd.dot(_player_x - 1, py + 1, 255)
			dmd.dot(_player_x - 2, py + 1, 200)

	if _overtakes >= 8 and not game_over:
		_end_mode(true)


# =========================================================================
# 3. LUNAR LANDER (Launch Pad)
# =========================================================================
const LANDER_SPR := [
	"  111  ",
	" 11111 ",
	"1101011",
	"1111111",
	" 1 1 1 ",
	"1  1  1"
]

func _init_lunar_lander() -> void:
	_lander_x = 24.0
	_lander_y = 1.0
	_lander_vx = 6.0
	_lander_vy = 0.0
	_fuel = 100.0
	_pad_x = 74
	_pad_w = 20
	_touchdown = false
	_crashed = false
	_thrust_main = false
	_thrust_left = false
	_thrust_right = false
	_debris.clear()


func _update_lunar_lander(delta: float, dmd: DotMatrix) -> void:
	# Moon surface terrain & landing pad
	dmd.line(0, 15, dmd.cols - 1, 15, 60)
	dmd.line(_pad_x, 15, _pad_x + _pad_w, 15, 255)
	# Beacons on landing pad
	if fmod(time_left, 0.4) < 0.2:
		dmd.dot(_pad_x, 14, 255)
		dmd.dot(_pad_x + _pad_w, 14, 255)

	# Fuel gauge top left
	dmd.text("F:%d" % int(_fuel), 24, 0, 1, -1, 140)

	if not _touchdown and not _crashed:
		# Physics
		_lander_vy += 8.0 * delta   # Lunar gravity
		if _fuel > 0.0:
			if _thrust_main:
				_lander_vy -= 18.0 * delta
				_fuel = maxf(0.0, _fuel - 18.0 * delta)
				# Exhaust flame
				dmd.dot(int(_lander_x) + 3, int(_lander_y) + 6, 255)
				dmd.dot(int(_lander_x) + 3, int(_lander_y) + 7, 180)
			if _thrust_left:
				_lander_vx += 14.0 * delta
				_fuel = maxf(0.0, _fuel - 8.0 * delta)
				dmd.dot(int(_lander_x) - 1, int(_lander_y) + 3, 200)
			if _thrust_right:
				_lander_vx -= 14.0 * delta
				_fuel = maxf(0.0, _fuel - 8.0 * delta)
				dmd.dot(int(_lander_x) + 7, int(_lander_y) + 3, 200)

		_lander_x += _lander_vx * delta
		_lander_y += _lander_vy * delta

		# Screen boundary bounce
		if _lander_x < 2.0:
			_lander_x = 2.0
			_lander_vx = absf(_lander_vx) * 0.5
		elif _lander_x > dmd.cols - 9:
			_lander_x = dmd.cols - 9
			_lander_vx = -absf(_lander_vx) * 0.5

		# Touchdown / crash detection
		if _lander_y >= 9.0:
			_lander_y = 9.0
			var center_x := _lander_x + 3
			var on_pad: bool = center_x >= _pad_x and center_x <= (_pad_x + _pad_w)
			var soft_v: bool = _lander_vy < 7.0 and absf(_lander_vx) < 5.0
			if on_pad and soft_v:
				_touchdown = true
				score += 250000
				Sound.play("jackpot", 1.0)
				_end_mode(true)
			else:
				_crashed = true
				score += 25000
				Sound.play("backfire", 0.85)
				for k in 12:
					_debris.append({"x": _lander_x + 3, "y": _lander_y + 3,
						"vx": randf_range(-15, 15), "vy": randf_range(-12, -2)})
				_end_mode(false)

		dmd.sprite(int(_lander_x), int(_lander_y), LANDER_SPR, 255)
	elif _touchdown:
		dmd.sprite(int(_lander_x), int(_lander_y), LANDER_SPR, 255)
		dmd.text("EAGLE LANDED!", dmd.cols / 2, 2, 1, 0, 255)
	elif _crashed:
		for p in _debris:
			p.x += float(p.vx) * delta
			p.y += float(p.vy) * delta
			dmd.dot(int(p.x), int(p.y), 220)
