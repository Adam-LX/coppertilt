"""Copper Speedway - theme painters (printed playfield art + raised pace-car model) for tools/build_table.py.

paint(pf, B)   : printed art, called right after the copper-bar base
overlay(ov, B) : raised toys above the playfield (the pace car on its podium)
B is the build_table module (helpers, numpy as B.np, geometry as B.G). All art is original.
"""
import math


def _checker_poly(pf, B, pts, cell=6.0, c1=(240, 240, 240), c2=(20, 20, 24), alpha=0.85, ang=0.0):
    np = B.np
    b, m = pf.poly_mask(pts)
    xx, yy = pf.grid(b)
    a = math.radians(ang)
    u = xx * math.cos(a) + yy * math.sin(a)
    v = -xx * math.sin(a) + yy * math.cos(a)
    k = (((np.floor(u / cell) + np.floor(v / cell)) % 2) == 0)[..., None]
    pf.put(b, m, np.where(k, np.array(c1, np.float32), np.array(c2, np.float32)), alpha=alpha)


def _checker_ring(pf, B, cx, cy, r0, r1, n=28):
    np = B.np
    b, d, ox, oy = pf.disc_field(cx, cy, r1 + 1)
    ang = np.arctan2(oy, ox)
    k = ((np.floor(ang / (2 * np.pi) * n) + np.floor((d - r0) / ((r1 - r0) / 2))) % 2 == 0)[..., None]
    col = np.where(k, np.array([245, 245, 245], np.float32), np.array([22, 22, 26], np.float32))
    pf.put(b, pf.cov(d, r1) * (1 - pf.cov(d, r0)), col, alpha=0.92)
    pf.put(b, pf.cov(d, r0), (150, 92, 60), alpha=0.85)            # copper podium
    pf.put(b, pf.cov(np.abs(d - r1), 0.6), (16, 12, 14))


def _floodlight(pf, B, x, y, flip=1):
    np = B.np
    # light cone towards the table centre
    tip = (x, y)
    a, c = (x + flip * 70, y + 70), (x + flip * 20, y + 90)
    b, m = pf.poly_mask([tip, a, c])
    xx, yy = pf.grid(b)
    fade = np.clip(1 - np.hypot(xx - x, yy - y) / 110, 0, 1)
    pf.add(b, m * fade * 0.35, (255, 240, 200))
    # pylon + lamp head
    b, m = pf.poly_mask([(x - 1.2, y), (x + 1.2, y), (x + 2.5, y + 40), (x - 2.5, y + 40)])
    pf.put(b, m, (150, 150, 160))
    b, m = pf.poly_mask([(x - 7, y - 4), (x + 7, y - 4), (x + 7, y + 3), (x - 7, y + 3)])
    pf.put(b, m, (40, 40, 48))
    for i in range(4):
        bb, dd, _, _ = pf.disc_field(x - 5.2 + i * 3.5, y - 0.5, 1.6)
        pf.put(bb, pf.cov(dd, 1.4), (255, 250, 220))


