"""Launch Pad - theme painters (printed playfield art + raised rocket model) for tools/build_table.py.

paint(pf, B)   : printed art, called right after the copper-bar base
overlay(ov, B) : raised toys above the playfield (the rocket on its launch pad)
B is the build_table module (helpers, numpy as B.np, geometry as B.G). All art is original.
"""
import math
import random
import numpy as np


def _planet(pf, B, cx, cy, r, c_lit, c_dark, ring=None):
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
    b = pf.box(min(x, x - dx * L), min(y, y - dy * L), max(x, x - dx * L), max(y, y - dy * L), 4)
    xx, yy = pf.grid(b)
    t = np.clip(((x - xx) * dx + (y - yy) * dy) / L, 0, 1)
    px, py = x - dx * L * t, y - dy * L * t
    dist = np.hypot(xx - px, yy - py)
    w = 0.6 + 2.6 * (1 - t)
    m = np.clip(1 - dist / w, 0, 1) * (1 - t) ** 1.3
    pf.add(b, m * 0.9, col)


def _hazard_ring(pf, B, cx, cy, r0, r1, n=24):
    b, d, ox, oy = pf.disc_field(cx, cy, r1 + 1)
    ang = np.arctan2(oy, ox)
    k = (((ang / (2 * np.pi) * n + d / 6) % 1) < 0.5)[..., None]
    col = np.where(k, np.array([255, 200, 40], np.float32), np.array([28, 26, 32], np.float32))
    m = pf.cov(d, r1) * (1 - pf.cov(d, r0))
    pf.put(b, m, col, alpha=0.9)
    pf.put(b, pf.cov(d, r0), (90, 92, 104), alpha=0.85)        # concrete pad
    pf.put(b, pf.cov(np.abs(d - r1), 0.6), (20, 16, 24))


def _launch_complex_foundation(pf, B, cx, cy, r=52.0):
    """Heavy reinforced concrete hexagonal launch pad & blast trench (NO CIRCUS SUNBURST)."""
    # 1. Hexagonal heavy foundation slab
    pts = []
    for i in range(6):
        a = math.radians(30 + i * 60)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    b_slab, m_slab = pf.poly_mask(pts)
    xx, yy = pf.grid(b_slab)
    # Concrete slab with panel seams
    grid_seams = (((xx - cx) % 14.0 < 0.8) | ((yy - cy) % 14.0 < 0.8))[..., None]
    concrete = np.where(grid_seams, np.array([42, 46, 56], np.float32), np.array([68, 74, 88], np.float32))
    pf.put(b_slab, m_slab, concrete, alpha=0.92)

    # Outer metallic rim on the hexagon
    for i in range(6):
        p1 = pts[i]
        p2 = pts[(i + 1) % 6]
        b_edge = pf.box(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1]), 2)
        def f_edge(d, tf, s):
            d.line([tf(*p1), tf(*p2)], fill=255, width=int(1.2 * s))
        pf.put(b_edge, pf.pil_mask(b_edge, f_edge), (160, 175, 195), alpha=0.85)

    # 2. Flame exhaust deflector channel (pointing downward)
    trench_pts = [(cx - 24, cy + 10), (cx + 24, cy + 10), (cx + 34, cy + r + 12), (cx - 34, cy + r + 12)]
    b_trench, m_trench = pf.poly_mask(trench_pts)
    pf.put(b_trench, m_trench, (25, 28, 36), alpha=0.95)
    # Heat glow in the flame trench
    xx_t, yy_t = pf.grid(b_trench)
    glow_t = np.clip(1.0 - np.hypot((xx_t - cx) / 28.0, (yy_t - (cy + 22)) / 30.0), 0, 1) ** 2
    pf.add(b_trench, glow_t * 0.75, (255, 120, 30))
    pf.add(b_trench, (glow_t ** 2) * 0.6, (255, 220, 80))

    # 3. Concentric circular blast pad deflector rings
    b_ring, d_ring, _, _ = pf.disc_field(cx, cy, 38.0)
    # Titanium blast ring
    pf.put(b_ring, pf.cov(np.abs(d_ring - 34.0), 1.2), (180, 190, 210), alpha=0.9)
    pf.put(b_ring, pf.cov(np.abs(d_ring - 26.0), 1.0), (120, 130, 150), alpha=0.85)

    # 4. Service umbilical gantry arms radiating out to perimeter
    for ang_deg in (45, 135, 225, 315):
        rad = math.radians(ang_deg)
        x1 = cx + math.cos(rad) * 28.0
        y1 = cy + math.sin(rad) * 28.0
        x2 = cx + math.cos(rad) * (r - 2)
        y2 = cy + math.sin(rad) * (r - 2)
        b_arm = pf.box(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), 2)
        def f_arm(d, tf, s):
            d.line([tf(x1, y1), tf(x2, y2)], fill=255, width=int(1.8 * s))
        pf.put(b_arm, pf.pil_mask(b_arm, f_arm), (200, 150, 60), alpha=0.9)


