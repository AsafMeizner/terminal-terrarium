"""Install terminal-terrarium from the offline bundle. No internet needed. Windows and Linux.

    python install.py             # terrarium + the ASCII Magic library (+ portable Node if you have none)
    python install.py --export    # also Pillow, for --snapshot/--record to PNG/GIF
    python install.py --no-node   # don't install the bundled Node.js
    python install.py --check     # just report what's installed

Only the Python standard library is used. Nothing is downloaded.
"""
import argparse
import glob
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOME_T = os.path.join(os.path.expanduser("~"), ".terrarium")
MAGIC_VERSION = "1.1.0"


def say(msg):
    print(f"[terrarium] {msg}", flush=True)


def pip_install(*args):
    cmd = [sys.executable, "-m", "pip", "install", "--no-index", *args]
    say(" ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        # externally-managed Pythons (Debian/Ubuntu 23+) refuse system-wide installs: retry for the user
        say("pip failed; retrying with --user --break-system-packages")
        r = subprocess.run(cmd + ["--user", "--break-system-packages"])
    return r.returncode == 0


def install_package():
    wheels = glob.glob(os.path.join(HERE, "wheels", "terminal_terrarium-*.whl"))
    if not wheels:
        sys.exit("no terrarium wheel found in wheels/")
    return pip_install("--force-reinstall", "--no-deps", wheels[0])


def install_pillow():
    if pip_install("--find-links", os.path.join(HERE, "extras", "pillow"), "pillow"):
        return True
    say("no matching Pillow wheel for this Python/OS; image export stays off (everything else works)")
    return False


def install_magic():
    src = os.path.join(HERE, "magic-library")
    dst = os.path.join(HOME_T, "magic", MAGIC_VERSION)
    if not os.path.isdir(src):
        say("no magic-library/ in the bundle; skipping the ASCII Magic library")
        return False
    os.makedirs(dst, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)
    open(os.path.join(dst, ".offline"), "w").close()  # never try the network
    say(f"ASCII Magic library -> {dst}")
    return True


def have_node():
    exe = shutil.which("node")
    if not exe:
        for cand in (os.path.join(HOME_T, "node", "node.exe"), os.path.join(HOME_T, "node", "bin", "node")):
            if os.path.isfile(cand):
                exe = cand
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
        major = int(out.lstrip("v").split(".")[0])
        return exe if major >= 18 else None
    except Exception:
        return None


def install_node():
    found = have_node()
    if found:
        say(f"Node.js already available: {found}")
        return True
    arch = platform.machine().lower()
    if arch not in ("amd64", "x86_64"):
        say(f"the bundled Node.js is for x64; this machine is {arch}. Install Node 18+ yourself for library pieces.")
        return False
    dst = os.path.join(HOME_T, "node")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    if os.name == "nt":
        archive = glob.glob(os.path.join(HERE, "extras", "node", "node-*-win-x64.zip"))
        if not archive:
            say("no Windows Node.js in extras/node/")
            return False
        with zipfile.ZipFile(archive[0]) as z:
            top = z.namelist()[0].split("/")[0]
            z.extractall(HOME_T)
        os.replace(os.path.join(HOME_T, top), dst)
    else:
        archive = glob.glob(os.path.join(HERE, "extras", "node", "node-*-linux-x64.tar.xz"))
        if not archive:
            say("no Linux Node.js in extras/node/")
            return False
        with tarfile.open(archive[0]) as t:
            top = t.getnames()[0].split("/")[0]
            t.extractall(HOME_T)
        os.replace(os.path.join(HOME_T, top), dst)
    say(f"portable Node.js -> {dst} (terrarium finds it there; it is not added to your PATH)")
    return True


def check():
    try:
        out = subprocess.run([sys.executable, "-m", "terrarium", "--version"], capture_output=True, text=True).stdout
        say(f"terrarium: {out.strip() or 'not installed'}")
    except Exception:
        say("terrarium: not installed")
    try:
        import PIL  # noqa: F401
        say("Pillow: installed (image export on)")
    except ImportError:
        say("Pillow: not installed (only needed for --snapshot/--record PNG/GIF)")
    lib = os.path.join(HOME_T, "magic", MAGIC_VERSION, "pieces")
    n = len(glob.glob(os.path.join(lib, "*.js")))
    say(f"ASCII Magic library: {n} pieces cached" + ("" if n else " (run install.py)"))
    say(f"Node.js: {have_node() or 'not found (needed only for magic:PIECE)'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", action="store_true", help="also install Pillow (PNG/GIF export)")
    ap.add_argument("--no-node", action="store_true", help="don't install the bundled Node.js")
    ap.add_argument("--no-magic", action="store_true", help="skip the ASCII Magic library")
    ap.add_argument("--check", action="store_true", help="only report what's installed")
    a = ap.parse_args()
    if sys.version_info < (3, 9):
        sys.exit(f"terrarium needs Python 3.9+, this is {platform.python_version()}")
    if a.check:
        check()
        return
    ok = install_package()
    if a.export:
        install_pillow()
    if not a.no_magic:
        install_magic()
        if not a.no_node:
            install_node()
    print()
    check()
    print()
    say("done. Try:  python -m terrarium   (or just: terrarium)")
    say("            python -m terrarium --list")
    say("            python -m terrarium magic:moonlit-sea")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
