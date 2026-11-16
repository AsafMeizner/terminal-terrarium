"""A night pond: frogs on lily pads croak, hop from pad to pad and zap flies with their tongues.

Each frog is a few round parts (a QuickBody: shapes.Body with a faster draw): a fat body, a head,
two eye bumps with big shiny eyes, folded back legs and little front legs. Its rules are simple:
sit, puff the throat sac to croak, blink, catch any fly that buzzes into reach, and now and then
leap in an arc to another pad. Pads higher up the screen are farther away, so they are smaller and
dimmer, and a frog shrinks as it hops away from you.
"""
import math

from ..engine import ASPECT, Scene, clamp, fbm, hsv, mix, noise1, scale
from .aquarium import QuickBody, hsh

MOON = (235, 235, 210)
WATER = (20, 40, 70)

FROGS = [
    # name, skin, belly, eye, accent (feet/sides), spots
    ("green frog", (95, 170, 70), (220, 225, 160), (230, 190, 60), (80, 140, 60), None),
    ("tree frog", (110, 205, 90), (235, 240, 200), (230, 50, 40), (250, 140, 40), None),     # red-eyed
    ("leopard frog", (120, 175, 90), (230, 230, 200), (220, 200, 90), (100, 150, 70), (40, 70, 35)),
    ("toad", (150, 120, 75), (215, 195, 150), (220, 160, 60), (130, 100, 60), (100, 75, 45)),
    ("bullfrog", (110, 135, 60), (225, 220, 150), (200, 170, 70), (95, 115, 50), (80, 95, 40)),
    ("blue frog", (70, 130, 220), (150, 190, 240), (20, 20, 30), (40, 60, 140), (20, 25, 50)),
]
FLOWERS = [((250, 170, 205), (255, 240, 245)), ((255, 250, 250), (255, 255, 255)), ((240, 120, 170), (255, 210, 230)),
           ((250, 220, 120), (255, 245, 200)), ((200, 160, 250), (240, 225, 255))]


class Pad:
    def __init__(self, x, y, R, depth, rng):
        self.x, self.y, self.R, self.depth = x, y, R, depth
        self.notch = rng.uniform(0, math.tau)
        self.color = hsv(rng.uniform(0.33, 0.45), rng.uniform(0.55, 0.8), rng.uniform(0.4, 0.55))
        self.flower = None
        self.frog = None
        self.bob = rng.uniform(0, 6)
        self.dip = 0.0          # pushed down when a frog lands

    def inside(self, x, y):
        dx = (x - self.x) / self.R
        dy = (y - self.y) * ASPECT / (self.R * 0.38)
        return dx * dx + dy * dy < 1


