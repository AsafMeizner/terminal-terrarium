# Writing a scene

A scene is one file in `terrarium/scenes/`. It is discovered automatically: no registry to edit.
Look at `terrarium/scenes/jellyfish.py` for a complete example.

```python
import math
from ..engine import ASPECT, Scene, clamp, mix, hsv, gradient, noise2, fbm

class Fireflies(Scene):
    name = "fireflies"              # CLI id, lowercase, unique
    title = "Fireflies"
    blurb = "fireflies drifting over a dark meadow"   # one line, shown in --list
    tags = ("night", "nature", "calm")
    options = {"count": (0, "how many fireflies (0 = auto)")}   # -o count=40

    def setup(self):                # build state; called on start, on resize and on density change
        n = self.opt("count") or self.count(30)   # count() scales by screen area and --density
        self.bugs = [[self.rng.uniform(0, self.w), self.rng.uniform(0, self.h)] for _ in range(n)]

    def update(self, dt):           # dt is already multiplied by --speed
        super().update(dt)          # advances self.t
        ...

    def draw(self, cv):             # cv is cleared before every frame
        for x, y in self.bugs:
            cv.shade(x, y, 0.9, (255, 230, 120))
```

## Canvas API (`terrarium/engine.py`)

| call | what it does |
|---|---|
| `cv.shade(x, y, v, rgb, mode="max", dim=True)` | intensity `v` in 0..1 picks a character from the active ramp (`--charset`) and dims the color. `mode="max"` keeps the brighter value, `"over"` replaces, `"add"` accumulates light. |
| `cv.put(x, y, ch, rgb)` | write a specific character (for glyph-based art: `/`, `\|`, `@`, `~`...) |
| `cv.text(x, y, s, rgb)` | a string |
| `cv.line(x0, y0, x1, y1, v, rgb)` | shaded line |
| `cv.glyph(v)` | the ramp character for an intensity |
| `cv.w, cv.h` | size in cells |

Helpers: `mix(c1, c2, t)`, `scale(c, k)`, `hsv(h, s, v)` (h in turns), `gradient(stops, t)`,
`clamp`, `lerp`, `smoothstep`, `noise1(x)`, `noise2(x, y)`, `fbm(x, y, octaves)`.
Scene helpers: `self.rng` (seeded `random.Random`, use it for all randomness so `--seed` works),
`self.t`, `self.w`, `self.h`, `self.opt(key)`, `self.count(base)`, `self.density`.

## Rules

- **Cells are about twice as tall as wide.** Multiply y-distances by `ASPECT` for round shapes.
- Colors are RGB tuples 0..255. Assume a dark background. Glow beats flat fill.
- **Single-width characters only**: ASCII, `·•°`, box drawing, `░▒▓█`, braille. No emoji, CJK or dingbats.
- All randomness through `self.rng`. Same seed, same scene.
- **Every run should look different.** Don't just shuffle positions. Roll the *structure* from
  `self.rng` like a little generative grammar: branch probability, angle mean and jitter, counts,
  proportions, palettes, layout. Give each object its own "genome". Explicit `-o` options override
  the dice; make `random` the default where it makes sense. Check 3 seeds side by side.
- Work at any size, from 60x20 up to 220x60. Nothing important should depend on a fixed size.
- `draw()` should take well under 30 ms at 160x48. Loop over bounding boxes rather than the full
  screen when you can.
- Declare every `-o` option in `options` with a default of the right type (int, float, bool or str).
- A scene must never crash. Clamp indices and guard divisions.

## Checking your scene

```sh
python -m terrarium --list                                   # it shows up, no load errors
python -m terrarium NAME --snapshot out.png --size 110x34    # look at it (needs Pillow)
python -m terrarium NAME --snapshot out.png --size 60x20     # small terminal
python -m terrarium NAME --record out.gif --frames 60        # motion
python -m terrarium NAME                                     # the real thing
```
