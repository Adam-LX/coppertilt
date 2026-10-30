#!/usr/bin/env python3
"""Midnight Funfair v3 - builds geometry.json + high-resolution lit art.

  nix-shell -p "python3.withPackages(p: [p.numpy p.pillow])" --run "python3 tools/build_table.py"

Logical table 320x640 units (physics), art at S=4 px/unit -> 1280x2560 playfield with
normal + specular maps for Godot 2D lights. Everything original and procedural (AI-generated
textures can later be dropped into assets/tables/midnight_funfair/src/ and blended in).
"""
import math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
from mf_paint import Img, blur, smooth_noise, shade, MAT
import toys_art

# per-table build: --table <id> picks the geometry module (+ optional theme painter module)
TABLES = {"midnight_funfair": "mf_geometry", "launch_pad": "lp_geometry", "copper_speedway": "cs_geometry"}
TABLE_ID = "midnight_funfair"
for _i, _a in enumerate(sys.argv):
    if _a == "--table" and _i + 1 < len(sys.argv):
        TABLE_ID = sys.argv[_i + 1]
    elif _a.startswith("--table="):
        TABLE_ID = _a.split("=", 1)[1]
G = importlib.import_module(TABLES[TABLE_ID])
THEME = importlib.import_module(G.THEME) if getattr(G, "THEME", None) else None
# M10_ART_HOOK: optional painted-illustration module per table (tools/<table>_art.py):
#   backdrop(pf, B, I) paints the scene under the printed art, light(pf, B, I) relights it after
import illus
try:
    ART = importlib.import_module(TABLE_ID + "_art")
except ImportError:
    ART = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "tables", TABLE_ID)
HD = os.path.join(OUT, "hd")        # modern lit art (default style)
PX = os.path.join(OUT, "pixel")     # Amiga-style 32-colour pixel art, same geometry
S = 4
W, H = G.W, G.H
LC = G.LIGHT_COLORS
rng = random.Random(1987)


def C(name, k=1.0, add=0.0):
    return tuple(min(255.0, c * k + add) for c in LC[name])


# ======================================================================= PLAYFIELD
def paint_base(pf):
    h, w = pf.h, pf.w
    y = (np.arange(h, dtype=np.float32) + 0.5) / S
    # AGA copper bars: night-blue sky -> violet -> big-top red/orange -> magenta -> midway blue
    # brighter, cleaner paint (v4): no muddy near-black bands, the lower field stays royal blue
    stops = getattr(G, "BASE_STOPS", None) or [(0, (46, 72, 172)), (90, (68, 106, 212)), (176, (128, 86, 210)), (206, (218, 70, 104)),
             (290, (244, 122, 62)), (350, (226, 74, 124)), (440, (160, 66, 194)), (540, (82, 112, 220)),
             (640, (56, 70, 160))]
    yb = np.floor(y / 6.0) * 6.0 + 3.0                     # 6-unit copper bands (stepped ramps)
    col = np.zeros((h, 3), np.float32)
    for c in range(3):
        col[:, c] = np.interp(yb, [s[0] for s in stops], [s[1][c] for s in stops])
    pf.rgb[:] = col[:, None, :]
    n1 = smooth_noise(w, h, 96, 3)
    n2 = smooth_noise(w, h, 20, 4)
    p = (n1 - 0.5) * 14 + (n2 - 0.5) * 6
    pf.rgb += np.stack([p * 1.0, p * 0.5, p * 1.2], -1)
    # a soft pool of light over the flipper area keeps the lower playfield readable
    xx, yy = np.meshgrid((np.arange(w, dtype=np.float32) + 0.5) / S, y)
    pool = np.exp(-(((xx - 150) / 120) ** 2 + ((yy - 520) / 110) ** 2))
    pf.rgb += pool[..., None] * np.array([26, 22, 34], np.float32)
    pf.spec[:] = 0.5      # clear-coated paint
    pf.shin[:] = 0.7


def sunburst(pf, cx, cy, r0, r1, rays, c1, c2, y_clip=None, alpha=1.0):
    b = pf.box(cx - r1, cy - r1, cx + r1, cy + r1, 0)
    xx, yy = pf.grid(b)
    ang = np.arctan2(yy - cy, xx - cx)
    rr = np.hypot(xx - cx, yy - cy)
    k = (np.floor((ang / (2 * np.pi) + 0.5) * rays).astype(int) % 2).astype(np.float32)
    edge = np.abs(((ang / (2 * np.pi) + 0.5) * rays) % 1 - 0.5)
    k = np.clip((0.5 - edge) * 60, 0, 1) * k
    fade = np.clip((rr - r0) / 10, 0, 1) * np.clip((r1 - rr) / (r1 * 0.45), 0, 1)
    col = np.asarray(c1, np.float32) * k[..., None] + np.asarray(c2, np.float32) * (1 - k[..., None])
    m = fade
    if y_clip:
        m = m * np.clip((yy - y_clip[0]) / 20, 0, 1) * np.clip((y_clip[1] - yy) / 20, 0, 1)
    pf.put(b, m, col, alpha=alpha)


def stars_sky(pf, x0, y0, x1, y1, n, seed):
    r = random.Random(seed)
    for _ in range(n):
        x, y = r.uniform(x0, x1), r.uniform(y0, y1)
        s = r.random()
        rad = 0.35 + s * 0.6
        b, d, ox, oy = pf.disc_field(x, y, rad * 3)
        if b is None:
            continue
        core = pf.cov(d, rad)
        glow = np.clip(1 - d / (rad * 3), 0, 1) ** 2 * 0.5
        c = (255, 250, 230) if s > 0.6 else (200, 190, 255)
        pf.put(b, np.maximum(core, glow), c)


def moon(pf, cx, cy, r):
    b, d, ox, oy = pf.disc_field(cx, cy, r * 3)
    glow = np.clip(1 - d / (r * 3), 0, 1) ** 2
    pf.add(b, glow * 0.6, (120, 100, 80))
    disc = pf.cov(d, r)
    bite = pf.cov(np.hypot(ox - r * 0.5, oy + r * 0.25), r * 0.86)
    m = disc * (1 - bite)
    shadev = np.clip(0.8 - 0.3 * ox / r, 0, 1.2)
    craters = smooth_noise(b[3] - b[2], b[1] - b[0], 10, 9)
    col = np.stack([255 * shadev, 238 * shadev, 190 * shadev], -1) * (0.85 + 0.15 * craters[..., None])
    pf.put(b, m, col)


def ferris_wheel(pf, cx, cy, r):
    """big printed wheel art behind the top bumpers (alpha-blended so it stays 'printed')."""
    def legs(d, tf, s):
        for sx in (-1, 1):
            d.line([tf(cx, cy), tf(cx + sx * r * 0.7, cy + r * 1.45)], fill=255, width=int(2.2 * s))
            d.line([tf(cx + sx * r * 0.2, cy + r * 0.5), tf(cx + sx * r * 0.55, cy + r * 1.1)], fill=255, width=int(1.0 * s))
    b = pf.box(cx - r * 0.8, cy, cx + r * 0.8, cy + r * 1.5, 2)
    m = pf.pil_mask(b, legs)
    pf.put(b, m, (70, 50, 130), alpha=0.9)
    # rims & spokes
    b = pf.box(cx - r, cy - r, cx + r, cy + r, 3)
    xx, yy = pf.grid(b)
    ox, oy = xx - cx, yy - cy
    d = np.hypot(ox, oy)
    ang = np.arctan2(oy, ox)
    rim = np.maximum(pf.cov(np.abs(d - r), 1.1), pf.cov(np.abs(d - (r - 6)), 0.6))
    rim = np.maximum(rim, pf.cov(np.abs(d - r * 0.42), 0.7))
    sp = 18
    a_sp = (ang * sp / (2 * np.pi)) % 1
    spokes = pf.cov(np.abs(a_sp - 0.5) * 2 * np.pi * d / sp, 0.45) * (d < r)
    # truss zigzag between rims
    zz = (d > r - 6) & (d < r)
    tz = ((ang * sp * 2 / (2 * np.pi)) % 1)
    zig = pf.cov(np.abs((d - (r - 6)) / 6 - np.where(tz < 0.5, tz * 2, 2 - tz * 2)) * 6, 0.45) * zz
    m = np.maximum(np.maximum(rim, spokes), zig)
    col = np.stack([230 + 0 * d, 110 + 60 * (oy / r), 210 + 0 * d], -1)
    pf.put(b, m, col, alpha=0.95)
    hub_b, hd, _, _ = pf.disc_field(cx, cy, 5)
    pf.dome(cx, cy, 5, "gold", (255, 200, 90), height=1.0 * S)
    pal = [(255, 70, 70), (70, 200, 255), (255, 210, 50), (120, 255, 120), (255, 130, 40), (210, 100, 255)]
    for i in range(12):           # gondolas
        a = i * 2 * math.pi / 12 + 0.1
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        pts = [(x - 4.5, y + 2), (x + 4.5, y + 2), (x + 3.5, y + 8), (x - 3.5, y + 8)]
        bb, mm = pf.poly_mask(pts)
        pf.put(bb, mm, pal[i % 6])
        bb, mm = pf.poly_mask([(x - 4.5, y + 2), (x + 4.5, y + 2), (x + 3, y - 1), (x - 3, y - 1)])
        pf.put(bb, mm, tuple(min(255, c + 60) for c in pal[i % 6]))
    for i in range(48):           # printed bulbs (the brightest get real lamps in Godot)
        a = i * 2 * math.pi / 48
        x, y = cx + math.cos(a) * (r + 1.5), cy + math.sin(a) * (r + 1.5)
        bb, dd, _, _ = pf.disc_field(x, y, 2.5)
        pf.put(bb, np.maximum(pf.cov(dd, 0.8), np.clip(1 - dd / 2.5, 0, 1) ** 2 * 0.6),
               (255, 250, 210) if i % 2 else (255, 200, 80))


