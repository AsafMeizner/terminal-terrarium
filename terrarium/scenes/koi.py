"""A koi pond seen from above: koi winding under lily pads and lotus flowers, ripples, caustic shimmer."""
import math

from ..engine import ASPECT, Scene, clamp, mix, noise1, noise2

TAU = math.tau
WHITE = (250, 248, 240)
RED = (236, 70, 30)
ORANGE = (255, 140, 30)
BLACK = (30, 30, 40)
GOLD = (255, 200, 80)
BLUEGREY = (120, 140, 170)

# variety -> base colour and patch colours
VARIETIES_ALL = ["kohaku", "sanke", "showa", "tancho", "ogon", "asagi", "chagoi", "kohaku"]
# water mood: caustic colour, mote colour
WATERS = [((60, 150, 170), (120, 150, 140)), ((50, 110, 180), (110, 130, 170)), ((70, 160, 120), (130, 160, 120)),
          ((90, 120, 170), (150, 140, 170))]
# lotus: tip colour, base colour
LOTUS = [((255, 110, 170), (255, 236, 244)), ((255, 255, 250), (255, 250, 220)), ((230, 80, 200), (255, 220, 245)),
         ((255, 150, 120), (255, 240, 220))]


class Koi:
    def __init__(self, rng, w, h, L, depth, kinds):
        self.L = L                                  # body length, x cells
        self.W = L * rng.uniform(0.105, 0.125)       # half width at the widest: body about 4x as long as wide
        self.depth = depth                          # 0 deep .. 1 near the surface
        self.x = rng.uniform(0.15, 0.85) * w
        self.y = rng.uniform(0.15, 0.85) * h * ASPECT   # aspect-corrected units
        self.ang = rng.uniform(0, TAU)
        self.speed = rng.uniform(2.2, 3.6) * (L / 14)
        self.seed = rng.randrange(1 << 12)
        self.kind = rng.choice(kinds)
        self.patch = rng.uniform(-0.2, 0.25)      # how much red: each fish its own genome
        self.pscale = rng.uniform(2.5, 5.5)
        self.phase = rng.uniform(0, TAU)
        n = 16
        self.n = n
        self.seg = L / n
        self.pts = [(self.x - math.cos(self.ang) * self.seg * i, self.y - math.sin(self.ang) * self.seg * i)
                    for i in range(n + 1)]
        self.surface = 0.0
        self.next_surface = rng.uniform(6, 20)


class Pad:
    def __init__(self, rng, x, y, r):
        self.x, self.y, self.r = x, y, r            # y aspect-corrected
        self.rot = rng.uniform(0, TAU)
        self.notch = rng.uniform(0.3, 0.45)
        self.drift = (rng.uniform(-0.05, 0.05), rng.uniform(-0.03, 0.03))
        self.spin = rng.uniform(-0.02, 0.02)
        self.lotus = 0.0
        self.ph = rng.uniform(0, TAU)
        self.veins = rng.randrange(9, 14)


def _texture(rng, tw, th):
    """A periodic ridged-wave texture (values 0..1) for caustics."""
    waves = []
    for _ in range(9):
        fx, fy = rng.randint(-4, 4), rng.randint(-3, 3)
        if fx == 0 and fy == 0:
            fx = 1
        waves.append((fx * TAU / tw, fy * TAU / th, rng.uniform(0, TAU), rng.uniform(0.5, 1.0)))
    norm = sum(wv[3] for wv in waves)
    tex = []
    for j in range(th):
        row = []
        for i in range(tw):
            v = sum(a * math.sin(fx * i + fy * j + ph) for fx, fy, ph, a in waves) / norm
            row.append((1 - min(1.0, abs(v) * 2.2)) ** 3)
        tex.append(row)
    return tex


