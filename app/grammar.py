"""Grammar for real use: short lessons organized by what you do with English, practice in
five question types, spaced review, and the same patterns found in the student's own books.

- Each point (app/data/grammar.json) says when you use it, how it is formed, the mistakes
  learners really make and a real-life mission, and has a bank of questions:
      situation  which sentence fits a real situation (meaning, not just form)
      gap        choose the words that complete a sentence
      fix        tap the mistake in a sentence
      order      build a sentence from word tiles
  Listen-and-write (dictation) items are made from the point's examples and read by Kokoro.
- A practice or review session gives each point a score, and the point moves through the
  same Leitner boxes as words (srs.py): back after 1, 3, 7, 14 and 30 days. Extra practice of
  a point that is not due doesn't skip the spacing; a poor score brings it back tomorrow.
- Pattern detectors find each point in real sentences, so a lesson shows examples from
  library texts at the student's level and the reader can highlight a grammar point.
- Students write their own sentences for the mission; with a Claude API key they get short,
  kind feedback.
"""
from __future__ import annotations

import json
import random
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Callable

import lemminflect
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import ai, db, library, srs, vocab
from .deps import Conn, student_row
from .textproc import sentence_spans, split_paragraphs

DATA = Path(__file__).resolve().parent / "data" / "grammar.json"
QUESTION_TYPES = ("situation", "gap", "fix", "order")
GOOD = 0.8                # session score that moves a point up a box
POOR = 0.5                # below this the point starts again from box 1
PRACTICE_DICTATIONS = 2
REVIEW_POINTS = 5
SNIPPET_WORDS = (5, 32)   # length of a book sentence worth showing
SCAN_UNITS = 400          # library units searched for a point's examples
WRITING_SHOWN = 5

router = APIRouter(prefix="/api/grammar")


def today() -> date:
    return date.today()


# ====================================================================== content

