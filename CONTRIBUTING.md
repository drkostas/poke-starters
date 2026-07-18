# Contributing to Poké Starters

Thanks for your interest. This is a small, self-contained project and contributions of any size are welcome, from a typo fix to a new region.

## Ground rules

- Be respectful. See the [Code of Conduct](./CODE_OF_CONDUCT.md).
- Open an issue before a large change so we can agree on the approach.
- Keep the app a single self-contained vanilla-JS file. No frameworks, no build-time bundler for the app itself.

## Project layout

| Path | What it is |
|---|---|
| `app/lab.template.html` | The source template. **Edit this**, not `lab.built.html`. |
| `app/build_lab.py` | Inlines fonts, the tour, and the Oak sprite into `lab.built.html`. |
| `app/optimizer.mjs` / `src/engine/optimizer.mjs` | The engine. These two copies must stay identical (a test guards it). |
| `app/worker.mjs` | The Web Worker that runs the search off the main thread. |
| `data-pipeline/` | Scripts that generate `app/data`, sprites, and maps. |
| `tests/` | `node --test` engine tests and Playwright end-to-end tests. |

## Setup

You need Python 3 (to build and serve) and Node 20+ (to run the tests).

```bash
git clone https://github.com/drkostas/poke-starters.git
cd poke-starters
npm install                 # test tooling only (no app dependencies)
npm run serve               # http://localhost:4788/lab.built.html
```

## Making a change

1. Edit `app/lab.template.html` (or the engine in `src/engine/optimizer.mjs`).
2. If you changed the engine, copy it to `app/optimizer.mjs` so the two stay in sync.
3. Rebuild the single-file app:
   ```bash
   npm run build
   ```
4. Run the checks (all must pass):
   ```bash
   npm run lint
   npm test                 # engine unit + invariant tests
   npm run test:e2e         # end-to-end on Chromium, WebKit, Firefox
   ```
   The first e2e run needs the browsers: `npx playwright install`.
5. If it is a UI change, look at it in the browser at both desktop and mobile widths. The app must stay usable by keyboard and screen reader, and pass an axe check.

## Pull requests

- Branch from `main`, name it `fix/short-name` or `feat/short-name`.
- Keep the PR focused on one thing.
- Fill in the PR template. Reference the issue with `Closes #N`.
- CI runs the lint, engine tests, a build-drift check, and the cross-browser e2e on every PR. Keep it green.
- Do not commit `node_modules`, `test-results`, or generated screenshots.

## Commit messages

Short, present tense, and specific. `fix: clamp Oak sprite to the viewport on landscape` beats `update stuff`. Conventional-commit prefixes (`fix:`, `feat:`, `docs:`, `test:`, `chore:`) are appreciated but not required.

## Good first issues

Check the [issues labelled `good first issue`](https://github.com/drkostas/poke-starters/issues?q=is%3Aopen+label%3A%22good+first+issue%22). Data corrections, a new encounter table, and small UI polish are all great entry points.
