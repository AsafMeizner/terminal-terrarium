"""Template written by `terrarium --new NAME`."""

TEMPLATE = '''"""{title}: describe your scene here."""
import math

from terrarium.engine import ASPECT, Scene, clamp, gradient, hsv, mix, noise2


class {cls}(Scene):
    name = "{name}"
    title = "{title}"
    blurb = "one line describing {name}"
    tags = ("custom",)
    options = {{
        "count": (0, "how many things (0 = based on screen size)"),
        "palette": ("random", "random, warm or cool"),
    }}

    def setup(self):
        """Build state. Runs at start, on resize and when density changes.
        Roll the *structure* from self.rng so every run looks different."""
        rng = self.rng
        palette = self.opt("palette")
        if palette == "random":
            palette = rng.choice(["warm", "cool"])
        base = rng.uniform(0.0, 0.15) if palette == "warm" else rng.uniform(0.5, 0.7)
        n = self.opt("count") or self.count(25)
        self.things = []
        for _ in range(n):
            self.things.append({{
                "x": rng.uniform(0, self.w),
                "y": rng.uniform(0, self.h),
                "r": rng.uniform(1.5, 4.0),           # a little "genome" per object
                "speed": rng.uniform(0.3, 1.2),
                "color": hsv(base + rng.uniform(-0.06, 0.06), 0.6, 1.0),
                "phase": rng.uniform(0, math.tau),
            }})

    def update(self, dt):
        super().update(dt)                             # advances self.t (dt includes --speed)
        for p in self.things:
            p["y"] -= p["speed"] * dt
            if p["y"] < -p["r"]:
                p["y"] = self.h + p["r"]
                p["x"] = self.rng.uniform(0, self.w)

    def draw(self, cv):
        # faint background gradient
        for y in range(0, self.h, 2):
            for x in range(0, self.w, 3):
                v = 0.06 + 0.06 * noise2(x * 0.05, y * 0.1 + self.t * 0.1)
                cv.shade(x, y, v, gradient([(20, 30, 60), (60, 40, 90)], y / self.h))
        # glowing round blobs (ASPECT keeps them round)
        for p in self.things:
            pulse = 0.8 + 0.2 * math.sin(self.t * 2 + p["phase"])
            r = p["r"] * pulse
            for y in range(int(p["y"] - r / ASPECT) - 1, int(p["y"] + r / ASPECT) + 2):
                for x in range(int(p["x"] - r) - 1, int(p["x"] + r) + 2):
                    d = math.hypot(x - p["x"], (y - p["y"]) * ASPECT) / r
                    if d < 1.3:
                        cv.shade(x, y, clamp(1.15 - d), mix(p["color"], (255, 255, 255), clamp(0.6 - d)))
'''


def render(name: str) -> str:
    title = name.replace("_", " ").replace("-", " ").title()
    cls = "".join(part.title() for part in name.replace("-", "_").split("_")) or "MyScene"
    return TEMPLATE.format(name=name, title=title, cls=cls)
