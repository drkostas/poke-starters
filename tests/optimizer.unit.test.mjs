// Unit tests for the starter-combination optimization engine.
// Deterministic, fixture-driven: every case builds a tiny synthetic Pokedex /
// type chart / evolution chain so exact numeric outputs can be asserted.
// Run: node --test tests/optimizer.unit.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  TYPES, LEGENDARY, RARITY_RANK, STRATEGIES, coverageTierThreshold,
  makeTypeApi, buildLines,
  fairness, triangleScore, coverageScore, sharedWeaknesses,
  bfsReach, catchableDexInReach, bestRarityByDex,
  optimize,
} from '../src/engine/optimizer.mjs';

// ---------- shared synthetic fixtures ----------

// A minimal fire>grass>water>fire triangle. Missing entries default to x1.
const TRI_CHART = {
  fire:  { fire: 0.5, grass: 2,   water: 0.5 },
  water: { water: 0.5, fire: 2,   grass: 0.5 },
  grass: { grass: 0.5, water: 2,  fire: 0.5 },
};
const T = makeTypeApi(TRI_CHART);

// mono-type "line-like" objects (only finalTypes is read by the sub-scores)
const mono = (t, bst = 500) => ({ finalTypes: [t], bstByStage: [bst], avgBst: bst });

test('TYPES has the 18 canonical types and a stable order', () => {
  assert.equal(TYPES.length, 18);
  assert.equal(TYPES[0], 'normal');
  assert.equal(TYPES[1], 'fire');
  assert.ok(new Set(TYPES).size === 18, 'no duplicate types');
});

test('LEGENDARY set flags the expected Gen1-3 legendaries and excludes commons', () => {
  for (const dex of [144, 150, 151, 249, 250, 384, 386]) {
    assert.ok(LEGENDARY.has(dex), `dex ${dex} should be legendary`);
  }
  for (const dex of [1, 6, 25, 133]) {
    assert.ok(!LEGENDARY.has(dex), `dex ${dex} should not be legendary`);
  }
});

test('makeTypeApi.eff multiplies dual-type effectiveness', () => {
  // fire vs [grass, ...]: 2x; water vs [fire]: 2x; unknown matchup defaults to 1x
  assert.equal(T.eff('fire', ['grass']), 2);
  assert.equal(T.eff('water', ['fire']), 2);
  assert.equal(T.eff('grass', ['fire']), 0.5);
  assert.equal(T.eff('normal', ['fire']), 1); // absent from chart -> neutral
  // dual type: multiply both defense components
  assert.equal(T.eff('fire', ['grass', 'grass']), 4);
});

test('makeTypeApi.bestOffense picks the strongest of the attacker types', () => {
  assert.equal(T.bestOffense(['fire', 'water'], ['fire']), 2); // water hits fire 2x
  assert.equal(T.bestOffense(['fire'], ['water']), 0.5);
  assert.equal(T.bestOffense(['normal'], ['water']), 1);
});

test('makeTypeApi.weaknesses returns only >1 matchups', () => {
  assert.deepEqual(T.weaknesses(['fire']), { water: 2 });
  assert.deepEqual(T.weaknesses(['water']), { grass: 2 });
  assert.deepEqual(T.weaknesses(['grass']), { fire: 2 });
  assert.deepEqual(T.weaknesses(['normal']), {}); // nothing beats it in this chart
});

test('fairness = 100 when BSTs are identical, clamps to 0 for wild spread', () => {
  assert.equal(fairness([500, 500, 500]), 100);
  assert.equal(fairness([500]), 100);
  assert.equal(fairness([100, 900]), 0); // sd 400 -> 100 - 500 -> clamped
});

test('fairness is monotonically non-increasing as spread widens', () => {
  const tight = fairness([490, 500, 510]);
  const wide = fairness([400, 500, 600]);
  assert.ok(tight >= wide, `tight ${tight} should be >= wide ${wide}`);
  assert.ok(tight >= 0 && tight <= 100);
});

test('triangleScore = 100 for a perfect cyclic triangle', () => {
  const combo = [mono('fire'), mono('grass'), mono('water')];
  assert.equal(triangleScore(combo, T), 100);
});

