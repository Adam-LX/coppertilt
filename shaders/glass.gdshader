shader_type canvas_item;
render_mode blend_add;
// Playfield glass (modern style): two broad, very soft reflections of the room lights that drift a
// little, brighter toward the back of the cabinet. Additive and faint so the ball/arrows stay clear.
uniform float t = 0.0;
uniform float strength = 0.05;
uniform float aspect = 1.0;

void fragment() {
	vec2 p = UV;
	p.x *= aspect;
	float d = p.x * 0.55 - p.y * 0.35;
	float a = smoothstep(0.20, 0.0, abs(fract(d + 0.15 + sin(t * 0.21) * 0.03) - 0.5));
	float b = smoothstep(0.045, 0.0, abs(fract(d + 0.40 + sin(t * 0.17) * 0.02) - 0.5));
	float back = mix(1.0, 0.3, UV.y);
	float v = (a * 0.55 + b * 1.0) * back * strength;
	COLOR = vec4(vec3(0.85, 0.9, 1.0) * v, 1.0);
}
