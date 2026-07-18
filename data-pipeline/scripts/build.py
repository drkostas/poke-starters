#!/usr/bin/env python3
"""
build.py — Assemble the normalized JSON outputs from raw sources + cache.

Produces (in ../output/):
  pokemon.json            core dex data, keyed by national dex number (string)
  evolution_chains.json   evolution chains + edge conditions, keyed by chain id
  type_chart.json         modern 18-type effectiveness matrix
  type_chart_gen1.json    Gen-1 (15-type) effectiveness matrix
  manifest.json           provenance + counts + notes

Run order: fetch_sources.py -> fetch_pokeapi.py -> build.py
Then verification is printed at the end of this script.

Field provenance summary:
  From cristobalmitchell/pokedex CSV : dexNumber, name, generation, types,
      baseStats, bst, height, weight, catchRate
  From PokeAPI pokemon (default form): abilities (+hidden/slot). Also the second
      source for the base-stat cross-check (all 1025 species).
  From PokeAPI evolution-chain       : evolution_chains.json, and each pokemon's
      evolutionChainId / isFinalEvolution / evolutionStageCount
  From veekun type_efficacy.csv      : type_chart.json (modern)
  From Showdown gen1/typechart.ts    : type_chart_gen1.json
"""
import csv
import io
import json
import os
import re
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
RAW = os.path.join(ROOT, "raw")
CACHE = os.path.join(ROOT, "cache")
OUT = os.path.join(ROOT, "output")

GENERATED_DATE = "2026-07-16"

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9}

MODERN_TYPES = [
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison",
    "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy",
]
GEN1_TYPES = [
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison",
    "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon",
]

SOURCES = {
    "pokemon_csv": "https://raw.githubusercontent.com/cristobalmitchell/pokedex/main/data/pokemon.csv",
    "type_efficacy_csv": "https://raw.githubusercontent.com/veekun/pokedex/master/pokedex/data/csv/type_efficacy.csv",
    "types_csv": "https://raw.githubusercontent.com/veekun/pokedex/master/pokedex/data/csv/types.csv",
    "gen1_typechart_ts": "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/mods/gen1/typechart.ts",
    "pokeapi_evolution_chain": "https://pokeapi.co/api/v2/evolution-chain/{id}",
    "pokeapi_pokemon": "https://pokeapi.co/api/v2/pokemon/{id}",
}


