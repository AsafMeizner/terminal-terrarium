"""A cat asleep on a cushion by the window. Point at it and it wakes up and watches; click to pet it.

The cat is a handful of round parts (a QuickBody: shapes.Body with a faster draw): a big oval body,
a haunch, a round head with two cone ears, a muzzle, and a tail that wraps around the front. The
rules are tiny: breathe (the body swells and sinks), flick the tail tip, twitch an ear, puff a
"z" now and then. When the pointer comes close the head lifts and the eyes open and follow it.
A click is a pet: purring, hearts, a big stretch, then it curls up and goes back to sleep.
"""
import math

from ..engine import ASPECT, Scene, clamp, hsv, mix, noise2, scale
from .aquarium import QuickBody, hsh

FURS = [
    # name, base, stripe/patch color, light (chest, muzzle), pattern
    ("orange tabby", (240, 145, 55), (150, 70, 25), (250, 225, 190), "tabby"),
    ("grey tabby", (160, 160, 165), (70, 70, 78), (225, 225, 220), "tabby"),
    ("brown tabby", (175, 130, 85), (70, 45, 28), (230, 210, 180), "tabby"),
    ("black cat", (105, 102, 122), (60, 58, 72), (150, 148, 165), "plain"),
    ("white cat", (238, 236, 230), (215, 210, 205), (250, 248, 245), "plain"),
    ("calico", (245, 240, 230), (225, 130, 50), (250, 248, 245), "calico"),
    ("tuxedo", (100, 98, 115), (60, 58, 70), (240, 240, 238), "tuxedo"),
    ("siamese", (235, 220, 190), (95, 70, 55), (245, 235, 215), "points"),
    ("cream", (245, 215, 160), (220, 180, 120), (252, 240, 215), "tabby"),
]
EYES = [(120, 220, 90), (250, 190, 50), (110, 190, 250), (200, 230, 80), (240, 150, 40)]
CUSHIONS = [(190, 60, 70), (60, 140, 150), (210, 165, 60), (140, 110, 190), (90, 150, 90), (200, 110, 150)]


