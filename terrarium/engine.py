"""Core engine: canvas, color pipeline, terminal I/O, keyboard input, scene base class."""
from __future__ import annotations

import math
import os
import random
import shutil
import sys

# Terminal cells are roughly twice as tall as they are wide. Multiply a y-distance
# (in cells) by ASPECT to compare it with an x-distance (in cells).
ASPECT = 2.0

RAMPS = {
    "ascii": " .:-=+*#%@",
    "fine": " .'`^\",:;Il!i~+_-?][}{1)(|/tjfrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "soft": " .·:;+=xX$&",
    "blocks": " ░▒▓█",
    "dots": " ·∙•●",
    "braille": " ⠁⠃⠇⡇⡏⡟⡿⣿",
    "lines": " .-~=≡",
    "binary": " 01",
    "stars": " .·+*",
}
DEFAULT_RAMP = "ascii"


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    """Blend two RGB tuples."""
    return (c1[0] + (c2[0] - c1[0]) * t, c1[1] + (c2[1] - c1[1]) * t, c1[2] + (c2[2] - c1[2]) * t)


def scale(c, k):
    return (c[0] * k, c[1] * k, c[2] * k)


def hsv(h, s, v):
    """HSV (h in turns 0..1) -> RGB 0..255."""
    h = (h % 1.0) * 6.0
    i = int(h)
    f = h - i
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
    return (r * 255, g * 255, b * 255)


def gradient(stops, t):
    """Sample a list of RGB stops at t in 0..1."""
    t = clamp(t)
    n = len(stops) - 1
    if n <= 0:
        return stops[0]
    x = t * n
    i = min(int(x), n - 1)
    return mix(stops[i], stops[i + 1], x - i)


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0)) if e1 != e0 else 0.0
    return t * t * (3 - 2 * t)


def _q(c):
    """Quantize a float RGB to an int tuple (step 4) so color caches stay small."""
    r, g, b = c
    r = 0 if r < 0 else 252 if r > 252 else int(r) & ~3
    g = 0 if g < 0 else 252 if g > 252 else int(g) & ~3
    b = 0 if b < 0 else 252 if b > 252 else int(b) & ~3
    return (r, g, b)


class Canvas:
    """A grid of (char, color) cells plus a per-cell intensity layer for compositing."""

    def __init__(self, w: int, h: int, ramp: str = RAMPS[DEFAULT_RAMP]):
        self.w, self.h = max(1, w), max(1, h)
        self.n = self.w * self.h
        self.ramp = ramp
        self.clear()

    def clear(self):
        self.ch = [" "] * self.n
        self.fg = [None] * self.n
        self.lv = [0.0] * self.n
        self.bc = [None] * self.n  # undimmed color, used by shade(mode="add")

    def put(self, x, y, ch, rgb, level=1.0):
        """Write one character (always overwrites)."""
        x = int(x)
        y = int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            i = y * self.w + x
            self.ch[i] = ch
            self.fg[i] = _q(rgb)
            self.lv[i] = level
            self.bc[i] = rgb

    def text(self, x, y, s, rgb):
        for k, c in enumerate(s):
            if c != " ":
                self.put(x + k, y, c, rgb)

    def shade(self, x, y, v, rgb, mode="max", dim=True):
        """Draw intensity v (0..1) at a cell using the active ramp.

        mode: 'max' keeps the brighter of old/new, 'over' always replaces,
              'add' accumulates light (colors blend by contribution).
        dim:  scale the color by intensity so faint cells are darker too.
        """
        x = int(x)
        y = int(y)
        if not (0 <= x < self.w and 0 <= y < self.h) or v <= 0.0:
            return
        i = y * self.w + x
        old = self.lv[i]
        if mode == "max":
            if v <= old:
                return
        elif mode == "add":
            base = self.bc[i]
            if old > 0 and base is not None:
                tot = old + v
                rgb = mix(base, rgb, v / tot)
                v = tot
        if v > 1.0:
            v = 1.0
        ramp = self.ramp
        idx = int(v * (len(ramp) - 1) + 0.5)
        self.lv[i] = v
        self.bc[i] = rgb
        if idx <= 0:
            if mode == "over":
                self.ch[i] = " "
            return
        self.ch[i] = ramp[idx]
        self.fg[i] = _q(scale(rgb, 0.3 + 0.7 * v) if dim else rgb)

    def glyph(self, v):
        """The ramp character for an intensity (for scenes that want to pick chars themselves)."""
        ramp = self.ramp
        return ramp[max(0, min(len(ramp) - 1, int(v * (len(ramp) - 1) + 0.5)))]

    def line(self, x0, y0, x1, y1, v, rgb, mode="max"):
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for k in range(steps + 1):
            t = k / steps
            self.shade(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, v, rgb, mode)

    def fill_box(self, x0, y0, x1, y1, ch=" "):
        for y in range(max(0, int(y0)), min(self.h, int(y1))):
            for x in range(max(0, int(x0)), min(self.w, int(x1))):
                i = y * self.w + x
                self.ch[i] = ch
                self.fg[i] = None
                self.lv[i] = 0.0


