extends RefCounted
## Per-table rules base (scripts/table/rules/<table_id>.gd extends this file).
##
## PinTable (scripts/table/table.gd) is the shared engine: geometry, solver, flippers, plunger,
## lamps, flashers, ball look, tilt, ball search, multiball serving. Everything that makes one table
## different - what a shot scores, which inserts light, missions, DMD texts - lives in the rules
## script of that table. The engine calls the hooks below; `t` is the PinTable.
## Shared table state the HUD / game.gd read stays on the table (multiplier, multiball, lock_lit,
## locked, super_lit, extra_lit, kickback_lit, ramps_to_lock, lanes, ride, stars, drops, shot_n).

var t          # PinTable


## shot names: progress inserts "<shot>1..n" + "<shot>_arrow" in geometry.json; shot_n counters
## M11_MOVERS: [{bumper: index, off: [dx, dy], period: s}] bumpers that slide on a short track
func movers() -> Array:
	return []


func shots() -> Array:
	return []


## coloured flashers (PointLight2D): name -> [[x, y], Color, radius]
func flashers() -> Dictionary:
	return {}


## letters of the top lanes (for the HUD), e.g. "FAIR"
func lane_word() -> String:
	var s := ""
	for L in t.g.lanes:
		s += str(L.get("letter", "?"))
	return s


func reset_game() -> void:
	pass


func reset_ball() -> void:
	pass


func on_bumper(_i: int, _b) -> void:
	t._score(100)


func on_sling(_i: int) -> void:
	t._score(10)


func on_target(_i: int) -> void:
	t._score(500)


func on_drop(_i: int) -> void:
	t._score(2500)


func on_bank(_bank: String) -> void:
	t._score(10000)


func on_lane(_i: int) -> void:
	t._score(1000)


func on_star(_i: int) -> void:
	t._score(500)


func on_orbit(_name: String) -> void:
	t._score(5000)


func on_spinner() -> void:
	t._score(100 * t.spinner_level)


func on_hole(_b, _hn: String) -> void:
	t._score(5000)


func on_toy(_name: String, _b) -> void:
	t._score(2500)


func on_ramp(_ri: int, _name: String) -> void:
	t._score(10000 * t.multiplier)


func lamp_states() -> Dictionary:
	var on := {}
	finish_lamps(on)
	return on


func mission_lines() -> PackedStringArray:
	return PackedStringArray(["", ""])


func on_multiball_over() -> void:
	t.super_lit = false


# --- helpers for the table scripts ---------------------------------------------------------

func say(text: String, sfx := "", anim := "", anim_text := "") -> void:
	t.announce.emit(text, sfx)
	if anim != "":
		t.dmd_anim.emit(anim, anim_text if anim_text != "" else text)


## skill shot: a soft plunge that drops into a top lane
func skill_lane(points := 25000, word := "SKILL SHOT") -> void:
	if t._skill_t > 0.0 and not t.tilted:
		t._skill_t = 0.0
		t._score(points)
		say("%s %s" % [word, _fmt(points)], "jackpot", "sparkle", word)


## top lanes: light one, all lit -> reset + callback
func light_lane(i: int, done: Callable) -> void:
	if t.lanes[i]:
		t._score(500)
		return
	t.lanes[i] = true
	t._score(1000)
	if t.lanes.count(true) == t.lanes.size():
		for k in t.lanes.size():
			t.lanes[k] = false
		t._score(10000)
		done.call()


func bump_multiplier(maxed_text := "BONUS MAX 25,000") -> void:
	if t.multiplier < 6:
		t.multiplier += 1
		say("BONUS %dX" % t.multiplier, "bonus", "big", "%dX" % t.multiplier)
	else:
		t._score(25000)
		say(maxed_text, "bonus")


## start a multiball: this ball keeps playing, `extra` more are served from the plunger lane
func start_multiball(extra: int, text: String, anim := "jackpot") -> void:
	t.lock_lit = false
	t.locked = 0
	t.multiball = true
	t._show = 1.2
	t.super_lit = false
	t._score(100000)
	say(text, "jackpot", anim, text)
	jackpot_fx()
	t._serve = extra
	t._serve_t = 0.6


## number of progress inserts "<shot>1..n" for a shot
func chase_len(shot: String) -> int:
	var n := 0
	while t.light_pos.has("%s%d" % [shot, n + 1]):
		n += 1
	return n


## progress inserts + arrow of one shot (arrow: 0 off, 1 on, 2 slow, 3 fast); chase on a made shot
func shot_lamps(on: Dictionary, shot: String, arrow: int, prog := -1) -> void:
	var n := chase_len(shot)
	if prog < 0:
		prog = int(t.shot_n.get(shot, 0)) % (n + 1)
	on[shot + "_arrow"] = arrow
	for j in n:
		on["%s%d" % [shot, j + 1]] = 1 if j < prog else 0
	if t._chase.has(shot):
		var step := int(t._chase[shot] * 12.0) % (n + 1)
		for j in n:
			on["%s%d" % [shot, j + 1]] = 1 if j == n - 1 - step else 0
		on[shot + "_arrow"] = 1 if step == n else 0


