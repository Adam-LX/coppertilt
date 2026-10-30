"""Midnight Funfair - painted illustration (m10): a fairground at night seen from the midway.

backdrop(): moonlit cloud banks, fireworks and searchlights over a silhouetted fairground skyline
(big tops, a roller coaster, a drop tower) at the horizon, then a lamp-lit cobbled midway running
down the table in perspective with out-of-focus fairground lights.
light():    chiaroscuro relight - warm pools round the toys, the corners fall off into the night.
"""
import math
import random


def _tent(I, pf, cx, base, w, h, c1, c2, seed):
    """striped big top: cone roof + drum wall, rim-lit from the sunset behind it."""
    np = I.np
    xx, yy = I.full(pf)
    roof = I.poly(pf, [(cx, base - h), (cx + w / 2, base - h * 0.45), (cx - w / 2, base - h * 0.45)])
    wall = I.poly(pf, [(cx - w / 2, base - h * 0.45), (cx + w / 2, base - h * 0.45), (cx + w / 2, base), (cx - w / 2, base)])
    ang = np.arctan2(xx - cx, (yy - (base - h)) + 1e-3)
    stripe = ((np.floor(ang * 9) % 2) == 0)[..., None]
    roofc = np.where(stripe, np.asarray(c1, np.float32), np.asarray(c2, np.float32)) * 0.85
    wst = ((np.floor((xx - cx) / (w / 10)) % 2) == 0)[..., None]
    wallc = np.where(wst, np.asarray(c1, np.float32), np.asarray(c2, np.float32)) * 0.6
    # warm light spilling from the tent door onto the cobbles
    I.put(pf, I.poly(pf, [(cx - w * 0.1, base), (cx - w * 0.1, base - h * 0.3), (cx + w * 0.1, base - h * 0.3), (cx + w * 0.1, base)]), (255, 210, 120), 0.9)
    I.glow(pf, cx, base + 8, w * 0.9, 12, (255, 180, 100), 0.35, 1.6)
    # shade: the right side of the cone turns away from the sunset glow
    shade = np.clip(0.9 - (xx - cx) / w * 0.9, 0.35, 1.0)[..., None]
    m = roof[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + roofc * shade * m
    m = wall[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + wallc * shade * m
    I.silhouette(pf, np.clip(roof + wall, 0, 1), (0, 0, 0), alpha=0.0, rim=(255, 190, 140), rim_k=0.9)
    # pennant + festoon down the roof edges
    I.put(pf, I.poly(pf, [(cx, base - h - 7), (cx + 5, base - h - 5), (cx, base - h - 3)]), c1, 0.9)
    I.string_lights(pf, [(cx - w / 2, base - h * 0.45), (cx, base - h), (cx + w / 2, base - h * 0.45)], 0.8, 5,
                    [(255, 230, 150), (255, 120, 160), (140, 220, 255)], r=0.8, k=0.9)


def _coaster(I, pf, x0, x1, base, seed):
    """roller-coaster silhouette: a sine-hill track on a trestle of supports."""
    np = I.np
    pts = []
    for i in range(61):
        t = i / 60
        x = x0 + (x1 - x0) * t
        y = base - 20 - 16 * abs(math.sin(t * math.pi * 2.2 + 0.4)) * (1 - 0.4 * t)
        pts.append((x, y))

    def f(d, s):
        q = [(x * s, y * s) for x, y in pts]
        d.line(q, fill=255, width=int(1.6 * s))
        for x, y in pts[::4]:
            d.line([(x * s, y * s), (x * s, base * s)], fill=200, width=max(1, int(0.6 * s)))
        for (xa, ya), (xb, yb) in zip(pts[::4], pts[4::4]):
            d.line([(xa * s, ya * s), (xb * s, base * s)], fill=150, width=max(1, int(0.4 * s)))
    m = I.draw_mask(pf, f)
    I.silhouette(pf, m, (34, 12, 52), rim=(255, 170, 120), rim_k=0.7)
    # the coaster train lights
    for x, y in pts[18:24]:
        I.glow(pf, x, y - 1, 2.2, 2.2, (255, 240, 180), 0.8, 1.5)


def _drop_tower(I, pf, x, top, base):
    np = I.np
    m = I.poly(pf, [(x - 2.2, base), (x - 1.4, top), (x + 1.4, top), (x + 2.2, base)])
    I.silhouette(pf, m, (30, 10, 48), rim=(255, 180, 130), rim_k=0.8)
    I.put(pf, I.poly(pf, [(x - 5, top + 22), (x + 5, top + 22), (x + 5, top + 26), (x - 5, top + 26)]), (60, 20, 80), 1.0)
    for i in range(7):
        I.glow(pf, x, top + 3 + i * 6, 1.8, 1.8, (255, 80, 80) if i % 2 else (255, 230, 120), 0.9, 1.5)
    I.glow(pf, x, top, 3.5, 3.5, (255, 60, 60), 0.9, 1.5)


def _midway(I, pf, vx, vy, y0, y1):
    """cobbled midway in perspective: rows get taller toward the viewer, joints converge at the horizon."""
    np = I.np
    xx, yy = I.full(pf)
    dy = np.maximum(yy - vy, 1.0)
    depth = 1.0 / dy                         # 1/z
    row = (1.0 / depth) ** 0.5               # perspective-ish row spacing
    rowi = np.floor(row * 1.6)
    u = (xx - vx) / dy * 18 + (rowi % 2) * 0.5
    fr = np.abs(((row * 1.6) % 1) - 0.5)
    fu = np.abs((u % 1) - 0.5)
    joint = np.clip(1 - np.minimum((0.5 - fr) * dy * 0.25, (0.5 - fu) * 6) , 0, 1)
    stone = 0.82 + 0.18 * I.smooth_noise(pf.w, pf.h, 9, 77)
    w = I.band(yy, y0, y1, 30) * np.clip((yy - vy) / 120, 0, 1)
    pf.rgb *= (1 - (joint * 0.33 + (1 - stone) * 0.6) * w)[..., None]
    # lamp-light shine on the wet cobbles in the middle of the path
    I.glow(pf, vx, (y0 + y1) / 2, 120, (y1 - y0) / 1.6, (255, 200, 150), 0.10, 2.0)


def backdrop(pf, B, I):
    np = I.np = B.np
    I.smooth_noise = B.smooth_noise
    HZ = 470.0                                   # horizon: the fair stands behind the ferris wheel
    # --- sky: moonlit cloud banks, firework smoke, searchlights sweeping up from the fair
    I.clouds(pf, 10, 230, (176, 160, 240), (30, 20, 80), cover=0.52, cell=80, seed=11, alpha=0.72)
    I.glow(pf, 58, 98, 40, 40, (255, 240, 190), 0.30, 2.0)          # moon halo
    I.clouds(pf, 280, 440, (230, 140, 200), (70, 30, 100), cover=0.38, cell=60, seed=14, alpha=0.40, soft=40)
    I.nebula(pf, 0, 260, [(120, 60, 200), (40, 90, 200)], seed=12, k=0.28)
    I.beams(pf, 44, HZ - 20, 18, 8, 420, (190, 200, 255), 0.24)
    I.beams(pf, 280, HZ - 30, -22, 7, 420, (255, 190, 220), 0.22)
    I.firework(pf, 262, 58, 24, (255, 210, 90), seed=1, n=44)
    I.firework(pf, 236, 170, 17, (255, 110, 190), seed=2, n=34)
    I.firework(pf, 34, 168, 13, (120, 230, 255), seed=3, n=28, k=0.8)
    I.firework(pf, 110, 46, 12, (160, 255, 150), seed=4, n=26, k=0.7)
    I.firework(pf, 40, 372, 16, (255, 170, 80), seed=5, n=34, k=0.8)
    I.firework(pf, 262, 300, 14, (140, 255, 200), seed=6, n=30, k=0.7)
    # --- horizon: sunset glow behind the fairground skyline
    I.glow(pf, 160, HZ - 6, 230, 46, (255, 130, 110), 0.55, 1.4)
    _coaster(I, pf, 180, 306, HZ - 2, 5)
    _drop_tower(I, pf, 24, HZ - 104, HZ - 2)
    _tent(I, pf, 58, HZ, 50, 40, (236, 50, 80), (255, 220, 160), 1)
    _tent(I, pf, 252, HZ + 2, 56, 44, (60, 120, 236), (255, 220, 160), 2)
    _tent(I, pf, 204, HZ + 2, 30, 26, (250, 170, 40), (120, 40, 140), 3)
    _tent(I, pf, 100, HZ + 2, 28, 24, (60, 200, 120), (255, 230, 190), 4)
    ground = I.poly(pf, [(0, HZ - 1), (320, HZ - 1), (320, HZ + 8), (0, HZ + 8)], blur_u=2.0)
    I.put(pf, ground, (40, 14, 54), 0.8)
    I.string_lights(pf, [(10, HZ - 50), (70, HZ - 34), (130, HZ - 46), (190, HZ - 34), (250, HZ - 48), (312, HZ - 34)], 5.0, 7,
                    [(255, 230, 150), (255, 110, 140), (120, 220, 255), (150, 255, 150)], r=0.9)
    # --- midway: perspective cobbles toward the viewer, lamp bokeh in the dark
    _midway(I, pf, 160, HZ - 4, HZ + 6, 640)
    I.bokeh(pf, 16, 270, 300, 450, 26, 3, 8, [(255, 210, 120), (255, 120, 170), (120, 200, 255), (180, 255, 160)], 0.20, seed=8)
    I.bokeh(pf, 20, 490, 300, 630, 12, 5, 11, [(255, 200, 140), (200, 140, 255)], 0.12, seed=9)


def light(pf, B, I):
    G = B.G
    pools = [(162, 134, 80, 70, (255, 220, 170), 0.32),          # carousel
             (G.TOWER[0], G.TOWER[1], 70, 60, (255, 170, 110), 0.30),   # helter-skelter
             (130, 432, 80, 66, (230, 170, 255), 0.30),         # ferris wheel logo
             (150, 540, 150, 90, (255, 240, 220), 0.22)]        # flipper area stays bright
    I.relight(pf, pools, ambient=0.80, vignette=0.20)
    I.grain(pf, 0.05, seed=13)
