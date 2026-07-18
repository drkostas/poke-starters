#!/usr/bin/env python3
"""Johto location connectivity graph for BFS proximity.

Nodes = Johto towns/cities, routes 29-46, and notable catch-areas.
Edges = direct walkable/surfable adjacency on the canonical Gen-2 (Gold/Silver/
Crystal) Johto overworld. Undirected + connected so BFS distance is defined.
Mt. Silver is excluded (Kanto-border postgame, not Johto-graph adjacent).

Run: python3 scripts/build_johto_connectivity.py
Writes: output/connectivity_johto.json (+ verification report)
"""
import json, os
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "output", "connectivity_johto.json"))

NODES = [
    ("new_bark", "New Bark Town", "town"), ("cherrygrove", "Cherrygrove City", "town"),
    ("violet", "Violet City", "town"), ("azalea", "Azalea Town", "town"),
    ("goldenrod", "Goldenrod City", "town"), ("ecruteak", "Ecruteak City", "town"),
    ("olivine", "Olivine City", "town"), ("cianwood", "Cianwood City", "town"),
    ("mahogany", "Mahogany Town", "town"), ("blackthorn", "Blackthorn City", "town"),
    ("route29", "Route 29", "route"), ("route30", "Route 30", "route"),
    ("route31", "Route 31", "route"), ("route32", "Route 32", "route"),
    ("route33", "Route 33", "route"), ("route34", "Route 34", "route"),
    ("route35", "Route 35", "route"), ("route36", "Route 36", "route"),
    ("route37", "Route 37", "route"), ("route38", "Route 38", "route"),
    ("route39", "Route 39", "route"), ("route40", "Route 40", "route"),
    ("route41", "Route 41", "route"), ("route42", "Route 42", "route"),
    ("route43", "Route 43", "route"), ("route44", "Route 44", "route"),
    ("route45", "Route 45", "route"), ("route46", "Route 46", "route"),
    ("sprout_tower", "Sprout Tower", "building"), ("burned_tower", "Burned Tower", "building"),
    ("tin_tower", "Bell Tower", "building"),
    ("ruins_of_alph", "Ruins of Alph", "cave"), ("union_cave", "Union Cave", "cave"),
    ("slowpoke_well", "Slowpoke Well", "cave"), ("ilex_forest", "Ilex Forest", "cave"),
    ("national_park", "National Park", "cave"), ("mt_mortar", "Mt. Mortar", "cave"),
    ("ice_path", "Ice Path", "cave"), ("whirl_islands", "Whirl Islands", "cave"),
    ("dark_cave", "Dark Cave", "cave"), ("dragons_den", "Dragon's Den", "cave"),
    ("lake_of_rage", "Lake of Rage", "water"),
]

EDGES = [
    ("new_bark", "route29"), ("route29", "cherrygrove"), ("route29", "route46"),
    ("cherrygrove", "route30"), ("route30", "route31"),
    ("route31", "violet"), ("route31", "dark_cave"),
    ("violet", "sprout_tower"), ("violet", "route32"), ("violet", "route36"),
    ("route32", "ruins_of_alph"), ("route32", "union_cave"),
    ("union_cave", "route33"), ("route33", "azalea"),
    ("azalea", "slowpoke_well"), ("azalea", "ilex_forest"),
    ("ilex_forest", "route34"), ("route34", "goldenrod"),
    ("goldenrod", "route35"), ("route35", "national_park"),
    ("national_park", "route36"), ("route36", "route37"), ("route37", "ecruteak"),
    ("ecruteak", "burned_tower"), ("ecruteak", "tin_tower"),
    ("ecruteak", "route38"), ("ecruteak", "route42"),
    ("route38", "route39"), ("route39", "olivine"),
    ("olivine", "route40"), ("route40", "route41"),
    ("route41", "cianwood"), ("route41", "whirl_islands"),
    ("route42", "mt_mortar"), ("route42", "mahogany"),
    ("mahogany", "route43"), ("mahogany", "route44"),
    ("route43", "lake_of_rage"), ("route44", "ice_path"),
    ("ice_path", "blackthorn"), ("blackthorn", "dragons_den"),
    ("blackthorn", "route45"), ("route45", "route46"), ("route45", "dark_cave"),
]

ids = {n[0] for n in NODES}
# validate edges reference known nodes
for a, b in EDGES:
    assert a in ids, f"edge endpoint not a node: {a}"
    assert b in ids, f"edge endpoint not a node: {b}"

# BFS connectivity check from New Bark Town
adj = {i: [] for i in ids}
for a, b in EDGES:
    adj[a].append(b); adj[b].append(a)
seen = {"new_bark"}; q = deque(["new_bark"])
while q:
    c = q.popleft()
    for nb in adj[c]:
        if nb not in seen:
            seen.add(nb); q.append(nb)
disconnected = ids - seen
assert not disconnected, f"DISCONNECTED nodes: {disconnected}"

# cross-check every encounter node exists in the graph
loc = json.load(open(os.path.join(os.path.dirname(OUT), "locations_johto.json")))
enc_nodes = {k for k in loc if k != "_meta"}
missing = enc_nodes - ids
assert not missing, f"encounter nodes missing from graph: {missing}"

out = {
    "region": "Johto",
    "basis": "Canonical Gen-2 (Gold/Silver/Crystal) Johto overworld adjacency; undirected + connected.",
    "nodes": [{"id": i, "name": n, "type": t} for i, n, t in NODES],
    "edges": [list(e) for e in EDGES],
}
json.dump(out, open(OUT, "w"), indent=1)
# also write the app-facing filename
json.dump(out, open(OUT.replace("connectivity_johto", "connectivity_johto"), "w"), indent=1)

print(f"Johto connectivity: {len(NODES)} nodes, {len(EDGES)} edges, connected=OK")
print(f"encounter nodes covered: {len(enc_nodes)}/{len(enc_nodes)} (pure connectors: {sorted(ids - enc_nodes)})")
# eccentricity sanity: max BFS distance from new_bark
dist = {"new_bark": 0}; q = deque(["new_bark"])
while q:
    c = q.popleft()
    for nb in adj[c]:
        if nb not in dist:
            dist[nb] = dist[c] + 1; q.append(nb)
far = max(dist.items(), key=lambda kv: kv[1])
print(f"farthest from New Bark: {far[0]} at {far[1]} steps")
