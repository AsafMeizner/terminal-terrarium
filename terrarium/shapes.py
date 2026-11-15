"""Build creatures out of round parts, and move them like living things.

The idea (see docs/ANIMALS.md): a creature is a few circles, ellipses and tapered capsules.
To draw it, every cell asks "how far am I from the body's edge?". Cells deep inside get dense
characters (#, @), cells on the edge get light ones (., :), and a light direction shades it so it
looks round. Moving it is just changing the parts' positions every frame.

    body = Body()
    body.capsule(10, 10, 20, 11, 3.0, 1.0, color=(255, 140, 60))   # a tapered fish body
    body.circle(21, 11, 1.2, color=(255, 255, 255))                 # a pale tail tip
    body.draw(cv)

Coordinates are terminal cells (x right, y down). Radii are in x-cells; the y axis is stretched
by ASPECT for you, so a circle comes out round on screen.
"""
from __future__ import annotations

import math

from .engine import ASPECT, clamp, mix, scale


# ----------------------------------------------------------------------------- distances
def sd_circle(px, py, cx, cy, r):
    return math.hypot(px - cx, py - cy) - r


def sd_ellipse(px, py, cx, cy, rx, ry, angle=0.0):
    # approximate signed distance: good enough for shading soft creatures
    c, s = math.cos(angle), math.sin(angle)
    dx, dy = px - cx, py - cy
    u = (dx * c + dy * s) / rx
    v = (-dx * s + dy * c) / ry
    k = math.hypot(u, v)
    return (k - 1.0) * min(rx, ry)


def sd_capsule(px, py, ax, ay, bx, by, ra, rb):
    """Tapered capsule from (ax, ay) radius ra to (bx, by) radius rb."""
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    ll = vx * vx + vy * vy
    t = 0.0 if ll == 0 else clamp((wx * vx + wy * vy) / ll)
    return math.hypot(wx - vx * t, wy - vy * t) - (ra + (rb - ra) * t)


def smin(a, b, k=0.6):
    """Smooth minimum: blends two shapes together like soft clay instead of a hard seam."""
    if k <= 0:
        return min(a, b)
    h = clamp(0.5 + 0.5 * (b - a) / k)
    return b + (a - b) * h - k * h * (1 - h)


