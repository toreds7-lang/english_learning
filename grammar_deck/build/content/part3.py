# PART 3 수식어구의 이해 — CH09–CH10, Unit 51–59
PART = dict(
    id="P3", no=3, title="수식어구의 이해", en="Adding Detail: Modifiers", color="#b45309",
    big="수식어(M)는 문장의 **살** — 명사에 붙으면 형용사 역할, 문장에 붙으면 부사 역할.",
    pts=[
        "CH09: to-v와 분사(v-ing / p.p.)가 **명사를 꾸미고**(형용사적) **문장을 꾸민다**(부사적).",
        "CH10: 부사절을 줄인 **분사구문** — 접속사와 주어를 빼고 v-ing로.",
    ],
    viz=dict(t="rows", h="M이 붙는 두 곳", rows=[
        ["명사 수식", "[S @n(The girl) [M>n *dancing* on stage]] [V is] [C my sister].", "형용사 역할", "U52"],
        ["명사 수식", "[S I] [V need] [O a @n(friend) [M>n *to talk to*]].", "형용사 역할", "U51"],
        ["문장 수식", "[M *To catch* the bus], [S he] [V ran].", "부사 역할", "U54"],
        ["문장 수식", "[M *Seeing* me], [S she] [V smiled].", "분사구문", "U57"],
    ]),
)

