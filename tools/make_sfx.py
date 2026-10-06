"""Generate the Lab's own sound effects (original, license-free, safe to ship to members).

Usage:  uv run tools/make_sfx.py      → sfx/*.wav (48 kHz stereo), sfx/LIBRARY.md and sfx/sound-menu.mp4

sound-menu.mp4 is the "what sounds are there?" answer: one numbered card per sound, then the sound.
It ships with the Lab, so Claude just opens it. Never generate audio previews on the fly.

Each sound is synthesised from scratch: soft and short, made to sit under a voice.
"""
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from lab import LAB

SR = 48000
OUT = LAB / "sfx"


def t(dur):
    return np.arange(int(SR * dur)) / SR


def env(x, attack, decay_rate):
    a = np.minimum(1.0, np.arange(len(x)) / max(int(SR * attack), 1))
    return x * a * np.exp(-decay_rate * np.arange(len(x)) / SR)


def lowpass(x, cutoff):
    # one-pole low-pass, enough to soften noise
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def pop(dur=0.09, f0=900, f1=260):
    tt = t(dur)
    f = f1 + (f0 - f1) * np.exp(-tt * 45)               # quick downward pitch drop
    ph = 2 * np.pi * np.cumsum(f) / SR
    return env(np.sin(ph), 0.002, 38)


def soft_pop():
    return 0.6 * pop(0.07, 700, 300)


def tick():
    tt = t(0.03)
    click = np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 260)
    rng = np.random.default_rng(1)
    noise = lowpass(rng.standard_normal(len(tt)), 5000) * np.exp(-tt * 400) * 0.4
    return env(click + noise, 0.0005, 0)


def woosh(dur=0.45):
    tt = t(dur)
    rng = np.random.default_rng(7)
    n = rng.standard_normal(len(tt))
    # sweep the brightness up then down while the level swells and fades
    shape = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 1.6
    bright = lowpass(n, 2500) * shape + lowpass(n, 700) * shape * 0.6
    return bright * 1.4


def riser(dur=0.6):
    tt = t(dur)
    rng = np.random.default_rng(3)
    n = lowpass(rng.standard_normal(len(tt)), 1800)
    tone = np.sin(2 * np.pi * np.cumsum(220 + 500 * (tt / dur) ** 2) / SR) * 0.25
    shape = (tt / dur) ** 2.2 * (1 - np.clip((tt - dur + 0.04) / 0.04, 0, 1))
    return (n * 0.8 + tone) * shape


