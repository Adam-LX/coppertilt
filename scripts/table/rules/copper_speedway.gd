extends "res://scripts/table/rules/table_rules.gd"
## Copper Speedway rules: R-A-C-E lanes (bonus X), P-I-T-S targets (kickback), TURBO 1-2-3 drops
## light the paddock lock, N-O-S drops (nitro: bonus X + 2x spinner). Chicane + banking ramps light
## the lock, two locks = SPEEDWAY MULTIBALL (chicane/banking = JACKPOT, then STRAIGHT wire = SUPER
## JACKPOT). The straight wire counts LAPS 1..5 (extra ball after lap 5), the PIT STOP saucer gives
## awards, orbits light the extra ball, stars raise the spinner.

var lap_n := 0       # laps completed (straight shots)
var orbit_n := 0


func shots() -> Array:
	return ["lorbit", "rorbit", "chicane", "banking", "straight", "garage", "pitstop", "paddock"]


func flashers() -> Dictionary:
	return {"top": [[162, 140], Color(1.0, 0.95, 0.8), 120.0], "nest": [[160, 252], Color(1.0, 0.45, 0.2), 130.0],
		"sling0": [[64, 500], Color(1.0, 0.25, 0.15), 90.0], "sling1": [[236, 500], Color(1.0, 1.0, 1.0), 90.0],
		"chicane": [[72, 300], Color(1.0, 0.3, 0.2), 150.0], "banking": [[228, 300], Color(1.0, 0.6, 0.2), 150.0],
		"straight": [[160, 262], Color(1.0, 0.95, 0.85), 150.0], "pitstop": [[150, 304], Color(0.5, 1.0, 0.6), 120.0]}


func reset_game() -> void:
	lap_n = 0
	orbit_n = 0


func on_bumper(bi: int, _b) -> void:
	t.flash["top" if bi < 3 else "nest"] = 1.0
	t._score(100)
	if t.bumper_hits % 50 == 0:
		t._score(50000)
		say("CROWD GOES WILD 50,000", "bonus", "sparkle")


func on_lane(i: int) -> void:
	skill_lane()
	light_lane(i, func() -> void: bump_multiplier("RACE 25,000"))


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
		t.announce.emit("PIT CREW - KICKBACK", "jackpot")
		t.dmd_anim.emit("sparkle", "KICKBACK LIT")


func on_drop(_i: int) -> void:
	t._score(2500)


func on_bank(bank: String) -> void:
	if bank == "turbo":
		t._score(25000)
		t.lock_lit = true
		t.announce.emit("TURBO BOOST - LOCK LIT", "jackpot")
		t.dmd_anim.emit("race", "LOCK IS LIT")
	else:
		t._score(20000)
		bump_multiplier("NITRO 25,000")
		t.spinner_level = mini(t.spinner_level + 1, 5)
		t.announce.emit("NITRO!", "jackpot")
		t.dmd_anim.emit("race", "NITRO")


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
	else:
		t.announce.emit("ORBIT 5,000", "")


func on_hole(b, hn: String) -> void:
	match hn:
		"garage":
			b.sprite.visible = false
			t._score(15000 * t.multiplier)
			say("GARAGE", "bonus", "sparkle")
		"paddock":
			b.sprite.visible = false
			if t.lock_lit and not t.multiball and not t.tilted:
				t.locked += 1
				t._score(25000)
				if t.locked >= 2:
					start_multiball(2, "SPEEDWAY MULTIBALL", "race")
				else:
					# virtual lock: this ball continues, the lock is 'held' in the paddock
					t.announce.emit("CAR 1 ON THE GRID", "bonus")
					t.dmd_anim.emit("big", "BALL LOCKED")
			else:
				t._score(10000)
				say("PADDOCK", "", "sparkle")
		"pitstop":
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
				3: bump_multiplier("RACE 25,000")
				4: t.lock_lit = true
				5: t._score(50000)
			t.announce.emit("PIT STOP: " + awards[i], "bonus")
			t.dmd_anim.emit("big", awards[i])