@lru_cache(maxsize=1)
def content() -> tuple[list[dict], list[dict], dict[str, dict]]:
    """(units, points in learning order, points by id)."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    points = sorted(data["points"], key=lambda p: p["order"])
    return data["units"], points, {p["id"]: p for p in points}


def get_point(pid: str) -> dict:
    p = content()[2].get(pid)
    if p is None:
        raise HTTPException(404, "Unknown grammar point")
    return p


MARK_RE = re.compile(r"\*([^*]+)\*")


def plain(s: str) -> str:
    return s.replace("*", "")


def norm_answer(s: str) -> str:
    """Lowercase words without punctuation. grammar.js uses the same rule."""
    s = re.sub(r"[^a-z0-9'\s-]", "", s.lower().replace("’", "'"))
    return re.sub(r"\s+", " ", s).strip()


# ====================================================================== questions

def fix_parts(sentence: str, right: str) -> dict:
    """Tappable words of a sentence with one *wrong* part, and the corrected sentence."""
    m = MARK_RE.search(sentence)
    text = plain(sentence)
    a, b = m.start(), m.end() - 2           # the same span without the two asterisks
    tokens, wrong = [], []
    for i, t in enumerate(re.finditer(r"\S+", text)):
        tokens.append(t.group())
        if t.start() < b and t.end() > a:
            wrong.append(i)
    fixed = text[:a] + (f"*{right}*" if right else "") + text[b:]
    fixed = re.sub(r"\s+([,.!?])", r"\1", re.sub(r"\s{2,}", " ", fixed)).strip()
    return {"tokens": tokens, "wrong": wrong, "corrected": fixed}


def order_parts(answer: str, accept: list[str], rng: random.Random) -> dict:
    """Shuffled word tiles without punctuation; the first word loses its capital (except I)."""
    words = [w for w in (re.sub(r"[^\w'’-]", "", w) for w in answer.split()) if w]
    if words[0] != "I" and not words[0].startswith(("I'", "I’")):
        words[0] = words[0][0].lower() + words[0][1:]
    tiles = words[:]
    for _ in range(20):
        rng.shuffle(tiles)
        if tiles != words:
            break
    return {"tiles": tiles, "answers": [norm_answer(s) for s in [answer, *accept]], "answer_text": answer}


def item(p: dict, i: int, rng: random.Random) -> dict:
    """Question i of a point, ready for the browser (options shuffled)."""
    q = p["questions"][i]
    base = {"point": p["id"], "qid": f"q{i}", "type": q["type"], "why": q.get("why", "")}
    if q["type"] == "situation":
        options = list(q["options"])
        correct = options[q["answer"]]
        rng.shuffle(options)
        return {**base, "context": q["context"], "options": options, "answer": options.index(correct)}
    if q["type"] == "gap":
        correct = MARK_RE.search(q["sentence"]).group(1)
        options = list(q["options"])
        rng.shuffle(options)
        return {**base, "prompt": MARK_RE.sub("_____", q["sentence"], count=1), "options": options,
                "answer": options.index(correct), "full": q["sentence"]}
    if q["type"] == "fix":
        return {**base, **fix_parts(q["sentence"], q["right"])}
    if q["type"] == "order":
        return {**base, **order_parts(q["answer"], q.get("accept", []), rng)}
    raise ValueError(q["type"])


def dictation(p: dict, i: int) -> dict:
    ex = p["examples"][i]
    return {"point": p["id"], "qid": f"d{i}", "type": "dictation", "sentence": plain(ex), "marked": ex}


def practice_items(p: dict, rng: random.Random) -> list[dict]:
    qs = [item(p, i, rng) for i in range(len(p["questions"]))]
    rng.shuffle(qs)
    picks = rng.sample(range(len(p["examples"])), min(PRACTICE_DICTATIONS, len(p["examples"])))
    dict_items = [dictation(p, i) for i in picks]
    return qs[:3] + dict_items[:1] + qs[3:] + dict_items[1:]


def review_items(conn: sqlite3.Connection, sid: int, t: date, rng: random.Random) -> list[dict]:
    """Due points, a few questions each (missed ones first), interleaved round by round."""
    rows = conn.execute(
        "SELECT * FROM grammar_progress WHERE student_id = ? AND box >= 1 AND due <= ? ORDER BY due, box LIMIT ?",
        (sid, t.isoformat(), REVIEW_POINTS)).fetchall()
    points = content()[2]
    rows = [r for r in rows if r["point"] in points]
    per = 3 if len(rows) <= 3 else 2
    queues = []
    for n, r in enumerate(rows):
        p = points[r["point"]]
        missed = json.loads(r["missed"] or "[]")
        ids = list(range(len(p["questions"])))
        rng.shuffle(ids)
        first = [int(m[1:]) for m in missed if m.startswith("q") and m[1:].isdigit() and int(m[1:]) < len(ids)]
        ids = list(dict.fromkeys(first + ids))[:per]
        queue = [item(p, i, rng) for i in ids]
        if len(rows) <= 3 or n % 2 == 0:
            missed_d = [int(m[1:]) for m in missed if m.startswith("d") and m[1:].isdigit()]
            ex = next((i for i in missed_d if i < len(p["examples"])), rng.randrange(len(p["examples"])))
            queue.append(dictation(p, ex))
        queues.append(queue)
    rng.shuffle(queues)
    out = []
    for k in range(max((len(q) for q in queues), default=0)):
        out += [q[k] for q in queues if k < len(q)]
    return out


# ====================================================================== progress

def schedule(box: int, due: str | None, score: float, t: date) -> tuple[int, date]:
    """Next box and review day after a session on one point."""
    is_due = box <= 0 or not due or due <= t.isoformat()
    if score < POOR:
        return srs.after_answer(box, False, t)
    if score >= GOOD:
        return srs.after_answer(box, True, t) if is_due else (box, date.fromisoformat(due))
    return max(box, 1), t + timedelta(days=1)


def progress_rows(conn: sqlite3.Connection, sid: int) -> dict[str, sqlite3.Row]:
    return {r["point"]: r for r in conn.execute("SELECT * FROM grammar_progress WHERE student_id = ?", (sid,))}


def status_of(row: sqlite3.Row | None) -> dict:
    if row is None:
        return {"status": "new", "box": 0, "due": None, "score": None, "sessions": 0}
    return {"status": srs.status(row["box"]), "box": row["box"], "due": row["due"],
            "score": row["last_score"], "sessions": row["sessions"]}


def card(p: dict, row: sqlite3.Row | None) -> dict:
    return {**{k: p[k] for k in ("id", "unit", "order", "title", "grammar", "band")}, **status_of(row)}


def brief(p: dict) -> dict:
    return {k: p[k] for k in ("id", "title", "grammar", "band")}


def summary(conn: sqlite3.Connection, sid: int, t: date, cards: list[dict] | None = None) -> dict:
    if cards is None:
        rows = progress_rows(conn, sid)
        cards = [card(p, rows.get(p["id"])) for p in content()[1]]
    nxt = next((c for c in cards if c["status"] == "new"), None)
    return {
        "total": len(cards),
        "started": sum(c["status"] != "new" for c in cards),
        "mastered": sum(c["status"] == "mastered" for c in cards),
        "due": sum(1 for c in cards if c["box"] >= 1 and c["due"] and c["due"] <= t.isoformat()),
        "next": brief(nxt) if nxt else None,
    }


# ====================================================================== finding grammar in texts

IRREGULAR = """arise arose arisen, awake awoke awoken, bear bore born, beat beat beaten, become became become,
begin began begun, bend bent bent, bet bet bet, bite bit bitten, bleed bled bled, blow blew blown,
break broke broken, bring brought brought, build built built, burn burnt burnt, burst burst burst,
buy bought bought, catch caught caught, choose chose chosen, come came come, cost cost cost,
creep crept crept, cut cut cut, deal dealt dealt, dig dug dug, do did done, draw drew drawn,
dream dreamt dreamt, drink drank drunk, drive drove driven, eat ate eaten, fall fell fallen,
feed fed fed, feel felt felt, fight fought fought, find found found, flee fled fled, fly flew flown,
forbid forbade forbidden, forget forgot forgotten, forgive forgave forgiven, freeze froze frozen,
get got gotten, give gave given, go went gone, grow grew grown, hang hung hung, have had had,
hear heard heard, hide hid hidden, hit hit hit, hold held held, hurt hurt hurt, keep kept kept,
kneel knelt knelt, know knew known, lay laid laid, lead led led, leap leapt leapt, learn learnt learnt,
leave left left, lend lent lent, let let let, lie lay lain, light lit lit, lose lost lost, make made made,
mean meant meant, meet met met, pay paid paid, put put put, quit quit quit, read read read,
ride rode ridden, ring rang rung, rise rose risen, run ran run, say said said, see saw seen,
seek sought sought, sell sold sold, send sent sent, set set set, shake shook shaken, shine shone shone,
shoot shot shot, show showed shown, shrink shrank shrunk, shut shut shut, sing sang sung, sink sank sunk,
sit sat sat, sleep slept slept, slide slid slid, smell smelt smelt, speak spoke spoken, spend spent spent,
spill spilt spilt, spin spun spun, spit spat spat, split split split, spread spread spread,
spring sprang sprung, stand stood stood, steal stole stolen, stick stuck stuck, sting stung stung,
strike struck struck, swear swore sworn, sweep swept swept, swim swam swum, swing swung swung,
take took taken, teach taught taught, tear tore torn, tell told told, think thought thought,
throw threw thrown, understand understood understood, wake woke woken, wear wore worn, weep wept wept,
win won won, write wrote written"""


def _irregular() -> tuple[set[str], set[str], set[str]]:
    past, pp, bases = set(), set(), set()
    for entry in IRREGULAR.split(","):
        b, pa, part = entry.split()
        bases.add(b)
        past.add(pa)
        pp.add(part)
    return past, pp | {"got", "been"}, bases


PAST_IRR, PP_IRR, BASE_IRR = _irregular()
NOT_ING = {"evening", "morning", "nothing", "something", "anything", "everything", "during", "ceiling",
           "pudding", "wedding", "darling", "sibling", "duckling", "earring", "lightning"}
ADJ_ING = {"interesting", "boring", "amazing", "exciting", "surprising", "annoying", "confusing", "disappointing",
           "embarrassing", "frightening", "shocking", "tiring", "relaxing", "charming", "astonishing", "terrifying",
           "worrying", "satisfying", "convincing", "promising", "challenging", "missing", "willing", "loving",
           "pleasing", "fascinating", "alarming", "thrilling", "depressing", "encouraging", "refreshing"}
ADJ_PP = {"tired", "married", "excited", "interested", "surprised", "pleased", "scared", "frightened", "worried",
          "bored", "gone", "done", "finished", "dressed", "prepared", "satisfied", "ashamed", "amazed", "annoyed",
          "confused", "delighted", "disappointed", "embarrassed", "shocked", "terrified", "astonished", "alarmed",
          "determined", "concerned", "involved", "supposed", "used", "seated", "engaged", "inclined", "obliged",
          "amused", "puzzled", "troubled", "relieved", "convinced", "drunk", "closed", "lost", "upset", "fed",
          "tied", "stuck", "settled", "beloved", "aged", "learned", "naked", "wicked", "crowded", "scattered"}
REPORT_NOUNS = {"fact", "idea", "news", "feeling", "hope", "thought", "belief", "sense", "chance", "sure", "way",
                "reason", "rumour", "rumor", "story", "promise", "proof", "sign", "suggestion"}
TO_VERBS = {"want", "need", "decide", "hope", "plan", "promise", "learn", "agree", "refuse", "offer", "try", "seem",
            "manage", "forget", "remember", "expect", "choose", "prefer", "like", "love", "hate", "start", "begin",
            "wish", "afford", "arrange", "attempt", "fail", "intend", "pretend", "threaten", "tend", "deserve"}
ING_VERBS = {"enjoy", "finish", "mind", "avoid", "keep", "stop", "suggest", "imagine", "miss", "practise", "practice",
             "consider", "quit", "risk", "deny", "admit", "recommend", "like", "love", "hate", "start", "begin", "go"}


@lru_cache(maxsize=1 << 16)
def lemmas(word: str) -> dict:
    return lemminflect.getAllLemmas(word)


def _verb_forms(w: str) -> list[str]:
    return [lm for pos in ("VERB", "AUX") for lm in lemmas(w).get(pos, ())]


def verb_ed(w: str) -> bool:
    return w.endswith("ed") and any(lm != w for lm in lemmas(w).get("VERB", ()))


def is_past(w: str) -> bool:
    """A past-tense verb ("went", "walked"), but not one spelled like its base ("put")."""
    return w != "had" and ((w in PAST_IRR and w not in BASE_IRR) or verb_ed(w))


def is_pp(w: str) -> bool:
    return w in PP_IRR or verb_ed(w)


def is_pp_distinct(w: str) -> bool:
    """A past participle that can't be read as a base verb ("seen", not "come")."""
    return (w in PP_IRR and w not in BASE_IRR) or verb_ed(w)


