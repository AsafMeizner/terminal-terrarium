"""An axolotl in a planted tank: it potters about, naps on the sand with a smile, and comes to see you.

The axolotl is a shapes.Chain spine (move the head, the body trails behind) wrapped in a
shapes.Body: a broad round head, a chubby body, a tapering tail with a see-through fin, four
little paddling legs, and the famous feathery gills, three stalks per side, each fringed with
fine filaments that wave in the water. Simple rules move it: wander lazily (shapes.Mover), sink
down and rest now and then, follow the pointer slowly, and gulp down bloodworms.
"""
import math
import random

from ..engine import ASPECT, Canvas, Scene, clamp, gradient, hsv, mix, scale
from ..shapes import Body, Chain, Mover

# morph: body color, belly color, gill color, eye color, speckles?
MORPHS = {
    "leucistic": ((255, 196, 206), (255, 225, 230), (255, 80, 135), (40, 20, 40), False),
    "golden": ((255, 205, 105), (255, 230, 165), (255, 140, 120), (235, 85, 110), False),
    "wild": ((125, 115, 80), (160, 150, 110), (165, 95, 135), (30, 25, 20), True),
    "albino": ((245, 240, 232), (255, 252, 245), (255, 110, 145), (235, 75, 105), False),
    "copper": ((215, 140, 95), (235, 175, 130), (240, 105, 95), (120, 40, 40), True),
    "melanoid": ((96, 98, 110), (120, 120, 132), (130, 95, 130), (20, 20, 25), False),
}


