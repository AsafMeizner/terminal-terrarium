"""Sky lanterns released over a calm lake at night, glowing and mirrored in the water."""
import math

from ..engine import ASPECT, RAMPS, Scene, clamp, mix, noise1

TAU = math.tau
GLOW = " .·:;+*#%@"
WATER = " .-~~=+*#"

# paper colours: (top of the lantern, bottom by the flame)
LANTERN_SETS = {
    "amber": [((225, 85, 25), (255, 185, 60)), ((235, 105, 30), (255, 200, 80)), ((215, 70, 20), (255, 170, 55))],
    "rose": [((215, 45, 55), (255, 150, 90)), ((225, 70, 80), (255, 175, 110)), ((230, 95, 40), (255, 190, 90))],
    "gold": [((235, 135, 30), (255, 220, 110)), ((225, 115, 25), (255, 210, 95)), ((240, 150, 45), (255, 230, 140))],
    "festival": [((220, 50, 40), (255, 170, 80)), ((235, 130, 20), (255, 215, 100)), ((200, 50, 120), (255, 160, 150)),
                 ((225, 95, 30), (255, 195, 85))],
}


def _q(r, g, b):
    return (0 if r < 0 else 252 if r > 252 else int(r) & ~3,
            0 if g < 0 else 252 if g > 252 else int(g) & ~3,
            0 if b < 0 else 252 if b > 252 else int(b) & ~3)


class Lantern:
    __slots__ = ("x", "y", "z", "rise", "sway", "phase", "seed", "top", "bot", "shape", "ribs", "age")

    def __init__(self, rng, x, y, z, colors):
        self.x, self.y, self.z = x, y, z
        self.rise = rng.uniform(0.8, 1.2)
        self.sway = rng.uniform(0.3, 1.0)
        self.phase = rng.uniform(0, TAU)
        self.seed = rng.randrange(1000)
        self.top, self.bot = rng.choice(colors)
        self.shape = rng.uniform(0.6, 0.85)        # bottom width / top width
        self.ribs = rng.choice((0, 2, 3))
        self.age = 0.0


