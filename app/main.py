"""WordStep: FastAPI backend for the dictionary, step-by-step word lists, spaced review,
daily quizzes and Kokoro TTS. Run with:  uv run uvicorn app.main:app --reload
"""
from __future__ import annotations

import asyncio
import difflib
import random
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, grammar, reading, srs
from .content import curriculum, word_key
from .deps import Conn, student_row
from .dictionary import TIMEOUT, DictionaryUnavailable, fetch_api, lookup, lookup_local
from .quiz import PRETEST_TYPES, REVIEW_TYPES, build_quiz
from .tts import DEFAULT_VOICE, KokoroTTS

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
RECOMMEND_THRESHOLD = 0.8   # a level counts as covered once 80% of it is learning or mastered

tts = KokoroTTS()


def today() -> date:
    return date.today()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    conn = db.connect()
    db.init(conn)
    conn.close()
    yield


app = FastAPI(title="WordStep", lifespan=lifespan)
app.include_router(reading.router)
app.include_router(grammar.router)


# ====================================================================== helpers

def all_levels(conn: sqlite3.Connection) -> list[dict]:
    return curriculum()[0] + db.custom_levels(conn)


def find_level(conn: sqlite3.Connection, level_id: str) -> dict:
    for lv in all_levels(conn):
        if lv["id"] == level_id:
            return lv
    raise HTTPException(404, "Unknown level")


def box_of(progress: dict, word: str) -> int:
    row = progress.get(word)
    return row["box"] if row else 0


def counts(words: list[str], progress: dict) -> dict:
    c = {"total": len(words), "new": 0, "learning": 0, "mastered": 0}
    for w in words:
        c[srs.status(box_of(progress, w))] += 1
    return c


def recommended_level(levels: list[dict], progress: dict) -> dict | None:
    for lv in levels:
        c = counts(lv["words"], progress)
        if c["total"] and (c["learning"] + c["mastered"]) / c["total"] < RECOMMEND_THRESHOLD:
            return lv
    return None


def level_summary(lv: dict, progress: dict, rec_id: str | None) -> dict:
    meta = {k: lv[k] for k in ("id", "order", "title", "band", "kind", "description", "custom")}
    return {**meta, **counts(lv["words"], progress), "recommended": lv["id"] == rec_id}


def progress_payload(row: sqlite3.Row | None) -> dict:
    if row is None:
        return {"status": "new", "box": 0, "due": None, "saved": False, "correct": 0, "wrong": 0}
    return {"status": srs.status(row["box"]), "box": row["box"], "due": row["due"],
            "saved": bool(row["saved"]), "correct": row["correct"], "wrong": row["wrong"]}


def word_card(conn: sqlite3.Connection, key: str, progress: dict) -> dict:
    """Short form of an entry for lists."""
    e = lookup_local(conn, key) or {}
    row = progress.get(key)
    return {"key": key, "word": e.get("word", key), "pos": e.get("pos", ""), "ipa": e.get("ipa", ""),
            "definition": e.get("definition", ""), "level": e.get("level"), **progress_payload(row)}


def suggest(conn: sqlite3.Connection, q: str, limit: int = 8) -> list[str]:
    k = word_key(q)
    if not k:
        return []
    keys = list(curriculum()[1]) + [r["word"] for r in conn.execute("SELECT DISTINCT word FROM custom_words")]
    starts = [w for w in keys if w.startswith(k)]
    inside = [w for w in keys if k in w and not w.startswith(k)]
    close = difflib.get_close_matches(k, keys, n=limit, cutoff=0.75)
    return list(dict.fromkeys(starts + inside + close))[:limit]


def streak(conn: sqlite3.Connection, sid: int, t: date) -> int:
    days = {date.fromisoformat(r[0]) for r in conn.execute(
        "SELECT DISTINCT day FROM activity WHERE student_id = ?", (sid,))}
    d = t if t in days else t - timedelta(days=1)
    n = 0
    while d in days:
        n += 1
        d -= timedelta(days=1)
    return n


# ====================================================================== students

class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class StudentPatch(BaseModel):
    daily_goal: int = Field(ge=1, le=100)


