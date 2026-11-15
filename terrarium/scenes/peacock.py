"""A peacock that struts, then raises and fans its train into a shimmering display.

The train is a set of feather layers radiating from the rump. Every layer is a row of evenly
spaced feathers, so for any cell the nearest feather is found in O(1) from its angle; the
cell then lands in that feather's eyespot (concentric glyph rings), its barbed vane or its shaft.
Opening the fan is two motions blended: the folded bundle swings up from the ground, then
spreads like a hand fan. While displaying, the feathers rattle and a shimmer wave sweeps across.
"""
import math

from ..engine import ASPECT, Scene, clamp, hsv, mix, noise1, scale, smoothstep

TAU = math.tau
PI = math.pi

# eyespot rings from the centre out, then vane colours (inner, outer), shaft
CLASSIC = dict(rings=[((40, 70, 230), "@"), ((30, 40, 140), "@"), ((40, 215, 200), "O"), ((210, 140, 60), "o"),
                      ((150, 205, 70), "*"), ((90, 170, 90), ":")],
               vane=((40, 120, 80), (170, 150, 70)), shaft=(210, 200, 150),
               body=(40, 110, 240), neck=(60, 170, 255), wing=(170, 120, 70))
WHITE = dict(rings=[((235, 240, 255), "@"), ((190, 200, 225), "@"), ((250, 250, 250), "O"), ((215, 215, 205), "o"),
                    ((240, 240, 230), "*"), ((180, 180, 175), ":")],
             vane=((170, 175, 175), (235, 235, 225)), shaft=(255, 255, 245),
             body=(235, 235, 240), neck=(250, 250, 255), wing=(220, 220, 215))


def _rot(c, dh, ds=1.0):
    r, g, b = c[0] / 255, c[1] / 255, c[2] / 255
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return c
    if mx == r:
        hh = ((g - b) / d) % 6
    elif mx == g:
        hh = (b - r) / d + 2
    else:
        hh = (r - g) / d + 4
    return hsv(hh / 6 + dh, clamp(d / mx * ds), mx)


def _dir_ch(dx, dy):
    ax, ay = abs(dx), abs(dy * ASPECT)
    if ax > 1.8 * ay:
        return "-"
    if ay > 1.8 * ax:
        return "|"
    return "\\" if dx * dy > 0 else "/"


