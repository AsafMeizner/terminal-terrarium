"""Play pieces from the ASCII Magic library in the terminal.

ASCII Magic (https://www.ascii-magic.com/ascii, github.com/kailashsr38/ascii-magic-art) is an
MIT-licensed library of ~700 animated ASCII pieces written in JavaScript. terrarium can play them
through its own renderer (themes, charsets, speed and keys all work) when Node.js is installed:
a small bridge (magic_bridge.mjs) runs the piece and hands frames over a pipe. The pieces are
downloaded once from the published npm package and cached in ~/.terrarium/magic/.

terrarium's own scenes never need Node; only these library pieces do.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request

from .engine import RAMPS, DEFAULT_RAMP, Scene

VERSION = "1.1.0"
CDN = f"https://cdn.jsdelivr.net/npm/ascii-magic-art@{VERSION}"
INDEX_URL = os.environ.get("TERRARIUM_MAGIC_INDEX", "https://terminal-terrarium.vercel.app/magic.json")
# Unsplash-licensed photo renderings (not MIT) and recreations of specific famous games: left out.
EXCLUDE = {"ocean-sunset", "starry-ridge"}
EXCLUDE_CATEGORIES = {"arcade"}
BRIDGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "magic_bridge.mjs")

# rough brightness of common shading glyphs, so --charset can redraw pieces in other characters
_SHADE = {}
for _ramp in (" ░▒▓█", " .:-=+*#%@", " ·∙•●", " .·oO@"):
    for _i, _c in enumerate(_ramp):
        if _c != " ":
            _SHADE.setdefault(_c, _i / (len(_ramp) - 1))


def cache_dir():
    return os.path.join(os.path.expanduser("~"), ".terrarium", "magic", VERSION)


def node_path():
    return shutil.which("node")


def load_index(max_age_days=7):
    """The piece list (name, category, note...). Downloaded from the terrarium site and cached."""
    path = os.path.join(cache_dir(), "index.json")
    try:
        if time.time() - os.path.getmtime(path) < max_age_days * 86400:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except OSError:
        pass
    try:
        if os.path.exists(INDEX_URL):  # a local file (handy when developing)
            with open(INDEX_URL, encoding="utf-8") as f:
                return json.load(f)
        req = urllib.request.Request(INDEX_URL, headers={"User-Agent": "terrarium"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        os.makedirs(cache_dir(), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data
    except Exception:
        try:  # offline: fall back to a stale copy if we have one
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except OSError:
            return {"pieces": [], "categories": []}


def allowed(slug):
    return bool(slug) and slug not in EXCLUDE and all(ch.isalnum() or ch == "-" for ch in slug)


def _hex(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return (200, 214, 210)


class MagicError(RuntimeError):
    pass


class MagicScene(Scene):
    """One ASCII Magic piece. Subclassed per piece by make_scene()."""

    name = "magic"
    title = "ASCII Magic"
    blurb = "a piece from the ASCII Magic library (needs Node.js)"
    tags = ("magic",)
    piece = ""
    _external = True  # not part of the built-in scene list

    def setup(self):
        if getattr(self, "_proc", None) is None:
            self._start()

    def _start(self):
        node = node_path()
        if not node:
            raise MagicError("ASCII Magic pieces need Node.js: install it from https://nodejs.org and try again")
        if not allowed(self.piece):
            raise MagicError(f"{self.piece!r} is not an available ASCII Magic piece")
        os.makedirs(cache_dir(), exist_ok=True)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self._proc = subprocess.Popen(
            [node, BRIDGE, self.piece, cache_dir(), CDN],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, creationflags=flags,
        )
        first = self._proc.stdout.readline()
        try:
            hello = json.loads(first)
        except ValueError:
            self.close()
            raise MagicError("couldn't start the ASCII Magic bridge (is Node.js 18 or newer installed?)")
        if "error" in hello:
            self.close()
            raise MagicError(f"couldn't load {self.piece!r}: {hello['error']}")
        self.meta = hello["meta"]
        self._palette = {k: _hex(v) for k, v in (self.meta.get("palette") or {}).items()}
        self._frame = None

    def close(self):
        p = getattr(self, "_proc", None)
        if p is not None:
            self._proc = None
            for step in (p.stdin.close, p.terminate, lambda: p.wait(timeout=2), p.stdout.close):
                try:
                    step()
                except Exception:
                    pass

    def __del__(self):
        self.close()

    def resize(self, w, h):
        self.w, self.h = w, h  # pieces have their own size; we just re-centre them

    def _fetch(self):
        p = self._proc
        if p is None:
            return None
        try:
            p.stdin.write(f"{self.t:.4f}\n")
            p.stdin.flush()
            line = p.stdout.readline()
            f = json.loads(line) if line else None
        except (OSError, ValueError):
            return None
        if not f or "error" in f:
            return None
        if f.get("palette"):
            self._palette.update({k: _hex(v) for k, v in f["palette"].items()})
        return f

    def draw(self, cv):
        f = self._fetch() or self._frame
        if not f:
            return
        self._frame = f
        lines = f["text"].split("\n")
        clines = f.get("color", "").split("\n") if f.get("color") else None
        square = self.meta.get("cell") == "square"
        sx = 2 if square else 1          # square-cell pieces: each cell is two terminal columns
        width = max((len(l) for l in lines), default=0) * sx
        ox = (cv.w - width) // 2
        oy = (cv.h - len(lines)) // 2
        remap = cv.ramp != RAMPS[DEFAULT_RAMP]
        pal = self._palette
        default = (200, 214, 210)
        for y, line in enumerate(lines):
            yy = oy + y
            if yy < 0 or yy >= cv.h:
                continue
            cl = clines[y] if clines and y < len(clines) else ""
            for x, ch in enumerate(line):
                if ch == " ":
                    continue
                key = cl[x] if x < len(cl) else " "
                rgb = pal.get(key, default) if key != " " else default
                if remap and ch in _SHADE:
                    ch = cv.glyph(_SHADE[ch])
                    if ch == " ":
                        continue
                xx = ox + x * sx
                cv.put(xx, yy, ch, rgb)
                if square:
                    cv.put(xx + 1, yy, ch, rgb)


def make_scene(slug, index=None):
    """A Scene class for one piece, e.g. make_scene("moonlit-sea")."""
    info = {}
    for p in (index or {}).get("pieces", []):
        if p.get("slug") == slug:
            info = p
            break
    if info.get("category") in EXCLUDE_CATEGORIES:
        raise MagicError(f"{slug!r} is not an available ASCII Magic piece")
    return type(f"Magic_{slug.replace('-', '_')}", (MagicScene,), {
        "name": f"magic:{slug}",
        "title": info.get("name") or slug.replace("-", " ").title(),
        "blurb": (info.get("note") or "a piece from the ASCII Magic library") + " (ASCII Magic, MIT)",
        "piece": slug,
    })
