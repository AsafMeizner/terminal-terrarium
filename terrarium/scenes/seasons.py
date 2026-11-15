"""One tree through the year: blossoms, full summer green, falling autumn leaves, winter snow."""
import math

from ..engine import ASPECT, Scene, clamp, gradient, hsv, mix, noise1, noise2, scale, smoothstep
from .bonsai import TAU, Tree, draw_wood, leaf_ramp
from .sakura import _hash, edge_glyph

SEASONS = ("spring", "summer", "autumn", "winter")

SPRING_LEAF = [(30, 80, 30), (70, 150, 60), (140, 210, 100), (200, 240, 160)]
SPRING_BLOOM = [(150, 70, 110), (240, 140, 180), (255, 200, 220), (255, 245, 250)]
SUMMER_LEAF = [(8, 40, 18), (20, 90, 36), (50, 150, 50), (130, 210, 80), (210, 245, 150)]
AUTUMN = [
    [(70, 10, 8), (170, 30, 20), (235, 70, 40), (255, 150, 90)],     # red
    [(80, 30, 6), (190, 80, 16), (250, 140, 30), (255, 200, 110)],   # orange
    [(80, 56, 8), (180, 130, 20), (240, 200, 50), (255, 240, 150)],  # gold
]
BARK = [(26, 18, 14), (60, 40, 30), (104, 74, 54), (150, 112, 84), (200, 165, 130)]
BIRCH_BARK = [(40, 40, 44), (110, 110, 112), (190, 190, 186), (230, 230, 224), (250, 250, 245)]

#               sky tint          ground (dark, light)                    sky density
LOOK = {
    "spring": ((110, 160, 210), ((20, 50, 24), (90, 170, 80)), 0.9),
    "summer": ((80, 130, 210), ((14, 44, 18), (70, 150, 50)), 1.0),
    "autumn": ((200, 120, 80), ((50, 30, 14), (170, 110, 50)), 0.9),
    "winter": ((140, 160, 200), ((40, 46, 60), (200, 215, 235)), 0.8),
}


SPECIES = ("oak", "maple", "birch", "willow", "umbrella", "cherry")


def species_genome(rng, sp):
    """Growth rules for one tree, drawn from ranges typical of its species."""
    u = rng.uniform
    g = {"limbs": rng.randint(3, 5), "fan": u(0.75, 1.0), "ratio": u(0.62, 0.76), "depth": 4, "p3": u(0.15, 0.4),
         "pull": u(0.88, 0.96), "wob": u(0.05, 0.1), "split": u(0.6, 1.0), "blob": u(0.15, 0.21), "tall": u(0.85, 1.05),
         "trunk": u(0.28, 0.36), "girth": u(0.035, 0.05), "lean": u(-0.1, 0.1), "limb": u(0.24, 0.3),
         "midblob": u(0.5, 1.0), "size": u(0.72, 0.86), "weep": False}
    if sp == "maple":
        g.update(limbs=rng.randint(3, 4), fan=u(0.9, 1.15), trunk=u(0.22, 0.3), ratio=u(0.66, 0.78))
    elif sp == "birch":
        g.update(limbs=rng.randint(2, 3), fan=u(0.3, 0.5), ratio=u(0.72, 0.82), trunk=u(0.45, 0.56),
                 girth=u(0.022, 0.03), blob=u(0.1, 0.14), pull=u(0.8, 0.9), tall=u(1.1, 1.4), size=u(0.8, 0.92),
                 lean=u(-0.15, 0.15))
    elif sp == "willow":
        g.update(depth=3, fan=u(0.8, 1.1), blob=u(0.12, 0.16), weep=True, trunk=u(0.3, 0.4), girth=u(0.045, 0.06))
    elif sp == "umbrella":
        g.update(limbs=rng.randint(2, 4), fan=u(1.0, 1.3), pull=u(1.0, 1.08), depth=3, trunk=u(0.38, 0.5),
                 tall=u(0.5, 0.7), blob=u(0.16, 0.22), limb=u(0.3, 0.36), split=u(0.4, 0.7))
    elif sp == "cherry":
        g.update(fan=u(0.95, 1.2), trunk=u(0.24, 0.32), pull=u(0.95, 1.05))
    return g


