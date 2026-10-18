import random
import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import ai, db, dictionary, grammar, library, main, reading

TODAY = date(2026, 10, 17)
STORY = """Mia lives in a small town. Every morning she walks to school with her dog.

Yesterday it was raining when she left the house. She was carrying a big bag, and she didn't see the hole.
She fell into the water! A man who was standing at the bus stop helped her. "Are you OK?" he asked.

Mia has never forgotten that day. If it rains tomorrow, she will take the bus."""


# ---------------------------------------------------------------- content

def test_grammar_content_is_complete():
    units, points, by_id = grammar.content()
    unit_ids = {u["id"] for u in units}
    assert len(points) == len(by_id) >= 24
    assert sorted(p["order"] for p in points) == list(range(1, len(points) + 1))
    for p in points:
        assert p["unit"] in unit_ids, p["id"]
        for key in ("title", "grammar", "band", "use", "mission"):
            assert p[key].strip(), (p["id"], key)
        assert len(p["form"]) >= 3 and len(p["examples"]) >= 4 and len(p["mistakes"]) >= 2, p["id"]
        assert all("*" in ex and ex.count("*") % 2 == 0 for ex in p["examples"]), p["id"]
        assert all(m["wrong"] and "*" in m["right"] and m["why"] for m in p["mistakes"]), p["id"]
        types = {q["type"] for q in p["questions"]}
        assert types == set(grammar.QUESTION_TYPES), (p["id"], types)
        for q in p["questions"]:
            assert q["why"].strip(), (p["id"], q)
            if q["type"] == "situation":
                assert len(set(q["options"])) == len(q["options"]) >= 3 and 0 <= q["answer"] < len(q["options"])
            elif q["type"] == "gap":
                marks = re.findall(r"\*([^*]+)\*", q["sentence"])
                assert len(marks) == 1 and marks[0] in q["options"] and len(set(q["options"])) == len(q["options"]) >= 3, q
            elif q["type"] == "fix":
                m = re.search(r"(^|[\s\"'(])\*([^*]+)\*([\s.,!?]|$)", q["sentence"])   # whole words only
                assert q["sentence"].count("*") == 2 and m and m.group(2) != q["right"], q
            elif q["type"] == "order":
                assert len(q["answer"].split()) >= 4 and "*" not in q["answer"], q


def test_every_point_is_found_in_its_own_examples():
    for p in grammar.content()[1]:
        found = [ex for ex in p["examples"] if grammar.find_in_paragraph(p["id"], grammar.plain(ex))]
        assert len(found) >= 2, (p["id"], found)


@pytest.mark.parametrize("pid, sentence", [
    ("passive", "She is tired after work."),
    ("present-perfect", "I have to go now."),
    ("present-continuous", "It was evening and this is interesting."),
    ("comparisons", "We walked in the forest and I would rather stay."),
    ("relative-clauses", "I know who did it."),
    ("used-to", "I am used to the noise."),
    ("for-since", "I've never cooked for a dog before."),
    ("articles", "A man came in. The woman left."),
])
def test_lookalikes_are_not_flagged(pid, sentence):
    assert grammar.find_in_paragraph(pid, sentence) == []


def test_question_items_are_ready_to_answer():
    rng = random.Random(3)
    fix = grammar.fix_parts("Why *you are* late?", "are you")
    assert fix["tokens"] == ["Why", "you", "are", "late?"] and fix["wrong"] == [1, 2]
    assert fix["corrected"] == "Why *are you* late?"
    removed = grammar.fix_parts("Although he is rich, *but* he isn't happy.", "")
    assert removed["corrected"] == "Although he is rich, he isn't happy."
    order = grammar.order_parts("If you need help, I'll be in the kitchen.", ["I'll be in the kitchen if you need help."], rng)
    assert sorted(order["tiles"]) == sorted(["if", "you", "need", "help", "I'll", "be", "in", "the", "kitchen"])
    assert order["answers"] == ["if you need help i'll be in the kitchen", "i'll be in the kitchen if you need help"]
    for p in grammar.content()[1]:
        for it in grammar.practice_items(p, rng):
            if it["type"] in ("situation", "gap"):
                assert 0 <= it["answer"] < len(it["options"])
            if it["type"] == "gap":
                assert "_____" in it["prompt"] and "*" not in it["prompt"]
                assert it["options"][it["answer"]] == re.search(r"\*([^*]+)\*", it["full"]).group(1)
            if it["type"] == "order":
                assert grammar.norm_answer(" ".join(it["tiles"])) not in it["answers"]       # really shuffled
                assert grammar.norm_answer(it["answer_text"]) == it["answers"][0]


