extends Node
## Sound effects pool + music manager (autoload "Sound").
## SFX: tools/gen_audio.py (procedural). Music + stingers: tools/amigamusic (own tracker synth,
## see docs/MUZYKA-AMIGA.md). title.ogg is the original intro/cracktro tune and is never regenerated.
##
## Music is driven by play_music(name) plus light polling of the current scene (no extra hooks):
##   "title"   -> title.ogg once (intro/cracktro), then the "menu" theme (unreal profile, ambient);
##                the menu's HIGH SCORES page plays "hiscore" (same theme, action section)
##   "funfair" -> Midnight Funfair; table.multiball switches to "funfair_multiball" on the next
##                bar line (bar_s from the JSON sidecar); initials entry plays "hiscore";
##                MATCH / GAME OVER / final score duck the music under the stingers
## Each music OGG has a sidecar <name>.json from the renderer (loop_offset, bar_s, ...): the loop
## restarts at loop_offset, so an intro plays once and the loop is seamless.
##
## Ball sounds (tools/gen_ballsound.py, docs/DZWIEK-KULKI.md): set_roll(speed, surface, pan, ball)
## drives one rolling voice per ball (playfield / plastic / wire loop plus a steel "shimmer" layer
## that grows with speed; volume + pitch + low-pass follow the speed, panned by x). roll_hit(name, strength, pan) plays a one-shot (ramp_drop,
## ball_click, hit_flipper, hit_rubber, hit_metal). While the game does not call set_roll() itself,
## Sound feeds it from the current table's balls (positions, ramps, impacts), so no hook is needed.

const SFX_DIR := "res://assets/audio/sfx/"
const MUSIC_DIR := "res://assets/audio/music/"
const STINGER_DIR := "res://assets/audio/stingers/"
const VOICE_DIR := "res://assets/audio/voice/"
const SFX_NAMES: Array[String] = [
	"flipper", "flipper_down", "bumper", "sling", "rollover", "target", "post",
	"launch", "plunger", "drain", "tilt", "warn", "bonus", "start", "jackpot", "save",
	"launch_launch_pad", "launch_copper_speedway",
	"bumper_launch_pad", "bumper_copper_speedway",
	"jackpot_launch_pad", "jackpot_copper_speedway",
	"turbo_blowoff", "engine_shift", "backfire", "tire_screech",
	"telemetry_chirp", "countdown_beep", "plasma_shield"]
## Stingers that are UI blips: they follow the effects volume and never duck the music.
const UI_STINGERS: Array[String] = [
	"menu", "menu_move", "menu_back", "menu_start", "menu_denied", "match_tick"]
const MUSIC_DB := -6.0          # music bed level under the effects
const STINGER_DB := -2.0        # musical stingers sit a bit above the bed
const VOICE_DB := +1.0          # announcer callouts sit cleanly above sfx/music
const FADE_S := 0.8             # crossfade between different pieces
const BAR_FADE_S := 0.12        # short crossfade on a bar line (normal <-> multiball)
const DUCK_DB := -9.0           # music under a musical stinger
const STATE_DUCK_DB := -7.0     # music during MATCH / GAME OVER / final score
const PAIRS := {
	"funfair": "funfair_multiball", "funfair_multiball": "funfair",
	"launch_pad": "launch_pad_multiball", "launch_pad_multiball": "launch_pad",
	"copper_speedway": "copper_speedway_multiball", "copper_speedway_multiball": "copper_speedway",
}

var _sfx: Dictionary = {}
var _players: Array[AudioStreamPlayer] = []
var _next := 0
var _music: AudioStreamPlayer            # audible (fading-in) music player
var _music_b: AudioStreamPlayer          # the other one (fading out / idle)
var _music_name := ""                    # track in _music
var _request := ""                       # last play_music() argument
var _intro_done := false                 # title.ogg has played once this session
var _gain: Dictionary = {}               # player -> [gain, target, per-second step]
var _pending := ""                       # track waiting for the next bar line
var _pending_at := -1.0
var _last_pos := 0.0
var _meta: Dictionary = {}               # track -> sidecar dictionary
var _streams: Dictionary = {}            # stinger name -> AudioStream (or null if missing)
var _sting: Array[AudioStreamPlayer] = []
var _sting_ui: Dictionary = {}           # player -> bool
var _sn := 0
var _voice: Dictionary = {}              # voice callout name -> AudioStream
var _voice_players: Array[AudioStreamPlayer] = []
var _vn := 0
var _time := 0.0
var _duck_until := 0.0
var _duck := 0.0                         # current duck in dB (smoothed)

