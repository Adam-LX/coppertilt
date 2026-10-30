extends Node
## Stuck-ball finder (headless): drops a ball from a grid of points over the playfield with the
## flippers at rest and reports every place where it comes to rest outside the flipper cradles,
## the shooter lane and the holes (= a spot that would need BALL SEARCH in real play).
##   godot --headless --audio-driver Dummy --path . res://tests/stuck_test.tscn -- --table=<id>
## Points inside closed ramp-base blocks / outside the cabinet are skipped (unreachable).

const DT := 1.0 / 800.0
const STEP := 9.0


func _ready() -> void:
	Settings.persist = false
	Settings.demo = false
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--table="):
			Settings.table_id = a.get_slice("=", 1)
	seed(7)
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
	var stuck := {}
	var n := 0
	var y := 40.0
	while y < 520.0:
		var x := 16.0
		while x < 292.0:
			var p := Vector2(x, y)
			x += STEP
			var skip := false
			for pv in blocks:
				if Geometry2D.is_point_in_polygon(p, pv):
					skip = true
			var br := float(t.g.ball_r) + 0.5
			for sg in t.g.segments:
				var q := Geometry2D.get_closest_point_to_segment(p, Vector2(sg[0], sg[1]), Vector2(sg[2], sg[3]))
				if q.distance_to(p) < br:
					skip = true
			for c in t.g.circles:
				if p.distance_to(Vector2(c[0], c[1])) < float(c[2]) + br:
					skip = true
			if skip:
				continue
			n += 1
			var b := t._spawn_ball(p)
			b.vel = Vector2(randf_range(-40.0, 40.0), randf_range(-20.0, 40.0))
			var still := 0.0
			var tt := 0.0
			var res := ""
			while tt < 7.0:
				t._step_ball(b, DT)
				tt += DT
				if b.pos.y > float(t.g.drain_y) or b.pos.x < 0.0 or b.pos.x > PinTable.W:
					break
				if b.ramp >= 0 or b.held > 0.0 or b.hole != "":
					still = 0.0
					continue
				if b.vel.length() < 12.0 and not t.at_flipper(b) and not t.in_lane(b):
					still += DT
				else:
					still = 0.0
				if still > 1.5:
					res = "stuck"
					break
			if res == "stuck":
				var k := Vector2i(int(round(b.pos.x / 6.0)), int(round(b.pos.y / 6.0)))
				if not stuck.has(k):
					stuck[k] = [b.pos, p, 0]
				stuck[k][2] += 1
			t._free_ball(b)
			t.balls.erase(b)
		y += STEP
	print("[stuck] table=%s starts=%d spots=%d" % [Settings.table_id, n, stuck.size()])
	for k in stuck:
		var s: Array = stuck[k]
		print("[stuck] rest=(%.1f,%.1f) n=%d first_from=(%.0f,%.0f)" % [s[0].x, s[0].y, s[2], s[1].x, s[1].y])
	print("[stuck] DONE spots=%d" % stuck.size())
	get_tree().quit(0)