test('triangleScore for a pair: mutual SE = 100, one-way = 30, none = 0 (matches the live scorer)', () => {
  assert.equal(triangleScore([mono('water'), mono('fire')], T), 30);  // water SE-beats fire, fire can't beat water -> one-way
  assert.equal(triangleScore([mono('fire'), mono('fire')], T), 0);    // 0.5x both ways -> neither hits
  // a real mutual 2-cycle (both members SE-beat each other) scores a full 100
  const MUT = makeTypeApi({ a: { b: 2 }, b: { a: 2 } }); const m2 = (t) => ({ finalTypes: [t] });
  assert.equal(triangleScore([m2('a'), m2('b')], MUT), 100);
});

test('triangleScore gives partial credit when no full cycle exists', () => {
  // fire and grass: fire SE-beats grass, grass does not SE-beat fire -> partial, not 100
  const s = triangleScore([mono('fire'), mono('grass'), mono('normal')], T);
  assert.ok(s > 0 && s < 100, `expected partial credit, got ${s}`);
});

test('coverageScore counts distinct super-effectively-covered types', () => {
  // fire covers grass, water covers fire, grass covers water -> 3 of 18 types
  const combo = [mono('fire'), mono('water'), mono('grass')];
  assert.equal(coverageScore(combo, T), Math.round(3 / 18 * 100)); // 17
  assert.equal(coverageScore([mono('normal')], T), 0);
});

test('sharedWeaknesses counts types that hit 2+ members', () => {
  // two grass mons are both weak to fire -> 1 shared weakness
  assert.equal(sharedWeaknesses([mono('grass'), mono('grass')], T), 1);
  // fire+water+grass each have a distinct weakness -> 0 shared
  assert.equal(sharedWeaknesses([mono('fire'), mono('water'), mono('grass')], T), 0);
});

// ---------- buildLines ----------

const linePokemon = {
  '1': { dexNumber: 1, name: 'Aa', generation: 1, types: ['fire'], bst: 300, catchRate: 45 },
  '2': { dexNumber: 2, name: 'Ab', generation: 1, types: ['fire'], bst: 450, catchRate: 45 },
  '3': { dexNumber: 3, name: 'Ac', generation: 2, types: ['fire'], bst: 525, catchRate: 45 },
};
const lineChains = {
  '1': {
    id: 1, stageCount: 3,
    species: [{ dexNumber: 1 }, { dexNumber: 2 }, { dexNumber: 3 }],
    edges: [{ fromDex: 1, toDex: 2 }, { fromDex: 2, toDex: 3 }],
  },
};

test('buildLines is era-aware: maxGen truncates the reachable final stage', () => {
  const g1 = buildLines(linePokemon, lineChains, 1);
  assert.equal(g1.length, 1);
  assert.equal(g1[0].baseDex, 1);
  assert.equal(g1[0].stageCount, 2, 'gen1 only reaches stage 2');
  assert.equal(g1[0].final.dexNumber, 2);
  assert.deepEqual(g1[0].bstByStage, [300, 450]);
  assert.equal(g1[0].avgBst, 375);

  const g2 = buildLines(linePokemon, lineChains, 2);
  assert.equal(g2.length, 1);
  assert.equal(g2[0].stageCount, 3, 'gen2 unlocks the final stage');
  assert.equal(g2[0].final.dexNumber, 3);
});

test('buildLines re-roots at the earliest AVAILABLE species (Pikachu, not Pichu)', () => {
  const pk = {
    '25': { dexNumber: 25, name: 'Pikachu', generation: 1, types: ['electric'], bst: 320 },
    '26': { dexNumber: 26, name: 'Raichu', generation: 1, types: ['electric'], bst: 485 },
    '172': { dexNumber: 172, name: 'Pichu', generation: 2, types: ['electric'], bst: 205 },
  };
  const ch = {
    '10': {
      id: 10, stageCount: 3,
      species: [{ dexNumber: 172 }, { dexNumber: 25 }, { dexNumber: 26 }],
      edges: [{ fromDex: 172, toDex: 25 }, { fromDex: 25, toDex: 26 }],
    },
  };
  const lines = buildLines(pk, ch, 1);
  assert.equal(lines.length, 1);
  assert.equal(lines[0].baseName, 'Pikachu', 'Pichu (gen2) is unavailable, so Pikachu is the root');
  assert.equal(lines[0].stageCount, 2);
});

