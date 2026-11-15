"""Bioluminescent jellyfish pulsing through deep water."""
import math

from ..engine import ASPECT, Scene, clamp, hsv, mix, scale

PALETTES = {
    "mixed": [(90, 220, 255), (255, 120, 210), (175, 125, 255), (255, 175, 130), (120, 255, 215)],
    "pink": [(255, 120, 210), (255, 160, 220), (240, 110, 255)],
    "blue": [(90, 200, 255), (120, 240, 255), (110, 150, 255)],
    "moon": [(220, 230, 255), (200, 210, 250), (240, 220, 255)],
    "fire": [(255, 140, 60), (255, 90, 90), (255, 200, 110)],
}


class Jelly:
    def __init__(self, rng, w, h, color, depth):
        self.depth = depth                       # 0 far .. 1 near
        big = min(w, h * ASPECT)
        self.r = max(3.5, big * (0.06 + 0.09 * depth) * rng.uniform(0.85, 1.15))  # bell radius (x cells)
        self.x = rng.uniform(0, w)
        self.y = rng.uniform(self.r * 0.6, h * 0.85)
        self.color = color
        self.phase = rng.uniform(0, math.tau)
        self.rate = rng.uniform(0.55, 0.85)      # pulses per second-ish
        self.drift = rng.uniform(-0.6, 0.6)
        self.sway = rng.uniform(0, math.tau)
        # per-jelly "genome": every jelly (and every run) is shaped a little differently
        self.ntent = rng.randint(3, 8)
        self.dome = rng.uniform(0.8, 1.45)        # flat saucer .. tall bell
        self.scallops = rng.uniform(9, 20)
        self.wiggle = rng.uniform(0.5, 1.7)
        self.arms = rng.choice((0, 2, 3, 3, 4, 5))
        self.ribs = rng.choice((0, 8, 12, 16, 22))
        self.tlen = self.r * rng.uniform(1.6, 2.6)
        self.vy = 0.0
        self.tilt = 0.0
        self.kx = 0.0       # sideways push (from ripples and the pointer)
        self.flash = 0.0    # extra glow after a ripple washes over it


