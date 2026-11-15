// Bundle the terrarium package (plus the browser bridge) into site/bundle.json for the web playground.
// Run: node scripts/build-site.mjs   (Vercel runs this as the build command)
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
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