def test_spacing_rules():
    s = grammar.schedule
    assert s(0, None, 1.0, TODAY) == (1, TODAY + timedelta(days=1))               # new point learned
    assert s(2, TODAY.isoformat(), 0.85, TODAY) == (3, TODAY + timedelta(days=7))  # due and good: up
    later = (TODAY + timedelta(days=5)).isoformat()
    assert s(3, later, 1.0, TODAY) == (3, TODAY + timedelta(days=5))               # extra practice keeps spacing
    assert s(4, TODAY.isoformat(), 0.6, TODAY) == (4, TODAY + timedelta(days=1))   # so-so: same box, tomorrow
    assert s(4, TODAY.isoformat(), 0.3, TODAY) == (1, TODAY + timedelta(days=1))   # poor: start again


# ---------------------------------------------------------------- HTTP API

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    for mod in (main, reading, grammar):
        monkeypatch.setattr(mod, "today", lambda: TODAY)
    monkeypatch.setattr(ai, "CONFIG_PATH", tmp_path / "ai.json")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    async def fake_fetch(word, client=None):
        return None, True

    monkeypatch.setattr(dictionary, "fetch_api", fake_fetch)
    monkeypatch.setattr(main, "fetch_api", fake_fetch)
    library.changed()
    with TestClient(main.app) as c:
        yield c


def make_student(client, name="Mina"):
    return client.post("/api/students", json={"name": name}).json()["id"]


def test_practice_review_and_dashboard(client, monkeypatch):
    sid = make_student(client)
    g = client.get(f"/api/grammar?student={sid}").json()
    assert g["total"] == len(g["points"]) and g["started"] == 0 and g["next"]["id"] == "be"
    assert client.get(f"/api/dashboard?student={sid}").json()["grammar"]["next"]["id"] == "be"

    page = client.get(f"/api/grammar/point/past-simple?student={sid}").json()
    assert page["point"]["title"] == "Tell what happened" and page["progress"]["status"] == "new"
    assert page["prev"] and page["next"] and not page["ai"]
    assert client.get(f"/api/grammar/point/nope?student={sid}").status_code == 404

    s = client.get(f"/api/grammar/session?student={sid}&point=past-simple").json()
    assert s["mode"] == "practice" and set(s["points"]) == {"past-simple"}
    assert {it["type"] for it in s["items"]} == {"situation", "gap", "fix", "order", "dictation"}

    answers = [{"q": it["qid"], "correct": it["qid"] != "q3"} for it in s["items"]]   # 7 of 8
    r = client.post("/api/grammar/result", json={"student": sid, "results": [{"point": "past-simple", "answers": answers}]}).json()
    res = r["results"][0]
    assert res["right"] == 7 and res["box"] == 1 and res["due"] == (TODAY + timedelta(days=1)).isoformat()
    poor = [{"q": "q0", "correct": False}, {"q": "q1", "correct": False}, {"q": "q2", "correct": True}]
    client.post("/api/grammar/result", json={"student": sid, "results": [{"point": "be", "answers": poor}]})

    g = client.get(f"/api/grammar?student={sid}").json()
    cards = {c["id"]: c for c in g["points"]}
    assert cards["past-simple"]["status"] == "learning" and cards["be"]["box"] == 1 and g["started"] == 2
    assert g["next"]["id"] == "present-simple" and g["due"] == 0
    d = client.get(f"/api/dashboard?student={sid}").json()
    assert d["streak"] == 1 and d["grammar"]["started"] == 2

    # tomorrow both points are due; missed questions come first
    assert client.get(f"/api/grammar/session?student={sid}").json()["items"] == []   # nothing due today
    monkeypatch.setattr(grammar, "today", lambda: TODAY + timedelta(days=1))
    rv = client.get(f"/api/grammar/session?student={sid}").json()
    assert rv["mode"] == "review" and set(rv["points"]) == {"past-simple", "be"}
    be_ids = [it["qid"] for it in rv["items"] if it["point"] == "be" and it["type"] != "dictation"]
    assert be_ids[:2] == ["q0", "q1"]
    ps_ids = [it["qid"] for it in rv["items"] if it["point"] == "past-simple"]
    assert ps_ids[0] == "q3"
    assert rv["items"][0]["point"] != rv["items"][1]["point"]                    # interleaved
    assert client.get(f"/api/dashboard?student={sid}").json()["grammar"]["due"] == 0  # main.today is still today


