import { test, expect } from "@playwright/test";

test("real dashboard connectivity, worker diagnostic, navigation and responsive layout", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Platform overview", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("AI-Powered Urban Intelligence Platform", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("All systems operational", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run worker diagnostic", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Run worker diagnostic", exact: true })
    .click();
  await expect(page.locator(".job-status")).toHaveText("succeeded", {
    timeout: 30_000,
  });
  await expect(page.getByLabel("Diagnostic result")).toBeVisible();
  await page
    .getByRole("button", { name: "Verify SUMO runtime", exact: true })
    .click();
  await expect(page.locator(".job-heading")).toContainText(
    "SUMO runtime verification",
  );
  await expect(page.locator(".job-status")).toHaveText("succeeded", {
    timeout: 30_000,
  });
  await expect(page.getByLabel("Diagnostic result")).toContainText("verified");
  await expect(page.locator(".runtime-line")).toContainText("Verified");
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: `../../docs/evidence/m03/m01-regression-${info.project.name}.png`,
    fullPage: true,
  });
  const menu = page.getByRole("button", {
    name: "Open navigation",
    exact: true,
  });
  if (await menu.isVisible()) await menu.click();
  const city = page.getByRole("button", { name: "Scenario Studio", exact: true });
  await city.focus();
  await expect(city).toBeFocused();
  await city.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Scenario Studio", exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText(
      "This workflow is reserved for a later milestone and is not enabled yet.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Return to overview" }).click();
  await expect(
    page.getByRole("heading", { name: "Platform overview", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("UI-only mocked dependency failure shows honest error state and supports retry", async ({
  page,
}) => {
  let unavailable = true;
  await page.route("**/api/health", async (route) => {
    if (unavailable)
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        headers: { "X-Earthmind-Api-Reachable": "true" },
        body: JSON.stringify({
          status: "degraded",
          service: "api",
          checks: { database: "ok", redis: "ok", worker: "error" },
        }),
      });
    else await route.continue();
  });
  await page.goto("/");
  await expect(
    page
      .getByRole("alert")
      .getByText("Some services need attention", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run worker diagnostic", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("article").filter({ hasText: "Simulation worker" }),
  ).toContainText("Unavailable");
  unavailable = false;
  await page.getByRole("button", { name: "Retry checks", exact: true }).click();
  await expect(
    page.getByText("All systems operational", { exact: true }),
  ).toBeVisible();
});
