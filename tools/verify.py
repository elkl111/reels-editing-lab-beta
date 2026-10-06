"""Listen back to a cut and check every kept word is there and nothing extra slipped in.

Uses Parakeet, which writes down repeats verbatim (Whisper silently merges them, so a
Whisper-based check can't see a restart that survived the cut). Also flags any phrase
of 3+ words that is said twice in a row.

Usage:  uv run tools/verify.py projects/<name> [--video rough.mp4]

Re-transcribes the rendered video and compares it with the lines in cut.json.
Prints OK, or the exact words that were clipped or that leaked in from cut-away takes.
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import LAB, load_json

MODEL = LAB / "models" / "whisper-large-v3-turbo"
PARAKEET = LAB / "models" / "parakeet-tdt-0.6b-v3"


def listen(wav):
    if (PARAKEET / "model.safetensors").exists():
        from parakeet_mlx import from_pretrained
        return from_pretrained(str(PARAKEET)).transcribe(str(wav), chunk_duration=120, overlap_duration=15).text
    import mlx_whisper
    model = str(MODEL) if (MODEL / "weights.safetensors").exists() else "mlx-community/whisper-large-v3-turbo"
    return mlx_whisper.transcribe(str(wav), path_or_hf_repo=model, condition_on_previous_text=False)["text"]


def repeats(words, n_min=3, window=12):
    """Phrases of n_min+ words said twice within a few words of each other (a restart that survived)."""
    found, i = [], 0
    while i < len(words):
        hit = None
        for n in range(6, n_min - 1, -1):
            gram = words[i:i + n]
            if len(gram) < n:
                continue
            for j in range(i + 1, min(i + window, len(words) - n + 1)):
                if words[j:j + n] == gram:
                    hit = (n, j)
                    break
            if hit:
                break
        if hit:
            found.append(" ".join(words[i:i + hit[0]]))
            i = hit[1] + hit[0]
        else:
            i += 1
    return found


MAX_PAUSE = 0.35   # any silence longer than this in a finished cut is dead air


def pauses(video):
    """Measure every silence in the rendered cut. Word comparison alone can't see dead air:
    a pause can hide inside a word whose timing got stretched (it happened: 1.7 s after 'business.')."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-af",
                          f"silencedetect=noise=-37dB:d={MAX_PAUSE}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    durs = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", out)]
    return list(zip(starts, durs))


def norm(text):
    return re.findall(r"[a-z0-9']+", text.lower().replace("-", " "))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--video", default="rough.mp4")
    args = ap.parse_args()
    proj = Path(args.project).resolve()

    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(proj / args.video),
                        "-ac", "1", "-ar", "16000", str(wav)], check=True)
        heard = listen(wav)

    expected = " ".join(l["text"] for l in load_json(proj / "cut.json")["lines"])
    e, h = norm(expected), norm(heard)
    problems = []
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, e, h, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        ctx = " ".join(e[max(a1 - 3, 0):a1])
        if op == "delete":
            problems.append(f"missing: '{' '.join(e[a1:a2])}' (after '…{ctx}')")
        elif op == "insert":
            problems.append(f"extra: '{' '.join(h[b1:b2])}' (after '…{ctx}')")
        else:
            problems.append(f"differs: expected '{' '.join(e[a1:a2])}', heard '{' '.join(h[b1:b2])}' (after '…{ctx}')")
    for r in repeats(h):
        if r not in " ".join(e):
            problems.append(f"repeated: '{r}' is said twice (a restart may have survived the cut)")
        elif " ".join(e).count(r) < " ".join(h).count(r):
            problems.append(f"repeated: '{r}' is said more often than in the kept lines")
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(proj / args.video)], capture_output=True, text=True).stdout or 0)
    for st, d in pauses(proj / args.video):
        if st + d < total - 0.05:                     # the natural fade-out at the very end is fine
            problems.append(f"pause: {d:.1f}s of silence at {st:.1f}s (dead air: trim it)")
    score = difflib.SequenceMatcher(None, e, h, autojunk=False).ratio()
    report = {"match": round(score, 3), "problems": problems}
    (proj / "verify.json").write_text(json.dumps(report, indent=2))
    if not problems:
        print(f"OK: every word is there ({len(e)} words).")
    else:
        print(f"{score:.0%} match, {len(problems)} spot(s) to check:")
        for p in problems:
            print("  -", p)
        print("Small differences in spelling (ChatGPT vs chat gpt) are usually transcription, not the cut.")


if __name__ == "__main__":
    main()