class Lanterns(Scene):
    name = "lanterns"
    title = "Sky Lanterns"
    blurb = "paper sky lanterns rising over a calm lake at night, glowing in the water"
    tags = ("night", "calm", "cozy", "water", "celebration")
    options = {
        "count": (0, "number of lanterns (0 = based on screen size)"),
        "wind": ("random", "breeze from -2 (left) to 2 (right), or random"),
        "colors": ("random", "random, amber, rose, gold or festival"),
        "moon": (True, "show the moon"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        wind = self.opt("wind")
        try:
            self.wind = clamp(float(wind), -3.0, 3.0)
        except (TypeError, ValueError):
            self.wind = rng.uniform(-1.0, 1.0)
        cs = self.opt("colors")
        if cs not in LANTERN_SETS:
            cs = rng.choice(("amber", "amber", "gold", "rose", "festival"))
        self.colors = LANTERN_SETS[cs]
        self.hz = max(4, min(h - 3, int(h * rng.uniform(0.6, 0.7))))
        hz = self.hz
        self.mk = max(1.0, min(2.4, (hz * 0.8) / max(1, h - hz)))
        self.big = max(2.5, min(9.0, w * rng.uniform(0.045, 0.06)))   # nearest lantern width (cells)
        n = self.opt("count") or max(6, min(70, int(round((10 + w * h / 160) * self.density))))
        self.n = n
        self.lanterns = []
        for k in range(n):
            z = rng.random() ** 1.6 * 0.95 + 0.05
            y = rng.uniform(-2, hz + (h - hz) * z)
            self.lanterns.append(Lantern(rng, rng.uniform(0, w), y, z, self.colors))
        self.lanterns.sort(key=lambda L: L.z)
        # sky
        ns = int(w * hz / 30 * self.density)
        self.stars = [(rng.randrange(w), rng.randrange(hz), rng.uniform(0.15, 0.7) ** 1.4, rng.uniform(0, TAU),
                       rng.uniform(0.5, 2.0)) for _ in range(ns)]
        self.show_moon = bool(self.opt("moon")) and rng.random() < 0.85
        self.moon_r = max(2.0, h * rng.uniform(0.075, 0.105) * ASPECT)
        self.moon_x = rng.uniform(0.12, 0.88) * w
        self.moon_y = rng.uniform(0.12, 0.3) * hz + self.moon_r / ASPECT
        self.phase = rng.choice((0.0, rng.uniform(0.25, 0.6), rng.uniform(-0.6, -0.25)))  # 0 = full
        self.moon_col = rng.choice(((255, 245, 220), (235, 240, 255), (255, 230, 190)))
        self.sky_tint = rng.choice(((40, 30, 70), (20, 35, 75), (55, 30, 60)))
        # far shore: one or two ranges of hills, a few village lights
        self.ridges = []
        seed = rng.randrange(1000)
        layers = rng.choice((1, 2, 2))
        for k in range(layers):
            f = k / max(1, layers - 1) if layers > 1 else 1.0
            amp = hz * rng.uniform(0.08, 0.2) * (1.0 - 0.4 * f)
            fq = rng.uniform(0.015, 0.04) * max(0.6, 100.0 / max(40, w))
            ridge = []
            for x in range(w):
                y = hz - 0.5 - amp * (0.55 + 0.45 * noise1(x * fq, seed + k * 7)) * (0.7 + 0.3 * noise1(x * fq * 3, seed + k * 7 + 1))
                ridge.append(y)
            col = (22, 20, 36) if k == layers - 1 else (32, 28, 50)
            self.ridges.append((ridge, col))
        self.ridges.reverse()  # far first
        self.village = [(rng.randrange(w), rng.choice(((255, 200, 120), (255, 180, 90), (255, 230, 170))))
                        for _ in range(int(w / 10 * rng.uniform(0.2, 1.0)))]
        # foreground: people on the near bank releasing lanterns
        self.people = []
        self.bank = []
        if h >= 16 and rng.random() < 0.85:
            bx0 = rng.choice((0, int(w * rng.uniform(0.0, 0.4))))
            bx1 = min(w, bx0 + int(w * rng.uniform(0.35, 0.8)))
            self.bank = (bx0, bx1)
            x = bx0 + rng.randint(2, 5)
            while x < bx1 - 3:
                kind = rng.choice(("adult", "adult", "child", "arms"))
                self.people.append((x, kind))
                x += rng.randint(3, 8)
        self.spawn_t = 0.0

    def respawn(self, L):
        rng = self.rng
        w, h, hz = self.w, self.h, self.hz
        z = rng.random() ** 1.6 * 0.95 + 0.05
        if self.people and rng.random() < 0.3:
            px, kind = rng.choice(self.people)
            nl = Lantern(rng, px, h - 3, rng.uniform(0.75, 1.0), self.colors)
        elif z > 0.55:
            nl = Lantern(rng, rng.uniform(0, w), h + 2 + self.big * z / ASPECT, z, self.colors)
        else:
            nl = Lantern(rng, rng.uniform(0, w), hz - 0.5 - z * 3, z, self.colors)
        return nl

    def update(self, dt):
        super().update(dt)
        t = self.t
        w = self.w
        out = []
        for k, L in enumerate(self.lanterns):
            L.age += dt
            sp = (0.35 + 1.1 * L.z) * L.rise
            L.y -= sp * dt
            L.x += (self.wind * (0.25 + 0.9 * L.z) + L.sway * 0.4 * math.sin(t * 0.35 + L.phase)) * dt
            L.z = max(0.04, L.z - dt * 0.004)          # drifting further away as it climbs
            size = self.big * L.z
            if L.y < -size / ASPECT * 1.5 - 1 or L.x < -size * 2 - 2 or L.x > w + size * 2 + 2:
                out.append(k)
        for k in out:
            self.lanterns[k] = self.respawn(self.lanterns[k])
        if out:
            self.lanterns.sort(key=lambda L: L.z)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, hz = self.w, self.h, self.hz
        if (cv.w, cv.h) != (w, h):
            return
        t = self.t
        n = w * hz
        R = [0.0] * n
        G = [0.0] * n
        B = [0.0] * n
        exp = math.exp
        # faint sky glow near the horizon
        st = self.sky_tint
        for y in range(max(0, hz - int(hz * 0.35)), hz):
            g = ((y - (hz - hz * 0.35)) / (hz * 0.35)) ** 2 * 0.22
            row = y * w
            for x in range(w):
                if (x * 7 + y * 3) % 3 == 0:
                    R[row + x] += st[0] * g * 1.6
                    G[row + x] += st[1] * g * 1.6
                    B[row + x] += st[2] * g * 1.6
        # moon and its halo
        if self.show_moon:
            mx, my, mr = self.moon_x, self.moon_y, self.moon_r
            mc = self.moon_col
            hr = mr * 4.0
            ph = self.phase
            for yy in range(max(0, int(my - hr / ASPECT)), min(hz, int(my + hr / ASPECT) + 1)):
                dy = (yy - my) * ASPECT
                row = yy * w
                for xx in range(max(0, int(mx - hr)), min(w, int(mx + hr) + 1)):
                    dx = xx - mx
                    d = math.sqrt(dx * dx + dy * dy) / mr
                    if d < 1.0:
                        lit = 1.0
                        if ph:
                            # shadow disc offset sideways carves the crescent
                            sd = math.sqrt((dx / mr - ph * 2.0) ** 2 + (dy / mr) ** 2)
                            lit = clamp((sd - 0.95) * 4.0) * 0.92 + 0.08
                        mare = 0.85 + 0.15 * noise1(xx * 0.9 + yy * 1.7, 3)
                        v = (0.75 + 0.25 * (1 - d * d)) * lit * mare
                        R[row + xx] += mc[0] * v * 1.2
                        G[row + xx] += mc[1] * v * 1.2
                        B[row + xx] += mc[2] * v * 1.2
                    elif d < 4.0:
                        v = 0.2 / (1.0 + (d - 1.0) * (d - 1.0) * 4.0) * (1.0 - abs(ph) * 0.6)
                        R[row + xx] += mc[0] * v
                        G[row + xx] += mc[1] * v
                        B[row + xx] += mc[2] * v
        # lantern light: halos and bodies
        bodies = []
        big = self.big
        for L in self.lanterns:
            fl = 0.82 + 0.18 * noise1(t * 2.3 + L.seed, L.seed)
            Wd = big * L.z
            dim = 0.45 + 0.55 * min(1.0, L.z * 2.2)
            if Wd < 1.6:
                bodies.append((L, fl * dim, None))
                hr = 2.2 + Wd * 1.5
            else:
                bodies.append((L, fl * dim, Wd))
                hr = Wd * 2.2
            cx, cy = L.x, L.y
            hy = hr / ASPECT
            col = L.bot
            k0 = 0.5 * fl * dim
            iy0, iy1 = max(0, int(cy - hy)), min(hz, int(cy + hy) + 1)
            ix0, ix1 = max(0, int(cx - hr)), min(w, int(cx + hr) + 1)
            inv = 1.0 / (hr * hr * 0.3)
            for yy in range(iy0, iy1):
                dy = (yy + 0.5 - cy) * ASPECT
                row = yy * w
                for xx in range(ix0, ix1):
                    dx = xx + 0.5 - cx
                    q = (dx * dx + dy * dy) * inv
                    if q < 3.3:
                        a = (1.0 / (1.0 + q * 4.0) - 0.06) * k0
                        if a > 0:
                            i = row + xx
                            R[i] += col[0] * a
                            G[i] += col[1] * a
                            B[i] += col[2] * a
            # the body itself also lights the buffer (so it is mirrored in the water)
            if Wd is not None:
                rows = max(2, int(round(Wd * 1.45 / ASPECT)))
                y0 = int(cy - rows / 2)
                for r in range(rows):
                    yy = y0 + r
                    if 0 <= yy < hz:
                        f = r / max(1, rows - 1)
                        hw = Wd * (1.0 - (1.0 - L.shape) * f) / 2 * 0.7
                        c = mix(L.top, L.bot, f ** 1.3)
                        v = (0.45 + 0.5 * f) * fl * dim
                        for xx in range(max(0, int(cx - hw)), min(w, int(cx + hw) + 1)):
                            i = yy * w + xx
                            R[i] += c[0] * v
                            G[i] += c[1] * v
                            B[i] += c[2] * v
            else:
                xx, yy = int(cx), int(cy)
                if 0 <= xx < w and 0 <= yy < hz:
                    i = yy * w + xx
                    v = fl * dim * 1.1
                    R[i] += col[0] * v
                    G[i] += col[1] * v
                    B[i] += col[2] * v
        # ---- tone map the sky
        ramp = GLOW if cv.ramp == RAMPS["ascii"] else cv.ramp
        rn = len(ramp) - 1
        ch, fgc, lv = cv.ch, cv.fg, cv.lv
        for i in range(n):
            r, g, b = R[i], G[i], B[i]
            m = r if r > g else g
            if b > m:
                m = b
            if m < 5.0:
                continue
            L_ = m / 255.0
            v = 1.0 - exp(-L_ * 1.3)
            if v < 0.12:
                continue
            gi = int(v * rn + 0.5)
            if gi <= 0:
                continue
            k = (0.25 + 0.75 * v) * 255.0 / m
            ch[i] = ramp[gi]
            fgc[i] = _q(r * k, g * k, b * k)
            lv[i] = v
        # stars where the sky is dark
        for sx, sy, b, ph, rate in self.stars:
            i = sy * w + sx
            if lv[i] > 0.04:
                continue
            v = b * (0.55 + 0.45 * math.sin(t * rate + ph))
            if v < 0.08:
                continue
            ch[i] = "." if v < 0.3 else "·" if v < 0.45 else "+" if v < 0.6 else "*"
            fgc[i] = _q(170 * v + 40, 175 * v + 40, 210 * v + 50)
            lv[i] = v
        if self.show_moon:
            self.draw_moon(cv)
        # ---- far hills (drawn behind brighter glows)
        for ridge, col in self.ridges:
            cq = _q(*col)
            for x in range(w):
                top = ridge[x]
                ty = int(top)
                for y in range(max(0, ty), hz):
                    i = y * w + x
                    if lv[i] > 0.2:
                        continue
                    ch[i] = ("▄" if top - ty >= 0.5 else "█") if y == ty else "█"
                    fgc[i] = cq
                    lv[i] = 0.1
        for x, c in self.village:
            i = (hz - 1) * w + x
            if lv[i] <= 0.2:
                ch[i] = "." if (x + int(t * 0.5)) % 7 else ","
                fgc[i] = _q(*c)
        # ---- water
        self.draw_water(cv, R, G, B)
        # ---- crisp lantern bodies on top
        for L, br, Wd in bodies:
            self.draw_lantern(cv, L, br, Wd)
        # ---- near bank and people
        self.draw_shore(cv)

    def draw_moon(self, cv):
        w, hz = self.w, self.hz
        mx, my, mr = self.moon_x, self.moon_y, self.moon_r
        mc = self.moon_col
        ph = self.phase
        ch, fgc, lv = cv.ch, cv.fg, cv.lv
        for yy in range(max(0, int(my - mr / ASPECT) - 1), min(hz, int(my + mr / ASPECT) + 2)):
            dy = (yy + 0.5 - my) * ASPECT
            for xx in range(max(0, int(mx - mr) - 1), min(w, int(mx + mr) + 2)):
                dx = xx + 0.5 - mx
                d = math.sqrt(dx * dx + dy * dy) / mr
                if d >= 1.0:
                    continue
                lit = 1.0
                if ph:
                    sd = math.sqrt((dx / mr - ph * 2.0) ** 2 + (dy / mr) ** 2)
                    lit = clamp((sd - 0.95) * 3.0)
                if lit <= 0.05:
                    continue
                mare = 0.9 - 0.12 * max(0.0, noise1(xx * 0.25 + yy * 0.6, 3))
                v = (0.7 + 0.3 * (1.0 - d * d)) * lit * mare
                i = yy * w + xx
                ch[i] = "█" if d < 0.86 and lit > 0.55 else "▓" if lit > 0.25 else "▒"
                fgc[i] = _q(mc[0] * v, mc[1] * v, mc[2] * v)
                lv[i] = v

    def draw_water(self, cv, R, G, B):
        w, h, hz, t = self.w, self.h, self.hz, self.t
        ch, fgc, lv = cv.ch, cv.fg, cv.lv
        wn = len(WATER) - 1
        depth = max(1, h - hz)
        mk = self.mk
        sin, exp = math.sin, math.exp
        rows = {}
        rad = 1
        win = 1.0 / (2 * rad + 1)

        def blurred(ym):
            r = rows.get(ym)
            if r is None:
                base = ym * w
                pr, pg, pb = [0.0], [0.0], [0.0]
                for x in range(w):
                    pr.append(pr[-1] + R[base + x])
                    pg.append(pg[-1] + G[base + x])
                    pb.append(pb[-1] + B[base + x])
                out = ([], [], [])
                for x in range(w):
                    a, b = max(0, x - rad), min(w, x + rad + 1)
                    out[0].append((pr[b] - pr[a]) * win)
                    out[1].append((pg[b] - pg[a]) * win)
                    out[2].append((pb[b] - pb[a]) * win)
                rows[ym] = out
                r = out
            return r

        mx = self.moon_x if self.show_moon else -999
        for y in range(hz, h):
            d = y - hz
            fade = 1.0 - 0.45 * d / depth
            wob = sin(y * 1.7 + t * 0.9) * (0.3 + d * 0.08) + noise1(y * 0.6 + t * 0.3, 9) * (0.3 + d * 0.1)
            ym0 = max(0, int(hz - 1 - d * mk))
            ym1 = max(0, ym0 - 1)
            r0, g0, b0 = blurred(ym0)
            r1, g1, b1 = blurred(ym1)
            row = y * w
            gl = 1.5 + d * 0.5          # moon glitter path widens towards the viewer
            for x in range(w):
                i = row + x
                sx = int(x + wob + 0.4 * sin(x * 0.19 + y * 1.1 + t * 1.1))
                if 0 <= sx < w:
                    r, g, b = r0[sx], g0[sx], b0[sx]
                    if r1[sx] + g1[sx] + b1[sx] > r + g + b:
                        r, g, b = r1[sx] * 0.9, g1[sx] * 0.9, b1[sx] * 0.9
                    m = r if r > g else g
                    if b > m:
                        m = b
                    if m > 6.0:
                        br = 0.7 + 0.4 * sin(x * 0.3 + y * 2.1 - t * 1.2) * sin(x * 0.05 - t * 0.4 + y * 0.8)
                        v = (1.0 - exp(-m / 255.0 * 1.8)) * fade * br
                        if v > 1.0:
                            v = 1.0
                        gi = int(v * wn + 0.5)
                        if gi > 0:
                            k = (0.25 + 0.75 * v) * 255.0 / m
                            ch[i] = WATER[gi]
                            fgc[i] = _q(r * k, g * k, b * k)
                            lv[i] = v
                            continue
                dxm = abs(x - mx)
                if dxm < gl:
                    s = sin(x * 1.3 + y * 3.1 - t * 2.4) + sin(x * 0.4 - y * 1.7 + t * 1.5)
                    if s > 0.9:
                        v = (1.0 - dxm / gl) * (0.25 + 0.3 * (s - 0.9)) * (1.0 - abs(self.phase) * 0.5)
                        c = self.moon_col
                        ch[i] = "-" if s < 1.4 else "~"
                        fgc[i] = _q(c[0] * v, c[1] * v, c[2] * v)
                        lv[i] = v
                        continue
                if (x * 5 + y * 11 + int(t + x * 0.03)) % 11 == 0:
                    ch[i] = "-"
                    fgc[i] = (24, 28, 52)
                    lv[i] = 0.04

    def draw_lantern(self, cv, L, br, Wd):
        w = self.w
        ch, fgc, lv = cv.ch, cv.fg, cv.lv
        cx, cy = L.x, L.y
        if Wd is None:
            xx, yy = int(cx), int(cy)
            if 0 <= xx < w and 0 <= yy < cv.h:
                c = mix(L.top, L.bot, 0.75)
                g = "·" if L.z < 0.07 else "o" if L.z < 0.12 else "0"
                k = 0.45 + 0.55 * min(1.0, br)
                i = yy * w + xx
                ch[i] = g
                fgc[i] = _q(c[0] * k, c[1] * k, c[2] * k)
                lv[i] = br
            return
        rows = max(2, int(round(Wd * 1.45 / ASPECT)))
        y0 = int(cy - rows / 2)
        hot = (255, 238, 170)
        for r in range(rows):
            yy = y0 + r
            if not (0 <= yy < cv.h):
                continue
            f = r / max(1, rows - 1)
            prof = 1.0 - (1.0 - L.shape) * f          # tapering towards the open bottom
            if r == 0:
                prof *= 0.86                          # rounded crown
            hw = Wd * prof / 2
            xa, xb = int(round(cx - hw)), int(round(cx + hw)) - 1
            if xb < xa:
                xb = xa
            c = mix(L.top, L.bot, f ** 1.2)
            for xx in range(max(0, xa), min(w, xb + 1)):
                i = yy * w + xx
                u = (xx + 0.5 - cx) / (hw + 1e-6)            # -1 .. 1 across the paper
                v = (0.62 + 0.45 * f) * br * (1.0 - 0.3 * u * u)
                cc = c
                if L.ribs and 0 < r < rows - 1 and xa < xx < xb and (xx - xa) % (L.ribs + 1) == 0:
                    v *= 0.8
                glow = max(0.0, f - 0.45) * (1.0 - abs(u)) * 1.6     # the flame lights the lower paper
                if glow > 0:
                    cc = mix(c, hot, min(1.0, glow) * br)
                g = "█"
                if r == 0:
                    g = "▄"
                elif r == rows - 1 and rows > 2:
                    g = "▀"
                k = 0.3 + 0.7 * min(1.0, v)
                ch[i] = g
                fgc[i] = _q(cc[0] * k, cc[1] * k, cc[2] * k)
                lv[i] = min(1.0, v)
        # the flame peeking out of the open bottom
        fy = y0 + rows
        fx = int(cx)
        if 0 <= fy < cv.h and 0 <= fx < w:
            i = fy * w + fx
            flick = 0.7 + 0.3 * math.sin(self.t * 13.0 + L.seed)
            ch[i] = "'" if flick < 0.9 else "*"
            fgc[i] = _q(255 * flick, 210 * flick, 120 * flick)
            lv[i] = 1.0

    def draw_shore(self, cv):
        if not self.bank:
            return
        w, h = self.w, self.h
        ch, fgc, lv = cv.ch, cv.fg, cv.lv
        bx0, bx1 = self.bank
        dark = (22, 15, 18)
        rim = (52, 32, 26)
        # the bank: a low mound at the bottom edge
        for x in range(max(0, bx0 - 2), min(w, bx1 + 2)):
            edge = min(x - bx0 + 2, bx1 + 2 - x)
            top = h - 1 if edge < 3 else h - 2
            for y in range(top, h):
                i = y * w + x
                ch[i] = "▄" if (y == top and edge < 2) else "█"
                fgc[i] = rim if y == top else dark
                lv[i] = 1.0
            if (x * 7) % 5 == 0 and top - 1 >= 0:
                i = (top - 1) * w + x
                ch[i] = "," if x % 2 else "'"
                fgc[i] = rim
        sprites = {
            "adult": [" ▄ ", "▐█▌", "▐█▌", "▐ ▌"],
            "child": [" ▄ ", "▐█▌", " ▌▐"],
            "arms": ["▌▄▐", "▐█▌", "▐█▌", "▐ ▌"],
        }
        for x, kind in self.people:
            rows = sprites[kind]
            base = h - 2
            for k, line in enumerate(reversed(rows)):
                yy = base - 1 - k
                off = len(line) // 2
                for j, c in enumerate(line):
                    xx = x - off + j
                    if c != " " and 0 <= xx < w and 0 <= yy < h:
                        i = yy * w + xx
                        ch[i] = c
                        fgc[i] = rim if k >= len(rows) - 2 else dark
                        lv[i] = 1.0


def scale_(c, k):
    return (c[0] * k, c[1] * k, c[2] * k)
