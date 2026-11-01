class_name PinTable
extends Node2D
## MIDNIGHT FUNFAIR v2 - 320x1024 logical table, custom Amiga-style ball solver.
##
## Geometry comes from tools/mf_geometry.py (-> geometry.json); art from tools/build_table.py:
##   hd/     1280x4096 painted playfield + normal/specular maps, lit by 2D lights (style "modern")
##   pixel/  320x1024 32-colour OCS-palette art, nearest filtered, baked light (style "pixel")
## Both styles share the same geometry, physics and rules; Settings.style picks one and the
## visuals are rebuilt live (F9).
##
## Solver (docs/research, Pinball Fantasies / Slam Tilt): 200 Hz x 4 micro-steps, ball r 7.5,
## materials (wall e 0.33, rubber, fixed bumper/sling kicks, targets 0.25, dead when tilted),
## analytic tapered-capsule flippers with the ST motion profile, 1-D ramp paths.
## PACE: the ball runs in its own time (dt * pace) - Settings.tempo x a view factor - so gravity
## (g*pace^2) and every kick/launch speed (v*pace) scale consistently and all shots still reach
## the same places. Flippers move in real time (snappy) but act on the ball in ball time.

signal scored(points: int)
signal announce(text: String, sfx: String)
signal dmd_anim(kind: String, text: String)
signal drained
signal launched
signal tilt_changed(level: float, is_tilted: bool)
signal extra_ball
signal save_request(seconds: float)   # M11_MODES: ball save when a mode starts
signal video_mode_start(id: String)

const W := 320.0
const H := 640.0
const GRAV := 390.0
const SUB := 4
const VMAX := 950.0
const CELL := 32.0

const E_WALL := 0.33
const E_RUBBER := 0.75
const E_TARGET := 0.25
const E_DEAD := 0.125
const BUMPER_OUT := 240.0
const SLING_OUT := 330.0
const RAMP_UP_DECEL := 390.0
const RAMP_DOWN_ACC := 260.0
const FL_W0 := 10.66
const FL_ACC_UP := 350.0
const FL_ACC_DOWN := 248.0
const LAUNCH_MIN := 676.0
const LAUNCH_MAX := 977.0
## plunger zones (charge 0..1): soft | SKILL (measured 695-745 all reach the F-A-I-R lanes) | full
const SKILL_LO := 0.30
const SKILL_HI := 0.60
const CHARGE_RATE := 1.0
const METER_AT := [0.02, 0.30, 0.45, 0.60, 0.85]


class Ball:
	var pos := Vector2.ZERO
	var vel := Vector2.ZERO
	var prev := Vector2.ZERO
	var ramp := -1           # index of the ramp the ball rides, -1 = on the playfield
	var rs := 0.0
	var rv := 0.0
	var held := 0.0
	var hole := ""           # hole holding the ball
	var cool := 0.0
	var still := 0.0
	var sprite: Sprite2D
	var shadow: Sprite2D
	var contact: Sprite2D    # HD: tight contact shadow right under the ball
	var rot := Basis()       # rolling orientation (world -> ball), drives the chrome reflection
	var last := Vector2.INF
	var inside := {}         # rollover id -> bool


class Flipper:
	var pivot := Vector2.ZERO
	var length := 44.0
	var r0 := 7.0
	var r1 := 3.5
	var rest := 0.0
	var dir := 1.0
	var swing := 0.0
	var u := 0.0
	var w := 0.0
	var pressed := false
	var locked := false
	var left := true
	var small := false
	var sprite: Sprite2D

	func angle() -> float:
		return rest + dir * u

	func step(dt: float) -> void:
		if pressed and not locked:
			if u < swing:
				w = maxf(w, FL_W0) + FL_ACC_UP * dt
				u += w * dt
				if u >= swing:
					u = swing
					w = 0.0
		else:
			if u > 0.0:
				w = minf(w, 0.0) - FL_ACC_DOWN * dt
				u += w * dt
				if u <= 0.0:
					u = 0.0
					w = 0.0


var table_id := ""             # assets/tables/<id>/ (empty = Settings.table_id)
var dir := ""                  # res://assets/tables/<id>/
var rules                      # per-table rules (scripts/table/rules/<id>.gd), see table_rules.gd
var g: Dictionary
var seg_a := PackedVector2Array()
var seg_b := PackedVector2Array()
var seg_mat: Array[String] = []
var seg_one := PackedVector2Array()
var circ: Array = []
var movers: Array = []   # M11_MOVERS: [bumper index, base, offset, period, circ index]
var _mover_t := 0.0
var grid: Dictionary = {}
var ramps: Array = []          # dicts: path, s, len, apex, down, mouth_a, mouth_b, in, name
var holes: Dictionary = {}     # name -> dict
var light_pos: Dictionary = {}
var lane_rect := Rect2()
var plunger_rest := Vector2.ZERO
var plunger_y := 624.0

var balls: Array[Ball] = []
var flippers: Array[Flipper] = []
var style := "modern"
var pace := 0.85               # ball-time scale (set by game.gd from Settings.tempo + view)

# visuals (rebuilt per style)
var vis: Node2D
var lamp_layer: Node2D
var fx: Node2D
# M10_FX: GI pools round the toys, lamp bloom, drop shadows, ramp chaser bulbs (modern style)
var gi_nodes: Array = []          # [sprite, kind, idx, colour, phase]
var cap_shadows: Array = []
var fl_shadows: Array = []
var ramp_bulbs: Array = []        # [pos, ramp name, order]
var bulb_layer: Node2D            # own canvas item, redrawn only when a chase step changes
var _bulb_key := ""
var ramp_mat: ShaderMaterial
# M11_3D: 3D view of the modern style (Table3D), null in 2D / pixel / headless
const Table3DScript := preload("res://scripts/table/table3d.gd")
var t3d = null
var view3d := false
var bumper_caps: Array[Sprite2D] = []
var drop_spr: Array[Sprite2D] = []
var spinner_spr: Sprite2D
var plunger_spr: Sprite2D
var lamp_nodes: Dictionary = {}     # light name -> [core Sprite2D, halo Sprite2D]
var lamp_level: Dictionary = {}     # light name -> 0..1 smoothed
var flash_lights: Dictionary = {}   # name -> PointLight2D
var flash: Dictionary = {}          # name -> 0..1
var ball_mat: ShaderMaterial
var ball_tex: Texture2D
var sparks: Array = []              # [pos, vel, life, color]

var bumper_flash: Array[float] = []
var sling_flash := [0.0, 0.0]
var target_flash: Array[float] = []

# rules / state
var autopilot := false
var scripted := false                # tests: flippers driven by script_flip
var script_flip := [false, false]
var input_enabled := true
var charging := false
var charge := 0.0
var tilt := 0.0
var tilted := false
var shake := Vector2.ZERO
var _shake_t := 1.0
var _shake_dir := Vector2.ZERO
var _shake_amp := 3.0
var _pop_pos := Vector2(160, 320)
var _pops: Array = []
var multiplier := 1
var bumper_hits := 0
var ramp_hits := 0
var lanes := []                      # top lanes lit (sized from geometry)
var ride := []                       # standup targets lit
var stars := []                      # star rollovers lit
var drops: Array[bool] = []          # true = down
var drop_reset := {}                 # bank -> seconds until it pops back up
var ramps_to_lock := 0
var lock_lit := false
var locked := 0
var multiball := false
var super_lit := false
var kickback_lit := true
var save_lit := false
var extra_lit := false
var spinner_level := 1
var spin_v := 0.0
var spin_a := 0.0
# ---- toys v1 (per-table toys from geometry.json: turntables, magnets, extra spinners, VUK kickers)
var discs: Array = []                 # turntables: {pos, r, w (rad/s), a, name, spr}
var magnets: Array = []               # magnets: {pos, r, hold, kicks, speed, cool, name, glow}
var spinners: Array = []              # extra spinners: {pos, w, v, a, spr, name}
var toy_n := {}                       # toy name -> times triggered (tests, lamps)
var _ramp_ix := {}                    # ramp name -> index
const DISC_GRIP := 1.7                # turntable friction coupling (1/s); weaker than gravity: never traps
var shot_n := {}                     # shot -> times made (progress inserts)
var _chase := {}                     # shot -> time left of a chase animation
var _show := 0.0                     # whole-table light show time left
var _serve := 0                      # balls waiting to be auto-served (multiball)
var _serve_t := 0.0
var _time := 0.0
var frozen := false                 # still shots (Settings.still): no physics, lamps snap to state
var _auto_flip := 0.0
var _auto_side := 0
var _auto_t := 0.0
var _auto_hold := 0.6
var _auto_wait := -1.0               # autopilot: delay before flipping (varies the contact point = aim)
var _skill_t := 0.0                  # skill shot window after a plunger launch


## Directory of a table's assets.
static func dir_for(id: String) -> String:
	return "res://assets/tables/%s/" % id


func _ready() -> void:
	if table_id == "":
		table_id = Settings.table_id
	if not FileAccess.file_exists(dir_for(table_id) + "geometry.json"):
		table_id = "midnight_funfair"
	dir = dir_for(table_id)
	var rp := "res://scripts/table/rules/%s.gd" % table_id
	if not ResourceLoader.exists(rp):
		rp = "res://scripts/table/rules/table_rules.gd"
	rules = load(rp).new()
	rules.t = self
	var f := FileAccess.open(dir + "geometry.json", FileAccess.READ)
	g = JSON.parse_string(f.get_as_text())
	_load_geometry()
	for fd in g.flippers:
		var fl := Flipper.new()
		fl.pivot = Vector2(fd.pivot[0], fd.pivot[1])
		fl.length = fd.len
		fl.r0 = fd.r0
		fl.r1 = fd.r1
		fl.rest = deg_to_rad(fd.rest)
		fl.left = fd.side == "L"
		fl.dir = -1.0 if fl.left else 1.0
		fl.swing = absf(deg_to_rad(float(fd.up) - float(fd.rest)))
		fl.small = float(fd.len) < 40.0
		flippers.append(fl)
	for i in g.bumpers.size():
		bumper_flash.append(0.0)
	for i in g.drops.size():
		drops.append(false)
		drop_reset[g.drops[i].bank] = 0.0
	for i in g.targets.size():
		target_flash.append(0.0)
	for s in rules.shots():
		shot_n[s] = 0
	set_style(Settings.style)
	reset_game()


