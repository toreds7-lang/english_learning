"""Data for the history-of-English deck: videos, the four tools, and every audio clip.

Audio items are rendered by build_deck.py with Kokoro. An item has either
  text  -> Kokoro phonemizes it (en-us), or
  ph    -> Kokoro reads these phonemes as given (is_phonemes=True).
Old and Middle English clips use `ph` with reconstructed pronunciations (approximate).
Phoneme strings follow Kokoro's style: the stress mark sits right before the stressed vowel.
"""
from __future__ import annotations

# Narration voices
V_OLD = "am_michael"    # time machine + Old/Middle English samples (one voice for both stages)
V_NOW = "af_heart"      # modern words and sentences

VIDEOS = {
    "rob": {"id": "0gHE9blt0mQ", "len": "22:21", "who": "RobWords",
            "title": "The entire history of English in 22 minutes – RobWords"},
    "nab": {"id": "tsvOWRlu7_s", "len": "11:25", "who": "English with Nab",
            "title": "The history of the English language – English with Nab"},
    "gill": {"id": "aEH2GkuRIHs", "len": "21:36", "who": "engVid Gill",
             "title": "Discover the History of English – Learn English with Gill (engVid)"},
    "lugh": {"id": "Nf7GTlhve98", "len": "1:03:50", "who": "Fortress of Lugh",
             "title": "Origins of the English – Fortress of Lugh"},
}

# ---------------------------------------------------------------- time machine (c. 1400 -> today)
# grp: front = 앞 모음, back = 뒤 모음, cons = 사라진 소리
TIME_MACHINE = [
    {"w": "time", "grp": "front", "me": ("tˈiːm", "/tiːm/", "티임"), "now": ("tˈaɪm", "/taɪm/", "타임"),
     "note": "가장 높은 모음 iː가 내려오며 이중모음 aɪ가 되었다."},
    {"w": "bite", "grp": "front", "me": ("bˈiːt", "/biːt/", "비이트"), "now": ("bˈaɪt", "/baɪt/", "바이트"),
     "note": "Nab 8:20: 중세의 bite는 지금의 beet와 비슷했다."},
    {"w": "meet", "grp": "front", "me": ("mˈeːt", "/meːt/", "메에트"), "now": ("mˈiːt", "/miːt/", "미잇"),
     "note": "eː가 한 칸 올라가 iː가 되었다."},
    {"w": "meat", "grp": "front", "me": ("mˈɛːt", "/mɛːt/", "매애트"), "now": ("mˈiːt", "/miːt/", "미잇"),
     "note": "ɛː → eː → iː. 1400년에는 meet와 소리가 달라서 철자도 달랐다. 지금은 같은 소리."},
    {"w": "see", "grp": "front", "me": ("sˈeː", "/seː/", "세에"), "now": ("sˈiː", "/siː/", "시이"),
     "note": "ee = 원래 '긴 에'. 그래서 철자가 ee."},
    {"w": "sea", "grp": "front", "me": ("sˈɛː", "/sɛː/", "새애"), "now": ("sˈiː", "/siː/", "시이"),
     "note": "ea = 원래 '긴 애'. see와 sea는 1400년엔 다른 소리였다."},
    {"w": "name", "grp": "front", "me": ("nˈaːmə", "/naːmə/", "나아머"), "now": ("nˈeɪm", "/neɪm/", "네임"),
     "note": "aː → ɛː → eɪ. 끝의 -e는 소리가 사라지고 글자만 남았다. 이것이 'magic e'의 기원."},
    {"w": "great", "grp": "front", "me": ("ɡrˈɛːt", "/ɡrɛːt/", "그래애트"), "now": ("ɡɹˈeɪt", "/ɡreɪt/", "그레잇"),
     "note": "예외: ea인데 iː까지 가지 않고 eɪ에서 멈췄다 (great, break, steak)."},
    {"w": "house", "grp": "back", "me": ("hˈuːs", "/huːs/", "후우스"), "now": ("hˈaʊs", "/haʊs/", "하우스"),
     "note": "uː → aʊ. ou라는 철자는 노르만 서기의 프랑스식 표기(OE hūs)."},
    {"w": "out", "grp": "back", "me": ("ˈuːt", "/uːt/", "우우트"), "now": ("ˈaʊt", "/aʊt/", "아웃"),
     "note": "house와 같은 길. 스코틀랜드 방언에는 지금도 'oot'가 남아 있다."},
    {"w": "boot", "grp": "back", "me": ("bˈoːt", "/boːt/", "보오트"), "now": ("bˈuːt", "/buːt/", "부웃"),
     "note": "oː → uː. 그래서 oo가 '우'로 읽힌다 (food, moon, goose)."},
    {"w": "boat", "grp": "back", "me": ("bˈɔːt", "/bɔːt/", "보오트 (입을 크게)"), "now": ("bˈoʊt", "/boʊt/", "보웃"),
     "note": "ɔː → oː → oʊ. oa = 원래 '입을 크게 벌린 오'."},
    {"w": "knight", "grp": "cons", "me": ("knˈɪçt", "/kniçt/", "크니히트"), "now": ("nˈaɪt", "/naɪt/", "나잇"),
     "note": "k는 1600년대에, gh(ç '히' 소리)는 1400~1600년대에 사라졌다. 글자만 남았다."},
    {"w": "walk", "grp": "cons", "me": ("wˈalk", "/walk/", "왈크"), "now": ("wˈɔːk", "/wɔːk/", "워억"),
     "note": "l이 사라지고 모음이 변했다 (talk, chalk, folk, palm)."},
]