def carousel(pf, cx, cy, r, alpha=0.85):
    """carousel canopy seen from above: scalloped candy-stripe disc (printed, behind the top bumpers)."""
    b = pf.box(cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4, 2)
    xx, yy = pf.grid(b)
    ox, oy = xx - cx, yy - cy
    d = np.hypot(ox, oy)
    ang = np.arctan2(oy, ox)
    n = 16
    edge = r + 3.0 * np.abs(np.cos(ang * n / 2))
    m = pf.cov(d - edge + 1.0, 1.0) if False else np.clip(edge - d, 0, 1)
    seg = ((ang / (2 * np.pi) + 0.5) * n).astype(int) % 2
    c1, c2 = np.array([200, 36, 70], np.float32), np.array([246, 206, 120], np.float32)
    col = np.where(seg[..., None] == 0, c1, c2)
    shade = np.clip(0.55 + 0.45 * (1 - d / (r + 3)) + 0.15 * (-(ox + oy) / (r * 1.4)), 0.4, 1.15)
    pf.put(b, m, col * shade[..., None], alpha=alpha)
    pf.put(b, np.clip(1 - np.abs(d - r * 0.55) / 0.9, 0, 1) * (d < r), (255, 230, 150), alpha=0.6 * alpha)
    for i in range(32):
        a = i * 2 * math.pi / 32
        x, y = cx + math.cos(a) * (r + 1.5), cy + math.sin(a) * (r + 1.5)
        bb, dd, _, _ = pf.disc_field(x, y, 2.2)
        pf.put(bb, np.clip(1 - dd / 2.2, 0, 1) ** 1.5, (255, 246, 200) if i % 2 else (255, 190, 80), alpha=alpha)
    pf.dome(cx, cy, 6, "gold", (255, 200, 90), height=1.0 * S)


def balloons(pf, items, tie):
    """bunch of printed balloons on strings tied at one point."""
    for x, y, r, c in items:
        b = pf.box(min(x, tie[0]) - 2, min(y, tie[1]) - 2, max(x, tie[0]) + 2, max(y, tie[1]) + 2, 2)
        m = pf.pil_mask(b, lambda d, tf, sc, x=x, y=y: d.line([tf(x, y + r), tf(*tie)], fill=255, width=max(1, int(0.5 * sc))))
        pf.put(b, m, (230, 230, 240), alpha=0.7)
    for x, y, r, c in items:
        b, d, ox, oy = pf.disc_field(x, y, r * 1.2)
        e = np.hypot(ox, oy / 1.18)
        body = np.clip(r - e, 0, 1)
        hl = np.clip(1 - np.hypot(ox + r * 0.35, oy + r * 0.45) / (r * 0.45), 0, 1) ** 2
        cc = np.asarray(c, np.float32)
        col = cc[None, None, :] * np.clip(1.05 - 0.45 * e / r, 0.45, 1)[..., None] + hl[..., None] * 150
        pf.put(b, pf.cov(np.abs(e - r), 0.5), (14, 8, 24))
        pf.put(b, body, col, ht=np.clip(r - e, 0, r) * 0.15 * S, ht_mode="max", spec=0.9, shin=0.8)
        bb, mm = pf.poly_mask([(x - 1.2, y + r * 1.18 + 1.6), (x + 1.2, y + r * 1.18 + 1.6), (x, y + r * 1.18 - 0.4)])
        pf.put(bb, mm, cc * 0.7)


def bunting(pf, x0, x1, y, sag, n, pal):
    """string of triangular pennant flags."""
    def yy(x):
        u = (x - x0) / (x1 - x0)
        return y + sag * 4 * u * (1 - u)
    b = pf.box(x0, y - 1, x1, y + sag + 1, 2)
    m = pf.pil_mask(b, lambda d, tf, sc: d.line([tf(x0 + (x1 - x0) * i / 24, yy(x0 + (x1 - x0) * i / 24)) for i in range(25)],
                                               fill=255, width=max(1, int(0.6 * sc))))
    pf.put(b, m, (240, 230, 210), alpha=0.8)
    w = (x1 - x0) / n
    for i in range(n):
        xa, xb = x0 + w * (i + 0.12), x0 + w * (i + 0.88)
        xm = (xa + xb) / 2
        bb, mm = pf.poly_mask([(xa, yy(xa)), (xb, yy(xb)), (xm, yy(xm) + w * 0.95)])
        pf.put(bb, mm, pal[i % len(pal)], alpha=0.92)


def tent_stripes(pf, pts, c1, c2, alpha=0.75, period=7.0):
    """diagonal candy stripes clipped to a polygon (dead corners under the inlane guides)."""
    b, m = pf.poly_mask(pts)
    if b is None:
        return
    xx, yy = pf.grid(b)
    k = (((xx + yy) / period) % 1 < 0.5)[..., None]
    col = np.where(k, np.asarray(c1, np.float32), np.asarray(c2, np.float32))
    shade = np.clip(1.0 - (yy - yy.min()) / max(1.0, yy.max() - yy.min()) * 0.4, 0.55, 1)[..., None]
    pf.put(b, m, col * shade, alpha=alpha)


def tower_art(pf, cx, cy):
    """helter-skelter tower seen from above: striped spiral disc + shadow ring (printed)."""
    b, d, ox, oy = pf.disc_field(cx, cy, 26)
    ang = np.arctan2(oy, ox)
    spiral = ((ang / (2 * np.pi) * 3 + d / 9) % 1) < 0.5
    col = np.where(spiral[..., None], np.array([235, 40, 60], np.float32), np.array([250, 235, 205], np.float32))
    shadev = np.clip(1.05 - 0.4 * (ox + oy) / 26, 0.5, 1.2)[..., None]
    pf.put(b, pf.cov(d, 25), col * shadev, ht=np.clip(25 - d, 0, 25) * 0.25 * S, ht_mode="max")
    pf.put(b, pf.cov(np.abs(d - 25), 1.0), (40, 10, 30))


def coaster_lattice(pf, path, every=10, depth=18):
    def f(d, tf, s):
        for i in range(0, len(path) - every, every):
            (x, y), (x2, y2) = path[i], path[i + every]
            d.line([tf(x + 4, y + 6), tf(x + 4, y + 6 + depth)], fill=200, width=int(0.9 * s))
            d.line([tf(x + 4, y + 6), tf(x2 + 4, y2 + 6 + depth)], fill=150, width=int(0.6 * s))
            d.line([tf(x + 4, y + 6 + depth), tf(x2 + 4, y2 + 6)], fill=150, width=int(0.6 * s))
    xs, ys = [p[0] for p in path], [p[1] for p in path]
    b = pf.box(min(xs), min(ys), max(xs) + 8, max(ys) + depth + 8, 2)
    m = pf.pil_mask(b, f)
    pf.put(b, m, (110, 60, 120), alpha=0.75)


def ghost(pf, cx, cy, s=1.0, col=(200, 230, 255)):
    pts = [(cx - 8 * s, cy + 9 * s)]
    for i in range(7):
        pts.append((cx - 8 * s + i * 16 * s / 6, cy + (9 if i % 2 == 0 else 5) * s))
    pts += [(cx + 8 * s, cy + 9 * s), (cx + 8 * s, cy - 2 * s)]
    for i in range(1, 12):
        a = i * math.pi / 12
        pts.append((cx + math.cos(a) * 8 * s, cy - 2 * s - math.sin(a) * 9 * s))
    b, m = pf.poly_mask(pts)
    pf.put(b, m, col, alpha=0.9)
    for ex in (-3, 3):
        bb, dd, _, _ = pf.disc_field(cx + ex * s, cy - 3 * s, 1.8 * s)
        pf.put(bb, pf.cov(dd, 1.6 * s), (30, 10, 50))
    bb, dd, _, _ = pf.disc_field(cx, cy + 3 * s, 1.8 * s)
    pf.put(bb, pf.cov(dd, 1.5 * s), (30, 10, 50))


