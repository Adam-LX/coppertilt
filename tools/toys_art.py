"""Per-table toys art (turntable sprites, magnets, VUK launch tubes, loop wires).

Called from build_table.py:  paint(pf, B)   - printed / sunk parts on the playfield
                             overlay(ov, B) - raised parts (tubes) on the ramp layer
                             sprites(B)     - rotating sprites (turntables), saved to hd/
Everything is procedural and original.
"""
import math
import os

import numpy as np

from mf_paint import Img, smooth_noise


def _horse(sp, cx, cy, ang, coat, saddle, S):
    """a carousel horse seen from above, nose pointing along ang (rad)."""
    ca, sa = math.cos(ang), math.sin(ang)

    def tf(u, v):
        return (cx + u * ca - v * sa, cy + u * sa + v * ca)
    b, d, ox, oy = sp.disc_field(cx, cy, 9.0)
    u = ox * ca + oy * sa
    v = -ox * sa + oy * ca
    body = np.hypot(u / 4.6, v / 1.9)
    neck = np.hypot((u - 4.6) / 2.6, v / 1.1)
    head = np.hypot((u - 7.0) / 1.9, v / 1.25)
    tail = np.hypot((u + 5.6) / 1.8, (v - 0.4 * np.sin(u * 2.0)) / 0.7)
    f = np.minimum(np.minimum(body, neck), np.minimum(head, tail))
    m = np.clip((1.0 - f) * 3.0 * S / 4.0, 0, 1)
    sp.put(b, np.clip((1.18 - f) * 3.0, 0, 1), (22, 10, 26), alpha=0.85)        # dark outline
    lit = np.clip(1.05 - 0.35 * np.clip(f, 0, 1) - 0.06 * (ox + oy), 0.5, 1.3)[..., None]
    sp.put(b, m, np.asarray(coat, np.float32) * lit, ht=(5.5 - 2.5 * np.clip(f, 0, 1)) * S, spec=0.85, shin=0.8)
    mane = np.clip((0.35 - np.abs(v)) * 4, 0, 1) * (u > 2.4) * (u < 7.2) * (f < 1.0)
    sp.put(b, mane, (250, 190, 70), ht=np.full_like(d, 6.0 * S))
    sad = np.clip((1.0 - np.hypot(u / 2.0, v / 2.05)) * 4, 0, 1)
    sp.put(b, sad, np.asarray(saddle, np.float32), ht=np.full_like(d, 6.2 * S), spec=0.9, shin=0.85)
    sp.dome(cx, cy, 1.25, "gold", (255, 214, 100), height=2.0 * S, z=6.5)       # the brass pole