def _grandstand(pf, B, x0, x1, y0, y1, seed=3):
    np = B.np
    rng = np.random.default_rng(seed)
    b, m = pf.poly_mask([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    xx, yy = pf.grid(b)
    rows = ((yy - y0) % 6.0 < 1.0)[..., None]
    pf.put(b, m, np.where(rows, np.array([70, 70, 84], np.float32), np.array([36, 40, 56], np.float32)), alpha=0.8)
    cols = [(255, 200, 80), (240, 80, 70), (120, 200, 255), (250, 250, 250), (255, 140, 60)]
    for i in range(int((x1 - x0) * (y1 - y0) / 14)):
        cx, cy = rng.uniform(x0 + 1, x1 - 1), y0 + 3 + 6 * rng.integers(0, int((y1 - y0) / 6))
        bb, dd, _, _ = pf.disc_field(cx, cy, 1.3)
        pf.put(bb, pf.cov(dd, 0.9), cols[i % len(cols)], alpha=0.9)


def _tyre_stack(pf, B, x, y, n=3):
    for i in range(n):
        cx, cy = x + (i - (n - 1) / 2) * 6.5, y
        b, d, _, _ = pf.disc_field(cx, cy, 3.6)
        pf.put(b, pf.cov(d, 3.3), (24, 24, 28))
        pf.put(b, pf.cov(B.np.abs(d - 2.2), 0.45), (110, 110, 120))
        pf.put(b, pf.cov(d, 1.1), (200, 60, 40))


def _oval_track(pf, B, cx, cy, rx, ry, w=8.0):
    np = B.np
    b = pf.box(cx - rx - w, cy - ry - w, cx + rx + w, cy + ry + w, 2)
    xx, yy = pf.grid(b)
    # distance to the ellipse (approximate, good for a printed band)
    q = np.hypot((xx - cx) / rx, (yy - cy) / ry)
    dist = (q - 1.0) * (rx * ry) / np.maximum(np.hypot((xx - cx) * ry / rx, (yy - cy) * rx / ry), 1e-3) * q
    band = pf.cov(np.abs(dist), w / 2)
    pf.put(b, band, (44, 44, 50), alpha=0.9)
    ang = np.arctan2((yy - cy) / ry, (xx - cx) / rx)
    dash = (((ang / (2 * np.pi) * 36) % 1) < 0.5).astype(np.float32)
    pf.put(b, pf.cov(np.abs(dist), 0.5) * dash, (245, 245, 235), alpha=0.9)
    for sgn in (-1, 1):       # red / white kerbs on both edges
        kerb = pf.cov(np.abs(dist - sgn * (w / 2 + 0.9)), 0.9)
        kc = (((ang / (2 * np.pi) * 48) % 1) < 0.5)[..., None]
        pf.put(b, kerb, np.where(kc, np.array([230, 40, 40], np.float32), np.array([240, 240, 240], np.float32)))
    # chequered start / finish line across the bottom of the oval
    _checker_poly(pf, B, [(cx - 2, cy + ry - w / 2), (cx + 4, cy + ry - w / 2), (cx + 4, cy + ry + w / 2), (cx - 2, cy + ry + w / 2)], cell=2.0)


def paint(pf, B):
    G = B.G
    np = B.np
    # --- top: floodlit night sky, grandstand with the crowd behind the bumpers
    B.stars_sky(pf, 20, 18, 300, 120, 70, 23)
    _grandstand(pf, B, 84, 236, 92, 116)
    _floodlight(pf, B, 52, 92, 1)
    _floodlight(pf, B, 248, 92, -1)
    # --- mid: copper sunburst behind the pace car, chequered podium
    B.sunburst(pf, G.TOWER[0], G.TOWER[1] + 12, 20, 150, 32, (245, 140, 60), (120, 50, 36), y_clip=(196, 352))
    _checker_ring(pf, B, G.TOWER[0], G.TOWER[1], 21, 27)
    for x, y, n in ((112, 352, 3), (72, 404, 2), (200, 446, 3), (104, 446, 2)):
        _tyre_stack(pf, B, x, y, n)
    # paddock garage door art beside the paddock hole
    b, m = pf.poly_mask([(256, 336), (282, 336), (282, 362), (256, 362)])
    xx, yy = pf.grid(b)
    slat = ((yy % 3.0) < 1.6)[..., None]
    pf.put(b, m, np.where(slat, np.array([200, 120, 70], np.float32), np.array([120, 66, 40], np.float32)), alpha=0.9)
    # --- lower centre: oval race track with the chrome COPPER SPEEDWAY logo inside
    B.sunburst(pf, 130, 432, 0, 70, 20, (40, 140, 90), (24, 90, 60), y_clip=(380, 480), alpha=0.6)
    _oval_track(pf, B, 130, 432, 54, 30)
    # --- corners: chequered flags; start grid lights across the bonus row
    _checker_poly(pf, B, [(30, 530), (94, 574), (94, 628), (30, 628)], cell=6.0, alpha=0.5, ang=12)
    _checker_poly(pf, B, [(270, 530), (206, 574), (206, 628), (270, 628)], cell=6.0, alpha=0.5, ang=-12)
    for i in range(5):
        x = 110 + i * 20
        b, m = pf.poly_mask([(x - 7, 511), (x + 7, 511), (x + 7, 525), (x - 7, 525)])
        pf.put(b, m, (22, 22, 26), alpha=0.9)
        for k in range(2):
            bb, dd, _, _ = pf.disc_field(x - 3 + 6 * k, 518, 2.6)
            pf.put(bb, pf.cov(dd, 2.2), (255, 60, 40) if i < 4 else (90, 255, 110))
    B.inlane_art(pf)
    for i in range(3):
        B.sunburst(pf, (60, 160, 250)[i], (36, 30, 40)[i], 0, 14, 12, (255, 220, 140), (60, 120, 120), alpha=0.35)
    B.printed_text(pf, "COPPER", 12, 130, 422, spacing=0.6, glow=(255, 140, 60), grad=B.CHROME, outline=(30, 10, 4))
    B.printed_text(pf, "SPEEDWAY", 9, 130, 442, spacing=0.6, glow=(255, 220, 120), grad=B.CHROME, outline=(30, 10, 4))
    # --- shot labels (big, readable)
    lab = dict(col=(255, 238, 196), outline=(16, 4, 24))
    B.printed_text(pf, "CHICANE", 4.4, 68, 382, angle=90, **lab)
    B.printed_text(pf, "BANKING", 4.4, 202, 340, angle=80, **lab)
    B.printed_text(pf, "ORBIT", 5, 24, 254, angle=90, col=(255, 240, 120))
    B.printed_text(pf, "ORBIT", 5, 277, 254, angle=-90, col=(255, 240, 120))
    B.printed_text(pf, "GARAGE", 3.6, 48, 318, col=(255, 170, 235))
    B.printed_text(pf, "PIT STOP", 4.0, 122, 300, col=(160, 255, 170))
    B.printed_text(pf, "PADDOCK", 3.6, 268, 370, col=(255, 170, 235))
    B.printed_text(pf, "TURBO", 4.2, 242, 248, angle=-90, col=(255, 140, 120))
    B.printed_text(pf, "N.O.S.", 4.0, 212, 405, angle=36, col=(130, 236, 255))
    B.printed_text(pf, "P I T S", 4.2, 59, 247, angle=90, col=(255, 230, 120))
    B.printed_text(pf, "LAPS", 3.0, 127, 286, col=(255, 255, 255))
    B.printed_text(pf, "STRAIGHT", 3.4, 176, 364, angle=-20, col=(255, 255, 255))
    B.printed_text(pf, "SHOOT AGAIN", 4, 150, 566, col=(255, 170, 150))
    B.printed_text(pf, "EXTRA BALL", 4, 150, 504, col=(255, 214, 150))
    B.printed_text(pf, "BONUS MULTIPLIER", 3.4, 150, 482, col=(255, 214, 150))
    B.printed_text(pf, "KICKBACK", 3.6, 19, 518, angle=90, col=(150, 255, 160))
    B.printed_text(pf, "JACKPOT", 4.4, 150, 397, col=(255, 255, 255))
    B.printed_text(pf, "LOCK", 3.6, 270, 420, col=(255, 170, 235))
    B.printed_text(pf, "SUPER", 3.2, 150, 358, col=(255, 214, 120))


def overlay(ov, B):
    """the pace car on its podium (raised toy, top-down, nose up-table)."""
    np, S, G = B.np, B.S, B.G
    cx, top, bot = G.TOWER[0], 226.0, 273.0
    # tyres first (stick out of the body sides)
    for ty in (236.0, 262.0):
        for sx in (-1, 1):
            b, m = ov.poly_mask([(cx + sx * 7, ty - 4.5), (cx + sx * 11, ty - 4.5), (cx + sx * 11, ty + 4.5), (cx + sx * 7, ty + 4.5)])
            xx, yy = ov.grid(b)
            tread = (0.75 + 0.25 * ((yy % 1.6) < 0.8))[..., None]
            ov.put(b, m, np.array([30, 30, 34], np.float32) * tread, ht=np.full_like(m, 7 * S), spec=0.3, shin=0.4)
    # body: rounded wedge, copper-red, shaded as a rounded hull
    pts = [(cx - 1.5, top - 5), (cx + 1.5, top - 5), (cx + 8, top + 7), (cx + 9, top + 22), (cx + 8.5, bot - 4), (cx + 6, bot),
           (cx - 6, bot), (cx - 8.5, bot - 4), (cx - 9, top + 22), (cx - 8, top + 7)]
    b, m = ov.poly_mask(pts)
    xx, yy = ov.grid(b)
    u = np.clip((xx - cx) / 9.0, -1, 1)
    roundv = np.sqrt(np.clip(1 - u * u, 0, 1))
    lit = (0.55 + 0.55 * roundv - 0.25 * u)[..., None]
    base = np.array([205, 70, 40], np.float32) * np.ones_like(lit)
    stripe = (np.abs(xx - cx) < 1.6)[..., None]
    base = np.where(stripe, np.array([245, 245, 245], np.float32), base)
    cab = ((yy > top + 12) & (yy < top + 30) & (np.abs(xx - cx) < 6.2))[..., None]
    base = np.where(cab, np.array([30, 40, 60], np.float32), base)           # glass canopy
    ov.put(b, m, np.clip(base * lit, 0, 255), ht=(10 + 6 * roundv) * S, spec=0.9, shin=0.85)
    # roof light bar + rear spoiler
    for k, col in ((-1, (255, 140, 40)), (1, (80, 160, 255))):
        bb, dd, _, _ = ov.disc_field(cx + k * 3.2, top + 21, 1.8)
        ov.put(bb, ov.cov(dd, 1.6), col, ht=np.full_like(dd, 18 * S), spec=1.0, shin=0.9)
    ov.tube([(cx - 10, bot - 1.5), (cx + 10, bot - 1.5)], 1.3, "chrome", (60, 60, 70), height=2 * S, z=14)
    # start number roundel on the bonnet
    bb, dd, _, _ = ov.disc_field(cx, top + 7, 2.8)
    ov.put(bb, ov.cov(dd, 2.6), (250, 250, 250), ht=np.full_like(dd, 15 * S))
    bb, dd, _, _ = ov.disc_field(cx, top + 7, 1.2)
    ov.put(bb, ov.cov(dd, 1.0), (20, 20, 24), ht=np.full_like(dd, 15.5 * S))
