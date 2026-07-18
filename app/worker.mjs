// Web Worker: runs the optimizer off the main thread so the UI never freezes.
import { optimize } from './optimizer.mjs';
let DATA = null;
self.onmessage = (e) => {
  const m = e.data;
  if (m.type === 'init') { DATA = m.data; self.postMessage({ type: 'ready' }); return; }
  if (m.type === 'optimize') {
    try {
      const t0 = performance.now();
      const out = optimize(DATA, m.params);
      self.postMessage({ type: 'result', id: m.id, out, ms: performance.now() - t0 });
    } catch (err) {
      self.postMessage({ type: 'error', id: m.id, error: String((err && err.message) || err) });
    }
  }
};
