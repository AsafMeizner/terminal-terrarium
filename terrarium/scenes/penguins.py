"""Penguins on an icy shore, with the sea cut away so you can watch them swim.

Each penguin is a shapes.Body: a fat ellipse with a white belly and dark back (a pattern picks the
color by which side of the body a cell is on), a round head, a beak, flippers and feet. All the
poses are the same parts turned along one body axis: upright and rocking side to side when it
waddles, flat on its belly when it slides, streamlined when it swims. Simple rules drive them:
stand, look around, waddle somewhere, belly-slide, flap, hop in, swim fast, leap back out.
"""
import math
import random

from ..engine import ASPECT, Canvas, Scene, clamp, gradient, hsv, mix, noise1, scale
from ..shapes import Body, Mover

WHITE = (240, 245, 252)
BS = "\\"
# species: back color, beak, feet, size, extras
SPECIES = {
    "emperor": {"back": (78, 84, 108), "beak": (235, 120, 60), "feet": (150, 110, 90), "size": 1.25},
    "rockhopper": {"back": (70, 74, 92), "beak": (225, 80, 45), "feet": (235, 150, 160), "size": 0.85},
    "littleblue": {"back": (90, 135, 200), "beak": (110, 110, 125), "feet": (230, 190, 200), "size": 0.68},
    "gentoo": {"back": (74, 80, 100), "beak": (245, 110, 50), "feet": (250, 140, 60), "size": 1.0},
}


