extends Node
## 3D view of the modern style (Settings.use_3d): the table objects are real procedural 3D models
## with a sun shadow, coloured omni lights and glow, seen by an orthographic top-down camera that
## is synced 1:1 with the 2D camera. Physics, the ball, lamps and fx stay 2D.
##
## Two SubViewports share one World3D:
##   low  (layer 1): painted floor, bumpers, posts, rubbers, rails, slings, flippers, drops,
##        targets, carousel, ramp supports, lights  -> Sprite2D z 0 (replaces the playfield)
##   high (layer 2): ramp decks + the helter tower dome -> Sprite2D z 2 (replaces the ramps
##        sprite), so the 2D ball (z 1 under a ramp, z 3 on it) is occluded exactly as before.
## Both sprites are unshaded (the 3D lights already lit them) and follow the 2D camera.

const RAMP_H := 30.0          # deck height at the top of a ramp (table units)
const PAD := 9.0              # ribbon half width = ramp width / 2 + PAD (bake_ramp_owner.py)
const TOWER_R := 15.0
const CAM_Y := 200.0
const CELL := 80.0            # static meshes are merged per CELL x CELL (per-object light limit)
const TILE := 40.0            # floor tiles
const SUN_DIR := Vector3(0.42, -1.0, 0.55)
const TINT := Vector3(0.96, 0.95, 0.98)

var t                         # PinTable
var low: SubViewport
var high: SubViewport
var low_spr: Sprite2D
var high_spr: Sprite2D
var root: Node3D
var cam_lo: Camera3D
var cam_hi: Camera3D
var sun: DirectionalLight3D
var env_lo: Environment
var lightfx := 2
var shadows := true

var _mats: Dictionary = {}
var _st: Dictionary = {}      # "mat|cx|cy" -> [SurfaceTool, mat key, layer]
var _fl: Array = []           # Node3D per flipper
var _bump: Array = []         # [ring MeshInstance3D, cap ShaderMaterial, OmniLight3D, base y]
var _drops: Array = []        # Node3D per drop
var _drop_y: Array = []
var _targets: Array = []      # ShaderMaterial / StandardMaterial3D per standup
var _discs: Array = []        # Node3D per turntable
var _ball_sh: Array = []      # shadow-only spheres
var _flash: Dictionary = {}   # flasher name -> OmniLight3D
var _inserts: Dictionary = {} # light name -> [OmniLight3D, colour]
var _ramp_mats: Array = []
var _pf_tex: Texture2D
var _owner: Texture2D
var _size := Vector2i(320, 640)
var _time := 0.0


# --- build -----------------------------------------------------------------------------------

func build() -> void:
	var dir: String = t.dir
	_pf_tex = load(dir + "hd/playfield.png")
	_owner = _load_tex(dir + "hd/ramp_owner.png")
	var world := World3D.new()
	root = Node3D.new()
	low = _viewport(world, 1)
	high = _viewport(world, 2)
	add_child(low)
	add_child(high)
	low.add_child(root)
	cam_lo = _camera(1)
	cam_hi = _camera(2)
	low.add_child(cam_lo)
	high.add_child(cam_hi)
	_environment()
	_build_floor()
	_build_rails()
	_build_posts()
	_build_slings()
	_build_bumpers()
	_build_flippers()
	_build_drops_targets()
	_build_discs()
	_build_misc()
	_build_ramps()
	_build_lights()
	_commit()
	low_spr = _sprite(low, 0, false)
	high_spr = _sprite(high, 2, true)
	sync_view(Vector2(t.W * 0.5, t.H * 0.5), 1.0, Vector2i(int(t.W), int(t.H)))
	apply_options(Settings.shadows3d, Settings.lightfx)


func _load_tex(p: String) -> Texture2D:
	if ResourceLoader.exists(p):
		return load(p)
	var img := Image.load_from_file(ProjectSettings.globalize_path(p))
	if img == null:
		return null
	return ImageTexture.create_from_image(img)


func _viewport(world: World3D, layer: int) -> SubViewport:
	var v := SubViewport.new()
	v.world_3d = world
	v.own_world_3d = false
	v.transparent_bg = true
	v.msaa_3d = Viewport.MSAA_4X
	v.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	v.positional_shadow_atlas_size = 0
	v.size = _size
	v.name = "View3D_%d" % layer
	return v


func _camera(layer: int) -> Camera3D:
	var c := Camera3D.new()
	c.projection = Camera3D.PROJECTION_ORTHOGONAL
	c.keep_aspect = Camera3D.KEEP_HEIGHT
	c.near = 1.0
	c.far = CAM_Y + 40.0
	c.rotation = Vector3(-PI * 0.5, 0.0, 0.0)
	c.cull_mask = layer
	c.current = true
	return c


