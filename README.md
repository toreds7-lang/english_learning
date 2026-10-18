# WordStep — English dictionary, vocabulary trainer, grammar and leveled reading

A FastAPI + HTML app for English learners: learner-friendly dictionary entries with IPA,
examples and usage tips; Kokoro text-to-speech for every word, definition and example;
step-by-step word levels up to advanced (Word Smart–style) vocabulary; saved words with
spaced-repetition review; daily quizzes and pretests; grammar for real life with practice and
review; a progress status bar; and a reading library that picks books at each student's level
and feeds new words into their review.

## Run

**One click (Windows):** double-click `run.bat`. It installs the Python packages, downloads
the Kokoro model on the first run, starts the server and opens the browser. It uses port
8000, or the next free port if 8000 is taken (it checks for other servers on 127.0.0.1,
0.0.0.0 and [::1] as well as for reserved ports), and prints the address it chose.
Options: `run.bat --host 0.0.0.0` for other devices on the network, `--port 9000` to
start the search at another port, `--no-browser` to skip opening the browser.

By hand:

```powershell
uv sync                                  # install dependencies (Python 3.11–3.13)
uv run python -m app.tts --fetch         # one-time: download Kokoro model (~340 MB) into models/kokoro/
uv run uvicorn app.main:app --port 8000  # then open http://127.0.0.1:8000
```

Add `--host 0.0.0.0` to let students on the same network open it from their own devices.
Without the Kokoro model the app still works and falls back to the browser's built-in voice.

