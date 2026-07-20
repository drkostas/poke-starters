// Starter-combination optimization engine (pure, data-injected).
// Data shapes:
//   pokemon: { "<dex>": {dexNumber,name,generation,types[],baseStats,bst,catchRate,
//              isFinalEvolution,evolutionChainId,evolutionStageCount} }
//   typeChart: { attackType: { defenseType: multiplier } }
//   chains: { "<id>": {id, species:[{dexNumber,name,stage}], stageCount, ...} }
//   locations?: { "<nodeId>": {name,type,catchable:[{dexNumber,...}]} }
//   connectivity?: { nodes:[{id,...}], edges:[[a,b],...] }

export const TYPES = ['normal','fire','water','electric','grass','ice','fighting','poison',
  'ground','flying','psychic','bug','rock','ghost','dragon','dark','steel','fairy'];

// legendary/mythical dex numbers (Gen 1-3 curated; extend as needed)
export const LEGENDARY = new Set([144,145,146,150,151, // Kanto
  243,244,245,249,250,251,                              // Johto
  377,378,379,380,381,382,383,384,385,386]);            // Hoenn

const TIDX = {}; TYPES.forEach((t,i)=>TIDX[t]=i);
function popcount(x){ x=x-((x>>1)&0x55555555); x=(x&0x33333333)+((x>>2)&0x33333333); return (((x+(x>>4))&0x0f0f0f0f)*0x01010101)>>24; }

// ---------- type effectiveness ----------
export function makeTypeApi(typeChart){
  const eff = (att, defTypes) => defTypes.reduce((m,d)=> m * (typeChart[att]?.[d] ?? 1), 1);
  const bestOffense = (attTypes, defTypes) => Math.max(...attTypes.map(a=>eff(a,defTypes)));
  const weaknesses = (defTypes) => {
    const w = {};
    for(const a of TYPES){ const m = eff(a, defTypes); if(m>1) w[a]=m; }
    return w;
  };
  return { eff, bestOffense, weaknesses };
}

// ---------- evolution lines ----------
// Build one line PER root-to-leaf evolution path available in this era.
// Era-aware root = an available species with no available parent (so Gen-1 Pikachu roots at
// Pikachu even though its chain's stage-0 is Pichu; Eevee emits a line per eeveelution branch).
export function buildLines(pokemon, chains, maxGen=9){
  const lines = [];
  for(const cid of Object.keys(chains)){
    const ch = chains[cid];
    const availDex = new Set((ch.species||[])
      .filter(s=>{ const sp=pokemon[String(s.dexNumber)]; return sp && sp.generation<=maxGen; })
      .map(s=>s.dexNumber));
    if(!availDex.size) continue;
    const adj = Object.create(null), hasParent = new Set(); // prototype-less for consistency/safety
    for(const e of (ch.edges||[])){
      if(availDex.has(e.fromDex) && availDex.has(e.toDex)){ (adj[e.fromDex]=adj[e.fromDex]||[]).push(e.toDex); hasParent.add(e.toDex); }
    }
    const roots = [...availDex].filter(d=>!hasParent.has(d));
    const paths = [];
    const dfs = (d, path)=>{ const nx=adj[d]||[]; if(!nx.length){ paths.push(path); return; } for(const t of nx) dfs(t, [...path, t]); };
    for(const r of roots) dfs(r, [r]);
    for(const path of paths){
      // hold per-line COPIES (with a fresh types array) so any downstream typing tweak (e.g. the
      // Gen-1 Fairy strip) can't mutate the shared, worker-persistent pokemon records.
      const stages = path.map(d=>{ const sp=pokemon[String(d)]; return sp ? {...sp, types:[...sp.types]} : null; }).filter(Boolean);
      if(!stages.length) continue;
      const base = stages[0], finalSp = stages[stages.length-1];
      const bstByStage = stages.map(s=>s.bst);
      lines.push({
        chainId: ch.id, baseDex: base.dexNumber, baseName: base.name, generation: base.generation,
        stageCount: stages.length, stages, base, final: finalSp,
        baseTypes: base.types, finalTypes: finalSp.types, catchRate: base.catchRate,
        bstByStage, avgBst: Math.round(bstByStage.reduce((a,b)=>a+b,0)/bstByStage.length),
        isLegendary: LEGENDARY.has(base.dexNumber) || stages.some(s=>LEGENDARY.has(s.dexNumber)),
      });
    }
  }
  return lines;
}