def haunted_house(pf, x, y, k=1.0):
    body0 = [(x - 16, y), (x - 16, y - 18), (x - 20, y - 18), (x - 8, y - 32), (x - 3, y - 27), (x - 3, y - 36),
            (x + 2, y - 36), (x + 2, y - 26), (x + 4, y - 24), (x + 18, y - 16), (x + 15, y - 16), (x + 15, y)]
    body = [(x + (px - x) * k, y + (py - y) * k) for px, py in body0]
    b, m = pf.poly_mask(body)
    sb, sm = pf.poly_mask([(px + 1.5, py + 2.0) for px, py in body])     # drop shadow
    pf.put(sb, sm, (10, 4, 20), alpha=0.5)
    b, m = pf.poly_mask(body)
    pf.put(b, m, (24, 10, 34))
    for wx, wy in ((-10, -12), (-3, -12), (8, -9), (-6, -22), (-1, -32)):
        wx, wy = wx * k, wy * k
        bb, mm = pf.poly_mask([(x + wx - 1.3, y + wy - 1.6), (x + wx + 1.3, y + wy - 1.6), (x + wx + 1.3, y + wy + 1.6), (x + wx - 1.3, y + wy + 1.6)])
        pf.put(bb, mm, (255, 220, 90))


def printed_text(pf, text, size, x, y, col=(255, 240, 210), outline=(20, 6, 30), angle=0.0, wide=False,
                 spacing=0.0, glow=None, grad=None, shadow=True):
    if shadow:      # printed drop shadow, down-right (light is top-left)
        o = max(0.5, size * 0.09)
        b, m = pf.text_mask(text, size, x + o, y + o * 1.2, angle=angle, wide=wide, spacing=spacing, stroke=size * 0.09)
        if b is not None:
            pf.put(b, m, (8, 4, 18), alpha=0.55)
    if glow:
        b, m = pf.text_mask(text, size, x, y, angle=angle, wide=wide, spacing=spacing, stroke=size * 0.12)
        if b is not None:
            p = int(6 * S)
            y0, y1, x0, x1 = max(0, b[0] - p), min(pf.h, b[1] + p), max(0, b[2] - p), min(pf.w, b[3] + p)
            big = np.zeros((y1 - y0, x1 - x0), np.float32)
            big[b[0] - y0:b[1] - y0, b[2] - x0:b[3] - x0] = m
            pf.add((y0, y1, x0, x1), np.clip(blur(big, 2.0 * S) * 1.6, 0, 1) * 0.9, glow)
    b, m = pf.text_mask(text, size, x, y, angle=angle, wide=wide, spacing=spacing, stroke=size * 0.09)
    if b is not None:
        pf.put(b, m, outline)
    b, m = pf.text_mask(text, size, x, y, angle=angle, wide=wide, spacing=spacing)
    if b is None:
        return
    if grad:
        hgt = m.shape[0]
        t = np.linspace(0, 1, hgt, dtype=np.float32)[:, None]
        if len(grad) == 2 and not isinstance(grad[0][0], float):
            grad = [(0.0, grad[0]), (1.0, grad[1])]
        c = np.stack([np.interp(t[:, 0], [g[0] for g in grad], [g[1][k] for g in grad]) for k in range(3)], -1)
        c = np.broadcast_to(c[:, None, :], m.shape + (3,)).astype(np.float32)
        pf.put(b, m, c, ht=m * 0.6 * S, ht_mode="add")
    else:
        pf.put(b, m, col)


def halo(pf, x, y, r, c):
    """soft painted light-bleed around an insert (reads as a backlit, glossy playfield)."""
    b, d, _, _ = pf.disc_field(x, y, r)
    g = np.clip(1 - d / r, 0, 1) ** 2
    pf.add(b, g * 0.30, tuple(float(v) for v in c))


def inlane_art(pf):
    """painted inlane / outlane strips with down-pointing chevrons (flow towards the flippers)."""
    lanes = [(19.0, (150, 255, 160)), (38.0, (255, 214, 90)), (262.0, (255, 214, 90)), (281.0, (255, 120, 120))]
    y0, y1, nk = 468, 548, 4
    if getattr(G, "INLANES", None):       # inlanes v2: inlane between separator post and sling, narrow outlane
        il, ir = G.INLANES
        lanes = [(il["outlane_x"], (150, 255, 160)), (il["inlane"][0][0], (255, 214, 90)),
                 (ir["inlane"][0][0], (255, 214, 90)), (ir["outlane_x"], (255, 120, 120))]
        y0, y1, nk = 472, 528, 3
    for x, col in lanes:
        c = np.asarray(col, np.float32)
        b, m = pf.poly_mask([(x - 4.2, y0), (x + 4.2, y0), (x + 4.2, y1), (x - 4.2, y1)])
        if b is None:
            continue
        xx, yy = pf.grid(b)
        fade = np.clip(1 - np.abs(yy - (y0 + y1) / 2) / ((y1 - y0) / 2 + 4), 0, 1)
        pf.put(b, m * fade * 0.55, c * 0.42)
        for k in range(nk):
            cy = y0 + 8 + k * 18
            bb, mm = pf.poly_mask([(x - 3.4, cy), (x, cy + 4.2), (x + 3.4, cy), (x + 3.4, cy + 2.2), (x, cy + 6.4), (x - 3.4, cy + 2.2)])
            if bb is not None:
                pf.put(bb, mm, c * 0.9 + 20, spec=0.9, shin=0.85)


def insert(pf, name, L, lens_only=False):
    x, y = L["pos"]
    kind, size = L["kind"], L["size"]
    c = np.asarray(LC[L["color"]], np.float32)
    if kind == "round":
        pts = None
        b, d, ox, oy = pf.disc_field(x, y, size + 1.2)
        pf.put(b, pf.cov(d, size + 1.6), (14, 8, 24))                   # outline
        rim = pf.cov(d, size + 1.0)
        pf.put(b, rim, (225, 225, 235), ht=-0.3 * S, spec=0.9, shin=0.8)
        lens = pf.cov(d, size)
        t = np.clip(d / size, 0, 1)
        halo(pf, x, y, size * 2.4, c)
        b, d, ox, oy = pf.disc_field(x, y, size + 1.2)
        pf.put(b, pf.cov(d, size + 1.6), (14, 8, 24))                   # outline
        pf.put(b, pf.cov(d, size + 1.0), (235, 235, 245), ht=-0.3 * S, spec=0.9, shin=0.8)
        col = c * (0.56 + 0.30 * (1 - t) ** 1.5)[..., None] + 18   # unlit: clearly coloured jewel lens
        hl = np.clip(1 - np.hypot(ox + size * 0.35, oy + size * 0.35) / (size * 0.55), 0, 1) ** 2
        pf.put(b, lens, col + hl[..., None] * 150, ht=-0.6 * S, spec=0.95, shin=0.9)
    else:
        if kind == "arrow":
            a = math.radians(L["dir"])
            fx, fy = math.cos(a), math.sin(a)
            px, py = -fy, fx
            s = size
            pts = [(x + fx * s * 1.3, y + fy * s * 1.3), (x + px * s * 0.9, y + py * s * 0.9),
                   (x + px * s * 0.35, y + py * s * 0.35), (x + px * s * 0.35 - fx * s, y + py * s * 0.35 - fy * s),
                   (x - px * s * 0.35 - fx * s, y - py * s * 0.35 - fy * s), (x - px * s * 0.35, y - py * s * 0.35),
                   (x - px * s * 0.9, y - py * s * 0.9)]
        else:
            pts = []
            for i in range(10):
                rr = size if i % 2 == 0 else size * 0.45
                a = -math.pi / 2 + i * math.pi / 5
                pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        halo(pf, x, y, size * 2.0, c)
        b, m = pf.poly_mask(pts)
        if b is None:
            return
        ring = np.clip(blur(m, 0.9 * S) * 2.2, 0, 1)
        ol = np.clip(blur(m, 1.4 * S) * 3.0, 0, 1)
        pf.put(b, np.maximum(ol - ring, 0), (14, 8, 24))                  # outline
        pf.put(b, np.maximum(ring - m, 0) * 0.9, (225, 225, 235), ht=-0.3 * S, spec=0.9)
        inner = blur(m, 0.6 * S)
        pf.put(b, m, c[None, None, :] * (0.54 + 0.36 * inner[..., None]) + 16, ht=-0.6 * S, spec=0.95, shin=0.9)
        # gloss streak across the top of the plastic insert
        xx, yy = pf.grid(b)
        streak = np.clip(1 - np.abs((xx - x) * 0.5 + (yy - y) + size * 0.35) / (size * 0.22), 0, 1) * m
        pf.add(b, streak * 0.55, (255, 255, 255))


def chrome_rails(pf):
    for pts in G.RAILS:
        if pts is G.RAILS[0]:
            continue
        pf.tube(pts, 1.6, "chrome", (235, 235, 245), height=3.2 * S, z=1.5)


