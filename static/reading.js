'use strict';
/* Reading pages: library, reader, placement test, reading progress and AI stories.
   Loaded before app.js; it only declares functions, which use app.js helpers when they run. */

const FIT_LABEL = { easy: 'Easy', right: 'Just right', challenge: 'Challenge', hard: 'Hard' };
const FIT_HELP = {
  easy: 'Almost every word is familiar — good for reading fast and fluently.',
  right: 'About 2 new words in 100: the best level for reading on your own.',
  challenge: 'A few more new words. Learn them first, then read.',
  hard: 'Many new words. Read it later, or read it with lots of word help.',
};
const SOURCE_LABEL = { storybook: 'Storybook', gutenberg: 'Classic', teacher: 'Teacher', ai: 'AI story' };
const CEFR_LIST = ['Pre-A1', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const per100 = (cov) => Math.max(0, Math.round((1 - cov) * 1000) / 10);
const fmtInt = (n) => Number(n || 0).toLocaleString('en-US');

/* ======================================================================= shared pieces */

function fitBadge(fit) {
  return `<span class="fit fit-${fit}" title="${esc(FIT_HELP[fit] || '')}">${FIT_LABEL[fit] || fit}</span>`;
}

// One card: a book (links to the book page) or the next unit of a book (links to the reader).
function bookCard(b, { asUnit = false } = {}) {
  const cov = asUnit ? b.unit_coverage : b.coverage;
  const fit = asUnit ? b.unit_fit : b.fit;
  const words = asUnit ? b.unit_words : b.words;
  const href = asUnit ? `#/read/${enc(b.id)}/${b.unit}` : `#/book/${enc(b.id)}`;
  const part = asUnit && b.units > 1 ? `<div class="bc-sub">Part ${b.unit + 1} of ${b.units}${b.done_units ? ` · ${b.done_units} read` : ''}</div>` : '';
  return `<a class="book-card" href="${href}">
    <div class="bc-top"><span class="src">${SOURCE_LABEL[b.source] || b.source}</span><span class="tag">${esc(asUnit ? b.unit_cefr || b.cefr : b.cefr)}</span></div>
    <div class="bc-title">${esc(b.title)}</div>${part}
    <div class="bc-meta">${fitBadge(fit)} <span>${per100(cov)} new / 100 words</span></div>
    <div class="bc-meta muted">${Math.max(1, Math.round(words / 120))} min · ${fmtInt(words)} words${b.learning_hits ? ` · <b class="hits">★ ${b.learning_hits} of your words</b>` : ''}</div>
    ${b.finished ? '<span class="bc-done">✓ Read</span>' : ''}
  </a>`;
}

const cardRow = (list, opts) => `<div class="book-grid">${list.map((b) => bookCard(b, opts)).join('')}</div>`;

function levelChip(p) {
  return `<a class="level-chip" href="#/reading" title="Your reading level — see progress">📖 ${esc(p.cefr)} · about ${fmtInt(p.vocab)} words</a>`;
}

/* ======================================================================= library */

async function renderLibrary({ paint }) {
  const [status, rec, dash] = await Promise.all([
    api('/api/library/status'), api(`/api/library/recommend?student=${sid()}`), refreshStatus()]);
  const total = Object.values(status.counts).reduce((n, c) => n + c.books, 0);
  const placed = dash.reading.placed;
  const section = (title, help, list, opts) => list.length ? `<section class="lib-section">
      <h2>${title}</h2><p class="muted small">${help}</p>${cardRow(list, opts)}</section>` : '';
  const nothingFits = !rec.right.length && !rec.challenge.length;
  if (!paint(`
    <div class="hello"><div><h1>Library</h1>
      <p class="muted">Books are matched to you like a masked-word game: in a text that fits, only about 2 of every 100 words are new.</p></div>
      ${levelChip(rec)}</div>
    ${placed ? '' : `<div class="card callout"><h2>Find your reading level</h2>
      <p class="muted small">A 3-minute word test tells the library which books fit you. Until then, books are matched to a beginner–intermediate level.</p>
      <div class="card-actions"><a class="btn primary" href="#/placement">Take the level test</a></div></div>`}
    ${total ? '' : `<div class="card callout"><h2>The library is empty</h2>
      <p class="muted small">Download the free books once (about 760 short storybooks and 32 classics). After that they work offline.</p>
      <div class="card-actions"><a class="btn primary" href="#/settings">Open library settings</a></div></div>`}
    ${section('Continue reading', 'Pick up where you stopped.', rec.continue, { asUnit: true })}
    ${section('Just right for you', FIT_HELP.right, rec.right, { asUnit: true })}
    ${section('A little challenge', 'About 3–5 new words in 100. The reader shows them first so you can learn them before you start.', rec.challenge, { asUnit: true })}
    ${nothingFits ? section('Best matches for now', 'Nothing in the library is easy enough yet, so these are the closest. Learn the new words first and tap any word you don’t know — or ask for a story written at your level.', rec.stretch, { asUnit: true }) : ''}
    ${section('Easy reading', FIT_HELP.easy, rec.easy, { asUnit: true })}
    <section class="grid two lib-tools">
      <div class="card"><h2>✨ A story written for you</h2>
        <p class="muted small">${status.ai.configured
          ? 'Claude writes a short story at your level that uses the words you are learning today.'
          : 'Ask a teacher to add a Claude API key in Settings to turn on stories written at your level.'}</p>
        <div class="card-actions">${status.ai.configured ? '<a class="btn primary" href="#/story">Write my story</a>' : '<a class="btn" href="#/settings">Settings</a>'}</div></div>
      <div class="card"><h2>Browse everything</h2>
        <p class="muted small">Search all books, or filter by level, source and how well they fit you.</p>
        <div class="card-actions"><a class="btn" href="#/browse">Browse the library</a><a class="btn ghost" href="#/reading">My reading progress</a></div></div>
    </section>`)) return;
}

async function renderBrowse({ params, paint }) {
  const f = { q: params.get('q') || '', source: params.get('source') || '', fit: params.get('fit') || '',
    cefr: params.get('cefr') || '', sort: params.get('sort') || 'fit' };
  const data = await api(`/api/library?student=${sid()}&${new URLSearchParams(f)}`);
  const opt = (v, label, cur) => `<option value="${v}" ${v === cur ? 'selected' : ''}>${label}</option>`;
  let shown = 60;
  if (!paint(`
    <a href="#/library" class="small">← Library</a>
    <h1 style="margin-top:.4rem">Browse the library</h1>
    <form class="filters" id="filters">
      <input type="search" name="q" placeholder="Title or author" value="${esc(f.q)}" aria-label="Search books">
      <select name="fit" aria-label="Fit">${opt('', 'Any fit', f.fit)}${Object.entries(FIT_LABEL).map(([k, v]) => opt(k, v, f.fit)).join('')}</select>
      <select name="cefr" aria-label="Level">${opt('', 'Any level', f.cefr)}${CEFR_LIST.map((c) => opt(c, c, f.cefr)).join('')}</select>
      <select name="source" aria-label="Source">${opt('', 'All sources', f.source)}${Object.entries(SOURCE_LABEL).map(([k, v]) => opt(k, v + 's', f.source)).join('')}</select>
      <select name="sort" aria-label="Sort">${opt('fit', 'Best fit first', f.sort)}${opt('easy', 'Easiest first', f.sort)}${opt('short', 'Shortest first', f.sort)}${opt('title', 'Title', f.sort)}</select>
    </form>
    <p class="muted small">${data.books.length} books · your level ${esc(data.cefr)} (about ${fmtInt(data.vocab)} words)</p>
    <div id="results"></div>
    <div class="card-actions" id="more-row"></div>`)) return;
  const draw = () => {
    $('#results').innerHTML = data.books.length ? cardRow(data.books.slice(0, shown)) : '<div class="card empty">No books match these filters.</div>';
    $('#more-row').innerHTML = data.books.length > shown ? `<button class="btn" type="button" id="more">Show more (${data.books.length - shown})</button>` : '';
    const more = $('#more');
    if (more) more.onclick = () => { shown += 60; draw(); };
  };
  draw();
  const form = $('#filters');
  const apply = () => { location.hash = '#/browse?' + new URLSearchParams([...new FormData(form)].filter(([, v]) => v)); };
  form.onchange = apply;
  form.onsubmit = (e) => { e.preventDefault(); apply(); };
}

async function renderBook({ arg, paint }) {
  const b = await api(`/api/library/book/${enc(arg)}?student=${sid()}`);
  const next = b.next_unit;
  if (!paint(`
    <a href="#/library" class="small">← Library</a>
    <div class="card" style="margin-top:.5rem">
      <div class="step-title"><h1 style="margin:0">${esc(b.title)}</h1><span class="tag">${esc(b.cefr)}</span>${fitBadge(b.fit)}</div>
      ${b.author ? `<p class="muted">${esc(b.author)}</p>` : ''}
      <p class="muted small">${fmtInt(b.words)} words · ${b.units > 1 ? `${b.units} parts · ` : ''}about ${per100(b.coverage)} new words per 100 for you${b.learning_hits ? ` · ★ ${b.learning_hits} words you are learning` : ''}</p>
      <p class="muted small">${FIT_HELP[b.fit]}</p>
      <div class="card-actions">
        ${next !== null ? `<a class="btn primary" href="#/read/${enc(b.id)}/${next}">${b.done_units ? 'Continue reading' : 'Start reading'}</a>` : '<span class="pill mastered">Finished ✓</span>'}
        ${b.deletable ? '<button class="btn ghost small danger" type="button" id="del-book">Delete</button>' : ''}
      </div>
      <p class="credit">${esc(b.credit)}${b.license ? ` · ${esc(b.license)}` : ''}${b.url ? ` · <a href="${esc(b.url)}" target="_blank" rel="noopener">source</a>` : ''}</p>
    </div>
    ${b.units > 1 ? `<div class="card"><h2>Parts</h2><ol class="unit-list">${b.units_list.map((u) => `
      <li class="${u.done ? 'done' : ''}"><a href="#/read/${enc(b.id)}/${u.idx}">${u.done ? '✓ ' : ''}${esc(u.title)}</a>
        <span class="muted small">${fmtInt(u.words)} words</span>${fitBadge(u.fit)}</li>`).join('')}</ol></div>` : ''}`)) return;
  const del = $('#del-book');
  if (del) del.onclick = async () => {
    if (!confirm('Delete this text from the library?')) return;
    await api(`/api/library/book/${enc(b.id)}`, { method: 'DELETE' });
    location.hash = '#/library';
  };
}

/* ======================================================================= reader */

function sentenceAt(text, pos) {
  const re = /[^.!?]*[.!?]+["'”’)\]]*(?:\s+|$)|[^.!?]+$/g;
  let m;
  while ((m = re.exec(text)) && m[0]) {
    if (pos < m.index + m[0].length) return m[0].trim();
  }
  return text;
}

function paragraphHTML(p, pi) {
  let out = '', pos = 0;
  for (const [s, e, lemma, cls, phrase] of p.w) {
    out += esc(p.t.slice(pos, s));
    out += `<span class="w w-${cls}" data-l="${esc(lemma)}"${phrase ? ` data-ph="${esc(phrase)}"` : ''} data-s="${s}">${esc(p.t.slice(s, e))}</span>`;
    pos = e;
  }
  return `<p class="rp" data-p="${pi}">${out}${esc(p.t.slice(pos))}</p>`;
}

// Split text into pieces of at most `max` characters at sentence ends (the TTS limit is 600).
function speechChunks(text, max = 550) {
  const parts = text.match(/[^.!?]+[.!?]+["'”’)\]]*\s*|[^.!?]+$/g) || [text];
  const out = [];
  let cur = '';
  for (const s of parts) {
    if ((cur + s).length > max && cur) { out.push(cur.trim()); cur = ''; }
    cur += s.length > max ? s.slice(0, max) : s;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}

async function renderRead({ arg, params, paint }) {
  const [bookId, idxStr] = arg.split('/');
  const idx = Number(idxStr || 0);
  const d = await api(`/api/read/${enc(bookId)}/${idx}?student=${sid()}`);
  const prefs = { size: 1.2, learning: true, hard: false, ...store.get('reader', {}) };
  const readHash = `#/read/${enc(bookId)}/${idx}`;
  const prelearn = d.prelearn.map((w) => w.word);
  const showPrelearn = prelearn.length && !d.finished && d.position < 0.05;
  const multi = d.book.units > 1;
  if (!paint(`
    <div class="reader">
      <div class="session-head"><a href="#/book/${enc(bookId)}">← ${esc(d.book.title)}</a>
        <span>${multi ? `Part ${idx + 1} of ${d.book.units}` : ''}</span></div>
      <div class="card reader-head">
        <h1>${esc(d.unit.title || d.book.title)}</h1>
        <div class="meta">${fitBadge(d.fit)}<span class="tag">${esc(d.unit.cefr)}</span>
          <span class="muted small">${fmtInt(d.unit.words)} words · about ${per100(d.coverage)} new words per 100 for you${d.learning_here.length ? ` · <b class="hits">${d.learning_here.length} words you are learning</b>` : ''}</span></div>
        <div class="reader-tools">
          <button class="btn small" type="button" id="read-aloud">${ICON.play} Read aloud</button>
          <label class="check small"><input type="checkbox" id="opt-learning" ${prefs.learning ? 'checked' : ''}> Highlight my words</label>
          <label class="check small"><input type="checkbox" id="opt-hard" ${prefs.hard ? 'checked' : ''}> Show words I may not know</label>
          <span class="size-btns"><button class="chip-btn" type="button" data-size="-1" aria-label="Smaller text">A−</button><button class="chip-btn" type="button" data-size="1" aria-label="Bigger text">A+</button></span>
          <label class="small" id="g-pick" hidden>Grammar <select id="opt-grammar"></select></label>
        </div>
        <p class="small g-note" id="g-note" hidden></p>
      </div>
      ${showPrelearn ? `<div class="card prelearn" id="prelearn">
        <h2>Before you read</h2>
        <p class="muted small">${prelearn.length === 1 ? 'This word is' : `These ${prelearn.length} words are`} probably new for you. Learning ${prelearn.length === 1 ? 'it' : 'them'} first makes the text much easier.</p>
        <div>${prelearn.map((w) => `<a class="chip" href="${wordHref(w)}">${esc(w)}</a>`).join('')}</div>
        <div class="card-actions">
          <a class="btn primary" href="#/study?words=${enc(prelearn.join(','))}&post=1&title=${enc('Words for ' + d.book.title)}&then=${enc(readHash)}">Learn ${prelearn.length === 1 ? 'it' : 'them'} first</a>
          <button class="btn" type="button" id="skip-pre">Start reading</button>
        </div></div>` : ''}
      ${d.target_words.length ? `<p class="muted small">Your target words are marked like <span class="w w-t">this</span>.</p>` : ''}
      <article class="card reader-text ${prefs.learning ? 'show-learning' : ''} ${prefs.hard ? 'show-hard' : ''}" id="text" style="--reader-size:${prefs.size}rem">
        ${d.paragraphs.map(paragraphHTML).join('')}
      </article>
      <div class="card reader-end">
        <p class="muted small">Tap any word to see what it means. Tapped words go to your list for review.</p>
        <button class="btn primary" type="button" id="finish">I finished reading</button>
        ${multi && idx + 1 < d.book.units ? `<a class="btn ghost" href="#/read/${enc(bookId)}/${idx + 1}">Skip to part ${idx + 2}</a>` : ''}
        <p class="credit">${esc(d.book.credit)}${d.book.license ? ` · ${esc(d.book.license)}` : ''}</p>
      </div>
    </div>
    <div class="word-sheet" id="sheet" hidden></div>`)) return;

  const text = $('#text');
  const savePrefs = () => store.set('reader', prefs);
  $('#opt-learning').onchange = (e) => { prefs.learning = e.target.checked; text.classList.toggle('show-learning', prefs.learning); savePrefs(); };
  $('#opt-hard').onchange = (e) => { prefs.hard = e.target.checked; text.classList.toggle('show-hard', prefs.hard); savePrefs(); };
  $$('[data-size]').forEach((b) => { b.onclick = () => {
    prefs.size = Math.min(2, Math.max(0.9, prefs.size + 0.1 * Number(b.dataset.size)));
    text.style.setProperty('--reader-size', prefs.size + 'rem');
    savePrefs();
  }; });
  wireReaderGrammar(text, bookId, idx, params.get('g') || d.grammar);
  const skip = $('#skip-pre');
  if (skip) skip.onclick = () => { $('#prelearn').remove(); text.scrollIntoView({ behavior: 'smooth' }); };
  if (d.position >= 0.05 && !d.finished) {
    requestAnimationFrame(() => window.scrollTo(0, text.offsetTop + d.position * Math.max(0, text.offsetHeight - innerHeight)));
    toast('Welcome back — continuing where you stopped');
  }

  /* ---- reading time: counts only while the page is visible and the student is active */
  const clock = { active: 0, sent: 0, lastInput: Date.now() };
  const position = () => {
    const span = Math.max(1, text.offsetHeight - innerHeight);
    return Math.min(1, Math.max(0, (scrollY - text.offsetTop + innerHeight * 0.3) / span));
  };
  const markInput = () => { clock.lastInput = Date.now(); };
  const report = (beacon = false) => {
    const delta = Math.min(3600, clock.active - clock.sent);
    if (delta < 5 && !beacon) return;
    clock.sent = clock.active;
    const body = { student: sid(), book: bookId, idx, seconds: delta, position: position() };
    if (beacon && navigator.sendBeacon) navigator.sendBeacon('/api/read/progress', new Blob([JSON.stringify(body)], { type: 'application/json' }));
    else api('/api/read/progress', { method: 'POST', body }).catch(() => {});
  };
  const tick = setInterval(() => {
    if (!document.hidden && Date.now() - clock.lastInput < 90_000) clock.active++;
    if (clock.active - clock.sent >= 30) report();
  }, 1000);
  const onHide = () => report(true);
  ['scroll', 'pointerdown', 'keydown'].forEach((ev) => addEventListener(ev, markInput, { passive: true }));
  addEventListener('pagehide', onHide);
  let finished = false;
  state.onLeave = () => {
    clearInterval(tick);
    ['scroll', 'pointerdown', 'keydown'].forEach((ev) => removeEventListener(ev, markInput));
    removeEventListener('pagehide', onHide);
    if (!finished) report(true);
  };

  /* ---- read aloud, paragraph by paragraph */
  const aloud = $('#read-aloud');
  aloud.onclick = async () => {
    if (aloud.classList.contains('playing')) { stopAudio(); return; }
    stopAudio();
    const id = playId;
    aloud.classList.add('playing');
    const paras = $$('.rp', text);
    const first = paras.findIndex((p) => p.getBoundingClientRect().bottom > 80);
    for (const p of paras.slice(Math.max(0, first))) {
      if (id !== playId) break;
      p.classList.add('speaking');
      p.scrollIntoView({ block: 'center', behavior: 'smooth' });
      for (const chunk of speechChunks(p.textContent)) {
        if (id !== playId) break;
        await playClip(chunk);
      }
      p.classList.remove('speaking');
    }
    aloud.classList.remove('playing');
  };

  /* ---- tap a word */
  const sheet = $('#sheet');
  const closeSheet = () => { sheet.hidden = true; $$('.w.tapped', text).forEach((w) => w.classList.remove('tapped')); };
  text.addEventListener('click', async (e) => {
    const w = e.target.closest('.w');
    if (!w) return;
    $$('.w.tapped', text).forEach((x) => x.classList.remove('tapped'));
    w.classList.add('tapped');
    const para = d.paragraphs[Number(w.closest('.rp').dataset.p)];
    const sentence = sentenceAt(para.t, Number(w.dataset.s));
    const key = w.dataset.ph || w.dataset.l;
    const surface = w.textContent;
    sheet.hidden = false;
    sheet.innerHTML = `<div class="ws-head"><b class="ws-word">${esc(key)}</b><button class="icon-btn" type="button" id="ws-close" aria-label="Close">✕</button></div><p class="muted">Looking up…</p>`;
    $('#ws-close').onclick = closeSheet;
    if (!w.classList.contains('w-n')) {
      api('/api/read/lookup', { method: 'POST', body: { student: sid(), book: bookId, idx, word: key, surface, sentence } }).catch(() => {});
    }
    speak(surface);
    let data = null;
    for (const q of [key, surface.toLowerCase()]) {
      try { data = await api(`/api/word?q=${enc(q)}&student=${sid()}`); break; } catch { /* try the next form */ }
    }
    if (sheet.hidden) return;
    if (!data) {
      const name = w.classList.contains('w-n');
      sheet.innerHTML = `<div class="ws-head"><b class="ws-word">${esc(name ? surface : key)}</b>
          <div class="row">${speakBtn(surface)} ${name ? '' : saveBtn(key, false)}<button class="icon-btn" type="button" id="ws-close" aria-label="Close">✕</button></div></div>
        <p class="muted">${name ? 'This looks like a name.' : 'The online dictionary has no entry or is not answering right now. Tap ☆ to save the word and look at it later.'}</p>
        <p class="ws-sent">${marked(sentence.replace(surface, `*${surface}*`))}</p>`;
      $('#ws-close').onclick = closeSheet;
      return;
    }
    const en = data.entry;
    sheet.innerHTML = `
      <div class="ws-head"><div><b class="ws-word">${esc(en.word)}</b> ${en.ipa ? `<span class="ipa">${esc(en.ipa)}</span>` : ''}
        ${en.pos ? `<span class="pos small">${esc(en.pos)}</span>` : ''}</div>
        <div class="row">${speakBtn(en.word)} ${saveBtn(data.key, data.progress.saved)}
        <button class="icon-btn" type="button" id="ws-close" aria-label="Close">✕</button></div></div>
      <p class="ws-def">${esc(en.definition) || '<em>No definition yet.</em>'}</p>
      <p class="ws-sent">${marked(sentence.replace(surface, `*${surface}*`))} ${speakBtn(sentence, 'Listen to the sentence')}</p>
      <div class="row"><span class="status-slot">${pill(data.progress.status)}</span>
        <button class="btn small success" type="button" id="ws-know">I know this word</button>
        <button class="btn small warn" type="button" id="ws-learn">Learn it</button>
        <a class="btn small ghost" href="${wordHref(data.key)}">Full entry →</a></div>`;
    $('#ws-close').onclick = closeSheet;
    const act = async (action, msg) => {
      try {
        const p = await api('/api/progress', { method: 'POST', body: { student: sid(), word: data.key, action } });
        $('.status-slot', sheet).innerHTML = pill(p.status);
        $('.star', sheet)?.classList.toggle('on', p.saved);
        toast(msg);
        refreshStatus();
      } catch (err) { toast(err.message); }
    };
    $('#ws-know').onclick = () => act('know', 'Marked as known');
    $('#ws-learn').onclick = () => act('learning', 'Added to your review');
  });
  state.onKey = (e) => { if (e.key === 'Escape') closeSheet(); };

  $('#finish').onclick = () => {
    finished = true;
    clearInterval(tick);
    stopAudio();
    finishReading({ d, bookId, idx, paint, seconds: clock.active - clock.sent });
  };
}

/* ---------------------------------------------------------------- after reading */

async function finishReading({ d, bookId, idx, paint, seconds }) {
  state.onKey = null;
  let rating = null;
  const [check, extra] = await Promise.all([
    api(`/api/read/${enc(bookId)}/${idx}/check?student=${sid()}`).catch(() => ({ questions: [] })),
    api(`/api/read/${enc(bookId)}/${idx}/questions?student=${sid()}`).catch(() => ({ questions: [] })),
  ]);
  const masked = check.questions;
  const comp = extra.questions;
  const answers = new Map();     // masked question id -> correct
  const compAnswers = new Map();
  const total = masked.length + comp.length;
  if (!paint(`
    <div class="session-head"><a href="#/read/${enc(bookId)}/${idx}">← Back to the text</a><span>${esc(d.book.title)}</span></div>
    <div class="card"><h1>Well done!</h1>
      <h2>How was it?</h2>
      <div class="rating" id="rating">
        <button class="option" type="button" data-r="easy">😌 Too easy</button>
        <button class="option" type="button" data-r="right">🙂 Just right</button>
        <button class="option" type="button" data-r="hard">😣 Too hard</button>
      </div></div>
    ${masked.length ? `<div class="card"><h2>Fill in the missing word</h2>
      <p class="muted small">Like the masked-word game language models learn from: one word is hidden in each sentence from the text. Words you are learning count as a review.</p>
      <ol class="check-list">${masked.map((q) => `<li data-q="${q.id}"><p class="qprompt small-q">${esc(q.prompt).replace('_____', '<span class="blank">_____</span>')}</p>
        <div class="options inline">${q.options.map((o, i) => `<button class="option" type="button" data-i="${i}">${esc(o)}</button>`).join('')}</div></li>`).join('')}</ol></div>` : ''}
    ${comp.length ? `<div class="card"><h2>Did you understand the story?</h2>
      <ol class="check-list">${comp.map((q, qi) => `<li data-c="${qi}"><p class="qprompt small-q">${esc(q.question)}</p>
        <div class="options">${q.options.map((o, i) => `<button class="option" type="button" data-i="${i}">${esc(o)}</button>`).join('')}</div><p class="muted small expl" hidden>${esc(q.explanation)}</p></li>`).join('')}</ol></div>` : ''}
    <div class="card-actions"><button class="btn primary" type="button" id="done" disabled>See my results</button></div>`)) return;

  const ready = () => { $('#done').disabled = !rating || answers.size + compAnswers.size < total; };
  $$('#rating .option').forEach((b) => { b.onclick = () => {
    rating = b.dataset.r;
    $$('#rating .option').forEach((x) => x.classList.toggle('picked', x === b));
    ready();
  }; });
  const wire = (li, correctIndex, store_, key) => {
    $$('.option', li).forEach((b) => { b.onclick = () => {
      if (store_.has(key)) return;
      const ok = Number(b.dataset.i) === correctIndex;
      store_.set(key, ok);
      $$('.option', li).forEach((x, i) => { x.disabled = true; if (i === correctIndex) x.classList.add('correct'); else if (x === b) x.classList.add('wrong'); });
      $('.expl', li)?.removeAttribute('hidden');
      ready();
    }; });
  };
  masked.forEach((q) => wire($(`[data-q="${q.id}"]`), q.answer, answers, q.id));
  comp.forEach((q, qi) => wire($(`[data-c="${qi}"]`), q.answer, compAnswers, qi));
  $('#done').onclick = async () => {
    $('#done').disabled = true;
    const body = {
      student: sid(), book: bookId, idx, seconds: Math.max(0, seconds), rating,
      answers: masked.map((q) => ({ word: q.word, correct: answers.get(q.id) })),
      questions_right: comp.length ? [...compAnswers.values()].filter(Boolean).length : null,
      questions_total: comp.length || null,
    };
    let r;
    try { r = await api('/api/read/finish', { method: 'POST', body }); } catch (err) { toast(err.message); $('#done').disabled = false; return; }
    refreshStatus();
    showReadingResult({ r, d, bookId, idx, paint });
  };
}

function showReadingResult({ r, d, bookId, idx, paint }) {
  const mins = Math.max(1, Math.round(r.seconds / 60));
  const change = r.vocab.after - r.vocab.before;
  const nextCards = [...(r.recommend.continue || []), ...(r.recommend.right || []), ...(r.recommend.challenge || [])]
    .filter((b) => !(b.id === bookId && b.unit === idx)).slice(0, 3);
  paint(`
    <div class="card results">
      <h1>Reading complete</h1>
      <div class="result-stats">
        <div><b>${mins}</b><span>minute${mins === 1 ? '' : 's'}</span></div>
        ${r.wpm ? `<div><b>${r.wpm}</b><span>words / min</span></div>` : ''}
        ${r.check.total ? `<div><b>${r.check.right}/${r.check.total}</b><span>check</span></div>` : ''}
        <div><b>${r.taps.length}</b><span>words looked up</span></div>
      </div>
      <p class="muted">Your reading level: <b>${esc(r.vocab.cefr)}</b>, about ${fmtInt(r.vocab.after)} words
        ${change ? `(${change > 0 ? '+' : ''}${fmtInt(change)})` : ''}.
        ${r.target > (d.target ?? r.target) ? ' Next time you will get a little easier texts.' : r.target < (d.target ?? r.target) ? ' Next time you will get slightly harder texts.' : ''}</p>
      ${r.reviewed.length ? `<p class="muted small">Reviewed in context: ${r.reviewed.map((x) => `${x.correct ? '✓' : '✗'} ${esc(x.word)}`).join(', ')}</p>` : ''}
      ${r.taps.length ? `<h3>Words you looked up</h3><div>${r.taps.map((w) => `<a class="chip" href="${wordHref(w)}">${esc(w)}</a>`).join('')}</div>` : ''}
      <div class="row">
        ${r.taps.length ? `<a class="btn warn" href="#/study?words=${enc(r.taps.join(','))}&post=1&title=${enc('Words from ' + d.book.title)}">Study these words</a>` : ''}
        ${r.next_unit !== null ? `<a class="btn primary" href="#/read/${enc(bookId)}/${r.next_unit}">Next part →</a>` : ''}
        <a class="btn" href="#/library">Library</a>
      </div>
    </div>
    ${nextCards.length ? `<section class="lib-section"><h2>Read next</h2>${cardRow(nextCards, { asUnit: true })}</section>` : ''}`);
}

/* ======================================================================= placement test */

async function renderPlacement({ paint }) {
  if (!paint(`<div class="card"><h1>Find your reading level</h1>
    <p>You will see about 65 words, one at a time. For each one, answer honestly: <b>do you know what it means?</b></p>
    <ul class="muted"><li>Takes about 3 minutes. Press <kbd>1</kbd> for “I know it” and <kbd>2</kbd> for “I don’t”.</li>
      <li>Some words are made up. Saying “I know it” to those lowers your score — so don’t guess.</li>
      <li>The result tells the library which books fit you, and where to start in the word steps.</li></ul>
    <div class="card-actions"><button class="btn primary" type="button" id="go">Start the test</button></div></div>`)) return;
  $('#go').onclick = async () => {
    const { items } = await api('/api/placement');
    const answers = [];
    let i = 0;
    const show = () => {
      if (i >= items.length) return submit();
      const w = items[i].word;
      if (!paint(`<div class="session-head"><a href="#/reading">← Cancel</a><span>${i + 1} / ${items.length}</span></div>
        ${bar({ total: items.length, mastered: i, learning: 0, new: items.length - i }, 'thin')}
        <div class="card flashcard"><div class="headword">${esc(w)}</div>
          <div class="pron">${speakBtn(w)}</div>
          <p class="hint">Do you know what this word means?</p>
          <div class="study-actions"><button class="btn success" type="button" id="yes">I know it <kbd>1</kbd></button>
          <button class="btn warn" type="button" id="no">I don’t <kbd>2</kbd></button></div></div>`)) return;
      if (settings.autoplay) speak(w);
      const answer = (yes) => { answers.push({ word: w, yes }); i++; show(); };
      $('#yes').onclick = () => answer(true);
      $('#no').onclick = () => answer(false);
      state.onKey = (e) => { if (e.key === '1') answer(true); if (e.key === '2') answer(false); };
    };
    const submit = async () => {
      state.onKey = null;
      const r = await api('/api/placement', { method: 'POST', body: { student: sid(), answers } });
      refreshStatus();
      if (!r.saved) {
        paint(`<div class="card results"><h1>Let’s try that again</h1>
          <p class="fb bad">You said “I know it” to ${Math.round(r.false_alarm * 100)}% of the made-up words, so the test can’t tell which words you really know. This result was not saved.</p>
          <p class="muted">Only press “I know it” when you could explain the word or use it in a sentence.</p>
          <div class="row"><button class="btn primary" type="button" onclick="route()">Take the test again</button><a class="btn" href="#/library">Not now</a></div></div>`);
        return;
      }
      paint(`<div class="card results"><h1>Your reading level</h1>
        <div class="score">${esc(r.cefr)}<small>about ${fmtInt(r.vocab)} words</small></div>
        <div class="band-bars">${r.bands.map((b) => `<div title="words ${fmtInt(b.from)}–${fmtInt(b.to)}"><span style="height:${Math.round(b.known * 100)}%"></span></div>`).join('')}</div>
        <p class="muted small">How many words you know in each frequency band, from common (left) to rare (right).</p>
        <p class="muted">The library now picks books where about 98 of 100 words are familiar to you. It keeps adjusting as you read.</p>
        <div class="row"><a class="btn primary" href="#/library">Find a book</a>
          <a class="btn" href="#/level/${enc(r.start_level)}">Word steps: start at ${esc(levelTitle(r.start_level) || r.start_level)}</a></div></div>`);
    };
    show();
  };
}

/* ======================================================================= reading progress */

function sparkline(points, w = 320, h = 70) {
  if (points.length < 2) return '';
  const ys = points.map((p) => Math.log(p.vocab));
  const lo = Math.min(...ys), hi = Math.max(...ys);
  const span = hi - lo || 1;
  const xy = ys.map((y, i) => `${(i / (ys.length - 1)) * (w - 8) + 4},${h - 6 - ((y - lo) / span) * (h - 12)}`);
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" role="img" aria-label="Vocabulary estimate over time"><polyline points="${xy.join(' ')}"/></svg>`;
}

async function renderReadingProfile({ paint }) {
  const p = await api(`/api/reading/profile?student=${sid()}`);
  const bandIdx = CEFR_LIST.indexOf(p.cefr);
  const days = [];
  for (let k = 13; k >= 0; k--) {
    const dt = new Date(); dt.setDate(dt.getDate() - k);
    const key = localDate(dt);
    const row = p.days.find((x) => x.day === key);
    days.push({ key, min: row ? Math.round(row.seconds / 60) : 0 });
  }
  const maxMin = Math.max(p.reading_goal, ...days.map((x) => x.min));
  const opt = (v, label, cur) => `<option value="${v}" ${String(v) === String(cur) ? 'selected' : ''}>${label}</option>`;
  if (!paint(`
    <h1>Reading progress</h1>
    <div class="grid two">
      <section class="card"><h2>Your level</h2>
        <div class="big-number">${esc(p.cefr)}</div>
        <p class="muted small">About ${fmtInt(p.vocab)} English words${p.placement ? ` · level test on ${esc(p.placement.day)}` : ' · no level test yet'}</p>
        <div class="cefr-scale">${CEFR_LIST.map((c, i) => `<span class="${i === bandIdx ? 'on' : i < bandIdx ? 'past' : ''}">${c}</span>`).join('')}</div>
        ${sparkline(p.history)}
        <div class="card-actions"><a class="btn ${p.placement ? '' : 'primary'}" href="#/placement">${p.placement ? 'Retake the level test' : 'Take the level test'}</a></div>
      </section>
      <section class="card"><h2>Last two weeks</h2>
        <div class="day-bars">${days.map((x) => `<div title="${x.key}: ${x.min} min"><span style="height:${Math.round((x.min / maxMin) * 100)}%" class="${x.min >= p.reading_goal ? 'met' : ''}"></span></div>`).join('')}</div>
        <p class="muted small">Daily goal: ${p.reading_goal} minutes · today ${p.today.minutes} min</p>
        <div class="result-stats small-stats">
          <div><b>${fmtInt(p.totals.minutes)}</b><span>minutes</span></div>
          <div><b>${fmtInt(p.totals.words)}</b><span>words read</span></div>
          <div><b>${p.totals.units}</b><span>texts finished</span></div>
          <div><b>${p.totals.check === null ? '–' : Math.round(p.totals.check * 100) + '%'}</b><span>check score</span></div>
        </div>
      </section>
    </div>
    <section class="card"><h2>Recently read</h2>
      ${p.recent.length ? `<ul class="word-list">${p.recent.map((r) => `<li><div class="wl-main"><a class="wl-word" href="#/read/${enc(r.book)}/${r.idx}">${esc(r.title)}</a>
        ${r.unit_title ? `<span class="muted small"> · ${esc(r.unit_title)}</span>` : ''}
        <div class="wl-def">${esc(r.day)} · ${r.taps} looked up${r.check ? ` · check ${r.check[0]}/${r.check[1]}` : ''}${r.wpm ? ` · ${r.wpm} wpm` : ''}</div></div>
        <div class="wl-side">${r.rating ? `<span class="pill ${r.rating === 'hard' ? 'learning' : r.rating === 'easy' ? 'new' : 'mastered'}">${{ easy: 'Too easy', right: 'Just right', hard: 'Too hard' }[r.rating]}</span>` : ''}</div></li>`).join('')}</ul>`
        : '<p class="empty">Nothing yet. <a href="#/library">Pick a book</a> — the first one is the hardest to start!</p>'}
    </section>
    <section class="card"><h2>Reading settings</h2>
      <form id="prefs">
        <label>Age group <select name="age_group">${opt('all', 'Not set', p.age_group)}${opt('kids', 'Child (about 6–12)', p.age_group)}${opt('teens', 'Teenager', p.age_group)}${opt('adults', 'Adult', p.age_group)}</select></label>
        <label>Texts should feel <select name="target_coverage">${[[0.99, 'very easy (1 new word in 100)'], [0.985, 'easy'], [0.98, 'just right (2 in 100)'], [0.975, 'a bit challenging'], [0.97, 'challenging (3 in 100)'], [0.96, 'hard (4 in 100)'], [0.95, 'study reading (5 in 100)']]
          .map(([v, l]) => opt(v, l, [0.99, 0.985, 0.98, 0.975, 0.97, 0.96, 0.95].reduce((a, b) => (Math.abs(b - p.target) < Math.abs(a - p.target) ? b : a)))).join('')}</select></label>
        <label>Daily reading goal <input type="number" name="reading_goal" min="1" max="240" value="${p.reading_goal}" style="width:6rem"> minutes</label>
        <button class="btn primary" type="submit">Save</button>
        <p class="muted small">The comfort setting also moves by itself: “Too hard” ratings and low check scores make your next texts easier.</p>
      </form>
    </section>`)) return;
  $('#prefs').onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    await api(`/api/students/${sid()}/reading`, { method: 'PATCH', body: {
      age_group: f.get('age_group'), target_coverage: Number(f.get('target_coverage')), reading_goal: Number(f.get('reading_goal')) } });
    toast('Saved');
    refreshStatus();
  };
}

/* ======================================================================= AI story maker */

async function renderStoryMaker({ params, paint }) {
  const [d, mine, gram] = await Promise.all([refreshStatus(), api(`/api/mywords?student=${sid()}`),
    api(`/api/grammar?student=${sid()}`).catch(() => ({ points: [] }))]);
  const focus = params.get('g') || '';
  const todays = d.today.words.map((w) => w.key);
  const learning = mine.filter((w) => w.status === 'learning').map((w) => w.key).filter((k) => !todays.includes(k));
  const pick = (k, on) => `<label class="pick"><input type="checkbox" name="w" value="${esc(k)}" ${on ? 'checked' : ''}> ${esc(k)}</label>`;
  const ideas = ['an animal adventure', 'a funny day at school', 'a small mystery', 'a trip to space', 'a football match', 'a kind stranger', 'a lost dog', 'a magic shop'];
  if (!paint(`
    <a href="#/library" class="small">← Library</a>
    <div class="card" style="margin-top:.5rem"><h1>✨ A story written for you</h1>
      <p class="muted">Claude writes an original story for your level (${esc(d.reading.cefr)}). It uses the words you choose below, and almost every other word is one you already know.</p>
      <form id="story-form">
        <label>What should it be about? <input name="topic" maxlength="300" placeholder="Anything you like" style="width:min(100%,28rem)"></label>
        <div>${ideas.map((t) => `<button class="chip-btn idea" type="button">${t}</button>`).join(' ')}</div>
        ${gram.points.length ? `<label>Grammar focus <select name="grammar"><option value="">None</option>${gram.points.map((p) =>
          `<option value="${esc(p.id)}" ${p.id === focus ? 'selected' : ''}>${esc(p.title)} (${esc(p.grammar)})</option>`).join('')}</select></label>` : ''}
        <label>Length <select name="length"><option value="short">Short (about 150 words)</option><option value="medium" selected>Medium (about 300 words)</option><option value="long">Long (about 500 words)</option></select></label>
        ${todays.length ? `<h3>Today's new words</h3><div class="picks">${todays.map((k, i) => pick(k, i < 6)).join('')}</div>` : ''}
        ${learning.length ? `<h3>Words you are learning</h3><div class="picks">${learning.slice(0, 24).map((k) => pick(k, false)).join('')}</div>` : ''}
        <p class="muted small">Up to 12 words. A story takes 20–60 seconds to write.</p>
        <div class="row"><button class="btn primary" type="submit" id="write">Write my story</button><span class="muted small" id="story-msg"></span></div>
      </form></div>`)) return;
  const form = $('#story-form');
  $$('.idea').forEach((b) => { b.onclick = () => { form.topic.value = b.textContent; }; });
  form.onsubmit = async (e) => {
    e.preventDefault();
    const words = $$('input[name=w]:checked', form).map((x) => x.value).slice(0, 12);
    $('#write').disabled = true;
    $('#story-msg').textContent = 'Writing your story… (this can take up to a minute)';
    try {
      const g = form.grammar?.value || null;
      const r = await api('/api/ai/story', { method: 'POST', body: { student: sid(), topic: form.topic.value, length: form.length.value, words, grammar: g } });
      location.hash = `#/read/${enc(r.id)}/0${g ? `?g=${enc(g)}` : ''}`;
    } catch (err) {
      $('#story-msg').textContent = err.message;
      $('#write').disabled = false;
    }
  };
}

/* ======================================================================= pieces used by app.js pages */

// Home page card: what to read today.
function todayReadingCard(rec, reading) {
  const t = rec?.today;
  const goalDone = reading.minutes >= reading.goal;
  return `<section class="card">
    <h2>Today's reading</h2>
    <p class="muted small">${reading.minutes} of ${reading.goal} minutes${goalDone ? ' · goal reached 🎉' : ''} · level ${esc(reading.cefr)}</p>
    ${t ? `<a class="today-book" href="#/read/${enc(t.id)}/${t.unit}"><b>${esc(t.title)}</b>
        <span class="muted small">${t.units > 1 ? `part ${t.unit + 1} · ` : ''}${Math.max(1, Math.round(t.unit_words / 120))} min · ${per100(t.unit_coverage)} new words / 100</span></a>`
      : '<p class="muted small">Download the free library in Settings to get book suggestions.</p>'}
    <div class="card-actions">${t ? `<a class="btn primary" href="#/read/${enc(t.id)}/${t.unit}">Read now</a>` : ''}
      <a class="btn ghost" href="#/library">Library</a>
      ${reading.placed ? '' : '<a class="btn" href="#/placement">Find my level</a>'}</div>
  </section>`;
}

// Word page: where the student met the word, and stories that use it.
async function wordContextsHTML(key) {
  const c = await api(`/api/word/contexts?q=${enc(key)}&student=${sid()}`);
  if (!c.seen.length && !c.library.length) return '';
  return `<section class="card contexts">
    ${c.seen.length ? `<h3>Where you met it</h3><ul class="examples">${c.seen.map((s) => `<li><span>${marked(s.sentence.replace(s.surface, `*${s.surface}*`))}
      ${s.title ? `<a class="muted small" href="#/read/${enc(s.book_id)}/${s.idx}"> — ${esc(s.title)}</a>` : ''}</span>${speakBtn(s.sentence)}</li>`).join('')}</ul>` : ''}
    ${c.library.length ? `<h3>Read it in a story</h3><ul class="examples">${c.library.map((s) => `<li><span>${marked(s.sentence)}
      <a class="small" href="#/read/${enc(s.book)}/${s.idx}"> — ${esc(s.title)}${s.unit_title ? `, ${esc(s.unit_title)}` : ''}</a> ${fitBadge(s.fit)}</span>${speakBtn(s.sentence)}</li>`).join('')}</ul>` : ''}
  </section>`;
}

// Settings page sections for the library and AI stories.
function libraryStatusHTML(status) {
  const c = (k) => status.counts[k]?.books || 0;
  const jobLine = (k) => {
    const j = status.jobs[k];
    if (!j) return '';
    if (j.state === 'running') return `<span class="muted small">Downloading… ${j.total ? `${j.done}/${j.total}` : ''}</span>`;
    if (j.state === 'error') return `<span class="small" style="color:var(--bad)">${esc(j.error)}</span>`;
    return '<span class="small" style="color:var(--ok)">Done ✓</span>';
  };
  const busy = (k) => status.jobs[k]?.state === 'running' ? 'disabled' : '';
  return `<ul class="custom-list">
    <li><span style="flex:1"><b>Storybooks</b> — about 760 short stories for beginners (African Storybook, Pratham Books StoryWeaver; CC BY licences)<br><span class="muted small">${c('storybook')} in the library</span></span>
      ${jobLine('storybooks')}<button class="btn small" type="button" data-import="storybooks" ${busy('storybooks')}>${c('storybook') ? 'Update' : 'Download'}</button></li>
    <li><span style="flex:1"><b>Classics</b> — ${status.gutenberg_titles} public-domain books from Project Gutenberg, split into chapters (one time, a few minutes)<br><span class="muted small">${c('gutenberg')} in the library</span></span>
      ${jobLine('gutenberg')}<button class="btn small" type="button" data-import="gutenberg" ${busy('gutenberg')}>${c('gutenberg') ? 'Update' : 'Download'}</button></li>
    <li><span style="flex:1"><b>Teachers' texts</b><br><span class="muted small">${c('teacher')} in the library</span></span></li>
  </ul>`;
}

function librarySettingsHTML(status) {
  const ai = status.ai;
  return `
    <section class="card" id="lib-settings">
      <h2>Reading library</h2>
      <p class="muted small">Free books are downloaded once and then work offline. Every book is leveled automatically for each student.</p>
      <div id="lib-status">${libraryStatusHTML(status)}</div>
      <h3>Add a text</h3>
      <form id="text-form">
        <label>Title <input name="title" required maxlength="120" style="width:min(100%,24rem)"></label>
        <label>Author / source <input name="author" maxlength="120" style="width:min(100%,24rem)"></label>
        <label>For <select name="audience"><option value="all">All ages</option><option value="kids">Children</option><option value="teens">Teens and adults</option></select></label>
        <label>Text<textarea name="text" rows="8" required placeholder="Paste a story or article you have the right to use. Leave a blank line between paragraphs."></textarea></label>
        <div class="row"><button class="btn primary" type="submit">Add to library</button><span class="muted small" id="text-msg"></span></div>
      </form>
    </section>
    <section class="card" id="ai-settings">
      <h2>AI stories (Claude)</h2>
      <p class="muted small">${ai.configured
        ? `Connected${ai.key_source === 'settings' ? ` with key ${esc(ai.key_hint)}` : ' with the key from the environment'}. Students can ask for stories written at their level.`
        : 'Add an Anthropic API key to let Claude write stories at each student’s level (get one at console.anthropic.com). The key is stored on this computer in userdata/ai.json.'}</p>
      <form id="ai-form" class="row">
        <input name="api_key" type="password" autocomplete="off" placeholder="${ai.key_source === 'settings' ? 'Replace the saved key' : 'sk-ant-…'}" style="flex:1;min-width:12rem">
        <select name="model">${Object.entries(ai.models).map(([k, v]) => `<option value="${k}" ${k === ai.model ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select>
        <button class="btn primary" type="submit">Save</button>
        ${ai.key_source === 'settings' ? '<button class="btn ghost small danger" type="button" id="ai-clear">Remove key</button>' : ''}
      </form>
    </section>`;
}

// Refresh the download list every 1.5 s while an import runs (only that list, so forms keep their text).
async function pollImports() {
  if (!$('#lib-status')) return;
  const s = await api('/api/library/status');
  if (!$('#lib-status')) return;
  $('#lib-status').innerHTML = libraryStatusHTML(s);
  wireImports();
  const running = Object.values(s.jobs).some((j) => j.state === 'running');
  if (running) setTimeout(pollImports, 1500);
  else if (Object.keys(s.jobs).length) toast(Object.values(s.jobs).some((j) => j.state === 'error') ? 'A download stopped — see the message' : 'Library updated');
}

function wireImports() {
  $$('[data-import]').forEach((b) => { b.onclick = async () => {
    b.disabled = true;
    await api(`/api/library/import/${b.dataset.import}`, { method: 'POST' });
    pollImports();
  }; });
}

function wireLibrarySettings(status) {
  wireImports();
  if (Object.values(status.jobs).some((j) => j.state === 'running')) pollImports();
  const tf = $('#text-form');
  tf.onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(tf);
    $('#text-msg').textContent = 'Adding…';
    try {
      const r = await api('/api/library/texts', { method: 'POST', body: Object.fromEntries(f) });
      location.hash = `#/book/${enc(r.id)}`;
    } catch (err) { $('#text-msg').textContent = err.message; }
  };
  const af = $('#ai-form');
  af.onsubmit = async (e) => {
    e.preventDefault();
    try {
      const s = await api('/api/ai/config', { method: 'POST', body: { api_key: af.api_key.value || null, model: af.model.value } });
      toast(s.configured ? 'AI settings saved' : 'Saved — add an API key to turn on AI stories');
      route();
    } catch (err) { toast(err.message); }
  };
  const clear = $('#ai-clear');
  if (clear) clear.onclick = async () => { await api('/api/ai/config', { method: 'POST', body: { clear_key: true } }); route(); };
}