# --------------------------------------------------------------------------- color pipeline

THEMES = {
    # kind 'native' leaves colors alone; 'gradient' maps luminance onto stops;
    # 'transform' adjusts saturation/brightness/tint.
    "natural": {"kind": "native", "blurb": "each scene's own colors"},
    "neon": {"kind": "transform", "sat": 1.7, "bright": 1.15, "blurb": "punchy, oversaturated"},
    "pastel": {"kind": "transform", "sat": 0.55, "tint": (255, 245, 250), "tint_k": 0.35, "bright": 1.1,
               "blurb": "soft and milky"},
    "faded": {"kind": "transform", "sat": 0.35, "bright": 0.85, "blurb": "washed-out film"},
    "sunset": {"kind": "gradient", "stops": [(40, 10, 60), (150, 30, 90), (240, 90, 60), (255, 180, 80), (255, 240, 190)]},
    "ocean": {"kind": "gradient", "stops": [(5, 20, 50), (10, 70, 130), (20, 150, 190), (110, 220, 230), (220, 255, 255)]},
    "forest": {"kind": "gradient", "stops": [(10, 30, 15), (30, 80, 40), (80, 150, 60), (170, 210, 100), (240, 250, 200)]},
    "ember": {"kind": "gradient", "stops": [(30, 0, 0), (120, 15, 0), (220, 70, 0), (255, 160, 30), (255, 245, 200)]},
    "ice": {"kind": "gradient", "stops": [(10, 20, 40), (50, 90, 160), (120, 170, 230), (200, 230, 255), (255, 255, 255)]},
    "vapor": {"kind": "gradient", "stops": [(30, 10, 70), (120, 30, 160), (255, 80, 200), (80, 220, 255), (240, 250, 255)]},
    "aurora": {"kind": "gradient", "stops": [(10, 20, 40), (20, 120, 100), (60, 230, 150), (170, 120, 255), (255, 230, 255)]},
    "candy": {"kind": "gradient", "stops": [(60, 20, 70), (255, 90, 160), (255, 190, 90), (130, 240, 200), (255, 255, 255)]},
    "matrix": {"kind": "gradient", "stops": [(0, 25, 5), (0, 110, 30), (40, 220, 80), (180, 255, 180)]},
    "amber": {"kind": "gradient", "stops": [(30, 15, 0), (140, 70, 0), (255, 160, 20), (255, 225, 150)]},
    "mono": {"kind": "gradient", "stops": [(40, 40, 40), (140, 140, 140), (250, 250, 250)]},
    "nord": {"kind": "gradient", "stops": [(46, 52, 64), (94, 129, 172), (136, 192, 208), (163, 190, 140), (236, 239, 244)]},
    "dracula": {"kind": "gradient", "stops": [(40, 42, 54), (98, 114, 164), (189, 147, 249), (255, 121, 198), (248, 248, 242)]},
    "gruvbox": {"kind": "gradient", "stops": [(40, 40, 40), (204, 36, 29), (215, 153, 33), (152, 151, 26), (235, 219, 178)]},
    "catppuccin": {"kind": "gradient", "stops": [(30, 30, 46), (137, 180, 250), (203, 166, 247), (245, 194, 231), (249, 226, 175)]},
    "rainbow": {"kind": "rainbow", "blurb": "hue follows brightness"},
    # selective color: everything silver-grey except one accent hue ("ASCII but make it cool")
    "noir": {"kind": "selective", "hue": 0.0, "blurb": "black and white, only reds survive"},
    "noir-gold": {"kind": "selective", "hue": 0.11, "blurb": "black and white, only golds survive"},
    "noir-cyan": {"kind": "selective", "hue": 0.52, "blurb": "black and white, only cyans survive"},
    "noir-rose": {"kind": "selective", "hue": 0.92, "blurb": "black and white, only pinks survive"},
}
for _k, _t in THEMES.items():
    _t.setdefault("blurb", "gradient palette" if _t["kind"] == "gradient" else "")


