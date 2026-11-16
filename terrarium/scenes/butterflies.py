"""Big, detailed butterflies and moths fluttering through a night garden, landing on flowers.

Every insect has its own genome: wing outline (rounded, falcate, swallowtailed, scalloped),
and a pattern composed from veins, edge bands with dots, apex patches, stripes, colour bands
and eyespots. The pattern is baked once into a small half-wing texture; each frame the texture
is foreshortened by the wingbeat angle (cos for width, sin for a little lift) so the flap reads
in 2D, lit by the angle, and mirrored for the other side.
"""
import math

from ..engine import ASPECT, Scene, clamp, hsv, mix, noise1, noise2, scale, smoothstep

TAU = math.tau
FAMILIES = ("monarch", "morpho", "swallowtail", "moth", "admiral", "jewel")
BLACK = (66, 46, 60)
WHITE = (250, 246, 236)

# half-wing texture: x 0..XM (out from the body), y YB..YT (up), units of the half-span R
XM, YB, YT, STEP = 1.25, -1.6, 1.1, 0.035
TX = int(XM / STEP) + 1
TY = int((YT - YB) / STEP) + 1


def _slope_ch(dx, dy):
    """Line glyph for a direction in cell units (dy down)."""
    ax, ay = abs(dx), abs(dy * ASPECT)
    if ax > 2.2 * ay:
        return "-"
    if ay > 2.2 * ax:
        return "|"
    return "\\" if dx * dy > 0 else "/"


def _jit(rng, c, k=24):
    return tuple(clamp(v + rng.uniform(-k, k), 0, 255) for v in c)


# --------------------------------------------------------------------------- genomes

def _curve(knots, n=160):
    """Smooth radius-vs-angle profile through (theta, r) knots (Catmull-Rom), as a lookup table."""
    knots = sorted(knots)
    lo, hi = knots[0][0], knots[-1][0]
    ths = [k[0] for k in knots]
    rs = [k[1] for k in knots]
    m = len(knots)
    tang = []
    for i in range(m):
        a, b = max(0, i - 1), min(m - 1, i + 1)
        tang.append((rs[b] - rs[a]) / (ths[b] - ths[a] or 1))
    lut = []
    j = 0
    for k in range(n + 1):
        th = lo + (hi - lo) * k / n
        while j < m - 2 and th > ths[j + 1]:
            j += 1
        d = ths[j + 1] - ths[j] or 1
        u = clamp((th - ths[j]) / d)
        u2, u3 = u * u, u * u * u
        r = ((2 * u3 - 3 * u2 + 1) * rs[j] + (u3 - 2 * u2 + u) * d * tang[j]
             + (-2 * u3 + 3 * u2) * rs[j + 1] + (u3 - u2) * d * tang[j + 1])
        lut.append(max(0.0, r))
    return lo, hi, lut


def _prof(curve, th):
    """(radius, s) of a wing profile at angle th; s is 0..1 across the wing, radius 0 outside."""
    lo, hi, lut = curve
    if th < lo or th > hi:
        return 0.0, -1.0
    s = (th - lo) / (hi - lo)
    f = s * (len(lut) - 1)
    i = int(f)
    if i >= len(lut) - 1:
        return lut[-1], 1.0
    return lut[i] + (lut[i + 1] - lut[i]) * (f - i), s


def _shape(rng, g, style):
    """Wing outlines from a few rolled numbers. style: round, pointed, swallow, moth, luna, morpho."""
    J = lambda a, b: rng.uniform(a, b)
    apex_th = J(0.45, 0.62)
    apex_r = J(1.0, 1.08)
    costa_th = apex_th + J(0.25, 0.34)
    tor_th = J(-0.42, -0.3)
    tor_r = J(0.58, 0.7)
    bulge = J(0.98, 1.06)
    h_r = J(0.8, 0.9)
    h_peak = J(-1.05, -0.8)
    h_lo = J(-1.75, -1.6)
    if style == "pointed":            # monarch-like: long forewing, crisp apex
        apex_r *= 1.05
        bulge = J(0.9, 0.97)
    elif style == "morpho":           # broad and blunt
        apex_th = J(0.3, 0.42)
        bulge = J(1.05, 1.12)
        h_r = J(0.8, 0.9)
        tor_r = J(0.66, 0.74)
    elif style == "swallow":
        apex_r *= J(1.05, 1.12)
        tor_r = J(0.55, 0.62)
        h_r = J(0.72, 0.8)
        h_peak = J(-0.95, -0.75)
    elif style in ("moth", "luna"):    # swept-back triangle, small hindwing
        apex_th = J(0.18, 0.36)
        costa_th = apex_th + J(0.42, 0.55)
        tor_th = J(-0.5, -0.38)
        tor_r = J(0.62, 0.72)
        bulge = J(0.96, 1.04)
        h_r = J(0.6, 0.7) if style == "moth" else J(0.66, 0.74)
        h_peak = J(-0.85, -0.6)
    fore = [(tor_th - 0.12, tor_r * 0.55), (tor_th, tor_r),
            ((tor_th + apex_th) / 2, (tor_r + apex_r) / 2 * bulge), (apex_th, apex_r),
            (apex_th + (costa_th - apex_th) * 0.45, apex_r * 0.86),
            (apex_th + (costa_th - apex_th) * 0.8, apex_r * 0.52), (costa_th, 0.02)]
    hind = [(0.05, 0.3), (-0.2, 0.5), (-0.5, h_r * 0.9), (h_peak, h_r), (h_peak - 0.3, h_r * 0.95),
            (-1.42, h_r * 0.72), (-1.6, h_r * 0.42), (h_lo, 0.04)]
    g["fore"] = _curve(fore)
    g["hind"] = _curve(hind)
    g["hind_lo"] = h_lo
    g["h_r"] = h_r
    g["tail_th"] = J(-1.42, -1.2) if style != "luna" else J(-1.48, -1.38)
    g["tail_w"] = J(0.06, 0.09) if style != "luna" else J(0.1, 0.14)


