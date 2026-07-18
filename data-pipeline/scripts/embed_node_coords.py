#!/usr/bin/env python3
"""Embed normalized [x,y] map coordinates into each region's connectivity nodes,
so the app can read node.x / node.y uniformly for all three regions.

  Kanto : hand-placed positions on the FRLG Town Map (ported from the app).
  Johto : pokecrystal data/maps/landmarks.asm pixel coords, bbox-fit to johto.png.
  Hoenn : pokeemerald region_map_sections.json grid-rectangle centers.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "output"))
RAW2 = os.path.normpath(os.path.join(HERE, "..", "raw", "gen2"))
RAW3 = os.path.normpath(os.path.join(HERE, "..", "raw", "gen3"))

# ---- Kanto (hand-placed, from the app's tuned FRLG overlay) --------------
KANTO_XY = {
 "pallet": [.28, .78], "viridian": [.28, .60], "pewter": [.28, .42], "cerulean": [.62, .36],
 "vermilion": [.61, .66], "lavender": [.75, .52], "celadon": [.50, .52], "fuchsia": [.52, .82],
 "saffron": [.61, .52], "cinnabar": [.28, .905], "indigo_plateau": [.21, .34],
 "route1": [.28, .69], "route2": [.27, .50], "route3": [.35, .40], "route4": [.50, .38],
 "route5": [.62, .44], "route6": [.61, .59], "route7": [.56, .52], "route8": [.70, .52],
 "route9": [.72, .36], "route10": [.76, .45], "route11": [.72, .66], "route12": [.77, .60],
 "route13": [.77, .68], "route14": [.75, .75], "route15": [.64, .81], "route16": [.42, .55],
 "route17": [.40, .69], "route18": [.46, .82], "route22": [.22, .60], "route23": [.21, .48],
 "route24": [.62, .28], "route25": [.66, .22], "route19": [.53, .90], "route20": [.40, .91],
 "route21": [.28, .86], "viridian_forest": [.27, .53], "mt_moon": [.42, .38],
 "rock_tunnel": [.75, .45], "digletts_cave": [.45, .55], "seafoam_islands": [.40, .935],
 "safari_zone": [.53, .74], "cerulean_cave": [.57, .33], "victory_road": [.21, .42],
 "pokemon_tower": [.76, .49], "power_plant": [.77, .42], "pokemon_mansion": [.30, .93],
}
# Hoenn eastern-sea islands + Dewford: grid-center projection doesn't register to hoenn.png
# for the offshore mapsecs (they're drawn compressed toward land). Per-node overrides from the
# graph-audit pixel measurements, applied on top of the grid math (inland nodes register fine).
HOENN_XY_OVERRIDE = {
 "ever_grande_city": [.887, .55], "victory_road": [.90, .60], "mossdeep_city": [.80, .377],
 "sootopolis_city": [.70, .48], "cave_of_origin": [.71, .50], "lilycove_city": [.615, .27],
 "dewford_town": [.109, .83],
}

# ---- Johto (landmarks.asm pixel coords, bbox-fit) ------------------------
def johto_xy():
    t = open(f"{RAW2}/landmarks.asm").read()
    seg = t.split("PalletTownName")[0]
    rows = re.findall(r'landmark\s+(-?\d+),\s*(-?\d+),\s*(\w+)Name', seg)
    N2N = {'NewBarkTown':'new_bark','Route29':'route29','CherrygroveCity':'cherrygrove','Route30':'route30',
     'Route31':'route31','VioletCity':'violet','SproutTower':'sprout_tower','Route32':'route32',
     'RuinsOfAlph':'ruins_of_alph','UnionCave':'union_cave','Route33':'route33','AzaleaTown':'azalea',
     'SlowpokeWell':'slowpoke_well','IlexForest':'ilex_forest','Route34':'route34','GoldenrodCity':'goldenrod',
     'Route35':'route35','NationalPark':'national_park','Route36':'route36','Route37':'route37',
     'EcruteakCity':'ecruteak','TinTower':'tin_tower','BurnedTower':'burned_tower','Route38':'route38',
     'Route39':'route39','OlivineCity':'olivine','Route40':'route40','WhirlIslands':'whirl_islands',
     'Route41':'route41','CianwoodCity':'cianwood','Route42':'route42','MtMortar':'mt_mortar',
     'MahoganyTown':'mahogany','Route43':'route43','LakeOfRage':'lake_of_rage','Route44':'route44',
     'IcePath':'ice_path','BlackthornCity':'blackthorn','DragonsDen':'dragons_den','Route45':'route45',
     'DarkCave':'dark_cave','Route46':'route46'}
    pts = {}
    for x, y, name in rows:
        node = N2N.get(name)
        if node: pts[node] = (int(x) + 8, int(y) + 16)
    xs = [p[0] for p in pts.values()]; ys = [p[1] for p in pts.values()]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    M = 0.055
    return {k: [round(M + (v[0]-xmin)/(xmax-xmin)*(1-2*M), 3),
                round(M + (v[1]-ymin)/(ymax-ymin)*(1-2*M), 3)] for k, v in pts.items()}

# ---- Hoenn (region-map grid centers) ------------------------------------
def hoenn_xy():
    sec = json.load(open(f"{RAW3}/region_map_sections.json"))["map_sections"]
    GW, GH = 28, 15
    SKIP = {"MAPSEC_NONE","MAPSEC_BATTLE_FRONTIER","MAPSEC_ARTISAN_CAVE","MAPSEC_TRAINER_HILL",
        "MAPSEC_MIRAGE_ISLAND","MAPSEC_MIRAGE_TOWER","MAPSEC_SOUTHERN_ISLAND","MAPSEC_AQUA_HIDEOUT_OLD",
        "MAPSEC_DESERT_UNDERPASS","MAPSEC_ALTERING_CAVE","MAPSEC_SEALED_CHAMBER","MAPSEC_SCORCHED_SLAB",
        "MAPSEC_ANCIENT_TOMB","MAPSEC_DESERT_RUINS","MAPSEC_ISLAND_CAVE","MAPSEC_MAGMA_HIDEOUT","MAPSEC_AQUA_HIDEOUT"}
    xy = {}
    for s in sec:
        if "x" not in s: continue
        sid = s["id"]
        if sid in SKIP or sid.startswith("MAPSEC_UNDERWATER"): continue
        if sid in ("MAPSEC_METEOR_FALLS2","MAPSEC_FIERY_PATH2","MAPSEC_JAGGED_PASS2"): continue
        nid = re.sub(r'route_(\d+)', r'route\1', sid.replace("MAPSEC_", "").lower())
        cx = s["x"] + s.get("width", 1)/2.0; cy = s["y"] + s.get("height", 1)/2.0
        xy[nid] = [round(cx/GW, 3), round(cy/GH, 3)]
    return xy

COORDS = {"kanto": KANTO_XY, "johto": johto_xy(), "hoenn": {**hoenn_xy(), **HOENN_XY_OVERRIDE}}

for region, xy in COORDS.items():
    path = f"{OUT}/connectivity_{region}.json"
    conn = json.load(open(path))
    miss = []
    for n in conn["nodes"]:
        if n["id"] in xy:
            n["x"], n["y"] = xy[n["id"]]
        else:
            miss.append(n["id"])
    json.dump(conn, open(path, "w"), indent=1)
    print(f"{region}: embedded coords into {len(conn['nodes'])-len(miss)}/{len(conn['nodes'])} nodes"
          + (f"  MISSING={miss}" if miss else ""))
