class_name DotMatrix
extends Control
## Orange plasma dot-matrix display (DMD) of any size, rendered by a dot shader from a
## cols x rows intensity buffer. Callers paint each frame with clear()/text()/dot() then
## call present(). Original 5x7 font, scalable 1x..3x.

const SHADER := preload("res://shaders/dmd.gdshader")
const GLYPHS := {
	"0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
	"2": "01110 10001 00001 00010 00100 01000 11111", "3": "11111 00010 00100 00010 00001 10001 01110",
	"4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
	"6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
	"8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
	"A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
	"C": "01110 10001 10000 10000 10000 10001 01110", "D": "11100 10010 10001 10001 10001 10010 11100",
	"E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
	"G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
	"I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
	"K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
	"M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
	"O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
	"Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
	"S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
	"U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
	"W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
	"Y": "10001 10001 10001 01010 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
	" ": "00000 00000 00000 00000 00000 00000 00000", "!": "00100 00100 00100 00100 00100 00000 00100",
	".": "00000 00000 00000 00000 00000 01100 01100", ",": "00000 00000 00000 00000 01100 00100 01000",
	"-": "00000 00000 00000 11111 00000 00000 00000", ":": "00000 01100 01100 00000 01100 01100 00000",
	"/": "00001 00010 00010 00100 01000 01000 10000", "+": "00000 00100 00100 11111 00100 00100 00000",
	"?": "01110 10001 00001 00010 00100 00000 00100", "x": "00000 00000 10001 01010 00100 01010 10001",
	"#": "01010 01010 11111 01010 11111 01010 01010",
}

@export var lit_color := Color(1.0, 0.55, 0.1)
@export var off_color := Color(0.13, 0.045, 0.02)

var cols := 128
var rows := 16
var buf := PackedByteArray()
var _img: Image
var _tex: ImageTexture
var _rows_cache := {}


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	for k in GLYPHS:
		_rows_cache[k] = (GLYPHS[k] as String).split(" ")
	var m := ShaderMaterial.new()
	m.shader = SHADER
	material = m
	resize_grid(cols, rows)


func resize_grid(c: int, r: int) -> void:
	cols = maxi(8, c)
	rows = maxi(7, r)
	buf.resize(cols * rows)
	buf.fill(0)
	_img = Image.create_from_data(cols, rows, false, Image.FORMAT_L8, buf)
	_tex = ImageTexture.create_from_image(_img)
	var m := material as ShaderMaterial
	m.set_shader_parameter("grid", Vector2(cols, rows))
	m.set_shader_parameter("lit", lit_color)
	m.set_shader_parameter("off", off_color)
	queue_redraw()


func clear() -> void:
	buf.fill(0)


func dot(x: int, y: int, v := 255) -> void:
	if x >= 0 and x < cols and y >= 0 and y < rows:
		var i := y * cols + x
		buf[i] = maxi(buf[i], v)


func line(x0: int, y0: int, x1: int, y1: int, v := 255) -> void:
	var dx := absi(x1 - x0)
	var sx := 1 if x0 < x1 else -1
	var dy := -absi(y1 - y0)
	var sy := 1 if y0 < y1 else -1
	var err := dx + dy
	while true:
		dot(x0, y0, v)
		if x0 == x1 and y0 == y1:
			break
		var e2 := 2 * err
		if e2 >= dy:
			err += dy
			x0 += sx
		if e2 <= dx:
			err += dx
			y0 += sy


func rect(x: int, y: int, w: int, h: int, v := 255, fill := true) -> void:
	if fill:
		for yy in range(y, y + h):
			for xx in range(x, x + w):
				dot(xx, yy, v)
	else:
		for xx in range(x, x + w):
			dot(xx, y, v)
			dot(xx, y + h - 1, v)
		for yy in range(y, y + h):
			dot(x, yy, v)
			dot(x + w - 1, yy, v)


func circle(cx: int, cy: int, r: int, v := 255, fill := false) -> void:
	for dy in range(-r, r + 1):
		for dx in range(-r, r + 1):
			var d2 := dx * dx + dy * dy
			if fill:
				if d2 <= r * r:
					dot(cx + dx, cy + dy, v)
			else:
				if d2 <= r * r and d2 >= (r - 1) * (r - 1):
					dot(cx + dx, cy + dy, v)


func sprite(x: int, y: int, pattern: Array, v := 255) -> void:
	for ry in pattern.size():
		var row: String = str(pattern[ry])
		for rx in row.length():
			var ch := row[rx]
			if ch != " " and ch != "0" and ch != ".":
				dot(x + rx, y + ry, v)


func text_width(t: String, s := 1) -> int:
	return maxi(0, t.length() * 6 * s - s)


## align: -1 left at x, 0 centred on x, 1 right-aligned ending at x
func text(t: String, x: int, y: int, s := 1, align := -1, v := 255) -> void:
	var w := text_width(t, s)
	var x0 := x if align < 0 else (x - w / 2 if align == 0 else x - w)
	for ci in t.length():
		var ch := t[ci]
		if ch != "x":
			ch = ch.to_upper()
		if not _rows_cache.has(ch):
			ch = "?"
		var rr: PackedStringArray = _rows_cache[ch]
		for ry in 7:
			var row: String = rr[ry]
			for rx in 5:
				if row[rx] == "1":
					for sy in s:
						for sx in s:
							dot(x0 + (ci * 6 + rx) * s + sx, y + ry * s + sy, v)


func present() -> void:
	_img.set_data(cols, rows, false, Image.FORMAT_L8, buf)
	_tex.update(_img)
	queue_redraw()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.02, 0.01, 0.0))
	draw_texture_rect(_tex, Rect2(Vector2.ZERO, size), false)