def _lum(c):
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0


def _rgb_to_hsv(c):
    r, g, b = c[0] / 255.0, c[1] / 255.0, c[2] / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        h = 0.0
    elif mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h / 6.0, (0.0 if mx == 0 else d / mx), mx


class ColorFX:
    """Global color transform: theme + hue shift + saturation + brightness."""

    def __init__(self, theme="natural", hue=0.0, sat=1.0, bright=1.0):
        self.set(theme, hue, sat, bright)

    def set(self, theme=None, hue=None, sat=None, bright=None):
        if theme is not None:
            if theme not in THEMES:
                raise ValueError(f"unknown theme {theme!r}")
            self.theme = theme
        if hue is not None:
            self.hue = hue
        if sat is not None:
            self.sat = sat
        if bright is not None:
            self.bright = bright
        self.identity = self.theme == "natural" and self.hue % 360 == 0 and self.sat == 1 and self.bright == 1
        self.cache = {}

    def apply(self, c):
        if self.identity:
            return c
        r = self.cache.get(c)
        if r is not None:
            return r
        th = THEMES[self.theme]
        kind = th["kind"]
        out = c
        if kind == "gradient":
            # Boost luminance a little so dim scenes still use the bright end of the palette.
            out = gradient(th["stops"], clamp(_lum(c) ** 0.8 * 1.15))
        elif kind == "rainbow":
            h, s, v = _rgb_to_hsv(c)
            out = hsv(_lum(c) * 0.85 + 0.55, 0.75, max(v, 0.15))
        elif kind == "selective":
            h, s, v = _rgb_to_hsv(c)
            dh = abs(((h - th["hue"] + 0.5) % 1.0) - 0.5)        # distance around the color wheel
            keep = clamp(1 - (dh - 0.035) / 0.04) * clamp((s - 0.2) / 0.25)
            lum = _lum(c) ** 0.9
            silver = (lum * 232, lum * 238, lum * 250)              # a cool, slightly blue grey
            accent = hsv(h, min(1.0, s * 1.25), min(1.0, v * 1.1))
            out = mix(silver, accent, keep)
        sat = self.sat * th.get("sat", 1.0)
        bright = self.bright * th.get("bright", 1.0)
        if self.hue % 360 or sat != 1.0:
            h, s, v = _rgb_to_hsv(out)
            out = hsv(h + self.hue / 360.0, clamp(s * sat), v)
        if "tint" in th:
            out = mix(out, th["tint"], th["tint_k"] * clamp(_lum(out) * 1.5))
        if bright != 1.0:
            out = scale(out, bright)
        out = (int(clamp(out[0], 0, 255)), int(clamp(out[1], 0, 255)), int(clamp(out[2], 0, 255)))
        self.cache[c] = out
        return out


