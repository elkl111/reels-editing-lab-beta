"""Clip intake: check a raw clip fits the beta, and prepare it for editing.

Usage:  uv run tools/intake.py "<clip>"      → a plain verdict (used by transcribe.py automatically)

Beta scope: vertical phone clips (9:16), English, up to about 4 minutes.
- Horizontal clips are refused with a friendly message.
- Clips over 4 minutes get a warning (slower and harder to review); over 6 minutes are refused.
- HDR clips (iPhone's default "HDR Video": HLG or Dolby Vision, 10-bit) are converted once to
  standard colour with Apple's own converter (avconvert, built into macOS). Otherwise every
  graphic would sit on washed-out, grey-looking footage. The original is never touched.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import run

WARN_MIN, MAX_MIN = 4, 6
HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}


def probe(clip):
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=codec_type,codec_name,width,height,pix_fmt,color_transfer:stream_side_data=rotation:format=duration",
               "-of", "json", str(clip)])
    d = json.loads(out)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
    a = any(s.get("codec_type") == "audio" for s in d.get("streams", []))
    rot = 0
    for sd in (v or {}).get("side_data_list", []):
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = (v or {}).get("width", 0), (v or {}).get("height", 0)
    if abs(rot) % 180 == 90:
        w, h = h, w
    return {"video": v is not None, "audio": a, "w": w, "h": h, "duration": float(d["format"].get("duration", 0)),
            "hdr": bool(v) and (v.get("color_transfer") in HDR_TRANSFERS or "10" in (v.get("pix_fmt") or "")),
            "codec": (v or {}).get("codec_name")}


def check(clip):
    """→ (ok, problems, notes): plain-language messages for the user."""
    p = probe(clip)
    problems, notes = [], []
    if not p["video"]:
        problems.append("This file has no video in it.")
    if not p["audio"]:
        problems.append("This clip has no sound, and the Lab edits by what you say.")
    if p["video"] and p["w"] > p["h"]:
        problems.append("This clip is horizontal. The beta edits vertical (9:16) phone clips only. Film holding the phone upright.")
    m = p["duration"] / 60
    if m > MAX_MIN:
        problems.append(f"This clip is {m:.0f} minutes. The beta takes clips up to about {WARN_MIN} minutes. "
                        "Trim it in the Photos app (Edit → drag the ends) or film it in parts.")
    elif m > WARN_MIN:
        notes.append(f"This clip is {m:.1f} minutes, longer than the {WARN_MIN} minutes the beta is tuned for. "
                     "It will work, but expect slower steps and a longer review.")
    if p["hdr"]:
        notes.append("Filmed in HDR: making a standard-colour copy first so colours and graphics look right.")
    return not problems, problems, notes, p


def prepare(clip, proj):
    """Return the file to edit from: the clip itself, or a standard-colour copy of an HDR clip."""
    ok, problems, notes, p = check(clip)
    for n in notes:
        print("NOTE:", n)
    if not ok:
        for x in problems:
            print("PROBLEM:", x)
        raise SystemExit("INTAKE=refused")
    if not p["hdr"]:
        return Path(clip)
    out = proj / "source-sdr.mov"
    if out.exists() and out.stat().st_mtime >= Path(clip).stat().st_mtime:
        return out
    tmp = proj / "source-sdr.tmp.mov"
    r = subprocess.run(["avconvert", "-s", str(clip), "-p", "Preset1920x1080", "-o", str(tmp), "--replace"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not tmp.exists():
        raise SystemExit(f"Couldn't convert the HDR clip: {r.stderr[-400:] or r.stdout[-400:]}")
    tmp.replace(out)
    print("NOTE: standard-colour copy ready.")
    return out


if __name__ == "__main__":
    ok, problems, notes, p = check(sys.argv[1])
    print(f"{p['w']}x{p['h']}, {p['duration'] / 60:.1f} min, {'HDR' if p['hdr'] else 'standard colour'}, {p['codec']}")
    for x in problems:
        print("PROBLEM:", x)
    for n in notes:
        print("NOTE:", n)
    print("INTAKE=" + ("ok" if ok else "refused"))
