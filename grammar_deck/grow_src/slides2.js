// ===== slides part 2: practice, wrap-up, navigation =====
function buildSwitch(el) {
  head(el, '연습 ①', '주어 스위치 — 어떤 단어가 주어를 ‘보고’ 있을까?', '주어를 바꾸면 반응하는 단어(주황 깜빡임)와, 목적어·보어를 바꿔도 그대로인 단어를 비교해 보세요.');
  const FR = ['be1', 'study', 'will', 'have', 'dont', 'was', 'long'];
  const tabs = h('div', 'tabs'); el.appendChild(tabs);
  const stg = h('div', 'stg card'); stg.style.flexBasis = '270px'; el.appendChild(stg); stg.appendChild(stageCtl());
  const body = h('div', 'swp'); el.appendChild(body);
  const left = h('div', 'pane card'), right = h('div', 'pane card'); body.append(left, right);
  let fi = 0;
  const load = () => {
    tabs.innerHTML = ''; FR.forEach((f, j) => { const b = h('button', 'tab' + (j === fi ? ' on' : ''), esc(SWITCH[f].tab)); b.onclick = () => { fi = j; load(); }; tabs.appendChild(b); });
    $$('.stage-in', stg).forEach(x => x.remove());
    const cfg = SWITCH[FR[fi]], stage = new Stage(stg, {atop: 92}), st0 = {si: 0, ri: (cfg.rows || []).map(() => 0)};
    const nodes = swNodes(cfg, st0);
    const spec = {nodes, arcs: cfg.arcs, km: swKm(cfg, st0), seat: cfg.seat, say: plain(nodes)};
    left.innerHTML = '<h3>바꿔 보기</h3>'; switchWidget(left, cfg, stage, spec, 0);
    right.innerHTML = `<h3>오늘의 발견</h3><div>${md(cfg.lesson)}</div><h3 class="mt">이렇게 말해 보세요</h3><div class="kos">주어를 바꿀 때마다 문장 전체를 소리 내어 읽기 → 반응하는 단어를 <b>먼저</b> 예측해 보기.</div>`;
    activate(stage, spec);
  };
  load();
}

