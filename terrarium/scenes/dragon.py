"""An eastern dragon chasing a pearl through moonlit clouds."""
import math

from ..engine import ASPECT, Scene, clamp, fbm, gradient, hsv, mix, noise2, scale, smoothstep
from .octopus import stroke
from .whale import dir_glyph

TAU = math.tau

# body gradient (dark .. light), belly plates, mane/fins, horns, eye, whiskers
GENOMES = {
    "jade": ([(8, 40, 28), (20, 100, 64), (60, 180, 110), (170, 245, 190)], (235, 205, 120), (255, 175, 60),
             (240, 225, 180), (255, 80, 40), (200, 250, 210)),
    "gold": ([(70, 36, 6), (170, 100, 20), (240, 175, 50), (255, 235, 150)], (255, 240, 200), (230, 50, 40),
             (250, 245, 225), (255, 40, 30), (255, 225, 160)),
    "crimson": ([(60, 6, 10), (150, 20, 30), (225, 60, 55), (255, 160, 130)], (250, 200, 90), (255, 200, 70),
                (245, 230, 200), (255, 230, 80), (255, 190, 150)),
    "azure": ([(8, 20, 70), (25, 70, 160), (70, 150, 235), (190, 230, 255)], (225, 235, 250), (120, 220, 255),
              (230, 235, 245), (255, 220, 90), (200, 235, 255)),
}


class Spark:
    __slots__ = ("x", "y", "vx", "vy", "life", "age")