# ---------------------------------------------------------------- spelling detective
# cause keys -> label/icon are defined in deck.js (CAUSES)
DETECTIVE = [
    {"w": "knight", "ipa": "/naɪt/", "ko": "기사", "parts": [
        {"t": "k", "c": "lost", "y": "~1600년대 말", "why": "고대 영어 cniht는 [크니히트]. k를 실제로 발음했다. 1600년대에 kn-의 k가 빠졌다 (know, knee, knife도 같다).",
         "hook": "독일어 Knecht(하인)는 지금도 k를 발음한다. 같은 뿌리."},
        {"t": "n"},
        {"t": "i", "c": "gvs", "y": "1400~1700", "why": "중세에는 [i] 소리. gh 소리가 빠지며 길어졌고, 대모음추이로 [aɪ]가 되었다.",
         "hook": "night, light, right, fight: -igh- = /aɪ/ 패턴은 꽤 믿을 만하다."},
        {"t": "gh", "c": "scribe", "y": "1200~1600", "why": "고대 영어에서는 h로 썼다 (niht). 노르만 서기들이 이 '히/흐' 소리를 gh로 적었고, 1400~1600년대 남부에서 소리가 사라졌다.",
         "hook": "독일어 Nacht, Licht의 ch 소리가 바로 그 소리."},
        {"t": "t"}]},
    {"w": "debt", "ipa": "/dɛt/", "ko": "빚", "parts": [
        {"t": "de"},
        {"t": "b", "c": "latin", "y": "1500년대", "why": "중세에는 프랑스어에서 온 dette였다. 르네상스 학자들이 라틴어 debitum을 보여 주려고 b를 넣었다. 영어에서 이 b를 발음한 적은 없다.",
         "hook": "b는 debit(차변), debtor와 이어 주는 '뜻의 고리'. doubt(← dubitare)도 같다."},
        {"t": "t"}]},
    {"w": "island", "ipa": "/ˈaɪlənd/", "ko": "섬", "parts": [
        {"t": "i"},
        {"t": "s", "c": "latin", "y": "1500년대", "why": "고대 영어는 īgland. s가 없었다. 학자들이 프랑스어 isle(← 라틴어 insula)과 같은 말이라고 착각해 s를 넣었다. 사실은 어원이 다르다.",
         "hook": "'잘못 복원된 어원'의 대표 예. isle과 헷갈려서 생긴 s."},
        {"t": "land"}]},
    {"w": "ghost", "ipa": "/ɡoʊst/", "ko": "유령", "parts": [
        {"t": "g"},
        {"t": "h", "c": "printer", "y": "1400년대 말~1500년대", "why": "고대 영어 gāst. 캑스턴 인쇄소의 플랑드르(지금의 벨기에·네덜란드) 출신 식자공이 자기 말 gheest처럼 gh로 찍었고, 그 철자가 굳었다 (RobWords 13:55).",
         "hook": "ghastly(무시무시한), aghast(겁에 질린)도 같은 gh."},
        {"t": "ost"}]},
    {"w": "could", "ipa": "/kʊd/", "ko": "~할 수 있었다", "parts": [
        {"t": "cou"},
        {"t": "l", "c": "analogy", "y": "1500년대", "why": "중세에는 coude. would(OE wolde)와 should(OE sceolde)에는 원래 l이 있었다. 모양을 맞추려고 could에도 l을 넣었다 (RobWords 14:15).",
         "hook": "could / would / should = -ould = /ʊd/. 세 쌍둥이로 외우기."},
        {"t": "d"}]},
    {"w": "son", "ipa": "/sʌn/", "ko": "아들", "parts": [
        {"t": "s"},
        {"t": "o", "c": "scribe", "y": "1200~1400", "why": "고대 영어 sunu. 중세 필기체에서 u, n, m, v, w는 모두 짧은 세로획(minim)이어서 'sunu'는 세로줄만 늘어선 모양이었다. 서기들이 읽기 쉽게 u 대신 o를 썼다.",
         "hook": "m·n·v 옆의 o는 /ʌ/: love, come, some, month, wonder, honey, oven. 패턴으로 외우기."},
        {"t": "n"}]},
    {"w": "queen", "ipa": "/kwiːn/", "ko": "여왕", "parts": [
        {"t": "qu", "c": "scribe", "y": "1100~1300", "why": "고대 영어 cwēn. 노르만 서기들이 프랑스식 qu로 바꿨다 (cwic → quick).",
         "hook": "프랑스식 표기 세트: cw→qu, hw→wh(what), sc→sh(ship), ū→ou(house)."},
        {"t": "ee", "c": "gvs", "y": "1400~1700", "why": "ee는 원래 '긴 에' [eː]. 대모음추이로 [iː]가 되었다.",
         "hook": "ee = /iː/는 매우 믿을 만한 패턴 (see, tree, green)."},
        {"t": "n"}]},
    {"w": "colonel", "ipa": "/ˈkɜːrnl/", "ko": "대령", "parts": [
        {"t": "co"},
        {"t": "l", "c": "latin", "y": "1600년대", "why": "1500년대 프랑스어 coronel로 들어와 r로 발음했다. 그 뒤 학자들이 이탈리아어 colonnello를 따라 철자만 l로 바꿨다. 발음은 r 그대로 남았다.",
         "hook": "'철자 따로, 발음 따로'의 끝판왕. kernel과 같은 소리."},
        {"t": "onel"}]},
    {"w": "one", "ipa": "/wʌn/", "ko": "하나", "parts": [
        {"t": "o", "c": "dialect", "y": "1400~1600", "why": "고대 영어 ān [아안]. 서남부 방언에서 앞에 w 소리가 붙은 발음 [wʌn]이 표준이 되었다. 철자는 옛 모양 그대로다.",
         "hook": "only, alone, atone, 관사 a/an에는 w가 없는 옛 소리가 남아 있다."},
        {"t": "ne"}]},
    {"w": "Wednesday", "ipa": "/ˈwɛnzdeɪ/", "ko": "수요일", "parts": [
        {"t": "We"},
        {"t": "d", "c": "lost", "y": "중세 이후", "why": "고대 영어 Wōdnesdæg, '보덴(Woden)의 날'. 빨리 말하면서 d와 가운데 모음이 빠졌다.",
         "hook": "Woden = 북유럽 신 오딘. Thursday = Thor의 날 (RobWords 7:49, Lugh 23:44)."},
        {"t": "nesday"}]},
    {"w": "psychology", "ipa": "/saɪˈkɑːlədʒi/", "ko": "심리학", "parts": [
        {"t": "p", "c": "loan", "y": "1600년대", "why": "그리스어 ψυχή(psukhē)의 철자를 라틴 문자로 옮겼다. 영어는 단어 첫머리 [ps]를 발음하지 않아 p가 묵음이다.",
         "hook": "ps-, ph, ch(=k), y, rh가 보이면 그리스어 출신 = 학술 단어."},
        {"t": "s"},
        {"t": "y", "c": "loan", "y": "1600년대", "why": "그리스 글자 υ(upsilon)를 라틴어에서 y로 옮겼다. 그래서 그리스어 출신 단어의 모음 자리에 y가 온다 (system, rhythm, gym).",
         "hook": "모음 자리의 y = 그리스어 신호."},
        {"t": "c"},
        {"t": "h", "c": "loan", "y": "1600년대", "why": "그리스 글자 χ(chi)를 ch로 옮겼다. 그래서 [tʃ]가 아니라 [k]로 읽는다.",
         "hook": "ch = k: chorus, character, school, technology, stomach."},
        {"t": "ology"}]},
    {"w": "laugh", "ipa": "/læf/", "ko": "웃다", "parts": [
        {"t": "lau"},
        {"t": "gh", "c": "lost", "y": "1400~1600", "why": "고대 영어 hlæhhan의 [x] '흐' 소리. 어떤 말에서는 소리가 사라졌고(night, though), 어떤 말에서는 [f]로 바뀌었다 (laugh, cough, enough, tough).",
         "hook": "gh는 '사라지거나 f'. ough가 7가지로 읽히는 이유."}]},
]