function buildAsk(el) {
  head(el, '연습 ②', '의도 먼저! 질문 만들기', '평서문을 보고 ‘무엇을 묻고 싶은지’ 고르세요. 의문사와 2번 자리가 어떻게 움직이는지 봅니다.');
  const tabs = h('div', 'tabs'); el.appendChild(tabs);
  const stg = h('div', 'stg card ask-stg'); el.appendChild(stg); stg.appendChild(stageCtl());
  const stage = new Stage(stg, {atop: 86, max: 44});
  const ctl = h('div', 'ask-ctl'); el.appendChild(ctl);
  const bot = h('div', 'ask-bot'); el.appendChild(bot);
  const lp = h('div', 'pane card'), rp = h('div', 'pane card'); bot.append(lp, rp);
  let si = 0, qi = null, speak = false, pending = null, cur = null;
  const setNodes = (nn, k) => { activate(stage, {nodes: nn, from: cur, fromSeat: cur ? autoSeat(cur) : null, arcs: 'auto', seat: autoSeat(nn), delay: 0, say: plain(nn)}); cur = nn; };
  const drawTabs = () => {
    tabs.innerHTML = ''; QSETS.forEach((S, j) => { const b = h('button', 'tab' + (j === si ? ' on' : ''), esc(S.name)); b.onclick = () => { si = j; qi = null; pending = null; cur = null; draw(); setNodes(parse(QSETS[si].st)); }; tabs.appendChild(b); });
  };
  const draw = () => {
    drawTabs();
    const S = QSETS[si];
    ctl.innerHTML = '<span class="lbl">무엇을 묻고 싶나요?</span>';
    S.qs.forEach((q, j) => { const b = h('button', 'btn sm' + (j === qi ? ' on' : ''), esc(q.l)); b.onclick = () => choose(j); ctl.appendChild(b); });
    const back = h('button', 'btn sm', '↺ 평서문으로'); back.onclick = () => { qi = null; pending = null; draw(); setNodes(parse(S.st)); }; ctl.appendChild(back);
    ctl.appendChild(h('span', 'sp'));
    const lab = h('label', '', `<input type="checkbox" ${speak ? 'checked' : ''}> 🗣 먼저 말해 보기 (정답은 나중에)`);
    lab.querySelector('input').onchange = e => { speak = e.target.checked; }; ctl.appendChild(lab);
    if (pending != null) {
      lp.innerHTML = `<div class="prompt">${esc(S.qs[pending].ko)}<small>머릿속으로(또는 소리 내어) 영어 질문을 먼저 만들어 보세요. 첫 단어는 무엇일까요?</small></div>`;
      const b = h('button', 'btn pri', '정답 보기 ▶ <kbd>Enter</kbd>'); b.onclick = reveal; lp.appendChild(h('div', '', '')).appendChild(b); lp.lastChild.style.textAlign = 'center';
      rp.innerHTML = `<h3>평서문</h3><div class="kos">${esc(plain(parse(S.st)))}<br><small>${esc(S.ko)}</small></div>`;
    } else if (qi == null) {
      lp.innerHTML = `<h3>순서</h3><ol class="qsteps"><li><b class="n">1</b><span>알고 싶은 것을 정한다 → 의문사(What · Where · When · Who …)가 <b>맨 앞</b></span></li><li><b class="n">2</b><span>2번 자리(will · did · has · can)가 <b>주어 앞</b>으로 점프 — 비어 있으면 do를 부른다</span></li><li><b class="n">3</b><span>물어본 자리는 비우고, 동사는 원형 (단, 주어를 물으면 점프 없음)</span></li></ol>`;
      rp.innerHTML = `<h3>평서문</h3><div class="kos">${esc(plain(parse(S.st)))}<br><small>${esc(S.ko)}</small></div>`;
    } else {
      const q = S.qs[qi];
      lp.innerHTML = `<h3>무슨 일이 일어났나</h3><ol class="qsteps">${q.steps.map((s, j) => `<li style="animation-delay:${0.5 + j * 0.5}s"><b class="n">${j + 1}</b><span>${md(s)}</span></li>`).join('')}</ol>`;
      rp.innerHTML = `<h3>질문</h3><div class="kos"><b>${esc(plain(parse(q.q)))}</b><br><small>${esc(q.ko)}</small></div><h3 class="mt">평서문</h3><div class="kos">${esc(plain(parse(S.st)))}<br><small>${esc(S.ko)}</small></div>`;
    }
  };
  const choose = j => { if (speak) { pending = j; qi = null; draw(); } else { qi = j; pending = null; draw(); setNodes(parse(QSETS[si].qs[j].q)); } };
  const reveal = () => { if (pending == null) return; qi = pending; pending = null; draw(); setNodes(parse(QSETS[si].qs[qi].q)); };
  SLIDEKEYS = e => { if (e.key === 'Enter' && pending != null) { reveal(); return true; } return false; };
  draw(); setNodes(parse(QSETS[si].st));
}