# ----------------------------------------------------------------------------- Body
class Body:
    """A creature made of round parts. Add parts, then draw() it onto a canvas."""

    def __init__(self, blend=0.7):
        self.parts = []      # (kind, args, color)
        self.decals = []     # (x, y_stretched, r, color, char): eyes, spots, stripes drawn on top
        self.blend = blend   # how softly parts merge (0 = hard seams)

    # Every part takes a color; parts drawn later win ties (eyes on top of heads).
    def circle(self, x, y, r, color=(255, 255, 255)):
        self.parts.append(("c", (x, y * ASPECT, r), color))
        return self

    def ellipse(self, x, y, rx, ry, angle=0.0, color=(255, 255, 255)):
        """rx, ry in x-cells; angle in radians (0 = along x)."""
        self.parts.append(("e", (x, y * ASPECT, rx, ry, angle), color))
        return self

    def capsule(self, x0, y0, x1, y1, r0, r1=None, color=(255, 255, 255)):
        self.parts.append(("s", (x0, y0 * ASPECT, x1, y1 * ASPECT, r0, r0 if r1 is None else r1), color))
        return self

    def spot(self, x, y, r, color, char=None):
        """A decal on top of the body: an eye, a spot, a stripe dot. It recolors the cells under
        it (and uses `char` if given, e.g. "o" or "@" for an eye). It doesn't change the shape."""
        self.decals.append((x, y * ASPECT, r, color, char))
        return self

    def bounds(self):
        xs, ys = [], []
        for kind, a, _ in self.parts:
            if kind == "c":
                xs += [a[0] - a[2], a[0] + a[2]]
                ys += [a[1] - a[2], a[1] + a[2]]
            elif kind == "e":
                m = max(a[2], a[3])
                xs += [a[0] - m, a[0] + m]
                ys += [a[1] - m, a[1] + m]
            else:
                r = max(a[4], a[5])
                xs += [min(a[0], a[2]) - r, max(a[0], a[2]) + r]
                ys += [min(a[1], a[3]) - r, max(a[1], a[3]) + r]
        return min(xs), min(ys) / ASPECT, max(xs), max(ys) / ASPECT

    def distance(self, px, py):
        """(signed distance, index of nearest part) at a point in stretched space."""
        best, idx = 1e9, -1
        blended = 1e9
        for i, (kind, a, _) in enumerate(self.parts):
            if kind == "c":
                d = sd_circle(px, py, *a)
            elif kind == "e":
                d = sd_ellipse(px, py, *a)
            else:
                d = sd_capsule(px, py, *a)
            if d <= best:
                best, idx = d, i
            blended = smin(blended, d, self.blend) if blended < 1e8 else d
        return blended, idx

    def draw(self, cv, light=(-0.55, -0.85), depth=1.0, edge=0.9, glow=0.0, pattern=None, mode="max",
             ambient=0.5):
        """Rasterize the body.

        light:   direction the light comes FROM (x, y); shading makes parts look round.
        depth:   0 far .. 1 near. Far bodies are dimmer, like the reel's "fade into the dark".
        edge:    how many cells the soft outline spans.
        glow:    extra faint halo outside the body (0 = none).
        pattern: optional fn(x, y, part_index, inside) -> color or None, for spots and stripes.
        """
        if not self.parts:
            return
        x0, y0, x1, y1 = self.bounds()
        pad = edge + glow * 3 + 1
        lx, ly = light
        ln = math.hypot(lx, ly) or 1.0
        lx, ly = lx / ln, ly / ln
        fade = 0.5 + 0.5 * clamp(depth)
        colors = [p[2] for p in self.parts]
        # 1) the distance from every cell in the bounding box to the body's surface, computed once
        ya, yb = max(0, int(y0 - pad / ASPECT)), min(cv.h, int(y1 + pad / ASPECT) + 2)
        xa, xb = max(0, int(x0 - pad)), min(cv.w, int(x1 + pad) + 2)
        bw = xb - xa
        if bw <= 0 or yb <= ya:
            return
        dist = self.distance
        D, I = [], []
        for y in range(ya, yb):
            py = (y + 0.5) * ASPECT
            for x in range(xa, xb):
                d, i = dist(x + 0.5, py)
                D.append(d)
                I.append(i)
        far = edge * 0.5 + glow * 3
        # 2) shade each cell from its depth inside the body and a normal from its neighbors
        for y in range(ya, yb):
            row = (y - ya) * bw
            py = (y + 0.5) * ASPECT
            for x in range(xa, xb):
                k = row + x - xa
                d = D[k]
                if d > far:
                    continue
                i = I[k]
                px = x + 0.5
                if d > edge * 0.5:  # halo
                    v = glow * 0.25 * (1 - (d - edge * 0.5) / (glow * 3))
                    cv.shade(x, y, v * fade, colors[i], mode)
                    continue
                # inside: dense; near the edge: light. That's the whole trick.
                inside = clamp((edge * 0.5 - d) / (edge * 1.3))
                # surface normal = how the distance changes toward the neighbors -> lambert light
                left = D[k - 1] if x > xa else d
                right = D[k + 1] if x < xb - 1 else d
                up = D[k - bw] if y > ya else d
                down = D[k + bw] if y < yb - 1 else d
                nx = right - left
                ny = (down - up) / ASPECT
                nn = math.hypot(nx, ny) or 1.0
                lit = clamp(-(nx * lx + ny * ly) / nn * 0.5 + 0.5)
                bulge = clamp(inside * 1.4)
                light_term = ambient + (1 - ambient) * (lit * (1 - bulge) + bulge * 0.85)
                v = (0.22 + 0.78 * inside ** 0.55) * light_term
                c = colors[i]
                if pattern is not None:
                    pc = pattern(px, py / ASPECT, i, inside)
                    if pc is not None:
                        c = pc
                c = mix(scale(c, 0.55), c, lit)  # shadow side is darker in color too
                char = None
                for sx, sy, sr, sc, sch in self.decals:
                    # inside the spot, or the one cell that holds its center (tiny eyes)
                    if math.hypot(px - sx, py - sy) <= sr or (int(sx) == x and int(sy / ASPECT) == y):
                        c, char = sc, sch
                if char:
                    cv.put(x, y, char, scale(c, fade), level=v * fade)
                else:
                    cv.shade(x, y, v * fade, c, mode)


