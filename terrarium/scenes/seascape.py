"""A cross-section of the sea: boats and leaping dolphins above, fish, kelp and light rays below."""
import math

from ..engine import ASPECT, Canvas, Scene, clamp, gradient, hsv, mix, noise1, scale

TAU = math.tau

TIMES = {
    "day": {
        "sky": [(40, 100, 200), (70, 140, 225), (120, 185, 240), (190, 225, 250)], "sky_v": (0.3, 0.6), "dens": (0.55, 0.35), "wdens": 1.6,
        "sun": [(255, 210, 120), (255, 245, 190), (255, 255, 245)], "glow": (255, 240, 200), "moon": False,
        "water": [(60, 190, 220), (24, 120, 180), (12, 60, 120), (6, 24, 60)], "surf": (200, 245, 255),
        "ray": (150, 230, 255), "sand": [(90, 80, 60), (200, 180, 130)], "stars": 0.0,
        "boat": {"sail": (250, 250, 255), "edge": (190, 205, 230), "hull": (200, 60, 60), "hull2": (60, 80, 130),
                 "mast": (150, 120, 90), "win": (40, 60, 90), "funnel": (230, 90, 50), "far": (120, 150, 190)},
        "gull": (245, 245, 250), "dolphin": (120, 150, 190), "belly": (200, 215, 235), "lights": False,
    },
    "sunset": {
        "sky": [(30, 14, 70), (90, 30, 110), (200, 70, 110), (255, 130, 80), (255, 190, 110)], "sky_v": (0.06, 0.4), "dens": (0.18, 0.55), "wdens": 1.0,
        "sun": [(255, 100, 60), (255, 180, 100), (255, 240, 190)], "glow": (255, 140, 80), "moon": False,
        "water": [(200, 110, 140), (90, 50, 130), (34, 26, 90), (10, 10, 40)], "surf": (255, 200, 150),
        "ray": (255, 160, 140), "sand": [(60, 40, 60), (160, 110, 110)], "stars": 0.15,
        "boat": {"sail": (120, 50, 90), "edge": (255, 150, 110), "hull": (70, 26, 60), "hull2": (60, 24, 56),
                 "mast": (90, 40, 70), "win": (255, 200, 120), "funnel": (100, 36, 70), "far": (150, 70, 110)},
        "gull": (60, 24, 60), "dolphin": (110, 80, 140), "belly": (220, 150, 160), "lights": True,
    },
    "night": {
        "sky": [(2, 4, 14), (6, 12, 34), (14, 26, 64), (30, 48, 100)], "sky_v": (0.04, 0.3), "dens": (0.12, 0.5), "wdens": 0.9,
        "sun": [(140, 150, 190), (210, 220, 245), (250, 250, 255)], "glow": (150, 170, 230), "moon": True,
        "water": [(60, 90, 150), (18, 36, 90), (8, 16, 50), (2, 6, 24)], "surf": (190, 210, 255),
        "ray": (120, 150, 230), "sand": [(30, 34, 54), (80, 86, 120)], "stars": 1.0,
        "boat": {"sail": (110, 125, 170), "edge": (190, 205, 245), "hull": (60, 66, 100), "hull2": (50, 56, 90),
                 "mast": (90, 96, 130), "win": (255, 210, 120), "funnel": (80, 86, 120), "far": (70, 84, 130)},
        "gull": (150, 160, 200), "dolphin": (90, 110, 160), "belly": (160, 180, 220), "lights": True,
    },
}

# Boat sprites, facing right (bow on the right). Last `hull` rows are the hull.
BOATS = {
    "sloop": (["      |      ",
               "     /|\\     ",
               "    /:|:\\    ",
               "   /::|::\\   ",
               "  /:::|:::\\  ",
               " /____|____\\ ",
               "\\===========/",
               " \\_________/ "], 2),
    "cutter": (["    |\\   ",
                "    |:\\  ",
                "    |::\\ ",
                "    |:::\\",
                "  __|____\\_",
                "  \\=======/",
                "   \\_____/ "], 2),
    "schooner": (["      |\\       |\\     ",
                  "      |:\\      |:\\    ",
                  "      |::\\     |::\\   ",
                  "      |:::\\    |:::\\  ",
                  "      |::::\\   |::::\\ ",
                  "  ____|_____\\__|_____\\_",
                  "  \\===================/ ",
                  "   \\_____o___o___o___/  "], 2),
    "steamer": (["          __    __        ",
                 "         |##|  |##|       ",
                 "      ___|==|__|==|___    ",
                 "     | o  o  o  o  o  |   ",
                 " ____|________________|___",
                 " \\ o  o  o  o  o  o  o   /",
                 "  \\=====================/ "], 2),
    "trawler": (["   |\\              ",
                 "   | \\        ___  ",
                 "   |  \\      |o o| ",
                 "___|___\\_____|___|_",
                 "\\  o    o    o    /",
                 " \\===============/ "], 2),
    "far_sail": ([" |\\ ",
                  " |:\\",
                  "\\__/"], 1),
    "far_ship": (["   _|_  ",
                  "\\______/"], 1),
}
MIRROR = str.maketrans("/\\()[]<>{}", "\\/)(][><}{")
FUNNELS = {"steamer": [(10, 0), (16, 0)], "trawler": [], "far_ship": [(4, 0)]}

