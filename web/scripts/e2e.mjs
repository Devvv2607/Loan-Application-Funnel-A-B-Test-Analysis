// Runs Playwright with project-local browsers (installed under node_modules).
import { spawnSync } from "node:child_process";

const env = { ...process.env, PLAYWRIGHT_BROWSERS_PATH: "0" };
const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const r = spawnSync(npx, ["playwright", "test", ...process.argv.slice(2)], { stdio: "inherit", env, shell: true });
process.exit(r.status ?? 1);
