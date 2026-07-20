#!/usr/bin/env python3
"""Build connectivity_sinnoh.json — Sinnoh (Gen 4) route/town graph.

Unlike Kanto/Johto/Hoenn (pret decompilations), Sinnoh's adjacency is encoded
here from the Platinum region layout as an original schematic; coordinates are
normalized (0..1) to match draw_sinnoh_map.py. type 'water' = Surf-gated
(open-sea routes + lake interiors), which the optimizer's obtainability model
treats as unreachable on foot.

Output: ../../app/data/connectivity_sinnoh.json  (compact single line)
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "app/data/connectivity_sinnoh.json"

# (id, name, type, x, y)
NODES = [
    ("twinleaf_town", "Twinleaf Town", "town", 0.09, 0.85),
    ("sandgem_town", "Sandgem Town", "town", 0.20, 0.86),
    ("jubilife_city", "Jubilife City", "town", 0.20, 0.66),
    ("oreburgh_city", "Oreburgh City", "town", 0.42, 0.68),
    ("floaroma_town", "Floaroma Town", "town", 0.25, 0.40),
    ("eterna_city", "Eterna City", "town", 0.40, 0.22),
    ("hearthome_city", "Hearthome City", "town", 0.55, 0.58),
    ("solaceon_town", "Solaceon Town", "town", 0.63, 0.42),
    ("veilstone_city", "Veilstone City", "town", 0.71, 0.58),
    ("pastoria_city", "Pastoria City", "town", 0.58, 0.76),
    ("celestic_town", "Celestic Town", "town", 0.58, 0.28),
    ("canalave_city", "Canalave City", "town", 0.05, 0.56),
    ("snowpoint_city", "Snowpoint City", "town", 0.57, 0.06),
    ("sunyshore_city", "Sunyshore City", "town", 0.85, 0.70),
    ("pokemon_league", "Pokemon League", "town", 0.95, 0.50),
    ("route201", "Route 201", "route", 0.15, 0.83),
    ("route202", "Route 202", "route", 0.24, 0.76),
    ("route203", "Route 203", "route", 0.31, 0.64),
    ("route204", "Route 204", "route", 0.28, 0.50),
    ("route205", "Route 205", "route", 0.33, 0.31),
    ("route206", "Route 206", "route", 0.45, 0.46),
    ("route207", "Route 207", "route", 0.46, 0.58),
    ("route208", "Route 208", "route", 0.52, 0.52),
    ("route209", "Route 209", "route", 0.60, 0.50),
    ("route210", "Route 210", "route", 0.57, 0.34),
    ("route211", "Route 211", "route", 0.49, 0.26),
    ("route212", "Route 212", "route", 0.56, 0.68),
    ("route213", "Route 213", "route", 0.66, 0.76),
    ("route214", "Route 214", "route", 0.72, 0.66),
    ("route215", "Route 215", "route", 0.63, 0.60),
    ("route216", "Route 216", "route", 0.55, 0.16),
    ("route217", "Route 217", "route", 0.56, 0.10),
    ("route218", "Route 218", "water", 0.12, 0.62),
    ("route219", "Route 219", "water", 0.12, 0.92),
    ("route221", "Route 221", "water", 0.06, 0.72),
    ("route222", "Route 222", "route", 0.79, 0.72),
    ("route223", "Route 223", "water", 0.92, 0.60),
    ("route224", "Route 224", "water", 0.96, 0.42),
    ("route225", "Route 225", "route", 0.98, 0.34),
    ("route210s", "Route 210 (S)", "route", 0.60, 0.44),
    ("oreburgh_gate", "Oreburgh Gate", "cave", 0.37, 0.66),
    ("oreburgh_mine", "Oreburgh Mine", "cave", 0.45, 0.72),
    ("ravaged_path", "Ravaged Path", "cave", 0.30, 0.56),
    ("valley_windworks", "Valley Windworks", "route", 0.30, 0.46),
    ("eterna_forest", "Eterna Forest", "cave", 0.34, 0.29),
    ("old_chateau", "Old Chateau", "cave", 0.36, 0.25),
    ("wayward_cave", "Wayward Cave", "cave", 0.45, 0.52),
    ("mt_coronet", "Mt. Coronet", "cave", 0.50, 0.40),
    ("lost_tower", "Lost Tower", "cave", 0.64, 0.48),
    ("solaceon_ruins", "Solaceon Ruins", "cave", 0.67, 0.40),
    ("great_marsh", "Great Marsh", "cave", 0.55, 0.72),
    ("fuego_ironworks", "Fuego Ironworks", "cave", 0.19, 0.36),
    ("lake_verity", "Lake Verity", "water", 0.10, 0.78),
    ("lake_valor", "Lake Valor", "water", 0.74, 0.78),
    ("lake_acuity", "Lake Acuity", "water", 0.55, 0.12),
    ("victory_road_sinnoh", "Victory Road", "cave", 0.93, 0.55),
    ("iron_island", "Iron Island", "cave", 0.02, 0.46),
    ("snowpoint_temple", "Snowpoint Temple", "cave", 0.60, 0.04),
    ("maniac_tunnel", "Maniac Tunnel", "cave", 0.75, 0.64),
]

EDGES = [
    ("twinleaf_town", "route201"), ("route201", "sandgem_town"), ("route201", "lake_verity"),
    ("sandgem_town", "route202"), ("route202", "jubilife_city"),
    ("jubilife_city", "route203"), ("jubilife_city", "route218"), ("route218", "canalave_city"),
    ("route203", "oreburgh_gate"), ("oreburgh_gate", "oreburgh_city"), ("oreburgh_city", "oreburgh_mine"),
    ("jubilife_city", "route204"), ("route204", "ravaged_path"), ("route204", "floaroma_town"),
    ("floaroma_town", "valley_windworks"), ("floaroma_town", "route205"), ("route205", "fuego_ironworks"),
    ("route205", "eterna_forest"), ("eterna_forest", "old_chateau"), ("eterna_forest", "eterna_city"),
    ("eterna_city", "route211"), ("route211", "mt_coronet"), ("route211", "celestic_town"),
    ("eterna_city", "route206"), ("route206", "wayward_cave"), ("route206", "route207"),
    ("route207", "oreburgh_city"), ("route207", "mt_coronet"),
    ("route208", "hearthome_city"), ("route208", "mt_coronet"),
    ("hearthome_city", "route209"), ("route209", "lost_tower"), ("route209", "solaceon_town"),
    ("solaceon_town", "solaceon_ruins"), ("solaceon_town", "route210"), ("route210", "celestic_town"),
    ("solaceon_town", "route210s"), ("route210s", "route215"),
    ("hearthome_city", "route215"), ("route215", "veilstone_city"),
    ("veilstone_city", "route214"), ("route214", "maniac_tunnel"), ("route214", "route213"),
    ("route213", "pastoria_city"), ("pastoria_city", "great_marsh"),
    ("pastoria_city", "route212"), ("route212", "hearthome_city"),
    ("route213", "lake_valor"), ("lake_valor", "route222"),
    ("route222", "sunyshore_city"), ("sunyshore_city", "route223"), ("route223", "victory_road_sinnoh"),
    ("victory_road_sinnoh", "pokemon_league"), ("pokemon_league", "route224"), ("route224", "route225"),
    ("celestic_town", "route211"),
    ("celestic_town", "route210"), ("hearthome_city", "route208"),
    ("snowpoint_city", "route217"), ("route217", "route216"), ("route216", "route211"),
    ("snowpoint_city", "lake_acuity"), ("route217", "lake_acuity"), ("snowpoint_city", "snowpoint_temple"),
    ("canalave_city", "route219"), ("route219", "route221"), ("route221", "iron_island"),
    ("canalave_city", "iron_island"),
    ("route213", "route222"),  # walkable coastal link (routes 213/222 are beaches, not open sea)
]

nodes = [{"id": i, "name": n, "type": t, "x": x, "y": y} for (i, n, t, x, y) in NODES]
out = {
    "_meta": {"region": "Sinnoh",
              "basis": "Pokemon Platinum region geography; original schematic layout. type 'water' = Surf-gated."},
    "nodes": nodes,
    "edges": [list(e) for e in EDGES],
}
OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"wrote {OUT}  ({len(nodes)} nodes, {len(EDGES)} edges)")
