"""An owl on a branch under a big moon. Its head follows the pointer; click and it flies.

The owl is round parts in layers (QuickBody: shapes.Body with a faster draw): an egg of a body
with folded wings, a round head, then a pale facial disc with two huge eyes and a hooked beak on
top. Turning the head is just sliding the face across the head and squashing it: past a quarter
turn the face slips around the side, and every so often the owl does the famous full swivel,
face vanishing behind and coming back round the other side. Feathers are a pattern callback.
"""
import math

from ..engine import ASPECT, Scene, clamp, fbm, mix, noise1, scale
from .aquarium import QuickBody, hsh

OWLS = [
    # name, body, wing, face disc, belly, eye, beak, tufts
    ("barn owl", (215, 165, 95), (190, 140, 80), (248, 244, 236), (245, 238, 225), (45, 30, 25), (235, 215, 190), False),
    ("snowy owl", (235, 235, 232), (215, 215, 212), (248, 248, 246), (245, 245, 242), (250, 200, 40), (60, 60, 60), False),
    ("tawny owl", (150, 100, 60), (120, 80, 50), (195, 150, 100), (200, 160, 110), (40, 28, 22), (220, 200, 140), False),
    ("great horned owl", (140, 115, 85), (110, 90, 65), (215, 175, 130), (210, 195, 170), (255, 205, 40), (60, 55, 50), True),
    ("long-eared owl", (165, 120, 70), (130, 95, 55), (225, 160, 90), (215, 180, 130), (255, 150, 30), (50, 45, 40), True),
    ("screech owl", (130, 130, 135), (105, 105, 110), (175, 175, 175), (200, 200, 200), (250, 210, 50), (90, 95, 90), True),
]
MOON = (240, 236, 210)