func _load_geometry() -> void:
	for s in g.segments:
		seg_a.append(Vector2(s[0], s[1]))
		seg_b.append(Vector2(s[2], s[3]))
		seg_mat.append(s[4])
		seg_one.append(Vector2(s[5], s[6]))
	for c in g.circles:
		circ.append([Vector2(c[0], c[1]), float(c[2]), c[3], c[4]])
	movers.clear()
	for m in rules.movers():
		var bi: int = int(m.bumper)
		var ci := -1
		for j in circ.size():
			if circ[j][3] == "bumper%d" % bi:
				ci = j
		movers.append([bi, Vector2(g.bumpers[bi][0], g.bumpers[bi][1]), Vector2(m.off[0], m.off[1]), float(m.period), ci])
	var pad := float(g.ball_r) + 4.0
	for i in seg_a.size():
		var lo := Vector2(minf(seg_a[i].x, seg_b[i].x), minf(seg_a[i].y, seg_b[i].y)) - Vector2(pad, pad)
		var hi := Vector2(maxf(seg_a[i].x, seg_b[i].x), maxf(seg_a[i].y, seg_b[i].y)) + Vector2(pad, pad)
		for cy in range(int(floor(lo.y / CELL)), int(floor(hi.y / CELL)) + 1):
			for cx in range(int(floor(lo.x / CELL)), int(floor(hi.x / CELL)) + 1):
				var k := Vector2i(cx, cy)
				if not grid.has(k):
					grid[k] = PackedInt32Array()
				var arr: PackedInt32Array = grid[k]
				arr.append(i)
				grid[k] = arr
	for r in g.ramps:
		var rp := {"name": r.name, "path": PackedVector2Array(), "s": PackedFloat32Array(),
			"apex": float(r.apex_s), "down": float(r.down_s), "kind": r.kind}
		for p in r.path:
			rp.path.append(Vector2(p[0], p[1]))
		for s in r.s:
			rp.s.append(s)
		rp["len"] = rp.s[rp.s.size() - 1]
		var m: Array = r.mouth
		rp["mouth_a"] = Vector2(m[0], m[1])
		rp["mouth_b"] = Vector2(m[2], m[3])
		rp["in"] = Vector2(r["in"][0], r["in"][1])
		rp["vuk"] = bool(r.get("vuk", false))
		rp["w"] = float(r.get("width", 18.0))
		var lp: Array = r.get("loop", [-1.0, -1.0])
		rp["loop"] = Vector2(lp[0], lp[1])      # loop-the-loop stretch: momentum carries the ball round
		_ramp_ix[r.name] = ramps.size()
		ramps.append(rp)
	for h in g.holes:
		holes[h.name] = h
	for d in g.get("discs", []):
		discs.append({"pos": Vector2(d.pos[0], d.pos[1]), "r": float(d.r), "w": float(d.omega), "a": 0.0,
			"name": str(d.name), "spr": null})
		toy_n[str(d.name)] = 0
	for m in g.get("magnets", []):
		magnets.append({"pos": Vector2(m.pos[0], m.pos[1]), "r": float(m.r), "hold": float(m.hold),
			"kicks": m.kicks, "speed": float(m.speed), "cool": 0.0, "name": str(m.name), "glow": 0.0})
		toy_n[str(m.name)] = 0
	for sp in g.get("spinners", []):
		spinners.append({"pos": Vector2(sp.pos[0], sp.pos[1]), "w": float(sp.w), "v": 0.0, "a": 0.0,
			"spr": null, "name": str(sp.name)})
		toy_n[str(sp.name)] = 0
	for k in g.lights:
		light_pos[k] = g.lights[k]
	var lr: Array = g.plunger.lane
	lane_rect = Rect2(lr[0], lr[1], lr[2], lr[3])
	plunger_rest = Vector2(g.plunger.rest[0], g.plunger.rest[1])
	for i in seg_a.size():
		if seg_mat[i] == "plunger":
			plunger_y = seg_a[i].y


# --- visuals -------------------------------------------------------------------

func _tex(name: String) -> Texture2D:
	# modern: CanvasTexture with normal + specular maps when present
	if style == "pixel":
		return load(dir + "pixel/" + name + ".png")
	var d: Texture2D = load(dir + "hd/" + name + ".png")
	var np := dir + "hd/" + name + "_n.png"
	if not ResourceLoader.exists(np):
		return d
	var ct := CanvasTexture.new()
	ct.diffuse_texture = d
	ct.normal_texture = load(np)
	var sp := dir + "hd/" + name + "_s.png"
	if ResourceLoader.exists(sp):
		ct.specular_texture = load(sp)
		ct.specular_shininess = 1.0
	else:
		ct.specular_color = Color(0.6, 0.6, 0.6)
		ct.specular_shininess = 0.75
	ct.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	return ct


func set_style(st: String) -> void:
	style = st if st in ["modern", "pixel"] else "modern"
	if vis:
		remove_child(vis)
		vis.queue_free()
	vis = Node2D.new()
	add_child(vis)
	var px := style == "pixel"
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST if px else CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	var k := 1.0 if px else 1.0 / float(g.art_scale)
	var amb := Color(1, 1, 1) if px else Color(0.96, 0.95, 0.98)
	bumper_caps.clear()
	drop_spr.clear()
	lamp_nodes.clear()
	flash_lights.clear()
	gi_nodes.clear()
	cap_shadows.clear()
	fl_shadows.clear()
	ramp_bulbs.clear()
	ramp_mat = null
	t3d = null
	view3d = not px and Settings.use_3d()

	if view3d:      # 3D view: the floor and all table objects are rendered by Table3D
		t3d = Table3DScript.new()
		t3d.t = self
		vis.add_child(t3d)
		t3d.build()
		vis.add_child(t3d.low_spr)
	else:
		var pf := Sprite2D.new()
		pf.texture = _tex("playfield")
		pf.centered = false
		pf.scale = Vector2(k, k)
		pf.self_modulate = amb
		vis.add_child(pf)

	# turntables (painted discs, rotate under the ball; drawn on the playfield, below lamps)
	for d in discs:
		d.spr = null
		if view3d:
			continue
		var ds := Sprite2D.new()
		ds.texture = _tex(d.name)
		ds.position = d.pos
		ds.rotation = d.a
		ds.scale = Vector2(k, k)
		ds.self_modulate = amb
		vis.add_child(ds)
		d.spr = ds

	# drop targets (pop-up faces, hidden when down)
	var dt := _tex("drop")
	for d in g.drops:
		if view3d:
			break
		var s := Sprite2D.new()
		s.texture = dt
		var a := Vector2(d.seg[0], d.seg[1])
		var b := Vector2(d.seg[2], d.seg[3])
		s.position = (a + b) * 0.5 + (b - a).orthogonal().normalized() * -1.0
		s.rotation = (b - a).angle()
		s.scale = Vector2(k, k)
		s.self_modulate = amb
		vis.add_child(s)
		drop_spr.append(s)

	lamp_layer = Node2D.new()
	vis.add_child(lamp_layer)
	if px:
		lamp_layer.draw.connect(_draw_lamps_pixel)
	else:
		_build_lamps_modern()
		lamp_layer.draw.connect(_draw_shadows_modern)
		_build_gi()

	var bt := _tex("bumper")
	for b in g.bumpers:
		if view3d:
			break
		var s := Sprite2D.new()
		s.texture = bt
		s.position = Vector2(b[0], b[1])
		s.scale = Vector2(k, k) * (float(b[2]) / 13.0)
		s.self_modulate = amb
		s.z_index = 1
		if not px:      # 2.5D: the raised cap throws a soft offset shadow
			var sh := Sprite2D.new()
			sh.texture = bt
			sh.position = s.position + Vector2(1.8, 2.6)
			sh.scale = s.scale * 1.06
			sh.modulate = Color(0.0, 0.0, 0.04, 0.42)
			sh.z_index = 1
			vis.add_child(sh)
			cap_shadows.append(sh)
		vis.add_child(s)
		bumper_caps.append(s)

	spinner_spr = null
	if g.has("spinner"):
		spinner_spr = Sprite2D.new()
		spinner_spr.texture = _tex("spinner")
		spinner_spr.position = Vector2(g.spinner.pos[0], g.spinner.pos[1])
		spinner_spr.scale = Vector2(k, k)
		spinner_spr.self_modulate = amb
		spinner_spr.z_index = 1
		vis.add_child(spinner_spr)
	for sp in spinners:
		var ss := Sprite2D.new()
		ss.texture = _tex("spinner")
		ss.position = sp.pos
		ss.scale = Vector2(k * sp.w / 26.0, k)
		ss.self_modulate = amb
		ss.z_index = 1
		vis.add_child(ss)
		sp.spr = ss

	plunger_spr = Sprite2D.new()
	plunger_spr.texture = _plunger_texture()
	plunger_spr.centered = false
	plunger_spr.position = Vector2(lane_rect.position.x + (lane_rect.size.x - 12.0) * 0.5, plunger_y)
	if not px:
		plunger_spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	vis.add_child(plunger_spr)

	for fl in flippers:
		fl.sprite = Sprite2D.new()
		var nm := "flipper_small" if fl.small else "flipper"
		fl.sprite.texture = _tex(nm)
		fl.sprite.centered = false
		var pad := 2.0
		var piv := Vector2(fl.r0 + pad, fl.r0 + pad)
		fl.sprite.offset = -piv / k
		fl.sprite.position = fl.pivot
		fl.sprite.scale = Vector2(k, k) * Vector2(1.0 if fl.left else -1.0, 1.0)
		fl.sprite.self_modulate = amb
		fl.sprite.z_index = 1
		fl.sprite.visible = not view3d     # 3D: the flipper is a mesh (the sprite keeps the angle)
		if not px and not view3d:
			var fs := Sprite2D.new()
			fs.texture = fl.sprite.texture
			fs.centered = false
			fs.offset = fl.sprite.offset
			fs.position = fl.pivot + Vector2(1.4, 2.2)
			fs.scale = fl.sprite.scale
			fs.modulate = Color(0.0, 0.0, 0.04, 0.40)
			fs.z_index = 1
			vis.add_child(fs)
			fl_shadows.append(fs)
		vis.add_child(fl.sprite)

	var rm := Sprite2D.new()
	if view3d:
		rm = t3d.high_spr       # 3D: the ramp decks layer (z 2), camera-synced by Table3D
	else:
		rm.texture = _tex("ramps")
		rm.centered = false
		rm.scale = Vector2(k, k)
		rm.self_modulate = amb
		rm.z_index = 2
	if not px and view3d:
		_build_ramp_bulbs()
	elif not px:      # clear plastic: refraction + sweeping glint
		ramp_mat = ShaderMaterial.new()
		ramp_mat.shader = load("res://shaders/plastic.gdshader")
		ramp_mat.set_shader_parameter("table_size", Vector2(W, H))
		rm.material = ramp_mat
		_build_ramp_bulbs()
	vis.add_child(rm)

	fx = Node2D.new()
	fx.z_index = 4
	var am := CanvasItemMaterial.new()
	am.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	am.light_mode = CanvasItemMaterial.LIGHT_MODE_UNSHADED
	fx.material = am
	fx.draw.connect(_draw_fx)
	vis.add_child(fx)
	if not ramp_bulbs.is_empty():
		bulb_layer = Node2D.new()
		bulb_layer.z_index = 4
		bulb_layer.material = am
		bulb_layer.draw.connect(_draw_ramp_bulbs)
		vis.add_child(bulb_layer)

	if px:
		ball_tex = load(dir + "pixel/ball.png")
		ball_mat = null
	else:
		ball_tex = load(dir + "hd/ball_mask.png")
		ball_mat = ShaderMaterial.new()
		ball_mat.shader = load("res://shaders/ball.gdshader")
		ball_mat.set_shader_parameter("env", load(dir + "hd/ball_env.png"))
		ball_mat.set_shader_parameter("pf", _ball_reflection_texture())
		ball_mat.set_shader_parameter("table_size", Vector2(W, H))
		ball_mat.set_shader_parameter("ball_r", float(g.ball_r))
		ball_mat.set_shader_parameter("quad", BALL_QUAD)
		_build_lights()
	for b in balls:
		_make_ball_sprite(b)
	apply_3d_options()


