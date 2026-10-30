// 3D view: shadow caster of a ramp ribbon (cast_shadow = shadows only): the painted deck and
// wires cut out of the projected ramp art.
shader_type spatial;
render_mode cull_disabled, unshaded;

uniform sampler2D ramp_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D owner_tex : filter_nearest, repeat_disable;
uniform vec2 table_size = vec2(320.0, 640.0);
uniform float my_id = 0.0;
uniform float cut = 0.35;

varying vec2 wp;

void vertex() {
	wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz;
}

void fragment() {
	vec2 uv = wp / table_size;
	float a = texture(ramp_tex, uv).a;
	if (abs(texture(owner_tex, uv).r - my_id) > 0.06) {
		a = 0.0;
	}
	ALBEDO = vec3(0.0);
	ALPHA = a;
	ALPHA_SCISSOR_THRESHOLD = cut;
}
