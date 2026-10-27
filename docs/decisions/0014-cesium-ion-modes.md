# ADR 0014: Runtime public ion configuration and persistent city modes

Date: 2026-10-27

Status: accepted for the bounded M03.5 Cesium integration

## Context

The real OSM/PostGIS network and local explicit-height building context already
work. They do not provide aerial imagery or complete Dubai skyline geometry.
The owner authorized their ion token for this application and requested actual
browser verification without importing/replacing geographic data.

## Decision

Use `NEXT_PUBLIC_CESIUM_ION_TOKEN` as the canonical deliberately public setting.
Retain `CESIUM_ION_PUBLIC_TOKEN` as a compatible alias; reject differing nonempty
values with a value-free configuration error. Compose injects root `.env` into
the runtime container. The no-store, force-dynamic server configuration endpoint
reads through runtime indirection and exposes only the existing five-field
allowlist. No token enters image build arguments or static client bundles.
Private account/upload/admin tokens are inappropriate for this public boundary.

Keep React-owned mode, selection and camera commands separate from native Cesium
ownership. One mount-owned Viewer survives Engineering/Realistic changes.
Providers are destroyed/replaced with generation guards, listener/credit cleanup
and an atomic loading-state reset; no ready state is carried across providers.
Road batches receive mode-specific presentation without changing their geographic
coordinates or identifiers. Initial Engineering has no hosted tile dependency.
Synthetic scopes never adopt real building or terrain content.

Use the installed CesiumJS 1.146.0 public `IonImageryProvider.fromAssetId` for
World Imagery AERIAL asset 2 and configured alternatives. This is the provider
underlying `createWorldImageryAsync`; pass the token explicitly because the SDK
endpoint cache keys options.accessToken rather than the global default token.
This avoids stale endpoint credentials after a runtime configuration change. The historical default asset 3812 returned actual HTTP404 with this
account; asset 2 returned HTTP200 and rendered actual aerial tiles. Do not silently
cycle through other assets on failure. `createOsmBuildingsAsync` loads asset96188;
readiness additionally requires visible nonempty building content and a rendered
frame. Missing and failed providers remain actionable beside the map.

Retain the aligned WGS84 ellipsoid by default. Optional authorized terrain stays
explicit. Realistic lighting uses a stated Dubai daytime presentation reference,
not live weather/time. Buildings cast restrained shadows onto the globe but do
not receive shadow maps themselves, avoiding visible facade depth-bias patterns.

Preserve automatic provider credit HTML and promote actual imagery tile credits
inline using the public per-provider `getTileCredits` method and bounded Credit
reuse. Restore the instance method on removal. OSM road attribution is a static
credit tied to selected real OSM scope, independent of the local context layer.
Do not infer commercial content rights from working requests.

Disable browser traces for these suites because traces persist public tokens and
signed provider URLs. Record only sanitized origins/paths, MIME types, statuses,
plain camera/selection identity and actual screenshots. Keep failed runs visible.

## Consequences and limits

Credentials are intentionally observable to the browser; use assets:read with
required assets and allowed origins. Runtime configuration avoids rebuilding an
image for token rotation, but Compose must recreate web to reinject environment.
Account entitlements, provider availability and OSM coverage remain external.
The current account-plan credit is retained. Actual verification is recorded in
[verification-cesium-ion.md](../verification-cesium-ion.md).

This decision does not change schema, source provenance, imports, simulations,
viewport feature budgets or spatial LOD. Those broader M03.5 performance requests
were superseded by the owner's narrower Cesium integration task. Existing bounded
rendering safeguards remain; no unlimited feature rendering is introduced.
