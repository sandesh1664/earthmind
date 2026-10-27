# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: diagnosis.spec.ts >> diagnosis actual local services show source-backed buildings, loaded globe, transparent boundary and stable Dubai camera focus
- Location: tests/browser/diagnosis.spec.ts:104:1

# Error details

```
Error: Settled camera must retain the requested actual ground focus

Settled camera must retain the requested actual ground focus

expect(received).toBe(expected) // Object.is equality

Expected: true
Received: false

Call Log:
- Timeout 25000ms exceeded while waiting on the predicate
```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e2]:
    - complementary "Workspace navigation" [ref=e3]:
      - link "EARTHMIND URBAN INTELLIGENCE" [ref=e4] [cursor=pointer]:
        - /url: "#overview"
        - generic [ref=e12]:
          - text: EARTHMIND
          - generic [ref=e13]: URBAN INTELLIGENCE
      - paragraph [ref=e14]: WORKSPACE M03
      - navigation "Main navigation" [ref=e15]:
        - button "Overview" [ref=e16] [cursor=pointer]
        - button "Geospatial Data" [ref=e23] [cursor=pointer]:
          - generic [ref=e27]: M02
        - button "City Explorer" [ref=e28] [cursor=pointer]
        - button "Scenario Studio" [ref=e33] [cursor=pointer]:
          - generic [ref=e39]: LATER
        - button "Simulation Laboratory" [ref=e40] [cursor=pointer]:
          - generic [ref=e44]: LATER
        - button "Traffic Intelligence" [ref=e45] [cursor=pointer]:
          - generic [ref=e51]: LATER
        - button "AI Command Center" [ref=e52] [cursor=pointer]:
          - generic [ref=e65]: LATER
        - button "Analytics" [ref=e66] [cursor=pointer]:
          - generic [ref=e70]: LATER
        - button "System Status" [ref=e71] [cursor=pointer]
        - button "Settings" [ref=e75] [cursor=pointer]:
          - generic [ref=e80]: LATER
      - generic [ref=e88]:
        - strong [ref=e89]: Local workspace
        - generic [ref=e90]: Foundation environment
    - main [ref=e91]:
      - generic [ref=e92]:
        - generic [ref=e93]:
          - button "Open navigation" [ref=e94] [cursor=pointer]
          - generic [ref=e96]: Workspace
          - strong [ref=e99]: City Explorer
        - generic [ref=e100]: LOCAL DEVELOPMENT
      - region "Dubai 3D digital twin" [ref=e104]:
        - generic [ref=e105]:
          - generic [ref=e106]:
            - paragraph [ref=e107]: DOWNTOWN DUBAI / BUSINESS BAY
            - heading "Dubai digital twin" [level=2] [ref=e108]
          - generic [ref=e109]: OPENSTREETMAP
        - generic [ref=e115]:
          - generic [ref=e116]:
            - text: Study region
            - combobox "3D study region" [ref=e117]:
              - option "Downtown Dubai / Business Bay — OpenStreetMap Study Area" [selected]
          - generic [ref=e118]:
            - text: Network version
            - combobox "3D network version" [ref=e119]:
              - option "osm-20261026-0b027352ec38 · published" [selected]
          - generic [ref=e120]:
            - generic "Show synthetic fixtures instead of imported geographic datasets" [ref=e121]:
              - checkbox "Development datasets" [ref=e122]
            - button "Enter fullscreen" [ref=e125] [cursor=pointer]
            - button "Layers" [ref=e131] [cursor=pointer]
            - button "Show feature inspector" [ref=e138] [cursor=pointer]
        - generic "Geographic data provenance" [ref=e142]:
          - generic [ref=e143]: REAL GEOGRAPHIC DATA — OpenStreetMap
          - generic [ref=e144]: 3D BUILDINGS — OSM source-height context · partial coverage
          - generic [ref=e145]: SYNTHETIC TRAFFIC — CLI smoke only; no viewer playback
          - generic [ref=e146]: LIVE TRAFFIC — Not connected
          - generic [ref=e147]: INFERRED SIGNALS — Not field verified
        - generic [ref=e149]:
          - generic [ref=e150]:
            - generic:
              - generic: CESIUM · WGS84
              - generic: OSM ROAD NETWORK
            - generic "Interactive 3D geographic globe" [ref=e152]:
              - generic [ref=e158]:
                - link [ref=e161] [cursor=pointer]:
                  - /url: https://cesium.com/
                  - img "Cesium ion" [ref=e162]
                - generic [ref=e163]:
                  - generic [ref=e164]:
                    - text: ©
                    - link "OpenStreetMap contributors" [ref=e165] [cursor=pointer]:
                      - /url: https://www.openstreetmap.org/copyright
                    - text: · ODbL
                  - text: •Made with Natural Earth · public domain
            - status:
              - generic: "500"
              - text: roads ·
              - generic: "0"
              - text: intersections rendered
            - generic "Map legend":
              - generic: primary link · tertiary · motorway link · unclassified
              - generic: Intersection
              - generic: OSM signal tag · unverified
              - generic: Selected feature
          - generic "Camera controls" [ref=e166]:
            - generic [ref=e167]:
              - button "Dubai overview" [ref=e168] [cursor=pointer]
              - button "Downtown Dubai" [ref=e169] [cursor=pointer]
              - button "Business Bay" [ref=e170] [cursor=pointer]
            - generic [ref=e171]:
              - button "Zoom to study region" [ref=e172] [cursor=pointer]
              - button "Zoom to selected feature" [disabled] [ref=e179]
              - button "Top-down view" [ref=e185] [cursor=pointer]
              - button "Perspective view" [ref=e188] [cursor=pointer]
              - button "Zoom in" [ref=e192] [cursor=pointer]
              - button "Zoom out" [ref=e196] [cursor=pointer]
              - button "Reset camera" [ref=e200] [cursor=pointer]
          - generic "Camera position indicator" [ref=e204]: 55.27440° E · 25.18167° N · 2,458 m altitude
        - group [ref=e209]:
          - generic "Network & source details 2,364 roads · 1,560 nodes" [ref=e210] [cursor=pointer]:
            - text: Network & source details
            - generic [ref=e215]: 2,364 roads · 1,560 nodes
        - status:
          - paragraph: "Display budget reached: at most 500 features and 25,000 coordinate positions per layer. Zoom closer to inspect remaining features."
        - paragraph [ref=e218]:
          - generic [ref=e224]:
            - text: Local OpenStreetMap cartography over Natural Earth reference; no satellite imagery.
            - strong [ref=e225]: "Cesium ion building tiles unavailable:"
            - text: set CESIUM_ION_PUBLIC_TOKEN. Ellipsoid terrain; OSM tagged-height buildings cover only part of the source area.
        - button "Local rendering diagnostics" [ref=e227] [cursor=pointer]
  - alert [ref=e232]
