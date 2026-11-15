"""Bridge between the browser (worker.js) and the real terrarium package, running in Pyodide."""
import array
import json

from terrarium.engine import RAMPS, THEMES, Canvas, ColorFX, Context
from terrarium.scenes import all_scenes

# Same grouping as scripts/update_readme.py
SECTIONS = [
    ("Flowers", {"flowers"}),
    ("Trees & plants", {"plants"}),
    ("Creatures", {"creatures", "animals"}),
    ("Water & ocean", {"ocean", "water"}),
    ("Space", {"space"}),
    ("Sky, weather & places", {"sky", "weather", "night", "city", "fire"}),
    ("Abstract & retro", set()),
]


def _section(cls):
    tags = set(cls.tags)
    for title, wanted in SECTIONS:
        if not wanted or tags & wanted:
            return title
    return SECTIONS[-1][0]


def _jsonable(v):
    return v if isinstance(v, (bool, int, float, str)) or v is None else str(v)


class Runner:
    def __init__(self):
        self.scenes = all_scenes()
        self.cfg = {}
        self.scene = None
        self.cv = None
        self.fx = ColorFX()

    def meta(self):
        return json.dumps({
            "scenes": [
                {"name": n, "title": c.title or n, "blurb": c.blurb, "tags": list(c.tags),
                 "interactions": getattr(c, "interactions", ""),
                 "section": _section(c),
                 "options": [{"key": k, "default": _jsonable(d), "type": type(d).__name__, "help": h}
                             for k, (d, h) in c.options.items()]}
                for n, c in self.scenes.items()
            ],
            "sections": [s for s, _ in SECTIONS],
            "themes": list(THEMES),
            "charsets": list(RAMPS),
        })

    def configure(self, cfg_json):
        cfg = json.loads(cfg_json)
        old = self.cfg
        rebuild = self.scene is None or any(
            cfg.get(k) != old.get(k) for k in ("scene", "seed", "options", "cols", "rows", "density"))
        self.cfg = cfg
        self.fx = ColorFX(cfg["theme"], float(cfg["hue"]), float(cfg["saturation"]), float(cfg["brightness"]))
        if rebuild:
            w, h = int(cfg["cols"]), int(cfg["rows"])
            ctx = Context(seed=int(cfg["seed"]), density=float(cfg["density"]),
                          options={k: str(v) for k, v in cfg.get("options", {}).items()})
            self.scene = self.scenes[cfg["scene"]](ctx, w, h)
            self.cv = Canvas(w, h, RAMPS[cfg["charset"]])
            # let growing scenes (bonsai, rose, timelapse...) start a little way in
            for _ in range(int(cfg.get("warmup", 0) * 15)):
                self.scene.update(1 / 15)
        self.cv.ramp = RAMPS[cfg["charset"]]

    def click(self, x, y):
        if self.scene is not None:
            self.scene.pointer = (x, y)
            self.scene.on_click(x, y)

    def point(self, x, y):
        if self.scene is not None:
            self.scene.pointer = None if x < 0 else (x, y)

    def step(self, dt):
        cfg = self.cfg
        if not cfg.get("paused"):
            self.scene.update(min(0.1, dt) * float(cfg["speed"]))
        cv = self.cv
        cv.clear()
        self.scene.draw(cv)
        apply = self.fx.apply
        cols = array.array("I", bytes(4 * cv.n))
        ch = cv.ch
        for i, f in enumerate(cv.fg):
            if f is not None and ch[i] != " ":
                r, g, b = apply(f)
                cols[i] = (r << 16) | (g << 8) | b | 0x1000000  # high bit marks "has color"
        return "".join(ch), cols.tobytes()


runner = Runner()
