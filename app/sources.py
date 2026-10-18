"""Free reading material for the library.

storybooks  ~760 short illustrated-book stories for beginners (Pre-A1 to B1), CC BY / CC BY-NC,
            from the African Storybook and Pratham Books (StoryWeaver), as kept in Markdown by
            the Global Storybooks project on GitHub (github.com/global-asp).
gutenberg   30 public-domain classics for B1-C2, split into chapters, downloaded from the
            Project Gutenberg mirror at gutenberg.pglaf.org (the main site asks programs to use
            mirrors, with a pause between requests).
teacher     any text a teacher pastes in; long texts are split into parts.

Each import runs once in the background and then works offline.
"""
from __future__ import annotations

import io
import re
import secrets
import sqlite3
import threading
import time
import zipfile

import httpx

from . import db
from .library import save_book

USER_AGENT = "WordStep/0.1 (classroom reading app)"
STORYBOOK_REPOS = [
    {"prefix": "asp", "repo": "global-asp/asp-source", "name": "African Storybook", "site": "https://africanstorybook.org"},
    {"prefix": "pb", "repo": "global-asp/pb-source", "name": "Pratham Books StoryWeaver", "site": "https://storyweaver.org.in"},
]
ZIP_URL = "https://codeload.github.com/{repo}/zip/refs/heads/master"
GUTENBERG_URL = "https://gutenberg.pglaf.org/cache/epub/{id}/pg{id}.txt"
GUTENBERG_DELAY = 2.0          # seconds between downloads, as the Gutenberg robot policy asks
MIN_STORY_WORDS = 8
UNIT_MAX_WORDS = 3500          # longer chapters are split into parts
PART_WORDS = 2200
UNIT_MIN_WORDS = 500           # shorter sections (fables, songs) are joined with the next ones
JOIN_TO_WORDS = 900

# (Gutenberg id, title, author, audience, heading style). Authors died before 1950, so these
# are public domain almost everywhere. Styles: toc = headings listed in the book's contents,
# chapter = "CHAPTER I" / "Chapter 1" / "STAVE I" / "Letter 1", roman = "IV. TITLE" or a lone
# numeral, none = no chapters (split by length).
GUTENBERG_BOOKS = [
    (14838, "The Tale of Peter Rabbit", "Beatrix Potter", "kids", "none"),
    (11757, "The Velveteen Rabbit", "Margery Williams", "kids", "none"),
    (21, "Aesop's Fables", "Aesop (tr. George Fyler Townsend)", "kids", "toc"),
    (2781, "Just So Stories", "Rudyard Kipling", "kids", "toc"),
    (2591, "Grimms' Fairy Tales", "Jacob and Wilhelm Grimm", "kids", "toc"),
    (1597, "Andersen's Fairy Tales", "Hans Christian Andersen", "kids", "toc"),
    (55, "The Wonderful Wizard of Oz", "L. Frank Baum", "kids", "chapter"),
    (11, "Alice's Adventures in Wonderland", "Lewis Carroll", "kids", "chapter"),
    (236, "The Jungle Book", "Rudyard Kipling", "kids", "toc"),
    (289, "The Wind in the Willows", "Kenneth Grahame", "kids", "roman"),
    (113, "The Secret Garden", "Frances Hodgson Burnett", "kids", "chapter"),
    (1874, "The Railway Children", "E. Nesbit", "kids", "chapter"),
    (778, "Five Children and It", "E. Nesbit", "kids", "chapter"),
    (271, "Black Beauty", "Anna Sewell", "kids", "numbered"),
    (45, "Anne of Green Gables", "L. M. Montgomery", "kids", "chapter"),
    (120, "Treasure Island", "Robert Louis Stevenson", "all", "roman"),
    (514, "Little Women", "Louisa May Alcott", "all", "chapter"),
    (46, "A Christmas Carol", "Charles Dickens", "all", "chapter"),
    (103, "Around the World in Eighty Days", "Jules Verne (tr. George M. Towle)", "all", "chapter"),
    (215, "The Call of the Wild", "Jack London", "all", "chapter"),
    (1661, "The Adventures of Sherlock Holmes", "Arthur Conan Doyle", "all", "toc"),
    (2852, "The Hound of the Baskervilles", "Arthur Conan Doyle", "all", "chapter"),
    (35, "The Time Machine", "H. G. Wells", "all", "roman"),
    (36, "The War of the Worlds", "H. G. Wells", "all", "roman"),
    (2776, "The Four Million (short stories)", "O. Henry", "all", "toc"),
    (1342, "Pride and Prejudice", "Jane Austen", "teens", "chapter"),
    (84, "Frankenstein", "Mary Shelley", "teens", "chapter"),
    (43, "The Strange Case of Dr Jekyll and Mr Hyde", "Robert Louis Stevenson", "teens", "toc"),
    (174, "The Picture of Dorian Gray", "Oscar Wilde", "teens", "chapter"),
    (2814, "Dubliners", "James Joyce", "teens", "toc"),
    (64317, "The Great Gatsby", "F. Scott Fitzgerald", "teens", "roman"),
    (829, "Gulliver's Travels", "Jonathan Swift", "teens", "chapter"),
]
GUTENBERG_SKIP = {21: {"life of aesop", "aesop s fables"}}   # sections left out, by normalized title


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+", text))


