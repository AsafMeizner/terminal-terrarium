"""Smoke tests: every scene builds, animates and renders at several sizes without crashing.

Run with:  python -m unittest discover -s tests -v
"""
import io
import unicodedata
import unittest

from terrarium.cli import build_parser, main
from terrarium.engine import RAMPS, THEMES, Canvas, ColorFX, Context, Renderer
from terrarium.scenes import all_scenes, errors

SIZES = [(100, 32), (60, 20), (180, 50), (24, 8)]


def _wide(c):
    return unicodedata.east_asian_width(c) in ("W", "F")


class SceneTests(unittest.TestCase):
    def test_no_load_errors(self):
        self.assertEqual(errors(), {})

    def test_scene_metadata(self):
        for name, cls in all_scenes().items():
            with self.subTest(scene=name):
                self.assertTrue(cls.blurb, "missing blurb")
                self.assertEqual(name, name.lower())
                for key, decl in cls.options.items():
                    self.assertEqual(len(decl), 2, f"option {key} must be (default, help)")

    def test_scenes_run_everywhere(self):
        for name, cls in all_scenes().items():
            for w, h in SIZES:
                with self.subTest(scene=name, size=(w, h)):
                    scene = cls(Context(seed=7), w, h)
                    cv = Canvas(w, h)
                    sink = io.StringIO()
                    r = Renderer(sink.write, "truecolor", ColorFX("natural"))
                    for frame in range(40):
                        scene.update(0.25 if frame < 20 else 1 / 30)
                        cv.clear()
                        scene.draw(cv)
                        r.render(cv)
                    self.assertEqual(len(cv.ch), w * h)
                    for c in set(cv.ch):
                        self.assertEqual(len(c), 1, f"cell holds {c!r}")
                        self.assertFalse(_wide(c), f"double-width char {c!r}")
                    scene.resize(w + 7, h + 3)
                    cv = Canvas(w + 7, h + 3)
                    scene.update(1 / 30)
                    scene.draw(cv)

    def test_seed_is_reproducible(self):
        for name, cls in all_scenes().items():
            with self.subTest(scene=name):
                frames = []
                for _ in range(2):
                    s = cls(Context(seed=123), 80, 24)
                    cv = Canvas(80, 24)
                    for _ in range(30):
                        s.update(1 / 30)
                    s.draw(cv)
                    frames.append("".join(cv.ch))
                self.assertEqual(frames[0], frames[1])

    def test_seeds_give_variety(self):
        """Different seeds should produce different pictures (procedural variety)."""
        for name, cls in all_scenes().items():
            with self.subTest(scene=name):
                pics = set()
                for seed in (1, 2, 3):
                    s = cls(Context(seed=seed), 80, 24)
                    cv = Canvas(80, 24)
                    for _ in range(30):
                        s.update(1 / 30)
                    s.draw(cv)
                    pics.add("".join(cv.ch))
                self.assertGreater(len(pics), 1, "all seeds look identical")

    def test_mouse_never_crashes(self):
        """Clicks and pointer moves anywhere (even off-screen) must be safe for every scene."""
        spots = [(0, 0), (40.5, 12.2), (79.9, 23.9), (-5, -5), (200, 90)]
        for name, cls in all_scenes().items():
            with self.subTest(scene=name):
                s = cls(Context(seed=4), 80, 24)
                cv = Canvas(80, 24)
                for x, y in spots:
                    s.pointer = (x, y)
                    s.on_click(x, y)
                    s.update(0.1)
                    cv.clear()
                    s.draw(cv)
                s.pointer = None
                for _ in range(20):
                    s.update(1 / 30)
                s.draw(cv)

    def test_density_extremes(self):
        for name, cls in all_scenes().items():
            for d in (0.1, 4.0):
                with self.subTest(scene=name, density=d):
                    s = cls(Context(seed=1, density=d), 90, 30)
                    cv = Canvas(90, 30)
                    s.update(0.5)
                    s.draw(cv)


class EngineTests(unittest.TestCase):
    def test_all_themes_and_modes(self):
        cv = Canvas(30, 6)
        for x in range(30):
            cv.shade(x, 2, x / 29, (200, 120, 80))
        for theme in THEMES:
            for mode in ("truecolor", "256", "mono"):
                sink = io.StringIO()
                Renderer(sink.write, mode, ColorFX(theme, 45, 0.8, 1.1)).render(cv)
                self.assertIn("\x1b[", sink.getvalue())

    def test_all_ramps(self):
        for name, ramp in RAMPS.items():
            cv = Canvas(10, 2, ramp)
            cv.shade(1, 1, 1.0, (255, 255, 255))
            self.assertEqual(cv.ch[11], ramp[-1], name)

    def test_diff_renderer_only_sends_changes(self):
        cv = Canvas(20, 5)
        cv.put(3, 3, "@", (255, 0, 0))
        sink = io.StringIO()
        r = Renderer(sink.write, "truecolor")
        r.render(cv)
        sink.truncate(0)
        sink.seek(0)
        r.render(cv)
        self.assertEqual(sink.getvalue(), "")


class CliTests(unittest.TestCase):
    def test_list_and_info(self):
        self.assertEqual(main(["--list"]), 0)
        self.assertEqual(main(["--themes"]), 0)
        for name in all_scenes():
            self.assertEqual(main(["--info", name]), 0)

    def test_parser(self):
        a = build_parser().parse_args(["jellyfish", "-t", "vapor", "-o", "count=3", "--size", "80x24"])
        self.assertEqual(a.size, (80, 24))
        self.assertEqual(a.theme, "vapor")

    def test_new_scene_template_is_a_working_plugin(self):
        import os
        import tempfile

        from terrarium import scenes as registry
        from terrarium.cli import main as cli_main

        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(cli_main(["--new", "test_orbs", "--path", d]), 0)
            self.assertTrue(os.path.exists(os.path.join(d, "test_orbs.py")))
            registry.add_path(d)
            try:
                cls = registry.all_scenes()["test_orbs"]
                s = cls(Context(seed=1), 60, 20)
                cv = Canvas(60, 20)
                s.update(0.1)
                s.draw(cv)
                self.assertTrue(any(c != " " for c in cv.ch))
            finally:
                registry._EXTRA_DIRS.clear()
                registry._LOADED = False
                registry._REGISTRY.clear()

    def test_text_snapshot(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.txt")
            self.assertEqual(main(["jellyfish", "--snapshot", p, "--size", "60x20", "--warmup", "1"]), 0)
            self.assertTrue(os.path.getsize(p) > 0)


if __name__ == "__main__":
    unittest.main()
