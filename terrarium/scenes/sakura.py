"""A cherry tree on a hill at dusk, shedding petals into gusty wind."""
import math

from ..engine import ASPECT, Scene, clamp, gradient, mix, noise1, noise2, scale
from .bonsai import TAU, Tree, draw_wood, leaf_ramp, wood_glyph

TIMES = {
    "dusk": {
        "sky": [(14, 10, 40), (60, 26, 84), (170, 60, 100), (255, 120, 90), (255, 190, 120)],
        "stars": 0.5, "orb": "sun", "orb_pos": (0.78, None), "orb_col": [(255, 110, 70), (255, 200, 120), (255, 245, 200)],
        "light": (0.75, -0.25), "tint": (255, 170, 130), "tint_k": 0.35,
        "bloom": [(52, 14, 50), (140, 46, 104), (226, 104, 156), (255, 168, 196), (255, 226, 228)],
        "hill": [(10, 6, 18), (34, 18, 44), (80, 40, 76)], "rim": (255, 130, 120),
        "ridge": [(26, 14, 44), (66, 32, 80)], "bark": [(14, 8, 12), (40, 22, 26), (86, 52, 52), (150, 96, 90), (220, 150, 130)],
        "petal": [(255, 150, 190), (255, 196, 214), (255, 228, 236), (240, 120, 170)],
    },
    "night": {
        "sky": [(4, 6, 20), (10, 14, 40), (22, 30, 70), (40, 56, 110), (70, 90, 150)],
        "stars": 1.0, "orb": "moon", "orb_pos": (0.76, 0.2), "orb_col": [(80, 90, 140), (190, 205, 245), (245, 248, 255)],
        "light": (0.6, -0.6), "tint": (170, 190, 255), "tint_k": 0.35,
        "bloom": [(36, 16, 52), (100, 52, 120), (190, 120, 190), (240, 186, 232), (255, 236, 250)],
        "hill": [(4, 6, 12), (14, 18, 36), (40, 50, 90)], "rim": (150, 170, 240),
        "ridge": [(10, 12, 30), (30, 36, 70)], "bark": [(8, 8, 14), (26, 22, 34), (60, 52, 70), (110, 100, 130), (170, 165, 200)],
        "petal": [(240, 190, 240), (255, 220, 250), (220, 200, 255), (255, 240, 255)],
    },
    "day": {
        "sky": [(30, 70, 130), (60, 120, 190), (110, 170, 230), (170, 210, 250), (220, 240, 255)],
        "stars": 0.0, "orb": "sun", "orb_pos": (0.82, 0.16), "orb_col": [(255, 220, 120), (255, 245, 190), (255, 255, 240)],
        "light": (0.5, -0.8), "tint": (255, 250, 230), "tint_k": 0.3,
        "bloom": [(90, 30, 70), (190, 80, 130), (250, 140, 180), (255, 196, 216), (255, 240, 244)],
        "hill": [(14, 40, 18), (40, 96, 40), (110, 170, 70)], "rim": (200, 250, 140),
        "ridge": [(40, 70, 110), (90, 130, 170)], "bark": [(26, 16, 12), (60, 40, 30), (110, 76, 56), (170, 124, 92), (225, 185, 145)],
        "petal": [(255, 160, 200), (255, 200, 220), (255, 235, 240), (250, 130, 180)],
    },
}

PETAL_GLYPHS = "`',.'`*,"

BLOOM_VARIANTS = (None, ((255, 246, 250), 0.35), ((210, 30, 120), 0.25), ((255, 160, 120), 0.22),
                  ((200, 120, 255), 0.18))


def vary_palette(base, rng):
    """Copy a time-of-day palette with a random sky tint and blossom variety (pale, deep, peach, lilac)."""
    from ..engine import hsv
    pal = dict(base)
    tint = hsv(rng.random(), 0.6, 1.0)
    k = rng.uniform(0.08, 0.25)
    pal["sky"] = [mix(c, scale(tint, sum(c) / 765 + 0.1), k) for c in base["sky"]]
    pal["ridge"] = [mix(c, scale(tint, 0.25), k * 0.6) for c in base["ridge"]]
    v = rng.choice(BLOOM_VARIANTS)
    if v:
        pal["bloom"] = [mix(c, v[0], v[1] * (0.4 + 0.6 * i / 4)) for i, c in enumerate(base["bloom"])]
        pal["petal"] = [mix(c, v[0], v[1]) for c in base["petal"]]
    return pal


