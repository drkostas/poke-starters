#!/usr/bin/env python3
"""Build app-ready locations_kanto.json + connectivity_kanto.json from the four raw Kanto datasets."""
import json, re, os

OUT = "/Users/gkos/Projects/pokemon_fun/data-pipeline/output"

wild = json.load(open(f"{OUT}/kanto_wild_encounters.json"))
special = json.load(open(f"{OUT}/kanto_special_encounters.json"))
conn = json.load(open(f"{OUT}/kanto_connectivity.json"))
catch = json.load(open(f"{OUT}/kanto_catch_rates.json"))["catchRateByDex"]
pk = json.load(open(f"{OUT}/pokemon.json"))

fixes = []
caveats = []
# Gen-1 maps that carry a super-rod fishing-group assignment in pokered but have no water
# tiles, so the fishing is unreachable in-game (verified vs PokeAPI: no red/blue fishing here).
WATERLESS_MAPS = {"Route 4"}

def display_name(dex):
    return pk[str(dex)]["name"]

def norm_ver(v):
    return {"red":"red","blue":"blue","both":"both",
            "Red":"red","Blue":"blue","Red/Blue":"both"}[v]

def tier_from_pct(pct):
    if pct is None: return None
    if pct >= 15: return "common"
    if pct >= 5:  return "uncommon"
    if pct >= 1:  return "rare"
    return "very_rare"

# ---------- node resolvers ----------
NODE_IDS = {n["id"] for n in conn["nodes"]}

def resolve_wild(mapname):
    m = mapname.strip()
    direct = {
        "Pallet Town":"pallet","Viridian City":"viridian","Pewter City":"pewter",
        "Cerulean City":"cerulean","Cerulean Gym":"cerulean",
        "Vermilion City":"vermilion","Vermilion Dock":"vermilion",
        "Lavender Town":"lavender","Celadon City":"celadon","Fuchsia City":"fuchsia",
        "Saffron City":"saffron","Cinnabar Island":"cinnabar","Indigo Plateau":"indigo_plateau",
        "Viridian Forest":"viridian_forest","Diglett's Cave":"digletts_cave",
        "Power Plant":"power_plant",
    }
    if m in direct: return direct[m]
    rm = re.match(r"^Route (\d+)$", m)
    if rm: return "route"+rm.group(1)
    for pref, node in [("Cerulean Cave","cerulean_cave"),("Mt. Moon","mt_moon"),
                       ("Rock Tunnel","rock_tunnel"),("Seafoam Islands","seafoam_islands"),
                       ("Safari Zone","safari_zone"),("Victory Road","victory_road"),
                       ("Pokemon Tower","pokemon_tower"),("Pokemon Mansion","pokemon_mansion")]:
        if m.startswith(pref): return node
    return None  # "Any fishing spot"

def resolve_special(loc):
    if loc.startswith("(unused"): return None
    if loc.startswith("Safari Zone"): return "safari_zone"
    if loc.startswith("Underground Path"): return "route5"  # Route 5 north entrance trade house
    rm = re.match(r"^Route (\d+)\b", loc)
    if rm: return "route"+rm.group(1)
    pref = {
        "Pallet Town":"pallet","Celadon City":"celadon","Saffron City":"saffron",
        "Cinnabar Island":"cinnabar","Cerulean City":"cerulean","Vermilion City":"vermilion",
        "Seafoam Islands":"seafoam_islands","Power Plant":"power_plant",
        "Victory Road":"victory_road","Pokemon Tower":"pokemon_tower","Cerulean Cave":"cerulean_cave",
    }
    for p, node in pref.items():
        if loc.startswith(p): return node
    return None

# ---------- accumulator ----------
# key: (node, dex, method) -> record
acc = {}

def add(node, dex, method, version, minlvl, maxlvl, weight_pct, tier, exempt, note):
    key = (node, dex, method)
    r = acc.get(key)
    if r is None:
        r = {"node":node,"dex":dex,"method":method,"versions":set(),
             "minLevel":None,"maxLevel":None,"bestPct":None,"tier":tier,
             "exempt":exempt,"note":note}
        acc[key] = r
    r["versions"].add(version)
    for lv in (minlvl, maxlvl):
        if lv is not None:
            r["minLevel"] = lv if r["minLevel"] is None else min(r["minLevel"], lv)
            r["maxLevel"] = lv if r["maxLevel"] is None else max(r["maxLevel"], lv)
    if weight_pct is not None:
        if r["bestPct"] is None or weight_pct > r["bestPct"]:
            r["bestPct"] = weight_pct
            r["tier"] = tier_from_pct(weight_pct)
    if note and not r["note"]:
        r["note"] = note

