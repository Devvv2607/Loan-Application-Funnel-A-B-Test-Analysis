// Post-build copy checks on the exported HTML.
import fs from "node:fs";
import path from "node:path";

const BANNER = "All data on this site is simulated.";
const required = ["index.html", "experiment/index.html", "recommendation/index.html"];
let failed = 0;
for (const f of required) {
  const html = fs.readFileSync(path.join("out", f), "utf-8");
  if (!html.includes(BANNER)) { console.error(`check-copy: banner missing on ${f}`); failed++; }
}
const pages = fs.readdirSync("out", { recursive: true }).filter((f) => String(f).endsWith(".html"));
for (const f of pages) {
  const html = fs.readFileSync(path.join("out", String(f)), "utf-8").toLowerCase();
  if (html.includes("default rate")) { console.error(`check-copy: "default rate" found in ${f}`); failed++; }
  if (!html.includes("simulated")) { console.error(`check-copy: no simulated-data label on ${f}`); failed++; }
}
if (failed) process.exit(1);
console.log(`check-copy: banner on ${required.length} key pages; ${pages.length} pages labelled simulated`);
