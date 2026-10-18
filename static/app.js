'use strict';

/* ======================================================================= helpers */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const view = $('#view');

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const marked = (s) => esc(s).replace(/\*([^*]+)\*/g, '<mark>$1</mark>');  // *target* -> highlighted
const plain = (s) => String(s ?? '').replace(/\*/g, '');
const pct = (n, total) => (total ? (100 * n) / total : 0);
const enc = encodeURIComponent;
const shuffle = (a) => {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};
const localDate = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const store = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem('wordstep.' + key);
      return v === null ? fallback : JSON.parse(v);
    } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem('wordstep.' + key, JSON.stringify(value)); } catch { /* storage blocked */ }
  },
};

const settings = { voice: 'af_heart', speed: 1, autoplay: true, ...store.get('settings', {}) };
const saveSettings = () => store.set('settings', settings);

const state = { student: null, tts: null, levels: [], routeId: 0, onKey: null, onLeave: null };
const sid = () => state.student?.id;

async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = null;
    try { detail = (await res.json()).detail; } catch { /* not JSON */ }
    const msg = typeof detail === 'string' ? detail : detail?.message || `${res.status} ${res.statusText}`;
    const err = new Error(msg);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return res.json();
}

let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2200);
}

/* ======================================================================= audio (Kokoro TTS) */

const player = new Audio();
let playId = 0;
let finishCurrent = null;

function ttsUrl(text, speed) {
  return '/api/tts?' + new URLSearchParams({ text: plain(text), voice: settings.voice, speed: String(speed ?? settings.speed) });
}

function browserSpeak(text, speed) {
  return new Promise((resolve) => {
    if (!('speechSynthesis' in window)) return resolve();
    const u = new SpeechSynthesisUtterance(plain(text));
    u.lang = settings.voice.startsWith('b') ? 'en-GB' : 'en-US';
    u.rate = speed ?? settings.speed;
    u.onend = u.onerror = () => resolve();
    speechSynthesis.speak(u);
  });
}

function stopAudio() {
  playId++;
  player.pause();
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  finishCurrent?.();
}

// Play one clip; resolves when it ends, fails, or is interrupted. Falls back to the browser voice.
function playClip(text, speed) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      if (finishCurrent === finish) finishCurrent = null;
      resolve();
    };
    finishCurrent = finish;
    const fallback = () => { if (!settled) browserSpeak(text, speed).then(finish); };
    if (state.tts && !state.tts.available) return fallback();
    player.onended = finish;
    player.onerror = fallback;
    player.src = ttsUrl(text, speed);
    player.play().catch((e) => { if (e.name === 'NotAllowedError') finish(); });
  });
}

async function speak(text, { speed, btn } = {}) {
  stopAudio();
  btn?.classList.add('playing');
  await playClip(text, speed);
  btn?.classList.remove('playing');
}

async function speakAll(texts, btn) {
  stopAudio();
  const id = playId;
  btn?.classList.add('playing');
  for (const t of texts) {
    if (id !== playId) break;
    await playClip(t);
  }
  btn?.classList.remove('playing');
}

/* ======================================================================= UI pieces */

const ICON = {
  speaker: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor" stroke="none"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>',
  star: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/></svg>',
  play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z" fill="currentColor"/></svg>',
};

const speakBtn = (text, label = 'Listen') =>
  `<button class="icon-btn" type="button" data-speak="${esc(plain(text))}" title="${label}" aria-label="${label}">${ICON.speaker}</button>`;
const slowBtn = (text) =>
  `<button class="chip-btn" type="button" data-speak="${esc(plain(text))}" data-speed="0.7" title="Listen slowly">slow</button>`;
const saveBtn = (key, saved) =>
  `<button class="icon-btn star ${saved ? 'on' : ''}" type="button" data-save="${esc(key)}" aria-pressed="${!!saved}" title="${saved ? 'Remove from My Words' : 'Save to My Words'}" aria-label="Save word">${ICON.star}</button>`;
const STATUS_LABEL = { new: 'New', learning: 'Learning', mastered: 'Mastered' };
const pill = (status) => `<span class="pill ${status}">${STATUS_LABEL[status] || status}</span>`;
const bar = (c, cls = '') =>
  `<div class="progress ${cls}" role="img" aria-label="${c.mastered} mastered, ${c.learning} learning, ${c.new} new">
     <span class="seg mastered" style="width:${pct(c.mastered, c.total)}%"></span>
     <span class="seg learning" style="width:${pct(c.learning, c.total)}%"></span>
   </div>`;
const levelTitle = (id) => state.levels.find((l) => l.id === id)?.title;
const wordHref = (w) => `#/word/${enc(w)}`;

function dueLabel(due) {
  if (!due) return '';
  const days = Math.round((new Date(due + 'T00:00') - new Date(localDate() + 'T00:00')) / 86400000);
  if (days < 0) return '<span class="due-label now">overdue</span>';
  if (days === 0) return '<span class="due-label now">due today</span>';
  return `<span class="due-label">in ${days} day${days === 1 ? '' : 's'}</span>`;
}

function wordRow(w) {
  return `<li>
    <div class="wl-main">
      <a class="wl-word" href="${wordHref(w.key)}">${esc(w.word)}</a>
      ${w.pos ? `<span class="pos small"> ${esc(w.pos)}</span>` : ''}
      <div class="wl-def">${esc(w.definition) || '<em>definition loading…</em>'}</div>
    </div>
    <div class="wl-side">${dueLabel(w.status !== 'new' ? w.due : null)} ${pill(w.status)} ${speakBtn(w.word)} ${saveBtn(w.key, w.saved)}</div>
  </li>`;
}