const DR = {i: 0, rnd: false, score: 0, tried: 0};
function buildDrill(el) {
  head(el, '연습 ③', '문장 키우기 드릴', '한국어 뜻을 보고 영어 블록을 순서대로 누르세요. <b style="color:var(--good)">NEW</b> = 이전 문장에 새로 붙은 조각. 어디에 들어갈까요?');
  const top = h('div', 'dr-top'), prevC = h('div', 'card dr-prev'), ko = h('div', 'card dr-ko'), zone = h('div', 'dzone'), pool = h('div', 'pool'), ctl = h('div', 'dr-ctl'), fb = h('div', 'dr-fb');
  el.append(top, prevC, ko, zone, pool, ctl, fb);
  let ans, chips, placed, done, punct;
  const load = () => {
    const st = STEPS[DR.i], to = parse(finalEn(st)), fi = fromIdx(DR.i);
    const prevNodes = st.boss ? parse(st.seq[st.seq.length - 2].en) : fi >= 0 ? parse(STEPS[fi].en) : null;
    const A = prevNodes ? keyed(prevNodes) : new Map();
    chips = chipsOf(to).map((c, j) => Object.assign(c, {id: j, nw: !!prevNodes && !!c.k && !A.has(c.k)}));
    ans = chips.map(c => c.text); punct = (plain(to).match(/[.?!]$/) || [''])[0];
    let sh = chips.slice();
    for (let t = 0; t < 8; t++) { sh = sh.map(c => [Math.random(), c]).sort((a, b) => a[0] - b[0]).map(x => x[1]); if (sh.length < 2 || sh.some((c, j) => c.text !== ans[j])) break; }
    chips = sh; placed = []; done = false; fb.textContent = ''; fb.className = 'dr-fb';
    top.innerHTML = `<span class="rpill" style="--rc:var(--${ROUNDS[st.r - 1].c})">${st.r < 8 ? 'ROUND ' + st.r : '★ BOSS'}</span><b style="color:var(--ink)">Step ${DR.i + 1}</b>` +
      '<span class="sp"></span>' +
      `<span>맞힌 문제 <b style="color:var(--ink)">${DR.score}</b> / ${DR.tried}</span>` +
      '<button class="btn sm" data-d="prev">◀</button><button class="btn sm" data-d="next">▶</button>' +
      `<button class="btn sm${DR.rnd ? ' on' : ''}" data-d="rnd">🔀 무작위</button><button class="btn sm" data-go="s${DR.i + 1}">이 Step 보기</button>`;
    prevC.innerHTML = prevNodes ? '<small>이전 문장 — 여기에 무엇이 붙거나 움직일까요?</small>' : '<small>🌱 새 씨앗 문장 — 처음부터 쌓아요</small>';
    if (prevNodes) { const s = sentEl(prevNodes); s.style.fontSize = '24px'; prevC.appendChild(s); }
    ko.innerHTML = `${esc(st.boss ? st.seq[st.seq.length - 1].ko : st.ko)}<small>위 뜻이 되도록 아래 블록을 순서대로 누르세요 · <kbd>Enter</kbd> 확인 · <kbd>Backspace</kbd> 되돌리기</small>`;
    draw();
  };
  const chipEl = (c, where, j) => { const b = h('button', 'chip', esc(c.text) + (c.nw ? '<span class="nw">NEW</span>' : '')); b.style.setProperty('--rc', `var(--${c.R})`); b.dataset.w = where; b.dataset.j = j; return b; };
  const draw = (marks) => {
    zone.innerHTML = ''; pool.innerHTML = '';
    if (!placed.length) zone.appendChild(h('span', 'ph', '여기에 문장이 만들어져요'));
    placed.forEach((c, j) => { const b = chipEl(c, 'z', j); if (marks) b.classList.add(marks[j] ? 'ok' : 'bad'); zone.appendChild(b); });
    if (placed.length) zone.appendChild(h('span', 'punct', esc(punct)));
    chips.forEach((c, j) => { if (!placed.includes(c)) pool.appendChild(chipEl(c, 'p', j)); });
    ctl.innerHTML = '<button class="btn" data-d="undo">↶ 되돌리기</button><button class="btn pri" data-d="check">확인 ✓</button><button class="btn" data-d="show">정답 보기</button><button class="btn" data-d="next">다음 문제 ▶</button><button class="btn" data-d="say">🔊</button>';
  };
  const check = () => {
    if (placed.length < ans.length) { fb.className = 'dr-fb bad'; fb.textContent = `블록이 ${ans.length - placed.length}개 남았어요.`; return; }
    const marks = placed.map((c, j) => c.text === ans[j]); const ok = marks.every(Boolean);
    if (!done) { DR.tried++; if (ok) DR.score++; done = true; }
    draw(marks); fb.className = 'dr-fb ' + (ok ? 'ok' : 'bad');
    fb.textContent = ok ? '정답! 🎉 ' + plain(parse(finalEn(STEPS[DR.i]))) : '빨간 블록의 자리를 다시 생각해 보세요. 힌트: 주어 바로 뒤 = 2번 자리';
  };
  const go = d => { DR.i = DR.rnd ? Math.floor(Math.random() * STEPS.length) : (DR.i + d + STEPS.length) % STEPS.length; load(); };
  el.addEventListener('click', e => {
    const c = e.target.closest('.chip');
    if (c) { const j = +c.dataset.j; if (c.dataset.w === 'p') placed.push(chips[j]); else placed.splice(j, 1); draw(); return; }
    const b = e.target.closest('[data-d]'); if (!b) return;
    const a = b.dataset.d;
    if (a === 'undo') { placed.pop(); draw(); }
    else if (a === 'check') check();
    else if (a === 'show') { placed = ans.map((t, j) => chips.filter(c => c.text === t)[ans.slice(0, j).filter(x => x === t).length]); done = true; draw(placed.map(() => true)); fb.className = 'dr-fb'; fb.textContent = '정답을 보고 소리 내어 한 번 읽어 보세요.'; }
    else if (a === 'next') go(1);
    else if (a === 'prev') go(-1);
    else if (a === 'rnd') { DR.rnd = !DR.rnd; load(); }
    else if (a === 'say') say(plain(parse(finalEn(STEPS[DR.i]))));
  });
  SLIDEKEYS = e => {
    if (e.key === 'Enter') { check(); return true; }
    if (e.key === 'Backspace') { placed.pop(); draw(); return true; }
    return false;
  };
  load();
}

