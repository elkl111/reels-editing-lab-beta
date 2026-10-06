"""Memes and GIFs for a reel: search a GIF library, or bring in the user's own file.

Usage:
  uv run tools/memes.py search "schitts creek david ew" --project projects/<name> [--n 6]
  uv run tools/memes.py add "<file.gif|.mp4|.mov|.png|.jpg>" --project projects/<name>

Search uses GIPHY (free key, 100 searches an hour), then KLIPY if a key is set. Keys live in
brand/keys.json: {"giphy": "...", "klipy": "..."}. They're never shared, because brand/ stays out of member copies.
Results land in projects/<name>/memes/: 1.mp4 … 6.mp4, index.json (title, source, size) and sheet.png
(numbered tiles). Claude looks at sheet.png, picks the one matching the request, and puts it in build.json as
{"kind": "gif", "file": "projects/<name>/memes/3.mp4", "word": i, "caption": "..."}.
"""
import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lab import LAB, load_json, run, save_json

KEYS = LAB / "brand" / "keys.json"
NO_KEY = ("MEMES=no-key  Searching needs a free GIPHY key (about 3 minutes, one time). "
          "Their own GIF or video files work without one: `memes.py add <file>`.")


def keys():
    return load_json(KEYS) if KEYS.exists() else {}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ReelsEditingLab/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def giphy(q, n, key):
    d = get("https://api.giphy.com/v1/gifs/search?" + urllib.parse.urlencode(
        {"api_key": key, "q": q, "limit": n, "rating": "pg-13", "lang": "en"}))
    out = []
    for g in d.get("data", []):
        im = g.get("images", {})
        mp4 = (im.get("original_mp4") or {}).get("mp4") or (im.get("original") or {}).get("mp4") \
            or (im.get("fixed_height") or {}).get("mp4")
        if mp4:
            out.append({"title": g.get("title", ""), "source": g.get("url", ""), "mp4": mp4, "from": "GIPHY"})
    return out


def klipy(q, n, key):
    d = get(f"https://api.klipy.com/api/v1/{key}/gifs/search?" + urllib.parse.urlencode({"q": q, "per_page": n}))
    items = (d.get("data") or {}).get("data") or d.get("data") or []
    out = []

    def find_mp4(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "url" and isinstance(v, str) and v.endswith(".mp4"):
                    return v
                r = find_mp4(v)
                if r:
                    return r
        return None
    for g in items if isinstance(items, list) else []:
        mp4 = find_mp4(g.get("file", g))
        if mp4:
            out.append({"title": g.get("title", ""), "source": g.get("url", ""), "mp4": mp4, "from": "KLIPY"})
    return out


def probe(f):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
               "-of", "json", str(f)])
    d = json.loads(out)
    s = d["streams"][0]
    return s["width"], s["height"], float(d["format"].get("duration") or 3.0)


def sheet(mdir, items):
    """Numbered contact sheet: the middle frame of each clip, so Claude (or the user) can pick by eye."""
    tiles = []
    for it in items:
        f = mdir / it["file"]
        t = mdir / f"tile-{it['n']}.png"
        mid = max(0.1, it["duration"] / 2)
        # number in the corner: drawn as a solid block plus the clip index in the file name, since ffmpeg has no drawtext
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{mid:.2f}", "-i", str(f), "-frames:v", "1",
             "-vf", "scale=360:360:force_original_aspect_ratio=decrease,pad=380:380:(ow-iw)/2:(oh-ih)/2:white", str(t)])
        tiles.append(t)
    lst = mdir / "tiles.txt"
    lst.write_text("".join(f"file '{t}'\n" for t in tiles))
    cols = min(3, len(tiles))
    rows = -(-len(tiles) // cols)
    out = mdir / "sheet.png"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", f"tile={cols}x{rows}",
         "-frames:v", "1", str(out)])
    return out


def save_clip(src_url_or_path, dst):
    if str(src_url_or_path).startswith("http"):
        tmp = dst.with_suffix(".dl.mp4")
        urllib.request.urlretrieve(src_url_or_path, tmp)
        src = tmp
    else:
        src = Path(src_url_or_path)
    # one clean format for the build: H.264, even dimensions, no audio, at most 4s
    if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", "3", "-i", str(src), "-vf",
             "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p", "-c:v", "libx264", "-r", "30", str(dst)])
    else:
        run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-t", "4", "-an", "-vf",
             "scale='min(720,iw)':-2,scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30,format=yuv420p", "-c:v", "libx264", str(dst)])
    if str(src_url_or_path).startswith("http"):
        src.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["search", "add"])
    ap.add_argument("what")
    ap.add_argument("--project", required=True)
    ap.add_argument("--n", type=int, default=6)
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    mdir = proj / "memes"
    mdir.mkdir(parents=True, exist_ok=True)
    idx_p = mdir / "index.json"
    index = load_json(idx_p) if idx_p.exists() else {"search": None, "items": []}

    if a.action == "add":
        n = f"own-{sum(1 for i in index['items'] if str(i['n']).startswith('own')) + 1}"
        f = mdir / f"{n}.mp4"
        save_clip(Path(a.what).expanduser(), f)
        w, h, d = probe(f)
        index["items"].append({"n": n, "file": f.name, "title": Path(a.what).name, "source": "own file",
                               "w": w, "h": h, "duration": d})
        save_json(idx_p, index)
        print(f"MEME={f}  ({w}x{h}, {d:.1f}s)")
        return

    k = keys()
    if not (k.get("giphy") or k.get("klipy")):
        sys.exit(NO_KEY)
    results = []
    try:
        if k.get("giphy"):
            results = giphy(a.what, a.n, k["giphy"])
        if len(results) < a.n and k.get("klipy"):
            results += klipy(a.what, a.n - len(results), k["klipy"])
    except Exception as e:
        sys.exit(f"MEMES=search-failed  ({e})")
    if not results:
        sys.exit("MEMES=none  Nothing found: try simpler words (show + character + emotion).")
    for old in mdir.glob("[0-9]*.mp4"):
        old.unlink()
    items = [i for i in index["items"] if str(i["n"]).startswith("own")]
    found = []
    for n, r in enumerate(results[:a.n], 1):
        f = mdir / f"{n}.mp4"
        try:
            save_clip(r["mp4"], f)
        except Exception:
            continue
        w, h, d = probe(f)
        found.append({"n": n, "file": f.name, "title": r["title"], "source": r["source"], "from": r["from"],
                      "w": w, "h": h, "duration": d})
    index = {"search": a.what, "items": items + found}
    save_json(idx_p, index)
    sh = sheet(mdir, found)
    for it in found:
        print(f"{it['n']}. {it['title'] or '(untitled)'}  {it['duration']:.1f}s  [{it['from']}]")
    print(f"SHEET={sh}  (tiles in order 1…{len(found)}, left to right, top to bottom)")


if __name__ == "__main__":
    main()
