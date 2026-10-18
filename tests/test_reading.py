import io
import json
import random
import zipfile
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ai, db, dictionary, library, main, reading, sources, textproc, vocab

TODAY = date(2026, 10, 17)

EASY_TEXT = """Tom has a small dog. The dog is brown and happy.
Every morning Tom and his dog walk to the park. They play with a red ball.

One day the ball goes into the water. The dog jumps in and gets the ball.
Tom laughs. "Good dog!" he says. They walk home together and eat lunch."""

HARD_TEXT = """The cartographer's meticulous palimpsest of ephemeral littoral demarcations confounded the
obstreperous quartermaster, whose perspicacity was notoriously evanescent.

Notwithstanding such vicissitudes, the indefatigable expedition persevered, circumnavigating
labyrinthine archipelagos whose idiosyncratic topography defied cartographic verisimilitude."""


# ---------------------------------------------------------------- text analysis

def test_lemmas_contractions_and_names():
    assert [textproc.lemma(w) for w in ("went", "children", "saw", "hungrier", "gobbling", "left", "evening")] == \
        ["go", "child", "see", "hungry", "gobble", "left", "evening"]
    assert [textproc.base_form(w) for w in ("Anansi's", "don't", "can't", "won’t", "I've")] == \
        ["anansi", "do", "can", "will", "i"]
    a = textproc.analyze('Anansi met Turtle. "Moo," said the cow. Turtle and the turtles swam. Shhh!')
    kinds = {t.surface: t.kind for toks in a.tokens for t in toks}
    assert kinds["Anansi"] == "name"            # capitalized, never lowercase, not an English word
    assert kinds["Turtle"] == "word"            # "turtles" also appears in lowercase
    assert kinds["Moo"] == kinds["Shhh"] == "marginal"
    assert a.words == a.free_tokens + sum(a.counts.values())


def test_sentences_ignore_abbreviations():
    assert textproc.sentences("Mr. Holmes sat down. Dr. Watson stood! Was it late?") == \
        ["Mr. Holmes sat down.", "Dr. Watson stood!", "Was it late?"]


# ---------------------------------------------------------------- vocabulary model

def test_knowledge_curve_and_estimate():
    assert vocab.rank("the") == 1 and vocab.rank("go") < vocab.rank("borrow") < vocab.rank("serendipity")
    assert vocab.p_known(2000, 2000) == pytest.approx(0.5)
    assert vocab.p_known(500, 2000) > 0.95 > 0.05 > vocab.p_known(8000, 2000)
    knows_to_3000 = [(r, int(r < 3000), 1.0) for r in range(200, 12000, 200)]
    assert 2400 < vocab.estimate_vocab(knows_to_3000, prior=1000, prior_sd=2) < 3800
    assert vocab.estimate_vocab([], prior=1500) == pytest.approx(1500, rel=0.02)
    assert [vocab.cefr(v) for v in (300, 800, 2000, 3000, 5000, 7000, 12000)] == \
        ["Pre-A1", "A1", "A2", "B1", "B2", "C1", "C2"]


def test_placement_items_are_safe_and_mixed():
    items = vocab.placement_items(random.Random(4))
    words = [it["word"] for it in items]
    fake = [w for w in words if w in vocab.PSEUDOWORDS]
    assert len(fake) == vocab.PSEUDOWORDS_PER_TEST
    assert len(words) == len(set(words)) == vocab.PSEUDOWORDS_PER_TEST + vocab.WORDS_PER_BAND * len(vocab.PLACEMENT_BANDS)
    assert not set(words) & vocab.BLOCKED
    assert all(textproc.is_base_word(w) for w in words if w not in fake)


def test_placement_scoring_corrects_for_guessing():
    items = [it["word"] for it in vocab.placement_items(random.Random(1))]
    honest = vocab.score_placement([(w, w not in vocab.PSEUDOWORDS and vocab.rank(w) < 4000) for w in items])
    assert honest["reliable"] and honest["false_alarm"] == 0
    assert 3000 <= honest["vocab"] <= 5000 and honest["cefr"] in ("B1", "B2")
    guesser = vocab.score_placement([(w, True) for w in items])
    assert not guesser["reliable"] and guesser["false_alarm"] == 1 and guesser["vocab"] <= 300


# ---------------------------------------------------------------- sources

STORY_MD = """# Fat King Thin Dog

##
This is a fat king.

##
The fat king has a thin dog.
The fat king and his thin dog go for a walk.

##
* License: [CC-BY]
* Text: Parismita
* Illustration: Parismita
* Language: en
"""

