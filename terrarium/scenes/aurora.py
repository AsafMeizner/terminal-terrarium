"""Northern lights rippling over dark mountains and a still lake."""
import math

from ..engine import RAMPS, Canvas, Scene, gradient, hsv, mix, noise1, scale, smoothstep

# With the default charset, use glyphs with a vertical grain so the curtains read as rays.
VERTICAL = " .':;!|lI#"

# Color stops from the lower edge of a curtain (u=0) up to its fading top (u=1), plus the
# fringe color that glows just below the lower edge.
PALETTES = {
    "classic": ([(200, 255, 220), (70, 255, 150), (40, 230, 140), (40, 180, 170), (100, 110, 240), (170, 80, 230),
                 (220, 70, 200)],
                (255, 80, 170)),
    "pink": ([(255, 225, 240), (255, 120, 200), (235, 90, 225), (175, 80, 240), (115, 80, 245), (80, 60, 210)],
             (255, 150, 110)),
    "blue": ([(220, 245, 255), (100, 225, 255), (60, 165, 255), (70, 115, 250), (130, 80, 240), (160, 60, 210)],
             (110, 255, 200)),
    "rainbow": ([(255, 255, 255)], (255, 255, 255)),  # hue computed per column
}
LUT_N = 32


class Curtain:
    def __init__(self, rng, k, n, sky_h, w):
        f = (k + rng.uniform(0.25, 0.75)) / n
        self.base = sky_h * (0.34 + 0.22 * f)                 # lower edge, cells from top
        self.height = sky_h * rng.uniform(0.35, 0.55)          # how far the rays reach up
        self.amp = sky_h * rng.uniform(0.14, 0.24)
        self.tilt = sky_h * rng.uniform(-0.25, 0.25)           # sweeps diagonally across the sky
        self.k1 = math.tau / (w * rng.uniform(0.5, 1.0) + 1)
        self.w1 = rng.uniform(0.06, 0.13) * rng.choice((-1, 1))
        self.p = rng.uniform(0, math.tau)
        self.amp2 = sky_h * rng.uniform(0.04, 0.07)
        self.k2 = rng.uniform(0.03, 0.06)
        self.w2 = rng.uniform(0.10, 0.18)
        self.seed = rng.randrange(1, 10_000)
        self.bright = rng.uniform(0.8, 1.0)
        self.hue = rng.random()
        self.drift = rng.uniform(0.25, 0.5) * rng.choice((-1, 1))  # rays slide along the curtain