def is_ing(w: str) -> bool:
    return (w.endswith("ing") and w not in NOT_ING and w not in ADJ_ING
            and any(lm != w for lm in lemmas(w).get("VERB", ())))


def is_base(w: str) -> bool:
    return w in _verb_forms(w)


def is_s_verb(w: str) -> bool:
    return w.endswith("s") and w not in ("is", "was", "this", "us", "yes") and any(lm != w for lm in _verb_forms(w))


def is_noun(w: str) -> bool:
    lm = lemmas(w)
    return ("NOUN" in lm and "ADJ" not in lm and "ADV" not in lm
            and w not in ("of", "more", "one", "other", "others", "lot", "kind", "sort"))


def is_adj(w: str) -> bool:
    return "ADJ" in lemmas(w) or "ADV" in lemmas(w)


def _graded(w: str, ending: str) -> bool:
    return w.endswith(ending) and any(lm != w for pos in ("ADJ", "ADV") for lm in lemmas(w).get(pos, ()))


def is_comparative(w: str) -> bool:
    return w in ("better", "worse", "fewer", "further", "farther") or _graded(w, "er")


def is_superlative(w: str) -> bool:
    return w in ("best", "worst") or _graded(w, "est")


def verb_lemma(w: str) -> str:
    forms = lemmas(w).get("VERB")
    return forms[0] if forms else w


@dataclass(frozen=True)
class Pattern:
    """A regex for one form of a grammar point. Named groups starting with "m" are the parts to
    highlight (default: the whole match); other named groups must pass their check."""
    rx: re.Pattern
    checks: tuple[tuple[str, Callable[[str], bool]], ...] = ()
    need: re.Pattern | None = None       # the sentence must match this
    avoid: re.Pattern | None = None      # … and must not match this
    paragraph: bool = False              # match across sentence ends


def P(rx: str, need: str | None = None, avoid: str | None = None, paragraph: bool = False,
      **checks: Callable[[str], bool]) -> Pattern:
    f = re.IGNORECASE
    return Pattern(re.compile(rx, f), tuple(checks.items()), need and re.compile(need, f),
                   avoid and re.compile(avoid, f), paragraph)


ADV = r"(?:(?:{})\s+)?"
QUESTION = r"\?\W*$"
HELPERS = r"(?:do|does|did|is|are|was|were|can|could|will|would|have|has|should|shall)"
SUBJ = r"(?:I|you|he|she|it|we|they)"
MONTHS = r"january|february|march|april|may|june|july|august|september|october|november|december"
DAYS = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"

