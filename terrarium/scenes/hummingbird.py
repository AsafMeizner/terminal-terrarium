"""A hummingbird hovering and darting between trumpet flowers.

The bird is a little rig in body coordinates (ellipse body, round head, fanned tail, long beak)
rotated by its pitch and mirrored by its facing. Wings beat far faster than the frame rate, so
they are drawn the way the eye sees them: a fan of faint strokes, densest at the ends of the
stroke where the wing slows, plus one sharp stroboscopic position. The gorget is iridescent: it
looks almost black until the angle is right, then blazes up.
"""
import math

from ..engine import ASPECT, Scene, clamp, hsv, mix, noise1, scale, smoothstep

TAU = math.tau
PI = math.pi

FLOWER_HUES = {"red": 0.995, "orange": 0.06, "pink": 0.93, "purple": 0.8, "yellow": 0.13}
# back colour, belly colour, gorget hue, tail colour
SPECIES = [
    ((60, 200, 110), (215, 225, 210), 0.98, (40, 80, 60)),     # ruby-throat
    ((70, 210, 140), (190, 200, 190), 0.9, (50, 90, 70)),      # Anna's (magenta)
    ((230, 120, 50), (245, 215, 185), 0.06, (210, 100, 40)),   # rufous
    ((50, 190, 200), (200, 220, 225), 0.75, (40, 70, 110)),    # violet-ear
    ((120, 220, 90), (225, 230, 200), 0.55, (60, 90, 50)),     # sapphire throat
]


def _dir_ch(dx, dy):
    """Line glyph for a direction with dy in rows (down positive)."""
    ax, ay = abs(dx), abs(dy * ASPECT)
    if ax > 1.7 * ay:
        return "-"
    if ay > 1.7 * ax:
        return "|"
    return "\\" if dx * dy > 0 else "/"


class Trumpet:
    """One tubular flower hanging off a plant; geometry is refreshed from the plant every frame."""

    def __init__(self, plant, at, side, ang, length, rad, col):
        self.plant = plant
        self.at = at          # 0..1 position along the stem
        self.side = side
        self.ang0 = ang       # axis angle from horizontal (y up), already sided
        self.L = length
        self.r = rad
        self.col = col
        self.busy = None
        self.x = self.y = 0.0
        self.ax, self.ay = 1.0, 0.0
        self.pulse = 0.0


class Plant:
    def __init__(self, rng, kind, x0, y0, height, lean, cols, L):
        self.kind = kind      # "spike" grows up from the ground, "vine" hangs from the top
        self.x0, self.y0 = x0, y0
        self.H = height
        self.lean = lean
        self.phase = rng.uniform(0, TAU)
        self.flowers = []
        n = rng.randint(2, 4)
        for k in range(n):
            at = 0.5 + 0.5 * (k + rng.uniform(0.2, 0.7)) / n
            side = rng.choice((-1, 1)) if kind == "vine" else (1 if k % 2 else -1)
            if kind == "spike":
                ang = rng.uniform(-0.35, 0.2)
            else:
                ang = rng.uniform(-0.75, -0.4)
            self.flowers.append(Trumpet(self, at, side, ang, L * rng.uniform(1.15, 1.4), L * rng.uniform(0.55, 0.65),
                                        rng.choice(cols)))
        self.leaves = [(rng.uniform(0.1, 0.9), rng.choice((-1, 1)), rng.uniform(0.6, 1.2)) for _ in range(rng.randint(0, 2))]
        self.sway = 0.0

    def point(self, s):
        """Stem point at s (0 base .. 1 tip) in cell coords."""
        sw = self.sway * s * s
        if self.kind == "spike":
            x = self.x0 + (self.lean * s * s + sw) * self.H * 0.35
            y = self.y0 - s * self.H / ASPECT
        else:
            x = self.x0 + (self.lean * s + sw) * self.H * 0.3
            y = self.y0 + s * self.H / ASPECT * (1 - 0.15 * s)
        return x, y