function entryHTML(e, key, progress, { actions = true } = {}) {
  const examples = e.examples || [];
  const senses = (e.senses || []).slice(1);
  const listenAll = [e.word, e.definition, ...examples].filter(Boolean).map(plain);
  const level = e.level && levelTitle(e.level);
  return `
  <article class="entry card">
    <header class="entry-head">
      <div>
        <h1 class="headword">${esc(e.word)}</h1>
        <div class="pron">
          ${e.ipa ? `<span class="ipa">${esc(e.ipa)}</span>` : ''}
          ${speakBtn(e.word, 'Pronounce')} ${slowBtn(e.word)}
        </div>
      </div>
      <div class="head-actions">
        <button class="btn ghost small" type="button" data-speak-all="${esc(JSON.stringify(listenAll))}">${ICON.play} Listen to all</button>
        ${progress ? saveBtn(key, progress.saved) : ''}
      </div>
    </header>
    <div class="meta">
      ${e.pos ? `<span class="pos">${esc(e.pos)}</span>` : ''}
      ${level ? `<a class="tag" href="#/level/${enc(e.level)}">${esc(level)}</a>` : ''}
      ${progress ? `<span class="status-slot">${pill(progress.status)}</span>` : ''}
      ${e.source && e.source !== 'built-in' ? `<span class="source">source: ${esc(e.source)}</span>` : ''}
    </div>
    <section class="def">
      <p>${esc(e.definition) || '<em>No definition available yet.</em>'}</p>
      ${e.definition ? speakBtn(e.definition, 'Listen to the definition') : ''}
    </section>
    ${senses.length ? `<h3>Other meanings</h3><ol class="senses">${senses.map((s) =>
      `<li><span class="pos small">${esc(s.pos)}</span> ${esc(s.definition)} ${speakBtn(s.definition)}</li>`).join('')}</ol>` : ''}
    ${examples.length ? `<h3>Examples</h3><ul class="examples">${examples.map((s) =>
      `<li><span>${marked(s)}</span>${speakBtn(s, 'Listen to the example')}</li>`).join('')}</ul>` : ''}
    ${e.synonyms?.length ? `<h3>Similar words</h3><div>${e.synonyms.map((s) =>
      `<a class="chip" href="${wordHref(s)}">${esc(s)}</a>`).join('')}</div>` : ''}
    ${e.note ? `<aside class="note"><strong>Tip</strong>${esc(e.note)}</aside>` : ''}
    ${actions && progress ? `<footer class="entry-actions">
      <button class="btn success" type="button" data-action="know" data-word="${esc(key)}">I know this word</button>
      <button class="btn warn" type="button" data-action="learning" data-word="${esc(key)}">Still learning — review it</button>
    </footer>` : ''}
  </article>`;
}

function wireSearch(form) {
  const input = $('input', form);
  const list = $('.suggest', form);
  let timer, items = [], active = -1;
  const go = (q) => { if (q.trim()) location.hash = wordHref(q.trim()); };
  const paintList = () => {
    list.hidden = !items.length;
    list.innerHTML = items.map((w, i) => `<li data-w="${esc(w)}" class="${i === active ? 'active' : ''}">${esc(w)}</li>`).join('');
  };
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const q = input.value.trim();
      items = q ? await api(`/api/suggest?q=${enc(q)}`).catch(() => []) : [];
      active = -1;
      paintList();
    }, 120);
  });
  input.addEventListener('keydown', (e) => {
    if (!items.length) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      active = (active + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      paintList();
    } else if (e.key === 'Escape') { items = []; paintList(); }
  });
  input.addEventListener('blur', () => setTimeout(() => { items = []; paintList(); }, 150));
  list.addEventListener('mousedown', (e) => { const li = e.target.closest('li'); if (li) go(li.dataset.w); });
  form.addEventListener('submit', (e) => { e.preventDefault(); go(active >= 0 ? items[active] : input.value); });
}

const searchBox = (big = false, value = '') => `
  <form class="searchbox ${big ? 'big' : ''}" role="search">
    <input type="search" placeholder="Look up a word or phrasal verb…" autocomplete="off" spellcheck="false" value="${esc(value)}" aria-label="Search the dictionary">
    <button class="btn primary" type="submit">Look up</button>
    <ul class="suggest" hidden></ul>
  </form>`;

/* ======================================================================= status bar */

async function refreshStatus() {
  if (!sid()) return null;
  const d = await api(`/api/dashboard?student=${sid()}`);
  state.dash = d;
  const o = d.overall;
  const goalDone = d.today.done >= d.today.goal;
  $('#statusbar').innerHTML = `
    <div class="sb-main">
      <div class="sb-top">
        <span><strong>${o.mastered + o.learning}</strong> of ${o.total} words studied · <strong>${Math.round(pct(o.mastered, o.total))}%</strong> mastered</span>
        <span class="legend">
          <span><span class="dot mastered"></span>${o.mastered} mastered</span>
          <span><span class="dot learning"></span>${o.learning} learning</span>
          <span><span class="dot new"></span>${o.new} new</span>
        </span>
      </div>
      ${bar(o)}
    </div>
    <div class="sb-stats">
      <a class="stat" href="#/" title="Days in a row with study">🔥 <b>${d.streak}</b> day streak</a>
      <a class="stat ${goalDone ? 'goal-done' : ''}" href="#/study?today=1" title="Today's new words">🎯 <b>${d.today.done}/${d.today.goal}</b> new today</a>
      <a class="stat ${d.due ? 'due' : ''}" href="#/quiz/review" title="Words due for review">🔁 <b>${d.due}</b> to review</a>
      <a class="stat ${d.reading.minutes >= d.reading.goal ? 'goal-done' : ''}" href="#/library" title="Minutes read today">📖 <b>${d.reading.minutes}/${d.reading.goal}</b> min read</a>
      ${d.grammar.due ? `<a class="stat due" href="#/grammar/review" title="Grammar points due for review">🧩 <b>${d.grammar.due}</b> grammar</a>` : ''}
    </div>`;
  return d;
}

async function loadLevels() {
  state.levels = await api(`/api/levels?student=${sid()}`);
  return state.levels;
}

/* ======================================================================= pages */