DETECTORS: dict[str, list[Pattern]] = {
    "be": [
        P(r"\b(?:I\s+am|I'm|you\s+are|you're|we\s+are|we're|they\s+are|they're|(?:he|she|it|this|that)\s+is|"
          r"he's|she's|it's|that's|there\s+(?:is|are)|there's)\b(?!\s+(?:been|gone|got|going\s+to|\w+ing)\b)"),
        P(r"^\W*(?:am\s+I|are\s+(?:you|we|they)|is\s+(?:he|she|it|this|that|there))\b", need=QUESTION),
    ],
    "present-simple": [
        P(r"\b(?:he|she|it)\s+" + ADV.format("always|usually|often|sometimes|never|also|really|still|only|rarely|just")
          + r"(?P<v>[a-z]+s)\b", v=is_s_verb),
        P(r"\b" + SUBJ + r"\s+(?:don't|doesn't|do\s+not|does\s+not)\s+(?P<v>[a-z]+)\b", v=is_base),
        P(r"\b(?:I|you|we|they)\s+(?:always|usually|often|sometimes|never|rarely)\s+(?P<v>[a-z]+)\b", v=is_base),
        P(r"\b(?:do|does)\s+" + SUBJ + r"\s+(?P<v>[a-z]+)\b", v=is_base),
    ],
    "present-continuous": [
        P(r"(?:\b(?:am|is|are|isn't|aren't)|'m|'re|'s)\s+" + ADV.format("not|still|just|always|now|really|also|slowly")
          + r"(?P<v>(?!going\s+to\b)[a-z]+ing)\b", v=is_ing),
        P(r"\b(?:am|is|are)\s+" + SUBJ + r"\s+(?P<v>[a-z]+ing)\b", v=is_ing),
    ],
    "questions": [
        P(r"^\W*(?:what|where|when|why|who|which|whose|how)(?:\s+[a-z]+)?\s+" + HELPERS + r"\b", need=QUESTION),
        P(r"^\W*" + HELPERS + r"\s+(?:I|you|he|she|it|we|they|there|your|my|his|her|our|their|the|this|that)\b",
          need=QUESTION),
        P(r"^\W*who\s+(?P<v>[a-z]+)\b", need=QUESTION, v=is_past),
    ],
    "articles": [
        P(r"\b(?P<m1>an?\s+(?:[a-z]+\s+)?(?P<n>[a-z]{3,}))\b[^.!?]*[.!?]+[\"'”)\]]*\s+(?:[^.!?]*?\s)?"
          r"(?P<m2>the\s+(?P=n))\b", paragraph=True, n=is_noun),
        P(r"\ban\s+(?:[aeiou]|hour|honest|honour|heir)[a-z]*\b"),
    ],
    "quantity": [
        P(r"\b(?:how\s+(?:much|many)|too\s+(?:much|many)|so\s+many|a\s+few|a\s+lot\s+of|lots\s+of|plenty\s+of|many|"
          r"some|any|enough)\s+(?P<n>[a-z]+)\b", n=is_noun),
        P(r"(?<!very )(?<!so )(?<!thank you )\bmuch\s+(?P<n>[a-z]+)\b", n=is_noun),
    ],
    "prepositions": [
        P(r"\bat\s+(?:\d{1,2}(?:[:.]\d{2})?(?:\s*(?:o'clock|[ap]\.?m\.?))?|night|noon|midnight|dawn|home|school|work|"
          r"lunch|dinner|breakfast|the\s+(?:weekend|moment|end|start|beginning|station|airport|door|corner|top|"
          r"bottom|bus\s+stop|table|window|back|front|party|cinema|café|cafe|shop|hospital))(?!\w)"),
        P(r"\bon\s+(?:" + DAYS + r"|weekdays|weekends|(?:my|his|her|your|their|our)\s+birthday|"
          r"the\s+(?:table|floor|wall|bed|shelf|desk|roof|ground|left|right|beach|bus|train|plane|phone|radio|"
          r"screen|kitchen\s+table)|\d{1,2}(?:st|nd|rd|th)?\s+(?:" + MONTHS + r"))s?(?!\w)"),
        P(r"\bin\s+(?:" + MONTHS + r"|spring|summer|autumn|winter|(?:1[5-9]|20)\d\d|bed|town|the\s+(?:morning|"
          r"afternoon|evening|garden|kitchen|house|room|box|bag|car|city|country|world|park|sea|water|forest|sky|"
          r"middle|past|future|south|north|east|west))(?!\w)"),
    ],
    "past-simple": [
        P(r"\b" + SUBJ + r"\s+" + ADV.format("just|then|suddenly|finally|never|always|also|only|really|quickly|"
                                             "slowly|soon|once|first|later") + r"(?P<v>[a-z]+)\b", v=is_past),
        P(r"\b(?:didn't|did\s+not)\s+(?P<v>[a-z]+)\b", v=is_base),
        P(r"\bdid\s+" + SUBJ + r"\s+(?P<v>[a-z]+)\b", v=is_base),
    ],
    "past-continuous": [
        P(r"\b(?:was|were|wasn't|weren't)\s+" + ADV.format("not|still|just|always|already|slowly|quietly|really|also")
          + r"(?P<v>(?!going\s+to\b)[a-z]+ing)\b", v=is_ing),
        P(r"\b(?:was|were)\s+" + SUBJ + r"\s+(?P<v>[a-z]+ing)\b", v=is_ing),
    ],
    "present-perfect": [
        P(r"(?:\b(?:have|has|haven't|hasn't)|'ve)\s+" + ADV.format("not|never|ever|just|already|always|recently|"
                                                                   "often|finally|only|also|now")
          + r"(?P<v>[a-z]+)\b", v=is_pp),
        P(r"\b(?:he|she|it)'s\s+(?:just|already|never|ever|finally|recently)\s+(?P<v>[a-z]+)\b", v=is_pp),
        P(r"\b(?:have|has)\s+" + SUBJ + r"\s+" + ADV.format("ever|never|already|just|really") + r"(?P<v>[a-z]+)\b",
          v=is_pp),
    ],
    "for-since": [
        P(r"(?P<m1>(?:\b(?:have|has|haven't|hasn't)|'ve|'s)\s+" + ADV.format("not|never|only|always|now|just")
          + r"(?P<v>been\s+[a-z]+ing|[a-z]+))\b[^.!?;:]{0,60}?\b(?P<m2>since|for\s+(?:ages|ever|so\s+long|too\s+long|"
          r"a\s+(?:long\s+)?while|a\s+long\s+time|(?:(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|"
          r"twenty|thirty|several|many|some|a\s+few|\d+)\s+(?:[a-z]+\s+)?)?(?:second|minute|hour|day|week|month|"
          r"year|decade)s?))\b", v=lambda w: is_pp(w.split()[-1]) or is_ing(w.split()[-1])),
        P(r"\b(?P<m1>how\s+long\s+(?:have|has))\b"),
    ],
    "used-to": [
        P(r"(?<!\bwas )(?<!\bwere )(?<!\bis )(?<!\bare )(?<!\bam )(?<!\bget )(?<!\bgot )(?<!\bbe )"
          r"\bused\s+to\s+(?P<v>[a-z]+)\b", v=is_base),
        P(r"\bdid(?:n't|\s+not)?\s+(?:" + SUBJ + r"\s+)?use\s+to\s+(?P<v>[a-z]+)\b", v=is_base),
    ],
    "past-perfect": [
        P(r"\b(?:had|hadn't)\s+" + ADV.format("not|never|already|just|ever|always|only|also|recently|finally|once")
          + r"(?P<v>[a-z]+)\b", v=is_pp),
        P(r"\b(?:I|you|he|she|we|they|it)'d\s+" + ADV.format("never|already|just|ever|not") + r"(?P<v>[a-z]+)\b",
          v=is_pp_distinct),
        P(r"\bhad\s+" + SUBJ + r"\s+" + ADV.format("ever|never|already") + r"(?P<v>[a-z]+)\b", v=is_pp),
    ],
    "future": [
        P(r"(?:\b(?:will|won't|shall)|'ll)\s+" + ADV.format("not|never|always|probably|definitely|soon|just|also|"
                                                            "still|certainly|really|only|then")
          + r"(?P<v>[a-z]+)\b", v=is_base),
        P(r"(?:\b(?:am|is|are)|'m|'re|'s)\s+(?:not\s+)?going\s+to\s+(?P<v>[a-z]+)\b", v=is_base),
    ],
    "if-real": [
        P(r"\b(?P<m1>if)\b[^.!?;]{2,80}?(?P<m2>(?:\b(?:will|won't)|'ll)\s+[a-z]+)",
          avoid=r"\b(?:would|wouldn't|were)\b|'d\b|\b(?:know|ask|asked|wonder|wondered|see|sure)\s+if\b"),
    ],
    "if-imagine": [
        P(r"\b(?P<m1>if\s+(?:" + SUBJ + r"|[a-z]+)\s+" + ADV.format("only|really|just|still|ever")
          + r"(?P<v>[a-z']+))\b[^.!?;]{0,80}?(?P<m2>(?:\b(?:would|wouldn't)|'d)\s+[a-z]+)",
          v=lambda w: w in ("were", "had", "was", "could", "knew", "did", "didn't", "wasn't", "weren't",
                            "couldn't") or is_past(w)),
        P(r"(?P<m2>(?:\b(?:would|wouldn't)|'d)\s+[a-z]+)\b[^.!?;]{0,80}?\b(?P<m1>if\s+" + SUBJ
          + r"\s+(?P<v>[a-z']+))\b",
          v=lambda w: w in ("were", "had", "was", "could", "knew", "did", "didn't") or is_past(w)),
        P(r"\b(?P<m1>(?:I|we|you|they|he|she)\s+wish(?:ed)?)\s+(?:that\s+)?(?P<m2>" + SUBJ
          + r"\s+(?P<v>[a-z']+))\b", v=lambda w: w in ("were", "had", "could", "would", "was", "knew") or is_past(w)),
        P(r"\b(?P<m1>if\s+only)\b"),
    ],
    "can-could": [
        P(r"\b(?:can|can't|cannot|could|couldn't)\s+" + ADV.format("not|never|only|still|easily|also|really|just|"
                                                                   "hardly")
          + r"(?P<v>[a-z]+)\b", v=is_base),
        P(r"(?:\b(?:am|is|are|was|were|be|been)|'m|'re)\s+(?:not\s+)?able\s+to\s+[a-z]+\b"),
        P(r"\b(?:could|can|would)\s+you\s+(?:please\s+)?(?:mind\s+)?(?P<v>[a-z]+)\b",
          v=lambda w: is_base(w) or is_ing(w)),
        P(r"\b(?:can|could|may)\s+I\s+(?P<v>[a-z]+)\b", v=is_base),
    ],
    "advice-rules": [
        P(r"\b(?:should|shouldn't|ought\s+to|must|mustn't|(?:have|has|had|don't\s+have|doesn't\s+have|"
          r"didn't\s+have)\s+to|needs?\s+to|had\s+better)\s+(?:not\s+)?"
          + ADV.format("always|never|really|just|also|probably|definitely") + r"(?P<v>[a-z]+)\b",
          v=lambda w: is_base(w) and w != "have"),
        P(r"'d\s+better\s+(?:not\s+)?(?P<v>[a-z]+)\b", v=is_base),
    ],
    "guessing": [
        P(r"\b(?:must|might|may|could|can't|couldn't|mightn't)\s+(?:not\s+)?(?:be\b|have\s+(?P<v>[a-z]+)\b)", v=is_pp),
        P(r"\b(?:might|may)\s+(?:not\s+)?" + ADV.format("well|also|even|just") + r"(?P<v>[a-z]+)\b",
          v=lambda w: is_base(w) and w != "i"),
    ],
    "comparisons": [
        P(r"\b(?P<c>[a-z]+)\s+than\b", c=is_comparative),
        P(r"\b(?:more|less)\s+[a-z]+\s+than\b"),
        P(r"\bthe\s+(?:most|least)\s+(?P<a>[a-z]+)\b", a=is_adj),
        P(r"\bthe\s+(?P<s>[a-z]+)\b", s=is_superlative),
        P(r"\b(?:not\s+)?as\s+(?P<a>[a-z]+)\s+as\b", a=lambda w: is_adj(w) and w not in ("well", "soon", "long", "far")),
    ],
    "relative-clauses": [
        P(r"\b(?P<m>(?P<n>[a-z]+)\s+(?:who|whom|whose|which|where))\b", avoid=QUESTION, n=is_noun),
        P(r"\b(?:the|a|an|this|every|any)\s+(?:[a-z]+\s+)?(?P<m>(?P<n>[a-z]+)\s+that)\s+(?P<v>[a-z]+)\b",
          n=lambda w: is_noun(w) and w not in REPORT_NOUNS,
          v=lambda w: w in ("i", "you", "he", "she", "we", "they", "is", "was", "are", "were", "has", "had", "can",
                            "could", "will", "would") or is_s_verb(w) or is_past(w)),
    ],
    "verb-patterns": [
        P(r"\b(?P<v>[a-z]+)\s+(?:not\s+)?to\s+(?P<b>[a-z]+)\b", v=lambda w: verb_lemma(w) in TO_VERBS, b=is_base),
        P(r"\b(?P<v>[a-z]+)\s+(?P<g>[a-z]+ing)\b", v=lambda w: verb_lemma(w) in ING_VERBS, g=is_ing),
        P(r"\b(?:at|in|of|for|about|without|before|after|by)\s+(?P<g>[a-z]+ing)\b", g=is_ing),
    ],
    "passive": [
        P(r"\b(?:am|is|are|was|were|be|been|being|isn't|aren't|wasn't|weren't)\s+"
          + ADV.format("not|being|also|often|never|always|just|already|still|then|soon|usually|widely|easily|"
                       "carefully|quickly|first|finally|now|mostly|completely|badly")
          + r"(?P<v>[a-z]+)\b", v=lambda w: is_pp(w) and w not in ADJ_PP and w != "been"),
    ],
    "reported-speech": [
        P(r"\b(?P<m1>said|told\s+(?:me|him|her|them|us|you)|explained|replied|answered|promised|admitted|claimed|"
          r"complained|thought|knew|realized|realised)\s+(?:that\s+)?(?:" + SUBJ + r"|there)\s+(?P<m2>was|were|had|"
          r"would|could|might|should|wasn't|weren't|hadn't|wouldn't|couldn't|didn't)\b"),
        P(r"\b(?P<m1>asked(?:\s+(?:me|him|her|them|us|you))?)\s+(?P<m2>if|whether|what|where|why|how|when|who)\b"),
        P(r"\b(?P<m1>(?:told|asked|ordered|warned|begged|reminded)\s+(?:me|him|her|them|us|you))\s+"
          r"(?P<m2>(?:not\s+)?to\s+[a-z]+)\b"),
    ],
    "linking": [
        P(r"\b(?:because(?:\s+of)?|although|even\s+though|though|however|unless|so\s+that|in\s+order\s+to|"
          r"as\s+a\s+result|on\s+the\s+other\s+hand|therefore|instead\s+of|whereas)\b"),
        P(r",\s+(?P<m>so|but)\s+(?:" + SUBJ + r"|the|there|my|his|her|our|their|this|that)\b"),
    ],
}


