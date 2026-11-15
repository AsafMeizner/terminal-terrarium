// Bundle the terrarium package (plus the browser bridge) into site/bundle.json for the web playground.
// Run: node scripts/build-site.mjs   (Vercel runs this as the build command)
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const files = {};

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) {
      if (name !== "__pycache__") walk(p);
    } else if (name.endsWith(".py")) {
      files[relative(root, p).split(sep).join("/")] = readFileSync(p, "utf8");
    }
  }
}

walk(join(root, "terrarium"));
files["terrarium_web.py"] = readFileSync(join(root, "site", "runner.py"), "utf8");
const version = (readFileSync(join(root, "terrarium", "__init__.py"), "utf8").match(/__version__ = "([^"]+)"/) || [])[1];
writeFileSync(join(root, "site", "bundle.json"), JSON.stringify({ version, files }));
const scenes = Object.keys(files).filter((f) => f.startsWith("terrarium/scenes/") && !f.endsWith("__init__.py"));
console.log(`site/bundle.json: ${Object.keys(files).length} files, ${scenes.length} scenes, v${version}`);

// Gallery: screenshots + a little metadata, so the grid shows before Python has loaded.
const shotsSrc = join(root, "docs", "screenshots");
const shotsDst = join(root, "site", "shots");
mkdirSync(shotsDst, { recursive: true });
const attr = (src, key) => {
  // class attributes look like:   name = "koi"    or    tags = ("water", "calm")
  const m = src.match(new RegExp(String.raw`^\s+${key}\s*=\s*("[^"]*"|\([^)]*\))`, "m"));
  if (!m) return null;
  const v = m[1];
  return v.startsWith("(") ? [...v.matchAll(/"([^"]*)"/g)].map((x) => x[1]) : v.slice(1, -1);
};
const gallery = [];
for (const f of scenes) {
  const src = files[f];
  const name = attr(src, "name");
  if (!name) continue;
  const shot = join(shotsSrc, name + ".png");
  if (existsSync(shot)) copyFileSync(shot, join(shotsDst, name + ".png"));
  gallery.push({
    name,
    title: attr(src, "title") || name,
    blurb: attr(src, "blurb") || "",
    tags: attr(src, "tags") || [],
    interactions: attr(src, "interactions") || "",
    shot: existsSync(shot) ? "shots/" + name + ".png" : null,
  });
}
gallery.sort((a, b) => a.name.localeCompare(b.name));
writeFileSync(join(root, "site", "gallery.json"), JSON.stringify(gallery));
console.log(`site/gallery.json: ${gallery.length} scenes, ${gallery.filter((g) => g.shot).length} with screenshots`);

