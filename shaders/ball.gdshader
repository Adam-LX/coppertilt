shader_type canvas_item;
// Polished solid chrome-steel pinball (heavy, opaque metallic sphere).
// Optical model:
//  - 100% solid, opaque chrome metal: NO transparent rim, NO soap-bubble glass halo.
//  - High-contrast chrome reflection:
//      * Upper half: bright translite marquee, neon backbox glow, overhead glass glare.
//      * Lower belly (p.y > 0, facing down towards table): mirrored live table elements & inserts.
//      * Left/right flanks: dark cabinet mirror blades with vertical chrome reflection sheen.
//      * Silhouette rim: sleek polished steel edge contour that cleanly pops against any background.
//  - Primary key spotlight: blinding specular core with razor-sharp optical diffraction starburst rays (promienie).
//  - Dynamic lights (up to 8): flashers, bumpers, lit inserts cast vivid moving glints & starburst rays.
//  - Rolling spin: physical micro-grain rotated by the rolling matrix (tangible weight and spin).
render_mode unshaded;

uniform sampler2D pf : filter_linear;                   // playfield art (fallback)
uniform sampler2D screen_tex : hint_screen_texture, filter_linear;   // live table under ball
uniform float live = 1.0;            // 1 = mirror live screen, 0 = static playfield art
uniform vec2 table_size = vec2(320.0, 640.0);
uniform vec2 ball_pos = vec2(0.0);
uniform float ball_r = 7.5;
uniform float quad = 1.6;
uniform mat3 rot = mat3(1.0);        // world -> ball-local (rolling)
uniform vec2 vel = vec2(0.0);        // table units / s
uniform float elev = 0.0;            // 0..1 ramp height
uniform vec4 lpos[8];                // light xy relative to ball centre (units), z = height
uniform vec4 lcol[8];                // rgb * energy
uniform float boost = 1.0;
uniform vec3 tint = vec3(1.0);

// Key spotlight: upper-left overhead
const vec3 KEY = vec3(-0.38, -0.55, 0.74);
const vec3 FILL = vec3(0.55, 0.30, 0.78);

// Tilted perspective coordinates
const vec3 TILT_U = vec3(0.0, -0.6816, 0.7317);   // table up
const vec3 TILT_V = vec3(0.0, 0.7317, 0.6816);    // table down

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

float luma(vec3 c) {
	return dot(c, vec3(0.299, 0.587, 0.114));
}

vec3 live_at(vec2 rel, vec2 c, vec2 k) {
	return texture(screen_tex, clamp(c + rel * k, vec2(0.001), vec2(0.999))).rgb;
}

// Optical diffraction starburst rays around specular highlights (promienie odblasku)
float spec_rays(vec3 rf_dir, vec3 L_dir, float spec_dot) {
	if (spec_dot < 0.72) {
		return 0.0;
	}
	vec3 up = abs(L_dir.z) < 0.95 ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
	vec3 u = normalize(cross(L_dir, up));
	vec3 v = cross(L_dir, u);
	vec3 dp = rf_dir - L_dir;
	vec2 c = vec2(dot(dp, u), dot(dp, v));
	float len_c = length(c);
	if (len_c < 1e-4) {
		return 1.0;
	}
	float ang = atan(c.y, c.x);
	// Sharp primary cross spikes + secondary 45-degree diagonal rays
	float primary = pow(max(abs(cos(ang * 2.0)), 1e-4), 16.0);
	float diagonal = pow(max(abs(cos(ang * 2.0 + 0.785398)), 1e-4), 16.0) * 0.45;
	float star = primary + diagonal;
	float fade = exp(-len_c * 7.5) * smoothstep(0.72, 0.96, spec_dot);
	return star * fade;
}

// Cabinet & arcade room reflection
vec3 room_env(vec3 d) {
	// Base steel volume: bright overhead, deeper tone towards lower horizon
	vec3 c = mix(vec3(0.68, 0.70, 0.75), vec3(0.90, 0.92, 0.96), smoothstep(-0.2, 0.8, d.z));
	c *= 0.82 + 0.18 * smoothstep(-0.6, 0.6, dot(d.xy, vec2(-0.55, -0.83)));

	// Backbox translite marquee (-y): glowing illuminated art with warm neon tones
	float bb = smoothstep(0.15, -0.65, d.y) * smoothstep(-0.1, 0.65, d.z) * smoothstep(0.85, 0.20, abs(d.x));
	c = mix(c, vec3(1.18, 1.04, 0.80), bb * 0.75);

	// Cabinet side rails (+/- x): dark polished mirror blades
	float rails = smoothstep(0.45, 0.92, abs(d.x)) * (1.0 - smoothstep(0.4, 0.95, d.z));
	float rx = (abs(d.x) - 0.72) / 0.12;
	vec3 rail_c = vec3(0.10, 0.11, 0.14) + vec3(0.40, 0.42, 0.50) * exp(-rx * rx);
	c = mix(c, rail_c, rails * 0.80);

	// Glass glare line along the horizon
	float rz = d.z / 0.10;
	float hz = exp(-rz * rz) * smoothstep(-0.3, 0.7, -d.y);
	c += vec3(0.92, 0.95, 1.0) * (hz * 0.28);

	return c;
}