def band(x, lo, hi):
    """Keep only frequencies between lo and hi (FFT mask; fine for short sounds)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def click_burst(dur=0.006, freq=3500, seed=0, level=1.0):
    tt = t(dur)
    rng = np.random.default_rng(seed)
    n = band(rng.standard_normal(len(tt) + 64), 2000, 9000)[:len(tt)]
    tone = np.sin(2 * np.pi * freq * tt)
    return (n * 0.7 + tone * 0.5) * np.exp(-tt * 900) * level


def place(total, items):
    """Mix short sounds into one buffer at given start times: items = [(start_s, sound)]."""
    out = np.zeros(int(SR * total))
    for st, snd in items:
        i = int(SR * st)
        j = min(len(out), i + len(snd))
        out[i:j] += snd[: j - i]
    return out


def mouse_click():
    # press, then a softer release ~70 ms later
    return place(0.1, [(0.0, click_burst(0.008, 3800, 1, 1.0)), (0.07, click_burst(0.006, 3200, 2, 0.55))])


def soft_swoosh(dur=0.38):
    tt = t(dur)
    rng = np.random.default_rng(11)
    n = rng.standard_normal(len(tt))
    shape = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 2
    return lowpass(band(n, 200, 3000), 1600) * shape


def swipe(dur=0.18):
    tt = t(dur)
    rng = np.random.default_rng(13)
    n = band(rng.standard_normal(len(tt)), 600, 9000)
    shape = (tt / dur) ** 1.5 * np.exp(-((tt - dur * 0.7) ** 2) / (2 * (dur * 0.25) ** 2))
    return n * shape


def keyboard():
    rng = np.random.default_rng(21)
    items, at = [], 0.0
    for k in range(7):
        items.append((at, click_burst(0.012, 1800 + rng.integers(-400, 600), 30 + k, 0.6 + 0.4 * rng.random())))
        at += 0.06 + 0.07 * rng.random()
    return place(at + 0.05, items)


def shutter():
    rng = np.random.default_rng(5)
    tt = t(0.05)
    whirr = band(rng.standard_normal(len(tt)), 800, 6000) * np.exp(-tt * 60) * 0.5
    return place(0.16, [(0.0, click_burst(0.01, 2600, 6, 1.0)), (0.012, whirr), (0.1, click_burst(0.008, 2100, 7, 0.7))])


def ding(f0=1320, dur=1.1):
    tt = t(dur)
    partials = [(1.0, 1.0, 3.0), (2.76, 0.45, 5.0), (5.4, 0.2, 8.0), (8.93, 0.08, 12.0)]
    x = sum(a * np.sin(2 * np.pi * f0 * r * tt) * np.exp(-tt * d) for r, a, d in partials)
    return env(x, 0.002, 0)


def sparkle():
    notes = [1568, 2093, 2637, 3136]                      # a bright rising arpeggio
    items = [(k * 0.06, 0.6 * ding(f, 0.5) * (0.9 - 0.12 * k)) for k, f in enumerate(notes)]
    return place(0.75, items)


def bubble(dur=0.09):
    tt = t(dur)
    f = 320 + 900 * (tt / dur) ** 1.3                      # pitch rises like a bubble popping up
    return env(np.sin(2 * np.pi * np.cumsum(f) / SR), 0.003, 30)


def thud(dur=0.32):
    tt = t(dur)
    f = 55 + 70 * np.exp(-tt * 30)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 14)
    rng = np.random.default_rng(9)
    knock = lowpass(rng.standard_normal(len(tt)), 900) * np.exp(-tt * 70) * 0.5
    return body + knock


def blip():
    a = 0.8 * np.sin(2 * np.pi * 880 * t(0.07)) * np.exp(-t(0.07) * 30)
    b = 0.8 * np.sin(2 * np.pi * 1320 * t(0.1)) * np.exp(-t(0.1) * 25)
    return place(0.2, [(0.0, a), (0.08, b)])


def page_flip(dur=0.32):
    tt = t(dur)
    rng = np.random.default_rng(17)
    n = band(rng.standard_normal(len(tt)), 1500, 8000)
    flutter = 0.55 + 0.45 * np.sin(2 * np.pi * 34 * tt) ** 2      # the paper's flutter
    shape = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 1.2
    return n * flutter * shape


LIBRARY = {
    # name: (generator, peak dB, what it's for)
    "pop":         (pop,         -6,  "hook lands, a point appears"),
    "soft_pop":    (soft_pop,    -9,  "highlighted word, subtle"),
    "bubble":      (bubble,      -9,  "playful pop-in"),
    "tick":        (tick,        -10, "label, small UI moment"),
    "mouse_click": (mouse_click, -8,  "a click, a choice, 'just tap this'"),
    "keyboard":    (keyboard,    -10, "typing a prompt, writing"),
    "shutter":     (shutter,     -9,  "a snapshot, a screenshot, freeze moment"),
    "soft_swoosh": (soft_swoosh, -10, "gentle transition"),
    "woosh":       (woosh,       -8,  "bigger transition, into a statement"),
    "swipe":       (swipe,       -10, "quick swipe, next idea"),
    "riser":       (riser,       -9,  "build-up before a reveal"),
    "thud":        (thud,        -7,  "a heavy point lands, a statement slams in"),
    "ding":        (ding,        -12, "an aha, a correct answer"),
    "sparkle":     (sparkle,     -13, "magic, transformation, a win"),
    "blip":        (blip,        -12, "notification, a new message"),
    "page_flip":   (page_flip,   -11, "next chapter, a list item"),
}


def save(name, x, peak_db=-6.0):
    x = x / (np.max(np.abs(x)) + 1e-9) * 10 ** (peak_db / 20)
    fade = min(len(x), int(SR * 0.005))
    x[-fade:] *= np.linspace(1, 0, fade)
    st = np.stack([x, x], axis=1)
    data = (st * 32767).astype(np.int16)
    OUT.mkdir(exist_ok=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


MENU_CARD = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:L;src:url("%(font)s");}
html,body{margin:0;background:#F3EEE6;}
.c{width:1080px;height:1080px;display:flex;flex-direction:column;justify-content:center;align-items:center;
   font-family:L,Helvetica,sans-serif;color:#2B2A28;text-align:center;box-sizing:border-box;padding:80px;}
.n{font-size:220px;font-weight:700;line-height:1;color:#D9774B;}
.t{font-size:96px;font-weight:700;margin-top:10px;}
.f{font-size:44px;margin-top:28px;opacity:.8;line-height:1.25;}
.s{font-size:32px;margin-top:40px;letter-spacing:.12em;text-transform:uppercase;opacity:.6;}
</style></head><body><div class="c">%(body)s</div></body></html>"""


