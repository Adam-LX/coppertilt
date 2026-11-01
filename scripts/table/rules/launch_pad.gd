extends "res://scripts/table/rules/table_rules.gd"
## Launch Pad rules: F-U-E-L lanes (bonus X), M-A-R-S targets (kickback), STAGE 1-2-3 drops light
## the hangar lock, P-A-D drops (bonus X). Gantry + booster ramps light the lock, two locks =
## LIFTOFF MULTIBALL (gantry/booster = JACKPOT, then LIFTOFF wire = SUPER JACKPOT). The liftoff
## wire counts down T-MINUS 4..0 (extra ball at zero), Mission Control saucer gives awards, orbits
## light the extra ball, stars raise the spinner.

var count_n := 0     # T-MINUS countdown progress (liftoff shots)
var orbit_n := 0
var video_mode_lit := false


func shots() -> Array:
	return ["lorbit", "rorbit", "gantry", "booster", "liftoff", "silo", "control", "hangar"]


func flashers() -> Dictionary:
	return {"top": [[162, 140], Color(1.0, 0.7, 0.3), 120.0], "nest": [[160, 252], Color(1.0, 0.55, 0.2), 130.0],
		"sling0": [[64, 500], Color(1.0, 0.5, 0.15), 90.0], "sling1": [[236, 500], Color(0.25, 0.6, 1.0), 90.0],
		"gantry": [[72, 300], Color(0.9, 0.92, 1.0), 150.0], "booster": [[228, 300], Color(0.3, 0.6, 1.0), 150.0],
		"liftoff": [[160, 262], Color(1.0, 0.6, 0.2), 150.0], "control": [[150, 304], Color(0.5, 1.0, 0.6), 120.0]}


func reset_game() -> void:
	count_n = 0
	orbit_n = 0
	video_mode_lit = false


func on_bumper(bi: int, _b) -> void:
	t.flash["top" if bi < 3 else "nest"] = 1.0
	t._score(100)
	if randf() < 0.35:
		Sound.play("plasma_shield", randf_range(0.9, 1.15), -4.0)
	if t.bumper_hits % 50 == 0:
		t._score(50000)
		say("SOLAR FLARE 50,000", "bonus", "sparkle")


func on_lane(i: int) -> void:
	skill_lane()
	light_lane(i, func() -> void: bump_multiplier("FUEL 25,000"))


func on_target(i: int) -> void:
	if t.ride[i]:
		t._score(500)
		return
	t.ride[i] = true
	t._score(1500)
	if t.ride.count(true) == t.ride.size():
		for k in t.ride.size():
			t.ride[k] = false
		t._score(25000)
		t.kickback_lit = true
		t.announce.emit("MARS MISSION - KICKBACK", "jackpot")
		t.dmd_anim.emit("sparkle", "KICKBACK LIT")


func on_drop(_i: int) -> void:
	t._score(2500)


func on_spinner() -> void:
	super.on_spinner()
	if randf() < 0.3:
		Sound.play("telemetry_chirp", randf_range(0.9, 1.2), -6.0)


func on_bank(bank: String) -> void:
	if bank == "stage":
		t._score(25000)
		t.lock_lit = true
		video_mode_lit = true
		Sound.play("plasma_shield", 1.05)
		Sound.play("countdown_beep", 1.3, -4.0)
		Sound.play_voice("stage_separation")
		t.announce.emit("LUNAR LANDER LIT - SHOOT SILO", "jackpot")
		t.dmd_anim.emit("saturn_liftoff", "LANDER LIT")
	else:
		t._score(20000)
		bump_multiplier("FUEL 25,000")
		Sound.play("telemetry_chirp", 1.1)
		Sound.play_voice("t_minus_zero")
		t.announce.emit("PAD CLEARED", "jackpot")


func on_star(i: int) -> void:
	t._score(1000 if not t.stars[i] else 300)
	t.stars[i] = true
	if t.stars.count(true) == t.stars.size():
		for k in t.stars.size():
			t.stars[k] = false
		t.spinner_level = mini(t.spinner_level + 1, 5)
		t._score(10000)
		t.announce.emit("SPINNER %dX" % t.spinner_level, "bonus")


func on_orbit(name: String) -> void:
	var k := "lorbit" if name == "left" else "rorbit"
	t.shot_n[k] += 1
	t._chase[k] = 0.8
	orbit_n += 1
	t._score(5000 * t.multiplier)
	if orbit_n % 4 == 0:
		t.extra_lit = true
		say("EXTRA BALL IS LIT", "bonus", "sparkle", "EXTRA BALL LIT")
	elif orbit_n % 4 == 2:
		Sound.play_voice("solar_flare")
		say("ORBIT TRAJECTORY", "bonus", "radar_sweep")
	else:
		say("ORBIT TRAJECTORY", "bonus", "radar_sweep")


func on_hole(b, hn: String) -> void:
	match hn:
		"silo":
			b.sprite.visible = false
			if video_mode_lit and not t.tilted:
				video_mode_lit = false
				b.held = 22.0
				t.video_mode_start.emit("lunar_lander")
				return
			t._score(15000 * t.multiplier)
			say("FUEL SILO", "bonus", "saturn_liftoff")
		"hangar":
			b.sprite.visible = false
			if t.lock_lit and not t.multiball and not t.tilted:
				t.locked += 1
				t._score(25000)
				if t.locked >= 2:
					start_multiball(2, "LIFTOFF MULTIBALL", "rocket")
				else:
					# virtual lock: this ball continues, the lock is 'held' in the hangar
					t.announce.emit("BALL 1 LOCKED", "bonus")
					t.dmd_anim.emit("big", "BALL LOCKED")
			else:
				t._score(10000)
				say("HANGAR", "", "sparkle")
		"control":
			if t.extra_lit and not t.tilted:
				t.extra_lit = false
				t.extra_ball.emit()
				say("EXTRA BALL", "jackpot", "jackpot")
				return
			var awards := ["5,000", "LIGHT KICKBACK", "25,000", "BONUS X", "LIGHT LOCK", "50,000"]
			var i := randi() % awards.size()
			match i:
				0: t._score(5000)
				1: t.kickback_lit = true
				2: t._score(25000)
				3: bump_multiplier("FUEL 25,000")
				4: t.lock_lit = true
				5: t._score(50000)
			t.announce.emit("MISSION CONTROL: " + awards[i], "bonus")
			t.dmd_anim.emit("big", awards[i])