# ---------------------------------------------------------------- word-layer game
# b: G = 게르만(고대 영어·노르드어), F = 프랑스어, L = 라틴·그리스어
LAYERS = [
    # triplets
    {"w": "ask", "b": "G", "src": "고대 영어 ascian", "fam": "ask · question · interrogate", "ko": "묻다 · 질문하다 · 심문하다"},
    {"w": "question", "b": "F", "src": "프랑스어 question (1200년대)", "fam": "ask · question · interrogate", "ko": "묻다 · 질문하다 · 심문하다"},
    {"w": "interrogate", "b": "L", "src": "라틴어 interrogare (1400년대 말)", "fam": "ask · question · interrogate", "ko": "묻다 · 질문하다 · 심문하다"},
    {"w": "rise", "b": "G", "src": "고대 영어 rīsan", "fam": "rise · mount · ascend", "ko": "오르다 · 등정하다 · 상승하다"},
    {"w": "mount", "b": "F", "src": "프랑스어 monter", "fam": "rise · mount · ascend", "ko": "오르다 · 등정하다 · 상승하다"},
    {"w": "ascend", "b": "L", "src": "라틴어 ascendere (1300년대 말)", "fam": "rise · mount · ascend", "ko": "오르다 · 등정하다 · 상승하다"},
    {"w": "begin", "b": "G", "src": "고대 영어 beginnan", "fam": "begin · commence · initiate", "ko": "시작하다 · 개시하다 · 착수하다"},
    {"w": "commence", "b": "F", "src": "프랑스어 comencier", "fam": "begin · commence · initiate", "ko": "시작하다 · 개시하다 · 착수하다"},
    {"w": "initiate", "b": "L", "src": "라틴어 initiare (1500년대)", "fam": "begin · commence · initiate", "ko": "시작하다 · 개시하다 · 착수하다"},
    {"w": "fear", "b": "G", "src": "고대 영어 fǣr", "fam": "fear · terror · trepidation", "ko": "두려움 · 공포 · 전율"},
    {"w": "terror", "b": "F", "src": "프랑스어 terreur (1300년대 말)", "fam": "fear · terror · trepidation", "ko": "두려움 · 공포 · 전율"},
    {"w": "trepidation", "b": "L", "src": "라틴어 trepidatio (1600년경)", "fam": "fear · terror · trepidation", "ko": "두려움 · 공포 · 전율"},
    # pairs
    {"w": "cow", "b": "G", "src": "고대 영어 cū", "fam": "cow (동물) · beef (고기)", "ko": "소 · 쇠고기"},
    {"w": "beef", "b": "F", "src": "프랑스어 buef (1300년경)", "fam": "cow (동물) · beef (고기)", "ko": "소 · 쇠고기"},
    {"w": "sheep", "b": "G", "src": "고대 영어 scēap", "fam": "sheep (동물) · mutton (고기)", "ko": "양 · 양고기"},
    {"w": "mutton", "b": "F", "src": "프랑스어 moton", "fam": "sheep (동물) · mutton (고기)", "ko": "양 · 양고기"},
    {"w": "freedom", "b": "G", "src": "고대 영어 frēodōm", "fam": "freedom · liberty", "ko": "자유 (일상) · 자유 (법·정치)"},
    {"w": "liberty", "b": "F", "src": "프랑스어 liberté (1300년대 말)", "fam": "freedom · liberty", "ko": "자유 (일상) · 자유 (법·정치)"},
    {"w": "buy", "b": "G", "src": "고대 영어 bycgan", "fam": "buy · purchase", "ko": "사다 · 구매하다"},
    {"w": "purchase", "b": "F", "src": "앵글로·노르만 프랑스어 purchacer", "fam": "buy · purchase", "ko": "사다 · 구매하다"},
    {"w": "tooth", "b": "G", "src": "고대 영어 tōþ", "fam": "tooth · dental", "ko": "이 · 치과(齒科)"},
    {"w": "dental", "b": "L", "src": "라틴어 dens, dentis (1590년대)", "fam": "tooth · dental", "ko": "이 · 치과(齒科)"},
    {"w": "moon", "b": "G", "src": "고대 영어 mōna", "fam": "moon · lunar", "ko": "달 · 음력(陰曆)/월(月)"},
    {"w": "lunar", "b": "L", "src": "라틴어 luna (1600년경)", "fam": "moon · lunar", "ko": "달 · 음력(陰曆)/월(月)"},
    {"w": "sun", "b": "G", "src": "고대 영어 sunne", "fam": "sun · solar", "ko": "해 · 태양(太陽)"},
    {"w": "solar", "b": "L", "src": "라틴어 sol (1400년대)", "fam": "sun · solar", "ko": "해 · 태양(太陽)"},
    # singles
    {"w": "sky", "b": "G", "src": "고대 노르드어 ský (바이킹)", "fam": "바이킹이 준 기본 단어", "ko": "하늘"},
    {"w": "egg", "b": "G", "src": "고대 노르드어 egg (바이킹)", "fam": "바이킹이 준 기본 단어", "ko": "달걀"},
    {"w": "they", "b": "G", "src": "고대 노르드어 þeir (바이킹)", "fam": "they · them · their", "ko": "그들"},
    {"w": "take", "b": "G", "src": "고대 노르드어 taka (바이킹)", "fam": "Take them as they are.", "ko": "잡다, 가져가다"},
    {"w": "very", "b": "F", "src": "프랑스어 verai '참된' (Gill 15:58)", "fam": "very = truly", "ko": "매우 (원래 '참으로')"},
    {"w": "people", "b": "F", "src": "앵글로·프랑스어 peple", "fam": "프랑스어인 줄 모르는 기본 단어", "ko": "사람들"},
    {"w": "photograph", "b": "L", "src": "그리스어 phōs(빛) + graphē(그림) (1839)", "fam": "photo · phone · graph", "ko": "사진(寫眞)"},
    {"w": "psychology", "b": "L", "src": "그리스어 psukhē(영혼) + logia (1600년대)", "fam": "-ology = ~학(學)", "ko": "심리학(心理學)"},
    {"w": "democracy", "b": "L", "src": "그리스어 dēmokratia (프랑스어 경유, 1570년대)", "fam": "demo(민) + cracy(다스림)", "ko": "민주주의(民主主義)"},
]

