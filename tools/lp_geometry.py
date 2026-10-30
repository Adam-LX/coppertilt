"""Launch Pad - geometry (original rocket-launch table; same cabinet/solver scale as Midnight Funfair).

Shots: GANTRY (left plastic ramp, U-turn to the left inlane), BOOSTER (right plastic ramp, U-turn to
the right inlane), LIFTOFF (wire from the upper flipper straight up past the rocket into the FUEL
lanes), CONTROL saucer, SILO + HANGAR holes (subway to CONTROL), orbits (spinner on the right).

Logical table units: 320 x 640 (ball radius 7.5, same scale as the Amiga references, so the
solver constants keep their meaning). v3 = dense ~620-unit relayout (visual reference review).
Art is painted at ART_SCALE x this (1280 x 2560 px).
Original layout; density modelled on research/../docs/research/table-density.md.
"""
import json, math, os

THEME = "lp_theme"
TITLE = "LAUNCH PAD"
TITLE_COLOR = (255, 190, 80)
LETTER_KEYS = ["lane_", "mars_", "stage_", "pad_"]
# night launch site: deep space blue -> dusk violet -> sodium orange pad -> concrete blue-grey
BASE_STOPS = [(0, (24, 34, 96)), (90, (40, 60, 150)), (176, (78, 64, 168)), (206, (120, 70, 150)),
              (290, (196, 104, 58)), (350, (180, 84, 70)), (440, (86, 88, 160)), (540, (62, 96, 170)),
              (640, (40, 56, 120))]
BLOCK_COLORS = [(210, 210, 220), (40, 110, 220), (230, 120, 30)]
SLING_COLORS = ((235, 120, 30), (40, 140, 235))
STANDUP_COLOR = (255, 90, 60)
BUMPER_COLORS = ((235, 110, 30), (30, 40, 110), (255, 150, 60), (240, 245, 255))
RAIL_RGB = (190, 225, 255)
BALL_ACCENT = (150, 150, 190)
GUIDE_SPOTS = [[47.5, 512.0], [252.5, 512.0], [18.5, 512.0], [281.5, 512.0], [24.0, 226.0], [277.0, 226.0]]

W, H = 320, 640
BALL_R = 7.5
SEGS = []      # [x1,y1,x2,y2,mat,onewayNx,onewayNy]
CIRCLES = []   # [x,y,r,mat,id]
RAILS = []     # wall polylines (painted as chrome / wood rails)
BLOCKS = []    # closed polygons painted as raised plastic (ramp bases, guides)


def seg(a, b, mat="wall", oneway=None):
    SEGS.append([round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2), mat,
                 0 if oneway is None else oneway[0], 0 if oneway is None else oneway[1]])


def poly(pts, mat="wall", rail=True, closed=False):
    pts = list(pts)
    if closed:
        pts = pts + [pts[0]]
    for a, b in zip(pts, pts[1:]):
        seg(a, b, mat)
    if rail:
        RAILS.append(pts)


def post(x, y, r=3.0, mat="rubber", name="post"):
    CIRCLES.append([x, y, r, mat, name])


def mirror(p):
    return (300.0 - p[0], p[1])


def catmull(pts, step=2.0):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        n = max(2, int(math.dist(p1, p2) / step))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    out.append(pts[-1])
    return out


# ---------------------------------------------------------------- cabinet
ARCH_C, ARCH_R = (161.0, 165.0), 151.0
arch = [(ARCH_C[0] + ARCH_R * math.cos(math.radians(a)), ARCH_C[1] + ARCH_R * math.sin(math.radians(a)))
        for a in range(180, 361, 4)]
