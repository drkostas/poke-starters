#!/usr/bin/env python3
"""Fetch Gen-4 (dex 387-493) sprites from PokeAPI into ../../app/sprites/dex/.

Prefers the Generation-IV Platinum sprite (era-accurate), falls back to the
default sprite. These are transparent PNGs, no post-processing needed. Uses
urllib (unaffected by the local RTK proxy that rewrites curl output).
"""
import urllib.request
from pathlib import Path

DEX_DIR = Path(__file__).resolve().parents[2] / "app/sprites/dex"
BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"
UA = {"User-Agent": "poke-starters-pipeline/1.0"}


def fetch(url: str):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except Exception:
        return None


def main():
    DEX_DIR.mkdir(parents=True, exist_ok=True)
    ok, fail = 0, []
    for dex in range(387, 494):
        data = fetch(f"{BASE}/versions/generation-iv/platinum/{dex}.png") or fetch(f"{BASE}/{dex}.png")
        if data and len(data) > 200:
            (DEX_DIR / f"{dex}.png").write_bytes(data)
            ok += 1
        else:
            fail.append(dex)
    print(f"fetched {ok}/107 Gen-4 sprites; failures: {fail}")


if __name__ == "__main__":
    main()