def sprite_carousel(B, d):
    """rotating carousel platform: planked deck, gold bulb rim, six horses, brass hub."""
    S = B.S
    r = float(d["r"])
    R = r + 2.0
    sp = Img(R * 2, R * 2, S, alpha=True)
    c = R
    b, dd, ox, oy = sp.disc_field(c, c, r + 1.5)
    ang = np.arctan2(oy, ox)
    # deck: radial planks with grain, darker joints
    n = 36
    plank = ((ang / (2 * np.pi) + 0.5) * n) % 1.0
    grain = smooth_noise(b[3] - b[2], b[1] - b[0], 3, 91)
    wood = np.array([176, 104, 52], np.float32) * (0.78 + 0.32 * grain)[..., None]
    wood = np.where((plank < 0.06)[..., None], wood * 0.45, wood)
    t = np.clip(dd / r, 0, 1)
    wood *= (1.08 - 0.25 * t)[..., None]
    sp.put(b, sp.cov(dd, r), wood, ht=np.full_like(dd, 2.0 * S), spec=0.55, shin=0.6)
    # painted rings on the deck: red/cream scallop band + gold pinstripes
    band = (dd > r * 0.74) & (dd < r * 0.86)
    seg = ((ang / (2 * np.pi) + 0.5) * 24).astype(int) % 2
    bc = np.where(seg[..., None] == 0, np.array([214, 36, 64], np.float32), np.array([250, 228, 176], np.float32))
    sp.put(b, band.astype(np.float32), bc, ht=np.full_like(dd, 2.4 * S), spec=0.8, shin=0.8)
    for rr in (r * 0.74, r * 0.86, r * 0.30):
        sp.put(b, sp.cov(np.abs(dd - rr), 0.45), (255, 214, 110), ht=np.full_like(dd, 2.6 * S), spec=1.0, shin=0.9)
    # rim: red skirt with gold bulbs
    rim = sp.cov(np.abs(dd - (r - 1.4)), 1.4)
    sp.put(b, rim, np.array([170, 20, 44], np.float32) * (1.1 - 0.3 * np.clip(-(ox + oy) / r, -1, 1))[..., None],
           ht=np.full_like(dd, 3.0 * S), spec=0.8, shin=0.7)
    for i in range(30):
        a = i * 2 * math.pi / 30
        sp.dome(c + math.cos(a) * (r - 1.4), c + math.sin(a) * (r - 1.4), 0.95, "plastic",
                (255, 244, 200) if i % 2 else (255, 176, 70), height=1.2 * S, z=3.0)
    # horses (alternating coats), noses pointing clockwise (the platform turns clockwise)
    coats = [(250, 246, 236), (60, 46, 58), (200, 204, 214), (250, 246, 236), (150, 90, 50), (200, 204, 214)]
    saddles = [(220, 30, 60), (40, 160, 230), (250, 190, 40), (130, 50, 200), (40, 200, 110), (230, 90, 30)]
    for i in range(6):
        a = math.radians(30 + i * 60)
        hr = r * 0.58
        _horse(sp, c + math.cos(a) * hr, c + math.sin(a) * hr, a + math.pi / 2, coats[i], saddles[i], S)
    # brass hub with a painted crown
    hb, hd, hox, hoy = sp.disc_field(c, c, r * 0.24)
    ha = np.arctan2(hoy, hox)
    star = np.abs(((ha / (2 * np.pi) * 8) % 1) - 0.5) < 0.22
    sp.put(hb, sp.cov(hd, r * 0.24), np.where(star[..., None], np.array([214, 36, 64], np.float32),
                                              np.array([40, 40, 120], np.float32)), ht=np.full_like(hd, 3.0 * S))
    sp.dome(c, c, r * 0.13, "gold", (255, 210, 90), height=3.0 * S, z=3.0)
    sp.save(os.path.join(B.HD, d["name"] + ".png"), alpha=True, normal_path=os.path.join(B.HD, d["name"] + "_n.png"),
            normal_strength=0.8)


def sprite_wheel(B, d):
    """rotating chrome hubcap / tyre turntable (speedway style)."""
    S = B.S
    r = float(d["r"])
    R = r + 2.0
    sp = Img(R * 2, R * 2, S, alpha=True)
    c = R
    b, dd, ox, oy = sp.disc_field(c, c, r + 1.5)
    ang = np.arctan2(oy, ox)
    tread = (((ang / (2 * np.pi)) * 40) % 1 < 0.5) & (dd > r * 0.8)
    sp.put(b, sp.cov(dd, r), np.where(tread[..., None], np.array([30, 30, 34], np.float32),
                                      np.array([52, 52, 58], np.float32)), ht=np.full_like(dd, 3 * S), spec=0.3)
    spoke = np.abs(((ang / (2 * np.pi) * 5) % 1) - 0.5) < 0.12
    sp.put(b, (dd < r * 0.78) * 1.0, np.where(spoke[..., None], np.array([230, 230, 240], np.float32),
                                              np.array([90, 92, 104], np.float32)), ht=np.full_like(dd, 3.4 * S), spec=1.0, shin=0.9)
    sp.dome(c, c, r * 0.2, "chrome", (240, 240, 250), height=2 * S, z=3.4)
    sp.save(os.path.join(B.HD, d["name"] + ".png"), alpha=True, normal_path=os.path.join(B.HD, d["name"] + "_n.png"))


def magnet(pf, B, m):
    """sunk electro-magnet: copper coil windings under a chrome pole piece, hazard ring + caption."""
    S = B.S
    x, y = m["pos"]
    r = float(m["r"]) + 2.0
    b, d, ox, oy = pf.disc_field(x, y, r + 4)
    ang = np.arctan2(oy, ox)
    hz = (((ang / (2 * np.pi)) * 16) % 1 < 0.5)
    pf.put(b, pf.cov(np.abs(d - (r + 2.4)), 1.6), np.where(hz[..., None], np.array([255, 200, 40], np.float32),
                                                           np.array([24, 22, 30], np.float32)), alpha=0.95)
    wind = 0.6 + 0.4 * np.cos(d * 2 * math.pi / 1.1)
    copper = np.array([214, 120, 60], np.float32) * wind[..., None]
    pf.put(b, pf.cov(d, r), copper, ht=np.full_like(d, -1.0 * S), spec=1.0, shin=0.9)
    pf.put(b, pf.cov(np.abs(d - r), 0.5), (30, 20, 20))
    pf.dome(x, y, r * 0.42, "chrome", (230, 232, 242), height=1.0 * S, flat=0.5)
    label = m.get("label")
    if label:
        B.printed_text(pf, label, 3.2, x, y + r + 6.5, col=(150, 210, 255), outline=(8, 8, 30))


