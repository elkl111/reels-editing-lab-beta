"""Transcribe a raw clip word by word (local, free, Apple Silicon).

Main engine: Parakeet. It writes down exactly what was said, including restarts said
without a pause ("while most of the, while most of the people"), which Whisper merges.
Whisper is kept as a fallback (--engine whisper).

Usage:  uv run tools/transcribe.py <clip path or file name in inbox/> [--name my-reel] [--lang en]
        uv run tools/transcribe.py <clip 1> <clip 2> … --name my-reel   (several clips for one reel, in filmed order)

Creates projects/<name>/ with:
  project.json     source path, duration
  transcript.json  every word with start/end seconds (cached; re-runs are instant)
  lines.md         the transcript grouped into numbered phrases, with pauses marked.
                   This is what Claude reads to decide the rough cut.
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import LAB, INBOX, ffprobe_duration, load_json, project_dir, require, run, save_json, slug, fmt_t

PARAKEET_MODEL = LAB / "models" / "parakeet-tdt-0.6b-v3"
HF_MODEL = "mlx-community/whisper-large-v3-turbo"
LOCAL_MODEL = LAB / "models" / "whisper-large-v3-turbo"
MODEL = str(LOCAL_MODEL) if (LOCAL_MODEL / "weights.safetensors").exists() else HF_MODEL
# Nudges Whisper to keep fillers and repeated takes instead of tidying them away.
VERBATIM_PROMPT = "Um, so, like, uh... I mean, okay. Wait, let me start again. So, um, the thing is,"

PHRASE_GAP = 0.35      # a pause this long starts a new phrase
SENTENCE_GAP = 0.15    # shorter pause is enough after . ? !


def resolve_clip(arg: str) -> Path:
    p = Path(arg).expanduser()
    if p.exists():
        return p.resolve()
    if (INBOX / arg).exists():
        return (INBOX / arg).resolve()
    raise SystemExit(f"Can't find clip: {arg}")


def transcribe_parakeet(audio: Path):
    """Parakeet gives sub-word tokens; a token starting with a space begins a new word."""
    from parakeet_mlx import from_pretrained
    model = from_pretrained(str(PARAKEET_MODEL))
    res = model.transcribe(str(audio), chunk_duration=120, overlap_duration=15)
    words, cur = [], None
    for sent in res.sentences:
        for tok in sent.tokens:
            t = tok.text
            if cur is None or t.startswith(" "):
                if cur and cur["w"].strip():
                    words.append(cur)
                cur = {"w": t.strip(), "s": tok.start, "e": tok.end, "p": 1.0}
            else:
                cur["w"] += t
                cur["e"] = tok.end
    if cur and cur["w"].strip():
        words.append(cur)
    # punctuation that arrives as its own token belongs to the word before it
    merged = []
    for w in words:
        if merged and all(ch in ".,?!;:…" for ch in w["w"]):
            merged[-1]["w"] += w["w"]
            merged[-1]["e"] = max(merged[-1]["e"], w["e"])
        else:
            merged.append(w)
    for i, w in enumerate(merged):
        w.update({"i": i, "s": round(w["s"], 3), "e": round(max(w["e"], w["s"] + 0.05), 3)})
    return merged, None


def transcribe(audio: Path, lang: str | None):
    import mlx_whisper
    res = mlx_whisper.transcribe(
        str(audio),
        path_or_hf_repo=MODEL,
        word_timestamps=True,
        condition_on_previous_text=False,
        initial_prompt=VERBATIM_PROMPT,
        language=lang,
    )
    words = []
    for seg in res.get("segments", []):
        for w in seg.get("words", []):
            text = w["word"].strip()
            if not text:
                continue
            words.append({"i": len(words), "w": text, "s": round(w["start"], 3),
                          "e": round(w["end"], 3), "p": round(w.get("probability", 1.0), 2)})
    return words, res.get("language", lang)


TRANSCRIPT_VERSION = 4
MIN_SILENCE = 0.18     # shortest pause worth detecting (seconds)


def detect_silences(audio: Path):
    """Real pauses from the audio itself. Whisper stretches words across pauses, so we need these."""
    import re
    import subprocess
    vol = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: (-?[\d.]+) dB", vol)
    mean = float(m.group(1)) if m else -30.0
    thresh = max(min(mean - 7, -30), -50)   # relative to how loud this recording is
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af",
                          f"silencedetect=noise={thresh:.0f}dB:d={MIN_SILENCE}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    sil = []
    for a, b in zip(starts, ends):
        a = max(a, 0.0)
        if sil and a - sil[-1][1] < 0.06:      # merge pauses split by a click or breath
            sil[-1][1] = b
        else:
            sil.append([a, b])
    return [[round(a, 3), round(b, 3)] for a, b in sil]


def snap_to_silences(words, silences):
    """Trim each word so it doesn't run into a real pause.

    Whisper often stretches a word across a pause (and the breaths around it). We split the
    word's span into its sounding parts and keep the one that's really the word: the part
    touching the next word when they run together, otherwise the longest part.
    """
    out = [dict(w) for w in words]
    for k, w in enumerate(out):
        s, e = w["s"], w["e"]
        parts, cur = [], s
        for a, b in silences:
            if b <= cur or a >= e:
                continue
            if a > cur:
                parts.append([cur, a])
            cur = max(cur, b)
        if cur < e:
            parts.append([cur, e])
        if not parts:                         # the whole word sits in a pause: keep it, mark unsure
            w["p"] = min(w["p"], 0.3)
            continue
        if len(parts) == 1:
            w["s"], w["e"] = parts[0]
            continue
        nxt = out[k + 1]["s"] if k + 1 < len(out) else None
        if nxt is not None and nxt - parts[-1][1] < 0.1:
            w["s"], w["e"] = parts[-1]        # runs straight into the next word
        else:
            w["s"], w["e"] = max(parts, key=lambda p: p[1] - p[0])
    for w in out:
        if w["e"] - w["s"] < 0.05:
            w["e"] = round(w["s"] + 0.05, 3)
        w["s"], w["e"] = round(w["s"], 3), round(w["e"], 3)
    return out


def group_phrases(words):
    phrases, cur = [], []
    for w in words:
        if cur:
            gap = w["s"] - cur[-1]["e"]
            ends_sentence = cur[-1]["w"][-1:] in ".?!"
            long_enough = len(cur) >= 8 and gap >= 0.12
            if gap >= PHRASE_GAP or ends_sentence or long_enough:
                phrases.append(cur)
                cur = []
        cur.append(w)
    if cur:
        phrases.append(cur)
    return phrases


def write_lines_md(proj: Path, words, duration: float, clips=None):
    phrases = group_phrases(words)
    marks = list(clips or [])
    out = [f"# Transcript phrases ({fmt_t(duration)} total, {len(words)} words)",
           "",
           "Format: P# [first_word-last_word] start→end | text   (pauses over 0.35s shown as ·· gap ··)",
           ""]
    prev_end = 0.0
    for n, ph in enumerate(phrases, 1):
        while marks and ph[0]["s"] >= marks[0]["start"] - 0.01:      # several clips: mark where each begins
            m = marks.pop(0)
            out.append(f"── clip {m['n']}: {m['file']} ({fmt_t(m['start'])}→{fmt_t(m['end'])}) ──")
        gap = ph[0]["s"] - prev_end
        if gap >= PHRASE_GAP:
            out.append(f"   ·· {gap:.1f}s gap ··")
        text = " ".join(w["w"] for w in ph)
        low = [w["w"] for w in ph if w["p"] < 0.5]
        flag = f"   (unsure: {', '.join(low)})" if low else ""
        out.append(f"P{n} [{ph[0]['i']}-{ph[-1]['i']}] {ph[0]['s']:.2f}→{ph[-1]['e']:.2f} | {text}{flag}")
        prev_end = ph[-1]["e"]
    (proj / "lines.md").write_text("\n".join(out) + "\n")
    return len(phrases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", nargs="+", help="one clip, or several filmed for the same reel (in order)")
    ap.add_argument("--name")
    ap.add_argument("--lang", default=None, help="whisper only: en, es, ... (auto-detect if omitted)")
    ap.add_argument("--engine", choices=["parakeet", "whisper"], default=None,
                    help="parakeet (default, verbatim) or whisper (fallback)")
    args = ap.parse_args()
    require("ffmpeg")

    originals = [resolve_clip(c) for c in args.clip]
    original = originals[0]
    name = args.name or slug(original.name)
    import intake
    proj = project_dir(name)
    clips = None
    if len(originals) == 1:
        clip = intake.prepare(original, proj)          # beta checks; HDR → standard-colour copy
    else:
        ready = [intake.prepare(o, proj, f"source-sdr-{k + 1}.mov") for k, o in enumerate(originals)]
        total = sum(ffprobe_duration(c) for c in ready)
        if total > intake.MAX_MIN * 60:
            print(f"PROBLEM: Together these clips run {total / 60:.0f} minutes. The beta takes up to about "
                  f"{intake.WARN_MIN} minutes per reel. Leave out the clips you don't need.")
            raise SystemExit("INTAKE=refused")
        clip, spans = intake.join(ready, proj)
        clips = [{"n": k + 1, "file": o.name, "start": a, "end": b} for k, (o, (a, b)) in enumerate(zip(originals, spans))]
        print(f"Joined {len(originals)} clips ({fmt_t(total)}).")
    duration = ffprobe_duration(clip)

    meta_p = proj / "project.json"
    meta = load_json(meta_p) if meta_p.exists() else {"created": datetime.now().isoformat(timespec="seconds")}
    meta.update({"name": name, "source": str(clip), "original": str(original), "duration": round(duration, 2)})
    if clips:
        meta["clips"] = clips
        meta["original"] = [str(o) for o in originals]
    else:
        meta.pop("clips", None)

    tr_p = proj / "transcript.json"
    cached = load_json(tr_p) if tr_p.exists() else {}
    engine = args.engine or ("parakeet" if (PARAKEET_MODEL / "model.safetensors").exists() else "whisper")
    if (cached.get("source") == str(clip) and cached.get("version") == TRANSCRIPT_VERSION
            and cached.get("engine") == engine):
        words = cached["words"]
        print(f"Using cached transcript ({len(words)} words).")
    else:
        t0 = time.time()
        audio = proj / "audio.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vn", "-ac", "1", "-ar", "16000", str(audio)])
        silences = detect_silences(audio)
        if engine == "parakeet":
            raw, lang = transcribe_parakeet(audio)
            # Parakeet's times are tight, except the last word before a pause can run into it
            words = snap_to_silences(raw, silences)
            model = PARAKEET_MODEL.name
        else:
            raw, lang = transcribe(audio, args.lang)
            words = snap_to_silences(raw, silences)
            model = HF_MODEL
        save_json(tr_p, {"version": TRANSCRIPT_VERSION, "engine": engine, "source": str(clip), "model": model,
                         "language": lang, "words": words, "silences": silences, "raw_words": raw})
        meta["language"] = lang
        audio.unlink(missing_ok=True)
        print(f"Transcribed {fmt_t(duration)} in {time.time() - t0:.0f}s ({len(words)} words, "
              f"{len(silences)} pauses found, engine: {engine}).")

    save_json(meta_p, meta)
    n = write_lines_md(proj, words, duration, meta.get("clips"))
    print(f"{n} phrases → {proj / 'lines.md'}")
    print(f"PROJECT={proj}")


if __name__ == "__main__":
    main()
