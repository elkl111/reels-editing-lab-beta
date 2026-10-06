"""The member's own reels, for the orbit (reels circling them) and the profile grid.

Usage:
  uv run tools/reels.py add <video files or a folder>     → brand/reels/01.mp4 + 01.jpg …  (up to 9)
  uv run tools/reels.py list
  uv run tools/reels.py clear

Reels come from the user: dropped files, or downloaded from their own profile (for example with Apify's
Instagram scraper, if they have it connected). Each one is trimmed to a short muted clip plus a thumbnail.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import LAB, run

D = LAB / "brand" / "reels"
VIDEO = (".mp4", ".mov", ".m4v")


def add(paths):
    D.mkdir(parents=True, exist_ok=True)
    files = []
    for p in paths:
        p = Path(p).expanduser()
        files += sorted(f for f in p.iterdir() if f.suffix.lower() in VIDEO) if p.is_dir() else [p]
    n = len(list(D.glob("*.mp4")))
    for f in files:
        if n >= 9:
            print("NOTE: kept the first 9 reels (the orbit and the grid use 6).")
            break
        n += 1
        out = D / f"{n:02d}.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-t", "4", "-i", str(f), "-an",
             "-vf", "scale=540:960:force_original_aspect_ratio=increase,crop=540:960,fps=30", "-c:v", "libx264", "-crf", "23", str(out)])
        run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", str(out), "-frames:v", "1", "-q:v", "3", str(out.with_suffix(".jpg"))])
        print(f"REEL={out.name}  ← {f.name}")


if __name__ == "__main__":
    a = sys.argv[1:] or ["list"]
    if a[0] == "add":
        add(a[1:])
    elif a[0] == "clear":
        for f in D.glob("*"):
            f.unlink()
        print("REELS=cleared")
    names = sorted(f.name for f in D.glob("*.mp4")) if D.exists() else []
    print(f"REELS={len(names)}  " + " ".join(names))
