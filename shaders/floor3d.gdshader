// 3D view: the painted playfield (and sling plastics) projected top-down by world xz.
// Lit so that with no shadow it looks exactly like the 2D art (x tint); the sun only
// darkens where something casts a shadow, coloured omni lights (flashers, bumpers,
// inserts) add on top.
shader_type spatial;
render_mode ambient_light_disabled, cull_disabled;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_disable;
uniform sampler2D spec_tex : hint_default_black, filter_linear_mipmap, repeat_disable;
uniform vec2 table_size = vec2(320.0, 640.0);
uniform vec3 tint = vec3(0.96, 0.95, 0.98);
uniform float shade = 0.5;         // light left in a full shadow
uniform float normal_strength = 0.6;
uniform float omni_gain = 1.0;

varying vec2 wp;
varying float sp;

void vertex() {
	wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz;
}

void fragment() {
	vec2 uv = wp / table_size;
	ALBEDO = texture(albedo_tex, uv).rgb * tint;
	vec3 n = texture(normal_tex, uv).rgb * 2.0 - 1.0;
	// view space of the top-down camera: x = table x, y = -table y (screen up), z = up
	NORMAL = normalize(vec3(n.x * normal_strength, n.y * normal_strength, 1.0));
	sp = texture(spec_tex, uv).r;
	ROUGHNESS = mix(0.18, 0.32, 1.0 - sp * 0.7);
	METALLIC = sp * 0.15;
	SPECULAR = 0.5 + 0.5 * sp;
}

void light() {
	float nd = clamp(dot(NORMAL, LIGHT), 0.0, 1.0);
	if (LIGHT_IS_DIRECTIONAL) {
		DIFFUSE_LIGHT += vec3(mix(shade, 1.0, ATTENUATION) * clamp(nd / 0.79, 0.0, 1.2));
		vec3 h_dir = normalize(VIEW + LIGHT);
		float spec_d = pow(max(dot(NORMAL, h_dir), 0.0), 48.0);
		SPECULAR_LIGHT += LIGHT_COLOR * spec_d * (0.10 + 0.75 * sp) * ATTENUATION;
	} else {
		vec3 c = LIGHT_COLOR * ATTENUATION * omni_gain / PI;
		DIFFUSE_LIGHT += c * nd;
		vec3 h = normalize(VIEW + LIGHT);
		float spec_omni = pow(max(dot(NORMAL, h), 0.0), 60.0) * 0.95 + pow(max(dot(NORMAL, h), 0.0), 16.0) * 0.30;
		SPECULAR_LIGHT += c * spec_omni * (0.22 + 1.5 * sp);
	}
}
