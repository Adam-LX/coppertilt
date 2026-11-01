shader_type canvas_item;
// Amiga-style copper bars + raster background with animated table-specific themes.
// Features:
// - Authentic Amiga copper raster bars sweeping vertically (themed per table)
// - Dynamic searchlights / tracking beams / stadium floodlights
// - Twinkling retro starfield
// - Table-specific lighting effects (carnival neon, rocket launch beacons, stadium camera flashes)
// - Fallback to checker floor when no panorama is set

uniform vec2 rect_size = vec2(1280.0, 720.0);
uniform float speed = 1.0;
uniform float floor_start = 0.72;   // 0..1, where the checker floor begins (>=1 disables)
uniform float brightness = 1.0;
uniform float line_px = 2.0;        // raster line height in pixels
uniform sampler2D panorama_tex : filter_linear, repeat_disable;
uniform bool use_panorama = true;
uniform int theme_idx = 0;          // 0 = midnight_funfair, 1 = launch_pad, 2 = copper_speedway

vec3 bar_hue(float i) {
	return 0.5 + 0.5 * cos(6.28318 * (i / 7.0 + vec3(0.05, 0.35, 0.65)));
}

// Table-specific copper bar palettes
vec3 table_bar_hue(float i, int theme) {
	if (theme == 1) {
		// Launch Pad: Deep space navy, aerospace cyan, electric cobalt, sodium rocket flame orange
		float phase = fract(i / 5.0);
		if (phase < 0.25) return mix(vec3(0.1, 0.2, 0.6), vec3(0.15, 0.6, 0.95), phase * 4.0);
		if (phase < 0.50) return mix(vec3(0.15, 0.6, 0.95), vec3(0.95, 0.55, 0.15), (phase - 0.25) * 4.0);
		if (phase < 0.75) return mix(vec3(0.95, 0.55, 0.15), vec3(0.8, 0.2, 0.1), (phase - 0.50) * 4.0);
		return mix(vec3(0.8, 0.2, 0.1), vec3(0.1, 0.2, 0.6), (phase - 0.75) * 4.0);
	} else if (theme == 2) {
		// Copper Speedway: British racing green, fiery copper, blazing amber, tachometer red
		float phase = fract(i / 5.0);
		if (phase < 0.25) return mix(vec3(0.05, 0.45, 0.25), vec3(0.95, 0.55, 0.15), phase * 4.0);
		if (phase < 0.50) return mix(vec3(0.95, 0.55, 0.15), vec3(1.0, 0.25, 0.1), (phase - 0.25) * 4.0);
		if (phase < 0.75) return mix(vec3(1.0, 0.25, 0.1), vec3(0.9, 0.8, 0.2), (phase - 0.50) * 4.0);
		return mix(vec3(0.9, 0.8, 0.2), vec3(0.05, 0.45, 0.25), (phase - 0.75) * 4.0);
	}
	// Midnight Funfair default
	return bar_hue(i);
}