def _genome(rng, family):
    """Roll a wing shape + pattern. Everything here is a dice roll inside a family's style."""
    g = dict(family=family, veins=0, vein_col=BLACK, vein_k=0.0, border=0.0, border_col=BLACK,
             dots=0, dot_col=WHITE, dots2=False, apex=None, stripes=[], rings=[], eyes=[], noise=0.0,
             noise_col=None, irid=0.0, windows=0, glide=rng.uniform(0.1, 0.35), tail=0.0, scallop=0.0,
             antenna="club", fuzz=False, under=(120, 90, 70), sheen=rng.uniform(0.12, 0.3))
    g["body_col"] = (70, 55, 50)
    g["rate"] = rng.uniform(2.4, 3.4)        # wingbeats per second
    style = "round"

    if family == "monarch":
        hue = rng.choice((0.075, 0.08, 0.065, 0.09, 0.055))  # monarch / viceroy / queen / painted lady
        base = hsv(hue, rng.uniform(0.82, 0.95), 1.0)
        style = "pointed"
        g.update(root=scale(base, 0.7), mid=base, edge=mix(base, (255, 225, 120), 0.35),
                 veins=rng.choice((5, 6, 7)), vein_k=rng.uniform(0.75, 1.0), border=rng.uniform(0.16, 0.24),
                 dots=rng.choice((6, 7, 8)), dots2=rng.random() < 0.7,
                 apex=(rng.uniform(0.62, 0.72), rng.choice((2, 3)), rng.choice((WHITE, (255, 205, 100)))),
                 under=mix(base, (255, 230, 170), 0.3), glide=rng.uniform(0.3, 0.55))
        if rng.random() < 0.35:  # painted-lady flavour: blotches + hindwing eye row instead of veins
            g["veins"] = 0
            g["stripes"].append((0.75, 0.5, 0.07, BLACK))
            for k in range(rng.choice((2, 3))):
                g["eyes"].append(("h", 0.35 + 0.17 * k, 0.74, 0.07, [BLACK, (110, 170, 255), BLACK]))
    elif family == "morpho":
        hue = rng.uniform(0.53, 0.66)
        base = hsv(hue, rng.uniform(0.6, 0.85), 1.0)
        style = "morpho"
        g.update(root=hsv(hue + 0.04, 0.9, 0.6), mid=base, edge=hsv(hue - 0.04, 0.35, 1.0),
                 border=rng.uniform(0.14, 0.26), dots=rng.choice((0, 5, 6, 7)), dot_col=(235, 240, 255),
                 irid=rng.uniform(0.7, 1.0), veins=rng.choice((0, 0, 6)), vein_k=0.3, vein_col=hsv(hue, 0.8, 0.5),
                 under=(150, 110, 70), glide=rng.uniform(0.25, 0.5))
        if rng.random() < 0.5:
            g["apex"] = (rng.uniform(0.7, 0.8), rng.choice((2, 3)), WHITE)
    elif family == "swallowtail":
        style = "swallow"
        kind = rng.choice(("tiger", "tiger", "black", "zebra", "emerald"))
        if kind == "tiger":
            base = hsv(rng.uniform(0.12, 0.15), rng.uniform(0.6, 0.8), 1.0)
            g.update(root=scale(base, 0.85), mid=base, edge=mix(base, WHITE, 0.3))
            n = rng.choice((3, 4, 5))
            ang = rng.uniform(1.0, 1.3)
            for k in range(n):
                g["stripes"].append((ang, 0.08 + k * rng.uniform(0.15, 0.2), rng.uniform(0.04, 0.065), BLACK))
            g["dot_col"] = base
        elif kind == "zebra":
            base = (236, 244, 255)
            g.update(root=(200, 215, 235), mid=base, edge=base)
            for k in range(rng.choice((5, 6, 7))):
                g["stripes"].append((1.2, 0.06 + k * 0.15, 0.045, BLACK))
            g["dot_col"] = (255, 120, 90)
        elif kind == "emerald":
            base = hsv(rng.uniform(0.38, 0.47), 0.8, 1.0)
            g.update(root=BLACK, mid=(60, 50, 60), edge=BLACK, irid=0.4)
            g["rings"].append(("f", 0.32, 0.66, base))
            g["rings"].append(("h", 0.28, 0.66, base))
            g["dot_col"] = base
        else:  # black swallowtail: dark with rows of yellow spots
            base = hsv(rng.uniform(0.12, 0.16), 0.75, 1.0)
            g.update(root=BLACK, mid=(64, 50, 58), edge=BLACK)
            g["rings"].append(("f", 0.66, 0.76, base))
            g["rings"].append(("h", 0.52, 0.66, base))
            g["dot_col"] = base
        g.update(border=rng.uniform(0.16, 0.24), dots=rng.choice((5, 6, 7)), veins=rng.choice((0, 6)),
                 vein_k=0.5, tail=rng.uniform(0.32, 0.5), scallop=rng.uniform(0.05, 0.09),
                 under=mix(base, WHITE, 0.3))
        g["eyes"].append(("h", 0.16, 0.8, 0.09, [(255, 120, 40), BLACK]))
        g["eyes"].append(("h", 0.36, 0.84, 0.075, [(90, 150, 255), BLACK]))
    elif family == "moth":
        kind = rng.choice(("luna", "rosy", "atlas", "sphinx", "io"))
        style = "luna" if kind == "luna" else "moth"
        g.update(antenna="feather", fuzz=True, glide=0.0, rate=rng.uniform(3.2, 4.0), noise=rng.uniform(0.15, 0.3))
        if kind == "luna":
            base = hsv(rng.uniform(0.25, 0.33), rng.uniform(0.3, 0.5), 1.0)
            g.update(root=(250, 250, 235), mid=base, edge=mix(base, (255, 210, 120), 0.5),
                     tail=rng.uniform(0.7, 0.95), body_col=(240, 240, 225), under=base, noise=0.08)
            eye = [(250, 230, 150), (190, 90, 150), (60, 40, 50)]
            g["eyes"].append(("f", 0.62, 0.5, 0.09, eye))
            g["eyes"].append(("h", 0.55, 0.45, 0.1, eye))
        elif kind == "rosy":
            pink, yel = hsv(rng.uniform(0.9, 0.97), 0.55, 1.0), hsv(rng.uniform(0.13, 0.16), 0.55, 1.0)
            g.update(root=pink, mid=yel, edge=pink, body_col=(255, 230, 140), under=pink, noise=0.05)
            g["rings"].append(("f", 0.32, 0.72, yel))
            g["rings"].append(("f", 0.0, 0.32, pink))
            g["rings"].append(("h", 0.0, 1.01, mix(pink, yel, 0.65)))
        elif kind == "atlas":
            base = hsv(rng.uniform(0.0, 0.06), rng.uniform(0.6, 0.8), rng.uniform(0.85, 0.95))
            g.update(root=scale(base, 0.75), mid=base, edge=(235, 205, 130),
                     windows=rng.choice((1, 2)), border=0.12, border_col=(225, 195, 125), under=base)
            g["rings"].append(("f", 0.6, 0.67, (250, 240, 220)))
            g["rings"].append(("h", 0.55, 0.63, (250, 240, 220)))
            g["eyes"].append(("f", 0.9, 0.86, 0.08, [(255, 220, 150), BLACK, (230, 100, 80)]))
        elif kind == "io":
            base = hsv(rng.uniform(0.11, 0.15), 0.75, 1.0)
            g.update(root=scale(base, 0.8), mid=base, edge=mix(base, (200, 120, 60), 0.5), under=base)
            g["eyes"].append(("h", 0.5, 0.55, 0.17, [BLACK, (120, 160, 255), BLACK, (255, 250, 250)]))
            g["rings"].append(("h", 0.82, 1.01, (220, 90, 70)))
        else:  # sphinx / hawk moth: grey-brown with wavy lines and a pink hindwing
            base = hsv(rng.uniform(0.05, 0.1), rng.uniform(0.15, 0.3), rng.uniform(0.8, 0.92))
            g.update(root=scale(base, 0.8), mid=base, edge=mix(base, WHITE, 0.25), noise=0.4, under=base)
            g["rings"].append(("h", 0.2, 0.78, hsv(rng.uniform(0.93, 1.0), 0.6, 1.0)))
            g["rings"].append(("f", 0.42, 0.48, scale(base, 0.45)))
            g["rings"].append(("f", 0.74, 0.8, scale(base, 0.45)))
        g["noise_col"] = scale(g["mid"], 0.6)
    elif family == "admiral":
        band = rng.choice(((255, 110, 50), (255, 70, 70), (255, 240, 240), (255, 170, 40), (120, 220, 255)))
        style = rng.choice(("round", "pointed"))
        g.update(root=BLACK, mid=(70, 52, 60), edge=(70, 52, 60), dots=rng.choice((0, 5, 6)), dot_col=WHITE,
                 border=rng.uniform(0.0, 0.1))
        g["stripes"].append((rng.uniform(0.2, 0.5), rng.uniform(0.45, 0.55), rng.uniform(0.08, 0.11), band))
        g["rings"].append(("h", 0.8, 0.93, band))
        g["apex"] = (rng.uniform(0.7, 0.8), rng.choice((2, 3)), WHITE)
        g["under"] = (130, 100, 110)
    else:  # jewel: a fantasy two-tone with eyespots, every hue is fair game
        style = rng.choice(("round", "pointed", "morpho", "swallow"))
        h0 = rng.random()
        h1 = h0 + rng.choice((0.08, 0.15, 0.5, -0.12))
        c0, c1 = hsv(h0, rng.uniform(0.55, 0.85), 1.0), hsv(h1, rng.uniform(0.5, 0.85), 1.0)
        g.update(root=scale(c0, 0.6), mid=c0, edge=c1, border=rng.uniform(0.0, 0.2),
                 dots=rng.choice((0, 6, 8)), irid=rng.uniform(0.0, 0.6), veins=rng.choice((0, 6)),
                 vein_k=0.35, vein_col=scale(c0, 0.4), under=mix(c0, c1, 0.5))
        if rng.random() < 0.7:
            rc = [BLACK, hsv(h1 + 0.5, 0.6, 1.0), WHITE]
            g["eyes"].append(("f", rng.uniform(0.55, 0.7), rng.uniform(0.6, 0.72), rng.uniform(0.09, 0.12), rc))
            g["eyes"].append(("h", rng.uniform(0.4, 0.6), rng.uniform(0.55, 0.68), rng.uniform(0.1, 0.14), rc))
        if style == "swallow":
            g["tail"] = rng.uniform(0.25, 0.45)
            g["scallop"] = rng.uniform(0.03, 0.07)
    _shape(rng, g, style)
    for key in ("root", "mid", "edge"):
        g[key] = _jit(rng, g[key], 12)
    return g