async function renderHome({ paint }) {
  const [d, levels, readRec] = await Promise.all([refreshStatus(), loadLevels(),
    api(`/api/library/recommend?student=${sid()}`).catch(() => null)]);
  const rec = d.recommended;
  const todayWords = d.today.words;
  const left = todayWords.filter((w) => !w.done).length;
  // The reading level test can show that earlier word steps are too easy.
  const startLv = d.reading.start_level && levels.find((l) => l.id === d.reading.start_level);
  const jump = startLv && rec && startLv.order > rec.order ? startLv : null;
  if (!paint(`
    <div class="hello">
      <div><h1>Hello, ${esc(d.student.name)}!</h1>
      <p class="muted">${rec ? `Your next step: <b>${esc(rec.title)}</b> (${esc(rec.band)})` : 'You have studied every level. Amazing!'}</p></div>
    </div>
    <div class="home-search">${searchBox(true)}</div>
    ${jump ? `<div class="card callout skip-ahead"><h2>Skip ahead?</h2>
      <p class="muted small">Your level test (${esc(d.reading.cefr)}) suggests you already know most words before <b>${esc(jump.title)}</b>.
        Take a quick pretest of ${esc(rec.title)} to skip the words you know, or go straight to ${esc(jump.title)}.</p>
      <div class="card-actions"><a class="btn primary" href="#/quiz/pretest?level=${enc(rec.id)}">Pretest ${esc(rec.title)}</a>
        <a class="btn" href="#/level/${enc(jump.id)}">Go to ${esc(jump.title)}</a></div></div>` : ''}
    <div class="grid two">
      <section class="card">
        <h2>Today's new words</h2>
        <p class="muted small">${todayWords.length ? `${d.today.done} of ${todayWords.length} done${rec ? ` · from ${esc(rec.title)}` : ''}` : 'No new words left — import a list in Settings.'}</p>
        <div>${todayWords.map((w) => `<a class="chip ${w.done ? 'done' : ''}" href="${wordHref(w.key)}">${w.done ? '✓ ' : ''}${esc(w.word)}</a>`).join('')}</div>
        <div class="card-actions">
          ${left ? `<a class="btn primary" href="#/study?today=1">Study ${left} word${left === 1 ? '' : 's'}</a>` : todayWords.length ? '<span class="pill mastered">Daily goal reached 🎉</span>' : ''}
        </div>
      </section>
      ${todayReadingCard(readRec, d.reading)}
      <section class="card">
        <h2>Today's review</h2>
        <div class="big-number">${d.due}</div>
        <p class="muted small">${d.due ? 'words are ready for review. Spaced repetition brings each word back just before you forget it.' : 'Nothing due right now. Words you study today come back here.'}</p>
        <div class="card-actions">
          <a class="btn ${d.due ? 'primary' : ''}" href="#/quiz/review" ${d.due ? '' : 'aria-disabled="true"'}>Start review</a>
          <a class="btn ghost" href="#/mywords">My Words (${d.saved})</a>
        </div>
      </section>
      ${grammarHomeCard(d.grammar)}
      ${rec ? `<section class="card">
        <h2>Pretest</h2>
        <p class="muted small">Already know some words in <b>${esc(rec.title)}</b>? Take a quick test — words you get right are skipped, so you only study what you need.</p>
        <div class="card-actions"><a class="btn" href="#/quiz/pretest?level=${enc(rec.id)}">Take a pretest</a></div>
      </section>` : ''}
      <section class="card wide">
        <h2>Your path</h2>
        <ul class="mini-levels">${levels.map((l) => `
          <li><a href="#/level/${enc(l.id)}">${esc(l.title)}</a>${bar(l, 'thin')}<span class="num">${l.mastered + l.learning}/${l.total}</span></li>`).join('')}
        </ul>
        <div class="card-actions"><a class="btn ghost small" href="#/learn">See all levels →</a></div>
      </section>
    </div>`)) return;
  wireSearch($('.home-search form'));
}

async function renderLearn({ paint }) {
  const levels = await loadLevels();
  paint(`
    <h1>Learn step by step</h1>
    <p class="muted">Go from everyday words to phrasal verbs, academic words and finally advanced Word Smart–style vocabulary.
      A level is covered when 80% of its words are learning or mastered — then the next one is recommended.</p>
    <ol class="path">${levels.map((l, i) => {
      const covered = l.total && (l.mastered + l.learning) / l.total >= 0.8;
      return `<li class="step ${l.recommended ? 'rec' : ''} ${covered ? 'done' : ''}">
        <div class="step-num">${covered ? '✓' : i + 1}</div>
        <div class="card">
          <div class="step-title"><h2><a href="#/level/${enc(l.id)}">${esc(l.title)}</a></h2>
            <span class="tag">${esc(l.band)}</span>${l.recommended ? '<span class="badge-rec">Next step</span>' : ''}</div>
          <p class="muted small">${esc(l.description)}</p>
          ${bar(l)}
          <div class="step-counts"><span><span class="dot mastered"></span>${l.mastered} mastered</span>
            <span><span class="dot learning"></span>${l.learning} learning</span><span><span class="dot new"></span>${l.new} new</span></div>
          <div class="card-actions">
            <a class="btn ${l.recommended ? 'primary' : ''} small" href="#/level/${enc(l.id)}">Open</a>
            ${l.new ? `<a class="btn ghost small" href="#/study?level=${enc(l.id)}">Study new words</a>
            <a class="btn ghost small" href="#/quiz/pretest?level=${enc(l.id)}">Pretest</a>` : ''}
          </div>
        </div>
      </li>`;
    }).join('')}</ol>
    <p class="muted small" style="margin-top:1rem">Have Word Smart 1 or 2? <a href="#/settings">Import your word list</a> to add it as a level.</p>`);
}

