"""Find the speaker's face through the cut (Apple Vision, built into macOS).

Usage:  uv run tools/faces.py projects/<name>   → projects/<name>/faces.json

Used by the build to keep graphics off the face, centre zooms on it, and pick the cover frame.
Samples 2 frames per second of rough.mp4; cached until rough.mp4 changes.
"""
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import LAB, load_json, run, save_json

BIN = LAB / "tools" / "bin" / "faces"
SRC = LAB / "tools" / "faces.swift"
RATE = 2


def ensure_binary():
    if not BIN.exists() or BIN.stat().st_mtime < SRC.stat().st_mtime:
        BIN.parent.mkdir(exist_ok=True)
        run(["swiftc", "-O", "-target", "arm64-apple-macos13", str(SRC), "-o", str(BIN)])


def analyse(proj: Path):
    video = proj / "rough.mp4"
    out_p = proj / "faces.json"
    if out_p.exists() and load_json(out_p).get("video_mtime") == video.stat().st_mtime:
        return load_json(out_p)
    ensure_binary()
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={RATE},scale=540:960", "-q:v", "3",
             f"{td}/f%05d.jpg"])
        res = subprocess.run([str(BIN), td], capture_output=True, text=True)
    frames = []
    for line in res.stdout.splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        k = int(d["file"][1:6]) - 1
        d["t"] = round(k / RATE + 0.5 / RATE, 2)
        frames.append(d)
    found = [f for f in frames if "box" in f]
    summary = None
    if found:
        tops = [f["box"][1] for f in found]
        bottoms = [f["box"][1] + f["box"][3] for f in found]
        centres_x = [f["box"][0] + f["box"][2] / 2 for f in found]
        summary = {
            "top": round(statistics.quantiles(tops, n=10)[0], 3),          # higher end of where the head goes
            "bottom": round(statistics.quantiles(bottoms, n=10)[-1], 3),   # lower end of the chin
            "centre_y": round(statistics.median([(a + b) / 2 for a, b in zip(tops, bottoms)]), 3),
            "centre_x": round(statistics.median(centres_x), 3),
            "seen": round(len(found) / max(len(frames), 1), 2),
        }
    data = {"video_mtime": video.stat().st_mtime, "rate": RATE, "summary": summary, "frames": frames}
    save_json(out_p, data)
    return data


def best_cover_time(faces, avoid=()):
    """The frame where the face looks best: Apple's capture quality, eyes clearly open."""
    best, best_t = -1, None
    for f in faces["frames"]:
        if "quality" not in f or any(a <= f["t"] <= b for a, b in avoid):
            continue
        eyes = f.get("eyes", 0)
        score = f["quality"] * (1.0 if eyes >= 0.24 else 0.6)
        if score > best:
            best, best_t = score, f["t"]
    return best_t


if __name__ == "__main__":
    d = analyse(Path(sys.argv[1]).resolve())
    print(json.dumps(d["summary"]), "cover at", best_cover_time(d))