// ---------- sub-scores ----------
export function fairness(bsts){
  const avg = bsts.reduce((a,b)=>a+b,0)/bsts.length;
  const sd = Math.sqrt(bsts.reduce((a,b)=>a+(b-avg)**2,0)/bsts.length);
  return Math.max(0, Math.round(100 - sd*1.25));
}
const permute = (arr) => arr.length<=1 ? [arr]
  : arr.flatMap((x,i)=>permute([...arr.slice(0,i),...arr.slice(i+1)]).map(p=>[x,...p]));

// perfect triangle: a cyclic ordering where each member SE-beats the next
export function triangleScore(combo, T){
  const n = combo.length;
  if(n<2) return 0;
  const beats = (i,j)=> T.bestOffense(combo[i].finalTypes, combo[j].finalTypes) >= 2;
  // a real 2-cycle needs MUTUAL super-effectiveness (100); a one-way hit is only partial (30) — this
  // matches the live scorer (triFromIdx) so the exported score and the displayed score never diverge.
  if(n===2){ const ab=beats(0,1), ba=beats(1,0); return (ab&&ba)?100:((ab||ba)?30:0); }
  const idx = combo.map((_,i)=>i);
  for(const p of permute(idx)){
    let ok = true;
    for(let k=0;k<n;k++){ if(!beats(p[k], p[(k+1)%n])){ ok=false; break; } }
    if(ok) return 100;
  }
  // partial: fraction of members that SE-beat at least one other
  let winners = 0;
  for(let i=0;i<n;i++) for(let j=0;j<n;j++) if(i!==j && beats(i,j)){ winners++; break; }
  return Math.round(winners/n*60);
}

export function coverageScore(combo, T){
  const covered = new Set();
  for(const t of TYPES){
    for(const m of combo){ if(T.bestOffense(m.finalTypes,[t]) >= 2){ covered.add(t); break; } }
  }
  return Math.round(covered.size/TYPES.length*100);
}

export function sharedWeaknesses(combo, T){
  const counts = {};
  for(const m of combo){ const w = T.weaknesses(m.finalTypes); for(const t in w) counts[t]=(counts[t]||0)+1; }
  return Object.values(counts).filter(c=>c>=2).length;
}

const commonType = (combo) => {
  const inter = combo.map(m=>new Set(m.finalTypes)).reduce((a,b)=> new Set([...a].filter(x=>b.has(x))));
  return inter.size>0;
};

// ---------- BFS proximity (optional) ----------
export function bfsReach(connectivity, startId, steps){
  const adj = Object.create(null); // prototype-less: a baseTown like "__proto__"/"toString" must key as data, not crash
  for(const [a,b] of connectivity.edges){ (adj[a]??=[]).push(b); (adj[b]??=[]).push(a); }
  // Surf gate (obtainability): open-water nodes can only be crossed with HM Surf, which a trainer just
  // starting out near their town does not have — so their reach stops at the shore. Encounters that
  // themselves need Surf / the Super Rod / a fossil / a trade are filtered separately, by method.
  const surfGated = Object.create(null);
  for(const n of (connectivity.nodes||[])) if(n && n.type==='water') surfGated[n.id]=true;
  const seen = new Map([[startId,0]]); const q=[startId];
  while(q.length){ const cur=q.shift(); const d=seen.get(cur); if(d>=steps) continue;
    for(const nb of (adj[cur]||[])) if(!seen.has(nb) && !surfGated[nb]){ seen.set(nb,d+1); q.push(nb); } }
  return seen; // Map nodeId -> distance (open-water nodes excluded: they need Surf)
}
// Encounter methods a just-starting trainer can't use near their town: Surf (HM), the Super Rod,
// fossil revival (the tech is far away, e.g. Cinnabar), and trades (need a partner). The old and good
// rods, grass, gifts, the Safari Zone and Game Corner are all fair game. (Matches the source video.)
export const UNOBTAINABLE_METHODS = new Set(['surf','super_rod','fossil','trade']);
const isObtainable = (c)=> !UNOBTAINABLE_METHODS.has(c.method);
export function catchableDexInReach(locations, reach){
  const dex = new Set();
  for(const nodeId of reach.keys()){
    const loc = locations[nodeId]; if(!loc) continue;
    for(const c of (loc.catchable||[])){ if(isObtainable(c)) dex.add(c.dexNumber); }
  }
  return dex;
}
// commonness rank: higher = easier to encounter
export const RARITY_RANK = { guaranteed:5, common:4, static:4, uncommon:3, rare:2, very_rare:1 };
// best (highest) rarity rank per dex, optionally restricted to a reach set of node ids
export function bestRarityByDex(locations, reach){
  const best = {};
  for(const [id,loc] of Object.entries(locations)){
    if(id==='_meta') continue; if(reach && !reach.has(id)) continue;
    for(const c of (loc.catchable||[])){ if(!isObtainable(c)) continue; const r = RARITY_RANK[c.rarityTier] || 1;
      if(!(c.dexNumber in best) || r > best[c.dexNumber]) best[c.dexNumber] = r; }
  }
  return best;
}