def _marks(pat: Pattern, m: re.Match) -> list[tuple[int, int]] | None:
    for group, check in pat.checks:
        v = m.group(group)
        if v is not None and not check(v.lower()):
            return None
    marks = [m.span(g) for g in pat.rx.groupindex if g.startswith("m") and m.group(g) is not None]
    return sorted(marks) or [m.span()]


def find_in_paragraph(pid: str, para: str, sents: list[tuple[int, int]] | None = None) -> list[list[tuple[int, int]]]:
    """Each use of a grammar point in a paragraph, as the character spans to highlight."""
    text = para.replace("’", "'").replace("‘", "'")     # same length, so spans still fit `para`
    sents = sents if sents is not None else sentence_spans(text)
    found = []
    for pat in DETECTORS.get(pid, ()):
        if pat.paragraph:
            found += [mk for m in pat.rx.finditer(text) if (mk := _marks(pat, m))]
            continue
        for a, b in sents:
            sent = text[a:b]
            if (pat.need and not pat.need.search(sent)) or (pat.avoid and pat.avoid.search(sent)):
                continue
            for m in pat.rx.finditer(sent):
                mk = _marks(pat, m)
                if mk:
                    found.append([(s + a, e + a) for s, e in mk])
    # several patterns can find the same words: keep the first of overlapping matches
    kept, taken = [], []
    for mk in sorted(found):
        if not any(s < te and e > ts for s, e in mk for ts, te in taken):
            kept.append(mk)
            taken += mk
    return kept


