"""Honeybees working a sunny flower patch.

Every bee runs the same few rules, and the colony behaviour comes out of them:
  1. leave the hive and fly (lazy S-curves, shapes.Mover) to a flower,
  2. sip there for a moment (the flower nods, pollen sparkles), maybe hop to a flower nearby,
  3. fly home with full pollen baskets,
  4. sometimes dance the waggle dance on the hive: the straight "waggle run" points at the flower
     she found, measured from straight up as the angle between the sun and that flower.
Bees are tiny shapes.Body creatures (striped abdomen, fuzzy thorax, dark head) with flickering
see-through wings. Nearer bees are bigger and faster; farther ones are smaller and dimmer.
"""
import math
import random

from ..engine import ASPECT, Canvas, Scene, clamp, fbm, hsv, mix, noise1, scale
from ..shapes import Body, Mover

YELLOW = (255, 214, 60)
STRIPE = (84, 52, 22)
FUZZ = (214, 150, 60)
WING = (205, 230, 255)
GRASS_FRONT = ",'\"v/\\|,'"

# kind: (petals lo, hi, petal color choices, center color, size multiplier, height multiplier)
KINDS = {
    "daisy": ((10, 14), [(250, 250, 245), (255, 240, 250)], (250, 200, 40), 1.0, 1.0),
    "sunflower": ((12, 16), [(255, 200, 30), (255, 170, 20)], (170, 95, 35), 1.35, 1.5),
    "poppy": ((4, 5), [(240, 50, 40), (255, 110, 30), (250, 80, 90)], (110, 50, 80), 1.05, 0.9),
    "cosmos": ((8, 8), [(250, 110, 190), (230, 80, 160), (255, 190, 220), (190, 120, 240)], (255, 210, 60), 0.95, 1.1),
    "lavender": ((0, 0), [(170, 120, 240), (140, 100, 230), (200, 150, 255)], (120, 90, 200), 0.9, 0.95),
}


