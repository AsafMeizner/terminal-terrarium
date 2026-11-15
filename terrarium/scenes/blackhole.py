"""A black hole: lensed accretion disk, photon ring, Doppler beaming and optional jets.

The lensing is real (if coarse): photon orbits around a Schwarzschild hole are integrated once
per process for a table of impact parameters, then every screen cell looks up where its ray
crosses the disk plane (front of the disk, the far side bent over the top, its underside below).
"""
import bisect
import math

from ..engine import ASPECT, RAMPS, Scene, clamp, gradient, mix

TAU = math.tau
B_CRIT = 1.5 * math.sqrt(3.0)   # shadow radius in Schwarzschild radii
NA = 128                        # disk texture: azimuth bins
NRT = 40                        # disk texture: radius bins
GLOW = " .:-=+*#%@"
BEAM = " .':;!|lI#"   # vertical grain for the jets

# temperature gradients, hottest first
PALETTES = {
    "gold": [(255, 255, 245), (255, 236, 190), (255, 196, 110), (245, 140, 50), (190, 70, 25), (90, 25, 10)],
    "ice": [(250, 252, 255), (200, 230, 255), (120, 180, 255), (80, 110, 240), (90, 60, 200), (45, 25, 110)],
    "ember": [(255, 245, 200), (255, 205, 90), (255, 130, 40), (225, 60, 30), (150, 25, 35), (70, 10, 25)],
    "eht": [(255, 240, 200), (255, 200, 120), (250, 150, 60), (210, 95, 35), (140, 50, 20), (60, 20, 10)],
    "violet": [(255, 245, 255), (240, 190, 255), (210, 120, 255), (150, 80, 240), (100, 50, 190), (45, 20, 100)],
}

_TABLE = {}


def _trace(b):
    """Integrate u'' = -u + 1.5 u^2 (rs = 1) from infinity. Returns (step, us, phi_end, escaped)."""
    h = 0.02 * min(1.0, max(0.05, b))
    u, w = 0.0, 1.0 / b
    us = [0.0]
    phi = 0.0
    lim = 5 * math.pi
    while phi < lim:
        k1u, k1w = w, -u + 1.5 * u * u
        u2 = u + 0.5 * h * k1u
        k2u, k2w = w + 0.5 * h * k1w, -u2 + 1.5 * u2 * u2
        u3 = u + 0.5 * h * k2u
        k3u, k3w = w + 0.5 * h * k2w, -u3 + 1.5 * u3 * u3
        u4 = u + h * k3u
        k4u, k4w = w + h * k3w, -u4 + 1.5 * u4 * u4
        nu = u + h / 6 * (k1u + 2 * k2u + 2 * k3u + k4u)
        w += h / 6 * (k1w + 2 * k2w + 2 * k3w + k4w)
        if nu >= 1.0:
            us.append(1.0)
            return h, us, phi + h, False
        if nu <= 0.0 and phi > h:
            f = u / (u - nu) if u != nu else 0.0
            return h, us, phi + h * f, True
        u = nu
        phi += h
        us.append(u)
    return h, us, phi, False


def _table():
    if not _TABLE:
        bs = []
        b = 0.01
        while b < 6.0:
            bs.append(b)
            b += 0.025
        while b < 20.0:
            bs.append(b)
            b += 0.1
        while b <= 80.0:
            bs.append(b)
            b += 0.5
        _TABLE["bs"] = bs
        _TABLE["rows"] = [_trace(b) for b in bs]
    return _TABLE["bs"], _TABLE["rows"]


def _periodic(rng, nx, ny, lx, ly):
    """Tileable value noise on an nx x ny grid with an lx x ly lattice, values 0..1."""
    lat = [[rng.random() for _ in range(lx)] for _ in range(ly)]
    out = []
    for y in range(ny):
        fy = y * ly / ny
        y0 = int(fy)
        ty = fy - y0
        ty = ty * ty * (3 - 2 * ty)
        ra, rb = lat[y0 % ly], lat[(y0 + 1) % ly]
        row = []
        for x in range(nx):
            fx = x * lx / nx
            x0 = int(fx)
            tx = fx - x0
            tx = tx * tx * (3 - 2 * tx)
            a = ra[x0 % lx] + (ra[(x0 + 1) % lx] - ra[x0 % lx]) * tx
            c = rb[x0 % lx] + (rb[(x0 + 1) % lx] - rb[x0 % lx]) * tx
            row.append(a + (c - a) * ty)
        out.append(row)
    return out


