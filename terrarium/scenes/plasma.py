"""Demoscene plasma: interfering sine fields poured through slowly cycling palettes."""
import math

from ..engine import ASPECT, Scene, clamp, gradient, hsv, smoothstep

# Cyclic palettes: the last stop flows back into the first.
PALETTES = {
    "vapor": [(70, 20, 160), (190, 40, 220), (255, 60, 160), (255, 120, 90), (255, 200, 110),
              (80, 230, 255), (40, 120, 255)],
    "fire": [(110, 0, 20), (210, 30, 10), (255, 100, 0), (255, 185, 40), (255, 240, 170),
             (255, 150, 30), (200, 40, 10)],
    "ocean": [(20, 50, 160), (10, 110, 200), (20, 190, 220), (140, 250, 235), (40, 210, 180),
              (30, 120, 210)],
    "toxic": [(20, 110, 40), (60, 200, 40), (180, 255, 60), (250, 255, 140), (60, 240, 170),
              (10, 150, 130)],
    "candy": [(255, 100, 170), (255, 170, 120), (255, 240, 150), (120, 240, 190), (110, 180, 255),
              (190, 120, 255)],
    "aurora": [(20, 80, 160), (20, 190, 140), (100, 255, 170), (160, 140, 255), (255, 110, 210),
               (70, 100, 230)],
    "rainbow": [hsv(k / 12, 0.8, 1.0) for k in range(12)],
}

NB = 512             # quantization of each summed field
NH = 128             # hue steps in the color table
NV = 24              # brightness steps in the color table
LUT_N = 1024         # sine lookup table size (power of two)
LUT_M = LUT_N - 1


def _q(c):
    r, g, b = c
    r = 0 if r < 0 else 252 if r > 252 else int(r) & ~3
    g = 0 if g < 0 else 252 if g > 252 else int(g) & ~3
    b = 0 if b < 0 else 252 if b > 252 else int(b) & ~3
    return (r, g, b)


