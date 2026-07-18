#!/usr/bin/env python3
"""Hoenn connectivity graph, derived from pokeemerald region-map rectangles.

Two location nodes are connected if their region-map grid rectangles touch or
overlap orthogonally (rook adjacency, not diagonal). The region map layout is
the game's own spatial abstraction, so route strips physically bridge the towns
they connect. Undirected; largest connected component kept; report any orphans.

Run: python3 scripts/build_hoenn_connectivity.py
Writes: output/connectivity_hoenn.json + hoenn NODE_XY (via build_hoenn_locations)
"""
import json, os, re
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "output"))
sections = json.load(open(f"{OUT.replace('output','raw/gen3')}/region_map_sections.json"))["map_sections"]
loc = json.load(open(f"{OUT}/locations_hoenn.json"))
enc_nodes = {k for k in loc if k != "_meta"}

GRID_W, GRID_H = 28, 15
SKIP = {"MAPSEC_NONE", "MAPSEC_BATTLE_FRONTIER", "MAPSEC_ARTISAN_CAVE", "MAPSEC_TRAINER_HILL",
        "MAPSEC_MIRAGE_ISLAND", "MAPSEC_MIRAGE_TOWER", "MAPSEC_SOUTHERN_ISLAND",
        "MAPSEC_AQUA_HIDEOUT_OLD", "MAPSEC_DESERT_UNDERPASS", "MAPSEC_ALTERING_CAVE",
        "MAPSEC_SEALED_CHAMBER", "MAPSEC_SCORCHED_SLAB", "MAPSEC_ANCIENT_TOMB",
        "MAPSEC_DESERT_RUINS", "MAPSEC_ISLAND_CAVE", "MAPSEC_MAGMA_HIDEOUT", "MAPSEC_AQUA_HIDEOUT"}

def node_id(sid):
    n = sid.replace("MAPSEC_", "").lower()
    return re.sub(r'route_(\d+)', r'route\1', n)
def ntype(sid, nm):
    if sid.endswith("_TOWN") or sid.endswith("_CITY"): return "town"
    if "ROUTE_" in sid: return "route"
    return "cave"

rects = {}
names = {}
types = {}
for s in sections:
    if "x" not in s: continue
    sid = s["id"]
    if sid in SKIP or sid.startswith("MAPSEC_UNDERWATER"): continue
    if sid in ("MAPSEC_METEOR_FALLS2", "MAPSEC_FIERY_PATH2", "MAPSEC_JAGGED_PASS2"): continue
    nid = node_id(sid)
    rects[nid] = (s["x"], s["y"], s.get("width", 1), s.get("height", 1))
    names[nid] = s["name"].title().replace("'S", "'s")
    types[nid] = ntype(sid, s["name"])

def touch_or_overlap(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    ox = min(ax + aw, bx + bw) - max(ax, bx)   # >0 overlap, ==0 edge touch, <0 gap
    oy = min(ay + ah, by + bh) - max(ay, by)
    if ox < 0 or oy < 0: return False
    if ox == 0 and oy == 0: return False        # pure diagonal corner touch
    return True

ids = list(rects.keys())
edges = set()
for i in range(len(ids)):
    for j in range(i + 1, len(ids)):
        if touch_or_overlap(rects[ids[i]], rects[ids[j]]):
            edges.add(tuple(sorted((ids[i], ids[j]))))

# Real ROM connections the rook-adjacency drops (corner-touch / non-adjacent grid cells).
# dewford_town–route106: verified game connection (Dewford's west surf exit); the grid rects
# touch only at a corner (ox==oy==0) so line 54 excludes it, leaving Dewford a degree-1 dead-end.
MANUAL_EDGES = [("dewford_town", "route106")]
for a, b in MANUAL_EDGES:
    if a in rects and b in rects:
        edges.add(tuple(sorted((a, b))))

# keep the largest connected component
adj = {i: [] for i in ids}
for a, b in edges:
    adj[a].append(b); adj[b].append(a)
def comp(start, seen):
    q = deque([start]); seen.add(start); c = {start}
    while q:
        x = q.popleft()
        for nb in adj[x]:
            if nb not in seen:
                seen.add(nb); c.add(nb); q.append(nb)
    return c
seen = set(); comps = []
for i in ids:
    if i not in seen:
        comps.append(comp(i, seen))
comps.sort(key=len, reverse=True)
main = comps[0]
orphans = [c for c in comps[1:]]

# Bridge orphan components to their nearest main-component node (Chebyshev between rect centers).
def center(r): return (r[0] + r[2] / 2, r[1] + r[3] / 2)
bridges = []
for oc in orphans:
    for onode in oc:
        oc_c = center(rects[onode])
        best = min(main, key=lambda m: abs(center(rects[m])[0] - oc_c[0]) + abs(center(rects[m])[1] - oc_c[1]))
        d = abs(center(rects[best])[0] - oc_c[0]) + abs(center(rects[best])[1] - oc_c[1])
        bridges.append((d, tuple(sorted((onode, best)))))
# add the single shortest bridge per orphan component, then recompute
for oc in orphans:
    cand = [(d, e) for d, e in bridges if e[0] in oc or e[1] in oc]
    if cand:
        d, e = min(cand)
        edges.add(e); adj[e[0]].append(e[1]); adj[e[1]].append(e[0])

# final connectivity check
seen = {ids[0]}; q = deque([ids[0]])
while q:
    x = q.popleft()
    for nb in adj[x]:
        if nb not in seen: seen.add(nb); q.append(nb)
disconnected = set(ids) - seen

out = {
    "region": "Hoenn",
    "basis": "pokeemerald region_map_sections.json rectangle adjacency (rook touch/overlap); "
             "orphan islands bridged to nearest mainland node.",
    "nodes": [{"id": i, "name": names[i], "type": types[i]} for i in ids],
    "edges": [list(e) for e in sorted(edges)],
}
json.dump(out, open(f"{OUT}/connectivity_hoenn.json", "w"), indent=1)

print(f"Hoenn connectivity: {len(ids)} nodes, {len(edges)} edges")
print(f"components before bridging: {[len(c) for c in comps]}")
print(f"disconnected after bridging: {sorted(disconnected) if disconnected else 'NONE (connected)'}")
missing = enc_nodes - set(ids)
print(f"encounter nodes missing from graph: {sorted(missing) if missing else 'none'}")
# spot-check known adjacencies
def has(a, b): return tuple(sorted((a, b))) in edges
for a, b in [("littleroot", "route101"), ("route101", "oldale"), ("rustboro", "route104"),
             ("mauville", "route110"), ("lilycove", "route121"), ("route110", "slateport")]:
    print(f"  edge {a}-{b}: {has(a,b)}")
