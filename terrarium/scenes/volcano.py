"""A volcano at night erupting in cycles: lava fountains, creeping flows, a lit ash plume."""
import math

from ..engine import ASPECT, RAMPS, Scene, clamp, gradient, mix, noise1, scale

TAU = math.tau

SKIES = [
    # top .. horizon, star tint, distant ridge color
    {"sky": [(4, 4, 14), (10, 8, 30), (34, 16, 44), (90, 30, 40)], "star": (230, 225, 255), "ridge": (26, 16, 34)},
    {"sky": [(6, 4, 18), (22, 10, 44), (60, 22, 70), (120, 44, 70)], "star": (240, 220, 255), "ridge": (34, 16, 44)},
    {"sky": [(2, 6, 18), (6, 14, 40), (16, 26, 64), (60, 40, 70)], "star": (215, 230, 255), "ridge": (14, 20, 40)},
    {"sky": [(8, 4, 8), (24, 10, 18), (60, 20, 24), (130, 50, 30)], "star": (255, 230, 210), "ridge": (30, 14, 18)},
]
LAVA = [(255, 255, 235), (255, 236, 120), (255, 160, 40), (230, 70, 18), (150, 26, 12), (60, 14, 12), (30, 10, 10)]
ASH = (88, 78, 92)
GLOW = (255, 110, 36)
PLUME_RAMP = " .:;coO08&"
HALO = "..··::;;++"   # lumpy glyphs read as billows (ascii charset only)


def _hash(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 982451653) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 65535.0


def tnoise(x, y, px, py, seed):
    """Tileable value noise in [0, 1] with periods px, py (lattice units)."""
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u = xf * xf * (3 - 2 * xf)
    v = yf * yf * (3 - 2 * yf)
    x0, x1 = xi % px, (xi + 1) % px
    y0, y1 = yi % py, (yi + 1) % py
    a = _hash(x0, y0, seed) + (_hash(x1, y0, seed) - _hash(x0, y0, seed)) * u
    b = _hash(x0, y1, seed) + (_hash(x1, y1, seed) - _hash(x0, y1, seed)) * u
    return a + (b - a) * v


def lava_col(temp):
    """temp 1 = white-hot .. 0 = cold crust."""
    return gradient(LAVA, 1.0 - clamp(temp))


def streak(vx, vy):
    """Glyph for something moving with velocity (vx cells/s, vy rows/s)."""
    ax, ay = abs(vx), abs(vy) * ASPECT
    if ay > ax * 2.2:
        return "|"
    if ax > ay * 2.2:
        return "-"
    return "/" if (vx > 0) == (vy < 0) else "\\"


class Flow:
    __slots__ = ("pts", "front", "speed", "heat", "born", "phase")


