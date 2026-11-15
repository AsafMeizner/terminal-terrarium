"""A city skyline time-lapse: a full day and night every cycle, windows lighting up one by one."""
import math

from ..engine import ASPECT, Scene, clamp, gradient, mix, scale

TAU = math.tau

# (sun elevation, sky top, sky middle, horizon)
SKY_KEYS = [
    (-1.0, (2, 3, 12), (4, 6, 20), (10, 14, 34)),
    (-0.3, (4, 6, 22), (10, 14, 40), (30, 30, 70)),
    (-0.12, (12, 16, 50), (60, 40, 100), (200, 90, 110)),
    (0.0, (30, 40, 100), (150, 90, 140), (255, 140, 80)),
    (0.12, (40, 80, 170), (120, 150, 210), (255, 200, 140)),
    (0.35, (40, 110, 210), (90, 160, 235), (175, 215, 250)),
    (1.0, (30, 100, 215), (80, 155, 240), (165, 210, 250)),
]
WARM = [(255, 200, 110), (255, 220, 150), (255, 180, 90), (255, 236, 190)]
COOL = [(170, 220, 255), (200, 230, 255), (150, 200, 255)]
TV = (120, 160, 255)
CLOUD_RAMP = " .:;coO08"


def _hash(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 982451653) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 65535.0


def tnoise(x, y, px, py, seed):
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u = xf * xf * (3 - 2 * xf)
    v = yf * yf * (3 - 2 * yf)
    x0, x1 = xi % px, (xi + 1) % px
    y0, y1 = yi % py, (yi + 1) % py
    a = _hash(x0, y0, seed) + (_hash(x1, y0, seed) - _hash(x0, y0, seed)) * u
    b = _hash(x0, y1, seed) + (_hash(x1, y1, seed) - _hash(x0, y1, seed)) * u
    return a + (b - a) * v


def sky_at(e):
    """Sky colors (top, middle, horizon) for a sun elevation e in -1..1."""
    keys = SKY_KEYS
    if e <= keys[0][0]:
        return keys[0][1:]
    for k in range(len(keys) - 1):
        a, b = keys[k], keys[k + 1]
        if e <= b[0]:
            f = (e - a[0]) / (b[0] - a[0])
            return tuple(mix(a[i], b[i], f) for i in (1, 2, 3))
    return keys[-1][1:]


class Building:
    __slots__ = ("x0", "x1", "top", "layer", "cells", "edges", "wins", "lights", "shade")


