"""Free fonts for kits: download a Google Font once into fonts/free/ so reels render offline.

Usage:  uv run tools/fonts.py "Instrument Serif" [--weight 400] [--italic]

In a kit, a font is either a file the user owns:
    "display": {"family": "Awesome Serif", "file": "fonts/private/AwesomeSerif-MediumTall.otf", "weight": 500}
or a free Google Font (fetched automatically by build.py the first time):
    "display": {"family": "Instrument Serif", "google": true, "weight": 400, "italic": false}
Google Fonts are open-licensed (OFL), so kits that use them are safe to share.
"""
import argparse
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import LAB

FREE = LAB / "fonts" / "free"


def local_path(family, weight=400, italic=False):
    return FREE / f"{family.replace(' ', '')}-{weight}{'i' if italic else ''}.ttf"


def fetch(family, weight=400, italic=False):
    """Return the local file for this Google Font, downloading it the first time."""
    out = local_path(family, weight, italic)
    if out.exists():
        return out
    axis = f"ital,wght@{1 if italic else 0},{weight}"
    url = "https://fonts.googleapis.com/css2?family=" + urllib.parse.quote(family) + ":" + axis
    try:
        css = urllib.request.urlopen(url, timeout=30).read().decode()
    except Exception:
        # some families have no weight axis (e.g. Anton, Instrument Serif): ask for the plain style
        url = "https://fonts.googleapis.com/css2?family=" + urllib.parse.quote(family) + (":ital@1" if italic else "")
        try:
            css = urllib.request.urlopen(url, timeout=30).read().decode()
        except Exception as e:
            raise SystemExit(f"Couldn't find the Google Font '{family}' ({'italic ' if italic else ''}{weight}): {e}")
    m = re.search(r"src:\s*url\((https://[^)]+\.ttf)\)", css)
    if not m:
        raise SystemExit(f"Google Fonts returned no file for '{family}'.")
    FREE.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    urllib.request.urlretrieve(m.group(1), tmp)
    tmp.replace(out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("family")
    ap.add_argument("--weight", type=int, default=400)
    ap.add_argument("--italic", action="store_true")
    a = ap.parse_args()
    print(fetch(a.family, a.weight, a.italic))
