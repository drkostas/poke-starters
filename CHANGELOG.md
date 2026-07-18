# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-18

First public release.

### Added

- **Starter-trio optimizer** across Gens 1 to 3: perfect type-triangle search
  (a real directed-Hamiltonian-cycle test), defensive coverage, shared-weakness,
  and stat-fairness strategies, with an auto-relax ladder for over-tight filters.
- **Era-aware type math**: a Gen-1-only query uses the authentic 15-type Gen-1
  chart. Type charts validated cell by cell against PokéAPI.
- **Gated slot-machine reveal**, ranked-result walking, and a whole-team evolve
  control, with FireRed/LeafGreen and Red/Blue/Yellow sprite sets.
- **Live catch maps** for Kanto, Johto, and Hoenn with ROM-accurate encounter
  tables, route graphs, and base-town breadth-first proximity.
- **Full Pokédex browser** with per-species stats, evolution lines, matchups,
  and wild locations.
- **Professor Oak guided walkthrough** (a short first-time tour and a full
  41-step version) and synthesized Game-Boy-style sound effects.
- **Shareable-link** state, running entirely on a Web Worker.
- **Mobile app-shell**: `Build` / `Team` / `Maps` tabs with a sticky spin bar,
  distinct from the desktop three-column layout.
- **Accessibility**: landmarks, a single page heading, ARIA state on controls, a
  live region for results, dialog focus-traps, reduced-motion and forced-colors
  support, and WCAG AA contrast (axe clean).
- **Tests**: engine unit and invariant tests, plus a cross-browser end-to-end
  suite on Chromium, WebKit, and Firefox, run in CI.

[1.0.0]: https://github.com/drkostas/poke-starters/releases/tag/v1.0.0
