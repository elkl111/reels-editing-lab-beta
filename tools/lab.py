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
