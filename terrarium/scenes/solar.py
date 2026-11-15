"""A solar system in perspective: a flickering star, shaded planets on tilted orbits, rings, moons, comets."""
import math

from ..engine import ASPECT, Canvas, Scene, clamp, gradient, hsv, mix, noise1, noise2, scale

TAU = math.tau

STARS = {
    #         core              mid               rim              corona
    "yellow": ((255, 255, 235), (255, 220, 120), (255, 150, 40), (255, 170, 70)),
    "orange": ((255, 240, 200), (255, 170, 80), (230, 90, 30), (255, 120, 50)),
    "white": ((255, 255, 255), (220, 235, 255), (150, 190, 255), (170, 200, 255)),
    "red": ((255, 210, 170), (255, 110, 70), (180, 40, 30), (255, 80, 60)),
}
PLANETS = {
    # kind: (radius range in cells, palettes)
    "rocky": ((0.8, 1.5), [[(90, 60, 50), (190, 120, 80), (240, 180, 130)], [(80, 80, 85), (160, 150, 140), (220, 210, 200)],
                           [(110, 40, 30), (210, 90, 50), (250, 160, 110)]]),
    "ocean": ((1.1, 1.8), [[(20, 50, 120), (50, 120, 210), (150, 210, 255)], [(20, 70, 90), (40, 150, 160), (150, 240, 220)]]),
    "gas": ((2.2, 3.6), [[(120, 80, 50), (220, 170, 110), (250, 225, 180)], [(110, 70, 40), (200, 140, 90), (240, 210, 170)],
                         [(70, 60, 110), (160, 140, 210), (230, 210, 255)]]),
    "ice": ((1.6, 2.6), [[(40, 90, 120), (100, 190, 220), (200, 245, 255)], [(40, 60, 130), (90, 130, 230), (180, 210, 255)]]),
}
RING_COLS = [(220, 200, 160), (200, 190, 210), (170, 210, 230), (230, 180, 140)]


def _hash(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 982451653) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 65535.0


class Planet:
    __slots__ = ("a", "e", "w", "th", "n", "r", "kind", "pal", "ring", "moons", "band", "spin", "seed", "x", "y", "z", "X", "Z")


