"""Build the finished reel: the locked rough cut + the user's kit → final.mp4.

Usage:
  uv run tools/build.py projects/<name> [--kit elena] [--no-open]
  uv run tools/build.py projects/<name> --sheet      # kit sheet: every piece in the kit over this footage
  uv run tools/build.py projects/<name> --looks presets [--left "NAME" --right "TOPIC"]   # pick-a-look sheet
  uv run tools/build.py projects/<name> --kit bold --out sample-bold                      # build under another name

Claude writes projects/<name>/build.json first (what goes where, chosen by the kit's rules):
{
  "captions": {"mode": "karaoke"},                       # optional override of the kit's mode
  "highlight_words": [27, 103],                          # word indexes that get a highlighter block
  "events": [
    {"type": "hook", "line": 1, "eyebrow": "Stop debating", "text": "Build your *business brain*"},
    {"type": "label", "at_line": 3},
    {"type": "statement", "line": 13, "text": "Work *across* them"}
  ]
}
- "line" = the cut line the event sits on (its timing follows that line); or give "start"/"end" in seconds.
- *word* = the brand's italic / highlighted emphasis word.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import FPS, H, LAB, W, fmt_t, load_json, open_video, replace_into, run, save_json
import faces as facefinder
import memes as mem
import fonts

STAGE = LAB / "effects" / "stage.html"
PUNCT_BREAK = ".?!,;:"


def load_kit(name):
    p = LAB / "packs" / name / "kit.json"
    if not p.exists():
        raise SystemExit(f"No kit called '{name}' in packs/")
    kit = load_json(p)
    for f in kit["fonts"].values():
        if f.get("file"):
            fp = LAB / f["file"]
            if not fp.exists():
                raise SystemExit(f"Kit font missing: {f['file']}")
        elif f.get("google"):
            fp = fonts.fetch(f["family"], f.get("weight", 400), f.get("italic", False))
        else:
            continue
        f["url"] = fp.as_uri()
    return kit


def kit_names():
    return sorted(p.parent.name for p in (LAB / "packs").glob("*/kit.json"))


def default_kit():
    p = LAB / "brand" / "kit.txt"
    return p.read_text().strip() if p.exists() else "elena"


def out_words(proj):
    """Every kept word with its time in the finished video."""
    edl = load_json(proj / "edl.json")
    words = load_json(proj / "transcript.json")["words"]
    out = []
    for sg in edl["segments"]:
        a, b = sg["words"]
        for w in words[a:b + 1]:
            s = sg["out_start"] + (max(w["s"], sg["start"]) - sg["start"])
            e = sg["out_start"] + (min(w["e"], sg["end"]) - sg["start"])
            out.append({"i": w["i"], "w": w["w"], "s": round(s, 3), "e": round(e, 3)})
    return out, edl


def line_of_word(edl, i):
    for ln in edl["lines"]:
        if ln["words"][0] <= i <= ln["words"][1]:
            return ln["line"]
    return None


def caption_chunks(words, edl, max_words, highlight):
    """Short caption groups: break at punctuation, at line ends, at pauses, or at max_words."""
    chunks, cur = [], []
    for k, w in enumerate(words):
        cur.append({"w": w["w"], "s": w["s"], "e": w["e"], "hl": w["i"] in highlight})
        nxt = words[k + 1] if k + 1 < len(words) else None
        end_here = (
            nxt is None or len(cur) >= max_words or w["w"][-1] in PUNCT_BREAK
            or line_of_word(edl, w["i"]) != line_of_word(edl, nxt["i"])
            or nxt["s"] - w["e"] > 0.35
        )
        if end_here:
            chunks.append(cur)
            cur = []
    out = []
    for k, c in enumerate(chunks):
        start = c[0]["s"]
        end = chunks[k + 1][0]["s"] if k + 1 < len(chunks) else c[-1]["e"] + 0.4
        end = min(end, c[-1]["e"] + 0.6)          # don't hold a caption through a long pause
        out.append({"start": round(start, 3), "end": round(end, 3), "words": c})
    return out


STATEMENT_DUR = 1.6


def resolve_events(plan, edl, total, words=()):
    lines = {ln["line"]: ln for ln in edl["lines"]}
    by_i = {w["i"]: w for w in words}
    evs = []
    for ev in plan.get("events", []):
        ev = dict(ev)
        if "word" in ev and ev["word"] in by_i:            # start on a spoken word
            ev["start"] = max(by_i[ev.pop("word")]["s"] - 0.1, 0.0)
            ev.setdefault("end", ev["start"] + 2.0)
        if "line" in ev and "start" not in ev:
            ln = lines[ev["line"]]
            ev["start"], ev["end"] = ln["out_start"], ln["out_end"]
        if ev["type"] == "hook":
            ev.setdefault("start", 0.0)
            ev["start"] = 0.0 if ev.get("line") == 1 else ev["start"]
            ev["end"] = max(ev.get("end", 3.0), ev["start"] + 3.0)
        if ev["type"] == "label":
            at = lines[ev.get("at_line", 2)]["out_start"] if "start" not in ev else ev["start"]
            ev["start"], ev["end"] = at, at + 3.2
        if ev["type"] == "statement":
            # a slam, not a slide: about 1.6s from its word (or the line start), then back to the speaker
            ev["end"] = ev["start"] + ev.get("dur", STATEMENT_DUR)
        if ev["type"] == "behind":
            ev["end"] = max(ev["end"], ev["start"] + 1.5)
            if ev.get("image"):
                img = Path(ev["image"]).expanduser()
                img = img if img.is_absolute() else LAB / img
                if not img.exists():
                    raise SystemExit(f"Behind image not found: {ev['image']}")
                ev["image_url"] = img.resolve().as_uri()
        ev["end"] = min(ev["end"], total)
        evs.append(ev)
    return evs


ICONS = LAB / "effects" / "icons.json"
VISUAL_DUR = {"gif": 2.6, "word": 1.8, "number": 2.2, "strike": 2.4, "chat": 3.5, "notify": 2.4, "step": 2.6, "phone": 3.0,
              "person": 2.6, "versus": 3.2, "scale": 3.0, "checklist": 3.0, "hub": 3.5, "flow": 3.0, "chips": 2.8}


def resolve_visuals(plan, edl, words, total, events=()):
    """Pop-up pieces from build.json → times in the finished reel.
    Timing keys: "word": i starts it as word i is said; "line": n spans that line; "start"/"end" in seconds;
    "until_word": j ends it after word j. Items take "word" too (each pops in as it's said).
    Any other "<name>_word": i becomes "<name>_t" (e.g. strike_word, reply_word, right_word, move_word, close_word)."""
    lines = {ln["line"]: ln for ln in edl["lines"]}
    at = {w["i"]: w for w in words}

    def wt(i, edge="s"):
        if i not in at:
            raise SystemExit(f"Visual points at word {i}, which isn't in the cut")
        return at[i][edge]
    icons = load_json(ICONS) if ICONS.exists() else {}
    blockers = [e for e in events if e["type"] in ("statement", "behind")]
    out, used = [], set()
    for v in plan.get("visuals", []):
        v = json.loads(json.dumps(v))
        if "word" in v:
            v["start"] = max(wt(v.pop("word")) - 0.12, 0.0)
        elif "line" in v and "start" not in v:
            v["start"] = lines[v["line"]]["out_start"]
            v.setdefault("end", lines[v["line"]]["out_end"] + 0.3)
        v.setdefault("start", 0.0)
        for key in [k for k in v if k.endswith("_word")]:
            name = "close_start" if key == "close_word" else key[:-5] + "_t"
            v[name] = wt(v.pop(key)) - 0.05
        items = v.get("items") or v.get("nodes") or []
        for it in items:
            if isinstance(it, dict) and "word" in it:
                it["t"] = wt(it.pop("word")) - 0.08
            if isinstance(it, dict) and it.get("icon"):
                used.add(it["icon"])
        for k in ("icon",):
            if v.get(k):
                used.add(v[k])
        for side in ("left", "right", "center"):
            if isinstance(v.get(side), dict) and v[side].get("icon"):
                used.add(v[side]["icon"])
        last = max([it["t"] for it in items if isinstance(it, dict) and "t" in it] + [v["start"]])
        if "until_word" in v:
            v["end"] = wt(v.pop("until_word"), "e") + 0.5
        if "end" not in v:
            v["end"] = max(v["start"] + v.pop("dur", VISUAL_DUR.get(v["kind"], 2.5)), last + 1.4)
        v["end"] = min(v["end"], total)
        # a full-screen statement or a behind-the-head moment owns the screen: pop-ups end before it starts
        for ev in blockers:
            if ev["start"] <= v["start"] < ev["end"]:          # starts inside: wait until it's over
                v["start"] = ev["end"] + 0.05
            if v["start"] < ev["start"] < v["end"]:            # runs into it: end just before
                v["end"] = ev["start"] - 0.05
        if v["end"] - v["start"] < 0.6:
            print(f"Skipped a {v['kind']} pop-up at {fmt_t(v['start'])}: it falls inside a statement or behind moment")
            continue
        if v["kind"] == "gif":
            f = Path(v.get("file", "")).expanduser()
            f = f if f.is_absolute() else LAB / f
            if not f.exists():
                raise SystemExit(f"Meme file not found: {v.get('file')}")
            v["file"] = str(f.resolve())
            gw, gh, gd = mem.probe(f)
            v["w"], v["h"] = gw, gh
            if v.get("at") == "full":
                v["end"] = min(v["end"], v["start"] + v.get("dur", 1.6))
            elif not v.get("at"):
                v["at"] = "chest" if gh > gw * 1.1 else "top"     # tall clips below the chin, wide ones above the head
            v["_i"] = len(out)
        if v.get("image"):
            img = Path(v["image"]).expanduser()
            img = img if img.is_absolute() else LAB / img
            if not img.exists():
                raise SystemExit(f"Image not found: {v['image']}")
            v["image_url"] = img.resolve().as_uri()
        out.append(v)
    # two pieces never share the band above the head: the earlier one makes way
    def top_band(v):
        if v.get("at"):
            return v["at"] in ("top", "full")
        return v["kind"] not in ("person", "phone", "chips")
    out.sort(key=lambda v: v["start"])
    prev = None
    for v in out:
        if not top_band(v):
            continue
        if prev and v["start"] < prev["end"]:
            if v["start"] - 0.05 - prev["start"] >= 0.8:
                prev["end"] = v["start"] - 0.05
            else:
                v["start"] = prev["end"] + 0.05
        prev = v
    out = [v for v in out if v["end"] - v["start"] >= 0.6]
    for k, v in enumerate(out):
        if v["kind"] == "gif":
            v["_i"] = k
    used |= {"check", "x", "arrow-up", "bell", "user", "sparkles", "circle"}
    missing = sorted(n for n in used if n not in icons)
    if missing:
        raise SystemExit(f"Unknown icon(s): {', '.join(missing)}. Find names with: uv run tools/icons.py <word>")
    return out, {n: icons[n] for n in used if n in icons}


TYPE_RATE = {"chat": (0.45, 0.045), "word": (0.0, 0.055)}
CHAT_SEND_PAUSE = 0.35                                          # typed → sent    # must match visuals.js: (delay, seconds per character)


def typing_cues(proj, visuals):
    """A typing sound for everything typed on screen: one soft key click per character, timed to the animation."""
    import numpy as np
    import wave
    import make_sfx as mk
    out, d = [], proj / "sfx"
    d.mkdir(exist_ok=True)
    for k, v in enumerate(visuals):
        if v["kind"] == "chat":
            text = v.get("prompt", "")
        elif v["kind"] == "word" and v.get("style") == "type":
            text = v["text"].replace("*", "")
        else:
            continue
        delay, rate = TYPE_RATE[v["kind"]]
        rng = np.random.default_rng(k + 7)
        dur = len(text) * rate + 0.2
        items = []
        for c, ch in enumerate(text):
            if ch == " " and rng.random() < 0.5:
                continue                                    # spaces are softer; some barely register
            lvl = (0.35 if ch == " " else 0.55) + 0.35 * rng.random()
            items.append((c * rate + rng.normal(0, 0.006), mk.click_burst(0.010, 1700 + rng.integers(-350, 650), 100 + c, lvl)))
        x = mk.place(dur, [(max(t, 0.0), snd) for t, snd in items])
        x = x / (np.max(np.abs(x)) + 1e-9) * 10 ** (-9 / 20)
        st = (np.stack([x, x], axis=1) * 32767).astype(np.int16)
        f = d / f"typing-{k}.wav"
        with wave.open(str(f), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(mk.SR); w.writeframes(st.tobytes())
        out.append({"at": round(v["start"] + delay, 3), "sfx": str(f)})
        if v["kind"] == "chat":
            send = v["start"] + delay + len(text) * rate + CHAT_SEND_PAUSE
            if send < v["end"] - 0.3:
                out.append({"at": round(send, 3), "sfx": "swipe"})
        v["sfx"] = False                                       # the typing replaces the pop-up's own sound
    return out


def gif_rects(timeline):
    """Ask the stage where each meme card's window sits once it has popped in: [x, y, w, h] in pixels."""
    gifs = [v for v in timeline.get("visuals", []) if v["kind"] == "gif" and v.get("at") != "full"]
    if not gifs:
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(STAGE.as_uri())
        pg.evaluate("tl => window.setup(tl)", timeline)
        pg.wait_for_timeout(300)
        for v in gifs:
            t = min(v["start"] + 0.8, (v["start"] + v["end"]) / 2)
            pg.evaluate(f"window.renderAt({t:.3f}, 'front')")
            r = pg.evaluate(f"(() => {{ const e = document.querySelector('[data-gif=\"{v['_i']}\"]'); if (!e) return null;"
                            f" const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }})()")
            if r:
                x, y, w, h = [int(round(z)) for z in r]
                v["rect"] = [x, y, w - w % 2, h - h % 2]
        b.close()


def face_sides(fdata):
    """Left and right edges of the face (stage pixels), so pop-ups can sit beside the head."""
    xs = [f["box"] for f in fdata.get("frames", []) if "box" in f]
    if not xs:
        return None, None
    lefts = sorted(b[0] for b in xs)
    rights = sorted(b[0] + b[2] for b in xs)
    return round(lefts[len(lefts) // 10] * W) - 40, round(rights[len(rights) * 9 // 10] * W) + 40

def ensure_rgba(png: Path):
    """Chromium saves fully opaque frames (e.g. a full-screen statement) without an alpha
    channel. Mixed with transparent frames, ffmpeg then drops them. Normalise to RGBA."""
    with open(png, "rb") as fh:
        head = fh.read(26)
    if head[25] != 6:                      # PNG colour type 6 = RGBA
        tmp = png.with_suffix(".rgba.png")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(png), "-pix_fmt", "rgba", str(tmp)])
        tmp.replace(png)


def render_overlay(timeline, total, out_dir, times=None, layer="front"):
    """Render the stage frame by frame (transparent PNGs). Identical frames are rendered once."""
    from playwright.sync_api import sync_playwright
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    n = int(round(total * FPS))
    frames = times if times is not None else [k / FPS for k in range(n)]
    entries, last_key, last_file, rendered = [], None, None, 0
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(STAGE.as_uri())
        pg.evaluate("tl => window.setup(tl)", timeline)
        pg.wait_for_timeout(300)
        for k, t in enumerate(frames):
            key = pg.evaluate(f"window.renderAt({t:.4f}, '{layer}')")
            if key != last_key or times is not None:
                f = out_dir / f"f{k:06d}.png"
                pg.screenshot(path=str(f), omit_background=True, clip={"x": 0, "y": 0, "width": W, "height": H})
                ensure_rgba(f)
                last_key, last_file = key, f
                rendered += 1
                entries.append([f, 1])
            else:
                entries[-1][1] += 1
        b.close()
    return entries, rendered


def zoom_plan(edl, plan, kit, total):
    """Framing over time.
    - Jump zoom: at each cut the framing alternates between normal and slightly closer.
      That's how editors hide jump cuts.
    - Punch-ins: lines Claude picked for emphasis get a quick push closer.
    Returns (start, end, scale) steps."""
    z = kit.get("zoom", {})
    jump = z.get("jump", 1.0)
    steps, k, flip = [], 0, False
    for sg in edl["segments"]:
        steps.append((sg["out_start"], sg["out_end"], jump if flip else 1.0))
        nxt = edl["segments"][k + 1] if k + 1 < len(edl["segments"]) else None
        contiguous = nxt and nxt["words"][0] == sg["words"][1] + 1 and nxt["start"] - sg["end"] < 0.6
        if not contiguous:
            flip = not flip                       # only flip where the picture actually jumps
        k += 1
    lines = {ln["line"]: ln for ln in edl["lines"]}
    punches = []
    for zm in plan.get("zooms", []):
        if "line" in zm:
            ln = lines[zm["line"]]
            punches.append((ln["out_start"], ln["out_end"], zm.get("scale", z.get("punch", 1.15))))
        else:
            punches.append((zm["start"], zm["end"], zm.get("scale", z.get("punch", 1.15))))
    return steps, punches, z.get("face_y", 0.38)


def zoom_filter(steps, punches, face_y):
    if all(s[2] == 1.0 for s in steps) and not punches:
        return None
    base = "+".join(f"between(it,{a:.3f},{b - 0.001:.3f})*{sc:.3f}" for a, b, sc in steps) or "1"
    # a punch eases in over 0.15 s and back out over 0.15 s, multiplied on top of the base framing
    ramp = "+".join(f"({sc - 1:.3f})*clip((it-{a:.3f})/0.15,0,1)*clip(({b:.3f}-it)/0.15,0,1)" for a, b, sc in punches) or "0"
    z = f"max(1,({base}))*(1+{ramp})"
    # keep the face height fixed while zooming (x centred, y anchored at face_y of the frame)
    return (f"zoompan=z='{z}':x='(iw-iw/zoom)/2':y='{face_y}*(ih-ih/zoom)':d=1:s={W}x{H}:fps={FPS}")


SFX_GAP = 3.5            # seconds between any two sounds on highlighted words
SFX_SAME_GAP = 8.0       # the same sound never plays again within this many seconds
KIND_SFX = {"notify": "blip"}   # chat and typewriter words get a typing track instead   # pop-ups with a natural sound of their own
SFX_PER_20S = 2          # each sound plays at most this many times per 20 seconds of reel


def sfx_options(kit):
    """The kit's sound lists per moment: from its palette (sfx/palettes.json), then any per-moment overrides."""
    sx = dict(kit.get("sfx") or {})
    pal = sx.get("palette")
    if pal:
        palettes = load_json(LAB / "sfx" / "palettes.json")
        if pal not in palettes:
            raise SystemExit(f"No sound set called '{pal}' (sets: {', '.join(k for k in palettes if not k.startswith('_'))})")
        sx = {**{k: v for k, v in palettes[pal].items() if k != "feel"}, **sx}
    avoid, more = set(sx.get("avoid", [])), sx.get("favour", [])
    for k, v in list(sx.items()):
        if k in ("hook", "label", "statement", "highlight", "visual") and isinstance(v, list):
            v = [n for n in v if n not in avoid]
            sx[k] = [n for n in more if n not in v and k == "highlight"] + v   # favourites lead the rotation
    return sx


def sfx_cues(timeline, kit, overrides=None, total=None):
    """Sound effects on the moments, quiet under the voice.
    Each moment type has a list of fitting sounds (from the kit's sound set); they rotate, a sound never
    repeats within SFX_SAME_GAP seconds, each is capped per reel length, and highlight sounds are spaced
    out, so a long reel doesn't become 18 identical pops (ENGINE-NOTES #16).
    build.json can pin a sound per event ("sfx": "ding") or add extra cues; pinned sounds are always played."""
    sx = sfx_options(kit)
    if not any(isinstance(v, (list, str)) and v for k, v in sx.items() if k not in ("volume_db", "palette", "library")):
        return []
    total = total or max([c["end"] for c in timeline["captions"]] + [1.0])
    cap = max(2, int(round(total / 20 * SFX_PER_20S)))

    def options(kind):
        v = sx.get(kind)
        return [v] if isinstance(v, str) else list(v or [])
    raw = []
    for ev in timeline["events"]:
        lead = 0.18 if ev["type"] == "statement" else 0.0      # a whoosh lands as the text slams in
        raw.append([max(ev["start"] - lead, 0.0), ev.get("sfx") or ev["type"], bool(ev.get("sfx"))])
    for v in timeline.get("visuals", []):
        pin = v.get("sfx") or KIND_SFX.get(v["kind"])
        if v.get("sfx") is not False:
            raw.append([v["start"], pin or "visual", bool(pin)])
    for c in timeline["captions"]:
        for w in c["words"]:
            if w.get("hl"):
                raw.append([w["s"], "highlight", False])
    for cue in (overrides or []):                                  # extra sounds Claude placed: {"at": 12.3, "sfx": "keyboard"}
        raw.append([cue["at"], cue["sfx"], True])
    raw.sort()
    turn, cues, last_at, count, last_hl = {}, [], {}, {}, -99.0
    for t, kind, pinned in raw:
        if pinned:
            name = kind
        else:
            if kind in ("highlight", "visual") and t - last_hl < SFX_GAP:
                continue
            opts = options(kind)
            name = None
            k = turn.get(kind, 0)
            for step in range(len(opts)):                          # next in rotation that's allowed here
                cand = opts[(k + step) % len(opts)]
                if t - last_at.get(cand, -99) >= SFX_SAME_GAP and count.get(cand, 0) < cap \
                        and (not cues or cues[-1][1] != cand):
                    name = cand
                    turn[kind] = k + step + 1
                    break
            if name is None:
                continue                                           # silence beats a repeat
            if kind in ("highlight", "visual"):
                last_hl = t
        last_at[name] = t
        count[name] = count.get(name, 0) + 1
        cues.append((t, name))
    return [(t, n) for t, n in cues if sfx_file(n).exists()]


def sfx_file(name):
    """A library sound by name, or a sound made for this reel (a path, e.g. the typing tracks)."""
    return Path(name) if name.endswith(".wav") else LAB / "sfx" / f"{name}.wav"


def write_concat(entries, path):
    lines = ["ffconcat version 1.0"]
    for f, count in entries:
        lines += [f"file '{f.as_posix()}'", f"duration {count / FPS:.6f}"]
    lines.append(f"file '{entries[-1][0].as_posix()}'")
    path.write_text("\n".join(lines) + "\n")
    return path


def render_base(proj, zoom):
    """The cut with its zooms baked in. Needed when someone has to be cut out of the zoomed picture."""
    out = proj / "base.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(proj / "rough.mp4"), "-vf", f"{zoom},setsar=1" if zoom else "null",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-c:a", "copy", str(out)])
    return out