def _hash(x, y):
    n = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 65535.0


DISC = "█▀▄"   # full, upper half, lower half block


def disc_glyph(x, y, cx, cy, r):
    """Half-block glyph for a disc of radius r (x cells) at (cx, cy): doubles vertical resolution.
    Returns (glyph or None, normalized distance of the cell centre)."""
    dx = (x + 0.5 - cx) / r
    dx2 = dx * dx
    dt = (y + 0.25 - cy) * ASPECT / r
    db = (y + 0.75 - cy) * ASPECT / r
    top = dx2 + dt * dt <= 1.0
    bot = dx2 + db * db <= 1.0
    d = math.sqrt(dx2 + ((y + 0.5 - cy) * ASPECT / r) ** 2)
    if top and bot:
        return DISC[0], d
    if top:
        return DISC[1], d
    if bot:
        return DISC[2], d
    return None, d


def edge_glyph(y, yl, yr):
    """A glyph tracing a surface at fractional row y (slope from neighbours). Returns (ch, row)."""
    iy = int(y)
    slope = (yr - yl) * 0.5
    if slope > 0.75:
        return "\\", iy
    if slope < -0.75:
        return "/", iy
    f = y - iy
    return ("'" if f < 0.3 else "-" if f < 0.62 else "_"), iy


