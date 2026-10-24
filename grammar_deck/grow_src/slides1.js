// ===== slides part 1: intro, map, steps =====
function head(el, kick, title, sub) { el.appendChild(h('div', 'g-head', `<div class="kick">${kick}</div><h2>${title}</h2>${sub ? `<p>${sub}</p>` : ''}`)); }
const finalEn = st => st.boss ? st.seq[st.seq.length - 1].en : st.en;
const stepText = i => plain(parse(finalEn(STEPS[i])));
function fromIdx(i) { const st = STEPS[i]; if (st.from === 0) return -1; if (st.from) return st.from - 1; return i > 0 && STEPS[i - 1].r === st.r ? i - 1 : -1; }
function ulinks(units) { return (units || []).map(u => `<a class="ulink" href="grammar_map_101.html#${u}" target="_blank" rel="noopener" title="영어 구문 지도 101에서 열기">📘 ${u} · ${esc(UNITS[u] || '')}</a>`).join(''); }
function mindHTML(m) { return `<h3>영어 순서로 생각하기</h3><div class="mind">${m.split('/').map(x => `<span>${esc(x.trim())}</span>`).join('<i>→</i>')}</div>`; }

// ---------------------------------------------------------------- cover
function buildCover(el) {
  el.classList.add('cover');
  el.appendChild(h('div', 'cv-top', `<div class="kick">동료와 함께하는 영어 문법 · 어순 편</div><h1>문장이 자란다</h1>
    <p>“I am a student.” 한 문장에서 시작해 한 조각씩 붙여 가며, 영어 어순을 45계단 올라갑니다.</p>`));
  const stg = h('div', 'stg card cv-stage'); el.appendChild(stg); stg.appendChild(stageCtl());
  const stage = new Stage(stg, {max: 50});
  el.appendChild(h('div', 'cv-pr', `
    <div class="card" style="--rc:var(--S)"><b>① 주어 ↔ 동사는 한 몸</b><span>동사는 주어를 보고 모양을 바꿔요 — I <b>am</b> · She <b>is</b>. self-attention처럼 동사는 늘 주어를 ‘봐요’.</span></div>
    <div class="card" style="--rc:var(--Q)"><b>② 의도 · 틀이 먼저</b><span>Do · Did · What · I don't think… 첫 단어에서 말하는 사람의 의도가 보여요.</span></div>
    <div class="card" style="--rc:var(--H)"><b>＋ 제안: 2번 자리</b><span>주어 바로 뒤 한 칸이 시제 · 부정 · 질문 · 짧은 대답을 모두 조종해요.</span></div>`));
  el.appendChild(h('div', 'cv-foot', '<kbd>←</kbd> <kbd>→</kbd> 이동 · <kbd>M</kbd> 지도 · <kbd>A</kbd> 곡선 · <kbd>K</kbd> 한국어 거울 · <kbd>R</kbd> 변신 다시 보기 · <kbd>F</kbd> 전체 화면'));
  const chain = [0, 1, 2, 3, 4, 6]; let k = 0;
  const next = () => {
    const i = chain[k % chain.length], pi = chain[(k + chain.length - 1) % chain.length], st = STEPS[i], to = parse(st.en);
    activate(stage, {nodes: to, from: k ? parse(STEPS[pi].en) : null, fromSeat: STEPS[pi].seat, arcs: st.arcs, km: st.km, seat: st.seat, build: !k, delay: 0, say: plain(to)});
    k++; if (!NOANIM) later(next, 4200);
  };
  next();
}