# Fish species: right-facing glyphs, color, school size range, speed
SPECIES = [
    {"g": ">", "col": (180, 215, 235), "n": (16, 30), "sp": 5.5, "tight": 1.0},
    {"g": "><>", "col": (255, 140, 50), "n": (5, 10), "sp": 3.5, "tight": 0.8},
    {"g": "><)>", "col": (80, 150, 255), "n": (4, 8), "sp": 3.2, "tight": 0.7},
    {"g": "><((('>", "col": (255, 215, 80), "n": (2, 4), "sp": 2.6, "tight": 0.5},
    {"g": "<><", "col": (120, 255, 200), "n": (6, 12), "sp": 4.0, "tight": 0.9},
    {"g": ">=>", "col": (255, 110, 160), "n": (5, 9), "sp": 3.6, "tight": 0.8},
    {"g": "><=>", "col": (200, 160, 255), "n": (4, 8), "sp": 3.0, "tight": 0.7},
]

WHALE = ["            __.---.__           ",
         "       _.--'         `--._    _ ",
         "     .'  o                `-.' )",
         "    <_________________.--.___.'  ",
         "         `--..____..--'          "]
TURTLE = ["    _____     ",
          "  /'_|_|_'\\__ ",
          " (_|_|_|_|_)_o>",
          "   '/    \\'    "]


def _hash(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 982451653) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 65535.0


def mirror(lines):
    w = max(len(l) for l in lines)
    return [l.ljust(w)[::-1].translate(MIRROR) for l in lines]


class Boat:
    __slots__ = ("kind", "x", "dir", "speed", "depth", "lines", "hull", "phase", "w", "hh", "funnels", "col")


class Dolphin:
    __slots__ = ("x", "y", "vx", "vy", "air", "trail", "next_leap", "cruise", "phase", "len", "delay")