class Frog:
    def __init__(self, sc, rng, pad):
        self.pad = pad
        pad.frog = self
        self.name, self.skin, self.belly, self.eye, self.accent, self.spots = rng.choice(sc.palettes)
        self.x, self.y = pad.x, pad.y
        self.k = rng.uniform(0.9, 1.1)
        self.state = "sit"
        self.timer = rng.uniform(1, 5)          # until the next croak
        self.hop_timer = rng.uniform(6, 16)
        self.blink = rng.uniform(1, 4)
        self.croak = 0.0
        self.sac = 0.0
        self.tongue = 0.0
        self.target = None
        self.hop = None
        self.cool = rng.uniform(0, 2)
        self.look = 0.0
        self.seed = rng.random() * 40

    def size(self, sc, y=None):
        d = sc.depth_at(self.y if y is None else y)
        return (2.8 + 3.6 * d) * sc.u * self.k

    def mouth(self, sc):
        S = self.size(sc)
        return self.x, self.y - 1.3 * S / ASPECT

    # ------------------------------------------------------------------ move
    def update(self, sc, dt):
        rng = sc.rng
        self.cool = max(0.0, self.cool - dt)
        self.blink -= dt
        if self.blink < -0.15:
            self.blink = rng.uniform(2, 6)
        if self.state == "hop":
            h = self.hop
            h["t"] += dt / h["dur"]
            t = min(1.0, h["t"])
            self.x = h["x0"] + (h["x1"] - h["x0"]) * t
            base = h["y0"] + (h["y1"] - h["y0"]) * t
            self.y = base - h["arc"] * 4 * t * (1 - t)
            if h["t"] >= 1:
                self.x, self.y = h["x1"], h["y1"]
                self.state = "sit"
                self.pad.dip = 1.0
                sc.splash(self.x, self.y, self.size(sc))
                self.hop_timer = rng.uniform(8, 20)
            return
        if self.pad is not None:
            self.x, self.y = self.pad.x, self.pad.y + 0.15 * self.pad.dip
        mx, my = self.mouth(sc)
        S = self.size(sc)
        reach = 5.0 * S + 4
        if self.state == "zap":
            self.tongue += dt * (9 if self.tongue_out else -6)
            if self.tongue_out and self.tongue >= 1:
                self.tongue_out = False
                if self.target in sc.flies:          # got it
                    sc.flies.remove(self.target)
                    self.caught = self.target
            if not self.tongue_out and self.tongue <= 0:
                self.tongue = 0.0
                self.state = "sit"
                self.caught = None
                self.target = None
                self.cool = rng.uniform(1.0, 2.5)
                self.croak = 0.0
                self.timer = rng.uniform(0.6, 2.0)  # a happy croak soon after
            return
        # look for the bait first, then any fly in reach
        if self.cool <= 0:
            for f in sc.flies:
                if f.get("bait") is self or not f.get("bait"):
                    d = math.hypot(f["x"] - mx, (f["y"] - my) * ASPECT)
                    if d < reach and f["y"] < self.y + 1:
                        self.state = "zap"
                        self.target = f
                        self.tongue = 0.0
                        self.tongue_out = True
                        self.tx, self.ty = f["x"], f["y"]
                        self.caught = None
                        return
        # croaking: the throat sac swells and sinks a few times
        self.timer -= dt
        if self.croak > 0:
            self.croak -= dt
            ph = self.croak * 7.0
            self.sac = max(0.0, math.sin(ph)) ** 0.7
            if self.croak <= 0:
                self.sac = 0.0
                self.timer = rng.uniform(3, 9)
            elif self.sac > 0.95 and rng.random() < dt * 8:
                sc.rings.append([self.x, self.y + 0.2, 0.0, S * 0.6])
        elif self.timer <= 0:
            self.croak = math.pi * rng.randint(2, 4) / 7.0
        # gaze drifts toward the nearest fly
        near = None
        bd = 1e9
        for f in sc.flies:
            d = abs(f["x"] - self.x) + abs(f["y"] - self.y) * ASPECT
            if d < bd:
                near, bd = f, d
        want = 0.0 if near is None else clamp((near["x"] - self.x) / 12, -1, 1)
        self.look += (want - self.look) * min(1.0, dt * 3)
        # bait out of reach: leap to the pad closest to it
        bait = next((f for f in sc.flies if f.get("bait") is self), None)
        if bait is not None:
            pad = sc.pad_near(bait["x"], bait["y"], exclude=self.pad)
            if pad is not None and math.hypot(pad.x - bait["x"], (pad.y - bait["y"]) * ASPECT) < \
                    math.hypot(self.x - bait["x"], (self.y - bait["y"]) * ASPECT) - 2:
                self.leap(sc, pad)
                return
        self.hop_timer -= dt
        if self.hop_timer <= 0 and self.croak <= 0:
            pad = sc.random_free_pad(self)
            if pad is not None:
                self.leap(sc, pad)
            else:
                self.hop_timer = rng.uniform(5, 10)

    def leap(self, sc, pad):
        dist = math.hypot(pad.x - self.x, (pad.y - self.y) * ASPECT)
        self.hop = {"x0": self.x, "y0": self.y, "x1": pad.x, "y1": pad.y, "t": 0.0,
                    "dur": 0.45 + dist * 0.012, "arc": 2.5 + dist * 0.12}
        self.state = "hop"
        sc.splash(self.x, self.y, self.size(sc) * 0.7)
        if self.pad is not None:
            self.pad.frog = None
        self.pad = pad
        pad.frog = self
        self.croak = 0.0
        self.sac = 0.0

    # ------------------------------------------------------------------ draw
    def draw(self, sc, cv):
        S = self.size(sc)
        d = sc.depth_at(self.y)
        x0, y0 = self.x, self.y
        skin, acc, belly = self.skin, self.accent, self.belly

        def P(u, v):
            return x0 + u * S, y0 + v * S / ASPECT

        b = QuickBody(blend=0.3 * S)
        jumping = self.state == "hop"
        stretch = 0.0
        if jumping:
            t = self.hop["t"]
            stretch = math.sin(min(1.0, t) * math.pi)
        # body + head
        b.ellipse(*P(0, -0.8 - 0.15 * stretch), S * 1.0, S * (0.8 + 0.12 * stretch), color=skin)
        b.ellipse(*P(0, -1.45 - 0.2 * stretch), S * 0.9, S * 0.55, color=skin)
        ey = -1.95 - 0.2 * stretch
        for side in (-1, 1):
            b.circle(*P(side * 0.6, ey), S * 0.36, color=skin)
        for side in (-1, 1):
            if not jumping:
                b.ellipse(*P(side * 0.88, -0.42), S * 0.5, S * 0.4, color=skin)                 # folded thigh
                fx0, fy0 = P(side * 0.95, -0.1)
                fx1, fy1 = P(side * 1.6, 0.0)
                b.capsule(fx0, fy0, fx1, fy1, S * 0.14, S * 0.22, color=acc)                   # back foot
                lx0, ly0 = P(side * 0.45, -0.7)
                lx1, ly1 = P(side * 0.55, -0.05)
                b.capsule(lx0, ly0, lx1, ly1, S * 0.17, S * 0.15, color=skin)                  # front leg
                b.ellipse(*P(side * 0.62, 0.0), S * 0.3, S * 0.1, color=acc)                    # front foot
            else:  # mid-air: legs kicked out long, arms reaching
                tx0, ty0 = P(side * 0.7, -0.45)
                tx1, ty1 = P(side * (0.9 + 0.3 * stretch), 0.5 + 0.7 * stretch)
                b.capsule(tx0, ty0, tx1, ty1, S * 0.3, S * 0.13, color=skin)
                fx1, fy1 = P(side * (1.0 + 0.4 * stretch), 0.75 + 0.9 * stretch)
                b.capsule(tx1, ty1, fx1, fy1, S * 0.13, S * 0.2, color=acc)
                ax0, ay0 = P(side * 0.5, -0.9)
                ax1, ay1 = P(side * (0.95 + 0.2 * stretch), -1.0 - 0.5 * stretch)
                b.capsule(ax0, ay0, ax1, ay1, S * 0.15, S * 0.12, color=skin)
        # eyes: shiny, and they glance toward the nearest fly
        closed = self.blink < 0 or self.state == "zap" and not self.tongue_out
        look = self.look * 0.12
        for side in (-1, 1):
            ex, eyy = P(side * 0.6 + look, ey + 0.02)
            if closed:
                b.spot(ex, eyy, 0.6, scale(skin, 0.6), "-")
            else:
                b.spot(ex, eyy, S * 0.2 + 0.25, self.eye, "O" if S > 3.2 else "o")
        # a wide smile
        mx0, my0 = P(-0.55, -1.3 - 0.2 * stretch)
        mx1, my1 = P(0.55, -1.3 - 0.2 * stretch)
        n = max(2, int(mx1 - mx0))
        if not jumping and S > 2.4:
            for i in range(n + 1):
                xx = mx0 + (mx1 - mx0) * i / n
                ch = "\\" if i == 0 else "/" if i == n else "_"
                b.spot(xx, my0 if 0 < i < n else my0 - 0.4, 0.3, scale(skin, 0.45), ch)
        spots, bl, seed = self.spots, belly, self.seed

        def pattern(x, y, i, inside):
            u, v = (x - x0) / S, (y - y0) * ASPECT / S
            if i == 0 and abs(u) < 0.55 and v > -0.7 and inside > 0.3:
                return bl
            if spots is not None and i <= 1 and hsh(int((x - x0) * 0.7 + seed), int((y - y0) * 1.2 + seed)) > 0.78:
                return spots
            return None
        b.draw(cv, light=sc.light_dir(x0), depth=0.6 + 0.4 * d, edge=clamp(S * 0.4, 1.0, 2.2), pattern=pattern,
               ambient=0.6, mode="over")
        # the throat sac balloons out under the chin when it croaks
        if self.sac > 0.05:
            sb = QuickBody(blend=0.3)
            p = self.sac
            sb.ellipse(*P(0, -1.05 + 0.1 * p), S * 0.42 * (1 + 0.55 * p), S * 0.24 * (1 + 1.2 * p),
                       color=mix(belly, (255, 250, 220), 0.4 * p))
            sb.draw(cv, light=sc.light_dir(x0), depth=0.6 + 0.4 * d, edge=1.2, ambient=0.75, mode="over")
            if p > 0.6:
                for side in (-1, 1):
                    cv.put(x0 + side * S * (1.4 + 0.3 * p), y0 - 1.3 * S / ASPECT, ")" if side > 0 else "(",
                           scale(MOON, 0.4 * p))
                    if S > 2.6:
                        cv.put(x0 + side * S * (1.75 + 0.4 * p), y0 - 1.3 * S / ASPECT, ")" if side > 0 else "(",
                               scale(MOON, 0.25 * p))
        # the tongue: shoots out to the fly and snaps back with it
        if self.state == "zap" and self.tongue > 0:
            mx, my = self.mouth(sc)
            t = clamp(self.tongue)
            tx = mx + (self.tx - mx) * t
            ty = my + (self.ty - my) * t
            cv.line(mx, my, tx, ty, 0.6, (240, 110, 130))
            cv.put(tx, ty, "@" if self.caught is None else "*", (255, 140, 160))