def person_masks(proj, base, windows):
    """Cut-out masks of the speaker for each 'behind' moment (Apple Vision)."""
    matte = LAB / "tools" / "bin" / "matte"
    src = LAB / "tools" / "matte.swift"
    if not matte.exists() or matte.stat().st_mtime < src.stat().st_mtime:
        run(["swiftc", "-O", "-target", "arm64-apple-macos13", str(src), "-o", str(matte)])
    dirs = []
    for k, (a, b) in enumerate(windows):
        d = proj / "masks" / f"w{k}"
        if d.exists():
            shutil.rmtree(d)
        (d / "in").mkdir(parents=True)
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(base),
             "-vf", f"fps={FPS}", "-q:v", "2", str(d / "in" / "f%05d.jpg")])
        run([str(matte), str(d / "in"), str(d / "out")])
        dirs.append(d / "out")
    return dirs


def composite(proj, entries, out_name, zoom=None, cues=(), sfx_db=-14, behind=None, gifs=()):
    """Layers, bottom to top: the video → anything 'behind' the speaker → the speaker cut out
    again (only during those moments) → captions and graphics. Plus sound effects."""
    front = write_concat(entries, proj / "overlay.ffconcat")
    src = behind["base"] if behind else proj / "rough.mp4"
    inputs = ["-i", str(src), "-f", "concat", "-safe", "0", "-i", str(front)]
    n_win = 0
    if behind:
        inputs += ["-f", "concat", "-safe", "0", "-i", str(write_concat(behind["entries"], proj / "behind.ffconcat"))]
        for d in behind["masks"]:
            inputs += ["-framerate", str(FPS), "-i", str(d / "f%05d.png")]
        n_win = len(behind["masks"])
    first_gif = 2 + (1 + n_win if behind else 0)
    for g in gifs:
        inputs += ["-stream_loop", "-1", "-i", str(g["file"])]
    first_sfx = first_gif + len(gifs)
    for t, name in cues:
        inputs += ["-i", str(sfx_file(name))]

    if behind:
        fc = f"[0:v]split={n_win + 1}[bb]" + "".join(f"[w{i}]" for i in range(n_win)) + ";"
        fc += f"[2:v]fps={FPS},format=rgba[bh];[bb][bh]overlay=0:0:eof_action=pass[bg0];"
        for i, (a, b) in enumerate(behind["windows"]):
            fc += (f"[w{i}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[wt{i}];"
                   f"[{3 + i}:v]format=gray,scale={W}:{H}[m{i}];"
                   f"[wt{i}][m{i}]alphamerge,setpts=PTS+{a:.3f}/TB[fg{i}];"
                   f"[bg{i}][fg{i}]overlay=0:0:eof_action=pass[bg{i + 1}];")
        fc += f"[bg{n_win}]null[base];"
    else:
        fc = f"[0:v]{zoom},setsar=1[base];" if zoom else "[0:v]null[base];"
    # memes / GIFs: laid in under the graphics, so their card frame and caption sit on top
    for k, g in enumerate(gifs):
        a, b = g["start"], g["end"]
        d = b - a
        fin, fout = (a + 0.05, max(b - 0.2, a + 0.1)) if g["full"] else (a + 0.28, max(b - 0.3, a + 0.4))
        fc += f"[{first_gif + k}:v]trim=duration={d:.3f},setpts=PTS-STARTPTS+{a:.3f}/TB,fps={FPS},"
        if g["full"]:
            fc += (f"split[ga{k}][gb{k}];[ga{k}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=24:2[gbg{k}];"
                   f"[gb{k}]scale={W}:{H}:force_original_aspect_ratio=decrease[gfg{k}];[gbg{k}][gfg{k}]overlay=(W-w)/2:(H-h)/2,")
            x, y = 0, 0
        else:
            x, y, w, h = g["rect"]
            fc += f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        fc += (f"format=rgba,fade=in:st={fin:.3f}:d=0.15:alpha=1,fade=out:st={fout:.3f}:d=0.15:alpha=1[g{k}];"
               f"[{'base' if k == 0 else f'gb_{k}'}][g{k}]overlay={x}:{y}:eof_action=pass[gb_{k + 1}];")
    top = f"gb_{len(gifs)}" if gifs else "base"
    fc += f"[1:v]fps={FPS},format=rgba[ov];[{top}][ov]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]"
    amap = "0:a"
    if cues:
        parts = []
        for k, (t, name) in enumerate(cues):
            ms = int(round(t * 1000))
            fc += f";[{k + first_sfx}:a]adelay={ms}|{ms},volume={sfx_db}dB[s{k}]"
            parts.append(f"[s{k}]")
        fc += f";[0:a]{''.join(parts)}amix=inputs={len(cues) + 1}:normalize=0:duration=first[a]"
        amap = "[a]"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc,
         "-map", "[v]", "-map", amap, "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-maxrate", "14M", "-bufsize", "28M",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(proj / f"tmp-{out_name}")])
    replace_into(proj / f"tmp-{out_name}", proj / out_name)