def scan_text(text: str) -> dict[str, list[list[tuple[int, int, int]]]]:
    """Every grammar point in a text: point id -> matches -> (paragraph, start, end) marks."""
    paras = split_paragraphs(text)
    sents = [sentence_spans(p.replace("’", "'")) for p in paras]
    out = {}
    for p in content()[1]:
        out[p["id"]] = [[(pi, s, e) for s, e in mk] for pi, para in enumerate(paras)
                        for mk in find_in_paragraph(p["id"], para, sents[pi])]
    return out


def snippet(para: str, marks: list[tuple[int, int]], sents: list[tuple[int, int]]) -> str | None:
    """The sentence(s) around a match, with the marks as *asterisks*, if it is a good example."""
    s0 = next((a for a, b in sents if a <= marks[0][0] < b), None)
    e0 = next((b for a, b in sents if a < marks[-1][1] <= b), None)
    if s0 is None or e0 is None:
        return None
    text = para[s0:e0].strip()
    if not SNIPPET_WORDS[0] <= len(text.split()) <= SNIPPET_WORDS[1] or re.search(r"[\[\]_{}<>|#*]", text):
        return None
    out, pos = [], s0
    for s, e in marks:
        out += [para[pos:s], "*", para[s:e], "*"]
        pos = e
    out.append(para[pos:e0])
    s = "".join(out).strip()
    if sum(s.count(q) for q in '"“”') % 2:          # a quotation cut in half by the sentence split
        s = s[1:].lstrip() if s[0] in '"“' else s[:-1].rstrip() if s[-1] in '"”' else s
    return s


