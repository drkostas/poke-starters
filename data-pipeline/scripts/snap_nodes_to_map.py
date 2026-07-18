#!/usr/bin/env python3
"""Snap route nodes onto the painted roads of each region's town-map PNG.
Town nodes are left untouched (they already sit on the map's own city markers).
Operates on normalized x/y in the connectivity JSON; writes back in place."""
import json, sys, math
from PIL import Image

MAPS = "/Users/gkos/Insync/Gdrive/Projects/pokemon_fun/app/maps"
# (connectivity json path, png, radius-in-px) per region
REGIONS = {
    "kanto": (f"{MAPS}/kanto_frlg.png", 16),
    "johto": (f"{MAPS}/johto.png", 12),
    "hoenn": (f"{MAPS}/hoenn.png", 14),
}

def is_road_orange(r, g, b):
    # FRLG / Emerald painted route: orange-tan, high red, mid-high green, low-mid blue
    if r > 236 and g > 236 and b > 236:      # white frame/margin
        return False
    return r >= 195 and 120 <= g <= 232 and b <= 175 and (r - b) >= 45

def is_road_paletan(r, g, b):
    # GSC (Johto) walkable land corridors are pale tan (~220,249,136), distinct from grass-green/water
    return r >= 200 and g >= 225 and 100 <= b <= 185 and (r - b) >= 45

ROAD_TEST = {"kanto": is_road_orange, "hoenn": is_road_orange, "johto": is_road_paletan}

def build_road_pixels(im, is_road):
    W, H = im.size
    px = im.load()
    pts = []
    for y in range(H):
        for x in range(W):
            p = px[x, y]
            if is_road(*p[:3]):
                pts.append((x, y))
    return pts, W, H

def snap_region(name, conn_paths):
    png, radius = REGIONS[name]
    im = Image.open(png).convert("RGB")
    road, W, H = build_road_pixels(im, ROAD_TEST[name])
    # index road pixels into a coarse grid for fast nearest lookup
    cell = 4
    grid = {}
    for (x, y) in road:
        grid.setdefault((x // cell, y // cell), []).append((x, y))

    def nearest_road(px, py, rad):
        best = None; bd = rad * rad + 1
        gx, gy = int(px) // cell, int(py) // cell
        span = rad // cell + 1
        for cx in range(gx - span, gx + span + 1):
            for cy in range(gy - span, gy + span + 1):
                for (x, y) in grid.get((cx, cy), ()):
                    d = (x - px) ** 2 + (y - py) ** 2
                    if d < bd:
                        bd = d; best = (x, y)
        return best, math.sqrt(bd) if best else None

    # load a representative connectivity to snap; snap once, write same result to all copies
    ref = json.load(open(conn_paths[0]))
    moved = 0; skipped = 0
    newcoords = {}
    for n in ref["nodes"]:
        if "x" not in n:
            continue
        # towns already sit on the map's own city markers; water/sea-route nodes have no painted
        # road beneath them, so snapping would yank them onto distant land — leave both untouched.
        if n.get("type") in ("town", "water"):
            newcoords[n["id"]] = (n["x"], n["y"]); continue
        px_, py_ = n["x"] * W, n["y"] * H
        pt, dist = nearest_road(px_, py_, radius)
        if pt:
            newcoords[n["id"]] = (pt[0] / W, pt[1] / H); moved += 1
        else:
            newcoords[n["id"]] = (n["x"], n["y"]); skipped += 1
    # apply to every copy
    for cp in conn_paths:
        c = json.load(open(cp))
        for n in c["nodes"]:
            if n["id"] in newcoords and "x" in n:
                n["x"], n["y"] = round(newcoords[n["id"]][0], 4), round(newcoords[n["id"]][1], 4)
        json.dump(c, open(cp, "w"), separators=(",", ":"))
    print(f"{name}: {len(road)} road px, moved {moved} route nodes, kept {skipped}")

if __name__ == "__main__":
    APP = "/Users/gkos/Insync/Gdrive/Projects/pokemon_fun/app/data"
    SC = "/private/tmp/claude-501/-Users-gkos-Insync-Gdrive-Projects-pokemon-fun/4eb25f59-d685-4ca1-be00-fe805e152a0d/scratchpad/data"
    names = sys.argv[1:] or ["kanto"]
    import os
    for nm in names:
        # only the copies that actually carry coords; APP first so it is the snap reference
        paths = [p for p in (f"{APP}/connectivity_{nm}.json", f"{SC}/connectivity_{nm}.json") if os.path.exists(p)]
        snap_region(nm, paths)
