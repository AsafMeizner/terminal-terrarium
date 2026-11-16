"""A starling murmuration at sunset: hundreds of boids folding into swirling clouds over a lake.

The flock is a classic boids model (separation, alignment, cohesion) using only the first few
neighbours found in a spatial hash (starlings track about seven), steered toward a wandering
attractor. Now and then a falcon dives through and the flock bends around it. Birds are drawn as
dark marks on a glowing sky, so where they crowd the sky is blotted out and the cloud shape reads
like the real thing. The sky, treeline and lake are baked once; only ripples and birds move.
"""
import math

from ..engine import ASPECT, Scene, clamp, fbm, gradient, hsv, mix, noise1, noise2, scale

TAU = math.tau

# sky stops from zenith to horizon, sun colour, water tint
PALETTES = {
    "sunset": ([(52, 44, 118), (130, 70, 160), (226, 100, 130), (255, 150, 80), (255, 214, 130)], (255, 240, 180)),
    "dusk": ([(30, 40, 100), (76, 70, 160), (160, 96, 180), (240, 130, 150), (255, 190, 140)], (255, 222, 196)),
    "golden": ([(70, 76, 130), (160, 120, 140), (244, 166, 100), (255, 204, 100), (255, 240, 170)], (255, 250, 210)),
    "fire": ([(50, 24, 70), (140, 36, 76), (230, 70, 56), (255, 132, 46), (255, 200, 90)], (255, 230, 150)),
    "pastel": ([(96, 110, 180), (170, 150, 210), (244, 172, 200), (255, 196, 176), (255, 230, 196)], (255, 248, 230)),
}


def _hash(x, y):
    n = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 65535.0


