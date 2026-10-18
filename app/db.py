"""SQLite storage for students, study progress, imported word lists and API lookups."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("WORDSTEP_DB", ROOT / "userdata" / "wordstep.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS students(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    daily_goal  INTEGER NOT NULL DEFAULT 10,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS progress(
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    word        TEXT NOT NULL,
    box         INTEGER NOT NULL DEFAULT 0,
    due         TEXT,
    saved       INTEGER NOT NULL DEFAULT 0,
    correct     INTEGER NOT NULL DEFAULT 0,
    wrong       INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(student_id, word)
);
CREATE TABLE IF NOT EXISTS activity(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    day         TEXT NOT NULL,
    word        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    correct     INTEGER
);
CREATE INDEX IF NOT EXISTS activity_student_day ON activity(student_id, day);
CREATE TABLE IF NOT EXISTS custom_levels(
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS custom_words(
    level_id    TEXT NOT NULL REFERENCES custom_levels(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    word        TEXT NOT NULL,
    definition  TEXT NOT NULL DEFAULT '',
    example     TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(level_id, word)
);
CREATE TABLE IF NOT EXISTS entry_cache(
    word        TEXT PRIMARY KEY,
    data        TEXT,
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- reading library: a book is split into units (a whole story, or one chapter)
CREATE TABLE IF NOT EXISTS books(
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,              -- storybook | gutenberg | teacher | ai
    title       TEXT NOT NULL,
    author      TEXT NOT NULL DEFAULT '',
    audience    TEXT NOT NULL DEFAULT 'all', -- kids | all | teens
    credit      TEXT NOT NULL DEFAULT '',
    license     TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    owner       INTEGER REFERENCES students(id) ON DELETE CASCADE,  -- AI stories belong to one student
    words       INTEGER NOT NULL DEFAULT 0,
    units       INTEGER NOT NULL DEFAULT 0,
    sentence_len REAL NOT NULL DEFAULT 0,
    meta        TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS units(
    book_id     TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    text        TEXT NOT NULL,
    words       INTEGER NOT NULL,
    free_tokens INTEGER NOT NULL DEFAULT 0,  -- names and sound words (count as known)
    sentence_len REAL NOT NULL DEFAULT 0,
    PRIMARY KEY(book_id, idx)
);
CREATE TABLE IF NOT EXISTS unit_lemmas(
    book_id     TEXT NOT NULL,
    idx         INTEGER NOT NULL,
    lemma       TEXT NOT NULL,
    n           INTEGER NOT NULL,
    PRIMARY KEY(book_id, idx, lemma),
    FOREIGN KEY(book_id, idx) REFERENCES units(book_id, idx) ON DELETE CASCADE
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS unit_lemmas_lemma ON unit_lemmas(lemma);
CREATE TABLE IF NOT EXISTS unit_questions(
    book_id     TEXT NOT NULL,
    idx         INTEGER NOT NULL,
    data        TEXT NOT NULL,
    PRIMARY KEY(book_id, idx),
    FOREIGN KEY(book_id, idx) REFERENCES units(book_id, idx) ON DELETE CASCADE
);

-- reading activity
CREATE TABLE IF NOT EXISTS reads(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    book_id     TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL,
    day         TEXT NOT NULL,
    seconds     INTEGER NOT NULL DEFAULT 0,
    position    REAL NOT NULL DEFAULT 0,
    finished    INTEGER NOT NULL DEFAULT 0,
    coverage    REAL,                       -- predicted share of known words when started
    taps        INTEGER NOT NULL DEFAULT 0,
    rating      TEXT,                       -- easy | right | hard
    check_right INTEGER,
    check_total INTEGER,
    check_data  TEXT
);
CREATE INDEX IF NOT EXISTS reads_student ON reads(student_id, finished);
CREATE TABLE IF NOT EXISTS reading_days(
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    day         TEXT NOT NULL,
    seconds     INTEGER NOT NULL DEFAULT 0,
    words       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(student_id, day)
);
CREATE TABLE IF NOT EXISTS lookups(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    word        TEXT NOT NULL,
    surface     TEXT NOT NULL DEFAULT '',
    book_id     TEXT,
    idx         INTEGER,
    sentence    TEXT NOT NULL DEFAULT '',
    day         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lookups_student_word ON lookups(student_id, word);
CREATE TABLE IF NOT EXISTS placements(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    day         TEXT NOT NULL,
    vocab       INTEGER NOT NULL,
    false_alarm REAL NOT NULL,
    data        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vocab_history(
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    day         TEXT NOT NULL,
    vocab       INTEGER NOT NULL,
    source      TEXT NOT NULL,
    PRIMARY KEY(student_id, day)
);

-- grammar: one row per point a student has practised (same Leitner boxes as words)
CREATE TABLE IF NOT EXISTS grammar_progress(
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    point       TEXT NOT NULL,
    box         INTEGER NOT NULL DEFAULT 0,
    due         TEXT,
    sessions    INTEGER NOT NULL DEFAULT 0,
    correct     INTEGER NOT NULL DEFAULT 0,
    wrong       INTEGER NOT NULL DEFAULT 0,
    last_score  REAL,
    missed      TEXT NOT NULL DEFAULT '[]',   -- question ids answered wrong last time, asked first in review
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(student_id, point)
);
CREATE TABLE IF NOT EXISTS grammar_writing(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    point       TEXT NOT NULL,
    day         TEXT NOT NULL,
    text        TEXT NOT NULL,
    corrected   TEXT NOT NULL DEFAULT '',
    feedback    TEXT NOT NULL DEFAULT '',
    ok          INTEGER                       -- Claude: correct and uses the point (NULL: not checked)
);
CREATE INDEX IF NOT EXISTS grammar_writing_student ON grammar_writing(student_id, point);
"""

