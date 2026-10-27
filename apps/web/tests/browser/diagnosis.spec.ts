import { expect, test, type Locator, type Page } from "@playwright/test";
import { writeFile } from "node:fs/promises";
import { browserEvidencePath } from "./evidence";
import { CITY_LIMITS } from "../../lib/city/api";

test.skip(Boolean(process.env.CI) && process.env.EARTHMIND_REAL_GEO_TESTS !== "true", "Diagnosis checks require the retained real geography and deployed local services; offline CI does not fabricate coverage.");

type Camera = {
  longitude: number; latitude: number; height: number; heading: number; pitch: number;
  bounds: [number, number, number, number] | null;
  groundFocus: [number, number] | null;
};
type RenderDiagnostics = {
  globeVisible: boolean; globeTilesLoaded: boolean; imageryLayerCount: number;
  boundaryFillAlpha: number | null;
};
type Observation = {
  errors: string[]; httpFailures: string[];
  requestFailures: { path: string; error: string; expectedCancellation: boolean; cancellationScope: "network-catalog" | "scope" | "spatial" | null }[];
  externalRequests: string[]; workers: string[];
  textureRequests: string[]; successfulTextures: string[];
};

// Evidence never contains URL queries, fragments, configuration bodies or tokens.
function safeURL(value: string): string {
  try { const url = new URL(value); return `${url.origin}${url.pathname}`; }
  catch { return "[non-URL]"; }
}
function safeText(value: string): string {
  return value
    .replace(/https?:\/\/[^\s"'<>]+/g, safeURL)
    .replace(/((?:access_)?token|authorization)\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]")
    .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g, "[REDACTED]");
}
function cancellableRead(request: import("@playwright/test").Request, page: Page): "network-catalog" | "scope" | "spatial" | null {
  const url = new URL(request.url());
  if (request.method() !== "GET" || url.origin !== new URL(page.url()).origin) return null;
  const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
  const keys = [...url.searchParams.keys()].sort().join(",");
  const scoped = url.pathname.match(/^\/api\/geospatial\/(?:networks\/([^/]+)\/validation|data-sources\/([^/]+)|regions\/([^/]+)\/geojson)$/);
  if (keys === "" && scoped && uuid.test(scoped[1] ?? scoped[2] ?? scoped[3] ?? "")) return "scope";
  const offset = Number(url.searchParams.get("offset"));
  if (url.searchParams.get("limit") !== "100" || !Number.isInteger(offset) || offset < 0 || offset >= 500 || offset % 100 !== 0) return null;
  if (url.pathname === "/api/geospatial/networks" && keys === "limit,offset,region_id" && uuid.test(url.searchParams.get("region_id") ?? "")) return "network-catalog";
  const spatial = url.pathname.match(/^\/api\/geospatial\/networks\/([^/]+)\/(edges|intersections)$/);
  const bbox = url.searchParams.get("bbox")?.split(",").map(Number);
  if (!spatial?.[1] || !uuid.test(spatial[1]) || keys !== "bbox,limit,offset" || bbox?.length !== 4 || !bbox.every(Number.isFinite)) return null;
  const [west,south,east,north] = bbox as [number,number,number,number];
  if (west >= -180 && east <= 180 && south >= -90 && north <= 90 &&
    east > west && east - west <= 1 && north > south && north - south <= 1) return "spatial";
  return null;
}
function observe(page: Page): Observation {
  const result: Observation = { errors: [], httpFailures: [], requestFailures: [], externalRequests: [], workers: [], textureRequests: [], successfulTextures: [] };
  page.on("pageerror", error => result.errors.push(safeText(error.message)));
  page.on("console", message => { if (message.type() === "error") result.errors.push(safeText(message.text())); });
  page.on("worker", worker => result.workers.push(safeURL(worker.url())));
  page.on("request", request => {
    const url = new URL(request.url());
    if (/^https?:$/.test(url.protocol) && !["127.0.0.1", "localhost"].includes(url.hostname)) result.externalRequests.push(safeURL(request.url()));
    if (/\/cesium\/Assets\/Textures\/NaturalEarthII\/.*\.jpg$/.test(url.pathname)) result.textureRequests.push(safeURL(request.url()));
  });
  page.on("requestfailed", request => {
    const error = safeText(request.failure()?.errorText ?? "Unknown transport failure");
    const cancellationScope = cancellableRead(request, page);
    result.requestFailures.push({ path: safeURL(request.url()), error, expectedCancellation: error === "net::ERR_ABORTED" && cancellationScope !== null, cancellationScope });
  });
  page.on("response", response => {
    const path = new URL(response.url()).pathname;
    if (response.status() >= 400) result.httpFailures.push(`${response.status()} ${safeURL(response.url())}`);
    if (response.ok() && /\/cesium\/Assets\/Textures\/NaturalEarthII\/.*\.jpg$/.test(path)) result.successfulTextures.push(safeURL(response.url()));
  });
  return result;
}
async function deployedConfig(page: Page) {
  const response = await page.request.get("/api/city/config");
  expect(response.status()).toBe(200);
  const config = await response.json() as { imageryMode: string; diagnosticsEnabled: boolean; ionPublicToken: string | null };
  expect(config.imageryMode, "Actual deployed configuration must remain the self-hosted local mode for these checks").toBe("local-osm");
  expect(config.diagnosticsEnabled, "Native diagnostics require CITY_DIAGNOSTICS_ENABLED=true").toBe(true);
  return { imageryMode: config.imageryMode, diagnosticsEnabled: config.diagnosticsEnabled, publicTokenConfigured: Boolean(config.ionPublicToken) };
}
async function openCity(page: Page): Promise<Locator> {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dubai digital twin", exact: true })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Development datasets", exact: true })).not.toBeChecked();
  await expect(page.getByTestId("city-geographic-source")).toHaveText("REAL GEOGRAPHIC DATA — OpenStreetMap");
  const scene = page.getByTestId("cesium-viewer");
  await expect.poll(() => scene.evaluate(element => ({
    phase: element.getAttribute("data-phase"),
    roads: Number(element.getAttribute("data-road-count")) > 0,
    geometry: element.getAttribute("data-geometry-ready") === "true",
    settled: element.getAttribute("data-camera-moving") === "false",
    canvases: element.querySelectorAll("canvas").length,
  })), { timeout: 60_000 }).toEqual({ phase: "ready", roads: true, geometry: true, settled: true, canvases: 1 });
  return scene;
}
async function renderState(scene: Locator): Promise<RenderDiagnostics> {
  return JSON.parse(await scene.getAttribute("data-render-diagnostics") ?? "null") as RenderDiagnostics;
}
async function cameraState(page: Page): Promise<Camera> {
  return JSON.parse(await page.getByTestId("camera-position").getAttribute("data-camera") ?? "null") as Camera;
}
function targetFramePitchAllowance(camera: Camera): number {
  if (!camera.groundFocus) return 0;
  // Installed Cesium Camera.flyToBoundingSphere uses the target ENU frame;
  // Camera.pitch measures in the camera-position ENU frame. Their pitch difference
  // is bounded by the angle between those up normals, plus 0.001° numeric slack.
  // FixedFrameTransforms computes its up axis from the WGS84 Cartesian gradient.
  const up = (longitude: number, latitude: number, height: number): [number,number,number] => {
    const lon = longitude * Math.PI / 180, lat = latitude * Math.PI / 180;
    const e2 = 6.6943799901413165e-3;
    const radius = 6378137 / Math.sqrt(1 - e2 * Math.sin(lat) ** 2);
    const [x,y,z] = [(radius + height) * Math.cos(lat) * Math.cos(lon), (radius + height) * Math.cos(lat) * Math.sin(lon), (radius * (1 - e2) + height) * Math.sin(lat) / (1 - e2)] as const;
    const length = Math.hypot(x,y,z);
    return [x/length,y/length,z/length];
  };
  const cameraUp = up(camera.longitude, camera.latitude, camera.height);
  const targetUp = up(camera.groundFocus[0], camera.groundFocus[1], 0);
  const dot = cameraUp[0]*targetUp[0]+cameraUp[1]*targetUp[1]+cameraUp[2]*targetUp[2];
  return Math.acos(Math.max(-1, Math.min(1, dot))) * 180 / Math.PI + 0.001;
}
async function assertFocus(page: Page, scene: Locator, target: [number, number]): Promise<Camera> {
  await expect.poll(async () => {
    const camera = await cameraState(page);
    return Boolean(camera?.groundFocus && await scene.getAttribute("data-camera-moving") === "false" &&
      Math.abs(camera.groundFocus[0] - target[0]) < 0.0005 && Math.abs(camera.groundFocus[1] - target[1]) < 0.0005);
  }, { timeout: 25_000, message: "Settled camera must retain the requested actual ground focus" }).toBe(true);
  const camera = await cameraState(page);
  for (const value of [camera.longitude, camera.latitude, camera.height, camera.heading, camera.pitch]) expect(Number.isFinite(value)).toBe(true);
  expect(camera.height).toBeGreaterThan(0);
  expect(camera.pitch).toBeLessThan(0);
  expect(camera.pitch).toBeGreaterThanOrEqual(-90.00001);
  expect(camera.bounds).not.toBeNull();
  return camera;
}
function unexpectedTransportFailures(observation: Observation) {
  // useCityData consumes TanStack's signal for network catalogs and viewport
  // reads. Only exact same-origin bounded GET shapes may be aborted; every
  // failure and its classification remain in the evidence above.
  return observation.requestFailures.filter(failure => !failure.expectedCancellation);
}
async function saveEvidence(page: Page, name: string, project: string, data: unknown) {
  await writeFile(browserEvidencePath(`${name}-${project}.json`), `${JSON.stringify(data, null, 2)}\n`);
  await page.screenshot({ path: browserEvidencePath(`${name}-${project}.png`), fullPage: true });
}