func _environment() -> void:
	env_lo = Environment.new()
	env_lo.background_mode = Environment.BG_CLEAR_COLOR
	env_lo.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env_lo.ambient_light_color = Color(0.42, 0.40, 0.5)
	env_lo.ambient_light_energy = 1.0
	env_lo.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	var sky := Sky.new()
	var pm := PanoramaSkyMaterial.new()
	pm.panorama = load(t.dir + "hd/ball_env.png")
	sky.sky_material = pm
	env_lo.sky = sky
	env_lo.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	env_lo.glow_intensity = 0.7
	env_lo.glow_strength = 1.0
	env_lo.glow_bloom = 0.0
	env_lo.glow_hdr_threshold = 0.95
	env_lo.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN
	env_lo.set_glow_level(0, 0.0)
	env_lo.set_glow_level(1, 0.6)
	env_lo.set_glow_level(2, 1.0)
	env_lo.set_glow_level(3, 0.8)
	env_lo.set_glow_level(4, 0.4)
	var e_hi := env_lo.duplicate() as Environment
	e_hi.glow_enabled = false
	cam_lo.environment = env_lo
	cam_hi.environment = e_hi
	sun = DirectionalLight3D.new()
	sun.layers = 3  # LIGHT_LAYERS_FIX: compat culls lights by camera mask
	sun.light_color = Color(1.0, 0.96, 0.9)
	sun.light_energy = 0.9
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	sun.directional_shadow_max_distance = 320.0
	sun.shadow_blur = 1.5
	sun.shadow_bias = 0.04
	sun.shadow_normal_bias = 0.6
	sun.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	root.add_child(sun)
	sun.look_at_from_position(Vector3(160, 100, 320), Vector3(160, 100, 320) + SUN_DIR, Vector3(0, 0, -1))


func _sprite(v: SubViewport, z: int, premult: bool) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = v.get_texture()
	s.centered = true
	s.z_index = z
	s.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	var m := CanvasItemMaterial.new()
	m.light_mode = CanvasItemMaterial.LIGHT_MODE_UNSHADED
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_PREMULT_ALPHA
	s.material = m
	return s


## 2D camera -> both 3D cameras + sprites (called by game.gd after every camera move).
func sync_view(pos: Vector2, zoom: float, px: Vector2i) -> void:
	if px.x <= 0 or px.y <= 0:
		return
	if px != _size:
		_size = px
		low.size = px
		high.size = px
	for c: Camera3D in [cam_lo, cam_hi]:
		c.size = float(px.y) / zoom
		c.position = Vector3(pos.x, CAM_Y, pos.y)
	for s: Sprite2D in [low_spr, high_spr]:
		s.position = pos
		s.scale = Vector2.ONE / zoom


func apply_options(sh: bool, fx: int) -> void:
	shadows = sh
	lightfx = clampi(fx, 0, 2)
	sun.shadow_enabled = shadows
	env_lo.glow_enabled = lightfx >= 2
	for n in _flash:
		_flash[n].visible = lightfx >= 1
	for b in _bump:
		b[2].visible = lightfx >= 1
	for n in _inserts:
		_inserts[n][0].visible = false
	for s in _ball_sh:
		s.visible = shadows


# --- materials / mesh helpers ------------------------------------------------------------------

func _mat(key: String) -> Material:
	if _mats.has(key):
		return _mats[key]
	var m := StandardMaterial3D.new()
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	match key:
		"chrome":
			m.albedo_color = Color(0.82, 0.84, 0.90)
			m.metallic = 0.95
			m.roughness = 0.12
		"dark":
			m.albedo_color = Color(0.32, 0.3, 0.38)
			m.metallic = 0.8
			m.roughness = 0.35
		"rubber":
			m.albedo_color = Color(0.93, 0.9, 0.86)
			m.roughness = 0.55
		"rubber_red":
			m.albedo_color = Color(0.72, 0.1, 0.16)
			m.roughness = 0.45
		"skirt":
			m.albedo_color = Color(0.85, 0.2, 0.55)
			m.roughness = 0.25
			m.metallic_specular = 0.8
		"body":
			m.albedo_color = Color(0.3, 0.12, 0.45)
			m.roughness = 0.3
		"post_cap":
			m.albedo_color = Color(1.0, 0.35, 0.55)
			m.roughness = 0.2
			m.metallic_specular = 0.9
		"target":
			m.albedo_color = Color(1.0, 0.82, 0.2)
			m.roughness = 0.3
		"gold":
			m.albedo_color = Color(0.96, 0.76, 0.32)
			m.metallic = 0.90
			m.roughness = 0.15
		"hole":
			m.albedo_color = Color(0.05, 0.04, 0.08)
			m.roughness = 0.6
		"floor":
			var f := ShaderMaterial.new()
			f.shader = load("res://shaders/floor3d.gdshader")
			f.set_shader_parameter("albedo_tex", _pf_tex)
			f.set_shader_parameter("normal_tex", load(t.dir + "hd/playfield_n.png"))
			f.set_shader_parameter("spec_tex", load(t.dir + "hd/playfield_s.png"))
			f.set_shader_parameter("table_size", Vector2(t.W, t.H))
			f.set_shader_parameter("tint", TINT)
			_mats[key] = f
			return f
		"plastic":         # sling plastics: the painted art on a raised clear plate
			var f := (_mat("floor") as ShaderMaterial).duplicate() as ShaderMaterial
			f.set_shader_parameter("shade", 0.75)
			_mats[key] = f
			return f
	_mats[key] = m
	return m


