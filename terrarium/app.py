"""Interactive run loop: scene switching, cycling, overlays and live keyboard controls."""
from __future__ import annotations

import random
import time

from .engine import RAMPS, THEMES, Canvas, ColorFX, Context, Keys, Renderer, Terminal

HELP = [
    "terrarium — keys",
    "",
    "  space    pause / resume",
    "  n  →     next scene",
    "  p  ←     previous scene",
    "  r        reseed (new variation)",
    "  +  -     speed up / slow down",
    "  ]  [     more / fewer things (density)",
    "  t  T     next / previous theme",
    "  c        next charset",
    "  h        hue shift +30°",
    "  i        show / hide info bar",
    "  ?        this help",
    "  q  esc   quit",
]


class App:
    def __init__(self, scene_classes, args):
        self.classes = scene_classes
        self.args = args
        self.idx = 0
        self.speed = args.speed
        self.density = args.density
        self.seed = args.seed
        self.fx = ColorFX(args.theme, args.hue, args.saturation, args.brightness)
        self.charset = args.charset
        self.themes = list(THEMES)
        self.charsets = list(RAMPS)
        self.paused = False
        self.show_help = False
        self.show_info = args.hud
        self.toast = None  # (text_lines, until)
        self.scene = None
        self.cv = None

    # ------------------------------------------------------------------ scene management
    def make_scene(self, w, h, reseed=False):
        if reseed or self.seed is None:
            seed = random.randrange(1 << 30)
        else:
            seed = self.seed
        ctx = Context(seed=seed, density=self.density, options=self.args.options)
        cls = self.classes[self.idx]
        if self.scene is not None:
            self.scene.close()
        self.scene = cls(ctx, w, h)
        self.scene_started = time.perf_counter()
        if self.args.title:
            hint = f"({cls.interactions})" if cls.interactions and not self.args.no_mouse else ""
            self.notify([cls.title or cls.name, cls.blurb, hint], 4.0 if hint else 3.5)

    def notify(self, lines, secs=2.0):
        self.toast = ([l for l in lines if l], time.perf_counter() + secs)

    def switch(self, step):
        self.idx = (self.idx + step) % len(self.classes)
        self.make_scene(self.cv.w, self.cv.h)

    # ------------------------------------------------------------------ input
    def handle(self, k):
        a = self
        if k in ("q", "Q", "esc"):
            return False
        if k == " ":
            a.paused = not a.paused
            a.notify(["paused" if a.paused else "playing"], 1.0)
        elif k in ("n", "right"):
            a.switch(1)
        elif k in ("p", "left"):
            a.switch(-1)
        elif k == "r":
            a.make_scene(a.cv.w, a.cv.h, reseed=True)
        elif k in ("+", "="):
            a.speed = min(8.0, a.speed * 1.25)
            a.notify([f"speed {a.speed:.2f}x"], 1.0)
        elif k in ("-", "_"):
            a.speed = max(0.05, a.speed / 1.25)
            a.notify([f"speed {a.speed:.2f}x"], 1.0)
        elif k in ("]", "["):
            a.density = min(5.0, a.density * 1.25) if k == "]" else max(0.1, a.density / 1.25)
            a.scene.ctx.density = a.density
            a.scene.setup()
            a.notify([f"density {a.density:.2f}"], 1.0)
        elif k in ("t", "T"):
            i = a.themes.index(a.fx.theme)
            a.fx.set(theme=a.themes[(i + (1 if k == "t" else -1)) % len(a.themes)])
            a.renderer.set_fx(a.fx)
            a.notify([f"theme: {a.fx.theme}"], 1.5)
        elif k == "c":
            i = a.charsets.index(a.charset) if a.charset in a.charsets else -1
            a.charset = a.charsets[(i + 1) % len(a.charsets)]
            a.cv.ramp = RAMPS[a.charset]
            a.notify([f"charset: {a.charset}"], 1.5)
        elif k == "h":
            a.fx.set(hue=(a.fx.hue + 30) % 360)
            a.renderer.set_fx(a.fx)
            a.notify([f"hue +{a.fx.hue:.0f}°"], 1.0)
        elif k == "i":
            a.show_info = not a.show_info
        elif k in ("?", "/"):
            a.show_help = not a.show_help
        return True

    # ------------------------------------------------------------------ overlays
    def draw_overlays(self, cv, fps):
        now = time.perf_counter()
        if self.toast and now < self.toast[1]:
            lines, until = self.toast
            fade = min(1.0, (until - now) / 0.8)
            col = (230 * fade + 25, 230 * fade + 25, 240 * fade + 15)
            y0 = cv.h - 1 - len(lines)
            for k, line in enumerate(lines):
                cv.fill_box(1, y0 + k, 3 + len(line), y0 + k + 1)
                cv.text(2, y0 + k, line, col if k == 0 else (col[0] * 0.65, col[1] * 0.65, col[2] * 0.7))
        if self.show_info:
            s = self.scene
            info = (f" {s.name}  seed {s.ctx.seed}  {fps:4.1f}fps  x{self.speed:.2f}  "
                    f"theme {self.fx.theme}  chars {self.charset} " + (" [paused]" if self.paused else ""))
            cv.fill_box(0, 0, len(info), 1)
            cv.text(0, 0, info, (150, 160, 170))
        if self.show_help:
            bw = max(len(l) for l in HELP) + 4
            bh = len(HELP) + 2
            x0 = max(0, (cv.w - bw) // 2)
            y0 = max(0, (cv.h - bh) // 2)
            cv.fill_box(x0, y0, x0 + bw, y0 + bh)
            for k, line in enumerate(HELP):
                cv.text(x0 + 2, y0 + 1 + k, line, (240, 240, 250) if k == 0 else (190, 200, 210))

    # ------------------------------------------------------------------ main loop
    def run(self):
        args = self.args
        term = Terminal(alt_screen=not args.no_alt_screen, mouse=not args.no_mouse)
        keys = Keys()
        self.renderer = Renderer(term.write, args.color, self.fx)
        frame = 1.0 / max(1, args.fps)
        term.enter()
        try:
            w, h = term.size()
            self.cv = Canvas(w, h, RAMPS[self.charset])
            self.make_scene(w, h)
            start = time.perf_counter()
            last = start - frame
            fps = float(args.fps)
            while True:
                t0 = time.perf_counter()
                dt = min(0.1, t0 - last)
                last = t0
                if dt > 0:
                    fps = fps * 0.9 + min(1000.0, 1.0 / dt) * 0.1

                w, h = term.size()
                if (w, h) != (self.cv.w, self.cv.h):
                    self.cv = Canvas(w, h, RAMPS[self.charset])
                    self.scene.resize(w, h)
                    term.clear()
                    self.renderer.reset()

                for k in keys.read():
                    if isinstance(k, tuple):  # mouse: ("click" | "move", x, y)
                        kind, mx, my = k
                        self.scene.pointer = (mx + 0.5, my + 0.5)
                        if kind == "click" and not self.show_help:
                            self.scene.on_click(mx + 0.5, my + 0.5)
                    elif not self.handle(k):
                        return
                if not self.paused:
                    self.scene.update(dt * self.speed)
                self.cv.clear()
                self.scene.draw(self.cv)
                if args.message:
                    msg = args.message
                    self.cv.fill_box((w - len(msg)) // 2 - 2, h // 2, (w + len(msg)) // 2 + 2, h // 2 + 1)
                    self.cv.text((w - len(msg)) // 2, h // 2, msg, (245, 245, 250))
                self.draw_overlays(self.cv, fps)
                self.renderer.render(self.cv)

                now = time.perf_counter()
                if args.duration and now - start >= args.duration:
                    return
                if args.cycle and len(self.classes) > 1 and now - self.scene_started >= args.cycle:
                    self.switch(1)
                time.sleep(max(0.0, frame - (time.perf_counter() - t0)))
        except KeyboardInterrupt:
            pass
        finally:
            term.exit()
            if self.scene is not None:
                self.scene.close()
            if self.scene is not None:
                print(f"terrarium: {self.scene.name} --seed {self.scene.ctx.seed}   (replay this exact variation)")