// ---------------------------------------------------------------- mirror
function buildMirror(el) {
  head(el, '들어가기', '한국어와 영어는 거울이다', '주어(①)는 같은 자리, 그 뒤는 거꾸로. 번호와 선을 따라가 보세요.');
  [{en: '[S#a{①} I] [V#b{②} study] [O#c{③} English].', km: '① 나는|a; ③ 영어를|c; ② 공부한다.|b'},
   {en: '[S#a{①} I] [H#b{②} will] [V#c{③} be] [C#d{④} a student] [M#e{⑤} next year].', km: '① 나는|a; ⑤ 내년에|e; ④ 학생이|d; ③ 될|c; ② 거야.|b'}]
    .forEach(x => { const stg = h('div', 'stg card mir'); el.appendChild(stg); new Stage(stg, {atop: 24, kgap: 50, max: 44}).play({nodes: parse(x.en), km: x.km}); });
  el.appendChild(h('div', 'card note', `영어 <b>① → ② → ③ → ④ → ⑤</b> · 한국어 <b>① → ⑤ → ④ → ③ → ②</b>. 영어는 핵심(동사)을 먼저 말하고 꾸밈을 뒤에 붙이는 <b>head-initial</b> 언어,
    한국어는 핵심을 맨 끝에 두는 <b>head-final</b> 언어예요.<br>그래서 한국어 문장을 다 만든 뒤 번역하면 끝에서부터 거꾸로 뒤져야 해요. 이 자료는 처음부터 <b>영어 순서로 생각하는</b> 연습을 합니다.`));
}

// ---------------------------------------------------------------- principle ①
function buildP1(el) {
  head(el, '원칙 ①', '주어와 동사는 한 몸 — self-attention으로 보면', '각 단어가 다른 단어를 얼마나 ‘보는지’(attention)를 그려 보면, am은 I를 가장 많이 봐요. 표의 줄을 눌러 보세요.');
  const row = h('div', 'row2'); row.style.gridTemplateColumns = '620px 1fr'; el.appendChild(row);
  const L = h('div', 'card p1l'); row.appendChild(L);
  const stg = h('div', 'stg mini'); L.appendChild(stg);
  const stage = new Stage(stg, {atop: 96, max: 50});
  const W = ['I', 'am', 'a', 'student'], ids = ['w0', 'w1', 'w2', 'w3'];
  const nodes = parse('[S#w0 I] [V#w1 am] [M#w2{관사} a] [C#w3 student].');
  const M = [[.20, .55, .05, .20], [.60, .10, .05, .25], [.05, .10, .15, .70], [.25, .30, .30, .15]];
  const tb = h('table', 'hm');
  tb.innerHTML = `<tr><th></th>${W.map(w => `<th>${w}</th>`).join('')}</tr>` +
    M.map((r, i) => `<tr data-r="${i}"><th class="rq">${W[i]} →</th>${r.map(v => `<td style="--p:${Math.round(v * 85)}%">${Math.round(v * 100)}</td>`).join('')}</tr>`).join('');
  L.appendChild(tb);
  L.appendChild(h('div', 'hmcap', '줄 = 지금 보고 있는 단어 · 칸 = 그 단어가 다른 단어에 주는 관심(%) — 설명을 위한 가상의 값'));
  const pick = r => {
    $$('tr', tb).forEach(t => t.classList.toggle('on', t.dataset.r === String(r)));
    activate(stage, {nodes, seat: 'w1', say: 'I am a student.',
      arcs: M[r].map((v, c) => c === r ? null : [ids[r], ids[c], v >= .45 ? 3 : v >= .2 ? 2 : 1, Math.round(v * 100) + '%']).filter(Boolean)});
  };
  tb.addEventListener('click', e => { const t = e.target.closest('tr[data-r]'); if (t) pick(+t.dataset.r); });
  pick(1);
  row.appendChild(h('div', 'ev', `
    <div class="card"><b class="t">1. 일치 — 동사는 주어를 보고 모양을 바꾼다</b>I <b>am</b> · You <b>are</b> · She <b>is</b> · She stud<b>ies</b>. 보어·목적어를 바꿔도 동사는 그대로예요.</div>
    <div class="card"><b class="t">2. 시제와 조동사는 주어 바로 뒤</b>I <b>will</b> be · I <b>did</b> not · I <b>have</b> been — 시간과 태도를 주어 바로 뒤에서 먼저 밝혀요.</div>
    <div class="card"><b class="t">3. 짧은 대답 = 주어 + 2번 자리</b>Are you…? → Yes, I <b>am</b>. · Did she…? → No, she <b>didn't</b>. 목적어가 없어도 대답이 돼요.</div>
    <div class="card"><b class="t">4. 한국어와 비교하면</b>나는(①) 학생(③) 이다(②) — 한국어 동사는 주어에서 <b>가장 먼</b> 끝에 있어요. 그래서 영어로 말할 때는 ‘주어 다음 바로 동사’를 의식해서 연습해요.</div>
    <small>※ 위 숫자는 설명용 그림이에요. 실제 BERT 연구에서도 ‘목적어 → 동사’, ‘한정사 → 명사’처럼 문법 관계를 따라가는 attention head가 관찰됐어요 (Clark et al., 2019). 자세한 이야기는 마지막의 ‘솔직한 메모’에.</small>`));
}