def find_examples(conn: sqlite3.Connection, sid: int, pid: str, limit: int = 4) -> list[dict]:
    """Sentences that use a grammar point, from library texts that fit the student (one per book)."""
    model = library.student_model(conn, sid)
    ix = library.index(conn)
    p = model.probs(ix)
    allowed = library.AUDIENCES.get(model.age, library.AUDIENCES["all"])
    books = {b["id"]: b for b in library.visible_books(conn, sid) if b["audience"] in allowed}
    ranked = []
    for key, v in ix.units.items():
        if key[0] in books:
            cov = v.coverage(p)
            ranked.append((abs(cov - model.target) + (0.02 if cov < model.target - 0.04 else 0), cov, key))
    ranked.sort(key=lambda r: r[:2])
    found: list[dict] = []
    for _, cov, (book_id, idx) in ranked[:SCAN_UNITS]:
        if len(found) >= limit:
            break
        if any(f["book"] == book_id for f in found):
            continue
        u = library.unit_row(conn, book_id, idx)
        hit = None
        for para in split_paragraphs(u["text"]):
            sents = sentence_spans(para.replace("’", "'"))
            hit = next((s for mk in find_in_paragraph(pid, para, sents) if (s := snippet(para, mk, sents))), None)
            if hit:
                break
        if hit:
            b = books[book_id]
            found.append({"sentence": hit, "book": book_id, "idx": idx, "title": b["title"],
                          "unit_title": u["title"] if u["title"] != b["title"] else "",
                          "fit": library.fit_of(cov, model.target)})
    return found


# ====================================================================== writing feedback (Claude)

WRITE_SYSTEM = """You are a warm, encouraging English teacher. A learner wrote a few sentences about their
own life to practise one grammar point. Check the text and fill in:
- "uses_target": true if the learner used the target grammar at least once, correctly or not.
- "correct": true if there are no grammar mistakes worth fixing.
- "corrected": the learner's text with the smallest changes that make it correct and natural. Keep their
  ideas and their words. If nothing needs fixing, repeat the text exactly.
- "fixes": up to 3 of the most useful corrections: the wrong words, the right words, and a very short
  reason in simple English. Grammar first; ignore small style choices and spelling of names.
- "feedback": 1-3 short sentences in simple English that suit the learner's level and age. First say one
  specific thing they did well, then give the most useful tip. If they did not use the target grammar,
  show how they could, using one of their own ideas.
Never be harsh. Avoid grammar terms the learner may not know, except the name of the target point."""

WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "uses_target": {"type": "boolean"},
        "correct": {"type": "boolean"},
        "corrected": {"type": "string"},
        "fixes": {"type": "array", "items": {
            "type": "object",
            "properties": {"wrong": {"type": "string"}, "right": {"type": "string"}, "why": {"type": "string"}},
            "required": ["wrong", "right", "why"], "additionalProperties": False}},
        "feedback": {"type": "string"},
    },
    "required": ["uses_target", "correct", "corrected", "fixes", "feedback"],
    "additionalProperties": False,
}


async def check_writing(p: dict, text: str, student: sqlite3.Row) -> dict:
    level = vocab.cefr(student["vocab_size"] or vocab.DEFAULT_VOCAB)
    age = {"kids": "a child (about 6-12)", "teens": "a teenager", "adults": "an adult"}.get(student["age_group"],
                                                                                          "any age")
    r = await ai.ask(WRITE_SYSTEM, "\n".join([
        f"Target grammar: {p['grammar']} ({p['title']}).",
        f"When to use it: {p['use']}",
        f"Task: {p['mission']}",
        f"Learner: CEFR level about {level}; {age}.",
        "", "Learner's text:", text,
    ]), WRITE_SCHEMA)
    fixes = [{k: str(f.get(k, "")).strip() for k in ("wrong", "right", "why")}
             for f in r.get("fixes", []) if isinstance(f, dict) and f.get("wrong")][:3]
    return {"uses_target": bool(r.get("uses_target")), "correct": bool(r.get("correct")),
            "corrected": str(r.get("corrected", "")).strip() or text, "fixes": fixes,
            "feedback": str(r.get("feedback", "")).strip()}


# ====================================================================== routes

@router.get("")
def overview(student: int, conn: Conn):
    student_row(conn, student)
    units, points, _ = content()
    rows = progress_rows(conn, student)
    cards = [card(p, rows.get(p["id"])) for p in points]
    return {"units": units, "points": cards, **summary(conn, student, today(), cards)}


