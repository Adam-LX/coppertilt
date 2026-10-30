#!/usr/bin/env python3
"""Midnight Funfair - single source of truth for table geometry + painted pixel art.

Run (NixOS):
  nix-shell -p "python3.withPackages(p: [p.numpy p.pillow])" --run "python3 tools/build_table.py"

Geometry is authored FIRST (in native 320x608 table pixels, the Amiga resolution) and
exported to geometry.json for the GDScript solver; the art is then painted AROUND the same
numbers, so what you see is what the ball hits. Everything is original and procedural.
Final images are reduced to a shared 64-colour EHB-like palette (32 colours + 32 half-bright)
with 4x4 ordered (Bayer) dithering.
"""
import json, math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "tables", "midnight_funfair")
ART = os.path.join(ROOT, "assets", "art")
W, H = 320, 608
BALL_R = 7.5
rng = random.Random(1987)
nrng = np.random.default_rng(1987)

FONT_CANDIDATES = [
    "/nix/store/2y3pp9j22paigsnwr7x6857b5n8s5chi-nerd-fonts-noto-3.5.0/share/fonts/truetype/NerdFonts/Noto/NotoSansNerdFont-ExtraCondensedBlack.ttf",
    "/etc/profiles/per-user/adam/share/fonts/truetype/NerdFonts/JetBrainsMono/JetBrainsMonoNerdFont-ExtraBold.ttf",
]
WIDE_FONT = "/etc/profiles/per-user/adam/share/fonts/truetype/NerdFonts/JetBrainsMono/JetBrainsMonoNerdFont-ExtraBold.ttf"


def font(size, wide=False):
    for p in ([WIDE_FONT] if wide else []) + FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# =============================================================== GEOMETRY ==

SEGS = []      # [x1,y1,x2,y2,mat,onewayNx,onewayNy]
CIRCLES = []   # [x,y,r,mat,id]
RAILS = []     # polylines to paint as chrome rails (visual for walls)


def seg(a, b, mat="wall", oneway=None):
    SEGS.append([round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2), mat,
                 0 if oneway is None else oneway[0], 0 if oneway is None else oneway[1]])


def poly(pts, mat="wall", rail=True, closed=False):
    pts = list(pts)
    if closed:
        pts = pts + [pts[0]]
    for a, b in zip(pts, pts[1:]):
        seg(a, b, mat)
    if rail:
        RAILS.append(pts)


def mirror(p):
    return (300.0 - p[0], p[1])


ARCH_C, ARCH_R = (161.0, 165.0), 151.0
arch = [(ARCH_C[0] + ARCH_R * math.cos(math.radians(a)), ARCH_C[1] + ARCH_R * math.sin(math.radians(a)))
        for a in range(180, 361, 6)]
outer = [(10.0, 604.0), (10.0, 165.0)] + arch[1:-1] + [(312.0, 165.0), (312.0, 604.0)]
poly(outer)
# plunger lane
LANE_TOP = 182.0
poly([(290.0, 604.0), (290.0, LANE_TOP)])
CIRCLES.append([290.0, LANE_TOP, 2.5, "wall", "lanepost"])
gate_a, gate_b = (290.0, LANE_TOP - 2), (311.0, LANE_TOP - 26)
gdx, gdy = gate_b[0] - gate_a[0], gate_b[1] - gate_a[1]
gl = math.hypot(gdx, gdy)
seg(gate_a, gate_b, "gate", oneway=(round(gdy / gl, 4), round(-gdx / gl, 4)))  # blocks balls coming down
seg((290.0, 592.0), (312.0, 592.0), "plunger")

# flippers
PIV_L, PIV_R = (96.0, 548.0), (204.0, 548.0)
FL_LEN, FL_R0, FL_R1 = 44.0, 7.0, 3.5
FLIPPERS = [
    {"side": "L", "pivot": PIV_L, "len": FL_LEN, "r0": FL_R0, "r1": FL_R1, "rest": 30.0, "up": -18.0},
    {"side": "R", "pivot": PIV_R, "len": FL_LEN, "r0": FL_R0, "r1": FL_R1, "rest": 150.0, "up": 198.0},
]

# inlane / outlane separators + guides tangent to the pivot circle
SEP_X, SEP_Y0, SEP_Y1 = 28.0, 432.0, 488.0


def guide_to_pivot(s, piv, r):
    dx, dy = piv[0] - s[0], piv[1] - s[1]
    L = math.hypot(dx, dy)
    d = (dx / L, dy / L)
    n = (d[1], -d[0]) if d[0] > 0 else (-d[1], d[0])   # upward normal
    return (piv[0] + n[0] * r, piv[1] + n[1] * r)


for sgn in (1, -1):
    tf = (lambda p: p) if sgn == 1 else mirror
    top, bot = tf((SEP_X, SEP_Y0)), tf((SEP_X, SEP_Y1))
    piv = PIV_L if sgn == 1 else PIV_R
    tan = guide_to_pivot(bot, piv, FL_R0 + 0.5)
    poly([top, bot, tan])
    CIRCLES.append([top[0], top[1], 3.0, "rubber", "post"])
    # slingshot
    A, B, C = tf((48.0, 424.0)), tf((48.0, 480.0)), tf((86.0, 506.0))
    seg(A, B, "rubber")
    seg(B, C, "rubber")
    seg(C, A, "sling%d" % (0 if sgn == 1 else 1))
    for p in (A, B, C):
        CIRCLES.append([p[0], p[1], 3.0, "rubber", "slingpost"])

# top lanes F-U-N
LANE_POSTS = [114.0, 146.0, 178.0, 210.0]
for x in LANE_POSTS:
    poly([(x, 58.0), (x, 84.0)])
    CIRCLES.append([x, 58.0, 2.5, "wall", "lanetop"])
LANES = [{"pos": [(a + b) / 2, 70.0], "r": 7.0, "letter": l}
         for a, b, l in zip(LANE_POSTS, LANE_POSTS[1:], "FUN")]

# pop bumpers
BUMPERS = [(116.0, 170.0), (184.0, 170.0), (150.0, 214.0)]
BUMPER_R = 13.0
for i, (x, y) in enumerate(BUMPERS):
    CIRCLES.append([x, y, BUMPER_R, "bumper", "bumper%d" % i])

# R-I-D-E standups on the left wall
TARGETS = []
for i, (l, y) in enumerate(zip("RIDE", (340.0, 360.0, 380.0, 400.0))):
    seg((14.0, y - 8.0), (14.0, y + 8.0), "target%d" % i)
    TARGETS.append({"letter": l, "seg": [14.0, y - 8.0, 14.0, y + 8.0], "light": [24.0, y]})

# rollercoaster ramp: mouth flaps on layer 0, 1D path above
FLAP_L = [(10.0, 279.0), (30.0, 292.0)]   # slopes down into the mouth: no pocket against the wall
FLAP_R = [(74.0, 312.0), (66.0, 284.0)]
poly(FLAP_L)
poly(FLAP_R)
CIRCLES.append([74.0, 312.0, 3.0, "wall", "flappost"])
MOUTH = [30.0, 292.0, 66.0, 284.0]
mdx, mdy = MOUTH[2] - MOUTH[0], MOUTH[3] - MOUTH[1]
ml = math.hypot(mdx, mdy)
MOUTH_IN = (mdy / ml, -mdx / ml)      # normal pointing into the ramp (up/left)
seg((MOUTH[0], MOUTH[1]), (MOUTH[2], MOUTH[3]), "ramp", oneway=MOUTH_IN)
RAMP_CTRL = [(48.0, 288.0), (42.0, 250.0), (36.0, 200.0), (38.0, 160.0), (50.0, 132.0), (72.0, 114.0),
             (104.0, 106.0), (150.0, 104.0), (200.0, 106.0), (236.0, 114.0), (260.0, 134.0),
             (271.0, 166.0), (274.0, 220.0), (272.0, 290.0), (268.0, 350.0), (264.0, 392.0), (262.0, 414.0)]


