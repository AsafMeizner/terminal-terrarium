"""A bonsai that grows out of a glazed pot, sways in a breeze, sheds leaves and regrows.

This module also holds the small tree toolkit (branch walker, wood rasterizer, foliage
pads) that the sakura and seasons scenes reuse.
"""
import math

from ..engine import ASPECT, RAMPS, Scene, clamp, gradient, mix, noise2, scale

TAU = math.tau

# Foliage ramp used when the default ascii charset is active: leafier than " .:-=+*#%@".
LEAFY = " .,:;*o%&@"

LEAF_PALETTES = {
    "green": [(10, 40, 22), (26, 92, 44), (64, 156, 62), (150, 214, 96), (222, 250, 170)],
    "autumn": [(52, 16, 8), (140, 40, 16), (218, 96, 28), (255, 168, 56), (255, 226, 140)],
    "sakura": [(70, 22, 56), (168, 62, 118), (236, 124, 170), (255, 186, 212), (255, 236, 246)],
    "maple": [(48, 6, 14), (130, 18, 30), (210, 44, 44), (255, 104, 70), (255, 190, 140)],
    "gold": [(50, 36, 6), (130, 96, 14), (214, 170, 34), (255, 220, 90), (255, 248, 190)],
    "wisteria": [(34, 18, 64), (84, 48, 150), (148, 104, 222), (196, 166, 255), (240, 228, 255)],
}
BARK = [(30, 18, 12), (70, 42, 26), (122, 80, 48), (178, 128, 82), (220, 180, 130)]
GLAZES = [
    ((22, 48, 96), (70, 128, 200), (170, 210, 250)),     # cobalt
    ((90, 36, 20), (176, 86, 50), (236, 160, 110)),      # terracotta
    ((34, 70, 62), (96, 158, 136), (190, 232, 210)),     # celadon
    ((40, 40, 46), (110, 110, 122), (200, 200, 212)),    # slate
]

STEP = 0.5  # branch walk step, in visual units (x cells == y rows * ASPECT)


def wood_glyph(dx, dy):
    """Directional glyph for a branch moving dx cells and dy rows (dy < 0 is up)."""
    ady = abs(dy)
    if ady < 1e-6 or abs(dx) > ady * 2.4:
        return "_" if abs(dx) > ady * 4 else "~"
    r = dx / ady
    if abs(r) < 0.4:
        return "|"
    return "/" if (dx > 0) == (dy < 0) else "\\"


