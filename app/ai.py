"""AI-written graded readers and comprehension questions (optional; uses the Claude API).

A story is written for one student: almost every word comes from what they know, and the
few new words are the ones they are studying in WordStep. After writing, the app measures
the story against the student's own vocabulary model; if too many words are probably
unknown, Claude rewrites it once, replacing exactly those words.

The API key is read from Settings (saved in userdata/ai.json) or from the usual Anthropic
credentials (ANTHROPIC_API_KEY, or an `ant auth login` profile).
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
from pathlib import Path

import anthropic

from . import library, vocab
from .content import word_key
from .textproc import analyze, is_dictionary_word

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "userdata" / "ai.json"
MODELS = {
    "claude-opus-5-5": "Claude Opus 5.5 — best writing (about 5–10 US cents per story)",
    "claude-sonnet-5-5": "Claude Sonnet 5.5 — good and cheaper (about 2–5 cents)",
    "claude-haiku-5-5": "Claude Haiku 5.5 — cheapest (well under 1 cent)",
}
DEFAULT_MODEL = "claude-opus-5-5"
NO_FALLBACK = {"claude-haiku-5-5"}      # models without server-side refusal fallback
LENGTHS = {"short": 150, "medium": 300, "long": 500}
QUESTION_COUNT = 4


class AIError(Exception):
    """A problem the student or teacher should see as a message."""


# ====================================================================== settings

def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(api_key: str | None = None, model: str | None = None, clear_key: bool = False) -> dict:
    cfg = load_config()
    if clear_key:
        cfg.pop("api_key", None)
    elif api_key:
        cfg["api_key"] = api_key.strip()
    if model:
        if model not in MODELS:
            raise AIError("Unknown model")
        cfg["model"] = model
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg), encoding="utf-8")
    return status()


def status() -> dict:
    cfg = load_config()
    key = cfg.get("api_key")
    env = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    return {
        "configured": bool(key or env),
        "key_source": "settings" if key else "environment" if env else None,
        "key_hint": f"…{key[-4:]}" if key else None,
        "model": cfg.get("model", DEFAULT_MODEL),
        "models": MODELS,
    }


def make_client() -> anthropic.AsyncAnthropic:
    key = load_config().get("api_key")
    return anthropic.AsyncAnthropic(api_key=key) if key else anthropic.AsyncAnthropic()


# ====================================================================== calling Claude

QUESTION_ITEM = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "answer": {"type": "integer", "description": "index of the correct option, 0-3"},
        "explanation": {"type": "string"},
    },
    "required": ["question", "options", "answer", "explanation"],
    "additionalProperties": False,
}
STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "paragraphs": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": QUESTION_ITEM},
    },
    "required": ["title", "paragraphs", "questions"],
    "additionalProperties": False,
}
QUESTIONS_SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": QUESTION_ITEM}},
    "required": ["questions"],
    "additionalProperties": False,
}

STORY_SYSTEM = """You write graded readers: short, original, engaging stories for people learning English.
A learner enjoys reading when about 98 of every 100 running words are words they already know, so you
write with a deliberately limited vocabulary:
- Use common, everyday English words. Use a rarer word only when it is one of the target words.
- Match sentence length and grammar to the reader's level: short sentences and simple tenses at A1-A2,
  more variety at B1-B2, natural literary style at C1-C2.
