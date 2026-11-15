"""A waterfall pouring from a mossy cliff into a pool, with mist, ripples, ferns and a rainbow."""
import math

from ..engine import ASPECT, Canvas, Scene, clamp, gradient, hsv, mix, noise1, noise2, scale

TAU = math.tau

TIMES = {
    "day": {"sky": [(50, 110, 200), (110, 170, 235), (190, 225, 250)], "sky_v": (0.2, 0.5), "dens": 0.5,
            "light": 1.0, "water": (225, 245, 255), "water2": (110, 170, 215), "pool": [(70, 150, 170), (20, 70, 100), (8, 30, 50)],
            "tint": (255, 250, 230), "stars": 0.0, "orb": None},
    "dusk": {"sky": [(40, 24, 80), (170, 80, 120), (255, 170, 110)], "sky_v": (0.1, 0.45), "dens": 0.35,
             "light": 0.7, "water": (255, 225, 210), "water2": (150, 120, 170), "pool": [(140, 90, 130), (50, 40, 90), (14, 14, 40)],
             "tint": (255, 170, 120), "stars": 0.2, "orb": "sun"},
    "night": {"sky": [(4, 6, 18), (12, 20, 50), (30, 44, 90)], "sky_v": (0.06, 0.3), "dens": 0.2,
              "light": 0.45, "water": (200, 220, 255), "water2": (80, 110, 170), "pool": [(50, 80, 140), (16, 30, 70), (4, 8, 24)],
              "tint": (150, 170, 240), "stars": 1.0, "orb": "moon"},
}
ROCKS = [
    [(26, 24, 30), (60, 56, 62), (104, 98, 100), (150, 144, 140)],      # granite
    [(34, 20, 18), (84, 50, 40), (140, 90, 66), (196, 140, 100)],       # sandstone
    [(18, 20, 26), (44, 48, 58), (80, 86, 98), (124, 130, 140)],        # basalt
]
MOSS = [(24, 60, 26), (50, 110, 40), (110, 170, 60), (170, 220, 110)]
ROCKY = "  .,:;i!|I#"
LEAFY = " .,;:\"*%&@"


def _hash(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 982451653) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 65535.0


class Drop:
    """One tier of the fall: water columns x0..x1 falling from row y0 to row y1."""
    __slots__ = ("x0", "x1", "y0", "y1", "cols")


