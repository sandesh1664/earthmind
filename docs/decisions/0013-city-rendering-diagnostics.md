# ADR 0013 — Honest provider state and observable geographic rendering

Status: accepted, 2026-10-27. Bounded correction to the existing M03/recovery viewer.

The local imagery mode uses packaged Natural Earth II under source-backed OSM
cartography. Its finest raster level is 0.17578125 degrees per pixel; at the Dubai
camera this is an almost uniform reference surface, not satellite imagery. A
missing public ion token cannot be repaired by camera styling or manufactured
geography. Existing source-height extrusions remain a separate, partial source.

Keep the present viewer, camera controls, licensed assets and PostGIS ownership.
Use one pure effective-mode policy for renderer initialization and source labels,
including the synthetic dataset's explicit Natural Earth override. Explicit ion
mode without a token retains a useful reference fallback, but reports blocked
and names its actual resolution/source. Optional provider failure never becomes
an unrelated backend/viewer failure and is not replaced by later ready state.

Provider adoption is not rendering evidence. Imagery/terrain readiness waits for
a completed frame, a visible globe and loaded visible globe tiles. The pinned SDK latches DataSourceDisplay.ready, so local models/context instead
wait for the mount’s public native geometry batches (PrimitiveCollection get/length
and Primitive/GroundPrimitive/GroundPolylinePrimitive.ready), followed by another
completed frame. This is scene preparation evidence, not per-building pixel coverage.
No SDK private source/visualizer field is used. Ion buildings additionally
require visible nonempty tile content. These observations do not certify full
Dubai coverage, metadata accuracy, satellite content, or provider entitlement.
Tile errors remain latched until a new load/toggle. All added event listeners
belong to the mount/provider generation and are removed on replacement/disposal.

Layer controls show provider-reported blocked reasons even when a public token
exists (local OSM heights still require ellipsoid terrain). Selected blocked
layers remain switchable off; errors remain visible. Do not redesign the scene
or replace legitimate missing-data states with decorative content.

Expose optional plain-value diagnostics for the actual camera orientation and
ground focus, globe/tile state, imagery layer count and boundary fill alpha.
Never expose native Cesium objects or credential values. Preserve the existing
350 ms measured settlement and destination presets. Later repeated mobile evidence
found the mesh-first pick returning a focus about 42 km away while camera pose
was unchanged. Flat EllipsoidTerrainProvider modes now use the analytic
Camera.pickEllipsoid intersection for both snapshots and orbit commands. Real
configured terrain retains its terrain-aware pick; live ion terrain is unverified.
The internal SDK trigger for the distant mesh hit is not established.

Browser verification records successful JPG textures, actual workers, console,
HTTP and transport failures. Expected cancellation of superseded bounded spatial and network-catalog reads
is classified and retained. Controlled configuration/failure tests are labeled
separately from actual deployed provider coverage. Evidence output can be routed
with EARTHMIND_EVIDENCE_DIR so new checks preserve historical milestone reports.

No schema change, new OSM import, external raster scraping, dependency upgrade,
scenario implementation or later milestone is part of this decision. See
[the diagnosis](../city-explorer-diagnosis.md) for commands, browser evidence and
remaining token/coverage blockers.

The actual mobile regression also exposed an unchanged-selection cancellation
race. Region/network selection must be idempotent: do not cancel an active
spatial query or clear its camera state unless its scope identifier changes.
Otherwise a cancelled query with the same key can remain idle and leave only the
boundary rendered. The regression holds/releases an existing stored fixture response and re-emits
the active selections within its real request deadline. Original trace evidence
shows cancellation within milliseconds of re-selection, without fabricated data.
