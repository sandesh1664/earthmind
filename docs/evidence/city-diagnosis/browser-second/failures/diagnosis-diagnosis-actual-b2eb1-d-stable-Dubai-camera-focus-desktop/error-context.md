# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: diagnosis.spec.ts >> diagnosis actual local services show source-backed buildings, loaded globe, transparent boundary and stable Dubai camera focus
- Location: tests/browser/diagnosis.spec.ts:104:1

# Error details

```
Error: expect(received).toBeLessThan(expected)

Expected: < 0.01
Received:   0.01237717336979216

Call Log:
- Timeout 15000ms exceeded while waiting on the predicate
```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e2]:
    - complementary "Workspace navigation" [ref=e3]:
      - link [ref=e4] [cursor=pointer]:
        - /url: "#overview"
      - navigation "Main navigation" [ref=e12]:
        - button "Overview" [ref=e13] [cursor=pointer]
        - button "Geospatial Data" [ref=e19] [cursor=pointer]
        - button "City Explorer" [ref=e22] [cursor=pointer]
        - button "Scenario Studio" [ref=e25] [cursor=pointer]
        - button "Simulation Laboratory" [ref=e30] [cursor=pointer]
        - button "Traffic Intelligence" [ref=e33] [cursor=pointer]
        - button "AI Command Center" [ref=e38] [cursor=pointer]
        - button "Analytics" [ref=e50] [cursor=pointer]
        - button "System Status" [ref=e53] [cursor=pointer]
        - button "Settings" [ref=e56] [cursor=pointer]
    - main [ref=e61]:
      - generic [ref=e62]:
        - generic [ref=e63]:
          - generic [ref=e64]: Workspace
          - strong [ref=e67]: City Explorer
        - generic [ref=e68]:
          - generic [ref=e69]: LOCAL DEVELOPMENT
          - generic [ref=e71]: M03
      - region "Dubai 3D digital twin" [ref=e75]:
        - generic [ref=e76]:
          - generic [ref=e77]:
            - paragraph [ref=e78]: DOWNTOWN DUBAI / BUSINESS BAY
            - heading "Dubai digital twin" [level=2] [ref=e79]
          - generic [ref=e80]: OPENSTREETMAP
        - generic [ref=e86]:
          - generic [ref=e87]:
            - text: Study region
            - combobox "3D study region" [ref=e88]:
              - option "Downtown Dubai / Business Bay — OpenStreetMap Study Area" [selected]
          - generic [ref=e89]:
            - text: Network version
            - combobox "3D network version" [ref=e90]:
              - option "osm-20261026-0b027352ec38 · published" [selected]
          - generic [ref=e91]:
            - generic "Show synthetic fixtures instead of imported geographic datasets" [ref=e92]:
              - checkbox "Development datasets" [ref=e93]
              - generic [ref=e96]: Development datasets
            - button "Enter fullscreen" [ref=e97] [cursor=pointer]
            - button "Layers" [ref=e103] [cursor=pointer]
            - button "Show feature inspector" [ref=e110] [cursor=pointer]
            - button "Refresh geographic data" [ref=e114] [cursor=pointer]
        - generic "Geographic data provenance" [ref=e120]:
          - generic [ref=e121]: REAL GEOGRAPHIC DATA — OpenStreetMap
          - generic [ref=e122]: 3D BUILDINGS — OSM source-height context · partial coverage
          - generic [ref=e123]: SYNTHETIC TRAFFIC — CLI smoke only; no viewer playback
          - generic [ref=e124]: LIVE TRAFFIC — Not connected
          - generic [ref=e125]: INFERRED SIGNALS — Not field verified
        - generic [ref=e127]:
          - generic [ref=e128]:
            - generic:
              - generic: CESIUM · WGS84
              - generic: OSM ROAD NETWORK
            - generic "Interactive 3D geographic globe" [ref=e130]:
              - generic [ref=e136]:
                - link [ref=e139] [cursor=pointer]:
                  - /url: https://cesium.com/
                  - img "Cesium ion" [ref=e140]
                - generic [ref=e141]:
                  - generic [ref=e142]:
                    - text: ©
                    - link "OpenStreetMap contributors" [ref=e143] [cursor=pointer]:
                      - /url: https://www.openstreetmap.org/copyright
                    - text: · ODbL
                  - text: •Made with Natural Earth · public domain
            - status:
              - generic: "500"
              - text: roads ·
              - generic: "0"
              - text: intersections rendered
            - generic "Map legend":
              - generic: primary link · motorway link · unclassified · primary
              - generic: Intersection
              - generic: OSM signal tag · unverified
              - generic: Selected feature
          - generic "Camera controls" [ref=e144]:
            - generic [ref=e145]:
              - button "Dubai overview" [ref=e146] [cursor=pointer]
              - button "Downtown Dubai" [ref=e147] [cursor=pointer]
              - button "Business Bay" [ref=e148] [cursor=pointer]
            - generic [ref=e149]:
              - button "Zoom to study region" [ref=e150] [cursor=pointer]
              - button "Zoom to selected feature" [disabled] [ref=e157]
              - button "Top-down view" [ref=e163] [cursor=pointer]
              - button "Perspective view" [active] [ref=e166] [cursor=pointer]
              - button "Zoom in" [ref=e170] [cursor=pointer]
              - button "Zoom out" [ref=e174] [cursor=pointer]
              - button "Reset camera" [ref=e178] [cursor=pointer]
          - generic "Camera position indicator" [ref=e182]:
            - generic [ref=e186]: 55.27440° E · 25.18478° N · 1,966 m altitude
            - generic [ref=e187]: EPSG:4326 · longitude, latitude
        - group [ref=e188]:
          - generic "Network & source details 2,364 roads · 1,560 nodes" [ref=e189] [cursor=pointer]:
            - text: Network & source details
            - generic [ref=e194]: 2,364 roads · 1,560 nodes
        - status:
          - paragraph: "Display budget reached: at most 500 features and 25,000 coordinate positions per layer. Zoom closer to inspect remaining features."
        - paragraph [ref=e197]:
          - generic [ref=e203]:
            - text: Local OpenStreetMap cartography over Natural Earth reference; no satellite imagery.
            - strong [ref=e204]: "Cesium ion building tiles unavailable:"
            - text: set CESIUM_ION_PUBLIC_TOKEN. Ellipsoid terrain; OSM tagged-height buildings cover only part of the source area.
        - button "Local rendering diagnostics" [ref=e206] [cursor=pointer]
  - alert [ref=e211]
