# Engine notes: what went wrong, and the rule that prevents it

Every failure the Lab has had, why it happened, and the defence now built in. Read this before changing anything in `tools/`. Add to it whenever something new breaks.

## Transcription

**1. Restarts said without a pause got merged (Oct 2026).**
- *What happened:* "while most of the… while most of the people" became one phrase, so the repeat survived the cut.
- *Why:* Whisper "cleans up" repeated phrases.
- *Defence:* Parakeet is the main transcriber because it writes down exactly what was said. Whisper is a fallback only.

**2. A word's timing swallowed a pause.**
- *What happened:* "business." was timed 38.24→40.48 when the voice stopped at 38.85, so 1.7s of dead air stayed in the cut.
- *Why:* speech models stretch the last word before a pause.
- *Defence:* word times are snapped to the real silences measured in the audio (`snap_to_silences`), for every engine.

**3. Model downloads stall.**
- *What happened:* Hugging Face downloads froze twice.
- *Defence:* download with `curl -C -` (resumable) into `models/`, and load models from there.

## Cutting

**4. Trusting the transcript's word edges.**
- *Why:* boundaries between run-together words are often 0.1–0.2s off.
- *Defence:* every cut lands on the real quiet point in the sound (`quiet_point`), at the seam closest to the kept word.

**5. A consonant's silence mistaken for a gap.**
- *What happened:* the 30ms silence inside "instea|d" was treated as the end of the word, which clipped it.
- *Defence:* a seam must be at least 40ms long, or clearly quieter than speech.

**6. Padding that reaches into the next word.**
- *What happened:* the breath added after "instead." picked up the "I" of a dropped line.
- *Defence:* padding never goes past the edge of the gap (`EDGE`).

**7. Pauses hidden inside a kept line.**
- *Defence:* any real silence over 0.28s inside a segment is cut out, whatever the word times say.

**8. Sentences glued with no air.**
- *What happened:* "…business. Let me" sounded like "…business. **So** let me".
- *Defence:* every join gets at least 0.18s of quiet (`MIN_JOIN`). If the recording doesn't have it, a tiny silence is added and the frame is held.

## Checking

**9. The checker had the same blind spot as the transcriber.**
- *What happened:* a Whisper-based check couldn't see the repeat that Whisper itself had merged, so it reported "OK" on a broken cut.
- *Defence:* `verify.py` listens with Parakeet and flags any phrase said twice in a row.

**10. Word comparison can't hear silence.**
- *Defence:* `verify.py` also measures every pause in the finished cut and flags anything over 0.35s.

**11. Never say "clean" without a fresh check.**
- *Rule:* run `verify.py` on the actual output after every change.
- *Rule:* when the checker flags something, prove whether it's real (listen to the junction, test the pieces apart and together) before changing the cut to please the checker.
- *Rule:* if it's ambiguous, tell the user the timestamp and let them listen.

## Rendering

**12. Full-screen moments vanished.**
- *What happened:* the browser saves fully opaque frames without transparency, and ffmpeg then dropped them during layering.
- *Defence:* every overlay frame is normalised to RGBA (`ensure_rgba`).

**13. Highlight blocks broke when a phrase wrapped onto two lines.**
- *Defence:* each emphasised word gets its own block.

**14. Graphics checked only in code.**
- *Rule:* after every build, look at frames at the hook, the label and each big moment before handing the reel over.

**15. The finished reel opened as a black screen.**
- *What happened:* QuickTime still had the previous `final.mp4` open. The new render overwrote that file in place, and the old window showed a black screen.
- *Why my check missed it:* I checked the file with ffmpeg, but never in the player the user actually opens.
- *Defence:* renders go to a temp file and are swapped in as a new file (`replace_into`). `open_video` closes any QuickTime window with that name before opening.
- *Check:* confirm playback with macOS's own engine (`qlmanage -t`), not only ffmpeg.

## 16. One sound used 18 times in a reel
- **What happened:** in Elena's onboarding test, a 1:50 reel played `soft_pop` on 18 of its 22 sound cues. When she asked "what are the other sounds?", the agent synthesised an audio preview on the spot, which was slow and awkward.
- **Root cause:** the Journal preset gave highlighted words a one-item sound list. Rotation can't vary a list of one, and nothing limited how often a sound could repeat or how dense highlight sounds got. There was also no ready-made way to hear the library.
- **Defence:**
  - Kits now pick a **sound set** (`sfx/palettes.json`) with 3+ sounds per moment.
  - `sfx_cues` never repeats a sound within 8s, caps each sound per reel length, spaces highlight sounds 3.5s apart, and picks silence over a repeat.
  - The build prints `SOUNDS=` with the counts.
  - `sfx/sound-menu.mp4` is pre-made, and the skill says never to generate previews.
- **Check:** after a build, no sound in `SOUNDS=` should exceed about 1 per 10 seconds of reel.

## 17. A count-up froze one short ("99" instead of "100+")
- **What happened:** the catalogue's number piece ended on 99.
- **Root cause:** the renderer reuses a frame whenever the stage returns the same key. The number's key used animation progress rounded to 30 steps. The last steps (98.3% → 100%) shared a key, so the final "100+" frame was never drawn.
- **Defence:** a piece's key must contain whatever text it shows, not just rounded progress. The number key now includes the shown value; typewriter, chat and scale keys already contain their character count or position.
- **Rule for new pieces:** if anything visible changes, the key must change.
- **Also found:** Awesome Serif maps "+" to a blank glyph. Numbers now draw their symbols (+ % € $) in the label font.

