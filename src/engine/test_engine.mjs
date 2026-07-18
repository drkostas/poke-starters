import { readFileSync } from 'node:fs';
import { optimize } from './optimizer.mjs';

const OUT = '/Users/gkos/Projects/pokemon_fun/data-pipeline/output';
const load = (f) => JSON.parse(readFileSync(`${OUT}/${f}`, 'utf8'));
const data = { pokemon: load('pokemon.json'), typeChart: load('type_chart.json'), chains: load('evolution_chains.json') };

function show(title, params){
  const t0 = Date.now();
  const out = optimize(data, params);
  const ms = Date.now()-t0;
  console.log(`\n=== ${title} ===  (${ms}ms)`);
  console.log('trace:', JSON.stringify(out.trace));
  out.results.slice(0,5).forEach(r=>{
    const names = r.members.map(m=>`${m.baseName}->${m.finalName}[${m.finalTypes.join('/')}] bst${m.bst}`).join('  |  ');
    console.log(`#${r.rank} T${r.tier} ${r.strategyLabel} | fair ${r.score.fair} cov ${r.score.cov} tri ${r.score.tri} shared ${r.score.shared} spread ${r.score.spread}`);
    console.log('     '+names);
  });
}

// 1) Classic: Gen1, size3, perfect triangle, mons that fully evolve (2 evolutions), balanced BST band
show('Gen1 · trio · perfect triangle · 2-evo · BST(last) 480-560', {
  generations:[1], size:3, evolutions:2, primaryStrategy:'triangle',
  bstStage:'last', bstMin:480, bstMax:560, excludeLegendary:true, results:10,
});

// 2) Gen1, size3, max coverage, any evolutions
show('Gen1 · trio · max coverage · any-evo', {
  generations:[1], size:3, evolutions:'any', primaryStrategy:'coverage',
  bstStage:'last', bstMin:0, bstMax:9999, results:10,
});

// 3) Gen1, size2 (soul-link), min shared weakness
show('Gen1 · pair · min shared weakness', {
  generations:[1], size:2, evolutions:'any', primaryStrategy:'weakness',
  bstStage:'avg', results:10,
});

// 4) Gen3, size3, stat-fairness, tight band
show('Gen3 · trio · stat-fairness · BST(last) 500-540', {
  generations:[3], size:3, evolutions:2, primaryStrategy:'fairness',
  bstStage:'last', bstMin:500, bstMax:540, results:10,
});
