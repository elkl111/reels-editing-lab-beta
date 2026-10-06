---
name: hooks
description: Write hooks for a reel that are curious but human, true to the reel and specific to it. Use in the new-reel flow (opening check after the rough cut; on-screen hook and cover title in the build), when the user asks to change the hook ("hook 2", "different hook", "punchier hook"), or before filming ("give me hooks for a reel about X", "how should I open this?").
---

# Hooks

A hook has one job: make the right person want the next 3 seconds. It does that with curiosity, not hype. The test we hold every hook to: **would a real person say this to a friend, and does the reel actually pay it off?**

Read `patterns.md` (next to this file) before writing. Read `brand/preferences.md` and `brand/hooks.md` if they exist; they hold what this user picks and rejects.

## 1. Mine the reel before writing anything

From the locked lines (or, before filming, from what they tell you), write down for yourself:
- **Payoff:** the one thing the viewer gets by the end. One sentence.
- **Tension:** what it pushes against: a mistake, a common belief, a frustration, a wasted effort.
- **Concrete detail:** a number, an object, a moment, a name, or a phrase the speaker actually said that's vivid.
- **Who it's for:** as specifically as the reel allows ("people paying for 3 AI tools", not "entrepreneurs").

Every hook is built from these four. If you can't name the payoff, the hook can't be true, so look again at the reel.

## 2. Write three options, each with a different pattern

Patterns (examples are in `patterns.md`):
- name the mistake
- flip the belief
- show the result, hide the how
- call out who it's for
- start mid-thought
- lead with the number
- before/after

Use a different one for each option, so the user gets a real choice and not three versions of the same line.

## 3. Keep only options that pass all four checks

| Check | Passes when | Fails when |
|---|---|---|
| **True** | The reel delivers exactly what the hook promises | It teases something bigger than the reel gives ("this changed everything") |
| **Specific** | It contains a detail from this reel; it couldn't go on someone else's video | It fits any reel in the niche ("Stop doing this with AI") |
| **Curious** | The viewer can't guess the answer, and wants it | The answer is obvious, or it's a yes/no question they can answer "no" to ("Do you use AI?") |
| **Human** | Said out loud, it sounds like a person texting a friend; it uses the speaker's own words where possible | It sounds like an ad or a guru |

Human, in practice:
- **Short:** an on-screen hook is about 8 words max. The eyebrow is 2–4 words.
- **No hype words:** game-changer, unlock, secret, hack, insane, crazy, mind-blowing, "you won't believe", "nobody is talking about", "this will change your life", ultimate, guaranteed.
- **No clickbait dressing:** no ALL-CAPS words for shouting (a kit's uppercase style is fine), no "!!!", no emoji stacks, no "POV:" unless it's genuinely a point-of-view setup.
- **Their voice:** if they say "honestly" and "my business brain", the hook can too. Never put words in their mouth that they'd cringe at.
- **Plain over clever:** a pun that needs decoding loses to a clear line that opens a loop.

Rewrite or drop any option that fails a check. Don't present it with a caveat.

## 4. Text works with the voice, not against it

The viewer hears the first spoken line and reads the hook card at the same moment.
- The card **adds** what the voice doesn't say: who it's for, what's at stake, or the tension.
- Never put the spoken first line word for word on the card. Captions already show it.
- Example:
  - spoken: "While most people are debating which AI tool is best…"
  - card eyebrow: "STOP SWITCHING AI TOOLS"
  - card text: "Build your *business brain*"

In `build.json`, `eyebrow` is the small caps line and `text` is the hook. Put exactly one `*emphasis*` on the word that carries the curiosity: the object, the number or the twist. It gets the kit's italic or highlight.

## In the new-reel flow

### A. Opening check (after the rough cut, before showing the lines)
Look at the first 2–3 seconds of the cut.
- **Warm-up openings** cost the reel. Trim them in `cut.json` before review, and say so in the review message ("I started you at 'Most people…' and skipped the 'so today I want to talk about'"). They include:
  - "so", "okay", "hey guys", "hi everyone"
  - "today I want to talk about…"
  - "so I've been thinking…"
  - restating the topic before saying anything
- **Cold open:** if a later line is clearly the strongest opener, offer it in the review. Don't apply it unprompted, because it changes their story. A strong opener is:
  - a surprising claim
  - the result
  - the most vivid moment
  - the line the reel is really about

  Offer it like this:
  > Option: start with line 7 ("I deleted all my AI subscriptions but one") as a cold open, then the rest as is. Say "cold open" to try it.

  If they say yes, move that entry to the top of `cut.json` (play order follows the list), re-run roughcut and verify, and check line 2 still makes sense after it. If it doesn't, drop or trim the line that now repeats.

### B. Hook card and cover title (in the build)
1. Write 3 options (steps 1–4). Pick the strongest as the hook event; store all three in it:
   `{"type": "hook", "line": 1, "eyebrow": "...", "text": "...", "options": [{"eyebrow": "...", "text": "...", "pattern": "name the mistake"}, …]}`
2. **Cover title:** the profile grid is browsed by topic, so the cover is clearer than the hook:
   - 3–6 words
   - names the subject
   - curious but not cryptic

   Put it in `build.json` as `"cover": {"text": "...", "eyebrow": "..."}`. Use the hook only if it already names the topic.
3. In the two-line build report, show the pick and the alternatives:
   > Hook: "Build your *business brain*". Or say **hook 2**: "One folder, every AI" / **hook 3**: "Stop paying for 3 tools".

### C. When they swap or change it
- "hook 2" / "hook 3": copy that option into the hook event's `eyebrow`/`text`, rebuild (graphics only; it takes about 30s), and confirm in one line.
- "punchier", "softer", "less salesy", "more me": write 3 new options in that direction, with the same checks, and pick one.
- Log every pick to `brand/hooks.md`, one line each, with the date, the reel, the chosen hook, its pattern, and any rejected options with the reason if they gave one.
- When they've picked or rejected the same pattern 3 times, add a line to `brand/preferences.md` ("prefers 'start mid-thought' hooks"; "never 'call out who it's for'").

## Before filming ("give me hooks for a reel about X")

1. Ask one question only if the payoff is unclear: "What's the one thing you want them to walk away with?"
2. Give 3 options, each with:
   - **Say:** the spoken first line, conversational, under 2 seconds to say
   - **Card:** the on-screen eyebrow plus text that pairs with it
   - the pattern name, in a few words
3. Add one line of delivery advice when it matters: "say the first line before you smile", or "start mid-sentence; we'll cut the breath before it".

Keep it in the chat, and short.
