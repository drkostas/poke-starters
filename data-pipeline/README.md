# Pokémon data pipeline

Foundational, normalized Pokémon data for the local team-planner app. Covers all
9 generations (national dex 1..1025). Output is plain JSON in `output/`, built
from lightweight sources (four small files plus cached PokéAPI calls, no repo
clones).

## Reproduce

```bash
bash scripts/run_all.sh
```

Or step by step:

```bash
python3 scripts/fetch_sources.py   # raw CSV/TS -> raw/
python3 scripts/fetch_pokeapi.py   # species map, evolution chains, all pokemon -> cache/
python3 scripts/build.py           # normalized JSON -> output/  (+ prints verification)
```

Both fetch scripts cache to disk and skip work already done, so re-runs are cheap.
All network access goes through Python `urllib` (not `curl`) so the local RTK
proxy does not rewrite API responses.

## Layout

```
data-pipeline/
  scripts/       fetch_sources.py, fetch_pokeapi.py, build.py, run_all.sh
  raw/           downloaded source files (CSV + Showdown TS)
  cache/         PokéAPI payloads (species_list, chains/, pokemon/)
  output/        the five JSON deliverables
```

## Outputs

### `output/pokemon.json`

A map keyed by national dex number as a string (`"1"`..`"1025"`). Each value:

| field | type | meaning | source |
|---|---|---|---|
| `dexNumber` | int | national dex number | CSV |
| `name` | string | display name (e.g. `"Mr. Mime"`) | CSV `english_name` |
| `generation` | int 1..9 | generation the species was introduced | CSV `gen` (Roman -> int) |
| `types` | string[] | 1 or 2 lowercase type names | CSV `primary_type` / `secondary_type` |
| `abilities` | object[] | `{name, isHidden, slot}`, ordered by slot | PokéAPI default form |
| `baseStats` | object | `{hp, atk, def, spAtk, spDef, speed}` | CSV, reconciled to current PokéAPI |
| `bst` | int | sum of the six base stats | computed |
| `height` | float | metres | CSV `height_m` |
| `weight` | float | kilograms | CSV `weight_kg` |
| `catchRate` | int | capture rate (0..255) | CSV `capture_rate` |
| `isFinalEvolution` | bool | true if the species is a leaf in its evolution tree | PokéAPI evolution chain |
| `evolutionChainId` | int | id of the evolution chain the species belongs to | PokéAPI evolution chain |
| `evolutionStageCount` | int | total stages in the whole line (chain max depth) | PokéAPI evolution chain |

Notes:
- Abilities come from the PokéAPI default form rather than the CSV, because the
  CSV embeds form annotations in the ability strings (for example Basculin's
  `"Rock Head (Blue-Striped Form)"`). Hidden abilities are flagged with
  `isHidden`; `slot` is 1 or 2 for regular abilities and 3 for the hidden slot.
- `baseStats` come from the CSV, then cross-checked against PokéAPI. Three species
  had stale CSV values (see caveats) and were reconciled to the current values.

### `output/evolution_chains.json`

A map keyed by chain id (string). Each chain:

| field | type | meaning |
|---|---|---|
| `id` | int | evolution chain id |
| `babyTriggerItem` | string \| null | incense item needed to breed the baby form, if any |
| `isBranched` | bool | true if any species evolves into more than one species |
| `stageCount` | int | maximum depth of the chain (number of stages) |
| `speciesCount` | int | number of species in the chain |
| `species` | object[] | `{name, dexNumber, stage}` for every member, stage is 1-based depth |
| `edges` | object[] | one per parent->child transition (see below) |

Each edge:

| field | type | meaning |
|---|---|---|
| `from` / `fromDex` | string / int | the pre-evolution |
| `to` / `toDex` | string / int | the evolved species |
| `methods` | object[] | one entry per distinct evolution condition |

Each method always has `trigger` (e.g. `level-up`, `use-item`, `trade`,
`three-critical-hits`, `tower-of-darkness`, `gimmighoul-coins`, ...) and
`tradeRequired` (bool). It additionally carries any of these that apply, in
camelCase, only when present: `minLevel`, `item`, `heldItem`, `timeOfDay`,
`happiness`, `minAffection`, `minBeauty`, `knownMove`, `knownMoveType`,
`location`, `gender`, `needsOverworldRain`, `partySpecies`, `partyType`,
`relativePhysicalStats`, `tradeSpecies`, `turnUpsideDown`, `nearSpecialRock`,
`versionGroup`, `isDefault`.

`versionGroup` marks which game a method applies to. A branch can list several
methods across games (Eevee -> Leafeon, for example). To pick the current
method, prefer `isDefault: true` or the latest `versionGroup`.

Every species' `evolutionChainId`, `isFinalEvolution` and `evolutionStageCount`
in `pokemon.json` are backfilled from this file, so the two stay consistent.

### `output/type_chart.json`

Modern (Gen 6+) 18-type effectiveness matrix.

```
type_chart[attackingType][defendingType] = multiplier   // 0, 0.5, 1, or 2
```

Top-level keys are the 18 lowercase type names, except `_meta`, which holds the
description, the dual-type rule, the source URL, and the type list. For a
defender with two types, multiply both defending lookups:

