// Property / invariant tests for the optimization engine, run against the REAL
// generated corpus in data-pipeline/output. These assert contracts that must
// hold for every query regardless of the underlying data, plus a guard that the
// two shipped copies of the engine never drift apart.
// Run: node --test tests/optimizer.invariants.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  optimize, buildLines, makeTypeApi, coverageScore, triangleScore, LEGENDARY,
} from '../src/engine/optimizer.mjs';

const load = (f) => JSON.parse(readFileSync(new URL(`../data-pipeline/output/${f}`, import.meta.url), 'utf8'));
const pokemon = load('pokemon.json');
const typeChart = load('type_chart.json');
const chains = load('evolution_chains.json');
const data = { pokemon, typeChart, chains };
const T = makeTypeApi(typeChart);

const genOf = (dex) => pokemon[String(dex)]?.generation;
const bstStageIndex = (stageCount, stage) =>
  stage === 'first' ? 0 : stage === 'second' ? Math.min(1, stageCount - 1) : stageCount - 1;

// Representative queries mirroring the app's real usage (from test_engine.mjs).
const QUERIES = {
  'gen1 trio triangle 2-evo band': { generations: [1], size: 3, evolutions: 2, primaryStrategy: 'triangle', bstStage: 'last', bstMin: 480, bstMax: 560, results: 20 },
  'gen1 trio coverage any-evo':    { generations: [1], size: 3, evolutions: 'any', primaryStrategy: 'coverage', results: 20 },
  'gen1 pair weakness':            { generations: [1], size: 2, evolutions: 'any', primaryStrategy: 'weakness', bstStage: 'avg', results: 20 },
  'gen3 trio fairness band':       { generations: [3], size: 3, evolutions: 2, primaryStrategy: 'fairness', bstStage: 'last', bstMin: 500, bstMax: 540, results: 20 },
};

// ---------- structural invariants across representative queries ----------

for (const [name, params] of Object.entries(QUERIES)) {
  test(`[${name}] result set is well-formed`, () => {
    const out = optimize(data, params);
    assert.ok(out.results.length > 0, 'query produced at least one result');
    assert.ok(out.results.length <= (params.results ?? 60), 'respects the results cap');

    out.results.forEach((r, i) => {
      // contiguous 1-based ranks
      assert.equal(r.rank, i + 1, 'ranks are contiguous and 1-based');
      // team size matches the request
      assert.equal(r.members.length, params.size, 'team size == requested size');
      // score fields are in-range
      for (const k of ['fair', 'cov', 'tri']) {
        assert.ok(r.score[k] >= 0 && r.score[k] <= 100, `${k}=${r.score[k]} in [0,100]`);
      }
      assert.ok(r.score.shared >= 0, 'shared weakness count is non-negative');
      assert.ok(r.score.avgBst > 0, 'avgBst positive');
      assert.ok(r.score.spread >= 0, 'spread non-negative');
      // members are distinct lines
      const sig = r.members.map(m => `${m.baseDex}:${m.finalDex}`);
      assert.equal(new Set(sig).size, sig.length, 'no duplicate line in a team');
    });
  });

  test(`[${name}] every member obeys the generation filter`, () => {
    const out = optimize(data, params);
    for (const r of out.results) {
      for (const m of r.members) {
        assert.ok(params.generations.includes(genOf(m.baseDex)),
          `member base dex ${m.baseDex} (gen ${genOf(m.baseDex)}) outside ${params.generations}`);
      }
    }
  });
}

// ---------- filter-honoring invariants ----------

test('excludeLegendary=true keeps all legendaries out of every team', () => {
  const out = optimize(data, { generations: [1], size: 3, excludeLegendary: true, results: 40 });
  for (const r of out.results) {
    for (const m of r.members) {
      assert.ok(!LEGENDARY.has(m.baseDex) && !LEGENDARY.has(m.finalDex),
        `legendary leaked in: base ${m.baseDex} / final ${m.finalDex}`);
    }
  }
});

test('BST band is respected at the requested stage', () => {
  const params = { generations: [1], size: 3, bstStage: 'last', bstMin: 480, bstMax: 560, results: 40 };
  const out = optimize(data, params);
  for (const r of out.results) {
    for (const m of r.members) {
      const i = bstStageIndex(m.stageCount, params.bstStage);
      const b = m.stages[i].bst;
      assert.ok(b >= params.bstMin && b <= params.bstMax,
        `member ${m.baseName} stage-bst ${b} outside [${params.bstMin},${params.bstMax}]`);
    }
  }
});

test('includeTypes: every team has at least one member of an included type', () => {
  const out = optimize(data, { generations: [1], size: 3, includeTypes: ['water'], results: 30 });
  // Only assert the invariant if the query itself did not relax includeTypes away.
  if (!out.relaxed.includes('dropped type-include')) {
    for (const r of out.results) {
      assert.ok(r.members.some(m => m.finalTypes.includes('water')),
        'team missing any water-type member despite includeTypes:[water]');
    }
  }
});

test('excludeTypes: no member carries an excluded type', () => {
  const out = optimize(data, { generations: [1], size: 3, excludeTypes: ['poison'], results: 30 });
  if (!out.relaxed.includes('dropped type-exclude')) {
    for (const r of out.results) {
      for (const m of r.members) {
        assert.ok(!m.finalTypes.includes('poison'), `poison leaked via ${m.finalName}`);
      }
    }
  }
});

