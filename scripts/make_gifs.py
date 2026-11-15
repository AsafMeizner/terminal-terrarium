"""Render README previews (needs Pillow).

    python scripts/make_gifs.py                 # PNG screenshot of every scene + GIFs of the highlights
    python scripts/make_gifs.py koi bonsai      # just these scenes (PNG, plus GIF if a highlight)
    python scripts/make_gifs.py --gif koi       # force a GIF for these scenes

Screenshots go to docs/screenshots/NAME.png, animations to docs/gifs/NAME.gif.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from terrarium.scenes import all_scenes  # noqa: E402

SHOTS = os.path.join(ROOT, "docs", "screenshots")
GIFS = os.path.join(ROOT, "docs", "gifs")

# Animated previews at the top of the README. Keep this list short: GIFs are heavy.
HIGHLIGHTS = ["jellyfish", "lilies", "bonsai", "timelapse", "fireworks", "whale", "butterflies",
              "aurora", "volcano", "koi", "campfire", "lavalamp"]

# Seconds to simulate before capturing, for scenes that grow or bloom.
WARMUP = {"bonsai": 40, "rose": 22, "seasons": 20, "sakura": 10, "snow": 30, "life": 6,
          "campfire": 6, "timelapse": 30, "volcano": 12, "fireworks": 3, "peacock": 14}
SEED = {"rain": 3}
OPTS = {"rain": ["-o", "skyline=city"]}  # extra flags for nicer previews


def run(name, args):
    base = [sys.executable, "-m", "terrarium", name, "--warmup", str(WARMUP.get(name, 6)),
            "--seed", str(SEED.get(name, 7))] + OPTS.get(name, [])
    subprocess.run(base + args, cwd=ROOT, check=True, capture_output=True)


def main(argv):
    force_gif = "--gif" in argv
    names = [a for a in argv if not a.startswith("--")]
    scenes = all_scenes()
    os.makedirs(SHOTS, exist_ok=True)
    os.makedirs(GIFS, exist_ok=True)
    for name in names or scenes:
        if name not in scenes:
            print(f"skip unknown scene {name}")
            continue
        png = os.path.join(SHOTS, f"{name}.png")
        run(name, ["--snapshot", png, "--size", "120x40", "--font-size", "10"])
        line = f"{name:<14} png {os.path.getsize(png) / 1024:5.0f} KB"
        if force_gif or name in HIGHLIGHTS:
            gif = os.path.join(GIFS, f"{name}.gif")
            run(name, ["--record", gif, "--size", "110x36", "--frames", "60", "--fps", "15", "--font-size", "10"])
            line += f"   gif {os.path.getsize(gif) / 1024:5.0f} KB"
        print(line, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
