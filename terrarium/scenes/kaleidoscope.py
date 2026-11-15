"""A slowly breathing kaleidoscope mandala in drifting jewel tones."""
import math

from ..engine import ASPECT, RAMPS, Scene, clamp, gradient, hsv, mix

TAU = math.tau
TEX = 64          # periodic noise texture size (power of two)
TEXM = TEX - 1
LUT_N = 256
SOFT = " .·:;+*oO%@"   # used instead of the default ramp: rounder glyphs suit a mandala

# cyclic palettes (the last stop wraps back to the first)
PALETTES = {
    "jewel": [(240, 50, 110), (165, 80, 240), (50, 120, 250), (0, 205, 165), (255, 200, 70)],
    "peacock": [(0, 140, 230), (0, 220, 190), (70, 235, 110), (40, 110, 210), (150, 90, 240)],
    "fireopal": [(255, 85, 50), (255, 165, 45), (255, 228, 140), (245, 60, 125), (170, 50, 190)],
    "amethyst": [(140, 70, 240), (215, 100, 245), (255, 150, 215), (105, 90, 230), (80, 150, 255)],
    "lagoon": [(30, 220, 230), (60, 140, 255), (130, 255, 205), (0, 170, 195), (200, 245, 255)],
    "sunset": [(255, 105, 75), (255, 75, 155), (185, 80, 235), (255, 180, 85), (255, 232, 155)],
    "emerald": [(0, 195, 120), (110, 240, 140), (215, 245, 125), (0, 140, 165), (245, 210, 95)],
    "rainbow": None,
}
WHITE = (255, 255, 255)
MOTIFS = ("petals", "petals", "petals", "dots", "scales", "zigzag", "rays", "lace")


def _qi(r, g, b):
    return (0 if r < 0 else 252 if r > 252 else int(r) & ~3,
            0 if g < 0 else 252 if g > 252 else int(g) & ~3,
            0 if b < 0 else 252 if b > 252 else int(b) & ~3)


def _periodic_noise(rng, size, cells):
    """Tileable smooth value noise: a size x size grid in [0, 1]."""
    lat = [[rng.random() for _ in range(cells)] for _ in range(cells)]
    out = [0.0] * (size * size)
    k = cells / size
    for y in range(size):
        fy = y * k
        y0 = int(fy)
        ty = fy - y0
        ty = ty * ty * (3 - 2 * ty)
        r0, r1 = lat[y0 % cells], lat[(y0 + 1) % cells]
        for x in range(size):
            fx = x * k
            x0 = int(fx)
            tx = fx - x0
            tx = tx * tx * (3 - 2 * tx)
            a = r0[x0 % cells] + (r0[(x0 + 1) % cells] - r0[x0 % cells]) * tx
            b = r1[x0 % cells] + (r1[(x0 + 1) % cells] - r1[x0 % cells]) * tx
            out[y * size + x] = a + (b - a) * ty
    return out


class Band:
    """One concentric ring of the mandala with its own motif (a little genome)."""

    def __init__(self, rng, r0, r1, idx, motif, n, R):
        self.r0, self.r1 = r0, r1
        self.motif = motif
        self.hue = idx * rng.choice((0.14, 0.2, 0.27, 0.36)) + rng.uniform(-0.04, 0.04)
        self.accent = rng.choice((0.5, 0.33, -0.25))
        self.spin = rng.uniform(0.02, 0.06) * (1 if idx % 2 else -1) * rng.choice((0, 1, 1))
        self.phase = rng.uniform(0, TAU)
        # how many motifs per mirror wedge: keep every motif at least ~7 cells across
        rmid = (r0 + r1) / 2
        circ = TAU * rmid * R
        most = max(1, min(3, int(circ / n / 7.0)))
        self.per = max(1, min(most, rng.choice((1, 1, 2, 2, 3))))
        self.offset = rng.choice((0.0, 0.5))
        self.width = rng.uniform(0.55, 0.9)          # petal fullness
        self.tip = rng.uniform(0.55, 1.3)            # pointy .. round
        self.lean = rng.uniform(-0.18, 0.18)          # petals curl like a pinwheel
        self.rib = rng.random() < 0.6
        self.rows = rng.randint(1, 2) if (r1 - r0) * R < 14 else rng.randint(2, 3)
        if motif == "scales":
            self.rows = 1 if (r1 - r0) * R < 16 else 2
        self.amp = rng.uniform(0.25, 0.45)
        self.edge_line = rng.random() < 0.45
        self.beads = rng.choice((2, 3, 4, 5))
        self.bright = rng.uniform(0.85, 1.0)