@app.get("/api/students")
def list_students(conn: Conn):
    return [dict(r) for r in conn.execute("SELECT id, name, daily_goal FROM students ORDER BY name")]


@app.post("/api/students")
def create_student(body: StudentIn, conn: Conn):
    """Create a profile, or return the existing one with the same name."""
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Name is empty")
    row = conn.execute("SELECT id, name, daily_goal FROM students WHERE name = ?", (name,)).fetchone()
    if row is None:
        cur = conn.execute("INSERT INTO students(name) VALUES (?)", (name,))
        conn.commit()
        row = conn.execute("SELECT id, name, daily_goal FROM students WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.patch("/api/students/{sid}")
def update_student(sid: int, body: StudentPatch, conn: Conn):
    student_row(conn, sid)
    conn.execute("UPDATE students SET daily_goal = ? WHERE id = ?", (body.daily_goal, sid))
    conn.commit()
    return dict(conn.execute("SELECT id, name, daily_goal FROM students WHERE id = ?", (sid,)).fetchone())


# ====================================================================== dashboard

@app.get("/api/dashboard")
def dashboard(student: int, conn: Conn):
    s = student_row(conn, student)
    t = today()
    progress = db.progress_map(conn, student)
    levels = all_levels(conn)
    rec = recommended_level(levels, progress)

    all_words = list(dict.fromkeys(w for lv in levels for w in lv["words"]))
    activity = conn.execute("SELECT word, kind FROM activity WHERE student_id = ? AND day = ?",
                            (student, t.isoformat())).fetchall()
    introduced = {r["word"] for r in activity if r["kind"] in ("know", "learning")}
    reviewed = {r["word"] for r in activity if r["kind"] == "quiz"}
    due = conn.execute("SELECT COUNT(*) FROM progress WHERE student_id = ? AND box >= 1 AND due <= ?",
                       (student, t.isoformat())).fetchone()[0]

    # Today's new words: continue from the recommended level, keeping words already
    # started today in the list so it stays stable through the day.
    picks: list[str] = []
    if rec is not None:
        for lv in levels[levels.index(rec):]:
            for w in lv["words"]:
                if len(picks) >= s["daily_goal"]:
                    break
                if w not in picks and (box_of(progress, w) == 0 or w in introduced):
                    picks.append(w)
    today_words = [{**word_card(conn, w, progress), "done": w in introduced} for w in picks]

    return {
        "student": {"id": s["id"], "name": s["name"], "daily_goal": s["daily_goal"]},
        "overall": counts(all_words, progress),
        "saved": sum(1 for r in progress.values() if r["saved"]),
        "due": due,
        "streak": streak(conn, student, t),
        "today": {"goal": s["daily_goal"], "done": sum(1 for w in today_words if w["done"]),
                  "reviewed": len(reviewed), "words": today_words},
        "recommended": level_summary(rec, progress, rec["id"]) if rec else None,
        "reading": reading.reading_today(conn, student, t),
        "grammar": grammar.summary(conn, student, t),
    }


# ====================================================================== levels

@app.get("/api/levels")
def get_levels(student: int, conn: Conn):
    student_row(conn, student)
    progress = db.progress_map(conn, student)
    levels = all_levels(conn)
    rec = recommended_level(levels, progress)
    return [level_summary(lv, progress, rec and rec["id"]) for lv in levels]


@app.get("/api/levels/{level_id}")
def get_level(level_id: str, student: int, conn: Conn):
    student_row(conn, student)
    lv = find_level(conn, level_id)
    progress = db.progress_map(conn, student)
    rec = recommended_level(all_levels(conn), progress)
    return {**level_summary(lv, progress, rec and rec["id"]),
            "words": [word_card(conn, w, progress) for w in lv["words"]]}


class ImportIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=200_000)
    description: str = Field("", max_length=300)


def parse_word_list(text: str) -> list[tuple[str, str, str]]:
    """Lines of `word`, or `word | definition | example` (tab also works). Numbering is ignored."""
    rows, seen = [], set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in re.split(r"\t|\|", line)]
        k = word_key(re.sub(r"^\d+\s*[.)]\s*", "", parts[0]))
        if not k or k in seen or len(k) > 60:
            continue
        seen.add(k)
        rows.append((k, parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else ""))
    return rows[:2000]