class Cat(Scene):
    name = "cat"
    title = "Sleepy Cat"
    blurb = "a cat curled up asleep on a cushion by the window, breathing, dreaming, purring when petted"
    tags = ("cozy", "creatures", "calm", "night")
    interactions = "point near the cat to wake it (its eyes follow you), click to pet it"
    options = {
        "fur": ("random", "fur: random, " + ", ".join(f[0].split()[0] for f in FURS)),
        "weather": ("random", "outside the window: random, rain, stars, snow"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        want = str(self.opt("fur")).lower()
        furs = [f for f in FURS if f[0].startswith(want)] or FURS
        self.fur_name, self.fur, self.stripe, self.light_fur, self.pattern = rng.choice(furs)
        self.eye = (110, 190, 250) if self.pattern == "points" else rng.choice(EYES)
        weather = str(self.opt("weather")).lower()
        self.weather = weather if weather in ("rain", "stars", "snow") else rng.choice(("rain", "rain", "stars", "snow"))
        self.face = rng.choice((-1, 1))
        self.C = max(3.0, min(w * 0.2, h * 0.5) * rng.uniform(0.9, 1.05))
        C = self.C
        self.cx = w * 0.5 + rng.uniform(-0.12, 0.12) * w
        self.sill = h - max(2, int(h * rng.uniform(0.12, 0.2)))         # top of the window seat
        self.cush = rng.choice(CUSHIONS)
        self.cush_rx = C * 1.45
        self.cush_ry = C * 0.32
        self.cy = self.sill - self.cush_ry / ASPECT * 0.9 - 0.62 * C / ASPECT * 0.85
        # the window behind
        ww = min(w * rng.uniform(0.45, 0.6), max(C * 3.2, w * 0.4))
        self.win = (max(1, int(self.cx - ww / 2 + rng.uniform(-0.1, 0.1) * w)), 1)
        self.win = (int(clamp(self.win[0], 1, w - ww - 1)), max(1, int(h * 0.06)))
        self.win_w = int(ww)
        self.win_h = max(4, int(self.sill - self.win[1] - 1))
        self.panes = rng.choice((2, 2, 3))
        self.wall = rng.choice([(70, 45, 50), (45, 50, 70), (60, 55, 45), (50, 60, 55)])
        self.stars = [(rng.random(), rng.random(), rng.random()) for _ in range(self.count(20))]
        self.moon = (rng.uniform(0.2, 0.8), rng.uniform(0.15, 0.4)) if rng.random() < 0.6 else None
        self.drops = [[rng.random(), rng.random(), rng.uniform(0.6, 1.4)] for _ in range(self.count(40))]
        self.glass = [[rng.random(), rng.random(), rng.uniform(0.02, 0.08)] for _ in range(self.count(10))]
        self.prop = rng.choice(("plant", "mug", "books", None))
        self.prop_x = rng.choice((-1, 1))
        self.seed = rng.uniform(0, 100)
        # state
        self.state = "sleep"
        self.st = 0.0          # time in state
        self.lift = 0.0        # head raised (0 asleep .. 1 alert)
        self.open = 0.0        # eyelids (0 shut .. 1 open)
        self.stretch = 0.0
        self.purr = 0.0
        self.away = 0.0        # seconds since the pointer left
        self.look = (0.0, 0.0)
        self.breath = rng.uniform(0, 6)
        self.flick = 0.0
        self.flick_t = rng.uniform(2, 6)
        self.ear = 0.0
        self.ear_t = rng.uniform(3, 8)
        self.zs = []
        self.z_t = 1.0
        self.hearts = []
        self.blink = 3.0

    # ------------------------------------------------------------------ helpers
    def P(self, u, v):
        """Cat-local coordinates (in units of C, v down) -> cells. u runs toward the head."""
        return self.cx + u * self.C * self.face, self.cy + v * self.C / ASPECT

    def head_pos(self):
        lift, s = self.lift, self.stretch
        return self.P(0.9 - 0.05 * lift + 0.3 * s, -0.12 - 0.45 * lift - 0.05 * s)

    def on_click(self, x, y):
        if self.state in ("purr", "stretch"):
            self.purr = max(self.purr, 2.0)
            return
        self.state = "purr"
        self.st = 0.0
        self.purr = 3.2

    # ------------------------------------------------------------------ move
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.1)
        rng = self.rng
        C = self.C
        self.st += dt
        hx, hy = self.head_pos()
        near = False
        if self.pointer is not None:
            px, py = self.pointer
            near = math.hypot(px - self.cx, (py - self.cy) * ASPECT) < C * 2.2
            dx, dy = (px - hx) * self.face, (py - hy) * ASPECT
            dd = math.hypot(dx, dy) or 1.0
            self.look = (dx / dd * min(1.0, dd / (C * 0.6)), dy / dd * min(1.0, dd / (C * 0.6)))
        self.away = 0.0 if near else self.away + dt
        s = self.state
        if s == "sleep":
            self.lift = max(0.0, self.lift - dt * 0.8)
            self.open = max(0.0, self.open - dt * 1.5)
            self.stretch = max(0.0, self.stretch - dt)
            if near:
                self.state, self.st = "wake", 0.0
        elif s == "wake":
            self.lift = min(1.0, self.lift + dt * 1.8)
            if self.lift > 0.4:
                self.open = min(1.0, self.open + dt * 2.5)
            self.blink -= dt
            if self.blink < 0:
                self.open = 0.1
                if self.blink < -0.12:
                    self.blink = rng.uniform(2, 5)
            if self.away > 3.5:            # bored: back to sleep
                self.state, self.st = "drowsy", 0.0
        elif s == "drowsy":
            self.open = max(0.0, self.open - dt * 0.6)
            if self.open < 0.4:
                self.lift = max(0.0, self.lift - dt * 0.7)
            if near:
                self.state = "wake"
            elif self.lift <= 0 and self.open <= 0:
                self.state, self.st = "sleep", 0.0
        elif s == "purr":
            self.lift = min(1.0, self.lift + dt * 1.5)
            self.open = max(0.0, self.open - dt * 3)      # happy squint
            self.purr -= dt
            if rng.random() < dt * 2.2:
                self.hearts.append([hx + rng.uniform(-2, 2), hy - C * 0.3 / ASPECT, rng.uniform(0, 6), 0.0])
            if self.purr <= 0:
                self.state, self.st = "stretch", 0.0
        elif s == "stretch":
            k = self.st / 2.6
            self.stretch = math.sin(clamp(k) * math.pi) ** 0.8
            self.open = 0.5 * self.stretch
            if k >= 1:
                self.stretch = 0.0
                self.state, self.st = ("wake" if near else "drowsy"), 0.0
        # tail tip flick, ear twitch, breathing
        self.breath += dt * (1.6 if self.state == "sleep" else 2.6 if self.state == "purr" else 2.2)
        self.flick_t -= dt
        if self.flick_t < 0:
            self.flick = 1.0
            self.flick_t = rng.uniform(2.5, 7) if self.state == "sleep" else rng.uniform(1, 3)
        self.flick = max(0.0, self.flick - dt * 1.4)
        self.ear_t -= dt
        if self.ear_t < 0:
            self.ear = 1.0
            self.ear_t = rng.uniform(3, 9)
        self.ear = max(0.0, self.ear - dt * 4)
        # z's while sleeping
        if self.state == "sleep" and self.lift < 0.1:
            self.z_t -= dt
            if self.z_t < 0:
                self.zs.append([hx + self.face * C * 0.2, hy - C * 0.35 / ASPECT, 0.0, rng.uniform(0, 6)])
                self.z_t = rng.uniform(1.3, 2.2)
        for z in self.zs:
            z[2] += dt
            z[1] -= dt * 1.1
            z[0] += self.face * dt * 0.8 + math.sin(z[2] * 2 + z[3]) * dt * 0.6
        self.zs = [z for z in self.zs if z[2] < 3.2 and z[1] > 0]
        for ht in self.hearts:
            ht[3] += dt
            ht[1] -= dt * 1.6
            ht[0] += math.sin(ht[3] * 3 + ht[2]) * dt * 1.2
        self.hearts = [ht for ht in self.hearts if ht[3] < 2.2 and ht[1] > 0]
        # the weather outside
        for d in self.drops:
            if self.weather == "rain":
                d[1] += dt * 1.6 * d[2]
                d[0] += dt * 0.12
            else:
                d[1] += dt * 0.08 * d[2]
                d[0] += math.sin(self.t * 0.7 + d[2] * 9) * dt * 0.02
            if d[1] > 1:
                d[1] -= 1
                d[0] = rng.random()
            d[0] %= 1.0
        for g in self.glass:
            g[1] += dt * g[2]
            if g[1] > 1:
                g[0], g[1] = rng.random(), 0.0

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        self.draw_room(cv)
        self.draw_cushion(cv)
        self.draw_cat(cv)
        t = self.t
        for x, y, age, ph in self.zs:
            k = clamp(1 - age / 3.2) * clamp(age * 3)
            ch = "z" if age < 1.1 else "Z"
            cv.put(x, y, ch, scale((200, 210, 255), 0.35 + 0.6 * k))
        for x, y, ph, age in self.hearts:
            k = clamp(1 - age / 2.2)
            c = scale((255, 110, 150), 0.4 + 0.6 * k)
            cv.put(x, y, "<", c)
            cv.put(x + 1, y, "3", c)
        if self.state == "purr":         # purr: little vibration waves around the body
            C = self.C
            for k in range(3):
                ph = (t * 1.6 + k / 3) % 1.0
                r = C * (1.05 + 0.5 * ph)
                for side in (-1, 1):
                    for j in range(-1, 2):
                        a = j * 0.35
                        x = self.cx + side * math.cos(a) * r * 1.05
                        y = self.cy + math.sin(a) * r * 0.55 / ASPECT - 0.5
                        cv.put(x, y, "~", scale((255, 200, 160), 0.6 * (1 - ph)))

    def draw_room(self, cv):
        w, h, t = self.w, self.h, self.t
        wall = self.wall
        # a soft wallpaper pattern
        for y in range(0, self.sill):
            for x in range(0, w):
                if (x + 3 * (y % 2)) % 6 == 0 and y % 2 == 0:
                    cv.put(x, y, "." if (x // 6 + y // 2) % 3 else "+", scale(wall, 0.55))
        x0, y0 = self.win
        ww, wh = self.win_w, self.win_h
        x1, y1 = x0 + ww, y0 + wh
        # outside: night sky
        sky0, sky1 = (15, 20, 45), (35, 40, 75)
        for y in range(y0 + 1, y1):
            f = (y - y0) / max(1, wh)
            c = mix(sky0, sky1, f)
            for x in range(x0 + 1, x1):
                cv.put(x, y, " ", c)
        cv.fill_box(x0 + 1, y0 + 1, x1, y1)
        if self.moon is not None and self.weather != "rain":
            mx = x0 + 2 + self.moon[0] * (ww - 4)
            my = y0 + 1 + self.moon[1] * (wh - 2)
            r = max(1.5, min(ww, wh * 2) * 0.09)
            for y in range(int(my - r / ASPECT - 2), int(my + r / ASPECT + 3)):
                for x in range(int(mx - r - 3), int(mx + r + 4)):
                    if x0 < x < x1 and y0 < y < y1:
                        d = math.hypot(x + 0.5 - mx, (y + 0.5 - my) * ASPECT)
                        if d < r:
                            cv.shade(x, y, 0.8 - 0.2 * d / r, (240, 235, 200))
                        elif d < r + 3:
                            cv.shade(x, y, 0.12 * (1 - (d - r) / 3), (180, 180, 210))
        if self.weather != "rain":
            for sx, sy, k in self.stars:
                x, y = x0 + 1 + sx * (ww - 2), y0 + 1 + sy * (wh - 2)
                tw = 0.5 + 0.5 * math.sin(t * (1 + 2 * k) + k * 40)
                cv.shade(x, y, 0.15 + 0.4 * tw * k, (210, 215, 255), mode="max")
        for dx, dy, sp in self.drops:
            x, y = x0 + 1 + dx * (ww - 2), y0 + 1 + dy * (wh - 2)
            if self.weather == "rain":
                cv.put(x, y, "/" if sp > 1.1 else "|", scale((120, 150, 200), 0.35 + 0.25 * sp))
            elif self.weather == "snow":
                cv.put(x, y, "*" if sp > 1.15 else ".", scale((230, 235, 250), 0.45 + 0.3 * sp))
        if self.weather == "rain":                       # drops trickling down the glass
            for gx, gy, sp in self.glass:
                x, y = x0 + 1 + gx * (ww - 2), y0 + 1 + gy * (wh - 2)
                cv.put(x, y, "o", (150, 180, 220))
                cv.put(x, y - 1, ".", (90, 110, 150))
        # the frame
        wood = (120, 80, 50)
        for x in range(x0, x1 + 1):
            cv.put(x, y0, "=", wood)
            cv.put(x, y1, "=", wood)
        for y in range(y0, y1 + 1):
            cv.put(x0, y, "|" if y not in (y0, y1) else "+", wood)
            cv.put(x1, y, "|" if y not in (y0, y1) else "+", wood)
        for k in range(1, self.panes):
            xm = x0 + ww * k // self.panes
            for y in range(y0 + 1, y1):
                cv.put(xm, y, "|", scale(wood, 0.9))
        ym = y0 + wh // 2
        for x in range(x0 + 1, x1):
            cv.put(x, ym, "-", scale(wood, 0.9))
        # window seat
        seat = (110, 75, 50)
        for x in range(w):
            cv.put(x, self.sill, "=", seat)
            for y in range(self.sill + 1, h):
                plank = (y - self.sill) % 2 == 0
                ch = "_" if plank else ("|" if (x + 5 * y) % 11 == 0 else " ")
                if ch != " ":
                    cv.put(x, y, ch, scale(seat, 0.5 - 0.15 * (y - self.sill) / max(1, h - self.sill)))
        self.draw_prop(cv)

    def draw_prop(self, cv):
        if self.prop is None:
            return
        C = self.C
        x = self.cx + self.prop_x * C * 1.85
        if x < 3 or x > self.w - 4:
            return
        y = self.sill - 1
        if self.prop == "mug":
            cv.text(x - 1, y, "|_|)", (200, 200, 210))
            cv.text(x - 1, y - 1, "| |", (200, 200, 210))
            for k in range(3):
                sx = x + math.sin(self.t * 1.5 + k * 1.3) * 0.8
                cv.put(sx, y - 2 - k, "(" if k % 2 else ")", scale((200, 200, 210), 0.5 - 0.12 * k))
        elif self.prop == "books":
            cols = [(160, 60, 60), (60, 100, 160), (200, 170, 70), (80, 140, 90)]
            for k in range(4):
                cv.text(x - 3 + (k % 2), y - k, "[=====]", cols[k % 4])
        else:
            cv.text(x - 2, y, "\\___/", (190, 100, 70))
            cv.text(x - 2, y - 1, "|   |", (190, 100, 70))
            for k in range(5):
                a = -math.pi / 2 + (k - 2) * 0.45 + math.sin(self.t * 0.6 + k) * 0.05
                for j in range(1, 5):
                    lx = x + math.cos(a) * j * 1.4
                    ly = y - 2 + math.sin(a) * j / ASPECT * 1.4
                    cv.put(lx, ly, "|" if abs(math.cos(a)) < 0.3 else ("/" if math.cos(a) > 0 else "\\"),
                           scale((90, 170, 80), 0.6 + 0.1 * j))

    def draw_cushion(self, cv):
        b = QuickBody(blend=0.5)
        rx, ry = self.cush_rx, self.cush_ry
        cy = self.sill - ry / ASPECT * 0.7
        b.ellipse(self.cx, cy, rx, ry, color=self.cush)
        seed = self.seed
        col = self.cush

        def pattern(x, y, i, inside):
            if (int(x * 0.5) + int(y)) % 2 == 0:
                return mix(col, (255, 255, 255), 0.12)
            return None
        b.draw(cv, light=(-self.face * 0.6, -0.8), edge=2.0, pattern=pattern, ambient=0.55, mode="over")
        for k in (-1, 0, 1):    # tufted buttons
            cv.put(self.cx + k * rx * 0.55, cy + 0.3, "o", scale(col, 0.6))

    def fur_pattern(self, part):
        """Pattern callback for one layer of the cat ("body", "head", "paws")."""
        pat, stripe, seed, f, C = self.pattern, self.stripe, self.seed, self.face, self.C
        cx, cy, fur, light = self.cx, self.cy, self.fur, self.light_fur
        hx, hy = self.head_pos()

        def pattern(x, y, i, inside):
            u = (x - cx) * f / C
            v = (y - cy) * ASPECT / C
            if pat == "tabby":
                if part == "body":
                    band = math.sin(u * 8 + math.sin(v * 3 + seed) * 1.3 + seed)
                    if v > 0.38:
                        return mix(fur, light, 0.5)
                    if band > 0.35:
                        return stripe
                elif part == "head" and i == 0:
                    hu = (x - hx) * f / C
                    hv = (y - hy) * ASPECT / C
                    if hv < -0.12 and math.sin(hu * 26) > 0.3:      # the tabby "M" on the forehead
                        return stripe
                    if hv > -0.05 and abs(math.sin(hv * 20)) > 0.85 and hu < 0.1:
                        return stripe
            elif pat == "calico":
                n = noise2(x * 0.11 + seed, y * 0.22)
                if n > 0.22:
                    return stripe
                if n < -0.3:
                    return (55, 50, 55)
            elif pat == "tuxedo":
                if part == "paws" or (part == "head" and i == 3):
                    return light
                if part == "body" and u > 0.55 and v > -0.15:
                    return light
            elif pat == "points":
                if part == "paws" or (part == "head" and i in (1, 2)):
                    return stripe
                if part == "head" and i == 0:
                    d = math.hypot((x - hx) * f / C - 0.18, (y - hy) * ASPECT / C - 0.08)
                    if d < 0.3:
                        return mix(stripe, fur, d / 0.3)
            elif pat == "plain" and part == "body" and v > 0.4:
                return mix(fur, light, 0.3)
            return None
        return pattern

    def draw_cat(self, cv):
        """Body, then tail, then paws, then head: each layer is its own QuickBody drawn with
        mode="over", so the soft light edge of a front layer draws a contour line across the one
        behind it. That's what makes the head read as a head instead of one big furry loaf."""
        C = self.C
        f = self.face
        br = math.sin(self.breath)
        if self.state == "purr":
            br = 0.5 * br + 0.3 * math.sin(self.t * 40)     # purring vibrates
        swell = 1 + 0.05 * br
        lift, st = self.lift, self.stretch
        fur, light = self.fur, self.light_fur
        P = self.P
        L = (-f * 0.65, -0.75)
        edge = clamp(C * 0.28, 1.2, 4.0)
        b = QuickBody(blend=0.1 * C)
        b.ellipse(*P(0.05 * st, 0.02), C * (1.0 + 0.25 * st), C * 0.55 * swell * (1 - 0.2 * st), color=fur)
        b.circle(*P(-0.5 - 0.15 * st, -0.08 - 0.25 * st), C * 0.5 * (1 + 0.03 * br), color=fur)
        b.draw(cv, light=L, edge=edge, pattern=self.fur_pattern("body"), ambient=0.5, mode="over")
        self.draw_tail(cv)
        # front paws: tucked under the chin when asleep, reaching far out in the stretch
        pw = QuickBody(blend=0.05 * C)
        for k in (0, 1):
            x0, y0 = P(0.55 + 0.12 * k, 0.38)
            x1, y1 = P(0.78 + 0.12 * k + 0.85 * st, 0.5 - 0.04 * k)
            pw.capsule(x0, y0, x1, y1, C * 0.12, C * 0.12, color=fur)
        pw.draw(cv, light=L, edge=clamp(C * 0.1, 1.0, 1.6), pattern=self.fur_pattern("paws"), ambient=0.6, mode="over")
        # the head: round, two cone ears (one twitches), a pale muzzle
        hx, hy = self.head_pos()
        hu = 0.9 - 0.05 * lift + 0.3 * st
        hv = -0.12 - 0.45 * lift - 0.05 * st
        hb = QuickBody(blend=0.06 * C)
        hb.circle(hx, hy, C * 0.42, color=fur)
        tw = self.ear * 0.25
        for bu, bv, tu, tv in ((-0.22, -0.2, -0.3, -0.78), (0.14, -0.26, 0.24 + tw, -0.8 + tw * 0.4)):
            x0, y0 = P(hu + bu, hv + bv)
            x1, y1 = P(hu + tu, hv + tv)
            hb.capsule(x0, y0, x1, y1, C * 0.2, C * 0.02, color=fur)
        hb.ellipse(*P(hu + 0.26, hv + 0.14), C * 0.17, C * 0.12, color=light)
        open_ = self.open
        eyes = []
        for du in (0.04, 0.25):
            ex, ey = P(hu + du, hv - 0.04)
            eyes.append((ex, ey))
            if open_ < 0.35:
                ch = "^" if self.state == "purr" else "-"
                hb.spot(ex, ey, 0.45, (25, 22, 25), ch)
                if C > 9:
                    hb.spot(ex + 1, ey, 0.3, (25, 22, 25), ch)
            else:
                hb.spot(ex, ey, C * 0.035 + 0.6, self.eye, "O" if C > 9 and open_ > 0.7 else "o")
        nx, ny = P(hu + 0.4, hv + 0.08)
        hb.spot(nx, ny, 0.3, (240, 130, 150), "v" if C > 7 else ".")
        hb.draw(cv, light=L, edge=clamp(C * 0.22, 1.2, 3.2), pattern=self.fur_pattern("head"), ambient=0.55,
                mode="over")
        # pupils: slits that follow the pointer
        if open_ >= 0.35:
            lx, ly = self.look
            for ex, ey in eyes:
                cv.put(ex + lx * f * 0.9, ey + ly * 0.45, "|" if open_ > 0.7 else "-", (15, 15, 10))
        wc = scale((235, 235, 235), 0.6)        # whiskers poke out past the muzzle
        for k in (-1, 1):
            for j in range(3 if C > 8 else 2):
                cv.put(nx + f * (2 + j), ny + (0.6 if k > 0 else -0.3) + j * 0.2 * k,
                       "-" if j < 2 else ("\\" if k * f > 0 else "/"), wc)

    def draw_tail(self, cv):
        """The tail wraps around the front of the body; the tip flicks."""
        C = self.C
        st = self.stretch
        n = 9
        pts = []
        for k in range(n):
            f = k / (n - 1)
            if st > 0.05:     # held up in a curve during the stretch
                a = math.pi * (0.95 - 0.55 * f * st)
                u = -0.95 + math.cos(a) * f * 0.6 * st - (1 - st) * 0.0
                v = 0.15 - math.sin(a) * f * 0.9 * st + (1 - st) * (0.45 * f)
            else:
                a = math.pi * (1.08 - 1.0 * f)
                u = math.cos(a) * 1.0
                v = 0.3 + math.sin(a) * 0.3 - max(0.0, f - 0.8) * 0.6
            if k >= n - 3:
                v -= self.flick * math.sin(self.t * 14) * 0.08 * (k - n + 4)
                u += self.flick * 0.05 * (k - n + 4)
            pts.append(self.P(u, v))
        b = QuickBody(blend=0.08 * C)
        for k in range(n - 1):
            r0 = C * (0.17 - 0.06 * k / n)
            r1 = C * (0.17 - 0.06 * (k + 1) / n)
            b.capsule(pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1], r0, r1, color=self.fur)
        stripe, pat = self.stripe, self.pattern

        def pattern(x, y, i, inside):
            if pat in ("tabby", "points") and (pat == "points" or i % 2 == 1):
                return stripe
            if pat == "calico" and i >= n - 4:
                return stripe
            return None
        b.draw(cv, light=(-self.face * 0.65, -0.75), edge=clamp(C * 0.12, 1.0, 1.8), pattern=pattern, ambient=0.55,
               mode="over")
