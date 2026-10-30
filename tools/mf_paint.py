"""High-resolution painting kit (logical coordinates, ART scale S pixels per unit).

Every primitive writes albedo (rgb), coverage (a), height (ht, in px) and specular
(spec 0..1, shin 0..1). Normal maps are derived from height; ambient occlusion and
contact shadows from height are baked softly into albedo. No palette, no dither.
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_BLACK = "/nix/store/2y3pp9j22paigsnwr7x6857b5n8s5chi-nerd-fonts-noto-3.5.0/share/fonts/truetype/NerdFonts/Noto/NotoSansNerdFont-ExtraCondensedBlack.ttf"
FONT_WIDE = "/etc/profiles/per-user/adam/share/fonts/truetype/NerdFonts/JetBrainsMono/JetBrainsMonoNerdFont-ExtraBold.ttf"
_fc = {}


def font(px, wide=False):
    key = (int(px), wide)
    if key not in _fc:
        p = FONT_WIDE if wide else FONT_BLACK
        _fc[key] = ImageFont.truetype(p, int(px)) if os.path.exists(p) else ImageFont.load_default()
    return _fc[key]


def _box1(m, r, axis):
    if r < 1:
        return m
    pad = [(0, 0)] * m.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(m, pad, mode="edge"), axis=axis, dtype=np.float64)
    n = m.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def blur(m, r):
    """~gaussian (3x box) blur with sigma ~ r (pixels)."""
    if r <= 0.5:
        return m
    br = max(1, int(round(r * 0.9)))
    out = m.astype(np.float32)
    for _ in range(3):
        out = _box1(_box1(out, br, 0), br, 1)
    return out


def smooth_noise(w, h, cell, seed):
    r = np.random.default_rng(seed)
    small = r.random((h // cell + 3, w // cell + 3)).astype(np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8)).resize(((w // cell + 3) * cell, (h // cell + 3) * cell), Image.BICUBIC)
    return np.asarray(im, np.float32)[:h, :w] / 255.0


class Img:
    def __init__(self, lw, lh, S, alpha=False, base_ht=0.0):
        self.S = S
        self.w, self.h = int(lw * S), int(lh * S)
        self.rgb = np.zeros((self.h, self.w, 3), np.float32)
        self.a = np.zeros((self.h, self.w), np.float32) if alpha else np.ones((self.h, self.w), np.float32)
        self.ht = np.full((self.h, self.w), base_ht, np.float32)
        self.spec = np.zeros((self.h, self.w), np.float32)
        self.shin = np.full((self.h, self.w), 0.25, np.float32)

    # ---- boxes ---------------------------------------------------------
    def box(self, x0, y0, x1, y1, pad=2.0):
        S = self.S
        bx0 = max(0, int(math.floor((x0 - pad) * S)))
        by0 = max(0, int(math.floor((y0 - pad) * S)))
        bx1 = min(self.w, int(math.ceil((x1 + pad) * S)))
        by1 = min(self.h, int(math.ceil((y1 + pad) * S)))
        if bx1 <= bx0 or by1 <= by0:
            return None
        return (by0, by1, bx0, bx1)

    def grid(self, b):
        by0, by1, bx0, bx1 = b
        xs = (np.arange(bx0, bx1, dtype=np.float32) + 0.5) / self.S
        ys = (np.arange(by0, by1, dtype=np.float32) + 0.5) / self.S
        return np.meshgrid(xs, ys)

    # ---- compositing ------------------------------------------------------
    def put(self, b, m, rgb, ht=None, spec=None, shin=None, ht_mode="set", alpha=1.0):
        """m: local coverage, rgb: colour or local array, ht: local height or scalar."""
        if b is None:
            return
        by0, by1, bx0, bx1 = b
        m = np.clip(m, 0, 1).astype(np.float32) * alpha
        sl = (slice(by0, by1), slice(bx0, bx1))
        rgb = np.asarray(rgb, np.float32)
        self.rgb[sl] = self.rgb[sl] * (1 - m[..., None]) + rgb * m[..., None]
        self.a[sl] = self.a[sl] + (1 - self.a[sl]) * m
        if ht is not None:
            h = np.asarray(ht, np.float32)
            if ht_mode == "set":
                self.ht[sl] = self.ht[sl] * (1 - m) + h * m
            elif ht_mode == "max":
                self.ht[sl] = np.where(m > 0.5, np.maximum(self.ht[sl], h), self.ht[sl] * (1 - m) + np.maximum(self.ht[sl], h) * m)
            elif ht_mode == "add":
                self.ht[sl] = self.ht[sl] + h * m
        if spec is not None:
            self.spec[sl] = self.spec[sl] * (1 - m) + np.float32(spec) * m
        if shin is not None:
            self.shin[sl] = self.shin[sl] * (1 - m) + np.float32(shin) * m

    def mul(self, b, m, f):
        by0, by1, bx0, bx1 = b
        sl = (slice(by0, by1), slice(bx0, bx1))
        m = np.clip(m, 0, 1)[..., None]
        self.rgb[sl] = self.rgb[sl] * (1 - m * (1 - np.asarray(f, np.float32)))

    def add(self, b, m, rgb):
        by0, by1, bx0, bx1 = b
        sl = (slice(by0, by1), slice(bx0, bx1))
        self.rgb[sl] = self.rgb[sl] + np.clip(m, 0, None)[..., None] * np.asarray(rgb, np.float32)

    # ---- PIL masks ---------------------------------------------------------
    def pil_mask(self, b, draw_fn, ss=2):
        """draw_fn(draw, tf) with tf(x,y)->(px,py) in a supersampled local L image."""
        by0, by1, bx0, bx1 = b
        S = self.S * ss
        im = Image.new("L", ((bx1 - bx0) * ss, (by1 - by0) * ss), 0)
        d = ImageDraw.Draw(im)

        def tf(x, y):
            return (x * S - bx0 * ss, y * S - by0 * ss)
        draw_fn(d, tf, S)
        if ss > 1:
            im = im.resize((bx1 - bx0, by1 - by0), Image.LANCZOS)
        return np.asarray(im, np.float32) / 255.0

    def poly_mask(self, pts):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        b = self.box(min(xs), min(ys), max(xs), max(ys), 1.0)
        if b is None:
            return None, None
        m = self.pil_mask(b, lambda d, tf, S: d.polygon([tf(*p) for p in pts], fill=255))
        return b, m

    def text_mask(self, text, size, x, y, anchor="mm", wide=False, angle=0.0, spacing=0.0, stroke=0.0):
        """size in logical units (cap height ~ 0.72 size)."""
        S = self.S
        f = font(size * S * 2, wide)
        tmp = Image.new("L", (1, 1))
        dd = ImageDraw.Draw(tmp)
        if spacing:
            widths = [dd.textlength(c, font=f) for c in text]
            tw = sum(widths) + spacing * S * 2 * (len(text) - 1)
        else:
            tw = dd.textlength(text, font=f)
        th = size * S * 2 * 1.4
        pad = int(stroke * S * 2) + 8
        im = Image.new("L", (int(tw) + pad * 2, int(th) + pad * 2), 0)
        d = ImageDraw.Draw(im)
        if spacing:
            cx = pad
            for c, cw in zip(text, widths):
                d.text((cx, pad + th / 2), c, font=f, fill=255, anchor="lm", stroke_width=int(stroke * S * 2), stroke_fill=255)
                cx += cw + spacing * S * 2
        else:
            d.text((pad + tw / 2, pad + th / 2), text, font=f, fill=255, anchor="mm", stroke_width=int(stroke * S * 2), stroke_fill=255)
        bbox = im.getbbox()
        if bbox is None:
            return None, None
        im = im.crop(bbox)
        if angle:
            im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
        im = im.resize((max(1, im.width // 2), max(1, im.height // 2)), Image.LANCZOS)
        wl, hl = im.width / S, im.height / S
        if anchor == "mm":
            x0, y0 = x - wl / 2, y - hl / 2
        elif anchor == "lm":
            x0, y0 = x, y - hl / 2
        else:
            x0, y0 = x - wl, y - hl / 2
        bx0, by0 = int(round(x0 * S)), int(round(y0 * S))
        b = (max(0, by0), min(self.h, by0 + im.height), max(0, bx0), min(self.w, bx0 + im.width))
        arr = np.asarray(im, np.float32) / 255.0
        arr = arr[b[0] - by0:b[1] - by0, b[2] - bx0:b[3] - bx0]
        return b, arr

    # ---- distance fields -----------------------------------------------------
    def disc_field(self, cx, cy, r, pad=2.0):
        b = self.box(cx - r, cy - r, cx + r, cy + r, pad)
        if b is None:
            return None, None, None, None
        xx, yy = self.grid(b)
        ox, oy = xx - cx, yy - cy
        return b, np.hypot(ox, oy), ox, oy

    def line_field(self, pts, pad):
        """nearest-distance field (+ offsets + arclength t) of a polyline, computed per segment."""
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        b = self.box(min(xs), min(ys), max(xs), max(ys), pad)
        if b is None:
            return None, None, None, None, None
        by0, by1, bx0, bx1 = b
        D = np.full((by1 - by0, bx1 - bx0), 1e9, np.float32)
        OX = np.zeros_like(D)
        OY = np.zeros_like(D)
        T = np.zeros_like(D)
        acc = 0.0
        for a, c in zip(pts, pts[1:]):
            sb = self.box(min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1]), pad)
            L = math.dist(a, c)
            if sb is None or L < 1e-6:
                acc += L
                continue
            xx, yy = self.grid(sb)
            dx, dy = c[0] - a[0], c[1] - a[1]
            t = np.clip(((xx - a[0]) * dx + (yy - a[1]) * dy) / (L * L), 0, 1)
            ox, oy = xx - (a[0] + t * dx), yy - (a[1] + t * dy)
            d = np.hypot(ox, oy)
            sl = (slice(sb[0] - by0, sb[1] - by0), slice(sb[2] - bx0, sb[3] - bx0))
            cur = D[sl]
            m = d < cur
            D[sl] = np.where(m, d, cur)
            OX[sl] = np.where(m, ox, OX[sl])
            OY[sl] = np.where(m, oy, OY[sl])
            T[sl] = np.where(m, acc + t * L, T[sl])
            acc += L
        return b, D, OX, OY, T

    def cov(self, d, r):
        """anti-aliased coverage of d <= r."""
        return np.clip((r - d) * self.S + 0.5, 0, 1)

    # ---- materials -------------------------------------------------------------
    def tube(self, pts, hw, kind="chrome", base=(200, 200, 210), height=None, z=0.0, field=None, alpha=1.0):
        if field is None and len(pts) == 1:
            return self.dome(pts[0][0], pts[0][1], hw, kind, base, height, z, alpha=alpha)
        if field is None:
            field = self.line_field(pts, hw + 2)
        b, d, ox, oy, _ = field
        if b is None:
            return
        self._round(b, d, ox, oy, hw, kind, base, height, z, alpha)

    def dome(self, cx, cy, r, kind="plastic", base=(220, 60, 60), height=None, z=0.0, flat=0.0, alpha=1.0):
        b, d, ox, oy = self.disc_field(cx, cy, r)
        if b is None:
            return
        if flat:
            dd = np.where(d <= r, np.maximum(d - flat * r, 0) / (1 - flat) , d)
        else:
            dd = d
        self._round(b, dd, ox, oy, r, kind, base, height, z, alpha, cover_d=d)

    def _round(self, b, d, ox, oy, hw, kind, base, height, z, alpha, cover_d=None):
        S = self.S
        cd = d if cover_d is None else cover_d
        m = self.cov(cd, hw)
        t = np.clip(d / hw, 0, 1)
        prof = np.sqrt(np.clip(1 - t * t, 0, 1))
        h = (height if height is not None else hw * S) * prof + z * S
        nn = np.maximum(d, 1e-6)
        nx, ny = ox / nn * t, oy / nn * t
        nz = prof
        col = shade(nx, ny, nz, base, kind)
        sp, sh = MAT[kind]
        self.put(b, m, col, h, sp, sh, ht_mode="max", alpha=alpha)

    def finish(self, ao=True, shadow=True, ao_k=0.012, sh_off=(4.0, 6.0), sh_k=0.55):
        """bake AO + contact shadows from height into albedo."""
        S = self.S
        if ao:
            hb = blur(self.ht, 3 * S)
            occ = np.clip((hb - self.ht) * ao_k, 0, 0.55)
            self.rgb *= (1 - occ)[..., None]
        if shadow:
            dx, dy = int(sh_off[0] * S), int(sh_off[1] * S)
            hs = np.roll(np.roll(self.ht, dy, 0), dx, 1)
            hs[:dy] = 0
            hs[:, :dx] = 0
            cast = np.clip((hs - self.ht) / (6.0 * S), 0, 1)
            cast = blur(cast, 2.2 * S)
            self.rgb *= (1 - cast * sh_k)[..., None]

    def normal_map(self, strength=1.0, smooth=0.8):
        h = blur(self.ht, smooth * self.S / 4) if smooth else self.ht
        gy, gx = np.gradient(h)
        nx, ny, nz = -gx * strength, gy * strength, np.ones_like(h)
        L = np.sqrt(nx * nx + ny * ny + nz * nz)
        n = np.stack([nx / L, ny / L, nz / L], -1)
        return Image.fromarray(np.clip((n * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8), "RGB")

    def save(self, path, alpha=False, normal_strength=1.0, spec_path=None, normal_path=None):
        rgb = np.clip(self.rgb, 0, 255).astype(np.uint8)
        if alpha:
            a = np.clip(self.a * 255, 0, 255).astype(np.uint8)
            Image.fromarray(np.dstack([rgb, a]), "RGBA").save(path, optimize=True)
        else:
            Image.fromarray(rgb, "RGB").save(path, optimize=True)
        if normal_path:
            self.normal_map(normal_strength).save(normal_path, optimize=True)
        if spec_path:
            sp = np.clip(self.spec * 255, 0, 255).astype(np.uint8)
            shn = np.clip(self.shin * 255, 0, 255).astype(np.uint8)
            Image.fromarray(np.dstack([sp, sp, sp, shn]), "RGBA").save(spec_path, optimize=True)


# material: (specular, shininess)
MAT = {"chrome": (1.0, 0.9), "plastic": (0.7, 0.6), "rubber": (0.12, 0.15), "glass": (0.9, 0.8),
       "wood": (0.35, 0.45), "paint": (0.35, 0.5), "metal": (0.6, 0.5), "gold": (0.9, 0.75)}
KEY = np.array([-0.42, -0.62, 0.66], np.float32)
KEY /= np.linalg.norm(KEY)
HALF = KEY + np.array([0, 0, 1], np.float32)
HALF /= np.linalg.norm(HALF)


def env_color(nx, ny, nz):
    """fake room reflection for chrome: warm cabinet lights above, dark playfield below, purple sky."""
    up = -ny
    sky = np.stack([70 + 60 * nz, 40 + 40 * nz, 120 + 90 * nz], -1)
    horizon = np.clip(1 - np.abs(up - 0.15) * 6, 0, 1)[..., None]
    floor = np.clip(-up * 2, 0, 1)[..., None]
    col = sky * (1 - floor) + np.array([25, 18, 40], np.float32) * floor
    col = col * (1 - horizon) + np.array([255, 210, 170], np.float32) * horizon
    win = np.clip(1 - np.hypot(nx + 0.35, ny + 0.45) * 3.2, 0, 1)[..., None]   # softbox highlight
    return col + win * 255


def shade(nx, ny, nz, base, kind):
    base = np.asarray(base, np.float32)
    diff = np.clip(nx * KEY[0] + ny * KEY[1] + nz * KEY[2], 0, 1)[..., None]
    spec = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1)[..., None]
    if kind == "chrome":
        col = env_color(nx, ny, nz) * (base / 255.0) * 0.85 + spec ** 40 * 255
    elif kind == "gold":
        col = env_color(nx, ny, nz) * np.array([1.0, 0.78, 0.38]) * 0.9 + spec ** 30 * 230
    elif kind == "rubber":
        col = base * (0.35 + 0.65 * diff) + spec ** 8 * 40
    else:   # plastic / glass / paint / wood
        col = base * (0.30 + 0.75 * diff) + spec ** 24 * 200
    return np.clip(col, 0, 255)
