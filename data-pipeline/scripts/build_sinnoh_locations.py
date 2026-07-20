#!/usr/bin/env python3
"""Build locations_sinnoh.json from PokeAPI location-area encounters (Platinum,
Diamond/Pearl fallback), keyed by connectivity_sinnoh node id.

Schema per node: {name, type, catchable:[{dexNumber,name,method,version,
rarityTier,minLevel,maxLevel}]}. PokeAPI methods/versions are normalized to the
project's vocabulary; encounter chance maps to a rarity tier. Requires
app/data/pokemon.json and connectivity_sinnoh.json.
"""
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UA = {"User-Agent": "poke-starters-pipeline/1.0"}

# PokeAPI location names that don't normalize cleanly to a node id
ALIAS = {
    "ruin-maniac-cave": "maniac_tunnel", "sinnoh-victory-road": "victory_road_sinnoh",
    "sinnoh-pokemon-league": "pokemon_league", "lost-tower": "lost_tower", "mt-coronet": "mt_coronet",
}


def get(url):
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(1)
    return None


def to_node(locname):
    if locname in ALIAS:
        return ALIAS[locname]
    s = locname.replace("sinnoh-", "")
    m = re.match(r"route-(\d+)", s)
    return ("route" + m.group(1)) if m else s.replace("-", "_")


def method_of(name):
    n = name.replace("-", "_")
    if n == "walk":
        return "grass"
    if n in ("only_one", "gift_egg", "seaweed"):
        return "static"
    return n  # surf, old_rod, good_rod, super_rod, rock_smash, headbutt, gift, ...


def rarity(chance, meth):
    if meth in ("gift", "static"):
        return "guaranteed"
    if chance >= 35:
        return "common"
    if chance >= 15:
        return "uncommon"
    if chance >= 5:
        return "rare"
    return "very_rare"


def main():
    poke = json.loads((ROOT / "app/data/pokemon.json").read_text())
    name2dex = {v["name"].lower(): int(k) for k, v in poke.items()}
    conn = json.loads((ROOT / "app/data/connectivity_sinnoh.json").read_text())
    node = {n["id"]: n for n in conn["nodes"]}
    myids = set(node)

    out = {}
    reg = get("https://pokeapi.co/api/v2/region/sinnoh")
    for ln in [l["name"] for l in reg["locations"]]:
        nid = to_node(ln)
        if nid not in myids:
            continue
        loc = get("https://pokeapi.co/api/v2/location/" + ln)
        if not loc:
            continue
        for a in loc["areas"]:
            area = get("https://pokeapi.co/api/v2/location-area/" + a["name"])
            if not area:
                continue
            for e in area["pokemon_encounters"]:
                pname = e["pokemon"]["name"]
                dex = name2dex.get(pname) or name2dex.get(pname.split("-")[0])
                if not dex:
                    continue
                vd = [v for v in e["version_details"] if v["version"]["name"] == "platinum"] \
                    or [v for v in e["version_details"] if v["version"]["name"] in ("diamond", "pearl")]
                best = None
                for v in vd:
                    for ed in v["encounter_details"]:
                        cand = {"method": method_of(ed["method"]["name"]), "chance": ed["chance"],
                                "min": ed["min_level"], "max": ed["max_level"]}
                        if best is None or cand["chance"] > best["chance"]:
                            best = cand
                if not best:
                    continue
                bucket = out.setdefault(nid, {"name": node[nid]["name"], "type": node[nid]["type"], "catchable": []})
                if not any(c["dexNumber"] == dex and c["method"] == best["method"] for c in bucket["catchable"]):
                    bucket["catchable"].append({
                        "dexNumber": dex, "name": poke[str(dex)]["name"], "method": best["method"],
                        "version": "platinum", "rarityTier": rarity(best["chance"], best["method"]),
                        "minLevel": best["min"], "maxLevel": best["max"]})

    result = {"_meta": {"region": "Sinnoh",
                        "basis": "PokeAPI location-area encounters (Platinum; Diamond/Pearl fallback). keyedBy connectivity_sinnoh node id."}}
    result.update(out)
    (ROOT / "app/data/locations_sinnoh.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    total = sum(len(v["catchable"]) for v in out.values())
    print(f"wrote locations_sinnoh.json — {len(out)} nodes, {total} catchable entries")


if __name__ == "__main__":
    main()
