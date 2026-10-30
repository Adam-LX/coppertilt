extends Node
## SIDE-DRAIN test (headless): balls released along both side walls (several heights, offsets,
## angles and speeds, flippers at rest, kickback OFF) and followed until they are resolved:
##   SAVE  - lands on a lower flipper (within the player's reach: flip or cradle)
##   OUT   - drains through an outlane (outside the flipper span) without touching a flipper
##   SDM   - drains down the middle without touching a flipper
##   BACK  - bounces back up into the upper playfield (still in play)
##   godot --headless --audio-driver Dummy --path . res://tests/lane_test.tscn -- --table=<id> [--verbose]

const DT := 1.0 / 800.0


func _ready() -> void:
	Settings.persist = false
	Settings.demo = false
	var verbose := false
	var kick := false
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--table="):
			Settings.table_id = a.get_slice("=", 1)
		if a == "--kick":
			kick = true
		if a == "--verbose":
			verbose = true
	seed(7)
	var t := PinTable.new()
	add_child(t)
	await get_tree().process_frame
	t.set_physics_process(false)
	t.set_process(false)
	t.clear_balls()
	var br := float(t.g.ball_r)
	var wall_l := 10.0
	var wall_r := float(t.g.plunger.lane[0])
	var fl_l: Variant = t.flippers[0]
	var fl_r: Variant = t.flippers[1]
	var res := {"L": {"save": 0, "out": 0, "sdm": 0, "back": 0, "other": 0}, "R": {"save": 0, "out": 0, "sdm": 0, "back": 0, "other": 0}}
	var outs := {}
	for side in ["L", "R"]:
		for y0 in [250.0, 280.0, 310.0, 340.0, 370.0, 390.0]:
			for off in [0.5, 5.0, 10.0]:
				var x0: float = wall_l + br + off if side == "L" else wall_r - br - off
				var p := Vector2(x0, y0)
				var skip := false
				for sg in t.g.segments:
					if Geometry2D.get_closest_point_to_segment(p, Vector2(sg[0], sg[1]), Vector2(sg[2], sg[3])).distance_to(p) < br + 0.5:
						skip = true
				for c in t.g.circles:
					if p.distance_to(Vector2(c[0], c[1])) < float(c[2]) + br + 0.5:
						skip = true
				for fl in t.flippers:
					if p.distance_to(fl.pivot) < fl.length + 10.0:
						skip = true
				if skip:
					continue
				for ang in [60.0, 75.0, 90.0, 105.0, 120.0]:
					for sp in [0.0, 120.0, 260.0, 420.0]:
						var a: float = ang if side == "L" else 180.0 - ang
						var b := t._spawn_ball(p)
						b.vel = Vector2.from_angle(deg_to_rad(a)) * sp
						t.kickback_lit = kick
						var outcome := "other"
						var tt := 0.0
						while tt < 10.0:
							t._step_ball(b, DT)
							tt += DT
							if b.ramp >= 0 or b.held > 0.0:
								outcome = "back"
								break
							if _on_flipper(b, fl_l, br) or _on_flipper(b, fl_r, br):
								outcome = "save"
								break
							if b.pos.y < y0 - 90.0:
								outcome = "back"
								break
							if b.pos.y > float(t.g.drain_y) or b.pos.y > 600.0 and (b.pos.x < fl_l.pivot.x - 24.0 or b.pos.x > fl_r.pivot.x + 24.0):
								outcome = "out" if (b.pos.x < fl_l.pivot.x - 4.0 or b.pos.x > fl_r.pivot.x + 4.0) else "sdm"
								break
						res[side][outcome] += 1
						if outcome == "out":
							var k: String = "%s y%d off%d" % [side, int(y0), int(off)]
							outs[k] = outs.get(k, 0) + 1
						if verbose:
							print("[lane] %s (%.0f,%.0f) a=%d v=%d -> %s" % [side, p.x, p.y, int(a), int(sp), outcome])
						t._free_ball(b)
						t.balls.erase(b)
	var tot := {"save": 0, "out": 0, "sdm": 0, "back": 0, "other": 0}
	for s in res:
		var n := 0
		for k in res[s]:
			n += res[s][k]
			tot[k] += res[s][k]
		print("[lane] table=%s side=%s n=%d save=%d (%.0f%%) out=%d (%.0f%%) sdm=%d back=%d other=%d" % [
			Settings.table_id, s, n, res[s].save, 100.0 * res[s].save / maxf(1, n), res[s].out,
			100.0 * res[s].out / maxf(1, n), res[s].sdm, res[s].back, res[s].other])
	var nt := 0
	for k in tot:
		nt += tot[k]
	for k in outs:
		print("[lane]   out from %s: %d" % [k, outs[k]])
	print("[lane] DONE table=%s n=%d save=%.0f%% out=%.0f%% sdm=%.0f%% back=%.0f%% other=%.0f%%" % [
		Settings.table_id, nt, 100.0 * tot.save / nt, 100.0 * tot.out / nt, 100.0 * tot.sdm / nt,
		100.0 * tot.back / nt, 100.0 * tot.other / nt])
	get_tree().quit()


## ball resting on / landing on the top face of a lower flipper (at rest)
func _on_flipper(b, fl, r: float) -> bool:
	var rel: Vector2 = b.pos - fl.pivot
	if rel.length_squared() > 70.0 * 70.0:
		return false
	var ang: float = fl.angle()
	var dir := Vector2(cos(ang), sin(ang))
	var tt := clampf(rel.dot(dir) / fl.length, 0.0, 1.0)
	var c: Vector2 = fl.pivot + dir * fl.length * tt
	var rad := lerpf(fl.r0, fl.r1, tt)
	return b.pos.distance_to(c) < r + rad + 1.0 and b.pos.y < c.y
