---
name: new-reel
description: Edit a talking-head reel from a raw clip. Use whenever the user says "I have a new reel", "edit this reel", "new clip", drags a video into the chat or drops one in inbox/, or gives edits to a rough cut ("drop line 3", "end line 9 at…", "good, move on"). Covers transcription, the rough cut and the review, all in the chat.
---

# Edit a reel

Everything happens in this chat. Talk like an editor: short updates, no jargon, no settings. Time each step and mention it when you hand back ("rough cut done in 0:40").

## 1. Transcribe

- The clip is the newest video in `inbox/` unless they drag one in or name one. If several are new, ask which.
- `transcribe.py` checks the clip first. If it prints `PROBLEM:` lines and `INTAKE=refused` (horizontal, too long, no sound), pass the message on kindly and stop. `NOTE:` lines (HDR converted, long clip) can be mentioned in one short line.
- Tell them: "Transcribing now, a few seconds."
- `uv run tools/transcribe.py "<clip>" --name <working-name>`
- Read `brand/preferences.md` if it exists.

The transcriber (Parakeet) writes down exactly what was said, **including restarts said without a pause** ("while most of the pe… while most of the people"). Every attempt is in the transcript, so every attempt can be cut.

## 2. Make the rough cut

Read `projects/<name>/lines.md`. Each phrase is `P# [firstword-lastword] start→end | text`. Word indexes point into `transcript.json`. To trim precisely, print the indexed words:
`python3 -c "import json;w=json.load(open('projects/<name>/transcript.json'))['words'];print(' '.join(f\"{x['i']}:{x['w']}\" for x in w))"`

Decide what stays, in this order:

1. **Retakes:** when a line is said more than once, keep the **last complete, fluent take**. Earlier attempts are rehearsal, including half-words ("pe", "m") and abandoned starts. Retakes are often reworded, so match on meaning.
2. **False starts:** drop anything that trails off, gets abandoned, or is immediately restarted. Look carefully inside long phrases, because restarts often happen mid-phrase with no pause ("and these are and these are the non-negotiables" → keep only the last "and these are the non-negotiables").
3. **Talking to themselves:** drop "okay", "let me start over", "was that good?", and laughter after a fumble.
4. **Fillers:** drop a leading "so", "um", "uh" or "okay" when the line works without it. Drop "uh" and "um" inside lines by splitting the line around them.
5. **Keep personality.** Asides and jokes that land are content. When unsure, keep it and mention it.
6. Keep the order they spoke in, unless they ask otherwise.

Write `projects/<name>/cut.json`:

```json
{"lines": [
  {"text": "while most of the people are debating…", "words": [19, 33]},
  {"text": "This is what I want you to do instead.", "words": [53, 61]}
]}
```

- One entry = one reviewable line: a sentence or short thought, about 2 to 8 seconds.
- `words` is an inclusive range of whole words. `text` is exactly those words (fix only obvious mis-hearings).

Then:
1. `uv run tools/roughcut.py projects/<name>` renders the cut, prints the numbered lines and opens the video in QuickTime.
2. `uv run tools/verify.py projects/<name>` listens back. Fix any "missing", "extra" or "repeated" spot before showing the user: adjust `cut.json` and re-run. Spelling-only differences ("Chat GPT" vs "ChatGPT") are fine.
3. **Opening check** (the `hooks` skill, section A): trim a warm-up start ("so today I want to talk about…"). If a later line would make a stronger cold open, offer it in the review rather than applying it.

## 3. Review in the chat

Show them:

```
Rough cut ready: 1:31 → 0:51, done in 0:40. It's playing in QuickTime.
I took out: 3 attempts at the opener, "and these are" twice, 6 of the 7 "let me show you"s.

 1. while most of the people are debating… (4.3s)
 2. or to go back to Claude… (5.6s)
 …

Tell me what to drop or change ("drop 3", "end 9 at 'important things'", "use the earlier take of 5"), or say "good".
```

