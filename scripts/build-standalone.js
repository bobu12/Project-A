/*
 * Build a single self-contained HTML file from the app.
 *
 * Inlines css/styles.css and every js module into index.html, producing
 * dist/GCC-Markets-Dashboard.html — one file you can open by double-clicking,
 * with no server, folders, or external requests.
 *
 * Run with:  node scripts/build-standalone.js   (or: npm run build)
 */
"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "dist");
const OUT_FILE = path.join(OUT_DIR, "GCC-Markets-Dashboard.html");

// Order matters: framework before providers, app last.
const JS_FILES = [
  "js/data.js",
  "js/providers/base.js",
  "js/providers/mock.js",
  "js/providers/yahoo.js",
  "js/providers/twelvedata.js",
  "js/providers/eodhd.js",
  "js/app.js",
];

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

function esc(str) {
  return str.replace(/[.*+?^/${}()|[\]\\]/g, "\\$&");
}

let html = read("index.html");
const css = read("css/styles.css");
const js = JS_FILES.map((f) => "/* ===== " + f + " ===== */\n" + read(f)).join("\n\n");

// 1. Inline the stylesheet.
html = html.replace(
  /<link rel="stylesheet" href="css\/styles.css" \/>/,
  "<style>\n" + css + "\n</style>"
);

// 2. Strip the provider-modules comment and each external <script src>.
html = html.replace(/\s*<!-- Provider modules[^>]*-->/g, "");
JS_FILES.forEach((f) => {
  html = html.replace(
    new RegExp('\\s*<script src="' + esc(f) + '"></script>', "g"),
    ""
  );
});

// 3. Inject one combined inline script just before </body>.
html = html.replace(/<\/body>/, "<script>\n" + js + "\n</script>\n</body>");

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.writeFileSync(OUT_FILE, html);

const externalRefs = (html.match(/(src|href)="(js|css)\//g) || []).length;
console.log("Wrote " + path.relative(ROOT, OUT_FILE) + " (" + html.length + " bytes)");
console.log("Remaining external js/css refs: " + externalRefs + (externalRefs === 0 ? "  ✓" : "  ✗"));
if (externalRefs !== 0) process.exit(1);