class Kaleidoscope(Scene):
    name = "kaleidoscope"
    title = "Kaleidoscope"
    blurb = "a breathing N-fold mandala of mirrored glass in drifting jewel tones"
    tags = ("abstract", "colorful", "calm", "trippy")
    options = {
        "symmetry": (0, "number of mirrored folds, 3-16 (0 = random 5-12)"),
        "palette": ("random", "random, jewel, peacock, fireopal, amethyst, lagoon, sunset, emerald or rainbow"),
        "speed": (1.0, "animation speed multiplier"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        n = self.opt("symmetry")
        self.n = max(3, min(16, n)) if n > 0 else rng.randint(5, 12)
        self.seg = TAU / self.n
        self.half = self.seg / 2
        pal = self.opt("palette")
        if pal not in PALETTES:
            pal = rng.choice(list(PALETTES) + ["harmony", "harmony"])
        self.pal_name = pal
        if pal == "rainbow":
            self.lut = [hsv(i / LUT_N, 0.72, 1.0) for i in range(LUT_N)]
        else:
            if pal == "harmony":  # a random base hue plus a contrasting accent
                base = rng.random()
                stops = [hsv(base + d, rng.uniform(0.6, 0.85), 1.0)
                         for d in (0, 0.08, rng.choice((0.33, 0.5, 0.6)), 0.16, -0.07)]
            else:
                stops = list(PALETTES[pal])
            k = rng.randrange(len(stops))
            stops = stops[k:] + stops[:k]
            if rng.random() < 0.5:
                stops.reverse()
            stops = stops + [stops[0]]
            self.lut = [gradient(stops, i / LUT_N) for i in range(LUT_N)]
        self.hue_drift = rng.uniform(0.01, 0.025) * rng.choice((-1, 1))
        self.spin = rng.uniform(0.015, 0.045) * rng.choice((-1, 1))
        self.style = rng.choice(("disc", "disc", "full"))
        self.glass = rng.uniform(0.18, 0.32)         # moving stained glass between the motifs
        self.glass_sc = rng.uniform(0.7, 1.3)
        self.glass_v = (rng.uniform(-0.05, 0.05), rng.uniform(0.03, 0.07) * rng.choice((-1, 1)))
        self.glass_rot = rng.uniform(0.03, 0.09) * rng.choice((-1, 1))
        self.breath = rng.uniform(0.03, 0.06)
        self.brate = rng.uniform(0.12, 0.25)
        self.tex = _periodic_noise(rng, TEX, rng.choice((4, 5, 6)))
        self.hue0 = rng.random()

        # polar geometry of every cell
        self.cx, self.cy = (w - 1) / 2.0, (h - 1) / 2.0
        R = max(4.0, min(w / 2.0, h / 2.0 * ASPECT) * 0.98)
        self.R = R
        self.px = 1.0 / R
        corner = math.hypot(w / 2.0, h / 2.0 * ASPECT) / R
        self.rmax = min(corner, 1.1) if self.style == "disc" else corner
        arc = R * self.half          # half-wedge arc length at r = 1, in cells
        self.na = max(10, min(48, int(arc / 0.9)))
        self.nr = max(16, min(80, int(R * self.rmax / 0.9)))

        # genome: concentric bands from the core outwards, each with a motif
        nb = max(2, min(4, int(R / 11)))
        nb = rng.randint(max(2, nb - 1), nb)
        core = rng.uniform(0.1, 0.17)
        outer = 1.0 if self.style == "disc" else min(self.rmax, rng.uniform(1.0, 1.3))
        ws = [rng.uniform(0.7, 1.4) for _ in range(nb)]
        ws[-1] *= 1.3                    # the outer ring gets the most room
        tot = sum(ws)
        self.core = core
        self.bands = []
        r = core
        last = None
        for i, wv in enumerate(ws):
            r1 = r + (outer - core) * wv / tot
            pool = [m for m in MOTIFS if m != last]
            if i == nb - 1:
                pool = ["petals", "petals", "petals", "lace"]   # a bold outer silhouette
            motif = rng.choice(pool)
            last = motif
            self.bands.append(Band(rng, r, r1, i, motif, self.n, R))
            r = r1

        nr, na = self.nr, self.na
        self.abin = na / self.half
        thetas, rows, skip = [], [], []
        for y in range(h):
            dy = (y - self.cy) * ASPECT
            for x in range(w):
                dx = x - self.cx
                rr = math.hypot(dx, dy) / R
                ir = int(rr / self.rmax * nr)
                if ir >= nr:
                    skip.append(y * w + x)
                    ir = nr - 1
                rows.append(ir * na)
                thetas.append(math.atan2(dy, dx) % TAU)
        self.thetas, self.rows, self.skip = thetas, rows, skip

    # ------------------------------------------------------------------ pattern
    def motif(self, B, r, an, r0, r1, sp, pulse, t):
        """Value, hue offset and whiteness of band B at radius r, wedge position an (0..1)."""
        half, px = self.half, self.px
        exp, sin, sqrt, cos = math.exp, math.sin, math.sqrt, math.cos
        width = r1 - r0
        s = (r - r0) / width
        per = B.per
        q = (an + sp) * per * 0.5 + B.offset
        q -= math.floor(q)
        dq = q if q < 0.5 else 1.0 - q          # 0 at a motif centre .. 0.5 halfway to the next
        span = 2.0 * half / per * r              # arc between two motif centres (radius units)
        lat = dq * span
        mo = B.motif
        v = 0.0
        hh = B.hue
        wh = 0.0
        if mo == "petals":
            if -0.12 < s < 1.08:
                sc = 0.0 if s < 0.0 else 1.0 if s > 1.0 else s
                lean = B.lean * sc
                d2 = dq - lean
                if d2 < 0:
                    d2 = -d2
                if d2 > 0.5:
                    d2 = 1.0 - d2
                lat = d2 * span
                prof = sin(math.pi * (0.04 + 0.92 * sc) ** B.tip) ** 0.75
                W = B.width * 0.5 * span * prof + 0.8 * px
                e = lat / W
                rw = 1.3 * px / W + 0.1
                if e < 1.0:
                    body = (1.0 - e) ** 0.9 * (0.3 + (0.4 + 0.15 * pulse) * (1.0 - sc) ** 0.6)
                    rim = exp(-((1.0 - e) / rw) ** 2) * (0.6 + 0.4 * (1.0 - sc))
                    v = body + rim
                    wh = rim * 0.35 + (0.3 * (1.0 - e) if sc < 0.25 else 0.0)
                    hh = B.hue + 0.22 * sc + 0.06 * e
                    if B.rib and e < 0.28 and 0.1 < sc < 0.8:
                        rib = (1.0 - e / 0.28) * 0.28
                        v += rib
                        hh += B.accent * rib * 2
                elif e < 2.0:
                    v = 0.16 * exp(-((e - 1.0) / (rw * 1.4)) ** 2) * prof
                    hh = B.hue + 0.1
        elif mo == "dots":
            rc = (r0 + r1) / 2
            rad = min(0.42 * width, 0.36 * span) + 0.8 * px
            d = sqrt((r - rc) ** 2 + lat * lat) / rad
            if d < 1.0:
                v = (1.0 - d * d) ** 0.5 * (0.6 + 0.3 * pulse)
                wh = (1.0 - d) ** 2 * 0.6
                hh = B.hue + B.accent * (1.0 - d) * 0.5
            elif d < 1.8:
                v = 0.25 * exp(-((d - 1.0) * 3.0) ** 2)
            # small satellite beads between the big ones
            sl = (0.5 - dq) * span
            sd = sqrt((r - rc) ** 2 + sl * sl) / (rad * 0.38 + 0.8 * px)
            if sd < 1.0:
                sv = (1.0 - sd * sd) * 0.55
                if sv > v:
                    v = sv
                    hh = B.hue + B.accent
        elif mo == "scales":
            if 0.0 <= s < 1.0:
                rr = s * B.rows
                row = int(rr)
                fr = rr - row
                qq = q + 0.5 * (row & 1)
                qq -= math.floor(qq)
                arcd = sqrt(((qq - 0.5) * 1.4) ** 2 + (1.0 - fr) ** 2)
                if arcd < 1.0:
                    rw = 1.4 * px * B.rows / width + 0.05
                    rim = exp(-((1.0 - arcd) / rw) ** 2)
                    v = 0.4 * (1.0 - arcd) ** 3 * (0.7 + 0.4 * pulse) + rim * 0.9
                    wh = rim * 0.3
                    hh = B.hue + 0.25 * arcd
        elif mo == "zigzag":
            if -0.2 <= s <= 1.2:
                lw = max(0.012, 1.5 * px) * (1.0 + 0.3 * pulse)
                for k2 in range(B.rows):
                    c = (k2 + 0.5) / B.rows
                    zz = c + B.amp / B.rows * (1 - 4 * dq) * (1 if k2 % 2 else -1)
                    d = (s - zz) * width / lw
                    vv = exp(-d * d) + 0.14 * exp(-d * d * 0.2)
                    if vv > v:
                        v = vv
                        hh = B.hue + k2 * 0.12
                        wh = exp(-d * d) * 0.3
        elif mo == "rays":
            if 0.0 <= s <= 1.0:
                d = lat / (1.2 * px + 0.02 * (1 - s))
                flow = 0.55 + 0.45 * sin(s * 7 - t * 2.2 + B.phase)
                v = (exp(-d * d) * 0.95 + exp(-d * d * 0.2) * 0.14) * flow
                wh = exp(-d * d) * 0.3 * flow
                bp = (t * 0.12 + B.phase) % 1.0      # a bead travelling along every ray
                bd = ((s - bp) * width) ** 2 + lat * lat
                v += exp(-bd / (8 * px * px + 0.0003)) * 0.8
        else:  # lace: a scalloped ring of arches with glowing hearts
            if -0.2 <= s <= 1.2:
                lw = max(0.014, 1.6 * px)
                arch = 0.8 - 0.62 * (2 * dq) ** 2
                d = (s - arch) * width / lw
                v = exp(-d * d) + 0.14 * exp(-d * d * 0.2)
                wh = exp(-d * d) * 0.3
                if 0.0 < s < arch:
                    hd = ((s - arch * 0.42) * width) ** 2 + lat * lat
                    hv = exp(-hd / ((0.0012 + 5 * px * px) * (0.8 + 0.4 * pulse)))
                    if hv > 0.05:
                        v += hv * 0.8
                        hh = B.hue + B.accent * hv
        if B.edge_line:
            d = (r - r1) / (2.0 * px)
            if -3.0 < d < 3.0:
                bead = 0.5 + 0.5 * cos(TAU * (an * B.beads * 0.5 - t * 0.04))
                ev = exp(-d * d) * (0.25 + 0.65 * bead ** 4)
                if ev > v:
                    v = ev
                    hh = B.hue + B.accent
                    wh = 0.15
        return v * B.bright, hh, wh

    def table(self, cv):
        t = self.t * self.opt("speed")
        ramp = SOFT if cv.ramp == RAMPS["ascii"] else cv.ramp
        rn = len(ramp) - 1
        lut = self.lut
        tex = self.tex
        half = self.half
        nr, na = self.nr, self.na
        disc = self.style == "disc"
        cos, sin, exp = math.cos, math.sin, math.exp
        b = 1.0 + self.breath * sin(t * self.brate * TAU)
        hue_t = self.hue0 + t * self.hue_drift
        gr = t * self.glass_rot
        gca, gsa = cos(gr) * self.glass_sc, sin(gr) * self.glass_sc
        gvx, gvy = self.glass_v[0] * t, self.glass_v[1] * t
        glass = self.glass
        glass_lvl = 0.66 + 0.04 * sin(t * 0.21)
        live = []
        for B in self.bands:   # breathing ripples outward with a little lag per ring
            bb = 1.0 + (b - 1.0) * (1.0 + 0.6 * sin(t * 0.37 + B.phase))
            live.append((B, B.r0 * bb, B.r1 * bb, t * B.spin, 0.5 + 0.5 * sin(t * 0.6 + B.phase)))
        core = self.core * b
        motif = self.motif
        chs, fgs, lvs = [], [], []
        ach, afg, alv = chs.append, fgs.append, lvs.append
        rmax = self.rmax
        for ir in range(nr):
            r = (ir + 0.5) / nr * rmax
            mine = [L for L in live if L[1] - 0.12 <= r <= L[2] + 0.06]
            if disc:
                env = clamp((1.08 - r) / 0.1)
            else:
                env = 1.0 / (1.0 + max(0.0, r - 1.0) * 1.2)
            cg = exp(-(r / core) ** 2 * 2.5)
            ring = 0.0
            if r < core * 1.6:   # a jewel in the middle: bright centre, thin halo ring
                d = (r - core * 1.15) / (1.5 * self.px)
                ring = exp(-d * d) * 0.7
            amb = 0.0
            ringhue = r * 0.3
            for ia in range(na):
                an = (ia + 0.5) / na               # 0..1 across the half wedge (mirror to mirror)
                val = 0.0
                hue = ringhue
                white = 0.0
                for B, r0, r1, sp, pulse in mine:
                    v, hh, wh = motif(B, r, an, r0, r1, sp, pulse, t)
                    if v > val:
                        val = v
                        hue = ringhue + hh
                        white = wh
                if val < 0.2 and glass > 0:
                    a = an * half
                    ux, uy = r * cos(a), r * sin(a)
                    gx = ux * gca - uy * gsa + gvx
                    gy = ux * gsa + uy * gca + gvy
                    nv = tex[(int(gy * TEX) & TEXM) * TEX + (int(gx * TEX) & TEXM)]
                    g = (nv - glass_lvl) * 3.2
                    if g > 0:
                        gv = glass * 2.6 * (g if g < 1.0 else 1.0) ** 0.7
                        if gv > val:
                            val = gv
                            hue = ringhue + nv * 0.6 + 0.3
                            white = 0.0
                if amb > val:
                    val = amb
                    hue = ringhue + 0.15
                if ring > val:
                    val = ring
                    hue = 0.5
                    white = 0.2
                if cg > 0.04 and cg > val * 0.5:
                    val = max(val, cg)
                    white = max(white, cg * 0.8)
                    hue = ringhue
                val *= env
                if val < 0.07:
                    ach(" ")
                    afg(None)
                    alv(0.0)
                    continue
                if val > 1.0:
                    val = 1.0
                val = val ** 0.72
                c = lut[int((hue + hue_t) * LUT_N) % LUT_N]
                if white > 0:
                    c = mix(c, WHITE, white if white < 1.0 else 1.0)
                gi = int(val * rn + 0.5)
                kk = 0.3 + 0.7 * val
                if gi > 0:
                    ach(ramp[gi])
                    afg(_qi(c[0] * kk, c[1] * kk, c[2] * kk))
                else:
                    ach(" ")
                    afg(None)
                alv(val)
        return chs, fgs, lvs

    def draw(self, cv):
        if (cv.w, cv.h) != (self.w, self.h):
            return
        chs, fgs, lvs = self.table(cv)
        t = self.t * self.opt("speed")
        rot = t * self.spin
        seg, half, abin = self.seg, self.half, self.abin
        na1 = self.na - 1
        ks = []
        for ro, th in zip(self.rows, self.thetas):
            s = (th + rot) % seg
            if s > half:
                s = seg - s
            ia = int(s * abin)
            ks.append(ro + (ia if ia < na1 else na1))
        cv.ch[:] = [chs[k] for k in ks]
        cv.fg[:] = [fgs[k] for k in ks]
        cv.lv[:] = [lvs[k] for k in ks]
        for i in self.skip:
            cv.ch[i] = " "
            cv.fg[i] = None
            cv.lv[i] = 0.0
