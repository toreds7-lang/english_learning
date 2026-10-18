"""Reading routes: library, reader, lookups, masked-word checks, placement test and level tracking.

How reading and the word steps feed each other:
- Before reading, the few probably-unknown words of a text can be learned as flashcards.
- While reading, tapping a word shows its entry and can save it to spaced review, with the
  sentence it came from; words being learned are highlighted in the text.
- After reading, the masked-word check reviews due words in context (a correct answer counts
  as a review), and the student's level and comfort target are updated.
- On a word's page, "Read it in a story" lists library texts that use it and fit the student.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import ai, db, grammar, library, sources, srs, vocab
from .content import word_key
from .deps import Conn, student_row
from .textproc import analyze, base_form, lemma, sentence_spans

router = APIRouter(prefix="/api")

CHECK_GOOD = 0.6          # masked-word score that shows the text was understood
PLACEMENT_SD = 0.35       # trust in a placement result (log scale), before reading evidence
NO_PLACEMENT_SD = 0.8
TAPLESS_WEIGHT = 0.1      # evidence weight of a word read past without tapping it
TAPLESS_PER_READ = 30
PHRASE_SCAN = 60          # texts searched for a phrasal verb on a word's page


def today() -> date:
    return date.today()


def lemma_key(word: str) -> str:
    """Lemma for a single word, normalized key for a phrase."""
    k = word_key(word)
    return k if " " in k else lemma(base_form(k))


# ====================================================================== level estimate

def vocab_evidence(conn: sqlite3.Connection, sid: int, model: library.StudentModel) -> list[tuple[float, int, float]]:
    """(rank, known, weight) observations from flashcards, taps, checks and finished reading."""
    rank = model.rank
    ev: list[tuple[float, int, float]] = []
    for (w,) in conn.execute("SELECT DISTINCT word FROM activity WHERE student_id = ? AND kind = 'know'", (sid,)):
        if " " not in w:
            ev.append((rank(lemma_key(w)), 1, 1.0))
    looked_up = {r["word"] for r in conn.execute("SELECT DISTINCT word FROM lookups WHERE student_id = ?", (sid,))}
    ev += [(rank(w), 0, 1.0) for w in looked_up if " " not in w]
    reads = conn.execute(
        "SELECT book_id, idx, rating, check_right, check_total, check_data FROM reads "
        "WHERE student_id = ? AND finished = 1 ORDER BY id DESC LIMIT 60", (sid,)).fetchall()
    lo, hi = model.vocab / 3, model.vocab * 3
    for r in reads:
        for a in json.loads(r["check_data"] or "[]"):
            ev.append((rank(a["word"]), int(bool(a["correct"])), 0.5))
        understood = r["check_total"] and r["check_right"] / r["check_total"] >= CHECK_GOOD and r["rating"] != "hard"
        if not understood:
            continue
        tapped_here = {x["word"] for x in conn.execute(
            "SELECT word FROM lookups WHERE student_id = ? AND book_id = ? AND idx = ?", (sid, r["book_id"], r["idx"]))}
        rows = conn.execute("SELECT lemma FROM unit_lemmas WHERE book_id = ? AND idx = ?", (r["book_id"], r["idx"]))
        passed = [rank(x["lemma"]) for x in rows if x["lemma"] not in tapped_here and lo <= rank(x["lemma"]) <= hi]
        ev += [(rk, 1, TAPLESS_WEIGHT) for rk in sorted(passed)[:TAPLESS_PER_READ]]
    return ev


def update_vocab(conn: sqlite3.Connection, sid: int, source: str = "reading") -> float:
    model = library.student_model(conn, sid)
    placed = conn.execute("SELECT vocab FROM placements WHERE student_id = ? ORDER BY id DESC LIMIT 1",
                          (sid,)).fetchone()
    prior, sd = (placed["vocab"], PLACEMENT_SD) if placed else (vocab.DEFAULT_VOCAB, NO_PLACEMENT_SD)
    v = vocab.estimate_vocab(vocab_evidence(conn, sid, model), prior, sd)
    save_vocab(conn, sid, v, source)
    return v


def save_vocab(conn: sqlite3.Connection, sid: int, v: float, source: str) -> None:
    conn.execute("UPDATE students SET vocab_size = ? WHERE id = ?", (round(v), sid))
    conn.execute("INSERT INTO vocab_history(student_id, day, vocab, source) VALUES (?, ?, ?, ?) "
                 "ON CONFLICT(student_id, day) DO UPDATE SET vocab = excluded.vocab, source = excluded.source",
                 (sid, today().isoformat(), round(v), source))
    conn.commit()


def adjust_target(target: float, rating: str | None, check_ratio: float | None) -> float:
    """A text rated too hard (or poorly understood) raises the share of known words aimed for."""
    if rating == "hard":
        target += 0.005
    elif rating == "easy":
        target -= 0.005
    if check_ratio is not None:
        if check_ratio < 0.5:
            target += 0.005
        elif check_ratio >= 0.85 and rating != "hard":
            target -= 0.0025
    return round(min(max(target, library.TARGET_MIN), library.TARGET_MAX), 4)


# ====================================================================== library

@router.get("/library/status")
def library_status(conn: Conn):
    counts = {r["source"]: {"books": r["n"], "words": r["w"]} for r in conn.execute(
        "SELECT source, COUNT(*) n, SUM(words) w FROM books WHERE owner IS NULL GROUP BY source")}
    return {"counts": counts, "jobs": sources.JOBS, "ai": ai.status(),
            "gutenberg_titles": len(sources.GUTENBERG_BOOKS)}


@router.post("/library/import/{source}")
def library_import(source: Literal["storybooks", "gutenberg"]):
    return sources.start_import(source)


@router.get("/library")
def get_library(student: int, conn: Conn, q: str = "", source: str = "", fit: str = "", cefr: str = "",
                audience: str = "", sort: Literal["fit", "easy", "short", "title"] = "fit"):
    student_row(conn, student)
    return library.library(conn, student, q=q, source=source, fit=fit, cefr=cefr, audience=audience, sort=sort)


@router.get("/library/recommend")
def get_recommend(student: int, conn: Conn):
    student_row(conn, student)
    return library.recommend(conn, student)


@router.get("/library/book/{book_id}")
def get_book(book_id: str, student: int, conn: Conn):
    student_row(conn, student)
    b = conn.execute("SELECT * FROM books WHERE id = ? AND (owner IS NULL OR owner = ?)", (book_id, student)).fetchone()
    if b is None:
        raise HTTPException(404, "Unknown book")
    model = library.student_model(conn, student)
    ix = library.index(conn)
    p = model.probs(ix)
    st = library.reading_state(conn, student).get(book_id)
    units = []
    for u in conn.execute("SELECT idx, title, words FROM units WHERE book_id = ? ORDER BY idx", (book_id,)):
        v = ix.units[(book_id, u["idx"])]
        cov = v.coverage(p)
        units.append({"idx": u["idx"], "title": u["title"], "words": u["words"], "cefr": v.cefr,
                      "coverage": round(cov, 4), "fit": library.fit_of(cov, model.target),
                      "done": bool(st and u["idx"] in st["finished"])})
    card = library.book_card(b, ix.books[book_id], p, model, st)
    return {**card, "url": b["url"], "units_list": units, "deletable": b["source"] in ("teacher", "ai"),
            "meta": json.loads(b["meta"] or "{}")}


@router.delete("/library/book/{book_id}")
def remove_book(book_id: str, conn: Conn):
    b = conn.execute("SELECT source FROM books WHERE id = ?", (book_id,)).fetchone()
    if b is None:
        raise HTTPException(404, "Unknown book")
    if b["source"] not in ("teacher", "ai"):
        raise HTTPException(400, "Only teachers' texts and AI stories can be deleted")
    library.delete_book(conn, book_id)
    return {"ok": True}


class TextIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=20, max_length=400_000)
    author: str = Field("", max_length=120)
    audience: Literal["kids", "all", "teens"] = "all"
    credit: str = Field("", max_length=300)


@router.post("/library/texts")
def add_text(body: TextIn, conn: Conn):
    try:
        book_id = sources.add_teacher_text(conn, body.title.strip(), body.text, body.author.strip(),
                                           body.audience, body.credit.strip())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"id": book_id}


# ====================================================================== reader

@router.get("/read/{book_id}/{idx}")
def get_reader(book_id: str, idx: int, student: int, conn: Conn):
    student_row(conn, student)
    data = library.reader(conn, student, book_id, idx)
    if data is None:
        raise HTTPException(404, "Unknown text")
    return data


def open_read(conn: sqlite3.Connection, sid: int, book_id: str, idx: int) -> sqlite3.Row:
    """The student's unfinished session for this unit, created on first use."""
    row = conn.execute("SELECT * FROM reads WHERE student_id = ? AND book_id = ? AND idx = ? AND finished = 0 "
                       "ORDER BY id DESC LIMIT 1", (sid, book_id, idx)).fetchone()
    if row is None:
        if library.unit_row(conn, book_id, idx) is None:
            raise HTTPException(404, "Unknown text")
        model = library.student_model(conn, sid)
        ix = library.index(conn)
        cov = ix.units[(book_id, idx)].coverage(model.probs(ix))
        cur = conn.execute("INSERT INTO reads(student_id, book_id, idx, day, coverage) VALUES (?, ?, ?, ?, ?)",
                           (sid, book_id, idx, today().isoformat(), round(cov, 4)))
        row = conn.execute("SELECT * FROM reads WHERE id = ?", (cur.lastrowid,)).fetchone()
    return row


