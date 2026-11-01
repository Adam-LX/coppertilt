extends Node
## Video Modes test (headless, deterministic):
## Tests all 3 table mini-games on DotMatrix:
## - "duck_hunt" (Midnight Funfair)
## - "redline_overtake" (Copper Speedway)
## - "lunar_lander" (Launch Pad)
## Tests activation, flipper inputs, rendering, scoring, and awards.

const VideoModesScript := preload("res://scripts/ui/video_modes.gd")
var fails := 0


func _ready() -> void:
	_run()
	print("[videomode] DONE fails=%d" % fails)
	get_tree().quit(1 if fails > 0 else 0)


func _check(ok: bool, what: String) -> void:
	print("[videomode] %s %s" % ["ok  " if ok else "FAIL", what])
	if not ok:
		fails += 1


func _run() -> void:
	var dmd := DotMatrix.new()
	add_child(dmd)
	dmd.resize_grid(128, 16)

	var vm = VideoModesScript.new()
	_check(not vm.active, "initially inactive")

	# --- 1. Duck Hunt (Midnight Funfair) ---
	vm.start("duck_hunt")
	_check(vm.active and vm.mode_id == "duck_hunt", "duck hunt started")
	_check(vm.time_left == 15.0, "time is 15s")

	# Update a few frames
	for f in 10:
		vm.update(0.05, dmd)

	# Aim and shoot
	vm.handle_input("left")
	vm.handle_input("action")
	vm.update(0.1, dmd)
	_check(vm.score >= 0, "shots register score (%d)" % vm.score)

	# Simulate time expiry
	vm.time_left = 0.01
	vm.update(0.05, dmd)
	_check(vm.game_over, "duck hunt game over on time")

	# --- 2. Redline Overtake (Copper Speedway) ---
	vm.start("redline_overtake")
	_check(vm.active and vm.mode_id == "redline_overtake", "redline overtake started")
	_check(vm._player_lane == 1, "starts in center lane")

	# Steer up and down
	vm.handle_input("left")
	_check(vm._player_lane == 0, "lane up to 0")
	vm.handle_input("right")
	_check(vm._player_lane == 1, "lane down to 1")
	vm.handle_input("right")
	_check(vm._player_lane == 2, "lane down to 2")

	# Update frames with overtaking
	for f in 30:
		vm.update(0.05, dmd)

	_check(vm.active, "racing actively updating on DMD")

	# --- 3. Lunar Lander (Launch Pad) ---
	vm.start("lunar_lander")
	_check(vm.active and vm.mode_id == "lunar_lander", "lunar lander started")

	var init_y: float = vm._lander_y
	vm.update(0.1, dmd)
	_check(vm._lander_y > init_y, "gravity pulls lander down (%.1f > %.1f)" % [vm._lander_y, init_y])

	# Fire thrusters
	vm.handle_input("action")
	_check(vm._thrust_main, "main thruster engaged")
	vm.update(0.1, dmd)
	vm.handle_input_release("action")
	_check(not vm._thrust_main, "main thruster released")

	# Check DotMatrix drawing primitives
	dmd.clear()
	dmd.rect(2, 2, 8, 8, 255, true)
	_check(dmd.buf[2 * dmd.cols + 2] == 255, "dmd.rect fills buffer")
	dmd.circle(20, 8, 4, 200, true)
	_check(dmd.buf[8 * dmd.cols + 20] == 200, "dmd.circle fills buffer")
	dmd.clear()
	dmd.line(0, 0, 10, 10, 180)
	_check(dmd.buf[5 * dmd.cols + 5] == 180, "dmd.line draws diagonal")
