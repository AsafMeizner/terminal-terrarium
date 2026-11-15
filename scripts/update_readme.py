"""Regenerate the scene gallery in README.md from the scenes' own metadata.

    python scripts/update_readme.py            # rewrite the block between the scene markers
    python scripts/update_readme.py --check    # exit 1 if README is out of date
    python scripts/update_readme.py --skip=a,b # leave unfinished scenes out
    python scripts/update_readme.py --tracked  # only scenes already committed to git

Each scene's name, blurb, tags and options come from its class, and its screenshot from
docs/screenshots/NAME.png (make one with scripts/make_gifs.py NAME).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from terrarium.scenes import all_scenes  # noqa: E402

START = "<!-- scenes:start -->"
END = "<!-- scenes:end -->"

# First matching tag wins. Order matters.
SECTIONS = [
    ("Flowers", {"flowers"}),
    ("Trees & plants", {"plants"}),
    ("Creatures", {"creatures", "animals"}),
    ("Water & ocean", {"ocean", "water"}),
    ("Space", {"space"}),
    ("Sky, weather & places", {"sky", "weather", "night", "city", "fire"}),
    ("Abstract & retro", set()),
]


def section_of(cls):
    tags = set(cls.tags)
    for title, wanted in SECTIONS:
        if not wanted or tags & wanted:
            return title
    return SECTIONS[-1][0]


def build(skip=()):
    scenes = {k: v for k, v in all_scenes().items() if k not in skip}
    groups = {title: [] for title, _ in SECTIONS}
    for name, cls in scenes.items():
        groups[section_of(cls)].append((name, cls))
    out = [START, "", f"**{len(scenes)} scenes.** Every one is procedurally generated: run it twice and you get two different pictures.", ""]
    for title, items in groups.items():
        if not items:
            continue
        out += [f"### {title}", "", "| | scene | |", "|---|---|---|"]
        for name, cls in items:
            shot = f"docs/screenshots/{name}.png"
            img = f'<img src="{shot}" width="300" alt="{name}">' if os.path.exists(os.path.join(ROOT, shot)) else ""
            opts = ", ".join(f"`{k}`" for k in cls.options) or "—"
            out.append(f"| {img} | **`{name}`** | {cls.blurb}<br><sub>options: {opts}</sub> |")
        out.append("")
    out.append(END)
    return "\n".join(out)


def main():
    path = os.path.join(ROOT, "README.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if START not in text or END not in text:
        sys.exit("README.md has no scene markers")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    skip = set()
    if "--tracked" in sys.argv:  # only scenes committed to git (skip work in progress)
        import subprocess

        tracked = subprocess.run(["git", "ls-files", "terrarium/scenes"], cwd=ROOT,
                                 capture_output=True, text=True, check=True).stdout.split()
        names = {os.path.splitext(os.path.basename(f))[0] for f in tracked}
        skip |= set(all_scenes()) - names
    for a in sys.argv[1:]:
        if a.startswith("--skip="):
            skip |= set(a.split("=", 1)[1].split(","))
    new = head + build(skip) + tail
    if "--check" in sys.argv:
        if new != text:
            sys.exit("README.md scene list is out of date: run python scripts/update_readme.py")
        return
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print("README.md updated")


if __name__ == "__main__":
    main()
