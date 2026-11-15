"""Conway's Game of Life on a torus, cells colored by age, dead cells leaving glowing ghosts."""
from ..engine import Scene, gradient

RULES = {
    "life": ({3}, {2, 3}),
    "highlife": ({3, 6}, {2, 3}),
    "daynight": ({3, 6, 7, 8}, {3, 4, 6, 7, 8}),
    "seeds": ({2}, set()),
    "maze": ({3}, {1, 2, 3, 4, 5}),
}

# age palettes: newborn -> young -> mature -> ancient, plus the color ghosts cool toward
PALETTES = {
    "aurora": ([(255, 255, 235), (120, 255, 210), (60, 190, 255), (150, 110, 255), (230, 80, 200),
                (255, 120, 90)], (90, 60, 170)),
    "ember": ([(255, 255, 220), (255, 215, 90), (255, 130, 40), (225, 55, 60), (160, 40, 130)],
              (120, 40, 60)),
    "ocean": ([(240, 255, 255), (120, 240, 255), (40, 150, 255), (50, 80, 220), (120, 60, 200)],
              (30, 60, 130)),
    "forest": ([(245, 255, 220), (170, 255, 120), (60, 210, 120), (30, 150, 140), (210, 180, 80)],
               (40, 90, 60)),
    "candy": ([(255, 255, 255), (255, 170, 220), (200, 140, 255), (120, 200, 255), (140, 255, 200)],
              (110, 70, 140)),
    "mono": ([(255, 255, 255), (205, 222, 255), (150, 170, 225), (110, 120, 175)], (60, 70, 100)),
}

# a few classic patterns as (dx, dy) cells
PATTERNS = [
    [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)],                                   # glider
    [(1, 0), (4, 0), (0, 1), (0, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3)],   # lightweight spaceship
    [(1, 0), (2, 0), (0, 1), (1, 1), (1, 2)],                                   # r-pentomino
    [(1, 0), (3, 1), (0, 2), (1, 2), (4, 2), (5, 2), (6, 2)],                   # acorn
    [(0, 0), (1, 0), (2, 0)],                                                   # blinker
    [(1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1)],                           # toad
    [(0, 0), (1, 0), (0, 1), (3, 2), (2, 3), (3, 3)],                           # beacon
    [(6, 0), (0, 1), (1, 1), (1, 2), (5, 2), (6, 2), (7, 2)],                   # diehard
]

GLOWS = (0.0, 0.05, 0.09, 0.12, 0.14, 0.15, 0.16, 0.16, 0.16)


def _q(c):
    r, g, b = c
    r = 0 if r < 0 else 252 if r > 252 else int(r) & ~3
    g = 0 if g < 0 else 252 if g > 252 else int(g) & ~3
    b = 0 if b < 0 else 252 if b > 252 else int(b) & ~3
    return (r, g, b)


