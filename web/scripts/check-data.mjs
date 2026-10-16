// Asserts every JSON the pages import exists, parses, is non-empty and is flagged simulated.
import fs from "node:fs";
import path from "node:path";

const src = fs.readFileSync(path.join("lib", "data.ts"), "utf-8");
const block = src.match(/DATA_FILES = \[([\s\S]*?)\] as const/)[1];
const names = [...block.matchAll(/"([^"]+)"/g)].map((m) => m[1]);
let failed = 0;
for (const n of names) {
  const p = path.join("public", "data", `${n}.json`);
  try {
    const raw = fs.readFileSync(p, "utf-8");
    const j = JSON.parse(raw);
    if (!raw.trim() || Object.keys(j).length === 0) throw new Error("empty");
    if (j.simulated !== true) throw new Error('missing "simulated": true');
    if (Array.isArray(j.rows) && j.rows.length === 0) throw new Error("no rows");
  } catch (e) {
    console.error(`check-data: ${p}: ${e.message}`);
    failed++;
  }
}
if (failed) process.exit(1);
console.log(`check-data: ${names.length} JSON files present, non-empty and flagged simulated`);