def make_cover(proj, kit, timeline, fdata, plan, name="cover.jpg"):
    """Cover image: the best-looking frame of the speaker + the title in the kit's style.
    Title stays inside the 3:4 area Instagram shows on the profile grid."""
    c = plan.get("cover", {})
    if c is False:
        return None
    hook = next((e for e in timeline["events"] if e["type"] == "hook"), {})
    text = c.get("text") or hook.get("text")
    if not text:
        return None
    t = c.get("at") or facefinder.best_cover_time(fdata) or 1.0
    frame = proj / "cover-frame.png"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(proj / "rough.mp4"), "-frames:v", "1", str(frame)])
    tl = {"kit": timeline["kit"], "safe": timeline.get("safe"), "captions": [],
          "events": [{"type": "cover", "start": 0, "end": 9, "text": text, "eyebrow": c.get("eyebrow", hook.get("eyebrow"))}]}
    entries, _ = render_overlay(tl, 1.0, proj / "cover-overlay", times=[0.5])
    out = proj / name
    run(["ffmpeg", "-v", "error", "-y", "-i", str(frame), "-i", str(entries[0][0]),
         "-filter_complex", "[0:v][1:v]overlay=0:0", "-frames:v", "1", "-q:v", "2", str(out)])
    return out


def build(proj, kit_name, no_open, out="final"):
    t0 = time.time()
    kit = load_kit(kit_name)
    plan = load_json(proj / "build.json") if (proj / "build.json").exists() else {}
    if plan.get("captions", {}).get("mode"):
        kit["captions"]["mode"] = plan["captions"]["mode"]
    if plan.get("sound_set"):                     # one reel in a different sound set: "use the clicky sounds here"
        kit["sfx"] = {**{k: v for k, v in (kit.get("sfx") or {}).items() if k in ("volume_db", "avoid", "favour")},
                      "palette": plan["sound_set"]}
    words, edl = out_words(proj)
    total = edl["total"]
    fdata = facefinder.analyse(proj)
    fs = fdata.get("summary")
    if fs:
        kit.setdefault("zoom", {})["face_y"] = fs["centre_y"]     # zoom around the real face
    timeline = {
        "kit": kit,
        "safe": {"face_top": round(fs["top"] * H), "face_bottom": round(fs["bottom"] * H)} if fs else None,
        "captions": caption_chunks(words, edl, kit["captions"]["max_words"], set(plan.get("highlight_words", []))),
        "events": resolve_events(plan, edl, total, words),
    }
    timeline["visuals"], timeline["icons"] = resolve_visuals(plan, edl, words, total, timeline["events"])
    if timeline["safe"]:
        timeline["safe"]["face_left"], timeline["safe"]["face_right"] = face_sides(fdata)
    save_json(proj / "timeline.json", timeline)
    gif_rects(timeline)
    entries, rendered = render_overlay(timeline, total, proj / "overlay")
    steps, punches, face_y = zoom_plan(edl, plan, kit, total)
    typed = typing_cues(proj, timeline["visuals"]) if plan.get("sfx", True) else []
    cues = sfx_cues(timeline, kit, (plan.get("sfx_extra") or []) + typed, total) if plan.get("sfx", True) else []
    timeline["zoom"] = {"steps": steps, "punches": punches}
    timeline["sfx"] = cues
    save_json(proj / "timeline.json", timeline)
    zf = zoom_filter(steps, punches, face_y)
    behind = None
    windows = [(e["start"], e["end"]) for e in timeline["events"] if e["type"] == "behind"]
    if windows:
        base = render_base(proj, zf)
        b_entries, _ = render_overlay(timeline, total, proj / "overlay-behind", layer="behind")
        behind = {"base": base, "entries": b_entries, "windows": windows,
                  "masks": person_masks(proj, base, windows)}
    gifs = [{"file": v["file"], "start": v["start"], "end": v["end"], "full": v.get("at") == "full", "rect": v.get("rect")}
            for v in timeline["visuals"] if v["kind"] == "gif" and (v.get("at") == "full" or v.get("rect"))]
    composite(proj, entries, f"{out}.mp4", zf, cues, kit.get("sfx", {}).get("volume_db", -14), behind, gifs)
    print(f"Built {fmt_t(total)} reel in {time.time() - t0:.0f}s with the '{kit['name']}' kit "
          f"({len(timeline['captions'])} captions, {len(timeline['events'])} moments, {len(punches)} punch-ins, "
          f"{len(cues)} sound effects, {rendered} unique frames).")
    if cues:
        from collections import Counter
        sset = (kit.get("sfx") or {}).get("palette") or "kit's own list"
        print(f"SOUNDS=set: {sset}; " + ", ".join(f"{n} ×{c}" for n, c in Counter("typing" if n.endswith(".wav") else n for _, n in cues).most_common()))
    cover = make_cover(proj, kit, timeline, fdata, plan, out.replace("final", "cover") + ".jpg")
    check_sheet(proj, timeline, proj / f"{out}.mp4")
    if out == "final":                                   # an easy-to-find copy for posting
        fin = LAB / "Finished reels"
        fin.mkdir(exist_ok=True)
        shutil.copy2(proj / "final.mp4", fin / f"{proj.name}.mp4")
        if cover:
            shutil.copy2(cover, fin / f"{proj.name} cover.jpg")
        print(f"FINISHED={fin / (proj.name + '.mp4')}")
    print(f"FINAL={proj / f'{out}.mp4'}")
    if cover:
        print(f"COVER={cover}")
    if not no_open:
        open_video(proj / f"{out}.mp4")


