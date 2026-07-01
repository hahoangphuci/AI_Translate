/**
 * Generate English policy HTML from VI templates + i18n bindings.
 * Usage: node frontend/scripts/generate_legal_en.mjs
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { JSDOM } from "jsdom";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

global.window = {};
eval(fs.readFileSync(path.join(root, "js", "i18n_data.js"), "utf8"));

const PAGE_BINDINGS = global.window.I18N_PAGE_BINDINGS;
const MESSAGES = global.window.I18N_MESSAGES;

const SLUG_FILES = {
  privacy: "privacy.html",
  terms: "terms.html",
  "data-deletion": "data-deletion.html",
  support: "support.html",
};

function buildEnHtml(slug, viInner) {
  const pagePath = `/${slug}`;
  const bindings = PAGE_BINDINGS[pagePath];
  if (!bindings) return "";

  const dom = new JSDOM(
    `<div id="wrap"><article class="legal-content glassmorphism">${viInner}</article></div>`,
  );
  const wrap = dom.window.document.getElementById("wrap");

  bindings.forEach((b) => {
    if (!b.sel || !b.key || !b.sel.includes("article.legal-content")) return;
    const val = MESSAGES.en[b.key];
    if (!val) return;
    wrap.querySelectorAll(b.sel).forEach((el) => {
      if (b.html) el.innerHTML = val;
      else el.textContent = val;
    });
  });

  return wrap.querySelector("article").innerHTML.trim();
}

const enPath = path.join(root, "config", "legal_pages_en.json");
let existing = {};
if (fs.existsSync(enPath)) {
  existing = JSON.parse(fs.readFileSync(enPath, "utf8"));
}

for (const [slug, filename] of Object.entries(SLUG_FILES)) {
  const htmlPath = path.join(root, "pages", filename);
  if (!fs.existsSync(htmlPath)) continue;
  const html = fs.readFileSync(htmlPath, "utf8");
  const match = html.match(
    /<article\s+class="legal-content glassmorphism">([\s\S]*?)<\/article>/i,
  );
  if (!match) continue;
  const enHtml = buildEnHtml(slug, match[1]);
  if (enHtml) existing[slug] = enHtml;
  console.log(`${slug}: ${enHtml ? enHtml.length + " chars" : "SKIP"}`);
}

fs.writeFileSync(enPath, JSON.stringify(existing, null, 2) + "\n", "utf8");
console.log("Wrote", enPath);
