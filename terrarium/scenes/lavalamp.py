"""A lava lamp: glowing wax blobs rising, merging and sinking inside a glass vessel."""
import math

from ..engine import ASPECT, Scene, clamp, mix, noise1

SCHEMES = {
    #           deep wax          mid wax           hot rim           liquid           glow
    "classic": ((190, 25, 25), (255, 85, 25), (255, 210, 90), (110, 25, 70), (255, 120, 40)),
    "blue": ((25, 60, 200), (40, 150, 255), (170, 245, 255), (25, 25, 90), (70, 150, 255)),
    "green": ((20, 130, 50), (90, 230, 70), (225, 255, 150), (15, 60, 50), (120, 255, 100)),
    "purple": ((110, 30, 190), (210, 80, 255), (255, 190, 250), (45, 15, 80), (210, 100, 255)),
    "pink": ((200, 30, 110), (255, 90, 170), (255, 210, 230), (70, 20, 80), (255, 110, 180)),
}
CHROME = (185, 190, 205)
METALS = {"chrome": (185, 190, 205), "gold": (230, 190, 110), "copper": (215, 135, 95),
          "graphite": (120, 125, 140), "pearl": (235, 225, 235)}

S = 1.6                       # kernel support in blob radii
T = (1 - 1 / (S * S)) ** 2    # iso level: a lone blob's surface sits exactly at its radius


def _q(c):
    r, g, b = c
    r = 0 if r < 0 else 252 if r > 252 else int(r) & ~3
    g = 0 if g < 0 else 252 if g > 252 else int(g) & ~3
    b = 0 if b < 0 else 252 if b > 252 else int(b) & ~3
    return (r, g, b)


class Blob:
    __slots__ = ("x", "y", "vx", "vy", "r", "temp", "ph", "seed")


