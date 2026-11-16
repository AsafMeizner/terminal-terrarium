"""Command line interface."""
from __future__ import annotations

import argparse
import random
import sys

from . import __version__
from .engine import RAMPS, THEMES, detect_color_mode
from .scenes import add_path, all_scenes, errors, plugin_dirs

EPILOG = """examples:
  terrarium                          a random scene
  terrarium jellyfish                one scene
  terrarium bonsai sakura --cycle 40 rotate between scenes every 40s
  terrarium --all --shuffle --cycle 30
  terrarium --tag ocean --cycle 30   every scene tagged 'ocean'
  terrarium jellyfish -t vapor -o count=9 -s 0.6
  terrarium bonsai --seed 42 --charset blocks
  terrarium koi --record koi.gif --size 90x30 --frames 120
  terrarium --magic-list moon        find ASCII Magic library pieces (needs Node.js to play)
  terrarium magic:moonlit-sea        play one, with all of terrarium's themes and keys
keys while running: space pause, n/p next/prev, t theme, c charset, +/- speed, ? help, q quit
"""


def _size(s):
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except ValueError:
        raise argparse.ArgumentTypeError("size must look like 100x32")


def build_parser():
    p = argparse.ArgumentParser(
        prog="terrarium",
        description="A terrarium of animated ASCII art for your terminal: jellyfish, bonsai, flowers, koi, aurora and more.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("scenes", nargs="*", help="scene name(s); omit for a random one (see --list)")
    g = p.add_argument_group("choosing scenes")
    g.add_argument("-l", "--list", action="store_true", help="list scenes and exit")
    g.add_argument("--info", metavar="SCENE", help="describe a scene and its -o options")
    g.add_argument("-a", "--all", action="store_true", help="use every scene")
    g.add_argument("--tag", action="append", default=[], help="use scenes with this tag (repeatable)")
    g.add_argument("--cycle", type=float, metavar="SECS", help="switch to the next scene every SECS seconds")
    g.add_argument("--shuffle", action="store_true", help="shuffle scene order")
    g.add_argument("--duration", type=float, metavar="SECS", help="exit after SECS seconds")

    g = p.add_argument_group("the ASCII Magic library (~700 more pieces, needs Node.js)")
    g.add_argument("--magic", nargs="?", const="random", metavar="PIECE",
                   help="play an ASCII Magic piece (random if no name); same as the scene name magic:PIECE")
    g.add_argument("--magic-list", nargs="?", const="", metavar="WORD",
                   help="list ASCII Magic pieces, optionally only those matching WORD")

    g = p.add_argument_group("making your own scenes")
    g.add_argument("--new", metavar="NAME", help="write a ready-to-edit scene template NAME.py and exit")
    g.add_argument("--path", action="append", default=[], metavar="DIR",
                   help="also load scenes from DIR (also: ~/.terrarium/scenes, $TERRARIUM_PATH)")

    g = p.add_argument_group("look")
    g.add_argument("-t", "--theme", default="natural", choices=list(THEMES), metavar="NAME",
                   help="color theme (see --themes); default: natural")
    g.add_argument("--themes", action="store_true", help="list themes and exit")
    g.add_argument("--charset", default="ascii", choices=list(RAMPS), metavar="NAME",
                   help=f"shading characters: {', '.join(RAMPS)}")
    g.add_argument("--color", default="auto", choices=["auto", "truecolor", "256", "mono"],
                   help="color output mode (default: auto-detect)")
    g.add_argument("--hue", type=float, default=0.0, metavar="DEG", help="rotate all hues by DEG degrees")
    g.add_argument("--saturation", type=float, default=1.0, metavar="X", help="saturation multiplier (0 = grey)")
    g.add_argument("--brightness", type=float, default=1.0, metavar="X", help="brightness multiplier")
    g.add_argument("--message", metavar="TEXT", help="show a caption in the middle of the screen")

    g = p.add_argument_group("motion")
    g.add_argument("-s", "--speed", type=float, default=1.0, metavar="X", help="animation speed multiplier")
    g.add_argument("-d", "--density", type=float, default=1.0, metavar="X",
                   help="how many things (fish, petals, stars...), multiplier")
    g.add_argument("--fps", type=int, default=30, help="target frames per second (default 30)")
    g.add_argument("--seed", type=int, help="random seed for a reproducible scene")
    g.add_argument("-o", "--option", action="append", default=[], metavar="KEY=VAL",
                   help="scene-specific option, e.g. -o count=7 (see --info SCENE)")

    g = p.add_argument_group("interface")
    g.add_argument("--hud", action="store_true", help="show the info bar (toggle with i)")
    g.add_argument("--no-title", dest="title", action="store_false", help="don't show the scene title card")
    g.add_argument("--no-alt-screen", action="store_true", help="draw in the normal screen buffer")
    g.add_argument("--no-mouse", action="store_true", help="don't capture the mouse (some scenes react to clicks)")

    g = p.add_argument_group("export (png/gif need Pillow)")
    g.add_argument("--snapshot", metavar="FILE", help="render one frame to FILE (.png, .txt or .ans) and exit")
    g.add_argument("--record", metavar="FILE.gif", help="record an animated GIF and exit")
    g.add_argument("--size", type=_size, default=(100, 32), metavar="WxH", help="export size in cells (default 100x32)")
    g.add_argument("--frames", type=int, default=90, help="GIF frame count (default 90)")
    g.add_argument("--warmup", type=float, default=4.0, metavar="SECS", help="simulate SECS before capturing")
    g.add_argument("--font", metavar="TTF", help="font file for image export")
    g.add_argument("--font-size", type=int, default=16, help="font size for image export")
    p.add_argument("-V", "--version", action="version", version=f"terrarium {__version__}")
    return p


def _parse_options(items):
    out = {}
    for it in items:
        if "=" not in it:
            sys.exit(f"terrarium: -o expects KEY=VAL, got {it!r}")
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _print_list(scenes):
    width = max(len(n) for n in scenes) + 2
    print(f"{len(scenes)} scenes:\n")
    for name, cls in scenes.items():
        tags = f"  [{', '.join(cls.tags)}]" if cls.tags else ""
        star = " *" if cls.interactions else "  "
        print(f"{star}{name:<{width}}{cls.blurb}{tags}")
    print("\n * reacts to your mouse: click or point at it")
    print("run `terrarium --info NAME` for a scene's options, `terrarium --new NAME` to make your own")
    dirs = plugin_dirs()
    if dirs:
        print("plugin dirs: " + ", ".join(dirs))
    bad = errors()
    if bad:
        print("\nscenes that failed to load:", file=sys.stderr)
        for k, v in bad.items():
            print(f"  {k}: {v}", file=sys.stderr)


def _print_info(cls):
    print(f"{cls.title or cls.name}  ({cls.name})")
    print(f"  {cls.blurb}")
    if cls.tags:
        print(f"  tags: {', '.join(cls.tags)}")
    if cls.interactions:
        print(f"  mouse: {cls.interactions}")
    if cls.options:
        print("  options (-o key=value):")
        for k, (default, help_) in cls.options.items():
            print(f"    {k:<12} {help_}  (default: {default})")
    else:
        print("  no scene-specific options")


def _new_scene(name, directory):
    import os
    import re

    from .template import render

    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        sys.exit("terrarium: scene names are lowercase letters, digits and _ (e.g. northern_lights)")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{name}.py")
    if os.path.exists(path):
        sys.exit(f"terrarium: {path} already exists")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(name))
    print(f"wrote {path}")
    print(f"try it:   terrarium {name} --path {directory}")
    print("or move it to ~/.terrarium/scenes/ to have it everywhere, or into terrarium/scenes/ to contribute it")
    return 0