```
effectiveness = chart[atk][defType1] * chart[atk][defType2]
```

Source: veekun `type_efficacy.csv` (integer percent 0/50/100/200, divided by 100)
with type ids resolved via veekun `types.csv`.

### `output/type_chart_gen1.json`

Gen-1 (Red/Blue/Yellow) 15-type matrix, same shape as the modern chart. Dark,
Steel and Fairy did not exist, so they are absent as both attacker and defender.
`_meta.differencesFromModern` documents the deltas. The notable ones:

- Ghost -> Psychic is `0` (no effect) because of the Gen-1 bug (the design intent
  was 2x super effective).
- Bug -> Poison is `2` (modern `0.5`), and Poison -> Bug is `2` (modern `1`).
- Ice -> Fire is `1` (modern `0.5`).

Source: Showdown `data/mods/gen1/typechart.ts`. That file overrides six defender
types (bug, fire, ghost, ice, poison, psychic) and inherits the rest, so the nine
non-overridden defenders are filled from the modern chart restricted to the 15
Gen-1 types.

### `output/manifest.json`

`generatedDate`, `sources` (every URL with what it provides), `counts`
(`species`, `withEvolutionData`, `chains`, `types`, `typesGen1`), `notes`,
`catchRateNotes`, and `statCorrections`.

## Sources

