"""Template written by `terrarium --new NAME`. It's the example from docs/ANIMALS.md."""

TEMPLATE = '''"""{title}: a little ASCII animal. Walkthrough: docs/ANIMALS.md in the terrarium repo."""
import math

from terrarium.engine import ASPECT, Scene, hsv
from terrarium.shapes import Body, Mover


class {cls}(Scene):
    name = "{name}"
    title = "{title}"
    blurb = "my own ASCII creatures"
    tags = ("custom", "creatures")
    interactions = "click to drop food"
    options = {{
        "count": (0, "how many creatures (0 = based on screen size)"),
    }}

    # 1. SETUP: make the creatures. Each one rolls its own "genome" so every run is different.
    def setup(self):
        rng = self.rng
        n = self.opt("count") or self.count(6)
        self.critters = []
        for _ in range(n):
            depth = rng.random()                          # 0 = far away, 1 = close
            self.critters.append({{
                "mover": Mover(rng, rng.uniform(0, self.w), rng.uniform(0, self.h), speed=6, depth=depth),
                "size": 2 + 3 * depth,                    # far things look smaller...
                "color": hsv(rng.random(), 0.6, 1.0),
                "depth": depth,
            }})
        self.critters.sort(key=lambda c: c["depth"])     # draw far ones first
        self.food = []

    # 2. INPUT: clicking drops food.
    def on_click(self, x, y):
        self.food.append([x, y])

    # 3. MOVE: every creature follows simple rules: wander, but head for the nearest food.
    def update(self, dt):
        super().update(dt)
        for c in self.critters:
            m = c["mover"]
            target = min(self.food, key=lambda f: (f[0] - m.x) ** 2 + (f[1] - m.y) ** 2) if self.food else None
            m.update(dt, self.t, (self.w, self.h), target=target, threat=self.pointer)
            if target and m.near(target[0], target[1], c["size"]):
                self.food.remove(target)                  # yum

    # 4. DRAW: each creature is a few round parts. Inside cells get dense characters, edges light ones.
    def draw(self, cv):
        for f in self.food:
            cv.put(f[0], f[1], "*", (255, 220, 120))
        for c in self.critters:
            m, s = c["mover"], c["size"]
            dx, dy = math.cos(m.heading), math.sin(m.heading) / ASPECT
            body = Body()
            body.capsule(m.x, m.y, m.x - dx * s * 1.8, m.y - dy * s * 1.8, s * 0.6, s * 0.25, color=c["color"])
            body.circle(m.x - dx * s * 2.0, m.y - dy * s * 2.0, s * 0.35, color=c["color"])   # tail
            body.spot(m.x + dx * s * 0.25, m.y + dy * s * 0.25 - 0.2, 0.3, (20, 20, 30), "o")  # eye
            body.draw(cv, depth=c["depth"])               # far = dimmer
'''


def render(name: str) -> str:
    title = name.replace("_", " ").replace("-", " ").title()
    cls = "".join(part.title() for part in name.replace("-", "_").split("_")) or "MyScene"
    return TEMPLATE.format(name=name, title=title, cls=cls)
