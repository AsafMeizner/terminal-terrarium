// Runs Python (Pyodide) off the main thread and streams frames to the page.
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/pyodide.mjs";

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/";

let py = null;
let runner = null;
let fps = 30;
let timer = null;
let last = 0;
let busy = false;

async function init() {
  try {
    post({ type: "status", text: "Loading Python in your browser…" });
    py = await loadPyodide({ indexURL: PYODIDE });
    post({ type: "status", text: "Planting the terrarium…" });
    const bundle = await (await fetch("bundle.json", { cache: "no-cache" })).json();
    const root = "/home/pyodide/";
    for (const [path, src] of Object.entries(bundle.files)) {
      const parts = path.split("/");
      let dir = root;
      for (const p of parts.slice(0, -1)) {
        dir += p + "/";
        try { py.FS.mkdir(dir); } catch (e) { /* exists */ }
      }
      py.FS.writeFile(root + path, src);
    }
    py.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
    py.runPython("from terrarium_web import runner");
    runner = py.globals.get("runner");
    post({ type: "ready", meta: JSON.parse(runner.meta()), version: bundle.version });
  } catch (err) {
    post({ type: "error", text: String(err && err.message ? err.message : err) });
  }
}

function post(msg, transfer) { self.postMessage(msg, transfer || []); }

function tick() {
  if (!runner || busy) return;
  busy = true;
  const now = performance.now();
  const dt = last ? (now - last) / 1000 : 1 / fps;
  last = now;
  try {
    const out = runner.step(dt);
    const chars = out.get(0);
    const proxy = out.get(1);
    const bytes = proxy.toJs();
    proxy.destroy();
    out.destroy();
    const colors = new Uint32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    post({ type: "frame", chars, colors, ms: performance.now() - now }, [colors.buffer]);
  } catch (err) {
    stop();
    post({ type: "error", text: String(err && err.message ? err.message : err) });
  }
  busy = false;
}

let lastCfg = {};
function paused() { return !!lastCfg.paused; }

function start() { stop(); last = 0; timer = setInterval(tick, 1000 / fps); }
function stop() { if (timer) clearInterval(timer); timer = null; }

self.onmessage = (e) => {
  const msg = e.data;
  if (msg.type === "click" && runner) { try { runner.click(msg.x, msg.y); if (paused()) tick(); } catch (err) { post({ type: "error", text: String(err) }); } return; }
  if (msg.type === "point" && runner) { try { runner.point(msg.x, msg.y); } catch (err) { /* ignore */ } return; }
  if (msg.type === "configure" && runner) {
    try {
      lastCfg = msg.cfg;
      fps = Math.max(5, Math.min(60, msg.cfg.fps || 30));
      runner.configure(JSON.stringify(msg.cfg));
      if (!timer || msg.restartClock) start();
      if (msg.cfg.paused) tick();
    } catch (err) {
      post({ type: "error", text: String(err && err.message ? err.message : err) });
    }
  }
};

init();