BOOK = """The Project Gutenberg eBook of Two Tales
*** START OF THE PROJECT GUTENBERG EBOOK TWO TALES ***

TWO TALES

Contents

     PREFACE
     CHAPTER I. The Red Hen
     CHAPTER II. The Lazy Cat

PREFACE

This preface explains many things about the old stories and the people who told them long ago in villages.
It goes on for a while so that it is clearly prose and not part of the contents list at all.

CHAPTER I.
The Red Hen

""" + ("The red hen found some wheat. She asked her friends for help, but nobody wanted to help her. " * 12) + """

[Illustration: The hen]

CHAPTER II.
The Lazy Cat

""" + ("The lazy cat slept all day in the warm sun, and the mice ran around the kitchen. " * 12) + """

*** END OF THE PROJECT GUTENBERG EBOOK TWO TALES ***
End matter that must not be read.
"""


def test_parse_storybook():
    s = sources.parse_storybook(STORY_MD)
    assert s["title"] == "Fat King Thin Dog" and s["author"] == "Parismita" and s["license"] == "CC BY 4.0"
    assert s["text"] == "This is a fat king.\n\nThe fat king has a thin dog. The fat king and his thin dog go for a walk."
    assert sources.parse_storybook("# Empty\n\n##\nHi.\n") is None      # too short to be a story


@pytest.mark.parametrize("style", ["chapter", "toc"])
def test_split_book_finds_chapters_and_skips_front_matter(style):
    units = sources.split_book(BOOK, style)
    assert [t for t, _ in units] == ["CHAPTER I. The Red Hen · CHAPTER II. The Lazy Cat"]   # short ones are joined
    body = units[0][1]
    assert body.startswith("The red hen found some wheat.") and "lazy cat" in body
    assert "Illustration" not in body and "preface" not in body.lower() and "End matter" not in body


def test_nice_title():
    assert sources.nice_title("CHAPTER II. THE EMPEROR'S NEW CLOTHES") == "Chapter II. The Emperor's New Clothes"
    assert sources.nice_title("XII. THE ADVENTURE OF THE COPPER BEECHES") == "XII. The Adventure of the Copper Beeches"
    assert sources.nice_title("IV") == "Chapter IV"
    assert sources.nice_title("The Lion and the Mouse") == "The Lion and the Mouse"


# ---------------------------------------------------------------- HTTP API

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main, "today", lambda: TODAY)
    monkeypatch.setattr(reading, "today", lambda: TODAY)
    monkeypatch.setattr(ai, "CONFIG_PATH", tmp_path / "ai.json")

    async def fake_fetch(word, client=None):
        return None, True

    monkeypatch.setattr(dictionary, "fetch_api", fake_fetch)
    monkeypatch.setattr(main, "fetch_api", fake_fetch)
    library.changed()
    with TestClient(main.app) as c:
        yield c


def make_student(client, name="Mina"):
    return client.post("/api/students", json={"name": name}).json()["id"]


def add_text(client, title, text, **kw):
    r = client.post("/api/library/texts", json={"title": title, "text": text, **kw})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def set_level(client, sid, words):
    r = client.patch(f"/api/students/{sid}/reading", json={"vocab_size": words})
    assert r.status_code == 200 and r.json()["vocab"] == words


def test_library_matches_texts_to_the_student(client):
    sid = make_student(client)
    set_level(client, sid, 3000)
    easy, hard = add_text(client, "Tom and his dog", EASY_TEXT), add_text(client, "The Expedition", HARD_TEXT)
    lib = client.get(f"/api/library?student={sid}").json()
    cards = {b["id"]: b for b in lib["books"]}
    assert cards[easy]["coverage"] > 0.97 > 0.85 > cards[hard]["coverage"]
    assert cards[easy]["fit"] in ("right", "easy") and cards[hard]["fit"] == "hard"
    assert lib["books"][0]["id"] == easy                       # best fit first
    rec = client.get(f"/api/library/recommend?student={sid}").json()
    assert rec["today"]["id"] == easy and rec["today"]["unit"] == 0
    assert [b["id"] for b in client.get(f"/api/library?student={sid}&fit=hard").json()["books"]] == [hard]

    answers = [{"word": w, "yes": False} for w in vocab.PSEUDOWORDS[:12]]
    answers += [{"word": w, "yes": True} for band in vocab.placement_candidates() for w in band[:5]]
    r = client.post("/api/placement", json={"student": sid, "answers": answers}).json()
    assert r["saved"] and r["cefr"] == "C2" and r["start_level"] == "L8"
    after = {b["id"]: b for b in client.get(f"/api/library?student={sid}").json()["books"]}
    assert after[hard]["coverage"] > cards[hard]["coverage"]   # a bigger vocabulary knows more of it
    assert client.get(f"/api/dashboard?student={sid}").json()["reading"]["cefr"] == "C2"


