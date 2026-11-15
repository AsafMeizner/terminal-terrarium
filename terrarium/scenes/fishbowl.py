"""A goldfish bowl you can feed. Also the worked example in docs/ANIMALS.md.

How it works, the way the "make your own ASCII animals" reels explain it:
  1. The screen is a grid of cells. Each frame we MOVE every fish, then DRAW it.
  2. Move: each fish wanders in lazy S-curves (shapes.Mover) and swims toward food if there is any.
  3. Draw: each fish is a few round parts (shapes.Body). Cells deep inside get dense characters,
     edge cells get light ones, and a light direction shades the body so it looks round.
  4. Depth: smaller fish are "farther away", so they swim slower and fade into the dark.
"""
import math

from ..engine import ASPECT, Scene, clamp, hsv, mix
from ..shapes import Body, Mover

GOLD = [(255, 150, 40), (255, 120, 50), (255, 190, 80), (250, 240, 230), (255, 90, 60)]


class Fish:
    def __init__(self, rng, x, y, depth):
        self.mover = Mover(rng, x, y, speed=5.0, depth=depth)
        self.depth = depth
        self.size = 3.2 + 3.2 * depth * rng.uniform(0.85, 1.15)   # near fish are bigger
        # a little genome: colors, fin length, a calico pattern for some
        self.color = rng.choice(GOLD)
        self.fin = rng.uniform(0.9, 1.6)
        self.calico = rng.random() < 0.3
        self.seed = rng.random() * 100
        self.flap = rng.uniform(0, math.tau)
        self.full = 0.0   # seconds of "just ate" happiness


