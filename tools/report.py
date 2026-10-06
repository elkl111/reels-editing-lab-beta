"""Problem report: bundle everything needed to debug a reel into one small zip on the Desktop.

Usage:  uv run tools/report.py [projects/<name>] --note "what went wrong, in the user's words" [--error "error text"]

Includes: the user's note, the error (if any), the Lab version, a setup check, Mac/ffmpeg versions,
the project's plan files (transcript, cut, build, timeline, verify), check.png, and a small 360p preview
of the latest video. Never includes the original footage, models or other projects.
"""
import argparse
import platform
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import LAB, PROJECTS

PLAN_FILES = ["project.json", "transcript.json", "lines.md", "cut.json", "edl.json", "lines_review.txt",
              "verify.json", "build.json", "timeline.json", "faces.json", "check.png", "looks.png"]


def latest_project():
    ps = [p for p in PROJECTS.glob("*") if p.is_dir()]
    return max(ps, key=lambda p: p.stat().st_mtime) if ps else None


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:
        return f"(failed: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    ap.add_argument("--note", default="")
    ap.add_argument("--error", default="")
    a = ap.parse_args()
    proj = Path(a.project).resolve() if a.project else latest_project()
    stamp = datetime.now().strftime("%Y-%m-%d %H.%M")
    out = Path.home() / "Desktop" / f"Reels Lab report {stamp}.zip"
    version = (LAB / "VERSION").read_text().strip() if (LAB / "VERSION").exists() else "?"
    info = "\n".join([
        f"Lab version: {version}",
        f"macOS: {platform.mac_ver()[0]} ({platform.machine()})",
        f"ffmpeg: {sh(['ffmpeg', '-version']).splitlines()[0] if sh(['ffmpeg', '-version']) else 'missing'}",
        f"Kit: {(LAB / 'brand' / 'kit.txt').read_text().strip() if (LAB / 'brand' / 'kit.txt').exists() else 'none'}",
        f"Project: {proj.name if proj else 'none'}",
        "", "Setup check:", sh([sys.executable, str(LAB / 'tools' / 'doctor.py')]),
    ])
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("note.txt", (a.note or "(no note)") + ("\n\nError:\n" + a.error if a.error else "") + "\n")
        z.writestr("info.txt", info + "\n")
        for f in ["brand/preferences.md", f"packs/{(LAB / 'brand' / 'kit.txt').read_text().strip()}/kit.json"
                  if (LAB / "brand" / "kit.txt").exists() else ""]:
            if f and (LAB / f).exists():
                z.write(LAB / f, f)
        if proj and proj.exists():
            for name in PLAN_FILES:
                if (proj / name).exists():
                    z.write(proj / name, f"project/{name}")
            vids = [v for v in [proj / "final.mp4", proj / "rough.mp4"] if v.exists()]
            if vids:
                prev = proj / "report-preview.mp4"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vids[0]), "-vf", "scale=-2:640",
                                "-c:v", "libx264", "-crf", "30", "-preset", "veryfast", "-c:a", "aac", "-b:a", "64k",
                                str(prev)], capture_output=True)
                if prev.exists():
                    z.write(prev, f"project/preview-{vids[0].stem}.mp4")
                    prev.unlink()
    mb = out.stat().st_size / 1e6
    print(f"REPORT={out}  ({mb:.1f} MB)")
    subprocess.run(["open", "-R", str(out)])


if __name__ == "__main__":
    main()
