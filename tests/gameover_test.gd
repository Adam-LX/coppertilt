extends Node
## End-of-game flow test (headless, deterministic):
##   godot --headless --path . res://tests/gameover_test.tscn
## Drains every ball and checks: ball save only once per ball, MATCH (both outcomes via
## seed), extra chance continues the same game, GAME OVER -> final score -> initials entry
## (saved in memory only) -> return to the menu. Never writes the player's settings file.

const DT := 1.0 / 200.0
var g: PinGame
var fails := 0
var states: Array[String] = []
var _done := false


func _ready() -> void:
	Settings.persist = false
	Settings.demo = false
	Settings.high_scores.erase(Settings.table_id)
	g = load("res://scenes/game.tscn").instantiate()
	add_child(g)
	await get_tree().process_frame
	g.set_process(false)
	g.table.set_physics_process(false)
	g.finished.connect(func() -> void: _done = true)
	_run_match_game()
	_run_no_match_game()
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
		if states.is_empty() or states[-1] != g.state:
			states.append(g.state)


func _wait(pred: Callable, max_s: float) -> bool:
	var n := int(max_s / DT)
	for i in n:
		if pred.call():
			return true
		_step(1)
	return pred.call()


func _drain() -> void:
	for b in g.table.balls:
		b.pos = Vector2(160, 660)
		b.vel = Vector2(0, 60)
	_step(2)


func _seed_for(score: int, want_hit: bool) -> int:
	var m: Dictionary = g.rules.match
	var rng := RandomNumberGenerator.new()
	for s in 1000:
		rng.seed = s
		if (PinGame.match_roll(rng, score, m) == PinGame.match_target(score, m)) == want_hit:
			return s
	return -1


func _odds() -> void:
	var m: Dictionary = g.rules.match
	var rng := RandomNumberGenerator.new()
	rng.seed = 12345
	var hits := 0
	for i in 10000:
		if PinGame.match_roll(rng, 120 + (i % 10) * 10, m) == PinGame.match_target(120 + (i % 10) * 10, m):
			hits += 1
	_check(hits > 850 and hits < 1150, "match odds ~1 in 10 (%d / 10000)" % hits)
	_check(PinGame.match_target(2345670, m) == 7, "match compares the TENS digit")


func _run_match_game() -> void:
	print("[test] --- game 1: ball save once, MATCH hit, extra chance, high score entry")
	_odds()
	states.clear()
	_step(20)
	_check(g.state == "play" and g.ball_no == 1, "game starts on ball 1")
	g._on_launched()
	_check(g.ball_save > 0.0, "ball save armed on first plunge")
	_drain()
	_check(g.state == "play" and g.table.balls.size() == 1, "quick drain saved")
	g._on_launched()
	_check(g.ball_save == 0.0, "ball save NOT re-armed on second plunge (was the endless-game bug)")
	_drain()
	_check(g.state == "drain", "second drain loses the ball")
	_check(_wait(func() -> bool: return g.state == "play" and g.ball_no == 2, 5.0), "ball 2 served")
	_drain()
	_check(_wait(func() -> bool: return g.state == "play" and g.ball_no == 3, 5.0), "ball 3 served")
	g.score = 2345670
	g.match_seed = _seed_for(2345670, true)
	g.table.multiplier = 3
	_drain()
	_check(_wait(func() -> bool: return g.state == "match", 5.0), "MATCH after the last ball")
	_check(g.table.balls.is_empty(), "no ball left in the shooter lane during MATCH")
	_check(g._match_hit, "seeded MATCH hit (seed %d, roll %d)" % [g.match_seed, g._match_num])
	var sc := g.score
	_check(_wait(func() -> bool: return g.state == "play", 8.0), "extra chance: play resumes")
	_check(g.ball_no == 3 and g.score == sc and g.table.balls.size() == 1 and g.table.input_enabled,
		"same game continues (ball %d, score %d, %d ball)" % [g.ball_no, g.score, g.table.balls.size()])
	_check(g.table.multiplier == 3, "table state kept (bonus %dX)" % g.table.multiplier)
	g._on_launched()
	_check(g.ball_save > 0.0, "extra chance ball gets its own ball save")
	g.ball_save = 0.0
	_drain()
	_check(_wait(func() -> bool: return g.state == "gameover", 5.0), "no second MATCH -> GAME OVER")
	_check(not states.slice(states.rfind("play")).has("match"), "MATCH only once per game")
	_check(not g.table.input_enabled and g.table.balls.is_empty(), "flippers off, table empty at game over")
	_check(_wait(func() -> bool: return g.state == "final", 5.0), "final score shown")
	_check(_wait(func() -> bool: return g.state == "entry", 5.0), "high score -> initials entry")
	g.entry_input("next")
	g.entry_input("prev")
	g.entry_input("char:A")
	g.entry_input("char:D")
	g.entry_input("back")
	g.entry_input("char:D")
	g.entry_input("char:M")
	_check(g.state == "over", "entry finished")
	var hs := Settings.scores_for(Settings.table_id)
	_check(hs[0][0] == "ADM" and int(hs[0][1]) == g.score, "saved as #1: %s %d" % [hs[0][0], hs[0][1]])
	_check(Settings.high_score >= g.score, "overall high score updated")
	_done = false
	_check(_wait(func() -> bool: return _done, 20.0), "returns to the menu (finished)")
	print("[test] states: ", " > ".join(states))


func _run_no_match_game() -> void:
	print("[test] --- game 2: MATCH miss -> GAME OVER, no entry for a low score")
	states.clear()
	g._start_game()
	_step(10)
	for b in 2:
		_drain()
		_check(_wait(func() -> bool: return g.state == "play" and g.ball_no == b + 2, 5.0), "ball %d served" % (b + 2))
	g.score = 12340
	g.match_seed = _seed_for(12340, false)
	_drain()
	_check(_wait(func() -> bool: return g.state == "match", 5.0), "MATCH after the last ball")
	_check(not g._match_hit, "seeded MATCH miss (seed %d, roll %d vs 4)" % [g.match_seed, g._match_num])
	_check(_wait(func() -> bool: return g.state != "match", 8.0) and g.state == "gameover", "miss -> GAME OVER")
	_check(_wait(func() -> bool: return g.state == "over", 10.0), "low score skips the entry")
	_check(not states.has("entry"), "no initials entry")
	_done = false
	_check(_wait(func() -> bool: return _done, 20.0), "returns to the menu (finished)")
	print("[test] states: ", " > ".join(states))
