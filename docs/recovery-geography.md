# Dubai geography recovery

This recovery replaces the main synthetic geographic demonstration with a bounded
OpenStreetMap workflow. The existing application, PostGIS store, source-provenance
models, immutable network versions, Cesium lifecycle and M01 worker remain in use.
Synthetic fixtures are preserved for explicit development/test mode. The owner's
recovery request explicitly authorizes real OSM import and a basic synthetic-demand
SUMO experiment; the old milestone scope is not used to postpone those features.

## Diagnosis and rendering approach

The previous close-range view combined an illustrative six-node/eight-road graph
with low-resolution Natural Earth imagery and ellipsoid terrain. That packaged
texture provides global geographic reference, not detailed Dubai street imagery.
The missing ion token also prevented licensed Cesium building tiles from loading.
Large interface headings and cards reduced the useful map area. Those conditions
explain why a correctly positioned globe still appeared to be a geographic demo.

The recovery adds self-hosted cartography derived from actual OSM geometry: road
context, building footprints, water, parks, bounded labels and selected buildings
with explicit metric height tags. Cesium renders that content on the real WGS84
ellipsoid. It is functional geographic geometry, not a screenshot/background,
photorealistic satellite raster or a claim that Cesium ion tiles are available.
The selectable, versioned road network comes from PostGIS rather than the context
GeoJSON. The control layout is being changed to keep the map as the main workspace.
Final browser acceptance and screenshots are recorded in [verification](verification.md).

## Exact source and extent

The selected engineering study extent covers Downtown Dubai and Business Bay:

```text
EPSG:4326; coordinate order longitude, latitude
west  = 55.258
south = 25.180
east  = 55.288
north = 25.208
```

This is a deliberately chosen study rectangle, not an official administrative
boundary. Overpass bbox syntax reverses the tuple to south,west,north,east.

The actual retained download used
`https://overpass-api.de/api/interpreter`, HTTP GET with an explicit Overpass QL
query. The complete query is retained in `source-manifest.json`; it selects
specified drivable highway classes, restriction relations, buildings, water,
land use/parks and named tourism nodes, with referenced members/nodes. It declares
a 60-second server timeout and a 32 MiB maximum-size budget. The client performs
one bounded request with a 90-second timeout; it has no automatic retry loop,
parallel extraction or tile harvesting. Once downloaded, the checksum-verified
extract is reused. Refresh into a new directory rather than overwriting a snapshot.
Public Overpass is not an application runtime backend. See its
[resource-sharing policy](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html).

Actual source snapshot:

| Field | Retained value |
| --- | --- |
| Download time UTC | 2026-10-26T23:12:15.216624+00:00 |
| OSM base timestamp in original manifest | 2026-10-26T23:11:02Z |
| Original extract bytes | 8,606,335 |
| SHA-256 | `9aab25c641c00ba9e19110015173d6ac8bb2f18ba29975ed4545d85e8fe5eb3e` |
| Original nodes / ways | 36,311 / 4,808 |
| Original relations / restriction relations | 189 / 158 |
| Source license | ODbL-1.0; © OpenStreetMap contributors |

The source is retained at
`/Users/redmug/EARTHMIND/data/dubai-osm/recovery-v1/source.osm.xml`, with
`source-manifest.json` beside it. It is ignored by Git, retained locally and not
replaced by a hand-written fixture. Original complete ways can extend outside the
query rectangle. Database import admits converted edges fully inside the declared
rectangle; the broader original/conversion extent remains explicitly recorded.
The smoke report records actual trajectory bounds. Route edges are restricted to
the checksum-verified imported database subset; the conversion itself still retains
complete source-way geometry beyond the database rectangle.

## Reproduce download, conversion and import

Run from `/Users/redmug/EARTHMIND` after `make setup`, with the native worker image
and database available. This sequence creates a **fresh** default artifact set:

```sh
uv run --locked python scripts/import_dubai_osm.py download
uv run --locked python scripts/import_dubai_osm.py convert
uv run --locked python scripts/import_dubai_osm.py import
uv run --locked python scripts/build_osm_context.py \
  --source data/dubai-osm/recovery-v1/source.osm.xml \
  --output data/dubai-osm/recovery-v1/context
make dev
```

The delivered artifact directory already contains the converted network. On that
existing directory, `convert` verifies source and network checksums before
reusing the retained result; changed or incomplete artifacts are refused. For a refreshed
source, pass a new `--directory` to the download/convert/import commands and update
the context output/mount consistently. Do not retry downloads in a loop.

