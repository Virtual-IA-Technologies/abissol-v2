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
  assert.equal(await page.getByRole("heading", { name: "Bienvenido a ABISSOL" }).count(), 1);
  const logo = page.locator('img[src="/abissol-logo.png"]');
  await logo.waitFor();
  assert.equal(await logo.evaluate(image => image.complete && image.naturalWidth > 0), true);
  await page.getByRole("button", { name: "Mostrar contraseña", exact: true }).click();
  assert.equal(await page.locator("#password").getAttribute("type"), "text");
  await page.getByRole("button", { name: "Ocultar contraseña", exact: true }).click();
  await page.screenshot({ path: "../../.local/login-green-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: "../../.local/login-green-mobile.png", fullPage: true });
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
