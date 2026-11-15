"""A single rose unfurling from a tight bud, holding, dropping a petal now and then, then starting over.

The flower is real 3D: every petal is a patch of a surface of revolution whose profile opens and
curls back as the bloom progresses (outer petals first). Petals are splatted into a z-buffer,
lit from the upper left, with contact shadows where one petal passes in front of another.
The rendering is spread over a few frames so it stays cheap.
"""
import math

from ..engine import ASPECT, Scene, clamp, mix, smoothstep

# dark (deep inside), body, bright (lit rim), underside
COLORS = {
    "red": ((100, 0, 22), (220, 20, 52), (255, 140, 140), (180, 24, 50)),
    "pink": ((110, 20, 60), (246, 110, 166), (255, 206, 226), (226, 120, 170)),
    "white": ((120, 110, 100), (246, 238, 226), (255, 255, 252), (230, 232, 214)),
    "yellow": ((140, 70, 0), (250, 196, 40), (255, 244, 170), (240, 200, 80)),
    "coral": ((120, 20, 10), (255, 110, 80), (255, 200, 160), (236, 120, 90)),
    "purple": ((50, 10, 70), (160, 70, 210), (226, 180, 255), (150, 90, 200)),
    # bicolours: the lit rims take a second hue
    "sunrise": ((150, 70, 0), (252, 200, 60), (255, 120, 110), (240, 190, 90)),
    "blush": ((130, 110, 110), (250, 240, 236), (255, 140, 180), (236, 226, 220)),
    "flame": ((110, 10, 0), (240, 80, 20), (255, 220, 90), (220, 90, 40)),
    "lilac": ((70, 40, 90), (210, 170, 240), (255, 240, 255), (190, 160, 220)),
}
RANDOM_POOL = ["red", "pink", "white", "yellow", "coral", "red", "purple", "sunrise", "blush", "flame", "lilac"]
GOLDEN = math.pi * (3 - math.sqrt(5))
TAU = math.tau

_L = (-0.55, -0.55, 0.65)          # light: upper left, a little in front
_n = math.sqrt(sum(c * c for c in _L))
LX, LY, LZ = (c / _n for c in _L)


def _dirch(dx, dy):
    ax, ay = abs(dx), abs(dy * ASPECT)
    if ax > 2.4 * ay:
        return "-"
    if ay > 2.4 * ax:
        return "|"
    return "\\" if dx * dy > 0 else "/"


