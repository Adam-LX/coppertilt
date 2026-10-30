shader_type canvas_item;
// Round plasma dots with a soft halo; TEXTURE is an L8 intensity grid (one texel per dot).
uniform vec2 grid = vec2(128.0, 16.0);
uniform vec4 lit : source_color = vec4(1.0, 0.55, 0.1, 1.0);
uniform vec4 off : source_color = vec4(0.13, 0.045, 0.02, 1.0);

void fragment() {
	vec2 cell = UV * grid;
	vec2 id = floor(cell);
	vec2 f = fract(cell) - 0.5;
	float v = texture(TEXTURE, (id + 0.5) / grid).r;
	float d = length(f);
	float core = 1.0 - smoothstep(0.30, 0.42, d);
	float halo = (1.0 - smoothstep(0.2, 0.75, d)) * 0.35;
	vec3 base = vec3(0.015, 0.006, 0.0);
	vec3 dotc = mix(off.rgb, lit.rgb * (0.55 + 0.45 * v), v);
	vec3 col = mix(base, dotc, core) + lit.rgb * halo * v * v;
	// specular pip on lit dots
	col += vec3(1.0, 0.9, 0.7) * v * (1.0 - smoothstep(0.0, 0.12, length(f + vec2(0.1, 0.12)))) * 0.5;
	COLOR = vec4(col, 1.0);
}