def _to256(c):
    r, g, b = c
    if abs(r - g) < 10 and abs(g - b) < 10:
        if r < 8:
            return 16
        if r > 238:
            return 231
        return 232 + round((r - 8) / 247 * 24)
    q = lambda x: 0 if x < 48 else 1 if x < 115 else (x - 35) // 40
    return 16 + 36 * q(r) + 6 * q(g) + q(b)


def detect_color_mode():
    if os.environ.get("NO_COLOR"):
        return "mono"
    ct = os.environ.get("COLORTERM", "").lower()
    if "truecolor" in ct or "24bit" in ct:
        return "truecolor"
    if os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM") in ("vscode", "iTerm.app", "WezTerm", "ghostty"):
        return "truecolor"
    if sys.platform == "win32":
        return "truecolor"  # Windows Terminal & modern conhost both handle 24-bit
    term = os.environ.get("TERM", "")
    if "256" in term:
        return "256"
    if term in ("xterm-kitty", "alacritty", "foot", "wezterm"):
        return "truecolor"
    return "256"


class Renderer:
    """Turns a Canvas into ANSI escape sequences, sending only the cells that changed."""

    def __init__(self, write, color_mode="truecolor", fx: ColorFX | None = None):
        self.write = write
        self.mode = color_mode
        self.fx = fx or ColorFX()
        self.sgr_cache = {}
        self.reset()

    def reset(self):
        self.pch = None
        self.pfg = None

    def set_fx(self, fx):
        self.fx = fx
        self.sgr_cache = {}
        self.reset()

    def sgr(self, c):
        s = self.sgr_cache.get(c)
        if s is None:
            r, g, b = self.fx.apply(c)
            if self.mode == "truecolor":
                s = f"\x1b[38;2;{r};{g};{b}m"
            elif self.mode == "256":
                s = f"\x1b[38;5;{_to256((r, g, b))}m"
            else:
                s = "\x1b[1m" if _lum((r, g, b)) > 0.6 else "\x1b[22m"
            self.sgr_cache[c] = s
        return s

    def render(self, cv: Canvas):
        ch, fg, w = cv.ch, cv.fg, cv.w
        pch, pfg = self.pch, self.pfg
        full = pch is None or len(pch) != cv.n
        out = []
        last = None
        cursor = -1
        sgr = self.sgr
        n = cv.n - 1  # never write the bottom-right cell: some terminals scroll
        for i in range(n):
            c = ch[i]
            f = fg[i]
            if not full and c == pch[i] and (c == " " or f == pfg[i]):
                continue
            if cursor != i:
                y, x = divmod(i, w)
                out.append(f"\x1b[{y + 1};{x + 1}H")
            if c != " " and f is not None:
                s = sgr(f)
                if s != last:
                    out.append(s)
                    last = s
            out.append(c)
            cursor = i + 1 if (i + 1) % w else -1
        if out:
            out.append("\x1b[0m")
            self.write("".join(out))
        self.pch = list(ch)
        self.pfg = list(fg)


# --------------------------------------------------------------------------- terminal + keys

MOUSE_ON = "\x1b[?1000h\x1b[?1003h\x1b[?1006h"   # clicks + motion, SGR coordinates
MOUSE_OFF = "\x1b[?1006l\x1b[?1003l\x1b[?1000l"


