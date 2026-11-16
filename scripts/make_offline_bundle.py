"""Build the offline (air-gapped) bundle: one zip with everything terrarium needs, no internet.

    python scripts/make_offline_bundle.py            # -> dist/terrarium-offline-<date>.zip
    python scripts/make_offline_bundle.py --keep     # also keep the unzipped folder

Run it ONLINE with a Python that has pip, and Node.js (for the website build). It builds from a
clean clone of the current commit (not the working folder), then downloads:
  - the ASCII Magic library pieces (MIT) so `terrarium magic:NAME` works offline
  - portable Node.js for Windows x64 and Linux x64 (only needed for library pieces)
  - Pillow wheels for Python 3.10-3.14 (only needed for PNG/GIF export)
  - Pyodide's core files so the website runs offline
See offline/README-OFFLINE.md for what the user gets.
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = "v26.13.1"
PYODIDE = "314.0.8"
PYODIDE_CDN = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE}/full/"
PYODIDE_FILES = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
PILLOW_PYTHONS = ["3.10", "3.11", "3.12", "3.13", "3.14"]
PILLOW_PLATFORMS = ["win_amd64", "manylinux_2_28_x86_64"]


def say(msg):
    print(f"[bundle] {msg}", flush=True)


def run(cmd, **kw):
    say(" ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def fetch(url, dest=None):
    req = urllib.request.Request(url, headers={"User-Agent": "terrarium-bundle"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if dest:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
    return data


def build_package(src, out):
    run([sys.executable, "-m", "pip", "wheel", src, "--no-deps", "-w", os.path.join(out, "wheels"), "-q"])


def build_source(src, out):
    dst = os.path.join(out, "source")
    os.makedirs(dst)
    # only the published branch: never other local branches, stashes or experiments
    run(["git", "-C", src, "bundle", "create", os.path.join(dst, "terrarium.bundle"), "main"])
    run(["git", "-C", src, "archive", "--format=zip", "-o", os.path.join(dst, "terminal-terrarium-source.zip"), "HEAD"])
    shutil.copy(os.path.join(src, "LICENSE"), dst)


def build_magic(src, out):
    """Pre-download every library piece the index lists, plus its lib/ files and licenses."""
    index = json.load(open(os.path.join(src, "site", "magic.json"), encoding="utf-8"))
    cdn = index["cdn"]
    lib = os.path.join(out, "magic-library")
    names = ["LICENSE", "NOTICE", "categories.json", "lib/kit.js", "lib/scene.js", "lib/image.js"]
    names += [f"pieces/{p['slug']}.js" for p in index["pieces"]]
    with concurrent.futures.ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda n: fetch(f"{cdn}/{n}", os.path.join(lib, *n.split("/"))), names))
    index = dict(index, cdn="offline", bundled=True)
    json.dump(index, open(os.path.join(lib, "index.json"), "w", encoding="utf-8"))
    open(os.path.join(lib, ".offline"), "w").close()
    say(f"magic library: {len(index['pieces'])} pieces")
    return lib


def build_website(src, out, magic_lib):
    site = os.path.join(src, "site")
    web = os.path.join(out, "website")
    os.makedirs(web)
    for name in ["index.html", "style.css", "app.js", "worker.js", "magic.js", "bundle.json", "gallery.json", "magic.json"]:
        shutil.copy(os.path.join(site, name), web)
    shutil.copytree(os.path.join(site, "shots"), os.path.join(web, "shots"))
    # Pyodide, locally
    for f in PYODIDE_FILES:
        fetch(PYODIDE_CDN + f, os.path.join(web, "pyodide", f))
    fetch(f"https://raw.githubusercontent.com/pyodide/pyodide/{PYODIDE}/LICENSE", os.path.join(web, "pyodide", "LICENSE"))
    # rewrite every external URL to a local one
    w = open(os.path.join(web, "worker.js"), encoding="utf-8").read()
    w = w.replace(f'from "{PYODIDE_CDN}pyodide.mjs"', 'from "./pyodide/pyodide.mjs"')
    w = w.replace(f'const PYODIDE = "{PYODIDE_CDN}";', 'const PYODIDE = new URL("./pyodide/", import.meta.url).href;')
    assert "cdn.jsdelivr" not in w, "worker.js still points at the CDN"
    open(os.path.join(web, "worker.js"), "w", encoding="utf-8", newline="\n").write(w)
    m = json.load(open(os.path.join(web, "magic.json"), encoding="utf-8"))
    m["cdn"] = "./magic-lib"
    json.dump(m, open(os.path.join(web, "magic.json"), "w", encoding="utf-8"))
    shutil.copytree(magic_lib, os.path.join(web, "magic-lib"))
    h = open(os.path.join(web, "index.html"), encoding="utf-8").read()
    h = "\n".join(line for line in h.split("\n") if "fonts.googleapis" not in line and "fonts.gstatic" not in line)
    open(os.path.join(web, "index.html"), "w", encoding="utf-8", newline="\n").write(h)


def build_extras(out):
    node = os.path.join(out, "extras", "node")
    for f in (f"node-{NODE}-win-x64.zip", f"node-{NODE}-linux-x64.tar.xz"):
        fetch(f"https://nodejs.org/dist/{NODE}/{f}", os.path.join(node, f))
    sums = fetch(f"https://nodejs.org/dist/{NODE}/SHASUMS256.txt").decode()
    for f in os.listdir(node):
        digest = hashlib.sha256(open(os.path.join(node, f), "rb").read()).hexdigest()
        assert f"{digest}  {f}" in sums, f"checksum mismatch for {f}"
    say(f"node {NODE}: checksums verified")
    pil = os.path.join(out, "extras", "pillow")
    for py in PILLOW_PYTHONS:
        for plat in PILLOW_PLATFORMS:
            run([sys.executable, "-m", "pip", "download", "pillow", "--only-binary=:all:", "--no-deps", "-q",
                 "--python-version", py, "--platform", plat, "-d", pil])


def write_docs(src, out, commit, n_scenes, n_pieces):
    tpl = open(os.path.join(src, "offline", "README-OFFLINE.md"), encoding="utf-8").read()
    tpl = (tpl.replace("{COMMIT}", commit).replace("{DATE}", datetime.date.today().isoformat())
              .replace("{SCENES}", str(n_scenes)).replace("{PIECES}", str(n_pieces)).replace("{NODE}", NODE))
    open(os.path.join(out, "README-OFFLINE.md"), "w", encoding="utf-8", newline="\n").write(tpl)
    shutil.copy(os.path.join(src, "offline", "install.py"), out)
    shutil.copy(os.path.join(src, "offline", "install-linux.sh"), out)
    shutil.copy(os.path.join(src, "offline", "serve-website.py"), out)
    bat = open(os.path.join(src, "offline", "install-windows.bat"), encoding="utf-8").read()
    open(os.path.join(out, "install-windows.bat"), "w", encoding="utf-8", newline="\r\n").write(bat.replace("\r\n", "\n"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep the unzipped bundle folder")
    a = ap.parse_args()
    stamp = datetime.date.today().strftime("%Y%m%d")
    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src")
        run(["git", "clone", "-q", ROOT, src])
        commit = subprocess.run(["git", "-C", src, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        run(["node", os.path.join(src, "scripts", "build-site.mjs")])
        name = f"terrarium-offline-{stamp}"
        out = os.path.join(tmp, name)
        os.makedirs(out)
        build_package(src, out)
        build_source(src, out)
        lib = build_magic(src, out)
        build_website(src, out, lib)
        build_extras(out)
        n_scenes = len(json.load(open(os.path.join(src, "site", "gallery.json"), encoding="utf-8")))
        n_pieces = len(json.load(open(os.path.join(lib, "index.json"), encoding="utf-8"))["pieces"])
        write_docs(src, out, commit, n_scenes, n_pieces)
        zpath = os.path.join(dist, name + ".zip")
        if os.path.exists(zpath):
            os.remove(zpath)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for d, _, files in os.walk(out):
                for f in files:
                    full = os.path.join(d, f)
                    z.write(full, os.path.join(name, os.path.relpath(full, out)))
        digest = hashlib.sha256(open(zpath, "rb").read()).hexdigest()
        open(zpath + ".sha256", "w").write(f"{digest}  {os.path.basename(zpath)}\n")
        if a.keep:
            keep = os.path.join(dist, name)
            if os.path.exists(keep):
                shutil.rmtree(keep)
            shutil.copytree(out, keep)
        say(f"{zpath}  {os.path.getsize(zpath) / 1e6:.1f} MB  sha256 {digest[:16]}...  ({n_scenes} scenes, {n_pieces} pieces, commit {commit})")


if __name__ == "__main__":
    main()
