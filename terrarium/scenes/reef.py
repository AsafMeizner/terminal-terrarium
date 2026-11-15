"""A sunlit coral reef: branching, brain and fan corals, swaying anemones with clownfish,
schools of tropical fish flocking, a sea turtle gliding past, caustics rippling on the sand."""
import math

from ..engine import ASPECT, RAMPS, Scene, clamp, gradient, hsv, mix, noise1, noise2, scale
from .bonsai import wood_glyph

TAU = math.tau


def qc(c):
    r, g, b = c
    return (0 if r < 0 else 252 if r > 252 else int(r) & ~3,
            0 if g < 0 else 252 if g > 252 else int(g) & ~3,
            0 if b < 0 else 252 if b > 252 else int(b) & ~3)


def hsh(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


CORAL_COLORS = [
    (255, 105, 170), (190, 110, 255), (255, 150, 70), (255, 220, 90), (90, 230, 210),
    (255, 90, 90), (150, 255, 140), (255, 170, 210), (120, 170, 255), (255, 120, 40),
]
BRAIN_COLORS = [(210, 220, 110), (230, 190, 120), (250, 160, 170), (170, 230, 150), (230, 140, 220)]
FISH = [
    # name, template colors: tail, body, stripe, eye/mouth
    ("blue tang", (255, 220, 60), (50, 110, 255), (20, 40, 140), (255, 230, 90)),
    ("yellow tang", (255, 210, 40), (255, 235, 70), (255, 250, 170), (255, 255, 255)),
    ("neon", (255, 60, 100), (70, 230, 255), (140, 255, 255), (255, 255, 255)),
    ("anthias", (255, 190, 70), (230, 100, 255), (255, 150, 255), (255, 230, 160)),
    ("parrot", (255, 120, 200), (70, 225, 175), (40, 160, 255), (255, 255, 200)),
    ("angel", (60, 70, 220), (255, 205, 50), (40, 50, 190), (255, 255, 255)),
    ("chromis", (120, 255, 200), (90, 255, 170), (200, 255, 230), (255, 255, 255)),
    ("wrasse", (80, 200, 255), (255, 110, 60), (60, 220, 255), (255, 240, 200)),
]
TEMPLATES = [
    ("><>", "tbe"),
    ("><(°>", "tbbee"),
    ("><))°>", "tbsbee"),
    ("><)))°>", "ttbsbee"),
]
MIRROR = str.maketrans("<>(){}/\\", "><)(}{\\/")


class Reef(Scene):
    name = "reef"
    title = "Coral Reef"
    blurb = "a vibrant coral reef: flocking tropical fish, swaying anemones, a gliding sea turtle"
    tags = ("ocean", "nature", "colorful", "calm")
    options = {
        "fish": (1.0, "amount of fish (multiplier)"),
        "turtle": (True, "a sea turtle glides by now and then"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.seed = rng.randrange(1 << 15)
        s = self.seed
        # water look varies per run
        hue = rng.uniform(-0.04, 0.05)
        self.water_top = hsv(0.52 + hue, 0.75, 0.82)
        self.water_bot = hsv(0.6 + hue, 0.9, 0.18)
        self.sand_col = mix((230, 200, 140), hsv(rng.uniform(0.05, 0.12), 0.4, 0.95), rng.uniform(0, 0.4))
        bed = rng.uniform(0.8, 0.86)
        amp = rng.uniform(0.02, 0.06)
        self.bed = [h * bed + h * amp * noise1(x * 0.04, s) + 0.6 * noise1(x * 0.2, s + 1) for x in range(w)]
        self.surface = 1
        self.slant = rng.uniform(0.35, 0.8) * rng.choice((-1, 1))
        self.ray_freq = rng.uniform(0.1, 0.2)
        self.build_water()
        self.beams = [(rng.uniform(0, w + h), rng.uniform(1.2, 3.5) * clamp(w / 100, 0.7, 1.5),
                       rng.uniform(0.05, 0.15), rng.uniform(0, TAU)) for _ in range(rng.randint(3, 6) + w // 60)]
        self.coral = {}       # static coral cells: index -> (ch, color)
        self.anims = []       # animated features
        self.anemones = []
        self.build_reef()
        self.static = [(i, c, qc(col)) for i, (c, col) in self.coral.items()]
        # fish schools
        n_species = rng.randint(3, 5)
        species = rng.sample(FISH, n_species)
        amount = max(0.0, float(self.opt("fish")))
        self.schools = []
        area = w * h / 3000
        for k, sp in enumerate(species):
            tmpl = TEMPLATES[rng.choice((0, 0, 1, 1, 2, 3)) if k else rng.choice((0, 1))]
            big = len(tmpl[0])
            n = int(round((rng.randint(8, 20) if big <= 3 else rng.randint(3, 9)) * area ** 0.7 * amount * self.density))
            if n <= 0:
                continue
            band = rng.uniform(0.15, 0.65) * h
            school = {
                "sp": sp, "tmpl": tmpl, "speed": rng.uniform(5, 9) * (1.2 if big <= 3 else 0.85),
                "band": band, "ph": rng.uniform(0, TAU), "wx": rng.uniform(0.03, 0.07), "wy": rng.uniform(0.05, 0.12),
                "fish": [],
            }
            gx = rng.uniform(0, w)
            for _ in range(n):
                school["fish"].append([gx + rng.uniform(-6, 6), band + rng.uniform(-2, 2), rng.uniform(-2, 2),
                                       rng.uniform(-0.5, 0.5), 1 if rng.random() < 0.5 else -1, rng.uniform(0, TAU)])
            self.schools.append(school)
        # clownfish live in the first anemone
        self.clowns = []
        if self.anemones:
            a = self.anemones[0]
            for k in range(rng.randint(1, 2)):
                self.clowns.append([a, rng.uniform(0, TAU), rng.uniform(0.7, 1.2)])
        self.bubbles = []
        self.snow = [[rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.2, 1.0), rng.uniform(0, TAU)]
                     for _ in range(int(w * h / 70 * self.density))]
        self.turtle = None
        self.turtle_wait = rng.uniform(4, 14)

    # -- static layers ------------------------------------------------------------------
    def build_water(self):
        w, h = self.w, self.h
        s = self.seed
        n = w * h
        ch = [" "] * n
        fg = [None] * n
        lv = [0.0] * n
        self.row_col = []
        for y in range(h):
            f = y / max(1, h - 1)
            col = mix(self.water_top, self.water_bot, f ** 0.8)
            self.row_col.append(col)
            for x in range(w):
                i = y * w + x
                if y >= int(self.bed[x]):
                    # sand
                    d = y - int(self.bed[x])
                    r = hsh(x, y, s + 2)
                    dens = 0.75 if d == 0 else 0.5
                    if r < dens:
                        k = hsh(y, x, s + 3)
                        ch[i] = "~" if d == 0 and k < 0.3 else "." if k < 0.5 else "," if k < 0.75 else ":" if k < 0.9 else "°"
                    shade = 1.0 - 0.12 * d
                    fg[i] = qc(scale(mix(self.sand_col, col, 0.25), shade * (0.75 + 0.25 * hsh(x, y, s + 4))))
                    lv[i] = 0.3
                    continue
                r = hsh(x, y, s)
                dens = 0.05 + 0.12 * (1 - f) ** 3
                if r < dens:
                    ch[i] = "." if r < dens * 0.7 else "·"
                    fg[i] = qc(scale(col, 0.45 + 0.3 * (1 - f)))
                    lv[i] = 0.05
        # far reef silhouettes behind everything
        for x in range(w):
            top = self.bed[x] - h * (0.12 + 0.12 * (0.5 + 0.5 * noise1(x * 0.06, s + 9))) - 2 * noise1(x * 0.3, s + 10)
            for y in range(max(0, int(top)), int(self.bed[x])):
                i = y * w + x
                f = (y - top) / max(1.0, self.bed[x] - top)
                if hsh(x, y, s + 11) < 0.55:
                    ch[i] = ":" if hsh(x, y, s + 12) < 0.5 else "%" if f > 0.5 else "."
                    fg[i] = qc(scale(mix(self.row_col[y], (40, 60, 110), 0.5), 0.5 + 0.2 * f))
                    lv[i] = 0.1
        self.bg = (ch, fg, lv)

    def put_static(self, x, y, c, col):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.coral[y * self.w + x] = (c, col)

    def build_reef(self):
        rng = self.rng
        w, h = self.w, self.h
        kinds = ["branch", "brain", "fan", "tube", "anemone", "kelp"]
        weights = [rng.uniform(0.6, 2.0), rng.uniform(0.5, 1.6), rng.uniform(0.6, 1.8), rng.uniform(0.1, 0.6),
                   rng.uniform(0.3, 1.0), rng.uniform(0.2, 0.8)]
        # a few rocks first
        for _ in range(rng.randint(1, 3) + w // 60):
            self.rock(rng.uniform(0, w), rng.uniform(4, 10) * clamp(h / 30, 0.6, 1.6))
        placed_anemone = False
        for row in (0, 1):     # 0 = back row (dimmer), 1 = front row
            x = rng.uniform(-2, 3)
            while x < w:
                if row == 1 and not placed_anemone and x > w * 0.2:
                    kind = "anemone"
                else:
                    kind = rng.choices(kinds, weights)[0]
                size = rng.uniform(0.6, 1.15) * (0.75 if row == 0 else 1.0)
                width = self.place(kind, x, size, row)
                if kind == "anemone" and row == 1:
                    placed_anemone = True
                x += width + rng.uniform(1, 4) * (2.0 if row == 0 else 1.0)
        # starfish and shells on the sand
        for _ in range(int(w / 25) + 1):
            x = rng.randrange(0, max(1, w))
            y = int(self.bed[x]) + rng.randint(0, 2)
            if y < h:
                self.put_static(x, y, "*" if rng.random() < 0.6 else "@", rng.choice(((255, 110, 60), (255, 70, 90), (255, 200, 120))))

    def ground(self, x):
        return self.bed[int(clamp(x, 0, self.w - 1))]

    def rock(self, cx, r):
        rng = self.rng
        s = rng.randrange(1 << 12)
        base = self.ground(cx)
        ry = max(1.0, r / ASPECT * rng.uniform(0.6, 1.0))
        col = mix((70, 70, 90), self.row_col[int(clamp(base, 0, self.h - 1))], 0.3)
        for y in range(int(base - ry) - 1, int(base) + 1):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                if not (0 <= x < self.w and 0 <= y < self.h):
                    continue
                u = (x + 0.5 - cx) / r
                v = (y + 0.5 - base) / ry
                if u * u + v * v + 0.3 * noise2(x * 0.5, y, s) > 1 or y > self.bed[min(self.w - 1, x)] + 0.5:
                    continue
                lt = clamp(0.6 - 0.5 * v - 0.3 * u + 0.2 * noise2(x * 0.8, y * 1.5, s + 1))
                c = "o" if lt > 0.75 else ":" if lt > 0.45 else "." if lt > 0.25 else " "
                if c == " ":
                    continue
                self.put_static(x, y, c, scale(col, 0.5 + 0.8 * lt))
                if lt > 0.75 and hsh(x, y, s) < 0.15:   # coralline algae
                    self.put_static(x, y, "°", (255, 120, 170))
        for x in range(int(cx - r), int(cx + r) + 1):
            if 0 <= x < self.w:
                u = (x - cx) / r
                self.bed[x] = min(self.bed[x], base - ry * math.sqrt(max(0.0, 1 - u * u)) * 0.9)

    def place(self, kind, x0, size, row):
        rng = self.rng
        h = self.h
        H = max(3.0, (self.ground(x0) - h * 0.22) * size)
        dim = 0.7 if row == 0 else 1.15
        col = rng.choice(CORAL_COLORS)
        col = mix(col, self.row_col[int(h * 0.6)], 0.4 * (1 - dim))
        if kind == "branch":
            wdt = H * rng.uniform(0.7, 1.2)
            self.branch_coral(x0 + wdt / 2, H * rng.uniform(0.5, 0.85), col, dim)
            return wdt
        if kind == "brain":
            wdt = clamp(H * rng.uniform(0.5, 0.9), 4, 18)
            self.brain_coral(x0 + wdt / 2, wdt / 2, rng.choice(BRAIN_COLORS), dim)
            return wdt
        if kind == "fan":
            r = H * rng.uniform(0.45, 0.75)
            self.anims.append(("fan", x0 + r, self.ground(x0 + r), r, col, dim, rng.uniform(0, TAU),
                               rng.randrange(1 << 12), rng.randint(7, 12)))
            return r * 2
        if kind == "tube":
            n = rng.randint(2, 4)
            for k in range(n):
                tx = x0 + k * rng.uniform(2.2, 3.2)
                th = H * rng.uniform(0.2, 0.5)
                self.tube(tx, th, col, dim)
            return n * 3
        if kind == "anemone":
            r = clamp(H * rng.uniform(0.25, 0.4), 2.5, 9)
            a = {"x": x0 + r, "y": self.ground(x0 + r), "r": r, "col": rng.choice(
                ((255, 120, 200), (200, 120, 255), (120, 255, 200), (255, 160, 90))), "tip": rng.choice(
                ((255, 240, 255), (255, 255, 160), (180, 255, 255))), "dim": dim, "n": int(r * 4) + 6,
                "ph": rng.uniform(0, TAU), "len": r * rng.uniform(0.7, 1.0)}
            self.anims.append(("anemone", a))
            if row == 1:
                self.anemones.append(a)
            return r * 2 + 1
        if kind == "kelp":
            n = rng.randint(1, 3)
            for k in range(n):
                self.anims.append(("kelp", x0 + k * rng.uniform(1.5, 3.0), H * rng.uniform(0.35, 0.8),
                                   mix(rng.choice(((60, 170, 70), (120, 160, 50), (60, 140, 110))), self.row_col[int(h * 0.5)], 0.3 * (1 - dim)),
                                   dim, rng.uniform(0, TAU)))
            return n * 1.5 + 1
        if kind == "plate":
            wdt = clamp(H * rng.uniform(0.6, 1.0), 5, 22)
            self.plate_coral(x0 + wdt / 2, wdt / 2, H * rng.uniform(0.25, 0.45), col, dim)
            return wdt
        return 4

    def branch_coral(self, cx, H, col, dim):
        rng = self.rng
        base = self.ground(cx)
        tipc = mix(col, (255, 255, 255), 0.45)
        dark = scale(col, 0.45)
        spread = rng.uniform(0.35, 0.7)
        p_split = rng.uniform(0.35, 0.65)
        trunks = rng.randint(2, 4)

        def grow(x, y, ang, length, depth):
            steps = max(1, int(length * 2))
            for k in range(steps):
                f = k / steps
                nx = x + math.sin(ang) * 0.5
                ny = y - math.cos(ang) * 0.5 / ASPECT
                ang += rng.gauss(0, 0.08)
                g = wood_glyph(nx - x, ny - y)
                hgt = clamp((base - ny) / max(1.0, H))
                self.put_static(nx, ny, g, scale(mix(dark, col, hgt), dim))
                x, y = nx, ny
                if depth < 4 and rng.random() < p_split * 0.12:
                    grow(x, y, ang + rng.choice((-1, 1)) * spread * rng.uniform(0.6, 1.3), length * (1 - f) * 0.8, depth + 1)
            self.put_static(x, y, "o" if rng.random() < 0.6 else "*", scale(tipc, dim))

        for k in range(trunks):
            a = (k - (trunks - 1) / 2) * spread * 0.8 + rng.gauss(0, 0.1)
            grow(cx + rng.uniform(-1, 1), base, a, H * ASPECT * rng.uniform(0.7, 1.0), 0)

    def brain_coral(self, cx, r, col, dim):
        rng = self.rng
        s = rng.randrange(1 << 12)
        base = self.ground(cx)
        ry = max(1.5, r / ASPECT * rng.uniform(0.9, 1.3))
        for y in range(int(base - ry) - 1, int(base) + 1):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                u = (x + 0.5 - cx) / r
                v = (y + 0.5 - base) / ry
                if u * u + v * v > 1 or v > 0.2:
                    continue
                nz = math.sqrt(max(0.0, 1 - u * u - v * v))
                lt = clamp(0.35 + 0.45 * (-v) * 0.8 - 0.25 * u + 0.35 * nz)
                n = noise2(x * 0.55, y * 1.1, s) * 3.0 + noise2(x * 1.3, y * 2.4, s + 1)
                fr = n - math.floor(n)
                groove = abs(fr - 0.5) < 0.17
                c = ("~" if hsh(x, y, s) < 0.5 else "S") if groove else ("@" if lt > 0.6 else "%" if lt > 0.4 else "&")
                cc = scale(col, (0.45 if groove else 0.7 + 0.5 * lt) * dim)
                self.put_static(x, y, c, cc)

    def plate_coral(self, cx, r, H, col, dim):
        base = self.ground(cx)
        top = base - H
        # stalk
        for y in range(int(top) + 1, int(base) + 1):
            self.put_static(cx, y, "|", scale(col, 0.5 * dim))
        # layered plates, widest at the top
        for k in range(3):
            y = int(top + k * 1.0)
            rw = r * (1 - 0.3 * k)
            for x in range(int(cx - rw), int(cx + rw) + 1):
                u = abs(x - cx) / max(1.0, rw)
                c = "_" if k == 0 else "=" if u < 0.8 else "-"
                self.put_static(x, y, c, scale(mix(col, (255, 255, 255), 0.25 * (1 - u) * (k == 0)), (0.95 - 0.2 * k) * dim))

    def tube(self, x, th, col, dim):
        base = self.ground(x)
        top = int(base - th)
        for y in range(top, int(base) + 1):
            f = (y - top) / max(1, base - top)
            self.put_static(x, y, "(", scale(col, (0.9 - 0.4 * f) * dim))
            self.put_static(x + 1, y, ")", scale(col, (0.6 - 0.3 * f) * dim))
        self.put_static(x, top - 1, "_", scale(mix(col, (255, 255, 255), 0.4), dim))
        self.put_static(x + 1, top - 1, "_", scale(mix(col, (255, 255, 255), 0.4), dim))

    # -- update ----------------------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        rng = self.rng
        w, h = self.w, self.h
        t = self.t
        for sc in self.schools:
            self.flock(sc, dt, t)
        for c in self.clowns:
            c[1] += dt * c[2] * (1.0 + 0.8 * max(0.0, math.sin(t * 0.7 + c[2] * 5)))
        # bubbles
        if self.anemones or self.anims:
            if rng.random() < dt * (0.6 + w / 80):
                x = rng.uniform(0, w)
                self.bubbles.append([x, self.ground(x) - 1, rng.uniform(0, TAU), 0.0])
        for b in self.bubbles:
            b[1] -= dt * (2.5 + 2.0 * b[3])
            b[3] += dt * 0.3
            b[0] += math.sin(t * 3 + b[2]) * dt * 0.8
        self.bubbles = [b for b in self.bubbles if b[1] > self.surface]
        for m in self.snow:
            m[1] += dt * 0.3 * m[2]
            m[0] += math.sin(t * 0.4 + m[3]) * dt * 0.3
            if m[1] >= h:
                m[1] -= h
                m[0] = rng.uniform(0, w)
        # turtle
        if self.opt("turtle"):
            if self.turtle is None:
                self.turtle_wait -= dt
                if self.turtle_wait <= 0:
                    d = rng.choice((-1, 1))
                    size = clamp(min(w * 0.065, h * 0.2), 3.0, 9)
                    self.turtle = {"x": -size * 3 if d > 0 else w + size * 3, "y": rng.uniform(0.25, 0.55) * h,
                                   "dir": d, "size": size, "ph": 0.0, "y0": 0.0}
                    self.turtle["y0"] = self.turtle["y"]
            else:
                tu = self.turtle
                tu["ph"] += dt * 1.6
                tu["x"] += tu["dir"] * dt * (2.0 + 1.2 * max(0.0, math.sin(tu["ph"]))) * clamp(w / 100, 0.7, 1.6)
                tu["y"] = tu["y0"] + math.sin(tu["ph"] * 0.25) * h * 0.06
                if (tu["dir"] > 0 and tu["x"] > w + tu["size"] * 3) or (tu["dir"] < 0 and tu["x"] < -tu["size"] * 3):
                    self.turtle = None
                    self.turtle_wait = rng.uniform(25, 50)

    def flock(self, sc, dt, t):
        w, h = self.w, self.h
        fish = sc["fish"]
        speed = sc["speed"]
        gx = w * 0.5 + w * 0.6 * math.sin(t * sc["wx"] + sc["ph"])
        gy = sc["band"] + h * 0.12 * math.sin(t * sc["wy"] + sc["ph"] * 2)
        R2 = 64.0
        blen = len(sc["tmpl"][0]) + 1.5
        n = len(fish)
        for i in range(n):
            f = fish[i]
            x, y, vx, vy = f[0], f[1], f[2], f[3]
            cx = cy = ax_ = ay_ = sx = sy = 0.0
            cnt = 0
            for j in range(n):
                if j == i:
                    continue
                o = fish[j]
                dx = o[0] - x
                dy = (o[1] - y) * ASPECT
                d2 = dx * dx + dy * dy
                if d2 < R2:
                    cnt += 1
                    cx += dx
                    cy += dy
                    ax_ += o[2]
                    ay_ += o[3]
                    if abs(dx) < blen and abs(o[1] - y) < 1.3:
                        sx -= (1 if dx > 0 else -1) * (blen - abs(dx)) * 0.6
                        sy -= (1 if o[1] > y else -1) * (1.3 - abs(o[1] - y)) * 2.0
            accx = (gx - x) * 0.05
            accy = (gy - y) * 0.15
            if cnt:
                accx += cx / cnt * 0.25 + (ax_ / cnt - vx) * 0.6 + sx * 3.0
                accy += cy / cnt / ASPECT * 0.25 + (ay_ / cnt - vy) * 0.6 + sy * 1.5
            accx += math.sin(t * 0.9 + f[5]) * 1.5
            accy += math.cos(t * 0.7 + f[5] * 1.3) * 0.6
            bed = self.ground(x)
            if y < 3:
                accy += (3 - y) * 4
            if y > bed - 3:
                accy -= (y - bed + 3) * 5
            vx += accx * dt
            vy += accy * dt
            sp = math.sqrt(vx * vx + vy * vy)
            if sp > speed:
                vx *= speed / sp
                vy *= speed / sp
            elif sp < speed * 0.3:
                k = speed * 0.3 / max(sp, 1e-3)
                vx *= k
                vy *= k
            vy = clamp(vy, -speed * 0.35, speed * 0.35)
            f[0] = x + vx * dt
            f[1] = y + vy * dt
            f[2], f[3] = vx, vy
            if vx > 0.4:
                f[4] = 1
            elif vx < -0.4:
                f[4] = -1
            f[5] += dt * 6

    # -- drawing -----------------------------------------------------------------------------
    def draw(self, cv):
        w, h = self.w, self.h
        if cv.w != w or cv.h != h:
            return
        t = self.t
        bch, bfg, blv = self.bg
        cv.ch[:] = bch
        cv.fg[:] = bfg
        cv.lv[:] = blv
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        self.draw_rays(cv)
        self.draw_surface(cv)
        self.draw_caustics(cv)
        for x, y, z, ph in self.snow:
            xi, yi = int(x), int(y)
            if 0 <= xi < w and 0 <= yi < h and ch[yi * w + xi] == " ":
                i = yi * w + xi
                ch[i] = "·" if z > 0.6 else "."
                fg[i] = qc(scale((150, 200, 230), 0.25 + 0.3 * z))
        # back row animated + static coral
        for a in self.anims:
            if a[0] == "kelp":
                self.draw_kelp(cv, *a[1:])
            elif a[0] == "fan":
                self.draw_fan(cv, *a[1:])
        for i, c, col in self.static:
            ch[i] = c
            fg[i] = col
            lv[i] = 0.8
        for sc in self.schools:
            self.draw_school(cv, sc)
        if self.turtle:
            self.draw_turtle(cv, self.turtle)
        for a in self.anims:
            if a[0] == "anemone":
                self.draw_anemone(cv, a[1], 0)
        for c in self.clowns:
            self.draw_clown(cv, c)
        for a in self.anims:
            if a[0] == "anemone":
                self.draw_anemone(cv, a[1], 1)
        for x, y, ph, age in self.bubbles:
            xi, yi = int(x), int(y)
            if 0 <= xi < w and 0 <= yi < h:
                i = yi * w + xi
                ch[i] = "." if age < 0.4 else "o" if age < 1.2 else "O"
                fg[i] = qc(scale((200, 240, 255), 0.6 + 0.3 * math.sin(t * 5 + ph)))

    def draw_rays(self, cv):
        """A handful of soft slanted light shafts that drift and flicker."""
        w, h = self.w, self.h
        t = self.t
        sl = self.slant
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        bed = self.bed
        for k, (u0, wd, sp, ph) in enumerate(self.beams):
            u = (u0 + math.sin(t * sp + ph) * w * 0.08) % (w + h * abs(sl)) - (h * abs(sl) if sl > 0 else 0)
            flick = 0.55 + 0.45 * noise1(t * 0.3 + ph, self.seed + k)
            for y in range(1, h):
                fall = (1 - y / (h * 0.95)) ** 1.3
                if fall <= 0.04:
                    break
                xc = u + y * sl
                for x in range(int(xc - wd), int(xc + wd) + 1):
                    if not (0 <= x < w) or y >= bed[x]:
                        continue
                    v = (1 - abs(x + 0.5 - xc) / wd) * fall * flick
                    if v < 0.12:
                        continue
                    i = y * w + x
                    if lv[i] > 0.2:
                        continue
                    ch[i] = ":" if v > 0.55 else "·" if v > 0.3 else "."
                    fg[i] = qc(mix(self.row_col[y], (210, 245, 255), 0.2 + 0.6 * v))
                    lv[i] = 0.15

    def draw_surface(self, cv):
        w = self.w
        t = self.t
        ch, fg = cv.ch, cv.fg
        for x in range(w):
            v = math.sin(x * 0.3 + t * 1.5) + 0.6 * math.sin(x * 0.11 - t * 0.9 + 1.3)
            i = x
            ch[i] = "~" if v > 0.3 else "-" if v > -0.6 else "_"
            fg[i] = qc(mix(self.water_top, (240, 255, 255), 0.4 + 0.3 * v))
            if w + x < len(ch) and (v > 1.0 or hsh(x, int(t * 4), 3) < 0.03):
                ch[w + x] = "°" if v > 1.2 else "."
                fg[w + x] = qc(mix(self.water_top, (255, 255, 255), 0.6))

    def draw_caustics(self, cv):
        w, h = self.w, self.h
        t = self.t
        ch, fg = cv.ch, cv.fg
        bed = self.bed
        sand = self.sand_col
        bright = (255, 250, 210)
        for x in range(w):
            y0 = int(bed[x])
            for y in range(y0, min(h, y0 + 4)):
                c = math.sin(x * 0.35 + t * 1.1 + 2.0 * math.sin(y * 0.8 - t * 0.6)) * \
                    math.sin(x * 0.21 - t * 0.7 + 1.7 * math.sin(y * 0.5 + x * 0.05 + t * 0.4))
                if c > 0.45:
                    i = y * w + x
                    if cv.lv[i] > 0.5:
                        continue
                    k = (c - 0.45) / 0.55
                    ch[i] = "~" if k > 0.5 else "-" if k > 0.2 else ch[i] if ch[i] != " " else "."
                    fg[i] = qc(mix(sand, bright, 0.3 + 0.7 * k))

    def draw_kelp(self, cv, x0, H, col, dim, ph):
        w, h = self.w, self.h
        t = self.t
        base = self.ground(x0)
        n = int(H)
        px = x0
        for k in range(n):
            f = k / max(1, n)
            x = x0 + math.sin(t * 0.9 + ph + k * 0.25) * f * 2.2 + math.sin(t * 0.37 + ph) * f * 1.2
            y = int(base - k)
            xi = int(x)
            if 0 <= xi < w and 0 <= y < h:
                dx = x - px
                c = "(" if dx < -0.12 else ")" if dx > 0.12 else "|"
                i = y * w + xi
                if k % 3 == 1 and k > 1:
                    lx = xi + (1 if (k // 3) % 2 else -1)
                    if 0 <= lx < w:
                        cv.ch[y * w + lx] = "," if lx < xi else "'"
                        cv.fg[y * w + lx] = qc(scale(mix(col, (220, 255, 140), 0.5), (0.6 + 0.4 * f) * dim))
                cv.ch[i] = c
                cv.fg[i] = qc(scale(mix(col, (200, 255, 120), 0.3 * f), (0.6 + 0.4 * f) * dim))
                cv.lv[i] = 0.6
            px = x

    def draw_fan(self, cv, cx, base, r, col, dim, ph, s, nray):
        w, h = self.w, self.h
        t = self.t
        lite = mix(col, (255, 255, 255), 0.3)
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        ry = r / ASPECT
        for y in range(int(base - ry * 1.05) - 1, int(base) + 1):
            if not (0 <= y < h):
                continue
            v = (base - y) / max(1.0, ry)
            sway = math.sin(t * 0.8 + ph) * v * v * 1.2
            for x in range(int(cx - r * 1.1) - 2, int(cx + r * 1.1) + 3):
                xs = x - sway
                u = (xs + 0.5 - cx) / r
                d = math.sqrt(u * u + v * v)
                if d > 1.0 or v < 0:
                    continue
                ang = math.atan2(u, v)
                ray = abs(math.sin(ang * nray * 0.5 + noise2(x * 0.2, y * 0.4, s) * 0.6))
                ring = abs(math.sin(d * 9 + noise2(x * 0.3, y * 0.5, s + 1)))
                if ray < 0.22:
                    c = "|" if abs(ang) < 0.3 else "/" if ang > 0 else "\\"
                elif ring < 0.25:
                    c = "-" if d < 0.85 else "~"
                elif hsh(x, y, s) < 0.18:
                    c = "+"
                else:
                    if d > 0.15:
                        continue
                    c = "|"
                if 0 <= x < w:
                    i = y * w + x
                    k = 0.6 + 0.4 * (1 - d)
                    ch[i] = c
                    fg[i] = qc(scale(mix(col, lite, d * 0.6), k * dim))
                    lv[i] = 0.6

    def draw_anemone(self, cv, a, layer):
        w, h = self.w, self.h
        t = self.t
        cx, base, r = a["x"], a["y"], a["r"]
        col, tip, dim = a["col"], a["tip"], a["dim"]
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        n = a["n"]
        if layer == 0:
            # body column
            for y in range(int(base - 1), int(base) + 1):
                for x in range(int(cx - r * 0.5), int(cx + r * 0.5) + 1):
                    if 0 <= x < w and 0 <= y < h:
                        i = y * w + x
                        ch[i] = "#" if (x + y) % 2 else "%"
                        fg[i] = qc(scale(col, 0.45 * dim))
        L = a["len"]
        for k in range(n):
            if k % 2 != layer:
                continue
            u = (k + 0.5) / n * 2 - 1
            x0 = cx + u * r * 0.55
            ang = u * 1.2
            px = x0
            steps = int(L * 1.6) + 2
            for j in range(steps):
                f = j / steps
                sway = math.sin(t * 1.3 + a["ph"] + k * 0.7 - j * 0.35) * f * 1.6
                x = x0 + math.sin(ang) * f * L * 1.2 + sway
                y = base - 1.5 - f * L * math.cos(ang) / ASPECT * 1.3 - f * 1.5
                xi, yi = int(x), int(y)
                if 0 <= xi < w and 0 <= yi < h:
                    dx = x - px
                    c = "o" if j == steps - 1 else ("/" if dx > 0.35 else "\\" if dx < -0.35 else ")" if dx > 0.1 else "(" if dx < -0.1 else "|")
                    i = yi * w + xi
                    ch[i] = c
                    fg[i] = qc(scale(mix(col, tip, f ** 2), (0.55 + 0.45 * f) * dim * (0.8 + 0.2 * layer)))
                    lv[i] = 0.7
                px = x

    def draw_clown(self, cv, c):
        a, ph, sp = c
        w, h = self.w, self.h
        x = a["x"] + math.sin(ph) * a["r"] * 0.8
        y = a["y"] - 2.5 - a["len"] * 0.4 - math.cos(ph * 1.3) * a["len"] * 0.35
        face = 1 if math.cos(ph) > 0 else -1
        body = "><))>" if face > 0 else "<((<>"
        cols = [(255, 120, 20), (255, 140, 30), (255, 255, 255), (255, 130, 20), (255, 150, 40)]
        if face < 0:
            cols = cols[::-1]
        xi = int(x) - 2
        yi = int(y)
        if 0 <= yi < h:
            for k, chh in enumerate(body):
                xx = xi + k
                if 0 <= xx < w:
                    i = yi * w + xx
                    cv.ch[i] = chh
                    cv.fg[i] = qc(cols[k])
                    cv.lv[i] = 0.9

    def draw_school(self, cv, sc):
        w, h = self.w, self.h
        name, tail, body, stripe, eye = sc["sp"]
        tmpl, roles = sc["tmpl"]
        rc = {"t": tail, "b": body, "s": stripe, "e": eye}
        n = len(tmpl)
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        for f in sc["fish"]:
            x, y, vx, vy, face, ph = f
            yi = int(y)
            if not (0 <= yi < h):
                continue
            wag = math.sin(ph) > 0
            if face > 0:
                x0 = int(x) - n + 1
                s = tmpl
                r = roles
            else:
                x0 = int(x)
                s = tmpl[::-1].translate(MIRROR)
                r = roles[::-1]
            depthk = 0.75 + 0.25 * clamp(1 - abs(y - h * 0.4) / h)
            for k in range(n):
                xx = x0 + k
                if 0 <= xx < w:
                    c = s[k]
                    if n >= 5 and r[k] == "t" and wag and c in "<>":
                        c = "}" if c == ">" else "{"
                    i = yi * w + xx
                    ch[i] = c
                    fg[i] = qc(scale(rc[r[k]], depthk))
                    lv[i] = 0.9

    def draw_turtle(self, cv, tu):
        w, h = self.w, self.h
        cx, cy, d, S = tu["x"], tu["y"], tu["dir"], tu["size"]
        ph = tu["ph"]
        shell_dark = (60, 80, 40)
        shell_lit = (170, 150, 80)
        skin = (120, 170, 120)
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        a = S * 1.35
        b = max(1.5, S * 0.62)

        def put(x, y, c, col):
            xi, yi = int(x), int(y)
            if 0 <= xi < w and 0 <= yi < h:
                i = yi * w + xi
                ch[i] = c
                fg[i] = qc(col)
                lv[i] = 1.0

        # flippers first (behind shell): front long, rear short; stroke angle
        stroke = math.sin(ph)
        for length, base_off, a0, amp in ((S * 1.7, 0.5, 0.35, 0.5), (S * 0.9, -0.7, 0.5, 0.3)):
            bx = cx + d * a * base_off
            by = cy + 0.3
            ang = a0 + amp * stroke          # 0 = straight back, larger = down
            n = int(length * 1.4) + 1
            px, py = bx, by
            for k in range(n):
                f = k / max(1, n - 1)
                x = bx - d * math.cos(ang) * f * length
                y = by + math.sin(ang) * f * length / ASPECT
                col = mix((150, 200, 150), (60, 100, 70), f * 0.6)
                put(x, y, "@" if f < 0.35 else "%" if f < 0.7 else wood_glyph(x - px, y - py), col)
                if f < 0.6:
                    put(x, y + 1, "%", scale(col, 0.6))
                px, py = x, y
        # shell: a shaded dome; scute seams follow a hexagon tiling
        pat = ("__/  \\", "  \\__/")
        plate = (110, 120, 50)
        for y in range(int(cy - b) - 1, int(cy + b * 0.2) + 1):
            for x in range(int(cx - a) - 1, int(cx + a) + 2):
                u = (x + 0.5 - cx) / a
                v = (y + 0.5 - cy) / b
                if u * u + v * v > 1.0 or v > 0.2:
                    continue
                nz = math.sqrt(max(0.0, 1 - u * u - v * v))
                lt = clamp(0.25 + 0.5 * nz - 0.35 * v + 0.2 * u * d)
                if v > -0.05 and (y + 1.5 - cy) / b > 0.2:
                    put(x, y, "=" if abs(u) < 0.85 else "-", mix((120, 110, 70), (230, 210, 150), lt))
                    continue
                row = pat[(y - int(cy)) % 2]
                c = row[int(x - cx) % 6]
                if c != " " and u * u + v * v < 0.85:
                    put(x, y, c, mix((30, 34, 14), (90, 80, 30), lt))
                else:
                    g = "@" if lt > 0.72 else "%" if lt > 0.55 else "#" if lt > 0.4 else "*" if lt > 0.25 else "+"
                    put(x, y, g, mix(scale(plate, 0.6), (220, 200, 110), lt))
        # head: a rounded snout with an eye
        hx = cx + d * (a + S * 0.35)
        hy = cy - b * 0.1
        hr = max(1.5, S * 0.45)
        for y in range(int(hy - hr / ASPECT) - 1, int(hy + hr / ASPECT) + 2):
            for x in range(int(hx - hr) - 1, int(hx + hr) + 2):
                u = (x + 0.5 - hx) / hr
                v = (y + 0.5 - hy) * ASPECT / hr
                if u * u + v * v > 1:
                    continue
                lt = clamp(0.7 - 0.4 * v + 0.2 * u * d)
                put(x, y, "@" if lt > 0.65 else "%" if lt > 0.4 else "#", mix((50, 90, 60), (170, 210, 160), lt))
        put(hx + d * hr * 0.35, hy - 0.3, "°", (255, 255, 255))
        for k in range(int(S * 0.6)):
            put(cx + d * (a - 1 + k * 0.5), cy + 0.2, "=", (80, 120, 80))