# ---------- fold WILD ----------
water_nodes = set()  # nodes with any surf/super_rod (fishable water)
unmapped_wild = set()
for e in wild:
    method = e["method"]
    ver = norm_ver(e["version"])
    if e["map"] == "Any fishing spot":
        continue  # handled globally below
    node = resolve_wild(e["map"])
    if node is None:
        unmapped_wild.add(e["map"]); continue
    if method in ("surf","super_rod"):
        # Route 4 has NO water tiles in Gen 1 but pokered assigns it super_rod .Group3;
        # the group is unreachable in-game, so drop it (also stops old/good-rod attaching).
        if e["map"] in WATERLESS_MAPS:
            continue
        water_nodes.add(node)
    # aggregate per-species slot weights within this entry
    per = {}
    for s in e["slots"]:
        d = s["dexNumber"]
        p = per.setdefault(d, {"w":0.0,"mn":s["level"],"mx":s["level"]})
        p["w"] += s["slotWeightPct"]
        p["mn"] = min(p["mn"], s["level"]); p["mx"] = max(p["mx"], s["level"])
    is_safari = (node == "safari_zone")
    for d, p in per.items():
        out_method = method
        exempt = False
        note = None
        if is_safari:
            exempt = True
            if method == "grass":
                out_method = "safari"
                note = "Safari Zone walk-in encounter; safari mechanics (bait/rock), no catch-rate roll."
            else:  # super_rod inside safari
                note = "Safari Zone Super Rod; safari mechanics, no catch-rate roll."
        add(node, d, out_method, ver, p["mn"], p["mx"], p["w"],
            tier_from_pct(p["w"]), exempt, note)

# ---------- location-independent Old/Good Rod ----------
# Old Rod (Magikarp) and Good Rod (Poliwag/Goldeen) use fixed ROM tables usable at any
# fishable water tile. Attach to every non-safari node that has water access.
old_rod = next(e for e in wild if e["method"]=="old_rod")
good_rod = next(e for e in wild if e["method"]=="good_rod")
rod_target_nodes = sorted(n for n in water_nodes if n != "safari_zone")
for node in rod_target_nodes:
    for e in (old_rod, good_rod):
        per = {}
        for s in e["slots"]:
            d = s["dexNumber"]
            p = per.setdefault(d, {"w":0.0,"mn":s["level"],"mx":s["level"]})
            p["w"] += s["slotWeightPct"]
            p["mn"] = min(p["mn"], s["level"]); p["mx"] = max(p["mx"], s["level"])
        for d, p in per.items():
            add(node, d, e["method"], "both", p["mn"], p["mx"], p["w"],
                tier_from_pct(p["w"]), False,
                "Location-independent: Old/Good Rod usable at any water tile.")

# ---------- fold SPECIAL ----------
GUARANTEED = {"starter","gift","fossil","game_corner","trade"}
skipped_special = []
for e in special:
    method = e["method"]
    if method == "safari":
        continue  # redundant with wild grass+super_rod (verified superset); dropped to avoid dup
    if "NOT catchable" in (e.get("notes") or ""):
        skipped_special.append((e["name"], e["location"], "not catchable (ghost)"))
        continue
    node = resolve_special(e["location"])
    if node is None:
        skipped_special.append((e["name"], e["location"], "unmapped/unused"))
        continue
    dex = e["dexNumber"]
    ver = norm_ver(e["version"])
    lvl = e["level"]
    if method == "static":
        tier = "static"
    elif method in GUARANTEED:
        tier = "guaranteed"
    else:
        tier = "guaranteed"
    note = None
    if method == "trade":
        mnote = re.search(r"Player GIVES (\w[\w'.♀♂ ]*?), RECEIVES", e["notes"])
        give = mnote.group(1).strip() if mnote else None
        note = "In-game trade" + (f"; give {give}" if give else "") + \
               "; received level = level of the mon you trade in (variable)."
    elif method == "fossil":
        note = "Revived from fossil at Cinnabar Pokemon Lab."
    elif method == "game_corner":
        note = "Game Corner prize (coins, not money)."
    elif method == "gift" and e["name"] == "Magikarp":
        note = "Magikarp salesman; costs ¥500 (scripted purchase)."
    elif method == "gift":
        note = "One-time gift Pokemon."
    elif method == "starter":
        note = "Choose-one starter (rival takes the type-advantaged one)."
    add(node, dex, method, ver, lvl, lvl, None, tier, False, note)

if skipped_special:
    for n, loc, why in skipped_special:
        fixes.append(f"Excluded non-catchable special entry: {n} @ {loc} ({why}).")

