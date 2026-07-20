#!/usr/bin/env python3
"""Route map edges as clean orthogonal (H/V only) polylines down the road centers.

For each region: read app/data/connectivity_<region>.json and app/maps/<map>.png,
snap the route/cave/building nodes onto the road centerline (towns and water stay on
their markers), then draw every land edge as horizontal/vertical segments through the
middle of the routes and the middle of the towns:

  1. road mask from the map palette, distance-transformed so "centeredness" is known;
  2. a 4-connectivity A* with a strong turn penalty (so paths run in long straight
     runs with few, square corners, never diagonals or staircases) and a mild centre
     bias finds the road path;
  3. the path is reduced to its corner points; edges with no road path (Surf
     crossings, off-road stubs) fall back to a plain L-shape.

Results are stored normalized (0..1) under `edgePaths` ("<a>|<b>" -> [[x,y],...]);
the app renders each as a polyline. Run: python3 route_edges.py [region]  (default:
all four). Requires Pillow. Run after build_sinnoh_connectivity.py for Sinnoh.
"""
import json
import heapq
import sys
from collections import deque
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MAPNAME = {"kanto": "kanto_frlg", "johto": "johto", "hoenn": "hoenn", "sinnoh": "sinnoh"}
N8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def is_road(r, g, b, region):
    if region in ("kanto", "hoenn"):
        return r >= 195 and 115 <= g <= 215 and b <= 115 and r + 8 >= g
    if region == "johto":
        return r >= 190 and g >= 200 and 80 <= b <= 180
    if region == "sinnoh":
        return 170 <= r <= 255 and 135 <= g <= 220 and 30 <= b <= 145 and r + 15 >= g >= b - 15
    return False


def build_mask(im, region):
    W, H = im.size
    px = im.load()
    M = bytearray(W * H)
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            if is_road(r, g, b, region):
                M[y * W + x] = 1
    return M, W, H


def dilate(M, W, H, it=1):
    for _ in range(it):
        N = bytearray(M)
        for y in range(H):
            for x in range(W):
                if M[y * W + x]:
                    continue
                for dx, dy in N8:
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < W and 0 <= yy < H and M[yy * W + xx]:
                        N[y * W + x] = 1
                        break
        M = N
    return M


def distance_transform(M, W, H):
    """Manhattan distance from each road pixel to the nearest non-road pixel."""
    INF = 1 << 30
    dist = [INF] * (W * H)
    dq = deque()
    for i in range(W * H):
        if not M[i]:
            dist[i] = 0
            dq.append(i)
    while dq:
        i = dq.popleft()
        x, y = i % W, i // W
        d = dist[i]
        for dx, dy in N4:
            xx, yy = x + dx, y + dy
            if 0 <= xx < W and 0 <= yy < H:
                j = yy * W + xx
                if dist[j] > d + 1:
                    dist[j] = d + 1
                    dq.append(j)
    return dist


def snap_center(M, dist, W, H, x, y, R):
    """Nearest road pixel that is as central (high distance-transform) as possible."""
    best, bs = None, -1e9
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            xx, yy = x + dx, y + dy
            if 0 <= xx < W and 0 <= yy < H and M[yy * W + xx]:
                s = dist[yy * W + xx] - 0.03 * (dx * dx + dy * dy)
                if s > bs:
                    bs, best = s, (xx, yy)
    return best


def paint(M, W, H, x, y, rad=2):
    for dy in range(-rad, rad + 1):
        for dx in range(-rad, rad + 1):
            xx, yy = x + dx, y + dy
            if 0 <= xx < W and 0 <= yy < H:
                M[yy * W + xx] = 1


