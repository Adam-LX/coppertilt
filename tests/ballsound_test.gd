extends Node
## Ball sound test (headless, no sound output needed):
##   godot --headless --audio-driver Dummy --path . res://tests/ballsound_test.tscn
## Checks Sound.set_roll() (volume / pitch / low-pass follow the speed, pan, surfaces, fade-out,
## multiball), Sound.roll_hit(), and the automatic feed from a table's balls: ramp surface,
## drop clack at a ramp exit, ball-ball click, impact by material, silence while paused.

const FILES: Array[String] = ["roll_playfield", "roll_plastic", "roll_wire", "ramp_drop",
	"ball_click", "hit_flipper", "hit_rubber", "hit_metal"]

class FakeBall:
	var pos := Vector2(160, 300)
	var vel := Vector2.ZERO
	var ramp := -1
	var rs := 0.0
	var rv := 0.0
	var held := 0.0
	var hole := ""

class FakeTable extends Node:
	var multiball := false
	var balls: Array = []
	var g := {"size": [320, 640], "ball_r": 7.5}
	var ramps: Array = [{"name": "helter", "kind": "wire", "len": 400.0},
		{"name": "coaster", "kind": "plastic", "len": 500.0}]
	var flippers: Array = []
	var circ: Array = [[Vector2(60, 200), 3.0, "rubber", "post"]]
	var seg_a := PackedVector2Array([Vector2(10, 100)])
	var seg_b := PackedVector2Array([Vector2(10, 600)])
	var seg_mat: Array[String] = ["wall"]

class FakeGame extends Node:
	var state := "play"
	var table: FakeTable

var fails := 0


func _check(ok: bool, what: String) -> void:
	print("[ball] %s %s" % ["ok  " if ok else "FAIL", what])
	if not ok:
		fails += 1


func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func _feed(speed: float, surface: String, pan: float, balls: int, s: float) -> void:
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < int(s * 1000.0):
		for b in balls:
			Sound.set_roll(speed, surface, pan, b)
		await get_tree().process_frame


func _player(voice: int, surface: String) -> AudioStreamPlayer:
	return Sound._roll[voice].players[surface]


func _lpf(voice: int) -> AudioEffectLowPassFilter:
	return AudioServer.get_bus_effect(int(Sound._roll[voice].bus), 0) as AudioEffectLowPassFilter


func _pan(voice: int) -> float:
	return (AudioServer.get_bus_effect(int(Sound._roll[voice].bus), 1) as AudioEffectPanner).pan


func _hit_playing(hit_name: String) -> bool:
	for p in Sound._hit_players:
		if p.playing and p.stream != null and p.stream.resource_path.ends_with(hit_name + ".ogg"):
			return true
	return false


