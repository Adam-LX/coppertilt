extends "res://scripts/table/rules/table_rules.gd"
## Midnight Funfair rules: F-A-I-R lanes (bonus X), R-I-D-E targets (kickback), DUCK / SHY drop
## banks (lock / bonus X), coaster + ghost train ramps light the Haunted House lock, two locks =
## MULTIBALL (ramps = JACKPOT, then HELTER SKELTER = SUPER JACKPOT), Fortune saucer, orbits light
## the extra ball, stars raise the spinner.

var helter_n := 0
var orbit_n := 0
var video_mode_lit := false


func shots() -> Array:
	return ["lorbit", "rorbit", "coaster", "ghost", "helter", "tunnel", "saucer", "haunted"]


func flashers() -> Dictionary:
	return {"top": [[162, 140], Color(1.0, 0.75, 0.3), 120.0], "nest": [[160, 252], Color(1.0, 0.4, 0.8), 130.0],
		"sling0": [[64, 500], Color(1.0, 0.3, 0.7), 90.0], "sling1": [[236, 500], Color(0.3, 0.7, 1.0), 90.0],
		"coaster": [[72, 300], Color(1.0, 0.25, 0.2), 150.0], "ghost": [[228, 300], Color(0.3, 1.0, 0.45), 150.0],
		"helter": [[160, 250], Color(1.0, 0.8, 0.3), 140.0], "saucer": [[150, 304], Color(0.9, 0.9, 1.0), 120.0]}


func reset_game() -> void:
	helter_n = 0
	orbit_n = 0
	video_mode_lit = false


func on_bumper(bi: int, _b) -> void:
	t.flash["top" if bi < 3 else "nest"] = 1.0
	t._score(100)
	if t.bumper_hits % 50 == 0:
		t._score(50000)
		say("SUPER BUMPERS", "bonus", "sparkle")


func on_lane(i: int) -> void:
	skill_lane()
	light_lane(i, func() -> void: bump_multiplier("F-A-I-R 25,000"))


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
		t.announce.emit("RIDE COMPLETE", "jackpot")
		t.dmd_anim.emit("sparkle", "KICKBACK LIT")


func on_drop(_i: int) -> void:
	t._score(2500)


func on_bank(bank: String) -> void:
	if bank == "duck":
		t._score(25000)
		t.lock_lit = true
		video_mode_lit = true
		Sound.play_voice("duck_hunt")
		t.announce.emit("DUCK SHOOT LIT - SHOOT SAUCER", "jackpot")
		t.dmd_anim.emit("circus", "DUCK SHOOT LIT")
	else:
		t._score(20000)
		bump_multiplier("F-A-I-R 25,000")
		t.announce.emit("COCONUT SHY", "jackpot")


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
		"tunnel":
			b.sprite.visible = false
			t._score(15000 * t.multiplier)
			say("TUNNEL OF LOVE", "bonus", "sparkle")
		"haunted":
			b.sprite.visible = false
			if t.lock_lit and not t.multiball and not t.tilted:
				t.locked += 1
				t._score(25000)
				if t.locked >= 2:
					start_multiball(2, "MULTIBALL", "wheel")
				else:
					# virtual lock: this ball continues, the lock is 'held' in the house
					t.announce.emit("BALL 1 LOCKED", "bonus")
					t.dmd_anim.emit("big", "BALL LOCKED")
			else:
				t._score(10000)
				say("HAUNTED HOUSE", "", "sparkle")
		"ghost":
			b.sprite.visible = false
			t._score(10000)
			Sound.play_voice("ghost_train")
			say("GHOST TRAIN", "bonus", "ghost")
		"saucer":
			if video_mode_lit and not t.tilted:
				video_mode_lit = false
				b.held = 22.0
				t.video_mode_start.emit("duck_hunt")
				return
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
				3: bump_multiplier("F-A-I-R 25,000")
				4: t.lock_lit = true
				5: t._score(50000)
			Sound.play_voice("fortune")
			t.announce.emit("FORTUNE: " + awards[i], "bonus")
			t.dmd_anim.emit("wheel", awards[i])


