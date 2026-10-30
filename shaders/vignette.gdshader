shader_type canvas_item;
// Subtle vignette over the table view: darkens the corners/edges a little for depth.
// steps > 0 quantises it into bands (pixel / Amiga style).
uniform float strength = 0.30;
uniform float steps = 0.0;
uniform float aspect = 1.0;

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	p.x *= mix(1.0, 0.85, clamp(aspect - 1.0, 0.0, 1.0));
	float r = length(p * vec2(0.85, 1.0));
	float v = smoothstep(0.75, 1.45, r);
	if (steps > 0.0) {
		v = floor(v * steps + 0.5) / steps;
	}
	COLOR = vec4(0.0, 0.0, 0.02, v * strength);
}
