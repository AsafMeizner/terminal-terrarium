"""Dandelion clocks: glowing seed puffs on swaying stems; gusts carry seeds away, the heads slowly regrow."""
import math

from ..engine import ASPECT, Scene, clamp, mix, noise1, noise2

TAU = math.tau
GOLDEN = math.pi * (3 - math.sqrt(5))
# moods: tuft colour, stalk colour, halo / star tint, mist of the far seeds
MOODS = {
    "moonlit": ((255, 255, 255), (150, 160, 196), (170, 180, 240), (60, 64, 100)),
    "dusk": ((255, 236, 246), (180, 150, 190), (220, 160, 220), (80, 50, 90)),
    "dawn": ((255, 246, 220), (200, 170, 130), (255, 200, 150), (100, 70, 60)),
    "frost": ((236, 255, 255), (130, 180, 190), (140, 220, 240), (40, 80, 100)),
}
SEED = (236, 240, 255)
TUFT = (255, 255, 255)
STALK = (150, 160, 196)


def _dirch(dx, dy):
    ax, ay = abs(dx), abs(dy * ASPECT)
    if ax > 2.4 * ay:
        return "-"
    if ay > 2.4 * ax:
        return "|"
    return "\\" if dx * dy > 0 else "/"


class Head:
    def __init__(self, rng, x, ground, top, R, depth):
        self.x0 = x
        self.ground = ground
        self.top = top              # y of the seed head at rest
        self.R = R
        self.depth = depth
        self.lean = rng.uniform(-0.12, 0.12)
        self.ph = rng.uniform(0, TAU)
        self.yaw = rng.uniform(0, TAU)
        n = int(clamp(R * R * 1.1, 50, 260))
        self.seeds = []
        for i in range(n):
            zz = 1 - 2 * (i + 0.5) / n
            rr = math.sqrt(max(0.0, 1 - zz * zz))
            a = i * GOLDEN
            # [x, y, z on unit sphere, grown 0..1, length jitter]
            a += rng.uniform(-0.25, 0.25)
            self.seeds.append([rr * math.cos(a), zz, rr * math.sin(a), 1.0, rng.uniform(0.82, 1.06)])
        self.x, self.y = x, top
        self.tilt = 0.0
        self.push = 0.0             # extra lean from the user's breath or a clicked gust
        self.push_v = 0.0


