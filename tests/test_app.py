import json
import random
import socket
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db, dictionary, launch, main, srs
from app.content import LEVEL_DIR, curriculum, word_key
from app.quiz import PRETEST_TYPES, REVIEW_TYPES, build_quiz, cloze, make_question
from app.tts import model_dir

TODAY = date(2026, 10, 17)


# ---------------------------------------------------------------- curriculum data

def test_level_files_are_complete():
    seen = set()
    for path in sorted(LEVEL_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert {"id", "order", "title", "band", "kind", "description", "words"} <= data.keys()
        assert len(data["words"]) == 30, path.name
        for w in data["words"]:
            k = word_key(w["word"])
            assert k not in seen, f"duplicate {k}"
            seen.add(k)
            assert w["ipa"].startswith("/") and w["ipa"].endswith("/"), k
            assert w["definition"] and w["pos"], k
            assert len(w["examples"]) >= 2, k
            for ex in w["examples"]:
                assert ex.count("*") >= 2 and ex.count("*") % 2 == 0, f"{k}: {ex}"
            assert cloze(w) is not None, f"{k} has no single-target example for fill-in-the-blank"
    assert len(seen) == 240


def test_levels_are_ordered_step_by_step():
    levels, entries = curriculum()
    assert [lv["id"] for lv in levels] == [f"L{i}" for i in range(1, 9)]
    assert levels[2]["kind"] == "phrasal" and levels[-1]["kind"] == "advanced"
    phrasal = [entries[k] for lv in levels if lv["kind"] == "phrasal" for k in lv["words"]]
    assert all(len(e["word"].split()) == 2 for e in phrasal), "phrasal verbs should be two words"


# ---------------------------------------------------------------- spaced repetition

def test_srs_progression():
    box, due = srs.after_answer(0, True, TODAY)
    assert (box, due) == (1, TODAY + timedelta(days=1))
    box, due = srs.after_answer(3, True, TODAY)
    assert (box, due) == (4, TODAY + timedelta(days=14)) and srs.status(box) == "mastered"
    assert srs.after_answer(5, True, TODAY)[0] == 5
    assert srs.after_answer(4, False, TODAY) == (1, TODAY + timedelta(days=1))
    assert srs.mark_known(TODAY) == (4, TODAY + timedelta(days=14))
    assert srs.mark_learning(0, TODAY) == (1, TODAY)
    assert srs.mark_learning(2, TODAY) == (2, TODAY)
    assert srs.mark_learning(5, TODAY) == (1, TODAY)


# ---------------------------------------------------------------- quiz generation

def test_quiz_questions_are_well_formed():
    entries = curriculum()[1]
    pool = [entries[k] for k in curriculum()[0][0]["words"]]
    rng = random.Random(1)
    for qtype in REVIEW_TYPES:
        for e in pool[:10]:
            q = make_question(e, pool, qtype, rng)
            assert q is not None
            if qtype == "spell":
                assert q["answer_text"] == e["word"]
                continue
            assert len(q["options"]) == 4 and len(set(q["options"])) == 4
            expected = e["definition"] if qtype == "word" else e["word"]
            assert q["options"][q["answer"]] == expected
            if qtype == "cloze":
                assert "_____" in q["prompt"] and "*" not in q["prompt"]


def test_build_quiz_mixes_types_and_respects_mode():
    entries = list(curriculum()[1].values())[:30]
    qs = build_quiz(entries[:12], entries, REVIEW_TYPES, random.Random(3))
    assert len(qs) == 12
    assert {q["type"] for q in qs} == set(REVIEW_TYPES)
    qs = build_quiz(entries[:12], entries, PRETEST_TYPES, random.Random(3))
    assert "spell" not in {q["type"] for q in qs}


# ---------------------------------------------------------------- dictionary API normalisation

API_SAMPLE = [{
    "word": "serendipity",
    "phonetics": [{"text": "/ˌsɛɹənˈdɪpɪti/"}],
    "meanings": [{
        "partOfSpeech": "noun",
        "definitions": [{"definition": "A combination of events which have come together by chance to make a surprisingly good result.",
                         "example": "Finding that book was pure serendipity.", "synonyms": ["chance"]}],
        "synonyms": ["luck", "chance"],
    }],
}]


def test_normalize_api():
    e = dictionary.normalize_api("serendipity", API_SAMPLE)
    assert e["ipa"] == "/ˌsɛɹənˈdɪpɪti/"
    assert e["pos"] == "noun" and e["definition"].startswith("A combination")
    assert e["examples"] == ["Finding that book was pure *serendipity*."]
    assert e["synonyms"] == ["chance", "luck"]
    assert dictionary.normalize_api("x", {"title": "No Definitions Found"}) is None


@pytest.mark.parametrize("status, ctype, body, expected", [
    (200, "application/json", json.dumps(API_SAMPLE), (True, True)),
    (404, "application/json", '{"title": "No Definitions Found"}', (False, True)),
    (404, "text/html", "<!DOCTYPE html><title>404 page</title>", (False, False)),  # flaky server page
    (502, "text/html", "bad gateway", (False, False)),
])
def test_fetch_api_tells_misses_from_outages(status, ctype, body, expected):
    import asyncio

    import httpx

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"content-type": ctype}, text=body)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await dictionary.fetch_api("serendipity", client)

    entry, definitive = asyncio.run(run())
    assert (entry is not None, definitive) == expected
    assert len(calls) == (1 if definitive else 2)   # transient failures are retried once


