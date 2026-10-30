shader_type canvas_item;
// Ramps / raised plastics (modern style): clear plastic refracts what lies under it (with a touch of
// chromatic split), opaque parts keep their painted colour, and a slow light glint sweeps over the
// glossy plastic and chrome (masked by the specular map). Normal-mapped 2D lights still apply.
// Animation is driven by `t` (table time) so frozen still frames are identical.
uniform sampler2D screen_tex : hint_screen_texture, filter_linear;
uniform float refract_texels = 9.0;
uniform float t = 0.0;
uniform vec2 table_size = vec2(320.0, 640.0);
uniform float glint = 0.5;

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	if (c.a < 0.004) {
		discard;
	}
	vec3 n = texture(NORMAL_TEXTURE, UV).rgb * 2.0 - 1.0;
	float sp = texture(SPECULAR_SHININESS_TEXTURE, UV).r;
	// screen pixels per texture pixel (camera zoom)
	float du = length(vec2(dFdx(UV.x), dFdy(UV.x)));
	float px_per_texel = TEXTURE_PIXEL_SIZE.x / max(du, 1e-7);
	vec2 o = n.xy * vec2(1.0, -1.0) * refract_texels * px_per_texel * SCREEN_PIXEL_SIZE * (1.0 - c.a);
	vec3 bg;
	bg.r = texture(screen_tex, SCREEN_UV + o * 1.12).r;
	bg.g = texture(screen_tex, SCREEN_UV + o).g;
	bg.b = texture(screen_tex, SCREEN_UV + o * 0.88).b;
	vec3 col = mix(bg, c.rgb, c.a);
	vec2 p = UV * table_size;
	float band = fract((p.x * 0.7 + p.y * 0.35) / 300.0 - t * 0.06);
	float g = smoothstep(0.03, 0.0, abs(band - 0.5)) * sp * glint;
	col += vec3(1.0, 0.97, 0.9) * g;
	COLOR = vec4(col, clamp(c.a * 6.0, 0.0, 1.0));
}