class Owl(Scene):
    name = "owl"
    title = "Night Owl"
    blurb = "an owl on a branch under a big moon: it blinks, hoots, swivels its head and flies"
    tags = ("night", "nature", "creatures", "calm")
    interactions = "point and the owl turns its head to watch you, click to make it fly across the moon"
    options = {
        "species": ("random", "random, barn, snowy, tawny, great, long, screech"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        want = str(self.opt("species")).lower()
        owls = [o for o in OWLS if o[0].startswith(want)] or OWLS
        (self.kind, self.body, self.wing, self.disc, self.belly, self.eye, self.beak,
         self.tufts) = rng.choice(owls)
        self.O = max(2.0, min(h * 0.24, w * 0.09) * rng.uniform(0.9, 1.05))
        O = self.O
        # the moon and the forest
        self.mr = max(3.0, min(h * 0.42, w * 0.2) * rng.uniform(0.8, 1.0))
        self.mx = w * rng.uniform(0.35, 0.65)
        self.my = h * rng.uniform(0.32, 0.42)
        self.stars = [(rng.uniform(0, w), rng.uniform(0, h * 0.7), rng.random()) for _ in range(self.count(30))]
        self.tseed = rng.uniform(0, 100)
        self.trees = []
        for _ in range(max(3, int(w / 14))):
            self.trees.append((rng.uniform(0, w), rng.uniform(0.35, 0.8) * h, rng.uniform(0.25, 0.45),
                               rng.uniform(0.25, 0.7)))
        self.trees.sort(key=lambda t: t[3])
        self.ground = h - max(1, int(h * 0.08))
        # branches: the main one from one side, maybe a second from the other
        side = rng.choice((-1, 1))
        self.branches = []
        for k, sd in enumerate((side, -side)):
            if k == 1 and rng.random() < 0.35:
                break
            y = h * (rng.uniform(0.72, 0.8) if k == 0 else rng.uniform(0.5, 0.65))
            x0 = -2 if sd < 0 else w + 2
            length = w * (rng.uniform(0.5, 0.62) if k == 0 else rng.uniform(0.25, 0.35))
            x1 = x0 - sd * length
            y1 = y + rng.uniform(-0.6, 0.6) * O / ASPECT
            perch = x0 - sd * length * rng.uniform(0.62, 0.78)
            twigs = [(rng.uniform(0.2, 0.9), rng.choice((-1, 1)), rng.uniform(0.3, 0.7)) for _ in range(rng.randint(1, 3))]
            self.branches.append({"x0": x0, "y0": y, "x1": x1, "y1": y1, "perch": perch, "twigs": twigs,
                                  "r": max(0.8, O * 0.16) * (1.0 if k == 0 else 0.8)})
        b = self.branches[0]
        self.x, self.y = b["perch"], self.branch_y(b, b["perch"])
        head_y = self.y - 2.6 * O / ASPECT
        off = rng.choice((-1, 1)) * (self.mr * rng.uniform(0.9, 1.25) + O * 0.4)
        self.mx = clamp(self.x + off, self.mr * 0.6, w - self.mr * 0.6)
        if abs(self.mx - self.x) < self.mr * 0.7:
            self.mx = clamp(self.x - off, self.mr * 0.6, w - self.mr * 0.6)
        self.my = clamp(head_y - rng.uniform(0.1, 0.5) * self.mr / ASPECT, self.mr / ASPECT * 0.7, h * 0.45)
        self.home = 0
        # state
        self.yaw = 0.0
        self.pitch = 0.0
        self.tilt = 0.0
        self.spin = None
        self.spin_t = rng.uniform(10, 20)
        self.blink = rng.uniform(1, 4)
        self.hoot_t = rng.uniform(3, 8)
        self.hoot = 0.0
        self.hoos = []
        self.flight = None
        self.flap = 0.0
        self.idle = 0.0
        self.look_t = 0.0
        self.idle_yaw = 0.0

    # ------------------------------------------------------------------ helpers
    def branch_y(self, b, x):
        t = clamp((x - b["x0"]) / ((b["x1"] - b["x0"]) or 1))
        return b["y0"] + (b["y1"] - b["y0"]) * t - b["r"] / ASPECT * 0.9

    def on_click(self, x, y):
        if self.flight is not None:
            return
        rng = self.rng
        dest = rng.randrange(len(self.branches)) if len(self.branches) > 1 and rng.random() < 0.6 else self.home
        b = self.branches[dest]
        tx = clamp(b["perch"] + rng.uniform(-0.12, 0.12) * self.w, min(b["x0"], b["x1"]) + self.O * 1.5,
                   max(b["x0"], b["x1"]) - self.O * 1.5)
        ty = self.branch_y(b, tx)
        # out across the face of the moon and back
        side = 1 if self.x < self.mx else -1
        p1 = (self.mx - side * self.mr * 0.3, self.my - self.mr * 0.25 / ASPECT)
        p2 = (self.mx + side * self.mr * 1.4, self.my + self.mr * 0.1 / ASPECT)
        self.flight = {"p": [(self.x, self.y), p1, p2, (tx, ty)], "t": 0.0, "dur": 4.5, "dest": dest}
        self.spin = None

    def flight_pos(self, t):
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = self.flight["p"]
        u = 1 - t
        x = u ** 3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * x3
        y = u ** 3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y3
        return x, y

    # ------------------------------------------------------------------ move
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.1)
        rng = self.rng
        O = self.O
        if self.flight is not None:
            fl = self.flight
            fl["t"] += dt / fl["dur"]
            t = clamp(fl["t"])
            self.x, self.y = self.flight_pos(t)
            self.flap += dt * (9 if t < 0.85 else 5)
            if fl["t"] >= 1:
                self.home = fl["dest"]
                self.flight = None
                self.yaw = 0.0
        else:
            hx, hy = self.x, self.y - 2.6 * O / ASPECT
            if self.pointer is not None:
                px, py = self.pointer
                dx = px - hx
                # past the shoulder the head keeps turning, owl-style
                target = clamp(dx / (self.w * 0.3), -1.0, 1.0) * 1.35 + clamp(dx / (self.w * 0.3), -1.6, 1.6) * 0.0
                if abs(dx) > self.w * 0.32:
                    target = math.copysign(2.1, dx)
                self.pitch += (clamp((py - hy) * ASPECT / (self.h * 1.2), -0.5, 0.5) - self.pitch) * min(1.0, dt * 5)
                self.spin = None
                self.idle = 0.0
                speed = 6.0
            else:
                self.idle += dt
                self.look_t -= dt
                if self.look_t < 0:
                    self.idle_yaw = rng.choice((0.0, 0.0, rng.uniform(-1.2, 1.2)))
                    self.look_t = rng.uniform(2, 5)
                target = self.idle_yaw
                self.pitch *= 1 - min(1.0, dt * 2)
                speed = 3.0
                self.spin_t -= dt
                if self.spin is None and self.spin_t < 0:
                    self.spin = 0.0
                    self.spin_t = rng.uniform(18, 30)
            if self.spin is not None:          # the famous full swivel
                self.spin += dt * 0.9
                self.yaw = self.spin * math.tau * 0.25 * (2.2 - 0.9 * math.cos(self.spin * 1.3))
                if self.yaw >= math.tau:
                    self.yaw = 0.0
                    self.spin = None
            else:
                self.yaw += (target - self.yaw) * min(1.0, dt * speed)
            # a curious head tilt now and then
            self.tilt = 0.25 * math.sin(self.t * 0.4) * max(0.0, math.sin(self.t * 0.13 + 1)) ** 4
            self.blink -= dt
            if self.blink < -0.16:
                self.blink = rng.uniform(1.5, 5)
            self.hoot_t -= dt
            if self.hoot_t < 0 and self.spin is None:
                self.hoot = 1.6
                self.hoot_t = rng.uniform(7, 14)
                n = rng.choice((1, 2, 2, 3))
                for k in range(n):
                    self.hoos.append([0.0, -0.45 * k, rng.choice((-1, 1)) if abs(self.yaw) < 0.3 else
                                      (1 if math.sin(self.yaw) > 0 else -1)])
            self.hoot = max(0.0, self.hoot - dt)
        for hoo in self.hoos:
            hoo[1] += dt
        self.hoos = [hh for hh in self.hoos if hh[1] < 2.4]

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h, t = self.w, self.h, self.t
        for x, y, k in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * (0.8 + k * 2) + k * 30)
            if math.hypot(x - self.mx, (y - self.my) * ASPECT) > self.mr + 4:
                cv.put(x, y, "*" if k > 0.93 else "+" if k > 0.85 else ".", scale((210, 215, 255), 0.25 + 0.5 * tw * k))
        self.draw_moon(cv)
        self.draw_forest(cv)
        for b in self.branches:
            self.draw_branch(cv, b)
        if self.flight is None:
            self.draw_perched(cv)
        else:
            self.draw_flying(cv)
        # "hoo" puffs drifting away from the beak
        hx, hy = self.x, self.y - 2.4 * self.O / ASPECT
        for age, delay, side in self.hoos:
            a = age + delay
            if a < 0 or self.flight is not None:
                continue
            k = clamp(1 - a / 2.4) * clamp(a * 4)
            x = hx + side * (self.O * 1.2 + a * 4)
            y = hy - a * 1.6
            cv.text(int(x) - (3 if side < 0 else 0), int(y), "hoo", scale((220, 225, 255), 0.25 + 0.7 * k))

    def draw_moon(self, cv):
        mx, my, r = self.mx, self.my, self.mr
        for y in range(max(0, int(my - r / ASPECT - 4)), min(self.h, int(my + r / ASPECT + 5))):
            for x in range(max(0, int(mx - r - 8)), min(self.w, int(mx + r + 9))):
                d = math.hypot(x + 0.5 - mx, (y + 0.5 - my) * ASPECT)
                if d < r:
                    c = fbm(x * 0.12, y * 0.24, 3, seed=11)
                    v = 0.55 + 0.3 * (1 - (d / r) ** 4) - 0.25 * max(0.0, c)
                    cv.shade(x, y, v, mix((205, 200, 175), MOON, clamp(1 - max(0.0, c) * 2.5)))
                elif d < r + 8:
                    cv.shade(x, y, 0.2 * (1 - (d - r) / 8) ** 2, (170, 180, 210))

    def draw_forest(self, cv):
        h, w = self.h, self.w
        for tx, th, tw, depth in self.trees:            # pine silhouettes, the far ones bluer
            col = mix((16, 22, 38), (10, 20, 16), depth)
            top = self.ground - th
            for y in range(max(0, int(top)), self.ground):
                f = (y - top) / max(1, th)
                half = th * tw * f * (0.75 + 0.25 * math.sin(y * 1.7 + tx))
                for x in range(max(0, int(tx - half)), min(w, int(tx + half) + 1)):
                    ch = "^" if y == int(top) else "/" if x < tx - half + 1 else "\\" if x > tx + half - 1 else "#"
                    cv.put(x, y, ch, scale(col, 0.8 + 0.3 * depth))
        for x in range(w):
            for y in range(self.ground, h):
                ch = "\"" if hsh(x, y) > 0.6 else "," if hsh(x, y, 2) > 0.5 else "."
                cv.put(x, y, ch, (20, 40, 25))

    def draw_branch(self, cv, b):
        q = QuickBody(blend=b["r"] * 0.6)
        q.capsule(b["x0"], b["y0"], b["x1"], b["y1"], b["r"] * 1.4, b["r"] * 0.55, color=(105, 75, 50))
        for f, sd, ln in b["twigs"]:
            x = b["x0"] + (b["x1"] - b["x0"]) * f
            y = b["y0"] + (b["y1"] - b["y0"]) * f
            dx = (b["x1"] - b["x0"]) * 0.12 * ln
            q.capsule(x, y, x + dx, y + sd * ln * self.O * 0.25, b["r"] * 0.5, b["r"] * 0.2, color=(95, 70, 48))
        seed = self.tseed

        def bark(x, y, i, inside):
            if hsh(int(x * 0.5 + seed), int(y)) > 0.75:
                return (70, 50, 35)
            return None
        q.draw(cv, light=((self.mx - (b["x0"] + b["x1"]) / 2) / self.w, -1.0), edge=1.4, pattern=bark, ambient=0.45,
               mode="over")
        # a few leaves
        for f, sd, ln in b["twigs"]:
            x = b["x0"] + (b["x1"] - b["x0"]) * f + (b["x1"] - b["x0"]) * 0.12 * ln
            y = b["y0"] + (b["y1"] - b["y0"]) * f + sd * ln * self.O * 0.25 / ASPECT
            for k in range(5):
                lx = x + math.cos(k * 1.3 + f * 9) * 1.6
                ly = y + math.sin(k * 1.3 + f * 9) * 0.8
                sway = math.sin(self.t * 1.2 + k + f * 5) * 0.3
                cv.put(lx + sway, ly, "*" if k % 2 else "o", scale((70, 120, 60), 0.55 + 0.1 * k))

    def feather(self, kind):
        """Pattern callbacks: scalloped chevrons on the breast, bars on the wings, specks."""
        x0, y0, O = self.x, self.y, self.O
        body, wing, belly = self.body, self.wing, self.belly
        snowy = self.kind.startswith("snowy")
        dark = scale(wing, 0.55)

        def pattern(x, y, i, inside):
            u = (x - x0) / O
            v = (y - y0) * ASPECT / O
            if kind == "body":
                if i == 0 and abs(u) < 0.55 and v > -2.0:          # pale breast with chevrons
                    if (math.sin(u * 9) * 0.15 + v * 4.5) % 1.0 < 0.22 and hsh(int(x), int(y)) > 0.35:
                        return dark if not snowy else (60, 60, 65)
                    return belly
                if i in (1, 2):                                   # wings: barred feathers
                    if (v * 3.2 + u * 0.4) % 1.0 < 0.25:
                        return dark if not snowy else (80, 80, 85)
                    return wing
            elif kind == "head" and snowy:
                if hsh(int(x * 0.8), int(y * 1.3), 4) > 0.85:
                    return (70, 70, 75)
            return None
        return pattern

    def draw_perched(self, cv):
        O = self.O
        x0, y0 = self.x, self.y
        hoot = self.hoot
        puff = 0.06 * max(0.0, math.sin(hoot * 6)) if hoot > 0 else 0.0
        bob = 0.08 * max(0.0, math.sin(hoot * 6)) if hoot > 0 else 0.0

        def P(u, v):
            return x0 + u * O, y0 + v * O / ASPECT

        L = (clamp((self.mx - x0) / self.w * 2, -1, 1), -0.7)
        b = QuickBody(blend=0.25 * O)
        b.ellipse(*P(0, -1.2), O * (0.95 + puff), O * 1.2, color=self.body)          # 0 body
        for sd in (-1, 1):                                                         # 1, 2 folded wings
            b.ellipse(*P(sd * 0.72, -1.05), O * 0.42, O * 1.08, angle=sd * 0.12, color=self.wing)
        tx0, ty0 = P(0, -0.2)
        tx1, ty1 = P(0, 0.45)
        b.capsule(tx0, ty0, tx1, ty1, O * 0.3, O * 0.18, color=self.wing)           # tail
        b.draw(cv, light=L, edge=clamp(O * 0.3, 1.2, 3.5), pattern=self.feather("body"), ambient=0.6, mode="over")
        # talons gripping the branch
        for sd in (-1, 1):
            fx, fy = P(sd * 0.32, 0.0)
            cv.text(int(fx) - 1, int(fy + 0.6), "vVv" if O > 6 else "v", (225, 190, 90))
        # the head: it can swivel all the way round
        yaw = self.yaw
        cy_ = math.cos(yaw)
        sy_ = math.sin(yaw)
        hu, hv = 0.0, -2.55 + bob
        hx, hy = P(hu, hv)
        hb = QuickBody(blend=0.2 * O)
        hb.circle(hx, hy, O * 0.95, color=self.body)
        if self.tufts:
            for sd in (-1, 1):
                k = sd * cy_ - 0.3 * sy_          # tufts slide with the turn too
                ax, ay = P(hu + k * 0.5, hv - 0.65)
                bx, by = P(hu + k * 0.72 + sd * 0.1, hv - 1.35)
                hb.capsule(ax, ay, bx, by, O * 0.24, O * 0.04, color=self.wing)
        hb.draw(cv, light=L, edge=clamp(O * 0.28, 1.2, 3.2), pattern=self.feather("head"), ambient=0.6, mode="over")
        if cy_ > -0.55:                       # the face is on our side of the head
            self.draw_face(cv, P, hu + sy_ * 0.55, hv + self.pitch * 0.25, max(0.25, cy_), L)

    def draw_face(self, cv, P, fu, fv, squash, L):
        O = self.O
        f = QuickBody(blend=0.3 * O)
        tilt = self.tilt
        for sd in (-1, 1):                    # a heart-shaped disc: two soft lobes
            du = sd * 0.4 * squash
            dv = sd * tilt * 0.4
            f.ellipse(*P(fu + du, fv - 0.02 + dv), O * 0.56 * squash, O * 0.64, angle=sd * 0.15, color=self.disc)
        bx0, by0 = P(fu, fv - 0.05)
        bx1, by1 = P(fu, fv + 0.38)
        f.capsule(bx0, by0, bx1, by1, O * 0.12, O * 0.04, color=self.beak)
        closed = self.blink < 0
        eyes = []
        for sd in (-1, 1):
            ex, ey = P(fu + sd * 0.45 * squash, fv - 0.14 + sd * tilt * 0.4)
            eyes.append((ex, ey))
        ri = O * 0.3 * squash + 0.4             # iris radius (x-cells)
        if closed:
            for ex, ey in eyes:
                f.spot(ex, ey, ri, scale(self.disc, 0.8), None)
                f.spot(ex, ey, 0.6, scale(self.disc, 0.3), "-")
        else:
            # decals are painted in order, so: both rims, then both irises, then pupils, then glints
            for ex, ey in eyes:
                f.spot(ex, ey, ri + 0.6, (0, 0, 0), " ")          # a dark gap rings each eye
            for ex, ey in eyes:
                f.spot(ex, ey, ri, self.eye, None)
            dx = clamp(self.yaw * 0.4, -0.6, 0.6) * O * 0.08
            dy = self.pitch * O * 0.06 / ASPECT
            for ex, ey in eyes:
                f.spot(ex + dx, ey + dy, O * 0.1 * squash + 0.25, (0, 0, 0), " ")
            for ex, ey in eyes:
                f.spot(ex + dx - O * 0.06, ey + dy - O * 0.04 / ASPECT, 0.2, (255, 255, 255), "'" if O > 5 else ".")
        f.draw(cv, light=L, edge=clamp(O * 0.2, 1.0, 2.4), ambient=0.8, mode="over")

    def draw_flying(self, cv):
        """Wings out: a body, a head, and two long wings that beat."""
        fl = self.flight
        t = clamp(fl["t"])
        depth = 1 - 0.55 * math.sin(t * math.pi)        # smaller out over the moon
        O = self.O * depth
        x0, y0 = self.x, self.y
        land = clamp((t - 0.85) / 0.15)
        beat = math.sin(self.flap) * (1 - land * 0.7)

        def P(u, v):
            return x0 + u * O, y0 + v * O / ASPECT

        L = (clamp((self.mx - x0) / self.w * 2, -1, 1), -0.7)
        b = QuickBody(blend=0.2 * O)
        b.ellipse(*P(0, -1.3), O * 0.75, O * 1.05, color=self.body)
        for sd in (-1, 1):
            sx, sy = P(sd * 0.5, -1.7)
            ex, ey = P(sd * 1.9, -1.9 - beat * 0.9)
            tx, ty = P(sd * (3.1 - 0.4 * abs(beat)), -1.6 - beat * 1.9)
            b.capsule(sx, sy, ex, ey, O * 0.45, O * 0.38, color=self.wing)
            b.capsule(ex, ey, tx, ty, O * 0.38, O * 0.12, color=self.wing)
        b.circle(*P(0, -2.45), O * 0.78, color=self.body)
        tx0, ty0 = P(0, -0.4)
        tx1, ty1 = P(0, 0.2)
        b.capsule(tx0, ty0, tx1, ty1, O * 0.3, O * 0.3, color=self.wing)
        b.draw(cv, light=L, edge=clamp(O * 0.28, 1.0, 3.0), pattern=self.feather("body"), ambient=0.5, mode="over")
        self.draw_face(cv, P, 0.0, -2.4, 0.85, L)
        # legs dangle down for the landing
        if land > 0:
            for sd in (-1, 1):
                fx, fy = P(sd * 0.3, 0.1 + 0.3 * land)
                cv.put(fx, fy, "v", (225, 190, 90))
