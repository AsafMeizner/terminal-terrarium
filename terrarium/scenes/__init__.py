"""Scene registry.

Built-in scenes: every module in this package is imported and every Scene subclass with a
`name` is registered, so adding a scene means dropping a new file here.

Plugin scenes: any .py file in ~/.terrarium/scenes, in a directory listed in the
TERRARIUM_PATH environment variable (os.pathsep-separated), or passed with --path is loaded too.
Plugins import from `terrarium.engine` and can override a built-in scene by reusing its name.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import pkgutil
import sys

from ..engine import Scene

_REGISTRY: dict[str, type[Scene]] = {}
_ERRORS: dict[str, str] = {}
_EXTRA_DIRS: list[str] = []
_LOADED = False


def plugin_dirs():
    dirs = list(_EXTRA_DIRS)
    env = os.environ.get("TERRARIUM_PATH", "")
    dirs += [d for d in env.split(os.pathsep) if d]
    dirs.append(os.path.join(os.path.expanduser("~"), ".terrarium", "scenes"))
    return [d for d in dirs if os.path.isdir(d)]


def add_path(path):
    """Register an extra plugin directory (call before load())."""
    global _LOADED
    _EXTRA_DIRS.append(os.path.abspath(path))
    _LOADED = False
    _REGISTRY.clear()


def _collect(cls):
    for sub in cls.__subclasses__():
        if getattr(sub, "name", ""):
            _REGISTRY[sub.name] = sub
        _collect(sub)


def _load_file(path):
    mod_name = "terrarium_plugin_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)


def load():
    global _LOADED
    if _LOADED:
        return _REGISTRY
    for mod in pkgutil.iter_modules(__path__):
        if mod.name.startswith("_"):
            continue
        try:
            importlib.import_module(f"{__name__}.{mod.name}")
        except Exception as e:  # a broken scene shouldn't take the whole app down
            _ERRORS[mod.name] = f"{type(e).__name__}: {e}"
    for d in plugin_dirs():
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".py") and not fn.startswith("_"):
                try:
                    _load_file(os.path.join(d, fn))
                except Exception as e:
                    _ERRORS[os.path.join(d, fn)] = f"{type(e).__name__}: {e}"
    _collect(Scene)
    _LOADED = True
    return _REGISTRY


def all_scenes() -> dict[str, type[Scene]]:
    return dict(sorted(load().items()))


def errors():
    load()
    return dict(_ERRORS)