test("diagnosis reselecting the active fixture preserves in-flight stored roads",async({page},info)=>{
  test.setTimeout(90_000);
  const observation=observe(page);
  const config=await deployedConfig(page);
  let release=()=>{};
  const gate=new Promise<void>(resolve=>{release=resolve;});
  let held=0;
  let heldAt=0;
  await page.route("**/api/geospatial/networks/22f68ce8-9247-5425-8342-827d86517ead/edges?**",async route=>{
    held++;
    if (!heldAt) heldAt=performance.now();
    await gate;
    await route.continue();
  });
  try {
    await page.goto("/");
    await page.getByRole("checkbox",{name:"Development datasets",exact:true}).check();
    const region=page.getByLabel("3D study region",{exact:true});
    const network=page.getByLabel("3D network version",{exact:true});
    await expect.poll(()=>held).toBeGreaterThan(0);
    const scene=page.getByTestId("cesium-viewer");
    await expect(network).toHaveValue("22f68ce8-9247-5425-8342-827d86517ead");
    // Exercise cancellation immediately, within the actual request deadline.
    // Waiting for imagery here would turn this into an unrelated timeout test.
    expect(performance.now()-heldAt).toBeLessThan(CITY_LIMITS.timeoutMs/2);
    // Both existing fixture selections are already in effect. Re-emitting change
    // must not cancel an unchanged query key and leave it idle without data.
    await region.selectOption(await region.inputValue());
    await network.selectOption(await network.inputValue());
    release();
    await expect(scene).toHaveAttribute("data-road-count","8",{timeout:30_000});
    await expect(scene).toHaveAttribute("data-intersection-count","6");
    await expect(scene).toHaveAttribute("data-phase","ready");
    expect(observation.errors).toEqual([]);
    expect(observation.httpFailures).toEqual([]);
    expect(unexpectedTransportFailures(observation)).toEqual([]);
    expect(observation.externalRequests).toEqual([]);
  } finally {
    release();
    await saveEvidence(page,"diagnosis-controlled-same-selection",info.project.name,{scope:"Existing explicitly selected synthetic-v1 fixture from actual PostGIS/API; its real spatial responses held/released while unchanged selections are re-emitted; no fabricated or newly imported data",actualDeployedConfig:config,held,observation});
  }
});