class Peacock(Scene):
    name = "peacock"
    title = "Peacock"
    blurb = "a peacock struts, then fans its train into a full shimmering display of eyespots"
    tags = ("nature", "creatures", "birds", "calm")
    options = {
        "interval": (0.0, "seconds of strutting between displays (0 = random)"),
        "palette": ("random", "random, classic, white or fantasy"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        pal = self.opt("palette")
        if pal == "random":
            pal = rng.choice(("classic", "classic", "classic", "white", "fantasy"))
        if pal == "white":
            P = WHITE
        elif pal == "fantasy":
            dh = rng.choice((0.12, 0.25, 0.4, 0.55, 0.7, 0.85)) + rng.uniform(-0.04, 0.04)
            P = dict(rings=[(_rot(c, dh), ch) for c, ch in CLASSIC["rings"]],
                     vane=tuple(_rot(c, dh) for c in CLASSIC["vane"]), shaft=CLASSIC["shaft"],
                     body=_rot(CLASSIC["body"], dh), neck=_rot(CLASSIC["neck"], dh), wing=CLASSIC["wing"])
        else:
            dh = rng.uniform(-0.03, 0.03)
            P = dict(rings=[(_rot(c, dh), ch) for c, ch in CLASSIC["rings"]], vane=CLASSIC["vane"],
                     shaft=CLASSIC["shaft"], body=_rot(CLASSIC["body"], dh), neck=_rot(CLASSIC["neck"], dh),
                     wing=CLASSIC["wing"])
        self.P = P
        self.ground = h - max(2, int(h * 0.08))
        # geometry: the fan must fit above the ground and across the screen
        hp_k = 0.3
        R = min(w * rng.uniform(0.36, 0.45), (self.ground - 1) * ASPECT / (1 + hp_k))
        self.R = R = max(8.0, R)
        self.hp = hp_k * R                                   # rump height (units)
        self.ew = R * rng.uniform(0.07, 0.09)                # eyespot half-width
        self.span = rng.uniform(2.75, 3.2)
        nl = rng.choice((4, 5, 5, 6))
        step = rng.uniform(0.13, 0.17)
        self.layers = []
        for j in range(nl):
            L = R * (1 - j * step)
            if L < R * 0.3:
                break
            arc = L * self.span
            n = max(5, int(arc / (self.ew * rng.uniform(2.4, 2.9))))
            self.layers.append([L, n])
        self.eye_len = rng.uniform(1.15, 1.45)
        self.shimmer_speed = rng.uniform(1.2, 2.2)
        self.rattle_hz = rng.uniform(9, 14)
        self.vane_k = rng.uniform(0.5, 0.65)
        self.crest = rng.randint(5, 8)
        # bird state
        self.x = rng.uniform(0.35, 0.65) * w
        self.face = rng.choice((-1, 1))
        self.state = "strut"
        self.timer = self.strut_time()
        self.open = 0.0
        self.walk_phase = 0.0
        self.tx = self.pick_x()
        self.trail = -self.face
        self.shake = 0.0
        self.bake_garden()

    def strut_time(self):
        iv = self.opt("interval")
        return iv if iv > 0 else self.rng.uniform(5, 11)

    def pick_x(self):
        w = self.w
        R = self.R
        lo, hi = min(w * 0.5, R * 0.75), max(w * 0.5, w - R * 0.75)
        return self.rng.uniform(lo, hi)

    def bake_garden(self):
        rng = self.rng
        w, h, gy = self.w, self.h, self.ground
        self.bg = {}
        hue = rng.uniform(0.25, 0.42)
        for _ in range(rng.randint(3, 6)):
            cx = rng.uniform(0, w)
            rw = rng.uniform(0.1, 0.25) * w
            rh = rng.uniform(0.25, 0.55) * h
            col = hsv(hue + rng.uniform(-0.05, 0.05), rng.uniform(0.4, 0.7), 1.0)
            for y in range(max(0, int(gy - rh)), gy):
                for x in range(max(0, int(cx - rw)), min(w, int(cx + rw) + 1)):
                    dx = (x - cx) / rw
                    dy = (gy - y) / rh
                    edge = 1 - dx * dx - dy * dy + 0.15 * noise1(x * 0.3 + y * 0.7, 5)
                    if edge > 0:
                        k = 0.05 + 0.1 * min(1.0, edge * 2) * (0.6 + 0.4 * noise1(x * 0.5 + y * 1.3, 6))
                        c = scale(col, k)
                        self.bg[y * w + x] = ("░", (int(c[0]) & ~3, int(c[1]) & ~3, int(c[2]) & ~3))
        flower_cols = [hsv(rng.random(), 0.5, 1.0) for _ in range(3)]
        for _ in range(int(w / 5)):
            x, y = int(rng.uniform(0, w)), int(gy - rng.uniform(0, h * 0.35))
            if 0 <= y < h:
                c = scale(rng.choice(flower_cols), rng.uniform(0.2, 0.4))
                self.bg[y * w + x] = (rng.choice(("*", ".", "o", "+")), (int(c[0]) & ~3, int(c[1]) & ~3, int(c[2]) & ~3))
        for x in range(w):
            for y in range(gy, h):
                d = (y - gy) / max(1, h - gy)
                ch = rng.choice(("_", ".", ",", "'", "\"", "-")) if y > gy else rng.choice(("_", ".", ","))
                c = scale(hsv(hue + rng.uniform(-0.04, 0.04), 0.6, 1.0), 0.18 + 0.12 * d)
                self.bg[y * w + x] = (ch, (int(c[0]) & ~3, int(c[1]) & ~3, int(c[2]) & ~3))

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.1)
        rng = self.rng
        if self.state == "strut":
            d = self.tx - self.x
            if abs(d) > 0.5:
                want = 1 if d > 0 else -1
                if want != self.face:
                    self.face = want
                spd = self.R * 0.06
                self.x += want * min(abs(d), spd * dt * (0.6 + 0.4 * abs(math.sin(self.walk_phase))))
                self.walk_phase += dt * 3.2
            else:
                self.tx = self.pick_x()
            self.trail += (-self.face - self.trail) * min(1, dt * 1.2)
            self.timer -= dt
            if self.timer <= 0:
                self.state = "raise"
                self.timer = rng.uniform(2.2, 3.2)
                self.dur = self.timer
        elif self.state == "raise":
            self.timer -= dt
            self.open = clamp(1 - self.timer / self.dur)
            if self.timer <= 0:
                self.state = "display"
                self.timer = rng.uniform(7, 13)
                self.open = 1.0
        elif self.state == "display":
            self.timer -= dt
            # bursts of train-rattling
            if self.shake <= 0 and rng.random() < dt * 0.35:
                self.shake = rng.uniform(1.0, 2.2)
            self.shake = max(0.0, self.shake - dt)
            if rng.random() < dt * 0.12:
                self.face = -self.face
            if self.timer <= 0:
                self.state = "fold"
                self.timer = rng.uniform(1.8, 2.6)
                self.dur = self.timer
                self.tx = self.pick_x()
                self.face = 1 if self.tx > self.x else -1
                self.trail = -self.face
        elif self.state == "fold":
            self.timer -= dt
            self.open = clamp(self.timer / self.dur)
            if self.timer <= 0:
                self.state = "strut"
                self.open = 0.0
                self.timer = self.strut_time()

    # ------------------------------------------------------------------ geometry
    def layer_angles(self, j, n, L):
        """(first angle, step) of layer j for the current openness (angles in rad, y up)."""
        o = self.open
        raise_k = smoothstep(0.0, 0.5, o)
        spread_k = smoothstep(0.35, 1.0, o)
        drop = math.asin(min(0.95, self.hp / L)) * 0.9
        trail = PI + drop if self.trail < 0 else -drop
        if self.trail < 0:
            centre = trail + (PI / 2 - trail) * raise_k
        else:
            centre = trail + (PI / 2 - trail) * raise_k
        folded = 0.012 + 0.006 * j
        stepa = folded + (self.span / max(1, n - 1) - folded) * spread_k
        off = 0.5 * stepa if j % 2 else 0.0
        return centre - (n - 1) / 2 * stepa + off * spread_k, stepa

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h = self.w, self.h
        for i, (ch, col) in self.bg.items():
            cv.ch[i] = ch
            cv.fg[i] = col
            cv.lv[i] = 0.05
        bob = math.sin(self.walk_phase * 2) * 0.3 if self.state == "strut" else 0.0
        px = self.x - self.face * self.R * 0.13
        py = self.ground - self.hp / ASPECT + bob * 0.2
        self.draw_train(cv, px, py)
        self.draw_body(cv, bob)

    def draw_train(self, cv, px, py):
        w, h = self.w, self.h
        t = self.t
        P = self.P
        rings = P["rings"]
        nr = len(rings)
        v_in, v_out = P["vane"]
        ew = self.ew
        el = ew * self.eye_len
        disp = self.open
        shake = self.shake if self.state == "display" else 0.0
        rat = (0.004 + 0.012 * min(1.0, shake)) * disp
        wave_c = PI / 2 + math.sin(t * self.shimmer_speed * 0.5) * self.span * 0.6
        lay = []
        for j, (L, n) in enumerate(self.layers):
            a0, st = self.layer_angles(j, n, L)
            lay.append((L, n, a0, st))
        # bounding box from the sector actually covered
        R = self.R + ew
        angs = []
        for L, n, a0, st in lay:
            angs += [a0, a0 + st * (n - 1)]
        amin, amax = min(angs), max(angs)
        amid = (amin + amax) / 2
        xs, ys = [px], [py]
        for k in range(9):
            a = amin + (amax - amin) * k / 8
            xs.append(px + math.cos(a) * R)
            ys.append(py - math.sin(a) * R / ASPECT)
        x0, x1 = max(0, int(min(xs)) - 1), min(w, int(max(xs)) + 2)
        y0, y1 = max(0, int(min(ys)) - 1), min(h, int(max(ys)) + 2)
        lv = cv.lv
        for y in range(y0, y1):
            dy = (py - (y + 0.5)) * ASPECT
            for x in range(x0, x1):
                dx = x + 0.5 - px
                r = math.hypot(dx, dy)
                if r > R or r < 1.0:
                    continue
                th = math.atan2(dy, dx)
                th += TAU * round((amid - th) / TAU)   # keep angles continuous around the bundle
                hit = None
                for L, n, a0, st in reversed(lay):          # front (short) layers first
                    if r > L + ew * 0.3:
                        continue
                    i = int(round((th - a0) / st))
                    if i < 0 or i >= n:
                        continue
                    jit = rat * math.sin(t * self.rattle_hz * TAU / 6 + i * 1.7)
                    dth = th - (a0 + i * st) - jit
                    perp = r * math.sin(dth)
                    along = r * math.cos(dth)
                    ec = L - el * 0.95
                    ex = (along - ec) / el
                    ey = perp / ew
                    d = math.sqrt(ex * ex + ey * ey)
                    if d < 1.0:
                        k = min(nr - 1, int(d * nr))
                        col, ch = rings[k]
                        hit = (ch, col, 0.95 - 0.08 * k, i)
                        break
                    vw = ew * self.vane_k * (0.25 + 0.75 * (along / L)) * (1.25 if along > ec else 1.0)
                    ap = abs(perp)
                    if along < L and ap < vw:
                        if ap < 0.4 and along < ec:
                            hit = (_dir_ch(math.cos(th - jit), -math.sin(th - jit)), P["shaft"], 0.5, i)
                        else:
                            # barbs sweep outward from the shaft
                            side = 1 if perp > 0 else -1
                            ba = th + side * 0.7
                            ch = _dir_ch(math.cos(ba), -math.sin(ba))
                            q = along / L
                            hit = (ch, mix(v_in, v_out, q), 0.42 + 0.15 * q, i)
                        break
                if hit is None:
                    continue
                ch, col, v, i = hit
                # shimmer wave and rattle sparkle
                sw = math.exp(-((th - wave_c) / 0.35) ** 2) * disp
                sp = 0.0
                if shake > 0 and ((i * 7 + int(t * 20)) % 11) == 0:
                    sp = 0.5
                k = 0.55 + 0.35 * v + 0.35 * sw + sp
                if k > 1.0:
                    col = mix(col, (255, 255, 240), min(0.6, (k - 1.0)))
                    k = 1.0
                idx = y * w + x
                if v > lv[idx] or lv[idx] < 0.1:
                    cv.put(x, y, ch, scale(col, k), level=v)

    def draw_body(self, cv, bob):
        """Profile body: legs, a horizontal egg with a chestnut wing, an S-neck, crested head.
        A one-cell dark margin is cut around it so it stands clear of the fan."""
        P = self.P
        R = self.R
        f = self.face
        gy = self.ground
        t = self.t
        bx = self.x
        bw = R * 0.16                    # half length of the body egg (units)
        bh = R * 0.1                     # half height
        leg = R * 0.2
        cy = gy - (leg + bh) / ASPECT + bob * 0.15
        body, neck, wing = P["body"], P["neck"], P["wing"]
        sheen = 0.5 + 0.5 * math.sin(t * 1.1)
        strut = self.state == "strut"
        nb = math.sin(self.walk_phase * 2) if strut else 0.25 * math.sin(t * 0.8)
        hx = bx + f * (bw * 0.95 + R * 0.04 * nb)
        hy = cy - (bh + R * 0.26) / ASPECT
        steps = max(5, int((cy - hy) * 1.5))
        neck_pts = []
        for k in range(steps + 1):
            q = k / steps
            sx = bx + f * bw * 0.7 + (hx - bx - f * bw * 0.7) * q - f * math.sin(q * PI) * R * 0.035
            sy = cy - bh * 0.3 / ASPECT + (hy - cy + bh * 0.3 / ASPECT) * q
            neck_pts.append((sx, sy, q))
        w, h = cv.w, cv.h
        y0, y1 = max(0, int(cy - bh / ASPECT) - 2), min(h, int(cy + bh / ASPECT) + 3)
        x0, x1 = max(0, int(bx - bw * 1.3) - 1), min(w, int(bx + bw * 1.3) + 2)

        def egg(x, y):
            ux = (x + 0.5 - bx) / bw * f
            vy = (y + 0.5 - cy) * ASPECT / bh
            return ux, vy, ux * ux + (vy / (1.0 + 0.2 * ux)) ** 2

        # cut a margin
        for y in range(y0, y1):
            for x in range(x0, x1):
                if egg(x, y)[2] < 1.5:
                    i = y * w + x
                    cv.ch[i] = " "
                    cv.fg[i] = None
                    cv.lv[i] = 0.0
        for sx, sy, q in neck_pts:
            for dx in (-1, 0, 1):
                xi, yi = int(sx) + dx, int(sy)
                if 0 <= xi < w and 0 <= yi < h:
                    cv.ch[yi * w + xi] = " "
                    cv.fg[yi * w + xi] = None
        # legs
        for side in (-1, 1):
            lp = self.walk_phase + (0 if side < 0 else PI)
            lift = max(0.0, math.sin(lp)) if strut else 0.0
            lx = bx + side * bw * 0.25 + (math.cos(lp) * R * 0.04 if strut else 0)
            for yy in range(int(cy + bh * 0.6 / ASPECT), gy):
                cv.put(lx, yy, "|", (160, 150, 140), level=0.6)
            cv.put(lx + f, gy - (1 if lift > 0.5 else 0), "^" if lift > 0.5 else "_", (160, 150, 140), level=0.6)
        # body
        for y in range(y0, y1):
            for x in range(x0, x1):
                ux, vy, e = egg(x, y)
                if e > 1:
                    continue
                lit = 0.6 + 0.3 * (1 - e) - 0.15 * vy
                col = mix(body, neck, clamp(0.3 + ux * 0.4 - vy * 0.3 + 0.25 * sheen))
                if ux < 0.25 and vy < 0.55:              # folded wing, barred chestnut and cream
                    bar = int((ux + vy * 0.6 + 2) * 4) % 2
                    col = mix(wing, (245, 225, 185), 0.45 * bar)
                    cv.put(x, y, "#" if bar else "%", scale(col, lit), level=0.9)
                else:
                    cv.shade(x, y, clamp(lit), col, mode="over")
        # neck
        for sx, sy, q in neck_pts:
            col = mix(body, neck, q)
            cv.put(sx, sy, "@" if q < 0.5 else "%", scale(mix(col, (255, 255, 255), 0.2 * sheen), 0.95), level=0.9)
            if q < 0.6:
                cv.put(sx - f, sy, "#", scale(col, 0.75), level=0.9)
        # head: blue, white eye stripe, beak, crest of tiny fans
        cv.put(hx, hy, "@", neck, level=1.0)
        cv.put(hx - f, hy, "@", scale(neck, 0.85), level=1.0)
        cv.put(hx, hy, "o" if int(t * 0.7) % 9 else "-", (250, 250, 250), level=1.0)
        cv.put(hx + f, hy, ">" if f > 0 else "<", (220, 200, 160), level=1.0)
        ln = max(1.5, R * 0.05)
        for k in range(self.crest):
            a = PI / 2 + (k - (self.crest - 1) / 2) * 0.14 + f * 0.15
            for s_ in range(1, int(ln) + 1):
                cx_ = hx - f * 0.3 + math.cos(a) * s_ * 1.4
                cy_ = hy - 0.6 - math.sin(a) * s_ / ASPECT * 1.4
                tip = s_ == int(ln)
                cv.put(cx_, cy_, "o" if tip else "'", neck if tip else (120, 140, 160), level=1.0)