class Terminal:
    def __init__(self, alt_screen=True, mouse=True):
        self.alt = alt_screen
        self.mouse = mouse
        self.out = sys.stdout
        self._unix_old = None
        self._win_in = None

    def enter(self):
        if sys.platform == "win32":
            try:
                import ctypes

                k = ctypes.windll.kernel32
                k.SetConsoleOutputCP(65001)
                h = k.GetStdHandle(-11)
                mode = ctypes.c_uint32()
                if k.GetConsoleMode(h, ctypes.byref(mode)):
                    k.SetConsoleMode(h, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                if self.mouse:
                    # mouse reports arrive as VT text: ENABLE_VIRTUAL_TERMINAL_INPUT, no quick-edit
                    hin = k.GetStdHandle(-10)
                    imode = ctypes.c_uint32()
                    if k.GetConsoleMode(hin, ctypes.byref(imode)):
                        self._win_in = (hin, imode.value)
                        k.SetConsoleMode(hin, (imode.value | 0x0200 | 0x0080) & ~0x0040)
            except Exception:
                pass
        try:
            self.out.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        if sys.platform != "win32" and sys.stdin.isatty():
            import termios
            import tty

            fd = sys.stdin.fileno()
            self._unix_old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        seq = ("\x1b[?1049h" if self.alt else "") + "\x1b[?25l\x1b[2J\x1b[H" + (MOUSE_ON if self.mouse else "")
        self.write(seq)

    def exit(self):
        self.write((MOUSE_OFF if self.mouse else "") + "\x1b[0m\x1b[?25h"
                   + ("\x1b[?1049l" if self.alt else "\x1b[2J\x1b[H"))
        if self._win_in is not None:
            try:
                import ctypes

                ctypes.windll.kernel32.SetConsoleMode(self._win_in[0], self._win_in[1])
            except Exception:
                pass
        if self._unix_old is not None:
            import termios

            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._unix_old)

    def write(self, s):
        self.out.write(s)
        self.out.flush()

    def clear(self):
        self.write("\x1b[0m\x1b[2J")

    @staticmethod
    def size():
        s = shutil.get_terminal_size((100, 32))
        return s.columns, s.lines


_ESC_KEYS = {"[A": "up", "[B": "down", "[C": "right", "[D": "left", "OA": "up", "OB": "down", "OC": "right", "OD": "left"}
_WIN_KEYS = {"H": "up", "P": "down", "M": "right", "K": "left"}


def parse_input(data):
    """Turn raw terminal input into events.

    Returns key names ("q", "up", "esc"...) and mouse tuples: ("click", x, y) for a left-button
    press and ("move", x, y) for motion, in 0-based cells.
    """
    events = []
    i = 0
    n = len(data)
    while i < n:
        c = data[i]
        if c == "\x1b":
            if data.startswith("[<", i + 1):  # SGR mouse report: ESC [ < b ; x ; y (M|m)
                j = i + 3
                while j < n and data[j] not in "Mm":
                    j += 1
                if j < n:
                    try:
                        b, x, y = (int(v) for v in data[i + 3:j].split(";"))
                        if data[j] == "M" and b & 32:
                            events.append(("move", x - 1, y - 1))
                        elif data[j] == "M" and b & 3 == 0 and b < 64:
                            events.append(("click", x - 1, y - 1))
                    except ValueError:
                        pass
                    i = j + 1
                    continue
            seq = data[i + 1:i + 3]
            if seq in _ESC_KEYS:
                events.append(_ESC_KEYS[seq])
                i += 3
                continue
            events.append("esc")
        else:
            events.append(c)
        i += 1
    return events


class Keys:
    """Non-blocking keyboard (and mouse) reader. read() returns key names and mouse tuples."""

    def read(self):
        if sys.platform == "win32":
            try:
                import msvcrt
            except ImportError:
                return []
            keys = []
            data = ""
            while msvcrt.kbhit():
                c = msvcrt.getwch()
                if c in ("\x00", "\xe0"):  # classic console arrow keys
                    keys.append(_WIN_KEYS.get(msvcrt.getwch(), ""))
                elif c == "\x03":
                    raise KeyboardInterrupt
                else:
                    data += c
            return keys + parse_input(data)
        if not sys.stdin.isatty():
            return []
        import select

        fd = sys.stdin.fileno()
        data = ""
        while select.select([fd], [], [], 0)[0]:
            chunk = os.read(fd, 256)
            if not chunk:
                break
            data += chunk.decode("utf-8", "ignore")
        return parse_input(data)


