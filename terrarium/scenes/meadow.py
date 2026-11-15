"""A wind-swept meadow at golden hour: grass waves, wildflowers bob, butterflies flutter."""
import math

from ..engine import ASPECT, Scene, clamp, fbm, gradient, mix, noise1, scale
from .bonsai import TAU
from .sakura import _hash, disc_glyph, edge_glyph

SKY = [(10, 14, 40), (30, 40, 90), (90, 80, 140), (220, 130, 110), (255, 190, 120)]
GRASS_FAR = [(20, 40, 50), (50, 80, 70)]
GRASS_NEAR = [(20, 70, 24), (60, 140, 40), (160, 210, 70), (250, 230, 130)]
FLOWERS = [
    ((255, 70, 60), "@"),      # poppy
    ((255, 214, 60), "*"),     # buttercup
    ((190, 120, 255), "&"),    # wild violet
    ((255, 250, 240), "*"),    # daisy
    ((100, 170, 255), "o"),    # cornflower
    ((255, 130, 200), "%"),    # clover
]
# light moods: sky stops, sun stops, cloud tint, far and near grass
MOODS = {
    "golden": {"sky": SKY, "sun": [(255, 250, 225), (255, 215, 140), (255, 160, 90)], "cloud": (70, 70, 120)},
    "rose": {"sky": [(16, 10, 36), (50, 30, 80), (150, 70, 130), (255, 120, 150), (255, 200, 170)],
             "sun": [(255, 240, 230), (255, 180, 170), (240, 110, 120)], "cloud": (90, 60, 110)},
    "morning": {"sky": [(20, 30, 60), (50, 80, 130), (120, 150, 190), (220, 200, 170), (255, 235, 190)],
                "sun": [(255, 255, 240), (255, 240, 190), (255, 210, 140)], "cloud": (110, 120, 150)},
    "blue": {"sky": [(4, 8, 24), (12, 24, 60), (30, 50, 100), (70, 90, 150), (130, 150, 200)],
             "sun": [(240, 245, 255), (200, 215, 245), (140, 160, 220)], "cloud": (50, 60, 100)},
}
GRASSES = {
    "lush": (GRASS_FAR, GRASS_NEAR),
    "dry": ([(40, 36, 40), (90, 80, 60)], [(70, 60, 20), (150, 120, 40), (220, 180, 80), (255, 230, 150)]),
    "teal": ([(14, 36, 50), (40, 80, 90)], [(10, 60, 50), (30, 130, 100), (110, 210, 150), (210, 250, 200)]),
    "spring": ([(24, 44, 40), (60, 100, 70)], [(30, 90, 30), (80, 170, 50), (170, 230, 80), (230, 255, 160)]),
    "autumn": ([(40, 30, 36), (90, 64, 60)], [(80, 40, 16), (170, 90, 30), (230, 150, 60), (255, 210, 130)]),
}

WINGS = [((255, 150, 40), (255, 210, 120)), ((80, 160, 255), (190, 230, 255)),
         ((255, 230, 90), (255, 250, 200)), ((250, 250, 255), (210, 220, 255)), ((255, 110, 170), (255, 200, 230))]


