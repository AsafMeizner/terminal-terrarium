// Index the ASCII Magic library (github.com/kailashsr38/ascii-magic-art, MIT) for the web playground.
// Writes site/magic.json: one entry per piece (slug, name, category, note, cell, size).
// The pieces themselves are loaded in the browser from the published npm package on jsDelivr.
// Run: node scripts/build-magic.mjs   (build-site.mjs calls it; failure just leaves the library out)
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const MAGIC_VERSION = "1.1.0";
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const CDN = `https://cdn.jsdelivr.net/npm/ascii-magic-art@${MAGIC_VERSION}`;
// These two are halftone renderings of Unsplash photos (Unsplash License, not MIT): leave them out.
const EXCLUDE = new Set(["ocean-sunset", "starry-ridge"]);
// Several arcade pieces are recreations of specific famous games; we don't feature them.
const EXCLUDE_CATEGORIES = new Set(["arcade"]);

const str = (src, key) => {
  const m = src.match(new RegExp(String.raw`\b${key}\s*:\s*"((?:[^"\\]|\\.)*)"`));
  return m ? m[1] : "";
};
const num = (src, key) => {
  const m = src.match(new RegExp(String.raw`\b${key}\s*:\s*(\d+)`));
  return m ? Number(m[1]) : 0;
};

export async function buildMagic() {
  const listing = await (await fetch(`https://data.jsdelivr.com/v1/packages/npm/ascii-magic-art@${MAGIC_VERSION}?structure=flat`)).json();
  const slugs = listing.files
    .map((f) => f.name)
    .filter((n) => n.startsWith("/pieces/") && n.endsWith(".js"))
    .map((n) => n.slice("/pieces/".length, -3))
    .filter((s) => !EXCLUDE.has(s));
  const categories = await (await fetch(`${CDN}/categories.json`)).json();
  const pieces = [];
  let next = 0;
  async function worker() {
    while (next < slugs.length) {
      const slug = slugs[next++];
      try {
        const src = await (await fetch(`${CDN}/pieces/${slug}.js`)).text();
        const head = src.slice(0, src.indexOf("export default") > 0 ? src.indexOf("export default") : 4000);
        const category = str(head, "category");
        if (EXCLUDE_CATEGORIES.has(category)) continue;
        pieces.push({
          slug,
          name: str(head, "name") || slug,
          category,
          note: str(head, "note"),
          cell: str(head, "cell") || "text",
          cols: num(head, "cols"),
          rows: num(head, "rows"),
          fps: num(head, "fps") || 20,
        });
      } catch {
        /* skip a piece we couldn't read */
      }
    }
  }
  await Promise.all(Array.from({ length: 16 }, worker));
  pieces.sort((a, b) => a.name.localeCompare(b.name));
  const used = new Set(pieces.map((p) => p.category));
  const out = { version: MAGIC_VERSION, cdn: CDN, categories: categories.filter((c) => used.has(c.id)), pieces };
  writeFileSync(join(root, "site", "magic.json"), JSON.stringify(out));
  return out;
}

if (import.meta.url === `file:///${process.argv[1].replace(/\\/g, "/")}` || process.argv[1]?.endsWith("build-magic.mjs")) {
  const out = await buildMagic();
  console.log(`site/magic.json: ${out.pieces.length} ASCII Magic pieces in ${out.categories.length} categories`);
}
