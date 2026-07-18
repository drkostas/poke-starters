#!/usr/bin/env bash
# Reproduce the whole dataset from scratch.
# Downloads are lightweight (4 small files + ~1550 cached JSON API calls).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/.."

echo "== 1/3 fetch static sources (CSV/TS) =="
python3 scripts/fetch_sources.py

echo "== 2/3 fetch PokeAPI (species map, evolution chains, all pokemon) =="
python3 scripts/fetch_pokeapi.py

echo "== 3/3 build normalized JSON + verify =="
python3 scripts/build.py

echo "Outputs in ./output/"