# ---------- finalize version collapse + build output ----------
METHOD_ORDER = {"grass":0,"surf":1,"old_rod":2,"good_rod":3,"super_rod":4,"safari":5,
                "static":6,"starter":7,"gift":8,"fossil":9,"game_corner":10,"trade":11}

def final_version(vs):
    if "both" in vs or {"red","blue"} <= vs:
        return "both"
    if vs == {"red"}: return "red"
    if vs == {"blue"}: return "blue"
    return "both"

locations = {}
for n in conn["nodes"]:
    locations[n["id"]] = {"name":n["name"],"type":n["type"],"catchable":[]}

for (node, dex, method), r in acc.items():
    ver = final_version(r["versions"])
    exempt = r["exempt"]
    cr = None if exempt else catch[str(dex)]
    entry = {
        "dexNumber": dex,
        "name": display_name(dex),
        "method": method,
        "version": ver,
        "rarityTier": r["tier"],
        "minLevel": r["minLevel"],
        "maxLevel": r["maxLevel"],
        "catchRate": cr,
        "catchRateExempt": exempt,
    }
    if r["note"]:
        entry["note"] = r["note"]
    locations[node]["catchable"].append(entry)

for node, loc in locations.items():
    loc["catchable"].sort(key=lambda x:(METHOD_ORDER.get(x["method"],99), x["dexNumber"]))

# ---------- metadata + write ----------
locations_out = {
    "_meta": {
        "region": "Kanto",
        "basis": "Pokemon Red/Blue (Gen 1), pokered ROM disassembly; catch rates = Gen-1 base_stats bytes",
        "keyedBy": "connectivity node id (see connectivity_kanto.json)",
        "schema": "location -> {name, type, catchable:[{dexNumber, name, method, version, rarityTier, minLevel, maxLevel, catchRate, catchRateExempt, note?}]}",
        "methods": ["grass","surf","old_rod","good_rod","super_rod","safari","static","starter","gift","fossil","game_corner","trade"],
        "rarityTiers": {
            "common":"aggregated wild slot weight >= 15%",
            "uncommon":"5-14%","rare":"1-4%","very_rare":"<1%",
            "static":"single fixed overworld encounter (catch roll applies)",
            "guaranteed":"received without a catch roll (starter/gift/fossil/game_corner/trade)"
        },
        "versionValues": ["red","blue","both"],
        "notes": [
            "catchRate is the Gen-1 R/B catch-rate byte keyed by National Dex number.",
            "catchRateExempt=true only for Safari Zone: safari mechanics (bait/rock/flee) replace the normal catch-rate roll.",
            "Guaranteed methods (starter/gift/fossil/game_corner/trade) list the species catchRate for reference, but the mon is received without a catch roll.",
            "Old Rod / Good Rod encounters are location-independent (fixed ROM tables); attached to every non-Safari node with fishable water.",
            "Level ranges are aggregated across all floors/sub-areas that map to a node; a species' rarityTier is the best (easiest) tier seen across those sub-areas.",
            "Trade received-mon levels are null: the received Pokemon inherits the level of the mon you trade in."
        ]
    }
}
locations_out.update(locations)

with open(f"{OUT}/locations_kanto.json","w") as f:
    json.dump(locations_out, f, indent=2, ensure_ascii=False)

# ---------- connectivity: clean {nodes, edges} for BFS ----------
connectivity_out = {
    "_meta": {
        "region":"Kanto",
        "graph":"undirected; each edge listed once; fully connected",
        "purpose":"BFS proximity: shortest hop-distance from any town to any catch-location",
        "typeTaxonomy": conn["_meta"]["typeTaxonomy"],
        "modelingNotes": conn["_meta"]["modelingNotes"],
    },
    "nodes": conn["nodes"],
    "edges": conn["edges"],
}
with open(f"{OUT}/connectivity_kanto.json","w") as f:
    json.dump(connectivity_out, f, indent=2, ensure_ascii=False)

# ---------- report ----------
total_entries = sum(len(l["catchable"]) for l in locations.values())
nonempty = sum(1 for l in locations.values() if l["catchable"])
print("unmapped wild maps:", sorted(unmapped_wild))
print("nodes total:", len(locations), "nonempty:", nonempty)
print("catchable entries:", total_entries)
print("edges:", len(conn["edges"]))
print("rod nodes:", rod_target_nodes)
print("skipped special:", skipped_special)
print("distinct rarity tiers:", sorted({e["rarityTier"] for l in locations.values() for e in l["catchable"] if e["rarityTier"]}))
# summary object
summ = {
    "locations": len(locations),
    "catchableEntries": total_entries,
    "nodes": len(conn["nodes"]),
    "edges": len(conn["edges"]),
}
print("SUMMARY:", json.dumps(summ))
