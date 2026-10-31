shader_type canvas_item;
// M14: polished chrome / steel pinball seen from above. A real ball is a near-perfect convex mirror, so
// it shows the LIVE table around it: the shader samples the screen right below the ball (hint_screen_texture:
// everything drawn before the ball, i.e. the lit 2D table or the rendered 3D table with its inserts,
// bumper lights, flasher pools and GI) along the mirrored view ray, so every lamp, flash and colour
// pool moves across the ball as it rolls. On top of that:
//  - upper part (rays going up; "up" tilted to the top of the screen like a 3/4 view): bright room /
//    glass with a warm backbox panel, key window and strip light, tinted by the far, blurred table,
//  - lower part (rays going down): the live table, mirrored and compressed like a convex mirror,
//    colourful, only slightly lifted so the steel stays bright silver,
//  - every nearby dynamic light (flashers, bumpers, lit inserts; up to 8, fed by table.gd) adds a sharp
//    coloured specular hotspot plus a soft coloured wash on the side facing it, so a firing flasher
//    visibly floods the ball with its colour,
//  - a clean white primary key hotspot plus a small secondary one,
//  - a dark cabinet band near the silhouette, a thin bright Fresnel rim and a slight edge darkening,
//  - a rolling layer (GI dots + micro-wear, rotated by the ball's spin) and motion blur at speed.
// No shadow is drawn in the quad: table.gd draws the drop shadow and the contact patch under the ball.
render_mode unshaded;

uniform sampler2D env : filter_linear, repeat_enable;   // GI / room map (equirect), rolls with the ball
uniform sampler2D pf : filter_linear;                   // playfield art (fallback only)
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;   // live table under the ball
uniform float live = 1.0;            // 1 = mirror the live screen, 0 = the static playfield art
uniform vec2 table_size = vec2(320.0, 640.0);
uniform vec2 ball_pos = vec2(0.0);
uniform float ball_r = 7.5;
uniform float quad = 1.6;
uniform mat3 rot = mat3(1.0);        // world -> ball-local (rolling)
uniform vec2 vel = vec2(0.0);        // table units / s
uniform float elev = 0.0;            // 0..1 ramp height
uniform vec4 lpos[8];                // light xy relative to the ball centre (units), z = height above the table
uniform vec4 lcol[8];                // rgb * energy
uniform float boost = 1.0;
uniform vec3 tint = vec3(1.0);

const vec3 KEY = vec3(-0.38, -0.55, 0.74);    // key light: upper left of the table, high
const vec3 FILL = vec3(0.55, 0.30, 0.78);
const vec3 TILT_U = vec3(0.0, -0.208, 0.978);   // world up in view space (tilt ~12 deg)
const vec3 TILT_V = vec3(0.0, 0.978, 0.208);    // world down the table in view space

float hash3(vec3 p) {
	p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 x) {
	vec3 i = floor(x);
	vec3 f = fract(x);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash3(i), hash3(i + vec3(1.0, 0.0, 0.0)), f.x),
			mix(hash3(i + vec3(0.0, 1.0, 0.0)), hash3(i + vec3(1.0, 1.0, 0.0)), f.x), f.y),
		mix(mix(hash3(i + vec3(0.0, 0.0, 1.0)), hash3(i + vec3(1.0, 0.0, 1.0)), f.x),
			mix(hash3(i + vec3(0.0, 1.0, 1.0)), hash3(i + vec3(1.0, 1.0, 1.0)), f.x), f.y), f.z);
}

// sharp band: 1 inside |x - c| < w, crisp edges of width e
float band(float x, float c, float w, float e) {
	return smoothstep(w + e, w, abs(x - c));
}

float luma(vec3 c) {
	return dot(c, vec3(0.299, 0.587, 0.114));
}

// the room / cabinet above the playfield, in table space (x right, y down the table, z up)
vec3 room_env(vec3 d) {
	float el = max(d.z, 0.0);
	// bright studio glass overhead: clear neutral silver-grey
	vec3 c = mix(vec3(0.92, 0.93, 0.95), vec3(0.68, 0.70, 0.75), smoothstep(0.10, 0.95, el));
	// gentle falloff away from key light to give 3D spherical volume
	c *= 0.85 + 0.15 * smoothstep(-0.6, 0.7, dot(d.xy, vec2(-0.55, -0.83)));
	// backbox: warm glowing translite marquee at the top (-y)
	float bb = smoothstep(0.1, -0.65, d.y) * smoothstep(0.08, 0.55, el) * smoothstep(0.85, 0.25, abs(d.x));
	c = mix(c, vec3(1.12, 0.98, 0.78), bb * 0.75);
	// cabinet side rails: vertical dark steel bands on left and right
	float side_rails = smoothstep(0.65, 0.92, abs(d.x)) * (1.0 - smoothstep(0.6, 0.95, el));
	c = mix(c, vec3(0.22, 0.23, 0.28), side_rails * 0.65);
	// key-light softbox window (upper left) split by a crisp frame bar + secondary strip light
	vec2 wq = abs(d.xy - vec2(-0.32, -0.40));
	float win = smoothstep(0.28, 0.26, wq.x) * smoothstep(0.20, 0.18, wq.y) * smoothstep(0.012, 0.022, abs(d.x + 0.32));
	float strip = band(d.y, 0.28, 0.035, 0.012) * band(d.x - 0.12, 0.0, 0.22, 0.05) * 0.75;
	float up = smoothstep(0.25, 0.65, el);
	c = mix(c, vec3(1.35, 1.34, 1.32), clamp(win + strip, 0.0, 1.0) * up);
	return c;
}

