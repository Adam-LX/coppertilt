extends Node
## M11 modes test (headless, deterministic):
##   godot --headless --path . res://tests/modes_test.tscn -- --table=<id>
## Saucer starts a story mode (through the real hole code), mode shots complete it, the timer
## ends it, relight after 3 shots, combos, hurry-up, extra ball lit, wizard mode and ball saves.

const DT := 1.0 / 200.0
var g: PinGame
var r
var fails := 0


func _ready() -> void:
	Settings.persist = false
	Settings.demo = false
	g = load("res://scenes/game.tscn").instantiate()
	add_child(g)
	await get_tree().process_frame
	g.set_process(false)
	g.table.set_physics_process(false)
	r = g.table.rules
	_run()
	print("[test] DONE fails=%d" % fails)
	get_tree().quit(1 if fails > 0 else 0)


func _check(ok: bool, what: String) -> void:
	print("[test] %s %s" % ["ok  " if ok else "FAIL", what])
	if not ok:
		fails += 1


func _step(n: int) -> void:
	for i in n:
		g.table._physics_process(DT)
		g._process(DT)


func _relight() -> void:
	var cs: Array = r.combo_shots()
	for i in 3:
		r.combo_t = 0.0
		r.mode_event(cs[i % cs.size()])


func _run() -> void:
	_step(20)
	_check(g.state == "play", "game started on %s" % Settings.table_id)
	var ms: Array = r.story_modes()
	_check(ms.size() == 2, "two story modes (%s)" % ", ".join(ms.map(func(m: Dictionary) -> String: return m.name)))
	var sn: String = r.saucer_name()
	_check(g.table.holes.has(sn), "saucer '%s' exists" % sn)
	for m in ms:
		for s in m.shots:
			_check(s in r.shots(), "mode shot '%s' is a real shot" % s)
	_check(r.hurry_shot() in r.shots(), "hurry-up shot '%s' is a real shot" % r.hurry_shot())

	# --- story mode 1 started by a ball really landing in the saucer
	g.ball_save = 0.0
	var b = g.table.balls[0]
	var h: Dictionary = g.table.holes[sn]
	b.pos = Vector2(h.pos[0], h.pos[1])
	b.vel = Vector2.ZERO
	b.cool = 0.0
	b.ramp = -1
	var sc0 := g.score
	g.table._events(b)
	_check(r.mode == 0 and r.mode_starts == 1, "saucer started '%s'" % ms[0].name)
	_check(g.ball_save >= r.MODE_SAVE - 0.01, "ball save armed at mode start (%.1f s)" % g.ball_save)
	_check(g.score > sc0, "mode start scored")
	_check(r.mode_line() != "" and g._mission_lines()[0] == r.mode_line(), "HUD shows '%s'" % r.mode_line())
	_check(not r.mode_saucer(b, sn), "saucer does not restart a running mode")
	var m0: Dictionary = ms[0]
	for i in int(m0.need):
		r.mode_event(m0.shots[i % m0.shots.size()])
	_check(r.mode == -1 and 0 in r.mode_done, "mode 1 completed with %d shots" % int(m0.need))
	_check(g.table.extra_lit, "first completed mode lights the extra ball")
	g.table.extra_lit = false

	# --- relight, mode 2 times out
	_check(not r.mode_saucer(b, sn), "no mode before relight")
	_relight()
	_check(r.mode_lit, "3 shots relight the mode")
	_check(r.mode_saucer(b, sn) and r.mode == 1, "saucer started '%s'" % ms[1].name)
	r.mode_tick(float(ms[1].time) + 0.5)
	_check(r.mode == -1 and not 1 in r.mode_done, "mode 2 timed out (not completed)")
	_relight()
	_check(r.mode_saucer(b, sn) and r.mode == 1, "mode 2 restarted after relight")
	var m1: Dictionary = ms[1]
	for i in int(m1.need):
		r.mode_event(m1.shots[i % m1.shots.size()])
	_check(r.mode == -1 and r.wizard_lit, "all modes done: wizard lit")

	# --- wizard
	g.ball_save = 0.0
	_check(r.mode_saucer(b, sn) and r.mode == -2, "saucer started %s" % r.wizard_name())
	_check(g.ball_save >= 19.9, "wizard ball save 20 s")
	var sc1 := g.score
	r.mode_event(r.shots()[0])
	_check(g.score >= sc1 + 150000, "wizard shot worth 150,000+ (%d)" % (g.score - sc1))
	r.mode_tick(41.0)
	_check(r.mode == -1, "wizard ends on time")

	# --- combo
	r.combo_t = 0.0
	r.combo = 0
	var cs: Array = r.combo_shots()
	var sc2 := g.score
	r.mode_event(cs[0])
	r.mode_event(cs[1])
	r.mode_event(cs[2 % cs.size()])
	_check(r.combo == 2 and g.score >= sc2 + 60000, "3-way combo scores (%d)" % (g.score - sc2))
	r.mode_tick(r.COMBO_WINDOW + 0.1)
	_check(r.combo == 0, "combo window expires")

	# --- hurry-up
	r.hurry_start()
	_check(r.hurry_t > 0.0 and r.mode_line().begins_with("HURRY"), "hurry-up started: %s" % r.mode_line())
	r.mode_tick(5.0)
	var v: int = r.hurry_value()
	var sc3 := g.score
	r.mode_event(r.hurry_shot())
	_check(r.hurry_t == 0.0 and g.score >= sc3 + v and v < r.HURRY_MAX and v >= r.HURRY_MIN,
		"hurry-up collected %d" % v)
	r.hurry_start()
	r.mode_tick(r.HURRY_TIME + 0.1)
	_check(r.hurry_t == 0.0, "hurry-up times out")

	# --- new game resets progress
	r.wizard_lit = true
	r.mode_done = [0]
	g.table.reset_game()
	_check(r.mode == -1 and r.mode_done.is_empty() and not r.wizard_lit, "reset_game clears modes")
	_step(200)
	_check(g.state == "play", "game still running")