class Meadow(Scene):
    name = "meadow"
    title = "Meadow"
    blurb = "a golden-hour meadow: grass waves in the wind, flowers bob, butterflies flutter"
    tags = ("nature", "plants", "wind", "calm")
    options = {
        "wind": (1.0, "wind strength"),
        "mood": ("random", "golden, rose, morning, blue or random"),
        "grass": ("random", "lush, dry, teal, spring, autumn or random"),
        "flowers": (1.0, "amount of wildflowers"),
        "butterflies": (0, "number of butterflies (0 = based on screen size)"),
        "sky": (True, "draw the sky gradient, sun and clouds"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.seed = rng.randrange(1 << 15)
        mood = self.opt("mood")
        mood = mood if mood in MOODS else rng.choice(list(MOODS))
        grass = self.opt("grass")
        grass = grass if grass in GRASSES else rng.choices(list(GRASSES), (4, 2, 1, 2, 1))[0]
        self.lk = dict(MOODS[mood])
        self.lk["far"], self.lk["near"] = GRASSES[grass]
        # a meadow of 2-5 kinds of wildflower, some much commoner than others
        k = rng.randint(2, min(5, len(FLOWERS)))
        self.flora = rng.sample(FLOWERS, k)
        self.flora_w = [rng.uniform(0.2, 1.0) ** 2 for _ in self.flora]
        self.wings = rng.sample(WINGS, rng.randint(1, len(WINGS)))
        self.wdir = rng.choice((-1, 1))
        hz = rng.uniform(0.44, 0.6)
        ha, hf = rng.uniform(0.02, 0.09), rng.uniform(0.015, 0.045)
        self.horizon = [h * hz + h * ha * noise1(x * hf, self.seed) + h * 0.02 * noise1(x * 0.03, self.seed) + h * 0.02 * noise1(x * 0.1, self.seed + 1)
                        for x in range(w)]
        top = min(self.horizon)
        sr = clamp(h * rng.uniform(0.1, 0.17), 2.5, 9.0)
        sx = w * rng.uniform(0.12, 0.88)
        self.sun = (sx, top - sr / ASPECT - h * 0.05, sr)
        # blades in depth layers: base row from the horizon down past the bottom edge.
        # depth 0 = far (short, hazy, dense), 1 = near (tall, bright, sparse) - gaps give depth.
        blades = []
        fl_amt = max(0.0, self.opt("flowers"))
        bottom = h + 3
        nl = int(clamp(h * 0.3, 5, 16))
        for li in range(nl):
            d = li / max(1, nl - 1)
            gap = 1.5 + 3.2 * d
            x = rng.uniform(0, gap)
            while x < w:
                hy = self.horizon[int(clamp(x, 0, w - 1))]
                y = hy + (bottom - hy) * (d ** 1.35) + rng.uniform(-0.6, 0.6) + 0.6
                height = 1.2 + d * d * h * 0.36 * rng.uniform(0.65, 1.15) + 2.2 * d
                flower = None
                if d > 0.15 and rng.random() < 0.09 * fl_amt * (0.5 + d):
                    flower = rng.choices(self.flora, self.flora_w)[0]
                    height *= rng.uniform(1.0, 1.15)
                blades.append([x, y, height, d, rng.uniform(0, TAU), rng.uniform(0.75, 1.3), flower,
                               rng.gauss(0, 0.4), rng.uniform(-0.18, 0.12)])
                x += gap * rng.uniform(0.6, 1.4)
        blades.sort(key=lambda b: b[1])
        self.blades = blades
        # sky: static dither dots + a pre-baked cloud band that scrolls
        self.sky = []
        self.stars = []
        if self.opt("sky"):
            for y in range(int(top) + 1):
                f = y / max(1.0, top)
                for x in range(w):
                    if y >= self.horizon[x]:
                        continue
                    r = rng.random()
                    if r < 0.03 + 0.2 * f ** 2.5:
                        self.sky.append((x, y, 0.05 + 0.2 * f ** 1.5, gradient(self.lk["sky"], f)))
                    elif f < 0.5 and r > 0.995:
                        self.stars.append((x, y, rng.uniform(0, TAU)))
            cw = w * 2
            self.cloud_w = cw
            self.clouds = []
            for y in range(int(top * 0.15), int(top * 0.85)):
                for x in range(cw):
                    n = fbm(x * 0.035, y * 0.22, 3, self.seed + 7)
                    if n > 0.25:
                        self.clouds.append((x, y, clamp((n - 0.25) * 3.5)))
        n = self.opt("butterflies") or max(1, int(round(4 * self.density * w * h / 4000)))
        self.flies = [self.new_fly() for _ in range(n)]
        self.motes = [[rng.uniform(0, w), rng.uniform(top, h), rng.uniform(0, TAU)] for _ in range(self.count(18))]
        self.gx = [0.0] * (w + 2)

    def new_fly(self):
        rng = self.rng
        h = self.h
        return {"x": rng.uniform(0, self.w), "y": rng.uniform(h * 0.4, h * 0.8), "vx": 0.0, "vy": 0.0,
                "ph": rng.uniform(0, TAU), "rate": rng.uniform(7, 11), "col": rng.choice(self.wings),
                "goal": (rng.uniform(0, self.w), rng.uniform(h * 0.35, h * 0.85)), "rest": 0.0}

    # -- simulation ------------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        rng = self.rng
        t = self.t
        W = max(0.0, self.opt("wind"))
        w, h = self.w, self.h
        # wind per column: a steady lean plus gusts that travel across the field
        s = self.seed
        for x in range(w + 2):
            g = noise1(x * 0.045 - self.wdir * t * (0.5 + 0.5 * W), s + 3) * 0.5 + 0.5
            g2 = noise1(x * 0.12 - self.wdir * t * 1.4 * (0.5 + 0.5 * W), s + 4)
            self.gx[x] = self.wdir * W * (0.3 + 1.3 * clamp((g - 0.42) * 2.4) ** 2 + 0.1 * g2)
        for f in self.flies:
            f["ph"] += dt * f["rate"]
            gx, gy = f["goal"]
            dx, dy = gx - f["x"], (gy - f["y"]) * ASPECT
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 2 or rng.random() < dt * 0.08:
                f["goal"] = (clamp(f["x"] + rng.uniform(-25, 25), 1, w - 2), rng.uniform(h * 0.35, h * 0.85))
            sp = 4.5
            f["vx"] += (dx / max(dist, 0.1) * sp - f["vx"]) * dt * 1.2 + rng.gauss(0, 6) * dt
            f["vy"] += (dy / max(dist, 0.1) * sp / ASPECT - f["vy"]) * dt * 1.2 + rng.gauss(0, 3) * dt
            gust = self.gx[int(clamp(f["x"], 0, w))]
            f["x"] += (f["vx"] + gust * 1.5) * dt
            f["y"] += (f["vy"] + math.sin(f["ph"] * 0.5) * 0.8) * dt
            if f["x"] > w + 2:
                f["x"] = -2.0
            elif f["x"] < -3:
                f["x"] = w + 1.0
            f["y"] = clamp(f["y"], 1, h - 2)
        for m in self.motes:
            m[2] += dt
            m[0] += (self.gx[int(clamp(m[0], 0, w))] * 2 + 0.3 * math.sin(m[2])) * dt
            m[1] += math.sin(m[2] * 0.7) * dt * 0.3
            if m[0] > w or m[0] < 0:
                m[0] %= w
                m[1] = rng.uniform(min(self.horizon), h)

    # -- drawing ---------------------------------------------------------------------
    def draw(self, cv):
        t = self.t
        w, h = self.w, self.h
        put = cv.put
        if self.opt("sky"):
            self.draw_sky(cv)
        # distant hill line
        for x in range(w):
            hy = self.horizon[x]
            ch, iy = edge_glyph(hy, self.horizon[max(0, x - 1)], self.horizon[min(w - 1, x + 1)])
            near_sun = math.exp(-((x - self.sun[0]) / (w * 0.25)) ** 2)
            put(x, iy, ch, mix((50, 70, 80), (255, 170, 110), 0.6 * near_sun))
        self.draw_grass(cv)
        for mx, my, mp in self.motes:
            put(mx, my, "." if math.sin(mp * 2) < 0.6 else "·", self.lk["sun"][1])
        for f in self.flies:
            self.draw_fly(cv, f)

    def draw_sky(self, cv):
        t = self.t
        put = cv.put
        for x, y, lv, col in self.sky:
            put(x, y, ".", scale(col, lv * 2.2))
        for x, y, ph in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * 1.3 + ph)
            put(x, y, "." if tw < 0.7 else "*", scale((230, 230, 255), 0.3 + 0.5 * tw))
        self.draw_clouds(cv)
        sx, sy, sr = self.sun
        R = sr * 3.2
        for y in range(int(sy - R / ASPECT) - 1, int(sy + R / ASPECT) + 2):
            if y < 0 or y >= cv.h:
                continue
            for x in range(int(sx - R) - 1, int(sx + R) + 2):
                if x < 0 or x >= cv.w or y >= self.horizon[x]:
                    continue
                ch, d = disc_glyph(x, y, sx, sy, sr)
                if ch:
                    put(x, y, ch, gradient(self.lk["sun"], min(1.0, d)))
                elif d < 3.2:
                    g = (3.2 - d) / 2.2
                    put(x, y, "·" if g > 0.5 else ".", scale(self.lk["sun"][2], 0.12 + 0.5 * g * g))

    def draw_clouds(self, cv):
        """Clouds lit warm from below near the sun."""
        t = self.t
        put = cv.put
        sx, sy, sr = self.sun
        off = int(t * 0.6)
        cw = self.cloud_w
        W = cv.w
        for x, y, v in self.clouds:
            xi = (x - off) % cw
            if xi >= W or y >= self.horizon[xi] - 1:
                continue
            warm = math.exp(-((xi - sx) / (W * 0.35)) ** 2)
            col = mix(self.lk["cloud"], self.lk["sun"][2], 0.35 + 0.5 * warm * (y / max(1, sy + 1)))
            put(xi, y, "-" if v < 0.5 else "~", scale(col, 0.2 + 0.45 * v))

    def draw_grass(self, cv):
        t = self.t
        put = cv.put
        gx = self.gx
        ng = len(gx)
        H = cv.h
        W = cv.w
        sunx = self.sun[0]
        sin = math.sin
        far_lit = self.lk["sun"][2]
        for bx, by, height, d, ph, stiff, flower, hj, cj in self.blades:
            xi = int(bx)
            g = gx[xi + 1 if 0 <= xi + 1 < ng else -1]
            flutter = 0.18 * sin(t * (2.0 + 2.5 * d) + ph)
            bend = (g + flutter) / stiff + hj
            n = max(1, int(height + 0.5))
            # far blades are hazy blue-green, near blades rich green with golden tips;
            # where a gust presses the grass over, the field brightens (sheen)
            sheen = clamp(abs(g) * 0.6)
            tipc = gradient(self.lk["near"], clamp(0.4 + 0.35 * d + sheen * 0.55 + cj))
            base = mix(self.lk["far"][0], self.lk["near"][0], d)
            if d < 0.35:
                haze = mix(self.lk["far"][1], far_lit, 0.35 * math.exp(-((bx - sunx) / (W * 0.3)) ** 2))
                tipc = mix(haze, tipc, d / 0.35)
            bright = 0.35 + 0.65 * d + 0.15 * sheen
            amp = bend * height * 0.55
            prev = 0.0
            y0 = int(by)
            for k in range(n):
                y = y0 - k
                if y < 0:
                    break
                f = (k + 1) / n
                off = amp * f * (0.35 + 0.65 * f)
                slope = off - prev
                prev = off
                if y >= H:
                    continue
                if slope > 1.4 and n > 3:
                    ch = "_" if f > 0.7 else "-"
                elif slope > 0.4:
                    ch = "/"
                elif slope < -0.4:
                    ch = "\\"
                elif k == n - 1 and n > 2 and not flower:
                    ch = "'"
                else:
                    ch = "|"
                c = 0.15 + 0.85 * f * f
                put(bx + off, y, ch, ((base[0] + (tipc[0] - base[0]) * c) * bright,
                                      (base[1] + (tipc[1] - base[1]) * c) * bright,
                                      (base[2] + (tipc[2] - base[2]) * c) * bright))
            if flower:
                fc, fch = flower
                fy = y0 - n
                fx = bx + amp + 0.3 * sin(t * 3 + ph)  # head rides the tip
                bob = 0.6 + 0.4 * sin(t * 2.2 + ph)
                put(fx, fy, fch, scale(fc, (0.45 + 0.55 * d) * (0.85 + 0.15 * bob)))
                if d > 0.6 and fch == "@":   # near poppies open their petals
                    pc = scale(fc, 0.55 + 0.3 * d)
                    put(fx - 1, fy, "(", pc)
                    put(fx + 1, fy, ")", pc)

    def draw_fly(self, cv, f):
        x, y = f["x"], f["y"]
        wing, edge = f["col"]
        flap = math.sin(f["ph"])
        k = 0.8 + 0.2 * abs(flap)
        if flap > -0.3:
            cv.put(x - 1, y, "}", scale(wing, k))
            cv.put(x + 1, y, "{", scale(wing, k))
            cv.put(x, y, ":", scale(edge, 0.9))
        else:   # wings folded up over the body
            cv.put(x, y, "Y", scale(wing, k))
