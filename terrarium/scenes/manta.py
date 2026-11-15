"""Manta rays gliding and banking in a slow ballet through sunlit blue water."""
import math

from ..engine import ASPECT, Scene, clamp, gradient, hsv, mix, noise2, scale, smoothstep
from .whale import dir_glyph

TAU = math.tau

DORSAL = [(16, 24, 46), (38, 58, 98), (75, 105, 155), (150, 180, 222), (230, 240, 255)]
DORSAL_BLACK = [(6, 8, 16), (16, 20, 34), (36, 44, 66), (80, 92, 120), (170, 180, 200)]
VENTRAL = [(60, 70, 90), (140, 155, 175), (215, 225, 238), (250, 252, 255)]


def leading(ay):
    """x of the wing's leading edge at |y| = ay (unit half-span)."""
    return 0.34 - 0.78 * ay ** 1.3 + 0.1 * math.sin(math.pi * ay)


def trailing(ay):
    return -0.26 - 0.2 * (1 - ay) ** 1.8 + 0.16 * math.sin(math.pi * ay) ** 2 - 0.2 * ay ** 4


class Manta:
    def __init__(self, rng, S, w, h, k, n):
        self.S = S                                  # half wingspan in cells
        self.seed = rng.randrange(1 << 15)
        self.black = rng.random() < 0.18            # melanistic morph
        self.patch = rng.uniform(0.0, 1.0)          # size of the white shoulder patches
        self.spots = rng.uniform(0.2, 0.75)         # belly spots, unique per animal
        self.flap = rng.uniform(0.14, 0.2)          # flaps per second
        self.amp = rng.uniform(0.16, 0.26)
        self.phase = rng.uniform(0, TAU)
        self.ceph = rng.uniform(0.0, 1.0)           # how unrolled the cephalic fins are
        self.remoras = [(rng.uniform(-0.12, 0.05), rng.uniform(-0.14, 0.14)) for _ in range(rng.choice((0, 1, 1, 2, 3)))]
        # path genome: a slow loop through the water column
        self.kind = rng.choice(("loop", "eight", "wave", "loop"))
        self.cx = w * (0.3 + 0.4 * (k + rng.uniform(0.2, 0.8)) / n)
        self.cy = h * ASPECT * rng.uniform(0.35, 0.62)
        self.ax = w * rng.uniform(0.12, 0.24)
        self.ay = h * ASPECT * rng.uniform(0.06, 0.14)
        self.az = rng.uniform(10, 22)
        self.om = rng.uniform(0.035, 0.06) * rng.choice((-1, 1))
        self.t0 = rng.uniform(0, 100)
        self.prev_yaw = None
        self.roll = 0.0
        self.pos = (0.0, 0.0, 0.0)
        self.basis = None
        self.samples = None
        self.sample_step = None

    def path(self, t):
        a = self.om * (t + self.t0) * TAU
        if self.kind == "loop":
            return (self.cx + self.ax * math.sin(a), self.cy + self.ay * math.sin(a * 2 + 1), self.az * math.cos(a))
        if self.kind == "eight":
            return (self.cx + self.ax * math.sin(a), self.cy + self.ay * math.sin(a + 0.5), self.az * math.sin(2 * a))
        return (self.cx + self.ax * math.sin(a), self.cy + self.ay * 1.3 * math.sin(a * 3), self.az * math.cos(a) * 0.6)

    def build_samples(self, step):
        """Planform samples in unit coords: (x, y, ay, region) with region 0 wing, 1 cephalic fin."""
        out = []
        n = int(1.0 / step) + 1
        for i in range(-n, n + 1):
            y = i * step
            ay = abs(y)
            if ay > 1.0:
                continue
            xl = leading(ay)
            xt = trailing(ay)
            x = xt
            while x <= xl:
                if ay < 0.16 and x > 0.29 + 0.03 * (1 - (ay / 0.16) ** 2):
                    break
                out.append((x, y, ay, 0))
                x += step
        # cephalic fins: two short lobes in front of the head
        x = 0.27
        while x < 0.45:
            for yy in (0.11, 0.135, 0.16):
                for sgn in (-1, 1):
                    out.append((x, yy * sgn, yy, 1))
            x += step
        self.samples = out
        self.sample_step = step


class Fish:
    __slots__ = ("ox", "oy", "oz", "ph", "sp")


