extends Node
## Audio manager test (headless, no sound output needed):
##   godot --headless --audio-driver Dummy --path . res://tests/sound_test.tscn
## Checks the named stingers (and the silent fallback), title intro -> menu theme -> HIGH SCORES
## music, Midnight Funfair normal <-> multiball switching on a bar line, initials entry music,
## ducking in end-of-game states and refresh_volume(). Never writes the player's settings file.

const STINGERS: Array[String] = ["match", "match_miss", "match_tick", "extra_chance", "game_over",
	"final_score", "highscore", "menu", "menu_move", "menu_back", "menu_start", "menu_denied"]

class FakeTable extends Node:
	var multiball := false

class FakeGame extends Node:
	var state := "play"
	var table: FakeTable

class FakeMenu extends Node:
	var page := "main"

var fails := 0


func _check(ok: bool, what: String) -> void:
	print("[sound] %s %s" % ["ok  " if ok else "FAIL", what])
	if not ok:
		fails += 1


func _wait(s: float) -> void:
	await get_tree().create_timer(s).timeout


func _wait_for(track: String, max_s: float) -> float:
	var t0 := Time.get_ticks_msec()
	while Sound.current_music() != track and Time.get_ticks_msec() - t0 < int(max_s * 1000.0):
		await get_tree().process_frame
	return (Time.get_ticks_msec() - t0) / 1000.0


func _ready() -> void:
	Settings.persist = false
	var mv := Settings.music_volume
	for n in STINGERS:
		_check(Sound.has_stinger(n), "stinger " + n)
	_check(not Sound.has_stinger("no_such_stinger"), "missing stinger reported missing")
	Sound.play_stinger("no_such_stinger")        # must be silent, no error
	Sound.play_stinger("match")
	await get_tree().process_frame
	_check(Sound._duck_until > Sound._time, "musical stinger ducks the music")
	Sound.play_stinger("menu_move")

	# voice callouts
	const VOICES := ["skill_shot", "super_skill_shot", "extra_ball", "extra_ball_lit",
		"jackpot", "super_jackpot", "multiball", "lock_lit", "ball_locked", "hurry_up",
		"shoot_again", "video_mode", "game_over", "tilt_warning", "tilted", "kickback",
		"combo", "super_combo", "start_midnight_funfair", "start_copper_speedway", "start_launch_pad"]
	for v in VOICES:
		_check(Sound.has_voice(v), "voice " + v)
	_check(not Sound.has_voice("no_such_voice"), "missing voice reported missing")
	Sound.play_voice("skill_shot")
	await get_tree().process_frame
	_check(Sound._duck_until > Sound._time, "voice callout ducks the music")

	# menu: title intro, then the unreal-profile menu theme; HIGH SCORES page -> hiscore
	var menu := FakeMenu.new()
	add_child(menu)
	Sound.play_music("title")
	_check(Sound.current_music() == "title", "title.ogg plays first (intro/cracktro)")
	Sound._intro_done = true                     # skip the 17 s intro
	await _wait_for("menu", 2.0)
	_check(Sound.current_music() == "menu", "after the intro -> menu theme")
	menu.page = "scores"
	await _wait_for("hiscore", 2.0)
	_check(Sound.current_music() == "hiscore", "HIGH SCORES page -> hiscore")
	menu.page = "main"
	await _wait_for("menu", 2.0)
	Sound.play_music("title")
	await get_tree().process_frame
	_check(Sound.current_music() == "menu", "title again (back from a game) -> menu, intro not repeated")
	menu.queue_free()
	await get_tree().process_frame

	# Midnight Funfair
	var g := FakeGame.new()
	g.table = FakeTable.new()
	g.add_child(g.table)
	add_child(g)
	Sound.play_music("funfair")
	await get_tree().process_frame
	_check(Sound.current_music() == "funfair", "funfair theme")
	var bar := float(Sound._meta_of("funfair").get("bar_s", 0.0))
	_check(bar > 1.0 and float(Sound._meta_of("funfair").get("loop_offset", 0.0)) > 0.0, "funfair sidecar: bar %.3f s" % bar)
	await _wait(0.4)
	g.table.multiball = true
	for _i in 10:                     # await resumes before the autoload's _process: give it a few frames
		await get_tree().process_frame
		if Sound._pending != "":
			break
	var at := Sound._pending_at
	_check(Sound._pending == "funfair_multiball", "multiball switch waits for the bar line")
	_check(absf(at / bar - roundf(at / bar)) < 0.001, "switch point %.3f s is on a bar line" % at)
	await _wait_for("funfair_multiball", bar + 1.0)
	_check(Sound.current_music() == "funfair_multiball", "multiball theme after the bar line")
	g.table.multiball = false
	await _wait_for("funfair", 3.0)
	_check(Sound.current_music() == "funfair", "back to the normal theme")
	g.state = "match"
	await _wait(0.5)
	_check(Sound._duck < -3.0, "music ducked during MATCH (%.1f dB)" % Sound._duck)
	g.state = "entry"
	await _wait_for("hiscore", 2.0)
	_check(Sound.current_music() == "hiscore", "initials entry -> hiscore music")
	g.state = "play"
	await _wait_for("funfair", 2.0)
	_check(Sound.current_music() == "funfair", "new game -> funfair again")
	await _wait(Sound.FADE_S + 0.3)   # let the crossfade finish before reading the gain

	# volume
	Settings.music_volume = 0.5
	Sound.refresh_volume()
	var expect := linear_to_db(0.5) + Sound.MUSIC_DB + Sound._duck
	_check(absf(Sound._music.volume_db - expect) < 0.5, "refresh_volume applies music volume (%.1f dB)" % Sound._music.volume_db)
	Settings.music_volume = mv
	Sound.refresh_volume()
	Sound.stop_music()
	print("[sound] DONE fails=%d" % fails)
	get_tree().quit(1 if fails > 0 else 0)
