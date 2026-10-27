import { expect, test, type Page } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { CityRoadCollectionSchema } from "../../lib/city/api";
import type { RoadFeature } from "../../lib/city/types";

test.skip(Boolean(process.env.CI) && process.env.EARTHMIND_REAL_GEO_TESTS !== "true", "Real-geography CI checks require the explicitly requested OSM import workflow; offline CI does not fabricate a real-data PASS.");

type Observation = {
  errors: string[];
  httpFailures: string[];
  externalRequests: string[];
  edgeRequests: string[];
  roads: Map<string, RoadFeature>;
  navigationToRoadReadyMs: number | null;
};

function observeActualServices(page: Page): Observation {
  const observation: Observation = {
    errors: [], httpFailures: [], externalRequests: [], edgeRequests: [], roads: new Map(), navigationToRoadReadyMs:null,
  };
  page.on("pageerror", error => observation.errors.push(error.message));
  page.on("console", message => {
    if (message.type() === "error") observation.errors.push(message.text());
  });
  page.on("request", request => {
    const url = new URL(request.url());
    if (/^https?:$/.test(url.protocol) && !["127.0.0.1", "localhost"].includes(url.hostname)) {
      observation.externalRequests.push(`${url.origin}${url.pathname}`);
    }
  });
  page.on("response", async response => {
    const url = new URL(response.url());
    if (response.status() >= 400 && /\/(api|geography|cesium|_next)\//.test(url.pathname)) {
      observation.httpFailures.push(`${response.status()} ${url.pathname}`);
    }
    if (url.pathname.startsWith("/api/geospatial/networks/") && url.pathname.endsWith("/edges") && response.ok()) {
      observation.edgeRequests.push(response.url());
      try {
        const collection = CityRoadCollectionSchema.parse(await response.json());
        for (const feature of collection.features) observation.roads.set(feature.id, feature);
      } catch (error) {
        // Camera movement deliberately cancels stale responses. Only that exact
        // transport cancellation is expected; schema/server failures remain errors.
        if (response.request().failure()?.errorText === "net::ERR_ABORTED") return;
        observation.errors.push(`Actual edge-response validation failed: ${String(error)}`);
      }
    }
  });
  return observation;
}

async function openRealCity(page: Page, observation: Observation) {
  const configurationResponse = await page.request.get("/api/city/config");
  expect(configurationResponse.status()).toBe(200);
  const configuration = await configurationResponse.json() as { diagnosticsEnabled: boolean; imageryMode: string };
  expect(configuration.diagnosticsEnabled, "Run CITY_DIAGNOSTICS_ENABLED=true make dev before native picking checks").toBe(true);
  expect(configuration.imageryMode, "This check verifies the actual self-hosted OSM context without third-party tiles").toBe("local-osm");
  const navigationStarted = performance.now();
  await page.goto("/");
  await expect(page.getByRole("heading", {name:"Dubai digital twin", exact:true})).toBeVisible();
  await expect(page.getByRole("checkbox", {name:"Development datasets", exact:true})).not.toBeChecked();
  await expect(page.getByTestId("city-geographic-source")).toHaveText("REAL GEOGRAPHIC DATA — OpenStreetMap");
  const scene = page.getByTestId("cesium-viewer");
  // The initial empty scene can report geometryReady before the PostGIS query
  // finishes. Require one coherent native-scene snapshot with actual roads;
  // cold GroundPolyline/context preparation has its own explicit 60s budget.
  await expect.poll(() => scene.evaluate(element => ({
    phase:element.getAttribute("data-phase"),
    hasRoads:Number(element.getAttribute("data-road-count"))>0,
    geometryReady:element.getAttribute("data-geometry-ready")==="true",
    cameraSettled:element.getAttribute("data-camera-moving")==="false",
    canvases:element.querySelectorAll("canvas").length,
  })), {timeout:60_000,message:"Actual PostGIS roads must be nonempty and native geometry ready"}).toEqual({
    phase:"ready",hasRoads:true,geometryReady:true,cameraSettled:true,canvases:1,
  });
  observation.navigationToRoadReadyMs=Math.round(performance.now()-navigationStarted);
  console.log(`Actual fresh-context navigation to nonempty ready roads: ${observation.navigationToRoadReadyMs}ms`);
  return scene;
}

