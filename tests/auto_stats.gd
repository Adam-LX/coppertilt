extends "res://tests/shot_test.gd"
## Autopilot statistics: 600 s of table time, drains by exit x, features reached.
func _ready() -> void:
	t = PinTable.new()
	add_child(t)
	t.set_physics_process(false)
	t.set_process(false)
	t.autopilot = true
	t.pace = 0.85
	await get_tree().process_frame
	var drains := {}
	var lastx := 0.0
	var tally := {}
	var a := _snap()
	var n_ball := 0
	var ball_t := 0.0
	var times := []
	var hist := []
	var shown := 0
	for i in int(600.0 / DT):
		t._physics_process(DT)
		ball_t += DT
		if t.balls.size():
			lastx = t.balls[0].pos.x
			if i % 20 == 0:
				hist.append(t.balls[0].pos.round())
				if hist.size() > 12:
					hist.pop_front()
		else:
			var k := "out_L" if lastx < 60 else ("out_R" if lastx > 240 else "center")
			drains[k] = drains.get(k, 0) + 1
			if k == "out_L" and shown < 6:
				shown += 1
				print("[auto] L-drain path: ", hist)
			hist.clear()
			times.append(int(ball_t))
			ball_t = 0.0
			for kk in _diff(a, _snap()):
				tally[kk] = tally.get(kk, 0) + 1
			t.reset_game()
			a = _snap()
			n_ball += 1
	print("[auto] balls=%d drains=%s life=%s" % [n_ball, str(drains), str(times)])
	var keys := tally.keys()
	keys.sort()
	var line := ""
	for k in keys:
		line += "%s:%d " % [k, tally[k]]
	print("[auto] balls reaching: ", line)
	get_tree().quit()