# --------------------------------------------------------------------------- scenes

class Context:
    """Shared run settings handed to every scene."""

    def __init__(self, seed=None, density=1.0, options=None):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.density = density
        self.options = options or {}


class Scene:
    """Base class. Subclasses set the class attributes and implement setup/update/draw.

    Coordinates are terminal cells: x in [0, w), y in [0, h), y grows downward.
    Use ASPECT when you need round shapes (dy_cells * ASPECT ~ dx_cells).
    """

    name = ""          # CLI id, e.g. "jellyfish"
    title = ""         # pretty name
    blurb = ""         # one-liner shown in --list and on the title card
    tags: tuple = ()   # e.g. ("nature", "ocean")
    options: dict = {}  # {"count": (default, "help text")}; read with self.opt("count")
    interactions = ""   # what clicking / pointing does, e.g. "click to drop food"; "" = nothing

    def __init__(self, ctx: Context, w: int, h: int):
        self.ctx = ctx
        self.rng = random.Random(ctx.rng.random())
        self.w, self.h = w, h
        self.t = 0.0
        self.pointer = None  # (x, y) in cells while the mouse is over the scene, else None
        self.setup()

    # -- hooks -------------------------------------------------------------
    def setup(self):
        """(Re)build state for the current size. Called on start and on resize by default."""

    def resize(self, w, h):
        self.w, self.h = w, h
        self.setup()

    def update(self, dt):
        self.t += dt

    def draw(self, cv: Canvas):
        raise NotImplementedError

    def on_click(self, x, y):
        """The user clicked cell (x, y) (floats, in cells). Override to react."""

    def close(self):
        """Release anything the scene holds (e.g. a helper process). Called when it's replaced."""

    # -- helpers -----------------------------------------------------------
    @property
    def density(self):
        return self.ctx.density

    def opt(self, key, default=None):
        """Scene option from -o key=value, coerced to the type of the declared default."""
        decl = self.options.get(key)
        if default is None and decl is not None:
            default = decl[0]
        raw = self.ctx.options.get(key)
        if raw is None:
            return default
        if isinstance(default, bool):
            return str(raw).lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            try:
                return int(float(raw))
            except ValueError:
                return default
        if isinstance(default, float):
            try:
                return float(raw)
            except ValueError:
                return default
        return raw

    def count(self, base, lo=1):
        """Scale a population by area and --density."""
        area = (self.w * self.h) / (100 * 30)
        return max(lo, int(round(base * area * self.ctx.density)))


def noise1(x, seed=0):
    """Cheap smooth 1D value noise in [-1, 1]."""
    i = math.floor(x)
    f = x - i
    u = f * f * (3 - 2 * f)

    def h(n):
        n = (n * 374761393 + seed * 668265263) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return (n & 0xFFFF) / 32767.5 - 1.0

    return h(i) * (1 - u) + h(i + 1) * u


def noise2(x, y, seed=0):
    """Cheap smooth 2D value noise in [-1, 1]."""
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u = xf * xf * (3 - 2 * xf)
    v = yf * yf * (3 - 2 * yf)

    def h(a, b):
        n = (a * 374761393 + b * 668265263 + seed * 2147483647) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return (n & 0xFFFF) / 32767.5 - 1.0

    a = h(xi, yi) + (h(xi + 1, yi) - h(xi, yi)) * u
    b = h(xi, yi + 1) + (h(xi + 1, yi + 1) - h(xi, yi + 1)) * u
    return a + (b - a) * v


def fbm(x, y, octaves=3, seed=0):
    tot, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        tot += noise2(x * freq, y * freq, seed + o) * amp
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return tot / norm
