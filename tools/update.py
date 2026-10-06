"""Update the Lab to the newest version, keeping everything that's the user's own.

Usage:  python3 tools/update.py [--check]

Downloads the latest member version (lab.json → update_url, a zip), and replaces only the engine:
the tools, the graphics, the skills, the sounds, the free fonts and the starter looks.
Never touched: brand/ (their answers and preferences), their own kit in packs/, projects/, inbox/,
Finished reels/, models/, fonts/private/. The previous engine is kept in .lab-backup/<version>/.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
ENGINE_DIRS = ["tools", "effects", "sfx", "fonts/free"]
ENGINE_FILES = ["CLAUDE.md", "SETUP.md", "README.md", "ENGINE-NOTES.md", "CHANGELOG.md", "VERSION",
                "pyproject.toml", "uv.lock", "lab.json", ".claude/settings.json", ".gitignore"]


def vtuple(v):
    return tuple(int(x) for x in v.strip().split(".") if x.isdigit())


def changes_since(changelog, old):
    """The changelog sections newer than the user's version."""
    out, keep = [], False
    for line in changelog.splitlines():
        if line.startswith("## "):
            ver = line[3:].split(":")[0].strip()
            keep = vtuple(ver) > vtuple(old) if ver[:1].isdigit() else False
        if keep:
            out.append(line)
    return "\n".join(out).strip()


def main():
    cfg = json.loads((LAB / "lab.json").read_text())
    url = cfg.get("update_url")
    if not url:
        sys.exit("UPDATE=not-configured  (this copy of the Lab has no update address yet)")
    old = (LAB / "VERSION").read_text().strip() if (LAB / "VERSION").exists() else "0"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        zp = td / "lab.zip"
        try:
            urllib.request.urlretrieve(url, zp)
        except Exception as e:
            sys.exit(f"UPDATE=download-failed  ({e}). Check the internet connection and try again.")
        with zipfile.ZipFile(zp) as z:
            z.extractall(td / "x")
        roots = [p for p in (td / "x").iterdir() if p.is_dir()]
        new = roots[0] if len(roots) == 1 and not (td / "x" / "VERSION").exists() else td / "x"
        nv = (new / "VERSION").read_text().strip()
        if vtuple(nv) <= vtuple(old):
            print(f"UPDATE=current  (you have {old}, the newest)")
            return
        if "--check" in sys.argv:
            print(f"UPDATE=available  {old} → {nv}\n" + changes_since((new / "CHANGELOG.md").read_text(), old))
            return
        backup = LAB / ".lab-backup" / old
        backup.mkdir(parents=True, exist_ok=True)
        before_deps = [(LAB / f).read_text() if (LAB / f).exists() else "" for f in ("pyproject.toml", "uv.lock")]
        # engine folders: replace whole
        for d in ENGINE_DIRS:
            if (LAB / d).exists():
                shutil.move(str(LAB / d), str(backup / d.replace("/", "_")))
            if (new / d).exists():
                shutil.copytree(new / d, LAB / d)
        # skills: replace the ones the Lab ships, leave any the user added
        for sk in (new / ".claude" / "skills").iterdir():
            dst = LAB / ".claude" / "skills" / sk.name
            if dst.exists():
                shutil.move(str(dst), str(backup / f"skill_{sk.name}"))
            shutil.copytree(sk, dst)
        for f in ENGINE_FILES:
            if (new / f).exists():
                if (LAB / f).exists():
                    shutil.copy2(LAB / f, backup / f.replace("/", "_"))
                (LAB / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(new / f, LAB / f)
        # starter looks only; the user's own kit is never touched
        for kp in (new / "packs").glob("*/kit.json"):
            if json.loads(kp.read_text()).get("preset"):
                (LAB / "packs" / kp.parent.name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(kp, LAB / "packs" / kp.parent.name / "kit.json")
        after_deps = [(LAB / f).read_text() if (LAB / f).exists() else "" for f in ("pyproject.toml", "uv.lock")]
        if after_deps != before_deps:
            print("Updating the Python tools…", flush=True)
            subprocess.run(["uv", "sync"], cwd=LAB)
        print(f"UPDATE=done  {old} → {nv}\n" + changes_since((new / "CHANGELOG.md").read_text(), old))


if __name__ == "__main__":
    main()
