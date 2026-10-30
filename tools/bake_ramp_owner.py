#!/usr/bin/env python3
"""Bake assets/tables/<id>/hd/ramp_owner.png for the 3D view.

The ramp art (ramps.png) is one flat top-view image; the 3D view projects it onto one raised
ribbon mesh per ramp (plus the helter tower dome). Where ribbons overlap (crossings, parallel
runs) each pixel must be drawn by exactly one of them: the ramp it was painted for. Owner =
the highest ramp whose deck covers the pixel, else the nearest ribbon. Value = (index+1)*40,
tower = (n_ramps+1)*40, 0 = none. 2 px per table unit, nearest filtered in the shader.

Usage: python3 tools/bake_ramp_owner.py <table_id>
(needs numpy + pillow: nix-shell -p "python3.withPackages(p: [p.numpy p.pillow])")
"""
import json, sys
import numpy as np
from PIL import Image

PAD = 9.0        # ribbon half width = width/2 + PAD (covers the painted side walls) - keep in sync with table3d.gd
TOWER_R = 15.0   # helter tower dome radius (table3d.gd TOWER_R)
S = 2            # px per unit


def elev(s, apex, down, L):
    e = np.ones_like(s)
    up = s < apex
    e[up] = np.clip(s[up] / max(apex, 1.0), 0, 1)
    dn = s >= down
    e[dn] = np.clip(1.0 - (s[dn] - down) / max(L - down, 1.0), 0, 1)
    return e * e * (3 - 2 * e)


def main(tid):
    d = f"assets/tables/{tid}/"
    g = json.load(open(d + "geometry.json"))
    W, H = g["size"]
    ys, xs = np.mgrid[0:H * S, 0:W * S]
    P = np.stack([(xs + 0.5) / S, (ys + 0.5) / S], -1).reshape(-1, 2)
    n = len(g["ramps"])
    best_core_h = np.full(len(P), -1.0)
    owner_core = np.zeros(len(P), np.int32)
    best_d = np.full(len(P), 1e9)
    owner_near = np.zeros(len(P), np.int32)
    for i, r in enumerate(g["ramps"]):
        path = np.array(r["path"], float)
        s = np.array(r["s"], float)
        L = s[-1]
        hs = elev(s, r["apex_s"], r["down_s"], L)
        hw = r.get("width", 18.0) / 2 + PAD
        core = r.get("width", 18.0) / 2 + 2.0
        dmin = np.full(len(P), 1e9)
        hmin = np.zeros(len(P))
        for k in range(len(path) - 1):
            a, b = path[k], path[k + 1]
            ab = b - a
            l2 = max(ab @ ab, 1e-9)
            lo = np.minimum(a, b) - hw - 1
            hi = np.maximum(a, b) + hw + 1
            m = (P[:, 0] > lo[0]) & (P[:, 0] < hi[0]) & (P[:, 1] > lo[1]) & (P[:, 1] < hi[1])
            if not m.any():
                continue
            q = P[m]
            t = np.clip(((q - a) @ ab) / l2, 0, 1)
            dd = np.linalg.norm(q - (a + ab * t[:, None]), axis=1)
            hh = hs[k] + (hs[k + 1] - hs[k]) * t
            cur = dmin[m]
            better = dd < cur
            idx = np.nonzero(m)[0][better]
            dmin[idx] = dd[better]
            hmin[idx] = hh[better]
        cov = dmin < hw
        c = (dmin < core) & (hmin > best_core_h)
        best_core_h[c] = hmin[c]
        owner_core[c] = i + 1
        nb = cov & (dmin < best_d)
        best_d[nb] = dmin[nb]
        owner_near[nb] = i + 1
    own = np.where(owner_core > 0, owner_core, owner_near)
    if "tower" in g:
        tx, ty = g["tower"]
        tw = np.hypot(P[:, 0] - tx, P[:, 1] - ty) < TOWER_R
        own[tw & (owner_core == 0)] = n + 1
    img = (own.reshape(H * S, W * S) * 40).clip(0, 255).astype(np.uint8)
    Image.fromarray(img, "L").save(d + "hd/ramp_owner.png")
    print("ramp_owner", tid, img.shape, {int(v): int((img == v).sum()) for v in np.unique(img)})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "midnight_funfair")