def test_guessing_on_the_placement_test_is_not_saved(client):
    sid = make_student(client)
    items = client.get("/api/placement").json()["items"]
    r = client.post("/api/placement", json={"student": sid, "answers": [{"word": i["word"], "yes": True} for i in items]}).json()
    assert not r["saved"] and not r["reliable"]
    assert client.get(f"/api/reading/profile?student={sid}").json()["placement"] is None


def test_reading_flow_links_words_and_level(client):
    sid = make_student(client)
    set_level(client, sid, 3000)
    book = add_text(client, "Tom and his dog", EASY_TEXT)
    client.post("/api/progress", json={"student": sid, "word": "ball", "action": "learning"})   # due today

    d = client.get(f"/api/read/{book}/0?student={sid}").json()
    cls = {(p["t"][w[0]:w[1]]): w[3] for p in d["paragraphs"] for w in p["w"]}
    assert cls["ball"] == "l" and cls["Tom"] == "n" and cls["dog"] == "k"
    assert d["learning_here"] == ["ball"] and d["fit"] in ("right", "easy")

    r = client.post("/api/read/lookup", json={"student": sid, "book": book, "idx": 0, "word": "laugh",
                                              "surface": "laughs", "sentence": "Tom laughs."})
    assert r.json()["ok"]
    client.post("/api/read/progress", json={"student": sid, "book": book, "idx": 0, "seconds": 50, "position": 0.4})
    assert client.get(f"/api/dashboard?student={sid}").json()["reading"]["minutes"] == 1

    check = client.get(f"/api/read/{book}/0/check?student={sid}").json()["questions"]
    assert check
    for q in check:
        assert "_____" in q["prompt"] and q["options"][q["answer"]] == q["answer_text"] and len(set(q["options"])) == 4

    answers = [{"word": "ball", "correct": True}] + [{"word": q["word"], "correct": True} for q in check]
    fin = client.post("/api/read/finish", json={"student": sid, "book": book, "idx": 0, "seconds": 40,
                                                "rating": "easy", "answers": answers}).json()
    assert fin["seconds"] == 90 and fin["wpm"] and fin["taps"] == ["laugh"]
    assert {"word": "ball", "correct": True, "box": 2} in fin["reviewed"]          # reviewed in context
    assert fin["target"] < 0.98 and fin["check"]["right"] == fin["check"]["total"]

    prof = client.get(f"/api/reading/profile?student={sid}").json()
    assert prof["totals"]["units"] == 1 and prof["totals"]["lookups"] == 1 and prof["recent"][0]["rating"] == "easy"
    assert prof["history"] and client.get(f"/api/dashboard?student={sid}").json()["streak"] == 1

    ctx = client.get(f"/api/word/contexts?q=laughing&student={sid}").json()
    assert ctx["word"] == "laugh" and ctx["seen"][0]["sentence"] == "Tom laughs."
    assert ctx["library"][0]["sentence"] == "Tom *laughs*."

    book_page = client.get(f"/api/library/book/{book}?student={sid}").json()
    assert book_page["finished"] and book_page["units_list"][0]["done"] and book_page["deletable"]
    assert client.delete(f"/api/library/book/{book}").json()["ok"]
    assert client.get(f"/api/read/{book}/0?student={sid}").status_code == 404


def test_phrasal_verbs_are_found_in_text():
    toks = textproc.analyze("She looked it up in the dictionary and then gave up.").tokens[0]
    found = library.find_phrases(toks, ["look up", "give up", "give in"])
    assert sorted((toks[i].surface, k) for i, k in found.items()) ==         [("gave", "give up"), ("looked", "look up"), ("up", "give up"), ("up", "look up")]