def catmull(pts, step=2.0):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        n = max(2, int(math.dist(p1, p2) / step))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    out.append(pts[-1])
    return out


RAMP_PATH = catmull(RAMP_CTRL)
ramp_s = [0.0]
for a, b in zip(RAMP_PATH, RAMP_PATH[1:]):
    ramp_s.append(ramp_s[-1] + math.dist(a, b))
APEX_S = ramp_s[[i for i, p in enumerate(RAMP_PATH) if p[0] >= 72][0]]
DOWN_S = ramp_s[[i for i, p in enumerate(RAMP_PATH) if p[0] >= 236][0]]

SCOOP = {"pos": [232.0, 262.0], "r": 8.0, "kick": [-0.56, 0.83], "speed": 330.0}
# little backstop behind the scoop
poly([(222.0, 252.0), (228.0, 247.0), (238.0, 247.0), (244.0, 253.0)])
KICKBACK = {"rect": [10.0, 540.0, 18.0, 44.0], "launch": [19.0, 552.0], "vy": -650.0}
PLUNGER = {"rest": [301.0, 592.0 - BALL_R], "lane": [290.0, 300.0, 22.0, 300.0]}

LIGHTS = {}


def light(name, x, y, kind="round", color="yellow", dirdeg=0.0, size=4.0):
    LIGHTS[name] = {"pos": [x, y], "kind": kind, "color": color, "dir": dirdeg, "size": size}


for ln in LANES:
    light("lane_" + ln["letter"], ln["pos"][0], ln["pos"][1] + 22, "round", "yellow", size=3.5)
for t in TARGETS:
    light("ride_" + t["letter"], t["light"][0], t["light"][1], "round", "red", size=3.0)
for i, x in enumerate((106.0, 132.0, 168.0, 194.0)):
    light("bonus%d" % (i + 2), x, 418.0, "round", "orange", size=4.5)
light("ramp_arrow", 82.0, 330.0, "arrow", "cyan", -118.0, 7.0)
light("ramp1", 98.0, 300.0, "round", "cyan", size=3.0)
light("ramp2", 108.0, 288.0, "round", "cyan", size=3.0)
light("ramp3", 118.0, 276.0, "round", "cyan", size=3.0)
light("lock", 216.0, 290.0, "arrow", "magenta", -62.0, 7.0)
light("jackpot", 150.0, 300.0, "star", "white", size=9.0)
light("kickback", 19.0, 512.0, "arrow", "green", -90.0, 5.0)
light("shoot_again", 150.0, 520.0, "round", "red", size=5.0)
light("extra_l", 38.0, 452.0, "round", "green", size=3.0)
light("extra_r", 262.0, 452.0, "round", "green", size=3.0)
LIGHT_COLORS = {"yellow": [255, 230, 60], "red": [255, 60, 50], "orange": [255, 150, 30], "cyan": [80, 230, 255],
                "magenta": [255, 80, 220], "white": [255, 255, 235], "green": [90, 255, 110]}


def export_geometry():
    g = {"size": [W, H], "ball_r": BALL_R, "segments": SEGS, "circles": CIRCLES,
         "flippers": [{**f, "pivot": list(f["pivot"])} for f in FLIPPERS],
         "lanes": LANES, "targets": TARGETS, "bumpers": [list(b) + [BUMPER_R] for b in BUMPERS],
         "ramp": {"mouth": MOUTH, "in": list(MOUTH_IN), "path": [[round(x, 2), round(y, 2)] for x, y in RAMP_PATH],
                  "s": [round(s, 2) for s in ramp_s], "apex_s": round(APEX_S, 2), "down_s": round(DOWN_S, 2)},
         "scoop": SCOOP, "kickback": KICKBACK, "plunger": PLUNGER, "lights": LIGHTS,
         "light_colors": LIGHT_COLORS, "drain_y": 614.0}
    with open(os.path.join(OUT, "geometry.json"), "w") as f:
        json.dump(g, f, indent=1)

# =============================================================== PAINTING ==
LIGHT3 = np.array([-0.45, -0.68, 0.58])
LIGHT3 = LIGHT3 / np.linalg.norm(LIGHT3)
HALF = LIGHT3 + np.array([0, 0, 1.0])
HALF = HALF / np.linalg.norm(HALF)
OUTLINE = np.array([14, 8, 24], float)


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rgb = np.zeros((h, w, 3), float)
        self.a = np.zeros((h, w), float)
        yy, xx = np.mgrid[0:h, 0:w]
        self.xx, self.yy = xx + 0.5, yy + 0.5

    def put(self, mask, col, alpha=1.0):
        m = np.clip(mask, 0, 1) * alpha
        if m.ndim == 2:
            m3 = m[..., None]
        col = np.asarray(col, float)
        self.rgb = self.rgb * (1 - m3) + col * m3
        self.a = np.maximum(self.a, m)

    def put_rgb(self, mask, rgb):
        m3 = np.clip(mask, 0, 1)[..., None]
        self.rgb = self.rgb * (1 - m3) + rgb * m3
        self.a = np.maximum(self.a, np.clip(mask, 0, 1))

    def mul(self, mask, f):
        m = np.clip(mask, 0, 1)[..., None]
        self.rgb = self.rgb * (1 - m * (1 - f))

    def layer_pil(self, draw_fn):
        """Draw with PIL on a transparent layer and composite (aliased = pixel art)."""
        im = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(im), im)
        arr = np.asarray(im).astype(float)
        m = arr[..., 3] / 255.0
        self.put_rgb(m, arr[..., :3])
        return m


