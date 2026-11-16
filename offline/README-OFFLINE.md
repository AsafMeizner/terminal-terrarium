# terminal-terrarium: offline bundle

Everything needed to use terminal-terrarium on a machine with **no internet**: Windows or Linux,
in a normal terminal. Built from commit `{COMMIT}` on {DATE}.

## You need

- **Python 3.9 or newer** with pip (`python --version`; on Windows the launcher `py` works too).
- Nothing else. Node.js, used only by the optional ASCII Magic library pieces, is included
  for x64 Windows and Linux.

## Install

**Windows**: double-click `install-windows.bat`, or in a terminal:

```bat
install-windows.bat            :: terrarium + ASCII Magic library (+ portable Node if needed)
install-windows.bat --export   :: also Pillow, for PNG/GIF export
```

**Linux**:

```sh
sh install-linux.sh            # terrarium + ASCII Magic library (+ portable Node if needed)
sh install-linux.sh --export   # also Pillow, for PNG/GIF export
```

Both run `install.py`, which uses only the Python standard library and installs from the files in
this folder. Check what's installed any time with `python install.py --check`.

## Use

```sh
terrarium                       # a random scene    (or: python -m terrarium)
terrarium jellyfish             # one scene
terrarium --list                # all {SCENES} scenes (* = reacts to the mouse)
terrarium --all --shuffle --cycle 30
terrarium bonsai -t noir-gold --charset blocks
terrarium --magic-list moon     # the ASCII Magic library ({PIECES} pieces, works offline)
terrarium magic:moonlit-sea
```

Keys: `space` pause, `n`/`p` scene, `r` new variation, `t` theme, `c` characters, `+`/`-` speed,
`?` help, `q` quit. Click and point in the scene too: feed the fish, launch fireworks...

If the `terrarium` command isn't found, use `python -m terrarium` (pip's script folder may not be
on your PATH).

## The website, offline

`website/` is the full playground (every scene and setting, plus the library gallery) with
Python-in-the-browser (Pyodide) included, so it needs no internet. Serve it locally:

```sh
python -m http.server 8000 -d website
```

then open <http://localhost:8000> in a browser. (Opening `index.html` straight from disk doesn't
work: browsers only run its background worker over http.)

## What's in here

| folder | what |
|---|---|
| `wheels/` | the terrarium package (pure Python, works on any OS) |
| `magic-library/` | the ASCII Magic pieces, pre-downloaded (MIT, see its `LICENSE` and `NOTICE`) |
| `extras/node/` | portable Node.js {NODE} for Windows x64 and Linux x64 (only for library pieces) |
| `extras/pillow/` | Pillow wheels for Python 3.10-3.14 on Windows x64 and Linux x64 (only for image export) |
| `website/` | the offline playground |
| `source/` | the full source code, plus `terrarium.bundle`: the git repository with all history (`git clone terrarium.bundle`) |

## Without the installer

```sh
python -m pip install --no-index wheels/terminal_terrarium-*.whl
```

That alone gives you all {SCENES} scenes. For library pieces offline, also point terrarium at the
library and say it's offline:

```sh
# Linux
export TERRARIUM_MAGIC_DIR="$PWD/magic-library" TERRARIUM_OFFLINE=1
# Windows (cmd)
set TERRARIUM_MAGIC_DIR=%CD%\magic-library
set TERRARIUM_OFFLINE=1
```

and use any Node.js 18+ (`TERRARIUM_NODE=path/to/node` if it isn't on PATH).

## Licenses

terrarium: MIT (`source/LICENSE`). ASCII Magic library: MIT by ASCII Magic (`magic-library/LICENSE`,
`magic-library/NOTICE`). Node.js: MIT and others (inside its archive). Pillow: MIT-CMU (inside each
wheel). Pyodide: MPL-2.0 (`website/pyodide/LICENSE`).
