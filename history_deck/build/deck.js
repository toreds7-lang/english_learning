(() => {
  const FILE = location.protocol === 'file:';
  const root = document.documentElement;
  if (FILE) root.classList.add('is-file');
  const $ = id => document.getElementById(id);
  const slides = [...document.querySelectorAll('.slide')];
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const wait = ms => new Promise(r => setTimeout(r, ms));

  // ---------- theme (remembered per browser when storage is available) ----------
  { const t = store.get('histeng-theme'); if (t) root.dataset.theme = t; }
  function toggleTheme() {
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    store.set('histeng-theme', root.dataset.theme);
  }

  // ---------- audio: Kokoro clips (base64 Ogg Opus); browser voice if a clip is missing ----------
  let cur = null;   // { a, btn, done }
  let seq = 0;      // bumps to cancel a running sequence
  function stopAudio() {
    if (cur) { cur.a.pause(); cur.done(); }
    if (window.speechSynthesis) speechSynthesis.cancel();
  }
  function say(key, btn) {
    stopAudio();
    return new Promise(resolve => {
      let a = null;
      const finish = () => { if (btn) btn.classList.remove('playing'); if (cur && cur.a === a) cur = null; resolve(); };
      const b64 = AUDIO[key];
      if (btn) btn.classList.add('playing');
      if (!b64) {
        const text = DATA.tts[key];
        if (!text || !window.speechSynthesis) { finish(); return; }
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'en-US'; u.rate = 0.9;
        u.onend = u.onerror = finish;
        a = { pause() {} };
        cur = { a, btn, done: finish };
        speechSynthesis.speak(u);
        return;
      }
      a = new Audio('data:audio/ogg;base64,' + b64);
      cur = { a, btn, done: finish };
      a.onended = finish;
      a.onerror = finish;
      a.play().catch(finish);
    });
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-say]');
    if (b) { seq++; say(b.dataset.say, b); }
  });

  // ---------- YouTube players: thumbnail first, iframe on click; four videos ----------
  const V = DATA.videos;
  const playIcon = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13l11-6.5z"/></svg>';
  const secs = v => String(v || 0).split(':').map(Number).reduce((a, n) => a * 60 + n, 0);
  const watchUrl = (v, t) => `https://www.youtube.com/watch?v=${V[v].id}${t ? `&t=${t}s` : ''}`;
  function showFacade(p, v) {
    v = v || p.dataset.cur || p.dataset.v;
    p.dataset.cur = v;
    p.classList.remove('playing');
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'facade';
    b.setAttribute('aria-label', (FILE ? 'Watch on YouTube: ' : 'Play video: ') + V[v].title);
    b.innerHTML = `<img alt="" src="${V[v].thumb}"><span class="play">${playIcon}${FILE ? 'YouTube에서 보기 ↗' : '재생 · ' + V[v].len}</span><span class="who">${esc(V[v].who)}</span>`;
    b.addEventListener('click', () => {
      if (FILE) window.open(watchUrl(v, 0), '_blank', 'noopener');
      else playVideo(p, v, 0);
    });
    p.replaceChildren(b);
  }
  function playVideo(p, v, t) {
    stopAudio();
    const f = document.createElement('iframe');
    f.src = `https://www.youtube-nocookie.com/embed/${V[v].id}?autoplay=1&rel=0&playsinline=1&cc_load_policy=1&cc_lang_pref=en${t ? `&start=${t}` : ''}`;
    f.title = V[v].title;
    f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    f.allowFullscreen = true;
    f.referrerPolicy = 'strict-origin-when-cross-origin';
    p.replaceChildren(f);
    p.dataset.cur = v;
    p.classList.add('playing');
  }
  document.querySelectorAll('.player').forEach(p => showFacade(p));

  // A "moment" box under each chip row shows what is said at that time. It is the only
  // way to "watch" offline (file://), and a handy English caption when the video plays.
  document.querySelectorAll('.chapters').forEach(c => {
    const m = document.createElement('p');
    m.className = 'moment en';
    m.hidden = true;
    m.setAttribute('aria-live', 'polite');
    const w = document.createElement('p');
    w.className = 'filewarn';
    w.innerHTML = '파일로 열어서 영상이 재생되지 않습니다. 시간을 누르면 그 장면의 대사가 나옵니다. 집에서는 <code>start_deck.bat</code>으로 열면 영상이 재생됩니다.';
    c.after(m, w);
  });
  document.querySelectorAll('.chapters button[data-v]').forEach(btn => {
    btn.addEventListener('click', () => {
      const slide = btn.closest('.slide');
      const v = btn.dataset.v, t = btn.dataset.t;
      const m = slide.querySelector('.moment');
      m.innerHTML = '';
      const b = document.createElement('b');
      b.textContent = `${V[v].who} ${t}`;
      const q = document.createElement('q');
      q.textContent = btn.dataset.q;
      m.append(b, q);
      if (btn.dataset.note) {
        const n = document.createElement('span');
        n.className = 'view';
        n.textContent = btn.dataset.note;
        m.append(n);
      }
      m.hidden = false;
      slide.querySelectorAll('.chapters button').forEach(x => x.classList.toggle('on', x === btn));
      if (FILE) return;
      const p = slide.querySelector('.player');
      if (p) playVideo(p, v, secs(t));
      else window.open(watchUrl(v, secs(t)), '_blank', 'noopener');
    });
  });

  // ---------- links to the other decks: only work when opened as files ----------
  document.querySelectorAll('a[data-xlink]').forEach(a => {
    if (FILE) { a.target = '_blank'; a.rel = 'noopener'; return; }
    a.classList.add('off');
    a.title = '다른 덱은 파일로 열었을 때 연결됩니다';
    a.removeAttribute('href');
  });
  if ($('xlinkNote')) $('xlinkNote').textContent = FILE
    ? 'english_reading 폴더 안의 다른 덱을 새 탭으로 엽니다.'
    : '지금은 start_deck.bat(localhost)으로 열려 있어 다른 덱 링크가 꺼져 있습니다. 탐색기에서 각 HTML 파일을 직접 여세요.';

  // ---------- 1 · knight fossil ----------
  const FOSSIL = [
    '<b>k</b> · 사라진 소리. 고대 영어 cniht는 [크니히트]. k를 실제로 발음했고, 1600년대에 빠졌습니다. 독일어 Knecht(하인)에는 지금도 남아 있습니다.',
    '<b>n</b> · 1,000년 동안 그대로인 글자. 모든 글자가 이상한 건 아닙니다.',
    '<b>i</b> · 대모음추이. 중세의 [i]가 길어졌다가 1400~1700년 사이 [aɪ]가 되었습니다. 그래서 i를 \'아이\'로 읽습니다.',
    '<b>gh</b> · 노르만 서기 + 사라진 소리. 고대 영어에서 h로 쓰던 \'히\' 소리 [ç]를 프랑스식 교육을 받은 서기들이 gh로 적었고, 소리는 1400~1600년대에 사라졌습니다. 독일어 Nacht의 ch 소리입니다.',
    '<b>t</b> · 그대로. 영어 철자의 대부분은 지금도 정직합니다. 이상한 부분만 \'범인\'을 찾으면 됩니다.'
  ];
  document.querySelectorAll('#fossil button').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('#fossil button').forEach(x => x.classList.toggle('on', x === b));
    $('fossilInfo').innerHTML = FOSSIL[+b.dataset.i];
  }));

  // ---------- 13 · time machine ----------
  const tm = { filter: 'all' };
  $('tmGrid').innerHTML = DATA.tm.map((r, i) => `
    <div class="tm" data-i="${i}" data-g="${r.grp}">
      <button type="button" class="say w" data-both="${i}" style="justify-content:flex-start"><span class="w">${esc(r.w)}</span></button>
      <div class="st">
        <button type="button" class="say" data-say="tm-${esc(r.w)}-me">1400</button><span class="k"><span class="ipa">${esc(r.me.ipa)}</span> ${esc(r.me.ko)}</span>
        <button type="button" class="say" data-say="tm-${esc(r.w)}-now">지금</button><span class="k"><span class="ipa">${esc(r.now.ipa)}</span> ${esc(r.now.ko)}</span>
      </div>
    </div>`).join('');
  const tmCards = [...document.querySelectorAll('#tmGrid .tm')];
  function tmPick(i) {
    tmCards.forEach(c => c.classList.toggle('on', +c.dataset.i === i));
    const r = DATA.tm[i];
    $('tmNote').innerHTML = `<b class="w">${esc(r.w)}</b> · ${esc(r.me.ipa)} → ${esc(r.now.ipa)} · ${esc(r.note)}`;
  }
  async function tmBoth(i, my) {
    tmPick(i);
    const card = tmCards[i];
    await say(`tm-${DATA.tm[i].w}-me`, card.querySelector('[data-say$="-me"]'));
    if (my !== seq) return;
    await wait(250);
    if (my !== seq) return;
    await say(`tm-${DATA.tm[i].w}-now`, card.querySelector('[data-say$="-now"]'));
  }
  tmCards.forEach(c => c.addEventListener('click', e => {
    const i = +c.dataset.i;
    if (e.target.closest('[data-both]')) { const my = ++seq; tmBoth(i, my); }
    else tmPick(i);
  }));
  $('tmFilter').addEventListener('click', e => {
    const b = e.target.closest('button[data-f]');
    if (!b) return;
    tm.filter = b.dataset.f;
    $('tmFilter').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
    tmCards.forEach(c => { c.hidden = tm.filter !== 'all' && c.dataset.g !== tm.filter; });
  });
  $('tmAll').addEventListener('click', async () => {
    const my = ++seq;
    for (const c of tmCards.filter(c => !c.hidden)) {
      await tmBoth(+c.dataset.i, my);
      if (my !== seq) return;
      await wait(600);
      if (my !== seq) return;
    }
  });
  $('tmStop').addEventListener('click', () => { seq++; stopAudio(); });

  // ---------- 18 · spelling detective ----------
  const CAUSES = {
    lost: ['🔇', '사라진 소리'], scribe: ['✒️', '노르만 서기'], printer: ['🖨️', '인쇄공'], latin: ['📜', '르네상스 학자'],
    gvs: ['🔊', '대모음추이'], analogy: ['🧩', '모양 맞추기'], dialect: ['🗣️', '방언 발음'], loan: ['✈️', '빌린 철자']
  };
  $('detCauses').innerHTML = Object.values(CAUSES).map(([ic, l]) => `<span>${ic} ${l}</span>`).join('');
  const det = { w: 0, seen: DATA.det.map(() => new Set()) };
  const oddCount = r => r.parts.filter(p => p.c).length;
  const detTotal = DATA.det.reduce((n, r) => n + oddCount(r), 0);
  function detScore() {
    const n = det.seen.reduce((a, s) => a + s.size, 0);
    $('detScore').textContent = `해결한 수수께끼 ${n} / ${detTotal}`;
    [...$('detWords').children].forEach((b, i) => b.classList.toggle('done', det.seen[i].size === oddCount(DATA.det[i])));
  }
  function detShow(i) {
    det.w = i;
    const r = DATA.det[i];
    [...$('detWords').children].forEach((b, j) => b.classList.toggle('on', j === i));
    $('detBig').innerHTML = r.parts.map((p, j) => p.c
      ? `<button type="button" class="p${det.seen[i].has(j) ? ' seen' : ''}" data-j="${j}" aria-label="${esc(p.t)}: 이상한 글자">${esc(p.t)}</button>`
      : `<span class="p">${esc(p.t)}</span>`).join('');
    $('detSay').dataset.say = `w-${r.w}`;
    $('detIpa').textContent = r.ipa;
    $('detKo').textContent = r.ko;
    $('detCard').innerHTML = `<p class="muted">반짝이는 글자 ${oddCount(r)}개를 누르세요.</p>`;
  }
  $('detWords').innerHTML = DATA.det.map((r, i) => `<button type="button" data-i="${i}">${esc(r.w)}</button>`).join('');
  $('detWords').addEventListener('click', e => { const b = e.target.closest('button'); if (b) detShow(+b.dataset.i); });
  $('detBig').addEventListener('click', e => {
    const b = e.target.closest('button.p');
    if (!b) return;
    const j = +b.dataset.j, r = DATA.det[det.w], p = r.parts[j];
    det.seen[det.w].add(j);
    b.classList.add('seen');
    $('detBig').querySelectorAll('button.p').forEach(x => x.classList.toggle('on', x === b));
    const [ic, label] = CAUSES[p.c];
    $('detCard').innerHTML = `<span class="stamp">${ic} ${label}</span><b class="w">${esc(r.w)}</b>의 <b class="w">${esc(p.t)}</b> · <span class="muted">${esc(p.y)}</span>
      <p>${esc(p.why)}</p><p class="hook"><b>외우는 요령</b> ${esc(p.hook)}</p>`;
    detScore();
  });
  detShow(0);
  detScore();

  // ---------- 21 · spelling-to-sound drill ----------
  const dr = { mode: 'sound', set: 0, i: 0, done: false, right: 0, total: 0, ok: new Set() };
  const drSets = () => dr.mode === 'sound' ? DATA.sound : DATA.stress;
  function hiWord(w, hl) {
    const lw = w.toLowerCase();
    if (hl.includes('_')) {
      const v = hl[0], e = lw.lastIndexOf('e');
      const vi = lw.lastIndexOf(v, e - 1);
      return esc(w.slice(0, vi)) + `<mark>${esc(w[vi])}</mark>` + esc(w.slice(vi + 1, e)) + `<mark>${esc(w[e])}</mark>` + esc(w.slice(e + 1));
    }
    const k = lw.indexOf(hl);
    return k < 0 ? esc(w) : esc(w.slice(0, k)) + `<mark>${esc(w.slice(k, k + hl.length))}</mark>` + esc(w.slice(k + hl.length));
  }
  function drRenderSets() {
    $('drSets').innerHTML = drSets().map((s, i) => `<button type="button" data-s="${i}" class="${i === dr.set ? 'on' : ''}">${esc(s.title)}</button>`).join('');
  }
  function drShow() {
    const s = drSets()[dr.set], it = s.items[dr.i];
    dr.done = false;
    $('drRule').textContent = s.rule;
    $('drRuleTitle').textContent = `규칙 · ${s.title}`;
    $('drFb').innerHTML = '답을 고르면 소리와 이유가 나옵니다.';
    $('drSay').dataset.say = `w-${it.w}`;
    $('drList').innerHTML = s.items.map(x => `<button type="button" class="say" data-say="w-${esc(x.w)}">${esc(x.w)}${dr.ok.has(dr.mode + s.id + x.w) ? ' ✓' : ''}</button>`).join('');
    if (dr.mode === 'sound') {
      $('drAsk').textContent = `${dr.i + 1} / ${s.items.length} · 표시된 글자는 어떤 소리일까?`;
      $('drWord').innerHTML = hiWord(it.w, it.hl);
      $('drChoices').innerHTML = `<div class="opts">${s.opts.map((o, j) => `<button type="button" data-o="${j}">${esc(o)}</button>`).join('')}</div>`;
    } else {
      $('drAsk').textContent = `${dr.i + 1} / ${s.items.length} · 강세가 오는 음절을 누르세요`;
      $('drWord').innerHTML = `<span class="w" style="font-size:1.3rem">${esc(it.w)}</span>`;
      $('drChoices').innerHTML = `<div class="syls">${it.syl.map((y, j) => `<button type="button" data-y="${j}">${esc(y)}</button>`).join('')}</div>`;
    }
    $('drScore').textContent = `맞힌 수 ${dr.right} / ${dr.total}`;
  }
  $('drChoices').addEventListener('click', e => {
    const s = drSets()[dr.set], it = s.items[dr.i];
    const b = e.target.closest('button');
    if (!b || dr.done) return;
    dr.done = true;
    dr.total++;
    const pick = dr.mode === 'sound' ? +b.dataset.o : +b.dataset.y;
    const good = pick === it.ans;
    if (good) { dr.right++; dr.ok.add(dr.mode + s.id + it.w); }
    const btns = [...$('drChoices').querySelectorAll('button')];
    btns.forEach((x, j) => { if (j === it.ans) x.classList.add('right'); else if (x === b) x.classList.add('wrong'); });
    if (dr.mode === 'sound') {
      $('drFb').innerHTML = `${good ? '✅ 맞아요.' : '❌ 아쉬워요.'} <b class="w">${esc(it.w)}</b> = <b>${esc(s.opts[it.ans])}</b> · ${esc(it.note)}`;
    } else {
      const shown = it.syl.map((y, j) => j === it.ans ? `<b>${esc(y.toUpperCase())}</b>` : esc(y)).join('·');
      $('drFb').innerHTML = `${good ? '✅ 맞아요.' : '❌ 아쉬워요.'} <span class="w">${shown}</span> <span class="ipa">${esc(it.ipa)}</span> · 강세 없는 모음은 /ə/로 약해집니다.`;
    }
    $('drScore').textContent = `맞힌 수 ${dr.right} / ${dr.total}`;
    $('drList').querySelectorAll('button')[dr.i].textContent = it.w + (good ? ' ✓' : '');
    seq++;
    say(`w-${it.w}`, $('drSay'));
  });
  $('drNext').addEventListener('click', () => {
    const s = drSets()[dr.set];
    if (dr.i < s.items.length - 1) dr.i++;
    else { dr.set = (dr.set + 1) % drSets().length; dr.i = 0; drRenderSets(); }
    drShow();
  });
  $('drSets').addEventListener('click', e => {
    const b = e.target.closest('button[data-s]');
    if (!b) return;
    dr.set = +b.dataset.s; dr.i = 0;
    drRenderSets(); drShow();
  });
  $('drMode').addEventListener('click', e => {
    const b = e.target.closest('button[data-m]');
    if (!b) return;
    dr.mode = b.dataset.m; dr.set = 0; dr.i = 0;
    $('drMode').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
    drRenderSets(); drShow();
  });
  drRenderSets();
  drShow();

  // ---------- 22 · vocabulary origins + top 40 ----------
  const ORIGINS = [
    { nm: '프랑스어', sub: '고대·앵글로 프랑스어', v: 28.3, c: 'F' },
    { nm: '라틴어', sub: '르네상스·학술 차용', v: 28.2, c: 'L' },
    { nm: '게르만어', sub: '고대 영어·노르드어·네덜란드어', v: 25.0, c: 'G' },
    { nm: '그리스어', sub: '학술·과학', v: 5.3, c: 'L' },
    { nm: '어원 불명', sub: '', v: 4.0, c: 'N' },
    { nm: '고유명사에서', sub: 'sandwich, hoover…', v: 3.3, c: 'N' },
    { nm: '기타 언어', sub: '', v: 0.9, c: 'N', lt: true }
  ];
  $('vbars').innerHTML = ORIGINS.map(o => {
    const val = o.lt ? '<1%' : o.v.toFixed(1) + '%';
    return `<div class="vbar" role="listitem" tabindex="0" title="${esc(o.nm)}: ${val}" aria-label="${esc(o.nm)} ${val}">
      <span class="nm">${esc(o.nm)}${o.sub ? `<small>${esc(o.sub)}</small>` : ''}</span>
      <span class="tr"><span class="fill ${o.c}" style="width:${(o.v / 30 * 100).toFixed(1)}%"></span></span>
      <span class="v">${val}</span></div>`;
  }).join('');
  const TOP40 = 'the be to of and a in that have I it for not on with he as you do at this but his by from they we say her she or an will my one all would there their what'.split(' ');
  const NORSE = new Set(['they', 'their']);
  $('top40').innerHTML = TOP40.map(w => `<span class="${NORSE.has(w) ? 'n' : ''}" title="${NORSE.has(w) ? '노르드어 (바이킹)' : '고대 영어'}">${w}</span>`).join('');

  // ---------- 23 · word-layer game ----------
  const BUCKET = { G: '게르만', F: '프랑스어', L: '라틴·그리스어' };
  const lg = { round: [], i: 0, right: 0, done: false };
  function lgNew() {
    lg.round = shuffle(DATA.layers.slice()).slice(0, 12);
    lg.i = 0; lg.right = 0;
    lgShow();
  }
  function lgShow() {
    lg.done = false;
    document.querySelectorAll('#lgBuckets .bucket').forEach(b => b.classList.remove('right', 'wrong'));
    if (lg.i >= lg.round.length) {
      $('lgWord').textContent = `${lg.right} / ${lg.round.length}`;
      $('lgCount').textContent = '한 판 끝!';
      $('lgFb').innerHTML = lg.right >= 10 ? '훌륭합니다. 단서만 보고도 층이 보이기 시작했어요.' : '단서 표를 한 번 더 보고 새 판을 해 보세요. 두 판이면 감이 옵니다.';
      $('lgScore').textContent = '';
      return;
    }
    $('lgWord').textContent = lg.round[lg.i].w;
    $('lgCount').textContent = `${lg.i + 1} / ${lg.round.length}`;
    $('lgFb').innerHTML = '층을 고르면 출처와 \'가족\'이 나옵니다.';
    $('lgScore').textContent = `맞힌 수 ${lg.right}`;
  }
  $('lgBuckets').addEventListener('click', e => {
    const b = e.target.closest('.bucket');
    if (!b || lg.done || lg.i >= lg.round.length) return;
    lg.done = true;
    const it = lg.round[lg.i];
    const good = b.dataset.b === it.b;
    if (good) lg.right++;
    document.querySelectorAll('#lgBuckets .bucket').forEach(x => {
      if (x.dataset.b === it.b) x.classList.add('right');
      else if (x === b) x.classList.add('wrong');
    });
    $('lgFb').innerHTML = `${good ? '✅' : '❌'} <b class="w">${esc(it.w)}</b> = <span class="lay ${it.b}">${BUCKET[it.b]}</span> · ${esc(it.src)}<br>가족: <b class="w">${esc(it.fam)}</b> · ${esc(it.ko)}`;
    $('lgScore').textContent = `맞힌 수 ${lg.right}`;
  });
  $('lgNext').addEventListener('click', () => { if (lg.i < lg.round.length) { lg.i++; lgShow(); } });
  $('lgNew').addEventListener('click', lgNew);
  lgNew();

  // ---------- 26 · today's checklist (kept in this browser) ----------
  const CKEY = 'histeng-today-v1';
  const checks = [...document.querySelectorAll('#todayCheck input')];
  let saved = {};
  try { saved = JSON.parse(store.get(CKEY)) || {}; } catch (e) { saved = {}; }
  const scoreNow = () => { $('checkScore').textContent = `${checks.filter(c => c.checked).length} / ${checks.length}`; };
  checks.forEach(c => {
    c.checked = !!saved[c.dataset.k];
    c.addEventListener('change', () => { saved[c.dataset.k] = c.checked; store.set(CKEY, JSON.stringify(saved)); scoreNow(); });
  });
  $('checkClear').addEventListener('click', () => { saved = {}; checks.forEach(c => { c.checked = false; }); store.set(CKEY, '{}'); scoreNow(); });
  scoreNow();

  // ---------- navigation ----------
  let at = -1;
  function go(i) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    if (i === at) return;
    if (at >= 0) {
      slides[at].classList.remove('active');
      slides[at].querySelectorAll('.player.playing').forEach(p => showFacade(p)); // stop the video when leaving
      seq++;
      stopAudio();
    }
    at = i;
    const s = slides[at];
    s.classList.add('active');
    s.scrollTop = 0;
    $('progress').style.width = ((at + 1) / slides.length * 100) + '%';
    refreshAccent();
    $('count').textContent = `${at + 1} / ${slides.length}`;
    $('label').textContent = s.dataset.label;
    $('prev').disabled = at === 0;
    $('next').disabled = at === slides.length - 1;
    try { history.replaceState(null, '', location.search + '#' + (at + 1)); } catch (e) {}
  }
  function refreshAccent() { $('progress').style.background = getComputedStyle(slides[at]).getPropertyValue('--accent'); }
  function toggleFull() {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen().catch(() => {});
  }
  $('prev').addEventListener('click', () => go(at - 1));
  $('next').addEventListener('click', () => go(at + 1));
  $('theme').addEventListener('click', () => { toggleTheme(); refreshAccent(); });
  $('full').addEventListener('click', toggleFull);
  document.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => go(+b.dataset.go - 1)));

  document.addEventListener('keydown', e => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.closest && e.target.closest('input, textarea, select')) return;
    const onControl = e.target.closest && e.target.closest('button, a');
    switch (e.key) {
      case 'ArrowRight': case 'PageDown': go(at + 1); break;
      case 'ArrowLeft': case 'PageUp': go(at - 1); break;
      case ' ': if (onControl) return; go(e.shiftKey ? at - 1 : at + 1); break;
      case 'Home': go(0); break;
      case 'End': go(slides.length - 1); break;
      case 'f': case 'F': toggleFull(); break;
      case 't': case 'T': toggleTheme(); refreshAccent(); break;
      default: return;
    }
    e.preventDefault();
  });

  const start = parseInt(location.hash.slice(1), 10);
  go(Number.isFinite(start) ? start - 1 : 0);

  // ---------- ?selftest: visit every slide and report overflow / missing pieces ----------
  if (/[?&]selftest\b/.test(location.search)) {
    const out = { slides: slides.length, overflow: [], wide: [], missingAudio: [], players: document.querySelectorAll('.player').length };
    document.querySelectorAll('[data-say]').forEach(b => { if (!AUDIO[b.dataset.say] && !DATA.tts[b.dataset.say]) out.missingAudio.push(b.dataset.say); });
    const W = innerWidth;
    slides.forEach((s, i) => {
      go(i);
      s.querySelectorAll('.col-text, .col-media, .full').forEach(el => {
        const over = el.scrollHeight - el.clientHeight;
        if (over > 2) out.overflow.push({ slide: i + 1, el: el.className, px: over });
      });
      s.querySelectorAll('*').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width && (r.right > W + 1 || r.left < -1) && !el.closest('.player')) out.wide.push({ slide: i + 1, el: el.tagName + '.' + el.className, right: Math.round(r.right) });
      });
    });
    out.wide = out.wide.slice(0, 20);
    go(Number.isFinite(start) ? start - 1 : 0);
    document.body.dataset.selftest = JSON.stringify(out);
    console.log('SELFTEST', out);
  }
})();
