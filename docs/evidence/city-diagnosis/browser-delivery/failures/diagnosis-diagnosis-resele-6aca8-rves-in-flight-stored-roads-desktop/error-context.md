# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: diagnosis.spec.ts >> diagnosis reselecting the active fixture preserves in-flight stored roads
- Location: tests/browser/diagnosis.spec.ts:145:1

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
    61 × locator resolved to <div data-phase="ready" data-road-count="0" data-geometry-ready="true" data-camera-moving="false" class="city-viewer-surface" data-testid="cesium-viewer" data-imagery-status="ready" data-intersection-count="6" data-local-building-count="0" data-buildings-status="blocked" data-render-diagnostics="{"globeVisible":true,"globeTilesLoaded":true,"imageryLayerCount":1,"boundaryFillAlpha":0.13}" data-layer-visibility="{"boundary":true,"roads":false,"intersections":true,"centroid":false,"highlight":false,"b…>…</div>
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
  72  | async function deployedConfig(page: Page) {
  73  |   const response = await page.request.get("/api/city/config");
  74  |   expect(response.status()).toBe(200);
  75  |   const config = await response.json() as { imageryMode: string; diagnosticsEnabled: boolean; ionPublicToken: string | null };
  76  |   expect(config.imageryMode, "Actual deployed configuration must remain the self-hosted local mode for these checks").toBe("local-osm");
  77  |   expect(config.diagnosticsEnabled, "Native diagnostics require CITY_DIAGNOSTICS_ENABLED=true").toBe(true);
  78  |   return { imageryMode: config.imageryMode, diagnosticsEnabled: config.diagnosticsEnabled, publicTokenConfigured: Boolean(config.ionPublicToken) };
  79  | }
  80  | async function openCity(page: Page): Promise<Locator> {
  81  |   await page.goto("/");
  82  |   await expect(page.getByRole("heading", { name: "Dubai digital twin", exact: true })).toBeVisible();
  83  |   await expect(page.getByRole("checkbox", { name: "Development datasets", exact: true })).not.toBeChecked();
  84  |   await expect(page.getByTestId("city-geographic-source")).toHaveText("REAL GEOGRAPHIC DATA — OpenStreetMap");
  85  |   const scene = page.getByTestId("cesium-viewer");
  86  |   await expect.poll(() => scene.evaluate(element => ({
  87  |     phase: element.getAttribute("data-phase"),
  88  |     roads: Number(element.getAttribute("data-road-count")) > 0,
  89  |     geometry: element.getAttribute("data-geometry-ready") === "true",
  90  |     settled: element.getAttribute("data-camera-moving") === "false",
  91  |     canvases: element.querySelectorAll("canvas").length,
  92  |   })), { timeout: 60_000 }).toEqual({ phase: "ready", roads: true, geometry: true, settled: true, canvases: 1 });
  93  |   return scene;
  94  | }
  95  | async function renderState(scene: Locator): Promise<RenderDiagnostics> {
  96  |   return JSON.parse(await scene.getAttribute("data-render-diagnostics") ?? "null") as RenderDiagnostics;
  97  | }
  98  | async function cameraState(page: Page): Promise<Camera> {
  99  |   return JSON.parse(await page.getByTestId("camera-position").getAttribute("data-camera") ?? "null") as Camera;
  100 | }
  101 | function targetFramePitchAllowance(camera: Camera): number {
  102 |   if (!camera.groundFocus) return 0;
  103 |   // Installed Cesium Camera.flyToBoundingSphere uses the target ENU frame;
  104 |   // Camera.pitch measures in the camera-position ENU frame. Their pitch difference
  105 |   // is bounded by the angle between those up normals, plus 0.001° numeric slack.
  106 |   // FixedFrameTransforms computes its up axis from the WGS84 Cartesian gradient.
  107 |   const up = (longitude: number, latitude: number, height: number): [number,number,number] => {
  108 |     const lon = longitude * Math.PI / 180, lat = latitude * Math.PI / 180;
  109 |     const e2 = 6.6943799901413165e-3;
  110 |     const radius = 6378137 / Math.sqrt(1 - e2 * Math.sin(lat) ** 2);
  111 |     const [x,y,z] = [(radius + height) * Math.cos(lat) * Math.cos(lon), (radius + height) * Math.cos(lat) * Math.sin(lon), (radius * (1 - e2) + height) * Math.sin(lat) / (1 - e2)] as const;
  112 |     const length = Math.hypot(x,y,z);
  113 |     return [x/length,y/length,z/length];
  114 |   };
  115 |   const cameraUp = up(camera.longitude, camera.latitude, camera.height);
  116 |   const targetUp = up(camera.groundFocus[0], camera.groundFocus[1], 0);
  117 |   const dot = cameraUp[0]*targetUp[0]+cameraUp[1]*targetUp[1]+cameraUp[2]*targetUp[2];
  118 |   return Math.acos(Math.max(-1, Math.min(1, dot))) * 180 / Math.PI + 0.001;
  119 | }
  120 | async function assertFocus(page: Page, scene: Locator, target: [number, number]): Promise<Camera> {
  121 |   await expect.poll(async () => {
  122 |     const camera = await cameraState(page);
  123 |     return Boolean(camera?.groundFocus && await scene.getAttribute("data-camera-moving") === "false" &&
  124 |       Math.abs(camera.groundFocus[0] - target[0]) < 0.0005 && Math.abs(camera.groundFocus[1] - target[1]) < 0.0005);
  125 |   }, { timeout: 25_000, message: "Settled camera must retain the requested actual ground focus" }).toBe(true);
  126 |   const camera = await cameraState(page);
  127 |   for (const value of [camera.longitude, camera.latitude, camera.height, camera.heading, camera.pitch]) expect(Number.isFinite(value)).toBe(true);
  128 |   expect(camera.height).toBeGreaterThan(0);
  129 |   expect(camera.pitch).toBeLessThan(0);
  130 |   expect(camera.pitch).toBeGreaterThanOrEqual(-90.00001);
  131 |   expect(camera.bounds).not.toBeNull();
  132 |   return camera;
  133 | }
  134 | function unexpectedTransportFailures(observation: Observation) {
  135 |   // useCityData consumes TanStack's signal for network catalogs and viewport
  136 |   // reads. Only exact same-origin bounded GET shapes may be aborted; every
  137 |   // failure and its classification remain in the evidence above.
  138 |   return observation.requestFailures.filter(failure => !failure.expectedCancellation);
  139 | }
  140 | async function saveEvidence(page: Page, name: string, project: string, data: unknown) {
  141 |   await writeFile(browserEvidencePath(`${name}-${project}.json`), `${JSON.stringify(data, null, 2)}\n`);
  142 |   await page.screenshot({ path: browserEvidencePath(`${name}-${project}.png`), fullPage: true });
  143 | }
  144 | 
  145 | test("diagnosis reselecting the active fixture preserves in-flight stored roads",async({page},info)=>{
  146 |   test.setTimeout(90_000);
  147 |   const observation=observe(page);
  148 |   const config=await deployedConfig(page);
  149 |   let release=()=>{};
  150 |   const gate=new Promise<void>(resolve=>{release=resolve;});
  151 |   let held=0;
  152 |   await page.route("**/api/geospatial/networks/22f68ce8-9247-5425-8342-827d86517ead/edges?**",async route=>{
  153 |     held++;
  154 |     await gate;
  155 |     await route.continue();
  156 |   });
  157 |   try {
  158 |     await page.goto("/");
  159 |     await page.getByRole("checkbox",{name:"Development datasets",exact:true}).check();
  160 |     const region=page.getByLabel("3D study region",{exact:true});
  161 |     const network=page.getByLabel("3D network version",{exact:true});
  162 |     await expect.poll(()=>held).toBeGreaterThan(0);
  163 |     const scene=page.getByTestId("cesium-viewer");
  164 |     await expect(network).toHaveValue("22f68ce8-9247-5425-8342-827d86517ead");
  165 |     await expect(scene).toHaveAttribute("data-imagery-status","ready");
  166 |     await assertFocus(page,scene,[55.2745,25.195]);
  167 |     // Both existing fixture selections are already in effect. Re-emitting change
  168 |     // must not cancel an unchanged query key and leave it idle without data.
  169 |     await region.selectOption(await region.inputValue());
  170 |     await network.selectOption(await network.inputValue());
  171 |     release();
> 172 |     await expect(scene).toHaveAttribute("data-road-count","8",{timeout:30_000});
      |                         ^ Error: expect(locator).toHaveAttribute(expected) failed
  173 |     await expect(scene).toHaveAttribute("data-intersection-count","6");
  174 |     await expect(scene).toHaveAttribute("data-phase","ready");
  175 |     expect(observation.errors).toEqual([]);
  176 |     expect(observation.httpFailures).toEqual([]);
  177 |     expect(unexpectedTransportFailures(observation)).toEqual([]);
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
```