class Life(Scene):
    name = "life"
    title = "Game of Life"
    blurb = "Conway's Game of Life on a torus, colored by age with fading ghosts"
    tags = ("math", "abstract", "retro")
    options = {
        "rule": ("random", "life, highlife, daynight, seeds, maze or random (mostly life)"),
        "palette": ("random", "aurora, ember, ocean, forest, candy, mono or random"),
        "start": ("random", "how worlds are seeded: soup, symmetric, patterns, band or random"),
        "speed": (12.0, "generations per second"),
        "reseed": (900, "reseed after this many generations (0 = only when stagnant)"),
        "fill": (0.32, "fraction of live cells when seeding"),
        "cell": (2, "cell width in characters (2 = square cells)"),
    }

    def _choose_style(self):
        rng = self.rng
        rule = self.opt("rule")
        if rule not in RULES:
            rule = rng.choices(("life", "highlife", "daynight"), (0.65, 0.2, 0.15))[0]
        pal = self.opt("palette")
        if pal not in PALETTES:
            pal = rng.choice(list(PALETTES))
        start = self.opt("start")
        if start not in ("soup", "symmetric", "patterns", "band"):
            start = rng.choices(("soup", "symmetric", "patterns", "band"), (0.4, 0.25, 0.2, 0.15))[0]
        fill = self.opt("fill")
        if "fill" not in self.ctx.options:
            fill = rng.uniform(0.5, 0.56) if rule == "daynight" else rng.uniform(0.22, 0.4)
        self.style = {"rule": rule, "palette": pal, "start": start, "fill": fill,
                      "ghost_fade": rng.uniform(1.0, 2.2)}

    def setup(self):
        if not hasattr(self, "style"):
            self._choose_style()
        self.cw = max(1, min(4, self.opt("cell")))
        self.gw = max(4, self.w // self.cw)
        self.gh = max(4, self.h)
        n = self.gw * self.gh
        self.age = [0] * n          # >0 alive for that many generations
        self.ghost = [0.0] * n      # afterglow of recently dead cells
        self.ghost_age = [0] * n
        rule = RULES[self.style["rule"]]
        self.born = [k in rule[0] for k in range(9)]
        self.survive = [k in rule[1] for k in range(9)]
        self.acc = 0.0
        self.gen = 0
        self.history = []
        self.flat = 0
        # neighbor index lists on the torus
        gw, gh = self.gw, self.gh
        self.nbr = []
        for y in range(gh):
            ym, yp = (y - 1) % gh, (y + 1) % gh
            for x in range(gw):
                xm, xp = (x - 1) % gw, (x + 1) % gw
                self.nbr.append((ym * gw + xm, ym * gw + x, ym * gw + xp, y * gw + xm,
                                 y * gw + xp, yp * gw + xm, yp * gw + x, yp * gw + xp))
        stops, self.ghost_col = PALETTES[self.style["palette"]]
        self.palette = [_q(gradient(stops, min(1.0, (a / 60.0) ** 0.6))) for a in range(61)]
        self.seed_soup(full=True)

    def seed_soup(self, full=False):
        rng = self.rng
        fill = min(0.9, max(0.02, self.style["fill"]))
        gw, gh = self.gw, self.gh
        if full:
            # the old world dies into ghosts
            for i in range(gw * gh):
                if self.age[i]:
                    self.ghost[i] = 1.0
                    self.ghost_age[i] = self.age[i]
                    self.age[i] = 0
            start = self.style["start"]
            age = self.age
            if start == "symmetric":
                # one quadrant of soup mirrored four ways: kaleidoscopic evolution
                hw, hh = (gw + 1) // 2, (gh + 1) // 2
                for y in range(hh):
                    for x in range(hw):
                        if rng.random() < fill * 0.9:
                            for xx, yy in ((x, y), (gw - 1 - x, y), (x, gh - 1 - y), (gw - 1 - x, gh - 1 - y)):
                                age[yy * gw + xx] = 1
            elif start == "patterns":
                # a scatter of gliders, spaceships, methuselahs and oscillators
                for _ in range(max(4, gw * gh // 90)):
                    pat = rng.choice(PATTERNS)
                    ox, oy = rng.randrange(gw), rng.randrange(gh)
                    fx, fy = rng.choice((1, -1)), rng.choice((1, -1))
                    swap = rng.random() < 0.5
                    for dx, dy in pat:
                        if swap:
                            dx, dy = dy, dx
                        age[((oy + dy * fy) % gh) * gw + (ox + dx * fx) % gw] = 1
            elif start == "band":
                y0 = int(gh * rng.uniform(0.3, 0.45))
                y1 = gh - y0
                for y in range(y0, y1):
                    for x in range(gw):
                        if rng.random() < fill:
                            age[y * gw + x] = 1
            else:
                for i in range(gw * gh):
                    if rng.random() < fill:
                        age[i] = 1
        else:
            # drop a few random soup patches into the running world
            for _ in range(rng.randint(2, 4)):
                cx, cy = rng.randrange(gw), rng.randrange(gh)
                r = rng.randint(3, max(4, min(gw, gh) // 5))
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if dx * dx + dy * dy <= r * r and rng.random() < fill:
                            self.age[((cy + dy) % gh) * gw + (cx + dx) % gw] = 1
        self.history = []
        self.flat = 0

    def step(self):
        age, nbr, born, survive = self.age, self.nbr, self.born, self.survive
        alive = [1 if a else 0 for a in age]
        new = [0] * len(age)
        ghost, gage = self.ghost, self.ghost_age
        pop = 0
        for i, (a, b, c, d, e, f, g, h) in enumerate(nbr):
            k = alive[a] + alive[b] + alive[c] + alive[d] + alive[e] + alive[f] + alive[g] + alive[h]
            if alive[i]:
                if survive[k]:
                    new[i] = age[i] + 1 if age[i] < 60 else 60
                    pop += 1
                else:
                    ghost[i] = 1.0
                    gage[i] = age[i]
            elif born[k]:
                new[i] = 1
                pop += 1
        self.age = new
        self.gen += 1
        # stagnation: same population pattern repeating, or tiny population
        sig = (pop, sum(1 for a in new if a == 1))
        self.history.append(sig)
        if len(self.history) > 40:
            self.history.pop(0)
        births = sig[1]
        if births < max(2, len(new) // 600):
            self.flat += 1
        else:
            self.flat = 0
        n = len(new)
        stale = len(self.history) >= 40 and len(set(self.history)) <= 3
        limit = self.opt("reseed")
        if pop < n * 0.01 or stale or self.flat > 30:
            self.seed_soup(full=pop < n * 0.004)
        elif limit and self.gen % limit == 0:
            self.seed_soup(full=True)
        elif self.gen % 150 == 0 and pop < n * 0.06:
            self.seed_soup(full=False)

    def update(self, dt):
        super().update(dt)
        rate = max(0.1, self.opt("speed"))
        # ghosts fade continuously, independent of generation rate
        decay = 1.0 - min(1.0, dt * self.style["ghost_fade"])
        g = self.ghost
        for i in range(len(g)):
            if g[i] > 0.01:
                g[i] *= decay
            elif g[i]:
                g[i] = 0.0
        self.acc += dt * rate
        steps = 0
        while self.acc >= 1.0 and steps < 8:
            self.acc -= 1.0
            self.step()
            steps += 1
        if steps == 8:
            self.acc = 0.0

    def draw(self, cv):
        gw, gh, cwid = self.gw, self.gh, self.cw
        age, ghost, gage, nbr = self.age, self.ghost, self.ghost_age, self.nbr
        pal = self.palette
        ramp = cv.ramp
        nr = len(ramp) - 1
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        W = cv.w
        H = min(cv.h, gh)
        ox = (cv.w - gw * cwid) // 2
        alive = [1 if a else 0 for a in age]
        gcol = self.ghost_col
        for y in range(H):
            row = y * gw
            base = y * W + ox
            for x in range(gw):
                i = row + x
                a = age[i]
                if a:
                    v = 1.0 if a == 1 else 0.92 if a < 6 else 0.82
                    c = pal[a]
                else:
                    n = nbr[i]
                    k = alive[n[0]] + alive[n[1]] + alive[n[2]] + alive[n[3]] + alive[n[4]] + \
                        alive[n[5]] + alive[n[6]] + alive[n[7]]
                    gv = ghost[i] * 0.36
                    hv = GLOWS[k]
                    if gv <= 0.02 and hv <= 0:
                        continue
                    if gv >= hv:
                        v = gv
                        ga = pal[gage[i]]
                        f = ghost[i]
                        # ghosts cool from their last color toward deep violet
                        m = f * f * 0.75
                        k = 0.3 + 0.5 * f
                        c = _q(((gcol[0] + (ga[0] - gcol[0]) * m) * k,
                                (gcol[1] + (ga[1] - gcol[1]) * m) * k,
                                (gcol[2] + (ga[2] - gcol[2]) * m) * k))
                    else:
                        v = hv
                        c = (40, 70, 120)
                idx = int(v * nr + 0.5)
                if idx <= 0:
                    continue
                gch = ramp[idx]
                j = base + x * cwid
                for s in range(cwid):
                    jj = j + s
                    if 0 <= jj - y * W < W:
                        ch[jj] = gch
                        fg[jj] = c
                        lv[jj] = v