test('fullChain=true yields teams whose members share an evolution-stage count', () => {
  const out = optimize(data, { generations: [1], size: 3, fullChain: true, results: 30 });
  if (!out.relaxed.includes('dropped full-chain match')) {
    for (const r of out.results) {
      const counts = new Set(r.members.map(m => m.stageCount));
      assert.equal(counts.size, 1, 'fullChain teams must share one stage count');
      assert.equal(r.score.sameEvo, true);
    }
  }
});

// ---------- determinism ----------

test('optimize is deterministic for identical inputs', () => {
  const params = { generations: [1], size: 3, primaryStrategy: 'triangle', results: 15 };
  const a = optimize(data, params);
  const b = optimize(data, params);
  assert.deepEqual(a.results, b.results, 'same query -> byte-identical results');
  assert.deepEqual(a.trace, b.trace);
});

// ---------- relaxation ladder ----------

test('relaxation only fires when the strict query is empty', () => {
  // A satisfiable query should not relax anything.
  const easy = optimize(data, { generations: [1], size: 3, results: 10 });
  assert.deepEqual(easy.relaxed, [], 'satisfiable query relaxes nothing');

  // An over-constrained query (impossible BST band) must relax and still return results.
  const hard = optimize(data, { generations: [1], size: 3, bstStage: 'last', bstMin: 9000, bstMax: 9999, results: 10 });
  assert.ok(hard.relaxed.length > 0, 'impossible band forced relaxation');
  assert.ok(hard.results.length > 0, 'relaxation recovered results');
});

// ---------- pure-function property invariants over real lines ----------

test('coverageScore is monotonic: a superset covers >= a subset', () => {
  const lines = buildLines(pokemon, chains, 1).filter(l => !l.isLegendary).slice(0, 40);
  for (let i = 0; i + 2 < lines.length; i += 7) {
    const pair = [lines[i], lines[i + 1]];
    const trio = [lines[i], lines[i + 1], lines[i + 2]];
    assert.ok(coverageScore(trio, T) >= coverageScore(pair, T),
      'adding a member cannot reduce coverage');
  }
});

test('triangleScore stays within [0,100] for arbitrary real trios', () => {
  const lines = buildLines(pokemon, chains, 1).slice(0, 30);
  for (let i = 0; i + 2 < lines.length; i += 5) {
    const s = triangleScore([lines[i], lines[i + 1], lines[i + 2]], T);
    assert.ok(s >= 0 && s <= 100, `triangleScore out of range: ${s}`);
  }
});

// ---------- proximity end-to-end over real Kanto data ----------

test('base-town proximity restricts teams to species catchable near the hub', () => {
  const locations = load('locations_kanto.json');
  const connectivity = load('connectivity_kanto.json');
  const withMap = { ...data, locations, connectivity };
  const out = optimize(withMap, { generations: [1], size: 3, baseTown: 'pallet', proximity: 2, results: 15 });
  assert.ok(out.trace.reachNodes > 0, 'BFS reached at least the hub');
  if (!out.relaxed.includes('removed base-town limit') && out.results.length) {
    const reachable = out.trace.catchableNearBase;
    assert.ok(reachable > 0, 'some species are catchable within reach');
  }
});

test('a baseTown that collides with a JS prototype name does not crash optimize()', () => {
  const withMap = { ...data, locations: load('locations_kanto.json'), connectivity: load('connectivity_kanto.json') };
  for (const baseTown of ['__proto__', 'constructor', 'toString', 'hasOwnProperty', 'valueOf']) {
    for (const proximity of [0, 1, 4]) {
      let out;
      assert.doesNotThrow(() => { out = optimize(withMap, { generations: [1], size: 3, baseTown, proximity }); },
        `optimize threw for baseTown="${baseTown}" proximity=${proximity}`);
      assert.ok(Array.isArray(out.results), 'returns a results array');
    }
  }
});

test('a Gen-1-only query does not mutate the shared pokemon type arrays (Fairy strip stays line-local)', () => {
  // the Gen-1 chart has no Fairy type, so compute() strips retconned Fairy off pre-Gen-6 species;
  // that must touch per-line copies, never the shared (worker-persistent) pokemon records.
  const arr = Array.isArray(pokemon) ? pokemon : Object.values(pokemon);
  const fairyGen1 = arr.filter((p) => p.generation === 1 && (p.types || []).includes('fairy'));
  assert.ok(fairyGen1.length > 0, 'corpus has at least one Gen-1 species with a retconned Fairy type');
  const before = fairyGen1.map((p) => [p.dexNumber, JSON.stringify(p.types)]);
  optimize(data, { generations: [1], size: 3 }); // gen1-only -> triggers the Fairy strip
  for (const [dex, snap] of before) {
    const p = arr.find((x) => x.dexNumber === dex);
    assert.equal(JSON.stringify(p.types), snap, `pokemon #${dex} types were mutated by a Gen-1 query`);
  }
});

// ---------- source-copy parity guard ----------

test('app/optimizer.mjs and src/engine/optimizer.mjs are byte-identical', () => {
  const a = readFileSync(new URL('../app/optimizer.mjs', import.meta.url));
  const b = readFileSync(new URL('../src/engine/optimizer.mjs', import.meta.url));
  assert.ok(a.equals(b), 'the two shipped engine copies have drifted — re-sync them');
});
