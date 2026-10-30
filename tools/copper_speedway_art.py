"""Copper Speedway - painted illustration (m10): a floodlit night race seen from the infield.

backdrop(): hazy night sky lit by stadium floodlights, packed grandstands with camera-flash bokeh
behind the bumpers, then the infield: mowed-grass stripes and a sweeping asphalt bend with
red/white kerbs and skid marks across the lower table.
light():    floodlight chiaroscuro, print grain.
"""
import math
import random


def _crowd(I, pf, y0, y1, seed):
    """tiered stands: rows of tiny heads in team colours, darker toward the back, a roof line."""
    np = I.np
    xx, yy = I.full(pf)
    rows = 9
    t = (yy - y0) / (y1 - y0)
    inside = ((yy > y0) & (yy < y1)).astype(np.float32)
    ri = np.floor(t * rows)
    fy = (t * rows) % 1
    hx = xx / 3.0 + ri * 0.5  # CROWD2
    fx = hx % 1
    head = np.clip(1 - np.hypot(fx - 0.5, (fy - 0.4) * 1.3) / 0.42, 0, 1)
    body = (fy > 0.55).astype(np.float32) * 0.8
    rng = np.random.default_rng(seed)
    pal = np.asarray([(230, 80, 60), (240, 200, 70), (70, 140, 230), (235, 235, 235), (70, 190, 110), (200, 110, 60)], np.float32)
    idx = ((np.floor(hx) * 7 + ri * 13 + (I.smooth_noise(pf.w, pf.h, int(3 * pf.S), seed) * 40)).astype(np.int64)) % len(pal)
    cell = np.sin(np.floor(hx) * 12.9898 + ri * 78.233) * 43758.5453
    cell = cell - np.floor(cell)
    lit = 0.7 + 0.6 * t + 0.35 * (cell - 0.5)
    head = head * (cell > 0.12)
    col = pal[idx] * lit[..., None]
    skin = np.asarray((215, 165, 130), np.float32) * lit[..., None]
    step = np.asarray((40, 44, 60), np.float32) * (0.6 + 0.4 * fy)[..., None]
    c = step * (1 - np.maximum(head, body)[..., None]) + col * body[..., None] + skin * head[..., None] * (1 - body[..., None])
    m = (inside * 0.9)[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + c * m
    # roof beam + support pillars
    I.put(pf, I.poly(pf, [(0, y0 - 4), (320, y0 - 4), (320, y0), (0, y0)]), (30, 30, 44), 0.95)
    for x in range(20, 320, 80):
        I.put(pf, I.poly(pf, [(x, y0), (x + 1.6, y0), (x + 1.6, y1), (x, y1)]), (36, 36, 52), 0.8)
    # camera flashes in the crowd
    r = random.Random(seed)
    for _ in range(26):
        x, y = r.uniform(6, 314), r.uniform(y0 + 2, y1 - 2)
        I.glow(pf, x, y, 4.5, 4.5, (255, 255, 240), r.uniform(0.35, 0.9), 2.2)
        I.glow(pf, x, y, 1.0, 1.0, (255, 255, 255), 1.0, 1.0)


def _grass(I, pf, y0, y1):
    np = I.np
    xx, yy = I.full(pf)
    w = I.band(yy, y0, y1, 8)
    stripe = (np.floor((xx * 0.8 + yy * 0.35) / 22) % 2).astype(np.float32)
    blade = I.fbm(pf.w, pf.h, 1.2 * pf.S, 2, 101)
    tint = np.asarray((40, 120, 70), np.float32) * (0.82 + 0.25 * stripe + 0.2 * (blade - 0.5))[..., None]
    m = (w * 0.55)[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + tint * m


def _track(I, pf, cx, cy, r0, r1):
    """sweeping asphalt bend (arc of a big circle) with kerbs, a racing line of rubber and skid marks."""
    np = I.np
    xx, yy = I.full(pf)
    d = np.hypot(xx - cx, yy - cy)
    ang = np.arctan2(yy - cy, xx - cx)
    tar = np.clip((d - r0) * pf.S * 0.5, 0, 1) * np.clip((r1 - d) * pf.S * 0.5, 0, 1) * (yy < cy)
    agg = I.fbm(pf.w, pf.h, 0.8 * pf.S, 2, 111)
    shade = 0.85 + 0.25 * agg + 0.1 * (I.smooth_noise(pf.w, pf.h, int(10 * pf.S), 112) - 0.5)
    asph = np.asarray((66, 68, 80), np.float32) * shade[..., None]
    m = (tar * 0.88)[..., None]
    pf.rgb[:] = pf.rgb * (1 - m) + asph * m
    # rubbered racing line (apex toward the inside), skid marks along the bend
    mid = r0 + (r1 - r0) * (0.38 + 0.18 * np.cos(ang * 3))
    line = np.exp(-((d - mid) / 4.0) ** 2) * tar
    I.mul(pf, 1 - line * 0.35)
    r = random.Random(7)
    for _ in range(9):
        a0 = r.uniform(-2.7, -0.45)
        rr = r.uniform(r0 + 5, r1 - 5)
        ln = r.uniform(0.04, 0.12)
        sk = np.exp(-((d - rr) / 0.7) ** 2) * ((ang > a0) & (ang < a0 + ln)) * tar
        sk2 = np.exp(-((d - rr - 3.2) / 0.7) ** 2) * ((ang > a0) & (ang < a0 + ln)) * tar
        I.mul(pf, 1 - (sk + sk2) * 0.55)
    # red/white kerbs on both edges
    for e in (r0, r1):
        kb = np.clip(1 - np.abs(d - e) / 2.4, 0, 1) * (yy < cy)
        kb = np.clip(kb * 3, 0, 1)
        red = (np.floor(ang * cx / 5.0) % 2 == 0)[..., None]
        kc = np.where(red, np.asarray((220, 40, 40), np.float32), np.asarray((240, 240, 240), np.float32))
        m = (kb * 0.9)[..., None]
        pf.rgb[:] = pf.rgb * (1 - m) + kc * m
    # dashed white edge line inside the kerbs
    for e in (r0 + 3.5, r1 - 3.5):
        wl = np.clip(1 - np.abs(d - e) / 0.5, 0, 1) * tar
        I.put(pf, wl, (235, 235, 235), 0.6)


def backdrop(pf, B, I):
    np = I.np = B.np
    I.smooth_noise = B.smooth_noise
    I.blur = B.blur
    # --- sky: floodlit haze, low lit clouds, stadium glow
    I.glow(pf, 160, 120, 220, 90, (120, 170, 220), 0.35, 1.5)
    I.clouds(pf, 10, 110, (170, 200, 230), (20, 40, 60), cover=0.45, cell=70, seed=121, alpha=0.45)
    # --- stands behind the bumpers
    _crowd(I, pf, 122, 194, 131)
    for x, a in ((52, 150), (248, -150), (52, 120), (248, -120)):  # BEAMSAFTER
        I.beams(pf, x, 90, a, 22, 360, (220, 235, 255), 0.30)
    I.beams(pf, 30, 70, 20, 5, 300, (220, 235, 255), 0.16)
    I.beams(pf, 290, 70, -20, 5, 300, (220, 235, 255), 0.16)
    I.glow(pf, 160, 196, 200, 16, (255, 230, 190), 0.25, 1.5)
    # --- infield grass + the sweeping bend across the lower table
    _grass(I, pf, 352, 640)
    _track(I, pf, 160, 800, 318, 360)
    I.bokeh(pf, 10, 360, 310, 470, 14, 3, 7, [(255, 240, 200), (255, 120, 90), (160, 210, 255)], 0.12, seed=133)


def light(pf, B, I):
    G = B.G
    tx, ty = G.TOWER
    pools = [(tx, ty, 80, 70, (255, 200, 140), 0.32),            # pace car podium
             (130, 432, 80, 56, (200, 255, 210), 0.26),          # logo / oval
             (52, 110, 90, 140, (220, 235, 255), 0.16),          # floodlight spill
             (248, 110, 90, 140, (220, 235, 255), 0.16),
             (150, 550, 150, 90, (255, 245, 230), 0.22)]         # flipper area stays bright
    I.relight(pf, pools, ambient=0.82, vignette=0.20)
    I.grain(pf, 0.05, seed=137)