def cabinet(pf):
    """wood side rails outside the outer wall + chrome inner lip."""
    outer = G.OUTER
    poly = outer + [(312.0, H), (320.0, H), (320.0, 0.0), (0.0, 0.0), (0.0, H), (10.0, H)]
    b = (0, pf.h, 0, pf.w)
    im = Image.new("L", (pf.w, pf.h), 0)
    ImageDraw.Draw(im).polygon([(x * S, y * S) for x, y in outer + [(312.0, H), (10.0, H)]], fill=255)
    inside = np.asarray(im, np.float32) / 255.0
    wood_m = 1 - inside
    xx, yy = pf.grid(b)
    wood = illus.wood(pf.w, pf.h, S, seed=21, along_y=True)
    # lacquer: a long soft sheen down the rails + darker toward the glass edge (depth)
    sheen = np.exp(-((xx % 160) - 40) ** 2 / 900.0) * 0.18 + 0.92
    edge = np.clip(blur(inside, 5 * S) * 1.6, 0, 1)
    wood = wood * (sheen * (1 - 0.35 * edge))[..., None]
    pf.put(b, wood_m, wood, ht=6 * S, spec=0.55, shin=0.6)
    pf.tube(outer, 2.0, "chrome", (240, 240, 250), height=3.5 * S, z=6.0)
    # plunger lane floor: brushed metal strip
    lb = pf.box(290, G.LANE_TOP, 312, H, 0)
    xx, yy = pf.grid(lb)
    brushed = smooth_noise(lb[3] - lb[2], lb[1] - lb[0], 3, 30)
    pf.put(lb, np.ones_like(xx), np.stack([26 + 16 * brushed] * 3, -1) * np.array([1.0, 0.95, 1.2]), spec=0.6)


def standup(pf, s, col):
    x0, y0, x1, y1 = s
    pts = [(x0 - 0.5, y0), (x0 + 2.2, y0), (x1 + 2.2, y1), (x1 - 0.5, y1)]
    b, m = pf.poly_mask(pts)
    xx, yy = pf.grid(b)
    pf.put(b, m, np.broadcast_to(np.asarray(col, np.float32), m.shape + (3,)) * 1.0, ht=3.5 * S, spec=0.7, shin=0.6)


def hole(pf, x, y, r):
    b, d, ox, oy = pf.disc_field(x, y, r + 3)
    pf.tube([(x, y)], r + 2.0, "chrome", (230, 230, 240), height=1.5 * S)
    pit = pf.cov(d, r)
    depth = np.clip(1 - d / r, 0, 1)
    pf.put(b, pit, np.stack([10 + 30 * (1 - depth), 4 + 10 * (1 - depth), 16 + 30 * (1 - depth)], -1),
           ht=-6 * S * depth, ht_mode="set", spec=0.1)


def ramp_block(pf, blk, col):
    bt, mt = pf.poly_mask([(x, y + 2.2) for x, y in blk])
    if bt is not None:
        pf.put(bt, mt, np.asarray(col, np.float32) * 0.3, ht=np.full_like(mt, 2.5 * S), ht_mode="max", spec=0.4)
    b, m = pf.poly_mask(blk)
    if b is None:
        return
    inner = blur(m, 1.2 * S)
    pf.put(b, m, np.asarray(col, np.float32) * (0.66 + 0.5 * inner[..., None]), ht=5 * S * inner, ht_mode="max", spec=0.85, shin=0.8)
    pf.tube(blk, 0.9, "chrome", (240, 240, 250), height=2 * S, z=4.5)


def sling(pf, tri, col):
    A, B, Cc = tri
    th = 2.4   # plastic thickness seen from the front
    bt, mt = pf.poly_mask([(A[0], A[1] + th), (B[0], B[1] + th), (Cc[0], Cc[1] + th)])
    pf.put(bt, mt, np.asarray(col, np.float32) * 0.32, ht=np.full_like(mt, 3 * S), ht_mode="max", spec=0.4)
    b, m = pf.poly_mask([A, B, Cc])
    inner = blur(m, 2.0 * S)
    pf.put(b, m, np.asarray(col, np.float32) * (0.62 + 0.55 * inner[..., None]), ht=6 * S * inner, ht_mode="max", spec=0.85, shin=0.8)
    # bright plastic gloss band just inside the long (kicker) edge
    edge = np.clip(blur(m, 0.8 * S) * 2.0, 0, 1) - np.clip(blur(m, 2.2 * S) * 2.0, 0, 1)
    pf.add(b, np.clip(edge, 0, 1) * 0.35, (255, 255, 255))
    pf.tube([A, B, Cc, A], 1.4, "rubber", (245, 245, 240), height=2.5 * S, z=3)
    for p in (A, B, Cc):
        pf.dome(p[0], p[1], 2.6, "chrome", (240, 240, 250), height=2.5 * S, z=4)


def posts(pf):
    for x, y, r, mat, name in G.CIRCLES:
        if mat == "bumper" or name in ("slingpost",):
            continue
        band = (18, 16, 22) if mat == "rubber" and name != "centerpost" else ((150, 30, 36) if mat == "rubber" else (120, 120, 132))
        pf.tube([(x, y + 0.4), (x, y + 2.4)], r + (1.4 if mat == "rubber" else 0.4), "rubber" if mat == "rubber" else "chrome", band, height=2.0 * S, z=1.0)
        if mat == "rubber":
            pf.dome(x, y, r + 1.4, "rubber", (30, 28, 34) if name != "centerpost" else (240, 60, 60), height=2.6 * S, z=2.5)
            pf.dome(x, y, max(1.4, r - 0.6), "chrome", (240, 240, 250), height=2.0 * S, z=4.5, flat=0.3)
        else:
            pf.dome(x, y, r + 0.4, "chrome", (240, 240, 250), height=2.5 * S, z=3.5)


def bumper_bases(pf):
    for x, y, r in G.BUMPERS:
        b, d, ox, oy = pf.disc_field(x, y, r + 5)
        glow = np.clip(1 - d / (r + 5), 0, 1)
        pf.mul(b, glow, 0.55)
        bs, ds, _, _ = pf.disc_field(x + 3.5, y + 5.0, r + 4)
        pf.mul(bs, blur(pf.cov(ds, r + 2.5), 1.6 * S), 0.45)
        ring = pf.cov(np.abs(d - (r + 3.6)), 0.9)
        pf.add(b, ring * 0.55, (255, 210, 90))                            # lit skirt ring
        pf.tube([(x, y)], r + 2.2, "chrome", (220, 220, 235), height=1.6 * S, z=0.5)


def lane_guides(pf):
    # rollover wire switches in lanes / inlanes / orbits
    spots = getattr(G, "GUIDE_SPOTS", None) or [[38.0, 498.0], [262.0, 498.0], [19.0, 498.0], [281.0, 498.0],
                                           [24.0, 226.0], [277.0, 226.0]]
    for x, y in spots:
        pf.tube([(x, y - 4), (x, y + 4)], 0.45, "chrome", (240, 240, 250), height=0.8 * S, z=0.4)
        b, d, ox, oy = pf.disc_field(x, y, 6)
        pf.put(b, pf.cov(np.abs(d - 5.5), 0.35), (180, 180, 200), alpha=0.6)


def spinner_bracket(pf):
    if not getattr(G, "SPINNER", None):
        return
    x, y = G.SPINNER["pos"]
    hw = G.SPINNER["w"] / 2
    pf.tube([(x - hw + 1, y), (x + hw - 1, y)], 0.7, "chrome", (240, 240, 250), height=2 * S, z=4)
    for sx in (-1, 1):
        pf.dome(x + sx * (hw - 1.5), y, 1.6, "chrome", (240, 240, 250), height=2 * S, z=4)


def drop_slots(pf):
    for d in G.DROPS:
        x0, y0, x1, y1 = d["seg"]
        pf.tube([(x0, y0), (x1, y1)], 2.4, "plastic", (8, 6, 10), height=-1.0 * S)


def kickback_hole(pf):
    if not getattr(G, "KICKBACK", None):
        return
    x, y = G.KICKBACK["launch"]
    b, d, _, _ = pf.disc_field(x, y + 22, 5)
    pf.put(b, pf.cov(d, 4.5), (12, 8, 16), ht=-2 * S)
    pf.tube([(x, y + 22)], 5.2, "chrome", (230, 230, 240), height=1 * S)


def apron(pf):
    pts = [(10, H - 14), (130, H - 14), (150, H - 4), (170, H - 14), (290, H - 14), (290, H), (10, H)]
    b, m = pf.poly_mask(pts)
    xx, yy = pf.grid(b)
    pf.put(b, m, np.stack([40 + 0 * xx, 30 + 0 * xx, 70 + 0 * xx], -1), ht=4 * S, spec=0.6)
    printed_text(pf, "COPPER TILT", 6, 60, H - 7, col=(255, 200, 90), wide=True)
    printed_text(pf, getattr(G, "TITLE", "MIDNIGHT FUNFAIR"), 6, 232, H - 7, col=getattr(G, "TITLE_COLOR", (120, 230, 255)), wide=True)


def letters_on_inserts(pf):
    for key, lab in [(k, None) for k in getattr(G, "LETTER_KEYS", ["lane_", "ride_", "duck_", "shy_"])]:
        for n, L in G.LIGHTS.items():
            if n.startswith(key):
                printed_text(pf, n.split("_")[1], L["size"] * 1.5, L["pos"][0], L["pos"][1] + 0.2,
                             col=(255, 255, 240), outline=(20, 8, 20))
    for i in range(2, 7):
        L = G.LIGHTS["mult%d" % i]
        printed_text(pf, "%dX" % i, 4.2, L["pos"][0], L["pos"][1] + 0.2, col=(255, 255, 240))


CHROME = [(0.0, (40, 76, 190)), (0.40, (196, 228, 255)), (0.49, (255, 255, 255)), (0.51, (70, 40, 24)),
          (0.70, (214, 128, 52)), (1.0, (255, 232, 168))]      # Amiga chrome: sky, horizon, earth