func _cap_mat(tex_name: String, self_lit := 0.55) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/cap3d.gdshader")
	m.set_shader_parameter("tex", load(t.dir + "hd/" + tex_name + ".png"))
	m.set_shader_parameter("tint", TINT)
	m.set_shader_parameter("self_lit", self_lit)
	return m


func _get_st(key: String, p: Vector2, layer := 1) -> SurfaceTool:
	var cx := int(clampf(p.x, 0.0, t.W - 1.0) / CELL)
	var cy := int(clampf(p.y, 0.0, t.H - 1.0) / CELL)
	var k := "%s|%d|%d|%d" % [key, cx, cy, layer]
	if not _st.has(k):
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		_st[k] = [st, key, layer]
	return _st[k][0]


func _commit() -> void:
	for k in _st:
		var e: Array = _st[k]
		var mi := MeshInstance3D.new()
		mi.mesh = (e[0] as SurfaceTool).commit()
		mi.material_override = _mat(e[1])
		mi.layers = e[2]
		root.add_child(mi)
	_st.clear()


static func _vx(st: SurfaceTool, p: Vector3, n: Vector3, uv := Vector2.ZERO) -> void:
	st.set_normal(n)
	st.set_uv(uv)
	st.add_vertex(p)


## One triangle; winding fixed so its front face is on the normal side (Godot: clockwise front).
static func _tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, na: Vector3, nb: Vector3, nc: Vector3,
		ua := Vector2.ZERO, ub := Vector2.ZERO, uc := Vector2.ZERO) -> void:
	if (b - a).cross(c - a).dot(na + nb + nc) > 0.0:
		_vx(st, a, na, ua)
		_vx(st, c, nc, uc)
		_vx(st, b, nb, ub)
	else:
		_vx(st, a, na, ua)
		_vx(st, b, nb, ub)
		_vx(st, c, nc, uc)


static func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, na: Vector3, nb: Vector3,
		nc: Vector3, nd: Vector3, ua := Vector2.ZERO, ub := Vector2.ZERO, uc := Vector2.ZERO, ud := Vector2.ZERO) -> void:
	_tri(st, a, b, c, na, nb, nc, ua, ub, uc)
	_tri(st, a, c, d, na, nc, nd, ua, uc, ud)


static func _v3(p: Vector2, y: float) -> Vector3:
	return Vector3(p.x, y, p.y)


## Cylinder side around c (radius r, y0..y1), smooth normals.
static func _cyl(st: SurfaceTool, c: Vector2, r: float, y0: float, y1: float, n := 20) -> void:
	for i in n:
		var a0 := TAU * i / n
		var a1 := TAU * (i + 1) / n
		var d0 := Vector2(cos(a0), sin(a0))
		var d1 := Vector2(cos(a1), sin(a1))
		var n0 := Vector3(d0.x, 0, d0.y)
		var n1 := Vector3(d1.x, 0, d1.y)
		_quad(st, _v3(c + d0 * r, y0), _v3(c + d1 * r, y0), _v3(c + d1 * r, y1), _v3(c + d0 * r, y1), n0, n1, n1, n0)


## Domed (paraboloid) top of radius r at y0 rising by rise; uvf maps a local offset to a uv.
static func _dome(st: SurfaceTool, c: Vector2, r: float, y0: float, rise: float, n := 20, rings := 4, uvf = null) -> void:
	for j in rings:
		var r0 := r * (1.0 - float(j) / rings)
		var r1 := r * (1.0 - float(j + 1) / rings)
		var h0 := y0 + rise * (1.0 - pow(r0 / r, 2.0))
		var h1 := y0 + rise * (1.0 - pow(r1 / r, 2.0))
		var s0 := 2.0 * rise * r0 / (r * r)
		var s1 := 2.0 * rise * r1 / (r * r)
		for i in n:
			var a0 := TAU * i / n
			var a1 := TAU * (i + 1) / n
			var d0 := Vector2(cos(a0), sin(a0))
			var d1 := Vector2(cos(a1), sin(a1))
			var p := [d0 * r0, d1 * r0, d1 * r1, d0 * r1]
			var hs := [h0, h0, h1, h1]
			var ss := [s0, s0, s1, s1]
			var ds := [d0, d1, d1, d0]
			var v: Array = []
			var nn: Array = []
			var uu: Array = []
			for q in 4:
				v.append(_v3(c + p[q], hs[q]))
				nn.append(Vector3(ds[q].x * ss[q], 1.0, ds[q].y * ss[q]).normalized())
				uu.append(uvf.call(p[q]) if uvf != null else Vector2.ZERO)
			if j == rings - 1:
				_tri(st, v[0], v[1], v[2], nn[0], nn[1], nn[2], uu[0], uu[1], uu[2])
			else:
				_quad(st, v[0], v[1], v[2], v[3], nn[0], nn[1], nn[2], nn[3], uu[0], uu[1], uu[2], uu[3])