def test_mark_target_handles_inflections_and_phrasal_verbs():
    assert dictionary.mark_target("She looked up the word.", "look up") == "She *looked up* the word."
    assert dictionary.mark_target("He runs daily.", "run") == "He *runs* daily."
    assert dictionary.mark_target("No match here.", "abate") == "No match here."


# ---------------------------------------------------------------- HTTP API

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main, "today", lambda: TODAY)

    async def fake_fetch(word, client=None):
        if word == "serendipity":
            return dictionary.normalize_api(word, API_SAMPLE), True
        if word == "offline":
            return None, False
        return None, True

    monkeypatch.setattr(dictionary, "fetch_api", fake_fetch)
    monkeypatch.setattr(main, "fetch_api", fake_fetch)
    with TestClient(main.app) as c:
        yield c


def make_student(client, name="Mina"):
    r = client.post("/api/students", json={"name": name})
    assert r.status_code == 200
    return r.json()["id"]


def test_students_are_reused_by_name(client):
    a = make_student(client, "Mina")
    b = make_student(client, "mina")
    assert a == b
    assert len(client.get("/api/students").json()) == 1


def test_dashboard_recommends_first_level(client):
    sid = make_student(client)
    d = client.get(f"/api/dashboard?student={sid}").json()
    assert d["overall"] == {"total": 240, "new": 240, "learning": 0, "mastered": 0}
    assert d["recommended"]["id"] == "L1"
    assert [w["key"] for w in d["today"]["words"]][:3] == ["borrow", "lend", "decide"]
    assert d["today"]["goal"] == 10 and d["due"] == 0 and d["streak"] == 0


def test_learning_flow_updates_progress_and_review(client):
    sid = make_student(client)
    for word in ("borrow", "lend"):
        r = client.post("/api/progress", json={"student": sid, "word": word, "action": "learning"})
        assert r.json()["status"] == "learning" and r.json()["saved"]
    r = client.post("/api/progress", json={"student": sid, "word": "decide", "action": "know"})
    assert r.json()["status"] == "mastered" and r.json()["due"] == "2026-10-31"

    d = client.get(f"/api/dashboard?student={sid}").json()
    assert d["due"] == 2 and d["streak"] == 1 and d["today"]["done"] == 3
    # Started words stay in today's list so it doesn't shift during the day.
    assert [w["key"] for w in d["today"]["words"]][:3] == ["borrow", "lend", "decide"]

    quiz = client.get(f"/api/quiz?student={sid}&mode=review").json()
    assert sorted(q["word"] for q in quiz["questions"]) == ["borrow", "lend"]

    r = client.post("/api/quiz/answer", json={"student": sid, "word": "borrow", "correct": True})
    assert r.json()["box"] == 2 and r.json()["due"] == "2026-10-20"
    r = client.post("/api/quiz/answer", json={"student": sid, "word": "lend", "correct": False})
    assert r.json()["box"] == 1 and r.json()["due"] == "2026-10-18" and r.json()["wrong"] == 1
    assert client.get(f"/api/dashboard?student={sid}").json()["due"] == 0


