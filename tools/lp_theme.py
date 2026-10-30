"""Launch Pad - theme painters (printed playfield art + raised rocket model) for tools/build_table.py.

paint(pf, B)   : printed art, called right after the copper-bar base
overlay(ov, B) : raised toys above the playfield (the rocket on its launch pad)
B is the build_table module (helpers, numpy as B.np, geometry as B.G). All art is original.
"""
import math
import random


def _planet(pf, B, cx, cy, r, c_lit, c_dark, ring=None):
    np = B.np
    b, d, ox, oy = pf.disc_field(cx, cy, r * 3)
    glow = np.clip(1 - d / (r * 3), 0, 1) ** 2
    pf.add(b, glow * 0.45, tuple(v * 0.5 for v in c_lit))
    disc = pf.cov(d, r)
    lit = np.clip(0.75 - 0.55 * (ox + oy * 0.8) / (r * 1.3), 0, 1)[..., None]
    bands = B.smooth_noise(b[3] - b[2], b[1] - b[0], 8, int(cx))[..., None]
    col = np.asarray(c_dark, np.float32) * (1 - lit) + np.asarray(c_lit, np.float32) * lit
    pf.put(b, disc, col * (0.85 + 0.25 * bands))
    if ring:
        def f(dr, tf, s):
            dr.ellipse([tf(cx - r * 1.9, cy - r * 0.55), tf(cx + r * 1.9, cy + r * 0.55)], outline=255, width=int(1.1 * s))
        bb = pf.box(cx - r * 2, cy - r, cx + r * 2, cy + r, 2)
        m = pf.pil_mask(bb, f)
        xx, yy = pf.grid(bb)
        front = ((yy > cy) | (np.hypot(xx - cx, yy - cy) > r)).astype(np.float32)
        pf.put(bb, m * front, ring, alpha=0.9)


def _lattice(pf, B, path, col=(170, 176, 196), every=10, depth=12):
    def f(d, tf, s):
        for i in range(0, len(path) - every, every):
            (x, y), (x2, y2) = path[i], path[i + every]
            d.line([tf(x + 4, y + 6), tf(x + 4, y + 6 + depth)], fill=210, width=int(0.9 * s))
            d.line([tf(x + 4, y + 6), tf(x2 + 4, y2 + 6 + depth)], fill=150, width=int(0.6 * s))
            d.line([tf(x + 4, y + 6 + depth), tf(x2 + 4, y2 + 6)], fill=150, width=int(0.6 * s))
    xs, ys = [p[0] for p in path], [p[1] for p in path]
    b = pf.box(min(xs), min(ys), max(xs) + 8, max(ys) + depth + 8, 2)
    pf.put(b, pf.pil_mask(b, f), col, alpha=0.7)


def _satellite(pf, B, x, y, k=1.0, ang=20.0):
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)

    def R(px, py):
        return (x + (px * ca - py * sa) * k, y + (px * sa + py * ca) * k)
    for sx in (-1, 1):       # solar panels
        b, m = pf.poly_mask([R(sx * 4, -3), R(sx * 14, -3), R(sx * 14, 3), R(sx * 4, 3)])
        pf.put(b, m, (40, 90, 200), alpha=0.95)
        for g in range(1, 4):
            bb, mm = pf.poly_mask([R(sx * (4 + g * 2.5), -3), R(sx * (4 + g * 2.5 + 0.4), -3),
                                   R(sx * (4 + g * 2.5 + 0.4), 3), R(sx * (4 + g * 2.5), 3)])
            pf.put(bb, mm, (160, 200, 255), alpha=0.8)
    b, m = pf.poly_mask([R(-4, -4), R(4, -4), R(4, 4), R(-4, 4)])
    pf.put(b, m, (235, 200, 90))
    bb, dd, _, _ = pf.disc_field(*R(0, -6), 2.2 * k)
    pf.put(bb, pf.cov(dd, 2.0 * k), (230, 230, 240))


def _comet(pf, B, x, y, dx, dy, L, col=(255, 230, 170)):
    np = B.np
    b = pf.box(min(x, x - dx * L), min(y, y - dy * L), max(x, x - dx * L), max(y, y - dy * L), 4)
    xx, yy = pf.grid(b)
    t = np.clip(((x - xx) * dx + (y - yy) * dy) / L, 0, 1)
    px, py = x - dx * L * t, y - dy * L * t
    dist = np.hypot(xx - px, yy - py)
    w = 0.6 + 2.6 * (1 - t)
    m = np.clip(1 - dist / w, 0, 1) * (1 - t) ** 1.3
    pf.add(b, m * 0.9, col)