// screen-space mapping: c = screen UV of the ball centre, k = screen UV per table unit
vec3 live_at(vec2 rel, vec2 c, vec2 k) {
	return texture(screen_tex, clamp(c + rel * k, vec2(0.001), vec2(0.999))).rgb;
}

// blurred far table (high mip level): smooth colour pools, no radial streaks
vec3 live_far(vec2 rel, vec2 c, vec2 k) {
	return textureLod(screen_tex, clamp(c + rel * k, vec2(0.001), vec2(0.999)), 4.0).rgb;
}

// Optical diffraction starburst rays around a specular highlight
float spec_rays(vec3 rf_dir, vec3 L_dir, float spec_dot) {
	if (spec_dot < 0.92) {
		return 0.0;
	}
	vec3 up = abs(L_dir.z) < 0.95 ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
	vec3 u = normalize(cross(L_dir, up));
	vec3 v = cross(L_dir, u);
	vec3 dp = rf_dir - L_dir;
	vec2 c = vec2(dot(dp, u), dot(dp, v));
	float len_c = length(c);
	if (len_c < 1e-4) {
		return smoothstep(0.92, 0.985, spec_dot);
	}
	float ang = atan(c.y, c.x);
	float star = pow(abs(cos(ang * 2.0)), 14.0) + 0.45 * pow(abs(cos(ang * 2.0 + 0.7854)), 14.0);
	float fade = exp(-len_c * 22.0) * smoothstep(0.92, 0.985, spec_dot);
	return star * fade;
}