// ---------------------------------------------------------------- principle ②
function buildP2(el) {
  head(el, '원칙 ②', '중요한 것(말하는 사람의 의도)이 먼저', '영어는 첫 단어에서 의도를 밝히고, 한국어는 끝까지 들어야 알아요. 테두리 칸 = 의도가 드러나는 단어.');
  const t = h('div', 'card p2t'); el.appendChild(t);
  let html = '<div class="hd">의도</div><div class="hd">English — 몇 번째 단어에서 알까?</div><div class="hd">한국어</div>';
  P2.forEach(r => {
    const chips = (ws, at) => ws.map((w, j) => `<span class="${j === at ? 'it' : j < at ? 'wait' : ''}">${esc(w)}</span>`).join('') + `<em>${at + 1} / ${ws.length}번째</em>`;
    html += `<div class="wh">${esc(r.what)}</div><div class="cw">${chips(r.en, r.ei)}</div><div class="cw">${chips(r.ko, r.ki)}</div>`;
  });
  t.innerHTML = html;
  el.appendChild(h('div', 'card note', `그래서 영어는 <b>첫 단어부터 집중</b>해서 듣고, 말할 때도 <b>의도부터</b> 꺼내면 돼요: <i>Do you…? · Could you…? · I don't think…</i><br>
    정확히는 <b>‘틀(질문 · 부정 · 판단) 먼저, 무거운 내용은 뒤로’</b> — 긴 설명이나 새 정보는 오히려 문장 끝으로 가요 (end-weight). 이 자료의 Round 5~7에서 같이 봅니다.`));
  const c = h('div', 'cards'); c.style.gridTemplateColumns = '1fr 1fr 1fr'; el.appendChild(c);
  c.innerHTML = `<div class="card"><h4>🎧 들을 때</h4>첫 단어(Do · Did · Can · Will · What)에서 <b>질문 종류</b>를, 2번 자리에서 <b>시제</b>를 잡아요. 첫 단어를 놓치면 문장 전체를 놓쳐요.</div>
    <div class="card"><h4>🗣 말할 때</h4>의도를 먼저 꺼내고 내용은 천천히: <i>Could you… · I don't think… · Do you know…</i> — 첫 두 단어가 나오면 나머지는 생각하면서 이어 가도 돼요.</div>
    <div class="card"><h4>🎯 첫 단어 게임</h4>진행자가 첫 두 단어만 말하면(<i>Did you… / I don't… / It is…</i>) 듣는 사람이 질문인지 · 부정인지 · 판단인지 맞히고 문장을 완성해요.</div>`;
}

