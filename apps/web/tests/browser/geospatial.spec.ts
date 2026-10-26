import { test, expect } from "@playwright/test";

async function openGeospatial(page: import("@playwright/test").Page) {
  await page.goto("/");
  const menu = page.getByRole("button", {
    name: "Open navigation",
    exact: true,
  });
  if (await menu.isVisible()) await menu.click();
  await page
    .getByRole("button", { name: "Geospatial Data", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Geospatial data management",
      exact: true,
    }),
  ).toBeVisible();
}

test("M02 real PostGIS fixture, network validation and provenance render without replacing M01", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await openGeospatial(page);
  await expect(
    page.getByRole("heading", {
      name: "Downtown Dubai — Synthetic Study Region",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Synthetic study data", { exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("region-area")).toContainText("km²");
  await expect(page.getByTestId("region-bounds")).toContainText("55.");
  await expect(
    page.getByRole("img", {
      name: "Illustrative study region boundary in longitude and latitude",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator(".geo-map-heading svg")).toHaveCSS("height", "13px");
  await expect
    .poll(() =>
      page.locator(".geo-boundary > svg").evaluate((svg) =>
        svg.getBoundingClientRect().height,
      ),
    )
    .toBeGreaterThanOrEqual(180);
  await expect(page.locator("footer")).toContainText("MILESTONE M03");
  await expect(page.getByTestId("network-node-count")).toHaveText("6");
  await expect(page.getByTestId("network-edge-count")).toHaveText("8");
  await expect(page.locator(".geo-validation")).toHaveText(/VALID/);
  await expect(page.getByTestId("source-license")).not.toBeEmpty();
  await expect(
    page.getByText(
      "Topology checks do not establish real-world network accuracy.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: `../../docs/evidence/m03/geospatial-${info.project.name}.png`,
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("M02 UI-only empty dataset is honest", async ({ page }) => {
  await page.route("**/api/geospatial/regions?*", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ items: [], total: 0, limit: 100, offset: 0 }),
    }),
  );
  await openGeospatial(page);
  await expect(
    page.getByRole("heading", {
      name: "No study regions registered",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", {
      name: "Illustrative study region boundary in longitude and latitude",
      exact: true,
    }),
  ).toHaveCount(0);
});

test("M02 UI-only service error supports retry", async ({ page }) => {
  let unavailable = true;
  await page.route("**/api/geospatial/regions?*", async (route) => {
    if (unavailable)
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "Unavailable" }),
      });
    else await route.continue();
  });
  await openGeospatial(page);
  await expect(
    page
      .getByRole("alert")
      .getByText(
        "Study regions are unavailable. Check the spatial service and retry.",
        { exact: true },
      ),
  ).toBeVisible();
  unavailable = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Downtown Dubai — Synthetic Study Region",
      exact: true,
    }),
  ).toBeVisible();
});
