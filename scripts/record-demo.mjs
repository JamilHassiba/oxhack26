// Reproducible, isolated simulation recording. Requires frontend npm ci + Playwright Chromium.
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
const { chromium } = createRequire(import.meta.url)(
  "../frontend/node_modules/playwright",
);
const output = fileURLToPath(new URL("../docs/demo/", import.meta.url));
const temporary = await mkdtemp(join(tmpdir(), "concierge-recording-"));
const server = spawn(
  "npm",
  ["run", "dev", "--", "--host", "127.0.0.1", "--port", "5180", "--strictPort"],
  {
    cwd: new URL("../frontend/", import.meta.url),
    env: { ...process.env, VITE_DEMO_MODE: "true" },
    stdio: "ignore",
  },
);
let browser;
try {
  let ready = false;
  for (let i = 0; i < 60; i++) {
    try {
      if ((await fetch("http://127.0.0.1:5180")).ok) {
        ready = true;
        break;
      }
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  if (!ready) throw new Error("Local demo server did not start on port 5180.");
  await mkdir(output, { recursive: true });
  browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    recordVideo: { dir: temporary, size: { width: 1440, height: 1000 } },
  });
  const page = await context.newPage();
  const video = page.video();
  await page.goto("http://127.0.0.1:5180/agents");
  await page.getByRole("heading", { name: "Maya", exact: true }).waitFor();
  await page.screenshot({ path: join(output, "agents.png"), fullPage: true });
  await page.waitForTimeout(1800);
  await page.getByRole("button", { name: "Enter agent", exact: true }).click();
  await page.getByRole("button", { name: "Book a table" }).click();
  await page.waitForTimeout(800);
  await page.getByRole("button", { name: "Send message" }).click();
  const approve = page.getByRole("button", { name: "Approve £20.00" });
  await approve.waitFor({ timeout: 15000 });
  await page.screenshot({ path: join(output, "approval.png"), fullPage: true });
  await page.waitForTimeout(2000);
  await approve.click();
  await page.getByText("All taken care of.", { exact: true }).waitFor();
  await page.waitForTimeout(1800);
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "History", exact: true })
    .click();
  await page.locator(".history-row").click();
  await page.getByText("Call transcript", { exact: true }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(output, "task.png"), fullPage: true });
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Calendar", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Dinner at The Ivy Oxford · 4 guests" })
    .waitFor();
  await page.waitForTimeout(1500);
  await page.getByRole("link", { name: "Analytics" }).click();
  await page.getByText("100%", { exact: true }).first().waitFor();
  await page.waitForTimeout(1500);
  await context.close();
  await video.saveAs(join(output, "fallback-demo.webm"));
  console.log(
    "Saved the simulated fallback video and three screenshots in docs/demo/.",
  );
} finally {
  await browser?.close();
  server.kill("SIGTERM");
  await rm(temporary, { recursive: true, force: true });
}