def smooth_noise(w, h, cell, seed):
    r = np.random.default_rng(seed)
    small = r.random((h // cell + 3, w // cell + 3))
    im = Image.fromarray((small * 255).astype(np.uint8)).resize(((w // cell + 3) * cell, (h // cell + 3) * cell), Image.BICUBIC)
    return np.asarray(im).astype(float)[:h, :w] / 255.0


def seg_dist(xx, yy, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy or 1e-9
    t = np.clip(((xx - ax) * dx + (yy - ay) * dy) / L2, 0, 1)
    cx, cy = ax + t * dx, ay + t * dy
    ox, oy = xx - cx, yy - cy
    d = np.hypot(ox, oy)
    return d, ox, oy, t


def shade(nx, ny, nz, base, spec_p=18, spec_k=1.0, amb=0.22, env=True):
    diff = np.clip(nx * LIGHT3[0] + ny * LIGHT3[1] + nz * LIGHT3[2], 0, 1)
    spec = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1) ** spec_p
    base = np.asarray(base, float)
    col = base * (amb + (1 - amb) * diff)[..., None] + (255 * spec * spec_k)[..., None]
    if env:   # chrome "horizon" band: reflected dark ground + purple sky
        band = np.clip(1 - np.abs(ny - 0.25) * 5, 0, 1)
        col = col - (band * 70)[..., None] + np.array([10, -6, 26]) * (ny < -0.2)[..., None]
    return np.clip(col, 0, 255)


def tube(cv, pts, hw, base, spec_p=16, spec_k=1.0, outline=1.2, env=True, amb=0.22):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    pad = hw + outline + 2
    x0, x1 = max(0, int(min(xs) - pad)), min(cv.w, int(max(xs) + pad) + 1)
    y0, y1 = max(0, int(min(ys) - pad)), min(cv.h, int(max(ys) + pad) + 1)
    xx, yy = cv.xx[y0:y1, x0:x1], cv.yy[y0:y1, x0:x1]
    best = np.full(xx.shape, 1e9)
    bx = np.zeros(xx.shape)
    by = np.zeros(xx.shape)
    for a, b in zip(pts, pts[1:]) if len(pts) > 1 else [(pts[0], pts[0])]:
        d, ox, oy, _ = seg_dist(xx, yy, a, b)
        m = d < best
        best = np.where(m, d, best)
        bx = np.where(m, ox, bx)
        by = np.where(m, oy, by)
    _tube_paint(cv, (y0, y1, x0, x1), best, bx, by, hw, base, spec_p, spec_k, outline, env, amb)


def _tube_paint(cv, box, d, ox, oy, hw, base, spec_p, spec_k, outline, env, amb):
    y0, y1, x0, x1 = box
    h = np.clip(d / hw, 0, 1)
    nn = np.maximum(d, 1e-6)
    nx, ny = ox / nn * h, oy / nn * h
    nz = np.sqrt(np.clip(1 - h * h, 0, 1))
    col = shade(nx, ny, nz, base, spec_p, spec_k, amb, env)
    body = (d <= hw).astype(float)
    ring = ((d > hw) & (d <= hw + outline)).astype(float)
    sub_rgb = cv.rgb[y0:y1, x0:x1]
    sub_a = cv.a[y0:y1, x0:x1]
    sub_rgb[:] = sub_rgb * (1 - ring[..., None]) + OUTLINE * ring[..., None]
    sub_rgb[:] = sub_rgb * (1 - body[..., None]) + col * body[..., None]
    sub_a[:] = np.maximum(sub_a, np.maximum(body, ring))


def dome(cv, cx, cy, r, base, spec_p=14, spec_k=1.0, outline=1.2, env=False, amb=0.25, flat=0.0):
    x0, x1 = max(0, int(cx - r - 3)), min(cv.w, int(cx + r + 4))
    y0, y1 = max(0, int(cy - r - 3)), min(cv.h, int(cy + r + 4))
    ox, oy = cv.xx[y0:y1, x0:x1] - cx, cv.yy[y0:y1, x0:x1] - cy
    d = np.hypot(ox, oy)
    if flat:
        d2 = np.maximum(d - flat * r, 0) / (1 - flat)
        _tube_paint(cv, (y0, y1, x0, x1), np.where(d <= r, d2, d), ox, oy, r, base, spec_p, spec_k, outline, env, amb)
    else:
        _tube_paint(cv, (y0, y1, x0, x1), d, ox, oy, r, base, spec_p, spec_k, outline, env, amb)


def poly_mask(w, h, pts, scale=1):
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).polygon([(x, y) for x, y in pts], fill=255)
    return np.asarray(im).astype(float) / 255.0


def box_blur(m, r):
    if r <= 0:
        return m
    im = Image.fromarray(np.clip(m * 255, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.BoxBlur(r))).astype(float) / 255.0


def dilate(m, r=1):
    im = Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.MaxFilter(2 * r + 1))).astype(float) / 255.0


def emboss(cv, mask, rgb, depth=2.5, outline=True, shadow=None):
    """Bevelled plastic / lettering: lights the blurred mask gradient."""
    if outline:
        o = dilate(mask, 1) * (1 - mask)
        cv.put(o, OUTLINE)
    b = box_blur(mask, 2)
    gy, gx = np.gradient(b)
    k = depth * 3
    nx, ny = -gx * k, -gy * k
    nz = np.ones_like(nx)
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    lit = (nx * LIGHT3[0] + ny * LIGHT3[1] + nz * LIGHT3[2]) / L
    spec = np.clip((nx * HALF[0] + ny * HALF[1] + nz * HALF[2]) / L, 0, 1) ** 30
    col = rgb * (0.35 + 0.85 * lit)[..., None] + (spec * 200)[..., None]
    cv.put_rgb(mask, np.clip(col, 0, 255))


def gradient_rgb(h, w, stops):
    """vertical gradient across rows 0..h-1 through list of (t, rgb)."""
    t = np.linspace(0, 1, h)
    out = np.zeros((h, 3))
    for c in range(3):
        out[:, c] = np.interp(t, [s[0] for s in stops], [s[1][c] for s in stops])
    return np.repeat(out[:, None, :], w, axis=1)


def text_mask(w, h, text, size, xy, wide=False, anchor="mm", stroke=0, spacing=0):
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    f = font(size, wide)
    if spacing:
        # manual letter spacing
        widths = [d.textlength(ch, font=f) for ch in text]
        total = sum(widths) + spacing * (len(text) - 1)
        x = xy[0] - total / 2
        for ch, cw in zip(text, widths):
            d.text((x + cw / 2, xy[1]), ch, fill=255, font=f, anchor="mm", stroke_width=stroke, stroke_fill=255)
            x += cw + spacing
    else:
        d.text(xy, text, fill=255, font=f, anchor=anchor, stroke_width=stroke, stroke_fill=255)
    return (np.asarray(im) > 127).astype(float)


def gold_letters(cv, text, size, xy, top=(255, 246, 150), mid=(255, 170, 30), bot=(190, 50, 20), wide=False,
                 spacing=0, shadow=(3, 3), stroke=0):
    m = text_mask(cv.w, cv.h, text, size, xy, wide=wide, spacing=spacing, stroke=stroke)
    ys = np.where(m.any(axis=1))[0]
    if len(ys) == 0:
        return m
    y0, y1 = ys[0], ys[-1] + 1
    grad = np.zeros((cv.h, cv.w, 3))
    grad[y0:y1] = gradient_rgb(y1 - y0, cv.w, [(0, top), (0.45, mid), (1, bot)])
    if shadow:
        sh = np.roll(np.roll(dilate(m, 1), shadow[1], 0), shadow[0], 1)
        cv.mul(sh, 0.3)
    emboss(cv, m, grad, depth=2.0)
    # 1px white-hot top edge highlight
    top_edge = m * (1 - np.roll(m, 1, 0))
    cv.put(top_edge, (255, 255, 230), 0.8)
    return m

# ------------------------------------------------------------ scenery ----


def paint_sky(cv, stops, seed=1, cloud=True, stars=260):
    cv.rgb[:] = gradient_rgb(cv.h, cv.w, stops)
    cv.a[:] = 1
    n1 = smooth_noise(cv.w, cv.h, 24, seed)
    n2 = smooth_noise(cv.w, cv.h, 7, seed + 1)
    paint = (n1 - 0.5) * 34 + (n2 - 0.5) * 14
    cv.rgb += np.stack([paint * 0.9, paint * 0.5, paint * 1.1], -1)
    if cloud:  # streaky painted clouds lit by the funfair glow (pink/orange from below)
        c = np.clip((smooth_noise(cv.w, cv.h, 40, seed + 7) - 0.58) * 4, 0, 1)
        c = c * np.clip(smooth_noise(cv.w, cv.h, 5, seed + 9) * 1.6, 0, 1)
        cv.put(c, (120, 50, 120), 0.45)
    r = random.Random(seed)
    for _ in range(stars):
        x, y = r.randrange(cv.w), r.randrange(int(cv.h * 0.8))
        b = r.random()
        col = (255, 255, 255) if b > 0.85 else ((255, 230, 160) if b > 0.5 else (170, 160, 230))
        cv.rgb[y, x] = col
        if b > 0.96 and 1 < x < cv.w - 2 and 1 < y < cv.h - 2:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.rgb[y + dy, x + dx] = (200, 190, 255)
    np.clip(cv.rgb, 0, 255, out=cv.rgb)


def ferris_wheel(cv, cx, cy, r, phase=0.0, legs_to=None, spokes=16, cars=8, bulbs=32, lw=2):
    def f(d, im):
        # support A-frame
        ly = legs_to if legs_to else cy + r * 1.35
        for sx in (-1, 1):
            for off, col in ((0, (40, 30, 70)), (1, (110, 100, 160))):
                d.line([(cx + off, cy), (cx + sx * r * 0.62 + off, ly)], fill=col, width=3 if off == 0 else 1)
            d.line([(cx + sx * r * 0.18, cy + (ly - cy) * 0.3), (cx + sx * r * 0.45, cy + (ly - cy) * 0.75)],
                   fill=(70, 60, 110), width=1)
        d.line([(cx - r * 0.45, cy + (ly - cy) * 0.75), (cx + r * 0.45, cy + (ly - cy) * 0.75)], fill=(70, 60, 110), width=1)
        for i in range(spokes):
            a = phase + i * 2 * math.pi / spokes
            d.line([(cx, cy), (cx + math.cos(a) * r, cy + math.sin(a) * r)], fill=(150, 120, 210), width=1)
        # rims
        for rr, col, wdt in ((r, (255, 120, 200), lw), (r - 5, (200, 70, 170), 1), (r * 0.45, (170, 110, 230), 1)):
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=col, width=wdt)
        # zig-zag truss between rims
        for i in range(spokes * 2):
            a0 = phase + i * math.pi / spokes
            a1 = phase + (i + 1) * math.pi / spokes
            r0, r1 = (r, r - 5) if i % 2 == 0 else (r - 5, r)
            d.line([(cx + math.cos(a0) * r0, cy + math.sin(a0) * r0), (cx + math.cos(a1) * r1, cy + math.sin(a1) * r1)],
                   fill=(230, 90, 180), width=1)
        for i in range(bulbs):
            a = phase + i * 2 * math.pi / bulbs
            x, y = cx + math.cos(a) * (r + 1), cy + math.sin(a) * (r + 1)
            c = (255, 250, 200) if i % 2 == 0 else (255, 210, 60)
            d.rectangle([x - 1, y - 1, x, y], fill=c)
        palette = [(255, 60, 60), (60, 200, 255), (255, 210, 40), (120, 255, 120), (255, 120, 40), (200, 90, 255)]
        for i in range(cars):
            a = phase + i * 2 * math.pi / cars
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            c = palette[i % len(palette)]
            cw = max(2, int(r / 22))
            d.line([(x, y), (x, y + cw)], fill=(60, 50, 90))
            d.line([(x, y), (x, y + cw * 1.5)], fill=(200, 180, 230))
            d.pieslice([x - cw * 1.6, y + cw * 0.6, x + cw * 1.6, y + cw * 3.6], 0, 180, fill=c, outline=(20, 10, 30))
            d.chord([x - cw * 1.4, y + cw * 0.2, x + cw * 1.4, y + cw * 1.6], 180, 360, fill=tuple(min(255, v + 40) for v in c), outline=(20, 10, 30))
            d.point([(x - cw, y + cw * 2.2)], fill=(255, 255, 220))
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 200, 70), outline=(30, 10, 30))
        d.point([(cx - 2, cy - 2)], fill=(255, 255, 255))
    cv.layer_pil(f)