The retained source download, native conversion, database import and context build
have executed. The repeated database import returned `created=false`, preserving
the same version and counts. Exact final commands, exits, browser/native smoke
results and remaining failures belong to [verification](verification.md). The
first conversion attempt exposed missing SUMO support data in the minimal worker
image. The worker Dockerfile now installs `sumo-tools` pinned to the same native
1.15.0 Debian package version as SUMO and asserts that the OSM typemap/network XSD
exist. The subsequent native conversion succeeded; its actual checksum is below.

| Imported artifact | Actual result |
| --- | --- |
| SUMO network SHA-256 | `86a950ddf4b835f74a5235973669c2d374803bade3d7053669ec2ddd9d87a7ab` |
| Database network UUID | `4aa62897-1a54-546c-a390-ddb156838f8e` |
| Version label | `osm-20261026-0b027352ec38` |
| Imported directed roads / intersections | 2,364 / 1,560 |
| Source road ways / ways with imported records | 2,377 / 1,273 |
| Omitted converted edges | 211 outside extent; 17 unsupported; no unmapped source edges or self-loops |
| Actual validation | VALID_WITH_WARNINGS: eight weak components, zero isolated nodes, no integrity errors |
| Lane inference count | 923 records flagged as inferred by netconvert; other interpreted tags are not field verification |
| Mapping SHA-256 | `80bec1ad585f788a3137835f594207b4e2592f9958b9ff3345cd21d4d00c51b1` |

This is not a claim that the bounded network is fully connected. The clipped
study extent and incomplete source topology can leave separate components. The
native smoke selects an actual valid route from the imported database subset;
it does not repair components by inventing roads.

The converter runs installed native `netconvert` in the worker image. It retains
street names and original identifiers, removes non-junction geometry nodes while
preserving road shapes, keeps passenger edges, uses UTM zone 40/WGS84 and disables
traffic-light, ramp and joined-junction guessing. SUMO can still infer lane counts,
speeds, priorities and lane-to-lane connections. Those derived values are marked
as such; they are not verified Dubai lane data. Relevant behavior is documented in
the [official SUMO OSM importer documentation](https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html).

Conversion produces `network.net.xml`, `netconvert.log` and
`conversion-manifest.json`. Import retains a separate many-to-many mapping between
OSM source ways, imported database road records and generated directed SUMO edges.
One OSM way may split into several SUMO edges and direction variants. Do not join
these sources by assuming identical IDs or one-way-to-one-edge cardinality.
`import-manifest.json` records the immutable database version and checksum chain.
Repeated operations verify existing artifacts; a new snapshot/version is required
for changed source. No synthetic fixture or published network is deleted.

## Cartographic artifact integrity

The context builder reads the actual retained XML; it never requests map tiles.
It enforces input, feature, coordinate-position and output byte budgets. It
rejects unsafe XML declarations, nonfinite/out-of-range coordinates, conflicting
node coordinates and invalid geometry. If any referenced node is absent, the
whole way is omitted and counted; remaining points are never connected across
a missing reference. Valid geometry is clipped to the study rectangle. Output
budgets are checked before replacing assets, and complete artifacts are published
with the checksum manifest last.

The actual context build from this source produced:

| Artifact | Features | Positions | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `context.geojson` | 4,676 | 39,090 | 2,053,685 | `30237bfcdca15d4427644d966eb564947392c6370bcd59715fc41069d0d4103d` |
| `buildings.geojson` | 402 | 4,895 | 249,109 | `fc5c22bc575a5151b09093b57dcd0a21cd3e5681b8b0d8036259b87bd33e2724` |

There are 120 bounded labels. This snapshot had zero incomplete-way and zero
invalid-geometry rejections. Counts include source cartography; they are **not**
the imported PostGIS road/intersection counts. The context directory is mounted
read-only at the web container's `public/geography`. Generated context, raw source,
converted networks and simulation output remain under ignored `data/`, outside
Git and Docker build contexts. A new checkout must run the documented import/build
workflow or restore checksum-verified retained artifacts; source code alone does
not magically contain the downloaded city dataset.

## Buildings, names and geographic accuracy

Only an explicit numeric metric OSM `height` tag within 1–1,000 meters becomes an
extruded height. `building:levels`, missing heights, feet, compound values and
invalid values are not converted into invented meter heights. Unknown-height
footprints remain flat. These models are partial source-backed extrusions, not
surveyed facade/roof models or licensed Cesium 3D Tiles. Height tags, source names,
lane tags, traffic lights and turn restrictions are community observations rather
than field verification by EARTHMIND.