CHAPTERS = [
# ------------------------------------------------------------------ CH09
dict(
    id="C09", no=9, title="수식어구: to부정사/분사",
    big="to-v 하나가 **명사 · 형용사 · 부사** 세 가지 역할을 한다 — 자리를 보면 역할이 보인다.",
    pts=[
        "명사 뒤 to-v → **형용사**(~할) / 문장 앞·뒤 to-v → **부사**(~하기 위해, ~해서)",
        "분사: v-ing = **능동·진행**(~하는), p.p. = **수동·완료**(~된)",
    ],
    viz=dict(t="table", h="to-v의 세 가지 얼굴", head=["역할", "자리", "뜻", "예", "단원"], rows=[
        ["명사", "S · O · C", "~하는 것", "*To read* is fun.", "U08 · U15 · U22"],
        ["형용사", "명사 뒤", "~할, ~하는", "a book *to read*", "U51"],
        ["부사", "문장 앞·뒤, 형용사 뒤", "~하기 위해, ~해서", "I came *to see* you.", "U54 · U55"]]),
    items=[
        dict(id="U51", title="to부정사의 형용사적 수식", sub="명사 + to-v: ~할, ~하는",
             f="명사 ← to-v (+ 전치사)",
             pts=[
                 "**명사 + to-v**: ~할, ~하는 (명사를 뒤에서 꾸민다).",
                 "전치사에 주의: a chair to sit **on**, a pen to write **with**, friends to talk **to** (명사가 전치사의 목적어)",
                 "**be to-v** 용법: 예정 · 의무 · 가능 · 운명 · 의도 (We *are to meet* at five.)",
             ],
             viz=dict(t="morph", steps=[
                 ["[V#v sit] [M#p on] [O#n a chair]", "sit on a chair (의자에 앉다)"],
                 ["[O#n @c(a chair)] [M>c [v#t to] [v#v sit] [m#p on]]", "a chair to sit on — on을 빠뜨리면 안 된다"],
             ]),
             ex=[
                 ("[S I] [V have] [O a lot of @n(homework) [M>n *to do*]] [M tonight].", "오늘 밤 *해야 할* 숙제가 많다."),
                 ("[S She] [V needs] [O @n(someone) [M>n *to talk to*]].", "그녀는 *이야기를 나눌* 누군가가 필요하다."),
                 ("[S We] [V *are to meet*] [M in front of the gym] [M at noon].", "우리는 정오에 체육관 앞에서 *만날 예정이다*."),
             ],
             chk=[dict(q="빈칸에 알맞은 것은?", s="He has no house to live ___.", o=["(필요 없음)", "in"], a=1,
                       w="live **in** a house → a house to live **in**.")],
             ln=["FS02", "U52", "U64", "U54"]),
        dict(id="U52", title="분사(v-ing/p.p.)의 형용사적 수식", sub="~하는(v-ing) / ~된(p.p.) + 명사",
             f="v-ing / p.p. + 명사  ·  명사 ← v-ing / p.p. + 어구",
             pts=[
                 "**v-ing**: 능동·진행 '~하는, ~하고 있는' (a *crying* baby)",
                 "**p.p.**: 수동·완료 '~된, ~당한' (a *broken* window, *fallen* leaves)",
                 "혼자면 명사 **앞**, 다른 어구와 함께 길어지면 명사 **뒤**: the man *standing at the door*",
             ],
             viz=dict(t="compare", cols=2, cards=[
                 dict(h="v-ing — 능동 (개가 짖는다)", s="a [M>n *barking*] @n(dog)"),
                 dict(h="p.p. — 수동 (자전거가 도난당했다)", s="a [M>n *stolen*] @n(bike)"),
                 dict(h="길면 뒤로 (v-ing)", s="the @n(boy) [M>n *wearing* a cap]"),
                 dict(h="길면 뒤로 (p.p.)", s="a @n(car) [M>n *made* in Korea]"),
             ]),
             ex=[
                 ("[S @n(The boy) [M>n *wearing* a red cap]] [V is] [C my brother].", "빨간 모자를 *쓰고 있는* 소년은 내 남동생이다."),
                 ("[S I] [V bought] [O a @n(car) [M>n *made* in Korea]].", "나는 한국에서 *만들어진* 차를 샀다."),
                 ("[S The [m>n *fallen*] @n(leaves)] [V covered] [O the path].", "*떨어진* 낙엽이 길을 덮었다."),
             ],
             chk=[dict(q="빈칸에 알맞은 것은?", s="There are many people ___ for the bus.", o=["waiting", "waited"], a=0,
                       w="사람들이 **기다리는**(능동) → waiting.")],
             ln=["U51", "U53", "U24", "U25", "U67"]),
        dict(id="U53", title="감정분사(v-ing/p.p.)의 형용사적 수식", sub="감정을 주는 쪽 v-ing / 느끼는 쪽 p.p.",
             f="감정을 주는 쪽 → v-ing · 느끼는 쪽 → p.p.",
             pts=[
                 "감정을 **일으키는** 쪽 → v-ing: boring · exciting · surprising · disappointing",
                 "감정을 **느끼는** 쪽 → p.p.: bored · excited · surprised · disappointed",
                 "'사물이면 v-ing, 사람이면 p.p.'가 아니다 — **관계**를 보라! (He is boring = 그가 남을 지루하게 한다)",
             ],
             viz=dict(t="emotion", src="The lecture", dst="the students", verb="bores →", ing="a boring lecture", pp="bored students"),
             ex=[
                 ("[S It] [V was] [C an *exciting* game].", "*흥미진진한* 경기였다."),
                 ("[S The *bored* students] [V looked] [M out the window].", "*지루해진* 학생들은 창밖을 내다보았다."),
                 ("[S I] [V heard] [O some *surprising* news] [M from my friend].", "나는 친구에게서 *놀라운* 소식을 들었다."),
             ],
             chk=[dict(q="빈칸에 알맞은 것은?", s="I was ___ to hear the news.", o=["shocking", "shocked"], a=1,
                       w="내가 충격을 **느끼는** 쪽 → shocked.")],
             tip="interesting / interested, confusing / confused 고르기는 어법 문제 단골. '누가 누구에게 감정을 주나' 화살표를 그려 보자.",
             ln=["U52", "FS08"]),
        dict(id="U54", title="to부정사의 부사적 수식 Ⅰ", sub="목적 · 감정의 원인 · 판단의 근거",
             f="(문장) + to-v = 목적 / 감정의 원인 / 판단 근거",
             pts=[
                 "**목적**: ~하기 위해 (= in order to · so as to) — 가장 흔하다.",
                 "**감정의 원인**: glad · happy · sorry · surprised + to-v (~해서)",
                 "**판단의 근거**: must be ~ + to-v (~하다니) — He must be smart *to solve* it.",
             ],
             viz=dict(t="rows", h="to-v 앞에 '왜?'를 넣어 보자", rows=[
                 ["목적", "[S I] [V went] [A to the store] [M to buy milk].", "왜 갔어? → 사려고"],
                 ["감정의 원인", "[S I] [V am] [C glad] [M to see you].", "왜 기뻐? → 만나서"],
                 ["판단 근거", "[S He] [V must be] [C rich] [M to buy that].", "왜 그렇게 생각해? → 그걸 사다니"],
             ]),
             ex=[
                 ("[S She] [V got up] [M early] [M *to catch* the first train].", "그녀는 첫 기차를 *타기 위해* 일찍 일어났다."),
                 ("[S I] [V was] [C surprised] [M *to see* my old teacher] [M at the concert].", "나는 콘서트에서 옛 선생님을 *뵙고* 놀랐다."),
                 ("[S He] [V must be] [C brave] [M *to say* that] [M in front of everyone].", "모두 앞에서 그런 말을 *하다니* 그는 용감한 게 틀림없다."),
             ],
             chk=[dict(q="밑줄 친 to-v의 의미는?", s="We were happy *to win* the game.", o=["목적", "감정의 원인", "결과"], a=1,
                       w="happy(감정) + to-v → **감정의 원인**: 이겨서 기뻤다.")],
             ln=["U55", "U56", "U51", "U79", "U16"]),
        dict(id="U55", title="to부정사의 부사적 수식 Ⅱ", sub="결과 · 형용사 수식 · 조건",
             f="결과 (only to / never to) · 형용사 + to-v",
             pts=[
                 "**결과**: (~해서 결국) ~하다 — grew up *to be*, only *to fail*(결국 ~하고 말았다), never *to return*",
                 "**형용사 수식**: easy *to use*, hard *to please*, dangerous *to swim in* — 형용사의 범위를 정해 준다.",
                 "**조건**: *To hear* him speak, you'd think he was a teacher. (= If you heard ~)",
             ],
             viz=dict(t="morph", steps=[
                 ["[S{가주어} It] [V#v is] [C#c hard] [S#t{진주어} to solve [o#q this problem]].", "가주어 구문 (U11)"],
                 ["[S#q This problem] [V#v is] [C#c hard] [M#t to solve].", "to-v의 목적어를 주어로 → 형용사 + to-v"],
             ]),
             ex=[
                 ("[S The little girl] [V grew up] [M *to be* a famous scientist].", "그 어린 소녀는 자라서 유명한 과학자가 *되었다*."),
                 ("[S He] [V ran] [A to the station], [M *only to find* the train gone].", "그는 역으로 달려갔지만 *결국* 기차가 떠난 것을 *알게 되었다*."),
                 ("[S This math problem] [V is] [C hard] [M *to solve*].", "이 수학 문제는 *풀기* 어렵다."),
             ],
             chk=[dict(q="같은 뜻이 되도록 빈칸에 알맞은 것은?", s="It is difficult to please my boss. = My boss is difficult to ___.", o=["please", "please him"], a=0,
                       w="목적어(my boss)가 주어로 나갔으므로 to-v 뒤에 목적어를 **다시 쓰지 않는다**.")],
             tip="This problem is hard to solve **it** ✘ — 주어로 나간 목적어를 다시 쓰면 틀린다.",
             ln=["U54", "U56", "U11"]),
        dict(id="U56", title="to부정사가 만드는 주요 구문", sub="too ~ to · enough to · 독립부정사",
             f="too + 형/부 + to-v ↔ so ~ that S can't · 형/부 + enough + to-v",
             pts=[
                 "**too + 형/부 + to-v**: 너무 ~해서 …할 수 없다 (= so ~ that S can't)",
                 "**형/부 + enough + to-v**: …할 만큼 충분히 ~하다 (= so ~ that S can)",
                 "**독립부정사**: to be honest · to tell the truth · needless to say · to make matters worse · strange to say",
             ],
             viz=dict(t="morph", steps=[
                 ["[S#s The coffee] [V#v is] [C#c *too* hot] [X#f{의미상 주어} for me] [M#t *to drink*].", "too ~ to-v"],
                 ["[S#s The coffee] [V#v is] [C#c *so* hot] [M#t that [s I] [v *can't* drink] [o it]].", "= so ~ that S can't (목적어 it을 다시 쓴다)"],
             ]),
             ex=[
                 ("[S The box] [V was] [C *too* heavy] [X{의미상 주어} for me] [M *to lift*].", "그 상자는 *너무* 무거워서 내가 들 *수 없었다*."),
                 ("[S She] [V is] [C old *enough*] [M *to get* a driver's license].", "그녀는 운전면허를 *딸 만큼 충분히* 나이가 들었다."),
                 ("[M *To be honest*], [S I] [V didn't read] [O the book].", "*솔직히 말하면*, 나는 그 책을 읽지 않았다."),
             ],
             chk=[dict(q="같은 뜻이 되도록 빈칸에 알맞은 것은?", s="He is too young to watch the movie. = He is so young that he ___ watch the movie.", o=["can", "can't"], a=1,
                       w="too ~ to-v = so ~ that S **can't**.")],
             tip="enough의 위치: 형용사·부사 **뒤**(old enough), 명사 **앞**(enough money).",
             ln=["U54", "U55", "U12", "U79"]),
    ]),
# ------------------------------------------------------------------ CH10
dict(
    id="C10", no=10, title="분사구문",
    big="분사구문 = **부사절을 줄인 것** — 접속사와 (같은) 주어를 빼고, 동사를 v-ing로.",
    pts=[
        "뜻(시간 · 이유 · 조건 · 양보 · 동시동작)은 **문맥**으로 판단 — 접속사를 다시 넣어 보면 보인다.",
        "주어가 다르면 남기고(독립분사구문), 수동이면 (Being) p.p., 먼저 일어났으면 Having p.p.",
    ],
    viz=dict(t="morph", h="분사구문 만들기 3단계 (「다음 단계 ▶」)", steps=[
        ["[M#a [x#c When] [s#s she] [v#v saw] [o#o me]], [S#t she] [V#w smiled].", "부사절 + 주절"],
        ["[M#a [s#s she] [v#v saw] [o#o me]], [S#t she] [V#w smiled].", "① 접속사 When을 뺀다"],
        ["[M#a [v#v saw] [o#o me]], [S#t she] [V#w smiled].", "② 주절과 같은 주어 she를 뺀다"],
        ["[M#a [v#v *Seeing*] [o#o me]], [S#t she] [V#w smiled].", "③ 동사를 v-ing로 → 분사구문 완성!"],
    ]),
    items=[
        dict(id="U57", title="분사구문의 의미", sub="시간 · 이유 · 조건 · 양보 · 동시동작 · 결과",
             f="(접속사 + S + V) → v-ing ~, S + V",
             pts=[
                 "분사구문 = 부사절을 줄인 것: **시간** · **이유** · **조건** · **양보** · **동시동작**(~하면서) · **연속·결과**(그래서 ~)",
                 "뜻은 문맥으로 판단 → 알맞은 **접속사를 넣어 보자**.",
                 "문장 뒤의 ', v-ing'는 대개 동시동작 또는 결과: ~, *making* it ~",
             ],
             viz=dict(t="table", head=["뜻", "분사구문", "= 부사절"], rows=[
                 ["시간", "*Seeing* me, she smiled.", "When she saw me"], ["이유", "*Being* tired, I slept early.", "Because I was tired"],
                 ["조건", "*Turning* left, you'll see it.", "If you turn left"], ["동시동작", "He sat, *reading* a book.", "as he read a book"],
                 ["결과", "It rained, *ruining* the trip.", "and it ruined the trip"]]),
             ex=[
                 ("[M *Feeling* tired], [S I] [V went] [A to bed] [M early].", "*피곤해서* 나는 일찍 잠자리에 들었다. (이유)"),
                 ("[M *Walking* along the beach], [S we] [V talked] [M about our future].", "해변을 *걸으며* 우리는 미래에 대해 이야기했다. (동시동작)"),
                 ("[S The bus] [V broke down], [M *making* us late for school].", "버스가 고장 나서 *그 바람에* 우리는 학교에 지각했다. (결과)"),
             ],
             chk=[dict(q="밑줄 친 분사구문의 의미는?", s="*Turning* left, you will find the bank.", o=["이유", "조건", "양보"], a=1,
                       w="= **If you turn left** (왼쪽으로 돌면) → 조건.")],
             ln=["U58", "U59", "U73", "U75", "U76"]),
        dict(id="U58", title="주의해야 할 분사구문의 형태", sub="Not v-ing · Having p.p. · (Being) p.p. · 접속사 + v-ing",
             f="Not v-ing · Having p.p. · (Being) p.p. · 접속사 + v-ing",
             pts=[
                 "**부정**: Not / Never를 분사 **앞에**: *Not knowing* what to say, ~",
                 "**완료형** Having p.p.: 주절보다 **먼저** 일어난 일 / **수동형** (Being) p.p.: Being은 흔히 생략 → p.p.로 시작",
                 "뜻을 분명히 하려고 **접속사를 남기기도** 한다: *While* reading, ~ / *When* asked, ~",
             ],
             viz=dict(t="table", h="모양 정리 (U43 표와 같은 구조!)", head=["", "능동", "수동"], rows=[
                 ["단순", "*Seeing*", "(Being) *seen*"], ["완료 (먼저 일어남)", "*Having seen*", "(Having been) *seen*"], ["부정", "*Not seeing*", "*Not seen*"]]),
             ex=[
                 ("[M *Not knowing* what to say], [S she] [V kept] [C silent].", "무슨 말을 해야 할지 *몰라서* 그녀는 침묵을 지켰다."),
                 ("[M *Having finished* my homework], [S I] [V went out] [M to play].", "숙제를 *끝낸 후* 나는 놀러 나갔다."),
                 ("[M *Written* in simple English], [S the book] [V is] [C easy] [M to read].", "쉬운 영어로 *쓰여 있어서* 그 책은 읽기 쉽다."),
             ],
             chk=[dict(q="빈칸에 알맞은 것은?", s="___ from space, the earth looks blue.", o=["Seeing", "Seen"], a=1,
                       w="지구가 우주에서 **보이는**(수동) → (Being) **Seen**.")],
             tip="분사구문 맨 앞 v-ing / p.p. 고르기: **주절의 주어**가 그 동작을 하는지(v-ing), 당하는지(p.p.)를 보라.",
             ln=["U57", "U43", "U31", "U59"]),
        dict(id="U59", title="주의해야 할 분사구문의 의미상의 주어", sub="독립분사구문 · with + O + 분사 · 비인칭 독립분사구문",
             f="S' + v-ing ~, S + V · with + O + v-ing / p.p.",
             pts=[
                 "분사구문의 주어 ≠ 주절의 주어 → 분사 앞에 **주어를 남긴다** (독립분사구문): *The weather being* nice, we went out.",
                 "**with + O + v-ing / p.p.**: ~한 채로, ~하면서 — O와 분사의 관계는 O.C.처럼 능동(v-ing) / 수동(p.p.)",
                 "비인칭 독립분사구문: generally speaking · frankly speaking · judging from · considering",
             ],
             viz=dict(t="compare", cols=1, cards=[
                 dict(h="with + O + v-ing — O가 ~하는 (능동)", s="[S He] [V walked] [M with [o#o his dog] [oc=o following him]].", n="개가 그를 따라오는 채로"),
                 dict(h="with + O + p.p. — O가 ~된 (수동)", s="[S He] [V listened] [M with [o#o his eyes] [oc=o closed]].", n="눈이 감긴 채로"),
             ]),
             ex=[
                 ("[M *It being* Sunday], [S the shops] [V were] [C closed].", "일요일*이어서* 가게들이 문을 닫았다."),
                 ("[S He] [V listened] [M to music] [M *with* [o#o his eyes] [oc=o *closed*]].", "그는 눈을 *감은 채로* 음악을 들었다."),
                 ("[M *Judging from* his accent], [S he] [V is] [M probably] [C from Australia].", "말투로 *판단하건대* 그는 아마 호주 출신일 것이다."),
             ],
             chk=[dict(q="빈칸에 알맞은 것은?", s="She sat on the bench with her legs ___.", o=["crossing", "crossed"], a=1,
                       w="다리가 **꼬아진**(수동) 상태 → with + O + **p.p.**")],
             ln=["U57", "U58", "U24", "U25"]),
    ]),
]