def sheet(proj, kit_name, no_open):
    """Kit sheet: the kit's pieces over this footage, side by side in one image."""
    kit = load_kit(kit_name)
    words, edl = out_words(proj)
    sample = [w for w in words[:12]]
    for w in sample:
        w["s"], w["e"] = 0.0, 0.1
    picked = sample[:kit['captions']['max_words']]
    longest = max(range(len(picked)), key=lambda k: len(picked[k]["w"]))   # highlight a word that carries meaning
    active_k = 0 if longest != 0 else 1
    cap = {"start": 0, "end": 99, "words": [{"w": w["w"], "s": 0.0 if k <= active_k else 0.5, "e": 1, "hl": k == longest}
                                              for k, w in enumerate(picked)]}
    for w in cap["words"]:
        w["s"] = 0.0 if w is cap["words"][active_k] else (0.0 if cap["words"].index(w) < active_k else 0.0)
    timelines = [
        ("Hook", {"captions": [], "events": [{"type": "hook", "start": 0, "end": 99, "eyebrow": "Your hook goes", "text": "right *here*, up top"}]}),
        ("Captions", {"captions": [cap], "events": []}),
        ("Big moment", {"captions": [], "events": [{"type": "statement", "start": 0, "end": 99, "text": "One *big* idea"}]}),
        ("Label", {"captions": [cap], "events": [{"type": "label", "start": 0, "end": 99}]}),
    ]
    out_dir = proj / "kitsheet"
    out_dir.mkdir(exist_ok=True)
    frame = out_dir / "frame.png"
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(min(3.0, edl["total"] / 2)), "-i", str(proj / "rough.mp4"),
         "-frames:v", "1", str(frame)])
    tiles = []
    for k, (title, tl) in enumerate(timelines):
        tl["kit"] = kit
        entries, _ = render_overlay(tl, 2.0, out_dir / f"t{k}", times=[1.0])
        tile = out_dir / f"tile{k}.png"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(frame), "-i", str(entries[0][0]),
             "-filter_complex", "[0:v][1:v]overlay=0:0,scale=540:960", "-frames:v", "1", str(tile)])
        tiles.append(tile)
    out = proj / f"kitsheet-{kit_name}.png"
    run(["ffmpeg", "-v", "error", "-y", *sum([["-i", str(t)] for t in tiles], []),
         "-filter_complex", f"hstack=inputs={len(tiles)}", "-frames:v", "1", str(out)])
    print(f"SHEET={out}")
    if not no_open:
        subprocess.run(["open", str(out)])


