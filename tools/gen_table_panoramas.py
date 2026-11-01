#!/usr/bin/env python3
"""Generate distinct 480x270 OCS-style panoramic title backdrops for each table.

- assets/tables/midnight_funfair/panorama.png (Midnight carnival skyline)
- assets/tables/launch_pad/panorama.png      (Cape Canaveral spaceport at night)
- assets/tables/copper_speedway/panorama.png (Night Grand Prix racing circuit)
"""
import math
import os
import random
import shutil
import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 480, 270

def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, v))

def quantize_ocs(im):
    """Quantize to Amiga 12-bit (OCS 4-bits per channel: 0, 17, 34, ..., 255)."""
    arr = np.array(im, dtype=np.float32)
    # 4-bit quantize: 16 levels per channel
    arr[..., :3] = np.round(arr[..., :3] / 17.0) * 17.0
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")

def build_launch_pad_panorama():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(im)
    rng = random.Random(42)

    # 1. Sky gradient: deep cosmic blue-black to dusk violet horizon
    for y in range(H):
        t = y / float(H)
        if t < 0.72:
            st = t / 0.72
            r = int(6 + 34 * st + 24 * (st ** 2))
            g = int(8 + 26 * st + 16 * (st ** 2))
            b = int(24 + 56 * st + 28 * (st ** 2))
        else:
            st = (t - 0.72) / 0.28
            r = int(64 * (1 - st) + 18 * st)
            g = int(48 * (1 - st) + 24 * st)
            b = int(68 * (1 - st) + 36 * st)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # 2. Stars
    for _ in range(140):
        sx = rng.randint(0, W - 1)
        sy = rng.randint(0, int(H * 0.65))
        br = rng.randint(140, 255)
        im.putpixel((sx, sy), (br, br, min(255, br + 20), 255))
        if rng.random() < 0.2:
            im.putpixel((sx + 1, sy), (br // 2, br // 2, br // 2, 255))

    # 3. Rising ringed planet on the right
    px, py, pr = 380, 55, 26
    for dy in range(-pr - 8, pr + 9):
        for dx in range(-pr * 2, pr * 2 + 1):
            x, y = px + dx, py + dy
            if 0 <= x < W and 0 <= y < H:
                dist = math.hypot(dx, dy)
                # Planet disc
                if dist <= pr:
                    lum = max(0.0, min(1.0, 0.75 - 0.5 * (dx + dy) / pr))
                    band = 0.85 + 0.15 * math.sin((y - py) * 0.7)
                    cr = int((160 + 50 * band) * lum)
                    cg = int((190 + 55 * band) * lum)
                    cb = int((240 + 15 * band) * lum)
                    im.putpixel((x, y), (cr, cg, cb, 255))
                # Rings (inclined ellipse)
                ring_u = dx * 0.9 + dy * 0.4
                ring_v = -dx * 0.4 + dy * 0.9
                ring_d = math.hypot(ring_u, ring_v * 2.6)
                if pr * 1.25 <= ring_d <= pr * 1.85:
                    if dy > 0 or dist > pr: # in front or outside planet
                        alpha = math.sin((ring_d - pr * 1.25) / (pr * 0.6) * math.pi)
                        orig = im.getpixel((x, y))
                        rr = int(orig[0] * (1 - alpha * 0.7) + 210 * alpha * 0.7)
                        rg = int(orig[1] * (1 - alpha * 0.7) + 225 * alpha * 0.7)
                        rb = int(orig[2] * (1 - alpha * 0.7) + 255 * alpha * 0.7)
                        im.putpixel((x, y), (rr, rg, rb, 255))

    gy = int(H * 0.74) # ground horizon ~199

    # 4. Background mountains & Cape Canaveral horizon silhouette
    mount_pts = [(0, gy)]
    for i in range(0, W + 20, 20):
        mount_pts.append((i, gy - 8 - int(6 * math.sin(i * 0.03) + 4 * math.cos(i * 0.07))))
    mount_pts.append((W, gy))
    draw.polygon(mount_pts, fill=(28, 30, 48, 255))

    # Distant second launch pad (Pad B) at x=80
    draw.rectangle([76, gy - 42, 84, gy], fill=(36, 42, 60, 255))
    draw.polygon([(78, gy - 62), (82, gy - 62), (83, gy - 42), (77, gy - 42)], fill=(44, 52, 70, 255))
    draw.point((80, gy - 63), fill=(255, 60, 40, 255)) # red obstruction beacon

    # 5. Cryogenic fuel spheres & storage facilities on left (x=110..160)
    for cx, r, col in [(125, 18, (160, 170, 185)), (152, 14, (140, 150, 165))]:
        draw.ellipse([cx - r, gy - r * 2 + 3, cx + r, gy + 3], fill=(30, 34, 46, 255), outline=col, width=2)
        # sphere support legs
        draw.line([cx - r + 3, gy + 3, cx - r + 5, gy - r + 3], fill=col, width=1)
        draw.line([cx + r - 3, gy + 3, cx + r - 5, gy - r + 3], fill=col, width=1)
        draw.line([cx, gy + 3, cx, gy - r + 3], fill=col, width=1)
        # equator catwalk
        draw.line([cx - r, gy - r + 3, cx + r, gy - r + 3], fill=(210, 215, 230), width=1)

    # 6. High-gain telemetry radar dish on right (x=360)
    rx, ry = 350, gy - 16
    draw.polygon([(rx - 5, gy), (rx + 5, gy), (rx + 2, ry), (rx - 2, ry)], fill=(80, 90, 110, 255))
    # parabolic dish facing up-left
    draw.arc([rx - 24, ry - 30, rx + 16, ry + 10], 190, 350, fill=(190, 210, 235, 255), width=3)
    draw.line([rx - 6, ry - 10, rx - 18, ry - 22], fill=(240, 245, 255, 255), width=2)

    # 7. MAIN LAUNCH VEHICLE & GANTRY (Center, x=220..270)
    gx = 245
    # Launch pad concrete mount / flame trench table
    draw.rectangle([gx - 45, gy - 16, gx + 45, gy + 4], fill=(45, 50, 65, 255), outline=(130, 140, 160, 255))
    # Flame deflector glow under pad
    draw.ellipse([gx - 22, gy - 12, gx + 22, gy + 14], fill=(255, 120, 30, 180))

    # Giant Gantry Tower (left of rocket: x=205..224, climbs from gy-16 to gy-140)
    tx0, tx1, ty_top = gx - 36, gx - 18, gy - 146
    draw.rectangle([tx0, ty_top, tx1, gy - 16], fill=(40, 24, 22, 255), outline=(210, 60, 45, 255), width=2)
    # Gantry criss-cross trusses
    for yf in range(ty_top, gy - 16, 12):
        draw.line([tx0, yf, tx1, yf], fill=(225, 75, 55, 255), width=1)
        draw.line([tx0, yf, tx1, min(gy - 16, yf + 12)], fill=(180, 50, 40, 255), width=1)
        draw.line([tx1, yf, tx0, min(gy - 16, yf + 12)], fill=(180, 50, 40, 255), width=1)
    # Gantry top crane
    draw.rectangle([tx0 - 4, ty_top - 8, tx1 + 18, ty_top], fill=(225, 70, 50, 255))
    draw.point((tx0, ty_top - 9), fill=(255, 255, 255, 255))
    draw.point((tx1 + 16, ty_top - 9), fill=(255, 40, 20, 255)) # blinking red beacon

    # Umbilical swing arms reaching to rocket
    for arm_y in [ty_top + 28, ty_top + 60, ty_top + 95]:
        draw.line([tx1, arm_y, gx - 7, arm_y], fill=(180, 190, 205, 255), width=2)
        draw.line([tx1, arm_y + 3, gx - 9, arm_y + 3], fill=(120, 130, 145, 255), width=1)

    # ROCKET (Saturn-V / Falcon style multi-stage rocket stack at gx=245)
    # Boosters / First stage base (gx-11 to gx+11, height from gy-16 up to gy-65)
    draw.rectangle([gx - 11, gy - 65, gx + 11, gy - 16], fill=(235, 240, 248, 255))
    draw.rectangle([gx - 11, gy - 65, gx - 4, gy - 16], fill=(170, 180, 195, 255)) # shade
    draw.rectangle([gx + 3, gy - 65, gx + 11, gy - 16], fill=(255, 255, 255, 255)) # highlight
    # Stage roll pattern (black/white checker blocks)
    for bx, by in [(gx - 11, gy - 65), (gx + 1, gy - 53), (gx - 11, gy - 26), (gx + 1, gy - 38)]:
        draw.rectangle([bx, by, bx + 9, by + 11], fill=(25, 28, 36, 255))
    # Interstage ring
    draw.rectangle([gx - 10, gy - 71, gx + 10, gy - 65], fill=(35, 40, 50, 255))

    # Second stage (gy-71 up to gy-108)
    draw.rectangle([gx - 9, gy - 108, gx + 9, gy - 71], fill=(230, 235, 245, 255))
    draw.rectangle([gx - 9, gy - 108, gx - 3, gy - 71], fill=(170, 175, 190, 255))
    draw.line([gx, gy - 108, gx, gy - 71], fill=(255, 60, 40, 255), width=2) # red racing stripe / logo

    # Third stage / Service module (gy-108 up to gy-126)
    draw.rectangle([gx - 8, gy - 126, gx + 8, gy - 108], fill=(240, 242, 250, 255))
    # Command module cone (gy-126 up to gy-138)
    draw.polygon([(gx - 8, gy - 126), (gx + 8, gy - 126), (gx, gy - 140)], fill=(245, 245, 255, 255))
    # Launch Escape System (LES) tower tower at top (gy-140 up to gy-158)
    draw.line([gx, gy - 140, gx, gy - 158], fill=(220, 225, 235, 255), width=2)
    draw.point((gx, gy - 159), fill=(255, 50, 40, 255)) # red nose beacon

    # 8. Floodlights and Xenon Searchlight Beams cutting the night sky
    for fx, fa in [(60, -0.4), (185, -0.15), (315, 0.2), (430, 0.45)]:
        # Floodlight tower
        draw.polygon([(fx - 3, gy), (fx + 3, gy), (fx + 1, gy - 40), (fx - 1, gy - 40)], fill=(80, 85, 100, 255))
        draw.rectangle([fx - 5, gy - 44, fx + 5, gy - 40], fill=(255, 230, 160, 255))
        # Searchlight beam polygon into the sky
        bx0 = fx
        by0 = gy - 42
        beam_len = 220
        bx_t0 = fx + int(math.sin(fa - 0.05) * beam_len)
        bx_t1 = fx + int(math.sin(fa + 0.05) * beam_len)
        by_t = by0 - int(math.cos(fa) * beam_len)
        # Soft beam
        beam_mask = Image.new("L", (W, H), 0)
        bd = ImageDraw.Draw(beam_mask)
        bd.polygon([(bx0, by0), (bx_t0, by_t), (bx_t1, by_t)], fill=45)
        beam_col = Image.new("RGBA", (W, H), (140, 220, 255, 255))
        im.paste(beam_col, (0, 0), beam_mask)

    # 9. Concrete Apron / Foreground (gy to H)
    for y in range(gy, H):
        t = (y - gy) / float(H - gy)
        cr = int(32 + 20 * t)
        cg = int(36 + 24 * t)
        cb = int(48 + 26 * t)
        draw.line([(0, y), (W, y)], fill=(cr, cg, cb, 255))

    # Concrete expansion joints in perspective
    for vx in [-60, 40, 140, 245, 350, 450, 550]:
        draw.line([(gx + int((vx - gx) * 0.2), gy), (vx, H)], fill=(24, 26, 36, 255), width=1)
    for y in [gy + 14, gy + 34, gy + 56]:
        draw.line([(0, y), (W, y)], fill=(24, 26, 36, 255), width=1)

    # Yellow/Black Hazard stripes on the flame trench barrier
    hx0, hx1, hy0, hy1 = gx - 90, gx + 90, gy + 4, gy + 12
    draw.rectangle([hx0, hy0, hx1, hy1], fill=(40, 40, 40, 255))
    for sx in range(hx0, hx1 + 10, 8):
        draw.polygon([(sx, hy1), (sx + 4, hy1), (sx + 8, hy0), (sx + 4, hy0)], fill=(245, 190, 30, 255))

    return quantize_ocs(im)

def build_copper_speedway_panorama():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(im)
    rng = random.Random(1987)

    # 1. Sky: Stadium night floodlight haze (teal-black at top to dramatic twilight copper/amber at horizon)
    for y in range(H):
        t = y / float(H)
        if t < 0.70:
            st = t / 0.70
            r = int(12 + 75 * (st ** 2.2))
            g = int(24 + 48 * st + 30 * (st ** 2))
            b = int(36 + 28 * st - 10 * (st ** 2))
        else:
            st = (t - 0.70) / 0.30
            r = int(95 * (1 - st) + 24 * st)
            g = int(62 * (1 - st) + 26 * st)
            b = int(32 * (1 - st) + 28 * st)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    gy = int(H * 0.73) # 197

    # 2. Grandstands packed with fans across the skyline (x=0..W)
    # Background tier roof
    draw.polygon([(0, gy - 40), (W, gy - 40), (W, gy - 36), (0, gy - 36)], fill=(50, 56, 70, 255))
    # Stand structure tiers
    for tier_y in range(gy - 36, gy - 10, 4):
        draw.line([(0, tier_y), (W, tier_y)], fill=(40, 44, 56, 255), width=1)
        # People in team colors
        for px in range(0, W, 3):
            if rng.random() < 0.85:
                tc = rng.choice([
                    (230, 55, 45), (240, 190, 40), (45, 130, 230),
                    (240, 240, 245), (40, 180, 100), (220, 110, 40)
                ])
                draw.point((px, tier_y - 1), fill=tc + (255,))
                # Camera flashes
                if rng.random() < 0.015:
                    draw.ellipse([px - 2, tier_y - 3, px + 2, tier_y + 1], fill=(255, 255, 255, 255))

    # Grandstand support pillars
    for col_x in range(20, W, 40):
        draw.rectangle([col_x - 1, gy - 40, col_x + 1, gy - 10], fill=(28, 30, 40, 255))

    # 3. Pit Building & Race Control Tower (Left-Center: x=40..170)
    # 2-story glass/concrete pit garage
    draw.rectangle([40, gy - 38, 170, gy - 6], fill=(38, 42, 54, 255), outline=(170, 180, 195, 255), width=2)
    # Lit pit garage bays with race mechanics
    for bx in [46, 74, 102, 130]:
        draw.rectangle([bx, gy - 24, bx + 22, gy - 6], fill=(240, 245, 255, 255))
        draw.rectangle([bx + 2, gy - 22, bx + 20, gy - 6], fill=(255, 215, 120, 255)) # warm interior light
        # Silhouette of race car / tool cart in bay
        draw.rectangle([bx + 4, gy - 14, bx + 18, gy - 6], fill=(40, 40, 50, 255))

    # Digital Timing Leaderboard Tower at x=175
    draw.rectangle([170, gy - 85, 192, gy - 6], fill=(24, 26, 34, 255), outline=(210, 140, 40, 255), width=2)
    draw.rectangle([173, gy - 82, 189, gy - 74], fill=(255, 40, 20, 255)) # "POS" header
    # Digital LED positions
    draw.text((174, gy - 71), "1 07", fill=(255, 220, 40, 255))
    draw.text((174, gy - 61), "2 12", fill=(240, 240, 240, 255))
    draw.text((174, gy - 51), "3 03", fill=(255, 120, 40, 255))
    draw.text((174, gy - 41), "4 99", fill=(120, 220, 255, 255))
    draw.text((174, gy - 31), "5 24", fill=(80, 240, 120, 255))

    # 4. Start/Finish Overhead Gantry (spanning track at x=200..340)
    draw.line([210, gy - 70, 330, gy - 70], fill=(210, 215, 225, 255), width=4)
    draw.line([210, gy - 66, 330, gy - 66], fill=(140, 145, 155, 255), width=2)
    # Overhead checkered flag banner
    for cx in range(220, 320, 8):
        for cy in range(gy - 64, gy - 52, 6):
            col = (245, 245, 245) if ((cx // 8 + cy // 6) % 2 == 0) else (20, 20, 24)
            draw.rectangle([cx, cy, cx + 7, cy + 5], fill=col + (255,))
    # Start light pods (5 red lights)
    for lx in range(240, 300, 12):
        draw.rectangle([lx - 1, gy - 50, lx + 7, gy - 40], fill=(20, 20, 20, 255))
        draw.ellipse([lx + 1, gy - 48, lx + 5, gy - 42], fill=(255, 30, 20, 255)) # blazing red start lights

    # Support gantry pillars
    draw.rectangle([206, gy - 70, 212, gy - 6], fill=(160, 165, 175, 255))
    draw.rectangle([328, gy - 70, 334, gy - 6], fill=(160, 165, 175, 255))

    # 5. Massive Stadium Floodlight Gantries
    for fx, fa in [(30, -0.3), (195, -0.1), (345, 0.2), (450, 0.4)]:
        draw.line([fx, gy - 6, fx, gy - 110], fill=(170, 175, 190, 255), width=3)
        draw.rectangle([fx - 14, gy - 118, fx + 14, gy - 108], fill=(50, 55, 65, 255))
        for spot_x in range(fx - 12, fx + 14, 5):
            draw.rectangle([spot_x, gy - 116, spot_x + 3, gy - 110], fill=(255, 250, 210, 255))
        # Beam of light
        beam_mask = Image.new("L", (W, H), 0)
        bd = ImageDraw.Draw(beam_mask)
        beam_len = 230
        bx0 = fx
        by0 = gy - 112
        bx_t0 = fx + int(math.sin(fa - 0.08) * beam_len)
        bx_t1 = fx + int(math.sin(fa + 0.08) * beam_len)
        by_t = by0 + int(math.cos(fa) * beam_len)
        bd.polygon([(bx0, by0), (bx_t0, by_t), (bx_t1, by_t)], fill=50)
        beam_col = Image.new("RGBA", (W, H), (255, 245, 200, 255))
        im.paste(beam_col, (0, 0), beam_mask)

    # 6. Asphalt Race Track & Curbs in Perspective (gy to H)
    for y in range(gy - 6, H):
        t = (y - (gy - 6)) / float(H - (gy - 6))
        ar = int(24 + 18 * t)
        ag = int(26 + 20 * t)
        ab = int(32 + 22 * t)
        draw.line([(0, y), (W, y)], fill=(ar, ag, ab, 255))

    # Sweeping Red-and-White Racing Kerb (curving across the middle)
    kerb_pts = []
    for step in range(0, 101):
        st = step / 100.0
        # Curve from right to center-left
        kx = W * (0.95 - 0.70 * st - 0.15 * math.sin(st * math.pi))
        ky = (gy - 6) + (H - (gy - 6)) * (st ** 1.3)
        kerb_pts.append((kx, ky))

    for i in range(len(kerb_pts) - 1):
        p1 = kerb_pts[i]
        p2 = kerb_pts[i + 1]
        col = (235, 45, 40) if ((i // 4) % 2 == 0) else (245, 245, 250)
        draw.line([p1, p2], fill=col + (255,), width=6)

    # Infield grass (left of kerb)
    infield_poly = [(0, gy - 6)] + kerb_pts + [(0, H)]
    infield_mask = Image.new("L", (W, H), 0)
    idr = ImageDraw.Draw(infield_mask)
    idr.polygon(infield_poly, fill=255)
    grass_im = Image.new("RGBA", (W, H), (24, 75, 48, 255))
    im.paste(grass_im, (0, 0), infield_mask)

    # Grid start boxes (white rectangles in perspective)
    for i, (gx, gy_box) in enumerate([(270, gy + 14), (245, gy + 32), (280, gy + 52), (250, gy + 72)]):
        w_box = 32 + i * 8
        h_box = 10 + i * 3
        draw.rectangle([gx - w_box // 2, gy_box, gx + w_box // 2, gy_box + h_box], outline=(240, 245, 255, 255), width=2)
        # Racing cars on grid!
        car_col = [(230, 45, 35), (240, 180, 30), (40, 140, 235), (45, 200, 110)][i]
        draw.rectangle([gx - w_box // 3, gy_box + 2, gx + w_box // 3, gy_box + h_box - 2], fill=car_col + (255,))
        # Headlight beams
        draw.point((gx - w_box // 3 + 2, gy_box + 2), fill=(255, 255, 200, 255))
        draw.point((gx + w_box // 3 - 2, gy_box + 2), fill=(255, 255, 200, 255))

    return quantize_ocs(im)

def main():
    lp_dir = os.path.join(ROOT, "assets", "tables", "launch_pad")
    cs_dir = os.path.join(ROOT, "assets", "tables", "copper_speedway")
    mf_dir = os.path.join(ROOT, "assets", "tables", "midnight_funfair")

    os.makedirs(lp_dir, exist_ok=True)
    os.makedirs(cs_dir, exist_ok=True)
    os.makedirs(mf_dir, exist_ok=True)

    print("Generating Launch Pad panorama...")
    lp_pano = build_launch_pad_panorama()
    lp_path = os.path.join(lp_dir, "panorama.png")
    lp_pano.save(lp_path)
    print(f"Saved: {lp_path}")

    print("Generating Copper Speedway panorama...")
    cs_pano = build_copper_speedway_panorama()
    cs_path = os.path.join(cs_dir, "panorama.png")
    cs_pano.save(cs_path)
    print(f"Saved: {cs_path}")

    # Copy title_art to midnight_funfair panorama if not present
    mf_path = os.path.join(mf_dir, "panorama.png")
    art_path = os.path.join(ROOT, "assets", "art", "title_art.png")
    if os.path.exists(art_path):
        shutil.copyfile(art_path, mf_path)
        print(f"Copied {art_path} -> {mf_path}")

if __name__ == "__main__":
    main()