// ---------- combination enumeration (with cap) ----------
function chooseCap(pool, N, cap){
  // trim pool so C(|pool|,N) <= cap, keeping the most "startery" lines
  const combosOf = (m)=>{ let c=1; for(let i=0;i<N;i++) c=c*(m-i)/(i+1); return c; };
  if(pool.length<=N || combosOf(pool.length)<=cap) return { pool, capped:false };
  // keep the strongest lines (final-stage BST desc), then more-evolved as tiebreak.
  // (An earlier median-BST tiebreak biased toward mediocrity and dropped Snorlax/Lapras/Gyarados.)
  const finalBst = (l)=> (l.final && l.final.bst) || l.bstByStage[l.bstByStage.length-1] || l.avgBst;
  const sorted = [...pool].sort((a,b)=> (finalBst(b)-finalBst(a)) || (b.stageCount-a.stageCount));
  let m = pool.length;
  while(m>N && combosOf(m)>cap) m--;
  return { pool: sorted.slice(0,m), capped:true, keptOf:pool.length };
}
function* combinations(arr, k, start=0, prefix=[]){
  if(prefix.length===k){ yield prefix; return; }
  for(let i=start;i<=arr.length-(k-prefix.length);i++) yield* combinations(arr,k,i+1,[...prefix,arr[i]]);
}

// ---------- fallback strategy ladder ----------
// rank tiebreaks now penalize shared defensive weakness (a fragile team should not outrank a
// sturdy one) and demote stat-fairness from a dominating term to a light tiebreak everywhere
// except its own strategy. The weakness tier fires at shared<=1 so it isn't dead code at size 6
// (where the global minimum shared weakness is 1).
// The "excellent coverage" bar scales with team size: a 6-member team trivially covers most
// types, so it must clear a higher bar than a 2-member team to earn the coverage tier. Values
// track roughly the 85th percentile of achievable coverage per size (measured), so the tier
// stays reachable at size 2 (coverage tops out near 72) and selective at size 6 (where a fixed
// cov>=80 gate otherwise passed most teams and swallowed the lower tiers).
export const coverageTierThreshold = (n = 3) => Math.min(92, 52 + 7 * n);

export const STRATEGIES = [
  { key:'triangle', label:'Perfect type triangle', pass:(s)=> s.tri>=100,   rank:(s)=> s.tri*3 + s.cov*2 - s.shared*12 + s.fair*0.5 },
  { key:'coverage', label:'Max coverage',          pass:(s)=> s.cov>=coverageTierThreshold(s.n), rank:(s)=> s.cov*3 - s.shared*10 + s.fair*0.5 },
  { key:'weakness', label:'Min shared weakness',   pass:(s)=> s.shared<=1,  rank:(s)=> (100-s.shared*12)*2 + s.cov + s.fair*0.5 },
  { key:'fairness', label:'Max stat-fairness',     pass:(s)=> s.fair>=85,   rank:(s)=> s.fair*3 + s.cov },
  { key:'sametype', label:'Same-type set',         pass:(s)=> s.sameType,   rank:(s)=> s.fair + s.cov - s.shared*6 },
];

const bstAtStage = (l, stage) => {
  if(stage==='avg') return l.avgBst;
  const i = stage==='first'?0 : stage==='second'?Math.min(1,l.bstByStage.length-1) : l.bstByStage.length-1;
  return l.bstByStage[i];
};