test("diagnosis controlled worker delay keeps source geometry loading until native preparation finishes", async ({page},info) => {
  test.setTimeout(90_000);
  const observation = observe(page);
  const config = await deployedConfig(page);
  let release = () => {};
  const gate = new Promise<void>(resolve => {release=resolve;});
  let heldWorkers = 0;
  await page.route("**/cesium/Workers/createGeometry.js",async route => {
    heldWorkers++;
    await gate;
    await route.continue();
  });
  try {
    await page.goto("/");
    const scene = page.getByTestId("cesium-viewer");
    // Actual GeoJSON has been adopted, but its real geometry worker cannot yet
    // prepare any mesh. A latched DataSourceDisplay.ready must not win this race.
    await expect(scene).toHaveAttribute("data-local-building-count","402",{timeout:30_000});
    await expect.poll(()=>heldWorkers).toBeGreaterThan(0);
    await expect(scene).toHaveAttribute("data-buildings-status","loading");
    await expect(scene).toHaveAttribute("data-imagery-status","loading");
    release();
    await expect(scene).toHaveAttribute("data-buildings-status","ready",{timeout:60_000});
    await expect(scene).toHaveAttribute("data-imagery-status","ready",{timeout:60_000});
    await expect.poll(async()=>Number(await scene.getAttribute("data-road-count"))).toBeGreaterThan(0);
    expect(observation.errors).toEqual([]);
    expect(observation.httpFailures).toEqual([]);
    expect(unexpectedTransportFailures(observation)).toEqual([]);
    expect(observation.externalRequests).toEqual([]);
  } finally {
    release();
    await saveEvidence(page,"diagnosis-controlled-worker-delay",info.project.name,{scope:"Controlled transport hold/release of the actual same-origin geometry worker script; no replacement geographic data or worker code",actualDeployedConfig:config,heldWorkers,observation});
  }
});