class Aurora(Scene):
    name = "aurora"
    title = "Aurora"
    blurb = "northern lights rippling over dark mountains and a still lake"
    tags = ("night", "nature", "calm", "sky")
    options = {
        "intensity": (1.0, "brightness of the lights (0.3 .. 2)"),
        "colors": ("random", "random, classic, pink, blue or rainbow"),
        "reflection": (True, "mirror the sky in a lake"),
        "curtains": (0, "number of curtains (0 = auto)"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.refl = bool(self.opt("reflection")) and h >= 14
        self.hz = int(h * rng.uniform(0.66, 0.76)) if self.refl else h
        hz = self.hz
        # three mountain ranges, far to near: each ridge is the lower envelope of jagged peaks
        self.ranges = []
        # generative grammar for the ranges: how many, how tall, how jagged, what tint
        nr = rng.choice((2, 3, 3, 4))
        tint = rng.choice(((40, 46, 88), (36, 52, 80), (52, 42, 86), (34, 46, 64)))
        lift = rng.uniform(-0.12, 0.08)                    # taller or flatter skylines overall
        jag = rng.uniform(0.5, 1.15)                       # slope: gentle hills .. sharp peaks
        specs = []
        for k in range(nr):
            f = k / max(1, nr - 1)
            lo = 0.5 + 0.36 * f + lift * (1 - f)
            specs.append((lo, min(0.98, lo + rng.uniform(0.12, 0.26)), jag * (1.0 - 0.45 * f),
                          scale(tint, 1.0 - 0.62 * f), 0.30 - 0.15 * f))
        if not self.refl:
            specs = [(lo * 0.85, hi * 0.85, sl, c, v) for lo, hi, sl, c, v in specs]
        spacing = rng.uniform(12, 28)
        for lo, hi, slope, col, v in specs:
            seed = rng.randrange(1, 10_000)
            peaks = []
            x = rng.uniform(-12, 0)
            while x < w + 12:
                peaks.append((x, hz * rng.uniform(lo, hi), slope * rng.uniform(0.55, 1.0)))
                x += rng.uniform(spacing * 0.6, spacing * 1.4) * (1.25 - slope * 0.5) * max(1.0, w / 110) ** 0.5
            ridge = []
            for x in range(w + 1):
                y = min(py + abs(x - px) * sl for px, py, sl in peaks)
                y += 0.6 * noise1(x * 0.35, seed)  # crags
                ridge.append(min(float(hz), y))
            self.ranges.append((ridge, col, v))
        self.sky_top = [max(0, min(int(r[0][x]) for r in self.ranges)) for x in range(w)]
        n = self.opt("curtains") or max(1, rng.choice((1, 2, 2, 3, 3, 4)) - (1 if w < 80 else 0))
        self.curtains = [Curtain(rng, k, n, hz, w) for k in range(n)]
        ns = int(w * hz / 32 * self.density)
        stars = [(rng.randrange(w), rng.randrange(max(1, hz)), rng.uniform(0.2, 1.0) ** 1.6,
                  rng.uniform(0, math.tau), rng.uniform(0.6, 2.4)) for _ in range(ns)]
        self.stars = [s for s in stars if s[1] < self.sky_top[s[0]] - 1]
        name = self.opt("colors")
        if name not in PALETTES:
            name = rng.choices(("classic", "pink", "blue", "rainbow"), (5, 2, 2, 1))[0]
        self.colors = name
        stops, fringe = PALETTES.get(name, PALETTES["classic"])
        self.rainbow = name == "rainbow"
        self.lut = [gradient(stops, i / (LUT_N - 1)) for i in range(LUT_N)]
        self.fringe = fringe
        self.hue_lut = [hsv(0.25 + i / 64 * 0.75, 0.7, 1.0) for i in range(64)]  # green -> blue -> pink
        self._bgkey = None
        # lake rows sample the sky with a stretch so the lights show up in a shallow lake
        self.mk = max(1.0, min(2.2, (hz * 0.75) / max(1, h - hz))) if self.refl else 1.0

    # ------------------------------------------------------------------ static layer
    def paint_static(self, b):
        w, h, hz = self.w, self.h, self.hz
        # very faint sky glow near the horizon
        for y in range(hz):
            g = (y / max(1, hz)) ** 2.5
            for x in range(w):
                if (x * 7 + y * 13) % 4 == 0 and g > 0.2:
                    b.shade(x, y, 0.06 + 0.08 * g, (40, 60, 120))
        for k, (ridge, col, v) in enumerate(self.ranges):
            f = k / max(1, len(self.ranges) - 1)
            rim = mix(col, (190, 210, 250), 0.6 - 0.3 * f)
            for x in range(w):
                ya, yb = ridge[x], ridge[x + 1]
                top = min(ya, yb)
                y0 = max(0, int(top))
                for y in range(y0 + 1, hz):  # body: a dark, densely textured mass
                    d = y - top
                    snow = max(0.0, 1 - d / (1.5 + 2.4 * (1 - f))) * (1.0 - 0.8 * f)
                    tex = 0.5 + 0.5 * noise1(x * 0.9 + y * 2.3, 31 + k)
                    c = mix(col, (150, 170, 220), snow * tex * 0.8)
                    c = scale(c, 1.0 - 0.35 * min(1.0, d / 10))
                    b.shade(x, y, 0.25 + 0.3 * tex + 0.2 * snow * tex, c, mode="over", dim=False)
                # ridge outline, glyph from slope
                if yb < ya - 0.5:
                    ch = "/"
                elif yb > ya + 0.5:
                    ch = "\\"
                else:
                    ch = "_" if top % 1 > 0.5 else "-"
                if y0 < hz:
                    b.put(x, y0, ch, rim, level=0.6)
                for yy in range(int(top) + 1, min(hz, int(max(ya, yb)))):  # steep: stack glyphs
                    b.put(x, yy, ch, rim, level=0.6)
        if self.refl:
            flip = {"/": "\\", "\\": "/", "_": "-", "-": "_"}
            for y in range(hz, h):
                d = y - hz
                ym = int(hz - 1 - d * self.mk)
                fade = 0.55 - 0.3 * d / max(1, h - hz)
                for x in range(w):
                    if (x * 3 + y * 11) % 13 == 0:
                        b.put(x, y, "-", (25, 38, 75), level=0.05)
                    if ym < 0:
                        continue
                    i = ym * w + x
                    if ym >= self.sky_top[x] and b.fg[i] is not None and b.ch[i] != " ":
                        c = b.ch[i]
                        b.put(x, y, flip.get(c, c), scale(b.fg[i], fade), level=0.05)

    def background(self, cv):
        key = (cv.w, cv.h, cv.ramp)
        if self._bgkey != key:
            b = Canvas(cv.w, cv.h, cv.ramp)
            self.paint_static(b)
            self._bg = b
            self._bgkey = key
        b = self._bg
        cv.ch[:] = b.ch
        cv.fg[:] = b.fg
        cv.lv[:] = b.lv
        cv.bc[:] = b.bc

    # ------------------------------------------------------------------ lights
    def light(self):
        """Accumulate aurora light for every sky cell. Returns (value, r, g, b) flat lists."""
        w, hz, t = self.w, self.hz, self.t
        n = w * hz
        av = [0.0] * n
        ar = [0.0] * n
        ag = [0.0] * n
        ab = [0.0] * n
        inten = self.opt("intensity")
        lut, fringe, rainbow, hue_lut = self.lut, self.fringe, self.rainbow, self.hue_lut
        sky_top = self.sky_top
        exp = math.exp
        lmax = LUT_N - 1
        for c in self.curtains:
            s0 = c.seed
            prev = None
            sx = 60.0 / max(60, w)  # keep ray spacing similar at every width
            for x in range(w):
                xs = x * sx
                yb = (c.base + c.amp * math.sin(x * c.k1 + t * c.w1 + c.p) + c.tilt * (x / w - 0.5)
                      + c.amp2 * noise1(xs * c.k2 * 1.6 + t * c.w2, s0))
                slope = 0.0 if prev is None else abs(yb - prev)
                prev = yb
                env = smoothstep(-0.7, 0.35, noise1(xs * 0.035 + t * 0.03, s0 + 1))
                if env <= 0.01:
                    continue
                # thin bright rays (ridged noise) over a soft base, sliding along the curtain
                r1 = 1.0 - abs(noise1(x * 0.33 + t * c.drift, s0 + 2))
                r2 = 1.0 - abs(noise1(x * 0.71 - t * c.drift * 1.7, s0 + 3))
                ray = r1 ** 6 * 0.9 + r2 ** 8 * 0.5
                shim = 0.5 + 0.5 * noise1(x * 0.2 - t * 1.1, s0 + 5)
                fold = 1 + 1.2 * min(1.0, slope * 1.5)  # curtains seen edge-on look brighter
                s = env * (0.3 + 1.5 * ray) * (0.7 + 0.5 * shim) * fold * c.bright * inten
                edge = env * (0.3 + 0.8 * ray + 0.3 * shim) * fold * c.bright * inten
                H = c.height * (0.45 + 0.75 * r1 ** 3) * (0.8 + 0.3 * shim)
                if rainbow:
                    hb = int((x / w * 0.6 + c.hue + t * 0.01) * 64)
                ytop = max(0, int(yb - H))
                ybot = min(hz, int(yb) + 3, sky_top[x] + 1)
                invH = 1.0 / H
                for y in range(ytop, ybot):
                    dy = yb - y
                    if dy >= 0:
                        u = dy * invH
                        if u >= 1.0:
                            continue
                        v = s * exp(-1.9 * u) * (1.0 - u * u) * 0.7 + edge * exp(-dy * 0.9) * 0.8
                        if rainbow:
                            col = hue_lut[(hb + int(u * 20)) % 64]
                        else:
                            col = lut[int(u * lmax)]
                    else:
                        v = edge * 0.3 * exp(dy * 1.4)
                        col = fringe
                    i = y * w + x
                    av[i] += v
                    ar[i] += v * col[0]
                    ag[i] += v * col[1]
                    ab[i] += v * col[2]
        return av, ar, ag, ab

    def draw(self, cv):
        w, h, hz, t = self.w, self.h, self.hz, self.t
        if (cv.w, cv.h) != (w, h):
            return
        self.background(cv)
        av, ar, ag, ab = self.light()
        sky_top = self.sky_top
        ramp = VERTICAL if cv.ramp == RAMPS["ascii"] else cv.ramp
        rn = len(ramp) - 1
        put = cv.put
        exp = math.exp
        out_v = [0.0] * (w * hz)
        out_c = [None] * (w * hz)
        white = (255, 255, 255)
        for y in range(hz):
            row = y * w
            for x in range(sky_top[x] if False else 0, w):
                i = row + x
                a = av[i]
                if a < 0.07 or y >= sky_top[x]:
                    continue
                k = 1.0 / a
                col = (ar[i] * k, ag[i] * k, ab[i] * k)
                v = 1.0 - exp(-a * 2.0)
                if a > 0.9:
                    col = mix(col, white, min(0.55, (a - 0.9) * 0.35))
                out_v[i] = v
                out_c[i] = col
                gi = int(v * rn + 0.5)
                if gi > 0:
                    kk = 0.3 + 0.7 * v
                    put(x, y, ramp[gi], (col[0] * kk, col[1] * kk, col[2] * kk), level=v)
        # stars, hidden behind bright aurora
        for sx, sy, b, ph, rate in self.stars:
            v = b * (0.55 + 0.45 * math.sin(t * rate + ph))
            if out_v[sy * w + sx] > v * 0.5 or v < 0.08:
                continue
            ch = "." if v < 0.4 else "+" if v < 0.75 else "*"
            put(sx, sy, ch, mix((90, 110, 170), white, v), level=v)
        # reflection: mirrored rows, wobbling and broken into ripples
        if self.refl:
            depth = h - hz
            for y in range(hz, h):
                d = y - hz
                ym = int(hz - 1 - d * self.mk)
                if ym < 0:
                    break
                fade = 0.85 - 0.35 * d / max(1, depth)
                wob = noise1(y * 0.9 + t * 0.5, 7) * (0.8 + d * 0.12)
                row = ym * w
                lv = cv.lv
                for x in range(w):
                    sx = int(x + wob + 0.7 * math.sin(x * 0.13 + y * 1.7 + t * 1.2))
                    if sx < 0 or sx >= w:
                        continue
                    v = out_v[row + sx]
                    if v <= 0.05:
                        continue
                    br = 0.75 + 0.25 * math.sin(x * 0.29 + y * 2.3 - t * 0.9)
                    v = v * fade * br
                    gi = int(v * rn + 0.5)
                    if gi > 0 and v > lv[y * w + x]:
                        col = out_c[row + sx]
                        kk = 0.3 + 0.7 * v
                        put(x, y, "~" if gi >= rn * 0.6 and ramp is VERTICAL else ramp[gi],
                            (col[0] * kk, col[1] * kk, col[2] * kk), level=v)