def test_storybook_and_gutenberg_imports(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "lib.db")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("asp-source-master/en/0002_fat-king.md", STORY_MD)
        zf.writestr("asp-source-master/fr/0002_roi.md", STORY_MD)          # other languages are ignored
    zipped = buf.getvalue()

    def handler(request):
        if "codeload.github.com" in str(request.url):
            return httpx.Response(200, content=zipped)
        return httpx.Response(200, content=BOOK.encode())

    conn = db.connect()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert sources.import_storybooks(conn, client=client) == 1               # the same story in both repos
    monkeypatch.setattr(sources, "GUTENBERG_BOOKS", [(9999, "Two Tales", "Anon", "kids", "chapter")])
    assert sources.import_gutenberg(conn, client=client, delay=0) == 1
    rows = {r["id"]: r for r in conn.execute("SELECT * FROM books")}
    assert rows["asp-0002"]["source"] == "storybook" and rows["asp-0002"]["license"] == "CC BY 4.0"
    assert rows["pg-9999"]["audience"] == "kids" and rows["pg-9999"]["units"] == 1
    ix = library.index(conn)
    assert ix.books["asp-0002"].cefr and ix.units[("pg-9999", 0)].words > 100
    conn.close()


# ---------------------------------------------------------------- AI stories (Claude call faked)

def test_ai_story_is_revised_when_too_hard(client, monkeypatch):
    sid = make_student(client)
    calls = []

    async def fake_ask(system, prompt, schema):
        calls.append(prompt)
        hard = len(calls) == 1
        paragraphs = ["Mia wanted to borrow a book. " + ("The perspicacious librarian was obstreperous." if hard
                                                         else "The kind man at the library smiled."),
                      "She said she would borrow it for one week, and she gave it back on time."]
        return {"title": "The Library Book", "paragraphs": paragraphs, "questions": [
            {"question": "What did Mia want?", "options": ["A book", "A cat", "A cake", "A bike"], "answer": 0,
             "explanation": "She wanted to borrow a book."},
            {"question": "Broken question", "options": ["Yes", "No"], "answer": 3, "explanation": ""}]}

    monkeypatch.setattr(ai, "ask", fake_ask)
    r = client.post("/api/ai/story", json={"student": sid, "topic": "a library", "words": ["borrow"]}).json()
    assert r["revised"] and len(calls) == 2 and "perspicacious" in calls[1]
    assert "borrow" in calls[0] and "CEFR level" in calls[0]
    d = client.get(f"/api/read/{r['id']}/0?student={sid}").json()
    assert "perspicacious" not in d["paragraphs"][0]["t"] and d["target_words"] == ["borrow"]
    assert any(w[3] == "t" for p in d["paragraphs"] for w in p["w"])            # target words are marked
    qs = client.get(f"/api/read/{r['id']}/0/questions?student={sid}").json()["questions"]
    assert [q["question"] for q in qs] == ["What did Mia want?"]              # invalid ones dropped
    other = make_student(client, "Jun")
    assert client.get(f"/api/read/{r['id']}/0?student={other}").status_code == 404   # private to Mina


def test_ai_settings_and_errors(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert not client.get("/api/ai/config").json()["configured"]
    s = client.post("/api/ai/config", json={"api_key": "sk-ant-test-1234", "model": "claude-haiku-5-5"}).json()
    assert s["configured"] and s["key_hint"] == "…1234" and s["model"] == "claude-haiku-5-5"
    assert json.loads(ai.CONFIG_PATH.read_text())["api_key"] == "sk-ant-test-1234"
    assert client.post("/api/ai/config", json={"model": "gpt-4"}).status_code == 422
    assert not client.post("/api/ai/config", json={"clear_key": True}).json()["configured"]

    async def failing(*a, **k):
        raise ai.AIError("The Claude API key was not accepted. Check it in Settings.")

    monkeypatch.setattr(ai, "ask", failing)
    sid = make_student(client)
    r = client.post("/api/ai/story", json={"student": sid})
    assert r.status_code == 503 and "not accepted" in r.json()["detail"]


def test_ai_questions_are_cached(client, monkeypatch):
    sid = make_student(client)
    book = add_text(client, "Tom and his dog", EASY_TEXT)
    n = []

    async def fake_ask(system, prompt, schema):
        n.append(1)
        assert "Tom has a small dog" in prompt
        return {"questions": [{"question": "Who has a dog?", "options": ["Tom", "Ann", "Bo", "Cy"], "answer": 0,
                               "explanation": "Tom has a small dog."}]}

    monkeypatch.setattr(ai, "ask", fake_ask)
    for _ in range(2):
        r = client.post("/api/ai/questions", json={"book": book, "idx": 0}).json()
        assert r["questions"][0]["question"] == "Who has a dog?"
    assert len(n) == 1
    assert client.get(f"/api/read/{book}/0?student={sid}").json()["has_questions"]