vec4 shade(vec2 p, float aa, vec2 sc, vec2 sk) {
	float r = length(p);
	float a = smoothstep(1.0, 1.0 - aa, r);
	if (a <= 0.0) {
		return vec4(0.0);
	}
	float r2 = min(dot(p, p), 0.9999);
	vec3 n = vec3(p, sqrt(1.0 - r2));                 // screen coords: x right, y down, z to viewer
	vec3 rf = 2.0 * n.z * n - vec3(0.0, 0.0, 1.0);    // mirror reflection of the view ray
	vec3 d = vec3(rf.x, dot(rf, TILT_V), dot(rf, TILT_U));
	vec3 P = vec3(n.xy * ball_r, ball_r * (1.0 + n.z));
	// --- upper hemisphere: bright studio room plus rolling GI layer
	vec3 sky = room_env(vec3(d.x, d.y, max(d.z - 0.02, 0.0)));
	vec3 rr = rot * rf;
	float u = atan(rr.y, rr.x) / 6.2831853 + 0.5;
	float v = acos(clamp(rr.z, -1.0, 1.0)) / 3.14159265;
	vec3 gi = texture(env, vec2(u, v * 0.5)).rgb;
	// GI dots: subtle sparkling ambient roll
	sky += gi * gi * 0.12 * smoothstep(0.92, 0.75, rr.z) * smoothstep(0.17, 0.26, v * 0.5);
	vec2 fdir = rf.xy / max(length(rf.xy), 1e-3);
	vec3 far_c;
	if (live > 0.5) {
		vec2 fp = (rf.xy * 12.0 + vec2(0.0, -8.0)) * ball_r;
		far_c = live_far(fp, sc, sk);
	} else {
		far_c = texture(pf, (ball_pos + fdir * ball_r * 10.0) / table_size).rgb;
	}
	sky *= 0.94 + 0.08 * luma(far_c);

	// --- lower hemisphere: table elements mirrored on polished steel
	// Only rays pointing down towards the table (rf.z < 0) can see the playfield
	float down = smoothstep(0.04, -0.16, rf.z);
	float t = P.z / max(-rf.z, 0.04);
	float tm = ball_r * 10.0;
	t = tm * (1.0 - exp(-t / tm));
	vec2 rel = P.xy + rf.xy * t;
	vec3 pfc = live > 0.5 ? live_at(rel, sc, sk) : texture(pf, (ball_pos + rel) / table_size).rgb;
	// contact occlusion: the area under the ball is shaded by the ball itself
	float occ = mix(0.45, 1.0, smoothstep(ball_r * 1.1, ball_r * 2.5, length(rel)));
	// chrome steel reflection of table elements: bright, metallic, never opaque paint
	vec3 floor_refl = (pfc * 0.70 + vec3(0.15, 0.16, 0.18)) * occ - elev * 0.03;
	// steel body preserves its silver character and mass
	vec3 steel_base = sky * (0.88 + 0.12 * smoothstep(-0.3, 0.8, dot(n, normalize(KEY))));
	vec3 col = mix(steel_base, mix(steel_base * 0.50 + floor_refl * 0.50, floor_refl, 0.30), down);

	// rolling micro-wear: faint smudges fixed to the steel (makes the spin visible)
	vec3 nl = rot * n;
	float w = vnoise(nl * 9.0) * 0.6 + vnoise(nl * 23.0) * 0.4;
	col *= 0.96 + 0.06 * w;
	col *= vec3(0.96, 0.97, 1.0);
	// dynamic lights: sharp coloured hotspot + diffraction rays + soft wash
	vec3 hot = vec3(0.0);
	vec3 wash = vec3(0.0);
	for (int i = 0; i < 8; i++) {
		vec3 lc = lcol[i].rgb;
		if (dot(lc, lc) < 1e-5) {
			continue;
		}
		vec3 L = normalize(lpos[i].xyz - P);
		float dl = max(dot(rf, L), 0.0);
		float nd = max(dot(n, L), 0.0);
		// sharp specular hotspot + diffraction rays
		float spec = smoothstep(0.976, 0.992, dl) * 3.6 + pow(max(dl, 1e-4), 45.0) * 0.65;
		float l_rays = spec_rays(rf, L, dl);
		hot += lc * (spec + l_rays * 2.2);
		wash += lc * (nd * nd * 0.45 + pow(max(dl, 1e-4), 8.0) * 0.15);
	}
	wash /= 1.0 + 0.5 * luma(wash);
	col = col * (1.0 + wash * 0.9) + wash * 0.15 + hot;
	// clean white primary key hotspot (fixed to the light) + starburst rays
	vec3 nKEY = normalize(KEY);
	float kd = max(dot(rf, nKEY), 0.0);
	col += vec3(1.0, 0.99, 0.97) * (smoothstep(0.978, 0.988, kd) * 3.4 + pow(max(kd, 1e-4), 110.0) * 0.55);
	// starburst diffraction rays radiating from the key highlight
	float key_rays = spec_rays(rf, nKEY, kd);
	col += vec3(1.0, 0.99, 0.95) * (key_rays * 2.5);
	// secondary fill glint
	float fd = max(dot(rf, normalize(FILL)), 0.0);
	col += vec3(0.92, 0.95, 1.0) * (smoothstep(0.9975, 0.9990, fd) * 1.6 + pow(max(fd, 1e-4), 160.0) * 0.18);
	col *= tint * boost;
	// silhouette: natural Fresnel reflection rising at grazing angles + clean dark edge line
	float fresnel = pow(1.0 - max(n.z, 0.0), 3.5);
	col = mix(col, vec3(0.96, 0.97, 1.0), fresnel * 0.40);
	col *= 1.0 - 0.50 * smoothstep(0.97, 0.998, r);
	return vec4(col, a);
}

void fragment() {
	vec2 q = (UV * 2.0 - 1.0) * quad;               // in ball radii
	float aa = max(fwidth(q.x) * 1.5, 0.02);
	// screen UV per table unit (from the quad's own derivatives) and the ball centre on screen
	vec2 sk = vec2(dFdx(SCREEN_UV.x) / dFdx(q.x), dFdy(SCREEN_UV.y) / dFdy(q.y)) / ball_r;
	vec2 sc = SCREEN_UV - q * ball_r * sk;
	float sp = length(vel);
	// subtle motion blur: ~1/150 s exposure, only at high speed, capped
	float bl = clamp(sp / 150.0 / ball_r - 0.35, 0.0, 0.7);
	if (bl <= 0.001) {
		COLOR = shade(q, aa, sc, sk);
	} else {
		vec2 dir = vel / sp;
		vec3 c = vec3(0.0);
		float s = 0.0;
		for (int i = 0; i < 7; i++) {
			vec4 o = shade(q - dir * bl * (float(i) / 6.0 - 0.5), aa, sc, sk);
			c += o.rgb * o.a;
			s += o.a;
		}
		COLOR = vec4(c / max(s, 1e-4), s / 7.0);
	}
}