def _hazard_ring(pf, B, cx, cy, r0, r1, n=24):
    np = B.np
    b, d, ox, oy = pf.disc_field(cx, cy, r1 + 1)
    ang = np.arctan2(oy, ox)
    k = (((ang / (2 * np.pi) * n + d / 6) % 1) < 0.5)[..., None]
    col = np.where(k, np.array([255, 200, 40], np.float32), np.array([28, 26, 32], np.float32))
    m = pf.cov(d, r1) * (1 - pf.cov(d, r0))
    pf.put(b, m, col, alpha=0.9)
    pf.put(b, pf.cov(d, r0) , (90, 92, 104), alpha=0.85)        # concrete pad
    pf.put(b, pf.cov(np.abs(d - r1), 0.6), (20, 16, 24))


def paint(pf, B):
    G = B.G
    np = B.np
    # --- top: deep space with a red planet, a ringed planet, comets
    B.stars_sky(pf, 20, 18, 300, 210, 190, 11)
    _planet(pf, B, 58, 100, 12, (255, 140, 80), (120, 30, 30))
    _planet(pf, B, 252, 104, 9, (190, 210, 255), (50, 60, 140), ring=(220, 220, 255))
    _comet(pf, B, 96, 170, -0.8, -0.6, 26)
    _comet(pf, B, 236, 176, 0.75, -0.66, 22, (170, 230, 255))
    # --- mid: engine-glow burst around the launch pad, the service tower lattice by the gantry ramp
    B.sunburst(pf, G.TOWER[0], G.TOWER[1] + 14, 20, 150, 30, (250, 150, 50), (150, 50, 44), y_clip=(196, 352))
    _hazard_ring(pf, B, G.TOWER[0], G.TOWER[1] + 14, 22, 28)
    _lattice(pf, B, G.RAMPS[0]["path"][:130])
    for sx, sy, k, a in ((112, 352, 0.75, 25), (72, 404, 0.62, -30), (198, 446, 0.55, 10)):
        _satellite(pf, B, sx, sy, k, a)
    # hangar door art beside the hangar hole
    b, m = pf.poly_mask([(256, 336), (282, 336), (282, 362), (256, 362)])
    xx, yy = pf.grid(b)
    slat = ((yy % 3.0) < 1.6)[..., None]
    pf.put(b, m, np.where(slat, np.array([120, 126, 140], np.float32), np.array([70, 74, 90], np.float32)), alpha=0.9)
    # --- lower centre: chrome LAUNCH PAD logo inside an orbit diagram
    B.sunburst(pf, 130, 432, 0, 70, 20, (60, 90, 200), (30, 44, 120), y_clip=(380, 480), alpha=0.6)

    def orbit(d, tf, s):
        for rx, ry in ((50, 18), (40, 30)):
            d.ellipse([tf(130 - rx, 432 - ry), tf(130 + rx, 432 + ry)], outline=255, width=int(0.8 * s))
    ob = pf.box(76, 398, 184, 466, 2)
    pf.put(ob, pf.pil_mask(ob, orbit), (140, 200, 255), alpha=0.7)
    # --- dead corners: hazard stripes; runway lights across the bonus row
    B.tent_stripes(pf, [(30, 530), (94, 574), (94, 628), (30, 628)], (255, 196, 40), (30, 28, 36), alpha=0.78)
    B.tent_stripes(pf, [(270, 530), (206, 574), (206, 628), (270, 628)], (255, 196, 40), (30, 28, 36), alpha=0.78)
    for i in range(11):
        x = 100 + i * 10
        bb, dd, _, _ = pf.disc_field(x, 518, 2.4)
        pf.put(bb, pf.cov(dd, 1.3), (255, 120, 60) if i % 2 else (120, 220, 255))
    B.inlane_art(pf)
    for i in range(3):
        B.sunburst(pf, (60, 160, 250)[i], (36, 30, 40)[i], 0, 14, 12, (255, 220, 140), (60, 60, 160), alpha=0.35)
    B.printed_text(pf, "LAUNCH", 13, 130, 418, spacing=0.6, glow=(255, 140, 60), grad=B.CHROME, outline=(8, 8, 30))
    B.printed_text(pf, "PAD", 18, 130, 442, spacing=1.2, glow=(90, 170, 255), grad=B.CHROME, outline=(8, 8, 30))
    # --- shot labels (big, readable)
    lab = dict(col=(255, 238, 196), outline=(16, 4, 24))
    B.printed_text(pf, "GANTRY", 4.6, 68, 382, angle=90, **lab)
    B.printed_text(pf, "BOOSTER", 4.4, 202, 340, angle=80, **lab)
    B.printed_text(pf, "ORBIT", 5, 24, 254, angle=90, col=(255, 240, 120))
    B.printed_text(pf, "ORBIT", 5, 277, 254, angle=-90, col=(255, 240, 120))
    B.printed_text(pf, "SILO", 3.8, 48, 318, col=(255, 170, 235))
    B.printed_text(pf, "CONTROL", 4.2, 122, 300, col=(160, 255, 170))
    B.printed_text(pf, "HANGAR", 3.8, 268, 370, col=(255, 170, 235))
    B.printed_text(pf, "STAGE", 4.2, 242, 248, angle=-90, col=(255, 196, 96))
    B.printed_text(pf, "LAUNCH PAD", 4.0, 212, 405, angle=36, col=(130, 236, 255))
    B.printed_text(pf, "M A R S", 4.2, 59, 247, angle=90, col=(255, 130, 118))
    B.printed_text(pf, "T-MINUS", 3.0, 127, 286, col=(255, 210, 150))
    B.printed_text(pf, "LIFTOFF", 3.6, 176, 364, angle=-20, col=(255, 200, 120))
    B.printed_text(pf, "SHOOT AGAIN", 4, 150, 566, col=(255, 170, 150))
    B.printed_text(pf, "EXTRA BALL", 4, 150, 504, col=(255, 214, 150))
    B.printed_text(pf, "BONUS MULTIPLIER", 3.4, 150, 482, col=(255, 214, 150))
    B.printed_text(pf, "KICKBACK", 3.6, 19, 518, angle=90, col=(150, 255, 160))
    B.printed_text(pf, "JACKPOT", 4.4, 150, 397, col=(255, 255, 255))
    B.printed_text(pf, "LOCK", 3.6, 270, 420, col=(255, 170, 235))
    B.printed_text(pf, "SUPER", 3.2, 150, 358, col=(255, 214, 120))