async function renderLevel({ arg, params, paint }) {
  const lv = await api(`/api/levels/${enc(arg)}?student=${sid()}`);
  const f = params.get('f') || 'all';
  const words = f === 'all' ? lv.words : lv.words.filter((w) => w.status === f);
  const tab = (key, label, n) => `<a class="${f === key ? 'active' : ''}" href="#/level/${enc(lv.id)}?f=${key}">${label} (${n})</a>`;
  const missing = lv.custom ? lv.words.filter((w) => !w.definition).length : 0;
  paint(`
    <a href="#/learn" class="small">← All levels</a>
    <div class="card" style="margin-top:.5rem">
      <div class="step-title"><h1 style="margin:0">${esc(lv.title)}</h1><span class="tag">${esc(lv.band)}</span>
        ${lv.recommended ? '<span class="badge-rec">Next step</span>' : ''}</div>
      <p class="muted">${esc(lv.description)}</p>
      ${bar(lv)}
      <div class="step-counts"><span><span class="dot mastered"></span>${lv.mastered} mastered</span>
        <span><span class="dot learning"></span>${lv.learning} learning</span><span><span class="dot new"></span>${lv.new} new</span></div>
      ${missing ? `<p class="muted small">Looking up definitions for ${missing} imported words… refresh in a moment.</p>` : ''}
      <div class="card-actions">
        ${lv.new ? `<a class="btn primary" href="#/study?level=${enc(lv.id)}">Study new words</a>
        <a class="btn" href="#/quiz/pretest?level=${enc(lv.id)}">Pretest this level</a>` : '<span class="pill mastered">All words started</span>'}
        ${/^(A1|A2|B1|B2|C1|C2)/.test(lv.band) ? `<a class="btn ghost" href="#/browse?cefr=${enc(lv.band.slice(0, 2))}">Read books at ${esc(lv.band.slice(0, 2))}</a>` : ''}
      </div>
    </div>
    <nav class="tabs">${tab('all', 'All', lv.total)}${tab('new', 'New', lv.new)}${tab('learning', 'Learning', lv.learning)}${tab('mastered', 'Mastered', lv.mastered)}</nav>
    <div class="card">${words.length ? `<ul class="word-list">${words.map(wordRow).join('')}</ul>` : '<p class="empty">No words here yet.</p>'}</div>`);
}

async function renderWord({ arg, paint }) {
  let data;
  try {
    data = await api(`/api/word?q=${enc(arg)}&student=${sid()}`);
  } catch (err) {
    if (err.status !== 404 && err.status !== 503) throw err;
    const sug = err.detail?.suggestions || [];
    if (paint(`${searchBox(false, arg)}
      <div class="card" style="margin-top:1rem"><h2>${esc(err.message)}</h2>
        ${err.status === 503
          ? '<p class="muted">Words in the WordStep levels always work offline.</p><button class="btn" type="button" onclick="route()">Try again</button>'
          : '<p class="muted">Check the spelling, or try the base form (e.g. "run" instead of "running").</p>'}
        ${sug.length ? `<h3>Did you mean</h3>${sug.map((s) => `<a class="chip" href="${wordHref(s)}">${esc(s)}</a>`).join('')}` : ''}
      </div>`)) wireSearch($('.searchbox'));
    return;
  }
  const history = store.get('history', []).filter((h) => h !== data.key);
  store.set('history', [data.key, ...history].slice(0, 15));
  if (!paint(`<div class="word-page">${searchBox()}${entryHTML(data.entry, data.key, data.progress)}<div id="contexts"></div></div>`)) return;
  wireSearch($('.searchbox'));
  if (settings.autoplay) speak(data.entry.word);
  wordContextsHTML(data.key).then((html) => { const slot = $('#contexts'); if (slot) slot.innerHTML = html; }).catch(() => {});
}

function renderSearch({ paint }) {
  const history = store.get('history', []);
  paint(`
    <h1>Dictionary</h1>
    ${searchBox(true)}
    ${history.length ? `<h3>Recently looked up</h3><div>${history.map((h) => `<a class="chip" href="${wordHref(h)}">${esc(h)}</a>`).join('')}</div>` : ''}
    <p class="muted small" style="margin-top:1.5rem">Words in the WordStep levels have learner-friendly definitions, examples and usage tips.
      Other words come from the free <a href="https://dictionaryapi.dev" target="_blank" rel="noopener">dictionaryapi.dev</a>.
      Every word, definition and example can be read aloud with Kokoro TTS.</p>`);
  wireSearch($('.searchbox'));
  $('.searchbox input').focus();
}

async function renderMyWords({ params, paint }) {
  const words = await api(`/api/mywords?student=${sid()}`);
  const today = localDate();
  const f = params.get('f') || 'saved';
  const filters = {
    saved: ['Saved', (w) => w.saved],
    due: ['Due today', (w) => w.box > 0 && w.due && w.due <= today],
    learning: ['Learning', (w) => w.status === 'learning'],
    mastered: ['Mastered', (w) => w.status === 'mastered'],
  };
  const shown = words.filter(filters[f][1]);
  const flash = words.filter((w) => w.saved || w.status === 'learning').length;
  paint(`
    <h1>My Words</h1>
    <p class="muted">Tap ☆ on any word to save it here. Saved words join your spaced review automatically.</p>
    <div class="card-actions" style="margin-top:0">
      <a class="btn primary" href="#/quiz/review">Review due words</a>
      ${flash ? `<a class="btn" href="#/study?mywords=1">Flashcards (${flash})</a>` : ''}
    </div>
    <nav class="tabs">${Object.entries(filters).map(([k, [label, fn]]) =>
      `<a class="${k === f ? 'active' : ''}" href="#/mywords?f=${k}">${label} (${words.filter(fn).length})</a>`).join('')}</nav>
    <div class="card">${shown.length ? `<ul class="word-list">${shown.map(wordRow).join('')}</ul>`
      : '<p class="empty">Nothing here yet. Save words from the dictionary or study a level.</p>'}</div>`);
}

/* ---------------------------------------------------------------- flashcard study */

