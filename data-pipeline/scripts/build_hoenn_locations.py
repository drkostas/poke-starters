#!/usr/bin/env python3
"""Build locations_hoenn.json + hoenn NODE_XY from pokeemerald disassembly.

Sources (ROM-accurate): pret/pokeemerald
  - src/data/wild_encounters.json           (per-map land/water/rock_smash/fishing)
  - src/data/region_map/region_map_sections.json (region-map grid coords per MAPSEC)
Slot weights come from the encounter file header:
  land [20,20,10,10,10,10,5,5,4,4,1,1]  water/rock_smash [60,30,5,4,1]
  fishing old[70,30] good[60,20,20] super[40,40,15,4,1]
Species are pokeemerald national-dex constants. Output schema matches Kanto/Johto.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "output"))
RAW = os.path.normpath(os.path.join(HERE, "..", "raw", "gen3"))

pk = json.load(open(f"{OUT}/pokemon.json"))
enc_data = json.load(open(f"{RAW}/wild_encounters.json"))
sections = json.load(open(f"{RAW}/region_map_sections.json"))["map_sections"]

# ---- species constant -> national dex ----------------------------------
def build_name_map():
    m = {}
    for dex, v in pk.items():
        m[re.sub(r'[^A-Z0-9]', '', v["name"].upper())] = int(dex)
    m.update({"NIDORANF": 29, "NIDORANM": 32, "FARFETCHD": 83, "MRMIME": 122, "HOOH": 250,
              "DEOXYS": 386, "UNOWN": 201})
    return m
NAME2DEX = build_name_map()
def sp_to_dex(sp):
    key = re.sub(r'[^A-Z0-9]', '', sp.replace("SPECIES_", "").upper())
    return NAME2DEX.get(key)

def tier_from_pct(pct):
    if pct >= 15: return "common"
    if pct >= 5:  return "uncommon"
    if pct >= 1:  return "rare"
    return "very_rare"

# ---- MAPSEC node table (towns/routes/landmarks with coords) --------------
GRID_W, GRID_H = 28, 15
SKIP_SEC = {  # not overworld catch nodes / duplicate coords
    "MAPSEC_NONE", "MAPSEC_BATTLE_FRONTIER", "MAPSEC_ARTISAN_CAVE", "MAPSEC_TRAINER_HILL",
    "MAPSEC_MIRAGE_ISLAND", "MAPSEC_MIRAGE_TOWER", "MAPSEC_SOUTHERN_ISLAND",
    "MAPSEC_AQUA_HIDEOUT_OLD", "MAPSEC_DESERT_UNDERPASS", "MAPSEC_ALTERING_CAVE",
    "MAPSEC_SEALED_CHAMBER", "MAPSEC_SCORCHED_SLAB", "MAPSEC_ANCIENT_TOMB",
    "MAPSEC_DESERT_RUINS", "MAPSEC_ISLAND_CAVE", "MAPSEC_MAGMA_HIDEOUT", "MAPSEC_AQUA_HIDEOUT",
}
def sec_type(secid, name):
    if secid.endswith("_TOWN") or secid.endswith("_CITY"): return "town"
    if "ROUTE_" in secid: return "route"
    return "cave"

nodes = {}      # node_id -> {name, type, secid, cx, cy}
sec_to_node = {}
for s in sections:
    if "x" not in s: continue
    sid = s["id"]
    if sid in SKIP_SEC: continue
    if sid.startswith("MAPSEC_UNDERWATER"): continue
    if sid in ("MAPSEC_METEOR_FALLS2", "MAPSEC_FIERY_PATH2", "MAPSEC_JAGGED_PASS2"):
        continue  # secondary coord tiles for the same landmark — keep primary only
    node = sid.replace("MAPSEC_", "").lower()
    # route_101 -> route101
    node = re.sub(r'route_(\d+)', r'route\1', node)
    cx = s["x"] + s.get("width", 1) / 2.0
    cy = s["y"] + s.get("height", 1) / 2.0
    nodes[node] = {"name": s["name"].title().replace("'S", "'s"), "type": sec_type(sid, s["name"]),
                   "secid": sid, "cx": cx, "cy": cy}
    sec_to_node[re.sub(r'[^A-Z0-9]', '', sid.replace("MAPSEC_", ""))] = node

# ---- resolve an encounter MAP_ label to a node (longest MAPSEC prefix) ----
def resolve_map(maplabel):
    key = re.sub(r'[^A-Z0-9]', '', maplabel.replace("MAP_", ""))
    best = None
    for secnorm, node in sec_to_node.items():
        if key.startswith(secnorm):
            if best is None or len(secnorm) > len(best[0]):
                best = (secnorm, node)
    return best[1] if best else None

# ---- slot weights -------------------------------------------------------
LAND_W = [20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1]
WATER_W = [60, 30, 5, 4, 1]
ROD = {"old_rod": (2, [70, 30]), "good_rod": (3, [60, 20, 20]), "super_rod": (5, [40, 40, 15, 4, 1])}

def slot_species(mons, weights):
    """mons list -> {dex:{pct,min,max}} using positional weights."""
    agg = {}
    for i, mon in enumerate(mons):
        if i >= len(weights): break
        dex = sp_to_dex(mon["species"])
        if dex is None: continue
        a = agg.setdefault(dex, {"pct": 0, "min": mon["min_level"], "max": mon["max_level"]})
        a["pct"] += weights[i]
        a["min"] = min(a["min"], mon["min_level"]); a["max"] = max(a["max"], mon["max_level"])
    return agg

locations = {}
unresolved = set(); unmapped_sp = set()

def add(node, method, agg):
    if not agg: return
    n = nodes.get(node)
    if not n: return
    loc = locations.setdefault(node, {"name": n["name"], "type": n["type"], "catchable": []})
    idx = {(c["dexNumber"], c["method"]): c for c in loc["catchable"]}
    order = {"common": 0, "uncommon": 1, "rare": 2, "very_rare": 3}
    for dex, d in agg.items():
        tier = tier_from_pct(d["pct"]); key = (dex, method)
        if key in idx:
            c = idx[key]
            if order[tier] < order[c["rarityTier"]]: c["rarityTier"] = tier
            c["minLevel"] = min(c["minLevel"], d["min"]); c["maxLevel"] = max(c["maxLevel"], d["max"])
        else:
            c = {"dexNumber": dex, "name": pk[str(dex)]["name"], "method": method,
                 "version": "emerald", "rarityTier": tier, "minLevel": d["min"], "maxLevel": d["max"],
                 "catchRate": pk[str(dex)]["catchRate"], "catchRateExempt": False}
            loc["catchable"].append(c); idx[key] = c

for e in enc_data["wild_encounter_groups"][0]["encounters"]:
    node = resolve_map(e["map"])
    if node is None:
        unresolved.add(e["map"]); continue
    if "land_mons" in e:
        add(node, "grass", slot_species(e["land_mons"]["mons"], LAND_W))
    if "water_mons" in e:
        add(node, "surf", slot_species(e["water_mons"]["mons"], WATER_W))
    if "rock_smash_mons" in e:
        add(node, "rock_smash", slot_species(e["rock_smash_mons"]["mons"], WATER_W))
    if "fishing_mons" in e:
        mons = e["fishing_mons"]["mons"]
        for rod, (cnt, w) in ROD.items():
            start = {"old_rod": 0, "good_rod": 2, "super_rod": 5}[rod]
            add(node, "fishing", slot_species(mons[start:start + cnt], w))
    for mon in e.get("land_mons", {}).get("mons", []) + e.get("water_mons", {}).get("mons", []):
        if sp_to_dex(mon["species"]) is None: unmapped_sp.add(mon["species"])

order = {"common": 0, "uncommon": 1, "rare": 2, "very_rare": 3}
for loc in locations.values():
    loc["catchable"].sort(key=lambda c: (order[c["rarityTier"]], c["dexNumber"]))

locations["_meta"] = {
    "region": "Hoenn",
    "basis": "Pokemon Emerald (Gen 3), pokeemerald wild_encounters.json; rarity from ROM slot weights "
             "land[20,20,10,10,10,10,5,5,4,4,1,1]/water[60,30,5,4,1]/fishing per-rod.",
    "keyedBy": "connectivity node id (see connectivity_hoenn.json)",
    "schema": "location -> {name, type, catchable:[{dexNumber, name, method, version, rarityTier, minLevel, maxLevel, catchRate, catchRateExempt}]}",
    "methods": ["grass", "surf", "rock_smash", "fishing"],
}
json.dump(locations, open(f"{OUT}/locations_hoenn.json", "w"), indent=1)

# ---- NODE_XY (grid center normalized) -----------------------------------
node_xy = {}
for node, n in nodes.items():
    node_xy[node] = [round(n["cx"] / GRID_W, 3), round(n["cy"] / GRID_H, 3)]
json.dump({"nodeXY": node_xy}, open(f"{OUT}/hoenn_node_xy.json", "w"), indent=1)

# ---- report -------------------------------------------------------------
enc_nodes = sorted(k for k in locations if k != "_meta")
total = sum(len(locations[n]["catchable"]) for n in enc_nodes)
uniq = sorted({c["dexNumber"] for n in enc_nodes for c in locations[n]["catchable"]})
print(f"Hoenn locations: {len(enc_nodes)} nodes, {total} catchable entries, {len(uniq)} unique species")
print(f"dex range: {min(uniq)}-{max(uniq)}")
print("node table size (for graph):", len(nodes))
if unresolved: print("UNRESOLVED encounter maps:", sorted(unresolved))
if unmapped_sp: print("UNMAPPED species:", sorted(unmapped_sp))