def _mission_telemetry_radar(pf, B, cx, cy, rx=58.0, ry=34.0):
    """High-tech orbital radar & mission telemetry CRT display (NO CIRCUS SUNBURST)."""
    b = pf.box(cx - rx - 4, cy - ry - 4, cx + rx + 4, cy + ry + 4, 2)
    xx, yy = pf.grid(b)
    norm_dist = np.hypot((xx - cx) / rx, (yy - cy) / ry)

    # 1. Dark glowing navy CRT screen display
    screen = pf.cov(norm_dist, 1.0)
    pf.put(b, screen, (12, 24, 48), alpha=0.95)

    # Scanline phosphor CRT texture
    scanlines = ((yy % 2.5) < 1.0).astype(np.float32)
    pf.add(b, screen * scanlines * 0.15, (40, 120, 220))

    # Outer bezel ring
    bezel = pf.cov(np.abs(norm_dist - 1.0) * rx, 1.4)
    pf.put(b, bezel, (80, 160, 240), alpha=0.9)

    # 2. Concentric range rings (LEO, GEO, Lunar Transfer)
    for frac in (0.33, 0.66):
        ring = pf.cov(np.abs(norm_dist - frac) * rx, 0.7)
        pf.put(b, ring, (50, 140, 220), alpha=0.7)

    # 3. Crosshairs (X and Y telemetry axes)
    cross_h = pf.cov(np.abs(yy - cy), 0.6) * screen
    cross_v = pf.cov(np.abs(xx - cx), 0.6) * screen
    pf.put(b, cross_h, (70, 160, 255), alpha=0.6)
    pf.put(b, cross_v, (70, 160, 255), alpha=0.6)

    # 4. Elliptical transfer trajectory path
    def f_traj(d, tf, s):
        # Sweeping transfer orbit from bottom-left to top-right
        d.arc([tf(cx - rx * 0.85, cy - ry * 0.7), tf(cx + rx * 0.85, cy + ry * 0.7)], start=-160, end=40, fill=255, width=int(1.2 * s))
    m_traj = pf.pil_mask(b, f_traj)
    pf.put(b, m_traj, (255, 200, 70), alpha=0.85)

    # Trajectory waypoint nodes
    for px, py in ((cx - rx * 0.6, cy + ry * 0.35), (cx, cy - ry * 0.55), (cx + rx * 0.65, cy - ry * 0.1)):
        bb, dd, _, _ = pf.disc_field(px, py, 2.0)
        pf.put(bb, pf.cov(dd, 1.5), (255, 120, 40), alpha=0.95)


def _sensor_reticle(pf, B, cx, cy, r=12.0):
    """Sci-fi sensor target reticle for top rollover lanes."""
    bb, dd, ox, oy = pf.disc_field(cx, cy, r + 2)
    # Outer reticle ring
    pf.put(bb, pf.cov(np.abs(dd - r), 0.9), (120, 210, 255), alpha=0.8)
    pf.put(bb, pf.cov(np.abs(dd - r * 0.55), 0.6), (70, 170, 240), alpha=0.65)
    # Core target dot
    pf.put(bb, pf.cov(dd, 1.6), (255, 200, 80), alpha=0.9)
    # 4 crosshair ticks
    ticks = ((np.abs(ox) < 0.6) & (dd >= r * 0.3) & (dd <= r * 1.2)) | \
            ((np.abs(oy) < 0.6) & (dd >= r * 0.3) & (dd <= r * 1.2))
    pf.put(bb, ticks.astype(np.float32), (140, 230, 255), alpha=0.75)


def paint(pf, B):
    G = B.G
    # --- top: deep space with a red planet, a ringed planet, comets
    B.stars_sky(pf, 20, 18, 300, 210, 190, 11)
    _planet(pf, B, 58, 100, 12, (255, 140, 80), (120, 30, 30))
    _planet(pf, B, 252, 104, 9, (190, 210, 255), (50, 60, 140), ring=(220, 220, 255))
    _comet(pf, B, 96, 170, -0.8, -0.6, 26)
    _comet(pf, B, 236, 176, 0.75, -0.66, 22, (170, 230, 255))

    # --- mid: authentic REINFORCED HEX LAUNCH PAD & BLAST TRENCH (NO CIRCUS SUNBURST!)
    _launch_complex_foundation(pf, B, G.TOWER[0], G.TOWER[1] + 14, r=50.0)
    _hazard_ring(pf, B, G.TOWER[0], G.TOWER[1] + 14, 22, 28)
    _lattice(pf, B, G.RAMPS[0]["path"][:130])
    for sx, sy, k, a in ((112, 352, 0.75, 25), (72, 404, 0.62, -30), (198, 446, 0.55, 10)):
        _satellite(pf, B, sx, sy, k, a)

    # hangar door art beside the hangar hole
    b, m = pf.poly_mask([(256, 336), (282, 336), (282, 362), (256, 362)])
    xx, yy = pf.grid(b)
    slat = ((yy % 3.0) < 1.6)[..., None]
    pf.put(b, m, np.where(slat, np.array([120, 126, 140], np.float32), np.array([70, 74, 90], np.float32)), alpha=0.9)

    # --- lower centre: authentic RADAR TELEMETRY CRT DISPLAY (NO CIRCUS SUNBURST!)
    _mission_telemetry_radar(pf, B, 130, 432, rx=56.0, ry=32.0)

    # --- dead corners: hazard stripes; runway lights across the bonus row
    B.tent_stripes(pf, [(30, 530), (94, 574), (94, 628), (30, 628)], (255, 196, 40), (30, 28, 36), alpha=0.78)
    B.tent_stripes(pf, [(270, 530), (206, 574), (206, 628), (270, 628)], (255, 196, 40), (30, 28, 36), alpha=0.78)
    for i in range(11):
        x = 100 + i * 10
        bb, dd, _, _ = pf.disc_field(x, 518, 2.4)
        pf.put(bb, pf.cov(dd, 1.3), (255, 120, 60) if i % 2 else (120, 220, 255))
    B.inlane_art(pf)

    # High-tech targeting reticles for the 3 top rollover lanes (replacing sunburst)
    for i, (rx, ry) in enumerate([(60, 36), (160, 30), (250, 40)]):
        _sensor_reticle(pf, B, rx, ry, r=13.0)

    # Chrome LAUNCH PAD logo
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
