"""Word lookup chain: built-in curriculum -> imported list -> cached API result -> dictionaryapi.dev."""
from __future__ import annotations

import re
import sqlite3
from urllib.parse import quote

import httpx

from . import db
from .content import curriculum, word_key

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"
TIMEOUT = 6.0


def mark_target(sentence: str, word: str) -> str:
    """Wrap the first occurrence of `word` (allowing inflections) in *asterisks*."""
    if "*" in sentence:
        return sentence
    head, *rest = word.split()
    pattern = r"\b" + re.escape(head) + r"\w*" + "".join(r"\s+" + re.escape(t) for t in rest) + r"\b"
    return re.sub(pattern, lambda m: f"*{m.group(0)}*", sentence, count=1, flags=re.IGNORECASE)


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        k = it.lower()
        if it and k not in seen:
            seen.add(k)
            out.append(it)
    return out


def normalize_api(word: str, payload) -> dict | None:
    """Turn a dictionaryapi.dev response into our entry shape."""
    if not isinstance(payload, list) or not payload:
        return None
    ipa, senses, examples, synonyms = "", [], [], []
    for item in payload:
        if not ipa:
            ipa = item.get("phonetic") or next(
                (p["text"] for p in item.get("phonetics", []) if p.get("text")), "")
        for meaning in item.get("meanings", []):
            pos = meaning.get("partOfSpeech", "")
            for d in meaning.get("definitions", []):
                if d.get("definition") and len(senses) < 4:
                    senses.append({"pos": pos, "definition": d["definition"]})
                if d.get("example") and len(examples) < 3:
                    examples.append(mark_target(d["example"], word))
                synonyms += d.get("synonyms", [])
            synonyms += meaning.get("synonyms", [])
    if not senses:
        return None
    if ipa and not ipa.startswith(("/", "[")):
        ipa = f"/{ipa}/"
    return {
        "word": payload[0].get("word", word),
        "pos": senses[0]["pos"],
        "ipa": ipa,
        "definition": senses[0]["definition"],
        "senses": senses,
        "examples": examples,
        "synonyms": _dedupe(synonyms)[:6],
        "note": "",
        "level": None,
        "source": "dictionaryapi.dev",
    }


class DictionaryUnavailable(Exception):
    """The online dictionary could not be reached (as opposed to: the word doesn't exist)."""


async def fetch_api(word: str, client: httpx.AsyncClient | None = None,
                    attempts: int = 2) -> tuple[dict | None, bool]:
    """Return (entry, definitive). `definitive` is False on network errors, so they aren't cached.

    dictionaryapi.dev answers a real miss with a JSON 404 ("No Definitions Found"); it also
    sometimes returns an HTML 404 page or times out, which is only a transient failure.
    """
    own = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT)
    try:
        for _ in range(attempts):
            try:
                r = await client.get(API_URL.format(quote(word)))
            except httpx.HTTPError:
                continue
            is_json = r.headers.get("content-type", "").startswith("application/json")
            if r.status_code == 200 and is_json:
                return normalize_api(word, r.json()), True
            if r.status_code == 404 and is_json:
                return None, True
        return None, False
    finally:
        if own:
            await client.aclose()


def _merge_imported(base: dict | None, row: sqlite3.Row) -> dict:
    entry = dict(base) if base else {
        "word": row["word"], "pos": "", "ipa": "", "definition": "", "senses": [],
        "examples": [], "synonyms": [], "note": "",
    }
    if row["definition"]:
        entry["definition"] = row["definition"]
    if row["example"]:
        entry["examples"] = [mark_target(row["example"], row["word"])] + entry.get("examples", [])
    entry["level"] = row["level_id"]
    entry["source"] = "imported" if not base else f"imported + {base.get('source')}"
    return entry


def lookup_local(conn: sqlite3.Connection, word: str) -> dict | None:
    """Lookup without any network call (built-in, imported, cached)."""
    k = word_key(word)
    builtin = curriculum()[1]
    if k in builtin:
        return builtin[k]
    cached = db.cache_get(conn, k)
    cached = None if cached is db.MISSING else cached
    imported = db.custom_word(conn, k)
    if imported:
        return _merge_imported(cached, imported)
    return cached


async def lookup(conn: sqlite3.Connection, word: str) -> dict | None:
    k = word_key(word)
    if not k:
        return None
    builtin = curriculum()[1]
    if k in builtin:
        return builtin[k]
    imported = db.custom_word(conn, k)
    cached = db.cache_get(conn, k)
    if cached is db.MISSING:
        cached, definitive = await fetch_api(k)
        if definitive:
            db.cache_put(conn, k, cached)
        elif not imported:
            raise DictionaryUnavailable(k)
    if imported:
        return _merge_imported(cached, imported)
    return cached
