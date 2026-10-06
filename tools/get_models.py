"""Download the speech models into models/ (resumable: if it stops, run it again and it carries on).

Usage:  uv run tools/get_models.py              → Parakeet (the main engine, 2.3 GB)
        uv run tools/get_models.py --whisper    → also Whisper (the backup engine, 1.5 GB)

Uses curl with resume because Hugging Face's own downloader stalled twice on big files (ENGINE-NOTES #3).
Prints progress every few seconds so Claude can tell the user how far along it is.
"""
import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
MODELS = {
    "parakeet-tdt-0.6b-v3": ("mlx-community/parakeet-tdt-0.6b-v3",
                             ["config.json", "tokenizer.model", "tokenizer.vocab", "vocab.txt", "model.safetensors"]),
    "whisper-large-v3-turbo": ("mlx-community/whisper-large-v3-turbo", ["config.json", "weights.safetensors"]),
}


def remote_size(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Length") or r.headers.get("x-linked-size") or 0)


def fetch(repo, name, dest):
    url = f"https://huggingface.co/{repo}/resolve/main/{name}"
    out = dest / name
    try:
        size = remote_size(url)
    except Exception:
        size = 0
    if out.exists() and size and out.stat().st_size == size:
        return
    for attempt in range(20):                                   # stalls are retried, resuming where it stopped
        p = subprocess.Popen(["curl", "-sSL", "-C", "-", "--retry", "5", "--speed-limit", "50000",
                              "--speed-time", "30", "-o", str(out), url])
        last = 0
        while p.poll() is None:
            time.sleep(5)
            if size and out.exists() and time.time() - last > 20:
                print(f"  {name}: {out.stat().st_size / size:.0%} of {size / 1e9:.1f} GB", flush=True)
                last = time.time()
        if out.exists() and (not size or out.stat().st_size >= size):
            print(f"  {name}: done", flush=True)
            return
        print(f"  {name}: connection dropped, resuming…", flush=True)
    sys.exit(f"Couldn't finish downloading {name}. Check the internet connection and run this again; it resumes.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--whisper", action="store_true")
    a = ap.parse_args()
    names = ["parakeet-tdt-0.6b-v3"] + (["whisper-large-v3-turbo"] if a.whisper else [])
    for m in names:
        repo, files = MODELS[m]
        dest = LAB / "models" / m
        dest.mkdir(parents=True, exist_ok=True)
        print(f"{m}:", flush=True)
        for f in files:
            fetch(repo, f, dest)
    print("MODELS=ok")


if __name__ == "__main__":
    main()