Keep the line list exactly as roughcut printed it (it's also in `lines_review.txt`).

## 4. Apply their edits

They answer in plain words, usually by line number.
- "Drop 3" → remove that entry.
- "End 9 at…" or "cut 'which I love'" → shrink that entry's word range.
- "Use the earlier take" → find it in `lines.md` and swap the range.
- A note about visuals ("show my screen here", "big text on this") → save it in `projects/<name>/notes.md` for the build step.

Re-run roughcut and verify (unchanged parts are reused, so it takes seconds). Reply in one or two lines with what changed and the new length. Repeat until they say "good".

If a correction would apply to every reel (for example "never cut my 'honestly'"), add it as one line to `brand/preferences.md`.

- "Cold open" → move the line you offered to the top of `cut.json`, re-run, and check the next line still follows.

When they say "good", the rough cut is locked and the build starts.

## 5. Build the finished reel (automatic, in their look)

When the rough cut is locked, build straight away. Don't ask for approval.

1. Read their kit: `brand/kit.txt` names it, and the kit is `packs/<kit>/kit.json`. Its `rules` say what goes where and how much (`intensity`).
2. Read the locked lines (`edl.json` → `lines`) and write `projects/<name>/build.json`:
   - **hook** on line 1, written with the `hooks` skill: mine the reel, write 3 options with different patterns, keep only those that pass the four checks (true, specific, curious, human), and store all three in `"options"`. The best one goes in `eyebrow` (2–4 words) and `text` (about 8 words max, one `*emphasis*`).
   - **cover:** `"cover": {"eyebrow": "...", "text": "..."}`, a clearer 3–6 word title that names the topic (`hooks` skill, B2).
   - **label** (name ✳ what they do): **not by default.** Add it only when the reel is about them: they introduce themselves ("I'm…", "if you're new here…"), tell their own story, or the user asks for it. Use `{"type": "label", "at_line": n}` on that line. If the kit's `label` still says YOUR NAME / WHAT YOU TEACH, ask them once for the wording (short, max ~22 characters per side) and save it in their kit.
   - **statement** (big text moment): a 1.6-second full-screen slam on the single strongest idea, rewritten to 2–4 punchy words with one `*emphasis*` word. Time it with `"word": i` on the word where the idea lands (for example "work" in "you can work across them"), not on the whole line. At most 2 per reel, never in the first 5 seconds, never back to back. With intensity `clean`, skip it. It covers the speaker, so keep it rare.
   - **highlight_words:** about one word every 3rd caption, on the nouns and numbers that carry the point (word indexes from `transcript.json`). Never filler words.
   - **visuals** (pop-up explainer graphics): plan them with the `visuals` skill, at the kit's density. At `busy`, this is the main layer of the edit.
   - **zooms:** 1–3 punch-ins, `{"line": n}`, on the lines that land the point (a promise, a number, a turn). Never on the hook line or a statement line. Jump zooms at cuts happen automatically (kit `zoom.jump`).
   - **behind** (text or a picture behind the speaker, with them in front, cut out by Apple Vision): at most 1–2 per reel, on a key noun or a reveal. `{"type": "behind", "line": n, "text": "One *folder*"}` puts giant words on the wall at head height (1–3 words read best). Add `"image": "path/to/file.jpg"` to replace the wall with a meme, screenshot or B-roll still they gave you, or a file in `assets/`. It costs about 20 seconds of extra build time per moment.
   - **Sound effects** are automatic from the kit's **sound set** (`"sfx": {"palette": "soft"}`; sets are in `sfx/palettes.json`):
     - `soft`: gentle and calm
     - `clicky`: techy and crisp
     - `playful`: light and fun
     - `punchy`: bold and high-energy

     Each moment rotates through 3+ sounds, and the build spaces them out and caps repeats, so don't add sounds on every highlight yourself.
     - Add 1–3 sounds that match what's being said: `"sfx_extra": [{"at": 12.3, "sfx": "keyboard"}]` for typing a prompt, `mouse_click` on "just click", `ding` or `sparkle` on an aha, `shutter` on "screenshot", `page_flip` on "next", `riser` just before a reveal. The `at` time is in the finished reel.
     - Pin a sound on one event with `"sfx": "thud"` inside it. Use `"sfx": false` in build.json for none.

### Sounds: what the user can say
- **"What sounds are there?" / "other sounds?"**
  - `open sfx/sound-menu.mp4`: a ready-made 40-second video with a numbered card and a play of each sound. **Never generate or synthesise audio previews**; the menu already exists.
  - In the chat, list the 4 sets in one line each, plus "or pick by number from the menu".
- **"Use the clicky sounds" (this reel):** `"sound_set": "clicky"` in build.json, then rebuild.
- **For every reel ("always clicky"):** set `sfx.palette` in their kit.
- **"No 3" / "I hate the bubble":** add the name to the kit's `sfx.avoid` list (lasting) and rebuild. Numbers match `sfx/LIBRARY.md`.
- **"More of 6":** add it to `sfx.favour`; favourites lead the rotation on highlighted words.
- **"Fewer sounds" / "quieter":**
  - fewer: drop `highlight_words` that don't need a sound, or set the kit's `"highlight": []`
  - quieter: lower `sfx.volume_db` by 3
- The build prints `SOUNDS=set: soft; soft_pop ×3, tick ×2…`. Mention the set in your report, so they know what to ask for by name.

3. `uv run tools/build.py projects/<name>` renders `final.mp4` (about 30 seconds for a 50-second reel) and opens it.
4. Check before handing back: grab frames at the hook, any label and each statement (`ffmpeg -ss <t> -i final.mp4 -frames:v 1 …`), look at them, and fix anything off-screen, unreadable or covering the face.
5. Tell them in two or three lines what you did, and that they can ask for changes ("no hook", "different big moment", "calmer"). For example:
   > Hook: "Build your *business brain*". Or say **hook 2**: "…" / **hook 3**: "…".
   > One big moment on "work across them", 4 highlighted words, 2 punch-ins. Sounds: the soft set (soft pop, swoosh, tick).

   Hook swaps and tweaks follow the `hooks` skill, section C.

   Then add: "It's also in your **Finished reels** folder, ready to post. For your next reel, start a new chat in this folder and type **/new-reel**." Say the new-chat line only on the first finished reel of a chat.

Tweaks: edit `build.json` (or the kit, for changes that should stick) and re-run build. Save lasting preferences to `brand/preferences.md`.

"Use these colours instead" / "make it sage and cream" / "different font": change their kit (`colors` values, keeping the roles; `visuals.rotate` for the pop-up colours; any free Google Font), then rebuild. Ask "just this reel or always?" only if unclear. Never edit a preset.

To preview a kit: `uv run tools/build.py projects/<name> --sheet` renders every piece over their footage as one image.