**Reading library:** open **Settings → Reading library** and press *Download* for the
storybooks (about 10 s) and the classics (one time, 2–10 minutes depending on the Gutenberg
mirror's speed). Or from the command line:
`uv run python -m app.sources` (both) or `uv run python -m app.sources storybooks`.

## How students use it

| Page | What it does |
|---|---|
| **Home** | Today's new words (daily goal), words due for review, a pretest for the next level, and the level path. |
| **Learn** | 8 levels in order. The first level that is under 80% covered is marked *Next step*. |
| **Flashcards** | Word + pronunciation first; the student recalls the meaning, then reveals it and answers *I knew it* or *Still learning*. |
| **Search** | Any word. Curriculum words use the built-in entries (offline); other words come from [dictionaryapi.dev](https://dictionaryapi.dev). |
| **My Words** | Saved words with their status and next review date. ☆ saves any word. |
| **Quiz** | *Today's review* (due words) or a *Pretest* for a level. |
| **Library** | Books for the student's level, grouped as *Just right*, *A little challenge* and *Easy*, plus *Continue reading*. |
| **Reader** | Tap any word for its meaning, pronunciation and ☆ save; words being learned are highlighted; read-aloud with Kokoro; finish with a rating and a masked-word check. |
| **Level test** | About 65 yes/no words (with made-up words to catch guessing). Sets the reading level and suggests where to start in the word steps. |
| **Reading progress** | Level and its history, minutes per day, recent reading, and reading settings (age group, comfort, daily minutes). |
| **Grammar** | 25 short lessons (A1–B2) named by what you do with them ("Tell what happened"), each with examples, common mistakes, sentences from the library, a real-life writing mission and an 8-question practice. Grammar points come back for review like words. |
| **AI story** | Optional: Claude writes a story at the student's level that uses the words they are learning, and optionally a grammar point. |
| **Status bar** | Mastered / learning / new across all levels, day streak, today's goal, words due, minutes read today, and grammar points due. |

### Levels (30 words each, 240 in total)

1. Everyday Basics (A1–A2)
2. Daily Life & Feelings (A2–B1)
3. Phrasal Verbs I — two-word, everyday (A2–B1)
4. Intermediate Core (B1–B2)
5. Phrasal Verbs II — two-word, idiomatic (B1–B2)
6. Academic Words (B2–C1)
7. Advanced I — Word Smart–style, SAT level (C1)
8. Advanced II — Word Smart–style, GRE level (C1–C2)

Every entry has US IPA, a simple English definition, two examples with the target word
highlighted, similar words, and a usage tip. The definitions and examples are original;
Word Smart's own content is not included (it is copyrighted).

### Adding Word Smart 1 / 2 (or any list)

In **Settings → Import a word list**, paste one word per line from your own copy. Numbering
like `1. abate` is ignored. Plain words get their definition, IPA and examples from the
online dictionary in the background. To use your own notes instead, write:

```
abate | to become less intense | The storm finally abated.
```

Imported lists show up as extra levels after Advanced II. They are shared by all students.

## The learning method

- **Spaced repetition (Leitner boxes).** A correct answer moves a word up a box. Boxes 1–5
  come back after 1, 3, 7, 14 and 30 days. A wrong answer sends the word back to box 1 for
  tomorrow. Words in box 4 or 5 count as *mastered*.
- **Active recall before reading.** Flashcards show the word and pronunciation first; the
  meaning is hidden until the student has tried to recall it.
- **Pretests skip known words.** A correct pretest answer marks the word as known (it is
  checked once more after 2 weeks). A missed word is saved for review the next day.
- **Mixed question types.** Review quizzes rotate four types: meaning → word,
  word → meaning, fill-in-the-blank from an example sentence, and listen-and-spell (Kokoro).
  A missed review question is asked again at the end, but only the first answer counts.

## Grammar for real life

Each grammar point is organized by what you **do** with it, not by its exam name: *Tell what
happened* (past simple), *Ask politely* (could you…?), *Say how long* (for / since). The lessons
are short on purpose: when you use it, how it is formed (3–4 lines), examples, and the mistakes
learners really make. There are 25 points from A1 to B2, in six groups: *Me and my world*,
*Stories and experiences*, *Plans and possibilities*, *Ask, advise and guess*, *Describe and
compare*, and *Imagine, report and connect*.

- **Practice in five question types.** *Which one fits?* (choose the sentence for a real
  situation — meaning, not just form), *fill the gap*, *tap the mistake*, *put the words in
  order*, and *listen and write* (Kokoro reads an example; every word of the grammar part must be
  right, and 80% of all words; typing "I am" for "I'm" is fine). Every answer explains why.
- **Spaced review.** A session gives each point a score. 80% or more moves it up a Leitner box
  (back after 1, 3, 7, 14, 30 days); under 50% sends it back to box 1; in between, it comes back
  tomorrow. Extra practice of a point that is not due doesn't skip the spacing. Review mixes the
  due points (interleaved, which helps learners choose the right form) and asks the questions
  missed last time first.
- **Grammar in your books (noticing).** Pattern detectors in `app/grammar.py` find each point in
  real text. A lesson shows sentences from library texts that fit the student's level, and the
  reader has a *Grammar* menu that highlights one point in the text (with how many times it is
  used). The detectors favour precision over recall: they miss some uses, but what they mark is
  almost always right.
- **Use it for real.** Each point ends with a mission about the student's own life ("Write three
  things you have done and two you have never done"). The sentences are saved on the lesson
  page; with a Claude API key, Claude checks them and gives one kind, simple tip.
- **AI stories with a grammar focus.** The story maker can build a story around one point, which
  then opens in the reader with that point highlighted.

To change the lessons, edit `app/data/grammar.json`. Mark the grammar part of examples with
`*asterisks*`; in a *gap* question the marked text is the answer, in a *fix* question it is the
mistake. `tests/test_grammar.py` checks the format and that each point's detector finds its own
examples.

## Reading: how the level is matched

The idea is the same as BERT's masking rate, applied to people: what decides whether a text
helps a reader is the share of running words they don't know. Reading research puts
comfortable independent reading at about **98% known words** (2 new words in 100; Hu & Nation
2000, Schmitt et al. 2011) and supported study reading at about **95%** (Laufer 1989). So the
target is much lower than BERT's 15%: with 15% of words unknown, a reader understands little.

- **A level is one number:** an estimated vocabulary size *V* on a frequency ranking of English
  lemmas (wordfreq). The chance of knowing a word of rank *r* is `1 / (1 + (r/V)^3.5)`. Words that
  are common in children's stories ("crocodile", "mango") count as easier than web frequency
  says. CEFR labels are approximate (after Milton 2010): A1 ≥ 500, A2 ≥ 1,500, B1 ≥ 2,500,
  B2 ≥ 4,000, C1 ≥ 6,000, C2 ≥ 9,000 lemmas.
- **Each text gets a personal coverage:** every word is reduced to its lemma ("went" → "go");
  names and sound words ("Moo", "Shhh") count as known. Words the student has mastered, is
  learning, or has looked up override the curve.
- **Fit bands** around the student's target *T* (default 98%): *Easy* ≥ T+1%, *Just right*
  T±1%, *Challenge* T−4% to T−1%, *Hard* below. Before a challenging text, the reader lists the
  few probably-new words so they can be learned as flashcards first.
- **Testing and tracking:** the level test (Meara-style yes/no with made-up words; a result with
  more than 25% "yes" to made-up words is not saved) sets *V*. After that, *V* is re-estimated
  after every finished text from words tapped (unknown), words read past without a tap in texts
  that were understood (weak evidence of known), masked-word answers, and "I know this word".
  The rating (*Too easy / Just right / Too hard*) and the check score move *T*.
- **Masked-word check:** after reading, one word is hidden in up to six sentences of the text;
  the wrong options come from the same text, with the same ending and part of speech.

### How reading and the word steps link

- Reader → words: every tapped word is logged with its sentence; ☆ or *Learn it* puts it into
  spaced review, and *Study these words* after reading turns all looked-up words into flashcards.
- Words → reader: words being learned are highlighted in texts, books that contain them rank
  higher, and a masked-word answer on a word that is due counts as a review in context.
- A word's page shows *Where you met it* and *Read it in a story* (sentences from library texts
  that fit the student).
- The level test suggests where to start in the word steps, and Home offers to skip ahead.
- AI stories are built around today's new words.

### Reading sources and licences

| Source | What | Licence |
|---|---|---|
| [African Storybook](https://africanstorybook.org), via [global-asp/asp-source](https://github.com/global-asp/asp-source) | ~370 short stories, Pre-A1–B1 | CC BY 4.0 (a few CC BY-NC) |
| [Pratham Books StoryWeaver](https://storyweaver.org.in), via [global-asp/pb-source](https://github.com/global-asp/pb-source) | ~390 short stories | CC BY 4.0 |
| [Project Gutenberg](https://www.gutenberg.org), from the gutenberg.pglaf.org mirror, 2 s between downloads | 32 classics split into chapters (list in `app/sources.py`) | Public domain in the USA; authors died before 1950 |
| Teachers | Any pasted text (Settings → Add a text) | Only add texts you may use |
| Claude | Stories written for one student, visible only to them | Generated |

Every text keeps its credit and licence line, shown under it. The NC stories are fine for
non-commercial classroom use. Storybook pictures are not downloaded.

### AI stories (optional)

Add an Anthropic API key in **Settings → AI stories** (stored in `userdata/ai.json`), or set
`ANTHROPIC_API_KEY`. The default model is Claude Opus 5.5; Sonnet 5.5 and Haiku 5.5 are cheaper.
A story takes 20–60 s. After writing, the app measures the story against the student's own
vocabulary; if too many words are probably new, Claude rewrites it once, replacing exactly
those words. Each story comes with four comprehension questions.

## Project layout

```
app/
  main.py          FastAPI routes (students, dashboard, levels, words, quiz, TTS, import)
  content.py       loads the curriculum from app/data/levels/*.json
  dictionary.py    lookup chain: built-in → imported list → cache → dictionaryapi.dev
  quiz.py          question generation
  srs.py           spaced-repetition rules
  db.py            SQLite schema and queries (userdata/wordstep.db)
  tts.py           Kokoro (kokoro-onnx) synthesis with a WAV cache in cache/tts/
  launch.py        one-click launcher behind run.bat: free-port search, opens the browser
  data/levels/     the 8 level files — edit or add JSON files to change the curriculum
  textproc.py      tokens, lemmas, names, sentences
  vocab.py         vocabulary model: frequency ranks, P(known), level test, level estimate
  library.py       books and units, lemma index, coverage and fit, recommendations, reader, masked-word check
  sources.py       storybook / Gutenberg / teacher-text import (python -m app.sources)
  reading.py       reading routes, level tracking, level test, word contexts, AI routes
  ai.py            Claude stories and comprehension questions
  grammar.py       grammar lessons, practice sessions, spaced review, pattern detectors, writing feedback
  data/grammar.json  the 25 grammar points and their questions
static/            index.html, style.css, app.js, reading.js, grammar.js (no build step)
tests/             uv run pytest
```

To add a level, copy a file in `app/data/levels/`, give it a new `id` and `order`, and mark
the target word in each example with `*asterisks*`. The fill-in-the-blank questions and
highlighting use those marks. `tests/test_app.py` checks the format.

## Notes

- dictionaryapi.dev is free but sometimes slow or down. When it doesn't respond, the app
  says so and nothing is cached, so the next try can still succeed. Curriculum words never
  need the network.
- Each TTS clip is generated once (about 1 s for a sentence on CPU) and then served from
  `cache/tts/`. The first clip after starting the server takes a few seconds while the
  model loads.
- Student profiles have no passwords. They are meant for a home or classroom computer.
- The library index (lemma counts per chapter) is built in memory on first use, about 1 s for
  the full library. The frequency ranking is cached in `cache/lemma_ranks.json`.
- Tapped words that are not in the curriculum are looked up on dictionaryapi.dev, so they need
  the network (and fail when that service is down).