def carousel(cv, cx, top, w, seed=0):
    rim_y = top + w * 0.24
    half = w / 2

    def f(d, im):
        # interior
        d.rectangle([cx - half + 4, rim_y + 6, cx + half - 4, rim_y + w * 0.34], fill=(48, 12, 52))
        # poles + horses
        r = random.Random(seed)
        n = 7
        for i in range(n):
            x = cx - half + 10 + i * (w - 20) / (n - 1)
            d.line([(x, rim_y + 6), (x, rim_y + w * 0.34)], fill=(255, 200, 60))
            d.point([(x, rim_y + 8)], fill=(255, 255, 200))
            hy = rim_y + w * 0.13 + (i % 3) * 3
            hc = [(250, 245, 235), (255, 170, 190), (170, 220, 255)][i % 3]
            facing = 1 if i % 2 == 0 else -1
            body = [x - 5, hy, x + 5, hy + 4]
            d.rounded_rectangle(body, radius=2, fill=hc, outline=(30, 10, 30))
            hx = x + facing * 5
            d.polygon([(hx, hy - 4), (hx + facing * 3, hy - 3), (hx + facing * 3, hy + 1), (hx, hy + 2)], fill=hc, outline=(30, 10, 30))
            d.line([(x - 4, hy + 4), (x - 5, hy + 8)], fill=(30, 10, 30))
            d.line([(x + 4, hy + 4), (x + 5, hy + 8)], fill=(30, 10, 30))
            d.point([(x - 2, hy + 1)], fill=(255, 60, 80))
        # platform
        py = rim_y + w * 0.34
        d.ellipse([cx - half - 2, py - 5, cx + half + 2, py + 7], fill=(150, 40, 60), outline=(20, 8, 24))
        d.ellipse([cx - half, py - 5, cx + half, py + 3], fill=(230, 160, 60), outline=(20, 8, 24))
        for i in range(14):
            a = math.pi * i / 13
            x = cx - math.cos(a) * (half - 1)
            y = py + 2 + math.sin(a) * 3
            d.point([(x, y)], fill=(255, 255, 200) if i % 2 else (255, 80, 80))
        # canopy cone: alternating wedges
        apex = (cx, top)
        k = 12
        for i in range(k):
            x0 = cx - half + i * w / k
            x1 = x0 + w / k
            col = (220, 30, 60) if i % 2 == 0 else (250, 230, 180)
            d.polygon([apex, (x0, rim_y), (x1, rim_y)], fill=col)
        d.line([apex, (cx - half, rim_y)], fill=(20, 8, 24))
        d.line([apex, (cx + half, rim_y)], fill=(20, 8, 24))
        # scalloped valance
        for i in range(k):
            x0 = cx - half + i * w / k
            col = (250, 230, 180) if i % 2 == 0 else (220, 30, 60)
            d.chord([x0, rim_y - 3, x0 + w / k, rim_y + 7], 0, 180, fill=col, outline=(20, 8, 24))
        d.rectangle([cx - half - 2, rim_y - 2, cx + half + 2, rim_y + 1], fill=(255, 196, 50), outline=(20, 8, 24))
        for i in range(16):
            x = cx - half + 1 + i * (w - 2) / 15
            d.point([(x, rim_y - 1)], fill=(255, 255, 230) if i % 2 == 0 else (255, 90, 60))
        # finial + flag
        d.line([(cx, top - 9), (cx, top)], fill=(255, 210, 80))
        d.polygon([(cx + 1, top - 9), (cx + 8, top - 7), (cx + 1, top - 5)], fill=(60, 220, 255), outline=(20, 8, 24))
        d.ellipse([cx - 2, top - 2, cx + 2, top + 2], fill=(255, 210, 80), outline=(20, 8, 24))
    cv.layer_pil(f)
    # shade canopy cone left->right (painted roundness)
    xx = cv.xx
    cone = poly_mask(cv.w, cv.h, [(cx, top), (cx - half, rim_y), (cx + half, rim_y)])
    sh = np.clip((xx - cx) / half, -1, 1)
    cv.rgb = cv.rgb * (1 - cone[..., None] * (0.35 * np.clip(sh, 0, 1))[..., None]) + \
        (cone * np.clip(-sh, 0, 1) * 30)[..., None]


