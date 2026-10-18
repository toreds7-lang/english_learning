"""Built-in curriculum: one JSON file per level in app/data/levels/."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

LEVEL_DIR = Path(__file__).parent / "data" / "levels"


def word_key(word: str) -> str:
    """Normalized lookup key: lowercase, single spaces ("Look  Up" -> "look up")."""
    return re.sub(r"\s+", " ", word.strip().lower())


@lru_cache(maxsize=1)
def curriculum() -> tuple[list[dict], dict[str, dict]]:
    """Return (levels in study order, entries by word key).

    Each level carries `words`, a list of word keys in teaching order. A word that
    appears in two files belongs to the first level that lists it.
    """
    levels: list[dict] = []
    entries: dict[str, dict] = {}
    for path in sorted(LEVEL_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        keys = []
        for w in data["words"]:
            k = word_key(w["word"])
            if k in entries:
                continue
            entries[k] = {**w, "level": data["id"], "source": "built-in"}
            keys.append(k)
        meta = {k: v for k, v in data.items() if k != "words"}
        levels.append({**meta, "words": keys, "custom": False})
    levels.sort(key=lambda lv: lv["order"])
    return levels, entries