class Waterfall(Scene):
    name = "waterfall"
    title = "Waterfall"
    blurb = "a waterfall pouring from a mossy cliff into a misty pool, ferns swaying at its edge"
    tags = ("nature", "water", "calm", "plants")
    options = {
        "flow": (1.0, "water flow (width and speed)"),
        "mist": (1.0, "amount of mist and spray"),
        "rainbow": (True, "a rainbow in the mist (daytime)"),
        "time": ("random", "random, day, dusk or night"),
    }

    # ------------------------------------------------------------------ setup
    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        tm = str(self.opt("time")).lower()
        if tm not in TIMES:
            tm = rng.choice(("day", "day", "dusk", "night"))
        self.tname = tm
        self.pal = TIMES[tm]
        self.seed = rng.randrange(1 << 15)
        self.rock = rng.choice(ROCKS)
        self.mossy = rng.uniform(0.5, 1.2)
        flow = max(0.2, self.opt("flow"))
        self.flow = flow
        self.pool_y = py = int(h * rng.uniform(0.7, 0.8))
        self.lip = lip = max(2, int(h * rng.uniform(0.12, 0.28)))
        self.cx = cx = w * rng.uniform(0.38, 0.62)
        fw = clamp(w * rng.uniform(0.09, 0.17) * flow ** 0.5, 4, 30)
        # cliff skyline: a notch for the river, shoulders either side
        shL = (lip - 1) * rng.uniform(0.2, 1.0)
        shR = (lip - 1) * rng.uniform(0.2, 1.0)
        nw = fw * 0.5 + rng.uniform(1, 4)
        self.ctop = []
        for x in range(w):
            d = abs(x + 0.5 - cx) - nw
            sh = shL if x < cx else shR
            rise = sh * clamp(d / rng.uniform(5, 9) if d > 0 else 0) if d > 0 else 0
            yy = lip - rise + 0.9 * noise1(x * 0.3, self.seed) * (d > 0)
            self.ctop.append(max(0.5, yy))
        # tiers
        ntier = rng.choice((1, 1, 2, 2, 3)) if py - lip > 12 else 1
        self.drops = []
        y0 = lip
        x0 = cx - fw / 2
        for k in range(ntier):
            if k == ntier - 1:
                y1 = py
            else:
                y1 = int(y0 + (py - y0) * rng.uniform(0.35, 0.6) / (ntier - k) * (1.3 if ntier == 2 else 1.0))
                y1 = max(y0 + 4, y1)
            d = Drop()
            d.x0, d.x1, d.y0, d.y1 = int(x0), int(x0 + fw), int(y0), int(y1)
            d.cols = [(rng.uniform(7, 12) * flow ** 0.3, rng.uniform(0, 10), rng.uniform(0.6, 1.0)) for _ in range(d.x1 - d.x0 + 4)]
            self.drops.append(d)
            # next tier: shifted, maybe wider
            x0 += rng.uniform(-fw * 0.6, fw * 0.6)
            fw = clamp(fw * rng.uniform(0.9, 1.35), 3, 30)
            x0 = clamp(x0, 2, w - fw - 2)
            y0 = y1
        self.last = self.drops[-1]
        # banks either side of the pool
        self.bankL = w * rng.uniform(0.04, 0.2)
        self.bankR = w * rng.uniform(0.8, 0.96)
        self.bank_h = rng.uniform(1.5, 4.0)
        # ferns on the banks and ledges
        self.ferns = []
        nf = max(2, int(rng.uniform(3, 7) * w / 100 * self.density))
        for k in range(nf):
            side = k % 2
            if side == 0:
                bx = rng.uniform(0, max(1.0, self.bankL + 4))
            else:
                bx = rng.uniform(min(w - 1.0, self.bankR - 4), w)
            by = self.ground(bx)
            sz = rng.uniform(0.6, 1.2) * clamp(h / 30, 0.6, 1.6)
            fronds = []
            for f in range(rng.randint(3, 6)):
                a = rng.uniform(-1.1, 1.1)
                fronds.append((a, rng.uniform(4, 7) * sz, rng.uniform(0.8, 1.6) * (1 if a > 0 else -1), rng.uniform(0, TAU)))
            self.ferns.append((bx, by, fronds, rng.choice(((60, 150, 60), (90, 170, 70), (40, 130, 80)))))
        # pines on the cliff top
        self.trees = []
        if lip > 4:
            for _ in range(rng.randint(2, 7)):
                tx = rng.uniform(0, w)
                if abs(tx - cx) < nw + 3:
                    continue
                self.trees.append((tx, rng.uniform(2.5, max(3.0, lip * 0.9))))
        # moving bits
        self.mist = []
        self.ripples = []
        self.rip_timer = 0.0
        ns = int(w * lip / 25 * self.pal["stars"] * self.density)
        self.stars = [(rng.randrange(w), rng.randrange(max(1, lip)), rng.uniform(0.2, 1), rng.uniform(0, TAU)) for _ in range(ns)]
        self.orb = None
        if self.pal["orb"]:
            ox = w * rng.choice((rng.uniform(0.08, 0.25), rng.uniform(0.75, 0.92)))
            self.orb = (ox, max(1.5, lip * rng.uniform(0.25, 0.5)), clamp(h * 0.06, 1.5, 4))
        self.rainbow = self.opt("rainbow") and tm == "day"
        self.rb_r = max(8.0, (self.last.x1 - self.last.x0) * rng.uniform(1.6, 2.4))
        self._bgkey = None

    def ground(self, x):
        """Row of the bank surface at x (pool level in the middle)."""
        w = self.w
        py = self.pool_y
        if x < self.bankL:
            return py - self.bank_h * (1 - x / max(1, self.bankL)) ** 0.7 - 0.5
        if x > self.bankR:
            return py - self.bank_h * ((x - self.bankR) / max(1, w - self.bankR)) ** 0.7 - 0.5
        return py

    def in_fall(self, x, y):
        for d in self.drops:
            if d.x0 <= x < d.x1 and d.y0 <= y < d.y1:
                return True
        return False

    # ------------------------------------------------------------------ static
    def paint_static(self, cv):
        w, h = self.w, self.h
        pal = self.pal
        s = self.seed
        sky = pal["sky"]
        lo, hi = pal["sky_v"]
        py = self.pool_y
        L = pal["light"]
        # sky
        for y in range(int(max(self.ctop)) + 1):
            f = y / max(1, self.lip)
            col = gradient(sky, clamp(f))
            for x in range(w):
                if y >= self.ctop[x]:
                    continue
                r = _hash(x, y, 5)
                if r < pal["dens"] * (0.6 + 0.6 * f):
                    v = lo + (hi - lo) * clamp(f)
                    cv.put(x, y, "░" if self.tname == "day" else "." if r < 0.2 else "·" if r > 0.4 else ":",
                           scale(col, 0.5 + v), level=v)
        if self.orb:
            ox, oy, r = self.orb
            moon = self.pal["orb"] == "moon"
            for y in range(int(oy - r / ASPECT) - 1, int(oy + r / ASPECT) + 2):
                for x in range(int(ox - r) - 1, int(ox + r) + 2):
                    if not (0 <= x < w and 0 <= y < h) or y >= self.ctop[x]:
                        continue
                    dx = (x + 0.5 - ox) / r
                    top = dx * dx + ((y + 0.25 - oy) * ASPECT / r) ** 2 <= 1
                    bot = dx * dx + ((y + 0.75 - oy) * ASPECT / r) ** 2 <= 1
                    if top or bot:
                        c = (240, 240, 255) if moon else (255, 200, 130)
                        cv.put(x, y, "█" if top and bot else "▀" if top else "▄", c, level=1)
        # pines on the cliff top (silhouettes)
        tc = mix((20, 50, 34), sky[0], 0.3) if self.tname != "day" else (34, 90, 50)
        for tx, th in self.trees:
            base = self.ctop[int(clamp(tx, 0, w - 1))]
            n = int(th)
            for k in range(n):
                y = int(base) - 1 - k
                half = (n - k) * 0.55
                for x in range(int(tx - half), int(tx + half) + 1):
                    if 0 <= x < w and 0 <= y < h:
                        ch = "/" if x < tx - half + 1 else "\\" if x > tx + half - 1 else "^" if k == n - 1 else "*"
                        cv.put(x, y, ch, scale(tc, 0.8 + 0.4 * _hash(x, y, 2)), level=0.5)
        # cliff face: strata, cracks, moss
        rock = self.rock
        drops = self.drops
        cx = self.cx
        for x in range(w):
            yt = self.ctop[x]
            iy = int(yt)
            yl, yr = self.ctop[max(0, x - 1)], self.ctop[min(w - 1, x + 1)]
            sl = (yr - yl) * 0.5
            edge = "\\" if sl > 0.7 else "/" if sl < -0.7 else "_" if yt - iy > 0.5 else "-"
            for y in range(iy, py):
                if self.in_fall(x, y):
                    continue
                if y >= self.ground(x):
                    continue
                d = (y - yt) / max(1, py - yt)
                # smooth boulders + faint strata + crack lines; lit from the top
                n = noise2(x * 0.09, y * 0.22, s + 3) * 0.6 + noise2(x * 0.22, y * 0.5, s + 4) * 0.3 + noise2(x * 0.6, y * 1.1, s + 5) * 0.1
                strata = math.sin(y * 1.3 + x * self.tilt + noise1(x * 0.05, s + 2) * 3)
                crack = abs(noise2(x * 0.16, y * 0.08, s + 6))
                wet = math.exp(-((x + 0.5 - cx) / (self.rb_r * 0.7)) ** 2)
                v = 0.45 + 0.55 * n + 0.08 * strata - 0.3 * d - 0.15 * wet
                if crack < 0.05:
                    v -= 0.25
                moss = noise2(x * 0.1, y * 0.3, s + 8) * 0.7 + noise2(x * 0.35, y * 0.7, s + 9) * 0.3
                moss += 0.35 * wet * self.mossy + 0.3 * self.mossy - 0.35 + 0.25 * (n > 0.2)
                if y == iy:
                    cv.put(x, y, edge, scale(mix(rock[3], MOSS[2], clamp(moss * 2)), 0.6 + 0.4 * L), level=0.5)
                    continue
                if moss > 0.15:
                    k = clamp((moss - 0.15) * 2.2)
                    mv = clamp(0.2 + 0.55 * k + 0.3 * n)
                    ch = LEAFY[int(mv * (len(LEAFY) - 1) + 0.5)]
                    col = scale(gradient(MOSS, mv), 0.65 + 0.45 * L)
                else:
                    v = clamp(v)
                    ch = ROCKY[int(v * (len(ROCKY) - 1) + 0.5)]
                    col = scale(gradient(rock, clamp(0.2 + v * 0.8)), 0.8 + 0.6 * L)
                if ch != " ":
                    cv.put(x, y, ch, col, level=v)
        # ledges where upper tiers land
        for d in drops[:-1]:
            for x in range(d.x0 - 1, d.x1 + 1):
                cv.put(x, d.y1, "_", rock[2], level=0.6)
        # banks
        for x in range(w):
            g = self.ground(x)
            if g >= py - 0.2:
                continue
            iy = int(g)
            cv.put(x, iy, "_" if g - iy > 0.5 else "-", mix(MOSS[2], rock[2], 0.4), level=0.6)
            for y in range(iy + 1, h):
                r = _hash(x, y, 13)
                ch = "@" if r < 0.15 else "o" if r < 0.3 else "%" if r < 0.4 else "." if r < 0.7 else ","
                col = gradient(rock, 0.35 + 0.4 * r) if r < 0.5 else gradient(MOSS, 0.2 + 0.4 * r)
                cv.put(x, y, ch, scale(col, 0.5 + 0.5 * L), level=0.4)

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

    @property
    def tilt(self):
        return 0.04

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        rng = self.rng
        d = self.last
        mist = max(0.0, self.opt("mist"))
        py = self.pool_y
        # spray and mist from the impact zone
        n = dt * (d.x1 - d.x0 + 2) * 6 * mist * self.density
        while n > 0:
            if rng.random() < n:
                x = rng.uniform(d.x0 - 1, d.x1 + 1)
                side = -1 if x < (d.x0 + d.x1) / 2 else 1
                self.mist.append([x, py - rng.uniform(0, 1), side * rng.uniform(0.5, 5.0), -rng.uniform(0.6, 3.0),
                                  0.0, rng.uniform(1.5, 4.5)])
            n -= 1
        keep = []
        for m in self.mist:
            m[4] += dt
            m[0] += m[2] * dt
            m[1] += m[3] * dt
            m[2] *= 1 - dt * 0.8
            m[3] *= 1 - dt * 0.5
            m[3] += 0.1 * dt
            if m[4] < m[5]:
                keep.append(m)
        self.mist = keep[-int(500 * max(0.2, mist)):]
        # ripples
        self.rip_timer -= dt
        if self.rip_timer <= 0:
            self.rip_timer = rng.uniform(0.6, 1.4) / max(0.3, self.flow)
            self.ripples.append([rng.uniform(d.x0, d.x1), 0.5, rng.uniform(5, 9)])
        for r in self.ripples:
            r[1] += r[2] * dt
        maxr = self.w * 0.35
        self.ripples = [r for r in self.ripples if r[1] < maxr][-8:]
        # drops on lower tiers also stir their ledge (handled in draw)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, t = self.w, self.h, self.t
        if (cv.w, cv.h) != (w, h):
            return
        self.background(cv)
        pal = self.pal
        put = cv.put
        for x, y, b, ph in self.stars:
            if y < self.ctop[x] and cv.ch[y * w + x] in " .·:":
                tw = b * (0.5 + 0.5 * math.sin(t * (1 + b) + ph))
                if tw > 0.25:
                    put(x, y, "." if tw < 0.6 else "*", scale((240, 240, 255), 0.4 + 0.6 * tw), level=0.3)
        self.draw_pool(cv)
        if self.rainbow:
            self.draw_rainbow(cv)
        for d in self.drops:
            self.draw_drop(cv, d)
        self.draw_river(cv)
        self.draw_mist(cv)
        self.draw_ferns(cv)

    def draw_river(self, cv):
        """The river at the lip, sliding toward the edge."""
        d = self.drops[0]
        t = self.t
        put = cv.put
        wc, wc2 = self.pal["water"], self.pal["water2"]
        for y in (d.y0 - 1, d.y0):
            for x in range(d.x0 - 1, d.x1 + 1):
                if not (0 <= x < self.w and 0 <= y < self.h):
                    continue
                s = math.sin(x * 1.3 - t * 6 + y * 2)
                if y == d.y0 - 1:
                    if y < self.ctop[x] - 0.2 or x < d.x0 or x >= d.x1:
                        continue
                    put(x, y, "~" if s > 0 else "-", mix(wc2, wc, 0.4 + 0.3 * s), level=0.7)
                else:
                    ch = "(" if x == d.x0 - 1 else ")" if x == d.x1 else "_" if s > 0.3 else "~"
                    put(x, y, ch, mix(wc2, wc, 0.6 + 0.3 * s), level=0.8)

    def draw_drop(self, cv, d):
        t = self.t
        put = cv.put
        wc, wc2 = self.pal["water"], self.pal["water2"]
        h = self.h
        for k, x in enumerate(range(d.x0 - 1, d.x1 + 1)):
            if not (0 <= x < self.w):
                continue
            sp, ph, b = d.cols[min(k, len(d.cols) - 1)]
            edge = x < d.x0 or x >= d.x1
            ex = 0
            for y in range(d.y0 + 1, d.y1):
                dy = y - d.y0
                u = math.sqrt(dy + 1) * 3.2 - t * sp * 0.6 + ph
                f = u - math.floor(u)
                v = f ** 2.2 * b
                if edge:
                    # thin, broken edge sheets flaring slightly outward near the bottom
                    if f < 0.6:
                        continue
                    v *= 0.6
                    ex = (-1 if x < d.x0 else 1) * int(dy > (d.y1 - d.y0) * 0.75)
                else:
                    v = 0.3 + 0.7 * v
                if v > 0.6:
                    ch = "|"
                elif v > 0.38:
                    ch = "!" if (x + y) % 3 == 0 else "|"
                elif v > 0.22:
                    ch = ":"
                else:
                    ch = "." if (x * 7 + y) % 2 else "'"
                c = mix(wc2, wc, clamp(v * 1.3))
                put(x + ex, y, ch, scale(c, 0.55 + 0.45 * v), level=0.5 + 0.5 * v)
        # foam where it lands
        for x in range(d.x0 - 2, d.x1 + 2):
            for y in (d.y1 - 1, d.y1):
                if not (0 <= x < self.w and 0 <= y < h):
                    continue
                r = _hash(x, y, int(t * 14))
                if y == d.y1 - 1 and (x < d.x0 or x >= d.x1) and r < 0.5:
                    continue
                ch = "@" if r < 0.15 else "O" if r < 0.35 else "o" if r < 0.6 else "*" if r < 0.75 else "°"
                put(x, y, ch, mix(wc, (255, 255, 255), 0.4 * r), level=0.9)

    def draw_pool(self, cv):
        w, h, t = self.w, self.h, self.t
        pal = self.pal
        py = self.pool_y
        put = cv.put
        stops = pal["pool"]
        d = self.last
        wc = pal["water"]
        fx0, fx1 = d.x0, d.x1
        for y in range(py, h):
            f = (y - py) / max(1, h - py)
            col = gradient(stops, f)
            for x in range(w):
                if self.ground(x) < py - 0.2 and y < self.ground(x) + 1 + (h - py):
                    if y > self.ground(x) - 0.5:
                        continue
                s = math.sin(x * 0.45 + t * 1.3 + y * 1.7) + 0.6 * math.sin(x * 0.13 - t * 0.7 + y * 3.1)
                # bright reflection of the falling water
                refl = 1.0 if fx0 - 1 <= x <= fx1 else 0.0
                if refl and (s > -0.3):
                    put(x, y, "|" if s > 0.8 else ":" if s > 0.2 else ".", scale(mix(col, wc, 0.6 - 0.4 * f), 0.8), level=0.5)
                    continue
                if s > 0.7:
                    put(x, y, "~" if s > 1.1 else "-", scale(mix(col, wc, 0.25 * (1 - f)), 0.9 + 0.2 * s), level=0.3)
                elif (x + y * 3) % 4 == 0:
                    put(x, y, ".", scale(col, 0.7), level=0.15)
        # ripple rings: flat ellipses spreading from the impact
        for rx0, r, sp in self.ripples:
            a = clamp(1 - r / (w * 0.35))
            if a <= 0.05:
                continue
            ry = min(r * 0.1, (h - py) * 0.8)
            n = int(r * 2.2) + 6
            c = scale(mix(pal["pool"][0], wc, 0.7), 0.4 + 0.6 * a)
            for k in range(n):
                th = k / n * TAU
                cth, sth = math.cos(th), math.sin(th)
                x = rx0 + r * cth
                y = py + 0.5 + ry * (sth + 1)
                if y >= h or y < py or (k % 3 == 1 and a < 0.6):
                    continue
                ch = "-" if sth < 0 else "~"
                put(x, y, ch, c, level=0.6 * a)

    def draw_rainbow(self, cv):
        d = self.last
        cx = (d.x0 + d.x1) / 2
        cy = self.pool_y + 1
        R = self.rb_r
        put = cv.put
        lv = cv.lv
        w = self.w
        t = self.t
        shimmer = 0.75 + 0.25 * math.sin(t * 0.5)
        for y in range(max(0, int(cy - R / ASPECT) - 2), self.pool_y):
            dy = (y + 0.5 - cy) * ASPECT
            for x in range(max(0, int(cx - R * 1.15)), min(w, int(cx + R * 1.15) + 1)):
                if d.x0 - 1 <= x <= d.x1:
                    continue
                dist = math.hypot(x + 0.5 - cx, dy) / R
                if not 0.82 < dist < 1.0:
                    continue
                band = (dist - 0.82) / 0.18           # 0 violet .. 1 red
                ends = clamp((self.pool_y - y) / (R / ASPECT * 0.25)) * clamp(1.3 - abs(x - cx) / R)
                v = 0.35 * ends * shimmer
                i = y * w + x
                if v > 0.08 and lv[i] < 0.55:
                    put(x, y, ":" if v > 0.2 else ".", hsv(0.78 - 0.78 * band, 0.75, 1.0), level=v)

    def draw_mist(self, cv):
        put = cv.put
        wc = self.pal["water"]
        for x, y, vx, vy, age, life in self.mist:
            f = age / life
            a = (1 - f) * (0.5 + 0.5 * min(1.0, age * 4))
            if a < 0.08:
                continue
            ch = "o" if a > 0.75 and abs(vy) > 1.5 else "·" if a > 0.45 else "." if a > 0.25 else ","
            put(x, y, ch, scale(wc, 0.3 + 0.6 * a), level=0.4 * a)
        # a soft bank of mist hugging the pool around the impact
        d = self.last
        t = self.t
        py = self.pool_y
        mist = max(0.0, self.opt("mist"))
        if mist <= 0:
            return
        span = (d.x1 - d.x0) * 1.8 + 4
        cx = (d.x0 + d.x1) / 2
        for y in range(max(0, py - 4), py + 1):
            for x in range(max(0, int(cx - span)), min(self.w, int(cx + span) + 1)):
                n = noise2(x * 0.18 - t * 0.4 * (1 if x > cx else -1), y * 0.6 + t * 0.2, self.seed + 30)
                k = (1 - abs(x - cx) / span) * (1 - (py - y) / 5) * mist
                v = (n * 0.5 + 0.5) * k
                if v > 0.35 and cv.lv[y * self.w + x] < 0.6:
                    put(x, y, ":" if v > 0.55 else ".", scale(wc, 0.35 + 0.4 * v), level=v * 0.5)

    def draw_ferns(self, cv):
        put = cv.put
        t = self.t
        for bx, by, fronds, col in self.ferns:
            for a0, L, curl, ph in fronds:
                sway = 0.08 * math.sin(t * 1.1 + ph + bx * 0.1)
                x, y = bx, by
                n = int(L * 2)
                for k in range(n):
                    s = k / max(1, n)
                    a = a0 + curl * s * s + sway * s
                    dx = math.sin(a) * 0.5
                    dy = -math.cos(a) * 0.5 / ASPECT
                    x += dx
                    y += dy
                    if k % 2:
                        continue
                    ad = abs(math.cos(a))
                    if ad > 0.75:
                        ch = "|"
                    elif ad > 0.3:
                        ch = "/" if (dx > 0) == (dy < 0) else "\\"
                    else:
                        ch = "_" if dy > 0 else "~"
                    c = mix(col, (200, 240, 140), s * 0.5)
                    c = scale(c, 0.55 + 0.45 * self.pal["light"])
                    put(x, y, ch, c, level=0.7)
                    # leaflets either side of the spine
                    if 0.1 < s < 0.95 and ad > 0.3:
                        lc = scale(c, 0.85)
                        put(x - 1, y, "\\" if dy < 0 else "/", lc, level=0.6)
                        put(x + 1, y, "/" if dy < 0 else "\\", lc, level=0.6)
                    elif 0.1 < s < 0.95:
                        put(x, y - 1, "'" if k % 4 else ",", scale(c, 0.85), level=0.6)
