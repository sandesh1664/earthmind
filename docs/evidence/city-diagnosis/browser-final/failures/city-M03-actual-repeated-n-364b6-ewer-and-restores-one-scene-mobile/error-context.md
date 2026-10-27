# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: city.spec.ts >> M03 actual repeated navigation destroys the old viewer and restores one scene
- Location: tests/browser/city.spec.ts:142:1

# Error details

```
Error: expect(locator).toHaveAttribute(expected) failed

Locator:  getByTestId('cesium-viewer')
Expected: "8"
Received: "0"
Timeout:  30000ms

Call log:
  - Expect "toHaveAttribute" getByTestId('cesium-viewer') with timeout 30000ms
  - waiting for getByTestId('cesium-viewer')
    5 × locator resolved to <div data-phase="ready" data-road-count="0" data-camera-moving="true" data-geometry-ready="true" class="city-viewer-surface" data-testid="cesium-viewer" data-intersection-count="0" data-imagery-status="loading" data-local-building-count="0" data-buildings-status="blocked" data-render-diagnostics="{"globeVisible":true,"globeTilesLoaded":false,"imageryLayerCount":1,"boundaryFillAlpha":0.13}" data-layer-visibility="{"boundary":true,"roads":false,"intersections":false,"centroid":false,"highlight":false…>…</div>
      - unexpected value "0"
    - locator resolved to <div data-phase="ready" data-road-count="0" data-camera-moving="true" data-geometry-ready="true" class="city-viewer-surface" data-testid="cesium-viewer" data-imagery-status="ready" data-intersection-count="0" data-local-building-count="0" data-buildings-status="blocked" data-render-diagnostics="{"globeVisible":true,"globeTilesLoaded":true,"imageryLayerCount":1,"boundaryFillAlpha":0.13}" data-layer-visibility="{"boundary":true,"roads":false,"intersections":false,"centroid":false,"highlight":false,"b…>…</div>
    56 × unexpected value "0"
       - locator resolved to <div data-phase="ready" data-road-count="0" data-geometry-ready="true" data-camera-moving="false" class="city-viewer-surface" data-testid="cesium-viewer" data-imagery-status="ready" data-intersection-count="0" data-local-building-count="0" data-buildings-status="blocked" data-render-diagnostics="{"globeVisible":true,"globeTilesLoaded":true,"imageryLayerCount":1,"boundaryFillAlpha":0.13}" data-layer-visibility="{"boundary":true,"roads":false,"intersections":false,"centroid":false,"highlight":false,"…>…</div>
    - unexpected value "0"

```

```yaml
- link "Cesium ion":
  - /url: https://cesium.com/
  - img "Cesium ion"
- text: Made with Natural Earth · public domain
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
> 20  |   await expect(scene).toHaveAttribute("data-road-count", "8", { timeout: 30_000 });
      |                       ^ Error: expect(locator).toHaveAttribute(expected) failed
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
  38  |   expect(configuration.diagnosticsEnabled, "Run CITY_DIAGNOSTICS_ENABLED=true make dev before native canvas-picking browser checks").toBe(true);
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
  88  |   // A selected blocked layer can be switched off; it cannot be switched back
  89  |   // on without access. Neither state may retain real OSM building resources.
  90  |   await expect(buildingLayer).toBeEnabled();
  91  |   await buildingLayer.uncheck();
  92  |   await expect(buildingLayer).toBeDisabled();
  93  |   await expect(scene).toHaveAttribute("data-buildings-status","off");
  94  |   await expect(scene).toHaveAttribute("data-local-building-count","0");
  95  |   await expect(page.getByRole("checkbox", { name: "World terrain", exact: true })).toBeDisabled();
  96  |   const roads = page.getByRole("checkbox", { name: "Road centerlines", exact: true });
  97  |   await roads.uncheck();
  98  |   await expect(scene).toHaveAttribute("data-road-count", "0");
  99  |   await roads.check();
  100 |   await expect(scene).toHaveAttribute("data-road-count", "8");
  101 |   const nodes = page.getByRole("checkbox", { name: "Intersections", exact: true });
  102 |   await nodes.uncheck(); await expect(scene).toHaveAttribute("data-intersection-count", "0");
  103 |   await nodes.check(); await expect(scene).toHaveAttribute("data-intersection-count", "6");
  104 |   for (const [label,key] of [["Study region","boundary"],["Geographic basemap","imagery"],["Region centroid","centroid"]] as const) {
  105 |     const input = page.getByRole("checkbox", {name:label,exact:true});
  106 |     const previous = await input.isChecked();
  107 |     await input.setChecked(!previous);
  108 |     await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}")[key] as boolean).toBe(!previous);
  109 |     await input.setChecked(previous);
  110 |   }
  111 |   await page.getByRole("button", { name: "Close layers", exact: true }).click();
  112 |   await expect(page.locator(".cesium-widget-credits")).toContainText("Natural Earth");
  113 |   const creditsBox = await page.locator(".cesium-viewer-bottom").boundingBox();
  114 |   const legendBox = await page.locator(".city-map-legend").boundingBox();
  115 |   expect(creditsBox).not.toBeNull(); expect(legendBox).not.toBeNull();
  116 |   expect(creditsBox!.y + creditsBox!.height).toBeLessThan(legendBox!.y);
  117 |   const before = await page.getByTestId("camera-position").textContent();
  118 |   await page.getByRole("button", { name: "Business Bay", exact: true }).click();
  119 |   await expect.poll(() => page.getByTestId("camera-position").textContent()).not.toBe(before);
  120 |   await page.getByRole("button", { name: "Dubai overview", exact: true }).click();
```