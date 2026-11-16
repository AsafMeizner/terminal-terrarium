"""Two koi chasing each other around a yin-yang circle inside a swirling vortex.

Inspired by @buildmeri's "Koi with Python" reel. One koi is silver-white, the other orange-gold;
each is a follow-the-leader spine (shapes.Chain) with a body stamped along it, and long silk fins
that trail behind along the path the fish has swum, so they ripple like ribbons. Around them the
water turns: rotating ripple rings, spiral arms or a starfield of current streaks, and sparkles.
"""
import math

from ..engine import ASPECT, Canvas, Scene, clamp, mix, noise2, scale
from ..shapes import Chain

TAU = math.tau
WHITE = (255, 255, 255)

# water palettes: (deep, mid, ring color, sparkle color)
WATERS = {
    "midnight": ((4, 10, 34), (20, 52, 120), (110, 160, 255), (200, 225, 255)),
    "teal": ((2, 18, 26), (10, 70, 90), (90, 210, 220), (200, 255, 250)),
    "indigo": ((10, 6, 36), (52, 30, 120), (160, 130, 255), (230, 210, 255)),
    "ink": ((6, 8, 14), (40, 46, 62), (150, 165, 190), (240, 236, 220)),
}


class Koi:
    def __init__(self, rng, kind, L, phase, n=20):
        self.kind = kind                 # "white" or "gold"
        self.L = L
        self.n = n
        self.W = L * rng.uniform(0.11, 0.13)
        self.phase = phase               # angle on the orbit
        self.seed = rng.randrange(1 << 12)
        self.fin = rng.uniform(0.45, 0.85)        # tail length, in body lengths
        self.pec = rng.uniform(0.18, 0.3)         # pectoral fin length
        self.wig = rng.uniform(0.0, TAU)
        self.ox = self.oy = 0.0                    # offset from the orbit (scatter / pointer lean)
        self.vx = self.vy = 0.0
        if kind == "white":
            self.base = rng.choice([(236, 240, 250), (228, 232, 246), (242, 238, 228)])
            self.patch = rng.choice([None, (235, 50, 35), (235, 50, 35)])
            self.finc = (190, 210, 255)
        else:
            self.base = rng.choice([(255, 140, 30), (255, 165, 40), (250, 120, 25), (255, 190, 70)])
            self.patch = rng.choice([None, (215, 35, 25), (200, 25, 40)])
            self.finc = (255, 175, 100)
        self.amount = rng.uniform(-0.1, 0.35)      # how much patch
        self.pscale = rng.uniform(2.0, 4.0)
        self.span = rng.uniform(0.9, 1.05)        # how far round the circle the body sweeps
        self.chain = None
        self.trail = []                             # recent tail positions, the path the fins follow


