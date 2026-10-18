# 영어 구문 지도 101 (grammar deck)

`grammar_map_101.html` is one offline slide deck that follows the grammar book's table of contents
(`../문법/문법1–6.png`): 5 Parts, 16 Chapters, 101 Units and 15 Further Study items, 142 slides in all.
Double-click it, or open it in Edge or Chrome. It needs no internet connection or server, and the Kokoro audio is built into the file.

## What is on each slide

- **Colour blocks.** Every example is split into S · V · O · C · M (+ I.O. / D.O. / O.C. / A) blocks.
  Lower-case labels mark the parts of a clause inside a block. An arrow means "modifies"; `=` means "same thing" (S = C, O = O.C.).
- **A picture for each unit.** These include step-by-step change animations (press 「다음 단계 ▶」 or `N`), timelines, certainty meters, flowcharts and comparison cards.
- **Connections.** The 구문 지도 (metro map) has 9 thread buttons. Each Unit and Chapter slide has 🧵 thread badges and ← / → link chips.
- **Practice.** ✎ 확인 문제 (one quick question), 🧩 문장 만들기 (put the blocks in order), and 🎧 섀도잉 (slow → repeat → normal → repeat).
  ✓ 이해했어요 / ↻ 복습 colours the map and the 📊 진도판. Progress is saved in that browser only.

Keys: ← → move, `M` map, `T` table of contents, `K` show all translations, `1` `2` `3` play an example (Shift = slow),
`S` shadowing, `Q` quick check, `B` block drill, `G` / `R` mark progress. Type a unit number in the box (e.g. `41`) and press Enter.

## Rebuilding after you edit the content

The content lives in `build/content/part1.py` … `part5.py` (Korean explanations, examples, visuals and quick checks)
and `build/content/meta.py` (the 9 threads). The page layout and code are in `build/template.html`.

```powershell
uv run python grammar_deck/build/build_deck.py --check      # check the markup only
uv run python grammar_deck/build/build_deck.py --no-audio   # fast build; uses the browser voice
uv run python grammar_deck/build/build_deck.py              # full build with Kokoro audio
```

Audio clips are cached in `build/audio_cache/` (Opus, about 21 kbps). Only new or changed sentences are rendered again.
The voices rotate by example: example 1 af_heart, example 2 am_michael, example 3 af_bella. Each example is rendered at 1.0× and 0.8× speed.
The example sentences are written for this deck and are not copied from the book.