# ====================================================================== storybooks

LICENSES = {"cc-by": "CC BY 4.0", "cc-by-nc": "CC BY-NC 4.0", "cc by-nc-sa": "CC BY-NC-SA 4.0",
            "public domain": "Public domain"}


def parse_storybook(md: str) -> dict | None:
    """One Global Storybooks Markdown file: '# Title', pages split by '##', metadata list last."""
    sections = re.split(r"^##[ \t]*$", md.replace("\r", ""), flags=re.M)
    title = re.sub(r"^#\s*", "", sections[0].strip().splitlines()[0]).strip() if sections[0].strip() else ""
    meta: dict[str, str] = {}
    if len(sections) > 1 and re.search(r"^\*\s*\w+:", sections[-1], flags=re.M):
        for k, v in re.findall(r"^\*\s*([\w ]+):\s*(.+)$", sections.pop(), flags=re.M):
            meta[k.strip().lower()] = v.strip()
    paragraphs = []
    for page in sections[1:]:
        for para in re.split(r"\n\s*\n", page):
            para = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", para)          # image links, if any
            para = re.sub(r"\s+", " ", para).strip()
            if para:
                paragraphs.append(para)
    text = "\n\n".join(paragraphs)
    if not title or word_count(text) < MIN_STORY_WORDS:
        return None
    lic = meta.get("license", "").strip("[] ")
    return {"title": title, "text": text, "author": meta.get("text", ""),
            "illustration": meta.get("illustration", ""), "license": LICENSES.get(lic.lower(), lic)}


def import_storybooks(conn: sqlite3.Connection, progress=lambda done, total: None,
                      client: httpx.Client | None = None) -> int:
    client = client or httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    stories = []
    for src in STORYBOOK_REPOS:
        r = client.get(ZIP_URL.format(repo=src["repo"]))
        r.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        for name in sorted(zf.namelist()):
            m = re.search(r"/en/((\d+)_[^/]+)\.md$", name)
            if m:
                stories.append((src, m.group(1), m.group(2), zf.read(name).decode("utf-8", "replace")))
    seen, done = set(), 0
    for src, stem, num, md in stories:
        done += 1
        story = parse_storybook(md)
        if story is None:
            continue
        fingerprint = (story["title"].lower(), story["text"][:80].lower())
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        credit = " · ".join(x for x in (f"Text: {story['author']}" if story["author"] else "",
                                        f"Illustration: {story['illustration']}" if story["illustration"] else "",
                                        src["name"]) if x)
        save_book(conn, {
            "id": f"{src['prefix']}-{num}", "source": "storybook", "title": story["title"],
            "author": story["author"], "audience": "kids", "credit": credit, "license": story["license"],
            "url": f"https://github.com/{src['repo']}/blob/master/en/{stem}.md",
        }, [(story["title"], story["text"])])
        progress(done, len(stories))
    return len(seen)


# ====================================================================== Project Gutenberg

START_RE = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG E(?:BOOK|TEXT)[^\n]*\n")
END_RE = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG E(?:BOOK|TEXT)")
ROMAN = r"[IVXLC]+"
HEADING_RES = {
    "chapter": re.compile(r"^(?:CHAPTER|Chapter|STAVE|Stave|LETTER|Letter)\s+(?:" + ROMAN + r"|\d+|[A-Za-z]+)\b"),
    "roman": re.compile(r"^" + ROMAN + r"\.?$|^" + ROMAN + r"\.\s+[A-Z“\"']"),
    "numbered": re.compile(r"^\d{1,2}\.?\s+[A-Z]"),
}


def gutenberg_body(raw: str) -> str:
    raw = raw.lstrip("﻿").replace("\r\n", "\n")
    s, e = START_RE.search(raw), END_RE.search(raw)
    return raw[s.end() if s else 0: e.start() if e else len(raw)]


SKIP_SECTIONS = {"preface", "the preface", "index", "contents", "footnotes", "appendix", "glossary", "notes",
                 "transcriber s note", "transcriber s notes", "list of illustrations", "illustrations"}
