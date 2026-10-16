import { expect, test } from "@playwright/test";
import path from "node:path";

const PAGES = ["", "funnel", "experiment", "guardrails", "recommendation", "methodology", "simulation",
  "reproducibility", "about"];
const WIDTHS = [1440, 1024, 768, 375];
const SHOTS = path.join(__dirname, "..", "..", "..", "tests", "screenshots");

for (const width of WIDTHS) {
  for (const page of PAGES) {
    const name = page || "home";
    test(`${name} has no horizontal scroll at ${width}px`, async ({ page: p }) => {
      await p.setViewportSize({ width, height: 900 });
      await p.goto(`/${page}${page ? "/" : ""}`);
      await p.waitForLoadState("networkidle");
      await p.waitForTimeout(300);
      const { scrollWidth, clientWidth } = await p.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));
      await p.screenshot({ path: path.join(SHOTS, `${name}-${width}.png`), fullPage: true });
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
    });
  }
}

test("simulated-data banner on home, experiment and recommendation", async ({ page }) => {
  for (const url of ["/", "/experiment/", "/recommendation/"]) {
    await page.goto(url);
    await expect(page.getByTestId("sim-banner").first()).toContainText("All data on this site is simulated");
  }
});
