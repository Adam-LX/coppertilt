// 3D view: textured part (bumper cap, flipper top, drop face, carousel) that can flash.
shader_type spatial;
render_mode cull_disabled;

uniform sampler2D tex : source_color, filter_linear_mipmap, repeat_disable;
uniform vec3 tint = vec3(0.96, 0.95, 0.98);
uniform float flash = 0.0;
uniform vec3 flash_color = vec3(1.0, 0.85, 0.6);
uniform float rough = 0.35;
uniform float metal = 0.0;
uniform float self_lit = 0.55;     // part of the art shown regardless of light (keeps 2D colours)

void fragment() {
	vec3 c = texture(tex, UV).rgb * tint;
	ALBEDO = c * (1.0 - self_lit);
	EMISSION = c * self_lit + c * flash_color * flash * 2.2;
	ROUGHNESS = rough;
	METALLIC = metal;
	SPECULAR = 0.75;
}
