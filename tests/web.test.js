/* Headless tests for the report's pure logic. Run: node tests/web.test.js */
'use strict';

const path = require('path');
const fs = require('fs');

const RPT = require(path.join(__dirname, '..', 'web', 'app.js'));
const data = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'reports', 'data.json'), 'utf8'));

let failures = 0;
function check(name, cond, detail) {
  console.log((cond ? 'ok   ' : 'FAIL ') + name + (cond || detail === undefined ? '' : ' -> ' + detail));
  if (!cond) failures++;
}

const obs = data.observations;

// --- filters ---------------------------------------------------------------
check('empty filters return everything', RPT.apply(obs, RPT.emptyFilters()).length === obs.length,
  RPT.apply(obs, RPT.emptyFilters()).length);

const textOnly = RPT.apply(obs, Object.assign(RPT.emptyFilters(), { test: 'text' }));
check('test=text keeps only text runs', textOnly.every(o => o.test === 'text'));
check('test=text count', textOnly.length === 535, textOnly.length);

const visionOnly = RPT.apply(obs, Object.assign(RPT.emptyFilters(), { test: 'vision' }));
check('test=vision count', visionOnly.length === 120, visionOnly.length);

const oneModel = RPT.apply(obs, Object.assign(RPT.emptyFilters(), { models: ['baseten/mammoth-1:free'] }));
check('model filter', oneModel.every(o => o.model === 'baseten/mammoth-1:free') && oneModel.length === 107,
  oneModel.length);

const okOnly = RPT.apply(obs, Object.assign(RPT.emptyFilters(), { out: 'ok' }));
check('out=ok keeps only correct', okOnly.every(o => o.ok === 1));

const skipped = RPT.apply(obs, Object.assign(RPT.emptyFilters(), { out: 'skip' }));
check('out=skip finds the box skips', skipped.length === 5 && skipped.every(o => o.skip), skipped.length);

const searched = RPT.apply(obs, Object.assign(RPT.emptyFilters(), { q: 'v3-1' }));
check('search is case-insensitive and matches task ids', searched.length > 0 &&
  searched.every(o => (o.task + ' ' + o.model + ' ' + o.cat).toLowerCase().includes('v3-1')), searched.length);

const combo = RPT.apply(obs, Object.assign(RPT.emptyFilters(),
  { test: 'vision', models: ['typesafe/jev-1.14'], out: 'fail' }));
check('combined filters', combo.every(o => o.test === 'vision' && o.model === 'typesafe/jev-1.14' && o.ok === 0));

// --- aggregation -----------------------------------------------------------
const agg = RPT.aggregate(obs);
check('aggregate total', agg.total === obs.length, agg.total);
const scored = obs.filter(o => o.ok !== null);
const expectedAcc = scored.reduce((s, o) => s + o.ok, 0) / scored.length;
check('aggregate accuracy', Math.abs(agg.acc - expectedAcc) < 1e-12, agg.acc + ' vs ' + expectedAcc);
check('aggregate model count', agg.models.length === 8, agg.models.length);
check('models sorted by accuracy desc',
  agg.models.every((m, i) => i === 0 || (agg.models[i - 1].acc || 0) >= (m.acc || 0)));

// per-model accuracy must match the text summary for text-only slice
const textAgg = RPT.aggregate(textOnly);
let mismatch = 0;
Object.keys(data.text_summary.models).forEach(slug => {
  const m = textAgg.models.find(x => x.model === slug);
  const want = data.text_summary.models[slug].accuracy;
  if (!m || Math.abs(m.acc - want) > 1e-9) mismatch++;
});
check('text accuracy matches summary.json per model', mismatch === 0, mismatch + ' mismatches');

// vision levels
const visAgg = RPT.aggregate(visionOnly);
check('vision has 5 levels', visAgg.levels.length === 5, visAgg.levels.length);

// --- ece -------------------------------------------------------------------
check('ece perfect', RPT.ece([{ conf: 0.5, ok: 1 }, { conf: 0.5, ok: 0 }], 10) === 0);
check('ece overconfident', Math.abs(RPT.ece([{ conf: 0.9, ok: 0 }, { conf: 0.9, ok: 0 }], 10) - 0.9) < 1e-12);
check('ece ignores null conf', RPT.ece([{ conf: null, ok: 1 }], 10) === null);

// --- hash roundtrip --------------------------------------------------------
const f = RPT.emptyFilters();
f.test = 'vision';
f.models = ['typesafe/jev-1.14', 'respan/span-02'];
f.cats = ['vision_layout', 'score'];
f.out = 'fail';
f.q = 'V3';
const hash = RPT.toHash(f, 'explore');
const back = RPT.parseHash(hash);
check('hash keeps view', back.view === 'explore', back.view);
check('hash keeps test', back.filters.test === 'vision', back.filters.test);
check('hash keeps models', back.filters.models.join(',') === f.models.join(','), back.filters.models.join(','));
check('hash keeps cats', back.filters.cats.join(',') === f.cats.join(','), back.filters.cats.join(','));
check('hash keeps out', back.filters.out === 'fail', back.filters.out);
check('hash keeps query', back.filters.q === 'V3', back.filters.q);
check('hash ignores junk', RPT.parseHash('#test=nonsense&out=zzz').filters.test === 'all');

// --- payload health --------------------------------------------------------
const bad = obs.filter(o => [o.p, o.b, o.conf].some(v => typeof v === 'number' && !isFinite(v)));
check('no NaN/Infinity in numeric fields', bad.length === 0, bad.length);
check('every observation has an id', obs.every(o => typeof o.id === 'string' && o.id.length > 3));
check('claim statuses are from the enum',
  data.claims.every(c => ['подтверждено', 'опровергнуто', 'частично', 'непроверяемо', 'несопоставимо'].includes(c.status)));
check('claims count', data.claims.length >= 18, data.claims.length);

// --- built HTML: embedding, offline purity, DOM contract -------------------
const ROOT = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(ROOT, 'reports', 'index.html'), 'utf8');

const m = html.match(/<script id="payload" type="application\/json">([\s\S]*?)<\/script>/);
check('payload block exists', !!m);
let embedded = null;
try { embedded = JSON.parse(m[1]); } catch (e) { embedded = null; }
check('embedded payload parses', embedded !== null);
check('embedded observations match data.json',
  embedded && embedded.observations.length === data.observations.length,
  embedded ? embedded.observations.length : 'n/a');
check('embedded claims match', embedded && embedded.claims.length === data.claims.length);
check('no NaN/Infinity literal in payload', m && !/:\s*(NaN|-?Infinity)/.test(m[1]));

const external = (html.match(/(?:src|href)="https?:\/\//g) || []).length;
check('no external src/href', external === 0, external);
check('no @import', !/@import/.test(html));
check('no script with src', !/<script[^>]+src=/.test(html));

const appJs = fs.readFileSync(path.join(ROOT, 'web', 'app.js'), 'utf8');
const ids = Array.from(new Set(Array.from(appJs.matchAll(/el\('([a-z0-9\-]+)'\)/g)).map(x => x[1])));
const missing = ids.filter(id => !new RegExp('id="' + id + '"').test(html));
check('every getElementById target exists', missing.length === 0, missing.join(','));

const views = ['overview', 'text', 'vision', 'explore', 'local', 'methods'];
check('all six sections exist', views.every(v => html.includes('id="v-' + v + '"')));
check('size under 2 MB', Buffer.byteLength(html) < 2_000_000, Buffer.byteLength(html));

console.log('\n' + (failures ? failures + ' FAILED' : 'all web tests passed'));
process.exit(failures ? 1 : 0);