# --- ball rolling / impacts ---
const BALL_DIR := "res://assets/audio/ball/"
const ROLL_SURFACES: Array[String] = ["playfield", "plastic", "wire"]
const ROLL_VOICES := 4
const ROLL_DB := -5.0           # loop level at full speed: about as loud as the music bed (like a real machine)
const SHIMMER_DB := -5.0        # steel sheen layer (roll_shimmer.ogg) at full speed, fades in above ~25% speed
const ROLL_REF_SPEED := 500.0   # px/s that counts as "fast" (launch / orbit speed)
const ROLL_MIN_SPEED := 6.0     # below this the ball is as good as still
const ROLL_HOLD_S := 0.12       # a voice not fed for this long fades out
const ROLL_MULTI_DB := -1.5     # per extra rolling ball, so multiball does not get loud
const BALL_HITS := {"ramp_drop": -4.0, "ball_click": -8.0, "hit_flipper": -7.0,
	"hit_rubber": -7.0, "hit_metal": -9.0}
const HIT_MIN_DV := 110.0       # px/s velocity change in one frame that counts as an impact
var _roll: Array[Dictionary] = []
var _roll_fed := -10.0                   # last time the game called set_roll() itself
var _hit_fed := -10.0                    # last time the game called roll_hit() itself
var _ball_state: Dictionary = {}         # ball index -> last pos / vel / ramp / rs / cooldown
var _hit_players: Array[AudioStreamPlayer] = []
var _hit_panners: Array[AudioEffectPanner] = []
var _hn := 0
var _ball_streams: Dictionary = {}
# --- diagnostics (user args, never saved): --sound-probe prints the roll / music state once a
# second (SOUND_PROBE); --sound-solo=roll|music|nomusic mutes the other parts for measurements
var _probe := false
var _probe_t := 0.0
var _solo := ""


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for n in SFX_NAMES:
		var p := SFX_DIR + n + ".wav"
		if ResourceLoader.exists(p):
			_sfx[n] = load(p)
	for i in 14:
		var pl := AudioStreamPlayer.new()
		add_child(pl)
		_players.append(pl)
	_music = AudioStreamPlayer.new()
	_music_b = AudioStreamPlayer.new()
	for m in [_music, _music_b]:
		add_child(m)
		_gain[m] = [0.0, 0.0, 1.0]
	for i in 4:
		var sp := AudioStreamPlayer.new()
		add_child(sp)
		_sting.append(sp)
		_sting_ui[sp] = false
	for i in 4:
		var vp := AudioStreamPlayer.new()
		add_child(vp)
		_voice_players.append(vp)
	_setup_ball()
	var args := OS.get_cmdline_user_args()
	_probe = args.has("--sound-probe")
	for a in args:
		if a.begins_with("--sound-solo="):
			_solo = a.substr(13)


func play(sfx_name: String, pitch := 1.0, volume_db := 0.0) -> void:
	var tbl_var := sfx_name + "_" + Settings.table_id
	if _sfx.has(tbl_var):
		sfx_name = tbl_var
	var s: AudioStream = _sfx.get(sfx_name)
	if s == null:
		return
	var pl := _players[_next]
	_next = (_next + 1) % _players.size()
	pl.stream = s
	pl.pitch_scale = pitch
	pl.volume_db = volume_db + _sfx_db() + _solo_db("sfx")
	pl.play()


## Starts (or keeps) a music piece; see the header for the names. Missing files are ignored.
func play_music(track: String) -> void:
	if track == _request and _music.playing:
		return
	_request = track
	_update_music()


func stop_music() -> void:
	_request = ""
	_pending = ""
	for m in [_music, _music_b]:
		m.stop()
		_gain[m] = [0.0, 0.0, 1.0]
	_music_name = ""


## Plays a named stinger (assets/audio/stingers/<name>.ogg); silently does nothing if missing.
func play_stinger(stinger_name: String) -> void:
	var s: AudioStream = _stinger(stinger_name)
	if s == null:
		return
	var sp := _sting[_sn]
	_sn = (_sn + 1) % _sting.size()
	var ui := UI_STINGERS.has(stinger_name)
	_sting_ui[sp] = ui
	sp.stream = s
	sp.volume_db = _stinger_db(ui) + _solo_db("sfx" if ui else "music")
	sp.play()
	if not ui:
		_duck_until = maxf(_duck_until, _time + s.get_length() * 0.85)


