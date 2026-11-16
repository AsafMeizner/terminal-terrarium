// terminal-terrarium playground: UI + canvas renderer. Python runs in worker.js.
import { loadIndex, loadPiece, MagicPlayer, paintFrame } from "./magic.js";

const $ = (id) => document.getElementById(id);
const tank = $("tank");
const art = $("art");
const glow = document.createElement("canvas"); // offscreen: a tiny copy of the art
const ctx = art.getContext("2d", { alpha: false });
const gctx = glow.getContext("2d");
const BG = "#070f12";
const FONT = '"JetBrains Mono", ui-monospace, Consolas, monospace';

const DEFAULTS = {
  scene: "jellyfish", seed: 0, theme: "natural", charset: "ascii",
  hue: 0, saturation: 1, brightness: 1, speed: 1, density: 1, cols: 0,
  fps: 30, paused: false, options: {},
};

let meta = null;
let cfg = { ...DEFAULTS, options: {} };
let rows = 0;
let cell = { w: 8, h: 16, font: 13, base: 0 };
let latest = null;
let drawPending = false;
let ready = false;
let lastFrameAt = 0;
let fpsEst = 0;
let workerMs = 0;
let glowTick = 0;
let colsChosen = false;
let laidCols = 0;
// "terrarium" = our Python scenes; "magic" = a piece from the ASCII Magic library (plain JS)
let mode = "terrarium";
let magicIndex = null;
const player = new MagicPlayer();
let magicRaf = 0;
let magicLast = 0;
let magicAcc = 0;

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ------------------------------------------------------------------ state <-> URL
function readHash() {
  const q = new URLSearchParams(location.hash.slice(1));
  const out = {};
  for (const k of ["scene", "theme", "charset"]) if (q.has(k)) out[k] = q.get(k);
  for (const k of ["seed", "hue", "saturation", "brightness", "speed", "density", "cols"]) {
    if (q.has(k) && !isNaN(parseFloat(q.get(k)))) out[k] = parseFloat(q.get(k));
  }
  out.options = {};
  for (const [k, v] of q) if (k.startsWith("o.")) out.options[k.slice(2)] = v;
  if (q.has("magic")) out.magic = q.get("magic");
  return out;
}

function writeHash() {
  const q = new URLSearchParams();
  if (mode === "magic") {
    q.set("magic", player.slug || "");
    for (const k of ["hue", "saturation", "brightness", "speed"]) if (cfg[k] !== DEFAULTS[k]) q.set(k, cfg[k]);
    history.replaceState(null, "", "#" + q.toString());
    return;
  }
  q.set("scene", cfg.scene);
  q.set("seed", cfg.seed);
  for (const k of ["theme", "charset", "hue", "saturation", "brightness", "speed", "density"]) {
    if (cfg[k] !== DEFAULTS[k]) q.set(k, cfg[k]);
  }
  if (colsChosen) q.set("cols", cfg.cols);
  for (const [k, v] of Object.entries(cfg.options)) q.set("o." + k, v);
  history.replaceState(null, "", "#" + q.toString());
}

// ------------------------------------------------------------------ worker
const worker = new Worker("worker.js", { type: "module" });
worker.onmessage = (e) => {
  const m = e.data;
  if (m.type === "status") setStatus(m.text);
  else if (m.type === "error") setStatus("Something broke in the Python side:\n" + m.text + "\n\nTry another scene or reload the page.", true);
  else if (m.type === "ready") onReady(m.meta);
  else if (m.type === "frame") {
    if (mode === "magic") return;
    latest = m;
    workerMs = workerMs * 0.9 + m.ms * 0.1;
    if (!drawPending) { drawPending = true; requestAnimationFrame(draw); }
  }
};

function setStatus(text, isError = false) {
  const s = $("status");
  s.hidden = !text;
  s.dataset.msg = text || "";
  s.textContent = text || "";
  s.classList.toggle("error", isError);
}

function send(restartClock = false) {
  if (!ready) return;
  worker.postMessage({ type: "configure", cfg: { ...cfg, rows }, restartClock });
  writeHash();
  updateCli();
}

