// Runs one ASCII Magic piece (github.com/kailashsr38/ascii-magic-art, MIT) for terrarium.
// terrarium starts this with Node, then asks for frames over stdin/stdout:
//   argv: <slug> <cacheDir> <cdnBase>
//   stdout line 1: {"ok":true,"meta":{...}}   (or {"error":"..."})
//   then for every line "t" (seconds) on stdin: one JSON frame {"text":...,"color":...,"palette":...}
// Pieces and their lib/ files are downloaded once from the published npm package and cached.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import { createInterface } from "node:readline";

const [slug, cacheDir, cdn] = process.argv.slice(2);
const say = (obj) => process.stdout.write(JSON.stringify(obj) + "\n");

async function fetchCached(rel) {
  const file = join(cacheDir, rel);
  try {
    return [file, await readFile(file, "utf8")];
  } catch {
    const res = await fetch(`${cdn}/${rel}`);
    if (!res.ok) throw new Error(`download failed (${res.status}) for ${rel}`);
    const src = await res.text();
    await mkdir(dirname(file), { recursive: true });
    await writeFile(file, src);
    return [file, src];
  }
}

// download a module and, recursively, the relative modules it imports
async function ensure(rel, seen = new Set()) {
  if (seen.has(rel)) return;
  seen.add(rel);
  const [, src] = await fetchCached(rel);
  for (const m of src.matchAll(/(?:from|import)\s*\(?\s*["'](\.{1,2}\/[^"']+)["']/g)) {
    const next = join(dirname(rel), m[1]).split("\\").join("/");
    await ensure(next, seen);
  }
}

try {
  if (!/^[a-z0-9-]+$/.test(slug || "")) throw new Error("bad piece name");
  const rel = `pieces/${slug}.js`;
  await ensure(rel);
  const mod = await import(pathToFileURL(join(cacheDir, rel)).href);
  const meta = mod.meta || {};
  const draw = mod.default();
  say({ ok: true, meta: { name: meta.name, note: meta.note, fps: meta.fps || 20, cell: meta.cell || "text", palette: meta.palette || {} } });
  const rl = createInterface({ input: process.stdin });
  rl.on("line", (line) => {
    const t = Number(line) || 0;
    try {
      const f = draw(t);
      if (typeof f === "string") say({ text: f });
      else say({ text: f.text, color: f.color, palette: f.palette });
    } catch (e) {
      say({ error: String(e && e.message ? e.message : e) });
    }
  });
  rl.on("close", () => process.exit(0));
} catch (e) {
  say({ error: String(e && e.message ? e.message : e) });
  process.exit(1);
}