# ---------------------------------------------------------------- spelling-to-sound drill
# sound mode: hl = letters to highlight; opts = choices; ans = index into opts
SOUND_SETS = [
    {"id": "ch", "title": "ch", "opts": ["/tʃ/ ㅊ", "/ʃ/ 쉬", "/k/ ㅋ"],
     "rule": "ch는 출신에 따라 3가지: 영어 ㅊ(church), 프랑스어 쉬(chef), 그리스어 ㅋ(chorus).",
     "items": [("church", "ch", 0, "고대 영어 cirice → 노르만 서기가 ch로"), ("chef", "ch", 1, "프랑스어 (1800년대 차용)"),
               ("chorus", "ch", 2, "그리스어 χορός"), ("machine", "ch", 1, "프랑스어 machine"),
               ("character", "ch", 2, "그리스어 χαρακτήρ"), ("cheese", "ch", 0, "고대 영어 cēse")]},
    {"id": "g", "title": "g + e/i", "opts": ["/ɡ/ ㄱ", "/dʒ/ ㅈ"],
     "rule": "e·i·y 앞의 g: 프랑스·라틴·그리스어 출신은 /dʒ/, 게르만·노르드어 출신은 /ɡ/.",
     "items": [("gentle", "g", 1, "프랑스어 gentil"), ("get", "g", 0, "노르드어 geta (바이킹)"),
               ("giant", "g", 1, "프랑스어 geant"), ("give", "g", 0, "노르드어 영향 (gefa)"),
               ("gym", "g", 1, "그리스어 gymnasion"), ("girl", "g", 0, "중세 영어 gurle")]},
    {"id": "o", "title": "o 옆에 m·n·v", "opts": ["/ʌ/ 어", "/oʊ/ 오우"],
     "rule": "m·n·v 옆에서 u 대신 쓴 o는 /ʌ/ (서기들의 minim 습관). magic e가 있어도 love·come·done은 /ʌ/.",
     "items": [("love", "o", 0, "OE lufu: u → o"), ("stone", "o", 1, "magic e + 대모음추이"),
               ("son", "o", 0, "OE sunu: u → o"), ("honey", "o", 0, "OE hunig: u → o"),
               ("home", "o", 1, "magic e + 대모음추이"), ("come", "o", 0, "OE cuman: u → o")]},
    {"id": "ea", "title": "ea", "opts": ["/iː/ 이이", "/ɛ/ 에", "/eɪ/ 에이"],
     "rule": "ea는 대부분 /iː/, 일부는 짧아져 /ɛ/ (head, bread), 소수는 /eɪ/에서 멈춤 (great, break, steak).",
     "items": [("sea", "ea", 0, "ɛː → iː"), ("head", "ea", 1, "1500~1600년대 짧아짐"),
               ("great", "ea", 2, "/eɪ/에서 멈춘 예외"), ("meat", "ea", 0, "ɛː → iː"),
               ("bread", "ea", 1, "짧아짐"), ("break", "ea", 2, "/eɪ/에서 멈춘 예외")]},
    {"id": "e", "title": "magic e", "opts": ["긴 소리 (이름)", "짧은 소리", "예외"],
     "rule": "끝 -e = 원래 발음하던 모음. 앞 모음이 '이름 소리'가 된다. 단, 영어 철자는 v로 끝나지 않으려고 e를 붙여서 have·give·love는 예외.",
     "items": [("hope", "o_e", 0, "/oʊ/"), ("hop", "o", 1, "/ɑː/"), ("cute", "u_e", 0, "/juː/"),
               ("cut", "u", 1, "/ʌ/"), ("have", "a_e", 2, "/æ/: v 뒤 e는 '철자 장식'"), ("give", "i_e", 2, "/ɪ/: v 뒤 e")]},
    {"id": "tion", "title": "-tion · -sion", "opts": ["/ʃən/ 션", "/ʒən/ 젼", "/tʃən/ 쳔"],
     "rule": "-tion은 거의 항상 /ʃən/. 앞이 s면 /tʃən/ (question), -sion은 모음 뒤 /ʒən/ (vision).",
     "items": [("nation", "tion", 0, "프랑스어·라틴어 -tion"), ("vision", "sion", 1, "모음 뒤 -sion"),
               ("question", "tion", 2, "s 뒤 -tion"), ("education", "tion", 0, "-tion"),
               ("decision", "sion", 1, "모음 뒤 -sion"), ("suggestion", "tion", 2, "s 뒤 -tion")]},
]
# stress mode: syl = syllables (display), ans = stressed index, ipa = display IPA
STRESS_SETS = [
    {"id": "photo", "title": "photograph 가족", "rule": "-er·-y가 붙으면 뒤에서 셋째, -ic이 붙으면 -ic 바로 앞에 강세. 강세 없는 모음은 /ə/로 약해진다.",
     "items": [("photograph", ["pho", "to", "graph"], 0, "/ˈfoʊtəɡræf/"),
               ("photographer", ["pho", "to", "gra", "pher"], 1, "/fəˈtɑːɡrəfər/"),
               ("photographic", ["pho", "to", "graph", "ic"], 2, "/ˌfoʊtəˈɡræfɪk/")]},
    {"id": "demo", "title": "democracy 가족", "rule": "같은 철자라도 강세가 옮겨 가면 모음 소리가 바뀐다 (de- /dɛ/ ↔ /dɪ/).",
     "items": [("democrat", ["dem", "o", "crat"], 0, "/ˈdɛməkræt/"),
               ("democracy", ["de", "moc", "ra", "cy"], 1, "/dɪˈmɑːkrəsi/"),
               ("democratic", ["dem", "o", "crat", "ic"], 2, "/ˌdɛməˈkrætɪk/"),
               ("economy", ["e", "con", "o", "my"], 1, "/ɪˈkɑːnəmi/"),
               ("economic", ["ec", "o", "nom", "ic"], 2, "/ˌɛkəˈnɑːmɪk/")]},
    {"id": "tion", "title": "-tion 규칙", "rule": "-tion·-sion·-ic은 바로 앞 음절에 강세. 단어가 길어져도 이 규칙은 거의 깨지지 않는다.",
     "items": [("nation", ["na", "tion"], 0, "/ˈneɪʃən/"),
               ("education", ["ed", "u", "ca", "tion"], 2, "/ˌɛdʒuˈkeɪʃən/"),
               ("information", ["in", "for", "ma", "tion"], 2, "/ˌɪnfərˈmeɪʃən/")]},
    {"id": "nv", "title": "명사 · 동사 쌍", "rule": "2음절 프랑스·라틴어 출신 쌍: 명사는 앞, 동사는 뒤에 강세 (REcord / reCORD).",
     "items": [("record (명사)", ["rec", "ord"], 0, "/ˈrɛkərd/"),
               ("record (동사)", ["re", "cord"], 1, "/rɪˈkɔːrd/"),
               ("present (명사)", ["pres", "ent"], 0, "/ˈprɛzənt/"),
               ("present (동사)", ["pre", "sent"], 1, "/prɪˈzɛnt/")]},
    {"id": "germ", "title": "게르만 vs 프랑스", "rule": "게르만 단어는 어근 첫 음절에 강세 (be-·for-·under- 같은 접두사는 X). 늦게 들어온 프랑스어 단어는 끝에 강세가 남기도 한다 (hotel, police, career).",
     "items": [("water", ["wa", "ter"], 0, "/ˈwɔːtər/"),
               ("begin", ["be", "gin"], 1, "/bɪˈɡɪn/"),
               ("forget", ["for", "get"], 1, "/fərˈɡɛt/"),
               ("hotel", ["ho", "tel"], 1, "/hoʊˈtɛl/"),
               ("police", ["po", "lice"], 1, "/pəˈliːs/"),
               ("career", ["ca", "reer"], 1, "/kəˈrɪr/")]},
]

