"""Learner vocabulary model.

A student's level is one number: an estimated vocabulary size V, measured on a frequency
ranking of English lemmas (rank 1 = "the"). The chance that the student knows a word of
frequency rank r is a logistic curve that crosses 50% at r = V (the library lowers r for
words that are common in children's stories, which learners meet early; see library.py):

    P(known) = 1 / (1 + (r / V) ** SLOPE)

V comes from a yes/no placement test (with made-up words to correct for guessing) and is
then refined from reading: words a student taps count as unknown, words they read past
count weakly as known, and "I know this word" counts as known.

The same scale gives each text a difficulty: the share of its running words a student
probably knows (its lexical coverage). Reading research puts comfortable reading at about
98% known words (2 unknown in 100), and study reading with support at about 95%.
"""
from __future__ import annotations

import json
import math
import random
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from wordfreq import top_n_list, word_frequency

from .textproc import base_form, is_base_word, lemma

ROOT = Path(__file__).resolve().parent.parent
RANK_CACHE = ROOT / "cache" / "lemma_ranks.json"
RANK_SOURCE_SIZE = 100_000       # surface forms taken from wordfreq's English list
RARE_RANK = 60_000               # rank used for words that aren't in the list
SLOPE = 3.5                      # steepness of the knowledge curve, per natural-log unit of rank
DEFAULT_VOCAB = 1500             # before any placement test
MIN_VOCAB, MAX_VOCAB = 150, 30_000

# Approximate CEFR bands on this scale (lemmas known, counted on the frequency list), after
# Milton's (2010) vocabulary sizes per CEFR level, stretched at the top where his test stops.
CEFR_BANDS = [(0, "Pre-A1"), (500, "A1"), (1500, "A2"), (2500, "B1"), (4000, "B2"), (6000, "C1"), (9000, "C2")]
CEFR_ORDER = [c for _, c in CEFR_BANDS]


def cefr(vocab: float) -> str:
    label = CEFR_BANDS[0][1]
    for floor, name in CEFR_BANDS:
        if vocab >= floor:
            label = name
    return label


# ---------------------------------------------------------------- frequency ranks

def _build_ranks() -> dict[str, int]:
    freq: dict[str, float] = {}
    for w in top_n_list("en", RANK_SOURCE_SIZE):
        if not re.fullmatch(r"[a-z]+(?:'[a-z]+)?", w):
            continue
        lm = lemma(base_form(w))
        freq[lm] = freq.get(lm, 0.0) + word_frequency(w, "en")
    ordered = sorted(freq, key=lambda k: -freq[k])
    return {w: i + 1 for i, w in enumerate(ordered)}


@lru_cache(maxsize=1)
def ranks() -> dict[str, int]:
    """Lemma -> frequency rank, built once from wordfreq and cached in cache/."""
    try:
        data = json.loads(RANK_CACHE.read_text(encoding="utf-8"))
        if data.get("size") == RANK_SOURCE_SIZE:
            return data["ranks"]
    except (OSError, ValueError, KeyError):
        pass
    r = _build_ranks()
    try:
        RANK_CACHE.parent.mkdir(parents=True, exist_ok=True)
        RANK_CACHE.write_text(json.dumps({"size": RANK_SOURCE_SIZE, "ranks": r}), encoding="utf-8")
    except OSError:
        pass
    return r


def rank(lemma_key: str) -> int:
    """Frequency rank of a lemma; multi-word items take the rank of their rarest word."""
    table = ranks()
    return max(table.get(w, RARE_RANK) for w in lemma_key.split()) if lemma_key else RARE_RANK


def p_known(r, vocab: float):
    """Chance of knowing a word of rank r (scalar or numpy array)."""
    return 1.0 / (1.0 + (np.asarray(r, dtype=float) / vocab) ** SLOPE)


# ---------------------------------------------------------------- level estimate

def estimate_vocab(evidence: list[tuple[int, int, float]], prior: float, prior_sd: float = 0.6) -> float:
    """Most likely V given (rank, known 0/1, weight) observations and a log-normal prior."""
    grid = np.linspace(math.log(MIN_VOCAB), math.log(MAX_VOCAB), 400)
    score = -((grid - math.log(prior)) ** 2) / (2 * prior_sd ** 2)
    if evidence:
        r = np.log(np.array([e[0] for e in evidence], dtype=float))[:, None]
        y = np.array([e[1] for e in evidence], dtype=float)[:, None]
        w = np.array([e[2] for e in evidence], dtype=float)[:, None]
        z = SLOPE * (grid[None, :] - r)               # log-odds of knowing each word
        loglik = y * -np.logaddexp(0, -z) + (1 - y) * -np.logaddexp(0, z)
        score = score + (w * loglik).sum(axis=0)
    return float(math.exp(grid[int(np.argmax(score))]))