class Tree:
    """Wood segments and foliage pads, each element tagged with the time it is born."""

    def __init__(self, base_x, base_y):
        self.bx, self.by = base_x, base_y
        self.segs = []   # (points [(x, yv, r, t)], depth)
        self.pads = []   # dicts: cx, cy (cells), rx, ry, birth, phase, flex
        self.wood = []   # rasterized cells: (x, y, ch, light, birth, depth)
        self.end = 1.0   # time when everything has grown

    # -- building ---------------------------------------------------------------
    def walk(self, x, yv, ang, length, r0, r1, t0, steer, depth, flare=0.0):
        """Trace a branch from (x, yv) heading `ang` (0 = up, + = right). Returns its points."""
        n = max(2, int(length / STEP))
        pts = []
        t = t0
        for i in range(n + 1):
            f = i / n
            pts.append((x, yv, (r0 + (r1 - r0) * f) * (1 + flare * (1 - f) ** 6), t))
            ang = steer(f, ang, x, yv)
            x += math.sin(ang) * STEP
            yv += math.cos(ang) * STEP
            t += STEP
        self.segs.append((pts, depth))
        return pts

    def pad(self, x, yv, rx, ry, birth, rng, flex=1.0):
        self.pads.append({"cx": x, "cy": self.by - yv / ASPECT, "rx": rx, "ry": ry, "birth": birth,
                          "phase": rng.uniform(0, TAU), "flex": flex, "seed": rng.randrange(1 << 16)})

    # -- finishing --------------------------------------------------------------
    def finish(self, grow_secs, thicken=True):
        """Rescale birth times to `grow_secs` and rasterize the wood into cells."""
        wood_end = max((p[-1][3] for p, _ in self.segs), default=1.0) or 1.0
        pad_end = max((pd["birth"] for pd in self.pads), default=0.0)
        k = grow_secs * 0.78 / max(wood_end, pad_end * 0.95, 1e-6)
        for pd in self.pads:
            pd["birth"] *= k
        self.end = grow_secs
        cells = {}
        for pts, depth in self.segs:
            n = len(pts)
            for i, (x, yv, r, t) in enumerate(pts):
                t *= k
                a = pts[max(0, i - 1)]
                b = pts[min(n - 1, i + 1)]
                dx = b[0] - a[0]
                dy = -(b[1] - a[1]) / ASPECT
                ch = wood_glyph(dx, dy)
                sy = self.by - yv / ASPECT
                vertical = abs(dx) <= abs(dy) * 1.6
                rr = max(r, 0.5)
                span = (lambda: range(int(math.floor(x - rr)), int(math.floor(x + rr)) + 1)) if vertical else \
                    (lambda: range(int(math.floor(sy - rr / ASPECT)), int(math.floor(sy + rr / ASPECT)) + 1))
                for c in span():
                    if vertical:
                        cx, cy = c, int(math.floor(sy))
                        o = (c + 0.5 - x) / rr
                    else:
                        cx, cy = int(math.floor(x)), c
                        o = (c + 0.5 - sy) * ASPECT / rr
                    if abs(o) > 1.15:
                        continue
                    ao = min(1.0, abs(o))
                    # thickening: outer cells appear as the branch's girth grows
                    birth = t + (ao ** 2) * max(0.0, grow_secs - t) * 0.85 if thicken and r > 0.7 else t
                    light = 0.62 - 0.38 * o + 0.1 * noise2(cx * 0.9, cy * 0.4, 7)
                    glyph = ch
                    if vertical and r > 1.1 and ao < 0.55 and ch == "|":
                        glyph = "|" if (cx + cy // 3) % 3 else ":"
                    key = (cx, cy)
                    old = cells.get(key)
                    if old is None or ao < old[5] - 0.05:
                        cells[key] = [cx, cy, glyph, light, min(birth, old[4]) if old else birth, ao, depth]
                    elif birth < old[4]:
                        old[4] = birth
        self.wood = sorted(((c[0], c[1], c[2], clamp(c[3]), c[4], c[6]) for c in cells.values()),
                           key=lambda c: c[4])


def bake_pad(pd, w, h, bumpy=0.3, flat_light=False):
    """Precompute foliage cells for a pad: list of (ox, row, level, light, dist)."""
    cx, cy, rx, ry, seed = pd["cx"], pd["cy"], pd["rx"], pd["ry"], pd["seed"]
    out = []
    for y in range(int(cy - ry * 1.4) - 1, int(cy + ry * 1.4) + 2):
        if y < 0 or y >= h:
            continue
        for x in range(int(cx - rx * 1.3) - 1, int(cx + rx * 1.3) + 2):
            u = (x + 0.5 - cx) / rx
            v = (y + 0.5 - cy) / ry
            d = math.sqrt(u * u + v * v)
            n = noise2(x * 0.3, y * 0.6, seed)
            vv = v * 1.35 if v > 0 else v      # flatter underside, domed top
            d = math.sqrt(u * u + vv * vv)
            edge = d + n * bumpy
            if edge > 1.18:
                continue
            tex = noise2(x * 0.9, y * 1.5, seed + 3)
            if edge > 1.0:   # soft halo just outside the clump
                out.append((x + 0.5 - cx, y, 0.12 * (1.18 - edge) / 0.18, 0.15, d))
                continue
            light = 0.5 - 0.55 * v - 0.18 * u + 0.2 * tex
            if flat_light:
                light = 0.5 + 0.25 * tex - 0.2 * v
            core = clamp((1.0 - edge) / 0.22)
            level = clamp(0.4 + 0.5 * core + 0.22 * tex - 0.1 * max(0.0, v))
            out.append((x + 0.5 - cx, y, level, clamp(light), d))
    return out


def leaf_ramp(cv):
    return LEAFY if cv.ramp == RAMPS["ascii"] else cv.ramp


def draw_wood(cv, tree, T=1e9, fade=1.0, bark=BARK, lo=0.15, hi=0.75, tint=None, tint_k=0.0):
    """Draw a tree's rasterized wood cells born before time T."""
    put = cv.put
    for x, y, ch, light, birth, depth in tree.wood:
        if birth > T:
            break
        k = clamp((T - birth) * 2.5) * fade
        col = gradient(bark, lo + light * hi)
        if tint is not None:
            col = mix(col, tint, tint_k * light)
        put(x, y, ch, scale(col, k))


STYLES = ("informal", "formal", "slanting", "cascade", "windswept", "broom", "literati")


def bonsai_genome(rng, style):
    """Random growth rules for one tree. Each style narrows the ranges toward its classic form."""
    g = {
        "style": style,
        "trunk": rng.uniform(0.58, 0.74), "girth": rng.uniform(0.038, 0.058), "taper": rng.uniform(0.18, 0.34),
        "lean": rng.uniform(-0.3, 0.3), "amp": rng.uniform(0.35, 0.85), "freq": rng.uniform(0.8, 2.2),
        "ph": rng.uniform(0, TAU), "wiggle": rng.uniform(0.015, 0.06), "flare": rng.uniform(0.3, 0.9),
        "nbr": rng.randint(3, 6), "lo": rng.uniform(0.2, 0.4), "hi": rng.uniform(0.8, 0.94),
        "angle": rng.uniform(0.95, 1.42), "ajit": rng.uniform(0.04, 0.3), "droop": rng.uniform(-0.25, 0.75),
        "blen": rng.uniform(0.26, 0.5), "split": rng.uniform(0.25, 0.95), "split_angle": rng.uniform(0.3, 0.95),
        "pad": rng.uniform(0.12, 0.185), "flat": rng.uniform(0.25, 0.38), "midpad": rng.uniform(0.15, 0.9),
        "alternate": rng.random() < 0.75, "apex": rng.uniform(0.9, 1.35), "bumpy": rng.uniform(0.18, 0.4),
        "cone": rng.uniform(0.2, 0.7), "wind": 0, "jin": 0,
    }
    if style == "formal":
        g.update(lean=rng.uniform(-0.04, 0.04), amp=rng.uniform(0.02, 0.1), taper=rng.uniform(0.12, 0.2),
                 nbr=rng.randint(5, 8), lo=rng.uniform(0.15, 0.25), angle=rng.uniform(1.3, 1.6),
                 droop=rng.uniform(-0.1, 0.25), cone=rng.uniform(0.85, 1.1), alternate=True,
                 trunk=rng.uniform(0.7, 0.8))
    elif style == "slanting":
        g.update(lean=rng.choice((-1, 1)) * rng.uniform(0.32, 0.55), amp=rng.uniform(0.08, 0.3),
                 freq=rng.uniform(0.6, 1.2))
    elif style == "windswept":
        wd = rng.choice((-1, 1))
        g.update(wind=wd, lean=wd * rng.uniform(0.3, 0.6), amp=rng.uniform(0.1, 0.4), angle=rng.uniform(1.15, 1.5),
                 droop=rng.uniform(-0.2, 0.2), flat=rng.uniform(0.18, 0.26), blen=rng.uniform(0.4, 0.58),
                 jin=rng.randint(1, 3), midpad=rng.uniform(0.6, 1.0))
    elif style == "broom":
        g.update(trunk=rng.uniform(0.3, 0.4), lean=rng.uniform(-0.08, 0.08), amp=rng.uniform(0.02, 0.12),
                 nbr=rng.randint(5, 8), pad=rng.uniform(0.1, 0.14), flat=rng.uniform(0.32, 0.42))
    elif style == "literati":
        g.update(trunk=rng.uniform(0.76, 0.88), girth=rng.uniform(0.022, 0.034), amp=rng.uniform(0.6, 1.05),
                 freq=rng.uniform(1.4, 2.6), nbr=rng.randint(1, 3), lo=rng.uniform(0.66, 0.8),
                 pad=rng.uniform(0.09, 0.13), apex=rng.uniform(1.1, 1.4), taper=rng.uniform(0.3, 0.45))
    elif style == "cascade":
        g.update(amp=rng.uniform(0.05, 0.25), pad=rng.uniform(0.1, 0.14), nbr=rng.randint(3, 6))
    return g


def build_bonsai(rng, bx, by, rows, width, style="informal", pot_half=0.0, drop=0.0):
    """Grow a bonsai from a random genome. pot_half: half the pot width (cascades clear the rim);
    drop: rows below the soil a cascade may hang."""
    g = bonsai_genome(rng, style)
    tree = Tree(bx, by)
    tree.genome = g
    hv = rows * ASPECT
    half = width * 0.5
    wig = g["wiggle"]
    r0 = clamp(hv * g["girth"], 0.8, 5.5)
    lim = min(half * 0.6, hv * 0.5)

    if style == "cascade":
        return _cascade(tree, rng, g, bx, hv, r0, pot_half, drop)

    trunk_len = hv * g["trunk"]
    lean, amp, freq, ph = g["lean"], g["amp"], g["freq"], g["ph"]

    def trunk_steer(f, a, x, yv):
        target = lean + amp * math.sin(f * freq * math.pi + ph) * (1 - 0.4 * f)
        if abs(x - bx) > lim * 0.5:
            target -= clamp((x - bx) / max(lim, 1), -1, 1) * 0.9
        return a + (target - a) * 0.18 + rng.gauss(0, wig)

    trunk = tree.walk(bx, 0.0, lean, trunk_len, r0, max(0.5, r0 * g["taper"]), 0.0, trunk_steer, 0, g["flare"])
    _roots(tree, rng, bx, r0, trunk_len)
    pad_rx = clamp(hv * g["pad"], 2.4, 22)

    if style == "broom":
        x, yv, r, t = trunk[-1]
        n = g["nbr"]
        for k in range(n):
            a = (-1.0 + 2.0 * (k + 0.5) / n) * rng.uniform(0.75, 1.05)
            ln = hv * rng.uniform(0.22, 0.3) * (1.0 - 0.25 * abs(a))
            pts = tree.walk(x, yv, a * 0.6, ln, max(0.5, r * 0.6), 0.5, t,
                            lambda f, aa, x_, y_, a=a: aa + (a - aa) * 0.15 + rng.gauss(0, wig), 1)
            for j, frac in ((len(pts) - 1, 1.0), (len(pts) * 2 // 3, 0.7)):
                ex, eyv, _, et = pts[j]
                prx = pad_rx * rng.uniform(0.8, 1.15) * frac
                tree.pad(ex, eyv + prx * 0.2, prx, prx * g["flat"], et + 1.0, rng, 1.0 + abs(a) * 0.5)
        arx = pad_rx * 1.6
        tree.pad(x, yv + hv * 0.2, arx, arx * g["flat"] * 0.9, t + trunk_len * 0.4, rng, 1.2)
        return tree

    n_br = g["nbr"] if rows > 14 else min(g["nbr"], rng.randint(2, 4))
    side = rng.choice((-1, 1)) if not g["wind"] else g["wind"]
    lo, hi = g["lo"], g["hi"]
    for k in range(n_br):
        f = lo + (hi - lo) * (k + rng.uniform(0.2, 0.8)) / n_br
        if g["wind"]:
            side = g["wind"]
        elif not g["alternate"]:
            side = rng.choice((-1, 1))
        idx = min(len(trunk) - 1, int(f * (len(trunk) - 1)))
        x, yv, r, t = trunk[idx]
        shrink = 1.0 - g["cone"] * (f - lo) / max(0.01, hi - lo) * 0.6
        blen = hv * g["blen"] * rng.uniform(0.8, 1.15) * (1.2 - 0.6 * f) * shrink
        blen = min(blen, max(3.0, half * 0.85 - abs(x - bx)))
        base = side * clamp(g["angle"] + rng.gauss(0, g["ajit"]), 0.6, 1.75)
        ph2 = rng.uniform(0, TAU)
        droop = g["droop"]

        def br_steer(q, a, x_, yv_, s=side, base=base, ph2=ph2, droop=droop):
            target = base + s * 0.18 * math.sin(q * 4 + ph2) - s * droop * q * q
            return a + (target - a) * 0.25 + rng.gauss(0, wig * 1.5)

        pts = tree.walk(x, yv, base * 0.8, blen, max(0.5, r * 0.55), 0.5, t, br_steer, 1)
        tx, tyv, _, tt = pts[-1]
        prx = pad_rx * rng.uniform(0.75, 1.05) * (1.1 - 0.35 * f) * (0.55 + 0.45 * shrink)
        if g["wind"]:
            prx *= 1.25
        tree.pad(tx + side * prx * 0.15 * abs(g["wind"]), tyv + prx * 0.25, prx, prx * g["flat"], tt + 1.0, rng,
                 0.5 + f)
        if blen > 8 and rng.random() < g["midpad"]:   # a second cloud partway along the limb
            mx, myv, _, mt = pts[int(len(pts) * 0.55)]
            tree.pad(mx, myv + prx * 0.25, prx * 0.7, prx * g["flat"] * 0.85, mt + 1.0, rng, 0.4 + f)
        if blen > 6 and rng.random() < g["split"]:     # a secondary twig with its own small cloud
            j = int(len(pts) * rng.uniform(0.35, 0.6))
            sx, syv, sr, st = pts[j]
            sl = blen * rng.uniform(0.35, 0.55)
            sa = side * g["split_angle"] * rng.uniform(0.7, 1.2)
            spts = tree.walk(sx, syv, sa, sl, 0.5, 0.5, st,
                             lambda q, a, x_, yv_, sa=sa: a + (sa - a) * 0.2 + rng.gauss(0, wig * 1.5), 2)
            ex, eyv, _, et = spts[-1]
            srx = prx * rng.uniform(0.55, 0.75)
            tree.pad(ex, eyv + srx * 0.2, srx, srx * g["flat"], et + 1.0, rng, 0.6 + f)
        side = -side
    # jin: short bare dead stubs on the windward side
    for _ in range(g["jin"]):
        f = rng.uniform(0.35, 0.8)
        x, yv, r, t = trunk[int(f * (len(trunk) - 1))]
        a = -g["wind"] * rng.uniform(0.9, 1.4)
        tree.walk(x, yv, a, hv * rng.uniform(0.06, 0.12), 0.5, 0.5, t,
                  lambda q, aa, x_, y_, a=a: aa + (a - aa) * 0.2 + rng.gauss(0, 0.1), 2)
    # apex crown
    x, yv, r, t = trunk[-1]
    arx = pad_rx * g["apex"] * (0.7 if style == "formal" else 1.0)
    tree.pad(x + g["wind"] * arx * 0.25, yv + arx * 0.15, arx, arx * (g["flat"] + 0.04), t + 1.0, rng, 1.5)
    return tree


def _roots(tree, rng, bx, r0, trunk_len):
    """Surface roots spreading over the soil."""
    if r0 <= 1.2:
        return
    for side in (-1, 1):
        rl = r0 * rng.uniform(1.4, 2.8)
        tree.walk(bx + side * r0 * 0.6, 0.3, side * 1.75, rl, r0 * 0.45, 0.4, trunk_len * 0.6,
                  lambda f, a, x, yv, s=side: a + (s * 1.95 - a) * 0.2, 0)


def _cascade(tree, rng, g, bx, hv, r0, pot_half, drop):
    """Kengai: the trunk rises briefly, arches over the rim and falls below the pot."""
    side = rng.choice((-1, 1))
    up = hv * rng.uniform(0.12, 0.24)
    clear = pot_half + rng.uniform(1.5, 4.0)
    maxdrop = drop * ASPECT
    length = up * 1.3 + clear * 1.3 + up + maxdrop + 4
    state = {"over": False}

    def steer(f, a, x, yv):
        if not state["over"] and yv < up:
            target = side * (0.25 + g["amp"])
        elif abs(x - bx) < clear:
            state["over"] = True
            target = side * 1.6
        else:
            state["over"] = True
            target = side * (2.45 if maxdrop > 2 else 1.75)
        return a + (target - a) * 0.13 + rng.gauss(0, g["wiggle"])

    trunk = tree.walk(bx, 0.0, side * 0.2, length, r0, max(0.5, r0 * 0.3), 0.0, steer, 0, g["flare"])
    cut = len(trunk)
    for i, p in enumerate(trunk):
        if p[1] < -maxdrop:
            cut = i
            break
    del trunk[max(3, cut):]
    _roots(tree, rng, bx, r0, up)
    pad_rx = clamp(hv * g["pad"], 2.4, 16)
    n = g["nbr"]
    for k in range(n):
        f = 0.25 + 0.7 * (k + rng.uniform(0.2, 0.8)) / n
        x, yv, r, t = trunk[int(f * (len(trunk) - 1))]
        a = side * rng.uniform(-0.3, 0.9)
        ln = hv * rng.uniform(0.06, 0.13)
        pts = tree.walk(x, yv, a, ln, max(0.5, r * 0.5), 0.5, t,
                        lambda q, aa, x_, y_, a=a: aa + (a - aa) * 0.2 + rng.gauss(0, 0.05), 1)
        ex, eyv, _, et = pts[-1]
        prx = pad_rx * rng.uniform(0.75, 1.1)
        tree.pad(ex + side * prx * 0.2, eyv + prx * 0.2, prx, prx * g["flat"], et + 1.0, rng, 0.8 + f)
    # crown on the arch and a cloud at the falling tip
    top = max(trunk, key=lambda p: p[1])
    tree.pad(top[0], top[1] + pad_rx * 0.3, pad_rx * 1.15, pad_rx * g["flat"], top[3] + 1.0, rng, 0.8)
    ex, eyv, _, et = trunk[-1]
    tree.pad(ex, eyv, pad_rx * 0.9, pad_rx * g["flat"] * 1.1, et + 1.0, rng, 1.6)
    return tree


class Bonsai(Scene):
    name = "bonsai"
    title = "Bonsai"
    blurb = "a bonsai grows from its pot, sways, sheds leaves and regrows"
    tags = ("nature", "plants", "calm", "zen")
    options = {
        "speed": (1.0, "growth speed multiplier"),
        "style": ("random", "informal, formal, slanting, cascade, windswept, broom, literati or random"),
        "leaves": ("random", "green, autumn, sakura, maple, gold, wisteria or random"),
        "pot": (True, "draw the ceramic pot"),
        "grow": (True, "animate the first tree growing (false = start fully grown)"),
        "life": (45.0, "seconds a grown tree lives before it fades and regrows"),
        "fall": (1.0, "falling leaf amount"),
    }

    def setup(self):
        rng = self.rng
        self.has_pot = bool(self.opt("pot"))
        self.falling = []
        self.motes = [[rng.uniform(0, self.w), rng.uniform(0, self.h), rng.uniform(0.2, 1), rng.uniform(0, TAU)]
                      for _ in range(max(4, int(self.w * self.h / 260 * self.density)))]
        self.new_tree(first=True)

    # -- layout ----------------------------------------------------------------
    def layout(self, style):
        """Pot size, depth, wall shape and glaze are re-rolled for every tree."""
        rng = self.rng
        w, h = self.w, self.h
        self.glaze = rng.choice(GLAZES)
        self.pot_taper = rng.choice((1.0, 1.0, 0.5, 0.0))
        if not self.has_pot:
            self.pot = None
            return h - 2
        if style == "cascade":    # tall, narrow pot so the trunk can fall past it
            ph = int(clamp(round(h * rng.uniform(0.2, 0.28)), 3, 14))
            pw = int(clamp(min(w * rng.uniform(0.14, 0.2), h * 0.9), 8, 40))
            self.pot_taper = rng.choice((0.0, 0.5))
            cx = w // 2 + rng.choice((-1, 1)) * int(w * 0.08)
        else:
            ph = int(clamp(round(h * rng.uniform(0.09, 0.15)), 2, 8))
            pw = int(clamp(min(w * rng.uniform(0.24, 0.36), h * 1.7), 12, 90))
            cx = w // 2 + int(rng.uniform(-0.04, 0.04) * w)
        self.pot = (cx - pw // 2, cx - pw // 2 + pw - 1, h - 2 - ph, ph)  # x0, x1, rim row, height
        return h - 3 - ph

    def new_tree(self, first=False):
        rng = self.rng
        style = self.opt("style")
        if style not in STYLES:
            style = rng.choice(STYLES)
        soil = self.layout(style)
        self.soil = soil
        name = self.opt("leaves")
        if name not in LEAF_PALETTES:
            name = rng.choice(list(LEAF_PALETTES))
        self.pal = LEAF_PALETTES[name]
        rows = max(6, soil - 1)
        if self.pot:
            x0, x1, ry, ph = self.pot
            bx = (x0 + x1) / 2 + rng.uniform(-1.5, 1.5)
            pot_half, drop = (x1 - x0) / 2, ph + 1
        else:
            bx = self.w / 2 + rng.uniform(-0.1, 0.1) * self.w
            pot_half, drop = 0.0, 0.0
        if style == "cascade":
            rows = max(6, int(rows * 0.8))
        self.style = style
        self.tree = build_bonsai(rng, bx, soil + 0.6, rows, self.w, style, pot_half, drop)
        speed = max(0.05, self.opt("speed"))
        self.tree.finish(18.0 / speed)
        if self.pot:   # nothing grows through the pot itself
            x0, x1, ry, ph = self.pot
            self.tree.wood = [c for c in self.tree.wood if not (c[1] > soil and x0 - 1 <= c[0] <= x1 + 1)]
        bumpy = self.tree.genome["bumpy"]
        for pd in self.tree.pads:
            pd["cells"] = bake_pad(pd, self.w, self.h, bumpy)
        self.T = self.tree.end if (first and not self.opt("grow")) else 0.0
        self.fade = 1.0
        self.falling = [f for f in self.falling if f[5]]  # landed leaves linger

    # -- simulation --------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        self.T += dt
        tree = self.tree
        life = max(5.0, self.opt("life"))
        age = self.T - tree.end
        if age > life:
            self.fade = clamp(1 - (age - life) / 3.0)
            if self.fade <= 0:
                self.new_tree()
                return
        # falling leaves
        grown = self.T > tree.end * 0.9 and self.fade > 0.5
        rate = 0.5 * self.opt("fall") * (len(tree.pads) / 6) * (1 if grown else 0)
        if self.fade < 1:
            rate *= 4  # the old tree sheds as it fades
        if rate > 0 and self.rng.random() < rate * dt:
            pd = self.rng.choice(tree.pads)
            cells = pd["cells"]
            if cells:
                ox, y, lv, li, d = self.rng.choice(cells)
                if lv > 0.2:
                    self.falling.append([pd["cx"] + ox, y + 0.5, self.rng.uniform(0, TAU),
                                         self.rng.uniform(0.6, 1.2), gradient(self.pal, 0.3 + li * 0.6), False, 0.0])
        ground = self.h - 1.0
        for f in self.falling:
            if f[5]:
                f[6] += dt
                continue
            f[2] += dt * 2.0
            f[1] += dt * 1.6 * f[3]
            f[0] += math.sin(f[2]) * dt * 1.6 + self.wind() * dt * 0.8
            g = ground
            if self.pot and self.pot[0] <= f[0] <= self.pot[1]:
                g = self.pot[2]  # rests on the rim / soil
            if f[1] >= g:
                f[1] = g - 0.5
                f[5] = True
        self.falling = [f for f in self.falling if f[6] < 9 and 0 <= f[0] < self.w]
        for m in self.motes:
            m[1] -= dt * 0.25 * m[2]
            m[0] += math.sin(self.t * 0.3 + m[3]) * dt * 0.2
            if m[1] < 0:
                m[1] += self.h
                m[0] = self.rng.uniform(0, self.w)

    def wind(self):
        t = self.t
        return 0.6 * math.sin(t * 0.37) + 0.4 * math.sin(t * 0.83 + 1.3)

    # -- drawing ----------------------------------------------------------------
    def draw(self, cv):
        t, T = self.t, self.T
        fade = self.fade
        for mx, my, mz, mp in self.motes:
            cv.shade(mx, my, 0.06 + 0.1 * mz * (0.5 + 0.5 * math.sin(t * 1.5 + mp)), (200, 190, 140))
        if self.pot:
            self.draw_pot(cv)
        draw_wood(cv, self.tree, T, fade)
        self.draw_pads(cv, T, fade)
        for x, y, ph, sp, col, landed, age in self.falling:
            k = clamp(1 - (age - 6) / 3) if landed else 1.0
            ch = ".," [int(x) % 2] if landed else "',`." [int(ph * 1.3) % 4]
            cv.put(x, y, ch, scale(col, 0.9 * k))

    def draw_pads(self, cv, T, fade):
        ramp = leaf_ramp(cv)
        nr = len(ramp) - 1
        pal = self.pal
        t = self.t
        wind = self.wind()
        put = cv.put
        W, H = cv.w, cv.h
        for pd in self.tree.pads:
            age = T - pd["birth"]
            if age <= 0:
                continue
            bloom = age / 2.5
            cx = pd["cx"]
            flex = pd["flex"]
            ph = pd["phase"]
            for ox, y, lv, li, d in pd["cells"]:
                b = clamp((bloom - d * 0.7) * 3.0)
                if b <= 0:
                    continue
                sway = (wind * 0.45 + 0.35 * math.sin(t * 1.1 + ph + y * 0.35)) * flex * 0.7
                x = int(cx + ox + sway)
                if x < 0 or x >= W:
                    continue
                gust = 0.5 + 0.5 * math.sin(x * 0.18 - t * 1.6 + y * 0.3)
                v = lv * b * fade * (0.9 + 0.18 * gust)
                if v < 0.04:
                    continue
                idx = int(clamp(v) * nr + 0.5)
                if idx <= 0:
                    continue
                col = gradient(pal, li * (0.85 + 0.25 * gust))
                put(x, y, ramp[idx], scale(col, (0.35 + 0.65 * clamp(v)) * fade))

    def draw_pot(self, cv):
        x0, x1, ry, ph = self.pot
        dark, mid, light = self.glaze
        w = x1 - x0
        # soil mound with a little moss
        for x in range(x0 + 1, x1):
            u = (x - x0) / max(1, w)
            n = noise2(x * 0.7, 3.1, 11)
            ch = "~.,:'"[int((n + 1) * 2.4) % 5]
            col = mix((70, 46, 30), (70, 130, 56), clamp(n * 1.5)) if n > 0.25 else (92, 64, 40)
            cv.put(x, ry - 1, ch, scale(col, 0.4 + 0.6 * clamp(1 - abs(u - 0.5) * 1.6)))
        # rim: a glossy lip
        for x in range(x0, x1 + 1):
            u = (x - x0) / max(1, w)
            col = gradient([light, mid, dark], clamp(abs(u - 0.25) * 1.4))
            ch = "(" if x == x0 else ")" if x == x1 else "="
            cv.put(x, ry, ch, col)
        # body: tapered bowl lit from the left, with a wave band under the rim
        for k in range(1, ph):
            y = ry + k
            lx, rx = x0 + int(k * self.pot_taper + 0.5), x1 - int(k * self.pot_taper + 0.5)
            last = k == ph - 1
            for x in range(lx, rx + 1):
                u = (x - lx) / max(1, rx - lx)
                shade = clamp(1.0 - abs(u - 0.28) * 1.45)
                col = gradient([scale(dark, 0.7), mid, light], shade)
                if x == lx:
                    ch = "\\" if self.pot_taper > 0.7 or (self.pot_taper > 0 and k % 2) else "|"
                elif x == rx:
                    ch = "/" if self.pot_taper > 0.7 or (self.pot_taper > 0 and k % 2) else "|"
                elif last:
                    ch = "_"
                elif k == 1 and ph > 3:
                    ch = "~" if x % 2 else "-"
                    col = mix(col, light, 0.25)
                else:
                    ch = "░"
                cv.put(x, y, ch, col)
        # feet
        fy = ry + ph
        inset = int(ph * self.pot_taper + 0.5)
        for fx in (x0 + inset + 1, x1 - inset - 2):
            cv.text(fx, fy, "[]", scale(dark, 1.4))
        # table line
        ty = min(self.h - 1, fy + 1)
        cxm = (x0 + x1) / 2
        for x in range(max(0, int(cxm - w)), min(self.w, int(cxm + w) + 1)):
            dd = abs(x - cxm) / max(1, w)
            cv.put(x, ty, "_", scale((110, 86, 66), clamp(1.0 - dd)))