function buildSummary(el) {
  head(el, '정리', '한 장 요약 — 영어 문장이 자라는 규칙', '왼쪽 세 줄이면 충분해요. 오른쪽 Round를 누르면 그 계단으로 이동합니다.');
  const row = h('div', 'row2'); row.style.gridTemplateColumns = '1fr 1.15fr'; el.appendChild(row);
  row.appendChild(h('div', 'cards', `
    <div class="card" style="border-top:4px solid var(--S)"><h4>① 주어 ↔ 동사는 한 몸</h4>동사의 <b>모양</b>(일치 · 시제)은 주어가 정하고, 목적어는 동사의 <b>뜻</b>을 완성해요. 주어가 길어져도 동사는 진짜 주어를 찾아가요.</div>
    <div class="card" style="border-top:4px solid var(--Q)"><h4>② 틀 · 의도 먼저, 무거운 내용은 뒤로</h4>질문 · 부정 · 판단 · 화제는 앞(Do · I don't think · It is important). 긴 설명 · 조건 · 시간 · 장소는 뒤.</div>
    <div class="card" style="border-top:4px solid var(--H)"><h4>③ 2번 자리</h4>주어 바로 뒤 한 칸 — <b>넣기</b>(will · can · have · be) · <b>not 붙이기</b> · <b>점프</b>(질문 · 도치) · 비어 있으면 <b>do</b>를 부른다.</div>`));
  const r = h('div', 'sumr'); row.appendChild(r);
  ROUNDS.forEach((R, ri) => {
    const first = STEPS.findIndex(s => s.r === ri + 1);
    const b = h('button', '', `<b>${ri < 7 ? 'Round ' + (ri + 1) : '★ Boss'} · ${esc(R.t)}</b><span>${esc(R.rule)}</span>`);
    b.style.setProperty('--rc', `var(--${R.c})`); b.dataset.go = 's' + (first + 1); r.appendChild(b);
  });
}

