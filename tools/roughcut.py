"""Turn Claude's line picks (cut.json) into a rough-cut video, then open it in QuickTime.

Usage:  uv run tools/roughcut.py projects/<name> [--no-open]

cut.json (written by Claude after reading lines.md):
{
  "lines": [
    {"text": "I have zero time to edit reels.", "words": [12, 18]},
    ...                                     # word index ranges, inclusive, in play order
  ]
}

Writes:
  edl.json       exact source times for every segment + each line's time in the output
  rough.mp4      1080x1920, 30fps, clean audio fades at every cut
  lines_review.txt  the numbered lines with lengths, shown to the user in the chat for review
"""
import argparse
import hashlib
import html
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import FPS, H, LAB, W, fmt_t, load_json, open_video, replace_into, run, save_json

PAD_IN = 0.08        # seconds kept before the first word of a segment
PAD_OUT = 0.14       # seconds kept after the last word
MAX_INNER_GAP = 0.28 # pauses longer than this inside a line get trimmed out
SILENCE_KEEP = 0.08  # breath kept on each side of a trimmed pause
EDGE = 0.03          # stay this far inside a gap, so the neighbouring word never bleeds in
MIN_JOIN = 0.18      # at least this much quiet at every join
LEAD_IN = 0.08       # natural quiet kept before a line: a breath, so joined sentences don't run together
FADE = 0.03          # audio fade at every cut, prevents pops


ENV_HOP = 0.01       # loudness measured every 10 ms
SEARCH_OUT = 0.30    # how far past a word's end we look for the quietest cut point
SEARCH_IN = 0.30     # how far before a word's start
MIN_GAP_FRAMES = 4   # 40 ms of quiet = a real gap between words
REACH = 0.20         # max distance the cut may move into a neighbouring, cut-away word


def loudness_envelope(proj, src):
    """Loudness every 10 ms, cached per project. Used to cut at the quietest instant."""
    import numpy as np
    cache = proj / "envelope.npy"
    if cache.exists():
        return np.load(cache)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    hop = int(16000 * ENV_HOP)
    n = len(a) // hop
    env = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(axis=1) + 1e-10)
    np.save(cache, env)
    return env


def quiet_point(env, lo, hi, prefer):
    """Where to cut between lo and hi seconds.

    A seam is a stretch at least 40 ms long that's near the quietest moment here, or a
    shorter dip that's clearly quieter than speech (words said in one breath only leave a
    10-30 ms dip). We take the seam CLOSEST to the kept word: the first one after it when
    cutting out (prefer='early', returns where the seam begins), the last one before it
    when cutting in (prefer='late', returns where the seam ends). None = no clear seam."""
    import numpy as np
    a, b = max(int(round(lo / ENV_HOP)), 0), min(int(round(hi / ENV_HOP)) + 1, len(env))
    if b - a < 2:
        return None
    w = 20 * np.log10(env[a:b])
    thresh = float(w.min()) + 6.0
    deep = float(np.median(w)) - 12.0
    runs, start = [], None
    for k, q in enumerate(list(w <= thresh) + [False]):
        if q and start is None:
            start = k
        elif not q and start is not None:
            depth = float(w[start:k].min())
            if k - start >= MIN_GAP_FRAMES or depth <= deep:
                runs.append((start, k))
            start = None
    if not runs:
        return None
    r = runs[0] if prefer == "early" else runs[-1]
    lo_t, hi_t = (a + r[0]) * ENV_HOP, (a + r[1]) * ENV_HOP
    return (lo_t if prefer == "early" else hi_t), lo_t, hi_t


