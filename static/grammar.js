'use strict';

/* ======================================================================= grammar
   Lessons organized by what you do with English, five practice types (situation, gap, fix,
   order, listen & write), spaced review, grammar in the student's books, and write-your-own
   with Claude feedback. Uses the helpers in app.js and reading.js. */

const GQLABEL = {
  situation: 'Which one fits?',
  gap: 'Choose the words that complete the sentence',
  fix: 'Tap the mistake',
  order: 'Put the words in order',
  dictation: 'Listen and write what you hear',
};

// Same rule as grammar.norm_answer on the server.
const normAnswer = (s) => String(s ?? '').toLowerCase().replace(/’/g, "'").replace(/[^a-z0-9'\s-]/g, '').replace(/\s+/g, ' ').trim();

const boxDots = (box) => `<span class="box-dots" title="Review box ${box} of 5">${[1, 2, 3, 4, 5].map((b) =>
  `<i class="${b <= box ? (box >= 4 ? 'm' : 'l') : ''}"></i>`).join('')}</span>`;

function backIn(due) {
  const days = Math.round((new Date(due + 'T00:00') - new Date(localDate() + 'T00:00')) / 86400000);
  return days <= 0 ? 'back today' : days === 1 ? 'back tomorrow' : `back in ${days} days`;
}

async function renderGrammar(ctx) {
  const [sub, ...rest] = ctx.arg.split('/');
  const id = rest.join('/');
  if (sub === 'point' && id) return renderGrammarPoint({ ...ctx, id });
  if (sub === 'practice' && id) return runGrammar({ ...ctx, point: id });
  if (sub === 'review') return runGrammar({ ...ctx, point: null });
  return renderGrammarHome(ctx);
}

/* ---------------------------------------------------------------- overview */

async function renderGrammarHome({ paint }) {
  const g = await api(`/api/grammar?student=${sid()}`);
  const nextId = g.next?.id;
  const gcard = (p) => `<a class="g-card ${p.id === nextId ? 'rec' : ''}" href="#/grammar/point/${enc(p.id)}">
      <div class="g-card-top"><span class="tag">${esc(p.band)}</span>${p.id === nextId ? '<span class="badge-rec">Next step</span>' : pill(p.status)}</div>
      <div class="g-card-title">${esc(p.title)}</div>
      <div class="g-card-sub">${esc(p.grammar)}</div>
      ${p.status !== 'new' ? `<div class="g-card-foot">${boxDots(p.box)}${dueLabel(p.due)}</div>` : ''}
    </a>`;
  paint(`
    <h1>Grammar for real life</h1>
    <p class="muted">Each lesson is about something you <b>do</b> with English: tell a story, ask politely, make plans.
      Learn it in a few minutes, find it in real books, use it to write about your own life, and it comes back for
      review just before you forget it.</p>
    <div class="grid two" style="margin-top:1rem">
      <section class="card">
        <h2>Today's grammar review</h2>
        <div class="big-number">${g.due}</div>
        <p class="muted small">${g.due ? `grammar point${g.due === 1 ? ' is' : 's are'} ready — a short mixed quiz.`
          : 'Nothing due. Points you practise come back after 1, 3, 7, 14 and 30 days.'}</p>
        <div class="card-actions"><a class="btn ${g.due ? 'primary' : ''}" href="#/grammar/review" ${g.due ? '' : 'aria-disabled="true"'}>Start review</a></div>
      </section>
      <section class="card">
        <h2>Next step</h2>
        ${g.next ? `<a class="today-book" href="#/grammar/point/${enc(g.next.id)}"><b>${esc(g.next.title)}</b>
            <span class="muted small">${esc(g.next.grammar)} · ${esc(g.next.band)}</span></a>
          <div class="card-actions"><a class="btn primary" href="#/grammar/point/${enc(g.next.id)}">Start lesson</a></div>`
          : '<p class="muted">You have started every point. Keep reviewing to master them!</p>'}
        <p class="muted small" style="margin-top:.8rem">${g.started} of ${g.total} started · ${g.mastered} mastered</p>
        ${bar({ total: g.total, mastered: g.mastered, learning: g.started - g.mastered, new: g.total - g.started }, 'thin')}
      </section>
    </div>
    ${g.units.map((u) => `<section class="g-unit">
      <h2>${esc(u.title)}</h2><p class="muted small">${esc(u.description)}</p>
      <div class="g-grid">${g.points.filter((p) => p.unit === u.id).map(gcard).join('')}</div>
    </section>`).join('')}`);
}

// Home page card.
function grammarHomeCard(g) {
  if (!g) return '';
  return `<section class="card">
    <h2>Grammar</h2>
    <p class="muted small">${g.started} of ${g.total} points started · ${g.mastered} mastered${g.due ? ` · <b class="hits">${g.due} to review</b>` : ''}</p>
    ${g.next ? `<a class="today-book" href="#/grammar/point/${enc(g.next.id)}"><b>${esc(g.next.title)}</b>
      <span class="muted small">Next: ${esc(g.next.grammar)} · ${esc(g.next.band)}</span></a>` : ''}
    <div class="card-actions">
      ${g.due ? '<a class="btn primary" href="#/grammar/review">Review grammar</a>'
        : g.next ? `<a class="btn primary" href="#/grammar/point/${enc(g.next.id)}">Start lesson</a>` : ''}
      <a class="btn ghost" href="#/grammar">All grammar</a>
    </div>
  </section>`;
}

/* ---------------------------------------------------------------- lesson */

function writingCheckHTML(text, r) {
  if (r.error) return `<div class="fb tip"><strong>Saved, but not checked.</strong><p>${esc(r.error)}</p></div>`;
  if (!r.check) {
    return `<div class="fb ok"><strong>Saved!</strong>
      <p>Now read it aloud ${speakBtn(text)} and compare it with the examples and the <i>Watch out</i> list above.</p></div>`;
  }
  const c = r.check;
  const good = c.correct && c.uses_target;
  return `<div class="fb ${good ? 'ok' : 'tip'}">
    <strong>${good ? 'Great — that is correct!' : c.correct ? 'Correct — now try to use the target grammar' : 'Nearly there!'}</strong>
    <p>${esc(c.feedback)}</p>
    ${c.fixes.length ? `<ul class="g-fixes">${c.fixes.map((f) =>
      `<li><span class="g-x">${esc(f.wrong)}</span> → <b class="g-ok">${esc(f.right)}</b> <span class="muted small">${esc(f.why)}</span></li>`).join('')}</ul>` : ''}
    ${c.corrected && c.corrected !== text ? `<p class="g-full"><span class="muted small">Better:</span> <span>${esc(c.corrected)}</span> ${speakBtn(c.corrected)}</p>` : ''}
  </div>`;
}

function writingHistoryHTML(list) {
  if (!list.length) return '';
  return `<h3>Your sentences</h3><ul class="g-history">${list.map((w) => `<li>
      <div>${esc(w.text)} ${speakBtn(w.corrected || w.text)}</div>
      ${w.corrected && w.corrected !== w.text ? `<div class="g-ok small">→ ${esc(w.corrected)}</div>` : ''}
      <div class="muted small">${esc(w.day)}${w.ok === 1 ? ' · ✓ checked' : ''}</div></li>`).join('')}</ul>`;
}

async function renderGrammarPoint({ id, paint }) {
  const d = await api(`/api/grammar/point/${enc(id)}?student=${sid()}`);
  const p = d.point;
  const pr = d.progress;
  if (!paint(`
    <a href="#/grammar" class="small">← Grammar</a>
    <article class="card g-lesson" style="margin-top:.5rem">
      <div class="meta" style="margin-top:0"><span class="tag">${esc(p.band)}</span>${pill(pr.status)}
        <span class="muted small">${esc(d.unit.title)}</span></div>
      <h1 class="g-title">${esc(p.title)}</h1>
      <p class="g-name">${esc(p.grammar)}</p>
      <p class="g-use">${esc(p.use)}</p>
      ${pr.status !== 'new' ? `<p class="muted small">${boxDots(pr.box)} Last score ${Math.round(100 * (pr.score || 0))}% · ${dueLabel(pr.due)}</p>` : ''}
      <div class="card-actions">
        <a class="btn primary" href="#/grammar/practice/${enc(p.id)}">Practise (${d.questions} questions)</a>
        <button class="btn ghost" type="button" data-speak-all="${esc(JSON.stringify(p.examples.map(plain)))}">${ICON.play} Listen to the examples</button>
      </div>
    </article>
    <section class="card">
      <h2>How it works</h2>
      <ul class="g-form">${p.form.map((f) => `<li>${esc(f)}</li>`).join('')}</ul>
      <h3>Examples</h3>
      <ul class="examples">${p.examples.map((s) => `<li><span>${marked(s)}</span>${speakBtn(s, 'Listen to the example')}</li>`).join('')}</ul>
      <h3>Watch out</h3>
      <ul class="g-mistakes">${p.mistakes.map((m) => `<li>
        <div class="g-x">✗ ${esc(m.wrong)}</div>
        <div class="g-ok"><span>✓ ${marked(m.right)}</span> ${speakBtn(m.right)}</div>
        <div class="muted small">${esc(m.why)}</div></li>`).join('')}</ul>
    </section>
    <section class="card" id="g-books"><h2>Find it in your books</h2><p class="muted small">Looking in the library for sentences at your level…</p></section>
    <section class="card g-mission">
      <h2>Use it for real</h2>
      <p class="g-task">${esc(p.mission)}</p>
      <form id="g-write">
        <textarea id="g-text" rows="4" maxlength="1000" placeholder="Write about your own life…" aria-label="Your sentences"></textarea>
        <div class="row"><button class="btn primary" type="submit">${d.ai ? 'Check my sentences' : 'Save my sentences'}</button>
          <span class="muted small" id="g-msg">${d.ai ? 'Claude checks your grammar and gives one tip.'
            : 'Add a Claude API key in <a href="#/settings">Settings</a> to get feedback.'}</span></div>
      </form>
      <div id="g-check"></div>
      <div id="g-history">${writingHistoryHTML(d.writing)}</div>
      ${d.ai ? `<p class="muted small">Want more? <a href="#/story?g=${enc(p.id)}">Get an AI story full of this grammar →</a></p>` : ''}
    </section>
    <nav class="g-nav">
      ${d.prev ? `<a href="#/grammar/point/${enc(d.prev.id)}">← ${esc(d.prev.title)}</a>` : '<span></span>'}
      ${d.next ? `<a href="#/grammar/point/${enc(d.next.id)}">${esc(d.next.title)} →</a>` : ''}
    </nav>`)) return;

  api(`/api/grammar/examples/${enc(p.id)}?student=${sid()}`).then((r) => {
    const slot = $('#g-books');
    if (!slot) return;
    slot.innerHTML = '<h2>Find it in your books</h2>' + (r.examples.length
      ? `<p class="muted small">Real sentences from texts at your level. Open one to read it with this grammar highlighted.</p>
        <ul class="examples">${r.examples.map((x) => `<li><span>${marked(x.sentence)}
          <a class="small" href="#/read/${enc(x.book)}/${x.idx}?g=${enc(p.id)}">— ${esc(x.title)}${x.unit_title ? `, ${esc(x.unit_title)}` : ''}</a>
          ${fitBadge(x.fit)}</span>${speakBtn(x.sentence)}</li>`).join('')}</ul>`
      : '<p class="muted small">No examples found yet. Download the free storybooks and classics in <a href="#/settings">Settings</a> and real sentences will appear here.</p>');
  }).catch(() => { const slot = $('#g-books'); if (slot) slot.remove(); });

  $('#g-write').onsubmit = async (e) => {
    e.preventDefault();
    const text = $('#g-text').value.trim();
    if (!text) return;
    const btn = $('button[type=submit]', e.target);
    btn.disabled = true;
    $('#g-msg').textContent = d.ai ? 'Checking…' : 'Saving…';
    try {
      const r = await api('/api/grammar/write', { method: 'POST', body: { student: sid(), point: p.id, text } });
      $('#g-check').innerHTML = writingCheckHTML(text, r);
      $('#g-msg').textContent = r.check ? 'Edit your text and check again if you like.' : '';
      d.writing.unshift({ text, corrected: r.check?.corrected || '', day: localDate(), ok: r.check ? Number(r.check.correct && r.check.uses_target) : null });
      $('#g-history').innerHTML = writingHistoryHTML(d.writing.slice(0, 5));
      refreshStatus();
    } catch (err) { $('#g-msg').textContent = err.message; }
    btn.disabled = false;
  };
}

/* ---------------------------------------------------------------- listen & write */

const SPECIAL_CONTRACTIONS = { "can't": ['cannot', 'can not'], "won't": ['will not'], "shan't": ['shall not'], "let's": ['let us'] };
const CLITIC_EXPANSIONS = [["n't", [' not']], ["'m", [' am']], ["'re", [' are']], ["'s", [' is', ' has']],
  ["'ve", [' have']], ["'ll", [' will']], ["'d", [' would', ' had']]];

// "nine" and "9" are both fine when writing what you hear.
const NUMBER_WORDS = Object.fromEntries(('zero one two three four five six seven eight nine ten eleven twelve thirteen '
  + 'fourteen fifteen sixteen seventeen eighteen nineteen twenty').split(' ').map((w, i) => [w, String(i)]));
const sameWord = (w) => NUMBER_WORDS[w] ?? w;

function expansions(w) {
  if (SPECIAL_CONTRACTIONS[w]) return SPECIAL_CONTRACTIONS[w];
  for (const [end, alts] of CLITIC_EXPANSIONS) {
    if (w.endsWith(end) && w.length > end.length) return alts.map((a) => w.slice(0, -end.length) + a);
  }
  return [];
}

// Compare what the student typed with the sentence. Every word of the grammar part (the
// *marked* words) must be right, and at least 80% of all words.
function checkDictation(it, typed) {
  const marks = [];
  let plainPos = 0, open = -1;
  for (const ch of it.marked) {
    if (ch === '*') {
      if (open < 0) open = plainPos; else { marks.push([open, plainPos]); open = -1; }
    } else plainPos++;
  }
  const exp = [...it.sentence.matchAll(/\S+/g)]
    .map((m) => ({ raw: m[0], w: sameWord(normAnswer(m[0])), g: marks.some(([a, b]) => m.index < b && m.index + m[0].length > a) }))
    .filter((t) => t.w);
  let t = normAnswer(typed);
  for (const tok of exp) {       // "I am" for "I'm" is fine
    if (!tok.w.includes("'")) continue;
    for (const alt of expansions(tok.w)) {
      const re = new RegExp(`(^| )${alt.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?= |$)`);
      if (re.test(t)) { t = t.replace(re, `$1${tok.w}`); break; }
    }
  }
  const got = t.split(' ').filter(Boolean).map(sameWord);
  const n = exp.length, m = got.length;
  const L = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      L[i][j] = exp[i].w === got[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    }
  }
  const hit = new Set();
  for (let i = 0, j = 0; i < n && j < m;) {
    if (exp[i].w === got[j]) { hit.add(i); i++; j++; } else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
  }
  const correct = exp.every((tok, i) => !tok.g || hit.has(i)) && hit.size >= 0.8 * n;
  const html = `<p class="g-dict">${exp.map((tok, i) =>
    `<span class="${hit.has(i) ? 'hit' : 'miss'}${tok.g ? ' gw' : ''}">${esc(tok.raw)}</span>`).join(' ')} ${speakBtn(it.sentence)}</p>
    <p class="muted small">You got ${hit.size} of ${n} words${exp.some((x, i) => x.g && !hit.has(i)) ? ' — listen again for the grammar words in bold' : ''}.</p>`;
  return { correct, html };
}

/* ---------------------------------------------------------------- practice & review */

function grammarBodyHTML(it) {
  const options = () => `<div class="options">${it.options.map((o, i) =>
    `<button class="option" type="button" data-i="${i}"><kbd>${i + 1}</kbd><span>${esc(o)}</span></button>`).join('')}</div>`;
  const tiles = (list) => list.map((t, i) => `<button class="tile" type="button" data-i="${i}">${esc(t)}</button>`).join('');
  if (it.type === 'situation') return `<p class="g-context">${esc(it.context)}</p>${options()}`;
  if (it.type === 'gap') return `<p class="qprompt">${esc(it.prompt).replace('_____', '<span class="blank">_____</span>')}</p>${options()}`;
  if (it.type === 'fix') return `<p class="muted small">One part of this sentence is wrong. Tap it.</p><div class="tiles" id="fix">${tiles(it.tokens)}</div>`;
  if (it.type === 'order') {
    return `<div class="order-line" id="line" aria-label="Your sentence"></div>
      <div class="tiles" id="pool">${tiles(it.tiles)}</div>
      <div class="row"><button class="btn primary" id="check" type="button" disabled>Check</button>
        <button class="btn ghost small" id="clear" type="button">Start again</button></div>`;
  }
  return `<div class="listen-row"><button class="btn" type="button" data-speak="${esc(it.sentence)}">${ICON.speaker} Play again</button>${slowBtn(it.sentence)}</div>
    <form class="spell-form" autocomplete="off"><input id="dict" type="text" spellcheck="false" autocapitalize="off" autocorrect="off"
      placeholder="Type the whole sentence" aria-label="What you hear"><button class="btn primary" type="submit">Check</button></form>`;
}

async function runGrammar({ point, paint }) {
  const q = new URLSearchParams({ student: sid() });
  if (point) q.set('point', point);
  const data = await api(`/api/grammar/session?${q}`);
  const back = point ? `#/grammar/point/${enc(point)}` : '#/grammar';
  if (!data.items.length) {
    paint(`<div class="card empty"><h2>No grammar to review right now 🎉</h2>
      <p>Points come back here when they are due. Start a new lesson to add one.</p>
      <div class="row" style="justify-content:center"><a class="btn primary" href="#/grammar">Grammar lessons</a></div></div>`);
    return;
  }
  const heading = point ? `Practice · ${esc(data.points[point].title)}` : 'Grammar review';
  const total = data.items.length;
  const queue = data.items.map((it) => ({ ...it, retry: false }));
  const results = new Map();     // point -> [{ q, correct }], first tries only
  let pos = 0, graded = 0;

  function show() {
    if (pos >= queue.length) return finish();
    const it = queue[pos];
    if (!paint(`
      <div class="session-head"><a href="${back}">← ${heading}</a><span>${it.retry ? 'Second chance' : `${graded + 1} / ${total}`}</span></div>
      <div class="progress thin"><span class="seg primary" style="width:${pct(graded, total)}%"></span></div>
      <div class="card g-q">
        <div class="qtype">${GQLABEL[it.type]}</div>
        ${grammarBodyHTML(it)}
        <div id="feedback"></div>
      </div>`)) return;
    wire(it);
  }

  function wire(it) {
    if (it.options) {
      $$('.option').forEach((b) => { b.onclick = () => answer(it, Number(b.dataset.i) === it.answer, Number(b.dataset.i)); });
      state.onKey = (e) => {
        const n = Number(e.key);
        if (n >= 1 && n <= it.options.length) answer(it, n - 1 === it.answer, n - 1);
      };
    } else if (it.type === 'fix') {
      $$('#fix .tile').forEach((b) => { b.onclick = () => answer(it, it.wrong.includes(Number(b.dataset.i)), Number(b.dataset.i)); });
    } else if (it.type === 'order') {
      const line = $('#line'), check = $('#check');
      const update = () => { check.disabled = $$('#pool .tile:not([hidden])').length > 0; };
      $$('#pool .tile').forEach((b) => {
        b.onclick = () => {
          b.hidden = true;
          const t = document.createElement('button');
          t.type = 'button';
          t.className = 'tile';
          t.textContent = b.textContent;
          t.onclick = () => { if (it.answered) return; t.remove(); b.hidden = false; update(); };
          line.append(t);
          update();
        };
      });
      $('#clear').onclick = () => { line.innerHTML = ''; $$('#pool .tile').forEach((b) => { b.hidden = false; }); update(); };
      check.onclick = () => {
        const built = $$('.tile', line).map((t) => t.textContent).join(' ');
        answer(it, it.answers.includes(normAnswer(built)), built);
      };
    } else if (it.type === 'dictation') {
      const input = $('#dict');
      input.focus();
      speak(it.sentence);
      $('.spell-form').onsubmit = (e) => {
        e.preventDefault();
        if (!input.value.trim() || input.disabled) return;
        answer(it, null, input.value);
      };
    }
  }

  function answer(it, correct, chosen) {
    if (it.answered) return;
    it.answered = true;
    state.onKey = null;
    let extra = '';
    if (it.options) {
      $$('.option').forEach((b, i) => {
        b.disabled = true;
        if (i === it.answer) b.classList.add('correct');
        else if (i === chosen) b.classList.add('wrong');
      });
    } else if (it.type === 'fix') {
      $$('#fix .tile').forEach((b, i) => {
        b.disabled = true;
        if (it.wrong.includes(i)) b.classList.add(correct ? 'found' : 'mistake');
        else if (i === chosen) b.classList.add('picked');
      });
    } else if (it.type === 'order') {
      $('#line').classList.add(correct ? 'correct' : 'wrong');
      $$('.tile').forEach((b) => { b.disabled = true; });
      $('#check').disabled = true;
      $('#clear').disabled = true;
    } else if (it.type === 'dictation') {
      const r = checkDictation(it, chosen);
      correct = r.correct;
      extra = r.html;
      const input = $('#dict');
      input.disabled = true;
      input.classList.add(correct ? 'correct' : 'wrong');
    }
    if (!it.retry) {
      graded++;
      if (!results.has(it.point)) results.set(it.point, []);
      results.get(it.point).push({ q: it.qid, correct });
      if (!correct) queue.push({ ...it, retry: true, answered: false });
    }
    const pt = data.points[it.point];
    const full = { situation: it.options?.[it.answer], gap: it.full, fix: it.corrected, order: it.answer_text, dictation: it.marked }[it.type] || '';
    $('#feedback').innerHTML = `
      <div class="fb ${correct ? 'ok' : 'bad'}">
        <strong>${correct ? 'Correct!' : 'Not quite.'}</strong>
        ${extra}
        ${it.type === 'order' && !correct ? `<p class="muted small">You made: ${esc(chosen)}</p>` : ''}
        ${it.type === 'dictation' ? '' : `<p class="g-full"><span>${marked(full)}</span> ${speakBtn(full)}</p>`}
        ${it.why ? `<p class="small">${esc(it.why)}</p>` : ''}
        <p class="muted small">${esc(pt.grammar)} · <a href="#/grammar/point/${enc(pt.id)}">${esc(pt.title)}</a></p>
        <button class="btn primary" id="next" type="button">Next <kbd>Enter</kbd></button>
      </div>`;
    $('#next').onclick = () => { pos++; show(); };
    $('#next').focus();
    if (settings.autoplay) speak(full);
  }

  async function finish() {
    const answers = [...results.values()].flat();
    const right = answers.filter((a) => a.correct).length;
    let saved = [];
    try {
      saved = (await api('/api/grammar/result', { method: 'POST', body: {
        student: sid(), results: [...results].map(([p, list]) => ({ point: p, answers: list })) } })).results;
    } catch { toast('Could not save your results'); }
    refreshStatus();
    paint(`<div class="card results">
      <h1>${point ? 'Practice complete' : 'Review complete'}</h1>
      <div class="score">${right}/${answers.length}<small>${Math.round(pct(right, answers.length))}%</small></div>
      <ul class="result-list">${saved.map((r) => `<li class="${r.right / r.total >= 0.8 ? 'ok' : r.right / r.total < 0.5 ? 'bad' : ''}">
        <span>${r.right}/${r.total}</span><a href="#/grammar/point/${enc(r.point)}">${esc(data.points[r.point].title)}</a>
        <span class="muted small" style="margin-left:auto">${backIn(r.due)}</span></li>`).join('')}</ul>
      <p class="muted">A score of 80% or more moves a point up: it comes back after 1, 3, 7, 14, then 30 days.
        Points you found hard come back tomorrow.</p>
      <div class="row">
        ${point ? `<a class="btn" href="#/grammar/point/${enc(point)}">Back to the lesson</a>` : ''}
        <a class="btn primary" href="#/grammar">Grammar home</a>
      </div></div>`);
  }

  show();
}

/* ---------------------------------------------------------------- reader: highlight a grammar point */

async function wireReaderGrammar(textEl, bookId, idx, initial) {
  let scan;
  try { scan = await api(`/api/grammar/scan?student=${sid()}&book=${enc(bookId)}&idx=${idx}`); } catch { return; }
  const pick = $('#g-pick'), sel = $('#opt-grammar'), note = $('#g-note');
  if (!pick || !scan.points.length) return;
  sel.innerHTML = '<option value="">Off</option>' + scan.points.map((p) =>
    `<option value="${esc(p.id)}">${esc(p.grammar)} (${p.count})</option>`).join('');
  pick.hidden = false;
  const apply = (id) => {
    $$('.w.g-on', textEl).forEach((w) => w.classList.remove('g-on'));
    const byPara = new Map();
    for (const [pi, s, e] of scan.spans[id] || []) {
      if (!byPara.has(pi)) byPara.set(pi, []);
      byPara.get(pi).push([s, e]);
    }
    for (const [pi, list] of byPara) {
      $$(`.rp[data-p="${pi}"] .w`, textEl).forEach((w) => {
        const s = Number(w.dataset.s), e = s + w.textContent.length;
        if (list.some(([a, b]) => s < b && e > a)) w.classList.add('g-on');
      });
    }
    const pt = scan.points.find((p) => p.id === id);
    note.hidden = !pt;
    if (pt) {
      note.innerHTML = `<span class="g-on">${esc(pt.grammar)}</span> is used ${pt.count} time${pt.count === 1 ? '' : 's'} in this text.
        <a href="#/grammar/point/${enc(pt.id)}">${esc(pt.title)} →</a>`;
    }
  };
  sel.onchange = () => apply(sel.value);
  if (initial && scan.spans[initial]) { sel.value = initial; apply(initial); }
}