// ------------------------------------------------------------------ layout + drawing
function layout() {
  const r = tank.getBoundingClientRect();
  if (!colsChosen) cfg.cols = Math.max(44, Math.min(160, Math.round(r.width / 8)));
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const cw = r.width / cfg.cols;
  const ch = cw * 2; // terminal cells are about twice as tall as wide; the scenes assume it
  const newRows = Math.max(8, Math.floor(r.height / ch));
  art.width = Math.round(r.width * dpr);
  art.height = Math.round(r.height * dpr);
  // the glow is a tiny copy of the art, upscaled by the browser: blur for free
  glow.width = Math.max(1, Math.round(r.width / 6));
  glow.height = Math.max(1, Math.round(r.height / 6));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  // fit the font so one glyph is one cell wide
  ctx.font = `100px ${FONT}`;
  const ratio = ctx.measureText("M").width / 100 || 0.6;
  const font = Math.min(cw / ratio, ch * 0.95);
  const yPad = (r.height - newRows * ch) / 2;
  cell = { w: cw, h: ch, font, yPad, dpr };
  ctx.font = `${font}px ${FONT}`;
  ctx.textBaseline = "middle";
  const changed = newRows !== rows || cfg.cols !== laidCols;
  rows = newRows;
  laidCols = cfg.cols;
  $("cols-out").textContent = `${cfg.cols} × ${rows}`;
  return changed;
}

const styleCache = new Map();
function cssColor(c) {
  let s = styleCache.get(c);
  if (!s) {
    s = "#" + (c & 0xffffff).toString(16).padStart(6, "0");
    styleCache.set(c, s);
  }
  return s;
}

function draw() {
  drawPending = false;
  const f = latest;
  if (!f) return;
  const n = cfg.cols * rows;
  if (f.chars.length !== n) return; // a frame from before a resize
  const r = tank.getBoundingClientRect();
  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, r.width, r.height);
  const { w: cw, h: ch, yPad } = cell;
  const chars = f.chars;
  const cols = f.colors;
  const W = cfg.cols;
  let last = -1;
  for (let i = 0; i < n; i++) {
    const c = cols[i];
    if (!c) continue;
    if (c !== last) { ctx.fillStyle = cssColor(c); last = c; }
    const y = (i / W) | 0;
    const x = i - y * W;
    ctx.fillText(chars[i], x * cw, yPad + y * ch + ch / 2);
  }
  applyGlow();
  const now = performance.now();
  if (lastFrameAt) fpsEst = fpsEst * 0.9 + (1000 / (now - lastFrameAt)) * 0.1;
  lastFrameAt = now;
}

function applyGlow() {
  if (tank.classList.contains("no-bloom")) return;
  // phosphor glow: shrink the frame to 1/6 size, then add it back stretched (soft = blurred)
  if ((glowTick ^= 1)) {
    gctx.clearRect(0, 0, glow.width, glow.height);
    gctx.drawImage(art, 0, 0, glow.width, glow.height);
  }
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalCompositeOperation = "lighter";
  ctx.globalAlpha = 0.45;
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(glow, 0, 0, art.width, art.height);
  ctx.restore();
}

// ------------------------------------------------------------------ ASCII Magic library
function magicColors() {
  // hue / saturation / brightness for library pieces (they bring their own palettes)
  art.style.filter = mode === "magic"
    ? `hue-rotate(${cfg.hue}deg) saturate(${cfg.saturation}) brightness(${cfg.brightness})` : "";
}

function magicLoop(now) {
  magicRaf = requestAnimationFrame(magicLoop);
  if (!player.draw) return;
  const fps = player.meta.fps || 20;
  const dt = magicLast ? Math.min(0.1, (now - magicLast) / 1000) : 0;
  magicLast = now;
  magicAcc += dt;
  if (magicAcc < 1 / fps && player.t > 0) return;
  const step = cfg.paused ? 0 : magicAcc * cfg.speed;
  magicAcc = 0;
  let out;
  try {
    out = player.frame(step);
  } catch (err) {
    setStatus("This library piece failed to draw: " + err.message, true);
    return;
  }
  const r = tank.getBoundingClientRect();
  ctx.setTransform(cell.dpr || 1, 0, 0, cell.dpr || 1, 0, 0);
  const size = paintFrame(ctx, out.frame, out.palette, out.square, r.width, r.height, FONT, BG);
  applyGlow();
  if (lastFrameAt) fpsEst = fpsEst * 0.9 + (1000 / (now - lastFrameAt)) * 0.1;
  lastFrameAt = now;
  $("cols-out").textContent = `${size.cols} x ${size.rows}`;
}