class Frogs(Scene):
    name = "frogs"
    title = "Frog Pond"
    blurb = "a moonlit pond: frogs croak on lily pads, leap from pad to pad and zap flies"
    tags = ("night", "nature", "creatures", "calm")
    interactions = "click to drop a bug: the nearest frog leaps over and zaps it with its tongue"
    options = {
        "frogs": (0, "how many frogs (0 = based on size)"),
        "fireflies": (True, "fireflies over the water"),
        "moon": (True, "the moon and its reflection"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.u = max(0.35, min(h, w / 2.4) / 40.0)
        self.horizon = max(2, int(h * rng.uniform(0.2, 0.3)))
        self.mx = rng.uniform(0.15, 0.85) * w
        self.mr = max(1.5, min(h * 0.17, w * 0.09) * ASPECT * 0.5 * rng.uniform(0.85, 1.15))
        self.my = max(self.mr / ASPECT + 0.5, self.horizon * rng.uniform(0.3, 0.55))
        self.phase = rng.choice((0.0, 0.0, 0.0, 0.75, -0.75, 0.5, -0.5))   # full, gibbous or crescent
        self.palettes = rng.sample(FROGS, rng.randint(1, 3))
        self.stars = [(rng.uniform(0, w), rng.uniform(0, self.horizon - 1), rng.random()) for _ in range(self.count(25))]
        self.tseed = rng.uniform(0, 100)
        self.tree_h = rng.uniform(0.5, 1.0)
        # lily pads: farther ones (higher up) are smaller
        self.pads = []
        want = max(4, int(rng.randint(7, 12) * (w * h / (120 * 40)) ** 0.6))
        tries = 0
        while len(self.pads) < want and tries < want * 40:
            tries += 1
            y = rng.uniform(self.horizon + 2, h - 1.5)
            d = self.depth_at(y)
            R = (4.5 + 8.5 * d) * self.u * rng.uniform(0.85, 1.15)
            x = rng.uniform(R * 0.6, w - R * 0.6)
            ok = all(((x - p.x) / (R + p.R)) ** 2 + ((y - p.y) * ASPECT / ((R + p.R) * 0.42)) ** 2 > 1.0
                     for p in self.pads)
            if ok:
                self.pads.append(Pad(x, y, R, d, rng))
        for p in self.pads:
            if rng.random() < 0.35:
                p.flower = (rng.choice(FLOWERS), rng.uniform(-0.4, 0.4), rng.uniform(0, 6))
        n = self.opt("frogs") or max(1, int(round(rng.randint(2, 4) * (w * h / (120 * 40)) ** 0.5 * self.density)))
        free = [p for p in self.pads if p.flower is None] or list(self.pads)
        rng.shuffle(free)
        free.sort(key=lambda p: -p.R)
        self.frogs = [Frog(self, rng, p) for p in free[:min(n, len(free))]]
        self.flies = []
        for _ in range(rng.randint(1, 3)):
            self.add_fly(rng.uniform(0, w), rng.uniform(self.horizon + 1, h - 3))
        self.fireflies = [[rng.uniform(0, w), rng.uniform(self.horizon * 0.6, h * 0.8), rng.uniform(0, 9),
                           rng.uniform(0.6, 1.4)] for _ in range(self.count(9))]
        self.rings = []
        self.drops = []
        self.reeds = []
        for side in (0, 1):
            if rng.random() < 0.8:
                bx = rng.uniform(0, w * 0.12) if side == 0 else rng.uniform(w * 0.88, w)
                for _ in range(rng.randint(3, 7)):
                    self.reeds.append((bx + rng.uniform(-3, 3), rng.uniform(0.3, 0.7) * (h - self.horizon),
                                       rng.uniform(-0.15, 0.15), rng.uniform(0, 6), rng.random() < 0.5))

    # ------------------------------------------------------------------ helpers
    def depth_at(self, y):
        return clamp((y - self.horizon) / max(1.0, self.h - self.horizon))

    def moonlight(self, d):
        return 0.55 + 0.45 * d

    def light_dir(self, x):
        return (clamp((x - self.mx) / self.w * 2, -1, 1), -0.8)

    def add_fly(self, x, y, bait=None):
        f = {"x": x, "y": y, "hx": x, "hy": y, "ph": self.rng.uniform(0, 9), "sp": self.rng.uniform(0.7, 1.4)}
        if bait is not None:
            f["bait"] = bait
            f["big"] = True
        self.flies.append(f)
        return f

    def pad_near(self, x, y, exclude=None):
        best, bd = None, 1e9
        for p in self.pads:
            if p is exclude or (p.frog is not None and p.frog.pad is p):
                continue
            d = math.hypot(p.x - x, (p.y - y) * ASPECT)
            if d < bd:
                best, bd = p, d
        return best

    def random_free_pad(self, frog):
        opts = [p for p in self.pads if p.frog is None and p is not frog.pad
                and math.hypot(p.x - frog.x, (p.y - frog.y) * ASPECT) < self.w * 0.45]
        return self.rng.choice(opts) if opts else None

    def splash(self, x, y, S):
        self.rings.append([x, y + 0.3, 0.0, S])
        for _ in range(int(3 + S)):
            self.drops.append([x + self.rng.uniform(-S, S), y, self.rng.uniform(-3, 3), -self.rng.uniform(3, 7), 0.0])

    def on_click(self, x, y):
        y = max(y, self.horizon + 1.0)
        frog = None
        bd = 1e9
        for f in self.frogs:
            d = math.hypot(f.x - x, (f.y - y) * ASPECT)
            if d < bd:
                frog, bd = f, d
        for f in self.flies:           # one bait per frog
            if f.get("bait") is frog:
                f["bait"] = None
        self.add_fly(x, y, bait=frog)

    # ------------------------------------------------------------------ move
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.1)
        rng = self.rng
        t = self.t
        for f in self.flies:
            if f.get("bait"):     # the dropped bug: buzzes in a small circle, slowly
                f["x"] = f["hx"] + math.sin(t * 3 + f["ph"]) * 1.2
                f["y"] = f["hy"] + math.sin(t * 4.3 + f["ph"]) * 0.4
                continue
            f["hx"] += math.sin(t * 0.3 * f["sp"] + f["ph"]) * dt * 4
            f["hy"] += math.cos(t * 0.23 * f["sp"] + f["ph"] * 2) * dt * 1.5
            f["hx"] = clamp(f["hx"], 2, self.w - 2)
            f["hy"] = clamp(f["hy"], self.horizon + 1, self.h - 2)
            f["x"] = f["hx"] + math.sin(t * 9 * f["sp"] + f["ph"]) * 1.5 + rng.uniform(-0.3, 0.3)
            f["y"] = f["hy"] + math.sin(t * 7 * f["sp"] + f["ph"] * 3) * 0.6
        if len([f for f in self.flies if not f.get("bait")]) < 2 and rng.random() < dt * 0.3:
            side = rng.choice((-1, self.w + 1))
            self.add_fly(side, rng.uniform(self.horizon + 2, self.h - 3))
        for frog in self.frogs:
            frog.update(self, dt)
        for p in self.pads:
            p.dip = max(0.0, p.dip - dt * 1.5)
        for r in self.rings:
            r[2] += dt
        self.rings = [r for r in self.rings if r[2] < 2.0]
        for dr in self.drops:
            dr[0] += dr[2] * dt
            dr[1] += dr[3] * dt / ASPECT
            dr[3] += 18 * dt
            dr[4] += dt
        self.drops = [d for d in self.drops if d[4] < 0.8]
        for ff in self.fireflies:
            ff[0] += math.sin(t * 0.21 * ff[3] + ff[2]) * dt * 2.5
            ff[1] += math.cos(t * 0.17 * ff[3] + ff[2] * 1.7) * dt * 0.9
            ff[0] %= self.w
            ff[1] = clamp(ff[1], 1, self.h - 2)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, t = self.w, self.h, self.t
        hz = self.horizon
        # sky
        for x, y, k in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * (1 + k * 2) + k * 50)
            if tw > 0.25:
                cv.put(x, y, "." if k < 0.7 else "+" if k > 0.95 else "*" if k > 0.88 else ".",
                       scale((200, 210, 255), 0.3 + 0.5 * tw * k))
        if self.opt("moon"):
            self.draw_moon(cv)
        # the far shore: a dark tree line
        for x in range(w):
            top = hz - 1 - (1.0 + 3 * self.tree_h * (0.5 + 0.5 * fbm(x * 0.05, self.tseed, 3)))
            pine = max(0.0, noise1(x * 0.45 + self.tseed) - 0.1)
            top -= pine * 4 * self.tree_h
            for y in range(max(0, int(top)), hz):
                edge = y == int(top)
                ch = ("^" if pine > 0.25 else "_") if edge else ("|" if pine > 0.5 and y > top + 2 and x % 3 == 0 else "#")
                cv.put(x, y, ch, (14, 26 + 10 * edge, 26 + 6 * edge))
        # water: dark, with lazy ripple lines and the moon's broken reflection
        for y in range(hz, h):
            d = self.depth_at(y)
            for x in range(0, w, 1):
                n = math.sin(x * (0.9 - 0.5 * d) + y * 2.3 + t * (0.6 + d)) * math.sin(x * 0.13 + y * 0.7 - t * 0.4)
                if n > 0.82:
                    cv.put(x, y, "~" if n > 0.9 else "-", scale((60, 90, 130), 0.35 + 0.3 * d))
        if self.opt("moon"):
            for y in range(hz, h):
                d = self.depth_at(y)
                half = self.mr * (0.4 + 1.1 * d)
                wob = math.sin(y * 1.7 + t * 1.3) * (0.5 + 1.5 * d)
                for x in range(int(self.mx - half + wob), int(self.mx + half + wob) + 1):
                    k = 1 - abs(x - self.mx - wob) / (half + 0.5)
                    s = math.sin(x * 0.9 + y * 3.1 + t * 2.0) + math.sin(y * 1.3 - t * 1.1)
                    if s > 0.2 - k:
                        cv.put(x, y, "=" if s > 1.4 and k > 0.5 else "~" if s > 0.7 else "-",
                               scale(MOON, (0.25 + 0.55 * k) * (0.9 - 0.4 * d)))
        # ripples from splashes and croaks
        for x, y, age, S in self.rings:
            r = S * (0.8 + age * 2.5)
            n = int(r * 3) + 6
            k = 1 - age / 2.0
            for i in range(n):
                a = i / n * math.tau
                cv.shade(x + math.cos(a) * r, y + math.sin(a) * r * 0.35 / ASPECT, 0.35 * k, (150, 180, 210))
        for x in []:
            pass
        # reeds and cattails at the edges (behind pads near the shore)
        for bx, H, lean, ph, cat in self.reeds:
            n = int(H) + 1
            for k in range(n):
                f = k / max(1, n - 1)
                x = bx + lean * f * H + math.sin(t * 0.8 + ph) * f * f * 0.8
                y = h - 1 - f * H
                cv.put(x, y, "|" if abs(lean) < 0.08 else ("/" if lean > 0 else "\\"), scale((70, 110, 60), 0.4 + 0.3 * f))
            if cat:
                x = bx + lean * H + math.sin(t * 0.8 + ph) * 0.8
                for j in range(2):
                    cv.put(x, h - 1 - H - j, "#", (110, 70, 40))
                cv.put(x, h - 3 - H, "|", (70, 110, 60))
        # pads, frogs and flowers, far to near
        items = [(p.y, 0, p) for p in self.pads] + [(f.y + (0.01 if f.state != "hop" else 0.0), 1, f) for f in self.frogs]
        items.sort(key=lambda e: (e[0], e[1]))
        for y, kind, obj in items:
            if kind == 0:
                self.draw_pad(cv, obj)
            else:
                obj.draw(self, cv)
        for x, y, vx, vy, age in self.drops:
            cv.put(x, y, "'" if vy < 0 else ".", scale((170, 200, 230), 1 - age))
        # flies and fireflies on top
        for f in self.flies:
            x, y = f["x"], f["y"]
            wing = int(t * 30 + f["ph"] * 10) % 2
            if f.get("big"):
                cv.put(x, y, "@", (120, 200, 120))
                cv.put(x - 1, y, "(" if wing else "<", (180, 200, 220))
                cv.put(x + 1, y, ")" if wing else ">", (180, 200, 220))
            else:
                cv.put(x, y, "*", (120, 120, 130))
                cv.put(x, y - 0.8, "v" if wing else "^", (150, 160, 180))
        if self.opt("fireflies"):
            for x, y, ph, sp in self.fireflies:
                g = max(0.0, math.sin(t * sp * 1.3 + ph)) ** 3
                if g > 0.05:
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        cv.shade(x + dx, y + dy, 0.12 * g, (160, 220, 80))
                    cv.put(x, y, "*" if g > 0.5 else "+" if g > 0.2 else ".", scale((230, 255, 130), 0.4 + 0.6 * g))

    def draw_moon(self, cv):
        mx, my, r = self.mx, self.my, self.mr
        ph = self.phase
        for y in range(max(0, int(my - r / ASPECT - 3)), min(self.horizon, int(my + r / ASPECT + 4))):
            for x in range(max(0, int(mx - r - 6)), min(self.w, int(mx + r + 7))):
                dx, dy = x + 0.5 - mx, (y + 0.5 - my) * ASPECT
                d = math.hypot(dx, dy)
                if d < r:
                    if ph and math.hypot(dx - ph * r * 2.2, dy) < r * 1.05:   # the shadowed part
                        cv.shade(x, y, 0.12, (60, 70, 100))
                        continue
                    crater = fbm(x * 0.35, y * 0.7, 2, seed=5)
                    v = 0.75 + 0.25 * (1 - d / r) - 0.25 * max(0.0, crater)
                    cv.shade(x, y, v, mix((200, 200, 175), MOON, 1 - max(0.0, crater) * 2))
                elif d < r + 5:
                    cv.shade(x, y, 0.16 * (1 - (d - r) / 5) ** 2, (160, 170, 200))

    def draw_pad(self, cv, p):
        R = p.R
        ry = R * 0.38 / ASPECT
        bob = math.sin(self.t * 0.7 + p.bob) * 0.12 + 0.2 * p.dip
        cx, cy = p.x, p.y + bob
        col = p.color
        ca, sa = math.cos(p.notch), math.sin(p.notch)
        lx = clamp((cx - self.mx) / self.w * 2, -1, 1)
        fade_ = 0.55 + 0.45 * p.depth
        for y in range(max(0, int(cy - ry)), min(self.h, int(cy + ry) + 1)):
            v_ = (y + 0.5 - cy) / ry
            if abs(v_) >= 1:
                continue
            half = R * math.sqrt(1 - v_ * v_)
            for x in range(max(0, int(cx - half)), min(self.w, int(cx + half) + 1)):
                u = (x + 0.5 - cx) / R
                rr = math.hypot(u, v_)
                if rr >= 1:
                    continue
                # the notch: a thin wedge cut from the center to the rim
                if rr > 0.1 and (u * ca + v_ * sa) > rr * 0.95:
                    continue
                a = math.atan2(v_, u)
                vein = abs(math.sin(a * 4.5 + p.notch)) < 0.16 and 0.15 < rr < 0.85
                edge = clamp((1 - rr) * R * 0.8)          # 0 at the rim .. 1 one cell inside
                lit = 0.5 + 0.5 * (-u * lx - v_ * 0.6)     # the moon side of the rim catches light
                v = 0.26 + 0.16 * edge + 0.4 * (1 - edge) * clamp(lit)
                c = mix(col, (190, 235, 150), 0.35 * (1 - edge) * clamp(lit))
                if vein:
                    v *= 0.7
                    c = scale(col, 0.75)
                cv.shade(x, y, v * fade_, c, mode="over")
        if p.flower is not None:
            (petal, tip), off, ph = p.flower
            self.draw_flower(cv, cx + off * R, cy - ry * 0.15, R, petal, tip, p.depth)

    def draw_flower(self, cv, x, y, R, petal, tip, depth):
        """A water lily: a cup of pointed petals around a golden middle (glyph art, sized to the pad)."""
        art = LILY[0] if R < 7 else LILY[1] if R < 12 else LILY[2]
        k = 0.65 + 0.35 * depth
        rows = len(art)
        sway = round(math.sin(self.t * 0.5 + x) * 0.4)
        for j, line in enumerate(art):
            f = j / max(1, rows - 1)          # 0 = petal tips at the top
            for i, ch in enumerate(line):
                if ch == " ":
                    continue
                c = (255, 205, 70) if ch in "@o" else mix(tip, petal, 0.3 + 0.7 * f)
                cv.put(x - len(line) // 2 + i + (sway if j == 0 else 0), y - rows + 1 + j, ch, scale(c, k))


LILY = [
    [r"\|/", r"-o-"],
    [r" \ | / ", r" -\|/- ", r"--(@)--"],
    [r"  \  |  /  ", r" \ \ | / / ", r"`-.\\||//.-'", r" --=(@@)=-- "],
]