```

# Test source

```ts
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
  86  |   }, { timeout: 25_000, message: "Settled camera must retain the requested actual ground focus" }).toBe(true);
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
> 158 |     await expect.poll(async () => Math.abs((await cameraState(page)).pitch + 55)).toBeLessThan(0.01);
      |                                                                                   ^ Error: expect(received).toBeLessThan(expected)
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
  187 |     const imagery = page.getByRole("checkbox", { name: "Geographic basemap", exact: true });
  188 |     await imagery.uncheck();
  189 |     await expect(scene).toHaveAttribute("data-imagery-status", "off");
  190 |     await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").imagery as boolean).toBe(false);
  191 |     await imagery.check();
  192 |     await expect(scene).toHaveAttribute("data-imagery-status", "blocked");
  193 |     await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").imagery as boolean).toBe(true);
  194 |     await expect.poll(() => observation.successfulTextures.length).toBeGreaterThan(0);
  195 |     expect(observation.errors).toEqual([]);
  196 |     expect(observation.httpFailures).toEqual([]);
  197 |     expect(unexpectedTransportFailures(observation)).toEqual([]);
  198 |     expect(observation.externalRequests).toEqual([]);
  199 |   } finally {
  200 |     await saveEvidence(page, "diagnosis-controlled-missing-token", info.project.name, { scope: "Controlled substitution of configuration only: imageryMode=ion and ionPublicToken=null; geography and assets remain actual local services; no working-ion claim", actualDeployedConfig: config, observation });
  201 |   }
  202 | });
  203 | 
  204 | test("diagnosis controlled context failure remains an error while stored geography and the globe stay usable", async ({ page }, info) => {
  205 |   test.setTimeout(90_000);
  206 |   const observation = observe(page);
  207 |   const config = await deployedConfig(page);
  208 |   let injectedFailures = 0;
  209 |   await page.route("**/geography/context.geojson", async route => { injectedFailures++; await route.abort("failed"); });
  210 |   try {
  211 |     const scene = await openCity(page);
  212 |     await expect(scene).toHaveAttribute("data-imagery-status", "error");
  213 |     await expect(page.locator('.city-provider-notice [role="alert"]')).toContainText("Imagery provider unavailable");
  214 |     await expect(scene).toHaveAttribute("data-buildings-status", "ready");
  215 |     await expect(scene).toHaveAttribute("data-local-building-count", "402");
  216 |     await expect.poll(async () => (await renderState(scene))?.globeTilesLoaded).toBe(true);
  217 |     await page.getByRole("button", { name: "Business Bay", exact: true }).click();
  218 |     await assertFocus(page, scene, [55.261, 25.182]);
  219 |     // Camera movement and later tile completion must not overwrite the error.
  220 |     await expect(scene).toHaveAttribute("data-imagery-status", "error");
  221 |     expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1 });
  222 |     expect(injectedFailures).toBeGreaterThan(0);
  223 |     expect(observation.requestFailures.some(failure => new URL(failure.path).pathname === "/geography/context.geojson")).toBe(true);
  224 |     expect(observation.httpFailures).toEqual([]);
  225 |     expect(unexpectedTransportFailures(observation).filter(failure => new URL(failure.path).pathname !== "/geography/context.geojson")).toEqual([]);
  226 |     expect(observation.errors.filter(error => !/net::ERR_FAILED/.test(error))).toEqual([]);
  227 |     expect(observation.externalRequests).toEqual([]);
  228 |   } finally {
  229 |     await saveEvidence(page, "diagnosis-controlled-context-failure", info.project.name, { scope: "Controlled transport abort of only the same-origin context GeoJSON; no substitute geographic response; expected browser network error retained", actualDeployedConfig: config, injectedFailures, observation });
  230 |   }
  231 | });
  232 | 
```