# Columns added to existing tables after the first release: (table, column, definition).
MIGRATIONS = [
    ("students", "age_group", "TEXT NOT NULL DEFAULT 'all'"),       # kids | teens | adults | all
    ("students", "vocab_size", "INTEGER"),                          # estimated, see vocab.py
    ("students", "target_coverage", "REAL NOT NULL DEFAULT 0.98"),  # share of known words that feels right
    ("students", "reading_goal", "INTEGER NOT NULL DEFAULT 10"),    # minutes per day
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists()
    # FastAPI opens the connection in a worker thread and may use it on the event loop.
    conn = sqlite3.connect(path, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if fresh:
        init(conn)
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode = WAL")   # library imports write while pages read
    conn.executescript(SCHEMA)
    for table, column, definition in MIGRATIONS:
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    conn.commit()


# ---------------------------------------------------------------- progress

def progress_map(conn: sqlite3.Connection, student_id: int) -> dict[str, sqlite3.Row]:
    rows = conn.execute("SELECT * FROM progress WHERE student_id = ?", (student_id,))
    return {r["word"]: r for r in rows}


def get_progress(conn: sqlite3.Connection, student_id: int, word: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM progress WHERE student_id = ? AND word = ?", (student_id, word)
    ).fetchone()


def upsert_progress(conn: sqlite3.Connection, student_id: int, word: str, **fields) -> None:
    fields = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in fields.items()}
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    updates = ", ".join(f"{k} = excluded.{k}" for k in fields)
    conn.execute(
        f"INSERT INTO progress(student_id, word, {cols}) VALUES (?, ?, {marks}) "
        f"ON CONFLICT(student_id, word) DO UPDATE SET {updates}, updated_at = datetime('now')",
        (student_id, word, *fields.values()),
    )


def log_activity(conn: sqlite3.Connection, student_id: int, day: date, word: str,
                 kind: str, correct: bool | None = None) -> None:
    conn.execute(
        "INSERT INTO activity(student_id, day, word, kind, correct) VALUES (?, ?, ?, ?, ?)",
        (student_id, day.isoformat(), word, kind, None if correct is None else int(correct)),
    )


# ---------------------------------------------------------------- imported lists

def custom_levels(conn: sqlite3.Connection) -> list[dict]:
    levels = []
    rows = conn.execute("SELECT * FROM custom_levels ORDER BY created_at, id").fetchall()
    for i, r in enumerate(rows):
        words = [w["word"] for w in conn.execute(
            "SELECT word FROM custom_words WHERE level_id = ? ORDER BY position", (r["id"],))]
        levels.append({
            "id": r["id"], "order": 100 + i, "title": r["title"], "band": "Imported",
            "kind": "imported", "description": r["description"], "words": words, "custom": True,
        })
    return levels


def custom_word(conn: sqlite3.Connection, word: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM custom_words WHERE word = ? ORDER BY definition = '' LIMIT 1", (word,)
    ).fetchone()


# ---------------------------------------------------------------- API cache

MISSING = object()


def cache_get(conn: sqlite3.Connection, word: str):
    """Return the cached entry, None for a cached "not found", or MISSING if never fetched.

    "Not found" results expire after a week so a word can be retried later.
    """
    row = conn.execute(
        "SELECT data, fetched_at >= datetime('now', '-7 days') AS fresh FROM entry_cache WHERE word = ?",
        (word,)).fetchone()
    if row is None or (row["data"] is None and not row["fresh"]):
        return MISSING
    return json.loads(row["data"]) if row["data"] else None


def cache_put(conn: sqlite3.Connection, word: str, entry: dict | None) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO entry_cache(word, data) VALUES (?, ?)",
        (word, json.dumps(entry, ensure_ascii=False) if entry else None),
    )
    conn.commit()
