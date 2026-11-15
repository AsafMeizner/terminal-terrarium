"""An octopus on the seabed: breathing mantle, eight curling arms with suckers, colour ripples, ink."""
import math

from ..engine import ASPECT, Scene, clamp, fbm, gradient, hsv, mix, noise2, scale, smoothstep

TAU = math.tau

# skin palettes: dark .. mid .. light, plus a contrast colour for chromatophore flashes and a sucker colour
PALETTES = {
    "coral": ([(70, 14, 12), (170, 45, 30), (240, 105, 60), (255, 185, 130)], (90, 10, 40), (255, 215, 190)),
    "violet": ([(40, 12, 60), (120, 40, 150), (200, 100, 230), (245, 190, 255)], (20, 10, 70), (250, 220, 255)),
    "teal": ([(6, 40, 44), (20, 110, 110), (60, 200, 175), (180, 255, 225)], (40, 20, 80), (220, 255, 240)),
    "amber": ([(60, 30, 8), (150, 85, 25), (230, 160, 55), (255, 225, 150)], (90, 20, 10), (255, 240, 205)),
    "rose": ([(70, 16, 40), (180, 50, 100), (245, 120, 165), (255, 205, 220)], (60, 10, 70), (255, 230, 240)),
    "ghost": ([(30, 40, 70), (90, 110, 160), (175, 195, 235), (240, 245, 255)], (110, 40, 120), (255, 255, 255)),
}