test("diagnosis actual local services show source-backed buildings, loaded globe, transparent boundary and stable Dubai camera focus", async ({ page }, info) => {
  test.setTimeout(120_000);
  const observation = observe(page);
  const config = await deployedConfig(page);
  const cameras: Record<string, Camera> = {};
  let network: unknown = null;
  try {
    const scene = await openCity(page);
    await expect(scene).toHaveAttribute("data-imagery-status", "ready");
    await expect(scene).toHaveAttribute("data-buildings-status", "ready");
    const manifestResponse = await page.request.get("/geography/manifest.json");
    expect(manifestResponse.status()).toBe(200);
    const manifest = await manifestResponse.json() as { source: string; source_sha256: string; explicit_height_buildings: number };
    expect(manifest.source).toBe("OpenStreetMap");
    expect(manifest.explicit_height_buildings).toBe(402);
    await expect(scene).toHaveAttribute("data-local-building-count", "402");
    const networkId = await page.getByLabel("3D network version", { exact: true }).inputValue();
    const networkResponse = await page.request.get(`/api/geospatial/networks/${networkId}`);
    expect(networkResponse.status()).toBe(200);
    const currentNetwork = await networkResponse.json() as { is_synthetic: boolean; version_label: string; data_source_id: string; node_count: number; edge_count: number };
    expect(currentNetwork.is_synthetic).toBe(false);
    expect(currentNetwork.version_label).toMatch(/^osm-/);
    expect(currentNetwork.node_count).toBeGreaterThan(6);
    expect(currentNetwork.edge_count).toBeGreaterThan(8);
    const sourceResponse = await page.request.get(`/api/geospatial/data-sources/${currentNetwork.data_source_id}`);
    expect(sourceResponse.status()).toBe(200);
    const source = await sourceResponse.json() as { provider_name: string; license_identifier: string; checksum_sha256: string };
    expect(source.provider_name).toContain("OpenStreetMap");
    expect(source.license_identifier).toBe("ODbL-1.0");
    expect(source.checksum_sha256).toBe(manifest.source_sha256);
    network = { id: networkId, ...currentNetwork, source };
    await expect.poll(async () => (await renderState(scene))?.globeTilesLoaded, { timeout: 30_000 }).toBe(true);
    expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1, boundaryFillAlpha: 0.13 });
    await expect.poll(() => observation.successfulTextures.length).toBeGreaterThan(0);
    await expect.poll(() => observation.workers.length).toBeGreaterThan(0);
    cameras.initial = await assertFocus(page, scene, [55.2744, 25.1972]);
    await page.getByRole("button", { name: "Layers", exact: true }).click();
    const boundary = page.getByRole("checkbox", { name: "Study region", exact: true });
    await expect(boundary).not.toBeChecked();
    await boundary.check();
    await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").boundary as boolean).toBe(true);
    expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1, boundaryFillAlpha: 0.13 });
    await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").imagery as boolean).toBe(true);
    await page.screenshot({ path: browserEvidencePath(`diagnosis-boundary-visible-${info.project.name}.png`), fullPage: true });
    await boundary.uncheck();
    await page.getByRole("button", { name: "Close layers", exact: true }).click();
    await page.getByRole("button", { name: "Business Bay", exact: true }).click();
    cameras.businessBay = await assertFocus(page, scene, [55.261, 25.182]);
    await page.getByRole("button", { name: "Downtown Dubai", exact: true }).click();
    cameras.downtown = await assertFocus(page, scene, [55.2744, 25.1972]);
    await page.getByRole("button", { name: "Top-down view", exact: true }).click();
    await expect.poll(async () => { const camera = await cameraState(page); return Math.abs(camera.pitch + 90) <= targetFramePitchAllowance(camera); }).toBe(true);
    cameras.topDown = await assertFocus(page, scene, cameras.downtown.groundFocus!);
    await page.getByRole("button", { name: "Perspective view", exact: true }).click();
    await expect.poll(async () => { const camera = await cameraState(page); return Math.abs(camera.pitch + 55) <= targetFramePitchAllowance(camera); }).toBe(true);
    cameras.perspective = await assertFocus(page, scene, cameras.topDown.groundFocus!);
    expect(observation.errors).toEqual([]);
    expect(observation.httpFailures).toEqual([]);
    expect(unexpectedTransportFailures(observation)).toEqual([]);
    expect(observation.externalRequests).toEqual([]);
  } finally {
    await saveEvidence(page, "diagnosis-actual-local", info.project.name, { scope: "Actual deployed local services and retained source data; no geographic response substitutions; does not verify satellite or ion buildings", config, network, cameras, observation });
  }
});