float star_hash(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

void fragment() {
	vec2 px = UV * rect_size;
	float ly = floor(px.y / line_px) * line_px;
	float y = ly / rect_size.y;
	float t = TIME * speed;

	// Check if panorama is available
	vec4 pano = vec4(0.0);
	bool has_pano = false;
	vec2 p_uv = vec2(0.0);

	if (use_panorama) {
		vec2 p_size = vec2(480.0, 270.0);
		float ak = max(rect_size.y / p_size.y, rect_size.x / p_size.x);
		vec2 scaled_size = p_size * ak;
		vec2 offset = (rect_size - scaled_size) * 0.5;
		p_uv = (px - offset) / scaled_size;

		if (p_uv.x >= 0.0 && p_uv.x <= 1.0 && p_uv.y >= 0.0 && p_uv.y <= 1.0) {
			pano = texture(panorama_tex, p_uv);
			if (pano.a > 0.05) {
				has_pano = true;
			}
		}
	}

	vec3 col = vec3(0.0);

	if (has_pano) {
		float lum = dot(pano.rgb, vec3(0.299, 0.587, 0.114));
		// Sky area: upper portion with dark ambient sky
		float is_sky = clamp(1.0 - (p_uv.y - 0.22) / 0.55, 0.0, 1.0) * (1.0 - smoothstep(0.20, 0.65, lum));

		// 1. Amiga Copper bars (flowing horizontal colour waves on the night sky)
		vec3 copper_col = vec3(0.0);
		for (int i = 0; i < 5; i++) {
			float fi = float(i);
			float c = 0.28 + 0.22 * sin(t * 0.75 + fi * 0.92);
			float w = 0.085;
			float d = abs(y - c) / w;
			if (d < 1.0) {
				float shade = 1.0 - d;
				float pulse = 0.75 + 0.25 * sin(t * 1.4 + fi * 1.3);
				copper_col += table_bar_hue(fi + t * 0.07, theme_idx) * (shade * pulse) * 0.28;
			}
		}

		// 2. Searchlights / Tracking Beams (customized per table)
		vec3 searchlights = vec3(0.0);
		if (theme_idx == 1) {
			// Launch Pad: High-power vertical xenon tracking beams scanning orbital paths
			vec2 b1_orig = vec2(0.14, 0.75);
			vec2 d1 = UV - b1_orig;
			float a1 = atan(d1.x, -d1.y);
			float s1 = sin(t * 0.35) * 0.35;
			float beam1 = exp(-pow((a1 - s1) * 14.0, 2.0)) * clamp(-d1.y, 0.0, 1.0);

			vec2 b2_orig = vec2(0.85, 0.75);
			vec2 d2 = UV - b2_orig;
			float a2 = atan(d2.x, -d2.y);
			float s2 = cos(t * 0.28 + 0.8) * 0.38;
			float beam2 = exp(-pow((a2 - s2) * 14.0, 2.0)) * clamp(-d2.y, 0.0, 1.0);

			searchlights = vec3(0.3, 0.85, 1.0) * beam1 * 0.25 + vec3(0.9, 0.95, 1.0) * beam2 * 0.22;
		} else if (theme_idx == 2) {
			// Copper Speedway: Wide criss-crossing stadium floodlights sweeping the circuit
			vec2 b1_orig = vec2(0.08, 0.70);
			vec2 d1 = UV - b1_orig;
			float a1 = atan(d1.x, -d1.y);
			float s1 = sin(t * 0.65) * 0.75;
			float beam1 = exp(-pow((a1 - s1) * 7.0, 2.0)) * clamp(-d1.y, 0.0, 1.0);

			vec2 b2_orig = vec2(0.92, 0.70);
			vec2 d2 = UV - b2_orig;
			float a2 = atan(d2.x, -d2.y);
			float s2 = cos(t * 0.52 + 1.8) * 0.72;
			float beam2 = exp(-pow((a2 - s2) * 7.0, 2.0)) * clamp(-d2.y, 0.0, 1.0);

			searchlights = vec3(1.0, 0.85, 0.45) * beam1 * 0.24 + vec3(1.0, 0.65, 0.3) * beam2 * 0.20;
		} else {
			// Midnight Funfair: Dual searchlights in cyan & carnival pink
			vec2 b1_orig = vec2(0.22, 0.78);
			vec2 d1 = UV - b1_orig;
			float a1 = atan(d1.x, -d1.y);
			float s1 = sin(t * 0.55) * 0.62;
			float beam1 = exp(-pow((a1 - s1) * 8.5, 2.0)) * clamp(-d1.y, 0.0, 1.0);

			vec2 b2_orig = vec2(0.72, 0.74);
			vec2 d2 = UV - b2_orig;
			float a2 = atan(d2.x, -d2.y);
			float s2 = cos(t * 0.44 + 1.3) * 0.68;
			float beam2 = exp(-pow((a2 - s2) * 8.5, 2.0)) * clamp(-d2.y, 0.0, 1.0);

			searchlights = vec3(0.4, 0.75, 1.0) * beam1 * 0.20 + vec3(1.0, 0.45, 0.7) * beam2 * 0.17;
		}

		// 3. Twinkling Stars in the night sky
		vec2 star_grid = floor(px / 18.0);
		float sh = star_hash(star_grid);
		float star = 0.0;
		if (sh > 0.965 && is_sky > 0.35) {
			float twinkle = sin(t * 3.2 + sh * 62.8) * 0.5 + 0.5;
			vec2 cell_pos = fract(px / 18.0) - vec2(0.5);
			if (length(cell_pos) < 0.22) {
				star = twinkle * (0.65 + 0.35 * sh);
			}
		}
		vec3 star_col = mix(vec3(0.9, 0.95, 1.0), vec3(1.0, 0.85, 0.5), sh) * star;

		// 4. Table-specific light animations
		float light_mask = smoothstep(0.35, 0.82, lum);
		float neon_anim = 0.85 + 0.15 * sin(t * 4.2 + p_uv.x * 30.0 + p_uv.y * 18.0);
		if (theme_idx == 1) {
			// Rocket beacon pulses & cryogenic vapor shimmer
			neon_anim = 0.88 + 0.12 * sin(t * 3.0 + p_uv.y * 22.0);
		} else if (theme_idx == 2) {
			// Camera flashes & start light strobe
			neon_anim = 0.82 + 0.18 * sin(t * 6.0 + p_uv.x * 40.0);
		}
		vec3 pano_col = pano.rgb;
		pano_col += pano_col * light_mask * (neon_anim - 1.0) * 0.8;

		// Combine layers
		col = pano_col + (copper_col + searchlights) * is_sky + star_col;

		// Vignette
		float vig = 1.0 - smoothstep(0.42, 0.95, length(UV - vec2(0.5)));
		col *= mix(0.88, 1.0, vig);
	} else {
		// Fallback: standalone copper bars + checker floor
		col = mix(vec3(0.03, 0.0, 0.10), vec3(0.10, 0.0, 0.18), y);
		col += 0.05 * vec3(0.5 + 0.5 * sin(ly * 0.05 + t), 0.0, 0.5 + 0.5 * cos(ly * 0.04 - t));

		for (int i = 0; i < 7; i++) {
			float fi = float(i);
			float c = 0.42 + 0.30 * sin(t * 1.3 + fi * 0.62);
			float w = 0.055;
			float d = abs(y - c) / w;
			if (d < 1.0) {
				float shade = 1.0 - d;
				col = table_bar_hue(fi + floor(t * 0.15), theme_idx) * (0.25 + 0.95 * shade) + vec3(pow(shade, 10.0));
			}
		}

		if (y > floor_start) {
			float h = (y - floor_start) / (1.0 - floor_start);
			float z = 1.0 / (h + 0.05);
			float fx = (px.x / rect_size.x - 0.5) * z * 6.0;
			float fz = z * 1.5 + t * 2.0;
			float chk = mod(floor(fx) + floor(fz), 2.0);
			vec3 a = vec3(0.95, 0.25, 0.55);
			vec3 b = vec3(0.12, 0.0, 0.30);
			vec3 fc = mix(b, a, chk) * (0.35 + 0.65 * h);
			col = mix(fc, col, 0.15);
			col += vec3(1.0, 0.5, 0.2) * exp(-h * 18.0) * 0.6;
		}
	}

	col *= brightness;
	// Quantise to OCS 12-bit palette (4 bits per channel, 0..15)
	col = floor(clamp(col, 0.0, 1.0) * 15.0 + 0.5) / 15.0;
	COLOR = vec4(col, 1.0);
}