## 3D view options (shadows, light effects) without a rebuild; also hides the 2D GI pools when
## the 3D lights replace them.
func apply_3d_options() -> void:
	if t3d == null:
		return
	t3d.apply_options(Settings.shadows3d, Settings.lightfx)
	if not gi_nodes.is_empty():
		var gi: Node = gi_nodes[0][0].get_parent()
		if gi:
			gi.visible = Settings.lightfx == 0


## 2D camera -> 3D cameras (game.gd, every frame).
func sync_3d(pos: Vector2, zoom: float, px: Vector2i) -> void:
	if t3d:
		t3d.sync_view(pos, zoom, px)


func _build_lights() -> void:
	var lt: Texture2D = load(dir + "hd/light.png")
	# coloured flashers (energy driven by flash[])
	var fls: Dictionary = rules.flashers()
	for n in fls:
		var l := PointLight2D.new()
		l.texture = lt
		l.position = Vector2(fls[n][0][0], fls[n][0][1])
		l.texture_scale = float(fls[n][2]) * 2.0 / 128.0
		l.color = fls[n][1]
		l.energy = 0.0
		l.height = 40.0
		vis.add_child(l)
		flash_lights[n] = l
		if not flash.has(n):
			flash[n] = 0.0


func _build_lamps_modern() -> void:
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	add.light_mode = CanvasItemMaterial.LIGHT_MODE_UNSHADED
	lamp_layer.material = add
	var tex := {"round": load(dir + "hd/lamp_round.png"), "arrow": load(dir + "hd/lamp_arrow.png"),
		"star": load(dir + "hd/lamp_star.png")}
	var glow: Texture2D = load(dir + "hd/glow.png")
	var cols: Dictionary = g.light_colors
	for n in light_pos:
		var L: Dictionary = light_pos[n]
		var c: Array = cols[L.color]
		var col := Color8(c[0], c[1], c[2])
		var core := Sprite2D.new()
		core.texture = tex[L.kind]
		var sz: float = L.size
		var tw: float = core.texture.get_width()
		var span := sz * (2.0 / 0.62 if L.kind == "round" else 2.0 / 0.64)
		core.scale = Vector2.ONE * span / tw
		core.position = Vector2(L.pos[0], L.pos[1])
		core.rotation = deg_to_rad(float(L.dir)) if L.kind == "arrow" else 0.0
		core.modulate = Color(col, 0.0)
		core.use_parent_material = true
		lamp_layer.add_child(core)
		var halo := Sprite2D.new()
		halo.texture = glow
		halo.scale = Vector2.ONE * sz * 3.0 / glow.get_width()   # glow <= 1.5x insert
		halo.position = core.position
		halo.modulate = Color(col, 0.0)
		halo.use_parent_material = true
		lamp_layer.add_child(halo)
		var hot := Sprite2D.new()      # white-hot filament spot in the middle of a lit insert
		hot.texture = glow
		hot.scale = Vector2.ONE * sz * (1.1 if L.kind == "star" else 0.9) / glow.get_width()
		hot.position = core.position
		hot.modulate = Color(1, 1, 1, 0)
		hot.use_parent_material = true
		lamp_layer.add_child(hot)
		var bloom := Sprite2D.new()    # wide, faint bloom so lit inserts bleed light onto the paint
		bloom.texture = glow
		bloom.scale = Vector2.ONE * sz * 7.0 / glow.get_width()
		bloom.position = core.position
		bloom.modulate = Color(col, 0.0)
		bloom.use_parent_material = true
		lamp_layer.add_child(bloom)
		lamp_nodes[n] = [core, halo, col, hot, bloom]
		if not lamp_level.has(n):
			lamp_level[n] = 0.0


## The ball mirrors a softened copy of the playfield (1 px per table unit): no sparkle/aliasing
## in the squeezed rim reflection.
func _ball_reflection_texture() -> Texture2D:
	var src: Texture2D = load(dir + "hd/playfield.png")
	var im := src.get_image()
	if im == null:
		return src
	if im.is_compressed():
		im.decompress()
	im.resize(int(W), int(H), Image.INTERPOLATE_BILINEAR)
	im.resize(int(W / 2.0), int(H / 2.0), Image.INTERPOLATE_BILINEAR)
	return ImageTexture.create_from_image(im)


const BALL_QUAD := 1.6   # HD ball quad = 1.6 x the ball (room for the motion blur)


func _make_ball_sprite(b: Ball) -> void:
	if b.sprite:
		b.sprite.queue_free()
	if b.shadow:
		b.shadow.queue_free()
	b.sprite = Sprite2D.new()
	b.sprite.texture = ball_tex
	b.sprite.add_to_group("ct_ball")
	b.sprite.z_index = 3 if b.ramp >= 0 else 1
	if ball_mat:
		b.sprite.material = ball_mat.duplicate()
		b.sprite.scale = Vector2.ONE * 15.0 * BALL_QUAD / ball_tex.get_width()
		b.contact = Sprite2D.new()
		b.contact.texture = load(dir + "hd/glow.png")
		b.contact.modulate = Color(0.0, 0.0, 0.02, 0.85)
		b.contact.show_behind_parent = true
		b.sprite.add_child(b.contact)
		b.shadow = Sprite2D.new()
		b.shadow.texture = load(dir + "hd/glow.png")
		b.shadow.modulate = Color(0.0, 0.0, 0.03, 0.75)
		b.shadow.scale = Vector2.ONE * 19.0 / 128.0
		b.shadow.z_index = b.sprite.z_index
		vis.add_child(b.shadow)
	else:
		# pixel style: a hard-edged dark disc offset like the HD shadow (2.5D)
		b.shadow = Sprite2D.new()
		b.shadow.texture = _pixel_shadow_texture()
		b.shadow.modulate = Color(0.02, 0.0, 0.08, 0.55)
		b.shadow.z_index = b.sprite.z_index
		vis.add_child(b.shadow)
	vis.add_child(b.sprite)


var _px_shadow: Texture2D


func _pixel_shadow_texture() -> Texture2D:
	if _px_shadow:
		return _px_shadow
	var img := Image.create(15, 15, false, Image.FORMAT_RGBA8)
	for y in 15:
		for x in 15:
			var d := Vector2(x - 7, y - 7).length()
			img.set_pixel(x, y, Color(1, 1, 1, 1.0 if d <= 6.6 else 0.0))
	_px_shadow = ImageTexture.create_from_image(img)
	return _px_shadow


## 0..1 height of a ball on a ramp (matches the art's wall drop in build_table.py)
func ramp_elev(b: Ball) -> float:
	if b.ramp < 0:
		return 0.0
	var rp: Dictionary = ramps[b.ramp]
	var apex: float = rp.apex
	var down: float = rp.down
	var L: float = rp.len
	var e := 1.0
	if b.rs < apex:
		e = clampf(b.rs / maxf(apex, 1.0), 0.0, 1.0)
	elif b.rs >= down:
		e = clampf(1.0 - (b.rs - down) / maxf(L - down, 1.0), 0.0, 1.0)
	return e * e * (3.0 - 2.0 * e)


func _plunger_texture() -> Texture2D:
	var img := Image.create(12, 16, false, Image.FORMAT_RGBA8)
	for y in 16:
		for x in 12:
			var c := Color8(14, 8, 24, 0)
			if x > 0 and x < 11:
				if y < 4:
					c = Color8(230, 60, 60) if x > 1 and x < 10 else Color8(14, 8, 24)
					if y == 1 and x > 2 and x < 9:
						c = Color8(255, 170, 160)
				elif x >= 4 and x <= 7:
					c = Color8(200, 200, 220) if x < 6 else Color8(120, 120, 150)
					if (y % 3) == 0:
						c = Color8(70, 70, 90)
			img.set_pixel(x, y, c)
	return ImageTexture.create_from_image(img)


# --- public API -------------------------------------------------------------

func reset_game() -> void:
	multiplier = 1
	bumper_hits = 0
	ramp_hits = 0
	lanes = []
	lanes.resize(g.lanes.size())
	lanes.fill(false)
	ride = []
	ride.resize(g.targets.size())
	ride.fill(false)
	stars = []
	stars.resize(g.get("stars", []).size())
	stars.fill(false)
	for i in drops.size():
		drops[i] = false
	ramps_to_lock = 0
	lock_lit = false
	locked = 0
	super_lit = false
	kickback_lit = true
	extra_lit = false
	spinner_level = 1
	for k in shot_n:
		shot_n[k] = 0
	for k in toy_n:
		toy_n[k] = 0
	for m in magnets:
		m.cool = 0.0
	rules.modes_reset()
	rules.reset_game()
	reset_ball()