async function renderStudy({ params, paint }) {
  let keys = [], title = 'Study', post = true;
  if (params.get('today')) {
    const d = await refreshStatus();
    keys = d.today.words.filter((w) => !w.done).map((w) => w.key);
    title = "Today's new words";
  } else if (params.get('level')) {
    const lv = await api(`/api/levels/${enc(params.get('level'))}?student=${sid()}`);
    keys = lv.words.filter((w) => w.status === 'new').slice(0, state.student.daily_goal).map((w) => w.key);
    title = lv.title;
  } else if (params.get('words')) {
    keys = params.get('words').split(',').filter(Boolean);
    title = params.get('title') || 'Practice';
    post = params.get('post') === '1';      // e.g. words to learn before reading a story
  } else if (params.get('mywords')) {
    const words = await api(`/api/mywords?student=${sid()}`);
    keys = shuffle(words.filter((w) => w.saved || w.status === 'learning').map((w) => w.key));
    title = 'My Words';
    post = false;
  }
  if (!keys.length) {
    paint(`<div class="card empty"><h2>No words to study here</h2><p>You've started every word in this set.</p>
      <div class="row" style="justify-content:center"><a class="btn primary" href="#/quiz/review">Review</a><a class="btn" href="#/learn">Choose a level</a></div></div>`);
    return;
  }

  const then = (params.get('then') || '').startsWith('#/') ? params.get('then') : '';
  const entries = new Map();
  const getEntry = (k) => {
    if (!entries.has(k)) entries.set(k, api(`/api/word?q=${enc(k)}&student=${sid()}`));
    return entries.get(k);
  };
  let i = 0;
  const knew = [], learning = [];

  async function show() {
    if (i >= keys.length) return finish();
    const key = keys[i];
    if (keys[i + 1]) getEntry(keys[i + 1]).catch(() => {});
    let data;
    try { data = await getEntry(key); } catch { i++; return show(); }
    const e = data.entry;
    const ok = paint(`
      <div class="session-head"><a href="#/">← ${esc(title)}</a><span>${i + 1} / ${keys.length}</span></div>
      ${bar({ total: keys.length, mastered: i, learning: 0, new: keys.length - i }, 'thin')}
      <div id="slot">
        <div class="card flashcard">
          <div class="headword">${esc(e.word)}</div>
          <div class="pron">${e.ipa ? `<span class="ipa">${esc(e.ipa)}</span>` : ''} ${speakBtn(e.word)} ${slowBtn(e.word)}</div>
          ${e.pos ? `<p class="pos">${esc(e.pos)}</p>` : ''}
          <p class="hint">Do you know what it means? Say it in your head, then check.</p>
          <button class="btn primary" id="reveal" type="button">Show meaning <kbd>Space</kbd></button>
        </div>
      </div>`);
    if (!ok) return;
    if (settings.autoplay) speak(e.word);
    const reveal = () => {
      $('#slot').innerHTML = entryHTML(e, key, data.progress, { actions: false }) + `
        <div class="study-actions">${post
          ? `<button class="btn success" id="knew" type="button">I knew it <kbd>1</kbd></button>
             <button class="btn warn" id="still" type="button">Still learning <kbd>2</kbd></button>`
          : `<button class="btn primary" id="next" type="button">Next <kbd>→</kbd></button>`}</div>`;
      if (post) {
        $('#knew').onclick = () => advance('know');
        $('#still').onclick = () => advance('learning');
        state.onKey = (ev) => { if (ev.key === '1') advance('know'); if (ev.key === '2') advance('learning'); };
      } else {
        $('#next').onclick = () => advance(null);
        $('#next').focus();
        state.onKey = (ev) => { if (ev.key === 'ArrowRight') advance(null); };
      }
    };
    $('#reveal').onclick = reveal;
    $('#reveal').focus();
    state.onKey = (ev) => { if (ev.key === ' ') { ev.preventDefault(); reveal(); } };

    async function advance(action) {
      state.onKey = null;
      if (action) {
        try {
          await api('/api/progress', { method: 'POST', body: { student: sid(), word: key, action } });
          (action === 'know' ? knew : learning).push(e.word);
        } catch (err) { toast(err.message); }
      }
      i++;
      show();
    }
  }

  function finish() {
    refreshStatus();
    paint(`<div class="card results">
      <h1>Session complete</h1>
      ${post ? `<div class="score">${knew.length + learning.length}<small>words</small></div>
        <p class="muted">You knew <b>${knew.length}</b> and started learning <b>${learning.length}</b>.
        ${learning.length ? 'The words you are learning are in today\'s review — quizzing yourself now locks them in.' : ''}</p>`
        : `<p class="muted">You went through ${keys.length} cards.</p>`}
      <div class="row">
        ${then ? `<a class="btn primary" href="${esc(then)}">Continue to the story →</a>` : ''}
        ${post && learning.length && !then ? '<a class="btn primary" href="#/quiz/review">Quiz me now</a>' : ''}
        <a class="btn" href="#/">Home</a>
      </div></div>`);
  }

  show();
}

/* ---------------------------------------------------------------- quiz */

const QLABEL = {
  meaning: 'Choose the word that matches this meaning',
  word: 'Choose the correct meaning',
  cloze: 'Choose the word that completes the sentence (its form may change)',
  spell: 'Listen and type the word',
};

async function renderQuiz(ctx) {
  if (ctx.arg === 'review' || ctx.arg === 'pretest') return runQuiz(ctx.arg, ctx);
  const [d, levels] = await Promise.all([refreshStatus(), loadLevels()]);
  const sizes = (id, def) => `<select id="${id}">${[5, 10, 15, 20].map((n) => `<option ${n === def ? 'selected' : ''}>${n}</option>`).join('')}</select>`;
  if (!ctx.paint(`
    <h1>Quiz</h1>
    <div class="grid two">
      <section class="card quiz-card">
        <h2>Today's review</h2>
        <div class="big-number">${d.due}</div>
        <p class="muted small">words due today. Four question types: meaning → word, word → meaning, fill in the blank, and listen &amp; spell.</p>
        <label>Questions ${sizes('rv-size', 10)}</label>
        <button class="btn primary" id="start-review" type="button" ${d.due ? '' : 'disabled'}>Start review</button>
        ${d.due ? '' : '<p class="muted small">Nothing is due. Study new words or take a pretest.</p>'}
      </section>
      <section class="card quiz-card">
        <h2>Pretest</h2>
        <p class="muted small">Find out which words you already know before studying a level. Correct answers are marked as known;
          missed words are saved to My Words.</p>
        <label>Level <select id="pt-level">${levels.map((l) =>
          `<option value="${esc(l.id)}" ${l.recommended ? 'selected' : ''} ${l.new ? '' : 'disabled'}>${esc(l.title)} (${l.new} new)</option>`).join('')}</select></label>
        <label>Questions ${sizes('pt-size', 10)}</label>
        <button class="btn primary" id="start-pretest" type="button">Start pretest</button>
      </section>
    </div>`)) return;
  $('#start-review').onclick = () => { location.hash = `#/quiz/review?size=${$('#rv-size').value}`; };
  $('#start-pretest').onclick = () => { location.hash = `#/quiz/pretest?level=${enc($('#pt-level').value)}&size=${$('#pt-size').value}`; };
}

