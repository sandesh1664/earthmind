# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: diagnosis.spec.ts >> diagnosis actual local services show source-backed buildings, loaded globe, transparent boundary and stable Dubai camera focus
- Location: tests/browser/diagnosis.spec.ts:220:1

# Error details

```
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 8

- Array []
+ Array [
+   Object {
+     "cancellationScope": null,
+     "error": "net::ERR_ABORTED",
+     "expectedCancellation": false,
+     "path": "http://127.0.0.1:3000/api/geospatial/data-sources/6c360c5b-0e03-5144-8eed-196d402bffd2",
+   },
+ ]
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
  178 |     expect(observation.externalRequests).toEqual([]);
  179 |   } finally {
  180 |     release();
  181 |     await saveEvidence(page,"diagnosis-controlled-same-selection",info.project.name,{scope:"Existing explicitly selected synthetic-v1 fixture from actual PostGIS/API; its real spatial responses held/released while unchanged selections are re-emitted; no fabricated or newly imported data",actualDeployedConfig:config,held,observation});
  182 |   }
  183 | });
  184 | 
  185 | test("diagnosis controlled worker delay keeps source geometry loading until native preparation finishes", async ({page},info) => {
  186 |   test.setTimeout(90_000);
  187 |   const observation = observe(page);
  188 |   const config = await deployedConfig(page);
  189 |   let release = () => {};
  190 |   const gate = new Promise<void>(resolve => {release=resolve;});
  191 |   let heldWorkers = 0;
  192 |   await page.route("**/cesium/Workers/createGeometry.js",async route => {
  193 |     heldWorkers++;
  194 |     await gate;
  195 |     await route.continue();
  196 |   });
  197 |   try {
  198 |     await page.goto("/");
  199 |     const scene = page.getByTestId("cesium-viewer");
  200 |     // Actual GeoJSON has been adopted, but its real geometry worker cannot yet
  201 |     // prepare any mesh. A latched DataSourceDisplay.ready must not win this race.
  202 |     await expect(scene).toHaveAttribute("data-local-building-count","402",{timeout:30_000});
  203 |     await expect.poll(()=>heldWorkers).toBeGreaterThan(0);
  204 |     await expect(scene).toHaveAttribute("data-buildings-status","loading");
  205 |     await expect(scene).toHaveAttribute("data-imagery-status","loading");
  206 |     release();
  207 |     await expect(scene).toHaveAttribute("data-buildings-status","ready",{timeout:60_000});
  208 |     await expect(scene).toHaveAttribute("data-imagery-status","ready",{timeout:60_000});
  209 |     await expect.poll(async()=>Number(await scene.getAttribute("data-road-count"))).toBeGreaterThan(0);
  210 |     expect(observation.errors).toEqual([]);
  211 |     expect(observation.httpFailures).toEqual([]);
  212 |     expect(unexpectedTransportFailures(observation)).toEqual([]);
  213 |     expect(observation.externalRequests).toEqual([]);
  214 |   } finally {
  215 |     release();
  216 |     await saveEvidence(page,"diagnosis-controlled-worker-delay",info.project.name,{scope:"Controlled transport hold/release of the actual same-origin geometry worker script; no replacement geographic data or worker code",actualDeployedConfig:config,heldWorkers,observation});
  217 |   }
  218 | });
  219 | 
  220 | test("diagnosis actual local services show source-backed buildings, loaded globe, transparent boundary and stable Dubai camera focus", async ({ page }, info) => {
  221 |   test.setTimeout(120_000);
  222 |   const observation = observe(page);
  223 |   const config = await deployedConfig(page);
  224 |   const cameras: Record<string, Camera> = {};
  225 |   let network: unknown = null;
  226 |   try {
  227 |     const scene = await openCity(page);
  228 |     await expect(scene).toHaveAttribute("data-imagery-status", "ready");
  229 |     await expect(scene).toHaveAttribute("data-buildings-status", "ready");
  230 |     const manifestResponse = await page.request.get("/geography/manifest.json");
  231 |     expect(manifestResponse.status()).toBe(200);
  232 |     const manifest = await manifestResponse.json() as { source: string; source_sha256: string; explicit_height_buildings: number };
  233 |     expect(manifest.source).toBe("OpenStreetMap");
  234 |     expect(manifest.explicit_height_buildings).toBe(402);
  235 |     await expect(scene).toHaveAttribute("data-local-building-count", "402");
  236 |     const networkId = await page.getByLabel("3D network version", { exact: true }).inputValue();
  237 |     const networkResponse = await page.request.get(`/api/geospatial/networks/${networkId}`);
  238 |     expect(networkResponse.status()).toBe(200);
  239 |     const currentNetwork = await networkResponse.json() as { is_synthetic: boolean; version_label: string; data_source_id: string; node_count: number; edge_count: number };
  240 |     expect(currentNetwork.is_synthetic).toBe(false);
  241 |     expect(currentNetwork.version_label).toMatch(/^osm-/);
  242 |     expect(currentNetwork.node_count).toBeGreaterThan(6);
  243 |     expect(currentNetwork.edge_count).toBeGreaterThan(8);
  244 |     const sourceResponse = await page.request.get(`/api/geospatial/data-sources/${currentNetwork.data_source_id}`);
  245 |     expect(sourceResponse.status()).toBe(200);
  246 |     const source = await sourceResponse.json() as { provider_name: string; license_identifier: string; checksum_sha256: string };
  247 |     expect(source.provider_name).toContain("OpenStreetMap");
  248 |     expect(source.license_identifier).toBe("ODbL-1.0");
  249 |     expect(source.checksum_sha256).toBe(manifest.source_sha256);
  250 |     network = { id: networkId, ...currentNetwork, source };
  251 |     await expect.poll(async () => (await renderState(scene))?.globeTilesLoaded, { timeout: 30_000 }).toBe(true);
  252 |     expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1, boundaryFillAlpha: 0.13 });
  253 |     await expect.poll(() => observation.successfulTextures.length).toBeGreaterThan(0);
  254 |     await expect.poll(() => observation.workers.length).toBeGreaterThan(0);
  255 |     cameras.initial = await assertFocus(page, scene, [55.2744, 25.1972]);
  256 |     await page.getByRole("button", { name: "Layers", exact: true }).click();
  257 |     const boundary = page.getByRole("checkbox", { name: "Study region", exact: true });
  258 |     await expect(boundary).not.toBeChecked();
  259 |     await boundary.check();
  260 |     await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").boundary as boolean).toBe(true);
  261 |     expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1, boundaryFillAlpha: 0.13 });
  262 |     await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").imagery as boolean).toBe(true);
  263 |     await page.screenshot({ path: browserEvidencePath(`diagnosis-boundary-visible-${info.project.name}.png`), fullPage: true });
  264 |     await boundary.uncheck();
  265 |     await page.getByRole("button", { name: "Close layers", exact: true }).click();
  266 |     await page.getByRole("button", { name: "Business Bay", exact: true }).click();
  267 |     cameras.businessBay = await assertFocus(page, scene, [55.261, 25.182]);
  268 |     await page.getByRole("button", { name: "Downtown Dubai", exact: true }).click();
  269 |     cameras.downtown = await assertFocus(page, scene, [55.2744, 25.1972]);
  270 |     await page.getByRole("button", { name: "Top-down view", exact: true }).click();
  271 |     await expect.poll(async () => { const camera = await cameraState(page); return Math.abs(camera.pitch + 90) <= targetFramePitchAllowance(camera); }).toBe(true);
  272 |     cameras.topDown = await assertFocus(page, scene, cameras.downtown.groundFocus!);
  273 |     await page.getByRole("button", { name: "Perspective view", exact: true }).click();
  274 |     await expect.poll(async () => { const camera = await cameraState(page); return Math.abs(camera.pitch + 55) <= targetFramePitchAllowance(camera); }).toBe(true);
  275 |     cameras.perspective = await assertFocus(page, scene, cameras.topDown.groundFocus!);
  276 |     expect(observation.errors).toEqual([]);
  277 |     expect(observation.httpFailures).toEqual([]);
> 278 |     expect(unexpectedTransportFailures(observation)).toEqual([]);
      |                                                      ^ Error: expect(received).toEqual(expected) // deep equality
  279 |     expect(observation.externalRequests).toEqual([]);
  280 |   } finally {
  281 |     await saveEvidence(page, "diagnosis-actual-local", info.project.name, { scope: "Actual deployed local services and retained source data; no geographic response substitutions; does not verify satellite or ion buildings", config, network, cameras, observation });
  282 |   }
  283 | });
  284 | 
  285 | test("diagnosis controlled configuration: missing ion token remains blocked with honest usable Natural Earth fallback", async ({ page }, info) => {
  286 |   test.setTimeout(90_000);
  287 |   const observation = observe(page);
  288 |   const config = await deployedConfig(page);
  289 |   await page.route("**/api/city/config", async route => {
  290 |     const response = await route.fetch();
  291 |     const actual = await response.json() as Record<string, unknown>;
  292 |     await route.fulfill({ response, json: { ...actual, imageryMode: "ion", ionPublicToken: null } });
  293 |   });
  294 |   try {
  295 |     const scene = await openCity(page);
  296 |     await expect(scene).toHaveAttribute("data-imagery-status", "blocked");
  297 |     await expect(scene).toHaveAttribute("data-buildings-status", "blocked");
  298 |     await expect.poll(async () => (await renderState(scene))?.globeTilesLoaded).toBe(true);
  299 |     expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1 });
  300 |     await expect(page.locator(".cesium-widget-credits")).toContainText("Natural Earth");
  301 |     await page.getByRole("button", { name: "Layers", exact: true }).click();
  302 |     await expect(page.locator(".city-layer-detail").filter({ hasText: /Natural Earth/i })).toContainText(/token|unavailable|blocked/i);
  303 |     const imagery = page.getByRole("checkbox", { name: "Geographic basemap", exact: true });
  304 |     await imagery.uncheck();
  305 |     await expect(scene).toHaveAttribute("data-imagery-status", "off");
  306 |     await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").imagery as boolean).toBe(false);
  307 |     await imagery.check();
  308 |     await expect(scene).toHaveAttribute("data-imagery-status", "blocked");
  309 |     await expect.poll(async () => JSON.parse(await scene.getAttribute("data-layer-visibility") ?? "{}").imagery as boolean).toBe(true);
  310 |     await expect.poll(() => observation.successfulTextures.length).toBeGreaterThan(0);
  311 |     expect(observation.errors).toEqual([]);
  312 |     expect(observation.httpFailures).toEqual([]);
  313 |     expect(unexpectedTransportFailures(observation)).toEqual([]);
  314 |     expect(observation.externalRequests).toEqual([]);
  315 |   } finally {
  316 |     await saveEvidence(page, "diagnosis-controlled-missing-token", info.project.name, { scope: "Controlled substitution of configuration only: imageryMode=ion and ionPublicToken=null; geography and assets remain actual local services; no working-ion claim", actualDeployedConfig: config, observation });
  317 |   }
  318 | });
  319 | 
  320 | test("diagnosis controlled context failure remains an error while stored geography and the globe stay usable", async ({ page }, info) => {
  321 |   test.setTimeout(90_000);
  322 |   const observation = observe(page);
  323 |   const config = await deployedConfig(page);
  324 |   let injectedFailures = 0;
  325 |   await page.route("**/geography/context.geojson", async route => { injectedFailures++; await route.abort("failed"); });
  326 |   try {
  327 |     const scene = await openCity(page);
  328 |     await expect(scene).toHaveAttribute("data-imagery-status", "error");
  329 |     await expect(page.locator('.city-provider-notice [role="alert"]')).toContainText("Imagery provider unavailable");
  330 |     await expect(scene).toHaveAttribute("data-buildings-status", "ready");
  331 |     await expect(scene).toHaveAttribute("data-local-building-count", "402");
  332 |     await expect.poll(async () => (await renderState(scene))?.globeTilesLoaded).toBe(true);
  333 |     await page.getByRole("button", { name: "Business Bay", exact: true }).click();
  334 |     await assertFocus(page, scene, [55.261, 25.182]);
  335 |     // Camera movement and later tile completion must not overwrite the error.
  336 |     await expect(scene).toHaveAttribute("data-imagery-status", "error");
  337 |     expect(await renderState(scene)).toMatchObject({ globeVisible: true, imageryLayerCount: 1 });
  338 |     expect(injectedFailures).toBeGreaterThan(0);
  339 |     expect(observation.requestFailures.some(failure => new URL(failure.path).pathname === "/geography/context.geojson")).toBe(true);
  340 |     expect(observation.httpFailures).toEqual([]);
  341 |     expect(unexpectedTransportFailures(observation).filter(failure => new URL(failure.path).pathname !== "/geography/context.geojson")).toEqual([]);
  342 |     expect(observation.errors.filter(error => !/net::ERR_FAILED/.test(error))).toEqual([]);
  343 |     expect(observation.externalRequests).toEqual([]);
  344 |   } finally {
  345 |     await saveEvidence(page, "diagnosis-controlled-context-failure", info.project.name, { scope: "Controlled transport abort of only the same-origin context GeoJSON; no substitute geographic response; expected browser network error retained", actualDeployedConfig: config, injectedFailures, observation });
  346 |   }
  347 | });
  348 | 
```