def check_sheet(proj, timeline, video):
    """One image with a frame from every moment and pop-up (when each is fully on screen), for Claude to look at
    before handing the reel back: off-screen, unreadable, covering the face, colliding."""
    moments = [(e["type"], e["start"] + min(1.2, (e["end"] - e["start"]) * 0.6)) for e in timeline["events"]]
    moments += [(v["kind"], max(v["start"] + 0.5, v["end"] - 0.35)) for v in timeline.get("visuals", [])]
    moments.sort(key=lambda m: m[1])
    if not moments:
        return None
    d = proj / "check"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir()
    for k, (_, t) in enumerate(moments):
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=270:480",
             str(d / f"c{k:03d}.png")])
    cols = min(6, len(moments))
    rows = -(-len(moments) // cols)
    out = proj / "check.png"
    run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", str(d / "c%03d.png"), "-vf", f"tile={cols}x{rows}",
         "-frames:v", "1", str(out)])
    print("CHECK=" + str(out) + "  (" + ", ".join(f"{n}@{fmt_t(t)}" for n, t in moments) + ")")
    return out


CATALOG = [
    {"kind": "chips", "cat": "chips: a list, each item as it's said", "items": [{"text": "Marketing", "icon": "megaphone"}, {"text": "Invoices", "icon": "receipt"}, {"text": "Emails", "icon": "mail"}, {"text": "Client calls", "icon": "phone"}]},
    {"kind": "chips", "cat": "chips (close): tabs closing", "at": "top", "close": True, "items": ["Invoices", "Emails", "Client call", "Launch"]},
    {"kind": "number", "cat": "number: counts up", "value": "100+", "label": "clients"},
    {"kind": "word", "cat": "word: pop", "text": "real *support*"},
    {"kind": "word", "cat": "word: typewriter", "style": "type", "text": "Did I reply to that?"},
    {"kind": "strike", "cat": "strike: rejected idea", "pre": "No", "text": "50 steps"},
    {"kind": "chat", "cat": "chat: a prompt being typed", "prompt": "write a better prompt for my newsletter", "reply": "Here's a sharper version…"},
    {"kind": "notify", "cat": "notify: a message or sale", "app": "Stripe", "icon": "credit-card", "title": "New payment: €497", "text": "Signature package"},
    {"kind": "checklist", "cat": "checklist: steps ticking off", "title": "This week", "items": ["Plan content", "Batch reels", "Send newsletter"]},
    {"kind": "step", "cat": "step: section title", "n": 1, "text": "*train* it"},
    {"kind": "flow", "cat": "flow: from → to", "items": [{"icon": "car", "text": "Commute"}, {"icon": "laptop", "text": "Remote"}, {"icon": "house", "text": "Home"}]},
    {"kind": "hub", "cat": "hub: a system", "title": "my AI system", "center": {"icon": "sparkles", "text": "AI"}, "nodes": [{"icon": "calendar", "text": "Calendar"}, {"icon": "inbox", "text": "Inbox"}, {"icon": "folder-kanban", "text": "Projects"}, {"icon": "users", "text": "CRM"}]},
    {"kind": "scale", "cat": "scale: a time span or range", "marks": ["1 month", "1 year", "2 years", "3 years"], "from": 0, "to": 3},
    {"kind": "person", "cat": "person: a client story", "name": "Abby", "note": "coach, 2 kids", "meter": 3},
    {"kind": "gif", "cat": "gif: a meme, on request", "file": "effects/sample-meme.mp4", "caption": "when it *finally* works"},
    {"kind": "versus", "cat": "versus: this, not that", "left": {"icon": "shuffle", "text": "Switching tools"}, "right": {"icon": "folder", "text": "One business brain"}},
]