@router.get("/point/{pid}")
def point_page(pid: str, student: int, conn: Conn):
    student_row(conn, student)
    p = get_point(pid)
    units, points, _ = content()
    i = points.index(p)
    row = conn.execute("SELECT * FROM grammar_progress WHERE student_id = ? AND point = ?", (student, pid)).fetchone()
    writing = [dict(r) for r in conn.execute(
        "SELECT id, day, text, corrected, feedback, ok FROM grammar_writing WHERE student_id = ? AND point = ? "
        "ORDER BY id DESC LIMIT ?", (student, pid, WRITING_SHOWN))]
    return {
        "point": {k: p[k] for k in ("id", "unit", "order", "title", "grammar", "band", "use", "form", "examples",
                                    "mistakes", "mission")},
        "unit": next(u for u in units if u["id"] == p["unit"]),
        "progress": status_of(row),
        "questions": len(p["questions"]) + min(PRACTICE_DICTATIONS, len(p["examples"])),
        "prev": brief(points[i - 1]) if i else None,
        "next": brief(points[i + 1]) if i + 1 < len(points) else None,
        "writing": writing,
        "ai": ai.status()["configured"],
    }


@router.get("/examples/{pid}")
def book_examples(pid: str, student: int, conn: Conn, limit: int = Query(4, ge=1, le=8)):
    student_row(conn, student)
    get_point(pid)
    return {"examples": find_examples(conn, student, pid, limit)}


@router.get("/session")
def session(student: int, conn: Conn, point: str | None = None):
    """One point's practice (all its questions + dictation), or a mixed review of due points."""
    student_row(conn, student)
    rng = random.Random()
    if point:
        items, mode = practice_items(get_point(point), rng), "practice"
    else:
        items, mode = review_items(conn, student, today(), rng), "review"
    points = content()[2]
    return {"mode": mode, "items": items,
            "points": {pid: brief(points[pid]) for pid in dict.fromkeys(it["point"] for it in items)}}


class AnswerIn(BaseModel):
    q: str = Field(min_length=1, max_length=10)
    correct: bool


class PointResultIn(BaseModel):
    point: str = Field(min_length=1, max_length=60)
    answers: list[AnswerIn] = Field(min_length=1, max_length=40)


class ResultIn(BaseModel):
    student: int
    results: list[PointResultIn] = Field(min_length=1, max_length=30)


@router.post("/result")
def save_result(body: ResultIn, conn: Conn):
    student_row(conn, body.student)
    t = today()
    out = []
    for r in body.results:
        p = get_point(r.point)
        row = conn.execute("SELECT * FROM grammar_progress WHERE student_id = ? AND point = ?",
                           (body.student, p["id"])).fetchone()
        box = row["box"] if row else 0
        right = sum(a.correct for a in r.answers)
        score = right / len(r.answers)
        new_box, due = schedule(box, row["due"] if row else None, score, t)
        missed = set(json.loads(row["missed"])) if row else set()
        missed = (missed - {a.q for a in r.answers if a.correct}) | {a.q for a in r.answers if not a.correct}
        conn.execute(
            "INSERT INTO grammar_progress(student_id, point, box, due, sessions, correct, wrong, last_score, missed) "
            "VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?) ON CONFLICT(student_id, point) DO UPDATE SET box = excluded.box, "
            "due = excluded.due, sessions = sessions + 1, correct = correct + excluded.correct, "
            "wrong = wrong + excluded.wrong, last_score = excluded.last_score, missed = excluded.missed, "
            "updated_at = datetime('now')",
            (body.student, p["id"], new_box, due.isoformat(), right, len(r.answers) - right, round(score, 3),
             json.dumps(sorted(missed))))
        db.log_activity(conn, body.student, t, "g:" + p["id"], "grammar", score >= GOOD)
        out.append({"point": p["id"], "right": right, "total": len(r.answers), "box": new_box,
                    "due": due.isoformat(), "status": srs.status(new_box),
                    "moved": "up" if new_box > box else "down" if new_box < box else "same"})
    conn.commit()
    return {"results": out}


class WriteIn(BaseModel):
    student: int
    point: str = Field(min_length=1, max_length=60)
    text: str = Field(min_length=1, max_length=1000)


@router.post("/write")
async def write(body: WriteIn, conn: Conn):
    """Save the student's own sentences; with a Claude key, also check them."""
    s = student_row(conn, body.student)
    p = get_point(body.point)
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Write something first")
    configured = ai.status()["configured"]
    result, error = None, None
    if configured:
        try:
            result = await check_writing(p, text, s)
        except ai.AIError as exc:
            error = str(exc)
    t = today()
    cur = conn.execute(
        "INSERT INTO grammar_writing(student_id, point, day, text, corrected, feedback, ok) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (body.student, p["id"], t.isoformat(), text, result["corrected"] if result else "",
         result["feedback"] if result else "",
         None if result is None else int(result["correct"] and result["uses_target"])))
    db.log_activity(conn, body.student, t, "g:" + p["id"], "write")
    conn.commit()
    return {"id": cur.lastrowid, "ai": configured, "check": result, "error": error}


@router.get("/scan")
def scan(student: int, book: str, idx: int, conn: Conn):
    """Grammar points in one library text, with the spans to highlight in the reader."""
    student_row(conn, student)
    b = conn.execute("SELECT id FROM books WHERE id = ? AND (owner IS NULL OR owner = ?)", (book, student)).fetchone()
    u = library.unit_row(conn, book, idx)
    if b is None or u is None:
        raise HTTPException(404, "Unknown text")
    found = scan_text(u["text"])
    return {
        "points": [{**brief(p), "count": len(found[p["id"]])} for p in content()[1] if found[p["id"]]],
        "spans": {pid: [list(m) for mk in matches for m in mk] for pid, matches in found.items() if matches},
    }
