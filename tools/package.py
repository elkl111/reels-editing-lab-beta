"""Make a clean member copy of the Lab: no personal footage, kits, fonts, models or settings.

Usage:  python3 tools/package.py "<destination folder>"

Left out:
- models (downloaded at setup)
- the inbox, projects and inspiration folders' contents
- private kits (`"private": true`) and fonts/private/
- brand/ answers (fresh stubs instead)
- the .venv and caches

The copy behaves exactly like a new member's first open: brand/kit.txt is missing, so Claude runs setup.
"""
import json
import shutil
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"models", ".venv", "__pycache__", "projects", "inbox", "inspiration", "private", "assets", "music",
             ".git", ".lab-backup", "Finished reels"}
SKIP_FILES = {".DS_Store", "audition.m4a", "release.py"}


def main():
    dest = Path(sys.argv[1]).expanduser().resolve()
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"{dest} already exists and isn't empty.")
    private = {p.parent.name for p in (LAB / "packs").glob("*/kit.json")
               if json.loads(p.read_text()).get("private") or not json.loads(p.read_text()).get("preset")}

    def ignore(d, names):
        d = Path(d)
        out = {n for n in names if n in SKIP_DIRS or n in SKIP_FILES or n.endswith(".pyc")}
        if d == LAB / "packs":
            out |= {n for n in names if n in private}
        if d == LAB / "brand":
            out |= set(names)
        return out

    shutil.copytree(LAB, dest, ignore=ignore)
    for sub in ["inbox", "projects", "inspiration", "models", "brand", "fonts/private"]:
        (dest / sub).mkdir(parents=True, exist_ok=True)
    (dest / "brand" / "preferences.md").write_text(
        "# Editing preferences\n\nClaude adds one line here whenever you correct something that should apply to every reel.\n")
    print(f"Member copy ready: {dest}")
    print("Left out private kits:", ", ".join(sorted(private)) or "none")


if __name__ == "__main__":
    main()
