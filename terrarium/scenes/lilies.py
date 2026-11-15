"""A bouquet of lilies: six-pointed blooms on long stems, swaying and slowly breathing.

Each bloom is drawn as a clean star of six long pointed tepals (three sepals slightly behind three
wider petals) with dark gaps between them. Inside a petal the glyph changes in only a few smooth
bands (the colour carries the fine gradient); the outline is a lighter rim, the midrib a stroke
that follows the petal's curve, and long stamens poke out past the petals with orange anthers.
Blooms are cached as sprites and re-rendered one per frame so breathing stays cheap.
"""
import math

from ..engine import ASPECT, Scene, clamp, mix, noise1, smoothstep

# Petal colours: margin, body, centre stripe, throat, spots (None = none), anthers.
PALETTES = {
    "white": dict(edge=(255, 255, 250), mid=(246, 244, 232), stripe=(214, 232, 150), throat=(140, 196, 90),
                  spot=None, anther=(236, 120, 30)),
    "pink": dict(edge=(255, 214, 232), mid=(250, 140, 190), stripe=(236, 80, 150), throat=(190, 50, 110),
                 spot=(176, 40, 100), anther=(200, 80, 40)),
    "stargazer": dict(edge=(255, 246, 250), mid=(248, 130, 184), stripe=(230, 50, 130), throat=(176, 40, 100),
                      spot=(160, 30, 90), anther=(196, 76, 36)),
    "peach": dict(edge=(255, 236, 214), mid=(255, 190, 146), stripe=(250, 150, 100), throat=(226, 130, 70),
                  spot=(196, 96, 60), anther=(200, 90, 30)),
    "orange": dict(edge=(255, 196, 96), mid=(255, 146, 50), stripe=(250, 110, 30), throat=(226, 90, 20),
                   spot=(120, 40, 16), anther=(150, 50, 20)),
    "yellow": dict(edge=(255, 252, 210), mid=(255, 226, 100), stripe=(250, 190, 50), throat=(200, 170, 50),
                   spot=(190, 110, 30), anther=(196, 80, 20)),
    "lavender": dict(edge=(248, 240, 255), mid=(210, 170, 250), stripe=(176, 120, 236), throat=(126, 90, 176),
                     spot=(130, 70, 170), anther=(210, 100, 40)),
}
CHOICES = {
    "white": ["white"],
    "pink": ["pink", "stargazer"],
    "orange": ["orange", "peach"],
    "mixed": ["white", "stargazer", "pink", "white", "peach", "stargazer"],
    "blush": ["white", "pink", "white", "stargazer"],
    "sunset": ["peach", "orange", "yellow", "white"],
    "pastel": ["lavender", "white", "pink", "yellow"],
    "golden": ["yellow", "white", "yellow", "peach"],
}
RIBBONS = [(250, 150, 190), (196, 150, 255), (255, 210, 140), (150, 196, 255), (255, 120, 150), (240, 240, 250)]

TAU = math.tau
SECTOR = math.pi / 3
SLX, SLY = -0.6, -0.8          # light direction in screen space (from the upper left)
STEM_D, STEM_L = (40, 110, 54), (140, 210, 110)


def _slope_ch(dx, dy):
    """A glyph for a stroke moving (dx, dy) cells (dy in rows, y down)."""
    ax, ay = abs(dx), abs(dy * ASPECT)
    if ax > 2.6 * ay:
        return "-"
    if ay > 2.6 * ax:
        k = dx / dy if dy else 0.0
        return "(" if k < -0.12 else ")" if k > 0.12 else "|"
    return "\\" if dx * dy > 0 else "/"