class MantaScene(Scene):
    name = "manta"
    title = "Manta rays"
    blurb = "manta rays gliding and banking in a slow ballet through sunlit blue water"
    tags = ("ocean", "nature", "calm")
    options = {
        "count": (0, "number of mantas (0 = random for the screen size)"),
        "fish": (True, "schools of silver fish"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        n = self.opt("count")
        if n <= 0:
            n = max(1, min(5, int(round(rng.uniform(1.6, 3.2) * (w * h / 4800) ** 0.35))))
        n = min(n, 12)
        base = min(w * 0.22, h * ASPECT * 0.38) * rng.uniform(0.9, 1.1)
        self.mantas = []
        for k in range(n):
            S = max(4.0, base * rng.uniform(0.7, 1.15) * (1.0 if k == 0 else 0.85))
            self.mantas.append(Manta(rng, S, w, h, k, n))
        self.tilt = rng.uniform(0.85, 1.05)         # camera looks down on the rays from above
        self.water = hsv(rng.uniform(0.53, 0.58), rng.uniform(0.55, 0.75), 0.95)
        self.sun = (rng.uniform(-0.4, 0.4), 1.0, rng.uniform(0.1, 0.4))
        self.ray_slant = rng.uniform(0.15, 0.45) * rng.choice((-1, 1))
        self.ray_freq = rng.uniform(0.08, 0.14)
        nm = int(w * h / 30 * self.density)
        self.motes = [[rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.15, 1.0), rng.uniform(0, 9)] for _ in range(nm)]
        self.schools = []
        if self.opt("fish"):
            for _ in range(rng.randint(1, 2)):
                self.schools.append(self.new_school(start=rng.uniform(0, 1)))
        self.zbuf = None

    def new_school(self, start=0.0):
        rng = self.rng
        w, h = self.w, self.h
        d = rng.choice((-1, 1))
        n = int(rng.uniform(14, 32) * (w * h / 4800) ** 0.5 * self.density) + 5
        fish = []
        rad = rng.uniform(0.08, 0.16) * w
        for _ in range(n):
            f = Fish()
            a = rng.uniform(0, TAU)
            r = rad * math.sqrt(rng.random())
            f.ox, f.oy = math.cos(a) * r, math.sin(a) * r * rng.uniform(0.3, 0.6)
            f.oz = rng.uniform(-1, 1)
            f.ph = rng.uniform(0, TAU)
            f.sp = rng.uniform(0.8, 1.2)
            fish.append(f)
        span = w + 2 * rad + 10
        return {"dir": d, "x": -rad - 5 + span * start if d > 0 else w + rad + 5 - span * start,
                "y": h * rng.uniform(0.2, 0.8), "speed": rng.uniform(3, 6), "fish": fish, "rad": rad,
                "wob": rng.uniform(0, TAU)}

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        t = self.t
        for m in self.mantas:
            p = m.path(t)
            q = m.path(t + 0.5)
            vx, vy, vz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
            vl = math.sqrt(vx * vx + vy * vy + vz * vz) or 1.0
            fx, fy, fz = vx / vl, -vy / vl, vz / vl      # world: y up (path y grows down)
            yaw = math.atan2(fz, fx)
            if m.prev_yaw is not None and dt > 0:
                dy = (yaw - m.prev_yaw + math.pi) % TAU - math.pi
                target = clamp(-dy / dt * 1.8, -1.3, 1.3)
                m.roll += (target - m.roll) * min(1.0, dt * 1.5)
            m.prev_yaw = yaw
            m.phase += dt * m.flap * TAU
            m.pos = p
            # basis: forward f, right r, up u
            rx, ry, rz = -fz, 0.0, fx                # f x (0,1,0)
            rl = math.sqrt(rx * rx + rz * rz) or 1.0
            rx, rz = rx / rl, rz / rl
            ux, uy, uz = ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx
            c, s = math.cos(m.roll), math.sin(m.roll)
            r2 = (rx * c + ux * s, ry * c + uy * s, rz * c + uz * s)
            u2 = (ux * c - rx * s, uy * c - ry * s, uz * c - rz * s)
            m.basis = ((fx, fy, fz), r2, u2)
        for sch in self.schools:
            sch["x"] += sch["dir"] * sch["speed"] * dt
            sch["y"] += math.sin(t * 0.3 + sch["wob"]) * dt * 0.8
        w = self.w
        for i, sch in enumerate(self.schools):
            if (sch["dir"] > 0 and sch["x"] - sch["rad"] > w + 4) or (sch["dir"] < 0 and sch["x"] + sch["rad"] < -4):
                self.schools[i] = self.new_school()
        for mo in self.motes:
            mo[1] += dt * 0.15 * mo[2]
            mo[0] += dt * 0.25 * math.sin(t * 0.3 + mo[3])
            if mo[1] >= self.h:
                mo[1] -= self.h
                mo[0] = self.rng.uniform(0, w)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        self.draw_water(cv)
        w, h = cv.w, cv.h
        self.zbuf = [-1e9] * (w * h)
        order = sorted(self.mantas, key=lambda m: self.depth_of(m.pos))
        schools = list(self.schools)
        for m in order:
            # schools between the mantas, by depth
            self.draw_manta(cv, m)
        for sch in schools:
            self.draw_school(cv, sch)

    def depth_of(self, p):
        return p[2] * math.cos(self.tilt) - (-(p[1] / ASPECT)) * 0

    def draw_water(self, cv):
        t = self.t
        w, h = self.w, self.h
        sl = self.ray_slant
        off = int(abs(sl) * h) + 2
        fr = self.ray_freq
        pat = []
        for q in range(-off, w + off + 1):
            v = (math.sin(q * fr + t * 0.15) * 0.55 + math.sin(q * fr * 2.3 - t * 0.25) * 0.35
                 + math.sin(q * fr * 0.41 + t * 0.07) * 0.4)
            pat.append((v - 0.35) * 0.5 if v > 0.35 else 0.0)
        col = self.water
        for y in range(h):
            fall = (1 - y / h) ** 1.3
            if fall < 0.05:
                break
            shift = int(y * sl) + off
            for x in range(w):
                v = pat[x + shift]
                if v > 0:
                    cv.shade(x, y, v * fall, col)
        for x in range(w):
            v = noise2(x * 0.1, t * 0.5, 5) * 0.5 + 0.5
            if v > 0.4:
                cv.put(x, 0, "~" if v > 0.6 else "-", scale((170, 225, 255), 0.35 + 0.6 * v), level=0.35)
        for x, y, z, _ in self.motes:
            cv.shade(x, y, 0.06 + 0.14 * z, (140, 190, 225))

    @staticmethod
    def surface(m, x, ay):
        """Flap displacement z and its slopes at unit coords (x, |y|)."""
        k = smoothstep(0.12, 1.0, ay)
        arg = m.phase - 2.6 * (0.3 - x) - 0.8 * ay
        wave = math.sin(arg)
        kk = k ** 1.25
        z = m.amp * kk * wave
        dzdx = m.amp * kk * math.cos(arg) * 2.6
        dzdy = m.amp * (1.6 * k ** 0.25 if 0.12 < ay < 1 else 0.0) * wave
        if ay < 0.25:            # domed body
            q = 1 - ((x - 0.05) / 0.35) ** 2
            if q > 0:
                z += 0.07 * (1 - (ay / 0.25) ** 2) * q
        return z, dzdx, dzdy

    @staticmethod
    def region(x, ay):
        """0 wing/body, 1 cephalic fin, None outside."""
        if ay <= 1.0:
            xl = leading(ay)
            if ay < 0.16:
                xl = min(xl, 0.32 + 0.03 * (1 - (ay / 0.16) ** 2))
            if trailing(ay) <= x <= xl:
                return 0
        if 0.095 <= ay <= 0.175 and 0.3 <= x <= 0.47 - 0.6 * (ay - 0.135) ** 2:
            return 1
        return None

    def draw_manta(self, cv, m):
        if m.basis is None:
            return
        w, h = cv.w, cv.h
        (fx, fy, fz), (rx, ry, rz), (ux, uy, uz) = m.basis
        px, py, pz = m.pos                          # py: aspect units, grows down
        S = m.S * (1 + pz * 0.012)
        ce, se = math.cos(self.tilt), math.sin(self.tilt)
        # screen images of the local axes (x cells, y aspect units down)
        Fx, Fy = fx * S, (-fy * ce + fz * se) * S
        Rx, Ry = rx * S, (-ry * ce + rz * se) * S
        Ux, Uy = ux * S, (-uy * ce + uz * se) * S
        det = Fx * Ry - Fy * Rx
        if abs(det) < 0.1 * S * S:
            self.draw_edge_on(cv, m, S, ce, se)
            det = 0.0
        idet = 1.0 / det if det else 0.0
        Fd = (fz * ce + fy * se) * S
        Rd = (rz * ce + ry * se) * S
        Ud = (uz * ce + uy * se) * S
        vx, vy, vz = 0.0, se, ce
        lx, ly, lz = self.sun
        ll = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / ll, ly / ll, lz / ll
        fog = clamp(0.35 - pz / 60)                 # far mantas fade into the blue
        zb = self.zbuf
        ch, fg, lv, bc = cv.ch, cv.fg, cv.lv, cv.bc
        ramp = cv.ramp
        nr = len(ramp) - 1
        dorsal = DORSAL_BLACK if m.black else DORSAL
        sd = m.seed
        patch = m.patch
        spots = m.spots
        water = self.water
        sqrt = math.sqrt
        surface = self.surface
        region = self.region
        ext = 1.25 * S
        x0, x1 = max(0, int(px - ext)), min(w, int(px + ext) + 1)
        y0, y1 = max(0, int((py - ext) / ASPECT)), min(h, int((py + ext) / ASPECT) + 1)
        for iy in range(y0, y1 if det else y0):
            Y = (iy + 0.5) * ASPECT - py
            for ix in range(x0, x1):
                X = ix + 0.5 - px
                # solve for the local (x, y), refining once for the flap displacement
                a = (X * Ry - Y * Rx) * idet
                b = (Fx * Y - Fy * X) * idet
                ay = b if b > 0 else -b
                if ay > 1.05 or a < -0.5 or a > 0.5:
                    continue
                z, dzdx, dzdy = surface(m, a, ay)
                X2, Y2 = X - Ux * z, Y - Uy * z
                a = (X2 * Ry - Y2 * Rx) * idet
                b = (Fx * Y2 - Fy * X2) * idet
                ay = b if b > 0 else -b
                reg = region(a, ay)
                if reg is None:
                    continue
                depth = pz + Fd * a + Rd * b + Ud * z
                i = iy * w + ix
                if depth <= zb[i]:
                    continue
                zb[i] = depth
                if reg == 1:             # cephalic fins curl down and inward
                    dzdx = -0.6 * (a - 0.3) / 0.17
                    dzdy = 0.0
                if b < 0:
                    dzdy = -dzdy
                nlx, nly = -dzdx * 2.5, -dzdy * 2.5
                nl = sqrt(nlx * nlx + nly * nly + 1.0)
                nlx, nly, nlz = nlx / nl, nly / nl, 1.0 / nl
                nwx = fx * nlx + rx * nly + ux * nlz
                nwy = fy * nlx + ry * nly + uy * nlz
                nwz = fz * nlx + rz * nly + uz * nlz
                facing = nwx * vx + nwy * vy + nwz * vz
                sun = nwx * lx + nwy * ly + nwz * lz
                edge = min(leading(ay) - a, a - trailing(ay), 1 - ay) if reg == 0 else 0.05
                if facing >= 0:
                    # back: dark, with pale shoulder patches and a sunlit sheen
                    lit = clamp(0.3 + 0.7 * sun)
                    c = gradient(dorsal, 0.3 + lit * 0.65)
                    if not m.black and 0.0 < a < 0.24 and 0.12 < ay < 0.2 + 0.35 * patch:
                        d = (ay - 0.12) / (0.08 + 0.35 * patch)
                        if a > 0.22 * d - 0.02 + 0.06 * noise2(a * 9, ay * 9, sd):
                            c = mix(c, (200, 212, 228), 0.7)
                            lit = max(lit, 0.6)
                    v = 0.55 + 0.45 * lit
                    if edge < 0.045:
                        c = mix(c, (190, 225, 255), 0.65)     # sunlit rim along the wing edges
                        v = max(v, 0.8)
                else:
                    # belly: white, with this animal's own spots, dark margins and gill slits
                    lit = clamp(0.6 + 0.4 * (-sun))
                    c = gradient(VENTRAL, 0.35 + 0.6 * lit)
                    if ay < 0.55 and noise2(a * 11 + sd, b * 11, sd) > 1 - spots * 0.9:
                        c = mix(c, (40, 45, 60), 0.75)
                    if reg == 0 and 0.06 < a < 0.24 and 0.07 < ay < 0.15 and int((a - 0.06) / 0.035) % 2 == 0:
                        c = mix(c, (50, 55, 70), 0.6)
                    if edge < 0.06:
                        c = mix(c, (60, 65, 85), 0.7)
                    v = 0.5 + 0.5 * lit

                c = mix(c, water, fog * 0.55)
                v *= 1 - fog * 0.35
                if v > 1:
                    v = 1.0
                idx = int(v * nr + 0.5)
                ch[i] = ramp[idx] if idx > 0 else ramp[1]
                kk = 0.3 + 0.7 * v
                r_, g_, b_ = c[0] * kk, c[1] * kk, c[2] * kk
                fg[i] = (int(r_) & ~3 if r_ < 252 else 252, int(g_) & ~3 if g_ < 252 else 252,
                         int(b_) & ~3 if b_ < 252 else 252)
                lv[i] = v
                bc[i] = c
        ph = m.phase
        # eyes on the sides of the head
        for sgn in (-1, 1):
            ex, ey = 0.3, 0.165 * sgn
            sx, sy, dep = self.proj(m, ex, ey, 0.0)
            ix, iy = int(sx), int(sy)
            if 0 <= ix < w and 0 <= iy < h and dep >= zb[iy * w + ix] - 0.6:
                cv.put(ix, iy, "o", mix((20, 25, 35), water, fog * 0.4), 1.0)
        # remoras riding under the belly
        for rxl, ryl in m.remoras:
            sx, sy, dep = self.proj(m, rxl, ryl, -0.06)
            ix, iy = int(sx), int(sy)
            if 0 <= ix < w and 0 <= iy < h and dep > zb[iy * w + ix]:
                head = ">" if fx > 0 else "<"
                body = "=" if abs(fx) > 0.3 else "|"
                cv.put(ix, iy, head, mix((190, 195, 200), water, fog * 0.5), 0.8)
                cv.put(ix - (1 if fx > 0 else -1), iy, body, mix((150, 155, 165), water, fog * 0.5), 0.8)
        # tail: a thin whip trailing behind
        prev = None
        n = int(S * 1.3) + 4
        for j in range(n + 1):
            s = j / n
            tx = -0.44 - 0.85 * s
            ty = 0.04 * math.sin(self.t * 1.5 + s * 5) * s
            tz = -0.05 * math.sin(ph - 2.6 * (0.3 - tx)) * s
            sx, sy, dep = self.proj(m, tx, ty, tz)
            if prev is not None:
                ix, iy = int(sx), int(sy)
                if 0 <= ix < w and 0 <= iy < h:
                    if dep > zb[iy * w + ix]:
                        g = dir_glyph(sx - prev[0], (sy - prev[1]) * ASPECT)
                        cv.put(ix, iy, g, mix(gradient(dorsal, 0.6 * (1 - s)), water, fog * 0.6 + 0.3 * s), 0.5)
            prev = (sx, sy)

    def draw_edge_on(self, cv, m, S, ce, se):
        """The wing plane is seen edge-on: splat planform samples as a thin bright sliver."""
        step = 0.42 / S
        if m.samples is None or abs(m.sample_step - step) > step * 0.25:
            m.build_samples(step)
        zb = self.zbuf
        w, h = cv.w, cv.h
        col = mix((150, 170, 200), self.water, clamp(0.5 - m.pos[2] / 45) * 0.5)
        for x, y, ay, reg in m.samples[::2]:
            z = self.surface(m, x, ay)[0]
            sx, sy, dep = self.proj(m, x, y, z)
            ix, iy = int(sx), int(sy)
            if 0 <= ix < w and 0 <= iy < h and dep > zb[iy * w + ix]:
                zb[iy * w + ix] = dep
                cv.shade(ix, iy, 0.75, col, "over")

    def proj(self, m, x, y, z):
        """Local unit coords of manta m -> (screen x, screen row, depth toward the camera)."""
        (fx, fy, fz), (rx, ry, rz), (ux, uy, uz) = m.basis
        px, py, pz = m.pos
        S = m.S * (1 + pz * 0.012)
        ce, se = math.cos(self.tilt), math.sin(self.tilt)
        ox = (fx * x + rx * y + ux * z) * S
        oy = (fy * x + ry * y + uy * z) * S
        oz = (fz * x + rz * y + uz * z) * S
        return px + ox, (py - oy * ce + oz * se) / ASPECT, pz + oz * ce + oy * se

    def draw_school(self, cv, sch):
        t = self.t
        d = sch["dir"]
        head = ">" if d > 0 else "<"
        w, h = cv.w, cv.h
        for f in sch["fish"]:
            # each fish wanders a little around its slot; flashes ripple through the school
            ox = f.ox + math.sin(t * 0.7 * f.sp + f.ph) * 1.5
            oy = f.oy + math.sin(t * 0.9 * f.sp + f.ph * 2) * 0.6
            x = sch["x"] + ox
            y = sch["y"] + oy / ASPECT * 2 + math.sin(t * 0.5 + ox * 0.08) * 1.2
            ix, iy = int(x), int(y)
            if not (0 <= ix < w and 0 <= iy < h):
                continue
            fl = math.sin(t * 2.5 - ox * 0.25 * d + f.ph * 0.3)
            b = 0.15 + 0.85 * (fl ** 4 if fl > 0 else 0.0)
            col = mix((60, 90, 125), (240, 248, 255), b)
            if f.oz < -0.3:
                col = mix(col, self.water, 0.4)
            cv.put(ix, iy, head, col, 0.6)
            tail = ix - d
            if 0 <= tail < w and b > 0.5:
                cv.put(tail, iy, "-", scale(col, 0.7), 0.5)