ROMAN_WORD = re.compile(r"(?i)l?x{0,3}(ix|iv|v?i{0,3})\.?")
SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into", "nor", "of", "on", "or",
               "the", "to", "with"}


def clean_paragraph(p: str) -> str:
    p = re.sub(r"\[Illustration[^\]]*\]", "", p, flags=re.S)
    p = re.sub(r"\[(?:Footnote|Note)[^\]]*\]", "", p, flags=re.S)
    p = re.sub(r"_([^_]+)_", r"\1", p)                       # _italics_
    p = re.sub(r"\s+", " ", p).strip()
    if re.fullmatch(r"[*\s.\-—=]*", p) or re.fullmatch(r"(?i)the end\.?", p) or re.fullmatch(ROMAN + r"\.?", p):
        return ""
    if word_count(p) < 60 and re.search(r"(?i)\b(e-?book|project gutenberg|transcriber|produced by)\b", p):
        return ""
    return p


def norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def nice_title(s: str) -> str:
    """'CHAPTER II. THE EMPEROR'S NEW CLOTHES' -> 'Chapter II. The Emperor's New Clothes'."""
    s = re.sub(r"\s+", " ", s).strip().strip("[]").rstrip(".:]").strip()
    if re.fullmatch(ROMAN, s):
        return f"Chapter {s}"
    if s != s.upper():
        return s
    words = []
    for i, w in enumerate(s.lower().split(" ")):
        core = w.strip("“”\"'‘’(),.:;!?")
        if core and ROMAN_WORD.fullmatch(core):
            w = w.upper()
        elif i and core in SMALL_WORDS and not words[-1].endswith((":", ".")):
            pass
        else:
            w = "-".join(re.sub(r"[a-z]", lambda m: m.group(0).upper(), part, count=1) for part in w.split("-"))
        words.append(w)
    return " ".join(words)


def toc_entries(paras: list[str]) -> set[str]:
    """Lines of the contents list (the paragraphs after a 'Contents' heading)."""
    for i, p in enumerate(paras):
        if re.fullmatch(r"(?i)\s*(table of )?contents:?\s*", p):
            entries = set()
            for q in paras[i + 1:i + 40]:
                lines = [ln.strip() for ln in q.splitlines() if ln.strip()]
                if len(lines) == 1 and norm_title(lines[0]) in entries:
                    break                                     # the first heading of the body
                if word_count(q) / len(lines) >= 9 and word_count(q) >= 18:
                    break                                     # prose: the contents list is over
                entries |= {norm_title(re.sub(r"\s{2,}\S+\s*$", "", ln)) for ln in lines}
                entries |= {norm_title(ln) for ln in lines}
            return {e for e in entries if e}
    return set()


def is_heading(p: str, style: str, toc: set[str]) -> bool:
    lines = [ln.strip() for ln in p.splitlines() if ln.strip()]
    if not lines or len(lines) > 3 or len(p) > 120:
        return False
    if style == "toc":
        return norm_title(p) in toc
    rx = HEADING_RES.get(style)
    return bool(rx and rx.match(lines[0]))


def split_book(raw: str, style: str, skip: set[str] = frozenset()) -> list[tuple[str, str]]:
    """Split a Gutenberg text into reading units of a few thousand words.

    `skip` holds normalized section titles to leave out (besides prefaces and indexes).
    """
    paras = [p for p in re.split(r"\n\s*\n", gutenberg_body(raw)) if p.strip()]
    toc = toc_entries(paras) if style == "toc" else set()
    sections: list[list] = []          # [title, [paragraphs]]
    started = style == "none"
    for p in paras:
        if style != "none" and is_heading(p, style, toc):
            if norm_title(p) == "index" and sections:
                break                                         # the rest is the index
            sections.append([nice_title(" ".join(p.split())), []])
            started = True
            continue
        text = clean_paragraph(p)
        if not text or not started:
            continue
        if not sections:
            lines = [ln for ln in p.splitlines() if ln.strip()]
            if word_count(text) < 15 or word_count(p) / len(lines) < 7:   # title page, lists
                continue
            sections.append(["", []])
        sections[-1][1].append(text)
    # drop the contents list (headings with no text before the first real section) and prefaces
    while sections and word_count(" ".join(sections[0][1])) < 40:
        sections.pop(0)
    sections = [s for s in sections if norm_title(s[0]) not in SKIP_SECTIONS | skip]
    merged: list[list] = []
    for title, body in sections:
        if merged and word_count(" ".join(merged[-1][1])) < 40:      # "PART ONE" followed by "CHAPTER I"
            merged[-1] = [" · ".join(t for t in (merged[-1][0], title) if t), merged[-1][1] + body]
        else:
            merged.append([title, body])
    units = []
    pending: list | None = None
    for title, body in merged:
        n = word_count(" ".join(body))
        if pending and (pending[2] < UNIT_MIN_WORDS or n < UNIT_MIN_WORDS) and pending[2] + n <= JOIN_TO_WORDS * 1.5:
            pending[0].append(title)
            pending[1] += body
            pending[2] += n
            continue
        if pending:
            units.append(pending)
        pending = [[title], body, n]
    if pending:
        units.append(pending)
    out = []
    for titles, body, n in units:
        titles = [t for t in titles if t]
        title = " · ".join(titles[:3]) + (" …" if len(titles) > 3 else "")
        if n <= UNIT_MAX_WORDS:
            out.append((title, "\n\n".join(body)))
            continue
        parts, cur = [], []
        for para in body:
            cur.append(para)
            if word_count(" ".join(cur)) >= PART_WORDS:
                parts.append(cur)
                cur = []
        if cur:
            if parts and word_count(" ".join(cur)) < UNIT_MIN_WORDS:
                parts[-1] += cur
            else:
                parts.append(cur)
        for k, part in enumerate(parts, 1):
            out.append((f"{title} ({k}/{len(parts)})" if title else f"Part {len(out) + 1}", "\n\n".join(part)))
    return [(t or f"Part {i + 1}", body) for i, (t, body) in enumerate(out)]


