"""A glowing sun (or moon) on the horizon of a rolling sea."""
import math

from ..engine import ASPECT, RAMPS, Canvas, Scene, clamp, gradient, mix, noise2, scale

# sky stops top -> horizon, sea deep color, sun core, sun rim, glow color, path color
TIMES = {
    "sunset": dict(
        sky=[(30, 14, 70), (80, 26, 110), (170, 50, 120), (240, 90, 90), (255, 150, 70), (255, 200, 120)],
        sky_v=(0.05, 0.36), deep=(60, 30, 110), sun=(255, 245, 190), rim=(255, 120, 70), glow=(255, 150, 80),
        path=(255, 200, 120), cloud=(255, 130, 160), cloud_dark=(120, 40, 110), size=0.13, height=0.18,
        foam=(255, 210, 200), stars=0.0, gull=(25, 8, 30), clouds=1.0),
    "night": dict(
        sky=[(4, 6, 20), (8, 14, 40), (16, 30, 70), (30, 50, 100), (50, 75, 130)],
        sky_v=(0.03, 0.22), deep=(14, 26, 70), sun=(250, 250, 235), rim=(200, 210, 230), glow=(140, 160, 220),
        path=(210, 225, 255), cloud=(110, 120, 170), cloud_dark=(20, 25, 50), size=0.075, height=0.75,
        foam=(170, 190, 230), stars=1.0, gull=(140, 150, 180), clouds=0.55),
    "day": dict(
        sky=[(40, 110, 220), (70, 150, 235), (120, 190, 245), (180, 225, 250), (225, 245, 255)],
        sky_v=(0.25, 0.5), deep=(20, 90, 160), sun=(255, 255, 240), rim=(255, 240, 180), glow=(255, 250, 220),
        path=(255, 255, 230), cloud=(250, 252, 255), cloud_dark=(160, 185, 215), size=0.07, height=1.35,
        foam=(240, 250, 255), stars=0.0, gull=(40, 50, 70), clouds=0.8),
}
SUNSET_SKIES = [
    [(30, 14, 70), (80, 26, 110), (170, 50, 120), (240, 90, 90), (255, 150, 70), (255, 200, 120)],   # magenta
    [(12, 18, 60), (50, 40, 120), (130, 70, 140), (220, 120, 110), (255, 180, 90), (255, 225, 150)],  # golden
    [(25, 8, 40), (90, 15, 60), (180, 30, 50), (240, 80, 40), (255, 140, 50), (255, 190, 100)],      # crimson
    [(20, 20, 70), (60, 50, 140), (150, 90, 180), (240, 130, 170), (255, 180, 160), (255, 220, 190)],  # lilac
]
WAVE_PRESETS = {"calm": 0.15, "gentle": 0.3, "moderate": 0.45, "choppy": 0.65, "rough": 0.8, "stormy": 1.0}
GULL_FRAMES = ("\\v/", "-v-", "/v\\", "-v-")


