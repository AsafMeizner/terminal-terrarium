"""An ant colony seen from above: trails appear out of nothing.

No ant knows where the food is or what a "highway" is. Each one follows three rules:
  1. wander randomly; if you smell food nearby, walk to it,
  2. carry a crumb home, dropping scent (pheromone) as you go, strongest near the food,
  3. if you smell a trail, walk up it (toward the stronger end).
Rule 3 makes ants follow the scent rule 2 leaves, which brings more ants, which lay more scent...
so busy highways form between the nest and the food, and fade away when the food runs out
(the scent evaporates). The scent lives on a grid the size of the screen, drawn as faint dots.
Big screens draw each ant as a tiny shapes.Body (head, thorax, abdomen) with walking legs.
"""
import math
import random

from ..engine import ASPECT, Canvas, Scene, clamp, mix, noise2, scale
from ..shapes import Body

# soil palettes: (name, base grain color, accent, pebble color, mound color)
SOILS = [
    ("loam", (92, 70, 50), (120, 95, 65), (120, 115, 105), (150, 115, 80)),
    ("clay", (130, 70, 45), (165, 95, 60), (140, 110, 95), (190, 115, 75)),
    ("sand", (150, 130, 90), (185, 165, 115), (160, 150, 130), (215, 190, 135)),
    ("forest", (70, 60, 40), (95, 80, 45), (105, 100, 90), (130, 105, 65)),
    ("ash", (90, 90, 88), (115, 112, 105), (140, 140, 135), (150, 145, 135)),
]
ANTS = [  # (species, body color, head color)
    ("red", (205, 85, 45), (170, 60, 35)),
    ("black", (150, 140, 135), (120, 112, 108)),
    ("golden", (220, 160, 70), (190, 125, 50)),
]
FOODS = [  # crumb colors
    [(230, 190, 120), (210, 160, 90), (240, 210, 150)],       # cookie
    [(250, 250, 250), (230, 235, 240), (255, 255, 230)],      # sugar
    [(240, 80, 60), (255, 130, 60), (250, 60, 90)],           # fruit
    [(120, 200, 80), (90, 170, 60), (160, 220, 100)],         # leaf bits
    [(225, 205, 160), (200, 180, 130), (240, 225, 185)],      # seeds
]


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


def blit(cv, cells, x, y):
    ix, iy = int(math.floor(x)), int(math.floor(y))
    W, H = cv.w, cv.h
    ch, fg, lv, bc = cv.ch, cv.fg, cv.lv, cv.bc
    for dx, dy, c, f, l in cells:
        px, py = ix + dx, iy + dy
        if 0 <= px < W and 0 <= py < H:
            i = py * W + px
            ch[i] = c
            fg[i] = f
            lv[i] = l
            bc[i] = f


def slope_ch(dx, dy):
    """Line glyph for a direction in stretched space (dy already * ASPECT)."""
    ax, ay = abs(dx), abs(dy)
    if ax > 2.0 * ay:
        return "-"
    if ay > 2.0 * ax:
        return "|"
    return "\\" if dx * dy > 0 else "/"


class Ant:
    __slots__ = ("x", "y", "a", "state", "timer", "carry", "since", "speed", "wob", "legs", "trips")

    def __init__(self, rng, x, y, speed):
        self.x, self.y = x, y
        self.a = rng.uniform(-math.pi, math.pi)
        self.state = "inside"
        self.timer = 0.0
        self.carry = None
        self.since = 0.0
        self.speed = speed * rng.uniform(0.85, 1.15)
        self.wob = rng.uniform(0, 100)
        self.legs = rng.uniform(0, 10)
        self.trips = 0