func reset_ball() -> void:
	for b in balls:
		_free_ball(b)
	balls.clear()
	multiball = false
	super_lit = false
	_serve = 0
	tilt = 0.0
	tilted = false
	for fl in flippers:
		fl.locked = false
	_spawn_ball(plunger_rest)
	rules.modes_ball()
	rules.reset_ball()
	tilt_changed.emit(tilt, tilted)


## Game over: remove every ball (nothing left in the shooter lane).
func clear_balls() -> void:
	for b in balls:
		_free_ball(b)
	balls.clear()
	_serve = 0
	multiball = false
	charging = false


func _free_ball(b: Ball) -> void:
	if b.sprite:
		b.sprite.queue_free()
	if b.shadow:
		b.shadow.queue_free()


func _spawn_ball(p: Vector2) -> Ball:
	var b := Ball.new()
	b.pos = p
	b.prev = p
	_make_ball_sprite(b)
	balls.append(b)
	return b


func lanes_lit() -> int:
	return lanes.count(true)


func targets_lit() -> int:
	return ride.count(true)


func focus_y() -> float:
	var y := 0.0
	for b in balls:
		if b.hole == "":
			y = maxf(y, b.pos.y)
	return y if balls.size() > 0 else H


func ball_speed() -> float:
	return balls[0].vel.length() if balls.size() > 0 else 0.0


func in_lane(b: Ball) -> bool:
	return lane_rect.has_point(b.pos) and b.pos.y > lane_rect.position.y + 4.0 and b.ramp < 0


func _in_lane(b: Ball) -> bool:
	return in_lane(b)


func nudge(dir: Vector2) -> void:
	if tilted:
		return
	for b in balls:
		if b.ramp < 0 and b.held <= 0.0:
			b.vel += dir * 117.0
	_shake_t = 0.0
	_shake_dir = -dir
	_shake_amp = 3.0
	tilt += 1.0
	if tilt >= 3.2:
		tilted = true
		for fl in flippers:
			fl.locked = true
		announce.emit("TILT", "tilt")
		dmd_anim.emit("tilt", "TILT")
	elif tilt >= 1.9:
		announce.emit("DANGER", "warn")
	tilt_changed.emit(tilt, tilted)


# --- frame --------------------------------------------------------------------

func _physics_process(delta: float) -> void:
	if frozen:
		return
	_controls(delta)
	var dt := delta / SUB
	var bdt := dt * pace
	_move_bumpers(delta)
	for i in SUB:
		for fl in flippers:
			fl.step(dt)
		for b in balls:
			_step_ball(b, bdt)
		for x in balls.size():
			for y in range(x + 1, balls.size()):
				_ball_ball(balls[x], balls[y])
	for b in balls.duplicate():
		if b.pos.y > float(g.drain_y):
			_free_ball(b)
			balls.erase(b)
			if balls.size() > 0 or _serve > 0:
				if multiball and balls.size() + _serve <= 1:
					multiball = false
					rules.on_multiball_over()
					announce.emit("MULTIBALL OVER", "drain")
			else:
				drained.emit()
	tilt = maxf(0.0, tilt - delta * 0.6)
	_timers(delta)


func _controls(delta: float) -> void:
	var l := false
	var r := false
	var plunge := false
	var lane_ball: Ball = null
	for b in balls:
		if in_lane(b):
			lane_ball = b
	if scripted:
		l = script_flip[0]
		r = script_flip[1]
	elif autopilot:
		var want_l := false
		var want_r := false
		for b in balls:
			if b.ramp >= 0 or b.vel.y < -150.0 or b.hole != "":
				continue
			for fl in flippers:
				var rel := b.pos - fl.pivot
				var side := rel.x * -fl.dir
				var reach := fl.length + 2.0
				if rel.y > -26.0 and rel.y < 20.0 and side > 3.0 and side < reach:
					if fl.left:
						want_l = true
					else:
						want_r = true
		if _auto_flip > 0.0:
			_auto_flip -= delta
			if _auto_flip <= 0.0:
				_auto_flip = -0.25
		elif _auto_flip < 0.0:
			_auto_flip = minf(0.0, _auto_flip + delta)
		elif want_l or want_r:
			# aim: wait a random moment so the ball meets the flipper at a different point
			if _auto_wait < 0.0:
				_auto_wait = randf_range(0.0, 0.11)
			_auto_wait -= delta
			if _auto_wait <= 0.0:
				_auto_wait = -1.0
				_auto_flip = randf_range(0.12, 0.22)
				_auto_side = (1 if want_l else 0) | (2 if want_r else 0)
		else:
			_auto_wait = -1.0
		var hold := _auto_flip > 0.0
		l = hold and (_auto_side & 1) != 0
		r = hold and (_auto_side & 2) != 0
		if lane_ball and lane_ball.vel.length() < 20.0:
			_auto_t += delta
			plunge = _auto_t < _auto_hold
			if _auto_t > _auto_hold + 0.4:
				_auto_t = 0.0
				# mix full plunges with soft skill shots into the F-A-I-R lanes
				_auto_hold = randf_range(0.7, 1.2) if randf() < 0.6 else randf_range(0.33, 0.57)
	elif input_enabled:
		l = Input.is_action_pressed(&"flip_left")
		r = Input.is_action_pressed(&"flip_right")
		plunge = Input.is_action_pressed(&"plunger")
		if Input.is_action_just_pressed(&"nudge_left"):
			nudge(Vector2(-1.0, -0.4))
		if Input.is_action_just_pressed(&"nudge_right"):
			nudge(Vector2(1.0, -0.4))
		if Input.is_action_just_pressed(&"nudge_up"):
			nudge(Vector2(0.0, -1.0))
	var was_l := flippers[0].pressed
	var was_r := flippers[1].pressed
	if l and not was_l:
		_rotate_lanes(-1)
		Sound.play("flipper")
	elif not l and was_l:
		Sound.play("flipper_down", 1.0, -6.0)
	if r and not was_r:
		_rotate_lanes(1)
		Sound.play("flipper", 1.06)
	elif not r and was_r:
		Sound.play("flipper_down", 1.06, -6.0)
	for fl in flippers:
		fl.pressed = l if fl.left else r

	var ready := lane_ball != null and lane_ball.pos.y > plunger_rest.y - 14.0 and lane_ball.vel.length() < 60.0
	if plunge and (ready or charging):
		var before := int(charge * 10.0)
		charging = true
		charge = minf(1.0, charge + delta * CHARGE_RATE)
		if int(charge * 10.0) != before:
			Sound.play("plunger", 0.8 + charge * 0.6, -6.0)
	elif charging:
		charging = false
		if ready:
			lane_ball.vel = Vector2(0.0, -launch_speed(charge, true))
			_skill_t = 4.0
			Sound.play("launch", 0.9 + charge * 0.2)
			launched.emit()
		charge = 0.0


## piecewise plunger curve: a wide flat middle band is the skill shot.
func launch_speed(c: float, jitter := false) -> float:
	if c < SKILL_LO:
		return lerpf(640.0, 690.0, c / SKILL_LO) + (randf() * 10.0 if jitter else 0.0)
	if c <= SKILL_HI:
		return lerpf(702.0, 738.0, (c - SKILL_LO) / (SKILL_HI - SKILL_LO)) + (randf_range(-3.0, 3.0) if jitter else 0.0)
	return lerpf(760.0, LAUNCH_MAX, (c - SKILL_HI) / (1.0 - SKILL_HI)) - (randf() * 15.0 if jitter else 0.0)



func _timers(delta: float) -> void:
	_skill_t = maxf(0.0, _skill_t - delta)
	for i in bumper_flash.size():
		bumper_flash[i] = maxf(0.0, bumper_flash[i] - delta * 5.0)
	for i in 2:
		sling_flash[i] = maxf(0.0, sling_flash[i] - delta * 5.0)
	for i in target_flash.size():
		target_flash[i] = maxf(0.0, target_flash[i] - delta * 3.0)
	for n in flash:
		flash[n] = maxf(0.0, flash[n] - delta * 3.2)
	_show = maxf(0.0, _show - delta)
	rules.mode_tick(delta)
	_tick_pops(delta)
	for n in _chase.keys():
		_chase[n] -= delta
		if _chase[n] <= 0.0:
			_chase.erase(n)
	# drop bank resets
	for bank in drop_reset:
		if drop_reset[bank] > 0.0:
			drop_reset[bank] -= delta
			if drop_reset[bank] <= 0.0:
				for i in g.drops.size():
					if g.drops[i].bank == bank:
						drops[i] = false
				Sound.play("target", 0.6, -4.0)
	# spinner
	if spin_v > 0.0:
		var before := floorf(spin_a)
		spin_a += spin_v * delta * pace
		spin_v = maxf(0.0, spin_v - delta * pace * (2.5 + spin_v * 0.6))
		if floorf(spin_a) != before:
			rules.on_spinner()
			Sound.play("rollover", 1.5, -10.0)
	for sp in spinners:
		if sp.v > 0.0:
			var b0 := floorf(sp.a)
			sp.a += sp.v * delta * pace
			sp.v = maxf(0.0, sp.v - delta * pace * (2.5 + sp.v * 0.6))
			if floorf(sp.a) != b0:
				rules.on_spinner()
				Sound.play("rollover", 1.7, -10.0)
	for m in magnets:
		m.cool = maxf(0.0, m.cool - delta * pace)
		m.glow = maxf(0.0, m.glow - delta * 1.5)
	# serve multiball balls one by one into the plunger lane (auto-launched)
	if _serve > 0:
		_serve_t -= delta
		if _serve_t <= 0.0:
			var free := true
			for b in balls:
				if in_lane(b):
					free = false
			if free:
				_serve -= 1
				_serve_t = 1.0
				var nb := _spawn_ball(plunger_rest)
				nb.vel = Vector2(0, -LAUNCH_MAX)
				Sound.play("launch", 1.1)
	# ball search
	for b in balls:
		if b.vel.length() < 8.0 and not in_lane(b) and not at_flipper(b) and b.held <= 0.0 and b.ramp < 0:
			b.still += delta
			if b.still > 3.0:
				b.still = 0.0
				if OS.get_cmdline_user_args().has("--probe"):
					print("[probe] ball search at (%.1f, %.1f)" % [b.pos.x, b.pos.y])
				b.vel = Vector2(randf_range(-1.0, 1.0) * 120.0, -200.0)
				announce.emit("BALL SEARCH", "post")
		else:
			b.still = 0.0


