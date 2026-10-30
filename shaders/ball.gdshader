shader_type canvas_item;
// Polished silver steel pinball seen from above. A real ball is a near-perfect mirror of a BRIGHT
// world (the lit room / glass / backbox overhead and the lit playfield around it), so it reads as
// polished silver (mean luminance ~0.75) through sharp detail, not through dark mass:
//  - upper part (rays going up; "up" is tilted to the top of the screen like a 3/4 view): bright
//    room / glass with a warm lit backbox panel, a big key-light window and a strip light;
//    the only dark part is a narrow cabinet band just above the horizon,
//  - a bright, slightly warm horizon line,
//  - lower part (rays going down): the real playfield art around the ball, mirrored, colourful but
//    lifted, and neutralised towards the rim so no coloured ring / halo follows the silhouette,
//  - a tiny, very bright, hard white key highlight plus a dim fill glint and flasher glints,
//  - a thin neutral dark edge line so the ball separates from bright art as well as from dark art,
//  - a rolling layer (GI dots + micro-wear, rotated by the ball's spin) so the reflection visibly turns,
//  - subtle motion blur along the velocity at high speed (the quad is `quad` x the ball).
// No shadow is drawn in the quad (no concentric ring): table.gd draws the soft drop shadow offset to
// the lower right and the small contact patch under the ball.
render_mode unshaded;

uniform sampler2D env : filter_linear, repeat_enable;   // GI / room map (equirect), rolls with the ball
uniform sampler2D pf : filter_linear;                   // playfield art
uniform vec2 table_size = vec2(320.0, 640.0);
uniform vec2 ball_pos = vec2(0.0);
uniform float ball_r = 7.5;
uniform float quad = 1.6;
uniform mat3 rot = mat3(1.0);        // world -> ball-local (rolling)
uniform vec2 vel = vec2(0.0);        // table units / s
uniform float elev = 0.0;            // 0..1 ramp height
uniform vec4 lpos[4];                // light xy relative to the ball centre (units), z = height above the table
uniform vec4 lcol[4];                // rgb * energy
uniform float boost = 1.0;
uniform vec3 tint = vec3(1.0);

const vec3 KEY = vec3(-0.40, -0.60, 0.69);    // key light: upper left of the table, high
const vec3 FILL = vec3(0.55, 0.30, 0.78);
const vec3 TILT_U = vec3(0.0, -0.6816, 0.7317);   // world up in view space (tilt 0.75 rad)
const vec3 TILT_V = vec3(0.0, 0.7317, 0.6816);    // world "down the table" in view space

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

// the bright room above the playfield, in table space (x right, y down the table, z up); el 0 = horizon
vec3 room_env(vec3 d) {
	float el = d.z;
	// lit room / glass: bright near the horizon, a touch cooler and dimmer straight up
	vec3 c = mix(vec3(0.95, 0.94, 0.92), vec3(0.88, 0.89, 0.92), smoothstep(0.10, 0.95, el));
	// gentle falloff on the side away from the key light (keeps the ball round, stays bright)
	float up = smoothstep(0.35, 0.70, el);
	c *= mix(1.0, 0.80 + 0.20 * smoothstep(-0.7, 0.5, dot(d.xy, vec2(-0.55, -0.83))), up);
	// backbox: lit translite above the top of the table (towards -y), warm
	float bb = band(d.x / max(-d.y, 0.05), 0.0, 0.62, 0.05) * band(el, 0.30, 0.12, 0.03) * step(0.0, -d.y);
	c = mix(c, vec3(1.08, 0.94, 0.70), bb * 0.85);
	// big key-light window (upper left) split by a thin frame bar, plus a strip light opposite
	vec2 wq = abs(d.xy - vec2(-0.32, -0.44));
	float win = smoothstep(0.30, 0.28, wq.x) * smoothstep(0.21, 0.19, wq.y) * smoothstep(0.012, 0.020, abs(d.x + 0.32));
	float strip = band(d.y, 0.30, 0.035, 0.012) * band(d.x - 0.12, 0.0, 0.22, 0.05) * 0.8;
	c = mix(c, vec3(1.35, 1.34, 1.32), clamp(win + strip, 0.0, 1.0) * up);
	// the only dark part: a soft, narrow cabinet band just above the horizon, mostly on the backbox
	// side (a full-strength band all round would draw a concentric "eye" ring on the ball)
	float wall = band(el, 0.07, 0.035, 0.06) * (0.25 + 0.75 * smoothstep(-0.1, 0.7, -d.y));
	c = mix(c, vec3(0.40, 0.38, 0.44), wall * 0.55);
	return c;
}

