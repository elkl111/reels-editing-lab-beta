"""Render a custom animated insert (an HTML page) into a transparent video clip for the reel.

Usage:  uv run tools/insert.py <projects/name/inserts/name/index.html> --dur 3.2 [--w 900 --h 700]
        → <same folder>/insert.mov   (ProRes 4444 with alpha), then place it in build.json:
          {"kind": "insert", "file": "projects/<name>/inserts/<name>/insert.mov", "word": i, "width": 700}

The page contract (what a sub-agent builds):
- a fixed-size root (w × h px), transparent background outside the card/window it draws
- window.renderAt(t) draws the exact state at time t seconds (no timers, no CSS transitions or animations):
  the same t must always give the same picture, because frames are captured one by one
- fonts and images from local files only; text sizes readable on a phone (≥ 24px at the size it's shown)
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import FPS, run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--w", type=int, default=900)
    ap.add_argument("--h", type=int, default=700)
    a = ap.parse_args()
    page = Path(a.html).resolve()
    frames = page.parent / "frames"
    frames.mkdir(exist_ok=True)
    for f in frames.glob("*.png"):
        f.unlink()
    from playwright.sync_api import sync_playwright
    n = int(round(a.dur * FPS))
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": a.w, "height": a.h})
        pg.goto(page.as_uri())
        pg.wait_for_function("typeof window.renderAt === 'function'")
        pg.evaluate("document.fonts.ready")
        for k in range(n):
            pg.evaluate(f"window.renderAt({k / FPS:.4f})")
            pg.screenshot(path=str(frames / f"f{k:05d}.png"), omit_background=True)
        b.close()
    out = page.parent / "insert.mov"
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(frames / "f%05d.png"),
         "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", str(out)])
    print(f"INSERT={out}  ({a.w}x{a.h}, {a.dur:.2f}s, alpha)")


if __name__ == "__main__":
    main()
