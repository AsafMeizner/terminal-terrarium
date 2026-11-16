// Plays pieces from the ASCII Magic library (github.com/kailashsr38/ascii-magic-art, MIT)
// on the playground canvas. Pieces are ES modules loaded from the published npm package:
// create() returns draw(t) -> a string, or { text, color } where color holds one palette key per
// character and meta.palette maps keys to hex colours.

let index = null;
const SHADE = { "░": 0.28, "▒": 0.52, "▓": 0.76, "█": 1 };

export async function loadIndex() {
  if (index) return index;
  try {
    index = await (await fetch("magic.json")).json();
  } catch {
    index = { pieces: [], categories: [] };
  }
  return index;
}

const moduleCache = new Map();
export function loadPiece(slug) {
  if (!moduleCache.has(slug)) moduleCache.set(slug, import(`${index.cdn}/pieces/${slug}.js`));
  return moduleCache.get(slug);
}

/** Paint one frame into a 2D context, fitted and centred in (w, h) CSS pixels. */
export function paintFrame(ctx, frame, palette, square, w, h, font, bg = "#070f12") {
  const text = typeof frame === "string" ? frame : frame.text;
  const color = typeof frame === "string" ? null : frame.color;
  const lines = text.split("\n");
  const clines = color ? color.split("\n") : null;
  const rows = lines.length;
  const cols = Math.max(1, ...lines.map((l) => l.length));
  const aspect = square ? 1 : 2; // cell height / width
  const cw = Math.min(w / cols, h / (rows * aspect));
  const ch = cw * aspect;
  const ox = (w - cols * cw) / 2;
  const oy = (h - rows * ch) / 2;
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);
  ctx.textBaseline = "middle";
  ctx.font = `${Math.min(cw / 0.6, ch * 0.95)}px ${font}`;
  const fallback = "#c8d6d2";
  let last = "";
  for (let y = 0; y < rows; y++) {
    const line = lines[y];
    const cl = clines ? clines[y] || "" : "";
    for (let x = 0; x < line.length; x++) {
      const c = line[x];
      if (c === " ") continue;
      const key = cl[x];
      const hex = (key && key !== " " && palette && palette[key]) || fallback;
      if (hex !== last) { ctx.fillStyle = hex; last = hex; }
      const yy = oy + y * ch;
      if (c === "▀" || c === "▄") {
        // half blocks: fill exactly so pixel art has no seams
        ctx.fillRect(ox + x * cw, c === "▀" ? yy : yy + ch / 2, cw + 0.5, ch / 2 + 0.5);
      } else if (SHADE[c]) {
        // shade blocks as solid cells at 25/50/75/100% strength: smooth, no font seams
        ctx.globalAlpha = SHADE[c];
        ctx.fillRect(ox + x * cw, yy, cw + 0.5, ch + 0.5);
        ctx.globalAlpha = 1;
      } else {
        ctx.fillText(c, ox + x * cw, oy + y * ch + ch / 2);
      }
    }
  }
  return { cols, rows };
}

/** A running piece. */
export class MagicPlayer {
  constructor() {
    this.draw = null;
    this.meta = null;
    this.t = 0;
    this.slug = null;
  }

  async open(slug) {
    const mod = await loadPiece(slug);
    this.meta = mod.meta || {};
    this.draw = mod.default();
    this.slug = slug;
    this.t = 0;
    return this.meta;
  }

  frame(dt) {
    this.t += dt;
    const f = this.draw(this.t);
    return { frame: f, palette: (f && f.palette) || this.meta.palette, square: this.meta.cell === "square" };
  }
}
