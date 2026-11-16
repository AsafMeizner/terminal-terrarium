"""Snow falling softly over moonlit hills and a cabin with a warm window."""
import math

from ..engine import ASPECT, Canvas, Scene, clamp, gradient, mix, noise1, scale

# moods: (sky stops, far / mid / near snow tint)
MOODS = [
    ([(6, 10, 28), (12, 20, 50), (24, 38, 80), (40, 60, 110)], [(80, 110, 190), (135, 170, 240), (200, 225, 255)]),
    ([(14, 8, 34), (34, 20, 70), (70, 40, 100), (120, 70, 120)], [(110, 90, 170), (170, 150, 230), (225, 215, 255)]),
    ([(4, 14, 24), (8, 30, 48), (16, 56, 72), (40, 90, 100)], [(70, 120, 150), (130, 190, 210), (200, 240, 250)]),
    ([(10, 10, 30), (30, 30, 70), (90, 60, 100), (170, 110, 110)], [(110, 100, 160), (190, 170, 210), (245, 225, 235)]),
]
WARM = (255, 170, 80)
SNOW = ".:'.,:.`.:"  # glyphs for the snowfield texture


class Snow(Scene):
    name = "snow"
    title = "Snow"
    blurb = "snow falling softly over moonlit hills and a cabin with a warm window"
    tags = ("night", "weather", "calm", "winter", "cozy")
    interactions = "point to breathe the snowflakes away, click to throw a snowball"
    options = {
        "amount": (1.0, "how much snow falls (0.2 .. 3)"),
        "wind": ("random", "sideways drift, -1 .. 1 (or random)"),
        "cabin": (True, "a cabin with a glowing window and chimney smoke"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        # three snowy hills, far to near: ridge row per column
        self.hills = []
        self.sky, tints = rng.choice(MOODS)
        try:
            self.wind = clamp(float(self.opt("wind")), -1.5, 1.5)
        except ValueError:
            self.wind = rng.choice((-1, 1)) * rng.uniform(0.0, 0.5)
        lift = rng.uniform(-0.08, 0.06)            # big open sky .. hills crowding the frame
        rough = rng.uniform(0.6, 1.6)              # rolling downs .. steep fells
        specs = [(0.52 + lift, 0.08 * rough, 0.020 * rng.uniform(0.6, 1.6), tints[0]),
                 (0.65 + lift * 0.6, 0.07 * rough, 0.03 * rng.uniform(0.6, 1.6), tints[1]),
                 (0.80 + lift * 0.3, 0.06 * rough, 0.045 * rng.uniform(0.6, 1.6), tints[2])]
        for base, amp, freq, col in specs:
            seed = rng.randrange(1, 9999)
            ridge = []
            for x in range(w + 1):
                u = x * freq * 110 / max(60, w)
                ridge.append(h * base - h * amp * (noise1(u, seed) * 1.6 + noise1(u * 2.7, seed + 1) * 0.4))
            self.hills.append((ridge, col))
        left = rng.random() < 0.5
        mxf = rng.uniform(0.1, 0.32)
        self.moon = (w * (mxf if left else 1 - mxf), h * rng.uniform(0.1, 0.25),
                     max(2.2, min(w, h * ASPECT) * rng.uniform(0.035, 0.06)))
        self.stars = [(rng.randrange(w), rng.randrange(max(1, int(h * 0.5))), rng.uniform(0.2, 1.0), rng.uniform(0, 6.3))
                      for _ in range(int(w * h / 70 * self.density))]
        # trees: (x, base row, height, layer)
        self.trees = []
        forest = rng.uniform(0.2, 1.5)             # bare hills .. dense woods
        tree_h = rng.uniform(0.8, 1.3)
        self.tree_w = rng.uniform(0.75, 1.3)       # slim spruces .. broad firs
        clump = rng.uniform(0, 1)                  # trees scattered evenly or in groves
        groves = [rng.uniform(0, w) for _ in range(rng.randint(1, 3))]
        for layer in (0, 1, 2):
            ridge = self.hills[layer][0]
            n = int(w / (12 - layer * 1.5) * rng.uniform(0.5, 0.9)) if layer < 2 else int(w / 28 * rng.uniform(0.6, 1.2))
            for _ in range(int(n * forest)):
                x = rng.uniform(0, w) if rng.random() > clump else rng.choice(groves) + rng.gauss(0, w * 0.06)
                th = rng.uniform(2.5, 4.5) * (1 + layer * 0.5) * h / 34 * tree_h
                self.trees.append((x, ridge[int(clamp(x, 0, w))] + 0.6, max(2.0, th), layer))
        self.trees.sort(key=lambda t: t[3])
        # cabin on the middle hill
        self.cabin = None
        self.chimney = None
        if self.opt("cabin") and w >= 30 and h >= 12:
            cw = max(9, int(min(w * 0.13, h * 0.5) * rng.uniform(0.8, 1.25)))
            ch = max(3, int(cw * 0.32))
            cx = int(w * (rng.uniform(0.5, 0.72) if left else rng.uniform(0.12, 0.38)))
            ridge = self.hills[1][0]
            base = int(max(ridge[int(clamp(x, 0, w))] for x in range(cx, cx + cw))) + 1
            self.cabin = (cx, base, cw, ch)
            rh = max(2, int(cw * 0.3))
            self.chimney = (cx + int(cw * 0.72) + 1.0, base - ch - rh - 1)
            self.trees = [t for t in self.trees if not (t[3] >= 1 and cx - 4 < t[0] < cx + cw + 4)]
        # flakes: [x, y, depth, phase, push vx, push vy]
        n = int(w * h / 9 * self.opt("amount") * self.density)
        self.flakes = [[rng.uniform(0, w), rng.uniform(0, h), rng.random() ** 1.3, rng.uniform(0, 6.3), 0.0, 0.0]
                       for _ in range(max(5, n))]
        self.balls = []                 # snowballs in flight: [x0, y0, x1, y1, age, flight time]
        self.puffs = []                 # burst snow: [x, y, vx, vy, age, life]
        self.poofs = []                 # the white cloud where a snowball burst: [x, y, age]
        self.acc = [0.0] * w            # snow piling up on the near hill
        self.smoke = []                 # [x, y, age]
        self.smoke_t = 0.0
        self._bgkey = None

    # ------------------------------------------------------------------ static layer
    def paint_static(self, b):
        w, h = self.w, self.h
        mx, my, mr = self.moon
        # sky
        for y in range(h):
            g = y / max(1, h - 1)
            col = gradient(self.sky, g)
            for x in range(w):
                dx = x + 0.5 - mx
                dy = (y + 0.5 - my) * ASPECT
                d = math.sqrt(dx * dx + dy * dy)
                glow = 0.5 * math.exp(-max(0.0, d - mr) / (mr * 1.3))
                v = 0.04 + 0.12 * g + glow
                if d < mr:
                    crater = noise1(x * 0.9 + y * 2.1, 4) > 0.35
                    b.put(x, y, "%" if crater or d > mr - 0.7 else "@",
                          (215, 215, 200) if crater else (250, 248, 232), level=0.95)
                elif glow > 0.07 and (x + y) % 2 == 0 or glow > 0.2:
                    c = mix(col, (190, 205, 240), min(1.0, glow * 1.6))
                    b.put(x, y, ":" if glow > 0.25 else ".", scale(c, 0.35 + glow * 1.3), level=0.05)
                elif (x * 7 + y * 3) % 5 == 0 and g > 0.25:
                    b.put(x, y, ".", scale(col, 0.9 + g), level=0.05)
        # hills, lit from the moon's side
        cab = self.cabin
        if cab:
            wx, wy = cab[0] + cab[2] * 0.3, cab[1] - cab[3] * 0.5
        for k, (ridge, col) in enumerate(self.hills):
            for x in range(w):
                top = ridge[x]
                slope = ridge[min(w, x + 1)] - ridge[max(0, x - 1)]
                lit = clamp(0.75 + slope * (0.6 if mx < x else -0.6))
                for y in range(max(0, int(top)), h):
                    d = y - top
                    tex = noise1(x * 0.5 + y * 1.3, 11 + k)
                    v = (0.45 + 0.15 * k) * lit * (1 - 0.45 * min(1.0, d / (h * 0.22))) + tex * 0.08
                    c = col
                    if cab and k >= 1:  # warm light from the window spilling over the snow
                        ddx = (x - wx)
                        ddy = (y - wy) * ASPECT
                        wl = math.exp(-(ddx * ddx + ddy * ddy) / (cab[2] * cab[2] * 1.2))
                        if wl > 0.03:
                            c = mix(col, WARM, wl * 0.8)
                            v += wl * 0.25
                    hsh = (x * 73 + y * 151 + k * 37) % 17
                    if d < 1:
                        g = "_" if top % 1 > 0.5 else "-"
                        c = mix(c, (255, 255, 255), 0.5)
                        v += 0.2
                    elif hsh == 0 and v > 0.3:
                        g = "*"  # glint
                        c = mix(c, (255, 255, 255), 0.6)
                    else:
                        gv = (0.22 + 0.5 * (0.5 + 0.5 * tex)) * lit * (1 - 0.5 * min(1.0, d / (h * 0.25)))
                        b.shade(x, y, gv, scale(c, clamp(0.65 + 0.5 * v, 0.05, 1.0)), mode="over", dim=False)
                        continue
                    b.put(x, y, g, scale(c, clamp(v, 0.05, 1.0)), level=0.3)
            for tx, ty, th, layer in self.trees:
                if layer == k:
                    self.paint_tree(b, tx, ty, th, layer)
            if k == 1 and cab:
                self.paint_cabin(b)

    def paint_tree(self, b, tx, ty, th, layer):
        dark = [(30, 55, 60), (25, 60, 50), (20, 70, 45)][layer]
        snowc = [(130, 150, 190), (180, 195, 230), (230, 240, 255)][layer]
        rows = int(th)
        for r in range(rows):
            y = int(ty - th + r)
            hw = 0.3 + (r + 1) * 0.55 * (1.3 if layer == 2 else 1.0) * self.tree_w
            if r % 2 == 1 and r < rows - 1:
                hw *= 0.8
            x0, x1 = int(tx - hw), int(tx + hw)
            for x in range(x0, x1 + 1):
                if x == x0:
                    ch, c = "/", snowc
                elif x == x1:
                    ch, c = "\\", snowc
                elif r == 0:
                    ch, c = "^", snowc
                else:
                    ch, c = ("*" if (x * 3 + r) % 5 == 0 else "#"), dark
                    if ch == "*":
                        c = snowc
                b.put(x, y, ch, c, level=0.6)
        b.put(tx, int(ty), "|", (70, 50, 40), level=0.5)

    def paint_cabin(self, b):
        cx, base, cw, ch = self.cabin
        wood = (120, 72, 45)
        dark = (80, 48, 32)
        top = base - ch
        for y in range(top, base):
            for x in range(cx, cx + cw):
                edge = x in (cx, cx + cw - 1)
                b.put(x, y, "|" if edge else "=", wood if (y - top) % 2 == 0 else dark, level=0.5)
        # roof with a thick snow cap
        rh = max(2, int(cw * 0.3))
        for r in range(rh + 1):
            y = top - 1 - r
            inset = r * (cw / 2 + 1) / (rh + 1)
            x0, x1 = int(cx - 1 + inset), int(cx + cw + inset * -1)
            for x in range(x0, x1 + 1):
                c = "/" if x == x0 else "\\" if x == x1 else "_" if r == 0 else "#"
                col = (235, 240, 255) if r > 0 and (x + r) % 3 else (210, 220, 245)
                b.put(x, y, c, col if c != "#" else mix(col, (180, 190, 220), 0.3), level=0.7)
        # chimney
        chx = cx + int(cw * 0.72)
        for y in range(top - int(rh * 0.6) - 1, top - rh - 1, -1):
            b.put(chx, y, "[", (110, 70, 60), level=0.6)
            b.put(chx + 1, y, "]", (110, 70, 60), level=0.6)
        b.put(chx, top - rh - 1, "_", (230, 235, 250), level=0.6)
        b.put(chx + 1, top - rh - 1, "_", (230, 235, 250), level=0.6)
        # door
        dx = cx + int(cw * 0.65)
        for y in range(base - min(ch, 3), base):
            b.put(dx, y, "|", (60, 35, 25), level=0.5)
            b.put(dx + 1, y, "|", (60, 35, 25), level=0.5)

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
        w, h, t = self.w, self.h, self.t
        wind = self.wind
        near = self.hills[2][0]
        mid = self.hills[1][0]
        far = self.hills[0][0]
        acc = self.acc
        gust = wind * (1 + 0.6 * noise1(t * 0.15, 5))
        p = self.pointer
        if p is not None:
            px, py = p
            pr = self.breath_r()
        drag = max(0.0, 1.0 - dt * 2.5)
        for f in self.flakes:
            z = f[2]
            if p is not None:
                dx, dy = f[0] - px, (f[1] - py) * ASPECT
                if -pr < dx < pr and -pr < dy < pr:
                    d = math.sqrt(dx * dx + dy * dy) + 0.3
                    if d < pr:   # near flakes feel it most
                        k = (1 - d / pr) * (35 + 40 * z) * dt / d
                        f[4] += dx * k
                        f[5] += dy * k / ASPECT
            sp = 1.2 + 4.5 * z * z
            f[1] += (sp + f[5]) * dt
            f[0] += (gust * (2 + 6 * z) + math.sin(t * (0.6 + z) + f[3]) * (0.4 + 1.2 * z) + f[4]) * dt
            if f[4] or f[5]:
                f[4] *= drag
                f[5] *= drag
                if abs(f[4]) + abs(f[5]) < 0.02:
                    f[4] = f[5] = 0.0
            xi = int(f[0])
            if 0 <= xi < w:
                ground = (near[xi] - acc[xi]) if z > 0.66 else mid[xi] if z > 0.33 else far[xi]
                if f[1] >= ground:
                    if z > 0.66:
                        acc[xi] = min(acc[xi] + 0.015, h * 0.12)
                    f[0] = rng.uniform(-w * 0.2, w * 1.2)
                    f[1] = -rng.uniform(0, 3)
                    f[4] = f[5] = 0.0
                    continue
            if f[1] > h or f[0] < -w * 0.3 or f[0] > w * 1.3 or f[1] < -h * 0.5:
                f[0] = rng.uniform(-w * 0.2, w * 1.2)
                f[1] = -rng.uniform(0, 3)
                f[4] = f[5] = 0.0
        self.update_snowballs(dt)
        # let piles settle so they stay smooth
        if int(t * 10) != int((t - dt) * 10):
            a = acc[:]
            for x in range(1, w - 1):
                acc[x] = a[x] * 0.8 + (a[x - 1] + a[x + 1]) * 0.1
        # chimney smoke
        if self.chimney:
            self.smoke_t += dt
            while self.smoke_t > 0.25:
                self.smoke_t -= 0.25
                self.smoke.append([self.chimney[0], self.chimney[1] - 0.5, 0.0, rng.uniform(0, 6.3)])
            keep = []
            for s in self.smoke:
                s[2] += dt
                s[1] -= dt * 1.1
                s[0] += dt * (gust * 2.5 + 0.6 * math.sin(t * 0.8 + s[3]) + 0.3)
                if s[2] < 7 and s[1] > -2:
                    keep.append(s)
            self.smoke = keep

    def breath_r(self):
        """Reach of the pointer's warm breath, in x-cells."""
        return max(6.0, min(self.w, self.h * ASPECT) * 0.15)

    def on_click(self, x, y):
        w, h = self.w, self.h
        x = clamp(x if x == x else w / 2, 0, w - 1)
        y = clamp(y if y == y else h / 2, 0, h - 1)
        # thrown from just below the screen, a little to one side of the target
        x0 = clamp(x + (w / 2 - x) * 0.4 + self.rng.uniform(-w * 0.1, w * 0.1), 0, w - 1)
        self.balls.append([x0, h + 2.0, x, y, 0.0, 0.45 + 0.35 * (h - y) / max(1, h)])
        del self.balls[:-6]

    def update_snowballs(self, dt):
        rng = self.rng
        landed = []
        for b in self.balls:
            b[4] += dt
            if b[4] >= b[5]:
                landed.append(b)
        for b in landed:
            self.balls.remove(b)
            x, y = b[2], b[3]
            self.poofs.append([x, y, 0.0])
            del self.poofs[:-6]
            for _ in range(rng.randint(40, 55)):     # puff!
                a = rng.uniform(0, math.tau)
                sp = rng.uniform(4, 20) * rng.choice((0.5, 1.0, 1.0))
                self.puffs.append([x, y, math.cos(a) * sp, math.sin(a) * sp / ASPECT - 4.0, 0.0,
                                   rng.uniform(0.8, 1.8)])
            xi = int(x)
            near = self.hills[2][0]
            if 0 <= xi < self.w and y >= near[xi] - self.acc[xi] - 2:   # splat into the snowbank
                for dx in range(-3, 4):
                    if 0 <= xi + dx < self.w:
                        self.acc[xi + dx] = min(self.acc[xi + dx] + 0.6 * (1 - abs(dx) / 4), self.h * 0.12)
        g = max(0.0, 1.0 - dt * 2.0)
        for q in self.puffs:
            q[4] += dt
            q[2] *= g
            q[3] = q[3] * g + 9.0 * dt
            q[0] += q[2] * dt
            q[1] += q[3] * dt
        self.puffs = [q for q in self.puffs if q[4] < q[5]]
        for q in self.poofs:
            q[2] += dt
        self.poofs = [q for q in self.poofs if q[2] < 0.9]
        del self.puffs[:-300]

    def draw_snowballs(self, cv):
        p = self.pointer
        if p is not None:   # a faint warm haze where the breath is
            px, py = p
            r = self.breath_r() * 0.7
            for yy in range(int(py - r / ASPECT), int(py + r / ASPECT) + 2):
                for xx in range(int(px - r), int(px + r) + 2):
                    d = math.hypot(xx + 0.5 - px, (yy + 0.5 - py) * ASPECT) / r
                    if d < 1:
                        cv.shade(xx, yy, 0.22 * (1 - d * d), (255, 190, 130))
        for x0, y0, x1, y1, age, ft in self.balls:
            u = age / ft
            x = x0 + (x1 - x0) * u
            y = y0 + (y1 - y0) * u - (1 - (2 * u - 1) ** 2) * self.h * 0.25   # an arc
            r = 3.6 - 2.4 * u                                              # flying away from us
            for yy in range(int(y - r / ASPECT) - 1, int(y + r / ASPECT) + 2):
                for xx in range(int(x - r) - 1, int(x + r) + 2):
                    d = math.hypot(xx + 0.5 - x, (yy + 0.5 - y) * ASPECT) / r
                    if d < 1:   # lit from the moon's side, with a soft shadowed edge
                        lit = clamp(1.0 - d * d * 0.55 + (xx + 0.5 - x) / r * 0.15 * (1 if self.moon[0] > x else -1))
                        cv.put(xx, yy, "@" if lit > 0.8 else "O" if lit > 0.6 else "o",
                               mix((120, 140, 190), (255, 255, 255), lit), level=lit)
        for x, y, age in self.poofs:
            r = 3.5 + age * 10.0
            k = (1 - age / 0.9) ** 0.7
            for yy in range(int(y - r / ASPECT) - 1, int(y + r / ASPECT) + 2):
                for xx in range(int(x - r) - 1, int(x + r) + 2):
                    d = math.hypot(xx + 0.5 - x, (yy + 0.5 - y) * ASPECT) / r
                    if d < 1:
                        cv.shade(xx, yy, k * (1 - d * d) * 0.9, (235, 242, 255), mode="over" if d < 0.9 * k else "max")
        for x, y, vx, vy, age, life in self.puffs:
            k = 1 - age / life
            cv.put(x, y, "*" if k > 0.6 else "+" if k > 0.3 else ".", mix((120, 140, 190), (250, 252, 255), k),
                   level=0.8 * k)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, t = self.w, self.h, self.t
        if (cv.w, cv.h) != (w, h):
            return
        self.background(cv)
        put, shade = cv.put, cv.shade
        for x, y, b, ph in self.stars:
            if cv.lv[y * w + x] > 0.12:
                continue
            v = b * (0.5 + 0.5 * math.sin(t * 1.3 + ph))
            if v > 0.3:
                put(x, y, "." if v < 0.7 else "+", mix((90, 110, 160), (230, 240, 255), v), level=0.2)
        # piled-up snow on the near hill
        near = self.hills[2][0]
        for x in range(w):
            a = self.acc[x]
            if a < 0.3:
                continue
            top = near[x] - a
            for y in range(int(top), int(near[x]) + 1):
                put(x, y, "_" if y == int(top) and (top % 1) > 0.5 else "#" if y > top + 1 else "=",
                    (225, 235, 255), level=0.5)
        # window glow (flickering fire inside)
        cab = self.cabin
        if cab:
            cx, base, cw, ch = cab
            fl = 0.8 + 0.2 * noise1(t * 3.0, 9)
            wx0 = cx + int(cw * 0.2)
            wwid = max(2, int(cw * 0.25))
            wy = base - ch + max(1, ch // 3)
            for yy in range(wy, min(base - 1, wy + max(1, ch // 2))):
                for xx in range(wx0, wx0 + wwid):
                    put(xx, yy, "#", scale((255, 200, 110), fl), level=0.9)
            for xx in (wx0 - 1, wx0 + wwid):
                put(xx, wy, "|", (90, 55, 35), level=0.5)
        # smoke
        for sx, sy, age, ph in self.smoke:
            k = age / 7
            r = 0.6 + age * 0.5
            v = 0.55 * (1 - k) ** 1.2
            for dx in range(-int(r), int(r) + 1):
                fall = 1 - abs(dx) / (r + 0.5)
                shade(sx + dx, sy, v * fall, (175, 180, 200))
        # flakes, far to near
        for x, y, z, ph, _, _ in self.flakes:
            if y < 0:
                continue
            if z < 0.33:
                put(x, y, ".", mix((70, 85, 120), (130, 145, 185), z * 3), level=0.3)
            elif z < 0.66:
                put(x, y, "+" if (ph * 10) % 3 < 1 else "*" if (ph * 10) % 3 < 2 else "·",
                    mix((140, 155, 195), (200, 210, 240), (z - 0.33) * 3), level=0.5)
            else:
                put(x, y, "*", (240, 245, 255), level=0.9)
        self.draw_snowballs(cv)
