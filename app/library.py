"""Reading library: books split into units (a whole story or one chapter), indexed by lemma
and matched to each student by predicted lexical coverage — the share of running words the
student probably knows.

Like BERT's masking rate, the share of unknown ("masked") words decides whether a text
teaches or frustrates: about 2% unknown is comfortable reading, about 5% is study reading
with support, and much more than that is too hard. Each student has a personal target
(students.target_coverage) that moves with their own ratings and check results.
"""
from __future__ import annotations

import json
import random
import re
import sqlite3
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

import lemminflect
import numpy as np

from . import srs, vocab
from .content import curriculum, word_key
from .textproc import Analysis, analyze, is_dictionary_word, lemma, sentence_spans

# Fit bands around the student's target coverage T (default 98% known).
EASY_ABOVE = 0.01          # coverage >= T + 1%: easy (fluency practice)
RIGHT_BELOW = 0.01         # T - 1% <= coverage < T + 1%: just right
CHALLENGE_BELOW = 0.04     # T - 4% <= coverage < T - 1%: challenge (learn the new words first)
TARGET_MIN, TARGET_MAX = 0.95, 0.99
LEVEL_COVERAGE = 0.95      # a text's level = vocabulary needed for this coverage
PRELEARN_MAX = 8
P_MASTERED, P_LEARNING, P_LOOKED_UP = 0.97, 0.55, 0.15
COMMON_RANK = 150          # the most frequent lemmas are never the target of a check question
# Web frequency underrates words children meet early ("crocodile", "mango"), so a word found
# in at least KID_MIN_STORIES storybooks gets rank min(web rank, KID_FACTOR x its storybook rank).
KID_FACTOR, KID_MIN_STORIES = 3, 3


def fit_of(coverage: float, target: float) -> str:
    if coverage >= target + EASY_ABOVE:
        return "easy"
    if coverage >= target - RIGHT_BELOW:
        return "right"
    if coverage >= target - CHALLENGE_BELOW:
        return "challenge"
    return "hard"


# ====================================================================== storing books

