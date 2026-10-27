# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: diagnosis.spec.ts >> diagnosis actual local services show source-backed buildings, loaded globe, transparent boundary and stable Dubai camera focus
- Location: tests/browser/diagnosis.spec.ts:220:1

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
  25  |   try { const url = new URL(value); return `${url.origin}${url.pathname}`; }
  26  |   catch { return "[non-URL]"; }
  27  | }
  28  | function safeText(value: string): string {
  29  |   return value
  30  |     .replace(/https?:\/\/[^\s"'<>]+/g, safeURL)
  31  |     .replace(/((?:access_)?token|authorization)\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]")
  32  |     .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g, "[REDACTED]");
  33  | }
  34  | function cancellableRead(request: import("@playwright/test").Request, page: Page): "network-catalog" | "spatial" | null {
  35  |   const url = new URL(request.url());
  36  |   if (request.method() !== "GET" || url.origin !== new URL(page.url()).origin) return null;
  37  |   const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
  38  |   const keys = [...url.searchParams.keys()].sort().join(",");
  39  |   const offset = Number(url.searchParams.get("offset"));
  40  |   if (url.searchParams.get("limit") !== "100" || !Number.isInteger(offset) || offset < 0 || offset >= 500 || offset % 100 !== 0) return null;
  41  |   if (url.pathname === "/api/geospatial/networks" && keys === "limit,offset,region_id" && uuid.test(url.searchParams.get("region_id") ?? "")) return "network-catalog";
  42  |   const spatial = url.pathname.match(/^\/api\/geospatial\/networks\/([^/]+)\/(edges|intersections)$/);
  43  |   const bbox = url.searchParams.get("bbox")?.split(",").map(Number);
  44  |   if (!spatial?.[1] || !uuid.test(spatial[1]) || keys !== "bbox,limit,offset" || bbox?.length !== 4 || !bbox.every(Number.isFinite)) return null;
  45  |   const [west,south,east,north] = bbox as [number,number,number,number];
  46  |   if (west >= -180 && east <= 180 && south >= -90 && north <= 90 &&
  47  |     east > west && east - west <= 1 && north > south && north - south <= 1) return "spatial";
  48  |   return null;
  49  | }
  50  | function observe(page: Page): Observation {
  51  |   const result: Observation = { errors: [], httpFailures: [], requestFailures: [], externalRequests: [], workers: [], textureRequests: [], successfulTextures: [] };
  52  |   page.on("pageerror", error => result.errors.push(safeText(error.message)));
  53  |   page.on("console", message => { if (message.type() === "error") result.errors.push(safeText(message.text())); });
  54  |   page.on("worker", worker => result.workers.push(safeURL(worker.url())));
  55  |   page.on("request", request => {
  56  |     const url = new URL(request.url());
  57  |     if (/^https?:$/.test(url.protocol) && !["127.0.0.1", "localhost"].includes(url.hostname)) result.externalRequests.push(safeURL(request.url()));
  58  |     if (/\/cesium\/Assets\/Textures\/NaturalEarthII\/.*\.jpg$/.test(url.pathname)) result.textureRequests.push(safeURL(request.url()));
  59  |   });
  60  |   page.on("requestfailed", request => {
  61  |     const error = safeText(request.failure()?.errorText ?? "Unknown transport failure");
  62  |     const cancellationScope = cancellableRead(request, page);
  63  |     result.requestFailures.push({ path: safeURL(request.url()), error, expectedCancellation: error === "net::ERR_ABORTED" && cancellationScope !== null, cancellationScope });
  64  |   });
  65  |   page.on("response", response => {
  66  |     const path = new URL(response.url()).pathname;
  67  |     if (response.status() >= 400) result.httpFailures.push(`${response.status()} ${safeURL(response.url())}`);
  68  |     if (response.ok() && /\/cesium\/Assets\/Textures\/NaturalEarthII\/.*\.jpg$/.test(path)) result.successfulTextures.push(safeURL(response.url()));
  69  |   });
  70  |   return result;
  71  | }
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
> 125 |   }, { timeout: 25_000, message: "Settled camera must retain the requested actual ground focus" }).toBe(true);
      |                                                                                                    ^ Error: Settled camera must retain the requested actual ground focus
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
  172 |     await expect(scene).toHaveAttribute("data-road-count","8",{timeout:30_000});
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
```