class KoiPond(Scene):
    name = "koi"
    title = "Koi Pond"
    blurb = "koi winding under lily pads and lotus flowers, ripples spreading on the water"
    tags = ("water", "nature", "calm", "zen")
    options = {
        "fish": (0, "number of koi (0 = based on screen size)"),
        "pads": (1.0, "amount of lily pads (0 = none)"),
        "ripples": (True, "ripple rings on the water"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        big = min(w, h * ASPECT)
        # a little generative grammar: pond mood, fish size and crowd, pad density, lotus colour
        self.water = rng.choice(WATERS)
        L = max(12.0, big * rng.uniform(0.4, 0.48))
        crowd = rng.uniform(0.6, 1.5)
        n = self.opt("fish") or max(2, min(10, int(round(1.6 * crowd * (w * h) / 5000 * self.density)) + 1))
        self.varieties = rng.sample(VARIETIES_ALL, rng.randint(2, 5))
        self.fish = [Koi(rng, w, h, L * rng.uniform(0.75, 1.15), (k + rng.random()) / n, self.varieties)
                     for k in range(n)]
        self.lotus_col = rng.choice(LOTUS)
        self.fish.sort(key=lambda f: f.depth)
        self.pads = []
        amount = self.opt("pads")
        npads = int(round(max(0, amount) * rng.uniform(0.4, 1.4) * max(2, w * h / 900)))
        tries = 0
        while len(self.pads) < npads and tries < npads * 30:
            tries += 1
            r = big * rng.uniform(0.07, 0.13)
            x = rng.uniform(0, w)
            y = rng.uniform(0, h * ASPECT)
            if any(math.hypot(x - p.x, y - p.y) < (r + p.r) * 0.95 for p in self.pads):
                continue
            pad = Pad(rng, x, y, r)
            self.pads.append(pad)
        for k, pad in enumerate(self.pads):
            if rng.random() < 0.5 and pad.r > 2.5:
                pad.lotus = pad.r * rng.uniform(0.85, 1.05)
        self.tw, self.th = 72, 40
        self.texA = _texture(rng, self.tw, self.th)
        self.texB = _texture(rng, self.tw, self.th)
        self.ripples = []
        self.next_ripple = rng.uniform(0.5, 2)
        self.motes = [[rng.uniform(0, w), rng.uniform(0, h * ASPECT), rng.uniform(0, TAU)] for _ in range(max(4, w * h // 400))]

    # ------------------------------------------------------------------ motion
    def update(self, dt):
        super().update(dt)
        rng = self.rng
        w, H = self.w, self.h * ASPECT
        t = self.t
        for f in self.fish:
            # wander, steer back from the edges, keep a little apart
            turn = noise1(t * 0.25 + f.seed, f.seed) * 1.1
            mx, my = w * 0.12, H * 0.14
            tx = ty = 0.0
            if f.x < mx:
                tx = 1
            elif f.x > w - mx:
                tx = -1
            if f.y < my:
                ty = 1
            elif f.y > H - my:
                ty = -1
            if tx or ty:
                want = math.atan2(ty, tx)
                d = (want - f.ang + math.pi) % TAU - math.pi
                turn += d * 1.6
            for o in self.fish:
                if o is f:
                    continue
                dx, dy = o.x - f.x, o.y - f.y
                dd = dx * dx + dy * dy
                if dd < (f.L * 0.6) ** 2 and abs(o.depth - f.depth) < 0.3:
                    side = math.sin(math.atan2(dy, dx) - f.ang)
                    turn -= 0.8 * (1 if side > 0 else -1)
            f.ang += clamp(turn, -1.6, 1.6) * dt
            sp = f.speed * (0.8 + 0.3 * math.sin(t * 0.4 + f.phase))
            f.x += math.cos(f.ang) * sp * dt
            f.y += math.sin(f.ang) * sp * dt
            f.phase += dt * (2.0 + sp * 0.6)
            # follow-the-leader body
            pts = [(f.x, f.y)]
            seg = f.seg
            for i in range(1, f.n + 1):
                px, py = f.pts[i]
                qx, qy = pts[-1]
                dx, dy = px - qx, py - qy
                d = math.hypot(dx, dy) or 1.0
                pts.append((qx + dx / d * seg, qy + dy / d * seg))
            f.pts = pts
            # come up to the surface now and then
            f.next_surface -= dt
            if f.next_surface <= 0:
                f.surface = 1.0
                f.next_surface = rng.uniform(10, 25)
                if self.opt("ripples"):
                    self.ripples.append([f.x + math.cos(f.ang) * seg, f.y + math.sin(f.ang) * seg, 0.0,
                                         f.L * 0.9, 1.0])
            f.surface = max(0.0, f.surface - dt * 0.4)
        for p in self.pads:
            p.x += p.drift[0] * dt
            p.y += p.drift[1] * dt
            p.rot += p.spin * dt
        if self.opt("ripples"):
            self.next_ripple -= dt
            if self.next_ripple <= 0:
                self.next_ripple = rng.uniform(1.0, 3.5)
                self.ripples.append([rng.uniform(0, w), rng.uniform(0, H), 0.0,
                                     min(w, H) * rng.uniform(0.12, 0.25), rng.uniform(0.5, 0.9)])
        keep = []
        for r in self.ripples:
            r[2] += dt * (2.2 + r[3] * 0.08)
            if r[2] < r[3]:
                keep.append(r)
        self.ripples = keep[-40:]

    # ------------------------------------------------------------------ drawing
    def draw(self, cv):
        self.draw_water(cv)
        for f in self.fish:
            self.draw_fish(cv, f)
        self.draw_ripples(cv)
        for p in self.pads:
            self.draw_pad(cv, p)
        for p in self.pads:
            if p.lotus:
                self.draw_lotus(cv, p)

    def draw_water(self, cv):
        t = self.t
        w, h = cv.w, cv.h
        tw, th = self.tw, self.th
        A, B = self.texA, self.texB
        ax, ay = t * 1.1, t * 0.45
        bx, by = -t * 0.8, t * 0.7
        shade = cv.shade
        col = self.water[0]
        xa = [int(x * 0.5 + ax) % tw for x in range(w)]
        xb = [int(x * 0.5 + bx) % tw for x in range(w)]
        for y in range(h):
            ra = A[int(y * ASPECT * 0.5 + ay) % th]
            rb = B[int(y * ASPECT * 0.5 + by) % th]
            for x, c in enumerate([ra[i] * rb[j] for i, j in zip(xa, xb)]):
                if c > 0.08:
                    shade(x, y, (c - 0.08) * 0.5, col)
        for mx, my, ph in self.motes:
            tw2 = 0.5 + 0.5 * math.sin(t * 0.7 + ph)
            shade(mx + math.sin(t * 0.1 + ph) * 2, my / ASPECT, 0.05 + 0.08 * tw2, self.water[1])

    def koi_color(self, f, s, q):
        """Pattern colour at body position s (0 head..1 tail), q (-1..1 across)."""
        kind = f.kind
        n = noise2(s * f.pscale + f.seed, q * 1.3 + f.seed * 0.37, f.seed) + f.patch
        if kind == "kohaku":
            return RED if n > 0.05 and s < 0.85 else WHITE
        if kind == "sanke":
            if n > 0.1 and s < 0.85:
                return RED
            m = noise2(s * 9 + 3.1, q * 3 + f.seed, f.seed + 1)
            return BLACK if m > 0.55 else WHITE
        if kind == "showa":
            if n > 0.15:
                return RED
            return WHITE if n < -0.35 else BLACK
        if kind == "tancho":
            d = (s - 0.12) ** 2 * 30 + q * q
            return RED if d < 0.35 else WHITE
        if kind == "ogon":
            return mix(GOLD, (255, 240, 180), 0.5 + 0.5 * n)
        if kind == "asagi":
            return ORANGE if abs(q) > 0.62 or s < 0.1 else mix(BLUEGREY, (170, 190, 220), 0.5 + 0.5 * n)
        return mix((200, 130, 70), (230, 170, 100), 0.5 + 0.5 * n)   # chagoi

    def draw_fish(self, cv, f):
        t = self.t
        pts = f.pts
        n = f.n
        W = f.W
        dim = 0.62 + 0.38 * f.depth + 0.2 * f.surface
        deep = (1 - f.depth) * 0.35
        tint = (40, 70, 110)
        shade = cv.shade
        # body centre line with a travelling swim wave
        cl = []
        for i in range(n + 1):
            px, py = pts[i]
            if i < n:
                dx, dy = pts[i][0] - pts[i + 1][0], pts[i][1] - pts[i + 1][1]
            else:
                dx, dy = pts[i - 1][0] - pts[i][0], pts[i - 1][1] - pts[i][1]
            d = math.hypot(dx, dy) or 1.0
            ux, uy = dx / d, dy / d
            s = i / n
            wave = math.sin(f.phase - s * 4.2) * W * 0.55 * s ** 1.3
            cl.append((px - uy * wave, py + ux * wave, ux, uy))
        pat = getattr(f, "pat", None)
        if pat is None:     # the colour pattern is fixed per fish: sample it once
            pat = f.pat = [[self.koi_color(f, i / 31, j / 6 - 1) for j in range(13)] for i in range(32)]
        fin_col = mix((240, 240, 235), self.koi_color(f, 0.5, 0.0), 0.35)

        def fin(x0, y0, ang, length, width, v0, prof):
            """A translucent filled fin: a blade from (x0, y0) along ang, half width = width * prof(g)."""
            ca, sa = math.cos(ang), math.sin(ang)
            px, py = -sa, ca
            steps = max(3, int(length * 1.5))
            c = mix(fin_col, tint, deep)
            for k in range(1, steps + 1):
                g = k / steps
                hw = width * prof(g)
                ns = max(1, int(hw * 1.5))
                cx, cy = x0 + ca * length * g, y0 + sa * length * g
                for j in range(-ns, ns + 1):
                    q = j / ns
                    edge = abs(q) > 0.66 or g > 0.85
                    v = 0.56 if edge else 0.3                # crisp light rim, sheer membrane
                    shade(cx + px * hw * q, (cy + py * hw * q) / ASPECT, v, mix(c, (255, 255, 255), 0.2 if edge else 0.0),
                          "max", False)

        # forked tail: two pointed lobes with a notch between them
        hx, hy, ux, uy = cl[n]
        heading = math.atan2(-uy, -ux)
        flap = math.sin(f.phase - 4.2) * 0.4
        lobe = lambda g: (g ** 0.6) * (1 - g) ** 0.7 * 2.2
        for side in (-1, 1):
            fin(hx, hy, heading + flap + side * 0.42, f.L * 0.3, f.W * 0.55, 0.5, lobe)
        # pectoral fins: rounded paddles that flutter
        px, py, ux, uy = cl[3]
        back = math.atan2(-uy, -ux)
        paddle = lambda g: math.sin(math.pi * min(1.0, g * 0.9 + 0.1)) ** 0.7
        for side in (-1, 1):
            flut = 0.3 * math.sin(t * 3.0 + f.phase + side)
            fin(px - uy * side * W * 0.75, py + ux * side * W * 0.75, back - side * (1.0 + flut), f.L * 0.2,
                f.W * 0.45, 0.5, paddle)
        # little dorsal-side pelvic fins further back
        px, py, ux, uy = cl[9]
        for side in (-1, 1):
            fin(px - uy * side * W * 0.45, py + ux * side * W * 0.45, back - side * 0.7, f.L * 0.1, f.W * 0.25,
                0.45, paddle)
        # body: splat tail to head so the head ends on top
        for i in range(n, -1, -1):
            s = i / n
            if s < 0.3:
                wd = W * math.sqrt(max(0.0, 1 - ((0.3 - s) / 0.33) ** 2))
            else:
                wd = W * (1 - 0.78 * ((s - 0.3) / 0.7) ** 1.25)
            cx, cy, ux, uy = cl[i]
            nx, ny = -uy, ux
            sub = 2 if i < n else 1
            for half in range(sub):
                if i == n and half:
                    break
                # interpolate toward the next point for a solid body
                if half:
                    jx, jy, _, _ = cl[i + 1] if i + 1 <= n else cl[i]
                    cx2, cy2 = (cx + jx) / 2, (cy + jy) / 2
                else:
                    cx2, cy2 = cx, cy
                ns = max(1, int(wd * 1.8))
                for j in range(-ns, ns + 1):
                    q = j / ns
                    x = cx2 + nx * wd * q
                    y = cy2 + ny * wd * q
                    rnd = math.sqrt(max(0.0, 1 - q * q))
                    # light from the upper left: the side facing it is brighter
                    side_lit = -(nx * q) * 0.55 - (ny * q) * 0.45
                    lam = clamp(0.35 + 0.5 * rnd + 0.3 * side_lit)
                    col = pat[int(s * 31)][int((q + 1) * 6 + 0.5)]
                    if abs(q) < 0.18 and 0.25 < s < 0.7:      # dorsal ridge
                        lam = min(1.0, lam + 0.12)
                    col = mix(col, tint, deep)
                    br = min(1.0, (0.68 + 0.4 * lam) * dim)
                    # few glyph bands (the colour carries the gradient): rim, flank, back
                    aq = abs(q)
                    v = 0.62 if aq > 0.72 else 0.78 if aq > 0.3 else 0.9
                    shade(x, y / ASPECT, v * (0.85 + 0.15 * dim), (col[0] * br, col[1] * br, col[2] * br),
                          "over", False)
        # eyes
        ex, ey, ux, uy = cl[1]
        for side in (-1, 1):
            cv.put(ex - uy * side * W * 0.55, (ey + ux * side * W * 0.55) / ASPECT, "·", (20, 20, 25))

    def draw_ripples(self, cv):
        for x, y, r, mr, k in self.ripples:
            f = r / mr
            a = k * (1 - f) ** 1.5 * min(1.0, r * 0.8)
            if a <= 0.02:
                continue
            for ring, kk in ((r, 1.0), (r * 0.72, 0.5)):
                if ring < 0.5:
                    continue
                m = max(8, int(ring * 7))
                for i in range(m):
                    ang = TAU * i / m
                    cv.shade(x + math.cos(ang) * ring, (y + math.sin(ang) * ring) / ASPECT, 0.45 * a * kk,
                             (170, 220, 230))

    def draw_pad(self, cv, p):
        r = p.r
        x0, x1 = int(p.x - r) - 1, int(p.x + r) + 2
        y0, y1 = int((p.y - r) / ASPECT) - 1, int((p.y + r) / ASPECT) + 2
        dark, light = (20, 80, 40), (110, 190, 90)
        shade = cv.shade
        bob = 0.04 * math.sin(self.t * 0.6 + p.ph)
        for y in range(max(0, y0), min(cv.h, y1)):
            dy = (y + 0.5) * ASPECT - p.y
            for x in range(max(0, x0), min(cv.w, x1)):
                dx = x + 0.5 - p.x
                d = math.hypot(dx, dy) / r
                if d > 1.0:
                    continue
                a = (math.atan2(dy, dx) - p.rot) % TAU
                if a < p.notch * (0.2 + d) or a > TAU - p.notch * 0.05:
                    continue                                # the notch
                vein = 0.5 + 0.5 * math.cos((a + bob) * p.veins)
                lam = clamp(0.55 - 0.35 * (dx + dy) / r * 0.5 + 0.15 * vein * d)
                rim = d > 0.88
                v = 0.78 if rim else 0.62 if vein > 0.88 else 0.5      # few glyph bands
                col = mix(dark, light, lam)
                if rim:
                    col = mix(col, (170, 210, 120), 0.4)
                if d < 0.12:
                    col = mix(col, (150, 190, 90), 0.5)
                shade(x, y, v, col, "over", False)

    def draw_lotus(self, cv, p):
        R = p.lotus
        cx, cy = p.x + p.r * 0.1, p.y - p.r * 0.05
        t = self.t
        shade = cv.shade
        x0, x1 = int(cx - R) - 1, int(cx + R) + 2
        y0, y1 = int((cy - R) / ASPECT) - 1, int((cy + R) / ASPECT) + 2
        tip, base = self.lotus_col
        rot = p.rot * 2 + 0.05 * math.sin(t * 0.5 + p.ph)
        for y in range(max(0, y0), min(cv.h, y1)):
            dy = (y + 0.5) * ASPECT - cy
            for x in range(max(0, x0), min(cv.w, x1)):
                dx = x + 0.5 - cx
                d = math.hypot(dx, dy) / R
                if d > 1.0:
                    continue
                a = math.atan2(dy, dx) - rot
                if d < 0.24:                                 # seed pod
                    pod = 0.5 + 0.5 * math.cos(dx * 3) * math.cos(dy * 3)
                    shade(x, y, 0.6 + 0.3 * pod, mix((230, 200, 60), (255, 240, 140), pod), "over", False)
                    continue
                # outer ring of 8 pointed petals, inner ring of 8 offset ones
                best = None
                for ring, k0, rmax, wd in ((1, 0.5, 0.62, 0.42), (0, 0.0, 1.0, 0.36)):
                    sector = TAU / 8
                    u = (a / sector + k0) % 1.0 - 0.5           # -0.5..0.5 across a petal
                    reach = rmax * (1 - (abs(u) / wd) ** 1.6) if abs(u) < wd else 0
                    if d < reach:
                        best = (ring, u / wd, d / rmax)
                        break
                if best is None:
                    continue
                ring, q, g = best
                lam = clamp(0.6 + 0.35 * (1 - abs(q)) - 0.25 * q * (1 if dx > 0 else -1) + 0.15 * ring)
                col = mix(base, tip, clamp((g - 0.35) / 0.65) ** 1.2)
                v = 0.4 + 0.55 * lam
                if abs(q) > 0.8:
                    v *= 0.7
                br = 0.55 + 0.45 * lam
                shade(x, y, v, (col[0] * br, col[1] * br, col[2] * br), "over", False)
