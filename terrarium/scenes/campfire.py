"""A crackling campfire under the stars: flames, sparks, smoke and warm light."""
import math

from ..engine import ASPECT, RAMPS, Canvas, Scene, clamp, gradient, mix, noise1, scale

PALETTES = {
    "classic": [(40, 0, 0), (150, 20, 0), (235, 70, 0), (255, 140, 20), (255, 205, 70), (255, 245, 190)],
    "ember": [(30, 0, 0), (120, 10, 0), (200, 30, 0), (250, 80, 10), (255, 150, 40), (255, 220, 150)],
    "golden": [(50, 10, 0), (170, 50, 0), (245, 120, 10), (255, 190, 40), (255, 235, 120), (255, 255, 220)],
    "blue": [(0, 0, 40), (10, 30, 140), (30, 100, 230), (80, 180, 255), (170, 230, 255), (240, 250, 255)],
    "green": [(0, 30, 10), (10, 110, 40), (40, 200, 80), (120, 255, 120), (200, 255, 170), (245, 255, 230)],
}
LUT_N = 48
FLAME = " .':^*(%#@"  # flame glyphs used with the default charset


class Campfire(Scene):
    name = "campfire"
    title = "Campfire"
    blurb = "a crackling campfire under the stars, with sparks and drifting smoke"
    tags = ("night", "cozy", "fire", "calm")
    options = {
        "size": (1.0, "size of the fire (0.5 .. 2)"),
        "sparks": (1.0, "amount of sparks (0 = none)"),
        "wind": ("random", "sideways lean of flames and smoke, -1 .. 1 (or random)"),
        "palette": ("random", "random, classic, ember, golden, blue or green"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        size = clamp(self.opt("size"), 0.3, 3.0)
        try:
            self.wind = clamp(float(self.opt("wind")), -1.5, 1.5)
        except ValueError:
            self.wind = rng.uniform(-0.35, 0.35)
        pal = self.opt("palette")
        if pal not in PALETTES:  # real fires mostly; now and then a magic one
            pal = rng.choices(list(PALETTES), (6, 3, 3, 1, 1))[0]
        self.palette = pal
        self.gy = int(h * rng.uniform(0.66, 0.78))   # ground line (top of the clearing)
        self.cx = w * rng.uniform(0.38, 0.62)
        wide, tall = rng.uniform(0.8, 1.25), rng.uniform(0.75, 1.3)   # low and broad .. tall and licking
        self.fw = int(clamp(min(w * 0.18, h * ASPECT * 0.3) * size * wide, 9, w - 4))
        self.fh = int(clamp(h * 0.45 * size * tall, 6, h - 2))
        self.decay_k = rng.uniform(0.85, 1.1)
        self.spread = rng.uniform(1.0, 2.0)          # how hard the edges burn off: wide body .. single tongue
        self.spark_k = rng.uniform(0.5, 1.6)
        self.base = self.gy + max(1, int((h - self.gy) * 0.3))   # row the flames grow from
        self.heat = [[0.0] * self.fw for _ in range(self.fh)]
        self.acc = 0.0
        self.lut = [gradient(PALETTES[pal], i / (LUT_N - 1)) for i in range(LUT_N)]
        self.sparks = []      # [x, y, vx, vy, life, max]
        self.smoke = []       # [x, y, age, seed]
        self.spark_acc = 0.0
        self.smoke_acc = 0.0
        self.flicker = 1.0
        self.stars = [(rng.randrange(w), rng.randrange(max(1, self.gy - 3)), rng.uniform(0.2, 1.0), rng.uniform(0, 6.3))
                      for _ in range(int(w * self.gy / 40 * self.density))]
        # treeline silhouette: a clearing in pines, taller toward the edges (or an open hilltop)
        seed = rng.randrange(1, 9999)
        pines = []
        x = rng.uniform(-3, 0)
        trees = rng.uniform(0.0, 1.4) if rng.random() < 0.85 else 0.0
        sl = rng.uniform(1.1, 2.1)
        while x < w + 3:
            d = abs(x - self.cx) / max(1, w / 2)
            pines.append((x, self.gy - h * rng.uniform(0.04, 0.16) * (0.4 + trees * d), sl * rng.uniform(0.85, 1.15)))
            x += rng.uniform(1.5, 4.0)
        self.tree_top = [min(py + abs(x + 0.5 - px) * sl for px, py, sl in pines) for x in range(w + 1)]
        # stones in a ring around the fire (an ellipse in perspective)
        self.stones = []
        n = max(5, int(self.fw * rng.uniform(0.5, 1.0)))
        kinds = rng.choice(("Oo0@", "Oo", "@0", "()o"))
        rx, ry = self.fw * 0.62, max(1.0, self.fw * 0.62 / ASPECT * 0.35)
        for k in range(n):
            a = math.pi * (k + 0.5) / n                 # front half only; the back is hidden by logs
            self.stones.append((self.cx - math.cos(a) * rx, self.base + math.sin(a) * ry * 0.9 + 0.4,
                                rng.choice(kinds), rng.uniform(0.6, 1.0)))
        self.stick_h = max(2, int(self.fh * 0.25))
        ns = rng.randint(0, 5)
        lean = rng.uniform(0.4, 0.8)
        self.sticks = [(self.cx + o * self.fw * 0.3, -o * lean) for o in
                       ([-1 + 2 * k / (ns - 1) for k in range(ns)] if ns > 1 else [])]
        nl = rng.choice((1, 2, 2, 3))
        self.logs = [(self.fw * (0.44 - 0.12 * k) * rng.uniform(0.85, 1.1), self.base - k) for k in range(nl)]
        self.ground = [[(x * 37 + y * 53 + seed) % 11 for x in range(w)] for y in range(h)]
        self._bgkey = None

    # ------------------------------------------------------------------ static layer
    def paint_static(self, b):
        w, h, gy = self.w, self.h, self.gy
        for y in range(gy):
            g = y / max(1, gy)
            for x in range(w):
                if y >= self.tree_top[x]:
                    continue
                if (x * 5 + y * 3) % 4 == 0 and g > 0.4:
                    b.put(x, y, ".", mix((10, 14, 34), (40, 30, 50), g), level=0.05)
        for x in range(w):
            ya, yb = self.tree_top[x], self.tree_top[x + 1]
            ch = "/" if yb < ya - 0.5 else "\\" if yb > ya + 0.5 else "^"
            top = min(ya, yb)
            for y in range(max(0, int(top)), gy):
                if y <= int(max(ya, yb)) - 1 or y == int(top):
                    b.put(x, y, ch, (35, 40, 55), level=0.1)

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

    # ------------------------------------------------------------------ simulation
    def step_fire(self):
        """One step of a 'doom fire' heat field, shaped into tongues of flame."""
        rng = self.rng
        heat, fw, fh = self.heat, self.fw, self.fh
        half = fw / 2
        t = self.t
        wind = self.wind
        bottom = heat[fh - 1]
        for x in range(fw):
            d = abs(x + 0.5 - half) / half
            base = (1 - d * d) ** 0.6 if d < 1 else 0.0
            tongue = noise1(x * 0.28 + t * 1.7, 3) * 0.6 + noise1(x * 0.7 - t * 3.1, 4) * 0.4  # hot spots wander
            bottom[x] = base * clamp(0.8 + 0.55 * tongue) * (0.85 + 0.15 * rng.random())
        k_decay = 0.95 * self.decay_k / fh
        lean = wind * 0.6
        rnd = rng.random
        for y in range(fh - 1):
            src = heat[y + 1]
            dst = heat[y]
            up = 1 - y / fh                                  # 1 at the top .. 0 at the bottom
            for x in range(fw):
                r = rnd()
                sx = x + (1 if r < 0.3 + lean * 0.3 else -1 if r > 0.7 + lean * 0.3 else 0)
                if sx < 0 or sx >= fw:
                    dst[x] = 0.0
                    continue
                d = abs(x + 0.5 - half) / half
                decay = k_decay * (0.3 + 1.4 * rnd()) * (1 + self.spread * d * d * (0.3 + up))
                v = src[sx] - decay
                dst[x] = v if v > 0 else 0.0

    def update(self, dt):
        super().update(dt)
        rng = self.rng
        self.acc += dt
        steps = 0
        while self.acc > 1 / 30 and steps < 4:
            self.acc -= 1 / 30
            self.step_fire()
            steps += 1
        if self.acc > 1 / 30:
            self.acc = 0.0
        t = self.t
        self.flicker = 0.85 + 0.1 * noise1(t * 3.1, 1) + 0.05 * noise1(t * 9.0, 2)
        wind = self.wind
        # sparks
        rate = 9 * self.opt("sparks") * self.spark_k * (self.fw / 16)
        self.spark_acc += dt * rate
        top = self.base - self.fh * 0.45
        while self.spark_acc > 1:
            self.spark_acc -= 1
            life = rng.uniform(0.8, 2.4)
            self.sparks.append([self.cx + rng.uniform(-0.3, 0.3) * self.fw, top + rng.uniform(-2, 3),
                                rng.uniform(-2.5, 2.5) + wind * 4, -rng.uniform(5, 11), life, life])
        keep = []
        for s in self.sparks:
            s[0] += (s[2] + 2.5 * noise1(t * 2 + s[5] * 10, 4)) * dt
            s[1] += s[3] * dt
            s[3] *= 1 - 0.6 * dt
            s[4] -= dt
            if s[4] > 0 and s[1] > -1:
                keep.append(s)
        self.sparks = keep[-300:]
        # smoke
        self.smoke_acc += dt * 3.0
        while self.smoke_acc > 1:
            self.smoke_acc -= 1
            self.smoke.append([self.cx + rng.uniform(-1.5, 1.5), self.base - self.fh * 0.7, 0.0, rng.uniform(0, 99)])
        keep = []
        for s in self.smoke:
            s[2] += dt
            s[1] -= dt * (1.6 - 0.12 * s[2])
            s[0] += dt * (wind * 3 + 1.4 * noise1(t * 0.4 + s[3], 6))
            if s[2] < 9 and s[1] > -2:
                keep.append(s)
        self.smoke = keep

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, gy, t = self.w, self.h, self.gy, self.t
        if (cv.w, cv.h) != (w, h):
            return
        self.background(cv)
        put, shade = cv.put, cv.shade
        cx, base, fw, fh = self.cx, self.base, self.fw, self.fh
        fl = self.flicker
        for x, y, b, ph in self.stars:
            if y >= self.tree_top[x]:
                continue
            v = b * (0.5 + 0.5 * math.sin(t * 1.4 + ph))
            if v > 0.25:
                put(x, y, "." if v < 0.6 else "+" if v < 0.9 else "*", mix((80, 100, 150), (235, 240, 255), v), level=0.2)
        # warm light on the clearing
        R = fw * 1.1
        glyphs = ".,'`.,:;'.,"
        exp = math.exp
        for y in range(gy, h):
            dy = (y - base) * ASPECT * 1.8
            row = self.ground[y]
            for x in range(w):
                dx = x - cx
                d = math.sqrt(dx * dx + dy * dy) / R
                v = fl * exp(-d * 1.7)
                gi = row[x]
                if v < 0.07:
                    if gi < 2:
                        put(x, y, ".", (30, 22, 24), level=0.02)
                    continue
                if gi > 8 * v + 2:  # sparser texture farther from the fire
                    continue
                put(x, y, glyphs[gi], mix((60, 22, 12), (255, 155, 70), min(1.0, v * 1.2)), level=v * 0.5)
        # light on the tree line
        for x in range(w):
            top = self.tree_top[x]
            d = abs(x - cx) / (w * 0.5)
            k = fl * 0.6 * max(0.0, 1 - d) ** 2
            if k > 0.05 and top < gy:
                put(x, int(top), cv.ch[int(top) * w + x], mix((35, 40, 55), (200, 100, 40), k), level=0.2)
        # smoke (behind the flames)
        for sx, sy, age, sd in self.smoke:
            k = age / 9
            r = 0.8 + age * 0.55
            v = 0.32 * (1 - k) ** 1.5 * min(1.0, age * 1.5)
            col = mix((120, 80, 70), (90, 95, 115), min(1.0, age / 3))
            for dx in range(-int(r), int(r) + 1):
                f = 1 - abs(dx) / (r + 0.5)
                shade(sx + dx, sy, v * f, col)
        # a teepee of sticks behind the flames
        for k, (lx, lean) in enumerate(self.sticks):
            for j in range(int(self.stick_h)):
                y = base - 1 - j
                x = lx + lean * j
                glow = max(0.0, 1 - j / self.stick_h)
                put(x, y, "|" if abs(lean) < 0.1 else "/" if lean > 0 else "\\", mix((60, 35, 22), (200, 90, 30), glow * fl), level=0.4)
        # flames
        heat, lut = self.heat, self.lut
        ramp = FLAME if cv.ramp == RAMPS["ascii"] else cv.ramp
        rn = len(ramp) - 1
        lv = cv.lv
        x0 = cx - fw / 2
        lmax = LUT_N - 1
        for gy_ in range(fh):
            y = int(base - fh + 1 + gy_)
            if y < 0 or y >= h:
                continue
            row = heat[gy_]
            for gx in range(fw):
                v = row[gx]
                if v < 0.06:
                    continue
                v = v * fl * 1.15
                if v > 1:
                    v = 1.0
                g = v ** 0.7
                gi = int(g * rn + 0.5)
                if gi > 0 and g > lv[y * w + int(x0 + gx)]:
                    put(x0 + gx, y, ramp[gi], lut[int(min(1.0, v * 1.25) * lmax)], level=g)
        # logs at the base, in front of the flames
        for r, (lw, ly) in enumerate(self.logs):
            x0, x1 = int(cx - lw), int(cx + lw)
            for x in range(x0, x1 + 1):
                glow = max(0.0, 1 - abs(x + 0.5 - cx) / lw)
                ember = 0.5 + 0.5 * noise1(x * 0.7 + t * 1.5, 8 + r)
                if x == x0 or x == x1:
                    ch = "(" if x == x0 else ")"
                    c = (110, 70, 45)
                else:
                    ch = "=" if r == 0 else "-"
                    c = mix((80, 45, 28), (255, 120, 30), glow * ember * fl)
                put(x, ly, ch, c, level=0.6)
        # stones (in front)
        for sx, sy, ch, b in self.stones:
            k = max(0.0, 1 - abs(sx - cx) / (fw * 0.8)) * fl
            put(sx, sy, ch, mix(scale((95, 90, 95), b), (255, 140, 60), 0.25 + 0.55 * k), level=0.7)
        # sparks
        for x, y, vx, vy, life, mx in self.sparks:
            k = life / mx
            col = gradient([(140, 20, 0), (255, 90, 0), (255, 180, 60), (255, 240, 180)], k)
            put(x, y, "*" if k > 0.75 else "'" if vy < -3 else ".", col, level=0.9)
