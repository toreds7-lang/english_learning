"""Build reading_deck/read_like_bert.html from build/template.html.

    uv run python reading_deck/build/build_deck.py             # full build with Kokoro audio
    uv run python reading_deck/build/build_deck.py --no-audio  # quick layout build (browser voice fallback)
    uv run python reading_deck/build/build_deck.py --check     # print the masking percentages only

The sample story is used by three slides: the [MASK] reading demo, the read-while-listening
player and the title card. Masked words are written [[word:level]]:
    level 2  -> hidden at 2 %, 5 % and 15 %
    level 5  -> hidden at 5 % and 15 %
    level 15 -> hidden at 15 % only
so the three versions are nested, like turning the difficulty up on the same page.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TEMPLATE = HERE / "template.html"
THUMB = HERE / "thumb.jpg"
OUT = HERE.parent / "read_like_bert.html"
AUDIO_DIR = HERE / "audio_cache"

VOICE = "af_heart"
SPEEDS = (1.0, 0.8)   # 1.25x is played from the 1.0 clip with playbackRate
OPUS_LEVEL = 0.95     # libsndfile compression level -> ~21 kbps speech

TITLE = "The Monday Report"
PASSAGE = [
    "Every Monday at nine, Mina had to send the weekly [[report:5]] to her [[manager:15]].",
    "This Monday, the printer on the fifth floor was [[broken:2]] again, and a long [[line:15]] of tired people [[stood:15]] in front of it.",
    "Mina did not want to [[wait:5]], so she walked down the [[stairs:2]] to the fourth floor.",
    "The office there was [[quiet:15]] and almost [[empty:5]], because most of [[the:15]] team was at a [[conference:15]] in Busan.",
    "She found a printer in the [[corner:15]], but it asked for a [[password:2]].",
    "A young man at the next desk looked up from his [[laptop:15]] and [[smiled:5]].",
    "“It’s our team’s [[name:15]], all in small letters,” he said.",
    "Mina [[typed:15]] it in, and the machine began to print without a [[sound:5]].",
    "She [[thanked:15]] him and asked which team he [[was:15]] on.",
    "“Design,” he said. “I [[started:15]] last week. You’re the first person from upstairs I’ve [[met:15]].”",
    "The next Monday, the printer upstairs was [[fixed:15]], but Mina [[still:15]] took the stairs down.",
    "This time, she brought two [[cups:15]] of [[coffee:2]].",
]

MARK = re.compile(r"\[\[([^:\]]+):(2|5|15)\]\]")
WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")


def plain(s: str) -> str:
    return MARK.sub(lambda m: m.group(1), s)


def check() -> dict:
    total = sum(len(WORD.findall(plain(s))) for s in PASSAGE)
    levels = {2: 0, 5: 0, 15: 0}
    for s in PASSAGE:
        if s.count("[[") != len(MARK.findall(s)):
            raise SystemExit(f"bad mask markup: {s}")
        for w, lv in MARK.findall(s):
            if len(WORD.findall(w)) != 1 or WORD.fullmatch(w) is None:
                raise SystemExit(f"a mask must hide exactly one word: {w!r}")
            for L in levels:
                if int(lv) <= L:
                    levels[L] += 1
    print(f"passage: {len(PASSAGE)} sentences, {total} words")
    for L, n in levels.items():
        print(f"  {L:>2}% setting: {n} masks = {n / total:.1%}")
    return {"total": total, "levels": levels}


def clip_key(voice: str, speed: float, text: str) -> str:
    return hashlib.sha1(f"{voice}|{speed}|{text}".encode("utf-8")).hexdigest()[:16]


def render_audio(rows: list) -> dict:
    sys.path.insert(0, str(ROOT))
    from app.tts import MODEL_FILE, VOICES_FILE, model_dir  # noqa: E402
    import soundfile as sf

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    jobs = []
    for r in rows:
        r["a"] = []
        for sp in SPEEDS:
            k = clip_key(VOICE, sp, r["tts"])
            r["a"].append(k)
            jobs.append((k, sp, r["tts"]))
    todo = [j for j in jobs if not (AUDIO_DIR / f"{j[0]}.ogg").exists()]
    print(f"audio: {len(jobs)} clips, {len(todo)} to render")
    if todo:
        d = model_dir()
        if d is None:
            raise SystemExit("Kokoro model not found. Run: uv run python -m app.tts --fetch")
        from kokoro_onnx import Kokoro

        kokoro = Kokoro(str(d / MODEL_FILE), str(d / VOICES_FILE))
        t0 = time.time()
        for n, (k, sp, txt) in enumerate(todo, 1):
            samples, sr = kokoro.create(txt, voice=VOICE, speed=sp, lang="en-us")
            buf = io.BytesIO()
            with sf.SoundFile(buf, "w", sr, 1, format="OGG", subtype="OPUS", compression_level=OPUS_LEVEL) as f:
                f.write(samples)
            (AUDIO_DIR / f"{k}.ogg").write_bytes(buf.getvalue())
            print(f"  {n}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
    return {k: base64.b64encode((AUDIO_DIR / f"{k}.ogg").read_bytes()).decode("ascii") for k, *_ in jobs}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    stats = check()
    if a.check:
        return
    rows = [{"s": s, "tts": plain(s), "a": ["", ""]} for s in PASSAGE]
    audio = {} if a.no_audio else render_audio(rows)
    data = {"title": TITLE, "passage": rows, "total": stats["total"]}
    html = TEMPLATE.read_text(encoding="utf-8")
    for ph in ("/*__DATA__*/", "/*__AUDIO__*/", "__THUMB__"):
        if html.count(ph) != 1:
            raise SystemExit(f"template must contain {ph} exactly once")
    dj = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = (html.replace("/*__DATA__*/", dj, 1)
                .replace("/*__AUDIO__*/", json.dumps(audio, separators=(",", ":")), 1)
                .replace("__THUMB__", base64.b64encode(THUMB.read_bytes()).decode("ascii"), 1))
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"wrote {a.out}  ({Path(a.out).stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