def paint_mf_theme(pf):
    # --- top: night sky, moon, ferris wheel = central motif behind the top bumpers
    stars_sky(pf, 20, 18, 300, 200, 150, 5)
    moon(pf, 58, 98, 12)
    if not getattr(G, "DISCS", None):
        carousel(pf, 162, 140, 50)      # printed canopy (replaced by the rotating carousel toy)
    # --- mid: big-top sunburst around the helter-skelter
    sunburst(pf, G.TOWER[0], G.TOWER[1], 20, 150, 28, (236, 112, 60), (178, 48, 74), y_clip=(196, 350), alpha=0.8)
    tower_art(pf, *G.TOWER)
    coaster_lattice(pf, G.RAMPS[0]["path"][:150], depth=12)
    for gx, gy, sc in ((112, 352, 0.8), (72, 400, 0.7), (196, 446, 0.6)):
        ghost(pf, gx, gy, sc, (200, 240, 255))
    haunted_house(pf, 270, 352, 0.7)
    # --- lower centre: chrome MIDNIGHT FUNFAIR logo on its own burst
    # --- lower centre: the ferris wheel rises behind the chrome MIDNIGHT FUNFAIR logo
    sunburst(pf, 130, 432, 0, 70, 20, (150, 70, 200), (100, 40, 150), y_clip=(380, 480), alpha=0.6)
    ferris_wheel(pf, 130, 432, 46)
    # --- fill the mid/lower gaps: balloons, bunting, candy-striped dead corners
    balloons(pf, [(40, 420, 5.5, (255, 70, 90)), (52, 412, 5.0, (80, 200, 255)), (50, 428, 4.6, (255, 220, 60))], (48, 446))
    balloons(pf, [(236, 436, 5.0, (120, 255, 130)), (248, 446, 4.6, (255, 120, 220)), (234, 452, 4.2, (255, 160, 50))], (242, 468))
    bunting(pf, 100, 200, 514, 9, 9, [(255, 70, 90), (255, 220, 60), (80, 200, 255), (120, 255, 130), (255, 120, 220)])
    tent_stripes(pf, [(30, 530), (94, 574), (94, 628), (30, 628)], (214, 44, 86), (255, 206, 130), alpha=0.72)
    tent_stripes(pf, [(270, 530), (206, 574), (206, 628), (270, 628)], (44, 110, 226), (255, 206, 130), alpha=0.72)
    inlane_art(pf)
    for i in range(3):
        sunburst(pf, (60, 160, 250)[i], (36, 30, 40)[i], 0, 14, 12, (255, 220, 140), (140, 60, 160), alpha=0.35)
    printed_text(pf, "MIDNIGHT", 11, 130, 416, spacing=0.6, glow=(120, 160, 255), grad=CHROME,
                 outline=(8, 8, 30))
    printed_text(pf, "FUNFAIR", 18, 130, 440, spacing=0.8, glow=(255, 90, 170), grad=CHROME,
                 outline=(8, 8, 30))
    # --- shot labels (big, readable)
    lab = dict(col=(255, 238, 196), outline=(16, 4, 24))
    printed_text(pf, "COASTER", 4.6, 68, 382, angle=90, **lab)
    printed_text(pf, "GHOST TRAIN", 4.2, 200, 340, angle=80, **lab)
    printed_text(pf, "ORBIT", 5, 24, 254, angle=90, col=(255, 240, 120))
    printed_text(pf, "ORBIT", 5, 277, 254, angle=-90, col=(255, 240, 120))
    printed_text(pf, "TUNNEL", 3.8, 48, 318, col=(255, 170, 235))
    printed_text(pf, "FORTUNE", 4.2, 122, 300, col=(255, 255, 255))
    printed_text(pf, "HAUNTED", 3.8, 268, 370, col=(255, 170, 235))
    printed_text(pf, "D U C K", 4.2, 242, 247, angle=-90, col=(255, 196, 96))
    printed_text(pf, "COCONUT SHY", 4.2, 212, 405, angle=36, col=(130, 236, 255))
    printed_text(pf, "R I D E", 4.2, 59, 247, angle=90, col=(255, 130, 118))
    printed_text(pf, "SHOOT AGAIN", 4, 150, 566, col=(255, 170, 150))
    printed_text(pf, "EXTRA BALL", 4, 150, 504, col=(255, 214, 150))
    printed_text(pf, "BONUS MULTIPLIER", 3.4, 150, 482, col=(255, 214, 150))
    printed_text(pf, "KICKBACK", 3.6, 19, 518, angle=90, col=(150, 255, 160))
    printed_text(pf, "JACKPOT", 4.4, 150, 397, col=(255, 255, 255))
    printed_text(pf, "LOCK", 3.6, 270, 420, col=(255, 170, 235))
    printed_text(pf, "SUPER", 3.2, 150, 358, col=(255, 214, 120))


def paint_playfield():
    pf = Img(W, H, S)
    paint_base(pf)
    if ART and hasattr(ART, "backdrop"):
        ART.backdrop(pf, sys.modules[__name__], illus)
    if THEME:
        THEME.paint(pf, sys.modules[__name__])
    else:
        paint_mf_theme(pf)
    if ART and hasattr(ART, "light"):
        ART.light(pf, sys.modules[__name__], illus)
    # inlane arrows painted
    # --- physical bits
    cabinet(pf)
    lane_guides(pf)
    for blk, col in zip(G.BLOCKS, getattr(G, "BLOCK_COLORS", None) or [(200, 40, 50), (40, 170, 80), (210, 160, 40)]):
        ramp_block(pf, blk, col)
    for i, tri in enumerate(G.SLINGS):
        sling(pf, tri, getattr(G, "SLING_COLORS", ((220, 40, 120), (40, 150, 230)))[i])
    for t in G.TARGETS:
        standup(pf, t["seg"], getattr(G, "STANDUP_COLOR", (255, 220, 60)))
    drop_slots(pf)
    for h in G.HOLES:
        hole(pf, h["pos"][0], h["pos"][1], h["r"])
    toys_art.paint(pf, sys.modules[__name__])
    kickback_hole(pf)
    bumper_bases(pf)
    spinner_bracket(pf)
    chrome_rails(pf)
    posts(pf)
    apron(pf)
    for n, L in G.LIGHTS.items():
        insert(pf, n, L)
    letters_on_inserts(pf)
    # shooter-lane meter captions go on top of the lane plate
    printed_text(pf, "SKILL", 3.4, 301, 527, angle=-90, col=(140, 255, 150))
    printed_text(pf, "POWER", 3.2, 301, 498, angle=-90, col=(255, 200, 150))
    # ramp shadows (from overlay) are added later by main()
    return pf


def gloss_pass(pf):
    """clear-coat sheen: two broad soft window reflections across the glass/paint + slight vibrance."""
    xx, yy = np.meshgrid((np.arange(pf.w, dtype=np.float32) + 0.5) / S, (np.arange(pf.h, dtype=np.float32) + 0.5) / S)
    u = xx * 0.45 + yy * 0.22
    sheen = np.exp(-((u - 70) / 16) ** 2) * 0.9 + np.exp(-((u - 150) / 9) ** 2) * 0.5
    sheen *= 0.6 + 0.4 * smooth_noise(pf.w, pf.h, 140, 77)
    pf.rgb += sheen[..., None] * 14.0
    m = pf.rgb.mean(-1, keepdims=True)
    pf.rgb = np.clip(m + (pf.rgb - m) * 1.10, 0, 255)


# ======================================================================= OVERLAY (ramps)
def ramp_elev(s, apex, down, L):
    """0..1 ramp height along the path: climb to the apex, level, then descend to the exit (2.5D)."""
    s = np.asarray(s, np.float32)
    up = np.clip(s / max(apex, 1.0), 0, 1)
    dn = np.clip(1 - (s - down) / max(L - down, 1.0), 0, 1)
    e = np.where(s < apex, up, np.where(s < down, 1.0, dn))
    return e * e * (3 - 2 * e)


RAMP_DROP0, RAMP_DROP = 2.0, 8.0
RAMP_RGB = {"red": (230, 40, 50), "green": (40, 210, 90), "orange": (240, 120, 30), "blue": (40, 120, 235),
            "silver": (170, 180, 200), "cyan": (40, 200, 230), "yellow": (235, 200, 40), "purple": (150, 60, 220)}    # visible wall drop (units) at ground level / extra at full height


def ramp_support(ov, x, y, drop, kind="chrome"):
    """a stilt from the ramp edge down to the playfield + its foot (seen slightly from the front)."""
    ov.tube([(x, y), (x, y + drop)], 0.9, kind, (225, 225, 235), height=1.6 * S, z=1)
    ov.dome(x, y + drop, 1.9, kind, (200, 200, 212), height=1.0 * S, z=0.2, flat=0.5)