| source | license | provides |
|---|---|---|
| [cristobalmitchell/pokedex](https://github.com/cristobalmitchell/pokedex) `data/pokemon.csv` | MIT | dexNumber, name, generation, types, baseStats, height, weight, catchRate |
| [PokéAPI](https://pokeapi.co) `pokemon/{id}` | source data © Nintendo/GF | abilities (default form); second-source base stats |
| PokéAPI `evolution-chain/{id}` | | evolution chains and all evolution backfill |
| PokéAPI `pokemon-species` | | authoritative species name -> dex map |
| [veekun/pokedex](https://github.com/veekun/pokedex) `type_efficacy.csv`, `types.csv` | | modern 18-type matrix |
| [smogon/pokemon-showdown](https://github.com/smogon/pokemon-showdown) `mods/gen1/typechart.ts` | MIT | Gen-1 15-type matrix |

## Verification

`build.py` prints a report on every run:

- counts: 1025 species, 1025 with evolution data, 541 chains, 18 modern / 15 Gen-1 types.
- JSON parse check on all five outputs.
- base-stat cross-check, raw CSV vs PokéAPI, over all 1025 species: 1022/1025 agree (99.7%).
- missing-field audit: zero species missing types, catchRate, abilities, or any evolution field.

Independent checks run during development: all 1025 generation values match the
canonical national-dex ranges, per-generation counts match the known totals
(151/100/135/107/156/72/88/96/120), and both type charts pass known matchup spot
checks (including dual-type products such as fire vs grass/steel = 4x).

## Gaps and caveats

- Base stats, types, height and weight are the species' DEFAULT form only.
  Alternate, mega, regional and rider forms are not separate entries. Examples:
  Wishiwashi is the Solo form, Zygarde is the 50% form, Minior is the Meteor
  form, Necrozma is the base form, Kyurem is the base form.
- Three species had CSV base stats that predate a post-launch stat revision and
  were reconciled to the current PokéAPI values (logged in `manifest.statCorrections`):
  Cresselia (Def 120->110, SpD 130->120), Zacian (Atk 130->120), Zamazenta
  (Atk 130->120).
- Minior's CSV catch rate is `"30 (Meteorite)255 (Core)"`; it is parsed to `30`
  (the Meteor/shell form, which is what you encounter). Logged in
  `manifest.catchRateNotes`.
- Evolution methods keep every version-group variant. Some exotic triggers carry
  limited extra detail because PokéAPI itself does not expose it (for example
  `three-critical-hits` for Sirfetch'd has no additional fields).
- Only the modern and Gen-1 type charts are provided. The Gen 2-5 charts (Steel
  resisting Ghost and Dark before Gen 6, no Fairy) are not included.
- The `against_*` columns in the source CSV are not used; effectiveness is
  derived from the authoritative type charts instead.

## Kanto location data

Two app-ready files that answer "where, and how easily, can I catch species X in
Kanto, and how far is that from town Y". Both are built by
`scripts/build_locations.py` from four ROM-derived raw datasets
(`kanto_wild_encounters.json`, `kanto_special_encounters.json`,
`kanto_connectivity.json`, `kanto_catch_rates.json`), each of which passed an
adversarial validation pass against the pokered disassembly plus Bulbapedia,
Serebii, and PokemonDB.

Scope is Pokemon Red/Blue (Gen 1). Yellow-only encounters are out of scope.

### `output/locations_kanto.json`

A map keyed by location id. The ids match the node ids in
`connectivity_kanto.json`, so a BFS over the graph and a lookup into this file
share the same keys. `_meta` holds the schema, method list, and rarity-tier
definitions. Every other key is one location:

| field | type | meaning |
|---|---|---|
| `name` | string | display name (e.g. `"Cerulean Cave"`) |
| `type` | string | `town`, `route`, `water`, `cave`, or `building` |
| `catchable` | object[] | every obtainable species at this location |

Each `catchable` entry:

| field | type | meaning |
|---|---|---|
| `dexNumber` | int | national dex number |
| `name` | string | display name, from `pokemon.json` |
| `method` | string | how you obtain it (see below) |
| `version` | string | `red`, `blue`, or `both` |
| `rarityTier` | string | `common`, `uncommon`, `rare`, `very_rare`, `static`, or `guaranteed` |
| `minLevel` / `maxLevel` | int \| null | level range across all sub-areas; null for trades |
| `catchRate` | int \| null | Gen-1 catch-rate byte (0..255); null when exempt |
| `catchRateExempt` | bool | true only for Safari Zone |
| `note` | string | optional, present when a caveat applies |

Methods: `grass`, `surf`, `old_rod`, `good_rod`, `super_rod`, `safari`, `static`,
`starter`, `gift`, `fossil`, `game_corner`, `trade`.

Rarity tiers for wild methods come from the Gen-1 encounter-slot weights in
`probabilities.asm` (slot chances `51,51,39,25,25,25,13,13,11,3` out of 256). A
species' weight is the sum of the slots it fills in a table: `common` is 15% or
more, `uncommon` is 5 to 14%, `rare` is 1 to 4%, `very_rare` is under 1%. Fishing
tiers use the same thresholds on the per-bite selection probability. `static`
marks a single fixed overworld encounter you battle (a catch roll still applies),
and `guaranteed` marks a species you receive without any catch roll (starter,
gift, fossil revival, Game Corner prize, or in-game trade).

Counts: 47 locations (44 non-empty; Pewter, Lavender, and Indigo Plateau have no
wild encounters and no fishable water), 400 catchable entries, 114 distinct
species. The 37 species with no direct entry are the Gen-1 evolution-only forms
(Ivysaur, Charizard, Nidoking, Alakazam, Gyarados, Dragonite, and so on) plus Mew,
which is event/glitch only.

### `output/connectivity_kanto.json`

The Kanto overworld as an undirected adjacency graph for BFS proximity: 47 nodes
(locations) and 51 edges (map connections). `_meta` carries the type taxonomy and
the modeling notes. `nodes` is `{id, name, type}`; `edges` is a list of
`[idA, idB]` pairs, each listed once. The graph is fully connected (every node is
reachable from every other), with no dangling references, duplicate edges,
self-loops, or isolated nodes.

### Provenance and reconciliations

- Catch rates are the Gen-1 base-stats bytes from `kanto_catch_rates.json`. These
  are the correct Red/Blue values and differ from the modern figures in
  `pokemon.json` for one species: Raticate is 90 in Gen 1 versus 127 later. The
  Gen-1 value 90 is used.
- The ghost Marowak on Pokemon Tower 6F is excluded from `catchable`. It is fought
  as an opponent and departs when defeated, so it is never captured.
- The unused Butterfree-for-Beedrill trade is excluded. It is a data leftover from
  the Japanese version and is not reachable in English Red/Blue.
- The Safari Zone is built from the ROM wild tables (grass walk-ins plus the
  Super Rod group) and every entry is marked `catchRateExempt`, because safari
  mechanics (bait, rock, flee) replace the normal catch-rate roll. The `safari`
  method entries in the raw special-encounter file were verified to be a subset of
  those wild tables and were dropped to avoid duplication.
- In the Safari Zone, Nidoran-M / Nidoran-F and Nidorino / Nidorina are marked
  `both`, because the ROM tables place both genders in both versions (they differ
  only by area and rate). Only Scyther (red) and Pinsir (blue) are strictly
  version-exclusive there.

### Remaining caveats

- Old Rod (Magikarp) and Good Rod (Poliwag / Goldeen) use fixed ROM tables usable
  at any water tile, so they are location-independent. They are attached to every
  non-Safari node that has fishable water, each flagged with a `note`. This is a
  deliberate modeling choice, not per-tile ROM data.
- Level ranges aggregate across all floors and sub-areas that map to one node (for
  example Cerulean Cave folds 1F, 2F, and B1F). A species' `rarityTier` is the
  best (easiest) tier seen across those sub-areas.
- Game Corner prizes that are buyable in both versions collapse to `version: both`
  with a level range that spans both games, so the exact per-version prize level
  and coin cost are not preserved (for example Clefairy is level 8 in Red and 12
  in Blue, stored as level 8 to 12).
- In-game trades store null levels, because the received Pokemon inherits the level
  of the Pokemon you trade in.
- Guaranteed methods list the species catch rate for reference, but the Pokemon is
  received without a catch roll.
- Dragonite's catch rate is 45 in Red/Blue. Yellow uses 9, which is out of scope
  here. Flagged as a low-severity version caveat only.
- Viridian to Pewter is modeled through the `viridian_forest` node rather than a
  direct edge, which mildly inflates that hop distance. Viridian Forest genuinely
  sits on Route 2, so this is a modeling choice documented in
  `connectivity_kanto.json` `_meta.modelingNotes`, not an error.