function buildHonest(el) {
  head(el, '솔직한 메모', '이 비유가 맞는 곳과 조심할 곳', '동료들이 “정말 그래요?”라고 물을 때를 위한 페이지.');
  const c = h('div', 'cards'); c.style.gridTemplateColumns = '1fr 1fr'; el.appendChild(c);
  c.innerHTML = `
    <div class="card" style="border-top:4px solid var(--good)"><h4>✔ 맞는 부분 — 주어 ↔ 동사의 끈은 진짜 있어요</h4><ul>
      <li>일치: I <b>am</b> / She <b>is</b> / They <b>are</b> — 동사(정확히는 2번 자리 단어)가 주어를 보고 모양을 바꿔요.</li>
      <li>시제 · 부정 · 질문 · 짧은 대답이 모두 ‘주어 + 2번 자리’에서 일어나요.</li></ul></div>
    <div class="card" style="border-top:4px solid var(--rev)"><h4>⚠ 조심 — 뜻으로는 동사 + 목적어도 끈끈해요</h4><ul>
      <li>언어학에서는 V + O를 한 덩어리(동사구, VP)로 봐요: <i>make a decision, take a break</i>. 관용구도 대부분 V + O (<i>kick the bucket</i>).</li>
      <li>그래서 정확한 말: <b>주어는 동사의 ‘모양’을, 목적어는 동사의 ‘뜻’을 완성한다.</b></li></ul></div>
    <div class="card" style="border-top:4px solid var(--rev)"><h4>⚠ 조심 — ‘중요한 것 먼저’ = ‘틀 먼저’</h4><ul>
      <li>질문 · 부정 · 판단 같은 <b>틀</b>은 앞에 오지만, 길고 새로운 정보는 오히려 <b>뒤로</b> 가요 (end-weight · end-focus): <i>It is important <b>to practice every day</b>.</i></li>
      <li>한국어가 ‘중요한 걸 뒤에 둔다’기보다, 한국어는 핵심(서술어)이 끝에 오는 <b>head-final</b>, 영어는 핵심이 앞에 오는 <b>head-initial</b> 언어 — 그래서 거울처럼 뒤집혀요.</li></ul></div>
    <div class="card" style="border-top:4px solid var(--H)"><h4>🧠 Self-attention과 실제 연구</h4><ul>
      <li>BERT의 attention head 중에는 ‘목적어 → 동사’, ‘한정사 → 명사’처럼 문법 관계를 따라가는 head가 있어요 (Clark et al., 2019).</li>
      <li>주어-동사 일치(<i>The keys to the cabinet <b>are</b> …</i>)는 언어 모델의 문법 능력을 시험하는 대표 과제예요 (Linzen et al., 2016; Goldberg, 2019).</li>
      <li>이 자료의 곡선 두께는 <b>설명용 그림</b>이에요. 실제 모델의 attention 값이 아니고, attention 하나가 곧 ‘문법’도 아니에요.</li></ul></div>`;
  el.appendChild(h('div', 'refs', 'Clark, Khandelwal, Levy & Manning (2019) What Does BERT Look At? An Analysis of BERT’s Attention · Linzen, Dupoux & Goldberg (2016) Assessing the Ability of LSTMs to Learn Syntax-Sensitive Dependencies · Goldberg (2019) Assessing BERT’s Syntactic Abilities'));
}