## A ball resting here is held by a flipper (cradle / upper flipper), not stuck: no BALL SEARCH.
func at_flipper(b: Ball) -> bool:
	if flippers.size() >= 2:
		var l := flippers[0].pivot
		var r := flippers[1].pivot
		if b.pos.y > minf(l.y, r.y) - 64.0 and b.pos.y < maxf(l.y, r.y) + 26.0 \
				and b.pos.x > l.x - 36.0 and b.pos.x < r.x + 36.0:
			return true
	for i in range(2, flippers.size()):
		if b.pos.distance_to(flippers[i].pivot) < 40.0:
			return true
	return false


# --- solver ---------------------------------------------------------------------

func _step_ball(b: Ball, dt: float) -> void:
	b.cool = maxf(0.0, b.cool - dt)
	b.prev = b.pos
	if b.held > 0.0:
		b.held -= dt
		if b.hole.begins_with("magnet:"):
			var mg: Dictionary = magnets[int(b.hole.substr(7))]
			b.pos = b.pos.lerp(mg.pos, 1.0 - exp(-14.0 * dt))
		if b.held <= 0.0:
			_release_hole(b)
		return
	if b.ramp >= 0:
		_step_ramp(b, dt)
		return
	var r := float(g.ball_r)
	b.vel.y += GRAV * dt
	b.vel.x = clampf(b.vel.x, -VMAX, VMAX)
	b.vel.y = clampf(b.vel.y, -VMAX * 1.2, VMAX)
	b.pos += b.vel * dt
	for d in discs:
		var off: Vector2 = b.pos - d.pos
		if off.length_squared() < d.r * d.r:
			var u := Vector2(-off.y, off.x) * float(d.w)
			b.vel += (u - b.vel) * minf(1.0, DISC_GRIP * dt)
	var cell := Vector2i(int(floor(b.pos.x / CELL)), int(floor(b.pos.y / CELL)))
	if grid.has(cell):
		for i in grid[cell]:
			var mat := seg_mat[i]
			var di := -1
			if mat.begins_with("drop"):
				di = int(mat.substr(4))
				if drops[di]:
					continue
			var a := seg_a[i]
			var ab := seg_b[i] - a
			var t := clampf((b.pos - a).dot(ab) / ab.length_squared(), 0.0, 1.0)
			var c := a + ab * t
			var d := b.pos - c
			var dl := d.length()
			if dl >= r or dl < 0.0001:
				continue
			var n := d / dl
			var one := seg_one[i]
			if mat.begins_with("ramp"):
				var ri := int(mat.substr(4))
				var rp: Dictionary = ramps[ri]
				var nin: Vector2 = rp["in"]
				var side := (b.pos - a).dot(nin)
				var vin := b.vel.dot(nin)
				if side > 0.0 or vin <= 0.0:
					continue
				if vin > 160.0 and not tilted:
					b.ramp = ri
					b.rs = 0.0
					b.rv = b.vel.length() * 0.92
					b.sprite.z_index = 3
					if b.shadow:
						b.shadow.z_index = 3
					Sound.play("rollover", 0.8)
					continue
				n = -nin
			elif one != Vector2.ZERO:
				if (b.pos - a).dot(one) <= 0.0:
					continue
				n = one
			b.pos = c + n * r
			_respond(b, n, mat, "", di)
	for ci in circ:
		var p: Vector2 = ci[0]
		var rr: float = ci[1] + r
		var d := b.pos - p
		var dl2 := d.length_squared()
		if dl2 >= rr * rr or dl2 < 0.0001:
			continue
		var dl := sqrt(dl2)
		var n := d / dl
		b.pos = p + n * rr
		_respond(b, n, ci[2], ci[3])
	for fl in flippers:
		_flipper_hit(b, fl, r)
	_events(b)


## M11_MOVERS: bumpers that slide slowly on a short track (collision, 2D sprites; 3D follows g.bumpers)
func _move_bumpers(delta: float) -> void:
	if movers.is_empty():
		return
	if not tilted:
		_mover_t += delta
	for m in movers:
		var q: Vector2 = m[1] + m[2] * (0.5 - 0.5 * cos(TAU * _mover_t / float(m[3])))
		var bi: int = m[0]
		g.bumpers[bi][0] = q.x
		g.bumpers[bi][1] = q.y
		if m[4] >= 0:
			circ[m[4]][0] = q
		if bi < bumper_caps.size():
			bumper_caps[bi].position = q
		if bi < cap_shadows.size():
			cap_shadows[bi].position = q + Vector2(1.8, 2.6)


func _respond(b: Ball, n: Vector2, mat: String, id := "", drop_i := -1) -> void:
	var vn := b.vel.dot(n)
	if vn >= 0.0:
		return
	var vt := b.vel - n * vn
	var vin := -vn
	var out := vin * E_WALL
	if tilted and (mat == "bumper" or mat.begins_with("sling")):
		out = vin * E_DEAD
	elif mat == "rubber":
		out = minf(vin * E_RUBBER, 200.0 + vin * 0.35)
		if vin > 120.0:
			Sound.play("post", 1.0, -8.0)
	elif mat == "bumper":
		out = maxf(BUMPER_OUT, vin * 0.8)
		var bi := int(id.substr(6))
		bumper_flash[bi] = 1.0
		bumper_hits += 1
		_skill_t = 0.0
		rules.on_bumper(bi, b)
		_burst(b.pos - n * float(g.ball_r), n, Color(1.0, 0.8, 0.4), 12)
		Sound.play("bumper", 0.9 + (bi % 5) * 0.05)
	elif mat.begins_with("sling"):
		if vin > 50.0:
			out = maxf(SLING_OUT, vin * 0.7)
			var si := int(mat.substr(5))
			sling_flash[si] = 1.0
			flash["sling%d" % si] = 1.0
			_burst(b.pos - n * float(g.ball_r), n, Color(1.0, 0.5, 0.9) if si == 0 else Color(0.5, 0.8, 1.0), 8)
			rules.on_sling(si)
			Sound.play("sling")
		else:
			out = vin * E_RUBBER
	elif mat.begins_with("target"):
		out = vin * E_TARGET
		_hit_target(int(mat.substr(6)))
	elif drop_i >= 0:
		out = vin * E_TARGET
		if vin > 40.0 and not tilted:
			_hit_drop(drop_i)
	elif mat == "plunger":
		out = vin * 0.1
	elif mat == "gate" or mat.begins_with("ramp"):
		out = vin * 0.3
	elif vin < 25.0:
		out = 0.0
	b.vel = vt * 0.995 + n * out


func _flipper_hit(b: Ball, fl: Flipper, r: float) -> void:
	var rel := b.pos - fl.pivot
	if rel.length_squared() > 60.0 * 60.0:
		return
	var ang := fl.angle()
	var dir := Vector2(cos(ang), sin(ang))
	var t := clampf(rel.dot(dir) / fl.length, 0.0, 1.0)
	var c := fl.pivot + dir * fl.length * t
	var rad := lerpf(fl.r0, fl.r1, t)
	var d := b.pos - c
	var dl := d.length()
	if dl >= r + rad or dl < 0.0001:
		return
	var n := d / dl
	b.pos = c + n * (r + rad)
	var q := c + n * rad - fl.pivot
	var omega := fl.dir * fl.w
	var vs := Vector2(-q.y, q.x) * omega
	var vrel := b.vel - vs
	var vn := vrel.dot(n)
	if vn >= 0.0:
		return
	var e := 0.39 if absf(fl.w) < 0.5 else 0.23
	if -vn < 30.0 and absf(fl.w) < 0.5:
		e = 0.0
	var vt := vrel - n * vn
	b.vel = vs + vt * 0.985 - n * vn * e


func _ball_ball(a: Ball, b: Ball) -> void:
	if (a.ramp >= 0) != (b.ramp >= 0) or a.held > 0.0 or b.held > 0.0:
		return
	var d := b.pos - a.pos
	var dl := d.length()
	var rr := float(g.ball_r) * 2.0
	if dl >= rr or dl < 0.001:
		return
	var n := d / dl
	var push := (rr - dl) * 0.5
	a.pos -= n * push
	b.pos += n * push
	var rv := (b.vel - a.vel).dot(n)
	if rv < 0.0:
		a.vel += n * rv * 0.95
		b.vel -= n * rv * 0.95
		Sound.play("post", 1.2, -6.0)


func _step_ramp(b: Ball, dt: float) -> void:
	var rp: Dictionary = ramps[b.ramp]
	var lpv: Vector2 = rp.loop
	if b.rs >= lpv.x and b.rs < lpv.y:
		b.rv -= 40.0 * dt
	elif b.rs < rp.apex:
		b.rv -= RAMP_UP_DECEL * dt
	elif b.rs < rp.down:
		b.rv -= 20.0 * dt
		if b.rv < 40.0 and b.rv >= 0.0:
			b.rv = 40.0
	else:
		b.rv += RAMP_DOWN_ACC * dt
	b.rv = minf(b.rv, 700.0)
	b.rs += b.rv * dt
	var path: PackedVector2Array = rp.path
	var ss: PackedFloat32Array = rp.s
	if b.rs <= 0.0:
		var nin: Vector2 = rp["in"]
		var ma: Vector2 = rp.mouth_a
		var mb: Vector2 = rp.mouth_b
		b.ramp = -1
		b.pos = (ma + mb) * 0.5 - nin * (float(g.ball_r) + 2.0)
		b.vel = -nin * absf(b.rv) + Vector2(randf_range(-20, 20), 0)
		b.sprite.z_index = 1
		if b.shadow:
			b.shadow.z_index = 1
		return
	if b.rs >= float(rp.len):
		var ri := b.ramp
		b.ramp = -1
		var n := path.size()
		var tan := (path[n - 1] - path[n - 3]).normalized()
		b.pos = path[n - 1]
		b.vel = tan * minf(b.rv, 420.0)
		b.sprite.z_index = 1
		if b.shadow:
			b.shadow.z_index = 1
		if rp.vuk:
			toy_n[rp.name] = int(toy_n.get(rp.name, 0)) + 1     # up-kicker habitrail: a toy, not a ramp shot
		else:
			_ramp_made(ri)
		return
	var lo := 0
	var hi := ss.size() - 1
	while hi - lo > 1:
		var mid := (lo + hi) >> 1
		if ss[mid] <= b.rs:
			lo = mid
		else:
			hi = mid
	var f := (b.rs - ss[lo]) / maxf(0.001, ss[hi] - ss[lo])
	var np := path[lo].lerp(path[hi], f)
	b.vel = (np - b.pos) / dt
	b.pos = np


# --- rules ----------------------------------------------------------------------