def catalog(proj, kit_name, no_open):
    """Catalogue video: every pop-up piece once, in this kit, over this footage."""
    kit = load_kit(kit_name)
    fdata = facefinder.analyse(proj)
    fs = fdata.get("summary")
    safe = {"face_top": round(fs["top"] * H), "face_bottom": round(fs["bottom"] * H)} if fs else None
    if safe:
        safe["face_left"], safe["face_right"] = face_sides(fdata)
    icons = load_json(ICONS)
    vis, used, t = [], set(), 0.3
    for v in json.loads(json.dumps(CATALOG)):
        v["start"], v["end"] = t, t + 2.8
        t += 3.0
        if v["kind"] == "gif":
            f = LAB / v["file"]
            v["file"] = str(f)
            v["w"], v["h"], _ = mem.probe(f)
            v["at"] = "chest" if v["h"] > v["w"] * 1.1 else "top"
            v["_i"] = len(vis)
        for it in v.get("items", []) + v.get("nodes", []):
            if isinstance(it, dict) and it.get("icon"):
                used.add(it["icon"])
        for side in ("left", "right", "center"):
            if isinstance(v.get(side), dict):
                used.add(v[side].get("icon"))
        if v.get("icon"):
            used.add(v["icon"])
        vis.append(v)
    used |= {"check", "x", "arrow-up", "bell", "user", "sparkles", "circle"}
    total = t
    tl = {"kit": kit, "safe": safe, "captions": [], "events": [], "visuals": vis, "catalog": True,
          "icons": {n: icons[n] for n in used if n in icons}}
    gif_rects(tl)
    entries, _ = render_overlay(tl, total, proj / "overlay-catalog")
    out = proj / f"catalog-{kit_name}.mp4"
    gifs = [{"file": v["file"], "start": v["start"], "end": v["end"], "full": False, "rect": v["rect"]}
            for v in vis if v["kind"] == "gif" and v.get("rect")]
    composite(proj, entries, out.name, None, (), -14, None, gifs)
    print(f"CATALOG={out}")
    if not no_open:
        open_video(out)


