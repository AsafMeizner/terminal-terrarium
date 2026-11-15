"""Flying through space: 3D stars streaking past, nebula clouds drifting by, optional hyperspace."""
import math

from ..engine import ASPECT, Scene, clamp, fbm, mix

# nebula palettes: each cloud blends two colors from one of these
NEBULA_PALETTES = {
    "classic": [(255, 80, 170), (110, 90, 255), (60, 200, 255), (255, 120, 70), (170, 80, 255),
                (60, 230, 180)],
    "orion": [(255, 90, 140), (255, 150, 90), (200, 70, 200), (255, 200, 150)],
    "teal": [(40, 220, 200), (60, 140, 255), (120, 255, 200), (40, 90, 200)],
    "violet": [(170, 80, 255), (255, 90, 200), (110, 90, 255), (220, 150, 255)],
    "ember": [(255, 110, 50), (255, 60, 90), (255, 180, 80), (200, 50, 60)],
    "aurora": [(80, 255, 160), (60, 200, 255), (180, 120, 255), (120, 255, 220)],
}
# star color temperature mixes: (cool blue-white, white, warm) weights
TEMPS = {"cool": (0.6, 0.3, 0.1), "balanced": (0.35, 0.35, 0.3), "warm": (0.15, 0.35, 0.5)}
COOL = [(170, 200, 255), (200, 220, 255), (190, 210, 255)]
WHITE = [(255, 255, 255), (240, 240, 255), (255, 250, 240)]
WARM = [(255, 240, 210), (255, 210, 170), (255, 190, 140)]
TEX = 64          # nebula noise texture size
POINT_GLYPHS = "..·+**"
STREAK = "-\\|/-\\|/"     # by direction, in 45 degree steps


class Star:
    __slots__ = ("x", "y", "z", "col", "mag", "px", "py")