class Jellyfish(Scene):
    name = "jellyfish"
    title = "Jellyfish"
    blurb = "bioluminescent jellyfish pulsing through deep water"
    tags = ("ocean", "nature", "calm")
    interactions = "click to send a ripple that makes the jellies glow, point to shoo them gently"
    options = {
        "count": (0, "number of jellyfish (0 = based on screen size)"),
        "palette": ("random", "random, harmony, mixed, pink, blue, moon or fire"),
        "snow": (1.0, "amount of drifting marine snow"),
        "rays": (True, "faint light rays from the surface"),
    }

    def setup(self):
        rng = self.rng
        choice = self.opt("palette")
        if choice == "random":
            choice = rng.choice(list(PALETTES) + ["harmony"] * 3)
        if choice in PALETTES:
            pal = PALETTES[choice]
        else:  # harmony: a random base hue with close neighbours
            base = rng.random()
            pal = [hsv(base + rng.uniform(-0.09, 0.09), rng.uniform(0.45, 0.7), 1.0) for _ in range(4)]
        n = self.opt("count") or max(2, int(round((2 + self.w * self.h / 2600) * self.density)))
        self.palette = pal
        self.jellies = []
        for k in range(n):
            depth = (k + rng.random()) / n
            self.jellies.append(Jelly(rng, self.w, self.h, rng.choice(pal), depth))
        self.jellies.sort(key=lambda j: j.depth)
        ns = int(self.w * self.h / 45 * self.opt("snow") * self.density)
        self.snow = [[rng.uniform(0, self.w), rng.uniform(0, self.h), rng.uniform(0.2, 1.0), rng.uniform(0, 9)]
                     for _ in range(ns)]
        self.rings = []     # click ripples: [x, y, radius, max radius, set of jellies already hit]

    def on_click(self, x, y):
        x = clamp(x, -2.0, self.w + 2.0)
        y = clamp(y, -2.0, self.h + 2.0)
        self.rings.append([x, y, 0.0, max(12.0, max(self.w, self.h * ASPECT) * 0.55), set()])
        self.rings = self.rings[-6:]

    def update(self, dt):
        super().update(dt)
        for j in list(self.jellies):
            j.phase += dt * j.rate * math.tau
            # A pulse = quick contraction then slow relax; thrust while contracting.
            c = max(0.0, math.sin(j.phase))
            thrust = c ** 2
            j.vy = j.vy * 0.96 ** (dt * 30) - thrust * (0.5 + j.depth * 0.9) * dt * 6
            j.vy += 0.25 * dt  # slow sinking between pulses
            j.y += j.vy * dt * 0.9
            j.x += (j.drift + 0.6 * math.sin(self.t * 0.2 + j.sway)) * dt * (0.4 + j.depth)
            # a ripple front washing over the jelly gives it a push and lights it up
            for rg in self.rings:
                if id(j) in rg[4]:
                    continue
                dx, dy = j.x - rg[0], (j.y - rg[1]) * ASPECT
                d = math.hypot(dx, dy)
                if d < rg[2] + j.r * 0.5:
                    rg[4].add(id(j))
                    k = 1 - rg[2] / rg[3]
                    if d > 1e-3:
                        j.kx += dx / d * 9.0 * k
                        j.vy += dy / d * 4.0 * k
                    j.flash = max(j.flash, 0.4 + 0.6 * k)
            # the pointer: jellies drift lazily away from it
            ptr = self.pointer
            if ptr is not None:
                dx, dy = j.x - ptr[0], (j.y - ptr[1]) * ASPECT
                d = math.hypot(dx, dy)
                reach = j.r * 2.2 + 6
                if 1e-3 < d < reach:
                    k = (1 - d / reach) * 4.0 * dt
                    j.kx += dx / d * k
                    j.vy += dy / d * k * 0.35
            j.x += j.kx * dt
            j.kx *= 0.4 ** dt
            j.flash = max(0.0, j.flash - dt * 0.45)
            j.tilt = 0.25 * math.sin(self.t * 0.3 + j.sway)
            if j.y < -j.r * 1.2:
                # it swam off the top: a brand-new, freshly generated jelly rises from below
                k = self.jellies.index(j)
                nj = Jelly(self.rng, self.w, self.h, self.rng.choice(self.palette), j.depth)
                nj.y = self.h + nj.r * 0.4
                self.jellies[k] = nj
            if j.x < -j.r * 2:
                j.x = self.w + j.r
            elif j.x > self.w + j.r * 2:
                j.x = -j.r
        for rg in self.rings:
            rg[2] += dt * (14.0 + rg[3] * 0.12)
        self.rings = [rg for rg in self.rings if rg[2] < rg[3]]
        for s in self.snow:
            s[1] += dt * 0.35 * s[2]
            s[0] += dt * 0.15 * math.sin(self.t * 0.5 + s[3])
            if s[1] >= self.h:
                s[1] -= self.h
                s[0] = self.rng.uniform(0, self.w)

    def draw(self, cv):
        t = self.t
        w, h = self.w, self.h
        if self.opt("rays"):
            for y in range(0, h):
                fall = 1 - y / h
                for x in range(0, w, 1):
                    v = math.sin(x * 0.11 - y * 0.05 + t * 0.15) * math.sin(x * 0.037 + t * 0.07)
                    if v > 0.55:
                        cv.shade(x, y, (v - 0.55) * 0.35 * fall, (60, 120, 190))
        for sx, sy, sz, _ in self.snow:
            cv.shade(sx, sy, 0.08 + 0.12 * sz, (110, 150, 190))
        for rg in self.rings:
            self.draw_ring(cv, rg)
        for j in self.jellies:
            self.draw_jelly(cv, j)

    def draw_ring(self, cv, rg):
        x, y, r, mr, _ = rg
        f = r / mr
        col = mix(self.palette[0], (220, 245, 255), 0.6)
        for ring, k in ((r, 1.0), (r * 0.82, 0.45), (r * 0.66, 0.2)):
            if ring < 0.5:
                continue
            a = (1 - f) ** 1.3 * min(1.0, ring * 0.5) * k
            if a < 0.03:
                continue
            n = max(10, int(ring * 7))
            for i in range(n):
                ang = math.tau * i / n
                cv.shade(x + math.cos(ang) * ring, y + math.sin(ang) * ring / ASPECT, 0.8 * a, col)

    def draw_jelly(self, cv, j):
        t = self.t
        pulse = max(0.0, math.sin(j.phase))
        bw = j.r * (1.0 - 0.16 * pulse)                  # bell half-width (x cells)
        bh = j.r * j.dome * (1.0 + 0.12 * pulse) / ASPECT  # bell height (y cells)
        cx, cy = j.x, j.y
        glow = 0.6 + 0.4 * j.depth
        col = j.color
        if j.flash > 0:
            glow *= 1.0 + 0.7 * j.flash
            col = mix(col, (255, 255, 255), 0.35 * j.flash)
            pulse = max(pulse, j.flash)
        rim_col = mix(col, (255, 255, 255), 0.5)
        organ_col = mix(col, (255, 110, 220), 0.55)
        ct, st = math.cos(j.tilt), math.sin(j.tilt)

        # ---- tentacles: thin strands whose glyph follows their slope
        base_y = cy + bh * 0.12
        for k in range(j.ntent):
            u = (k + 0.5) / j.ntent * 2 - 1           # -1..1 across the bell rim
            x0 = cx + u * bw * 0.75 + st * bh
            rows = int(j.tlen)
            px = None
            for s in range(rows):
                f = s / max(1, rows)
                wave = math.sin(t * 1.4 + k * 1.9 - s * 0.22 + j.phase * 0.2) * (0.3 + f * 4.0) * j.wiggle
                x = x0 + wave + u * f * j.r * 0.18 + st * s
                y = base_y + s
                v = (1 - f) ** 1.2 * 0.55 * glow
                c = mix(col, rim_col, 0.4 * (1 - f))
                self.strand(cv, x, y, v, c, 0.0 if px is None else x - px)
                px = x
        # oral arms: short, frilly, brighter, near the middle
        for k in range(j.arms):
            u = (k - (j.arms - 1) / 2) * 0.17
            x0 = cx + u * bw + st * bh
            rows = int(j.tlen * 0.6)
            px = None
            for s in range(rows):
                f = s / max(1, rows)
                x = x0 + math.sin(t * 1.0 + k * 1.7 - s * 0.6) * (0.4 + f * 1.5) + st * s
                y = base_y + s
                v = (1 - f * 0.8) * 0.85 * glow
                self.strand(cv, x, y, v, organ_col, 0.0 if px is None else x - px, thick=True)
                px = x

        # ---- bell (with a soft halo)
        x0 = int(cx - bw * 1.3 - 2)
        x1 = int(cx + bw * 1.3 + 3)
        y0 = int(cy - bh * 1.35 - 1)
        y1 = int(cy + bh * 0.45 + 2)
        for y in range(max(0, y0), min(cv.h, y1)):
            for x in range(max(0, x0), min(cv.w, x1)):
                px = (x + 0.5 - cx)
                py = (y + 0.5 - cy) * ASPECT
                rx = px * ct + py * st
                ry = -px * st + py * ct
                u = rx / bw
                dy = ry / (bh * ASPECT)
                bottom = 0.10 + 0.05 * math.sin(u * j.scallops + t * 3) - 0.12 * u * u  # scalloped margin
                d = math.sqrt(u * u + (dy if dy < 0 else 0) ** 2)                # 0 center .. 1 dome
                if d > 1.0 or dy > bottom:
                    # halo outside the dome
                    if dy <= bottom + 0.15 and d < 1.3:
                        hv = (1.3 - d) / 0.3 * 0.22 * glow
                        cv.shade(x, y, hv, col)
                    continue
                rim = clamp((d - 0.5) / 0.5) ** 2.5
                ribs = 0.5 + 0.5 * math.cos(math.atan2(dy, u) * j.ribs)
                hilite = math.exp(-((u + 0.35) ** 2 + (dy + 0.62) ** 2) * 10)
                v = 0.22 + rim * 0.66 + ribs * 0.07 * (1 - rim) + hilite * 0.5
                c = mix(col, rim_col, rim * 0.8 + hilite * 0.5)
                # four-leaf gonads glowing in the middle of the bell
                ox, oy = u, (dy + 0.45) * 1.3
                ang = math.atan2(oy, ox)
                orad = math.sqrt(ox * ox + oy * oy)
                lobe = 0.22 + 0.07 * math.cos(ang * 4 + j.phase * 0.3)
                organ = clamp(1 - abs(orad - lobe) / 0.08)
                if organ > 0:
                    c = mix(c, organ_col, organ)
                    v = max(v, 0.5 * organ + 0.15)
                if bottom - dy < 0.08:                    # glowing margin
                    v = max(v, 0.9)
                    c = rim_col
                v *= glow * (0.85 + 0.25 * pulse)
                cv.shade(x, y, v, c)

    @staticmethod
    def strand(cv, x, y, v, col, dx, thick=False):
        """Draw one strand cell with a glyph that follows its slope (dx = x change per row)."""
        xi, yi = int(x), int(y)
        if not (0 <= xi < cv.w and 0 <= yi < cv.h) or v < 0.06:
            return
        i = yi * cv.w + xi
        if v <= cv.lv[i]:
            return
        if v < 0.22:
            ch = "." if v < 0.13 else ":"
        elif dx < -0.45:
            ch = "/"
        elif dx > 0.45:
            ch = "\\"
        elif thick:
            ch = "}" if dx < 0 else "{" if dx > 0.15 else "|"
        else:
            ch = "(" if dx < -0.15 else ")" if dx > 0.15 else "|"
        cv.put(xi, yi, ch, scale(col, 0.35 + 0.65 * v), level=v)