BOT = 636.0
OUTER = [(10.0, BOT), (10.0, 165.0)] + arch[1:-1] + [(312.0, 165.0), (312.0, BOT)]
poly(OUTER)
LANE_TOP = 182.0
poly([(290.0, BOT), (290.0, LANE_TOP)])
post(290.0, LANE_TOP, 2.5, "wall", "lanepost")
gate_a, gate_b = (290.0, LANE_TOP - 2), (311.0, LANE_TOP - 26)
gdx, gdy = gate_b[0] - gate_a[0], gate_b[1] - gate_a[1]
gl = math.hypot(gdx, gdy)
seg(gate_a, gate_b, "gate", oneway=(round(gdy / gl, 4), round(-gdx / gl, 4)))
PLUNGER_Y = 624.0
seg((290.0, PLUNGER_Y), (312.0, PLUNGER_Y), "plunger")
PLUNGER = {"rest": [301.0, PLUNGER_Y - BALL_R], "lane": [290.0, LANE_TOP, 22.0, PLUNGER_Y - LANE_TOP]}
DRAIN_Y = 648.0

# ---------------------------------------------------------------- lower playfield (flippers)
PIV_L, PIV_R = (96.0, 580.0), (204.0, 580.0)
UPPER = (22.0, 360.0)
FLIPPERS = [
    {"side": "L", "pivot": PIV_L, "len": 44.0, "r0": 7.0, "r1": 3.5, "rest": 30.0, "up": -18.0},
    {"side": "R", "pivot": PIV_R, "len": 44.0, "r0": 7.0, "r1": 3.5, "rest": 150.0, "up": 198.0},
    # upper flipper on the left wall, shoots the Helter-Skelter, SHY bank, Haunted House
    {"side": "L", "pivot": UPPER, "len": 34.0, "r0": 6.0, "r1": 3.0, "rest": 24.0, "up": -30.0},
]
poly([(10.0, 334.0), (17.0, 352.0)])            # deflector: rolls balls off the wall onto the flipper
# ---- inlanes v2 (slanted side guides "pochylnia" + narrow outlanes; see docs/research/lanes-reference.md)
# A ball dropping down a side wall rides the slope SLOPE_A-SLOPE_B (one-way, solid from above) onto
# the separator post and into the inlane, which leads diagonally onto the pivot end of the flipper.
# Only a ball bouncing outwards (sling / post) slips through the gap into the narrow outlane x 10..27.
SEP_X, SEP_Y0, SEP_Y1 = 27.0, 452.0, 520.0     # outlane wall x / separator post y / inlane guide bend y
SEP_POST_X = 37.0
SLOPE_A, SLOPE_B = (10.0, 404.0), (34.0, 430.0)
SLING_PTS = ((58.0, 466.0), (58.0, 512.0), (86.0, 534.0))


def guide_to_pivot(s, piv, r):
    dx, dy = piv[0] - s[0], piv[1] - s[1]
    L = math.hypot(dx, dy)
    d = (dx / L, dy / L)
    n = (d[1], -d[0]) if d[0] > 0 else (-d[1], d[0])
    return (piv[0] + n[0] * r, piv[1] + n[1] * r)