## Rolling sound of one ball, call every frame per ball (ball = 0..3). speed in px/s, surface
## "playfield" | "plastic" | "wire", pan -1..1 (ball x). Voices fade out when no longer fed.
func set_roll(speed: float, surface := "playfield", pan := 0.0, ball := 0) -> void:
	_roll_fed = _time
	_feed_roll(speed, surface, pan, ball)


## Ball one-shot: ramp_drop, ball_click, hit_flipper, hit_rubber, hit_metal; strength 0..1.
func roll_hit(hit_name: String, strength := 1.0, pan := 0.0) -> void:
	_hit_fed = _time
	_play_hit(hit_name, strength, pan)


## Re-reads the music / effects volumes from Settings (called by Settings.set_volume).
func refresh_volume() -> void:
	for sp in _sting:
		if sp.playing:
			sp.volume_db = _stinger_db(bool(_sting_ui[sp]))
	for vp in _voice_players:
		if vp.playing:
			vp.volume_db = _voice_db() + _solo_db("sfx")
	_apply_gains()


func has_stinger(stinger_name: String) -> bool:
	return _stinger(stinger_name) != null


## Plays a dynamic voice announcer callout (assets/audio/voice/<name>.wav).
## Automatically checks for table-specific variant first (<name>_<table_id>).
func play_voice(voice_name: String, pitch := 1.0, volume_db := 0.0) -> void:
	var tbl_var := voice_name + "_" + Settings.table_id
	if _has_voice(tbl_var):
		voice_name = tbl_var
	var s: AudioStream = _voice_stream(voice_name)
	if s == null:
		return
	var vp := _voice_players[_vn]
	_vn = (_vn + 1) % _voice_players.size()
	vp.stream = s
	vp.pitch_scale = pitch
	vp.volume_db = volume_db + _voice_db() + _solo_db("sfx")
	vp.play()
	_duck_until = maxf(_duck_until, _time + s.get_length() * 0.9)


func has_voice(voice_name: String) -> bool:
	var tbl_var := voice_name + "_" + Settings.table_id
	return _has_voice(tbl_var) or _has_voice(voice_name)


func _has_voice(voice_name: String) -> bool:
	return _voice_stream(voice_name) != null


func _voice_stream(voice_name: String) -> AudioStream:
	if not _voice.has(voice_name):
		var s: AudioStream = null
		for ext in [".wav", ".ogg"]:
			var p: String = VOICE_DIR + voice_name + ext
			if ResourceLoader.exists(p):
				s = load(p)
				break
		if s is AudioStreamWAV:
			(s as AudioStreamWAV).loop_mode = AudioStreamWAV.LOOP_DISABLED
		elif s is AudioStreamOggVorbis:
			(s as AudioStreamOggVorbis).loop = false
		_voice[voice_name] = s
	return _voice.get(voice_name)


func _voice_db() -> float:
	return linear_to_db(maxf(Settings.sfx_volume, 0.001)) + VOICE_DB


func current_music() -> String:
	return _music_name


# --- internals -------------------------------------------------------------------------------

func _process(delta: float) -> void:
	_time += delta
	if _request != "":
		_update_music()
	for m in [_music, _music_b]:
		var g: Array = _gain[m]
		if g[0] != g[1]:
			g[0] = move_toward(g[0], g[1], g[2] * delta)
			if g[0] <= 0.0 and g[1] <= 0.0:
				m.stop()
	var want := DUCK_DB if _time < _duck_until else 0.0
	want = minf(want, _state_duck())
	_duck = move_toward(_duck, want, (30.0 if want < _duck else 10.0) * delta)
	_apply_gains()
	if _time - _roll_fed > 0.25 or _time - _hit_fed > 0.25:
		_auto_ball(delta)
	_update_roll(delta)
	if _probe:
		_probe_t += delta
		if _probe_t >= 1.0:
			_probe_t = 0.0
			_print_probe()


## -80 dB for the parts muted by --sound-solo (diagnostics only).
func _solo_db(part: String) -> float:
	if _solo == "" or _solo == part or (_solo == "nomusic" and part != "music"):
		return 0.0
	return -80.0