class Murmuration(Scene):
    name = "murmuration"
    title = "Murmuration"
    blurb = "a starling murmuration swirls over a sunset lake, bending around a diving falcon"
    tags = ("nature", "creatures", "sky", "calm", "sunset")
    interactions = "point to make the flock swerve around you, click to send the falcon diving there"
    options = {
        "birds": (0, "number of starlings (0 = based on screen size)"),
        "predator": (True, "a falcon dives through now and then"),
        "palette": ("random", "random, sunset, dusk, golden, fire or pastel"),
    }

    # ------------------------------------------------------------------ setup
    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        pal = self.opt("palette")
        if pal not in PALETTES:
            pal = rng.choice(list(PALETTES))
        stops, sun_col = PALETTES[pal]
        hue_shift = rng.uniform(-0.03, 0.03)
        self.stops = [self._shift(c, hue_shift) for c in stops]
        self.sun_col = sun_col
        self.horizon = int(h * rng.uniform(0.6, 0.7))
        self.sun_x = rng.uniform(0.15, 0.85) * w
        self.sun_r = clamp(w * rng.uniform(0.035, 0.055), 2.5, 9.0)
        self.cloudiness = rng.uniform(0.25, 0.75)
        self.cloud_seed = rng.randrange(1000)
        self.tree_seed = rng.randrange(1000)
        self.tree_h = rng.uniform(1.0, 3.0)
        self.sun_y = self.horizon - self.tree_h - 1 - self.sun_r / ASPECT * rng.uniform(0.2, 1.6)
        self.tree_kind = rng.choice(("forest", "poplars", "hills", "reeds"))
        self.bake()
        # flock genome
        area = w * h
        n = self.opt("birds") or int(clamp(area / 9 * self.density, 80, 850))
        n = int(clamp(n, 5, 1500))
        self.speed = rng.uniform(11, 16)
        self.r_see = rng.uniform(3.2, 4.6)
        self.r_sep = rng.uniform(1.3, 1.9)
        self.k_coh = rng.uniform(0.5, 1.2)
        self.k_ali = rng.uniform(1.2, 2.2)
        self.k_sep = rng.uniform(26, 40)
        self.k_att = rng.uniform(0.3, 0.6)
        self.topo = rng.choice((6, 7, 7, 8))
        rx = rng.uniform(0.1, 0.17) * w
        self.roost = (rx, rx * rng.uniform(0.35, 0.6))
        self.att_seed = rng.uniform(0, 100)
        self.att_fx, self.att_fy = rng.uniform(0.05, 0.11), rng.uniform(0.07, 0.15)
        self.lobes = rng.choice((1, 1, 2))   # one cloud, or a cloud that keeps splitting in two
        top, bot = h * 0.16 * ASPECT, (self.horizon - 3) * ASPECT
        self.sky_box = (top, bot)
        cx, cy = rng.uniform(0.3, 0.7) * w, rng.uniform(0.3, 0.5) * h * ASPECT
        self.birds = []
        for _ in range(n):
            a = rng.uniform(0, TAU)
            rr = rng.uniform(0, 1) ** 0.5 * min(w, h * ASPECT) * 0.15
            ang = rng.uniform(-0.4, 0.4) + (0 if rng.random() < 0.5 else math.pi)
            self.birds.append([cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.5,
                               math.cos(ang) * self.speed, math.sin(ang) * self.speed * 0.3,
                               rng.uniform(0, TAU), rng.uniform(5, 8)])
        # falcon
        self.fal = None
        self.fal_timer = rng.uniform(6, 14)
        self.fal_target = None   # where a click told the falcon to dive (stretched coords)
        self.frame = 0
        self.ripple = [rng.uniform(-1, 1) for _ in range(97)]

    @staticmethod
    def _shift(c, dh):
        if not dh:
            return c
        r, g, b = c[0] / 255, c[1] / 255, c[2] / 255
        mx, mn = max(r, g, b), min(r, g, b)
        d = mx - mn
        if d == 0:
            return c
        if mx == r:
            hh = ((g - b) / d) % 6
        elif mx == g:
            hh = (b - r) / d + 2
        else:
            hh = (r - g) / d + 4
        return hsv(hh / 6 + dh, d / mx, mx)

    def sky_at(self, x, y):
        """(glyph value, final rgb) of the sky at a cell, sun and clouds included."""
        hz = self.horizon
        f = clamp(y / max(1, hz))
        col = gradient(self.stops, f ** 1.15)
        bright = 0.8 + 0.2 * f ** 0.8
        # brush-stroke texture: long horizontal streaks
        streak = fbm(x * 0.035, y * 0.45, 3, self.cloud_seed + 3)
        vg = 0.4 + 0.1 * f + 0.5 * streak
        # sun glow
        dx = (x + 0.5 - self.sun_x)
        dy = (y + 0.5 - self.sun_y) * ASPECT
        d = math.hypot(dx, dy) / self.sun_r
        glow = math.exp(-d * 0.3) * 0.6 + math.exp(-(((y - hz) * 0.5) ** 2)) * 0.25 * math.exp(-abs(dx) / (self.w * 0.35))
        vg += glow * 0.35
        bright += glow * 0.35
        col = mix(col, self.sun_col, clamp(glow * 0.8))
        # long thin clouds lit from below
        c = fbm(x * 0.016, y * 0.3, 3, self.cloud_seed) + 0.3 * noise2(x * 0.06, y * 0.55, self.cloud_seed + 9)
        c = (c + 0.12 - (1 - self.cloudiness) * 0.55) * 2.4
        if c > 0 and f > 0.12:
            lit = mix(mix(self.stops[2], (255, 150, 170), 0.35), self.sun_col, clamp(glow * 1.5))
            dark = scale(self.stops[1], 0.75)
            under = clamp(0.5 + 0.5 * math.sin(y * 1.9 + x * 0.013))
            cc = mix(dark, lit, 0.35 + 0.65 * under * f)
            k = clamp(c)
            col = mix(col, cc, k * 0.85)
            vg += k * (0.15 + 0.2 * under)
        vg += (_hash(x, y) - 0.5) * 0.1
        if d < 1.0:
            col = mix(self.sun_col, (255, 255, 245), (1 - d) * 0.8)
            vg = 2.0
            bright = 1.0
        return clamp(vg, 0.12, 1.0) if vg < 2 else 2.0, scale(col, clamp(bright, 0, 1.0))

    def bake(self):
        """Pre-render sky, treeline and the lake's reflection source."""
        w, h = self.w, self.h
        hz = self.horizon
        self.bg_ch = [" "] * (w * h)
        self.bg_fg = [None] * (w * h)
        self.bg_v = [0.0] * (w * h)
        self.sky = [None] * (w * (hz + 1))
        for y in range(0, hz + 1):
            for x in range(w):
                v, col = self.sky_at(x, y)
                self.sky[y * w + x] = (v, col)
                if y < h:
                    i = y * w + x
                    self.bg_ch[i] = "█" if v > 1.5 else "░" if v < 0.22 else "▒" if v < 0.45 else "▓"
                    v = min(v, 1.0)
                    self.sky[y * w + x] = (v, col)
                    k = 0.85 + 0.15 * v
                    self.bg_fg[i] = (int(min(252, col[0] * k)) & ~3, int(min(252, col[1] * k)) & ~3,
                                     int(min(252, col[2] * k)) & ~3)
                    self.bg_v[i] = v
        # treeline: a silhouette whose top edge catches the light
        rng = self.rng
        self.tree_top = []
        poplars = [(rng.uniform(0, w), rng.uniform(2, 6), rng.uniform(1.2, 2.2)) for _ in range(int(w / 12))]
        for x in range(w):
            n = fbm(x * 0.05, 0.5, 3, self.tree_seed)
            if self.tree_kind == "hills":
                th = self.tree_h * 1.3 + n * 2.5 + 1.5 * math.sin(x * 0.03 + self.tree_seed)
            elif self.tree_kind == "reeds":
                th = 0.6 + abs(n) * 1.2
            else:
                th = self.tree_h + n * 2.2 + 0.8 * noise1(x * 0.4, self.tree_seed)
                if self.tree_kind == "poplars":
                    for px, ph, pw in poplars:
                        d = abs(x - px) / pw
                        if d < 1:
                            th = max(th, self.tree_h + ph * (1 - d * d) ** 0.5)
            self.tree_top.append(max(0.3, th))
        for x in range(w):
            top = hz - self.tree_top[x]
            for y in range(max(0, int(top)), min(h, hz + 1)):
                i = y * w + x
                if y == int(top) and top - int(top) < 0.6:
                    # rim: a dim crown edge against the sky
                    v, col = self.sky[min(hz, y) * w + x]
                    left = self.tree_top[x - 1] if x > 0 else self.tree_top[x]
                    right = self.tree_top[x + 1] if x < w - 1 else self.tree_top[x]
                    ch = "^" if left < self.tree_top[x] > right else "/" if right > left + 0.3 else "\\" if left > right + 0.3 else "-"
                    if self.tree_kind == "reeds":
                        ch = "|" if (x * 7) % 3 else "/"
                    self.bg_ch[i] = ch
                    self.bg_fg[i] = tuple(int(c * 0.22) & ~3 for c in col)
                    self.bg_v[i] = 0.3
                else:
                    self.bg_ch[i] = " "
                    self.bg_fg[i] = None
                    self.bg_v[i] = 0.0
        # foreground reeds standing in the water
        self.reeds = []
        for _ in range(int(w / rng.uniform(3, 6))):
            x = rng.uniform(0, w)
            if rng.random() < 0.6:
                x = rng.choice((rng.uniform(0, w * 0.2), rng.uniform(w * 0.8, w)))
            self.reeds.append((x, rng.uniform(1.5, max(2.0, (h - hz) * 0.75)), rng.uniform(-0.4, 0.4), rng.uniform(0, TAU),
                               rng.random() < 0.35))

    def on_click(self, x, y):
        w = self.w
        top, bot = self.sky_box
        tx = clamp(x if x == x else w / 2, 0, w - 1)
        ty = clamp((y if y == y else 0) * ASPECT, top, bot)
        self.fal_target = (tx, ty)
        sp = self.speed * 2.3
        if self.fal is None:
            # stoop in from high up on the far side
            side = 1 if tx < w / 2 else -1
            fx, fy = tx + side * w * 0.45, top - 6
            d = math.hypot(tx - fx, ty - fy) or 1
            self.fal = [fx, fy, (tx - fx) / d * sp, (ty - fy) / d * sp, 0.0, 0.0]
        else:
            self.fal[4] = 0.0     # already out hunting: wheel round toward the click

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 1 / 15)
        t = self.t
        rng = self.rng
        w = self.w
        top, bot = self.sky_box
        birds = self.birds
        n = len(birds)
        # wandering attractor (or two, for flocks that split and merge)
        ax = w * (0.5 + 0.33 * noise1(t * self.att_fx + self.att_seed, 1) + 0.12 * math.sin(t * 0.05 + self.att_seed))
        ay = top + (bot - top) * (0.45 + 0.35 * noise1(t * self.att_fy + self.att_seed * 2, 2))
        atts = [(ax, ay)]
        if self.lobes == 2:
            sep = (0.5 + 0.5 * math.sin(t * 0.07 + self.att_seed)) * w * 0.22
            atts = [(ax - sep, ay), (ax + sep, ay + sep * 0.15)]
        self.atts = atts
        # falcon
        fal = self.fal
        if self.opt("predator") or fal is not None:
            if fal is None:
                self.fal_timer -= dt
                if self.fal_timer <= 0 and n:
                    side = rng.choice((-1, 1))
                    cx = sum(b[0] for b in birds[::7]) / len(birds[::7])
                    cy = sum(b[1] for b in birds[::7]) / len(birds[::7])
                    fx = cx - side * w * 0.6
                    fy = top - 4
                    d = math.hypot(cx - fx, cy - fy) or 1
                    sp = self.speed * rng.uniform(1.7, 2.1)
                    self.fal = fal = [fx, fy, (cx - fx) / d * sp, (cy - fy) / d * sp, 0.0, 0.0]
            else:
                fal[0] += fal[2] * dt
                fal[1] += fal[3] * dt
                fal[4] += dt
                fal[5] += dt * 7
                tg = self.fal_target
                if tg is not None:
                    # a clicked dive: home hard on the spot, then sweep on through
                    dx, dy = tg[0] - fal[0], tg[1] - fal[1]
                    d = math.hypot(dx, dy) or 1
                    sp = max(self.speed * 2.3, math.hypot(fal[2], fal[3]))
                    k = min(1.0, dt * 4.0)
                    fal[2] += (dx / d * sp - fal[2]) * k
                    fal[3] += (dy / d * sp - fal[3]) * k
                    if d < 3.0 or fal[4] > 4.0:
                        self.fal_target = None
                elif fal[4] < 2.2 and n:
                    # home on the nearest part of the flock for a moment
                    b = birds[int(fal[4] * 97) % n]
                    dx, dy = b[0] - fal[0], b[1] - fal[1]
                    d = math.hypot(dx, dy) or 1
                    sp = math.hypot(fal[2], fal[3])
                    fal[2] += (dx / d * sp - fal[2]) * dt * 0.8
                    fal[3] += (dy / d * sp - fal[3]) * dt * 0.8
                if self.fal_target is None and (fal[0] < -20 or fal[0] > w + 20 or fal[1] < top - 30
                                                or fal[1] > bot + 10 or fal[4] > 12):
                    self.fal = fal = None
                    self.fal_timer = rng.uniform(10, 22)
        # spatial hash
        cs = self.r_see
        grid = {}
        for i, b in enumerate(birds):
            key = (int(b[0] // cs), int(b[1] // cs))
            cell = grid.get(key)
            if cell is None:
                grid[key] = [i]
            else:
                cell.append(i)
        rs2 = self.r_see * self.r_see
        sep2 = self.r_sep * self.r_sep
        rsep = self.r_sep
        r0x, r0y = self.roost
        topo = self.topo
        kc, ka, ks, kt = self.k_coh, self.k_ali, self.k_sep, self.k_att
        sp0 = self.speed
        vmax, vmin = sp0 * 1.35, sp0 * 0.65
        par = self.frame & 1
        self.frame += 1
        big = n > 300
        order = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))
        ptr = self.pointer
        if ptr is not None:   # the pointer is a hawk the flock swerves around
            ppx, ppy = ptr[0], ptr[1] * ASPECT
            pr = max(9.0, min(w, bot) * 0.16)
            pr2 = pr * pr
        for i, b in enumerate(birds):
            x, y, vx, vy = b[0], b[1], b[2], b[3]
            if not big or (i & 1) == par:
                gx, gy = int(x // cs), int(y // cs)
                cnt = 0
                sx = sy = avx = avy = cx = cy = 0.0
                for ox, oy in order:
                    cell = grid.get((gx + ox, gy + oy))
                    if cell is None:
                        continue
                    m = len(cell)
                    off = (i * 7) % m             # start somewhere different for every bird
                    for q in range(m):
                        j = cell[(off + q) % m]
                        if j == i:
                            continue
                        o = birds[j]
                        dx, dy = o[0] - x, o[1] - y
                        d2 = dx * dx + dy * dy
                        if d2 < rs2:
                            cnt += 1
                            cx += dx
                            cy += dy
                            avx += o[2]
                            avy += o[3]
                            if d2 < sep2:
                                k = 1.0 / (d2 + 0.04)
                                sx -= dx * k
                                sy -= dy * k
                            if cnt >= topo:
                                break
                    if cnt >= topo:
                        break
                ax_ = ay_ = 0.0
                if cnt:
                    inv = 1.0 / cnt
                    ax_ += cx * inv * kc + (avx * inv - vx) * ka * 0.5 + sx * ks
                    ay_ += cy * inv * kc + (avy * inv - vy) * ka * 0.5 + sy * ks
                # attractor: gentle when near, firmer when strays
                best = None
                for tx, ty in atts:
                    dx, dy = tx - x, ty - y
                    d2 = dx * dx + dy * dy
                    if best is None or d2 < best[0]:
                        best = (d2, dx, dy)
                # the roost: an ellipse the flock is free to roam inside; outside it, a firm pull
                ex, ey = best[1] / r0x, best[2] / r0y
                d = math.sqrt(ex * ex + ey * ey) + 1e-6
                pull = kt * (0.25 + 6.0 * max(0.0, d - 1.0))
                dd = math.sqrt(best[0]) + 1e-6
                ax_ += best[1] / dd * pull * 3
                ay_ += best[2] / dd * pull * 3
                # keep inside the sky band
                if y < top:
                    ay_ += (top - y) * 2.5
                elif y > bot:
                    ay_ -= (y - bot) * 3.5
                if x < 2:
                    ax_ += (2 - x) * 1.5
                elif x > w - 2:
                    ax_ -= (x - w + 2) * 1.5
                if ptr is not None:
                    dx, dy = x - ppx, y - ppy
                    d2 = dx * dx + dy * dy
                    if d2 < pr2:
                        d = math.sqrt(d2) + 0.3
                        k = (pr + 0.5 - d) * 14 / d
                        ax_ += dx * k
                        ay_ += dy * k
                if fal is not None:
                    dx, dy = x - fal[0], y - fal[1]
                    d2 = dx * dx + dy * dy
                    if d2 < 200:
                        d = math.sqrt(d2) + 0.3
                        k = (14.2 - d) * 9 / d
                        ax_ += dx * k
                        ay_ += dy * k
                b[4] = ax_
                b[5] = ay_
            vx += b[4] * dt * 2.0
            vy += b[5] * dt * 2.0
            s = math.hypot(vx, vy) or 1e-6
            if s > vmax:
                vx, vy = vx / s * vmax, vy / s * vmax
            elif s < vmin:
                vx, vy = vx / s * vmin, vy / s * vmin
            b[0] = x + vx * dt
            b[1] = y + vy * dt
            b[2] = vx
            b[3] = vy

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        w, h = self.w, self.h
        if cv.w != w or cv.h != h:
            return
        t = self.t
        hz = self.horizon
        cv.ch[:] = self.bg_ch
        cv.fg[:] = self.bg_fg
        cv.lv[:] = self.bg_v
        # bird density grid (cells)
        dens = {}
        for b in self.birds:
            xi = int(b[0])
            yi = int(b[1] / ASPECT)
            if 0 <= xi < w and 0 <= yi < hz:
                k = yi * w + xi
                dens[k] = dens.get(k, 0) + 1
        # lake: rippled reflection of the sky (and of the birds)
        sky = self.sky
        rip = self.ripple
        glyphs = "  .-░░░▒▒▓▓"
        sun_x = self.sun_x
        for y in range(hz + 1, h):
            depth = (y - hz) / max(1, h - hz)
            src = hz - (y - hz) * 1.0 - 1
            sy = int(clamp(src, 0, hz))
            amp = 0.4 + depth * 2.5
            row_off = math.sin(y * 1.3 + t * 1.1) * amp
            base = y * w
            for x in range(w):
                jit = rip[(x + y * 7 + int(t * 6)) % 97] * amp * 0.6
                sx = int(x + row_off + jit)
                sx = 0 if sx < 0 else w - 1 if sx >= w else sx
                v, col = sky[sy * w + sx]
                if self.bg_v[sy * w + sx] == 0.0 and sy > hz - 6:
                    v, col = 0.0, col          # treeline reflects as dark
                v = v * (0.78 - 0.18 * depth)
                # glitter road under the sun
                gd = abs(x - sun_x) / (self.sun_r * (1.2 + depth * 2.5))
                if gd < 1 and rip[(x * 3 + y * 11 + int(t * 5)) % 97] > 0.35 + gd * 0.6:
                    v = 0.7 + 0.25 * (1 - gd)
                    col = self.sun_col
                if dens.get(sy * w + sx):
                    v *= 0.35
                i = base + x
                if v < 0.06:
                    cv.ch[i] = " "
                    cv.fg[i] = None
                    cv.lv[i] = 0.0
                    continue
                k = 0.7 + 0.3 * v
                ch = glyphs[int(v * 10 + 0.5)]
                if rip[(x * 5 + y * 13 + int(t * 3)) % 97] > 0.72 - depth * 0.25:
                    ch = "~" if v > 0.3 else "-"          # ripple lines break up the mirror
                cv.ch[i] = ch
                cv.fg[i] = (int(min(252, col[0] * k * 0.85)) & ~3, int(min(252, col[1] * k * 0.92)) & ~3,
                            int(min(252, col[2] * k * 1.05 + 8)) & ~3)
                cv.lv[i] = v
        # birds: dark marks; crowded cells blot out the sky. Single birds use half-row ticks
        # (' up high in the cell, , low) so sparse edges get twice the vertical detail.
        for b in self.birds:
            xi = int(b[0])
            yf = b[1] / ASPECT
            yi = int(yf)
            if not (0 <= xi < w and 0 <= yi < hz):
                continue
            i = yi * w + xi
            nb = dens.get(i, 0)
            if nb == 0:
                continue
            dens[i] = 0
            v, col = sky[i]
            if nb == 1:
                ph = (t * 1.6 * b[5] / 6 + b[4]) % 1.0
                low = yf - yi > 0.5
                if ph < 0.3:
                    ch = "v"
                elif ph < 0.55:
                    ch = "-" if abs(b[3]) < abs(b[2]) else ("," if low else "'")
                else:
                    ch = "," if low else "`"
                cv.put(xi, yi, ch, scale(col, 0.3), level=0.4)
            elif nb == 2:
                cv.put(xi, yi, ":" if (xi + yi) & 1 else "w", scale(col, 0.22), level=0.4)
            elif nb <= 4:
                cv.put(xi, yi, ";" if (xi * 3 + yi) % 4 else "%", scale(col, 0.13), level=0.4)
            else:
                cv.ch[i] = " "
                cv.fg[i] = None
        # falcon: a crisp dark silhouette with beating wings
        fal = self.fal
        if fal is not None:
            fx, fy = int(fal[0]), int(fal[1] / ASPECT)
            up = math.sin(fal[5]) > 0
            right = fal[2] > 0
            # a black cut-out, wider than any starling: swept wings beating up and down
            if up:
                shape = [(-4, -1), (-3, -1), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (3, -1), (4, -1), (0, 1)]
            else:
                shape = [(-4, 1), (-3, 0), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (3, 0), (4, 1), (0, 1)]
            for dx, dy in shape:
                x, y = fx + dx, fy + dy
                if 0 <= x < w and 0 <= y < hz:
                    i = y * w + x
                    cv.ch[i] = " "
                    cv.fg[i] = None
            x = fx + (1 if right else -1)
            if 0 <= x < w and 0 <= fy < hz:
                cv.put(x, fy, ">" if right else "<", scale(sky[fy * w + x][1], 0.25), level=0.5)
        # reeds in front of the water
        for rx, rh, lean, ph, tuft in self.reeds:
            sway = lean + 0.25 * math.sin(t * 0.7 + ph)
            n = int(rh)
            for k in range(n):
                f = k / max(1, rh)
                x = rx + sway * f * f * rh * 0.5
                y = h - 1 - k
                ch = "|" if abs(sway * f) < 0.2 else ("/" if sway > 0 else "\\")
                if tuft and k == n - 1:
                    ch = "$" if (int(rx) & 1) else "&"
                cv.put(x, y, ch, (28, 20, 30), level=0.5)