## lamps every table shares + light shows + the plunger power meter (call last)
func finish_lamps(on: Dictionary) -> void:
	for i in t.lanes.size():
		var L: Dictionary = t.g.lanes[i]
		on["lane_" + str(L.get("letter", str(i)))] = 1 if t.lanes[i] else 0
	for i in t.g.drops.size():
		var d: Dictionary = t.g.drops[i]
		on[d.bank + "_" + d.letter] = 1 if t.drops[i] else 0
	for i in t.stars.size():
		on["star%d" % i] = 1 if t.stars[i] else 0
	for m in range(2, 7):
		on["mult%d" % m] = 1 if t.multiplier >= m else 0
	on["kickback"] = 1 if t.kickback_lit else 0
	on["shoot_again"] = 2 if t.save_lit else 0
	on["extra_ball"] = 2 if t.extra_lit else 0
	if t.g.has("spinner"):
		on["spinner"] = 3 if t.spin_v > 0.3 else (1 if t.spinner_level > 1 else 0)
	# light shows: attract patterns while a ball waits in the shooter lane, sweep on multiball start
	var waiting := false
	for b in t.balls:
		if t.lane_rect.has_point(b.pos):
			waiting = true
	if waiting and not t.multiball:
		t._apply_pattern(on, int(t._time / 4.0) % 8, t._time)
	elif t._show > 0.0:
		t._apply_pattern(on, 0, 1.2 - t._show)
	elif mode == -2:   # M11_FX: wizard = radar sweep over the unlit lamps
		_overlay(on, 3, t._time * 1.6)
	elif t.multiball:   # multiball = sparkle over the unlit lamps, game lamps stay readable
		_overlay(on, 6, t._time)
	# plunger power meter in the shooter lane (never part of the light shows)
	for i in t.METER_AT.size():
		var mk := "meter%d" % i
		if not t.light_pos.has(mk):
			continue
		if t.charging:
			on[mk] = 1 if t.charge >= t.METER_AT[i] else 0
		elif waiting and (i == 1 or i == 2):
			on[mk] = 2
		else:
			on[mk] = 0


static func _fmt(n: int) -> String:
	var s := str(n)
	var out := ""
	while s.length() > 3:
		out = "," + s.substr(s.length() - 3) + out
		s = s.substr(0, s.length() - 3)
	return s + out


# --- M11_MODES: combos, hurry-up, story modes from the saucer, wizard mode ---------------------
# Shared by every table. The engine (table.gd) calls modes_reset / modes_ball / mode_tick,
# mode_event(<shot>) after every made shot, mode_saucer(b, hole) before on_hole and hurry_start()
# when a drop bank is completed. A table only lists its modes in story_modes().

const COMBO_WINDOW := 3.5
const HURRY_TIME := 20.0
const HURRY_MAX := 300000
const HURRY_MIN := 30000
const MODE_SAVE := 10.0

var combo := 0
var combo_t := 0.0
var hurry_t := 0.0
var mode := -1               # index into story_modes(), -2 = wizard, -1 = none
var mode_t := 0.0
var mode_hits := 0
var mode_lit := true
var mode_done: Array = []    # completed mode indexes
var relight := 0             # shots left until the next mode is lit again
var wizard_lit := false
var mode_starts := 0         # for tests


## [{name, shots: [..], need, time, value}]; the saucer starts them in turn
func story_modes() -> Array:
	return []


func saucer_name() -> String:
	return "saucer"


func hurry_shot() -> String:
	return ""


func wizard_name() -> String:
	return "WIZARD MODE"


## major shots that count for combos
func combo_shots() -> Array:
	var a := shots().duplicate()
	a.erase(saucer_name())
	return a


func modes_reset() -> void:
	mode_done = []
	wizard_lit = false
	modes_ball()


func modes_ball() -> void:
	combo = 0
	combo_t = 0.0
	hurry_t = 0.0
	mode = -1
	mode_t = 0.0
	mode_hits = 0
	mode_lit = true
	relight = 0


var _fl_t := 0.0
var _fl_i := 0


## lights a light-show pattern only where the game left a lamp dark
func _overlay(on: Dictionary, pat: int, time: float) -> void:
	var tmp := {}
	t._apply_pattern(tmp, pat, time)
	for k in tmp:
		if tmp[k] == 1 and int(on.get(k, 0)) == 0:
			on[k] = 1


func mode_tick(delta: float) -> void:
	# multiball / wizard: flashers fire in turn
	if (t.multiball or mode == -2) and not t.tilted and not t.flash.is_empty():
		_fl_t -= delta
		if _fl_t <= 0.0:
			_fl_t = 0.35 if mode == -2 else 0.6
			var ks: Array = t.flash.keys()
			_fl_i = (_fl_i + 1) % ks.size()
			t.flash[ks[_fl_i]] = maxf(float(t.flash[ks[_fl_i]]), 0.75)
	combo_t = maxf(0.0, combo_t - delta)
	if combo_t <= 0.0:
		combo = 0
	if hurry_t > 0.0:
		hurry_t = maxf(0.0, hurry_t - delta)
		if hurry_t <= 0.0:
			say("HURRY-UP OVER", "drain")
	if mode != -1 and not t.tilted:
		mode_t -= delta
		if mode_t <= 0.0:
			_mode_end(false)


