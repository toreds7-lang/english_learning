"""Build grammar_deck/grammar_map_101.html from content/*.py + template.html.

    uv run python grammar_deck/build/build_deck.py             # full build with Kokoro audio
    uv run python grammar_deck/build/build_deck.py --no-audio  # quick layout build (browser voice fallback)
    uv run python grammar_deck/build/build_deck.py --check     # validate content only

Example sentences use a small markup (see template.html, parseMk):
    [S The girl] [V *is*] [C happy].     role blocks, *highlight*
    [S#s He] [V is] [C=s tall]           =id : "same as" link,  >id : arrow to @id(...) or #id block
    [O that [s he] [v left]]             lower-case roles = parts of a clause inside a block
    [G that]                             omitted word: shown as "(that)", not spoken
    [S{가주어} It]                        custom label under the block
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CONTENT = HERE / "content"
TEMPLATE = HERE / "template.html"
OUT = HERE.parent / "grammar_map_101.html"
AUDIO_DIR = HERE / "audio_cache"

VOICES = ["af_heart", "am_michael", "af_bella"]  # example 1, 2, 3
SPEEDS = (1.0, 0.8)                               # normal, slow (shadowing)
OPUS_LEVEL = 0.95                                 # libsndfile compression level -> ~21 kbps speech

ROLES = {"S", "V", "O", "IO", "DO", "C", "OC", "M", "A", "X", "G"}
VIZ_TYPES = {"blocks", "morph", "compare", "table", "rows", "slots", "flow", "meter", "pair", "bars",
             "groups", "emotion", "prep", "chips", "tiles", "scale", "trend", "timeline"}
BLK = re.compile(r"([A-Za-z]+)((?:#[A-Za-z0-9]+|>[A-Za-z0-9]+|=[A-Za-z0-9]+|\{[^}]*\})*) ?")
OPT = re.compile(r"#([A-Za-z0-9]+)|>([A-Za-z0-9]+)|=([A-Za-z0-9]+)|\{([^}]*)\}")
ANC = re.compile(r"@([A-Za-z0-9]+)\(")


# ---------------------------------------------------------------- markup
def parse(s: str, strict: bool = True) -> list:
    i = 0

    def seq(end: str | None) -> list:
        nonlocal i
        out: list = []
        buf = ""
        while i < len(s):
            ch = s[i]
            if end and ch == end:
                if buf:
                    out.append({"t": "txt", "v": buf})
                i += 1
                return out
            if ch == "[":
                if buf:
                    out.append({"t": "txt", "v": buf})
                    buf = ""
                m = BLK.match(s, i + 1)
                if not m:
                    raise ValueError(f"bad block header at {i}")
                i = m.end()
                n = {"t": "blk", "role": m.group(1), "id": None, "to": [], "eq": [], "lab": None}
                for a, b, c, d in OPT.findall(m.group(2)):
                    if a:
                        n["id"] = a
                    elif b:
                        n["to"].append(b)
                    elif c:
                        n["eq"].append(c)
                    else:
                        n["lab"] = d
                if n["role"].upper() not in ROLES:
                    raise ValueError(f"unknown role {n['role']!r}")
                n["kids"] = seq("]")
                out.append(n)
                continue
            if ch == "@":
                m = ANC.match(s, i)
                if m:
                    if buf:
                        out.append({"t": "txt", "v": buf})
                        buf = ""
                    i = m.end()
                    out.append({"t": "anc", "id": m.group(1), "kids": seq(")")})
                    continue
            if ch == "]" or (strict and ch == ")"):
                raise ValueError(f"stray {ch!r} at {i}")
            buf += ch
            i += 1
        if end:
            raise ValueError(f"missing {end!r}")
        if buf:
            out.append({"t": "txt", "v": buf})
        return out

    return seq(None)


def walk(nodes):
    for n in nodes:
        yield n
        if n["t"] != "txt":
            yield from walk(n["kids"])


def check_markup(s: str, where: str, strict: bool = True) -> list:
    try:
        nodes = parse(s, strict)
    except ValueError as e:
        raise SystemExit(f"[markup] {where}: {e}\n    {s}")
    ids = {n["id"] for n in walk(nodes) if n["t"] == "blk" and n["id"]} | {n["id"] for n in walk(nodes) if n["t"] == "anc"}
    for n in walk(nodes):
        if n["t"] == "blk":
            for t in n["to"] + n["eq"]:
                if t not in ids:
                    raise SystemExit(f"[markup] {where}: link target {t!r} not found\n    {s}")
    if s.count("*") % 2:
        raise SystemExit(f"[markup] {where}: odd number of '*'\n    {s}")
    return nodes


def speech_text(nodes) -> str:
    def rec(ns):
        out = []
        for n in ns:
            if n["t"] == "txt":
                out.append(n["v"].replace("*", ""))
            elif n["t"] == "blk" and n["role"].upper() == "G":
                continue
            else:
                out.append(rec(n["kids"]))
        return "".join(out)

    t = re.sub(r"\s+", " ", rec(nodes))
    t = re.sub(r"\s+([,.;:?!])", r"\1", t).strip()
    t = re.sub(r"^[,;:]\s*", "", t)
    return t


# ---------------------------------------------------------------- content
def load(name: str):
    spec = importlib.util.spec_from_file_location(f"gm_{name}", CONTENT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def collect():
    meta = load("meta")
    parts, chapters = [], []
    for k in range(1, 6):
        if not (CONTENT / f"part{k}.py").exists():
            print(f"[warn] part{k}.py missing — skipped")
            continue
        mod = load(f"part{k}")
        p = dict(mod.PART)
        parts.append(p)
        for c in mod.CHAPTERS:
            c = dict(c)
            c["part"] = p["id"]
            chapters.append(c)
    return parts, chapters, meta.THREADS


def viz_markups(v, where):
    """Yield (markup, where) for every sentence inside a viz spec and validate its shape."""
    if v is None:
        return
    if isinstance(v, list):
        for j, x in enumerate(v):
            yield from viz_markups(x, f"{where}[{j}]")
        return
    t = v.get("t")
    if t not in VIZ_TYPES:
        raise SystemExit(f"[viz] {where}: unknown type {t!r}")
    if t == "blocks":
        yield v["s"], where
    elif t == "morph":
        for j, st in enumerate(v["steps"]):
            yield st[0], f"{where}.step{j}"
    elif t == "compare":
        for j, c in enumerate(v["cards"]):
            if c.get("s"):
                yield c["s"], f"{where}.card{j}"
    elif t == "rows":
        for j, r in enumerate(v["rows"]):
            yield r[1], f"{where}.row{j}"
    elif t == "table":
        for r in v["rows"]:
            if len(r) != len(v["head"]):
                raise SystemExit(f"[viz] {where}: row width {len(r)} != head {len(v['head'])}: {r}")
            for c in r:
                if isinstance(c, str) and "[" in c:
                    yield c, f"{where}.cell"
    elif t == "flow":
        def fl(node, w):
            if "a" in node:
                if node.get("s"):
                    yield node["s"], w
                return
            yield from fl(node["yes"], w + ".y")
            yield from fl(node["no"], w + ".n")
        yield from fl(v, where)


def viz_refs(v):
    if v is None:
        return
    if isinstance(v, list):
        for x in v:
            yield from viz_refs(x)
        return
    t = v["t"]
    if t == "rows":
        for r in v["rows"]:
            if len(r) > 3 and r[3]:
                yield r[3]
    elif t == "slots":
        for s in v["slots"]:
            for f in s.get("fill", []):
                if isinstance(f, (list, tuple)) and len(f) > 1 and f[1]:
                    yield f[1]
    elif t in ("tiles",):
        for x in v["tiles"]:
            if len(x) > 2 and x[2]:
                yield x[2]
    elif t == "prep":
        for x in v["items"]:
            if len(x) > 2 and x[2]:
                yield x[2]


def build_data():
    parts, chapters, threads = collect()
    ids: dict[str, str] = {}
    for p in parts:
        ids[p["id"]] = "part"
    unit_nos, fs_no = [], 0
    items_all = []
    for c in chapters:
        ids[c["id"]] = "chapter"
        for it in c["items"]:
            if it["id"] in ids:
                raise SystemExit(f"duplicate id {it['id']}")
            ids[it["id"]] = "item"
            items_all.append((c, it))
    ids.update({"map": "x", "threads": "x", "board": "x", "title": "x", "howto": "x"})
    partial = len(parts) < 5

    def ref_ok(r, where):
        if r in ids:
            return True
        if partial:
            return False
        raise SystemExit(f"{where}: reference to unknown id {r!r}")

    sentences = []  # (item_id, idx, text)
    out_ch = []
    for c in chapters:
        items = []
        for it in c["items"]:
            iid = it["id"]
            kind = "fs" if iid.startswith("FS") else "unit"
            row = {
                "id": iid, "kind": kind, "title": it["title"], "sub": it.get("sub", ""),
                "pts": it.get("pts", []), "f": it.get("f", ""), "viz": it.get("viz"),
                "links": it.get("ln", []), "tip": it.get("tip"), "drill": it.get("drill", 0),
            }
            if kind == "unit":
                row["no"] = int(iid[1:])
                unit_nos.append(row["no"])
            else:
                fs_no += 1
                row["fsno"] = int(iid[2:])
                if row["fsno"] != fs_no:
                    raise SystemExit(f"{iid}: Further Study numbering out of order (expected FS{fs_no:02d})")
            exs = []
            if len(it["ex"]) < 2:
                raise SystemExit(f"{iid}: needs at least 2 examples")
            for j, (s, ko) in enumerate(it["ex"]):
                nodes = check_markup(s, f"{iid}.ex{j}")
                if ko.count("*") % 2:
                    raise SystemExit(f"[ko] {iid}.ex{j}: odd '*' in translation")
                txt = speech_text(nodes)
                exs.append({"s": s, "ko": ko, "tts": txt, "a": ["", ""]})
                sentences.append((iid, j, txt))
            row["ex"] = exs
            chk = it.get("chk") or []
            if not chk:
                raise SystemExit(f"{iid}: missing quick check")
            for q in chk:
                if not (0 <= q["a"] < len(q["o"])):
                    raise SystemExit(f"{iid}: check answer index out of range")
                if q.get("s"):
                    check_markup(q["s"], f"{iid}.chk", strict=False)
            row["chk"] = chk
            for m, w in viz_markups(row["viz"], f"{iid}.viz"):
                check_markup(m, w)
            for r in viz_refs(row["viz"]):
                ref_ok(r, iid)
            row["links"] = [r for r in row["links"] if ref_ok(r, iid)]
            if not (0 <= row["drill"] < len(exs)):
                raise SystemExit(f"{iid}: drill index out of range")
            items.append(row)
        cc = {k: c.get(k) for k in ("id", "no", "title", "big", "pts", "viz", "part")}
        cc["items"] = items
        for m, w in viz_markups(cc["viz"], f"{c['id']}.viz"):
            check_markup(m, w)
        for r in viz_refs(cc["viz"]):
            ref_ok(r, c["id"])
        out_ch.append(cc)
    for p in parts:
        for m, w in viz_markups(p.get("viz"), f"{p['id']}.viz"):
            check_markup(m, w)
        for r in viz_refs(p.get("viz")):
            ref_ok(r, p["id"])
    if sorted(unit_nos) != list(range(1, len(unit_nos) + 1)):
        missing = sorted(set(range(1, 102)) - set(unit_nos))
        print(f"[warn] unit numbers not contiguous; missing: {missing}")
    for t in threads:
        missing = [u for u in t["units"] if u not in ids]
        if missing and len(parts) == 5:
            raise SystemExit(f"thread {t['id']}: unknown units {missing}")
        t["units"] = [u for u in t["units"] if u in ids]
    data = {"parts": parts, "chapters": out_ch, "threads": threads}
    return data, sentences


# ---------------------------------------------------------------- audio
def clip_key(voice: str, speed: float, text: str) -> str:
    return hashlib.sha1(f"{voice}|{speed}|{text}".encode("utf-8")).hexdigest()[:16]


def render_audio(data, sentences) -> dict:
    sys.path.insert(0, str(ROOT))
    from app.tts import MODEL_FILE, VOICES_FILE, model_dir  # noqa: E402
    import soundfile as sf

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    jobs = []
    by_item = {it["id"]: it for c in data["chapters"] for it in c["items"]}
    for iid, j, txt in sentences:
        voice = VOICES[j % len(VOICES)]
        keys = []
        for sp in SPEEDS:
            k = clip_key(voice, sp, txt)
            keys.append(k)
            jobs.append((k, voice, sp, txt))
        by_item[iid]["ex"][j]["a"] = keys
    todo = [j for j in jobs if not (AUDIO_DIR / f"{j[0]}.ogg").exists()]
    print(f"audio: {len(jobs)} clips, {len(todo)} to render")
    if todo:
        d = model_dir()
        if d is None:
            raise SystemExit("Kokoro model not found. Run: uv run python -m app.tts --fetch")
        from kokoro_onnx import Kokoro

        kokoro = Kokoro(str(d / MODEL_FILE), str(d / VOICES_FILE))
        t0 = time.time()
        for n, (k, voice, sp, txt) in enumerate(todo, 1):
            samples, sr = kokoro.create(txt, voice=voice, speed=sp, lang="en-us")
            buf = io.BytesIO()
            with sf.SoundFile(buf, "w", sr, 1, format="OGG", subtype="OPUS", compression_level=OPUS_LEVEL) as f:
                f.write(samples)
            (AUDIO_DIR / f"{k}.ogg").write_bytes(buf.getvalue())
            if n % 25 == 0 or n == len(todo):
                el = time.time() - t0
                print(f"  {n}/{len(todo)}  {el:.0f}s elapsed, ~{el / n * (len(todo) - n):.0f}s left", flush=True)
    audio = {}
    for k, *_ in jobs:
        audio[k] = base64.b64encode((AUDIO_DIR / f"{k}.ogg").read_bytes()).decode("ascii")
    return audio


# ---------------------------------------------------------------- main
def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    data, sentences = build_data()
    n_items = sum(len(c["items"]) for c in data["chapters"])
    print(f"content ok: {len(data['parts'])} parts, {len(data['chapters'])} chapters, {n_items} items, {len(sentences)} example sentences")
    if a.check:
        return
    audio = {} if a.no_audio else render_audio(data, sentences)
    html = TEMPLATE.read_text(encoding="utf-8")
    dj = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    aj = json.dumps(audio, separators=(",", ":"))
    html = html.replace("/*__DATA__*/", dj, 1).replace("/*__AUDIO__*/", aj, 1)
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"wrote {a.out}  ({Path(a.out).stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