def looks(proj, kit_list, left=None, right=None, no_open=False):
    """Pick-a-look sheet: the same moment of the user's own clip in every kit, side by side.
    Each tile shows the hook, a caption with a highlighted word and the name label."""
    words, edl = out_words(proj)
    plan = load_json(proj / "build.json") if (proj / "build.json").exists() else {}
    hook = next((e for e in plan.get("events", []) if e.get("type") == "hook"), None) or \
        {"eyebrow": "Here's the thing", "text": "Your hook *goes* here"}
    fdata = facefinder.analyse(proj)
    fs = fdata.get("summary")
    safe = {"face_top": round(fs["top"] * H), "face_bottom": round(fs["bottom"] * H)} if fs else None
    out_dir = proj / "looks"
    out_dir.mkdir(exist_ok=True)
    frame = out_dir / "frame.png"
    t = facefinder.best_cover_time(fdata) or min(3.0, edl["total"] / 2)
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(proj / "rough.mp4"), "-frames:v", "1", str(frame)])
    tiles, pops = [], []
    if safe:
        safe["face_left"], safe["face_right"] = face_sides(fdata)
    for name in kit_list:
        kit = load_kit(name)
        if left or right:
            kit["label"] = {"left": left or kit["label"]["left"], "right": right or kit["label"]["right"]}
        picked = words[:kit["captions"]["max_words"]]
        longest = max(range(len(picked)), key=lambda k: len(picked[k]["w"]))
        cap = {"start": 0, "end": 99, "words": [{"w": w["w"], "s": 0.0, "e": 9, "hl": k == longest} for k, w in enumerate(picked)]}
        if kit["captions"]["mode"] == "word":           # one-word-at-a-time kits show their highlighted word
            cap["words"] = [cap["words"][longest]]
        tl = {"kit": kit, "safe": safe, "captions": [cap],
              "events": [{"type": "hook", "start": 0, "end": 99, "eyebrow": hook.get("eyebrow"), "text": hook["text"]}]
                        + ([{"type": "label", "start": 0, "end": 99}] if left or right else [])}
        entries, _ = render_overlay(tl, 2.0, out_dir / f"o-{name}", times=[1.0])
        tile = out_dir / f"{name}.png"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(frame), "-i", str(entries[0][0]),
             "-filter_complex", "[0:v][1:v]overlay=0:0,scale=540:960,pad=560:960:10:0:white", "-frames:v", "1", str(tile)])
        tiles.append(tile)
        # second row: the same look's pop-ups (a chat window and a few chips)
        icons = load_json(ICONS)
        demo = [{"kind": "chat", "start": 0, "end": 99, "title": "Chat", "prompt": "plan my week of content", "greeting": "How can I help today?"},
                {"kind": "chips", "start": 0, "end": 99, "at": "chest", "items": [
                    {"text": "Content", "icon": "pen-line", "t": 0}, {"text": "Clients", "icon": "users", "t": 0},
                    {"text": "Calendar", "icon": "calendar", "t": 0}]}]
        tl2 = {"kit": kit, "safe": safe, "captions": [], "events": [], "visuals": demo,
               "icons": {n: icons[n] for n in ("pen-line", "users", "calendar", "arrow-up", "check", "x") if n in icons}}
        e2, _ = render_overlay(tl2, 2.0, out_dir / f"p-{name}", times=[1.2])
        tile2 = out_dir / f"{name}-pop.png"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(frame), "-i", str(e2[0][0]),
             "-filter_complex", "[0:v][1:v]overlay=0:0,scale=540:960,pad=560:960:10:0:white", "-frames:v", "1", str(tile2)])
        pops.append(tile2)
    out = proj / "looks.png"
    rows = []
    for k, row in enumerate([tiles, pops]):
        r = out_dir / f"row{k}.png"
        run(["ffmpeg", "-v", "error", "-y", *sum([["-i", str(t)] for t in row], []),
             "-filter_complex", f"hstack=inputs={len(row)}" if len(row) > 1 else "null", "-frames:v", "1", str(r)])
        rows.append(r)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(rows[0]), "-i", str(rows[1]), "-filter_complex", "vstack=inputs=2",
         "-frames:v", "1", str(out)])
    print("LOOKS=" + ", ".join(kit_list))
    print(f"SHEET={out}")
    if not no_open:
        subprocess.run(["open", str(out)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--kit")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--catalog", action="store_true", help="video of every pop-up piece in this kit")
    ap.add_argument("--out", default="final", help="output name, e.g. sample-bold → sample-bold.mp4")
    ap.add_argument("--looks", help="compare kits side by side: 'presets', 'all', or names like editorial,bold")
    ap.add_argument("--left", help="name on the label (for --looks)")
    ap.add_argument("--right", help="topic on the label (for --looks)")
    args = ap.parse_args()
    proj = Path(args.project).resolve()
    if args.looks:
        names = kit_names()
        if args.looks == "presets":
            names = [n for n in names if load_json(LAB / "packs" / n / "kit.json").get("preset")]
        elif args.looks != "all":
            names = args.looks.split(",")
        looks(proj, names, args.left, args.right, args.no_open)
        return
    kit = args.kit or default_kit()
    if args.catalog:
        catalog(proj, kit, args.no_open)
        return
    if args.sheet:
        sheet(proj, kit, args.no_open)
    else:
        build(proj, kit, args.no_open, args.out)


if __name__ == "__main__":
    main()