def cellhash(x, y, s=0):
    """A cheap per-cell random number in [-1, 1] (for sparse speckle that shouldn't clump)."""
    n = (x * 374761393 + y * 668265263 + s * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 32767.5 - 1.0


def bake(draw_fn, w, h, ramp):
    """Render draw_fn(cv, ax, ay) into a small canvas once; return its cells relative to the anchor."""
    cv = Canvas(w, h, ramp)
    ax, ay = w // 2, h // 2
    draw_fn(cv, ax + 0.5, ay + 0.5)
    out = []
    for i, c in enumerate(cv.ch):
        if c != " " and cv.fg[i] is not None:
            y, x = divmod(i, w)
            out.append((x - ax, y - ay, c, cv.fg[i], cv.lv[i]))
    return out


def blit(cv, cells, x, y, over=False):
    """Stamp baked cells at (x, y); keeps whatever is brighter unless over=True."""
    ix, iy = int(math.floor(x)), int(math.floor(y))
    W, H = cv.w, cv.h
    ch, fg, lv, bc = cv.ch, cv.fg, cv.lv, cv.bc
    for dx, dy, c, f, l in cells:
        px, py = ix + dx, iy + dy
        if 0 <= px < W and 0 <= py < H:
            i = py * W + px
            if over or l >= lv[i]:
                ch[i] = c
                fg[i] = f
                lv[i] = l
                bc[i] = f


def wing_oval(cv, cx, cy, rx, ry, ang, col):
    """A see-through oval: faint dots inside, a light rim. Drawn under the body (mode max)."""
    c, sn = math.cos(ang), math.sin(ang)
    m = max(rx, ry) + 1
    for y in range(int(cy - m / ASPECT) - 1, int(cy + m / ASPECT) + 2):
        for x in range(int(cx - m) - 1, int(cx + m) + 2):
            ddx, ddy = x + 0.5 - cx, (y + 0.5 - cy) * ASPECT
            u = (ddx * c + ddy * sn) / rx
            v = (-ddx * sn + ddy * c) / ry
            k = math.hypot(u, v)
            if k <= 1.15:
                cv.shade(x, y, 0.3 if k > 0.7 else 0.16, col, dim=False)


def slope_ch(dx, dy):
    ax, ay = abs(dx), abs(dy * ASPECT)
    if ax > 2.2 * ay:
        return "-"
    if ay > 2.2 * ax:
        return "|"
    return "\\" if dx * dy > 0 else "/"


class Flower:
    def __init__(self, rng, kind, x, base_y, head_y, r, depth, bloom=1.0):
        petals, colors, center, _, _ = KINDS[kind]
        self.kind = kind
        self.x0, self.base_y = x, base_y
        self.hx, self.hy = x + rng.uniform(-2, 2), head_y
        self.r = r
        self.depth = depth
        self.n = rng.randint(*petals)
        self.color = rng.choice(colors)
        self.center = center
        self.rot = rng.uniform(0, math.tau)
        self.phase = rng.uniform(0, math.tau)
        self.sway_k = rng.uniform(0.6, 1.3)
        self.bloom = bloom
        self.nod = 0.0
        self.leaves = [(rng.uniform(0.25, 0.65), rng.choice((-1, 1))) for _ in range(rng.randint(1, 2))]
        self.cache = {}

    def sway(self, t):
        return (math.sin(t * 0.8 * self.sway_k + self.phase) * 0.9
                + noise1(t * 0.35 + self.phase * 3) * 0.8) * (0.5 + 0.5 * self.depth)

    def head(self, t):
        return self.hx + self.sway(t), self.hy + self.nod * 0.8

    def open(self):
        return self.bloom > 0.65


class Bee:
    def __init__(self, rng, x, y, depth, u):
        self.depth = depth
        self.size = (5.5 + 4.5 * depth) * u
        self.mover = Mover(rng, x, y, speed=13.0 * u ** 0.5, depth=depth)
        self.state = "in"
        self.timer = rng.uniform(0.0, 6.0)
        self.flower = None
        self.visits = 0
        self.pollen = 0.0
        self.wing = rng.uniform(0, 10)
        self.buzz = rng.uniform(0, math.tau)
        self.facing = 1
        self.curious_cd = rng.uniform(0, 3)
        self.orbit = 0.0
        self.resume = None
        self.dance = None   # (angle of the waggle run, phase)
        self.hover = (0.0, 0.0)


class Bees(Scene):
    name = "bees"
    title = "Bees"
    blurb = "honeybees visit swaying flowers, fly home and waggle-dance the way to the best ones"
    tags = ("nature", "creatures", "cozy", "day")
    interactions = "click to plant a flower (it blooms and the bees find it), point to make bees circle it"
    options = {
        "bees": (0, "how many bees (0 = based on size)"),
        "flowers": (0, "how many flowers (0 = based on width)"),
        "hive": ("random", "hive style: box, skep, wild or random"),
    }

    # ------------------------------------------------------------------ setup
    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.u = u = clamp(min(h / 40, w / 110), 0.45, 1.5)
        self.gy = h * rng.uniform(0.62, 0.7)
        hive = self.opt("hive")
        if hive not in ("box", "skep", "wild"):
            hive = rng.choice(("box", "skep", "wild"))
        self.hive = hive
        self.side = rng.choice((-1, 1))   # -1: hive on the left
        self.sun = (w * (0.85 if self.side < 0 else 0.15) + rng.uniform(-4, 4), h * rng.uniform(0.08, 0.16))
        self.sun_r = max(2.0, 3.2 * u)
        self.hive_color = rng.choice([(235, 232, 220), (170, 205, 225), (180, 225, 190), (245, 215, 140),
                                      (230, 180, 160)])
        self.build_hive()
        # the meadow: a few flower kinds for this run, in drifts
        kinds = list(KINDS)
        rng.shuffle(kinds)
        self.kinds = kinds[:rng.randint(2, 4)]
        weights = [rng.uniform(0.5, 1.5) for _ in self.kinds]
        n = self.opt("flowers") or max(4, int(round(w / rng.uniform(7, 11) * self.density ** 0.5)))
        self.flowers = []
        for k in range(n):
            x = (k + rng.uniform(0.1, 0.9)) / n * w
            if abs(x - self.hx) < self.hw * 0.7 + 2 and self.hive != "wild":
                x = self.hx + self.side * -(self.hw * 0.7 + 2 + rng.uniform(0, 4))
            depth = 0.2 + 0.8 * rng.random() ** 0.7
            kind = rng.choices(self.kinds, weights)[0]
            self.flowers.append(self.new_flower(kind, x, depth))
        self.flowers.sort(key=lambda f: f.depth)
        nb = self.opt("bees") or max(3, int(round(w * h / 480 * self.density)))
        nb = min(nb, 60)
        self.bees = []
        for k in range(nb):
            depth = (k + rng.random()) / nb
            b = Bee(rng, self.ex, self.ey, depth, u)
            if rng.random() < 0.7:  # most bees are already out working
                f = rng.choice(self.flowers)
                hx, hy = f.head(0)
                b.mover.x, b.mover.y = hx + rng.uniform(-8, 8), hy + rng.uniform(-6, 3)
                b.state, b.flower = "out", f
            self.bees.append(b)
        self.planted = []
        self.bg_seed = rng.random()
        self.sparks = []   # [x, y, vx, vy, life, color]
        self.trail = []    # waggle-dance footprints [x, y, life]
        self.bee_cache = {}
        self.bg = None

    def new_flower(self, kind, x, depth, head_y=None, bloom=1.0):
        rng, u, h, gy = self.rng, self.u, self.h, self.gy
        size, height = KINDS[kind][3], KINDS[kind][4]
        r = (2.2 + 2.8 * depth) * u * size * rng.uniform(0.85, 1.15)
        base_y = gy + (h - gy) * depth + 1
        if head_y is None:
            stem = ((h - gy) * 0.45 + h * 0.3 * rng.random()) * (0.6 + 0.4 * depth) * height
            head_y = max(h * 0.24 + r / ASPECT, base_y - stem)
            head_y = min(head_y, h - r / ASPECT - 1.5)
        return Flower(rng, kind, x, base_y, head_y, r, depth, bloom)

    def build_hive(self):
        rng, u, w, h = self.rng, self.u, self.w, self.h
        side = self.side
        self.hw = hw = max(6.0, 9.0 * u + w * 0.025)
        self.hx = hx = w / 2 + side * (w / 2 - hw * 0.8 - rng.uniform(2, 6))
        if self.hive == "wild":
            self.htop = 1.5
            self.hh = max(5.0, h * rng.uniform(0.28, 0.36))
            self.ex, self.ey = hx, self.htop + self.hh * 0.86
            self.face = (hx, self.htop + self.hh * 0.5)
        elif self.hive == "skep":
            self.hh = hh = hw * 0.62
            base = self.gy + (h - self.gy) * 0.45
            self.htop = base - hh
            self.ex, self.ey = hx, base - 0.6
            self.face = (hx, self.htop + hh * 0.45)
        else:
            boxes = rng.randint(2, 3)
            self.boxes = boxes
            self.hh = hh = boxes * max(2.6, 3.4 * u) + 1.5
            base = self.gy + (h - self.gy) * 0.5
            self.htop = base - hh
            self.ex, self.ey = hx, base - 1.4
            self.face = (hx, self.htop + hh * 0.55)

    def on_click(self, x, y):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        rng = self.rng
        y = clamp(y, self.h * 0.2, self.h - 2)
        depth = clamp((y - self.h * 0.3) / (self.h * 0.6))
        kind = rng.choice(self.kinds)
        f = self.new_flower(kind, x, depth, head_y=y, bloom=0.0)
        f.hx = x
        f.base_y = max(f.base_y, y + 3)
        self.flowers.append(f)
        self.planted.append(f)
        if len(self.planted) > 30:   # keep the patch from growing forever
            old = self.planted.pop(0)
            if old in self.flowers:
                self.flowers.remove(old)
        self.flowers.sort(key=lambda g: g.depth)

    # ------------------------------------------------------------------ move
    def update(self, dt):
        super().update(dt)
        rng, t = self.rng, self.t
        dt = min(dt, 0.25)
        for f in self.flowers:
            if f.bloom < 1.0:
                f.bloom = min(1.0, f.bloom + dt / 4.0)
                if f.bloom >= 1.0:
                    f.cache.clear()
                if f.open() and f.bloom - dt / 4.0 <= 0.65:
                    # scouts notice the new flower
                    scouts = [b for b in self.bees if b.state in ("out", "home")]
                    rng.shuffle(scouts)
                    for b in scouts[:3]:
                        b.state, b.flower = "out", f
            f.nod = max(0.0, f.nod - dt * 2.5)
        open_flowers = [f for f in self.flowers if f.open()]
        ptr = self.pointer
        if ptr is not None and not (0 <= ptr[0] < self.w and 0 <= ptr[1] < self.h):
            ptr = None
        for b in self.bees:
            self.move_bee(b, dt, t, open_flowers, ptr)
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 1.5 * dt
            s[4] -= dt
        self.sparks = [s for s in self.sparks if s[4] > 0]
        for p in self.trail:
            p[2] -= dt
        self.trail = [p for p in self.trail if p[2] > 0]

    def move_bee(self, b, dt, t, flowers, ptr):
        rng, m = self.rng, b.mover
        b.wing += dt * 40
        b.curious_cd -= dt
        st = b.state
        if st == "in":
            b.timer -= dt
            if b.timer <= 0 and flowers:
                b.state = "out"
                b.flower = self.pick_flower(b, flowers)
                m.x, m.y = self.ex + rng.uniform(-1, 1), self.ey
                m.heading = -math.pi / 2 + rng.uniform(-0.8, 0.8)
            return
        # curiosity: the pointer is a big strange flower
        if (ptr is not None and st in ("out", "home", "sip") and b.curious_cd <= 0
                and math.hypot(m.x - ptr[0], (m.y - ptr[1]) * ASPECT) < 16 * self.u + 6):
            b.resume, b.state = st, "curious"
            b.timer = rng.uniform(2.5, 4.5)
            b.orbit = math.atan2((m.y - ptr[1]) * ASPECT, m.x - ptr[0])
            st = "curious"
        if st == "curious":
            b.timer -= dt
            if ptr is None or b.timer <= 0:
                b.state = b.resume if b.resume != "sip" else "out"
                b.curious_cd = rng.uniform(5, 9)
                return
            b.orbit += dt * (2.2 + b.depth)
            rad = (3.0 + 2.0 * b.depth) * self.u + 1.5
            tx = ptr[0] + math.cos(b.orbit) * rad
            ty = ptr[1] + math.sin(b.orbit) * rad / ASPECT + math.sin(t * 5 + b.buzz) * 0.3
            self.glide(b, tx, ty, dt, 6.0)
            return
        if st == "out":
            f = b.flower
            if f is None or f not in self.flowers or not flowers:
                b.flower = f = self.pick_flower(b, flowers) if flowers else None
                if f is None:
                    b.state = "home"
                    return
            hx, hy = f.head(t)
            ty = hy - f.r / ASPECT * 0.35
            m.update(dt, t, (self.w, self.h), target=(hx, ty), margin=0)
            m.y += math.sin(t * 7 + b.buzz) * dt * 1.5
            if m.near(hx, ty, 2.5):
                b.state, b.timer = "sip", rng.uniform(1.6, 3.6)
                b.hover = (rng.uniform(-0.4, 0.4) * f.r, rng.uniform(-0.45, -0.15) * f.r / ASPECT)
                f.nod = 1.0
        elif st == "sip":
            f = b.flower
            if f is None or f not in self.flowers:
                b.state = "home"
                return
            hx, hy = f.head(t)
            ox, oy = b.hover
            self.glide(b, hx + ox + math.sin(t * 1.7 + b.buzz) * 0.4, hy + oy, dt, 8.0)
            b.timer -= dt
            b.pollen = min(1.0, b.pollen + dt * 0.35)
            if rng.random() < dt * 6:
                self.sparks.append([m.x + rng.uniform(-1, 1), m.y + rng.uniform(-0.5, 0.5),
                                    rng.uniform(-2, 2), rng.uniform(-2.5, -0.5), rng.uniform(0.5, 1.2),
                                    rng.choice([(255, 230, 90), (255, 200, 60), (255, 250, 180)])])
            if b.timer <= 0:
                b.visits += 1
                if b.visits < 3 and rng.random() < 0.55:
                    near = sorted(flowers, key=lambda g: abs(g.hx - f.hx) + abs(g.hy - f.hy) * 2)
                    b.flower = rng.choice(near[1:4] or near)
                    b.state = "out"
                else:
                    b.state = "home"
        elif st == "home":
            ty = self.ey - 0.5
            m.update(dt, t, (self.w, self.h), target=(self.ex, ty), margin=0)
            m.y += math.sin(t * 7 + b.buzz) * dt * 1.5
            if m.near(self.ex, ty, 2.5):
                if b.flower is not None and rng.random() < 0.4:
                    hx, hy = b.flower.head(t)
                    # waggle angle: from "up", the angle between the sun and the flower (seen from the hive)
                    sun = math.atan2((self.sun[1] - self.ey) * ASPECT, self.sun[0] - self.ex)
                    food = math.atan2((hy - self.ey) * ASPECT, hx - self.ex)
                    b.dance = (-math.pi / 2 + (food - sun), 0.0)
                    b.state, b.timer = "dance", rng.uniform(4.5, 7.0)
                else:
                    b.state, b.timer = "in", rng.uniform(1.5, 5.0)
                b.visits, b.pollen = 0, 0.0
        elif st == "dance":
            ang, ph = b.dance
            ph += dt / 1.6
            b.dance = (ang, ph)
            fx, fy = self.face
            run = 2.4 + 1.6 * self.u
            k = ph % 2.0
            ca, sa = math.cos(ang), math.sin(ang)
            loop_side = 1 if int(ph // 2) % 2 == 0 else -1
            if k % 2.0 < 1.0:   # the waggle run: straight, shaking side to side
                s = (k - 0.5) * run
                wag = math.sin(ph * 60) * 0.55
                x = fx + ca * s - sa * wag
                y = fy + (sa * s + ca * wag) / ASPECT
            else:               # loop back around, alternating sides
                a = (k - 1.0) * math.pi
                s = math.cos(a) * run * 0.5
                q = math.sin(a) * run * 0.55 * loop_side
                x = fx + ca * s - sa * q
                y = fy + (sa * s + ca * q) / ASPECT
            if rng.random() < dt * 12:
                self.trail.append([x, y, 2.5])
            b.facing = 1 if x >= m.x else -1
            m.x, m.y = x, y
            b.timer -= dt
            if b.timer <= 0:
                b.state, b.timer = "in", rng.uniform(1.0, 3.0)
                b.dance = None
            return
        # face the way we fly
        c = math.cos(m.heading)
        if abs(c) > 0.25:
            b.facing = 1 if c > 0 else -1

    def glide(self, b, tx, ty, dt, k):
        m = b.mover
        a = clamp(dt * k)
        nx, ny = m.x + (tx - m.x) * a, m.y + (ty - m.y) * a
        if abs(nx - m.x) > 0.02:
            b.facing = 1 if nx > m.x else -1
        m.heading = math.atan2((ny - m.y) * ASPECT, nx - m.x) if (nx, ny) != (m.x, m.y) else m.heading
        m.x, m.y = nx, ny

    def pick_flower(self, b, flowers):
        if not flowers:
            return None
        rng = self.rng
        # bees like flowers at about their own depth (so near bees stay near) and new flowers
        cands = rng.sample(flowers, min(4, len(flowers)))
        return min(cands, key=lambda f: abs(f.depth - b.depth) + rng.random() * 0.4)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        key = (cv.ramp, cv.w, cv.h)
        if self.bg is None or self.bg[0] != key:
            self.bg = (key, self.bake_background(cv.ramp))
        bgc = self.bg[1]
        cv.ch[:] = bgc.ch
        cv.fg[:] = bgc.fg
        cv.lv[:] = bgc.lv
        cv.bc[:] = bgc.bc
        t = self.t
        # sun shimmer
        sx, sy = self.sun
        for k in range(10):
            a = k / 10 * math.tau + t * 0.05
            ln = self.sun_r * (1.9 + 0.35 * math.sin(t * 1.3 + k * 1.7))
            for j in range(3):
                d = self.sun_r * 1.25 + (ln - self.sun_r * 1.25) * (j + 1) / 3
                cv.shade(sx + math.cos(a) * d, sy + math.sin(a) * d / ASPECT, 0.32 - j * 0.08, (255, 220, 120))
        # dance footprints on the hive
        for x, y, life in self.trail:
            cv.shade(x, y, 0.25 * clamp(life), (255, 220, 140), "over")
        # flowers and bees by depth (far first)
        items = [(f.depth, 0, i) for i, f in enumerate(self.flowers)]
        items += [(b.depth + 0.04, 1, i) for i, b in enumerate(self.bees) if b.state != "in"]
        items.sort()
        for _, kind, i in items:
            if kind == 0:
                self.draw_flower(cv, self.flowers[i])
            else:
                self.draw_bee(cv, self.bees[i])
        for x, y, vx, vy, life, col in self.sparks:
            ch = "*" if life > 0.8 else "+" if life > 0.45 else "·"
            cv.put(x, y, ch, scale(col, 0.5 + 0.5 * clamp(life)))

    def bake_background(self, ramp):
        w, h = self.w, self.h
        rng = random.Random(self.bg_seed)
        cv = Canvas(w, h, ramp)
        gy = self.gy
        sx, sy = self.sun
        r = self.sun_r
        # sky: a warm haze around the sun, sparse pale-blue air above the meadow
        seed = int(self.gy * 1000) % 997
        for y in range(0, int(gy) + 1):
            for x in range(w):
                d = math.hypot(x - sx, (y - sy) * ASPECT)
                haze = clamp(1 - d / (r * 7)) ** 1.5
                n = cellhash(x, y, seed)
                if n > 0.8 - haze * 0.5:
                    cv.shade(x, y, 0.1 + 0.2 * haze, mix((110, 160, 220), (255, 235, 170), haze))
        sun = Body()
        sun.circle(sx, sy, r, color=(255, 236, 150))
        sun.draw(cv, light=(0, 0), glow=1.2, ambient=1.0)
        # clouds
        for _ in range(rng.randint(1, 3)):
            cx = rng.uniform(0.1, 0.9) * w
            cy = rng.uniform(0.1, 0.3) * gy + 1
            if abs(cx - sx) < r * 5:
                cx = (cx + w / 2) % w
            cs = rng.uniform(1.6, 2.6) * self.u
            puffs = [(cx + (k - 2) * cs * 1.4 + rng.uniform(-1, 1), cy + rng.uniform(-0.3, 0.3) * cs / ASPECT,
                      cs * rng.uniform(1.0, 1.6)) for k in range(rng.randint(3, 6))]
            cseed = rng.randint(0, 999)
            x0 = int(min(p[0] - p[2] for p in puffs)) - 1
            x1 = int(max(p[0] + p[2] for p in puffs)) + 2
            for y in range(int(cy - cs * 1.2) - 1, int(cy + cs) + 2):
                for x in range(max(0, x0), min(w, x1)):
                    d = min(math.hypot(x + 0.5 - px, (y + 0.5 - py) * ASPECT) / pr for px, py, pr in puffs)
                    v = clamp(1.1 - d) * (0.65 + 0.35 * fbm(x * 0.3, y * 0.6, 2, cseed))
                    if y + 0.5 > cy + cs * 0.35:          # flat-ish bottoms
                        v *= 0.5
                    if v > 0.08:
                        cv.shade(x, y, 0.08 + 0.32 * v, mix((170, 180, 200), (255, 250, 240), v))
        # distant hills and a tree line
        hseed = rng.uniform(0, 100)
        for x in range(w):
            top = gy - 1.5 - (noise1(x * 0.05 + hseed) * 0.5 + 0.5) * h * 0.08 - noise1(x * 0.3 + hseed, 3) * 0.6
            for y in range(int(top), int(gy) + 1):
                v = 0.1 + 0.1 * (y - top) / max(1, gy - top)
                cv.shade(x, y, v, (90, 140, 100))
        # the meadow: grass texture that gets lusher toward the front
        gseed = int(hseed * 10)
        for y in range(int(gy), h):
            f = (y - gy) / max(1, h - gy)
            for x in range(w):
                n = cellhash(x, y, gseed)
                if n > 0.5 - f * 0.45:
                    g = clamp(0.5 + noise1(x * 0.11 + y * 0.4, gseed + 1) * 0.5)
                    col = mix((60, 120, 40), (150, 200, 70), g)
                    k = int(abs(n) * 97)
                    ch = GRASS_FRONT[k % len(GRASS_FRONT)] if f > 0.4 else ".,'`"[k % 4]
                    cv.put(x, y, ch, scale(col, 0.25 + 0.35 * f), level=0.1 + 0.15 * f)
                # tiny far flowers dotted in the grass
                elif n < -0.93 and f < 0.6:
                    cv.put(x, y, "·", hsv(rng.choice([0.0, 0.14, 0.8, 0.95]), 0.5, 0.75), level=0.2)
        self.paint_hive(cv)
        return cv

    def paint_hive(self, cv):
        hx, hw, top, hh = self.hx, self.hw, self.htop, self.hh
        light_x = 1 if self.sun[0] > hx else -1
        if self.hive == "wild":
            # an oak branch along the top, the comb hanging from it
            x0 = 0 if self.side < 0 else self.w - 1
            x1 = hx - self.side * hw * 1.4
            steps = int(abs(x1 - x0)) + 1
            for k in range(steps + 1):
                x = x0 + (x1 - x0) * k / steps
                y = 0.6 + 0.6 * k / steps + math.sin(k * 0.3) * 0.3
                cv.put(x, y, "=", (120, 85, 55))
                cv.put(x, y + 1, "~", (80, 55, 35))
                if k % 5 == 2:
                    cv.put(x + 1, y + 1.6, "%", (60, 140, 50))
                    cv.put(x, y + 1.6, "&", (80, 160, 60))
            for y in range(int(top), int(top + hh) + 1):
                f = (y - top) / hh
                half = hw * 0.5 * math.sin(math.pi * clamp(f * 0.85 + 0.12)) ** 0.7 * (1.1 - f * 0.4)
                for x in range(int(hx - half), int(hx + half) + 1):
                    e = abs(x + 0.5 - hx) / max(0.5, half)
                    lit = clamp(0.6 + 0.4 * light_x * (x - hx) / max(1, half))
                    pat = "/ \\_" if y % 2 == 0 else "\\_/ "
                    c = pat[(x + 400) % 4]
                    col = mix((150, 90, 20), (255, 190, 60), lit * (1 - e * 0.5))
                    if c == " ":
                        c = "o" if (x * 7 + y * 3) % 5 == 0 else "."
                        col = mix(col, (255, 220, 120), 0.4)
                    cv.put(x, y, c, col, level=0.6)
            ex, ey = self.ex, self.ey
            cv.put(ex, ey, "@", (35, 20, 10))
            cv.put(ex - 1, ey, "(", (90, 50, 15))
            cv.put(ex + 1, ey, ")", (90, 50, 15))
        elif self.hive == "skep":
            base = top + hh
            # a little wooden bench
            for x in range(int(hx - hw * 0.75), int(hx + hw * 0.75) + 1):
                cv.put(x, base + 0.2, "=", (140, 95, 60))
            for lx in (hx - hw * 0.6, hx + hw * 0.6):
                for y in range(int(base) + 1, int(base + 2.5 * self.u) + 2):
                    cv.put(lx, y, "|", (110, 75, 45))
            rows = int(hh) + 1
            for k in range(rows):
                y = base - 1 - k
                f = (k + 0.5) / rows
                half = hw * 0.55 * math.sqrt(max(0.0, 1 - f ** 2.2))
                for x in range(int(hx - half), int(hx + half) + 1):
                    nx = (x + 0.5 - hx) / max(0.5, half)
                    lit = clamp(0.55 + 0.45 * nx * light_x - f * 0.15)
                    c = "=" if (k % 2 == 0) else "~"
                    if (x + k * 3) % 7 == 0:
                        c = "-"
                    cv.put(x, y, c, mix((140, 95, 30), (245, 200, 100), lit), level=0.6)
            ex, ey = self.ex, self.ey
            cv.put(ex - 1, ey, "(", (60, 40, 15))
            cv.put(ex, ey, "_", (20, 12, 5))
            cv.put(ex + 1, ey, ")", (60, 40, 15))
        else:
            base = top + hh
            col = self.hive_color
            x0, x1 = int(hx - hw / 2), int(hx + hw / 2)
            # stand
            for x in range(x0 - 1, x1 + 2):
                cv.put(x, base, "=", (120, 85, 55))
            for lx in (x0, x1):
                for y in range(int(base) + 1, int(base + 2 * self.u) + 2):
                    cv.put(lx, y, "|", (100, 70, 45))
            # boxes
            bh = (hh - 1.5) / self.boxes
            for bi in range(self.boxes):
                yt = top + 1.5 + bi * bh
                for y in range(int(yt), int(yt + bh)):
                    for x in range(x0, x1 + 1):
                        lit = clamp(0.65 + 0.35 * light_x * (x - hx) / max(1, hw / 2))
                        edge = x in (x0, x1)
                        cv.put(x, y, "|" if edge else ("_" if y == int(yt + bh) - 1 else ":"),
                               scale(col, 0.45 + 0.45 * lit) if not edge else scale(col, 0.4), level=0.5)
                # a hand grip
                gy_ = int(yt + bh / 2)
                for x in range(int(hx - 1), int(hx + 2)):
                    cv.put(x, gy_, "=", scale(col, 0.35))
            # roof
            for x in range(x0 - 1, x1 + 2):
                cv.put(x, top + 0.6, "_", (200, 70, 60))
                cv.put(x, top + 1.2, "#", (170, 60, 50))
            # entrance slot and landing board
            ey = int(self.ey)
            for x in range(int(hx - hw * 0.25), int(hx + hw * 0.25) + 1):
                cv.put(x, ey, "_", (25, 15, 10))
                cv.put(x, ey + 1, "=", (150, 110, 70))

    def draw_flower(self, cv, f):
        t = self.t
        hx, hy = f.head(t)
        sway = hx - f.hx
        grow = clamp(f.bloom / 0.35)   # the stem grows first, then the head opens
        green = mix((40, 110, 40), (90, 180, 70), f.depth)
        # stem: a gentle curve from the ground to the head, bending with the head
        y0 = min(self.h - 1 + 0.0, f.base_y)
        top = y0 + (hy - y0) * grow
        n = int(abs(y0 - top)) + 1
        prev = None
        for k in range(n + 1):
            s = k / max(1, n)
            y = y0 + (top - y0) * s
            x = f.x0 + (f.hx - f.x0) * s + sway * s * s * grow
            if prev is not None:
                cv.put(x, y, slope_ch(x - prev[0], y - prev[1]), scale(green, 0.55 + 0.35 * f.depth), level=0.4)
            prev = (x, y)
        for lf, side in f.leaves:
            if grow < lf + 0.2:
                continue
            y = y0 + (top - y0) * lf
            x = f.x0 + (f.hx - f.x0) * lf + sway * lf * lf
            ln = max(1, int(f.r * 0.7))
            for j in range(1, ln + 1):
                cv.put(x + side * j, y - (j - 1) * 0.5 + (0.5 if j == ln else 0),
                       "_" if j < ln else ("/" if side > 0 else "\\"), scale(green, 0.8), level=0.4)
        if f.bloom < 0.3:
            return
        stage = 1.0 if f.bloom >= 1.0 else round(min(1.0, (f.bloom - 0.3) / 0.6) * 8) / 8
        key = (cv.ramp, stage)
        cells = f.cache.get(key)
        if cells is None:
            sz = int(f.r * 2.6) + 6
            cells = bake(lambda c, x, y: self.paint_head(c, x, y, f, stage), sz, int(sz / ASPECT * 1.6) + 6, cv.ramp)
            f.cache[key] = cells
        blit(cv, cells, hx, hy)

    def paint_head(self, cv, x, y, f, stage):
        r = f.r
        if stage <= 0.05:   # a closed green bud
            b = Body()
            b.ellipse(x, y, r * 0.3, r * 0.45, math.pi / 2, color=(80, 150, 60))
            b.draw(cv, depth=f.depth)
            return
        b = Body(blend=0.25)
        if f.kind == "lavender":
            for k in range(7):
                yy = y - (k - 2) * r * 0.32 / ASPECT * 2.2 * stage
                b.circle(x + (0.3 if k % 2 else -0.3), yy, r * (0.36 - k * 0.025) * (0.4 + 0.6 * stage),
                         color=mix(f.color, (240, 220, 255), k / 9))
            b.draw(cv, depth=f.depth, ambient=0.6)
            return
        fade = 0.55 + 0.45 * f.depth
        if f.kind == "poppy":
            # broad, round, cupped petals: soft Body blobs around a dark eye
            for k in range(f.n):
                a = f.rot + k / f.n * math.tau
                d = r * 0.42 * stage
                b.circle(x + math.cos(a) * d, y + math.sin(a) * d / ASPECT, max(0.5, r * 0.5 * stage),
                         color=mix(f.color, (255, 255, 255), 0.18 * (k % 2)))
            b.draw(cv, depth=f.depth, ambient=0.6, edge=1.0)
            eye = Body()
            eye.circle(x, y, max(0.5, r * 0.2), color=f.center)
            eye.draw(cv, depth=f.depth, mode="over")
            return
        # daisies, sunflowers, cosmos: petals as radial strokes ( \ | / ) around a round center
        cr = {"sunflower": 0.42, "daisy": 0.3}.get(f.kind, 0.24)
        n = f.n
        width = {"cosmos": 0.55, "sunflower": 0.1}.get(f.kind, 0.2)
        reach = r * (cr + (1 - cr) * stage)
        for yy in range(int(y - reach / ASPECT) - 1, int(y + reach / ASPECT) + 2):
            for xx in range(int(x - reach) - 1, int(x + reach) + 2):
                dx, dy = xx + 0.5 - x, (yy + 0.5 - y) * ASPECT
                d = math.hypot(dx, dy)
                q = d / max(0.5, reach)
                if q > 1.0 or d < r * cr * 0.8:
                    continue
                a = math.atan2(dy, dx)
                petal = math.cos(n * (a - f.rot)) * 0.5 + 0.5        # 1 on a petal's axis, 0 between
                if petal < width + q * 0.25 and n > 0 and q > 0.3:
                    continue
                lit = clamp(0.6 - 0.4 * (dx * 0.55 + dy * 0.85) / max(1.0, d))
                col = mix(scale(f.color, 0.6), f.color, lit)
                if q > 0.86:
                    ch = "'" if dy < 0 else "."
                    col = scale(col, 0.8)
                else:
                    ch = slope_ch(dx, dy / ASPECT)
                cv.put(xx, yy, ch, scale(col, fade), level=0.5)
        b.circle(x, y, max(0.6, r * cr), color=f.center)
        center = f.center
        seeds = f.kind == "sunflower"

        def pattern(px, py, i, inside):
            if seeds and (int(px * 1.3) + int(py * 2.0)) % 2 == 0:
                return scale(center, 0.7)
            return None
        b.draw(cv, depth=f.depth, pattern=pattern, ambient=0.65, edge=0.9, mode="over")

    def draw_bee(self, cv, b):
        m = b.mover
        wing = int(b.wing) % 2
        sq = round(b.size * 2) / 2
        key = (cv.ramp, sq, b.facing, wing, round(b.depth * 4), b.pollen > 0.3)
        cells = self.bee_cache.get(key)
        if cells is None:
            sz = int(sq * 2.4) + 6
            cells = bake(lambda c, x, y: self.paint_bee(c, x, y, sq, b.facing, wing, b.depth, b.pollen > 0.3),
                         sz, int(sz / ASPECT) + 6, cv.ramp)
            self.bee_cache[key] = cells
        bob = math.sin(self.t * 9 + b.buzz) * 0.25 if b.state not in ("sip", "dance") else 0.0
        blit(cv, cells, m.x, m.y + bob, over=True)

    def paint_bee(self, cv, x, y, s, f, wing, depth, pollen):
        fade = 0.55 + 0.45 * depth
        # wings first, see-through: a pale oval of light dots with a slightly brighter rim,
        # flickering between "up" and "swept back"
        up = 1.2 if wing else 0.42
        for k, (ln, wd, back) in enumerate(((0.36, 0.16, 0.02), (0.27, 0.12, 0.22))):
            dx, dy = -f * math.cos(up), -math.sin(up)          # stretched space, pointing out of the body
            cx = x + f * s * (0.08 - back) + dx * s * ln * 0.95
            cy = (y * ASPECT - s * 0.24 + dy * s * ln * 0.95) / ASPECT
            wing_oval(cv, cx, cy, s * ln, s * wd, math.atan2(dy, dx), scale(WING, (1.0 - 0.25 * k) * fade))
        body = Body(blend=0.45)
        # a chubby striped abdomen, a fuzzy thorax, a dark head, a tiny stinger
        ax = x - f * s * 0.18
        body.ellipse(ax, y + s * 0.02 / ASPECT, s * 0.36, s * 0.3, f * 0.12, color=YELLOW)
        body.circle(x + f * s * 0.17, y - s * 0.02 / ASPECT, s * 0.19, color=FUZZ)
        body.circle(x + f * s * 0.38, y + s * 0.03 / ASPECT, s * 0.15, color=(95, 70, 40))
        body.capsule(x - f * s * 0.52, y + s * 0.06 / ASPECT, x - f * s * 0.64, y + s * 0.08 / ASPECT,
                     s * 0.06, s * 0.02, color=STRIPE)
        band = max(0.7, s * 0.12)

        def pattern(px, py, i, inside):
            if i == 0:
                u = (px - ax) * f + s * 0.06
                if u > -s * 0.3 and int((u + 10 * band) / band) % 2 == 1:
                    return STRIPE
            return None
        body.spot(x + f * s * 0.44, y - s * 0.02 / ASPECT, 0.2, (20, 14, 8), "o" if s >= 6 else None)
        body.draw(cv, depth=depth, pattern=pattern, edge=0.8, ambient=0.7)
        # antennae, legs and the pollen basket
        hx = x + f * s * 0.42
        hy = y - s * 0.14 / ASPECT
        cv.put(hx + f * 0.6, hy - 0.6, "/" if f > 0 else "\\", scale((150, 110, 60), fade), level=0.5)
        if s >= 5:
            ly = y + s * 0.27 / ASPECT + 0.3
            for lx in (x + f * s * 0.08, x + f * s * 0.26):
                cv.put(lx, ly, "\\" if f > 0 else "/", scale((120, 90, 50), fade), level=0.4)
        if pollen:
            cv.put(x - f * s * 0.02, y + s * 0.3 / ASPECT + 0.4, "o", scale((255, 150, 30), fade), level=0.8)