async function assertNoFatalOrExternalRequests(observation: Observation) {
  expect(observation.errors).toEqual([]);
  expect(observation.httpFailures).toEqual([]);
  // These tests operate on the retained local OSM extract. No public tile-server
  // requests, fake geographic responses or token-backed provider calls are used.
  expect(observation.externalRequests).toEqual([]);
}

test("recovery real OSM default, native road picking, source metadata, layers and height-tagged context", async ({page}, info) => {
  test.setTimeout(90_000);
  const observation = observeActualServices(page);
  const scene = await openRealCity(page,observation);
  const regionId = await page.getByLabel("3D study region", {exact:true}).inputValue();
  const networkId = await page.getByLabel("3D network version", {exact:true}).inputValue();
  const regionResponse = await page.request.get(`/api/geospatial/regions/${regionId}`);
  const networkResponse = await page.request.get(`/api/geospatial/networks/${networkId}`);
  expect(regionResponse.status()).toBe(200);
  expect(networkResponse.status()).toBe(200);
  const region = await regionResponse.json() as {metadata:{is_synthetic:boolean};bounds:number[];area_km2:number};
  const network = await networkResponse.json() as {is_synthetic:boolean;data_source_id:string;node_count:number;edge_count:number;version_label:string};
  expect(region.metadata.is_synthetic).toBe(false);
  expect(region.bounds).toEqual([55.258,25.18,55.288,25.208]);
  expect(region.area_km2).toBeGreaterThan(0);
  expect(network.is_synthetic).toBe(false);
  expect(network.node_count).toBeGreaterThan(0);
  expect(network.edge_count).toBeGreaterThan(0);
  const sourceResponse = await page.request.get(`/api/geospatial/data-sources/${network.data_source_id}`);
  expect(sourceResponse.status()).toBe(200);
  const source = await sourceResponse.json() as {provider_name:string;license_identifier:string;checksum_sha256:string};
  expect(source.provider_name).toContain("OpenStreetMap");
  expect(source.license_identifier).toBe("ODbL-1.0");
  expect(source.checksum_sha256).toMatch(/^[a-f0-9]{64}$/);
  const regionOptions = await page.getByLabel("3D study region", {exact:true}).locator("option").allTextContents();
  expect(regionOptions.every(label => !/synthetic/i.test(label))).toBe(true);
  await expect(page.locator(".city-synthetic-strip")).toHaveCount(0);
  await expect(page.getByText("LIVE TRAFFIC — Not connected", {exact:true})).toBeVisible();

  const contextResponse = await page.request.get("/geography/manifest.json");
  expect(contextResponse.status()).toBe(200);
  const context = await contextResponse.json() as {source:string;source_sha256:string;explicit_height_buildings:number};
  expect(context.source).toBe("OpenStreetMap");
  expect(context.source_sha256).toBe(source.checksum_sha256);
  expect(context.explicit_height_buildings).toBeGreaterThan(0);
  await expect.poll(async () => Number(await scene.getAttribute("data-local-building-count")), {timeout:45_000}).toBe(context.explicit_height_buildings);
  await expect(page.locator(".cesium-widget-credits")).toContainText("OpenStreetMap contributors");
  await expect(page.locator('.cesium-widget-credits a[href="https://www.openstreetmap.org/copyright"]').first()).toBeVisible();

  await page.getByRole("button", {name:"Top-down view",exact:true}).click();
  await expect(scene).toHaveAttribute("data-camera-moving", "true");
  await expect(scene).toHaveAttribute("data-camera-moving", "false");
  await expect(scene).toHaveAttribute("data-geometry-ready", "true");
  await expect.poll(async () => await scene.getAttribute("data-pick-id"), {timeout:30_000}).toMatch(/^[a-f0-9-]{36}$/);
  await expect.poll(() => observation.roads.size).toBeGreaterThan(0);
  const canvas = scene.locator("canvas");
  const rectangle = await canvas.boundingBox();
  if (!rectangle) throw new Error("Actual Cesium canvas has no layout");
  const x = Number(await scene.getAttribute("data-pick-x"));
  const y = Number(await scene.getAttribute("data-pick-y"));
  expect(x).toBeGreaterThan(0); expect(y).toBeGreaterThan(0);
  expect(x).toBeLessThan(rectangle.width); expect(y).toBeLessThan(rectangle.height);
  await page.mouse.click(rectangle.x+x,rectangle.y+y);
  await expect(page.getByTestId("selected-road-identifier")).toBeVisible();
  const selectedId = await page.getByTestId("selected-feature-id").innerText();
  await expect.poll(() => observation.roads.has(selectedId)).toBe(true);
  const selected = observation.roads.get(selectedId)!;
  expect(selected.properties.is_synthetic).toBe(false);
  expect(selected.properties.source_edge_id).toMatch(/^osm:way:/);
  await expect(page.getByTestId("selected-road-identifier")).toHaveText(selected.properties.sumo_edge_id);
  await expect(page.getByTestId("selected-road-length")).toHaveText(selected.properties.length_m.toLocaleString("en", {maximumFractionDigits:2}));
  await expect(page.getByTestId("selected-road-lanes")).toContainText(String(selected.properties.lane_count));
  await expect(page.getByTestId("feature-inspector")).toContainText(network.version_label);
  await expect(page.getByTestId("feature-inspector")).toContainText(source.provider_name);
  await expect(page.getByText("OSM way ID", {exact:true}).locator("..").locator("dd")).toHaveText(String(selected.properties.metadata?.osm_way_id));
  if (selected.properties.name) await expect(page.getByRole("heading", {name:selected.properties.name,exact:true})).toBeVisible();
  if (selected.properties.metadata?.lane_count_source === "inferred_by_netconvert") {
    await expect(page.getByTestId("selected-road-lanes")).toContainText("inferred by netconvert");
  }
  await mkdir("../../docs/evidence/recovery", {recursive:true});
  await page.screenshot({path:`../../docs/evidence/recovery/road-inspector-${info.project.name}.png`,fullPage:true});
  await page.getByRole("button", {name:"Zoom to feature",exact:true}).click();
  await expect(scene).toHaveAttribute("data-camera-moving", "true");
  await expect(scene).toHaveAttribute("data-camera-moving", "false");
  await page.getByRole("button", {name:"Close feature inspector",exact:true}).click();

  await page.getByRole("button", {name:"Layers",exact:true}).click();
  const roads = page.getByRole("checkbox", {name:"Road centerlines",exact:true});
  await roads.uncheck();
  await expect(scene).toHaveAttribute("data-road-count", "0");
  await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").roads as boolean).toBe(false);
  await roads.check();
  await expect.poll(async () => Number(await scene.getAttribute("data-road-count"))).toBeGreaterThan(0);
  const buildings = page.getByRole("checkbox", {name:"3D buildings",exact:true});
  await expect(buildings).toBeEnabled();
  await buildings.uncheck();
  await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").buildings as boolean).toBe(false);
  await buildings.check();
  await expect.poll(async () => Number(await scene.getAttribute("data-local-building-count")), {timeout:45_000}).toBe(context.explicit_height_buildings);
  await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").buildings as boolean).toBe(true);
  await page.getByRole("button", {name:"Close layers",exact:true}).click();
  for (const address of observation.edgeRequests) {
    const query = new URL(address).searchParams;
    expect(Number(query.get("limit"))).toBeLessThanOrEqual(100);
    const bbox = query.get("bbox")?.split(",").map(Number);
    expect(bbox).toHaveLength(4);
    expect(bbox![2]!-bbox![0]!).toBeLessThanOrEqual(1);
    expect(bbox![3]!-bbox![1]!).toBeLessThanOrEqual(1);
  }
  await assertNoFatalOrExternalRequests(observation);
  await writeFile(`../../docs/evidence/recovery/real-network-${info.project.name}.json`,JSON.stringify({navigationToRoadReadyMs:observation.navigationToRoadReadyMs,timingScope:"Fresh browser context navigation to nonempty native-ready PostGIS roads and settled camera; includes context-loading contention, not GPU frame latency",regionId,networkId,network,source,context,selectedRoad:selected,edgeRequests:observation.edgeRequests,errors:observation.errors,httpFailures:observation.httpFailures,externalRequests:observation.externalRequests},null,2)+"\n");
});