def save_book(conn: sqlite3.Connection, book: dict, units: list[tuple[str, str]]) -> str:
    """Store (or replace) a book and its units. `units` is a list of (title, text)."""
    analyses = [(title, text, analyze(text)) for title, text in units]
    analyses = [u for u in analyses if u[2].words]
    if not analyses:
        raise ValueError("The text has no English words")
    total = Counter()
    free = words = sentences = 0
    for _, _, a in analyses:
        total.update(a.counts)
        free += a.free_tokens
        words += a.words
        sentences += a.sentences
    slen = words / sentences if sentences else 0.0
    conn.execute("DELETE FROM books WHERE id = ?", (book["id"],))
    conn.execute(
        "INSERT INTO books(id, source, title, author, audience, credit, license, url, owner, words, units, "
        "sentence_len, meta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (book["id"], book["source"], book["title"], book.get("author", ""), book.get("audience", "all"),
         book.get("credit", ""), book.get("license", ""), book.get("url", ""), book.get("owner"),
         words, len(analyses), round(slen, 1), json.dumps(book.get("meta", {}))))
    for i, (title, text, a) in enumerate(analyses):
        conn.execute(
            "INSERT INTO units(book_id, idx, title, text, words, free_tokens, sentence_len) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (book["id"], i, title, "\n\n".join(a.paragraphs), a.words, a.free_tokens, round(a.sentence_len, 1)))
        conn.executemany("INSERT INTO unit_lemmas(book_id, idx, lemma, n) VALUES (?, ?, ?, ?)",
                         [(book["id"], i, lm, n) for lm, n in a.counts.items()])
    conn.commit()
    changed()
    return book["id"]


def delete_book(conn: sqlite3.Connection, book_id: str) -> None:
    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    changed()


# ====================================================================== in-memory index

@dataclass
class Vec:
    ids: np.ndarray          # lemma ids
    counts: np.ndarray       # running words per lemma
    words: int
    free: int
    sentence_len: float = 0.0
    level: int = 0           # vocabulary needed for 95% coverage
    cefr: str = ""

    def coverage(self, p: np.ndarray) -> float:
        if not self.words:
            return 1.0
        return float((self.free + (p[self.ids] * self.counts).sum()) / self.words)

    def set_level(self, ranks: np.ndarray) -> None:
        """Long sentences make a text harder than its words alone suggest, so the CEFR label
        uses the vocabulary figure raised by 4% per word of average sentence length above 14."""
        need = LEVEL_COVERAGE * self.words - self.free
        if len(self.ids) and need > 0:
            r = ranks[self.ids]
            order = np.argsort(r)
            reached = np.searchsorted(np.cumsum(self.counts[order]), need)
            self.level = int(r[order][min(reached, len(order) - 1)])
        self.cefr = vocab.cefr(self.level * (1 + 0.04 * max(0.0, self.sentence_len - 14)))


@dataclass
class Index:
    version: int
    lemma_id: dict[str, int] = field(default_factory=dict)
    lemmas: list[str] = field(default_factory=list)
    ranks: np.ndarray = field(default_factory=lambda: np.zeros(0))   # effective ranks
    units: dict[tuple[str, int], Vec] = field(default_factory=dict)
    books: dict[str, Vec] = field(default_factory=dict)

    def rank(self, lemma_key: str) -> float:
        lid = self.lemma_id.get(lemma_key)
        return float(self.ranks[lid]) if lid is not None else float(vocab.rank(lemma_key))


_version = 0
_index: Index | None = None
_lock = threading.Lock()


def changed() -> None:
    global _version
    _version += 1


def index(conn: sqlite3.Connection) -> Index:
    """Lemma vectors for every unit and book, rebuilt after the library changes."""
    global _index
    with _lock:
        if _index is not None and _index.version == _version:
            return _index
        ix = Index(_version)
        per_unit: dict[tuple[str, int], tuple[list[int], list[int]]] = {}
        for book_id, idx, lm, n in conn.execute("SELECT book_id, idx, lemma, n FROM unit_lemmas"):
            lid = ix.lemma_id.get(lm)
            if lid is None:
                lid = ix.lemma_id[lm] = len(ix.lemmas)
                ix.lemmas.append(lm)
            ids, counts = per_unit.setdefault((book_id, idx), ([], []))
            ids.append(lid)
            counts.append(n)
        ix.ranks = np.array([vocab.rank(lm) for lm in ix.lemmas], dtype=float)
        stories = Counter(lm for (lm,) in conn.execute(
            "SELECT lemma FROM unit_lemmas JOIN books ON books.id = unit_lemmas.book_id WHERE books.source = 'storybook'"))
        for kid_rank, (lm, n) in enumerate(stories.most_common(), 1):
            if n < KID_MIN_STORIES:
                break
            lid = ix.lemma_id[lm]
            ix.ranks[lid] = min(ix.ranks[lid], KID_FACTOR * kid_rank)
        book_parts: dict[str, list[Vec]] = {}
        for r in conn.execute("SELECT book_id, idx, words, free_tokens, sentence_len FROM units"):
            ids, counts = per_unit.get((r["book_id"], r["idx"]), ([], []))
            v = Vec(np.array(ids, dtype=np.int32), np.array(counts, dtype=np.int32), r["words"], r["free_tokens"],
                    r["sentence_len"])
            v.set_level(ix.ranks)
            ix.units[(r["book_id"], r["idx"])] = v
            book_parts.setdefault(r["book_id"], []).append(v)
        slen = {r["id"]: r["sentence_len"] for r in conn.execute("SELECT id, sentence_len FROM books")}
        for book_id, parts in book_parts.items():
            if len(parts) == 1:
                ix.books[book_id] = parts[0]
                continue
            agg = Counter()
            for v in parts:
                agg.update(dict(zip(v.ids.tolist(), v.counts.tolist())))
            v = Vec(np.array(list(agg), dtype=np.int32), np.array(list(agg.values()), dtype=np.int32),
                    sum(v.words for v in parts), sum(v.free for v in parts), slen.get(book_id, 0.0))
            v.set_level(ix.ranks)
            ix.books[book_id] = v
        _index = ix
        return ix


# ====================================================================== student model

@dataclass
class StudentModel:
    id: int
    vocab: float
    target: float
    age: str
    reading_goal: int
    overrides: dict[str, float]
    learning: set[str]
    mastered: set[str]
    due: set[str]
    rank: object = vocab.rank        # lemma -> effective rank (Index.rank)

    def p(self, lemma_key: str) -> float:
        if lemma_key in self.overrides:
            return self.overrides[lemma_key]
        return float(vocab.p_known(self.rank(lemma_key), self.vocab))

    def probs(self, ix: Index) -> np.ndarray:
        p = vocab.p_known(ix.ranks, self.vocab) if len(ix.ranks) else np.zeros(0)
        for lm, pk in self.overrides.items():
            lid = ix.lemma_id.get(lm)
            if lid is not None:
                p[lid] = pk
        return p


def student_model(conn: sqlite3.Connection, sid: int, today: date | None = None) -> StudentModel:
    today = today or date.today()
    s = conn.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    overrides: dict[str, float] = {}
    since = (today - timedelta(days=60)).isoformat()
    for r in conn.execute("SELECT DISTINCT word FROM lookups WHERE student_id = ? AND day >= ?", (sid, since)):
        overrides[r["word"]] = P_LOOKED_UP
    learning, mastered, due = set(), set(), set()
    for r in conn.execute("SELECT word, box, due FROM progress WHERE student_id = ? AND box > 0", (sid,)):
        if srs.status(r["box"]) == "mastered":
            mastered.add(r["word"])
            overrides[r["word"]] = P_MASTERED
        else:
            learning.add(r["word"])
            overrides[r["word"]] = P_LEARNING
        if r["due"] and r["due"] <= today.isoformat():
            due.add(r["word"])
    return StudentModel(sid, float(s["vocab_size"] or vocab.DEFAULT_VOCAB), float(s["target_coverage"]),
                        s["age_group"], s["reading_goal"], overrides, learning, mastered, due, index(conn).rank)


# ====================================================================== listing and recommending

AUDIENCES = {"kids": ("kids", "all"), "teens": ("kids", "all", "teens"), "adults": ("kids", "all", "teens"),
             "all": ("kids", "all", "teens")}


def visible_books(conn: sqlite3.Connection, sid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM books WHERE owner IS NULL OR owner = ? ORDER BY title", (sid,)).fetchall()


def reading_state(conn: sqlite3.Connection, sid: int) -> dict[str, dict]:
    """Per book: finished unit numbers, and the unit of the latest unfinished session."""
    state: dict[str, dict] = {}
    for r in conn.execute("SELECT book_id, idx, finished, position, id FROM reads WHERE student_id = ? ORDER BY id",
                          (sid,)):
        st = state.setdefault(r["book_id"], {"finished": set(), "open": None, "last": 0})
        if r["finished"]:
            st["finished"].add(r["idx"])
        else:
            st["open"] = (r["idx"], r["position"])
        st["last"] = r["id"]
    for st in state.values():
        if st["open"] and st["open"][0] in st["finished"]:
            st["open"] = None
    return state


def next_unit(book: sqlite3.Row, st: dict | None) -> int | None:
    """The unit to read next: an open session, else the first unfinished unit."""
    if st and st["open"]:
        return st["open"][0]
    done = st["finished"] if st else set()
    return next((i for i in range(book["units"]) if i not in done), None)


def book_card(b: sqlite3.Row, v: Vec, p: np.ndarray, model: StudentModel, st: dict | None,
              learning_hits: int = 0) -> dict:
    done = len(st["finished"]) if st else 0
    cov = v.coverage(p)
    return {
        "id": b["id"], "title": b["title"], "author": b["author"], "source": b["source"],
        "audience": b["audience"], "words": b["words"], "units": b["units"], "cefr": v.cefr, "level": v.level,
        "minutes": max(1, round(b["words"] / 120)), "coverage": round(cov, 4), "unknown_per_100": round(100 * (1 - cov), 1),
        "fit": fit_of(cov, model.target), "done_units": done, "finished": done >= b["units"],
        "next_unit": next_unit(b, st), "learning_hits": learning_hits, "credit": b["credit"], "license": b["license"],
    }


def library(conn: sqlite3.Connection, sid: int, *, q: str = "", source: str = "", fit: str = "",
            cefr: str = "", audience: str = "", sort: str = "fit") -> dict:
    model = student_model(conn, sid)
    ix = index(conn)
    p = model.probs(ix)
    state = reading_state(conn, sid)
    allowed = AUDIENCES.get(model.age, AUDIENCES["all"])
    learning_ids = np.array([ix.lemma_id[w] for w in model.learning if w in ix.lemma_id], dtype=np.int32)
    cards = []
    for b in visible_books(conn, sid):
        v = ix.books.get(b["id"])
        if v is None or b["audience"] not in (audience.split(",") if audience else allowed):
            continue
        if source and b["source"] != source:
            continue
        if q and q.lower() not in (b["title"] + " " + b["author"]).lower():
            continue
        if cefr and v.cefr != cefr:
            continue
        hits = int(np.isin(v.ids, learning_ids).sum()) if len(learning_ids) else 0
        card = book_card(b, v, p, model, state.get(b["id"]), hits)
        if fit and card["fit"] != fit:
            continue
        cards.append(card)
    if sort == "fit":
        cards.sort(key=lambda c: (abs(c["coverage"] - model.target), c["title"]))
    elif sort == "easy":
        cards.sort(key=lambda c: -c["coverage"])
    elif sort == "short":
        cards.sort(key=lambda c: c["words"])
    return {"books": cards, "target": model.target, "vocab": round(model.vocab), "cefr": vocab.cefr(model.vocab)}


def recommend(conn: sqlite3.Connection, sid: int, per_group: int = 6) -> dict:
    """Next units to read, grouped by fit, plus books the student is in the middle of."""
    model = student_model(conn, sid)
    ix = index(conn)
    p = model.probs(ix)
    state = reading_state(conn, sid)
    allowed = AUDIENCES.get(model.age, AUDIENCES["all"])
    beginner = model.vocab < 2000
    learning_ids = np.array([ix.lemma_id[w] for w in model.learning if w in ix.lemma_id], dtype=np.int32)
    groups: dict[str, list] = {"right": [], "challenge": [], "easy": [], "hard": []}
    cont = []
    for b in visible_books(conn, sid):
        if b["audience"] not in allowed:
            continue
        st = state.get(b["id"])
        u = next_unit(b, st)
        v = ix.units.get((b["id"], u)) if u is not None else None
        if v is None:
            continue
        cov = v.coverage(p)
        hits = int(np.isin(v.ids, learning_ids).sum()) if len(learning_ids) else 0
        card = {**book_card(b, ix.books[b["id"]], p, model, st, hits),
                "unit": u, "unit_coverage": round(cov, 4), "unit_fit": fit_of(cov, model.target),
                "unit_words": v.words, "unit_cefr": v.cefr}
        score = abs(cov - model.target) - 0.002 * min(hits, 5)
        if b["audience"] == "kids" and model.age in ("teens", "adults") and not beginner:
            score += 0.01                      # older students see children's stories only when nothing else fits
        if st and (st["open"] or st["finished"]):
            cont.append((-st["last"], card))
            continue
        if card["unit_fit"] in groups:
            groups[card["unit_fit"]].append((score, card))
    hard = groups.pop("hard")
    out = {k: [c for _, c in sorted(v, key=lambda t: t[0])[:per_group]] for k, v in groups.items()}
    # when nothing fits yet (true beginners), the easiest of the harder texts, read with word help
    out["stretch"] = [c for _, c in sorted(hard, key=lambda t: -t[1]["unit_coverage"])[:per_group]]
    out["continue"] = [c for _, c in sorted(cont, key=lambda t: t[0])[:per_group]]
    out["today"] = (out["continue"] or out["right"] or out["challenge"] or out["easy"] or out["stretch"]
                    or [None])[0]
    out.update(target=model.target, vocab=round(model.vocab), cefr=vocab.cefr(model.vocab))
    return out


# ====================================================================== reader

def phrase_keys(conn: sqlite3.Connection, model: StudentModel) -> list[str]:
    """Multi-word items worth spotting in a text: curriculum phrasal verbs and the student's own."""
    keys = {k for k in curriculum()[1] if " " in k}
    keys |= {r["word"] for r in conn.execute("SELECT DISTINCT word FROM custom_words WHERE word LIKE '% %'")}
    keys |= {w for w in model.learning | model.mastered if " " in w}
    return sorted(keys)


def find_phrases(tokens: list, keys: list[str]) -> dict[int, str]:
    """token position -> phrase key, for verb + particle(s) with at most one word in between."""
    by_head: dict[str, list[tuple[str, list[str]]]] = {}
    for key in keys:
        head, *rest = key.split()
        by_head.setdefault(lemma(head), []).append((key, rest))
    found: dict[int, str] = {}
    for i, t in enumerate(tokens):
        for key, rest in by_head.get(t.lemma, []):
            hit, j = [i], i + 1
            for part in rest:
                k = next((k for k in range(j, min(j + 2, len(tokens))) if tokens[k].surface.lower() == part), None)
                if k is None:
                    break
                hit.append(k)
                j = k + 1
            else:
                for pos in hit:
                    found.setdefault(pos, key)
                break
    return found


def unit_row(conn: sqlite3.Connection, book_id: str, idx: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM units WHERE book_id = ? AND idx = ?", (book_id, idx)).fetchone()


def token_class(t, model: StudentModel, targets: set[str]) -> str:
    if t.kind != "word":
        return "n"
    if t.lemma in targets:
        return "t"
    if t.lemma in model.learning:
        return "l"
    if t.lemma in model.mastered:
        return "m"
    return "u" if model.p(t.lemma) < 0.5 else "k"


def prelearn_words(a: Analysis, model: StudentModel, limit: int = PRELEARN_MAX) -> list[dict]:
    """The words most worth learning before reading: probably unknown, frequent in this text."""
    cands = [(n, lm) for lm, n in a.counts.items()
             if lm not in model.learning and model.p(lm) < 0.5 and len(lm) > 2 and is_dictionary_word(lm)]
    cands.sort(key=lambda t: (-t[0], vocab.rank(t[1])))
    return [{"word": lm, "count": n} for n, lm in cands[:limit]]


def reader(conn: sqlite3.Connection, sid: int, book_id: str, idx: int) -> dict | None:
    b = conn.execute("SELECT * FROM books WHERE id = ? AND (owner IS NULL OR owner = ?)", (book_id, sid)).fetchone()
    u = unit_row(conn, book_id, idx)
    if b is None or u is None:
        return None
    model = student_model(conn, sid)
    a = analyze(u["text"])
    meta = json.loads(b["meta"] or "{}")
    targets = {word_key(w) for w in meta.get("target_words", [])}
    keys = phrase_keys(conn, model)
    paragraphs = []
    for text, toks in zip(a.paragraphs, a.tokens):
        phrases = find_phrases(toks, keys)
        words = []
        for i, t in enumerate(toks):
            cls = token_class(t, model, targets)
            ph = phrases.get(i)
            if ph and (ph in model.learning or ph in targets):
                cls = "t" if ph in targets else "l"
            words.append([t.start, t.end, t.lemma, cls] + ([ph] if ph else []))
        paragraphs.append({"t": text, "w": words})
    ix = index(conn)
    v = ix.units[(book_id, idx)]
    cov = v.coverage(model.probs(ix))
    st = reading_state(conn, sid).get(book_id)
    learning_here = sorted({t.lemma for toks in a.tokens for t in toks if t.lemma in model.learning})
    titles = [r["title"] for r in conn.execute("SELECT title FROM units WHERE book_id = ? ORDER BY idx", (book_id,))]
    return {
        "book": {"id": b["id"], "title": b["title"], "author": b["author"], "source": b["source"],
                 "credit": b["credit"], "license": b["license"], "url": b["url"], "units": b["units"],
                 "cefr": ix.books[book_id].cefr, "titles": titles},
        "unit": {"idx": idx, "title": u["title"], "words": u["words"], "cefr": v.cefr},
        "paragraphs": paragraphs,
        "coverage": round(cov, 4), "unknown_per_100": round(100 * (1 - cov), 1),
        "fit": fit_of(cov, model.target), "target": model.target,
        "prelearn": prelearn_words(a, model), "learning_here": learning_here,
        "target_words": sorted(targets), "grammar": meta.get("grammar"),
        "finished": bool(st and idx in st["finished"]),
        "position": st["open"][1] if st and st["open"] and st["open"][0] == idx else 0,
        "has_questions": conn.execute("SELECT 1 FROM unit_questions WHERE book_id = ? AND idx = ?",
                                      (book_id, idx)).fetchone() is not None,
    }


# ====================================================================== masked-word check

SHAPES = (("ing", re.compile(r"ing$")), ("ed", re.compile(r"ed$")), ("ly", re.compile(r"ly$")),
          ("s", re.compile(r"[^s]s$")))


def shape(word: str) -> str:
    """Ending class plus part-of-speech set, so options fit the sentence's grammar equally well."""
    w = word.lower()
    ending = next((name for name, rx in SHAPES if rx.search(w)), "base")
    if ending == "base" and lemma(w) != w:
        ending = "inflected"                         # "eaten", "went": not interchangeable with "cook"
    pos = sorted(set(lemminflect.getAllLemmas(w)) & {"VERB", "NOUN", "ADJ", "ADV"})
    return f"{ending}:{'/'.join(pos)}"


def masked_check(conn: sqlite3.Connection, sid: int, book_id: str, idx: int, n: int = 6,
                 rng: random.Random | None = None) -> list[dict]:
    """BERT-style check: hide one word in a few sentences and ask for it back.

    Targets are words the student is learning (so the check doubles as a review) or words of
    middling difficulty for them; the three wrong options come from the same text, with the
    same ending (-ing, -ed, -s, -ly), so grammar alone doesn't give the answer away.
    """
    rng = rng or random.Random()
    u = unit_row(conn, book_id, idx)
    if u is None:
        return []
    model = student_model(conn, sid)
    a = analyze(u["text"])
    pool: dict[str, set[str]] = {}
    sents = []
    for text, toks in zip(a.paragraphs, a.tokens):
        for s, e in sentence_spans(text):
            st = [t for t in toks if s <= t.start < e]
            if 6 <= len(st) <= 30:
                sents.append((text[s:e].strip(), s, st))
            for t in st:
                if t.kind == "word" and t.surface.isalpha() and vocab.rank(t.lemma) > COMMON_RANK:
                    pool.setdefault(shape(t.surface), set()).add(t.surface.lower())

    def candidates(st):
        out = []
        for t in st:
            if t.kind != "word" or not t.surface.isalpha() or len(t.surface) < 3 or vocab.rank(t.lemma) <= COMMON_RANK:
                continue
            pk = model.p(t.lemma)
            weight = 3.0 if t.lemma in model.learning else (1.0 if 0.35 <= pk <= 0.98 else 0.0)
            if weight:
                out.append((weight + rng.random(), t))
        return sorted(out, key=lambda x: -x[0])

    chosen = []
    buckets = np.array_split(np.arange(len(sents)), min(n, len(sents))) if sents else []
    for bucket in buckets:
        best = None
        for i in bucket:
            c = candidates(sents[i][2])
            if c and (best is None or c[0][0] > best[0]):
                best = (c[0][0], i, c[0][1])
        if best:
            chosen.append(best[1:])
    questions = []
    for i, t in chosen:
        sentence, offset, _ = sents[i]
        answer = t.surface
        exact, ending = shape(answer), shape(answer).split(":")[0]
        same = [w for w in pool.get(exact, set()) if lemma(w) != t.lemma and w not in sentence.lower()]
        if len(same) < 3:                            # fall back to the same ending, any part of speech
            same = [w for k, ws in pool.items() if k.split(":")[0] == ending for w in ws
                    if lemma(w) != t.lemma and w not in sentence.lower()]
        if len(same) < 3:
            continue
        wrong = rng.sample(sorted(same), 3)
        if answer[0].isupper():
            wrong = [w.capitalize() for w in wrong]
        options = wrong + [answer]
        rng.shuffle(options)
        start = t.start - offset
        prompt = sentence[:start] + "_____" + sentence[start + len(answer):]
        questions.append({"id": len(questions), "prompt": prompt, "options": options,
                          "answer": options.index(answer), "word": t.lemma, "answer_text": answer,
                          "sentence": sentence})
    return questions