def _q(r, g, b):
    return (0 if r < 0 else 252 if r > 252 else int(r) & ~3,
            0 if g < 0 else 252 if g > 252 else int(g) & ~3,
            0 if b < 0 else 252 if b > 252 else int(b) & ~3)


class BlackHole(Scene):
    name = "blackhole"
    title = "Black Hole"
    blurb = "a black hole bending light: lensed accretion disk, photon ring, Doppler glow and jets"
    tags = ("space", "science", "calm")
    options = {
        "tilt": (-1.0, "degrees the camera sits above the disk, 2-40 (-1 = random)"),
        "jets": ("random", "relativistic jets: on, off or random"),
        "palette": ("random", "random, gold, ice, ember, eht or violet"),
        "stars": (1.0, "amount of background stars"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        bs, rows = _table()
        # ---- genome
        tilt = self.opt("tilt")
        tilt = clamp(tilt, 2.0, 40.0) if tilt >= 0 else rng.choice((rng.uniform(3, 8), rng.uniform(5, 12),
                                                                     rng.uniform(10, 22)))
        inc = math.radians(90.0 - tilt)
        self.roll = math.radians(rng.uniform(-14, 14))
        self.spin = rng.choice((-1, 1))
        self.r_in = rng.uniform(2.6, 3.2)
        self.r_out = rng.uniform(9.0, 15.0)
        jets = str(self.opt("jets")).lower()
        self.jets = jets in ("on", "true", "yes", "1") or (jets not in ("off", "false", "no", "0")
                                                          and rng.random() < 0.4)
        pal = self.opt("palette")
        if pal not in PALETTES:
            pal = rng.choice(("gold", "gold", "gold", "ice", "ember", "eht", "violet"))
        self.pal_name = pal
        stops = PALETTES[pal]
        self.jet_col = rng.choice(((140, 180, 255), (170, 140, 255), (120, 230, 255)))
        if pal == "ice":
            self.jet_col = (200, 150, 255)
        self.dl = rng.uniform(25, 45)
        self.jet_open = rng.uniform(0.04, 0.09)                 # lens distance: how strongly stars are bent
        self.star_v = (rng.uniform(-0.6, 0.6), rng.uniform(-0.15, 0.15))
        self.rate = rng.uniform(5.0, 8.0)             # time scale of the orbits
        self.vin = rng.uniform(0.6, 1.4)              # infall drift of the texture (bins / s)
        twist = rng.uniform(4, 12) * self.spin
        # ---- disk texture: streaky in azimuth, ringed in radius, with spiral arms
        n1 = _periodic(rng, NA, NRT, rng.choice((10, 12, 16)), rng.choice((8, 10)))
        n2 = _periodic(rng, NA, NRT, rng.choice((32, 40, 48)), 20)
        ringf = rng.uniform(3, 7)
        self.tex = []
        for j in range(NRT):
            row = []
            gap = 0.75 + 0.25 * math.sin(j / NRT * TAU * ringf)
            for i in range(NA):
                k = int(i + twist * j / NRT * NA / TAU * 0.6) % NA
                v = n1[j][k] * 0.6 + n2[j][(k * 2) % NA] * 0.4
                v = clamp((v - 0.2) / 0.7) ** 1.6
                row.append((0.25 + 1.3 * v) * gap)
            self.tex.append(row)

        # ---- projection
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        self.cx, self.cy = cx, cy
        sc = min((w / 2.0) / (self.r_out * 0.92), (h / 2.0 * ASPECT) / (self.r_out * 0.5))
        self.sc = sc
        si, ci = math.sin(inc), math.cos(inc)
        cr, sr = math.cos(self.roll), math.sin(self.roll)
        lr_in, lr_out = math.log(self.r_in), math.log(self.r_out)
        rate = self.rate
        lut = [gradient(stops, k / 63) for k in range(64)]
        n = w * h
        self.ent = []        # (cell, ia0, omega bins/s, ir, intensity, color)
        self.sky = []        # (cell, sky x, sky y, weight)
        self.ring = [0.0] * n
        base = [0.0] * n
        basec = [None] * n
        shadow = [False] * n
        subs = (-0.25, 0.25)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                acc = {}
                sky_hits = []
                for sy in subs:
                    X0 = (x - cx) / sc
                    Y0 = -(y + sy - cy) * ASPECT / sc
                    X = X0 * cr + Y0 * sr
                    Y = -X0 * sr + Y0 * cr
                    b = math.hypot(X, Y)
                    if b < 1e-4:
                        b = 1e-4
                    al = math.atan2(Y, X)
                    ca, sa = math.cos(al), math.sin(al)
                    k = bisect.bisect_left(bs, b)
                    if k >= len(bs):
                        k = len(bs) - 1
                    elif k > 0 and b - bs[k - 1] < bs[k] - b:
                        k -= 1
                    hstep, us, phend, esc = rows[k]
                    nu = len(us) - 1
                    phi1 = math.atan2(-ci, sa * si) % math.pi
                    trans = 1.0
                    for kk in range(4):
                        pc = phi1 + kk * math.pi
                        if pc >= phend:
                            break
                        f = pc / hstep
                        j = int(f)
                        if j >= nu:
                            break
                        u = us[j] + (us[j + 1] - us[j]) * (f - j)
                        if u <= 0:
                            continue
                        r = 1.0 / u
                        if not (self.r_in <= r <= self.r_out):
                            continue
                        sp, cp = math.sin(pc), math.cos(pc)
                        px, py, pz = sp * ca, sp * sa, cp           # position (ex, ey, c)
                        qx, qy, qz = cp * ca, cp * sa, -sp          # d position / d phi
                        du = (us[j + 1] - us[j]) / hstep
                        tx, ty, tz = (-du * r * r) * px + r * qx, (-du * r * r) * py + r * qy, (-du * r * r) * pz + r * qz
                        tn = math.sqrt(tx * tx + ty * ty + tz * tz) or 1.0
                        kx, ky, kz = -tx / tn, -ty / tn, -tz / tn   # photon heads to the camera
                        vx, vy, vz = (si * pz - ci * py), ci * px, -si * px
                        vn = math.sqrt(vx * vx + vy * vy + vz * vz) or 1.0
                        beta = min(0.62, math.sqrt(0.5 / max(0.2, r - 1.0))) * 0.8
                        gam = 1.0 / math.sqrt(1.0 - beta * beta)
                        dop = 1.0 / (gam * (1.0 - beta * self.spin * (vx * kx + vy * ky + vz * kz) / vn))
                        g = dop * math.sqrt(max(0.05, 1.0 - 1.0 / r))
                        x_ = self.r_in / r
                        emit = x_ ** 1.7 * (1.0 - math.sqrt(x_) * 0.85) * 9.0
                        inten = emit * g ** 1.8 * trans * (1.0 if kk == 0 else 0.85)
                        temp = clamp((1.0 - (math.log(r) - lr_in) / (lr_out - lr_in)) * 0.75 + (g - 1.0) * 0.55
                                     + 0.1, 0.0, 1.0)
                        col = lut[int((1.0 - temp) * 63)]
                        psi = math.atan2(py * -ci + pz * si, px)    # azimuth in the disk plane
                        ir = int((math.log(r) - lr_in) / (lr_out - lr_in) * (NRT - 1))
                        om = math.sqrt(0.5 / (r * r * r)) * rate * NA / TAU * self.spin
                        ia0 = (psi % TAU) / TAU * NA
                        key = (ir, int(ia0) // 3)
                        if key in acc:
                            e = acc[key]
                            e[3] += inten * 0.5
                        else:
                            acc[key] = [ia0, om, ir, inten * 0.5, col]
                        trans *= 0.12
                    if not esc:
                        shadow[i] = shadow[i] or b < B_CRIT
                    elif trans > 0.05:
                        bet = b - self.dl * (phend - math.pi)
                        sx = bet * ca * sc
                        sy_ = bet * sa * sc / ASPECT
                        sky_hits.append((sx, sy_, trans * 0.5))
                    # photon ring: a razor-thin bright circle hugging the shadow
                    dr = (b - B_CRIT * 1.03) * sc / 0.8
                    if -4 < dr < 4:
                        side = 1.0 + 0.55 * self.spin * ca * si
                        self.ring[i] += (math.exp(-dr * dr) * 1.1 + math.exp(-dr * dr * 0.15) * 0.18) * side
                for e in acc.values():
                    self.ent.append((i, e[0], e[1], e[2], e[3], e[4]))
                    base[i] += e[3]
                    basec[i] = e[4] if basec[i] is None else mix(basec[i], e[4], 0.5)
                if sky_hits:
                    sx = sum(s[0] for s in sky_hits) / len(sky_hits)
                    sy_ = sum(s[1] for s in sky_hits) / len(sky_hits)
                    self.sky.append((i, sx, sy_, sum(s[2] for s in sky_hits)))
        self.shadow = shadow
        self.ring_col = mix(stops[1], (255, 255, 255), 0.4)
        # ---- static bloom: blur of the time-averaged disk light
        glow = self._blur(base, w, h, 4, 2)
        glow = self._blur(glow, w, h, 4, 2)
        self.glow = []
        gc = mix(stops[2], stops[3], 0.5)
        for i in range(n):
            gv = glow[i] * 0.55
            if gv > 0.02 and not shadow[i]:
                c = basec[i] if basec[i] is not None else gc
                self.glow.append((i, gv, mix(c, gc, 0.5)))
        # ---- jets along the projected spin axis
        self.jet = []
        if self.jets:
            ax, ay = -sr, cr                    # screen 'up' after roll (Y up)
            jl = max(w, h * ASPECT)
            for y in range(h):
                for x in range(w):
                    X = (x - cx)
                    Y = -(y - cy) * ASPECT
                    s = X * ax + Y * ay
                    p = X * ay - Y * ax
                    d = abs(s)
                    if d < 1.0:
                        continue
                    wd = 0.5 + d * self.jet_open
                    v = math.exp(-(p / wd) ** 2) + 0.25 * math.exp(-(p / (wd * 3.0)) ** 2)
                    if v < 0.04:
                        continue
                    i = y * w + x
                    if shadow[i] and s < 0:
                        continue
                    fall = (0.35 + 0.65 * math.exp(-d / (jl * 0.12))) * math.exp(-d / (jl * 0.5)) * (1.0 if s > 0 else 0.75)
                    fall *= min(1.0, d / (B_CRIT * sc * 0.9))
                    self.jet.append((i, d / sc, v * fall))
        # ---- stars
        self.star_amt = self.opt("stars")
        self.star_seed = rng.randrange(1 << 20)

    @staticmethod
    def _blur(src, w, h, rx, ry):
        tmp = [0.0] * (w * h)
        for y in range(h):
            row = y * w
            acc = 0.0
            win = 2 * rx + 1
            line = src[row:row + w]
            pre = [0.0]
            for v in line:
                pre.append(pre[-1] + v)
            for x in range(w):
                a, b = max(0, x - rx), min(w, x + rx + 1)
                tmp[row + x] = (pre[b] - pre[a]) / win
        out = [0.0] * (w * h)
        win = 2 * ry + 1
        for x in range(w):
            col = [tmp[y * w + x] for y in range(h)]
            pre = [0.0]
            for v in col:
                pre.append(pre[-1] + v)
            for y in range(h):
                a, b = max(0, y - ry), min(h, y + ry + 1)
                out[y * w + x] = (pre[b] - pre[a]) / win
        return out

    def draw(self, cv):
        w, h = self.w, self.h
        if (cv.w, cv.h) != (w, h):
            return
        t = self.t
        n = w * h
        R = [0.0] * n
        G = [0.0] * n
        Bl = [0.0] * n
        # static bloom
        for i, gv, c in self.glow:
            R[i] += c[0] * gv
            G[i] += c[1] * gv
            Bl[i] += c[2] * gv
        # rotating, infalling disk
        tex = self.tex
        shift = int(t * self.vin)
        for i, ia0, om, ir, inten, c in self.ent:
            v = tex[(ir + shift) % NRT][int(ia0 - om * t) % NA] * inten
            R[i] += c[0] * v
            G[i] += c[1] * v
            Bl[i] += c[2] * v
        # photon ring (it flickers faintly as hot spots pass behind the hole)
        rc = self.ring_col
        flick = 0.85 + 0.15 * math.sin(t * 1.7)
        ring = self.ring
        for i in range(n):
            v = ring[i]
            if v > 0.01:
                v *= flick
                R[i] += rc[0] * v
                G[i] += rc[1] * v
                Bl[i] += rc[2] * v
        # jets: knots racing outward
        J = None
        if self.jet:
            J = {}
            jc = self.jet_col
            sin = math.sin
            for i, d, v in self.jet:
                k = v * (0.6 + 1.0 * max(0.0, sin(d * 0.7 - t * 5.0)) ** 3) * 2.6
                J[i] = k * 255
                R[i] += jc[0] * k
                G[i] += jc[1] * k
                Bl[i] += jc[2] * k
        # tone map
        ramp = GLOW if cv.ramp == RAMPS["ascii"] else cv.ramp
        rn = len(ramp) - 1
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        exp = math.exp
        for i in range(n):
            r, g, b = R[i], G[i], Bl[i]
            m = r if r > g else g
            if b > m:
                m = b
            if m < 4.0:
                continue
            L = m / 255.0
            v = 1.0 - exp(-L * 1.6)
            gi = int(v * rn + 0.5)
            if gi <= 0:
                continue
            k = 255.0 / m
            cr, cg, cb = r * k, g * k, b * k
            if L > 1.2:                       # over-exposed light burns towards white
                wk = min(0.8, (L - 1.2) * 0.35)
                cr += (255 - cr) * wk
                cg += (255 - cg) * wk
                cb += (255 - cb) * wk
            kk = 0.25 + 0.75 * v
            if J is not None and J.get(i, 0.0) > m * 0.55:
                ch[i] = BEAM[int(v * 9 + 0.5)] if gi > 0 else ' '
                fg[i] = _q(cr * kk, cg * kk, cb * kk)
                lv[i] = v
                continue
            ch[i] = ramp[gi]
            fg[i] = _q(cr * kk, cg * kk, cb * kk)
            lv[i] = v
        # background stars, bent around the hole
        amt = self.star_amt
        if amt > 0:
            ox, oy = t * self.star_v[0], t * self.star_v[1]
            seed = self.star_seed
            thr = int(60 * amt)
            for i, sx, sy, wt in self.sky:
                if lv[i] > 0.3:
                    continue
                X = sx + ox
                Y = sy + oy
                gx, gy = math.floor(X / 3.0), math.floor(Y / 1.5)
                hsh = (gx * 73856093 ^ gy * 19349663 ^ seed) & 0xFFFFFFFF
                hsh = ((hsh ^ (hsh >> 13)) * 1274126177) & 0xFFFFFFFF
                if (hsh & 1023) >= thr:
                    continue
                px = (gx + 0.2 + 0.6 * ((hsh >> 10) & 255) / 255.0) * 3.0
                py = (gy + 0.2 + 0.6 * ((hsh >> 18) & 255) / 255.0) * 1.5
                d = (X - px) ** 2 + ((Y - py) * ASPECT) ** 2
                if d > 0.8:
                    continue
                br = (0.35 + 0.65 * ((hsh >> 26) & 63) / 63.0) * (1.0 - d / 0.8) * min(1.0, wt * 1.6)
                if br < 0.12 or br <= lv[i]:
                    continue
                tint = (hsh >> 8) & 3
                col = ((255, 230, 200), (210, 225, 255), (255, 255, 255), (255, 210, 170))[tint]
                c = "." if br < 0.35 else "+" if br < 0.65 else "*"
                ch[i] = c
                fg[i] = _q(col[0] * br, col[1] * br, col[2] * br)
                lv[i] = br
