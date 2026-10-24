/* Decision-model report — vanilla JS, no dependencies.
   Pure functions are exported for headless tests (node tests/web.test.js). */
(function (global) {
  'use strict';

  var PALETTE = ['#4c8dff', '#3fb950', '#d29922', '#f85149', '#a371f7',
                 '#39c5cf', '#db6d28', '#e85aad', '#7ee787', '#ffa657', '#79c0ff'];

  var CAT_EN = {
    abstention: 'Abstention',
    adversarial: 'Adversarial',
    choice_fact: 'Choice: Single Fact',
    choice_multiconstraint: 'Choice: Multi-Constraint',
    choice_near_miss: 'Choice: Near Miss',
    choice_shortcut_trap: 'Choice: Shortcut Trap',
    multilingual: 'RU/EN Pairs',
    noul_false: 'Predicate: False',
    noul_true: 'Predicate: True',
    score: 'Score Rating',
    vision_color: 'Color',
    vision_count: 'Count',
    vision_shape: 'Shape',
    vision_position: 'Position',
    vision_text: 'Text on Image',
    vision_compare: 'Size Comparison',
    vision_symbol: 'Symbol',
    vision_stamp: 'Stamp & Status',
    vision_layout: 'Layout',
    vision_arithmetic: 'Receipt Arithmetic',
    vision_aggregate: 'Sum / Aggregation',
    vision_ratio: 'Value Ratio',
    vision_table: 'Table',
    vision_grid: 'Grid',
    vision_box: 'Coordinates (Box)',
    vision_code: 'Code',
    vision_ocr: 'Text Recognition (OCR)'
  };

  var CAT_HINT = {
    abstention: 'Insufficient information in input; expected answer is "insufficient data"',
    adversarial: 'Prompt injections, negative assertions, unit traps, policy overrides',
    choice_fact: 'Single unambiguous fact/signal in state',
    choice_multiconstraint: 'Requires matching two or more conditions/rules simultaneously',
    choice_near_miss: 'Distractors differ by a single digit, entity, or word',
    choice_shortcut_trap: 'Distractor mirrors exact keywords from input, correct answer does not',
    multilingual: 'Same decision task in Russian and English',
    noul_false: 'Assertion is false; expected answer is "no"',
    noul_true: 'Assertion is true; expected answer is "yes"',
    score: 'Ordinal rubric 0–4; expected answer is a weighted position'
  };

  function catName(cat) { return CAT_EN[cat] || cat; }
  var ruCat = catName; // Alias for backward compatibility

  var SHORT = {
    'baseten/mammoth-1:free': 'mammoth-1',
    'baseten/elephant-1:free': 'elephant-1',
    'inception/mercury-decide:free': 'mercury-decide',
    'inception/mercury-decide': 'mercury-decide',
    'perplexity/pplx-decider-flash-v1.2': 'pplx-flash',
    'perplexity/pplx-decider-v1.2': 'pplx-decider',
    'typesafe/jev-1.14': 'jev-1.14',
    'typesafe/jev-1.13': 'jev-1.13',
    'respan/span-02': 'span-02',
    'cloudflare/clef-flash': 'clef-flash',
    'cloudflare/clef': 'clef',
    'liquid/d1': 'd1',
    'liquid/d1-ultra': 'd1-ultra',
    'vllm-d3-flash': 'd3-flash',
    'vllm-d3-mini': 'd3-mini',
    'vllm-d3-nano': 'd3-nano',
    'vllm-d3-lite': 'd3-lite',
    'vllm-d3-edge': 'd3-edge',
    'Clef-Flash': 'Clef-Flash',
    'Kev-9B': 'Kev-9B',
    'Kev-4B': 'Kev-4B',
    'Laya': 'Laya',
    'Julia-1': 'Julia-1'
  };

  function isLocalModel(m) {
    if (!m) return false;
    if (m.indexOf('(local)') >= 0) return true;
    var locNames = ['Clef-Flash', 'Julia-1', 'Kev-4B', 'Kev-9B', 'Laya',
                    'vllm-d3-edge', 'vllm-d3-flash', 'vllm-d3-lite', 'vllm-d3-mini', 'vllm-d3-nano'];
    return locNames.indexOf(m) >= 0;
  }

  function displayModel(m, isLocal) {
    var cleanName = (m || '').replace(/\s*\(local\)$/, '');
    var base = SHORT[cleanName] || cleanName.split('/').pop().replace(':free', '');
    if (isLocal || isLocalModel(m)) {
      if (base.indexOf('(local)') < 0) base += ' (local)';
    }
    return base;
  }

  function shortModel(m) {
    return SHORT[m] || m.split('/').pop().replace(':free', '');
  }

  /* ------------------------------------------------------------ pure logic */

  function emptyFilters() {
    return { test: 'all', models: [], cats: [], langs: [], diffs: [], out: 'all', q: '', heatFilter: 'all', vmodelsFilter: 'all' };
  }

  function apply(obs, f) {
    var q = (f.q || '').trim().toLowerCase();
    return obs.filter(function (o) {
      if (f.test !== 'all' && o.test !== f.test) return false;
      if (f.models.length && f.models.indexOf(o.model) < 0) return false;
      if (f.cats.length && f.cats.indexOf(o.cat) < 0) return false;
      if (f.langs.length && f.langs.indexOf(o.lang) < 0) return false;
      if (f.diffs.length && f.diffs.indexOf(o.diff) < 0) return false;
      if (f.out === 'ok' && o.ok !== 1) return false;
      if (f.out === 'fail' && o.ok !== 0) return false;
      if (f.out === 'skip' && !o.skip) return false;
      if (q) {
        var hay = (o.task + ' ' + o.model + ' ' + o.cat).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });
  }

  function mean(xs) {
    if (!xs.length) return null;
    var s = 0;
    for (var i = 0; i < xs.length; i++) s += xs[i];
    return s / xs.length;
  }

  function ece(pairs, bins) {
    bins = bins || 10;
    var total = 0, n = 0, i, b, k;
    var acc = [], conf = [], cnt = [];
    for (i = 0; i < bins; i++) { acc.push(0); conf.push(0); cnt.push(0); }
    for (i = 0; i < pairs.length; i++) {
      var c = pairs[i].conf, ok = pairs[i].ok;
      if (c === null || c === undefined) continue;
      b = Math.min(bins - 1, Math.max(0, Math.floor(c * bins)));
      acc[b] += ok; conf[b] += c; cnt[b] += 1; n += 1;
    }
    if (!n) return null;
    for (k = 0; k < bins; k++) {
      if (!cnt[k]) continue;
      total += (cnt[k] / n) * Math.abs(acc[k] / cnt[k] - conf[k] / cnt[k]);
    }
    return total;
  }

  function aggregate(obs) {
    var scored = obs.filter(function (o) { return o.ok !== null; });
    var byModel = {};
    var byCat = {};
    var byLevel = {};
    var byTest = {};

    obs.forEach(function (o) {
      var m = byModel[o.model] || (byModel[o.model] = { model: o.model, n: 0, ok: 0, sk: 0, lat: [], cost: 0, p: [], b: [], cf: [] });
      m.n += 1;
      if (o.ok !== null) {
        m.ok += o.ok;
        if (o.p !== null) m.p.push(o.p);
        if (o.b !== null) m.b.push(o.b);
        if (o.conf !== null) m.cf.push({ conf: o.conf, ok: o.ok });
      } else {
        m.sk += 1;
      }
      if (o.lat) m.lat.push(o.lat);
      m.cost += o.cost || 0;

      if (o.ok !== null) {
        var c = byCat[o.cat] || (byCat[o.cat] = { cat: o.cat, n: 0, ok: 0 });
        c.n += 1; c.ok += o.ok;
        var t = byTest[o.test] || (byTest[o.test] = { test: o.test, n: 0, ok: 0 });
        t.n += 1; t.ok += o.ok;
        if (o.test === 'vision') {
          var l = byLevel[o.level] || (byLevel[o.level] = { level: o.level, n: 0, ok: 0 });
          l.n += 1; l.ok += o.ok;
        }
      }
    });

    var models = Object.keys(byModel).map(function (k) {
      var m = byModel[k];
      var scoredN = m.n - m.sk;
      return {
        model: m.model,
        n: m.n,
        skipped: m.sk,
        scored: scoredN,
        acc: scoredN ? m.ok / scoredN : null,
        brier: mean(m.b),
        ece: ece(m.cf),
        lat: mean(m.lat),
        cost: m.cost
      };
    }).sort(function (a, b) { return (b.acc || 0) - (a.acc || 0); });

    var cats = Object.keys(byCat).map(function (k) {
      var c = byCat[k];
      return { cat: c.cat, n: c.n, acc: c.ok / c.n };
    }).sort(function (a, b) { return a.cat.localeCompare(b.cat); });

    var levels = Object.keys(byLevel).map(function (k) {
      var l = byLevel[k];
      return { level: +l.level, n: l.n, acc: l.ok / l.n };
    }).sort(function (a, b) { return a.level - b.level; });

    return {
      total: obs.length,
      scored: scored.length,
      acc: scored.length ? scored.reduce(function (s, o) { return s + o.ok; }, 0) / scored.length : null,
      cost: obs.reduce(function (s, o) { return s + (o.cost || 0); }, 0),
      models: models,
      cats: cats,
      levels: levels,
      byTest: byTest
    };
  }

  function pair(obs) {
    var cats = {};
    var models = {};
    obs.forEach(function (o) {
      models[o.model] = 1;
      if (o.ok === null) return;
      var key = o.model + '|' + o.cat;
      var p = cats[key] || (cats[key] = { model: o.model, cat: o.cat, n: 0, ok: 0 });
      p.n += 1; p.ok += o.ok;
    });
    Object.keys(cats).forEach(function (k) { cats[k].acc = cats[k].ok / cats[k].n; });
    return { cells: cats, models: Object.keys(models) };
  }

  /* --------------------------------------------------------------- url hash */

  function encodeList(xs) {
    return xs.map(encodeURIComponent).join('~');
  }
  function decodeList(s) {
    return s ? s.split('~').filter(Boolean).map(decodeURIComponent) : [];
  }

  function toHash(f, view) {
    var parts = ['view=' + encodeURIComponent(view || 'overview')];
    if (f.test !== 'all') parts.push('test=' + f.test);
    if (f.models.length) parts.push('models=' + encodeList(f.models));
    if (f.cats.length) parts.push('cats=' + encodeList(f.cats));
    if (f.langs.length) parts.push('langs=' + encodeList(f.langs));
    if (f.diffs.length) parts.push('diffs=' + encodeList(f.diffs));
    if (f.out !== 'all') parts.push('out=' + f.out);
    if (f.q) parts.push('q=' + encodeURIComponent(f.q));
    return '#' + parts.join('&');
  }

  function parseHash(h) {
    var f = emptyFilters();
    var view = 'overview';
    (h || '').replace(/^#/, '').split('&').forEach(function (kv) {
      if (!kv) return;
      var i = kv.indexOf('=');
      var k = decodeURIComponent(kv.slice(0, i));
      var v = kv.slice(i + 1);
      if (k === 'test' && ['all', 'text', 'vision'].indexOf(v) >= 0) f.test = v;
      else if (k === 'models') f.models = decodeList(v);
      else if (k === 'cats') f.cats = decodeList(v).map(decodeURIComponent);
      else if (k === 'langs') f.langs = decodeList(v);
      else if (k === 'diffs') f.diffs = decodeList(v);
      else if (k === 'out' && ['all', 'ok', 'fail', 'skip'].indexOf(v) >= 0) f.out = v;
      else if (k === 'q') f.q = decodeURIComponent(v);
      else if (k === 'view') view = v;
    });
    return { filters: f, view: view };
  }

  var api = {
    emptyFilters: emptyFilters, apply: apply, aggregate: aggregate, ece: ece,
    pair: pair, parseHash: parseHash, toHash: toHash, mean: mean, PALETTE: PALETTE
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  global.RPT = api;
  if (typeof document === 'undefined') return;

  /* ------------------------------------------------------------------- dom */

  var DATA = null;
  var state = emptyFilters();
  var view = 'overview';

  function el(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function pct(x, d) { return x === null || x === undefined ? '—' : (x * 100).toFixed(d === undefined ? 1 : d) + '%'; }
  function num(x, d) {
    if (x === null || x === undefined) return '—';
    return Number(x).toFixed(d === undefined ? 0 : d);
  }

  function kpi(label, value, note) {
    return '<div class="kpi"><div class="k">' + esc(label) + '</div>' +
      '<div class="v">' + value + '</div><div class="n">' + (note || '') + '</div></div>';
  }

  function barChart(items, valueFmt) {
    if (!items.length) return '<p class="note">No data matches the selected filters.</p>';
    var max = Math.max.apply(null, items.map(function (i) { return i.value || 0; })) || 1;
    return items.map(function (i, idx) {
      var w = Math.max(1, Math.round((i.value / max) * 100));
      var color = idx < 3 ? '#4c8dff' : '#2f4f7a';
      return '<div class="bar-row"><div class="bar-label" title="' + esc(i.label) + '">' +
        esc(i.label) + '</div><div class="bar-track"><div class="bar-fill" style="width:' + w +
        '%;background:' + color + '"></div></div><div class="bar-val">' +
        valueFmt(i.value) + '</div></div>';
    }).join('');
  }

  function heatmap(obs, filter) {
    filter = filter || (typeof state !== 'undefined' && state.heatFilter) || 'all';
    var p = pair(obs);
    var cloudModels = p.models.slice();

    var colList = [];
    if (filter === 'all' || filter === 'cloud') {
      cloudModels.forEach(function (m) {
        var scored = obs.filter(function (o) { return o.model === m && o.ok !== null; });
        var overallAcc = scored.length ? scored.reduce(function (s, o) { return s + o.ok; }, 0) / scored.length : 0;
        colList.push({
          id: m,
          name: shortModel(m),
          full: m,
          isLocal: false,
          acc: overallAcc,
          getCatAcc: function (c) {
            var cell = p.cells[m + '|' + c];
            return cell ? { acc: cell.acc, n: cell.n } : null;
          }
        });
      });
    }

    if (typeof DATA !== 'undefined' && DATA && DATA.local && (filter === 'all' || filter === 'local')) {
      var locs = DATA.local.filter(function (r) { return r.text !== undefined && r.text_by_family; });
      locs.forEach(function (r) {
        colList.push({
          id: r.model + ' (local)',
          name: displayModel(r.model, true),
          full: r.model + ' (local)',
          isLocal: true,
          acc: r.text || 0,
          getCatAcc: function (c) {
            if (r.text_by_family && r.text_by_family[c] !== undefined) {
              return { acc: r.text_by_family[c], n: r.text_n || 107 };
            }
            return null;
          }
        });
      });
    }

    colList.sort(function (a, b) { return (b.acc || 0) - (a.acc || 0); });

    var cats = {};
    Object.keys(p.cells).forEach(function (k) { cats[p.cells[k].cat] = 1; });
    var catList = Object.keys(cats).sort(function (a, b) { return catName(a).localeCompare(catName(b)); });
    if (!colList.length || !catList.length) return '<p class="note">No data available.</p>';

    var html = '<table class="hm2"><thead><tr><th>Category</th>';
    colList.forEach(function (col) {
      var localBadge = col.isLocal ? ' style="color:#79c0ff"' : '';
      html += '<th class="num"' + localBadge + ' title="' + esc(col.full) + ' (' + pct(col.acc) + ')">' + esc(col.name) + '</th>';
    });
    html += '<th class="num">Average</th></tr></thead><tbody>';
    catList.forEach(function (c) {
      html += '<tr><td class="hm-cat" title="' + esc(c) + '">' + esc(catName(c)) + '</td>';
      var sum = 0, cnt = 0;
      colList.forEach(function (col) {
        var cell = col.getCatAcc(c);
        if (!cell || cell.acc === null || cell.acc === undefined) { html += '<td class="hm hm-empty">—</td>'; return; }
        sum += cell.acc; cnt += 1;
        html += '<td class="hm" style="' + heatStyle(cell.acc) + '" title="' + esc(col.full) +
          ', ' + esc(catName(c)) + ': ' + pct(cell.acc) + '">' + Math.round(cell.acc * 100) + '</td>';
      });
      html += '<td class="hm hm-avg">' + (cnt ? Math.round((sum / cnt) * 100) : '—') + '</td></tr>';
    });
    html += '</tbody></table>';
    return '<div class="table-scroll">' + html + '</div>';
  }

  function textModelsTable(textObs) {
    var agg = aggregate(textObs);
    var list = [];
    var cloudSummary = (DATA && DATA.text_summary && DATA.text_summary.models) || {};

    agg.models.forEach(function (m) {
      var entry = cloudSummary[m.model] || {};
      list.push({
        model: m.model,
        displayName: shortModel(m.model),
        isLocal: false,
        type: 'Cloud',
        n: m.scored,
        acc: m.acc,
        ci: entry.accuracy_ci || null,
        brier: m.brier,
        ece: m.ece,
        lat: m.lat,
        cost: '$' + num(m.cost, 4)
      });
    });

    if (DATA && DATA.local) {
      DATA.local.forEach(function (loc) {
        if (loc.text === undefined) return;
        list.push({
          model: loc.model,
          displayName: displayModel(loc.model, true),
          isLocal: true,
          type: 'Local',
          n: loc.text_n || 107,
          acc: loc.text,
          ci: loc.text_ci || null,
          brier: loc.text_brier,
          ece: loc.text_ece,
          lat: loc.text_p50,
          cost: loc.vram_mib ? loc.vram_mib + ' MiB' : '—'
        });
      });
    }

    list.sort(function (a, b) { return (b.acc || 0) - (a.acc || 0); });

    var rows = list.map(function (r, idx) {
      var ciStr = r.ci ? pct(r.ci[0], 1) + ' … ' + pct(r.ci[1], 1) : '—';
      var badgeCls = r.isLocal ? 'style="border-color:#388bfd;color:#79c0ff"' : 'style="color:#8b98a5"';
      var highlight = idx < 3 ? ' style="font-weight:600"' : '';
      return '<tr>' +
        '<td class="mono"' + highlight + ' title="' + esc(r.model) + '">' + esc(r.displayName) + '</td>' +
        '<td><span class="pill neutral" ' + badgeCls + '>' + esc(r.type) + '</span></td>' +
        '<td class="num">' + r.n + '</td>' +
        '<td class="num"' + highlight + '>' + pct(r.acc) + '</td>' +
        '<td class="num" style="color:#8b98a5">' + ciStr + '</td>' +
        '<td class="num">' + num(r.brier, 3) + '</td>' +
        '<td class="num">' + num(r.ece, 3) + '</td>' +
        '<td class="num">' + (r.lat ? num(r.lat, 0) + ' ms' : '—') + '</td>' +
        '<td class="num mono">' + esc(r.cost) + '</td>' +
        '</tr>';
    }).join('');

    return '<div class="table-scroll"><table><thead><tr>' +
      '<th>Model</th><th>Environment</th><th class="num">Tasks</th><th class="num">Accuracy</th>' +
      '<th class="num">95% CI</th><th class="num">Brier</th><th class="num">ECE</th>' +
      '<th class="num">p50 Latency</th><th class="num">Resource / Cost</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>';
  }

  function heatStyle(a) {
    if (a < 0.6) return 'background:rgba(248,81,73,' + (0.10 + (1 - a) * 0.45).toFixed(2) + ')';
    if (a < 0.85) return 'background:rgba(210,153,34,' + (0.12 + (1 - a) * 0.35).toFixed(2) + ')';
    return 'background:rgba(63,185,80,' + (0.10 + a * 0.45).toFixed(2) + ')';
  }

  function calibration(obs) {
    var byModel = {};
    obs.forEach(function (o) {
      if (o.ok === null || o.conf === null) return;
      (byModel[o.model] = byModel[o.model] || []).push(o);
    });
    var series = Object.keys(byModel)
      .filter(function (m) { return byModel[m].length >= 10; })
      .map(function (m) {
        var bins = [];
        for (var i = 0; i < 10; i++) bins.push({ n: 0, ok: 0, c: 0 });
        byModel[m].forEach(function (o) {
          var b = Math.min(9, Math.floor(o.conf * 10));
          bins[b].n += 1; bins[b].ok += o.ok; bins[b].c += o.conf;
        });
        var pts = bins.map(function (b, i) {
          return b.n >= 3 ? { x: (i + 0.5) / 10, y: b.ok / b.n, n: b.n } : null;
        }).filter(Boolean);
        var acc = byModel[m].reduce(function (s, o) { return s + o.ok; }, 0) / byModel[m].length;
        return { model: m, pts: pts, acc: acc };
      })
      .sort(function (a, b) { return b.acc - a.acc; })
      .slice(0, 6);

    if (!series.length) return '<p class="note">Insufficient data for calibration curve.</p>';
    var W = 560, H = 360, P = 42;
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;max-width:' + W + 'px;height:auto">';
    svg += '<rect x="' + P + '" y="10" width="' + (W - P - 12) + '" height="' + (H - P - 10) + '" fill="none" stroke="#2a323d"/>';
    svg += '<line x1="' + P + '" y1="' + (H - P) + '" x2="' + (W - 12) + '" y2="10" stroke="#3b4652" stroke-dasharray="4 4"/>';
    for (var t = 0; t <= 1.001; t += 0.25) {
      var x = P + t * (W - P - 12), y = (H - P) - t * (H - P - 10);
      svg += '<text x="' + x + '" y="' + (H - P + 16) + '" fill="#8b98a5" font-size="10" text-anchor="middle">' + t.toFixed(2) + '</text>';
      svg += '<text x="' + (P - 6) + '" y="' + (y + 3) + '" fill="#8b98a5" font-size="10" text-anchor="end">' + t.toFixed(2) + '</text>';
    }
    series.forEach(function (s, i) {
      var color = PALETTE[i % PALETTE.length];
      var d = s.pts.map(function (p, j) {
        var x = P + p.x * (W - P - 12);
        var y = (H - P) - p.y * (H - P - 10);
        return (j ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
      }).join(' ');
      svg += '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2"/>';
      s.pts.forEach(function (p) {
        var x = P + p.x * (W - P - 12), y = (H - P) - p.y * (H - P - 10);
        svg += '<circle cx="' + x + '" cy="' + y + '" r="3" fill="' + color + '"/>';
      });
    });
    svg += '</svg>';
    var legend = series.map(function (s, i) {
      return '<span><i style="background:' + PALETTE[i % PALETTE.length] + '"></i>' + esc(s.model) + '</span>';
    }).join('');
    return svg + '<div class="legend">' + legend + '</div>' +
      '<p class="note">X-axis: reported model confidence. Y-axis: empirical accuracy. ' +
      'Points along the diagonal indicate perfect calibration; below diagonal indicates overconfidence.</p>';
  }

  function scatter(obs) {
    var agg = aggregate(obs);
    var pts = agg.models.filter(function (m) { return m.acc !== null && m.lat; });
    if (pts.length < 2) return '<p class="note">Insufficient data.</p>';
    var W = 560, H = 340, P = 46;
    var minX = Math.min.apply(null, pts.map(function (p) { return p.lat; }));
    var maxX = Math.max.apply(null, pts.map(function (p) { return p.lat; }));
    var minY = Math.min.apply(null, pts.map(function (p) { return p.acc; }));
    var maxY = Math.max.apply(null, pts.map(function (p) { return p.acc; }));
    var padX = (maxX - minX) * 0.15 || 50, padY = (maxY - minY) * 0.15 || 0.02;
    minX -= padX; maxX += padX; minY -= padY; maxY += padY;
    function sx(v) { return P + (v - minX) / (maxX - minX) * (W - P - 16); }
    function sy(v) { return (H - P) - (v - minY) / (maxY - minY) * (H - P - 20); }
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;max-width:' + W + 'px;height:auto">';
    svg += '<line x1="' + P + '" y1="' + (H - P) + '" x2="' + (W - 16) + '" y2="' + (H - P) + '" stroke="#2a323d"/>';
    svg += '<line x1="' + P + '" y1="20" x2="' + P + '" y2="' + (H - P) + '" stroke="#2a323d"/>';
    pts.forEach(function (p, i) {
      svg += '<circle cx="' + sx(p.lat).toFixed(1) + '" cy="' + sy(p.acc).toFixed(1) +
        '" r="6" fill="' + PALETTE[i % PALETTE.length] + '" opacity="0.85"><title>' +
        esc(p.model) + ': ' + (p.acc * 100).toFixed(1) + '%, ' + Math.round(p.lat) + ' ms</title></circle>';
    });
    svg += '<text x="' + (W / 2) + '" y="' + (H - 8) + '" fill="#8b98a5" font-size="11" text-anchor="middle">Average Latency, ms</text>';
    svg += '</svg>';
    return svg + '<p class="note">Each point represents a model. Top-left is optimal: higher accuracy and lower latency. ' +
      'Cloud latency includes network transport and provider queueing.</p>';
  }

  /* ---------------------------------------------------------------- render */

  function catKey(obs) {
    var present = {};
    obs.forEach(function (o) { present[o.cat] = 1; });
    var rows = Object.keys(present).sort().map(function (c) {
      return '<tr><td><b>' + esc(catName(c)) + '</b></td><td class="mono">' + esc(c) + '</td>' +
        '<td style="white-space:normal">' + esc(CAT_HINT[c] || '—') + '</td></tr>';
    }).join('');
    return '<div class="table-scroll"><table><tr><th>Category</th><th>Code</th><th>Capability Evaluated</th></tr>' +
      rows + '</table></div>';
  }

  function modelTable(agg) {
    var rows = agg.models.map(function (m) {
      var skipNote = m.skipped ? ' <span class="sub">+' + m.skipped + ' skip</span>' : '';
      return '<tr><td class="mono">' + esc(m.model) + '</td>' +
        '<td class="num">' + m.scored + skipNote + '</td>' +
        '<td class="num">' + pct(m.acc) + '</td>' +
        '<td class="num">' + num(m.brier, 3) + '</td>' +
        '<td class="num">' + num(m.ece, 3) + '</td>' +
        '<td class="num">' + num(m.lat, 0) + '</td>' +
        '<td class="num">$' + num(m.cost, 4) + '</td></tr>';
    }).join('');
    return '<div class="table-scroll"><table><tr><th>Model</th><th class="num">Responses</th>' +
      '<th class="num">Accuracy</th><th class="num">Brier</th><th class="num">ECE</th>' +
      '<th class="num">Latency, ms</th><th class="num">Cost</th></tr>' + rows + '</table></div>';
  }

  function visionModelsTable(vis, filter) {
    filter = filter || (typeof state !== 'undefined' && state.vmodelsFilter) || 'all';
    var agg = aggregate(vis);
    var list = [];

    if (filter === 'all' || filter === 'cloud') {
      agg.models.forEach(function (m) {
        var skipNote = m.skipped ? ' <span class="sub">+' + m.skipped + ' skip</span>' : '';
        list.push({
          model: m.model,
          displayName: shortModel(m.model),
          isLocal: false,
          type: 'Cloud',
          n: m.scored,
          skipNote: skipNote,
          acc: m.acc,
          brier: m.brier,
          ece: m.ece,
          lat: m.lat,
          cost: '$' + num(m.cost, 4)
        });
      });
    }

    if (typeof DATA !== 'undefined' && DATA && DATA.local && (filter === 'all' || filter === 'local')) {
      DATA.local.forEach(function (loc) {
        if (loc.vision === undefined) return;
        var skipNote = loc.vision_skipped ? ' <span class="sub">+' + loc.vision_skipped + ' skip</span>' : '';
        list.push({
          model: loc.model,
          displayName: displayModel(loc.model, true),
          isLocal: true,
          type: 'Local',
          n: loc.vision_n || 19,
          skipNote: skipNote,
          acc: loc.vision,
          brier: loc.vision_brier,
          ece: null,
          lat: loc.vision_p50,
          cost: loc.vram_mib ? loc.vram_mib + ' MiB' : '—'
        });
      });
    }

    list.sort(function (a, b) { return (b.acc || 0) - (a.acc || 0); });

    var rows = list.map(function (m, idx) {
      var badgeCls = m.isLocal ? 'style="border-color:#388bfd;color:#79c0ff"' : 'style="color:#8b98a5"';
      var highlight = idx < 3 ? ' style="font-weight:600"' : '';
      return '<tr>' +
        '<td class="mono"' + highlight + ' title="' + esc(m.model) + '">' + esc(m.displayName) + '</td>' +
        '<td><span class="pill neutral" ' + badgeCls + '>' + esc(m.type) + '</span></td>' +
        '<td class="num">' + m.n + m.skipNote + '</td>' +
        '<td class="num"' + highlight + '>' + pct(m.acc) + '</td>' +
        '<td class="num">' + num(m.brier, 3) + '</td>' +
        '<td class="num">' + num(m.ece, 3) + '</td>' +
        '<td class="num">' + (m.lat ? num(m.lat, 0) + ' ms' : '—') + '</td>' +
        '<td class="num mono">' + esc(m.cost) + '</td>' +
        '</tr>';
    }).join('');

    return '<div class="table-scroll"><table><thead><tr>' +
      '<th>Model</th><th>Environment</th><th class="num">Responses</th><th class="num">Accuracy</th>' +
      '<th class="num">Brier</th><th class="num">ECE</th><th class="num">Latency, ms</th>' +
      '<th class="num">Resource / Cost</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>';
  }

  function visionLadderTable(vis) {
    var agg = aggregate(vis);
    var cloudByLvl = {};
    agg.levels.forEach(function (l) { cloudByLvl[l.level] = l.acc; });

    var localVisionModels = (typeof DATA !== 'undefined' && DATA && DATA.local)
      ? DATA.local.filter(function (r) { return r.vision !== undefined && r.vision_by_level; })
      : [];

    var lvlNotes = {
      1: 'Single salient object (color, count, shape, position)',
      2: 'Text on image, size comparison, symbols, stamps & status',
      3: 'Layout, receipt arithmetic, aggregation, value ratios',
      4: 'Structured table, grid reasoning, bounding box coordinates',
      5: 'Dense code debugging, OCR under challenging conditions'
    };

    var rows = [1, 2, 3, 4, 5].map(function (lvl) {
      var cAcc = cloudByLvl[lvl] !== undefined ? cloudByLvl[lvl] : null;
      var locSum = 0, locCnt = 0;
      localVisionModels.forEach(function (loc) {
        if (loc.vision_by_level && loc.vision_by_level[String(lvl)] !== undefined) {
          locSum += loc.vision_by_level[String(lvl)];
          locCnt += 1;
        }
      });
      var lAcc = locCnt ? locSum / locCnt : null;
      var diff = (cAcc !== null && lAcc !== null) ? (lAcc - cAcc) : null;
      var diffStr = diff !== null ? (diff > 0 ? '+' : '') + (diff * 100).toFixed(1) + ' pp' : '—';
      var diffCls = diff === null ? '' : (diff >= 0 ? 'color:#56d364' : 'color:#ff7b72');

      return '<tr>' +
        '<td><b>L' + lvl + '</b></td>' +
        '<td style="white-space:normal;color:#8b98a5">' + esc(lvlNotes[lvl] || '') + '</td>' +
        '<td class="num">' + pct(cAcc) + '</td>' +
        '<td class="num" style="color:#79c0ff">' + pct(lAcc) + '</td>' +
        '<td class="num mono" style="' + diffCls + '">' + diffStr + '</td>' +
        '</tr>';
    }).join('');

    return '<div class="table-scroll"><table><thead><tr>' +
      '<th>Level</th><th>Capability Evaluated</th><th class="num">Cloud (6)</th>' +
      '<th class="num">Local (6)</th><th class="num">Δ (Loc − Cloud)</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  }

  function renderOverview(obs) {
    var agg = aggregate(obs);
    var best = agg.models[0];
    var textN = obs.filter(function (o) { return o.test === 'text'; }).length;
    var visN = obs.length - textN;
    el('kpis').innerHTML =
      kpi('Observations', agg.total, textN + ' text · ' + visN + ' vision') +
      kpi('Models Evaluated', agg.models.length, DATA.meta.sources.text + ' / ' + DATA.meta.sources.vision) +
      kpi('Overall Accuracy', pct(agg.acc), 'across ' + agg.scored + ' scored responses') +
      kpi('Cumulative Cost', '$' + num(agg.cost, 4), 'entire filtered slice');

    el('chart-acc').innerHTML = barChart(
      agg.models.map(function (m) { return { label: m.model, value: m.acc || 0 }; }),
      function (v) { return pct(v); });

    el('chart-test').innerHTML = barChart(
      Object.keys(agg.byTest).map(function (k) {
        var t = agg.byTest[k];
        return { label: k === 'text' ? 'Text Tasks' : 'Vision Tasks', value: t.ok / t.n };
      }), function (v) { return pct(v); });

    el('table-models').innerHTML = modelTable(agg);
    el('overview-sub').textContent = 'Top Model: ' + (best ? best.model + ' — ' + pct(best.acc) : '—');
  }

  function renderText(obs) {
    var textObs = obs.filter(function (o) { return o.test === 'text'; });
    el('text-models-table').innerHTML = textModelsTable(textObs);

    var hfBox = el('heat-filter');
    if (hfBox) {
      hfBox.innerHTML = '';
      [['all', 'All (15)'], ['cloud', 'Cloud (5)'], ['local', 'Local (10)']].forEach(function (pair) {
        chip(hfBox, pair[1], (state.heatFilter || 'all') === pair[0], function (btn) {
          state.heatFilter = pair[0];
          el('heat').innerHTML = heatmap(textObs, pair[0]);
          Array.prototype.forEach.call(hfBox.children, function (c) { c.classList.remove('on'); });
          btn.classList.add('on');
        });
      });
    }

    el('heat').innerHTML = heatmap(textObs, state.heatFilter || 'all');
    el('catkey').innerHTML = catKey(textObs);
    el('calib').innerHTML = calibration(textObs);
    el('scatter').innerHTML = scatter(textObs);

    var cmp = (DATA.text_summary && DATA.text_summary.comparisons) || {};
    var keys = Object.keys(cmp).sort(function (a, b) { return Math.abs(cmp[b].diff) - Math.abs(cmp[a].diff); });
    if (!keys.length) { el('cmp').innerHTML = '<p class="note">No comparison data available.</p>'; return; }
    var rows = keys.map(function (k) {
      var r = cmp[k];
      return '<tr><td class="mono">' + esc(k) + '</td><td class="num">' + (r.diff > 0 ? '+' : '') +
        (r.diff * 100).toFixed(1) + ' pp</td><td class="num">' + (r.lo * 100).toFixed(1) + ' … ' +
        (r.hi * 100).toFixed(1) + '</td><td class="num">' + r.p.toFixed(3) + '</td></tr>';
    }).join('');
    el('cmp').innerHTML = '<p class="note">Paired bootstrap over 107 tasks, 2,000 resamples. ' +
      'Evaluated across the entire corpus independently of active filters above.</p>' +
      '<div class="table-scroll"><table><tr><th>Pair (B − A)</th><th class="num">Δ Accuracy</th>' +
      '<th class="num">95% CI</th><th class="num">p-value</th></tr>' + rows + '</table></div>';

    var bias = [];
    Object.keys(DATA.text_summary.models).forEach(function (m) {
      var e = DATA.text_summary.models[m];
      if (e.score_bias === undefined) return;
      bias.push('<tr><td class="mono">' + esc(m) + '</td><td class="num">' + e.score_mae.toFixed(2) +
        '</td><td class="num">' + e.score_nmae.toFixed(3) + '</td><td class="num">' +
        (e.score_bias > 0 ? '+' : '') + e.score_bias.toFixed(2) + '</td></tr>');
    });
    el('bias').innerHTML = '<div class="table-scroll"><table><tr><th>Model</th>' +
      '<th class="num">MAE</th><th class="num">nMAE</th><th class="num">Bias toward Center</th></tr>' +
      bias.join('') + '</table></div>';
  }

  function renderVision(obs) {
    var vis = obs.filter(function (o) { return o.test === 'vision'; });
    el('vlvl').innerHTML = visionLadderTable(vis);

    var vfBox = el('vmodels-filter');
    if (vfBox) {
      vfBox.innerHTML = '';
      [['all', 'All (12)'], ['cloud', 'Cloud (6)'], ['local', 'Local (6)']].forEach(function (pair) {
        chip(vfBox, pair[1], (state.vmodelsFilter || 'all') === pair[0], function (btn) {
          state.vmodelsFilter = pair[0];
          el('vmodels').innerHTML = visionModelsTable(vis, pair[0]);
          Array.prototype.forEach.call(vfBox.children, function (c) { c.classList.remove('on'); });
          btn.classList.add('on');
        });
      });
    }

    el('vmodels').innerHTML = visionModelsTable(vis, state.vmodelsFilter || 'all');
    renderVisionCards(vis);

    var localVisionModels = (typeof DATA !== 'undefined' && DATA && DATA.local)
      ? DATA.local.filter(function (r) { return r.vision !== undefined && r.vision_per_task; })
      : [];

    var solved = {};
    vis.forEach(function (o) {
      if (o.ok === null) return;
      var s = solved[o.task] || (solved[o.task] = {
        task: o.task, cat: o.cat, level: o.level,
        cloud_n: 0, cloud_ok: 0, loc_n: 0, loc_ok: 0
      });
      s.cloud_n += 1; s.cloud_ok += o.ok;
    });

    localVisionModels.forEach(function (loc) {
      if (!loc.vision_per_task) return;
      Object.keys(loc.vision_per_task).forEach(function (tid) {
        var s = solved[tid];
        if (!s) return;
        s.loc_n += 1;
        s.loc_ok += loc.vision_per_task[tid] === 1 ? 1 : 0;
      });
    });

    var rows = Object.keys(solved).map(function (k) { return solved[k]; })
      .map(function (s) {
        s.total_ok = s.cloud_ok + s.loc_ok;
        s.total_n = s.cloud_n + s.loc_n;
        s.rate = s.total_n ? s.total_ok / s.total_n : 0;
        return s;
      })
      .sort(function (a, b) { return a.rate - b.rate || a.task.localeCompare(b.task); })
      .map(function (s) {
        return '<tr>' +
          '<td class="mono">' + esc(s.task) + '</td>' +
          '<td>L' + s.level + '</td>' +
          '<td title="' + esc(s.cat) + '">' + esc(catName(s.cat)) + '</td>' +
          '<td class="num"><b>' + s.total_ok + '/' + s.total_n + '</b> (' + Math.round(s.rate * 100) + '%)</td>' +
          '<td class="num" style="color:#8b98a5">' + s.cloud_ok + '/' + s.cloud_n + '</td>' +
          '<td class="num" style="color:#79c0ff">' + s.loc_ok + '/' + s.loc_n + '</td>' +
          '</tr>';
      }).join('');
    el('vdiff').innerHTML = '<p class="note">Sorted by aggregate difficulty (cloud + local): hardest tasks where most models failed appear first.</p>' +
      '<div class="table-scroll"><table><thead><tr>' +
      '<th>Task ID</th><th>Level</th><th>Category</th><th class="num">Solved (Total)</th>' +
      '<th class="num">Cloud (6)</th><th class="num">Local (6)</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>';

    var vs = DATA.vision_summary || { models: {} };
    var box = Object.keys(vs.models).filter(function (m) { return vs.models[m].box_iou !== undefined; });
    el('box').innerHTML = box.length
      ? box.map(function (m) {
        var v = vs.models[m].box_iou;
        return '<p class="note"><b>' + esc(m) + '</b> — IoU ' + v.toFixed(3) +
          (v >= 0.5 ? ' (threshold met)' : ' (below 0.5 threshold)') + '</p>';
      }).join('')
      : '<p class="note">Box coordinate queries were only sent to Jev; unsupported by other models.</p>';
  }

  function renderVisionCards(vis) {
    var byTask = {};
    vis.forEach(function (o) { (byTask[o.task] = byTask[o.task] || []).push(o); });
    var cards = (DATA.vision_tasks || []).filter(function (t) { return byTask[t.id]; });
    if (!cards.length) {
      el('vtasks').innerHTML = '<p class="note">No tasks match active filters.</p>';
      return;
    }
    var localVisionModels = (typeof DATA !== 'undefined' && DATA && DATA.local)
      ? DATA.local.filter(function (r) { return r.vision !== undefined && r.vision_per_task; })
      : [];

    el('vtasks').innerHTML = cards.map(function (t) {
      var cloudRows = (byTask[t.id] || []).map(function (o) {
        var cls = o.skip ? 'skip' : (o.ok ? 'ok' : 'fail');
        var mark = o.skip ? '—' : (o.ok ? '✓' : '✗');
        var wrong = '';
        if (!o.ok && !o.skip && o.pred !== null && o.pred !== undefined) {
          if (t.criteria && t.criteria[o.pred]) wrong = t.criteria[o.pred];
          else if (typeof o.pred === 'number') wrong = 'IoU ' + o.pred.toFixed(2);
          else wrong = String(o.pred);
        }
        return {
          model: o.model,
          displayName: shortModel(o.model),
          isLocal: false,
          ok: o.ok,
          skip: o.skip,
          cls: cls,
          mark: mark,
          conf: o.conf,
          wrong: wrong
        };
      });

      var localRows = localVisionModels.map(function (loc) {
        var isBoxOnly = Boolean(t.box_only || t.id === 'V4-14');
        var isSkipped = isBoxOnly || loc.vision_per_task[t.id] === undefined;
        var isOk = !isSkipped && loc.vision_per_task[t.id] === 1;
        var cls = isSkipped ? 'skip' : (isOk ? 'ok' : 'fail');
        var mark = isSkipped ? '—' : (isOk ? '✓' : '✗');
        var wrong = (!isOk && !isSkipped) ? 'error' : '';
        return {
          model: loc.model + ' (local)',
          displayName: displayModel(loc.model, true),
          isLocal: true,
          ok: isSkipped ? null : (isOk ? 1 : 0),
          skip: isSkipped,
          cls: cls,
          mark: mark,
          conf: null,
          wrong: wrong
        };
      });

      var allRows = cloudRows.concat(localRows).sort(function (a, b) {
        return (b.ok || 0) - (a.ok || 0) || (b.conf || 0) - (a.conf || 0);
      });

      var rowsHtml = allRows.map(function (o) {
        var nameColor = o.isLocal ? ' style="color:#79c0ff"' : '';
        return '<div class="vrow">' +
          '<span class="vm mono"' + nameColor + ' title="' + esc(o.model) + '">' + esc(o.displayName) + '</span>' +
          '<span class="pill ' + o.cls + '">' + o.mark + '</span>' +
          '<span class="vc" title="confidence">' + (o.conf !== null && o.conf !== undefined ? o.conf.toFixed(2) : '—') + '</span>' +
          '<span class="vp" title="model prediction">' + esc(o.wrong) + '</span></div>';
      }).join('');

      return '<div class="vtask">' +
        '<div class="vhead"><span class="pill neutral">L' + t.level + '</span>' +
        '<b class="mono">' + esc(t.id) + '</b>' +
        '<span class="sub">' + esc(catName(t.family)) + '</span></div>' +
        (t.image ? '<img loading="lazy" src="' + t.image + '" alt="' + esc(t.id) + '">' : '') +
        '<div class="vq">' + esc(t.instructions) + '</div>' +
        '<div class="vgold">Ground Truth: <b>' + esc(t.gold_label) + '</b></div>' +
        '<div class="vres">' + rowsHtml + '</div></div>';
    }).join('');
  }

  function renderExplore(obs) {
    var rows = obs.slice(0, 400).map(function (o) {
      var cls = o.ok === null ? 'skip' : (o.ok ? 'ok' : 'fail');
      var label = o.ok === null ? 'skip' : (o.ok ? 'pass' : 'fail');
      return '<tr><td class="mono">' + esc(o.task) + '</td><td>' + (o.test === 'text' ? 'text' : 'vision') +
        '</td><td class="mono">' + esc(o.model) + '</td><td title="' + esc(o.cat) + '">' + esc(catName(o.cat)) +
        '</td>' +
        '<td class="num">' + (o.level || '—') + '</td><td>' + esc(o.lang) + '</td><td>' + esc(o.diff) + '</td>' +
        '<td><span class="pill ' + cls + '">' + label + '</span></td>' +
        '<td class="num">' + num(o.p, 3) + '</td><td class="num">' + num(o.conf, 3) + '</td>' +
        '<td class="num">' + num(o.lat, 0) + '</td></tr>';
    }).join('');
    el('explore-count').textContent = 'Showing ' + Math.min(400, obs.length) + ' of ' + obs.length;
    el('explore-table').innerHTML = '<div class="table-scroll"><table><tr><th>Task ID</th><th>Test</th>' +
      '<th>Model</th><th>Category</th><th class="num">Lvl</th><th>Lang</th><th>Diff</th>' +
      '<th>Result</th><th class="num">p(gold)</th><th class="num">Confidence</th><th class="num">ms</th></tr>' +
      rows + '</table></div>';
  }

  function renderMethods() {
    var v = DATA.verify || [];
    el('verify').innerHTML = v.length
      ? '<div class="table-scroll"><table><tr><th>Verification Check</th><th>Result</th><th>Details</th></tr>' +
        v.map(function (c) {
          return '<tr><td>' + esc(c.name) + '</td><td><span class="pill ' +
            (c.ok ? 'ok' : 'fail') + '">' + (c.ok ? 'passed' : 'failed') + '</span></td>' +
            '<td class="mono" style="white-space:normal">' + esc(c.detail || '') + '</td></tr>';
        }).join('') + '</table></div>'
      : '<p class="note">No verification results found — run python -m src.verify.</p>';
    el('meta').innerHTML =
      '<p class="note">Data snapshot as of ' + esc(DATA.meta.built_at) +
      ' · text: <span class="mono">' + esc(DATA.meta.sources.text) + '</span>' +
      ' · vision: <span class="mono">' + esc(DATA.meta.sources.vision) + '</span>' +
      ' · sha256(raw) ' + esc(DATA.meta.source_sha256.text_raw) + ' / ' +
      esc(DATA.meta.source_sha256.vision_raw) + '</p>';

    var cat = DATA.catalog || [];
    var img = cat.filter(function (m) { return (m.modalities || []).indexOf('image') >= 0; });
    var audio = cat.filter(function (m) { return (m.modalities || []).indexOf('audio') >= 0; });
    var video = cat.filter(function (m) { return (m.modalities || []).indexOf('video') >= 0; });
    el('catalog').innerHTML = '<p class="note">Catalog contains ' + cat.length + ' decision models; ' +
      img.length + ' accept images, ' + audio.length + ' accept audio, ' + video.length + ' accept video.</p>' +
      '<div class="table-scroll"><table><tr><th>Model</th><th>Modalities</th><th class="num">Input $/1M</th>' +
      '<th class="num">Context</th></tr>' + cat.map(function (m) {
        return '<tr><td class="mono">' + esc(m.slug) + '</td><td>' + esc((m.modalities || []).join(' + ')) +
          '</td><td class="num">' + (m.price_in ? '$' + (m.price_in * 1e6).toFixed(3) : 'free') +
          '</td><td class="num">' + m.ctx + '</td></tr>';
      }).join('') + '</table></div>';
  }

  function renderLocal() {
    var loc = DATA.local || [];
    if (!loc.length) {
      el('local-table').innerHTML = '<p class="note">No local benchmark runs found.</p>';
      return;
    }
    var rows = loc.map(function (r) {
      return '<tr><td class="mono">' + esc(r.model) + '</td>' +
        '<td class="num">' + (r.text !== undefined ? pct(r.text) : '—') + '</td>' +
        '<td class="num">' + (r.text_p50 ? r.text_p50 + ' ms' : '—') + '</td>' +
        '<td class="num">' + (r.vision !== undefined ? pct(r.vision) : '—') + '</td>' +
        '<td class="num">' + (r.vision_p50 ? r.vision_p50 + ' ms' : '—') + '</td>' +
        '<td class="num">' + (r.ctx || '—') + '</td>' +
        '<td class="num">' + (r.vram_mib ? r.vram_mib + ' MiB' : '—') + '</td>' +
        '<td style="white-space:normal;color:#8b98a5">' + esc(r.note || '') + '</td></tr>';
    }).join('');
    el('local-table').innerHTML = '<div class="table-scroll"><table><tr><th>Model</th>' +
      '<th class="num">Text Acc</th><th class="num">Text Latency</th><th class="num">Vision Acc</th>' +
      '<th class="num">Vision Latency</th><th class="num">Context</th><th class="num">VRAM</th>' +
      '<th>Deployment Notes</th></tr>' + rows + '</table></div>';

    el('local-chart').innerHTML = barChart(
      loc.filter(function (r) { return r.text !== undefined; })
        .map(function (r) { return { label: r.model, value: r.text }; }),
      function (v) { return pct(v); });

    el('local-vchart').innerHTML = barChart(
      loc.filter(function (r) { return r.vision !== undefined; })
        .map(function (r) { return { label: r.model, value: r.vision }; }),
      function (v) { return pct(v); });

    // cloud reference points, same corpora
    var cloudText = (DATA.text_summary && DATA.text_summary.models) || {};
    var cloudRows = Object.keys(cloudText).map(function (m) {
      var e = cloudText[m];
      return '<tr><td class="mono">' + esc(m) + '</td><td class="num">' +
        pct(e.accuracy) + '</td><td class="num">' +
        (e.latency && e.latency.p50 ? Math.round(e.latency.p50) + ' ms' : '—') + '</td></tr>';
    }).join('');
    var cloudVision = (DATA.vision_summary && DATA.vision_summary.models) || {};
    var cloudVRows = Object.keys(cloudVision).filter(function (m) {
      return cloudVision[m].accuracy !== undefined;
    }).map(function (m) {
      var e = cloudVision[m];
      return '<tr><td class="mono">' + esc(m) + '</td><td class="num">' +
        pct(e.accuracy) + '</td><td class="num">' +
        (e.latency && e.latency.p50 ? Math.round(e.latency.p50) + ' ms' : '—') + '</td></tr>';
    }).join('');
    el('local-cloud').innerHTML =
      '<div class="two-col"><div><h3>Cloud, Text</h3><div class="table-scroll"><table>' +
      '<tr><th>Model</th><th class="num">Accuracy</th><th class="num">p50 Latency</th></tr>' + cloudRows +
      '</table></div></div><div><h3>Cloud, Vision</h3><div class="table-scroll"><table>' +
      '<tr><th>Model</th><th class="num">Accuracy</th><th class="num">p50 Latency</th></tr>' + cloudVRows +
      '</table></div></div></div>';
  }

  function render() {
    var obs = apply(DATA.observations, state);
    el('f-summary').textContent = obs.length + ' observations in selection';
    renderOverview(obs);
    renderText(obs);
    renderVision(obs);
    renderExplore(obs);
    renderLocal();
    renderMethods();
    var hash = toHash(state, view);
    if (location.hash !== hash) {
      try { history.replaceState(null, '', hash); }
      catch (e) { location.hash = hash; }
    }
  }

  /* ----------------------------------------------------------------- controls */

  function chip(container, label, on, onClick, title) {
    var b = document.createElement('button');
    b.className = 'chip' + (on ? ' on' : '');
    b.textContent = label;
    if (title) b.title = title;
    b.onclick = function () { onClick(b); };
    container.appendChild(b);
  }

  function buildControls() {
    var models = {};
    var cats = {};
    var langs = {};
    var diffs = {};
    DATA.observations.forEach(function (o) {
      models[o.model] = 1; cats[o.cat] = 1; langs[o.lang] = 1; diffs[o.diff] = 1;
    });

    var testBox = el('f-test');
    ['all', 'text', 'vision'].forEach(function (t) {
      chip(testBox, t, state.test === t, function () {
        state.test = t; rebuild(); render();
      });
    });

    var modelBox = el('f-models');
    Object.keys(models).sort().forEach(function (m) {
      chip(modelBox, m.replace(':free', ' · free'), state.models.indexOf(m) >= 0, function () {
        toggle(state.models, m); rebuild(); render();
      });
    });

    var catBox = el('f-cats');
    Object.keys(cats).sort().forEach(function (c) {
      chip(catBox, catName(c), state.cats.indexOf(c) >= 0, function () {
        toggle(state.cats, c); rebuild(); render();
      }, c);
    });

    var outBox = el('f-out');
    [['all', 'all'], ['ok', 'correct'], ['fail', 'incorrect'], ['skip', 'skipped']].forEach(function (pair) {
      chip(outBox, pair[1], state.out === pair[0], function () {
        state.out = pair[0]; rebuild(); render();
      });
    });
    el('f-q').value = state.q || '';
    el('f-q').oninput = function (e) { state.q = e.target.value; render(); };

    el('f-reset').onclick = function () {
      state = emptyFilters(); el('f-q').value = ''; rebuild(); render();
    };

    document.querySelectorAll('nav.tabs button').forEach(function (b) {
      b.onclick = function () {
        view = b.getAttribute('data-view');
        document.querySelectorAll('nav.tabs button').forEach(function (x) { x.classList.remove('active'); });
        document.querySelectorAll('section.view').forEach(function (x) { x.classList.remove('active'); });
        b.classList.add('active');
        el('v-' + view).classList.add('active');
        window.scrollTo(0, 0);
        render();
      };
    });
  }

  function toggle(arr, v) {
    var i = arr.indexOf(v);
    if (i >= 0) arr.splice(i, 1); else arr.push(v);
  }

  function rebuild() {
    ['f-test', 'f-models', 'f-cats', 'f-out'].forEach(function (id) {
      var c = el(id);
      if (c) c.innerHTML = '';
    });
    buildControls();
  }

  function init() {
    var raw = el('payload').textContent;
    DATA = JSON.parse(raw);
    var parsed = parseHash(location.hash);
    state = parsed.filters;
    view = parsed.view || 'overview';
    document.querySelectorAll('nav.tabs button').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-view') === view);
    });
    document.querySelectorAll('section.view').forEach(function (x) { x.classList.remove('active'); });
    el('v-' + view).classList.add('active');
    buildControls();
    render();
    window.addEventListener('hashchange', function () {
      var p = parseHash(location.hash);
      state = p.filters; view = p.view;
      rebuild(); render();
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})(typeof globalThis !== 'undefined' ? globalThis : this);
