# Cesium ion integration and visualization modes

This integration uses installed CesiumJS 1.146.0 and the existing Next.js App
Router, PostGIS network, same-origin APIs and mount-owned Viewer. It adds two
presentation modes; it does not import geography or implement simulations.

## Local public token configuration

The canonical setting is `NEXT_PUBLIC_CESIUM_ION_TOKEN`. The existing
`CESIUM_ION_PUBLIC_TOKEN` is a supported legacy alias. Set one, or use the same
value for both. Different nonempty values fail with a safe, actionable
configuration error. Private token names are never used as a browser token.

For Docker Compose, edit the ignored repository-root `.env` locally:

```dotenv
NEXT_PUBLIC_CESIUM_ION_TOKEN=<your public scoped token, configured locally>
CESIUM_ION_PUBLIC_TOKEN=
CESIUM_ION_IMAGERY_ASSET_ID=2
CESIUM_ION_TERRAIN_ASSET_ID=1
CITY_IMAGERY_MODE=local-osm
```

Use `assets:read` with access to the required assets and allowed application
origins. Include the actual development origin (`http://localhost:3000`, and
`http://127.0.0.1:3000` if used) in URL restrictions. The existing
strict-origin-when-cross-origin policy retains the Referer needed by restricted
tokens. Never put account/upload/admin credentials in either public setting.
[Cesium's token documentation](https://cesium.com/learn/ion/cesium-ion-access-tokens/).

After a credentials/asset change, recreate the web container so Compose reads
`.env` again; a plain `docker restart` does not reinject environment values:

```sh
cd /Users/redmug/EARTHMIND
CITY_DIAGNOSTICS_ENABLED=true docker compose --env-file .env up --detach --no-deps --force-recreate --wait web
```

For first deployment of this code, add `--build`. Diagnostics are optional in
normal use; they are needed for the native camera/picking verification suite.
Refresh the page after restarting, then select **Realistic city**. Engineering
remains the initial mode and has no hosted provider dependency.

For direct Next.js development, `apps/web/.env.local` follows Next's normal
project-root convention. Restart the Next process after changing configuration.
The dynamic, no-store `/api/city/config` route reads the runtime environment and
returns only the five allowlisted visualization fields. Runtime indirection is
intentional: the token is not embedded in built JavaScript, and credentials do
not require a new image build. The `NEXT_PUBLIC_` name still identifies an
intentionally browser-observable visualization token. Do not log the response
body or include credentials in screenshots, trace archives or Git.

## Provider and mode behavior

Engineering uses retained OSM cartography, explicit source-height extrusions,
color-coded PostGIS road categories and the existing inspector/debugging tools.
Realistic requests ion aerial imagery, Cesium OSM Buildings and natural daylight
with restrained shadows. It replaces providers and road presentation inside the
same Viewer; mode changes do not reset the camera or typed selection.

The installed SDK's `IonWorldImageryStyle.AERIAL` maps to asset **2**. The
integration uses the underlying public `IonImageryProvider.fromAssetId` API with
an explicit access token for this asset and configured alternatives. This is the
same World Imagery provider as `createWorldImageryAsync`, while also keying the
SDK endpoint cache by the actual token during runtime configuration changes. OSM Buildings uses supported
`createOsmBuildingsAsync` (asset **96188**). No default evaluation token is
borrowed and no runtime cycling through alternate assets hides a provider error.

In this account's actual access probe, legacy imagery asset **3812 returned
HTTP 404**, while imagery **2**, buildings **96188** and terrain **1** returned
HTTP 200. These endpoint results alone do not prove visible tiles; actual browser
results and screenshots are recorded in the verification report. Default imagery
is now asset 2, and an explicitly configured unavailable asset remains a visible
error. Asset availability and entitlements remain account/provider dependent.
[Cesium imagery guide](https://cesium.com/learn/cesiumjs-learn/cesiumjs-imagery/).

Missing credentials report blocked access and identify the coarse Natural Earth
reference fallback. HTTP401 identifies a rejected token, HTTP403 denied
asset/origin access, HTTP404/410 an unavailable asset, and HTTP429 quota/rate
limits. Errors stay visible outside the closed Layers panel. Backend roads and
inspection remain usable; switch back to Engineering without moving the camera.
Synthetic development scopes never mix in real ion buildings or terrain.

Ellipsoid terrain remains the aligned default for the source-derived geometry.
Authorized World Terrain is optional through the layer control; no fabricated
terrain or height guesses are introduced. Flat-surface camera controls use the
analytic WGS84 intersection; configured terrain retains the terrain-aware path.
Daylight uses a documented presentation reference, 2026-10-27 09:00 UTC / 13:00
Dubai, rather than implying live weather/time. Camera destinations retain their
geographic coordinates and use eased flights.

Credits remain enabled and provider attribution is retained. Follow the account
plan and content terms before commercial use/distribution; the current provider
may display its account-plan credit. This work does not change account licensing.
[Cesium content/attribution guide](https://cesium.com/learn/ion/content-usage-and-attribution-guide/).

## Verification safety

Browser traces are off because they retain signed URLs and public configuration
response bodies. Tests instead record sanitized origins/paths, HTTP statuses,
MIME/resource types, actual camera/Viewer identity and screenshots. They never
store token values, signed URL queries or provider response headers. A controlled
legacy-asset check uses a real remote HTTP404, not fake tiles. Existing PostGIS
records, immutable source provenance and inspectors remain preserved.
