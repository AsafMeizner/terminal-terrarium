"""A rotating spiral galaxy: logarithmic arms, a golden core, blue star-forming arms and pink nebulae."""
import math

from ..engine import ASPECT, Scene, clamp, mix

LUT_N = 2048
LUT_M = LUT_N - 1
TAU = math.tau

# core, arm glow, inter-arm glow, young stars, old stars, nebula knots
PALETTES = {
    "classic": ((255, 222, 160), (130, 175, 255), (150, 120, 190),
                [(170, 205, 255), (200, 225, 255), (140, 180, 255), (235, 240, 255)],
                [(255, 210, 160), (255, 190, 140), (255, 230, 200), (240, 170, 130)], (255, 90, 175)),
    "sapphire": ((235, 245, 255), (80, 160, 255), (80, 100, 180),
                 [(120, 210, 255), (180, 235, 255), (100, 170, 255), (230, 245, 255)],
                 [(200, 215, 255), (170, 190, 240), (230, 235, 255), (150, 170, 230)], (110, 255, 220)),
    "rose": ((255, 215, 185), (255, 140, 200), (150, 90, 170),
             [(255, 190, 225), (255, 230, 240), (240, 150, 220), (210, 180, 255)],
             [(255, 200, 170), (255, 180, 160), (250, 220, 200), (230, 160, 150)], (190, 120, 255)),
    "aurora": ((255, 245, 200), (100, 245, 200), (70, 130, 170),
               [(140, 255, 220), (200, 255, 240), (110, 220, 255), (230, 255, 245)],
               [(255, 230, 180), (230, 210, 170), (255, 245, 215), (210, 200, 160)], (255, 100, 180)),
    "ember": ((255, 225, 150), (255, 150, 80), (150, 70, 90),
              [(255, 200, 140), (255, 230, 190), (255, 170, 110), (255, 245, 220)],
              [(255, 190, 130), (240, 160, 110), (255, 215, 170), (220, 140, 100)], (255, 70, 120)),
    "violet": ((255, 230, 210), (170, 130, 255), (110, 80, 170),
               [(200, 180, 255), (230, 220, 255), (160, 150, 255), (245, 240, 255)],
               [(255, 210, 190), (240, 190, 200), (255, 230, 220), (220, 170, 190)], (255, 110, 160)),
}
STAR_GLYPHS = ".·.·+*"


def _q(c):
    r, g, b = c
    r = 0 if r < 0 else 252 if r > 252 else int(r) & ~3
    g = 0 if g < 0 else 252 if g > 252 else int(g) & ~3
    b = 0 if b < 0 else 252 if b > 252 else int(b) & ~3
    return (r, g, b)