async function openMagic(slug) {
  const p = magicIndex && magicIndex.pieces.find((x) => x.slug === slug);
  if (!p) return;
  setStatus(`Loading ${p.name} from the ASCII Magic library...`);
  try {
    await player.open(slug);
  } catch (err) {
    setStatus(`That piece did not load (${err.message}). Check your connection and try again.`, true);
    return;
  }
  setStatus("");
  if (mode !== "magic") {
    mode = "magic";
    worker.postMessage({ type: "configure", cfg: { ...cfg, rows, paused: true } }); // rest the Python side
  }
  document.body.dataset.mode = "magic";
  magicColors();
  $("magic-list").value = slug;
  $("magic-note").textContent = p.note;
  $("scene-title").textContent = p.name;
  document.title = `${p.name}, terminal-terrarium`;
  $("interact").textContent = "";
  art.style.cursor = "default";
  magicLast = 0;
  magicAcc = 1;
  if (!magicRaf) magicRaf = requestAnimationFrame(magicLoop);
  writeHash();
  updateCli();
  markCurrentCard();
}

function stopMagic() {
  mode = "terrarium";
  document.body.dataset.mode = "terrarium";
  cancelAnimationFrame(magicRaf);
  magicRaf = 0;
  magicColors();
}

function leaveMagic() {
  if (mode !== "magic") return;
  stopMagic();
  syncControls();
  send(true);
}

function fillMagicList() {
  const list = $("magic-list");
  const q = $("magic-search").value.trim().toLowerCase();
  const cat = $("magic-cat").value;
  list.replaceChildren();
  const cats = new Map(magicIndex.categories.map((c) => [c.id, c.name]));
  const groups = new Map();
  for (const p of magicIndex.pieces) {
    if (cat && p.category !== cat) continue;
    if (q && !(p.name.toLowerCase().includes(q) || p.note.toLowerCase().includes(q))) continue;
    const g = cats.get(p.category) || "Other";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(p);
  }
  let n = 0;
  for (const [g, items] of groups) {
    const og = document.createElement("optgroup");
    og.label = g;
    for (const p of items) { og.append(new Option(p.name, p.slug)); n++; }
    list.append(og);
  }
  $("magic-count").textContent = `${n} pieces`;
  if (player.slug) list.value = player.slug;
}

async function initMagic() {
  magicIndex = await loadIndex();
  if (!magicIndex.pieces.length) { $("tab-magic").hidden = true; return; }
  $("tab-magic").textContent = `ASCII Magic library (${magicIndex.pieces.length})`;
  for (const c of magicIndex.categories) $("magic-cat").add(new Option(c.name, c.id));
  fillMagicList();
  $("magic-search").addEventListener("input", fillMagicList);
  $("magic-cat").addEventListener("change", fillMagicList);
  $("magic-list").addEventListener("change", () => openMagic($("magic-list").value));
  $("magic-random").addEventListener("click", () => {
    const opts = [...$("magic-list").options];
    if (opts.length) openMagic(opts[Math.floor(Math.random() * opts.length)].value);
  });
  $("tab-magic").addEventListener("click", () => {
    if (mode === "magic") return;
    const first = player.slug || ($("magic-list").options[0] && $("magic-list").options[0].value);
    if (first) openMagic(first);
  });
  $("tab-terrarium").addEventListener("click", leaveMagic);
  buildMagicGallery();
}