static func _torus(st: SurfaceTool, c: Vector2, rr: float, tube: float, y: float, n := 24, m := 8) -> void:
	for i in n:
		for j in m:
			var pts: Array = []
			var nrm: Array = []
			for q in [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]]:
				var a: float = TAU * float(q[0]) / n
				var b: float = TAU * float(q[1]) / m
				var d := Vector2(cos(a), sin(a))
				var nv := Vector3(d.x * cos(b), sin(b), d.y * cos(b))
				pts.append(_v3(c + d * (rr + tube * cos(b)), y + tube * sin(b)))
				nrm.append(nv)
			_quad(st, pts[0], pts[1], pts[2], pts[3], nrm[0], nrm[1], nrm[2], nrm[3])


## Extrude a cross-section profile (Vector2(across, up), convex, any order) along segment a->b.
static func _extrude(st: SurfaceTool, a: Vector2, b: Vector2, prof: PackedVector2Array, uvf = null) -> void:
	var d := (b - a).normalized()
	var o := d.orthogonal()
	var oc := Vector2.ZERO
	for p in prof:
		oc += p
	oc /= prof.size()
	for i in prof.size():
		var p := prof[i]
		var q := prof[(i + 1) % prof.size()]
		var e := q - p
		var nn := Vector2(e.y, -e.x).normalized()
		if nn.dot((p + q) * 0.5 - oc) < 0.0:
			nn = -nn
		var n3 := (Vector3(o.x, 0, o.y) * nn.x + Vector3.UP * nn.y).normalized()
		var pa := a + o * p.x
		var qa := a + o * q.x
		var pb := b + o * p.x
		var qb := b + o * q.x
		var u := [Vector2.ZERO, Vector2.ZERO, Vector2.ZERO, Vector2.ZERO]
		if uvf != null:
			u = [uvf.call(0.0, p.x), uvf.call(0.0, q.x), uvf.call(1.0, q.x), uvf.call(1.0, p.x)]
		_quad(st, _v3(pa, p.y), _v3(qa, q.y), _v3(qb, q.y), _v3(pb, p.y), n3, n3, n3, n3, u[0], u[1], u[2], u[3])


## Flat polygon prism (sides + top), top optionally uv'd by uvf(local point).
static func _prism(st: SurfaceTool, pts: PackedVector2Array, y0: float, y1: float, uvf = null) -> void:
	var c := Vector2.ZERO
	for p in pts:
		c += p
	c /= pts.size()
	for i in pts.size():
		var a := pts[i]
		var b := pts[(i + 1) % pts.size()]
		var nn := (b - a).orthogonal().normalized()
		if nn.dot((a + b) * 0.5 - c) < 0.0:
			nn = -nn
		var n3 := Vector3(nn.x, 0, nn.y)
		var ua: Vector2 = uvf.call(a) if uvf != null else Vector2.ZERO
		var ub: Vector2 = uvf.call(b) if uvf != null else Vector2.ZERO
		_quad(st, _v3(a, y0), _v3(b, y0), _v3(b, y1), _v3(a, y1), n3, n3, n3, n3, ua, ub, ub, ua)
	var idx := Geometry2D.triangulate_polygon(pts)
	for i in range(0, idx.size(), 3):
		var p0 := pts[idx[i]]
		var p1 := pts[idx[i + 1]]
		var p2 := pts[idx[i + 2]]
		var u0: Vector2 = uvf.call(p0) if uvf != null else Vector2.ZERO
		var u1: Vector2 = uvf.call(p1) if uvf != null else Vector2.ZERO
		var u2: Vector2 = uvf.call(p2) if uvf != null else Vector2.ZERO
		_tri(st, _v3(p0, y1), _v3(p1, y1), _v3(p2, y1), Vector3.UP, Vector3.UP, Vector3.UP, u0, u1, u2)


# --- table parts ---------------------------------------------------------------------------------

func _build_floor() -> void:
	var nx := int(ceil(t.W / TILE))
	var ny := int(ceil(t.H / TILE))
	var m := _mat("floor")
	for iy in ny:
		for ix in nx:
			var pm := PlaneMesh.new()
			pm.size = Vector2(TILE, TILE)
			var mi := MeshInstance3D.new()
			mi.mesh = pm
			mi.material_override = m
			mi.position = Vector3((ix + 0.5) * TILE, 0.0, (iy + 0.5) * TILE)
			mi.layers = 1
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			root.add_child(mi)


func _build_rails() -> void:
	var rail := PackedVector2Array([Vector2(-1.0, 0.0), Vector2(1.0, 0.0), Vector2(1.0, 6.0), Vector2(0.4, 7.0), Vector2(-0.4, 7.0), Vector2(-1.0, 6.0)])
	var band := PackedVector2Array([Vector2(-1.2, 2.6), Vector2(1.2, 2.6), Vector2(1.3, 4.2), Vector2(1.0, 5.6), Vector2(-1.0, 5.6), Vector2(-1.3, 4.2)])
	for i in t.seg_a.size():
		var mat: String = t.seg_mat[i]
		var a: Vector2 = t.seg_a[i]
		var b: Vector2 = t.seg_b[i]
		if a.distance_to(b) < 0.5:
			continue
		var mid := (a + b) * 0.5
		if mat == "wall":
			_extrude(_get_st("chrome", mid), a, b, rail)
		elif mat == "rubber" or mat.begins_with("sling"):
			_extrude(_get_st("rubber", mid), a, b, band)