# heteronyms and other words where Kokoro's own phonemizer is not what we want
PH_OVERRIDE = {
    "record (명사)": "ɹˈɛkɚd", "record (동사)": "ɹɪkˈɔɹd",
    "present (명사)": "pɹˈɛzənt", "present (동사)": "pɹɪzˈɛnt",
    "one": "wˈʌn", "girl": "ɡˈɜɹl", "thorough": "θˈɜɹoʊ",
}

# ---------------------------------------------------------------- audio used directly by slides
# key -> item. Slides refer to these with data-say="key".
SLIDE_AUDIO = {
    # warm-up: ough
    **{f"ough-{w}": {"text": w} for w in ["though", "through", "tough", "cough", "bough", "thought", "thorough"]},
    # Old English (Lord's Prayer, c. 1000) and Middle English (Chaucer, c. 1390), reconstructed
    "oe-prayer": {"ph": "fˈæder ˈuːre, θˈuː θe ˈæɑrt on hˈeovonum, sˈiː θˈiːn nˈama jehˈɑːlɣod.", "voice": V_OLD, "speed": 0.85},
    "now-prayer": {"text": "Our Father, who art in heaven, hallowed be thy name."},
    "me-chaucer": {"ph": "hwˈan θat aprˈil wiθ hiz ʃˈuːrəs sˈoːtə, θə drˈuxt ɔf mˈartʃ haθ pˈɛːrsəd tˈoː θə rˈoːtə.", "voice": V_OLD, "speed": 0.85},
    "now-chaucer": {"text": "When April with its sweet showers has pierced the drought of March to the root."},
    # Old English word order demo
    "oe-hunta1": {"ph": "se hˈunta ofslˈoːx θone bˈeran.", "voice": V_OLD, "speed": 0.85},
    "oe-hunta2": {"ph": "θone bˈeran ofslˈoːx se hˈunta.", "voice": V_OLD, "speed": 0.85},
    "oe-hunta3": {"ph": "se bˈera ofslˈoːx θone hˈuntan.", "voice": V_OLD, "speed": 0.85},
    "now-hunter": {"text": "The hunter killed the bear."},
    # pronunciation slide
    **{f"pr-{w}": {"text": w} for w in ["strike", "strengths", "Christmas"]},
    **{f"schwa-{w}": {"text": w} for w in ["about", "taken", "pencil", "lemon", "circus"]},
    # Norse doublets
    "skirt": {"text": "skirt"}, "shirt": {"text": "shirt"},
}
