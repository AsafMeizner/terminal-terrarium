"""A spinning, shaded 3D donut (pink frosting, sprinkles, golden dough) - or a sphere or a cube."""
import math

from ..engine import ASPECT, Scene, clamp, mix

# frosting: (base, highlight, halo glow)
FROSTINGS = {
    "strawberry": ((255, 105, 175), (255, 215, 235), (255, 110, 180)),
    "chocolate": ((150, 78, 48), (240, 190, 160), (200, 120, 80)),
    "mint": ((90, 230, 170), (215, 255, 235), (90, 230, 170)),
    "lavender": ((175, 130, 255), (232, 218, 255), (170, 130, 255)),
    "lemon": ((255, 215, 70), (255, 250, 205), (255, 210, 90)),
    "blueberry": ((90, 150, 255), (205, 225, 255), (100, 150, 255)),
    "vanilla": ((245, 232, 212), (255, 255, 255), (230, 210, 190)),
}
SPRINKLES = {
    "rainbow": [(255, 245, 120), (120, 230, 255), (255, 255, 255), (150, 255, 140),
                (255, 150, 60), (190, 140, 255), (255, 90, 120)],
    "pastel": [(255, 200, 220), (200, 230, 255), (210, 255, 210), (255, 245, 200), (230, 210, 255)],
    "neon": [(255, 60, 200), (60, 255, 120), (60, 200, 255), (255, 240, 60)],
    "chocolate": [(110, 60, 40), (255, 250, 240), (190, 130, 90)],
    "gold": [(255, 215, 90), (255, 240, 170), (240, 175, 60), (255, 255, 230)],
}
# dough: (lit, shadow, pale ring under the frosting)
DOUGHS = {
    "golden": ((235, 160, 70), (150, 70, 25), (255, 215, 150)),
    "baked": ((205, 120, 50), (105, 48, 20), (240, 180, 120)),
    "pale": ((245, 200, 130), (170, 115, 60), (255, 238, 195)),
    "cocoa": ((140, 78, 45), (65, 32, 16), (200, 135, 95)),
}
# gas-giant band sets for the sphere
BANDS = [
    [(40, 60, 140), (90, 170, 255), (230, 240, 255), (255, 170, 110), (240, 90, 150),
     (120, 80, 210), (90, 220, 230), (255, 220, 150)],
    [(120, 60, 30), (210, 140, 80), (250, 220, 170), (190, 100, 60), (240, 200, 140), (150, 80, 50)],
    [(30, 80, 160), (120, 210, 255), (230, 250, 255), (60, 140, 220), (170, 230, 255)],
    [(255, 120, 170), (255, 210, 140), (140, 240, 210), (170, 150, 255), (255, 245, 220)],
    [(60, 30, 110), (200, 60, 160), (255, 140, 90), (255, 220, 120), (120, 50, 160)],
]
# cube face colors
FACES = [
    [(255, 90, 160), (90, 200, 255), (255, 190, 90), (150, 110, 255), (90, 255, 180), (255, 120, 90)],
    [(80, 220, 255), (60, 140, 255), (140, 255, 230), (90, 100, 230), (180, 240, 255), (50, 190, 210)],
    [(255, 120, 80), (255, 200, 90), (255, 80, 140), (255, 160, 60), (255, 230, 150), (220, 70, 90)],
    [(170, 110, 255), (255, 110, 200), (110, 140, 255), (255, 160, 230), (140, 90, 220), (210, 160, 255)],
]


def _q(c):
    r, g, b = c
    r = 0 if r < 0 else 252 if r > 252 else int(r) & ~3
    g = 0 if g < 0 else 252 if g > 252 else int(g) & ~3
    b = 0 if b < 0 else 252 if b > 252 else int(b) & ~3
    return (r, g, b)


def _rot(ax, ay, az):
    """Rotation matrix Rz(az) * Rx(ax) * Ry(ay) as nested lists (rows)."""
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]

    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    return mul(rz, mul(rx, ry))


def _norm(v):
    d = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / d, v[1] / d, v[2] / d)