async function runQuiz(mode, { params, paint }) {
  const query = new URLSearchParams({ student: sid(), mode, size: params.get('size') || 10 });
  if (params.get('level')) query.set('level', params.get('level'));
  const data = await api(`/api/quiz?${query}`);
  if (!data.questions.length) {
    paint(`<div class="card empty">
      <h2>${mode === 'review' ? 'Nothing to review right now 🎉' : 'No new words left in this level'}</h2>
      <p>${mode === 'review' ? 'Words come back here when they are due. Study some new words first.' : 'Every word in this level has been started.'}</p>
      <div class="row" style="justify-content:center"><a class="btn primary" href="#/learn">Learn new words</a><a class="btn" href="#/quiz">Quiz menu</a></div></div>`);
    return;
  }
  const total = data.questions.length;
  const queue = data.questions.map((q) => ({ ...q, retry: false }));
  const first = new Map();   // word -> first-attempt result (only these are graded)
  let pos = 0;
  const heading = mode === 'review' ? "Today's review" : `Pretest · ${esc(data.level?.title || '')}`;

  function promptHTML(q) {
    if (q.type === 'word') return `<div class="qprompt word">${esc(q.prompt)} ${speakBtn(q.speak)}</div>`;
    if (q.type === 'cloze') return `<p class="qprompt">${esc(q.prompt).replace('_____', '<span class="blank">_____</span>')}</p>`;
    if (q.type === 'spell') return `<p class="qprompt">${esc(q.prompt)}</p>
      <div class="listen-row"><button class="btn" type="button" data-speak="${esc(q.speak)}">${ICON.speaker} Play again</button>${slowBtn(q.speak)}</div>`;
    return `<p class="qprompt">${esc(q.prompt)}</p>`;
  }

  function showQuestion() {
    if (pos >= queue.length) return results();
    const q = queue[pos];
    const done = first.size;
    const ok = paint(`
      <div class="session-head"><a href="#/quiz">← ${heading}</a><span>${q.retry ? 'Second chance' : `${done + 1} / ${total}`}</span></div>
      <div class="progress thin"><span class="seg primary" style="width:${pct(done, total)}%"></span></div>
      <div class="card">
        <div class="qtype">${QLABEL[q.type]}</div>
        ${promptHTML(q)}
        ${q.type === 'spell'
          ? `<form class="spell-form" autocomplete="off"><input id="spell" type="text" spellcheck="false" autocapitalize="off" autocorrect="off" placeholder="Type what you hear" aria-label="Your answer"><button class="btn primary" type="submit">Check</button></form>`
          : `<div class="options">${q.options.map((o, i) => `<button class="option" type="button" data-i="${i}"><kbd>${i + 1}</kbd><span>${esc(o)}</span></button>`).join('')}</div>`}
        <div id="feedback"></div>
      </div>`);
    if (!ok) return;

    if (q.type === 'spell') {
      const input = $('#spell');
      input.focus();
      speak(q.speak);
      $('.spell-form').onsubmit = (e) => {
        e.preventDefault();
        if (!input.value.trim() || input.disabled) return;
        const norm = (s) => s.trim().toLowerCase().replace(/\s+/g, ' ');
        answer(norm(input.value) === norm(q.answer_text));
      };
    } else {
      if (q.type === 'word' && settings.autoplay) speak(q.speak);
      $$('.option').forEach((b) => { b.onclick = () => answer(Number(b.dataset.i) === q.answer, Number(b.dataset.i)); });
      state.onKey = (e) => {
        const n = Number(e.key);
        if (n >= 1 && n <= q.options.length) answer(n - 1 === q.answer, n - 1);
      };
    }

    function answer(correct, chosen) {
      if (q.answered) return;
      q.answered = true;
      state.onKey = null;
      if (q.type === 'spell') {
        const input = $('#spell');
        input.disabled = true;
        input.classList.add(correct ? 'correct' : 'wrong');
      } else {
        $$('.option').forEach((b, i) => {
          b.disabled = true;
          if (i === q.answer) b.classList.add('correct');
          else if (i === chosen) b.classList.add('wrong');
        });
      }
      if (!q.retry) {
        first.set(q.word, { correct, word: q.feedback.word });
        api('/api/quiz/answer', { method: 'POST', body: { student: sid(), word: q.word, correct, mode } })
          .catch(() => toast('Could not save your answer'));
        if (!correct && mode === 'review') queue.push({ ...q, retry: true, answered: false });
      }
      const f = q.feedback;
      const example = q.type === 'cloze' ? q.prompt.replace('_____', `*${q.removed}*`) : f.example;
      $('#feedback').innerHTML = `
        <div class="fb ${correct ? 'ok' : 'bad'}">
          <strong>${correct ? 'Correct!' : 'Not quite.'}</strong>
          ${correct ? '' : ` The answer is <b>${esc(f.word)}</b>.`}
          <div class="fb-entry">
            <div class="row"><span class="fb-word">${esc(f.word)}</span>
              ${f.ipa ? `<span class="ipa">${esc(f.ipa)}</span>` : ''}${speakBtn(f.word)}</div>
            <p>${esc(f.definition)}</p>
            ${example ? `<p class="ex">${marked(example)} ${speakBtn(example)}</p>` : ''}
          </div>
          <button class="btn primary" id="next" type="button">Next <kbd>Enter</kbd></button>
        </div>`;
      $('#next').onclick = () => { pos++; showQuestion(); };
      $('#next').focus();
      if (settings.autoplay && q.type !== 'spell') speak(f.word);
    }
  }

  function results() {
    const rows = [...first.entries()];
    const right = rows.filter(([, v]) => v.correct).length;
    const missed = rows.filter(([, v]) => !v.correct).map(([k]) => k);
    refreshStatus();
    paint(`<div class="card results">
      <h1>${mode === 'review' ? 'Review complete' : 'Pretest complete'}</h1>
      <div class="score">${right}/${rows.length}<small>${Math.round(pct(right, rows.length))}%</small></div>
      <p class="muted">${mode === 'pretest'
        ? 'Words you got right are marked as known (you will see them once more in 2 weeks). Missed words are saved to My Words for tomorrow.'
        : 'Correct words move up a box and come back later. Missed words come back tomorrow.'}</p>
      <ul class="result-list">${rows.map(([k, v]) =>
        `<li class="${v.correct ? 'ok' : 'bad'}"><span>${v.correct ? '✓' : '✗'}</span><a href="${wordHref(k)}">${esc(v.word)}</a></li>`).join('')}</ul>
      <div class="row">
        ${missed.length ? `<a class="btn warn" href="#/study?words=${enc(missed.join(','))}">Study missed words</a>` : ''}
        <a class="btn" href="#/quiz">Quiz menu</a><a class="btn primary" href="#/">Home</a>
      </div></div>`);
  }

  showQuestion();
}

