// Print-test: render the Recommendation page to an A4 PDF (print media) and report the page count.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const out = path.resolve("..", "tests", "print", "recommendation-a4.pdf");
fs.mkdirSync(path.dirname(out), { recursive: true });
const server = spawn(process.execPath, ["scripts/serve.mjs"], { env: { ...process.env, PORT: "4174" } });
await new Promise((r) => setTimeout(r, 800));
try {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("http://localhost:4174/recommendation/", { waitUntil: "networkidle" });
  await page.emulateMedia({ media: "print" });
  await page.pdf({ path: out, format: "A4", printBackground: true, preferCSSPageSize: true });
  await browser.close();
} finally {
  server.kill();
}
const pdf = fs.readFileSync(out, "latin1");
const pages = (pdf.match(/\/Type\s*\/Page[^s]/g) || []).length;
console.log(`print-memo: ${pages} A4 page(s) -> ${path.relative(path.resolve(".."), out)}`);
process.exit(pages === 1 ? 0 : 1);
