"""A kneeling armored knight, his red cape streaming in the wind, ash drifting past.

Inspired by @arimecoa's "ASCII but make it cool" reel: silver plate rendered in pure density
shading under a hard side light, with one splash of color.

How it is built:
  * The knight is ~40 parts (circles, ellipses, tapered capsules and trapezoids) stacked front to
    back like cut-out plates. Each cell shows the front-most part covering it and is lit as if that
    part were a curved metal plate: a diffuse term, a sharp specular highlight, a cool rim light
    from behind and a faint "horizon" reflection, which is what makes steel read as steel. Back
    plates get dark seams where front plates overlap them, and front parts cast short shadows.
    He doesn't move, so all of that is computed once (on start or resize) and copied each frame.
  * The cape is real cloth: a grid of verlet points pinned behind his neck, pushed by wind, gusts
    and gravity, held together by distance constraints, and drawn as shaded triangles. Where the
    cloth folds edge-on it gets darker; where it turns its back to you, you see the darker lining.
  * Ash and embers ride the same wind; the pointer is the wind source and a click is a gust.
"""
import math

from ..engine import ASPECT, Canvas, Scene, clamp, mix, noise1, noise2, scale
from ..shapes import sd_capsule, sd_circle, sd_ellipse

TAU = math.tau
WHITE = (255, 255, 255)

CAPES = {
    "red": ((214, 28, 36), (255, 96, 80), (110, 10, 22)),
    "crimson": ((170, 14, 44), (240, 70, 90), (80, 6, 24)),
    "blue": ((40, 70, 190), (110, 150, 255), (16, 26, 90)),
    "gold": ((222, 160, 40), (255, 222, 120), (110, 70, 14)),
}
#           base color         amb   kd    ks   shininess
MATERIALS = {
    "plate": ((196, 204, 218), 0.05, 1.2, 0.95, 26),
    "dark": ((150, 156, 170), 0.04, 0.95, 1.05, 34),     # blackened steel: dim body, hot highlights
    "mail": ((150, 156, 168), 0.05, 0.95, 0.30, 6),
    "gold": ((238, 186, 82), 0.06, 1.0, 0.80, 18),
    "blade": ((222, 230, 244), 0.08, 0.85, 1.25, 44),
    "cloth": ((92, 94, 106), 0.04, 0.62, 0.05, 4),
    "leather": ((118, 104, 96), 0.04, 0.75, 0.15, 6),
    "void": ((0, 0, 0), 0.0, 0.0, 0.0, 1),
}


def sd_trap(px, py, cx, cy, r1, r2, he, ca, sa, rr):
    """Rounded isosceles trapezoid: half-width r1 at the bottom, r2 at the top, half-height he.
    (ca, sa) rotate it; 'up' is screen-up when unrotated."""
    dx, dy = px - cx, py - cy
    x = abs(dx * ca + dy * sa)
    y = dx * sa - dy * ca
    cax = x - min(x, r1 if y < 0 else r2)
    cay = abs(y) - he
    k2x, k2y = r2 - r1, 2 * he
    kk = k2x * k2x + k2y * k2y
    t = ((r2 - x) * k2x + (he - y) * k2y) / kk if kk else 0.0
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    cbx = x - r2 + k2x * t
    cby = y - he + k2y * t
    s = -1.0 if (cbx < 0 and cay < 0) else 1.0
    return s * math.sqrt(min(cax * cax + cay * cay, cbx * cbx + cby * cby)) - rr


class Part:
    __slots__ = ("f", "box", "mat", "thick", "prof", "trim", "tex", "tint", "dim")

    def __init__(self, f, box, mat, thick, prof=1.4, trim=False, tex=None, tint=None, dim=1.0):
        self.f, self.box, self.mat, self.thick, self.prof = f, box, mat, thick, prof
        self.trim, self.tex, self.tint, self.dim = trim, tex, tint, dim