vec4 shade(vec2 p, float aa, vec2 sc, vec2 sk) {
	float r = length(p);
	float a = smoothstep(1.0, 1.0 - aa, r);
	if (a <= 0.0) {
		return vec4(0.0);
	}
	float r2 = min(dot(p, p), 0.9999);
	vec3 n = vec3(p, sqrt(1.0 - r2));                 // normal: x right, y down, z to viewer
	vec3 rf = 2.0 * n.z * n - vec3(0.0, 0.0, 1.0);    // mirror reflection

	// Tilted coordinate space: horizon crosses the ball naturally
	vec3 d = vec3(rf.x, dot(rf, TILT_V), dot(rf, TILT_U));

	// 1. Chrome steel base reflection
	vec3 col = room_env(d);

	// 2. Mirrored table elements on the downward-facing belly of the ball (p.y > 0)
	// Only the lower face facing the table reflects the playfield art & inserts.
	// We strictly fade out towards the outer rim (r > 0.75) to prevent any transparent glass halo!
	if (p.y > 0.0 && r < 0.85) {
		float belly = smoothstep(0.0, 0.55, p.y) * smoothstep(0.85, 0.60, r);
		// Sample playfield ahead of the ball
		vec2 rel = vec2(n.x * 2.2, (n.y + 0.3) * 3.5) * ball_r;
		vec3 pfc = live > 0.5 ? live_at(rel, sc, sk) : texture(pf, (ball_pos + rel) / table_size).rgb;
		// Blend vivid table colors cleanly into polished chrome steel
		vec3 table_refl = mix(pfc * 1.15, vec3(0.78, 0.80, 0.85), 0.35) - elev * 0.04;
		col = mix(col, table_refl, belly * 0.55);
	}

	// 3. Rolling micro-grain (tangible physical spin)
	vec3 nl = rot * n;
	float grain = vnoise(nl * 10.0) * 0.6 + vnoise(nl * 24.0) * 0.4;
	col *= 0.92 + 0.14 * grain;

	// 4. Primary key spotlight + optical diffraction starburst rays (promienie)
	vec3 k = normalize(KEY);
	float kd = max(dot(rf, k), 0.0);
	// Broad metallic specular gloss
	col += vec3(0.92, 0.95, 1.0) * pow(max(kd, 1e-4), 16.0) * 0.45;
	col += vec3(1.0, 0.98, 0.95) * pow(max(kd, 1e-4), 65.0) * 1.10;
	// Blinding core highlight
	col += vec3(1.0, 1.0, 1.0) * (smoothstep(0.982, 0.995, kd) * 4.2 + pow(max(kd, 1e-4), 340.0) * 2.0);
	// Optical starburst diffraction rays
	float key_rays = spec_rays(rf, k, kd);
	col += vec3(1.0, 0.99, 0.95) * (key_rays * 4.0);

	// Secondary fill glint
	vec3 f_dir = normalize(FILL);
	float fd = max(dot(rf, f_dir), 0.0);
	col += vec3(0.85, 0.90, 1.0) * (pow(max(fd, 1e-4), 140.0) * 0.70 + pow(max(fd, 1e-4), 18.0) * 0.12);

	// 5. Dynamic lights (flashers, glowing bumpers, lit inserts)
	vec3 hot = vec3(0.0);
	vec3 wash = vec3(0.0);
	vec3 P = vec3(n.xy * ball_r, ball_r * (1.0 + n.z));
	for (int i = 0; i < 8; i++) {
		vec3 lc = lcol[i].rgb;
		if (dot(lc, lc) < 1e-5) {
			continue;
		}
		vec3 L = normalize(lpos[i].xyz - P);
		float dl = max(dot(rf, L), 0.0);
		float nd = max(dot(n, L), 0.0);
		// Sharp specular glint + diffraction rays
		float spec = smoothstep(0.970, 0.992, dl) * 3.6 + pow(max(dl, 1e-4), 55.0) * 0.80;
		float l_rays = spec_rays(rf, L, dl);
		hot += lc * (spec + l_rays * 3.2);
		// Metallic wash on the light-facing side
		wash += lc * (pow(nd, 3.2) * 0.35 + pow(max(dl, 1e-4), 8.0) * 0.18);
	}
	col = col + wash * 0.22 + hot;
	col *= tint * boost;

	// 6. Solid metal silhouette: contact shadow at bottom & crisp perimeter outline
	float contact = smoothstep(0.78, 0.98, r) * smoothstep(0.2, 0.85, p.y);
	col *= 1.0 - 0.42 * contact;

	// Dark perimeter contour so ball pops sharply on both dark and light art
	col *= 1.0 - 0.58 * smoothstep(0.960, 0.996, r);

	return vec4(col, a);
}

void fragment() {
	vec2 q = (UV * 2.0 - 1.0) * quad;               // in ball radii
	float aa = max(fwidth(q.x) * 1.5, 0.02);
	float dqx = dFdx(q.x);
	float dqy = dFdy(q.y);
	vec2 sk = vec2(abs(dqx) > 1e-6 ? dFdx(SCREEN_UV.x) / dqx : 0.0,
			abs(dqy) > 1e-6 ? dFdy(SCREEN_UV.y) / dqy : 0.0) / ball_r;
	vec2 sc = SCREEN_UV - q * ball_r * sk;
	float sp = length(vel);
	float bl = clamp(sp / 150.0 / ball_r - 0.35, 0.0, 0.7);
	if (bl <= 0.001) {
		COLOR = shade(q, aa, sc, sk);
	} else {
		vec2 dir = normalize(vel) * (bl * ball_r);
		vec4 c = shade(q, aa, sc, sk) * 0.44;
		c += shade(q - dir * 0.5, aa, sc, sk) * 0.28;
		c += shade(q - dir, aa, sc, sk) * 0.28;
		COLOR = c;
	}
}
