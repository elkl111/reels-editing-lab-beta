"""Find icons for pop-ups (Lucide, free licence; 2,000+ icons).

Usage:  uv run tools/icons.py calendar money email     → matching icon names for each word
"""
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
icons = json.loads((LAB / "effects" / "icons.json").read_text())
tags = json.loads((LAB / "effects" / "icon-tags.json").read_text())

for word in sys.argv[1:]:
    w = word.lower()
    exact = [n for n in icons if n == w]
    named = [n for n in icons if w in n and n not in exact]
    tagged = [n for n, ts in tags.items() if any(w == t.lower() for t in ts) and n not in exact + named]
    hits = (exact + sorted(named, key=len) + sorted(tagged, key=len))[:12]
    print(f"{word}: {', '.join(hits) if hits else '(none — try a simpler word)'}")
