"""Text analysis for the reading library: words, lemmas, names, sentences and text difficulty.

Every running word is reduced to a lemma ("went" -> "go", "children" -> "child"), so a
text can be compared with what a student knows. Names count as known (the usual rule in
lexical-coverage research), and numbers are ignored.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache

import lemminflect
from wordfreq import zipf_frequency

WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
SENTENCE_END_RE = re.compile(r"[.!?]+[\"'”’)\]]*(?=\s+|$)")
ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "st", "mt", "jr", "sr", "prof", "capt", "col", "gen",
                 "lt", "rev", "vs", "etc", "no", "messrs", "esq"}
NEGATIONS = {"can't": "can", "won't": "will", "shan't": "shall", "ain't": "be"}
CLITICS = ("n't", "'s", "'re", "'ve", "'ll", "'d", "'m")
# Interjections and sound words: like names, they don't decide whether a text is readable.
MARGINAL = set("""ah aha ahem ahh ahoy alas argh baa bah bam beep boo brr cluck ding dong eh er gee goodbye
grr ha hah haha hee hey hi hiss hm hmm ho hoo hooray hurrah hurray huh kapow lo meh meow miaow moo neigh oh
oho oink ooh oops ouch ow phew pow psst quack ribbit shh shoo splat tock toot tut tweet ugh uh um vroom
wham whee whoa whoosh woof wow yay yippee yuck yum zzz""".split())


def base_form(token: str) -> str:
    """Lowercase word without a clitic: "Anansi's" -> "anansi", "don't" -> "do"."""
    w = token.lower().replace("’", "'")
    if w in NEGATIONS:
        return NEGATIONS[w]
    for c in CLITICS:
        if w.endswith(c) and len(w) > len(c):
            return w[: -len(c)]
    return w


@lru_cache(maxsize=1 << 18)
def zipf(word: str) -> float:
    return zipf_frequency(word, "en")


@lru_cache(maxsize=1 << 18)
def lemma(word: str) -> str:
    """Dictionary form of a lowercase word, without part-of-speech context.

    Inflected verb forms go to the verb ("went" -> "go", "saw" -> "see") unless the word is
    also a common base form itself ("left" stays "left"); -ing and -ed words that are nouns or
    adjectives in their own right stay as they are ("evening", "tired"); plurals go to the singular.
    """
    cands = lemminflect.getAllLemmas(word)
    if not cands:
        return word
    verbs = [lm for pos in ("VERB", "AUX") for lm in cands.get(pos, ())]
    others = {lm for pos, lms in cands.items() if pos not in ("VERB", "AUX") for lm in lms}
    if word in others and word.endswith(("ing", "ed")):
        return word
    if word in others or word in verbs:
        alt = next((v for v in verbs if v != word), None)
        return alt if alt and zipf(alt) > zipf(word) + 0.3 else word
    if verbs:
        return verbs[0]
    for pos in ("NOUN", "ADJ", "ADV", "PROPN"):
        if pos in cands:
            return cands[pos][0]
    return word


def is_dictionary_word(word: str) -> bool:
    return bool(lemminflect.getAllLemmas(word))


def is_base_word(word: str) -> bool:
    """A dictionary word that is not an inflection of another word ("swim", not "swimming")."""
    cands = lemminflect.getAllLemmas(word)
    return bool(cands) and all(word in lms for lms in cands.values())


# ---------------------------------------------------------------- sentences

def sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of each sentence. Abbreviations like "Mr." don't end a sentence."""
    spans, start = [], 0
    for m in SENTENCE_END_RE.finditer(text):
        before = re.search(r"([A-Za-z]+)\.?$", text[start:m.start() + 1])
        if m.group(0).startswith(".") and before and before.group(1).lower() in ABBREVIATIONS:
            continue
        spans.append((start, m.end()))
        start = m.end()
        while start < len(text) and text[start].isspace():
            start += 1
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def sentences(text: str) -> list[str]:
    return [text[a:b].strip() for a, b in sentence_spans(text)]


# ---------------------------------------------------------------- analysis

def is_marginal(base: str) -> bool:
    """Sound words, interjections and made-up spellings ("shhh", "nubbly")."""
    return (base in MARGINAL or re.search(r"(.)\1\1", base) is not None
            or (not is_dictionary_word(base) and zipf(base) < 1.0))


@dataclass
class Token:
    start: int
    end: int
    surface: str
    lemma: str
    kind: str = "word"          # word | name | marginal (names and marginal words count as known)
    sentence_start: bool = False


@dataclass
class Analysis:
    paragraphs: list[str]
    tokens: list[list[Token]]                       # per paragraph
    counts: Counter = field(default_factory=Counter)  # lemma -> running words (free words excluded)
    words: int = 0                                  # all running words
    free_tokens: int = 0                            # names and marginal words
    sentences: int = 0

    @property
    def sentence_len(self) -> float:
        return self.words / self.sentences if self.sentences else 0.0


def split_paragraphs(text: str) -> list[str]:
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text.replace("\r", ""))]
    return [p for p in paras if p]


def analyze(text: str) -> Analysis:
    """Tokenize, lemmatize and find names in a text (paragraphs separated by blank lines)."""
    paragraphs = split_paragraphs(text)
    all_tokens: list[list[Token]] = []
    caps_inside, caps_first, lower_seen = Counter(), Counter(), set()
    n_sentences = 0
    for para in paragraphs:
        toks = []
        starts = [a for a, _ in sentence_spans(para)]
        n_sentences += len(starts)
        si = 0
        for m in WORD_RE.finditer(para):
            first = False
            while si < len(starts) and starts[si] <= m.start():   # first word of a sentence
                first, si = True, si + 1
            base = base_form(m.group(0))
            toks.append(Token(m.start(), m.end(), m.group(0), lemma(base), sentence_start=first))
            if m.group(0)[0].isupper():
                (caps_first if first else caps_inside)[base] += 1
            else:
                lower_seen.add(toks[-1].lemma)
        all_tokens.append(toks)

    def is_name(base: str) -> bool:
        if lemma(base) in lower_seen or zipf(base) >= 5.0:   # "Turtle" is a word if "turtles" occurs
            return False
        if caps_inside[base]:
            return True
        # only ever seen at the start of a sentence: a name if it isn't an English word
        return not is_dictionary_word(base) and zipf(base) < 3.0

    names = {b for b in set(caps_inside) | set(caps_first) if is_name(b)}
    a = Analysis(paragraphs, all_tokens, sentences=n_sentences)
    for toks in all_tokens:
        for t in toks:
            a.words += 1
            base = base_form(t.surface)
            t.kind = "name" if base in names else "marginal" if is_marginal(base) else "word"
            if t.kind == "word":
                a.counts[t.lemma] += 1
            else:
                a.free_tokens += 1
    return a