class LavaLamp(Scene):
    name = "lavalamp"
    title = "Lava Lamp"
    blurb = "glowing wax blobs rising, merging and sinking in a lava lamp"
    tags = ("retro", "calm", "cozy")
    interactions = "click to heat the wax and send up a fresh blob, point to warm it gently"
    options = {
        "lamp": (True, "draw the lamp (off = blobs fill the whole screen)"),
        "colors": ("random", "classic, blue, green, purple, pink or random"),
        "blobs": (0, "number of blobs (0 = random)"),
        "viscosity": (0.0, "how thick the wax is, 0.5 (runny) .. 2 (slow) (0 = random)"),
    }

    def _choose_style(self):
        """Roll this lamp's design and wax once; explicit -o options win."""
        rng = self.rng
        st = {}
        col = self.opt("colors")
        st["colors"] = col if col in SCHEMES else rng.choice(("classic", "classic", "blue", "green",
                                                               "purple", "pink"))
        st["metal"] = rng.choice(("chrome", "chrome", "gold", "copper", "graphite", "pearl"))
        # silhouette: glass share of the height, taper, where it bulges, cap and base shapes
        st["glass"] = rng.uniform(0.55, 0.66)
        st["cap"] = rng.uniform(0.07, 0.13)
        st["top_w"] = rng.uniform(0.26, 0.42)
        st["max_w"] = rng.uniform(0.70, 0.90)
        st["bulge"] = rng.uniform(0.65, 0.85)
        st["cap_top"] = rng.uniform(0.12, 0.3)
        st["base_top"] = rng.uniform(0.5, 0.65)
        st["base_bot"] = rng.uniform(0.85, 1.05)
        st["base_curve"] = rng.choice((0.6, 0.9, 1.4))
        st["rings"] = rng.choice(((0.18, 0.82), (0.5,), (0.15, 0.4, 0.85), ()))
        st["width"] = rng.uniform(0.18, 0.24)
        # wax behavior
        visc = self.opt("viscosity")
        st["visc"] = clamp(visc, 0.3, 3.0) if visc > 0 else rng.uniform(0.7, 1.6)
        st["lift"] = rng.uniform(0.12, 0.2)
        st["size"] = rng.uniform(0.28, 0.42)
        st["n"] = rng.choice((4, 5, 6, 6, 7, 8))
        self.style = st

    def setup(self):
        w, h = self.w, self.h
        if not hasattr(self, "style"):
            self._choose_style()
        st = self.style
        self.scheme = SCHEMES[st["colors"]]
        self.metal = METALS[st["metal"]]
        self.lamp = bool(self.opt("lamp"))
        if self.lamp:
            self._build_lamp()
        else:
            self.cx = w / 2.0
            self.gy0, self.gy1 = 0, h
            self.rows = {y: (0, w) for y in range(h)}
            self.hw = {y: w / 2.0 for y in range(h)}
            self.static = []
        gh = self.gy1 - self.gy0
        self.gh = gh
        rng = self.rng
        n = self.opt("blobs")
        if n <= 0:
            n = st["n"] if self.lamp else max(6, int(round(w * h / 520 * self.density * st["n"] / 6)))
        widest = max(self.hw.values()) if self.hw else w / 2
        base_r = widest * (st["size"] if self.lamp else st["size"] * 0.3)
        if not self.lamp:
            base_r = min(base_r, h * ASPECT * 0.14)
        self.blobs = []
        for k in range(n):
            b = Blob()
            b.r = max(1.6, base_r * rng.uniform(0.6, 1.1))
            b.y = rng.uniform(self.gy0 + gh * 0.1, self.gy1 - gh * 0.1)
            hw = self._hw(b.y)
            b.x = self.cx + rng.uniform(-1, 1) * max(0.0, hw - b.r)
            b.vx = 0.0
            b.vy = 0.0
            b.temp = rng.random()
            b.ph = rng.uniform(0, math.tau)
            b.seed = rng.uniform(0, 1000)
            self.blobs.append(b)
        self.n_base = len(self.blobs)   # blobs beyond this were added by clicks
        self.heat = []                  # [x, y, age]: warm flashes where the user clicked

    # ------------------------------------------------------------------ mouse
    def _inside(self, x, y):
        """Nearest point inside the glass to (x, y)."""
        if not self.rows:
            return self.cx, (self.gy0 + self.gy1) / 2.0
        ys = sorted(self.rows)
        yi = int(clamp(y if y == y else 0, ys[0], ys[-1]))
        if yi not in self.rows:
            yi = min(ys, key=lambda r: abs(r - yi))
        x0, x1 = self.rows[yi]
        return clamp(x if x == x else self.cx, x0 + 0.5, max(x0 + 0.5, x1 - 0.5)), yi + 0.5

    def on_click(self, x, y):
        x, y = self._inside(x, y)
        self.heat.append([x, y, 0.0])
        del self.heat[:-5]
        near = None
        best = 1e9
        for b in self.blobs:
            d = math.hypot(b.x - x, (b.y - y) * ASPECT) - b.r
            if d < best:
                near, best = b, d
        if near is not None and best < near.r * 0.6:
            near.temp = 1.0                 # clicked right on the wax: it melts and surges up
            near.vy = min(near.vy, 0.0) - self.gh * 0.12
            return
        rng = self.rng
        b = Blob()
        rs = [bb.r for bb in self.blobs[:self.n_base]] or [3.0]
        b.r = max(1.6, sum(rs) / len(rs) * rng.uniform(0.55, 0.8))
        b.x, b.y = x, y
        b.vx = 0.0
        b.vy = -self.gh * 0.06
        b.temp = 1.0
        b.ph = rng.uniform(0, math.tau)
        b.seed = rng.uniform(0, 1000)
        self.blobs.append(b)
        if len(self.blobs) > self.n_base + 4:     # keep the lamp from filling up
            extra = self.blobs[self.n_base:-1]
            self.blobs.remove(min(extra, key=lambda bb: bb.temp + (bb.y < self.gy1 - self.gh * 0.2)))

    # ------------------------------------------------------------------ lamp geometry
    def _build_lamp(self):
        w, h = self.w, self.h
        ht = h * 0.96
        top = (h - ht) / 2.0
        self.cx = cx = w / 2.0
        st = self.style
        wm = max(5.0, min(w * 0.30, ht * ASPECT * st["width"]))
        cap0, cap1 = top, top + ht * st["cap"]
        g0, g1 = cap1, cap1 + ht * st["glass"]
        b0, b1 = g1, top + ht
        tw, mw, bu = st["top_w"], st["max_w"], st["bulge"]
        bt, bb, bc = st["base_top"], st["base_bot"], st["base_curve"]
        ct = st["cap_top"]

        def glass_hw(yn):        # 0 top .. 1 bottom of the glass
            if yn < bu:
                return wm * (tw + (mw - tw) * (yn / bu) ** 1.15)
            u = (yn - bu) / (1 - bu)
            return wm * (mw - (mw - bt) * u * u)

        def cap_hw(yn):
            return wm * (ct + (tw + 0.02 - ct) * yn)

        def base_hw(yn):
            return wm * (bt + (bb - bt) * yn ** bc)

        self.gy0, self.gy1 = int(math.floor(g0)) + 1, int(math.floor(g1))
        sc = self.scheme
        glow = sc[4]
        metal = self.metal
        static = []          # (index, ch, color, level)
        occupied = set()
        rows, hws = {}, {}

        def put(x, y, ch, c, v):
            if 0 <= x < w and 0 <= y < h:
                i = y * w + x
                static.append((i, ch, _q(c), v))
                occupied.add(i)

        def profile(y):
            yc = y + 0.5
            if yc < cap0:
                return None, 0
            if yc < cap1:
                return "cap", cap_hw((yc - cap0) / (cap1 - cap0))
            if yc < g1:
                return "glass", glass_hw((yc - g0) / (g1 - g0))
            if yc < b1:
                return "base", base_hw((yc - b0) / (b1 - b0))
            return None, 0

        for y in range(h):
            part, hw = profile(y)
            if part is None:
                continue
            _, hw_up = profile(y - 1)
            _, hw_dn = profile(y + 1)
            xl = int(round(cx - hw))
            xr = int(round(cx + hw)) - 1
            if part == "glass":
                slope = (hw_dn or hw) - (hw_up or hw)
                if slope > 0.45:
                    lc, rc = "/", "\\"
                elif slope < -0.45:
                    lc, rc = "\\", "/"
                else:
                    lc, rc = "(", ")"
                yn = (y + 0.5 - g0) / (g1 - g0)
                ec = mix(mix(metal, glow, 0.45), (255, 255, 255), 0.25)
                put(xl, y, lc, ec, 0.7 + 0.2 * yn)
                put(xr, y, rc, ec, 0.7 + 0.2 * yn)
                rows[y] = (xl + 1, xr)
                hws[y] = hw
            else:
                # brushed metal: cylinder shading with a bright highlight band and warm bounce
                yn = (y + 0.5 - (cap0 if part == "cap" else b0)) / ((cap1 - cap0) if part == "cap" else (b1 - b0))
                for x in range(xl, xr + 1):
                    u = (x + 0.5 - cx) / max(1.0, hw)
                    body = math.sqrt(max(0.0, 1 - u * u))
                    hl = math.exp(-((u + 0.42) / 0.13) ** 2)
                    v = 0.12 + 0.36 * body + 0.5 * hl
                    warm = 0.35 if part == "base" and yn < 0.25 else 0.15
                    c = mix(metal, glow, warm * (1 - yn * 0.5))
                    c = mix(c, (255, 255, 255), hl * 0.5)
                    if part == "base" and any(abs(yn - rr) < 0.055 for rr in st["rings"]):
                        v *= 0.55                      # engraved rings
                    if x == xl or x == xr:
                        slope = (hw_dn or hw) - (hw_up or hw)
                        if slope > 0.3:
                            ch = "/" if x == xl else "\\"
                        elif slope < -0.3:
                            ch = "\\" if x == xl else "/"
                        else:
                            ch = "|"
                        put(x, y, ch, mix(c, (255, 255, 255), 0.2), max(0.55, v))
                    else:
                        put(x, y, None, c, clamp(v))
        # table surface and warm light pool
        floor = int(math.ceil(b1))
        if floor < h:
            for x in range(w):
                d = abs(x + 0.5 - cx) / (wm * 3.2)
                v = 0.5 * math.exp(-d * d * 2.0) + 0.08
                put(x, floor, "_", mix((60, 50, 60), glow, clamp(1.2 - d)), v)
        # the glass's first and last rows become the rims where it meets cap and base
        ytop, ybot = min(rows), max(rows)
        for yy in (ytop, ybot):
            xa, xb = rows.pop(yy)
            hws.pop(yy, None)
            for x in range(xa - 1, xb + 1):
                put(x, yy, "=", mix(metal, glow, 0.3), 0.75)
        self.gy0, self.gy1 = ytop + 1, ybot
        self.rows = rows
        self.hw = hws
        self.floor = floor
        # warm light falloff around the glass
        gcy = (g0 + g1) * 0.55
        halo = []
        for y in range(h):
            for x in range(w):
                i = y * w + x
                if i in occupied:
                    continue
                if y in rows and rows[y][0] <= x < rows[y][1]:
                    continue
                dx = (x + 0.5 - cx) / (wm * 1.3)
                dy = (y + 0.5 - gcy) * ASPECT / ((g1 - g0) * ASPECT * 0.75)
                d2 = dx * dx + dy * dy
                v = 0.22 / (1.0 + d2 * 2.2) - 0.035
                if y >= floor:
                    v *= 0.5
                if v > 0.05:
                    halo.append((i, None, _q(mix((40, 20, 30), glow, clamp(v * 4))), v))
        self.static = halo + static

    def _hw(self, y):
        yi = int(y)
        if yi in self.hw:
            return self.hw[yi]
        if not self.hw:
            return self.w / 2.0
        if yi < min(self.hw):
            return self.hw[min(self.hw)]
        return self.hw[max(self.hw)]

    # ------------------------------------------------------------------ physics
    def update(self, dt):
        super().update(dt)
        gy0, gy1, gh = self.gy0, self.gy1, max(1, self.gh)
        g = gh * self.style["lift"]
        visc = self.style["visc"]
        t = self.t
        for hs in self.heat:
            hs[2] += dt
        self.heat = [hs for hs in self.heat if hs[2] < 1.5]
        p = self.pointer
        for b in self.blobs:
            if p is not None:   # the pointer is a warm hand on the glass
                d = math.hypot(b.x - p[0], (b.y - p[1]) * ASPECT)
                if d < b.r * 2.2:
                    b.temp = min(1.0, b.temp + dt * 0.5 * (1.0 - d / (b.r * 2.2)))
            yn = (b.y - gy0) / gh            # 0 top .. 1 bottom
            if yn > 0.82:
                b.temp += dt * 0.22 * (yn - 0.75) * 4
            elif yn < 0.25:
                b.temp -= dt * 0.20 * (0.3 - yn) * 4
            else:
                b.temp -= dt * 0.015
            b.temp = clamp(b.temp, 0.0, 1.0)
            b.vy += -(b.temp - 0.5) * g * dt
            b.vy *= 1 - min(1.0, 1.4 * visc * dt)
            b.vx += (noise1(t * 0.2 + b.seed) * 1.6 + (self.cx - b.x) * 0.04) * dt
            b.vx *= 1 - min(1.0, 1.2 * dt)
            b.x += b.vx * dt
            b.y += b.vy * dt
            ry = b.r / ASPECT
            if b.y < gy0 + ry * 0.7:
                b.y = gy0 + ry * 0.7
                b.vy = abs(b.vy) * 0.2
                b.temp = min(b.temp, 0.3)
            if b.y > gy1 - ry * 0.4:
                b.y = gy1 - ry * 0.4
                b.vy = -abs(b.vy) * 0.2
            hw = self._hw(b.y)
            lim = max(0.0, hw - b.r * 1.3)
            if b.x < self.cx - lim:
                b.x = self.cx - lim
                b.vx = abs(b.vx) * 0.3
            elif b.x > self.cx + lim:
                b.x = self.cx + lim
                b.vx = -abs(b.vx) * 0.3

    # ------------------------------------------------------------------ drawing
    def draw(self, cv):
        W, H = cv.w, cv.h
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        ramp = cv.ramp
        nr = len(ramp) - 1
        for i, c, col, v in self.static:
            if i < cv.n:
                if c is None:
                    gi = int(v * nr + 0.5)
                    if gi <= 0:
                        continue
                    c = ramp[gi]
                ch[i] = c
                fg[i] = col
                lv[i] = v
        self.draw_lava(cv)
        self.draw_heat(cv)

    def draw_heat(self, cv):
        """Warm glows: a fading flash where the user clicked and a faint one under the pointer."""
        glow, hot = self.scheme[4], self.scheme[2]
        spots = [(x, y, 4.0 + a * 5.0, 0.55 * (1 - a / 1.5)) for x, y, a in self.heat]
        p = self.pointer
        if p is not None and int(p[1]) in self.rows:
            x0, x1 = self.rows[int(p[1])]
            if x0 <= p[0] < x1:
                spots.append((p[0], p[1], 2.5, 0.22))
        rows = self.rows
        for sx, sy, r, k in spots:
            for y in range(int(sy - r / ASPECT) - 1, int(sy + r / ASPECT) + 2):
                span = rows.get(y)
                if span is None:
                    continue
                for x in range(max(span[0], int(sx - r) - 1), min(span[1], int(sx + r) + 2)):
                    d = math.hypot(x + 0.5 - sx, (y + 0.5 - sy) * ASPECT) / r
                    if d < 1.0:
                        v = k * (1 - d * d)
                        cv.shade(x, y, v, mix(glow, hot, v), mode="max")

    def draw_lava(self, cv):
        W, H = cv.w, cv.h
        t = self.t
        rows = self.rows
        gy0, gy1, gh = self.gy0, self.gy1, max(1, self.gh)
        if not rows:
            return
        field = {}
        for y, (x0, x1) in rows.items():
            if 0 <= y < H:
                field[y] = [0.0] * (x1 - x0)
        # metaball kernel splats within each blob's support
        for b in self.blobs:
            wob = 1 + 0.07 * math.sin(t * 1.1 + b.ph)
            st = 1 + clamp(abs(b.vy) * 0.25, 0, 0.35)           # stretch along motion
            rx = b.r * wob / math.sqrt(st)
            ry = b.r * wob * st / ASPECT
            sx, sy = rx * S, ry * S
            ya, yb = max(gy0, int(b.y - sy)), min(gy1, int(b.y + sy) + 1)
            irx2 = 1.0 / (rx * rx * S * S)
            iry2 = 1.0 / (ry * ry * S * S)
            for y in range(ya, yb):
                row = field.get(y)
                if row is None:
                    continue
                x0, x1 = rows[y]
                dy2 = (y + 0.5 - b.y) ** 2 * iry2
                if dy2 >= 1:
                    continue
                xa, xb = max(x0, int(b.x - sx)), min(x1, int(b.x + sx) + 1)
                bx = b.x - 0.5
                for x in range(xa, xb):
                    q = (x - bx) ** 2 * irx2 + dy2
                    if q < 1:
                        k = 1 - q
                        row[x - x0] += k * k
        # wax pool resting on the bottom, gently heaving
        pool_h = max(1.2, gh * 0.07)
        surf = [gy1 - pool_h * (1 + 0.35 * math.sin(x * 0.35 + t * 0.6) + 0.2 * math.sin(x * 0.13 - t * 0.4))
                for x in range(W)]
        for y in range(max(gy0, int(gy1 - pool_h * 3)), gy1):
            row = field.get(y)
            if row is None:
                continue
            x0, x1 = rows[y]
            yc = y + 0.5
            for x in range(x0, min(x1, W)):
                g = (yc - surf[x]) / pool_h
                if g > -1.2:
                    row[x - x0] += T * (1 + g * 0.8)
        # shade
        deep, mid, hot, liquid, glow = self.scheme
        ramp = cv.ramp
        nr = len(ramp) - 1
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        cx = self.cx
        lamp = self.lamp
        for y, row in field.items():
            x0, x1 = rows[y]
            yn = clamp((y + 0.5 - gy0) / gh)
            up = field.get(y - 1)
            dn = field.get(y + 1)
            hw = max(1.0, (x1 - x0) / 2.0)
            bulb = 0.55 + 0.45 * yn * yn                 # light from the bulb in the base
            o = y * W
            for xi, f in enumerate(row):
                x = x0 + xi
                if f >= T:
                    fu = fd = 0.0
                    if up is not None:
                        j = x - rows[y - 1][0]
                        if 0 <= j < len(up):
                            fu = up[j]
                    if dn is not None:
                        j = x - rows[y + 1][0]
                        if 0 <= j < len(dn):
                            fd = dn[j]
                    depth = clamp((f - T) / 0.55)
                    rim = clamp(1 - (f - T) / 0.08)
                    lit = clamp(0.5 + (fu - fd) * 1.2)    # undersides catch the bulb light
                    under = rim * clamp((lit - 0.5) * 2.5)
                    v = 0.5 + 0.42 * depth + 0.12 * (lit - 0.5) + 0.25 * under
                    c = mix(deep, mid, clamp(0.25 + depth * 1.2))
                    c = mix(c, hot, clamp((depth - 0.6) * 1.6 + under * 0.9))
                    v = clamp(v, 0.25, 1.0)
                else:
                    halo = clamp((f - T * 0.35) / (T * 0.65))
                    u = (x + 0.5 - cx) / hw if lamp else 0.0
                    base = (0.075 + 0.12 * yn * yn) * (1 - 0.4 * u * u)
                    if lamp and -0.78 < u < -0.62:
                        base += 0.07                    # reflection streak on the glass
                    v = base + 0.42 * halo ** 1.6
                    if v < 0.055:
                        continue
                    c = mix(liquid, glow, clamp(halo * 0.9 + yn * 0.15))
                gi = int(v * nr + 0.5)
                if gi <= 0:
                    continue
                k = 0.3 + 0.7 * v if f < T else 0.6 + 0.4 * v
                i = o + x
                ch[i] = ramp[gi]
                fg[i] = _q((c[0] * k, c[1] * k, c[2] * k))
                lv[i] = v