func _score(p: int) -> void:
	if not tilted:
		scored.emit(p)
		if p >= 25000:
			_popup(p)


# --- M11_MODES: effects helpers (flashers, camera kick, big point popups) ---------------------

func flash_all(v: float) -> void:
	for n in flash:
		flash[n] = maxf(flash[n], v)


func kick_shake(amp: float) -> void:
	if not Settings.get("shake") == false:
		_shake_t = 0.0
		_shake_dir = Vector2.from_angle(randf() * TAU)
		_shake_amp = 3.0 * amp


func _popup(p: int) -> void:
	if vis == null or DisplayServer.get_name() == "headless":
		return
	var s := str(p)
	var out := ""
	while s.length() > 3:
		out = "," + s.substr(s.length() - 3) + out
		s = s.substr(0, s.length() - 3)
	var big := p >= 250000
	var ls := LabelSettings.new()
	ls.font = ThemeDB.fallback_font
	ls.font_size = 26 if big else 18
	ls.font_color = Color(1.0, 0.85, 0.25) if big else Color(1, 1, 1)
	ls.outline_size = 6
	ls.outline_color = Color(0.05, 0.02, 0.1)
	var l := Label.new()
	l.text = s + out
	l.label_settings = ls
	l.z_index = 20
	l.size = Vector2(160, 40)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.position = Vector2(clampf(_pop_pos.x, 70.0, W - 70.0) - 80.0, _pop_pos.y - 44.0)
	l.pivot_offset = Vector2(80, 20)
	vis.add_child(l)
	if _pops.size() > 5:
		var o: Label = _pops.pop_front()[0]
		o.queue_free()
	_pops.append([l, 0.0])


func _tick_pops(delta: float) -> void:
	for e in _pops.duplicate():
		e[1] += delta
		var l: Label = e[0]
		var k: float = e[1]
		l.position.y -= delta * 22.0
		l.scale = Vector2.ONE * (1.0 + 0.35 * maxf(0.0, 1.0 - k * 6.0))
		l.modulate.a = clampf((1.4 - k) / 0.4, 0.0, 1.0)
		if k >= 1.4:
			l.queue_free()
			_pops.erase(e)


func _crossed(b: Ball, key: String, inside: bool) -> bool:
	var was: bool = b.inside.get(key, false)
	b.inside[key] = inside
	return inside and not was


func _events(b: Ball) -> void:
	_pop_pos = b.pos
	for i in g.lanes.size():
		var L: Dictionary = g.lanes[i]
		if _crossed(b, "lane%d" % i, b.pos.distance_to(Vector2(L.pos[0], L.pos[1])) < float(L.r) + 1.0):
			Sound.play("rollover", 1.0 + i * 0.08)
			rules.on_lane(i)
	for i in g.get("stars", []).size():
		var sp := Vector2(g.stars[i][0], g.stars[i][1])
		if _crossed(b, "star%d" % i, b.pos.distance_to(sp) < 7.0):
			Sound.play("rollover", 1.3)
			rules.on_star(i)
	# orbits: upward crossing of the detection line inside the orbit channel
	for o in g.get("orbits", []):
		var oy: float = o.y
		if b.prev.y > oy and b.pos.y <= oy and b.pos.x >= float(o.x[0]) and b.pos.x <= float(o.x[1]):
			Sound.play("rollover", 0.9)
			rules.on_orbit(o.name)
			rules.mode_event("lorbit" if o.name == "left" else "rorbit")
	# spinner
	if g.has("spinner"):
		var spn := Vector2(g.spinner.pos[0], g.spinner.pos[1])
		var hw := float(g.spinner.w) * 0.5
		if absf(b.pos.x - spn.x) < hw and (b.prev.y - spn.y) * (b.pos.y - spn.y) <= 0.0 and b.prev.y != b.pos.y:
			spin_v = maxf(spin_v, absf(b.vel.y) * 0.03)
			_score(200)
	for sp in spinners:
		var hw2 := float(sp.w) * 0.5
		if absf(b.pos.x - sp.pos.x) < hw2 and (b.prev.y - sp.pos.y) * (b.pos.y - sp.pos.y) <= 0.0 and b.prev.y != b.pos.y:
			sp.v = maxf(sp.v, absf(b.vel.y) * 0.03)
			toy_n[sp.name] = int(toy_n[sp.name]) + 1
			_score(200)
	for d in discs:
		if _crossed(b, "disc_" + d.name, b.pos.distance_to(d.pos) < float(d.r)):
			toy_n[d.name] = int(toy_n[d.name]) + 1
			rules.on_toy(d.name, b)
	# magnets: grab a passing ball, hold it, then throw it at a shot
	if b.cool <= 0.0 and not tilted:
		for mi in magnets.size():
			var m: Dictionary = magnets[mi]
			if m.cool <= 0.0 and b.pos.distance_to(m.pos) < float(m.r) and b.vel.length() < 560.0:
				b.vel = Vector2.ZERO
				b.held = float(m.hold)
				b.hole = "magnet:%d" % mi
				m.cool = float(m.hold) + 6.0
				m.glow = 1.0
				toy_n[m.name] = int(toy_n[m.name]) + 1
				Sound.play("target", 0.5, -4.0)
				rules.on_toy(m.name, b)
				return
	# holes
	if b.cool <= 0.0:
		for hn in holes:
			var h: Dictionary = holes[hn]
			var hp := Vector2(h.pos[0], h.pos[1])
			if b.pos.distance_to(hp) < float(h.r) - 1.0 and b.vel.length() < 480.0:
				b.pos = hp
				b.vel = Vector2.ZERO
				b.held = 0.9
				b.hole = hn
				Sound.play("target", 0.7)
				shot_n[hn] = int(shot_n.get(hn, 0)) + 1
				_chase[hn] = 0.8
				if not rules.mode_saucer(b, hn):
					rules.on_hole(b, hn)
					rules.mode_event(hn)
				break
	# kickback
	if not g.has("kickback"):
		return
	var kr: Array = g.kickback.rect
	if kickback_lit and not tilted and Rect2(kr[0], kr[1], kr[2], kr[3]).has_point(b.pos) and b.vel.y > 0.0:
		b.pos = Vector2(g.kickback.launch[0], g.kickback.launch[1])
		b.vel = Vector2(0.0, g.kickback.vy)
		kickback_lit = false
		_score(5000)
		_burst(b.pos, Vector2.UP, Color(0.5, 1.0, 0.5), 14)
		announce.emit("KICKBACK", "launch")


func _release_hole(b: Ball) -> void:
	if b.hole.begins_with("magnet:"):
		var m: Dictionary = magnets[int(b.hole.substr(7))]
		var ks: Array = m.kicks
		var kd: Array = ks[randi() % ks.size()]
		var kv := Vector2(kd[0], kd[1]).normalized()
		b.hole = ""
		b.pos = m.pos
		b.vel = kv * float(m.speed)
		b.cool = 0.6
		m.glow = 1.0
		_burst(b.pos, kv, Color(0.6, 0.85, 1.0), 16)
		Sound.play("launch", 1.4, -6.0)
		return
	var h: Dictionary = holes[b.hole]
	if h.has("vuk") and _ramp_ix.has(h.vuk):
		# vertical up-kicker: fires the ball straight into its habitrail
		var ri: int = _ramp_ix[h.vuk]
		b.hole = ""
		b.ramp = ri
		b.rs = 0.5
		b.rv = float(h.get("vuk_speed", 700.0))
		b.pos = ramps[ri].path[0]
		b.cool = 0.5
		if b.sprite:
			b.sprite.visible = true
			b.sprite.z_index = 3
		if b.shadow:
			b.shadow.z_index = 3
		var fk2: String = h.get("flash", "saucer")
		if flash.has(fk2):
			flash[fk2] = 1.0
		_burst(Vector2(h.pos[0], h.pos[1]), Vector2.UP, Color(1.0, 0.8, 0.5), 18)
		Sound.play("launch", 1.2)
		return
	if h.has("subway"):
		# travel under the playfield to the saucer
		var s: Dictionary = holes[h.subway]
		b.hole = h.subway
		b.pos = Vector2(s.pos[0], s.pos[1])
		b.held = 0.7
		if b.sprite:
			b.sprite.visible = true
		return
	var k := Vector2(h.kick[0], h.kick[1])
	b.pos = Vector2(h.pos[0], h.pos[1]) + k * 4.0
	b.vel = k * float(h.speed)
	b.cool = 0.5
	b.hole = ""
	var fk: String = h.get("flash", "saucer")
	if flash.has(fk):
		flash[fk] = 1.0
	_burst(b.pos, k, Color(1, 1, 1), 10)
	Sound.play("launch", 1.3, -4.0)












func _rotate_lanes(d: int) -> void:
	if lanes.size() < 2:
		return
	if d < 0:
		lanes.push_back(lanes.pop_front())
	else:
		lanes.push_front(lanes.pop_back())


func _hit_target(i: int) -> void:
	target_flash[i] = 1.0
	Sound.play("target", 1.0 + i * 0.05)
	rules.on_target(i)


func _hit_drop(i: int) -> void:
	drops[i] = true
	Sound.play("target", 0.85)
	rules.on_drop(i)
	var bank: String = g.drops[i].bank
	for j in g.drops.size():
		if g.drops[j].bank == bank and not drops[j]:
			return
	drop_reset[bank] = 1.6
	rules.on_bank(bank)
	rules.hurry_start()


func _ramp_made(ri: int) -> void:
	ramp_hits += 1
	var name: String = ramps[ri].name
	shot_n[name] = int(shot_n.get(name, 0)) + 1
	_chase[name] = 1.0
	if flash.has(name):
		flash[name] = 1.0
	rules.on_ramp(ri, name)
	rules.mode_event(name)


# --- drawing ----------------------------------------------------------------------

func _burst(p: Vector2, n: Vector2, col: Color, count: int) -> void:
	for i in count:
		var a := n.angle() + randf_range(-1.2, 1.2)
		var sp := randf_range(60.0, 220.0)
		sparks.append([p, Vector2(cos(a), sin(a)) * sp, randf_range(0.2, 0.45), col])
	if sparks.size() > 220:
		sparks = sparks.slice(sparks.size() - 220)