class Sakura(Scene):
    name = "sakura"
    title = "Sakura"
    blurb = "a cherry tree on a hill at dusk, petals swirling in gusty wind"
    tags = ("nature", "plants", "japan", "calm", "wind")
    interactions = "sweep the pointer to blow the petals around, click to shake the tree"
    options = {
        "petals": (1.0, "amount of drifting petals"),
        "wind": (1.0, "wind strength"),
        "time": ("random", "dusk, night, day or random"),
        "shape": ("random", "spreading, upright, wide, weeping or random"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        tod = self.opt("time")
        if tod not in TIMES:
            tod = rng.choices(("dusk", "night", "day"), (0.45, 0.3, 0.25))[0]
        self.tod = tod
        self.pal = vary_palette(TIMES[tod], rng)
        self.seed = rng.randrange(1 << 15)
        self.wdir = rng.choice((-1, 1))
        # composition: the tree stands on one side, the sun or moon hangs over the other
        side = rng.choice((-1, 1))
        self.hx = w * (0.5 + side * rng.uniform(0.04, 0.22))
        self.orb_x = w * (0.5 - side * rng.uniform(0.14, 0.36))
        lx, ly = self.pal["light"]
        self.pal["light"] = (abs(lx) * (1 if self.orb_x > self.hx else -1), ly)
        # terrain: a hill under the tree, maybe a second knoll, a far ridge, maybe a lone peak
        base = h * rng.uniform(0.86, 0.94)
        top = h * rng.uniform(0.6, 0.76)
        hw = w * rng.uniform(0.2, 0.42)
        kx, kw, kh = w * rng.random(), w * rng.uniform(0.1, 0.25), h * rng.uniform(0.0, 0.1)
        self.hill = [base - (base - top) * math.exp(-((x - self.hx) / hw) ** 2)
                     - kh * math.exp(-((x - kx) / kw) ** 2)
                     + 0.25 * noise1(x * 0.05, self.seed) for x in range(w)]
        ox = self.orb_x
        rb, ra, rf = h * rng.uniform(0.52, 0.64), h * rng.uniform(0.03, 0.11), rng.uniform(0.015, 0.05)
        dip = h * 0.06 if tod == "dusk" else 0.0
        peak = rng.random() < 0.4
        px, pw, phh = w * rng.uniform(0.15, 0.85), w * rng.uniform(0.12, 0.22), h * rng.uniform(0.12, 0.22)
        self.ridge = []
        for x in range(w):
            y = rb + ra * noise1(x * rf, self.seed + 1) + h * 0.012 * noise1(x * 0.07, self.seed + 2)                 + dip * math.exp(-((x - ox) / (w * 0.12)) ** 2)
            if peak:   # a lone volcano-like cone with a flattened top
                c = clamp(1 - abs(x - px) / pw)
                y = min(y, rb + ra - phh * min(0.85, c ** 1.4) / 0.85)
            self.ridge.append(y)
        self.build_sky()
        self.build_tree()
        self.pile = [0.0] * w
        n = int(self.count(160) * max(0.0, self.opt("petals")))
        self.petals = [self.spawn(initial=True) for _ in range(n)]
        self.gust = 0.0
        self.flurry = []        # extra petals shaken loose by a click; they don't respawn
        self.shake = 0.0        # 1 right after a click, decays: the canopy trembles
        self.last_ptr = None
        self.pvel = (0.0, 0.0)  # smoothed pointer velocity (cells/s): moving it is the wind

    def on_click(self, x, y):
        rng = self.rng
        self.shake = 1.0
        if not self.canopy:
            return
        x = x if x == x else self.hx
        y = y if y == y else self.h / 2
        near = [c for c in self.canopy if abs(c[0] - x) < 12 and abs(c[1] - y) < 6]
        src = near if len(near) >= 10 else self.canopy
        for _ in range(rng.randint(130, 170)):
            px, py, *_ = rng.choice(src)
            pt = self.spawn()
            pt[0], pt[1] = px + rng.uniform(-0.5, 0.5), py + rng.uniform(-0.5, 0.5)
            a = rng.uniform(0, TAU)
            sp = rng.uniform(4.0, 14.0)
            pt[2], pt[3] = math.cos(a) * sp + self.wdir * 2.0, abs(math.sin(a)) * sp * 0.3 + 1.0
            pt[6] = mix(pt[6], (255, 250, 252), 0.45)    # fresh petals catch the light
            pt[7] = 1.25
            self.flurry.append(pt)
        del self.flurry[:-500]

    # -- static layers --------------------------------------------------------------
    def build_sky(self):
        rng = self.rng
        w, h = self.w, self.h
        pal = self.pal
        self.sky = []
        self.stars = []
        for y in range(h):
            for x in range(w):
                if y >= self.ridge[x]:
                    continue
                f = clamp(y / max(1.0, self.ridge[x]))          # 0 top .. 1 horizon
                r = rng.random()
                dens = 0.01 + 0.12 * f ** 2.5
                if r < dens:
                    lvl = 0.06 + 0.22 * f ** 1.5 + 0.06 * rng.random()
                    self.sky.append((x, y, lvl, gradient(pal["sky"], f ** 1.2)))
                elif r > 1 - 0.012 * pal["stars"] * (1 - f) ** 1.5:
                    self.stars.append((x, y, rng.uniform(0.3, 1.0), rng.uniform(0, TAU)))
        oy = None if self.tod == "dusk" else rng.uniform(0.1, 0.3)
        self.orb_r = clamp(h * rng.uniform(0.13, 0.2), 3.0, 11.0)
        self.orb_y = h * (oy or 0)
        if oy is None:
            lo = min(self.ridge[int(clamp(x, 0, w - 1))] for x in range(int(self.orb_x - self.orb_r), int(self.orb_x + self.orb_r) + 1))
            self.orb_y = int(lo - self.orb_r / ASPECT - 0.6) + 0.5
        # long thin clouds in the lower sky, lit by the orb
        self.clouds = []
        self.cloud_cut = rng.uniform(0.3, 0.6)
        for y in range(int(h * 0.12), int(h * 0.62)):
            for x in range(w):
                if y >= self.ridge[x] - 1:
                    continue
                n = noise2(x * 0.025, y * 0.45, self.seed + 21) + 0.35 * noise2(x * 0.1, y * 0.9, self.seed + 22)
                if n > self.cloud_cut:
                    near = math.exp(-((x - self.orb_x) / (w * 0.35)) ** 2 - ((y - self.orb_y) / (h * 0.4)) ** 2)
                    self.clouds.append((x, y, clamp((n - self.cloud_cut) * 3), near))
        self.bake_land()

    def build_tree(self):
        """Grow the cherry from a random rule set: shape family, limb count, fork odds, angles,
        length ratio, depth, cluster size. Weeping trees hang curtains of blossom."""
        rng = self.rng
        w, h = self.w, self.h
        shape = self.opt("shape")
        if shape not in ("spreading", "upright", "wide", "weeping"):
            shape = rng.choice(("spreading", "spreading", "upright", "wide", "weeping"))
        self.shape = shape
        bx = self.hx
        by = self.hill[int(clamp(bx, 0, w - 1))] + 0.5
        rows = by - max(2.0, h * 0.06)
        hv = rows * ASPECT * rng.uniform(0.62, 0.84)
        spread = min(w * 0.5, hv * 1.25)
        g = {
            "limbs": rng.randint(2, 5), "fan": {"spreading": rng.uniform(0.9, 1.2), "upright": rng.uniform(0.45, 0.75),
                                                "wide": rng.uniform(1.15, 1.4), "weeping": rng.uniform(0.7, 1.1)}[shape],
            "p3": rng.uniform(0.1, 0.5), "ratio": rng.uniform(0.6, 0.8), "depth": rng.randint(2, 4),
            "pull": rng.uniform(0.96, 1.15) if shape != "upright" else rng.uniform(0.8, 0.95),
            "blob": rng.uniform(0.13, 0.19), "split": rng.uniform(0.55, 1.15), "wob": rng.uniform(0.04, 0.1),
            "trunk": rng.uniform(0.22, 0.38) if shape != "upright" else rng.uniform(0.32, 0.44),
            "girth": rng.uniform(0.035, 0.055), "lean": rng.uniform(-0.25, 0.25), "midblob": rng.uniform(0.3, 1.0),
        }
        if shape == "weeping":
            g["depth"] = min(g["depth"], 3)
            g["blob"] *= 0.85
        self.genome = g
        tree = Tree(bx, by)
        blobs = []
        trunk_len = hv * g["trunk"]
        r0 = clamp(hv * g["girth"], 0.8, 5.0)
        lean = g["lean"]

        def steer_to(target, wob=0.05):
            return lambda f, a, x, yv: a + (target - a) * 0.12 + rng.gauss(0, wob)

        trunk = tree.walk(bx, 0.0, lean, trunk_len, r0, r0 * 0.7, 0.0, steer_to(lean * 0.5, 0.03), 0, 0.8)

        def weep(x, yv, ang, t, length):
            """A hanging strand: arcs outward then falls, beaded with small clusters."""
            s = 1 if ang >= 0 else -1
            pts = tree.walk(x, yv, ang, length, 0.45, 0.4, t,
                            lambda f, a, x_, y_: a + (s * 2.95 - a) * 0.22 + rng.gauss(0, 0.04), 4)
            for k in range(2, len(pts), max(2, len(pts) // 6)):
                px, pyv = pts[k][0], pts[k][1]
                blobs.append([px, by - pyv / ASPECT, spread * g["blob"] * rng.uniform(0.6, 0.85), rng.random(), 1.6])

        def branch(x, yv, ang, length, r, depth, t):
            pts = tree.walk(x, yv, ang, length, r, max(0.4, r * 0.6), t, steer_to(ang * g["pull"], g["wob"]), depth)
            ex, eyv, er, et = pts[-1]
            if depth >= g["depth"] or length < 3:
                if shape == "weeping":
                    weep(ex, eyv, ang, et, hv * rng.uniform(0.25, 0.45))
                    if rng.random() < 0.6:
                        weep(ex, eyv, -ang * 0.4, et, hv * rng.uniform(0.18, 0.35))
                br = spread * g["blob"] * rng.uniform(0.85, 1.25)
                blobs.append([ex, by - eyv / ASPECT, br, rng.random(), 1.0])
                return
            if depth >= 2 and rng.random() < g["midblob"]:   # clusters along outer limbs keep the dome full
                mx, myv, _, _ = pts[len(pts) // 2]
                blobs.append([mx, by - myv / ASPECT, spread * g["blob"] * rng.uniform(0.7, 0.95), rng.random(), 1.0])
            kids = 3 if rng.random() < g["p3"] else 2
            for k in range(kids):
                da = (k / (kids - 1) - 0.5) * g["split"] * rng.uniform(0.75, 1.15)
                na = clamp(ang + da, -1.5, 1.5)
                branch(ex, eyv, na, length * g["ratio"] * rng.uniform(0.9, 1.1), er * 0.7, depth + 1, et)

        x, yv, r, t = trunk[-1]
        limbs = g["limbs"]
        scale_len = {2: 1.15, 3: 1.0, 4: 0.92, 5: 0.85}[limbs] * (0.78 / max(0.6, g["ratio"])) ** 0.5
        for k in range(limbs):
            a = (-1.0 + 2.0 * (k + rng.uniform(0.3, 0.7)) / limbs) * g["fan"] * rng.uniform(0.85, 1.05)
            branch(x, yv, a, hv * rng.uniform(0.25, 0.33) * (1.1 - 0.2 * abs(a)) * scale_len, r * 0.7, 1, t)
        # sparse rule sets get fuller clusters so every tree still reads as a cloud of blossom
        main = sum(1 for b in blobs if b[4] == 1.0)
        if 0 < main < 12:
            k = min(1.6, (12 / main) ** 0.5)
            for b in blobs:
                b[2] *= k
        tree.finish(1.0, thicken=False)
        self.tree = tree
        self.bake_canopy(blobs)

    def bake_canopy(self, blobs):
        """Union of round blossom clusters, each shaded like a soft sphere lit by the sky."""
        w, h = self.w, self.h
        lx, ly = self.pal["light"]
        lz = 0.55
        ln = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / ln, ly / ln, lz / ln
        best = {}
        for bx, by, br, depth, tall in blobs:
            ry = br / ASPECT * 0.9 * tall
            for y in range(int(by - ry * 1.3) - 1, int(by + ry * 1.3) + 2):
                if y < 0 or y >= h:
                    continue
                for x in range(int(bx - br * 1.3) - 1, int(bx + br * 1.3) + 2):
                    if x < 0 or x >= w:
                        continue
                    u = (x + 0.5 - bx) / br
                    v = (y + 0.5 - by) / ry
                    n = noise2(x * 0.28, y * 0.55, self.seed + 5)
                    d2 = u * u + v * v
                    edge = math.sqrt(d2) + 0.32 * n
                    if edge > 1.15:
                        continue
                    nz = math.sqrt(max(0.0, 1 - min(1.0, d2)))
                    z = depth * 0.6 + nz * br * 0.05 + (y / h) * 0.6
                    old = best.get((x, y))
                    if old is not None and old[0] >= z:
                        continue
                    lam = clamp(u * lx + v * ly + nz * lz)
                    best[(x, y)] = (z, edge, lam, depth, v)
        cells = []
        bmin = min((b[1] for b in blobs), default=0)
        if not blobs:
            self.canopy, self.canopy_top = [], 0
            return
        for (x, y), (z, edge, lam, depth, v) in best.items():
            tex = noise2(x * 0.85, y * 1.6, self.seed + 9)
            if edge > 1.0:
                cells.append((x, y, 0.16 * (1.15 - edge) / 0.15, 0.45, 0.0, abs(x - self.hx)))
                continue
            core = clamp((1.0 - edge) / 0.25)
            shade = clamp(0.3 + 0.55 * lam + 0.16 * tex - 0.18 * (1 - depth))
            level = clamp(0.42 + 0.4 * core + 0.28 * tex + 0.15 * lam)
            hot = clamp((lam - 0.62) * 2.5) * clamp(tex + 0.6)   # sun-kissed rim
            cells.append((x, y, level, shade, hot, abs(x - self.hx)))
        self.canopy = cells
        self.canopy_top = bmin

    # -- petals -------------------------------------------------------------------
    def spawn(self, initial=False):
        rng = self.rng
        if self.canopy and rng.random() < 0.8:
            x, y, *_ = rng.choice(self.canopy)
            x += rng.uniform(-0.5, 0.5)
            y += rng.uniform(-0.5, 0.5)
        else:
            x = (rng.uniform(-3, 0) if self.wdir > 0 else rng.uniform(self.w, self.w + 3))
            y = rng.uniform(0, self.h * 0.7)
        if initial:
            x = rng.uniform(0, self.w)
            y = rng.uniform(0, self.h * 0.8)
        return [x, y, 0.0, 0.0, rng.uniform(0, TAU), rng.uniform(2, 6), rng.choice(self.pal["petal"]),
                rng.uniform(0.6, 1.0)]

    def update(self, dt):
        super().update(dt)
        t = self.t
        W = max(0.0, self.opt("wind"))
        # gusts: slow noise mapped so calm spells and strong blasts alternate
        g = noise1(t * 0.18, self.seed + 4) * 0.5 + 0.5
        self.gust = clamp((g - 0.35) * 1.8) ** 1.5
        base = W * (1.2 + 5.0 * self.gust) * self.wdir
        # the pointer: sweeping it is a breeze that drags nearby petals along
        ptr = self.pointer
        if ptr is not None and self.last_ptr is not None and dt > 0:
            vx = clamp((ptr[0] - self.last_ptr[0]) / dt, -60, 60)
            vy = clamp((ptr[1] - self.last_ptr[1]) / dt, -30, 30)
        else:
            vx = vy = 0.0
        self.last_ptr = ptr
        k = min(1.0, dt * 5.0)
        self.pvel = (self.pvel[0] + (vx - self.pvel[0]) * k, self.pvel[1] + (vy - self.pvel[1]) * k)
        self.shake = max(0.0, self.shake - dt * 0.9)
        self.petals = self.step_petals(self.petals, dt, base, W, True, 1.6, 0.0)
        self.flurry = self.step_petals(self.flurry, dt, base, W, False, 0.45, 1.6)
        w = self.w
        pile = self.pile
        # wind slowly scatters the pile so it never grows without bound
        k = dt * 0.015 * (1 + 3 * self.gust * W)
        for i in range(w):
            if pile[i] > 0:
                pile[i] = max(0.0, pile[i] - k * pile[i])

    def step_petals(self, petals, dt, base, W, respawn, follow, sink):
        t = self.t
        w, h = self.w, self.h
        s = self.seed
        hill = self.hill
        pile = self.pile
        ptr = self.pointer
        pvx, pvy = self.pvel
        reach = max(7.0, w * 0.09)
        stir = abs(pvx) + abs(pvy) > 0.5
        keep = []
        for p in petals:
            x, y = p[0], p[1]
            # curl of a drifting noise field makes eddies and swirls
            nx, ny = x * 0.06 - t * 0.35 * (0.5 + W), y * 0.14 + t * 0.05
            e = 0.35
            dndy = (noise2(nx, ny + e, s) - noise2(nx, ny - e, s))
            dndx = (noise2(nx + e, ny, s) - noise2(nx - e, ny, s))
            sw = 2.5 * (0.4 + W * 0.6) * (0.6 + self.gust)
            tvx = base + dndy * sw * 2.2
            tvy = 0.85 + sink - dndx * sw * 0.7 - self.gust * W * 0.25
            if ptr is not None:
                dx, dy = x - ptr[0], (y - ptr[1]) * ASPECT
                if -reach < dx < reach and -reach < dy < reach:
                    d = math.sqrt(dx * dx + dy * dy)
                    if d < reach:
                        f = 1 - d / reach
                        if stir:      # carried along by the sweep
                            tvx += pvx * f * 1.6
                            tvy += pvy * f * 1.6
                        else:         # a resting pointer stirs a small eddy
                            tvx += -dy / (d + 1) * f * 4
                            tvy += dx / (d + 1) * f * 2
            p[2] += (tvx - p[2]) * min(1.0, dt * follow)
            p[3] += (tvy - p[3]) * min(1.0, dt * follow)
            p[0] = x + p[2] * dt
            p[1] = y + p[3] * dt
            p[4] += p[5] * dt * (0.5 + 0.5 * self.gust)
            xi = int(p[0])
            if p[0] >= w + 8 or p[1] < -6 or p[0] < -8 or p[1] > h + 4:
                if respawn:
                    p[:] = self.spawn()
                    keep.append(p)
                continue
            if 0 <= xi < w and p[1] >= hill[xi] - pile[xi] * 0.5:
                if pile[xi] < 2.6:
                    pile[xi] += 0.35
                if respawn:
                    p[:] = self.spawn()
                    keep.append(p)
                continue
            keep.append(p)
        return keep

    # -- drawing ------------------------------------------------------------------
    def draw(self, cv):
        t = self.t
        pal = self.pal
        w, h = self.w, self.h
        shade = cv.shade
        put = cv.put
        for x, y, lvl, col in self.sky:
            shade(x, y, lvl, col)
        for x, y, b, ph in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * (1.0 + b) + ph)
            put(x, y, "." if tw < 0.6 else "+" if b > 0.85 and tw > 0.92 else "*" if tw > 0.85 else "·",
                scale((235, 235, 255), 0.35 + 0.6 * b * tw))
        self.draw_clouds(cv)
        self.draw_orb(cv)
        self.draw_land(cv)
        draw_wood(cv, self.tree, bark=pal["bark"], lo=0.1, hi=0.65, tint=pal["tint"], tint_k=0.25)
        self.draw_canopy(cv)
        self.draw_pile(cv)
        chs = cv.ch
        for x, y, vx, vy, ph, spin, col, b in self.petals + self.flurry:
            xi, yi = int(x), int(y)
            if 0 <= xi < w and 0 <= yi < h and chs[yi * w + xi] in DISC:
                continue   # behind the sun / moon disc
            fl = 0.5 + 0.5 * math.sin(ph)          # tumbling: the petal flashes as it turns
            ch = PETAL_GLYPHS[int(ph) % len(PETAL_GLYPHS)]
            put(x, y, ch, scale(col, b * (0.7 + 0.45 * fl)))

    def draw_orb(self, cv):
        pal = self.pal
        cx, cy, r = self.orb_x, self.orb_y, self.orb_r
        t = self.t
        stops = pal["orb_col"]
        moon = pal["orb"] == "moon"
        R = r * 2.6
        for y in range(int(cy - R / ASPECT) - 1, int(cy + R / ASPECT) + 2):
            if y < 0 or y >= cv.h:
                continue
            for x in range(int(cx - R) - 1, int(cx + R) + 2):
                if x < 0 or x >= cv.w or y >= self.ridge[x]:
                    continue
                ch, d = disc_glyph(x, y, cx, cy, r)
                if ch:
                    if moon:
                        crater = clamp(noise2(x * 0.5, y * 1.0, 77))
                        col = gradient(stops, 0.92 - 0.25 * min(1.0, d) ** 2 - 0.35 * crater)
                    else:
                        col = gradient(stops, 1 - min(1.0, d) * 0.6)
                    cv.put(x, y, ch, col)
                else:
                    g = (2.6 - d) / 1.52
                    if g > 0.05:
                        cv.put(x, y, "·" if g > 0.55 else ".", scale(stops[0 if not moon else 1], 0.15 + 0.55 * g * g))

    def draw_land(self, cv):
        put = cv.put
        for x, y, ch, col in self.land:
            put(x, y, ch, col)

    def draw_clouds(self, cv):
        """Soft clouds drift very slowly."""
        put = cv.put
        pal = self.pal
        cc = pal["sky"][3]
        warm = pal["orb_col"][1]
        off = self.t * 0.15
        w = self.w
        for x, y, v, near in self.clouds:
            xi = int(x + off) % w
            if y >= self.ridge[xi] - 1:
                continue
            col = mix(scale(cc, 0.55), warm, near * 0.8)
            put(xi, y, "-" if v < 0.55 else "~", scale(col, 0.18 + 0.4 * v * (0.4 + 0.6 * near)))

    def bake_land(self):
        """Ridge and hill as continuous outlines over textured fills (static, drawn every frame)."""
        pal = self.pal
        w, h = self.w, self.h
        r0, r1 = pal["ridge"]
        h0, h1, h2 = pal["hill"]
        rim = pal["rim"]
        out = []
        for x in range(w):
            ry, hy = self.ridge[x], self.hill[x]
            ch, iy = edge_glyph(ry, self.ridge[max(0, x - 1)], self.ridge[min(w - 1, x + 1)])
            if iy < hy - 1:
                out.append((x, iy, ch, mix(r1, rim, 0.25)))
            for y in range(iy + 1, int(hy)):
                dd = (y - ry) / max(1.0, hy - ry)
                if _hash(x, y) < 0.05 - 0.03 * dd:
                    out.append((x, y, ".", scale(mix(r1, r0, clamp(dd * 1.5)), 0.7)))
            sun_side = clamp(1 - abs(x - self.orb_x) / w)
            ch, iy = edge_glyph(hy, self.hill[max(0, x - 1)], self.hill[min(w - 1, x + 1)])
            out.append((x, iy, ch, mix(h2, rim, 0.3 + 0.6 * sun_side)))
            for y in range(iy + 1, h):
                dd = (y - hy) / max(1.0, h - hy)
                r = _hash(x, y)
                if r < (0.55 if y - iy <= 1 else 0.2 - 0.12 * dd):
                    k = _hash(y * 3, x)
                    ch = "'" if k < 0.35 else '"' if k < 0.5 else "," if k < 0.75 else "."
                    lit = clamp(1 - dd * 2.2) * (0.3 + 0.7 * sun_side)
                    out.append((x, y, ch, mix(mix(h1, h0, clamp(dd * 1.4)), mix(h2, rim, 0.3), 0.5 * lit)))
        self.land = out

    def draw_canopy(self, cv):
        ramp = leaf_ramp(cv)
        nr = len(ramp) - 1
        pal = self.pal
        stops = pal["bloom"]
        tint, tk = pal["tint"], pal["tint_k"]
        t = self.t
        put = cv.put
        W = max(0.0, self.opt("wind"))
        gust = self.gust
        sway_amp = (0.25 + 1.1 * gust) * (0.4 + 0.6 * W) * self.wdir
        sway_amp += clamp(self.pvel[0] * 0.05, -1.2, 1.2)        # a pointer sweep sways the boughs
        shake = self.shake * self.shake * 2.2 * math.sin(t * 31.0)
        top = self.canopy_top
        h = self.h
        span = max(1.0, self.w * 0.3)
        for x, y, lvl, sh, hot, dx in self.canopy:
            reach = clamp(dx / span) * 0.6 + clamp((h - y) / h) * 0.6
            sway = (sway_amp * (0.6 + 0.4 * math.sin(t * 1.3 + y * 0.4 + x * 0.05)) + shake) * reach
            xi = int(x + sway)
            ripple = math.sin(x * 0.21 - t * (1.5 + 2.5 * gust) + y * 0.35)
            v = lvl * (0.92 + 0.12 * ripple)
            idx = int(clamp(v) * nr + 0.5)
            if idx <= 0:
                continue
            col = gradient(stops, sh * (0.9 + 0.12 * ripple))
            if hot > 0:
                col = mix(col, tint, tk * hot)
            put(xi, y, ramp[idx], scale(col, 0.5 + 0.5 * clamp(v)))

    def draw_pile(self, cv):
        stops = self.pal["petal"]
        put = cv.put
        for x, p in enumerate(self.pile):
            if p < 0.08:
                continue
            gy = int(self.hill[x])
            k = 0
            while p > 0 and k < 3:
                v = min(1.0, p)
                ch = "." if v < 0.35 else "," if v < 0.6 else "o" if (x + k) % 3 else "*"
                put(x, gy - k if k else gy, ch, scale(stops[(x + k) % len(stops)], 0.45 + 0.5 * v))
                p -= 1.0
                k += 1