async def enrich(words: list[str]) -> None:
    """Background task: fetch dictionary entries for imported words that we don't have yet."""
    conn = db.connect()
    sem = asyncio.Semaphore(4)
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async def one(w: str) -> None:
                async with sem:
                    entry, definitive = await fetch_api(w, client)
                if definitive:
                    db.cache_put(conn, w, entry)
            await asyncio.gather(*(one(w) for w in words))
    finally:
        conn.close()


@app.post("/api/levels/import")
def import_level(body: ImportIn, background: BackgroundTasks, conn: Conn):
    rows = parse_word_list(body.text)
    if not rows:
        raise HTTPException(422, "No words found. Put one word per line.")
    level_id = "C" + secrets.token_hex(3)
    conn.execute("INSERT INTO custom_levels(id, title, description) VALUES (?, ?, ?)",
                 (level_id, body.title.strip(), body.description.strip()))
    conn.executemany(
        "INSERT INTO custom_words(level_id, position, word, definition, example) VALUES (?, ?, ?, ?, ?)",
        [(level_id, i, w, d, ex) for i, (w, d, ex) in enumerate(rows)])
    conn.commit()
    builtin = curriculum()[1]
    missing = [w for w, _, _ in rows if w not in builtin and db.cache_get(conn, w) is db.MISSING]
    if missing:
        background.add_task(enrich, missing)
    return {"id": level_id, "title": body.title.strip(), "count": len(rows), "fetching": len(missing)}


@app.delete("/api/levels/{level_id}")
def delete_level(level_id: str, conn: Conn):
    if not find_level(conn, level_id)["custom"]:
        raise HTTPException(400, "Built-in levels can't be deleted")
    conn.execute("DELETE FROM custom_levels WHERE id = ?", (level_id,))
    conn.commit()
    return {"ok": True}


# ====================================================================== words

@app.get("/api/suggest")
def get_suggest(q: str, conn: Conn):
    return suggest(conn, q)


@app.get("/api/word")
async def get_word(q: str, conn: Conn, student: int | None = None):
    key = word_key(q)
    try:
        entry = await lookup(conn, key)
    except DictionaryUnavailable:
        raise HTTPException(503, {"message": "The online dictionary didn't respond. Please try again in a moment.",
                                  "suggestions": suggest(conn, q)}) from None
    if entry is None:
        raise HTTPException(404, {"message": f"No entry found for “{q.strip()}”.",
                                  "suggestions": suggest(conn, q)})
    row = db.get_progress(conn, student, key) if student else None
    return {"key": key, "entry": entry, "progress": progress_payload(row)}


class ProgressIn(BaseModel):
    student: int
    word: str = Field(min_length=1, max_length=80)
    action: Literal["know", "learning", "save", "unsave", "reset"]


@app.post("/api/progress")
def set_progress(body: ProgressIn, conn: Conn):
    student_row(conn, body.student)
    key, t = word_key(body.word), today()
    row = db.get_progress(conn, body.student, key)
    box = row["box"] if row else 0

    if body.action == "know":
        nb, due = srs.mark_known(t)
        db.upsert_progress(conn, body.student, key, box=nb, due=due)
        db.log_activity(conn, body.student, t, key, "know")
    elif body.action == "learning":
        nb, due = srs.mark_learning(box, t)
        db.upsert_progress(conn, body.student, key, box=nb, due=due, saved=1)
        db.log_activity(conn, body.student, t, key, "learning")
    elif body.action == "save":
        fields: dict = {"saved": 1}
        if box == 0:  # saving a new word puts it into review
            fields["box"], fields["due"] = srs.mark_learning(0, t)
        db.upsert_progress(conn, body.student, key, **fields)
    elif body.action == "unsave":
        db.upsert_progress(conn, body.student, key, saved=0)
    elif body.action == "reset":
        conn.execute("DELETE FROM progress WHERE student_id = ? AND word = ?", (body.student, key))
    conn.commit()
    return progress_payload(db.get_progress(conn, body.student, key))