class Starfield(Scene):
    name = "starfield"
    title = "Starfield"
    blurb = "flying through space past streaking stars and drifting nebulae"
    tags = ("space", "retro", "fast")
    options = {
        "speed": (1.0, "cruising speed"),
        "warp": (False, "jump to hyperspace now and then"),
        "stars": (1.0, "amount of stars"),
        "nebulae": (True, "colorful nebula clouds drifting past"),
        "palette": ("random", "nebula colors: classic, orion, teal, violet, ember, aurora or random"),
    }

    DEPTH = 32.0

    def setup(self):
        w, h = self.w, self.h
        rng = self.rng
        if not hasattr(self, "style"):
            pal = self.opt("palette")
            if pal not in NEBULA_PALETTES:
                pal = rng.choice(list(NEBULA_PALETTES))
            self.style = {
                "palette": pal,
                "temps": TEMPS[rng.choice(list(TEMPS))],
                "roll": rng.uniform(0.02, 0.09) * rng.choice((-1, 1)),
                "sway": rng.uniform(0.0, 0.06),
                "fov": rng.uniform(0.45, 0.65),
                "neb_n": rng.choice((1, 2, 2, 3)),
            }
        st = self.style
        self.neb_colors = NEBULA_PALETTES[st["palette"]]
        self.f = max(w, h * ASPECT) * st["fov"]       # focal length in x cells
        n = int(clamp(w * h / 9.0, 120, 1600) * max(0.05, self.opt("stars")) * self.density)
        self.stars = [self._star(rng.uniform(0.5, self.DEPTH)) for _ in range(n)]
        self.roll = 0.0
        self.z_travel = 0.0
        self.speed = self.opt("speed") * 4.0
        self.warp_k = 0.0          # 0 cruise .. 1 full hyperspace
        self.warp_t = rng.uniform(0, 6)
        # a tileable-ish noise texture for nebulae (sampled, not recomputed per frame)
        seed = rng.randrange(1000)
        self.tex = [[clamp(0.5 + 1.1 * fbm(x / 9.0, y / 9.0, 4, seed)) for x in range(TEX)] for y in range(TEX)]
        self.nebulae = []
        if self.opt("nebulae"):
            for k in range(st["neb_n"]):
                self.nebulae.append(self._nebula(rng.uniform(8, self.DEPTH * 2.2) + k * self.DEPTH))

    def _star(self, z):
        rng = self.rng
        s = Star()
        # spread over a wide box so the edges stay populated at any aspect
        s.x = rng.uniform(-1, 1) * self.DEPTH * 0.9
        s.y = rng.uniform(-1, 1) * self.DEPTH * 0.9
        s.z = z
        s.col = rng.choice(rng.choices((COOL, WHITE, WARM), self.style["temps"])[0])
        s.mag = rng.uniform(0.35, 1.0) ** 1.5
        s.px = s.py = None
        return s

    def _nebula(self, z):
        rng = self.rng
        a = rng.uniform(0, math.tau)
        d = rng.uniform(4, 14)
        return {"x": math.cos(a) * d, "y": math.sin(a) * d, "z": z, "r": rng.uniform(7, 14),
                "c1": rng.choice(self.neb_colors), "c2": rng.choice(self.neb_colors),
                "u": rng.uniform(0, TEX), "v": rng.uniform(0, TEX)}

    def update(self, dt):
        super().update(dt)
        rng = self.rng
        if self.opt("warp"):
            # cruise -> spool up -> hyperspace -> drop out, on a loop
            self.warp_t += dt
            cyc = self.warp_t % 24.0
            if cyc < 8:
                target = 0.0
            elif cyc < 19:
                target = 1.0
            else:
                target = 0.0
            rate = 0.35 if target > self.warp_k else 0.6
            self.warp_k += clamp(target - self.warp_k, -rate * dt, rate * dt)
        else:
            self.warp_k = max(0.0, self.warp_k - dt)
        wk = self.warp_k * self.warp_k * (3 - 2 * self.warp_k)
        v = self.speed * (1 + 18 * wk)
        self.cur_speed = v
        st = self.style
        self.roll += dt * (st["roll"] + st["sway"] * math.sin(self.t * 0.13)) * (1 - 0.7 * wk)
        dz = v * dt
        D = self.DEPTH
        for s in self.stars:
            s.z -= dz
            if s.z < 0.3:
                ns = self._star(s.z + D)
                s.x, s.y, s.z, s.col, s.mag = ns.x, ns.y, ns.z, ns.col, ns.mag
        for k, nb in enumerate(self.nebulae):
            nb["z"] -= dz * 0.5          # nebulae are huge and far: they drift past slower
            if nb["z"] < -nb["r"] * 0.5:
                self.nebulae[k] = self._nebula(D * rng.uniform(1.6, 2.6))

    def draw(self, cv):
        W, H = cv.w, cv.h
        cx, cy = W / 2.0, H / 2.0
        f = self.f
        cr, sr = math.cos(self.roll), math.sin(self.roll)
        wk = self.warp_k * self.warp_k * (3 - 2 * self.warp_k)
        if self.nebulae:
            self.draw_nebulae(cv, cx, cy, cr, sr, wk)
        if wk > 0.05:
            # hyperspace tunnel glow at the vanishing point
            rr = 3 + 6 * wk
            for y in range(int(cy - rr / ASPECT), int(cy + rr / ASPECT) + 1):
                for x in range(int(cx - rr), int(cx + rr) + 1):
                    d = math.hypot(x + 0.5 - cx, (y + 0.5 - cy) * ASPECT) / rr
                    if d < 1:
                        cv.shade(x, y, (1 - d) ** 3 * 0.8 * wk, (170, 210, 255))
        speed = self.cur_speed
        # streak length: how far back in time (seconds) the tail reaches
        tail_dt = 0.04 + 0.16 * wk
        D = self.DEPTH
        shade = cv.shade
        for s in self.stars:
            z = s.z
            if z <= 0.3:
                continue
            x = s.x * cr - s.y * sr
            y = s.x * sr + s.y * cr
            iz = f / z
            hx = cx + x * iz
            hy = cy + y * iz / ASPECT
            if not (-2 <= hx < W + 2 and -2 <= hy < H + 2):
                continue
            z2 = z + speed * tail_dt
            iz2 = f / z2
            tx = cx + x * iz2
            ty = cy + y * iz2 / ASPECT
            near = clamp(1 - z / D)
            bright = min(0.85, s.mag * (0.3 + 0.75 * near ** 1.3) * (1 + 0.5 * wk))
            col = s.col
            if wk > 0:
                col = mix(col, (150, 200, 255), wk * 0.7)
            dx, dy = hx - tx, (hy - ty)
            steps = int(max(abs(dx), abs(dy)))
            if steps <= 0:
                ix, iy = int(hx), int(hy)
                if 0 <= ix < W and 0 <= iy < H and bright > cv.lv[iy * W + ix]:
                    g = POINT_GLYPHS[min(5, int(bright * 6.5))]
                    kk = 0.35 + 0.65 * bright
                    cv.put(ix, iy, g, (col[0] * kk, col[1] * kk, col[2] * kk), level=bright)
                continue
            steps = min(steps, 160)
            inv = 1.0 / steps
            # streaks use glyphs that follow their direction
            ang = math.atan2(dy * ASPECT, dx)
            g = STREAK[int(((ang + math.pi) / math.pi * 4 + 0.5)) % 8]
            lvl = cv.lv
            for k in range(steps + 1):
                u = k * inv                     # 0 tail .. 1 head
                ix = int(tx + dx * u)
                iy = int(ty + dy * u)
                if 0 <= ix < W and 0 <= iy < H:
                    v = bright * (0.2 + 0.8 * u * u)
                    j = iy * W + ix
                    if v > lvl[j]:
                        kk = 0.25 + 0.75 * v
                        cv.put(ix, iy, g if k < steps else POINT_GLYPHS[min(5, int(bright * 6.5))],
                               (col[0] * kk, col[1] * kk, col[2] * kk), level=v)

    def draw_nebulae(self, cv, cx, cy, cr, sr, wk):
        W, H = cv.w, cv.h
        f = self.f
        tex = self.tex
        D = self.DEPTH
        for nb in sorted(self.nebulae, key=lambda n: -n["z"]):
            z = nb["z"]
            zc = max(z, 1.0)
            x = nb["x"] * cr - nb["y"] * sr
            y = nb["x"] * sr + nb["y"] * cr
            iz = f / zc
            px, py = cx + x * iz, cy + y * iz / ASPECT
            rad = nb["r"] * iz
            # fade in from the distance, out as it passes us
            fade = clamp((D * 2.6 - z) / (D * 0.8)) * clamp((z + nb["r"] * 0.5) / (nb["r"] * 0.8))
            if fade <= 0.01 or rad < 1.5:
                continue
            x0, x1 = max(0, int(px - rad)), min(W, int(px + rad) + 1)
            y0, y1 = max(0, int(py - rad / ASPECT)), min(H, int(py + rad / ASPECT) + 1)
            if x0 >= x1 or y0 >= y1:
                continue
            ts = TEX * 1.7 / (2 * rad)       # texture cells per screen cell
            c1, c2 = nb["c1"], nb["c2"]
            u0, v0 = nb["u"], nb["v"]
            maxrad = max(W, H * ASPECT) * 0.9
            fade *= clamp((maxrad - rad) / (maxrad * 0.5))
            if fade <= 0.01:
                continue
            amp = 0.8 * fade * (1 - 0.6 * wk)
            irad = 1.0 / rad
            for yy in range(y0, y1):
                dyy = (yy + 0.5 - py) * ASPECT * irad
                dy2 = dyy * dyy
                if dy2 >= 1:
                    continue
                ty_ = v0 + (yy - py) * ASPECT * ts
                trow = tex[int(ty_) % TEX]
                trow2 = tex[int(ty_ * 3.7 + 17) % TEX]
                for xx in range(x0, x1):
                    dxx = (xx + 0.5 - px) * irad
                    d2 = dxx * dxx + dy2
                    if d2 >= 1:
                        continue
                    tx_ = u0 + (xx - px) * ts
                    n = trow[int(tx_) % TEX] * 0.72 + trow2[int(tx_ * 3.7 + 5) % TEX] * 0.28
                    fall = (1 - d2) ** 1.6
                    v = (0.04 + 1.5 * n * n) * fall * amp
                    if v > 0.1:
                        cv.shade(xx, yy, v, mix(c1, c2, clamp(n * 1.4 - 0.2)), mode="add")