func _build_posts() -> void:
	for c in t.circ:
		var p: Vector2 = c[0]
		var r: float = c[1]
		var mat: String = c[2]
		var nm := str(c[3]) if c.size() > 3 else ""
		if nm.begins_with("bumper"):
			continue
		if mat == "rubber":
			var st := _get_st("chrome", p)
			_cyl(st, p, r * 0.5, 0.0, 10.0, 14)
			_torus(_get_st("rubber", p), p, r * 0.68, r * 0.32, 4.5, 20, 8)
			_dome(_get_st("post_cap", p), p, r * 0.62, 10.0, 1.6, 14, 3)
			_cyl(_get_st("post_cap", p), p, r * 0.62, 8.8, 10.0, 14)
		elif mat == "wall":
			var st := _get_st("chrome", p)
			_cyl(st, p, r, 0.0, 8.0, 14)
			_dome(st, p, r, 8.0, minf(r, 2.0), 14, 3)


func _build_slings() -> void:
	if not t.g.has("slings"):
		return
	for poly in t.g.slings:
		var pts := PackedVector2Array()
		for p in poly:
			pts.append(Vector2(p[0], p[1]))
		var c := (pts[0] + pts[1] + pts[2]) / 3.0
		var ins := PackedVector2Array()
		for p in pts:
			ins.append(c + (p - c) * 0.78)
		if Geometry2D.is_polygon_clockwise(ins):
			ins.reverse()
		_prism(_get_st("plastic", c), ins, 8.0, 9.0)


func _build_bumpers() -> void:
	var cm_tex := "bumper"
	for i in t.g.bumpers.size():
		var b: Array = t.g.bumpers[i]
		var p := Vector2(b[0], b[1])
		var r := float(b[2])
		var holder: Node3D = null   # M11_MOVERS: a moving bumper gets its own node
		for m in t.movers:
			if int(m[0]) == i:
				holder = Node3D.new()
				holder.position = Vector3(p.x, 0.0, p.y)
				root.add_child(holder)
		if holder:
			for part in [["dark", 1.15, 0.0, 1.2, 24, 0.01, 1], ["skirt", 1.06, 1.2, 2.8, 24, 0.4, 2], ["body", 0.78, 2.8, 9.0, 20, 0.0, 0]]:
				var ps := SurfaceTool.new()
				ps.begin(Mesh.PRIMITIVE_TRIANGLES)
				_cyl(ps, Vector2.ZERO, r * float(part[1]), float(part[2]), float(part[3]), int(part[4]))
				if int(part[6]) > 0:
					_dome(ps, Vector2.ZERO, r * float(part[1]), float(part[3]), float(part[5]), int(part[4]), int(part[6]))
				var pm := MeshInstance3D.new()
				pm.mesh = ps.commit()
				pm.material_override = _mat(part[0])
				holder.add_child(pm)
		else:
			_cyl(_get_st("dark", p), p, r * 1.15, 0.0, 1.2, 24)
			_dome(_get_st("dark", p), p, r * 1.15, 1.2, 0.01, 24, 1)
			_cyl(_get_st("skirt", p), p, r * 1.06, 1.2, 2.8, 24)
			_dome(_get_st("skirt", p), p, r * 1.06, 2.8, 0.4, 24, 2)
			_cyl(_get_st("body", p), p, r * 0.78, 2.8, 9.0, 20)
		var par: Node3D = holder if holder else root
		var lp := Vector2.ZERO if holder else p
		# moving chrome ring (drops onto the ball when the bumper fires)
		var rs := SurfaceTool.new()
		rs.begin(Mesh.PRIMITIVE_TRIANGLES)
		_torus(rs, Vector2.ZERO, r * 0.9, r * 0.1, 0.0, 28, 6)
		var ring := MeshInstance3D.new()
		ring.mesh = rs.commit()
		ring.material_override = _mat("chrome")
		ring.position = Vector3(lp.x, 6.8, lp.y)
		par.add_child(ring)
		# cap: the painted top (bumper.png: circle centred (64, 78), r ~50 px = r units)
		var cap_m := _cap_mat(cm_tex, 0.5)
		var cs := SurfaceTool.new()
		cs.begin(Mesh.PRIMITIVE_TRIANGLES)
		var uvf := func(q: Vector2) -> Vector2: return Vector2((64.0 + q.x / r * 50.0) / 128.0, (78.0 + q.y / r * 50.0) / 160.0)
		_cyl(cs, Vector2.ZERO, r, 9.0, 11.5, 28)
		_dome(cs, Vector2.ZERO, r, 11.5, 1.8, 28, 5, uvf)
		var cap := MeshInstance3D.new()
		cap.mesh = cs.commit()
		cap.material_override = cap_m
		cap.position = Vector3(lp.x, 0.0, lp.y)
		par.add_child(cap)
		var l := OmniLight3D.new()
		l.layers = 3
		l.position = Vector3(lp.x, 6.0, lp.y)
		l.omni_range = r * 3.2
		l.light_color = Color(1.0, 0.78, 0.5)
		l.light_energy = 0.3
		l.shadow_enabled = false
		par.add_child(l)
		_bump.append([ring, cap_m, l, holder])