def _wing_r(g, wing, th):
    if wing == "f":
        return _prof(g["fore"], th)
    r, s = _prof(g["hind"], th)
    if r <= 0:
        return r, s
    if g["scallop"]:
        r *= 1 - g["scallop"] * abs(math.sin(s * 8 * math.pi))
    if g["tail"]:
        d = abs(th - g["tail_th"]) / g["tail_w"]
        if d < 1:
            r += g["tail"] * (1 - d * d) ** 0.7
    return r, s


def _bake(g, rng):
    """Bake the half-wing pattern into a texture of (v, rgb, rho) or None per texel."""
    tex = [None] * (TX * TY)
    seed = rng.randrange(1 << 16)
    dots = g["dots"]
    windows = [(rng.uniform(0.35, 0.55), rng.uniform(0.0, 0.2), rng.uniform(0.07, 0.1)) for _ in range(g["windows"])]
    eyes = []
    for w, es, er, rad, rings in g["eyes"]:
        lo, hi, _ = g["fore"] if w == "f" else g["hind"]
        tt = lo + es * (hi - lo)
        rr = _prof(g["fore"] if w == "f" else g["hind"], tt)[0] * er
        eyes.append((w, rr * math.cos(tt), rr * math.sin(tt), rad, rings))
    for iy in range(TY):
        y = YB + (iy + 0.5) * STEP
        for ix in range(TX):
            x = (ix + 0.5) * STEP
            th = math.atan2(y, x)
            r = math.hypot(x, y)
            rf, s = _wing_r(g, "f", th)
            wing = "f"
            if r > rf:
                rh, s = _wing_r(g, "h", th)
                if r > rh:
                    continue
                wing, rho = "h", r / max(rh, 1e-6)
                if g["tail"] and abs(th - g["tail_th"]) < g["tail_w"] and r > g["h_r"] * 0.85:
                    rho = max(rho, 0.9)  # the tail itself reads as margin
            else:
                rho = r / max(rf, 1e-6)
            if rho < 0.5:
                col = mix(g["root"], g["mid"], smoothstep(0.0, 0.5, rho))
            else:
                col = mix(g["mid"], g["edge"], smoothstep(0.5, 1.0, rho))
            v = 0.62 + 0.3 * smoothstep(0.0, 0.8, rho)
            for w, a, b, rc in g["rings"]:
                if w == wing and a <= rho <= b:
                    col = rc
            for ang, off, wid, sc in g["stripes"]:
                d = x * math.cos(ang) + y * math.sin(ang) - off
                if abs(d) < wid:
                    col = sc
                    v = 0.72 if sc is BLACK else 0.85
            if g["noise"]:
                n = noise2(x * 7, y * 7, seed)
                wave = math.sin(rho * 16 + noise2(x * 3, y * 3, seed + 1) * 3)
                if wave > 0.8:
                    col = mix(col, g["noise_col"], min(1.0, g["noise"] * 1.8))
                col = mix(col, g["noise_col"], g["noise"] * max(0.0, n))
            if g["veins"] and rho > 0.15:
                fr = (s * g["veins"]) % 1.0
                if min(fr, 1 - fr) * r * 2.4 < 0.07:
                    col = mix(col, g["vein_col"], g["vein_k"])
                    if g["vein_k"] > 0.6:
                        v = 0.72
                if wing == "f" and abs(rho - 0.5) < 0.04 and 0.3 < s < 0.75:
                    col = mix(col, g["vein_col"], g["vein_k"] * 0.8)
            if g["apex"] and wing == "f":
                a0, nsp, scol = g["apex"]
                if s > a0 and rho > 0.5:
                    col = BLACK
                    v = 0.72
                    for k in range(nsp):
                        ps = a0 + (1 - a0) * (k + 0.6) / (nsp + 0.6)
                        if (s - ps) ** 2 * 40 + (rho - 0.74) ** 2 * 50 < 0.12:
                            col = scol
                            v = 0.95
            if g["border"] and rho > 1 - g["border"]:
                col = g["border_col"]
                v = 0.72
                if dots:
                    band = (rho - (1 - g["border"])) / g["border"]
                    fr = (s * dots + (0.5 if wing == "h" else 0.0)) % 1.0
                    if (fr - 0.5) ** 2 * 2.2 + (band - 0.55) ** 2 * 1.2 < 0.09:
                        col = g["dot_col"]
                        v = 0.95
                    elif g["dots2"] and (fr - 0.5) ** 2 * 3 + (band - 0.12) ** 2 * 3 < 0.04:
                        col = g["dot_col"]
                        v = 0.9
            for w, ex, ey, rad, rings in eyes:
                if w != wing:
                    continue
                d = math.hypot(x - ex, y - ey) / rad
                if d < 1.0:
                    k = min(len(rings) - 1, int(d * len(rings)))
                    col = rings[len(rings) - 1 - k]
                    v = 0.95
                    if d < 0.2 and len(rings) >= 3:
                        col = mix(col, WHITE, 0.7)
            for wx, wy, wr in windows:
                if wing == "f" and (x - wx) ** 2 + (y - wy) ** 2 < wr * wr:
                    v = 0.35
                    col = mix(col, (255, 250, 230), 0.5)
            if rho > 0.94:
                v = min(v, 0.6)
            tex[iy * TX + ix] = (v, col, rho)
    return tex


