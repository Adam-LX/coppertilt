"""Painted-illustration toolkit (m10): full-frame procedural painting helpers for the theme backdrops.

All functions work on an mf_paint.Img (pf.rgb float 0..255, pf.S px per table unit) and use table
units for coordinates. Everything is procedural and original (no external art).
  fbm / clouds / nebula   - layered value-noise clouds with light-side shading
  beams / glow / bokeh    - additive light (searchlights, haze pools, out-of-focus lamps)
  silhouette              - filled shape with a rim light on its lit edge (depth cue)
  relight                 - global chiaroscuro: ambient falloff + coloured light pools
  grain                   - print/paper texture so flat fills read as painted
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw

from mf_paint import blur, smooth_noise


def full(pf):
    """full-frame unit grids (cached on the image)."""
    g = getattr(pf, "_ill_grid", None)
    if g is None:
        xs = (np.arange(pf.w, dtype=np.float32) + 0.5) / pf.S
        ys = (np.arange(pf.h, dtype=np.float32) + 0.5) / pf.S
        g = np.meshgrid(xs, ys)
        pf._ill_grid = g
    return g


def fbm(w, h, cell, octaves, seed, gain=0.5):
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for i in range(octaves):
        c = max(2, int(cell / (2 ** i)))
        out += smooth_noise(w, h, c, seed + 31 * i) * amp
        tot += amp
        amp *= gain
    return out / tot


def band(yy, y0, y1, soft):
    """1 inside [y0,y1], soft ramps outside (units)."""
    return np.clip((yy - (y0 - soft)) / soft, 0, 1) * np.clip(((y1 + soft) - yy) / soft, 0, 1)


def poly(pf, pts, ss=2, blur_u=0.0):
    im = Image.new("L", (pf.w * ss // 2, pf.h * ss // 2), 0) if ss == 1 else Image.new("L", (pf.w, pf.h), 0)
    k = pf.S if ss != 1 else pf.S / 2
    ImageDraw.Draw(im).polygon([(x * k, y * k) for x, y in pts], fill=255)
    if ss == 1:
        im = im.resize((pf.w, pf.h), Image.BILINEAR)
    m = np.asarray(im, np.float32) / 255.0
    return blur(m, blur_u * pf.S) if blur_u else m


def draw_mask(pf, fn, blur_u=0.0):
    """fn(draw, k) with k = px per unit; returns a full-frame mask."""
    im = Image.new("L", (pf.w, pf.h), 0)
    fn(ImageDraw.Draw(im), pf.S)
    m = np.asarray(im, np.float32) / 255.0
    return blur(m, blur_u * pf.S) if blur_u else m


def put(pf, m, col, alpha=1.0):
    m = np.clip(m * alpha, 0, 1)[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + np.asarray(col, np.float32) * m


def add(pf, m, col):
    pf.rgb += np.clip(m, 0, None)[..., None] * np.asarray(col, np.float32)


def screen(pf, m, col):
    """screen blend: brightens without blowing out."""
    c = np.clip(m, 0, 1)[..., None] * np.asarray(col, np.float32) / 255.0
    pf.rgb[:] = 255.0 - (255.0 - pf.rgb) * (1 - c)


def mul(pf, f):
    pf.rgb *= np.asarray(f, np.float32)[..., None] if np.ndim(f) == 2 else np.asarray(f, np.float32)


def clouds(pf, y0, y1, lit, dark, cover=0.5, cell=90, seed=1, alpha=0.6, light=(-0.6, -0.8), soft=30):
    """volumetric-looking cloud banks: fbm density, shaded by its gradient toward the light."""
    xx, yy = full(pf)
    n = fbm(pf.w, pf.h, cell * pf.S / 4, 5, seed)
    dens = np.clip((n - (1 - cover)) / 0.22, 0, 1) * band(yy, y0, y1, soft)
    gy, gx = np.gradient(blur(n, 2 * pf.S))
    sh = np.clip(0.5 - (gx * light[0] + gy * light[1]) * pf.S * 60, 0, 1)
    col = np.asarray(dark, np.float32) * (1 - sh[..., None]) + np.asarray(lit, np.float32) * sh[..., None]
    m = (dens * alpha)[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + col * m
    return dens


def nebula(pf, y0, y1, cols, seed=5, k=0.55, cell=120):
    """additive coloured gas: each colour gets its own warped fbm, filaments from ridged noise."""
    xx, yy = full(pf)
    w = band(yy, y0, y1, 40)
    for i, c in enumerate(cols):
        n = fbm(pf.w, pf.h, cell * pf.S / 4, 5, seed + 97 * i)
        ridge = 1 - np.abs(n * 2 - 1)
        m = np.clip((n - 0.45) / 0.35, 0, 1) ** 1.5 * 0.7 + ridge ** 6 * 0.5
        screen(pf, m * w * k, c)


def beams(pf, x, y, ang_deg, spread_deg, length, col, k=0.35, soft=0.35):
    """a searchlight cone from (x,y); ang 0 = up, clockwise positive."""
    xx, yy = full(pf)
    dx, dy = xx - x, yy - y
    a = math.radians(ang_deg)
    ux, uy = math.sin(a), -math.cos(a)
    along = dx * ux + dy * uy
    across = dx * uy - dy * ux
    half = np.maximum(along, 0) * math.tan(math.radians(spread_deg / 2)) + 0.6
    t = np.clip(1 - np.abs(across) / half, 0, 1)
    edge = t ** (1 + soft * 4)
    fall = np.clip(1 - along / length, 0, 1) ** 1.4 * (along > 0)
    screen(pf, edge * fall * k, col)


def glow(pf, cx, cy, rx, ry, col, k=0.5, p=2.0):
    xx, yy = full(pf)
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    screen(pf, np.clip(1 - d, 0, 1) ** p * k, col)


def bokeh(pf, x0, y0, x1, y1, n, rmin, rmax, cols, k=0.35, seed=3):
    r = random.Random(seed)
    for _ in range(n):
        x, y, rad = r.uniform(x0, x1), r.uniform(y0, y1), r.uniform(rmin, rmax)
        b, d, _, _ = pf.disc_field(x, y, rad + 1)
        if b is None:
            continue
        disc = np.clip((rad - d) * pf.S / 2 + 0.5, 0, 1)
        rim = np.clip(1 - np.abs(d - rad * 0.85) / (rad * 0.25), 0, 1)
        m = (disc * 0.55 + rim * 0.45) * k * r.uniform(0.5, 1.0)
        c = np.asarray(r.choice(cols), np.float32)
        sl = (slice(b[0], b[1]), slice(b[2], b[3]))
        pf.rgb[sl] = 255 - (255 - pf.rgb[sl]) * (1 - np.clip(m, 0, 1)[..., None] * c / 255)


def silhouette(pf, m, col, alpha=1.0, rim=None, rim_off=(-0.8, -0.8), rim_k=0.9, tex=None):
    """fill mask m with col; light the edge facing the light (rim_off points toward the light)."""
    c = np.asarray(col, np.float32)
    if tex is not None:
        c = c * tex[..., None]
    mm = np.clip(m * alpha, 0, 1)[..., None]
    pf.rgb[:] = pf.rgb * (1 - mm) + c * mm
    if rim is not None:
        dx, dy = int(round(rim_off[0] * pf.S)), int(round(rim_off[1] * pf.S))
        sh = np.roll(np.roll(m, -dy, 0), -dx, 1)
        e = np.clip(m - sh, 0, 1) * alpha * rim_k
        screen(pf, blur(e, 0.3 * pf.S) * 1.2, rim)


def string_lights(pf, pts, sag, n, cols, r=1.1, k=1.0):
    """festoon bulbs on a sagging wire between consecutive points."""
    def f(d, s):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            q = []
            for i in range(25):
                t = i / 24
                q.append(((x0 + (x1 - x0) * t) * s, (y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)) * s))
            d.line(q, fill=255, width=max(1, int(0.35 * s)))
    put(pf, draw_mask(pf, f), (20, 14, 24), 0.8)
    j = 0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        for i in range(1, n):
            t = i / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)
            c = cols[j % len(cols)]
            j += 1
            b, d, _, _ = pf.disc_field(x, y, r * 5)
            if b is None:
                continue
            sl = (slice(b[0], b[1]), slice(b[2], b[3]))
            g = (np.clip(1 - d / (r * 5), 0, 1) ** 2 * 0.6 * k)[..., None] * np.asarray(c, np.float32) / 255
            pf.rgb[sl] = 255 - (255 - pf.rgb[sl]) * (1 - g)
            core = pf.cov(d, r)[..., None]
            pf.rgb[sl] = pf.rgb[sl] * (1 - core) + (np.asarray(c, np.float32) * 0.4 + 153) * core


def firework(pf, cx, cy, r, col, seed=1, n=40, k=0.9):
    """a burst: drooping radial trails with bright heads + a soft flash."""
    rr = random.Random(seed)
    glow(pf, cx, cy, r * 1.3, r * 1.3, col, 0.25, 2.5)

    def f(d, s):
        for i in range(n):
            a = 2 * math.pi * i / n + rr.uniform(-0.05, 0.05)
            L = r * rr.uniform(0.7, 1.0)
            q = []
            for j in range(9):
                t = j / 8
                q.append(((cx + math.cos(a) * L * t) * s, (cy + math.sin(a) * L * t + 0.18 * r * t * t) * s))
            d.line(q[2:], fill=180, width=max(1, int(0.45 * s)))
            hx, hy = q[-1]
            d.ellipse([hx - 0.9 * s, hy - 0.9 * s, hx + 0.9 * s, hy + 0.9 * s], fill=255)
    m = draw_mask(pf, f)
    screen(pf, blur(m, 1.6 * pf.S) * 1.6 * k, col)
    screen(pf, blur(m, 0.5 * pf.S) * 1.2 * k, col)
    screen(pf, m * k, tuple(min(255, c * 0.5 + 140) for c in col))


def relight(pf, lights, ambient=0.72, vignette=0.22, cx=160, cy=330):
    """chiaroscuro: darken away from the light, coloured pools where the scene is lit.
    lights: [(x, y, rx, ry, (r,g,b) tint, strength)]"""
    xx, yy = full(pf)
    vg = 1 - vignette * np.clip(np.hypot((xx - cx) / 190, (yy - cy) / 360), 0, 1) ** 2
    f = np.full(xx.shape + (3,), ambient, np.float32)
    for x, y, rx, ry, tint, s in lights:
        d = np.clip(1 - ((xx - x) / rx) ** 2 - ((yy - y) / ry) ** 2, 0, 1) ** 1.6
        f += d[..., None] * s * np.asarray(tint, np.float32) / 255.0
    pf.rgb *= np.clip(f, 0, 1.45) * vg[..., None]


def grain(pf, k=0.06, seed=9):
    """printed-art texture: fine grain + soft mottling + faint fibre streaks."""
    xx, yy = full(pf)
    g = np.random.default_rng(seed).random((pf.h, pf.w)).astype(np.float32)
    g = blur(g, 0.6) - 0.5
    mott = smooth_noise(pf.w, pf.h, int(14 * pf.S), seed + 1) - 0.5
    fib = np.sin(yy * 3.1 + 4 * smooth_noise(pf.w, pf.h, int(30 * pf.S), seed + 2)) * 0.5
    f = 1 + k * (g * 1.2 + mott * 0.8 + fib * 0.25)
    pf.rgb *= f[..., None]


def wood(w, h, S, seed=21, along_y=True):
    """procedural plank wood: warped annual rings + pores + plank seams; returns rgb (h,w,3)."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    u, v = (xs, ys) if along_y else (ys, xs)
    warp = smooth_noise(w, h, int(40 * S), seed) * 2 - 1
    rings = np.sin((u / S) * 0.8 + warp * 9 + (v / S) * 0.02 + smooth_noise(w, h, int(9 * S), seed + 1) * 3.0)
    rings = (rings * 0.5 + 0.5) ** 2.2
    pores = np.random.default_rng(seed).random((h, w)).astype(np.float32)
    pores = blur(pores, 0.5) * 0 + (pores > 0.985) * 0.6
    streak = smooth_noise(w, h, max(2, int(1.5 * S)), seed + 2)
    tone = 0.62 + 0.38 * rings - 0.12 * pores + 0.08 * (streak - 0.5)
    base = np.asarray((122, 64, 30), np.float32)
    dark = np.asarray((54, 24, 12), np.float32)
    col = dark + (base - dark) * tone[..., None]
    return col