func _print_probe() -> void:
	var vs: Array[String] = []
	for v in _roll:
		var pl := ""
		for n in v.players:
			var p: AudioStreamPlayer = v.players[n]
			if p.playing:
				pl += "%s:%.1fdB/p%.2f " % [n, p.volume_db, p.pitch_scale]
		if v.shimmer != null and (v.shimmer as AudioStreamPlayer).playing:
			pl += "shimmer:%.1fdB " % (v.shimmer as AudioStreamPlayer).volume_db
		vs.append("spd=%.0f s=%.2f lpf=%d %s%s" % [float(v.speed), float(v.s),
			int((AudioServer.get_bus_effect(int(v.bus), 0) as AudioEffectLowPassFilter).cutoff_hz), v.surface,
			(" [" + pl.strip_edges() + "]") if pl != "" else ""])
	print("[sndprobe] t=%.1f fed=%s auto=%s sfx=%.2f music=%.2f music_db=%.1f(%s) master_db=%.1f | %s" % [
		_time, "game" if _time - _roll_fed <= 0.25 else "auto", str(_time - _roll_fed > 0.25 or _time - _hit_fed > 0.25),
		Settings.sfx_volume, Settings.music_volume, _music.volume_db, "on" if _music.playing else "off",
		AudioServer.get_bus_volume_db(0), " | ".join(vs)])


func _update_music() -> void:
	# title intro finished (or about to): hand over to the menu theme
	if _music_name == "title" and not _intro_done and _music.stream != null:
		var ln := _music.stream.get_length()
		if not _music.playing or _music.get_playback_position() >= ln - FADE_S * 0.5:
			_intro_done = true
	var want := _resolve()
	if want == "":
		return
	if want == _music_name:
		_pending = ""
		if not _music.playing and want != "title":
			_switch(want, 0.05, 0.0)       # stream ended or was stopped: start again
		return
	if _pending != "":
		if want != _pending:
			_pending = ""
		else:
			var pos := _music.get_playback_position()
			if pos >= _pending_at - 0.008 or pos + 0.5 < _last_pos or not _music.playing:
				var off := float(_meta_of(want).get("loop_offset", 0.0))
				_switch(want, BAR_FADE_S, off)
			_last_pos = pos
			return
	if PAIRS.get(_music_name, "") == want and _music.playing:
		var bar := float(_meta_of(_music_name).get("bar_s", 0.0))
		if bar > 0.0:
			var pos := _music.get_playback_position()
			var nxt := ceilf((pos + 0.03) / bar) * bar
			_pending = want
			_pending_at = minf(nxt, _music.stream.get_length())
			_last_pos = pos
			return
	_switch(want, 0.05 if want == "title" or not _music.playing else FADE_S, 0.0)


## Which piece should be playing right now (request + what the current scene shows).
func _resolve() -> String:
	var r := _request
	var ctx := _ctx()
	if r == "title" or r == "menu":
		if r == "title" and not _intro_done and _has_music("title"):
			return "title"
		if ctx != null and str(ctx.get("page")) == "scores" and _has_music("hiscore"):
			return "hiscore"
		return "menu" if _has_music("menu") else "title"
	# Table music with seamless multiball pairing
	var base_m := r.replace("_multiball", "")
	var mb_m := base_m + "_multiball"
	if _has_music(base_m):
		if ctx != null:
			if str(ctx.get("state")) == "entry" and _has_music("hiscore"):
				return "hiscore"
			var t: Variant = ctx.get("table")
			if t is Object and is_instance_valid(t) and (t as Object).get("multiball") == true \
					and _has_music(mb_m):
				return mb_m
		return base_m
	return r


func _state_duck() -> float:
	if _request in ["title", "menu", "hiscore"]:
		return 0.0
	var ctx := _ctx()
	if ctx != null and str(ctx.get("state")) in ["match", "gameover", "final", "over"]:
		return STATE_DUCK_DB
	return 0.0


## The scene node that owns the game state: the current scene, or one of its children
## (tests add the game / menu under their own root).
func _ctx() -> Object:
	var tree := get_tree()
	if tree == null or tree.current_scene == null:
		return null
	var sc := tree.current_scene
	if "table" in sc or "page" in sc:
		return sc
	for c in sc.get_children():
		if "table" in c or "page" in c:
			return c
	return null


func _switch(track: String, fade: float, from_pos: float) -> void:
	_pending = ""
	var s := _load_music(track)
	if s == null:
		return
	var old := _music
	_music = _music_b
	_music_b = old
	_music.stream = s
	_gain[_music] = [0.0 if fade > 0.06 else 1.0, 1.0, 1.0 / maxf(fade, 0.01)]
	_gain[old] = [float(_gain[old][0]), 0.0, 1.0 / maxf(fade, 0.01)]
	if not old.playing:
		_gain[old] = [0.0, 0.0, 1.0]
	_music_name = track
	_apply_gains()
	_music.play(from_pos)