class Solar(Scene):
    name = "solar"
    title = "Solar System"
    blurb = "a star with shaded planets on tilted orbits, rings, moons and the odd comet"
    tags = ("space", "calm", "science")
    options = {
        "planets": (0, "number of planets (0 = random)"),
        "speed": (1.0, "orbital speed multiplier"),
        "orbits": (True, "draw faint orbit lines"),
        "star": ("random", "random, yellow, orange, white or red"),
    }

    # ------------------------------------------------------------------ setup
    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.seed = rng.randrange(1 << 15)
        st = str(self.opt("star")).lower()
        self.star = STARS[st] if st in STARS else STARS[rng.choice(("yellow", "yellow", "orange", "white", "red"))]
        self.cx = w / 2 + rng.uniform(-0.05, 0.05) * w
        self.cy = h / 2 + rng.uniform(-0.04, 0.04) * h
        big = min(w, h * ASPECT)
        self.R = clamp(big * rng.uniform(0.055, 0.085), 2.2, 10)
        self.tilt = rng.uniform(0.32, 0.55)            # sin of the orbital plane's inclination to the view
        self.ct = math.sqrt(1 - self.tilt ** 2)
        n = self.opt("planets")
        if n <= 0:
            n = rng.randint(4, 8)
        n = max(1, min(12, n))
        amax = min(w * 0.49, (h * 0.5 - 1.5) * ASPECT / self.tilt * 0.98)
        amin = self.R * 1.9 + 2
        amax = max(amin + 4, amax)
        # spacing: roughly geometric, like real systems
        q = (amax / amin) ** (1 / max(1, n - 1)) if n > 1 else 1.0
        self.planets = []
        for i in range(n):
            p = Planet()
            p.a = amin * q ** i * rng.uniform(0.94, 1.04) if n > 1 else (amin + amax) / 2
            frac = i / max(1, n - 1)
            if frac < 0.35:
                kind = rng.choice(("rocky", "rocky", "ocean"))
            elif frac < 0.8:
                kind = rng.choice(("gas", "gas", "ice", "ocean"))
            else:
                kind = rng.choice(("ice", "gas", "rocky"))
            rr, pals = PLANETS[kind]
            p.kind = kind
            p.r = rng.uniform(*rr) * clamp(big / 68, 0.6, 2.0)
            p.pal = rng.choice(pals)
            if rng.random() < 0.3:    # recolour: hue jitter for variety
                hj = rng.uniform(-0.08, 0.08)
                p.pal = [self.hue_shift(c, hj) for c in p.pal]
            p.e = rng.uniform(0.0, 0.22)
            p.w = rng.uniform(0, TAU)
            p.th = (i * 2.39996 + rng.uniform(-0.5, 0.5)) % TAU
            p.n = 1.6 * (amin / p.a) ** 1.5           # mean motion, Kepler's third law
            p.ring = None
            if kind in ("gas", "ice") and rng.random() < 0.45:
                p.ring = (rng.uniform(1.5, 1.8), rng.uniform(2.2, 2.9), rng.uniform(0.22, 0.4), rng.choice(RING_COLS))
            p.moons = [(rng.uniform(1.8, 3.2) * p.r, rng.uniform(0, TAU), rng.uniform(0.8, 2.2) * rng.choice((-1, 1)))
                       for _ in range(rng.randint(0, 2 if kind in ("gas", "ice") else 1))]
            p.band = rng.uniform(3.0, 7.0)
            p.spin = rng.uniform(0.2, 0.6)
            p.seed = rng.randrange(1000)
            self.planets.append(p)
        # make sure at least one ringed giant appears in most systems
        giants = [p for p in self.planets if p.kind in ("gas", "ice")]
        if giants and not any(p.ring for p in giants) and rng.random() < 0.7:
            g = rng.choice(giants)
            g.ring = (1.55, 2.6, rng.uniform(0.25, 0.4), rng.choice(RING_COLS))
        self.belt = None
        if n >= 3 and rng.random() < 0.55:
            k = rng.randint(1, n - 2)
            a0, a1 = self.planets[k].a, self.planets[k + 1].a
            self.belt = [(rng.uniform(a0 * 1.12, a1 * 0.88), rng.uniform(0, TAU), rng.random()) for _ in range(int(rng.uniform(60, 160) * w / 120))]
        self.comet = None
        self.comet_timer = rng.uniform(3, 12)
        self._bgkey = None
        self.place(0)

    @staticmethod
    def hue_shift(c, k):
        r, g, b = c
        return (clamp(r * (1 + k * 3), 0, 255), clamp(g * (1 - abs(k)), 0, 255), clamp(b * (1 - k * 3), 0, 255))

    def project(self, X, Z):
        """Orbit-plane coordinates (x cells, Z depth cells; +Z = far) -> screen x, y."""
        return self.cx + X, self.cy - Z * self.tilt / ASPECT

    def place(self, dt):
        sp = self.opt("speed")
        for p in self.planets:
            # true anomaly advances faster near periapsis
            r = p.a * (1 - p.e * p.e) / (1 + p.e * math.cos(p.th))
            p.th += dt * sp * p.n * (p.a / r) ** 2 * math.sqrt(1 - p.e * p.e)
            r = p.a * (1 - p.e * p.e) / (1 + p.e * math.cos(p.th))
            p.X = r * math.cos(p.th + p.w)
            p.Z = r * math.sin(p.th + p.w)
            p.x, p.y = self.project(p.X, p.Z)

    # ------------------------------------------------------------------ static: stars, milky way, orbits
    def paint_static(self, cv):
        w, h = self.w, self.h
        rng_s = self.seed
        ang = (rng_s % 360) / 360 * math.pi
        ca, sa = math.cos(ang), math.sin(ang)
        for y in range(h):
            for x in range(w):
                # a faint milky-way band
                u = ((x - w / 2) * sa - (y - h / 2) * ASPECT * ca) / max(w, h * ASPECT)
                band = math.exp(-(u / 0.12) ** 2)
                n = noise2(x * 0.08, y * 0.16, rng_s) * 0.5 + 0.5
                r = _hash(x, y, rng_s)
                if r < 0.012 + 0.06 * band * n:
                    b = _hash(y, x, rng_s + 1)
                    ch = "." if b < 0.6 else "·" if b < 0.85 else "+" if b < 0.96 else "*"
                    col = mix((150, 160, 200), (255, 240, 220), b) if r > 0.006 else hsv(0.55 + b * 0.5, 0.35, 0.9)
                    cv.put(x, y, ch, scale(col, 0.35 + 0.6 * b), level=0.2)
                elif band * n > 0.45 and r < 0.25:
                    cv.put(x, y, ".", scale((110, 100, 150), band * n * 0.7), level=0.1)

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
        rng = self.rng
        self.place(dt)
        c = self.comet
        if c is None:
            self.comet_timer -= dt
            if self.comet_timer <= 0:
                self.spawn_comet()
        else:
            # parabolic orbit: s parameter advances so the speed scales like 1/sqrt(r)
            q, s, rot, d = c["q"], c["s"], c["rot"], c["d"]
            r = q * (1 + s * s)
            c["s"] = s + d * dt * c["k"] / r ** 1.5 * q ** 0.5 * 2.2 * max(0.2, self.opt("speed")) ** 0.5
            if abs(c["s"]) > c["smax"]:
                self.comet = None
                self.comet_timer = rng.uniform(10, 25)

    def spawn_comet(self):
        rng = self.rng
        q = rng.uniform(self.R * 2.0, self.R * 5.0)
        d = rng.choice((-1, 1))
        span = max(self.w, self.h * ASPECT / self.tilt) * 0.75
        smax = math.sqrt(max(1.0, span / q))
        self.comet = {"q": q, "s": -d * smax, "rot": rng.uniform(0, TAU), "d": d, "k": rng.uniform(6, 10), "smax": smax * 1.02,
                      "tilt": rng.uniform(-0.6, 0.6)}

    def comet_pos(self, s=None):
        c = self.comet
        s = c["s"] if s is None else s
        q = c["q"]
        X0, Z0 = q * (1 - s * s), 2 * q * s
        cr, sr = math.cos(c["rot"]), math.sin(c["rot"])
        X, Z = X0 * cr - Z0 * sr, X0 * sr + Z0 * cr
        x, y = self.project(X, Z)
        return x, y - X * c["tilt"] * 0.12, X, Z

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, t = self.w, self.h, self.t
        if (cv.w, cv.h) != (w, h):
            return
        self.background(cv)
        # twinkle a few stars
        put = cv.put
        for k in range(int(w * h / 300)):
            x = int(_hash(k, 1, self.seed) * w)
            y = int(_hash(k, 2, self.seed) * h)
            if math.sin(t * (1 + k % 5) + k) > 0.92:
                put(x, y, "+", (230, 235, 255), level=0.3)
        if self.opt("orbits"):
            self.draw_orbits(cv, far=True)
        self.draw_belt(cv, far=True)
        far = sorted([p for p in self.planets if p.Z >= 0], key=lambda p: -p.Z)
        near = sorted([p for p in self.planets if p.Z < 0], key=lambda p: -p.Z)
        if self.comet is not None and self.comet_pos()[3] >= 0:
            self.draw_comet(cv)
        for p in far:
            self.draw_planet(cv, p)
        self.draw_sun(cv)
        if self.opt("orbits"):
            self.draw_orbits(cv, far=False)
        self.draw_belt(cv, far=False)
        if self.comet is not None and self.comet_pos()[3] < 0:
            self.draw_comet(cv)
        for p in near:
            self.draw_planet(cv, p)

    def draw_orbits(self, cv, far):
        put = cv.put
        w, h = self.w, self.h
        R = self.R
        for p in self.planets:
            n = int(p.a * 2.2) + 12
            col = scale(mix(p.pal[1], (130, 140, 190), 0.55), 0.55 if far else 0.75)
            for k in range(n):
                th = k / n * TAU
                r = p.a * (1 - p.e * p.e) / (1 + p.e * math.cos(th))
                X = r * math.cos(th + p.w)
                Z = r * math.sin(th + p.w)
                if (Z >= 0) != far:
                    continue
                x, y = self.project(X, Z)
                xi, yi = int(x), int(y)
                if 0 <= xi < w and 0 <= yi < h and cv.lv[yi * w + xi] < 0.25:
                    put(xi, yi, "." if k % 2 else "·", col, level=0.2)

    def draw_belt(self, cv, far):
        if not self.belt:
            return
        put = cv.put
        t = self.t * max(0.0, self.opt("speed"))
        amin = self.R * 1.9 + 2
        for a, th0, b in self.belt:
            th = th0 + t * 1.6 * (amin / a) ** 1.5
            X, Z = a * math.cos(th), a * math.sin(th)
            if (Z >= 0) != far:
                continue
            x, y = self.project(X, Z)
            put(x, y, "." if b < 0.7 else "·" if b < 0.93 else "o", scale((170, 150, 130), 0.4 + 0.5 * b), level=0.25)

    def draw_sun(self, cv):
        w, h, t = self.w, self.h, self.t
        cx, cy, R = self.cx, self.cy, self.R
        core, mid, rim, cor = self.star
        put = cv.put
        ramp = cv.ramp
        rn = len(ramp) - 1
        Rc = R * 3.2
        s = self.seed
        for y in range(max(0, int(cy - Rc / ASPECT) - 1), min(h, int(cy + Rc / ASPECT) + 2)):
            dy = (y + 0.5 - cy) * ASPECT
            for x in range(max(0, int(cx - Rc) - 1), min(w, int(cx + Rc) + 2)):
                dx = x + 0.5 - cx
                d = math.sqrt(dx * dx + dy * dy) / R
                dtop = math.sqrt(dx * dx + (dy - 0.25 * ASPECT) ** 2) / R
                dbot = math.sqrt(dx * dx + (dy + 0.25 * ASPECT) ** 2) / R
                if dtop <= 1.0 or dbot <= 1.0:
                    # limb darkening + boiling granulation
                    gran = noise2(x * 0.45 + t * 0.5, y * 0.9 - t * 0.35, s + 7)
                    col = mix(mix(core, mid, min(1.0, d) ** 1.6), rim, clamp(d - 0.72) * 3)
                    col = mix(col, rim if gran < 0 else core, abs(gran) * 0.35)
                    col = scale(col, 1.0 - 0.25 * min(1.0, d) ** 3)
                    ch = "█" if dtop <= 1.0 and dbot <= 1.0 else "▀" if dtop <= 1.0 else "▄"
                    put(x, y, ch, col, level=1.0)
                    continue
                if d > 3.2:
                    continue
                ang = math.atan2(dy, dx)
                # corona streamers: angular noise that slowly drifts and flickers
                st = noise1(ang * 2.5 + 30 + t * 0.15, s + 3) * 0.6 + noise1(ang * 7 - t * 0.3, s + 4) * 0.4
                fl = 0.85 + 0.15 * noise1(t * 4 + ang, s + 5)
                g = math.exp(-(d - 1) * (1.7 - 1.0 * clamp(st + 0.3))) * fl * (0.75 + 0.25 * clamp(st + 0.5))
                if g < 0.07:
                    continue
                if g > cv.lv[y * w + x]:
                    r_ = _hash(x, y, int(t * 8))
                    ch = "*" if g > 0.62 and r_ > 0.45 else ":" if g > 0.36 else "·" if g > 0.2 else "."
                    put(x, y, ch, scale(mix(cor, rim, clamp(d - 1) * 0.6), 0.35 + 0.75 * g), level=g)

    def draw_planet(self, cv, p):
        w, h, t = self.w, self.h, self.t
        put = cv.put
        ramp = cv.ramp
        rn = len(ramp) - 1
        px, py, r = p.x, p.y, p.r
        # light direction (viewer coords: x right, y up, z toward the viewer)
        X, Y, Zv = p.X, p.Z * self.tilt, -p.Z * self.ct
        L = math.sqrt(X * X + Y * Y + Zv * Zv) or 1.0
        lx, ly, lz = -X / L, -Y / L, -Zv / L
        ring = p.ring
        if ring:
            self.draw_ring(cv, p, back=True)
        dark, base, hi = p.pal
        ry = r / ASPECT
        spin = t * p.spin
        kind = p.kind

        def sample(u, v):
            nz = math.sqrt(max(0.0, 1 - u * u - v * v))
            lit = clamp(u * lx - v * ly + nz * lz)
            if kind in ("gas", "ice"):
                tex = math.sin(v * p.band + noise1(v * 3 + u * 0.8 + spin, p.seed) * 1.2)
                col = gradient((dark, base, hi), clamp(0.55 + 0.35 * tex))
            elif kind == "ocean":
                land = noise2(u * 2.2 + spin * 1.5, v * 2.2, p.seed)
                col = (70, 150, 80) if land > 0.25 else base
                if abs(v) > 0.82:
                    col = (235, 240, 250)
            else:
                cr = noise2(u * 3 + spin, v * 3, p.seed)
                col = gradient((dark, base, hi), clamp(0.55 + 0.4 * cr))
            val = 0.22 + 0.85 * lit ** 0.75
            rim = clamp((1 - nz) * 3 - 1.4) * lit          # bright limb on the day side
            return scale(mix(col, (255, 255, 255), 0.3 * rim), val)

        for y in range(max(0, int(py - ry) - 1), min(h, int(py + ry) + 2)):
            vt = (y + 0.25 - py) * ASPECT / r
            vb = (y + 0.75 - py) * ASPECT / r
            for x in range(max(0, int(px - r) - 1), min(w, int(px + r) + 2)):
                u = (x + 0.5 - px) / r
                top = u * u + vt * vt <= 1
                bot = u * u + vb * vb <= 1
                if top and bot:
                    put(x, y, "█", mix(sample(u, vt), sample(u, vb), 0.5), level=0.9)
                elif top:
                    put(x, y, "▀", sample(u, vt), level=0.9)
                elif bot:
                    put(x, y, "▄", sample(u, vb), level=0.9)
        if ring:
            self.draw_ring(cv, p, back=False)
        # moons
        for rm, ph, sp in p.moons:
            a = ph + t * sp * max(0.0, self.opt("speed"))
            mx = px + rm * math.cos(a)
            mz = rm * math.sin(a)
            my = py - mz * self.tilt / ASPECT
            if mz > 0 and ((mx - px) / r) ** 2 + ((my - py) * ASPECT / r) ** 2 < 1:
                continue
            lit = 0.5 + 0.5 * clamp(-(math.cos(a) * X + mz * 0) / (abs(X) + 1e-6))
            put(mx, my, "•" if lit > 0.6 else "o", scale((220, 220, 230), 0.5 + 0.5 * lit), level=0.8)

    def draw_ring(self, cv, p, back):
        """Ring annulus in half blocks; the back half is drawn before the planet, the front half after."""
        r0, r1, rt, col = p.ring
        put = cv.put
        w, h = self.w, self.h
        px, py, r = p.x, p.y, p.r
        Ro = r * r1
        t = self.t

        def inside(dx, dy):
            e = math.sqrt(dx * dx + (dy / rt) ** 2) / r
            if not r0 <= e <= r1:
                return 0.0
            f = (e - r0) / (r1 - r0)
            if abs(f - 0.6) < 0.07:                      # a Cassini-like division
                return 0.0
            return 0.55 + 0.35 * math.sin(f * 19) * 0.5 + 0.2 * (1 - f)

        for y in range(max(0, int(py - Ro * rt / ASPECT) - 1), min(h, int(py + Ro * rt / ASPECT) + 2)):
            dyt = (y + 0.25 - py) * ASPECT
            dyb = (y + 0.75 - py) * ASPECT
            for x in range(max(0, int(px - Ro) - 1), min(w, int(px + Ro) + 2)):
                dx = x + 0.5 - px
                vt = inside(dx, dyt) if (dyt < 0) == back else 0.0
                vb = inside(dx, dyb) if (dyb < 0) == back else 0.0
                if back:      # hidden behind the planet's disc
                    if vt and dx * dx + dyt * dyt <= r * r:
                        vt = 0.0
                    if vb and dx * dx + dyb * dyb <= r * r:
                        vb = 0.0
                if not (vt or vb):
                    continue
                # the planet's shadow falls across the far side of the ring
                v = max(vt, vb) * (0.6 if back else 1.0)
                c = scale(col, v)
                ch = "█" if vt and vb else "▀" if vt else "▄"
                put(x, y, ch, c, level=0.8)

    def draw_comet(self, cv):
        put = cv.put
        x, y, X, Z = self.comet_pos()
        r = math.hypot(X, Z)
        # tail points away from the star, longer when close
        dx, dy = x - self.cx, (y - self.cy) * ASPECT
        dl = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dl, dy / dl
        L = clamp(self.R * 140 / max(r, 1), 6, max(self.w, 20) * 0.4)
        n = int(L * 2.5)
        t = self.t
        for k in range(n, 0, -1):
            f = k / n
            spread = f * L * 0.12
            wob = noise1(k * 0.4 - t * 3, 5) * spread
            tx = x + ux * f * L - uy * wob
            ty = y + (uy * f * L + ux * wob) / ASPECT
            v = (1 - f) ** 0.9
            if v < 0.05:
                continue
            ch = "*" if v > 0.75 else ":" if v > 0.45 else "." if v > 0.2 else "·"
            put(tx, ty, ch, mix((120, 170, 255), (230, 245, 255), v), level=v)
            # dust tail: fainter, curved and yellower
            put(tx - uy * f * 2.0, ty + ux * f * 2.0 / ASPECT, "." if v > 0.3 else "·", scale((255, 220, 160), 0.3 + 0.5 * v), level=v * 0.5)
        for ox in (-1, 1):
            put(x + ox, y, "·", (150, 200, 255), level=0.6)
        put(x, y, "@", (255, 255, 255), level=1.0)
