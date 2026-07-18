#!/usr/bin/env python3
"""Build the Kanto location connectivity graph for BFS proximity.

Nodes = Kanto towns/cities, routes, and notable catch-areas (caves, towers,
Safari Zone, Power Plant, etc.). Edges = direct walkable/surfable adjacency,
based on the canonical Gen-1 (Red/Blue/Yellow) Kanto overworld map.

The graph is undirected (each edge stored once) and connected, so BFS distance
from any town to any catch-location is computable.

Type taxonomy is limited to {town, route, cave, building, water}:
  - town     : towns and cities (incl. Indigo Plateau)
  - route    : land routes (grass/road you walk)
  - water    : surf-only sea routes (19, 20, 21)
  - cave     : natural notable areas (forest, caves, islands, Safari Zone,
               Victory Road) -- the "natural wild area" bucket
  - building : man-made structures with wild Pokemon (Tower, Power Plant, Mansion)

Run: python3 scripts/build_kanto_connectivity.py
Writes: output/kanto_connectivity.json  (+ prints a verification report)
"""

import json
import os
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "output", "kanto_connectivity.json"))

# --- Nodes -----------------------------------------------------------------
# (id, name, type)
NODES = [
    # Towns & cities
    ("pallet", "Pallet Town", "town"),
    ("viridian", "Viridian City", "town"),
    ("pewter", "Pewter City", "town"),
    ("cerulean", "Cerulean City", "town"),
    ("vermilion", "Vermilion City", "town"),
    ("lavender", "Lavender Town", "town"),
    ("celadon", "Celadon City", "town"),
    ("fuchsia", "Fuchsia City", "town"),
    ("saffron", "Saffron City", "town"),
    ("cinnabar", "Cinnabar Island", "town"),
    ("indigo_plateau", "Indigo Plateau", "town"),
    # Land routes
    ("route1", "Route 1", "route"),
    ("route2", "Route 2", "route"),
    ("route3", "Route 3", "route"),
    ("route4", "Route 4", "route"),
    ("route5", "Route 5", "route"),
    ("route6", "Route 6", "route"),
    ("route7", "Route 7", "route"),
    ("route8", "Route 8", "route"),
    ("route9", "Route 9", "route"),
    ("route10", "Route 10", "route"),
    ("route11", "Route 11", "route"),
    ("route12", "Route 12", "route"),
    ("route13", "Route 13", "route"),
    ("route14", "Route 14", "route"),
    ("route15", "Route 15", "route"),
    ("route16", "Route 16", "route"),
    ("route17", "Route 17", "route"),
    ("route18", "Route 18", "route"),
    ("route22", "Route 22", "route"),
    ("route23", "Route 23", "route"),
    ("route24", "Route 24", "route"),
    ("route25", "Route 25", "route"),
    # Water (surf) routes
    ("route19", "Route 19", "water"),
    ("route20", "Route 20", "water"),
    ("route21", "Route 21", "water"),
    # Notable natural catch-areas
    ("viridian_forest", "Viridian Forest", "cave"),
    ("mt_moon", "Mt. Moon", "cave"),
    ("rock_tunnel", "Rock Tunnel", "cave"),
    ("digletts_cave", "Diglett's Cave", "cave"),
    ("seafoam_islands", "Seafoam Islands", "cave"),
    ("safari_zone", "Safari Zone", "cave"),
    ("cerulean_cave", "Cerulean Cave", "cave"),
    ("victory_road", "Victory Road", "cave"),
    # Notable man-made catch-areas
    ("pokemon_tower", "Pokemon Tower", "building"),
    ("power_plant", "Power Plant", "building"),
    ("pokemon_mansion", "Pokemon Mansion", "building"),
]

# --- Edges (undirected, canonical adjacency) --------------------------------
EDGES = [
    # South loop: Pallet <-> Route 1 <-> Viridian
    ("pallet", "route1"),
    ("route1", "viridian"),
    # Viridian's exits: Route 2 north, Route 22 west
    ("viridian", "route2"),
    ("viridian", "route22"),
    # Route 2 -> Viridian Forest -> Pewter; Diglett's Cave (north entrance) off Route 2
    ("route2", "viridian_forest"),
    ("route2", "digletts_cave"),
    ("viridian_forest", "pewter"),
    # Pewter -> Route 3 -> Mt. Moon -> Route 4 -> Cerulean
    ("pewter", "route3"),
    ("route3", "mt_moon"),
    ("mt_moon", "route4"),
    ("route4", "cerulean"),
    # Cerulean's exits: Route 5 south, Route 9 east, Route 24 north, Cerulean Cave (surf)
    ("cerulean", "route5"),
    ("cerulean", "route9"),
    ("cerulean", "route24"),
    ("cerulean", "cerulean_cave"),
    # Nugget Bridge: Route 24 -> Route 25 (Bill's, dead end)
    ("route24", "route25"),
    # Saffron hub: Route 5 (N), Route 6 (S), Route 7 (W), Route 8 (E)
    ("route5", "saffron"),
    ("saffron", "route6"),
    ("saffron", "route7"),
    ("saffron", "route8"),
    # Route 6 -> Vermilion; Vermilion -> Route 11 east
    ("route6", "vermilion"),
    ("vermilion", "route11"),
    # Diglett's Cave (south entrance) off Route 11; Route 11 -> Route 12 gate
    ("route11", "digletts_cave"),
    ("route11", "route12"),
    # Route 7 -> Celadon -> Route 16 -> Cycling Road (17,18) -> Fuchsia
    ("route7", "celadon"),
    ("celadon", "route16"),
    ("route16", "route17"),
    ("route17", "route18"),
    ("route18", "fuchsia"),
    # Fuchsia exits: Route 15 (NW), Route 19 (S, water), Safari Zone
    ("fuchsia", "route15"),
    ("fuchsia", "route19"),
    ("fuchsia", "safari_zone"),
    # Route 15 <-> 14 <-> 13 <-> 12 (west chain toward Lavender area)
    ("route15", "route14"),
    ("route14", "route13"),
    ("route13", "route12"),
    # Route 12 -> Lavender; Route 8 -> Lavender
    ("route12", "lavender"),
    ("route8", "lavender"),
    # Lavender exits: Route 10 (N, Rock Tunnel), Pokemon Tower (in-town)
    ("lavender", "route10"),
    ("lavender", "pokemon_tower"),
    # Route 10: Rock Tunnel (cave), Power Plant (surf), Route 9 (N)
    ("route10", "rock_tunnel"),
    ("route10", "power_plant"),
    ("route9", "route10"),
    # Southern sea loop: Route 19 <-> Route 20 (Seafoam) <-> Cinnabar <-> Route 21 <-> Pallet
    ("route19", "route20"),
    ("route20", "seafoam_islands"),
    ("route20", "cinnabar"),
    ("cinnabar", "route21"),
    ("cinnabar", "pokemon_mansion"),
    ("route21", "pallet"),
    # West to the League: Route 22 <-> Route 23 <-> Victory Road <-> Indigo Plateau
    ("route22", "route23"),
    ("route23", "victory_road"),
    ("victory_road", "indigo_plateau"),
]