func _load_music(track: String) -> AudioStream:
	var stream: AudioStream = null
	for ext in [".ogg", ".wav"]:
		var p: String = MUSIC_DIR + track + ext
		if ResourceLoader.exists(p):
			stream = load(p)
			break
	if stream == null:
		return null
	# title.ogg is the one-shot intro when the menu theme exists; everything else loops
	var loop := not (track == "title" and _has_music("menu"))
	var off := float(_meta_of(track).get("loop_offset", 0.0))
	if stream is AudioStreamOggVorbis:
		var o := stream as AudioStreamOggVorbis
		o.loop = loop
		o.loop_offset = off
	elif stream is AudioStreamWAV:
		var w := stream as AudioStreamWAV
		w.loop_mode = AudioStreamWAV.LOOP_FORWARD if loop else AudioStreamWAV.LOOP_DISABLED
		w.loop_begin = int(off * w.mix_rate)
		w.loop_end = w.data.size() / (4 if w.stereo else 2)
	return stream


func _has_music(track: String) -> bool:
	return ResourceLoader.exists(MUSIC_DIR + track + ".ogg") or ResourceLoader.exists(MUSIC_DIR + track + ".wav")


func _meta_of(track: String) -> Dictionary:
	if not _meta.has(track):
		var d: Dictionary = {}
		var p := MUSIC_DIR + track + ".json"
		if FileAccess.file_exists(p):
			var v: Variant = JSON.parse_string(FileAccess.get_file_as_string(p))
			if v is Dictionary:
				d = v
		_meta[track] = d
	return _meta[track]


func _stinger(stinger_name: String) -> AudioStream:
	if not _streams.has(stinger_name):
		var s: AudioStream = null
		for ext in [".ogg", ".wav"]:
			var p: String = STINGER_DIR + stinger_name + ext
			if ResourceLoader.exists(p):
				s = load(p)
				break
		if s is AudioStreamOggVorbis:
			(s as AudioStreamOggVorbis).loop = false
		_streams[stinger_name] = s
	return _streams[stinger_name]


func _music_db() -> float:
	return linear_to_db(maxf(Settings.music_volume, 0.001)) + MUSIC_DB


func _sfx_db() -> float:
	return linear_to_db(maxf(Settings.sfx_volume, 0.001))


func _stinger_db(ui: bool) -> float:
	return _sfx_db() if ui else linear_to_db(maxf(Settings.music_volume, 0.001)) + STINGER_DB


func _apply_gains() -> void:
	var base := _music_db() + _duck
	for m in [_music, _music_b]:
		m.volume_db = base + linear_to_db(maxf(float(_gain[m][0]), 0.0001)) + _solo_db("music")


func _exit_tree() -> void:
	for p in get_children():
		if p is AudioStreamPlayer:
			p.stop()
			p.stream = null


# --- ball sounds -----------------------------------------------------------------------------

func _setup_ball() -> void:
	for n in ROLL_SURFACES + ["shimmer"]:
		var st := _ball_stream("roll_" + n)
		if st is AudioStreamOggVorbis:
			(st as AudioStreamOggVorbis).loop = true
	for s_name in ["engine_speedway", "thruster_launch_pad"]:
		var st := _ball_stream(s_name)
		if st is AudioStreamOggVorbis:
			(st as AudioStreamOggVorbis).loop = true
	for v in ROLL_VOICES:
		var bus := _make_bus("CT_Roll%d" % v, true)
		var voice := {"t": -10.0, "speed": 0.0, "s": 0.0, "surface": "playfield", "pan": 0.0,
			"bus": bus, "players": {}, "gain": {}, "detune": 1.0 + 0.035 * v, "shimmer": null, "sh_gain": 0.0,
			"engine": null, "engine_gain": 0.0, "thruster": null, "thruster_gain": 0.0}
		for n in ROLL_SURFACES:
			if _ball_stream("roll_" + n) == null:
				continue
			var p := AudioStreamPlayer.new()
			p.stream = _ball_stream("roll_" + n)
			p.bus = AudioServer.get_bus_name(bus)
			add_child(p)
			voice.players[n] = p
			voice.gain[n] = 0.0
		var sh := _ball_stream("roll_shimmer")
		if sh != null:
			var p := AudioStreamPlayer.new()
			p.stream = sh
			p.bus = AudioServer.get_bus_name(bus)
			add_child(p)
			voice.shimmer = p
		var eng := _ball_stream("engine_speedway")
		if eng != null:
			var p := AudioStreamPlayer.new()
			p.stream = eng
			p.bus = AudioServer.get_bus_name(bus)
			add_child(p)
			voice.engine = p
		var thr := _ball_stream("thruster_launch_pad")
		if thr != null:
			var p := AudioStreamPlayer.new()
			p.stream = thr
			p.bus = AudioServer.get_bus_name(bus)
			add_child(p)
			voice.thruster = p
		_roll.append(voice)
	for i in 3:
		var bus := _make_bus("CT_BallHit%d" % i, false)
		var p := AudioStreamPlayer.new()
		p.bus = AudioServer.get_bus_name(bus)
		add_child(p)
		_hit_players.append(p)
		_hit_panners.append(AudioServer.get_bus_effect(bus, 0) as AudioEffectPanner)


