# BERT처럼 영어책 읽기 (reading deck)

`read_like_bert.html` is an 18-slide lecture for Korean coworkers on how to read English books.
It follows five rules, and each rule borrows one idea from the BERT paper:
choose the right book (but with about 2% unknown words, not BERT's 15%), don't translate,
don't stop for every word, guess from both sides (bidirectional + attention), and read at least twice (epochs).
Rule 2 uses Speak English With Tiffani's "STOP TRANSLATING!" video (noD9L_9hXU4).

## Opening it

- **Company PC:** double-click `read_like_bert.html` in Edge or Chrome. It is one offline file: no internet, CDN or server needed, and the Kokoro audio is built in.
  The video can't play from a file, so the time chips show what Tiffani says at that moment instead.
- **Home:** double-click `start_deck.bat`. It serves the folder on `http://localhost` so the YouTube video can play inside the slides.

Keys: ← → move, `F` full screen, `T` dark mode, `Home` first slide. Add `#7` to the address to open slide 7.

## The four tools

| Slide | Tool | What it does |
|---|---|---|
| 7 | 페이지 테스트 | Paste a page of your book, click the words you don't know. It shows the known-word percentage and says easy / just right (98–99%) / challenge (95–97%) / too hard. |
| 9 | 덩어리 읽기 | Four office sentences cut into chunks. Korean "training wheels" in English order, step through, a pacer (100/150/200 wpm), and a "거꾸로 해석" replay that shows how the eye jumps when you translate from the end. |
| 12 | [MASK] 읽기 | The story "The Monday Report" with 2.4%, 5.3% or 15.3% of the words hidden. Click a mask to check it and score your guesses. |
| 14 | 듣면서 읽기 | The same story read by Kokoro (af_heart) sentence by sentence, at 0.8×, 1.0× or 1.25×. You can hide the text and underline the words that were masked at 5%. |

## Rebuilding after you edit

The slides are in `build/template.html`. The story and its masks are in `build/build_deck.py` (`PASSAGE`):
`[[word:2]]` is hidden at 2%, 5% and 15%; `[[word:5]]` at 5% and 15%; `[[word:15]]` at 15% only.

```powershell
uv run python reading_deck/build/build_deck.py --check      # print the masking percentages
uv run python reading_deck/build/build_deck.py --no-audio   # fast build; uses the browser voice
uv run python reading_deck/build/build_deck.py              # full build with Kokoro audio
```

Audio clips are cached in `build/audio_cache/` (Opus, about 21 kbps), so only changed sentences are rendered again.
`build/thumb.jpg` is the video thumbnail that the slides show before the video plays.
The story and the example sentences were written for this deck.