def overlay(ov, B):
    """the rocket model standing on its pad (raised toy, casts the overlay shadow)."""
    np, S, G = B.np, B.S, B.G
    cx = G.TOWER[0]
    top, bot = 222.0, 272.0
    # fins first (behind the body)
    for sx in (-1, 1):
        b, m = ov.poly_mask([(cx + sx * 6.5, 252), (cx + sx * 14, 266), (cx + sx * 14, 273), (cx + sx * 6.5, 268)])
        xx, yy = ov.grid(b)
        lit = np.clip(1.0 - 0.25 * sx - (yy - 252) / 60, 0.5, 1.2)[..., None]
        ov.put(b, m, np.array([225, 60, 40], np.float32) * lit, ht=np.full_like(m, 10 * S), spec=0.8, shin=0.7)
    # body: white cylinder with an ogive nose (shaded across its width)
    pts = []
    for i in range(13):
        u = i / 12
        y = top + u * 16
        w = 6.5 * math.sin(u * math.pi / 2) ** 0.7
        pts.append((cx + w, y))
    pts += [(cx + 6.5, bot - 2), (cx + 5.0, bot), (cx - 5.0, bot), (cx - 6.5, bot - 2)]
    pts += [(2 * cx - x, y) for x, y in reversed(pts[:13])]
    b, m = ov.poly_mask(pts)
    xx, yy = ov.grid(b)
    u = np.clip((xx - cx) / 6.5, -1, 1)
    roundv = np.sqrt(np.clip(1 - u * u, 0, 1))
    lit = (0.55 + 0.55 * roundv - 0.28 * u)[..., None]
    base = np.where(((yy < top + 13) | ((yy > 244) & (yy < 248)))[..., None],
                    np.array([230, 50, 40], np.float32), np.array([240, 240, 246], np.float32))
    base = np.where(((yy > 256) & (yy < 262))[..., None], np.array([40, 44, 56], np.float32), base)
    ov.put(b, m, np.clip(base * lit, 0, 255), ht=(14 + 8 * roundv) * S, spec=0.9, shin=0.8)
    # porthole + engine bell
    ov.dome(cx, 236, 2.6, "chrome", (240, 240, 250), height=2 * S, z=22)
    bb, dd, _, _ = ov.disc_field(cx, 236, 1.9)
    ov.put(bb, ov.cov(dd, 1.8), (60, 150, 255), ht=np.full_like(dd, 24 * S))
    ov.dome(cx, bot + 1.5, 3.4, "chrome", (200, 200, 212), height=2 * S, z=6, flat=0.4)
    # launch clamps (two short gantry arms)
    for sx in (-1, 1):
        ov.tube([(cx + sx * 7.2, 250), (cx + sx * 19, 250)], 1.0, "chrome", (220, 220, 230), height=1.6 * S, z=8)
        ov.dome(cx + sx * 19, 250, 1.8, "chrome", (220, 220, 230), height=1.6 * S, z=6)
