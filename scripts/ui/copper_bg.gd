class_name CopperBackdrop
extends ColorRect
## Full-rect Amiga copper-bar backdrop. Keeps the shader's rect_size in sync.

const SHADER := preload("res://shaders/copper.gdshader")

@export var floor_start := 0.72
@export var speed := 1.0
@export var brightness := 1.0
@export var panorama: Texture2D = null
@export var theme_idx := 0


func _ready() -> void:
	var m := ShaderMaterial.new()
	m.shader = SHADER
	material = m
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(_sync)
	_sync()


func _sync() -> void:
	var m := material as ShaderMaterial
	if not m:
		return
	m.set_shader_parameter("rect_size", size)
	m.set_shader_parameter("floor_start", floor_start)
	m.set_shader_parameter("speed", speed)
	m.set_shader_parameter("brightness", brightness)
	m.set_shader_parameter("theme_idx", theme_idx)
	if panorama:
		m.set_shader_parameter("panorama_tex", panorama)
		m.set_shader_parameter("use_panorama", true)
	else:
		m.set_shader_parameter("use_panorama", false)