func _build_flippers() -> void:
	var art := float(t.g.art_scale)
	for fl in t.flippers:
		var nm := "flipper_small" if fl.small else "flipper"
		var tex: Texture2D = load(t.dir + "hd/" + nm + ".png")
		var tw := float(tex.get_width())
		var th := float(tex.get_height())
		var piv: float = fl.r0 + 2.0
		var outline := PackedVector2Array()
		for i in 13:
			var a := -PI * 0.5 + PI * i / 12.0
			outline.append(Vector2(fl.length + cos(a) * fl.r1, sin(a) * fl.r1))
		for i in 13:
			var a := PI * 0.5 + PI * i / 12.0
			outline.append(Vector2(cos(a) * fl.r0, sin(a) * fl.r0))
		var mirror: bool = not fl.left
		var pts := PackedVector2Array()
		for p in outline:
			pts.append(Vector2(p.x, -p.y) if mirror else p)
		if Geometry2D.is_polygon_clockwise(pts):
			pts.reverse()
		var uvf := func(q: Vector2) -> Vector2:
			var lq := Vector2(q.x, -q.y) if mirror else q
			return Vector2((lq.x + piv) * art / tw, (lq.y + piv) * art / th)
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		_prism(st, pts, 0.0, 8.0, uvf)
		var mi := MeshInstance3D.new()
		mi.mesh = st.commit()
		mi.material_override = _cap_mat(nm, 0.45)
		var nd := Node3D.new()
		nd.position = _v3(fl.pivot, 0.0)
		nd.add_child(mi)
		var ps := SurfaceTool.new()
		ps.begin(Mesh.PRIMITIVE_TRIANGLES)
		_cyl(ps, Vector2.ZERO, fl.r0 * 0.35, 8.0, 9.2, 12)
		_dome(ps, Vector2.ZERO, fl.r0 * 0.35, 9.2, 0.6, 12, 2)
		var pin := MeshInstance3D.new()
		pin.mesh = ps.commit()
		pin.material_override = _mat("chrome")
		nd.add_child(pin)
		root.add_child(nd)
		_fl.append(nd)


func _build_drops_targets() -> void:
	var dtex: Texture2D = load(t.dir + "hd/drop.png")
	var dw := float(dtex.get_width()) / float(t.g.art_scale)
	var dh := float(dtex.get_height()) / float(t.g.art_scale)
	var dm := _cap_mat("drop", 0.5)
	for d in t.g.drops:
		var a := Vector2(d.seg[0], d.seg[1])
		var b := Vector2(d.seg[2], d.seg[3])
		var c := (a + b) * 0.5 + (b - a).orthogonal().normalized() * -1.0
		var ang := (b - a).angle()
		var hl := a.distance_to(b) * 0.5
		var box := PackedVector2Array([Vector2(-hl, -1.8), Vector2(hl, -1.8), Vector2(hl, 1.8), Vector2(-hl, 1.8)])
		var uvf := func(q: Vector2) -> Vector2: return Vector2(0.5 + q.x / dw, 0.5 + q.y / dh)
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		_prism(st, box, -12.0, 9.0, uvf)
		var mi := MeshInstance3D.new()
		mi.mesh = st.commit()
		mi.material_override = dm
		mi.position = _v3(c, 0.0)
		mi.rotation.y = -ang
		root.add_child(mi)
		_drops.append(mi)
		_drop_y.append(0.0)
	for tg in t.g.targets:
		var a := Vector2(tg.seg[0], tg.seg[1])
		var b := Vector2(tg.seg[2], tg.seg[3])
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(1.0, 0.82, 0.22)
		m.roughness = 0.3
		m.emission_enabled = true
		m.emission = Color(1.0, 0.7, 0.2)
		m.emission_energy_multiplier = 0.0
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var o := (b - a).orthogonal().normalized()
		_extrude(st, a - o * 0.2, b - o * 0.2, PackedVector2Array([Vector2(-1.4, 0), Vector2(1.4, 0), Vector2(1.4, 7.0), Vector2(-1.4, 7.0)]))
		_extrude(st, a.lerp(b, 0.4) - o * 2.6, a.lerp(b, 0.6) - o * 2.6, PackedVector2Array([Vector2(-1.0, 0), Vector2(1.0, 0), Vector2(1.0, 5.0), Vector2(-1.0, 5.0)]))
		var mi := MeshInstance3D.new()
		mi.mesh = st.commit()
		mi.material_override = m
		root.add_child(mi)
		_targets.append(m)