def tent(cv, cx, base_y, w, h, c1=(40, 120, 220), c2=(240, 236, 220)):
    def f(d, im):
        half = w / 2
        top = base_y - h
        shoulder = base_y - h * 0.45
        k = 6
        for i in range(k):
            x0 = cx - half + i * w / k
            x1 = x0 + w / k
            col = c1 if i % 2 == 0 else c2
            d.polygon([(cx, top), (cx - half * 0.55 + (x0 - cx + half) * 0.55, shoulder),
                       (cx - half * 0.55 + (x1 - cx + half) * 0.55, shoulder)], fill=col)
            d.rectangle([x0, shoulder, x1, base_y], fill=tuple(int(c * 0.8) for c in col))
        d.line([(cx, top), (cx - half * 0.55, shoulder)], fill=(20, 8, 24))
        d.line([(cx, top), (cx + half * 0.55, shoulder)], fill=(20, 8, 24))
        d.rectangle([cx - half, shoulder, cx + half, base_y], outline=(20, 8, 24))
        d.polygon([(cx - 4, base_y), (cx, shoulder + 3), (cx + 4, base_y)], fill=(25, 8, 30))
        d.line([(cx, top - 6), (cx, top)], fill=(255, 220, 90))
        d.polygon([(cx, top - 6), (cx + 5, top - 5), (cx, top - 3)], fill=(255, 70, 70))
    cv.layer_pil(f)


def bunting(cv, x0, x1, y, sag, step=9, size=5, colors=None):
    colors = colors or [(255, 60, 60), (255, 220, 60), (60, 200, 255), (120, 255, 120), (255, 120, 230)]

    def f(d, im):
        pts = []
        n = int((x1 - x0) / 2)
        for i in range(n + 1):
            t = i / n
            pts.append((x0 + (x1 - x0) * t, y + sag * 4 * t * (1 - t)))
        d.line(pts, fill=(200, 190, 230))
        k = 0
        x = x0 + 3
        while x < x1 - 3:
            t = (x - x0) / (x1 - x0)
            yy = y + sag * 4 * t * (1 - t)
            col = colors[k % len(colors)]
            d.polygon([(x - size / 2, yy), (x + size / 2, yy), (x, yy + size + 1)], fill=col, outline=(20, 8, 24))
            k += 1
            x += step
    cv.layer_pil(f)


def coaster_lattice(cv, pts, depth=60, seed=3):
    """Wooden coaster support lattice hanging under a path (background silhouette)."""
    def f(d, im):
        for i in range(0, len(pts) - 1, 4):
            x, y = pts[i]
            d.line([(x, y), (x, y + depth)], fill=(70, 40, 80), width=1)
            if i + 4 < len(pts):
                x2, y2 = pts[i + 4]
                d.line([(x, y + depth * 0.5), (x2, y2)], fill=(55, 30, 70))
                d.line([(x, y), (x2, y2 + depth * 0.5)], fill=(55, 30, 70))
    cv.layer_pil(f)


def moon(cv, cx, cy, r):
    ox, oy = cv.xx - cx, cv.yy - cy
    disc = (np.hypot(ox, oy) <= r).astype(float)
    bite = (np.hypot(ox - r * 0.45, oy + r * 0.2) <= r * 0.85).astype(float)
    m = disc * (1 - bite)
    glow = np.clip(1 - np.hypot(ox, oy) / (r * 2.6), 0, 1) ** 2
    cv.put(glow, (255, 220, 170), 0.35)
    shade_v = np.clip(0.75 + 0.25 * (-ox / r), 0, 1)
    cv.put_rgb(m, np.stack([255 * shade_v, 236 * shade_v, 170 * shade_v], -1))

# ----------------------------------------------------------- playfield ----


def insert(cv, x, y, kind, color, size, dirdeg=0.0, lit=False):
    """Unlit insert: tinted dark lens + chrome bezel. Godot draws the lit state on top."""
    c = np.array(LIGHT_COLORS[color], float)
    lens = c * (1.0 if lit else 0.34) + (0 if lit else 10)
    if kind == "round":
        dome(cv, x, y, size + 1.2, (190, 190, 210), spec_p=10, outline=1.0, env=True)
        dome(cv, x, y, size, lens, spec_p=8, spec_k=0.7, outline=0.0, amb=0.45)
    elif kind == "arrow":
        a = math.radians(dirdeg)
        fx, fy = math.cos(a), math.sin(a)
        px, py = -fy, fx
        s = size
        pts = [(x + fx * s * 1.3, y + fy * s * 1.3), (x + px * s * 0.9, y + py * s * 0.9),
               (x + px * s * 0.35, y + py * s * 0.35), (x + px * s * 0.35 - fx * s, y + py * s * 0.35 - fy * s),
               (x - px * s * 0.35 - fx * s, y - py * s * 0.35 - fy * s), (x - px * s * 0.35, y - py * s * 0.35),
               (x - px * s * 0.9, y - py * s * 0.9)]
        m = poly_mask(cv.w, cv.h, pts)
        emboss(cv, m, np.broadcast_to(lens, (cv.h, cv.w, 3)), depth=1.5)
    elif kind == "star":
        pts = []
        for i in range(10):
            rr = size if i % 2 == 0 else size * 0.45
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        m = poly_mask(cv.w, cv.h, pts)
        emboss(cv, m, np.broadcast_to(lens, (cv.h, cv.w, 3)), depth=1.5)


import re as _re
_GLYPHS = dict(_re.findall(r'"(.)": "([01 ]{41})"', open(os.path.join(ROOT, "scripts", "ui", "dot_matrix.gd")).read()))


def pixel_text_mask(w, h, text, x, y, scale=1):
    m = np.zeros((h, w))
    tw = len(text) * 6 * scale - scale
    x0 = int(round(x - tw / 2))
    y0 = int(round(y - 3.5 * scale))
    for i, ch in enumerate(text.upper()):
        g = _GLYPHS.get(ch)
        if g is None:
            continue
        for ry, row in enumerate(g.split(" ")):
            for rx, b in enumerate(row):
                if b == "1":
                    px, py = x0 + (i * 6 + rx) * scale, y0 + ry * scale
                    m[max(0, py):max(0, py + scale), max(0, px):max(0, px + scale)] = 1
    return m


