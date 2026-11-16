"""A planted fish tank with depth: the "make your own ASCII animals" idea at full scale.

Every fish is a few round parts (shapes.Body) moved by its own small set of rules:
  - neon tetras flock (stay close, match their neighbours, don't bump, follow a wandering leader)
  - angelfish glide slowly, tall and triangular
  - goldfish drift in lazy S-curves (shapes.Mover)
  - the pufferfish hovers, and puffs up into a spiky ball if you point at it
  - shrimp walk and peck on the gravel, a snail crawls across the front glass
Depth is faked the way the reel explains: fish in the back are smaller, slower, dimmer and bluer.
"""
import math

from ..engine import ASPECT, Scene, clamp, hsv, mix, noise1, scale
from ..shapes import Body, Mover

DEEP = (14, 34, 70)        # far things fade toward this color
RAYC = (120, 180, 225)


def fade(c, depth):
    """Far = bluer and darker. depth 0 (back glass) .. 1 (front glass)."""
    return mix(DEEP, c, 0.5 + 0.5 * clamp(depth))


def wrap(a):
    return (a + math.pi) % math.tau - math.pi


def hsh(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


class Frame:
    """The local frame of a side-view animal: u runs nose-ward, v runs up (both in x-cells).

    face is -1..1: the sign says which way the animal faces, the size squashes its length while
    it turns around (seen from the side, a fish turning toward you looks shorter)."""

    def __init__(self, x, y, face, pitch=0.0):
        sgn = 1.0 if face >= 0 else -1.0
        self.x, self.y = x, y
        self.L = max(0.22, abs(face))
        self.fx, self.fy = sgn * math.cos(pitch), math.sin(pitch) * sgn
        ux, uy = self.fy, -self.fx
        if uy > 0:
            ux, uy = -ux, -uy
        self.ux, self.uy = ux, uy
        self.angle = math.atan2(self.fy, self.fx)

    def p(self, du, dv):
        du *= self.L
        return (self.x + self.fx * du + self.ux * dv, self.y + (self.fy * du + self.uy * dv) / ASPECT)

    def local(self, x, y):
        dx, dy = x - self.x, (y - self.y) * ASPECT
        return (dx * self.fx + dy * self.fy) / self.L, dx * self.ux + dy * self.uy

    def cap(self, b, u0, v0, u1, v1, r0, r1, color):
        x0, y0 = self.p(u0, v0)
        x1, y1 = self.p(u1, v1)
        b.capsule(x0, y0, x1, y1, r0, r1, color=color)

    def ell(self, b, u, v, ru, rv, color):
        x, y = self.p(u, v)
        b.ellipse(x, y, max(0.3, ru * self.L), rv, self.angle, color=color)


class QuickBody(Body):
    """shapes.Body with a faster draw(), same parts and same look.

    Three tricks: the distance field is inlined; each row only looks at the parts that reach it
    (a part farther away than the blend radius can't change a smooth-min); and the surface normal
    comes from two forward differences instead of four central ones."""

    def _dist(self, px, py, parts):
        best, idx, bl = 1e9, -1, None
        k = self.blend
        hyp = math.hypot
        for i, kind, a, xa, xb in parts:
            if px < xa or px > xb:
                continue
            if kind == 0:
                d = hyp(px - a[0], py - a[1]) - a[2]
            elif kind == 1:
                dx, dy = px - a[0], py - a[1]
                c, s_ = a[5], a[6]
                d = (hyp((dx * c + dy * s_) / a[2], (dy * c - dx * s_) / a[3]) - 1.0) * a[7]
            else:
                ax, ay, vx, vy, ra, rd, il = a
                wx, wy = px - ax, py - ay
                t = (wx * vx + wy * vy) * il
                t = 0.0 if t < 0 else 1.0 if t > 1 else t
                d = hyp(wx - vx * t, wy - vy * t) - (ra + rd * t)
            if d <= best:
                best, idx = d, i
            if bl is None:
                bl = d
            elif k > 0:
                h = 0.5 + 0.5 * (d - bl) / k
                h = 0.0 if h < 0 else 1.0 if h > 1 else h
                bl = d + (bl - d) * h - k * h * (1 - h)
            elif d < bl:
                bl = d
        return (1e9, -1) if bl is None else (bl, idx)

    def draw(self, cv, light=(-0.55, -0.85), depth=1.0, edge=0.9, glow=0.0, pattern=None, mode="max",
             ambient=0.5):
        if not self.parts:
            return
        lim = edge * 0.5
        halo = lim + glow * 3
        reach = halo + self.blend + 0.6
        prep = []     # (index, kind, params, xmin, xmax, ymin, ymax) in stretched space
        for i, (kind, a, _) in enumerate(self.parts):
            if kind == "c":
                r = a[2] + reach
                prep.append((i, 0, a, a[0] - r, a[0] + r, a[1] - r, a[1] + r))
            elif kind == "e":
                c, s_ = math.cos(a[4]), math.sin(a[4])
                m = max(a[2], a[3]) + reach
                prep.append((i, 1, (a[0], a[1], a[2], a[3], a[4], c, s_, min(a[2], a[3])),
                             a[0] - m, a[0] + m, a[1] - m, a[1] + m))
            else:
                ax, ay, bx, by, ra, rb = a
                vx, vy = bx - ax, by - ay
                ll = vx * vx + vy * vy
                r = max(ra, rb) + reach
                prep.append((i, 2, (ax, ay, vx, vy, ra, rb - ra, 0.0 if ll == 0 else 1.0 / ll),
                             min(ax, bx) - r, max(ax, bx) + r, min(ay, by) - r, max(ay, by) + r))
        lx, ly = light
        ln = math.hypot(lx, ly) or 1.0
        lx, ly = lx / ln, ly / ln
        fade_ = 0.5 + 0.5 * clamp(depth)
        colors = [p[2] for p in self.parts]
        dist = self._dist
        decals = self.decals
        e = 0.4
        ymin = min(p[5] for p in prep)
        ymax = max(p[6] for p in prep)
        for y in range(max(0, int(ymin / ASPECT)), min(cv.h, int(ymax / ASPECT) + 1)):
            py = (y + 0.5) * ASPECT
            row = [(p[0], p[1], p[2], p[3], p[4]) for p in prep if p[5] <= py <= p[6]]
            if not row:
                continue
            xa = min(p[3] for p in row)
            xb = max(p[4] for p in row)
            for x in range(max(0, int(xa)), min(cv.w, int(xb) + 1)):
                px = x + 0.5
                d, i = dist(px, py, row)
                if d > halo:
                    continue
                if d > lim:
                    v = glow * 0.25 * (1 - (d - lim) / (glow * 3))
                    cv.shade(x, y, v * fade_, colors[i], mode)
                    continue
                inside = (lim - d) / (edge * 1.3)
                inside = 1.0 if inside > 1 else inside
                nx = dist(px + e, py, row)[0] - d
                ny = dist(px, py + e, row)[0] - d
                nn = math.hypot(nx, ny) or 1.0
                lit = -(nx * lx + ny * ly) / nn * 0.5 + 0.5
                lit = 0.0 if lit < 0 else 1.0 if lit > 1 else lit
                bulge = inside * 1.4
                bulge = 1.0 if bulge > 1 else bulge
                v = (0.22 + 0.78 * inside ** 0.55) * (ambient + (1 - ambient) * (lit * (1 - bulge) + bulge * 0.85))
                c = colors[i]
                if pattern is not None:
                    pc = pattern(px, y + 0.5, i, inside)
                    if pc is not None:
                        c = pc
                c = mix(scale(c, 0.55), c, lit)
                char = None
                for sx, sy, sr, sc, sch in decals:
                    if math.hypot(px - sx, py - sy) <= sr or (int(sx) == x and int(sy / ASPECT) == y):
                        c, char = sc, sch
                if char:
                    cv.put(x, y, char, scale(c, fade_), level=v * fade_)
                else:
                    cv.shade(x, y, v * fade_, c, mode)


# ----------------------------------------------------------------------------- swimmers
class Swimmer:
    """A fish moved by a shapes.Mover, kept inside the tank, that turns around like a real fish."""
    speed = 4.0
    turniness = 1.0

    def __init__(self, sc, rng, depth, size):
        self.depth = depth
        self.s = size
        x = rng.uniform(sc.w * 0.15, sc.w * 0.85)
        y = rng.uniform(sc.top + 2, max(sc.top + 2.5, sc.floor - 2))
        self.m = Mover(rng, x, y, speed=self.speed * sc.u, depth=depth)
        self.m.turn *= self.turniness
        self.face = 1.0 if math.cos(self.m.heading) >= 0 else -1.0
        self.flap = rng.uniform(0, math.tau)
        self.full = 0.0
        self.fright = 0.0

    def zone(self, sc):
        s = self.s
        return (s * 1.2, sc.w - s * 1.2, sc.top + 1 + s * 0.5 / ASPECT, sc.floor - s * 0.6 / ASPECT - 0.5)

    def move(self, sc, dt):
        m = self.m
        target = sc.nearest_food(m.x, m.y)
        threat = None
        if sc.pointer and m.near(sc.pointer[0], sc.pointer[1], self.s * 2.2 + 5):
            threat = sc.pointer
            self.fright = 1.0
        oy = m.y
        m.update(dt, sc.t, (sc.w, sc.h), target=target, threat=threat, margin=0)
        m.y = oy + (m.y - oy) * 0.55            # fish swim mostly level
        x0, x1, y0, y1 = self.zone(sc)
        soft = self.s * 2.5 + 3
        if m.x < x0 + soft or m.x > x1 - soft:   # ease away from the side glass
            want = 0.0 if m.x < x0 + soft else math.pi
            m.heading += wrap(want - m.heading) * min(1.0, dt * 2.5)
        if (m.y < y0 and math.sin(m.heading) < 0) or (m.y > y1 and math.sin(m.heading) > 0):
            m.heading = -m.heading
        m.x = clamp(m.x, x0, x1)
        m.y = clamp(m.y, y0, max(y0, y1))
        c = math.cos(m.heading)
        if abs(c) > 0.25:
            want = 1.0 if c > 0 else -1.0
            self.face += clamp(want - self.face, -dt * 3, dt * 3)
        if target is not None and m.near(target[0], target[1], self.s * 0.9 + 0.8):
            sc.eat(target, m.x, m.y)
            self.full = 2.0
        self.full = max(0.0, self.full - dt)
        self.fright = max(0.0, self.fright - dt)
        self.flap += dt * (5 + 8 * (threat is not None) + 3 * (target is not None))
        return target, threat

    def update(self, sc, dt):
        self.move(sc, dt)

    def frame(self, max_pitch=0.35):
        m = self.m
        pitch = clamp(math.atan2(math.sin(m.heading), abs(math.cos(m.heading))) * 0.6, -max_pitch, max_pitch)
        return Frame(m.x, m.y, self.face, pitch)


GOLD = [(255, 140, 40), (255, 110, 45), (255, 185, 70), (250, 236, 222), (255, 85, 55), (240, 200, 120)]


class Goldfish(Swimmer):
    speed = 4.5

    def __init__(self, sc, rng, depth, size):
        super().__init__(sc, rng, depth, size)
        self.color = rng.choice(GOLD)
        self.fin = rng.uniform(0.9, 1.7)      # comet tails are long, fantails short
        self.twin = rng.random() < 0.5
        self.calico = rng.random() < 0.3
        self.seed = rng.random() * 100

    def draw(self, sc, cv):
        f = self.frame()
        s = self.s
        col = fade(self.color, self.depth)
        fin = fade(mix(self.color, (255, 255, 255), 0.4), self.depth)
        wag = math.sin(self.flap) * 0.35
        b = QuickBody(blend=0.6)
        f.ell(b, -0.25 * s, 0, s * 1.1, s * 0.78, col)                      # chubby body
        f.cap(b, 0.2 * s, -0.05 * s, 0.75 * s, -0.05 * s, s * 0.6, s * 0.42, col)  # head
        f.cap(b, -1.0 * s, 0, -1.5 * s, 0, s * 0.42, s * 0.22, col)            # tail stalk
        spread = (-0.75, 0.75) if self.twin else (-0.55, 0.55)
        for sp in spread:                                                     # a flared, forked tail
            a = math.pi + wag + sp
            L = s * self.fin
            f.cap(b, -1.5 * s, 0, -1.5 * s + math.cos(a) * L, math.sin(a) * L, s * 0.12, s * 0.38, fin)
        f.cap(b, 0.1 * s, 0.7 * s, -0.9 * s, 1.05 * s - wag * 0.2 * s, s * 0.3, s * 0.12, fin)      # dorsal fin
        pa = -2.1 + math.sin(self.flap * 1.3) * 0.35                                  # paddling fin
        f.cap(b, 0.1 * s, -0.35 * s, 0.1 * s + math.cos(pa) * s * 0.75, -0.35 * s + math.sin(pa) * s * 0.75,
              s * 0.12, s * 0.2, fin)
        ex, ey = f.p(0.62 * s, 0.15 * s)
        b.spot(ex, ey, 0.3, fade((240, 240, 230), self.depth), "o" if s * f.L > 2.6 else ".")
        pattern = None
        if self.calico:
            seed = self.seed

            def pattern(x, y, i, inside):
                if i == 0 and math.sin(x * 0.9 + seed) * math.sin(y * 1.7 + seed * 2) > 0.35:
                    return fade((250, 245, 240), self.depth)
                return None
        b.draw(cv, depth=self.depth, edge=clamp(s * 0.4, 0.9, 2.4), glow=0.35 if self.full > 0 else 0.0, pattern=pattern)


ANGELS = [
    # body, stripe (None = plain), fin tint
    ((215, 220, 228), (25, 25, 35), (190, 200, 215)),     # silver, the classic
    ((235, 235, 240), (40, 40, 50), (220, 225, 235)),     # zebra
    ((245, 205, 95), None, (255, 225, 140)),              # gold
    ((240, 240, 245), None, (225, 230, 245)),             # platinum
    ((220, 215, 205), "marble", (200, 195, 190)),         # marble
]


class Angelfish(Swimmer):
    speed = 2.2
    turniness = 0.55

    def __init__(self, sc, rng, depth, size):
        super().__init__(sc, rng, depth, size)
        self.body, self.stripe, self.fin = rng.choice(ANGELS)
        self.tall = rng.uniform(0.85, 1.15)
        self.seed = rng.random() * 50

    def zone(self, sc):
        s = self.s
        return (s * 1.5, sc.w - s * 1.5, sc.top + 1 + s * 1.7 / ASPECT, sc.floor - s * 1.9 / ASPECT)

    def draw(self, sc, cv):
        f = self.frame(0.2)
        s, d = self.s, self.depth
        tall = self.tall
        body = fade(self.body, d)
        fin = fade(self.fin, d)
        b = QuickBody(blend=1.4)
        f.ell(b, 0, 0, s * 1.0, s * 0.95, body)
        f.cap(b, 0.3 * s, 0.0, 1.05 * s, 0.1 * s, s * 0.5, s * 0.16, body)             # snout
        flow = math.sin(self.flap * 0.5) * 0.1 * s
        f.cap(b, -0.15 * s, 0.45 * s, -0.85 * s + flow, 2.1 * s * tall, s * 0.75, s * 0.12, fin)    # dorsal sail
        f.cap(b, -0.15 * s, -0.45 * s, -0.85 * s - flow, -2.1 * s * tall, s * 0.75, s * 0.12, fin)  # anal sail
        wag = math.sin(self.flap) * 0.18
        for sp in (-0.5, 0.5):
            a = math.pi + sp + wag
            f.cap(b, -0.85 * s, 0, -0.85 * s + math.cos(a) * s * 0.8, math.sin(a) * s * 0.8, s * 0.14, s * 0.32, fin)
        ex, ey = f.p(0.55 * s, 0.2 * s)
        b.spot(ex, ey, 0.35, fade((230, 70, 50) if self.stripe is None else (240, 240, 230), d), "o" if s > 2.6 else ".")
        stripe = self.stripe
        pattern = None
        if stripe is not None:
            sc_ = fade(mix(stripe if stripe != "marble" else (35, 35, 45), self.body, 0.12), d)
            seed = self.seed
            bars = (0.55, -0.1, -0.8)

            def pattern(x, y, i, inside):
                u, v = f.local(x, y)
                if stripe == "marble":
                    if math.sin(u * 0.9 / max(1, s * 0.25) + seed) + math.sin(v * 0.7 / max(1, s * 0.25) - seed) > 0.9:
                        return sc_
                    return None
                for bu in bars:
                    if abs(u - bu * s) < 0.07 * s + 0.3:
                        return sc_
                return None
        b.draw(cv, depth=d, edge=clamp(s * 0.35, 0.9, 2.2), pattern=pattern, glow=0.3 if self.full > 0 else 0.0)
        # long trailing ventral filaments
        for k, off in enumerate((-0.05, 0.12)):
            x0, y0 = f.p(0.45 * s, -0.6 * s)
            sw = math.sin(self.flap * 0.4 + k) * 0.25 * s
            x1, y1 = f.p((-0.1 + off) * s + sw, -2.3 * s * tall)
            cv.line(x0, y0, x1, y1, 0.3 * (0.5 + 0.5 * d), fin)


PUFFERS = [
    # body, spots, belly
    ((200, 205, 90), (90, 80, 30), (240, 240, 200)),      # dwarf puffer
    ((120, 160, 90), (240, 230, 150), (235, 235, 215)),   # figure-eight
    ((210, 170, 110), (110, 70, 40), (245, 230, 200)),    # sand puffer
    ((150, 170, 190), (40, 50, 70), (235, 240, 245)),     # spotted grey
]


class Puffer(Swimmer):
    speed = 1.8
    turniness = 0.7

    def __init__(self, sc, rng, depth, size):
        super().__init__(sc, rng, depth, size)
        self.body, self.spots, self.belly = rng.choice(PUFFERS)
        self.puff = 0.0        # 0 = normal, 1 = full spiky ball
        self.hold = 0.0
        self.seed = rng.random() * 50

    def zone(self, sc):
        s = self.s * (1 + 0.55 * self.puff)
        return (s * 1.4, sc.w - s * 1.4, sc.top + 1 + s * 1.0 / ASPECT, sc.floor - s * 1.0 / ASPECT - 0.5)

    def update(self, sc, dt):
        m = self.m
        scared = sc.pointer is not None and m.near(sc.pointer[0], sc.pointer[1], self.s * 2.5 + 4)
        if scared:
            self.hold = 3.5
        self.hold = max(0.0, self.hold - dt)
        if self.hold > 0:
            self.puff = min(1.0, self.puff + dt * 3.5)       # gulp water fast...
        else:
            self.puff = max(0.0, self.puff - dt * 0.6)      # ...let it out slowly
        keep = m.speed
        m.speed = keep * (1 - 0.8 * self.puff)
        self.move(sc, dt)
        m.speed = keep

    def draw(self, sc, cv):
        f = self.frame(0.15)
        p = self.puff
        s, d = self.s, self.depth
        R = s * (1 + 0.55 * p)
        body, belly, spots = fade(self.body, d), fade(self.belly, d), fade(self.spots, d)
        b = QuickBody(blend=0.7)
        f.ell(b, 0, 0, R * (1.0 - 0.1 * p), R * (0.8 + 0.2 * p), body)
        wag = math.sin(self.flap * 1.6) * 0.35
        for sp in (-0.4, 0.4):
            a = math.pi + sp + wag
            f.cap(b, -0.9 * R, 0, -0.9 * R + math.cos(a) * s * 0.6, math.sin(a) * s * 0.6, s * 0.18, s * 0.12, body)
        pf = math.sin(self.flap * 4) * 0.6                     # tiny pectoral fin buzzing
        f.cap(b, 0.0, -0.05 * R, -0.45 * s * math.cos(pf), -0.05 * R - 0.45 * s * math.sin(pf), s * 0.13, s * 0.05,
              mix(body, belly, 0.5))
        ex, ey = f.p(0.5 * R, 0.32 * R)
        b.spot(ex, ey, 0.45 + 0.1 * s, fade((245, 245, 235), d), "O" if s > 2.5 else "o")
        mx, my = f.p(0.98 * R, -0.08 * R)
        b.spot(mx, my, 0.2, mix(belly, (220, 120, 110), 0.4), ".")
        seed = self.seed

        def pattern(x, y, i, inside):
            if i != 0:
                return None
            u, v = f.local(x, y)
            if v < -0.25 * R:
                return belly
            if hsh(int(x * 0.8 + seed), int(y * 1.6)) > 0.72:
                return spots
            return None
        b.draw(cv, depth=d, pattern=pattern, edge=clamp(R * 0.45, 0.9, 2.6))
        if p > 0.45:                                       # spines pop out of the ball
            n = int(10 + R * 2.2)
            for k in range(n):
                a = k / n * math.tau + 0.2
                ca, sa = math.cos(a), math.sin(a)
                r = R * (1.0 - 0.1 * p) * 1.02 + 0.6 + 0.5 * (p - 0.45)
                x = f.x + ca * r * (1.0 if abs(ca) > 0.3 else 1.0)
                y = f.y + sa * r * (0.8 + 0.2 * p) / ASPECT
                ch = "-" if abs(sa) < 0.38 else "|" if abs(ca) < 0.38 else ("\\" if ca * sa > 0 else "/")
                cv.put(x, y, ch, scale(spots if hsh(k, 3) > 0.5 else body, 0.6 + 0.4 * d))


TETRAS = [
    # stripe (front/top), rear-lower, belly
    ((60, 200, 255), (235, 40, 55), (210, 220, 230)),     # neon
    ((70, 220, 255), (240, 40, 60), (240, 50, 70)),       # cardinal: red all along
    ((255, 120, 40), (255, 90, 30), (255, 170, 110)),     # ember
    ((230, 235, 240), (40, 40, 50), (220, 225, 230)),     # rummy-nose (red head added below)
    ((250, 230, 90), (255, 200, 40), (250, 240, 180)),    # lemon
]


class School:
    """Flocking: each tetra steers toward the school's wandering leader, matches its neighbours'
    speed, and keeps a little space. Three tiny rules make a convincing school."""

    def __init__(self, sc, rng, n, depth):
        self.depth = depth
        self.kind = rng.choice(TETRAS)
        self.rummy = self.kind is TETRAS[3]
        self.cardinal = self.kind is TETRAS[1]
        x = rng.uniform(sc.w * 0.3, sc.w * 0.7)
        y = (sc.top + sc.floor) / 2
        self.leader = Mover(rng, x, y, speed=6 * sc.u, depth=depth)
        self.fish = []
        for _ in range(n):
            d = clamp(depth + rng.uniform(-0.1, 0.1))
            s = (1.4 + 1.3 * d) * sc.u * rng.uniform(0.9, 1.1)
            self.fish.append([x + rng.uniform(-6, 6), y + rng.uniform(-2, 2), rng.uniform(-3, 3), rng.uniform(-1, 1),
                              d, s, 1.0, rng.uniform(0, 6)])   # x, y, vx, vy(stretched), depth, size, face, flap

    def update(self, sc, dt):
        L = self.leader
        food = sc.nearest_food(L.x, L.y)
        oy = L.y
        L.update(dt, sc.t, (sc.w, sc.h), target=food, margin=6)
        L.y = clamp(oy + (L.y - oy) * 0.6, sc.top + 3, sc.floor - 3)
        L.x = clamp(L.x, 4, sc.w - 4)
        fish = self.fish
        n = len(fish)
        px = sc.pointer
        vmax = 9 * sc.u * (0.6 + 0.4 * self.depth)
        sep = 3.6 * sc.u * (0.7 + 0.5 * self.depth)
        sep2, near2 = sep * sep, sep * sep * 4
        R0 = sep * math.sqrt(n) * 0.55
        for i, f in enumerate(fish):
            lx, ly = L.x - f[0], (L.y - f[1]) * ASPECT
            ld = math.hypot(lx, ly) + 1e-6
            pull = max(0.0, ld - R0) * 0.9 + 0.15 * ld
            ax = lx / ld * pull
            ay = ly / ld * pull
            cx = cy = 0.0
            avx = avy = 0.0
            k = 0
            for j in range(n):
                if j == i:
                    continue
                g = fish[j]
                dx, dy = f[0] - g[0], (f[1] - g[1]) * ASPECT
                dd = dx * dx + dy * dy
                if dd < near2:
                    avx += g[2]
                    avy += g[3]
                    k += 1
                    if dd < sep2:
                        inv = 1.0 / (dd + 0.3)
                        cx += dx * inv * 30
                        cy += dy * inv * 30
            if k:
                ax += (avx / k - f[2]) * 1.2
                ay += (avy / k - f[3]) * 1.2
            ax += cx
            ay += cy
            if food is not None:
                ax += (food[0] - f[0]) * 0.8
                ay += (food[1] - f[1]) * ASPECT * 0.8
                if math.hypot(food[0] - f[0], (food[1] - f[1]) * ASPECT) < f[5] + 0.8:
                    sc.eat(food, f[0], f[1])
                    food = sc.nearest_food(L.x, L.y)
            if px is not None:
                dx, dy = f[0] - px[0], (f[1] - px[1]) * ASPECT
                dd = math.hypot(dx, dy)
                if dd < 12:
                    ax += dx / (dd + 0.5) * 90
                    ay += dy / (dd + 0.5) * 90
            f[2] += ax * dt
            f[3] += ay * dt
            sp = math.hypot(f[2], f[3])
            vm = vmax * (2.0 if px is not None else 1.0)
            if sp > vm:
                f[2] *= vm / sp
                f[3] *= vm / sp
            f[3] *= 1 - min(1.0, dt * 1.5)           # damp vertical: fish swim level
            f[0] = clamp(f[0] + f[2] * dt, 1, sc.w - 2)
            f[1] = clamp(f[1] + f[3] * dt / ASPECT, sc.top + 1.2, sc.floor - 1)
            if abs(f[2]) > 0.6:
                f[6] += clamp((1.0 if f[2] > 0 else -1.0) - f[6], -dt * 5, dt * 5)
            f[7] += dt * (10 + sp)

    def draw_one(self, cv, f):
        x, y, vx, vy, d, s, face, flap = f
        pitch = clamp(math.atan2(vy, abs(vx) + 1e-6) * 0.5, -0.3, 0.3)
        fr = Frame(x, y, face, pitch)
        stripe, rear, belly = (fade(c, d) for c in self.kind)
        b = QuickBody(blend=0.4)
        fr.cap(b, 0.3 * s, 0, -1.3 * s, 0, s * 0.42, s * 0.2, stripe)
        wag = math.sin(flap) * 0.4
        for sp in (-0.5, 0.5):
            a = math.pi + sp + wag
            fr.cap(b, -1.3 * s, 0, -1.3 * s + math.cos(a) * s * 0.6, math.sin(a) * s * 0.6, s * 0.16, s * 0.05,
                   rear if self.rummy else mix(stripe, rear, 0.5))
        cardinal, rummy = self.cardinal, self.rummy
        head = fade((240, 60, 60), d)

        def pattern(px, py, i, inside):
            u, v = fr.local(px, py)
            if rummy:
                return head if u > 0.0 else None
            if v < 0.08 * s and (u < -0.4 * s or cardinal):
                return rear
            if v < -0.2 * s:
                return belly
            return None
        ex, ey = fr.p(0.2 * s, 0.08 * s)
        if s * fr.L > 1.8:
            b.spot(ex, ey, 0.2, fade((240, 240, 240), d), ".")
        b.draw(cv, depth=d, pattern=pattern, edge=0.8, glow=0.15)

    def items(self):
        return [(f[4], self, f) for f in self.fish]


class Shrimp:
    """Walks along the gravel, stops to pick at it, turns around now and then."""

    COLORS = [(235, 50, 45), (60, 120, 235), (250, 200, 50), (200, 190, 170), (255, 110, 40)]

    def __init__(self, sc, rng, depth):
        self.depth = depth
        self.s = (2.0 + 1.3 * depth) * sc.u
        self.x = rng.uniform(sc.w * 0.1, sc.w * 0.9)
        self.dir = rng.choice((-1, 1))
        self.color = rng.choice(self.COLORS)
        self.walk = rng.uniform(0, 6)
        self.pause = rng.uniform(0, 2)
        self.speed = rng.uniform(0.8, 1.6) * sc.u * (0.5 + 0.5 * depth)

    def update(self, sc, dt):
        rng = sc.rng
        food = sc.nearest_food(self.x, sc.floor, ground_only=True)
        if food is not None and abs(food[0] - self.x) < 25:
            self.dir = 1 if food[0] > self.x else -1
            self.pause = 0
            if abs(food[0] - self.x) < self.s:
                sc.eat(food, self.x, sc.floor)
        if sc.pointer and abs(sc.pointer[0] - self.x) < 6 and abs(sc.pointer[1] - sc.floor) < 4:
            self.x += -math.copysign(dt * 12 * sc.u, sc.pointer[0] - self.x)   # flick backwards
            self.pause = 0.5
        if self.pause > 0:
            self.pause -= dt
            self.walk += dt * 2           # pecking
        else:
            self.x += self.dir * self.speed * dt
            self.walk += dt * 9
            if rng.random() < dt * 0.25:
                self.pause = rng.uniform(1, 3.5)
            if rng.random() < dt * 0.08:
                self.dir = -self.dir
        if self.x < 3 or self.x > sc.w - 3:
            self.dir = 1 if self.x < 3 else -1
            self.x = clamp(self.x, 3, sc.w - 3)

    def draw(self, sc, cv):
        s, d = self.s, self.depth
        gy = sc.ground(self.x) - 0.35 - 0.3 * s / ASPECT
        bob = 0.15 * s * max(0.0, math.sin(self.walk * 1.3)) if self.pause > 0 else 0.0
        fr = Frame(self.x, gy, self.dir)
        col = fade(self.color, d)
        dark = scale(col, 0.75)
        b = QuickBody(blend=0.5)
        fr.cap(b, 0.9 * s, 0.25 * s - bob, 0.0, 0.45 * s, s * 0.32, s * 0.4, col)       # head + carapace
        arc = [(-0.45, 0.48, 0.38), (-0.9, 0.38, 0.33), (-1.25, 0.15, 0.27), (-1.45, -0.1, 0.2)]
        for u, v, r in arc:
            fr.ell(b, u * s, v * s, r * s * 1.1, r * s, col)
        for sp in (-0.4, 0.4):                                                       # tail fan
            fr.cap(b, -1.45 * s, -0.1 * s, -1.85 * s, (-0.15 + sp * 0.4) * s, s * 0.12, s * 0.16, dark)
        b.draw(cv, depth=d, edge=0.8, ambient=0.6)
        # antennae: two long feelers sweeping forward and up
        hx, hy = fr.p(1.0 * s, 0.3 * s - bob)
        for k, (lu, lv) in enumerate(((2.6, 1.3), (2.1, 0.4))):
            sw = math.sin(sc.t * 2 + k + self.walk * 0.3) * 0.25 * s
            x1, y1 = fr.p((1.0 + lu) * s, (0.3 + lv) * s + sw)
            cv.line(hx, hy, x1, y1, 0.25 + 0.15 * d, mix(col, (255, 255, 255), 0.2))
        # little legs under the body
        for k in range(3):
            lx, ly = fr.p((0.4 - k * 0.5) * s, 0.0)
            ch = "," if (int(self.walk * 2) + k) % 2 else "'"
            cv.put(lx, ly + 0.5, ch, scale(col, 0.5 + 0.3 * d))


class Snail:
    """A mystery snail crawling across the front glass, very slowly, leaving a faint trail."""

    SHELLS = [((240, 200, 90), (150, 100, 30)), ((235, 225, 205), (170, 150, 120)),
              ((120, 80, 50), (220, 190, 140)), ((90, 120, 200), (40, 60, 120)), ((140, 130, 70), (40, 35, 20))]

    def __init__(self, sc, rng):
        self.depth = 1.1
        self.s = 2.6 * sc.u * rng.uniform(0.9, 1.15)
        self.x = rng.uniform(sc.w * 0.15, sc.w * 0.85)
        self.y = rng.uniform(sc.top + 3, max(sc.top + 3.5, sc.floor - 4))
        self.heading = rng.choice((0.0, math.pi)) + rng.uniform(-0.4, 0.4)
        self.shell, self.band = rng.choice(self.SHELLS)
        self.phase = rng.uniform(0, 50)
        self.trail = []
        self.hide = 0.0

    def update(self, sc, dt):
        if sc.pointer and math.hypot(sc.pointer[0] - self.x, (sc.pointer[1] - self.y) * ASPECT) < self.s * 3:
            self.hide = 2.5                 # pulls into its shell
        self.hide = max(0.0, self.hide - dt)
        if self.hide > 0:
            return
        self.heading += math.sin(sc.t * 0.15 + self.phase) * dt * 0.25
        right = math.cos(self.heading) >= 0
        base = 0.0 if right else math.pi
        self.heading = base + clamp(wrap(self.heading - base), -0.7, 0.7)
        sp = 0.35 * sc.u
        self.x += math.cos(self.heading) * sp * dt
        self.y += math.sin(self.heading) * sp * dt / ASPECT
        if self.x < self.s * 2 or self.x > sc.w - self.s * 2:
            self.heading = math.pi - self.heading
        if self.y < sc.top + 2 or self.y > sc.floor - 3:
            self.heading = -self.heading
        self.x = clamp(self.x, self.s * 2, sc.w - self.s * 2)
        self.y = clamp(self.y, sc.top + 2, max(sc.top + 2, sc.floor - 3))
        if not self.trail or math.hypot(self.trail[-1][0] - self.x, self.trail[-1][1] - self.y) > 0.7:
            self.trail.append((self.x, self.y))
            self.trail = self.trail[-40:]

    def draw(self, sc, cv):
        for k, (x, y) in enumerate(self.trail[:-3]):
            cv.shade(x, y + 0.3, 0.06 + 0.06 * k / 40, (150, 190, 200))
        s = self.s
        out = 1.0 - min(1.0, self.hide * 2)
        pitch = wrap(self.heading - (0.0 if math.cos(self.heading) >= 0 else math.pi))
        fr = Frame(self.x, self.y, 1.0 if math.cos(self.heading) >= 0 else -1.0,
                   pitch if math.cos(self.heading) >= 0 else -pitch)
        foot = (205, 190, 170)
        b = QuickBody(blend=0.5)
        if out > 0.05:
            stretch = 1 + 0.1 * math.sin(sc.t * 1.2 + self.phase)
            fr.cap(b, (1.2 * stretch * out - 0.2) * s, -0.15 * s, -1.2 * s, -0.25 * s, s * 0.38, s * 0.22, foot)
        sx, sy = fr.p(-0.15 * s, 0.6 * s)
        b.circle(sx, sy, s * 0.95, self.shell)
        shell, band = self.shell, self.band
        face = fr.fx

        def pattern(x, y, i, inside):
            if i != len(b.parts) - 1:
                return None
            dx, dy = (x - sx) * face, (y - sy) * ASPECT
            r = math.hypot(dx, dy) / (s * 0.95)
            a = math.atan2(dy, dx) / math.tau
            if (a + r * 2.2) % 1.0 < 0.22:
                return band
            return None
        b.draw(cv, depth=1.0, pattern=pattern, edge=0.9)
        if out > 0.5:      # eye stalks
            for k, (lu, lv) in enumerate(((1.75, 0.75), (1.45, 0.95))):
                x0, y0 = fr.p(1.0 * s, 0.05 * s)
                wob = math.sin(sc.t * 1.5 + k * 2 + self.phase) * 0.12 * s
                x1, y1 = fr.p(lu * s, lv * s + wob)
                cv.line(x0, y0, x1, y1, 0.35, foot)
                cv.put(x1, y1, ".", (40, 30, 30))


# ----------------------------------------------------------------------------- scenery
class Plant:
    def __init__(self, sc, rng, x, depth, kind):
        self.x, self.depth, self.kind = x, depth, kind
        self.phase = rng.uniform(0, 10)
        hmax = sc.floor - sc.top
        self.blades = []
        if kind == "grass":                 # vallisneria: long ribbon leaves
            for _ in range(rng.randint(4, 9)):
                self.blades.append((x + rng.uniform(-2.5, 2.5), hmax * rng.uniform(0.35, 0.95) * (0.6 + 0.4 * depth),
                                    rng.uniform(-0.25, 0.25), rng.uniform(0, 6)))
            g = rng.uniform(0.25, 0.4)
            self.color = hsv(g, 0.7, 0.75)
        elif kind == "sword":               # amazon sword: a rosette of broad leaves
            n = rng.randint(5, 8)
            for k in range(n):
                ang = (k / (n - 1) - 0.5) * rng.uniform(1.6, 2.2) + rng.uniform(-0.1, 0.1)
                self.blades.append((ang, hmax * rng.uniform(0.25, 0.5) * (0.6 + 0.4 * depth),
                                    rng.uniform(1.0, 1.8) * sc.u * (0.6 + 0.4 * depth), rng.uniform(0, 6)))
            self.color = hsv(rng.uniform(0.24, 0.32), 0.65, 0.7)
        else:                               # stem plant: a tall stem with leaf pairs
            for _ in range(rng.randint(2, 4)):
                self.blades.append((x + rng.uniform(-2, 2), hmax * rng.uniform(0.4, 0.85) * (0.6 + 0.4 * depth),
                                    rng.uniform(-0.15, 0.15), rng.uniform(0, 6)))
            self.color = rng.choice([(90, 190, 80), (200, 90, 80), (150, 200, 70), (220, 130, 90)])

    def draw(self, sc, cv):
        d = self.depth
        t = sc.t
        base_y = sc.ground(self.x) + 0.3
        if self.kind == "grass":
            for bx, H, lean, ph in self.blades:
                n = int(H) + 1
                px = bx
                for k in range(n):
                    f = k / max(1, n - 1)
                    x = bx + lean * f * H * 0.6 + math.sin(t * 0.7 + ph + f * 2.2) * f * f * 3.5
                    y = base_y - f * H
                    dx = x - px
                    px = x
                    ch = "|" if abs(dx) < 0.25 else ("/" if dx > 0 else "\\")
                    c = fade(mix(scale(self.color, 0.55), mix(self.color, (200, 240, 140), 0.3 + 0.2 * (ph % 1)), f), d)
                    cv.put(x, y, ch, scale(c, 0.55 + 0.45 * d))
        elif self.kind == "sword":
            # broad leaves, hatched along their direction so they read as leaves, not blobs
            for ang, H, W, ph in self.blades:
                a = ang + math.sin(t * 0.5 + ph) * 0.07
                steps = int(H * 1.3) + 2
                for k in range(1, steps):
                    f = k / steps
                    bend = a * (1 + f * 0.7)
                    cx = self.x + math.sin(bend) * f * H * 1.5
                    cy = base_y - math.cos(bend) * f * H
                    hw = W * math.sin(math.pi * min(1.0, f * 1.02)) ** 0.8
                    tx = math.sin(bend) * 1.5          # cells across per row up
                    ch = "|" if abs(tx) < 0.45 else ("/" if tx > 0 else "\\")
                    m = int(hw) + 1
                    for j in range(-m, m + 1):
                        if abs(j) > hw + 0.3:
                            continue
                        e = abs(j) / (hw + 0.5)
                        c = mix(self.color, (200, 240, 140), 0.45) if j == 0 else scale(self.color, 0.95 - 0.35 * e)
                        cv.put(cx + j, cy, ch, scale(fade(c, d), 0.55 + 0.45 * d))
        else:
            for bx, H, lean, ph in self.blades:
                n = int(H) + 1
                for k in range(n):
                    f = k / max(1, n - 1)
                    x = bx + lean * f * H * 0.5 + math.sin(t * 0.6 + ph + f * 1.5) * f * 1.3
                    y = base_y - f * H
                    c = fade(mix(self.color, (230, 240, 150), 0.3 * f), d)
                    cv.put(x, y, "|", scale(mix(c, (60, 90, 40), 0.5), 0.5 + 0.4 * d))
                    if k > 0:
                        flick = math.sin(t * 1.3 + ph + k) > 0.6
                        lc = scale(c, (0.6 + 0.4 * d) * (0.75 + 0.25 * (k % 2)))
                        cv.put(x - 1, y, "\\" if not flick else "-", lc)
                        cv.put(x + 1, y, "/" if not flick or k % 2 else "-", lc)
                        if k % 3 == 0 and f < 0.9:
                            cv.put(x - 2, y - 0.5, "\\", scale(lc, 0.7))
                            cv.put(x + 2, y - 0.5, "/", scale(lc, 0.7))


class Rock:
    def __init__(self, sc, rng, x, depth):
        self.depth = depth
        self.x = x
        self.rx = rng.uniform(3, 7) * sc.u * (0.6 + 0.4 * depth)
        self.ry = self.rx * rng.uniform(0.45, 0.7)
        self.color = rng.choice([(130, 125, 120), (110, 100, 90), (150, 140, 120), (90, 95, 105)])
        self.seed = rng.random() * 40
        self.parts = [(rng.uniform(-0.5, 0.5), rng.uniform(0.5, 0.8)) for _ in range(rng.randint(1, 2))]

    def draw(self, sc, cv):
        gy = sc.ground(self.x) + 0.3
        b = QuickBody(blend=1.2)
        b.ellipse(self.x, gy, self.rx, self.ry, color=fade(self.color, self.depth))
        for dx, k in self.parts:
            b.ellipse(self.x + dx * self.rx, gy + 0.2, self.rx * k * 0.7, self.ry * k, color=fade(self.color, self.depth))
        seed = self.seed
        moss = fade((80, 130, 60), self.depth)

        def pattern(x, y, i, inside):
            return moss if hsh(int(x + seed), int(y)) > 0.8 and inside < 0.5 else None
        b.draw(cv, depth=self.depth, pattern=pattern, ambient=0.4)


GRAVEL = [
    [(200, 175, 125), (170, 145, 100), (225, 205, 160), (140, 120, 90)],      # sand
    [(150, 145, 140), (110, 105, 100), (190, 180, 165), (120, 100, 80)],      # river pebbles
    [(70, 70, 75), (110, 110, 115), (50, 50, 55), (140, 140, 150)],           # black sand
    [(240, 120, 170), (100, 170, 250), (250, 220, 90), (130, 230, 140)],      # neon gravel
]


# ----------------------------------------------------------------------------- the scene
class Aquarium(Scene):
    name = "aquarium"
    title = "Aquarium"
    blurb = "a planted fish tank in depth: schooling tetras, angelfish, a pufferfish, shrimp and a snail"
    tags = ("water", "creatures", "calm", "cozy")
    interactions = "click to drop food flakes, point at fish to startle them (the pufferfish puffs up)"
    options = {
        "species": ("random", "which animals: random, all, or a list like tetra+angel+puffer+gold+shrimp+snail"),
        "fish": (1.0, "amount of fish (multiplier)"),
        "rays": (True, "light rays through the water"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.u = max(0.35, min(h, w / 2.6) / 32.0)       # size unit: 1 at 32 rows
        self.top = 1
        self.floor = h - max(2, round(h * 0.13))
        self.gseed = rng.uniform(0, 100)
        amount = self.opt("fish") * self.density
        area = w * h / (120 * 40)
        # which species live here: rolled per seed, unless asked
        spec = str(self.opt("species")).lower()
        allsp = ["tetra", "angel", "puffer", "gold", "shrimp", "snail"]
        if spec == "all":
            have = set(allsp)
        elif spec == "random":
            have = {s for s, p in zip(allsp, (0.85, 0.65, 0.6, 0.7, 0.8, 0.75)) if rng.random() < p}
            if not have & {"angel", "gold", "puffer"}:      # always at least one big fish
                have.add(rng.choice(("angel", "gold", "puffer")))
            while len(have) < 4:
                have.add(rng.choice(allsp))
        else:
            have = {s for s in allsp if s in spec}
        self.items = []
        self.schools = []
        self.creatures = []
        k = self.u
        if "tetra" in have:
            for _ in range(1 if area < 1.6 or rng.random() < 0.6 else 2):
                n = max(4, int(rng.randint(10, 20) * min(2.0, area) ** 0.7 * amount))
                self.schools.append(School(self, rng, n, rng.uniform(0.45, 1.0)))
        if "angel" in have:
            for _ in range(max(1, int(rng.randint(1, 3) * min(1.5, area) * amount))):
                d = rng.choice((0.15, 0.4, 0.75, 1.0)) + rng.uniform(-0.05, 0.05)
                self.creatures.append(Angelfish(self, rng, d, (2.2 + 2.6 * d) * k))
        if "gold" in have:
            for _ in range(max(1, int(rng.randint(1, 3) * min(1.5, area) * amount))):
                d = rng.uniform(0.1, 1.0)
                self.creatures.append(Goldfish(self, rng, d, (2.2 + 3.2 * d) * k))
        if "puffer" in have:
            d = rng.uniform(0.55, 1.0)
            self.creatures.append(Puffer(self, rng, d, (2.6 + 1.4 * d) * k))
        # a few tiny far-away fish in the haze so the back of the tank isn't empty
        for _ in range(int(rng.randint(2, 5) * min(2.0, area) * amount)):
            d = rng.uniform(0.0, 0.2)
            g = Goldfish(self, rng, d, (1.3 + 0.8 * d) * k)
            g.color = rng.choice([(220, 120, 60), (200, 200, 210), (120, 190, 230)])
            g.twin = False
            self.creatures.append(g)
        self.shrimp = []
        if "shrimp" in have:
            for _ in range(max(1, int(rng.randint(2, 5) * min(2.0, area) ** 0.7))):
                self.shrimp.append(Shrimp(self, rng, rng.uniform(0.4, 1.0)))
        self.snails = [Snail(self, rng) for _ in range(rng.choice((1, 1, 2)) if "snail" in have else 0)]
        # scenery
        self.plants = []
        nplants = max(2, int(rng.randint(4, 8) * min(2.0, area) ** 0.6))
        for i in range(nplants):
            x = (i + rng.uniform(0.1, 0.9)) / nplants * w
            d = rng.choice((0.05, 0.25, 0.5, 0.9, 1.0)) if abs(x - w / 2) > w * 0.15 else rng.uniform(0.0, 0.4)
            self.plants.append(Plant(self, rng, x, d, rng.choice(("grass", "grass", "sword", "stem"))))
        self.rocks = [Rock(self, rng, rng.uniform(w * 0.1, w * 0.9), rng.uniform(0.2, 0.8))
                      for _ in range(rng.randint(0, 2))]
        pal = GRAVEL[rng.choices(range(4), weights=(4, 4, 2, 1))[0]]
        self.gravel = []
        for x in range(w):
            g0 = self.ground(x)
            for y in range(int(g0), h):
                r = hsh(x, y, 7)
                top = y == int(g0)
                ch = "." if r < 0.3 else "," if r < 0.45 else "o" if r < 0.6 else "°" if r < 0.72 else ":" if r < 0.88 else "_" if r < 0.97 else "O"
                if top:
                    ch = "_" if r < 0.5 else "." if r < 0.8 else "o"
                c = pal[int(hsh(x, y, 9) * len(pal)) % len(pal)]
                k2 = (0.75 if top else 0.55) - 0.3 * (y - g0) / max(1, h - g0)
                self.gravel.append((x, y, ch, scale(c, k2)))
        self.stone = rng.uniform(w * 0.15, w * 0.85)
        self.bubbles = []
        self.food = []
        nr = rng.randint(3, 6)
        self.rays = [(rng.uniform(-0.1, 1.1) * w, rng.uniform(1.5, 4.5) * (w / 100 + 0.5), rng.uniform(0, 9),
                      rng.uniform(0.25, 0.6)) for _ in range(nr)]
        self.slant = rng.uniform(0.25, 0.6) * rng.choice((-1, 1))
        self.motes = [(rng.uniform(0, w), rng.uniform(self.top, self.floor), rng.uniform(0, 9))
                      for _ in range(self.count(14))]

    def ground(self, x):
        return self.floor + 0.7 * noise1(x * 0.09 + self.gseed) + 0.3

    def nearest_food(self, x, y, ground_only=False):
        best, bd = None, 1e9
        for f in self.food:
            if ground_only != (f[3] > 0):
                continue
            d = (f[0] - x) ** 2 + ((f[1] - y) * ASPECT) ** 2
            if d < bd:
                best, bd = f, d
        return best

    def eat(self, flake, x, y):
        if flake in self.food:
            self.food.remove(flake)
            self.bubbles.append([x, y - 0.3, 0.3])

    def on_click(self, x, y):
        y = clamp(y, self.top + 0.5, self.floor - 1)
        for _ in range(self.rng.randint(5, 9)):
            self.food.append([x + self.rng.uniform(-2.5, 2.5), y + self.rng.uniform(-0.6, 0.6),
                              self.rng.uniform(0, 6), 0.0,
                              self.rng.choice([(240, 160, 70), (230, 90, 60), (200, 200, 90), (150, 210, 90)])])

    # ------------------------------------------------------------------ move
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.1)        # big steps make the flock explode; the tests use 0.25
        rng = self.rng
        for f in self.food:           # flakes flutter down, then rest on the gravel for a while
            if f[3] == 0:
                f[1] += dt * 1.1 * self.u
                f[0] += math.sin(self.t * 2.2 + f[2]) * dt * 0.8
                if f[1] >= self.ground(f[0]) - 0.6:
                    f[1] = self.ground(f[0]) - 0.6
                    f[3] = 1e-3
            else:
                f[3] += dt
        self.food = [f for f in self.food if f[3] < 25]
        for s in self.schools:
            s.update(self, dt)
        for c in self.creatures:
            c.update(self, dt)
        for s in self.shrimp:
            s.update(self, dt)
        for s in self.snails:
            s.update(self, dt)
        if rng.random() < dt * 9:             # the air stone
            self.bubbles.append([self.stone + rng.uniform(-0.8, 0.8), self.floor - 0.5, rng.uniform(0.0, 0.6)])
        for b in self.bubbles:
            b[1] -= dt * (3 + b[2] * 4) * self.u ** 0.5
            b[0] += math.sin(self.t * 3 + b[2] * 20 + b[1] * 0.5) * dt * 2.0
            b[2] = min(1.0, b[2] + dt * 0.03)
        self.bubbles = [b for b in self.bubbles if b[1] > self.top + 0.5]

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, t = self.w, self.h, self.t
        top, floor = self.top, self.floor
        if self.opt("rays"):
            # soft diagonal shafts of light from the lamp, slowly swaying
            for x0, width, ph, power in self.rays:
                sway = math.sin(t * 0.2 + ph) * 3
                for y in range(top, int(floor)):
                    f = (y - top) / max(1, floor - top)
                    cx = x0 + sway + self.slant * (y - top) * ASPECT
                    wd = width * (1 + f * 0.6)
                    for x in range(max(0, int(cx - wd)), min(w, int(cx + wd) + 1)):
                        k = 1 - abs(x + 0.5 - cx) / wd
                        if k <= 0:
                            continue
                        v = power * k * (1 - f * 0.8) * (0.8 + 0.2 * math.sin(y * 0.4 - t * 0.8 + ph))
                        if v > 0.17:
                            cv.put(x, y, "." if v < 0.3 else ":", scale(RAYC, 0.12 + 0.35 * v))
        for x, y, ph in self.motes:
            yy = y + math.sin(t * 0.3 + ph) * 1.5
            xx = x + math.sin(t * 0.17 + ph * 2) * 3
            cv.shade(xx, yy, 0.12, (150, 170, 160))
        # the surface: a bright wavy line with sparkle
        for x in range(w):
            wv = math.sin(x * 0.35 + t * 1.6) + math.sin(x * 0.13 - t * 0.9)
            ch = "~" if wv > 0.4 else "-"
            cv.put(x, top - 1 + (1 if h > 4 else 0), ch, scale((150, 200, 235), 0.45 + 0.2 * wv))
        for x, y, ch, c in self.gravel:
            cv.put(x, y, ch, c)
        # everything else, far to near
        layers = [(r.depth, r) for r in self.rocks] + [(p.depth, p) for p in self.plants]
        layers += [(c.depth, c) for c in self.creatures] + [(s.depth, s) for s in self.shrimp]
        layers += [(0.6, "bubbles"), (0.8, "food")]
        flock = []
        for s in self.schools:
            flock += s.items()
        layers += [(d, (school, f)) for d, school, f in flock]
        layers += [(s.depth, s) for s in self.snails]
        layers.sort(key=lambda e: e[0])
        for d, obj in layers:
            if obj == "bubbles":
                self.draw_bubbles(cv)
            elif obj == "food":
                for x, y, ph, rest, col in self.food:
                    cv.put(x, y, "*" if (int(ph * 10) % 3) else ",", col if rest < 18 else scale(col, 0.5))
            elif isinstance(obj, tuple):
                obj[0].draw_one(cv, obj[1])
            else:
                obj.draw(self, cv)

    def draw_bubbles(self, cv):
        sx = self.stone
        gy = self.ground(sx)
        for k in range(-1, 2):
            cv.put(sx + k, gy - 0.6, "=", (120, 120, 130))
        for x, y, r in self.bubbles:
            ch = "o" if r > 0.7 else "°" if r > 0.35 else "."
            cv.put(x, y, ch, mix((90, 140, 190), (200, 230, 250), r))