```

# Test source

```ts
  1   | import { expect, test, type Locator, type Page } from "@playwright/test";
  2   | import { writeFile } from "node:fs/promises";
  3   | import { browserEvidencePath } from "./evidence";
  4   | 
  5   | test.skip(Boolean(process.env.CI) && process.env.EARTHMIND_REAL_GEO_TESTS !== "true", "Diagnosis checks require the retained real geography and deployed local services; offline CI does not fabricate coverage.");
  6   | 
  7   | type Camera = {
  8   |   longitude: number; latitude: number; height: number; heading: number; pitch: number;
  9   |   bounds: [number, number, number, number] | null;
  10  |   groundFocus: [number, number] | null;
  11  | };
  12  | type RenderDiagnostics = {
  13  |   globeVisible: boolean; globeTilesLoaded: boolean; imageryLayerCount: number;
  14  |   boundaryFillAlpha: number | null;
  15  | };
  16  | type Observation = {
  17  |   errors: string[]; httpFailures: string[];
  18  |   requestFailures: { path: string; error: string }[];
  19  |   externalRequests: string[]; workers: string[];
  20  |   textureRequests: string[]; successfulTextures: string[];
  21  | };
  22  | 
  23  | // Evidence never contains URL queries, fragments, configuration bodies or tokens.
  24  | function safeURL(value: string): string {
  25  |   try { const url = new URL(value); return `${url.origin}${url.pathname}`; }
  26  |   catch { return "[non-URL]"; }
  27  | }
  28  | function safeText(value: string): string {
  29  |   return value
  30  |     .replace(/https?:\/\/[^\s"'<>]+/g, safeURL)
  31  |     .replace(/((?:access_)?token|authorization)\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]")
  32  |     .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g, "[REDACTED]");
  33  | }
  34  | function observe(page: Page): Observation {
  35  |   const result: Observation = { errors: [], httpFailures: [], requestFailures: [], externalRequests: [], workers: [], textureRequests: [], successfulTextures: [] };
  36  |   page.on("pageerror", error => result.errors.push(safeText(error.message)));
  37  |   page.on("console", message => { if (message.type() === "error") result.errors.push(safeText(message.text())); });
  38  |   page.on("worker", worker => result.workers.push(safeURL(worker.url())));
  39  |   page.on("request", request => {
  40  |     const url = new URL(request.url());
  41  |     if (/^https?:$/.test(url.protocol) && !["127.0.0.1", "localhost"].includes(url.hostname)) result.externalRequests.push(safeURL(request.url()));
  42  |     if (/\/cesium\/Assets\/Textures\/NaturalEarthII\/.*\.jpg$/.test(url.pathname)) result.textureRequests.push(safeURL(request.url()));
  43  |   });
  44  |   page.on("requestfailed", request => result.requestFailures.push({ path: safeURL(request.url()), error: safeText(request.failure()?.errorText ?? "Unknown transport failure") }));
  45  |   page.on("response", response => {
  46  |     const path = new URL(response.url()).pathname;
  47  |     if (response.status() >= 400) result.httpFailures.push(`${response.status()} ${safeURL(response.url())}`);
  48  |     if (response.ok() && /\/cesium\/Assets\/Textures\/NaturalEarthII\/.*\.jpg$/.test(path)) result.successfulTextures.push(safeURL(response.url()));
  49  |   });
  50  |   return result;
  51  | }
  52  | async function deployedConfig(page: Page) {
  53  |   const response = await page.request.get("/api/city/config");
  54  |   expect(response.status()).toBe(200);
  55  |   const config = await response.json() as { imageryMode: string; diagnosticsEnabled: boolean; ionPublicToken: string | null };
  56  |   expect(config.imageryMode, "Actual deployed configuration must remain the self-hosted local mode for these checks").toBe("local-osm");
  57  |   expect(config.diagnosticsEnabled, "Native diagnostics require CITY_DIAGNOSTICS_ENABLED=true").toBe(true);
  58  |   return { imageryMode: config.imageryMode, diagnosticsEnabled: config.diagnosticsEnabled, publicTokenConfigured: Boolean(config.ionPublicToken) };
  59  | }
  60  | async function openCity(page: Page): Promise<Locator> {
  61  |   await page.goto("/");
  62  |   await expect(page.getByRole("heading", { name: "Dubai digital twin", exact: true })).toBeVisible();
  63  |   await expect(page.getByRole("checkbox", { name: "Development datasets", exact: true })).not.toBeChecked();
  64  |   await expect(page.getByTestId("city-geographic-source")).toHaveText("REAL GEOGRAPHIC DATA — OpenStreetMap");
  65  |   const scene = page.getByTestId("cesium-viewer");
  66  |   await expect.poll(() => scene.evaluate(element => ({
  67  |     phase: element.getAttribute("data-phase"),
  68  |     roads: Number(element.getAttribute("data-road-count")) > 0,
  69  |     geometry: element.getAttribute("data-geometry-ready") === "true",
  70  |     settled: element.getAttribute("data-camera-moving") === "false",
  71  |     canvases: element.querySelectorAll("canvas").length,
  72  |   })), { timeout: 60_000 }).toEqual({ phase: "ready", roads: true, geometry: true, settled: true, canvases: 1 });
  73  |   return scene;
  74  | }
  75  | async function renderState(scene: Locator): Promise<RenderDiagnostics> {
  76  |   return JSON.parse(await scene.getAttribute("data-render-diagnostics") ?? "null") as RenderDiagnostics;
  77  | }
  78  | async function cameraState(page: Page): Promise<Camera> {
  79  |   return JSON.parse(await page.getByTestId("camera-position").getAttribute("data-camera") ?? "null") as Camera;
  80  | }
  81  | async function assertFocus(page: Page, scene: Locator, target: [number, number]): Promise<Camera> {
  82  |   await expect.poll(async () => {
  83  |     const camera = await cameraState(page);
  84  |     return Boolean(camera?.groundFocus && await scene.getAttribute("data-camera-moving") === "false" &&
  85  |       Math.abs(camera.groundFocus[0] - target[0]) < 0.0005 && Math.abs(camera.groundFocus[1] - target[1]) < 0.0005);
> 86  |   }, { timeout: 25_000, message: "Settled camera must retain the requested actual ground focus" }).toBe(true);
      |                                                                                                    ^ Error: Settled camera must retain the requested actual ground focus
  87  |   const camera = await cameraState(page);
  88  |   for (const value of [camera.longitude, camera.latitude, camera.height, camera.heading, camera.pitch]) expect(Number.isFinite(value)).toBe(true);
  89  |   expect(camera.height).toBeGreaterThan(0);
  90  |   expect(camera.pitch).toBeLessThan(0);
  91  |   expect(camera.pitch).toBeGreaterThanOrEqual(-90.00001);
  92  |   expect(camera.bounds).not.toBeNull();
  93  |   return camera;
  94  | }
  95  | function unexpectedTransportFailures(observation: Observation) {
  96  |   // Viewport changes intentionally cancel only superseded bounded spatial reads.
  97  |   return observation.requestFailures.filter(failure => !(failure.error === "net::ERR_ABORTED" && /\/api\/geospatial\/networks\/[^/]+\/(edges|intersections)$/.test(new URL(failure.path).pathname)));
  98  | }
  99  | async function saveEvidence(page: Page, name: string, project: string, data: unknown) {
  100 |   await writeFile(browserEvidencePath(`${name}-${project}.json`), `${JSON.stringify(data, null, 2)}\n`);
  101 |   await page.screenshot({ path: browserEvidencePath(`${name}-${project}.png`), fullPage: true });
  102 | }
  103 | 
  104 | test("diagnosis actual local services show source-backed buildings, loaded globe, transparent boundary and stable Dubai camera focus", async ({ page }, info) => {
  105 |   test.setTimeout(120_000);
  106 |   const observation = observe(page);
  107 |   const config = await deployedConfig(page);
  108 |   const cameras: Record<string, Camera> = {};
  109 |   let network: unknown = null;
  110 |   try {
  111 |     const scene = await openCity(page);
  112 |     await expect(scene).toHaveAttribute("data-imagery-status", "ready");
  113 |     await expect(scene).toHaveAttribute("data-buildings-status", "ready");
  114 |     const manifestResponse = await page.request.get("/geography/manifest.json");
  115 |     expect(manifestResponse.status()).toBe(200);
  116 |     const manifest = await manifestResponse.json() as { source: string; source_sha256: string; explicit_height_buildings: number };
  117 |     expect(manifest.source).toBe("OpenStreetMap");
  118 |     expect(manifest.explicit_height_buildings).toBe(402);
  119 |     await expect(scene).toHaveAttribute("data-local-building-count", "402");
  120 |     const networkId = await page.getByLabel("3D network version", { exact: true }).inputValue();
  121 |     const networkResponse = await page.request.get(`/api/geospatial/networks/${networkId}`);
  122 |     expect(networkResponse.status()).toBe(200);
  123 |     const currentNetwork = await networkResponse.json() as { is_synthetic: boolean; version_label: string; data_source_id: string; node_count: number; edge_count: number };
  124 |     expect(currentNetwork.is_synthetic).toBe(false);
  125 |     expect(currentNetwork.version_label).toMatch(/^osm-/);
  126 |     expect(currentNetwork.node_count).toBeGreaterThan(6);
  127 |     expect(currentNetwork.edge_count).toBeGreaterThan(8);
  128 |     const sourceResponse = await page.request.get(`/api/geospatial/data-sources/${currentNetwork.data_source_id}`);
  129 |     expect(sourceResponse.status()).toBe(200);
  130 |     const source = await sourceResponse.json() as { provider_name: string; license_identifier: string; checksum_sha256: string };
  131 |     expect(source.provider_name).toContain("OpenStreetMap");
  132 |     expect(source.license_identifier).toBe("ODbL-1.0");
  133 |     expect(source.checksum_sha256).toBe(manifest.source_sha256);
  134 |     network = { id: networkId, ...currentNetwork, source };
  135 |     await expect.poll(async () => (await renderState(scene))?.globeTilesLoaded, { timeout: 30_000 }).toBe(true);
  136 |     expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1, boundaryFillAlpha: 0.13 });
  137 |     await expect.poll(() => observation.successfulTextures.length).toBeGreaterThan(0);
  138 |     await expect.poll(() => observation.workers.length).toBeGreaterThan(0);
  139 |     cameras.initial = await assertFocus(page, scene, [55.2744, 25.1972]);
  140 |     await page.getByRole("button", { name: "Layers", exact: true }).click();
  141 |     const boundary = page.getByRole("checkbox", { name: "Study region", exact: true });
  142 |     await expect(boundary).not.toBeChecked();
  143 |     await boundary.check();
  144 |     await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").boundary as boolean).toBe(true);
  145 |     expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1, boundaryFillAlpha: 0.13 });
  146 |     await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").imagery as boolean).toBe(true);
  147 |     await page.screenshot({ path: browserEvidencePath(`diagnosis-boundary-visible-${info.project.name}.png`), fullPage: true });
  148 |     await boundary.uncheck();
  149 |     await page.getByRole("button", { name: "Close layers", exact: true }).click();
  150 |     await page.getByRole("button", { name: "Business Bay", exact: true }).click();
  151 |     cameras.businessBay = await assertFocus(page, scene, [55.261, 25.182]);
  152 |     await page.getByRole("button", { name: "Downtown Dubai", exact: true }).click();
  153 |     cameras.downtown = await assertFocus(page, scene, [55.2744, 25.1972]);
  154 |     await page.getByRole("button", { name: "Top-down view", exact: true }).click();
  155 |     await expect.poll(async () => Math.abs((await cameraState(page)).pitch + 90)).toBeLessThan(0.01);
  156 |     cameras.topDown = await assertFocus(page, scene, cameras.downtown.groundFocus!);
  157 |     await page.getByRole("button", { name: "Perspective view", exact: true }).click();
  158 |     await expect.poll(async () => Math.abs((await cameraState(page)).pitch + 55)).toBeLessThan(0.01);
  159 |     cameras.perspective = await assertFocus(page, scene, cameras.topDown.groundFocus!);
  160 |     expect(observation.errors).toEqual([]);
  161 |     expect(observation.httpFailures).toEqual([]);
  162 |     expect(unexpectedTransportFailures(observation)).toEqual([]);
  163 |     expect(observation.externalRequests).toEqual([]);
  164 |   } finally {
  165 |     await saveEvidence(page, "diagnosis-actual-local", info.project.name, { scope: "Actual deployed local services and retained source data; no geographic response substitutions; does not verify satellite or ion buildings", config, network, cameras, observation });
  166 |   }
  167 | });
  168 | 
  169 | test("diagnosis controlled configuration: missing ion token remains blocked with honest usable Natural Earth fallback", async ({ page }, info) => {
  170 |   test.setTimeout(90_000);
  171 |   const observation = observe(page);
  172 |   const config = await deployedConfig(page);
  173 |   await page.route("**/api/city/config", async route => {
  174 |     const response = await route.fetch();
  175 |     const actual = await response.json() as Record<string, unknown>;
  176 |     await route.fulfill({ response, json: { ...actual, imageryMode: "ion", ionPublicToken: null } });
  177 |   });
  178 |   try {
  179 |     const scene = await openCity(page);
  180 |     await expect(scene).toHaveAttribute("data-imagery-status", "blocked");
  181 |     await expect(scene).toHaveAttribute("data-buildings-status", "blocked");
  182 |     await expect.poll(async () => (await renderState(scene))?.globeTilesLoaded).toBe(true);
  183 |     expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1 });
  184 |     await expect(page.locator(".cesium-widget-credits")).toContainText("Natural Earth");
  185 |     await page.getByRole("button", { name: "Layers", exact: true }).click();
  186 |     await expect(page.locator(".city-layer-detail").filter({ hasText: /Natural Earth/i })).toContainText(/token|unavailable|blocked/i);
```