def build_edl(words, lines, duration, env=None, silences=None):
    """Line picks → source segments cut on word boundaries.

    Kept words that sit back to back in the original recording play straight through,
    even across line boundaries. Cuts only happen where a take is dropped or the
    speaker paused longer than MAX_INNER_GAP.
    """
    kept = []                                   # (line number, word) in play order
    for li, line in enumerate(lines, 1):
        a, b = line["words"]
        if b < a or not words[a:b + 1]:
            raise SystemExit(f"Line {li} has an empty word range {a}-{b}")
        kept += [(li, w) for w in words[a:b + 1]]

    groups, cur = [], [kept[0]]
    for item in kept[1:]:
        prev = cur[-1][1]
        w = item[1]
        if w["i"] == prev["i"] + 1 and w["s"] - prev["e"] <= MAX_INNER_GAP:
            cur.append(item)
        else:
            groups.append(cur)
            cur = [item]
    groups.append(cur)

    segs = []
    for g in groups:
        first_w, last_w = g[0][1], g[-1][1]
        first, last = first_w["i"], last_w["i"]
        ws0, we0 = first_w["s"], last_w["e"]
        prev_w = words[first - 1] if first > 0 else None
        next_w = words[last + 1] if last + 1 < len(words) else None
        s = e = None
        if env is not None:
            # cut where the sound is actually quietest, not exactly where Whisper guessed.
            # The search may reach a little into a neighbouring word that's being cut away
            # (Whisper's boundary between run-together words is often early), but never far.
            lo_q = max(ws0 - SEARCH_IN, prev_w["e"] - REACH, prev_w["s"] + 0.03) if prev_w else 0.0
            hi_q = min(we0 + SEARCH_OUT, next_w["s"] + REACH, next_w["e"] - 0.03) if next_w else duration
            q = quiet_point(env, lo_q, min(ws0 + 0.05, words[first]["e"] - 0.03), "late")
            # a little air before the first word, but never reaching back past the gap
            s = None if q is None else max(q[0] - LEAD_IN, q[1] + EDGE, 0.0)
            q = quiet_point(env, max(we0 - 0.05, words[last]["s"] + 0.03), hi_q, "early")
            # a little breath after the last word, but never past the gap into the next word
            e = None if q is None else min(q[0] + 0.08, q[2] - EDGE, duration)
        if s is None:
            s = max(ws0 - PAD_IN, (prev_w["e"] + ws0) / 2) if prev_w else max(ws0 - PAD_IN, 0.0)
        if e is None:
            e = min(we0 + PAD_OUT, (we0 + next_w["s"]) / 2) if next_w else min(we0 + PAD_OUT, duration)
        segs.append({"lines": sorted({li for li, _ in g}), "start": round(s, 3), "end": round(e, 3),
                     "words": [first, last]})

    # Safety net: cut out any real pause inside a segment, whatever the word times say
    if silences:
        split = []
        for sg in segs:
            pieces = [[sg["start"], sg["end"]]]
            for a, b in silences:
                if b - a < MAX_INNER_GAP:
                    continue
                cut_a, cut_b = a + SILENCE_KEEP, b - SILENCE_KEEP
                nxt = []
                for ps, pe in pieces:
                    if cut_a > ps + 0.05 and cut_b < pe - 0.05:
                        nxt += [[ps, cut_a], [cut_b, pe]]
                    else:
                        nxt.append([ps, pe])
                pieces = nxt
            for k, (ps, pe) in enumerate(pieces):
                d = dict(sg, start=round(ps, 3), end=round(pe, 3))
                split.append(d)
        segs = split

    # Every join gets a little quiet. Two sentences glued with no air run together and
    # can sound like a phantom word ("business. Let me" → "business. So let me").
    # If the recording itself has too little room, add a tiny silence and hold the frame.
    def spoken(sg):
        return [w for w in words[sg["words"][0]:sg["words"][1] + 1]
                if w["e"] > sg["start"] + 0.01 and w["s"] < sg["end"] - 0.01]
    for k, sg in enumerate(segs):
        sg["pad"] = 0.0
        if k + 1 < len(segs):
            mine, theirs = spoken(sg), spoken(segs[k + 1])
            tail = max(0.0, sg["end"] - mine[-1]["e"]) if mine else 0.0
            head = max(0.0, theirs[0]["s"] - segs[k + 1]["start"]) if theirs else 0.0
            sg["pad"] = round(max(0.0, MIN_JOIN - (tail + head)), 3)

    t = 0.0
    for sg in segs:
        sg["out_start"] = round(t, 3)
        t += sg["end"] - sg["start"] + sg["pad"]
        sg["out_end"] = round(t, 3)

    def out_time(src_t):
        for sg in segs:
            if sg["start"] - 1e-6 <= src_t <= sg["end"] + 1e-6:
                return sg["out_start"] + (src_t - sg["start"])
        return None

    # each line's span on the output timeline (for the review list and, later, captions)
    bounds = []
    for li, line in enumerate(lines, 1):
        a, b = line["words"]
        bounds.append((li, line, words[a], words[b]))
    line_times = []
    for k, (li, line, fw, lw) in enumerate(bounds):
        seg_in = next(sg for sg in segs if sg["words"][0] <= fw["i"] <= sg["words"][1])
        seg_out = [sg for sg in segs if sg["words"][0] <= lw["i"] <= sg["words"][1]][-1]
        start = seg_in["out_start"] if fw["i"] == seg_in["words"][0] else out_time((words[fw["i"] - 1]["e"] + fw["s"]) / 2)
        end = seg_out["out_end"] if lw["i"] == seg_out["words"][1] else out_time((lw["e"] + words[lw["i"] + 1]["s"]) / 2)
        line_times.append({"line": li, "text": line["text"], "words": line["words"],
                           "out_start": round(start, 3), "out_end": round(end, 3),
                           "dur": round(end - start, 2)})
    return segs, line_times, round(t, 3)