def write_json(name, obj):
    path = os.path.join(OUT, name)
    with open(path, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  wrote {name:26s} {os.path.getsize(path):>9,} bytes")
    return path


# ---------------------------------------------------------------------------
# CSV parse
# ---------------------------------------------------------------------------
def load_csv_rows():
    with open(os.path.join(RAW, "pokemon.csv"), "r", encoding="utf-16") as f:
        text = f.read()
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    header = rows[0]
    idx = {c: i for i, c in enumerate(header)}
    return rows[1:], idx


def parse_int(s):
    m = re.search(r"\d+", s or "")
    return int(m.group()) if m else None


_PAYLOAD_CACHE = {}


def load_pokeapi_payload(dex):
    if dex not in _PAYLOAD_CACHE:
        with open(os.path.join(CACHE, "pokemon", f"{dex}.json")) as f:
            _PAYLOAD_CACHE[dex] = json.load(f)
    return _PAYLOAD_CACHE[dex]


def prettify_ability(slug):
    """PokeAPI slug 'lightning-rod' -> display 'Lightning Rod'."""
    return slug.replace("-", " ").title()


def load_pokeapi_abilities(dex):
    """Clean default-form abilities (name/isHidden/slot) from the PokeAPI payload.

    Avoids the form-annotated ability strings in the CSV (e.g. Basculin's
    'Rock Head (Blue-Striped Form)') by taking the species' DEFAULT form.
    """
    d = load_pokeapi_payload(dex)
    out = []
    for a in sorted(d["abilities"], key=lambda a: a["slot"]):
        out.append({
            "name": prettify_ability(a["ability"]["name"]),
            "isHidden": a["is_hidden"],
            "slot": a["slot"],
        })
    return out


def pokeapi_base_stats(dex):
    d = load_pokeapi_payload(dex)
    return {STAT_KEY[s["stat"]["name"]]: s["base_stat"]
            for s in d["stats"] if s["stat"]["name"] in STAT_KEY}


# ---------------------------------------------------------------------------
# Evolution chains
# ---------------------------------------------------------------------------
def _name(x):
    if isinstance(x, dict) and x and "name" in x:
        return x["name"]
    return x


DETAIL_MAP = {
    "min_level": "minLevel",
    "item": "item",
    "held_item": "heldItem",
    "time_of_day": "timeOfDay",
    "min_happiness": "happiness",
    "min_affection": "minAffection",
    "min_beauty": "minBeauty",
    "known_move": "knownMove",
    "known_move_type": "knownMoveType",
    "location": "location",
    "gender": "gender",
    "needs_overworld_rain": "needsOverworldRain",
    "party_species": "partySpecies",
    "party_type": "partyType",
    "relative_physical_stats": "relativePhysicalStats",
    "trade_species": "tradeSpecies",
    "turn_upside_down": "turnUpsideDown",
}


def norm_method(det):
    m = {"trigger": _name(det["trigger"])}
    m["tradeRequired"] = (m["trigger"] == "trade") or bool(det.get("trade_species"))
    for src, dst in DETAIL_MAP.items():
        v = _name(det.get(src))
        if v not in (None, "", False):
            m[dst] = v
    if det.get("near_special_rock"):
        m["nearSpecialRock"] = True
    vg = _name(det.get("version_group"))
    if vg:
        m["versionGroup"] = vg
    if det.get("is_default"):
        m["isDefault"] = True
    return m


def dedupe_methods(methods):
    out, seen = [], set()
    for m in methods:
        key = json.dumps(m, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def build_evolution(species_map):
    files = sorted(glob.glob(os.path.join(CACHE, "chains", "*.json")),
                   key=lambda p: int(os.path.splitext(os.path.basename(p))[0]))
    chains = {}
    dex_chain = {}          # dex -> chain id
    dex_is_final = {}       # dex -> bool (leaf)
    dex_stage_count = {}    # dex -> max depth of its chain
    missing_species = set()

    for fp in files:
        with open(fp) as f:
            data = json.load(f)
        cid = data["id"]
        root = data["chain"]

        nodes = []   # {name, dexNumber, stage}
        edges = []
        branched = False
        max_depth = 1

        def dex_of(name):
            d = species_map.get(name)
            if d is None:
                missing_species.add(name)
            return d

        def walk(node, depth):
            nonlocal branched, max_depth
            max_depth = max(max_depth, depth)
            nm = node["species"]["name"]
            ndex = dex_of(nm)
            nodes.append({"name": nm, "dexNumber": ndex, "stage": depth})
            children = node.get("evolves_to", [])
            if len(children) > 1:
                branched = True
            is_leaf = len(children) == 0
            if ndex is not None:
                dex_chain[ndex] = cid
                dex_is_final[ndex] = is_leaf
            for child in children:
                cnm = child["species"]["name"]
                cdex = dex_of(cnm)
                methods = dedupe_methods([norm_method(d) for d in child["evolution_details"]])
                edges.append({
                    "from": nm, "fromDex": ndex,
                    "to": cnm, "toDex": cdex,
                    "methods": methods,
                })
                walk(child, depth + 1)

        walk(root, 1)

        for n in nodes:
            if n["dexNumber"] is not None:
                dex_stage_count[n["dexNumber"]] = max_depth

        edges.sort(key=lambda e: (e["fromDex"] or 0, e["toDex"] or 0))
        chains[str(cid)] = {
            "id": cid,
            "babyTriggerItem": _name(data.get("baby_trigger_item")),
            "isBranched": branched,
            "stageCount": max_depth,
            "speciesCount": len(nodes),
            "species": sorted(nodes, key=lambda n: (n["stage"], n["dexNumber"] or 0)),
            "edges": edges,
        }

    return chains, dex_chain, dex_is_final, dex_stage_count, missing_species


# ---------------------------------------------------------------------------
# Type charts
# ---------------------------------------------------------------------------
def build_modern_chart():
    id2name = {}
    with open(os.path.join(RAW, "types.csv")) as f:
        for r in csv.DictReader(f):
            tid = int(r["id"])
            if r["identifier"] in MODERN_TYPES:
                id2name[tid] = r["identifier"]
    chart = {a: {d: 1.0 for d in MODERN_TYPES} for a in MODERN_TYPES}
    with open(os.path.join(RAW, "type_efficacy.csv")) as f:
        for r in csv.DictReader(f):
            a = id2name.get(int(r["damage_type_id"]))
            d = id2name.get(int(r["target_type_id"]))
            if a and d:
                chart[a][d] = int(r["damage_factor"]) / 100.0
    return chart


def _fmt(v):
    return int(v) if v == int(v) else v


def parse_gen1_overrides():
    """Parse Showdown gen1/typechart.ts -> {defender: {attacker: multiplier}}."""
    text = open(os.path.join(RAW, "gen1_typechart.ts")).read()
    code2mult = {0: 1.0, 1: 2.0, 2: 0.5, 3: 0.0}
    overrides = {}
    # match blocks:  <type>: { ... damageTaken: { <body> } ... }
    for m in re.finditer(r"(\w+):\s*\{[^{}]*?damageTaken:\s*\{([^}]*)\}", text, re.S):
        defender = m.group(1).lower()
        if defender not in GEN1_TYPES:
            continue
        body = m.group(2)
        row = {}
        for k, v in re.findall(r"(\w+):\s*(\d)", body):
            atk = k.lower()
            if atk in GEN1_TYPES:  # drop psn/tox/dark/steel/fairy keys
                row[atk] = code2mult[int(v)]
        overrides[defender] = row
    return overrides


def build_gen1_chart(modern):
    overrides = parse_gen1_overrides()
    chart = {a: {} for a in GEN1_TYPES}
    for atk in GEN1_TYPES:
        for dfn in GEN1_TYPES:
            if dfn in overrides and atk in overrides[dfn]:
                chart[atk][dfn] = _fmt(overrides[dfn][atk])
            else:
                chart[atk][dfn] = _fmt(modern[atk][dfn])
    return chart, overrides


# ---------------------------------------------------------------------------
# Verification: cross-check base stats vs PokeAPI sample
# ---------------------------------------------------------------------------
STAT_KEY = {
    "hp": "hp", "attack": "atk", "defense": "def",
    "special-attack": "spAtk", "special-defense": "spDef", "speed": "speed",
}


def cross_check(pokemon, csv_stats_map, dex_list):
    """Compare the RAW CSV base stats against PokeAPI (the honest cross-check)."""
    results = []
    for dex in dex_list:
        api_stats = pokeapi_base_stats(dex)
        csv_stats = csv_stats_map[str(dex)]
        results.append({
            "dex": dex, "name": pokemon[str(dex)]["name"],
            "agree": api_stats == csv_stats,
            "csv": csv_stats, "pokeapi": api_stats,
        })
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)

    with open(os.path.join(CACHE, "species_list.json")) as f:
        species_map = json.load(f)

    print("[evolution] building chains + backfill maps")
    chains, dex_chain, dex_is_final, dex_stage_count, missing = build_evolution(species_map)
    if missing:
        print("   WARN: chain species not in species map:", sorted(missing))

    print("[pokemon] parsing CSV + merging evolution backfill")
    rows, idx = load_csv_rows()

    def cell(row, name):
        return row[idx[name]].strip()

    pokemon = {}
    catchrate_notes = []
    csv_stats_map = {}      # raw CSV stats, kept for an honest cross-check
    stat_corrections = []   # CSV stats reconciled to current PokeAPI values
    for row in rows:
        dex = int(cell(row, "national_number"))
        sdex = str(dex)
        csv_stats = {
            "hp": int(cell(row, "hp")),
            "atk": int(cell(row, "attack")),
            "def": int(cell(row, "defense")),
            "spAtk": int(cell(row, "sp_attack")),
            "spDef": int(cell(row, "sp_defense")),
            "speed": int(cell(row, "speed")),
        }
        csv_stats_map[sdex] = csv_stats
        # Reconcile against the current-generation PokeAPI stats: the CSV lags a
        # few post-launch stat revisions (Cresselia Def/SpD, Zacian/Zamazenta Atk).
        api_stats = pokeapi_base_stats(dex)
        if api_stats and api_stats != csv_stats:
            stat_corrections.append({
                "dex": dex, "name": cell(row, "english_name"),
                "csv": csv_stats, "used_pokeapi": api_stats,
            })
            stats = api_stats
        else:
            stats = csv_stats
        types = [cell(row, "primary_type").lower()]
        sec = cell(row, "secondary_type").lower()
        if sec:
            types.append(sec)
        raw_cap = cell(row, "capture_rate")
        catch = parse_int(raw_cap)
        if not re.fullmatch(r"\d+", raw_cap):
            catchrate_notes.append({"dex": dex, "name": cell(row, "english_name"),
                                    "raw": raw_cap, "used": catch})
        pokemon[sdex] = {
            "dexNumber": dex,
            "name": cell(row, "english_name"),
            "generation": ROMAN[cell(row, "gen")],
            "types": types,
            "abilities": load_pokeapi_abilities(dex),
            "baseStats": stats,
            "bst": sum(stats.values()),
            "height": float(cell(row, "height_m")),
            "weight": float(cell(row, "weight_kg")),
            "catchRate": catch,
            "isFinalEvolution": dex_is_final.get(dex),
            "evolutionChainId": dex_chain.get(dex),
            "evolutionStageCount": dex_stage_count.get(dex),
        }

    with_evo = sum(1 for p in pokemon.values() if p["evolutionChainId"] is not None)

    print("[type charts] building modern + gen1")
    modern = build_modern_chart()
    gen1, gen1_overrides = build_gen1_chart(modern)

    modern_out = {
        "_meta": {
            "description": "Modern (Gen 6+) 18-type effectiveness matrix.",
            "structure": "type_chart[attackingType][defendingType] = multiplier (0, 0.5, 1, or 2)",
            "dualTypeRule": "For a defender with two types, multiply both defending lookups: "
                            "effectiveness = chart[atk][defType1] * chart[atk][defType2].",
            "source": SOURCES["type_efficacy_csv"],
            "types": MODERN_TYPES,
            "generation": "6-9",
        }
    }
    for a in MODERN_TYPES:
        modern_out[a] = {d: _fmt(modern[a][d]) for d in MODERN_TYPES}

    gen1_out = {
        "_meta": {
            "description": "Gen-1 (Red/Blue/Yellow) 15-type effectiveness matrix. "
                           "No Dark, Steel, or Fairy types existed.",
            "structure": "type_chart[attackingType][defendingType] = multiplier (0, 0.5, 1, or 2)",
            "dualTypeRule": "For a defender with two types, multiply both defending lookups.",
            "source": SOURCES["gen1_typechart_ts"],
            "types": GEN1_TYPES,
            "generation": "1",
            "differencesFromModern": [
                "Ghost -> Psychic is 0x (no effect) due to a Gen-1 bug (design intent was 2x super effective).",
                "Bug -> Poison is 2x (super effective); modern is 0.5x.",
                "Poison -> Bug is 2x (super effective); modern is 1x.",
                "Ice -> Fire is 1x (neutral); modern is 0.5x (Fire resists Ice).",
                "Fire -> Ice unchanged at 2x, but Ice's other matchups differ per the notes above.",
                "Dark, Steel and Fairy types (and all their interactions) do not exist.",
            ],
            "overriddenDefenders": sorted(gen1_overrides.keys()),
        }
    }
    for a in GEN1_TYPES:
        gen1_out[a] = {d: gen1[a][d] for d in GEN1_TYPES}

    print("[write] outputs")
    write_json("pokemon.json", pokemon)
    write_json("evolution_chains.json", chains)
    write_json("type_chart.json", modern_out)
    write_json("type_chart_gen1.json", gen1_out)

    manifest = {
        "generatedDate": GENERATED_DATE,
        "generations": "1-9 (national dex 1..1025)",
        "sources": [
            {"name": "cristobalmitchell/pokedex (MIT)", "url": SOURCES["pokemon_csv"],
             "provides": "dexNumber, name, generation, types, baseStats, bst, height, weight, catchRate"},
            {"name": "PokeAPI pokemon (default form)", "url": "https://pokeapi.co/api/v2/pokemon/{id}",
             "provides": "abilities (name/isHidden/slot); second-source base stats for the full cross-check"},
            {"name": "PokeAPI evolution-chain", "url": "https://pokeapi.co/api/v2/evolution-chain/{id}",
             "provides": "evolution_chains.json; evolutionChainId, isFinalEvolution, evolutionStageCount backfill"},
            {"name": "PokeAPI pokemon-species (name->dex map)", "url": "https://pokeapi.co/api/v2/pokemon-species",
             "provides": "authoritative species name -> national dex number mapping"},
            {"name": "veekun/pokedex type_efficacy.csv", "url": SOURCES["type_efficacy_csv"],
             "provides": "modern 18-type effectiveness matrix"},
            {"name": "veekun/pokedex types.csv", "url": SOURCES["types_csv"],
             "provides": "type id -> name map for the efficacy matrix"},
            {"name": "smogon/pokemon-showdown gen1/typechart.ts", "url": SOURCES["gen1_typechart_ts"],
             "provides": "Gen-1 15-type effectiveness matrix"},
        ],
        "counts": {
            "species": len(pokemon),
            "withEvolutionData": with_evo,
            "chains": len(chains),
            "types": len(MODERN_TYPES),
            "typesGen1": len(GEN1_TYPES),
        },
        "notes": [
            "pokemon.json is a map keyed by national dex number as a string ('1'..'1025').",
            "types are lowercase; 1 or 2 per species. Dual-type effectiveness = product of both defending lookups.",
            "abilities come from the PokeAPI DEFAULT form (name/isHidden/slot); the CSV ability strings were "
            "discarded because they embed form annotations (e.g. 'Rock Head (Blue-Striped Form)').",
            "base stats, types, height, weight reflect the DEFAULT form only; alternate/mega/regional/rider forms "
            "are not separate entries (e.g. Wishiwashi=Solo, Zygarde=50%, Minior=Meteor, Necrozma=base).",
            "evolutionStageCount is the total number of stages in a species' whole evolution line (chain max depth).",
            "isFinalEvolution is true when the species is a leaf in its evolution tree (includes non-evolving species).",
            "type_chart files carry a '_meta' key; every other top-level key is a real lowercase type.",
            "Catch-rate anomalies (parsed to the first integer) are listed in this manifest under catchRateNotes.",
        ],
        "catchRateNotes": catchrate_notes,
        "statCorrections": stat_corrections,
    }
    manifest["notes"].append(
        f"{len(stat_corrections)} species had CSV base stats reconciled to current PokeAPI values "
        "(see statCorrections): the CSV predates a few post-launch stat revisions."
    )
    if missing:
        manifest["notes"].append(f"Chain species with no dex mapping (skipped): {sorted(missing)}")
    write_json("manifest.json", manifest)

    # -------------------------------------------------------------- verify
    print("\n" + "=" * 66)
    print("VERIFICATION")
    print("=" * 66)
    print(f"species                : {len(pokemon)}")
    print(f"species w/ evolutionChainId: {with_evo}")
    print(f"evolution chains       : {len(chains)}")
    print(f"modern types           : {len(MODERN_TYPES)}   gen1 types: {len(GEN1_TYPES)}")

    # JSON parse check via a clean subprocess-independent reload
    print("\nJSON parse check:")
    for name in ["pokemon.json", "evolution_chains.json", "type_chart.json",
                 "type_chart_gen1.json", "manifest.json"]:
        with open(os.path.join(OUT, name)) as f:
            json.load(f)
        print(f"  OK  {name}")

    # Base-stat cross-check — raw CSV vs PokeAPI over all 1025 + a highlighted sample
    all_dex = sorted(int(d) for d in pokemon)
    full = cross_check(pokemon, csv_stats_map, all_dex)
    full_agree = sum(1 for r in full if r["agree"])
    mismatches = [r for r in full if not r["agree"]]
    print(f"\nBase-stat cross-check: raw CSV vs PokeAPI (ALL {len(full)} species):")
    print(f"  agreement: {full_agree}/{len(full)} ({100*full_agree/len(full):.1f}%)")
    if mismatches:
        print(f"  discrepancies ({len(mismatches)}) — reconciled to current PokeAPI values in pokemon.json:")
        for r in mismatches:
            diff = {k: (r["csv"][k], r["pokeapi"][k]) for k in r["csv"] if r["csv"][k] != r["pokeapi"][k]}
            print(f"    #{r['dex']:>4} {r['name']:<12} CSV->PokeAPI {diff}")
    else:
        print("  no discrepancies")

    with open(os.path.join(CACHE, "statcheck_sample.json")) as f:
        sample = json.load(f)
    print(f"\n  highlighted random sample of {len(sample)}:")
    for r in cross_check(pokemon, csv_stats_map, sample):
        print(f"    {'OK ' if r['agree'] else 'DIFF'} #{r['dex']:>4} {r['name']}")

    # Missing key fields
    print("\nMissing-field audit:")
    def miss(pred):
        return [d for d, p in pokemon.items() if pred(p)]
    checks = {
        "empty types": miss(lambda p: not p["types"]),
        "null catchRate": miss(lambda p: p["catchRate"] is None),
        "no abilities": miss(lambda p: not p["abilities"]),
        "null evolutionChainId": miss(lambda p: p["evolutionChainId"] is None),
        "null isFinalEvolution": miss(lambda p: p["isFinalEvolution"] is None),
        "null evolutionStageCount": miss(lambda p: p["evolutionStageCount"] is None),
    }
    for label, lst in checks.items():
        preview = "" if not lst else "  e.g. " + ", ".join(sorted(lst, key=int)[:10])
        print(f"  {label:26s}: {len(lst)}{preview}")

    print("\nDone.")


if __name__ == "__main__":
    main()