class Dandelion(Scene):
    name = "dandelion"
    title = "Dandelion"
    blurb = "dandelion clocks in the wind, seeds drifting off on curling paths"
    tags = ("flowers", "nature", "calm", "night")
    interactions = "move the pointer past a seed head to blow its seeds away, click for a big gust from there"
    options = {
        "heads": (0, "number of seed heads (0 = based on screen size)"),
        "wind": (1.0, "strength of the gusts"),
        "mood": ("random", "moonlit, dusk, dawn, frost or random"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        # generative grammar: mood, wind character, how many heads and how they stand
        mood = self.opt("mood")
        self.mood = MOODS[mood] if mood in MOODS else MOODS[rng.choice(list(MOODS))]
        self.dir = rng.choice((-1, 1))                       # which way the wind blows
        self.gustiness = rng.uniform(0.6, 1.4)               # how often gusts come
        self.turb = rng.uniform(0.6, 1.6)                    # how much the air swirls
        n = self.opt("heads") or max(1, min(5, int(w / 55) + rng.choice((0, 0, 1, -1)) + 1))
        R = max(3.5, min(w * 0.13, h * ASPECT * 0.2, w / (n * 2.7) + 1)) * rng.uniform(0.85, 1.1)
        self.R = R
        ground = h - 1.5
        self.ground = ground
        self.heads = []
        for k in range(n):
            u = (k + 0.5) / n
            x = w * (0.12 + 0.76 * u) + rng.uniform(-1, 1) * w * 0.04
            depth = rng.uniform(0.6, 1.0)
            rr = R * depth * rng.uniform(0.75, 1.1)
            top = ground - (h - R / ASPECT * 1.6) * rng.uniform(0.35, 0.85)
            top = max(rr / ASPECT + 1, top)
            self.heads.append(Head(rng, x, ground, top, rr, depth))
        self.heads.sort(key=lambda hd: hd.depth)
        self.flyers = []
        self.stars = [(rng.uniform(0, w), rng.uniform(0, h * 0.75), rng.uniform(0, TAU), rng.uniform(0.3, 1))
                      for _ in range(max(10, w * h // 140))]
        # grass blades and the leaf rosettes at each stem's foot
        self.grass = [(rng.uniform(0, w), rng.uniform(1.5, 4.0), rng.uniform(0, TAU), rng.uniform(0.4, 1.0))
                      for _ in range(max(8, w // 4))]
        self.leaves = []
        for hd in self.heads:
            for s in (-1, 1):
                for j in range(2):
                    self.leaves.append((hd.x0, s * rng.uniform(0.95, 1.2) + s * j * 0.22,
                                        R * rng.uniform(1.0, 1.6) * (1 - 0.25 * j), rng.uniform(0, TAU)))
        self.gust = 0.0
        self.gust_t = rng.uniform(2, 5)
        self.gust_len = 3.0
        self.gust_age = 99.0
        self.gust_peak = 1.0
        self.streaks = []
        self.wind = 0.0
        self.last_ptr = None
        self.rings = []             # [x, y, age]: the shock of a clicked gust spreading out

    # ------------------------------------------------------------------ mouse
    def seed_pos(self, hd, s):
        cy, sy = math.cos(hd.yaw), math.sin(hd.yaw)
        px = s[0] * cy + s[2] * sy
        pz = -s[0] * sy + s[2] * cy
        x = hd.x + (px * math.cos(hd.tilt) - s[1] * math.sin(hd.tilt)) * hd.R * s[4]
        y = hd.y + (-(px * math.sin(hd.tilt) + s[1] * math.cos(hd.tilt))) * hd.R * s[4] / ASPECT
        return x, y, pz

    def blow(self, ox, oy, reach, power, rate):
        """Air blowing outward from (ox, oy): detach seeds facing it, push flyers and stems away."""
        rng = self.rng
        for hd in self.heads:
            dx, dy = hd.x - ox, (hd.y - oy) * ASPECT
            d = math.hypot(dx, dy)
            if d > reach + hd.R:
                continue
            fall = clamp(1.0 - max(0.0, d - hd.R) / reach)
            hd.push_v += (1 if dx >= 0 else -1) * power * fall * 0.6
            for s in hd.seeds:
                if s[3] < 1.0:
                    continue
                x, y, pz = self.seed_pos(hd, s)
                sx, sy = x - ox, (y - oy) * ASPECT
                sd = math.hypot(sx, sy) + 0.5
                # seeds nearest the breath go first
                near = clamp(1.0 - (sd - max(0.0, d - hd.R)) / (hd.R * 2.2))
                if rng.random() < rate * fall * (0.25 + near):
                    s[3] = -rng.uniform(4, 9)
                    sp = power * rng.uniform(6, 14) * (0.4 + fall)
                    self.flyers.append([x, y, sx / sd * sp, sy / sd * sp / ASPECT - 0.5, rng.uniform(0, TAU),
                                        rng.uniform(-4, 4), 0.0, hd.depth * (0.8 + 0.2 * (pz > 0)),
                                        rng.uniform(0, 100)])
        for fl in self.flyers:
            dx, dy = fl[0] - ox, (fl[1] - oy) * ASPECT
            d = math.hypot(dx, dy) + 0.5
            if d < reach:
                k = power * 10 * (1 - d / reach) / d
                fl[2] += dx * k
                fl[3] += dy * k / ASPECT

    def on_click(self, x, y):
        x = clamp(x if x == x else self.w / 2, -5, self.w + 5)
        y = clamp(y if y == y else self.h / 2, -5, self.h + 5)
        self.blow(x, y, max(18.0, self.w * 0.45), 2.0, 0.75)
        self.rings.append([x, y, 0.0])
        del self.rings[:-4]

    # ------------------------------------------------------------------ motion
    def wind_at(self, x, y, t):
        """Wind velocity (cells/s) with some swirl."""
        base = self.wind
        a = noise2(x * 0.05 + t * 0.15, y * 0.09, 3) * 2.2 * self.turb
        return self.dir * (base * 1.5 * (1.0 + 0.4 * math.cos(a)) + 1.4), base * 0.3 * self.turb * math.sin(a) - 0.35

    def update(self, dt):
        super().update(dt)
        rng = self.rng
        t = self.t
        strength = self.opt("wind")
        # gusts: a slow swell and a fade, now and then
        self.gust_t -= dt
        if self.gust_t <= 0:
            self.gust_age = 0.0
            self.gust_len = rng.uniform(2.5, 4.5)
            self.gust_peak = rng.uniform(0.6, 1.0)
            self.gust_t = rng.uniform(5, 10) / self.gustiness
        self.gust_age += dt
        g = 0.0
        if self.gust_age < self.gust_len:
            f = self.gust_age / self.gust_len
            g = math.sin(math.pi * f) ** 1.5 * self.gust_peak
        self.gust = g * strength
        self.wind = (0.4 + 0.6 * noise1(t * 0.3, 11) * 0.5 + 6.0 * g) * strength
        # the pointer is a breath: hovering near a head stirs it, sweeping past it blows seeds off
        p = self.pointer
        if p is not None:
            if self.last_ptr is not None and dt > 0:
                speed = math.hypot(p[0] - self.last_ptr[0], (p[1] - self.last_ptr[1]) * ASPECT) / dt
            else:
                speed = 0.0
            self.last_ptr = p
            self.blow(p[0], p[1], self.R * 1.6, 0.25 + min(1.0, speed / 25),
                      dt * (0.03 + min(4.0, speed / 6)))
        else:
            self.last_ptr = None
        for r in self.rings:
            r[2] += dt
        self.rings = [r for r in self.rings if r[2] < 1.0]
        for hd in self.heads:
            hd.push_v -= (hd.push * 9.0 + hd.push_v * 2.5) * dt     # a springy stem
            hd.push = clamp(hd.push + hd.push_v * dt, -0.5, 0.5)
            sway = (0.25 + 0.25 * math.sin(t * 0.8 + hd.ph)) * 0.3 + self.wind * 0.08
            hd.tilt = clamp(self.dir * sway * (0.6 + 0.4 * hd.depth) + hd.lean + hd.push, -0.8, 0.8)
            stem = hd.ground - hd.top
            hd.x = hd.x0 + math.sin(hd.tilt) * stem * ASPECT * 0.5
            hd.y = hd.ground - math.cos(hd.tilt) * stem
            hd.yaw += dt * (0.08 + 0.1 * self.wind)
            cy, sy = math.cos(hd.yaw), math.sin(hd.yaw)
            for s in hd.seeds:
                if s[3] < 1.0:
                    if s[3] < 0:
                        s[3] = min(0.0, s[3] + dt)      # waiting before regrowing
                    elif self.gust < 0.2:
                        s[3] = min(1.0, s[3] + dt * 0.06)
                    continue
                if self.gust > 0.15:
                    # seeds on the downwind side let go first
                    px = s[0] * cy + s[2] * sy
                    expo = 0.2 + max(0.0, px * self.dir) + 0.3 * max(0.0, -s[1])
                    if rng.random() < dt * self.gust * expo * 0.25:
                        s[3] = -rng.uniform(4, 9)
                        pz = -s[0] * sy + s[2] * cy
                        x = hd.x + (px * math.cos(hd.tilt) - s[1] * math.sin(hd.tilt)) * hd.R * s[4]
                        y = hd.y + (-(px * math.sin(hd.tilt) + s[1] * math.cos(hd.tilt))) * hd.R * s[4] / ASPECT
                        self.flyers.append([x, y, px * 2.0, -s[1] * 0.8, rng.uniform(0, TAU), rng.uniform(-3, 3),
                                            0.0, hd.depth * (0.8 + 0.2 * (pz > 0)), rng.uniform(0, 100)])
        keep = []
        for fl in self.flyers:
            wx, wy = self.wind_at(fl[0], fl[1], t + fl[8])
            k = min(1.0, dt * 1.2)
            fl[2] += (wx - fl[2]) * k
            fl[3] += (wy - fl[3]) * k
            fl[0] += fl[2] * dt * (0.6 + 0.4 * fl[7])
            fl[1] += fl[3] * dt * 0.5
            fl[4] += fl[5] * dt
            fl[6] += dt
            if -3 < fl[0] < self.w + 3 and -3 < fl[1] < self.h + 1 and fl[6] < 60:
                keep.append(fl)
        self.flyers = keep[-400:]
        # wind streaks during gusts
        if self.gust > 0.25 and rng.random() < dt * self.gust * 6:
            sx0 = rng.uniform(-10, self.w * 0.6)
            self.streaks.append([sx0 if self.dir > 0 else self.w - sx0, rng.uniform(0, self.h * 0.85), 0.0,
                                 rng.uniform(4, 10)])
        ks = []
        for st in self.streaks:
            st[2] += dt
            st[0] += dt * (8 + self.wind * 4) * self.dir
            if st[2] < 1.6 and -12 < st[0] < self.w + 12:
                ks.append(st)
        self.streaks = ks

    # ------------------------------------------------------------------ drawing
    def draw(self, cv):
        t = self.t
        w, h = cv.w, cv.h
        for x, y, ph, k in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * (0.6 + k) + ph * 7)
            cv.shade(x, y, 0.06 + 0.16 * tw * k, self.mood[2])
        for rx, ry, age in self.rings:     # a clicked gust: air rushing out in a ring
            r = 2.0 + age * max(w, h * ASPECT) * 0.45
            n = int(r * 3) + 12
            for i in range(n):
                a = i / n * TAU
                if math.sin(a * 7 + rx) > 0.2:            # broken into wisps
                    cv.shade(rx + math.cos(a) * r, ry + math.sin(a) * r / ASPECT, 0.35 * (1 - age),
                             self.mood[2])
        for st in self.streaks:
            a = math.sin(math.pi * st[2] / 1.6)
            for i in range(int(st[3])):
                xx = st[0] - i * self.dir
                cv.shade(xx, st[1] + 0.4 * math.sin(xx * 0.3), 0.1 * a * (1 - i / st[3]), self.mood[2])
        # back flyers, heads, front flyers
        for fl in self.flyers:
            if fl[7] < 0.75:
                self.draw_flyer(cv, fl)
        for hd in self.heads:
            self.draw_stem(cv, hd)
            self.draw_head(cv, hd)
        self.draw_ground(cv)
        for fl in self.flyers:
            if fl[7] >= 0.75:
                self.draw_flyer(cv, fl)

    def draw_stem(self, cv, hd):
        steps = int((hd.ground - hd.y - hd.R * 0.45 / ASPECT) * 2) + 2
        col = mix((60, 120, 70), (140, 190, 120), 0.5 * hd.depth)
        prev = None
        for i in range(steps + 1):
            f = i / steps                      # 0 at the ground
            bend = math.sin(hd.tilt) * f * f
            x = hd.x0 + bend * (hd.ground - hd.top) * ASPECT * 0.5
            y = hd.ground - (hd.ground - hd.y - hd.R * 0.45 / ASPECT) * f
            if prev is not None:
                cv.put(x, y, _dirch(x - prev[0], y - prev[1]), mix(col, (30, 60, 40), 0.3 * (1 - f)))
            prev = (x, y)

    def draw_head(self, cv, hd):
        R = hd.R
        cx, cy = hd.x, hd.y
        cyaw, syaw = math.cos(hd.yaw), math.sin(hd.yaw)
        ct, st = math.cos(hd.tilt), math.sin(hd.tilt)
        glow = 0.55 + 0.45 * hd.depth
        shade = cv.shade
        # soft halo
        hr = R * 1.25
        for y in range(int(cy - hr / ASPECT) - 1, int(cy + hr / ASPECT) + 2):
            for x in range(int(cx - hr) - 1, int(cx + hr) + 2):
                d = math.hypot(x + 0.5 - cx, (y + 0.5 - cy) * ASPECT) / hr
                if d < 1:
                    shade(x, y, 0.07 * (1 - d) * glow, self.mood[2])
        order = []
        for s in hd.seeds:
            if s[3] <= 0:
                continue
            px = s[0] * cyaw + s[2] * syaw
            pz = -s[0] * syaw + s[2] * cyaw
            py = s[1]
            sx = px * ct - py * st
            sy = px * st + py * ct
            order.append((pz, sx, sy, s[3] * s[4]))
        order.sort()
        put = cv.put
        for pz, sx, sy, g in order:
            front = 0.5 + 0.5 * pz                # 0 back .. 1 front
            L = R * g
            tx, ty = cx + sx * L, cy - sy * L / ASPECT
            if front > 0.3:
                # the beak: faint dots toward the centre
                sc = mix((24, 26, 40), self.mood[1], (0.25 + 0.5 * front) * glow)
                for f in (0.45, 0.7):
                    put(cx + sx * L * f, cy - sy * L * f / ASPECT, "·", sc)
            # the pappus
            k = front * glow * (0.5 + 0.5 * g)
            if front > 0.72:
                ch = "*"
            elif front > 0.3:
                ch = "+"
            else:
                ch = "·"
            put(tx, ty, ch, mix(self.mood[3], self.mood[0], 0.25 + 0.75 * k))
        # the receptacle
        shade(cx, cy, 0.7, (170, 140, 90), "over", False)
        if R > 6:
            shade(cx + 1, cy, 0.45, (130, 110, 80), "over", False)

    def draw_flyer(self, cv, fl):
        x, y, vx, vy, spin, _, age, depth, _ = fl
        a = min(1.0, age * 2) * (0.5 + 0.5 * depth)
        # the stalk hangs below the parachute, rocking as it spins
        ang = math.pi / 2 + 0.7 * math.sin(spin)
        sx, sy = math.cos(ang), math.sin(ang) / ASPECT
        cv.put(x + sx * 1.2, y + sy * 1.2, _dirch(sx, sy), mix((20, 20, 30), self.mood[1], a * 0.45))
        if depth > 0.8:
            cv.put(x + sx * 2.2, y + sy * 2.2, "·", mix((20, 20, 30), (200, 170, 120), a * 0.8))
        wide = abs(math.cos(spin))
        cv.put(x, y, "*" if wide > 0.45 else "+", mix((40, 40, 60), self.mood[0], a))

    def draw_ground(self, cv):
        t = self.t
        h = cv.h
        wind = self.wind
        for gx, gl, ph, k in self.grass:
            bend = 0.25 * math.sin(t * 1.1 + ph) + 0.12 * wind * self.dir
            prev = None
            n = int(gl * 2) + 1
            for i in range(n + 1):
                f = i / n
                x = gx + bend * f * f * gl * 2
                y = h - 0.01 - f * gl
                if prev is not None:
                    cv.put(x, y, _dirch(x - prev[0], y - prev[1]), mix((14, 40, 24), (70, 140, 80), k * (0.3 + 0.5 * f)))
                prev = (x, y)
        # toothed dandelion leaves fanning out from each stem foot
        ground = self.ground + 1.0
        for x0, ang, L, ph in self.leaves:
            a = ang + 0.04 * math.sin(t * 0.9 + ph) + 0.02 * wind * self.dir
            dx, dy = math.sin(a), -math.cos(a)
            px, py = -dy, dx
            n = int(L * 1.3) + 2
            side = 1 if dx > 0 else -1
            for i in range(n + 1):
                f = i / n
                hw = L * 0.13 * math.sin(math.pi * f ** 0.75)
                hw *= 0.45 + 0.55 * ((f * 6.5) % 1.0)      # backward-pointing teeth
                bx = x0 + dx * L * f
                by = ground * ASPECT + dy * L * f
                ns = max(1, int(hw * 1.4))
                for j in range(-ns, ns + 1):
                    s2 = j / ns
                    lit = clamp(0.6 - 0.35 * s2 * side)
                    if abs(s2) < 0.2:
                        v, col = 0.42, (120, 190, 110)
                    else:
                        v, col = 0.22 + 0.35 * lit, mix((14, 50, 26), (90, 170, 84), lit)
                    cv.shade(bx + px * hw * s2, (by + py * hw * s2) / ASPECT, v, col, "over", False)
