"""Offline rendering: snapshot a scene to .png/.txt/.ans or record it to .gif (Pillow for images)."""
from __future__ import annotations

import os
import sys

from .engine import RAMPS, Canvas, ColorFX, Context, _to256

BG = (11, 12, 16)

_FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\CascadiaMono.ttf",
    r"C:\Windows\Fonts\CascadiaCode.ttf",
    r"C:\Windows\Fonts\consola.ttf",
    # macOS
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Menlo.ttc",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


def _font(path, size):
    from PIL import ImageFont

    for p in ([path] if path else []) + _FONT_CANDIDATES:
        if p and os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def simulate(scene_cls, w, h, args, frames, warmup):
    """Yield canvases for `frames` frames after `warmup` seconds, with a fixed timestep."""
    ctx = Context(seed=args.seed if args.seed is not None else 1, density=args.density, options=args.options)
    scene = scene_cls(ctx, w, h)
    dt = 1.0 / args.fps
    step = dt * args.speed
    t = 0.0
    while t < warmup:
        scene.update(step)
        t += dt
    cv = Canvas(w, h, RAMPS[args.charset])
    for _ in range(frames):
        cv.clear()
        scene.draw(cv)
        yield cv
        scene.update(step)


class _Painter:
    def __init__(self, w, h, fx, font_path=None, font_size=16):
        from PIL import Image

        self.Image = Image
        self.font = _font(font_path, font_size)
        self.cw = max(1, round(self.font.getlength("M")))
        asc, desc = self.font.getmetrics()
        self.chh = asc + desc
        self.w, self.h = w, h
        self.fx = fx
        self.masks = {}

    def mask(self, c):
        m = self.masks.get(c)
        if m is None:
            from PIL import ImageDraw

            m = self.Image.new("L", (self.cw, self.chh), 0)
            ImageDraw.Draw(m).text((0, 0), c, fill=255, font=self.font)
            self.masks[c] = m
        return m

    def paint(self, cv):
        im = self.Image.new("RGB", (self.w * self.cw, self.h * self.chh), BG)
        cw, chh, w = self.cw, self.chh, cv.w
        for i, c in enumerate(cv.ch):
            if c == " " or cv.fg[i] is None:
                continue
            y, x = divmod(i, w)
            im.paste(self.fx.apply(cv.fg[i]), (x * cw, y * chh), self.mask(c))
        return im


def _ansi(cv, fx, mode):
    lines = []
    for y in range(cv.h):
        row = []
        last = None
        for x in range(cv.w):
            i = y * cv.w + x
            c, f = cv.ch[i], cv.fg[i]
            if c != " " and f is not None and mode != "mono":
                r, g, b = fx.apply(f)
                s = f"\x1b[38;2;{r};{g};{b}m" if mode == "truecolor" else f"\x1b[38;5;{_to256((r, g, b))}m"
                if s != last:
                    row.append(s)
                    last = s
            row.append(c)
        lines.append("".join(row).rstrip() + "\x1b[0m")
    return "\n".join(lines) + "\n"


def export(scene_cls, args):
    w, h = args.size
    fx = ColorFX(args.theme, args.hue, args.saturation, args.brightness)
    path = args.record or args.snapshot
    ext = os.path.splitext(path)[1].lower()
    frames = args.frames if args.record else 1
    canvases = simulate(scene_cls, w, h, args, frames, args.warmup)

    if ext in (".txt", ".ans"):
        cv = next(canvases)
        text = "\n".join("".join(cv.ch[y * w:(y + 1) * w]).rstrip() for y in range(h)) + "\n"
        if ext == ".ans":
            text = _ansi(cv, fx, "truecolor")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    try:
        painter = _Painter(w, h, fx, args.font, args.font_size)
    except ImportError:
        sys.exit("terrarium: image export needs Pillow  ->  pip install pillow")

    if ext == ".gif":
        Image = painter.Image
        images = [painter.paint(cv) for cv in canvases]
        # One shared palette (sampled from several frames) and no dithering: unchanged pixels stay
        # byte-identical between frames, so the GIF encoder only stores what actually moved.
        picks = images[:: max(1, len(images) // 6)][:6]
        sample = Image.new("RGB", (images[0].width, images[0].height * len(picks)))
        for k, im in enumerate(picks):
            sample.paste(im, (0, k * im.height))
        palette = sample.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
        frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=round(1000 / args.fps),
                       loop=0, optimize=True)
    else:
        painter.paint(next(canvases)).save(path)
    return path
