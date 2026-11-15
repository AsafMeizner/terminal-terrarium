"""A tree's whole life in time-lapse on a hillside.

Days flash by (sun and moon arcs, racing clouds and their shadows), years turn through the
seasons, a seed sprouts, grows into a big tree, ages, sheds its limbs, falls, crumbles into the
soil, and a different tree grows from the same spot. Every tree comes from a randomized growth
genome (branch probability, angles, taper, tropism, depth, internode length, foliage, colors),
so no two generations look alike.
"""
import math

from ..engine import ASPECT, RAMPS, Scene, clamp, gradient, hsv, mix, noise1, noise2, scale, smoothstep
from .bonsai import LEAFY, wood_glyph
from .sakura import disc_glyph, edge_glyph

TAU = math.tau
STEP = 0.7


def qc(c):
    r, g, b = c
    return (0 if r < 0 else 252 if r > 252 else int(r) & ~3,
            0 if g < 0 else 252 if g > 252 else int(g) & ~3,
            0 if b < 0 else 252 if b > 252 else int(b) & ~3)


def hsh(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def mul(c, L):
    return (c[0] * L[0], c[1] * L[1], c[2] * L[2])


def keyed(keys, e):
    """Interpolate a list of (key, value-tuple-of-colors) at e."""
    if e <= keys[0][0]:
        return keys[0][1]
    for (k0, v0), (k1, v1) in zip(keys, keys[1:]):
        if e <= k1:
            f = (e - k0) / (k1 - k0)
            return tuple(mix(a, b, f) for a, b in zip(v0, v1))
    return keys[-1][1]


# --------------------------------------------------------------------------- palettes

SPECIES = {
    "oak": {
        "bark": [(22, 15, 10), (54, 36, 24), (92, 64, 42), (136, 98, 68), (184, 146, 108)],
        "spring": [(20, 60, 20), (60, 130, 40), (120, 190, 60), (180, 230, 100), (230, 250, 170)],
        "summer": [(8, 36, 16), (20, 84, 32), (46, 140, 46), (110, 190, 70), (190, 235, 130)],
        "autumn": "warm",
    },
    "birch": {
        "bark": [(70, 68, 64), (150, 148, 140), (205, 203, 196), (234, 232, 226), (252, 252, 248)],
        "spring": [(40, 80, 20), (100, 160, 40), (160, 215, 70), (210, 240, 120), (245, 255, 200)],
        "summer": [(20, 60, 20), (50, 120, 36), (100, 180, 60), (170, 225, 100), (230, 250, 170)],
        "autumn": "gold",
    },
    "pine": {
        "bark": [(26, 12, 8), (70, 34, 20), (120, 62, 36), (170, 100, 60), (210, 150, 100)],
        "spring": [(4, 28, 24), (12, 64, 48), (30, 116, 80), (90, 178, 112), (180, 232, 160)],
        "summer": [(4, 26, 24), (10, 56, 46), (22, 98, 72), (60, 150, 100), (140, 200, 150)],
        "autumn": None,
    },
    "willow": {
        "bark": [(20, 18, 14), (52, 46, 36), (90, 80, 64), (132, 120, 98), (180, 168, 140)],
        "spring": [(40, 70, 20), (100, 150, 40), (170, 210, 80), (215, 240, 140), (245, 255, 200)],
        "summer": [(22, 56, 22), (60, 120, 40), (120, 175, 60), (180, 215, 110), (230, 245, 180)],
        "autumn": "gold",
    },
    "baobab": {
        "bark": [(40, 30, 30), (90, 72, 68), (146, 120, 110), (196, 170, 152), (232, 212, 190)],
        "spring": [(30, 60, 20), (70, 120, 30), (130, 175, 50), (190, 215, 100), (235, 245, 170)],
        "summer": [(20, 46, 16), (50, 96, 30), (96, 146, 46), (160, 190, 80), (215, 230, 140)],
        "autumn": "brown",
    },
}
AUTUMNS = {
    "warm": [
        [(50, 18, 6), (120, 46, 14), (190, 90, 26), (230, 140, 50), (255, 200, 110)],      # russet
        [(56, 8, 10), (140, 24, 20), (215, 60, 30), (250, 120, 60), (255, 190, 130)],      # scarlet
        [(70, 30, 6), (170, 70, 12), (240, 130, 24), (255, 180, 70), (255, 225, 150)],     # orange
        [(60, 6, 30), (130, 20, 50), (200, 50, 70), (240, 110, 100), (255, 180, 160)],     # crimson
    ],
    "gold": [
        [(70, 46, 4), (160, 110, 10), (235, 180, 30), (255, 220, 80), (255, 245, 170)],
        [(80, 50, 6), (180, 120, 14), (245, 170, 30), (255, 210, 90), (255, 240, 180)],
    ],
    "brown": [
        [(60, 40, 10), (130, 90, 20), (190, 140, 40), (225, 185, 80), (250, 225, 140)],
        [(70, 30, 10), (150, 70, 20), (210, 120, 40), (240, 170, 80), (255, 215, 150)],
    ],
}
DEAD = [(30, 20, 10), (70, 50, 26), (120, 90, 50), (160, 130, 80), (200, 170, 120)]
CUT = (214, 178, 124)
MOSS = (70, 130, 50)
SNOW = (226, 234, 248)

SKY_KEYS = [  # sun elevation -> (zenith, middle, horizon)
    (-1.0, ((2, 3, 12), (5, 8, 26), (12, 18, 44))),
    (-0.22, ((4, 6, 22), (10, 14, 42), (26, 32, 70))),
    (-0.08, ((12, 16, 52), (50, 40, 104), (190, 90, 96))),
    (0.02, ((34, 56, 132), (150, 100, 150), (255, 150, 80))),
    (0.14, ((40, 90, 180), (110, 150, 210), (255, 200, 140))),
    (0.35, ((50, 120, 225), (110, 175, 245), (200, 230, 255))),
    (1.0, ((40, 112, 228), (100, 170, 248), (190, 226, 255))),
]
LIGHT_KEYS = [
    (-1.0, ((0.30, 0.36, 0.60),)),
    (-0.2, ((0.32, 0.38, 0.62),)),
    (-0.05, ((0.55, 0.45, 0.62),)),
    (0.03, ((1.0, 0.64, 0.46),)),
    (0.15, ((1.0, 0.86, 0.72),)),
    (0.35, ((1.0, 1.0, 1.0),)),
    (1.0, ((1.0, 1.0, 1.0),)),
]
CLOUD_KEYS = [  # (lit, shade)
    (-1.0, ((60, 70, 105), (22, 26, 46))),
    (-0.15, ((70, 76, 120), (26, 28, 54))),
    (-0.03, ((240, 140, 130), (80, 50, 90))),
    (0.06, ((255, 190, 140), (130, 90, 120))),
    (0.25, ((250, 250, 255), (150, 160, 190))),
    (1.0, ((255, 255, 255), (160, 170, 200))),
]
FLOWER_SETS = [
    [(255, 120, 170), (255, 220, 80), (180, 120, 255), (245, 245, 255)],
    [(255, 90, 70), (255, 200, 60), (255, 255, 240)],
    [(120, 170, 255), (190, 140, 255), (255, 255, 255), (255, 230, 120)],
    [(255, 150, 200), (255, 110, 150), (255, 210, 230)],
    [(255, 230, 90), (255, 170, 40), (255, 255, 200)],
]
SKY_RAMP = " .·:"
CLOUD_RAMP = " ⠁⠃⠇⡇⡏⡟⡿⣿"


def tinted(stops, tint, k):
    return [mix(c, scale(tint, (c[0] + c[1] + c[2]) / 640), k) for c in stops]


# --------------------------------------------------------------------------- tree genome + builder

class Branch:
    __slots__ = ("pts", "parent", "depth", "attach", "length", "end_ang", "t0", "t1", "drop", "gone", "kids")

    def __init__(self, pts, parent, depth, attach, length, end_ang):
        self.pts = pts
        self.parent = parent
        self.depth = depth
        self.attach = attach
        self.length = length
        self.end_ang = end_ang
        self.t0 = self.t1 = 0.0
        self.drop = 9.0
        self.gone = False
        self.kids = []


def taper(r0, r1, flare=0.0, bulge=0.0):
    def f(u):
        return (r0 + (r1 - r0) * u) * (1 + flare * (1 - u) ** 6) * (1 + bulge * math.sin(math.pi * u))
    return f


def steer(rng, target, k=0.15, wob=0.05):
    def f(u, a):
        return a + (target(u, a) - a) * k + rng.gauss(0, wob)
    return f


def make_genome(rng, species):
    """Randomized growth rules: the species sets the architecture, the genome everything else."""
    U = rng.uniform
    g = {
        "species": species,
        "lean": U(-0.12, 0.12),
        "p_branch": U(0.6, 0.98),         # chance each potential side shoot exists
        "kids": rng.choice((2, 2, 3, 3, 4)),
        "angle": U(0.32, 0.8),            # mean branching angle (radians)
        "jitter": U(0.04, 0.3),           # angle noise per branch
        "ratio": U(0.58, 0.8),            # child length / parent length
        "taper": U(0.5, 0.78),            # radius kept along a branch
        "trop": U(-0.3, 0.3),             # + bends up toward light, - droops outward
        "depth": rng.randint(3, 5),
        "internode": U(0.5, 0.95),        # where side shoots sprout along a parent
        "wob": U(0.02, 0.11),             # waviness
        "blob": U(0.13, 0.19),           # foliage clump size (fraction of height)
        "squash": U(0.5, 0.95),           # clump flatness
        "density": U(0.88, 1.0),           # fraction of foliage cells that carry leaves
        "midblob": U(0.5, 1.0),
        "girth": U(0.8, 1.25),
        "height": U(0.85, 1.0),
        "life": U(0.85, 1.15),
        "limbs": rng.randint(3, 6),
        "fan": U(0.8, 1.25),
        "trunk": U(0.85, 1.15),
    }
    base = SPECIES[species]
    tint = hsv(rng.random(), U(0.4, 0.9), 1.0)
    tk = U(0.0, 0.22)
    g["spring"] = tinted(base["spring"], tint, tk)
    g["summer"] = tinted(base["summer"], tint, tk * 0.8)
    au = base["autumn"]
    if au is None:
        g["autumn"] = None
    else:
        g["autumn"] = tinted(rng.choice(AUTUMNS[au]), hsv(rng.random(), 0.5, 1.0), U(0.0, 0.15))
    g["bark"] = tinted(base["bark"], hsv(rng.random(), 0.3, 1.0), U(0.0, 0.12))
    return g


class Gen:
    def __init__(self, rng, G, H):
        self.rng = rng
        self.G = G
        self.H = H
        self.br = []
        self.blobs = []    # [x, yv, rx, branch, frac, squash, birth]
        self.strands = []  # [x, yv, rows, branch, frac, birth]

    def walk(self, x, yv, ang, length, rfun, steer_fn, depth, parent=-1, attach=1.0):
        n = max(2, int(length / STEP + 0.5))
        st = length / n
        pts = []
        for i in range(n + 1):
            f = i / n
            pts.append((x, yv, rfun(f)))
            ang = steer_fn(f, ang)
            x += math.sin(ang) * st
            yv += math.cos(ang) * st
            if yv < 0.8 and depth > 0:
                yv = 0.8
        b = Branch(pts, parent, depth, attach, length, ang)
        self.br.append(b)
        if parent >= 0:
            self.br[parent].kids.append(len(self.br) - 1)
        return len(self.br) - 1

    def blob(self, x, yv, rx, branch, frac, squash=0.75):
        self.blobs.append([x, yv, max(0.6, rx), branch, frac, squash, 0.0])

    def at(self, bi, f):
        pts = self.br[bi].pts
        return pts[int(clamp(f) * (len(pts) - 1))]

    # -- generic recursive limb (oak / willow arms / baobab crown) ---------------------
    def limb(self, x, yv, ang, length, r, depth, parent, attach, maxd=None):
        rng, G, H = self.rng, self.G, self.H
        maxd = G["depth"] if maxd is None else maxd
        sgn = 1 if ang >= 0 else -1
        trop = G["trop"]
        a0 = ang

        def tgt(f, a):
            return a0 * (1 - 0.6 * trop) - sgn * trop * 0.6 * f
        bi = self.walk(x, yv, ang, length, taper(r, max(0.35, r * G["taper"])),
                       steer(rng, tgt, 0.14, G["wob"]), depth, parent, attach)
        b = self.br[bi]
        ex, eyv, er = b.pts[-1]
        if depth >= maxd or length < 2.2:
            self.blob(ex, eyv, H * G["blob"] * rng.uniform(0.8, 1.2), bi, 1.0, G["squash"])
            return
        if depth >= 2 and rng.random() < G["midblob"]:
            mx, myv, _ = self.at(bi, 0.55)
            self.blob(mx, myv, H * G["blob"] * rng.uniform(0.6, 0.85), bi, 0.55, G["squash"])
        kids = G["kids"]
        made = 0
        for k in range(kids):
            if k > 0 and rng.random() > G["p_branch"]:
                continue
            if kids > 1:
                da = (k / (kids - 1) - 0.5) * 2 * G["angle"]
            else:
                da = 0.0
            da += rng.gauss(0, G["jitter"])
            na = clamp(b.end_ang + da, -1.75, 1.75)
            fi = 1.0 if k % 2 == 0 else rng.uniform(G["internode"], 1.0)
            sx, syv, sr = self.at(bi, fi)
            self.limb(sx, syv, na, length * G["ratio"] * rng.uniform(0.88, 1.12), max(0.35, sr * 0.72),
                      depth + 1, bi, fi, maxd)
            made += 1
        if made == 0:
            self.blob(ex, eyv, H * G["blob"], bi, 1.0, G["squash"])


def roots(gen, r0, n=2):
    rng = gen.rng
    for side in (-1, 1)[:n]:
        if r0 > 1.1:
            rl = r0 * rng.uniform(1.4, 2.6)
            gen.walk(side * r0 * 0.5, 0.25, side * 1.8, rl, taper(r0 * 0.45, 0.4), lambda f, a, s=side: a + (s * 2.0 - a) * 0.2, 0)


def build_oak(gen):
    rng, G, H = gen.rng, gen.G, gen.H
    tl = H * rng.uniform(0.28, 0.38) * G["trunk"]
    r0 = clamp(H * 0.048 * G["girth"], 0.7, 6.0)
    lean = G["lean"]
    t = gen.walk(0.0, 0.0, lean, tl, taper(r0, r0 * 0.72, 0.9), steer(rng, lambda f, a: lean * 0.3, 0.1, 0.03), 0)
    roots(gen, r0)
    n = G["limbs"]
    for k in range(n):
        a = (-1.1 + 2.2 * (k + rng.uniform(0.25, 0.75)) / n) * G["fan"]
        fi = rng.uniform(0.65, 1.0)
        x, yv, r = gen.at(t, fi)
        gen.limb(x, yv, a, H * rng.uniform(0.22, 0.31) * (1.08 - 0.25 * abs(a)), r * 0.68, 1, t, fi)
    x, yv, r = gen.br[t].pts[-1]
    gen.blob(x, yv + H * 0.05, H * G["blob"] * 1.1, t, 0.0, G["squash"])


def build_pine(gen):
    rng, G, H = gen.rng, gen.G, gen.H
    r0 = clamp(H * 0.034 * G["girth"], 0.6, 4.0)
    tl = H * 0.97
    t = gen.walk(0.0, 0.0, G["lean"] * 0.2, tl, taper(r0, 0.35, 0.6),
                 steer(rng, lambda f, a: 0.0, 0.2, 0.012), 0)
    roots(gen, r0)
    yv = H * rng.uniform(0.12, 0.24)
    spread = rng.uniform(0.3, 0.44)       # cone width
    droop = rng.uniform(1.5, 2.05)        # whorl angle (pi/2 = level)
    gap = rng.uniform(0.045, 0.085)
    while yv < H * 0.9:
        f = yv / tl
        x, y_, r = gen.at(t, f)
        L = (1 - f) ** rng.uniform(0.8, 1.15) * H * spread * rng.uniform(0.85, 1.1) + H * 0.02
        for s_ in (-1, 1):
            if rng.random() > 0.55 + 0.45 * G["p_branch"]:
                continue
            a = s_ * (droop + rng.gauss(0, G["jitter"] * 0.4))
            bi = gen.walk(x, y_, s_ * 1.3, L, taper(max(0.4, r * 0.5), 0.35),
                          steer(rng, lambda ff, aa, a=a: a + G["trop"] * -0.5 * ff * (1 if a > 0 else -1), 0.18, 0.04),
                          1, t, f)
            mx, myv, _ = gen.at(bi, 0.55)
            gen.blob(mx, myv - 0.5, L * 0.62 + 1.0, bi, 0.3, rng.uniform(0.26, 0.4))
        yv += H * gap * (1 - 0.3 * f) * rng.uniform(0.8, 1.2)
    x, yv, r = gen.br[t].pts[-1]
    gen.blob(x, yv - H * 0.03, H * 0.045 + 1, t, 0.0, 1.5)


def build_willow(gen):
    rng, G, H = gen.rng, gen.G, gen.H
    tl = H * rng.uniform(0.26, 0.36) * G["trunk"]
    r0 = clamp(H * 0.052 * G["girth"], 0.8, 6.0)
    lean = G["lean"]
    t = gen.walk(0.0, 0.0, lean, tl, taper(r0, r0 * 0.7, 0.8), steer(rng, lambda f, a: lean * 0.5, 0.1, 0.04), 0)
    roots(gen, r0)
    n = G["limbs"] + 1
    arch = rng.uniform(1.6, 2.4)
    for k in range(n):
        a0 = (-0.95 + 1.9 * (k + rng.uniform(0.25, 0.75)) / n) * G["fan"]
        sgn = 1 if a0 >= 0 else -1
        fi = rng.uniform(0.7, 1.0)
        x, yv, r = gen.at(t, fi)
        L = H * rng.uniform(0.38, 0.55)
        bi = gen.walk(x, yv, a0 * 0.6, L, taper(r * 0.6, 0.35),
                      steer(rng, lambda f, a, a0=a0, s=sgn: a0 * 0.6 + s * arch * f ** 1.4, 0.2, G["wob"] * 0.6), 1, t, fi)
        pts = gen.br[bi].pts
        for j in range(len(pts) // 5, len(pts), max(1, len(pts) // 4)):
            px, pyv, _ = pts[j]
            gen.blob(px, pyv + 0.8, H * G["blob"] * rng.uniform(0.5, 0.7), bi, j / len(pts), 0.6)
        if rng.random() < G["p_branch"]:
            fj = rng.uniform(0.3, 0.6)
            sx, syv, sr = gen.at(bi, fj)
            sa = a0 * 0.6 + sgn * rng.uniform(0.2, 0.6)
            sb = gen.walk(sx, syv, sa, L * rng.uniform(0.4, 0.6), taper(max(0.35, sr * 0.7), 0.35),
                          steer(rng, lambda f, a, sa=sa, s=sgn: sa + s * arch * 0.8 * f, 0.2, 0.05), 2, bi, fj)
            pts2 = gen.br[sb].pts
        else:
            sb, pts2 = None, []
        for b_i, pp in ((bi, pts), (sb, pts2)):
            if b_i is None:
                continue
            lx = None
            for j, (px, pyv, _) in enumerate(pp):
                if j < len(pp) * 0.15:
                    continue
                if lx is None or abs(px - lx) >= rng.uniform(0.9, 1.6):
                    rows = (pyv / ASPECT) * rng.uniform(0.45, 0.9) * (0.6 + 0.4 * G["density"])
                    gen.strands.append([px, pyv, rows, b_i, j / len(pp), 0.0])
                    lx = px
    x, yv, r = gen.br[t].pts[-1]
    gen.blob(x, yv + H * 0.06, H * G["blob"] * 0.9, t, 0.0, 0.7)


def build_birch(gen):
    rng, G, H = gen.rng, gen.G, gen.H
    nt = rng.choice((1, 2, 2, 3))
    for k in range(nt):
        off = k - (nt - 1) / 2
        a = off * rng.uniform(0.1, 0.22) + G["lean"] * 0.5
        L = H * rng.uniform(0.82, 0.97) * (1 - 0.12 * abs(off))
        r0 = clamp(H * 0.024 * G["girth"], 0.55, 2.4) * (1 if off == 0 else 0.85)
        t = gen.walk(off * r0 * 1.3, 0.0, a, L, taper(r0, 0.35, 0.3),
                     steer(rng, lambda f, aa, a=a: a * (1 - 0.5 * f), 0.1, 0.025), 0)
        yy = L * rng.uniform(0.25, 0.38)
        side = rng.choice((-1, 1)) if off == 0 else (1 if off > 0 else -1)
        while yy < L * 0.94:
            f = yy / L
            x, yv, r = gen.at(t, f)
            if rng.random() < G["p_branch"]:
                bl = H * rng.uniform(0.09, 0.2) * (1.15 - 0.6 * f)
                ba = a + side * (G["angle"] + 0.25 + rng.gauss(0, G["jitter"]))
                bi = gen.walk(x, yv, ba, bl, taper(max(0.35, r * 0.5), 0.35),
                              steer(rng, lambda ff, aa, ba=ba, s=side: ba + s * (0.5 - G["trop"]) * ff, 0.15, 0.05), 1, t, f)
                ex, eyv, _ = gen.br[bi].pts[-1]
                gen.blob(ex, eyv, H * G["blob"] * rng.uniform(0.45, 0.65), bi, 1.0, 0.85)
                if bl > 4:
                    mx, myv, _ = gen.at(bi, 0.5)
                    gen.blob(mx, myv, H * G["blob"] * 0.45, bi, 0.5, 0.85)
            side = -side if rng.random() < 0.85 else side
            yy += H * rng.uniform(0.035, 0.07)
        x, yv, r = gen.br[t].pts[-1]
        gen.blob(x, yv, H * G["blob"] * 0.55, t, 0.0, 1.1)


def build_baobab(gen):
    rng, G, H = gen.rng, gen.G, gen.H
    tl = H * rng.uniform(0.48, 0.6) * G["trunk"]
    r0 = clamp(H * 0.1 * G["girth"], 1.6, 11.0)
    t = gen.walk(0.0, 0.0, G["lean"] * 0.3, tl, taper(r0, r0 * rng.uniform(0.45, 0.65), 0.3, rng.uniform(0.08, 0.25)),
                 steer(rng, lambda f, a: 0.0, 0.2, 0.01), 0)
    x, yv, r = gen.br[t].pts[-1]
    n = G["limbs"] + rng.randint(2, 4)
    for k in range(n):
        a = (-1.3 + 2.6 * (k + rng.uniform(0.2, 0.8)) / n)
        L = H * rng.uniform(0.15, 0.26) * (1.1 - 0.2 * abs(a))
        sx = x + a * r * 0.35
        bi = gen.walk(sx, yv - r * 0.3, a, L, taper(r * 0.3, 0.4),
                      steer(rng, lambda f, aa, a=a: a * (0.85 - 0.4 * G["trop"]), 0.15, 0.1 + G["wob"]), 1, t, 1.0)
        b = gen.br[bi]
        ex, eyv, er = b.pts[-1]
        kids = rng.randint(1, 3)
        for j in range(kids):
            ka = b.end_ang + rng.uniform(-0.6, 0.6)
            kb = gen.walk(ex, eyv, ka, L * rng.uniform(0.35, 0.6), taper(max(0.35, er * 0.7), 0.35),
                          steer(rng, lambda f, aa, ka=ka: ka * 0.8, 0.15, 0.12), 2, bi, 1.0)
            kx, kyv, _ = gen.br[kb].pts[-1]
            gen.blob(kx, kyv + 0.6, H * G["blob"] * rng.uniform(0.8, 1.1), kb, 1.0, 0.45)
    gen.blob(x, yv + 1.0, H * G["blob"] * 0.6, t, 0.0, 0.45)


BUILDERS = {"oak": build_oak, "pine": build_pine, "willow": build_willow, "birch": build_birch, "baobab": build_baobab}
HEIGHT = {"oak": 0.88, "pine": 1.0, "willow": 0.8, "birch": 0.97, "baobab": 0.74}


class Life:
    """One tree: geometry, growth schedule, baked foliage, and its slow death."""

    def __init__(self, scene, species):
        self.scene = scene
        rng = scene.rng
        w, h = scene.w, scene.h
        self.species = species
        G = make_genome(rng, species)
        self.G = G
        self.ox = scene.tx + 0.5
        gy = scene.gy[int(clamp(scene.tx, 0, w - 1))]
        self.oy = gy + 0.6
        rows = max(3.0, self.oy - 1.0)
        H = rows * ASPECT * HEIGHT[species] * G["height"]
        gen = Gen(rng, G, H)
        BUILDERS[species](gen)
        self.br, self.blobs, self.strands = gen.br, gen.blobs, gen.strands
        self.H = H
        self.fit(w, h)
        self.schedule(rng)
        self.seed = rng.randrange(1 << 15)
        self.bake_canopy(w, h)
        trunk = [b for b in self.br if b.depth == 0 and b.pts[-1][1] > 2]
        self.r0 = max((b.pts[0][2] for b in trunk), default=1.0)
        self.pivot = (trunk[0].pts[0][0] if trunk else 0.0, max(1.0, self.r0 * 1.1))
        self.dir = 1 if (w - self.ox) > self.ox else -1
        self.phi = 0.0
        self.fallen = False
        self.cache_key = None
        self.cache = []
        self.evergreen = G["autumn"] is None
        self.events = sorted((b.drop, i) for i, b in enumerate(self.br) if b.depth > 0)
        self.ev = 0

    def fit(self, w, h):
        """Uniformly shrink the tree so it fits beside its base."""
        xl = xr = 0.0
        top = 1.0
        for b in self.br:
            for x, yv, r in b.pts:
                xl = min(xl, x - r)
                xr = max(xr, x + r)
                top = max(top, yv)
        for x, yv, rx, *_ in self.blobs:
            xl = min(xl, x - rx * 1.2)
            xr = max(xr, x + rx * 1.2)
            top = max(top, yv + rx * 0.5)
        roomL = min(self.ox - 1, w * 0.45)
        roomR = min(w - self.ox - 1, w * 0.45)
        roomT = (self.oy - 0.5) * ASPECT
        k = min(1.0, roomL / max(1e-6, -xl), roomR / max(1e-6, xr), roomT / max(1e-6, top))
        if k < 1.0:
            for b in self.br:
                b.pts = [(x * k, yv * k, r * k) for x, yv, r in b.pts]
                b.length *= k
            for bl in self.blobs:
                bl[0] *= k
                bl[1] *= k
                bl[2] = max(0.6, bl[2] * k)
            for s in self.strands:
                s[0] *= k
                s[1] *= k
                s[2] *= k
            self.H *= k

    def schedule(self, rng):
        H = max(1.0, self.H)
        for b in self.br:
            if b.parent < 0:
                b.t0, b.t1 = 0.0, 0.3
            else:
                p = self.br[b.parent]
                b.t0 = p.t0 + (p.t1 - p.t0) * b.attach + 0.02
                b.t1 = b.t0 + 0.08 + 0.55 * b.length / H
        m = max((b.t1 for b in self.br if b.depth > 0), default=0.3)
        k = 0.82 / max(m, 1e-6)
        for b in self.br:
            if b.depth > 0:
                b.t0 *= k
                b.t1 *= k
        for bl in self.blobs:
            b = self.br[bl[3]]
            bl[6] = 0.0 if b.depth == 0 else b.t0 + (b.t1 - b.t0) * bl[4]
        for s in self.strands:
            b = self.br[s[3]]
            s[5] = b.t0 + (b.t1 - b.t0) * s[4] + 0.03
            s.append(rng.uniform(0, TAU))
        for b in self.br:
            if b.depth == 0:
                continue
            if b.depth == 1:
                d = rng.uniform(0.785, 0.84)
            elif b.depth == 2:
                d = rng.uniform(0.745, 0.8)
            else:
                d = rng.uniform(0.69, 0.765)
            if b.parent >= 0 and self.br[b.parent].depth > 0:
                d = min(d, self.br[b.parent].drop)
            b.drop = d

    def bake_canopy(self, w, h):
        lx, ly, lz = -0.45, -0.75, 0.5
        ln = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / ln, ly / ln, lz / ln
        rng = self.scene.rng
        best = {}
        ox, oy = self.ox, self.oy
        seed = self.seed
        for x, yv, rx, bri, frac, squash, birth in self.blobs:
            cx = ox + x
            cy = oy - yv / ASPECT
            ry = max(0.6, rx * squash / ASPECT)
            z = rng.random()
            for Y in range(int(cy - ry * 1.3) - 1, int(cy + ry * 1.3) + 2):
                if Y < 0 or Y >= h:
                    continue
                for X in range(int(cx - rx * 1.3) - 1, int(cx + rx * 1.3) + 2):
                    if X < 0 or X >= w:
                        continue
                    u = (X + 0.5 - cx) / rx
                    v = (Y + 0.5 - cy) / ry
                    d2 = u * u + v * v
                    edge = math.sqrt(d2) + 0.3 * noise2(X * 0.3, Y * 0.6, seed)
                    if edge > 1.12:
                        continue
                    nz = math.sqrt(max(0.0, 1 - min(1.0, d2)))
                    zz = z + nz * 0.3
                    old = best.get((X, Y))
                    if old is not None and old[0] >= zz:
                        continue
                    lam = clamp(u * lx + v * ly + nz * lz)
                    best[(X, Y)] = (zz, edge, lam, birth, min(1.2, math.sqrt(d2)))
        if not best:
            self.canopy = []
            return
        top = min(k[1] for k in best)
        bot = max(k[1] for k in best)
        span = max(1, bot - top)
        cells = []
        dens = self.G["density"]
        for (X, Y), (zz, edge, lam, birth, dist) in best.items():
            tex = noise2(X * 0.85, Y * 1.6, seed + 9)
            vert = 1 - (Y - top) / span
            if edge > 1.0:
                level, light = 0.16, 0.3
            else:
                core = clamp((1.0 - edge) / 0.25)
                light = clamp(0.28 + 0.55 * lam + 0.16 * tex + 0.14 * vert)
                level = clamp(0.42 + 0.38 * core + 0.25 * tex + 0.12 * lam)
            rv = hsh(X, Y, seed + 3) / dens
            cells.append((X + 0.5 - ox, Y + 0.5 - oy, X, Y, level, int(light * 9.99), rv, birth, dist,
                          int(hsh(X, Y, seed + 4) * 3.99), int(hsh(X, Y, seed + 5) * 7.99), light > 0.62))
        self.canopy = cells

    # -- wood ---------------------------------------------------------------------
    def raster(self, g, s, thick, phi=0.0):
        sc = self.scene
        w, h = sc.w, sc.h
        ox, oy = self.ox, self.oy
        cells = {}
        cphi, sphi = math.cos(phi), math.sin(phi)
        px, pyv = self.pivot
        birch = self.species == "birch"
        floor = math.floor
        for b in self.br:
            if b.gone:
                continue
            if b.depth == 0:
                rf = 1.0
            else:
                if g <= b.t0:
                    continue
                rf = min(1.0, (g - b.t0) / max(1e-6, b.t1 - b.t0))
            pts = b.pts
            n = len(pts)
            m = n if rf >= 1 else max(2, int(rf * (n - 1)) + 1)
            sp = []
            for k in range(m):
                x, yv, r = pts[k]
                rot = 0
                if phi and yv > pyv and b.depth == 0:
                    dx, dy = x - px, yv - pyv
                    x = px + dx * cphi + dy * sphi
                    yv = pyv - dx * sphi + dy * cphi
                    rot = 1
                sp.append((ox + x * s, oy - yv * s / ASPECT, r * s * thick, rot))
            for k in range(m):
                X, Y, r, rot = sp[k]
                a = sp[k - 1] if k else sp[k]
                c = sp[k + 1] if k + 1 < m else sp[k]
                dx, dy = c[0] - a[0], c[1] - a[1]
                if m < n:
                    r *= min(1.0, 0.3 + (m - k) * 0.12)
                ch = wood_glyph(dx, dy)
                rr = r if r > 0.5 else 0.5
                vertical = abs(dx) <= abs(dy) * 1.6
                if vertical:
                    Yi = floor(Y)
                    if Yi < 0 or Yi >= h:
                        continue
                    span = [(Xc, Yi, (Xc + 0.5 - X) / rr) for Xc in range(floor(X - rr), floor(X + rr) + 1)]
                else:
                    Xi = floor(X)
                    if Xi < 0 or Xi >= w:
                        continue
                    rv = rr / ASPECT
                    span = [(Xi, Yc, (Yc + 0.5 - Y) * ASPECT / rr) for Yc in range(floor(Y - rv), floor(Y + rv) + 1)]
                for Xc, Yc, o in span:
                    if not (0 <= Xc < w and 0 <= Yc < h):
                        continue
                    ao = abs(o)
                    if ao > 1.15:
                        continue
                    i = Yc * w + Xc
                    old = cells.get(i)
                    if old is not None and old[0] <= ao:
                        continue
                    light = 0.62 - 0.38 * o + 0.1 * noise2(Xc * 0.9, Yc * 0.4, 7)
                    lk = int(clamp(light) * 9.99)
                    gl = ch
                    if vertical and rr > 1.2 and ao < 0.6 and ch == "|" and hsh(Xc, Yc, 5) < 0.3:
                        gl = ":"
                    if birch and rr >= 0.7 and hsh(Xc, Yc, 77) < 0.22:
                        gl = "=" if hsh(Xc, Yc, 78) < 0.5 else "-"
                        lk = 10
                    top = (not vertical and o < -0.3) or (rr <= 0.55 and not vertical)
                    cells[i] = (ao, gl, lk, top, rot, Xc, Yc)
        return cells

    def wood(self, g, s, thick, phi):
        key = (int(g * 300), sum(1 for b in self.br if b.gone), round(phi, 3), round(s, 3))
        if key != self.cache_key:
            self.cache_key = key
            cells = self.raster(g, s, thick, phi)
            self.cache = [(i, c[1], c[2], c[3]) for i, c in cells.items()]
        return self.cache


# --------------------------------------------------------------------------- the scene

class Timelapse(Scene):
    name = "timelapse"
    title = "Time-lapse"
    blurb = "a tree's whole life in time-lapse: days flash by as it sprouts, grows, ages, falls and a new one rises"
    tags = ("nature", "plants", "sky", "time")
    options = {
        "life": (120.0, "seconds for one tree's life, from seed to crumbled log"),
        "species": ("random", "random, oak, pine, willow, birch or baobab"),
        "day": (2.5, "seconds per day (a year is 8 days)"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.seed = rng.randrange(1 << 15)
        self.life_base = max(20.0, float(self.opt("life")))
        self.dayl = max(0.3, float(self.opt("day")))
        self.yearl = self.dayl * 8
        self.day0 = rng.uniform(0.25, 0.4)
        # -- terrain: a random hillside with a knoll for the tree
        self.tx = int(w * rng.uniform(0.34, 0.5))
        slope = rng.uniform(-0.12, 0.12)
        knoll = rng.uniform(0.02, 0.08)
        kw = rng.uniform(0.16, 0.32)
        rough = rng.uniform(0.008, 0.03)
        base = rng.uniform(0.76, 0.82)
        s = self.seed
        self.gy = [h * (base + slope * (x / max(1, w - 1) - 0.5)) - h * knoll * math.exp(-((x - self.tx) / (w * kw)) ** 2)
                   + (h * rough + 0.3) * (noise1(x * 0.07, s) + 0.5 * noise1(x * 0.19, s + 1)) for x in range(w)]
        fa, na = rng.uniform(0.04, 0.1), rng.uniform(0.03, 0.08)
        self.r1 = [h * 0.5 + h * fa * noise1(x * 0.022, s + 2) + h * 0.03 * noise1(x * 0.07, s + 3) for x in range(w)]
        self.r2 = [h * 0.6 + h * na * noise1(x * 0.035, s + 4) + h * 0.015 * noise1(x * 0.11, s + 5) for x in range(w)]
        self.sky_edge = [min(self.r1[x], self.r2[x], self.gy[x]) for x in range(w)]
        self.hmean = max(1.0, sum(self.sky_edge) / max(1, w))
        # -- random looks
        self.sky_tint = hsv(rng.random(), 0.6, 1.0)
        self.sky_tk = rng.uniform(0.0, 0.18)
        self.far_col = mix((70, 90, 120), hsv(rng.random(), 0.4, 0.6), rng.uniform(0, 0.4))
        self.near_col = mix((40, 92, 70), hsv(rng.random(), 0.5, 0.35), rng.uniform(0, 0.4))
        gh = rng.uniform(-0.04, 0.04)
        self.grass = [hsv(0.28 + gh, 0.6, 0.8), hsv(0.3 + gh, 0.68, 0.62), hsv(0.13 + gh, 0.6, 0.66)]
        self.flower_set = rng.choice(FLOWER_SETS)
        self.cloudy = rng.uniform(0.35, 1.0)
        self.build_background()
        # -- sky life
        n = int(self.count(70))
        self.stars = []
        for _ in range(n):
            x = rng.uniform(0, w)
            y = rng.uniform(0, self.hmean * 0.95)
            self.stars.append((x, y, rng.uniform(0.3, 1.0), rng.uniform(0, TAU)))
        self.pole = (w * rng.uniform(0.2, 0.8), -h * 0.3)
        self.clouds = [self.make_cloud(rng.uniform(-10, w + 10)) for _ in range(max(1, int((2 + w / 40) * self.cloudy)))]
        # -- ground life
        self.bh = [rng.uniform(0.3, 2.2) if rng.random() < 0.6 else 0.0 for _ in range(w)]
        self.bph = [rng.uniform(0, TAU) for _ in range(w)]
        self.bhue = [rng.random() for _ in range(w)]
        self.flowers = []
        self.year_idx = -1
        self.parts = []
        self.debris = []
        self.logs = []
        self.prev = None
        self.ages = 0.0
        self.new_tree()
        self.update_sky()

    # -- background -----------------------------------------------------------------
    def build_background(self):
        """Static terrain + sky layout. Each cell gets a palette class and either a fixed glyph,
        a fixed ramp level (terrain) or a sky level that scales with daylight."""
        w, h = self.w, self.h
        s = self.seed
        NSKY = h
        self.FE, self.FF, self.FF2 = NSKY, NSKY + 1, NSKY + 2
        self.NE, self.NF, self.NT = NSKY + 3, NSKY + 4, NSKY + 5
        self.GE = NSKY + 6
        self.G0 = NSKY + 7
        self.NS = NSKY + 15
        n = w * h
        cls = [0] * n
        xs = [0] * n
        fixed = [" "] * n
        level = [0.0] * n     # >0: terrain ramp level
        lv = [0.0] * n
        sky = []
        for y in range(h):
            for x in range(w):
                i = y * w + x
                xs[i] = x
                gy, r1, r2 = self.gy[x], self.r1[x], self.r2[x]
                gyi, r1i, r2i = int(gy), int(r1), int(r2)
                if y < gyi and y < r1i and y < r2i:
                    cls[i] = y
                    f = clamp(y / max(1.0, min(gy, r1, r2)))
                    streak = noise2(x * 0.045, y * 0.55, s + 7)
                    sky.append((i, f, streak, hsh(x, y, s + 10)))
                    continue
                lv[i] = 0.1
                if y >= gyi:
                    d = y - gyi
                    if d == 0:
                        ch, _ = edge_glyph(gy, self.gy[max(0, x - 1)], self.gy[min(w - 1, x + 1)])
                        r5 = hsh(x, y, s + 5)
                        fixed[i] = ch if ch in "/\\" else "'" if r5 < 0.45 else "," if r5 < 0.75 else "." if r5 < 0.9 else '"'
                        cls[i] = self.GE
                        continue
                    band = 0 if d <= 2 else 1 if d <= 4 else 2 if d <= 7 else 3
                    dens = (0.55, 0.32, 0.2, 0.12)[band]
                    if hsh(x, y, s) < dens:
                        k = hsh(y * 3, x, s + 1)
                        fixed[i] = ('"' if k < 0.3 else "'" if k < 0.55 else "," if k < 0.8 else ";") if band < 2 else                             ("," if k < 0.4 else "." if k < 0.85 else ":")
                    cls[i] = self.G0 + band * 2 + (1 if hsh(x, y, s + 2) < 0.4 else 0)
                elif y >= r2i:
                    d = y - r2i
                    cls[i] = self.NE if d == 0 else self.NF
                    tex = noise2(x * 0.15, y * 0.5, s + 3)
                    level[i] = clamp((0.42 if d == 0 else 0.34 - 0.004 * d) + 0.06 * tex, 0.27, 0.6)
                else:
                    d = y - r1i
                    cls[i] = self.FE if d == 0 else self.FF if d < 3 else self.FF2
                    tex = noise2(x * 0.1, y * 0.4, s + 4)
                    level[i] = clamp((0.25 if d == 0 else 0.2 - 0.008 * d) + 0.05 * tex, 0.08, 0.25)
        # a ragged line of distant conifers along the near ridge
        for x in range(w):
            y = int(self.r2[x]) - 1
            if 0 <= y < h and y < int(self.gy[x]) and hsh(x, 99, s) < 0.3:
                i = y * w + x
                fixed[i] = "^" if hsh(x, 98, s) < 0.75 else "A"
                level[i] = 0.0
                cls[i] = self.NT
                lv[i] = 0.1
        self.bg_cls, self.bg_x, self.bg_lv = cls, xs, lv
        self.bg_fixed, self.bg_level, self.bg_sky = fixed, level, sky
        self.bg_cache = {}

    def bg_chars(self, ramp, k):
        """Glyph array for a ramp and a sky brightness step (0..5), built lazily."""
        key = (ramp, k)
        out = self.bg_cache.get(key)
        if out is not None:
            return out
        nr = len(ramp) - 1
        out = list(self.bg_fixed)
        ascii_ramp = ramp == RAMPS["ascii"]
        for i, lev in enumerate(self.bg_level):
            if lev > 0:
                r = hsh(i, 3, 5)
                if ascii_ramp:
                    if lev >= 0.26:   # near ridge: a distant forest of tiny conifers
                        out[i] = "^" if r < 0.07 else "A" if r < 0.09 else ":" if r < 0.2 else "." if r < 0.38 else " "
                    else:             # far ridge: blue haze
                        out[i] = ":" if r < lev * 0.7 else "." if r < lev * 2.2 else " "
                else:
                    out[i] = ramp[max(1, min(nr, int(lev * nr + r - 0.3)))]
        B = k / 5
        sr = SKY_RAMP
        for i, f, streak, r in self.bg_sky:
            lev = B * (0.04 + 0.36 * f ** 2.4) + 0.03 + 0.1 * streak * (0.2 + B)
            j = int(lev * 3 + r - 0.5)
            if j > 0:
                out[i] = sr[min(3, j)]
        self.bg_cache[key] = out
        return out

    def make_cloud(self, x):
        rng = self.rng
        w, h = self.w, self.h
        cw = rng.uniform(7, 20) * clamp(w / 110, 0.5, 1.6)
        top = rng.uniform(h * 0.04, h * 0.32)
        puffs = []
        for _ in range(rng.randint(3, 6)):
            puffs.append((rng.uniform(-cw * 0.45, cw * 0.45), rng.uniform(-0.25, 0.25) * cw * 0.25,
                          cw * rng.uniform(0.18, 0.34)))
        cells = []
        sd = rng.randrange(1 << 12)
        ry = max(1.0, cw * 0.36 / ASPECT)
        for dy in range(-int(ry) - 1, int(ry * 0.5) + 2):
            for dx in range(-int(cw * 0.8) - 2, int(cw * 0.8) + 3):
                lev = 0.0
                for px, py, pr in puffs:
                    d = math.sqrt((dx - px) ** 2 + ((dy - py) * ASPECT) ** 2) / pr
                    lev = max(lev, 1 - d)
                if dy > ry * 0.35:
                    lev *= 0.4
                lev += 0.25 * noise2(dx * 0.3, dy * 0.7, sd)
                if lev > 0.05:
                    cells.append((dx, dy, clamp(lev * 1.6), clamp(0.5 - dy / (ry * 2))))
        return [x, top, cw, cells, rng.uniform(0.75, 1.3)]

    # -- trees ---------------------------------------------------------------------
    def new_tree(self):
        rng = self.rng
        want = self.opt("species")
        if want in SPECIES:
            sp = want
        else:
            choices = [k for k in SPECIES if k != self.prev] or list(SPECIES)
            sp = rng.choice(choices)
        self.prev = sp
        self.tree = Life(self, sp)
        self.life = self.life_base * self.tree.G["life"]
        self.age = 0.0

    def growth(self):
        f = self.age / self.life
        u = clamp((f - 0.012) / 0.48)
        g = smoothstep(0.0, 1.0, u) ** 0.8 if u > 0 else 0.0
        return f, g

    # -- update --------------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        rng = self.rng
        w, h = self.w, self.h
        self.age += dt
        tree = self.tree
        f, g = self.growth()
        self.update_sky()
        # seasons / flowers
        yi = int(self.t / self.yearl)
        if yi != self.year_idx:
            self.year_idx = yi
            self.flowers = []
            for _ in range(int(self.count(9) * rng.uniform(0.5, 1.3))):
                x = rng.randrange(0, w) if w > 0 else 0
                if abs(x - self.tx) < 2:
                    continue
                self.flowers.append((x, rng.uniform(0.04, 0.2), rng.uniform(0.5, 0.64), rng.choice(self.flower_set),
                                     rng.random()))
        # branch drops and twig vanishing
        while tree.ev < len(tree.events) and tree.events[tree.ev][0] <= f:
            _, bi = tree.events[tree.ev]
            tree.ev += 1
            b = tree.br[bi]
            if b.gone:
                continue
            if b.depth >= 3:
                b.gone = True
                if rng.random() < 0.5:
                    x, yv, _ = b.pts[-1]
                    self.parts.append([tree.ox + x, tree.oy - yv / ASPECT, rng.uniform(-1, 1), 0.0, 2,
                                       (110, 90, 70), 0.0, False])
            else:
                self.drop_branch(tree, bi)
        # topple
        if not tree.fallen and f >= 0.845:
            u = clamp((f - 0.845) / 0.03)
            tree.phi = tree.dir * (math.pi / 2) * 0.985 * u ** 2.2
            if u >= 1 or self.trunk_hits(tree):
                self.make_log(tree)
                tree.fallen = True
        if tree.fallen and f >= 0.92:
            self.new_tree()
        # clouds
        for c in self.clouds:
            c[0] += dt * w / (self.dayl * 2.8) * c[4]
            if c[0] - c[2] > w + 2:
                nc = self.make_cloud(-c[2] * 1.2 - rng.uniform(0, w * 0.3))
                c[:] = nc
        # falling leaves: from canopy as density drops
        dens = self.leaf_density(f)
        prev = getattr(self, "prev_dens", dens)
        self.prev_dens = dens
        drop = max(0.0, prev - dens)
        if drop > 0 and tree.canopy and len(self.parts) < 500:
            k = drop * len(tree.canopy) * 0.06 * self.density
            nspawn = int(k) + (1 if rng.random() < k - int(k) else 0)
            pal = self.cur_pal[2] if hasattr(self, "cur_pal") else SPECIES["oak"]["summer"]
            for _ in range(nspawn):
                c = rng.choice(tree.canopy)
                self.parts.append([c[2] + 0.5, c[3] + 0.5, rng.uniform(-1.5, 1.5), rng.uniform(2, 5), 0,
                                   gradient(pal, rng.uniform(0.3, 0.9)), 0.0, False])
        # snow
        if self.snowfall > 0 and len(self.parts) < 600:
            k = self.snowfall * w * 0.5 * dt * self.density
            for _ in range(int(k) + (1 if rng.random() < k - int(k) else 0)):
                self.parts.append([rng.uniform(0, w), -0.5, rng.uniform(-1.5, 0.5), rng.uniform(5, 9), 1,
                                   SNOW, 0.0, False])
        self.update_parts(dt)
        self.update_debris(dt)
        self.logs = [lg for lg in self.logs if self.t - lg["born"] < lg["dur"]]

    def leaf_density(self, f):
        decline = smoothstep(0.6, 0.7, f)
        if self.tree.evergreen:
            d = 1.0
        else:
            d = self.sea["dd"]
        return d * (1 - decline)

    def update_sky(self):
        dphase = (self.t / self.dayl + self.day0) % 1.0
        self.dphase = dphase
        e = -math.cos(TAU * dphase)
        self.elev = e
        top, midc, hor = keyed(SKY_KEYS, e)
        tk = self.sky_tk
        self.skyc = (mix(top, scale(self.sky_tint, 0.4), tk), mix(midc, scale(self.sky_tint, 0.7), tk), hor)
        self.L = keyed(LIGHT_KEYS, e)[0]
        self.cloudc = keyed(CLOUD_KEYS, e)
        self.skyB = smoothstep(-0.3, 0.4, e)
        # seasons
        yp = (self.t / self.yearl) % 1.0
        self.yp = yp
        spring_k = 1 - smoothstep(0.12, 0.3, yp)
        autumn_k = smoothstep(0.5, 0.64, yp) * (1 - smoothstep(0.97, 1.0, yp))
        dd = smoothstep(0.0, 0.16, yp) if yp < 0.4 else 1 - smoothstep(0.62, 0.75, yp)
        snow = smoothstep(0.76, 0.8, yp) * (1 - smoothstep(0.94, 0.99, yp))
        if yp < 0.4:
            gh = 0.3 + 0.7 * smoothstep(0.0, 0.25, yp)
        else:
            gh = 1 - 0.45 * smoothstep(0.55, 0.75, yp)
        gh *= 1 - snow
        self.sea = {"spring": spring_k, "autumn": autumn_k, "dd": dd, "snow": snow, "grass": gh}
        self.snowfall = 1.0 if 0.75 < yp < 0.9 else 0.0

    # -- dying ---------------------------------------------------------------------
    def drop_branch(self, tree, bi):
        lines = []
        stack = [bi]
        while stack:
            j = stack.pop()
            b = tree.br[j]
            if b.gone:
                continue
            b.gone = True
            lines.append([(tree.ox + x, tree.oy - yv / ASPECT) for x, yv, r in b.pts[::2] + b.pts[-1:]])
            stack.extend(b.kids)
        pts = [p for ln in lines for p in ln]
        if not pts:
            return
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        rel = [[(x - cx, (y - cy) * ASPECT) for x, y in ln] for ln in lines]
        rng = self.rng
        self.debris.append({"lines": rel, "x": cx, "y": cy, "a": 0.0, "w": rng.uniform(-2.2, 2.2),
                            "vy": 0.0, "vx": rng.uniform(-2, 2), "landed": None, "seed": rng.randrange(1 << 12)})

    def update_debris(self, dt):
        w = self.w
        keep = []
        for d in self.debris:
            if d["landed"] is None:
                d["vy"] += 45 * dt
                d["y"] += d["vy"] * dt
                d["x"] += d["vx"] * dt
                d["a"] += d["w"] * dt
                ca, sa = math.cos(d["a"]), math.sin(d["a"])
                hit = False
                for ln in d["lines"]:
                    for px, pv in ln[::2]:
                        X = d["x"] + px * ca - pv * sa
                        Y = d["y"] + (px * sa + pv * ca) / ASPECT
                        xi = int(clamp(X, 0, w - 1))
                        if Y >= self.gy[xi] - 0.4:
                            hit = True
                            break
                    if hit:
                        break
                if hit or d["y"] > self.h + 5:
                    d["landed"] = self.t
            if d["landed"] is None or self.t - d["landed"] < self.life_base * 0.07:
                keep.append(d)
        self.debris = keep

    def trunk_hits(self, tree):
        cells = tree.raster(1.0, 1.0, 1.0, tree.phi)
        gy = self.gy
        for c in cells.values():
            if c[4] and c[6] >= int(gy[c[5]]):
                return True
        return False

    def make_log(self, tree):
        cells = tree.raster(1.0, 1.0, 1.0, tree.phi)
        w, h = self.w, self.h
        gy = self.gy
        px = tree.ox + tree.pivot[0]
        r0 = max(1.0, tree.r0)
        cols = {}
        for c in cells.values():
            if c[4]:
                cols.setdefault(c[5], []).append(c)
        out = []
        rng = self.rng
        for X, cs in cols.items():
            maxY = max(c[6] for c in cs)
            minY = min(c[6] for c in cs)
            target = int(gy[X]) - 1 - maxY
            k = clamp((abs(X - px) - r0) / (2 * r0))
            sh = int(round(target * k))
            for c in cs:
                Y = c[6] + sh
                if not (0 <= Y < h):
                    continue
                if maxY == minY:
                    ch = "="
                elif c[6] == minY:
                    ch = "_"
                elif c[6] == maxY:
                    ch = "="
                else:
                    ch = "=" if hsh(X, Y, 3) < 0.6 else "-" if hsh(X, Y, 4) < 0.6 else "~"
                out.append([X, Y, ch, c[2], hsh(X, Y, 11), 1])
        if out:
            xs = [o[0] for o in out]
            far = max(xs) if tree.dir > 0 else min(xs)
            near = min(xs) if tree.dir > 0 else max(xs)
            for o in out:
                if o[0] == far:
                    o[2] = ")" if tree.dir > 0 else "("
                    o[5] = 2
                elif o[0] == near and o[2] != "_":
                    o[2] = "(" if tree.dir > 0 else ")"
                    o[5] = 2
        # stump
        stump = [c for c in cells.values() if not c[4]]
        if stump:
            top = min(c[6] for c in stump if True)
            for c in stump:
                ch = c[1]
                kind = 0
                if c[6] == top and c[1] in "|:":
                    ch, kind = "_", 2
                out.append([c[5], c[6], ch, c[2], hsh(c[5], c[6], 11), kind])
        self.logs.append({"cells": out, "born": self.t, "dur": self.life_base * 0.24, "bark": tree.G["bark"]})
        # dust
        for o in out[:: max(1, len(out) // 30)]:
            self.parts.append([o[0] + 0.5, o[1] + 0.5, rng.uniform(-3, 3), rng.uniform(-4, -1), 3,
                               (150, 130, 100), 0.0, False])

    def update_parts(self, dt):
        w = self.w
        gy = self.gy
        keep = []
        t = self.t
        for p in self.parts:
            if p[7]:
                p[6] += dt
                if p[6] < (2.5 if p[4] == 0 else 0.4):
                    keep.append(p)
                continue
            p[6] += dt
            kind = p[4]
            if kind == 3:      # dust
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[3] += 3 * dt
                if p[6] < 1.2:
                    keep.append(p)
                continue
            p[0] += (p[2] + math.sin(t * 3 + p[6] * 4 + p[1]) * 1.5) * dt
            p[1] += p[3] * dt
            xi = int(p[0])
            if xi < 0 or xi >= w or p[1] > self.h:
                continue
            if p[1] >= gy[xi] - 0.3:
                p[1] = gy[xi] - 0.6
                p[7] = True
                p[6] = 0.0
            keep.append(p)
        self.parts = keep

    # -- palettes ---------------------------------------------------------------------
    def palette(self):
        h = self.h
        NS = self.NS
        top, midc, hor = self.skyc
        B = self.skyB
        L = self.L
        sea = self.sea
        hm = self.hmean
        P = [None] * NS
        bright = 0.55 + 0.45 * B
        for y in range(h):
            f = clamp(y / hm)
            P[y] = qc(scale(gradient((top, midc, hor), f ** 0.85), bright))
        snow = sea["snow"]
        far = mix(hor, mul(self.far_col, L), 0.55)
        P[self.FE] = qc(mix(mix(far, hor, 0.35), mul(SNOW, L), 0.5 * snow))
        P[self.FF] = qc(scale(far, 0.45))
        P[self.FF2] = qc(scale(far, 0.32))
        near = mix(mul(self.near_col, L), hor, 0.15)
        P[self.NE] = qc(mix(scale(near, 1.3), mul(SNOW, L), 0.6 * snow))
        P[self.NF] = qc(scale(near, 0.65))
        P[self.NT] = qc(mix(scale(near, 1.1), mul(SNOW, L), 0.3 * snow))
        g0, g1, g2 = self.grass
        gs = mix(mix(g0, g1, 1 - sea["spring"]), g2, sea["autumn"])
        top_c = mix(gs, SNOW, snow)
        P[self.GE] = qc(mul(top_c, L))
        deep = mix(scale(gs, 0.45), (40, 30, 22), 0.4)
        for band in range(4):
            f = band / 3
            c = mix(mix(gs, SNOW, snow * (1 - f * 0.7)), deep, 0.25 + 0.6 * f)
            P[self.G0 + band * 2] = qc(mul(scale(c, 0.62 - 0.3 * f), L))
            P[self.G0 + band * 2 + 1] = qc(mul(scale(mix(c, (110, 90, 50), 0.3), 0.55 - 0.25 * f), L))
        P1 = list(P)
        P2 = list(P)
        for k in range(self.FE, NS):
            P1[k] = qc(scale(P[k], 0.72))
            P2[k] = qc(scale(P[k], 0.5))
        return P + P1 + P2

    def leaf_palettes(self, f):
        G = self.tree.G
        sea = self.sea
        base = [mix(a, b, 1 - sea["spring"]) for a, b in zip(G["spring"], G["summer"])]
        decline = smoothstep(0.58, 0.7, f)
        pals = []
        for b in range(4):
            if G["autumn"] is None:
                p = base
            else:
                k = clamp(sea["autumn"] * 1.6 - b * 0.2)
                p = [mix(x, y, k) for x, y in zip(base, G["autumn"])]
            if decline > 0:
                p = [mix(x, y, decline * 0.8) for x, y in zip(p, DEAD)]
            pals.append(p)
        self.cur_pal = pals
        return pals

    # -- drawing -----------------------------------------------------------------------
    def draw(self, cv):
        w, h = self.w, self.h
        if cv.w != w or cv.h != h:
            return
        t = self.t
        L = self.L
        tree = self.tree
        f, g = self.growth()
        # background
        P = self.palette()
        NS = self.NS
        day = smoothstep(0.02, 0.2, self.elev)
        cover = [0.0] * w
        if day > 0:
            sunx = self.sun_x()
            for c in self.clouds:
                off = (c[0] - sunx) * 0.15
                x0 = int(c[0] - c[2] * 0.55 + off)
                x1 = int(c[0] + c[2] * 0.55 + off)
                for x in range(max(0, x0), min(w, x1 + 1)):
                    edge = min(x - x0, x1 - x) / 2.0
                    cover[x] += clamp(edge) * c[4]
        O = [0] * w
        for x in range(w):
            k = cover[x] * day
            O[x] = 2 * NS if k > 0.7 else NS if k > 0.25 else 0
        k = int(round(self.skyB * 5))
        cv.ch[:] = self.bg_chars(cv.ramp, k)
        cv.lv[:] = self.bg_lv
        cv.fg[:] = [P[c + O[x]] for c, x in zip(self.bg_cls, self.bg_x)]
        self.draw_stars(cv)
        self.draw_orbs(cv)
        self.draw_clouds(cv)
        self.draw_grass(cv)
        self.draw_flowers(cv)
        self.draw_logs(cv)
        if not tree.fallen:
            s = 0.06 + 0.94 * g ** 0.9
            thick = 0.35 + 0.65 * g
            self.draw_tree(cv, f, g, s, thick)
        self.draw_debris(cv)
        self.draw_parts(cv)

    def sun_x(self):
        return self.w * 0.5 + self.w * 0.48 * math.sin(TAU * (self.dphase - 0.5))

    def draw_orbs(self, cv):
        w, h = self.w, self.h
        hm = self.hmean
        r = clamp(h * 0.07, 1.5, 4.5)
        for which in (0, 1):
            dp = (self.dphase + 0.5 * which) % 1.0
            e = -math.cos(TAU * dp)
            if e < -0.1:
                continue
            cx = w * 0.5 + w * 0.48 * math.sin(TAU * (dp - 0.5))
            cy = hm - (hm - h * 0.08) * e
            if which == 0:
                col = gradient([(255, 110, 50), (255, 190, 110), (255, 245, 215)], clamp(e * 2.5 + 0.2))
                R = r * 4.5
                gk = 0.8
            else:
                col = (225, 232, 255)
                R = r * 2.4
                gk = 0.35
            rr = r if which == 0 else r * 0.75
            for y in range(max(0, int(cy - R / ASPECT) - 1), min(h, int(cy + R / ASPECT) + 2)):
                for x in range(max(0, int(cx - R) - 1), min(w, int(cx + R) + 2)):
                    if y >= self.sky_edge[x] - 0.3 or y >= int(self.sky_edge[x]):
                        continue
                    ch, d = disc_glyph(x, y, cx, cy, rr)
                    i = y * w + x
                    if ch:
                        if which == 1:
                            cr = clamp(noise2(x * 0.6, y * 1.1, 77))
                            c = mix(col, (150, 160, 200), 0.5 * cr)
                        else:
                            c = mix(col, (255, 255, 240), 0.5 * (1 - min(1.0, d)))
                        cv.ch[i] = ch
                        cv.fg[i] = qc(c)
                        cv.lv[i] = 1.0
                    else:
                        gv = (R / rr - d) / (R / rr - 1)
                        if gv <= 0:
                            continue
                        gv = gv * gv * gk
                        old = cv.fg[i]
                        if old is None:
                            old = (0, 0, 0)
                        cv.fg[i] = qc(mix(old, col, clamp(gv)))
                        if cv.ch[i] == " " and gv > 0.12:
                            cv.ch[i] = "·" if gv > 0.3 else "."
                        elif gv > 0.45:
                            cv.ch[i] = ":"

    def draw_stars(self, cv):
        k = smoothstep(-0.02, -0.25, self.elev)
        if k <= 0:
            return
        w = self.w
        t = self.t
        cx, cy = self.pole
        ang = (self.t / self.dayl) * TAU * 0.04
        ca, sa = math.cos(ang), math.sin(ang)
        edge = self.sky_edge
        for x, y, b, ph in self.stars:
            dx, dy = x - cx, (y - cy) * ASPECT
            X = cx + dx * ca - dy * sa
            Y = cy + (dx * sa + dy * ca) / ASPECT
            xi, yi = int(X), int(Y)
            if 0 <= xi < w and 0 <= yi < edge[xi] - 1:
                tw = 0.6 + 0.4 * math.sin(t * 3 + ph)
                v = b * tw * k
                ch = "*" if v > 0.75 else "+" if v > 0.6 else "·" if v > 0.35 else "."
                i = yi * w + xi
                cv.ch[i] = ch
                cv.fg[i] = qc(scale((230, 235, 255), 0.3 + 0.7 * v))

    def draw_clouds(self, cv):
        w = self.w
        lit, shade = self.cloudc
        ramp = CLOUD_RAMP
        nr = len(ramp) - 1
        tab = [qc(mix(shade, lit, j / 5)) for j in range(6)]
        edge = self.sky_edge
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        for cx, cy, cw, cells, op in self.clouds:
            for dx, dy, lev, light in cells:
                X = int(cx + dx)
                Y = int(cy + dy)
                if 0 <= X < w and 0 <= Y < edge[X] - 0.5:
                    v = lev * op * 0.9
                    idx = int(clamp(v) * nr + 0.5)
                    if idx <= 0:
                        continue
                    i = Y * w + X
                    if idx < nr and hsh(X - int(cx), Y, 61) < 0.5:
                        idx += 1
                    ch[i] = ramp[idx]
                    fg[i] = tab[int(light * 5)] if v > 0.3 else qc(scale(tab[int(light * 5)], 0.4 + v * 2))
                    lv[i] = v

    def draw_grass(self, cv):
        w, h = self.w, self.h
        sea = self.sea
        gh = sea["grass"]
        if gh <= 0.05:
            return
        L = self.L
        g0, g1, g2 = self.grass
        base = mix(mix(g0, g1, 1 - sea["spring"]), g2, sea["autumn"])
        cols = [qc(mul(mix(base, (230, 240, 140), 0.12 * j), L)) for j in range(5)]
        t = self.t
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        for x in range(w):
            n = self.bh[x] * gh
            if n < 0.5:
                continue
            y = int(self.gy[x]) - 1
            if not (0 <= y < h):
                continue
            hue = self.bhue[x]
            lean = math.sin(t * 2.3 + x * 0.33 + self.bph[x])
            if n > 1.6:
                c = "/" if lean > 0.6 else "\\" if lean < -0.6 else "|"
            elif n > 1.0:
                c = '"' if hue < 0.5 else "'"
            else:
                c = "," if hue < 0.6 else "."
            i = y * w + x
            ch[i] = c
            fg[i] = cols[int(hue * 4.99)]
            lv[i] = 0.4

    def draw_flowers(self, cv):
        w, h = self.w, self.h
        yp = self.yp
        L = self.L
        for x, t0, t1, col, ph in self.flowers:
            if yp < t0 or yp > t1 + 0.08:
                continue
            gy = int(self.gy[x])
            open_k = clamp((yp - t0) / 0.06)
            wilt = clamp((yp - t1) / 0.08)
            stem = qc(mul(mix((60, 150, 60), (120, 100, 50), wilt), L))
            if 0 <= gy - 1 < h:
                i = (gy - 1) * w + x
                cv.ch[i] = "|"
                cv.fg[i] = stem
            y = gy - 2
            if 0 <= y < h:
                i = y * w + x
                cv.ch[i] = "." if open_k < 0.3 or wilt > 0.6 else "o" if open_k < 0.7 else ("*" if ph < 0.5 else "@")
                cv.fg[i] = qc(mul(mix(col, (110, 80, 40), wilt), L))
                cv.lv[i] = 0.8

    def draw_logs(self, cv):
        w = self.w
        L = self.L
        for lg in self.logs:
            dcy = (self.t - lg["born"]) / lg["dur"]
            bark = lg["bark"]
            grey = [mix(c, (120, 116, 110), 0.6) for c in bark]
            rot = mix(grey[2], (64, 50, 38), clamp(dcy * 1.5))
            for X, Y, ch, lk, rv, kind in lg["cells"]:
                if rv < dcy * 1.15 - 0.1:
                    continue
                i = Y * w + X
                if kind == 2:
                    c = mix(CUT, (90, 70, 50), clamp(dcy * 1.4))
                else:
                    c = mix(gradient(grey, 0.15 + 0.7 * (lk if lk < 10 else 2) / 9), rot, clamp(dcy * 1.2))
                cc = ch
                if dcy > 0.15 and hsh(X, Y, 23) < 0.45 * dcy:
                    c = mix(MOSS, (150, 190, 80), hsh(X, Y, 24))
                    cc = "," if hsh(X, Y, 25) < 0.5 else '"'
                if rv < dcy * 1.15 + 0.08:
                    cc = "." if hsh(X, Y, 26) < 0.6 else ","
                cv.ch[i] = cc
                cv.fg[i] = qc(mul(c, L))
                cv.lv[i] = 0.6

    def draw_tree(self, cv, f, g, s, thick):
        tree = self.tree
        w, h = self.w, self.h
        L = self.L
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        # seed
        if f < 0.012:
            gy = int(self.gy[int(clamp(self.tx, 0, w - 1))])
            if 0 <= gy - 1 < h:
                i = (gy - 1) * w + self.tx
                ch[i] = "o" if f > 0.006 else "."
                fg[i] = qc(mul((170, 120, 70), L))
            if f < 0.006:
                return
        if f < 0.07:
            # a seedling: stem and two leaves, drawn until the sapling outgrows it
            gy = int(self.gy[int(clamp(self.tx, 0, w - 1))])
            k = 1 + int(clamp((f - 0.006) / 0.03) * 2)
            leaf = qc(mul((120, 220, 90), L))
            stem = qc(mul((90, 170, 70), L))
            x = self.tx
            for j in range(k):
                y = gy - 1 - j
                if 0 <= y < h and 0 <= x < w:
                    ch[y * w + x] = "|"
                    fg[y * w + x] = stem
            y = gy - 1 - k
            if 0 <= y < h:
                for dx, c in ((-1, "\\"), (0, "'"), (1, "/")):
                    if 0 <= x + dx < w:
                        ch[y * w + x + dx] = c
                        fg[y * w + x + dx] = leaf
            if f < 0.03:
                return
        grey = smoothstep(0.66, 0.84, f)
        bark = tree.G["bark"]
        if grey > 0:
            bark = [mix(c, (130, 128, 124), grey * 0.85) for c in bark]
        tab = [qc(mul(gradient(bark, 0.12 + 0.75 * k / 9), L)) for k in range(10)]
        tab.append(qc(mul((34, 30, 28), L)))
        snow = self.sea["snow"]
        stab = [qc(mix(c, mul(SNOW, L), snow * 0.8)) for c in tab]
        for i, c, lk, top in tree.wood(g, s, thick, tree.phi):
            ch[i] = c
            fg[i] = stab[lk] if top else tab[lk]
            lv[i] = 0.7
        dens = self.leaf_density(f)
        if dens <= 0.001:
            return
        pals = self.leaf_palettes(f)
        ramp = cv.ramp if cv.ramp != RAMPS["ascii"] else LEAFY
        nr = len(ramp) - 1
        tables = []
        for p in pals:
            rows = []
            for lk in range(10):
                base = mul(gradient(p, lk / 9), L)
                rows.append([qc(scale(base, 0.35 + 0.65 * j / nr)) for j in range(nr + 1)])
            tables.append(rows)
        evs = tree.evergreen
        snowt = None
        if evs and snow > 0:
            sn = mul(SNOW, L)
            snowt = [qc(mix(scale(sn, 0.6 + 0.4 * j / nr), sn, 0.3)) for j in range(nr + 1)]
        t = self.t
        RT = [int(round(1.2 * math.sin(t * 2.5 + k * 0.785))) for k in range(8)]
        full = s >= 0.999
        ox, oy = tree.ox, tree.oy
        for rx, ry, X, Y, level, lk, rv, birth, dist, bk, ph, hi in tree.canopy:
            if rv > dens:
                continue
            if not full:
                if g < birth or (g - birth) * 9 < dist:
                    continue
                X = int(ox + rx * s)
                Y = int(oy + ry * s)
                if not (0 <= X < w and 0 <= Y < h):
                    continue
            i = Y * w + X
            j = int(level * nr + 0.5)
            if j <= 0:
                continue
            ch[i] = ramp[j]
            if snowt is not None and hi and rv < snow:
                fg[i] = snowt[j]
            else:
                k2 = lk + RT[ph]
                k2 = 0 if k2 < 0 else 9 if k2 > 9 else k2
                fg[i] = tables[bk][k2][j]
            lv[i] = level
        if tree.strands:
            self.draw_strands(cv, tree, g, s, dens, tables, nr)

    def draw_strands(self, cv, tree, g, s, dens, tables, nr):
        w, h = self.w, self.h
        t = self.t
        ox, oy = tree.ox, tree.oy
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        glyphs = "|!:;|'"
        for x0, yv, rows, bi, frac, birth, ph in tree.strands:
            if g < birth:
                continue
            grow = clamp((g - birth) * 6) * (0.25 + 0.75 * dens)
            n = int(rows * grow * s)
            if n <= 0:
                continue
            Y0 = oy - yv * s / ASPECT
            X0 = ox + x0 * s
            px = X0
            seedk = int(x0 * 7) & 0xFFF
            for k in range(n):
                sw = math.sin(t * 1.4 + ph + k * 0.22) * k * 0.05
                X = X0 + sw
                Y = int(Y0 + k)
                xi = int(X)
                if not (0 <= xi < w and 0 <= Y < h):
                    px = X
                    continue
                r = hsh(seedk, k, 9)
                if r > dens * 1.05 + 0.05:
                    px = X
                    continue
                dx = X - px
                px = X
                c = "/" if dx < -0.35 else "\\" if dx > 0.35 else glyphs[int(r * 5.99)]
                f = k / max(1, n)
                lk = int(clamp(0.85 - 0.5 * f + 0.15 * (r - 0.5)) * 9)
                j = int(clamp(0.75 - 0.3 * f) * nr + 0.5)
                i = Y * w + xi
                ch[i] = c
                fg[i] = tables[int(r * 3.99)][lk][j]
                lv[i] = 0.6

    def draw_debris(self, cv):
        w, h = self.w, self.h
        bark = [mix(c, (130, 128, 124), 0.7) for c in self.tree.G["bark"]]
        L = self.L
        col = qc(mul(gradient(bark, 0.55), L))
        for d in self.debris:
            ca, sa = math.cos(d["a"]), math.sin(d["a"])
            crumble = 0.0
            if d["landed"] is not None:
                crumble = (self.t - d["landed"]) / (self.life_base * 0.07)
            sd = d["seed"]
            for li, ln in enumerate(d["lines"]):
                sp = [(d["x"] + px * ca - pv * sa, d["y"] + (px * sa + pv * ca) / ASPECT) for px, pv in ln]
                n = len(sp)
                for k in range(n):
                    if crumble > 0 and hsh(sd + li, k, 13) < crumble:
                        continue
                    X, Y = sp[k]
                    a = sp[k - 1] if k else sp[k]
                    c = sp[k + 1] if k + 1 < n else sp[k]
                    xi, yi = int(X), int(Y)
                    if 0 <= xi < w and 0 <= yi < h:
                        i = yi * w + xi
                        cv.ch[i] = wood_glyph(c[0] - a[0], c[1] - a[1])
                        cv.fg[i] = col
                        cv.lv[i] = 0.6

    def draw_parts(self, cv):
        w, h = self.w, self.h
        L = self.L
        for x, y, vx, vy, kind, col, age, landed in self.parts:
            xi, yi = int(x), int(y)
            if not (0 <= xi < w and 0 <= yi < h):
                continue
            i = yi * w + xi
            if kind == 0:
                k = clamp(1 - (age - 1.5)) if landed else 1.0
                c = "." if landed else "',`."[int(age * 6 + x) % 4]
                cv.ch[i] = c
                cv.fg[i] = qc(mul(scale(col, 0.9 * k), L))
            elif kind == 1:
                cv.ch[i] = "*" if (int(x * 3 + y) % 5 == 0) else "."
                cv.fg[i] = qc(mul(SNOW, L))
            elif kind == 2:
                cv.ch[i] = "."
                cv.fg[i] = qc(mul(col, L))
            else:
                k = clamp(1 - age / 1.2)
                cv.ch[i] = "." if age > 0.5 else ":"
                cv.fg[i] = qc(mul(scale(col, k), L))
