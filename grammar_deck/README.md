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

---

# 문장이 자란다 (`grow_a_sentence.html`)

A 57-slide offline deck on English word order for Korean coworkers. It starts from **"I am a student."** and grows the sentence one piece at a time through 45 steps, ending with
*"I don't think my coworkers who have studied with me for a year will stop now."* Double-click the file to open it in Edge or Chrome. It needs no internet or server.

It teaches two ideas plus one suggested tool:
① **The subject and verb are bound together.** The verb changes form to match its subject (I am / She is), much as in self-attention. The object completes the verb's meaning.
② **Intent and frame come first.** The first word shows the intent (Do · Did · What · I don't think…), while long content goes to the end (end-weight).
＋ **2번 자리 (operator seat).** The slot right after the subject: will · can · have · be · do go there, not attaches after it, it jumps ahead of the subject for questions and inversion, and when it is empty, do fills it.

| Slides | What they are |
|---|---|
| 1–6 | Cover (the sentence grows on its own), Korean ↔ English mirror, principle ① (attention heatmap), principle ②, the 2nd-seat machine + seat grid, staircase map |
| 7–51 | Steps 1–45 in 7 rounds + boss. Each step animates from its previous sentence (new piece pops in, moved pieces slide, changed words flash). It shows attention arcs above, the Korean mirror with crossing lines below, "왜 이 자리?", English-order thinking, and links to the matching unit in `grammar_map_101.html` |
| 52–54 | Practice: ① subject switch (which words react to the subject?) ② intent-first question maker (5 statements × yes/no · wh · subject questions, optional "say it first" mode) ③ grow-the-sentence drill (Korean meaning → order the blocks; NEW marks the added piece) |
| 55–57 | One-page summary, honest notes (where the analogy holds and where it breaks, with references), ideas for running the study group |

Keys: ← → / Space move, `R` replay the morph, `A` arcs, `K` Korean mirror, `L` role labels, `M` map, `D` drill this step, `N` next boss layer, `T` theme, `F` full screen. Type a step number (1–45) in the box.
🔊 uses the browser's own voice; no audio is embedded.

## Editing

The sentences are in `grow_src/data1.js` (Rounds 1–4) and `grow_src/data2.js` (Rounds 5–7, boss, switch/question data).
Each step uses the block markup (`[S#s I] [V#v am] [C#c a student].`), Korean mirror chunks (`km: '나는|s; 학생|c; 이다.|v'`) and arcs (`arcs: 's-v 3 일치; v-c 1 ='`).
Keep the same `#id` for a word from one step to the next so the morph can track it.

```powershell
uv run python grammar_deck/grow_src/build_grow.py            # build grow_a_sentence.html
```
To check the deck, open `grow_a_sentence.html?selftest`. It renders every slide and lists missing ids, Korean chunks that don't match the Korean sentence, and overflowing panes.
