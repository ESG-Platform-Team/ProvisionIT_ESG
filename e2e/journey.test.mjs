// End-to-end browser tests: the analyst journey through the real interface.
//
// Runs Chromium against the website and API, with the fixture company TST,
// so nothing leaves the machine. Each test names the user story it checks
// (US-xx on the Confluence "User story" page).
//
//   Local:  ./demo.sh --reset   (in another terminal), then
//           cd e2e && npm install && npx playwright install chromium && npm test
//   Live:   E2E_BASE_URL=https://provisionit-esg.provisionit-esg.workers.dev npm test
//
// Against a deployed site the journey creates a throwaway account, so the
// site must allow sign-ups from the E2E_EMAIL_DOMAIN (default example.com).

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { chromium } from "playwright";

const BASE = process.env.E2E_BASE_URL || "http://localhost:8001";
const DOMAIN = process.env.E2E_EMAIL_DOMAIN || "example.com";
const RUN_TIMEOUT = Number(process.env.E2E_RUN_TIMEOUT || 120000);

let browser, page;
const errors = [];

before(async () => {
  browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1400, height: 900 }, acceptDownloads: true });
  page = await context.newPage();
  page.setDefaultTimeout(20000);
  page.on("pageerror", (e) => errors.push(String(e)));
});

after(async () => {
  await browser?.close();
});

test("US-36 a new analyst creates an account and lands on search", async () => {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.getByText("New here? Create an account").click();
  await page.fill("#auth-name", "E2E Tester");
  await page.fill("#auth-email", `e2e-${Date.now()}@${DOMAIN}`);
  await page.fill("#auth-password", "a long end-to-end password");
  await page.getByRole("button", { name: "CREATE ACCOUNT" }).click();
  await page.getByRole("button", { name: "SIGN OUT" }).waitFor();
  await page.locator('input[placeholder^="Company name"]').waitFor();
});

test("US-04 searching TST resolves to one company", async () => {
  await page.fill('input[placeholder^="Company name"]', "TST");
  await page.getByText("Fixture Test Group").first().waitFor();
});

test("US-06 the retrieval screen lists every source and its outcome", async () => {
  await page.getByRole("button", { name: "Assess", exact: true }).click();
  await page.getByRole("button", { name: "OPEN ASSESSMENT" }).waitFor({ timeout: RUN_TIMEOUT });
  const text = await page.locator("body").innerText();
  assert.match(text, /\d+ OF \d+ RETRIEVED/);
  assert.match(text, /RETRIEVED/);
  assert.match(text, /NOT FOUND ON SITE/, "a broken link must stay visible, not be dropped");
});

test("US-09 US-10 US-24 the scorecard shows three pillars, two scores and a separate confidence", async () => {
  await page.getByRole("button", { name: "OPEN ASSESSMENT" }).click();
  await page.getByText(/^transparency$/i).first().waitFor();
  const text = await page.locator("body").innerText();
  for (const pillar of ["GOVERNANCE", "ENVIRONMENTAL", "SOCIAL"]) {
    assert.ok(text.includes(pillar), `missing pillar ${pillar}`);
  }
  assert.ok(text.includes("PRACTICE"), "practice score missing");
  assert.ok(text.includes("EVIDENCE STRENGTH"), "source confidence missing");
  assert.ok(text.includes("never merged"), "the screen should say the two scores are never merged");
});

test("US-28 the scorecard states that software formed the assessment", async () => {
  const text = await page.locator("body").innerText();
  assert.ok(text.includes("MACHINE INTERPRETATION"));
  assert.ok(text.includes("formed by software, not by a person"));
});

test("US-14 US-16 each evidenced finding names its document and page", async () => {
  // Principle 01 opens expanded. An evidenced row shows its source grade and
  // "<document> p.<n>". (Opening the full quoted passage from the row is not
  // wired in the interface yet; the API serves it, see test_acceptance.py US-16.)
  await page.getByText("G1.1", { exact: true }).first().waitFor();
  const text = await page.locator("body").innerText();
  assert.match(text, /G1\.1[\s\S]{0,400}?\bp\.\d+/, "G1.1 should cite a document page");
});

test("US-20 the PDF report downloads", async () => {
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "DOWNLOAD PDF REPORT" }).click(),
  ]);
  assert.match(download.suggestedFilename(), /\.pdf$/);
});

test("US-21 the run appears in history", async () => {
  await page.getByRole("button", { name: /^history$/i }).click();
  await page.getByText("Fixture Test Group").first().waitFor();
});

test("the journey raised no uncaught page errors", () => {
  assert.deepEqual(errors, []);
});