func _process(delta: float) -> void:
	if frozen:
		delta = 0.0
	_time += delta
	_shake_t += delta
	shake = _shake_dir * _shake_amp * sin(PI * clampf(_shake_t / 0.08, 0.0, 1.0)) if _shake_t < 0.08 else Vector2.ZERO
	var px := style == "pixel"
	for bi in balls.size():
		var b := balls[bi]
		Sound.set_roll(0.0 if b.held > 0.0 or b.hole != "" else (absf(b.rv) if b.ramp >= 0 else b.vel.length()), str(ramps[b.ramp].kind) if b.ramp >= 0 else "playfield", b.pos.x / W * 2.0 - 1.0, bi)
		b.sprite.position = b.pos.round() if px else b.pos
		if b.hole == "":
			b.sprite.visible = true
		# 2.5D: the ball grows a little and its shadow moves away/softens with ramp height
		var e := ramp_elev(b)
		var sc := 1.0 + 0.16 * e
		var base := (15.0 * BALL_QUAD / ball_tex.get_width()) if not px else 1.0
		b.sprite.scale = Vector2.ONE * base * sc
		if b.shadow:
			b.shadow.visible = b.sprite.visible and not (t3d != null and t3d.shadows)
			var off := Vector2(2.2, 3.2) + Vector2(4.6, 6.6) * e
			if px:
				b.shadow.position = (b.pos + off).round()
				b.shadow.modulate.a = 0.55 - 0.2 * e
			else:
				b.shadow.position = b.pos + off
				b.shadow.modulate.a = 0.75 - 0.32 * e
				b.shadow.scale = Vector2.ONE * 19.0 / 128.0 * (1.0 + 0.3 * e)
		_ball_look(b, delta, e, px)
	for fl in flippers:
		fl.sprite.rotation = fl.angle() if fl.left else fl.angle() - PI
	for i in fl_shadows.size():
		fl_shadows[i].rotation = flippers[i].sprite.rotation
	if t3d:
		t3d.update(delta)
	_update_gi()
	if ramp_mat:
		ramp_mat.set_shader_parameter("t", _time)
	var k := 1.0 if px else 1.0 / float(g.art_scale)
	for i in bumper_caps.size():
		var bs: float = g.bumpers[i][2] / 13.0
		var amb := Color(1, 1, 1) if px else Color(0.96, 0.95, 0.98)
		bumper_caps[i].self_modulate = amb.lerp(Color(2.2, 2.0, 1.4), bumper_flash[i])
		bumper_caps[i].scale = Vector2.ONE * k * bs * (1.0 + 0.08 * bumper_flash[i])
	for i in drop_spr.size():
		drop_spr[i].visible = not drops[i]
	if spinner_spr:
		spinner_spr.scale.y = k * absf(cos(spin_a * TAU))
	for sp in spinners:
		if sp.spr:
			sp.spr.scale.y = k * absf(cos(float(sp.a) * TAU))
	for d in discs:
		d.a = fmod(float(d.a) + float(d.w) * delta * pace, TAU)
		if d.spr:
			d.spr.rotation = d.a
	plunger_spr.position.y = plunger_y + charge * 8.0
	for n in flash_lights:
		flash_lights[n].energy = flash[n] * 1.5
	# bullet-time sparks
	for s in sparks:
		s[0] += s[1] * delta * pace
		s[1] *= 0.92
		s[2] -= delta
	sparks = sparks.filter(func(s: Array) -> bool: return s[2] > 0.0)
	if not px:
		_update_lamps_modern(delta)
	lamp_layer.queue_redraw()
	fx.queue_redraw()
	if bulb_layer:
		var key := ""
		for rn in _bulb_names():
			var ch := snappedf(clampf(float(_chase.get(rn, 0.0)), 0.0, 1.0), 0.125)
			key += "%d:%.3f," % [int(_time * (7.0 + 14.0 * ch)), ch]
		if key != _bulb_key:
			_bulb_key = key
			bulb_layer.queue_redraw()


## Chrome ball: rolling orientation, velocity (motion blur), nearby flasher light, contact shadow.
func _ball_look(b: Ball, delta: float, e: float, px: bool) -> void:
	var v := Vector2.ZERO
	if b.last != Vector2.INF and delta > 0.0:
		var d := b.pos - b.last
		if d.length() < 40.0:        # not a teleport (drain, kickout, saucer)
			v = d / delta
			# rolling without slipping: omega = z x v / r (z points from the table to the viewer)
			var ang := d.length() / float(g.ball_r)
			if ang > 1e-4:
				var axis := Vector3(-d.y, d.x, 0.0).normalized()
				b.rot = (b.rot * Basis(axis, ang)).orthonormalized()
	b.last = b.pos
	# M14_BALL: every nearby dynamic light mirrors in the steel: flashers (also the 3D light-show
	# pulse), bumper lights (always glowing, brighter when they fire) and lit inserts
	var cands: Array = []
	for n in flash_lights:
		var en: float = flash[n]
		if t3d and t3d._flash.has(n):
			en = maxf(en, (t3d._flash[n] as OmniLight3D).light_energy / 2.2)
		if en > 0.02:
			var l: PointLight2D = flash_lights[n]
			var rel := l.position - b.pos
			var w := en * 2.6 / (1.0 + rel.length_squared() / 9000.0)
			cands.append([w, Vector3(rel.x, rel.y, 26.0), l.color])
	for i in g.bumpers.size():
		var rel := Vector2(g.bumpers[i][0], g.bumpers[i][1]) - b.pos
		var w: float = (0.22 + bumper_flash[i] * 1.2) / (1.0 + rel.length_squared() / 3000.0)
		if w > 0.03:
			cands.append([w, Vector3(rel.x, rel.y, 16.0), Color(1.0, 0.86, 0.62)])
	for n in lamp_nodes:
		var lv: float = lamp_level.get(n, 0.0)
		if lv < 0.08:
			continue
		var lp: Array = light_pos[n].pos
		var rel := Vector2(lp[0], lp[1]) - b.pos
		var d2 := rel.length_squared()
		if d2 > 6400.0:
			continue
		var w := lv * 0.75 / (1.0 + d2 / 1200.0)
		cands.append([w, Vector3(rel.x, rel.y, 4.0), lamp_nodes[n][2]])
	cands.sort_custom(func(a: Array, c: Array) -> bool: return a[0] > c[0])
	if px:
		# pixel style keeps its dithered sprite; flashers just tint it a little
		var t := Color(1, 1, 1)
		for c in cands.slice(0, 2):
			t += (c[2] as Color) * minf(float(c[0]), 1.0) * 0.35
		b.sprite.modulate = t
		return
	var m := b.sprite.material as ShaderMaterial
	if m == null:
		return
	var lp := PackedVector4Array()
	var lc := PackedVector4Array()
	for i in 8:
		if i < cands.size():
			var c: Array = cands[i]
			var col: Color = c[2]
			var w: float = minf(float(c[0]), 2.6)
			lp.append(Vector4(c[1].x, c[1].y, c[1].z, 0.0))
			lc.append(Vector4(col.r * w, col.g * w, col.b * w, 0.0))
		else:
			lp.append(Vector4(0, 0, 50, 0))
			lc.append(Vector4.ZERO)
	m.set_shader_parameter("ball_pos", b.pos)
	m.set_shader_parameter("rot", b.rot.transposed())
	m.set_shader_parameter("vel", v)
	m.set_shader_parameter("elev", e)
	m.set_shader_parameter("lpos", lp)
	m.set_shader_parameter("lcol", lc)
	if b.contact:
		# tight dark contact patch, only directly under the ball contact point
		var s := b.sprite.scale.x
		b.contact.position = Vector2(0.3, 0.6) / s
		b.contact.scale = Vector2.ONE * (3.5 / 128.0) / s * (1.0 + 0.3 * e)
		b.contact.modulate.a = 0.75 * (1.0 - 0.7 * e)


func _blink(rate := 4.0) -> bool:
	return fmod(_time * rate, 1.0) < 0.5


## Lamp states: 0 off, 1 on, 2 slow blink, 3 fast blink, 4 dim (insert lit low)

## 8 light-chase patterns over every insert, from its position on the table.
## Lamp states: 0 off, 1 on, 2 slow blink, 3 fast blink, 4 dim (insert lit low)
func lamp_states() -> Dictionary:
	return rules.lamp_states()


func _apply_pattern(on: Dictionary, pat: int, t: float) -> void:
	var c := Vector2(160.0, 330.0)
	for k in light_pos:
		var p := Vector2(light_pos[k].pos[0], light_pos[k].pos[1])
		var lit := false
		match pat:
			0:   # sweep up
				lit = fposmod(H - p.y - t * 520.0, 640.0) < 70.0
			1:   # sweep down
				lit = fposmod(p.y - t * 420.0, 320.0) < 50.0
			2:   # rings out from the centre
				lit = fposmod(p.distance_to(c) - t * 180.0, 90.0) < 26.0
			3:   # radar beam
				lit = absf(angle_difference(Vector2(cos(t * 3.0), sin(t * 3.0)).angle(), (p - c).angle())) < 0.45
			4:   # left/right wipe
				lit = fposmod(p.x + (t * 300.0 if int(t / 2.0) % 2 == 0 else -t * 300.0), 160.0) < 50.0
			5:   # checkerboard blink
				lit = (int(p.x / 24.0) + int(p.y / 24.0) + int(t * 3.0)) % 2 == 0
			6:   # sparkle
				lit = (absi(hash(k)) + int(t * 10.0)) % 7 == 0
			7:   # colour groups in turn
				lit = int(t * 2.0) % 4 == absi(hash(light_pos[k].color)) % 4
		on[k] = 1 if lit else 0


func _lamp_target(st: int) -> float:
	match st:
		1:
			return 1.0
		2:
			return 1.0 if _blink() else 0.0
		3:
			return 1.0 if _blink(8.0) else 0.0
	return 0.0


func _update_lamps_modern(delta: float) -> void:
	var on := lamp_states()
	for n in lamp_nodes:
		var tgt := _lamp_target(on.get(n, 0))
		var lv: float = lamp_level[n]
		# incandescent bulb: fast on, slower off
		lv = tgt if frozen else move_toward(lv, tgt, delta * (18.0 if tgt > lv else 9.0))
		lamp_level[n] = lv
		var core: Sprite2D = lamp_nodes[n][0]
		var halo: Sprite2D = lamp_nodes[n][1]
		var col: Color = lamp_nodes[n][2]
		core.modulate = Color(col.r * 1.6, col.g * 1.6, col.b * 1.6, lv)
		halo.modulate = Color(col.r, col.g, col.b, lv * 0.55)
		lamp_nodes[n][3].modulate = Color(1.0, 1.0, 0.92, lv * 0.85)
		lamp_nodes[n][4].modulate = Color(col.r, col.g, col.b, lv * 0.16)