func _ready() -> void:
	Settings.persist = false
	await _frames(2)
	for f in FILES:
		_check(ResourceLoader.exists("res://assets/audio/ball/%s.ogg" % f), "file %s.ogg" % f)
	_check(Sound.has_method("set_roll") and Sound.has_method("roll_hit"), "API set_roll / roll_hit")

	# speed -> volume / pitch / filter, pan
	await _feed(600.0, "playfield", -1.0, 1, 0.6)
	var p := _player(0, "playfield")
	var v_fast := p.volume_db
	var pitch_fast := p.pitch_scale
	var cut_fast := _lpf(0).cutoff_hz
	_check(p.playing, "fast ball rolls (%.1f dB, pitch %.2f, low-pass %d Hz)" % [v_fast, pitch_fast, cut_fast])
	_check(v_fast > -9.0 and v_fast < -2.0, "roll clearly audible but below the music peak (%.1f dB)" % v_fast)
	_check(_pan(0) < -0.5, "panned left by x (%.2f)" % _pan(0))
	await _feed(90.0, "playfield", 1.0, 1, 0.8)
	_check(p.volume_db < v_fast - 6.0, "slow ball is quieter (%.1f dB)" % p.volume_db)
	_check(p.pitch_scale < pitch_fast - 0.15, "slow ball is lower (%.2f)" % p.pitch_scale)
	_check(_lpf(0).cutoff_hz < cut_fast * 0.4, "slow ball is darker (%d Hz)" % _lpf(0).cutoff_hz)
	_check(_pan(0) > 0.5, "pan follows x to the right (%.2f)" % _pan(0))

	# surfaces
	await _feed(400.0, "wire", 0.0, 1, 0.5)
	_check(_player(0, "wire").playing and not _player(0, "playfield").playing, "wireform surface")
	await _feed(400.0, "plastic", 0.0, 1, 0.5)
	_check(_player(0, "plastic").playing and not _player(0, "wire").playing, "plastic ramp surface")
	await get_tree().create_timer(0.5).timeout
	_check(not _player(0, "plastic").playing, "voice fades out when no longer fed")

	# multiball
	await _feed(400.0, "playfield", 0.0, 1, 0.6)
	var single := _player(0, "playfield").volume_db
	await _feed(400.0, "playfield", 0.0, 3, 0.6)
	var all3 := _player(0, "playfield").playing and _player(1, "playfield").playing and _player(2, "playfield").playing
	_check(all3, "one voice per ball in multiball")
	_check(_player(0, "playfield").volume_db < single - 2.5, "multiball voices are trimmed (%.1f vs %.1f dB)" % [_player(0, "playfield").volume_db, single])
	_check(not is_equal_approx(_player(0, "playfield").pitch_scale, _player(1, "playfield").pitch_scale), "voices slightly detuned")
	Sound.roll_hit("hit_metal", 1.0, 0.5)
	await _frames(2)
	_check(_hit_playing("hit_metal"), "roll_hit one-shot")
	Sound.roll_hit("nope")
	await get_tree().create_timer(0.7).timeout

	# automatic feed from a table
	var g := FakeGame.new()
	g.table = FakeTable.new()
	g.add_child(g.table)
	add_child(g)
	var b := FakeBall.new()
	b.vel = Vector2(0, -450)
	g.table.balls = [b]
	await get_tree().create_timer(0.5).timeout
	_check(_player(0, "playfield").playing, "auto: playfield roll from the table's ball")
	b.ramp = 0
	b.rv = 300.0
	b.rs = 100.0
	await get_tree().create_timer(0.3).timeout
	_check(_player(0, "wire").playing, "auto: wire ramp surface")
	b.rs = 390.0
	await _frames(3)
	b.ramp = -1
	b.pos = Vector2(250, 300)
	b.vel = Vector2(0, 300)
	await _frames(3)
	_check(_hit_playing("ramp_drop"), "auto: drop clack when the ball leaves a ramp")
	await get_tree().create_timer(0.4).timeout
	# impact on a rubber post
	b.pos = Vector2(60, 212)
	b.vel = Vector2(0, -400)
	await _frames(3)
	b.vel = Vector2(0, 350)
	await _frames(3)
	_check(_hit_playing("hit_rubber"), "auto: rubber post impact")
	await get_tree().create_timer(0.4).timeout
	# ball-ball click (multiball)
	var b2 := FakeBall.new()
	b2.pos = Vector2(200, 400)
	b2.vel = Vector2(-200, 0)
	b.pos = Vector2(150, 400)
	b.vel = Vector2(200, 0)
	g.table.balls = [b, b2]
	await _frames(3)
	b.pos = Vector2(170, 400)
	b2.pos = Vector2(184, 400)
	await _frames(3)
	_check(_hit_playing("ball_click"), "auto: ball-ball click")
	_check(_player(1, "playfield").playing, "auto: second ball has its own voice")
	# pause = silence
	get_tree().paused = true
	await get_tree().create_timer(0.5, true).timeout
	_check(not _player(0, "playfield").playing and not _player(1, "playfield").playing, "silent while paused")
	get_tree().paused = false
	g.queue_free()
	await get_tree().create_timer(0.4).timeout
	_check(not _player(0, "playfield").playing, "silent without a table")
	print("[ball] DONE fails=%d" % fails)
	get_tree().quit(1 if fails > 0 else 0)
