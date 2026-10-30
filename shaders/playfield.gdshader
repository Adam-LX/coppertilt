shader_type canvas_item;
// "Neon Harbor" playfield art, painted procedurally in table space (600x1800 units).
// Chunky 2-unit pixels, 12-bit palette and 4x4 ordered dithering for a pixel-painted Amiga look.

varying vec2 wp;

void vertex() {
	wp = VERTEX;
}

float hash(float n) { return fract(sin(n * 12.9898) * 43758.5453); }
float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float bayer4(vec2 p) {
	int x = int(mod(p.x, 4.0));
	int y = int(mod(p.y, 4.0));
	int i = x + y * 4;
	float m[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
	return m[i] / 16.0 - 0.5;
}

void fragment() {
	vec2 cell = floor(wp / 2.0);
	vec2 p = cell * 2.0;
	float t = TIME;
	float horizon = 1010.0;

	// night sky: violet top fading to hot pink at the horizon
	float sy = clamp(p.y / horizon, 0.0, 1.0);
	vec3 col = mix(vec3(0.07, 0.02, 0.20), vec3(0.75, 0.18, 0.45), pow(sy, 2.2));

	// stars
	float st = hash2(floor(p / 6.0));
	if (p.y < 760.0 && st > 0.985) {
		col += vec3(0.8, 0.8, 1.0) * (0.5 + 0.5 * sin(t * 3.0 + st * 80.0));
	}

	// striped synthwave sun
	vec2 sc = vec2(300.0, 905.0);
	float d = length(p - sc);
	if (d < 150.0 && p.y < horizon) {
		float k = clamp((p.y - 800.0) / 200.0, 0.0, 1.0);
		float gap = mod(p.y, 20.0) < k * 11.0 ? 1.0 : 0.0;
		vec3 sun = mix(vec3(1.0, 0.92, 0.35), vec3(1.0, 0.25, 0.55), clamp((p.y - 760.0) / 240.0, 0.0, 1.0));
		col = mix(sun, col, gap);
	} else if (p.y < horizon) {
		col += vec3(0.9, 0.3, 0.4) * exp(-(d - 150.0) / 60.0) * 0.35;
	}

	// harbour skyline + cranes silhouette
	float bx = floor(p.x / 22.0);
	float bh = 25.0 + hash(bx) * 85.0 + (abs(p.x - 300.0) > 160.0 ? 40.0 : 0.0);
	if (p.y < horizon && p.y > horizon - bh) {
		col = vec3(0.10, 0.03, 0.16);
		vec2 wcell = floor(vec2(p.x / 6.0, p.y / 8.0));
		if (mod(p.x, 6.0) < 3.0 && mod(p.y, 8.0) < 4.0 && hash2(wcell) > 0.72) {
			col = mix(vec3(1.0, 0.8, 0.3), vec3(0.3, 0.9, 1.0), step(0.9, hash2(wcell + 7.0)));
		}
	}
	// crane arms
	if (abs(p.y - (horizon - 175.0)) < 3.0 && p.x > 40.0 && p.x < 170.0) col = vec3(0.12, 0.03, 0.18);
	if (abs(p.x - 70.0) < 3.0 && p.y > horizon - 178.0 && p.y < horizon) col = vec3(0.12, 0.03, 0.18);

	// water: deep blue, animated reflection streaks of sun and city lights
	if (p.y >= horizon) {
		float wy = (p.y - horizon) / 790.0;
		col = mix(vec3(0.16, 0.05, 0.30), vec3(0.01, 0.02, 0.09), clamp(wy * 1.6, 0.0, 1.0));
		float wave = sin(p.y * 0.35 - t * 2.2 + sin(p.x * 0.04 + t) * 2.0);
		float spread = 150.0 * (1.0 - wy * 0.5);
		if (abs(p.x - 300.0) < spread && wave > 0.55 && wy < 0.6) {
			col = mix(col, vec3(1.0, 0.45, 0.55), 0.7 * (1.0 - wy / 0.6));
		}
		if (hash2(floor(vec2(p.x / 22.0, p.y / 6.0))) > 0.93 && wave > 0.0 && wy < 0.3) {
			col += vec3(0.4, 0.35, 0.15) * (1.0 - wy / 0.3);
		}
		// perspective neon grid in the deep water
		float gz = 1.0 / max(wy, 0.02);
		if (wy > 0.35) {
			float gx = (p.x - 300.0) / (12.0 + (1.0 - wy) * 30.0);
			float gl = step(0.92, fract(gx)) + step(0.9, fract(gz * 3.0 - t * 0.6));
			col = mix(col, vec3(0.1, 0.8, 1.0), clamp(gl, 0.0, 1.0) * 0.35 * wy);
		}
	}

	// rail-side vignette (painted shadow near walls)
	float edge = min(p.x - 20.0, 585.0 - p.x);
	col *= 0.55 + 0.45 * clamp(edge / 50.0, 0.0, 1.0);

	// dithered 12-bit quantisation
	col = floor(clamp(col, 0.0, 1.0) * 15.0 + 0.5 + bayer4(cell)) / 15.0;
	COLOR = vec4(col, 1.0);
}