func _draw_shadows_modern() -> void:
	pass


func _draw_fx() -> void:
	var px := style == "pixel"
	for s in sparks:
		var c: Color = s[3]
		var a: float = clampf(float(s[2]) / 0.3, 0.0, 1.0)
		var p: Vector2 = s[0]
		var v: Vector2 = s[1]
		if px:
			fx.draw_rect(Rect2(p.round(), Vector2(1, 1)), Color(c, a))
		else:
			fx.draw_line(p, p - v * 0.025, Color(c.r * 1.5, c.g * 1.5, c.b * 1.5, a), 0.8)
	# sling flash
	for i in 2:
		if sling_flash[i] > 0.0:
			var tri: Array = g.slings[i]
			var pts := PackedVector2Array()
			for q in tri:
				pts.append(Vector2(q[0], q[1]))
			fx.draw_colored_polygon(pts, Color(1, 0.8, 1, 0.35 * sling_flash[i]))
	# turntables: chasing rim bulbs (rotate with the platform)
	for d in discs:
		var dp: Vector2 = d.pos
		var dr: float = float(d.r) - 1.4
		var nb := 30
		var ph := int(_time * 9.0)
		for i in nb:
			if (i + ph) % 3 != 0:
				continue
			var a := float(d.a) + i * TAU / nb
			var q := dp + Vector2(cos(a), sin(a)) * dr
			if px:
				fx.draw_rect(Rect2(q.round(), Vector2(1, 1)), Color(1.0, 0.85, 0.4, 0.9))
			else:
				fx.draw_circle(q, 1.6, Color(1.0, 0.8, 0.35, 0.55))
				fx.draw_circle(q, 0.8, Color(1.0, 0.95, 0.8, 0.9))
	# magnets: crackling field while a ball is held, pulse when it lets go
	for mi in magnets.size():
		var m: Dictionary = magnets[mi]
		var held_here := false
		for b in balls:
			if b.hole == "magnet:%d" % mi:
				held_here = true
		var gl := 1.0 if held_here else float(m.glow)
		var mp: Vector2 = m.pos
		var mr: float = m.r
		if gl <= 0.0:
			if float(m.cool) <= 0.0 and not px:     # armed: slow blue breathing ring
				fx.draw_arc(mp, mr + 3.0, 0, TAU, 40, Color(0.35, 0.65, 1.0, 0.22 + 0.18 * sin(_time * 4.0)), 1.4)
			continue
		if px:
			fx.draw_arc(mp.round(), mr, 0, TAU, 16, Color(0.5, 0.8, 1.0, gl), 1.0)
			continue
		fx.draw_circle(mp, mr + 2.0, Color(0.3, 0.55, 1.0, 0.18 * gl))
		for k2 in 5:
			var a0 := _time * 7.0 + k2 * TAU / 5.0
			var pts := PackedVector2Array()
			for j in 6:
				var rr := mr * (1.0 - j / 6.0)
				var aj := a0 + j * 0.5 + sin(_time * 40.0 + j * 3.0 + k2) * 0.35
				pts.append(mp + Vector2(cos(aj), sin(aj)) * rr)
			fx.draw_polyline(pts, Color(0.55, 0.8, 1.0, 0.8 * gl), 0.7)
	# lit bumper caps glow + an expanding hit ring
	for i in g.bumpers.size():
		if bumper_flash[i] > 0.0 and not px:
			var bp := Vector2(g.bumpers[i][0], g.bumpers[i][1])
			var f: float = bumper_flash[i]
			var br := float(g.bumpers[i][2])
			fx.draw_circle(bp, br + 4.0, Color(1.0, 0.7, 0.4, 0.25 * f))
			fx.draw_arc(bp, br + 2.0 + (1.0 - f) * 12.0, 0, TAU, 48, Color(1.0, 0.85, 0.55, 0.75 * f), 1.0 + 1.6 * f)


func _draw_lamps_pixel() -> void:
	var on := lamp_states()
	var cols: Dictionary = g.light_colors
	for k in light_pos:
		var st: int = on.get(k, 0)
		if _lamp_target(st) <= 0.0:
			continue
		var L: Dictionary = light_pos[k]
		var c: Array = cols[L.color]
		var col := Color8(c[0], c[1], c[2])
		var p := Vector2(L.pos[0], L.pos[1])
		var s: float = L.size
		match L.kind:
			"round":
				lamp_layer.draw_circle(p, s + 1.5, Color(col, 0.35))
				lamp_layer.draw_circle(p, s, col)
				lamp_layer.draw_rect(Rect2(p + Vector2(-s * 0.5, -s * 0.6), Vector2(1, 1)), Color.WHITE)
			"arrow":
				lamp_layer.draw_colored_polygon(_arrow_pts(p, s, deg_to_rad(float(L.dir))), col)
				lamp_layer.draw_rect(Rect2(p.round() - Vector2(1, 1), Vector2(2, 2)), Color.WHITE)
			"star":
				var pts := PackedVector2Array()
				for i in 10:
					var rr := s if i % 2 == 0 else s * 0.45
					var a := -PI / 2.0 + i * PI / 5.0
					pts.append(p + Vector2(cos(a), sin(a)) * rr)
				lamp_layer.draw_colored_polygon(pts, col)
				lamp_layer.draw_rect(Rect2(p.round() - Vector2(1, 1), Vector2(2, 2)), Color.WHITE)
	for b in balls:
		if b.sprite.visible:
			var off := Vector2(6, 7) if b.ramp >= 0 else Vector2(3, 3)
			lamp_layer.draw_circle(b.pos.round() + off, 6.5, Color(0, 0, 0.05, 0.45))


func _arrow_pts(p: Vector2, s: float, a: float) -> PackedVector2Array:
	var f := Vector2(cos(a), sin(a))
	var q := Vector2(-f.y, f.x)
	return PackedVector2Array([p + f * s * 1.3, p + q * s * 0.9, p + q * s * 0.35, p + q * s * 0.35 - f * s,
		p - q * s * 0.35 - f * s, p - q * s * 0.35, p - q * s * 0.9])


# ---------------------------------------------------------------- M10 modern-style light effects
## GI: warm light pools under/around the toys (additive), breathing slowly, flaring on hits.
func _build_gi() -> void:
	var gi := Node2D.new()
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	m.light_mode = CanvasItemMaterial.LIGHT_MODE_UNSHADED
	gi.material = m
	vis.add_child(gi)
	var glow: Texture2D = load(dir + "hd/glow.png")
	var spots: Array = []
	for i in g.bumpers.size():
		var b: Array = g.bumpers[i]
		spots.append([Vector2(b[0], b[1]), float(b[2]) * 2.8, Color(1.0, 0.78, 0.5), "bumper", i])
	for d in discs:
		spots.append([d.pos, float(d.r) * 1.35, Color(1.0, 0.86, 0.62), "disc", 0])
	for sp in spinners:
		spots.append([sp.pos, float(sp.w) * 1.3, Color(0.7, 0.85, 1.0), "spin", 0])
	for mi in magnets.size():
		spots.append([magnets[mi].pos, float(magnets[mi].r) * 2.6, Color(0.5, 0.72, 1.0), "mag", mi])
	for i in mini(2, g.slings.size()):
		var c := Vector2.ZERO
		for q in g.slings[i]:
			c += Vector2(q[0], q[1])
		spots.append([c / float(g.slings[i].size()), 30.0, Color(1.0, 0.8, 0.95), "sling", i])
	if g.has("tower"):
		spots.append([Vector2(g.tower[0], g.tower[1]), 46.0, Color(1.0, 0.72, 0.45), "tower", 0])
	for k2 in spots.size():
		var sp2: Array = spots[k2]
		var s := Sprite2D.new()
		s.texture = glow
		s.position = sp2[0]
		s.scale = Vector2.ONE * float(sp2[1]) * 2.0 / glow.get_width()
		s.modulate = Color(sp2[2], 0.0)
		s.use_parent_material = true
		gi.add_child(s)
		gi_nodes.append([s, sp2[3], sp2[4], sp2[2], float(k2) * 1.7])


func _update_gi() -> void:
	for gn in gi_nodes:
		var a := 0.13 + 0.035 * sin(_time * 1.6 + float(gn[4]))
		var i: int = gn[2]
		match gn[1]:
			"bumper":
				a += 0.5 * bumper_flash[i]
			"sling":
				a += 0.45 * float(sling_flash[i])
			"mag":
				a += 0.35 * float(magnets[i].glow)
			"tower":
				a += 0.25 * clampf(float(flash.get("tower", 0.0)), 0.0, 1.0)
		var s: Sprite2D = gn[0]
		s.modulate = Color(gn[3], a)


## Chaser bulbs along both edges of every plastic ramp; they run faster and flare after a shot.
func _build_ramp_bulbs() -> void:
	for rp in ramps:
		if str(rp.kind) != "plastic":
			continue
		var path: PackedVector2Array = rp.path
		var off := float(rp.w) * 0.5 + 1.0
		var next := 12.0
		var order := 0
		for j in range(1, path.size()):
			if rp.s[j] < next or rp.s[j] > float(rp.len) - 10.0:
				continue
			next += 15.0
			var tg := (path[j] - path[j - 1]).normalized()
			var nn := tg.orthogonal()
			ramp_bulbs.append([path[j] + nn * off, rp.name, order])
			ramp_bulbs.append([path[j] - nn * off, rp.name, order])
			order += 1


var _bulb_name_list: Array = []
func _bulb_names() -> Array:
	if _bulb_name_list.is_empty():
		for rb in ramp_bulbs:
			if not _bulb_name_list.has(rb[1]):
				_bulb_name_list.append(rb[1])
	return _bulb_name_list


func _draw_ramp_bulbs() -> void:
	for rb in ramp_bulbs:
		var ch := snappedf(clampf(float(_chase.get(rb[1], 0.0)), 0.0, 1.0), 0.125)
		var ph := int(_time * (7.0 + 14.0 * ch))
		var lit := (int(rb[2]) + ph) % 4 == 0
		var a := 0.75 if lit else 0.14
		a = maxf(a, ch * 0.9)
		var p: Vector2 = rb[0]
		bulb_layer.draw_circle(p, 2.0, Color(1.0, 0.7, 0.3, a * 0.35))
		bulb_layer.draw_circle(p, 0.85, Color(1.0, 0.95, 0.8, a))