def sound_menu():
    """sfx/sound-menu.mp4: an intro card with the sound sets, then each sound: number, name, use, sound."""
    import json, subprocess, tempfile
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, str(Path(__file__).parent))
    import fonts
    font = fonts.fetch("Inter", 700).as_uri()
    palettes = {k: v for k, v in json.loads((OUT / "palettes.json").read_text()).items() if not k.startswith("_")}
    names = list(LIBRARY)
    sets_of = {n: [p for p, v in palettes.items() if any(n in (v.get(m) or []) for m in ("hook", "label", "statement", "highlight"))]
               for n in names}
    cards = [("intro", '<div class="t">Sound menu</div><div class="f">Sound sets: ' +
              " · ".join(f"<b>{p}</b>" for p in palettes) +
              '<br><br>Say "use the clicky sounds",<br>"more of 6", or "no 3"</div>', None)]
    for k, n in enumerate(names, 1):
        cards.append((n, f'<div class="n">{k}</div><div class="t">{n.replace("_", " ")}</div>'
                         f'<div class="f">{LIBRARY[n][2]}</div>'
                         f'<div class="s">{" · ".join(sets_of[n]) or "extra"}</div>', OUT / f"{n}.wav"))
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": 1080, "height": 1080})
            for k, (n, body, _) in enumerate(cards):
                pg.set_content(MENU_CARD % {"font": font, "body": body})
                pg.evaluate("document.fonts.ready")
                pg.screenshot(path=str(td / f"c{k:02d}.png"))
            b.close()
        parts = []
        for k, (n, body, wav) in enumerate(cards):
            dur = 4.0 if wav is None else 2.2
            seg = td / f"s{k:02d}.mp4"
            audio = ["-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo"] if wav is None else ["-i", str(wav)]
            af = "anull" if wav is None else f"adelay=500|500,apad,atrim=0:{dur}"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", str(dur), "-i", str(td / f"c{k:02d}.png"),
                            *audio, "-filter_complex", f"[1:a]{af}[a]", "-map", "0:v", "-map", "[a]",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-t", str(dur), str(seg)], check=True)
            parts.append(seg)
        (td / "list.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(td / "list.txt"),
                        "-c", "copy", str(OUT / "sound-menu.mp4")], check=True)
    return OUT / "sound-menu.mp4"


def main():
    for name, (fn, peak, _) in LIBRARY.items():
        save(name, fn(), peak)
    (OUT / "LIBRARY.md").write_text(
        "# Sound effects\n\nAll generated by tools/make_sfx.py: original, free to use and share.\n"
        "Numbers match sfx/sound-menu.mp4. Sound sets (which sounds go on which moment) are in sfx/palettes.json.\n\n" +
        "\n".join(f"{k}. **{n}**: {d}" for k, (n, (_, _, d)) in enumerate(LIBRARY.items(), 1)) + "\n")
    print("SFX:", ", ".join(LIBRARY))
    print("MENU=" + str(sound_menu()))


if __name__ == "__main__":
    main()