// the library also gets a gallery: still frames drawn live as cards scroll into view
function buildMagicGallery() {
  const cards = $("magic-cards");
  const filters = $("magic-filters");
  const cats = magicIndex.categories;
  const show = (id) => {
    cards.querySelectorAll("li").forEach((li) => { li.hidden = id !== "all" && li.dataset.cat !== id; });
    filters.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.cat === id)));
  };
  const counts = {};
  for (const p of magicIndex.pieces) counts[p.category] = (counts[p.category] || 0) + 1;
  for (const c of [{ id: "all", name: "All" }, ...cats]) {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.cat = c.id;
    b.textContent = c.id === "all" ? `All ${magicIndex.pieces.length}` : `${c.name} ${counts[c.id] || 0}`;
    b.addEventListener("click", () => show(c.id));
    filters.append(b);
  }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      io.unobserve(e.target);
      const cv = e.target;
      loadPiece(cv.dataset.slug).then((mod) => {
        const draw = mod.default();
        const f = draw(2.0);
        const c2 = cv.getContext("2d");
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        cv.width = cv.clientWidth * dpr;
        cv.height = cv.clientHeight * dpr;
        c2.setTransform(dpr, 0, 0, dpr, 0, 0);
        paintFrame(c2, f, (f && f.palette) || mod.meta.palette, mod.meta.cell === "square", cv.clientWidth, cv.clientHeight, FONT, BG);
      }).catch(() => { cv.replaceWith(Object.assign(document.createElement("span"), { className: "noshot", textContent: "preview unavailable" })); });
    }
  }, { rootMargin: "300px" });
  for (const p of magicIndex.pieces) {
    const li = document.createElement("li");
    li.dataset.cat = p.category;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "card";
    btn.dataset.magic = p.slug;
    const cv = document.createElement("canvas");
    cv.className = "thumb";
    cv.dataset.slug = p.slug;
    cv.setAttribute("aria-label", `${p.name}: ${p.note}`);
    const title = Object.assign(document.createElement("span"), { className: "card-title", textContent: p.name });
    const blurb = Object.assign(document.createElement("span"), { className: "card-blurb", textContent: p.note });
    btn.append(cv, title, blurb);
    btn.addEventListener("click", () => { window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" }); openMagic(p.slug); });
    li.append(btn);
    cards.append(li);
    io.observe(cv);
  }
  show("all");
}

setInterval(() => {
  if (ready && mode === "magic") { $("perf").textContent = `${fpsEst.toFixed(0)} fps, plain JavaScript`; return; }
  if (ready) $("perf").textContent = `${fpsEst.toFixed(0)} fps, ${workerMs.toFixed(1)} ms of Python per frame`;
}, 1000);

// ------------------------------------------------------------------ controls
function sceneMeta(name = cfg.scene) { return meta.scenes.find((s) => s.name === name); }

function choicesFrom(help) {
  // "mixed, pink, blue, moon or fire" -> ["mixed", "pink", ...]
  // "relativistic jets: on, off or random" -> the part after the colon
  const tail = help.includes(":") ? help.slice(help.lastIndexOf(":") + 1) : help;
  const head = tail.split(/[(;]/)[0];
  const parts = head.split(/,\s*|\s+or\s+/).map((s) => s.trim()).filter(Boolean);
  if (parts.length >= 2 && parts.every((p) => /^[a-z][a-z0-9_-]*$/.test(p))) return parts;
  return null;
}

function buildOptions() {
  const box = $("options");
  box.replaceChildren();
  for (const o of sceneMeta().options) {
    const id = "opt-" + o.key;
    const label = document.createElement("label");
    label.htmlFor = id;
    label.textContent = o.key;
    label.title = o.help;
    const current = cfg.options[o.key] ?? o.default;
    let input;
    if (o.type === "bool") {
      label.className = "check";
      input = document.createElement("input");
      input.type = "checkbox";
      input.checked = String(current).toLowerCase() === "true" || current === true || current === "1" || current === "on";
      label.prepend(input);
      input.addEventListener("change", () => setOption(o, input.checked ? "true" : "false"));
      input.id = id;
      box.append(label);
      const help = document.createElement("p");
      help.className = "hint";
      help.textContent = o.help;
      help.style.marginTop = "2px";
      box.append(help);
      continue;
    }
    const choices = o.type === "str" ? choicesFrom(o.help) : null;
    if (choices) {
      input = document.createElement("select");
      const all = choices.includes(String(o.default)) ? choices : [String(o.default), ...choices];
      for (const c of all) input.add(new Option(c, c));
      input.value = String(current);
    } else {
      input = document.createElement("input");
      input.type = o.type === "str" ? "text" : "number";
      if (o.type === "int") input.step = "1";
      if (o.type === "float") input.step = "0.1";
      input.value = current;
    }
    input.id = id;
    input.addEventListener("change", () => setOption(o, input.value));
    const help = document.createElement("p");
    help.className = "hint";
    help.style.marginTop = "2px";
    help.textContent = o.help;
    box.append(label, input, help);
  }
}

function setOption(o, value) {
  const clean = cleanOption(o, value);
  if (clean === null || String(clean) === String(o.default)) delete cfg.options[o.key];
  else cfg.options[o.key] = clean;
  send(true);
}

function syncControls() {
  markCurrentCard();
  const s = sceneMeta();
  $("scene").value = cfg.scene;
  $("blurb").textContent = s.blurb;
  $("interact").textContent = s.interactions ? `Try it: ${s.interactions} in the tank.` : "";
  art.style.cursor = s.interactions ? "crosshair" : "default";
  $("scene-title").textContent = s.title;
  document.title = `${s.title}, terminal-terrarium`;
  $("seed").value = cfg.seed;
  for (const k of ["theme", "charset"]) $(k).value = cfg[k];
  for (const k of ["hue", "saturation", "brightness", "speed", "density", "cols"]) $(k).value = cfg[k];
  $("hue-out").textContent = `${cfg.hue}°`;
  $("saturation-out").textContent = `${Number(cfg.saturation).toFixed(2)}×`;
  $("brightness-out").textContent = `${Number(cfg.brightness).toFixed(2)}×`;
  $("speed-out").textContent = `${Number(cfg.speed).toFixed(2)}×`;
  $("density-out").textContent = `${Number(cfg.density).toFixed(2)}×`;
  $("btn-pause").textContent = cfg.paused ? "Play" : "Pause";
  tank.classList.toggle("paused", cfg.paused);
}

function updateCli() {
  if (mode === "magic") {
    $("cli").textContent = `terrarium magic:${player.slug}`;
    $("cli-hint").textContent = "This piece in your terminal (library pieces need Node.js installed):";
    return;
  }
  $("cli-hint").textContent = "This exact scene in your terminal:";
  const s = sceneMeta();
  const parts = ["terrarium", cfg.scene, "--seed", cfg.seed];
  if (cfg.theme !== "natural") parts.push("-t", cfg.theme);
  if (cfg.charset !== "ascii") parts.push("--charset", cfg.charset);
  if (cfg.hue) parts.push("--hue", cfg.hue);
  if (cfg.saturation != 1) parts.push("--saturation", cfg.saturation);
  if (cfg.brightness != 1) parts.push("--brightness", cfg.brightness);
  if (cfg.speed != 1) parts.push("-s", cfg.speed);
  if (cfg.density != 1) parts.push("-d", cfg.density);
  for (const o of s.options) if (o.key in cfg.options) parts.push("-o", `${o.key}=${cfg.options[o.key]}`);
  $("cli").textContent = parts.map(shellQuote).join(" ");
}

// The command is meant to be pasted into a shell, and option values can come from a shared link:
// quote anything that isn't plainly safe.
function shellQuote(v) {
  const t = String(v);
  return /^[A-Za-z0-9_.,:=+\/-]+$/.test(t) ? t : "'" + t.replace(/'/g, "'\\''") + "'";
}

// Keep only option values that fit the option's declared type (or choices).
function cleanOption(o, raw) {
  const v = String(raw).replace(/[\x00-\x1f\x7f]/g, "").trim().slice(0, 40);
  if (o.type === "bool") return ["true", "false", "1", "0", "on", "off", "yes", "no"].includes(v.toLowerCase()) ? v.toLowerCase() : null;
  if (o.type === "int") return /^-?\d+$/.test(v) ? v : null;
  if (o.type === "float") return /^-?\d+(\.\d+)?$/.test(v) ? v : null;
  const choices = choicesFrom(o.help);
  if (choices) return choices.includes(v) || v === String(o.default) ? v : null;
  return /^[A-Za-z0-9_.+-]+$/.test(v) ? v : null; // free text: plain tokens or numbers only
}

function sanitizeOptions() {
  const s = sceneMeta();
  const out = {};
  for (const o of s.options) {
    if (o.key in cfg.options) {
      const v = cleanOption(o, cfg.options[o.key]);
      if (v !== null) out[o.key] = v;
    }
  }
  cfg.options = out;
}

function newSeed() { return Math.floor(Math.random() * 1e6); }

function setScene(name, { reseed = false } = {}) {
  if (mode === "magic") stopMagic();
  cfg.scene = name;
  cfg.options = {};
  if (reseed) cfg.seed = newSeed();
  buildOptions();
  syncControls();
  send(true);
}

function step(dir) {
  const names = meta.scenes.map((s) => s.name);
  const i = names.indexOf(cfg.scene);
  setScene(names[(i + dir + names.length) % names.length]);
}

function cycle(key, list, dir = 1) {
  const i = list.indexOf(cfg[key]);
  cfg[key] = list[(i + dir + list.length) % list.length];
  syncControls();
  send();
}

function togglePause() { cfg.paused = !cfg.paused; syncControls(); send(); }

function bindControls() {
  const sel = $("scene");
  for (const section of meta.sections) {
    const group = document.createElement("optgroup");
    group.label = section;
    for (const s of meta.scenes.filter((x) => x.section === section)) group.append(new Option(s.title, s.name));
    if (group.children.length) sel.append(group);
  }
  for (const t of meta.themes) $("theme").add(new Option(t, t));
  for (const c of meta.charsets) $("charset").add(new Option(c, c));

  sel.addEventListener("change", () => setScene(sel.value));
  $("prev").addEventListener("click", () => step(-1));
  $("next").addEventListener("click", () => step(1));
  $("shuffle").addEventListener("click", () => {
    const others = meta.scenes.filter((s) => s.name !== cfg.scene);
    setScene(others[Math.floor(Math.random() * others.length)].name, { reseed: true });
  });
  $("seed").addEventListener("change", () => { cfg.seed = Math.max(0, parseInt($("seed").value, 10) || 0); send(true); });
  $("reroll").addEventListener("click", () => { cfg.seed = newSeed(); syncControls(); send(true); });
  for (const k of ["theme", "charset"]) $(k).addEventListener("change", () => { cfg[k] = $(k).value; send(); });
  for (const k of ["hue", "saturation", "brightness", "speed", "density"]) {
    $(k).addEventListener("input", () => {
      cfg[k] = parseFloat($(k).value);
      syncControls();
      if (mode === "magic") { magicColors(); writeHash(); } else send();
    });
  }
  $("cols").addEventListener("input", () => { colsChosen = true; cfg.cols = parseInt($("cols").value, 10); layout(); syncControls(); send(); });
  $("bloom").addEventListener("change", () => tank.classList.toggle("no-bloom", !$("bloom").checked));
  $("reset-options").addEventListener("click", () => { cfg.options = {}; buildOptions(); send(true); });
  $("btn-pause").addEventListener("click", togglePause);
  $("btn-full").addEventListener("click", toggleFull);
  $("share").addEventListener("click", (e) => copy(location.href, e.currentTarget, "Link copied"));
  document.querySelectorAll("button.copy").forEach((b) =>
    b.addEventListener("click", () => copy($(b.dataset.copy).textContent, b, "Copied")));

  window.addEventListener("keydown", (e) => {
    if (e.target.closest("input, select, textarea") || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key;
    if (k === " ") { e.preventDefault(); togglePause(); }
    else if (k === "n" || k === "ArrowRight") step(1);
    else if (k === "p" || k === "ArrowLeft") step(-1);
    else if (k === "r") { cfg.seed = newSeed(); syncControls(); send(true); }
    else if (k === "t") cycle("theme", meta.themes);
    else if (k === "T") cycle("theme", meta.themes, -1);
    else if (k === "c") cycle("charset", meta.charsets);
    else if (k === "f") toggleFull();
  });

  // the mouse: scenes can react to pointing and clicking
  const toCell = (e) => {
    const r = art.getBoundingClientRect();
    return { x: (e.clientX - r.left) / cell.w, y: (e.clientY - r.top - cell.yPad) / cell.h };
  };
  let lastPoint = 0;
  art.addEventListener("pointermove", (e) => {
    const now = performance.now();
    if (now - lastPoint < 30) return; // ~30 updates a second is plenty
    lastPoint = now;
    const c = toCell(e);
    worker.postMessage({ type: "point", x: c.x, y: c.y });
  });
  art.addEventListener("pointerleave", () => worker.postMessage({ type: "point", x: -1, y: -1 }));
  art.addEventListener("pointerdown", (e) => {
    const c = toCell(e);
    worker.postMessage({ type: "click", x: c.x, y: c.y });
  });

  let resizeTimer = null;
  new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (layout()) send(true); else draw(); syncControls(); }, 120);
  }).observe(tank);
}