function buildMethods(el) {
  head(el, '수업 운영 제안', '동료 스터디에서 이렇게 써 보세요', '한 번에 Round 1~2개씩, 15분 설명 + 15분 게임이 적당해요.');
  const c = h('div', 'cards'); c.style.gridTemplateColumns = '1fr 1fr 1fr'; el.appendChild(c);
  c.innerHTML = `
    <div class="card"><h4>🔁 문장 키우기 릴레이 (5분)</h4>한 사람이 <i>I am a student.</i> → 다음 사람이 한 조각 추가·변형. 틀리면 다른 사람이 ‘몇 번 자리’가 틀렸는지 짚어 주기.</div>
    <div class="card"><h4>⏱ 2번 자리 5초 변신</h4>진행자가 문장을 말하고 “부정!” “질문!” “짧은 대답!” “What!”을 외치면 5초 안에 바꾸기. 정답은 <a data-go="seat" href="#seat">변신 기계</a>로 확인.</div>
    <div class="card"><h4>🗣 주어 + 동사 먼저 내뱉기</h4>말을 시작할 때 <i>I think… / I want to… / We need to…</i>처럼 S + V부터 말하고, 나머지는 생각하면서 덧붙이기. 한국어 문장을 다 만들고 번역하지 않기.</div>
    <div class="card"><h4>🪞 거울 읽기</h4>내 한국어 문장을 ‘주어 뒤부터 거꾸로’ 읽기: 나는 / 3년 동안 / 회사에서 / 영어를 / 공부해 / 왔다 → I / have / studied / English / at work / for three years.</div>
    <div class="card"><h4>💬 회의 틀 문장 6개</h4><i>Do you think…? · I don't think… · It is important to… · What do you think? · Can you tell me what…? · If we…, we will…</i></div>
    <div class="card"><h4>✉️ 메일 첫 문장 = 의도</h4><i>I'm writing to ask… · Could you…? · I wanted to let you know…</i> 영어 메일도 의도부터. 세부는 둘째 문단으로.</div>`;
  el.appendChild(h('div', 'links', '<span style="font-size:13.5px;color:var(--muted);align-self:center">더 깊이 — 같은 폴더의 영어 구문 지도 101:</span>' + ulinks(['U03', 'U17', 'U29', 'U64', 'U94'])));
}

// ---------------------------------------------------------------- slide list
const SL = [];
const add = (id, title, build) => SL.push({id, title, build});
add('cover', '문장이 자란다', buildCover);
add('mirror', '한국어와 영어는 거울', buildMirror);
add('p1', '원칙 ① 주어 ↔ 동사는 한 몸', buildP1);
add('p2', '원칙 ② 의도 · 틀이 먼저', buildP2);
add('seat', '제안: 2번 자리', buildSeat);
add('map', '문장 계단 지도', buildMap);
STEPS.forEach((st, i) => add('s' + (i + 1), `Step ${i + 1} · ${stepText(i)}`, el => buildStep(el, i)));
add('switch', '연습 ① 주어 스위치', buildSwitch);
add('ask', '연습 ② 의도 먼저 질문 만들기', buildAsk);
add('drill', '연습 ③ 문장 키우기 드릴', buildDrill);
add('summary', '한 장 요약', buildSummary);
add('honest', '솔직한 메모', buildHonest);
add('methods', '수업에서 이렇게', buildMethods);
const IDX = Object.fromEntries(SL.map((s, i) => [s.id, i]));

