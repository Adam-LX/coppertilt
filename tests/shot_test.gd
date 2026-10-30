extends Node
## Deterministic shot tests (headless):
##   godot --headless --path . res://tests/shot_test.tscn [-- --map]
## Part A: scripted ball placement/velocity at every sensor -> must register.
## Part B (--map): flipper shot map - ball rolls down each flipper, flip after a delay,
## record what the shot reached. Tells autopilot aim from unreachable geometry.

const DT := 1.0 / 200.0
var t: PinTable
var fails := 0


func _ready() -> void:
	t = PinTable.new()
	add_child(t)
	t.set_physics_process(false)
	t.set_process(false)
	t.scripted = true
	t.pace = 0.85
	await get_tree().process_frame
	_part_a()
	if OS.get_cmdline_user_args().has("--map"):
		_part_b()
	if OS.get_cmdline_user_args().has("--aim"):
		_part_c()
	if OS.get_cmdline_user_args().has("--launch"):
		_part_l()
	print("[test] DONE fails=%d" % fails)
	get_tree().quit(1 if fails > 0 else 0)


func _fresh() -> PinTable.Ball:
	t.reset_game()
	t.kickback_lit = false
	t.script_flip = [false, false]
	for i in 30:
		t._physics_process(DT)
	return t.balls[0]


func _snap() -> Dictionary:
	return {"lanes": t.lanes.duplicate(), "ride": t.ride.duplicate(), "stars": t.stars.duplicate(),
		"drops": t.drops.duplicate(), "shots": t.shot_n.duplicate(), "bumpers": t.bumper_hits,
		"orbit": t.rules.orbit_n, "spin": t.spin_v, "toys": t.toy_n.duplicate()}


func _diff(a: Dictionary, b: Dictionary) -> Array:
	var out := []
	for i in b.lanes.size():
		if b.lanes[i] and not a.lanes[i]: out.append("lane%s" % t.g.lanes[i].letter)
	for i in b.ride.size():
		if b.ride[i] and not a.ride[i]: out.append("ride%s" % t.g.targets[i].letter)
	for i in 3:
		if b.stars[i] and not a.stars[i]: out.append("star%d" % i)
	for i in b.drops.size():
		if b.drops[i] and not a.drops[i]: out.append("drop%d" % i)
	for k in b.shots:
		if b.shots[k] > a.shots[k]: out.append(k)
	if b.bumpers > a.bumpers: out.append("bump%d" % (b.bumpers - a.bumpers))
	for k in b.toys:
		if b.toys[k] > a.toys.get(k, 0): out.append(k)
	return out


func _run(b: PinTable.Ball, secs: float, stop_low := true) -> Array:
	var a := _snap()
	var seen := {}
	for i in int(secs / DT):
		t._physics_process(DT)
		for k in _diff(a, _snap()):
			seen[k] = true
		if t.balls.is_empty() or (stop_low and t.balls[0].pos.y > PinTable.H - 94.0 and i > 40):
			break
	return seen.keys()


func _expect(name: String, pos: Vector2, vel: Vector2, want: String, secs := 2.5) -> void:
	var b := _fresh()
	b.pos = pos
	b.prev = pos
	b.vel = vel
	var got := _run(b, secs)
	var ok := got.has(want)
	if not ok:
		fails += 1
	print("[test] %s %-14s want=%-8s got=%s" % ["PASS" if ok else "FAIL", name, want, str(got)])


func _try(pos: Vector2, vel: Vector2, want: String) -> bool:
	var b := _fresh()
	b.pos = pos
	b.prev = pos
	b.vel = vel
	return _run(b, 2.5).has(want)


func _part_a() -> void:
	var g := t.g
	for i in 4:
		var L: Dictionary = g.lanes[i]
		_expect("lane " + L.letter, Vector2(L.pos[0], 104), Vector2(0, -300), "lane" + L.letter)
	for i in 3:
		var sp := Vector2(g.stars[i][0], g.stars[i][1])
		if not _try(sp + Vector2(0, 22), Vector2(0, -330), "star%d" % i):
			# a toy right below the rollover (Launch Pad rocket): roll it from above instead
			_expect("star %d" % i, sp + Vector2(0, -22), Vector2(0, 330), "star%d" % i)
		else:
			print("[test] PASS star %d" % i)
	for i in 4:
		var tg: Dictionary = g.targets[i]
		var y := (float(tg.seg[1]) + float(tg.seg[3])) * 0.5
		_expect("ride " + tg.letter, Vector2(78, y), Vector2(-400, -40), "ride" + tg.letter)
	for i in g.drops.size():
		var d: Dictionary = g.drops[i]
		var c := Vector2((d.seg[0] + d.seg[2]) * 0.5, (d.seg[1] + d.seg[3]) * 0.5)
		var n := Vector2(d.seg[3] - d.seg[1], -(d.seg[2] - d.seg[0])).normalized()
		var toward := Vector2(150, PinTable.H * 0.586) if c.y > PinTable.H * 0.586 else Vector2(200, c.y)
		if n.dot(toward - c) < 0.0:
			n = -n
		_expect("drop %d" % i, c + n * 26.0, -n * 380.0, "drop%d" % i)
	_expect("orbit L", Vector2(26, PinTable.H * 0.5), Vector2(0, -700), "lorbit")
	_expect("orbit R", Vector2(277, PinTable.H * 0.52), Vector2(0, -700), "rorbit")
	for h in g.holes:
		var hp := Vector2(h.pos[0], h.pos[1])
		_expect("hole " + h.name, hp + Vector2(0, 30), Vector2(0, -175), h.name)
	for h in g.holes:
		if h.has("vuk"):
			var vp := Vector2(h.pos[0], h.pos[1])
			_expect("vuk " + h.name, vp + Vector2(0, 30), Vector2(0, -175), h.vuk, 5.0)
	for m in t.magnets:
		_expect("magnet " + m.name, m.pos + Vector2(0, 26), Vector2(0, -220), m.name)
	for d in t.discs:
		_expect("disc " + d.name, d.pos + Vector2(0, float(d.r) + 14.0), Vector2(0, -320), d.name)
	for sp in t.spinners:
		_expect("spinner " + sp.name, sp.pos + Vector2(0, 30), Vector2(0, -600), sp.name)
	for rp in t.ramps:
		if rp.vuk:
			continue
		var m: Vector2 = (rp.mouth_a + rp.mouth_b) * 0.5
		var nin: Vector2 = rp["in"]
		_expect("ramp " + rp.name, m - nin * 30.0, nin * 700.0, rp.name, 7.0)


