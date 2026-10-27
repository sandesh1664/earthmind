# CesiumJS integration — M03

CesiumJS 1.146.0 is pinned in the npm workspace and lock. Its published Node
requirement is >=22; the existing Node22 ARM64 container satisfies it. The
existing strict Next.js App Router and React19 application remain in place.

## Browser initialization and assets

City Explorer is a lazy client module. The viewer sets `window.CESIUM_BASE_URL`
to `/cesium/` before dynamically importing Cesium and its scene controller.
The server never constructs a Viewer or accesses WebGL. Cesium Widgets CSS is
imported by the application layout.

`npm run dev` and `npm run build` run `scripts/copy-cesium-assets.mjs` first. That
script checks the installed Cesium version against the exact dependency, then
copies Workers, ThirdParty, Assets, Widgets and upstream license/notice files
into ignored `apps/web/public/cesium`. It does not download provider data.
The Docker build runs the same script; its standalone runtime explicitly copies
`public`, alongside Next's standalone output and static chunks. Generated Cesium
assets are excluded from Git, ESLint inputs and the host Docker context.

`/cesium/manifest.json` identifies the installed version. Verify Workers JS,
ThirdParty WASM/JS, Natural Earth imagery and Widgets CSS over HTTP after any
packaging change. A successful webpack/Turbopack compilation alone is not proof
that workers resolve. The production browser checks exercise the deployed scene.

## Viewer ownership

React owns UI configuration, query results, typed feature selection and camera
commands. A mount-scoped controller owns the native Viewer, geometry collections,
provider instances and event subscriptions. Callback refs keep updates current
without reconstructing the viewer on React renders. Cleanup cancels outstanding
work, detaches events, destroys owned resources, explicitly releases its owned WebGL context when the
standard WEBGL_lose_context extension is available, and prevents asynchronous results
from modifying a destroyed scene. React Strict Mode's development remount is
handled as a normal create/dispose cycle; no native object enters an application
store or browser global.

Request-render mode avoids an always-running scene when idle. Camera and layer
changes request frames explicitly. Geometry updates depend on geographic data
identity rather than unrelated inspector changes; selected styling is separate.
See the actual implementation under `apps/web/components/city/runtime` and the
recorded lifecycle/browser results in verification.md.

## Lawful credential-free mode

The M03 reference mode starts with ellipsoid terrain and locally packaged Natural Earth II
imagery. This is low-resolution cartography, not current satellite imagery.
Natural Earth describes its raster/vector data as public domain. Visible credits
and upstream Cesium notices remain available. Region/road/intersection overlays
come from PostGIS regardless of optional provider access. No external tile
scraping, fallback public OSM tile harvesting or invented 3D buildings occurs.

## Optional Cesium ion access

Only these runtime environment variables are exposed by the allowlisted
`GET /api/city/config` route:

```dotenv
CESIUM_ION_PUBLIC_TOKEN=
CESIUM_ION_IMAGERY_ASSET_ID=3812
CESIUM_ION_TERRAIN_ASSET_ID=1
CITY_DIAGNOSTICS_ENABLED=false
```

Create an intentionally public, read-only ion visualization token restricted to
the necessary assets and deployment origins in your own account. Follow current
ion terms and entitlements. Never paste an account administrator, upload/write,
private GIS or server service token into this setting. Browser tokens are
observable by design. Private environment values and the M02 write token are
never returned. No token is baked through `NEXT_PUBLIC_*` or committed.

Configure the ignored `.env`, then recreate the web service so it reads the new
runtime environment. Missing tokens leave ion building tiles/terrain explicitly blocked;
this is not an application initialization failure. Optional provider requests
use supported asynchronous APIs, retain automatic attribution and surface
loading/errors. Provider failure must leave the local globe and backend overlays
usable. Available building properties are displayed as escaped text; coverage,
height and name are never invented.

Real building rendering and attribution with an authorized token must be reported
BLOCKED until actually exercised. Do not replace this gate with mocked tiles.

## References checked

- https://cesium.com/learn/cesiumjs-learn/cesiumjs-quickstart/
- https://cesium.com/learn/cesiumjs/ref-doc/Viewer.html
- https://cesium.com/learn/cesiumjs/ref-doc/IonImageryProvider.html
- https://www.naturalearthdata.com/about/terms-of-use/

The installed package source/type declarations are the version-specific authority
for asynchronous API signatures; current documentation was checked as well.

Public token scope and URL restrictions follow Cesium's
[access-token guide](https://cesium.com/learn/ion/cesium-ion-access-tokens/).
Use only `assets:read`, restrict required asset IDs and allowed app origins, and
retain the browser Referer needed by URL restrictions. The current referrer
policy sends the origin on cross-origin requests. No geocoder is enabled.
For captures that include licensed ion content, display the actual required
provider attribution in the capture; an unexplained attribution link alone is
insufficient under the [content guide](https://cesium.com/learn/ion/content-usage-and-attribution-guide/).

Camera loading uses measured public pose settlement (350ms stable within0.05m
position/1e-7 unit-vector orientation, with viewport changes included) followed
by the350ms query debounce. This avoids relying only on native moveEnd precision
when a visibly stationary camera still produces tiny native changes. Top-down
and perspective modes orbit the actual ground focus, preserving the selected
view instead of rotating at the displaced camera position.

The pinned1.146 widget teardown removes input actions but does not destroy its
public ScreenSpaceEventHandler. The integration explicitly destroys that handler
before Viewer.destroy (which guards an already-destroyed handler), then releases
the owned WebGL context when supported. This uses public APIs; no vendor source
or SDK private field is patched. The long browser regression checks DOM/listener
counts because a zero canvas count alone did not reveal the retained listeners.

Clean installs apply `patches/@cesium+engine+26.4.0.patch` using pinned
patch-package8.0.1. The three-statement change uses a WeakMap keyed by Context
for cached terrain index buffers, avoiding a strong UUID-keyed path from the
global terrain grid cache to destroyed buffers and old canvases. The dev/build
asset script verifies both exact engine version and the patched source SHA256;
a skipped or incompatible patch fails the build. Docker copies the patch before
npmci. See [ADR0011](decisions/0011-cesium-lifecycle-patch.md).

Owned SDK credit-style elements are tracked during synchronous Viewer creation
and removed on disposal (also on initialization failure). Existing styles and
attribution remain untouched while the viewer is active. Memory measurements
disable DOM snapshot tracing because controlled trace-on/off experiments showed
that tracer retention inflated DOM/listener counts. Functional browser checks
retain failure traces separately.


## Recovery default

`CITY_IMAGERY_MODE=local-osm` now selects self-hosted OSM vector cartography plus
explicit-height footprint models from the retained licensed extract. The web
container mounts only generated public context under `/geography`; raw source,
DB mapping and SUMO files remain private. Context file bytes are hash-checked
against their manifest before schema validation/native adoption. Local mode uses
ellipsoid-only heights; provider terrain is blocked to avoid mixed height models.
`natural-earth` remains the explicit lightweight global/test mode. `ion` uses
configured public asset access; licensed provider tile execution remains blocked
until credentials are actually available. See recovery-geography.md for details.
