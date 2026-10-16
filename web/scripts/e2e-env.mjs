// Runs a node script with project-local Playwright browsers (under node_modules).
import { spawnSync } from "node:child_process";

const r = spawnSync(process.execPath, process.argv.slice(2), {
  stdio: "inherit", env: { ...process.env, PLAYWRIGHT_BROWSERS_PATH: "0" },
});
process.exit(r.status ?? 1);