class Plasma(Scene):
    name = "plasma"
    title = "Plasma"
    blurb = "demoscene plasma: interfering sine waves through cycling palettes"
    tags = ("abstract", "retro", "colorful")
    interactions = "point to pull the ripples along, click to pour in a new palette"
    options = {
        "palette": ("random", "vapor, fire, ocean, toxic, candy, aurora, rainbow or random"),
        "scale": (0.0, "wave frequency, bigger = finer ripples (0 = random)"),
        "cycle": (1.0, "palette cycling speed"),
    }

    def setup(self):
        w, h = self.w, self.h
        rng = self.rng
        if not hasattr(self, "style"):
            # roll this run's field once: palette, wave frequencies, speeds and directions
            pal = self.opt("palette")
            if pal not in PALETTES:
                pal = rng.choice(list(PALETTES))
            sg = lambda: rng.choice((-1, 1))
            self.style = {
                "palette": pal,
                "scale": self.opt("scale") if self.opt("scale") > 0 else rng.uniform(0.7, 1.5),
                "f": [rng.uniform(0.6, 1.3), rng.uniform(1.2, 2.0), rng.uniform(0.9, 1.7),
                      rng.uniform(0.6, 1.2), rng.uniform(0.9, 1.7)],
                "v": [rng.uniform(0.3, 0.7) * sg() for _ in range(6)],
                "rip": rng.uniform(0.7, 1.6),
                "bands": rng.uniform(4.5, 8.5),
                "hue": rng.uniform(0.6, 1.3) * sg(),
                "wander": [rng.uniform(0.1, 0.32) for _ in range(4)],
            }
        st = self.style
        stops = PALETTES[st["palette"]]
        stops = list(stops) + [stops[0]]
        # Spatial frequency (radians per x-cell) relative to the screen, so the composition
        # holds at any size.
        span = max(40.0, max(w, h * ASPECT))
        self.k = 8.0 / span * max(0.1, st["scale"])
        q = (NB - 1) / 10.0                 # a field sum spans [-5, 5]
        self.q = q
        self.lutq = [math.sin(i * math.tau / LUT_N) * q for i in range(LUT_N)]
        # Radial distance table twice the screen size: a moving center is an offset into it.
        self.W2, self.H2 = 2 * w + 2, 2 * h + 2
        kr = self.k * st["rip"] * LUT_N / math.tau
        cx, cy = w + 1, h + 1
        self.dist = [int(math.hypot(x - cx, (y - cy) * ASPECT) * kr)
                     for y in range(self.H2) for x in range(self.W2)]
        self.seeds = [rng.uniform(0, 100) for _ in range(10)]
        # Fixed color table indexed by hue*NV + brightness; cycling only re-maps hue bins.
        self.table_ramp = None
        self.colors = self._colors(stops)
        if not hasattr(self, "pull"):
            # mouse state: the pointer drags ripple A, a click drops ripple B and fades palettes
            self.pull = 0.0                # 0 = ripple A wanders, 1 = it follows the pointer
            self.pt = (w / 2, h / 2)       # eased pointer position
            self.drop = None               # [x, y, strength] where the last click landed
            self.fade = None               # [old stops, new stops, progress 0..1]

    @staticmethod
    def _colors(stops, stops2=None, mixk=0.0):
        out = []
        for hi in range(NH):
            c = gradient(stops, hi / NH)
            if stops2 is not None:
                c2 = gradient(stops2, hi / NH)
                c = (c[0] + (c2[0] - c[0]) * mixk, c[1] + (c2[1] - c[1]) * mixk, c[2] + (c2[2] - c[2]) * mixk)
            for vi in range(NV):
                v = vi / (NV - 1)
                glint = clamp((v - 0.86) / 0.14) * 0.55       # white-hot crests
                cc = (c[0] + (255 - c[0]) * glint, c[1] + (255 - c[1]) * glint, c[2] + (255 - c[2]) * glint)
                k = 0.25 + 0.75 * v
                out.append(_q((cc[0] * k, cc[1] * k, cc[2] * k)))
        return out

    def on_click(self, x, y):
        st = self.style
        names = list(PALETTES)
        old = PALETTES[st["palette"]]
        st["palette"] = names[(names.index(st["palette"]) + 1) % len(names)]
        new = PALETTES[st["palette"]]
        self.fade = [list(old) + [old[0]], list(new) + [new[0]], 0.0]
        self.drop = [clamp(x, 0, self.w - 1), clamp(y, 0, self.h - 1), 0.0]

    def update(self, dt):
        super().update(dt)
        p = self.pointer
        if p is not None:
            px, py = clamp(p[0], 0, self.w - 1), clamp(p[1], 0, self.h - 1)
            k = min(1.0, dt * 4.0)
            self.pt = (self.pt[0] + (px - self.pt[0]) * k, self.pt[1] + (py - self.pt[1]) * k)
            if self.pull == 0.0:
                self.pt = (px, py)
            self.pull = min(1.0, self.pull + dt * 1.5)
        elif self.pull > 0.0:
            self.pull = max(0.0, self.pull - dt * 0.5)
        if self.drop is not None:
            self.drop[2] += dt
            if self.drop[2] > 9.0:
                self.drop = None
        if self.fade is not None:
            self.fade[2] = min(1.0, self.fade[2] + dt / 1.6)
            f = self.fade[2]
            self.colors = self._colors(self.fade[0], self.fade[1], f * f * (3 - 2 * f))
            if f >= 1.0:
                self.fade = None

    def _tables(self, ramp):
        if self.table_ramp != ramp:
            nr = len(ramp) - 1
            self.vlevel = [0.06 + 0.94 * vi / (NV - 1) for vi in range(NV)]
            chars = []
            for vi in range(NV):
                idx = int(self.vlevel[vi] * nr + 0.5)
                chars.append(ramp[idx] if idx > 0 else " ")
            self.chars = chars * NH
            self.levels = self.vlevel * NH
            self.table_ramp = ramp

    def draw(self, cv):
        w, h = min(self.w, cv.w), min(self.h, cv.h)
        t = self.t
        k = self.k
        q = self.q
        sd = self.seeds
        lut = self.lutq
        self._tables(cv.ramp)

        # Per-frame bin maps: field A -> hue row offset, field B -> brightness column.
        cyc = t * 0.04 * self.opt("cycle")
        st = self.style
        f, vv, wd = st["f"], st["v"], st["wander"]
        hs, bands = st["hue"], st["bands"]
        HB = [int(((b / (NB - 1) * 2 - 1) * hs + cyc) % 1.0 * NH) * NV for b in range(NB)]
        VB = []
        for b in range(NB):
            s = b / (NB - 1) * 2 - 1
            band = 0.5 + 0.5 * math.sin(s * bands - t * 0.7)
            VB.append(int((0.1 + 0.9 * band ** 1.1) * (NV - 1) + 0.5))

        # Separable plane waves along x and y.
        colA = [math.sin(x * k * f[0] + t * vv[0] + sd[0]) * q for x in range(w)]
        colB = [math.sin(x * k * f[1] + t * vv[1] + sd[1]) * q for x in range(w)]
        rowA = [math.sin(y * ASPECT * k * f[2] + t * vv[2] + sd[2]) * q for y in range(h)]
        rowB = [math.sin(y * ASPECT * k * f[3] + t * vv[3] + sd[3]) * q for y in range(h)]
        # A rotating plane wave: sin(ax + by + p) = sin(ax)cos(by + p) + cos(ax)sin(by + p).
        ang = t * 0.09 * vv[4] / abs(vv[4]) + sd[4]
        kd = k * f[4]
        ax, by = kd * math.cos(ang), kd * math.sin(ang) * ASPECT
        p = t * vv[5] * 1.4
        S1 = [math.sin(ax * x) * q for x in range(w)]
        C1 = [math.cos(ax * x) * q for x in range(w)]
        C2 = [math.cos(by * y + p) for y in range(h)]
        S2 = [math.sin(by * y + p) for y in range(h)]
        # Two ripples from wandering centers.
        W2 = self.W2
        oxa = int((0.5 + 0.45 * math.sin(t * wd[0] + sd[5])) * w)
        oya = int((0.5 + 0.45 * math.sin(t * wd[1] + sd[6])) * h)
        oxb = int((0.5 + 0.45 * math.sin(t * wd[2] + sd[7])) * w)
        oyb = int((0.5 + 0.45 * math.cos(t * wd[3] + sd[8])) * h)
        if self.pull > 0.0:   # the pointer drags ripple A (eased in and out)
            e = self.pull * self.pull * (3 - 2 * self.pull)
            oxa = int(oxa + (self.pt[0] - oxa) * e)
            oya = int(oya + (self.pt[1] - oya) * e)
        if self.drop is not None:   # ripple B sits where the last click landed, then drifts home
            age = self.drop[2]
            e = smoothstep(0.0, 0.7, age) * (1.0 - smoothstep(5.0, 9.0, age))
            oxb = int(oxb + (self.drop[0] - oxb) * e)
            oyb = int(oyb + (self.drop[1] - oyb) * e)
        oxa = max(0, min(w, oxa))
        oya = max(0, min(h, oya))
        oxb = max(0, min(w, oxb))
        oyb = max(0, min(h, oyb))
        pa = int(t * 1.1 * LUT_N / math.tau)
        pb = int(-t * 0.8 * LUT_N / math.tau)
        dist = self.dist
        M = LUT_M
        q0 = (NB - 1) / 2.0 + 0.5
        chars, colors, levels = self.chars, self.colors, self.levels
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        cw = cv.w
        for y in range(h):
            ra = rowA[y] + q0
            rb = rowB[y] + q0
            c2 = C2[y]
            s2 = S2[y]
            ia = (y - oya + h + 1) * W2 + (w + 1 - oxa)
            ib = (y - oyb + h + 1) * W2 + (w + 1 - oxb)
            ks = []
            app = ks.append
            for a, bb, s1, c1, u, v in zip(colA, colB, S1, C1, dist[ia:ia + w], dist[ib:ib + w]):
                rot = s1 * c2 + c1 * s2
                la = lut[(u - pa) & M]
                lb = lut[(v - pb) & M]
                app(HB[int(ra + a + rot + la + lb)] + VB[int(rb + bb - rot + la - lb)])
            o = y * cw
            ch[o:o + w] = [chars[i] for i in ks]
            fg[o:o + w] = [colors[i] for i in ks]
            lv[o:o + w] = [levels[i] for i in ks]
        if self.drop is not None and self.drop[2] < 1.6:
            # a splash ring spreading from the click
            age = self.drop[2]
            r = 1.0 + age * max(w, h * ASPECT) * 0.35
            fade = 1.0 - age / 1.6
            steps = int(r * 7) + 8
            dx, dy = self.drop[0], self.drop[1]
            for i in range(steps):
                a = i / steps * math.tau
                cv.shade(dx + math.cos(a) * r, dy + math.sin(a) * r / ASPECT, 0.35 + 0.6 * fade,
                         (255, 250, 240), mode="over")
