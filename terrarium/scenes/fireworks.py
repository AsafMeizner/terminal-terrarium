"""A fireworks show over a lake or a harbour city: shells, many burst types, smoke and reflections."""
import math

from ..engine import ASPECT, RAMPS, Scene, clamp, hsv, mix, noise1

TAU = math.tau
SPARK = " .·:;+**#@"          # used instead of the default ramp
WATER = " .-~~=+*#"
WHITE = (255, 255, 255)
GOLD = (255, 190, 90)
SILVER = (225, 230, 255)

SHOW_PALETTES = {
    "festival": [(255, 60, 70), (60, 255, 120), (80, 140, 255), (255, 220, 60), (230, 90, 255), (60, 230, 255)],
    "goldsilver": [GOLD, (255, 215, 140), SILVER, (255, 170, 70), (240, 240, 255)],
    "tricolor": [(255, 60, 60), (245, 245, 255), (70, 110, 255)],
    "jewel": [(255, 40, 120), (150, 60, 255), (0, 200, 255), (0, 255, 160), (255, 200, 40)],
    "pastel": [(255, 150, 200), (160, 210, 255), (190, 255, 190), (255, 230, 160), (220, 180, 255)],
    "warm": [(255, 90, 40), (255, 170, 50), (255, 60, 110), (255, 220, 120), (255, 120, 80)],
    "cool": [(80, 160, 255), (120, 255, 230), (190, 120, 255), (230, 240, 255), (60, 220, 255)],
}
TYPES = ("peony", "chrysanthemum", "willow", "ring", "palm", "crossette", "strobe", "crackle", "dahlia")


