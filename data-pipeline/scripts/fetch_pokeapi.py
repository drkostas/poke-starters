#!/usr/bin/env python3
"""
fetch_pokeapi.py — Pull the live-API bits that the static CSV can't provide.

Uses urllib (RTK-proof) with a small thread pool and on-disk caching so
re-runs are cheap and the pipeline is reproducible.

Writes into ../cache/:
  species_list.json          name -> national dex number (authoritative)
  chains/<id>.json           raw evolution-chain payloads (rich trigger data)
  pokemon/<dex>.json         default-form `pokemon/<dex>` payloads (all 1025) used
                             for clean abilities + a full base-stat cross-check
  statcheck_sample.json      15 deterministic dex numbers highlighted in the report

Evolution-chain data is the ONLY source rich enough for trigger taxonomy
(min level, item, held item, time of day, happiness, trade, etc.).
The default-form pokemon payloads give clean abilities (name/isHidden/slot),
avoiding the form-annotated ability strings in the CSV.
"""
import json
import os
import random
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.normpath(os.path.join(HERE, "..", "cache"))
API = "https://pokeapi.co/api/v2"
UA = {"User-Agent": "pokemon-fun-pipeline/1.0"}

STATCHECK_N = 15
STATCHECK_SEED = 1025  # deterministic sample


def get_json(url: str, retries: int = 4):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {url} :: {last}")


def species_map():
    """name -> dexNumber. species id == national dex number for the base dex."""
    path = os.path.join(CACHE, "species_list.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    data = get_json(f"{API}/pokemon-species/?limit=100000")
    out = {}
    for r in data["results"]:
        dex = int(r["url"].rstrip("/").split("/")[-1])
        out[r["name"]] = dex
    with open(path, "w") as f:
        json.dump(out, f, indent=0)
    print(f"  species_list.json: {len(out)} species")
    return out


def chain_ids():
    data = get_json(f"{API}/evolution-chain/?limit=100000")
    ids = [int(r["url"].rstrip("/").split("/")[-1]) for r in data["results"]]
    print(f"  evolution-chain count: {data['count']} ({len(ids)} ids)")
    return ids


def fetch_chains(ids):
    cdir = os.path.join(CACHE, "chains")
    os.makedirs(cdir, exist_ok=True)
    todo = [i for i in ids if not os.path.exists(os.path.join(cdir, f"{i}.json"))]
    print(f"  chains: {len(ids)} total, {len(ids) - len(todo)} cached, {len(todo)} to fetch")

    def one(cid):
        d = get_json(f"{API}/evolution-chain/{cid}/")
        with open(os.path.join(cdir, f"{cid}.json"), "w") as f:
            json.dump(d, f)
        return cid

    done = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(one, i): i for i in todo}
        for fut in as_completed(futs):
            fut.result()
            done += 1
            if done % 50 == 0:
                print(f"    ... {done}/{len(todo)} chains")
    print(f"  chains: fetched {done} new")


def fetch_pokemon(max_dex=1025):
    """All default-form pokemon payloads (abilities + stats for cross-check)."""
    pdir = os.path.join(CACHE, "pokemon")
    os.makedirs(pdir, exist_ok=True)
    todo = [d for d in range(1, max_dex + 1)
            if not os.path.exists(os.path.join(pdir, f"{d}.json"))]
    print(f"  pokemon: {max_dex} total, {max_dex - len(todo)} cached, {len(todo)} to fetch")

    def one(dex):
        d = get_json(f"{API}/pokemon/{dex}/")
        with open(os.path.join(pdir, f"{dex}.json"), "w") as f:
            json.dump(d, f)
        return dex

    done = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(one, d): d for d in todo}
        for fut in as_completed(futs):
            fut.result()
            done += 1
            if done % 100 == 0:
                print(f"    ... {done}/{len(todo)} pokemon")
    print(f"  pokemon: fetched {done} new")

    # deterministic 15-species sample highlighted in the build report
    rng = random.Random(STATCHECK_SEED)
    sample = sorted(rng.sample(range(1, max_dex + 1), STATCHECK_N))
    with open(os.path.join(CACHE, "statcheck_sample.json"), "w") as f:
        json.dump(sample, f)
    print(f"  statcheck highlight sample: {sample}")


def main():
    os.makedirs(CACHE, exist_ok=True)
    print("[1/4] species map")
    species_map()
    print("[2/4] chain ids")
    ids = chain_ids()
    print("[3/4] evolution chains")
    fetch_chains(ids)
    print("[4/4] all pokemon (abilities + full stat cross-check)")
    fetch_pokemon()
    print("Done. Cache in", CACHE)


if __name__ == "__main__":
    main()