# --------------------------------------------------------------------------- creatures

class Fly:
    def __init__(self, scene, depth, family, enter=False):
        rng = scene.rng
        self.depth = depth
        self.g = _genome(rng, family)
        self.tex = _bake(self.g, rng)
        big = min(scene.w, scene.h * ASPECT)
        moth = family == "moth"
        self.R = max(3.5, big * (0.1 + 0.11 * depth) * rng.uniform(0.9, 1.15) * (0.9 if moth else 1.0))
        w, h = scene.w, scene.h
        if enter:
            side = rng.choice((-1, 1))
            self.x = w / 2 + side * (w / 2 + self.R * 1.4)
            self.y = rng.uniform(h * 0.15, h * 0.6)
        else:
            self.x = rng.uniform(self.R, w - self.R)
            self.y = rng.uniform(h * 0.15, h * 0.65)
        self.vx = rng.uniform(-3, 3)
        self.vy = rng.uniform(-1, 1)
        self.phase = rng.uniform(0, TAU)
        self.seed = rng.randrange(1000)
        self.tilt = 0.0
        self.state = "fly"
        self.tx, self.ty = self.pick_target(scene)
        self.timer = rng.uniform(3, 7)
        self.glide = 0.0
        self.flower = None
        self.rest_phase = 0.0
        self.life = rng.uniform(25, 60)
        self.speed = rng.uniform(5, 9) * (0.6 + 0.6 * depth) * (1.25 if moth else 1.0)
        self.trail_t = 0.0
        self.phi = 0.0
        pal = [self.g["mid"], self.g["edge"], self.g.get("dot_col", WHITE)]
        self.trail_cols = [mix(c, WHITE, 0.35) for c in pal]

    def pick_target(self, scene):
        rng = scene.rng
        return rng.uniform(scene.w * 0.08, scene.w * 0.92), rng.uniform(scene.h * 0.08, scene.h * 0.62)