function toggleFull() {
  if (document.fullscreenElement) document.exitFullscreen();
  else tank.requestFullscreen?.();
}

async function copy(text, button, done) {
  try {
    await navigator.clipboard.writeText(text);
    const old = button.textContent;
    button.textContent = done;
    button.classList.add("done");
    setTimeout(() => { button.textContent = old; button.classList.remove("done"); }, 1400);
  } catch {
    button.textContent = "Select and copy";
  }
}

// ------------------------------------------------------------------ start
async function onReady(m) {
  meta = m;
  const fromHash = readHash();
  cfg = { ...DEFAULTS, ...fromHash, options: fromHash.options || {} };
  if (!sceneMeta(cfg.scene)) cfg.scene = DEFAULTS.scene;
  if (!("seed" in fromHash)) cfg.seed = newSeed();
  if (!meta.themes.includes(cfg.theme)) cfg.theme = "natural";
  if (!meta.charsets.includes(cfg.charset)) cfg.charset = "ascii";
  sanitizeOptions();
  if (reduceMotion) cfg.paused = true;
  colsChosen = "cols" in fromHash;
  await document.fonts.load(`16px "JetBrains Mono"`).catch(() => {});
  layout();
  bindControls();
  buildOptions();
  syncControls();
  ready = true;
  setStatus("");
  send(true);
  await initMagic();
  if (fromHash.magic) openMagic(fromHash.magic);
}

