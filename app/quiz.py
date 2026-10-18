"""Quiz question generation.

Question types
    meaning   read the definition, choose the word
    word      see/hear the word, choose the definition
    cloze     an example sentence with a blank, choose the word
    spell     hear the word (Kokoro), read the definition, type the word
"""
from __future__ import annotations

import random
import re

from .content import word_key

REVIEW_TYPES = ("meaning", "word", "cloze", "spell")
PRETEST_TYPES = ("meaning", "word", "cloze")
BLANK = "_____"


def pos_group(entry: dict) -> str:
    pos = (entry.get("pos") or "").lower()
    if "phrasal" in pos:
        return "phrasal"
    return pos.split(",")[0].strip() or "other"


def cloze(entry: dict) -> tuple[str, str] | None:
    """Return (sentence with blank, removed text) from the first single-target example."""
    for ex in entry.get("examples", []):
        parts = re.findall(r"\*([^*]+)\*", ex)
        if len(parts) == 1:
            return re.sub(r"\*[^*]+\*", BLANK, ex, count=1), parts[0]
    return None


def first_example(entry: dict) -> str:
    return (entry.get("examples") or [""])[0]


def distractors(entry: dict, pool: list[dict], n: int, field: str, rng: random.Random) -> list[str]:
    """Up to n distinct values of `field` from other entries, same part of speech first."""
    target = word_key(entry["word"])
    others = [e for e in pool if word_key(e["word"]) != target and e.get("definition")]
    same = [e for e in others if pos_group(e) == pos_group(entry)]
    rest = [e for e in others if pos_group(e) != pos_group(entry)]
    rng.shuffle(same)
    rng.shuffle(rest)
    seen = {entry[field].lower()}
    out: list[str] = []
    for e in same + rest:
        v = e[field]
        if v.lower() in seen:
            continue
        seen.add(v.lower())
        out.append(v)
        if len(out) == n:
            break
    return out


def _choices(correct: str, wrong: list[str], rng: random.Random) -> tuple[list[str], int]:
    options = wrong + [correct]
    rng.shuffle(options)
    return options, options.index(correct)


def make_question(entry: dict, pool: list[dict], qtype: str, rng: random.Random) -> dict | None:
    word = entry["word"]
    base = {
        "word": word_key(word),
        "type": qtype,
        "feedback": {
            "word": word, "ipa": entry.get("ipa", ""), "pos": entry.get("pos", ""),
            "definition": entry.get("definition", ""), "example": first_example(entry),
        },
    }
    if qtype == "meaning":
        wrong = distractors(entry, pool, 3, "word", rng)
        if len(wrong) < 3:
            return None
        options, answer = _choices(word, wrong, rng)
        return {**base, "prompt": entry["definition"], "options": options, "answer": answer}
    if qtype == "word":
        wrong = distractors(entry, pool, 3, "definition", rng)
        if len(wrong) < 3:
            return None
        options, answer = _choices(entry["definition"], wrong, rng)
        return {**base, "prompt": word, "speak": word, "options": options, "answer": answer}
    if qtype == "cloze":
        c = cloze(entry)
        wrong = distractors(entry, pool, 3, "word", rng)
        if not c or len(wrong) < 3:
            return None
        options, answer = _choices(word, wrong, rng)
        sentence, removed = c
        return {**base, "prompt": sentence, "removed": removed, "options": options, "answer": answer}
    if qtype == "spell":
        return {**base, "prompt": entry["definition"], "speak": word, "answer_text": word}
    raise ValueError(qtype)


def build_quiz(entries: list[dict], pool: list[dict], types: tuple[str, ...],
               rng: random.Random | None = None) -> list[dict]:
    """One question per entry, rotating through `types` and falling back when one can't be built."""
    rng = rng or random.Random()
    rotation = list(types)
    rng.shuffle(rotation)
    questions = []
    for i, entry in enumerate(e for e in entries if e.get("definition")):
        preferred = rotation[i % len(rotation)]
        for qtype in (preferred, "meaning", "word", "spell"):
            if qtype not in types:
                continue
            q = make_question(entry, pool, qtype, rng)
            if q:
                questions.append({"id": len(questions), **q})
                break
    return questions


def check_spelling(given: str, expected: str) -> bool:
    norm = lambda s: re.sub(r"\s+", " ", s.strip().lower())  # noqa: E731
    return norm(given) == norm(expected)