class Bloom:
    def __init__(self, rng, x, h, stem, kind, cols, size):
        self.x0 = x
        self.stem = stem          # stem length in rows
        self.base = h - 1
        self.kind = kind
        self.petal, self.center = cols
        self.r = size             # head radius (x cells)
        self.np = {"daisy": rng.choice((11, 13, 16)), "cosmos": 8, "cone": rng.choice((10, 12, 14)),
                   "zinnia": rng.choice((12, 14))}[kind]
        self.d0 = {"daisy": 0.28, "cosmos": 0.24, "cone": 0.34, "zinnia": 0.3}[kind] * rng.uniform(0.9, 1.1)
        self.pw = {"daisy": 0.13, "cosmos": 0.3, "cone": 0.17, "zinnia": 0.2}[kind] * rng.uniform(0.85, 1.15)
        self.droop = {"cone": rng.uniform(0.35, 0.6)}.get(kind, rng.uniform(0.0, 0.12))
        self.tilt = rng.uniform(0.62, 0.85)       # how much the face is turned up (vertical squash)
        self.phase = rng.uniform(0, TAU)
        self.bend = rng.uniform(-0.25, 0.25)
        self.rot = rng.uniform(0, TAU)
        self.leaves = [(rng.uniform(0.25, 0.7), rng.choice((-1, 1))) for _ in range(rng.randint(1, 3))]
        self.x, self.y = x, h - 1 - stem
        self.taken = False
        self.grow = 1.0           # < 1 while a clicked flower is still opening
        self.full = (stem, size)

    def update(self, t):
        sway = 0.9 * math.sin(t * 0.6 + self.phase) + 0.4 * noise1(t * 0.3 + self.phase * 5)
        self.x = self.x0 + (self.bend * self.stem * 0.4 + sway) * min(1.0, self.stem / 10)
        self.y = self.base - self.stem