func on_ramp(_ri: int, name: String) -> void:
	if t.multiball:
		if name == "helter" and t.super_lit:
			t.super_lit = false
			t._score(1000000)
			say("SUPER JACKPOT", "jackpot", "jackpot")
			jackpot_fx()
			return
		if name != "helter":
			t._score(250000)
			t.super_lit = true
			say("JACKPOT", "jackpot", "jackpot")
			jackpot_fx()
			return
	if name == "helter":
		helter_n += 1
		t._score(25000 * t.multiplier)
		Sound.play_voice("helter_skelter")
		if helter_n % 3 == 0:
			t.extra_lit = true
			say("HELTER SKELTER - EXTRA BALL LIT", "jackpot", "sparkle", "EXTRA BALL LIT")
		else:
			say("HELTER SKELTER", "bonus", "coaster")
		return
	t._score(10000 * t.multiplier)
	if not t.lock_lit:
		t.ramps_to_lock += 1
		if t.ramps_to_lock >= 3:
			t.lock_lit = true
			t.ramps_to_lock = 0
			say("LOCK IS LIT", "bonus", "coaster")
			return
	var title := "ROLLER COASTER" if name == "coaster" else "GHOST TRAIN"
	say(title, "bonus", "coaster")


func lamp_states() -> Dictionary:
	var on: Dictionary = {}
	for i in t.ride.size():
		on["ride_" + "RIDE"[i]] = 1 if t.ride[i] else (3 if t.target_flash[i] > 0.0 else 0)
	for shot in shots():
		var n := chase_len(shot)
		var prog: int = t.shot_n[shot] % (n + 1)
		if shot == "coaster" or shot == "ghost":
			prog = t.ramps_to_lock if not t.lock_lit else n
		var arrow := 1
		if t.multiball and (shot == "coaster" or shot == "ghost"):
			arrow = 3
		elif t.multiball and shot == "helter" and t.super_lit:
			arrow = 3
		elif t.lock_lit and shot == "haunted":
			arrow = 3
		elif t.extra_lit and shot == "saucer":
			arrow = 2
		elif shot == "lorbit" and t.spin_v > 0.0:
			arrow = 3
		shot_lamps(on, shot, arrow, prog)
	on["jackpot"] = 3 if t.multiball else 0
	on["lock"] = 2 if t.lock_lit else (1 if t.locked > 0 else 0)
	on["extra_l"] = 1 if t.kickback_lit else 0
	on["extra_r"] = 2 if t.save_lit else 0
	var nt := 0
	while t.light_pos.has("tower%d" % nt):
		nt += 1
	var tl := (helter_n % 3) * (nt / 3)
	for i in nt:
		var st := 1 if i < tl else 0
		if t._chase.has("helter") or t.multiball:
			st = 1 if (int(t._time * 14.0) - i) % 4 == 0 else 0
		on["tower%d" % i] = st
	finish_lamps(on)
	on["super"] = 2 if t.super_lit else 0
	on["lock1"] = 1 if t.locked >= 1 else (2 if t.lock_lit else 0)
	on["lock2"] = 2 if t.lock_lit and t.locked >= 1 else 0
	return on


func mission_lines() -> PackedStringArray:
	var a := ""
	if t.multiball:
		a = "HELTER = SUPER JACKPOT" if t.super_lit else "RAMPS = JACKPOT"
	elif t.lock_lit:
		a = "HAUNTED HOUSE: LOCK %d/2" % (t.locked + 1)
	elif t.extra_lit:
		a = "FORTUNE: EXTRA BALL"
	else:
		a = "RAMPS %d/3 TO LOCK" % t.ramps_to_lock
	var b := "RIDE %d/4  FAIR %d/4" % [t.targets_lit(), t.lanes_lit()]
	return PackedStringArray([a, b])


# M11_MODES: story modes started from the saucer saucer, hurry-up on helter, wizard mode
func story_modes() -> Array:
	return [{"name": "GHOST TRAIN FRENZY", "shots": ["ghost", "haunted", "tunnel"], "need": 5, "time": 35.0, "value": 75000},
		{"name": "COASTER COMBO", "shots": ["coaster", "helter", "lorbit", "rorbit"], "need": 4, "time": 30.0, "value": 100000}]


func saucer_name() -> String:
	return "saucer"


func hurry_shot() -> String:
	return "helter"


func wizard_name() -> String:
	return "CARNIVAL OF LIGHTS"


# M11_MOVERS: one bumper slides slowly on a short track
func movers() -> Array:
	return [{"bumper": 2, "off": [0, -8], "period": 6.0}]