def paint_overlay():
    ov = Img(W, H, S, alpha=True)
    for ri, rp in enumerate(G.RAMPS):
        if rp.get("art") == "tube":
            continue        # VUK launch tube: painted by toys_art.overlay
        path = [tuple(p) for p in rp["path"]]
        s = rp["s"]
        hw = rp["width"] / 2
        if rp["kind"] == "plastic":
            ds = rp["down_s"]
            cut = next(i for i, v in enumerate(s) if v >= ds - 30)
            plastic, wire = path[:cut + 1], path[cut:]
            col = RAMP_RGB.get(rp["color"], (40, 210, 90))
            f = ov.line_field(plastic, hw + 3 + RAMP_DROP0 + RAMP_DROP)
            b, d, ox, oy, T = f
            m = ov.cov(d, hw)
            across = np.clip(d / hw, 0, 1)
            # 2.5D side walls: the floor footprint swept down by its height (front faces visible)
            E = ramp_elev(T, rp["apex_s"], rp["down_s"], s[-1])
            drop = (RAMP_DROP0 + RAMP_DROP * E) * S
            wall = np.zeros_like(m)
            grad = np.zeros_like(m)
            for k in range(1, int((RAMP_DROP0 + RAMP_DROP) * S) + 1):
                mk = np.roll(m * (drop >= k), k, 0)
                mk[:k] = 0
                new = mk > wall
                grad = np.where(new, k / np.maximum(np.roll(drop, k, 0), 1), grad)
                wall = np.maximum(wall, mk)
            wall = wall * (1 - m)
            wcol = np.asarray(col, np.float32) * (0.62 - 0.3 * grad)[..., None]
            ov.put(b, wall, wcol, ht=np.full_like(d, 2 * S), spec=0.5, shin=0.6, alpha=0.9)
            # rim line where the wall meets the playfield
            foot = np.clip(wall - np.roll(wall, -int(0.8 * S), 0), 0, 1)
            ov.put(b, foot, (20, 12, 26), alpha=0.6)
            # stilts along both edges
            Es = ramp_elev(s, rp["apex_s"], rp["down_s"], s[-1])
            acc = 0.0
            for i in range(1, len(plastic)):
                acc += math.dist(plastic[i - 1], plastic[i])
                if acc >= 34 and Es[i] > 0.25:
                    acc = 0.0
                    for o in (-hw + 0.8, hw - 0.8):
                        ex, ey = offset_line(plastic[max(0, i - 1):i + 2], o)[1 if i > 0 else 0]
                        ramp_support(ov, ex, ey, RAMP_DROP0 + RAMP_DROP * float(Es[i]))
            # floor: tinted translucent plastic with cross ties (coaster track)
            ties = (np.abs((T % 7.0) - 3.5) < 0.7).astype(np.float32) * (across < 0.75)
            base = np.asarray(col, np.float32) * (0.75 + 0.25 * (1 - across))[..., None]
            ov.put(b, m, base, ht=np.full_like(d, 4 * S), spec=0.9, shin=0.8, alpha=0.70)
            # ramp gloss: darker curved floor towards the walls (2.5D trough) + a long specular streak
            ov.mul(b, m * np.clip((across - 0.55) / 0.45, 0, 1), 0.62)
            ov.add(b, m * np.exp(-((across - 0.30) / 0.09) ** 2) * (0.6 + 0.4 * np.sin(T * 0.11) ** 2), (110, 105, 100))
            # entrance chevrons printed on the plastic (point up the ramp)
            chev = (np.abs(((T - np.abs(across) * 4.0) % 9.0) - 4.5) < 0.9) * (T < 42) * (across < 0.6)
            ov.put(b, chev * m, (255, 250, 220), ht=np.full_like(d, 4.4 * S), alpha=0.85)
            if rp.get("deco", "ties" if ri == 0 else "rails") == "ties":
                ov.put(b, ties * m, (250, 220, 200), ht=np.full_like(d, 4.6 * S), alpha=0.9)
            else:   # ghost train: glowing green rails on a dark track
                ov.put(b, (np.abs(across - 0.45) < 0.08) * m, getattr(G, "RAIL_RGB", (160, 255, 170)), alpha=0.9)
            # walls = chrome edges
            for side in (-1, 1):
                edge = ov.cov(np.abs(d - (hw - 0.8)), 1.0)
                ov.put(b, edge, (235, 235, 245), ht=np.full_like(d, 7 * S), spec=1.0, shin=0.9)
            ov.finish(ao=False, shadow=False)
            # entrance flap: polished lip at the mouth
            mx = rp["mouth"]
            ov.tube([(mx[0], mx[1]), (mx[2], mx[3])], 1.6, "chrome", (240, 240, 250), height=3 * S, z=2)
        else:
            wire = path
        # wireform: two (three for helter) chrome wires + rings
        offs = (-5.0, 5.0) if rp["kind"] == "plastic" else (-6.0, 0.0, 6.0)
        if rp["kind"] == "plastic":
            offs = (-5.0, 5.0)
        kind = "gold" if rp["color"] == "gold" else "chrome"
        Ew = ramp_elev(s, rp["apex_s"], rp["down_s"], s[-1])[len(path) - len(wire):]
        acc = 0.0
        for i in range(1, len(wire)):
            acc += math.dist(wire[i - 1], wire[i])
            if acc >= 30 and Ew[i] > 0.2:
                acc = 0.0
                ramp_support(ov, wire[i][0], wire[i][1], 1.0 + 7.0 * float(Ew[i]), kind)
        for o in offs:
            pts = offset_line(wire, o)
            ov.tube(pts, 1.1, kind, (240, 240, 250), height=2.2 * S, z=8)
        acc = 0.0
        for a, c in zip(wire, wire[1:]):
            acc += math.dist(a, c)
            if acc >= 14:
                acc = 0.0
                nx, ny = c[1] - a[1], a[0] - c[0]
                L = math.hypot(nx, ny) or 1
                nx, ny = nx / L, ny / L
                w2 = max(abs(o) for o in offs) + 1.5
                ov.tube([(c[0] - nx * w2, c[1] - ny * w2), (c[0] + nx * w2, c[1] + ny * w2)], 0.7, kind,
                        (220, 220, 230), height=1.4 * S, z=8)
    # cut the ramp ends flush with their mouths
    for rp in G.RAMPS:
        if rp.get("vuk"):
            continue
        mx = rp["mouth"]
        cxm, cym = (mx[0] + mx[2]) / 2, (mx[1] + mx[3]) / 2
        nx_, ny_ = rp["in"]
        b = ov.box(cxm - 26, cym - 26, cxm + 26, cym + 26, 0)
        xx, yy = ov.grid(b)
        side = (xx - cxm) * nx_ + (yy - cym) * ny_
        keep = np.clip(side * S + 0.5 + 1.2 * S, 0, 1)
        sl = (slice(b[0], b[1]), slice(b[2], b[3]))
        ov.a[sl] *= keep
    toys_art.overlay(ov, sys.modules[__name__])
    if THEME:
        THEME.overlay(ov, sys.modules[__name__])
        return ov
    # helter-skelter tower roof (tallest object on the table)
    cx, cy = G.TOWER
    b, d, ox, oy = ov.disc_field(cx, cy, 20)
    ang = np.arctan2(oy, ox)
    stripe = ((ang / (2 * np.pi) * 8) % 1) < 0.5
    t = np.clip(d / 18, 0, 1)
    nx, ny = ox / np.maximum(d, 1e-6) * 0.7, oy / np.maximum(d, 1e-6) * 0.7
    nz = np.full_like(d, 0.7)
    base = np.where(stripe[..., None], np.array([230, 40, 60], np.float32), np.array([250, 240, 220], np.float32))
    col = shade(nx, ny, nz, 1.0, "plastic") if False else None
    lit = np.clip(nx * -0.42 + ny * -0.62 + 0.66 * nz, 0, 1)[..., None] + 0.3
    ov.put(b, ov.cov(d, 18), base * np.clip(lit, 0, 1.2), ht=(1 - t) * 14 * S + 10 * S, spec=0.8, shin=0.7)
    ov.dome(cx, cy, 3.2, "gold", (255, 210, 90), height=3 * S, z=24)
    # flag
    bb, mm = ov.poly_mask([(cx, cy - 1), (cx + 9, cy - 4), (cx, cy - 7)])
    ov.put(bb, mm, (60, 220, 255), ht=np.full_like(mm, 26 * S))
    return ov


def offset_line(pts, o):
    out = []
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]
        c = pts[min(len(pts) - 1, i + 1)]
        dx, dy = c[0] - a[0], c[1] - a[1]
        L = math.hypot(dx, dy) or 1
        out.append((p[0] - dy / L * o, p[1] + dx / L * o))
    return out


