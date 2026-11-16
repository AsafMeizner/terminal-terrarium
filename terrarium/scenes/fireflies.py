"""Fireflies blinking over a summer meadow at the edge of a forest."""
import math

from ..engine import ASPECT, Canvas, Scene, clamp, gradient, mix, noise1, scale

COLORS = {
    "yellow": [(255, 230, 110), (230, 255, 120), (255, 215, 90)],
    "green": [(170, 255, 120), (130, 255, 150), (200, 255, 110)],
    "blue": [(120, 220, 255), (150, 200, 255), (110, 255, 230)],
    "amber": [(255, 170, 70), (255, 140, 60), (255, 200, 90)],
    "mixed": [(255, 230, 110), (170, 255, 120), (120, 220, 255), (255, 160, 220)],
}
HALO = ".·:+*"  # glow glyphs from faint to bright
SKIES = [
    [(4, 6, 22), (8, 14, 40), (14, 30, 60), (25, 60, 80), (40, 90, 95)],     # teal dusk
    [(6, 4, 24), (16, 12, 48), (34, 26, 80), (70, 50, 110), (110, 80, 120)],  # violet
    [(2, 6, 16), (6, 14, 34), (10, 26, 56), (20, 44, 90), (40, 70, 120)],     # deep blue
    [(8, 6, 20), (20, 16, 40), (50, 34, 60), (100, 60, 70), (150, 90, 70)],   # last light of sunset
]


class Bug:
    def __init__(self, rng, w, top, bottom, color, depth):
        self.depth = depth                     # 0 far .. 1 near
        self.bx = rng.uniform(0, w)
        self.by = rng.uniform(top, bottom)
        self.s1 = rng.randrange(1, 9999)
        self.s2 = rng.randrange(1, 9999)
        self.speed = rng.uniform(0.08, 0.18)
        self.period = rng.uniform(2.5, 5.5)
        self.phase = rng.uniform(0, 1)
        self.on = rng.uniform(0.3, 0.5)        # fraction of the cycle spent lit
        self.color = color
        self.x = self.bx
        self.y = self.by
        self.pull = 0.0                        # 0 free .. 1 circling the pointer's lantern
        self.orbit = 2.5 + (self.s1 % 997) / 997 * 6.5   # how close it circles (no extra dice: keeps seeds stable)