def cellhash(x, y, s=0):
    """A cheap per-cell random number in [-1, 1]."""
    n = (x * 374761393 + y * 668265263 + s * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 32767.5 - 1.0


def slope_ch(dx, dy):
    """Line glyph for a direction in stretched space."""
    ax, ay = abs(dx), abs(dy)
    if ax > 2.0 * ay:
        return "-"
    if ay > 2.0 * ax:
        return "|"
    return "\\" if dx * dy > 0 else "/"


class Axolotl(Scene):
    name = "axolotl"
    title = "Axolotl"
    blurb = "a smiling axolotl with frilly gills potters around a planted tank and naps on the sand"
    tags = ("water", "creatures", "cute", "cozy", "calm")
    interactions = "it follows the pointer (slowly, curiously); click to drop a bloodworm it gulps down"
    options = {
        "morph": ("random", "leucistic, golden, wild, albino, copper, melanoid or random"),
        "plants": (True, "draw the plants"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        m = self.opt("morph")
        self.morph = m if m in MORPHS else rng.choice(["leucistic"] * 3 + list(MORPHS))
        self.colors = MORPHS[self.morph]
        self.top = 1.5
        self.floor = h - max(2.0, h * 0.12)
        # size from the tank: about a third of the width, but it has to fit the height too
        self.Lb = Lb = clamp(min(w * 0.3, (self.floor - self.top) * ASPECT * 0.8), 12, 64)
        self.n = 12
        x, y = w * rng.uniform(0.3, 0.7), self.floor - Lb * 0.12 / ASPECT
        heading = rng.choice((0.0, math.pi))
        self.mover = Mover(rng, x, y, speed=Lb * 0.2, depth=1.0)
        self.mover.heading = heading
        self.chain = Chain(x, y, self.n, spacing=Lb / self.n, angle=heading + math.pi)
        self.state = "rest"
        self.timer = rng.uniform(3, 7)
        self.blink = rng.uniform(2, 5)
        self.gulp = 0.0
        self.paddle = 0.0
        self.worms = []          # [x, y, vy, wiggle seed, eaten]
        self.bubbles = []
        self.spots = [(rng.uniform(0, 1), rng.uniform(-1, 1)) for _ in range(40)] if self.colors[4] else []
        self.chubby = rng.uniform(0.95, 1.15)
        self.gill_len = rng.uniform(0.9, 1.2)
        self.air = rng.uniform(0.1, 0.9) * w
        self.bg = None
        self.bg_seed = rng.random()
        self.body_cache = None
        self.plants = self.roll_plants()

    def roll_plants(self):
        rng = self.rng
        w, h = self.w, self.h
        plants = []
        # vallisneria: long ribbons along the back, in clumps
        for _ in range(rng.randint(2, 4)):
            cx = rng.uniform(0.05, 0.95) * w
            for k in range(rng.randint(3, 7)):
                plants.append(("ribbon", cx + rng.uniform(-3, 3), rng.uniform(0.45, 0.92) * (self.floor - self.top),
                               rng.uniform(0, math.tau), mix((60, 150, 70), (130, 200, 90), rng.random())))
        # a few round moss balls and fern clumps on the sand
        for _ in range(rng.randint(0, 2)):
            plants.append(("moss", rng.uniform(0.05, 0.95) * w, rng.uniform(1.2, 2.2) * max(1.0, h / 30), 0, (70, 140, 60)))
        for _ in range(rng.randint(1, 2)):
            plants.append(("fern", rng.uniform(0.05, 0.95) * w, rng.uniform(4, 7) * max(0.7, h / 35), rng.random(),
                           (50, 120, 60)))
        return plants

    # ------------------------------------------------------------------ interaction
    def on_click(self, x, y):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        y = clamp(y, self.top + 1, self.floor - 1)
        self.worms.append([x, y, 0.0, self.rng.uniform(0, 10)])
        if len(self.worms) > 6:
            self.worms.pop(0)

    # ------------------------------------------------------------------ move
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.2)
        rng = self.rng
        m = self.mover
        Lb = self.Lb
        for wm in self.worms:   # bloodworms sink slowly, then wriggle on the sand
            wm[2] = min(2.0, wm[2] + dt)
            wm[1] = min(self.floor - 0.6, wm[1] + wm[2] * dt)
        ptr = self.pointer
        if ptr is not None and not (0 <= ptr[0] < self.w and self.top <= ptr[1] < self.h):
            ptr = None
        target = None
        speed_k = 1.0
        if self.worms:
            self.state = "eat"
            wm = min(self.worms, key=lambda q: abs(q[0] - m.x) + abs(q[1] - m.y) * 2)
            target = (wm[0], wm[1])
            speed_k = 1.3
            if m.near(wm[0], wm[1], Lb * 0.12 + 1.0):
                self.worms.remove(wm)
                self.gulp = 0.6
                self.state, self.timer = "swim", rng.uniform(4, 8)
                target = None
        elif ptr is not None:
            self.state = "follow"
            # stop a little short of the pointer and look at it
            dx, dy = ptr[0] - m.x, (ptr[1] - m.y) * ASPECT
            d = math.hypot(dx, dy)
            stand_off = Lb * 0.22
            if d > stand_off:
                target = ptr
                speed_k = clamp((d - stand_off) / (Lb * 0.25), 0.3, 1.0)
            else:
                speed_k = 0.0
                want = math.atan2(dy, dx)
                diff = (want - m.heading + math.pi) % math.tau - math.pi
                m.heading += diff * dt * 1.5
        elif self.state == "follow":
            self.state, self.timer = "swim", rng.uniform(3, 6)
        self.timer -= dt
        if self.state == "rest":
            speed_k = 0.0
            if self.timer <= 0:
                self.state, self.timer = "swim", rng.uniform(8, 16)
                m.heading = -0.4 if math.cos(m.heading) > 0 else math.pi + 0.4
        elif self.state == "swim" and self.timer <= 0:
            self.state, self.timer = "sink", 6.0
        if self.state == "sink":
            target = (m.x + math.cos(m.heading) * Lb * 0.5, self.floor)
            speed_k = 0.6
            if m.y >= self.floor - Lb * 0.13 / ASPECT - 0.3 or self.timer <= 0:
                self.state, self.timer = "rest", rng.uniform(6, 14)
        if speed_k > 0:
            sp = m.speed
            m.speed = sp * speed_k
            m.update(dt, self.t, (self.w, self.h), target=target, margin=0)
            m.speed = sp
            self.paddle += dt * (3 + 5 * speed_k)
        # mostly level swimmer; keep inside the tank
        fr = math.cos(m.heading) >= 0
        if target is not None and abs(target[0] - m.x) > Lb * 0.1:
            fr = target[0] > m.x          # turn round (smoothly) for food or the pointer behind it
        base = 0.0 if fr else math.pi
        diff = (m.heading - base + math.pi) % math.tau - math.pi
        lim = 0.75 if self.state in ("eat", "follow", "sink") else 0.45
        if abs(diff) > lim:
            m.heading -= math.copysign(min(abs(diff) - lim, dt * 2.2), diff)
        margin = Lb * 0.2
        hy = Lb * 0.13 / ASPECT
        if m.x < margin or m.x > self.w - margin:
            m.heading = math.pi - m.heading
            m.x = clamp(m.x, margin, self.w - margin)
        m.y = clamp(m.y, self.top + hy + 1.5, self.floor - hy)
        self.chain.follow(m.x, m.y)
        # the body rests on the sand rather than sinking into it
        pts = self.chain.points
        r_body = Lb * 0.11 / ASPECT
        sag = 0.6 if self.state == "rest" else 0.0
        for i in range(1, len(pts)):
            x, y = pts[i]
            lo = self.floor - r_body * (1 - i / len(pts) * 0.6)
            y = min(lo, y + sag * dt * 2)
            pts[i] = (x, y)
        self.blink -= dt
        if self.blink < -0.18:
            self.blink = rng.uniform(2.5, 6.0)
        self.gulp = max(0.0, self.gulp - dt)
        # bubbles from the air stone
        if rng.random() < dt * 4:
            self.bubbles.append([self.air + rng.uniform(-0.5, 0.5), self.floor - 0.5, rng.random()])
        for b in self.bubbles:
            b[1] -= dt * (3 + b[2] * 3)
            b[0] += math.sin(self.t * 3 + b[2] * 10) * dt * 0.8
        self.bubbles = [b for b in self.bubbles if b[1] > self.top + 0.5]

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
        # water surface and light shafts
        for x in range(self.w):
            y = self.top + math.sin(x * 0.3 + t * 1.2) * 0.25
            cv.put(x, y, "~" if (x + int(t * 2)) % 4 else "-", (140, 200, 230), level=0.4)
        if self.opt("plants"):
            self.draw_plants(cv, back=True)
        for b in self.bubbles:
            cv.put(b[0], b[1], "o" if b[2] > 0.6 else "°", (180, 220, 250), level=0.4)
        for x, y, vy, s in self.worms:
            for k in range(4):
                wx = x + k * 0.8 - 1.2
                wy = y + math.sin(t * 8 + s + k * 1.3) * 0.45
                cv.put(wx, wy, "~" if k % 2 else "s", (220, 40, 50), level=0.8)
        self.draw_axolotl(cv)
        if self.opt("plants"):
            self.draw_plants(cv, back=False)

    def draw_plants(self, cv, back):
        t = self.t
        for kind, x, size, ph, col in self.plants:
            if kind == "ribbon" and back:
                n = int(size) + 1
                for k in range(n):
                    f = k / max(1, n - 1)
                    sway = math.sin(t * 0.7 + ph + f * 2.2) * f * f * 3.0 + math.sin(t * 1.9 + ph) * f * 0.4
                    px = x + sway
                    nx = x + math.sin(t * 0.7 + ph + (f + 1 / n) * 2.2) * (f + 1 / n) ** 2 * 3.0
                    ch = ")" if nx - px > 0.12 else "(" if nx - px < -0.12 else "|"
                    c = scale(col, 0.5 + 0.45 * f)
                    cv.put(px, self.floor - 0.5 - k, ch, c, level=0.3)
                    if f < 0.8:
                        cv.put(px + 1, self.floor - 0.5 - k, ch, scale(c, 0.7), level=0.3)
            elif kind == "fern" and not back:
                for leaf in range(5):
                    a = -math.pi / 2 + (leaf - 2) * 0.45 + math.sin(t * 0.8 + ph * 10 + leaf) * 0.06
                    ln = size * (0.8 + 0.25 * (leaf % 2))
                    for k in range(1, int(ln) + 1):
                        px = x + math.cos(a) * k * 0.9
                        py = self.floor - 0.5 + math.sin(a) * k / ASPECT * 1.4
                        cv.put(px, py, slope_ch(math.cos(a), math.sin(a)) if k < ln - 1 else "'",
                               scale(col, 0.7 + 0.3 * k / ln), level=0.35)
                        if 1 < k < ln - 1 and k % 2 == 0:
                            cv.put(px - 1, py, "<", scale(col, 0.8), level=0.3)
                            cv.put(px + 1, py, ">", scale(col, 0.8), level=0.3)

    def gill_paths(self, hx, hy, ang, up):
        """Three gill stalks per side, from behind the head, as lists of points (stretched)."""
        Lb = self.Lb
        t = self.t
        ca, sa = math.cos(ang), math.sin(ang)
        ux, uy = up
        perk = 0.25 if self.state in ("follow", "eat") else 0.0
        paths = []
        for k, (spread, ln) in enumerate(((1.3, 0.28), (1.8, 0.33), (2.35, 0.29))):
            base_s = (-0.03 - 0.05 * k) * Lb
            bq = (0.11 - k * 0.012) * Lb
            bx = hx + ca * base_s + ux * bq
            by = hy + sa * base_s + uy * bq
            pts = []
            a0 = spread - perk * (1 - k * 0.5) + math.sin(t * 1.8 + k * 1.1) * 0.12
            seg = 5
            for j in range(seg + 1):
                q = j / seg
                a = a0 + q * 0.45 + math.sin(t * 2.6 + k + q * 3) * 0.12 * q
                # direction: angle measured from "forward" toward "up"
                dx = ca * math.cos(a) + ux * math.sin(a)
                dy = sa * math.cos(a) + uy * math.sin(a)
                L = ln * Lb * self.gill_len * q
                pts.append((bx + dx * L, by + dy * L, dx, dy))
            paths.append(pts)
        return paths

    def draw_gills(self, cv, paths, near):
        """Each gill: a soft bright stalk (Body capsules) with a fringe of fine filaments."""
        gill = self.colors[2]
        col = gill if near else scale(gill, 0.62)
        Lb = self.Lb
        t = self.t
        # filaments first (under the stalks): little strokes swept back off both sides
        for k, pts in enumerate(paths):
            for j in range(1, len(pts)):
                x, y, dx, dy = pts[j]
                for side in (-1, 1):
                    fx, fy = -dy * side, dx * side
                    wav = math.sin(t * 3.5 + j * 1.3 + k * 2 + side) * 0.35
                    ox, oy = fx - dx * (0.7 + wav), fy - dy * (0.7 + wav)
                    on = math.hypot(ox, oy) or 1
                    ox, oy = ox / on, oy / on
                    for d, br in ((Lb * 0.05 + 1.0, 0.85), (Lb * 0.05 + 2.4, 0.6)):
                        cv.put(x + ox * d, (y + oy * d) / ASPECT, slope_ch(ox, oy),
                               scale(mix(col, (255, 255, 255), 0.2), br if near else br * 0.8), level=0.35)
        # the stalks: a soft brush stroke, dense along the middle, lighter at the sides
        for k, pts in enumerate(paths):
            for j in range(1, len(pts)):
                x0, y0, dx, dy = pts[j - 1]
                x1, y1, _, _ = pts[j]
                q = j / (len(pts) - 1)
                width = Lb * (0.025 - 0.012 * q) + 0.3
                steps = max(1, int(math.hypot(x1 - x0, y1 - y0) * 1.5))
                for st in range(steps):
                    u = st / steps
                    x, y = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
                    c = mix(col, (255, 255, 255), 0.18 * (j % 2)) if near else col
                    g = slope_ch(dx, dy)
                    cv.put(x, y / ASPECT, g, c, level=0.8 if near else 0.5)
                    if q < 0.7:   # thicker toward the base
                        cv.put(x - dy * width, (y + dx * width) / ASPECT, g, scale(c, 0.8), level=0.7 if near else 0.45)

    def draw_axolotl(self, cv):
        Lb = self.Lb
        body_c, belly_c, gill_c, eye_c, speckled = self.colors
        pts = self.chain.points
        P = [(x, y * ASPECT) for x, y in pts]      # stretched
        hx, hy = P[0]
        ang = self.chain.heading(0)
        ca, sa = math.cos(ang), math.sin(ang)
        # "up" for this body: the perpendicular that points up the screen
        ux, uy = -sa, ca
        if uy > 0:
            ux, uy = -ux, -uy
        # head center sits a little behind the chain's first point
        hcx, hcy = hx - ca * Lb * 0.06, hy - sa * Lb * 0.06
        paths = self.gill_paths(hcx, hcy, ang, (ux, uy))
        # the far-side gills peek out a little forward and above the near ones
        far_paths = [[(x + ca * 2.5 + ux * 1.5, y + sa * 2.5 + uy * 1.5, dx, dy) for x, y, dx, dy in p] for p in paths[:2]]
        self.draw_gills(cv, far_paths, near=False)
        # The body is the expensive part (every cell asks "how far from the edge?"), and the
        # axolotl moves slowly: rasterize it only when its pose changed, at most every other frame.
        key = (cv.ramp, tuple((round(x * 2), round(y * 2)) for x, y in pts), self.state == "rest",
               self.blink < 0, self.gulp > 0.25, int(self.paddle * 2) % 12 if self.state != "rest" else 0)
        self.frame = getattr(self, "frame", 0) + 1
        cached = getattr(self, "body_cache", None)
        if cached is None or (cached[0] != key and (self.frame % 2 == 0 or cached[2] != cv.ramp)):
            tmp = Canvas(cv.w, cv.h, cv.ramp)
            self.paint_body(tmp, P, pts, ang, ca, sa, ux, uy, hx, hy, hcx, hcy)
            xs = [x for x, _ in pts]
            ys = [y for _, y in pts]
            m = Lb * 0.35
            x0, x1 = max(0, int(min(xs) - m)), min(cv.w, int(max(xs) + m) + 1)
            y0, y1 = max(0, int(min(ys) - m / ASPECT)), min(cv.h, int(max(ys) + m / ASPECT) + 1)
            cells = []
            W = cv.w
            for y in range(y0, y1):
                for x in range(x0, x1):
                    i = y * W + x
                    if tmp.ch[i] != " " and tmp.fg[i] is not None:
                        cells.append((i, tmp.ch[i], tmp.fg[i], tmp.lv[i]))
            cached = self.body_cache = (key, cells, cv.ramp)
        ch, fg, lv, bc = cv.ch, cv.fg, cv.lv, cv.bc
        for i, c, f, l in cached[1]:
            if i < cv.n:
                ch[i], fg[i], lv[i], bc[i] = c, f, l, f
        self.draw_gills(cv, paths, near=True)

    def paint_body(self, cv, P, pts, ang, ca, sa, ux, uy, hx, hy, hcx, hcy):
        Lb = self.Lb
        body_c, belly_c, gill_c, eye_c, speckled = self.colors
        n = len(pts)
        rest = self.state == "rest"

        def leg(i_seg, front, near):
            sx, sy = P[i_seg]
            phase = self.paddle + (0 if front else math.pi) + (0 if near else math.pi / 2)
            if rest:
                la = math.pi / 2 + (0.35 if front else -0.35) * (1 if ca > 0 else -1)
                dx, dy = math.cos(la) * 0.3 * ca + (-ux) * 1.0, (-uy) * 1.0
            else:
                sw = math.sin(phase) * 0.8
                dx = -ux * 0.7 + ca * (sw - 0.5)
                dy = -uy * 0.7 + sa * (sw - 0.5)
            dn = math.hypot(dx, dy) or 1
            dx, dy = dx / dn, dy / dn
            r = Lb * 0.08 * self.chubby
            bx, by = sx - ux * r * 0.6, sy - uy * r * 0.6
            ln = Lb * 0.14
            ex, ey = bx + dx * ln, by + dy * ln
            return (bx, by / ASPECT, ex, ey / ASPECT, Lb * 0.035, Lb * 0.028)

        legs = [leg(2, True, False), leg(6, False, False)]
        far = Body(blend=0.3)
        for x0, y0, x1, y1, r0, r1 in legs:
            far.capsule(x0, y0, x1, y1, r0, r1, color=scale(body_c, 0.7))
        far.draw(cv, depth=0.4, edge=0.7)
        # the fin: a soft, see-through ribbon along the back half and tail
        # the fin: a see-through membrane along the back half and tail, with a light rim
        fin_c = mix(body_c, (255, 255, 255), 0.35)
        for i in range(4, n - 1):
            ax_, ay_ = P[i]
            bx_, by_ = P[i + 1]
            tx, ty = bx_ - ax_, by_ - ay_
            tn = math.hypot(tx, ty) or 1
            nx_, ny_ = -ty / tn, tx / tn
            rim = slope_ch(tx, ty)
            for st in range(3):
                u = st / 3
                f = (i + u - 4) / max(1, n - 5)
                x, y = ax_ + tx * u, ay_ + ty * u
                hf = Lb * (0.09 + 0.06 * math.sin(math.pi * clamp(f * 1.15))) * (1 - f * 0.45)
                for side in (-1, 1):
                    for d in range(int(Lb * 0.05), int(hf) + 1):
                        edge_ = d >= int(hf)
                        cv.put(x + nx_ * side * d, (y + ny_ * side * d) / ASPECT, rim if edge_ else ".",
                               scale(fin_c, 0.75 if edge_ else 0.45), level=0.3)
        # body and tail
        radii = []
        for i in range(n):
            f = i / (n - 1)
            if f < 0.12:
                r = 0.065 + 0.1 * f            # a little neck behind the big head
            elif f < 0.4:
                r = 0.078
            else:
                r = 0.078 * (1 - (f - 0.4) / 0.6) ** 1.1 + 0.008
            radii.append(r * Lb * self.chubby)
        for g in range(1, n - 1, 3):
            b = Body(blend=1.0)
            segs = list(range(g, min(n - 1, g + 3)))
            for i in segs:
                b.capsule(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], radii[i], radii[i + 1], color=body_c)

            def pattern(px, py, j, inside, segs=segs):
                i = segs[min(j, len(segs) - 1)]
                ax_, ay_ = pts[i][0], pts[i][1] * ASPECT
                bx_, by_ = pts[i + 1][0], pts[i + 1][1] * ASPECT
                tx, ty = bx_ - ax_, by_ - ay_
                tn = math.hypot(tx, ty) or 1
                nx_, ny_ = -ty / tn, tx / tn       # this segment's own "down" side
                if ny_ < 0:
                    nx_, ny_ = -nx_, -ny_
                if (px - ax_) * nx_ + (py * ASPECT - ay_) * ny_ > radii[i] * 0.45:
                    return belly_c
                if speckled and cellhash(int(px), int(py), 5) > 0.55:
                    return scale(body_c, 0.55)
                return None
            b.draw(cv, depth=1.0, pattern=pattern, edge=0.9, ambient=0.62)
        # the head: broad and round, with a wide smile
        head = Body(blend=0.9)
        hr = Lb * 0.16 * self.chubby
        head.ellipse(hcx, hcy / ASPECT, hr * 1.3, hr, ang, color=body_c)
        head.circle(hx + ca * Lb * 0.03 - ux * Lb * 0.01, (hy + sa * Lb * 0.03 - uy * Lb * 0.01) / ASPECT,
                    hr * 0.78, color=body_c)
        # eye: on the upper front of the head
        ex = hcx + ca * hr * 0.55 + ux * hr * 0.35
        ey = hcy + sa * hr * 0.55 + uy * hr * 0.35
        closed = self.blink < 0 or (rest and int(self.t * 0.3) % 3 == 0 and self.blink < 1.2)
        head.spot(ex, ey / ASPECT, max(0.25, hr * 0.12), eye_c, "-" if closed else ("@" if hr > 4 else "o"))
        # smile: a curve under the snout, from the tip back toward the cheek
        mouth_open = self.gulp > 0.25
        smile_col = scale(mix(body_c, (120, 40, 60), 0.55), 1.0)
        for k in range(5):
            u = k / 4
            sxp = hcx + ca * hr * (1.05 - u * 0.75) - ux * hr * (0.3 - 0.18 * u * u)
            syp = hcy + sa * hr * (1.05 - u * 0.75) - uy * hr * (0.3 - 0.18 * u * u)
            head.spot(sxp, syp / ASPECT, 0.1, smile_col if not mouth_open else (90, 20, 40),
                      ("O" if mouth_open and k == 0 else "_") if k < 4 else (")" if ca > 0 else "("))
        head.draw(cv, depth=1.0, edge=0.9, ambient=0.66,
                  pattern=lambda px, py, i, inside: belly_c if (
                      (px - hcx) * ux + (py * ASPECT - hcy) * uy < -hr * 0.55) else None)
        # cheek blush for the pale morphs
        if self.morph in ("leucistic", "albino", "golden"):
            bx = hcx - ca * hr * 0.05 - ux * hr * 0.05
            by = hcy - sa * hr * 0.05 - uy * hr * 0.05
            cv.put(bx, by / ASPECT, "·", mix(gill_c, (255, 255, 255), 0.3), level=0.9)
        near = Body(blend=0.3)
        for x0, y0, x1, y1, r0, r1 in (leg(2, True, True), leg(6, False, True)):
            near.capsule(x0, y0, x1, y1, r0, r1, color=mix(body_c, (255, 255, 255), 0.1))
        near.draw(cv, depth=1.0, edge=0.7)

    def bake_background(self, ramp):
        w, h = self.w, self.h
        rng = random.Random(self.bg_seed)
        cv = Canvas(w, h, ramp)
        fl = self.floor
        # deep water: faint motes, darker toward the bottom
        for y in range(int(self.top) + 1, int(fl)):
            f = (y - self.top) / max(1, fl - self.top)
            for x in range(w):
                if cellhash(x, y, 3) > 0.9:
                    cv.put(x, y, ".", gradient([(90, 160, 200), (40, 90, 130)], f), level=0.1)
        # sand and gravel
        sand = rng.choice([(200, 180, 140), (170, 150, 120), (120, 115, 110), (215, 200, 170)])
        for y in range(int(fl), h):
            for x in range(w):
                n = cellhash(x, y, 9)
                if n > -0.5:
                    c = mix(sand, (255, 255, 255), 0.1 * n)
                    ch = "o" if n > 0.92 else "." if n < 0.3 else ":" if n < 0.7 else ","
                    if n > 0.92:
                        c = hsv(rng.random(), 0.25, 0.7)
                    cv.put(x, y, ch, scale(c, 0.55 + 0.25 * (y - fl) / max(1, h - fl)), level=0.2)
        # a few rocks / a terracotta hide
        for _ in range(rng.randint(1, 3)):
            rx, rr = rng.uniform(0, w), rng.uniform(2, 4.5) * max(0.8, h / 35)
            rock = Body(blend=0.6)
            rock.ellipse(rx, fl - rr * 0.25 / ASPECT, rr * 1.3, rr * 0.7, 0, color=rng.choice([(130, 125, 120), (110, 100, 95), (150, 140, 125)]))
            rock.draw(cv, depth=0.3, ambient=0.5)
        if rng.random() < 0.6:
            px = rng.uniform(0.15, 0.85) * w
            pr = max(3.0, self.Lb * 0.18)
            for k in range(40):
                a = math.pi + k / 39 * math.pi
                x = px + math.cos(a) * pr
                y = fl - 0.3 + math.sin(a) * pr / ASPECT
                cv.put(x, y, "(" if math.cos(a) < -0.5 else ")" if math.cos(a) > 0.5 else "_", (200, 110, 70), level=0.5)
                cv.put(x + 0.7 * math.cos(a), y + 0.4 * math.sin(a), ".", (150, 80, 50), level=0.3)
        for kind, x, size, ph, col in self.plants:
            if kind == "moss":
                mb = Body()
                mb.circle(x, fl - size / ASPECT, size, color=col)
                mb.draw(cv, depth=0.7, ambient=0.5)
        # the glass: faint panes at the sides
        for y in range(int(self.top), h):
            cv.put(0, y, "|", (90, 120, 140), level=0.3)
            cv.put(w - 1, y, "|", (90, 120, 140), level=0.3)
        return cv