class Fishbowl(Scene):
    name = "fishbowl"
    title = "Fishbowl"
    blurb = "goldfish drifting in a glass bowl; feed them and they come to eat"
    tags = ("water", "creatures", "calm", "cozy")
    interactions = "click to drop food, point at a fish to startle it"
    options = {
        "fish": (0, "how many goldfish (0 = based on size)"),
        "bowl": (True, "draw the glass bowl"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        # the bowl: an ellipse filling most of the screen (wider than tall, in real pixels)
        self.cx, self.cy = w / 2, h * 0.52
        self.rx = min(w * 0.46, h * 0.48 * ASPECT)
        self.ry = self.rx / ASPECT * 0.92
        self.water_top = self.cy - self.ry * 0.72
        n = self.opt("fish") or max(3, int(round((3 + w * h / 1600) * self.density)))
        self.fish = []
        for k in range(n):
            depth = (k + rng.random()) / n
            x, y = self.random_point(0.6)
            self.fish.append(Fish(rng, x, y, depth))
        self.fish.sort(key=lambda f: f.depth)  # far fish first, near fish drawn on top
        self.food = []      # [x, y, vy]
        self.bubbles = []
        # pebbles and a plant: rolled once per run
        self.pebbles = [(self.cx + rng.uniform(-0.8, 0.8) * self.rx * 0.8,
                         rng.uniform(0.0, 1.0), hsv(rng.choice([0.05, 0.08, 0.55, 0.9]), 0.35, 0.8))
                        for _ in range(int(self.rx * 1.6))]
        self.plant_x = self.cx + rng.choice([-1, 1]) * self.rx * rng.uniform(0.35, 0.55)
        self.plant_leaves = rng.randint(4, 7)

    def random_point(self, k=0.7):
        a = self.rng.uniform(0, math.tau)
        r = math.sqrt(self.rng.random()) * k
        return self.cx + math.cos(a) * self.rx * r, self.cy + abs(math.sin(a)) * self.ry * r * 0.6

    def inside(self, x, y, margin=0.0):
        return ((x - self.cx) / (self.rx - margin)) ** 2 + ((y - self.cy) / (self.ry - margin / ASPECT)) ** 2 < 1 \
            and y > self.water_top

    def on_click(self, x, y):
        if not self.inside(x, y):
            x, y = self.cx + (x - self.cx) * 0.5, self.water_top + 0.5
        for _ in range(self.rng.randint(3, 5)):
            self.food.append([x + self.rng.uniform(-1.5, 1.5), max(y, self.water_top + 0.3), 0.0])

    # ------------------------------------------------------------------ move
    def update(self, dt):
        super().update(dt)
        rng = self.rng
        floor = self.cy + self.ry * 0.62
        for f in self.food:
            f[2] = min(1.2, f[2] + dt * 0.8)          # flakes sink slowly...
            f[1] = min(floor, f[1] + f[2] * dt)
            f[0] += math.sin(self.t * 2 + f[1]) * dt * 0.4
        for fish in self.fish:
            target = None
            if self.food:
                m = fish.mover
                target = min(self.food, key=lambda p: (p[0] - m.x) ** 2 + ((p[1] - m.y) * ASPECT) ** 2)
            threat = self.pointer if self.pointer and fish.mover.near(*self.pointer, fish.size * 2.5) else None
            fish.mover.update(dt, self.t, (self.w, self.h), target=target, threat=threat, margin=0)
            # fish swim mostly level: keep the heading within ~45 degrees of horizontal
            m = fish.mover
            facing_right = math.cos(m.heading) >= 0
            base = 0.0 if facing_right else math.pi
            diff = (m.heading - base + math.pi) % math.tau - math.pi
            m.heading = base + max(-0.8, min(0.8, diff))
            # stay inside the bowl: steer back toward the middle
            if not self.inside(m.x, m.y, margin=fish.size * 1.2):
                want = math.atan2((self.cy - m.y) * ASPECT, self.cx - m.x)
                diff = (want - m.heading + math.pi) % math.tau - math.pi
                m.heading += diff * min(1.0, dt * 4)
            # and a hard wall: the glass is the glass
            mx_, my_ = fish.size * 1.0, fish.size * 0.5 / ASPECT
            k = math.hypot((m.x - self.cx) / (self.rx - mx_), (m.y - self.cy) / (self.ry - my_))
            if k > 1:
                m.x = self.cx + (m.x - self.cx) / k
                m.y = self.cy + (m.y - self.cy) / k
            m.y = max(m.y, self.water_top + 1.0 + my_)
            # eat!
            if target is not None and m.near(target[0], target[1], fish.size * 0.9):
                self.food.remove(target)
                fish.full = 2.5
                self.bubbles.append([m.x, m.y - 0.5, rng.uniform(0.3, 0.7)])
            fish.full = max(0.0, fish.full - dt)
            fish.flap += dt * (6 + 10 * (threat is not None) + 4 * (target is not None))
        if rng.random() < dt * 1.5:
            self.bubbles.append([self.plant_x + rng.uniform(-1, 1), floor, rng.uniform(0.2, 0.6)])
        for b in self.bubbles:
            b[1] -= dt * (2.0 + b[2] * 2)
            b[0] += math.sin(self.t * 3 + b[2] * 10) * dt * 0.6
        self.bubbles = [b for b in self.bubbles if b[1] > self.water_top]

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        cx, cy, rx, ry = self.cx, self.cy, self.rx, self.ry
        floor = cy + ry * 0.62
        # water: a faint blue tint that gets deeper toward the bottom
        for y in range(max(0, int(self.water_top)), min(cv.h, int(cy + ry) + 1)):
            depth = (y - self.water_top) / (ry * 1.7)
            for x in range(max(0, int(cx - rx)), min(cv.w, int(cx + rx) + 1)):
                if self.inside(x + 0.5, y + 0.5):
                    # sparse caustic glints instead of a full field of dots
                    shimmer = math.sin(x * 0.35 + y * 0.8 + self.t * 1.3) * math.sin(x * 0.13 - y * 0.5 + self.t * 0.7)
                    if shimmer > 0.55:
                        cv.shade(x, y, 0.12 * (1 - depth * 0.6), (90, 170, 220))
        # water surface line
        for x in range(int(cx - rx), int(cx + rx) + 1):
            if self.inside(x + 0.5, self.water_top + 0.6):
                y = self.water_top + 0.15 * math.sin(x * 0.5 + self.t * 2)
                cv.shade(x, y, 0.35, (150, 210, 240))
        # pebbles on the bottom
        for px, k, col in self.pebbles:
            py = floor + k * (cy + ry * 0.9 - floor)
            if self.inside(px, py):
                cv.shade(px, py, 0.55, col)
        # a swaying plant
        for leaf in range(self.plant_leaves):
            side = -1 if leaf % 2 else 1
            length = 4 + leaf * 1.3
            for s in range(int(length * 2)):
                f = s / (length * 2)
                sway = math.sin(self.t * 0.9 + leaf + f * 2) * f * 1.6
                x = self.plant_x + side * leaf * 0.35 + sway
                y = floor - f * length
                cv.shade(x, y, 0.5 * (1 - f * 0.4), mix((40, 120, 60), (110, 200, 90), f))
        # food flakes and bubbles
        for x, y, _ in self.food:
            cv.put(x, y, "*", (240, 200, 120))
        for x, y, r in self.bubbles:
            cv.put(x, y, "o" if r > 0.45 else "°", (180, 220, 255))
        # the fish (far ones first)
        for fish in self.fish:
            self.draw_fish(cv, fish)
        # the glass: a bright rim with a highlight on the upper left
        if self.opt("bowl"):
            steps = int((rx + ry * ASPECT) * 4)
            for i in range(steps):
                a = i / steps * math.tau
                x = cx + math.cos(a) * rx
                y = cy + math.sin(a) * ry
                if y < cy - ry * 0.86:   # open neck at the top
                    continue
                hi = clamp(math.cos(a + 2.3)) ** 3
                cv.shade(x, y, 0.35 + 0.5 * hi, mix((120, 160, 180), (240, 250, 255), hi))
            for x in range(int(cx - rx * 0.5), int(cx + rx * 0.5) + 1):   # the rim of the neck
                cv.shade(x, cy - ry * 0.86, 0.5, (170, 200, 215))

    def draw_fish(self, cv, fish):
        m = fish.mover
        a = m.heading
        ca, sa = math.cos(a), math.sin(a) / ASPECT
        s = fish.size
        hx, hy = m.x, m.y
        tx, ty = hx - ca * s * 1.9, hy - sa * s * 1.9           # where the tail starts
        wag = math.sin(fish.flap) * 0.6
        # tail fins fan out behind, wagging
        fa = a + math.pi + wag
        b = Body(blend=0.5)
        b.capsule(hx, hy, tx, ty, s * 0.62, s * 0.3, color=fish.color)   # body, fat at the head
        for spread in (-0.55, 0.55):
            ang = fa + spread
            b.capsule(tx, ty, tx + math.cos(ang) * s * fish.fin, ty + math.sin(ang) * s * fish.fin / ASPECT,
                      s * 0.24, s * 0.05, color=mix(fish.color, (255, 255, 255), 0.35))
        # a pectoral fin that paddles
        pa = a + math.pi / 2 + 0.5 + math.sin(fish.flap * 1.3) * 0.4
        fx, fy = hx - ca * s * 0.6, hy - sa * s * 0.6
        b.capsule(fx, fy, fx + math.cos(pa) * s * 0.7, fy + math.sin(pa) * s * 0.7 / ASPECT,
                  s * 0.16, s * 0.04, color=mix(fish.color, (255, 255, 255), 0.4))
        # the eye
        ex, ey = hx + ca * s * 0.2 - sa * ASPECT * s * 0.15, hy + sa * s * 0.2 - ca / ASPECT * s * 0.15
        b.spot(ex, ey, 0.3, (20, 20, 30), "o" if s > 3 else ".")
        pattern = None
        if fish.calico:
            seed = fish.seed

            def pattern(x, y, i, inside):
                if i == 0 and math.sin(x * 0.9 + seed) * math.sin(y * 1.7 + seed * 2) > 0.35:
                    return (250, 245, 240)
                return None
        happy = 0.4 if fish.full > 0 else 0.0
        b.draw(cv, depth=fish.depth, glow=happy, pattern=pattern)
