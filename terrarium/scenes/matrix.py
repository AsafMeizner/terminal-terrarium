"""Digital rain: columns of falling glyphs with white-hot heads and fading trails."""
import math

from ..engine import Scene, clamp, hsv, mix

GLYPHS = ("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
          "abcdefghijkmnopqrstuvwxyz"
          "$+-*/=%\"'#&_(),.;:?!\\|{}<>[]^~@")

# glyph mixes a run can be built from
GLYPH_SETS = {
    "classic": GLYPHS,
    "digits": "0123456789" * 3 + "+-*=<>:.",
    "binary": "01" * 8 + "10",
    "hex": "0123456789ABCDEF",
    "letters": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz",
    "symbols": "$+-*/=%\"'#&_(),.;:?!\\|{}<>[]^~@",
    "circuit": "01" * 4 + "|-+=<>[]{}/\\_" * 2,
}
ACCENTS = [((150, 120, 0), (255, 220, 80), (255, 250, 220)),     # gold
           ((0, 110, 160), (80, 230, 255), (225, 250, 255)),     # ice
           ((150, 20, 100), (255, 100, 200), (255, 230, 245)),   # magenta
           ((130, 130, 140), (230, 230, 240), (255, 255, 255))]  # silver

# (trail color, bright trail, head) per color scheme
COLORS = {
    "green": ((0, 150, 40), (90, 255, 120), (225, 255, 230)),
    "cyan": ((0, 110, 160), (80, 230, 255), (225, 250, 255)),
    "amber": ((150, 70, 0), (255, 180, 50), (255, 245, 220)),
    "red": ((150, 10, 20), (255, 80, 80), (255, 225, 225)),
    "purple": ((90, 30, 170), (190, 120, 255), (245, 230, 255)),
    "pink": ((160, 20, 110), (255, 110, 200), (255, 230, 245)),
}


def _q(c):
    r, g, b = c
    r = 0 if r < 0 else 252 if r > 252 else int(r) & ~3
    g = 0 if g < 0 else 252 if g > 252 else int(g) & ~3
    b = 0 if b < 0 else 252 if b > 252 else int(b) & ~3
    return (r, g, b)


class Drop:
    __slots__ = ("x", "y", "speed", "length", "depth", "tick", "hue", "accent")

    def __init__(self, rng, x, h, depth, start_above=True):
        self.x = x
        self.depth = depth                                   # 0 far .. 1 near
        self.length = rng.uniform(0.25, 0.9) * h * (0.6 + 0.6 * depth)
        self.speed = rng.uniform(7, 13) * (0.45 + 0.9 * depth)   # cells per second
        self.y = -rng.uniform(0, h * 1.2) if start_above else rng.uniform(-h * 0.2, h * 1.2)
        self.tick = 0.0
        self.hue = rng.random()
        self.accent = False


