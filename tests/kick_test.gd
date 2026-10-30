extends "res://tests/shot_test.gd"
# kickback outcome sweep: args ay by vy  (deflector (10,ay)-(30,by), kick speed vy)
func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var ay := float(args[0]); var by := float(args[1]); var vy := float(args[2])
	var res := []
	for pace in [0.6, 0.75, 0.85, 1.0, 1.15, 1.3]:
		for dv in [-30.0, 0.0, 30.0]:
			t = PinTable.new()
			add_child(t)
			t.set_physics_process(false)
			t.set_process(false)
			t.scripted = true
			t.pace = pace
			await get_tree().process_frame
			for i in t.seg_a.size():
				if t.seg_one[i] != Vector2.ZERO and absf(t.seg_a[i].x - 10.0) < 0.1:
					t.seg_a[i] = Vector2(10, ay); t.seg_b[i] = Vector2(30, by)
					var d := (t.seg_b[i] - t.seg_a[i]).normalized()
					t.seg_one[i] = Vector2(-d.y, d.x)
			t.g.kickback.vy = vy
			var b := _fresh()
			t.kickback_lit = true
			b.pos = Vector2(19, PinTable.H - 84.0); b.prev = b.pos; b.vel = Vector2(0, 150 + dv)
			var out := "alive"
			for i in 1000:
				t._physics_process(DT)
				if t.balls.size() == 0:
					out = "DRAIN"; break
				var p: Vector2 = t.balls[0].pos
				if p.y > PinTable.H - 99.0 and p.x > 45 and p.x < 255:
					out = "C%d" % int(p.x) if p.x > 126.0 and p.x < 174.0 else "flip%d" % int(p.x)
					break
			res.append(out)
			t.queue_free()
			await get_tree().process_frame
	var good := 0
	for r in res:
		if r.begins_with("flip") or r == "alive":
			good += 1
	print("[kick] %s %s %s -> %d/%d good  %s" % [ay, by, vy, good, res.size(), res])
	get_tree().quit()