# ======================================================================= SPRITES
def sprite_flipper(length, r0, r1, name):
    pad = 2
    w, h = length + r0 + r1 + pad * 2, r0 * 2 + pad * 2
    sp = Img(w, h, S, alpha=True)
    piv = (r0 + pad, h / 2)
    tip = (piv[0] + length, h / 2)
    b = sp.box(0, 0, w, h, 0)
    xx, yy = sp.grid(b)
    t = np.clip((xx - piv[0]) / length, 0, 1)
    rad = r0 + (r1 - r0) * t
    d = np.abs(yy - h / 2)
    dc0 = np.hypot(xx - piv[0], yy - piv[1])
    dc1 = np.hypot(xx - tip[0], yy - tip[1])
    inside_body = (xx >= piv[0]) & (xx <= tip[0])
    dist = np.where(inside_body, d - rad, np.minimum(dc0 - r0, dc1 - r1))
    dist = np.minimum(dist, np.minimum(dc0 - r0, dc1 - r1))
    m = sp.cov(dist, 0)
    rub = (dist > -1.3)
    core = np.clip(-dist / 2.5, 0, 1)
    nz = np.sqrt(np.clip(core, 0, 1))
    gx, gy = np.gradient(-dist)
    col_body = np.array([246, 230, 184], np.float32)    # cream
    col_rub = np.array([235, 30, 40], np.float32)
    base = np.where(rub[..., None], col_rub, col_body)
    lit = np.clip(0.55 + 0.45 * core - 0.18 * (yy - h / 2) / max(r0, 1), 0.4, 1.08)   # top-left lit, 4 tones
    lit = np.round(lit * 4) / 4
    sp.put(b, m, base * lit[..., None], ht=core * 4 * S, spec=0.7, shin=0.6)
    sp.put(b, sp.cov(np.abs(dist + 0.15), 0.25), (40, 14, 20))                 # 1 px outline
    sp.dome(piv[0], piv[1], 2.8, "chrome", (240, 240, 250), height=2 * S, z=4)
    # print a small star on the flipper
    bb, mm = sp.text_mask("COPPER", r0 * 0.9, piv[0] + length * 0.45, h / 2, wide=True)
    if bb is not None:
        sp.put(bb, mm, (150, 40, 40))
    sp.finish(ao=False, shadow=False)
    sp.save(os.path.join(HD, name + ".png"), alpha=True, normal_path=os.path.join(HD, name + "_n.png"),
            normal_strength=0.8)
    return {"pivot_px": [piv[0] * S, piv[1] * S]}


def sprite_bumper(r, name):
    R = r + 3
    BAND = 4.0                                   # visible cylinder side (units)
    sp = Img(R * 2, R * 2 + BAND * 2, S, alpha=True)
    c = R
    cy = R + BAND                                # cap centre = image centre = physics centre
    # rubber skirt at the foot, then the body side band (cylinder, lit from the left)
    sp.tube([(c, cy + BAND)], r + 1.2, "rubber", (235, 235, 235), height=3 * S)
    b, d, ox, oy = sp.disc_field(c, cy + BAND / 2, r + BAND)
    xx, yy = sp.grid(b)
    body = sp.cov(np.where(np.abs(yy - (cy + BAND / 2)) <= BAND / 2, np.abs(xx - c), np.minimum(
        np.hypot(xx - c, yy - cy), np.hypot(xx - c, yy - cy - BAND))), r - 0.2)
    u = np.clip((xx - c) / (r - 0.2), -1, 1)
    lit = np.clip(0.55 - 0.45 * u + 0.35 * np.sqrt(np.clip(1 - u * u, 0, 1)), 0.15, 1.1)
    stripe = (((np.arctan2(np.sqrt(np.clip(1 - u * u, 0, 1)), u) / np.pi * 6) % 1) < 0.5)
    _bc = getattr(G, "BUMPER_COLORS", ((210, 40, 120), (60, 30, 140), (255, 70, 150), (255, 230, 90)))
    bcol = np.where(stripe[..., None], np.array(_bc[0], np.float32), np.array(_bc[1], np.float32))
    sp.put(b, body, bcol * lit[..., None], ht=np.full_like(d, 3.5 * S), spec=0.7, shin=0.6)
    c, cyc = c, cy
    sp.tube([(c, cyc)], r - 0.2, "chrome", (210, 210, 222), height=1 * S, z=3.5)   # top lip
    sp.dome(c, cy, r - 0.5, "chrome", (225, 225, 235), height=4 * S, z=1, flat=0.6)   # metal ring
    b, d, ox, oy = sp.disc_field(c, cy, r - 2.2)
    cap = sp.cov(d, r - 2.5)
    ang = np.arctan2(oy, ox)
    star = np.abs(((ang / (2 * np.pi) * 10) % 1) - 0.5) < 0.25
    t = np.clip(d / (r - 2.5), 0, 1)
    col = np.where((star & (t > 0.35))[..., None], np.array(_bc[2], np.float32), np.array(_bc[3], np.float32))
    hl = np.clip(1 - np.hypot(ox + r * 0.3, oy + r * 0.35) / (r * 0.45), 0, 1) ** 2
    sp.put(b, cap, col * (0.75 + 0.25 * (1 - t))[..., None] + hl[..., None] * 140,
           ht=(6 + 2.5 * np.sqrt(np.clip(1 - t * t, 0, 1))) * S, spec=0.95, shin=0.85)
    sp.save(os.path.join(HD, name + ".png"), alpha=True, normal_path=os.path.join(HD, name + "_n.png"),
            normal_strength=0.7)


def sprite_drop(name):
    w, h = 18, 6
    sp = Img(w, h, S, alpha=True)
    b = sp.box(0, 0, w, h, 0)
    xx, yy = sp.grid(b)
    ex = np.minimum(np.minimum(xx - 0.5, w - 0.5 - xx), np.minimum(yy - 0.5, h - 0.5 - yy))
    m = sp.cov(-ex, 0)
    bev = np.clip(ex / 1.2, 0, 1)
    sp.put(b, m, np.array([250, 250, 245], np.float32) * (0.6 + 0.4 * bev[..., None]), ht=bev * 3 * S, spec=0.7)
    sp.save(os.path.join(HD, name + ".png"), alpha=True, normal_path=os.path.join(HD, name + "_n.png"))


def sprite_spinner(name):
    w, h = 26, 6
    sp = Img(w, h, S, alpha=True)
    b = sp.box(0, 0, w, h, 0)
    xx, yy = sp.grid(b)
    ex = np.minimum(np.minimum(xx - 0.5, w - 0.5 - xx), np.minimum(yy - 0.5, h - 0.5 - yy))
    m = sp.cov(-ex, 0)
    brushed = smooth_noise(b[3] - b[2], b[1] - b[0], 2, 40)
    base = np.stack([200 + 40 * brushed] * 3, -1) * np.array([1.0, 0.95, 0.8])
    sp.put(b, m, base, ht=np.clip(ex, 0, 1) * 2 * S, spec=1.0, shin=0.9)
    bb, mm = sp.text_mask("SPIN", 4.2, w / 2, h / 2, wide=True)
    sp.put(bb, mm, (150, 20, 60))
    sp.save(os.path.join(HD, name + ".png"), alpha=True, normal_path=os.path.join(HD, name + "_n.png"))


def sprite_ball():
    """ball base + environment map for the reflection shader."""
    n = 128
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    ox, oy = (xx + 0.5 - n / 2) / (n / 2), (yy + 0.5 - n / 2) / (n / 2)
    d = np.hypot(ox, oy)
    a = np.clip((1 - d) * n / 2 + 0.5, 0, 1)
    Image.fromarray(np.dstack([np.full((n, n, 3), 255, np.uint8), (a * 255).astype(np.uint8)]), "RGBA").save(
        os.path.join(HD, "ball_mask.png"))
    # equirect-ish environment: dark room, warm cabinet light strips, playfield colours below
    ew, eh = 256, 128
    yy, xx = np.mgrid[0:eh, 0:ew].astype(np.float32)
    v = yy / eh
    u = xx / ew
    col = np.zeros((eh, ew, 3), np.float32)
    sky = np.array([30, 24, 60], np.float32)
    floor = np.array([90, 30, 110], np.float32)
    t = np.clip((v - 0.45) * 4, 0, 1)[..., None]
    col[:] = sky * (1 - t) + floor * t
    for cu, cv, rr, c in ((0.25, 0.25, 0.08, (255, 240, 220)), (0.62, 0.2, 0.05, (255, 200, 150)),
                          (0.8, 0.32, 0.04, (150, 220, 255)), (0.45, 0.7, 0.10, (255, 80, 150)),
                          (0.1, 0.75, 0.08, (255, 200, 60)), (0.9, 0.7, 0.1, (60, 200, 255))):
        dd = np.hypot((u - cu) * 2, v - cv)
        col += np.asarray(c, np.float32) * np.clip(1 - dd / rr, 0, 1)[..., None] ** 1.5
    strip = (np.abs(v - 0.12) < 0.02).astype(np.float32)[..., None]
    col += strip * 200
    noise = smooth_noise(ew, eh, 8, 50)[..., None]
    col *= 0.85 + 0.3 * noise
    Image.fromarray(np.clip(col, 0, 255).astype(np.uint8), "RGB").save(os.path.join(HD, "ball_env.png"))


def sprite_glow():
    n = 128
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    d = np.hypot(xx + 0.5 - n / 2, yy + 0.5 - n / 2) / (n / 2)
    g = np.clip(1 - d, 0, 1) ** 2.2
    Image.fromarray(np.dstack([np.full((n, n, 3), 255, np.uint8), (g * 255).astype(np.uint8)]), "RGBA").save(
        os.path.join(HD, "glow.png"))
    # soft light cookie for PointLight2D
    g2 = np.clip(1 - d, 0, 1) ** 1.6
    Image.fromarray((np.dstack([g2, g2, g2, np.ones_like(g2)]) * 255).astype(np.uint8), "RGBA").save(
        os.path.join(HD, "light.png"))