def astar4(M, dist, maxdt, W, H, s, t, turn, center):
    """4-connectivity A*; state carries the incoming direction so turns can be priced."""
    start = (s[0], s[1], -1)
    g = {start: 0.0}
    came = {}
    seen = set()
    pq = [(abs(s[0] - t[0]) + abs(s[1] - t[1]), 0.0, start)]
    while pq:
        _, gc, st = heapq.heappop(pq)
        if st in seen:
            continue
        seen.add(st)
        x, y, d = st
        if (x, y) == t:
            path = [(x, y)]
            cur = st
            while cur in came:
                cur = came[cur]
                path.append((cur[0], cur[1]))
            return path[::-1]
        for di, (dx, dy) in enumerate(N4):
            xx, yy = x + dx, y + dy
            if not (0 <= xx < W and 0 <= yy < H) or not M[yy * W + xx]:
                continue
            step = 1.0 + (turn if (d != -1 and di != d) else 0) + center * (1.0 - dist[yy * W + xx] / maxdt)
            ns = (xx, yy, di)
            ng = gc + step
            if ng < g.get(ns, 1e18):
                g[ns] = ng
                came[ns] = st
                heapq.heappush(pq, (ng + abs(xx - t[0]) + abs(yy - t[1]), ng, ns))
    return None


def corners(path):
    """Keep only the endpoints and the points where the direction turns."""
    if len(path) < 3:
        return path
    out = [path[0]]
    for i in range(1, len(path) - 1):
        a, b, c = path[i - 1], path[i], path[i + 1]  # a is the immediate predecessor
        if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
            out.append(b)
    if out[-1] != path[-1]:
        out.append(path[-1])
    return out


def route_region(region, turn=10.0, center=0.8, write=True):
    path_json = ROOT / f"app/data/connectivity_{region}.json"
    conn = json.loads(path_json.read_text())
    im = Image.open(ROOT / f"app/maps/{MAPNAME[region]}.png").convert("RGB")
    M, W, H = build_mask(im, region)
    dist_road = distance_transform(M, W, H)

    # 1) snap route/cave/building nodes onto the road centerline
    Rsnap = min(16, max(6, int(0.045 * W)))
    for n in conn["nodes"]:
        if n["type"] in ("town", "water"):
            continue
        s = snap_center(M, dist_road, W, H, int(n["x"] * W), int(n["y"] * H), Rsnap)
        if s:
            n["x"], n["y"] = round(s[0] / W, 4), round(s[1] / H, 4)
    nodes = {n["id"]: n for n in conn["nodes"]}

    # 2) routing mask = roads + a patch at every node centre, dilated to bridge gaps
    RM = bytearray(M)
    for n in conn["nodes"]:
        if n["type"] != "water":
            paint(RM, W, H, int(n["x"] * W), int(n["y"] * H), 2)
    RM = dilate(RM, W, H, 5 if W >= 400 else 3)
    dist_rt = distance_transform(RM, W, H)
    maxdt = max(dist_rt)

    # 3) an orthogonal path per edge: road-following (A*) or an L-shape fallback
    paths, routed = {}, 0
    for a, b in conn["edges"]:
        na, nb = nodes[a], nodes[b]
        s = (int(na["x"] * W), int(na["y"] * H))
        t = (int(nb["x"] * W), int(nb["y"] * H))
        water = na["type"] == "water" or nb["type"] == "water"
        p = None if water else astar4(RM, dist_rt, maxdt, W, H, s, t, turn, center)
        if p:
            p = corners(p)
            routed += 1
        elif s == t:
            p = [s, t]
        else:
            c1, c2 = (t[0], s[1]), (s[0], t[1])
            def on(c):
                return 0 <= c[0] < W and 0 <= c[1] < H and RM[c[1] * W + c[0]]
            corner = c1 if water or on(c1) or not on(c2) else c2
            p = [s, corner, t]
        paths[f"{a}|{b}"] = [[round(x / W, 4), round(y / H, 4)] for x, y in p]

    conn["edgePaths"] = paths
    if write:
        path_json.write_text(json.dumps(conn, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{region}: {W}x{H}  {routed}/{len(conn['edges'])} edges follow roads; "
          f"rest are L-shapes (Surf/off-road). all orthogonal.")


if __name__ == "__main__":
    regions = [sys.argv[1]] if len(sys.argv) > 1 else ["kanto", "johto", "hoenn", "sinnoh"]
    for reg in regions:
        route_region(reg)