def build():
    node_ids = [n[0] for n in NODES]
    idset = set(node_ids)

    # Validate: no duplicate node ids
    assert len(node_ids) == len(idset), "duplicate node id detected"

    # Validate: edges reference known nodes, no self-loops, no duplicates
    seen = set()
    norm_edges = []
    for a, b in EDGES:
        assert a in idset, f"edge endpoint not a node: {a}"
        assert b in idset, f"edge endpoint not a node: {b}"
        assert a != b, f"self-loop edge: {a}"
        key = tuple(sorted((a, b)))
        assert key not in seen, f"duplicate edge: {key}"
        seen.add(key)
        norm_edges.append([a, b])

    data = {
        "_meta": {
            "region": "Kanto",
            "basis": "Gen-1 (Pokemon Red/Blue/Yellow) canonical overworld map",
            "graph": "undirected; each edge listed once; connected",
            "purpose": "BFS proximity: shortest hop-distance from any town to any catch-location",
            "typeTaxonomy": {
                "town": "towns & cities (incl. Indigo Plateau)",
                "route": "land routes you walk",
                "water": "surf-only sea routes (19, 20, 21)",
                "cave": "natural notable areas: forest, caves, islands, Safari Zone, Victory Road",
                "building": "man-made wild-Pokemon areas: Pokemon Tower, Power Plant, Pokemon Mansion",
            },
            "modelingNotes": [
                "Viridian Forest sits on Route 2 between Viridian and Pewter; modeled route2 -> viridian_forest -> pewter.",
                "Mt. Moon bridges Route 3 and Route 4.",
                "Rock Tunnel and Power Plant both hang off Route 10 (Power Plant via Surf); Route 9 joins Route 10's north end.",
                "Diglett's Cave links Route 2 (north entrance, near Pewter) and Route 11 (south, near Vermilion).",
                "Victory Road is the required cave between Route 23 and Indigo Plateau.",
                "Seafoam Islands sit on the Route 20 sea path; Cerulean Cave is reached by Surf from Cerulean.",
                "Saffron's four gates connect Routes 5/6/7/8; Underground Path shortcuts are omitted (redundant for adjacency).",
                "Route 25 ends at Bill's house (no wild encounters there) but the route itself has catchable Pokemon, so it is kept as a leaf node.",
            ],
        },
        "nodes": [{"id": i, "name": n, "type": t} for (i, n, t) in NODES],
        "edges": norm_edges,
    }
    return data, node_ids, norm_edges


def bfs_connected(node_ids, edges):
    adj = {i: [] for i in node_ids}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    start = node_ids[0]
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nb in adj[cur]:
            if nb not in seen:
                seen.add(nb)
                q.append(nb)
    return seen, adj


def main():
    data, node_ids, edges = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=True)
        f.write("\n")

    # Verify parse
    with open(OUT) as f:
        reloaded = json.load(f)

    # Verify connectivity
    seen, adj = bfs_connected(node_ids, edges)
    connected = len(seen) == len(node_ids)
    unreached = sorted(set(node_ids) - seen)

    # Sample BFS distances from Pallet Town
    def bfs_dist(src):
        dist = {src: 0}
        q = deque([src])
        while q:
            c = q.popleft()
            for nb in adj[c]:
                if nb not in dist:
                    dist[nb] = dist[c] + 1
                    q.append(nb)
        return dist

    dpallet = bfs_dist("pallet")

    type_counts = {}
    for n in data["nodes"]:
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1

    print("=== kanto_connectivity.json verification ===")
    print(f"path                : {OUT}")
    print(f"nodes               : {len(data['nodes'])}")
    print(f"edges               : {len(data['edges'])}")
    print(f"types               : {type_counts}")
    print(f"json reparse        : ok ({len(reloaded['nodes'])} nodes)")
    print(f"connected           : {connected}")
    if not connected:
        print(f"UNREACHED           : {unreached}")
    ecc = max(dpallet.values())
    farthest = sorted([k for k, v in dpallet.items() if v == ecc])
    print(f"BFS from pallet: max hop-distance = {ecc}, farthest = {farthest}")
    # A few spot distances
    for t in ["mt_moon", "safari_zone", "cerulean_cave", "power_plant", "indigo_plateau"]:
        print(f"  dist(pallet -> {t}) = {dpallet.get(t)}")
    assert connected, "GRAPH NOT CONNECTED"
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