class P:
    """One particle. kind: 0 star, 1 shell, 2 spark, 3 comet (splits), 4 flash."""
    __slots__ = ("x", "y", "vx", "vy", "age", "life", "col", "drag", "grav", "kind", "bright",
                 "hist", "hlen", "htime", "flags", "seed", "btype", "z")

    def __init__(self, x, y, vx, vy, life, col, drag=1.5, grav=1.0, kind=0, bright=1.0, hlen=0, flags=0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.age = 0.0
        self.life = life
        self.col = col
        self.drag = drag
        self.grav = grav
        self.kind = kind
        self.bright = bright
        self.hlen = hlen
        self.hist = [] if hlen else None
        self.htime = 0.0
        self.flags = flags          # 1 glitter, 2 strobe, 4 crackle on death, 8 sheds sparks
        self.seed = 0
        self.btype = None
        self.z = 0.0


class Fireworks(Scene):
    name = "fireworks"
    title = "Fireworks"
    blurb = "a fireworks show over a lake or a harbour city, with smoke, reflections and a finale"
    tags = ("night", "celebration", "colorful", "sky")
    options = {
        "intensity": (1.0, "how busy the show is (0.3 .. 3)"),
        "finale": (True, "end each act with a finale barrage"),
        "backdrop": ("random", "random, lake or city"),
        "palette": ("random", "random, festival, goldsilver, tricolor, jewel, pastel, warm or cool"),
    }

    # ------------------------------------------------------------------ setup
    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        bd = self.opt("backdrop")
        if bd not in ("lake", "city"):
            bd = rng.choice(("lake", "city"))
        self.backdrop = bd
        pal = self.opt("palette")
        if pal not in SHOW_PALETTES:
            pal = rng.choice(list(SHOW_PALETTES) + ["festival", "random"])
        if pal == "random":
            base = rng.random()
            self.pal = [hsv(base + k * rng.choice((0.12, 0.18, 0.31)), rng.uniform(0.5, 0.85), 1.0) for k in range(5)]
        else:
            self.pal = SHOW_PALETTES[pal]
        self.pal_name = pal
        # the show's genome: which shells this pyrotechnician loves
        wts = [rng.uniform(0.2, 1.0) for _ in TYPES]
        for k in rng.sample(range(len(TYPES)), 2):
            wts[k] *= 2.5                        # two signature shells
        self.weights = wts
        self.inten = clamp(self.opt("intensity"), 0.1, 4.0)
        self.wind = rng.uniform(-1.2, 1.2)
        self.smoke_amt = rng.uniform(0.6, 1.3)
        self.trail_style = rng.choice(("sparks", "sparks", "glow"))

        # ---- layout
        small = h < 16
        if bd == "lake":
            self.hz = int(h * rng.uniform(0.68, 0.76))
        else:
            self.hz = int(h * rng.uniform(0.76, 0.84))
        if small:
            self.hz = int(h * 0.75)
        self.hz = max(3, min(h - 2, self.hz))
        hz = self.hz
        self.sky_units = hz * ASPECT
        self.G = 0.2 * self.sky_units            # gravity in x-cell units / s^2
        self.mk = max(1.0, min(2.6, (hz * 0.8) / max(1, h - hz)))
        self.build_backdrop()
        # stars in the clear sky
        ns = int(w * hz / 40 * self.density)
        self.stars = [(rng.randrange(w), rng.randrange(max(1, int(hz * 0.8))), rng.uniform(0.1, 0.45),
                       rng.uniform(0, TAU), rng.uniform(0.5, 2.0)) for _ in range(ns)]
        self.parts = []
        self.smoke = []
        self.lights = []          # (x, y, col, age, strength, radius)
        self.next_launch = 0.2
        self.act = 0.0
        self.finale_at = rng.uniform(30, 45)
        self.finale_len = rng.uniform(6, 9)
        self.quiet = 0.0
        self.flash = (0.0, 0.0, 0.0)
        # smoke texture
        self.tex = [[rng.random() for _ in range(16)] for _ in range(16)]
        for _ in range(2):
            self.launch(rng.uniform(0.2, 0.8) * w, rng.uniform(0.15, 0.4))

    def build_backdrop(self):
        rng = self.rng
        w, h, hz = self.w, self.h, self.hz
        self.sil = [h] * w            # top row of the silhouette per column
        self.silf = [0.0] * w         # fractional part: > 0.5 means the top cell is half filled
        self.windows = []             # (x, y, color, phase)
        self.edge = []
        self.shore_lights = []
        self.trees_flat = False
        if self.backdrop == "city":
            x = -rng.randint(0, 4)
            maxh = max(3, int(hz * rng.uniform(0.28, 0.42)))
            warm = rng.choice(((255, 200, 120), (255, 220, 160), (200, 220, 255)))
            while x < w:
                bw = rng.randint(3, 9)
                tall = rng.random() < 0.18
                bh = int(maxh * (rng.uniform(0.65, 1.0) if tall else rng.uniform(0.2, 0.6)))
                bh = max(2, bh)
                top = hz - bh
                spire = tall and rng.random() < 0.5
                lit = rng.uniform(0.1, 0.45)
                wc = warm if rng.random() < 0.75 else mix(warm, (180, 210, 255), 0.7)
                for xx in range(max(0, x), min(w, x + bw)):
                    self.sil[xx] = min(self.sil[xx], top)
                    for yy in range(top + 1, hz):
                        if (xx - x) % 2 == 1 and (yy - top) % 2 == 0 and xx < x + bw - 1 and rng.random() < lit:
                            self.windows.append((xx, yy, mix(wc, (255, 255, 255), rng.uniform(0, 0.3)),
                                                 rng.uniform(0, TAU) if rng.random() < 0.08 else -1.0))
                if spire:
                    sx = x + bw // 2
                    sh = rng.randint(2, max(2, maxh // 4))
                    for k in range(sh):
                        if 0 <= sx < w:
                            self.sil[sx] = min(self.sil[sx], top - k - 1)
                    if 0 <= sx < w:
                        self.windows.append((sx, top - sh, (255, 60, 50), -2.0))   # aircraft beacon
                x += bw + (0 if rng.random() < 0.7 else rng.randint(1, 3))
        else:
            seed = rng.randrange(1000)
            hill = max(2.0, hz * rng.uniform(0.1, 0.22))
            trees = rng.random() < 0.6
            self.trees_flat = not trees
            fq = rng.uniform(0.02, 0.05) * max(0.6, 100.0 / max(40, w))
            for x in range(w):
                y = hz - 1 - hill * (0.55 + 0.45 * noise1(x * fq, seed)) * (0.75 + 0.25 * noise1(x * fq * 3.3, seed + 1))
                if trees:
                    y -= 1.3 * max(0.0, noise1(x * 0.6, seed + 2))
                y = min(hz - 1.0, y)
                self.sil[x] = int(y)
                self.silf[x] = y - int(y)
            for _ in range(int(w / 9 * rng.uniform(0.3, 1.0))):
                x = rng.randrange(w)
                self.shore_lights.append((x, hz - 1, rng.choice(((255, 200, 120), (255, 230, 170), (255, 170, 90)))))
        # spectators in the foreground, cut out against the bright water
        self.crowd = []
        if h >= 18 and rng.random() < 0.6:
            x = rng.randint(0, 3)
            gap = rng.uniform(2.2, 4.5)
            while x < w:
                if rng.random() < 0.8:
                    self.crowd.append((x, rng.random() < 0.15))
                x += max(2, int(rng.uniform(gap * 0.6, gap * 1.4)))

    # ------------------------------------------------------------------ show logic
    def pick_type(self):
        return self.rng.choices(TYPES, self.weights)[0]

    def launch(self, x, apex_frac, btype=None, col=None):
        rng = self.rng
        hz = self.hz
        y_t = hz * apex_frac
        g = self.G / ASPECT
        rise = max(2.0, hz - y_t)
        vy = -math.sqrt(2 * g * rise)
        fuse = -vy / g * rng.uniform(0.9, 1.0)
        p = P(x, hz - 0.5, rng.uniform(-1.5, 1.5) + self.wind * 0.6, vy, fuse, (255, 200, 140),
              drag=0.0, grav=1.0, kind=1, bright=0.55, hlen=7 if self.trail_style == "glow" else 3)
        p.btype = btype or self.pick_type()
        p.seed = rng.random()
        p.z = rng.uniform(0.75, 1.15) * (1.0 - 0.35 * (1.0 - apex_frac))   # size by distance
        if col is not None:
            p.col = col
        self.parts.append(p)

    def burst(self, s):
        rng = self.rng
        typ = s.btype
        x, y = s.x, s.y
        R = self.sky_units * rng.uniform(0.25, 0.38) * s.z * (0.7 if self.h < 16 else 1.0)
        pal = self.pal
        c1 = rng.choice(pal)
        c2 = rng.choice(pal) if rng.random() < 0.55 else c1
        room = max(0, int(3000 * min(1.5, self.inten)) - len(self.parts))
        scale_n = min(1.0, room / 160.0) * clamp((self.w * self.h) / 5000.0, 0.45, 1.3)
        G = self.G
        add = self.parts.append
        sphere = self._sphere
        light_col = c1
        if typ in ("peony", "chrysanthemum", "dahlia"):
            n = int(rng.randint(60, 100) * scale_n)
            drag = rng.uniform(1.7, 2.3)
            life = rng.uniform(1.5, 2.3)
            pistil = rng.random() < 0.4
            glit = rng.random() < 0.3
            for k in range(n):
                dx, dy, dz = sphere(rng)
                sp = R * drag * rng.uniform(0.92, 1.05)
                col = c1 if (k % 2 == 0 or c2 is c1) else c2
                fl = 1 if glit else 0
                hl = 3
                if typ == "chrysanthemum":
                    hl, fl = 6, fl | 8
                if typ == "dahlia":
                    sp *= 0.8
                    hl = 4
                p = P(x, y, sp * dx, sp * dy / ASPECT, life * rng.uniform(0.85, 1.1), col, drag, 1.0, 0,
                      0.5 + 0.2 * dz, hl, fl)
                add(p)
            if pistil:
                pc = rng.choice(pal)
                for k in range(int(n * 0.25)):
                    dx, dy, dz = sphere(rng)
                    sp = R * 0.45 * drag
                    add(P(x, y, sp * dx, sp * dy / ASPECT, life * 0.7, pc, drag, 1.0, 0, 0.6))
        elif typ == "willow":
            n = int(rng.randint(55, 85) * scale_n)
            col = rng.choice((GOLD, GOLD, (255, 210, 130), (255, 170, 80))) if rng.random() < 0.8 else c1
            light_col = col
            for k in range(n):
                dx, dy, dz = sphere(rng)
                sp = R * 2.4 * rng.uniform(0.85, 1.05)
                add(P(x, y, sp * dx, sp * dy / ASPECT, rng.uniform(3.2, 4.6), col, 2.4, 0.55, 0, 0.55, 16, 1))
        elif typ == "ring":
            n = int(rng.randint(40, 64) * scale_n)
            a1 = rng.uniform(0, TAU)
            tilt = rng.uniform(0.15, 1.2)
            rings = 2 if rng.random() < 0.35 else 1
            drag = 1.9
            for rr in range(rings):
                col = c1 if rr == 0 else c2
                tl = tilt if rr == 0 else -tilt * rng.uniform(0.5, 1.2)
                for k in range(n):
                    a = k / n * TAU
                    ux, uy = math.cos(a), math.sin(a) * math.cos(tl)
                    cx_, cy_ = ux * math.cos(a1) - uy * math.sin(a1), ux * math.sin(a1) + uy * math.cos(a1)
                    sp = R * drag * (1.0 if rr == 0 else 0.7)
                    add(P(x, y, sp * cx_, sp * cy_ / ASPECT, rng.uniform(1.6, 2.1), col, drag, 0.8, 0, 0.7, 2))
            for k in range(int(n * 0.4)):         # small core
                dx, dy, dz = sphere(rng)
                sp = R * 0.35 * drag
                add(P(x, y, sp * dx, sp * dy / ASPECT, 1.2, c2, drag, 1.0, 0, 0.6))
        elif typ == "palm":
            n = rng.randint(6, 10)
            col = c1 if rng.random() < 0.5 else GOLD
            light_col = col
            a0 = rng.uniform(0, TAU)
            for k in range(n):
                a = a0 + k / n * TAU + rng.uniform(-0.1, 0.1)
                sp = R * 1.25 * rng.uniform(0.9, 1.05)
                p = P(x, y, sp * math.cos(a), sp * math.sin(a) / ASPECT - 0.2 * R / ASPECT, rng.uniform(2.2, 2.8), col,
                      1.25, 0.85, 0, 1.0, 14, 8)
                add(p)
        elif typ == "crossette":
            n = int(rng.randint(8, 14) * max(0.5, scale_n))
            col = c1
            for k in range(n):
                a = k / n * TAU + rng.uniform(-0.15, 0.15)
                sp = R * 1.6
                p = P(x, y, sp * math.cos(a), sp * math.sin(a) / ASPECT, rng.uniform(0.6, 0.85), col, 1.6, 1.0,
                      3, 1.0, 6, 0)
                p.btype = c2
                add(p)
        elif typ == "strobe":
            n = int(rng.randint(60, 100) * scale_n)
            col = rng.choice((SILVER, WHITE, c1))
            light_col = col
            for k in range(n):
                dx, dy, dz = sphere(rng)
                sp = R * 1.9 * rng.uniform(0.85, 1.05)
                p = P(x, y, sp * dx, sp * dy / ASPECT, rng.uniform(2.2, 3.0), col, 2.2, 0.5, 0, 0.75, 2, 2)
                p.seed = rng.random()
                add(p)
        else:  # crackle: gold stars that pop into a cloud of white crackles
            n = int(rng.randint(40, 65) * scale_n)
            col = rng.choice((GOLD, (255, 220, 160), c1))
            light_col = col
            for k in range(n):
                dx, dy, dz = sphere(rng)
                sp = R * 1.9 * rng.uniform(0.6, 1.05)
                add(P(x, y, sp * dx, sp * dy / ASPECT, rng.uniform(0.7, 1.1), col, 1.9, 1.0, 0, 0.6, 3, 4))
        # the burst lights the sky, smoke and water
        self.lights.append([x, y, light_col, 0.0, 1.0 * s.z, R])
        # and leaves a smoke puff behind
        if self.smoke_amt > 0 and len(self.smoke) < 26:
            self.smoke.append([x, y + rng.uniform(-1, 1), R * rng.uniform(0.5, 0.8), 0.0, rng.uniform(12, 20),
                               self.smoke_amt * rng.uniform(0.6, 1.0), rng.uniform(0, 16), rng.uniform(0, 16)])

    @staticmethod
    def _sphere(rng):
        z = rng.uniform(-1.0, 1.0)
        a = rng.uniform(0, TAU)
        r = math.sqrt(1 - z * z)
        return r * math.cos(a), r * math.sin(a), z

    def director(self, dt):
        rng = self.rng
        self.act += dt
        finale = bool(self.opt("finale"))
        in_finale = finale and self.finale_at <= self.act < self.finale_at + self.finale_len
        if finale and self.act >= self.finale_at + self.finale_len:
            self.act = 0.0                                      # a new act begins after a pause
            self.quiet = rng.uniform(2.5, 4.0)
            self.finale_at = rng.uniform(35, 60)
            self.finale_len = rng.uniform(6, 9)
            self.weights = [wv * rng.uniform(0.6, 1.6) for wv in self.weights]   # the mix evolves
        if self.quiet > 0:
            self.quiet -= dt
            return
        self.next_launch -= dt
        if self.next_launch > 0:
            return
        w = self.w
        rate = 1.0 * self.inten * (4.0 if in_finale else 1.0)
        self.next_launch = rng.expovariate(rate) + 0.15
        if in_finale or rng.random() < 0.22:
            # a salvo: matching shells fanned across the sky
            k = rng.randint(2, 5 if in_finale else 4)
            typ = rng.choice(("peony", "chrysanthemum", "strobe", "willow", "crackle", "dahlia")) if in_finale \
                else self.pick_type()
            col = (255, 200, 140)
            mid = rng.uniform(0.3, 0.7) * w
            spread = rng.uniform(0.12, 0.25) * w
            apex = rng.uniform(0.15, 0.4)
            for j in range(k):
                f = (j - (k - 1) / 2) / max(1, k - 1)
                self.launch(clamp(mid + f * spread * 2, 2, w - 3), apex + rng.uniform(-0.04, 0.04), typ, col)
            self.next_launch += 0.4
        else:
            self.launch(rng.uniform(0.1, 0.9) * w, rng.uniform(0.1, 0.5))

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        if dt > 0.1:                        # big steps (tests, warmup): integrate in slices
            n = int(dt / 0.05) + 1
            for _ in range(n):
                self.step(dt / n)
        else:
            self.step(dt)

    def step(self, dt):
        rng = self.rng
        self.director(dt)
        G = self.G / ASPECT
        w, hz = self.w, self.hz
        alive = []
        new = []
        wind = self.wind
        for p in self.parts:
            p.age += dt
            if p.hist is not None:
                p.htime += dt
                if p.htime > 0.05:
                    p.htime = 0.0
                    p.hist.append((p.x, p.y))
                    if len(p.hist) > p.hlen:
                        del p.hist[0]
            if p.age >= p.life:
                if p.kind == 1:
                    self.burst(p)
                elif p.kind == 3:            # crossette splits into a cross
                    a0 = math.atan2(p.vy * ASPECT, p.vx)
                    sp = math.hypot(p.vx, p.vy * ASPECT) * 0.5 + self.sky_units * 0.12
                    for k in range(4):
                        a = a0 + math.pi / 4 + k * math.pi / 2
                        new.append(P(p.x, p.y, sp * math.cos(a), sp * math.sin(a) / ASPECT, rng.uniform(0.7, 1.0),
                                     p.btype or p.col, 1.8, 1.0, 0, 1.0, 5, 0))
                    new.append(P(p.x, p.y, 0, 0, 0.12, WHITE, 0, 0, 4, 1.0))
                elif p.flags & 4:            # crackle
                    for k in range(rng.randint(1, 3)):
                        new.append(P(p.x + rng.uniform(-1.2, 1.2), p.y + rng.uniform(-0.6, 0.6), 0, 0,
                                     rng.uniform(0.06, 0.16), rng.choice((WHITE, (255, 240, 200))), 0, 0, 4, 1.0))
                if p.hist is not None and p.hist and p.kind != 1:
                    # let the trail fade out on its own
                    p.kind = 5
                    p.life = p.age + 0.35
                    p.hist = p.hist[-6:]
                    p.bright *= 0.6
                    alive.append(p)
                continue
            if p.kind == 5:
                if p.age >= p.life:
                    continue
                alive.append(p)
                continue
            k = math.exp(-p.drag * dt) if p.drag else 1.0
            p.vx = p.vx * k + wind * 0.25 * dt
            p.vy = p.vy * k + G * p.grav * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.kind == 1:                   # rising shell sheds sparks
                if self.trail_style == "sparks" and rng.random() < dt * 40:
                    new.append(P(p.x + rng.uniform(-0.3, 0.3), p.y + 0.3, rng.uniform(-1.5, 1.5),
                                 rng.uniform(0.0, 1.5), rng.uniform(0.2, 0.45), (255, 170, 80), 2.5, 0.6, 2, 0.4))
            elif p.flags & 8 and rng.random() < dt * 14:
                new.append(P(p.x, p.y, p.vx * 0.1 + rng.uniform(-0.8, 0.8), p.vy * 0.1 + rng.uniform(0, 0.6),
                             rng.uniform(0.3, 0.7), mix(p.col, GOLD, 0.6), 2.0, 0.7, 2, 0.5))
            if p.y > hz + 0.5 and p.kind != 1:
                continue
            alive.append(p)
        if len(alive) + len(new) > 4200:
            new = new[:max(0, 4200 - len(alive))]
        self.parts = alive + new
        for L in self.lights:
            L[3] += dt
        self.lights = [L for L in self.lights if L[3] < 4.0]
        for s in self.smoke:
            s[3] += dt
            s[0] += (wind * 0.8 + 0.3) * dt
            s[1] -= 0.08 * dt
            s[2] += 0.25 * dt
        self.smoke = [s for s in self.smoke if s[3] < s[4] and -s[2] * 2 < s[0] < w + s[2] * 2]

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, hz = self.w, self.h, self.hz
        if (cv.w, cv.h) != (w, h):
            return
        t = self.t
        n = w * hz
        R = [0.0] * n
        Gc = [0.0] * n
        B = [0.0] * n
        exp = math.exp
        # ---- burst light: soft halos (sky glow) + global flash level
        fr = fg = fb = 0.0
        for x0, y0, col, age, st, rad in self.lights:
            f = st * (exp(-age * 3.0) * 0.9 + exp(-age * 0.7) * 0.12)
            fr += col[0] * f
            fg += col[1] * f
            fb += col[2] * f
            if f < 0.03:
                continue
            hr = rad * 1.35
            hy = hr / ASPECT
            ix0, ix1 = max(0, int(x0 - hr)), min(w, int(x0 + hr) + 1)
            iy0, iy1 = max(0, int(y0 - hy)), min(hz, int(y0 + hy) + 1)
            inv = 1.0 / (hr * hr * 0.35)
            k0 = f * 0.45
            cr, cg, cb = col[0] * k0, col[1] * k0, col[2] * k0
            for yy in range(iy0, iy1):
                dy = (yy - y0) * ASPECT
                dy2 = dy * dy
                row = yy * w
                for xx in range(ix0, ix1):
                    dx = xx - x0
                    q = (dx * dx + dy2) * inv
                    if q < 3.0:
                        a = 1.0 / (1.0 + q * q * 3.0) - 0.04
                        if a > 0:
                            i = row + xx
                            R[i] += cr * a
                            Gc[i] += cg * a
                            B[i] += cb * a
        self.flash = (fr, fg, fb)
        # ---- smoke, lit by recent bursts
        tex = self.tex
        for sx, sy, rad, age, life, dens, ox, oy in self.smoke:
            fade = min(1.0, age / 0.8) * (1.0 - age / life) * dens
            if fade <= 0.02:
                continue
            lr, lg, lb = 18.0, 20.0, 34.0
            for x0, y0, col, la, st, lrad in self.lights:
                d2 = ((x0 - sx) ** 2 + ((y0 - sy) * ASPECT) ** 2) / (lrad * lrad * 4)
                f = st * (exp(-la * 2.0) * 1.2 + exp(-la * 0.6) * 0.25) / (1.0 + d2)
                lr += col[0] * f
                lg += col[1] * f
                lb += col[2] * f
            ry = rad / ASPECT
            ix0, ix1 = max(0, int(sx - rad)), min(w, int(sx + rad) + 1)
            iy0, iy1 = max(0, int(sy - ry)), min(hz, int(sy + ry) + 1)
            inv = 1.0 / (rad * rad)
            k0 = fade * 0.5
            for yy in range(iy0, iy1):
                dy = (yy - sy) * ASPECT
                row = yy * w
                ty = int(yy * 0.5 + oy + age * 0.3)
                for xx in range(ix0, ix1):
                    dx = xx - sx
                    q = (dx * dx + dy * dy) * inv
                    if q >= 1.0:
                        continue
                    nz = tex[ty & 15][int(xx * 0.3 + ox - age * 0.4) & 15]
                    a = (1.0 - q) * (nz - 0.3) * k0
                    if a > 0:
                        i = row + xx
                        R[i] += lr * a
                        Gc[i] += lg * a
                        B[i] += lb * a
        # ---- particles
        slope = {}
        head = {}
        for p in self.parts:
            kind = p.kind
            ph = p.age / p.life if p.life > 0 else 1.0
            if kind == 1:
                v = p.bright
                col = (255, 220, 170)
            elif kind == 2:
                v = p.bright * (1.0 - ph)
                col = mix((255, 230, 160), p.col, ph)
            elif kind == 4:
                v = 1.0 - ph * 0.5
                col = p.col
            elif kind == 5:
                v = 0.0
                col = p.col
            else:
                if ph < 0.06:
                    col = mix(WHITE, p.col, ph / 0.06)
                elif ph < 0.6:
                    col = p.col
                else:
                    col = mix(p.col, (p.col[0] * 0.8 + 50, p.col[1] * 0.35, p.col[2] * 0.2), (ph - 0.6) / 0.4)
                v = p.bright * (1.0 - ph ** 2.2)
                if p.flags & 1 and ph > 0.45:          # glitter: random twinkles late in life
                    hsh = (int(t * 24) * 2654435761 + id(p)) & 0xFFFF
                    v *= 1.4 if hsh < 18000 else 0.25
                if p.flags & 2:                         # strobe: hard on/off flashes
                    on = math.sin(t * 22.0 + p.seed * 40.0) > 0.55 or ph < 0.15
                    v = (1.1 if on else 0.0) * (1.0 - ph * 0.6)
                    col = WHITE if on else col
            hist = p.hist
            if hist:
                # trail: a fading line back through the recent positions
                m = len(hist)
                lx, ly = p.x, p.y
                tv = (v if kind != 5 else p.bright * (1.0 - (p.age - p.life + 0.35) / 0.35)) * 0.75
                if kind == 1:
                    tv *= 0.45
                tcol = mix(col, GOLD if kind != 3 else col, 0.35)
                for j in range(m - 1, -1, -1):
                    hx, hy = hist[j]
                    f = (j + 1) / (m + 1)
                    seg = tv * f
                    if seg < 0.03:
                        break
                    ddx, ddy = lx - hx, (ly - hy) * ASPECT
                    adx, ady = abs(ddx), abs(ddy)
                    if adx > ady * 2.4:
                        gl = "-"
                    elif ady > adx * 2.4:
                        gl = "|" if kind != 1 else ":"
                    else:
                        gl = "\\" if (ddx > 0) == (ddy > 0) else "/"
                    steps = int(max(abs(hx - lx), abs(hy - ly))) + 1
                    for s in range(steps):
                        u = s / steps
                        xx = int(lx + (hx - lx) * u)
                        yy = int(ly + (hy - ly) * u)
                        if 0 <= xx < w and 0 <= yy < hz:
                            i = yy * w + xx
                            R[i] += tcol[0] * seg
                            Gc[i] += tcol[1] * seg
                            B[i] += tcol[2] * seg
                            slope[i] = gl
                    lx, ly = hx, hy
            if v <= 0.02:
                continue
            xx, yy = int(p.x), int(p.y)
            if 0 <= xx < w and 0 <= yy < hz:
                i = yy * w + xx
                head[i] = 1
                R[i] += col[0] * v
                Gc[i] += col[1] * v
                B[i] += col[2] * v
                if v > 0.35 and kind in (0, 4):        # bright stars bleed into their neighbours
                    k = (v - 0.3) * 0.3
                    for j in (i - 1, i + 1):
                        if 0 <= j < n:
                            R[j] += col[0] * k
                            Gc[j] += col[1] * k
                            B[j] += col[2] * k
        # ---- tone map the sky
        ramp = SPARK if cv.ramp == RAMPS["ascii"] else cv.ramp
        rn = len(ramp) - 1
        ch, fgc, lv = cv.ch, cv.fg, cv.lv
        skyv = [0.0] * n
        skyc = [None] * n
        for i in range(n):
            r, g, b = R[i], Gc[i], B[i]
            m = r if r > g else g
            if b > m:
                m = b
            if m < 5.0:
                continue
            L = m / 255.0
            v = 1.0 - exp(-L * 1.15)
            k = 255.0 / m
            cr, cg, cb = r * k, g * k, b * k
            if L > 1.4:
                wk = min(0.8, (L - 1.4) * 0.35)
                cr += (255 - cr) * wk
                cg += (255 - cg) * wk
                cb += (255 - cb) * wk
            skyv[i] = v
            skyc[i] = (cr, cg, cb)
            gi = int(v * rn + 0.5)
            if gi > 0:
                kk = 0.25 + 0.75 * v
                gl = slope.get(i)
                ch[i] = gl if (gl is not None and i not in head and v > 0.12) else ramp[gi]
                fgc[i] = _q(cr * kk, cg * kk, cb * kk)
                lv[i] = v
        # stars behind it all (hidden by smoke and light)
        for sx, sy, b, ph, rate in self.stars:
            i = sy * w + sx
            if lv[i] > 0.05 or sy >= self.sil[sx]:
                continue
            v = b * (0.6 + 0.4 * math.sin(t * rate + ph))
            ch[i] = "." if v < 0.3 else "·" if v < 0.4 else "+"
            fgc[i] = _q(150 * v + 30, 160 * v + 30, 200 * v + 40)
            lv[i] = v
        self.draw_backdrop(cv, skyv, skyc, R, Gc, B)

    def draw_backdrop(self, cv, skyv, skyc, R, Gc, B):
        w, h, hz, t = self.w, self.h, self.hz, self.t
        ch, fgc, lv = cv.ch, cv.fg, cv.lv
        fr, fg, fb = self.flash
        fl = min(1.0, max(fr, fg, fb) / 255.0)
        tint = (fr / (max(fr, fg, fb) + 1e-6) * 255, fg / (max(fr, fg, fb) + 1e-6) * 255,
                fb / (max(fr, fg, fb) + 1e-6) * 255) if fl > 0.01 else (0, 0, 0)
        # ---- water: shimmering, compressed reflections of the sky
        wramp = WATER
        wn = len(wramp) - 1
        depth = max(1, h - hz)
        mk = self.mk
        sin = math.sin
        exp = math.exp
        # horizontally blurred sky light: fireworks smear into soft glows on the water
        rows = {}
        rad = 2
        win = 1.0 / (2 * rad + 1)

        def blurred(ym):
            r = rows.get(ym)
            if r is None:
                base = ym * w
                pr, pg, pb = [0.0], [0.0], [0.0]
                for x in range(w):
                    pr.append(pr[-1] + R[base + x])
                    pg.append(pg[-1] + Gc[base + x])
                    pb.append(pb[-1] + B[base + x])
                br_, bg_, bb_ = [], [], []
                for x in range(w):
                    a, b = max(0, x - rad), min(w, x + rad + 1)
                    br_.append((pr[b] - pr[a]) * win)
                    bg_.append((pg[b] - pg[a]) * win)
                    bb_.append((pb[b] - pb[a]) * win)
                r = (br_, bg_, bb_)
                rows[ym] = r
            return r

        for y in range(hz, h):
            d = y - hz
            fade = 1.25 - 0.55 * d / depth
            wob = sin(y * 1.9 + t * 1.3) * (0.6 + d * 0.12) + noise1(y * 0.7 + t * 0.4, 5) * (0.5 + d * 0.15)
            row = y * w
            ym0 = int(hz - 1 - d * mk)
            if ym0 < 0:
                ym0 = 0
            ym1 = max(0, ym0 - 1)
            r0, g0, b0 = blurred(ym0)
            r1, g1, b1 = blurred(ym1)
            for x in range(w):
                sx = int(x + wob + 0.6 * sin(x * 0.21 + y * 1.3 + t * 1.6))
                i = row + x
                if 0 <= sx < w:
                    r, g, b = r0[sx], g0[sx], b0[sx]
                    if r1[sx] + g1[sx] + b1[sx] > r + g + b:
                        r, g, b = r1[sx], g1[sx], b1[sx]
                    m = r if r > g else g
                    if b > m:
                        m = b
                    if m > 6.0:
                        br = 0.65 + 0.5 * sin(x * 0.33 + y * 2.3 - t * 1.7) * sin(x * 0.07 - t * 0.5 + y * 0.9)
                        v = (1.0 - exp(-m / 255.0 * 3.0)) * fade * br
                        if v > 1.0:
                            v = 1.0
                        gi = int(v * wn + 0.5)
                        if gi > 0:
                            k = (0.25 + 0.75 * v) * 255.0 / m
                            ch[i] = wramp[gi]
                            fgc[i] = _q(r * k, g * k * 0.97, b * k)
                            lv[i] = v
                            continue
                # dark water texture, lit a little by the flashes
                if (x * 7 + y * 13 + int(t * 2 + x * 0.05)) % 9 == 0:
                    a = 0.08 + 0.35 * fl
                    ch[i] = "-" if (x + y) % 3 else "~"
                    fgc[i] = _q(20 + tint[0] * a * 0.5, 30 + tint[1] * a * 0.5, 55 + tint[2] * a * 0.5)
                    lv[i] = 0.05
        # ---- silhouettes (city or hills), rim-lit by the bursts
        sil = self.sil
        silf = self.silf
        body = (15 + tint[0] * 0.05 * fl, 16 + tint[1] * 0.05 * fl, 26 + tint[2] * 0.05 * fl)
        bq = _q(*body)
        rq = _q(body[0] + 6 + tint[0] * 0.1 * fl, body[1] + 6 + tint[1] * 0.1 * fl, body[2] + 10 + tint[2] * 0.1 * fl)
        for x in range(w):
            top = sil[x]
            for y in range(max(0, top), hz):
                i = y * w + x
                if y == top:
                    ch[i] = "▄" if silf[x] >= 0.5 else "█"
                    fgc[i] = rq
                else:
                    ch[i] = "█"
                    fgc[i] = bq
                lv[i] = 0.3
        if self.backdrop == "lake":
            for x, y, c in self.shore_lights:
                i = y * w + x
                ch[i] = "."
                fgc[i] = _q(*c)
                if y + 1 < h:
                    j = (y + 1) * w + x
                    ch[j] = "'" if (int(t * 3) + x) % 4 else ","
                    fgc[j] = _q(c[0] * 0.5, c[1] * 0.5, c[2] * 0.5)
        for x, y, c, ph in self.windows:
            if not (0 <= x < w and 0 <= y < h):
                continue
            i = y * w + x
            if ph == -2.0:                     # beacon
                if math.sin(t * 3.0) > 0.3:
                    ch[i] = "*"
                    fgc[i] = _q(*c)
                continue
            if ph >= 0 and math.sin(t * 0.3 + ph) > 0.7:
                continue                       # someone switched the light off
            ch[i] = ":" if (x + y) % 2 else "."
            fgc[i] = _q(*c)
            # window reflections on the water
            yr = hz + int((hz - 1 - y) / self.mk) + 1
            if hz <= yr < h and math.sin(x * 0.7 + yr * 1.3 + t * 2.0) > -0.2:
                j = yr * w + x
                if lv[j] < 0.2:
                    ch[j] = "-"
                    fgc[j] = _q(c[0] * 0.4, c[1] * 0.4, c[2] * 0.4)
                    lv[j] = 0.2
        # ---- the crowd: heads and shoulders cut out against the bright water
        if self.crowd:
            dark = (6, 6, 9)
            for x, kid in self.crowd:
                hy = h - (1 if kid else 2)
                for yy, xs in ((hy, ((x, "▄"),)), (hy + 1, ((x - 1, "▄"), (x, "█"), (x + 1, "▄")))):
                    if yy >= h:
                        continue
                    for xx, c in xs:
                        if 0 <= xx < w:
                            i = yy * w + xx
                            ch[i] = c
                            fgc[i] = dark
                            lv[i] = 1.0


def _q(r, g, b):
    return (0 if r < 0 else 252 if r > 252 else int(r) & ~3,
            0 if g < 0 else 252 if g > 252 else int(g) & ~3,
            0 if b < 0 else 252 if b > 252 else int(b) & ~3)