class Bird:
    def __init__(self, scene, sp, L, enter_side):
        rng = scene.rng
        self.L = L
        back, belly, ghue, tail = sp
        j = lambda c: tuple(clamp(v + rng.uniform(-15, 15), 0, 255) for v in c)
        self.back, self.belly, self.tailc = j(back), j(belly), j(tail)
        self.ghue = ghue + rng.uniform(-0.03, 0.03)
        self.beak = rng.uniform(0.85, 1.1)
        self.curve = rng.uniform(-0.12, 0.05)
        self.rate = rng.uniform(0.8, 1.2)
        self.face = -enter_side
        self.x = scene.w / 2 + enter_side * (scene.w / 2 + L * 4)
        self.y = rng.uniform(scene.h * 0.25, scene.h * 0.5)
        self.alpha = 0.5
        self.state = "dart"
        self.flower = None
        self.timer = 0.0
        self.sx = self.sy = 0.0
        self.tx = self.ty = 0.0
        self.dur = 1.0
        self.prog = 1.0
        self.glint_seed = rng.uniform(0, 100)
        self.wphase = rng.uniform(0, TAU)
        self.leaving = False
        self.dip = 0.0
        self.turn = 0.0


class Hummingbird(Scene):
    name = "hummingbird"
    title = "Hummingbird"
    blurb = "a hummingbird hovers and darts between trumpet flowers, its throat flashing in the light"
    tags = ("nature", "creatures", "flowers", "calm")
    options = {
        "birds": (0, "number of hummingbirds: 1 or 2 (0 = random, a visitor sometimes drops by)"),
        "flower": ("random", "random, red, orange, pink, purple, yellow or mixed"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        big = min(w, h * ASPECT)
        self.L = L = clamp(big * rng.uniform(0.115, 0.135), 2.6, 14.0)
        fc = self.opt("flower")
        if fc == "random":
            fc = rng.choice(list(FLOWER_HUES) + ["mixed", "mixed"])
        if fc in FLOWER_HUES:
            hues = [FLOWER_HUES[fc] + rng.uniform(-0.02, 0.02) for _ in range(3)]
        else:
            h0 = rng.random()
            hues = [h0, h0 + rng.uniform(0.08, 0.2), rng.choice(list(FLOWER_HUES.values()))]
        cols = [hsv(hh, rng.uniform(0.7, 0.9), 1.0) for hh in hues]
        # plants: spikes from the ground and vines from the top, spread across the width
        self.plants = []
        n = max(2, min(5, int(w / max(18.0, L * 6.5))))
        slots = [(k + rng.uniform(0.2, 0.8)) / n * w for k in range(n)]
        for x in slots:
            kind = "spike" if rng.random() < 0.65 else "vine"
            if kind == "spike":
                H = rng.uniform(0.45, 0.8) * h * ASPECT
                p = Plant(rng, kind, x, h - 1, H, rng.uniform(-0.25, 0.25), cols, L)
            else:
                H = rng.uniform(0.35, 0.6) * h * ASPECT
                p = Plant(rng, kind, x, -1, H, rng.uniform(-0.3, 0.3), cols, L)
            self.plants.append(p)
        self.trumpets = [f for p in self.plants for f in p.flowers]
        self.update_plants()
        # birds
        nb = self.opt("birds")
        self.max_birds = nb if nb in (1, 2) else (2 if rng.random() < 0.35 else 1)
        self.visitor = nb == 0
        self.species = rng.sample(SPECIES, 2)
        self.birds = [Bird(self, self.species[0], L, rng.choice((-1, 1)))]
        b = self.birds[0]
        b.x, b.y = rng.uniform(0.3, 0.7) * w, rng.uniform(0.3, 0.5) * h
        self.choose(b)
        self.visit_timer = rng.uniform(10, 25)
        self.pollen = []
        # backdrop: dark broad leaves, baked once
        self.bake_backdrop()

    def bake_backdrop(self):
        rng = self.rng
        w, h = self.w, self.h
        self.bg = {}
        tone = hsv(rng.uniform(0.28, 0.45), rng.uniform(0.4, 0.7), 1.0)
        glow_x, glow_y = rng.uniform(0.2, 0.8) * w, rng.uniform(0.1, 0.4) * h
        glow_c = hsv(rng.uniform(0.05, 0.15) if rng.random() < 0.6 else rng.uniform(0.5, 0.65), 0.5, 1.0)
        rad = max(w, h * ASPECT) * rng.uniform(0.35, 0.55)
        for y in range(h):
            for x in range(w):
                d = math.hypot(x + 0.5 - glow_x, (y + 0.5 - glow_y) * ASPECT) / rad
                if d < 1:
                    k = (1 - d) ** 2
                    n = noise1(x * 0.15 + y * 0.9, 3)
                    if k * (0.7 + 0.3 * n) > 0.18:
                        c = scale(mix(glow_c, tone, d), 0.05 + 0.22 * k * (0.75 + 0.25 * n))
                        self.bg[y * w + x] = ("░", (int(c[0]) & ~3, int(c[1]) & ~3, int(c[2]) & ~3), 0.05)
        # a soft glow of distant light behind the leaves
        self.glow = (glow_x, glow_y, glow_c)

    # ------------------------------------------------------------------ plants & targets
    def update_plants(self):
        t = self.t
        for p in self.plants:
            p.sway = 0.08 * math.sin(t * 0.5 + p.phase) + 0.05 * noise1(t * 0.3 + p.phase * 3)
            for f in p.flowers:
                x, y = p.point(f.at)
                a = f.ang0 + p.sway * 0.6
                f.ax, f.ay = math.cos(a) * f.side, math.sin(a)
                # the flower hangs on a short pedicel off the stem
                f.x = x + f.ax * f.L * 0.15
                f.y = y - f.ay * f.L * 0.15 / ASPECT
                f.pulse = max(0.0, f.pulse - 0.02)

    def pose_for(self, b, f, depth):
        """Body position, facing and pitch so the beak tip sits `depth` inside flower f's mouth."""
        L = b.L
        mx = f.x + f.ax * f.L
        my = f.y - f.ay * f.L / ASPECT
        bdx, bdy = -f.ax, -f.ay          # beak direction (y up)
        face = 1 if bdx > 0 else -1
        ang = math.atan2(bdy, bdx * face)  # in the facing frame
        beta = -1.0 + b.curve
        alpha = clamp(ang - beta, 0.35, 1.9)
        tipx = mx + bdx * depth * f.L
        tipy = my - bdy * depth * f.L / ASPECT
        # head centre is 1.05 along the axis; beak starts 0.4 in front of it
        hx = math.cos(alpha) * 1.05
        hy = math.sin(alpha) * 1.05
        bx = math.cos(alpha + beta) * (0.4 + b.beak)
        by = math.sin(alpha + beta) * (0.4 + b.beak)
        px = tipx - (hx + bx) * L * face
        py = tipy + (hy + by) * L / ASPECT
        return px, py, face, alpha

    def choose(self, b):
        rng = self.rng
        free = [f for f in self.trumpets if f.busy is None and f is not b.flower and self.reachable(f)]
        if b.flower is not None:
            b.flower.busy = None
        if not free or rng.random() < 0.12:
            b.flower = None
            b.tx = clamp(b.x + rng.uniform(-0.3, 0.3) * self.w, b.L * 2, self.w - b.L * 2)
            b.ty = clamp(rng.uniform(0.2, 0.6) * self.h, 2, self.h - 3)
            b.mode_after = "look"
        else:
            near = sorted(free, key=lambda f: abs(f.x - b.x) + abs(f.y - b.y) * 2 + rng.uniform(0, self.w * 0.5))
            f = near[0]
            f.busy = b
            b.flower = f
            px, py, face, alpha = self.pose_for(b, f, -0.9)
            b.tx, b.ty = px, py
            b.face_to = face
            b.mode_after = "hover"
        b.sx, b.sy = b.x, b.y
        d = math.hypot(b.tx - b.x, (b.ty - b.y) * ASPECT)
        b.dur = clamp(d / (b.L * 9), 0.35, 1.1)
        b.prog = 0.0
        b.state = "dart"

    def reachable(self, f):
        """The bird must fit on screen while feeding there."""
        L = self.L
        mx = f.x + f.ax * f.L
        bx = mx + f.ax * L * 2.8
        return L < bx < self.w - L and 2 < mx < self.w - 2 and 1 < f.y < self.h - 2

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.1)
        rng = self.rng
        self.update_plants()
        for b in list(self.birds):
            b.wphase += dt * 47.0 * b.rate
            b.turn = max(0.0, b.turn - dt * 3)
            if b.state == "dart":
                b.prog = min(1.0, b.prog + dt / b.dur)
                e = smoothstep(0, 1, b.prog)
                b.x = b.sx + (b.tx - b.sx) * e
                b.y = b.sy + (b.ty - b.sy) * e - math.sin(b.prog * math.pi) * b.L * 0.25
                want = 1 if b.tx > b.sx else -1
                if abs(b.tx - b.sx) > b.L * 0.5 and b.face != want and b.prog < 0.5:
                    b.face = want
                    b.turn = 1.0
                b.alpha += (0.35 - b.alpha) * min(1, dt * 8) if b.prog < 0.7 else (0.9 - b.alpha) * min(1, dt * 6)
                if b.prog >= 1.0:
                    if b.leaving:
                        self.birds.remove(b)
                        if b.flower is not None:
                            b.flower.busy = None
                        continue
                    b.state = b.mode_after
                    b.timer = rng.uniform(0.3, 0.8) if b.state == "hover" else rng.uniform(1.0, 2.5)
            elif b.state in ("hover", "feed", "back"):
                f = b.flower
                if f is None:
                    b.state = "look"
                    continue
                depth = {"hover": -0.9, "back": -0.9}.get(b.state, 0.12 + 0.1 * math.sin(self.t * 5.0) + b.dip)
                px, py, face, alpha = self.pose_for(b, f, depth)
                if b.face != face:
                    b.face = face
                    b.turn = 1.0
                k = min(1.0, dt * (10 if b.state == "feed" else 6))
                b.x += (px - b.x) * k
                b.y += (py - b.y) * k + math.sin(self.t * 7 + b.glint_seed) * 0.02
                b.alpha += (alpha - b.alpha) * k
                b.timer -= dt
                if b.state == "feed":
                    f.pulse = 1.0
                    if rng.random() < dt * 6:
                        mx = f.x + f.ax * f.L * 1.05
                        my = f.y - f.ay * f.L * 1.05 / ASPECT
                        self.pollen.append([mx, my, f.ax * rng.uniform(0.5, 2) + rng.uniform(-1, 1),
                                            rng.uniform(-0.8, 0.3), rng.uniform(1.0, 2.5), rng.uniform(0, TAU)])
                if b.timer <= 0:
                    if b.state == "hover":
                        b.state = "feed"
                        b.timer = rng.uniform(1.4, 3.2)
                        b.dip = rng.uniform(-0.05, 0.08)
                    elif b.state == "feed":
                        b.state = "back"
                        b.timer = rng.uniform(0.25, 0.5)
                    else:
                        self.next_move(b)
            elif b.state == "look":
                b.y += math.sin(self.t * 2.3 + b.glint_seed) * dt * 0.6
                b.alpha += (0.95 - b.alpha) * min(1, dt * 4)
                b.timer -= dt
                if rng.random() < dt * 0.9:
                    b.face = -b.face
                    b.turn = 1.0
                if b.timer <= 0:
                    self.next_move(b)
        # a visitor drops by now and then (or stays, with birds=2)
        if self.max_birds == 2 and len(self.birds) < 2:
            self.visit_timer -= dt
            if self.visit_timer <= 0:
                side = rng.choice((-1, 1))
                nb = Bird(self, self.species[1], self.L * rng.uniform(0.85, 1.0), side)
                nb.visits = rng.randint(2, 5) if self.visitor else 10 ** 6
                self.birds.append(nb)
                self.choose(nb)
                self.visit_timer = rng.uniform(15, 35)
        alive = []
        for p in self.pollen:
            p[4] -= dt
            if p[4] > 0:
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[3] += 0.25 * dt
                alive.append(p)
        self.pollen = alive[-200:]

    def next_move(self, b):
        visits = getattr(b, "visits", None)
        if visits is not None:
            b.visits -= 1
            if b.visits <= 0:
                if b.flower is not None:
                    b.flower.busy = None
                    b.flower = None
                side = 1 if b.x > self.w / 2 else -1
                b.sx, b.sy = b.x, b.y
                b.tx, b.ty = self.w / 2 + side * (self.w / 2 + b.L * 6), b.y - self.h * 0.2
                b.dur, b.prog, b.state, b.leaving = 0.9, 0.0, "dart", True
                return
        self.choose(b)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h = self.w, self.h
        t = self.t
        gx, gy, gc = self.glow
        for i, (ch, col, v) in self.bg.items():
            cv.ch[i] = ch
            cv.fg[i] = col
            cv.lv[i] = v
        for p in self.plants:
            self.draw_plant(cv, p)
        for f in self.trumpets:
            self.draw_trumpet(cv, f)
        for p in self.pollen:
            tw = 0.5 + 0.5 * math.sin(t * 11 + p[5])
            v = min(1.0, p[4]) * (0.35 + 0.5 * tw)
            ch = "*" if v > 0.6 else "+" if v > 0.42 else "·" if v > 0.25 else "."
            cv.put(p[0], p[1], ch, scale((255, 225, 120), 0.4 + 0.6 * v), level=v)
        for b in self.birds:
            self.draw_bird(cv, b)

    def draw_plant(self, cv, p):
        """A thin, graceful stem with one or two small leaves."""
        n = max(3, int(p.H / ASPECT * 1.3))
        stem = (60, 120, 70) if p.kind == "spike" else (80, 110, 60)
        px, py = p.point(0)
        for k in range(1, n + 1):
            s = k / n
            x, y = p.point(s)
            cv.put(x, y, _dir_ch(x - px, y - py), scale(stem, 0.5 + 0.3 * s), level=0.3)
            px, py = x, y
        up = 1 if p.kind == "spike" else -1
        tip_ch = "'" if up > 0 else ","
        for at, side, sz in p.leaves:
            x, y = p.point(at)
            ln = max(2, int(self.L * 0.5 * sz))
            for k in range(1, ln + 1):
                q = k / ln
                ch = "_" if q < 0.4 else ("~" if q < 0.85 else tip_ch)
                cv.put(x + side * k, y - up * (q > 0.6) * 0.6, ch, scale((70, 150, 80), 0.45 + 0.3 * math.sin(q * PI)),
                       level=0.3)

    def draw_trumpet(self, cv, f):
        """A slender tube that flares into a five-lobed mouth. Few glyph levels: a bright rim,
        a deeper fill, a pale lobed lip and a dark throat."""
        h, w = self.h, self.w
        ax, ay = f.ax, f.ay
        L, R = f.L, f.r
        x0, y0 = f.x, f.y
        Rm = R * 1.35
        ext = L * 1.1 + Rm
        k = 1.0 + 0.25 * f.pulse
        col = f.col
        rim_c = scale(mix(col, (255, 245, 235), 0.2), k)
        fill_c = scale(mix(col, (70, 0, 40), 0.35), 0.8 * k)
        lip_c = scale(mix(col, (255, 250, 245), 0.45), k)
        tube_ch = "=" if abs(ay) < 0.45 else _dir_ch(ax, -ay / ASPECT)
        along_ch = _dir_ch(ax, -ay / ASPECT)
        across_ch = _dir_ch(-ay, -ax / ASPECT)
        if abs(ax) > abs(ay) * 1.2:
            tip_ch = ")" if ax > 0 else "("
        else:
            tip_ch = "v" if ay < 0 else "^"
        cal = (90, 160, 80)
        for y in range(max(0, int(y0 - ext / ASPECT) - 1), min(h, int(y0 + ext / ASPECT) + 2)):
            dy = -(y + 0.5 - y0) * ASPECT
            for x in range(max(0, int(x0 - ext) - 1), min(w, int(x0 + ext) + 2)):
                dx = x + 0.5 - x0
                u = (dx * ax + dy * ay) / L               # along the tube 0..1
                if u < 0.0 or u > 1.1:
                    continue
                p = -dx * ay + dy * ax                    # across, units
                ap = abs(p)
                if u < 0.9:
                    r = max(0.5, R * (0.16 + 0.84 * smoothstep(0.5, 0.92, u) ** 1.6))
                    if ap > r:
                        continue
                    if u < 0.12:
                        cv.put(x, y, tube_ch, cal, level=0.6)
                    elif r < 1.2:
                        cv.put(x, y, tube_ch, rim_c, level=0.6)
                    elif ap > r - 0.8:
                        cv.put(x, y, along_ch, rim_c, level=0.7)
                    else:
                        cv.put(x, y, ":", fill_c, level=0.6)
                    continue
                # the mouth: five lobes across the opening, each with a rounded edge
                s = p / Rm
                if abs(s) > 1.0:
                    continue
                lob = (s + 1.0) * 2.5                     # 0..5 across the five lobes
                fr = lob - int(lob) - 0.5
                edge = 0.9 + 0.13 * math.cos(fr * PI) * (1 - 0.3 * s * s)
                if u > edge:
                    continue
                if abs(s) < 0.32 and u < edge - 0.04:
                    cv.put(x, y, ".", (70, 20, 40), level=0.7)       # the dark throat
                elif u > edge - 0.06 and abs(fr) < 0.3:
                    cv.put(x, y, tip_ch, scale(lip_c, 1.15), level=0.9)   # lobe tips
                else:
                    cv.put(x, y, across_ch, lip_c, level=0.8)

    def draw_bird(self, cv, b):
        """Clean silhouette: wing blur behind, a dark margin cut round the body, then a rounded
        body with few glyph levels, a bright gorget, a thin beak and a fanned tail."""
        L = b.L
        t = self.t
        w, h = self.w, self.h
        face = b.face
        al = b.alpha
        ca, sa = math.cos(al), math.sin(al)
        beta = -1.0 + b.curve
        # iridescent gorget: always jewel-bright, blazing and shifting hue when the angle is right
        g = math.sin(t * 0.9 + b.glint_seed) * 0.6 + math.sin(t * 2.3 + b.glint_seed * 2) * 0.4 + b.turn * 1.2
        flash = clamp((g + 0.15) * 1.6)
        gorget = hsv(b.ghue + 0.05 * math.sin(t * 1.7 + b.glint_seed) - 0.04 * flash, 0.9 - 0.25 * flash,
                     0.7 + 0.3 * flash)
        sheen = 0.5 + 0.5 * math.sin(t * 1.3 + b.glint_seed)
        # wings first: a faint fan behind the bird, plus one strobed blade
        shx = b.x + (ca * 0.3 - sa * 0.32) * L * face
        shy = b.y - (sa * 0.3 + ca * 0.32) * L / ASPECT
        darting = b.state == "dart" and 0.1 < b.prog < 0.9
        a0, a1 = (al + 0.45, al + 1.75) if not darting else (al + 0.9, al + 1.7)
        wl = 1.6 * L
        wing_col = mix(b.back, (200, 220, 235), 0.6)
        nf = 6
        for k in range(nf):
            q = k / (nf - 1)
            edge = abs(2 * q - 1)
            self.blade(cv, shx, shy, a0 + (a1 - a0) * q, wl, face, 0.1 + 0.16 * edge ** 3, wing_col)
        sp = 0.5 + 0.5 * math.sin(b.wphase)
        self.blade(cv, shx, shy, a0 + (a1 - a0) * sp, wl, face, 0.34, wing_col)
        # classify silhouette cells
        ext = L * 2.4
        x0, x1 = max(0, int(b.x - ext)), min(w, int(b.x + ext) + 1)
        y0, y1 = max(0, int(b.y - ext / ASPECT)), min(h, int(b.y + ext / ASPECT) + 1)
        tail_tau = -0.3 + 0.12 * math.sin(t * 3 + b.glint_seed)
        tc, ts = math.cos(tail_tau), math.sin(tail_tau)
        tail_ch = _dir_ch(-math.cos(al + tail_tau) * face, math.sin(al + tail_tau) / ASPECT)
        cells = {}
        eye = None
        inv = 1.0 / L
        for y in range(y0, y1):
            wy = -(y + 0.5 - b.y) * ASPECT * inv
            for x in range(x0, x1):
                wx = (x + 0.5 - b.x) * inv * face
                u = wx * ca + wy * sa                      # along the body, toward the head
                v = -wx * sa + wy * ca                     # + is the back
                hu, hv = u - 1.05, v - 0.05
                hd = math.sqrt(hu * hu + hv * hv) / 0.5
                if hd < 1.0:
                    if abs(hu - 0.16) < 0.12 and abs(hv - 0.12) < 0.13:
                        eye = (x, y)
                    reg = "throat" if (hv < -0.12 and hu > -0.35) else "crown"
                    cells[(x, y)] = (reg, hd)
                    continue
                if -0.9 < u < 1.1:
                    lim = (1 - (u / 1.1) ** 4) if u > 0 else (1 - (u / 0.9) ** 2)
                    bw = 0.62 * (1 - 0.12 * u) * max(0.0, lim) ** 0.5
                    if abs(v) < bw:
                        e = abs(v) / bw
                        reg = "back" if v > 0.05 else ("throat" if u > 0.7 else "belly")
                        cells[(x, y)] = (reg, e)
                        continue
                ru, rv = u + 0.7, v + 0.02
                tu = ru * tc + rv * ts
                tv = -ru * ts + rv * tc
                if -0.9 < tu < 0:
                    spread = 0.1 + 0.24 * (-tu / 0.9)
                    if abs(tv) < spread:
                        cells[(x, y)] = ("tip" if tu < -0.74 else "tail", abs(tv) / spread)
        # cut a dark margin so the bird stands clear of flowers and wing blur
        for (x, y) in cells:
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (x + ox, y + oy)
                if q not in cells and 0 <= q[0] < w and 0 <= q[1] < h:
                    i = q[1] * w + q[0]
                    cv.ch[i] = " "
                    cv.fg[i] = None
                    cv.lv[i] = 0.0
        back = mix(b.back, (255, 245, 150), 0.3 * sheen)
        for (x, y), (reg, e) in cells.items():
            k = 1.0 - 0.3 * e * e
            if reg == "crown":
                ch, c = "@", mix(back, (255, 255, 220), 0.15 * (1 - e))
            elif reg == "back":
                ch, c = "#", back
            elif reg == "throat":
                ch, c, k = "@", gorget, 1.0 - 0.15 * e
            elif reg == "belly":
                ch, c = "%", b.belly
            elif reg == "tail":
                ch, c, k = tail_ch, b.tailc, 0.85
            else:
                ch, c, k = ("v" if e > 0.4 else tail_ch), mix(b.tailc, (250, 250, 250), 0.8), 0.9
            cv.put(x, y, ch, scale(c, k), level=1.0)
        if eye:
            ex, ey = eye
            cv.put(ex, ey, "o", (10, 10, 14), level=1.0)
            cv.put(ex - face, ey, ".", (250, 250, 250), level=1.0)
        # beak: one clean thin line
        bl = (0.42 + b.beak) * L
        sx = b.x + (ca * 1.05 + math.cos(al + beta) * 0.46) * L * face
        sy = b.y - (sa * 1.05 + math.sin(al + beta) * 0.46) * L / ASPECT
        bdx, bdy = math.cos(al + beta) * face, -math.sin(al + beta) / ASPECT
        n = max(2, int(bl * 1.1))
        ch = _dir_ch(bdx, bdy)
        for k in range(n + 1):
            q = k / n
            cv.put(sx + bdx * bl * q, sy + bdy * bl * q, ch, scale((215, 205, 190), 1 - 0.3 * q), level=1.0)

    def blade(self, cv, sx, sy, a, length, face, val, col):
        dx, dy = math.cos(a) * face, -math.sin(a) / ASPECT
        ch = _dir_ch(dx, dy)
        n = max(2, int(length * 1.05))
        w = cv.w
        for k in range(1, n + 1):
            q = k / n
            vv = val * (1.0 - 0.3 * q)
            x, y = int(sx + dx * length * q), int(sy + dy * length * q)
            if 0 <= x < w and 0 <= y < cv.h and cv.lv[y * w + x] < vv:
                cv.put(x, y, ch, scale(col, 0.3 + 0.7 * vv), level=vv)