class Dragon(Scene):
    name = "dragon"
    title = "Dragon"
    blurb = "an eastern dragon chasing a glowing pearl through moonlit clouds"
    tags = ("night", "fantasy", "sky")
    options = {
        "color": ("random", "random, " + ", ".join(GENOMES)),
        "clouds": (1.0, "amount of cloud (0 = clear sky)"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        name = self.opt("color")
        if name not in GENOMES:
            name = rng.choice(list(GENOMES))
        body, self.belly, self.mane, self.horn, self.eye, self.whisker = GENOMES[name]
        hs = rng.uniform(-0.03, 0.03)
        self.body = [self.shift(c, hs) for c in body]
        big = min(w, h * ASPECT)
        self.R = max(1.3, big * rng.uniform(0.03, 0.04))            # body half-thickness (aspect units)
        self.nseg = 64
        self.seg = max(1.0, (w * rng.uniform(1.3, 1.8)) / self.nseg)
        self.speed = rng.uniform(11, 16) * (big / 80) ** 0.5
        self.turn = rng.uniform(1.4, 2.2)
        self.wiggle = rng.uniform(0.4, 0.9)
        self.horn_len = rng.uniform(1.6, 2.4)
        self.horn_tines = rng.randint(1, 3)
        self.whisker_len = rng.uniform(2.2, 3.4)
        self.mane_n = rng.randint(4, 7)
        self.spine_gap = rng.uniform(1.6, 2.6)
        self.legs = sorted(rng.uniform(0.14, 0.2) for _ in range(1)) + [rng.uniform(0.5, 0.6)]
        self.belly_side = 1
        # pearl path genome
        self.pa = (rng.uniform(0.28, 0.4) * w, rng.uniform(0.22, 0.32) * h * ASPECT)
        self.pf = (rng.uniform(0.05, 0.08), rng.uniform(0.08, 0.13))
        self.pp = (rng.uniform(0, TAU), rng.uniform(0, TAU))
        self.pt = rng.uniform(0, 50)
        # start the dragon trailing in behind the pearl
        px, py = self.pearl_pos(self.pt - 2.0)
        self.ang = rng.uniform(0, TAU)
        self.pts = [(px - math.cos(self.ang) * self.seg * i, py - math.sin(self.ang) * self.seg * i)
                    for i in range(self.nseg + 1)]
        self.mouth = 0.0
        self.breath = 0.0
        self.next_breath = rng.uniform(4, 9)
        self.sparks = []
        self.build_sky()

    @staticmethod
    def shift(c, hs):
        import colorsys
        hh, ss, vv = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
        return hsv(hh + hs, ss, vv)

    def pearl_pos(self, t):
        w, h = self.w, self.h
        ax, ay = self.pa
        fx, fy = self.pf
        x = w / 2 + ax * math.sin(t * fx * TAU + self.pp[0]) + 0.08 * w * math.sin(t * 0.21 + 1.3)
        y = h * ASPECT * 0.5 + ay * math.sin(t * fy * TAU + self.pp[1]) + 0.05 * h * ASPECT * math.sin(t * 0.33)
        return x, y

    # ------------------------------------------------------------------ sky
    def build_sky(self):
        rng = self.rng
        w, h = self.w, self.h
        side = rng.choice((-1, 1))
        self.moon_r = max(3.0, min(w * 0.09, h * ASPECT * 0.17) * rng.uniform(0.85, 1.15))
        self.moon = (w / 2 + side * w * rng.uniform(0.18, 0.32), h * ASPECT * rng.uniform(0.22, 0.34))
        self.moon_col = hsv(rng.uniform(0.1, 0.16), rng.uniform(0.08, 0.25), 1.0)
        sd = rng.randrange(999)
        mx, my = self.moon
        mr = self.moon_r
        cells = []
        for y in range(max(0, int((my - mr * 2.4) / ASPECT)), min(h, int((my + mr * 2.4) / ASPECT) + 1)):
            for x in range(max(0, int(mx - mr * 2.4)), min(w, int(mx + mr * 2.4) + 1)):
                dx = x + 0.5 - mx
                dy = (y + 0.5) * ASPECT - my
                d = math.sqrt(dx * dx + dy * dy) / mr
                if d < 1:
                    z = math.sqrt(1 - d * d)
                    mare = fbm(x * 0.12, y * 0.24, 3, sd) * 0.5 + 0.5
                    crater = noise2(x * 0.5, y * 1.0, sd + 3)
                    v = 0.8 + 0.2 * z - 0.2 * smoothstep(0.45, 0.75, mare) - (0.1 if crater > 0.55 else 0)
                    col = mix(self.moon_col, (175, 170, 160), smoothstep(0.45, 0.8, mare) * 0.7)
                    cells.append((x, y, clamp(v), col, True))
                elif d < 2.4:
                    v = 0.32 * (2.4 - d) / 1.4
                    v = v * v * 2.2
                    if v > 0.03:
                        cells.append((x, y, v, self.moon_col, False))
        self.moon_cells = cells
        self.stars = [(rng.randrange(w), rng.randrange(h), rng.random() ** 2.5, rng.uniform(0, TAU))
                      for _ in range(int(w * h / 22 * self.density))]
        # clouds: two looping texture layers, lit from the moon side
        amt = max(0.0, float(self.opt("clouds")))
        self.layers = []
        if amt > 0:
            for depth in (0, 1):
                self.layers.append(self.build_clouds(depth, amt, rng.randrange(999)))

    def build_clouds(self, depth, amt, sd):
        """A looping strip of cumulus banks made of rounded puffs, lit from the moon's side."""
        rng = self.rng
        w, h = self.w, self.h
        tw = w * 2
        mx, my = self.moon
        nb = max(1, int(round((2 if depth == 0 else 1) * min(3.0, amt) + rng.uniform(-0.3, 0.6))))
        puffs = []
        for _ in range(nb):
            base = h * ASPECT * (rng.uniform(0.45, 0.95) if depth == 0 else rng.uniform(0.82, 1.02))
            x = rng.uniform(0, tw)
            end = x + tw * rng.uniform(0.35, 0.8) * min(1.5, 0.6 + 0.4 * amt)
            size = h * ASPECT * rng.uniform(0.1, 0.16) * (1.25 if depth else 1.0)
            while x < end:
                r = size * rng.uniform(0.6, 1.4)
                puffs.append((x % tw, base - r * rng.uniform(0.1, 0.6), r, base))
                x += r * rng.uniform(0.7, 1.2)
        night = (34, 42, 80) if depth == 0 else (48, 56, 98)
        lit_col = mix(self.moon_col, (205, 215, 245), 0.35)
        cols = [[] for _ in range(tw)]
        grid = {}
        for px, py, r, base in puffs:
            for y in range(max(0, int((py - r) / ASPECT)), min(h, int(base / ASPECT) + 2)):
                cy = (y + 0.5) * ASPECT
                for xx in range(int(px - r) - 1, int(px + r) + 2):
                    dx = xx + 0.5 - px
                    dy = cy - py
                    d = math.sqrt(dx * dx + dy * dy) / r
                    if d >= 1:
                        continue
                    fade = clamp((base + 1.5 - cy) / 3.0)          # flat-ish bottoms
                    k = (1 - d) * fade
                    if k <= 0:
                        continue
                    key = (xx % tw, y)
                    old = grid.get(key)
                    # surface normal of this puff, to light the side that faces the moon
                    ndx, ndy = dx / r, dy / r
                    if old is None or k > old[0]:
                        grid[key] = (k, ndx, ndy)
        for (x, y), (k, ndx, ndy) in grid.items():
            n = fbm(x * 0.15, y * 0.3, 2, sd) * 0.15
            kk = clamp(k + n)
            if kk < 0.03:
                continue
            # light: the rim facing the moon glows, the underside stays dark
            lx = mx - (x % w)
            ly = my - y * ASPECT
            ll = math.hypot(lx, ly) or 1.0
            facing = clamp((ndx * lx + ndy * ly) / ll)
            c = mix(night, lit_col, clamp(0.2 + facing * 0.9 + clamp(-ndy) * 0.3))
            ch = None
            rim = ((x + 1) % tw, y) not in grid or ((x - 1) % tw, y) not in grid or (x, y - 1) not in grid
            if rim and y > 0:
                # puff outline, drawn like the scrolling clouds of old paintings
                if ndy < -0.55:
                    ch = "~" if (x + y) % 3 else "-"
                elif ndx < 0:
                    ch = "(" if ndy < 0.3 else "/"
                else:
                    ch = ")" if ndy < 0.3 else "\\"
                if ndy > 0.4:
                    ch = None
                v = 0.35 + 0.45 * facing
            else:
                v = 0.06 + 0.1 * kk + 0.12 * facing * (1 - kk)
            v *= 0.75 if depth == 0 else 0.95
            cols[x].append((y, v, c, kk, ch))
        speed = rng.uniform(0.5, 1.0) * (2.0 if depth else 1.0) * rng.choice((-1, 1))
        return {"cols": cols, "speed": speed, "tw": tw, "depth": depth}

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        rng = self.rng
        t = self.t
        self.pt += dt
        px, py = self.pearl_pos(self.pt)
        hx, hy = self.pts[0]
        dx, dy = px - hx, py - hy
        dist = math.hypot(dx, dy)
        want = math.atan2(dy, dx)
        da = (want - self.ang + math.pi) % TAU - math.pi
        self.ang += clamp(da, -self.turn * dt, self.turn * dt)
        self.ang += math.sin(t * 1.3) * self.wiggle * dt
        sp = self.speed * clamp(dist / (self.R * 10), 0.55, 1.25)
        nx = hx + math.cos(self.ang) * sp * dt
        ny = hy + math.sin(self.ang) * sp * dt
        pts = self.pts
        pts[0] = (nx, ny)
        seg = self.seg
        for i in range(1, len(pts)):
            ax, ay = pts[i - 1]
            bx, by = pts[i]
            ex, ey = bx - ax, by - ay
            d = math.hypot(ex, ey) or 1.0
            pts[i] = (ax + ex / d * seg, ay + ey / d * seg)
        # fiery breath now and then
        self.next_breath -= dt
        if self.next_breath <= 0 and self.breath <= 0:
            self.breath = rng.uniform(1.0, 2.0)
            self.next_breath = rng.uniform(6, 12)
        if self.breath > 0:
            self.breath -= dt
            self.mouth = min(1.0, self.mouth + dt * 4)
            if self.mouth > 0.5:
                for _ in range(int(dt * 60) + (1 if rng.random() < (dt * 60) % 1 else 0)):
                    self.emit_spark()
        else:
            self.mouth = max(0.0, self.mouth - dt * 2)
        for s in self.sparks:
            s.age += dt
            s.x += s.vx * dt
            s.y += s.vy * dt
            s.vx *= 0.97 ** (dt * 30)
            s.vy = s.vy * 0.97 ** (dt * 30) - 3 * dt
        self.sparks = [s for s in self.sparks if s.age < s.life]

    def head_frame(self):
        hx, hy = self.pts[0]
        bx, by = self.pts[2]
        tx, ty = hx - bx, hy - by
        tl = math.hypot(tx, ty) or 1.0
        tx, ty = tx / tl, ty / tl
        # "up" for the head: the side of the body away from the belly
        nx, ny = -ty, tx
        if ny > 0:
            nx, ny = -nx, -ny
        return hx, hy, tx, ty, nx, ny

    def emit_spark(self):
        rng = self.rng
        hx, hy, tx, ty, nx, ny = self.head_frame()
        R = self.R
        s = Spark()
        mx = hx + tx * R * 2.6 - nx * R * 0.2
        my = hy + ty * R * 2.6 - ny * R * 0.2
        a = math.atan2(ty, tx) + rng.uniform(-0.35, 0.35)
        sp = rng.uniform(12, 26) * (R / 3) ** 0.5
        s.x, s.y = mx, my
        s.vx, s.vy = math.cos(a) * sp, math.sin(a) * sp
        s.life = rng.uniform(0.5, 1.2)
        s.age = 0.0
        self.sparks.append(s)

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        self.draw_sky(cv)
        for layer in self.layers:
            if layer["depth"] == 0:
                self.draw_clouds(cv, layer, front=False)
        self.draw_pearl(cv)
        self.draw_dragon(cv)
        self.draw_sparks(cv)
        for layer in self.layers:
            if layer["depth"] == 1:
                self.draw_clouds(cv, layer, front=True)

    def draw_sky(self, cv):
        t = self.t
        for x, y, b, ph in self.stars:
            v = (0.1 + 0.7 * b) * (0.65 + 0.35 * math.sin(t * (0.7 + b * 2) + ph))
            ch = "*" if v > 0.6 else "+" if v > 0.42 else "·" if v > 0.22 else "."
            cv.put(x, y, ch, scale((220, 225, 255), 0.3 + 0.7 * v), v * 0.5)
        for x, y, v, col, disk in self.moon_cells:
            if disk:
                cv.shade(x, y, v, col, "over")
            else:
                cv.shade(x, y, v, col)

    def draw_clouds(self, cv, layer, front):
        w, h = cv.w, cv.h
        tw = layer["tw"]
        off = int(self.t * layer["speed"]) % tw
        cols = layer["cols"]
        lv = cv.lv
        for x in range(w):
            for y, v, c, k, ch in cols[(x + off) % tw]:
                if ch is not None:
                    i = y * w + x
                    if front or lv[i] < v:
                        cv.put(x, y, ch, scale(c, 0.3 + 0.7 * v), v)
                elif front and k > 0.3:
                    cv.shade(x, y, max(v, 0.12), c, "over")      # near clouds veil what is behind
                else:
                    cv.shade(x, y, v, c)

    def draw_pearl(self, cv):
        px, py = self.pearl_pos(self.pt)
        t = self.t
        r = max(1.2, self.R * 0.75)
        col = (255, 235, 245)
        glow = (255, 170, 210)
        for y in range(int((py - r * 4) / ASPECT), int((py + r * 4) / ASPECT) + 1):
            for x in range(int(px - r * 4), int(px + r * 4) + 1):
                dx = x + 0.5 - px
                dy = (y + 0.5) * ASPECT - py
                d = math.sqrt(dx * dx + dy * dy) / r
                if d < 1:
                    cv.shade(x, y, 1.0 - 0.3 * d, mix(col, glow, d * 0.5), "over")
                elif d < 4:
                    a = math.atan2(dy, dx)
                    flick = 0.6 + 0.4 * math.sin(a * 5 + t * 4)
                    cv.shade(x, y, 0.45 * ((4 - d) / 3) ** 2 * flick, glow)

    def draw_dragon(self, cv):
        pts = self.pts
        n = len(pts) - 1
        R = self.R
        t = self.t
        widths = []
        for i in range(n + 1):
            s = i / n
            # neck, swelling body, long tapering tail
            wv = 0.62 + 0.5 * smoothstep(0.02, 0.16, s) - 0.05 * math.sin(s * 40)
            wv *= 1 - smoothstep(0.45, 1.0, s) * 0.85
            widths.append(R * wv + 0.35)
        body = self.body
        # tangents and normals per body point, for lighting and belly side
        normals = []
        for i in range(n + 1):
            a = pts[max(0, i - 1)]
            b = pts[min(n, i + 1)]
            tx, ty = b[0] - a[0], b[1] - a[1]
            tl = math.hypot(tx, ty) or 1.0
            normals.append((-ty / tl, tx / tl))
        mx, my = self.moon
        # legs on the far side go behind the body
        for li, ls in enumerate(self.legs):
            self.draw_leg(cv, ls + 0.025, far=True, normals=normals, widths=widths)
        self.draw_mane(cv, normals, widths, back=True)
        cells = {}
        stroke(cells, cv.w, cv.h, pts, widths, step=0.5)
        w = cv.w
        put, shade = cv.put, cv.shade
        belly = self.belly
        L = self.seg * n
        for key, (dn, s, side) in cells.items():
            y, x = divmod(key, w)
            idx = min(n, int(s * n + 0.5))
            nx, ny = normals[idx]
            # moonlight on a cylinder: direction to the moon from this point
            px, py = pts[idx]
            lx, ly = mx - px, my - py
            ll = math.hypot(lx, ly) or 1.0
            lx, ly = lx / ll, ly / ll
            nz = math.sqrt(max(0.0, 1 - dn * dn))
            ndot = side * (nx * lx + ny * ly) * 0.8 + nz * 0.6
            lit = clamp(0.25 + 0.75 * ndot)
            bside = side if ny > 0 else -side
            q = s * L / 1.5
            if bside > 0.35:
                # belly plates
                fq = (q * 1.3) % 1.0
                c = mix(belly, (90, 70, 40), 0.55 * (1 - lit))
                if fq < 0.25:
                    put(x, y, "-", scale(c, 0.55), 0.7)
                else:
                    put(x, y, "=", scale(c, 0.45 + 0.55 * lit), 0.8)
                continue
            # scales in staggered rows
            row = int((side + 1) * 2.2)
            fq = (q + 0.5 * (row & 1)) % 1.0
            edge = fq < 0.28
            v = 0.42 + 0.55 * lit - (0.22 if edge else 0)
            c = gradient(body, clamp(lit * (0.75 if edge else 1.0) + 0.1))
            if not edge and ((x * 7 + y * 13 + int(q)) % 23 == 0) and lit > 0.55:
                put(x, y, "*", mix(c, (255, 255, 240), 0.6), 1.0)     # a scale catching the light
                continue
            shade(x, y, clamp(v), c, "over")
        self.draw_spines(cv, normals, widths)
        self.draw_mane(cv, normals, widths, back=False)
        for ls in self.legs:
            self.draw_leg(cv, ls, far=False, normals=normals, widths=widths)
        self.draw_tail_tuft(cv, normals, widths)
        self.draw_head(cv, widths[0])

    @staticmethod
    def dorsal(normals, i):
        """The body normal that points upward: spines and mane go on that side."""
        nx, ny = normals[i]
        return (-nx, -ny) if ny > 0 else (nx, ny)

    def draw_spines(self, cv, normals, widths):
        pts = self.pts
        n = len(pts) - 1
        L = self.seg * n
        step = max(1, int(self.spine_gap * self.R / self.seg + 0.5))
        for i in range(3, int(n * 0.92), step):
            dx, dy = self.dorsal(normals, i)
            r = widths[i] + 0.7
            x = pts[i][0] + dx * r
            y = (pts[i][1] + dy * r) / ASPECT
            if abs(dy) > abs(dx) * 0.6:
                ch = "^" if dy < 0 else "v"
            else:
                ch = ">" if dx > 0 else "<"
            cv.put(x, y, ch, scale(self.mane, 0.9 - 0.4 * i / n), 0.8)

    def tuft(self, cv, x, y, dx, dy, length, width, phase, bright):
        """A flame-like tuft of hair streaming along (dx, dy) from (x, y) (aspect units)."""
        t = self.t
        m = 6
        pts = []
        px, py = x, y
        for q in range(m + 1):
            f = q / m
            wv = math.sin(t * 5 + phase - f * 4) * 0.45 * f
            ax, ay = dx - dy * wv, dy + dx * wv
            pts.append((px, py))
            px, py = px + ax * length / m, py + ay * length / m
        widths = [width * (1 - f / m) ** 0.8 + 0.25 for f in range(m + 1)]
        cells = {}
        stroke(cells, cv.w, cv.h, pts, widths)
        hot = mix(self.mane, (255, 250, 220), 0.45)
        for key, (dn, s, side) in cells.items():
            yy, xx = divmod(key, cv.w)
            c = mix(hot, self.mane, s) if dn < 0.5 else self.mane
            cv.shade(xx, yy, clamp((0.85 - 0.45 * s - 0.25 * dn) * bright), c, "over")

    def draw_mane(self, cv, normals, widths, back):
        pts = self.pts
        n = len(pts) - 1
        k = self.mane_n
        R = self.R
        for j in range(k):
            if (j % 2 == 0) != back:
                continue
            i = 1 + int(j * 0.1 * n / k)
            dx, dy = self.dorsal(normals, i)
            r = widths[i] * 0.7
            x, y = pts[i][0] + dx * r, pts[i][1] + dy * r
            bi = min(n, i + 3)
            bx, by = pts[bi][0] - pts[i][0], pts[bi][1] - pts[i][1]
            bl = math.hypot(bx, by) or 1.0
            ax, ay = bx / bl + dx * 0.9, by / bl + dy * 0.9
            al = math.hypot(ax, ay) or 1.0
            self.tuft(cv, x, y, ax / al, ay / al, R * (1.8 + 0.6 * math.sin(j * 1.7)), R * 0.45, j * 1.3,
                      0.7 if back else 1.0)

    def draw_tail_tuft(self, cv, normals, widths):
        pts = self.pts
        n = len(pts) - 1
        ex, ey = pts[n - 1]
        bx, by = ex - pts[n - 4][0], ey - pts[n - 4][1]
        bl = math.hypot(bx, by) or 1.0
        bx, by = bx / bl, by / bl
        for j in range(3):
            spread = (j - 1) * 0.45
            ca, sa = math.cos(spread), math.sin(spread)
            self.tuft(cv, ex, ey, bx * ca - by * sa, bx * sa + by * ca, self.R * 2.4, self.R * 0.55, j * 2.1, 1.0)

    def draw_leg(self, cv, s, far, normals, widths):
        pts = self.pts
        n = len(pts) - 1
        i = min(n - 1, max(1, int(s * n)))
        nx, ny = normals[i]
        bnx, bny = (nx, ny) if ny > 0 else (-nx, -ny)               # toward the belly
        tx, ty = pts[i - 1][0] - pts[i + 1][0], pts[i - 1][1] - pts[i + 1][1]
        tl = math.hypot(tx, ty) or 1.0
        tx, ty = tx / tl, ty / tl                                  # toward the head
        R = self.R
        ph = self.t * 3 + s * 20 + (1.5 if far else 0)
        swing = 0.5 * math.sin(ph)
        x0 = pts[i][0] + bnx * widths[i] * 0.6
        y0 = pts[i][1] + bny * widths[i] * 0.6
        # thigh goes down-back, shin forward, then claws
        a1x, a1y = bnx * 0.8 - tx * (0.5 + swing), bny * 0.8 - ty * (0.5 + swing)
        k1 = math.hypot(a1x, a1y) or 1.0
        x1, y1 = x0 + a1x / k1 * R * 1.3, y0 + a1y / k1 * R * 1.3
        a2x, a2y = bnx * 0.6 + tx * (0.6 - swing), bny * 0.6 + ty * (0.6 - swing)
        k2 = math.hypot(a2x, a2y) or 1.0
        x2, y2 = x1 + a2x / k2 * R * 1.1, y1 + a2y / k2 * R * 1.1
        cells = {}
        stroke(cells, cv.w, cv.h, [(x0, y0), (x1, y1), (x2, y2)], [R * 0.5, R * 0.42, R * 0.3])
        dim = 0.55 if far else 1.0
        for key, (dn, ss, side) in cells.items():
            y, x = divmod(key, cv.w)
            cv.shade(x, y, clamp((0.75 - 0.35 * dn) * dim), gradient(self.body, 0.6 - 0.3 * dn), "over")
        # claws: three hooks fanned at the foot
        cc = scale(self.horn, dim)
        for k in (-1, 0, 1):
            ang = math.atan2(a2y, a2x) + k * 0.6
            cx, cy = x2 + math.cos(ang) * R * 0.7, y2 + math.sin(ang) * R * 0.7
            cv.put(cx, cy / ASPECT, dir_glyph(math.cos(ang), math.sin(ang)), cc, 0.9)

    def draw_head(self, cv, neck_w):
        R = self.R
        hx, hy, tx, ty, nx, ny = self.head_frame()
        t = self.t
        mouth = self.mouth
        put = cv.put
        body = self.body
        # skull: from the neck to the snout, a little above the axis
        L = R * 4.6
        skull = []
        wid = []
        for k in range(7):
            f = k / 6
            bump = 0.18 * math.sin(f * math.pi * 1.2)     # brow
            skull.append((hx + tx * L * f + nx * R * bump, hy + ty * L * f + ny * R * bump))
            wid.append(R * (1.55 - 0.85 * f ** 1.2) + 0.3)
        # lower jaw hinges open when breathing fire
        ja = 0.12 + 0.45 * mouth
        jdx = tx * math.cos(ja) - nx * math.sin(ja)
        jdy = ty * math.cos(ja) - ny * math.sin(ja)
        j0x, j0y = hx + tx * L * 0.25 - nx * R * 0.55, hy + ty * L * 0.25 - ny * R * 0.55
        jaw = [(j0x + jdx * L * 0.75 * f, j0y + jdy * L * 0.75 * f) for f in (0, 0.5, 1)]
        jw = [R * 0.55, R * 0.42, R * 0.25]
        cells = {}
        stroke(cells, cv.w, cv.h, jaw, jw)
        for key, (dn, s, side) in cells.items():
            y, x = divmod(key, cv.w)
            cv.shade(x, y, clamp(0.75 - 0.3 * dn), mix(self.belly, body[1], 0.4), "over")
        if mouth > 0.3:       # teeth and a glowing throat
            for f in (0.45, 0.65, 0.85):
                qx, qy = jaw[0][0] + (jaw[2][0] - jaw[0][0]) * f, jaw[0][1] + (jaw[2][1] - jaw[0][1]) * f
                put(qx + nx * R * 0.4, (qy + ny * R * 0.5) / ASPECT, "^" if ny < 0 else "v", (255, 250, 240), 1)
        cells = {}
        stroke(cells, cv.w, cv.h, skull, wid)
        mx, my = self.moon
        for key, (dn, s, side) in cells.items():
            y, x = divmod(key, cv.w)
            up = side * (1 if (-ty * nx + tx * ny) > 0 else -1)
            lit = clamp(0.5 + 0.35 * up + 0.3 * math.sqrt(max(0.0, 1 - dn * dn)))
            c = gradient(body, lit)
            if up < -0.45:
                c = mix(c, self.belly, 0.5)
            if dn > 0.82:     # a dark outline separates the head from the body
                cv.shade(x, y, 0.35, gradient(body, 0.15), "over")
                continue
            cv.shade(x, y, clamp(0.55 + 0.45 * lit), c, "over")
        # nostril and snout tip
        sx, sy = skull[-1]
        put(sx + tx * 0.6, (sy + ty * 0.6) / ASPECT, "o", scale(body[0], 1.0), 1)
        # horns: antlers sweeping back from the top of the head
        bx, by = hx + tx * L * 0.15 + nx * R * 0.9, hy + ty * L * 0.15 + ny * R * 0.9
        for side_k, dim in ((1, 1.0), (-1, 0.6)):
            hxp, hyp = bx + tx * R * 0.3 * side_k, by + ty * R * 0.3 * side_k
            ang = math.atan2(-ty * 0.8 + ny * 0.7, -tx * 0.8 + nx * 0.7) + 0.15 * side_k
            m = int(self.horn_len * R / 0.6) + 2
            px, py = hxp, hyp
            for q in range(m):
                f = q / m
                ang2 = ang + 0.5 * f * (1 if ny < 0 else -1) * (1 if tx > 0 else -1) * -1
                qx, qy = px + math.cos(ang2) * 0.6, py + math.sin(ang2) * 0.6
                put(qx, qy / ASPECT, dir_glyph(qx - px, qy - py), scale(self.horn, dim * (1 - 0.3 * f)), 1)
                if self.horn_tines and q in (m // 2, m // 3 * 2)[: self.horn_tines] and side_k > 0:
                    ta = ang2 + 0.9 * (1 if ny < 0 else -1)
                    for e in (1, 2):
                        ex, ey = qx + math.cos(ta) * 0.6 * e, qy + math.sin(ta) * 0.6 * e
                        put(ex, ey / ASPECT, dir_glyph(math.cos(ta), math.sin(ta)), scale(self.horn, dim * 0.8), 1)
                px, py = qx, qy
        # glowing eye with a little halo
        ex, ey = hx + tx * L * 0.42 + nx * R * 0.45, hy + ty * L * 0.42 + ny * R * 0.45
        for ox in (-1, 1):
            cv.shade(ex + ox, ey / ASPECT, 0.5, self.eye)
        put(ex, ey / ASPECT, "@", mix(self.eye, (255, 255, 230), 0.4 + 0.3 * math.sin(t * 3)), 1)
        # whiskers: long barbels streaming from the snout
        for j, side_k in enumerate((1, -1)):
            px, py = sx - nx * R * 0.2 * side_k, sy - ny * R * 0.2 * side_k
            m = int(self.whisker_len * R / 0.7) + 3
            ang = math.atan2(-ty, -tx) + side_k * 0.5
            for q in range(m):
                f = q / m
                ang2 = ang + math.sin(t * 2.5 + j * 2 - f * 6) * 0.9 * f - side_k * 0.4 * f
                qx, qy = px + math.cos(ang2) * 0.7, py + math.sin(ang2) * 0.7
                put(qx, qy / ASPECT, dir_glyph(qx - px, qy - py), scale(self.whisker, 1 - 0.55 * f), 0.8)
                px, py = qx, qy

    def draw_sparks(self, cv):
        for s in self.sparks:
            f = s.age / s.life
            col = gradient([(255, 255, 220), (255, 210, 80), (255, 110, 30), (180, 30, 20)], f)
            ch = "@" if f < 0.15 else "*" if f < 0.4 else "+" if f < 0.65 else "·" if f < 0.85 else "."
            cv.put(s.x, s.y / ASPECT, ch, col, 1 - f)
