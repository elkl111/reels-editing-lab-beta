"""Shared helpers for the Reels Editing Lab tools."""
import json
import re
import shutil
import subprocess
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
PROJECTS = LAB / "projects"
INBOX = LAB / "inbox"

W, H, FPS = 1080, 1920, 30

# Instagram Reels covers parts of the frame with its own buttons and text. Graphics stay out of them.
# Bottom and right are strict (username, caption, audio row, like/comment/share sit on the video).
# The top is lighter: only the corners carry the header, and a stricter line shrank top pop-ups too much.
# effects/stage.html has the same numbers (SAFE_ZONE); keep the two in step.
SAFE = {"top": 170, "bottom": 1470, "side": 35, "icons_x": 980, "icons_y": 1155}

# Loudness for posting: Instagram plays reels at about -14 LUFS, so a reel mixed there isn't turned
# down (too loud) or left quieter than the next reel in the feed (too quiet).
TARGET_LUFS, MAX_PEAK = -14.0, -1.0


def slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", Path(name).stem).strip("-").lower()
    return s or "reel"


def project_dir(name: str) -> Path:
    d = PROJECTS / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_json(p: Path):
    return json.loads(Path(p).read_text())


def save_json(p: Path, data):
    Path(p).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def run(cmd, **kw):
    """Run a command, raising with stderr on failure."""
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r.stdout


def ffprobe_duration(path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", str(path)])
    return float(out.strip())


def require(tool: str):
    if not shutil.which(tool):
        raise SystemExit(f"Missing '{tool}'. Run the setup steps in SETUP.md.")


def fmt_t(sec: float) -> str:
    m, s = divmod(max(sec, 0), 60)
    return f"{int(m)}:{s:04.1f}"


def project_meta(proj: Path) -> dict:
    p = proj / "project.json"
    return load_json(p) if p.exists() else {}


def open_video(path):
    """Show a video in QuickTime. Closes any QuickTime window already showing a file with
    this name first: an old window keeps showing the previous version (or goes black)."""
    import subprocess
    name = Path(path).name
    subprocess.run(["osascript", "-e",
                    f'tell application "QuickTime Player" to close (every document whose name is "{name}") saving no'],
                   capture_output=True)
    subprocess.run(["open", "-a", "QuickTime Player", str(path)])


def replace_into(tmp, final):
    """Swap a finished render into place as a new file, never overwriting one in use."""
    Path(tmp).replace(final)


def loudness(path):
    """→ (integrated LUFS, true peak dBTP) of a file's sound, or (None, None) if it has none."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
                        "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    summary = r.stderr.split("Summary:")[-1]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    pk = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    val = lambda m: None if not m or m.group(1) == "-inf" else float(m.group(1))
    return val(i), val(pk)