The actual source contains the Burj Khalifa footprint as OSM way `446646206`,
with `building:levels=163` but no explicit `height` tag. It therefore remains flat
in the current tagged-height layer. No famous-building height is silently filled
from memory. The tallest explicit height in this snapshot is 330 meters for
JW Marriott Marquis Hotel Tower 2. Simple closed-way polygons are supported;
unassembled multipolygon relations remain omitted. This limits coverage of
complex water/building geometry and must not be presented as uniform city coverage.

The optional Cesium ion path remains available through an intentionally public,
scoped token. Missing access must remain a precise unavailable-provider state;
local OSM geometry does not count as proof that ion requests/entitlements succeed.
Provider automatic attribution remains visible whenever those services are used.

## Basic real-network synthetic-demand experiment

After a successful import and worker rebuild, run a new output directory:

```sh
docker compose run --rm --no-deps \
  --user "$(id -u):$(id -g)" \
  --volume "$PWD/data/dubai-osm/recovery-v1:/data" \
  worker python -m earthmind_worker.real_network_smoke \
  --network /data/network.net.xml \
  --import-manifest /data/import-manifest.json \
  --output-dir /data/smoke-001
```

This is a repeatable operator command, not a browser/API execution of native tools.
Use a new `smoke-002` directory for another run. The command refuses to overwrite
prior results. The current-user mapping allows the non-root native process to
write the bound artifact directory while preserving normal worker defaults.

The worker verifies the network checksum, source checksum/extent and database UUID
from the actual import manifest, verifies `source-sumo-db-mapping.json` against
its retained checksum, checks mapped database UUID identities, and restricts the
route to actual imported PostGIS edge IDs. Converted edges outside the database
extent cannot enter the smoke route. It selects deterministic connected passenger
turns using SUMO connection/permission records and generates three explicitly synthetic
vehicles with seed 42 and five-second departure spacing. It limits execution to
600 simulation steps and 120 seconds wall time. It requires all three vehicles to
depart, move and complete; teleports or collisions invalidate the check. Geographic
conversion is tested with actual TraCI XY→longitude/latitude→XY round trips within
0.05 meters. This exercises one bounded route, not every road or turn restriction.

Actual output files are `synthetic-smoke.rou.xml`, `sumo.log`, `tripinfo.xml`,
`fcd.geo.xml`, `summary.xml`, `recorded-positions.json` and `smoke-result.json`.
Trip distances/durations, moving/departed/completed counts and trajectory bounds
are derived from actual SUMO/TraCI output. Isolated harness units do not establish
that the real run passed; consult the final native-run evidence. Recorded positions
are retained for later playback, but no fake animated vehicles or browser replay
layer is substituted for a recorded-output implementation.

The actual conversion warnings also matter: the retained log records eight ignored
restriction relations, junction-shape and connection-speed adjustments, sharp-turn
and disconnected-lane warnings. A successful conversion and bounded smoke do not
turn those findings into verified lane-level accuracy. Consult the original log
and import validation rather than hiding them behind a single success badge.

## Provenance and licensing in the interface

The interface must distinguish real OSM geographic geometry, provider-dependent
buildings, synthetic test fixtures, synthetic simulation demand, unverified/inferred
signals and disconnected live traffic. Real road positions are not proof of
lane-level driving accuracy, lawful routing, calibrated demand or current traffic.
Only the selected real dataset loses the blanket synthetic-geometry warning;
synthetic fixtures retain it. Context and authoritative selectable overlays have
separate visibility/data identities rather than being silently merged.

Keep visible `© OpenStreetMap contributors` credit linked to the
[OSM copyright/license page](https://www.openstreetmap.org/copyright). Original and
derived OSM data retain ODbL terms; the application's proprietary source-code
license does not relicense that geographic database. Distribution/public use must
retain required notices and applicable database sharing obligations. The official
[OSMF attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines)
cover interactive maps, databases, static screenshots and simulations. Natural
Earth and Cesium notices remain separately attributed. No public OSM raster tile
service is used by this local context path.

## Display performance boundary

The local context is rendered on an ellipsoid without terrain clamping. Flat
polygons/lines use small display-only offsets (0.2/0.35m) to avoid z-fighting;
these are rendering offsets, not measured elevations. Explicit building heights
remain source values. Switching to a synthetic fixture disables real context
providers and preserves its clear development warning. Browser timings and the
actual software-renderer scope are recorded separately in verification.md.

Ordinary hosted CI uses the local Natural Earth reference and preserved fixture
checks; it does not silently query public Overpass on every push. Explicitly
select the real_geography workflow input to import/validate real data and run
recovery browser checks. Skipped real-data checks in ordinary CI are NOT RUN,
not a real-geography PASS. Hosted execution remains NOT RUN until observed.