func _build_discs() -> void:
	for d in t.discs:
		var nm := str(d.name)
		var tex: Texture2D = load(t.dir + "hd/" + nm + ".png")
		var span := float(tex.get_width()) / float(t.g.art_scale)
		var r := float(d.r)
		var uvf := func(q: Vector2) -> Vector2: return Vector2(0.5, 0.5) + q / span
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		_cyl(st, Vector2.ZERO, r, 0.0, 1.4, 48)
		_dome(st, Vector2.ZERO, r, 1.4, 0.4, 48, 6, uvf)
		var mi := MeshInstance3D.new()
		mi.mesh = st.commit()
		mi.material_override = _cap_mat(nm, 0.5)
		var rim := SurfaceTool.new()
		rim.begin(Mesh.PRIMITIVE_TRIANGLES)
		_torus(rim, Vector2.ZERO, r, 0.7, 1.2, 64, 6)
		var rmi := MeshInstance3D.new()
		rmi.mesh = rim.commit()
		rmi.material_override = _mat("gold")
		var nd := Node3D.new()
		nd.position = _v3(d.pos, 0.0)
		nd.add_child(mi)
		nd.add_child(rmi)
		root.add_child(nd)
		_discs.append(nd)


func _build_misc() -> void:
	# spinner brackets
	var sps: Array = []
	if t.g.has("spinner"):
		sps.append([Vector2(t.g.spinner.pos[0], t.g.spinner.pos[1]), float(t.g.spinner.get("w", 26.0))])
	for sp in t.spinners:
		sps.append([sp.pos, float(sp.w)])
	for s in sps:
		for sg in [-1.0, 1.0]:
			var p: Vector2 = s[0] + Vector2(sg * (s[1] * 0.5 + 1.2), 0.0)
			_cyl(_get_st("chrome", p), p, 1.3, 0.0, 9.0, 10)
			_dome(_get_st("chrome", p), p, 1.3, 9.0, 0.8, 10, 2)
	# hole rims (saucer / subway entries)
	for hn in t.holes:
		var h: Dictionary = t.holes[hn]
		var p := Vector2(h.pos[0], h.pos[1])
		_torus(_get_st("dark", p), p, float(h.r) + 0.8, 0.9, 0.4, 24, 6)
	# helter tower: chrome pole under the dome
	if t.g.has("tower"):
		var tp := Vector2(t.g.tower[0], t.g.tower[1])
		_cyl(_get_st("chrome", tp), tp, 2.6, 0.0, RAMP_H + 8.0, 14)