class Pile:
    def __init__(self, rng, x, y, amount, colors):
        self.x, self.y = x, y
        self.max = self.amount = amount
        self.colors = colors
        self.r = 1.2 + amount ** 0.5 * 0.35
        # crumbs scattered in a little heap, biggest in the middle
        self.crumbs = []
        for k in range(amount):
            a = rng.uniform(0, math.tau)
            d = math.sqrt(rng.random()) * self.r
            self.crumbs.append((x + math.cos(a) * d, y + math.sin(a) * d / ASPECT, rng.choice(colors),
                                rng.choice("o*.,%#o8")))
        self.crumbs.sort(key=lambda c: -math.hypot(c[0] - x, (c[1] - y) * ASPECT))  # take outer crumbs first


class Ants(Scene):
    name = "ants"
    title = "Ant Colony"
    blurb = "ants wander, find crumbs and lay scent trails; highways emerge and fade"
    tags = ("nature", "creatures", "emergent", "simulation")
    interactions = "click to drop a pile of food"
    options = {
        "ants": (0, "how many ants (0 = based on size, max 220)"),
        "soil": ("random", "soil: loam, clay, sand, forest, ash or random"),
        "species": ("random", "ants: red, black, golden or random"),
        "trails": (True, "draw the scent trails"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        soil = self.opt("soil")
        names = [s[0] for s in SOILS]
        self.soil = SOILS[names.index(soil)] if soil in names else rng.choice(SOILS)
        sp = self.opt("species")
        names = [s[0] for s in ANTS]
        if sp in names:
            self.species = ANTS[names.index(sp)]
        else:   # gray ants on gray ash would vanish
            self.species = rng.choice([a for a in ANTS if not (a[0] == "black" and self.soil[0] == "ash")])
        self.big = w >= 96   # Body ants with legs from 100x30 terminals up; glyph ants below
        self.L = clamp(w / 30, 4.0, 6.0) if self.big else 1.0
        self.nest = (w * rng.uniform(0.2, 0.8), h * rng.uniform(0.25, 0.75))
        self.nest_r = max(1.5, min(w, h * ASPECT) * 0.035)
        n = self.opt("ants") or int(w * h / (110 if self.big else 45) * self.density)
        n = max(6, min(220, n))
        speed = max(4.5, min(11.0, w / 16))
        nx, ny = self.nest
        self.ants = []
        for k in range(n):
            a = Ant(rng, nx, ny, speed)
            if rng.random() < 0.6:   # many are already out foraging
                d = rng.uniform(0, min(w, h * ASPECT) * 0.3)
                ang = rng.uniform(0, math.tau)
                a.x = clamp(nx + math.cos(ang) * d, 1, w - 2)
                a.y = clamp(ny + math.sin(ang) * d / ASPECT, 1, h - 2)
                a.a = ang
                a.state = "forage"
                a.timer = rng.uniform(15, 40)
            else:
                a.timer = rng.uniform(0, 8)
            self.ants.append(a)
        self.grid = [0.0] * (w * h)
        self.piles = []
        far = min(w, h * ASPECT) * 0.3
        for _ in range(rng.randint(2, 4)):
            for _try in range(20):
                x, y = rng.uniform(3, w - 4), rng.uniform(2, h - 3)
                if math.hypot(x - nx, (y - ny) * ASPECT) > far:
                    break
            self.add_pile(x, y, rng.randint(25, 60))
        self.respawn = rng.uniform(10, 25)
        self.evap_acc = 0.0
        self.stock = 0
        self.cache = {}
        self.bg = None
        self.bg_seed = rng.random()

    def add_pile(self, x, y, amount):
        x = clamp(x, 2, self.w - 3)
        y = clamp(y, 1.5, self.h - 2)
        self.piles.append(Pile(self.rng, x, y, amount, self.rng.choice(FOODS)))
        if len(self.piles) > 8:
            self.piles.pop(0)

    def on_click(self, x, y):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        self.add_pile(x, y, self.rng.randint(30, 55))

    # ------------------------------------------------------------------ move
    def sense(self, x, y):
        ix, iy = int(x), int(y)
        if 0 <= ix < self.w and 0 <= iy < self.h:
            return self.grid[iy * self.w + ix]
        return -1.0

    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.2)
        rng = self.rng
        w, h = self.w, self.h
        grid = self.grid
        nx, ny = self.nest
        nr = self.nest_r
        sd = 3.0   # sensor distance (stretched cells)
        piles = self.piles
        for a in self.ants:
            st = a.state
            a.legs += dt * a.speed * 1.4
            if st == "inside":
                a.timer -= dt
                if a.timer <= 0:
                    a.state = "forage"
                    a.a = rng.uniform(-math.pi, math.pi)
                    a.x = nx + math.cos(a.a) * nr * 0.6
                    a.y = ny + math.sin(a.a) * nr * 0.6 / ASPECT
                    a.timer = rng.uniform(20, 45)
                    a.since = 0.0
                continue
            a.since += dt
            ca, sa = math.cos(a.a), math.sin(a.a)
            turn = math.sin(self.t * 1.7 + a.wob) * 1.2 + rng.uniform(-2.5, 2.5)
            if st == "forage":
                a.timer -= dt
                target = None
                for p in piles:   # smell food nearby
                    if abs(p.x - a.x) < p.r + 5 and abs(p.y - a.y) < (p.r + 5) / ASPECT:
                        target = p
                        break
                if target is not None:
                    want = math.atan2((target.y - a.y) * ASPECT, target.x - a.x)
                    turn = ((want - a.a + math.pi) % math.tau - math.pi) * 5
                    if math.hypot(target.x - a.x, (target.y - a.y) * ASPECT) < target.r * 0.8 + 0.6:
                        target.amount -= 1
                        c = target.crumbs.pop() if target.crumbs else (0, 0, target.colors[0], "o")
                        a.carry = c[2]
                        a.state, a.since = "return", 0.0
                        a.a += math.pi
                        if target.amount <= 0:
                            piles.remove(target)
                        continue
                else:
                    # follow the scent: three feelers, steer toward the strongest
                    l = self.sense(a.x + math.cos(a.a - 0.6) * sd, a.y + math.sin(a.a - 0.6) * sd / ASPECT)
                    c = self.sense(a.x + ca * sd, a.y + sa * sd / ASPECT)
                    r = self.sense(a.x + math.cos(a.a + 0.6) * sd, a.y + math.sin(a.a + 0.6) * sd / ASPECT)
                    best = max(l, c, r)
                    if best > 0.03:
                        if best == c:
                            turn *= 0.15
                        else:
                            turn = (-3.5 if best == l else 3.5) + turn * 0.15
                        # walking the wrong way down a trail? the scent behind is stronger: turn round
                        back = self.sense(a.x - ca * sd, a.y - sa * sd / ASPECT)
                        if back > best * 1.15 and rng.random() < dt * 2.5:
                            a.a += math.pi
                if a.timer <= 0:
                    a.state, a.since = "return", 0.0
            else:  # return home, laying scent if we carry food
                want = math.atan2((ny - a.y) * ASPECT, nx - a.x)
                turn = ((want - a.a + math.pi) % math.tau - math.pi) * 3.0 + turn * 0.35
                if a.carry is not None:
                    i = int(a.y) * w + int(a.x)
                    if 0 <= i < w * h:
                        grid[i] = min(1.0, grid[i] + dt * 5.0 * math.exp(-a.since / 9.0))
                if math.hypot(nx - a.x, (ny - a.y) * ASPECT) < nr * 0.7:
                    if a.carry is not None:
                        self.stock += 1
                        a.trips += 1
                    a.carry = None
                    a.state = "inside"
                    a.timer = rng.uniform(0.5, 3.0)
                    continue
            a.a += turn * dt
            a.x += math.cos(a.a) * a.speed * dt
            a.y += math.sin(a.a) * a.speed * dt / ASPECT
            # walls: turn back in
            if a.x < 1 or a.x > w - 2 or a.y < 0.5 or a.y > h - 1.5:
                a.x = clamp(a.x, 1, w - 2)
                a.y = clamp(a.y, 0.5, h - 1.5)
                a.a = math.atan2((h / 2 - a.y) * ASPECT, w / 2 - a.x) + rng.uniform(-1, 1)
        # scent evaporates (every few frames, on the whole grid)
        self.evap_acc += dt
        if self.evap_acc > 0.15:
            k = 0.5 ** (self.evap_acc / 7.0)
            self.grid = [v * k if v > 0.004 else 0.0 for v in grid]
            self.evap_acc = 0.0
        # new food shows up now and then
        if len(piles) < 2:
            self.respawn -= dt
            if self.respawn <= 0:
                self.respawn = rng.uniform(12, 30)
                far = min(w, h * ASPECT) * 0.25
                for _try in range(20):
                    x, y = rng.uniform(3, w - 4), rng.uniform(2, h - 3)
                    if math.hypot(x - nx, (y - ny) * ASPECT) > far:
                        break
                self.add_pile(x, y, rng.randint(20, 50))

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
        # the scent trails: faint dots, brighter where the trail is strong
        if self.opt("trails"):
            tc = self.trail_color
            ch, fg, lv = cv.ch, cv.fg, cv.lv
            for i, v in enumerate(self.grid):
                if v > 0.02 and lv[i] < 0.25:
                    s = clamp(v ** 0.5)
                    ch[i] = "." if s < 0.3 else "·" if s < 0.5 else ":" if s < 0.75 else "•"
                    c = scale(tc, 0.35 + 0.65 * s)
                    fg[i] = (int(c[0]) & ~3, int(c[1]) & ~3, int(c[2]) & ~3)
                    lv[i] = 0.2
        # food
        for p in self.piles:
            for x, y, col, c in p.crumbs:
                cv.put(x, y, c, col, level=0.6)
        # the ants
        L = self.L
        body, head = self.species[1], self.species[2]
        for a in self.ants:
            if a.state == "inside":
                continue
            q = int(round(a.a / math.tau * 16)) % 16
            leg = int(a.legs) % 2
            k = (cv.ramp, q, leg, a.carry)
            cells = self.cache.get(k)
            if cells is None:
                ang = q / 16 * math.tau
                sz = int(L * 3) + 6
                cells = bake(lambda c, x, y: self.paint_ant(c, x, y, ang, leg, a.carry, body, head),
                             sz, sz // 2 + 5, cv.ramp)
                self.cache[k] = cells
            blit(cv, cells, a.x, a.y)

    def paint_ant(self, cv, x, y, ang, leg, carry, body, head):
        ca, sa = math.cos(ang), math.sin(ang)
        if not self.big:
            # tiny screens: a head dot in front of a body glyph
            cv.put(x, y, "o", body, level=0.8)
            cv.put(x + ca * 1.0, y + sa * 0.5, "·" if carry is None else "*", head if carry is None else carry,
                   level=0.7)
            return
        L = self.L

        def at(t, side=0.0):   # a point t along the body (stretched units), side to the left/right
            return x + ca * t - sa * side, y + (sa * t + ca * side) / ASPECT

        # legs first, under the body: three per side, alternating tripods
        for i, off in enumerate((-0.28, 0.0, 0.28)):
            for side in (-1, 1):
                swing = (0.22 if (i % 2 == 0) == (side > 0) else -0.22) * (1 if leg else -1)
                bx, by = at(off * L * 0.5 + 0.05 * L, 0)
                tx, ty = at((off * 1.3 + swing) * L * 0.6 + 0.05 * L, side * L * 0.42)
                ch = slope_ch(tx - bx, (ty - by) * ASPECT)
                cv.put(tx, ty, ch, scale(head, 0.55), level=0.4)
        b = Body(blend=0.25)
        b.ellipse(*at(-0.32 * L), L * 0.27, L * 0.19, ang, color=body)      # abdomen (gaster)
        b.ellipse(*at(0.04 * L), L * 0.14, L * 0.09, ang, color=head)       # thorax
        b.circle(*at(0.33 * L), L * 0.13, color=head)                       # head
        b.draw(cv, depth=1.0, edge=0.8, ambient=0.6)
        # antennae
        hx, hy = at(0.45 * L)
        for side in (-1, 1):
            tx, ty = at(0.62 * L, side * L * 0.22)
            cv.put(tx, ty, slope_ch(tx - hx, (ty - hy) * ASPECT), scale(head, 0.6), level=0.4)
        if carry is not None:
            cx, cy = at(0.62 * L)
            cv.put(cx, cy, "o", carry, level=0.9)

    def bake_background(self, ramp):
        w, h = self.w, self.h
        rng = random.Random(self.bg_seed)
        cv = Canvas(w, h, ramp)
        name, base, accent, pebble, mound = self.soil
        self.trail_color = mix((255, 230, 140), self.species[1], 0.25) if name != "sand" else (255, 250, 210)
        s = rng.randint(0, 999)
        for y in range(h):
            for x in range(w):
                n = noise2(x * 0.08, y * 0.16, s)
                g = noise2(x * 0.9, y * 1.7, s + 1)
                if g > 0.55 - n * 0.2:
                    ch = ".,'`"[int((g + 1) * 37) % 4]
                    cv.put(x, y, ch, scale(mix(base, accent, clamp(n + 0.5)), 0.45 + 0.25 * g), level=0.1)
                elif n > 0.55 and g < -0.6:
                    cv.put(x, y, ":", scale(accent, 0.5), level=0.1)
        # pebbles
        for _ in range(int(w * h / 90)):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            cv.put(x, y, rng.choice("oO0o."), scale(pebble, rng.uniform(0.45, 0.8)), level=0.15)
        # twigs, and leaves for forest floors
        for _ in range(rng.randint(1, 3)):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            ang = rng.uniform(0, math.pi)
            ln = rng.uniform(6, 16)
            for k in range(int(ln)):
                px, py = x + math.cos(ang) * k, y + math.sin(ang) * k / ASPECT
                cv.put(px, py, slope_ch(math.cos(ang), math.sin(ang)), (95, 70, 45), level=0.2)
        if name == "forest":
            for _ in range(rng.randint(2, 4)):
                lf = Body()
                x, y = rng.uniform(0, w), rng.uniform(0, h)
                lf.ellipse(x, y, rng.uniform(3, 6), rng.uniform(1.2, 2.2), rng.uniform(0, math.pi),
                           color=rng.choice([(120, 100, 40), (150, 90, 40), (90, 110, 50)]))
                lf.draw(cv, depth=0.0, ambient=0.4)
        # the nest: a mound of dug-out grains around a dark hole
        nx, ny = self.nest
        nr = self.nest_r
        for y in range(int(ny - nr * 2.4 / ASPECT) - 1, int(ny + nr * 2.4 / ASPECT) + 2):
            for x in range(int(nx - nr * 2.4) - 1, int(nx + nr * 2.4) + 2):
                d = math.hypot(x + 0.5 - nx, (y + 0.5 - ny) * ASPECT) / nr
                if d < 0.75:
                    cv.fill_box(x, y, x + 1, y + 1)   # the hole: nothing but dark
                elif d < 2.3:
                    k = 1 - abs(d - 1.2) / 1.1
                    lit = clamp(0.55 - 0.45 * ((x - nx) * 0.6 + (y - ny) * ASPECT * 0.8) / (nr * d))
                    if rng.random() < 0.45 + 0.6 * k:
                        c = rng.choice(".:oo*'") if k < 0.6 else rng.choice("oO0@o*")
                        cv.put(x, y, c, scale(mound, (0.45 + 0.55 * k) * (0.6 + 0.5 * lit)), level=0.3)
        return cv