/* ---------------------------------------------------------------- settings */

async function renderSettings({ paint }) {
  const [tts, levels, libStatus] = await Promise.all([api('/api/tts/status'), loadLevels(), api('/api/library/status')]);
  state.tts = tts;
  const custom = levels.filter((l) => l.custom);
  if (!paint(`
    <h1>Settings</h1>
    <section class="card">
      <h2>Voice</h2>
      <p class="muted small">${tts.available
        ? 'Kokoro TTS is ready. Clips are cached, so each sentence is generated only once.'
        : 'Kokoro model files were not found, so your browser\'s voice is used. Run <code>uv run python -m app.tts --fetch</code> and restart.'}</p>
      <label>Voice <select id="voice">${Object.entries(tts.voices).map(([id, name]) =>
        `<option value="${id}" ${id === settings.voice ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select></label>
      <label>Speed <input type="range" id="speed" min="0.6" max="1.3" step="0.05" value="${settings.speed}" style="vertical-align:middle">
        <output id="speed-out">${Number(settings.speed).toFixed(2)}×</output></label>
      <label class="check"><input type="checkbox" id="autoplay" ${settings.autoplay ? 'checked' : ''}> Play pronunciation automatically</label>
      <button class="btn" type="button" data-speak="She advocates free education for all, and her argument is compelling.">${ICON.speaker} Test voice</button>
    </section>
    <section class="card">
      <h2>Daily goal</h2>
      <form id="goal-form" class="row">
        <label style="margin:0">New words per day <input type="number" id="goal" min="1" max="100" value="${state.student.daily_goal}" style="width:6rem"></label>
        <button class="btn primary" type="submit">Save</button>
      </form>
    </section>
    <section class="card">
      <h2>Import a word list (Word Smart 1 · 2 or any list)</h2>
      <p class="muted small">Paste words from your own copy of <i>Word Smart</i> (or a teacher's list), one per line.
        Plain words get their definition, IPA and examples from the dictionary automatically.
        To use your own notes, write <code>word | definition | example sentence</code>.</p>
      <form id="import-form">
        <label>Title <input id="imp-title" required maxlength="80" placeholder="Word Smart 1 — Part 1" style="width:min(100%,24rem)"></label>
        <label>Words<textarea id="imp-text" rows="9" required placeholder="abase&#10;abate | to become less strong | The storm finally abated.&#10;abdicate"></textarea></label>
        <div class="row"><button class="btn primary" type="submit">Import list</button><span id="imp-msg" class="muted small"></span></div>
      </form>
      ${custom.length ? `<h3>Imported lists</h3><ul class="custom-list">${custom.map((l) =>
        `<li><a href="#/level/${enc(l.id)}">${esc(l.title)}</a><span class="muted small">${l.total} words</span>
         <button class="btn ghost small danger" type="button" data-del="${esc(l.id)}">Delete</button></li>`).join('')}</ul>` : ''}
    </section>
    ${librarySettingsHTML(libStatus)}
    <section class="card">
      <h2>Student</h2>
      <p>Studying as <b>${esc(state.student.name)}</b>. Each student has their own saved words, review schedule and progress.</p>
      <button class="btn" id="switch" type="button">Switch student</button>
    </section>`)) return;

  $('#voice').onchange = (e) => { settings.voice = e.target.value; saveSettings(); };
  $('#speed').oninput = (e) => {
    settings.speed = Number(e.target.value);
    $('#speed-out').textContent = settings.speed.toFixed(2) + '×';
    saveSettings();
  };
  $('#autoplay').onchange = (e) => { settings.autoplay = e.target.checked; saveSettings(); };
  $('#goal-form').onsubmit = async (e) => {
    e.preventDefault();
    state.student = await api(`/api/students/${sid()}`, { method: 'PATCH', body: { daily_goal: Number($('#goal').value) } });
    toast('Daily goal saved');
    refreshStatus();
  };
  $('#import-form').onsubmit = async (e) => {
    e.preventDefault();
    const msg = $('#imp-msg');
    msg.textContent = 'Importing…';
    try {
      const r = await api('/api/levels/import', { method: 'POST', body: { title: $('#imp-title').value, text: $('#imp-text').value } });
      toast(`Imported ${r.count} words`);
      location.hash = `#/level/${enc(r.id)}`;
    } catch (err) { msg.textContent = err.message; }
  };
  $$('[data-del]').forEach((b) => {
    b.onclick = async () => {
      if (!confirm('Delete this imported list? Study progress for its words is kept.')) return;
      await api(`/api/levels/${enc(b.dataset.del)}`, { method: 'DELETE' });
      route();
    };
  });
  $('#switch').onclick = switchStudent;
  wireLibrarySettings(libStatus);
}

/* ======================================================================= students */

function chooseStudent() {
  return new Promise(async (resolve) => {
    const list = await api('/api/students');
    const modal = $('#profile-modal');
    $('#profile-list').innerHTML = list.length
      ? list.map((s) => `<button class="profile" type="button" data-sid="${s.id}"><span class="avatar">${esc(s.name[0].toUpperCase())}</span>${esc(s.name)}</button>`).join('')
      : '<p class="muted">No students yet. Type your name to start.</p>';
    modal.hidden = false;
    $('#new-name').value = '';
    $('#new-name').focus();
    const done = (s) => { modal.hidden = true; setStudent(s); resolve(s); };
    $('#profile-list').onclick = (e) => {
      const b = e.target.closest('[data-sid]');
      if (b) done(list.find((s) => String(s.id) === b.dataset.sid));
    };
    $('#new-profile').onsubmit = async (e) => {
      e.preventDefault();
      const name = $('#new-name').value.trim();
      if (name) done(await api('/api/students', { method: 'POST', body: { name } }));
    };
  });
}

function setStudent(s) {
  state.student = s;
  store.set('student', s.id);
  $('#student-chip').textContent = '👤 ' + s.name;
}

async function switchStudent() {
  stopAudio();
  await chooseStudent();
  location.hash = '#/';
  route();
}

/* ======================================================================= global events & router */

document.addEventListener('click', async (e) => {
  const one = e.target.closest('[data-speak]');
  if (one) {
    e.preventDefault();
    speak(one.dataset.speak, { speed: one.dataset.speed ? Number(one.dataset.speed) : undefined, btn: one });
    return;
  }
  const all = e.target.closest('[data-speak-all]');
  if (all) {
    e.preventDefault();
    speakAll(JSON.parse(all.dataset.speakAll), all);
    return;
  }
  const save = e.target.closest('[data-save]');
  if (save) {
    const on = save.classList.contains('on');
    try {
      const p = await api('/api/progress', { method: 'POST', body: { student: sid(), word: save.dataset.save, action: on ? 'unsave' : 'save' } });
      save.classList.toggle('on', p.saved);
      save.setAttribute('aria-pressed', String(p.saved));
      const slot = save.closest('.entry')?.querySelector('.status-slot');
      if (slot) slot.innerHTML = pill(p.status);
      toast(p.saved ? 'Saved to My Words' : 'Removed from My Words');
      refreshStatus();
    } catch (err) { toast(err.message); }
    return;
  }
  const act = e.target.closest('[data-action]');
  if (act) {
    try {
      const p = await api('/api/progress', { method: 'POST', body: { student: sid(), word: act.dataset.word, action: act.dataset.action } });
      const entry = act.closest('.entry');
      $('.status-slot', entry).innerHTML = pill(p.status);
      $('.star', entry)?.classList.toggle('on', p.saved);
      toast(act.dataset.action === 'know' ? 'Marked as known — you will see it again in 2 weeks' : 'Added to today\'s review');
      refreshStatus();
    } catch (err) { toast(err.message); }
  }
});

document.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.target.matches('input, textarea, select')) return;
  state.onKey?.(e);
});