class Matrix(Scene):
    name = "matrix"
    title = "Digital Rain"
    blurb = "falling columns of glyphs with white-hot heads and green trails"
    tags = ("retro", "code", "dark")
    options = {
        "color": ("green", "green, cyan, amber, red, purple, pink or rainbow"),
        "density": (1.0, "how many streams per column"),
        "glyphs": ("random", "classic, digits, binary, hex, letters, symbols, circuit, mixed or random"),
    }

    def _choose_style(self):
        rng = self.rng
        gs = self.opt("glyphs")
        if gs == "mixed" or (gs not in GLYPH_SETS and rng.random() < 0.35):
            # a blend of two or three sets
            names = rng.sample(sorted(GLYPH_SETS), rng.randint(2, 3))
            glyphs = "".join(GLYPH_SETS[n] for n in names)
        else:
            if gs not in GLYPH_SETS:
                gs = rng.choice(("classic", "classic", "classic", "digits", "binary", "hex", "letters",
                                 "symbols", "circuit"))
            glyphs = GLYPH_SETS[gs]
        self.style = {
            "glyphs": glyphs,
            "speed": rng.uniform(0.7, 1.4),          # overall pace
            "spread": rng.uniform(0.15, 0.6),         # how different stream speeds are
            "length": rng.uniform(0.7, 1.3),
            "accent_p": rng.choice((0.0, 0.0, 0.02, 0.04, 0.07)),
            "accent": rng.choice(ACCENTS),
        }

    def _roll_drop(self, d):
        """Speed, length and accent for a (re)spawned stream, from this run's distribution."""
        rng, st, h = self.rng, self.style, self.h
        sp = st["speed"] * (1 + rng.uniform(-st["spread"], st["spread"]))
        d.speed = 10.0 * sp * (0.45 + 0.9 * d.depth)
        d.length = rng.uniform(0.25, 0.9) * h * (0.6 + 0.6 * d.depth) * st["length"]
        d.accent = rng.random() < st["accent_p"]

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        if not hasattr(self, "style"):
            self._choose_style()
        GLYPHS = self.glyphs = self.style["glyphs"]
        self.glyph = [[rng.choice(GLYPHS) for _ in range(w)] for _ in range(h)]
        dens = max(0.05, self.opt("density")) * self.density
        n = max(4, int(w * 0.85 * dens))
        self.drops = []
        for _ in range(n):
            x = rng.randrange(w)
            d = Drop(rng, x, h, rng.random() ** 0.8, start_above=False)
            self._roll_drop(d)
            self.drops.append(d)
        self.drops.sort(key=lambda d: d.depth)
        self.mutate_acc = 0.0
        scheme = self.opt("color")
        self.rainbow = scheme == "rainbow"
        self.scheme = COLORS.get(scheme, COLORS["green"])
        self._cache = {}

    def update(self, dt):
        super().update(dt)
        rng = self.rng
        h, w = self.h, self.w
        GLYPHS = self.glyphs
        for d in self.drops:
            old = int(d.y)
            d.y += d.speed * dt
            if int(d.y) != old and 0 <= int(d.y) < h:
                # a fresh glyph under the head each time it steps
                self.glyph[int(d.y)][d.x] = rng.choice(GLYPHS)
            if d.y - d.length > h:
                d.x = rng.randrange(w)
                d.depth = rng.random() ** 0.8
                self._roll_drop(d)
                d.y = -rng.uniform(0, h * 0.5)
                d.hue = rng.random()
        # random glyph mutations all over the screen
        self.mutate_acc += dt * w * h * 0.02
        g = self.glyph
        while self.mutate_acc >= 1:
            self.mutate_acc -= 1
            g[rng.randrange(h)][rng.randrange(w)] = rng.choice(GLYPHS)

    def _color(self, f, depth, hue, accent=False):
        """Trail color for position f (0 head .. 1 tail end); returns (rgb, level)."""
        key = (int(f * 24), int(depth * 6), int(hue * 12) if self.rainbow else 0, accent)
        r = self._cache.get(key)
        if r is None:
            ff = key[0] / 24
            dd = key[1] / 6
            if accent:
                c0, c1, head = self.style["accent"]
            elif self.rainbow:
                c0 = hsv(key[2] / 12, 0.9, 0.55)
                c1 = hsv(key[2] / 12, 0.6, 1.0)
                head = mix(c1, (255, 255, 255), 0.75)
            else:
                c0, c1, head = self.scheme
            fade = (1 - ff) ** 1.6
            if ff < 0.04:
                c = head
                v = 1.0
            else:
                c = mix(c0, c1, clamp((1 - ff) ** 2.2 * 1.4))
                if ff < 0.14:
                    c = mix(c, head, (0.14 - ff) / 0.14 * 0.55)
                v = 0.12 + 0.88 * fade
            k = (0.35 + 0.65 * dd) * (0.25 + 0.75 * v)
            r = (_q((c[0] * k, c[1] * k, c[2] * k)), v * (0.45 + 0.55 * dd))
            self._cache[key] = r
        return r

    def draw(self, cv):
        h = min(self.h, cv.h)
        w = min(self.w, cv.w)
        g = self.glyph
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        cw = cv.w
        t = self.t
        color = self._color
        GLYPHS = self.glyphs
        for d in self.drops:
            x = d.x
            if x >= w:
                continue
            head = int(d.y)
            L = max(2.0, d.length)
            y0 = max(0, int(d.y - L))
            y1 = min(h - 1, head)
            for y in range(y1, y0 - 1, -1):
                f = (d.y - y) / L
                if f > 1:
                    break
                c, v = color(f, d.depth, d.hue, d.accent)
                i = y * cw + x
                if v <= lv[i]:
                    continue
                # head glyph flickers fast; the rest holds still like stamped type
                if y == head:
                    gl = GLYPHS[int(t * 30 + x * 7) % len(GLYPHS)]
                else:
                    gl = g[y][x]
                    # rare glints: a trail glyph flashes bright for a moment
                    if ((x * 73856093) ^ (y * 19349663) ^ (int(t * 6) * 83492791)) % 97 == 0:
                        c, v = color(0.06, d.depth, d.hue, d.accent)
                ch[i] = gl
                fg[i] = c
                lv[i] = v
            # soft glow just below the head of near streams
            if d.depth > 0.6 and 0 <= head + 1 < h and d.y - head > 0.5:
                i = (head + 1) * cw + x
                if lv[i] < 0.2:
                    c0, c1, hc = self.scheme
                    ch[i] = g[head + 1][x]
                    fg[i] = _q(mix((0, 0, 0), c1, 0.35 * (d.y - head)))
                    lv[i] = 0.2