def test_pretest_marks_known_and_saves_missed(client):
    sid = make_student(client)
    quiz = client.get(f"/api/quiz?student={sid}&mode=pretest&level=L7&size=5").json()
    assert quiz["level"]["id"] == "L7" and len(quiz["questions"]) == 5
    assert all(q["type"] != "spell" for q in quiz["questions"])
    w1, w2 = quiz["questions"][0]["word"], quiz["questions"][1]["word"]
    assert client.post("/api/quiz/answer", json={"student": sid, "word": w1, "correct": True, "mode": "pretest"}).json()["status"] == "mastered"
    missed = client.post("/api/quiz/answer", json={"student": sid, "word": w2, "correct": False, "mode": "pretest"}).json()
    assert missed["saved"] and missed["due"] == "2026-10-18"
    level = client.get(f"/api/levels/L7?student={sid}").json()
    assert (level["mastered"], level["learning"], level["new"]) == (1, 1, 28)


def test_word_lookup_builtin_api_and_missing(client):
    sid = make_student(client)
    r = client.get(f"/api/word?q=Look%20Up&student={sid}").json()
    assert r["entry"]["source"] == "built-in" and r["key"] == "look up"
    r = client.get("/api/word?q=serendipity").json()
    assert r["entry"]["source"] == "dictionaryapi.dev"
    r = client.get("/api/word?q=borow")
    assert r.status_code == 404 and "borrow" in r.json()["detail"]["suggestions"]
    r = client.get("/api/word?q=offline")
    assert r.status_code == 503
    assert client.get("/api/word?q=offline").status_code == 503   # outages are not cached as misses
    assert client.get("/api/suggest?q=give").json()[:2] == ["give up", "give in"]


def test_import_word_smart_list(client):
    sid = make_student(client)
    text = "1. serendipity\nabate\n# comment\nzzzz | a made-up word | The *zzzz* was loud.\nabate\n"
    r = client.post("/api/levels/import", json={"title": "Word Smart 1", "text": text}).json()
    assert r["count"] == 3 and r["fetching"] == 2   # abate is built-in already
    levels = client.get(f"/api/levels?student={sid}").json()
    custom = [lv for lv in levels if lv["custom"]]
    assert custom and custom[0]["title"] == "Word Smart 1" and custom[0]["total"] == 3

    detail = client.get(f"/api/levels/{r['id']}?student={sid}").json()
    defs = {w["key"]: w["definition"] for w in detail["words"]}
    assert defs["serendipity"].startswith("A combination")      # filled by background lookup
    assert defs["zzzz"] == "a made-up word"                       # teacher's own definition
    assert defs["abate"] == "to become less strong or intense"    # built-in entry wins

    assert client.delete(f"/api/levels/{r['id']}").json()["ok"]
    assert client.delete("/api/levels/L1").status_code == 400


@pytest.mark.skipif(model_dir() is None, reason="Kokoro model files not downloaded")
def test_tts_returns_wav(client):
    r = client.get("/api/tts", params={"text": "Hello, *world*!", "voice": "af_heart", "speed": 1.0})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert r.content[:4] == b"RIFF" and len(r.content) > 10_000


# ---------------------------------------------------------------- launcher port choice

def listening(host: str) -> socket.socket:
    s = socket.socket()
    s.bind((host, 0))
    s.listen()
    return s


@pytest.mark.parametrize("occupant", ["127.0.0.1", "0.0.0.0"])
def test_claim_port_skips_a_port_in_use(occupant):
    # 0.0.0.0 is the Windows case where binding 127.0.0.1 on the same port still succeeds
    with listening(occupant) as busy:
        taken = busy.getsockname()[1]
        with launch.claim_port("127.0.0.1", taken) as sock:
            port = sock.getsockname()[1]
            assert port != taken
            assert not launch.answers("127.0.0.1", port)   # ours is bound but not serving yet


def test_claim_port_keeps_a_free_port_and_skips_unsafe_ones():
    with listening("127.0.0.1") as probe:
        free = probe.getsockname()[1]
    with launch.claim_port("127.0.0.1", free) as sock:
        assert sock.getsockname()[1] == free
    with launch.claim_port("127.0.0.1", 6000) as sock:   # browsers refuse to open port 6000
        assert sock.getsockname()[1] != 6000