## Runtime bus (not saved to the project's bus layout): [low-pass] + panner -> Master.
func _make_bus(bus_name: String, with_lpf: bool) -> int:
	var idx := AudioServer.get_bus_index(bus_name)
	if idx < 0:
		idx = AudioServer.bus_count
		AudioServer.add_bus(idx)
		AudioServer.set_bus_name(idx, bus_name)
		AudioServer.set_bus_send(idx, "Master")
		if with_lpf:
			var lpf := AudioEffectLowPassFilter.new()
			lpf.cutoff_hz = 2000.0
			AudioServer.add_bus_effect(idx, lpf)
		AudioServer.add_bus_effect(idx, AudioEffectPanner.new())
	return idx


func _ball_stream(n: String) -> AudioStream:
	if not _ball_streams.has(n):
		var p := BALL_DIR + n + ".ogg"
		_ball_streams[n] = load(p) if ResourceLoader.exists(p) else null
	return _ball_streams[n]


func _feed_roll(speed: float, surface: String, pan: float, ball: int) -> void:
	if ball < 0 or ball >= _roll.size():
		return
	var v: Dictionary = _roll[ball]
	v.t = _time
	v.speed = maxf(speed, 0.0)
	v.surface = surface if v.players.has(surface) else "playfield"
	v.pan = clampf(pan, -1.0, 1.0)