// ---------- main optimize ----------
// Public entry: compute, and if a query returns nothing, progressively relax the
// user's hard filters (one at a time) until results appear, reporting what was dropped.
export function optimize(data, params){
  const p = {
    generations:[1], size:3, evolutions:'any', excludeLegendary:true, excludeTradeStuck:false,
    includeTypes:[], excludeTypes:[], bstStage:'last', bstMin:0, bstMax:9999,
    baseTown:null, baseTownRegion:null, proximity:1, primaryStrategy:'triangle', cap:400000, results:60, fullChain:false, rarityMin:0, crossGen:false, ...params,
  };
  const RELAX = [
    { label:'widened BST band',        apply:q=> (q.bstMin>0||q.bstMax<9999) ? {...q, bstMin:Math.max(0,q.bstMin-60), bstMax:Math.min(9999,q.bstMax+60)} : null },
    { label:'extended proximity +1',   apply:q=> (q.baseTown && q.proximity<4) ? {...q, proximity:q.proximity+1} : null },
    { label:'dropped rarity filter',   apply:q=> q.rarityMin>0 ? {...q, rarityMin:0} : null },
    { label:'dropped type-exclude',    apply:q=> q.excludeTypes.length ? {...q, excludeTypes:[]} : null },
    { label:'relaxed evolution count', apply:q=> q.evolutions!=='any' ? {...q, evolutions:'any'} : null },
    { label:'dropped full-chain match',apply:q=> q.fullChain ? {...q, fullChain:false} : null },
    { label:'dropped type-include',    apply:q=> q.includeTypes.length ? {...q, includeTypes:[]} : null },
    { label:'widened BST fully',       apply:q=> (q.bstMin>0||q.bstMax<9999) ? {...q, bstMin:0, bstMax:9999} : null },
    { label:'dropped cross-gen requirement', apply:q=> q.crossGen ? {...q, crossGen:false} : null },
    { label:'removed base-town limit', apply:q=> q.baseTown ? {...q, baseTown:null, baseTownRegion:null} : null },
  ];
  let cur = p; const applied = [];
  let out = compute(data, cur);
  for(let i=0; i<RELAX.length && out.results.length===0; i++){
    const nxt = RELAX[i].apply(cur); if(!nxt) continue;
    cur = nxt; applied.push(RELAX[i].label); out = compute(data, cur);
  }
  out.relaxed = applied;
  // the ACTUAL params the results were computed under (may differ from the request after relaxation),
  // so the map can render the reach/base that the shown teams really reflect.
  out.effProximity = cur.proximity; out.effBaseTown = cur.baseTown; out.effBaseTownRegion = cur.baseTownRegion;
  return out;
}
function compute(data, p){
  const { pokemon, chains } = data;
  // Gen-1-only queries use the authentic Gen-1 type chart (15 types, no dark/steel/fairy and the
  // pre-Gen-6 special cases) when it's provided, so the matchup math matches the era being planned.
  const gen1only = p.generations && p.generations.length && p.generations.every(g=>g===1);
  const typeChart = (gen1only && data.typeChartGen1) ? data.typeChartGen1 : data.typeChart;
  // coverage denominator is the number of types that actually EXIST in the active era's chart
  // (15 for Gen-1, 18 otherwise) so the COV metric can reach 100 instead of capping at 15/18=83.
  const nTypes = Object.keys(typeChart).filter(k=>k!=='_meta').length || 18;
  const T = makeTypeApi(typeChart);
  const maxGen = Math.max(...p.generations);
  let lines = buildLines(pokemon, chains, maxGen).filter(l=> p.generations.includes(l.generation));
  // Gen-1 has no Fairy type: strip the retconned Fairy from pre-Gen-6 species so pure-Fairy mons
  // (Clefairy/Clefable) fall back to Normal instead of scoring/rendering as typeless under the 15-type chart.
  if(gen1only){ const stripFairy=(ts)=>{ const t=ts.filter(x=>x!=='fairy'); return t.length?t:['normal']; };
    for(const l of lines){ l.finalTypes=stripFairy(l.finalTypes); if(l.final&&l.final.types) l.final.types=stripFairy(l.final.types);
      if(l.stages) for(const s of l.stages) if(s.types) s.types=stripFairy(s.types); } }
  const trace = { pool0: lines.length, maxGen };
  if(p.excludeLegendary) lines = lines.filter(l=>!l.isLegendary);
  if(p.evolutions!=='any') lines = lines.filter(l=> (l.stageCount-1)===Number(p.evolutions));
  if(p.includeTypes.length) lines = lines.filter(l=> l.finalTypes.some(t=>p.includeTypes.includes(t)));
  if(p.excludeTypes.length) lines = lines.filter(l=> !l.finalTypes.some(t=>p.excludeTypes.includes(t)));
  lines = lines.filter(l=>{ const b=bstAtStage(l,p.bstStage); return b>=p.bstMin && b<=p.bstMax; });
  // base-town proximity is region-scoped: the town's region supplies the connectivity + locations,
  // so a Johto/Hoenn town runs BFS on that region's graph (not just Kanto).
  const geo = (p.baseTown && p.baseTownRegion && data.regions && data.regions[p.baseTownRegion])
    ? data.regions[p.baseTownRegion]
    : { connectivity: data.connectivity, locations: data.locations };
  let reach = null;
  if(p.baseTown && geo.connectivity) reach = bfsReach(geo.connectivity, p.baseTown, p.proximity);
  if(reach && geo.locations){
    const dex = catchableDexInReach(geo.locations, reach);
    lines = lines.filter(l=> l.stages.some(s=> dex.has(s.dexNumber)));
    trace.reachNodes = reach.size; trace.catchableNearBase = dex.size;
  }
  if(p.rarityMin > 0){
    // with a base town, rarity is scoped to that region's reach; with base=Anywhere it must span
    // EVERY selected generation's region (not just Kanto's data.locations) — take the best per dex.
    let best;
    if(p.baseTown && geo.locations){ best = bestRarityByDex(geo.locations, reach); }
    else if(data.regions){ best = {}; const genR = {1:'kanto',2:'johto',3:'hoenn',4:'sinnoh'};
      const regs = [...new Set(p.generations.map(g=>genR[g]).filter(Boolean))];
      for(const r of regs){ const R = data.regions[r]; if(!R || !R.locations) continue;
        const b = bestRarityByDex(R.locations, null);
        for(const dex in b){ if((b[dex]||0) > (best[dex]||0)) best[dex] = b[dex]; } }
    } else { best = geo.locations ? bestRarityByDex(geo.locations, reach) : {}; }
    lines = lines.filter(l=> l.stages.some(s=> (best[s.dexNumber]||0) >= p.rarityMin));
    trace.rarityMin = p.rarityMin;
  }
  trace.pool = lines.length;

  const { pool, capped, keptOf } = chooseCap(lines, p.size, p.cap);
  trace.capped = capped; if(capped) trace.keptOf = keptOf;
  const n = pool.length, N = p.size;

  // cross-gen: force every SELECTED generation to be represented by at least one member
  // (per-line generation as a bit; a combo must OR to a superset of the selected-gen mask)
  const genBit = new Int32Array(n);
  for(let i=0;i<n;i++) genBit[i] = 1 << pool[i].generation;
  let selGenMask = 0; if(p.crossGen) for(const g of p.generations) selGenMask |= (1 << g);
  // a team must never contain two lines from the SAME base species (branched evolutions — e.g.
  // Vaporeon + Jolteon both descend from Eevee — otherwise share a baseDex and would double up).
  const baseKey = new Int32Array(n);
  for(let i=0;i<n;i++) baseKey[i] = pool[i].baseDex;

  // ---- precompute per-line bitmask vectors (18 types fit in 18 bits) ----
  const covMask = new Int32Array(n), weakMask = new Int32Array(n), selfMask = new Int32Array(n);
  const bstArr = new Float64Array(n), stageArr = new Int32Array(n);
  for(let i=0;i<n;i++){
    const l = pool[i]; let cov=0, weak=0, self=0;
    for(let ti=0;ti<18;ti++){ const t=TYPES[ti];
      if(T.bestOffense(l.finalTypes,[t])>=2) cov |= (1<<ti);
      if(T.eff(t,l.finalTypes)>1) weak |= (1<<ti); }
    for(const t of l.finalTypes) self |= (1<<TIDX[t]);
    covMask[i]=cov; weakMask[i]=weak; selfMask[i]=self;
    bstArr[i]=bstAtStage(l,p.bstStage); stageArr[i]=l.stageCount;
  }
  // beats[i*n+j] = 1 iff line i super-effectively beats line j (dual-type aware)
  const beats = new Uint8Array(n*n);
  for(let i=0;i<n;i++) for(let j=0;j<n;j++)
    if(i!==j && T.bestOffense(pool[i].finalTypes,pool[j].finalTypes)>=2) beats[i*n+j]=1;
  const B = (ix,a,b)=> beats[ix[a]*n+ix[b]]===1;
  // real directed-Hamiltonian-cycle test over the beats relation (each member SE-beats the next)
  const hamCycle = (ix)=>{ const k=ix.length; const vis=new Array(k).fill(false); vis[0]=true;
    const go=(pos,cnt)=>{ if(cnt===k) return B(ix,pos,0);
      for(let nx=1;nx<k;nx++){ if(!vis[nx] && B(ix,pos,nx)){ vis[nx]=true; if(go(nx,cnt+1)) return true; vis[nx]=false; } }
      return false; };
    return go(0,1);
  };
  const triFromIdx = (ix)=>{
    const k=ix.length; if(k<2) return 0;
    if(k===2){ const ab=B(ix,0,1), ba=B(ix,1,0); return (ab&&ba)?100:((ab||ba)?30:0); } // a true 2-cycle needs mutual SE
    let full=true, winners=0;
    for(let x=0;x<k;x++){ let out=0,inn=0; for(let y=0;y<k;y++){ if(x===y) continue;
        if(B(ix,x,y)) out=1; if(B(ix,y,x)) inn=1; }
      if(out) winners++; if(!(out&&inn)) full=false; }
    if(full && hamCycle(ix)) return 100; // necessary condition first (cheap), then confirm a real cycle
    return Math.round(winners/k*60);
  };
  // ---- best single-member swap that reduces the team's shared defensive weakness ----
  const sharedOf = (arr)=>{ let sm=0; for(let a=0;a<arr.length;a++) for(let b=a+1;b<arr.length;b++) sm|=(weakMask[arr[a]]&weakMask[arr[b]]); return popcount(sm); };
  const bestSwap = (ixArr)=>{
    const baseShared = sharedOf(ixArr);
    if(baseShared===0) return null; // already unweak — nothing to fix
    const baseTri = triFromIdx(ixArr);
    let baseCovMask=0; for(const t of ixArr) baseCovMask|=covMask[t]; const baseCov = popcount(baseCovMask);
    const inSet = new Set(ixArr); let best=null;
    for(let slot=0; slot<ixArr.length; slot++){
      const trial = ixArr.slice();
      for(let cand=0; cand<n; cand++){
        if(inSet.has(cand)) continue;
        // never suggest a swap that duplicates a base species already on the team
        let dupBase=false; for(let s2=0;s2<ixArr.length;s2++){ if(s2!==slot && baseKey[ixArr[s2]]===baseKey[cand]){ dupBase=true; break; } }
        if(dupBase) continue;
        // under full-chain match every member shares one stage count; a swap must not break that
        if(p.fullChain && stageArr[cand] !== stageArr[ixArr[0]]) continue;
        trial[slot]=cand;
        // respect the cross-gen requirement: the swapped team must still cover every selected generation
        if(selGenMask){ let gm=0; for(const t of trial) gm|=genBit[t]; if((gm&selGenMask)!==selGenMask) continue; }
        const sh = sharedOf(trial);
        if(sh < baseShared){
          let cov=0; for(const t of trial) cov|=covMask[t]; const covN=popcount(cov);
          // net-benefit gate: don't recommend trading away real offensive coverage for a small
          // weakness cut. Allow at most (weaknesses cut) types of coverage loss.
          if(baseCov-covN > (baseShared-sh)) continue;
          const keepsTri = baseTri>=100 ? (triFromIdx(trial)>=100) : true;
          // weakness cut dominates; among equal cuts prefer one that keeps a perfect triangle, then coverage
          const score = (baseShared-sh)*1000 + (keepsTri?300:0) + covN;
          if(!best || score>best.score) best={slot, cand, sh, cov:covN, score, tri:triFromIdx(trial)};
        }
      }
    }
    if(!best) return null;
    const to = pool[best.cand], from = pool[ixArr[best.slot]];
    return { slot:best.slot, oldShared:baseShared, newShared:best.sh, newCov:Math.round(best.cov/nTypes*100),
      oldTri:baseTri, newTri:best.tri, breaksTriangle: baseTri>=100 && best.tri<100,
      fromDex:from.baseDex, fromName:from.baseName,
      toBaseDex:to.baseDex, toBaseName:to.baseName, toFinalName:to.final.name, toFinalTypes:to.finalTypes };
  };

  // ---- score all combinations over pool indices (cheap bitops, no per-combo alloc) ----
  const scored = [];
  const ix = new Int32Array(N);
  (function rec(start, depth){
    if(depth===N){
      if(selGenMask){ let gm=0; for(let d=0;d<N;d++) gm|=genBit[ix[d]]; if((gm&selGenMask)!==selGenMask) return; }
      let mn=Infinity, mx=-Infinity, sum=0, cov=0, self=selfMask[ix[0]], sameEvo=true, ev=stageArr[ix[0]];
      for(let d=0;d<N;d++){ const i=ix[d]; const b=bstArr[i]; sum+=b; if(b<mn)mn=b; if(b>mx)mx=b;
        cov|=covMask[i]; self&=selfMask[i]; if(stageArr[i]!==ev) sameEvo=false; }
      const avg=sum/N; let sd=0; for(let d=0;d<N;d++){ const diff=bstArr[ix[d]]-avg; sd+=diff*diff; } sd=Math.sqrt(sd/N);
      let sharedMask=0; for(let a=0;a<N;a++) for(let b=a+1;b<N;b++) sharedMask|=(weakMask[ix[a]]&weakMask[ix[b]]);
      scored.push({ ix: Array.from(ix), s:{
        n: N, fair: Math.max(0, Math.round(100 - sd*1.25)), cov: Math.round(popcount(cov)/nTypes*100),
        tri: triFromIdx(ix), shared: popcount(sharedMask), sameType: self!==0, sameEvo,
        avgBst: Math.round(avg), spread: mx-mn } });
      return;
    }
    for(let i=start;i<=n-(N-depth);i++){
      let dup=false; for(let d=0;d<depth;d++){ if(baseKey[ix[d]]===baseKey[i]){ dup=true; break; } } // no two lines from one base species
      if(dup) continue;
      ix[depth]=i; rec(i+1, depth+1); }
  })(0,0);
  trace.combosScored = scored.length;
  // full-chain match: keep only combos whose members share the same evolution-stage count
  const cand = p.fullChain ? scored.filter(x => x.s.sameEvo) : scored;
  trace.afterFullChain = cand.length;

  // order strategies: primary first, then the rest in ladder order
  const order = [p.primaryStrategy, ...STRATEGIES.map(x=>x.key).filter(k=>k!==p.primaryStrategy)];
  const strat = order.map(k=>STRATEGIES.find(x=>x.key===k)).filter(Boolean);
  const primarySt = strat[0] || STRATEGIES[0];
  // The chosen (primary) strategy ALWAYS orders the whole candidate set by its rank(), so picking a
  // strategy always changes the ranking — even when its pass() threshold is unreachable (e.g. size-2
  // coverage never hits cov>=80). tier/badge is assigned by pass() lazily for the kept slice only,
  // not by allocating a wrapper over all ~400k candidates (identical output, far less work + memory).
  const ranked = [...cand].sort((a,b)=> primarySt.rank(b.s) - primarySt.rank(a.s));

  return {
    trace,
    results: ranked.slice(0, p.results).map((r,i)=>{
      let tier = strat.findIndex(st=> st.pass(r.s)); if(tier<0) tier = strat.length;
      const st = strat[tier];
      const combo = r.ix.map(k=>pool[k]);
      return {
        rank:i+1, tier, strategy: st?st.key:'any', strategyLabel: st?st.label:'Best remaining',
        score:{ fair:r.s.fair, cov:r.s.cov, tri:r.s.tri, shared:r.s.shared,
                avgBst:r.s.avgBst, spread:r.s.spread, sameEvo:r.s.sameEvo },
        swap: i<24 ? bestSwap(r.ix) : null, // suggest a weakness-cutting swap for the results users browse
        members: combo.map(l=>({ baseDex:l.baseDex, baseName:l.baseName, finalDex:l.final.dexNumber,
          finalName:l.final.name, finalTypes:l.finalTypes, stageCount:l.stageCount,
          bst:bstAtStage(l,p.bstStage), stages:l.stages.map(s=>({dex:s.dexNumber,name:s.name,bst:s.bst,types:s.types})) })),
      };
    }),
    strategyLadder: strat.map(s=>({key:s.key,label:s.label})),
  };
}