class Rose(Scene):
    name = "rose"
    title = "Rose"
    blurb = "a single rose unfurling from a bud, dropping a petal now and then"
    tags = ("flowers", "nature", "calm")
    options = {
        "color": ("random", "red, pink, white, yellow, coral, purple, sunrise, blush, flame, lilac or random"),
        "bloom": (20.0, "seconds for the bud to open fully"),
        "loop": (True, "start over with a new rose after a while"),
    }

    def setup(self):
        w, h = self.w, self.h
        self.S = max(4.0, min(w * 0.2, h * ASPECT * 0.28))   # rose scale (x cells)
        self.cx = w / 2
        self.cy = h * 0.42
        self.motes = [[self.rng.uniform(0, w), self.rng.uniform(0, h), self.rng.uniform(0, TAU)]
                      for _ in range(max(5, w * h // 260))]
        self.new_rose(first=True)

    def new_rose(self, first=False):
        rng = self.rng
        c = self.opt("color")
        if c not in COLORS:
            pool = [k for k in RANDOM_POOL if k != getattr(self, "cname", None)]
            c = rng.choice(pool)
        self.cname = c
        self.pal = COLORS[c]
        self.age = 0.0
        self.fade = 1.0
        # the rose's genome: how many petals, how wide, how far they open and curl, the view
        n = rng.randint(18, 30)
        g_span = rng.uniform(0.85, 1.15)
        g_open = rng.uniform(0.95, 1.25)
        g_curl = rng.uniform(0.6, 1.3)
        g_len = rng.uniform(0.9, 1.1)
        self.elev = rng.uniform(0.7, 0.98)
        self.stem_wave = rng.uniform(-1, 1)
        self.leaf_side = rng.choice((-1, 1))
        self.leaf_spots = sorted(rng.uniform(0.45, 0.85) for _ in range(rng.randint(1, 3)))
        self.petals = []
        rot = rng.uniform(0, TAU)
        for i in range(n):
            f = i / (n - 1)
            self.petals.append(dict(
                f=f, phi=rot + i * GOLDEN + rng.uniform(-0.12, 0.12),
                span=(1.25 - 0.62 * f) * rng.uniform(0.92, 1.08) * g_span,
                L=(0.32 + 0.68 * f ** 0.7) * rng.uniform(0.95, 1.05) * g_len,
                r0=0.03 + 0.13 * f, z0=-0.12 * f,
                ac=0.04 + 0.22 * f, ao=0.2 + g_open * f ** 1.3,
                delay=(1 - f) * 0.62, curl=(0.3 + 0.8 * f) * rng.uniform(0.85, 1.15) * g_curl,
                sepal=False, gone=False))
        for k in range(5):
            self.petals.append(dict(
                f=1.0, phi=rot + k * TAU / 5 + 0.3, span=0.12, L=0.34, r0=0.1, z0=-0.2,
                ac=0.12, ao=2.0, delay=0.0, curl=0.2, sepal=True, gone=False))
        self.falling = []
        self.next_drop = rng.uniform(3, 6)
        self.buf = None
        self.job = None
        self.spin = rng.uniform(0, TAU)

    # ------------------------------------------------------------------ motion
    def update(self, dt):
        super().update(dt)
        bloom = max(1.0, self.opt("bloom"))
        self.age += dt
        self.spin += dt * 0.06
        p = self.age / bloom
        hold = 16.0
        if p >= 1.0:
            self.next_drop -= dt
            loose = [pt for pt in self.petals if not pt["sepal"] and not pt["gone"] and pt["f"] > 0.55]
            if self.next_drop <= 0 and len(loose) > 6:
                self.next_drop = self.rng.uniform(2.5, 5.5)
                pt = max(loose, key=lambda q: q["f"] + self.rng.random() * 0.3)
                self.drop(pt)
            if self.opt("loop") and self.age > bloom + hold:
                self.fade = max(0.0, 1 - (self.age - bloom - hold) / 3.0)
                if self.fade <= 0:
                    self.new_rose()
                    return
        keep = []
        floor = self.h - 1.0
        for fp in self.falling:
            fp["t"] += dt
            if fp["y"] < floor:
                fp["vy"] = min(fp["vy"] + dt * 1.2, 2.2)
                fp["y"] += fp["vy"] * dt
                fp["x"] += (math.sin(fp["t"] * 1.3 + fp["ph"]) * 2.2 + fp["drift"]) * dt
                fp["spin"] += dt * fp["rate"]
            else:
                fp["rest"] += dt
            if fp["rest"] < 6 and -4 < fp["x"] < self.w + 4:
                keep.append(fp)
        self.falling = keep

    def drop(self, pt):
        pt["gone"] = True
        S = self.S
        ang = pt["phi"] + self.spin
        x = self.cx + math.cos(ang) * S * 0.8
        y = self.cy + (0.3 - 0.4 * math.sin(ang)) * S * 0.6 / ASPECT
        self.falling.append(dict(x=x, y=y, vy=0.0, t=0.0, ph=self.rng.uniform(0, TAU), drift=self.rng.uniform(-0.6, 0.6),
                                 spin=self.rng.uniform(0, TAU), rate=self.rng.uniform(1.5, 3.0), rest=0.0,
                                 size=max(1.5, S * 0.12)))

    # ------------------------------------------------------------------ rendering
    def render_petals(self, petals, zb, p):
        """Splat petals into zb {cell: (depth, idx, u, v, lit, back)}."""
        S = self.S
        ce, se = math.cos(self.elev), math.sin(self.elev)     # camera elevation, 40-56 degrees
        sin, cos, sqrt = math.sin, math.cos, math.sqrt
        floor = math.floor
        spin = self.spin
        for idx, pt in petals:
            if pt["gone"]:
                continue
            if pt["sepal"]:
                o = smoothstep(0.0, 0.3, p)
            else:
                o = smoothstep(0.0, 1.0, clamp((p - pt["delay"]) / max(0.2, 1 - pt["delay"])))
            alpha = pt["ac"] + (pt["ao"] - pt["ac"]) * o
            curl = pt["curl"] * (0.15 + 0.85 * o)
            pinch = 0.7 * (1 - o) * (0 if pt["sepal"] else 1)
            grow = 0.58 + 0.42 * min(1.0, p * 1.4 + 0.1)
            L = pt["L"] * S * grow
            r = pt["r0"] * S * grow
            z = pt["z0"] * S
            span = pt["span"] * (0.85 + 0.25 * o)
            phi = pt["phi"] + spin
            nu = max(5, int(L * 1.15))
            du = L / nu
            # rough widest radius to pick the sampling across
            rmax = r + L * min(1.0, sin(min(1.57, alpha + curl)))
            nv = max(3, int(span * rmax * 0.95))
            f = pt["f"]
            for iu in range(nu + 1):
                u = iu / nu
                th = alpha - pinch * u + curl * u ** 2.5
                st, ct = sin(th), cos(th)
                if iu:
                    r += st * du
                    z += ct * du
                if r < 0.05:
                    r = 0.05
                umax_ok = u
                width = span * (0.5 + 0.5 * sin(min(1.0, u * 1.7) * 1.5708))
                for jv in range(-nv, nv + 1):
                    v = jv / nv
                    if u > 1 - 0.22 * v * v:          # rounded petal top
                        continue
                    psi = phi + v * width
                    cp, sp = cos(psi), sin(psi)
                    x = r * cp
                    y = r * sp
                    # camera: depth toward the viewer, screen up
                    depth = -y * ce + z * se
                    up = y * se + z * ce
                    key = (int(floor(x)), int(floor(-up / ASPECT)))
                    old = zb.get(key)
                    if old is not None and old[0] >= depth:
                        continue
                    # normal of the surface of revolution
                    nx, ny, nz = -ct * cp, -ct * sp, st
                    facing = -ny * ce + nz * se
                    back = facing < 0
                    if back:
                        nx, ny, nz = -nx, -ny, -nz
                    lit = (nx * LX + ny * LY + nz * LZ + 0.3) / 1.3
                    if lit < 0:
                        lit = 0.0
                    zb[key] = (depth, idx, u, v, lit, back, f)

    def resolve(self, zb):
        dark, body, bright, under = self.pal
        out = []
        get = zb.get
        green_d, green_b = (20, 70, 30), (110, 190, 90)
        petals = self.petals
        dmax = self.S * 0.16
        for (kx, ky), (depth, idx, u, v, lit, back, f) in zb.items():
            occl = False
            for nb in (get((kx, ky + 1)), get((kx - 1, ky + 1)), get((kx + 1, ky + 1))):
                if nb is not None and nb[1] != idx and depth + 1.2 < nb[0] < depth + dmax:
                    occl = True
                    break
            if petals[idx]["sepal"]:
                lam = lit * (0.5 if occl else 1.0)
                out.append((kx, ky, 0.25 + 0.6 * lam, mix(green_d, green_b, lam)))
                continue
            if back:
                ao = 0.75 + 0.25 * min(1.0, u * 2.0)
            else:
                ao = (0.6 + 0.4 * min(1.0, u * 1.8)) * (0.8 + 0.2 * f)
            lam = lit * ao * (0.8 + 0.2 * ((idx * 0.618) % 1.0))     # each petal its own tone
            rim = smoothstep(0.78, 1.0, u + 0.2 * v * v)
            if 0.66 < u + 0.2 * v * v < 0.8:                         # the rim rolls back: a dark crease
                lam *= 0.72
            if back:
                base = mix(dark, under, 0.3 + 0.7 * lam)
            else:
                lam = min(1.0, lam * 1.35)
                base = mix(dark, body, min(1.0, lam * 1.5))
            if occl and not back:
                out.append((kx, ky, 0.12, mix(dark, (0, 0, 0), 0.3)))
                continue
            if back:
                lam = lit * ao * (0.6 if occl else 1.0)
                col = mix(base, bright, clamp(rim * 0.6 * lam))
                out.append((kx, ky, 0.08 + 0.8 * lam ** 1.5 + 0.3 * rim * lam, col))
                continue
            col = mix(base, bright, clamp(rim * 0.9 * lam + max(0.0, lam - 0.7) * 1.2))
            out.append((kx, ky, 0.08 + 0.8 * lam ** 1.5 + 0.3 * rim * lam, col))
        return out

    def render_job(self, p):
        """A generator that renders the flower over a few frames, then yields the finished buffer."""
        zb = {}
        items = list(enumerate(self.petals))
        # sepals behind, then petals; split the work into chunks
        chunk = 8
        for k in range(0, len(items), chunk):
            self.render_petals(items[k:k + chunk], zb, p)
            yield None
        yield self.resolve(zb)

    def step_render(self, full=False):
        p = self.age / max(1.0, self.opt("bloom"))
        if self.job is None:
            self.job = self.render_job(min(1.0, p))
        while True:
            res = next(self.job)
            if res is not None:
                self.buf = res
                self.job = None
                return
            if not full:
                return

    # ------------------------------------------------------------------ drawing
    def draw(self, cv):
        t = self.t
        self.step_render(full=self.buf is None)
        for x, y, ph in self.motes:
            tw = 0.5 + 0.5 * math.sin(t * 0.6 + ph * 5)
            cv.shade(x, y, 0.04 + 0.1 * tw, (170, 140, 170))
        self.draw_stem(cv)
        fade = self.fade
        ox, oy = self.cx, self.cy
        sway = 0.4 * math.sin(t * 0.35)
        bx = int(round(ox + sway))
        by = int(round(oy))
        shade = cv.shade
        for kx, ky, v, col in self.buf:
            if fade < 1:
                v *= fade
                col = (col[0] * fade, col[1] * fade, col[2] * fade)
            shade(bx + kx, by + ky, v, col, "over", False)
        dark, body, bright, under = self.pal
        for fp in self.falling:
            self.draw_falling(cv, fp, body, bright, dark)

    def draw_falling(self, cv, fp, body, bright, dark):
        s = fp["size"]
        flip = math.cos(fp["spin"])
        wx = s * (0.35 + 0.65 * abs(flip))
        a = 1.0 - min(1.0, fp["rest"] / 6.0)
        lam = 0.45 + 0.45 * flip
        for dy in range(-1, 2):
            for dx in range(-int(wx) - 1, int(wx) + 2):
                e = (dx / max(0.6, wx)) ** 2 + (dy * ASPECT / max(0.8, s * 0.9)) ** 2
                if e > 1:
                    continue
                q = 1 - e
                v = (0.35 + 0.55 * q) * a * (0.6 + 0.4 * lam)
                col = mix(mix(dark, body, 0.5 + 0.5 * lam), bright, 0.4 * q * lam)
                cv.shade(fp["x"] + dx, fp["y"] + dy, v, col, "over", False)

    def draw_stem(self, cv):
        S = self.S
        t = self.t
        x0 = self.cx + 0.4 * math.sin(t * 0.35)
        y0 = self.cy + S * 0.3 / ASPECT
        h = cv.h
        dark, light = (20, 70, 30), (120, 200, 96)
        prev = None
        n = int(h - y0) * 2 + 2
        thorn = 0
        pts = []
        for i in range(n + 1):
            f = i / n
            y = y0 + (h - y0) * f
            x = x0 + self.stem_wave * S * 0.18 * math.sin(f * 3.0) - 0.3 * math.sin(t * 0.35) * f
            pts.append((x, y))
            if prev is not None:
                ch = _dirch(x - prev[0], y - prev[1])
                cv.put(x, y, ch, mix(dark, light, 0.75))
                if S > 9:
                    cv.put(x + 1, y, ch, mix(dark, light, 0.35))
            prev = (x, y)
        # thorns
        for k, f in enumerate((0.3, 0.52, 0.78)):
            x, y = pts[int(f * n)]
            side = 1 if k % 2 else -1
            cv.put(x + (2 if side > 0 and S > 9 else side), y, ">" if side > 0 else "<", (150, 110, 60))
        # two leaves (each a little spray of three serrated leaflets)
        for k, f in enumerate(self.leaf_spots):
            side = self.leaf_side * (1 if k % 2 == 0 else -1)
            x, y = pts[int(f * n)]
            self.draw_leafspray(cv, x, y, side, S * (0.55 if k == 0 else 0.45), t + k * 2)

    def draw_leafspray(self, cv, x, y, side, size, t):
        base_ang = (0.0 if side > 0 else math.pi) - side * 0.45 + 0.05 * math.sin(t * 0.7)
        ca, sa = math.cos(base_ang), math.sin(base_ang)
        # petiole
        steps = max(2, int(size * 0.8))
        for i in range(1, steps + 1):
            px = x + ca * size * 0.8 * i / steps
            py = y + sa * size * 0.8 * i / steps / ASPECT
            cv.put(px, py, _dirch(ca, sa / ASPECT), (60, 130, 60))
        tipx = x + ca * size * 0.8
        tipy = y + sa * size * 0.8 / ASPECT
        self.leaflet(cv, tipx, tipy, base_ang, size * 0.62)
        self.leaflet(cv, x + ca * size * 0.42, y + sa * size * 0.42 / ASPECT, base_ang - side * 1.0, size * 0.48)
        self.leaflet(cv, x + ca * size * 0.42, y + sa * size * 0.42 / ASPECT, base_ang + side * 1.0, size * 0.48)

    def leaflet(self, cv, x0, y0, ang, ln):
        ca, sa = math.cos(ang), math.sin(ang)
        px, py = -sa, ca
        wd = ln * 0.38
        nf = max(3, int(ln * 1.5))
        dark, light = (16, 60, 26), (120, 200, 90)
        for i in range(nf + 1):
            f = i / nf
            hw = wd * math.sin(math.pi * f ** 0.8) * (1 + 0.15 * math.sin(f * 18))   # serrated
            ns = max(1, int(hw * 1.6))
            cx = x0 + ca * ln * f
            cy = y0 * ASPECT + sa * ln * f
            for j in range(-ns, ns + 1):
                s = j / ns
                lit = clamp(0.55 + 0.4 * (s if py * -1 + px * -0.6 > 0 else -s))
                if abs(s) < 0.2:
                    v, col = 0.5, (150, 214, 120)
                else:
                    v, col = 0.3 + 0.5 * lit, mix(dark, light, lit)
                cv.shade(cx + px * hw * s, (cy + py * hw * s) / ASPECT, v, col, "over", False)