func _part_b() -> void:
	var tally := {}
	for fi in 3:
		var fl: PinTable.Flipper = t.flippers[fi]
		var ftally := {}
		var n := 0
		for start in [0.15, 0.35]:
			for d10 in range(0, 60, 2):
				var b := _fresh()
				var ang := fl.angle()
				var dir := Vector2(cos(ang), sin(ang))
				var nrm := Vector2(-dir.y, dir.x)
				if nrm.y > 0.0:
					nrm = -nrm
				var p: Vector2 = fl.pivot + dir * fl.length * start + nrm * (fl.r0 + 7.5 + 0.5)
				b.pos = p
				b.prev = p
				b.vel = dir * 40.0
				var side := 0 if fl.left else 1
				# small flipper is on the left button
				var a := _snap()
				var seen := {}
				for i in int(d10 * 0.01 / DT):
					t._physics_process(DT)
				t.script_flip[side] = true
				for i in int(3.5 / DT):
					if i == 40:
						t.script_flip = [false, false]
					t._physics_process(DT)
					for k in _diff(a, _snap()):
						seen[k] = true
					if t.balls.is_empty() or t.balls[0].held > 0.0 or (i > 60 and t.balls[0].pos.y > PinTable.H - 124.0):
						break
				n += 1
				for k in seen:
					if k.begins_with("bump"):
						k = "bumpers"
					ftally[k] = ftally.get(k, 0) + 1
		var keys := ftally.keys()
		keys.sort()
		var line := ""
		for k in keys:
			line += "%s:%d " % [k, ftally[k]]
		print("[map] flipper %d (%s%s) n=%d  %s" % [fi, "L" if fl.left else "R", " small" if fl.small else "", n, line])


func _part_l() -> void:
	# fine launch sweep (skill-shot band) and the charge->speed mapping actually used
	for v in range(640, 800, 5):
		var b := _fresh()
		b.vel = Vector2(0, -v)
		print("[launch] %4d -> %s" % [v, str(_run(b, 5.0))])
	if t.has_method("launch_speed"):
		var hits := 0
		var n := 0
		for i in 41:
			var c := i / 40.0
			if c < 0.3 or c > 0.6:
				continue
			for k in 3:
				var b := _fresh()
				b.vel = Vector2(0, -t.launch_speed(c))
				var got := _run(b, 5.0)
				n += 1
				var lane := false
				for g in got:
					if String(g).begins_with("lane"):
						lane = true
				hits += 1 if lane else 0
		print("[launch] skill zone 0.30-0.60 -> lane %d/%d" % [hits, n])


func _part_c() -> void:
	# launch sweep: plunger speed -> what the first 5 s reach
	for v in range(600, 1000, 20):
		var b := _fresh()
		b.vel = Vector2(0, -v)
		var got := _run(b, 5.0)
		print("[aim] launch %4d -> %s  end=%s" % [v, str(got), str(t.balls[0].pos.round()) if t.balls.size() else "-"])
	# angle sweep from above each flipper: angle from vertical (deg, + = right)
	var srcs := []
	for fl in t.flippers:
		var tag := "U" if fl.small else ("L" if fl.left else "R")
		srcs.append([tag, fl.pivot + (Vector2(26, -14) if fl.small else Vector2(22 if fl.left else -22, -29))])
	for src in srcs:
		for spd in [800.0, 1050.0]:
			var line := ""
			for a in range(-50, 52, 4):
				var b := _fresh()
				b.pos = src[1]
				b.prev = b.pos
				b.vel = Vector2(sin(deg_to_rad(a)), -cos(deg_to_rad(a))) * spd
				var got := _run(b, 6.0)
				var first := ""
				for k in got:
					if not k.begins_with("bump"):
						first = k
						break
				if first == "" and got.size() > 0:
					first = "B"
				line += "%d:%s " % [a, first if first != "" else "-"]
			print("[aim] %s v%d %s" % [src[0], spd, line])