static func _smooth(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


func _height(r: Dictionary, s: float) -> float:
	var apex := float(r.apex)
	var down := float(r.down)
	var L := float(r.len)
	var e := 1.0
	if s < apex:
		e = s / maxf(apex, 1.0)
	elif s >= down:
		e = 1.0 - (s - down) / maxf(L - down, 1.0)
	return RAMP_H * _smooth(e)


func _ramp_shader(id: int) -> Array:
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/ramp3d.gdshader")
	m.set_shader_parameter("ramp_tex", load(t.dir + "hd/ramps.png"))
	m.set_shader_parameter("spec_tex", load(t.dir + "hd/ramps_s.png"))
	m.set_shader_parameter("owner_tex", _owner)
	m.set_shader_parameter("table_size", Vector2(t.W, t.H))
	m.set_shader_parameter("tint", TINT)
	m.set_shader_parameter("my_id", id * 40.0 / 255.0)
	var s := ShaderMaterial.new()
	s.shader = load("res://shaders/ramp3d_shadow.gdshader")
	s.set_shader_parameter("ramp_tex", load(t.dir + "hd/ramps.png"))
	s.set_shader_parameter("owner_tex", _owner)
	s.set_shader_parameter("table_size", Vector2(t.W, t.H))
	s.set_shader_parameter("my_id", id * 40.0 / 255.0)
	_ramp_mats.append(m)
	return [m, s]


func _add_pair(st: SurfaceTool, mats: Array) -> void:
	var mesh := st.commit()
	var vis := MeshInstance3D.new()
	vis.mesh = mesh
	vis.material_override = mats[0]
	vis.layers = 2
	vis.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(vis)
	var sh := MeshInstance3D.new()
	sh.mesh = mesh
	sh.material_override = mats[1]
	sh.layers = 1
	sh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	root.add_child(sh)


func _build_ramps() -> void:
	var n: int = t.ramps.size()
	for ri in n:
		var r: Dictionary = t.ramps[ri]
		var path: PackedVector2Array = r.path
		var ss := PackedFloat32Array(r.s)
		var hw := float(r.w) * 0.5 + PAD
		var mats := _ramp_shader(ri + 1)
		var os: Array[Vector2] = []
		var hs: Array[float] = []
		for i in path.size():
			var d := path[mini(i + 1, path.size() - 1)] - path[maxi(i - 1, 0)]
			os.append(d.normalized().orthogonal())
			hs.append(_height(r, ss[i]))
		var st: SurfaceTool = null
		var cnt := 0
		var next_sup := 20.0
		for i in path.size():
			if i > 0:
				if st == null:
					st = SurfaceTool.new()
					st.begin(Mesh.PRIMITIVE_TRIANGLES)
				var a0 := _v3(path[i - 1] + os[i - 1] * hw, hs[i - 1])
				var a1 := _v3(path[i - 1] - os[i - 1] * hw, hs[i - 1])
				var b0 := _v3(path[i] + os[i] * hw, hs[i])
				var b1 := _v3(path[i] - os[i] * hw, hs[i])
				_quad(st, a0, b0, b1, a1, Vector3.UP, Vector3.UP, Vector3.UP, Vector3.UP)
				cnt += 1
				if cnt >= 24:
					_add_pair(st, mats)
					st = null
					cnt = 0
			# supports: thin chrome legs under the deck edges
			if ss[i] >= next_sup and hs[i] > 8.0:
				next_sup = ss[i] + 45.0
				for sg in [-1.0, 1.0]:
					var lp: Vector2 = path[i] + os[i] * sg * (float(r.w) * 0.5 + 2.0)
					_cyl(_get_st("chrome", lp), lp, 0.9, 0.0, hs[i] - 0.5, 8)
		if st != null and cnt > 0:
			_add_pair(st, mats)
	# helter tower dome (owner id n + 1)
	if t.g.has("tower"):
		var tp := Vector2(t.g.tower[0], t.g.tower[1])
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		_dome(st, tp, TOWER_R, RAMP_H + 6.0, 8.0, 28, 5)
		_add_pair(st, _ramp_shader(n + 1))



func _color(name: String) -> Color:
	var c = t.g.light_colors.get(name, [255, 255, 255])
	return Color8(int(c[0]), int(c[1]), int(c[2]))


func _build_lights() -> void:
	if t.rules and t.rules.has_method("flashers"):
		var fl: Dictionary = t.rules.flashers()
		for n in fl:
			var e: Array = fl[n]
			var l := OmniLight3D.new()
			l.layers = 3
			l.position = Vector3(float(e[0][0]), 22.0, float(e[0][1]))
			l.omni_range = float(e[2]) * 0.8
			l.light_color = e[1]
			l.light_energy = 0.0
			l.omni_attenuation = 1.2
			l.visible = false
			root.add_child(l)
			_flash[n] = l
	for n in t.g.lights:
		var d: Dictionary = t.g.lights[n]
		var l := OmniLight3D.new()
		l.layers = 3
		l.position = Vector3(float(d.pos[0]), 3.0, float(d.pos[1]))
		l.omni_range = float(d.get("size", 4.0)) * 3.2
		l.light_color = _color(str(d.get("color", "white")))
		l.light_energy = 0.0
		l.visible = false
		root.add_child(l)
		_inserts[n] = [l, l.light_color]


# --- per frame -----------------------------------------------------------------------------------

func update(delta: float) -> void:
	_time += delta
	for i in _fl.size():
		_fl[i].rotation.y = -t.flippers[i].angle()
	for i in _bump.size():
		var f: float = t.bumper_flash[i]
		var e: Array = _bump[i]
		e[0].position.y = 6.8 - 3.6 * _smooth((f - 0.5) / 0.4)
		(e[1] as ShaderMaterial).set_shader_parameter("flash", f)
		e[2].light_energy = 0.3 + 3.0 * f
		if e[3] != null:
			(e[3] as Node3D).position = Vector3(float(t.g.bumpers[i][0]), 0.0, float(t.g.bumpers[i][1]))
	for i in _drops.size():
		var target := -12.5 if t.drops[i] else 0.0
		_drop_y[i] = move_toward(_drop_y[i], target, delta * 140.0)
		_drops[i].position.y = _drop_y[i]
	for i in _targets.size():
		var tf: float = t.target_flash[i] if i < t.target_flash.size() else 0.0
		_targets[i].emission_energy_multiplier = tf * 2.5
	for i in _discs.size():
		_discs[i].rotation.y = -float(t.discs[i].a)
	for m in _ramp_mats:
		m.set_shader_parameter("t", t._time)
	# multiball / light show: flashers pulse, a sweep runs over the inserts
	var show := bool(t.multiball) or float(t._show) > 0.0
	for n in _flash:
		var l: OmniLight3D = _flash[n]
		var en := float(t.flash.get(n, 0.0)) * 2.2
		if show and lightfx >= 2:
			en = maxf(en, 0.9 * maxf(0.0, sin(_time * 7.0 + l.position.x * 0.05 + l.position.z * 0.02)))
		l.light_energy = en
		l.visible = lightfx >= 1 and en > 0.01
	if lightfx >= 2:
		for n in _inserts:
			var e: Array = _inserts[n]
			var l: OmniLight3D = e[0]
			var lv := float(t.lamp_level.get(n, 0.0))
			if show:
				lv = maxf(lv, 0.8 * maxf(0.0, sin(_time * 5.0 - l.position.z * 0.03)))
			l.light_energy = lv * 0.9
			l.visible = lv > 0.03
	# shadow-only spheres for the balls (the 2D ball keeps its own art)
	while _ball_sh.size() < t.balls.size():
		var s := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = float(t.g.ball_r)
		sm.height = sm.radius * 2.0
		sm.radial_segments = 16
		sm.rings = 8
		s.mesh = sm
		s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		root.add_child(s)
		_ball_sh.append(s)
	for i in _ball_sh.size():
		var s: MeshInstance3D = _ball_sh[i]
		if i < t.balls.size():
			var b = t.balls[i]
			s.visible = shadows and b.sprite != null and b.sprite.visible and b.hole == ""
			s.position = Vector3(b.pos.x, t.ramp_elev(b) * RAMP_H + float(t.g.ball_r) + 0.3, b.pos.y)
		else:
			s.visible = false