func on_ramp(_ri: int, name: String) -> void:
	if t.multiball:
		if name == "liftoff" and t.super_lit:
			t.super_lit = false
			t._score(1000000)
			say("SUPER JACKPOT", "jackpot", "rocket")
			jackpot_fx()
			return
		if name != "liftoff":
			t._score(250000)
			t.super_lit = true
			say("JACKPOT", "jackpot", "jackpot")
			jackpot_fx()
			return
	if name == "liftoff":
		count_n += 1
		t._score(25000 * t.multiplier)
		Sound.play("countdown_beep", 0.9 + (count_n % 5) * 0.1, -1.0)
		if count_n % 5 == 0:
			t.extra_lit = true
			Sound.play_voice("t_minus_zero")
			say("LIFTOFF - EXTRA BALL LIT", "jackpot", "saturn_liftoff", "EXTRA BALL LIT")
		elif count_n % 3 == 0:
			video_mode_lit = true
			Sound.play_voice("stage_separation")
			say("LUNAR LANDER LIT - SHOOT SILO", "bonus", "stage_sep", "VIDEO MODE")
		else:
			say("T-MINUS %d" % (5 - count_n % 5), "bonus", "rocket")
		return
	t._score(10000 * t.multiplier)
	if not t.lock_lit:
		t.ramps_to_lock += 1
		if t.ramps_to_lock >= 3:
			t.lock_lit = true
			t.ramps_to_lock = 0
			say("LOCK IS LIT", "bonus", "rocket")
			return
	say("GANTRY" if name == "gantry" else "BOOSTER", "bonus", "rocket")


func lamp_states() -> Dictionary:
	var on: Dictionary = {}
	for i in t.ride.size():
		on["mars_" + "MARS"[i]] = 1 if t.ride[i] else (3 if t.target_flash[i] > 0.0 else 0)
	for shot in shots():
		var n := chase_len(shot)
		var prog: int = t.shot_n[shot] % (n + 1)
		if shot == "gantry" or shot == "booster":
			prog = t.ramps_to_lock if not t.lock_lit else n
		var arrow := 1
		if t.multiball and (shot == "gantry" or shot == "booster"):
			arrow = 3
		elif t.multiball and shot == "liftoff" and t.super_lit:
			arrow = 3
		elif t.lock_lit and shot == "hangar":
			arrow = 3
		elif t.extra_lit and shot == "control":
			arrow = 2
		elif shot == "lorbit" and t.spin_v > 0.0:
			arrow = 3
		shot_lamps(on, shot, arrow, prog)
	on["jackpot"] = 3 if t.multiball else 0
	on["lock"] = 2 if t.lock_lit else (1 if t.locked > 0 else 0)
	on["extra_l"] = 1 if t.kickback_lit else 0
	on["extra_r"] = 2 if t.save_lit else 0
	# T-MINUS ladder: count0 (bottom) .. count4 (green, liftoff); chases in multiball
	var lit := count_n % 5
	for i in 5:
		var st := 1 if i < lit else (2 if i == lit else 0)
		if t.multiball or t._chase.has("liftoff"):
			st = 1 if (int(t._time * 12.0) - i) % 5 == 0 else 0
		on["count%d" % i] = st
	finish_lamps(on)
	on["super"] = 2 if t.super_lit else 0
	on["lock1"] = 1 if t.locked >= 1 else (2 if t.lock_lit else 0)
	on["lock2"] = 2 if t.lock_lit and t.locked >= 1 else 0
	return on


func mission_lines() -> PackedStringArray:
	var a := ""
	if t.multiball:
		a = "LIFTOFF = SUPER JACKPOT" if t.super_lit else "RAMPS = JACKPOT"
	elif t.lock_lit:
		a = "HANGAR: LOCK %d/2" % (t.locked + 1)
	elif t.extra_lit:
		a = "CONTROL: EXTRA BALL"
	else:
		a = "RAMPS %d/3 TO LOCK" % t.ramps_to_lock
	var b := "MARS %d/4  FUEL %d/4  T-%d" % [t.targets_lit(), t.lanes_lit(), 5 - count_n % 5]
	return PackedStringArray([a, b])


# M11_MODES: story modes started from the control saucer, hurry-up on liftoff, wizard mode
func story_modes() -> Array:
	return [{"name": "COUNTDOWN", "shots": ["liftoff", "gantry", "booster"], "need": 5, "time": 35.0, "value": 75000},
		{"name": "SPACEWALK", "shots": ["lorbit", "rorbit", "silo", "hangar"], "need": 4, "time": 30.0, "value": 100000}]


func saucer_name() -> String:
	return "control"


func hurry_shot() -> String:
	return "liftoff"


func wizard_name() -> String:
	return "ORBITAL WIZARD"


# M11_MOVERS: one bumper slides slowly on a short track
func movers() -> Array:
	return [{"bumper": 2, "off": [-10, 0], "period": 5.0}]
