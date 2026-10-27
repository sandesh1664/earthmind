import { safeBrowserText, safeBrowserURL } from "./security";
import { expect, test, chromium, type Page } from "@playwright/test";
import { writeFile } from "node:fs/promises";
import { browserEvidencePath } from "./evidence";

async function openCity(page: Page) {
  await page.goto("/");
  const menu = page.getByRole("button", { name: "Open navigation", exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "City Explorer", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dubai digital twin", exact: true })).toBeVisible();
  // These preserved M03 regressions intentionally exercise the original fixture.
  // The default production catalog now contains real geography only.
  await page.getByRole("checkbox", {name: "Development datasets", exact: true}).check();
  await page.getByLabel("3D study region", {exact: true}).selectOption("8d31afa3-5d52-59b5-a8bc-691b5867dfcb");
}
async function ready(page: Page) {
  const scene = page.getByTestId("cesium-viewer");
  await expect(scene).toHaveAttribute("data-phase", "ready", { timeout: 45_000 });
  await expect(scene).toHaveAttribute("data-geometry-ready", "true");
  await expect(scene).toHaveAttribute("data-road-count", "8", { timeout: 30_000 });
  await expect(scene).toHaveAttribute("data-intersection-count", "6");
  await expect(scene.locator("canvas")).toHaveCount(1);
  await expect(scene).toHaveAttribute("data-camera-moving", "false");
  return scene;
}

test("M03 real Cesium globe, backend road picking, camera controls, layers and attribution", async ({ page }, info) => {
  const errors: string[] = [], workers: string[] = [], spatial: string[] = [], external: string[] = [];
  page.on("pageerror", (error) => errors.push(safeBrowserText(error.message)));
  page.on("console", (message) => { if (message.type() === "error") errors.push(safeBrowserText(message.text())); });
  page.on("worker", (worker) => workers.push(safeBrowserURL(worker.url())));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.includes("/api/geospatial/networks/") && /edges|intersections/.test(url.pathname)) spatial.push(url.toString());
    if (/^https?:/.test(url.protocol) && !["127.0.0.1", "localhost"].includes(url.hostname)) external.push(`${url.origin}${url.pathname}`);
  });
  const configuration = await (await page.request.get("/api/city/config")).json() as {diagnosticsEnabled:boolean};
  expect(configuration.diagnosticsEnabled, "Run CITY_DIAGNOSTICS_ENABLED=true make dev before native canvas-picking browser checks").toBe(true);
  await openCity(page);
  const scene = await ready(page);
  await expect(page.getByTestId("city-region-area")).toContainText("1.3398");
  await expect(page.getByTestId("city-source-license")).toContainText("Proprietary-Synthetic");
  const network = await page.getByLabel("3D network version", { exact: true }).inputValue();
  const response = await page.request.get(`/api/geospatial/networks/${network}/edges?limit=100&offset=0`);
  expect(response.status()).toBe(200);
  const backend = await response.json() as { features: { id: string; properties: {sumo_edge_id:string;lane_count:number;length_m:number} }[] };
  await page.getByRole("button", { name: "Zoom to study region", exact: true }).click();
  await page.getByRole("button", { name: "Top-down view", exact: true }).click();
  await expect(scene).toHaveAttribute("data-camera-moving", "true");
  await expect(scene).toHaveAttribute("data-camera-moving", "false");
  await expect.poll(async()=>{const id=await scene.getAttribute("data-pick-id");return backend.features.some(feature=>feature.id===id);}).toBe(true);
  const canvas = scene.locator("canvas");
  // The opt-in diagnostic is a projection from the actual Cesium scene. No
  // native Viewer is exposed, and picking still runs through the real canvas.
  await expect.poll(async () => Number(await scene.getAttribute("data-pick-x"))).toBeGreaterThan(0);
  await expect(scene).toHaveAttribute("data-camera-moving", "false");
  await expect(scene).toHaveAttribute("data-road-count", "8");
  await canvas.scrollIntoViewIfNeeded();
  const rect = await canvas.boundingBox();
  if (!rect) throw new Error("Cesium canvas has no actual layout");
  const x = Number(await scene.getAttribute("data-pick-x"));
  const y = Number(await scene.getAttribute("data-pick-y"));
  await page.mouse.click(rect.x+x, rect.y+y);
  await expect(page.getByTestId("selected-feature-id")).toBeVisible();
  const selectedId=await page.getByTestId("selected-feature-id").innerText();
  const selected=backend.features.find(feature=>feature.id===selectedId);
  expect(selected,"Native canvas pick must identify an actual fixture road").toBeDefined();
  await expect(page.getByTestId("selected-road-identifier")).toHaveText(selected!.properties.sumo_edge_id);
  await expect(page.getByTestId("selected-road-lanes")).toHaveText(String(selected!.properties.lane_count));
  await expect(page.getByTestId("selected-road-length")).toHaveText(selected!.properties.length_m.toLocaleString("en", {maximumFractionDigits:2}));
  await page.getByRole("button", { name: "Layers", exact: true }).click();
  const highlight = page.getByRole("checkbox", {name:"Selection highlight",exact:true});
  await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").highlight as boolean).toBe(true);
  await highlight.uncheck();
  await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").highlight as boolean).toBe(false);
  await highlight.check();
  await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").highlight as boolean).toBe(true);
  await page.getByRole("button", {name:"Close layers",exact:true}).click();
  await page.getByRole("button", { name: "Zoom to feature", exact: true }).click();
  await expect(page.getByTestId("camera-position")).toContainText("m altitude");
  await page.getByRole("button", { name: "Deselect", exact: true }).click();
  await page.getByRole("button", { name: "Zoom to study region", exact: true }).click();
  await ready(page);
  await page.getByRole("button", { name: "Layers", exact: true }).click();
  const buildingLayer = page.getByRole("checkbox", { name: "3D buildings", exact: true });
  // Synthetic development scope must not silently retain real OSM context.
  await expect(scene).toHaveAttribute("data-local-building-count","0");
  // A selected blocked layer can be switched off; it cannot be switched back
  // on without access. Neither state may retain real OSM building resources.
  await expect(buildingLayer).toBeEnabled();
  await buildingLayer.uncheck();
  await expect(buildingLayer).toBeDisabled();
  await expect(scene).toHaveAttribute("data-buildings-status","off");
  await expect(scene).toHaveAttribute("data-local-building-count","0");
  await expect(page.getByRole("checkbox", { name: "World terrain", exact: true })).toBeDisabled();
  const roads = page.getByRole("checkbox", { name: "Road centerlines", exact: true });
  await roads.uncheck();
  await expect(scene).toHaveAttribute("data-road-count", "0");
  await roads.check();
  await expect(scene).toHaveAttribute("data-road-count", "8");
  const nodes = page.getByRole("checkbox", { name: "Intersections", exact: true });
  await nodes.uncheck(); await expect(scene).toHaveAttribute("data-intersection-count", "0");
  await nodes.check(); await expect(scene).toHaveAttribute("data-intersection-count", "6");
  for (const [label,key] of [["Study region","boundary"],["Geographic basemap","imagery"],["Region centroid","centroid"]] as const) {
    const input = page.getByRole("checkbox", {name:label,exact:true});
    const previous = await input.isChecked();
    await input.setChecked(!previous);
    await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}")[key] as boolean).toBe(!previous);
    await input.setChecked(previous);
  }
  await page.getByRole("button", { name: "Close layers", exact: true }).click();
  await expect(page.locator(".cesium-widget-credits")).toContainText("Natural Earth");
  const creditsBox = await page.locator(".cesium-viewer-bottom").boundingBox();
  const legendBox = await page.locator(".city-map-legend").boundingBox();
  expect(creditsBox).not.toBeNull(); expect(legendBox).not.toBeNull();
  expect(creditsBox!.y + creditsBox!.height).toBeLessThan(legendBox!.y);
  const before = await page.getByTestId("camera-position").textContent();
  await page.getByRole("button", { name: "Business Bay", exact: true }).click();
  await expect.poll(() => page.getByTestId("camera-position").textContent()).not.toBe(before);
  await page.getByRole("button", { name: "Dubai overview", exact: true }).click();
  await expect.poll(() => page.getByTestId("camera-position").textContent()).not.toContain("2400 m");
  await page.getByRole("button", { name: "Downtown Dubai", exact: true }).click();
  await page.getByRole("button", { name: "Zoom to study region", exact: true }).click();
  await ready(page);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0,0));
  await page.screenshot({ path:browserEvidencePath(`city-${info.project.name}.png`), fullPage:true });
  expect(workers.length).toBeGreaterThan(0);
  expect(spatial.length).toBeGreaterThan(0);
  for (const value of spatial) {
    const query = new URL(value).searchParams;
    expect(Number(query.get("limit"))).toBeLessThanOrEqual(100);
    const bbox = query.get("bbox")?.split(",").map(Number);
    expect(bbox).toHaveLength(4);
    expect(bbox![2]!-bbox![0]!).toBeLessThanOrEqual(1);
  }
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
  await writeFile(browserEvidencePath(`city-network-${info.project.name}.json`), JSON.stringify({workers,spatialRequests:spatial,externalRequests:external,errors},null,2)+"\n");
});