func hurry_value() -> int:
	return int(lerpf(HURRY_MIN, HURRY_MAX, hurry_t / HURRY_TIME)) / 1000 * 1000


func hurry_start() -> void:
	if hurry_shot() == "" or hurry_t > 0.0 or t.tilted:
		return
	hurry_t = HURRY_TIME
	say("HURRY-UP: SHOOT %s" % hurry_shot().to_upper(), "bonus", "big", "HURRY-UP")


func mode_event(shot: String) -> void:
	if t.tilted:
		return
	# combos: major shots in quick succession
	if shot in combo_shots():
		if combo_t > 0.0:
			combo += 1
			var pts := 20000 * combo
			t._score(pts)
			if combo >= 2:
				say("%d-WAY COMBO %s" % [combo + 1, _fmt(pts)], "bonus", "big", "COMBO X%d" % (combo + 1))
		combo_t = COMBO_WINDOW
		if relight > 0:
			relight -= 1
			if relight == 0 and mode == -1:
				mode_lit = true
				say("MODE IS LIT AT %s" % saucer_name().to_upper(), "bonus")
	# hurry-up collect
	if hurry_t > 0.0 and shot == hurry_shot():
		var v := hurry_value()
		hurry_t = 0.0
		t._score(v)
		jackpot_fx()
		say("HURRY-UP %s" % _fmt(v), "jackpot", "jackpot", _fmt(v))
	# story mode / wizard progress
	if mode == -2:
		t._score(150000)
		mode_hits += 1
		jackpot_fx()
		say("%s %d" % [wizard_name(), mode_hits], "jackpot", "sparkle", "150,000")
	elif mode >= 0:
		var m: Dictionary = story_modes()[mode]
		if shot in m.shots:
			mode_hits += 1
			t._score(int(m.value))
			t.flash_all(0.7)
			if mode_hits >= int(m.need):
				_mode_end(true)
			else:
				say("%s %d/%d" % [m.name, mode_hits, int(m.need)], "bonus", "big", "%d/%d" % [mode_hits, int(m.need)])


## the saucer starts the lit mode (extra ball and multiball keep priority); true = handled
func mode_saucer(_b, hn: String) -> bool:
	if hn != saucer_name() or t.tilted or t.multiball or t.extra_lit or mode != -1:
		return false
	var ms := story_modes()
	if ms.is_empty():
		return false
	if wizard_lit:
		wizard_lit = false
		mode = -2
		mode_t = 40.0
		mode_hits = 0
		mode_starts += 1
		t._score(250000)
		t.save_request.emit(20.0)
		jackpot_fx()
		say(wizard_name(), "jackpot", "jackpot", wizard_name())
		return true
	if not mode_lit:
		return false
	var idx := -1
	for i in ms.size():
		var k: int = (mode_done.size() + i) % ms.size()
		if not k in mode_done:
			idx = k
			break
	if idx < 0:
		return false
	mode = idx
	mode_lit = false
	mode_hits = 0
	mode_starts += 1
	mode_t = float(ms[idx].time)
	t._score(50000)
	t.save_request.emit(MODE_SAVE)
	t._show = 1.2
	say("%s: SHOOT %s" % [ms[idx].name, " ".join(ms[idx].shots).to_upper()], "jackpot", "big", ms[idx].name)
	return true


func _mode_end(won: bool) -> void:
	var ms := story_modes()
	if mode == -2:
		say("%s TOTAL %d" % [wizard_name(), mode_hits], "bonus", "big", "WIZARD OVER")
	elif won:
		var m: Dictionary = ms[mode]
		if not mode in mode_done:
			mode_done.append(mode)
		t._score(500000)
		jackpot_fx()
		say("%s COMPLETE 500,000" % m.name, "jackpot", "jackpot", "COMPLETE")
		if mode_done.size() == 1:
			t.extra_lit = true
		if mode_done.size() >= ms.size():
			mode_done = []
			wizard_lit = true
			say("%s IS LIT" % wizard_name(), "jackpot", "sparkle", "WIZARD LIT")
	else:
		say("%s OVER" % ms[mode].name, "drain")
	mode = -1
	mode_t = 0.0
	relight = 3


func jackpot_fx() -> void:
	t.flash_all(1.0)
	t._show = 1.2
	t.kick_shake(0.8)


## first HUD line while a mode or hurry-up runs ("" = the table's own line)
func mode_line() -> String:
	if mode == -2:
		return "%s %ds" % [wizard_name(), ceili(mode_t)]
	if mode >= 0:
		var m: Dictionary = story_modes()[mode]
		return "%s %d/%d %ds" % [m.name, mode_hits, int(m.need), ceili(mode_t)]
	if hurry_t > 0.0:
		return "HURRY %s %s" % [hurry_shot().to_upper(), _fmt(hurry_value())]
	if wizard_lit:
		return "%s: WIZARD LIT" % saucer_name().to_upper()
	return ""