def import_gutenberg(conn: sqlite3.Connection, progress=lambda done, total: None,
                     client: httpx.Client | None = None, delay: float = GUTENBERG_DELAY) -> int:
    client = client or httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    have = {r["id"] for r in conn.execute("SELECT id FROM books WHERE source = 'gutenberg'")}
    count = 0
    for i, (gid, title, author, audience, style) in enumerate(GUTENBERG_BOOKS, 1):
        book_id = f"pg-{gid}"
        if book_id not in have:
            r = client.get(GUTENBERG_URL.format(id=gid))
            r.raise_for_status()
            units = split_book(r.content.decode("utf-8", "replace"), style, GUTENBERG_SKIP.get(gid, set()))
            save_book(conn, {
                "id": book_id, "source": "gutenberg", "title": title, "author": author, "audience": audience,
                "credit": f"{author} · Project Gutenberg eBook #{gid}", "license": "Public domain (USA)",
                "url": f"https://www.gutenberg.org/ebooks/{gid}",
            }, units)
            if delay:
                time.sleep(delay)
        count += 1
        progress(i, len(GUTENBERG_BOOKS))
    return count


# ====================================================================== teachers' texts

def split_long_text(text: str) -> list[tuple[str, str]]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.replace("\r", "")) if p.strip()]
    if word_count(text) <= UNIT_MAX_WORDS:
        return [("", "\n\n".join(paras))]
    parts, cur = [], []
    for p in paras:
        cur.append(p)
        if word_count(" ".join(cur)) >= PART_WORDS:
            parts.append(cur)
            cur = []
    if cur:
        parts.append(cur)
    return [(f"Part {i}", "\n\n".join(p)) for i, p in enumerate(parts, 1)]


def add_teacher_text(conn: sqlite3.Connection, title: str, text: str, author: str = "",
                     audience: str = "all", credit: str = "") -> str:
    units = [(u or title, body) for u, body in split_long_text(text)]
    return save_book(conn, {"id": "t-" + secrets.token_hex(4), "source": "teacher", "title": title,
                            "author": author, "audience": audience, "credit": credit or "Added by a teacher"},
                     units)


# ====================================================================== background imports

SOURCES = {"storybooks": import_storybooks, "gutenberg": import_gutenberg}
JOBS: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def start_import(source: str) -> dict:
    """Run an import in a background thread; JOBS[source] reports progress."""
    with _jobs_lock:
        job = JOBS.get(source)
        if job and job["state"] == "running":
            return job
        job = JOBS[source] = {"state": "running", "done": 0, "total": 0, "error": None}

    def run():
        conn = db.connect()
        try:
            def progress(done, total):
                job.update(done=done, total=total)
            job["count"] = SOURCES[source](conn, progress)
            job["state"] = "done"
        except Exception as exc:  # network errors, a changed file format: report, don't crash
            job.update(state="error", error=f"{type(exc).__name__}: {exc}")
        finally:
            conn.close()

    threading.Thread(target=run, name=f"import-{source}", daemon=True).start()
    return job


if __name__ == "__main__":   # uv run python -m app.sources [storybooks] [gutenberg]
    import sys

    conn = db.connect()
    db.init(conn)
    for name in sys.argv[1:] or list(SOURCES):
        print(f"Importing {name}…")
        n = SOURCES[name](conn, lambda done, total: print(f"\r  {done}/{total}", end="", flush=True))
        print(f"\n  {n} books")
