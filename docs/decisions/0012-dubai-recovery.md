# ADR 0012 — Real OSM geography with separate conversion and synthetic demand

Status: accepted for the explicitly requested project recovery, 2026-10-27.
Actual execution status is maintained in [verification](../verification.md).

## Context

M03 correctly preserved synthetic data labels and token-free rendering, but its
small invented network and low-resolution global texture did not provide the
owner's expected real Dubai geographic experience. The recovery request explicitly
authorizes a bounded real OSM download/import, SUMO conversion, improved map-first
interface and a basic synthetic-demand experiment. It does not authorize deleting
existing fixtures or claiming unavailable licensed provider access.

## Decision

1. Retain the application, PostGIS/ORM/Alembic, bounded typed spatial APIs, worker
   separation and Cesium lifecycle. Import into a new immutable network version.
   Keep synthetic fixtures accessible through an explicit development/test mode.
2. Acquire one bounded Downtown Dubai/Business Bay OSM snapshot at
   `[55.258,25.180,55.288,25.208]` in EPSG:4326 longitude/latitude. Retain original
   bytes, acquisition/base timestamps, complete query, source/license/attribution
   and checksum. Cache/reuse the snapshot; public Overpass is not a runtime map
   backend and is not called on camera movement or startup.
3. Run pinned native ARM64 `netconvert` in the worker environment. Include its
   matching typemaps/XSDs via exact-version `sumo-tools`; a binary alone is not a
   verified import capability. Preserve full conversion logs, commands and hashes.
4. Map original OSM identifiers to actual generated SUMO directed edges and new
   database records. Represent one-to-many conversion explicitly. Preserve the
   source snapshot beyond the database rectangle and record the bounded import
   policy rather than implying all original ways were clipped.
5. Build self-hosted OSM cartography from retained source geometry. It supplies
   recognizable geographic context without prohibited tile scraping or a paid
   imagery dependency. Interactive versioned roads remain served from PostGIS.
   Describe this as cartography, not satellite imagery or provider 3D Tiles.
6. Extrude only explicit valid metric height tags. Leave unknown heights flat;
   never infer height from storey counts or known landmark names. Missing-node
   ways, invalid coordinates and invalid geometries are rejected rather than
   repaired into invented geography. Publish bounded artifacts with checksums.
7. Keep licensed ion providers optional and precise about missing access. Display
   automatic/provider/OSM/Natural Earth credits and source-backed metadata only.
8. Add a bounded worker CLI for three reproducible synthetic vehicles on a valid
   route in the checksum-matched imported network. Verify the mapping checksum and
   restrict every route edge to the actual imported PostGIS subset. Require actual motion,
   completion, output metrics and geographic conversion; reject teleport/collision
   success substitutes. Do not add fake playback, live-traffic labels or calibrated
   traffic/forecast claims.

## Consequences and limits

The local app gains real road positions and source-backed city geometry without
another database, arbitrary server proxy, embedded private token or competing
geographic source of truth. Source/data artifacts are intentionally ignored by Git;
a fresh environment needs the documented retained-artifact or bounded-download
workflow. Named volumes and old fixture/version records remain preserved.

Converted lanes, speeds, junction connections and priorities may involve SUMO
inference and must be flagged. OSM signal/restriction tags are not field verified;
missing tags do not prove absence. Topological validity is not routing accuracy.
The context build omits unassembled multipolygon relations and missing-height
extrusions. In this source, even the Burj Khalifa footprint has no explicit height;
it remains flat. Licensed provider access/coverage is a separate capability.

The smoke experiment verifies a bounded route and outputs only synthetic demand
results. Its recorded trajectories are retained, while browser replay remains
separate work unless actually implemented and tested. Real geometry is not live
traffic. Code licenses do not replace ODbL obligations for derived geographic data.

Large source/conversion/trajectory artifacts remain outside Git. Small manifests,
exact command outputs, source checksums, actual screenshots, native conversion/run
results and failures belong in the recovery verification evidence. Isolated unit
success or a context-build count cannot substitute for real import/browser/SUMO
acceptance. See [recovery workflow](../recovery-geography.md).