LIGHT = _norm((-0.55, 0.75, -0.65))           # world space, y up, camera looks along +z
HALF = _norm((LIGHT[0], LIGHT[1], LIGHT[2] - 1.0))
FILL = _norm((0.5, -0.7, -0.45))               # warm bounce light from below-right


class Donut(Scene):
    name = "donut"
    title = "Donut"
    blurb = "a spinning 3D donut with frosting, sprinkles and golden dough (or a planet, or a cube)"
    tags = ("3d", "retro", "fun")
    options = {
        "shape": ("random", "donut, sphere, cube or random (mostly donuts)"),
        "frosting": ("random", "strawberry, chocolate, mint, lavender, lemon, blueberry, vanilla or random"),
        "spin": (1.0, "rotation speed"),
        "sprinkles": (True, "sprinkles on the frosting"),
    }

    def _choose_style(self):
        """Roll this run's look once; explicit -o options win."""
        rng = self.rng
        st = {}
        shape = self.opt("shape")
        if shape not in ("donut", "sphere", "cube"):
            shape = rng.choices(("donut", "sphere", "cube"), (0.6, 0.2, 0.2))[0]
        st["shape"] = shape
        fr = self.opt("frosting")
        if fr not in FROSTINGS:
            fr = rng.choice(("strawberry", "strawberry", "chocolate", "mint", "lavender", "lemon",
                             "blueberry", "vanilla"))
        st["frosting"] = fr
        sp = rng.choice(list(SPRINKLES))
        if fr == "chocolate" and sp == "chocolate":
            sp = "rainbow"
        st["sprinkles"] = sp
        st["dough"] = rng.choice(("golden", "golden", "baked", "pale", "cocoa"))
        st["bands"] = rng.randrange(len(BANDS))
        st["faces"] = rng.randrange(len(FACES))
        # spin: rates and directions per axis, and how far the donut leans toward us
        st["rates"] = tuple(rng.uniform(0.6, 1.4) * rng.choice((-1, 1)) for _ in range(3))
        st["tilt"] = rng.uniform(-1.0, -0.45)
        st["wobble"] = rng.uniform(0.5, 1.0)
        st["axis"] = rng.uniform(-0.6, 0.6)
        st["phase"] = tuple(rng.uniform(0, math.tau) for _ in range(3))
        self.style = st

    R = 1.0      # torus major radius
    r = 0.46     # torus minor radius
    K = 5.0      # camera distance

    def setup(self):
        w, h = self.w, self.h
        if not hasattr(self, "style"):
            self._choose_style()
        st = self.style
        self.shape = st["shape"]
        self.FROST, self.FROST_HI, self.GLOW = FROSTINGS[st["frosting"]]
        self.SPRINKLE_COLORS = SPRINKLES[st["sprinkles"]]
        self.DOUGH, self.DOUGH_DARK, self.DOUGH_EDGE = DOUGHS[st["dough"]]
        self.bands = BANDS[st["bands"]]
        self.faces = FACES[st["faces"]]
        extent = {"donut": self.R + self.r, "sphere": 1.0, "cube": 1.5}[self.shape]
        # screen radius (x cells) the object should fill
        target = min(w * 0.42, h * ASPECT * 0.44)
        self.f = target * (self.K - extent * 0.6) / extent   # focal length in x cells
        self.ax, self.ay, self.az = st["phase"]
        if self.shape == "donut":
            self._build_torus(target)
        rng = self.rng
        self.stars = [(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0, 6.28), rng.uniform(0.5, 1.5))
                      for _ in range(int(w * h / 140 * self.density))]

    # ------------------------------------------------------------------ torus
    def _build_torus(self, target):
        R, r = self.R, self.r
        spx = target / (R + r)                    # cells per object unit (roughly)
        nphi = max(60, min(420, int(math.tau * (R + r) * spx * 1.05)))
        nth = max(24, min(160, int(math.tau * r * spx * 1.15)))
        self.nphi, self.nth = nphi, nth
        self.th = [(math.cos(i * math.tau / nth), math.sin(i * math.tau / nth)) for i in range(nth)]
        self.th_c = [(R + r * c, r * s) for c, s in self.th]
        self.phi = [(math.cos(j * math.tau / nphi), math.sin(j * math.tau / nphi)) for j in range(nphi)]
        # material map in (theta, phi): 0 dough, 1 frosting, 2.. sprinkle colors
        rng = self.rng
        mat = [0] * (nth * nphi)
        edge = [0.0] * (nth * nphi)
        drip_seed = [rng.uniform(0, 6.28) for _ in range(3)]
        for j in range(nphi):
            p = j * math.tau / nphi
            # wavy frosting edge with a few drips on the outside
            wave = 0.18 * math.sin(p * 5 + drip_seed[0]) + 0.10 * math.sin(p * 11 + drip_seed[1])
            drip = max(0.0, math.sin(p * 7 + drip_seed[2])) ** 6 * 0.55
            for i in range(nth):
                c, s = self.th[i]
                # height around the tube: s > 0 is the top; outside (c > 0) drips further down
                lim = 0.02 - wave - (drip if c > 0 else 0.0)
                k = i * nphi + j
                if s > lim:
                    mat[k] = 1
                    edge[k] = clamp((s - lim) / 0.25)
                else:
                    edge[k] = -clamp((lim - s) / 0.25)
        if self.opt("sprinkles"):
            # sprinkles: short streaks laid at random angles on the frosting
            n = int(nphi * nth / 30)
            for _ in range(n):
                i0 = rng.randrange(nth)
                j0 = rng.randrange(nphi)
                if mat[i0 * nphi + j0] != 1 or self.th[i0][1] < -0.3:
                    continue
                col = 2 + rng.randrange(len(self.SPRINKLE_COLORS))
                ang = rng.uniform(0, math.pi)
                di, dj = math.sin(ang), math.cos(ang) * 1.6
                ln = rng.randint(3, 5)
                for s in range(ln):
                    ii = int(i0 + di * s) % nth
                    jj = int(j0 + dj * s) % nphi
                    for (a, b) in ((ii, jj), ((ii + 1) % nth, jj)):
                        if mat[a * nphi + b] == 1:
                            mat[a * nphi + b] = col
        self.mat = mat
        self.edge = edge

    def update(self, dt):
        super().update(dt)
        sp = self.opt("spin")
        ra, rb, rc = self.style["rates"]
        self.ax += dt * 0.55 * sp * ra
        self.az += dt * 0.31 * sp * rc
        self.ay += dt * 0.42 * sp * rb

    def _matrix(self):
        if self.shape == "donut":
            # tumble, but keep the frosting facing us more often than not
            st = self.style
            ax = st["tilt"] + 0.85 * st["wobble"] * math.sin(self.ax) + 0.3 * math.sin(self.ax * 0.37)
            return _rot(ax, self.ay * 1.3, 0.55 * math.sin(self.az))
        if self.shape == "sphere":
            return _rot(-0.35 + 0.15 * math.sin(self.ax * 0.5), self.ay * 1.2, self.style["axis"])
        return _rot(self.ax, self.ay, self.az)

    def draw(self, cv):
        self.draw_backdrop(cv)
        if self.shape == "donut":
            self.draw_torus(cv)
        elif self.shape == "sphere":
            self.draw_sphere(cv)
        else:
            self.draw_cube(cv)

    def draw_backdrop(self, cv):
        t = self.t
        for x, y, ph, sp in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * sp + ph)
            cv.shade(x, y, 0.06 + 0.12 * tw * tw, (170, 150, 220))

    # ------------------------------------------------------------------ torus
    def draw_torus(self, cv):
        W, H = cv.w, cv.h
        M = self._matrix()
        K = self.K
        f = self.f
        fy = f / ASPECT
        cxs, cys = W / 2.0, H / 2.0
        zbuf = [0.0] * (W * H)
        ibuf = [0] * (W * H)
        nth, nphi = self.nth, self.nphi
        thc = self.th_c
        th = self.th
        ex, ey, ez = M[0][1], M[1][1], M[2][1]
        for j, (cp, sp) in enumerate(self.phi):
            ux = M[0][0] * cp + M[0][2] * sp
            uy = M[1][0] * cp + M[1][2] * sp
            uz = M[2][0] * cp + M[2][2] * sp
            for i in range(nth):
                c, s = th[i]
                if c * uz + s * ez > 0.12:          # facing away: never visible
                    continue
                a, b = thc[i]
                z = a * uz + b * ez + K
                ooz = 1.0 / z
                px = int(cxs + (a * ux + b * ex) * f * ooz)
                py = int(cys - (a * uy + b * ey) * fy * ooz)
                if 0 <= px < W and 0 <= py < H:
                    k = py * W + px
                    if ooz > zbuf[k]:
                        zbuf[k] = ooz
                        ibuf[k] = i * nphi + j
        # shade the winning samples
        ramp = cv.ramp
        nr = len(ramp) - 1
        mat, edge = self.mat, self.edge
        FROST, FROST_HI, SPRINK = self.FROST, self.FROST_HI, self.SPRINKLE_COLORS
        DOUGH, DOUGH_DARK, DOUGH_EDGE = self.DOUGH, self.DOUGH_DARK, self.DOUGH_EDGE
        phi = self.phi
        L, Hh = LIGHT, HALF
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        filled = []
        for k in range(W * H):
            if zbuf[k] == 0.0:
                continue
            idx = ibuf[k]
            i, j = divmod(idx, nphi)
            c, s = th[i]
            cp, sp = phi[j]
            ux = M[0][0] * cp + M[0][2] * sp
            uy = M[1][0] * cp + M[1][2] * sp
            uz = M[2][0] * cp + M[2][2] * sp
            nx, ny, nz = c * ux + s * ex, c * uy + s * ey, c * uz + s * ez
            diff = nx * L[0] + ny * L[1] + nz * L[2]
            if diff < 0:
                diff = 0.0
            fill = nx * FILL[0] + ny * FILL[1] + nz * FILL[2]
            if fill > 0:
                diff += fill * 0.4
            nh = nx * Hh[0] + ny * Hh[1] + nz * Hh[2]
            rim = clamp(1.0 + nz * 1.6) ** 2          # light wrapping the silhouette
            m = mat[idx]
            if m == 1:
                spec = nh ** 28 if nh > 0 else 0.0
                base = mix(FROST, FROST_HI, clamp(diff * 0.35 + spec))
                v = 0.12 + 0.62 * diff + 0.45 * spec + 0.12 * rim
                col = mix(base, (255, 255, 255), clamp(spec * 1.2))
            elif m >= 2:
                spec = nh ** 12 if nh > 0 else 0.0
                base = SPRINK[m - 2]
                v = 0.55 + 0.45 * diff + 0.3 * spec
                col = mix(base, (255, 255, 255), clamp(spec))
            else:
                spec = nh ** 8 * 0.25 if nh > 0 else 0.0
                e = edge[idx]
                base = mix(DOUGH_DARK, DOUGH, clamp(0.25 + diff * 1.2))
                if e > -0.6:                         # pale baked ring under the frosting
                    base = mix(base, DOUGH_EDGE, (e + 0.6) / 0.6 * 0.6)
                v = 0.16 + 0.66 * diff + spec + 0.1 * rim
                col = base
            col = mix(col, FROST_HI, 0.25 * rim * (1 - diff))
            v = clamp(v, 0.08, 1.0)
            gi = int(v * nr + 0.5)
            ch[k] = ramp[gi] if gi > 0 else ramp[1]
            kk = 0.35 + 0.65 * v
            fg[k] = _q((col[0] * kk, col[1] * kk, col[2] * kk))
            lv[k] = v
            filled.append(k)
        self._halo(cv, filled, zbuf, self.GLOW)

    def _halo(self, cv, filled, mask, color):
        """Faint glow in the empty cells right around the object."""
        W, H = cv.w, cv.h
        n = W * H
        glow = {}
        for k in filled:
            for d, g in ((-1, 0.2), (1, 0.2), (-W, 0.16), (W, 0.16), (-2, 0.1), (2, 0.1)):
                q = k + d
                if 0 <= q < n and not mask[q]:
                    if glow.get(q, 0) < g:
                        glow[q] = g
        for q, g in glow.items():
            y, x = divmod(q, W)
            cv.shade(x, y, g, color)

    # ------------------------------------------------------------------ sphere
    def draw_sphere(self, cv):
        W, H = cv.w, cv.h
        M = self._matrix()
        K = self.K
        f = self.f
        cxs, cys = W / 2.0, H / 2.0
        ramp = cv.ramp
        nr = len(ramp) - 1
        # orthographic-ish projection radius for the bounding box
        rad = f / math.sqrt(K * K - 1)
        x0, x1 = max(0, int(cxs - rad - 2)), min(W, int(cxs + rad + 3))
        y0, y1 = max(0, int(cys - rad / ASPECT - 2)), min(H, int(cys + rad / ASPECT + 3))
        L, Hh = LIGHT, HALF
        t = self.t
        mask = [0] * (W * H)
        filled = []
        bands = self.bands
        nb = len(bands)
        for py in range(y0, y1):
            dy = -(py + 0.5 - cys) * ASPECT / f
            for px in range(x0, x1):
                dx = (px + 0.5 - cxs) / f
                # ray from (0,0,-K) along (dx, dy, 1); sphere radius 1 at origin
                a = dx * dx + dy * dy + 1.0
                b = -2.0 * K
                c = K * K - 1.0
                disc = b * b - 4 * a * c
                if disc < 0:
                    continue
                tt = (-b - math.sqrt(disc)) / (2 * a)
                nx, ny, nz = dx * tt, dy * tt, -K + tt
                # object-space normal (transpose of M)
                ox = M[0][0] * nx + M[1][0] * ny + M[2][0] * nz
                oy = M[0][1] * nx + M[1][1] * ny + M[2][1] * nz
                oz = M[0][2] * nx + M[1][2] * ny + M[2][2] * nz
                lon = math.atan2(oz, ox)
                lat = oy + 0.06 * math.sin(lon * 3 + oy * 6 + t * 0.4) + 0.03 * math.sin(lon * 9 - t * 0.2)
                bandf = (lat * 3.2 + 4.0) % nb
                bi = int(bandf)
                fr = bandf - bi
                fr = fr * fr * (3 - 2 * fr)
                base = mix(bands[bi], bands[(bi + 1) % nb], fr)
                diff = max(0.0, nx * L[0] + ny * L[1] + nz * L[2])
                nh = nx * Hh[0] + ny * Hh[1] + nz * Hh[2]
                spec = nh ** 40 if nh > 0 else 0.0
                rim = clamp(1.0 + nz * 1.4) ** 2
                v = clamp(0.1 + 0.78 * diff + 0.6 * spec + 0.2 * rim, 0.08, 1.0)
                col = mix(base, (255, 255, 255), clamp(spec * 1.3))
                col = mix(col, (150, 200, 255), 0.4 * rim * (1 - diff))
                k = py * W + px
                gi = int(v * nr + 0.5)
                cv.ch[k] = ramp[gi] if gi > 0 else ramp[1]
                kk = 0.35 + 0.65 * v
                cv.fg[k] = _q((col[0] * kk, col[1] * kk, col[2] * kk))
                cv.lv[k] = v
                mask[k] = 1
                filled.append(k)
        self._halo(cv, filled, mask, self.bands[1])

    # ------------------------------------------------------------------ cube
    def draw_cube(self, cv):
        W, H = cv.w, cv.h
        M = self._matrix()
        K = self.K
        f = self.f
        cxs, cys = W / 2.0, H / 2.0
        ramp = cv.ramp
        nr = len(ramp) - 1
        rad = f * 1.75 / (K - 1.75)
        x0, x1 = max(0, int(cxs - rad - 1)), min(W, int(cxs + rad + 2))
        y0, y1 = max(0, int(cys - rad / ASPECT - 1)), min(H, int(cys + rad / ASPECT + 2))
        # camera in object space
        ocx, ocy, ocz = M[2][0] * -K, M[2][1] * -K, M[2][2] * -K
        L, Hh = LIGHT, HALF
        face_cols = self.faces
        mask = [0] * (W * H)
        filled = []
        hue_t = self.t * 0.1
        for py in range(y0, y1):
            dy = -(py + 0.5 - cys) * ASPECT / f
            for px in range(x0, x1):
                dx = (px + 0.5 - cxs) / f
                # ray direction in object space
                rx = M[0][0] * dx + M[1][0] * dy + M[2][0]
                ry = M[0][1] * dx + M[1][1] * dy + M[2][1]
                rz = M[0][2] * dx + M[1][2] * dy + M[2][2]
                tn, tf = -1e9, 1e9
                axis = 0
                sign = 1
                for ax_i, (o, d) in enumerate(((ocx, rx), (ocy, ry), (ocz, rz))):
                    if abs(d) < 1e-9:
                        if o < -1 or o > 1:
                            tn = 1e9
                            break
                        continue
                    t1 = (-1 - o) / d
                    t2 = (1 - o) / d
                    sg = -1
                    if t1 > t2:
                        t1, t2 = t2, t1
                        sg = 1
                    if t1 > tn:
                        tn = t1
                        axis = ax_i
                        sign = sg
                    if t2 < tf:
                        tf = t2
                if tn > tf or tn < 0:
                    continue
                hx, hy, hz = ocx + rx * tn, ocy + ry * tn, ocz + rz * tn
                # face coordinates for edge glow
                if axis == 0:
                    u, w2 = hy, hz
                elif axis == 1:
                    u, w2 = hx, hz
                else:
                    u, w2 = hx, hy
                edge = max(abs(u), abs(w2))
                inner = min(abs(u), abs(w2))
                # object normal -> world normal
                on = [0.0, 0.0, 0.0]
                on[axis] = float(sign)
                nx = M[0][0] * on[0] + M[0][1] * on[1] + M[0][2] * on[2]
                ny = M[1][0] * on[0] + M[1][1] * on[1] + M[1][2] * on[2]
                nz = M[2][0] * on[0] + M[2][1] * on[1] + M[2][2] * on[2]
                diff = max(0.0, nx * L[0] + ny * L[1] + nz * L[2])
                nh = nx * Hh[0] + ny * Hh[1] + nz * Hh[2]
                spec = nh ** 30 if nh > 0 else 0.0
                fi = axis * 2 + (sign > 0)
                base = face_cols[fi]
                # soft diagonal sheen across each face
                sheen = 0.5 + 0.5 * math.sin((u + w2) * 2.2 + hue_t * 6)
                base = mix(base, face_cols[(fi + 1) % 6], 0.3 * sheen)
                v = 0.16 + 0.5 * diff + 0.45 * spec + 0.1 * sheen
                col = mix(base, (255, 255, 255), clamp(spec))
                e = clamp((edge - 0.88) / 0.1)
                if e > 0:
                    v = max(v, 0.75 + 0.25 * e)
                    col = mix(col, (255, 245, 255), 0.75 * e)
                # faint inner frame like a glass tile
                fr = clamp(1 - abs(edge - 0.72) / 0.04) * 0.3
                if fr > 0:
                    v = max(v, v + fr * 0.5)
                    col = mix(col, (255, 255, 255), fr)
                v = clamp(v, 0.08, 1.0)
                k = py * W + px
                gi = int(v * nr + 0.5)
                cv.ch[k] = ramp[gi] if gi > 0 else ramp[1]
                kk = 0.35 + 0.65 * v
                cv.fg[k] = _q((col[0] * kk, col[1] * kk, col[2] * kk))
                cv.lv[k] = v
                mask[k] = 1
                filled.append(k)
        self._halo(cv, filled, mask, self.faces[3])