class Ocean(Scene):
    name = "ocean"
    title = "Ocean"
    blurb = "a glowing sun on the horizon of a rolling sea"
    tags = ("nature", "ocean", "calm", "sky")
    options = {
        "time": ("random", "random, sunset, night or day"),
        "waves": ("random", "random, calm, gentle, moderate, choppy, rough, stormy (or 0..1)"),
        "gulls": (True, "an occasional seagull"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        time = self.opt("time")
        if time not in TIMES:
            time = rng.choices(("sunset", "night", "day"), (5, 3, 2))[0]
        self.time = time
        cfg = self.cfg = dict(TIMES[time])
        if time == "sunset":  # a few sunset moods
            cfg["sky"] = rng.choice(SUNSET_SKIES)
        raw = str(self.opt("waves")).lower()
        try:
            self.rough = clamp(float(raw))
        except ValueError:
            self.rough = WAVE_PRESETS.get(raw, rng.uniform(0.1, 0.85))
        self.hz = max(3, int(h * rng.uniform(0.42, 0.58)))
        hz = self.hz
        big = min(w, h * ASPECT * 1.2)
        self.sr = max(2.5, big * cfg["size"] * rng.uniform(0.8, 1.3))   # sun radius in x cells
        self.sx = w * rng.uniform(0.3, 0.7)
        self.sy = hz - self.sr / ASPECT * (0.15 + cfg["height"] * rng.uniform(1.6, 3.0))
        self.stripes = time == "sunset" and rng.random() < 0.7
        # waves: (amplitude, kx, kz, omega, phase)
        r = self.rough
        j = lambda v: v * rng.uniform(0.75, 1.3)  # noqa: E731  (each sea gets its own swell)
        sgn = rng.choice((-1, 1))
        self.waves = [
            (1.0, sgn * j(0.22), j(0.9), j(1.1), rng.uniform(0, 6.3)),
            (0.7 + 0.3 * r, -sgn * j(0.55), j(0.7), j(0.9), rng.uniform(0, 6.3)),
            (0.35 + 0.6 * r, rng.choice((-1, 1)) * j(1.1), j(1.4), j(1.9), rng.uniform(0, 6.3)),
            (0.2 + 0.4 * r, rng.choice((-1, 1)) * j(1.8), j(2.1), j(2.7), rng.uniform(0, 6.3)),
        ]
        self.wsum = sum(a for a, *_ in self.waves)
        # cloud streaks: a static noise texture, wider than the screen, scrolled slowly
        self.cw = w * 2
        self.clouds = []
        cseed = rng.randrange(1, 9999)
        cy, cs, ca = rng.uniform(0.3, 0.7), rng.uniform(0.15, 0.3), rng.uniform(0.3, 1.3)
        for y in range(hz):
            g = y / max(1, hz)
            band = math.exp(-((g - cy) / cs) ** 2) * (0.7 + 0.6 * r) * cfg["clouds"] * ca
            row = []
            for x in range(self.cw):
                n = noise2(x * 0.035, y * 0.45, cseed) * 0.65 + noise2(x * 0.09, y * 0.9, cseed + 1) * 0.35
                row.append(clamp((n + 0.1) * 1.8) * band)
            self.clouds.append(row)
        ns = int(w * hz / 30 * cfg["stars"] * self.density)
        self.stars = [(rng.randrange(w), rng.randrange(max(1, hz - 1)), rng.uniform(0.2, 1.0), rng.uniform(0, 6.3))
                      for _ in range(ns)]
        self.gull = None
        self.gull_timer = rng.uniform(2, 8)
        self._bgkey = None

    # ------------------------------------------------------------------ helpers
    def sky_at(self, y):
        """(color, intensity) of the plain sky gradient for a row."""
        g = y / max(1, self.hz - 1)
        lo, hi = self.cfg["sky_v"]
        return gradient(self.cfg["sky"], g), lo + (hi - lo) * g ** 1.6

    def paint_static(self, b):
        """Sky gradient and sun glow (static)."""
        w, hz = self.w, self.hz
        cfg = self.cfg
        sx, sy, sr = self.sx, self.sy, self.sr
        glow = cfg["glow"]
        for y in range(hz):
            col, v = self.sky_at(y)
            dy = (y + 0.5 - sy) * ASPECT
            for x in range(w):
                dx = x + 0.5 - sx
                d = math.sqrt(dx * dx + dy * dy) / sr
                gl = 0.0
                if d > 1.0:
                    gl = 0.65 * math.exp(-(d - 1.0) * 1.1) + 0.12 * math.exp(-(d - 1.0) * 0.25)
                c = mix(col, glow, min(1.0, gl * 1.3))
                b.shade(x, y, min(1.0, v + gl * 0.45), c)

    def background(self, cv):
        key = (cv.w, cv.h, cv.ramp)
        if self._bgkey != key:
            bg = Canvas(cv.w, cv.h, cv.ramp)
            self.paint_static(bg)
            self._bg = bg
            self._bgkey = key
        bg = self._bg
        cv.ch[:] = bg.ch
        cv.fg[:] = bg.fg
        cv.lv[:] = bg.lv
        cv.bc[:] = bg.bc

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        if not self.opt("gulls"):
            return
        if self.gull is None:
            self.gull_timer -= dt
            if self.gull_timer <= 0:
                d = self.rng.choice((-1, 1))
                self.gull = [(-4 if d > 0 else self.w + 4), self.rng.uniform(self.hz * 0.15, self.hz * 0.6),
                             d * self.rng.uniform(3.5, 6.0), self.rng.uniform(0, 6.3)]
        else:
            g = self.gull
            g[0] += g[2] * dt
            g[1] += math.sin(self.t * 0.9 + g[3]) * dt * 0.6
            if g[0] < -6 or g[0] > self.w + 6:
                self.gull = None
                self.gull_timer = self.rng.uniform(6, 16)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, hz, t = self.w, self.h, self.hz, self.t
        if (cv.w, cv.h) != (w, h):
            return
        cfg = self.cfg
        self.background(cv)
        shade = cv.shade
        sx, sy, sr = self.sx, self.sy, self.sr
        # stars
        for x, y, b, ph in self.stars:
            v = b * (0.5 + 0.5 * math.sin(t * 1.5 + ph))
            if v > 0.25:
                cv.put(x, y, "." if v < 0.6 else "+", mix((80, 100, 150), (240, 245, 255), v), level=v)
        # clouds (behind the sun's disc but lit by it)
        off = t * 0.6
        cw = self.cw
        ccol, cdark = cfg["cloud"], cfg["cloud_dark"]
        for y in range(hz):
            row = self.clouds[y]
            base, _ = self.sky_at(y)
            dy = (y - sy) * ASPECT
            for x in range(w):
                c = row[int(x + off) % cw]
                if c < 0.3:
                    continue
                prox = math.exp(-abs(x - sx) / (sr * 3.5) - abs(dy) / (sr * 4))
                col = mix(cdark, ccol, clamp(0.35 + prox * 0.9))
                shade(x, y, 0.3 + 0.6 * c * (0.5 + 0.6 * prox), col, mode="over", dim=False)
        # sun / moon disc
        self.draw_disc(cv)
        # sea
        self.draw_sea(cv)
        # gull
        g = self.gull
        if g is not None:
            frame = GULL_FRAMES[int(t * 6 + g[3]) % 4]
            cv.text(int(g[0]) - 1, int(g[1]), frame, cfg["gull"])

    def draw_disc(self, cv):
        cfg = self.cfg
        sx, sy, sr, t, hz = self.sx, self.sy, self.sr, self.t, self.hz
        ry = sr / ASPECT
        night = self.time == "night"
        for y in range(max(0, int(sy - ry - 1)), min(hz, int(sy + ry + 2))):
            dy = (y + 0.5 - sy) / ry
            if abs(dy) > 1:
                continue
            half = sr * math.sqrt(1 - dy * dy)
            g = (dy + 1) / 2
            # synthwave stripes across the lower half of the sun, drifting down
            stripe = 1.0
            if self.stripes and dy > 0.1 and int(y - sy) % 2 == 1:
                stripe = 0.5  # synthwave bands across the lower half
            col = mix(cfg["sun"], cfg["rim"], g ** 1.4)
            for x in range(int(sx - half), int(sx + half) + 1):
                dx = (x + 0.5 - sx) / sr
                edge = dx * dx + dy * dy
                if edge > 1:
                    continue
                v = (1.0 - 0.15 * edge) * stripe
                c = col
                if night:  # craters
                    n = noise2(x * 0.5, y * 0.9, 3)
                    if n > 0.25:
                        c = mix(col, (150, 160, 185), (n - 0.25) * 1.6)
                        v -= 0.12
                cv.shade(x, y, v, c, mode="over")

    def draw_sea(self, cv):
        cfg = self.cfg
        w, h, hz, t = self.w, self.h, self.hz, self.t
        sx, sr = self.sx, self.sr
        inv = 1.0 / self.wsum
        deep = cfg["deep"]
        pathc = cfg["path"]
        foamc = cfg["foam"]
        rough = self.rough
        foam_thr = 0.62 - 0.3 * rough
        sea_h = h - hz
        sin = math.sin
        put = cv.put
        water = cv.ramp == RAMPS["ascii"]
        ramp = cv.ramp
        prev = 0.0
        rn = len(ramp) - 1
        (a0, kx0, kz0, w0, p0), (a1, kx1, kz1, w1, p1), (a2, kx2, kz2, w2, p2), (a3, kx3, kz3, w3, p3) = self.waves
        for y in range(hz, h):
            p = (y - hz + 1) / sea_h               # ~0 at the horizon .. 1 at the bottom
            z = 1.0 / p
            Z = z * 3.5
            refl_c, _ = self.sky_at(max(0, int(hz - 1 - (y - hz) * 1.3)))
            fres = (1 - p) ** 1.5                  # far water mirrors the sky, near water is deep
            lit = mix(mix(deep, refl_c, 0.5 + 0.5 * fres), (255, 255, 255), 0.12)
            dark = mix(deep, refl_c, 0.2 + 0.3 * fres)
            amp = 0.45 + 0.55 * p ** 0.5
            pw = sr * (0.6 + 1.5 * p)              # half-width of the sun's glitter path
            xs = 0.22 * z
            ph0, ph1, ph2, ph3 = kz0 * Z + w0 * t + p0, kz1 * Z + w1 * t + p1, kz2 * Z + w2 * t + p2, kz3 * Z + w3 * t + p3
            vmax = 0.55 + 0.2 * fres
            for x in range(w):
                X = (x - sx) * xs
                n = (a0 * sin(kx0 * X + ph0) + a1 * sin(kx1 * X + ph1)
                     + a2 * sin(kx2 * X + ph2) + a3 * sin(kx3 * X + ph3)) * inv * amp
                crest = n * 1.25 + 0.35
                crest = 0.0 if crest < 0 else 1.0 if crest > 1 else crest
                v = 0.25 + vmax * crest * crest
                c = mix(dark, lit, crest)
                dxp = abs(x - sx)
                if dxp < pw:
                    k = 1 - dxp / pw
                    sp = 0.5 + 0.5 * sin(x * 2.3 + y * 5.1 + n * 7 + t * 2.4)
                    g = k ** 1.5 * (0.45 + 0.55 * crest) * (0.35 + 0.65 * sp)
                    if g > 0.5 and sp > 0.93:
                        put(x, y, "*", pathc, level=1.0)
                        continue
                    if g > 0.16 and water:  # glitter: broken bright dashes
                        put(x, y, "=" if g > 0.5 else "-" if g > 0.3 else "~" if crest > 0.4 else "_",
                            mix(c, pathc, min(1.0, 0.3 + g)), level=0.5 + g * 0.5)
                        continue
                    c = mix(c, pathc, min(1.0, g * 1.6 + k * 0.2))
                    v += g * 0.9
                if n > foam_thr:
                    f = min(1.0, (n - foam_thr) / (1 - foam_thr) * 2)
                    put(x, y, "^" if f > 0.8 and p > 0.5 and rough > 0.6 else "~", mix(c, foamc, 0.3 + 0.7 * f), level=0.8)
                    continue
                if v > 1.0:
                    v = 1.0
                kk = 0.45 + 0.55 * v
                if water:  # pick the glyph from the wave's shape, not just its brightness
                    if crest < 0.12:
                        ch = "." if (x + y) % 3 else " "
                    elif crest < 0.3:
                        ch = "_" if n < prev else "."
                    elif crest < 0.55:
                        ch = "-"
                    elif crest < 0.8 or v < 0.7:
                        ch = "~"
                    else:
                        ch = "="
                    prev = n
                    if ch != " ":
                        put(x, y, ch, (c[0] * kk, c[1] * kk, c[2] * kk), level=v)
                    continue
                gi = int(v * rn + 0.5)
                if gi > 0:
                    put(x, y, ramp[gi], (c[0] * kk, c[1] * kk, c[2] * kk), level=v)