class Knight(Scene):
    name = "knight"
    title = "Kneeling Knight"
    blurb = "a kneeling knight in silver plate, his red cape streaming in a wind full of ash"
    tags = ("fantasy", "ascii-art", "dramatic", "night")
    interactions = "point to steer the wind, click for a gust"
    options = {
        "armor": ("random", "random, plate, ornate, mail or dark"),
        "helm": ("random", "random, great, bascinet, sallet or armet"),
        "cape": ("random", "random, red, crimson, blue or gold"),
        "sword": ("random", "random, long, broad, cross or wavy"),
        "ash": (1.0, "amount of drifting ash and embers"),
        "wind": (1.0, "wind strength"),
        "ruins": (True, "ruined pillars and the moon in the background"),
    }

    # ------------------------------------------------------------------ genome
    def setup(self):
        rng = self.rng
        w, h = self.w, self.h

        def pick(key, choices, weights=None):
            v = self.opt(key)
            if v in choices:
                return v
            return rng.choices(choices, weights=weights)[0]

        g = self.g = {}
        g["armor"] = pick("armor", ["plate", "ornate", "mail", "dark"], [45, 25, 18, 12])
        g["helm"] = pick("helm", ["great", "bascinet", "sallet", "armet"])
        g["cape"] = pick("cape", list(CAPES), [55, 20, 12, 13])
        g["sword"] = pick("sword", ["long", "broad", "cross", "wavy"], [35, 25, 25, 15])
        g["facing"] = rng.choice((-1, 1))          # which knee is raised
        g["light"] = g["facing"] * (1 if rng.random() < 0.8 else -1)   # key light: in front, or behind him
        g["plume"] = rng.random() < 0.35
        g["scarf"] = rng.random() < 0.55
        g["eyes"] = rng.random() < 0.5
        g["bulk"] = rng.uniform(0.92, 1.1)
        g["sword_x"] = rng.uniform(0.33, 0.36)
        g["hand_v"] = rng.uniform(0.6, 0.64)
        g["bow"] = rng.uniform(0.0, 0.2)
        g["pauldron"] = rng.uniform(0.9, 1.3)
        g["lames"] = rng.randint(2, 4)
        g["ridge"] = rng.random() < 0.6
        g["cape_len"] = rng.uniform(1.05, 1.5)
        g["tatter"] = rng.uniform(0.0, 0.35)
        g["moon"] = rng.choice(("full", "full", "crescent", "none"))
        g["pillars"] = rng.randint(0, 4)
        g["arch"] = rng.random() < 0.3
        g["hills"] = rng.random() < 0.6
        g["wind_dir"] = -g["facing"]          # blowing into his face, the cape streams behind
        self.cape_cols = CAPES[g["cape"]]

        # layout: the knight kneels a little off-center, upwind, so the cape has room to stream
        H = h * ASPECT
        self.gy = H * (0.86 if h >= 14 else 0.92)            # ground line, stretched units
        S = min(self.gy * 0.92, w * 1.3)
        self.S = S
        self.cx = w * 0.5 - g["wind_dir"] * min(w * 0.12, S * 0.2) - g["facing"] * S * 0.05
        lx, ly, lz = g["light"] * 0.7, -0.45, 0.58
        n = math.sqrt(lx * lx + ly * ly + lz * lz)
        self.L = (lx / n, ly / n, lz / n)
        hx, hy, hz = self.L[0], self.L[1], self.L[2] + 1.0
        n = math.sqrt(hx * hx + hy * hy + hz * hz)
        self.Hv = (hx / n, hy / n, hz / n)
        rx, ry, rz = -g["light"] * 0.85, -0.25, 0.25
        n = math.sqrt(rx * rx + ry * ry + rz * rz)
        self.R = (rx / n, ry / n, rz / n)

        self.parts = []
        self.build_knight()
        self.static = None          # (ramp, ch, fg, lv, bc), rendered lazily for the active ramp
        self.cells = []             # cached (x, y, v, color, char, mode) for the static layer
        self.mask = [False] * (w * h)
        self.render_knight()
        self.render_background()

        # wind state
        self.wind = [g["wind_dir"] * 1.0, -0.05]
        self.gust = 0.0
        self.gust_dir = (g["wind_dir"], 0.0)
        self.build_cloth()
        # ash and embers
        self.ash = []
        na = int(self.count(70) * max(0.0, self.opt("ash")))
        for _ in range(na):
            self.ash.append(self.new_ash(rng.uniform(0, w), rng.uniform(0, h)))
        self.streaks = [[rng.uniform(0, w), rng.uniform(0, self.gy / ASPECT * 0.95), rng.uniform(4, 12),
                         rng.uniform(0.7, 1.3), rng.uniform(0, TAU)] for _ in range(max(2, self.count(9)))]
        self.grass = [(rng.uniform(0, w), rng.uniform(0.0, 1.0), rng.randint(1, 2), rng.uniform(0, TAU))
                      for _ in range(max(3, int(w * 0.14)))]
        self.flash = 0.0

    # ------------------------------------------------------------------ knight geometry
    def X(self, u):
        return self.cx + self.g["facing"] * u * self.S

    def Y(self, v):
        return self.gy - v * self.S

    def _add(self, f, box, mat, thick, **kw):
        self.parts.append(Part(f, box, mat, max(0.6, thick), **kw))

    def circ(self, u, v, r, mat, **kw):
        x, y, rr = self.X(u), self.Y(v), r * self.S
        self._add(lambda px, py: sd_circle(px, py, x, y, rr), (x - rr, y - rr, x + rr, y + rr), mat, rr, **kw)

    def ell(self, u, v, ru, rv, a, mat, **kw):
        x, y = self.X(u), self.Y(v)
        rx, ry = ru * self.S, rv * self.S
        ang = math.atan2(-self.g["facing"] * math.sin(a), math.cos(a))
        m = max(rx, ry)
        self._add(lambda px, py: sd_ellipse(px, py, x, y, rx, ry, ang), (x - m, y - m, x + m, y + m), mat,
                  min(rx, ry), **kw)

    def cap(self, u0, v0, u1, v1, r0, r1, mat, **kw):
        x0, y0, x1, y1 = self.X(u0), self.Y(v0), self.X(u1), self.Y(v1)
        a, b = r0 * self.S, r1 * self.S
        m = max(a, b)
        self._add(lambda px, py: sd_capsule(px, py, x0, y0, x1, y1, a, b),
                  (min(x0, x1) - m, min(y0, y1) - m, max(x0, x1) + m, max(y0, y1) + m), mat, min(a, b) + 0.3,
                  **kw)

    def trap(self, u, v, wb, wt, hh, mat, a=0.0, r=0.0, **kw):
        x, y = self.X(u), self.Y(v)
        S = self.S
        r1, r2, he, rr = wb * S, wt * S, hh * S, r * S
        ang = math.atan2(-self.g["facing"] * math.sin(a), math.cos(a))
        ca, sa = math.cos(ang), math.sin(ang)
        m = math.hypot(max(r1, r2), he) + rr
        self._add(lambda px, py: sd_trap(px, py, x, y, r1, r2, he, ca, sa, rr), (x - m, y - m, x + m, y + m), mat,
                  min(max(r1, r2), he) + rr, **kw)

    def build_knight(self):
        """The knight in profile, facing +u. Parts are added back to front."""
        g = self.g
        armor = g["armor"]
        P = "dark" if armor == "dark" else "plate"
        trim = armor == "ornate"
        mail = armor == "mail"
        bk = g["bulk"]
        pk = g["pauldron"]
        knot = self.cape_cols[0]
        arm = "mail" if mail else P
        sx = g["sword_x"]
        hand_v = g["hand_v"]

        # --- far arm (behind the body, in shadow), reaching for the pommel
        self.cap(-0.005, 0.735, 0.19, 0.59, 0.038, 0.034, arm, prof=1.1, dim=0.6)
        self.circ(0.19, 0.59, 0.038, P, prof=0.9, dim=0.6)
        self.cap(0.19, 0.59, sx - 0.02, hand_v + 0.035, 0.032, 0.027, arm, prof=1.1, dim=0.6)
        self.ell(sx + 0.005, hand_v + 0.04, 0.042, 0.026, 0.25, P, prof=1.0, dim=0.6)
        # --- the kneeling leg (far side): thigh down to the knee on the ground, shin running back
        self.cap(-0.08, 0.4, -0.01, 0.075, 0.07 * bk, 0.05, "mail" if mail else P, prof=1.2, dim=0.6)  # cuisse
        self.cap(-0.02, 0.05, -0.31, 0.05, 0.046, 0.034, P, prof=1.0, dim=0.6)  # greave
        self.cap(-0.31, 0.05, -0.375, 0.012, 0.03, 0.02, P, prof=1.0, dim=0.6)  # toes down
        self.circ(-0.305, 0.055, 0.032, P, prof=1.0, dim=0.6)
        self.circ(0.0, 0.06, 0.052, P, prof=0.85, trim=trim, dim=0.6)  # knee cop
        # mail skirt under the faulds
        self.ell(-0.03, 0.42, 0.13 * bk, 0.05, -0.1, "mail", prof=2.0)
        # --- the raised leg (near side): thigh forward, knee up, shin straight down, foot flat
        knee_u, knee_v = 0.235, 0.355
        self.cap(knee_u - 0.005, knee_v - 0.02, knee_u - 0.025, 0.07, 0.05, 0.034, P, prof=1.0)       # greave
        self.cap(knee_u - 0.06, 0.03, knee_u + 0.08, 0.022, 0.03, 0.022, P, prof=1.0)                 # sabaton
        self.circ(knee_u - 0.03, 0.05, 0.03, P, prof=1.0)                                            # ankle
        self.cap(-0.04, 0.4, knee_u, knee_v, 0.08 * bk, 0.06, "mail" if mail else P, prof=1.2)      # cuisse
        self.circ(knee_u + 0.012, knee_v, 0.064, P, prof=0.8, trim=trim)                             # knee cop
        self.ell(knee_u - 0.02, knee_v - 0.05, 0.042, 0.025, 0.6, P, prof=1.0, trim=trim)            # fan
        # --- torso: backplate, breastplate bulging forward, faulds, tasset over the thigh
        self.ell(-0.045, 0.63, 0.1 * bk, 0.15, 0.06, "cloth", prof=2.0)
        for k in range(3):
            self.ell(-0.02 + 0.006 * k, 0.505 - k * 0.032, (0.112 + 0.01 * k) * bk, 0.024, -0.12, P,
                     prof=2.0, trim=trim and k == 2)
        self.trap(0.03, 0.41, 0.06, 0.05, 0.05, P, a=0.25, r=0.01, prof=1.8, trim=trim)          # tasset
        self.ell(-0.015, 0.645, 0.115 * bk, 0.14, 0.08, "mail" if mail else P, prof=1.3,
                 trim=trim and not mail)                                                         # breastplate
        if mail:
            self.ell(0.0, 0.62, 0.09 * bk, 0.12, 0.08, "cloth", prof=2.5)                       # surcoat
            self.cap(-0.11 * bk, 0.535, 0.1 * bk, 0.53, 0.013, 0.013, "leather", prof=1.0)       # belt
        else:
            self.ell(-0.005, 0.555, 0.1 * bk, 0.045, -0.05, P, prof=1.6, trim=trim)              # plackart
            if g["ridge"]:
                self.cap(0.055 * bk, 0.56, 0.085 * bk, 0.7, 0.008, 0.006, P, prof=0.6)
        # gorget and the scarf knot at the throat
        self.ell(0.0, 0.79, 0.062, 0.036, 0.15, "mail" if mail else P, prof=1.2, trim=trim)
        self.ell(0.045, 0.785, 0.03, 0.022, 0.4, "cloth", prof=1.0, tint=knot)
        # --- the helmet, head bowed toward the hilt
        hu, hv = 0.055, 0.87
        tilt = -0.38 - g["bow"]

        def R(u, v):
            c, s_ = math.cos(tilt), math.sin(tilt)
            return hu + u * c - v * s_, hv + u * s_ + v * c

        helm = g["helm"]
        if helm == "great":
            self.trap(hu, hv, 0.07, 0.066, 0.075, P, a=tilt, r=0.014, prof=1.6, trim=trim)
            a0, a1 = R(0.035, 0.012), R(0.08, 0.012)
            self.cap(*a0, *a1, 0.0055, 0.0055, "void")
            for k in range(3):
                for j in range(2):
                    self.circ(*R(0.045 + j * 0.015, -0.025 - k * 0.013), 0.0035, "void")
            self.cap(*R(-0.075, 0.03), *R(0.084, 0.03), 0.006, 0.006, P, prof=0.6)          # brow band
        elif helm == "bascinet":
            self.ell(*R(-0.01, 0.01), 0.072, 0.08, tilt, P, prof=0.9, trim=trim)
            self.cap(*R(0.02, -0.01), *R(0.15, -0.02), 0.052, 0.008, P, prof=0.8)            # the snout
            self.cap(*R(0.03, 0.012), *R(0.115, 0.002), 0.005, 0.004, "void")
            self.cap(*R(-0.02, 0.08), *R(-0.04, 0.095), 0.016, 0.004, P, prof=0.9)           # pointed crown
        elif helm == "sallet":
            self.cap(*R(-0.02, 0.03), *R(-0.15, -0.035), 0.05, 0.012, P, prof=0.9)           # tail
            self.ell(*R(0.0, 0.025), 0.078, 0.066, tilt, P, prof=0.9, trim=trim)
            self.trap(*R(0.035, -0.055), 0.045, 0.05, 0.03, P, a=tilt, r=0.01, prof=1.2)      # bevor
            self.cap(*R(0.02, -0.018), *R(0.078, -0.018), 0.006, 0.006, "void")
        else:  # armet
            self.ell(*R(0.0, 0.0), 0.07, 0.08, tilt, P, prof=1.0, trim=trim)
            self.ell(*R(0.035, -0.035), 0.05, 0.04, tilt, P, prof=1.2)                       # visor
            self.cap(*R(-0.06, 0.06), *R(0.06, 0.06), 0.009, 0.007, P, prof=0.6)             # comb
            self.cap(*R(0.025, 0.0), *R(0.072, 0.0), 0.005, 0.005, "void")
        # --- the sword, planted in front of the raised knee
        sw = g["sword"]
        bw = {"long": 0.022, "broad": 0.03, "cross": 0.024, "wavy": 0.024}[sw]
        tip = -0.015
        gv = hand_v - 0.15                       # crossguard height
        blade_top = gv - 0.01
        if sw == "wavy":
            n = 7
            step = (blade_top - tip - 0.04) / n
            for k in range(n):
                v0 = tip + 0.04 + k * step
                o = 0.005 * (1 if k % 2 else -1)
                self.cap(sx + o, v0, sx - o, v0 + step, bw * 0.8, bw * 0.8, "blade", prof=0.8)
            self.cap(sx, tip, sx, tip + 0.045, 0.003, bw * 0.7, "blade", prof=0.8)
        else:
            hh = (blade_top - tip) / 2
            self.trap(sx, tip + hh, bw * 0.22, bw, hh, "blade", r=0.002, prof=0.9)
        self.cap(sx, tip + 0.09, sx, blade_top - 0.02, 0.0035, 0.004, "void")              # fuller
        if sw == "cross":
            self.cap(sx - 0.12, gv - 0.03, sx, gv, 0.011, 0.015, "blade", prof=0.9, trim=trim)
            self.cap(sx, gv, sx + 0.12, gv - 0.03, 0.015, 0.011, "blade", prof=0.9, trim=trim)
            self.circ(sx - 0.12, gv - 0.03, 0.016, "blade", prof=0.9)
            self.circ(sx + 0.12, gv - 0.03, 0.016, "blade", prof=0.9)
        else:
            q = 0.14 if sw == "broad" else 0.11
            self.cap(sx - q, gv, sx + q, gv, 0.012, 0.012, "blade", prof=0.9, trim=trim)
            for s in (-1, 1):
                self.ell(sx + s * q, gv, 0.011, 0.019, 0.0, "blade", prof=0.9)
        self.circ(sx, gv, 0.018, "blade", prof=0.8)
        self.cap(sx, gv + 0.015, sx, hand_v - 0.01, 0.012, 0.013, "leather", prof=1.0, tex="wrap")   # grip
        self.ell(sx, hand_v + 0.002, 0.02, 0.016, 0.0, "blade", prof=0.8, trim=trim)          # pommel
        # --- pauldron: layered lames under a big rounded top plate
        for k in range(g["lames"] - 1, -1, -1):
            f = 1 - k * 0.13
            self.ell(0.005 + 0.006 * k, 0.725 - k * 0.03, 0.078 * pk * f, 0.03 * pk * f, -0.2, P, prof=1.0,
                     trim=trim)
        self.ell(-0.005, 0.765, 0.085 * pk, 0.062 * pk, 0.05, P, prof=0.85, trim=trim)
        if g["ridge"]:
            self.cap(-0.075 * pk, 0.79, 0.07 * pk, 0.8, 0.008, 0.006, P, prof=0.6)
        # --- near arm and the gauntlets folded over the pommel
        self.cap(0.0, 0.725, 0.16, 0.575, 0.04, 0.036, arm, prof=1.1)
        self.circ(0.16, 0.575, 0.042, P, prof=0.85, trim=trim)                              # couter
        self.ell(0.14, 0.555, 0.03, 0.042, 0.7, P, prof=1.0, trim=trim)
        self.cap(0.16, 0.575, sx - 0.035, hand_v + 0.01, 0.035, 0.029, arm, prof=1.1)
        self.trap(sx - 0.05, hand_v + 0.012, 0.03, 0.036, 0.02, P, a=-1.35, r=0.007, prof=1.4, trim=trim)
        self.ell(sx - 0.002, hand_v + 0.014, 0.046, 0.028, -0.1, P, prof=1.0, tex="fingers")
        self.slit = (self.X(R(0.06, 0.0)[0]), self.Y(R(0.06, 0.0)[1]), 0.0)
        self.helm_top = (self.X(R(-0.02, 0.08)[0]), self.Y(R(-0.02, 0.08)[1]))
        self.neck = (self.X(-0.07), self.Y(0.79))
        self.knot = (self.X(0.05), self.Y(0.78))

    # ------------------------------------------------------------------ knight rendering (once)
    def render_knight(self):
        self.kcells = []
        parts = self.parts[::-1]           # front first
        np_ = len(parts)
        S = self.S
        w, h = self.w, self.h
        lo = [p.box for p in parts]
        x0 = int(max(0, min(b[0] for b in lo) - 1))
        x1 = int(min(w, max(b[2] for b in lo) + 2))
        y0 = int(max(0, min(b[1] for b in lo) / ASPECT - 1))
        y1 = int(min(h, max(b[3] for b in lo) / ASPECT + 2))
        if x1 <= x0 or y1 <= y0:
            self.kbox = (0, 0, 0, 0)
            return
        bw = x1 - x0
        L, Hv, R = self.L, self.Hv, self.R
        cast = (L[0], L[1])
        cn = math.hypot(*cast) or 1.0
        cast = (cast[0] / cn, cast[1] / cn)
        sh1, sh2 = max(0.9, S * 0.018), max(1.6, S * 0.04)
        trim_w = max(0.9, S * 0.011)
        vis = [-1] * (bw * (y1 - y0))
        dvis = [0.0] * len(vis)
        for y in range(y0, y1):
            py = (y + 0.5) * ASPECT
            for x in range(x0, x1):
                px = x + 0.5
                for k in range(np_):
                    b = lo[k]
                    if px < b[0] - 0.5 or px > b[2] + 0.5 or py < b[1] - 0.5 or py > b[3] + 0.5:
                        continue
                    d = parts[k].f(px, py)
                    if d < 0:
                        vis[(y - y0) * bw + x - x0] = k
                        dvis[(y - y0) * bw + x - x0] = d
                        break
        cells = []
        e = 0.5
        for y in range(y0, y1):
            py = (y + 0.5) * ASPECT
            for x in range(x0, x1):
                j = (y - y0) * bw + x - x0
                k = vis[j]
                if k < 0:
                    continue
                self.mask[y * w + x] = True
                part = parts[k]
                if part.mat == "void":
                    cells.append((x, y, 0.0, (0, 0, 0), " ", "over"))
                    continue
                px = x + 0.5
                d = dvis[j]
                f = part.f
                gx = f(px + e, py) - f(px - e, py)
                gy = f(px, py + e) - f(px, py - e)
                gn = math.hypot(gx, gy) or 1.0
                gx, gy = gx / gn, gy / gn
                hh = clamp(-d / part.thick)
                tilt = (1 - hh) ** part.prof
                nz = math.sqrt(max(0.0, 1 - tilt * tilt))
                nx, ny = gx * tilt, gy * tilt
                mat = part.mat
                if part.trim and -d < trim_w and mat != "mail":
                    mat = "gold"
                base, amb, kd, ks, shin = MATERIALS[mat]
                if part.tint is not None:
                    base = part.tint
                    ks = 0.3
                # cast shadow: is a part in front of this one between it and the light?
                shadow = 1.0
                for t in (sh1, sh2):
                    qx, qy = px + cast[0] * t, py + cast[1] * t
                    for m in range(k):
                        bb = lo[m]
                        if bb[0] <= qx <= bb[2] and bb[1] <= qy <= bb[3] and parts[m].f(qx, qy) < 0 \
                                and parts[m].mat != "void":
                            shadow = 0.55 if t == sh1 else min(shadow, 0.7)
                            break
                    if shadow < 0.5:
                        break
                ndl = nx * L[0] + ny * L[1] + nz * L[2]
                diff = max(0.0, ndl)
                ndh = nx * Hv[0] + ny * Hv[1] + nz * Hv[2]
                spec = max(0.0, ndh) ** shin if ndh > 0 else 0.0
                rim = max(0.0, nx * R[0] + ny * R[1] + nz * R[2]) ** 3 * 0.55 * tilt
                env = math.exp(-((ny + 0.35) / 0.18) ** 2) * 0.12 * tilt if mat in ("plate", "blade", "dark") else 0
                fill = 0.1 * nz if mat != "cloth" else 0.04 * nz
                lum = amb + fill + kd * diff * shadow + ks * spec * shadow + rim + env
                # edges, the way ASCII shaders do it: the silhouette and the seams where a plate in front
                # overlaps this one become line glyphs (| / - \) that follow the contour
                edge = None
                seam = False
                xl, xr, yu, yd = x > x0, x < x1 - 1, y > y0, y < y1 - 1
                for nj, ok in ((j - 1, xl), (j + 1, xr), (j - bw, yu), (j + bw, yd)):
                    kk = vis[nj] if ok else -1
                    if kk < 0:
                        edge = (gx, gy, True)
                        break
                    if kk < k and parts[kk].mat != "void":
                        seam = True
                if mat == "mail":
                    lum *= 0.62 + 0.38 * (((x + (y & 1)) & 1) ^ (y % 3 == 0))
                if part.tex == "wrap":
                    lum *= 0.55 + 0.45 * (y & 1)
                elif part.tex == "fingers":
                    if int((px - self.X(-0.03) * 0 - part.box[0]) / max(1.0, 0.016 * S)) % 2 and hh < 0.75:
                        lum *= 0.6
                if seam:
                    lum *= 0.55
                lum *= part.dim
                v = clamp(lum) ** 0.78
                col = mix(scale(base, 0.55), base, clamp(diff * shadow))
                col = mix(col, (150, 175, 220), clamp(rim * 1.4))
                col = mix(col, WHITE, clamp(spec * shadow * 1.3))
                ch = None
                if edge is not None and S > 18:
                    ex, ey, outer = edge
                    a = math.degrees(math.atan2(ey, ex)) % 180.0
                    if a < 22.5 or a >= 157.5:
                        ch = "|"
                    elif a < 67.5:
                        ch = "/"
                    elif a < 112.5:
                        ch = "_" if ey > 0 else "-"
                    else:
                        ch = "\\"
                    if outer:
                        v = max(v, 0.32)
                    else:
                        v = clamp(v * 0.75)
                        col = scale(col, 0.8)
                    col = scale(col, 0.3 + 0.7 * v)
                cells.append((x, y, v, col, ch, "over"))
        self.kcells = cells
        self.kbox = (x0, y0, x1, y1)

    # ------------------------------------------------------------------ background (once)
    def render_background(self):
        rng = self.rng
        g = self.g
        w, h = self.w, self.h
        gy = self.gy / ASPECT
        cells = []
        add = cells.append
        sky_seed = rng.randrange(1 << 16)
        # stars, very dim
        for _ in range(int(w * h * 0.012)):
            x, y = rng.uniform(0, w), rng.uniform(0, gy * 0.8)
            add((x, y, rng.uniform(0.06, 0.2), (150, 160, 190), None, "max"))
        # the moon
        if self.opt("ruins") and g["moon"] != "none" and h >= 12:
            side = -g["wind_dir"]
            mx = w * 0.5 + side * w * rng.uniform(0.2, 0.33)
            my = gy * rng.uniform(0.18, 0.3)
            mr = max(2.0, min(w * 0.07, gy * 0.18 * ASPECT))
            cut = g["moon"] == "crescent"
            for y in range(max(0, int(my - mr * 2 / ASPECT) - 1), min(h, int(my + mr * 2 / ASPECT) + 2)):
                for x in range(max(0, int(mx - mr * 2) - 1), min(w, int(mx + mr * 2) + 2)):
                    dx, dy = x + 0.5 - mx, (y + 0.5 - my) * ASPECT
                    d = math.hypot(dx, dy) / mr
                    if d < 1:
                        lit = 1.0
                        if cut:
                            d2 = math.hypot(dx + side * mr * 0.45, dy + mr * 0.12) / (mr * 0.95)
                            lit = clamp((d2 - 1) * 4)
                        crater = 0.5 + 0.5 * noise2(dx * 0.35, dy * 0.35, sky_seed)
                        v = (0.18 + 0.14 * crater) * lit * (1 - 0.25 * d ** 4)
                        if v > 0.02:
                            add((x, y, v, (200, 210, 230), None, "max"))
                    elif d < 2.0 and not cut:
                        add((x, y, 0.07 * (2 - d) ** 2, (120, 130, 160), None, "max"))
        # distant hills
        if g["hills"]:
            hs = rng.uniform(0, 100)
            for x in range(w):
                top = gy - (1.2 + 2.8 * (0.5 + 0.5 * noise1(x * 0.045 + hs))) * (h / 30) - 0.5
                for y in range(max(0, int(top)), int(gy)):
                    v = 0.07 if y == int(top) else 0.045 + 0.03 * (noise2(x * 0.3, y * 0.6, sky_seed) > 0.3)
                    add((x, y, v, (90, 100, 125), None, "max"))
        # ruined pillars and an arch, dim silhouettes with stone courses
        if self.opt("ruins"):
            kx0, _, kx1, _ = self.kbox
            spots = []
            for _ in range(g["pillars"]):
                for _try in range(12):
                    px = rng.uniform(0.04, 0.96) * w
                    if not (kx0 - 3 < px < kx1 + 3) and all(abs(px - q) > 7 for q in spots):
                        spots.append(px)
                        break
            stone = (120, 126, 146)

            def pillar(px, pw, top, broken):
                xl, xr = int(round(px - pw)), int(round(px + pw))
                for x in range(xl, xr + 1):
                    if not 0 <= x < w:
                        continue
                    u = (x + 0.5 - px) / max(0.5, pw)
                    jag = top + 1.8 * (0.5 + 0.5 * math.sin(u * 2.6 + broken))
                    lit = 0.5 + 0.5 * clamp(-u * g["light"], -1, 1)
                    for y in range(max(0, int(jag)), int(gy)):
                        k = 0.55 + 0.45 * lit
                        if y == int(jag):
                            ch = "_" if abs(u) < 0.9 else "."
                        elif x in (xl, xr):
                            ch = "|"
                        elif (y - int(top)) % 4 == 3:
                            ch = "_"
                        elif (x - xl) % 2 == 0:
                            ch = ":"
                        else:
                            continue
                        add((x, y, 0.1 * k, scale(stone, 0.2 + 0.2 * k), ch, "max"))

            for px in spots:
                pw = max(1.0, w * rng.uniform(0.014, 0.024))
                pillar(px, pw, gy - gy * rng.uniform(0.3, 0.62), rng.uniform(0, TAU))
            if g["arch"] and h >= 16:
                ax = (rng.uniform(0.1, 0.22) if self.cx > w / 2 else rng.uniform(0.78, 0.9)) * w
                ar = max(4.0, w * rng.uniform(0.07, 0.1))
                ah = gy * rng.uniform(0.3, 0.42)
                pw = max(1.0, ar * 0.18)
                for s in (-1, 1):
                    pillar(ax + s * ar, pw, gy - ah, rng.uniform(0, TAU))
                # the arc: two concentric curves of contour glyphs, broken off on one side
                for rr in (ar - pw, ar + pw):
                    n = int(rr * 5)
                    for i in range(n + 1):
                        a = math.pi * i / n
                        if math.cos(a) * g["wind_dir"] > 0.55:
                            continue
                        x = ax + math.cos(a) * rr
                        y = gy - ah - math.sin(a) * rr / ASPECT
                        tx, ty = -math.sin(a), -math.cos(a)   # tangent, screen-down positive
                        ang = math.degrees(math.atan2(ty, tx)) % 180
                        ch = "-" if ang < 22.5 or ang >= 157.5 else "\\" if ang < 67.5 else "|" if ang < 112.5 else "/"
                        add((x, y, 0.09, scale(stone, 0.55), ch, "max"))
        # ground: a faint horizon, scattered grit getting denser toward us, a few stones, his shadow
        sx = self.cx - g["light"] * self.S * 0.25
        srx, sry = self.S * 0.42, self.S * 0.06
        for x in range(w):
            add((x, gy, 0.16, (110, 112, 125), None, "max"))
        for y in range(int(gy) + 1, h):
            near = (y - gy) / max(1.0, h - gy)
            for x in range(w):
                n = noise2(x * 0.5, y * 1.1, sky_seed + 7)
                if n > 0.35 - 0.25 * near:
                    sh = ((x + 0.5 - sx) / srx) ** 2 + (((y + 0.5) * ASPECT - self.gy) / sry) ** 2
                    k = 0.3 if sh < 1 else 1.0
                    add((x, y, (0.07 + 0.1 * near + 0.08 * (n - 0.35)) * k, (105, 100, 98), None, "max"))
        for _ in range(int(w * 0.12)):
            x = rng.uniform(0, w)
            y = gy + rng.uniform(0.3, 1.0) * (h - gy)
            r = rng.uniform(0.6, 1.6) * (0.6 + (y - gy) / max(1.0, h - gy))
            for yy in range(int(y - r / ASPECT), int(y + r / ASPECT) + 1):
                for xx in range(int(x - r), int(x + r) + 1):
                    dx, dy = xx + 0.5 - x, (yy + 0.5 - y) * ASPECT
                    if dx * dx + dy * dy < r * r:
                        lit = clamp(0.5 + 0.5 * (dx * g["light"] - dy) / (r + 0.01))
                        add((xx, yy, 0.12 + 0.22 * lit, (130, 128, 128), None, "max"))
        self.cells = cells

    def static_layer(self, ramp):
        if self.static is not None and self.static[0] == ramp:
            return self.static
        cv = Canvas(self.w, self.h, ramp)
        w, h = self.w, self.h
        for x, y, v, col, ch, mode in self.cells:
            if ch is None:
                cv.shade(x, y, v, col, mode)
            elif 0 <= int(x) < w and 0 <= int(y) < h and cv.lv[int(y) * w + int(x)] < v:
                cv.put(x, y, ch, col, level=v)
        for x, y, v, col, ch, mode in self.kcells:
            if ch is not None:
                cv.put(x, y, ch, col, level=1.0)
            else:
                cv.shade(x, y, max(v, 0.001), col, "over")
                i = y * w + x
                cv.lv[i] = 1.0 if cv.ch[i] == " " else max(cv.lv[i], 0.4)   # nothing faint draws over armor
        self.static = (ramp, cv.ch, cv.fg, cv.lv, cv.bc)
        return self.static

    # ------------------------------------------------------------------ cloth
    def build_cloth(self):
        g = self.g
        S = self.S
        nx, ny = self.neck
        self.cols = 6
        self.rows = max(6, min(18, int(S * g["cape_len"] / 4.5)))
        L = S * 0.55 * g["cape_len"]
        self.seg = L / (self.rows - 1)
        top, bot = ny + S * 0.01, ny + S * 0.2
        self.anchors = [(nx + g["wind_dir"] * S * 0.03, top + (bot - top) * j / (self.cols - 1)) for j in range(self.cols)]
        w0 = (bot - top) / (self.cols - 1)
        self.across = [w0 * (1.0 + 1.1 * (i / (self.rows - 1)) ** 0.8) for i in range(self.rows)]
        rng = self.rng
        self.fold_ph = [rng.uniform(0, TAU) for _ in range(self.cols)]
        self.lens = [self.rows - (int(rng.random() * g["tatter"] * self.rows) if 0 < j < self.cols - 1 or
                                  rng.random() < 0.5 else 0) for j in range(self.cols)]
        self.cloth = []
        for j, (ax, ay) in enumerate(self.anchors):
            strand = []
            for i in range(self.rows):
                x = ax + g["wind_dir"] * self.seg * i * 0.9
                y = ay + self.seg * i * 0.35
                strand.append([x, y, x, y])
            self.cloth.append(strand)
        # scarf tails and plume: single strands
        self.tails = []
        if g["scarf"]:
            kx, ky = self.knot
            for k in range(2):
                n = 7 + k * 2
                seg = S * (0.035 + 0.005 * k)
                self.tails.append([[kx, ky + k, kx, ky + k] for _ in range(n)] + [seg, 0.55 - 0.15 * k])
        if g["plume"]:
            px, py = self.helm_top
            self.tails.append([[px, py, px, py] for _ in range(6)] + [S * 0.04, 0.5])

    def step_cloth(self, dt):
        t = self.t
        S = self.S
        wx, wy = self.wind
        strength = self.opt("wind")
        speed = S * 1.6 * strength
        grav = S * 1.1
        damp = 0.985
        for j, strand in enumerate(self.cloth):
            ax, ay = self.anchors[j]
            for i, p in enumerate(strand):
                if i == 0:
                    p[0], p[1], p[2], p[3] = ax, ay, ax, ay
                    continue
                vx, vy = (p[0] - p[2]) / dt, (p[1] - p[3]) / dt
                f = i / (self.rows - 1)
                gust = 0.75 + 0.5 * noise1(t * 0.6 + f * 1.5, 3) + self.gust * 1.8
                tx, ty = wx * speed * gust, wy * speed * gust
                # flutter: a wave traveling down the cloth, perpendicular to the wind
                wave = math.sin(t * 7.0 - i * 0.9 + j * 0.35) + 0.5 * math.sin(t * 11.3 - i * 1.7 + j)
                amp = S * 0.9 * (0.3 + f) * strength * (0.6 + 0.4 * gust)
                tx += -wy * wave * amp
                ty += wx * wave * amp
                ax_ = (tx - vx) * 2.2
                ay_ = (ty - vy) * 2.2 + grav
                nxp = p[0] + (p[0] - p[2]) * damp + ax_ * dt * dt
                nyp = p[1] + (p[1] - p[3]) * damp + ay_ * dt * dt
                p[2], p[3] = p[0], p[1]
                p[0], p[1] = nxp, nyp
        seg = self.seg
        cols, rows = self.cols, self.rows
        for _ in range(5):
            for j in range(cols):
                strand = self.cloth[j]
                for i in range(1, rows):
                    a, b = strand[i - 1], strand[i]
                    self._relax(a, b, seg, i == 1)
            for i in range(1, rows):
                rest = self.across[i]
                for j in range(cols - 1):
                    self._relax(self.cloth[j][i], self.cloth[j + 1][i], rest, False, 0.5)

    @staticmethod
    def _relax(a, b, rest, pin_a, k=1.0):
        dx, dy = b[0] - a[0], (b[1] - a[1])
        d = math.hypot(dx, dy) or 1e-6
        diff = (d - rest) / d * k
        if pin_a:
            b[0] -= dx * diff
            b[1] -= dy * diff
        else:
            a[0] += dx * diff * 0.5
            a[1] += dy * diff * 0.5
            b[0] -= dx * diff * 0.5
            b[1] -= dy * diff * 0.5

    def step_tails(self, dt):
        t = self.t
        S = self.S
        wx, wy = self.wind
        speed = S * 1.3 * self.opt("wind")
        for k, tail in enumerate(self.tails):
            pts, seg = tail[:-2], tail[-2]
            if k < 2 and self.g["scarf"]:
                ox, oy = self.knot
            else:
                ox, oy = self.helm_top
            pts[0][0], pts[0][1] = ox, oy
            for i, p in enumerate(pts[1:], 1):
                vx, vy = (p[0] - p[2]) / dt, (p[1] - p[3]) / dt
                gust = 0.7 + 0.5 * noise1(t * 0.8 + i * 0.3 + k * 5, 9) + self.gust * 1.5
                wave = math.sin(t * 9 - i * 1.1 + k * 2)
                tx = wx * speed * gust - wy * wave * S * 0.6
                ty = wy * speed * gust + wx * wave * S * 0.6
                ax_ = (tx - vx) * 2.0
                ay_ = (ty - vy) * 2.0 + S * 1.4
                nxp = p[0] + (p[0] - p[2]) * 0.98 + ax_ * dt * dt
                nyp = p[1] + (p[1] - p[3]) * 0.98 + ay_ * dt * dt
                p[2], p[3] = p[0], p[1]
                p[0], p[1] = nxp, nyp
            for _ in range(4):
                for i in range(1, len(pts)):
                    self._relax(pts[i - 1], pts[i], seg, i == 1)

    # ------------------------------------------------------------------ ash
    def new_ash(self, x, y):
        rng = self.rng
        ember = rng.random() < 0.28
        return [x, y, 0.0, 0.0, ember, rng.uniform(0, TAU), rng.uniform(0.4, 1.0)]

    def on_click(self, x, y):
        if not (math.isfinite(x) and math.isfinite(y)):
            return
        nx, ny = self.neck
        dx, dy = nx - x, (ny - y * ASPECT)
        d = math.hypot(dx, dy) or 1.0
        self.gust = 1.0
        self.gust_dir = (dx / d, dy / d)
        self.flash = 1.0
        rng = self.rng
        cx, cy = clamp(x, 0, self.w - 1), clamp(y, 0, self.h - 1)
        for _ in range(int(26 * max(0.2, self.opt("ash")))):
            a = rng.uniform(0, TAU)
            sp = rng.uniform(4, 22)
            p = self.new_ash(cx, cy)
            p[2], p[3] = math.cos(a) * sp + dx / d * 12, math.sin(a) * sp / ASPECT + dy / d * 6 / ASPECT
            self.ash.append(p)
        if len(self.ash) > 400:
            self.ash = self.ash[-400:]

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        g = self.g
        t = self.t
        # the wind: a steady breeze from one side, or blowing away from the pointer
        bx, by = g["wind_dir"] * 1.0, -0.06 + 0.12 * noise1(t * 0.15, 5)
        ptr = self.pointer
        if ptr is not None:
            nx, ny = self.neck
            dx, dy = nx - ptr[0], ny - ptr[1] * ASPECT
            d = math.hypot(dx, dy)
            if d > 1e-3:
                bx, by = dx / d, dy / d * 0.8 - 0.05
        if self.gust > 0:
            k = self.gust
            bx, by = bx * (1 - k) + self.gust_dir[0] * k, by * (1 - k) + self.gust_dir[1] * k
        n = math.hypot(bx, by) or 1.0
        bx, by = bx / n, by / n
        k = min(1.0, dt * 2.5)
        self.wind[0] += (bx - self.wind[0]) * k
        self.wind[1] += (by - self.wind[1]) * k
        steps = max(1, min(4, int(math.ceil(dt / (1 / 60)))))
        sdt = min(dt, 4 / 60) / steps
        if sdt > 0:
            for _ in range(steps):
                self.step_cloth(sdt)
                self.step_tails(sdt)
        self.gust = max(0.0, self.gust - dt * 0.9)
        self.flash = max(0.0, self.flash - dt * 1.5)
        # ash and embers
        w, h = self.w, self.h
        wx, wy = self.wind
        sp = 9.0 * self.opt("wind") * (1 + self.gust * 2.5)
        rng = self.rng
        keep = []
        for p in self.ash:
            tx = wx * sp * p[6] + 2.5 * noise2(p[0] * 0.08, t * 0.4 + p[5], 1)
            ty = (wy * sp * p[6] + 2.0 * noise2(p[1] * 0.1, t * 0.4 + p[5], 2)) / ASPECT
            ty += -0.6 if p[4] else 0.25
            kk = min(1.0, dt * 1.6)
            p[2] += (tx - p[2]) * kk
            p[3] += (ty - p[3]) * kk
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[5] += dt * (3.0 if p[4] else 0.8)
            if -3 <= p[0] <= w + 3 and -3 <= p[1] <= h + 3:
                keep.append(p)
            elif len(keep) < self.count(70) * max(0.0, self.opt("ash")):
                # re-enter from the upwind edge
                if abs(wx) > abs(wy) * 0.6:
                    q = self.new_ash(-2 if wx > 0 else w + 2, rng.uniform(0, h))
                else:
                    q = self.new_ash(rng.uniform(0, w), -2 if wy > 0 else h + 2)
                keep.append(q)
        self.ash = keep
        for s in self.streaks:
            s[0] += wx * s[3] * 38 * dt * (1 + self.gust * 2)
            s[1] += wy * s[3] * 12 * dt
            s[4] += dt
            if s[0] < -15 or s[0] > w + 15 or s[1] < -2 or s[1] > h:
                s[0] = -12 if wx > 0 else w + 12
                s[1] = rng.uniform(0, self.gy / ASPECT * 0.95)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        if cv.w != self.w or cv.h != self.h:
            return
        _, ch, fg, lv, bc = self.static_layer(cv.ramp)
        cv.ch = ch[:]
        cv.fg = fg[:]
        cv.lv = lv[:]
        cv.bc = bc[:]
        self.draw_streaks(cv)
        self.draw_cloth(cv)
        self.draw_grass(cv)
        self.draw_tails(cv)
        self.draw_eyes(cv)
        self.draw_ash(cv)

    def draw_streaks(self, cv):
        wx, wy = self.wind
        w = cv.w
        lv = cv.lv
        for x, y, ln, sp, ph in self.streaks:
            a = 0.5 + 0.5 * math.sin(ph * 0.7)
            for k in range(int(ln)):
                xx = int(x - wx * k)
                yy = int(y - wy * k * 0.3)
                if 0 <= xx < w and 0 <= yy < cv.h:
                    i = yy * w + xx
                    if lv[i] < 0.05:
                        f = 1 - k / ln
                        c = 60 + 50 * f * a
                        cv.put(xx, yy, "-" if f > 0.35 else ".", (c, c + 4, c + 18), level=0.04)

    def draw_cloth(self, cv):
        base, hi, back = self.cape_cols
        cloth = self.cloth
        mask = self.mask
        w, h = cv.w, cv.h
        L = self.L
        t = self.t
        # per-vertex brightness: how open (facing us) the cloth is there, and its slope vs the light
        bright = []
        for j in range(self.cols):
            row = []
            for i in range(self.rows):
                p = cloth[j][i]
                jn = j + 1 if j + 1 < self.cols else j - 1
                q = cloth[jn][i]
                op = clamp(math.hypot(q[0] - p[0], q[1] - p[1]) / (self.across[i] or 1))
                pn = cloth[j][min(self.rows - 1, i + 1)]
                pp = cloth[j][max(0, i - 1)]
                tx, ty = pn[0] - pp[0], pn[1] - pp[1]
                tn = math.hypot(tx, ty) or 1
                facing = 0.5 + 0.5 * ((-ty / tn) * L[0] + (tx / tn) * L[1])
                fold = 0.5 + 0.5 * math.sin(j * 1.9 + i * 0.3 - t * 3.0 + self.fold_ph[j])
                wave = math.cos(t * 7.0 - i * 0.9 + j * 0.35)
                b = 0.1 + op * (0.22 + 0.3 * fold + 0.2 * facing) + 0.28 * max(0.0, wave) * op
                row.append(b)
            bright.append(row)
        shade = cv.shade
        for j in range(self.cols - 1):
            A, B = cloth[j], cloth[j + 1]
            nlen = min(self.lens[j], self.lens[j + 1])
            for i in range(nlen - 1):
                p00, p10, p11, p01 = A[i], B[i], B[i + 1], A[i + 1]
                b00, b10, b11, b01 = bright[j][i], bright[j + 1][i], bright[j + 1][i + 1], bright[j][i + 1]
                for (pa, ba), (pb, bb), (pc, bc_) in (((p00, b00), (p10, b10), (p11, b11)),
                                                      ((p00, b00), (p11, b11), (p01, b01))):
                    ax, ay = pa[0], pa[1] / ASPECT
                    bx, by = pb[0], pb[1] / ASPECT
                    cx, cy = pc[0], pc[1] / ASPECT
                    area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
                    if abs(area) < 1e-6:
                        continue
                    front = area > 0
                    col_lo, col_hi = (base, hi) if front else (back, base)
                    xa, xb = max(0, int(min(ax, bx, cx))), min(w - 1, int(max(ax, bx, cx)) + 1)
                    ya, yb = max(0, int(min(ay, by, cy))), min(h - 1, int(max(ay, by, cy)) + 1)
                    inv = 1.0 / area
                    for y in range(ya, yb + 1):
                        py = y + 0.5
                        row = y * w
                        for x in range(xa, xb + 1):
                            if mask[row + x]:
                                continue
                            px = x + 0.5
                            l1 = ((bx - px) * (cy - py) - (cx - px) * (by - py)) * inv
                            l2 = ((cx - px) * (ay - py) - (ax - px) * (cy - py)) * inv
                            l3 = 1 - l1 - l2
                            if l1 < -0.08 or l2 < -0.08 or l3 < -0.08:
                                continue
                            bv = l1 * ba + l2 * bb + l3 * bc_
                            if not front:
                                bv *= 0.7
                            bv = clamp(bv)
                            shade(x, y, bv, mix(col_lo, col_hi, clamp((bv - 0.45) * 1.8)), "max")
        # crisp outer edges
        for j in (0, self.cols - 1):
            strand = cloth[j]
            for i in range(self.lens[j] - 1):
                a, b = strand[i], strand[i + 1]
                steps = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]) / ASPECT)) + 1
                for s in range(steps + 1):
                    f = s / steps
                    x = a[0] + (b[0] - a[0]) * f
                    y = (a[1] + (b[1] - a[1]) * f) / ASPECT
                    xi, yi = int(x), int(y)
                    if 0 <= xi < w and 0 <= yi < h and not mask[yi * w + xi]:
                        shade(xi, yi, 0.55, base, "max")

    def draw_tails(self, cv):
        base, hi, back = self.cape_cols
        for k, tail in enumerate(self.tails):
            pts = tail[:-2]
            plume = not (k < 2 and self.g["scarf"])
            col_a = (225, 228, 236) if plume and self.g["cape"] == "gold" else hi
            n = len(pts)
            for i in range(n - 1):
                a, b = pts[i], pts[i + 1]
                steps = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]) / ASPECT) * 1.5) + 1
                for s in range(steps + 1):
                    f = (i + s / steps) / (n - 1)
                    x = a[0] + (b[0] - a[0]) * s / steps
                    y = (a[1] + (b[1] - a[1]) * s / steps) / ASPECT
                    v = 0.85 - 0.45 * f
                    col = mix(col_a, base if not plume else col_a, f)
                    cv.shade(x, y, v, col, "over")
                    if f < 0.6 and self.S > 30:
                        cv.shade(x, y + 0.6, v * 0.6, mix(base, back, 0.5), "max")

    def draw_eyes(self, cv):
        if not self.g["eyes"]:
            return
        x, y, _ = self.slit
        glow = 0.55 + 0.25 * math.sin(self.t * 1.3) + 0.4 * self.flash
        cv.put(x, y / ASPECT, "." if glow < 0.7 else "*", mix((150, 190, 255), WHITE, clamp(glow - 0.5)),
               level=glow)

    def draw_grass(self, cv):
        gy = self.gy / ASPECT
        wx = self.wind[0]
        t = self.t
        h = cv.h
        for x, k, n, ph in self.grass:
            y = gy + 0.6 + k * min(2.5, h - gy - 1.0)
            lean = wx * (0.5 + 0.5 * math.sin(t * 6 + ph)) * (1 + self.gust)
            for s in range(n):
                xx = x + lean * s * 0.6
                yy = y - s
                if s == n - 1:
                    ch = "/" if lean > 0.3 else "\\" if lean < -0.3 else "'"
                else:
                    ch = ","
                if 0 <= int(xx) < cv.w and 0 <= int(yy) < h:
                    i = int(yy) * cv.w + int(xx)
                    if cv.lv[i] < 0.3:
                        c = 52 + 14 * s
                        cv.put(xx, yy, ch, (c, c + 10, c - 6), level=0.2)

    def draw_ash(self, cv):
        w, h = cv.w, cv.h
        for x, y, vx, vy, ember, ph, sz in self.ash:
            xi, yi = int(x), int(y)
            if not (0 <= xi < w and 0 <= yi < h):
                continue
            if ember:
                fl = 0.55 + 0.45 * math.sin(ph * 2.3) * math.sin(ph * 0.7 + 1)
                col = mix((200, 60, 10), (255, 200, 90), fl)
                i = yi * w + xi
                if cv.lv[i] < 0.6:
                    cv.put(xi, yi, "*" if fl > 0.75 and sz > 0.7 else "." if fl < 0.35 else "+" if sz > 0.8 else "'",
                           col, level=0.5)
                tx, ty = int(x - vx * 0.08), int(y - vy * 0.08)
                if (tx, ty) != (xi, yi):
                    cv.shade(tx, ty, 0.12 * fl, (200, 70, 20))
            else:
                cv.shade(x, y, 0.1 + 0.18 * sz, (150, 150, 158))
