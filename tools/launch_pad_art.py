"""Launch Pad - painted illustration (m10): a cosmodrome at night, seen from the launch apron.

backdrop(): the Milky Way and aurora curtains over deep space, a giant ringed planet rising behind
the launch complex at the horizon (gantry towers, fuel spheres, a second rocket venting steam,
searchlights), then a floodlit concrete apron in perspective down to the flippers.
light():    steam round the main rocket's pad, chiaroscuro relight, print grain.
"""
import math
import random


def _milky_way(I, pf):
    np = I.np
    xx, yy = I.full(pf)
    d = (xx * 0.52 + yy * 0.85) - 150.0          # diagonal band from the left mid to the top right
    core = np.exp(-(d / 34.0) ** 2)
    n = I.fbm(pf.w, pf.h, 40 * pf.S / 4, 5, 41)
    I.screen(pf, core * (0.35 + 0.65 * n) * 0.55 * I.band(yy, 0, 240, 40), (210, 200, 255))
    dust = (1 - np.abs(I.fbm(pf.w, pf.h, 22 * pf.S / 4, 4, 43) * 2 - 1)) ** 5
    I.mul(pf, 1 - dust * np.exp(-(d / 14.0) ** 2) * 0.45 * I.band(yy, 0, 240, 40))
    # star dust inside the band
    rng = np.random.default_rng(44)
    sp = (rng.random((pf.h, pf.w)) > 0.9975).astype(np.float32) * core * I.band(yy, 0, 240, 30)
    I.add(pf, I.blur(sp, 0.35 * pf.S) * 6.0, (255, 245, 230))


def _aurora(I, pf, y0, y1):
    np = I.np
    xx, yy = I.full(pf)
    warp = I.fbm(pf.w, pf.h, 60 * pf.S / 4, 3, 51)
    cur = (0.5 + 0.5 * np.sin(xx * 0.09 + warp * 9.0)) ** 6
    fade = np.clip((yy - y0) / (y1 - y0), 0, 1) ** 1.5 * I.band(yy, y0, y1, 12)
    I.screen(pf, cur * fade * 0.45, (90, 255, 190))
    I.screen(pf, cur * fade ** 4 * 0.35, (255, 120, 220))


def _planet(I, pf, cx, cy, r):
    """giant ringed planet: banded disc, lit from the upper left, atmosphere rim, ring in front."""
    np = I.np
    xx, yy = I.full(pf)
    dx, dy = (xx - cx) / r, (yy - cy) / r
    rr = np.sqrt(dx ** 2 + dy ** 2)
    disc = np.clip((1 - rr) * r * pf.S * 0.5, 0, 1)
    lat = dy + 0.08 * I.fbm(pf.w, pf.h, 12 * pf.S, 3, 61)
    bands = 0.5 + 0.5 * np.sin(lat * 22)
    c1, c2 = np.asarray((236, 170, 120), np.float32), np.asarray((150, 80, 110), np.float32)
    col = c1 * bands[..., None] + c2 * (1 - bands[..., None])
    nz = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
    lit = np.clip(-dx * 0.55 - dy * 0.45 + nz * 0.55, 0.06, 1)
    col = col * lit[..., None]
    m = disc[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + col * m
    atm = np.clip(1 - np.abs(rr - 1.0) / 0.07, 0, 1) ** 2 * np.clip(-dx - dy + 0.5, 0, 1)
    I.screen(pf, atm * 0.9, (150, 200, 255))
    # ring (tilted ellipse), its back half hidden by the disc
    rx, ry = r * 1.9, r * 0.32
    e = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy + r * 0.1) / ry) ** 2)
    ring = np.clip(1 - np.abs(e - 1.0) / 0.12, 0, 1) * (0.6 + 0.4 * np.sin(e * 90))
    front = (yy > cy - r * 0.1) | (disc < 0.5)
    I.screen(pf, ring * front * 0.75, (255, 225, 190))


def _gantry(I, pf, x, top, base, w):
    def f(d, s):
        X = lambda v: v * s
        d.rectangle([X(x - w / 2), X(top), X(x - w / 2 + 1.2), X(base)], fill=255)
        d.rectangle([X(x + w / 2 - 1.2), X(top), X(x + w / 2), X(base)], fill=255)
        y = top
        while y < base:
            d.line([(X(x - w / 2), X(y)), (X(x + w / 2), X(y + 7))], fill=230, width=max(1, int(0.5 * s)))
            d.line([(X(x + w / 2), X(y)), (X(x - w / 2), X(y + 7))], fill=230, width=max(1, int(0.5 * s)))
            d.line([(X(x - w / 2), X(y)), (X(x + w / 2), X(y))], fill=255, width=max(1, int(0.6 * s)))
            y += 7
        d.rectangle([X(x - w / 2 - 3), X(top - 3), X(x + w / 2 + 3), X(top)], fill=255)   # crane head
        d.line([(X(x), X(top - 3)), (X(x), X(top - 12))], fill=255, width=max(1, int(0.8 * s)))
    m = I.draw_mask(pf, f)
    I.silhouette(pf, m, (18, 14, 44), rim=(170, 200, 255), rim_k=0.8)
    for i in range(int((base - top) / 14)):
        I.glow(pf, x + (w / 2 + 0.5) * (1 if i % 2 else -1), top + 4 + i * 14, 1.6, 1.6, (255, 70, 60), 0.9, 1.5)
    I.glow(pf, x, top - 12, 2.5, 2.5, (255, 60, 50), 1.0, 1.5)