def label(cv, text, x, y, size=8, col=(255, 240, 200), shadow=True, wide=True, spacing=0):
    m = pixel_text_mask(cv.w, cv.h, text, x, y, 2 if size >= 12 else 1)
    o = dilate(m, 1) * (1 - m)
    cv.put(o, OUTLINE)
    cv.put(m, col)


def paint_playfield():
    cv = Canvas(W, H)
    paint_sky(cv, [(0, (8, 4, 34)), (0.25, (30, 10, 70)), (0.55, (70, 16, 90)), (0.8, (60, 10, 60)), (1, (24, 6, 30))],
              seed=5, stars=320)
    moon(cv, 56, 52, 13)
    # distant skyline of the fair: tents + tower silhouettes behind, glow from below
    glow = np.clip(1 - np.abs(cv.yy - 300) / 140, 0, 1) ** 2
    cv.put(glow, (255, 90, 120), 0.18)
    # searchlight beams sweeping up from the fair
    for bx, ang, col in ((150, -100, (255, 200, 255)), (150, -70, (180, 230, 255)), (60, -80, (255, 220, 160)), (250, -105, (200, 255, 220))):
        a = math.radians(ang)
        dx, dy = math.cos(a), math.sin(a)
        px, py = cv.xx - bx, cv.yy - 380
        along = px * dx + py * dy
        across = np.abs(-px * dy + py * dx)
        beam = np.clip(1 - across / (4 + along * 0.12), 0, 1) * (along > 0) * np.clip(1 - along / 420, 0, 1)
        cv.put(beam, col, 0.16)
    # warm midway: painted boardwalk planks + light pools in the lower half (no grid: irregular planks)
    yy, xx = cv.yy, cv.xx
    floor = np.clip((yy - 330) / 60, 0, 1)
    ang = np.arctan2(yy - 392, xx - 150)
    dist = np.hypot(xx - 150, yy - 392)
    wob = (smooth_noise(W, H, 16, 78) - 0.5) * 0.35
    ray = (np.sin(ang * 18 + wob * 3) > 0).astype(float)
    tone = smooth_noise(W, H, 3, 77)
    c1 = np.stack([150 + tone * 40, 30 + tone * 20, 110 + tone * 30], -1)
    c2 = np.stack([90 + tone * 30, 20 + tone * 14, 96 + tone * 30], -1)
    sun = np.where(ray[..., None] > 0, c1, c2) * np.clip(1.15 - dist / 330, 0.45, 1)[..., None]
    cv.put_rgb(floor * 0.8, sun)
    # painted ring of bulbs around the carousel plaza
    for i in range(44):
        t = i / 44 * 2 * math.pi
        x, y = 150 + math.cos(t) * 118, 392 + math.sin(t) * 64
        if 12 < x < 288 and 336 < y < 590:
            dome(cv, x, y, 1.4, (255, 230, 120) if i % 2 else (255, 120, 160), spec_p=6, outline=0.6)
    for (lx, ly, rx_, ry_, col) in ((150, 405, 110, 42, (255, 150, 60)), (150, 470, 90, 30, (255, 80, 140)),
                                    (60, 540, 50, 30, (120, 80, 255)), (240, 540, 50, 30, (120, 80, 255)),
                                    (150, 560, 70, 30, (255, 120, 60))):
        pool = np.clip(1 - np.hypot((xx - lx) / rx_, (yy - ly) / ry_), 0, 1) ** 1.5
        cv.put(pool * floor, col, 0.45)
    coaster_lattice(cv, RAMP_PATH[: len(RAMP_PATH) // 3], depth=70)
    ferris_wheel(cv, 150, 186, 82, phase=0.12, legs_to=328, spokes=16, cars=10, bulbs=40)
    tent(cv, 252, 336, 52, 46, (40, 110, 220))
    bunting(cv, 12, 288, 236, 16)
    bunting(cv, 80, 222, 316, 10, step=8, size=4)
    carousel(cv, 150, 336, 108)

    # big title lettering between the slings
    gold_letters(cv, "MIDNIGHT", 22, (150, 446), spacing=1)
    gold_letters(cv, "FUNFAIR", 24, (150, 470), top=(200, 255, 255), mid=(60, 190, 255), bot=(40, 40, 170), spacing=1)

    # painted lane guide paths (arrows/stripes) and drop shadows of raised parts
    shadow = np.zeros((H, W))
    sh_cv = Canvas(W, H)

    def raised(d, im):
        for pts in RAILS:
            d.line(pts, fill=(255, 255, 255, 255), width=6)
        for c in CIRCLES:
            r = c[2] + (3 if c[3] == "bumper" else 1)
            d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(255, 255, 255, 255))
        for sgn in (1, -1):
            tf = (lambda p: p) if sgn == 1 else mirror
            d.polygon([tf((48, 424)), tf((48, 480)), tf((86, 506))], fill=(255, 255, 255, 255))
    sm = sh_cv.layer_pil(raised)
    shadow = np.maximum(shadow, np.roll(np.roll(sm, 4, 0), 3, 1))
    # ramp shadow (ramp floats above the playfield)
    rm = ramp_mask(width=13)
    shadow = np.maximum(shadow, np.roll(np.roll(rm, 6, 0), 5, 1) * 0.9)
    cv.mul(box_blur(shadow, 1), 0.45)

    # ramp support pillars
    for i in (30, 70, 150, 210):
        x, y = RAMP_PATH[i]
        tube(cv, [(x + 4, y + 4), (x + 4, y + 12)], 1.5, (120, 110, 150), outline=1.0)

    # lane/shot decals
    for ln in LANES:
        x, y = ln["pos"]
        tube(cv, [(x - 3, y), (x + 3, y)], 1.2, (210, 210, 225), outline=1.0)
        label(cv, ln["letter"], x, y + 12, 9, (255, 236, 120))
    label(cv, "COASTER", 66, 348, 7, (120, 240, 255))
    label(cv, "BIG WHEEL", 232, 238, 7, (255, 150, 240))
    label(cv, "RIDE", 40, 326, 7, (255, 120, 110))
    label(cv, "SHOOT AGAIN", 150, 533, 6, (255, 140, 130))
    label(cv, "JACKPOT", 150, 314, 7, (255, 255, 220))

    for name, L in LIGHTS.items():
        insert(cv, L["pos"][0], L["pos"][1], L["kind"], L["color"], L["size"], L["dir"])
    for i, x in enumerate((106, 132, 168, 194)):
        label(cv, "%dX" % (i + 2), x, 429, 6, (255, 220, 150))

    # scoop: dark hole with metal lip
    sx, sy = SCOOP["pos"]
    dome(cv, sx, sy, 9.5, (200, 200, 220), spec_p=8, env=True)
    ox, oy = cv.xx - sx, cv.yy - sy
    hole = (np.hypot(ox, oy) <= 7.0).astype(float)
    cv.put(hole, (6, 2, 10))
    cv.put(hole * (np.hypot(ox + 1.5, oy + 1.5) > 6.0), (40, 30, 60))

    # ramp mouth plate
    mp = poly_mask(W, H, [(26, 300), (30, 290), (66, 282), (70, 292)])
    emboss(cv, mp, np.broadcast_to(np.array([170, 170, 190.0]), (H, W, 3)), depth=1.5)

    # slingshot plastics (bevelled, with painted stars) + rubber band on the kicking face
    for sgn in (1, -1):
        tf = (lambda p: p) if sgn == 1 else mirror
        A, B, C = tf((48, 424)), tf((48, 480)), tf((86, 506))
        m = poly_mask(W, H, [A, B, C])
        base = gradient_rgb(H, W, [(0, (255, 60, 140)), (0.69, (255, 80, 150)), (0.74, (200, 30, 110)), (0.84, (120, 10, 80)), (1, (90, 10, 70))])
        emboss(cv, m, base, depth=3.0)
        cxs = (A[0] + B[0] + C[0]) / 3
        cys = (A[1] + B[1] + C[1]) / 3
        insert(cv, cxs, cys + 2, "star", "yellow", 6.0, lit=True)
        tube(cv, [C, A], 2.0, (40, 36, 48), spec_p=30, spec_k=0.8, env=False)
        tube(cv, [A, B, C], 1.6, (40, 36, 48), spec_p=30, spec_k=0.8, env=False)

    # target faces
    for i, t in enumerate(TARGETS):
        x1, y1, x2, y2 = t["seg"]
        m = np.zeros((H, W))
        m[int(y1) + 1:int(y2) - 1, 12:17] = 1
        col = np.array([[255, 70, 60], [255, 220, 60], [60, 220, 255], [120, 255, 120]][i], float)
        emboss(cv, m, np.broadcast_to(col, (H, W, 3)), depth=2.0)
        label(cv, t["letter"], 15, (y1 + y2) / 2, 7, (20, 10, 20), wide=True)

    # chrome rails (walls) - chunky with highlights + outline
    for pts in RAILS:
        tube(cv, pts, 2.6, (150, 160, 190))
    # posts: rubber rings on chrome caps
    for c in CIRCLES:
        if c[3] == "bumper":
            # bumper skirt / base ring painted on the playfield; cap is a sprite
            dome(cv, c[0], c[1], c[2] + 2.5, (30, 26, 40), spec_p=30, spec_k=0.6, env=False, flat=0.6)
        elif c[4] in ("post", "slingpost", "flappost"):
            dome(cv, c[0], c[1], c[2] + 1.0, (40, 36, 50), spec_p=30, spec_k=0.7, env=False)
            dome(cv, c[0], c[1], max(1.4, c[2] - 1.2), (230, 220, 120), spec_p=12, outline=0.6)
        else:
            dome(cv, c[0], c[1], c[2] + 0.5, (180, 180, 210), spec_p=12, env=True)

    # gate in the plunger lane
    tube(cv, [(SEGS_by_mat("gate")[0][:2]), (SEGS_by_mat("gate")[0][2:4])], 1.0, (230, 230, 240), outline=1.0)
    # plunger lane floor shading + apron
    lane = np.zeros((H, W))
    lane[LANE_TOP.__int__():H, 291:312] = 1
    cv.mul(lane, 0.7)
    ap = poly_mask(W, H, [(10, 604), (10, 596), (60, 590), (240, 590), (290, 596), (290, 604)])
    # apron only outside the drain gap
    gap = np.zeros((H, W))
    gap[580:, 118:182] = 1
    ap = ap * (1 - gap)
    base = gradient_rgb(H, W, [(0, (60, 50, 90)), (0.96, (90, 80, 130)), (1, (40, 30, 60))])
    emboss(cv, ap, base, depth=2)
    # border: thick black cabinet edge outside the outer wall
    outside = 1 - poly_mask(W, H, outer[:-1] + [(312, 608), (10, 608)])
    outside[:, 312:] = 1
    outside[:, :10] = 1
    wood = gradient_rgb(H, W, [(0, (40, 20, 40)), (1, (20, 10, 26))])
    tex = smooth_noise(W, H, 3, 42)[..., None] * 20
    cv.put_rgb(outside * (1 - poly_mask(W, H, [(290, 170), (312, 160), (312, 608), (290, 608)])), wood + tex)
    return cv


def SEGS_by_mat(m):
    return [s for s in SEGS if s[4] == m]


def ramp_mask(width=12):
    im = Image.new("L", (W, H), 0)
    ImageDraw.Draw(im).line(RAMP_PATH, fill=255, width=width * 2, joint="curve")
    return np.asarray(im).astype(float) / 255.0


def paint_ramp():
    cv = Canvas(W, H)
    # coaster track: red wooden bed with crossties (see-through gaps), twin chrome rails, outer guard rails
    def offset(path, d):
        out = []
        for i, (x, y) in enumerate(path):
            a = path[max(0, i - 1)]
            b = path[min(len(path) - 1, i + 1)]
            tx, ty = b[0] - a[0], b[1] - a[1]
            L = math.hypot(tx, ty) or 1
            out.append((x - ty / L * d, y + tx / L * d))
        return out
    P = RAMP_PATH
    bed = Image.new("L", (W, H), 0)
    ImageDraw.Draw(bed).line(P, fill=255, width=20, joint="curve")
    bedm = np.asarray(bed).astype(float) / 255
    # crossties every 5 px of path length
    ties = Image.new("L", (W, H), 0)
    td = ImageDraw.Draw(ties)
    acc = 0.0
    for i in range(1, len(P)):
        acc += math.dist(P[i - 1], P[i])
        if acc >= 5:
            acc = 0
            a, b = offset([P[i - 1], P[i]], 10), offset([P[i - 1], P[i]], -10)
            td.line([a[1], b[1]], fill=255, width=2)
    tiem = np.asarray(ties).astype(float) / 255 * bedm
    # translucent dark plastic bed (ball under it stays visible as a silhouette)
    cv.put(bedm, (60, 20, 70), 0.55)
    cv.put(tiem, (150, 60, 40))
    cv.put(tiem * (np.roll(tiem, 1, 0) < 0.5), (220, 120, 70))
    for d in (-8.5, 8.5):
        tube(cv, offset(P, d), 2.3, (160, 170, 200))
    # entry & exit flaps
    tube(cv, [(30, 292), (66, 284)], 2.0, (210, 210, 230))
    # sign on the top crossing
    m = pixel_text_mask(W, H, "ROLLER COASTER", 150, 104)
    cv.put(dilate(m, 1), OUTLINE)
    cv.put(m, (255, 240, 90))
    return cv


# ------------------------------------------------------------- sprites ----


def sprite_ball():
    cv = Canvas(15, 15)
    dome(cv, 7.5, 7.5, 6.6, (190, 195, 215), spec_p=20, spec_k=1.0, outline=0.9, env=True)
    return cv


def sprite_flipper():
    cv = Canvas(56, 18)
    piv = (8.5, 9.0)
    tip = (8.5 + FL_LEN, 9.0)
    ox, oy = cv.xx, cv.yy
    d, dx, dy, t = seg_dist(ox, oy, piv, tip)
    r = FL_R0 + (FL_R1 - FL_R0) * t
    h = np.clip(d / r, 0, 1)
    m = (d <= r).astype(float)
    ring = ((d > r - 1.6) & (d <= r)).astype(float)
    nn = np.maximum(d, 1e-6)
    nz = np.sqrt(np.clip(1 - h * h, 0, 1))
    body = shade(dx / nn * h, dy / nn * h, nz * 1.4, (245, 240, 230), 20, 0.9, 0.3, False)
    rub = shade(dx / nn * h, dy / nn * h, nz, (230, 40, 50), 20, 0.6, 0.3, False)
    o = ((d > r) & (d <= r + 1.1)).astype(float)
    cv.put(o, OUTLINE)
    cv.put_rgb(m, body)
    cv.put_rgb(ring, rub)
    dome(cv, piv[0], piv[1], 3.0, (255, 200, 60), spec_p=10, outline=0.7)
    return cv, piv


def sprite_bumper(lit):
    cv = Canvas(32, 32)
    c = 16
    dome(cv, c, c, 13.5, (250, 250, 250) if lit else (150, 150, 165), spec_p=10, outline=1.0, flat=0.5)
    ring_col = (255, 80, 60) if lit else (150, 30, 40)
    ox, oy = cv.xx - c, cv.yy - c
    d = np.hypot(ox, oy)
    a = np.arctan2(oy, ox)
    rays = (np.sin(a * 8) > 0).astype(float) * ((d > 5) & (d < 10.5))
    cv.put(rays, (255, 220, 60) if lit else (120, 90, 40))
    cv.put((d >= 10.5) & (d < 12.5), ring_col)
    dome(cv, c, c, 5, (255, 240, 120) if lit else (110, 100, 70), spec_p=8, outline=0.8)
    if lit:
        cv.put(np.clip(1 - d / 16, 0, 1) * 0.35, (255, 255, 220))
    return cv


# ------------------------------------------------------------ title/side ----


def paint_panorama(w, h, seed=11):
    cv = Canvas(w, h)
    paint_sky(cv, [(0, (8, 4, 34)), (0.45, (40, 12, 84)), (0.75, (110, 30, 100)), (1, (30, 8, 34))], seed=seed, stars=int(w * h / 300))
    moon(cv, w * 0.82, h * 0.2, h * 0.07)
    gy = h * 0.78
    glow = np.clip(1 - np.abs(cv.yy - gy) / (h * 0.35), 0, 1) ** 2
    cv.put(glow, (255, 110, 120), 0.3)
    # coaster on the left
    pts = []
    for i in range(80):
        t = i / 79
        x = w * (0.02 + 0.4 * t)
        y = gy - h * (0.18 + 0.22 * abs(math.sin(t * math.pi * 1.6 + 0.4)))
        pts.append((x, y))
    coaster_lattice(cv, pts, depth=int(h * 0.4))
    tube(cv, pts, max(1.5, h / 160), (220, 60, 80), env=False)
    ferris_wheel(cv, w * 0.62, h * 0.43, h * 0.3, phase=0.3, legs_to=gy, spokes=20, cars=12, bulbs=56, lw=3)
    tent(cv, w * 0.16, gy + 4, w * 0.16, h * 0.22, (220, 40, 60))
    tent(cv, w * 0.88, gy + 4, w * 0.13, h * 0.2, (40, 110, 220))
    bunting(cv, 0, w, h * 0.6, h * 0.08, step=max(8, w // 40), size=max(5, h // 60))
    carousel(cv, w * 0.42, gy - h * 0.22, h * 0.3)
    # ground: dark fairground with light pools
    ground = (cv.yy > gy + h * 0.02).astype(float)
    cv.put_rgb(ground, gradient_rgb(h, w, [(0, (40, 12, 40)), (1, (10, 4, 16))]) + smooth_noise(w, h, 4, seed)[..., None] * 18)
    for i in range(int(w / 30)):
        x = rng.uniform(0, w)
        y = rng.uniform(gy + h * 0.05, h)
        pool = np.clip(1 - np.hypot((cv.xx - x) / (h * 0.08), (cv.yy - y) / (h * 0.025)), 0, 1)
        cv.put(pool, (255, 180, 90), 0.25)
    return cv


def logo(w=300, h=72):
    cv = Canvas(w, h)
    m = gold_letters(cv, "COPPER TILT", 44, (w / 2, h / 2), top=(255, 255, 240), mid=(255, 160, 60), bot=(150, 40, 30),
                     wide=False, spacing=2, shadow=(4, 4), stroke=1)
    return cv

# ------------------------------------------------------------ palette ----

BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], float) + 0.5) / 16 - 0.5


