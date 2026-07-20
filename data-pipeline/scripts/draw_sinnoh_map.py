#!/usr/bin/env python3
"""Draw an ORIGINAL schematic Sinnoh map -> ../../app/maps/sinnoh.png.

Not a reproduction of any game asset: the landmass is built from the connectivity
node layout (land nodes + their edges dilated into a coastline), then painted in
the app's palette with a snow cap (north), a Mt. Coronet spine, and tan routes.
Node coordinates in connectivity_sinnoh.json are placed to sit on this terrain.
Requires Pillow.
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
W, H = 560, 600  # VBH in the app = round(240 * H / W, 1) = 257.1
LAND_TYPES = {"town", "route", "cave"}
WATER = (84, 150, 200); LAND = (122, 178, 105); SNOW = (226, 238, 242)
MTN = (150, 140, 120); ROUTE = (216, 197, 150); COAST = (60, 110, 150)


def main():
    conn = json.loads((ROOT / "app/data/connectivity_sinnoh.json").read_text())
    nodes = {n["id"]: n for n in conn["nodes"]}

    def px(n):
        return (n["x"] * W, n["y"] * H)

    # land mask: union of node circles + thick land edges, smoothed into a coastline
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    for n in nodes.values():
        if n["type"] in LAND_TYPES:
            x, y = px(n)
            md.ellipse([x - 46, y - 46, x + 46, y + 46], fill=255)
    for a, b in conn["edges"]:
        if nodes[a]["type"] in LAND_TYPES and nodes[b]["type"] in LAND_TYPES:
            md.line([px(nodes[a]), px(nodes[b])], fill=255, width=54)
    mask = mask.filter(ImageFilter.GaussianBlur(16)).point(lambda v: 255 if v > 120 else 0).filter(ImageFilter.GaussianBlur(2))

    img = Image.composite(Image.new("RGB", (W, H), LAND), Image.new("RGB", (W, H), WATER), mask)
    edge = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1))
    img = Image.composite(Image.new("RGB", (W, H), COAST), img, edge.point(lambda v: min(255, int(v * 1.5))))

    snow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(snow).rectangle([0, 0, W, int(0.19 * H)], fill=255)
    snow = Image.composite(snow, Image.new("L", (W, H), 0), mask).filter(ImageFilter.GaussianBlur(10))
    img = Image.composite(Image.new("RGB", (W, H), SNOW), img, snow)

    mtn = Image.new("L", (W, H), 0)
    m = ImageDraw.Draw(mtn)
    for a, b in [("route216", "route211"), ("route211", "mt_coronet"), ("mt_coronet", "route208"), ("route208", "route210s")]:
        if a in nodes and b in nodes:
            m.line([px(nodes[a]), px(nodes[b])], fill=255, width=30)
    mc = px(nodes["mt_coronet"])
    m.ellipse([mc[0] - 34, mc[1] - 34, mc[0] + 34, mc[1] + 34], fill=255)
    mtn = Image.composite(mtn, Image.new("L", (W, H), 0), mask).filter(ImageFilter.GaussianBlur(6))
    img = Image.composite(Image.new("RGB", (W, H), MTN), img, mtn)

    dr = ImageDraw.Draw(img)
    for a, b in conn["edges"]:
        if nodes[a]["type"] in LAND_TYPES and nodes[b]["type"] in LAND_TYPES:
            dr.line([px(nodes[a]), px(nodes[b])], fill=ROUTE, width=6)

    out = ROOT / "app/maps/sinnoh.png"
    img.save(out)
    print(f"wrote {out} ({W}x{H}); set app VBH sinnoh = {round(240 * H / W, 1)}")


if __name__ == "__main__":
    main()
