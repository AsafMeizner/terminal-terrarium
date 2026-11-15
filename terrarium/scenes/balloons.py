"""Hot air balloons rising over a misty valley at sunrise: layered ridges fading into haze, drifting
mist, a glinting river, striped and patterned envelopes shaded as spheres, burner flares."""
import math

from ..engine import ASPECT, Scene, clamp, gradient, hsv, mix, noise1, noise2, scale
from .sakura import disc_glyph

TAU = math.tau


def qc(c):
    r, g, b = c
    return (0 if r < 0 else 252 if r > 252 else int(r) & ~3,
            0 if g < 0 else 252 if g > 252 else int(g) & ~3,
            0 if b < 0 else 252 if b > 252 else int(b) & ~3)


def hsh(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


TIMES = {
    "sunrise": {"sky": [(30, 34, 90), (110, 70, 140), (240, 130, 120), (255, 200, 130)], "sun": (255, 190, 110),
                "sun_y": 0.8, "ridge": (60, 50, 100), "mist": (255, 205, 190), "light": (255, 200, 160)},
    "day": {"sky": [(40, 100, 200), (90, 150, 225), (170, 205, 240), (225, 235, 245)], "sun": (255, 250, 225),
            "sun_y": 0.25, "ridge": (50, 90, 90), "mist": (235, 245, 255), "light": (255, 255, 240)},
    "sunset": {"sky": [(40, 24, 80), (150, 50, 110), (250, 110, 70), (255, 190, 90)], "sun": (255, 140, 60),
               "sun_y": 0.78, "ridge": (70, 34, 80), "mist": (255, 170, 150), "light": (255, 160, 110)},
}
PALETTES = [
    [(230, 40, 50), (255, 210, 60), (40, 90, 220)],
    [(255, 90, 160), (255, 240, 240), (120, 60, 200)],
    [(30, 170, 120), (255, 220, 80), (240, 80, 40)],
    [(255, 140, 30), (250, 245, 230), (200, 30, 60)],
    [(60, 180, 240), (255, 255, 255), (255, 200, 40)],
    [(150, 60, 220), (255, 120, 40), (250, 230, 90)],
    [(20, 40, 120), (240, 240, 250), (220, 40, 40)],
    [(250, 60, 120), (255, 180, 40), (60, 200, 160), (70, 90, 230)],
]
PATTERNS = ("gores", "bands", "chevron", "checker", "spiral", "crown", "solid")


class Balloons(Scene):
    name = "balloons"
    title = "Hot Air Balloons"
    blurb = "hot air balloons rising over a misty valley at sunrise, burners flaring"
    tags = ("sky", "calm", "colorful", "nature")
    options = {
        "count": (0, "number of balloons in the air (0 = based on screen size)"),
        "time": ("sunrise", "sunrise, day or sunset"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        self.seed = rng.randrange(1 << 15)
        self.look = TIMES.get(self.opt("time"), TIMES["sunrise"])
        self.horizon = h * rng.uniform(0.38, 0.5)
        self.sun_x = w * rng.uniform(0.2, 0.8)
        self.lx = 1 if self.sun_x > w * 0.5 else -1
        self.wind = rng.uniform(0.4, 1.4) * rng.choice((-1, 1))
        self.build_land()
        n = self.opt("count") or max(3, int(round((3 + w * h / 1500) * self.density)))
        self.target = n
        self.balloons = []
        for k in range(n):
            self.balloons.append(self.make_balloon(initial=True))
        self.balloons.sort(key=lambda b: b["z"])

    # -- static land --------------------------------------------------------------------------
    def build_land(self):
        rng = self.rng
        w, h = self.w, self.h
        s = self.seed
        look = self.look
        sky = look["sky"]
        hz = self.horizon
        n = w * h
        ch = [" "] * n
        fg = [None] * n
        lv = [0.0] * n
        hor = sky[-1]
        self.sky_row = []
        for y in range(h):
            f = clamp(y / max(1.0, hz))
            self.sky_row.append(gradient(sky, f ** 1.3))
        # ridges far -> near
        nl = rng.randint(4, 6)
        self.ridges = []
        base_col = mix(look["ridge"], hsv(rng.random(), 0.4, 0.5), rng.uniform(0, 0.3))
        for k in range(nl):
            f = k / max(1, nl - 1)
            base = hz + (h - hz) * (0.02 + 0.55 * f ** 1.3)
            amp = h * rng.uniform(0.05, 0.13) * (1.2 - 0.5 * f)
            sharp = rng.uniform(0.3, 1.0)
            prof = []
            for x in range(w):
                v = noise1(x * 0.02 * (1 + f), s + k * 7) * 0.7 + noise1(x * 0.06, s + k * 7 + 1) * 0.3 * sharp
                prof.append(base - amp * (0.6 + v))
            # a gap for the valley the river runs through
            self.ridges.append(prof)
        self.valley_x = w * rng.uniform(0.3, 0.7)
        cover = [-1] * n
        for k, prof in enumerate(self.ridges):
            for x in range(w):
                for y in range(max(0, int(prof[x])), h):
                    cover[y * w + x] = k
        self.cover = cover
        self.river = set()
        # valley floor + river (the nearest strip of land)
        floor_y = int(h - max(2, h * 0.12))
        self.floor_y = floor_y
        rw0 = rng.uniform(1.0, 2.0)
        ph = rng.uniform(0, TAU)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                k = cover[i]
                if k < 0:
                    f = clamp(y / max(1.0, hz))
                    r = hsh(x, y, s)
                    dens = 0.03 + 0.4 * f ** 3
                    if r < dens:
                        ch[i] = "." if r < dens * 0.6 else "·" if r < dens * 0.9 else "-"
                        fg[i] = qc(scale(self.sky_row[y], 0.6 + 0.4 * f))
                        lv[i] = 0.05
                    continue
                prof = self.ridges[k]
                far = 1 - k / max(1, nl - 1)
                top = int(prof[x])
                d = y - top
                # light from the sun side on ridge slopes
                sl = prof[min(w - 1, x + 1)] - prof[max(0, x - 1)]
                lit = clamp(0.45 - sl * 0.6 * self.lx - 0.08 * d)
                col = mix(scale(base_col, 0.35 + 0.5 * (1 - far)), hor, far * 0.75)
                col = mix(col, look["light"], lit * 0.35 * (0.4 + far * 0.6))
                if d == 0:
                    ch[i] = ("/" if sl < 0 else "\\") if abs(sl) > 1.2 else ("-" if hsh(x, y, s + 5) < 0.3 else "'" if far > 0.5 else ".")
                    fg[i] = qc(mix(col, look["light"], 0.4 + 0.3 * far))
                else:
                    r = hsh(x, y, s + 3 + k)
                    near = k >= nl - 2
                    if near and r < 0.3 and d <= 3:
                        ch[i] = "^" if hsh(x, y, s + 9) < 0.6 else "A"     # tree line
                    elif r < 0.55 - 0.25 * far:
                        if far > 0.45:
                            ch[i] = ":" if r < 0.35 else "." if r < 0.6 else "'"
                        else:
                            ch[i] = "░" if r < 0.5 else ":" if r < 0.65 else "."
                    fg[i] = qc(scale(col, 0.75 + 0.45 * lit))
                lv[i] = 0.2
        # the river winds from the bottom up into the valley
        for y in range(int(self.ridges[-1][int(self.valley_x)]) + 1, h):
            f = (y - hz) / max(1.0, h - hz)
            cx = self.valley_x + math.sin(y * 0.35 + ph) * w * 0.06 * f + (y - h) * 0.4
            half = rw0 * (0.4 + 2.5 * f ** 1.5)
            for x in range(int(cx - half), int(cx + half) + 1):
                if 0 <= x < w and cover[y * w + x] == nl - 1:
                    i = y * w + x
                    self.river.add(i)
                    ch[i] = "~" if hsh(x, y, s + 21) < 0.5 else "-"
                    fg[i] = qc(mix(hor, (90, 110, 160), 0.4))
                    lv[i] = 0.3
        self.river = sorted(self.river)
        self.bg = (ch, fg, lv)
        # mist: a wide static texture scrolled per row
        self.mw = w * 2
        self.mist = []
        for y in range(h):
            row = [noise2(x * 0.045, y * 0.35, s + 30) * 0.7 + noise2(x * 0.12, y * 0.8, s + 31) * 0.3
                   for x in range(self.mw)]
            self.mist.append(row)
        self.mist_band = []
        for y in range(h):
            v = 0.0
            for k in range(1, nl):
                prof = self.ridges[k]
                avg = sum(prof) / w
                v = max(v, math.exp(-((y - avg + 1.0) / max(1.0, h * 0.05)) ** 2))
            self.mist_band.append(v * (0.6 + 0.4 * clamp((y - hz) / max(1.0, h - hz))))
        self.mist_speed = [self.wind * (0.6 + 1.5 * hsh(y, 3, s)) for y in range(h)]

    # -- balloons -----------------------------------------------------------------------------
    def make_balloon(self, initial=False):
        rng = self.rng
        w, h = self.w, self.h
        z = rng.random() ** 0.8
        R = clamp((1.6 + 6.5 * z) * clamp(min(w / 100, h / 30), 0.5, 1.8), 1.2, 14)
        pal = list(rng.choice(PALETTES))
        rng.shuffle(pal)
        if initial:
            x = rng.uniform(0, w)
            y = rng.uniform(R * 1.2 / ASPECT + 1, self.horizon + (h - self.horizon) * 0.55)
        else:
            x = self.valley_x + rng.uniform(-w * 0.3, w * 0.3)
            ridge = self.ridges[int(clamp(z * len(self.ridges), 0, len(self.ridges) - 1))]
            y = ridge[int(clamp(x, 0, w - 1))] + R * 0.2
        return {
            "x": x, "y": y, "z": z, "R": R, "pal": pal, "pat": rng.choice(PATTERNS),
            "gores": rng.choice((6, 8, 10, 12)), "vy": -rng.uniform(0.15, 0.5) * (0.4 + z),
            "ph": rng.uniform(0, TAU), "burn": 0.0, "next": rng.uniform(1, 8), "spin": rng.uniform(-0.15, 0.15),
            "rot": rng.uniform(0, TAU),
        }

    def update(self, dt):
        super().update(dt)
        rng = self.rng
        w, h = self.w, self.h
        for b in self.balloons:
            alt = clamp(1 - b["y"] / max(1.0, h))
            b["x"] += (self.wind * (0.3 + alt) + 0.25 * math.sin(self.t * 0.2 + b["ph"])) * dt * (0.3 + b["z"])
            b["y"] += b["vy"] * dt * (1.0 + 0.6 * b["burn"])
            b["rot"] += b["spin"] * dt
            b["next"] -= dt
            if b["next"] <= 0 and b["burn"] <= 0:
                b["burn"] = rng.uniform(1.0, 2.5)
                b["next"] = rng.uniform(4, 12)
            if b["burn"] > 0:
                b["burn"] = max(0.0, b["burn"] - dt)
            if b["x"] < -b["R"] * 3:
                b["x"] = w + b["R"] * 2
            elif b["x"] > w + b["R"] * 3:
                b["x"] = -b["R"] * 2
        self.balloons = [b for b in self.balloons if b["y"] + b["R"] * 2.2 / ASPECT * 2 > -2]
        while len(self.balloons) < self.target:
            self.balloons.append(self.make_balloon())
            self.balloons.sort(key=lambda b: b["z"])

    # -- drawing --------------------------------------------------------------------------------
    def draw(self, cv):
        w, h = self.w, self.h
        if cv.w != w or cv.h != h:
            return
        t = self.t
        look = self.look
        bch, bfg, blv = self.bg
        cv.ch[:] = bch
        cv.fg[:] = bfg
        cv.lv[:] = blv
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        self.draw_sun(cv)
        # river glints
        sun = look["sun"]
        for i in self.river:
            r = hsh(i, int(t * 6), 5)
            if r < 0.08:
                ch[i] = "*" if r < 0.015 else "·"
                fg[i] = qc(mix(sun, (255, 255, 255), 0.4))
            elif r < 0.3:
                ch[i] = "~"
                fg[i] = qc(mix(self.sky_row[-1], sun, 0.4))
        # balloons far to near, with mist banks drawn in between by depth
        mist_drawn = False
        for b in self.balloons:
            if not mist_drawn and b["z"] > 0.45:
                self.draw_mist(cv)
                mist_drawn = True
            self.draw_balloon(cv, b)
        if not mist_drawn:
            self.draw_mist(cv)

    def draw_sun(self, cv):
        w, h = self.w, self.h
        look = self.look
        cx = self.sun_x
        cy = self.horizon * look["sun_y"]
        r = clamp(h * 0.09, 1.5, 7)
        R = r * 4.5
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        col = look["sun"]
        cover = self.cover
        for y in range(max(0, int(cy - R / ASPECT) - 1), min(h, int(cy + R / ASPECT) + 2)):
            for x in range(max(0, int(cx - R) - 1), min(w, int(cx + R) + 2)):
                i = y * w + x
                if cover[i] >= 0:
                    continue
                g, d = disc_glyph(x, y, cx, cy, r)
                if g:
                    ch[i] = g
                    fg[i] = qc(mix(col, (255, 255, 235), 0.5 * (1 - min(1.0, d))))
                    lv[i] = 1.0
                else:
                    gv = (R / r - d) / (R / r - 1)
                    if gv <= 0:
                        continue
                    gv = gv * gv * 0.85
                    old = fg[i] or (0, 0, 0)
                    fg[i] = qc(mix(old, col, clamp(gv)))
                    if ch[i] == " " and gv > 0.1:
                        ch[i] = "·" if gv > 0.3 else "."
                    elif gv > 0.45:
                        ch[i] = ":"

    def draw_mist(self, cv):
        w, h = self.w, self.h
        t = self.t
        mc = self.look["mist"]
        mw = self.mw
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        for y in range(h):
            band = self.mist_band[y]
            if band < 0.08:
                continue
            row = self.mist[y]
            off = int(t * self.mist_speed[y]) % mw
            rc = self.sky_row[min(h - 1, y)]
            for x in range(w):
                v = (row[(x + off) % mw] + 0.15) * band
                if v < 0.18:
                    continue
                i = y * w + x
                ch[i] = "~" if v > 0.55 else "·" if v > 0.3 else "."
                fg[i] = qc(mix(mix(rc, mc, 0.5), (255, 255, 255), clamp(v - 0.3)))
                lv[i] = 0.3

    def draw_balloon(self, cv, b):
        w, h = self.w, self.h
        ramp = cv.ramp
        nr = len(ramp) - 1
        cx, cy, R, z = b["x"], b["y"], b["R"], b["z"]
        pal = b["pal"]
        pat = b["pat"]
        ng = b["gores"]
        Ry = R * 1.05 / ASPECT * 2       # envelope height above centre (rows) ~ round on screen
        haze = self.sky_row[int(clamp(cy, 0, h - 1))]
        hk = (1 - z) * 0.45
        light = self.look["light"]
        burn = b["burn"]
        flare = 0.0
        if burn > 0:
            flare = clamp(burn * 2) * (0.75 + 0.25 * math.sin(self.t * 40 + b["ph"]))
        ch, fg, lv = cv.ch, cv.fg, cv.lv
        lx = self.lx
        top = int(cy - Ry * 0.5) - 1
        bot = int(cy + Ry * 0.75) + 1
        rot = b["rot"]
        for y in range(max(0, top), min(h, bot + 1)):
            v = (y + 0.5 - cy) / (Ry * 0.5)           # -1 top .. ~1.4 mouth
            if v < -1.0 or v > 1.45:
                continue
            if v <= 0:
                half = R * math.sqrt(max(0.0, 1 - v * v))
            else:
                half = R * (1 - 0.78 * (v / 1.45) ** 1.25)
            if half < 0.3:
                continue
            for x in range(int(cx - half - 1), int(cx + half + 1) + 1):
                if not (0 <= x < w):
                    continue
                u = (x + 0.5 - cx) / max(0.5, half)
                if abs(u) > 1.0:
                    continue
                nz = math.sqrt(max(0.0, 1 - u * u))
                vv = clamp(v, -1, 1)
                lam = clamp(0.35 + 0.45 * u * lx + 0.3 * nz - 0.2 * vv)
                # pattern colour
                lon = math.asin(clamp(u)) / math.pi + 0.5 + rot / TAU   # 0..1 around the visible side
                gi = int(lon * ng)
                if pat == "gores":
                    c = pal[gi % len(pal)]
                elif pat == "bands":
                    c = pal[int((v + 1) * 2.2) % len(pal)]
                elif pat == "chevron":
                    c = pal[int((v + 1) * 2.5 + abs((lon * ng) % 2 - 1) * 1.2) % len(pal)]
                elif pat == "checker":
                    c = pal[(gi + int((v + 1) * 3)) % len(pal)]
                elif pat == "spiral":
                    c = pal[int(lon * ng + v * 3) % len(pal)]
                elif pat == "crown":
                    c = pal[0] if v < -0.45 else pal[1] if v < 0.15 else pal[2 % len(pal)] if gi % 2 else pal[0]
                else:
                    c = pal[0] if abs(v - 0.1) > 0.12 else pal[1]
                seam = abs((lon * ng) % 1 - 0.5) > 0.44
                c = mix(c, light, 0.15 * lam)
                k = (0.3 + 0.85 * lam) * (0.85 if seam else 1.0)
                if flare > 0 and v > 0.3:
                    c = mix(c, (255, 200, 90), flare * 0.5 * (v - 0.3))
                    k += flare * 0.25 * (v - 0.3)
                col = mix(scale(c, k), haze, hk)
                j = int(clamp(0.35 + 0.6 * lam) * nr + 0.5)
                g = ramp[max(1, min(nr, j))]
                if abs(u) > 0.93:
                    g = "(" if u < 0 else ")"
                i = y * w + x
                ch[i] = g
                fg[i] = qc(col)
                lv[i] = 0.9
        # ropes and basket
        mouth_y = cy + Ry * 0.5 * 1.45
        mh = R * (1 - 0.78) * 0.9
        by = int(mouth_y + max(1.0, R * 0.35))
        bw = max(1, int(R * 0.35))
        rope = qc(mix((120, 90, 70), haze, hk))
        basket = qc(mix((150, 100, 60), haze, hk))
        my = int(mouth_y)
        for y in range(my, by):
            f = (y - my) / max(1, by - my)
            for side in (-1, 1):
                x = int(round(cx + side * (mh + (bw - mh) * f)))
                if 0 <= x < w and 0 <= y < h:
                    i = y * w + x
                    ch[i] = "\\" if (side < 0) == (bw > mh) else "/"
                    if abs(bw - mh) < 0.6:
                        ch[i] = "|"
                    fg[i] = rope
        if flare > 0 and my < by:
            for y in range(my, by):
                xi = int(cx)
                if 0 <= xi < w and 0 <= y < h:
                    i = y * w + xi
                    ch[i] = "^" if y == my else "*" if flare > 0.6 else "'"
                    fg[i] = qc(mix((255, 120, 30), (255, 245, 160), flare))
        if 0 <= by < h:
            for x in range(int(cx) - bw, int(cx) + bw + 1):
                if 0 <= x < w:
                    i = by * w + x
                    ch[i] = "[" if x == int(cx) - bw else "]" if x == int(cx) + bw else "#"
                    fg[i] = basket