- Use every target word at least twice, in contexts that make its meaning easy to guess.
- Keep names short and easy to say. Give the story a clear beginning, middle and end.
- Suit the content to the reader's age group. No violence, romance or frightening content for children.
Then write comprehension questions about the story: four options each, exactly one correct, testing
understanding of what happened and why, not memory of single words. "answer" is the index (0-3) of the
correct option. Write paragraphs as plain text without markdown."""

QUESTIONS_SYSTEM = """You write comprehension questions for people learning English. Each question has four
options with exactly one correct answer, uses simple language (simpler than the text itself), and tests
understanding of events, reasons and meaning rather than memory of single words. "answer" is the index
(0-3) of the correct option; "explanation" says briefly why, in simple English."""


async def ask(system: str, prompt: str, schema: dict) -> dict:
    """One structured request. Returns the parsed JSON object."""
    model = load_config().get("model", DEFAULT_MODEL)
    extra = {} if model in NO_FALLBACK else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        response = await make_client().beta.messages.create(
            model=model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
            **extra,
        )
    except anthropic.AuthenticationError:
        raise AIError("The Claude API key was not accepted. Check it in Settings.") from None
    except anthropic.PermissionDeniedError:
        raise AIError("This API key is not allowed to use that model.") from None
    except anthropic.RateLimitError:
        raise AIError("Too many requests right now. Please try again in a minute.") from None
    except anthropic.APIConnectionError:
        raise AIError("Could not reach the Claude API. Check the internet connection.") from None
    except anthropic.APIStatusError as exc:
        raise AIError(f"The Claude API returned an error ({exc.status_code}). Please try again.") from None
    except anthropic.AnthropicError as exc:   # e.g. no credentials configured
        raise AIError(f"The Claude API is not set up: {exc}") from None
    if response.stop_reason == "refusal":
        raise AIError("Claude declined to write this. Try a different topic.")
    if response.stop_reason == "max_tokens":
        raise AIError("The answer was cut off. Try a shorter length.")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except ValueError:
        raise AIError("Claude's answer could not be read. Please try again.") from None


def clean_questions(items: list[dict]) -> list[dict]:
    out = []
    for q in items:
        opts = [str(o).strip() for o in q.get("options", [])]
        ans = q.get("answer")
        if len(opts) == 4 and len(set(opts)) == 4 and isinstance(ans, int) and 0 <= ans < 4 and q.get("question"):
            out.append({"question": q["question"].strip(), "options": opts, "answer": ans,
                        "explanation": str(q.get("explanation", "")).strip()})
    return out


# ====================================================================== stories

def hard_words(text: str, model: library.StudentModel, allowed: set[str]) -> tuple[float, list[str]]:
    """Predicted coverage of a text for this student, and the probably-unknown words in it."""
    a = analyze(text)
    if not a.words:
        return 1.0, []
    known = a.free_tokens + sum(n * (1.0 if lm in allowed else model.p(lm)) for lm, n in a.counts.items())
    unknown = sorted({lm for lm in a.counts if lm not in allowed and model.p(lm) < 0.5 and is_dictionary_word(lm)},
                     key=lambda lm: -a.counts[lm])
    return known / a.words, unknown


def level_brief(model: library.StudentModel, age: str) -> str:
    level = vocab.cefr(model.vocab)
    common = int(model.vocab * 0.5) // 100 * 100 or 100
    ages = {"kids": "a child (about 6-12)", "teens": "a teenager", "adults": "an adult"}.get(age, "any age")
    return (f"Reader: CEFR level {level}, knows roughly the {common} most common English words well; "
            f"age group: {ages}.")


async def write_story(conn: sqlite3.Connection, sid: int, topic: str, length: str,
                      words: list[str], grammar: dict | None = None) -> dict:
    """`grammar` is a grammar point (grammar.py): the story then uses it again and again."""
    model = library.student_model(conn, sid)
    student = conn.execute("SELECT name FROM students WHERE id = ?", (sid,)).fetchone()
    targets = [word_key(w) for w in words if word_key(w)][:12]
    learning = sorted(model.learning - set(targets))[:20]
    n_words = LENGTHS.get(length, LENGTHS["medium"])
    prompt = "\n".join([
        level_brief(model, model.age),
        f"Length: about {n_words} words.",
        f"Topic or idea: {topic.strip() or 'your choice — something fun and surprising'}",
        f"Target words to use (each at least twice): {', '.join(targets) if targets else '(none)'}",
        f"Words the reader is learning (use some if they fit naturally): {', '.join(learning) if learning else '(none)'}",
        f"Write {QUESTION_COUNT} comprehension questions.",
    ])
    if grammar:
        prompt += "\n" + (f"Grammar focus: {grammar['grammar']} ({grammar['title'].lower()}). {grammar['use']} "
                          "Use it naturally and often (at least 6 times), so the reader meets it again and again.")
    story = await ask(STORY_SYSTEM, prompt, STORY_SCHEMA)
    allowed = set(targets) | set(learning)
    text = "\n\n".join(p.strip() for p in story.get("paragraphs", []) if p.strip())
    coverage, unknown = hard_words(text, model, allowed)
    revised = False
    if unknown and coverage < model.target - 0.01:
        rewrite = await ask(STORY_SYSTEM, "\n".join([
            level_brief(model, model.age),
            "Rewrite this story so it is easier. These words are probably new for this reader; replace each "
            f"with a more common word or phrase: {', '.join(unknown[:25])}.",
            f"Keep these target words: {', '.join(targets) if targets else '(none)'}. Keep the plot, the length "
            f"and the title, and update the {QUESTION_COUNT} questions to match.",
            *([f"Keep using {grammar['grammar']} often: it is the grammar focus of this story."] if grammar else []),
            "Story (JSON):", json.dumps(story, ensure_ascii=False),
        ]), STORY_SCHEMA)
        new_text = "\n\n".join(p.strip() for p in rewrite.get("paragraphs", []) if p.strip())
        new_cov, new_unknown = hard_words(new_text, model, allowed)
        if new_text and new_cov > coverage:
            story, text, coverage, unknown, revised = rewrite, new_text, new_cov, new_unknown, True
    if not text:
        raise AIError("Claude returned an empty story. Please try again.")
    title = story.get("title", "").strip() or "A New Story"
    used_model = load_config().get("model", DEFAULT_MODEL)
    book_id = library.save_book(conn, {
        "id": "ai-" + secrets.token_hex(4), "source": "ai", "title": title, "author": "WordStep AI",
        "audience": "kids" if model.age == "kids" else "all", "owner": sid,
        "credit": f"Written by {MODELS.get(used_model, used_model).split(' —')[0]} for {student['name']}",
        "meta": {"target_words": targets, "topic": topic, "model": used_model, "revised": revised,
                 "grammar": grammar["id"] if grammar else None},
    }, [(title, text)])
    questions = clean_questions(story.get("questions", []))
    if questions:
        conn.execute("INSERT OR REPLACE INTO unit_questions(book_id, idx, data) VALUES (?, 0, ?)",
                     (book_id, json.dumps(questions)))
        conn.commit()
    return {"id": book_id, "title": title, "coverage": round(coverage, 4), "revised": revised,
            "unknown": unknown[:10]}


async def questions_for(conn: sqlite3.Connection, book_id: str, idx: int) -> list[dict]:
    """Comprehension questions for any unit, written once and then kept."""
    row = conn.execute("SELECT data FROM unit_questions WHERE book_id = ? AND idx = ?", (book_id, idx)).fetchone()
    if row:
        return json.loads(row["data"])
    u = library.unit_row(conn, book_id, idx)
    if u is None:
        raise AIError("Unknown text")
    result = await ask(QUESTIONS_SYSTEM,
                       f"Write {QUESTION_COUNT} questions about this text.\n\nTitle: {u['title']}\n\n{u['text']}",
                       QUESTIONS_SCHEMA)
    questions = clean_questions(result.get("questions", []))
    if not questions:
        raise AIError("No usable questions came back. Please try again.")
    conn.execute("INSERT OR REPLACE INTO unit_questions(book_id, idx, data) VALUES (?, ?, ?)",
                 (book_id, idx, json.dumps(questions)))
    conn.commit()
    return questions