def vuk_pad(pf, B, h):
    """VUK scoop: chrome cup + arrow decal around the hole."""
    x, y = h["pos"]
    b, d, ox, oy = pf.disc_field(x, y, 14)
    ang = np.arctan2(oy, ox)
    ray = (np.abs(((ang / (2 * np.pi)) * 12) % 1 - 0.5) < 0.18) & (d > 10) & (d < 14)
    pf.put(b, ray * 1.0, (255, 140, 40), alpha=0.85)


def tube(ov, B, rp):
    """clear launch tube (VUK habitrail): translucent plastic with chrome rings, glowing core line."""
    S = B.S
    path = [tuple(p) for p in rp["path"]]
    hw = 6.0
    b, d, ox, oy, T = ov.line_field(path, hw + 2)
    across = np.clip(d / hw, 0, 1)
    m = ov.cov(d, hw)
    prof = np.sqrt(np.clip(1 - across ** 2, 0, 1))
    col = np.array([70, 200, 255], np.float32) * (0.6 + 0.5 * (1 - prof))[..., None]     # edges denser (fresnel)
    ov.put(b, m, col, ht=(10 + 4 * prof) * S, spec=1.0, shin=0.95, alpha=0.30 + 0.40 * across)
    ov.put(b, ov.cov(np.abs(across - 0.0), 0.12) * m, (150, 255, 255), alpha=0.5)          # neon core strip
    ov.put(b, ov.cov(np.abs(d - (hw - 0.6)), 0.55), (235, 245, 255), ht=np.full_like(d, 12 * S), alpha=0.8)
    ov.put(b, ov.cov(np.abs(across - 0.38), 0.07) * m, (255, 255, 255), alpha=0.75)    # long highlight
    acc = 0.0
    for a, c in zip(path, path[1:]):
        acc += math.dist(a, c)
        if acc >= 16:
            acc = 0.0
            nx, ny = c[1] - a[1], a[0] - c[0]
            L = math.hypot(nx, ny) or 1
            nx, ny = nx / L, ny / L
            ov.tube([(c[0] - nx * (hw + 0.6), c[1] - ny * (hw + 0.6)), (c[0] + nx * (hw + 0.6), c[1] + ny * (hw + 0.6))],
                    0.9, "chrome", (225, 228, 240), height=1.5 * S, z=11)


def loop_insert(pf, B, c):
    """printed target ring + caption under a loop-the-loop wire."""
    x, y, r = c
    b, d, ox, oy = pf.disc_field(x, y, r + 5)
    ang = np.arctan2(oy, ox)
    chk = ((((ang / (2 * np.pi)) * 20) % 1 < 0.5) ^ (d > r)).astype(np.float32)
    ring = pf.cov(np.abs(d - r), 2.6)
    pf.put(b, ring, np.where(chk[..., None] > 0, np.array([245, 245, 240], np.float32),
                             np.array([20, 20, 24], np.float32)), alpha=0.9)
    pf.put(b, pf.cov(d, r - 3.0), (255, 120, 30), alpha=0.35)
    B.printed_text(pf, "LOOP", 3.6, x, y, col=(255, 230, 120), outline=(40, 10, 0))


def paint(pf, B):
    G = B.G
    for rp in G.RAMPS:
        if rp.get("loop_c"):
            loop_insert(pf, B, rp["loop_c"])
    for m in getattr(G, "MAGNETS", []):
        magnet(pf, B, m)
    for h in G.HOLES:
        if h.get("vuk"):
            vuk_pad(pf, B, h)


def overlay(ov, B):
    for rp in B.G.RAMPS:
        if rp.get("art") == "tube":
            tube(ov, B, rp)


def sprites(B):
    for d in getattr(B.G, "DISCS", []):
        {"carousel": sprite_carousel, "wheel": sprite_wheel}[d.get("art", "carousel")](B, d)


def sprite_names(G):
    return [d["name"] for d in getattr(G, "DISCS", [])]
