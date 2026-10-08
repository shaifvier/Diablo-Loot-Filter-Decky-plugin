const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
function store(handlers) {
  const source = fs.readFileSync('src/viewer/store.ts', 'utf8');
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(js, { exports, console, require: name => name === '@decky/api' ? { callable: method => (...args) => handlers[method](...args) } : { useSyncExternalStore: () => {} } });
  return exports;
}
const reply = data => ({ ok: true, data });
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; };
const reference = variant => ({ id: 'xf9um40q', variantId: variant, gear: [], skills: { steps: [{}], activeStep: 0 }, paragon: { steps: [{ boards: [{ allocations: [{ key: "board/1" }, { key: "board/2" }] }, { allocations: [] }] }], activeStep: 0 } });
const progress = completed => ({ completed, total: 10, needsReview: false, fingerprint: 'test' });
const tick = () => new Promise(resolve => setImmediate(resolve));

test('late variant responses cannot overwrite the chosen variant; return preserves board and zoom', async () => {
  const first = deferred(), second = deferred();
  const s = store({ get_build_reference: (_, variant) => variant === 0 ? first.promise : second.promise });
  const one = s.loadReference('xf9um40q', 0), two = s.loadReference('xf9um40q', 1);
  second.resolve(reply(reference(1))); await two;
  s.preference({ tab: 'paragon', board: 1, paragonZoom: 4 });
  first.resolve(reply(reference(0))); await one;
  assert.equal(s.snapshot().reference.variantId, 1);
  assert.equal(s.lastVariant("xf9um40q", 0), 1);
  assert.equal(s.snapshot().preferences.board, 1);
  await s.loadReference('xf9um40q', 1);
  assert.equal(s.snapshot().preferences.paragonZoom, 4);
  assert.equal(s.snapshot().preferences.tab, 'paragon');
});

test('rapid node toggles queue durable snapshots and cannot leak into another character', async () => {
  const pending = [], calls = [];
  const s = store({
    get_build_reference: (_, v) => reply(reference(v)),
    get_paragon_progress: () => reply(progress([])),
    set_paragon_progress: (char, id, variant, step, completed) => {
      calls.push({ char, completed }); const d = deferred(); pending.push(d); return d.promise;
    },
  });
  await s.loadReference('xf9um40q', 0); s.update({ characterId: 'first' }); await s.loadProgress();
  s.toggleNode('board/1'); s.toggleNode('board/2'); await tick();
  assert.equal(calls.length, 1);
  assert.deepEqual(Array.from(s.snapshot().progress.completed), ['board/1', 'board/2']);
  s.update({ characterId: 'second' }); const load = s.loadProgress();
  pending[0].resolve(reply(progress(['board/1']))); await tick();
  assert.equal(calls.length, 2);
  assert.equal(calls[1].char, 'first');
  assert.deepEqual(Array.from(calls[1].completed), ['board/1', 'board/2']);
  pending[1].resolve(reply(progress(['board/1', 'board/2']))); await load;
  assert.equal(s.snapshot().characterId, 'second');
  assert.equal(s.snapshot().progress.completed.length, 0);
});

test('failed save reports an error, retains intent, and supports retry', async () => {
  let fail = true;
  const s = store({ get_build_reference: (_, v) => reply(reference(v)), get_paragon_progress: () => reply(progress([])),
    set_paragon_progress: (_, __, ___, ____, completed) => fail ? { ok: false, error: 'Disk full' } : reply(progress(completed)),
  });
  await s.loadReference('xf9um40q', 0); s.update({ characterId: 'first' }); await s.loadProgress();
  s.toggleNode('board/1'); await tick();
  assert.equal(s.snapshot().progressError, 'Disk full');
  assert.deepEqual(Array.from(s.snapshot().progress.completed), ['board/1']);
  s.update({ characterId: 'second' }); await s.loadProgress();
  assert.equal(s.snapshot().progressError, null);
  s.update({ characterId: 'first' }); await s.loadProgress();
  assert.equal(s.snapshot().progressError, 'Disk full');
  assert.deepEqual(Array.from(s.snapshot().progress.completed), ['board/1']);
  fail = false; s.saveProgress(s.snapshot().progress.completed); await tick();
  assert.equal(s.snapshot().progressError, null);
  assert.equal(s.snapshot().progressSaving, false);
});
