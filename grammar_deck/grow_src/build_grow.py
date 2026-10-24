"""Build grammar_deck/grow_a_sentence.html (one offline file) from grow_src/.

    uv run python grammar_deck/grow_src/build_grow.py

The content lives in data1.js (Round 1-4) and data2.js (Round 5-7, boss, practice data).
To check the result, open grow_a_sentence.html?selftest in Edge or Chrome: it renders every slide and lists
missing ids, Korean mirror chunks that don't match the Korean sentence, and overflowing panes.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "grow_a_sentence.html"
JS = ["engine.js", "data1.js", "data2.js", "slides1.js", "slides2.js"]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    html = (HERE / "template.html").read_text(encoding="utf-8")
    css = (HERE / "style.css").read_text(encoding="utf-8")
    js = "\n".join((HERE / f).read_text(encoding="utf-8") for f in JS)
    if "</script" in js.lower():
        raise SystemExit("a JS source contains </script>")
    html = html.replace("/*__CSS__*/", css, 1).replace("/*__JS__*/", js, 1)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