func _update_roll(delta: float) -> void:
	var rolling := 0
	for v in _roll:
		if _time - float(v.t) < ROLL_HOLD_S and float(v.speed) > ROLL_MIN_SPEED:
			rolling += 1
	var multi := ROLL_MULTI_DB * maxf(rolling - 1, 0)
	var k := 1.0 - exp(-delta * 18.0)
	for v in _roll:
		var live := _time - float(v.t) < ROLL_HOLD_S and float(v.speed) > ROLL_MIN_SPEED
		var target := clampf(float(v.speed) / ROLL_REF_SPEED, 0.0, 1.4) if live else 0.0
		v.s = lerpf(float(v.s), target, k)
		if not live and float(v.s) < 0.02:
			v.s = 0.0   # release ends instead of an endless exponential tail
		var s: float = v.s
		var lvl := pow(minf(s, 1.2), 0.6)   # slow rolls stay audible too
		var bus: int = v.bus
		var lpf := AudioServer.get_bus_effect(bus, 0) as AudioEffectLowPassFilter
		var pn := AudioServer.get_bus_effect(bus, 1) as AudioEffectPanner
		# never darker than ~2 kHz: the granular mid band is what makes it read as a steel ball
		lpf.cutoff_hz = (2600.0 if v.surface == "wire" else 1800.0) + 11000.0 * pow(minf(s, 1.0), 1.3)
		pn.pan = lerpf(pn.pan, float(v.pan) * 0.8, k)
		for n in v.players:
			var want := lvl if n == v.surface else 0.0
			v.gain[n] = move_toward(float(v.gain[n]), want, delta * 7.0)
			var p: AudioStreamPlayer = v.players[n]
			var gl: float = v.gain[n]
			if gl > 0.002:
				if not p.playing:
					p.play(randf() * 2.0)
				p.volume_db = ROLL_DB + _sfx_db() + multi + linear_to_db(gl) + _solo_db("roll")
				p.pitch_scale = (0.85 + 0.35 * minf(s, 1.3)) * float(v.detune)
			elif p.playing:
				p.stop()
		# steel sheen grows with speed (less of it on the wire ramp, which rings by itself)
		if v.shimmer != null:
			var sp: AudioStreamPlayer = v.shimmer
			var sw := pow(clampf((s - 0.22) / 0.78, 0.0, 1.0), 1.2) * (0.45 if v.surface == "wire" else 1.0)
			v.sh_gain = move_toward(float(v.sh_gain), sw, delta * 6.0)
			var gs: float = v.sh_gain
			if gs > 0.002:
				if not sp.playing:
					sp.play(randf() * 2.0)
				sp.volume_db = SHIMMER_DB + _sfx_db() + multi + linear_to_db(gs) + _solo_db("roll")
				sp.pitch_scale = (0.9 + 0.2 * minf(s, 1.3)) * float(v.detune)
			elif sp.playing:
				sp.stop()
		# table-specific dynamic propulsion sounds (engine revving on speedway, rocket ion thrusters on launch pad)
		var is_speedway: bool = Settings.table_id == "copper_speedway"
		var is_launch: bool = Settings.table_id == "launch_pad"
		if v.engine != null:
			var ep: AudioStreamPlayer = v.engine
			var ew := (lvl * 1.1) if (live and is_speedway) else 0.0
			v.engine_gain = move_toward(float(v.engine_gain), ew, delta * 8.0)
			var eg: float = v.engine_gain
			if eg > 0.002:
				if not ep.playing:
					ep.play(randf() * 2.0)
				ep.volume_db = -5.0 + _sfx_db() + multi + linear_to_db(eg) + _solo_db("roll")
				ep.pitch_scale = clampf((0.72 + 0.95 * minf(s, 1.4)) * float(v.detune), 0.6, 2.2)
			elif ep.playing:
				ep.stop()
		if v.thruster != null:
			var tp: AudioStreamPlayer = v.thruster
			var tw := (lvl * 0.95) if (live and is_launch) else 0.0
			v.thruster_gain = move_toward(float(v.thruster_gain), tw, delta * 8.0)
			var tg: float = v.thruster_gain
			if tg > 0.002:
				if not tp.playing:
					tp.play(randf() * 2.0)
				tp.volume_db = -6.0 + _sfx_db() + multi + linear_to_db(tg) + _solo_db("roll")
				tp.pitch_scale = clampf((0.85 + 0.55 * minf(s, 1.4)) * float(v.detune), 0.6, 1.8)
			elif tp.playing:
				tp.stop()


func _play_hit(hit_name: String, strength: float, pan: float) -> void:
	var st := _ball_stream(hit_name)
	if st == null or not BALL_HITS.has(hit_name) or _hit_players.is_empty():
		return
	var p := _hit_players[_hn]
	_hit_panners[_hn].pan = clampf(pan, -1.0, 1.0) * 0.8
	_hn = (_hn + 1) % _hit_players.size()
	p.stream = st
	p.pitch_scale = randf_range(0.95, 1.05)
	p.volume_db = float(BALL_HITS[hit_name]) + _sfx_db() + linear_to_db(0.2 + 0.8 * clampf(strength, 0.0, 1.0)) + _solo_db("roll")
	p.play()