// ---------------------------------------------------------------- 2번 자리 (operator seat)
function buildSeat(el) {
  head(el, '제안 — 더 쉬운 방법', '2번 자리 하나로 부정 · 질문 · 대답을 다 만든다', '주어 바로 뒤 한 칸(operator)을 ‘조종석’으로 보세요. 버튼을 눌러 변신시켜 보세요.');
  const top = h('div', 'mach'); el.appendChild(top);
  const mc = h('div', 'card machc'); top.appendChild(mc);
  const bar = h('div', 'machb'); mc.appendChild(bar);
  const stg = h('div', 'stg'); mc.appendChild(stg);
  const stage = new Stage(stg, {atop: 62, max: 40});
  const ko = h('div', 'machko'); mc.appendChild(ko);
  top.appendChild(h('div', 'card rules', `<b>2번 자리의 세 가지 동작</b><ol>
    <li><b>넣기</b> — will · can · have · be · do가 주어 바로 뒤에</li>
    <li><b>not 붙이기</b> — 2번 자리 바로 뒤에 not</li>
    <li><b>점프</b> — 질문 · 강조면 2번 자리가 주어 앞으로</li></ol>
    ☆ 2번 자리가 비어 있으면(studied) <b>do를 부른다</b> — did가 과거를 가져가고 동사는 원형으로.`));
  let mi = 0, fi = 0, cur = null;
  const set = (m, f) => {
    const F = MACH[m].forms[f], nn = parse(F[1]);
    activate(stage, {nodes: nn, from: cur, fromSeat: 'h', arcs: 'auto', seat: 'h', delay: 0, say: plain(nn)});
    cur = nn; mi = m; fi = f; ko.textContent = F[2]; draw();
  };
  const draw = () => {
    bar.innerHTML = '';
    MACH.forEach((M, m) => { const b = h('button', 'tab' + (m === mi ? ' on' : ''), esc(M.name)); b.onclick = () => { cur = null; set(m, 0); }; bar.appendChild(b); });
    bar.appendChild(h('span', '', '&nbsp;→&nbsp;'));
    MACH[mi].forms.forEach((F, f) => { const b = h('button', 'btn sm' + (f === fi ? ' on' : ''), esc(F[0])); b.onclick = () => set(mi, f); bar.appendChild(b); });
  };
  set(0, 0);
  const gc = h('div', 'card gridc'); el.appendChild(gc);
  const seatCols = [1, 3];
  gc.innerHTML = `<table class="grid"><tr>${GRID_COLS.map((c, j) => `<th class="${seatCols.includes(j) ? 'seatc' : ''}">${c}</th>`).join('')}</tr>` +
    GRID.map(r => `<tr>${r.map((c, j) => `<td class="${seatCols.includes(j) ? 'seatc' : ''}">${c ? `<span class="r-${c[1]}">${esc(c[0])}</span>` : ''}</td>`).join('')}</tr>`).join('') + '</table>';
}

