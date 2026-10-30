#!/usr/bin/env python3
"""Menu carousel preview for a table: hd playfield + ramps, scaled to 480 x 960.
usage: python3 tools/make_preview.py assets/tables/<id>"""
import sys
from pathlib import Path
from PIL import Image

d = Path(sys.argv[1])
pf = Image.open(d / "hd" / "playfield.png").convert("RGBA")
r = d / "hd" / "ramps.png"
if r.exists():
    ramps = Image.open(r).convert("RGBA").resize(pf.size)
    pf.alpha_composite(ramps)
pf = pf.resize((480, 960), Image.LANCZOS)
pf.convert("RGB").save(d / "preview.png", optimize=True)
print("preview", d / "preview.png", pf.size)
