import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const base = process.env.PLATFORM_TEST_URL || "http://localhost:5185";
  await page.goto(base);
  await page.getByRole("button", { name: "Ingresar", exact: true }).waitFor();
  assert.match(await page.title(), /ABISSOL/);
  assert.equal(await page.getByText("Versión 2", { exact: true }).count(), 1);
  const settingsStatus = await page.evaluate(async () =>
    (await fetch("http://localhost:8015/abissol/api/v1/ui-settings", { credentials: "include" })).status);
  assert.equal(settingsStatus, 200);
  const health = await page.request.get("http://localhost:8015/health/ready");
  assert.equal(health.status(), 200);
  assert.equal((await health.json()).database, "connected");
  assert.deepEqual(errors, []);
  console.log("Acceso React, identidad ABISSOL V2 y API/MariaDB: OK.");
} finally {
  await browser.close();
}