def lamp_masks():
    """white lit-insert shapes (Godot tints + HDR boosts them -> bloom)."""
    n = 64
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    ox, oy = (xx + 0.5 - n / 2) / (n / 2), (yy + 0.5 - n / 2) / (n / 2)
    d = np.hypot(ox, oy)
    core = np.clip((0.62 - d) * 20, 0, 1)
    halo = np.clip(1 - d, 0, 1) ** 2 * 0.55
    a = np.maximum(core, halo)
    hot = np.clip(1 - d / 0.5, 0, 1)
    rgb = np.stack([200 + 55 * hot] * 3, -1)
    Image.fromarray(np.dstack([rgb, a * 255]).astype(np.uint8), "RGBA").save(os.path.join(HD, "lamp_round.png"))
    for kind in ("arrow", "star"):
        sz = 128
        im = Image.new("L", (sz, sz), 0)
        dr = ImageDraw.Draw(im)
        c = sz / 2
        s = sz * 0.32
        if kind == "arrow":   # pointing +x
            pts = [(c + s * 1.3, c), (c, c + s * 0.9), (c, c + s * 0.35), (c - s, c + s * 0.35), (c - s, c - s * 0.35),
                   (c, c - s * 0.35), (c, c - s * 0.9)]
        else:
            pts = []
            for i in range(10):
                rr = s * 1.25 if i % 2 == 0 else s * 0.56
                a0 = -math.pi / 2 + i * math.pi / 5
                pts.append((c + math.cos(a0) * rr, c + math.sin(a0) * rr))
        dr.polygon(pts, fill=255)
        m = np.asarray(im, np.float32) / 255
        halo = blur(m, 9) * 0.8
        a = np.maximum(m, halo)
        Image.fromarray(np.dstack([np.full((sz, sz, 3), 255, np.float32), a * 255]).astype(np.uint8), "RGBA").save(
            os.path.join(HD, "lamp_%s.png" % kind))


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(HD, exist_ok=True)
    os.makedirs(PX, exist_ok=True)
    G.export(OUT, S)
    ov = paint_overlay()
    pf = paint_playfield()
    pf.finish(ao=True, shadow=True)
    gloss_pass(pf)
    # overlay casts a soft shadow onto the playfield
    # 2.5D: a tight contact shadow + a long soft height shadow (light from the upper left)
    near = blur(np.roll(np.roll(ov.a, int(4 * S), 0), int(3 * S), 1), 1.5 * S)
    far = blur(np.roll(np.roll(ov.a, int(11 * S), 0), int(8 * S), 1), 4.5 * S)
    sh = np.clip(near * 0.42 + far * 0.38, 0, 0.72)
    pf.rgb *= (1 - sh)[..., None]
    pf.save(os.path.join(HD, "playfield.png"), normal_path=os.path.join(HD, "playfield_n.png"),
            spec_path=os.path.join(HD, "playfield_s.png"), normal_strength=0.9)
    ov.save(os.path.join(HD, "ramps.png"), alpha=True, normal_path=os.path.join(HD, "ramps_n.png"),
            spec_path=os.path.join(HD, "ramps_s.png"), normal_strength=0.9)
    for f in G.FLIPPERS[:1]:
        sprite_flipper(f["len"], f["r0"], f["r1"], "flipper")
    sprite_flipper(G.FLIPPERS[2]["len"], G.FLIPPERS[2]["r0"], G.FLIPPERS[2]["r1"], "flipper_small")
    sprite_bumper(13.0, "bumper")
    sprite_drop("drop")
    sprite_spinner("spinner")
    toys_art.sprites(sys.modules[__name__])
    sprite_ball()
    sprite_glow()
    lamp_masks()
    build_pixel()
    print("built", pf.w, "x", pf.h)


# ======================================================================= PIXEL STYLE
def _quant(im, colors, alpha):
    """Amiga-ish: 1 px per logical unit, OCS 12-bit palette (4 bits/channel), N colours, no dither."""
    rgb = im.convert("RGB")
    a = np.asarray(im.convert("RGBA"))[..., 3] if alpha else None
    q = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.asarray(q.getpalette()[:colors * 3], np.int32).reshape(-1, 3)
    pal = (np.round(pal / 17.0) * 17).clip(0, 255)          # 12-bit OCS colour grid
    out = pal[np.asarray(q)].astype(np.uint8)
    if alpha:
        a = np.where(a > 110, 255, 0).astype(np.uint8)         # 1-bit transparency like bitplane sprites
        return Image.fromarray(np.dstack([out, a]), "RGBA")
    return Image.fromarray(out, "RGB")


def build_pixel():
    """Downsample the HD paint to 1 px/unit and posterise to a shared 32-colour palette (playfield)
    and 16-colour sprites; nearest-neighbour rendered in Godot. Lighting is baked (no 2D lights)."""
    pf = Image.open(os.path.join(HD, "playfield.png")).convert("RGB")
    # bake a fixed 'lamp light' look into the pixel playfield: a bit brighter + more contrast
    small = pf.resize((W, H), Image.BOX)
    arr = np.asarray(small, np.float32)
    arr = np.clip((arr - 4) * 1.06, 0, 255)
    _quant(Image.fromarray(arr.astype(np.uint8)), 64, False).save(os.path.join(PX, "playfield.png"))
    ov = Image.open(os.path.join(HD, "ramps.png")).convert("RGBA").resize((W, H), Image.BOX)
    _quant(ov, 32, True).save(os.path.join(PX, "ramps.png"))
    for name in ["flipper", "flipper_small", "bumper", "drop", "spinner", "ball_mask"] + toys_art.sprite_names(G):
        im = Image.open(os.path.join(HD, name + ".png")).convert("RGBA")
        k = S if name != "ball_mask" else 8      # ball mask is 128px -> 16 px (ball d=15)
        im = im.resize((max(1, im.width // k), max(1, im.height // k)), Image.BOX)
        _quant(im, 16, True).save(os.path.join(PX, name + ".png"))
    pixel_ball(os.path.join(PX, "ball.png"))


def pixel_ball(path, n=15):
    """Pixel-style chrome ball: the HD mirror-sphere model (dark cabinet above the reflection
    horizon, mirrored playfield colour below, bright horizon line, fixed key highlight, Fresnel
    darkening) reduced to 5 steel tones + 1 reflected-playfield tone with 4x4 Bayer dithering."""
    tones = np.array([[40, 42, 58], [108, 112, 130], [164, 168, 186], [206, 210, 222], [248, 249, 255]], np.uint8)
    accent = np.array(getattr(G, "BALL_ACCENT", (176, 124, 170)), np.uint8)          # magenta playfield seen in the lower rim
    bayer = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) + 0.5) / 16.0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    px, py = (xx + 0.5 - n / 2) / (n / 2), (yy + 0.5 - n / 2) / (n / 2)
    r = np.hypot(px, py)
    inside = r <= 1.0
    nz = np.sqrt(np.clip(1 - px * px - py * py, 0, 1))
    rfx, rfy, rfz = 2 * nz * px, 2 * nz * py, 2 * nz * nz - 1
    key = np.array([-0.40, -0.60, 0.69]); key /= np.linalg.norm(key)
    kd = np.clip(rfx * key[0] + rfy * key[1] + rfz * key[2], 0, 1)
    floor = rfz < -0.02
    lum = np.where(floor, 0.56 - 0.05 * py, 0.66 + 0.26 * np.clip(-(px + py) / 1.4, 0, 1) - 0.10 * np.clip(px + py, 0, 1))
    lum = lum + 0.30 * np.exp(-(rfz / 0.12) ** 2)                 # horizon line
    lum = lum + 0.9 * kd ** 60                                      # key highlight bloom
    lum = lum * np.where((r > 0.78) & (py > 0.3), 1 - 0.55 * (r - 0.78) / 0.22, 1.0)  # dark only at the bottom  # Fresnel darkening
    lum = np.clip(lum, 0, 1)
    th = bayer[(yy.astype(int) % 4), (xx.astype(int) % 4)]
    idx = np.clip(np.floor(lum * 4 + th - 0.5 + 0.5), 0, 4).astype(int)
    rgb = tones[idx].copy()
    # reflected playfield colour on the mid tones of the lower rim (dithered)
    acc = floor & (idx == 2) & (th > 0.55) & (py > 0.2)
    rgb[acc] = accent
    # hard specular: a 2x2 glint fixed to the key light, plus one dim fill pixel
    hx, hy = int(round(n / 2 + key[0] * 0.5 * n / 2 - 0.5)), int(round(n / 2 + key[1] * 0.5 * n / 2 - 0.5))
    rgb[hy:hy + 2, hx:hx + 2] = tones[4]
    rgb[int(n * 0.68), int(n * 0.70)] = tones[3]
    rgb[(r > 0.93) & inside & (py > 0.2)] = tones[0]                # bottom outline       # dark outline keeps it round
    a = inside.astype(np.uint8) * 255
    Image.fromarray(np.dstack([rgb, a]), "RGBA").save(path)


if __name__ == "__main__":
    main()
