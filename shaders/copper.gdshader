shader_type canvas_item;
// Amiga-style copper bars + raster background with a scrolling checker floor.
// Colours are quantised to the OCS 12-bit palette (4 bits per channel).

uniform vec2 rect_size = vec2(1280.0, 720.0);
uniform float speed = 1.0;
uniform float floor_start = 0.72;   // 0..1, where the checker floor begins (>=1 disables)
uniform float brightness = 1.0;
uniform float line_px = 2.0;        // raster line height in pixels

vec3 bar_hue(float i) {
	return 0.5 + 0.5 * cos(6.28318 * (i / 7.0 + vec3(0.0, 0.33, 0.67)));
}

void fragment() {
	vec2 px = UV * rect_size;
	float ly = floor(px.y / line_px) * line_px;
	float y = ly / rect_size.y;
	float t = TIME * speed;

	// raster background: slow vertical colour cycle like a copper list
	vec3 col = mix(vec3(0.03, 0.0, 0.10), vec3(0.10, 0.0, 0.18), y);
	col += 0.05 * vec3(0.5 + 0.5 * sin(ly * 0.05 + t), 0.0, 0.5 + 0.5 * cos(ly * 0.04 - t));

	// copper bars: later bars overwrite earlier ones, as on the real chip
	for (int i = 0; i < 7; i++) {
		float fi = float(i);
		float c = 0.42 + 0.30 * sin(t * 1.3 + fi * 0.62);
		float w = 0.055;
		float d = abs(y - c) / w;
		if (d < 1.0) {
			float shade = 1.0 - d;
			col = bar_hue(fi + floor(t * 0.15)) * (0.25 + 0.95 * shade) + vec3(pow(shade, 10.0));
		}
	}

	// checker floor with perspective, scrolling toward the viewer
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
		// horizon glow
		col += vec3(1.0, 0.5, 0.2) * exp(-h * 18.0) * 0.6;
	}

	col *= brightness;
	col = floor(clamp(col, 0.0, 1.0) * 15.0 + 0.5) / 15.0;
	COLOR = vec4(col, 1.0);
}
