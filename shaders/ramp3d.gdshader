// 3D view: ramp decks / wireforms. The flat top-view ramp art is projected by world xz onto a
// raised ribbon per ramp; ramp_owner.png (tools/bake_ramp_owner.py) keeps each painted pixel on
// exactly one ribbon. Same sweeping glint as the 2D plastic shader.
shader_type spatial;
render_mode blend_mix, cull_disabled, ambient_light_disabled, depth_draw_never;

uniform sampler2D ramp_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D spec_tex : hint_default_black, filter_linear_mipmap, repeat_disable;
uniform sampler2D owner_tex : filter_nearest, repeat_disable;
uniform vec2 table_size = vec2(320.0, 640.0);
uniform vec3 tint = vec3(0.96, 0.95, 0.98);
uniform float my_id = 0.0;
uniform float t = 0.0;
uniform float glint = 1.0;
uniform float alpha_boost = 1.0;

varying vec2 wp;

void vertex() {
	wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz;
}

void fragment() {
	vec2 uv = wp / table_size;
	if (abs(texture(owner_tex, uv).r - my_id) > 0.06) {
		discard;
	}
	vec4 c = texture(ramp_tex, uv);
	float s = texture(spec_tex, uv).r;
	float band = fract((wp.x * 0.7 + wp.y * 0.35) / 300.0 - t * 0.06);
	float g = smoothstep(0.03, 0.0, abs(band - 0.5)) * s * glint;
	ALBEDO = c.rgb * tint;
	EMISSION = vec3(g) * 0.8;
	ALPHA = clamp(c.a * alpha_boost + g * 0.4, 0.0, 1.0);
	NORMAL = vec3(0.0, 0.0, 1.0);
}

void light() {
	if (LIGHT_IS_DIRECTIONAL) {
		DIFFUSE_LIGHT += vec3(1.0);
	} else {
		vec3 c = LIGHT_COLOR * ATTENUATION / PI;
		DIFFUSE_LIGHT += c * 0.8;
		SPECULAR_LIGHT += c * 0.25;
	}
}