class Seascape(Scene):
    name = "seascape"
    title = "Seascape"
    blurb = "a cross-section of the sea: boats and leaping dolphins above, fish and kelp below"
    tags = ("ocean", "nature", "calm", "animals")
    interactions = "click the sea for a dolphin leap, the sky for gulls; point under water to scatter fish"
    options = {
        "time": ("random", "random, day, sunset or night"),
        "boats": (-1, "how many boats at once (-1 = random)"),
        "dolphins": (True, "a pod of leaping dolphins"),
        "fish": (1.0, "amount of fish"),
    }

    # ------------------------------------------------------------------ setup
    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        tm = str(self.opt("time")).lower()
        if tm not in TIMES:
            tm = rng.choice(("day", "day", "sunset", "sunset", "sunset", "night", "night"))
        self.tname = tm
        self.pal = TIMES[tm]
        self.seed = rng.randrange(1 << 15)
        self.hz = hz = max(4, int(round(h * rng.uniform(0.34, 0.42))))
        self.amp = rng.uniform(0.35, 0.75)
        self.wk = rng.uniform(0.18, 0.32)
        # seabed
        depth = h - hz
        bedh = max(1.5, depth * rng.uniform(0.1, 0.2))
        self.bed = [h - 1 - bedh * (0.5 + 0.5 * noise1(x * 0.06, self.seed)) - 1.2 * noise1(x * 0.23, self.seed + 1)
                    for x in range(w)]
        # sun / moon
        self.sx = w * rng.choice((rng.uniform(0.12, 0.35), rng.uniform(0.65, 0.88)))
        big = min(w, h * ASPECT)
        self.sr = max(2.5, big * rng.uniform(0.08, 0.13) * (0.75 if self.pal["moon"] else 1.0))
        lift = rng.uniform(-0.25, 0.6) if tm != "day" else rng.uniform(1.4, 2.2)
        self.sy = hz - self.sr / ASPECT * lift
        self.sy = max(self.sr / ASPECT + 0.5, self.sy)
        self.raydir = 1 if self.sx < w / 2 else -1
        # sky variant: slight hue drift of the palette
        self.hue = rng.uniform(-0.04, 0.04)
        self.clouds = rng.choice((0.0, 0.6, 1.0, 1.4))
        self.cloud_at = rng.uniform(0.3, 0.75)
        # boats
        nb = self.opt("boats")
        self.maxboats = nb if nb >= 0 else rng.randint(1, 3 if w < 100 else 4)
        kinds = ["sloop", "cutter", "schooner", "steamer", "trawler"]
        wts = [rng.uniform(0.2, 1.0) for _ in kinds]
        self.mix_kinds = (kinds, wts)
        self.boats = []
        for k in range(self.maxboats):
            self.boats.append(self.new_boat(initial=True))
        self.boats.sort(key=lambda b: b.depth)
        self.boat_timer = rng.uniform(2, 6)
        self.smoke = []
        self.splash = []
        # gulls
        self.gulls = [self.new_gull(True) for _ in range(rng.randint(1, 4) if w >= 60 else 1)]
        # dolphins: one pod
        self.pod = []
        self.pod_timer = rng.uniform(0.5, 3.0)
        self.pod_n = rng.randint(1, 5)
        # fish schools from a few species
        fam = max(0.0, self.opt("fish"))
        species = rng.sample(SPECIES, rng.randint(2, 3))
        area = w * depth / (100 * 18)
        self.schools = []
        for sp in species:
            col = sp["col"]
            n = int(rng.randint(*sp["n"]) * min(2.5, max(0.4, area)) * fam * self.density)
            if n <= 0:
                continue
            tx, ty = rng.uniform(0, w), rng.uniform(hz + 2, max(hz + 3, self.bedtop() - 1))
            fish = []
            for _ in range(n):
                fx = tx + rng.uniform(-5, 5)
                fy = ty + rng.uniform(-1.5, 1.5)
                d = rng.choice((-1, 1))
                fish.append([fx, fy, d * sp["sp"], 0.0, d])
            self.schools.append({"sp": sp, "fish": fish, "tx": tx, "ty": ty, "timer": rng.uniform(2, 6),
                                 "col": mix(col, (255, 255, 255), rng.uniform(0, 0.25))})
        # seaweed and coral
        self.weeds = []
        nwd = max(2, int(w / rng.uniform(6, 12) * self.density))
        kelp_hue = rng.choice(((40, 160, 70), (90, 150, 40), (40, 140, 110), (150, 120, 40)))
        for _ in range(nwd):
            x = rng.uniform(1, w - 2)
            hgt = (self.bed[int(x)] - hz) * rng.uniform(0.2, 0.7)
            self.weeds.append((x, hgt, rng.uniform(0, TAU), rng.uniform(0.6, 1.4),
                               mix(kelp_hue, (255, 255, 160), rng.uniform(0, 0.3))))
        self.corals = []
        for _ in range(int(w / rng.uniform(8, 20))):
            x = rng.randrange(1, max(2, w - 1))
            self.corals.append((x, rng.choice(((255, 110, 140), (255, 160, 80), (190, 120, 255), (255, 220, 120))),
                                rng.randint(1, 3), rng.random()))
        self.bubbles = []
        self.vents = [rng.uniform(0, w) for _ in range(rng.randint(1, 3))]
        self.creature = None
        self.creature_timer = rng.uniform(4, 14)
        # light-ray profile along the slanted axis
        self.rayL = w + h * 3 + 10
        self.rays = [max(0.0, math.sin(u * 0.19) * math.sin(u * 0.053 + 1.3) + 0.2 * math.sin(u * 0.41)) for u in range(self.rayL)]
        ns = int(w * hz / 25 * self.pal["stars"] * self.density)
        self.stars = [(rng.randrange(w), rng.randrange(max(1, hz - 1)), rng.uniform(0.2, 1.0), rng.uniform(0, TAU))
                      for _ in range(ns)]
        self._bgkey = None
        self.visitors = []   # gulls called in by a click: [x, y, vx, phase, age]

    def on_click(self, x, y):
        w, hz = self.w, self.hz
        rng = self.rng
        x = clamp(x, 0.0, w - 1.0)
        if y < hz - 0.5:
            # the sky: a little V of gulls sweeps through the clicked spot
            y = clamp(y, 0.5, max(0.5, hz - 2.0))
            d = rng.choice((-1, 1))
            sp = rng.uniform(8, 11)
            for k in range(rng.randint(2, 4)):
                side = 1 if k % 2 else -1
                row = (k + 1) // 2
                self.visitors.append([x - d * row * 3.5, clamp(y + side * row * 0.9, 0.5, max(0.5, hz - 2.0)),
                                      d * sp, rng.uniform(0, TAU), 0.0])
            self.visitors = self.visitors[-24:]
            return
        # the sea: a dolphin bursts out of the water and arcs over the clicked spot
        if len(self.pod) >= 12:
            return
        if not hasattr(self, "leap_rhythm"):
            self.leap_rhythm = 2.4
        d = rng.choice((-1, 1))
        o = Dolphin()
        o.vx = d * rng.uniform(10, 12)
        v0 = rng.uniform(13.5, 15.5)
        o.x = x - o.vx * (v0 / 16.0)            # take off early so the top of the arc lands on the click
        o.cruise = hz + rng.uniform(1.6, 3.2)
        o.y = self.surf(o.x) + 1.4
        o.vy = -v0
        o.air = False
        o.trail = [(o.x - o.vx * 0.03 * k, o.y + 0.4 * k) for k in range(6, 0, -1)]
        o.next_leap = self.leap_rhythm + rng.uniform(0, 1)
        o.phase = rng.uniform(0, TAU)
        o.len = rng.randint(5, 7) if w >= 80 else 4
        o.delay = 0.0
        self.pod.append(o)

    def bedtop(self):
        return min(self.bed) if self.bed else self.h - 1

    def surf(self, x, t=None):
        t = self.t if t is None else t
        k = self.wk
        return self.hz + self.amp * (0.65 * math.sin(x * k - t * 1.7) + 0.35 * math.sin(x * k * 0.43 + t * 0.9 + 1.3))

    def new_boat(self, initial=False):
        rng = self.rng
        b = Boat()
        b.depth = rng.random()             # 0 far .. 1 near
        kinds, wts = self.mix_kinds
        if b.depth < 0.35 or self.w < 70:
            b.kind = "far_sail" if rng.random() < 0.6 else "far_ship"
            b.depth *= 0.4
        else:
            b.kind = rng.choices(kinds, wts)[0]
            if self.w < 110 and b.kind in ("schooner", "steamer"):
                b.kind = rng.choice(("sloop", "cutter", "trawler"))
        lines, hull = BOATS[b.kind]
        b.dir = rng.choice((-1, 1))
        b.lines = lines if b.dir > 0 else mirror(lines)
        b.hull = hull
        b.w = max(len(l) for l in lines)
        b.hh = len(lines)
        b.speed = (0.6 + 2.2 * b.depth) * rng.uniform(0.7, 1.3) * (1.3 if b.kind in ("steamer", "trawler") else 1.0)
        b.phase = rng.uniform(0, TAU)
        b.funnels = FUNNELS.get(b.kind, [])
        if b.dir < 0:
            b.funnels = [(b.w - 1 - fx - 1, fy) for fx, fy in b.funnels]
        if initial:
            b.x = rng.uniform(-b.w * 0.3, self.w - b.w * 0.7)
        else:
            b.x = -b.w - 1 if b.dir > 0 else self.w + 1
        b.col = rng.random()
        return b

    def new_gull(self, initial=False):
        rng = self.rng
        d = rng.choice((-1, 1))
        x = rng.uniform(0, self.w) if initial else (-4 if d > 0 else self.w + 4)
        return [x, rng.uniform(1, max(2, self.hz * 0.6)), d * rng.uniform(3, 7), rng.uniform(0, TAU), rng.random() < 0.4]

    # ------------------------------------------------------------------ static layer
    def paint_static(self, cv):
        w, h, hz = self.w, self.h, self.hz
        pal = self.pal
        sky = [self.tint(c) for c in pal["sky"]]
        lo, hi = pal["sky_v"]
        sx, sy, sr = self.sx, self.sy, self.sr
        glow = pal["glow"]
        cloud_c = mix(sky[-1], (255, 255, 255), 0.35) if not pal["moon"] else (70, 80, 120)
        d0, d1 = pal["dens"]
        wd = pal["wdens"]
        for y in range(hz):
            f = y / max(1, hz - 1)
            col = gradient(sky, f ** 1.1)
            v = lo + (hi - lo) * f ** 1.5
            dy = (y + 0.5 - sy) * ASPECT
            for x in range(w):
                dx = x + 0.5 - sx
                d = math.sqrt(dx * dx + dy * dy) / sr
                gl = 0.0
                if d > 1.0:
                    gl = 0.7 * math.exp(-(d - 1.0) * 0.9) + 0.15 * math.exp(-(d - 1.0) * 0.25)
                r = _hash(x, y, 5)
                # thin streaky clouds, lit from the sun side
                cl = noise1(x * 0.045 + y * 7.3, self.seed + y) * 0.7 + noise1(x * 0.13 + y * 3.1, self.seed + 2) * 0.3
                band = math.exp(-((f - self.cloud_at) / 0.22) ** 2) * self.clouds
                if cl * band > 0.18:
                    k = clamp((cl * band - 0.18) * 4)
                    put_c = mix(cloud_c, glow, clamp(gl * 2.5 + 0.2))
                    cv.put(x, y, "~" if k > 0.6 else "-", scale(put_c, 0.35 + 0.5 * k + 0.3 * gl), level=0.4)
                    continue
                if r < d0 + d1 * f + gl * 1.5:
                    lvl = min(1.0, v + gl * 0.6)
                    ch = "." if r < 0.09 + 0.2 * f else ":" if lvl > 0.45 and r > 0.5 else "·" if r > 0.3 else "."
                    cv.put(x, y, ch, scale(mix(col, glow, min(1.0, gl * 1.3)), 0.45 + 0.9 * lvl), level=lvl)
        # sun / moon disc (half blocks), clipped at the mean sea level
        stops = pal["sun"]
        moon = pal["moon"]
        for y in range(max(0, int(sy - sr / ASPECT) - 1), min(hz, int(sy + sr / ASPECT) + 2)):
            for x in range(max(0, int(sx - sr) - 1), min(w, int(sx + sr) + 2)):
                dx = (x + 0.5 - sx) / sr
                top = dx * dx + ((y + 0.25 - sy) * ASPECT / sr) ** 2 <= 1
                bot = dx * dx + ((y + 0.75 - sy) * ASPECT / sr) ** 2 <= 1 and y < hz - 1
                if not (top or bot):
                    continue
                d = math.sqrt(dx * dx + ((y + 0.5 - sy) * ASPECT / sr) ** 2)
                if moon:
                    cr = clamp(noise1(x * 0.7 + y * 3.1, 9) * 0.8)
                    col = gradient(stops, 0.95 - 0.3 * min(1.0, d) ** 2 - 0.35 * cr)
                else:
                    col = gradient(stops, 1 - min(1.0, d) * 0.65 - (y + 0.5 - sy) / (sr / ASPECT) * 0.15)
                cv.put(x, y, "\u2588" if top and bot else "\u2580" if top else "\u2584", col, level=1.0)
        # water body: depth gradient with sparse texture
        water = pal["water"]
        for y in range(hz + 1, h):
            f = (y - hz) / max(1, h - hz)
            col = gradient(water, f ** 0.8)
            for x in range(w):
                if y >= self.bed[x]:
                    continue
                r = _hash(x, y, 11)
                if r < (0.34 - 0.24 * f) * wd:
                    ch = "." if r < 0.14 else "-" if r < 0.2 else "~" if r < 0.24 else "·"
                    cv.put(x, y, ch, scale(col, 0.45 + 0.35 * (1 - f)), level=0.1)
        # seabed sand
        s0, s1 = pal["sand"]
        for x in range(w):
            yb = self.bed[x]
            iy = int(yb)
            l, r = self.bed[max(0, x - 1)], self.bed[min(w - 1, x + 1)]
            sl = (r - l) * 0.5
            ch = "\\" if sl > 0.7 else "/" if sl < -0.7 else ("_" if yb - iy > 0.5 else "-")
            cv.put(x, iy, ch, s1, level=0.5)
            for y in range(iy + 1, h):
                q = _hash(x, y, 3)
                ch = "." if q < 0.4 else "," if q < 0.6 else ":" if q < 0.75 else "_" if q < 0.85 else "o" if q < 0.9 else " "
                cv.put(x, y, ch, mix(s1, s0, clamp((y - yb) / 3 + q * 0.3)), level=0.3)
        # coral
        for x, col, sz, r in self.corals:
            yb = int(self.bed[min(w - 1, x)])
            shape = ["Y", "y", "*", "v", "%"][int(r * 5)]
            for k in range(sz):
                for dx in range(-k, k + 1):
                    if abs(dx) + (sz - k) <= sz:
                        cv.put(x + dx, yb - 1 - (sz - 1 - k), shape if k == 0 else ("\\" if dx < 0 else "/" if dx > 0 else "|"),
                               scale(col, 0.7 + 0.3 * (k == 0)), level=0.6)
            cv.put(x, yb - 1, "|", scale(col, 0.75), level=0.6)

    def tint(self, c):
        if not self.hue:
            return c
        k = self.hue
        return (clamp(c[0] * (1 + k * 2), 0, 255), c[1], clamp(c[2] * (1 - k * 2), 0, 255))

    def background(self, cv):
        key = (cv.w, cv.h, cv.ramp)
        if self._bgkey != key:
            bg = Canvas(cv.w, cv.h, cv.ramp)
            self.paint_static(bg)
            self._bg = bg
            self._bgkey = key
        bg = self._bg
        cv.ch[:] = bg.ch
        cv.fg[:] = bg.fg
        cv.lv[:] = bg.lv
        cv.bc[:] = bg.bc

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        rng = self.rng
        t = self.t
        w, h, hz = self.w, self.h, self.hz
        # boats
        keep = []
        for b in self.boats:
            b.x += b.dir * b.speed * dt
            if -b.w - 3 < b.x < w + 3:
                keep.append(b)
            for fx, fy in b.funnels:
                if rng.random() < dt * 9:
                    y0 = self.boat_y(b) - b.hh + 1 + fy
                    self.smoke.append([b.x + fx + 0.5, y0 - 0.5, -b.dir * b.speed * 0.3, 0.0, rng.uniform(2.5, 5.0), b.depth])
        self.boats = keep
        if len(self.boats) < self.maxboats:
            self.boat_timer -= dt
            if self.boat_timer <= 0:
                self.boats.append(self.new_boat())
                self.boats.sort(key=lambda b: b.depth)
                self.boat_timer = rng.uniform(3, 12)
        sm = []
        for p in self.smoke:
            p[3] += dt
            p[0] += (p[2] + 1.2) * dt
            p[1] -= dt * (0.9 - 0.12 * p[3])
            if p[3] < p[4] and p[1] > -1:
                sm.append(p)
        self.smoke = sm[-300:]
        # gulls
        for g in self.gulls:
            g[0] += g[2] * dt
            g[1] += math.sin(t * 0.7 + g[3]) * dt * 0.8
            g[1] = clamp(g[1], 0.5, hz - 2)
        self.gulls = [g if -6 < g[0] < w + 6 else self.new_gull() for g in self.gulls]
        # dolphins
        if self.opt("dolphins") or self.pod:
            self.update_pod(dt)
        for g in self.visitors:
            g[0] += g[2] * dt
            g[4] += dt
            g[1] = clamp(g[1] - math.sin(g[4] * 1.5) * dt * 0.8, 0.5, max(0.5, hz - 2))
        self.visitors = [g for g in self.visitors if -6 < g[0] < w + 6 and g[4] < 30]
        # splashes
        sp = []
        for d in self.splash:
            d[3] += 18 * dt
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[4] -= dt
            if d[4] > 0 and d[1] < self.surf(d[0]) + 0.3:
                sp.append(d)
        self.splash = sp
        # fish
        for s in self.schools:
            self.update_school(s, dt)
        # bubbles
        for vx in self.vents:
            if rng.random() < dt * 1.6:
                self.bubbles.append([vx + rng.uniform(-1, 1), self.bed[int(clamp(vx, 0, w - 1))] - 1, rng.uniform(0, TAU), rng.uniform(1.5, 3.5)])
        bb = []
        for b in self.bubbles:
            b[1] -= b[3] * dt
            b[0] += math.sin(t * 3 + b[2]) * dt * 0.8
            if b[1] > self.surf(b[0]) + 0.6:
                bb.append(b)
        self.bubbles = bb[-150:]
        # whale / turtle
        c = self.creature
        if c is None:
            self.creature_timer -= dt
            if self.creature_timer <= 0:
                self.spawn_creature()
        else:
            c[0] += c[2] * dt
            c[1] += math.sin(t * 0.4) * dt * 0.3
            if c[0] < -c[4] - 4 or c[0] > w + 4:
                self.creature = None
                self.creature_timer = rng.uniform(15, 35)
            elif c[3] == "whale" and rng.random() < dt * 1.5:
                self.bubbles.append([c[0] + (c[4] * 0.3 if c[2] > 0 else c[4] * 0.7), c[1], rng.uniform(0, TAU), 2.0])

    def spawn_creature(self):
        rng = self.rng
        w, h, hz = self.w, self.h, self.hz
        depth = self.bedtop() - hz
        kind = "whale" if (rng.random() < 0.5 and w >= 70 and depth >= 9) else "turtle"
        lines = WHALE if kind == "whale" else TURTLE
        d = rng.choice((-1, 1))
        if d < 0:
            lines = mirror(lines)
        sw = max(len(l) for l in lines)
        y = rng.uniform(hz + 2, max(hz + 2.5, self.bedtop() - len(lines) - 1))
        x = -sw - 1 if d > 0 else w + 1
        self.creature = [x, y, d * (2.2 if kind == "whale" else 3.2), kind, sw, lines]

    def update_pod(self, dt):
        rng = self.rng
        w, hz = self.w, self.hz
        if not self.pod:
            self.pod_timer -= dt
            if self.pod_timer > 0:
                return
            d = rng.choice((-1, 1))
            sp = rng.uniform(9, 13)
            gap = rng.uniform(0.45, 0.8)
            for k in range(self.pod_n):
                o = Dolphin()
                o.x = (-8 - k * sp * gap) if d > 0 else (w + 8 + k * sp * gap)
                o.cruise = hz + rng.uniform(1.6, 3.2)
                o.y = o.cruise
                o.vx = d * sp
                o.vy = 0.0
                o.air = False
                o.trail = []
                o.next_leap = rng.uniform(0.6, 1.6)
                o.phase = rng.uniform(0, TAU)
                o.len = rng.randint(5, 7) if w >= 80 else 4
                o.delay = k * gap
                self.pod.append(o)
            self.leap_rhythm = rng.uniform(1.6, 3.0)
            return
        alive = []
        for o in self.pod:
            sy = self.surf(o.x)
            if o.air:
                o.vy += 16.0 * dt
                if o.y > sy and o.vy > 0:
                    o.air = False
                    self.make_splash(o.x, sy, o.vx, 8)
            else:
                o.next_leap -= dt
                if o.next_leap <= 0 and o.y < o.cruise + 0.6:
                    o.vy = -rng.uniform(13.0, 16.5)
                    o.next_leap = self.leap_rhythm + rng.uniform(-0.3, 0.6)
                elif o.vy > -5:
                    # spring back to cruising depth with a gentle undulation
                    target = o.cruise + 0.5 * math.sin(self.t * 2 + o.phase)
                    o.vy += ((target - o.y) * 6.0 - o.vy * 3.0) * dt
            wasbelow = o.y > sy
            o.x += o.vx * dt
            o.y += o.vy * dt
            sy2 = self.surf(o.x)
            if wasbelow and o.y < sy2 and o.vy < 0 and not o.air:
                o.air = True
                self.make_splash(o.x, sy2, o.vx, 6)
            o.trail.append((o.x, o.y))
            if len(o.trail) > 40:
                del o.trail[0]
            if -14 < o.x < w + 14 or (o.vx > 0 and o.x < 0) or (o.vx < 0 and o.x > w):
                if (o.vx > 0 and o.x > w + 12) or (o.vx < 0 and o.x < -12):
                    continue
                alive.append(o)
        self.pod = alive
        if not alive:
            self.pod_timer = rng.uniform(6, 16)
            self.pod_n = rng.randint(1, 5)

    def make_splash(self, x, y, vx, n):
        rng = self.rng
        for _ in range(n):
            self.splash.append([x + rng.uniform(-1, 1), y - 0.2, vx * 0.15 + rng.uniform(-3, 3), -rng.uniform(4, 9),
                                rng.uniform(0.5, 1.0)])

    def update_school(self, s, dt):
        rng = self.rng
        w, hz = self.w, self.hz
        sp = s["sp"]
        fish = s["fish"]
        n = len(fish)
        if not n:
            return
        s["timer"] -= dt
        if s["timer"] <= 0:
            s["timer"] = rng.uniform(3, 8)
            s["tx"] = rng.uniform(-w * 0.1, w * 1.1)
            s["ty"] = rng.uniform(hz + 2, max(hz + 2.5, self.bedtop() - 1.5))
        cx = sum(f[0] for f in fish) / n
        cy = sum(f[1] for f in fish) / n
        avx = sum(f[2] for f in fish) / n
        speed = sp["sp"]
        tight = sp["tight"]
        tx, ty = s["tx"], s["ty"]
        lo, hi = hz + 1.5, None
        ptr = self.pointer
        if ptr is not None and ptr[1] < hz:
            ptr = None              # only a hand in the water scares fish
        for i, f in enumerate(fish):
            ax = (tx - f[0]) * 0.25 + (cx - f[0]) * 0.6 * tight + (avx - f[2]) * 0.5
            ay = (ty - f[1]) * 0.5 + (cy - f[1]) * 0.8 * tight
            vmax = speed * 1.3
            vyl = 1.2
            if ptr is not None:
                dx, dy = f[0] - ptr[0], (f[1] - ptr[1]) * ASPECT
                d = math.hypot(dx, dy)
                if d < 12:
                    k = (12 - d) * 14.0 / max(d, 0.5)
                    ax += dx * k
                    ay += dy * k / ASPECT
                    vmax = speed * 3.0
                    vyl = 4.0
            for j in range(max(0, i - 4), min(n, i + 5)):
                if j == i:
                    continue
                g = fish[j]
                dx = f[0] - g[0]
                dy = (f[1] - g[1]) * ASPECT
                d2 = dx * dx + dy * dy
                if d2 < 9 and d2 > 1e-4:
                    k = (9 - d2) / 9 * 6.0
                    ax += dx / math.sqrt(d2) * k
                    ay += dy / math.sqrt(d2) * k * 0.4
            f[2] += ax * dt
            f[3] += ay * dt
            v = math.hypot(f[2], f[3] * ASPECT)
            if v > vmax:
                f[2] *= vmax / v
                f[3] *= vmax / v
            elif v < speed * 0.4 and v > 1e-6:
                f[2] *= speed * 0.4 / v
                f[3] *= speed * 0.4 / v
            f[3] = clamp(f[3], -vyl, vyl)
            f[0] += f[2] * dt
            f[1] += f[3] * dt
            xi = int(clamp(f[0], 0, w - 1))
            bot = self.bed[xi] - 1.2
            if f[1] < lo:
                f[1] = lo
                f[3] = abs(f[3])
            elif f[1] > bot:
                f[1] = bot
                f[3] = -abs(f[3])
            if abs(f[2]) > 0.5:
                f[4] = 1 if f[2] > 0 else -1
            if f[0] < -w * 0.3:
                f[0] = w * 1.2
            elif f[0] > w * 1.3:
                f[0] = -w * 0.2

    # ------------------------------------------------------------------ draw
    def boat_y(self, b):
        """Row of the boat's waterline (bottom hull row), bobbing on the wave under its middle."""
        mid = b.x + b.w * 0.5
        s = self.surf(mid)
        return int(s + 0.5 + 0.35 * math.sin(self.t * 1.3 + b.phase))

    def draw(self, cv):
        w, h, hz, t = self.w, self.h, self.hz, self.t
        if (cv.w, cv.h) != (w, h):
            return
        self.background(cv)
        put = cv.put
        pal = self.pal
        for x, y, b, ph in self.stars:
            if cv.lv[y * w + x] > 0.5:
                continue
            tw = b * (0.5 + 0.5 * math.sin(t * (1 + b) + ph))
            if tw > 0.25:
                put(x, y, "." if tw < 0.55 else "+" if tw > 0.85 else "·", scale((235, 240, 255), 0.35 + 0.65 * tw), level=0.3)
        self.draw_underwater(cv)
        # big creature, seaweed, fish, bubbles
        c = self.creature
        if c is not None:
            col = (90, 110, 150) if c[3] == "whale" else (90, 170, 110)
            col = mix(col, pal["water"][1], 0.25)
            for k, line in enumerate(c[5]):
                y = int(c[1]) + k
                for i, ch in enumerate(line):
                    if ch != " ":
                        xx = int(c[0]) + i
                        if 0 <= xx < w and self.surf(xx) + 0.6 < y < self.bed[xx]:
                            put(xx, y, ch, col if ch not in "o" else (230, 240, 255), level=0.7)
        self.draw_weeds(cv)
        self.draw_fish(cv)
        for x, y, ph, sp in self.bubbles:
            yy = y
            put(x, yy, "o" if sp > 2.8 else "°" if sp > 2.1 else ".", mix(pal["ray"], (255, 255, 255), 0.5), level=0.5)
        # dolphins under water first (dim), then the surface, then everything above
        self.draw_pod(cv, under=True)
        self.draw_surface(cv)
        self.draw_smoke(cv)
        for b in self.boats:
            self.draw_boat(cv, b)
        self.draw_pod(cv, under=False)
        for x, y, vx, vy, life in self.splash:
            put(x, y, "'" if vy < 0 else "." if life < 0.4 else ",", mix(pal["surf"], (255, 255, 255), 0.4), level=0.8)
        gc = pal["gull"]
        for x, y, vx, ph, age in self.visitors:
            fl = math.sin(t * 9 + ph)
            cv.text(int(x) - 1, int(y), "\\v/" if fl > 0.3 else "-v-" if fl > -0.3 else "/v\\", gc)
        for x, y, vx, ph, far in self.gulls:
            fl = math.sin(t * 7 + ph)
            if far:
                put(x, y, "v" if fl > 0 else "-", scale(gc, 0.8))
            else:
                s = "\\v/" if fl > 0.3 else "-v-" if fl > -0.3 else "/v\\"
                cv.text(int(x) - 1, int(y), s, gc)

    def draw_underwater(self, cv):
        w, h, hz, t = self.w, self.h, self.hz, self.t
        pal = self.pal
        rays = self.rays
        L = self.rayL
        rc = pal["ray"]
        put = cv.put
        bed = self.bed
        off = t * 1.1
        sl = 0.55 * self.raydir
        rch = "\\" if sl > 0 else "/"
        depth = max(1, self.bedtop() - hz)
        sunk = clamp(1.4 - abs(self.sx - w / 2) / w)
        lv = cv.lv
        for y in range(hz + 1, h):
            f = (y - hz) / depth
            fade = (1 - f) ** 1.3 if f < 1 else 0.0
            if fade < 0.04:
                continue
            base = int(-y * sl * 2.2 + off) + L
            for x in range(w):
                if y >= bed[x]:
                    continue
                r = rays[(x + base) % L] * (0.6 + 0.4 * math.sin((x + base) * 0.02 + t * 0.3))
                v = r * fade * 0.55 * sunk
                if v > 0.12 and v > lv[y * w + x]:
                    hsh = ((x * 73856093) ^ (y * 19349663)) & 7
                    if hsh < 3 + int(v * 6):
                        put(x, y, rch if v > 0.36 and hsh < 2 else "." if hsh & 1 else "'", scale(rc, 0.25 + 0.8 * v), level=v)
        # caustic shimmer just under the surface
        sc = pal["surf"]
        for y in range(hz + 1, min(h, hz + 3)):
            for x in range(w):
                s = math.sin(x * 0.7 + t * 2.1 + y) * math.sin(x * 0.23 - t * 1.3)
                if s > 0.55 and y > self.surf(x) + 0.5:
                    put(x, y, "~" if s > 0.75 else "-", scale(sc, 0.35 + 0.4 * s), level=0.3)

    def draw_surface(self, cv):
        w, t = self.w, self.t
        pal = self.pal
        sc = pal["surf"]
        gl = pal["sun"][2]
        put = cv.put
        prev = self.surf(-1)
        cur = self.surf(0)
        for x in range(w):
            nxt = self.surf(x + 1)
            iy = int(cur)
            fr = cur - iy
            sl = (nxt - prev) * 0.5
            ch = "/" if sl < -0.45 else "\\" if sl > 0.45 else ("~" if fr < 0.33 else "-" if fr < 0.66 else "_")
            near = math.exp(-abs(x - self.sx) / (self.sr * 2.2))
            glint = near * (0.5 + 0.5 * math.sin(x * 1.9 + t * 3.3))
            col = mix(sc, gl, clamp(glint * 1.2))
            put(x, iy, ch, scale(col, 0.75 + 0.25 * glint), level=0.9)
            if (x + int(t * 3)) % 4 == 0:
                put(x, iy + 1, "-", scale(sc, 0.3), level=0.2)
            # sun glitter on the water right under the surface
            if near > 0.3 and glint > 0.5:
                put(x, iy + 1, "=" if glint > 0.75 else "-", scale(gl, 0.4 + 0.5 * glint), level=0.6)
            prev, cur = cur, nxt

    def draw_boat(self, cv, b):
        pal = self.pal
        bc = pal["boat"]
        put = cv.put
        far = b.kind.startswith("far")
        y0 = self.boat_y(b) - b.hh + 1
        x0 = int(b.x)
        lights = pal["lights"]
        hz = self.hz
        haze = 0.0 if not far else 0.35
        sky_h = pal["sky"][-1]
        hullc = bc["hull"] if b.col < 0.5 else bc["hull2"]
        sun_side = 1 if self.sx > b.x + b.w / 2 else -1
        for k, line in enumerate(b.lines):
            y = y0 + k
            is_hull = k >= b.hh - b.hull
            for i, ch in enumerate(line):
                if ch == " ":
                    continue
                x = x0 + i
                if far:
                    col = mix(bc["far"], sky_h, haze)
                elif is_hull:
                    col = bc["win"] if ch == "o" else hullc
                    if ch == "o" and not lights:
                        col = mix(hullc, (255, 255, 255), 0.5)
                elif ch == "|" or ch == "_":
                    col = bc["mast"]
                elif ch == ":":
                    col = bc["sail"]
                elif ch in "#=":
                    col = bc["funnel"]
                elif ch == "o":
                    col = bc["win"] if lights else mix(bc["sail"], (40, 60, 90), 0.6)
                else:
                    col = bc["edge"] if ((ch == "/") == (sun_side < 0) or ch in "()") else mix(bc["edge"], bc["sail"], 0.5)
                put(x, y, ch, col, level=0.9)
        if lights and not far:
            # a masthead light
            for i, ch in enumerate(b.lines[0]):
                if ch == "|":
                    if math.sin(self.t * 2 + b.phase) > -0.6:
                        put(x0 + i, y0 - 1, "*", (255, 240, 180), level=1.0)
                    break

    def draw_smoke(self, cv):
        put = cv.put
        night = self.pal["moon"]
        for x, y, vx, age, life, depth in self.smoke:
            f = age / life
            col = mix((170, 165, 175) if not night else (100, 105, 130), self.pal["sky"][-1], f * 0.7)
            ch = "o" if f < 0.12 else "O" if f < 0.3 else "o" if f < 0.55 else "°" if f < 0.75 else "."
            put(x + math.sin(age * 2 + depth * 9) * f, y, ch, scale(col, 0.95 - 0.5 * f), level=0.4)

    def draw_weeds(self, cv):
        put = cv.put
        t = self.t
        bed = self.bed
        w = self.w
        for x, hgt, ph, sp, col in self.weeds:
            yb = bed[int(x)]
            n = int(hgt)
            px = x
            for k in range(n):
                f = (k + 1) / max(1, n)
                sw = math.sin(t * sp + ph - k * 0.35) * (0.4 + 2.2 * f) + 0.6 * math.sin(t * 0.4 + ph) * f
                xx = x + sw
                y = int(yb) - 1 - k
                d = xx - px
                ch = "(" if d < -0.2 else ")" if d > 0.2 else ("}" if k % 2 else "{")
                if k == n - 1:
                    ch = "'"
                c = scale(col, 0.55 + 0.45 * f)
                put(xx, y, ch, c, level=0.6)
                px = xx

    def draw_fish(self, cv):
        put = cv.put
        w = self.w
        night = self.pal["moon"]
        t = self.t
        for s in self.schools:
            g = s["sp"]["g"]
            gl = g[::-1].translate(MIRROR)
            col = s["col"]
            if night:
                col = mix(col, (40, 60, 110), 0.35)
            n = len(g)
            for k, f in enumerate(s["fish"]):
                x, y = f[0], f[1]
                xi, yi = int(x), int(y)
                glyphs = g if f[4] > 0 else gl
                xs = xi - n + 1 if f[4] > 0 else xi
                shimmer = 0.8 + 0.2 * math.sin(t * 4 + k * 1.7)
                c = scale(col, shimmer)
                for i, ch in enumerate(glyphs):
                    xx = xs + i
                    if 0 <= xx < w and yi > self.surf(xx) + 0.5:
                        put(xx, yi, ch, c, level=0.7)

    def draw_pod(self, cv, under):
        pal = self.pal
        put = cv.put
        w = self.w
        dc, belly = pal["dolphin"], pal["belly"]
        for o in self.pod:
            tr = o.trail
            if len(tr) < 2:
                continue
            # body points spaced ~1 visual unit apart, walking back along the trail
            pts = [tr[-1]]
            acc = 0.0
            for j in range(len(tr) - 1, 0, -1):
                ax, ay = tr[j]
                bx, by = tr[j - 1]
                acc += math.hypot(ax - bx, (ay - by) * ASPECT)
                if acc >= 0.95:
                    pts.append((bx, by))
                    acc = 0.0
                    if len(pts) >= o.len:
                        break
            n = len(pts)
            right = o.vx > 0
            for i, (x, y) in enumerate(pts):
                xi, yi = int(x), int(y)
                if not (0 <= xi < w):
                    continue
                below = y > self.surf(x) + 0.3
                if below != under:
                    continue
                if i == 0:
                    ch = ">" if right else "<"
                elif i == n - 1:
                    ch = "<" if right else ">"
                else:
                    px, py = pts[i - 1]
                    dx, dy = px - x, (py - y) * ASPECT
                    if abs(dy) < abs(dx) * 0.45:
                        ch = "=" if i < n * 0.6 else "-"
                    else:
                        ch = "/" if (dx > 0) == (dy < 0) else "\\"
                c = mix(dc, belly, 0.35 if i == 0 else 0.0)
                if below:
                    c = mix(c, pal["water"][1], 0.45)
                put(xi, yi, ch, c, level=0.8)
                if i == max(1, n // 2 - 1) and not below:
                    put(xi, yi - 1, "^" if abs(o.vy) < 6 else ("/" if right else "\\"), dc, level=0.8)