vec4 shade(vec2 p, float aa) {
	float r = length(p);
	float a = smoothstep(1.0, 1.0 - aa, r);
	if (a <= 0.0) {
		return vec4(0.0);
	}
	float r2 = min(dot(p, p), 0.9999);
	vec3 n = vec3(p, sqrt(1.0 - r2));                 // screen coords: x right, y down, z to viewer
	vec3 rf = 2.0 * n.z * n - vec3(0.0, 0.0, 1.0);    // mirror reflection of the view ray
	// reflected world seen as by the usual 3/4 pinball camera: "up" tilted towards the top of the
	// screen, so the room / backbox fill the upper part of the ball and the table the lower part
	// (a horizon curve across the ball instead of a concentric eye-like ring)
	vec3 d = vec3(rf.x, dot(rf, TILT_V), dot(rf, TILT_U));
	float hz = 0.0;                                    // horizon (reflection) height
	// --- upper hemisphere: bright room (fixed, as a real mirror) plus the rolling GI layer
	vec3 sky = room_env(vec3(d.x, d.y, max(d.z - hz, 0.0)));
	vec3 rr = rot * rf;
	float u = atan(rr.y, rr.x) / 6.2831853 + 0.5;
	float v = acos(clamp(rr.z, -1.0, 1.0)) / 3.14159265;
	vec3 gi = texture(env, vec2(u, v * 0.5)).rgb;
	sky += gi * gi * 0.30 * smoothstep(0.92, 0.80, rr.z);   // GI dots only, not the map's top line
	// --- lower hemisphere: the playfield around the ball, mirrored: colourful but lifted
	vec3 P = vec3(n.xy * ball_r, ball_r * (1.0 + n.z));
	float t = P.z / max(-rf.z, 0.02);
	t = min(t, ball_r * 9.0);
	vec2 hit = ball_pos + P.xy + rf.xy * t;
	vec3 pfc = texture(pf, hit / table_size).rgb;
	vec3 floor_c = mix(pfc * 1.15, vec3(0.90, 0.89, 0.92), 0.45) - elev * 0.04;
	floor_c += max(0.58 - luma(floor_c), 0.0);         // bright even over dark art (no dark mass)
	// towards the rim the reflected table is right next to the ball: neutralise it (no coloured halo)
	floor_c = mix(floor_c, vec3(luma(floor_c)) * 0.92 + 0.06, smoothstep(0.80, 0.96, r) * 0.75);
	vec3 col = mix(sky, floor_c, smoothstep(hz + 0.06, hz - 0.06, d.z));
	// bright, slightly warm horizon line where the reflected table meets the room
	col += vec3(1.0, 0.97, 0.92) * 0.12 * exp(-pow((d.z - hz - 0.02) / 0.03, 2.0));
	// rolling micro-wear: faint smudges fixed to the steel (makes the spin visible)
	vec3 nl = rot * n;
	float w = vnoise(nl * 9.0) * 0.6 + vnoise(nl * 23.0) * 0.4;
	col *= 0.94 + 0.09 * w;
	// polished steel: neutral, very slightly cool; a gentle key-side gradient gives the ball volume
	col *= vec3(0.96, 0.97, 0.99) * (0.78 + 0.22 * smoothstep(-0.5, 0.95, dot(n, normalize(KEY))));
	// tiny, very bright, hard white key highlight (fixed to the light) + a dim fill glint + flashers
	float kd = max(dot(rf, normalize(KEY)), 0.0);
	col += vec3(1.0, 0.99, 0.96) * (smoothstep(0.986, 0.992, kd) * 3.0 + pow(kd, 160.0) * 0.4);
	float fd = max(dot(rf, normalize(FILL)), 0.0);
	col += vec3(0.9, 0.93, 1.0) * (smoothstep(0.9988, 0.9995, fd) * 0.9 + pow(fd, 120.0) * 0.10);
	for (int i = 0; i < 4; i++) {
		vec3 L = normalize(lpos[i].xyz - P);
		float dl = max(dot(rf, L), 0.0);
		col += lcol[i].rgb * (smoothstep(0.996, 0.999, dl) * 1.8 + pow(dl, 30.0) * 0.35);
	}
	col *= tint * boost;
	// thin neutral dark edge line (grazing angle), so the silhouette reads on bright art too
	col *= 1.0 - 0.62 * smoothstep(0.955, 0.995, r);
	return vec4(col, a);
}

void fragment() {
	vec2 q = (UV * 2.0 - 1.0) * quad;               // in ball radii
	float aa = max(fwidth(q.x) * 1.5, 0.02);
	float sp = length(vel);
	// subtle motion blur: ~1/150 s exposure, only at high speed, capped
	float bl = clamp(sp / 150.0 / ball_r - 0.35, 0.0, 0.7);
	if (bl <= 0.001) {
		COLOR = shade(q, aa);
	} else {
		vec2 dir = vel / sp;
		vec3 c = vec3(0.0);
		float s = 0.0;
		for (int i = 0; i < 7; i++) {
			vec4 o = shade(q - dir * bl * (float(i) / 6.0 - 0.5), aa);
			c += o.rgb * o.a;
			s += o.a;
		}
		COLOR = vec4(c / max(s, 1e-4), s / 7.0);
	}
}