// ------------------------------------------------------------------ gallery
// Built from gallery.json (made at build time), so it shows before Python has loaded.
const SECTIONS = [
  ["Flowers", ["flowers"]],
  ["Trees & plants", ["plants"]],
  ["Creatures", ["creatures", "animals"]],
  ["Water & ocean", ["ocean", "water"]],
  ["Space", ["space"]],
  ["Sky, weather & places", ["sky", "weather", "night", "city", "fire"]],
  ["Abstract & retro", []],
];
const sectionOf = (tags) => (SECTIONS.find(([, want]) => !want.length || want.some((t) => tags.includes(t))) || SECTIONS[6])[0];

function openScene(name) {
  window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
  if (ready) setScene(name, { reseed: true });
  else location.hash = `scene=${encodeURIComponent(name)}`;
}

function markCurrentCard() {
  document.querySelectorAll(".card").forEach((c) => {
    const on = mode === "magic" ? c.dataset.magic === player.slug : c.dataset.scene === cfg.scene;
    c.setAttribute("aria-current", String(on));
  });
}

(async function buildGallery() {
  let items = [];
  try { items = await (await fetch("gallery.json")).json(); } catch { return; }
  const cards = $("cards");
  const filters = $("filters");
  const counts = {};
  for (const it of items) { it.section = sectionOf(it.tags); counts[it.section] = (counts[it.section] || 0) + 1; }
  const show = (section) => {
    cards.querySelectorAll("li").forEach((li) => { li.hidden = section !== "All" && li.dataset.section !== section; });
    filters.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.section === section)));
  };
  for (const name of ["All", ...SECTIONS.map(([s]) => s).filter((s) => counts[s])]) {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.section = name;
    b.textContent = name === "All" ? `All ${items.length}` : `${name} ${counts[name]}`;
    b.addEventListener("click", () => show(name));
    filters.append(b);
  }
  for (const it of items) {
    const li = document.createElement("li");
    li.dataset.section = it.section;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "card";
    btn.dataset.scene = it.name;
    if (it.shot) {
      const img = document.createElement("img");
      img.src = it.shot;
      img.alt = `${it.title}: ${it.blurb}`;
      img.loading = "lazy";
      btn.append(img);
    } else {
      const ph = document.createElement("span");
      ph.className = "noshot";
      ph.textContent = "no preview yet";
      btn.append(ph);
    }
    const title = document.createElement("span");
    title.className = "card-title";
    title.textContent = it.title;
    const blurb = document.createElement("span");
    blurb.className = "card-blurb";
    blurb.textContent = it.blurb;
    btn.append(title, blurb);
    if (it.interactions) {
      const m = document.createElement("span");
      m.className = "card-mouse";
      m.textContent = "Reacts to your mouse";
      btn.append(m);
    }
    btn.addEventListener("click", () => openScene(it.name));
    li.append(btn);
    cards.append(li);
  }
  show("All");
  markCurrentCard();
})();

// a little life while Python loads
(function loadingRamp() {
  const s = $("status");
  const ramp = " .:-=+*#%@";
  let i = 0;
  const t = setInterval(() => {
    if (ready || s.classList.contains("error")) return clearInterval(t);
    const k = i++ % (ramp.length * 2);
    const bar = Array.from({ length: 24 }, (_, j) => ramp[Math.abs(((j + k) % (ramp.length * 2)) - ramp.length) % ramp.length]).join("");
    s.textContent = `${s.dataset.msg || "Loading…"}\n\n${bar}`;
  }, 90);
})();
