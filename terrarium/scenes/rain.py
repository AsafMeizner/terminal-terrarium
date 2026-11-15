"""Night rain over a city: slanted streaks, splashes, ripples and lightning."""
import math

from ..engine import ASPECT, Canvas, Scene, clamp, mix, noise1, scale

WINDOW_SETS = [
    [(255, 200, 110), (255, 170, 80), (255, 220, 150), (170, 210, 255), (255, 140, 90)],   # warm
    [(160, 210, 255), (200, 230, 255), (255, 220, 160), (120, 180, 255)],                  # cold
    [(255, 90, 180), (90, 230, 255), (255, 200, 110), (180, 120, 255)],                    # neon
]
GLOWS = [((50, 50, 110), (210, 110, 120)), ((40, 50, 100), (200, 140, 90)), ((30, 40, 90), (90, 120, 200)),
         ((50, 30, 90), (200, 90, 170))]


class Rain(Scene):
    name = "rain"
    title = "Rain"
    blurb = "night rain over a city, with splashes, ripples and lightning"
    tags = ("night", "weather", "city", "moody")
    interactions = "click to call down lightning right there"
    options = {
        "intensity": (1.0, "how hard it rains (0.2 .. 3)"),
        "wind": ("random", "slant of the rain, -1 .. 1 (or random)"),
        "lightning": (1.0, "how often lightning strikes (0 = never)"),
        "skyline": ("random", "random, city, forest or none"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.gy = max(4, int(h * rng.uniform(0.64, 0.76)))   # street level (top of the ground band)
        self.skyline = self.opt("skyline")
        if self.skyline not in ("city", "forest", "none"):
            self.skyline = rng.choices(("city", "forest", "none"), (6, 3, 1))[0]
        try:
            self.wind = clamp(float(self.opt("wind")), -1.5, 1.5)
        except ValueError:
            self.wind = rng.choice((-1, 1)) * rng.uniform(0.0, 0.7)
        # the mood: color of the sky glow, the windows, the lightning
        self.glow = rng.choice(GLOWS)
        self.win_colors = rng.choice(WINDOW_SETS)
        self.branch_p = rng.uniform(0.03, 0.12)    # chance a bolt forks at each step
        self.zig = rng.uniform(0.8, 2.0)           # how far each bolt step can swing sideways
        self.bolt_tint = rng.choice(((130, 110, 230), (110, 150, 255), (200, 120, 230)))
        self.top = [self.gy] * w                   # first row of skyline per column (gy = nothing)
        self.windows = []                          # (x, y, color, flicker phase or None, glyph)
        self.far_top = [self.gy] * w
        self.antennas = []
        if self.skyline == "city":
            self.build_city()
        elif self.skyline == "forest":
            self.build_forest()
        n = int(w * h / 7 * self.opt("intensity") * self.density)
        self.drops = [self.new_drop(rng.uniform(-h, h)) for _ in range(max(10, n))]
        self.splashes = []    # [x, y, vx, vy, life]
        self.ripples = []     # [x, y, age, rmax]
        self.flash = 0.0
        self.bolt = None
        self.bolt_t = 0.0
        self.next_strike = self.strike_delay()
        self._bgkey = None
        self.sparks = []      # embers where a clicked bolt hits a roof or tree: [x, y, vx, vy, life]

    def on_click(self, x, y):
        rng, w, h, gy = self.rng, self.w, self.h, self.gy
        tx = clamp(x, 0.0, w - 1.0)
        roof = self.top[int(tx)] if self.skyline != "none" else gy
        if y < roof:
            end, wet = float(roof), roof >= gy        # hits the rooftop / treetop under the click
        else:
            end, wet = clamp(y, gy + 0.5, h - 1.0), True   # all the way down to the street
        # a jagged walk from the top of the sky, bent so it lands exactly on the target
        pts = [(tx + rng.uniform(-8, 8), 0.0)]
        while pts[-1][1] < end and len(pts) < 300:
            px, py = pts[-1]
            pts.append((px + rng.choice((-1, -1, 0, 1, 1)) * rng.uniform(0.4, self.zig), py + rng.uniform(0.6, 1.4)))
        err = tx - pts[-1][0]
        last = max(1e-6, pts[-1][1])
        pts = [(px + err * py / last, min(py, end)) for px, py in pts]
        segs = []
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            segs.append((x0, y0, x1, y1, 1.0))
            if rng.random() < self.branch_p * 1.5 and len(segs) < 500:
                self._grow(x1, y1, min(end, y1 + end * rng.uniform(0.2, 0.45)), segs, 1, 0.6)
        self.bolt = segs
        self.bolt_t = 0.0
        self.next_strike = max(self.next_strike, 1.5)
        if wet:
            # the puddle it hits jumps: rings and a crown of spray
            for k in range(3):
                self.ripples.append([tx, end, -0.15 * k, 6.0 + 3.0 * k])
            for _ in range(26):
                self.splashes.append([tx + rng.uniform(-1.5, 1.5), end - 0.3, rng.uniform(-14, 14),
                                      -rng.uniform(8, 20), rng.uniform(0.4, 0.8)])
        else:
            for _ in range(22):
                self.sparks.append([tx + rng.uniform(-0.5, 0.5), end - 0.3, rng.uniform(-12, 12),
                                    -rng.uniform(4, 14), rng.uniform(0.4, 0.9)])

    def strike_delay(self):
        f = self.opt("lightning")
        if f <= 0:
            return 1e9
        return self.rng.expovariate(f / 7.0) + 1.5

    def build_city(self):
        rng, w, gy = self.rng, self.w, self.gy
        self.far_top = [gy] * w
        tall = rng.uniform(0.75, 1.25)             # skyscrapers or a low town
        wide = rng.uniform(0.7, 1.4)
        gap = rng.choice((0, 1, 2))
        for depth in (0, 1):
            x = rng.randint(-6, 0)
            while x < w:
                bw = max(3, int((rng.randint(4, 11) if depth == 0 else rng.randint(5, 14)) * wide))
                hmax = gy * (0.55 if depth == 0 else 0.42) * tall
                bh = int(rng.uniform(gy * 0.12, hmax) if depth == 0 else rng.uniform(gy * 0.08, hmax))
                top = gy - bh
                for xx in range(max(0, x), min(w, x + bw)):
                    self.top[xx] = min(self.top[xx], top)
                    if depth == 0:
                        self.far_top[xx] = min(self.far_top[xx], top)
                lit = rng.uniform(0.15, 0.6)
                for yy in range(top + 1, gy - 1, 1 + depth):
                    for xx in range(x + 1, x + bw - 1, 2):
                        if 0 <= xx < w and rng.random() < lit:
                            c = rng.choice(self.win_colors)
                            c = scale(c, 0.55 if depth == 0 else 0.95)
                            self.windows.append((xx, yy, c, rng.uniform(0, 6.3) if rng.random() < 0.08 else None,
                                                 "·" if depth == 0 else "•"))
                if bh > gy * 0.35 and rng.random() < 0.5:
                    self.antennas.append((x + bw // 2, top - 1, rng.uniform(0, 6.3)))
                x += bw + (rng.randint(0, gap) if depth == 0 else rng.randint(1, 2 + 2 * gap))

    def build_forest(self):
        """A pine forest: the upper envelope of many narrow triangles."""
        rng, w, gy = self.rng, self.w, self.gy
        tall = rng.uniform(0.7, 1.3)
        slope = rng.uniform(1.1, 2.2)            # rows per column: narrow spruces .. broad firs
        pines = []
        x = rng.uniform(-3, 0)
        while x < w + 3:
            pines.append((x, gy - gy * rng.uniform(0.12, 0.38) * tall, slope * rng.uniform(0.8, 1.2)))
            x += rng.uniform(1.5, 5.0)
        self.ftop = [min(gy, min(py + abs(xx + 0.5 - px) * sl for px, py, sl in pines)) for xx in range(w + 1)]
        self.top = [int(v) for v in self.ftop[:w]]

    def new_drop(self, y=None):
        rng = self.rng
        z = rng.random() ** 1.4                    # most drops are far away
        land = self.gy + (self.h - self.gy) * (0.15 + 0.85 * z)
        return [rng.uniform(-self.w * 0.3, self.w * 1.3), -rng.uniform(0, 4) if y is None else y,
                z, 28 + 40 * z, land]

    # ------------------------------------------------------------------ static layer
    def paint_static(self, b):
        w, h, gy = self.w, self.h, self.gy
        # city glow above the skyline, hazy far buildings, black near buildings
        ymid = sum(self.top) / max(1, w)
        span = max(3.0, gy * 0.5)
        for y in range(gy):
            g = clamp(1 - (ymid - y) / span)
            for x in range(w):
                if y < self.top[x]:
                    v = 0.03 + 0.27 * g ** 2.2
                    b.shade(x, y, v, mix(self.glow[0], self.glow[1], g ** 2))
                elif self.skyline == "city" and y >= self.far_top[x] and (y < self.top[x] or self.top[x] == self.far_top[x])                         and self.far_top[x] < gy and (x * 3 + y * 7) % 3 == 0:
                    pass
        for x in range(w):
            ft, nt = self.far_top[x], self.top[x]
            if self.skyline != "city" or ft >= gy:
                continue
            for y in range(ft, gy):
                near = y >= nt and nt < ft
                if not near:
                    b.put(x, y, ":" if (x * 3 + y * 5) % 3 else ".", (40, 42, 72), level=0.05)
        # roof lines / tree outlines
        for x in range(w):
            t = self.top[x]
            if t >= gy:
                continue
            if self.skyline == "city":
                b.put(x, t, "_", (40, 48, 75), level=0.1)
                continue
            ya, yb = self.ftop[x], self.ftop[x + 1]
            ch = "/" if yb < ya - 0.5 else "\\" if yb > ya + 0.5 else "^"
            for y in range(int(min(ya, yb)), max(int(min(ya, yb)) + 1, int(max(ya, yb)))):
                b.put(x, y, ch, (45, 60, 80), level=0.1)
        # street: faint wet texture
        for y in range(gy, h):
            for x in range(w):
                if (x * 7 + y * 13) % 11 == 0:
                    b.put(x, y, "-" if (x + y) % 2 else ".", (25, 32, 50), level=0.05)

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

    # ------------------------------------------------------------------ lightning
    def make_bolt(self):
        rng, w = self.rng, self.w
        x = rng.uniform(w * 0.1, w * 0.9)
        end = self.top[int(clamp(x, 0, w - 1))] if self.skyline != "none" else self.gy
        segs = []
        self._grow(x, 0.0, end, segs, 0, 1.0)
        return segs

    def _grow(self, x, y, end, segs, depth, strength):
        rng = self.rng
        while y < end and len(segs) < 600:
            nx = x + rng.choice((-1, -1, 0, 1, 1)) * rng.uniform(0.4, self.zig)
            ny = y + rng.uniform(0.6, 1.4)
            segs.append((x, y, nx, ny, strength))
            if depth < 2 and rng.random() < self.branch_p:
                bend = end * rng.uniform(0.3, 0.6) if depth == 0 else end * 0.2
                self._grow(nx, ny, min(end, ny + bend), segs, depth + 1, strength * 0.6)
            x, y = nx, ny

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        rng = self.rng
        wind = self.wind
        h, w = self.h, self.w
        for d in self.drops:
            d[1] += d[3] * dt
            d[0] += d[3] * wind * dt * 0.5
            if d[1] >= d[4]:
                z = d[2]
                if z > 0.25:
                    if z > 0.5 and rng.random() < 0.45:
                        self.ripples.append([d[0], d[4], 0.0, 1.5 + 4.5 * z])
                    for _ in range(1 + int(z * 2.5)):
                        self.splashes.append([d[0], d[4] - 0.3, rng.uniform(-6, 6) * z + wind * 3,
                                              -rng.uniform(5, 11) * z, 0.35])
                d[:] = self.new_drop()
        keep = []
        for s in self.splashes:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 40 * dt
            s[4] -= dt
            if s[4] > 0:
                keep.append(s)
        self.splashes = keep[-400:]
        keep = []
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 30 * dt
            s[4] -= dt
            if s[4] > 0:
                keep.append(s)
        self.sparks = keep[-200:]
        keep = []
        for r in self.ripples:
            r[2] += dt
            if r[2] < 0.9:
                keep.append(r)
        self.ripples = keep[-300:]
        # lightning
        self.next_strike -= dt
        if self.next_strike <= 0:
            self.bolt = self.make_bolt()
            self.bolt_t = 0.0
            self.next_strike = self.strike_delay()
        if self.bolt is not None:
            self.bolt_t += dt
            bt = self.bolt_t
            # flicker: strike, dip, restrike, fade
            if bt < 0.08:
                self.flash = 1.0
            elif bt < 0.14:
                self.flash = 0.3
            elif bt < 0.24:
                self.flash = 0.85
            else:
                self.flash = max(0.0, 0.85 - (bt - 0.24) * 2.2)
            if bt > 0.7:
                self.bolt = None
                self.flash = 0.0

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, gy, t = self.w, self.h, self.gy, self.t
        if (cv.w, cv.h) != (w, h):
            return
        self.background(cv)
        put, shade = cv.put, cv.shade
        f = self.flash
        top = self.top
        if f > 0.02:  # the whole sky lights up; the skyline stays a black silhouette
            for y in range(gy):
                g = y / gy
                v = f * (0.25 + 0.35 * (1 - g))
                col = mix((150, 140, 210), (90, 90, 150), g)
                for x in range(w):
                    if y < top[x]:
                        k = (x * 7 + y * 3) % 5
                        put(x, y, ":" if k == 0 else "." if k < 3 else "'", scale(col, v * (1.4 + 0.4 * k)), level=v)
        # windows and their wobbling reflections on the wet street
        refl = (h - gy)
        for x, y, c, ph, g in self.windows:
            k = 1.0
            if ph is not None:
                k = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * 2.5 + ph)) ** 3
            put(x, y, g, scale(c, k), level=0.5)
            ry = gy + (gy - y) * 0.6
            if ry < h - 0.5:  # broken, wobbling reflection on the wet street
                for j in range(2):
                    yy = ry + j
                    rx = x + noise1(yy * 0.9 + t * 1.7, x) * 1.6
                    put(rx, yy, "|" if j == 0 else "!", scale(c, 0.45 * k * (1 - j * 0.4)), level=0.3)
        for x, y, ph in self.antennas:
            if math.sin(t * 2 + ph) > 0.6:
                put(x, y, "*", (255, 60, 60), level=0.8)
            else:
                put(x, y, "|", (60, 60, 80), level=0.2)
        # ground lit by the flash
        if f > 0.02:
            for y in range(gy, h):
                for x in range(0, w, 1):
                    if (x * 3 + y * 7) % 4 == 0:
                        put(x, y, "-", scale((150, 150, 210), f * 0.7), level=0.1)
        # ripples: flattened ellipses that expand and fade
        for rx, ry, age, rmax in self.ripples:
            if age < 0:
                continue
            k = age / 0.9
            r = rmax * (0.25 + 0.75 * math.sqrt(k))
            v = (1 - k) * 0.55
            ry_ = r / ASPECT * 0.5
            steps = max(6, int(r * 2.2))
            col = scale((130, 160, 215), v + 0.1)
            for i in range(steps):
                a = i / steps * math.tau
                ca = math.cos(a)
                px = rx + ca * r
                py = ry + math.sin(a) * ry_
                put(px, py, "-" if abs(ca) < 0.6 else ".", col, level=v)
        # rain streaks
        wind = self.wind
        sl = wind * 0.5
        ch = "|" if abs(sl) < 0.12 else "\\" if sl > 0 else "/"
        lit = 0.4 * f
        for x, y, z, sp, land in self.drops:
            if y < 0:
                continue
            length = 1 + int(z * 3.5)
            c = mix((55, 70, 105), (175, 195, 235), z)
            if lit:
                c = mix(c, (230, 230, 255), lit)
            for k in range(length):
                yy = y - k
                if yy >= land:
                    continue
                xx = x - sl * k
                fade = 1 - k / (length + 0.5)
                put(xx, yy, ch, scale(c, fade), level=0.3 + 0.5 * z)
        for x, y, vx, vy, life in self.splashes:
            put(x, y, "." if vy > 0 else "'", (150, 175, 220), level=0.5)
        for x, y, vx, vy, life in self.sparks:
            put(x, y, "*" if life > 0.5 else "'" if vy < 0 else ".", mix((255, 120, 40), (255, 240, 200), clamp(life * 1.5)),
                level=0.9)
        # the bolt
        if self.bolt is not None and f > 0.25:
            core = (240, 235, 255)
            halo = self.bolt_tint
            for x0, y0, x1, y1, s in self.bolt:
                dx = x1 - x0
                c = "|" if abs(dx) < 0.45 else "/" if dx < 0 else "\\"
                for hx in (-2, -1, 1, 2):
                    if cv.lv[int(clamp(y1, 0, h - 1)) * w + int(clamp(x1 + hx, 0, w - 1))] < 0.9:
                        put(x1 + hx, y1, ":" if abs(hx) == 1 else ".", scale(halo, (0.9 if abs(hx) == 1 else 0.5) * s * f),
                            level=0.6)
                put(x1, y1, c, scale(core, 0.6 + 0.4 * s * f), level=1.0)
                if s >= 1.0:
                    put(x1 + (1 if dx >= 0 else -1) * 0.6, y1, c, scale(core, 0.8 * f), level=1.0)