def cellhash(x, y, s=0):
    """A cheap per-cell random number in [-1, 1] (for sparse speckle that shouldn't clump)."""
    n = (x * 374761393 + y * 668265263 + s * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 32767.5 - 1.0


def bake(draw_fn, w, h, ramp):
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


class Penguin:
    def __init__(self, rng, kind, x, y, u, pid):
        sp = SPECIES[kind]
        self.kind = kind
        self.id = pid
        self.L = (16.0 + rng.uniform(-1.5, 2.0)) * sp["size"] * u   # length/height, stretched units
        self.x, self.y = x, y            # center of the body, in cells
        self.foot = y                    # the y of its feet line on the ice
        self.facing = rng.choice((-1, 1))
        self.state = "stand"
        self.timer = rng.uniform(0.5, 4.0)
        self.target = x
        self.phase = rng.uniform(0, math.tau)
        self.flap = 0.0
        self.vx = self.vy = 0.0
        self.mover = None
        self.angle = 0.0       # swim/flight direction
        self.happy = 0.0
        self.fish = None


class Penguins(Scene):
    name = "penguins"
    title = "Penguins"
    blurb = "penguins waddle, belly-slide and dive off an ice shelf; watch them swim underwater"
    tags = ("nature", "creatures", "cold", "cozy")
    interactions = "click to toss a fish: the nearest penguins waddle, slide or swim to grab it"
    options = {
        "penguins": (0, "colony size (0 = random for the screen size)"),
        "species": ("mixed", "emperor, rockhopper, littleblue, gentoo or mixed"),
        "sky": ("random", "day, dusk, night or random"),
        "snow": (True, "falling snow"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.u = u = clamp(min(h / 38, w / 100), 0.45, 1.5)
        sky = self.opt("sky")
        self.sky = sky if sky in ("day", "dusk", "night") else rng.choice(("day", "dusk", "night"))
        self.horizon = h * rng.uniform(0.3, 0.38)
        self.side = rng.choice((-1, 1))                 # -1: ice on the left
        frac = rng.uniform(0.42, 0.6)
        self.edge = w * frac if self.side < 0 else w * (1 - frac)
        self.ice_top = h * rng.uniform(0.5, 0.56)
        self.band = max(2.0, 3.0 * u)                     # the walkable top of the ice
        self.water = self.ice_top + self.band + max(1.0, 1.5 * u)
        self.bump = rng.uniform(0, 100)
        # a floating iceberg on the water side, most of it under water
        self.berg = None
        if rng.random() < 0.7:
            wx0, wx1 = (self.edge + 12, w - 4) if self.side < 0 else (4, self.edge - 12)
            if wx1 - wx0 > 14:
                self.berg = (rng.uniform(wx0 + 5, wx1 - 5), rng.uniform(4, 7) * u, rng.uniform(0, 100))
        # the colony
        sp = self.opt("species")
        if sp in SPECIES:
            kinds = [sp]
        else:
            ks = list(SPECIES)
            rng.shuffle(ks)
            kinds = ks[:rng.randint(1, 3)]
        ice_w = self.edge if self.side < 0 else w - self.edge
        mean = sum(SPECIES[k]["size"] for k in kinds) / len(kinds)
        n = self.opt("penguins") or max(2, int(ice_w / (11 * mean * u) * rng.uniform(0.8, 1.25) * self.density ** 0.5))
        n = min(n, 40)
        self.penguins = []
        for k in range(n):
            kind = rng.choice(kinds)
            x = self.ice_x((k + rng.uniform(0.25, 0.75)) / n)   # spread out along the ice
            foot = self.ice_top + rng.uniform(0.3, 1.0) * self.band
            p = Penguin(rng, kind, x, foot, u, k)
            p.y = foot - p.L * 0.5 / ASPECT
            if rng.random() < 0.25:  # some start in the water
                self.to_swim(p, rng.uniform(0.2, 0.8))
            self.penguins.append(p)
        self.flakes = [[rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.3, 1.0)] for _ in range(self.count(45))]
        self.bubbles = []
        self.splashes = []
        self.fish = []            # tossed fish: dicts with position, landing spot and state
        self.cache = {}
        self.bg = None
        self.bg_seed = rng.random()

    # ------------------------------------------------------------------ geometry helpers
    def ice_x(self, f):
        """A point across the ice from the screen edge to near the ice edge (f in 0..1)."""
        if self.side < 0:
            return 2 + (self.edge - 4) * f
        return self.edge + 2 + (self.w - self.edge - 4) * f

    def on_ice(self, x):
        return x < self.edge - 1 if self.side < 0 else x > self.edge + 1

    def water_x(self, f):
        if self.side < 0:
            return self.edge + 3 + (self.w - self.edge - 6) * f
        return 3 + (self.edge - 6) * f

    def to_swim(self, p, f=None):
        rng = self.rng
        p.state = "swim"
        x = self.water_x(rng.random() if f is None else f)
        y = rng.uniform(self.water + 3, self.h - 2)
        p.x, p.y = x, y
        p.mover = Mover(rng, x, y, speed=16 * self.u ** 0.5, depth=1.0)
        p.timer = rng.uniform(6, 14)

    # ------------------------------------------------------------------ interaction
    def on_click(self, x, y):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        rng = self.rng
        if self.on_ice(x) and y < self.water:
            land = (x, self.ice_top + self.band * 0.6, "ice")
        else:
            land = (x if not self.on_ice(x) else self.edge - self.side * 4, max(y, self.water + 1), "water")
        f = {"x": x, "y": y - 6, "tx": land[0], "ty": land[1], "kind": land[2], "t": 0.0, "state": "air"}
        self.fish.append(f)
        if len(self.fish) > 6:
            self.fish.pop(0)
        # the nearest penguins go for it
        if land[2] == "ice":
            cands = [p for p in self.penguins if p.state in ("stand", "waddle", "flap", "slide")]
        else:
            cands = [p for p in self.penguins if p.state == "swim"]
            if not cands:
                cands = [p for p in self.penguins if p.state in ("stand", "waddle", "flap")]
        cands.sort(key=lambda p: abs(p.x - land[0]) + abs(p.y - land[1]) * 2)
        for p in cands[:rng.randint(2, 3)]:
            p.fish = f
            if p.state != "swim":
                if land[2] == "water":
                    p.state, p.target = "waddle", self.edge + self.side * 2
                elif abs(p.x - land[0]) > 18 * self.u and rng.random() < 0.6:
                    self.start_slide(p, land[0])
                else:
                    p.state, p.target = "waddle", land[0]

    def start_slide(self, p, target):
        p.state = "slide"
        p.target = target
        p.facing = 1 if target > p.x else -1
        p.vx = p.facing * self.rng.uniform(10, 14) * self.u ** 0.5

    # ------------------------------------------------------------------ move
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.2)
        rng = self.rng
        w, h = self.w, self.h
        for p in self.penguins:
            self.move_penguin(p, dt)
        # fish fly in, then lie on the ice or sink
        for f in self.fish:
            f["t"] += dt
            if f["state"] == "air":
                k = min(1.0, f["t"] / 0.6)
                f["x"] = f["x"] + (f["tx"] - f["x"]) * min(1.0, dt * 6)
                f["y"] = f["ty"] - 6 * (1 - k) * (1 - k)   # drops onto the spot
                if k >= 1:
                    f["state"] = "lying" if f["kind"] == "ice" else "sinking"
                    if f["kind"] == "water":
                        self.splash(f["x"], self.water)
            elif f["state"] == "sinking":
                f["y"] = min(h - 2, f["y"] + dt * 1.5)
                f["x"] += math.sin(self.t * 3 + f["t"]) * dt
            if f["t"] > 30:
                f["state"] = "gone"
        self.fish = [f for f in self.fish if f["state"] != "gone"]
        for b in self.bubbles:
            b[1] -= dt * (3 + b[2] * 3)
            b[0] += math.sin(self.t * 4 + b[2] * 9) * dt
        self.bubbles = [b for b in self.bubbles if b[1] > self.water + 0.5]
        for s in self.splashes:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 18 * dt
            s[4] -= dt
        self.splashes = [s for s in self.splashes if s[4] > 0 and s[1] < self.water + 0.5]
        if self.opt("snow"):
            for fl in self.flakes:
                fl[1] += dt * (1.5 + fl[2] * 2.5)
                fl[0] += dt * (math.sin(self.t * 0.7 + fl[2] * 20) * 1.2 + 0.8)
                if fl[1] > h or fl[0] > w:
                    fl[0], fl[1] = rng.uniform(-5, w), rng.uniform(-3, 0)

    def splash(self, x, y):
        rng = self.rng
        for _ in range(8):
            self.splashes.append([x, y, rng.uniform(-6, 6), rng.uniform(-10, -4), rng.uniform(0.4, 0.9)])

    def move_penguin(self, p, dt):
        rng = self.rng
        st = p.state
        p.happy = max(0.0, p.happy - dt)
        if p.fish is not None and p.fish not in self.fish:
            p.fish = None
        if st in ("stand", "waddle", "flap", "slide", "eat"):
            p.y = p.foot - p.L * 0.5 / ASPECT if st != "slide" else p.foot - p.L * 0.17 / ASPECT
        if st == "stand":
            p.timer -= dt
            if p.timer <= 0:
                r = rng.random()
                if r < 0.35:
                    p.state, p.target = "waddle", self.ice_x(rng.random())
                elif r < 0.5:
                    self.start_slide(p, self.ice_x(rng.random()))
                elif r < 0.65:
                    p.state, p.timer = "flap", rng.uniform(1.0, 2.0)
                elif r < 0.82:
                    p.state, p.target = "waddle", self.edge + self.side * 2   # off for a swim
                    p.dive = True
                else:
                    p.facing *= -1    # look around
                    p.timer = rng.uniform(1.5, 4.5)
        elif st == "flap":
            p.flap += dt * 14
            p.timer -= dt
            if p.timer <= 0:
                p.state, p.timer, p.flap = "stand", rng.uniform(1.0, 4.0), 0.0
        elif st == "eat":
            p.timer -= dt
            p.flap += dt * 10
            if p.timer <= 0:
                p.state, p.timer, p.flap = "stand", rng.uniform(1.0, 3.0), 0.0
        elif st == "waddle":
            target = p.fish["x"] if p.fish is not None and p.fish["kind"] == "ice" and p.fish["state"] == "lying" else p.target
            d = target - p.x
            p.facing = 1 if d > 0 else -1
            speed = (2.4 + p.L * 0.08) * (1.6 if p.fish is not None else 1.0)
            p.phase += dt * speed * 2.2
            p.x += p.facing * speed * dt
            if not self.on_ice(p.x):   # reached the edge
                p.x = self.edge + self.side * 1.2
                if getattr(p, "dive", False) or (p.fish is not None and p.fish["kind"] == "water"):
                    self.start_hop(p)
                    return
                p.state, p.timer = "stand", rng.uniform(1, 3)
            elif abs(d) < 0.6:
                p.state, p.timer = "stand", rng.uniform(1.0, 5.0)
            self.try_eat(p)
        elif st == "slide":
            p.x += p.vx * dt
            p.vx *= 1 - dt * 0.5
            p.phase += dt * 3
            if rng.random() < dt * 8:
                self.splashes.append([p.x - p.facing * p.L * 0.4, p.foot - 0.3, -p.facing * rng.uniform(1, 4),
                                      rng.uniform(-3, -1), 0.4])
            done = abs(p.vx) < 2.5 or (p.target - p.x) * p.facing < 0 or not self.on_ice(p.x + p.facing * 2)
            if done:
                if not self.on_ice(p.x + p.facing * 2):
                    p.x = self.edge + self.side * 2.5
                p.state, p.timer = "stand", rng.uniform(0.8, 3.0)
                p.vx = 0.0
            self.try_eat(p)
        elif st in ("hop", "leap"):
            p.vy += 24 * dt
            p.x += p.vx * dt
            p.y += p.vy * dt / ASPECT
            p.angle = math.atan2(p.vy, p.vx)
            if st == "hop" and p.y > self.water + 1.5:
                self.splash(p.x, self.water)
                self.to_swim_here(p)
            elif st == "leap" and p.vy > 0 and p.y + p.L * 0.5 / ASPECT >= p.foot and self.on_ice(p.x):
                p.y = p.foot - p.L * 0.5 / ASPECT
                p.state, p.timer = "stand", rng.uniform(1.0, 3.0)
                p.facing = -self.side
            elif st == "leap" and p.y > self.water + 1.5 and not self.on_ice(p.x):
                self.splash(p.x, self.water)
                self.to_swim_here(p)
        elif st == "swim":
            m = p.mover
            target = None
            if p.fish is not None and p.fish["state"] == "sinking":
                target = (p.fish["x"], p.fish["y"])
            elif p.timer <= 0:
                target = (self.edge - self.side * 3, self.water + 2.5)   # head for the ice edge
            p.timer -= dt
            m.update(dt, self.t, (self.w, self.h), target=target, margin=0)
            # keep under water and off the ice
            lo, hi = self.water + 1.5, self.h - 1.5
            if m.y < lo:
                m.y = lo
                m.heading = abs(m.heading) * 0.6
            if m.y > hi:
                m.y = hi
                m.heading = -abs(m.heading) * 0.6
            if self.side < 0 and m.x < self.edge + 2:
                m.x, m.heading = self.edge + 2, rng.uniform(-0.5, 0.5)
            if self.side > 0 and m.x > self.edge - 2:
                m.x, m.heading = self.edge - 2, math.pi + rng.uniform(-0.5, 0.5)
            m.x = clamp(m.x, 1, self.w - 2)
            p.x, p.y = m.x, m.y
            p.angle = m.heading
            p.facing = 1 if math.cos(m.heading) >= 0 else -1
            p.phase += dt * 10
            if rng.random() < dt * 3:
                self.bubbles.append([p.x - math.cos(m.heading) * p.L * 0.4, p.y, rng.random()])
            if p.fish is not None and p.fish["state"] == "sinking" and m.near(p.fish["x"], p.fish["y"], p.L * 0.45):
                self.eat(p)
            if target is not None and p.fish is None and m.near(target[0], target[1], 3.0):
                # leap out onto the ice
                p.state = "leap"
                p.vx = self.side * rng.uniform(5, 9) * self.u ** 0.5
                p.vy = -rng.uniform(16, 20)
                p.foot = self.ice_top + rng.uniform(0.3, 1.0) * self.band
                p.x = self.edge - self.side * 1.5
                self.splash(p.x, self.water)

    def start_hop(self, p):
        p.state = "hop"
        p.dive = False
        p.vx = -self.side * self.rng.uniform(4, 7)
        p.vy = -self.rng.uniform(9, 13)
        p.facing = -self.side

    def to_swim_here(self, p):
        p.state = "swim"
        p.mover = Mover(self.rng, p.x, max(p.y, self.water + 2), speed=16 * self.u ** 0.5, depth=1.0)
        p.mover.heading = math.atan2(1.0, -self.side * 1.0)
        p.timer = self.rng.uniform(6, 14)

    def try_eat(self, p):
        f = p.fish
        if f is not None and f["state"] == "lying" and abs(f["x"] - p.x) < p.L * 0.3 + 0.6:
            self.eat(p)

    def eat(self, p):
        f = p.fish
        if f in self.fish:
            self.fish.remove(f)
        for q in self.penguins:
            if q.fish is f:
                q.fish = None
        p.happy = 2.5
        if p.state == "swim":
            p.timer = min(p.timer, 2.0)
        else:
            p.state, p.timer = "eat", 1.6

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
        w = self.w
        # animated water surface and light shafts
        wy = self.water
        x0, x1 = (int(self.edge), w) if self.side < 0 else (0, int(self.edge) + 1)
        for x in range(x0, x1):
            y = wy + math.sin(x * 0.35 + t * 1.6) * 0.3 + math.sin(x * 0.11 - t * 0.9) * 0.25
            cv.put(x, y, "~" if (x + int(t * 3)) % 3 else "-", (170, 215, 240), level=0.5)
            g = math.sin(x * 0.21 + t * 0.4) * math.sin(x * 0.05 - t * 0.23)
            if g > 0.6:
                for yy in range(int(wy) + 1, min(self.h, int(wy) + 1 + int((g - 0.5) * 30))):
                    cv.shade(x + (yy - wy) * 0.15, yy, 0.13 * (1 - (yy - wy) / 16), (120, 190, 230))
        # penguins: in the water first, then on the ice from back to front
        swimmers = [p for p in self.penguins if p.state == "swim"]
        others = sorted((p for p in self.penguins if p.state != "swim"), key=lambda p: p.foot)
        for p in swimmers:
            self.draw_penguin(cv, p)
        for b in self.bubbles:
            cv.put(b[0], b[1], "o" if b[2] > 0.6 else "°", (190, 225, 255), level=0.4)
        for f in self.fish:
            self.draw_fish(cv, f)
        for p in others:
            self.draw_penguin(cv, p)
        for s in self.splashes:
            cv.put(s[0], s[1], "'" if s[3] < 0 else ".", (220, 240, 255), level=0.5)
        if self.opt("snow"):
            for x, y, z in self.flakes:
                cv.put(x, y, "*" if z > 0.8 else "·" if z > 0.5 else ".", scale((235, 240, 255), 0.5 + 0.5 * z),
                       level=0.3)

    def draw_fish(self, cv, f):
        x, y = f["x"], f["y"]
        wig = int(self.t * 6) % 2
        face = 1 if int(f["t"] * 2) % 2 == 0 or f["state"] != "sinking" else -1
        col = (170, 200, 220)
        s = "><>" if face > 0 else "<><"
        if f["state"] == "lying":
            s = ">=<" if wig else "><="
        cv.text(x - 1, y, s, col)
        cv.put(x + (1 if face > 0 else -1), y, "°" if wig else "o", (230, 240, 250))

    def draw_penguin(self, cv, p):
        st = p.state
        f = p.facing
        flap = 0
        if st in ("swim", "hop", "leap"):
            q = int(round((p.angle % math.tau) / math.tau * 16)) % 16
            pose = ("swim", q, int(p.phase) % 2)
        elif st == "slide":
            pose = ("slide", f, 0)
        else:
            rock = 0
            if st == "waddle":
                rock = int(round(math.sin(p.phase) * 2))
            if st in ("flap", "eat"):
                flap = 1 + int(p.flap) % 2
            pose = ("stand", f, rock, flap, st == "eat" and int(p.flap) % 2 == 0)
        key = (cv.ramp, p.id, pose)
        cells = self.cache.get(key)
        if cells is None:
            sz = int(p.L * 1.5) + 8
            cells = bake(lambda c, x, y: self.paint(c, x, y, p, pose), sz, sz // 2 + 6, cv.ramp)
            if len(self.cache) > 1500:
                self.cache.clear()
            self.cache[key] = cells
        bob = 0.0
        if st == "waddle":
            bob = -abs(math.sin(p.phase)) * 0.4
        blit(cv, cells, p.x, p.y + bob)

    def paint(self, cv, cx, cy, p, pose):
        sp = SPECIES[p.kind]
        L = p.L
        kind = pose[0]
        if kind == "swim":
            ang = pose[1] / 16 * math.tau
            f = 1 if math.cos(ang) >= 0 else -1
            flap_a = 0.5 if pose[2] else -0.2
            feet_tuck = True
        elif kind == "slide":
            f = pose[1]
            ang = 0.0 if f > 0 else math.pi
            ang += f * 0.08
            flap_a = 0.9
            feet_tuck = True
        else:
            f = pose[1]
            rock = pose[2] * 0.12
            ang = -math.pi / 2 + rock
            flap_a = (0.0, 0.9, 1.5)[pose[3]]
            feet_tuck = False
        ax, ay = math.cos(ang), math.sin(ang)
        nx, ny = (-ay, ax) if f > 0 else (ay, -ax)     # "front": belly side

        def P(s, q):   # body-local (along, front) in stretched units -> cell coords
            return cx + ax * s * L + nx * q * L, cy + (ay * s * L + ny * q * L) / ASPECT

        back, beak, feet = sp["back"], sp["beak"], sp["feet"]
        b = Body(blend=0.35)
        # 0 body: a pear, wide at the bottom, narrowing to the neck
        b.capsule(*P(-0.2, 0.0), *P(0.12, 0.02), L * 0.25, L * 0.16, color=back)
        b.circle(*P(0.33, 0.04), L * 0.13, color=back)                            # 1 head
        bx0, by0 = P(0.33, 0.14)
        bx1, by1 = P(0.3, 0.28 if p.kind != "emperor" else 0.3)
        b.capsule(bx0, by0, bx1, by1, L * 0.045, L * 0.015, color=beak)            # 2 beak
        # flipper: from the shoulder, swinging out with the flap angle
        sx_, sy_ = P(0.14, -0.04)
        fa = math.pi + flap_a                                                    # along -axis, rotated out
        ca, sa = math.cos(fa), math.sin(fa)
        tip_s, tip_q = ca * 0.34, -abs(sa) * 0.34 - 0.06
        tx, ty = P(0.14 + tip_s, tip_q)
        b.capsule(sx_, sy_, tx, ty, L * 0.065, L * 0.03, color=scale(back, 0.85))  # 3 flipper
        if feet_tuck:
            fx0, fy0 = P(-0.42, 0.02)
            fx1, fy1 = P(-0.5, 0.06)
        else:
            fx0, fy0 = P(-0.43, 0.04)
            fx1, fy1 = P(-0.45, 0.16)
        b.capsule(fx0, fy0, fx1, fy1, L * 0.05, L * 0.04, color=feet)             # 4 feet
        tx0, ty0 = P(-0.38, -0.16)
        b.capsule(*P(-0.33, -0.12), tx0, ty0, L * 0.04, L * 0.015, color=back)    # 5 tail
        # the eye
        ex, ey = P(0.36, 0.08)
        eye_col = (255, 60, 50) if p.kind == "rockhopper" else WHITE
        b.spot(ex, ey, 0.2, eye_col, "o" if L > 9 else ".")
        if p.kind == "gentoo":
            gx, gy = P(0.41, 0.0)
            b.spot(gx, gy, L * 0.05, WHITE)     # the white cap stripe
        cxs, cys = cx, cy * ASPECT
        belly_from = -0.02 if p.kind != "littleblue" else 0.0
        emperor = p.kind == "emperor"
        ear = P(0.27, -0.02)

        def pattern(px, py, i, inside):
            # which side of the body axis is this cell on? front side = white belly
            dx, dy = px - cxs, py * ASPECT - cys
            q = (dx * nx + dy * ny) / L
            s = (dx * ax + dy * ay) / L
            if i == 0 and q > belly_from - 0.05 * s:
                return WHITE if s < 0.2 else mix(WHITE, (250, 220, 120), 0.6) if emperor else WHITE
            if i == 1 and emperor and math.hypot(px - ear[0], (py - ear[1]) * ASPECT) < L * 0.09:
                return (255, 190, 60)
            if i == 1 and p.kind == "littleblue" and q > 0.06 and s < 0.33:
                return WHITE
            return None
        b.draw(cv, depth=1.0, pattern=pattern, edge=0.8, ambient=0.6)
        if p.kind == "rockhopper":
            # the spiky yellow crest over the eye, swept back
            for k in range(3):
                x, y = P(0.4 - k * 0.04, 0.08 - k * 0.11)
                cv.put(x, y, "~" if k else "=", (255, 225, 70), level=0.9)
            x, y = P(0.47, -0.12)
            cv.put(x, y, "\\" if f > 0 else "/", (255, 230, 90), level=0.9)
        if len(pose) > 4 and pose[4]:   # eating: beak up, a fish tail sticks out
            x, y = P(0.33, 0.36)
            cv.put(x, y, "<" if f > 0 else ">", (170, 200, 220), level=0.9)

    # ------------------------------------------------------------------ background
    def bake_background(self, ramp):
        w, h = self.w, self.h
        rng = random.Random(self.bg_seed)
        cv = Canvas(w, h, ramp)
        hz = self.horizon
        sky = self.sky
        if sky == "night":
            for _ in range(int(w * hz / 25)):
                cv.put(rng.uniform(0, w), rng.uniform(0, hz - 1), rng.choice("..·*+"),
                       scale((220, 230, 255), rng.uniform(0.4, 1.0)), level=0.2)
            # an aurora curtain: bright lower hem, rays fading upward
            base = rng.uniform(0.45, 0.65) * hz
            hue = rng.choice([0.36, 0.42, 0.8])
            for x in range(w):
                hem = base + math.sin(x * 0.045 + self.bump) * hz * 0.15 + noise1(x * 0.08, 7) * 2
                ray = clamp(0.4 + 0.6 * noise1(x * 0.35, 9))
                height = hz * (0.25 + 0.3 * ray)
                for k in range(int(height)):
                    y = hem - k
                    v = (0.62 if k == 0 else 0.45) * (1 - k / height) ** 0.7 * (0.35 + 0.65 * ray)
                    if 0 <= y < hz:
                        cv.shade(x, y, v, hsv(hue + k / max(1, height) * 0.25, 0.7, 1.0))
        else:
            top = (40, 70, 120) if sky == "day" else (60, 40, 90)
            low = (150, 200, 235) if sky == "day" else (255, 150, 120)
            for y in range(int(hz)):
                f = y / max(1, hz)
                for x in range(w):
                    if cellhash(x, y, 11) > 0.62 - f * 0.5:
                        cv.shade(x, y, 0.08 + 0.18 * f, mix(top, low, f))
            # a low sun
            sx = w * rng.uniform(0.2, 0.8)
            sun = Body()
            sun.circle(sx, hz - 1.5, max(1.5, 2.5 * self.u), color=(255, 240, 200) if sky == "day" else (255, 170, 100))
            sun.draw(cv, light=(0, 0), glow=1.0, ambient=1.0)
        # far tabular icebergs on the horizon
        for _ in range(rng.randint(2, 4)):
            x = rng.uniform(0, w)
            bw = rng.uniform(4, 12) * self.u
            bh = rng.uniform(1, 2.5) * self.u
            for yy in range(int(hz - bh), int(hz) + 1):
                for xx in range(int(x - bw / 2), int(x + bw / 2) + 1):
                    cv.put(xx, yy, "_" if yy == int(hz - bh) else "#", (170, 190, 210) if yy > hz - bh else (220, 235, 245),
                           level=0.3)
        # the open sea between the horizon and the shore
        for y in range(int(hz) + 1, int(self.water) + 1):
            for x in range(w):
                if cellhash(x, y, 21) > 0.6:
                    cv.put(x, y, "~" if (x + y) % 3 else "-", scale((90, 140, 190), 0.4 + 0.3 * (y - hz) / max(1, self.water - hz)),
                           level=0.15)
        # under water: deepening blue, the seen-through cross-section
        wy = self.water
        for y in range(int(wy) + 1, h):
            f = (y - wy) / max(1, h - wy)
            for x in range(w):
                n = cellhash(x, y, 31)
                if n > 0.55 - f * 0.25:
                    cv.shade(x, y, 0.1 + 0.08 * (1 - f), gradient([(70, 150, 210), (30, 70, 140), (15, 30, 80)], f))
        # the ice shelf: a bright top, a cliff face, and its pale underwater foot
        e = self.edge
        top = self.ice_top
        for x in range(w):
            if not self.on_ice(x + 0.5):
                continue
            dist = abs(x + 0.5 - e)
            bump = noise1(x * 0.15 + self.bump) * 0.6
            ytop = top + bump * 0.5 - (0 if dist > 3 else (3 - dist) * -0.3)
            for y in range(int(ytop), h):
                if y < top + self.band + 0.5:
                    # walkable snow: bright, a few sparkles
                    k = (y - ytop) / max(1, self.band)
                    c = mix((245, 250, 255), (200, 220, 240), k)
                    n = cellhash(x, y, 47)
                    ch = "_" if y == int(ytop) else ("·" if n > 0.7 else "." if n > 0.15 else " ")
                    if ch != " ":
                        cv.put(x, y, ch, scale(c, 1.0 if ch == "_" else 0.55), level=0.3)
                elif y < wy + 0.5:
                    # the cliff above the water: pale blue, a few cracks
                    n = noise1(x * 0.4 + y * 3.1, 41)
                    ch = "|" if n > 0.6 else ":" if n > 0.1 else "."
                    cv.put(x, y, ch, mix((150, 190, 225), (225, 238, 250), n * 0.5 + 0.5), level=0.3)
                else:
                    # the foot of the ice under water, seen through the water: faint
                    f = (y - wy) / max(1, h - wy)
                    slope = f * 6 * self.u
                    if dist > slope:     # the underwater wall slopes outward a little
                        n = cellhash(x, y, 43)
                        rim = dist < slope + 1.5
                        if n > -0.1 or rim:
                            c = gradient([(120, 180, 225), (60, 110, 180), (35, 60, 120)], f)
                            ch = ("/" if self.side > 0 else BS) if rim else "." if n < 0.5 else ":"
                            cv.put(x, y, ch, scale(c, 0.8), level=0.2)
        # a floating iceberg: a little above water, a lot below
        if self.berg is not None:
            bx, br, bs = self.berg
            for y in range(int(wy - br * 0.45), min(h, int(wy + br * 1.6))):
                for x in range(int(bx - br * 2.2), int(bx + br * 2.2) + 1):
                    yy = y - wy
                    if yy < 0:
                        half = br * (0.9 + yy / (br * 0.5)) * 1.3 + noise1(y * 0.9 + bs) * 0.8
                    else:
                        half = br * 1.6 * (1 - (yy / (br * 1.6)) ** 2) ** 0.5 + noise1(y * 0.7 + bs) * 0.8
                    if abs(x + 0.5 - bx) < half:
                        if yy < 0:
                            lit = clamp(0.6 + 0.4 * (bx - x) / max(1, half))
                            cv.put(x, y, "#" if lit > 0.6 else "%", mix((180, 205, 230), (250, 252, 255), lit), level=0.5)
                        else:
                            cv.shade(x, y, 0.3 - 0.1 * yy / (br * 1.6), (140, 200, 235), "over")
        return cv
