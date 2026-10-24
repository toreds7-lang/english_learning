# 영어는 왜 쓰인 대로 읽히지 않을까 (history-of-English deck)

`why_english_spelling.html` is a 27-slide lecture for Korean coworkers. It explains, through the history of English,
why English spelling, pronunciation, vocabulary and grammar are hard for people who read Hangul, and what to do about it.
Part 1 (slides 1–16) is the history; part 2 (slides 17–27) turns each difficulty into a study method and a hands-on tool.

Reference videos (chips on the slides jump to the moment, or show the line when offline):
RobWords, *The entire history of English in 22 minutes* (0gHE9blt0mQ) · English with Nab, *The history of the English language* (tsvOWRlu7_s) ·
engVid Gill, *Discover the History of English* (aEH2GkuRIHs) · Fortress of Lugh, *Origins of the English* (Nf7GTlhve98).
The Fortress of Lugh video is about the English *people* (migration, genetics). Only its language-related moments are used, and its genetics reading is labelled as the video's own view.

## Opening it

- **Company PC:** double-click `why_english_spelling.html` in Edge or Chrome. It is one offline file (no internet, CDN or server; the Kokoro audio is built in).
  Videos can't play from a file, so the time chips show what the speaker says at that moment.
- **Home:** double-click `start_deck.bat`. It serves this folder on `http://localhost` so the YouTube videos play inside the slides.
  Links to the other decks work only when the deck is opened as a file.

Keys: ← → move, `F` full screen, `T` dark mode, `Home` first slide. Add `#12` to the address to open slide 12.

## Slides

| # | Slide | # | Slide |
|---|---|---|---|
| 1 | Title · *knight* letter fossils | 15 | Modern English (dictionaries, world words, OED Korean words) |
| 2 | Warm-up: Hangul vs. *ough* ×7 | 16 | Part 1 summary: which era made which difficulty |
| 3 | Hangul was designed, English spelling accumulated | 17 | Spelling: 7 reasons + spelling keeps meaning |
| 4 | 1,500-year timeline (click a band to jump) | 18 | **Tool ② Spelling detective** |
| 5 | Roots: PIE → Germanic, Grimm's-law word pairs | 19 | Pronunciation: 4 reasons it is hard for Koreans |
| 6 | Old English (+ reconstructed Lord's Prayer) | 20 | Stress decides the vowel |
| 7 | Old English grammar = Korean particles | 21 | **Tool ③ Spelling-to-sound drill** |
| 8 | Vikings / Old Norse | 22 | Vocabulary: 3 layers ↔ 고유어/한자어, origin chart, top 40 |
| 9 | 1066 Norman Conquest + scribes' spellings | 23 | **Tool ④ Word-layer game** |
| 10 | Middle English (+ reconstructed Chaucer) | 24 | Grammar: from particles to positions |
| 11 | 1476 printing press | 25 | 8 study methods the history suggests |
| 12 | Great Vowel Shift (vowel chart) | 26 | 5-step word routine, 4-week plan, daily checklist |
| 13 | **Tool ① Sound time machine** (1400 vs. now) | 27 | One-page summary, honesty notes, sources |
| 14 | Renaissance & Early Modern (Latin flood, respellings, *do*) | | |

## Rebuilding after you edit

Sources are in `build/`:

| File | What it holds |
|---|---|
| `template.html` | styles, slides 1–8, bottom bar, placeholders |
| `part_history.html` | slides 9–16 (inserted at `<!--__PART2__-->`) |
| `part_learn.html` | slides 17–27 |
| `deck.js` | slide engine, players, the four tools, `?selftest` |
| `content.py` | videos, time-machine words, detective words, layer-game words, drill sets, every audio clip |
| `thumbs/` | the four video thumbnails (inlined as base64) |

```powershell
uv run python history_deck/build/build_deck.py --check      # validate audio keys, video chips, tool data
uv run python history_deck/build/build_deck.py --no-audio   # fast build; uses the browser voice
uv run python history_deck/build/build_deck.py              # full build with Kokoro audio (~85 s first time)
```

The check fails if a `data-say` key has no clip, a chip names an unknown video or a time past its end, or a detective word's parts don't spell the word.
Audio clips are cached in `build/audio_cache/` (Ogg Opus, ~21 kbps). Old and Middle English clips are Kokoro (`am_michael`) reading reconstructed IPA
with `is_phonemes=True`, so they are approximations; Kokoro writes the stress mark right before the stressed vowel (`tˈiːm`), and `g` must be `ɡ`.
Open the built file with `?selftest` to visit every slide; it writes overflow / off-screen / missing-audio results to `document.body.dataset.selftest`.
