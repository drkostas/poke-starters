#!/usr/bin/env python3
"""Build locations_johto.json from pokecrystal Johto wild-encounter disassembly.

Source (ROM-accurate): pret/pokecrystal data/wild/johto_grass.asm + johto_water.asm
Gen-2 slot probabilities (from data/wild/probabilities.asm):
  grass 7 slots -> [30,30,20,10,5,4,1]   water 3 slots -> [60,30,10]
Rarity tier = best (max) per-species encounter chance across morn/day/nite.
Species names are pokecrystal constants (national-dex order 1..251).
Output schema matches locations_kanto.json.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "output"))
RAW = os.path.normpath(os.path.join(HERE, "..", "raw", "gen2"))

GRASS_W = [30, 30, 20, 10, 5, 4, 1]
WATER_W = [60, 30, 10]

pk = json.load(open(f"{OUT}/pokemon.json"))

# ---- species constant -> national dex ----------------------------------
def build_name_map():
    m = {}
    for dex, v in pk.items():
        key = re.sub(r'[^A-Z0-9]', '', v["name"].upper())
        m[key] = int(dex)
    # pokecrystal constant spellings that don't normalize cleanly
    special = {
        "NIDORANF": 29, "NIDORANM": 32, "FARFETCHD": 83, "MRMIME": 122,
        "HOOH": 250, "PORYGON": 137, "MIMEJR": 439,
    }
    m.update(special)
    return m
NAME2DEX = build_name_map()

def const_to_dex(const):
    key = re.sub(r'[^A-Z0-9]', '', const.upper())
    if key in NAME2DEX:
        return NAME2DEX[key]
    return None

def tier_from_pct(pct):
    if pct >= 15: return "common"
    if pct >= 5:  return "uncommon"
    if pct >= 1:  return "rare"
    return "very_rare"

# ---- map label -> graph node id ----------------------------------------
def johto_node(L):
    if L.startswith('SPROUT_TOWER'): return 'sprout_tower', 'building'
    if L.startswith('TIN_TOWER') or L.startswith('BELL_TOWER'): return 'tin_tower', 'building'
    if L.startswith('BURNED_TOWER'): return 'burned_tower', 'building'
    if L.startswith('RUINS_OF_ALPH'): return 'ruins_of_alph', 'cave'
    if L.startswith('UNION_CAVE'): return 'union_cave', 'cave'
    if L.startswith('SLOWPOKE_WELL'): return 'slowpoke_well', 'cave'
    if L == 'ILEX_FOREST': return 'ilex_forest', 'cave'
    if L == 'NATIONAL_PARK': return 'national_park', 'cave'
    if L.startswith('MOUNT_MORTAR'): return 'mt_mortar', 'cave'
    if L.startswith('ICE_PATH'): return 'ice_path', 'cave'
    if L.startswith('WHIRL_ISLAND'): return 'whirl_islands', 'cave'
    if L.startswith('SILVER_CAVE'): return None, None  # Mt Silver = Kanto-border postgame; excluded
    if L.startswith('DARK_CAVE'): return 'dark_cave', 'cave'
    if L.startswith('DRAGONS_DEN'): return 'dragons_den', 'cave'
    if L == 'LAKE_OF_RAGE': return 'lake_of_rage', 'water'
    if L == 'OLIVINE_PORT': return 'olivine', 'town'
    m = re.match(r'ROUTE_(\d+)$', L)
    if m: return 'route' + m.group(1), 'route'
    m = re.match(r'([A-Z_]+)_(CITY|TOWN)$', L)
    if m:
        city = {'NEW_BARK': 'new_bark', 'CHERRYGROVE': 'cherrygrove', 'VIOLET': 'violet',
                'AZALEA': 'azalea', 'GOLDENROD': 'goldenrod', 'ECRUTEAK': 'ecruteak',
                'OLIVINE': 'olivine', 'CIANWOOD': 'cianwood', 'MAHOGANY': 'mahogany',
                'BLACKTHORN': 'blackthorn'}.get(m.group(1))
        return (city, 'town') if city else (None, None)
    return None, None

NODE_NAMES = {
    'new_bark': 'New Bark Town', 'cherrygrove': 'Cherrygrove City', 'violet': 'Violet City',
    'azalea': 'Azalea Town', 'goldenrod': 'Goldenrod City', 'ecruteak': 'Ecruteak City',
    'olivine': 'Olivine City', 'cianwood': 'Cianwood City', 'mahogany': 'Mahogany Town',
    'blackthorn': 'Blackthorn City',
    'sprout_tower': 'Sprout Tower', 'tin_tower': 'Bell Tower', 'burned_tower': 'Burned Tower',
    'ruins_of_alph': 'Ruins of Alph', 'union_cave': 'Union Cave', 'slowpoke_well': 'Slowpoke Well',
    'ilex_forest': 'Ilex Forest', 'national_park': 'National Park', 'mt_mortar': 'Mt. Mortar',
    'ice_path': 'Ice Path', 'whirl_islands': 'Whirl Islands', 'dark_cave': 'Dark Cave',
    'dragons_den': "Dragon's Den", 'lake_of_rage': 'Lake of Rage',
}
def route_name(node):
    m = re.match(r'route(\d+)', node)
    return f"Route {m.group(1)}" if m else NODE_NAMES.get(node, node)

# ---- parsers ------------------------------------------------------------
def parse_grass(text):
    """-> list of (label, [ (dex, minL, maxL, best_pct) ])"""
    out = {}
    blocks = re.split(r'def_grass_wildmons ', text)[1:]
    for b in blocks:
        label = b.split('\n', 1)[0].strip()
        # collect all `db LEVEL, SPECIES` lines in order (21 = 3 times x 7 slots)
        rows = re.findall(r'db\s+(\d+),\s*([A-Z0-9_]+)\s*$', b, re.M)
        if len(rows) < 21:
            continue
        rows = rows[:21]
        times = [rows[0:7], rows[7:14], rows[14:21]]
        agg = {}  # dex -> {minL,maxL,pct}
        for slots in times:
            per = {}
            for i, (lvl, sp) in enumerate(slots):
                dex = const_to_dex(sp)
                if dex is None: continue
                lvl = int(lvl)
                per.setdefault(dex, {'pct': 0, 'min': lvl, 'max': lvl})
                per[dex]['pct'] += GRASS_W[i]
                per[dex]['min'] = min(per[dex]['min'], lvl)
                per[dex]['max'] = max(per[dex]['max'], lvl)
            for dex, d in per.items():
                a = agg.setdefault(dex, {'pct': 0, 'min': d['min'], 'max': d['max']})
                a['pct'] = max(a['pct'], d['pct'])       # best time-of-day chance
                a['min'] = min(a['min'], d['min'])
                a['max'] = max(a['max'], d['max'])
        out[label] = [(dex, d['min'], d['max'], d['pct'], 'grass') for dex, d in agg.items()]
    return out

def parse_water(text):
    out = {}
    blocks = re.split(r'def_water_wildmons ', text)[1:]
    for b in blocks:
        label = b.split('\n', 1)[0].strip()
        rows = re.findall(r'db\s+(\d+),\s*([A-Z0-9_]+)\s*$', b, re.M)
        if len(rows) < 3:
            continue
        rows = rows[:3]
        agg = {}
        for i, (lvl, sp) in enumerate(rows):
            dex = const_to_dex(sp)
            if dex is None: continue
            lvl = int(lvl)
            a = agg.setdefault(dex, {'pct': 0, 'min': lvl, 'max': lvl})
            a['pct'] += WATER_W[i]
            a['min'] = min(a['min'], lvl); a['max'] = max(a['max'], lvl)
        out[label] = [(dex, d['min'], d['max'], d['pct'], 'surf') for dex, d in agg.items()]
    return out

# ---- assemble -----------------------------------------------------------
grass = parse_grass(open(f"{RAW}/johto_grass.asm").read())
water = parse_water(open(f"{RAW}/johto_water.asm").read())

locations = {}
unresolved = set()

def add(label, entries):
    node, ntype = johto_node(label)
    if node is None:
        unresolved.add(label); return
    loc = locations.setdefault(node, {"name": NODE_NAMES.get(node, route_name(node)),
                                       "type": ntype, "catchable": []})
    # merge: keep best rarity per (dex, method)
    idx = {(c['dexNumber'], c['method']): c for c in loc['catchable']}
    for dex, mn, mx, pct, method in entries:
        tier = tier_from_pct(pct)
        key = (dex, method)
        if key in idx:
            c = idx[key]
            # keep the higher chance (lower tier index)
            order = {"common": 0, "uncommon": 1, "rare": 2, "very_rare": 3}
            if order[tier] < order[c['rarityTier']]:
                c['rarityTier'] = tier
            c['minLevel'] = min(c['minLevel'], mn); c['maxLevel'] = max(c['maxLevel'], mx)
        else:
            c = {"dexNumber": dex, "name": pk[str(dex)]["name"], "method": method,
                 "version": "crystal", "rarityTier": tier, "minLevel": mn, "maxLevel": mx,
                 "catchRate": pk[str(dex)]["catchRate"], "catchRateExempt": False}
            loc['catchable'].append(c); idx[key] = c

for label, entries in grass.items(): add(label, entries)
for label, entries in water.items(): add(label, entries)

# sort catchable by rarity then dex for stable output
order = {"common": 0, "uncommon": 1, "rare": 2, "very_rare": 3}
for loc in locations.values():
    loc['catchable'].sort(key=lambda c: (order[c['rarityTier']], c['dexNumber']))

locations["_meta"] = {
    "region": "Johto",
    "basis": "Pokemon Crystal (Gen 2), pokecrystal ROM disassembly (johto_grass.asm + johto_water.asm); "
             "rarity = best morn/day/nite slot chance via grass[30,30,20,10,5,4,1]/water[60,30,10]",
    "keyedBy": "connectivity node id (see connectivity_johto.json)",
    "schema": "location -> {name, type, catchable:[{dexNumber, name, method, version, rarityTier, minLevel, maxLevel, catchRate, catchRateExempt}]}",
    "methods": ["grass", "surf"],
    "excluded": ["Mt. Silver / Silver Cave (Kanto-border postgame, not Johto-graph adjacent)"],
}

json.dump(locations, open(f"{OUT}/locations_johto.json", "w"), indent=1)

# ---- report -------------------------------------------------------------
nodes = sorted(k for k in locations if k != "_meta")
total = sum(len(locations[n]['catchable']) for n in nodes)
uniq = sorted({c['dexNumber'] for n in nodes for c in locations[n]['catchable']})
print(f"Johto locations: {len(nodes)} nodes, {total} catchable entries, {len(uniq)} unique species")
print("nodes:", nodes)
if unresolved:
    print("UNRESOLVED labels (excluded):", sorted(unresolved))
# sanity: any species that failed to map?
allc = set()
for lab, e in list(grass.items()) + list(water.items()):
    for row in e: allc.add(row[0])
print("dex range:", min(uniq), "-", max(uniq))