def add_time(conn: sqlite3.Connection, sid: int, read_id: int, seconds: int, words: int = 0) -> None:
    t = today().isoformat()
    conn.execute("UPDATE reads SET seconds = seconds + ?, day = ? WHERE id = ?", (seconds, t, read_id))
    conn.execute("INSERT INTO reading_days(student_id, day, seconds, words) VALUES (?, ?, ?, ?) "
                 "ON CONFLICT(student_id, day) DO UPDATE SET seconds = seconds + excluded.seconds, "
                 "words = words + excluded.words", (sid, t, seconds, words))


class LookupIn(BaseModel):
    student: int
    book: str
    idx: int
    word: str = Field(min_length=1, max_length=80)
    surface: str = Field("", max_length=80)
    sentence: str = Field("", max_length=600)


@router.post("/read/lookup")
def read_lookup(body: LookupIn, conn: Conn):
    """A tap on a word while reading: it counts as a word the student didn't know."""
    student_row(conn, body.student)
    row = open_read(conn, body.student, body.book, body.idx)
    key = word_key(body.word)
    first = conn.execute("SELECT 1 FROM lookups WHERE student_id = ? AND book_id = ? AND idx = ? AND word = ?",
                         (body.student, body.book, body.idx, key)).fetchone() is None
    conn.execute("INSERT INTO lookups(student_id, word, surface, book_id, idx, sentence, day) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (body.student, key, body.surface, body.book, body.idx, body.sentence.strip(), today().isoformat()))
    if first:
        conn.execute("UPDATE reads SET taps = taps + 1 WHERE id = ?", (row["id"],))
    conn.commit()
    return {"ok": True}


class ReadProgressIn(BaseModel):
    student: int
    book: str
    idx: int
    seconds: int = Field(0, ge=0, le=3600)     # reading time since the last report
    position: float = Field(0, ge=0, le=1)


@router.post("/read/progress")
def read_progress(body: ReadProgressIn, conn: Conn):
    student_row(conn, body.student)
    row = open_read(conn, body.student, body.book, body.idx)
    add_time(conn, body.student, row["id"], body.seconds)
    conn.execute("UPDATE reads SET position = ? WHERE id = ?", (body.position, row["id"]))
    if body.seconds:
        db.log_activity(conn, body.student, today(), body.book, "read")
    conn.commit()
    return {"ok": True}


@router.get("/read/{book_id}/{idx}/check")
def read_check(book_id: str, idx: int, student: int, conn: Conn, size: int = Query(6, ge=3, le=10)):
    student_row(conn, student)
    if library.unit_row(conn, book_id, idx) is None:
        raise HTTPException(404, "Unknown text")
    return {"questions": library.masked_check(conn, student, book_id, idx, size)}


@router.get("/read/{book_id}/{idx}/questions")
def read_questions(book_id: str, idx: int, student: int, conn: Conn):
    """Comprehension questions already written for this unit (AI stories come with them)."""
    student_row(conn, student)
    row = conn.execute("SELECT data FROM unit_questions WHERE book_id = ? AND idx = ?", (book_id, idx)).fetchone()
    return {"questions": json.loads(row["data"]) if row else []}


class CheckAnswer(BaseModel):
    word: str = Field(min_length=1, max_length=80)
    correct: bool


class FinishIn(BaseModel):
    student: int
    book: str
    idx: int
    seconds: int = Field(0, ge=0, le=3600)
    rating: Literal["easy", "right", "hard"] | None = None
    answers: list[CheckAnswer] = Field(default_factory=list, max_length=20)
    questions_right: int | None = Field(None, ge=0)
    questions_total: int | None = Field(None, ge=0)


@router.post("/read/finish")
def read_finish(body: FinishIn, conn: Conn):
    s = student_row(conn, body.student)
    t = today()
    row = open_read(conn, body.student, body.book, body.idx)
    unit = library.unit_row(conn, body.book, body.idx)
    seconds = row["seconds"] + body.seconds
    right = sum(a.correct for a in body.answers) + (body.questions_right or 0)
    total = len(body.answers) + (body.questions_total or 0)
    add_time(conn, body.student, row["id"], body.seconds, unit["words"])
    conn.execute("UPDATE reads SET finished = 1, position = 1, rating = ?, check_right = ?, check_total = ?, "
                 "check_data = ? WHERE id = ?",
                 (body.rating, right if total else None, total or None,
                  json.dumps([a.model_dump() for a in body.answers]), row["id"]))
    db.log_activity(conn, body.student, t, body.book, "read")

    # A masked word the student is learning and is due today counts as a review in context.
    reviewed = []
    for a in body.answers:
        key = word_key(a.word)
        p = db.get_progress(conn, body.student, key)
        if p is not None and p["box"] >= 1 and p["due"] and p["due"] <= t.isoformat():
            nb, due = srs.after_answer(p["box"], a.correct, t)
            column = "correct" if a.correct else "wrong"
            db.upsert_progress(conn, body.student, key, box=nb, due=due, **{column: p[column] + 1})
            db.log_activity(conn, body.student, t, key, "quiz", a.correct)
            reviewed.append({"word": key, "correct": a.correct, "box": nb})

    before = float(s["vocab_size"] or vocab.DEFAULT_VOCAB)
    ratio = right / total if total else None
    target = adjust_target(s["target_coverage"], body.rating, ratio)
    conn.execute("UPDATE students SET target_coverage = ? WHERE id = ?", (target, body.student))
    conn.commit()
    after = update_vocab(conn, body.student)
    taps = [r["word"] for r in conn.execute(
        "SELECT DISTINCT word FROM lookups WHERE student_id = ? AND book_id = ? AND idx = ?",
        (body.student, body.book, body.idx))]
    rec = library.recommend(conn, body.student, per_group=3)
    nxt = body.idx + 1 if body.idx + 1 < conn.execute("SELECT units FROM books WHERE id = ?",
                                                       (body.book,)).fetchone()["units"] else None
    return {
        "seconds": seconds, "words": unit["words"],
        "wpm": round(unit["words"] / (seconds / 60)) if seconds >= 30 else None,
        "coverage": row["coverage"], "taps": taps, "check": {"right": right, "total": total},
        "reviewed": reviewed, "target": target,
        "vocab": {"before": round(before), "after": round(after), "cefr": vocab.cefr(after)},
        "next_unit": nxt, "recommend": rec,
    }


# ====================================================================== profile, placement, preferences

def reading_today(conn: sqlite3.Connection, sid: int, t: date) -> dict:
    row = conn.execute("SELECT seconds, words FROM reading_days WHERE student_id = ? AND day = ?",
                       (sid, t.isoformat())).fetchone()
    s = conn.execute("SELECT vocab_size, reading_goal FROM students WHERE id = ?", (sid,)).fetchone()
    placed = conn.execute("SELECT 1 FROM placements WHERE student_id = ?", (sid,)).fetchone() is not None
    v = s["vocab_size"] or vocab.DEFAULT_VOCAB
    return {"minutes": round((row["seconds"] if row else 0) / 60), "words": row["words"] if row else 0,
            "goal": s["reading_goal"], "placed": placed, "vocab": v, "cefr": vocab.cefr(v),
            "start_level": START_LEVEL[vocab.cefr(v)] if placed else None}


@router.get("/reading/profile")
def reading_profile(student: int, conn: Conn):
    s = student_row(conn, student)
    t = today()
    v = s["vocab_size"] or vocab.DEFAULT_VOCAB
    placed = conn.execute("SELECT day, vocab, false_alarm FROM placements WHERE student_id = ? ORDER BY id DESC LIMIT 1",
                          (student,)).fetchone()
    history = [dict(r) for r in conn.execute(
        "SELECT day, vocab, source FROM vocab_history WHERE student_id = ? ORDER BY day", (student,))]
    totals = conn.execute(
        "SELECT COUNT(*) units, COUNT(DISTINCT book_id) books, COALESCE(SUM(check_right), 0) cr, "
        "COALESCE(SUM(check_total), 0) ct FROM reads WHERE student_id = ? AND finished = 1", (student,)).fetchone()
    time_row = conn.execute("SELECT COALESCE(SUM(seconds), 0) s, COALESCE(SUM(words), 0) w FROM reading_days "
                            "WHERE student_id = ?", (student,)).fetchone()
    week = [dict(r) for r in conn.execute(
        "SELECT day, seconds, words FROM reading_days WHERE student_id = ? AND day >= ? ORDER BY day",
        (student, (t - timedelta(days=13)).isoformat()))]
    recent = []
    for r in conn.execute(
            "SELECT r.*, b.title book_title, u.title unit_title, u.words FROM reads r JOIN books b ON b.id = r.book_id "
            "JOIN units u ON u.book_id = r.book_id AND u.idx = r.idx WHERE r.student_id = ? AND r.finished = 1 "
            "ORDER BY r.id DESC LIMIT 12", (student,)):
        recent.append({"book": r["book_id"], "idx": r["idx"], "title": r["book_title"],
                       "unit_title": r["unit_title"] if r["unit_title"] != r["book_title"] else "",
                       "day": r["day"], "rating": r["rating"], "taps": r["taps"], "coverage": r["coverage"],
                       "check": [r["check_right"], r["check_total"]] if r["check_total"] else None,
                       "wpm": round(r["words"] / (r["seconds"] / 60)) if r["seconds"] >= 30 else None})
    return {
        "vocab": v, "cefr": vocab.cefr(v), "target": s["target_coverage"], "age_group": s["age_group"],
        "reading_goal": s["reading_goal"],
        "placement": dict(placed) if placed else None, "history": history,
        "totals": {"units": totals["units"], "books": totals["books"], "minutes": round(time_row["s"] / 60),
                   "words": time_row["w"], "check": round(totals["cr"] / totals["ct"], 2) if totals["ct"] else None,
                   "lookups": conn.execute("SELECT COUNT(DISTINCT word) FROM lookups WHERE student_id = ?",
                                           (student,)).fetchone()[0]},
        "days": week, "recent": recent, "today": reading_today(conn, student, t),
        "bands": [{"cefr": c, "from": f} for f, c in vocab.CEFR_BANDS],
    }


class ReadingPrefs(BaseModel):
    age_group: Literal["kids", "teens", "adults", "all"] | None = None
    target_coverage: float | None = Field(None, ge=library.TARGET_MIN, le=library.TARGET_MAX)
    reading_goal: int | None = Field(None, ge=1, le=240)
    vocab_size: int | None = Field(None, ge=vocab.MIN_VOCAB, le=vocab.MAX_VOCAB)   # set by a teacher


@router.patch("/students/{sid}/reading")
def update_reading_prefs(sid: int, body: ReadingPrefs, conn: Conn):
    student_row(conn, sid)
    for field_name in ("age_group", "target_coverage", "reading_goal"):
        value = getattr(body, field_name)
        if value is not None:
            conn.execute(f"UPDATE students SET {field_name} = ? WHERE id = ?", (value, sid))
    if body.vocab_size is not None:
        save_vocab(conn, sid, body.vocab_size, "teacher")
    conn.commit()
    return reading_profile(sid, conn)


# Where to start in the word steps for each reading level (built-in level ids).
START_LEVEL = {"Pre-A1": "L1", "A1": "L1", "A2": "L2", "B1": "L4", "B2": "L6", "C1": "L7", "C2": "L8"}


@router.get("/placement")
def placement_items():
    return {"items": vocab.placement_items()}


class PlacementAnswer(BaseModel):
    word: str = Field(min_length=1, max_length=40)
    yes: bool


class PlacementIn(BaseModel):
    student: int
    answers: list[PlacementAnswer] = Field(min_length=10, max_length=200)


@router.post("/placement")
def placement_submit(body: PlacementIn, conn: Conn):
    student_row(conn, body.student)
    result = vocab.score_placement([(a.word.lower(), a.yes) for a in body.answers])
    result.pop("evidence")
    if not result["reliable"]:          # too many "yes" answers to made-up words: guessing
        return {**result, "saved": False, "start_level": START_LEVEL[result["cefr"]]}
    conn.execute("INSERT INTO placements(student_id, day, vocab, false_alarm, data) VALUES (?, ?, ?, ?, ?)",
                 (body.student, today().isoformat(), result["vocab"], result["false_alarm"],
                  json.dumps({"answers": [a.model_dump() for a in body.answers], "bands": result["bands"]})))
    save_vocab(conn, body.student, result["vocab"], "placement")
    return {**result, "saved": True, "start_level": START_LEVEL[result["cefr"]]}


# ====================================================================== word contexts

def snippet(text: str, key: str) -> str | None:
    """The first sentence of a text that uses the word or phrase, marked *like this*."""
    a = analyze(text)
    for para, toks in zip(a.paragraphs, a.tokens):
        if " " in key:
            hits = sorted(library.find_phrases(toks, [key]))
        else:
            hits = [i for i, t in enumerate(toks) if t.lemma == key]
        if not hits:
            continue
        s, e = next((s, e) for s, e in sentence_spans(para) if s <= toks[hits[0]].start < e)
        runs: list[list[int]] = []                   # adjacent words ("give up") share one mark
        for i in (h for h in hits if s <= toks[h].start < e):
            if runs and not para[toks[runs[-1][1]].end:toks[i].start].strip():
                runs[-1][1] = i
            else:
                runs.append([i, i])
        out, pos = [], s
        for a, b in runs:
            out += [para[pos:toks[a].start], f"*{para[toks[a].start:toks[b].end]}*"]
            pos = toks[b].end
        out.append(para[pos:e])
        return "".join(out).strip()
    return None


def phrase_pattern(key: str) -> re.Pattern:
    """Quick text filter for a phrasal verb: the verb's stem, then its particles nearby."""
    head, *rest = key.split()
    stem = head[:max(3, len(head) - 2)]
    return re.compile(r"(?i)\b" + re.escape(stem) + r"\w*" + "".join(r"\W+(?:\w+\W+)?" + re.escape(p) + r"\b"
                                                                   for p in rest))


@router.get("/word/contexts")
def word_contexts(q: str, student: int, conn: Conn, limit: int = Query(3, ge=1, le=8)):
    """Where the student met this word, and library texts that use it at a level that fits."""
    student_row(conn, student)
    key = lemma_key(q)
    exact = word_key(q)
    seen = []
    for r in conn.execute(
            "SELECT l.surface, l.sentence, l.day, l.book_id, l.idx, b.title FROM lookups l LEFT JOIN books b "
            "ON b.id = l.book_id WHERE l.student_id = ? AND l.word IN (?, ?) AND l.sentence != '' "
            "ORDER BY l.id DESC LIMIT 5", (student, key, exact)):
        seen.append(dict(r))
    model = library.student_model(conn, student)
    ix = library.index(conn)
    p = model.probs(ix)
    head = key.split()[0] if " " in key else key
    rows = conn.execute(
        "SELECT ul.book_id, ul.idx, b.title, u.title unit_title FROM unit_lemmas ul JOIN books b ON b.id = ul.book_id "
        "JOIN units u ON u.book_id = ul.book_id AND u.idx = ul.idx "
        "WHERE ul.lemma = ? AND (b.owner IS NULL OR b.owner = ?)", (lemma(head) if " " in key else key, student)).fetchall()
    scored = []
    for r in rows:
        v = ix.units.get((r["book_id"], r["idx"]))
        if v:
            cov = v.coverage(p)
            scored.append((abs(cov - model.target) + (0.02 if cov < model.target - 0.04 else 0), cov, r))
    found = []
    pattern = phrase_pattern(key) if " " in key else None
    for _, cov, r in sorted(scored, key=lambda x: x[0])[:PHRASE_SCAN if pattern else limit * 2]:
        if len(found) >= limit:
            break
        u = library.unit_row(conn, r["book_id"], r["idx"])
        if pattern and not pattern.search(u["text"]):
            continue
        text = snippet(u["text"], key)
        if text:
            found.append({"book": r["book_id"], "idx": r["idx"], "title": r["title"],
                          "unit_title": r["unit_title"] if r["unit_title"] != r["title"] else "",
                          "sentence": text, "coverage": round(cov, 4), "fit": library.fit_of(cov, model.target)})
    return {"word": key, "seen": seen, "library": found}


# ====================================================================== AI stories

class AIConfigIn(BaseModel):
    api_key: str | None = Field(None, max_length=300)
    model: str | None = None
    clear_key: bool = False


@router.get("/ai/config")
def ai_config():
    return ai.status()


@router.post("/ai/config")
def ai_config_save(body: AIConfigIn):
    try:
        return ai.save_config(body.api_key, body.model, body.clear_key)
    except ai.AIError as exc:
        raise HTTPException(422, str(exc)) from exc


class StoryIn(BaseModel):
    student: int
    topic: str = Field("", max_length=300)
    length: Literal["short", "medium", "long"] = "medium"
    words: list[str] = Field(default_factory=list, max_length=12)
    grammar: str | None = Field(None, max_length=60)     # a grammar point to use again and again


@router.post("/ai/story")
async def ai_story(body: StoryIn, conn: Conn):
    student_row(conn, body.student)
    point = grammar.get_point(body.grammar) if body.grammar else None
    try:
        return await ai.write_story(conn, body.student, body.topic, body.length, body.words, point)
    except ai.AIError as exc:
        raise HTTPException(503, str(exc)) from exc


class QuestionsIn(BaseModel):
    book: str
    idx: int


@router.post("/ai/questions")
async def ai_questions(body: QuestionsIn, conn: Conn):
    try:
        return {"questions": await ai.questions_for(conn, body.book, body.idx)}
    except ai.AIError as exc:
        raise HTTPException(503, str(exc)) from exc