// ---------------------------------------------------------------- map
function buildMap(el) {
  head(el, '전체 지도', '문장 계단 45 — 눌러서 어디든 이동', 'Round 1의 한 문장이 Round 7의 긴 문장까지 자라요. 각 계단은 이전 문장에 한 조각을 붙이거나 옮긴 것.');
  const wrap = h('div', 'stairs'); el.appendChild(wrap);
  ROUNDS.forEach((R, ri) => {
    const col = h('div', 'stair'); col.style.setProperty('--rc', `var(--${R.c})`); col.style.marginTop = ((7 - ri) * 17) + 'px';
    col.appendChild(h('div', 'sh', `${ri < 7 ? 'R' + (ri + 1) : '★'} ${esc(R.t)}<small>${esc(R.s)}</small>`));
    STEPS.forEach((s, j) => { if (s.r !== ri + 1) return; const b = h('button', 'sx', `<i>${j + 1}</i><span>${esc(stepText(j))}</span>`); b.dataset.go = 's' + (j + 1); col.appendChild(b); });
    wrap.appendChild(col);
  });
  const lg = [['S', '주어 S'], ['V', '동사 V'], ['H', '조동사 Aux'], ['N', '부정 not'], ['O', '목적어 O'], ['C', '보어 C'], ['M', '수식어 M'], ['Q', '의문사 Wh'], ['K', '연결어']];
  el.appendChild(h('div', 'legend', lg.map(([r, t]) => `<span class="lg" style="--rc:var(--${r})"><i></i>${t}</span>`).join('') +
    '<span class="lg"><b style="background:var(--ink);color:var(--bg);border-radius:50%;width:18px;height:18px;display:inline-grid;place-items:center;font-size:11px">2</b>2번 자리</span>' +
    '<span>· 위 곡선 = attention · 아래 선 = 한국어 거울</span>'));
  el.appendChild(h('div', 'links', '<button class="btn" data-go="switch">🔁 연습 ① 주어 스위치</button><button class="btn" data-go="ask">❓ 연습 ② 의도 먼저 질문 만들기</button><button class="btn" data-go="drill">🧩 연습 ③ 문장 키우기 드릴</button><button class="btn" data-go="summary">📌 한 장 요약</button><button class="btn" data-go="honest">🧠 솔직한 메모</button>'));
}

