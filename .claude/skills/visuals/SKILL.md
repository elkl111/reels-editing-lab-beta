---
name: visuals
description: The visual director. Plans the pop-up explainer graphics (chips, numbers, chat windows, checklists, diagrams…) that illustrate what the speaker says, beat by beat, in their kit's style. Use in the new-reel build step, when the user asks for more or fewer graphics ("more pop-ups", "illustrate this part", "a checklist here"), or asks what graphics exist ("what can you add?", "show me the options").
---

# Visual director

A great talking-head reel shows what the speaker is saying, a beat at a time: a list becomes chips popping in as each item is said; a number counts up; "I typed a prompt" becomes a chat window typing it. The pieces are small, sit around the head (never on the face), and appear exactly when the word is spoken.

You plan this in `build.json` → `"visuals": [...]`. The engine handles placement, the kit's look, animation and a sound per pop-up.

## 1. Read the reel as beats

Go through the locked lines (`edl.json`) with word indexes:
`python3 -c "import json;w=json.load(open('projects/<name>/transcript.json'))['words'];c=json.load(open('projects/<name>/cut.json'));[print(' '.join(f\"{x['i']}:{x['w']}\" for x in w[a:b+1])) for a,b in (l['words'] for l in c['lines'])]"`

Mark every beat that has something **showable**:
- a list of things
- a number
- a tool or app
- an action (typing, sending, booking)
- a before/after or a this-vs-that
- a process or steps
- a system
- a person or story
- a time span
- a rejected idea
- a key word worth landing

Filler, transitions and feelings without an object get nothing.

## 2. Pick the piece for each beat

| They say… | Piece | Example |
|---|---|---|
| a list ("marketing, invoices, emails") | `chips`, one item per word as it's said | items with `word` each |
| things being dropped or closed ("all those tabs in my head") | `chips` with `"close": true` | |
| a figure ("100+ clients", "3pm", "a team of 2") | `number` | `"value": "100+", "label": "clients"` |
| the key word or punch of a line | `word` (`"style": "type"` for a thought or question) | `"text": "real *support*"` |
| something they reject ("no 50 steps", "not another app") | `strike` | `"pre": "No", "text": "50 steps", "strike_word": i` |
| typing a prompt, asking AI, sending a DM | `chat` | `"prompt": "...", "reply": "..."` (optional) |
| a sale, a message, a booking, a notification | `notify` | `"app": "Stripe", "title": "New payment: €497"` |
| steps done, a to-do list, wins | `checklist` | items with `word` each |
| "step 1 / the first thing / part two" | `step` | `"n": 1, "text": "*train* it"` |
| a change or process (A → B → C) | `flow` | items with `icon` and `text` |
| a system, tools connected, "everything in one place" | `hub` | `center` plus `nodes` with icons |
| a time span or range ("in a month… in 3 years") | `scale` | `marks`, `from`, `to`, `move_word` |
| a client, a person, a story about someone | `person` | `"name": "Abby", "note": "coach", "meter": 3` |
| this vs that, old way vs new way | `versus` | `left` (the ✗) / `right` (the ✓), `right_word` |
| their profile, a screenshot, an app | `phone` | `"image": "assets/profile.png"` (only images the user gave) |

**Text on pieces:**
- 1–3 words per chip, node or label
- use their words
- title case is fine, but no full sentences except in `chat` and `notify`

**Icons:** find real names with `uv run tools/icons.py calendar money email` and never guess a name. The build stops on an unknown icon.

## 3. Timing (word indexes from the transcript)

- `"word": i` makes the piece appear as word i is spoken. Use the first word of the beat, not the start of the line.
- Items take their own `"word"`, so each chip, check or node lands as it's said. This is what makes it feel edited.
- Ending a piece:
  - `"until_word": j` ends it after word j
  - otherwise it holds about 2–3s, or until 1.4s after its last item
  - `"dur": 2.5` sets the length directly
- Other moments can be timed to words too: `strike_word`, `reply_word` (chat), `right_word` (versus), `move_word` / `move_end_word` (scale), `meter_word` (person), `close_word` (closing chips).

## 4. Density from the kit (`kit.json` → `visuals.density`)

| density | how often | feel |
|---|---|---|
| `calm` | one piece every 8–10s | a clean expert explainer |
| `steady` | every 4–6s | most reels |
| `busy` | every 2–4s, nearly continuous | the fast "explainer" style |

Rules at every density:
- One piece at a time. Two can overlap only if they're in different zones and belong to the same beat.
- Never during the hook (first ~3s) or a statement. Pieces can replace statements: at `busy`, use at most 1 statement.
- Don't use the same kind twice in a row, unless it's the same list continuing.
- A `word` pop should **condense or reframe**, not mirror the caption. When it shows the same words, the engine hides the caption while it's up. That works, but a pop like "the *whole* business" on "comprehensive overview of your business" adds more than repeating "non-negotiables".
- Don't put a highlight (`highlight_words`) on a word that also gets a pop-up.
- `chat` plays a full little story by itself: it types the prompt (with key clicks), sends it (swipe sound), then shows the AI "thinking", then the `reply` if given. Give it about 1.5s after the typing ends, so it can send. A short `reply` in their words (the outcome they describe) makes it land.
- Leave short breathing gaps (≥0.4s) between pieces.
- `"at"` overrides the zone (`top`, `left`, `right`, `chest`) only when the default collides with something.

## 5. Build and check

`uv run tools/build.py projects/<name>`. The build prints `CHECK=…/check.png`: one frame per moment and pop-up. **Read it** and fix anything that is:
- unreadable
- off-screen
- covering the face
- colliding with a caption
- illustrating the wrong word

Then hand back as in the new-reel skill, adding one line such as: "12 pop-ups: chips for your 4 tasks, a chat window on 'prompt', a hub for your AI system…".

## When the user asks
- **"What graphics can you add?" / "show me the options":** open the catalogue video if one exists for their kit (`projects/*/catalog-<kit>.mp4`). Otherwise render one on their latest reel: `uv run tools/build.py projects/<name> --catalog`. It shows every piece once, in their look, labelled. Never describe pieces at length instead.
- **"More / fewer pop-ups":** change the density for this reel; save it to the kit's `visuals.density` if they say "always".
- **"A checklist here" / "show my profile when I say follow":** add exactly that piece on that word.
- **Style** ("outlined cards", "calmer animations", "thicker icons"): the kit's `"visuals"` block:
  - `card`: `solid` / `outline` / `glass`
  - `motion`: `gentle` / `snappy` / `bouncy`
  - `icon_stroke`: 1.5–2.5
  - `radius`
  - colours: `accent`, `strong`, `alert`, `word`, `card_color`; colour names from the kit or hex values

  Change their kit, never a preset.
