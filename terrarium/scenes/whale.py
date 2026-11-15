"""A giant humpback whale (and maybe her calf) gliding through deep blue water, or through space."""
import math

from ..engine import ASPECT, Scene, clamp, fbm, gradient, hsv, mix, noise1, noise2, scale, smoothstep

TAU = math.tau

# ----------------------------------------------------------------------------- shared drawing helpers
# (the manta, octopus and dragon scenes import these too)


def edge_glyph(e):
    """Pick (row, char) that best places a horizontal outline at fractional row e."""
    c1 = round(e - 0.9)   # '_' sits near the bottom of its cell
    c2 = round(e - 0.5)   # '-' sits in the middle
    if abs(c1 + 0.9 - e) <= abs(c2 + 0.5 - e):
        return c1, "_"
    return c2, "-"


def dir_glyph(dx, dy):
    """A line glyph for a direction given in aspect-corrected units (dy grows downward)."""
    if dx == 0 and dy == 0:
        return "-"
    a = math.atan2(dy, dx) % math.pi       # 0..pi
    if a < 0.42 or a > 2.72:
        return "-"
    if a < 1.2:
        return "\\"
    if a < 1.94:
        return "|"
    return "/"


def raster_chain(cv, pts, widths, shade_fn):
    """Rasterize a tapered tube given as points (x cells, y aspect units) and half-widths.

    shade_fn(x, y, s, side, gx, gy) is called for every covered cell: s is the 0..1 position along
    the chain, side the signed lateral offset (-1..1) and (gx, gy) the local chain direction.
    """
    n = len(pts)
    if n < 2:
        return
    wmax = max(widths)
    bx0 = int(min(p[0] for p in pts) - wmax - 1)
    bx1 = int(max(p[0] for p in pts) + wmax + 2)
    by0 = int((min(p[1] for p in pts) - wmax) / ASPECT - 1)
    by1 = int((max(p[1] for p in pts) + wmax) / ASPECT + 2)
    segs = []
    for i in range(n - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy
        w0, w1 = widths[i], widths[i + 1]
        wm = max(w0, w1)
        segs.append((ax, ay, dx, dy, ll if ll > 1e-9 else 1e-9, w0, w1 - w0, i,
                     min(ax, bx) - wm, max(ax, bx) + wm, min(ay, by) - wm, max(ay, by) + wm))
    inv = 1.0 / (n - 1)
    sqrt = math.sqrt
    for y in range(max(0, by0), min(cv.h, by1)):
        py = (y + 0.5) * ASPECT
        rows = [sg for sg in segs if sg[10] <= py <= sg[11]]
        if not rows:
            continue
        rx0 = max(0, bx0, int(min(sg[8] for sg in rows)))
        rx1 = min(cv.w, bx1, int(max(sg[9] for sg in rows)) + 1)
        for x in range(rx0, rx1):
            px = x + 0.5
            best = 1.0
            hit = None
            for ax, ay, dx, dy, ll, w0, dw, i, lx, hx, _, _ in rows:
                if px < lx or px > hx:
                    continue
                ox = px - ax
                oy = py - ay
                t = (ox * dx + oy * dy) / ll
                if t < 0.0:
                    t = 0.0
                elif t > 1.0:
                    t = 1.0
                ex = ox - dx * t
                ey = oy - dy * t
                wr = w0 + dw * t
                if wr <= 0.05:
                    continue
                d2 = (ex * ex + ey * ey) / (wr * wr)
                if d2 < best:
                    best = d2
                    hit = (i + t, dx * ey - dy * ex, dx, dy)
            if hit is not None:
                d = sqrt(best)
                shade_fn(x, y, hit[0] * inv, d if hit[1] > 0 else -d, hit[2], hit[3])


class Ring:
    def __init__(self, x, y, speed, life, col):
        self.x, self.y = x, y
        self.r = 0.0
        self.speed = speed
        self.life = life
        self.age = 0.0
        self.col = col


# ----------------------------------------------------------------------------- the whale

BACK = [(14, 26, 64), (28, 58, 122), (58, 112, 190), (130, 195, 250), (220, 245, 255)]
BACK_DARK = [(10, 16, 40), (22, 40, 86), (44, 80, 140), (100, 150, 205), (200, 230, 250)]
BELLY = [(58, 72, 108), (125, 145, 182), (195, 212, 235), (245, 250, 255)]
FIN = [(80, 100, 140), (170, 195, 225), (225, 238, 250), (255, 255, 255)]


class Whale:
    """One humpback with its own genome."""

    def __init__(self, rng, L, x, y, facing, calf=False):
        self.L = L
        self.calf = calf
        self.x, self.y = x, y            # head position (cells, rows)
        self.facing = facing             # +1 swims right, -1 left
        self.depth = rng.uniform(0.2, 0.235) * (1.12 if calf else 1.0)   # body depth / length
        self.jaw = rng.uniform(0.0, 0.25)           # how deep the throat pouch is
        self.arch = rng.uniform(0.01, 0.03)         # how arched the back is
        self.fin_len = rng.uniform(0.29, 0.34) * (0.9 if calf else 1.0)
        self.fin_w = rng.uniform(0.026, 0.032)
        self.dorsal = rng.uniform(0.25, 0.7)        # dorsal hump size
        self.dorsal_u = rng.uniform(0.6, 0.67)
        self.belly_line = rng.uniform(0.15, 0.45)   # how far the white belly reaches up
        self.mottle = rng.uniform(0.2, 0.6)
        self.dark = rng.random() < 0.4
        self.seed = rng.randrange(1 << 16)
        self.beat = rng.uniform(0.12, 0.17) * (1.6 if calf else 1.0)    # tail beats per second
        self.amp = rng.uniform(0.035, 0.05)
        self.phase = rng.uniform(0, TAU)
        self.fin_rate = rng.uniform(0.07, 0.12)
        self.fin_amp = rng.uniform(0.15, 0.25)
        self.fin_base = rng.uniform(0.7, 0.92)
        self.fin_phase = rng.uniform(0, TAU)
        self.fluke_span = rng.uniform(0.15, 0.18)
        self.fluke_white = rng.uniform(0.25, 0.85)   # each humpback's fluke pattern is unique
        ntub = rng.randint(5, 10)
        self.tubercles = sorted(rng.uniform(0.015, 0.2) for _ in range(ntub))
        self.barnacles = []
        for _ in range(rng.randint(5, 14)):
            where = rng.random()
            if where < 0.5:     # chin and throat
                self.barnacles.append(("body", rng.uniform(0.01, 0.12), rng.uniform(0.4, 0.95)))
            elif where < 0.8:   # leading edge of the pectoral fin
                self.barnacles.append(("fin", rng.uniform(0.2, 0.95), 0))
            else:               # along the flank
                self.barnacles.append(("body", rng.uniform(0.25, 0.7), rng.uniform(-0.3, 0.5)))
        self.pitch = 0.0
        self.wander = rng.uniform(0, 100)

    # body shape ----------------------------------------------------------
    def radii(self, u):
        """Top and bottom radius (aspect units) at body position u (0 nose .. 1 tail)."""
        if u < 0.0 or u > 1.0:
            return 0.0, 0.0
        D = self.L * self.depth
        if u < 0.42:
            x = u / 0.42
            T = 0.04 + 0.96 * x * (1.55 - 0.55 * x)
        else:
            T = 0.15 + 0.85 * math.cos((u - 0.42) / 0.58 * math.pi / 2) ** 1.5
        if u < 0.32:
            x = u / 0.32
            B = 0.04 + 0.96 * (x * (1.8 - 0.8 * x)) ** 0.85
        else:
            B = 0.15 + 0.85 * math.cos((u - 0.32) / 0.68 * math.pi / 2) ** 1.7
        B *= 1 + self.jaw * math.sin(clamp(u / 0.45) * math.pi)
        top = D * 0.43 * T
        bot = D * 0.57 * B
        du = (u - self.dorsal_u) / 0.03
        if -2.5 < du < 1.5:        # small dorsal fin on a hump
            top += D * self.dorsal * 0.35 * math.exp(-du * du * (0.5 if du < 0 else 2.5))
        if u < 0.22:               # knobbly rostrum
            top += D * 0.012 * math.sin(u * 170 + self.seed) * (1 - u / 0.22)
        return top, bot

    def spine(self, u):
        """Center row of the body at u (rows)."""
        L = self.L
        env = smoothstep(0.35, 1.0, u) ** 1.3
        wave = math.sin(self.phase - 2.2 * u) * env * self.amp * L
        head = math.sin(self.phase + 1.2) * 0.006 * L * (1 - u)
        arch = -self.arch * L * math.sin(math.pi * min(1.0, u * 1.2))
        return self.y + (wave + head + arch + (u - 0.35) * L * math.sin(self.pitch) * 0.5) / ASPECT

    def col_x(self, u):
        return self.x - self.facing * u * self.L

    def update(self, dt, t):
        self.phase += dt * self.beat * TAU
        self.pitch = 0.1 * math.sin(t * 0.06 + self.wander) + 0.04 * math.sin(t * 0.17 + self.wander * 2)


class WhaleScene(Scene):
    name = "whale"
    title = "Humpback"
    blurb = "a giant humpback whale gliding through deep blue water (or through space)"
    tags = ("ocean", "nature", "calm", "space")
    options = {
        "calf": ("random", "random, on or off: a calf swimming alongside"),
        "space": (False, "on: a cosmic whale swimming among stars and nebulae"),
        "rays": (True, "light rays from the surface"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.space = bool(self.opt("space"))
        calf = str(self.opt("calf")).lower()
        calf = rng.random() < 0.55 if calf == "random" else calf in ("1", "on", "true", "yes")
        facing = rng.choice((-1, 1))
        L = min(w * rng.uniform(0.62, 0.68), h * ASPECT * (1.75 if not calf else 1.45))
        L = max(L, 14)
        span = L * 1.13                            # nose to fluke tips
        hx = w / 2 + facing * span / 2
        hy = h * (rng.uniform(0.42, 0.52) if not calf else rng.uniform(0.55, 0.62))
        self.mother = Whale(rng, L, hx, hy, facing)
        self.whales = [self.mother]
        self.calf = None
        if calf:
            cl = L * rng.uniform(0.36, 0.44)
            cx = hx - facing * L * rng.uniform(0.05, 0.3)
            cy = hy - (L * 0.23 * 0.45 + cl * 0.25 * 0.6) / ASPECT - rng.uniform(1.5, 3.0)
            c = Whale(rng, cl, cx, cy, facing, calf=True)
            c.phase = self.mother.phase + 1.0
            self.calf = c
            self.whales.insert(0, c)
        self.base = [(wh.x, wh.y) for wh in self.whales]
        self.glide = rng.uniform(0.02, 0.045)

        if self.space:
            hue = rng.random()
            self.hue = hue
            self.pal = {
                "rim": hsv(hue + 0.05, 0.3, 1.0), "dust": hsv(hue + 0.15, 0.45, 1.0),
                "glow": hsv(hue - 0.1, 0.5, 1.0),
            }
            self.body_sky = [hsv(hue + 0.12, 0.85, 0.3), hsv(hue + 0.04, 0.75, 0.62), hsv(hue - 0.06, 0.6, 0.92),
                             hsv(hue - 0.16, 0.35, 1.0), (255, 250, 245)]
            self.fin_sky = [hsv(hue + 0.08, 0.7, 0.5), hsv(hue - 0.1, 0.45, 0.95), (255, 250, 250)]
        else:
            self.pal = {"rim": (215, 242, 255), "dust": (110, 160, 205), "glow": (130, 205, 245)}
            self.water = hsv(0.57 + rng.uniform(-0.03, 0.03), 0.7, 0.8)
        n = int(w * h / 24 * self.density)
        self.motes = [[rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.15, 1.0), rng.uniform(0, 9)]
                      for _ in range(n)]
        self.bubbles = []
        self.bubble_src = None
        self.rings = []
        self.sparkles = []
        self.next_bubbles = rng.uniform(1.0, 4)
        self.next_song = rng.uniform(2, 6)
        self.ray_slant = rng.uniform(0.25, 0.6) * rng.choice((-1, 1))
        self.ray_freq = rng.uniform(0.07, 0.12)
        if self.space:
            self.build_space()

    def build_space(self):
        rng = self.rng
        w, h = self.w, self.h
        self.stars = []
        for _ in range(int(w * h / 16 * self.density)):
            self.stars.append((rng.randrange(w), rng.randrange(h), rng.random() ** 3, rng.uniform(0, TAU),
                               hsv(rng.choice((0.6, 0.08, 0.13, 0.75, 0.55)), rng.uniform(0, 0.35), 1.0)))
        sd = rng.randrange(1000)
        c1 = hsv(self.hue + rng.uniform(0.25, 0.45), 0.8, 0.95)
        c2 = hsv(self.hue + rng.uniform(-0.3, -0.15), 0.75, 0.95)
        ang = rng.uniform(0, math.pi)
        ca, sa = math.cos(ang), math.sin(ang)
        cx, cy = rng.uniform(0.25, 0.75) * w, rng.uniform(0.3, 0.7) * h
        width = rng.uniform(0.15, 0.28)
        neb = []
        for y in range(h):
            for x in range(w):
                px, py = x - cx, (y - cy) * ASPECT
                along = (px * ca + py * sa) / max(w, 1)
                across = (-px * sa + py * ca) / max(w, 1)
                band = math.exp(-(across / width) ** 2) * (0.55 + 0.45 * math.cos(along * 3.5))
                if band < 0.05:
                    continue
                v = clamp((fbm(x * 0.05, y * 0.1, 4, sd) * 0.9 + 0.4) * band * 1.4)
                if v > 0.14:
                    k = clamp(0.5 + fbm(x * 0.03, y * 0.06, 2, sd + 7) * 1.6)
                    neb.append((x, y, (v - 0.14) * 0.42, mix(c1, c2, k)))
        self.nebula = neb

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        t = self.t
        rng = self.rng
        w, h = self.w, self.h
        for wh, (bx, by) in zip(self.whales, self.base):
            wh.update(dt, t)
            # a slow wandering glide around the home position
            wh.x = bx + self.glide * w * math.sin(t * 0.04 + self.mother.wander)
            wh.y = by + 0.05 * h * math.sin(t * 0.055 + self.mother.wander * 1.7) - wh.pitch * wh.L * 0.05
            if wh.calf:
                wh.x += 0.03 * w * math.sin(t * 0.09 + wh.wander)
                wh.y += 0.02 * h * math.sin(t * 0.13 + wh.wander)
        f = self.mother.facing
        flow = 0.5 if self.space else 1.0
        for m in self.motes:   # the water slides backwards past the swimming whale
            m[0] -= f * dt * (0.4 + 1.6 * m[2]) * flow
            m[1] += dt * (0.06 * math.sin(t * 0.4 + m[3]) + (0 if self.space else 0.07))
            if m[0] < -1:
                m[0] += w + 2
            elif m[0] > w + 1:
                m[0] -= w + 2
            if m[1] >= h:
                m[1] -= h
            elif m[1] < 0:
                m[1] += h
        if not self.space:
            self.update_bubbles(dt)
        self.next_song -= dt
        if self.next_song <= 0:
            self.next_song = rng.uniform(7, 14)
            wh = self.mother if rng.random() < 0.75 else self.whales[0]
            col = self.pal["glow"] if not self.space else hsv(self.hue + rng.uniform(-0.25, 0.25), 0.5, 1.0)
            for k in range(rng.randint(2, 4)):
                r = Ring(wh.col_x(0.1), wh.spine(0.1), rng.uniform(5, 8) * (wh.L / 70) ** 0.5, rng.uniform(6, 9), col)
                r.age = -k * 0.8
                self.rings.append(r)
        for r in self.rings:
            r.age += dt
            if r.age > 0:
                r.r += dt * r.speed
        self.rings = [r for r in self.rings if r.age < r.life]
        if self.space:     # stardust shed from the whale's skin
            for wh in self.whales:
                if rng.random() < dt * (10 if not wh.calf else 4):
                    u = rng.uniform(0.25, 1.0)
                    top, bot = wh.radii(u)
                    y = wh.spine(u) + rng.uniform(-top, bot) / ASPECT
                    self.sparkles.append([wh.col_x(u), y, 1.0, rng.uniform(0.25, 0.6),
                                          -wh.facing * rng.uniform(0.6, 2.5), rng.uniform(-0.3, 0.3)])
            for s in self.sparkles:
                s[2] -= dt * s[3] * 0.5
                s[0] += s[4] * dt
                s[1] += s[5] * dt
            self.sparkles = [s for s in self.sparkles if s[2] > 0]

    def update_bubbles(self, dt):
        rng = self.rng
        t = self.t
        self.next_bubbles -= dt
        if self.next_bubbles <= 0:
            self.next_bubbles = rng.uniform(5, 11)
            self.bubble_src = [rng.choice(self.whales), rng.uniform(1.5, 3.5)]
        if self.bubble_src:
            wh = self.bubble_src[0]
            self.bubble_src[1] -= dt
            if self.bubble_src[1] <= 0:
                self.bubble_src = None
            if rng.random() < dt * 10:
                u = 0.24
                top, _ = wh.radii(u)
                self.bubbles.append([wh.col_x(u) + rng.uniform(-1, 1), wh.spine(u) - top / ASPECT - 0.5,
                                     rng.uniform(0.0, 0.5), rng.uniform(0, TAU), rng.uniform(1.3, 2.6)])
        for b in self.bubbles:
            b[1] -= dt * b[4]
            b[0] += math.sin(t * 2.2 + b[3]) * dt * 0.9 - self.mother.facing * dt * 0.5
            b[2] = min(1.0, b[2] + dt * 0.1)
        self.bubbles = [b for b in self.bubbles if b[1] > 0.5]

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        if self.space:
            self.draw_space(cv)
        else:
            self.draw_water(cv)
        for r in self.rings:
            self.draw_ring(cv, r)
        for wh in self.whales:
            self.draw_whale(cv, wh)
        if self.space:
            for x, y, life, _, _, _ in self.sparkles:
                ch = "*" if life > 0.75 else "+" if life > 0.5 else "·" if life > 0.25 else "."
                cv.put(x, y, ch, scale(self.pal["dust"], 0.3 + 0.7 * life), level=life * 0.6)
        else:
            for x, y, sz, _, _ in self.bubbles:
                ch = "O" if sz > 0.85 else "o" if sz > 0.45 else "°" if sz > 0.2 else "."
                cv.put(x, y, ch, mix((140, 195, 240), (235, 250, 255), sz), level=0.6)

    def draw_water(self, cv):
        t = self.t
        w, h = self.w, self.h
        if self.opt("rays"):
            # light rays from the surface: a 1D pattern swept along a slanted axis, fading with depth
            sl = self.ray_slant
            off = int(abs(sl) * h) + 2
            fr = self.ray_freq
            pat = []
            for q in range(-off, w + off + 1):
                v = (math.sin(q * fr + t * 0.12) * 0.55 + math.sin(q * fr * 2.3 - t * 0.21) * 0.3
                     + math.sin(q * fr * 0.37 + t * 0.05) * 0.4)
                pat.append((v - 0.45) * 0.42 if v > 0.45 else 0.0)
            col = self.water
            for y in range(h):
                fall = (1 - y / h) ** 1.7
                if fall < 0.06:
                    break
                shift = int(y * sl) + off
                for x in range(w):
                    v = pat[x + shift]
                    if v > 0:
                        cv.shade(x, y, v * fall, col)
        for x in range(w):    # the shimmering surface seen from below
            v = noise2(x * 0.12, t * 0.4, 3) * 0.5 + 0.5
            if v > 0.45:
                cv.put(x, 0, "~" if v > 0.62 else "-", scale((120, 190, 235), 0.3 + 0.5 * v), level=0.3)
        for x, y, z, _ in self.motes:
            cv.shade(x, y, 0.06 + 0.16 * z, self.pal["dust"])

    def draw_space(self, cv):
        t = self.t
        for x, y, v, col in self.nebula:
            cv.shade(x, y, v * (0.85 + 0.15 * math.sin(t * 0.3 + x * 0.1)), col)
        for x, y, b, ph, col in self.stars:
            v = (0.12 + 0.88 * b) * (0.6 + 0.4 * math.sin(t * (1 + b * 2) + ph))
            ch = "*" if v > 0.7 else "+" if v > 0.45 else "·" if v > 0.22 else "."
            cv.put(x, y, ch, scale(col, 0.25 + 0.75 * v), level=v * 0.5)
        for x, y, z, _ in self.motes:
            if z > 0.75:
                cv.shade(x, y, 0.1 + 0.15 * z, self.pal["dust"])

    def draw_ring(self, cv, r):
        if r.age <= 0 or r.r < 1:
            return
        fade = (1 - r.age / r.life) ** 1.5 * min(1.0, r.age * 2)
        v = 0.42 * fade
        if v < 0.04:
            return
        n = int(TAU * r.r * 1.2) + 8
        for k in range(n):
            a = k / n * TAU
            wob = 0.5 + 0.5 * math.sin(a * 6 + r.age * 3)
            cv.shade(r.x + math.cos(a) * r.r, r.y + math.sin(a) * r.r / ASPECT, v * (0.55 + 0.45 * wob), r.col)

    # ------------------------------------------------------------------ the whale itself
    def draw_whale(self, cv, wh):
        self.draw_fin(cv, wh, far=True)
        self.draw_flukes(cv, wh)
        self.draw_body(cv, wh)
        self.draw_fin(cv, wh, far=False)

    def draw_body(self, cv, wh):
        space = self.space
        t = self.t
        L = wh.L
        f = wh.facing
        dimk = 0.85 if wh.calf else 1.0
        rim = self.pal["rim"]
        back = BACK_DARK if wh.dark else BACK
        sky = self.body_sky if space else None
        seed = wh.seed
        x_head = wh.x
        xa, xb = sorted((x_head, wh.col_x(1.0)))
        cols = []
        for x in range(max(0, int(xa) - 2), min(cv.w, int(xb) + 3)):
            u = (x_head - (x + 0.5)) * f / L
            if -0.02 <= u <= 1.02:
                top, bot = wh.radii(u)
                yc = wh.spine(clamp(u))
                cols.append((x, u, yc, yc - top / ASPECT, yc + bot / ASPECT, top, bot))
        # light from above, a little in front of the whale and toward the viewer
        lx, ly, lz = 0.35 * f, -0.8, 0.5
        ll = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / ll, ly / ll, lz / ll
        hx, hy, hz = lx, ly, lz + 1.0
        hl = math.sqrt(hx * hx + hy * hy + hz * hz)
        hx, hy, hz = hx / hl, hy / hl, hz / hl
        put = cv.put
        shade = cv.shade
        sqrt = math.sqrt
        nc = len(cols)
        for idx in range(1, nc - 1):
            x, u, yc, ytop, ybot, top, bot = cols[idx]
            if u < 0 or u > 1:
                continue
            p, q = cols[idx - 1], cols[idx + 1]
            # slopes along x (aspect units per cell) of the axis and of both radii
            dyc = (q[2] - p[2]) * ASPECT * 0.5
            dtop = (q[5] - p[5]) * 0.5
            dbot = (q[6] - p[6]) * 0.5
            belly_n = wh.belly_line + 0.3 * noise1(u * 11, seed) * wh.mottle
            groove = 0.03 < u < 0.46
            mouth_y = None
            if u < 0.24:     # the mouth line, curving up toward the eye
                k = u / 0.24
                mouth_y = yc + ((ybot - yc) * (0.18 - 0.1 * k * k) - (yc - ytop) * 0.15 * k ** 3)
            gtop = yc + (ybot - yc) * (0.3 if u > 0.24 else 0.35)
            for y in range(max(0, int(ytop)), min(cv.h, int(ybot) + 1)):
                c0 = ytop if ytop > y else y
                c1 = ybot if ybot < y + 1 else y + 1
                cov = c1 - c0
                if cov < 0.18:
                    continue
                cy = (c0 + c1) * 0.5
                edge = cov < 0.999
                if cy < yc:
                    n = (cy - yc) / max(0.01, yc - ytop)
                    dr = dtop
                else:
                    n = (cy - yc) / max(0.01, ybot - yc)
                    dr = dbot
                if n < -1 or n > 1:
                    continue
                sq = sqrt(1 - n * n)
                # surface normal of a body of revolution around a bent axis
                ny, nz = n, sq
                nx = -(ny * (dyc + n * dr) + nz * sq * dr)
                nl = sqrt(nx * nx + ny * ny + nz * nz)
                nx, ny, nz = nx / nl, ny / nl, nz / nl
                dif = nx * lx + ny * ly + nz * lz
                dif = dif if dif > 0 else 0.0
                spec = nx * hx + ny * hy + nz * hz
                spec = spec ** 24 if spec > 0 else 0.0
                rimv = (1 - nz) ** 3 if n < 0 else 0.0
                light = 0.1 + 0.8 * dif
                if space:
                    neb = fbm(u * 7 - t * 0.05, n * 1.6 + t * 0.03, 2, seed + 5) * 0.5 + 0.5
                    col = gradient(sky, clamp(neb * 0.6 + light * 0.4 + rimv * 0.5))
                    v = 0.25 + 0.4 * neb + 0.35 * light + rimv * 0.5
                    hsh = (int(u * L * 1.7) * 7919 + int((n + 1) * 7) * 104729 + seed) % 89
                    if hsh < 7:
                        tw = 0.5 + 0.5 * math.sin(t * 2.0 + hsh * 1.3 + u * 20)
                        put(x, y, "*" if tw > 0.6 else "+" if tw > 0.3 else "·", mix(rim, (255, 255, 255), tw), 0.9)
                        continue
                    if groove and cy > gtop and (y % 2 == 0):
                        col = mix(col, rim, 0.25)
                    if spec > 0.02:
                        col = mix(col, (255, 255, 255), clamp(spec * 1.5))
                    if edge:
                        col = mix(col, rim, 0.7)
                        v = (0.6 + 0.4 * v) * cov ** 0.5
                    shade(x, y, clamp((v + spec) * dimk), col, "over")
                    continue
                mot = noise2(u * L * 0.15, n * 2.5, seed)
                if n > belly_n + 0.2 * mot * wh.mottle:
                    lb = clamp(0.4 + 0.55 * light + 0.15 * n + 0.1 * mot)
                    col = gradient(BELLY, lb)
                    v = 0.45 + 0.5 * lb
                    if groove and cy > gtop:
                        # throat grooves: pleats running from chin to navel
                        fade = 1 - smoothstep(0.3, 0.46, u)
                        if (y + (1 if u > 0.2 else 0)) % 2 == 0 and fade > 0.2:
                            put(x, y, "=", scale(gradient(BELLY, 0.3 + 0.6 * lb), (0.6 + 0.4 * fade) * dimk), 0.7)
                            continue
                else:
                    caus = noise2(u * L * 0.16 + t * 0.5, n * 3 - t * 0.2, seed + 9)
                    caus = (caus - 0.3) * 1.6 if caus > 0.3 else 0.0
                    l2 = clamp(light * 0.85 + caus * (-n if n < 0 else 0) * 0.5 + 0.08 * mot * wh.mottle + rimv * 0.6)
                    col = gradient(back, l2)
                    v = 0.35 + 0.65 * l2
                if spec > 0.02:
                    col = mix(col, (240, 250, 255), clamp(spec * 1.2))
                    v += spec * 0.5
                if edge:
                    if n < 0:
                        col = mix(col, rim, 0.6)
                    v *= cov ** 0.6
                shade(x, y, clamp(v * dimk), col, "over")
            if space:     # a soft glow around the cosmic whale
                glow = self.pal["glow"]
                for k in (1, 2):
                    cv.shade(x, ytop - k + 0.5, (0.32 - 0.12 * k) * dimk, glow)
                    cv.shade(x, ybot + k - 0.5, (0.3 - 0.12 * k) * dimk, glow)
            # mouth
            if mouth_y is not None and u > 0.01:
                my, mch = edge_glyph(mouth_y)
                put(x, my, mch, scale(gradient(back, 0.15), dimk), 0.5)
        # knobs on the rostrum, eye, barnacles, blowhole
        knob = scale(mix(rim, (200, 200, 190), 0.4), dimk)
        for tu in wh.tubercles:
            top, _ = wh.radii(tu)
            put(wh.col_x(tu), wh.spine(tu) - top / ASPECT + 0.55, "o" if not space else "*", knob, 0.9)
        eu = 0.255
        top, bot = wh.radii(eu)
        ey = wh.spine(eu) + 0.05 * bot / ASPECT
        put(wh.col_x(eu), ey, "@" if not space else "o", (225, 240, 255) if not space else (255, 250, 230), 1.0)
        for kind, a, b in wh.barnacles:
            if kind == "body":
                top, bot = wh.radii(a)
                y = wh.spine(a) + (b * bot if b > 0 else b * top) / ASPECT
                put(wh.col_x(a), y, "°" if int(a * 997) % 2 else "o", (235, 228, 205) if not space else rim, 0.9)
        bu = 0.27
        top, _ = wh.radii(bu)
        put(wh.col_x(bu), wh.spine(bu) - top / ASPECT + 0.6, '"', scale(rim, 0.8 * dimk), 0.9)

    @staticmethod
    def outline(cv, x, e, pe, ne, col):
        """Draw the outline cell(s) of a column edge at fractional row e, glyph following the slope."""
        dy = ne - pe          # rows per two columns, in screen order
        if abs(dy) < 1.1:
            r, ch = edge_glyph(e)
            cv.put(x, r, ch, col, 0.9)
            return
        g = "/" if dy < 0 else "\\"
        if abs(dy) > 5:
            g = "|"
        lo = min(e, (pe + e) / 2, (ne + e) / 2)
        hi = max(e, (pe + e) / 2, (ne + e) / 2)
        for yy in range(int(lo), int(hi) + 1):
            cv.put(x, yy, g, col, 0.9)

    def fin_points(self, wh, far):
        """Polyline (x cells, y aspect) and half-widths for a pectoral fin."""
        L = wh.L
        f = wh.facing
        t = self.t
        ru = 0.3 if not far else 0.27
        top, bot = wh.radii(ru)
        rx = wh.col_x(ru)
        ry = (wh.spine(ru) + bot * (0.45 if not far else 0.3) / ASPECT) * ASPECT
        flen = L * wh.fin_len * (0.85 if far else 1.0)
        n = 9
        ph = t * wh.fin_rate * TAU + wh.fin_phase + (0.8 if far else 0.0)
        ang = wh.fin_base + wh.fin_amp * math.sin(ph) + (0.25 if far else 0) + wh.pitch
        pts = [(rx, ry)]
        x, y = rx, ry
        seg = flen / n
        for i in range(n):
            s = (i + 1) / n
            ang += 0.035 * math.sin(ph - 1.2 - s * 2.0) - 0.012     # a lagging flex along the fin
            x -= f * math.cos(ang) * seg
            y += math.sin(ang) * seg
            pts.append((x, y))
        wmax = L * wh.fin_w
        widths = [wmax * (0.75 + 1.1 * (i / n) * (1 - i / n) ** 0.4) * (1 - (i / n) ** 3) + 0.35 for i in range(n + 1)]
        return pts, widths

    def draw_fin(self, cv, wh, far):
        pts, widths = self.fin_points(wh, far)
        space = self.space
        dimk = (0.5 if far else 1.0) * (0.85 if wh.calf else 1.0)
        f = wh.facing
        seed = wh.seed
        rim = self.pal["rim"]
        stops = self.fin_sky if space else FIN
        put, shade = cv.put, cv.shade
        t = self.t

        def fn(x, y, s, side, gx, gy):
            if s < 0.08:
                return
            d = abs(side)
            lead = side * f < 0         # the forward edge carries the knobby tubercles
            m = noise2(s * 9, side * 2, seed + 3)
            if d > 0.6:
                if lead and not far and math.sin(s * 34) > 0.1:
                    put(x, y, "o", scale(mix(stops[-1], rim, 0.3), dimk), 0.9)
                else:
                    put(x, y, dir_glyph(gx, gy), scale(mix(stops[-2], rim, 0.5), dimk), 0.9)
                return
            lit = clamp(0.35 + 0.6 * (1 - d) + 0.25 * m + (0.15 if lead else -0.05))
            if space:
                lit = clamp(lit * (0.75 + 0.25 * math.sin(t * 1.5 - s * 6)))
            shade(x, y, clamp((0.45 + 0.5 * lit) * dimk), gradient(stops, lit), "over")

        raster_chain(cv, pts, widths, fn)
        if not far:
            for kind, a, _ in wh.barnacles:
                if kind == "fin":
                    i = min(len(pts) - 1, max(1, int(a * (len(pts) - 1))))
                    px, py = pts[i]
                    put(px + f * 0.5, py / ASPECT + widths[i] / ASPECT * 0.5, "°", (240, 230, 205), 1)

    def draw_flukes(self, cv, wh):
        """The tail flukes, seen a little from below so both lobes show; they lag the tail stroke."""
        L = wh.L
        f = wh.facing
        space = self.space
        dimk = 0.85 if wh.calf else 1.0
        rim = self.pal["rim"]
        tx, ty = wh.col_x(1.0), wh.spine(1.0) * ASPECT
        px, py = wh.col_x(0.95), wh.spine(0.95) * ASPECT
        ax, ay = tx - px, ty - py
        al = math.hypot(ax, ay) or 1.0
        lag = -0.25 * math.cos(wh.phase - 2.2)      # bend of the flukes against the stroke
        ang = math.atan2(ay / al, ax / al) + lag * f
        dx, dy = math.cos(ang), math.sin(ang)        # along the tail, pointing away from the head
        nx, ny = -dy, dx
        S = L * wh.fluke_span
        chord = S * 0.62
        fs = 0.42 + 0.1 * math.sin(wh.phase - 2.2)    # foreshortening as the flukes pitch
        reach = max(S, chord * 2.6) + 2
        x0, x1 = int(tx - reach - 1), int(tx + reach + 2)
        y0, y1 = int((ty - reach) / ASPECT - 1), int((ty + reach) / ASPECT + 2)
        seed = wh.seed
        back = BACK_DARK if wh.dark else BACK
        put, shade = cv.put, cv.shade
        for y in range(max(0, y0), min(cv.h, y1)):
            qy = (y + 0.5) * ASPECT - ty
            for x in range(max(0, x0), min(cv.w, x1)):
                qx = x + 0.5 - tx
                a = qx * dx + qy * dy
                b = qx * nx + qy * ny
                lobe = 1 if b > 0 else -1
                Sv = S * fs * (1.0 + 0.12 * lobe * lag)
                s = abs(b) / Sv
                if s > 1 or a < -0.5:
                    continue
                lead = chord * (0.02 + 1.5 * s ** 1.5)
                trail = lead + chord * (0.38 + 0.62 * math.sin(min(1.0, s * 1.25) * math.pi / 2)) * (1 - s ** 4)
                if a < lead or a > trail:
                    continue
                fr = (a - lead) / max(0.01, trail - lead)     # 0 leading .. 1 trailing edge
                if fr > 0.82 and s > 0.12 and math.sin(s * 26 + seed) > 0.4:
                    put(x, y, "~", scale(rim, 0.75 * dimk), 0.9)     # ragged trailing edge
                    continue
                m = fbm(s * 4 + lobe * 3, a / chord * 2.5, 2, seed + 11) * 0.5 + 0.5
                rimk = clamp(1 - min(fr, 1 - fr) * 5) * 0.5 + clamp((s - 0.8) * 5) * 0.4
                if space:
                    col = gradient(self.body_sky, clamp(0.3 + 0.6 * m))
                    v = 0.45 + 0.45 * m
                elif m > 1 - wh.fluke_white:
                    col = gradient(BELLY, 0.5 + 0.45 * m)
                    v = 0.6 + 0.35 * m
                else:
                    col = gradient(back, 0.45 + 0.3 * (1 - s))
                    v = 0.55 + 0.25 * (1 - s)
                col = mix(col, rim, rimk)
                shade(x, y, clamp(v * dimk * (1 - 0.35 * clamp((s - 0.85) * 6))), col, "over")