test("diagnosis controlled configuration: missing ion token remains blocked with honest usable Natural Earth fallback", async ({ page }, info) => {
  test.setTimeout(90_000);
  const observation = observe(page);
  const config = await deployedConfig(page);
  await page.route("**/api/city/config", async route => {
    const response = await route.fetch();
    const actual = await response.json() as Record<string, unknown>;
    await route.fulfill({ response, json: { ...actual, imageryMode: "ion", ionPublicToken: null } });
  });
  try {
    const scene = await openCity(page);
    await expect(scene).toHaveAttribute("data-imagery-status", "blocked");
    await expect(scene).toHaveAttribute("data-buildings-status", "blocked");
    await expect.poll(async () => (await renderState(scene))?.globeTilesLoaded).toBe(true);
    expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1 });
    await expect(page.locator(".cesium-widget-credits")).toContainText("Natural Earth");
    await page.getByRole("button", { name: "Layers", exact: true }).click();
    await expect(page.locator(".city-layer-detail").filter({ hasText: /Natural Earth/i })).toContainText(/token|unavailable|blocked/i);
    const imagery = page.getByRole("checkbox", { name: "Geographic basemap", exact: true });
    await imagery.uncheck();
    await expect(scene).toHaveAttribute("data-imagery-status", "off");
    await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").imagery as boolean).toBe(false);
    await imagery.check();
    await expect(scene).toHaveAttribute("data-imagery-status", "blocked");
    await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").imagery as boolean).toBe(true);
    await expect.poll(() => observation.successfulTextures.length).toBeGreaterThan(0);
    expect(observation.errors).toEqual([]);
    expect(observation.httpFailures).toEqual([]);
    expect(unexpectedTransportFailures(observation)).toEqual([]);
    expect(observation.externalRequests).toEqual([]);
  } finally {
    await saveEvidence(page, "diagnosis-controlled-missing-token", info.project.name, { scope: "Controlled substitution of configuration only: imageryMode=ion and ionPublicToken=null; geography and assets remain actual local services; no working-ion claim", actualDeployedConfig: config, observation });
  }
});

test("diagnosis controlled context failure remains an error while stored geography and the globe stay usable", async ({ page }, info) => {
  test.setTimeout(90_000);
  const observation = observe(page);
  const config = await deployedConfig(page);
  let injectedFailures = 0;
  await page.route("**/geography/context.geojson", async route => { injectedFailures++; await route.abort("failed"); });
  try {
    const scene = await openCity(page);
    await expect(scene).toHaveAttribute("data-imagery-status", "error");
    await expect(page.locator('.city-provider-notice [role="alert"]')).toContainText("Imagery provider unavailable");
    await expect(scene).toHaveAttribute("data-buildings-status", "ready");
    await expect(scene).toHaveAttribute("data-local-building-count", "402");
    await expect.poll(async () => (await renderState(scene))?.globeTilesLoaded).toBe(true);
    await page.getByRole("button", { name: "Business Bay", exact: true }).click();
    await assertFocus(page, scene, [55.261, 25.182]);
    // Camera movement and later tile completion must not overwrite the error.
    await expect(scene).toHaveAttribute("data-imagery-status", "error");
    expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1 });
    expect(injectedFailures).toBeGreaterThan(0);
    expect(observation.requestFailures.some(failure => new URL(failure.path).pathname === "/geography/context.geojson")).toBe(true);
    expect(observation.httpFailures).toEqual([]);
    expect(unexpectedTransportFailures(observation).filter(failure => new URL(failure.path).pathname !== "/geography/context.geojson")).toEqual([]);
    expect(observation.errors.filter(error => !/net::ERR_FAILED/.test(error))).toEqual([]);
    expect(observation.externalRequests).toEqual([]);
  } finally {
    await saveEvidence(page, "diagnosis-controlled-context-failure", info.project.name, { scope: "Controlled transport abort of only the same-origin context GeoJSON; no substitute geographic response; expected browser network error retained", actualDeployedConfig: config, injectedFailures, observation });
  }
});