def _sphere_tank(I, pf, cx, cy, r):
    np = I.np
    xx, yy = I.full(pf)
    dx, dy = (xx - cx) / r, (yy - cy) / r
    rr = np.sqrt(dx ** 2 + dy ** 2)
    disc = np.clip((1 - rr) * r * pf.S * 0.5, 0, 1)
    legs = I.poly(pf, [(cx - r * 0.8, cy), (cx - r * 0.6, cy), (cx - r * 0.7, cy + r * 1.4), (cx - r * 0.9, cy + r * 1.4)]) + \
        I.poly(pf, [(cx + r * 0.6, cy), (cx + r * 0.8, cy), (cx + r * 0.9, cy + r * 1.4), (cx + r * 0.7, cy + r * 1.4)])
    I.silhouette(pf, np.clip(legs, 0, 1), (20, 16, 46))
    nz = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
    sh = np.clip(0.25 + nz * 0.5 - dx * 0.35 - dy * 0.2, 0.08, 1)
    spec = np.clip(1 - np.hypot(dx + 0.35, dy + 0.4) / 0.3, 0, 1) ** 2
    col = np.asarray((150, 150, 190), np.float32) * sh[..., None] + spec[..., None] * 200
    m = disc[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + col * m


def _rocket(I, pf, x, top, base):
    w = 5.0
    body = I.poly(pf, [(x - w / 2, base - 4), (x - w / 2, top + 9), (x, top), (x + w / 2, top + 9), (x + w / 2, base - 4)])
    fins = I.poly(pf, [(x - w / 2, base - 12), (x - w / 2 - 3.5, base), (x - w / 2, base - 3)]) + \
        I.poly(pf, [(x + w / 2, base - 12), (x + w / 2 + 3.5, base), (x + w / 2, base - 3)])
    I.silhouette(pf, body, (210, 214, 236), rim=(255, 255, 255), rim_off=(-0.6, 0), rim_k=0.6)
    I.put(pf, I.poly(pf, [(x + 0.4, base - 4), (x + 0.4, top + 9), (x + w / 2, top + 9), (x + w / 2, base - 4)]), (120, 120, 160), 0.6)
    I.put(pf, I.poly(pf, [(x - w / 2, top + 16), (x + w / 2, top + 16), (x + w / 2, top + 19), (x - w / 2, top + 19)]), (40, 40, 70), 0.9)
    I.silhouette(pf, I.np.clip(fins, 0, 1), (200, 60, 60))


def _steam(I, pf, cx, cy, rx, ry, seed, alpha=0.6, warm=(255, 170, 110)):
    np = I.np
    xx, yy = I.full(pf)
    n = I.fbm(pf.w, pf.h, 9 * pf.S, 4, seed)
    rad = np.clip(1 - ((xx - cx) / rx) ** 2 - ((yy - cy) / ry) ** 2, 0, 1)
    dens = np.clip((n * 0.9 + rad * 0.9 - 0.75) / 0.25, 0, 1) * (rad > 0)
    gy, gx = np.gradient(I.blur(n, 1.5 * pf.S))
    lit = np.clip(0.55 + (gx * 0.5 - gy * 0.8) * pf.S * 60, 0, 1)
    below = np.clip((yy - (cy - ry * 0.3)) / ry, 0, 1)        # engine light from underneath
    c = np.asarray((214, 214, 236), np.float32) * lit[..., None] + np.asarray((90, 90, 130), np.float32) * (1 - lit[..., None])
    c = c * (1 - below[..., None] * 0.5) + np.asarray(warm, np.float32) * below[..., None] * 0.5
    m = (dens * alpha)[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + c * m


def _apron(I, pf, vx, vy, y0, y1):
    """floodlit concrete slabs in perspective, joints converging on the horizon, painted guide lines."""
    np = I.np
    xx, yy = I.full(pf)
    dy = np.maximum(yy - vy, 1.0)
    row = np.sqrt(dy) * 0.9
    u = (xx - vx) / dy * 7.0
    fr = np.abs((row % 1) - 0.5)
    fu = np.abs((u % 1) - 0.5)
    joint = np.clip(1 - np.minimum((0.5 - fr) * dy * 0.35, (0.5 - fu) * dy * 0.5), 0, 1)
    slab = 0.85 + 0.3 * (I.smooth_noise(pf.w, pf.h, int(6 * pf.S), 71) - 0.5) + \
        0.12 * (np.floor(row) % 3 == 0) * (np.floor(u) % 2 == 0)
    w = I.band(yy, y0, y1, 6) * np.clip((yy - vy) / 60, 0, 1)
    tint = np.asarray((96, 92, 140), np.float32)
    m = (w * 0.30)[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + tint * m
    pf.rgb *= (1 - w * (joint * 0.35 + (1 - slab) * 0.5))[..., None]
    # yellow guide lines converging on the pad
    for k in (-1.5, 1.5):
        lane = np.clip(1 - np.abs(u - k) * dy * 0.12, 0, 1) * w * ((row * 2 % 1) < 0.6)
        I.put(pf, lane, (255, 200, 60), 0.55)
    I.glow(pf, vx, (y0 + y1) / 2, 140, (y1 - y0) / 1.5, (200, 210, 255), 0.10, 2.0)


def backdrop(pf, B, I):
    np = I.np = B.np
    I.smooth_noise = B.smooth_noise
    I.blur = B.blur
    HZ = 488.0
    G = B.G
    # --- deep space: nebula, Milky Way, aurora curtains low over the complex
    I.nebula(pf, 0, 250, [(120, 50, 200), (30, 110, 220), (200, 60, 140)], seed=31, k=0.30)
    _milky_way(I, pf)
    I.clouds(pf, 150, 250, (150, 150, 230), (20, 16, 70), cover=0.35, cell=70, seed=33, alpha=0.35)
    _aurora(I, pf, 352, HZ - 20)
    # --- horizon: the giant planet rising, launch complex silhouettes, searchlights
    I.glow(pf, 160, HZ - 4, 240, 40, (255, 140, 90), 0.45, 1.4)
    _planet(I, pf, 262, HZ - 6, 46)
    I.beams(pf, 36, HZ - 4, 16, 7, 460, (190, 210, 255), 0.26)
    I.beams(pf, 292, HZ - 4, -24, 6, 460, (200, 220, 255), 0.22)
    I.beams(pf, 210, HZ - 8, -4, 5, 300, (255, 200, 160), 0.14)
    _sphere_tank(I, pf, 76, HZ - 16, 9)
    _sphere_tank(I, pf, 236, HZ - 14, 7)
    _rocket(I, pf, 206, HZ - 58, HZ - 4)
    _gantry(I, pf, 196, HZ - 64, HZ - 2, 7)
    _steam(I, pf, 206, HZ - 6, 26, 9, 81, alpha=0.7)
    _gantry(I, pf, 32, HZ - 110, HZ - 2, 9)
    _gantry(I, pf, 292, HZ - 96, HZ - 2, 8)
    ground = I.poly(pf, [(0, HZ - 2), (320, HZ - 2), (320, HZ + 6), (0, HZ + 6)], blur_u=1.5)
    I.put(pf, ground, (22, 16, 46), 0.85)
    # --- the apron: floodlit concrete toward the flippers, distant runway lights
    _apron(I, pf, 160, HZ - 4, HZ + 4, 640)
    for i in range(26):
        x = 8 + i * 12
        I.glow(pf, x, HZ + 3, 1.3, 0.9, (120, 200, 255) if i % 2 else (255, 200, 120), 0.8, 1.5)
    I.bokeh(pf, 16, 360, 304, 470, 18, 3, 7, [(255, 200, 140), (140, 200, 255), (255, 120, 120)], 0.16, seed=36)


def light(pf, B, I):
    G = B.G
    tx, ty = G.TOWER
    # exhaust steam rolling off the main pad (kept off the labels, under the rocket's flame trench)
    _steam(I, pf, tx - 30, ty + 22, 20, 10, 91, alpha=0.45)
    _steam(I, pf, tx + 30, ty + 22, 20, 10, 92, alpha=0.45)
    pools = [(tx, ty + 10, 80, 70, (255, 190, 120), 0.34),        # rocket + engine glow
             (130, 432, 80, 60, (170, 200, 255), 0.28),          # logo
             (160, 120, 120, 70, (200, 190, 255), 0.18),         # bumpers under the stars
             (150, 550, 150, 90, (255, 245, 230), 0.22)]         # flipper area stays bright
    I.relight(pf, pools, ambient=0.82, vignette=0.20)
    I.grain(pf, 0.05, seed=37)