class YinYang(Scene):
    name = "yinyang"
    title = "Yin Yang Koi"
    blurb = "a white koi and a golden koi chasing each other around a swirling yin-yang vortex"
    tags = ("water", "zen", "calm", "creatures")
    interactions = "click to send a ripple, point to tempt the koi"
    options = {
        "vortex": ("random", "random, rings, spiral or stars"),
        "water": ("random", "random, midnight, teal, indigo or ink"),
        "speed": (1.0, "how fast the koi circle"),
        "fins": (1.0, "fin and tail length"),
        "sparkle": (1.0, "amount of sparkles"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        v = self.opt("vortex")
        self.style = v if v in ("rings", "spiral", "stars") else rng.choice(("rings", "spiral", "stars", "rings"))
        wat = self.opt("water")
        self.water = WATERS[wat] if wat in WATERS else WATERS[rng.choice(["midnight", "midnight", "teal", "indigo", "ink"])]
        self.cx, self.cy = w / 2, h * ASPECT / 2                  # stretched space
        self.big = min(w, h * ASPECT) * 0.5
        self.R0 = self.big * rng.uniform(0.7, 0.78)
        self.dir = rng.choice((-1, 1))
        self.omega = rng.uniform(0.32, 0.48) * self.opt("speed") * self.dir
        self.breath = rng.uniform(0.12, 0.22)                     # how far they spiral in and out
        self.breath_rate = rng.uniform(0.15, 0.25)
        L = max(6.0, self.R0 * 1.7)
        self.dt_last = 1 / 30
        self.koi = [Koi(rng, "white", L, 0.0), Koi(rng, "gold", L, math.pi)]
        if rng.random() < 0.5:
            self.koi.reverse()
            self.koi[0].phase, self.koi[1].phase = 0.0, math.pi
        self.theta = rng.uniform(0, TAU)
        for k in self.koi:
            self.place(k, init=True)
        # vortex structure
        self.rings = []
        nr = rng.randint(7, 11)
        for i in range(nr):
            r = self.big * (0.18 + 1.75 * ((i + rng.random() * 0.6) / nr) ** 1.15)
            arcs = [(rng.uniform(0, TAU), rng.uniform(0.6, 2.6)) for _ in range(rng.randint(2, 4))]
            self.rings.append([r, arcs, rng.uniform(0.6, 1.4), rng.choice(".-~:")])
        self.arms = rng.randint(2, 4)
        self.twist = rng.uniform(1.6, 3.0) * self.dir
        self.stars = [self.new_star(rng.uniform(0.15, 1.9) * self.big) for _ in range(self.count(150))]
        self.sparks = [[rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0, TAU), rng.uniform(0.5, 2.0)]
                       for _ in range(int(self.count(18) * max(0.0, self.opt("sparkle"))))]
        self.ripples = []         # [x, y (stretched), radius, max]
        self.static = None
        self.build_background()

    def new_star(self, r):
        rng = self.rng
        return [r, rng.uniform(0, TAU), rng.uniform(0.6, 1.4), rng.uniform(0.2, 1.0)]

    # ------------------------------------------------------------------ motion
    def orbit_radius(self):
        return self.R0 * (1 - self.breath * (0.5 + 0.5 * math.sin(self.t * self.breath_rate)))

    def shape(self, k):
        """Target spine in yin-yang form: the head in its bulb, the body spiralling out to the rim
        and sweeping half a turn back. The whole figure turns with theta."""
        R = self.orbit_radius()
        b = 0.5 + 0.5 * math.sin(self.t * self.breath_rate * 1.7 + 1.0)
        r0, r1 = R * (0.36 + 0.08 * b), R * (0.8 + 0.06 * b)
        sweep = math.pi * (0.74 + 0.1 * b) * k.span
        a0 = self.theta + k.phase
        out = []
        for i in range(k.n + 1):
            s = i / k.n
            a = a0 - self.dir * sweep * s
            r = r0 + (r1 - r0) * s ** 0.85
            out.append((self.cx + math.cos(a) * r, self.cy + math.sin(a) * r))
        return out

    def place(self, k, init=False):
        tgt = self.shape(k)
        if init:
            pts = [(x, y / ASPECT) for x, y in tgt]
            seg = sum(math.hypot(tgt[i + 1][0] - tgt[i][0], tgt[i + 1][1] - tgt[i][1]) for i in range(k.n)) / k.n
            k.chain = Chain(pts[0][0], pts[0][1], k.n + 1, seg)
            k.chain.points = pts
            k.trail = [pts[-1]]
            return
        # the head leads (follow-the-leader gives the body its fluid lag after a scatter), then every
        # point relaxes back toward the yin-yang shape; the scatter offset fades along the body
        hx, hy = tgt[0]
        k.chain.follow(hx + k.ox, (hy + k.oy) / ASPECT)
        pts = k.chain.points
        a = 1 - math.exp(-self.dt_last * 7.0)
        for i, (x, y) in enumerate(pts):
            f = i / k.n
            wgt = (1 - f) ** 1.5
            tx, ty = tgt[i][0] + k.ox * wgt, (tgt[i][1] + k.oy * wgt) / ASPECT
            pts[i] = (x + (tx - x) * a, y + (ty - y) * a)
        tail = pts[-1]
        last = k.trail[0]
        if math.hypot(tail[0] - last[0], (tail[1] - last[1]) * ASPECT) > max(0.6, k.L / k.n * 0.4):
            k.trail.insert(0, tail)
            del k.trail[90:]

    def on_click(self, x, y):
        if not (math.isfinite(x) and math.isfinite(y)):
            return
        X, Y = clamp(x, -5, self.w + 5), clamp(y, -5, self.h + 5) * ASPECT
        self.ripples.append([X, Y, 0.0, self.big * 1.6])
        self.ripples = self.ripples[-5:]
        for k in self.koi:
            hx, hy = k.chain.points[0]
            dx, dy = hx - X, hy * ASPECT - Y
            d = math.hypot(dx, dy) or 1.0
            push = self.big * 3.2 * clamp(1.4 - d / (self.big * 1.6), 0.35, 1.0)
            k.vx += dx / d * push
            k.vy += dy / d * push

    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.1)
        self.dt_last = dt
        self.theta += self.omega * dt
        ptr = self.pointer
        for k in self.koi:
            # a spring pulls each koi back onto the circle after a scatter; the pointer tempts it
            tx = ty = 0.0
            if ptr is not None:
                hx, hy = k.chain.points[0]
                dx, dy = ptr[0] - hx, ptr[1] * ASPECT - hy * ASPECT
                d = math.hypot(dx, dy)
                reach = self.big * 1.2
                if 1e-3 < d < reach:
                    pull = min(d, self.big * 0.35) * (1 - d / reach) * 1.6
                    tx, ty = dx / d * pull, dy / d * pull
            k.vx += ((tx - k.ox) * 3.0 - k.vx * 2.2) * dt
            k.vy += ((ty - k.oy) * 3.0 - k.vy * 2.2) * dt
            k.ox += k.vx * dt
            k.oy += k.vy * dt
            k.wig += dt * (4.0 + 0.04 * math.hypot(k.vx, k.vy))
            self.place(k)
        for r in self.ripples:
            r[2] += dt * (self.big * 0.9 + 6)
        self.ripples = [r for r in self.ripples if r[2] < r[3]]
        rate = abs(self.omega) * 1.1
        for s in self.stars:
            r = s[0]
            s[1] += self.dir * rate * s[2] * (self.big / max(r, self.big * 0.15)) ** 1.2 * dt
            s[0] -= dt * (0.6 + 0.08 * self.big / max(r, 1.0)) * s[2]
            if s[0] < self.big * 0.12:
                s[:] = self.new_star(self.rng.uniform(1.5, 2.0) * self.big)
        for sp in self.sparks:
            sp[2] += dt * sp[3]
            if sp[2] > TAU * 3:
                sp[0], sp[1], sp[2] = self.rng.uniform(0, self.w), self.rng.uniform(0, self.h), 0.0

    # ------------------------------------------------------------------ static water
    def build_background(self):
        w, h = self.w, self.h
        deep, mid, ring, _ = self.water
        cells = []
        seed = self.rng.randrange(1 << 16)
        for y in range(h):
            for x in range(w):
                dx, dy = x + 0.5 - self.cx, (y + 0.5) * ASPECT - self.cy
                r = math.hypot(dx, dy) / (self.big * 1.9)
                glow = clamp(1 - r) ** 1.6
                n = noise2(x * 0.18, y * 0.36, seed)
                v = glow * (0.07 + 0.06 * n)
                if n > 0.15 and v > 0.04:
                    cells.append((x, y, v, mix(deep, mid, 0.4 + 0.6 * glow)))
        self.bg = cells

    def static_layer(self, ramp):
        if self.static is None or self.static[0] != ramp:
            cv = Canvas(self.w, self.h, ramp)
            for x, y, v, c in self.bg:
                cv.shade(x, y, v, c)
            self.static = (ramp, cv.ch, cv.fg, cv.lv, cv.bc)
        return self.static

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        if cv.w == self.w and cv.h == self.h:
            _, ch, fg, lv, bc = self.static_layer(cv.ramp)
            cv.ch, cv.fg, cv.lv, cv.bc = ch[:], fg[:], lv[:], bc[:]
        if self.style == "rings":
            self.draw_rings(cv)
        elif self.style == "spiral":
            self.draw_spiral(cv)
        else:
            self.draw_stars(cv)
        self.draw_ripples(cv)
        self.draw_sparks(cv)
        for k in self.koi:
            self.draw_fins(cv, k)
        for k in self.koi:
            self.draw_body(cv, k)

    def ring_points(self, r, a0, span, step=1.0):
        n = max(2, int(r * span / step))
        cx, cy = self.cx, self.cy
        for i in range(n + 1):
            a = a0 + span * i / n
            yield i / n, cx + math.cos(a) * r, (cy + math.sin(a) * r) / ASPECT

    def draw_rings(self, cv):
        t = self.t
        ring = self.water[2]
        put = cv.put
        w, h = cv.w, cv.h
        lv = cv.lv
        for r, arcs, sp, glyph in self.rings:
            rot = self.dir * t * abs(self.omega) * sp * (self.big / r) ** 0.6
            fade = clamp(1.25 - r / (self.big * 1.9))
            for a0, span in arcs:
                for f, x, y in self.ring_points(r, a0 + rot, span):
                    xi, yi = int(x), int(y)
                    if 0 <= xi < w and 0 <= yi < h:
                        env = math.sin(f * math.pi)
                        v = (0.2 + 0.5 * env) * fade
                        i = yi * w + xi
                        if v > lv[i]:
                            if env > 0.3:
                                # a current line: the glyph follows the ring's direction
                                a = a0 + rot + span * f
                                ang = math.degrees(math.atan2(math.cos(a), -math.sin(a))) % 180
                                ch = "-" if ang < 22 or ang >= 158 else "\\" if ang < 68 else "|" if ang < 112 else "/"
                                if glyph == "." and env < 0.7:
                                    ch = "."
                            else:
                                ch = "."
                            put(xi, yi, ch, scale(ring, 0.25 + 0.75 * v), level=v)
        self.draw_center(cv)

    def draw_spiral(self, cv):
        t = self.t
        ring = self.water[2]
        big = self.big
        rot = self.dir * t * abs(self.omega) * 0.8
        w, h = cv.w, cv.h
        lv = cv.lv
        k = self.twist / 2.2
        for arm in range(self.arms * 2):
            # main arms plus fainter in-between arms, each a stream of glyphs following the curve
            main = arm % 2 == 0
            base = TAU * (arm / 2) / self.arms + rot
            r = big * 0.15
            while r < big * 2.0:
                ang = base + math.log(r / (big * 0.15)) * k
                x = self.cx + math.cos(ang) * r
                y = (self.cy + math.sin(ang) * r) / ASPECT
                xi, yi = int(x), int(y)
                fade = clamp(1.3 - r / (big * 1.8))
                wav = 0.5 + 0.5 * math.sin(r * 0.3 - t * abs(self.omega) * 6)
                v = (0.18 + 0.45 * wav) * fade * (1.0 if main else 0.5)
                if 0 <= xi < w and 0 <= yi < h and v > lv[yi * w + xi]:
                    # tangent of a log spiral: radial part 1, angular part k*r
                    tx = math.cos(ang) - k * math.sin(ang)
                    ty = math.sin(ang) + k * math.cos(ang)
                    deg = math.degrees(math.atan2(ty, tx)) % 180
                    ch = "-" if deg < 22 or deg >= 158 else "\\" if deg < 68 else "|" if deg < 112 else "/"
                    cv.put(xi, yi, ch if v > 0.14 else ".", scale(ring, 0.25 + 0.75 * v), level=v)
                r += max(0.6, r * 0.03)
        # a few faint full rings underneath
        for r, arcs, sp, glyph in self.rings[::3]:
            for f, x, y in self.ring_points(r, 0, TAU, 2.5):
                cv.shade(x, y, 0.07, ring)
        self.draw_center(cv)

    def draw_stars(self, cv):
        ring = self.water[2]
        spark = self.water[3]
        big = self.big
        for r, a, sp, br in self.stars:
            x = self.cx + math.cos(a) * r
            y = (self.cy + math.sin(a) * r) / ASPECT
            fade = clamp(1.4 - r / (big * 1.7))
            v = (0.2 + 0.5 * br) * fade
            # a short streak along its orbit
            tx, ty = -math.sin(a) * self.dir, math.cos(a) * self.dir
            ln = 2 + int(4 * sp * (big / max(r, big * 0.3)) ** 0.8)
            for k in range(ln):
                cv.shade(x - tx * k * 0.9, y - ty * k * 0.9 / ASPECT, v * (1 - k / (ln + 1)), mix(ring, spark, br))
            if br > 0.85:
                cv.put(x, y, "+", mix(ring, spark, 0.7), level=v)
        for r, arcs, sp, glyph in self.rings[::2]:
            for f, x, y in self.ring_points(r, self.t * 0.05 * self.dir, TAU, 3.0):
                cv.shade(x, y, 0.06, ring)
        self.draw_center(cv)

    def draw_center(self, cv):
        """A faint glow where the two koi meet: the eye of the vortex."""
        ring = self.water[3]
        r0 = self.orbit_radius() * 0.3
        cx, cy = self.cx, self.cy / ASPECT
        for y in range(int(cy - r0 / ASPECT) - 1, int(cy + r0 / ASPECT) + 2):
            for x in range(int(cx - r0) - 1, int(cx + r0) + 2):
                d = math.hypot(x + 0.5 - cx, (y + 0.5 - cy) * ASPECT) / max(r0, 0.5)
                if d < 1:
                    cv.shade(x, y, 0.16 * (1 - d) ** 2, ring)

    def draw_ripples(self, cv):
        spark = self.water[3]
        for X, Y, r, mr in self.ripples:
            f = r / mr
            for rr, k in ((r, 1.0), (r * 0.86, 0.5), (r * 0.72, 0.25)):
                if rr < 0.5:
                    continue
                a = (1 - f) ** 1.2 * k
                n = max(12, int(rr * 6))
                for i in range(n):
                    ang = TAU * i / n
                    cv.shade(X + math.cos(ang) * rr, (Y + math.sin(ang) * rr) / ASPECT, 0.75 * a, spark)

    def draw_sparks(self, cv):
        spark = self.water[3]
        for x, y, ph, rate in self.sparks:
            tw = math.sin(ph)
            if tw > 0.55:
                k = (tw - 0.55) / 0.45
                cv.put(x, y, "*" if k > 0.75 else "+" if k > 0.4 else ".", scale(spark, 0.4 + 0.6 * k), level=k)

    # ------------------------------------------------------------------ koi
    def spine(self, k):
        """The chain's points with a swimming wiggle, in stretched space, plus per-point normals."""
        pts = k.chain.points
        n = len(pts)
        out = []
        for i, (x, y) in enumerate(pts):
            a = pts[max(0, i - 1)]
            b = pts[min(n - 1, i + 1)]
            tx, ty = a[0] - b[0], (a[1] - b[1]) * ASPECT
            tn = math.hypot(tx, ty) or 1.0
            nx, ny = -ty / tn, tx / tn
            f = i / (n - 1)
            wob = math.sin(k.wig - f * 5.0) * k.W * 0.35 * f * f
            out.append((x + nx * wob, y * ASPECT + ny * wob, nx, ny, tx / tn, ty / tn))
        return out

    def radius(self, k, f):
        W = k.W
        if f < 0.16:
            return W * (0.72 + 0.28 * math.sqrt(f / 0.16))
        if f < 0.36:
            return W
        return W * (1 - 0.84 * ((f - 0.36) / 0.64) ** 1.1)

    def draw_fins(self, cv, k):
        sp = self.spine(k)
        n = len(sp)
        fc = k.finc
        fins = self.opt("fins")
        t = self.t
        shade = cv.shade
        # tail: two silk lobes that trail along the path the tail has swum
        trail = [(sp[-1][0], sp[-1][1])] + [(x, y * ASPECT) for x, y in k.trail]
        L = k.L * k.fin * fins
        # resample the trail to evenly spaced points
        path = [trail[0]]
        acc = 0.0
        step = max(0.8, k.W * 0.35)
        for i in range(1, len(trail)):
            ax, ay = trail[i - 1]
            bx, by = trail[i]
            d = math.hypot(bx - ax, by - ay)
            while d > 1e-6 and acc + d >= step and len(path) * step < L:
                f = (step - acc) / d
                ax, ay = ax + (bx - ax) * f, ay + (by - ay) * f
                path.append((ax, ay))
                d = math.hypot(bx - ax, by - ay)
                acc = 0.0
            acc += d
            if len(path) * step >= L:
                break
        m = len(path)
        if m >= 3:
            # each lobe is a translucent sheet: faint inside with fine silk striations, a bright hem
            frame = []
            for i in range(m):
                a_ = path[max(0, i - 1)]
                b_ = path[min(m - 1, i + 1)]
                tx, ty = b_[0] - a_[0], b_[1] - a_[1]
                tn = math.hypot(tx, ty) or 1.0
                frame.append((path[i][0], path[i][1], -ty / tn, tx / tn))
            hem = mix(fc, WHITE, 0.45)
            for side in (-1, 1):
                for i2 in range(2 * m - 1):
                    i = i2 // 2
                    j = min(m - 1, i + 1)
                    u = 0.5 if i2 % 2 else 0.0
                    px = frame[i][0] + (frame[j][0] - frame[i][0]) * u
                    py = frame[i][1] + (frame[j][1] - frame[i][1]) * u
                    nx = frame[i][2] + (frame[j][2] - frame[i][2]) * u
                    ny = frame[i][3] + (frame[j][3] - frame[i][3]) * u
                    f = (i + u) / (m - 1)
                    spread = k.W * (0.35 + 1.7 * f ** 0.75)
                    wave = math.sin(k.wig * 0.8 - f * 6 + side) * k.W * 0.6 * f
                    fade = 1 - 0.75 * f
                    o = spread * 0.12
                    stepo = 0.7
                    while o <= spread:
                        q = o / spread
                        stripe = 0.5 + 0.5 * math.cos(q * 9.0 + f * 3.0)
                        if spread - o < stepo:
                            v = 0.6 * fade
                            c = hem
                        else:
                            v = (0.1 + 0.16 * stripe * stripe) * fade
                            c = fc
                        off = side * o + wave * q
                        shade(px + nx * off, (py + ny * off) / ASPECT, v, c)
                        o += stepo
        # pectoral fins: long, fanned, flapping slowly
        i0 = max(1, int(n * 0.22))
        bx, by, nx, ny, tx, ty = sp[i0]
        r = self.radius(k, i0 / (n - 1))
        pl = k.L * k.pec * (0.7 + 0.3 * fins)
        for side in (-1, 1):
            flap = 0.35 * math.sin(t * 2.2 + side + k.seed)
            for ray in range(4):
                ang_out = 0.75 + 0.22 * ray + flap
                ca, sa = math.cos(ang_out), math.sin(ang_out)
                # direction: backward (-t) rotated outward toward this side
                dx = -tx * ca + side * nx * sa
                dy = -ty * ca + side * ny * sa
                sx, sy = bx + side * nx * r * 0.8, by + side * ny * r * 0.8
                ln = pl * (1 - 0.12 * ray)
                steps = max(2, int(ln * 1.3))
                for s in range(1, steps + 1):
                    f = s / steps
                    curl = math.sin(t * 2.2 + f * 2.5 + side) * f * f * k.W * 0.5
                    x = sx + dx * ln * f + side * nx * curl
                    y = sy + dy * ln * f + side * ny * curl
                    v = (0.6 - 0.35 * f) * (1.0 if ray in (0, 3) else 0.65)
                    shade(x, y / ASPECT, v, fc)

    def draw_body(self, cv, k):
        sp = self.spine(k)
        n = len(sp)
        w, h = cv.w, cv.h
        buf = {}
        for i in range(n - 1):
            ax, ay = sp[i][0], sp[i][1]
            bx, by = sp[i + 1][0], sp[i + 1][1]
            ra = self.radius(k, i / (n - 1))
            rb = self.radius(k, (i + 1) / (n - 1))
            m = max(ra, rb) + 0.6
            vx, vy = bx - ax, by - ay
            ll = vx * vx + vy * vy or 1e-6
            x0, x1 = max(0, int(min(ax, bx) - m)), min(w - 1, int(max(ax, bx) + m) + 1)
            y0, y1 = max(0, int((min(ay, by) - m) / ASPECT)), min(h - 1, int((max(ay, by) + m) / ASPECT) + 1)
            for y in range(y0, y1 + 1):
                py = (y + 0.5) * ASPECT
                row = y * w
                for x in range(x0, x1 + 1):
                    px = x + 0.5
                    wx, wy = px - ax, py - ay
                    s = (wx * vx + wy * vy) / ll
                    s = 0.0 if s < 0 else 1.0 if s > 1 else s
                    dx, dy = wx - vx * s, wy - vy * s
                    d = math.sqrt(dx * dx + dy * dy)
                    rr = ra + (rb - ra) * s
                    depth = 1 - d / (rr + 0.45)
                    if depth <= 0:
                        continue
                    j = row + x
                    old = buf.get(j)
                    if old is None or depth > old[0]:
                        side = 1.0 if (vx * dy - vy * dx) > 0 else -1.0
                        buf[j] = (depth, (i + s) / (n - 1), side * d / (rr + 0.45))
        # shade: dense along the back, light at the edges, lit from the upper left; koi patterns
        base = k.base
        patch = k.patch
        seed = k.seed
        lx, ly = -0.6, -0.8
        hx, hy, hnx, hny = sp[0][0], sp[0][1], sp[0][2], sp[0][3]
        put = cv.put
        shade = cv.shade
        for j, (depth, f, lat) in buf.items():
            y, x = divmod(j, w)
            # fake normal from how far across the body the cell is
            i = min(n - 1, int(f * (n - 1)))
            nx, ny = sp[i][2], sp[i][3]
            lit = 0.5 + 0.5 * clamp(lat * (nx * lx + ny * ly) * 1.4, -1, 1)
            v = (0.42 + 0.58 * depth ** 0.6) * (0.88 + 0.2 * lit)
            if f > 0.9:
                v *= 0.8
            c = base
            if patch is not None:
                pn = noise2(f * k.pscale * 2.2 + seed, lat * 1.3 + seed * 0.37, seed)
                if pn > 0.15 - k.amount and 0.08 < f < 0.85:
                    c = patch
            if k.kind == "white":
                c = mix(c, (170, 195, 245), clamp(0.45 - depth) * 1.2)     # pearly blue edge
            else:
                c = mix(c, (255, 220, 120), clamp(depth - 0.55) * 0.9)     # golden glow on the back
            c = mix(c, WHITE, clamp(lit - 0.75) * 1.2 * depth)
            shade(x, y, clamp(v), c, "over")
        # eyes
        r = self.radius(k, 0.06)
        tx, ty = sp[0][4], sp[0][5]
        for side in (-1, 1):
            ex = hx + tx * r * 0.35 + side * hnx * r * 0.62
            ey = hy + ty * r * 0.35 + side * hny * r * 0.62
            put(ex, ey / ASPECT, "o" if k.W > 4 else ".", (20, 24, 40), level=1.0)
