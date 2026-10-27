# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: city.spec.ts >> M03 real Cesium globe, backend road picking, camera controls, layers and attribution
- Location: tests/browser/city.spec.ts:27:1

# Error details

```
Error: Run CITY_DIAGNOSTICS_ENABLED=true make dev before native canvas-picking browser checks

expect(received).toBe(expected) // Object.is equality

Expected: true
Received: false
```

# Test source

```ts
  1   | import { expect, test, chromium, type Page } from "@playwright/test";
  2   | import { writeFile } from "node:fs/promises";
  3   | import { browserEvidencePath } from "./evidence";
  4   | 
  5   | async function openCity(page: Page) {
  6   |   await page.goto("/");
  7   |   const menu = page.getByRole("button", { name: "Open navigation", exact: true });
  8   |   if (await menu.isVisible()) await menu.click();
  9   |   await page.getByRole("button", { name: "City Explorer", exact: true }).click();
  10  |   await expect(page.getByRole("heading", { name: "Dubai digital twin", exact: true })).toBeVisible();
  11  |   // These preserved M03 regressions intentionally exercise the original fixture.
  12  |   // The default production catalog now contains real geography only.
  13  |   await page.getByRole("checkbox", {name: "Development datasets", exact: true}).check();
  14  |   await page.getByLabel("3D study region", {exact: true}).selectOption("8d31afa3-5d52-59b5-a8bc-691b5867dfcb");
  15  | }
  16  | async function ready(page: Page) {
  17  |   const scene = page.getByTestId("cesium-viewer");
  18  |   await expect(scene).toHaveAttribute("data-phase", "ready", { timeout: 45_000 });
  19  |   await expect(scene).toHaveAttribute("data-geometry-ready", "true");
  20  |   await expect(scene).toHaveAttribute("data-road-count", "8", { timeout: 30_000 });
  21  |   await expect(scene).toHaveAttribute("data-intersection-count", "6");
  22  |   await expect(scene.locator("canvas")).toHaveCount(1);
  23  |   await expect(scene).toHaveAttribute("data-camera-moving", "false");
  24  |   return scene;
  25  | }
  26  | 
  27  | test("M03 real Cesium globe, backend road picking, camera controls, layers and attribution", async ({ page }, info) => {
  28  |   const errors: string[] = [], workers: string[] = [], spatial: string[] = [], external: string[] = [];
  29  |   page.on("pageerror", (error) => errors.push(error.message));
  30  |   page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  31  |   page.on("worker", (worker) => workers.push(worker.url()));
  32  |   page.on("request", (request) => {
  33  |     const url = new URL(request.url());
  34  |     if (url.pathname.includes("/api/geospatial/networks/") && /edges|intersections/.test(url.pathname)) spatial.push(url.toString());
  35  |     if (/^https?:/.test(url.protocol) && !["127.0.0.1", "localhost"].includes(url.hostname)) external.push(`${url.origin}${url.pathname}`);
  36  |   });
  37  |   const configuration = await (await page.request.get("/api/city/config")).json() as {diagnosticsEnabled:boolean};
> 38  |   expect(configuration.diagnosticsEnabled, "Run CITY_DIAGNOSTICS_ENABLED=true make dev before native canvas-picking browser checks").toBe(true);
      |                                                                                                                                      ^ Error: Run CITY_DIAGNOSTICS_ENABLED=true make dev before native canvas-picking browser checks
  39  |   await openCity(page);
  40  |   const scene = await ready(page);
  41  |   await expect(page.getByTestId("city-region-area")).toContainText("1.3398");
  42  |   await expect(page.getByTestId("city-source-license")).toContainText("Proprietary-Synthetic");
  43  |   const network = await page.getByLabel("3D network version", { exact: true }).inputValue();
  44  |   const response = await page.request.get(`/api/geospatial/networks/${network}/edges?limit=100&offset=0`);
  45  |   expect(response.status()).toBe(200);
  46  |   const backend = await response.json() as { features: { id: string; properties: {sumo_edge_id:string;lane_count:number;length_m:number} }[] };
  47  |   await page.getByRole("button", { name: "Zoom to study region", exact: true }).click();
  48  |   await page.getByRole("button", { name: "Top-down view", exact: true }).click();
  49  |   await expect(scene).toHaveAttribute("data-camera-moving", "true");
  50  |   await expect(scene).toHaveAttribute("data-camera-moving", "false");
  51  |   await expect.poll(async()=>{const id=await scene.getAttribute("data-pick-id");return backend.features.some(feature=>feature.id===id);}).toBe(true);
  52  |   const canvas = scene.locator("canvas");
  53  |   // The opt-in diagnostic is a projection from the actual Cesium scene. No
  54  |   // native Viewer is exposed, and picking still runs through the real canvas.
  55  |   await expect.poll(async () => Number(await scene.getAttribute("data-pick-x"))).toBeGreaterThan(0);
  56  |   await expect(scene).toHaveAttribute("data-camera-moving", "false");
  57  |   await expect(scene).toHaveAttribute("data-road-count", "8");
  58  |   await canvas.scrollIntoViewIfNeeded();
  59  |   const rect = await canvas.boundingBox();
  60  |   if (!rect) throw new Error("Cesium canvas has no actual layout");
  61  |   const x = Number(await scene.getAttribute("data-pick-x"));
  62  |   const y = Number(await scene.getAttribute("data-pick-y"));
  63  |   await page.mouse.click(rect.x+x, rect.y+y);
  64  |   await expect(page.getByTestId("selected-feature-id")).toBeVisible();
  65  |   const selectedId=await page.getByTestId("selected-feature-id").innerText();
  66  |   const selected=backend.features.find(feature=>feature.id===selectedId);
  67  |   expect(selected,"Native canvas pick must identify an actual fixture road").toBeDefined();
  68  |   await expect(page.getByTestId("selected-road-identifier")).toHaveText(selected!.properties.sumo_edge_id);
  69  |   await expect(page.getByTestId("selected-road-lanes")).toHaveText(String(selected!.properties.lane_count));
  70  |   await expect(page.getByTestId("selected-road-length")).toHaveText(selected!.properties.length_m.toLocaleString("en", {maximumFractionDigits:2}));
  71  |   await page.getByRole("button", { name: "Layers", exact: true }).click();
  72  |   const highlight = page.getByRole("checkbox", {name:"Selection highlight",exact:true});
  73  |   await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").highlight as boolean).toBe(true);
  74  |   await highlight.uncheck();
  75  |   await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").highlight as boolean).toBe(false);
  76  |   await highlight.check();
  77  |   await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").highlight as boolean).toBe(true);
  78  |   await page.getByRole("button", {name:"Close layers",exact:true}).click();
  79  |   await page.getByRole("button", { name: "Zoom to feature", exact: true }).click();
  80  |   await expect(page.getByTestId("camera-position")).toContainText("m altitude");
  81  |   await page.getByRole("button", { name: "Deselect", exact: true }).click();
  82  |   await page.getByRole("button", { name: "Zoom to study region", exact: true }).click();
  83  |   await ready(page);
  84  |   await page.getByRole("button", { name: "Layers", exact: true }).click();
  85  |   const buildingLayer = page.getByRole("checkbox", { name: "3D buildings", exact: true });
  86  |   // Synthetic development scope must not silently retain real OSM context.
  87  |   await expect(scene).toHaveAttribute("data-local-building-count","0");
  88  |   await expect(buildingLayer).toBeDisabled();
  89  |   await expect(page.getByRole("checkbox", { name: "World terrain", exact: true })).toBeDisabled();
  90  |   const roads = page.getByRole("checkbox", { name: "Road centerlines", exact: true });
  91  |   await roads.uncheck();
  92  |   await expect(scene).toHaveAttribute("data-road-count", "0");
  93  |   await roads.check();
  94  |   await expect(scene).toHaveAttribute("data-road-count", "8");
  95  |   const nodes = page.getByRole("checkbox", { name: "Intersections", exact: true });
  96  |   await nodes.uncheck(); await expect(scene).toHaveAttribute("data-intersection-count", "0");
  97  |   await nodes.check(); await expect(scene).toHaveAttribute("data-intersection-count", "6");
  98  |   for (const [label,key] of [["Study region","boundary"],["Geographic basemap","imagery"],["Region centroid","centroid"]] as const) {
  99  |     const input = page.getByRole("checkbox", {name:label,exact:true});
  100 |     const previous = await input.isChecked();
  101 |     await input.setChecked(!previous);
  102 |     await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}")[key] as boolean).toBe(!previous);
  103 |     await input.setChecked(previous);
  104 |   }
  105 |   await page.getByRole("button", { name: "Close layers", exact: true }).click();
  106 |   await expect(page.locator(".cesium-widget-credits")).toContainText("Natural Earth");
  107 |   const creditsBox = await page.locator(".cesium-viewer-bottom").boundingBox();
  108 |   const legendBox = await page.locator(".city-map-legend").boundingBox();
  109 |   expect(creditsBox).not.toBeNull(); expect(legendBox).not.toBeNull();
  110 |   expect(creditsBox!.y + creditsBox!.height).toBeLessThan(legendBox!.y);
  111 |   const before = await page.getByTestId("camera-position").textContent();
  112 |   await page.getByRole("button", { name: "Business Bay", exact: true }).click();
  113 |   await expect.poll(() => page.getByTestId("camera-position").textContent()).not.toBe(before);
  114 |   await page.getByRole("button", { name: "Dubai overview", exact: true }).click();
  115 |   await expect.poll(() => page.getByTestId("camera-position").textContent()).not.toContain("2400 m");
  116 |   await page.getByRole("button", { name: "Downtown Dubai", exact: true }).click();
  117 |   await page.getByRole("button", { name: "Zoom to study region", exact: true }).click();
  118 |   await ready(page);
  119 |   await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  120 |   await page.evaluate(() => window.scrollTo(0,0));
  121 |   await page.screenshot({ path:browserEvidencePath(`city-${info.project.name}.png`), fullPage:true });
  122 |   expect(workers.length).toBeGreaterThan(0);
  123 |   expect(spatial.length).toBeGreaterThan(0);
  124 |   for (const value of spatial) {
  125 |     const query = new URL(value).searchParams;
  126 |     expect(Number(query.get("limit"))).toBeLessThanOrEqual(100);
  127 |     const bbox = query.get("bbox")?.split(",").map(Number);
  128 |     expect(bbox).toHaveLength(4);
  129 |     expect(bbox![2]!-bbox![0]!).toBeLessThanOrEqual(1);
  130 |   }
  131 |   expect(errors).toEqual([]);
  132 |   expect(external).toEqual([]);
  133 |   await writeFile(browserEvidencePath(`city-network-${info.project.name}.json`), JSON.stringify({workers,spatialRequests:spatial,externalRequests:external,errors},null,2)+"\n");
  134 | });
  135 | 
  136 | test("M03 actual repeated navigation destroys the old viewer and restores one scene", async ({ page }) => {
  137 |   const errors: string[] = [];
  138 |   page.on("pageerror", error => errors.push(error.message));
```