def _magic_scene(slug):
    """Validate and build the Scene class for an ASCII Magic piece (before the terminal is taken)."""
    from .engine import Context
    from .magic import MagicError, load_index, make_scene, node_path

    if not node_path():
        sys.exit("terrarium: ASCII Magic pieces need Node.js (https://nodejs.org). terrarium's own scenes don't.")
    index = load_index()
    known = {p["slug"] for p in index.get("pieces", [])}
    if slug == "random":
        if not known:
            sys.exit("terrarium: couldn't get the ASCII Magic piece list (are you online?)")
        slug = random.choice(sorted(known))
    elif known and slug not in known:
        close = sorted(s for s in known if slug in s)[:6]
        hint = f" (did you mean {', '.join(close)}?)" if close else " (try --magic-list)"
        sys.exit(f"terrarium: no ASCII Magic piece called {slug!r}{hint}")
    try:
        cls = make_scene(slug, index)
        probe = cls(Context(seed=1), 80, 24)   # downloads + checks the piece once, then caches it
        probe.close()
    except MagicError as e:
        sys.exit(f"terrarium: {e}")
    return cls


def _print_magic(word):
    from .magic import load_index, node_path

    index = load_index()
    pieces = index.get("pieces", [])
    if not pieces:
        sys.exit("terrarium: couldn't get the ASCII Magic piece list (are you online?)")
    cats = {c["id"]: c["name"] for c in index.get("categories", [])}
    w = word.lower()
    hits = [p for p in pieces if not w or w in p["slug"] or w in p["name"].lower() or w in p.get("note", "").lower()]
    width = max((len(p["slug"]) for p in hits), default=10) + 2
    for p in hits:
        print(f"  {p['slug']:<{width}}{cats.get(p['category'], p['category'])}: {p['note'][:70]}")
    print(f"\n{len(hits)} of {len(pieces)} ASCII Magic pieces (https://www.ascii-magic.com/ascii, MIT).")
    print("play one with:  terrarium magic:NAME" + ("" if node_path() else "   (install Node.js first: https://nodejs.org)"))
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.options = _parse_options(args.option)
    if args.new:
        return _new_scene(args.new, args.path[0] if args.path else ".")
    for d in args.path:
        add_path(d)
    scenes = all_scenes()
    if not scenes:
        sys.exit("terrarium: no scenes could be loaded: " + str(errors()))

    if args.list:
        _print_list(scenes)
        return 0
    if args.magic_list is not None:
        return _print_magic(args.magic_list)
    if args.magic:
        args.scenes = [f"magic:{args.magic}"] + list(args.scenes)
    if args.themes:
        for name, th in THEMES.items():
            print(f"  {name:<12}{th.get('blurb', '')}")
        return 0
    if args.info:
        if args.info not in scenes:
            sys.exit(f"terrarium: unknown scene {args.info!r} (try --list)")
        _print_info(scenes[args.info])
        return 0

    for n in args.scenes:
        if n.startswith("magic:"):
            continue
        if n not in scenes:
            close = [s for s in scenes if s.startswith(n[:3])]
            hint = f" — did you mean {', '.join(close)}?" if close else " (try --list)"
            sys.exit(f"terrarium: unknown scene {n!r}{hint}")

    if args.scenes:
        chosen = [_magic_scene(n[6:]) if n.startswith("magic:") else scenes[n] for n in args.scenes]
    elif args.tag:
        chosen = [c for c in scenes.values() if set(args.tag) & set(c.tags)]
        if not chosen:
            sys.exit(f"terrarium: no scenes tagged {', '.join(args.tag)}")
    elif args.all or args.cycle:
        chosen = list(scenes.values())
    else:
        chosen = [random.choice(list(scenes.values()))]
    if args.shuffle:
        random.shuffle(chosen)

    if args.snapshot or args.record:
        from .export import export

        path = export(chosen[0], args)
        print(f"wrote {path}")
        return 0

    if args.color == "auto":
        args.color = detect_color_mode()
    if not sys.stdout.isatty():
        sys.exit("terrarium: stdout is not a terminal (use --snapshot/--record to render to a file)")

    from .app import App

    App(chosen, args).run()
    return 0