def stroke(cells, w, h, pts, widths, step=0.45):
    """Stamp a tapered tube into `cells` (key -> [dn, s, side]) keeping the nearest sample per cell.

    pts are (x cells, y aspect units); widths are half-widths in the same units."""
    n = len(pts)
    if n < 2:
        return
    sqrt = math.sqrt
    for i in range(n - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        seg = sqrt(dx * dx + dy * dy)
        k = max(1, int(seg / step))
        w0, w1 = widths[i], widths[i + 1]
        tx, ty = (dx / seg, dy / seg) if seg > 1e-6 else (1.0, 0.0)
        for j in range(k):
            f = j / k
            px = ax + dx * f
            py = ay + dy * f
            r = w0 + (w1 - w0) * f
            if r < 0.3:
                r = 0.3
            s = (i + f) / (n - 1)
            x0 = int(px - r)
            x1 = int(px + r) + 1
            y0 = int((py - r) / ASPECT)
            y1 = int((py + r) / ASPECT) + 1
            if x1 < 0 or x0 >= w or y1 < 0 or y0 >= h:
                continue
            ir = 1.0 / r
            for y in range(max(0, y0), min(h, y1)):
                ey = (y + 0.5) * ASPECT - py
                for x in range(max(0, x0), min(w, x1)):
                    ex = x + 0.5 - px
                    d2 = ex * ex + ey * ey
                    if d2 >= r * r:
                        continue
                    key = y * w + x
                    dn = sqrt(d2) * ir
                    c = cells.get(key)
                    if c is None or dn < c[0]:
                        side = tx * ey - ty * ex
                        cells[key] = [dn, s, dn if side > 0 else -dn]


class Arm:
    def __init__(self, rng, k, n_arms, near):
        self.near = near
        # direction on the seabed plane: 0 right, pi/2 away from the viewer, -pi/2 toward the viewer
        self.phi = (k + 0.5) / n_arms * TAU + rng.uniform(-0.25, 0.25)
        self.len = rng.uniform(0.8, 1.15)
        self.bend = rng.uniform(-0.8, 0.8)        # sideways sweep of the arm on the sand
        out = 1 if math.cos(self.phi) >= 0 else -1
        self.curl = rng.uniform(1.6, 3.2) * -out  # tips roll up and outward
        self.wave = rng.uniform(0.3, 0.8)
        self.speed = rng.uniform(0.25, 0.6)
        self.phase = rng.uniform(0, TAU)
        self.arch = rng.uniform(0.2, 1.4)         # how high the arm arches before touching the sand
        self.jspread = rng.uniform(-0.18, 0.18)
        self.reach = 0.0
        self.reach_target = 0.0
        self.depth = 0.0
        self.pts = []
        self.widths = []


class Puff:
    def __init__(self, x, y, vx, vy, r):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.r = r
        self.age = 0.0
        self.seed = (int(x * 13) * 7 + int(y * 17)) % 997


class Octopus(Scene):
    name = "octopus"
    title = "Octopus"
    blurb = "an octopus on the seabed: curling arms, colour-changing skin, now and then a jet and an ink cloud"
    tags = ("ocean", "nature", "creature")
    options = {
        "palette": ("random", "random, " + ", ".join(PALETTES)),
        "ink": (True, "jet away now and then, leaving an ink cloud"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        pal = self.opt("palette")
        if pal not in PALETTES:
            pal = rng.choice(list(PALETTES))
        self.skin, self.flash, self.sucker = PALETTES[pal]
        # tint the palette a little so two runs of the same palette still differ
        hs = rng.uniform(-0.04, 0.04)
        self.skin = [self.tint(c, hs) for c in self.skin]
        self.ground = min(h - 4, int(h * rng.uniform(0.66, 0.74)))
        self.persp = rng.uniform(0.38, 0.5)
        self.R = max(2.4, min(w * 0.058, h * ASPECT * 0.095) * rng.uniform(0.9, 1.08))   # mantle radius
        self.elong = rng.uniform(0.9, 1.5)        # how long the mantle bag is
        self.side = rng.choice((-1, 1))           # which way the bag droops
        self.tilt = rng.uniform(0.15, 0.45) * rng.choice((-1, 1))
        self.arm_len = self.R * rng.uniform(5.0, 6.2)
        self.spots = rng.uniform(0.35, 0.75)      # how spotty
        self.stripes = rng.random() < 0.3
        self.seed = rng.randrange(1 << 15)
        n_arms = 8
        order = list(range(n_arms))
        self.arms = []
        for k in order:
            self.arms.append(Arm(rng, k, n_arms, near=(k % 2 == 0)))
        rng.shuffle(self.arms)
        # body state
        self.x = w * rng.uniform(0.35, 0.65)
        self.y = self.rest_y()
        self.vx = self.vy = 0.0
        self.axis = -math.pi / 2 + self.tilt     # direction crown -> mantle
        self.jet = 0.0                           # 0 resting .. 1 mid-jet
        self.state = "rest"
        self.timer = rng.uniform(10, 18)
        self.reach_timer = rng.uniform(1, 4)
        self.puffs = []
        self.ripple_dir = rng.choice((-1, 1))
        self.ripple_k = rng.uniform(0.25, 0.5)
        self.ripple_speed = rng.uniform(1.2, 2.2)
        self.flash_t = 0.0
        self.next_flash = rng.uniform(4, 9)
        self.build_seabed()
        n = int(w * h / 40 * self.density)
        self.motes = [[rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.2, 1.0), rng.uniform(0, 9)] for _ in range(n)]

    @staticmethod
    def tint(c, hs):
        r, g, b = c
        # rotate hue slightly through hsv
        import colorsys
        hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        return hsv(hh + hs, ss, vv)

    def rest_y(self):
        return self.ground - self.R * 1.1 / ASPECT

    def build_seabed(self):
        rng = self.rng
        w, h = self.w, self.h
        g = self.ground
        sd = rng.randrange(999)
        sand = hsv(rng.uniform(0.07, 0.12), rng.uniform(0.3, 0.5), 0.75)
        self.sand = []
        self.height = []
        for x in range(w):
            self.height.append(g - 0.6 - 0.9 * (fbm(x * 0.04, 0.5, 2, sd) * 0.5 + 0.5))
        for y in range(int(min(self.height)), h):
            for x in range(w):
                top = self.height[x]
                if y + 1 < top:
                    continue
                depth = (y - top) / max(1, h - top)
                near = 0.35 + depth          # ripples spread out toward the viewer
                rip = math.sin(x * 0.4 / near + noise2(x * 0.05, y * 0.3, sd) * 4 + y * 0.9 / near)
                v = 0.07 + 0.07 * rip + 0.06 * fbm(x * 0.15, y * 0.4, 2, sd + 1) + 0.05 * depth
                if y < top:      # partial top cell
                    v *= 0.6
                ch = None
                if rip > 0.93 and y >= top + 1 and (x + y) % 3:
                    ch = "~" if rip > 0.97 else "-"
                self.sand.append((x, y, clamp(v, 0.04, 0.3), mix(sand, (60, 60, 90), 0.55 - 0.35 * depth), ch))
        # rocks, shells and weed
        self.rocks = []
        for _ in range(rng.randint(1, 3)):
            rx = rng.choice((rng.uniform(0.02, 0.25), rng.uniform(0.75, 0.98))) * w
            rr = rng.uniform(0.04, 0.08) * w
            self.rocks.append((rx, rr, rng.uniform(0.35, 0.6), rng.randrange(99)))
        self.shells = [(rng.uniform(0, w), rng.choice("@o*&"), hsv(rng.random(), 0.35, 0.9)) for _ in range(rng.randint(2, 6))]
        self.weeds = []
        for _ in range(rng.randint(2, 6)):
            wx = rng.choice((rng.uniform(0.0, 0.3), rng.uniform(0.7, 1.0))) * w
            self.weeds.append((wx, rng.uniform(0.25, 0.55) * h, rng.uniform(0, TAU), hsv(rng.uniform(0.22, 0.38), 0.6, 0.7)))

    # ------------------------------------------------------------------ simulation
    def update(self, dt):
        super().update(dt)
        rng = self.rng
        t = self.t
        w, h = self.w, self.h
        self.timer -= dt
        if self.state == "rest":
            self.x += math.sin(t * 0.13) * dt * 0.15
            self.y += (self.rest_y() + 0.25 * math.sin(t * 0.7) - self.y) * min(1.0, dt * 2)
            self.vx = self.vy = 0.0
            if self.timer <= 0 and self.opt("ink"):
                self.start_jet()
            elif self.timer <= 0:
                self.timer = rng.uniform(10, 18)
        elif self.state == "jet":
            self.jet = min(1.0, self.jet + dt * 4)
            self.vx *= 0.985 ** (dt * 30)
            self.vy *= 0.985 ** (dt * 30)
            self.vy += 1.2 * dt
            sp = math.hypot(self.vx, self.vy * ASPECT)
            if sp < 4.5 or self.timer <= 0:
                self.state = "sink"
                self.timer = 20
        else:   # sink: arms spread, drift down to the sand again
            self.jet = max(0.0, self.jet - dt * 0.6)
            self.vx *= 0.96 ** (dt * 30)
            self.vy += (1.4 - self.vy) * min(1.0, dt * 0.8)
            if self.y >= self.rest_y():
                self.y = self.rest_y()
                self.vy = 0
                self.state = "rest"
                self.jet = 0.0
                self.timer = rng.uniform(14, 26)
        if self.state != "rest":
            self.x += self.vx * dt
            self.y += self.vy * dt
            m = self.R * 1.2
            if self.x < m:
                self.x, self.vx = m, abs(self.vx) * 0.5
            elif self.x > w - m:
                self.x, self.vx = w - m, -abs(self.vx) * 0.5
            top = self.R * (1.2 + self.elong) / ASPECT
            if self.y < top:
                self.y, self.vy = top, abs(self.vy) * 0.3
        # body axis: upright at rest, along the motion while jetting
        target = -math.pi / 2 + self.tilt + 0.06 * math.sin(t * 0.4)
        if self.state == "jet":
            target = math.atan2(self.vy * ASPECT, self.vx)
        elif self.state == "sink":
            target = -math.pi / 2 + self.tilt * 0.5 + 0.3 * math.sin(t * 0.8) * self.jet
        da = (target - self.axis + math.pi) % TAU - math.pi
        self.axis += da * min(1.0, dt * (5 if self.state == "jet" else 1.5))
        # an arm now and then reaches out to explore
        self.reach_timer -= dt
        if self.reach_timer <= 0:
            self.reach_timer = rng.uniform(3, 8)
            a = rng.choice(self.arms)
            a.reach_target = 0.0 if a.reach_target > 0 else rng.uniform(0.6, 1.0)
        for a in self.arms:
            a.reach += (a.reach_target - a.reach) * min(1.0, dt * 0.5)
            if a.reach > 0.9 * a.reach_target and a.reach_target > 0 and rng.random() < dt * 0.15:
                a.reach_target = 0.0
        # chromatophore flashes
        self.next_flash -= dt
        if self.next_flash <= 0:
            self.next_flash = rng.uniform(5, 12)
            self.flash_t = 1.0
            self.ripple_dir = rng.choice((-1, 1))
        self.flash_t = max(0.0, self.flash_t - dt * 0.5)
        # ink
        for p in self.puffs:
            p.age += dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vx *= 0.9 ** (dt * 30)
            p.vy *= 0.9 ** (dt * 30)
            p.vy += 0.05 * dt
            p.r += dt * (3.0 / (1 + p.age))
        self.puffs = [p for p in self.puffs if p.age < 9]
        if self.state == "jet" and self.jet < 1 and rng.random() < dt * 25:
            self.spawn_ink(0.6)
        for m in self.motes:
            m[1] += dt * 0.12 * m[2]
            m[0] += dt * 0.2 * math.sin(t * 0.3 + m[3])
            if m[1] > self.ground:
                m[1] = 0
                m[0] = rng.uniform(0, w)
        self.build_arms()

    def start_jet(self):
        rng = self.rng
        self.state = "jet"
        self.timer = 2.5
        self.jet = 0.0
        side = rng.choice((-1, 1)) if self.w * 0.25 < self.x < self.w * 0.75 else (1 if self.x < self.w / 2 else -1)
        sp = rng.uniform(26, 34) * (self.R / 9) ** 0.4
        ang = rng.uniform(0.7, 1.15)
        self.vx = side * sp * math.cos(ang)
        self.vy = -sp * math.sin(ang) / ASPECT
        self.flash_t = 1.0
        for _ in range(16):
            self.spawn_ink(1.0)

    def spawn_ink(self, k):
        rng = self.rng
        sx, sy = self.siphon()
        a = math.atan2(-self.vy * ASPECT, -self.vx) + rng.uniform(-0.6, 0.6)
        sp = rng.uniform(1, 6) * k
        self.puffs.append(Puff(sx + rng.uniform(-1, 1), sy + rng.uniform(-0.5, 0.5), math.cos(a) * sp,
                               math.sin(a) * sp / ASPECT, self.R * rng.uniform(0.4, 0.8) * k))

    # ------------------------------------------------------------------ geometry
    def frame(self):
        """Body balls in aspect units: crown, head, mantle, mantle tip."""
        R = self.R
        cx, cy = self.x, self.y * ASPECT
        ax, ay = math.cos(self.axis), math.sin(self.axis)
        breath = 1 + 0.06 * math.sin(self.t * 1.1) * (1 - self.jet) + 0.05 * self.jet
        stretch = 1 + 0.35 * self.jet
        balls = [
            (cx, cy, R * 0.5),
            (cx + ax * R * 0.55, cy + ay * R * 0.55, R * 0.7),
            (cx + ax * R * (1.5 * stretch), cy + ay * R * 1.5 * stretch, R * 1.35 * breath),
            (cx + ax * R * (1.6 + 0.45 * self.elong) * stretch - ay * R * 0.9 * self.side,
             cy + ay * R * (1.6 + 0.45 * self.elong) * stretch + ax * R * 0.9 * self.side, R * 1.15 * breath),
        ]
        return balls

    def siphon(self):
        R = self.R
        ax, ay = math.cos(self.axis), math.sin(self.axis)
        px, py = -ay, ax
        side = 1 if self.tilt > 0 else -1
        x = self.x + ax * R * 0.5 + px * R * 0.75 * side
        y = self.y * ASPECT + ay * R * 0.5 + py * R * 0.75 * side
        return x, y / ASPECT

    def build_arms(self):
        t = self.t
        R = self.R
        cx, cy = self.x, self.y * ASPECT
        gy = self.ground * ASPECT
        hc = gy - cy                             # crown height above the sand
        persp = self.persp
        j = self.jet
        nseg = 24
        trail = self.axis + math.pi
        for a in self.arms:
            L = self.arm_len * a.len * (1 + 0.2 * a.reach)
            seg = L / nseg
            reach = a.reach * (1 - j)
            # --- rest pose: a curvy path on the seabed plane, seen in perspective; tip curls up in view
            X, Z = math.cos(a.phi) * R * 0.45, math.sin(a.phi) * R * 0.45
            psi = a.phi
            rest = [(cx + X, gy - Z * persp - hc)]
            sx, sy = rest[0]
            curl_from = 0.62 + 0.1 * a.len
            ang = None
            for i in range(nseg):
                s = (i + 1) / nseg
                wv = a.wave * math.sin(t * a.speed * 3 + a.phase - s * 4)
                if s < curl_from:
                    psi += (a.bend + wv) * 1.6 / nseg
                    X += math.cos(psi) * seg
                    Z += math.sin(psi) * seg
                    hgt = hc * (1 - smoothstep(0.0, 0.32, s)) + a.arch * R * math.sin(math.pi * min(1.0, s / 0.5))
                    hgt += reach * R * 3.0 * smoothstep(0.1, 1.0, s)
                    nx, ny = cx + X, gy - Z * persp - hgt
                    if ang is None or s < curl_from:
                        ang = math.atan2(ny - sy, nx - sx)
                else:
                    # the free tip rolls up into a spiral, in the picture plane
                    ang += a.curl * (1 - 0.7 * reach) * ((s - curl_from) / (1 - curl_from)) ** 1.2 * 7.0 / nseg
                    ang += wv * 0.5 / nseg
                    nx, ny = sx + math.cos(ang) * seg, sy + math.sin(ang) * seg
                rest.append((nx, ny))
                sx, sy = nx, ny
            if j > 0.01:
                # --- jet pose: trailing in a tight bundle behind the mantle
                b = trail + a.jspread
                x, y = rest[0]
                jp = [(x, y)]
                for i in range(nseg):
                    s = (i + 1) / nseg
                    b2 = b + 0.25 * math.sin(t * 4 + a.phase - s * 6) * s
                    x += math.cos(b2) * seg * 1.05
                    y += math.sin(b2) * seg * 1.05
                    jp.append((x, y))
                k = smoothstep(0.0, 1.0, j)
                rest = [(p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k) for p, q in zip(rest, jp)]
            a.pts = rest
            a.depth = math.sin(a.phi) * (1 - j)
            w0 = R * 0.36 * (1 - 0.12 * a.depth)
            a.widths = [w0 * (1 - 0.9 * (i / nseg) ** 0.75) + 0.3 for i in range(nseg + 1)]

    # ------------------------------------------------------------------ drawing
    def draw(self, cv):
        self.draw_water(cv)
        self.draw_seabed(cv)
        arms = sorted(self.arms, key=lambda a: -a.depth)
        for a in arms:
            if a.depth > 0.05:
                self.draw_arm(cv, a, far=True)
        self.draw_body(cv)
        for a in arms:
            if a.depth <= 0.05:
                self.draw_arm(cv, a, far=False)
        self.draw_eyes(cv)
        self.draw_ink(cv)

    def draw_water(self, cv):
        t = self.t
        w, h = self.w, self.h
        g = self.ground
        for x in range(0, w):
            ray = math.sin(x * 0.09 + t * 0.1) + 0.6 * math.sin(x * 0.23 - t * 0.17)
            if ray > 0.7:
                for y in range(0, int(g * 0.8), 1):
                    v = (ray - 0.7) * 0.25 * (1 - y / (g * 0.8))
                    xx = x + y * 0.35
                    cv.shade(xx, y, v, (70, 130, 190))
        for x, y, z, _ in self.motes:
            cv.shade(x, y, 0.07 + 0.12 * z, (110, 150, 180))

    def draw_seabed(self, cv):
        t = self.t
        for wx, wl, ph, col in self.weeds:     # kelp strands swaying
            n = int(wl)
            px = wx
            for i in range(n):
                s = i / max(1, n)
                x = wx + math.sin(t * 0.8 + ph + s * 3) * s * 3
                y = self.ground - i
                ch = "(" if x < px - 0.15 else ")" if x > px + 0.15 else "|"
                if i % 4 == 2:
                    ch = "}" if math.sin(ph + i) > 0 else "{"
                cv.put(x, y, ch, scale(col, 0.45 + 0.4 * (1 - s)), 0.5)
                px = x
        for rx, rr, hh, sd in self.rocks:
            for y in range(int(self.ground - rr * hh / ASPECT * 2) - 1, int(self.ground) + 1):
                for x in range(int(rx - rr), int(rx + rr) + 1):
                    dx = (x + 0.5 - rx) / rr
                    dy = (self.ground - (y + 0.5)) * ASPECT / (rr * hh * 2)
                    if dy < 0:
                        continue
                    edge = 1 - dx * dx - dy * dy + 0.15 * noise2(x * 0.3, y * 0.6, sd)
                    if edge > 0:
                        v = 0.12 + 0.22 * (1 - dy) * (0.6 - 0.4 * dx) + 0.12 * noise2(x * 0.7, y, sd + 1)
                        cv.shade(x, y, clamp(v, 0.06, 0.45), (85, 95, 115) if sd % 2 else (105, 92, 88), "over")
        for x, y, v, col, ch in self.sand:
            if ch:
                cv.put(x, y, ch, scale(col, 0.15 + v), v)
            else:
                cv.shade(x, y, v, col)
        for sx, ch, col in self.shells:
            cv.put(sx, self.ground - 0.3, ch, col, 0.6)

    def skin_color(self, u, v, base, extra=0.0):
        """Chromatophore colour at skin coords (u along the body, v across); base = lighting 0..1."""
        t = self.t
        sd = self.seed
        spot = noise2(u * 2.2, v * 2.2, sd)
        rip = math.sin(u * self.ripple_k * 6 - t * self.ripple_speed * self.ripple_dir * 2 + v * 0.8)
        dark = 0.0
        if spot > 1 - self.spots * 1.3:
            dark += 0.35
        if self.stripes and math.sin(u * 3.5 + v * 0.5) > 0.6:
            dark += 0.3
        dark += 0.22 * (rip if rip > 0 else 0) + 0.1 * extra
        lum = clamp(base * (1 - dark * 0.6))
        col = gradient(self.skin, lum ** 0.8)
        if self.flash_t > 0:
            band = math.sin(u * 2 - self.flash_t * 12)
            if band > 0.4:
                col = mix(col, self.flash, (band - 0.4) * self.flash_t)
        return col, lum

    def draw_body(self, cv):
        balls = self.frame()
        R = self.R
        w, h = cv.w, cv.h
        x0 = int(min(b[0] - b[2] * 1.6 for b in balls) - 1)
        x1 = int(max(b[0] + b[2] * 1.6 for b in balls) + 2)
        y0 = int(min(b[1] - b[2] * 1.6 for b in balls) / ASPECT - 1)
        y1 = int(max(b[1] + b[2] * 1.6 for b in balls) / ASPECT + 2)
        cx, cy = self.x, self.y * ASPECT
        ax, ay = math.cos(self.axis), math.sin(self.axis)
        lx, ly, lz = -0.45, -0.75, 0.5
        ln = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / ln, ly / ln, lz / ln
        sd = self.seed
        shade = cv.shade
        put = cv.put
        rim_col = self.skin[-1]
        sqrt = math.sqrt
        for y in range(max(0, y0), min(h, y1)):
            py = (y + 0.5) * ASPECT
            for x in range(max(0, x0), min(w, x1)):
                px = x + 0.5
                f = 0.0
                gx = gy = 0.0
                for bx, by, br in balls:
                    dx = px - bx
                    dy = py - by
                    q = (dx * dx + dy * dy) / (br * br * 2.56)
                    if q >= 1.0:
                        continue
                    k = 1 - q
                    f += k * k
                    g = 4 * k / (br * br * 2.56)
                    gx += g * dx
                    gy += g * dy
                if f < 0.3:
                    continue
                if f < 0.371:       # soft glow just outside the skin
                    shade(x, y, (f - 0.3) * 4.5, self.skin[1])
                    continue
                hgt = sqrt(min(1.0, (f - 0.371) / 0.5))
                gl = sqrt(gx * gx + gy * gy) + 1e-9
                s2 = sqrt(max(0.0, 1 - hgt * hgt))
                nx, ny, nz = gx / gl * s2, gy / gl * s2, hgt
                dif = nx * lx + ny * ly + nz * lz
                dif = dif if dif > 0 else 0.0
                spec = (nx * 0.3 + ny * -0.5 + nz * 0.8)
                spec = spec ** 30 if spec > 0 else 0.0
                # skin coordinates: u along the body axis, v across it
                rx, ry = px - cx, py - cy
                u = (rx * ax + ry * ay) / R
                vv = (-rx * ay + ry * ax) / R
                base = 0.18 + 0.75 * dif + 0.25 * (1 - hgt) ** 2
                col, lum = self.skin_color(u, vv, base)
                # papillae: little bumps on the mantle
                hsh = (x * 73856093 ^ int(u * 6) * 19349663 ^ sd) % 41
                if u > 1.0 and hsh < 2 and hgt > 0.35:
                    put(x, y, "°" if hsh else "o", mix(col, rim_col, 0.5), 0.9)
                    continue
                if spec > 0.03:
                    col = mix(col, (255, 250, 245), clamp(spec))
                shade(x, y, clamp(0.45 + 0.55 * lum + spec * 0.4), col, "over")

    def draw_arm(self, cv, a, far):
        cells = {}
        stroke(cells, cv.w, cv.h, a.pts, a.widths)
        dim = 0.75 if far else 1.0
        put, shade = cv.put, cv.shade
        w = cv.w
        sucker = self.sucker
        side_s = -1 if a.curl > 0 else 1         # suckers on the inside of the curl
        for key, (dn, s, side) in cells.items():
            y, x = divmod(key, w)
            nz = math.sqrt(max(0.0, 1 - dn * dn))
            light = 0.3 + 0.6 * nz - 0.15 * side * side_s
            col, lum = self.skin_color(s * 6 + 2, side * 0.5, clamp(light) * (1 - 0.25 * s))
            if side * side_s > 0.45 and dn > 0.45:
                # sucker row along the underside
                ph = s * self.arm_len * a.len * 0.55
                if math.sin(ph * 2.2) > -0.2 and s > 0.04:
                    ch = "o" if s < 0.45 else "°" if s < 0.8 else "."
                    put(x, y, ch, scale(mix(sucker, col, 0.3), dim * (0.7 + 0.3 * (1 - s))), 0.8)
                    continue
            shade(x, y, clamp((0.45 + 0.55 * lum) * dim), col, "over")

    def draw_eyes(self, cv):
        R = self.R
        ax, ay = math.cos(self.axis), math.sin(self.axis)
        px, py = -ay, ax
        hx = self.x + ax * R * 0.62
        hy = self.y * ASPECT + ay * R * 0.62
        gold = (255, 205, 90)
        blink = (self.t * 0.23) % 1 < 0.03
        for side in (-1, 1):
            ex = hx + px * R * 0.48 * side
            ey = (hy + py * R * 0.48 * side) / ASPECT
            if blink:
                cv.text(int(ex) - 1, ey, "---", scale(self.skin[1], 0.8))
                continue
            cv.put(ex - 1, ey, "(", mix(gold, self.skin[2], 0.4), 1)
            cv.put(ex, ey, "=" if self.state == "rest" else "o", (40, 20, 10) if self.state == "rest" else (20, 10, 5), 1)
            cv.put(ex, ey, "-", (30, 15, 5), 1)
            cv.put(ex + 1, ey, ")", mix(gold, self.skin[2], 0.4), 1)
            cv.put(ex, ey - 1, "_", scale(gold, 0.7), 1)

    def draw_ink(self, cv):
        for p in self.puffs:
            life = clamp(1 - p.age / 9)
            r = p.r
            x0, x1 = int(p.x - r - 1), int(p.x + r + 2)
            y0, y1 = int(p.y - r / ASPECT - 1), int(p.y + r / ASPECT + 2)
            for y in range(max(0, y0), min(cv.h, y1)):
                for x in range(max(0, x0), min(cv.w, x1)):
                    dx = (x + 0.5 - p.x) / r
                    dy = (y + 0.5 - p.y) * ASPECT / r
                    d = dx * dx + dy * dy
                    if d > 1:
                        continue
                    n = noise2(x * 0.4 + p.seed, y * 0.8 + p.age * 0.5, 7) * 0.5 + 0.5
                    v = (1 - d) * (0.45 + 0.5 * n) * life
                    if v < 0.08:
                        continue
                    i = y * cv.w + x
                    if v * 1.4 > cv.lv[i] or v > 0.3:
                        cv.shade(x, y, clamp(v * 1.15), mix((70, 55, 110), (150, 130, 190), n * n), "over")
