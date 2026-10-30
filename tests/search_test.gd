extends Node
## BALL SEARCH finder (headless): fires balls from a grid of points in a region with a fan of
## velocities (flippers at rest) and reports every place where the game's own BALL SEARCH rule
## (speed < 8 for 3 s, off ramps, not in a cradle / lane / hole) would fire.
##   godot --headless --audio-driver Dummy --path . res://tests/search_test.tscn -- --table=<id> [--region=x0,y0,x1,y1]

const DT := 1.0 / 800.0
const STEP := 8.0


func _ready() -> void:
	Settings.persist = false
	Settings.demo = false
	var region := Rect2(150, 280, 130, 120)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--table="):
			Settings.table_id = a.get_slice("=", 1)
		if a.begins_with("--region="):
			var v := a.get_slice("=", 1).split_floats(",")
			region = Rect2(v[0], v[1], v[2] - v[0], v[3] - v[1])
	seed(11)
	var t := PinTable.new()
	add_child(t)
	await get_tree().process_frame
	t.set_physics_process(false)
	t.set_process(false)
	t.clear_balls()
	var blocks: Array[PackedVector2Array] = []
	for blk in t.g.get("blocks", []):
		var pv := PackedVector2Array()
		for p in blk:
			pv.append(Vector2(p[0], p[1]))
		blocks.append(pv)
	var br := float(t.g.ball_r) + 0.5
	var found := {}
	var n := 0
	var y := region.position.y
	while y <= region.end.y:
		var x := region.position.x
		while x <= region.end.x:
			var p := Vector2(x, y)
			x += STEP
			var skip := false
			for pv in blocks:
				if Geometry2D.is_point_in_polygon(p, pv):
					skip = true
			for sg in t.g.segments:
				if Geometry2D.get_closest_point_to_segment(p, Vector2(sg[0], sg[1]), Vector2(sg[2], sg[3])).distance_to(p) < br:
					skip = true
			for c in t.g.circles:
				if p.distance_to(Vector2(c[0], c[1])) < float(c[2]) + br:
					skip = true
			if skip:
				continue
			for ang in [-150.0, -120.0, -90.0, -60.0, -30.0, 0.0, 180.0]:
				for sp in [60.0, 180.0, 340.0]:
					n += 1
					var b := t._spawn_ball(p)
					b.vel = Vector2.from_angle(deg_to_rad(ang)) * sp
					var still := 0.0
					var tt := 0.0
					while tt < 9.0:
						t._step_ball(b, DT)
						tt += DT
						if b.pos.y > float(t.g.drain_y) or b.pos.x < 0.0 or b.pos.x > PinTable.W:
							break
						if b.vel.length() < 8.0 and not t.in_lane(b) and not t.at_flipper(b) and b.held <= 0.0 and b.ramp < 0:
							still += DT
						else:
							still = 0.0
						if still > 3.0:
							var k := Vector2i(int(round(b.pos.x / 4.0)), int(round(b.pos.y / 4.0)))
							if not found.has(k):
								found[k] = [b.pos, p, ang, sp, 0]
							found[k][4] += 1
							break
					t._free_ball(b)
					t.balls.erase(b)
			pass
		y += STEP
	print("[search] table=%s shots=%d spots=%d" % [Settings.table_id, n, found.size()])
	for k in found:
		var s: Array = found[k]
		print("[search] rest=(%.1f,%.1f) n=%d first_from=(%.0f,%.0f) ang=%d v=%d" % [s[0].x, s[0].y, s[4], s[1].x, s[1].y, s[2], s[3]])
	print("[search] DONE spots=%d" % found.size())
	get_tree().quit()
