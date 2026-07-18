#!/usr/bin/env python3
"""
fetch_sources.py — Download the static CSV/TS sources for the pipeline.

All downloads use urllib (not curl) so they are unaffected by the local
RTK proxy that rewrites curl output. Files land in ../raw/.

Sources:
  - cristobalmitchell/pokedex  data/pokemon.csv   (MIT) — 1025 species, UTF-16 TSV
  - veekun/pokedex             type_efficacy.csv  — modern 18-type effectiveness
  - veekun/pokedex             types.csv          — type id -> identifier map
  - smogon/pokemon-showdown    gen1/typechart.ts  — Gen-1 type chart deltas
"""
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.normpath(os.path.join(HERE, "..", "raw"))

SOURCES = {
    "pokemon.csv": "https://raw.githubusercontent.com/cristobalmitchell/pokedex/main/data/pokemon.csv",
    "type_efficacy.csv": "https://raw.githubusercontent.com/veekun/pokedex/master/pokedex/data/csv/type_efficacy.csv",
    "types.csv": "https://raw.githubusercontent.com/veekun/pokedex/master/pokedex/data/csv/types.csv",
    "gen1_typechart.ts": "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/mods/gen1/typechart.ts",
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pokemon-fun-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> None:
    os.makedirs(RAW, exist_ok=True)
    for fname, url in SOURCES.items():
        data = fetch(url)
        out = os.path.join(RAW, fname)
        with open(out, "wb") as f:
            f.write(data)
        print(f"  saved {fname:22s} {len(data):>9,} bytes  <- {url}")
    print("Done. Raw sources in", RAW)


if __name__ == "__main__":
    main()