test('buildLines emits one line per branch (Eevee-style)', () => {
  const pk = {
    '133': { dexNumber: 133, name: 'Eevee', generation: 1, types: ['normal'], bst: 325 },
    '134': { dexNumber: 134, name: 'Vaporeon', generation: 1, types: ['water'], bst: 525 },
    '135': { dexNumber: 135, name: 'Jolteon', generation: 1, types: ['electric'], bst: 525 },
  };
  const ch = {
    '20': {
      id: 20, stageCount: 2,
      species: [{ dexNumber: 133 }, { dexNumber: 134 }, { dexNumber: 135 }],
      edges: [{ fromDex: 133, toDex: 134 }, { fromDex: 133, toDex: 135 }],
    },
  };
  const lines = buildLines(pk, ch, 1);
  assert.equal(lines.length, 2, 'two branches -> two lines');
  assert.deepEqual(lines.map(l => l.final.name).sort(), ['Jolteon', 'Vaporeon']);
  for (const l of lines) assert.equal(l.baseName, 'Eevee');
});

test('buildLines flags legendary lines by base OR any stage', () => {
  const pk = {
    '144': { dexNumber: 144, name: 'Articuno', generation: 1, types: ['ice', 'flying'], bst: 580 },
    '1': { dexNumber: 1, name: 'Aa', generation: 1, types: ['fire'], bst: 318 },
  };
  const ch = {
    'L': { id: 'L', stageCount: 1, species: [{ dexNumber: 144 }], edges: [] },
    'N': { id: 'N', stageCount: 1, species: [{ dexNumber: 1 }], edges: [] },
  };
  const lines = buildLines(pk, ch, 1);
  const leg = lines.find(l => l.baseDex === 144);
  const norm = lines.find(l => l.baseDex === 1);
  assert.equal(leg.isLegendary, true);
  assert.equal(norm.isLegendary, false);
});

// ---------- proximity / rarity helpers ----------

test('bfsReach returns node->distance up to the step budget', () => {
  const conn = { nodes: [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }],
    edges: [['a', 'b'], ['b', 'c'], ['c', 'd']] };
  const reach = bfsReach(conn, 'a', 2);
  assert.equal(reach.get('a'), 0);
  assert.equal(reach.get('b'), 1);
  assert.equal(reach.get('c'), 2);
  assert.ok(!reach.has('d'), 'd is 3 hops away, beyond budget 2');
});

test('catchableDexInReach unions catchable dex over reached nodes', () => {
  const loc = { a: { catchable: [{ dexNumber: 1 }, { dexNumber: 2 }] },
    b: { catchable: [{ dexNumber: 2 }, { dexNumber: 3 }] },
    c: { catchable: [{ dexNumber: 9 }] } };
  const reach = new Map([['a', 0], ['b', 1]]);
  const dex = catchableDexInReach(loc, reach);
  assert.deepEqual([...dex].sort((x, y) => x - y), [1, 2, 3]);
});

test('RARITY_RANK orders tiers and bestRarityByDex keeps the easiest encounter', () => {
  assert.ok(RARITY_RANK.guaranteed > RARITY_RANK.common);
  assert.ok(RARITY_RANK.common > RARITY_RANK.rare);
  assert.ok(RARITY_RANK.rare > RARITY_RANK.very_rare);
  const loc = {
    _meta: { skip: true },
    a: { catchable: [{ dexNumber: 1, rarityTier: 'rare' }] },
    b: { catchable: [{ dexNumber: 1, rarityTier: 'common' }] },
  };
  const all = bestRarityByDex(loc, null);
  assert.equal(all[1], RARITY_RANK.common, 'keeps the highest (easiest) rank across nodes');
  const restricted = bestRarityByDex(loc, new Set(['a']));
  assert.equal(restricted[1], RARITY_RANK.rare, 'reach set restricts which nodes count');
});