class Seasons(Scene):
    name = "seasons"
    title = "Seasons"
    blurb = "one tree through the year: blossom, summer green, autumn fall, winter snow"
    tags = ("nature", "plants", "calm", "weather")
    options = {
        "length": (30.0, "seconds per season"),
        "start": ("spring", "spring, summer, autumn or winter"),
        "lock": (False, "stay in the start season"),
        "tree": ("random", "oak, maple, birch, willow, umbrella, cherry or random"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.seed = rng.randrange(1 << 15)
        start = self.opt("start")
        self.start = SEASONS.index(start) if start in SEASONS else 0
        sp = self.opt("tree")
        self.species = sp if sp in SPECIES else rng.choice(SPECIES)
        self.make_palettes()
        # land: rolling ground with a knoll (or a dip) under the tree
        self.tx = w * rng.uniform(0.32, 0.68)
        base = h * rng.uniform(0.82, 0.9)
        knoll = h * rng.uniform(-0.04, 0.12)
        kw = w * rng.uniform(0.15, 0.4)
        roll, rf = h * rng.uniform(0.0, 0.05), rng.uniform(0.02, 0.06)
        self.ground = [base + 0.5 * noise1(x * 0.06, self.seed) + roll * noise1(x * rf, self.seed + 3)
                       - knoll * math.exp(-((x - self.tx) / kw) ** 2) for x in range(w)]
        self.sky = [(x, y, 0.05 + 0.18 * (y / h) ** 2 * rng.random())
                    for y in range(int(h * 0.8)) for x in range(w)
                    if rng.random() < 0.01 + 0.07 * (y / h) ** 2 and y < self.ground[x] - 1]
        self.build_tree()
        self.snow = [0.0] * w       # snow depth on the ground, in rows
        self.litter = [0.0] * w     # fallen autumn leaves
        self.cap = 0.0              # snow on branches 0..1
        self.parts = []             # [x, y, vx, vy, phase, kind, color, life]
        self.flies = []
        self.calc_weights()

    def make_palettes(self):
        """Per-run colors: species sets the autumn mix and bark; a random tint shifts greens and skies."""
        rng = self.rng
        sp = self.species
        tint = hsv(rng.random(), 0.7, 1.0)
        tk = rng.uniform(0.0, 0.18)
        self.p_spring = [mix(c, scale(tint, sum(c) / 600), tk) for c in SPRING_LEAF]
        green = rng.choice(((0, 0, 0), (60, 60, 0), (0, 40, 60), (40, 20, 0)))   # deep, olive, blue-green, warm
        self.p_summer = [(clamp(c[0] + green[0] * i / 4, 0, 255), clamp(c[1] + green[1] * i / 4, 0, 255),
                          clamp(c[2] + green[2] * i / 4, 0, 255)) for i, c in enumerate(SUMMER_LEAF)]
        bloom = rng.choice((None, ((255, 255, 250), 0.6), ((220, 60, 140), 0.3), ((255, 180, 150), 0.3)))
        self.p_bloom = [mix(c, bloom[0], bloom[1]) for c in SPRING_BLOOM] if bloom else list(SPRING_BLOOM)
        self.bloom_amt = {"cherry": 1.0, "birch": 0.15, "willow": 0.25}.get(sp, rng.uniform(0.3, 0.8))
        self.p_autumn = AUTUMN
        mixes = {"maple": (0.65, 0.3, 0.05), "birch": (0.02, 0.18, 0.8), "willow": (0.0, 0.25, 0.75),
                 "umbrella": (0.15, 0.6, 0.25)}
        self.autumn_mix = mixes.get(sp) or (rng.random() + 0.05, rng.random() + 0.05, rng.random() + 0.05)
        self.p_bark = BIRCH_BARK if sp == "birch" else BARK
        sky_t = hsv(rng.random(), 0.5, 1.0)
        self.look = {k: (mix(v[0], sky_t, rng.uniform(0.0, 0.3)), v[1], v[2]) for k, v in LOOK.items()}

    # -- tree -------------------------------------------------------------------
    def build_tree(self):
        rng = self.rng
        w, h = self.w, self.h
        bx = self.tx + rng.uniform(-1, 1)
        by = self.ground[int(clamp(bx, 0, w - 1))] + 0.4
        g = species_genome(rng, self.species)
        self.genome = g
        hv = (by - max(2.0, h * 0.06)) * ASPECT * g["size"]
        spread = min(w * 0.42, hv * 1.0)
        tree = Tree(bx, by)
        blobs = []

        def steer_to(target, wob=0.05):
            return lambda f, a, x, yv: a + (target - a) * 0.15 + rng.gauss(0, wob)

        trunk_len = hv * g["trunk"]
        r0 = clamp(hv * g["girth"], 0.8, 4.5)
        lean = g["lean"]
        trunk = tree.walk(bx, 0.0, lean, trunk_len, r0, r0 * 0.65, 0.0, steer_to(lean * 0.6, 0.03), 0, 0.9)

        def weep(x, yv, ang, t, length):
            sd = 1 if ang >= 0 else -1
            pts = tree.walk(x, yv, ang, length, 0.45, 0.4, t,
                            lambda f, a, x_, y_: a + (sd * 2.95 - a) * 0.25 + rng.gauss(0, 0.04), 4)
            for k in range(1, len(pts), max(2, len(pts) // 6)):
                blobs.append((pts[k][0], by - pts[k][1] / ASPECT, spread * g["blob"] * rng.uniform(0.45, 0.65), 1.7))

        def branch(x, yv, ang, length, r, depth, t):
            pts = tree.walk(x, yv, ang, length, r, max(0.4, r * 0.62), t, steer_to(ang * g["pull"], g["wob"]), depth)
            ex, eyv, er, et = pts[-1]
            if depth >= 2 and rng.random() < g["midblob"]:
                mx, myv, _, _ = pts[len(pts) // 2]
                blobs.append((mx, by - myv / ASPECT, spread * g["blob"] * rng.uniform(0.7, 0.85), g["tall"]))
            if depth >= g["depth"] or length < 2.5:
                if g["weep"]:
                    weep(ex, eyv, ang, et, hv * rng.uniform(0.3, 0.5))
                blobs.append((ex, by - eyv / ASPECT, spread * g["blob"] * rng.uniform(0.9, 1.25), g["tall"]))
                return
            kids = 3 if rng.random() < g["p3"] else 2
            for k in range(kids):
                da = (k / (kids - 1) - 0.5) * g["split"] * rng.uniform(0.75, 1.2)
                branch(ex, eyv, clamp(ang + da, -1.45, 1.45), length * g["ratio"] * rng.uniform(0.9, 1.1),
                       er * 0.72, depth + 1, et)

        x, yv, r, t = trunk[-1]
        limbs = g["limbs"]
        for k in range(limbs):
            a = (-1 + 2 * (k + rng.uniform(0.3, 0.7)) / limbs) * g["fan"] * rng.uniform(0.85, 1.05)
            branch(x, yv, a, hv * g["limb"] * rng.uniform(0.9, 1.1), r * 0.72, 1, t)
        main = sum(1 for b in blobs if b[3] != 1.7)
        if 0 < main < 10:   # sparse rule sets get fuller clusters
            k = min(1.6, (10 / main) ** 0.5)
            blobs = [(a, b, c * k, d) for a, b, c, d in blobs]
        tree.finish(1.0, thicken=False)
        self.tree = tree
        self.bake_crown(blobs)
        # snow caps: cells just above wood that is not already covered by wood
        wood = {(c[0], c[1]): c[2] for c in tree.wood}
        caps = []
        for (x, y), ch in wood.items():
            if (x, y - 1) not in wood and ch != "|" and 0 <= y - 1:
                caps.append((x, y - 1, _hash(x, y)))
            elif ch == "|" and (x, y - 1) not in wood and 0 <= y - 1:
                caps.append((x, y - 1, _hash(x, y) * 0.45 + 0.55))
        self.caps = caps

    def bake_crown(self, blobs):
        w, h = self.w, self.h
        lx, ly, lz = -0.55, -0.6, 0.58
        best = {}
        for bx, by, br, tall in blobs:
            ry = br / ASPECT * 0.9 * tall
            for y in range(int(by - ry * 1.3) - 1, int(by + ry * 1.3) + 2):
                if y < 0 or y >= h:
                    continue
                for x in range(int(bx - br * 1.3) - 1, int(bx + br * 1.3) + 2):
                    if x < 0 or x >= w:
                        continue
                    u = (x + 0.5 - bx) / br
                    v = (y + 0.5 - by) / ry
                    d2 = u * u + v * v
                    edge = math.sqrt(d2) + 0.3 * noise2(x * 0.3, y * 0.6, self.seed + 5)
                    if edge > 1.05:
                        continue
                    nz = math.sqrt(max(0.0, 1 - min(1.0, d2)))
                    z = nz * br + by * 0.3
                    old = best.get((x, y))
                    if old is not None and old[0] >= z:
                        continue
                    best[(x, y)] = (z, edge, clamp(u * lx + v * ly + nz * lz))
        rng = self.rng
        cells = []
        for (x, y), (z, edge, lam) in best.items():
            tex = noise2(x * 0.85, y * 1.6, self.seed + 9)
            core = clamp((1.0 - edge) / 0.25)
            shade = clamp(0.22 + 0.62 * lam + 0.18 * tex)
            level = clamp(0.4 + 0.42 * core + 0.26 * tex + 0.12 * lam)
            # r: the coverage at which this leaf appears; inner cells leaf out first
            cl = (noise2(x * 0.22, y * 0.45, self.seed + 11) + 1) * 0.5
            r = clamp(0.55 * cl + 0.25 * edge + 0.2 * rng.random())
            hue = rng.choices((0, 1, 2), self.autumn_mix)[0]
            cells.append([x, y, level, shade, r, rng.random(), hue, rng.random()])
        self.crown = cells

    # -- season clock ------------------------------------------------------------
    def calc_weights(self):
        L = max(3.0, self.opt("length"))
        if self.opt("lock"):
            self.k, self.f, self.b = self.start, 0.5, 0.0
        else:
            p = self.t / L + self.start
            self.k = int(p) % 4
            self.f = p - int(p)
            self.b = smoothstep(0.78, 1.0, self.f)   # crossfade into the next season
        w = [0.0] * 4
        w[self.k] += 1 - self.b
        w[(self.k + 1) % 4] += self.b
        self.wts = w

    def coverage(self):
        w = self.wts
        f = self.f
        k = self.k
        def cov(i, ff):
            return (0.25 + 0.55 * ff, 1.0, 1.0 - 0.72 * smoothstep(0.15, 1.0, ff), 0.0)[i]
        a = cov(k, f)
        b = cov((k + 1) % 4, 0.0)
        return a * (1 - self.b) + b * self.b

    # -- simulation --------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        self.calc_weights()
        rng = self.rng
        w, h = self.w, self.h
        sp, su, au, wi = self.wts
        t = self.t
        wind = 0.6 * math.sin(t * 0.21) + 0.5 * noise1(t * 0.3, self.seed)
        self.wind = wind
        area = w * h / 3000
        # spawn particles
        rates = (("petal", 3.0 * sp * (self.k == 0)), ("leaf", 7.0 * au), ("snow", 16.0 * area * wi * self.density))
        for kind, rate in rates:
            n = rate * dt
            while n > 0:
                if rng.random() < n:
                    self.parts.append(self.spawn(kind))
                n -= 1
        target = int(14 * area * su * self.density)
        if len(self.flies) < target and rng.random() < dt * 3:
            self.flies.append([rng.uniform(0, w), rng.uniform(h * 0.35, self.ground[0] - 1), rng.uniform(0, TAU),
                               rng.uniform(0.5, 1.0)])
        elif len(self.flies) > target and self.flies and rng.random() < dt * 3:
            self.flies.pop()
        for fl in self.flies:
            fl[2] += dt * fl[3]
            fl[0] += math.cos(fl[2] * 1.3) * dt * 1.2 + wind * dt * 0.3
            fl[1] += math.sin(fl[2] * 0.9) * dt * 0.5
            fl[0] %= w
            fl[1] = clamp(fl[1], h * 0.3, h * 0.84)
        # move particles
        g = self.ground
        keep = []
        for p in self.parts:
            x, y, vx, vy, ph, kind, col, life = p
            if kind == "snow":
                p[0] = x + (wind * 1.2 + 0.4 * math.sin(ph + t)) * dt
                p[1] = y + vy * dt
            else:
                p[4] = ph + dt * 3
                p[0] = x + (wind * 2.0 + math.sin(p[4]) * 1.8) * dt
                p[1] = y + vy * (0.7 + 0.5 * math.cos(p[4])) * dt
            xi = int(p[0]) % w
            ground = g[xi] - (self.snow[xi] if kind == "snow" else 0)
            if p[1] >= ground:
                if kind == "snow":
                    if self.snow[xi] < 2.2:
                        self.snow[xi] += 0.14
                elif kind == "leaf":
                    self.litter[xi] = min(1.5, self.litter[xi] + 0.25)
                continue
            if -3 < p[0] < w + 3:
                keep.append(p)
        self.parts = keep
        # snow melts in spring and summer; litter rots away under the snow
        melt = dt * (0.08 * (sp + su) + 0.01)
        rot = dt * (0.02 + 0.08 * wi + 0.1 * sp)
        for i in range(w):
            if self.snow[i] > 0:
                self.snow[i] = max(0.0, self.snow[i] - melt * (1 + self.snow[i]))
            if self.litter[i] > 0:
                self.litter[i] = max(0.0, self.litter[i] - rot)
        # smooth snow so it lies in drifts rather than columns
        if wi > 0.05:
            s = self.snow
            for i in range(1, w - 1):
                avg = (s[i - 1] + s[i + 1]) * 0.5
                s[i] += (avg - s[i]) * min(1.0, dt * 2)
        target_cap = wi
        self.cap += (target_cap - self.cap) * min(1.0, dt * 0.12)

    def spawn(self, kind):
        rng = self.rng
        if kind == "snow":
            return [rng.uniform(-5, self.w + 5), rng.uniform(-2, 0), 0, rng.uniform(1.0, 2.6), rng.uniform(0, TAU),
                    kind, rng.random(), 0]
        cells = self.crown
        x, y = rng.uniform(0, self.w), 0
        if cells:
            c = rng.choice(cells)
            x, y = c[0], c[1]
        if kind == "petal":
            col = rng.choice(self.p_bloom[1:])
        else:
            col = gradient(rng.choice(self.p_autumn), rng.uniform(0.35, 0.9))
        return [x, y, 0, rng.uniform(1.0, 1.8), rng.uniform(0, TAU), kind, col, 0]

    # -- drawing ----------------------------------------------------------------
    def blend(self, key_fn):
        w = self.wts
        out = (0.0, 0.0, 0.0)
        for i in range(4):
            if w[i] > 0:
                c = key_fn(SEASONS[i])
                out = (out[0] + c[0] * w[i], out[1] + c[1] * w[i], out[2] + c[2] * w[i])
        return out

    def draw(self, cv):
        t = self.t
        w, h = self.w, self.h
        put = cv.put
        sp, su, au, wi = self.wts
        sky = self.blend(lambda s: self.look[s][0])
        for x, y, lv in self.sky:
            cv.shade(x, y, lv, sky)
        # ground
        gd = self.blend(lambda s: self.look[s][1][0])
        gl = self.blend(lambda s: self.look[s][1][1])
        for x in range(w):
            gy = self.ground[x]
            ch, iy = edge_glyph(gy, self.ground[max(0, x - 1)], self.ground[min(w - 1, x + 1)])
            put(x, iy, ch, gl)
            for y in range(iy + 1, h):
                dd = (y - gy) / max(1.0, h - gy)
                r = _hash(x, y)
                if r < 0.8 - 0.4 * dd:
                    k = _hash(y * 3, x)
                    c = "'" if k < 0.35 else '"' if k < 0.5 else "," if k < 0.75 else "."
                    put(x, y, c, scale(mix(gl, gd, clamp(dd * 1.6 + 0.2)), 0.85 - 0.4 * dd))
        # leaf litter
        for x, lv in enumerate(self.litter):
            if lv > 0.08:
                col = gradient(self.p_autumn[x % 3], 0.3 + 0.4 * _hash(x, 5))
                put(x, int(self.ground[x]), "," if lv < 0.5 else "o" if x % 3 else "%", scale(col, 0.4 + 0.5 * min(1, lv)))
        draw_wood(cv, self.tree, bark=self.p_bark, lo=0.12, hi=0.7)
        self.draw_caps(cv)
        self.draw_crown(cv)
        self.draw_snow_ground(cv)
        for fx, fy, ph, sp_ in self.flies:
            glow = 0.5 + 0.5 * math.sin(ph * 3)
            if glow > 0.25:
                put(fx, fy, "*" if glow > 0.8 else ".", scale((220, 255, 120), 0.3 + 0.7 * glow))
        for x, y, vx, vy, ph, kind, col, life in self.parts:
            if kind == "snow":
                near = col
                ch = "*" if near > 0.93 else "·" if near > 0.7 else "."
                put(x, y, ch, scale((235, 240, 255), 0.45 + 0.55 * near))
            else:
                ch = "`',." [int(ph) % 4] if kind == "petal" else "~,'`"[int(ph) % 4]
                put(x, y, ch, col)

    def draw_caps(self, cv):
        if self.cap < 0.03:
            return
        put = cv.put
        cap = self.cap
        for x, y, r in self.caps:
            if r < cap:
                put(x, y, "_" if r < 0.5 else ".", scale((235, 242, 255), 0.5 + 0.5 * clamp((cap - r) * 4)))

    def draw_snow_ground(self, cv):
        put = cv.put
        s = self.snow
        w = self.w
        for x in range(w):
            d = s[x]
            if d < 0.05:
                continue
            g = self.ground[x]
            top = g - d
            ch, iy = edge_glyph(top, self.ground[max(0, x - 1)] - s[max(0, x - 1)],
                                self.ground[min(w - 1, x + 1)] - s[min(w - 1, x + 1)])
            put(x, iy, ch, scale((235, 242, 255), 0.6 + 0.4 * min(1, d)))
            for y in range(iy + 1, int(g) + 1):
                put(x, y, ":" if (x + y) % 3 == 0 else ".", (180, 195, 225))

    def draw_crown(self, cv):
        cov = self.coverage()
        if cov <= 0.005:
            return
        ramp = leaf_ramp(cv)
        nr = len(ramp) - 1
        put = cv.put
        t = self.t
        sp, su, au, wi = self.wts
        wind = self.wind
        bloom = ((0.8 - 0.55 * self.f) if self.k == 0 else 0.8) * self.bloom_amt
        for x, y, lv, sh, r, br, hue, ph in self.crown:
            vis = clamp((cov - r) * 8)
            if vis <= 0:
                continue
            ripple = math.sin(x * 0.2 - t * 1.4 + y * 0.3)
            sway = (wind * 0.5 + 0.3 * math.sin(t * 1.1 + y * 0.3)) * clamp((self.ground[0] - y) / self.h)
            v = lv * vis * (0.92 + 0.1 * ripple)
            idx = int(clamp(v) * nr + 0.5)
            if idx <= 0:
                continue
            s = sh * (0.9 + 0.1 * ripple)
            cr = cg = cb = 0.0
            for wt, c in ((sp, gradient(self.p_bloom, 0.3 + 0.7 * s) if br < bloom else gradient(self.p_spring, s)) if sp else (0, None),
                          (su, gradient(self.p_summer, s)) if su else (0, None),
                          (au, gradient(self.p_autumn[hue], s)) if au else (0, None),
                          (wi, gradient(self.p_autumn[1], s * 0.5)) if wi else (0, None)):
                if wt:
                    cr += c[0] * wt
                    cg += c[1] * wt
                    cb += c[2] * wt
            col = (cr, cg, cb)
            put(int(x + sway), y, ramp[idx], scale(col, 0.45 + 0.55 * clamp(v)))