// ---------------------------------------------------------------- navigation
const canvas = $('#canvas');
const store = {get(k, d) { try { const v = localStorage.getItem('grow.' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem('grow.' + k, JSON.stringify(v)); } catch (e) { /* private mode */ } }};
const PREF = Object.assign({arcs: true, mirror: true, labels: true}, store.get('prefs', {}));
let cur = 0;
function applyPrefs() {
  document.body.classList.toggle('no-arcs', !PREF.arcs); document.body.classList.toggle('no-mirror', !PREF.mirror); document.body.classList.toggle('nolab', !PREF.labels);
  $('#nArc').classList.toggle('off', !PREF.arcs); $('#nKo').classList.toggle('off', !PREF.mirror); $('#nLab').classList.toggle('off', !PREF.labels);
  store.set('prefs', PREF);
}
function toggle(k) { PREF[k] = !PREF[k]; applyPrefs(); if (k === 'labels' && ACTIVE) ACTIVE.stage.overlays(); }
function fitCanvas() { SCALE = Math.min(innerWidth / 1280, (innerHeight - 46) / 720); canvas.style.transform = `translate(-50%,-50%) scale(${SCALE})`; }
function show(i, noHash) {
  i = Math.max(0, Math.min(SL.length - 1, i));
  clearTimers(); SLIDEKEYS = null; ACTIVE = null;
  try { if ('speechSynthesis' in window) speechSynthesis.cancel(); } catch (e) { /* ignore */ }
  cur = i; canvas.innerHTML = '';
  const el = h('div', 'slide'); canvas.appendChild(el);
  CTX = SL[i].id;
  try { SL[i].build(el); } catch (e) { warn('build error: ' + e.message); el.appendChild(h('pre', '', esc(e.stack || e.message))); }
  $('#nCnt').textContent = `${i + 1} / ${SL.length}`; $('#nTtl').textContent = SL[i].title;
  $('#bar').style.width = ((i + 1) / SL.length * 100) + '%';
  if (!noHash && !SELFTEST) { try { history.replaceState(null, '', '#' + SL[i].id); } catch (e) { location.hash = SL[i].id; } }
  store.set('last', SL[i].id);
}
function go(id) { if (IDX[id] != null) show(IDX[id]); }
canvas.addEventListener('click', e => {
  const g = e.target.closest('[data-go]'); if (g) { e.preventDefault(); go(g.dataset.go); return; }
  const d = e.target.closest('[data-drill]'); if (d) { DR.i = +d.dataset.drill; go('drill'); return; }
  const a = e.target.closest('[data-a]'); if (!a) return;
  if (a.dataset.a === 'replay') replay(); else if (a.dataset.a === 'say' && ACTIVE) say(ACTIVE.spec.say);
});
$('#nPrev').onclick = () => show(cur - 1); $('#nNext').onclick = () => show(cur + 1); $('#nMap').onclick = () => go('map');
$('#nArc').onclick = () => toggle('arcs'); $('#nKo').onclick = () => toggle('mirror'); $('#nLab').onclick = () => toggle('labels');
function cycleTheme() { const r = document.documentElement, t = r.dataset.theme; r.dataset.theme = t === 'dark' ? 'light' : t === 'light' ? '' : 'dark'; if (!r.dataset.theme) delete r.dataset.theme; store.set('theme', r.dataset.theme || ''); }
$('#nTheme').onclick = cycleTheme;
function full() { try { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen(); } catch (e) { /* not allowed */ } }
$('#nFull').onclick = full;
$('#nGo').addEventListener('keydown', e => {
  if (e.key !== 'Enter') return; const v = e.target.value.trim(); e.target.value = ''; e.target.blur();
  if (/^\d+$/.test(v) && +v >= 1 && +v <= STEPS.length) go('s' + v); else if (IDX[v] != null) go(v);
});
document.addEventListener('keydown', e => {
  if (e.target.closest('input,textarea') || e.ctrlKey || e.metaKey || e.altKey) return;
  if (SLIDEKEYS && SLIDEKEYS(e)) { e.preventDefault(); return; }
  const k = e.key;
  if (k === 'ArrowRight' || k === 'PageDown' || k === ' ') { e.preventDefault(); show(cur + 1); }
  else if (k === 'ArrowLeft' || k === 'PageUp') { e.preventDefault(); show(cur - 1); }
  else if (k === 'Home') show(0); else if (k === 'End') show(SL.length - 1);
  else if (k === 'r' || k === 'R') replay();
  else if (k === 'a' || k === 'A') toggle('arcs'); else if (k === 'k' || k === 'K') toggle('mirror'); else if (k === 'l' || k === 'L') toggle('labels');
  else if (k === 'm' || k === 'M') go('map'); else if (k === 't' || k === 'T') cycleTheme(); else if (k === 'f' || k === 'F') full();
  else if ((k === 'd' || k === 'D') && /^s\d+$/.test(SL[cur].id)) { DR.i = +SL[cur].id.slice(1) - 1; go('drill'); }
});
addEventListener('resize', () => { fitCanvas(); if (ACTIVE && !NOANIM) ACTIVE.stage.overlays(); });
addEventListener('hashchange', () => { const id = location.hash.slice(1); if (IDX[id] != null && IDX[id] !== cur) show(IDX[id], true); });

// ---------------------------------------------------------------- self-test (?selftest): data checks + render every slide
function dataChecks() {
  const norm = s => s.replace(/[\s.,?!]/g, '');
  STEPS.forEach((st, i) => {
    CTX = 's' + (i + 1);
    const layers = st.boss ? st.seq : [st];
    layers.forEach((L, j) => {
      let ns; try { ns = parse(L.en); } catch (e) { warn(e.message); return; }
      const ids = new Set(); (function rec(xs) { xs.forEach(n => { if (n.t === 'blk') { if (n.id) { if (ids.has(n.id)) warn('duplicate id ' + n.id); ids.add(n.id); } rec(n.kids); } }); })(ns);
      if (L.seat && !ids.has(L.seat)) warn('seat id missing ' + L.seat);
      parseArcs(L.arcs || '').forEach(([a, b]) => { if (!ids.has(a) || !ids.has(b)) warn(`arc id missing ${a}-${b}`); });
      const km = parseKm(L.km || '');
      km.forEach(([, k]) => k.forEach(x => { if (!ids.has(x)) warn('km id missing ' + x); }));
      const kj = km.filter(c => !c[0].startsWith('(')).map(c => c[0].replace(/^[①-⑳]\s*/, '')).join('');
      if (norm(kj) !== norm(L.ko)) warn(`km/ko mismatch${st.boss ? ' layer ' + (j + 1) : ''}: "${kj}" vs "${L.ko}"`);
    });
    const fi = fromIdx(i); if (st.from && (fi < 0 || fi >= i)) warn('bad from ' + st.from);
    (st.units || []).forEach(u => { if (!UNITS[u]) warn('unknown unit ' + u); });
  });
  QSETS.forEach((S, a) => { CTX = 'ask' + a; try { parse(S.st); S.qs.forEach(q => parse(q.q)); } catch (e) { warn(e.message); } });
  CTX = '';
}
function selftest() {
  dataChecks();
  const report = [];
  SL.forEach((s, i) => {
    show(i, true);
    const el = canvas.firstChild;
    if (el.scrollHeight > el.clientHeight + 2) warn(`slide overflow ${el.scrollHeight - el.clientHeight}px`);
    $$('.pane, .card', el).forEach(p => { if (p.scrollHeight > p.clientHeight + 2) warn(`overflow in .${p.className.replace(/ /g, '.')} by ${p.scrollHeight - p.clientHeight}px`); });
    $$('.host', el).forEach(hs => { const st = hs.querySelector('.sent'); if (st && st.offsetWidth > hs.clientWidth + 2) warn('sentence wider than stage'); });
    report.push(s.id);
  });
  const out = $('#stout'); out.hidden = false;
  out.textContent = `SELFTEST ${WARN.length ? 'WARN ' + WARN.length : 'OK'} — ${SL.length} slides\n` + WARN.join('\n');
  document.title = WARN.length ? 'SELFTEST WARN ' + WARN.length : 'SELFTEST OK';
}

// ---------------------------------------------------------------- start
(function init() {
  const th = store.get('theme', ''); if (th) document.documentElement.dataset.theme = th;
  fitCanvas(); applyPrefs();
  if (SELFTEST) { selftest(); return; }
  const h0 = location.hash.slice(1), last = store.get('last', 'cover');
  show(IDX[h0] != null ? IDX[h0] : IDX[last] != null ? IDX[last] : 0, IDX[h0] == null);
})();