test('STRATEGIES ladder is well-formed', () => {
  const keys = STRATEGIES.map(s => s.key);
  assert.deepEqual(keys, ['triangle', 'coverage', 'weakness', 'fairness', 'sametype']);
  for (const s of STRATEGIES) {
    assert.equal(typeof s.pass, 'function');
    assert.equal(typeof s.rank, 'function');
    assert.equal(typeof s.label, 'string');
  }
});

test('coverage tier threshold is size-aware (reachable at size 2, selective at size 6)', () => {
  // grows with team size, so a bigger team must clear a higher coverage bar
  assert.ok(coverageTierThreshold(2) < coverageTierThreshold(6), 'threshold grows with team size');
  // reachable at size 2: achievable coverage tops out near 72, so the bar must sit below that
  assert.ok(coverageTierThreshold(2) <= 72, 'size-2 threshold is reachable');
  // selective at size 6: a fixed cov>=80 passed most 6-teams, so the bar must be well above 80
  assert.ok(coverageTierThreshold(6) >= 88, 'size-6 threshold is selective');
  // the coverage strategy consumes it: identical coverage tiers differently by team size
  const cov = STRATEGIES.find((s) => s.key === 'coverage');
  assert.equal(cov.pass({ cov: 68, n: 2 }), true, 'cov 68 is excellent for a 2-team');
  assert.equal(cov.pass({ cov: 84, n: 6 }), false, 'cov 84 is not "max coverage" for a 6-team');
  // missing size falls back to a mid default rather than NaN (never silently always-false)
  assert.equal(cov.pass({ cov: 95 }), true, 'defaults sanely when team size is absent');
});

// ---------- optimize() integration on a synthetic Pokedex ----------

// Pokedex with a clear fire/water/grass triangle plus filler, all BST 500 so
// fairness is constant and the triangle wins tier 0.
function triangleData() {
  const mk = (dex, name, type) => ({ dexNumber: dex, name, generation: 1, types: [type], bst: 500, catchRate: 45 });
  const pokemon = {
    '101': mk(101, 'Fyra', 'fire'), '102': mk(102, 'Fyrb', 'fire'),
    '201': mk(201, 'Aqua', 'water'), '301': mk(301, 'Leaf', 'grass'),
    '401': mk(401, 'Norm', 'normal'),
  };
  const chains = {};
  for (const dex of Object.keys(pokemon)) {
    chains[dex] = { id: Number(dex), stageCount: 1, species: [{ dexNumber: Number(dex) }], edges: [] };
  }
  return { pokemon, typeChart: TRI_CHART, chains };
}

test('optimize returns ranked results with the triangle on top', () => {
  const out = optimize(triangleData(), { generations: [1], size: 3, primaryStrategy: 'triangle', results: 10 });
  assert.ok(out.results.length > 0, 'has results');
  // ranks are 1..N contiguous
  out.results.forEach((r, i) => assert.equal(r.rank, i + 1));
  const top = out.results[0];
  assert.equal(top.tier, 0);
  assert.equal(top.strategy, 'triangle');
  assert.equal(top.score.tri, 100);
  assert.equal(top.members.length, 3);
  const types = top.members.flatMap(m => m.finalTypes).sort();
  assert.deepEqual(types, ['fire', 'grass', 'water'], 'the perfect triangle is fire/water/grass');
  assert.equal(out.relaxed.length, 0, 'no relaxation needed');
});

test('optimize relaxes hard filters when a query is empty and reports what it dropped', () => {
  // no dragon-type line exists -> includeTypes:[dragon] yields nothing, forcing relaxation
  const out = optimize(triangleData(), { generations: [1], size: 3, includeTypes: ['dragon'], results: 10 });
  assert.ok(out.results.length > 0, 'relaxation recovered results');
  assert.ok(out.relaxed.includes('dropped type-include'), `relaxed log: ${out.relaxed.join(',')}`);
});

test('optimize honors excludeTypes as a hard filter (no relaxation when results remain)', () => {
  const out = optimize(triangleData(), { generations: [1], size: 3, excludeTypes: ['fire'], results: 10 });
  for (const r of out.results) {
    for (const m of r.members) {
      assert.ok(!m.finalTypes.includes('fire'), 'no fire members survive an explicit exclude');
    }
  }
});