class Fireflies(Scene):
    name = "fireflies"
    title = "Fireflies"
    blurb = "fireflies blinking over a summer meadow at the edge of a forest"
    tags = ("night", "nature", "calm", "summer")
    interactions = "point to hold up a lantern they drift toward, click to set off a swarm flashing in sync"
    options = {
        "count": (0, "number of fireflies (0 = based on screen size)"),
        "color": ("random", "random, yellow, green, blue, amber or mixed"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.hz = int(h * rng.uniform(0.56, 0.68))   # where the far treeline meets the meadow
        hz = self.hz
        self.sky = rng.choice(SKIES)
        # far treeline: pointed pines or round broadleaf crowns, as an upper envelope of shapes
        tall = rng.uniform(0.7, 1.4)
        self.pines = rng.random() < 0.6
        if self.pines:
            pines = []
            x = rng.uniform(-3, 0)
            sl = rng.uniform(1.1, 2.2)
            while x < w + 3:
                pines.append((x, hz - h * rng.uniform(0.06, 0.18) * tall, sl * rng.uniform(0.85, 1.15)))
                x += rng.uniform(1.5, 4.5)
            self.tree_top = [min(py + abs(x + 0.5 - px) * s_ for px, py, s_ in pines) for x in range(w + 1)]
        else:
            crowns = []
            x = rng.uniform(-6, 0)
            while x < w + 6:
                r = rng.uniform(3, 8) * max(1.0, w / 110) ** 0.5
                crowns.append((x, hz - h * rng.uniform(0.06, 0.16) * tall, r))
                x += r * rng.uniform(0.8, 1.5)
            top = []
            for x in range(w + 1):
                best = float(hz)
                for cx, cy, r in crowns:
                    d = abs(x + 0.5 - cx)
                    if d < r:
                        best = min(best, cy + r / ASPECT * (1 - math.sqrt(1 - (d / r) ** 2)) * 3.0)
                top.append(best)
            self.tree_top = top
        # big framing trees at the edges: (cx, canopy cy, rx, ry, trunk width)
        self.frames = []
        for side in (0, 1):
            if rng.random() < 0.7:
                cx = (rng.uniform(-0.04, 0.08) if side == 0 else rng.uniform(0.92, 1.04)) * w
                rx = max(6, w * rng.uniform(0.1, 0.16))
                self.frames.append((cx, h * rng.uniform(0.18, 0.3), rx, h * rng.uniform(0.22, 0.32), max(2, int(rx * 0.22))))
        mr = max(3.5, min(w, h * ASPECT) * rng.uniform(0.06, 0.1))
        side = rng.choice((-1, 1))
        self.moon = (w * (0.5 + side * rng.uniform(0.1, 0.32)), h * rng.uniform(0.12, 0.24), mr)
        self.phase = (rng.choice((-1, 1)) * rng.uniform(0.3, 0.65), rng.uniform(-0.25, 0.25))  # crescent cut
        self.stars = [(rng.randrange(w), rng.randrange(max(1, int(hz * 0.85))), rng.uniform(0.2, 1.0), rng.uniform(0, 6.3),
                       rng.uniform(0.5, 2.0)) for _ in range(int(w * h / 45 * self.density))]
        # grass blades: (x, height, phase)
        self.grass_h = rng.uniform(0.7, 1.4)
        self.grass = []
        for x in range(w):
            for _ in range(2):
                tall = rng.random() < 0.08
                gh = (rng.uniform(3, 4 + h * 0.12) if tall else rng.uniform(1.0, 2.2 + h * 0.05)) * self.grass_h
                self.grass.append((x + rng.uniform(-0.4, 0.4), gh, rng.uniform(0, 6.3)))
        cname = self.opt("color")
        if cname not in COLORS:
            cname = rng.choices(("yellow", "green", "blue", "amber", "mixed"), (5, 3, 1, 2, 2))[0]
        pal = COLORS[cname]
        n = self.opt("count") or self.count(30, lo=8)
        self.bugs = []
        for k in range(n):
            depth = rng.random()
            top = hz - h * 0.25 + depth * h * 0.15
            bottom = hz + (h - hz) * (0.3 + 0.6 * depth)
            self.bugs.append(Bug(rng, w, top, bottom, rng.choice(pal), depth))
        self.bugs.sort(key=lambda b: b.depth)
        self.n_base = len(self.bugs)
        self.pal = pal
        self._bgkey = None

    # ------------------------------------------------------------------ mouse
    def on_click(self, x, y):
        rng = self.rng
        w, h, t = self.w, self.h, self.t
        x = clamp(x if x == x else w / 2, 0, w - 1)
        y = clamp(y if y == y else h / 2, 0, h - 1)
        period = rng.uniform(2.2, 3.2)
        phase = (0.02 - t / period) % 1.0          # all of them light up right now, together
        swarm = []
        for _ in range(rng.randint(10, 16)):
            b = Bug(rng, w, y - 1, y + 1, rng.choice(self.pal), rng.random())
            a = rng.uniform(0, math.tau)
            r = math.sqrt(rng.random()) * max(6.0, w * 0.08)
            b.bx, b.by = x + math.cos(a) * r, y + math.sin(a) * r / ASPECT
            # their wandering starts centred on the click, not on a random offset
            b.bx -= noise1(t * b.speed, b.s1) * 9 * (0.5 + b.depth)
            b.by -= noise1(t * b.speed * 1.3, b.s2) * 3.5 * (0.5 + b.depth) + math.sin(t * 0.7 + b.s1) * 0.6
            swarm.append(b)
        # fireflies already nearby catch the rhythm too
        reach = max(10.0, w * 0.15)
        for b in self.bugs + swarm:
            if b in swarm or math.hypot(b.x - x, (b.y - y) * ASPECT) < reach:
                b.period = period
                b.phase = phase + rng.uniform(-0.01, 0.01)
                b.on = 0.42
        extra = self.bugs[self.n_base:] + swarm
        self.bugs = self.bugs[:self.n_base] + extra[-48:]     # keep the meadow from overfilling
        self.bugs.sort(key=lambda b: b.depth)

    # ------------------------------------------------------------------ static layer
    def paint_static(self, b):
        w, h, hz = self.w, self.h, self.hz
        mx, my, mr = self.moon
        ref = sum(self.tree_top) / max(1, w)
        for y in range(hz + 1):
            g = min(1.0, y / max(1.0, ref))
            col = gradient(self.sky, g)
            for x in range(w):
                if y >= self.tree_top[x]:
                    continue
                dx = x + 0.5 - mx
                dy = (y + 0.5 - my) * ASPECT
                d = math.sqrt(dx * dx + dy * dy)
                # crescent: inside the moon, outside a second disc shifted toward the light
                dx2 = dx + mr * self.phase[0]
                dy2 = dy - mr * self.phase[1]
                inner = math.sqrt(dx2 * dx2 + dy2 * dy2)
                if d < mr:
                    if inner > mr * 0.9:
                        edge = inner < mr * 1.08 or d > mr - 0.9
                        b.put(x, y, (")" if self.phase[0] > 0 else "(") if edge else "@", (255, 245, 205) if edge else (255, 250, 225), level=1.0)
                    continue
                glow = 0.35 * math.exp(-max(0.0, d - mr) / (mr * 0.35))
                hg = g ** 5
                if glow > 0.08 and ((x * 7 + y * 13) % 3 or glow > 0.2):
                    c = mix(col, (210, 215, 180), min(1.0, glow * 1.5))
                    b.put(x, y, ":" if glow > 0.25 else ".", scale(c, 0.4 + glow * 1.2), level=0.05)
                elif hg > 0.1:  # horizon glow behind the trees
                    if hg > 0.35 or (x * 3 + y * 7) % 3:
                        c = mix(col, (90, 160, 140), hg)
                        b.put(x, y, ":" if hg > 0.7 else ".", scale(c, 0.5 + 0.8 * hg), level=0.1)
                elif (x * 5 + y * 3) % 3 == 0:
                    b.put(x, y, ".", scale(col, 1.2), level=0.03)
        # far treeline: dark, with a faint rim of horizon light
        for x in range(w):
            top = self.tree_top[x]
            ya, yb = self.tree_top[x], self.tree_top[x + 1]
            ch = "/" if yb < ya - 0.5 else "\\" if yb > ya + 0.5 else "^"
            if not self.pines and ch == "^":  # rounded crowns: pick the glyph by sub-row height
                fr = min(ya, yb) % 1
                ch = "_" if fr > 0.66 else "-" if fr > 0.33 else "`"
            top = min(ya, yb)
            for y in range(max(0, int(top)), hz + 1):
                if y <= int(max(ya, yb)) - 1 or y == int(top):
                    b.put(x, y, ch, (40, 85, 85), level=0.2)
                else:
                    b.ch[y * w + x] = " "
                    b.lv[y * w + x] = 0.0
        # meadow
        for y in range(hz + 1, h):
            g = (y - hz) / max(1, h - hz)
            for x in range(w):
                if (x * 11 + y * 7) % 5 < 2:
                    b.put(x, y, "." if (x + y) % 3 else ",", scale((20, 55, 35), 0.7 + 0.6 * g), level=0.05)
        # framing trees: trunk and a big leafy canopy
        for cx, cy, rx, ry, tw in self.frames:
            for y in range(int(cy), h):
                for x in range(int(cx - tw / 2), int(cx + tw / 2) + 1):
                    edge = x in (int(cx - tw / 2), int(cx + tw / 2))
                    b.put(x, y, "|" if edge else ":" if (x + y) % 2 else ".", (70, 52, 40) if edge else (38, 30, 26), level=0.3)
            for y in range(max(0, int(cy - ry)), min(h, int(cy + ry * 0.7))):
                for x in range(max(0, int(cx - rx * 1.2)), min(w, int(cx + rx * 1.2) + 1)):
                    dx = (x - cx) / rx
                    dy = (y - cy) / ry
                    n = noise1(x * 0.35 + y * 0.9, 21) * 0.25 + noise1(x * 0.13 - y * 0.4, 22) * 0.2
                    r = dx * dx + dy * dy
                    if r < 1 + n:
                        rim = clamp((r - (0.72 + n)) * 4) * clamp(0.7 - dy)
                        i = y * w + x
                        b.ch[i] = " "  # the canopy hides the sky behind it
                        b.lv[i] = 0.0
                        hsh = (x * 37 + y * 53) % 7
                        if rim > 0.15 or hsh == 0:
                            leaf = "&%*@&%,"[hsh]
                            b.put(x, y, leaf, mix((10, 24, 18), (45, 95, 70), rim), level=0.3)

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
        t = self.t
        w, h = self.w, self.h
        p = self.pointer
        reach = max(14.0, min(w, h * ASPECT) * 0.45)    # how far the lantern's light carries
        for b in self.bugs:
            # smooth wandering: slow noise around a drifting home position
            b.bx += noise1(t * 0.05, b.s1 + 7) * dt * 1.5
            if b.bx < -5:
                b.bx += w + 10
            elif b.bx > w + 5:
                b.bx -= w + 10
            b.x = b.bx + noise1(t * b.speed, b.s1) * 9 * (0.5 + b.depth)
            b.y = b.by + noise1(t * b.speed * 1.3, b.s2) * 3.5 * (0.5 + b.depth) + math.sin(t * 0.7 + b.s1) * 0.6
            if p is not None or b.pull > 0.0:
                want = 0.0
                if p is not None:
                    d = math.hypot(b.x - p[0], (b.y - p[1]) * ASPECT)
                    if d < reach * (1.6 if b.pull > 0.2 else 1.0):
                        want = 0.85
                b.pull += (want - b.pull) * min(1.0, dt * (0.7 if want else 0.35))
                if b.pull < 0.005 and not want:
                    b.pull = 0.0
                if b.pull > 0.0:
                    lx, ly = p if p is not None else (b.x, b.y)
                    if p is not None:
                        b.lx, b.ly = lx, ly
                    else:
                        lx, ly = getattr(b, "lx", b.x), getattr(b, "ly", b.y)
                    a = t * (0.5 + b.speed * 2) * (1 if b.s1 % 2 else -1) + b.s2
                    ox = lx + math.cos(a) * b.orbit
                    oy = ly + math.sin(a) * b.orbit / ASPECT
                    e = b.pull * b.pull * (3 - 2 * b.pull)
                    b.x += (ox - b.x) * e
                    b.y += (oy - b.y) * e

    def brightness(self, b):
        p = ((self.t / b.period) + b.phase) % 1.0
        if p < b.on:
            s = math.sin(math.pi * p / b.on)
            return s * s
        return 0.0

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, hz, t = self.w, self.h, self.hz, self.t
        if (cv.w, cv.h) != (w, h):
            return
        self.background(cv)
        put, shade = cv.put, cv.shade
        lv = cv.lv
        for x, y, b, ph, rate in self.stars:
            if lv[y * w + x] > 0.1 or y >= self.tree_top[x]:
                continue
            v = b * (0.55 + 0.45 * math.sin(t * rate + ph))
            if v > 0.25:
                put(x, y, "." if v < 0.6 else "+" if v < 0.9 else "*", mix((80, 100, 150), (230, 240, 255), v), level=0.15)
        # swaying grass
        for gx, gh, ph in self.grass:
            sway = math.sin(t * 0.9 + gx * 0.15 + ph * 0.3) * 0.5 + noise1(t * 0.4 + gx * 0.05, 3) * 0.6
            rows = int(gh)
            for r in range(rows + 1):
                y = h - 1 - r
                lean = sway * (r / max(1, rows))
                x = gx + lean * r * 0.8
                ch = "/" if lean > 0.25 else "\\" if lean < -0.25 else "|"
                if r == rows:
                    ch = "'" if gh % 1 > 0.5 else ","
                c = mix((15, 45, 25), (45, 110, 60), r / max(1, rows))
                put(x, y, ch, c, level=0.2)
        # the pointer's lantern: a small warm glow
        p = self.pointer
        if p is not None:
            px, py = p
            for y in range(max(0, int(py - 3)), min(h, int(py + 4))):
                for x in range(max(0, int(px - 6)), min(w, int(px + 7))):
                    g = math.exp(-((x + 0.5 - px) ** 2 + ((y + 0.5 - py) * ASPECT) ** 2) / 9.0) * 0.45
                    if g > 0.05 and g > lv[y * w + x]:
                        put(x, y, HALO[min(2, int(g * 6))], scale((255, 200, 120), 0.35 + g), level=g)
        # fireflies: a bright core with a soft halo
        for b in self.bugs:
            v = self.brightness(b)
            near = b.depth
            if v < 0.03:
                if near > 0.5:  # unlit fireflies are faint dark specks
                    put(b.x, b.y, ".", (40, 50, 30), level=0.1)
                continue
            col = b.color
            rx = 2.0 + 3.0 * near
            ry = rx / ASPECT
            x0, x1 = int(b.x - rx - 1), int(b.x + rx + 1)
            y0, y1 = int(b.y - ry - 1), int(b.y + ry + 1)
            inv = 1.0 / (rx * rx)
            amp = v * (0.7 + 0.45 * near)
            for y in range(max(0, y0), min(h, y1 + 1)):
                dy = (y + 0.5 - b.y) * ASPECT
                row = y * w
                for x in range(max(0, x0), min(w, x1 + 1)):
                    dx = x + 0.5 - b.x
                    g = math.exp(-(dx * dx + dy * dy) * inv * 2.5) * amp
                    if g > 0.06 and g > lv[row + x]:
                        put(x, y, HALO[min(len(HALO) - 1, int(g * len(HALO) * 1.1))],
                            mix(scale(col, 0.25 + 0.75 * g), col, 0.0), level=g)
            core = "@" if near > 0.6 and v > 0.6 else "*" if v > 0.4 else "+"
            put(b.x, b.y, core, mix(col, (255, 255, 240), 0.5 * v), level=1.0)