func on_ramp(_ri: int, name: String) -> void:
	if t.multiball:
		if name == "straight" and t.super_lit:
			t.super_lit = false
			t._score(1000000)
			say("SUPER JACKPOT", "jackpot", "race")
			jackpot_fx()
			return
		if name != "straight":
			t._score(250000)
			t.super_lit = true
			say("JACKPOT", "jackpot", "jackpot")
			jackpot_fx()
			return
	if name == "straight":
		lap_n += 1
		t._score(25000 * t.multiplier)
		if lap_n % 5 == 0:
			t.extra_lit = true
			say("CHEQUERED FLAG - EXTRA BALL LIT", "jackpot", "race", "EXTRA BALL LIT")
		else:
			say("LAP %d" % (lap_n % 5), "bonus", "race")
		return
	t._score(10000 * t.multiplier)
	if not t.lock_lit:
		t.ramps_to_lock += 1
		if t.ramps_to_lock >= 3:
			t.lock_lit = true
			t.ramps_to_lock = 0
			say("LOCK IS LIT", "bonus", "race")
			return
	say("CHICANE" if name == "chicane" else "BANKING", "bonus", "race")


func lamp_states() -> Dictionary:
	var on: Dictionary = {}
	for i in t.ride.size():
		on["pits_" + "PITS"[i]] = 1 if t.ride[i] else (3 if t.target_flash[i] > 0.0 else 0)
	for shot in shots():
		var n := chase_len(shot)
		var prog: int = t.shot_n[shot] % (n + 1)
		if shot == "chicane" or shot == "banking":
			prog = t.ramps_to_lock if not t.lock_lit else n
		var arrow := 1
		if t.multiball and (shot == "chicane" or shot == "banking"):
			arrow = 3
		elif t.multiball and shot == "straight" and t.super_lit:
			arrow = 3
		elif t.lock_lit and shot == "paddock":
			arrow = 3
		elif t.extra_lit and shot == "pitstop":
			arrow = 2
		elif shot == "lorbit" and t.spin_v > 0.0:
			arrow = 3
		shot_lamps(on, shot, arrow, prog)
	on["jackpot"] = 3 if t.multiball else 0
	on["lock"] = 2 if t.lock_lit else (1 if t.locked > 0 else 0)
	on["extra_l"] = 1 if t.kickback_lit else 0
	on["extra_r"] = 2 if t.save_lit else 0
	# LAPS ladder: lap0 (bottom) .. lap4 (green, chequered flag); chases in multiball
	var lit := lap_n % 5
	for i in 5:
		var st := 1 if i < lit else (2 if i == lit else 0)
		if t.multiball or t._chase.has("straight"):
			st = 1 if (int(t._time * 12.0) - i) % 5 == 0 else 0
		on["lap%d" % i] = st
	finish_lamps(on)
	on["super"] = 2 if t.super_lit else 0
	on["lock1"] = 1 if t.locked >= 1 else (2 if t.lock_lit else 0)
	on["lock2"] = 2 if t.lock_lit and t.locked >= 1 else 0
	return on


func mission_lines() -> PackedStringArray:
	var a := ""
	if t.multiball:
		a = "STRAIGHT = SUPER JACKPOT" if t.super_lit else "RAMPS = JACKPOT"
	elif t.lock_lit:
		a = "PADDOCK: LOCK %d/2" % (t.locked + 1)
	elif t.extra_lit:
		a = "PIT STOP: EXTRA BALL"
	else:
		a = "RAMPS %d/3 TO LOCK" % t.ramps_to_lock
	var b := "PITS %d/4  RACE %d/4  LAP %d/5" % [t.targets_lit(), t.lanes_lit(), lap_n % 5]
	return PackedStringArray([a, b])


# M11_MODES: story modes started from the pitstop saucer, hurry-up on straight, wizard mode
func story_modes() -> Array:
	return [{"name": "PIT STOP CHALLENGE", "shots": ["pitstop", "garage", "paddock", "chicane"], "need": 4, "time": 30.0, "value": 100000},
		{"name": "FINAL LAP", "shots": ["lorbit", "rorbit", "straight", "banking"], "need": 5, "time": 35.0, "value": 75000}]


func saucer_name() -> String:
	return "pitstop"


func hurry_shot() -> String:
	return "straight"


func wizard_name() -> String:
	return "CHAMPIONSHIP"


# M11_MOVERS: one bumper slides slowly on a short track
func movers() -> Array:
	return [{"bumper": 2, "off": [0, 10], "period": 5.5}]