class Skyline(Scene):
    name = "skyline"
    title = "Skyline"
    blurb = "a city skyline time-lapse: day to night, windows lighting up, traffic streaming below"
    tags = ("city", "night", "sky", "timelapse")
    options = {
        "cycle": (40.0, "seconds for a full day and night"),
        "density": (1.0, "how packed the skyline is"),
        "start": (-1.0, "hour of day to start at, 0..24 (-1 = random)"),
        "clouds": ("random", "random, cumulus, streaks, scattered or none"),
    }

    # ------------------------------------------------------------------ setup
    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.seed = rng.randrange(1 << 15)
        st = self.opt("start")
        self.tod0 = (st / 24.0) % 1.0 if st >= 0 else rng.uniform(0.6, 0.78)
        self.harbor = rng.random() < 0.4 and h >= 16
        road = 2 if h >= 14 else 1
        water = max(2, int(h * rng.uniform(0.12, 0.18))) if self.harbor else 0
        self.road_y = h - road - water          # first road row
        self.water_y = h - water
        self.gy = self.road_y                     # ground row: buildings stand on it
        # grammar for this city
        dens = max(0.2, self.opt("density"))
        self.g = g = {
            "spire": rng.uniform(0.05, 0.35),
            "antenna": rng.uniform(0.15, 0.5),
            "tower": rng.uniform(0.05, 0.4),
            "setback": rng.uniform(0.2, 0.7),
            "crown": rng.uniform(0.05, 0.35),
            "gap": clamp(rng.uniform(0.05, 0.3) / dens, 0, 0.6),
            "wmin": rng.choice((3, 4, 5)),
            "wmax": rng.choice((8, 10, 13, 16)),
            "hmax": rng.uniform(0.42, 0.66),
            "warm": rng.uniform(0.5, 0.95),
        }
        centers = [rng.uniform(0.2, 0.8) for _ in range(rng.randint(1, 2))]
        spread = rng.uniform(0.15, 0.35)

        def bump(x):
            u = x / max(1, w)
            return max(math.exp(-((u - c) / spread) ** 2) for c in centers)

        self.blds = []
        avail = self.gy - 1
        for layer in (0, 1):
            x = rng.uniform(-3, 0)
            while x < w:
                bw = rng.randint(g["wmin"], g["wmax"]) + (2 if layer == 0 else 0)
                if rng.random() < g["gap"] * (0.5 if layer == 0 else 1.0):
                    x += rng.randint(1, 4)
                    continue
                top = (0.35 + 0.65 * bump(x + bw / 2)) * rng.uniform(0.45, 1.0)
                hgt = avail * g["hmax"] * top * (1.0 if layer == 0 else 0.66) + rng.uniform(2, 4)
                hgt = clamp(hgt, 2, avail - 1)
                self.blds.append(self.make_building(int(x), int(x) + bw, hgt, layer))
                x += bw + (rng.randint(0, 1) if layer == 0 else rng.randint(0, 2))
        # sky mask: cells not covered by any building (or road)
        self.cover = [False] * (w * h)
        for b in self.blds:
            for x, y, *_ in b.cells:
                self.cover[y * w + x] = True
            for x, y, *_ in b.edges:
                self.cover[y * w + x] = True
        self.skyrows = []
        for y in range(self.gy):
            row = [x for x in range(w) if not self.cover[y * w + x]]
            self.skyrows.append(row)
        self.stars = [(rng.randrange(w), rng.randrange(max(1, int(self.gy * 0.7))), rng.uniform(0.2, 1.0), rng.uniform(0, TAU))
                      for _ in range(int(w * self.gy / 30 * self.density))]
        self.stars = [s for s in self.stars if not self.cover[s[1] * w + s[0]]]
        # clouds
        cl = str(self.opt("clouds")).lower()
        self.cstyle = cl if cl in ("cumulus", "streaks", "scattered", "none") else rng.choice(("cumulus", "streaks", "scattered", "cumulus", "none"))
        self.cspeed = rng.uniform(5, 12) * rng.choice((-1, 1))
        self.TW, self.TH = 128, 32
        sx, sy = {"cumulus": (8.0, 4.0), "streaks": (20.0, 1.2), "scattered": (5.0, 3.0), "none": (8, 4)}[self.cstyle]
        pxl, pyl = int(self.TW / sx), max(1, int(self.TH / sy))
        self.ctile = [[0.7 * tnoise(x / sx, y / sy, pxl, pyl, self.seed + 3)
                       + 0.3 * tnoise(x / sx * 2.5, y / sy * 2, int(pxl * 2.5) or 1, int(pyl * 2) or 1, self.seed + 4)
                       for x in range(self.TW)] for y in range(self.TH)]
        self.cthr = {"cumulus": 0.5, "streaks": 0.6, "scattered": 0.58, "none": 2.0}[self.cstyle]
        self.cband = (rng.uniform(0.05, 0.25), rng.uniform(0.4, 0.75))
        # traffic
        self.cars = []
        lanes = [self.road_y + (1 if road > 1 else 0), self.road_y]
        self.lanes = lanes
        for _ in range(int(w / 5 * self.density)):
            self.cars.append(self.new_car(rng.uniform(0, w)))
        self.lamps = list(range(rng.randint(2, 6), w, rng.randint(7, 12)))
        self.plane = None
        self.plane_timer = rng.uniform(2, 12)
        self.moon_phase = rng.uniform(-0.8, 0.8)

    def make_building(self, x0, x1, hgt, layer):
        rng = self.rng
        g = self.g
        w, gy = self.w, self.gy
        b = Building()
        b.x0, b.x1, b.layer = x0, x1, layer
        b.cells, b.edges, b.wins, b.lights = [], [], [], []
        b.shade = rng.uniform(-0.15, 0.15)
        bw = x1 - x0
        top = gy - hgt
        b.top = top
        # tiers (setbacks)
        tiers = [(x0, x1, top)]
        if bw >= 6 and hgt > 8 and rng.random() < g["setback"]:
            n = rng.randint(1, 2)
            cx0, cx1, ctop = x0, x1, top
            tiers = []
            for k in range(n + 1):
                tiers.append((cx0, cx1, ctop))
                inset = rng.randint(1, max(1, (cx1 - cx0) // 4))
                if cx1 - cx0 - 2 * inset < 3:
                    break
                cx0, cx1 = cx0 + inset, cx1 - inset
                ctop -= rng.uniform(2, max(2.5, hgt * 0.25))
            tiers = tiers[::-1]
        # rasterize tiers: the widest tier at the bottom
        occupied = {}
        for k, (tx0, tx1, ttop) in enumerate(sorted(tiers, key=lambda t: t[2])):
            for y in range(max(0, int(ttop)), gy):
                for x in range(max(0, tx0), min(w, tx1)):
                    occupied[(x, y)] = (tx0, tx1, int(ttop))
        # window style for this building
        style = rng.choice(("grid", "grid", "dense", "bands", "strips", "sparse"))
        colstep = 2 if style in ("grid", "sparse", "strips") else 1
        rowstep = 1 if style != "sparse" else 2
        warm = rng.random() < g["warm"]
        tone = rng.choice(WARM) if warm else rng.choice(COOL)
        for (x, y), (tx0, tx1, ttop) in occupied.items():
            edge = x == tx0 or x == tx1 - 1
            roof = y == ttop
            b.cells.append((x, y, 1 if edge else 0, roof))
            if roof or edge or y >= gy - 1 or y == ttop + 1 and bw > 4:
                continue
            lx = x - tx0 - 1
            ly = y - ttop
            if style == "bands" and ly % 2 == 0:
                continue
            if style == "strips" and lx % 3 == 2:
                continue
            if colstep == 2 and lx % 2 == 1:
                continue
            if rowstep == 2 and ly % 2 == 1:
                continue
            ch = "=" if style == "bands" else "|" if style == "strips" else "▄"
            kind = 0 if rng.random() > 0.04 else 1      # 1 = flickering tv glow
            col = tone if rng.random() < 0.8 else rng.choice(WARM + COOL)
            b.wins.append((x, y, rng.uniform(0.05, 0.95), rng.uniform(0.15, 1.6), col, kind, ch, rng.random()))
        # roof grammar
        tx0, tx1, ttop = min(tiers, key=lambda t: t[2])
        ttop = int(ttop)
        mid = (tx0 + tx1 - 1) // 2
        r = rng.random()
        if layer == 1 and hgt > 10 and r < g["spire"]:
            n = rng.randint(3, max(3, int(hgt * 0.35)))
            for k in range(1, n + 1):
                b.edges.append((mid, ttop - k, "|" if k < n else "^"))
            b.lights.append((mid, ttop - n - 1, rng.uniform(0, TAU)))
        elif hgt > 6 and r < g["spire"] + g["crown"] and tx1 - tx0 >= 5:
            # stepped / pyramid crown
            cx0, cx1, y = tx0, tx1 - 1, ttop - 1
            while cx1 - cx0 >= 1 and y >= 0:
                b.edges.append((cx0, y, "/"))
                b.edges.append((cx1, y, "\\"))
                for x in range(cx0 + 1, cx1):
                    b.edges.append((x, y, "█"))
                cx0 += 1
                cx1 -= 1
                y -= 1
            if cx1 == cx0:
                b.edges.append((cx0, y, "^"))
        elif r < g["spire"] + g["crown"] + g["antenna"]:
            n = rng.randint(2, 5)
            ax = rng.randint(tx0 + 1, max(tx0 + 1, tx1 - 2))
            for k in range(1, n + 1):
                b.edges.append((ax, ttop - k, "|" if k > 1 else "+"))
            b.lights.append((ax, ttop - n - 1, rng.uniform(0, TAU)))
            if rng.random() < 0.4 and tx1 - tx0 > 6:
                ax2 = ax + rng.choice((-2, 2, 3))
                if tx0 < ax2 < tx1 - 1:
                    for k in range(1, n // 2 + 2):
                        b.edges.append((ax2, ttop - k, "|"))
        elif hgt < self.gy * 0.6 and r < g["spire"] + g["crown"] + g["antenna"] + g["tower"] and tx1 - tx0 >= 5:
            tx = rng.randint(tx0 + 1, tx1 - 4)
            for dx, dy, ch in ((0, 1, "/"), (2, 1, "\\"), (0, 2, "|"), (1, 2, "_"), (2, 2, "|"),
                               (0, 3, "."), (1, 3, "-"), (2, 3, ".")):
                b.edges.append((tx + dx, ttop - dy, ch))
        elif r < 0.85 and tx1 - tx0 >= 4:
            b.edges.append((tx0 + 1, ttop - 1, "_"))      # rooftop hut
            b.edges.append((tx0 + 2, ttop - 1, "_"))
        b.edges = [(x, y, ch) for x, y, ch in b.edges if 0 <= x < w and 0 <= y < gy]
        return b

    def new_car(self, x=None):
        rng = self.rng
        lane = rng.randrange(2)
        d = 1 if lane == 0 else -1
        if x is None:
            x = -rng.uniform(1, 20) if d > 0 else self.w + rng.uniform(1, 20)
        return [x, lane, d * rng.uniform(14, 26), rng.randint(2, 6), rng.random()]

    # ------------------------------------------------------------------ time
    def tod(self):
        cyc = max(4.0, self.opt("cycle"))
        return (self.tod0 + self.t / cyc) % 1.0

    def update(self, dt):
        super().update(dt)
        rng = self.rng
        w = self.w
        tod = self.tod()
        # rush hours: more traffic around 8:00 and 18:00, little at 3:00
        busy = 0.25 + 0.75 * max(math.exp(-((tod - 0.33) / 0.06) ** 2), math.exp(-((tod - 0.75) / 0.07) ** 2), 0.35 * (0.2 < tod < 0.95))
        keep = []
        for c in self.cars:
            c[0] += c[2] * dt
            if -25 < c[0] < w + 25:
                keep.append(c)
        self.cars = keep
        target = int(w / 4.5 * self.density * busy)
        while len(self.cars) < target and rng.random() < 0.5:
            self.cars.append(self.new_car())
        p = self.plane
        if p is None:
            self.plane_timer -= dt
            if self.plane_timer <= 0:
                d = rng.choice((-1, 1))
                self.plane = [-3 if d > 0 else w + 3, rng.uniform(1, max(2, self.gy * 0.3)), d * rng.uniform(6, 11), rng.uniform(-0.25, 0.1)]
        else:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            if p[0] < -5 or p[0] > w + 5 or p[1] < -1:
                self.plane = None
                self.plane_timer = rng.uniform(6, 20)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, t = self.w, self.h, self.t
        if (cv.w, cv.h) != (w, h):
            return
        tod = self.tod()
        ang = TAU * (tod - 0.25)
        e = math.sin(ang)               # sun elevation
        top_c, mid_c, hor_c = sky_at(e)
        dark = clamp(0.35 - e * 2.2)    # 0 day .. 1 night
        dawn = tod < 0.5
        if dawn:
            hor_c = mix(hor_c, (255, 150, 170), 0.25 * clamp(1 - abs(e) * 5))
        gy = self.gy
        put = cv.put
        cover = self.cover
        # sun & moon positions on wide arcs
        arc_w, arc_h = w * 0.62, gy * 1.05
        sun = (w / 2 - math.cos(ang) * arc_w, gy - math.sin(ang) * arc_h)
        moon = (w / 2 + math.cos(ang) * arc_w, gy + math.sin(ang) * arc_h)
        sr = max(2.0, min(w, h * ASPECT) * 0.055)
        glow_c = mix((255, 150, 70), (255, 250, 230), clamp(e * 3))
        bright = clamp(0.25 + e * 1.5)
        # --- sky
        for y in range(gy):
            f = y / max(1, gy - 1)
            col = gradient((top_c, mid_c, hor_c), f ** 0.9)
            dens = 0.12 + 0.45 * f + 0.6 * bright
            lv = 0.12 + 0.25 * f + 0.25 * bright
            dyS = (y + 0.5 - sun[1]) * ASPECT
            kk = 0.5 + 0.8 * lv
            tone = bright * (0.55 + 0.45 * f)
            cd = scale(col, 0.75 + 0.35 * f)
            cc = (col[0] * kk, col[1] * kk, col[2] * kk)
            for x in self.skyrows[y]:
                r = _hash(x, y, 9)
                dx = x + 0.5 - sun[0]
                gl = 0.0
                if e > -0.15:
                    d2 = (dx * dx + dyS * dyS) / (sr * sr)
                    if d2 < 60:
                        gl = clamp(1.4 / (1 + d2 * 0.25) - 0.08) * clamp((e + 0.15) * 5)
                if r < dens + gl:
                    if gl > 0.05:
                        c = mix(col, glow_c, clamp(gl * 1.3))
                        k = 0.5 + 0.8 * min(1.0, lv + gl * 0.6)
                        put(x, y, ":" if gl > 0.4 and r > 0.4 else "·" if r > 0.25 else ".", (c[0] * k, c[1] * k, c[2] * k), level=lv)
                    elif tone > 0.45:
                        put(x, y, "░" if r < (tone - 0.45) * 5 else ":", cd, level=lv)
                    else:
                        put(x, y, "." if r < 0.55 * dens else "·" if r < 0.85 * dens else ":", cc, level=lv)
        # stars
        if dark > 0.3:
            for x, y, b, ph in self.stars:
                tw = b * (0.5 + 0.5 * math.sin(t * (1 + 2 * b) + ph)) * clamp((dark - 0.3) * 2)
                if tw > 0.2:
                    put(x, y, "." if tw < 0.5 else "·" if tw < 0.7 else "+" if b > 0.9 else "*", scale((240, 240, 255), 0.4 + 0.6 * tw), level=0.3)
        # sun / moon discs
        if sun[1] < gy + sr:
            self.disc(cv, sun[0], sun[1], sr, [(255, 120, 60), (255, 200, 120), (255, 250, 220)], clamp(e * 3 + 0.4))
        if moon[1] < gy + sr:
            self.disc(cv, moon[0], moon[1], sr * 0.75, [(150, 150, 170), (215, 220, 235), (250, 250, 255)], 0.7, self.moon_phase)
        self.draw_clouds(cv, e, dark, top_c, hor_c, glow_c, sun)
        if self.plane is not None:
            self.draw_plane(cv, dark)
        self.draw_city(cv, e, dark, hor_c, sun)
        self.draw_road(cv, dark, tod)
        if self.harbor:
            self.draw_water(cv, dark, hor_c)

    def disc(self, cv, cx, cy, r, stops, k, phase=None):
        put = cv.put
        w, gy = self.w, self.gy
        cover = self.cover
        for y in range(max(0, int(cy - r / ASPECT) - 1), min(gy, int(cy + r / ASPECT) + 2)):
            for x in range(max(0, int(cx - r) - 1), min(w, int(cx + r) + 2)):
                if cover[y * w + x]:
                    continue
                dx = (x + 0.5 - cx) / r
                top = dx * dx + ((y + 0.25 - cy) * ASPECT / r) ** 2 <= 1
                bot = dx * dx + ((y + 0.75 - cy) * ASPECT / r) ** 2 <= 1
                if phase is not None:      # moon shadow
                    sx = dx + phase * 1.4
                    if top and sx * sx + ((y + 0.25 - cy) * ASPECT / r) ** 2 < 0.9:
                        top = False
                    if bot and sx * sx + ((y + 0.75 - cy) * ASPECT / r) ** 2 < 0.9:
                        bot = False
                if not (top or bot):
                    continue
                d = math.sqrt(dx * dx + ((y + 0.5 - cy) * ASPECT / r) ** 2)
                col = gradient(stops, (1 - min(1.0, d) * 0.6) * k + (1 - k) * 0.3)
                put(x, y, "█" if top and bot else "▀" if top else "▄", col, level=1.0)

    def draw_clouds(self, cv, e, dark, top_c, hor_c, glow_c, sun):
        if self.cstyle == "none":
            return
        w, gy, t = self.w, self.gy, self.t
        tile, TW, TH = self.ctile, self.TW, self.TH
        thr = self.cthr
        b0, b1 = self.cband
        off = t * self.cspeed
        put = cv.put
        cover = self.cover
        day_c = (245, 248, 255)
        night_c = (46, 48, 66)
        lit = mix(night_c, day_c, clamp(e * 3 + 0.4))
        under = mix((120, 70, 60), (255, 130, 90), clamp(1 - abs(e) * 4)) if abs(e) < 0.3 else lit
        city = (110, 80, 70)
        ramp = CLOUD_RAMP if self.cstyle != "streaks" else " .-~=="
        rn = len(ramp) - 1
        lo, hi = int(gy * b0), int(gy * b1)
        for y in range(lo, min(gy, hi + 1)):
            f = (y - lo) / max(1, hi - lo)
            band = math.sin(f * math.pi)
            row = tile[int(y * TH / max(1, gy)) % TH]
            rowb = tile[(int(y * TH / max(1, gy)) + 2) % TH]
            for x in range(w):
                if cover[y * w + x]:
                    continue
                u = int(x + off) % TW
                n = row[u] * band
                if n < thr:
                    continue
                k = clamp((n - thr) / (1 - thr) * 2.2)
                bottom = clamp((rowb[u] - row[u]) * 4 + 0.5)       # lower faces
                c = mix(lit, under, bottom * 0.7)
                if dark > 0.6:
                    c = mix(c, city, 0.3 * bottom)              # city glow on the underside at night
                dsun = abs(x - sun[0]) / max(1, w)
                if abs(e) < 0.35:
                    c = mix(c, glow_c, clamp(0.5 - dsun) * 0.7)
                lv = 0.2 + 0.75 * k
                idx = int(lv * rn + 0.5)
                put(x, y, ramp[idx], scale(c, 0.45 + 0.55 * lv), level=lv)

    def draw_plane(self, cv, dark):
        x, y, vx, vy = self.plane
        t = self.t
        put = cv.put
        xi, yi = int(x), int(y)
        if 0 <= yi < self.gy and self.cover[yi * self.w + max(0, min(self.w - 1, xi))]:
            return
        if dark > 0.4:
            if math.sin(t * 9) > 0.6:
                put(xi, yi, "*", (255, 255, 255), level=1)
            put(xi - (1 if vx > 0 else -1), yi, ".", (255, 60, 60) if int(t * 2) % 2 else (60, 255, 120), level=1)
        else:
            cv.text(xi - 1, yi, "-=-" if vx > 0 else "-=-", (90, 95, 110))
            put(xi + (2 if vx > 0 else -2), yi, ">" if vx > 0 else "<", (90, 95, 110))

    def draw_city(self, cv, e, dark, hor_c, sun):
        put = cv.put
        t = self.t
        tod = self.tod()
        # late-night switch-off: grows from 22:00 to 06:00
        late = ((tod - 0.9) % 1.0) / 0.35 if (tod > 0.9 or tod < 0.25) else 0.0
        day_wall = [(118, 132, 160), (82, 92, 116)]
        night_wall = [(22, 22, 40), (12, 12, 22)]
        dusk_wall = [(72, 50, 92), (40, 28, 56)]
        kd = clamp((dark - 0.5) * 2)
        sunx = sun[0]
        flick = (0.6 + 0.4 * math.sin(t * 13)) * (0.7 + 0.3 * math.sin(t * 7.3))
        for b in self.blds:
            L = b.layer
            base = mix(mix(day_wall[L], dusk_wall[L], clamp(dark * 1.6)), night_wall[L], kd)
            if L == 0:
                base = mix(base, hor_c, 0.25)
            base = scale(base, 1 + b.shade)
            lit_side = 1 if sunx > (b.x0 + b.x1) / 2 else 0
            edge_c = mix(base, mix((255, 210, 150), (255, 255, 255), clamp(e * 2)), 0.35 * clamp(e * 4 + 0.6) * (1 - kd))
            roof_c = mix(base, hor_c, 0.4)
            for x, y, edge, roof in b.cells:
                if roof:
                    put(x, y, "▄", roof_c if not kd else mix(roof_c, base, kd), level=0.4)
                elif edge and ((x == b.x1 - 1) == bool(lit_side)):
                    put(x, y, "█", edge_c, level=0.4)
                else:
                    put(x, y, "█", base, level=0.4)
            for x, y, ch in b.edges:
                put(x, y, ch, mix(base, (200, 200, 220), 0.25) if ch not in "█" else base, level=0.4)
            # windows
            win_day = mix(base, mix(hor_c, (200, 220, 255), 0.5), 0.35)
            for x, y, on, off, col, kind, ch, r in b.wins:
                lit = dark > on and late < off
                if lit:
                    c = col if not kind else mix(TV, (255, 255, 255), flick * 0.4)
                    if L == 0:
                        c = mix(c, base, 0.35)
                    put(x, y, ch, c, level=0.9)
                elif dark < 0.4 and r < 0.6:
                    put(x, y, ch, win_day, level=0.5)
            # blinking aviation lights
            for x, y, ph in b.lights:
                on = math.sin(t * 3.0 + ph) > 0.2
                put(x, y, "*" if on else ".", (255, 40, 30) if on else (110, 20, 20), level=1.0)

    def draw_road(self, cv, dark, tod):
        w, h, t = self.w, self.h, self.t
        put = cv.put
        ry = self.road_y
        lanes = self.lanes
        asphalt = mix((70, 72, 80), (24, 24, 32), dark)
        for y in range(ry, self.water_y):
            for x in range(w):
                if (x + y * 3) % 4 == 0:
                    put(x, y, "_" if y == ry else ".", asphalt, level=0.1)
        # street lamps
        for lx in self.lamps:
            put(lx, ry - 1, "|", mix((90, 90, 100), (60, 60, 70), dark), level=0.5)
            if dark > 0.45:
                put(lx, ry - 2, "o", (255, 210, 130), level=1.0)
                put(lx - 1, ry - 1, ".", (160, 120, 70), level=0.3)
                put(lx + 1, ry - 1, ".", (160, 120, 70), level=0.3)
            else:
                put(lx, ry - 2, "-", (110, 110, 120), level=0.5)
        # traffic: long-exposure light trails at night, little cars by day
        for x, lane, vx, ln, r in self.cars:
            y = lanes[lane]
            d = 1 if vx > 0 else -1
            if dark > 0.35:
                head = (255, 250, 220) if d > 0 else (255, 40, 30)
                tail = (255, 200, 120) if d > 0 else (150, 10, 10)
                L = ln + 3
                for k in range(L):
                    f = k / L
                    put(x - d * k, y, "=" if f < 0.3 else "-", mix(head, tail, f), level=1 - f)
            else:
                body = [(200, 50, 50), (60, 110, 200), (230, 230, 235), (240, 190, 50), (40, 40, 50)][int(r * 5)]
                s = "o=o" if r > 0.5 else "o-o"
                for k, ch in enumerate(s):
                    put(int(x) - d * k, y, ch if ch != "o" else "o", body if ch != "o" else (40, 40, 40), level=0.8)

    def draw_water(self, cv, dark, hor_c):
        w, h, t = self.w, self.h, self.t
        wy = self.water_y
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        put = cv.put
        base = mix((40, 80, 130), (8, 12, 30), dark)
        sin = math.sin
        for y in range(wy, h):
            d = y - wy
            src = wy - 1 - self.road_rows() - int(d * 1.5)
            amp = 0.6 + d * 0.5
            for x in range(w):
                wob = sin(y * 1.9 + t * 2.1 + x * 0.17) + 0.5 * sin(x * 0.41 - t * 1.4 + y)
                sx = int(x + wob * amp)
                if 0 <= src and 0 <= sx < w:
                    i = src * w + sx
                    c = fg[i]
                    if c is not None and ch[i] != " " and (lv[i] > 0.6 or (dark < 0.4 and lv[i] > 0.3)):
                        k = 0.65 - d * 0.04
                        put(x, y, "~" if wob > 0.2 else "-" if wob > -0.7 else "=", (c[0] * k, c[1] * k, c[2] * k + 12), level=0.3)
                        continue
                if (x + y * 5 + int(t * 4)) % 6 == 0:
                    put(x, y, "~" if wob > 0 else "-", scale(base, 0.8 + 0.3 * wob), level=0.1)

    def road_rows(self):
        return self.water_y - self.road_y
