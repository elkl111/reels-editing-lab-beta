"""Setup check: what this Mac has, what's missing, and how to fix it.

Usage:  uv run tools/doctor.py          → a plain checklist + DOCTOR=ok | DOCTOR=missing:<names>
        python3 tools/doctor.py         (works before uv exists too)

Each line: ✓ / ✗ name: what it is (and the fix if missing). The setup skill reads this and fixes
things in order. Nothing here installs anything.
"""
import importlib.util
import platform
import shutil
import subprocess
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
PARAKEET = LAB / "models" / "parakeet-tdt-0.6b-v3" / "model.safetensors"


def check():
    rows = []

    def add(name, ok, what, fix=""):
        rows.append((name, ok, what, fix))

    add("mac", platform.system() == "Darwin" and platform.machine() == "arm64",
        "a Mac with an Apple chip (M1 or newer)", "The Lab needs an Apple-chip Mac for now.")
    free = shutil.disk_usage(LAB).free / 1e9
    add("space", free > 6, f"{free:.0f} GB free (needs about 6 GB)", "Free up some disk space.")
    add("homebrew", bool(shutil.which("brew") or Path("/opt/homebrew/bin/brew").exists()),
        "Homebrew, the Mac's app installer for tools like ffmpeg",
        'The user pastes this into the Terminal app (it asks for their Mac password): '
        '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
    add("ffmpeg", bool(shutil.which("ffmpeg") and shutil.which("ffprobe")), "ffmpeg, the video engine",
        "brew install ffmpeg")
    add("uv", bool(shutil.which("uv") or (Path.home() / ".local/bin/uv").exists()), "uv, runs the Lab's Python tools",
        "curl -LsSf https://astral.sh/uv/install.sh | sh")
    xcode = subprocess.run(["xcode-select", "-p"], capture_output=True).returncode == 0 and bool(shutil.which("swiftc"))
    built = (LAB / "tools" / "bin" / "faces").exists() and (LAB / "tools" / "bin" / "matte").exists()
    add("apple-tools", xcode or built, "Apple's command line tools (face finding and cut-outs)",
        "xcode-select --install   (a Mac window pops up: click Install)")
    venv = LAB / ".venv"
    add("python-tools", venv.exists() and any(venv.glob("lib/python3*/site-packages/parakeet_mlx")),
        "the Lab's Python tools", "uv sync")
    chromium = list((Path.home() / "Library/Caches/ms-playwright").glob("chromium*"))
    add("renderer", bool(chromium), "the graphics renderer (a hidden browser)", "uv run playwright install chromium")
    add("speech-model", PARAKEET.exists() and PARAKEET.stat().st_size > 2_000_000_000,
        "the speech model that writes down every word (2.3 GB, runs on this Mac)", "uv run tools/get_models.py")
    add("look", (LAB / "brand" / "kit.txt").exists(), "a chosen look (set during onboarding)", "the setup skill")
    return rows


if __name__ == "__main__":
    rows = check()
    for name, ok, what, fix in rows:
        print(f"{'✓' if ok else '✗'} {name}: {what}" + ("" if ok else f"\n    fix: {fix}"))
    missing = [r[0] for r in rows if not r[1]]
    print("DOCTOR=" + ("ok" if not missing else "missing:" + ",".join(missing)))