// ---------------------------------------------------------------- step slides
function stepHeader(i) {
  const st = STEPS[i], R = ROUNDS[st.r - 1], hd = h('div', 's-head');
  hd.innerHTML = `<div class="hl"><div><span class="rpill">${st.r < 8 ? 'ROUND ' + st.r : '★ BOSS'} · ${esc(R.t)}</span><span class="sno">STEP ${i + 1} / ${STEPS.length}</span></div><h2>${md(st.h)}</h2></div>`;
  const dots = h('div', 'rdots');
  STEPS.forEach((s, j) => { if (s.r !== st.r) return; const b = h('button', j === i ? 'cur' : j < i ? 'done' : '', String(j + 1)); b.title = stepText(j); b.dataset.go = 's' + (j + 1); dots.appendChild(b); });
  hd.appendChild(dots);
  return hd;
}
function prevLine(from, to, label) {
  const pv = h('div', 'prev');
  pv.innerHTML = from ? `<span>이전 문장 ${label} ▸</span><span class="pv">${esc(plain(from))}</span><span class="dch">${diffChips(from, to)}</span>`
    : '<span class="seed">🌱 새 씨앗 문장</span><span>— 여기서부터 다시 한 조각씩 키워요</span>';
  return pv;
}
function sideFoot(i, st) {
  return h('div', 'ulinks', ulinks(st.units));
}
function buildStep(el, i) {
  const st = STEPS[i]; if (st.boss) return buildBoss(el, i);
  const R = ROUNDS[st.r - 1];
  el.classList.add('step'); el.style.setProperty('--rc', `var(--${R.c})`);
  el.appendChild(stepHeader(i));
  const fi = fromIdx(i), to = parse(st.en), from = fi >= 0 ? parse(STEPS[fi].en) : null;
  el.appendChild(prevLine(from, to, from ? `<span class="sl" data-go="s${fi + 1}">(Step ${fi + 1})</span>` : ''));
  const stg = h('div', 'stg card'); el.appendChild(stg); stg.appendChild(stageCtl(i));
  const stage = new Stage(stg);
  const spec = {nodes: to, from, fromSeat: fi >= 0 ? STEPS[fi].seat : null, arcs: st.arcs, km: st.km, seat: st.seat, build: !from, say: plain(to)};
  const bot = h('div', 's-bot'); el.appendChild(bot);
  bot.appendChild(h('div', 'pane card why', `<h3>왜 이 자리?</h3><ul>${st.why.map(w => `<li>${md(w)}</li>`).join('')}</ul>`));
  bot.appendChild(h('div', 'pane card mid', mindHTML(st.mind) + `<h3 class="mt">한국어 뜻</h3><div class="kos">${esc(st.ko)}</div>`));
  const side = h('div', 'pane card side'); bot.appendChild(side);
  if (st.sw) switchWidget(side, SWITCH[st.sw], stage, spec, st.swi || 0);
  else if (st.cmp) side.appendChild(h('div', 'sw', '<h3>비교</h3>' + st.cmp.map(([k, s, n]) => `<div class="cmpc ${k}"><b>${k === 'ok' ? '✓' : '△'} ${esc(s)}</b><small>${esc(n)}</small></div>`).join('')));
  else {
    const sb = findBlk(to, st.seat);
    side.appendChild(h('div', 'seatbox', `<h3>2번 자리</h3>지금 2번 자리 단어: <span class="w">${esc(sb ? plain([sb]) : '-')}</span>`));
    side.appendChild(h('div', 'rrule', `<b>Round ${st.r} 규칙</b><br>${esc(R.rule)}`));
  }
  side.appendChild(h('div', 'sp'));
  side.appendChild(sideFoot(i, st));
  activate(stage, spec);
}
function buildBoss(el, i) {
  const st = STEPS[i], R = ROUNDS[st.r - 1];
  el.classList.add('step'); el.style.setProperty('--rc', `var(--${R.c})`);
  el.appendChild(stepHeader(i));
  const pvBox = h('div', ''); el.appendChild(pvBox);
  const stg = h('div', 'stg card'); el.appendChild(stg); stg.appendChild(stageCtl(i));
  const stage = new Stage(stg, {max: 40});
  const bot = h('div', 's-bot'); el.appendChild(bot);
  const why = h('div', 'pane card why'); bot.appendChild(why);
  const mid = h('div', 'pane card mid'); bot.appendChild(mid);
  const side = h('div', 'pane card side'); bot.appendChild(side);
  const nav = h('div', 'sw'); side.appendChild(nav); side.appendChild(h('div', 'sp')); side.appendChild(sideFoot(i, st));
  let L = NOANIM ? st.seq.length - 1 : 0;
  const show = (l, anim) => {
    L = Math.max(0, Math.min(st.seq.length - 1, l));
    const S = st.seq[L], to = parse(S.en), from = L > 0 && anim ? parse(st.seq[L - 1].en) : null;
    pvBox.replaceChildren(prevLine(L > 0 ? parse(st.seq[L - 1].en) : null, to, `(층 ${L})`));
    why.innerHTML = `<h3>체크리스트 — 층 ${L + 1} / ${st.seq.length}</h3><ul>${st.why.map((w, j) => `<li class="${j === L ? 'lit' : j > L ? 'dim' : ''}">${md(w)}</li>`).join('')}</ul>`;
    mid.innerHTML = `<h3>이번 층</h3><div class="kos"><b>${esc(S.note)}</b></div><h3 class="mt">한국어 뜻</h3><div class="kos">${esc(S.ko)}</div>`;
    nav.innerHTML = `<h3>층 쌓기</h3><div class="opts">${st.seq.map((_, j) => `<button class="opt${j === L ? ' on' : ''}" data-l="${j}">${j + 1}</button>`).join('')}</div>
      <div style="display:flex;gap:6px;margin-top:6px"><button class="btn sm" data-l="${L - 1}">◀ 이전 층</button><button class="btn sm pri" data-l="${L + 1}">다음 층 ▶ <kbd>N</kbd></button></div>`;
    activate(stage, {nodes: to, from, fromSeat: L > 0 ? st.seq[L - 1].seat : null, arcs: S.arcs, km: S.km, seat: S.seat, build: !from && anim, delay: 250, say: plain(to)});
  };
  nav.addEventListener('click', e => { const b = e.target.closest('[data-l]'); if (b) show(+b.dataset.l, true); });
  SLIDEKEYS = e => { if (e.key === 'n' || e.key === 'N') { show(L + 1, true); return true; } return false; };
  show(L, true);
}