def stroke(cv, pts, col_fn, skip=0):
    """Draw a polyline as one clean strand: one glyph per cell, chosen by local slope.

    pts: [(x, y)] in cells; col_fn(f) -> rgb or None for f in 0..1 along the strand.
    """
    n = len(pts)
    seen = None
    for i in range(1, n):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        cell = (int(math.floor(x1)), int(math.floor(y1)))
        if cell == seen:
            continue
        seen = cell
        if i < skip:
            continue
        col = col_fn(i / (n - 1))
        if col is not None:
            cv.put(cell[0], cell[1], _slope_ch(x1 - x0, y1 - y0), col)


def bezier(p0, p1, p2, steps):
    out = []
    for i in range(steps + 1):
        u = i / steps
        a, b, c = (1 - u) * (1 - u), 2 * u * (1 - u), u * u
        out.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))
    return out


class Bloom:
    def __init__(self, rng, x, y, R, pal, depth, lean, genome):
        self.x0, self.y0 = x, y
        self.x, self.y = x, y
        self.R = R
        self.pal = pal
        self.depth = depth
        self.psi = math.atan2(-0.35 + rng.uniform(-0.2, 0.2), lean or 0.001)   # direction the face turns
        self.squash = clamp(1 - abs(lean) * 0.32 - rng.uniform(0.0, 0.1), 0.62, 0.98)
        self.rot = rng.uniform(0, SECTOR)
        self.petals = []
        for k in range(6):
            inner = k % 2 == 1
            self.petals.append(dict(
                inner=inner,
                len=(rng.uniform(0.9, 0.96) if inner else rng.uniform(0.98, 1.05)) * genome["length"],
                wid=(0.26 if inner else 0.19) * rng.uniform(0.93, 1.07) * genome["width"],
                dphi=rng.uniform(-0.07, 0.07),
                bend=rng.choice((-1, 1)) * rng.uniform(0.08, 0.3) * genome["curl"],
            ))
        self.stamens = [(SECTOR * k + SECTOR / 2 + rng.uniform(-0.12, 0.12), rng.uniform(0.74, 0.86) * genome["stamen"],
                         rng.uniform(-0.25, 0.25)) for k in range(6)]
        self.pistil = (rng.uniform(0, TAU), 0.9 * genome["stamen"])
        self.phase = rng.uniform(0, TAU)
        self.rate = rng.uniform(0.2, 0.3)
        self.sph = rng.uniform(0, TAU)
        self.seed = rng.randrange(1 << 16)
        self.open = 0.5
        self.sprite = None
        self.anthers = []


class Bud:
    def __init__(self, rng, x, y, size, pal, ang):
        self.x0, self.y0 = x, y
        self.x, self.y = x, y
        self.size = size
        self.pal = pal
        self.ang = ang
        self.depth = 0.0
        self.sph = rng.uniform(0, TAU)