class Volcano(Scene):
    name = "volcano"
    title = "Volcano"
    blurb = "a volcano at night erupting in cycles: lava fountains, flows and a glowing ash plume"
    tags = ("nature", "night", "fire", "dramatic")
    options = {
        "frequency": (1.0, "how often it erupts (multiplier)"),
        "intensity": (1.0, "eruption strength (multiplier)"),
        "plume": (True, "draw the ash plume"),
        "style": ("random", "random, fountain or explosive (random picks per eruption)"),
        "base": ("random", "random, sea or plain"),
        "shake": (True, "shake the view while it rumbles"),
    }

    # ------------------------------------------------------------------ setup
    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.seed = rng.randrange(1 << 15)
        self.pal = rng.choice(SKIES)
        base = str(self.opt("base")).lower()
        self.sea = rng.random() < 0.65 if base not in ("sea", "plain") else base == "sea"
        self.hz = hz = max(4, min(h - 2, int(round(h * rng.uniform(0.74, 0.82)))))
        # --- cone grammar: height, base widths (asymmetric), slope curvature, crater, breach
        self.cx = cx = w * rng.uniform(0.36, 0.64)
        self.H = H = hz * rng.uniform(0.5, 0.68)
        self.rc = rc = max(1.6, min(w * rng.uniform(0.025, 0.055), H * ASPECT * 0.35))
        span = min(w * 0.5, max(8.0, H * ASPECT * rng.uniform(1.3, 2.1)))
        self.RL = span * rng.uniform(0.8, 1.25)
        self.RR = span * rng.uniform(0.8, 1.25)
        self.kL = rng.uniform(1.25, 2.3)      # >1 = concave flanks (classic stratovolcano)
        self.kR = rng.uniform(1.25, 2.3)
        cdepth = rng.uniform(0.4, 1.6)
        breach = rng.choice((-1, 0, 0, 1))    # a notch on one rim
        shoulder = rng.uniform(-0.25, 0.25)   # an old vent bump on one flank
        sh_x = cx + rng.choice((-1, 1)) * span * rng.uniform(0.35, 0.6)
        self.top = top = []
        for x in range(w):
            xc = x + 0.5 - cx
            if abs(xc) <= rc:
                q = xc / rc
                hgt = H - cdepth * (1 - q * q)
                if breach and q * breach > 0:
                    hgt -= cdepth * 0.9 * abs(q)
            else:
                if xc < 0:
                    u, k = (-xc - rc) / self.RL, self.kL
                else:
                    u, k = (xc - rc) / self.RR, self.kR
                hgt = H * (1 - clamp(u)) ** k if u < 1 else 0.0
                hgt += H * shoulder * 0.35 * math.exp(-((x - sh_x) / (span * 0.12)) ** 2) * (1 - clamp(u))
                hgt += H * 0.035 * noise1(x * 0.18, self.seed) * (1 - clamp(u))
            top.append(hz - max(0.0, hgt))
        self.ty = hz - H                      # crater floor row (float)
        self.Hm = self.ty * 1.12
        # distant ridges
        self.ridges = []
        for k in range(rng.randint(1, 2)):
            amp = hz * rng.uniform(0.08, 0.2)
            off = rng.uniform(0, 100)
            fr = rng.uniform(0.02, 0.05)
            self.ridges.append([hz - amp * (0.55 + 0.45 * noise1(x * fr + off, self.seed + k))
                                - amp * 0.3 * noise1(x * fr * 3 + off, self.seed + 9) for x in range(w)])
        # wind for the plume, a moon maybe
        self.wind = rng.choice((-1, 1)) * rng.uniform(0.6, 2.2)
        self.moon = None
        if rng.random() < 0.55:
            mx = w * (rng.uniform(0.08, 0.22) if self.wind > 0 else rng.uniform(0.78, 0.92))
            self.moon = (mx, hz * rng.uniform(0.12, 0.25), clamp(h * 0.07, 1.6, 4.5), rng.uniform(0.25, 0.55))
        ns = int(w * hz / 26 * self.density)
        self.stars = []
        for _ in range(ns):
            x, y = rng.randrange(w), rng.randrange(max(1, hz - 1))
            if y < self.ridge_min(x) - 1 and y < top[x] - 1:
                self.stars.append((x, y, rng.uniform(0.15, 1.0), rng.uniform(0, TAU)))
        # plume texture tile
        self.TW, self.TH = 64, 96
        self.tile = [[0.65 * tnoise(x / 8.0, y / 8.0, 8, 12, self.seed) + 0.35 * tnoise(x / 4.0, y / 4.0, 16, 24, self.seed + 1)
                      for x in range(self.TW)] for y in range(self.TH)]
        self.ash = rng.choice((((40, 34, 44), (130, 118, 128)), ((36, 34, 42), (120, 124, 140)),
                               ((46, 36, 36), (140, 120, 112))))
        # emission history (0.05 s samples)
        self.hist = [0.1] * 800
        self.hpos = 0
        self.hacc = 0.0
        # eruption cycle
        self.phase = "quiet"
        self.ptime = 0.0
        self.pdur = rng.uniform(1.0, 2.5)
        self.style = "fountain"
        self.burst = 0.0
        self.glow = 0.3
        self.emit = 0.1
        self.parts = []          # [x, y, vx, vy, age, life, landed]
        self.flows = []
        self.bolt = None         # (cells, time left)
        self.bolt_cd = 0.0
        self.shake = 0
        self.shake_t = 0.0
        self.spawn_acc = 0.0
        # some old, cold flows for texture
        for _ in range(rng.randint(2, 5)):
            f = self.new_flow()
            f.front = len(f.pts)
            f.heat = 0.0
            f.born = -100.0
            self.flows.append(f)
        self.ngul = rng.uniform(9, 17)
        self.mside = 0.0 if self.moon is None else (-1.0 if self.moon[0] < cx else 1.0)
        self.bake()
        self._bgkey = None

    def ridge_min(self, x):
        return min((r[x] for r in self.ridges), default=self.hz)

    def new_flow(self):
        rng = self.rng
        top, w, hz = self.top, self.w, self.hz
        x = self.cx + rng.uniform(-0.8, 0.8) * self.rc
        drift = rng.choice((-1, 1)) * rng.uniform(0.15, 1.5)
        mean = rng.uniform(0.3, 1.0)
        ph = rng.uniform(0, 50)
        y = int(top[int(clamp(x, 0, w - 1))]) + 1
        pts = []
        while y < hz:
            xi = int(clamp(x, 0, w - 1))
            if y < top[xi] + 0.5:      # pushed off the flank: steer back onto the face
                drift *= 0.6
                x += -1 if x > self.cx else 1
                xi = int(clamp(x, 0, w - 1))
            pts.append((xi, y))
            x += drift + mean * noise1(y * 0.35 + ph, self.seed + 3) * 0.8
            drift *= 1.02
            y += 1
        f = Flow()
        f.pts = pts or [(int(self.cx), int(self.ty) + 1)]
        f.front = 0.0
        f.speed = rng.uniform(1.2, 2.6)
        f.heat = 1.0
        f.born = self.t
        f.phase = rng.uniform(0, TAU)
        return f

    # ------------------------------------------------------------------ static layers
    def bake(self):
        """Cone cells: (x, y, level, base color, glow proximity)."""
        w, hz, top = self.w, self.hz, self.top
        cx, ty, H = self.cx, self.ty, self.H
        s = self.seed
        cells = []
        edge = []
        for x in range(w):
            yt = top[x]
            if yt >= hz - 0.2:
                continue
            iy = int(yt)
            yl, yr = top[max(0, x - 1)], top[min(w - 1, x + 1)]
            slope = (yr - yl) * 0.5
            ch = "\\" if slope > 0.7 else "/" if slope < -0.7 else ("'" if yt - iy < 0.33 else "-" if yt - iy < 0.66 else "_")
            near = math.exp(-(abs(x + 0.5 - cx) / (self.rc * 3.0)) - max(0.0, iy - ty) / (H * 0.35))
            edge.append((x, iy, ch, near))
            for y in range(iy + 1, hz):
                d = (y - yt) / max(1.0, H)
                sx = x + 0.5 - cx
                sy = (y + 0.5 - ty) * ASPECT
                ang = math.atan2(sx, sy)
                dist = math.hypot(sx, sy)
                # radial gullies fanning out from the summit
                g = math.sin(ang * self.ngul + 2.6 * noise1(dist * 0.07 + ang * 2.0, s))
                r = _hash(x, y, s)
                lit = 0.5 + 0.5 * math.sin(ang) * self.mside
                lvl = (0.13 + 0.2 * max(0.0, g) + 0.07 * r + 0.06 * lit) * (1 - 0.35 * clamp(d))
                near = math.exp(-(abs(sx) / (self.rc * 4.0)) - (y - ty) / (H * 0.4))
                col = mix((34, 22, 36), (104, 70, 76), clamp(0.5 * g + 0.5 * r * 0.6 + 0.2))
                col = mix(col, (70, 76, 110), 0.3 * lit * (self.moon is not None))
                if g > 0.55 and r > 0.25:
                    tn = abs(sx) / max(0.01, sy)
                    ch = "|" if tn < 0.3 else ("/" if sx < 0 else "\\") if tn < 3.0 else "_"
                elif r < 0.12:
                    continue
                else:
                    ch = ".,:;"[int(lvl * 12) % 4] if lvl < 0.24 else ";!i:"[int(r * 53) % 4]
                cells.append((x, y, lvl, col, near, ch))
        self.cone = cells
        self.edge = edge

    def paint_static(self, cv):
        """Sky gradient, distant ridges, sea / plain texture (no glow; that is added per frame)."""
        w, h, hz = self.w, self.h, self.hz
        sky = self.pal["sky"]
        for y in range(hz):
            f = y / max(1, hz - 1)
            col = gradient(sky, f ** 1.3)
            dens = 0.04 + 0.6 * f ** 2.5
            for x in range(w):
                if _hash(x, y, self.seed + 5) < dens:
                    cv.shade(x, y, 0.1 + 0.35 * f ** 2, col, dim=False)
        rc = self.pal["ridge"]
        for k, ridge in enumerate(self.ridges):
            col = mix(rc, sky[-1], 0.25 * k)
            for x in range(w):
                yt = ridge[x]
                iy = int(yt)
                cv.put(x, iy, "_" if yt - iy > 0.5 else "-", scale(mix(col, sky[-1], 0.5), 1.1))
                for y in range(iy + 1, hz):
                    if _hash(x, y, 77 + k) < 0.35:
                        cv.put(x, y, ".", scale(col, 0.9))
                    else:
                        cv.put(x, y, " ", col)
        if not self.sea:
            for y in range(hz, h):
                d = (y - hz) / max(1, h - hz)
                for x in range(w):
                    r = _hash(x, y, 31)
                    if r < 0.45:
                        ch = "." if r < 0.2 else "," if r < 0.32 else "_" if r < 0.4 else "'"
                        cv.put(x, y, ch, mix((30, 18, 22), (60, 38, 34), d + r))

    def background(self, cv):
        key = (cv.w, cv.h, cv.ramp)
        if self._bgkey != key:
            from ..engine import Canvas
            bg = Canvas(cv.w, cv.h, cv.ramp)
            self.paint_static(bg)
            self._bg = bg
            self._bgkey = key
        bg = self._bg
        cv.ch[:] = bg.ch
        cv.fg[:] = bg.fg
        cv.lv[:] = bg.lv
        cv.bc[:] = bg.bc

    # ------------------------------------------------------------------ simulation
    def next_phase(self):
        rng = self.rng
        freq = max(0.05, self.opt("frequency"))
        inten = max(0.1, self.opt("intensity"))
        order = {"quiet": "rumble", "rumble": "erupt", "erupt": "wane", "wane": "quiet"}
        self.phase = order[self.phase]
        self.ptime = 0.0
        if self.phase == "quiet":
            self.pdur = rng.uniform(5.0, 11.0) / freq
        elif self.phase == "rumble":
            self.pdur = rng.uniform(2.0, 3.5)
            st = str(self.opt("style")).lower()
            self.style = st if st in ("fountain", "explosive") else rng.choice(("fountain", "explosive"))
            self.fh = rng.uniform(0.45, 0.95)          # fountain height (share of the sky)
            self.fspread = rng.uniform(2.5, 6.0)
        elif self.phase == "erupt":
            self.pdur = rng.uniform(6.0, 11.0) * inten ** 0.3
            n = rng.randint(1, 3) + (1 if inten > 1.4 else 0)
            for _ in range(n):
                self.flows.append(self.new_flow())
            # old flows beyond the newest few are forgotten
            if len(self.flows) > 10:
                self.flows = self.flows[-10:]
        else:
            self.pdur = rng.uniform(2.5, 4.5)

    def update(self, dt):
        super().update(dt)
        rng = self.rng
        t = self.t
        inten = max(0.1, self.opt("intensity"))
        self.ptime += dt
        if self.ptime >= self.pdur:
            self.next_phase()
        p = self.ptime / max(0.01, self.pdur)
        ph = self.phase
        flick = 0.06 * noise1(t * 3.0, self.seed + 11)
        if ph == "quiet":
            g, e = 0.32, 0.1
        elif ph == "rumble":
            g, e = 0.35 + 0.4 * p, 0.12 + 0.25 * p
        elif ph == "erupt":
            g, e = 1.0, 0.85 + 0.15 * math.sin(t * 2.3)
            if self.style == "explosive":
                e = 0.6 + 0.4 * self.burst
        else:
            g, e = 1.0 - 0.6 * p, 0.85 * (1 - p) + 0.1
        self.glow += (g + flick - self.glow) * min(1.0, dt * 3)
        self.emit = e
        # emission history
        self.hacc += dt
        while self.hacc >= 0.05:
            self.hacc -= 0.05
            self.hpos = (self.hpos + 1) % len(self.hist)
            self.hist[self.hpos] = self.emit
        # shake
        self.shake_t -= dt
        if self.shake_t <= 0:
            self.shake_t = 0.07
            amt = (p if ph == "rumble" else 0.5 * self.burst if ph == "erupt" else 0.0)
            self.shake = rng.choice((-1, 1)) if (self.opt("shake") and rng.random() < amt * 0.7) else 0
        # eruption: particles
        self.burst = max(0.0, self.burst - dt * 2.5)
        if ph == "erupt" or (ph == "wane" and p < 0.5):
            fade = 1.0 if ph == "erupt" else 1 - p * 2
            if self.style == "fountain":
                self.spawn_acc += dt * 110 * inten * fade
                while self.spawn_acc >= 1:
                    self.spawn_acc -= 1
                    self.spawn(rng.gauss(0, self.fspread), self.fh * rng.uniform(0.55, 1.05))
            else:
                if rng.random() < dt * 1.8 * fade:
                    self.burst = 1.0
                    for _ in range(int(rng.uniform(25, 55) * inten)):
                        self.spawn(rng.gauss(0, 7.0), rng.uniform(0.3, 1.0) * self.fh)
                self.spawn_acc += dt * 12 * inten * fade
                while self.spawn_acc >= 1:
                    self.spawn_acc -= 1
                    self.spawn(rng.gauss(0, 3.0), rng.uniform(0.15, 0.5) * self.fh)
        elif ph == "rumble" and rng.random() < dt * 6 * p:
            self.spawn(rng.gauss(0, 1.5), rng.uniform(0.05, 0.2))
        top, w, hz = self.top, self.w, self.hz
        G = 26.0
        alive = []
        for q in self.parts:
            q[4] += dt
            if q[6]:
                if q[4] < q[5] + 4.0:
                    alive.append(q)
                continue
            q[3] += G * dt
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            q[2] *= 1 - dt * 0.15
            xi = int(q[0])
            if xi < -2 or xi > w + 2 or q[1] > self.h:
                continue
            if 0 <= xi < w and q[3] > 0 and q[1] >= top[xi] and top[xi] < hz - 0.3:
                q[1] = top[xi] + 0.6
                q[6] = True
                q[5] = q[4]
                alive.append(q)
                continue
            if q[1] >= hz and self.sea:
                continue
            alive.append(q)
        self.parts = alive[-900:]
        # flows advance and cool
        for f in self.flows:
            if f.front < len(f.pts):
                f.front = min(len(f.pts), f.front + dt * f.speed * (0.5 + 0.8 * f.heat))
            if ph in ("erupt",) and t - f.born < 20:
                f.heat = min(1.0, f.heat + dt * 0.5)
            else:
                f.heat = max(0.0, f.heat - dt * 0.035)
        # lightning
        self.bolt_cd -= dt
        if self.bolt is not None:
            cells, left = self.bolt
            left -= dt
            self.bolt = (cells, left) if left > 0 else None
        elif ph == "erupt" and self.opt("plume") and self.bolt_cd <= 0:
            rate = 0.9 if self.style == "explosive" else 0.3
            if rng.random() < dt * rate * inten:
                self.make_bolt()
                self.bolt_cd = rng.uniform(0.4, 1.5)

    def spawn(self, vx, hshare):
        rng = self.rng
        hgt = max(2.0, self.ty * hshare)
        vy = -math.sqrt(2 * 26.0 * hgt)
        x = self.cx + rng.uniform(-0.6, 0.6) * self.rc
        self.parts.append([x, self.ty - 0.2, vx, vy * rng.uniform(0.9, 1.05), 0.0, rng.uniform(1.4, 3.2), False])

    def make_bolt(self):
        rng = self.rng
        tau = rng.uniform(1.0, 4.0)
        y = self.row_for_tau(tau)
        if y is None:
            return
        x = self.plume_x(tau) + rng.uniform(-1, 1) * self.plume_w(tau) * 0.5
        cells = []
        for _ in range(rng.randint(5, 12)):
            dx = rng.choice((-1, 0, 1, 1, -1))
            ch = "|" if dx == 0 else ("/" if dx < 0 else "\\")
            cells.append((int(x), int(y), ch))
            x += dx
            y += 1
            if y >= self.ty:
                break
            if rng.random() < 0.2:
                bx, by = x, y
                for _ in range(rng.randint(2, 4)):
                    d = rng.choice((-1, 1))
                    bx += d
                    by += 1
                    cells.append((int(bx), int(by), "/" if d < 0 else "\\"))
        self.bolt = (cells, rng.uniform(0.12, 0.3))

    # ------------------------------------------------------------------ plume model
    # Material emitted at time t - tau sits at height dy(tau) = Hm (1 - exp(-tau / T)).
    def plume_dy(self, tau):
        return self.Hm * (1 - math.exp(-tau / 3.2))

    def row_for_tau(self, tau):
        y = self.ty - self.plume_dy(tau)
        return y if y >= 0 else None

    def plume_x(self, tau):
        return self.cx + self.wind * tau ** 1.35 * 0.9

    def plume_w(self, tau):
        return self.rc * 0.8 + 3.4 * tau ** 0.85 + 6.0 * max(0.0, tau - 4.0) ** 0.7

    def draw_plume(self, cv):
        ty = self.ty
        if ty < 2:
            return
        Hm = self.Hm
        hist, hp, hn = self.hist, self.hpos, len(self.hist)
        t = self.t
        tile, TW, TH = self.tile, self.TW, self.TH
        w = self.w
        ramp = PLUME_RAMP if cv.ramp == RAMPS["ascii"] else cv.ramp
        rn = len(ramp) - 1
        put = cv.put
        glow = self.glow
        flash = 0.0
        if self.bolt is not None:
            flash = 0.5 + 0.5 * math.sin(t * 90)
        lit_c = (255, 120, 40)
        hot_c = (255, 200, 120)
        dark_c, pale_c = self.ash
        fl_c = (200, 190, 255)
        for y in range(int(ty), -1, -1):
            dy = ty - y
            fr = dy / Hm
            if fr >= 0.995:
                break
            tau = -3.2 * math.log(1 - fr)
            k = int(tau / 0.05)
            if k >= hn - 1:
                break
            e = hist[(hp - k) % hn]
            dens = e * math.exp(-tau / 16.0)
            if dens < 0.04:
                continue
            xc = self.plume_x(tau)
            pw = self.plume_w(tau)
            # texture travels with the material: v is keyed to emission time
            ve = (t - tau) * 7.0
            iv = int(ve) % TH
            iv2 = (iv + 5) % TH
            ivs = int(ve * 2.3 + 17) % TH
            row, row2, rows = tile[iv], tile[iv2], tile[ivs]
            lit = clamp(glow * math.exp(-dy / (self.H * 0.6 + 2)) * 1.4)
            x0 = max(0, int(xc - pw * 1.6) - 1)
            x1 = min(w, int(xc + pw * 1.6) + 2)
            inv = 1.0 / pw
            for x in range(x0, x1):
                u = (x + 0.5 - xc) * inv
                iu = int(u * 14 + 1000.5) % TW
                big = row[iu]
                small = rows[int(u * 31 + 500.5) % TW]
                a = 1.0 - u * u * 0.9 + (big - 0.5) * 2.0 + (small - 0.5) * 0.7
                if a <= 0.2:
                    continue
                val = dens * (a - 0.2) * 1.5
                if val < 0.1:
                    continue
                if val > 1.0:
                    val = 1.0
                # billows facing down catch the glow from the crater
                face = clamp(0.5 + (row2[iu] - big) * 3.0)
                c = mix(dark_c, pale_c, clamp(0.25 + 0.6 * small * face))
                gl = lit * (0.3 + 0.7 * face) * clamp(1.4 - abs(u) * 0.6)
                if gl > 0.02:
                    c = mix(c, lit_c if gl < 0.75 else hot_c, clamp(gl))
                if flash:
                    c = mix(c, fl_c, flash * 0.6 * clamp(1.2 - fr))
                lv = 0.16 + 0.5 * val + 0.3 * gl * val
                if lv > 1.0:
                    lv = 1.0
                idx = int(lv * rn + 0.5)
                if idx > 0:
                    put(x, y, ramp[idx], scale(c, 0.5 + 0.5 * lv), level=lv)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, hz, t = self.w, self.h, self.hz, self.t
        if (cv.w, cv.h) != (w, h):
            return
        self.background(cv)
        put = cv.put
        glow = self.glow
        ramp = cv.ramp
        rn = len(ramp) - 1
        star = self.pal["star"]
        for x, y, b, ph in self.stars:
            tw = b * (0.55 + 0.45 * math.sin(t * (0.8 + b * 2) + ph))
            if tw > 0.2:
                put(x, y, "." if tw < 0.5 else "·" if tw < 0.75 else "+" if b > 0.9 else "*", scale(star, 0.3 + 0.7 * tw), level=0.3)
        if self.moon:
            self.draw_moon(cv)
        # sky glow over the crater (lights the sky dome and the lower sky)
        cx, ty = self.cx, self.ty
        R = (self.H * 0.9 + 4) * (0.6 + 0.6 * glow)
        sky = self.pal["sky"]
        for y in range(max(0, int(ty - R / ASPECT * 1.2)), min(hz, int(ty + R / ASPECT))):
            for x in range(max(0, int(cx - R * 1.6)), min(w, int(cx + R * 1.6) + 1)):
                d = math.hypot((x - cx) / 1.6, (y - ty) * ASPECT) / R
                if d >= 1:
                    continue
                g = (1 - d) ** 2 * glow
                if g > 0.05:
                    i = y * w + x
                    lvl = 0.1 + 0.5 * g
                    if lvl > cv.lv[i]:
                        k = int(g * 9 + _hash(x, y, 3) * 1.5)
                        put(x, y, HALO[min(k, len(HALO) - 1)], mix(sky[-1], GLOW, clamp(g * 1.6)), level=lvl)
        if self.opt("plume"):
            self.draw_plume(cv)
        self.draw_cone(cv)
        self.draw_flows(cv)
        self.draw_parts(cv)
        if self.bolt is not None:
            for x, y, ch in self.bolt[0]:
                if 0 <= x < w and 0 <= y < self.ty:
                    put(x, y, ch, (235, 225, 255), level=1.0)
        self.draw_base(cv)
        if self.shake:
            s = self.shake
            ch, fg, lv = cv.ch, cv.fg, cv.lv
            for y in range(hz):
                a, b = y * w, (y + 1) * w
                ch[a:b] = ch[a + s:b] + ch[a:a + s] if s > 0 else ch[b + s:b] + ch[a:b + s]
                fg[a:b] = fg[a + s:b] + fg[a:a + s] if s > 0 else fg[b + s:b] + fg[a:b + s]
                lv[a:b] = lv[a + s:b] + lv[a:a + s] if s > 0 else lv[b + s:b] + lv[a:b + s]

    def draw_moon(self, cv):
        """A crescent drawn with half blocks (two samples per cell) and a faint halo."""
        mx, my, r, phase = self.moon
        lit = (250, 240, 215)
        for y in range(int(my - r / ASPECT) - 2, int(my + r / ASPECT) + 3):
            for x in range(int(mx - r * 1.6) - 1, int(mx + r * 1.6) + 2):
                dx = (x + 0.5 - mx) / r
                hits = []
                for sub in (0.25, 0.75):
                    dy = (y + sub - my) * ASPECT / r
                    sx = dx + phase * 1.3
                    hits.append(dx * dx + dy * dy <= 1 and sx * sx + dy * dy * 1.05 > 1)
                dc = dx * dx + ((y + 0.5 - my) * ASPECT / r) ** 2
                if hits[0] or hits[1]:
                    ch = "█" if hits[0] and hits[1] else "▀" if hits[0] else "▄"
                    cv.put(x, y, ch, mix(lit, (200, 190, 175), clamp(dc)), level=0.9)
                elif dc < 2.6:
                    cv.shade(x, y, 0.1 * (2.6 - dc), (140, 140, 180))

    def draw_cone(self, cv):
        put = cv.put
        glow = self.glow
        ramp = cv.ramp
        rn = len(ramp) - 1
        gc = (255, 96, 30)
        ascii = ramp == RAMPS["ascii"]
        for x, y, lvl, col, near, ch in self.cone:
            g = near * glow
            v = min(1.0, lvl + 0.35 * g)
            if not ascii:
                idx = int(v * rn + 0.5)
                ch = ramp[idx] if idx > 0 else "."
            c = mix(col, gc, clamp(g * 1.1)) if g > 0.02 else col
            put(x, y, ch, scale(c, 0.55 + 0.6 * v), level=v)
        edge_c = (120, 84, 96) if self.moon is None else (130, 130, 170)
        for x, y, ch, near in self.edge:
            g = near * glow
            put(x, y, ch, mix(edge_c, (255, 170, 80), clamp(g * 1.2)), level=0.5)
        # lava lake glowing in the crater
        cx, rc, ty = self.cx, self.rc, self.ty
        y = int(ty)
        t = self.t
        for x in range(int(cx - rc) + 1, int(cx + rc)):
            if 0 <= x < self.w and self.top[x] >= y - 0.5:
                f = 0.5 + 0.5 * math.sin(x * 1.3 + t * 3.1)
                put(x, y, "~" if f > 0.5 else "=", lava_col(0.45 + 0.4 * glow + 0.15 * f))

    def draw_flows(self, cv):
        put = cv.put
        t = self.t
        w = self.w
        for f in self.flows:
            n = int(f.front)
            pts = f.pts
            heat = f.heat
            for i in range(min(n, len(pts))):
                x, y = pts[i]
                # older parts of a flow crust over first; channels pulse downstream
                age = (n - i) / max(1.0, len(pts))
                local = heat * (1.0 - 0.55 * age) + 0.12
                pulse = 0.5 + 0.5 * math.sin(i * 0.7 - t * 4.0 + f.phase)
                temp = local * (0.75 + 0.3 * pulse)
                if i + 1 < len(pts):
                    dx = pts[i + 1][0] - x
                else:
                    dx = 0
                ch = "|" if dx == 0 else "/" if dx < 0 else "\\"
                if abs(dx) > 1:
                    ch = "_"
                if temp < 0.2:
                    put(x, y, ":" if (x + y) % 2 else ".", lava_col(temp))
                    continue
                put(x, y, ch, lava_col(temp))
                if temp > 0.55 and i % 3 != 1:     # a second strand: the channel is braided
                    xx = x + (1 if (i // 3) % 2 else -1)
                    if 0 <= xx < w and y > self.top[xx]:
                        put(xx, y, ch, lava_col(temp * 0.85))
                elif temp > 0.45:     # glowing levees either side
                    for s in (-1, 1):
                        xx = x + s
                        if 0 <= xx < w and y > self.top[xx]:
                            put(xx, y, "." if pulse < 0.5 else ":", scale(lava_col(temp * 0.7), 0.6))
                if dx and abs(dx) > 1:  # fill horizontal runs
                    for k in range(1, abs(dx)):
                        put(x + (k if dx > 0 else -k), y, "_", lava_col(temp * 0.9))
            if 0 < n < len(pts) and heat > 0.3:
                x, y = pts[n - 1]
                put(x, y, "@", lava_col(min(1.0, heat * 1.05)))

    def draw_parts(self, cv):
        put = cv.put
        shade = cv.shade
        hz = self.hz
        for x, y, vx, vy, age, life, landed in self.parts:
            if landed:
                temp = 0.55 - (age - life) * 0.14
                if temp > 0.05:
                    put(x, y, "*" if temp > 0.45 else "," if temp > 0.25 else ".", lava_col(temp))
                continue
            temp = 1.0 - age / life * 0.75
            c = lava_col(temp)
            if temp > 0.75:
                ch = "*" if temp > 0.88 else "+"
                shade(x - 1, y, 0.22, GLOW)
                shade(x + 1, y, 0.22, GLOW)
            elif temp > 0.5:
                ch = "+" if temp > 0.62 else "'"
            else:
                ch = "."
            put(x, y, ch, c, level=1.0)
            # short glowing tail behind fast embers
            if temp > 0.6 and abs(vy) > 8:
                put(x - vx * 0.05, y - vy * 0.05, "'" if vy < 0 else ".", scale(c, 0.5))

    def draw_base(self, cv):
        w, h, hz, t = self.w, self.h, self.hz, self.t
        put = cv.put
        glow = self.glow
        cx = self.cx
        if not self.sea:
            # plain: lava glow on the ground near the foot of the cone
            for y in range(hz, h):
                for x in range(w):
                    d = abs(x - cx) / (self.RL + self.RR) * 2
                    g = glow * math.exp(-d * 2.2) * (1 - (y - hz) / max(1, h - hz)) * 0.7
                    if g > 0.08 and cv.ch[y * w + x] != " ":
                        cv.fg[y * w + x] = tuple(int(v) & ~3 for v in mix(cv.fg[y * w + x], (200, 70, 30), g))
            return
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        sin = math.sin
        deep = (16, 26, 58)
        for y in range(hz, h):
            d = y - hz
            p = (d + 1) / max(1, h - hz)
            src = hz - 1 - int(d * 1.7)
            amp = 0.6 + 2.2 * p
            for x in range(w):
                wob = sin(y * 1.7 + t * 1.9 + x * 0.13) + 0.6 * sin(x * 0.37 - t * 1.3 + y)
                sx = int(x + wob * amp)
                if src >= 0 and 0 <= sx < w:
                    i = src * w + sx
                    if lv[i] > 0.12 and fg[i] is not None and ch[i] != " " and (lv[i] > 0.4 or fg[i][0] > 90):
                        c = fg[i]
                        k = 0.8 - 0.3 * p
                        rc = (c[0] * k, c[1] * k * 0.9, c[2] * k + 18)
                        put(x, y, "~" if wob > 0.3 else "-" if wob > -0.6 else "=", rc, level=0.3)
                        continue
                # glitter path of the eruption's light, then dark ripples
                r = 0.5 + 0.5 * wob
                dxp = abs(x - cx)
                pw = self.rc * (1.5 + 2.5 * p) + 2
                if dxp < pw * 1.6:
                    k = (1 - dxp / (pw * 1.6)) * glow
                    sp = 0.5 + 0.5 * sin(x * 2.1 + y * 4.3 + t * 2.7 + wob * 2)
                    g = k * (0.3 + 0.7 * sp)
                    if g > 0.22:
                        put(x, y, "=" if g > 0.6 else "-" if g > 0.4 else "~", lava_col(0.15 + 0.6 * g), level=0.4)
                        continue
                if r > 0.72 or (x * 7 + y * 3) % 5 == 0:
                    gx = math.exp(-dxp / (self.rc * 6 + 6)) * glow
                    c = mix(deep, (150, 50, 30), gx * 0.8)
                    put(x, y, "-" if r > 0.86 else "." if r < 0.76 else "~", scale(c, 0.9 + r * 0.7), level=0.15)