def seg_key(src, s):
    return hashlib.sha1(f"{src}|{s['start']}|{s['end']}|{s.get('pad', 0)}|{W}x{H}@{FPS}".encode()).hexdigest()[:12]


def render_segment(src, seg, out):
    d = seg["end"] - seg["start"]
    pad = seg.get("pad", 0.0)
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"fps={FPS},format=yuv420p")
    af = f"afade=t=in:st=0:d={FADE},afade=t=out:st={max(d - FADE, 0):.3f}:d={FADE}"
    if pad > 0:                            # hold the last frame and add silence for the join
        vf += f",tpad=stop_mode=clone:stop_duration={pad:.3f}"
        af += f",apad=pad_dur={pad:.3f}"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{seg['start']:.3f}", "-t", f"{d:.3f}", "-i", str(src),
         "-vf", vf, "-af", af, "-t", f"{d + pad:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(out)])


def render(proj, src, segs):
    cache = proj / "segments"
    cache.mkdir(exist_ok=True)
    jobs, files = [], []
    for s in segs:
        f = cache / f"{seg_key(src, s)}.mp4"
        files.append(f)
        if not f.exists():
            jobs.append((s, f))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda j: render_segment(src, j[0], j[1]), jobs))
    lst = proj / "concat.txt"
    lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in files))
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", "-movflags", "+faststart", str(proj / "tmp-rough.mp4")])
    replace_into(proj / "tmp-rough.mp4", proj / "rough.mp4")
    # drop cached segments no longer used
    keep = {f.name for f in files}
    for f in cache.glob("*.mp4"):
        if f.name not in keep:
            f.unlink()
    return len(jobs), len(segs), time.time() - t0


def lines_for_chat(line_times):
    """The numbered lines with their lengths, ready to paste into the chat for review."""
    return "\n".join(f"{ln['line']:>2}. {ln['text']}  ({ln['dur']:.1f}s)" for ln in line_times)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    proj = Path(args.project).resolve()
    meta = load_json(proj / "project.json")
    tr = load_json(proj / "transcript.json")
    words = tr["words"]
    cut = load_json(proj / "cut.json")
    src = Path(meta["source"])

    env = loudness_envelope(proj, src)
    segs, line_times, total = build_edl(words, cut["lines"], meta["duration"], env, tr.get("silences"))
    save_json(proj / "edl.json", {"source": str(src), "segments": segs, "lines": line_times, "total": total})
    new, n, secs = render(proj, src, segs)
    (proj / "lines_review.txt").write_text(lines_for_chat(line_times) + "\n")

    cut_pct = 100 * (1 - total / meta["duration"])
    print(f"{fmt_t(meta['duration'])} → {fmt_t(total)} ({cut_pct:.0f}% cut), "
          f"{len(line_times)} lines, {n} segments ({new} rendered, {n - new} reused) in {secs:.0f}s")
    print(f"VIDEO={proj / 'rough.mp4'}")
    print("LINES:")
    print(lines_for_chat(line_times))
    if not args.no_open:
        open_video(proj / "rough.mp4")


if __name__ == "__main__":
    main()