## 18. Feedback on the first pop-up reel (Elena, 2026-10-06)
1. **The statement covered the speaker for 4.8s.**
   - Cause: a statement spanned its whole line.
   - Defence: statements are a 1.6s slam (`STATEMENT_DUR`), started with `"word": i` on the word where the idea lands.
2. **The video "messed up" just before the statement.**
   - Cause: a caption jumped above the head for a few frames when the chat window ended, then the statement cut in.
   - Defence: auto-caption placement is decided once per caption, from everything that overlaps it, so captions never jump mid-phrase.
3. **The same words were on screen twice:** the "non-negotiables" pop and the "non-negotiables" caption.
   - Defence: captions hide while a word, number, strike or step pop-up shows the same words. The visuals skill asks for pops that condense or reframe rather than mirror.
4. **The chat window jumped and then sat idle.**
   - Cause: the input grew when the prompt wrapped, and nothing happened after typing.
   - Defence: fixed-size window. It types (one key click per letter, with the sound timed to the letters), sends (button press, swipe sound, the prompt becomes a bubble), then shows the AI thinking and an optional reply.
5. **Pop-ups were dropped near statement or behind moments.**
   - Defence: they now wait until the moment ends, or end just before it, instead of being skipped. `check.png` shows every pop-up for the agent to review.


## 19. Memes and GIFs: why the clip is laid in underneath
- **Problem:** the stage renders frames as browser screenshots, and a browser can't hold an animated GIF at an exact moment. GIFs drawn on the stage would play at the wrong speed and stutter.
- **Design:** the stage draws the card as a frame with a **see-through window**, and asks the browser where that window sits once the card has popped in (`gif_rects`). ffmpeg then lays the clip (converted to MP4 by `tools/memes.py`) *underneath* the graphics layer at exactly that rectangle and time.
  - The window stays filled with the card colour for its first 0.3s, until the clip fades in, so it never shows as an empty frame.
  - Tall clips go below the chin and wide ones above the head. The earlier of two pieces above the head makes way for the next.
  - When both the top and the chin area are busy, captions drop to the bottom of the screen.

## 20. Graphics under Instagram's own buttons (compared with the video-edit skill, 2026-10-06)
- **What happened:** captions could drop to 84–86% of the height and the name label sat at y 1500, both under Instagram's username, caption and audio row. Pop-ups could start at y 60 and run to y 1580. Nothing measured this.
- **Defence:** one safe zone, `SAFE` in `tools/lab.py` = `SAFE_ZONE` in `effects/stage.html`: bottom 1470, sides 35, the like / comment / share column (x > 980 below y 1155), top 170. All the zones, captions, the hook and the label stay inside it. Low captions narrow so they clear the button column. A hook that doesn't fit above a high head shrinks (to 85% at most) instead of riding into the header.
- **Check:** while rendering, `safeAudit()` measures every visible caption, hook, label and pop-up. The build prints `SAFE ZONE:` lines, and `verify.py --video final.mp4` repeats them.
- **Why the top is 170, not 220:** at 220, top pop-ups on a high-framed face shrank by a third and chat windows became unreadable. Instagram's header only uses the corners up there.

## 21. Every reel went out at whatever loudness the phone recorded
- **What happened:** the welcome sample measured -31.6 LUFS and Elena's test reels -26 to -27. Instagram plays at about -14, so these sounded quieter than every reel around them. Nothing measured loudness.
- **Defence:** `prepare_voice` filters rumble below 70 Hz and gently compresses the voice. The whole mix is then lifted to -14 LUFS, and a limiter keeps peaks under -1 dB. Sound effects keep the balance the kits were tuned at (voices around -26 LUFS, `SFX_TUNED_AT`) whatever the recording level.
- **Check:** the build prints `LOUDNESS=`, and `verify.py --video final.mp4` flags more than 2 LU off target or peaks over -0.5 dB.

## 22. Misheard names reached the captions
- **What happened:** captions come straight from the transcript's words, so fixing "cloud" → "Claude" in `cut.json` changed the review list but not the screen.
- **Defence:** `build.json` → `"spell": {"<word index>": "Claude"}` (and `""` to fold "Chat" "GPT" into "ChatGPT"), applied to captions only. Pop-up timing still uses the original words. The new-reel skill scans for misheard names, and `brand/names.txt` remembers them.

## 23. Several clips for one reel
- **Design:** `transcribe.py clip1 clip2 …` brings each clip to 1080×1920, 30 fps and PCM sound (an HDR clip becomes standard colour first). It adds 0.5 s of held frame and quiet after each clip and joins them into `source-joined.mov`. The quiet means no phrase or cut seam can run across two clips. `project.json` → `clips` holds where each clip starts, and `lines.md` marks it. Everything after that treats it as one clip, so retake picking works across clips. The originals are never touched. The beta length limit applies to the total.

## 24. Close-ups put graphics on the face
- **Found while testing:** pop-ups were placed around the face as measured on the un-zoomed cut. During a 1.5× close-up, the face is 1.5× bigger, so a top pop-up landed on the eyes.
- **Defence:** the zoom plan goes into the timeline *before* the graphics render. `stage.html` (`zoomAt`, `zoomedSafe`) recomputes the face box for every frame's framing (jump zooms, punch-ins, close-ups, push-ins), so zones, captions and the hook follow the real face.

## 25. Soft zooms on a 1080 cut
- **Problem:** zooming 1.5× into a 1080×1920 cut upscales it, and it looks soft.
- **Defence:** when a reel has real zooms and the source is 4K, `roughcut.render_hq` makes a 4K copy of the same cut (hardware-encoded, cached per segment). The zoom is then taken from it. The first build takes about 30 s longer; later builds reuse it.