# ----------------------------------------------------------------------------- motion
class Chain:
    """Follow-the-leader spine: move the head, the rest trails behind at fixed spacing.
    Use it for fish, snakes, tails, tentacles, dragons."""

    def __init__(self, x, y, n, spacing=1.0, angle=math.pi):
        self.spacing = spacing
        self.points = [(x + math.cos(angle) * spacing * i, y + math.sin(angle) * spacing * i / ASPECT)
                       for i in range(n)]

    def follow(self, hx, hy):
        pts = self.points
        pts[0] = (hx, hy)
        for i in range(1, len(pts)):
            px, py = pts[i - 1]
            x, y = pts[i]
            dx, dy = x - px, (y - py) * ASPECT
            d = math.hypot(dx, dy) or 1e-6
            k = self.spacing / d
            pts[i] = (px + dx * k, py + dy * k / ASPECT)

    @property
    def head(self):
        return self.points[0]

    def heading(self, i=0):
        """Direction (radians, in stretched space) the chain points at segment i."""
        a = self.points[i]
        b = self.points[min(i + 1, len(self.points) - 1)]
        return math.atan2((a[1] - b[1]) * ASPECT, a[0] - b[0])


class Mover:
    """A point that wanders on lazy S-curves and can steer toward a target or away from a threat.

    Each mover has its own random "personality" (turn rate, speed), so a crowd doesn't move in
    lockstep. depth 0..1: far movers are slower (the reel's fake-3D trick).
    """

    def __init__(self, rng, x, y, speed=4.0, depth=1.0):
        self.x, self.y = x, y
        self.heading = rng.uniform(-math.pi, math.pi)
        self.speed = speed * (0.45 + 0.55 * depth) * rng.uniform(0.8, 1.2)
        self.turn = rng.uniform(0.6, 1.4)
        self.phase = rng.uniform(0, 100)
        self.depth = depth

    def update(self, dt, t, bounds, target=None, threat=None, margin=4.0):
        w, h = bounds
        # lazy S-curves: heading drifts with a slow sine wobble
        steer = math.sin(t * 0.5 * self.turn + self.phase) * 0.9 * self.turn
        want = None
        if target is not None:
            want = math.atan2((target[1] - self.y) * ASPECT, target[0] - self.x)
        if threat is not None:
            dx, dy = self.x - threat[0], (self.y - threat[1]) * ASPECT
            if math.hypot(dx, dy) < 18:
                want = math.atan2(dy, dx)
        # keep away from the walls
        if self.x < margin or self.x > w - margin or self.y < margin / ASPECT or self.y > h - margin / ASPECT:
            want = math.atan2((h / 2 - self.y) * ASPECT, w / 2 - self.x)
        if want is not None:
            diff = (want - self.heading + math.pi) % math.tau - math.pi
            steer = diff * 2.5
        self.heading += steer * dt
        boost = 1.6 if threat is not None and want is not None else 1.0
        self.x += math.cos(self.heading) * self.speed * boost * dt
        self.y += math.sin(self.heading) * self.speed * boost * dt / ASPECT

    def near(self, x, y, r):
        return math.hypot(self.x - x, (self.y - y) * ASPECT) < r
