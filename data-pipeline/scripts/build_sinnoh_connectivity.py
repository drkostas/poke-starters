#!/usr/bin/env python3
"""Build connectivity_sinnoh.json - Sinnoh (Gen 4) route/town graph.

Adjacency is encoded from the Platinum region layout. Coordinates are normalized
(0..1) against the real Sinnoh Town Map (app/maps/sinnoh.png): town and lake nodes
sit on their map markers, and route/cave nodes sit on the road pixels. type 'water'
= Surf-gated (open-sea routes + lake interiors), treated as unreachable on foot.
Run route_edges.py afterwards to (re)compute the `edgePaths` that trace the roads;
this script only emits nodes + edges. Output: ../../app/data/connectivity_sinnoh.json
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "app/data/connectivity_sinnoh.json"

# (id, name, type, x, y) - x,y normalized 0..1, on app/maps/sinnoh.png
NODES = [
    ("twinleaf_town", "Twinleaf Town", "town", 0.25, 0.84),
    ("sandgem_town", "Sandgem Town", "town", 0.3, 0.79),
    ("jubilife_city", "Jubilife City", "town", 0.298, 0.71),
    ("oreburgh_city", "Oreburgh City", "town", 0.41, 0.71),
    ("floaroma_town", "Floaroma Town", "town", 0.303, 0.593),
    ("eterna_city", "Eterna City", "town", 0.41, 0.49),
    ("hearthome_city", "Hearthome City", "town", 0.561, 0.663),
    ("solaceon_town", "Solaceon Town", "town", 0.632, 0.616),
    ("veilstone_city", "Veilstone City", "town", 0.746, 0.566),
    ("pastoria_city", "Pastoria City", "town", 0.667, 0.788),
    ("celestic_town", "Celestic Town", "town", 0.545, 0.488),
    ("canalave_city", "Canalave City", "town", 0.19, 0.65),
    ("snowpoint_city", "Snowpoint City", "town", 0.462, 0.18),
    ("sunyshore_city", "Sunyshore City", "town", 0.879, 0.725),
    ("pokemon_league", "Pokemon League", "town", 0.857, 0.519),
    ("route201", "Route 201", "route", 0.2635, 0.7958),
    ("route202", "Route 202", "route", 0.2769, 0.7773),
    ("route203", "Route 203", "route", 0.3327, 0.71),
    ("route204", "Route 204", "route", 0.3, 0.6497),
    ("route205", "Route 205", "route", 0.325, 0.5267),
    ("route206", "Route 206", "route", 0.4269, 0.5963),
    ("route207", "Route 207", "route", 0.4404, 0.6241),
    ("route208", "Route 208", "route", 0.5192, 0.5545),
    ("route209", "Route 209", "route", 0.6135, 0.6659),
    ("route210", "Route 210", "route", 0.5192, 0.5545),
    ("route211", "Route 211", "route", 0.4904, 0.4826),
    ("route212", "Route 212", "route", 0.6135, 0.6659),
    ("route213", "Route 213", "route", 0.7635, 0.6636),
    ("route214", "Route 214", "route", 0.7635, 0.6566),
    ("route215", "Route 215", "route", 0.6615, 0.6218),
    ("route216", "Route 216", "route", 0.4731, 0.3689),
    ("route217", "Route 217", "route", 0.4077, 0.239),
    ("route218", "Route 218", "water", 0.244, 0.68),
    ("route219", "Route 219", "water", 0.19, 0.65),
    ("route221", "Route 221", "water", 0.19, 0.65),
    ("route222", "Route 222", "route", 0.775, 0.7378),
    ("route223", "Route 223", "water", 0.872, 0.656),
    ("route224", "Route 224", "water", 0.857, 0.519),
    ("route225", "Route 225", "route", 0.8865, 0.4942),
    ("route210s", "Route 210 (S)", "route", 0.6135, 0.6659),
    ("oreburgh_gate", "Oreburgh Gate", "cave", 0.35, 0.71),
    ("oreburgh_mine", "Oreburgh Mine", "cave", 0.4673, 0.7425),
    ("ravaged_path", "Ravaged Path", "cave", 0.3, 0.6497),
    ("valley_windworks", "Valley Windworks", "route", 0.2808, 0.5754),
    ("eterna_forest", "Eterna Forest", "cave", 0.3423, 0.5035),
    ("old_chateau", "Old Chateau", "cave", 0.3173, 0.5383),
    ("wayward_cave", "Wayward Cave", "cave", 0.4904, 0.4826),
    ("mt_coronet", "Mt. Coronet", "cave", 0.5192, 0.5568),
    ("lost_tower", "Lost Tower", "cave", 0.6135, 0.6659),
    ("solaceon_ruins", "Solaceon Ruins", "cave", 0.6981, 0.6311),
    ("great_marsh", "Great Marsh", "cave", 0.7173, 0.7796),
    ("fuego_ironworks", "Fuego Ironworks", "cave", 0.3, 0.6473),
    ("lake_verity", "Lake Verity", "water", 0.22, 0.8),
    ("lake_valor", "Lake Valor", "water", 0.732, 0.722),
    ("lake_acuity", "Lake Acuity", "water", 0.4, 0.18),
    ("victory_road_sinnoh", "Victory Road", "cave", 0.8558, 0.5847),
    ("iron_island", "Iron Island", "cave", 0.1769, 0.6914),
    ("snowpoint_temple", "Snowpoint Temple", "cave", 0.519, 0.14),
    ("maniac_tunnel", "Maniac Tunnel", "cave", 0.7135, 0.6961),
]

EDGES = [
    ("twinleaf_town", "route201"), ("route201", "sandgem_town"), ("route201", "lake_verity"),
    ("sandgem_town", "route202"), ("route202", "jubilife_city"), ("jubilife_city", "route203"),
    ("jubilife_city", "route218"), ("route218", "canalave_city"), ("route203", "oreburgh_gate"),
    ("oreburgh_gate", "oreburgh_city"), ("oreburgh_city", "oreburgh_mine"), ("jubilife_city", "route204"),
    ("route204", "ravaged_path"), ("route204", "floaroma_town"), ("floaroma_town", "valley_windworks"),
    ("floaroma_town", "route205"), ("route205", "fuego_ironworks"), ("route205", "eterna_forest"),
    ("eterna_forest", "old_chateau"), ("eterna_forest", "eterna_city"), ("eterna_city", "route211"),
    ("route211", "mt_coronet"), ("route211", "celestic_town"), ("eterna_city", "route206"),
    ("route206", "wayward_cave"), ("route206", "route207"), ("route207", "oreburgh_city"),
    ("route207", "mt_coronet"), ("route208", "hearthome_city"), ("route208", "mt_coronet"),
    ("hearthome_city", "route209"), ("route209", "lost_tower"), ("route209", "solaceon_town"),
    ("solaceon_town", "solaceon_ruins"), ("solaceon_town", "route210"), ("route210", "celestic_town"),
    ("solaceon_town", "route210s"), ("route210s", "route215"), ("hearthome_city", "route215"),
    ("route215", "veilstone_city"), ("veilstone_city", "route214"), ("route214", "maniac_tunnel"),
    ("route214", "route213"), ("route213", "pastoria_city"), ("pastoria_city", "great_marsh"),
    ("pastoria_city", "route212"), ("route212", "hearthome_city"), ("pastoria_city", "route213"),
    ("route213", "lake_valor"), ("lake_valor", "route222"), ("route222", "sunyshore_city"),
    ("sunyshore_city", "route223"), ("route223", "victory_road_sinnoh"), ("victory_road_sinnoh", "pokemon_league"),
    ("pokemon_league", "route224"), ("route224", "route225"), ("celestic_town", "route211"),
    ("celestic_town", "route210"), ("hearthome_city", "route208"), ("snowpoint_city", "route217"),
    ("route217", "route216"), ("route216", "route211"), ("snowpoint_city", "lake_acuity"),
    ("route217", "lake_acuity"), ("snowpoint_city", "snowpoint_temple"), ("canalave_city", "route219"),
    ("route219", "route221"), ("route221", "iron_island"), ("canalave_city", "iron_island"),
    ("route213", "route222"),
]

nodes = [{"id": i, "name": n, "type": t, "x": x, "y": y} for (i, n, t, x, y) in NODES]
out = {
    "_meta": {"region": "Sinnoh",
              "basis": "Pokemon Platinum Sinnoh Town Map (fan artwork by ICEREG1992/pkmnmap4, used with permission). Town/lake nodes on map markers; route/cave nodes on road pixels; edgePaths (added by route_edges.py) trace the roads. type 'water' = Surf-gated."},
    "nodes": nodes,
    "edges": [list(e) for e in EDGES],
}
existing = json.loads(OUT.read_text()) if OUT.exists() else {}
if "edgePaths" in existing:
    out["edgePaths"] = existing["edgePaths"]  # preserve routed paths on re-run
OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"wrote {OUT}  ({len(nodes)} nodes, {len(EDGES)} edges)")
