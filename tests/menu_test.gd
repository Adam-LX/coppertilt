extends Node
## Main menu test (headless): godot --headless --path . res://tests/menu_test.tscn
## Drives the menu with input actions (as keyboard / pad would) and checks pages, the table
## carousel, options and that every page draws. Never writes the player's settings file.

var m: Control
var fails := 0


func _check(ok: bool, what: String) -> void:
	print("[menu] %s %s" % ["ok  " if ok else "FAIL", what])
	if not ok:
		fails += 1


func _press(action: StringName) -> void:
	var ev := InputEventAction.new()
	ev.action = action
	ev.pressed = true
	m._unhandled_input(ev)


func _frames(n := 3) -> void:
	for i in n:
		await get_tree().process_frame


func _ready() -> void:
	Settings.persist = false
	var style0 := Settings.style
	var tempo0 := Settings.tempo
	var music0 := Settings.music_volume
	m = load("res://scenes/title.tscn").instantiate()
	m.size = Vector2(1920, 1080)
	add_child(m)
	await _frames()
	var tabs := Settings.tables()
	_check(tabs.size() >= 1, "tables found: %d" % tabs.size())
	_check(m._previews.size() >= 1, "preview images loaded: %d" % m._previews.size())
	_check(m.page == "main" and m._items().size() == 5, "main page has 5 items")
	var sel = tabs[0]
	for tb in tabs:      # the carousel opens on the player's last-picked table (persisted setting)
		if tb.id == Settings.table_id:
			sel = tb
	_check(m._items()[0][1] == sel.name, "carousel shows " + str(sel.name))
	_press(&"ui_down"); _press(&"ui_down")
	_check(m._items()[m.sel][0] == "OPTIONS", "down x2 -> OPTIONS")
	_press(&"ui_accept")
	_check(m.page == "options", "accept -> options page")
	await _frames()
	for i in 4:
		_press(&"ui_down")
	_check(m._items()[m.sel][0] == "GAME SPEED", "GAME SPEED item")
	var t := Settings.tempo
	_press(&"ui_right")
	_check(is_equal_approx(Settings.tempo, minf(t + 0.05, Settings.TEMPO_MAX)), "right on GAME SPEED: %.2f -> %.2f" % [t, Settings.tempo])
	_press(&"ui_left")
	_check(is_equal_approx(Settings.tempo, t), "left restores tempo")
	for i in 4:
		_press(&"ui_up")
	_press(&"ui_accept")
	_check(Settings.style != style0, "accept on STYLE toggles to " + Settings.style_name())
	_press(&"ui_accept")
	_check(Settings.style == style0, "toggle back")
	# 3D view options: VIEW 3D / 2D CLASSIC, 3D SHADOWS, LIGHT FX (never saved here)
	var view0 := Settings.view
	_press(&"ui_down")
	_check(m._items()[m.sel][0] == "VIEW", "VIEW item")
	_press(&"ui_accept")
	_check(Settings.view != view0, "accept on VIEW toggles to " + Settings.view_name())
	_press(&"ui_accept")
	_check(Settings.view == view0, "VIEW back")
	var sh0 := Settings.shadows3d
	_press(&"ui_down")
	_press(&"ui_accept")
	_check(Settings.shadows3d != sh0, "accept on 3D SHADOWS toggles to " + Settings.shadows_name())
	_press(&"ui_accept")
	_check(Settings.shadows3d == sh0, "3D SHADOWS back")
	var lf0 := Settings.lightfx
	_press(&"ui_down")
	_press(&"ui_left")
	_check(Settings.lightfx == maxi(lf0 - 1, 0), "left on LIGHT FX -> " + Settings.lightfx_name())
	Settings.set_lightfx(lf0)
	_check(m._items()[m.sel][1] == Settings.lightfx_name(), "lighting value shown")
	for i in 3:
		_press(&"ui_down")
	var mv := Settings.music_volume
	_press(&"ui_left")
	_check(Settings.music_volume < mv or mv == 0.0, "music volume down: %.1f -> %.1f" % [mv, Settings.music_volume])
	_press(&"ui_right")
	_check(is_equal_approx(Settings.music_volume, mv), "music volume back")
	_press(&"ui_down"); _press(&"ui_down")
	_check(m._items()[m.sel][0] == "CONTROLS", "CONTROLS item")
	_press(&"ui_accept")
	_check(m.page == "controls", "controls page")
	await _frames()
	_press(&"back")
	_check(m.page == "options", "back -> options")
	_press(&"ui_cancel")
	_check(m.page == "main" and m._items()[m.sel][0] == "OPTIONS", "cancel -> main, OPTIONS selected")
	_press(&"ui_down")
	_press(&"ui_accept")
	_check(m.page == "scores", "HIGH SCORES page")
	await _frames()
	_check(Settings.scores_for(str(tabs[0].id)).size() == Settings.HS_COUNT, "top 5 listed")
	_press(&"ui_accept")
	_check(m.page == "main", "BACK from scores")
	# carousel wraps (one table today -> stays; more tables -> moves)
	m.sel = 0
	var ti: int = m._ti
	_press(&"ui_right")
	_check(m._ti == (ti + 1) % tabs.size(), "carousel right")
	_press(&"flip_left")
	_check(m._ti == ti, "carousel left (flipper button)")
	# portrait and ultrawide layouts draw without errors
	for sz in [Vector2(2560, 1080), Vector2(1080, 1920), Vector2(1280, 720)]:
		m.size = sz
		for p in ["main", "options", "scores", "controls"]:
			m.page = p
			m.sel = 0
			await _frames(2)
	_check(true, "all pages drawn at 3 more sizes")
	Settings.style = style0
	Settings.set_tempo(tempo0)
	Settings.set_volume("music", music0)
	print("[menu] DONE fails=%d" % fails)
	get_tree().quit(1 if fails > 0 else 0)
