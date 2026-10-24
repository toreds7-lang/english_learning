// ===== engine: markup → colour blocks, morph (FLIP), attention arcs, Korean mirror =====
const Q_ = location.search + location.hash;
const SELFTEST = /selftest/.test(Q_);
const NOANIM = SELFTEST || /noanim/.test(Q_);
if (NOANIM) document.documentElement.classList.add('noanim');
const WARN = []; let CTX = '';
function warn(m) { const s = (CTX ? CTX + ': ' : '') + m; if (!WARN.includes(s)) WARN.push(s); if (!SELFTEST) console.warn(s); }

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
function h(tag, cls, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
function svgEl(cls) { const e = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); e.setAttribute('class', cls); return e; }
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const md = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\*(.+?)\*/g, '<i>$1</i>')
  .replace(/✗/g, '<span class="no">✗</span>').replace(/✓/g, '<span class="yes">✓</span>');

let SCALE = 1, timers = [];
function later(fn, ms) { const t = setTimeout(fn, ms); timers.push(t); return t; }
function clearTimers() { timers.forEach(clearTimeout); timers = []; }

// ---------------------------------------------------------------- markup
const ROLES = 'SVHNOCMQKGX';
const LAB = {S: '주어 S', V: '동사 V', H: '조동사 Aux', N: '부정 not', O: '목적어 O', C: '보어 C', M: '수식어 M', Q: '의문사 Wh', K: '연결어', G: '생략 가능', X: ''};
const LAB_IN = {s: '주어', v: '동사', h: '조동사', n: '부정', o: '목적어', c: '보어', m: '수식', q: '의문사', k: '연결', g: '생략', x: ''};
const PCACHE = new Map();
function parse(s) {
  if (PCACHE.has(s)) return JSON.parse(PCACHE.get(s));
  let i = 0;
  const seq = end => {
    const out = []; let buf = '';
    while (i < s.length) {
      const ch = s[i];
      if (end && ch === end) { if (buf) out.push({t: 'txt', v: buf}); i++; return out; }
      if (ch === '[') {
        if (buf) { out.push({t: 'txt', v: buf}); buf = ''; }
        const m = /^([A-Za-z])((?:#[A-Za-z0-9]+|\{[^}]*\})*) ?/.exec(s.slice(i + 1));
        if (!m) throw new Error('bad block: ' + s);
        i += 1 + m[0].length;
        const n = {t: 'blk', role: m[1], id: null, lab: null};
        (m[2].match(/#[A-Za-z0-9]+|\{[^}]*\}/g) || []).forEach(o => { if (o[0] === '#') n.id = o.slice(1); else n.lab = o.slice(1, -1); });
        if (!ROLES.includes(n.role.toUpperCase())) throw new Error('unknown role ' + n.role + ': ' + s);
        n.kids = seq(']');
        out.push(n); continue;
      }
      if (ch === ']') throw new Error('stray ]: ' + s);
      buf += ch; i++;
    }
    if (end) throw new Error('missing ' + end + ': ' + s);
    if (buf) out.push({t: 'txt', v: buf});
    return out;
  };
  const r = seq(null);
  PCACHE.set(s, JSON.stringify(r));
  return r;
}
function textOf(ns) { return ns.map(n => n.t === 'txt' ? n.v : (n.role.toUpperCase() === 'G' ? '' : textOf(n.kids))).join(''); }
function plain(ns) { return textOf(ns).replace(/\s+/g, ' ').replace(/\s+([,.?!])/g, '$1').trim(); }
function ownText(n) { return n.kids.filter(k => k.t === 'txt').map(k => k.v).join('').replace(/\s+/g, ' ').trim(); }
function findBlk(ns, id) { for (const n of ns) { if (n.t !== 'blk') continue; if (n.id === id) return n; const r = findBlk(n.kids, id); if (r) return r; } return null; }
function setText(ns, id, text) { const b = findBlk(ns, id); if (!b) { warn('setText: no block ' + id); return; } b.kids = [{t: 'txt', v: text}]; }
function parseKm(s) { return s.split(';').map(x => x.trim()).filter(Boolean).map(x => { const j = x.lastIndexOf('|'); return [x.slice(0, j).trim(), x.slice(j + 1).trim().split(/\s+/)]; }); }
function parseArcs(s) {
  return s.split(';').map(x => x.trim()).filter(Boolean).map(x => {
    const m = /^(\w+)-(\w+)\s+(\d)\s*(.*)$/.exec(x); if (!m) { warn('bad arc ' + x); return null; }
    return [m[1], m[2], +m[3], m[4].trim()];
  }).filter(Boolean);
}
function topKeyed(ns) { return ns.filter(n => n.t === 'blk' && n.id).map(n => ({k: n.id, R: n.role.toUpperCase()})); }
function autoSeat(ns) { const t = topKeyed(ns); const x = t.find(b => b.R === 'H') || t.find(b => b.R === 'V'); return x ? x.k : null; }
function autoArcs(ns) {
  const t = topKeyed(ns), f = p => t.findIndex(p), out = [];
  const iS = f(b => b.k === 's'), iH = f(b => b.R === 'H'), iV = f(b => b.R === 'V'), iQ = f(b => b.R === 'Q' && b.k !== 's'), iO = f(b => b.R === 'O' || b.R === 'C');
  if (iH >= 0 && iS >= 0) out.push([t[iH].k, t[iS].k, 3, iH < iS ? '점프: 질문' : '일치']);
  else if (iS >= 0 && iV >= 0) out.push([t[iS].k, t[iV].k, 3, '일치']);
  if (iH >= 0 && iV >= 0) out.push([t[iH].k, t[iV].k, 2, '']);
  if (iQ >= 0 && iV >= 0) out.push([t[iQ].k, t[iV].k, 2, '빈자리에서 옴']);
  if (iV >= 0 && iO >= 0) out.push([t[iV].k, t[iO].k, 2, '']);
  return out;
}

// ---------------------------------------------------------------- render
function renderNodes(ns, opt) {
  const frag = document.createDocumentFragment();
  ns.forEach(n => {
    if (n.t === 'txt') { frag.appendChild(document.createTextNode(n.v)); return; }
    const R = n.role.toUpperCase(), inner = n.role !== R;
    const b = h('span', 'b r-' + R + (inner ? ' in' : '') + (R === 'X' ? ' x' : '') + (R === 'G' ? ' gap' : ''));
    b.dataset.r = R; if (n.id) b.dataset.k = n.id;
    if (opt.seat && n.id === opt.seat) b.classList.add('seat');
    const bt = h('span', 'bt');
    if (R === 'G') bt.textContent = '(' + textOfAll(n.kids) + ')'; else bt.appendChild(renderNodes(n.kids, opt));
    b.appendChild(bt);
    const lab = n.lab != null ? n.lab : (inner ? LAB_IN[n.role] : LAB[R]);
    if (lab) b.appendChild(h('span', 'bl', esc(lab)));
    frag.appendChild(b);
  });
  return frag;
}
function textOfAll(ns) { return ns.map(n => n.t === 'txt' ? n.v : textOfAll(n.kids)).join('').trim(); }
function sentEl(ns, opt = {}) { const s = h('div', 'sent'); s.appendChild(renderNodes(ns, opt)); return s; }

// ---------------------------------------------------------------- FLIP morph
function ownOf(e) { const bt = e.querySelector(':scope > .bt'); let t = ''; bt.childNodes.forEach(c => { if (c.nodeType === 3) t += c.nodeValue; }); return t.replace(/\s+/g, ' ').trim(); }
function snap(host) {
  const base = host.getBoundingClientRect(), m = {};
  host.querySelectorAll('[data-k]').forEach(e => {
    const r = e.getBoundingClientRect(), p = e.parentElement.closest('[data-k]');
    m[e.dataset.k] = {x: (r.left - base.left) / SCALE, y: (r.top - base.top) / SCALE, own: ownOf(e), r: e.dataset.r, el: e, clone: e.cloneNode(true), anc: p ? p.dataset.k : null};
  });
  return m;
}
function flip(host, A, B, fs) {
  const moved = [];
  for (const k in B) {
    const b = B[k], e = b.el, a = A[k];
    if (!a) {
      const kids = $$('[data-k]', e).some(c => A[c.dataset.k]);
      e.classList.add(kids ? 'wrap' : 'new'); continue;
    }
    let dx = a.x - b.x, dy = a.y - b.y;
    if (b.anc && A[b.anc] && B[b.anc]) { dx -= A[b.anc].x - B[b.anc].x; dy -= A[b.anc].y - B[b.anc].y; }
    if (a.own.toLowerCase() !== b.own.toLowerCase() || a.r !== b.r) {
      e.classList.add('chg');
      if (a.own && a.own.toLowerCase() !== b.own.toLowerCase()) { const t = h('span', 'oldtag', '<s>' + esc(a.own) + '</s>'); t.style.left = b.x + 'px'; t.style.top = (b.y - fs * 0.62) + 'px'; t.style.fontSize = (fs * 0.42) + 'px'; host.appendChild(t); }
    }
    if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) { e.style.transform = `translate(${dx}px,${dy}px)`; moved.push(e); }
  }
  for (const k in A) {
    if (B[k]) continue;
    const a = A[k];
    if (a.anc && A[a.anc] && !B[a.anc]) continue;
    const g = a.clone; g.classList.add('ghost'); g.style.left = a.x + 'px'; g.style.top = a.y + 'px'; g.style.fontSize = fs + 'px';
    host.appendChild(g);
  }
  void host.offsetWidth;
  moved.forEach(e => { e.classList.add('mv'); e.style.transform = ''; });
}

// ---------------------------------------------------------------- diff (for the "이전 문장" chips)
function keyed(ns) {
  const m = new Map();
  const rec = (xs, parent) => xs.forEach(n => {
    if (n.t !== 'blk') return;
    if (n.id) m.set(n.id, {parent, own: ownText(n), full: plain([n]) || ownText(n)});
    rec(n.kids, n.id || parent);
  });
  rec(ns, null); return m;
}
function hasSurvivor(k, M, other) {
  for (const [kk, v] of M) { let p = v.parent; while (p) { if (p === k && other.has(kk)) return true; p = (M.get(p) || {}).parent; } }
  return false;
}
function diff(a, b) {
  const A = keyed(a), B = keyed(b), out = [];
  B.forEach((v, k) => {
    if (A.has(k)) return;
    if (v.parent && !A.has(v.parent) && !hasSurvivor(v.parent, B, A)) return;
    const t = hasSurvivor(k, B, A) ? v.own : v.full;
    if (t) out.push({t: 'add', s: '+ ' + t});
  });
  B.forEach((v, k) => { const u = A.get(k); if (u && u.own.toLowerCase() !== v.own.toLowerCase()) out.push({t: 'chg', s: (u.own || '∅') + ' → ' + (v.own || '∅')}); });
  const groups = new Map();
  B.forEach((v, k) => { const u = A.get(k); if (!u || (u.parent || '') !== (v.parent || '')) return; const g = v.parent || ''; if (!groups.has(g)) groups.set(g, []); groups.get(g).push(k); });
  groups.forEach(keys => {
    const aOrder = [...A.keys()].filter(k => keys.includes(k));
    let cur = keys.slice();
    for (let guard = 0; guard < 10; guard++) {
      const ao = aOrder.filter(k => cur.includes(k));
      if (ao.every((k, j) => cur[j] === k)) break;
      let best = null, bd = 0;
      cur.forEach((k, j) => { const d = j - ao.indexOf(k), ad = Math.abs(d); if (ad > Math.abs(bd) || (ad && ad === Math.abs(bd) && d < 0 && bd > 0)) { best = k; bd = d; } });
      if (!best) break;
      out.push({t: 'mv', s: (bd < 0 ? '↶ ' : '↷ ') + B.get(best).full + (bd < 0 ? ' 앞으로' : ' 뒤로')});
      cur = cur.filter(k => k !== best);
    }
  });
  A.forEach((v, k) => { if (B.has(k) || (v.parent && !B.has(v.parent))) return; out.push({t: 'del', s: '− ' + v.full}); });
  return out;
}
function diffChips(a, b) { return diff(a, b).slice(0, 6).map(d => `<span class="dc ${d.t}">${esc(d.s)}</span>`).join(''); }

// ---------------------------------------------------------------- drill chips
function chipsOf(ns) {
  const out = [];
  const push = (text, R, k) => {
    if (/^[,;:]$/.test(text) && out.length) { out[out.length - 1].text += text; return; }
    if (/^[.?!]+$/.test(text)) return;
    out.push({text, R, k});
  };
  const rec = (xs, R0, k0) => xs.forEach(n => {
    if (n.t === 'txt') { n.v.trim().split(/\s+/).filter(Boolean).forEach(w => push(w, R0 || 'X', k0)); return; }
    const R = n.role.toUpperCase(); if (R === 'G') return;
    const RR = R === 'X' ? (R0 || 'X') : R;
    if (n.kids.some(c => c.t === 'blk')) rec(n.kids, RR, n.id || k0);
    else push(plain(n.kids), RR, n.id || k0);
  });
  rec(ns, null, null);
  return out;
}

// ---------------------------------------------------------------- Stage
class Stage {
  constructor(root, o = {}) {
    this.o = Object.assign({max: 46, min: 17, kmax: 20, amax: 86}, o);
    this.el = h('div', 'stage-in');
    if (o.atop != null) this.el.style.setProperty('--atop', o.atop + 'px');
    if (o.kgap != null) this.el.style.setProperty('--kgap', o.kgap + 'px');
    this.svgM = svgEl('mlines'); this.svgA = svgEl('arcs'); this.labs = h('div', 'alabs');
    this.host = h('div', 'host'); this.ko = h('div', 'korow');
    this.el.append(this.svgM, this.svgA, this.host, this.ko, this.labs);
    root.appendChild(this.el);
  }
  render(ns, seat, fs) { this.host.innerHTML = ''; const s = sentEl(ns, {seat}); s.style.fontSize = fs + 'px'; this.host.appendChild(s); return s; }
  fit(list) {
    const W = this.host.clientWidth - 10; let fs = this.o.max;
    list.filter(Boolean).forEach(ns => {
      const s = this.render(ns, null, fs); const w = s.offsetWidth;
      if (w > W) { fs = Math.max(this.o.min, Math.floor(fs * W / w)); s.style.fontSize = fs + 'px'; while (s.offsetWidth > W && fs > this.o.min) { fs--; s.style.fontSize = fs + 'px'; } }
    });
    return fs;
  }
  clear() { this.svgA.innerHTML = ''; this.svgM.innerHTML = ''; this.labs.innerHTML = ''; }
  play(spec) {
    this.spec = spec; this.clear(); this.ko.classList.remove('later');
    const {nodes, from} = spec;
    const fs = this.fs = this.fit([nodes, from]);
    const anim = !NOANIM && spec.animate !== false;
    if (!anim || !from) {
      const s = this.render(nodes, spec.seat, fs); this.renderKo(spec);
      if (anim && spec.build) {
        const bs = $$(':scope > .b', s);
        bs.forEach((b, j) => { b.classList.add('new'); b.style.animationDelay = (0.15 + j * 0.14).toFixed(2) + 's'; });
        this.ko.classList.add('later');
        later(() => { this.ko.classList.remove('later'); this.overlays(); }, 450 + bs.length * 140 + 450);
      } else this.overlays();
      return;
    }
    this.render(from, spec.fromSeat, fs); this.ko.innerHTML = '';
    later(() => {
      const A = snap(this.host); this.render(nodes, spec.seat, fs); const B = snap(this.host);
      flip(this.host, A, B, fs); this.renderKo(spec); this.ko.classList.add('later');
      later(() => { this.ko.classList.remove('later'); this.overlays(); }, 950);
    }, spec.delay != null ? spec.delay : 650);
  }
  renderKo(spec) {
    this.ko.innerHTML = '';
    if (!spec.km) { this.ko.style.display = 'none'; return; }
    this.ko.style.display = '';
    const chunks = typeof spec.km === 'string' ? parseKm(spec.km) : spec.km;
    chunks.forEach(([t, ids]) => {
      const c = h('span', 'kc' + (t.startsWith('(') ? ' dim' : ''), esc(t)); c.dataset.ids = ids.join(' ');
      const e = this.host.querySelector(`[data-k="${ids[0]}"]`);
      if (!e) warn('mirror target missing: ' + ids[0]);
      c.style.setProperty('--rc', `var(--${e ? e.dataset.r : 'X'})`);
      this.ko.appendChild(c);
    });
    let fs = this.o.kmax; this.ko.style.fontSize = fs + 'px';
    const W = this.el.clientWidth - 6, width = () => $$('.kc', this.ko).reduce((a, c) => a + c.offsetWidth, 0) + (chunks.length - 1) * fs * 0.45;
    while (width() > W && fs > 12) { fs--; this.ko.style.fontSize = fs + 'px'; }
  }
  overlays() {
    const sp = this.spec; this.clear();
    if (sp.arcs) this.drawArcs(sp.arcs === 'auto' ? autoArcs(sp.nodes) : sp.arcs);
    if (sp.km) this.drawMirror();
  }
  drawArcs(arcs) {
    if (typeof arcs === 'string') arcs = parseArcs(arcs);
    const base = this.el.getBoundingClientRect(), placed = []; let svg = '';
    const pos = k => {
      const b = this.host.querySelector(`[data-k="${k}"]`); if (!b) { warn('arc target missing: ' + k); return null; }
      const r = b.querySelector(':scope > .bt').getBoundingClientRect();
      return {x: (r.left + r.width / 2 - base.left) / SCALE, y: (r.top - base.top) / SCALE, R: b.dataset.r};
    };
    arcs.forEach(([a, b, w, lab], i) => {
      const p = pos(a), q = pos(b); if (!p || !q) return;
      const span = Math.abs(q.x - p.x), top = Math.min(p.y, q.y) - 3;
      const hh = Math.min(this.o.amax, 22 + span * 0.3), cy = top - hh, col = `var(--${p.R})`, f = v => v.toFixed(1);
      svg += `<path class="arc w${w}" pathLength="1" style="stroke:${col};animation-delay:${(i * 0.13).toFixed(2)}s" d="M${f(p.x)},${f(p.y - 3)} C${f(p.x)},${f(cy)} ${f(q.x)},${f(cy)} ${f(q.x)},${f(q.y - 3)}"/>`;
      [p, q].forEach(z => { svg += `<circle cx="${f(z.x)}" cy="${f(z.y - 3)}" r="${w > 2 ? 3.6 : 2.6}" style="fill:${col}"/>`; });
      if (lab) {
        const L = h('span', 'alab', esc(lab)); L.style.setProperty('--rc', col);
        L.style.left = ((p.x + q.x) / 2) + 'px'; L.style.top = Math.max(9, top - hh * 0.75) + 'px';
        L.style.animationDelay = (i * 0.13 + 0.3).toFixed(2) + 's';
        this.labs.appendChild(L); placed.push(L);
      }
    });
    this.svgA.innerHTML = svg;
    const boxes = [], ov = (a, b) => a.left < b.right + 3 && b.left < a.right + 3 && a.top < b.bottom + 1 && b.top < a.bottom + 1;
    placed.forEach(L => {
      let r = L.getBoundingClientRect(), n = 0;
      while (boxes.some(b => ov(b, r)) && n < 6) { const t = parseFloat(L.style.top); L.style.top = (t > 26 ? t - 17 : t + 34) + 'px'; r = L.getBoundingClientRect(); n++; }
      boxes.push(r);
    });
  }
  drawMirror() {
    const base = this.el.getBoundingClientRect(), s = this.host.querySelector('.sent'); if (!s) return;
    const sb = (s.getBoundingClientRect().bottom - base.top) / SCALE + 3, f = v => v.toFixed(1); let svg = '';
    $$('.kc', this.ko).forEach(c => {
      const cr = c.getBoundingClientRect(), x2 = (cr.left + cr.width / 2 - base.left) / SCALE, y2 = (cr.top - base.top) / SCALE - 2;
      c.dataset.ids.split(' ').forEach(k => {
        const e = this.host.querySelector(`[data-k="${k}"]`); if (!e) { warn('mirror target missing: ' + k); return; }
        const r = e.querySelector(':scope > .bt').getBoundingClientRect(), x1 = (r.left + r.width / 2 - base.left) / SCALE, my = (sb + y2) / 2;
        svg += `<path style="stroke:var(--${e.dataset.r})" d="M${f(x1)},${f(sb)} C${f(x1)},${f(my)} ${f(x2)},${f(my)} ${f(x2)},${f(y2)}"/>`;
      });
    });
    this.svgM.innerHTML = svg;
  }
}

// ---------------------------------------------------------------- active stage (R replays, 🔊 speaks)
let ACTIVE = null, SLIDEKEYS = null;
function activate(stage, spec) { ACTIVE = {stage, spec}; stage.play(spec); }
function replay() { if (ACTIVE) ACTIVE.stage.play(ACTIVE.spec); }
function say(text) {
  try {
    if (!('speechSynthesis' in window) || !text) return;
    const u = new SpeechSynthesisUtterance(text); u.lang = 'en-US'; u.rate = 0.9;
    const vs = speechSynthesis.getVoices(); const v = vs.find(x => x.lang === 'en-US' && x.localService) || vs.find(x => /^en/.test(x.lang));
    if (v) u.voice = v; speechSynthesis.cancel(); speechSynthesis.speak(u);
  } catch (e) { /* no voice */ }
}
function stageCtl(drill) {
  const c = h('div', 'stg-ctl');
  c.innerHTML = (drill != null ? `<button class="btn sm" data-drill="${drill}" title="드릴로 이 문장 만들기 (D)">🧩 직접 만들기 <kbd>D</kbd></button>` : '') + '<button class="btn sm" data-a="replay" title="변신 다시 보기 (R)">↻ 다시 보기 <kbd>R</kbd></button>' +
    ('speechSynthesis' in window ? '<button class="btn sm" data-a="say" title="듣기 (브라우저 음성)">🔊</button>' : '');
  return c;
}

// ---------------------------------------------------------------- subject switch
function swNodes(cfg, st) {
  const ns = parse(cfg.base), subj = cfg.subj[st.si], key = subj[1];
  setText(ns, cfg.sk || 's', subj[0]);
  for (const id in cfg.dv || {}) setText(ns, id, cfg.dv[id][key] != null ? cfg.dv[id][key] : cfg.dv[id]._);
  (cfg.rows || []).forEach((row, ri) => { const o = row.opts[st.ri[ri]]; for (const id in o[1]) setText(ns, id, key === 'pl' && o[1][id].pl ? o[1][id].pl : o[1][id]._); });
  return ns;
}
function swKm(cfg, st) {
  const ch = parseKm(cfg.km), sk = cfg.sk || 's', subj = cfg.subj[st.si];
  ch.forEach(c => { if (c[1][0] === sk) c[0] = subj[2]; });
  (cfg.rows || []).forEach((row, ri) => { const o = row.opts[st.ri[ri]]; ch.forEach(c => { if (o[2] && o[2][c[1][0]] != null) c[0] = o[2][c[1][0]]; }); });
  return ch;
}
function switchWidget(root, cfg, stage, spec0, si0) {
  const st = {si: si0 || 0, ri: (cfg.rows || []).map(() => 0)};
  let cur = swNodes(cfg, st);
  const wrap = h('div', 'sw'), log = h('div', 'swlog', '단어를 눌러 보세요 — 어떤 단어가 반응할까요?');
  const row = (nm, note, labels, sel, pick) => {
    const r = h('div', 'swr', `<div class="nm">${esc(nm)}</div>`), o = h('div', 'opts');
    labels.forEach((l, j) => { const b = h('button', 'opt' + (j === sel ? ' on' : ''), esc(l)); b.onclick = () => pick(j); o.appendChild(b); });
    r.appendChild(o); if (note) r.appendChild(h('div', 'nt', md(note))); return r;
  };
  const change = mut => {
    mut(); const nn = swNodes(cfg, st), d = diff(cur, nn).filter(x => x.t === 'chg');
    log.innerHTML = d.length ? '바뀐 단어: ' + d.map(x => `<b>${esc(x.s)}</b>`).join(' · ') : '바뀐 단어가 없어요';
    const sp = Object.assign({}, spec0, {nodes: nn, from: cur, fromSeat: spec0.seat, km: swKm(cfg, st), delay: 0, build: false, say: plain(nn)});
    cur = nn; draw(); activate(stage, sp);
  };
  const draw = () => {
    wrap.innerHTML = '';
    wrap.appendChild(row('주어 S 바꾸기', cfg.subjNote, cfg.subj.map(x => x[0]), st.si, j => change(() => { st.si = j; })));
    (cfg.rows || []).forEach((r, ri) => wrap.appendChild(row(r.nm, r.note, r.opts.map(o => o[0]), st.ri[ri], j => change(() => { st.ri[ri] = j; }))));
    wrap.appendChild(log);
  };
  draw(); root.appendChild(wrap);
  return {nodes: () => cur, km: () => swKm(cfg, st)};
}