class Galaxy(Scene):
    name = "galaxy"
    title = "Spiral Galaxy"
    blurb = "a rotating spiral galaxy with a golden core, blue arms and pink nebulae"
    tags = ("space", "calm", "science")
    options = {
        "arms": (0, "number of spiral arms, 1-6 (0 = random 2-5)"),
        "tilt": (-1.0, "viewing tilt in degrees, 0 = face-on (-1 = random)"),
        "pitch": (0.0, "arm pitch in degrees, small = tightly wound (0 = random)"),
        "bar": ("random", "central bar for two-armed galaxies: on, off or random"),
        "spin": ("random", "rotation direction: cw, ccw or random"),
        "palette": ("random", "classic, sapphire, rose, aurora, ember, violet or random"),
        "nebulae": (-1.0, "amount of nebula knots (-1 = random)"),
        "stars": (1.0, "amount of stars"),
    }

    def _choose_style(self):
        """Pick this galaxy's look once; explicit -o options win over the dice."""
        rng = self.rng
        st = {}
        arms = self.opt("arms")
        st["m"] = max(1, min(6, arms)) if arms > 0 else rng.choice((2, 2, 2, 3, 3, 4, 5))
        tilt = self.opt("tilt")
        st["tilt"] = tilt if tilt >= 0 else rng.choice((rng.uniform(15, 45), rng.uniform(45, 70)))
        pitch = self.opt("pitch")
        st["pitch"] = clamp(pitch, 5, 60) if pitch > 0 else rng.uniform(14, 30)
        bar = str(self.opt("bar")).lower()
        if bar in ("on", "true", "yes", "1"):
            st["bar"] = True
        elif bar in ("off", "false", "no", "0"):
            st["bar"] = False
        else:
            st["bar"] = rng.random() < 0.45
        st["bar"] = st["bar"] and st["m"] == 2
        spin = str(self.opt("spin")).lower()
        st["mirror"] = -1 if spin == "cw" else 1 if spin == "ccw" else rng.choice((-1, 1))
        pal = self.opt("palette")
        if pal not in PALETTES:
            pal = rng.choice(("classic", "classic", "sapphire", "rose", "aurora", "ember", "violet"))
        st["palette"] = pal
        neb = self.opt("nebulae")
        st["nebulae"] = neb if neb >= 0 else rng.choice((0.3, 0.7, 1.0, 1.5, 2.2))
        st["core"] = rng.uniform(0.7, 1.5)
        st["pa"] = rng.uniform(-0.55, 0.55)
        st["bar_len"] = rng.uniform(0.18, 0.3)
        self.style = st

    def setup(self):
        w, h = self.w, self.h
        rng = self.rng
        if not hasattr(self, "style"):
            self._choose_style()
        st = self.style
        (self.CORE, self.ARM, self.INTER, self.YOUNG, self.OLD, self.NEBULA) = PALETTES[st["palette"]]
        self.m = st["m"]
        tilt = math.radians(clamp(st["tilt"], 0.0, 85.0))
        self.ct = max(0.08, math.cos(tilt))
        self.pa = st["pa"]                                # position angle of the major axis
        self.bar = st["bar"]
        self.bl = st["bar_len"] if self.bar else 0.0
        self.cx, self.cy = w / 2.0, h / 2.0
        # galaxy radius in x cells, limited by the width and by the tilted height
        sp, cp = math.sin(self.pa), math.cos(self.pa)
        fx = math.sqrt(cp * cp + (self.ct * sp) ** 2)          # half-width per unit radius
        fy = math.sqrt(sp * sp + (self.ct * cp) ** 2)          # half-height per unit radius
        self.Rg = max(6.0, min(w * 0.40 / fx, h * 0.44 * ASPECT / fy))
        self.k = 1.0 / math.tan(math.radians(st["pitch"]))   # spiral winding
        self.omega_p = 0.035                              # pattern speed (rad/s)
        cpa, spa = math.cos(self.pa), math.sin(self.pa)
        # disk (X, Y) -> screen: x = cx + Rg*(X cpa - Y ct spa), y = cy + Rg/ASPECT*(X spa + Y ct cpa)
        mir = st["mirror"]                               # mirroring flips the sense of rotation
        self.mx = (self.Rg * cpa, -self.Rg * self.ct * spa * mir)
        self.my = (self.Rg * spa / ASPECT, self.Rg * self.ct * cpa / ASPECT * mir)

        # arm profile lookups over the spiral phase (crest at 0)
        self.arm_lut = []
        self.dust_lut = []
        for i in range(LUT_N):
            p = (i / LUT_N) * TAU
            if p > math.pi:
                p -= TAU
            self.arm_lut.append(math.exp(-(p / 0.75) ** 2))
            self.dust_lut.append(math.exp(-((p + 0.85) / 0.28) ** 2))   # dark lane on the inner edge

        # per-cell disk coordinates for the diffuse glow
        self.cells = []
        det = self.mx[0] * self.my[1] - self.mx[1] * self.my[0]
        m, k = self.m, self.k
        sc = LUT_N / TAU
        for y in range(h):
            for x in range(w):
                dx, dy = x + 0.5 - self.cx, y + 0.5 - self.cy
                X = (dx * self.my[1] - dy * self.mx[1]) / det
                Y = (-dx * self.my[0] + dy * self.mx[0]) / det
                r = math.sqrt(X * X + Y * Y)
                if r > 1.25:
                    continue
                phi = math.atan2(Y, X)
                lr = math.log(max(r, 0.02))
                a = int((m * phi + m * k * lr) * sc) & LUT_M
                cs = st["core"]
                bulge = 1.6 * math.exp(-r / (0.05 * cs)) + 0.6 * math.exp(-r / (0.15 * cs))
                inner = clamp((r - self.bl * 0.8) / 0.1) if self.bar else clamp(r / 0.1)
                disk = math.exp(-r / 0.5) * clamp((1.2 - r) / 0.45) * inner
                self.cells.append((y * w + x, a, bulge, disk, r, X, Y))

        # stars
        amount = max(0.05, self.opt("stars")) * self.density
        n = int(clamp(self.Rg * self.Rg * self.ct * 1.3, 500, 6000) * amount)
        self.stars = []          # [r, phi, omega, kind, color, base, age, life, lnterm]
        for _ in range(n):
            self.stars.append(self._new_star(young=rng.random() < 0.55, fresh=False))
        self.knots = []
        for _ in range(int(round(4 * self.m * min(1.5, amount) * st["nebulae"]))):
            r = rng.uniform(max(0.22, self.bl + 0.05), 0.85)
            j = rng.randrange(self.m)
            self.knots.append((r, j, rng.uniform(-0.12, 0.12), rng.uniform(0.6, 1.3), rng.uniform(0, TAU)))
        self.bg = [(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0, TAU), rng.uniform(0.6, 2.2),
                    rng.choice(((255, 255, 255), (190, 210, 255), (255, 220, 190))), rng.random())
                   for _ in range(int(w * h / 55 * self.density))]

    def _omega(self, r):
        return 0.075 / (r + 0.18) + 0.01

    def _new_star(self, young, fresh=True):
        rng = self.rng
        m, k = self.m, self.k
        if young:
            r = min(1.05, max(0.1, self.bl * 0.9) + rng.expovariate(1 / 0.28))
            j = rng.randrange(m)
            phi = TAU * j / m - k * math.log(r) + self.omega_p * self.t + rng.gauss(0, 0.12)
            life = rng.uniform(5, 18)
            age = 0.0 if fresh else rng.uniform(0, life)
            color = rng.choice(self.YOUNG)
            base = rng.uniform(0.25, 0.75)
            kind = 1
        else:
            if rng.random() < 0.35:
                r = abs(rng.gauss(0, 0.12))                # bulge
            else:
                r = min(1.15, rng.expovariate(1 / 0.32))
            phi = rng.uniform(0, TAU)
            life = age = 0.0
            color = rng.choice(self.OLD)
            base = rng.uniform(0.08, 0.3)
            kind = 0
        r = max(0.01, r)
        lnterm = m * k * math.log(r)
        return [r, phi, self._omega(r), kind, color, base, age, life, lnterm]

    def update(self, dt):
        super().update(dt)
        stars = self.stars
        for idx, s in enumerate(stars):
            s[1] += s[2] * dt
            if s[3]:
                s[6] += dt
                if s[6] > s[7]:
                    stars[idx] = self._new_star(True)

    def draw(self, cv):
        W, H = cv.w, cv.h
        t = self.t
        # background stars twinkle
        for x, y, ph, sp, col, b in self.bg:
            tw = 0.5 + 0.5 * math.sin(t * sp + ph)
            v = (0.2 + 0.8 * b * b) * (0.3 + 0.7 * tw * tw)
            gl = STAR_GLYPHS[min(len(STAR_GLYPHS) - 1, int(v * len(STAR_GLYPHS)))]
            k = 0.25 + 0.6 * v
            cv.put(x, y, gl, (col[0] * k, col[1] * k, col[2] * k), level=v * 0.3)

        n = W * H
        L = [0.0] * n
        R = [0.0] * n
        G = [0.0] * n
        B = [0.0] * n
        arm_lut, dust_lut = self.arm_lut, self.dust_lut
        m = self.m
        sc = LUT_N / TAU
        P = int(m * self.omega_p * t * sc)
        CORE, ARM, INTER, NEBULA = self.CORE, self.ARM, self.INTER, self.NEBULA
        bar = self.bar
        if bar:
            # the bar turns with the pattern; the arms start from its ends
            ba = self.omega_p * t - self.k * math.log(self.bl)
            bc, bs = math.cos(ba), math.sin(ba)
            ibl2 = 1.0 / (self.bl * self.bl)
            ibw2 = 1.0 / (self.bl * 0.28) ** 2
            blim = self.bl * 1.3
        # diffuse light: bulge + arms - dust
        for i, a, bulge, disk, r, X, Y in self.cells:
            if i >= n:
                continue
            ph = (a - P) & LUT_M
            arm = arm_lut[ph]
            dust = dust_lut[ph] * clamp((r - 0.1) / 0.2)
            d = disk * (0.05 + 1.7 * arm * arm) * (1 - 0.85 * dust)
            bb = bulge * (1 - 0.25 * dust)
            if bar and r < blim:
                u = X * bc + Y * bs
                vv = Y * bc - X * bs
                bb += 0.75 * math.exp(-(u * u * ibl2 + vv * vv * ibw2) * 1.5)
            tot = d + bb
            if tot < 0.01:
                continue
            L[i] += tot
            ca = mix(INTER, ARM, arm)
            R[i] += bb * CORE[0] + d * ca[0]
            G[i] += bb * CORE[1] + d * ca[1]
            B[i] += bb * CORE[2] + d * ca[2]

        # stars
        cx, cy = self.cx, self.cy
        mx0, mx1 = self.mx
        my0, my1 = self.my
        cos, sin = math.cos, math.sin
        for s in self.stars:
            r, phi = s[0], s[1]
            c, sn = cos(phi), sin(phi)
            X, Y = r * c, r * sn
            x = int(cx + X * mx0 + Y * mx1)
            y = int(cy + X * my0 + Y * my1)
            if not (0 <= x < W and 0 <= y < H):
                continue
            ph = (int((m * phi + s[8]) * sc) - P) & LUT_M
            arm = arm_lut[ph]
            dust = dust_lut[ph]
            if s[3]:
                age, life = s[6], s[7]
                fade = min(1.0, age * 2.0) * (1 - age / life) ** 1.3
                b = s[5] * fade * (0.35 + 0.65 * arm)
            else:
                b = s[5] * (0.6 + 0.4 * arm)
            b *= 1 - 0.75 * dust
            if b <= 0.01:
                continue
            col = s[4]
            i = y * W + x
            L[i] += b
            R[i] += b * col[0]
            G[i] += b * col[1]
            B[i] += b * col[2]

        # pink nebula knots ride the arm crests
        k = self.k
        for r, j, off, size, ph0 in self.knots:
            phi = TAU * j / m - k * math.log(r) + self.omega_p * t + off
            X, Y = r * cos(phi), r * sin(phi)
            kx = cx + X * mx0 + Y * mx1
            ky = cy + X * my0 + Y * my1
            pulse = 0.75 + 0.25 * sin(t * 0.7 + ph0)
            rad = max(1.2, self.Rg * 0.035 * size)
            for yy in range(int(ky - rad / ASPECT) - 1, int(ky + rad / ASPECT) + 2):
                if not 0 <= yy < H:
                    continue
                for xx in range(int(kx - rad) - 1, int(kx + rad) + 2):
                    if not 0 <= xx < W:
                        continue
                    d2 = ((xx + 0.5 - kx) ** 2 + ((yy + 0.5 - ky) * ASPECT) ** 2) / (rad * rad)
                    if d2 > 2.5:
                        continue
                    b = 0.9 * pulse * math.exp(-d2 * 1.6)
                    i = yy * W + xx
                    L[i] += b
                    R[i] += b * NEBULA[0]
                    G[i] += b * NEBULA[1]
                    B[i] += b * NEBULA[2]

        # tone map into glyphs
        ramp = cv.ramp
        nr = len(ramp) - 1
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        exp = math.exp
        for i in range(n):
            l = L[i]
            if l < 0.02:
                continue
            v = 1 - exp(-l * 1.7)
            if v <= lv[i]:
                continue
            gi = int(v * nr + 0.5)
            if gi <= 0:
                continue
            inv = 1.0 / l
            # brightest cells bloom toward white
            wht = clamp((l - 1.2) * 0.35)
            kk = (0.3 + 0.7 * v)
            r_ = R[i] * inv
            g_ = G[i] * inv
            b_ = B[i] * inv
            r_ += (255 - r_) * wht
            g_ += (255 - g_) * wht
            b_ += (255 - b_) * wht
            ch[i] = ramp[gi]
            fg[i] = _q((r_ * kk, g_ * kk, b_ * kk))
            lv[i] = v