# ---------------------------------------------------------------- placement test

PLACEMENT_BANDS = [(250, 1000), (1000, 2000), (2000, 3000), (3000, 4000), (4000, 5000), (5000, 6500),
                   (6500, 8000), (8000, 10000), (10000, 13000), (13000, 16000), (16000, 20000)]
WORDS_PER_BAND = 5
KNOWN_BELOW = 250               # the 250 most frequent lemmas are assumed known
PSEUDOWORDS = """blendary crandle dorpish fluggard gristake hobnical jindle lorrish mandicate nuvery
plonderous quindle ruftle skarrow tramnify vellicop wembish yarnicle zorpid brastical chindery deflonate
fendicle glorpen jestulate mabble nindle obstrine prandicle scrobious torpicate whumble cralder fosterine
grimple hesticate lumbrous morvish pelterize sprocken trundance vorgle bramblet dwindish flonkary""".split()
PSEUDOWORDS_PER_TEST = 12
# Words kept out of the placement test (it is shown to children).
BLOCKED = set("""abortion anal anus arse ass bastard bitch blowjob boob boobs breast butt cock condom crap
cunt damn dick dildo drug drunk erotic fag fuck gay genital hell homo horny incest kill lesbian masturbate
naked nazi nigger nipple nude orgasm penis piss porn prostitute pussy queer rape rapist retard scrotum semen
sex sexual sexy shit slut sperm suicide testicle tit tits vagina viagra whore""".split())


@lru_cache(maxsize=1)
def placement_candidates() -> list[list[str]]:
    """Per band, base-form dictionary words that are safe to show."""
    bands: list[list[str]] = [[] for _ in PLACEMENT_BANDS]
    for w, r in ranks().items():
        if not (3 <= len(w) <= 12 and w.isalpha() and w not in BLOCKED):
            continue
        if not is_base_word(w):
            continue
        for i, (lo, hi) in enumerate(PLACEMENT_BANDS):
            if lo <= r < hi:
                bands[i].append(w)
                break
    return bands


def placement_items(rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    items = [{"word": w, "band": i}
             for i, words in enumerate(placement_candidates())
             for w in rng.sample(words, min(WORDS_PER_BAND, len(words)))]
    items += [{"word": w, "band": None} for w in rng.sample(PSEUDOWORDS, PSEUDOWORDS_PER_TEST)]
    rng.shuffle(items)
    return [{"word": it["word"]} for it in items]


def score_placement(answers: list[tuple[str, bool]]) -> dict:
    """Meara-style yes/no score: hit rate per band, corrected by the false-alarm rate on made-up words."""
    fake = set(PSEUDOWORDS)
    fake_answers = [yes for w, yes in answers if w in fake]
    false_alarm = sum(fake_answers) / len(fake_answers) if fake_answers else 0.0
    by_band: list[list[bool]] = [[] for _ in PLACEMENT_BANDS]
    evidence = []
    for w, yes in answers:
        if w in fake:
            continue
        r = rank(w)
        for i, (lo, hi) in enumerate(PLACEMENT_BANDS):
            if lo <= r < hi:
                by_band[i].append(yes)
                break
        evidence.append((r, int(yes), (1.0 - false_alarm) if yes else 1.0))
    vocab = float(KNOWN_BELOW)
    bands = []
    for (lo, hi), got in zip(PLACEMENT_BANDS, by_band):
        hit = sum(got) / len(got) if got else 0.0
        adjusted = max(0.0, (hit - false_alarm) / (1 - false_alarm)) if false_alarm < 1 else 0.0
        vocab += adjusted * (hi - lo)
        bands.append({"from": lo, "to": hi, "known": round(adjusted, 2)})
    vocab = min(max(vocab, MIN_VOCAB), MAX_VOCAB)
    return {"vocab": round(vocab), "cefr": cefr(vocab), "false_alarm": round(false_alarm, 2),
            "reliable": false_alarm <= 0.25, "bands": bands, "evidence": evidence}