class Lilies(Scene):
    name = "lilies"
    title = "Lilies"
    blurb = "a bouquet of lilies swaying and breathing, pollen drifting in the light"
    tags = ("flowers", "nature", "calm")
    options = {
        "count": (0, "number of blooms, 1-5 (0 = based on screen size)"),
        "color": ("random", "white, pink, orange, mixed, blush, sunset, pastel, golden or random"),
        "sway": (1.0, "how much the bouquet sways"),
        "ribbon": (True, "tie the stems with a ribbon"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        # ---- a small generative grammar: every seed picks its own bouquet
        if self.opt("count"):
            n = max(1, min(5, self.opt("count")))
        else:
            n = rng.choice((2, 2, 3)) if w < 100 else rng.choice((3, 3, 3, 4)) if w < 200 else rng.choice((3, 4, 5))
        cname = self.opt("color")
        if cname not in CHOICES:
            cname = rng.choice(list(CHOICES))
        choice = CHOICES[cname]
        self.genome = g = dict(width=rng.uniform(0.88, 1.15), curl=rng.uniform(0.6, 1.4),
                               length=rng.uniform(0.94, 1.06), stamen=rng.uniform(0.95, 1.15))
        fit = {1: 0.24, 2: 0.19, 3: 0.165, 4: 0.13, 5: 0.115}[n]
        R = max(5.0, min(w * fit, h * ASPECT * (0.36 if n == 1 else 0.28), w / (2.2 + 0.75 * n))) * rng.uniform(0.93, 1.04)
        self.R = R
        cx = w / 2 + rng.uniform(-0.03, 0.03) * w
        top = R * 0.84 / ASPECT + 0.5
        drop = R * rng.uniform(0.72, 0.9) / ASPECT          # how much lower the front row sits
        # the tie sits below the front row
        gy = min(h * 0.86, max(h * 0.66, top + drop + R * 0.75 / ASPECT + 3))
        self.gx, self.gy = cx, gy
        if len(set(choice)) > 1:
            cols = [choice[k % len(choice)] for k in range(n)]
            rng.shuffle(cols)
        else:
            cols = [choice[0]] * n
        # arrangement: back row on top, front row lower and nearer; spacing with a little jitter
        if n == 1:
            spots = [(0.0, 0, 1.0)]
        elif n == 2:
            s = rng.choice((-1, 1))
            spots = [(-0.75 * s, 0, 0.95), (0.75 * s, 1, 1.0)]
        elif n == 3:
            spots = [(0.0, 0, 0.92), (-1.32, 1, 1.0), (1.32, 1, 1.0)]
        elif n == 4:
            spots = [(-0.75, 0, 0.92), (0.75, 0, 0.92), (-1.5, 1, 1.0), (1.5, 1, 1.0)]
        else:
            spots = [(-1.15, 0, 0.9), (0.0, 0, 0.9), (1.15, 0, 0.9), (-0.62, 1, 1.0), (0.62, 1, 1.0)]
        tilt = rng.uniform(-0.25, 0.25)
        self.blooms = []
        for k, (u, row, size) in enumerate(spots):
            u = u * rng.uniform(0.9, 1.08) + tilt * row
            x = cx + u * R * 1.02
            y = top + drop * row + rng.uniform(-0.6, 0.6) * R * 0.08 / ASPECT
            if n > 1 and row == 0 and abs(u) < 0.2:
                y = top
            rr = R * size * rng.uniform(0.94, 1.04)
            lean = clamp(u * 0.42 + rng.uniform(-0.18, 0.18), -0.8, 0.8)
            depth = row + rng.uniform(0, 0.3)
            self.blooms.append(Bloom(rng, x, y, rr, PALETTES[cols[k]], depth, lean, g))
        # buds: tall closed lilies peeking out above and between
        self.buds = []
        nb = sum(1 for _ in range(3) if rng.random() < (0.6 if n > 1 else 0.35))
        for k in range(nb):
            side = rng.choice((-1, 1))
            x = cx + side * rng.uniform(0.5, 1.6) * R
            y = max(R * 0.35 / ASPECT + 1, top - R * rng.uniform(0.0, 0.25) / ASPECT)
            ang = -math.pi / 2 + side * rng.uniform(0.15, 0.55)
            self.buds.append(Bud(rng, x, y, R * rng.uniform(0.62, 0.85), PALETTES[rng.choice(choice)], ang))
        # leaves: long narrow blades from the tie
        self.leaves = []
        for k in range(rng.randint(2, 4)):
            side = -1 if k % 2 == 0 else 1
            if rng.random() < 0.8:
                ang = -math.pi / 2 + side * rng.uniform(0.3, 0.75)
                ln = R * rng.uniform(1.1, 1.6)
                bend = side * rng.uniform(0.15, 0.35)
            else:
                ang = -math.pi / 2 + side * rng.uniform(0.85, 1.1)
                ln = R * rng.uniform(0.9, 1.2)
                bend = side * rng.uniform(0.3, 0.45)
            self.leaves.append((side * rng.uniform(0.0, 1.5), rng.uniform(-0.6, 0.6), ang, ln,
                                R * rng.uniform(0.06, 0.085), bend, rng.uniform(0, TAU)))
        nst = len(self.blooms) + len(self.buds)
        self.stem_off = [rng.uniform(-1.0, 1.0) * min(2.5, R * 0.1) for _ in range(nst)]
        self.low_stems = sorted(rng.uniform(-1, 1) for _ in range(max(3, nst)))
        self.ribbon_col = rng.choice(RIBBONS)
        self.bow = rng.uniform(0.85, 1.2)
        self.pollen = []
        self.motes = [[rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0, TAU), rng.uniform(0.3, 1.0)]
                      for _ in range(max(6, int(w * h / 300)))]
        self.frame = 0
        self.breeze = 0.0

    # ------------------------------------------------------------------ motion
    def update(self, dt):
        super().update(dt)
        t = self.t
        sway = self.opt("sway")
        gy = self.gy
        breeze = 0.65 * math.sin(t * 0.42) + 0.35 * noise1(t * 0.25, 7)
        self.breeze = breeze
        for b in self.blooms + self.buds:
            height = (gy - b.y0) / max(1.0, gy)
            dx = sway * (breeze * 1.3 + 0.45 * math.sin(t * 0.9 + b.sph)) * height * self.R * 0.13
            b.x = b.x0 + dx
            b.y = b.y0 + abs(dx) * 0.04 + 0.1 * math.sin(t * 0.7 + b.sph)
        for b in self.blooms:
            b.open = 0.5 + 0.5 * math.sin(t * b.rate + b.phase)
            if b.anthers and self.rng.random() < dt * 0.6:
                ax, ay = self.rng.choice(b.anthers)
                self.pollen.append([b.x + ax, b.y + ay, self.rng.uniform(-0.5, 0.5), self.rng.uniform(-0.45, -0.12),
                                    0.0, self.rng.uniform(4, 9)])
        keep = []
        for p in self.pollen:
            p[4] += dt
            p[0] += (p[2] + breeze * 0.7 * sway + 0.3 * math.sin(p[4] * 1.3 + p[5])) * dt
            p[1] += p[3] * dt
            if p[4] < p[5] and -2 < p[0] < self.w + 2 and p[1] > -2:
                keep.append(p)
        self.pollen = keep[-200:]
        for m in self.motes:
            m[1] -= dt * 0.12 * m[3]
            m[0] += dt * 0.2 * math.sin(t * 0.3 + m[2])
            if m[1] < 0:
                m[1] += self.h
                m[0] = self.rng.uniform(0, self.w)

    # ------------------------------------------------------------------ drawing
    def draw(self, cv):
        t = self.t
        nbl = len(self.blooms)
        for b in self.blooms:
            if b.sprite is None:
                self.render_bloom(b)
        if nbl:
            self.render_bloom(self.blooms[self.frame % nbl])   # round-robin refresh
        self.frame += 1
        for x, y, ph, k in self.motes:
            tw = 0.5 + 0.5 * math.sin(t * 0.8 + ph * 3)
            cv.shade(x, y, 0.05 + 0.1 * tw * k, (150, 140, 190))
        self.draw_low_stems(cv)
        for lf in self.leaves:
            self.draw_leaf(cv, lf)
        for k, b in enumerate(self.buds):
            self.draw_stem(cv, b.x, b.y, self.stem_off[nbl + k])
            self.draw_bud(cv, b)
        order = sorted(range(nbl), key=lambda i: self.blooms[i].depth)
        for i in order:
            b = self.blooms[i]
            self.draw_stem(cv, b.x, b.y, self.stem_off[i], b.R * 0.4)
        for i in order:
            self.blit(cv, self.blooms[i])
        if self.opt("ribbon"):
            self.draw_ribbon(cv)
        for x, y, vx, vy, age, life in self.pollen:
            f = age / life
            a = min(1.0, age * 2) * (1 - f) ** 1.2
            cv.shade(x, y, 0.2 + 0.5 * a, mix((255, 160, 50), (255, 236, 160), a), "max", False)

    # ---- one bloom into a sprite
    def render_bloom(self, b):
        pal = b.pal
        edge_c, mid_c, stripe_c, throat_c, spot_c = pal["edge"], pal["mid"], pal["stripe"], pal["throat"], pal["spot"]
        op = b.open
        R = b.R * (0.96 + 0.04 * op)
        cp, sp = math.cos(b.psi), math.sin(b.psi)
        s = b.squash
        inv_s = 1.0 / s
        rot = b.rot + 0.03 * math.sin(self.t * 0.5 + b.sph)
        curl = 0.75 + 0.5 * op                         # breathing: tips sweep further when open
        petals = b.petals
        ext = R * 1.12
        sin, cos, sqrt, atan2 = math.sin, math.cos, math.sqrt, math.atan2
        white = (255, 255, 255)
        sprite = []
        cells = {}
        for ky in range(-int(ext / ASPECT) - 1, int(ext / ASPECT) + 2):
            py = (ky + 0.5) * ASPECT
            for kx in range(-int(ext) - 1, int(ext) + 2):
                px = kx + 0.5
                a1 = (px * cp + py * sp) * inv_s
                a2 = -px * sp + py * cp
                lx = a1 * cp - a2 * sp
                ly = a1 * sp + a2 * cp
                r = sqrt(lx * lx + ly * ly) / R
                if r > 1.12:
                    continue
                th = atan2(ly, lx) - rot
                k0 = math.floor(th / SECTOR)
                best = None
                near_inner = 9.0
                for k in (k0 - 1, k0, k0 + 1):
                    pt = petals[k % 6]
                    dth = (th - k * SECTOR - pt["dphi"] - pt["bend"] * curl * r * r + math.pi) % TAU - math.pi
                    a = r * cos(dth) / pt["len"]
                    if a <= 0.02 or a >= 1.0:
                        continue
                    hw = pt["wid"] * sin(math.pi * a ** 0.72) ** 1.1
                    c = r * sin(dth) / hw if hw > 1e-4 else 9.0
                    ac = abs(c)
                    if ac >= 1.0:
                        if pt["inner"] and ac < near_inner:
                            near_inner = ac
                        continue
                    layer = 1 if pt["inner"] else 0
                    if best is None or layer > best[0]:
                        best = (layer, a, c, k, hw)
                if best is None:
                    if r < 0.12:      # the throat
                        q = 1 - r / 0.12
                        sprite.append((kx, ky, 0.42 + 0.2 * q, mix(throat_c, (220, 236, 140), q * 0.7), None))
                    continue
                cells[(kx, ky)] = best + (r, near_inner)
        for (kx, ky), (layer, a, c, k, hw, r, near_inner) in cells.items():
            pt = petals[k % 6]
            ac = abs(c)
            # the petal axis direction at this radius (tangent of the curved axis), in screen space
            phi = rot + k * SECTOR + pt["dphi"] + pt["bend"] * curl * r * r
            tang = phi + math.atan(2 * pt["bend"] * curl * r * r)
            dx, dy = cos(tang), sin(tang)
            a1 = (dx * cp + dy * sp) * s
            a2 = -dx * sp + dy * cp
            ux, uy = a1 * cp - a2 * sp, a1 * sp + a2 * cp
            # smooth lighting: brighter toward the tip, the half facing the light brighter
            side = (1 if c > 0 else -1) * (-uy * SLX + ux * SLY)
            lam = 0.5 + 0.38 * smoothstep(0.05, 0.62, a) + 0.16 * side * min(1.0, ac * 1.6)
            if layer == 0:
                lam *= 0.86
                if near_inner < 1.35:                       # tucked under an inner petal
                    lam *= 0.62 + 0.38 * (near_inner - 1.0) / 0.35
            lam = clamp(lam)
            # colour: deep stripe and throat at the base, margin colour toward the edges and tip
            col = mix(mid_c, edge_c, clamp(ac * 1.1 - 0.15 + (a - 0.55) * 0.9))
            if ac < 0.4:
                col = mix(col, stripe_c, 0.6 * (1 - ac / 0.4) * clamp(1.15 - a * 1.3))
            if a < 0.28:
                col = mix(col, throat_c, ((0.28 - a) / 0.28) ** 1.5)
            if spot_c is not None and 0.14 < a < 0.5 and 0.15 < ac < 0.7:
                hsh = ((int(a * 22) * 73856093) ^ (int(c * 4 + 9) * 19349663) ^ (k * 83492791) ^ b.seed) & 1023
                if hsh < 150:
                    col = mix(col, spot_c, 0.75)
            br = 0.45 + 0.6 * lam
            col = (min(255, col[0] * br), min(255, col[1] * br), min(255, col[2] * br))
            cw = hw * R                                   # petal half width in cells here
            if cw > 1.2 and (ac > 1 - 0.75 / cw or a > 0.95):
                # the outline: a lighter glyph in a brighter colour
                sprite.append((kx, ky, 0.56, mix(col, white, 0.4), None))
                continue
            if layer and cw > 2.0 and ac < 0.5 / cw and 0.15 < a < 0.8:
                # the midrib: a stroke that follows the petal
                sprite.append((kx, ky, 1.0, mix(stripe_c, col, 0.35), _slope_ch(ux, uy / ASPECT)))
                continue
            v = 0.62 if lam < 0.66 else 0.76 if lam < 0.84 else 0.9
            if layer == 0:
                v -= 0.06
            sprite.append((kx, ky, v, col, None))
        # stamens: thin strokes in the gaps, anthers poking past the petal tips
        fil = (190, 210, 150)
        b.anthers = []
        lean = math.sqrt(max(0.0, 1 - s * s))
        for ang, ln, wob in b.stamens:
            a0 = rot + ang
            Ls = R * ln * (0.95 + 0.05 * op)
            n = max(4, int(Ls * 1.4))
            pts = []
            for i in range(n + 1):
                f = i / n
                rr = Ls * (0.1 + 0.9 * f)
                aa = a0 + wob * f * f
                lx, ly = math.cos(aa) * rr, math.sin(aa) * rr
                a1 = (lx * cp + ly * sp) * s
                a2 = -lx * sp + ly * cp
                x = a1 * cp - a2 * sp + cp * lean * Ls * 0.35 * f
                y = (a1 * sp + a2 * cp + sp * lean * Ls * 0.35 * f) / ASPECT
                pts.append((x, y))
            seen = None
            for i in range(max(2, int(n * 0.5)), n + 1):      # the inner half hides in the throat
                x0, y0 = pts[i - 1]
                x1, y1 = pts[i]
                cell = (int(math.floor(x1)), int(math.floor(y1)))
                if cell == seen:
                    continue
                seen = cell
                sprite.append((cell[0], cell[1], 1.0, mix((110, 150, 96), fil, i / n), _slope_ch(x1 - x0, y1 - y0)))
            b.anthers.append(pts[-1])
        anth = pal["anther"]
        for tx, ty in b.anthers:
            sprite.append((int(math.floor(tx)), int(math.floor(ty)), 1.0, anth, None))
        # the pistil: shorter and straighter, rising toward the viewer, with a green stigma
        a0 = rot + b.pistil[0]
        Ls = R * b.pistil[1] * 0.8
        n = max(4, int(Ls * 1.4))
        prev = None
        for i in range(n + 1):
            f = i / n
            rr = Ls * f
            lx, ly = math.cos(a0) * rr * 0.5, math.sin(a0) * rr * 0.5
            a1 = (lx * cp + ly * sp) * s
            a2 = -lx * sp + ly * cp
            x = a1 * cp - a2 * sp + cp * lean * Ls * 0.8 * f
            y = (a1 * sp + a2 * cp + sp * lean * Ls * 0.8 * f) / ASPECT
            if prev is not None and f > 0.55:
                sprite.append((int(math.floor(x)), int(math.floor(y)), 1.0, (176, 214, 140),
                               _slope_ch(x - prev[0], y - prev[1])))
            prev = (x, y)
        sprite.append((int(math.floor(prev[0])), int(math.floor(prev[1])), 0.9, (150, 230, 110), None))
        b.sprite = sprite

    def blit(self, cv, b):
        ox, oy = int(round(b.x)), int(round(b.y))
        shade, put = cv.shade, cv.put
        for kx, ky, v, col, ch in b.sprite:
            if ch is None:
                shade(ox + kx, oy + ky, v, col, "over", False)
            else:
                put(ox + kx, oy + ky, ch, col)

    # ---- stems, leaves, buds, ribbon
    def draw_stem(self, cv, bx, by, off, hide_r=0.0):
        gx, gy = self.gx + off * 0.5, self.gy
        if by >= gy - 1:
            return
        p1 = (gx + (bx - gx) * 0.15, gy - (gy - by) * 0.6)
        pts = bezier((gx, gy), p1, (bx, by), int((gy - by) * 2.5) + 6)
        # stop under the flower so the stem does not show through the gaps between petals
        hide = (hide_r or 0.0) ** 2
        pts = [p for p in pts if (p[0] - bx) ** 2 + ((p[1] - by) * ASPECT) ** 2 > hide]
        if len(pts) > 1:
            stroke(cv, pts, lambda f: mix(STEM_D, STEM_L, 0.35 + 0.25 * f))

    def draw_low_stems(self, cv):
        gx, gy = self.gx, self.gy
        n = len(self.low_stems)
        spread = min(3.5, self.R * 0.18)
        for k, s in enumerate(self.low_stems):
            end = (gx + s * spread * 1.9, cv.h + 1)
            pts = bezier((gx + s * spread * 0.5, gy - 0.5), (gx + s * spread * 0.7, (gy + cv.h) / 2), end,
                         int((cv.h - gy) * 2.5) + 4)
            lam = 0.75 - 0.4 * (k / max(1, n - 1))
            stroke(cv, pts, lambda f, lam=lam: mix(STEM_D, STEM_L, lam * (1 - 0.35 * f)))

    def draw_leaf(self, cv, lf):
        ox, oy, ang, ln, wd, bend, ph = lf
        sway = self.opt("sway")
        ang = ang + sway * (0.04 * math.sin(self.t * 0.8 + ph) + 0.03 * self.breeze)
        x0, y0 = self.gx + ox, self.gy + oy
        ca, sa = math.cos(ang), math.sin(ang)
        px, py = -sa, ca
        n = max(6, int(ln * 1.3))
        left, right = [], []
        for i in range(n + 1):
            f = i / n
            off = bend * ln * f * f
            cx = x0 + ca * ln * f + px * off
            cy = y0 * ASPECT + sa * ln * f + py * off
            tx, ty = ca + px * 2 * bend * f, sa + py * 2 * bend * f
            tn = math.hypot(tx, ty) or 1.0
            nx, ny = -ty / tn, tx / tn
            hw = wd * 2.2 * (f ** 0.6) * (1 - f) ** 0.9
            left.append((cx + nx * hw, (cy + ny * hw) / ASPECT))
            right.append((cx - nx * hw, (cy - ny * hw) / ASPECT))
            if hw > 0.9:                                   # a soft fill between the edges
                ns = int(hw * 1.2)
                for j in range(-ns + 1, ns):
                    q = j / ns
                    lam = 0.5 + 0.3 * q * (1 if bend > 0 else -1)
                    cv.shade(cx + nx * hw * q, (cy + ny * hw * q) / ASPECT, 0.2 + 0.12 * lam,
                             mix((20, 70, 34), (80, 160, 80), lam), "over", False)
        stroke(cv, left, lambda f: mix(STEM_D, STEM_L, 0.7))
        stroke(cv, right, lambda f: mix(STEM_D, STEM_L, 0.45))

    def draw_bud(self, cv, b):
        green, tip = (90, 170, 90), b.pal["mid"]
        ln = b.size
        ang = b.ang + 0.05 * math.sin(self.t * 0.9 + b.sph)
        ca, sa = math.cos(ang), math.sin(ang)
        px, py = -sa, ca
        x0 = b.x - ca * ln * 0.3
        y0 = b.y * ASPECT - sa * ln * 0.3
        n = max(6, int(ln * 1.4))
        left, right = [], []
        for i in range(n + 1):
            f = i / n
            hw = ln * 0.5 * (f ** 1.3) * (1 - f) ** 0.6
            cx, cy = x0 + ca * ln * f, y0 + sa * ln * f
            left.append((cx + px * hw, (cy + py * hw) / ASPECT))
            right.append((cx - px * hw, (cy - py * hw) / ASPECT))
            if hw > 0.7:
                ns = int(hw * 1.3)
                for j in range(-ns + 1, ns):
                    q = j / ns
                    lam = clamp(0.62 + 0.3 * q * (1 if ca < 0 else -1) - 0.2 * abs(q))
                    col = mix(green, mix(tip, (255, 255, 255), 0.3), clamp((f - 0.25) / 0.5))
                    k = 0.5 + 0.5 * lam
                    cv.shade(cx + px * hw * q, (cy + py * hw * q) / ASPECT, 0.62 if lam < 0.6 else 0.76,
                             (col[0] * k, col[1] * k, col[2] * k), "over", False)
        rim = mix(green, mix(tip, (255, 255, 255), 0.5), 0.6)
        stroke(cv, left, lambda f: mix(green, rim, f))
        stroke(cv, right, lambda f: mix(green, rim, f))

    def draw_ribbon(self, cv):
        R = self.R
        gx, gy = self.gx, self.gy
        col = self.ribbon_col
        dark = mix(col, (20, 10, 30), 0.45)
        light = mix(col, (255, 255, 255), 0.35)
        t = self.t
        bw = max(2, int(min(4.0, R * 0.16)) + 1)        # the band around the stems
        y = int(gy)
        for x in range(int(gx) - bw, int(gx) + bw + 1):
            cv.put(x, y, "=", mix(light, dark, (x - gx + bw) / (2 * bw)))
        size = max(3.0, R * 0.32) * self.bow
        sw = 0.05 * math.sin(t * 0.7) * self.opt("sway")
        for side in (-1, 1):                              # two teardrop loops
            pts = []
            n = max(10, int(size * 4))
            for i in range(n + 1):
                a = TAU * i / n
                lx = (1 - math.cos(a)) * 0.5 * size
                ly = math.sin(a) * size * 0.3 * (1 - math.cos(a)) * 0.6
                ang = -0.32 + sw
                pts.append((gx + side * (lx * math.cos(ang) - ly * math.sin(ang)),
                            gy + (lx * math.sin(ang) + ly * math.cos(ang)) / ASPECT))
            stroke(cv, pts, lambda f: mix(light, dark, 0.3 + 0.4 * abs(math.sin(f * math.pi))))
        for side in (-1, 1):                              # two tails
            p0 = (gx + side * 0.6, gy + 0.6)
            p1 = (gx + side * size * 0.45, gy + size * 0.5 / ASPECT)
            p2 = (gx + side * size * (0.6 + 0.12 * math.sin(t * 0.6 + side)), gy + size * 1.15 / ASPECT)
            stroke(cv, bezier(p0, p1, p2, max(6, int(size * 3))), lambda f: mix(light, dark, f * 0.6))
        cv.put(gx, gy, "@", light)
        cv.put(gx - 1, gy, "(", col)
        cv.put(gx + 1, gy, ")", col)
