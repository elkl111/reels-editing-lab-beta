---
name: setup
description: First-time onboarding for the Reels Editing Lab. Installs what's missing, runs a short brand interview, lets the user pick their look on their own footage, and saves it as their kit. Use when the user says "set me up", "get started", "onboard me", or when brand/kit.txt doesn't exist yet (the Lab hasn't been set up).
---

# Set me up

The user has just opened the Lab for the first time. They are not technical. By the end they have everything installed, a look they chose by seeing it on their own face, and their own kit saved. Then they're ready for their first reel.

Tone: warm, brief, one step at a time. Say what's happening while they wait. Never paste raw tool output at them. Never ask them to run a command, except the one Homebrew line if it's missing (see step 1).

Start with one short message:
> Welcome to the Reels Editing Lab. Setup takes about 10 minutes: I install a few things, ask you 3 quick questions, and then you pick your look by seeing it on your own video. Let's go.

## 1. Install (≈5 min, mostly the speech model download)

Run `python3 tools/doctor.py`. It prints a checklist and `DOCTOR=ok` or `DOCTOR=missing:<names>`. Fix the missing items in this order, re-running the doctor at the end:

1. **mac / space:** if either fails, stop and explain kindly (Apple-chip Mac needed; about 6 GB free).
2. **homebrew:** you can't install it for them, because it needs their Mac password in a real Terminal. Explain in one line why, then give them the exact line from the doctor's fix, telling them to open the **Terminal** app (Cmd+Space, type Terminal), paste it, press Enter, type their Mac password (nothing shows while typing; that's normal) and follow the prompts. At the end Homebrew prints two "Next steps" lines starting with `echo` and `eval`; ask them to paste those too. Wait for them to say done, then re-check.
3. **apple-tools:** run `xcode-select --install`. A Mac window pops up; tell them to click **Install** and say when it's finished (a few minutes). Homebrew usually installs these already, so check first.
4. **ffmpeg:** `brew install ffmpeg` (use `/opt/homebrew/bin/brew` if `brew` isn't on the path yet).
5. **uv:** `curl -LsSf https://astral.sh/uv/install.sh | sh`, then use `~/.local/bin/uv` if `uv` isn't found yet.
6. **python-tools:** `uv sync`
7. **renderer:** `uv run playwright install chromium`
8. **speech-model:** `uv run tools/get_models.py` in the background (2.3 GB). It resumes by itself if the connection drops. Start it, then move on to the interview while it downloads. Check back on it before step 3 needs it.

While things install, tell them in one line what each piece is for (the doctor's descriptions are written for this).

## 2. Brand interview (3 questions, one at a time)

Ask conversationally, one question per message. Keep their exact words.

Don't ask for a name, tagline or "what you do" label: the Lab doesn't add one by default (see the new-reel skill, "label").

1. **Energy.** "How are you on camera: calm and thoughtful, warm and chatty, or high-energy?" This sets how busy the edit is (see the table in step 4).
2. **Brand.** "Do you have a brand or design file, brand colours, or fonts? Drop your design file (a .md or PDF) and I'll build your look from it. Or paste colour codes, or drop 3–6 screenshots of reels whose look you love into the `inspiration` folder. Or just say 'no, show me options'."
3. **Never.** "Anything you never want on your reels? For example all-caps text, certain emojis, sound effects, words you'd never say."

Save the answers to `brand/profile.md`:
```markdown
# Profile
- Energy: warm and chatty
- Brand: colours #… / fonts … / screenshots in inspiration/ / none
- Never: …
```
Also add each "never" to `brand/preferences.md` as a one-line rule.

## 3. See the looks on their own face

Ask: "Now drop in any clip of you talking to the camera, ideally 20 seconds or more. Drag it into this chat or into the `inbox` folder. It doesn't have to be a good take; it's just to try looks on."

When the clip is in (and the speech model has finished):
1. `uv run tools/transcribe.py "<clip>" --name welcome-sample`
2. Read `projects/welcome-sample/lines.md`. Write `cut.json` with **the first 3–5 clean lines, about 12–20 seconds**, using the new-reel rough-cut rules (last clean take, no false starts). Run `uv run tools/roughcut.py projects/welcome-sample --no-open` and `uv run tools/verify.py projects/welcome-sample`, and fix anything it flags. Don't ask them to review this cut; it's only a sample.
3. Write `build.json` like the new-reel skill: a hook written with the `hooks` skill from what they actually said (this is their first impression of the Lab, so make it good), 1–2 highlight words, 1 zoom, and one statement on the strongest line. Add 2–4 pop-ups with the `visuals` skill (for example chips for a list they mention, or a chat window if they talk about prompting), so they see what the Lab really does. Don't add a behind moment.
4. **Looks sheet:** `uv run tools/build.py projects/welcome-sample --looks presets`. It opens one image with their clip in every look, side by side, in the order printed after `LOOKS=`. Look at the image yourself first (Read it) and check the text is readable and nothing covers the face.
5. Introduce the looks in one short line each, in the printed order, using each kit's `description` (`packs/<name>/kit.json`). The top row shows the hook and captions; the bottom row shows the pop-ups.
   Then say clearly that **a look is a starting point, not a final choice:**
   > Pick the one whose *feel* you like most. Everything can be changed after: "this one, but in sage and cream", "use my colours: #…", "a softer font", "no pink". I'll redo it on your clip so you can see it.

   Ask which they'd like to **see moving**.
6. For each one they pick: `uv run tools/build.py projects/welcome-sample --kit <name> --out sample-<name>`. It opens in QuickTime. If they pick two, build both and open them one after another.

If they gave brand colours, fonts or screenshots in step 2, also offer: "Or I can make a look from your brand." See step 5.

## 4. Save their kit

When they choose (for example "Editorial, but in sage and cream" or "Playful, but calmer"):
1. Copy `packs/<preset>/kit.json` to `packs/<their-first-name-lowercase>/kit.json`. In the copy:
   - `"name"`: their name
   - `"preset": false`
   - `"based_on": "<preset>"`
2. Apply their energy:

   | Energy | intensity | zoom jump / punch | sfx volume_db | statements |
   |---|---|---|---|---|
   | calm and thoughtful | clean | 1.04 / 1.08 | −17 | at most 1 |
   | warm and chatty | signature | 1.07 / 1.13 | −13 | at most 1–2 |
   | high-energy | full | 1.12 / 1.22 | −10 | up to 2 |

   Change `rules.intensity`, `zoom`, `sfx.volume_db` and the `rules.statement` wording to match.

   Sound set (`sfx.palette`):
   - calm: `soft`
   - warm: `soft` or `playful`
   - high-energy: `punchy`
   - tech or AI topics: consider `clicky`

   Mention once that they can hear every sound in `sfx/sound-menu.mp4` and switch sets by asking ("use the playful sounds"). If they said "no sound effects", set `"sfx": {}`. If they said no all-caps, set `style.caption_case`, `style.hook_case` and `style.statement_case` to `"none"`.
3. Apply their colours, whether from the interview or the moment they ask ("use these colours instead"):
   - **From hex codes or plain names:** "sage" or "dusty pink" are fine; pick tasteful hexes and tell them which.
   - **Swap the values** in `colors` and keep the roles: light colours go on cards and captions, dark ones on statement backgrounds and ink, brights on highlights and `visuals.rotate`.
   - **Check contrast:** text must be readable on its background.
   - **Re-render the looks sheet** for their kit (`--looks <their-kit>`) so they see it before the full sample.
   - **Fonts work the same way:** any free Google Font (`fonts.py` confirms it exists).
4. Write the kit's folder name to `brand/kit.txt`.
5. Build the sample once more in their kit: `uv run tools/build.py projects/welcome-sample --out sample-mine`. It opens in QuickTime. Ask: "This is your look. Anything you'd change?" Apply changes to their kit (not the preset) and rebuild until they're happy. Small changes like "smaller captions", "less yellow" or "no tilt" are one-line edits in `kit.json`.

## 5. Make a look from their brand (when asked)

### From a design file (the best way)
If they have a brand or design doc (a `.md`, PDF or Google Doc export, like a `BRAND-DESIGN.md`):
1. **Get the file.** Ask them to drag it into the chat or drop it in `brand/`, then save a copy as `brand/design.md` (or keep the PDF) as the source of truth for their look.
2. **Map it to their kit:**

   | In the design file | In `kit.json` |
   |---|---|
   | colour palette (hex codes and what each is for) | `colors`, plus `roles`: backgrounds → `hook_card` and `label_bg`; text colour → `ink` and `hook_text`; the "statement" or dark block → `statement_bg`; highlight colours → `highlight_blocks`; accents → `accent_pill`, `visuals.rotate` |
   | "never pure black or white" type rules | use their darkest brand colour as ink |
   | headline and display font | `fonts.display` / `poster`, its italic as `fonts.italic`, a sans for `label` and captions |
   | signature moves (italic mixing, highlight blocks behind words, tilt, stickers, all caps) | `moves` and `style` (`hook_case`, `statement_case`, `radius`) |
   | mood ("calm", "playful", "luxury") | `visuals.motion`, `visuals.density`, `sfx.palette` |
   | photo or video style (warm, moody, bright, film-like) | `grade`: `contrast`, `saturation`, `brightness`, `warmth` (−0.05 to 0.05), `vignette` (0–0.5), `legibility` (dark gradients behind text, 0–0.5). Keep skin natural: no film grain, no heavy crush. |
   | icons, graphic elements, stickers, buttons (line weight, rounded or square, filled colour tiles) | `visuals.icon_stroke` (thin 1.5 → bold 2.5), `visuals.radius`, `visuals.card` (solid / outline / glass), `visuals.accent` (icon tile colour), `visuals.rotate` (chip and sticker colours) |

3. **Paid or custom fonts:** look for the font files. If they have them, they drop them in `fonts/private/` and the kit uses `"file"`. If not, pick the **closest free Google Font**: match the contrast, the width (tall or condensed?), and whether an italic exists. Tell them what you substituted and why. For example, "your paid serif → Instrument Serif: same tall, high-contrast feel, has an italic."
4. **Show it:** render `--looks <their-kit>` and build `sample-mine`. Say which parts came straight from their file and which you interpreted.
5. **Keep it in sync:** if they update the design file later ("I changed my brand colours"), re-read `brand/design.md` and update the kit the same way.

### From screenshots or pasted colours

When they want their own look rather than a preset:
1. Read their screenshots in `inspiration/`, their brand guide, or the codes they pasted. Note:
   - type: serif or sans, how heavy, whether it's all caps, whether it mixes in an italic
   - caption treatment: outline, shadow or box; whole phrase or word by word
   - card shapes and radius
   - 4–6 colours
   - how busy it is
2. Start from the closest preset and change only what differs. Fonts must be **free Google Fonts**: write `{"family": "<Google Font name>", "google": true, "weight": N}` (add `"italic": true` for an italic). Confirm each one downloads with `uv run tools/fonts.py "<family>" --weight N`. If they own a paid font, they can drop the file in `fonts/private/` and use `{"family": "...", "file": "fonts/private/<file>", "weight": N}`.
3. Don't copy another creator's exact fonts and colours. Take the feel, not the trademark look.
4. Render `--looks <their-kit>` to check it, then build `sample-mine` as in step 4, and iterate in chat.

## 6. Finish

In about 3 lines, tell them:
- their look is saved and every reel will use it automatically
- how to edit a reel: drop a clip in `inbox/` or the chat and say "edit this reel". You cut it, they review the lines in chat, and you build it in their look.
- that pop-up graphics illustrate what they say; "show me the graphics" plays the catalogue of all 14 in their look
- optional extras: drop 6 of their own reels in the chat for the "reels orbiting you" effect and the profile grid (`tools/reels.py add`); give their real Instagram numbers once (saved to `brand/instagram.json`) for the follow animation
- that they can ask for a meme or GIF on any line ("the David Rose 'ew' meme here"). Searching needs a free GIPHY key, which you'll help them get the first time; their own GIF files work right away
- that colours and fonts are never locked: "use these colours instead" works on any reel, any time
- that they can change anything any time by just saying so ("captions smaller", "no sounds on this one", "try the Loud look on this reel")

- that finished reels land in the **Finished reels** folder
- the commands: **/new-reel** for a new clip (start a new chat in this folder for each reel), **/update** to get new versions, and **/report-problem** if something breaks

Then offer: "Want to edit the full clip you just gave me as your first real reel?" If yes, run the new-reel skill on it, in this chat.

## Kit style switches (for tweaks)

`kit.json` → `"style"`:
- `caption_outline`: px; 0 means a shadow only
- `caption_case`: "none" / "uppercase"
- `hook`: "card" / "bare" (no card, outlined text)
- `hook_size`
- `hook_case`
- `statement_case`
- `label`: "ticket" / "pill"
- `label_mark`: the symbol between name and topic
- `radius`
- `shadow` / `shadow_soft`: rgba colours

`"captions"`:
- `mode`: "karaoke" (words light up), "phrase" (whole phrase), "word" (one big word at a time)
- `size`
- `max_words`
- `position_y`

`"moves"`:
- `tilt_degrees`
- `highlighter_blocks`
