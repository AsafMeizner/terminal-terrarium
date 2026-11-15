"""Desert dunes under a big sky: wind-blown sand off the crests, saguaros, a slow cycle from day
through sunset to a milky-way night and dawn, heat shimmer, tumbleweeds and a camel caravan."""
import math

from ..engine import ASPECT, RAMPS, Scene, clamp, gradient, hsv, mix, noise1, noise2, scale, smoothstep
from .sakura import disc_glyph

TAU = math.tau


def qc(c):
    r, g, b = c
    return (0 if r < 0 else 252 if r > 252 else int(r) & ~3,
            0 if g < 0 else 252 if g > 252 else int(g) & ~3,
            0 if b < 0 else 252 if b > 252 else int(b) & ~3)


def hsh(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def keyed(keys, p):
    """Cyclic interpolation of (phase, value-tuple) keys over p in [0, 1)."""
    p %= 1.0
    for (k0, v0), (k1, v1) in zip(keys, keys[1:]):
        if k0 <= p <= k1:
            f = (p - k0) / max(1e-9, k1 - k0)
            return tuple(mix(a, b, f) for a, b in zip(v0, v1))
    return keys[-1][1]


# phase: 0 noon, 0.25 sunset, 0.5 midnight, 0.75 dawn
SKY = [  # zenith, mid, horizon
    (0.0, ((40, 100, 200), (100, 160, 225), (230, 215, 190))),
    (0.15, ((50, 100, 190), (130, 160, 210), (250, 205, 150))),
    (0.22, ((50, 50, 130), (190, 90, 120), (255, 130, 60))),
    (0.27, ((20, 20, 70), (90, 40, 100), (220, 80, 60))),
    (0.33, ((6, 8, 26), (14, 16, 46), (40, 30, 70))),
    (0.5, ((3, 4, 16), (8, 10, 32), (22, 22, 54))),
    (0.67, ((6, 8, 26), (14, 18, 50), (40, 36, 80))),
    (0.73, ((30, 40, 100), (120, 90, 150), (255, 140, 110))),
    (0.8, ((50, 90, 180), (150, 170, 210), (255, 200, 150))),
    (1.0, ((40, 100, 200), (100, 160, 225), (230, 215, 190))),
]
SAND = [  # lit, shadow
    (0.0, ((250, 205, 135), (170, 110, 70))),
    (0.15, ((255, 190, 110), (160, 95, 70))),
    (0.23, ((255, 130, 70), (110, 45, 70))),
    (0.28, ((150, 70, 90), (50, 22, 50))),
    (0.34, ((100, 104, 160), (34, 34, 70))),
    (0.5, ((96, 100, 160), (30, 32, 66))),
    (0.66, ((100, 104, 160), (34, 34, 70))),
    (0.73, ((220, 130, 120), (90, 50, 80))),
    (0.8, ((255, 190, 130), (150, 90, 80))),
    (1.0, ((250, 205, 135), (170, 110, 70))),
]
SAND_RAMP = " .·:;+*%#"
LOCKS = {"day": 0.06, "sunset": 0.232, "night": 0.5, "dawn": 0.762}
CAMEL = (
    (" ,^^._o", " /|  |\\"),
    (" ,^^._o", " |\\  /|"),
)


class Desert(Scene):
    name = "desert"
    title = "Desert"
    blurb = "sand streaming off dunes, saguaros, a camel caravan, sunset into a milky-way night"
    tags = ("nature", "sky", "night", "calm")
    options = {
        "cycle": (90.0, "seconds for a full day and night"),
        "time": ("cycle", "cycle, day, sunset, night or dawn (lock the time)"),
        "caravan": (True, "a camel caravan crosses the far dunes now and then"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.seed = rng.randrange(1 << 15)
        s = self.seed
        lock = self.opt("time")
        self.lock = LOCKS.get(lock)
        self.cyc = max(10.0, float(self.opt("cycle")))
        self.p0 = rng.uniform(0.0, 0.12) if self.lock is None else self.lock
        self.wind = rng.choice((-1, 1))
        tint = hsv(rng.random(), 0.5, 1.0)
        self.tint, self.tk = tint, rng.uniform(0.0, 0.15)
        # -- dune field: layers far -> near, each a max of asymmetric dunes
        self.horizon = h * rng.uniform(0.5, 0.6)
        nl = 4 if h >= 16 else 3
        self.layers = []
        for k in range(nl):
            f = k / max(1, nl - 1)
            base = self.horizon + (h - self.horizon) * (0.12 + 0.62 * f ** 1.1)
            amp = (h - self.horizon) * rng.uniform(0.28, 0.45) * (0.5 + 0.8 * f)
            prof = [base + 0.5 * noise1(x * 0.05, s + k) for x in range(w)]
            n = rng.randint(2, 4) + (w // 70)
            for _ in range(n):
                c = rng.uniform(-0.1, 1.1) * w
                hgt = amp * rng.uniform(0.5, 1.0)
                lw = w * rng.uniform(0.12, 0.3) * (0.6 + f)
                ll = lw * rng.uniform(0.25, 0.45)
                for x in range(w):
                    dx = (x - c) * self.wind
                    if dx < 0:
                        u = -dx / lw
                        v = hgt * max(0.0, 1 - u * u) if u < 1 else 0.0
                    else:
                        u = dx / ll
                        v = hgt * max(0.0, 1 - u) ** 1.6 if u < 1 else 0.0
                    prof[x] = min(prof[x], base - v)
            self.layers.append(prof)
        self.build_bg()
        # -- saguaros
        self.cacti = []
        for _ in range(rng.randint(1, 3) + w // 60):
            k = rng.randrange(1, nl)
            x = rng.uniform(3, w - 4)
            self.cacti.append(self.make_cactus(x, k))
        self.cacti.sort(key=lambda c: c["layer"])
        # -- sky: stars and milky way
        self.stars = [(rng.uniform(0, w), rng.uniform(0, self.horizon), rng.uniform(0.2, 1.0), rng.uniform(0, TAU))
                      for _ in range(int(self.count(80)))]
        self.band = self.build_milky_way()
        self.grains = []
        self.weed = None
        self.weed_wait = rng.uniform(5, 15)
        self.caravan = None
        self.caravan_wait = rng.uniform(2, 10)

    # -- static terrain ------------------------------------------------------------------
    def build_bg(self):
        w, h = self.w, self.h
        s = self.seed
        n = w * h
        self.cell_layer = [-1] * n
        self.cell_slope = [0.0] * n
        self.cell_depth = [0.0] * n
        self.cell_tex = [0.0] * n
        self.cell_fade = [1.0] * n
        self.sky_cells = []
        self.surface = [h] * w
        L = self.layers
        for x in range(w):
            for y in range(h):
                i = y * w + x
                cover = [j for j in range(len(L)) if y >= int(L[j][x])]
                if not cover:
                    self.sky_cells.append(i)
                    continue
                k = max(cover)
                self.cell_layer[i] = k
                prof = L[k]
                sl = prof[min(w - 1, x + 1)] - prof[max(0, x - 1)]
                self.cell_slope[i] = clamp(-sl * 1.5, -1.0, 1.0)   # + faces right
                self.cell_depth[i] = clamp((y - prof[x]) / max(2.0, (h - prof[x])))
                self.cell_fade[i] = 1.0 / (1.0 + (y - prof[x]) / max(2.0, (h - self.horizon) * 0.18))
                self.cell_tex[i] = math.sin(x * 0.55 + y * 2.1 + 2.5 * noise2(x * 0.06, y * 0.25, s + 3))
            self.surface[x] = int(min(l[x] for l in L))
        self.bg_cache = {}

    def dune_chars(self, ramp, lq):
        """Glyphs for the dunes for a quantized sun direction lq (-10..10)."""
        key = (ramp, lq)
        out = self.bg_cache.get(key)
        if out is not None:
            return out
        lx = lq / 10.0
        nr = len(ramp) - 1
        w = self.w
        out = [" "] * (self.w * self.h)
        bright = [0] * (self.w * self.h)
        L = self.layers
        for i, k in enumerate(self.cell_layer):
            if k < 0:
                continue
            x = i % w
            y = i // w
            sl = self.cell_slope[i]
            d = self.cell_depth[i]
            lit = clamp(0.45 + 0.8 * sl * lx * self.cell_fade[i] + 0.1 * (1 - abs(lx)) - 0.15 * d)
            far = 1 - k / max(1, len(L) - 1)
            b = clamp(lit * (0.75 + 0.25 * (1 - far)))
            crest = y == int(L[k][x])
            tex = self.cell_tex[i]
            if crest:
                c = "_" if abs(sl) < 0.2 else ("/" if sl > 0 else "\\")
            elif tex > 0.93 and b > 0.45:
                c = "~"
            else:
                j = int(b * (len(SAND_RAMP) - 1) * 1.05 + hsh(x, y, 9) * 0.8 - 0.4)
                c = SAND_RAMP[max(1, min(len(SAND_RAMP) - 1, j))]
            out[i] = c
            bright[i] = min(9, int(b * 9.99))
        self.bg_cache[key] = (out, bright)
        return out, bright

    def build_milky_way(self):
        rng = self.rng
        w, h = self.w, self.h
        s = self.seed
        x0, y0 = rng.uniform(0.0, 0.3) * w, rng.uniform(0.0, 0.2) * h
        x1, y1 = rng.uniform(0.75, 1.0) * w, rng.uniform(0.8, 1.0) * self.horizon
        if rng.random() < 0.5:
            x0, x1 = x1, x0
        dx, dy = x1 - x0, (y1 - y0) * ASPECT
        ln = math.sqrt(dx * dx + dy * dy) or 1
        nx, ny = -dy / ln, dx / ln
        width = h * rng.uniform(0.18, 0.3)
        cells = []
        for y in range(int(self.horizon)):
            for x in range(w):
                d = ((x - x0) * nx + (y - y0) * ASPECT * ny) / width
                core = math.exp(-d * d * 2.2)
                n = noise2(x * 0.08, y * 0.2, s + 50) * 0.5 + noise2(x * 0.25, y * 0.6, s + 51) * 0.3
                dust = noise2(x * 0.12, y * 0.35, s + 52)
                lev = core * (0.55 + n) - (0.35 * core if dust > 0.35 and abs(d) < 0.35 else 0)
                if lev > 0.12 and hsh(x, y, s + 53) < 0.25 + lev:
                    col = mix((120, 110, 200), (255, 220, 200), clamp(core * 1.2 + n * 0.5))
                    if n > 0.35:
                        col = mix(col, (230, 140, 220), 0.3)
                    cells.append((y * w + x, clamp(lev), col))
        return cells

    def make_cactus(self, x, layer):
        rng = self.rng
        h = self.h
        prof = self.layers[layer]
        base = prof[int(clamp(x, 0, self.w - 1))]
        far = 1 - layer / max(1, len(self.layers) - 1)
        Ht = max(3, int((base - self.horizon * 0.7) * rng.uniform(0.35, 0.7) * (1.1 - 0.5 * far)))
        wide = Ht >= 9
        cells = []
        cx = int(x)
        top = int(base) - Ht
        for y in range(top, int(base) + 1):
            if wide:
                cells += [(cx - 1, y, "("), (cx, y, "|"), (cx + 1, y, ")")]
            else:
                cells.append((cx, y, "|"))
        if wide:
            cells += [(cx - 1, top - 1, "."), (cx, top - 1, "-"), (cx + 1, top - 1, ".")]
        else:
            cells.append((cx, top - 1, "."))
        arms = rng.choice((0, 1, 2, 2, 3, 4)) if Ht >= 5 else 0
        side = rng.choice((-1, 1))
        for a in range(arms):
            ay = int(top + Ht * rng.uniform(0.3, 0.65))
            reach = rng.randint(1, 3) + (1 if wide else 0)
            up = max(1, int(Ht * rng.uniform(0.15, 0.45)))
            x0 = cx + side * (2 if wide else 1)
            for k in range(reach):
                cells.append((x0 + side * k, ay, "="))
            ex = x0 + side * (reach - 1) + side
            cells.append((ex, ay, "/" if side > 0 else "\\"))
            for k in range(1, up + 1):
                cells.append((ex, ay - k, "|"))
            cells.append((ex, ay - up - 1, "."))
            if rng.random() < 0.8:
                side = -side
        return {"cells": cells, "layer": layer, "far": far}

    # -- update ---------------------------------------------------------------------------
    def phase(self):
        if self.lock is not None:
            return self.lock
        return (self.p0 + self.t / self.cyc) % 1.0

    def update(self, dt):
        super().update(dt)
        rng = self.rng
        w, h = self.w, self.h
        t = self.t
        gust = 0.5 + 0.5 * noise1(t * 0.2, self.seed + 7)
        # sand streaming off the crests of the nearer dunes
        for k in range(1, len(self.layers)):
            prof = self.layers[k]
            rate = dt * w * 0.25 * gust * (0.5 + 0.5 * k / len(self.layers)) * self.density
            for _ in range(int(rate) + (1 if rng.random() < rate - int(rate) else 0)):
                x = rng.randrange(1, w - 1) if w > 2 else 0
                if prof[x] <= prof[x - 1] and prof[x] <= prof[min(w - 1, x + 1)] or rng.random() < 0.08:
                    self.grains.append([x + 0.5, prof[x] - 0.3, self.wind * rng.uniform(4, 9) * (0.6 + gust),
                                        rng.uniform(-0.6, 0.3), 0.0, rng.uniform(0.6, 1.6), k])
        keep = []
        for g in self.grains:
            g[4] += dt
            g[0] += g[2] * dt
            g[1] += g[3] * dt
            g[3] += 0.4 * dt
            if g[4] < g[5] and 0 <= g[0] < w:
                keep.append(g)
        self.grains = keep[-900:]
        # tumbleweed
        if self.weed is None:
            self.weed_wait -= dt
            if self.weed_wait <= 0:
                r = clamp(h * 0.05, 1.0, 2.5)
                self.weed = {"x": -3 if self.wind > 0 else w + 3, "r": r, "rot": 0.0, "hop": 0.0, "vy": 0.0}
        else:
            wd = self.weed
            wd["x"] += self.wind * dt * (5 + 6 * gust)
            wd["rot"] += dt * 6 * self.wind
            wd["vy"] -= dt * 30
            wd["hop"] = max(0.0, wd["hop"] + wd["vy"] * dt)
            if wd["hop"] <= 0:
                wd["vy"] = rng.uniform(4, 9) * gust
            if wd["x"] < -6 or wd["x"] > w + 6:
                self.weed = None
                self.weed_wait = rng.uniform(12, 30)
        # caravan
        if self.opt("caravan"):
            if self.caravan is None:
                self.caravan_wait -= dt
                if self.caravan_wait <= 0:
                    d = rng.choice((-1, 1))
                    n = rng.randint(3, 6)
                    self.caravan = {"x": -8 if d > 0 else w + 8 + 9 * n, "d": d, "n": n, "gap": rng.uniform(8, 11),
                                    "speed": rng.uniform(1.2, 2.2) * clamp(w / 100, 0.6, 1.5), "ph": 0.0}
            else:
                cv_ = self.caravan
                cv_["x"] += cv_["d"] * dt * cv_["speed"]
                cv_["ph"] += dt * 3
                tail = cv_["x"] - cv_["d"] * cv_["gap"] * cv_["n"]
                if (cv_["d"] > 0 and tail > w + 8) or (cv_["d"] < 0 and tail < -8):
                    self.caravan = None
                    self.caravan_wait = rng.uniform(25, 60)

    # -- drawing ----------------------------------------------------------------------------
    def draw(self, cv):
        w, h = self.w, self.h
        if cv.w != w or cv.h != h:
            return
        t = self.t
        p = self.phase()
        e = math.cos(TAU * p)                     # sun elevation
        sun_x = w * 0.5 + w * 0.44 * math.sin(TAU * p)
        night = smoothstep(0.05, -0.3, e)
        top, midc, hor = keyed(SKY, p)
        top = mix(top, scale(self.tint, 0.5), self.tk)
        lit, shade = keyed(SAND, p)
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        hz = self.horizon
        # sky
        rowc = []
        for y in range(h):
            f = clamp(y / max(1.0, hz))
            rowc.append(qc(gradient((top, midc, hor), f ** 1.1)))
        B = clamp(e * 1.2 + 0.4)
        s = self.seed
        for i in self.sky_cells:
            y = i // w
            x = i - y * w
            f = clamp(y / max(1.0, hz))
            r = hsh(x, y, s)
            dens = 0.03 + (0.1 + 0.6 * f ** 2.0) * (0.4 + 0.6 * B)
            if r < dens:
                ch[i] = "." if r < dens * 0.55 else "·" if r < dens * 0.85 else ":"
                fg[i] = rowc[y]
                lv[i] = 0.05
        # milky way + stars
        if night > 0.02:
            for i, lev, col in self.band:
                if ch[i] == " " or lev > 0.4:
                    v = lev * night
                    if v < 0.08:
                        continue
                    ch[i] = "·" if v < 0.3 else ":" if v < 0.5 else "*" if v > 0.75 and (i % 7 == 0) else "·"
                    fg[i] = qc(scale(col, 0.25 + 0.6 * v))
            for x, y, b, ph in self.stars:
                xi, yi = int(x), int(y)
                if 0 <= xi < w and 0 <= yi < h and yi < self.surface[xi] - 1:
                    tw = 0.65 + 0.35 * math.sin(t * (1.5 + b) + ph)
                    v = b * tw * night
                    if v < 0.1:
                        continue
                    i = yi * w + xi
                    ch[i] = "*" if v > 0.8 else "+" if v > 0.6 else "·" if v > 0.3 else "."
                    fg[i] = qc(scale((240, 240, 255), 0.35 + 0.65 * v))
        # sun or moon
        self.draw_orb(cv, sun_x, e, False)
        moon_x = w * 0.5 + w * 0.44 * math.sin(TAU * (p + 0.5))
        self.draw_orb(cv, moon_x, -e, True)
        # dunes
        lx = clamp((sun_x - w * 0.5) / (w * 0.44)) if e > -0.15 else -0.4 * math.sin(TAU * (p + 0.5))
        if abs(lx) < 0.6:       # the sun never stands exactly overhead: keep some relief
            lx = 0.6 if lx >= 0 else -0.6
        lq = int(round(lx * 10))
        dch, dbr = self.dune_chars(cv.ramp, lq)
        nl = len(self.layers)
        pal = []
        haze = mix(hor, midc, 0.3)
        for k in range(nl):
            far = 1 - k / max(1, nl - 1)
            row = []
            for b in range(10):
                c = mix(shade, lit, b / 9)
                c = mix(c, haze, far * 0.4)
                row.append(qc(scale(c, 0.7 + 0.4 * b / 9)))
            pal.append(row)
        layer = self.cell_layer
        for x in range(w):
            for y in range(self.surface[x], h):
                i = y * w + x
                k = layer[i]
                if k < 0:
                    continue
                ch[i] = dch[i]
                fg[i] = pal[k][dbr[i]]
                lv[i] = 0.3
        # heat shimmer on the far dunes in the day
        shim = smoothstep(0.3, 0.8, e)
        if shim > 0:
            y0 = int(hz) - 1
            for y in range(max(0, y0), min(h, y0 + 4)):
                off = int(round(math.sin(t * 7 + y * 2.3) * 1.2 * shim))
                if off:
                    a, b = y * w, (y + 1) * w
                    rowch = ch[a:b]
                    rowfg = fg[a:b]
                    ch[a:b] = rowch[-off:] + rowch[:-off]
                    fg[a:b] = rowfg[-off:] + rowfg[:-off]
        # caravan on the far dunes, then cacti, weed, grains
        if self.caravan:
            self.draw_caravan(cv, lit, shade, night, e)
        for c in self.cacti:
            self.draw_cactus(cv, c, e, night, hor)
        if self.weed:
            self.draw_weed(cv, lit, shade)
        gcol = mix(lit, (255, 255, 255), 0.2)
        for x, y, vx, vy, age, life, k in self.grains:
            xi, yi = int(x), int(y)
            if 0 <= xi < w and 0 <= yi < h:
                v = 1 - age / life
                i = yi * w + xi
                ch[i] = "~" if v > 0.7 and abs(vx) > 6 else "-" if v > 0.5 else "·" if v > 0.25 else "."
                fg[i] = qc(scale(gcol, 0.35 + 0.55 * v))

    def draw_orb(self, cv, cx, e, moon):
        w, h = self.w, self.h
        if e < -0.12:
            return
        hz = self.horizon
        cy = hz - (hz - h * 0.08) * e
        r = clamp(h * (0.09 if not moon else 0.06) * (1.25 - 0.35 * clamp(e)), 1.5, 7)
        if moon:
            col = (230, 235, 255)
            R = r * 2.4
        else:
            low = clamp(1 - e * 2.5)
            col = mix((255, 245, 210), (255, 110, 50), low)
            R = r * (3.5 + 2.5 * low)
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        for y in range(max(0, int(cy - R / ASPECT) - 1), min(h, int(cy + R / ASPECT) + 2)):
            for x in range(max(0, int(cx - R) - 1), min(w, int(cx + R) + 2)):
                if y >= self.surface[x]:
                    continue
                g, d = disc_glyph(x, y, cx, cy, r)
                i = y * w + x
                if g:
                    if moon:
                        cr = clamp(noise2(x * 0.6, y * 1.1, 77))
                        c = mix(col, (150, 160, 200), 0.5 * cr)
                    else:
                        c = mix(col, (255, 255, 230), 0.6 * (1 - min(1.0, d)))
                    ch[i] = g
                    fg[i] = qc(c)
                    lv[i] = 1.0
                else:
                    gv = (R / r - d) / (R / r - 1)
                    if gv <= 0:
                        continue
                    gv = gv * gv * (0.35 if moon else 0.8)
                    old = fg[i] or (0, 0, 0)
                    fg[i] = qc(mix(old, col, clamp(gv)))
                    if ch[i] == " " and gv > 0.1:
                        ch[i] = "·" if gv > 0.3 else "."
                    elif gv > 0.45 and not moon:
                        ch[i] = ":"
        # long glittering reflection band on the horizon at sunset
        if not moon and 0 < e < 0.3:
            y = int(hz)
            for x in range(max(0, int(cx - R * 2)), min(w, int(cx + R * 2) + 1)):
                if 0 <= y < h and self.surface[x] <= y:
                    pass

    def draw_cactus(self, cv, c, e, night, hor):
        w, h = self.w, self.h
        day = smoothstep(-0.05, 0.4, e)
        green = (90, 175, 95)
        sil = mix((96, 44, 70), (50, 56, 96), night)
        col = mix(sil, green, day)
        col = mix(col, hor, c["far"] * 0.35)
        rim = mix(col, (255, 170, 100), clamp(1 - abs(e - 0.1) * 4) * 0.6)
        k = c["layer"]
        layer = self.cell_layer
        for x, y, g in c["cells"]:
            if 0 <= x < w and 0 <= y < h:
                i = y * w + x
                if layer[i] > k:
                    continue          # hidden behind a nearer dune
                cv.ch[i] = g
                cv.fg[i] = qc(rim if g in "(/." else scale(col, 0.8) if g == ")" else col)
                cv.lv[i] = 0.8

    def draw_weed(self, cv, lit, shade):
        w, h = self.w, self.h
        wd = self.weed
        x = wd["x"]
        k = len(self.layers) - 1
        gy = self.layers[k][int(clamp(x, 0, w - 1))]
        r = wd["r"]
        cy = gy - r / ASPECT - wd["hop"] * 0.5 - 0.3
        col = mix((150, 110, 60), lit, 0.3)
        glyphs = "@%#&*o+x"
        for y in range(int(cy - r / ASPECT) - 1, int(cy + r / ASPECT) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                u = (xx + 0.5 - x) / r
                v = (y + 0.5 - cy) * ASPECT / r
                d = u * u + v * v
                if d > 1.1 or not (0 <= xx < w and 0 <= y < h):
                    continue
                a = math.atan2(v, u) + wd["rot"]
                g = glyphs[int((a * 2.5 + d * 4) % len(glyphs))]
                if d > 0.75:
                    g = "(" if u < -0.3 else ")" if u > 0.3 else "~"
                i = y * w + xx
                cv.ch[i] = g
                cv.fg[i] = qc(scale(col, 0.6 + 0.4 * (1 - d)))
                cv.lv[i] = 0.8

    def draw_caravan(self, cv, lit, shade, night, e):
        w, h = self.w, self.h
        c = self.caravan
        prof = self.layers[min(1, len(self.layers) - 1)]
        day = smoothstep(-0.05, 0.35, e)
        col = qc(mix(mix((30, 16, 30), (10, 10, 26), night), mix((110, 70, 50), shade, 0.3), day))
        for j in range(c["n"]):
            x = c["x"] - c["d"] * j * c["gap"]
            xi = int(x)
            frame = CAMEL[int(c["ph"] + j * 0.7) % 2]
            gy = prof[int(clamp(x, 0, w - 1))]
            for r, row in enumerate(frame):
                if c["d"] < 0:
                    row = row[::-1].translate(str.maketrans("/\\()", "\\/)("))
                y = int(gy - 0.2) - (len(frame) - r)
                for k, g in enumerate(row):
                    xx = xi + k - 3
                    if g != " " and 0 <= xx < w and 0 <= y < h:
                        i = y * w + xx
                        cv.ch[i] = g
                        cv.fg[i] = col
                        cv.lv[i] = 0.8