test("recovery map-first real view, native fullscreen resizing and Dubai camera presets", async ({page},info) => {
  test.setTimeout(90_000);
  const observation = observeActualServices(page);
  const scene = await openRealCity(page,observation);
  const canvas = scene.locator("canvas");
  const original = await canvas.boundingBox();
  if (!original) throw new Error("Actual Cesium canvas is missing");
  const viewport = page.viewportSize()!;
  expect(original.height / viewport.height).toBeGreaterThan(0.5);
  expect(original.width / viewport.width).toBeGreaterThan(0.75);
  expect(original.y).toBeLessThan(viewport.height*0.35);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", {name:"Enter fullscreen",exact:true}).click();
  await expect.poll(() => page.evaluate(() => document.fullscreenElement?.classList.contains("city-workspace") ?? false)).toBe(true);
  await expect(page.getByRole("button", {name:"Exit fullscreen",exact:true})).toBeVisible();
  await expect.poll(async () => {
    const box=await canvas.boundingBox();
    return box ? Math.abs(box.width-original.width)+Math.abs(box.height-original.height) : 0;
  }).toBeGreaterThan(10);
  const fullscreenBox = await canvas.boundingBox();
  if (!fullscreenBox) throw new Error("Canvas disappeared in fullscreen");
  expect(fullscreenBox.height).toBeGreaterThan(original.height);
  await page.getByRole("button", {name:"Exit fullscreen",exact:true}).click();
  await expect.poll(() => page.evaluate(() => document.fullscreenElement === null)).toBe(true);
  await expect.poll(async () => Math.abs(((await canvas.boundingBox())?.width ?? 0)-original.width)).toBeLessThan(2);

  const before = await page.getByTestId("camera-position").innerText();
  await page.getByRole("button", {name:"Business Bay",exact:true}).click();
  await expect.poll(() => page.getByTestId("camera-position").innerText()).not.toBe(before);
  await expect(scene).toHaveAttribute("data-camera-moving", "false");
  const businessBay = await page.getByTestId("camera-position").innerText();
  await page.getByRole("button", {name:"Downtown Dubai",exact:true}).click();
  await expect.poll(() => page.getByTestId("camera-position").innerText()).not.toBe(businessBay);
  await expect(scene).toHaveAttribute("data-camera-moving", "false");
  await expect(scene).toHaveAttribute("data-geometry-ready", "true");
  await expect.poll(async () => Number(await scene.getAttribute("data-local-building-count")),{timeout:45_000}).toBeGreaterThan(0);
  await mkdir("../../docs/evidence/recovery",{recursive:true});
  await page.screenshot({path:`../../docs/evidence/recovery/dubai-${info.project.name}.png`,fullPage:true});
  await assertNoFatalOrExternalRequests(observation);
  await writeFile(`../../docs/evidence/recovery/layout-${info.project.name}.json`,JSON.stringify({navigationToRoadReadyMs:observation.navigationToRoadReadyMs,timingScope:"Fresh browser context navigation to nonempty native-ready PostGIS roads and settled camera; includes context-loading contention, not GPU frame latency",viewport,canvasBeforeFullscreen:original,canvasDuringFullscreen:fullscreenBox,businessBayCamera:businessBay,downtownCamera:await page.getByTestId("camera-position").innerText(),errors:observation.errors,httpFailures:observation.httpFailures,externalRequests:observation.externalRequests},null,2)+"\n");
});