@app.get("/api/mywords")
def my_words(student: int, conn: Conn):
    student_row(conn, student)
    progress = db.progress_map(conn, student)
    keys = sorted((k for k, r in progress.items() if r["saved"] or r["box"] > 0),
                  key=lambda k: (progress[k]["due"] or "9999", k))
    return [word_card(conn, k, progress) for k in keys]


# ====================================================================== quiz

def quiz_pool(conn: sqlite3.Connection, words: list[str], levels: list[dict]) -> list[dict]:
    """Distractor pool: entries from the same levels as the quiz words, or all built-in words."""
    level_ids = set()
    for lv in levels:
        if any(w in lv["words"] for w in words):
            level_ids.add(lv["id"])
    keys = {w for lv in levels if lv["id"] in level_ids for w in lv["words"]}
    pool = [e for e in (lookup_local(conn, k) for k in keys) if e and e.get("definition")]
    return pool if len(pool) >= 8 else list(curriculum()[1].values())


@app.get("/api/quiz")
async def get_quiz(student: int, conn: Conn, mode: Literal["review", "pretest"] = "review",
                   level: str | None = None, size: int = Query(10, ge=3, le=30)):
    student_row(conn, student)
    t, rng = today(), random.Random()
    progress = db.progress_map(conn, student)
    levels = all_levels(conn)
    lv = None
    if mode == "review":
        rows = conn.execute(
            "SELECT word FROM progress WHERE student_id = ? AND box >= 1 AND due <= ? "
            "ORDER BY due, box LIMIT ?", (student, t.isoformat(), size)).fetchall()
        words = [r["word"] for r in rows]
        rng.shuffle(words)
    else:
        lv = find_level(conn, level) if level else (recommended_level(levels, progress) or levels[-1])
        fresh = [w for w in lv["words"] if box_of(progress, w) == 0]
        words = rng.sample(fresh, min(size, len(fresh)))

    entries = []
    for w in words:
        try:
            e = await lookup(conn, w)
        except DictionaryUnavailable:
            continue
        if e and e.get("definition"):
            entries.append({**e, "word": e["word"] if word_key(e["word"]) == w else w})
    questions = build_quiz(entries, quiz_pool(conn, words, levels),
                           REVIEW_TYPES if mode == "review" else PRETEST_TYPES, rng)
    return {"mode": mode, "level": level_summary(lv, progress, None) if lv else None,
            "questions": questions}


class AnswerIn(BaseModel):
    student: int
    word: str = Field(min_length=1, max_length=80)
    correct: bool
    mode: Literal["review", "pretest"] = "review"


@app.post("/api/quiz/answer")
def quiz_answer(body: AnswerIn, conn: Conn):
    student_row(conn, body.student)
    key, t = word_key(body.word), today()
    row = db.get_progress(conn, body.student, key)
    box = row["box"] if row else 0

    if body.mode == "pretest":
        if body.correct:
            nb, due = srs.mark_known(t)
            fields = {"box": nb, "due": due}
        else:  # a word the student needs: save it and review it tomorrow
            fields = {"box": 1, "due": t + timedelta(days=1), "saved": 1}
    else:
        nb, due = srs.after_answer(box, body.correct, t)
        fields = {"box": nb, "due": due}
    column = "correct" if body.correct else "wrong"
    fields[column] = (row[column] if row else 0) + 1
    db.upsert_progress(conn, body.student, key, **fields)
    db.log_activity(conn, body.student, t, key, "quiz", body.correct)
    conn.commit()
    return progress_payload(db.get_progress(conn, body.student, key))


# ====================================================================== TTS

@app.get("/api/tts/status")
def tts_status():
    return tts.status()


@app.get("/api/tts")
def speak(text: str = Query(min_length=1, max_length=600), voice: str = DEFAULT_VOICE,
          speed: float = Query(1.0, ge=0.5, le=1.5)):
    try:
        path = tts.synthesize(text, voice, speed)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # model missing or failed: the browser falls back to Web Speech
        raise HTTPException(503, f"TTS unavailable: {exc}") from exc
    return FileResponse(path, media_type="audio/wav",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


# ====================================================================== static

app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