def _oneway_up(a, b):
    """one-way segment a-b that is solid only for a ball coming from above."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    n = (dy / L, -dx / L)
    if n[1] > 0:
        n = (-n[0], -n[1])
    seg(a, b, "wall", oneway=(round(n[0], 4), round(n[1], 4)))


SLINGS = []
SLOPES = []
INLANES = []   # art: [inlane centre path, outlane x, side]
for sgn in (1, -1):
    tf = (lambda p: p) if sgn == 1 else mirror
    piv = PIV_L if sgn == 1 else PIV_R
    sa, sb = tf(SLOPE_A), tf(SLOPE_B)
    _oneway_up(sa, sb)
    RAILS.append([sa, sb])
    post(sb[0], sb[1], 2.5, "wall", "slopepost")
    SLOPES.append([sa, sb])
    top, bend = tf((SEP_POST_X, SEP_Y0)), tf((SEP_POST_X, SEP_Y1))
    tan = guide_to_pivot(bend, piv, 7.5)
    poly([top, bend, tan])                                           # inlane guide
    poly([tf((SEP_POST_X - 2.6, SEP_Y0 + 2.4)), tf((SEP_X, SEP_Y0 + 18.0)), tf((SEP_X, BOT))])  # outlane wall
    post(top[0], top[1], 3.5, "rubber", "seppost")
    A, B, C = (tf(p) for p in SLING_PTS)
    seg(A, B, "rubber")
    seg(B, C, "rubber")
    seg(C, A, "sling%d" % (0 if sgn == 1 else 1))
    for p in (A, B, C):
        post(p[0], p[1], 3.0, "rubber", "slingpost")
    # tilted rubber cap over the top sling post: a ball can never balance on the post's crown
    seg(tf((A[0] - 3.5 if sgn == 1 else 300 - A[0] - 3.5, A[1] - 5.4)), tf((A[0] + 3.5 if sgn == 1 else 300 - A[0] + 3.5, A[1] - 1.4)), "rubber")
    SLINGS.append([A, B, C])
    mid_x = (SEP_POST_X + SLING_PTS[0][0]) / 2
    INLANES.append({"inlane": [tf((mid_x, SEP_Y0 + 14)), tf((mid_x, SEP_Y1 - 4)),
                               tf(((mid_x + tan[0] if sgn == 1 else mid_x + 300 - tan[0]) / 2 - 6, 548.0))],
                    "outlane_x": tf(((10.0 + SEP_X) / 2, 0))[0], "y0": SEP_Y0 + 24, "y1": 560.0})
post(150.0, 622.0, 4.0, "rubber", "centerpost")
# kickback: fires straight up the outlane, passes up through the one-way slope and is turned back
# onto the slope (and so into the inlane) by the deflector under the upper flipper
_ka, _kb = (10.0, 396.0), (26.0, 386.0)
_kl = math.hypot(_kb[0] - _ka[0], _kb[1] - _ka[1])
seg(_ka, _kb, "wall", oneway=(round(-(_kb[1] - _ka[1]) / _kl, 4), round((_kb[0] - _ka[0]) / _kl, 4)))
KICK_DEFLECTOR = [_ka, _kb]
KICKBACK = {"rect": [10.0, 572.0, 17.0, 44.0], "launch": [18.5, 584.0], "vy": -835.0}
# ---- /inlanes v2

# ---------------------------------------------------------------- orbits + spinner
ORB_Y0, ORB_Y1 = 214.0, 300.0
poly([(38.0, ORB_Y1), (38.0, ORB_Y0)])
post(38.0, ORB_Y1, 3.0, "rubber")
post(38.0, ORB_Y0, 2.5, "wall", "orbitpost")
poly([(264.0, ORB_Y1), (264.0, ORB_Y0)])
post(264.0, ORB_Y1, 3.0, "rubber")
post(264.0, ORB_Y0, 2.5, "wall", "orbitpost")
ORBITS = [{"name": "left", "x": [10.0, 38.0], "y": 250.0}, {"name": "right", "x": [264.0, 290.0], "y": 250.0}]
SPINNER = {"pos": [277.0, 282.0], "w": 26.0}

# ---------------------------------------------------------------- top lanes + bumpers
LANE_POSTS = [104.0, 136.0, 168.0, 200.0, 232.0]
for x in LANE_POSTS:
    poly([(x, 52.0), (x, 80.0)])
    post(x, 52.0, 2.5, "wall", "lanetop")
LANES = [{"pos": [(a + b) / 2, 66.0], "r": 7.0, "letter": l}
         for a, b, l in zip(LANE_POSTS, LANE_POSTS[1:], "FUEL")]
BUMPER_R = 13.0
# ---- toys v1: the top trio is an asteroid cluster on the right, a MAGNET + the VUK launch tube on the left
BUMPERS = [(198.0, 108.0, 12.0), (226.0, 140.0, 12.0), (192.0, 170.0, 12.0),     # top trio (asteroid cluster)
           (104.0, 252.0, BUMPER_R), (216.0, 252.0, BUMPER_R)]                    # pair beside the tower
for i, (x, y, r) in enumerate(BUMPERS):
    CIRCLES.append([x, y, r, "bumper", "bumper%d" % i])
STARS = [[110.0, 208.0], [160.0, 202.0], [210.0, 208.0]]       # star rollovers

# ---------------------------------------------------------------- targets
TARGETS = []      # stand-ups M-A-R-S on the left orbit wall
for i, (l, y) in enumerate(zip("MARS", (220.0, 238.0, 256.0, 274.0))):
    s = [39.5, y - 8.0, 39.5, y + 8.0]
    seg(s[:2], s[2:], "target%d" % i)
    TARGETS.append({"letter": l, "seg": s, "light": [50.0, y]})
DROPS = []        # drop banks: STAGE 1-2-3 on the right orbit wall, P-A-D angled lower right
for i, (l, y) in enumerate(zip("123", (226.0, 248.0, 270.0))):
    s = [262.5, y - 9.0, 262.5, y + 9.0]
    seg(s[:2], s[2:], "drop%d" % len(DROPS))
    DROPS.append({"bank": "stage", "letter": l, "seg": s, "light": [252.0, y]})
sa, sb = (188.0, 410.0), (226.0, 382.0)
for i, l in enumerate("PAD"):
    t0, t1 = i / 3 + 0.02, (i + 1) / 3 - 0.02
    p0 = (sa[0] + (sb[0] - sa[0]) * t0, sa[1] + (sb[1] - sa[1]) * t0)
    p1 = (sa[0] + (sb[0] - sa[0]) * t1, sa[1] + (sb[1] - sa[1]) * t1)
    s = [round(p0[0], 2), round(p0[1], 2), round(p1[0], 2), round(p1[1], 2)]
    seg(p0, p1, "drop%d" % len(DROPS))
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    DROPS.append({"bank": "pad", "letter": l, "seg": s, "light": [mx - 8.0, my - 11.0]})
poly([(182.0, 416.0), (232.0, 379.0)], rail=False)        # backing plate behind P-A-D
post(182.0, 416.0, 3.0, "rubber")
seg((179.6, 414.2), (188.76, 409.44))   # cap: no resting notch between the post and the first drop (was a BALL SEARCH spot)
post(232.0, 379.0, 3.0, "rubber")

# ---------------------------------------------------------------- holes / subway
HOLES = [
    {"name": "control", "pos": [150.0, 304.0], "r": 8.0, "kick": [-0.28, 0.96], "speed": 260.0, "flash": "control",
     "vuk": "launch", "vuk_speed": 700.0},
    {"name": "silo", "pos": [48.0, 304.0], "r": 8.0, "subway": "control"},
    {"name": "hangar", "pos": [246.0, 362.0], "r": 8.0, "subway": "control"},
]
poly([(236.0, 354.0), (246.0, 344.0), (256.0, 354.0)])   # hangar backstop (peaked: nothing rests on it)
SUBWAY = [[246.0, 362.0], [240.0, 340.0], [190.0, 300.0], [150.0, 304.0]]   # painted dashed path
SUBWAY2 = [[48.0, 304.0], [80.0, 344.0], [126.0, 330.0], [150.0, 304.0]]

# ---------------------------------------------------------------- ramps
RAMPS = []


def ramp(name, mouth_a, mouth_b, ctrl, back, apex_pred, down_pred, kind, width, color):
    mdx, mdy = mouth_b[0] - mouth_a[0], mouth_b[1] - mouth_a[1]
    ml = math.hypot(mdx, mdy)
    n_in = (mdy / ml, -mdx / ml)
    idx = len(RAMPS)
    seg(mouth_a, mouth_b, "ramp%d" % idx, oneway=(round(n_in[0], 4), round(n_in[1], 4)))
    blk = [mouth_a] + back + [mouth_b]
    poly(blk, rail=False)
    BLOCKS.append(blk)
    post(mouth_a[0], mouth_a[1], 2.5, "wall", "mouthpost")
    post(mouth_b[0], mouth_b[1], 2.5, "wall", "mouthpost")
    path = catmull(ctrl)
    s = [0.0]
    for a, b in zip(path, path[1:]):
        s.append(s[-1] + math.dist(a, b))
    apex = s[[i for i, p in enumerate(path) if apex_pred(i, p)][0]]
    down = s[[i for i, p in enumerate(path) if down_pred(i, p) and s[i] >= apex][0]]
    RAMPS.append({"name": name, "mouth": [*mouth_a, *mouth_b], "in": [round(n_in[0], 4), round(n_in[1], 4)],
                  "path": [[round(x, 2), round(y, 2)] for x, y in path], "s": [round(v, 2) for v in s],
                  "apex_s": round(apex, 2), "down_s": round(down, 2), "kind": kind, "width": width, "color": color})


# A: GANTRY - left mouth, climbs the service tower, U-turn over the top-left, wire down to the left inlane
ramp("gantry", (60.0, 322.0), (96.0, 314.0),
     [(78.0, 318.0), (80.0, 290.0), (78.0, 252.0), (75.0, 212.0), (73.0, 176.0), (70.0, 150.0), (61.0, 130.0),
      (46.0, 123.0), (32.0, 133.0), (24.0, 160.0), (21.0, 200.0), (21.0, 240.0), (21.0, 282.0), (21.0, 320.0),
      (21.0, 360.0), (24.0, 400.0), (36.0, 438.0), (47.5, 464.0)],
     [(56.0, 294.0), (100.0, 280.0)],
     lambda i, p: p[1] < 140.0, lambda i, p: p[0] < 40.0, "plastic", 22.0, "silver")
RAMPS[-1]["deco"] = "ties"
# B: BOOSTER - right mouth, climbs the right, U-turn over the top-right, wire down to the right inlane
ramp("booster", (212.0, 314.0), (248.0, 322.0),
     [(230.0, 318.0), (231.0, 290.0), (234.0, 256.0), (234.0, 220.0), (236.0, 182.0), (241.0, 152.0), (251.0, 132.0),
      (265.0, 124.0), (277.0, 135.0), (281.0, 162.0), (281.0, 200.0), (280.0, 260.0), (279.0, 330.0),
      (277.0, 390.0), (264.0, 438.0), (252.5, 464.0)],
     [(208.0, 290.0), (258.0, 270.0)],
     lambda i, p: p[1] < 140.0, lambda i, p: p[0] > 276.0, "plastic", 22.0, "blue")
RAMPS[-1]["deco"] = "rails"
# C: LIFTOFF - wire from the upper flipper, up the launch tower past the rocket, into the FUEL lanes
_d = (0.948, -0.318)
_c = (180.0, 318.0)
_t = (-_d[1], _d[0])
ma = (_c[0] - _t[0] * 13.0, _c[1] - _t[1] * 13.0)
mb = (_c[0] + _t[0] * 13.0, _c[1] + _t[1] * 13.0)
TOWER = (160.0, 250.0)     # the rocket on its pad (theme art + flasher)
ROCKET = [(160.0, 222.0), (167.0, 234.0), (167.0, 260.0), (174.0, 272.0), (146.0, 272.0), (153.0, 260.0), (153.0, 234.0)]
poly(ROCKET, rail=False, closed=True)      # the rocket model is a solid toy on the playfield
ramp("liftoff", ma, mb,
     [_c, (192.0, 310.0), (198.0, 294.0), (196.0, 272.0), (189.0, 248.0), (182.0, 222.0), (177.0, 194.0),
      (173.0, 166.0), (168.0, 138.0), (162.0, 114.0), (156.0, 98.0), (152.0, 90.0)],
     [(ma[0] + _d[0] * 10, ma[1] + _d[1] * 10 + 6.0), (mb[0] + _d[0] * 10, mb[1] + _d[1] * 10)],
     lambda i, p: p[1] < 296.0, lambda i, p: i > 0 and p[1] < 236.0, "wire", 18.0, "silver")


def vuk_ramp(name, hole, ctrl, width=12.0, color="cyan"):
    """up-kicker habitrail: no mouth on the playfield, the ball is fired in by the VUK in `hole`."""
    path = catmull([tuple(hole)] + ctrl)
    s = [0.0]
    for a, b in zip(path, path[1:]):
        s.append(s[-1] + math.dist(a, b))
    hx, hy = hole
    RAMPS.append({"name": name, "mouth": [hx - 6.0, hy, hx + 6.0, hy], "in": [0.0, -1.0],
                  "path": [[round(x, 2), round(y, 2)] for x, y in path], "s": [round(v, 2) for v in s],
                  "apex_s": round(s[-1], 2), "down_s": round(s[-1], 2), "kind": "wire", "art": "tube",
                  "vuk": True, "width": width, "color": color})


# D: LAUNCH - the CONTROL saucer is a VUK: it fires the ball up a clear tube left of the rocket into the FUEL lanes
vuk_ramp("launch", (150.0, 304.0),
         [(143.0, 292.0), (139.0, 272.0), (138.0, 244.0), (139.0, 214.0), (140.0, 186.0), (138.0, 160.0),
          (132.0, 130.0), (124.0, 104.0), (120.0, 92.0)])
MAGNETS = [{"name": "magnet", "pos": [104.0, 150.0], "r": 10.0, "hold": 1.2, "speed": 480.0, "label": "MAGNET",
            "kicks": [[1.0, 0.2], [-0.27, 1.0], [0.3, 1.0]]}]
DISCS = []
SPINNERS = []
# ---------------------------------------------------------------- inserts / lamps
LIGHTS = {}


def light(name, x, y, kind="round", color="yellow", dirdeg=0.0, size=4.0):
    LIGHTS[name] = {"pos": [round(x, 2), round(y, 2)], "kind": kind, "color": color, "dir": dirdeg, "size": size}


for ln in LANES:
    light("lane_" + ln["letter"], ln["pos"][0], ln["pos"][1], "round", "yellow", size=4.4)
for t in TARGETS:
    light("mars_" + t["letter"], t["light"][0], t["light"][1], "round", "red", size=3.4)
for d in DROPS:
    light(d["bank"] + "_" + d["letter"], d["light"][0], d["light"][1], "round",
          "orange" if d["bank"] == "stage" else "cyan", size=3.4)
for i, (x, y) in enumerate(STARS):
    light("star%d" % i, x, y, "star", "white", size=6.0)
for i, x in enumerate((114.0, 132.0, 150.0, 168.0, 186.0)):
    light("mult%d" % (i + 2), x, 472.0, "round", "orange", size=4.6)


def shot(name, x, y, dirdeg, color, chase=3):
    light(name + "_arrow", x, y, "arrow", color, dirdeg, 7.0)
    r = math.radians(dirdeg)
    for k in range(chase):
        light("%s%d" % (name, k + 1), x - math.cos(r) * (15 + 8 * k), y - math.sin(r) * (15 + 8 * k),
              "round", color, size=2.6)


shot("lorbit", 24.0, 318.0, -92.0, "yellow", 2)
shot("silo", 50.0, 336.0, -96.0, "magenta", 2)
shot("gantry", 82.0, 348.0, -100.0, "white")
shot("control", 144.0, 332.0, -90.0, "green", 2)
shot("liftoff", 174.0, 350.0, -20.0, "orange", 1)
shot("booster", 226.0, 348.0, -80.0, "cyan", 2)
shot("hangar", 252.0, 388.0, -98.0, "magenta", 1)
shot("rorbit", 277.0, 318.0, -88.0, "yellow", 2)
light("jackpot", 150.0, 384.0, "star", "white", size=7.5)
light("lock", 270.0, 410.0, "round", "magenta", size=3.6)
light("lock1", 258.0, 434.0, "round", "magenta", size=3.0)
light("lock2", 282.0, 434.0, "round", "magenta", size=3.0)
light("super", 150.0, 366.0, "round", "gold", size=3.4)
# plunger power meter in the shooter lane, bottom (soft) -> top (full); 1+2 = SKILL zone
for _i, _c in enumerate(["cyan", "green", "green", "orange", "red"]):
    light("meter%d" % _i, 301.0, 586.0 - 16.0 * _i, "round", _c, size=3.4)
light("lock1", 258.0, 434.0, "round", "magenta", size=3.0)
light("lock2", 282.0, 434.0, "round", "magenta", size=3.0)
light("super", 150.0, 366.0, "round", "gold", size=3.4)
# plunger power meter in the shooter lane, bottom (soft) -> top (full); 1+2 = SKILL zone
for _i, _c in enumerate(["cyan", "green", "green", "orange", "red"]):
    light("meter%d" % _i, 301.0, 586.0 - 16.0 * _i, "round", _c, size=3.4)
light("kickback", 18.5, 542.0, "arrow", "green", -90.0, 5.0)
light("shoot_again", 150.0, 556.0, "round", "red", size=5.0)
light("extra_l", 47.5, 494.0, "round", "green", size=3.0)
light("extra_r", 252.5, 494.0, "round", "green", size=3.0)
light("extra_ball", 150.0, 494.0, "round", "orange", size=4.6)
light("spinner", 277.0, 300.0, "round", "cyan", size=2.8)
for i in range(5):                                      # countdown ladder beside the rocket: 5..1
    light("count%d" % i, 127.0, 274.0 - i * 10.0, "round", "red" if i < 4 else "green", size=2.6)
LIGHT_COLORS = {"yellow": [255, 230, 60], "red": [255, 60, 50], "orange": [255, 150, 30], "cyan": [80, 230, 255],
                "magenta": [255, 80, 220], "white": [255, 255, 235], "green": [90, 255, 110], "gold": [255, 200, 90]}


def export(out_dir, art_scale):
    g = {"size": [W, H], "art_scale": art_scale, "ball_r": BALL_R, "segments": SEGS, "circles": CIRCLES,
         "flippers": [{**f, "pivot": list(f["pivot"])} for f in FLIPPERS],
         "lanes": LANES, "targets": TARGETS, "drops": DROPS, "bumpers": [list(b) for b in BUMPERS],
         "ramps": RAMPS, "holes": HOLES, "orbits": ORBITS, "spinner": SPINNER, "stars": STARS,
         "kickback": KICKBACK, "plunger": PLUNGER, "lights": LIGHTS, "light_colors": LIGHT_COLORS,
         "drain_y": DRAIN_Y, "tower": list(TOWER), "blocks": [[list(p) for p in b] for b in BLOCKS],
         "slings": [[list(map(float, q)) for q in t] for t in SLINGS],
         "discs": DISCS, "spinners": SPINNERS, "magnets": MAGNETS}
    with open(os.path.join(out_dir, "geometry.json"), "w") as f:
        json.dump(g, f, indent=1)
    return g


if __name__ == "__main__":
    # debug plot
    from PIL import Image, ImageDraw
    S = 2
    im = Image.new("RGB", (W * S, H * S), (20, 20, 30))
    d = ImageDraw.Draw(im)
    for x1, y1, x2, y2, m, *_ in SEGS:
        col = {"wall": (200, 200, 200), "rubber": (255, 255, 255), "gate": (0, 200, 0), "plunger": (255, 0, 0)}.get(
            m, (255, 120, 0) if m.startswith("drop") else (255, 0, 255) if m.startswith("ramp") else (0, 200, 255))
        d.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=col, width=2)
    for x, y, r, m, n in CIRCLES:
        d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], outline=(255, 80, 80) if m == "bumper" else (200, 200, 200))
    for f in FLIPPERS:
        px, py = f["pivot"]
        a = math.radians(f["rest"])
        d.line([px * S, py * S, (px + math.cos(a) * f["len"]) * S, (py + math.sin(a) * f["len"]) * S], fill=(255, 255, 0), width=8)
    for rp, col in zip(RAMPS, [(255, 60, 60), (60, 255, 60), (255, 200, 60)]):
        d.line([(x * S, y * S) for x, y in rp["path"]], fill=col, width=3)
    for h in HOLES:
        x, y = h["pos"]
        d.ellipse([(x - 8) * S, (y - 8) * S, (x + 8) * S, (y + 8) * S], fill=(120, 0, 160))
    for n, l in LIGHTS.items():
        x, y = l["pos"]
        d.ellipse([(x - 2) * S, (y - 2) * S, (x + 2) * S, (y + 2) * S], fill=tuple(LIGHT_COLORS[l["color"]]))
    im.save(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots", "lp_geom_debug.png"))
    print(len(SEGS), "segs", len(CIRCLES), "circles", len(LIGHTS), "lights")