class Butterflies(Scene):
    name = "butterflies"
    title = "Butterflies"
    blurb = "big patterned butterflies and moths flutter through a night garden and rest on flowers"
    tags = ("nature", "creatures", "calm", "summer")
    interactions = "point to shoo the butterflies, click to grow a flower they come to visit"
    options = {
        "count": (0, "number of butterflies (0 = based on screen size)"),
        "family": ("random", "random, monarch, morpho, swallowtail, moth, admiral or jewel"),
        "flowers": (True, "flowers at the bottom to land on"),
        "trail": (True, "faint shimmering trail behind each butterfly"),
    }

    def setup(self):
        rng = self.rng
        w, h = self.w, self.h
        fam = self.opt("family")
        self.fam_fixed = fam if fam in FAMILIES else None
        # a garden "mood": which families are common this run
        pool = list(FAMILIES)
        rng.shuffle(pool)
        self.pool = pool[:rng.randint(2, 4)] + [rng.choice(FAMILIES)]
        n = self.opt("count") or max(2, min(7, int(round((1.5 + w * h / 2400) * self.density))))
        self.flies = []
        for k in range(n):
            depth = (k + rng.uniform(0.2, 0.9)) / n
            self.flies.append(Fly(self, depth, self.family()))
        self.flies.sort(key=lambda f: f.depth)
        # flowers: a few species per run, every head with its own petal count and droop
        self.blooms = []
        if self.opt("flowers"):
            hue0 = rng.random()
            scheme = rng.choice(("analog", "complement", "wild", "pastel"))
            kinds = rng.sample(("daisy", "cosmos", "cone", "zinnia"), rng.randint(1, 3))
            nb = max(2, int(w / rng.uniform(12, 20)))
            xs = sorted(rng.uniform(2, w - 2) for _ in range(nb))
            big = min(w, h * ASPECT)
            for x in xs:
                kind = rng.choice(kinds)
                if scheme == "analog":
                    hue = hue0 + rng.uniform(-0.08, 0.08)
                elif scheme == "complement":
                    hue = hue0 + rng.choice((0, 0.5)) + rng.uniform(-0.04, 0.04)
                else:
                    hue = rng.random()
                sat = rng.uniform(0.25, 0.45) if scheme == "pastel" else rng.uniform(0.5, 0.85)
                petal = hsv(hue, sat, 1.0) if kind != "daisy" or rng.random() < 0.5 else (250, 248, 240)
                center = rng.choice(((255, 200, 60), (255, 170, 50))) if kind in ("daisy", "cosmos") else                     rng.choice(((150, 80, 40), (120, 60, 50), (255, 150, 40)))
                stem = rng.uniform(h * 0.12, h * 0.36)
                size = clamp(big * rng.uniform(0.045, 0.075), 2.4, 8.0)
                self.blooms.append(Bloom(rng, x, h, stem, kind, (petal, center), size))
        # night garden backdrop: stars, a low glowing mist and grass
        self.stars = [(rng.uniform(0, w), rng.uniform(0, h * 0.55), rng.uniform(0, TAU), rng.uniform(0.5, 2.0))
                      for _ in range(int(w * h / 140))]
        self.grass = [(rng.uniform(0, w), rng.uniform(1.5, max(2.0, h * 0.12)), rng.uniform(-0.6, 0.6), rng.uniform(0, TAU),
                       hsv(rng.uniform(0.22, 0.38), rng.uniform(0.4, 0.7), rng.uniform(0.25, 0.45)))
                      for _ in range(int(w * 0.9))]
        self.sparks = []
        self.n_blooms = len(self.blooms)   # clicked flowers are appended after these

    # ------------------------------------------------------------------ mouse
    def on_click(self, x, y):
        rng = self.rng
        w, h = self.w, self.h
        x = clamp(x if x == x else w / 2, 2, max(2, w - 3))
        y = y if y == y else h / 2
        stem = clamp(h - 1 - y, h * 0.12, h * 0.45)
        big = min(w, h * ASPECT)
        kind = rng.choice(("daisy", "cosmos", "cone", "zinnia"))
        petal = hsv(rng.random(), rng.uniform(0.45, 0.8), 1.0)
        center = (255, 200, 60) if kind in ("daisy", "cosmos") else rng.choice(((150, 80, 40), (255, 150, 40)))
        b = Bloom(rng, x, h, stem, kind, (petal, center), clamp(big * rng.uniform(0.055, 0.08), 2.6, 8.0))
        b.grow = 0.0
        b.stem, b.r = 0.5, 0.3
        self.blooms.append(b)
        extra = self.blooms[self.n_blooms:]
        if len(extra) > 5:            # the oldest clicked flower makes way
            old = extra[0]
            self.blooms.remove(old)
            for f in self.flies:
                if f.flower is old:
                    f.flower = None
                    f.state = "fly"
                    f.tx, f.ty = f.pick_target(self)
        # the nearest butterfly comes to land on it, another one comes to look
        free = sorted((f for f in self.flies if f.state in ("fly", "approach", "rest")),
                      key=lambda f: abs(f.x - x) + abs(f.y - (h - stem)) * ASPECT)
        for k, f in enumerate(free[:2]):
            if f.flower is not None:
                f.flower.taken = False
                f.flower = None
            if k == 0:
                b.taken = True
                f.flower = b
                f.state = "approach"
                f.timer = 14
            else:
                f.state = "fly"
                f.tx, f.ty = clamp(x + rng.choice((-1, 1)) * f.R * 2.2, 0, w), h - 1 - stem - f.R / ASPECT
                f.timer = rng.uniform(5, 8)

    def family(self):
        return self.fam_fixed or self.rng.choice(self.pool)

    # ------------------------------------------------------------------ update
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.1)
        t = self.t
        rng = self.rng
        w, h = self.w, self.h
        for b in self.blooms:
            if b.grow < 1.0:   # a clicked flower shoots up and opens
                b.grow = min(1.0, b.grow + dt / 1.8)
                e = smoothstep(0.0, 0.6, b.grow)
                b.stem = max(0.5, b.full[0] * e)
                b.r = max(0.3, b.full[1] * smoothstep(0.45, 1.0, b.grow))
                if 0.5 < b.grow < 0.9 and rng.random() < dt * 30:
                    a = rng.uniform(0, TAU)
                    self.sparks.append([b.x, b.y, math.cos(a) * 3, math.sin(a) * 1.5 - 0.5, rng.uniform(0.8, 1.6),
                                        mix(b.petal, WHITE, 0.4), rng.uniform(0, TAU), 1.0])
            b.update(t)
        ptr = self.pointer
        for i, f in enumerate(self.flies):
            f.life -= dt
            if f.state == "rest" and ptr is not None and                     math.hypot(f.x - ptr[0], (f.y - ptr[1]) * ASPECT) < f.R * 1.3:
                # startled off its flower
                f.state = "fly"
                f.flower.taken = False
                f.flower = None
                f.vy = -f.speed
                f.tx, f.ty = f.pick_target(self)
                f.timer = rng.uniform(3, 6)
            if f.state == "rest":
                b = f.flower
                f.x += (b.x - f.x) * min(1, dt * 8)
                f.y += (b.y - f.R * 0.3 / ASPECT - f.y) * min(1, dt * 8)
                f.rest_phase += dt * 0.9
                # bask open, then slowly close and open again
                c = 0.5 - 0.5 * math.cos(f.rest_phase)
                f.phi = 0.95 * c ** 2.2
                f.tilt += (b.bend * 0.6 - f.tilt) * dt
                f.timer -= dt
                if f.timer <= 0:
                    f.state = "fly"
                    b.taken = False
                    f.flower = None
                    f.vy = -f.speed * 0.8
                    f.tx, f.ty = f.pick_target(self)
                    f.timer = rng.uniform(4, 9)
                continue
            # flapping
            f.phase += dt * TAU * f.g["rate"]
            if f.glide > 0:
                f.glide -= dt
                target_phi = 0.08 + 0.05 * math.sin(f.phase * 0.3)
                f.phi += (target_phi - f.phi) * min(1, dt * 10)
            else:
                f.phi = -0.3 + 1.65 * (0.5 - 0.5 * math.cos(f.phase)) ** 1.7
                if rng.random() < dt * f.g["glide"] * 0.5 and math.sin(f.phase) < -0.8:
                    f.glide = rng.uniform(0.4, 1.3)
            # steering
            if f.state == "approach":
                b = f.flower
                f.tx, f.ty = b.x, b.y - f.R * 0.3 / ASPECT
            dx, dy = f.tx - f.x, (f.ty - f.y) * ASPECT
            dist = math.hypot(dx, dy) + 1e-6
            sp = f.speed * (min(1.0, dist / 6) if f.state == "approach" else 1.0)
            n1 = noise1(t * 0.7 + f.seed, f.seed) * 0.9
            n2 = noise1(t * 0.9 + f.seed * 3, f.seed + 1) * 0.9
            dvx = dx / dist * sp + n1 * f.speed * (0.2 if f.state == "approach" else 0.7)
            dvy = dy / dist * sp / ASPECT + n2 * f.speed * (0.1 if f.state == "approach" else 0.35)
            if ptr is not None:                         # flutter away from the pointer
                ox, oy = f.x - ptr[0], (f.y - ptr[1]) * ASPECT
                dd = math.hypot(ox, oy) + 1e-6
                lim = f.R * 2.6
                if dd < lim:
                    push = (lim - dd) / lim * f.speed * 3.0
                    dvx += ox / dd * push
                    dvy += oy / dd * push / ASPECT
                    if f.state == "fly" and dd < f.R * 1.5:
                        f.tx, f.ty = f.pick_target(self)
            for o in self.flies:                       # keep a little personal space
                if o is not f and o.state != "rest":
                    ox, oy = f.x - o.x, (f.y - o.y) * ASPECT
                    dd = math.hypot(ox, oy) + 1e-6
                    lim = (f.R + o.R) * 1.1
                    if dd < lim:
                        push = (lim - dd) / lim * f.speed * 1.5
                        dvx += ox / dd * push
                        dvy += oy / dd * push / ASPECT
            k = min(1.0, dt * 1.6)
            f.vx += (dvx - f.vx) * k
            f.vy += (dvy - f.vy) * k
            # each downstroke gives a little hop
            lift = math.cos(f.phase) * (0.0 if f.glide > 0 else 1.0) * 1.8 * (0.5 + f.depth * 0.5)
            f.x += f.vx * dt
            f.y += (f.vy + lift * 0.6) * dt
            f.tilt += (clamp(f.vx * 0.045, -0.3, 0.3) - f.tilt) * min(1, dt * 3)
            # trail
            if self.opt("trail"):
                f.trail_t -= dt
                if f.trail_t <= 0:
                    f.trail_t = 0.05
                    self.sparks.append([f.x + rng.uniform(-1, 1), f.y + rng.uniform(-0.3, 0.6),
                                        rng.uniform(-0.4, 0.4), rng.uniform(0.1, 0.6), rng.uniform(1.0, 2.2),
                                        rng.choice(f.trail_cols), rng.uniform(0, TAU), f.depth])
            if f.state == "approach" and dist < 0.8:
                f.state = "rest"
                f.timer = rng.uniform(5, 11)
                f.rest_phase = 0.0
                f.vx = f.vy = 0.0
                continue
            f.timer -= dt
            if f.state == "leave":
                if f.x < -f.R * 2 or f.x > w + f.R * 2 or f.y < -f.R or f.y > h + f.R:
                    nf = Fly(self, f.depth, self.family(), enter=True)
                    self.flies[i] = nf
                continue
            if f.timer <= 0 or dist < 2:
                f.timer = rng.uniform(3, 7)
                free = [b for b in self.blooms if not b.taken]
                roll = rng.random()
                if f.life <= 0 and roll < 0.6:
                    f.state = "leave"
                    side = -1 if f.x < w / 2 else 1
                    f.tx, f.ty = w / 2 + side * (w / 2 + f.R * 4), rng.uniform(-h * 0.1, h * 0.5)
                elif free and roll < 0.3 and sum(o.state in ("rest", "approach") for o in self.flies) < max(1, len(self.flies) // 2):
                    b = min(rng.sample(free, min(3, len(free))), key=lambda bb: abs(bb.x - f.x))
                    b.taken = True
                    f.flower = b
                    f.state = "approach"
                    f.timer = 12
                else:
                    f.tx, f.ty = f.pick_target(self)
            # soft walls
            if f.state == "fly":
                if f.x < -f.R * 0.5:
                    f.vx += dt * 8
                elif f.x > w + f.R * 0.5:
                    f.vx -= dt * 8
                if f.y < 1:
                    f.vy += dt * 6
                elif f.y > h * 0.75:
                    f.vy -= dt * 6
        alive = []
        for s in self.sparks:
            s[4] -= dt
            if s[4] > 0:
                s[0] += s[2] * dt
                s[1] += s[3] * dt
                alive.append(s)
        self.sparks = alive[-400:]

    # ------------------------------------------------------------------ draw
    def draw(self, cv):
        t = self.t
        w, h = self.w, self.h
        for sx, sy, sp, sr in self.stars:
            v = 0.12 + 0.12 * math.sin(t * sr + sp)
            if v > 0.13:
                cv.put(sx, sy, "." if v < 0.2 else "·", (150, 160, 210), level=v)
        # grass
        for gx, gh, lean, ph, gc in self.grass:
            sway = lean + 0.35 * math.sin(t * 0.8 + ph + gx * 0.05)
            for k in range(int(gh)):
                f = k / gh
                x = gx + sway * f * f * gh * 0.6
                ch = "|" if abs(sway * f) < 0.25 else ("/" if sway > 0 else "\\")
                cv.put(x, h - 1 - k, ch, scale(gc, 1 - 0.4 * f))
        for b in self.blooms:
            self.draw_bloom(cv, b)
        for s in self.sparks:
            life = s[4]
            tw = 0.5 + 0.5 * math.sin(t * 9 + s[6])
            v = min(1.0, life) * (0.25 + 0.35 * tw) * (0.6 + 0.4 * s[7])
            ch = "*" if v > 0.45 else "+" if v > 0.33 else "·" if v > 0.18 else "."
            x, y = int(s[0]), int(s[1])
            if 0 <= x < w and 0 <= y < h and cv.lv[y * w + x] < v:
                cv.put(x, y, ch, scale(s[5], 0.4 + 0.6 * v), level=v)
        for f in self.flies:
            self.draw_fly(cv, f)

    def draw_bloom(self, cv, b):
        h = self.h
        # stem: gentle curve from the base to the head
        rows = int(b.stem)
        stem_col = (70, 130, 60)
        px = b.x0
        for k in range(rows + 1):
            f = k / max(1, rows)
            x = b.x0 + (b.x - b.x0) * f * f
            y = b.base - k
            ch = _slope_ch(x - px, -1) if k else "|"
            cv.put(x, y, ch, scale(stem_col, 0.6 + 0.3 * f))
            px = x
        for lf, side in b.leaves:
            k = int(rows * lf)
            f = k / max(1, rows)
            x = b.x0 + (b.x - b.x0) * f * f
            cv.put(x + side, b.base - k, "/" if side > 0 else "\\", (60, 140, 70))
            cv.put(x + 2 * side, b.base - k - (1 if abs(side) else 0), "~", (50, 120, 60))
        # head: petals as radiating strokes (slope-aware glyphs) around a domed centre; the face
        # is tipped toward the sky, so the vertical axis is squashed by b.tilt
        r = b.r
        t = self.t
        rot = b.rot + 0.08 * math.sin(t * 0.7 + b.phase)
        pet, cen = b.petal, b.center
        deep = mix(pet, (70, 20, 70), 0.4)
        tip = mix(pet, (255, 255, 255), 0.3)
        sy = b.tilt / ASPECT
        # back petals first (upper half, further away), then the front ones
        order = sorted(range(b.np), key=lambda k: math.sin(rot + k * TAU / b.np))
        for k in order:
            a = rot + k * TAU / b.np
            ca, sa = math.cos(a), math.sin(a)
            n = max(2, int(r * 1.1))
            fy = 1.0 if sa > 0 else 0.85
            for q in range(n + 1):
                u = q / n
                rr = b.d0 + (1 - b.d0) * u
                x = b.x + ca * rr * r
                y = b.y + sa * rr * r * sy + b.droop * (rr * r * sy) * rr
                if u > 0.85:
                    ch = "o" if b.kind == "cosmos" else "*" if b.kind == "zinnia" else "."
                    ch = "'" if b.kind == "daisy" and sa < 0 else ch
                else:
                    ch = _slope_ch(ca, sa * sy + b.droop * sy * 2 * rr)
                c = mix(deep, tip, u) if b.kind != "daisy" else mix(pet, tip, u)
                cv.put(x, y, ch, scale(c, (0.65 + 0.35 * u) * fy), level=0.6)
                if b.pw > 0.16 and 0.2 < u < 0.85:          # broad petals get a second stroke
                    cv.put(x + (1 if ca > 0 else -1) * (abs(sa) > 0.5), y + (0 if abs(sa) > 0.5 else 0), ch, scale(c, 0.6 * fy))
        # centre
        cr = max(0.6, b.d0 * r)
        for y in range(int(b.y - cr * sy - 0.5), int(b.y + cr * sy + 1.5)):
            for x in range(int(b.x - cr - 0.5), int(b.x + cr + 1.5)):
                d = math.hypot((x + 0.5 - b.x) / cr, (y + 0.5 - b.y) / max(0.5, cr * sy))
                if d < 1.15:
                    dome = 1 - min(1.0, d)
                    c = mix(cen, (255, 250, 210), 0.35 * dome if cen[0] > 200 else 0.1 * dome)
                    ch = "@" if dome > 0.45 else "o" if b.kind == "cone" else "%"
                    cv.put(x, y, ch, scale(c, 0.7 + 0.3 * dome), level=0.9)

    def draw_fly(self, cv, f):
        g = f.g
        tex = f.tex
        R = f.R
        w, h = cv.w, cv.h
        phi = f.phi
        cphi = max(0.07, math.cos(phi))
        sphi = math.sin(phi)
        lift = 0.28
        ct, st = math.cos(f.tilt), math.sin(f.tilt)
        glow = 0.78 + 0.22 * f.depth
        # light: flat-open wings catch the most light; morpho blue flashes with the angle
        light = (0.62 + 0.38 * cphi) * glow
        irid = g["irid"]
        sheen_c = 0.5 + 0.5 * math.sin(f.phase * 0.5)
        under = phi > 1.05
        ext = R * 1.75
        x0, x1 = max(0, int(f.x - ext)), min(w, int(f.x + ext) + 1)
        y0, y1 = max(0, int(f.y - ext / ASPECT)), min(h, int(f.y + ext / ASPECT) + 1)
        inv = 1.0 / R
        mid = g["mid"]
        lvs = cv.lv
        for y in range(y0, y1):
            py = -(y + 0.5 - f.y) * ASPECT * inv          # up positive, units of R
            for x in range(x0, x1):
                px = (x + 0.5 - f.x) * inv
                bx = px * ct - py * st                      # across the body
                by = px * st + py * ct                      # along the body (head up)
                ax = bx if bx > 0 else -bx
                xw = ax / cphi
                if xw >= XM:
                    continue
                yw = by - xw * sphi * lift
                iy = int((yw - YB) / STEP)
                if iy < 0 or iy >= TY:
                    continue
                cell = tex[iy * TX + int(xw / STEP)]
                if cell is None:
                    # soft halo just outside the wing edge
                    ix2 = int(xw * 0.9 / STEP)
                    iy2 = int((yw * 0.9 - YB) / STEP)
                    if 0 <= iy2 < TY and tex[iy2 * TX + ix2] is not None:
                        i = y * w + x
                        hv = 0.09 * glow
                        if lvs[i] < hv:
                            cv.shade(x, y, hv, mix(mid, (255, 255, 255), 0.3))
                    continue
                v, col, rho = cell
                if under:
                    col = mix(g["under"], col, 0.3)
                if irid:
                    hs = math.sin(phi * 2.2 + rho * 2.5)
                    col = mix(col, mix((60, 255, 255), (170, 110, 255), 0.5 + 0.5 * hs), irid * 0.35 * (0.5 + 0.5 * hs) * (1 - rho * 0.5))
                sh = math.exp(-((rho - 0.25 - 0.6 * sheen_c) * 6) ** 2) * g["sheen"]
                if sh > 0.02:
                    col = mix(col, (255, 255, 255), sh)
                vv = v * light * (1.0 + 0.3 * sh)
                if xw * cphi < 0.08 and phi > 0.9:
                    vv *= 1.1
                cv.shade(x, y, vv, scale(col, 0.45 + 0.55 * light / glow * glow), mode="over", dim=False)
        # body: head, fuzzy thorax, segmented abdomen along the axis
        bc = g["body_col"]
        bcol = scale(mix(bc, (255, 240, 220), 0.25), 0.6 + 0.4 * glow)

        def at(bx, by):
            px, py = bx * ct + by * st, -bx * st + by * ct
            return f.x + px * R, f.y - py * R / ASPECT

        steps = max(3, int(R * 0.8))
        for k in range(steps + 1):
            u = k / steps                                   # 0 head .. 1 tail
            sx, sy = at(0.0, 0.2 - u * 0.78)
            if u < 0.1:
                ch, c = "@", mix(bc, (255, 255, 255), 0.25)
            elif u < 0.36:
                ch, c = ("#" if g["fuzz"] else "8"), mix(bc, (255, 230, 200), 0.3)
            else:
                ch, c = ("|" if abs(st) < 0.25 else "/" if st > 0 else "\\"), mix(bc, (255, 230, 200), 0.15)
            cv.put(sx, sy, ch, scale(c, 0.65 + 0.35 * glow))
        # antennae: thin lines from the head ending in a club (butterflies) or feathery (moths)
        club = g["antenna"] == "club"
        alen = 0.5 if club else 0.34
        spread = 0.38 if club else 0.62
        for side in (-1, 1):
            n = max(2, int(R * alen * 0.9))
            px_, py_ = at(0.0, 0.24)
            for k in range(1, n + 1):
                q = k / n
                bx = side * math.sin(spread) * alen * q * (1 + 0.25 * q)
                by = 0.24 + math.cos(spread) * alen * q
                ax, ay = at(bx, by)
                if k == n:
                    ch = "o" if club else "*"
                elif not club:
                    ch = "}" if side < 0 else "{"
                else:
                    ch = _slope_ch(ax - px_, ay - py_)
                cv.put(ax, ay, ch, bcol)
                px_, py_ = ax, ay