$('#student-chip').addEventListener('click', switchStudent);

const ROUTES = {
  '': renderHome, learn: renderLearn, level: renderLevel, word: renderWord, search: renderSearch,
  mywords: renderMyWords, study: renderStudy, quiz: renderQuiz, settings: renderSettings,
  // reading.js
  library: renderLibrary, browse: renderBrowse, book: renderBook, read: renderRead,
  placement: renderPlacement, reading: renderReadingProfile, story: renderStoryMaker,
  grammar: renderGrammar,   // grammar.js
};
const NAV_OF = { study: 'learn', browse: 'library', book: 'library', read: 'library', placement: 'library',
  reading: 'library', story: 'library' };

function parseHash() {
  const h = location.hash.replace(/^#\/?/, '');
  const [path, qs = ''] = h.split('?');
  const [name = '', ...rest] = path.split('/');
  return { name, arg: decodeURIComponent(rest.join('/')), params: new URLSearchParams(qs) };
}

async function route() {
  if (!state.student) return;
  stopAudio();
  state.onLeave?.();          // e.g. the reader saves reading time
  state.onLeave = null;
  state.onKey = null;
  const id = ++state.routeId;
  // Each page paints through this guard so a slow page can't overwrite a newer one.
  const paint = (html) => {
    if (id !== state.routeId) return false;
    view.innerHTML = html;
    return true;
  };
  const { name, arg, params } = parseHash();
  const nav = ROUTES[name] ? name || 'home' : 'home';
  $$('.nav a').forEach((a) => a.classList.toggle('active', a.dataset.nav === (NAV_OF[nav] || nav)));
  view.innerHTML = '<div class="loading">Loading…</div>';
  window.scrollTo(0, 0);
  try {
    await (ROUTES[name] || renderHome)({ arg, params, paint });
  } catch (err) {
    console.error(err);
    paint(`<div class="card"><h2>Something went wrong</h2><p class="muted">${esc(err.message)}</p><a class="btn" href="#/">Home</a></div>`);
  }
}

async function boot() {
  state.tts = await api('/api/tts/status').catch(() => ({ available: false, voices: {} }));
  if (state.tts.voices && !(settings.voice in state.tts.voices)) settings.voice = state.tts.default_voice || 'af_heart';
  const students = await api('/api/students');
  const saved = students.find((s) => s.id === store.get('student', null));
  if (saved) setStudent(saved);
  else await chooseStudent();
  window.addEventListener('hashchange', route);
  await route();
  if (location.hash.replace(/^#\/?/, '') !== '') refreshStatus();
}

boot().catch((err) => {
  console.error(err);
  view.innerHTML = `<div class="card"><h2>WordStep could not start</h2><p class="muted">${esc(err.message)}</p>
    <p class="muted small">Is the server running? Start it with <code>uv run uvicorn app.main:app</code>.</p></div>`;
});