def test_writing_is_saved_and_checked(client, monkeypatch):
    sid = make_student(client)
    r = client.post("/api/grammar/write", json={"student": sid, "point": "past-simple", "text": "Yesterday I go to the park."}).json()
    assert r["check"] is None and not r["ai"]
    assert client.get(f"/api/grammar/point/past-simple?student={sid}").json()["writing"][0]["text"] == "Yesterday I go to the park."

    seen = {}

    async def fake_ask(system, prompt, schema):
        seen["prompt"] = prompt
        return {"uses_target": True, "correct": False, "corrected": "Yesterday I went to the park.",
                "fixes": [{"wrong": "go", "right": "went", "why": "Yesterday is finished time."}],
                "feedback": "Nice idea! Use the past: went."}

    monkeypatch.setattr(ai, "ask", fake_ask)
    client.post("/api/ai/config", json={"api_key": "sk-test"})
    r = client.post("/api/grammar/write", json={"student": sid, "point": "past-simple", "text": "Yesterday I go to the park."}).json()
    assert r["ai"] and r["check"]["corrected"] == "Yesterday I went to the park." and r["check"]["fixes"][0]["right"] == "went"
    assert "Past simple" in seen["prompt"] and "Yesterday I go" in seen["prompt"]
    page = client.get(f"/api/grammar/point/past-simple?student={sid}").json()
    assert page["ai"] and page["writing"][0]["corrected"] == "Yesterday I went to the park." and page["writing"][0]["ok"] == 0

    async def failing(*a):
        raise ai.AIError("Too many requests right now.")

    monkeypatch.setattr(ai, "ask", failing)
    r = client.post("/api/grammar/write", json={"student": sid, "point": "be", "text": "I am Mina."}).json()
    assert r["check"] is None and r["error"] == "Too many requests right now."


def test_grammar_in_books_and_reader(client, monkeypatch):
    sid = make_student(client)
    client.patch(f"/api/students/{sid}/reading", json={"vocab_size": 3000})
    book = client.post("/api/library/texts", json={"title": "Mia and the Rain", "text": STORY}).json()["id"]

    ex = client.get(f"/api/grammar/examples/past-continuous?student={sid}").json()["examples"]
    assert ex and ex[0]["book"] == book and "*was raining*" in ex[0]["sentence"]
    rel = client.get(f"/api/grammar/examples/relative-clauses?student={sid}").json()["examples"]
    assert "*man who*" in rel[0]["sentence"]

    scan = client.get(f"/api/grammar/scan?student={sid}&book={book}&idx=0").json()
    ids = {p["id"]: p["count"] for p in scan["points"]}
    for pid in ("present-simple", "past-continuous", "past-simple", "present-perfect", "if-real", "questions"):
        assert ids.get(pid), pid
    para = client.get(f"/api/read/{book}/0?student={sid}").json()["paragraphs"]
    pi, s, e = scan["spans"]["present-perfect"][0]
    assert para[pi]["t"][s:e] == "has never forgotten"
    assert client.get(f"/api/grammar/scan?student={sid}&book=nope&idx=0").status_code == 404

    # an AI story can be built around a grammar point, and the reader then highlights it
    async def fake_ask(system, prompt, schema):
        assert "Grammar focus: Past continuous" in prompt or "Keep using Past continuous often" in prompt
        return {"title": "The Storm", "paragraphs": ["The wind was blowing and the children were playing."],
                "questions": []}

    monkeypatch.setattr(ai, "ask", fake_ask)
    r = client.post("/api/ai/story", json={"student": sid, "topic": "a storm", "grammar": "past-continuous"}).json()
    assert client.get(f"/api/read/{r['id']}/0?student={sid}").json()["grammar"] == "past-continuous"