def build_palette(cvs):
    samples = []
    for cv in cvs:
        rgb = cv.rgb[cv.a > 0.5]
        samples.append(rgb[:: max(1, len(rgb) // 40000)])
    s = np.concatenate(samples)
    # bias towards bright: the EHB half-brights cover the darks
    bright = s[s.max(axis=1) > 70]
    im = Image.fromarray(np.clip(bright[None, :, :], 0, 255).astype(np.uint8))
    q = im.quantize(colors=32, method=Image.MEDIANCUT)
    pal = np.array(q.getpalette()[:96], float).reshape(32, 3)
    pal[0] = OUTLINE * 2           # keep a near-black outline colour (its half = OUTLINE)
    pal = np.round(pal / 17) * 17  # 12-bit OCS colour (4 bits/channel)
    full = np.concatenate([pal, np.floor(pal / 2 / 17) * 17])
    return np.unique(full, axis=0)


def quantize(cv, pal, strength=22.0):
    h, w = cv.a.shape
    th = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]
    rgb = cv.rgb + th[..., None] * strength
    flat = rgb.reshape(-1, 3)
    out = np.zeros_like(flat)
    for i in range(0, len(flat), 65536):
        chunk = flat[i:i + 65536]
        # perceptual-ish weights
        d = (((chunk[:, None, :] - pal[None, :, :]) * np.array([0.9, 1.2, 0.7])) ** 2).sum(-1)
        out[i:i + 65536] = pal[d.argmin(1)]
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = out.reshape(h, w, 3).astype(np.uint8)
    rgba[..., 3] = (cv.a > 0.5).astype(np.uint8) * 255
    return Image.fromarray(rgba, "RGBA")


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(ART, exist_ok=True)
    export_geometry()
    pf = paint_playfield()
    rp = paint_ramp()
    ball = sprite_ball()
    fl, piv = sprite_flipper()
    b0, b1 = sprite_bumper(False), sprite_bumper(True)
    side = paint_panorama(200, 300, seed=21)
    title = paint_panorama(480, 270, seed=31)
    lg = logo()
    pal = build_palette([pf, rp, side, title])
    print("palette colours:", len(pal))
    for cv, path in ((pf, "playfield.png"), (rp, "ramp.png"), (ball, "ball.png"), (fl, "flipper.png"),
                     (b0, "bumper.png"), (b1, "bumper_lit.png")):
        quantize(cv, pal, 22 if path in ("playfield.png", "ramp.png") else 10).save(os.path.join(OUT, path))
    quantize(side, pal).save(os.path.join(ART, "side_art.png"))
    quantize(title, pal).save(os.path.join(ART, "title_art.png"))
    quantize(lg, pal, 10).save(os.path.join(ART, "logo.png"))
    pal_im = Image.new("RGB", (len(pal), 1))
    pal_im.putdata([tuple(int(c) for c in p) for p in pal])
    pal_im.save(os.path.join(OUT, "palette.png"))
    print("flipper pivot in sprite:", piv, " ramp length:", round(ramp_s[-1], 1), "apex", round(APEX_S, 1), "down", round(DOWN_S, 1))


if __name__ == "__main__":
    main()
