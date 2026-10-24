"""Build history_deck/why_english_spelling.html from build/template.html + deck.js + content.py.

    uv run python history_deck/build/build_deck.py             # full build with Kokoro audio
    uv run python history_deck/build/build_deck.py --no-audio  # quick layout build (browser voice fallback)
    uv run python history_deck/build/build_deck.py --check     # validate the slides only

Checks before writing:
  * every data-say="key" in the template is a known audio clip
  * every video chip (data-v + data-t) names a known video and a time inside it
Audio clips are cached in build/audio_cache/ (Ogg Opus ~21 kbps), keyed by voice, speed and text/phonemes.
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
sys.path.insert(0, str(HERE))
import content as C  # noqa: E402

TEMPLATE = HERE / "template.html"          # slides 1-8 + styles + chrome
PARTS = ("part_history.html", "part_learn.html")   # slides 9-16, 17-27 (inserted at <!--__PART2__-->)
JS = HERE / "deck.js"
THUMBS = HERE / "thumbs"
AUDIO_DIR = HERE / "audio_cache"
OUT = HERE.parent / "why_english_spelling.html"

OPUS_LEVEL = 0.95     # libsndfile compression level -> ~21 kbps speech
WORD_SPEED = 0.9


def secs(t: str) -> int:
    n = 0
    for part in t.split(":"):
        n = n * 60 + int(part)
    return n


def audio_items() -> dict:
    """key -> {text|ph, voice, speed}"""
    items: dict[str, dict] = {}

    def word(w: str) -> dict:
        if w in C.PH_OVERRIDE:
            return {"ph": C.PH_OVERRIDE[w], "voice": C.V_NOW, "speed": WORD_SPEED}
        return {"text": w, "voice": C.V_NOW, "speed": WORD_SPEED}

    for r in C.TIME_MACHINE:
        items[f"tm-{r['w']}-me"] = {"ph": r["me"][0], "voice": C.V_OLD, "speed": 0.85}
        items[f"tm-{r['w']}-now"] = {"ph": r["now"][0], "voice": C.V_OLD, "speed": 0.85}
    for r in C.DETECTIVE:
        items[f"w-{r['w']}"] = word(r["w"])
    for s in C.SOUND_SETS:
        for w, *_ in s["items"]:
            items[f"w-{w}"] = word(w)
    for s in C.STRESS_SETS:
        for w, *_ in s["items"]:
            items[f"w-{w}"] = word(w)
    for k, v in C.SLIDE_AUDIO.items():
        if k in C.PH_OVERRIDE.keys():
            raise SystemExit(f"slide audio key collides with a word: {k}")
        it = dict(v)
        if "text" in it and it["text"] in C.PH_OVERRIDE:
            it = {"ph": C.PH_OVERRIDE[it.pop("text")]}
        it.setdefault("voice", C.V_NOW)
        it.setdefault("speed", WORD_SPEED)
        items[k] = it
    return items


def check_template(html: str, items: dict) -> None:
    bad = sorted(set(re.findall(r'data-say="([^"]+)"', html)) - set(items))
    if bad:
        raise SystemExit(f"unknown data-say keys: {bad}")
    chips = re.findall(r'<button[^>]*\bdata-v="([^"]+)"[^>]*\bdata-t="([^"]+)"', html)
    for v, t in chips:
        if v not in C.VIDEOS:
            raise SystemExit(f"unknown video key in chip: {v}")
        if secs(t) >= secs(C.VIDEOS[v]["len"]):
            raise SystemExit(f"chip time {t} is past the end of {v} ({C.VIDEOS[v]['len']})")
    bad_q = re.findall(r'<button[^>]*\bdata-v="[^"]+"(?![^>]*\bdata-q=)[^>]*>', html)
    if bad_q:
        raise SystemExit(f"chip without data-q: {bad_q[0][:120]}")
    slides = html.count('<section class="slide')
    says = set(re.findall(r'data-say="([^"]+)"', html))
    print(f"template: {slides} slides, {len(chips)} video chips, {len(says)} audio buttons")


def clip_key(it: dict) -> str:
    body = ("ph:" + it["ph"]) if "ph" in it else ("tx:" + it["text"])
    return hashlib.sha1(f"{it['voice']}|{it['speed']}|{body}".encode("utf-8")).hexdigest()[:16]


def render_audio(items: dict) -> dict:
    from app.tts import MODEL_FILE, VOICES_FILE, model_dir  # noqa: E402
    import soundfile as sf

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    keyed = {k: clip_key(it) for k, it in items.items()}
    todo = [k for k in items if not (AUDIO_DIR / f"{keyed[k]}.ogg").exists()]
    print(f"audio: {len(items)} clips, {len(todo)} to render")
    if todo:
        d = model_dir()
        if d is None:
            raise SystemExit("Kokoro model not found. Run: uv run python -m app.tts --fetch")
        from kokoro_onnx import Kokoro

        kokoro = Kokoro(str(d / MODEL_FILE), str(d / VOICES_FILE))
        t0 = time.time()
        for n, k in enumerate(todo, 1):
            it = items[k]
            if "ph" in it:
                samples, sr = kokoro.create(it["ph"], voice=it["voice"], speed=it["speed"], is_phonemes=True)
            else:
                samples, sr = kokoro.create(it["text"], voice=it["voice"], speed=it["speed"], lang="en-us")
            buf = io.BytesIO()
            with sf.SoundFile(buf, "w", sr, 1, format="OGG", subtype="OPUS", compression_level=OPUS_LEVEL) as f:
                f.write(samples)
            (AUDIO_DIR / f"{keyed[k]}.ogg").write_bytes(buf.getvalue())
            if n % 10 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
    return {k: base64.b64encode((AUDIO_DIR / f"{keyed[k]}.ogg").read_bytes()).decode("ascii") for k in items}


def deck_data(items: dict) -> dict:
    videos = {}
    for k, v in C.VIDEOS.items():
        thumb = THUMBS / f"{v['id']}.jpg"
        videos[k] = {**v, "thumb": "data:image/jpeg;base64," + base64.b64encode(thumb.read_bytes()).decode("ascii")}
    tm = [{"w": r["w"], "grp": r["grp"], "note": r["note"],
           "me": {"ipa": r["me"][1], "ko": r["me"][2]}, "now": {"ipa": r["now"][1], "ko": r["now"][2]}}
          for r in C.TIME_MACHINE]
    sound = [{"id": s["id"], "title": s["title"], "opts": s["opts"], "rule": s["rule"],
              "items": [{"w": w, "hl": hl, "ans": a, "note": n} for w, hl, a, n in s["items"]]}
             for s in C.SOUND_SETS]
    stress = [{"id": s["id"], "title": s["title"], "rule": s["rule"],
               "items": [{"w": w, "syl": syl, "ans": a, "ipa": ipa} for w, syl, a, ipa in s["items"]]}
              for s in C.STRESS_SETS]
    for s in C.STRESS_SETS:
        for w, syl, a, _ in s["items"]:
            if not 0 <= a < len(syl):
                raise SystemExit(f"stress index out of range: {w}")
    for s in C.SOUND_SETS:
        for w, hl, a, _ in s["items"]:
            if not 0 <= a < len(s["opts"]):
                raise SystemExit(f"answer index out of range: {w}")
    for r in C.DETECTIVE:
        if "".join(p["t"] for p in r["parts"]) != r["w"]:
            raise SystemExit(f"detective parts do not spell the word: {r['w']}")
    return {"videos": videos, "tm": tm, "det": C.DETECTIVE, "layers": C.LAYERS,
            "sound": sound, "stress": stress,
            "tts": {k: it.get("text", "") for k, it in items.items()}}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    html = TEMPLATE.read_text(encoding="utf-8")
    if html.count("<!--__PART2__-->") != 1:
        raise SystemExit("template must contain <!--__PART2__--> exactly once")
    parts = "".join((HERE / p).read_text(encoding="utf-8") for p in PARTS)
    html = html.replace("<!--__PART2__-->", parts, 1)
    items = audio_items()
    check_template(html, items)
    data = deck_data(items)
    if a.check:
        return
    sys.path.insert(0, str(ROOT))
    audio = {} if a.no_audio else render_audio(items)

    for ph in ("/*__JS__*/", "/*__DATA__*/", "/*__AUDIO__*/"):
        if html.count(ph) != 1:
            raise SystemExit(f"template must contain {ph} exactly once")
    js = JS.read_text(encoding="utf-8")
    if "</script" in js:
        raise SystemExit("deck.js must not contain </script")
    dj = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = (html.replace("/*__JS__*/", js, 1)
                .replace("/*__DATA__*/", dj, 1)
                .replace("/*__AUDIO__*/", json.dumps(audio, separators=(",", ":")), 1))
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"wrote {a.out}  ({Path(a.out).stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
