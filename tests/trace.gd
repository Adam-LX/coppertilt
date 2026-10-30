extends "res://tests/shot_test.gd"
func _ready() -> void:
	t = PinTable.new()
	add_child(t)
	t.set_physics_process(false)
	t.set_process(false)
	t.scripted = true
	t.pace = 0.85
	await get_tree().process_frame
	var args := OS.get_cmdline_user_args()
	var b := _fresh()
	b.pos = Vector2(float(args[0]), float(args[1]))
	b.prev = b.pos
	b.vel = Vector2(float(args[2]), float(args[3]))
	for i in 300:
		t._physics_process(DT)
		if i % 6 == 0 and t.balls.size():
			var x := t.balls[0]
			print("[tr] %d pos=%s vel=%s ramp=%d" % [i, x.pos.round(), x.vel.round(), x.ramp])
	get_tree().quit()