test("M03 actual repeated navigation destroys the old viewer and restores one scene", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(safeBrowserText(error.message)));
  for (let cycle=0; cycle<3; cycle++) {
    await openCity(page); await ready(page);
    const menu = page.getByRole("button", {name:"Open navigation",exact:true});
    if (await menu.isVisible()) await menu.click();
    const contextReleased = await page.evaluate(async () => {
      const canvas = document.querySelector<HTMLCanvasElement>(".city-cesium-host canvas");
      const gl = canvas?.getContext("webgl2") ?? canvas?.getContext("webgl");
      const navigation = [...document.querySelectorAll<HTMLButtonElement>('nav[aria-label="Main navigation"] button')].find(button => button.textContent?.trim() === "Overview");
      if (!canvas || !gl || !navigation) throw new Error("Owned canvas or navigation unavailable");
      return new Promise<boolean>(resolve => {
        const lost = () => { clearTimeout(timer); resolve(gl.isContextLost()); };
        const timer = setTimeout(() => {canvas.removeEventListener("webglcontextlost",lost);resolve(false);},2000);
        canvas.addEventListener("webglcontextlost",lost,{once:true});
        navigation.click();
      });
    });
    expect(contextReleased).toBe(true);
    await expect(page.locator(".city-cesium-host canvas")).toHaveCount(0);
  }
  expect(errors).toEqual([]);
});

test("M03 actual browser without WebGL shows a usable metadata fallback", async ({ baseURL }, info) => {
  const browser = await chromium.launch({args:["--disable-webgl","--disable-webgl2"]});
  try {
    const context = await browser.newContext({baseURL:baseURL ?? "http://127.0.0.1:3000",viewport:info.project.use.viewport ?? {width:1440,height:1000}});
    const page = await context.newPage();
    await openCity(page);
    await expect(page.getByTestId("cesium-viewer")).toHaveAttribute("data-phase", "webgl-unavailable");
    await expect(page.getByTestId("city-region-area")).toContainText("km²");
    await expect(page.getByRole("button", {name:"Inspect road provisional:e0",exact:true})).toBeVisible();
    await page.getByRole("button", {name:"Inspect road provisional:e0",exact:true}).click();
    await expect(page.getByTestId("selected-road-identifier")).toHaveText("provisional:e0");
    await page.screenshot({path:browserEvidencePath(`webgl-fallback-${info.project.name}.png`),fullPage:true});
  } finally { await browser.close(); }
});