## Feeds set_roll()/hits from the current table while the game does not do it itself: speed from
## the ball's velocity (ramp speed on a ramp; silent while paused, held or in a hole), surface from
## the ramp it rides, a drop clack when a ramp is completed, clicks on ball-ball contact, impacts by material.
func _auto_ball(delta: float) -> void:
	var feed_roll := _time - _roll_fed > 0.25
	var feed_hit := _time - _hit_fed > 0.25
	var ctx := _ctx()
	var t: Object = null
	if ctx != null and "table" in ctx:
		var tv: Variant = ctx.get("table")
		if tv is Object and is_instance_valid(tv) and "balls" in tv:
			t = tv
	if t == null or get_tree().paused or delta <= 0.0:
		_ball_state.clear()
		return
	var balls: Array = t.get("balls")
	var gd: Variant = t.get("g")
	var w := 320.0
	var br := 7.5
	if gd is Dictionary:
		w = float((gd as Dictionary).get("size", [320, 640])[0])
		br = float((gd as Dictionary).get("ball_r", 7.5))
	var ramps: Array = t.get("ramps") if "ramps" in t else []
	var seen := {}
	for i in mini(balls.size(), ROLL_VOICES):
		var b: Object = balls[i]
		if b == null:
			continue
		seen[i] = true
		var pos: Vector2 = b.get("pos")
		var vel: Vector2 = b.get("vel")
		var ramp: int = int(b.get("ramp"))
		var rs: float = float(b.get("rs"))
		var still := float(b.get("held")) > 0.0 or str(b.get("hole")) != ""
		var pan := clampf(pos.x / w * 2.0 - 1.0, -1.0, 1.0)
		var st: Dictionary = _ball_state.get(i, {})
		var speed := absf(float(b.get("rv"))) if ramp >= 0 else vel.length()
		var surface := "playfield"
		if ramp >= 0 and ramp < ramps.size():
			surface = "wire" if str((ramps[ramp] as Dictionary).get("kind", "")) == "wire" else "plastic"
		if feed_roll:
			_feed_roll(0.0 if still else speed, surface, pan, i)
		if feed_hit and not st.is_empty() and not still and not bool(st.still):
			var cool: float = st.cool
			var was_ramp: int = st.ramp
			if was_ramp >= 0 and ramp < 0 and was_ramp < ramps.size():
				var ln := float((ramps[was_ramp] as Dictionary).get("len", 0.0))
				if ln > 0.0 and float(st.rs) > ln * 0.5:
					_play_hit("ramp_drop", clampf(speed / ROLL_REF_SPEED + 0.4, 0.4, 1.0), pan)
					cool = 0.15
			elif ramp < 0 and was_ramp < 0 and cool <= 0.0:
				var dv := (vel - (st.vel as Vector2)).length()
				if dv > HIT_MIN_DV:
					var hit := _impact_kind(t, pos, br)
					if hit != "":
						_play_hit(hit, clampf((dv - HIT_MIN_DV) / 700.0, 0.0, 1.0), pan)
						cool = 0.06
			st.cool = cool
		_ball_state[i] = {"pos": pos, "vel": vel, "ramp": ramp, "rs": rs, "still": still,
			"cool": maxf(float(st.get("cool", 0.0)) - delta, 0.0)}
	for i in _ball_state.keys():
		if not seen.has(i):
			_ball_state.erase(i)
	if feed_hit:
		_ball_clicks(balls, br, w)


func _ball_clicks(balls: Array, br: float, w: float) -> void:
	var n := mini(balls.size(), ROLL_VOICES)
	for i in n:
		for j in range(i + 1, n):
			var a: Object = balls[i]
			var b: Object = balls[j]
			if a == null or b == null or int(a.get("ramp")) != int(b.get("ramp")):
				continue
			var key := "c%d_%d" % [i, j]
			var d := (a.get("pos") as Vector2).distance_to(b.get("pos"))
			var touching := d < br * 2.0 + 1.0
			if touching and not bool(_ball_state.get(key, false)):
				var rv := ((a.get("vel") as Vector2) - (b.get("vel") as Vector2)).length()
				if rv > 40.0:
					var x := ((a.get("pos") as Vector2).x + (b.get("pos") as Vector2).x) * 0.5
					_play_hit("ball_click", clampf(rv / 500.0, 0.15, 1.0), clampf(x / w * 2.0 - 1.0, -1.0, 1.0))
			_ball_state[key] = touching


## What the ball just hit, from the table's geometry next to it ("" = something with its own
## sound already: bumpers, slings, targets, drops, gates).
func _impact_kind(t: Object, pos: Vector2, br: float) -> String:
	var reach := br + 5.0
	var fl: Variant = t.get("flippers")
	if fl is Array:
		for f in fl:
			var piv: Vector2 = f.get("pivot")
			if pos.distance_to(piv) < float(f.get("length")) + reach:
				return "hit_flipper"
	var circ: Variant = t.get("circ")
	if circ is Array:
		for c in circ:
			if pos.distance_to(c[0]) < float(c[1]) + reach:
				var m := str(c[2])
				return "hit_rubber" if m == "rubber" else ("hit_metal" if m == "wall" else "")
	var sa: Variant = t.get("seg_a")
	var sb: Variant = t.get("seg_b")
	var sm: Variant = t.get("seg_mat")
	if sa is PackedVector2Array and sb is PackedVector2Array and sm is Array:
		var best := reach
		var kind := ""
		for k in (sa as PackedVector2Array).size():
			var q := Geometry2D.get_closest_point_to_segment(pos, sa[k], sb[k])
			var d := pos.distance_to(q)
			if d < best:
				best = d
				var m := str(sm[k])
				kind = "hit_rubber" if m == "rubber" else ("hit_metal" if m == "wall" or m.begins_with("ramp") else "")
		return kind
	return ""
