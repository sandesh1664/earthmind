# M02 spatial API

The FastAPI base URL is `http://127.0.0.1:8000/api/v1` with the default local
Compose ports. Interactive OpenAPI documentation is at
`http://127.0.0.1:8000/docs`; the schema is at `/openapi.json`. M02 extends the
existing API. M01 health, readiness, capabilities, and bounded diagnostic
contracts remain compatible.

Compose publishes API, web, and PostgreSQL ports only on loopback. These APIs
assume a trusted local developer. Public reads have no user authentication.
`POST /regions` requires the private development write token; this gate is not a
user login or authorization system for shared deployment. Identity, TLS, managed
secrets, database role separation, and an exposure review are required before
binding the services externally.

## Endpoints

All paths in this table are relative to `/api/v1`. Identifiers are UUIDs. List
and spatial collection endpoints accept `limit` and `offset` unless indicated.

| Method | Path | Inputs | Successful response |
| --- | --- | --- | --- |
| GET | `/regions` | Pagination | Region page |
| GET | `/regions/{region_id}` | Region UUID | Region metadata, derived area/centroid, bounds |
| POST | `/regions` | Authorized `RegionCreate` JSON | `201` region and `Location` header |
| GET | `/regions/{region_id}/geojson` | Region UUID | GeoJSON MultiPolygon Feature |
| GET | `/networks` | Optional `region_id`; pagination | Network page |
| GET | `/networks/{network_id}` | Network UUID | Version summary with actual feature counts and bounds |
| GET | `/networks/{network_id}/edges` | Optional `bbox`; pagination | LineString FeatureCollection |
| GET | `/networks/{network_id}/intersections` | Optional `bbox` or `polygon`; pagination | Point FeatureCollection |
| GET | `/networks/{network_id}/validation` | Optional `tolerance_m` in `0..100` | Fresh, read-only structural validation report |
| POST | `/geo/validate` | Geometry JSON wrapper | Valid geometry type, SRID, coordinate order, optional area |
| POST | `/geo/contains` | `region_id` and Point geometry | Containment result including boundary policy |
| GET | `/geo/nearby-edges` | `longitude`, `latitude`; optional `radius_m`, `network_id`; pagination | Distance-ordered LineString FeatureCollection |
| GET | `/data-sources` | Pagination | Public provenance page |
| GET | `/data-sources/{source_id}` | Source UUID | Public provenance record |

Region, network, and source lists use `{ "items": [], "total": 0, "limit": 25,
"offset": 0 }`. Spatial lists use `{ "type": "FeatureCollection", "features":
[], "total": 0, "limit": 25, "offset": 0 }`. `total` counts all matching
records before pagination; it is not the length of the returned page. Empty
matches return `200` with an empty list. An empty network has `bounds: null`.
Bounds use `[west, south, east, north]`. Network counts and bounds are queried
from stored features rather than copied from claimed summary values.

## Geometry and measurement contract

Inputs are GeoJSON geometry objects, not complete FeatureCollections. Supported
types are Point, LineString, Polygon, and MultiPolygon. Region creation accepts
only Polygon or MultiPolygon and stores a MultiPolygon. Contains accepts only a
Point. Geometry objects and request models reject undeclared fields.

Coordinates are two finite numbers in `[longitude, latitude]` order, in EPSG:4326.
Longitude must be within `[-180, 180]` and latitude within `[-90, 90]`. An optional
`coordinate_order` field defaults to the sole allowed value
`"longitude_latitude"`; any other value is rejected. The API never flips
ambiguous coordinate pairs. Alternate CRS declarations, Z/M coordinates,
GeometryCollections, empty geometry, invalid polygon topology, unclosed rings,
and excess coordinate counts are rejected before a spatial database operation.
Callers must transform other coordinate systems before sending data.

Stored region area uses `ST_Area(boundary::geography) / 1000000`, and edge length
uses `ST_Length(geom::geography)`. Nearby filtering and distance use PostGIS
geography in meters. Geometry validation computes polygon area independently
with the WGS84 ellipsoid through pyproj. Metric distances are not calculated
from raw longitude/latitude degrees.

Region centroid and area are database-derived, never client overrides. The
centroid policy uses the geographic centroid when covered by the boundary;
otherwise it uses `ST_PointOnSurface` as a covered representative point. The
returned `centroid` can therefore be a representative point for concave regions.
Contains and polygon intersection queries use `ST_Covers`, so boundary points
count as contained. Bbox filtering uses geometry `&&` plus `ST_Intersects`.
Nearby filtering uses the functional GiST index on the plain `geom::geography`
expression, without a typmod that would prevent index matching.

`bbox` is the comma-separated string `west,south,east,north`. West must be less
than east and south less than north; antimeridian-wrapping boxes are rejected.
For intersections, `polygon` is a URL-encoded Polygon/MultiPolygon geometry JSON
string, at most 60,000 characters. Choose `bbox` or `polygon`, not both. Polygon
filters obey the same coordinate and spatial-span limits as bbox filters.

## Limits

Settings are read from the API environment. Compose passes through the values
listed in `.env.example`. Default pagination is 25, with offset 0.

| Setting or input | Default | Enforced bound |
| --- | --- | --- |
| `GEO_MAX_REQUEST_BYTES` | 262144 bytes | POST regions and spatial-tool bodies, including streamed chunks; configurable 1024..1048576 |
| `GEO_MAX_COORDINATES` | 5000 positions | Per input geometry; configurable 4..5000 |
| `GEO_MAX_BBOX_DEGREES` | 1.0 degree | Maximum longitude span and latitude span independently, for bbox and polygon filters; configurable greater than 0 through 5 |
| `GEO_MAX_PAGE_SIZE` | 100 | `limit` is 1 through the configured maximum, never above 100 |
| `offset` | 0 | Integer 0..100000 |
| `GEO_MAX_RADIUS_M` | 5000 meters | Positive radius through the configured maximum, never above 5000; request default 250 |
| `GEO_MAX_VALIDATION_FEATURES` | 10000 | Total nodes plus edges permitted for structural graph validation; configurable 10..100000 |
| `GEO_MAX_VALIDATION_COORDINATES` | 100000 | Total stored point positions across nodes and edges permitted for graph validation; configurable 10..100000 |
| `GEO_BOUNDARY_TOLERANCE_M` | 5 meters | Region-coverage tolerance 0..100, overridable for a validation request with `tolerance_m` |

Spatial filtering occurs in PostGIS before feature serialization; results are
paginated. Structural graph validation is the deliberate bounded exception that
loads network topology into Python. PostGIS aggregates feature and coordinate
counts before loading geometry; either exceeded budget skips graph processing.
Validation holds a shared parent-version lock, coordinated with child-write
triggers, so a concurrent draft edit cannot invalidate the count/fetch budget.
No full-network geometry download is needed
for a bbox, polygon, or proximity query. Count and extent aggregates still
perform database work proportional to matching data; the tiny fixture does not
establish production throughput. Database geometry constraints provide an
additional hard complexity ceiling; trusted ingestion must also honor public
response geometry limits.

## Reads and spatial examples

The seeded region and network UUIDs are deterministic. These examples require a
running, migrated, seeded stack (`make dev`, or `make migrate` and `make seed`).

```sh
curl --fail 'http://127.0.0.1:8000/api/v1/regions?limit=25&offset=0'
curl --fail 'http://127.0.0.1:8000/api/v1/networks?region_id=8d31afa3-5d52-59b5-a8bc-691b5867dfcb'
curl --fail 'http://127.0.0.1:8000/api/v1/networks/22f68ce8-9247-5425-8342-827d86517ead/edges?bbox=55.2685,25.19,55.2805,25.20&limit=10'
curl --fail 'http://127.0.0.1:8000/api/v1/geo/nearby-edges?longitude=55.274&latitude=25.195&radius_m=1000&limit=10'
curl --fail --json '{"geometry":{"type":"Point","coordinates":[55.274,25.195]},"coordinate_order":"longitude_latitude"}' \
  http://127.0.0.1:8000/api/v1/geo/validate
curl --fail --json '{"region_id":"8d31afa3-5d52-59b5-a8bc-691b5867dfcb","point":{"type":"Point","coordinates":[55.274,25.195]},"coordinate_order":"longitude_latitude"}' \
  http://127.0.0.1:8000/api/v1/geo/contains
curl --fail --get --data-urlencode 'polygon={"type":"Polygon","coordinates":[[[55.2685,25.19],[55.2805,25.19],[55.2805,25.20],[55.2685,25.20],[55.2685,25.19]]]}' \
  http://127.0.0.1:8000/api/v1/networks/22f68ce8-9247-5425-8342-827d86517ead/intersections
```

The following complete response was read from the running local API on
2026-10-26 using `curl --fail --silent --show-error
http://127.0.0.1:8000/api/v1/regions/8d31afa3-5d52-59b5-a8bc-691b5867dfcb/geojson`.
Whitespace is reformatted; the values are the actual response.

```json
{
  "type": "Feature",
  "id": "8d31afa3-5d52-59b5-a8bc-691b5867dfcb",
  "geometry": {
    "type": "MultiPolygon",
    "coordinates": [[[[55.2685, 25.19], [55.2805, 25.19], [55.2805, 25.2], [55.2685, 25.2], [55.2685, 25.19]]]]
  },
  "properties": {
    "id": "8d31afa3-5d52-59b5-a8bc-691b5867dfcb",
    "slug": "dubai-downtown-demo",
    "name": "Downtown Dubai — Synthetic Study Region",
    "country_code": "AE",
    "area_km2": 1.3398134937911033,
    "is_synthetic": true,
    "boundary_policy": "Illustrative study boundary, not an official municipal boundary"
  }
}
```

The actual first road feature from the same API with `edges?limit=1` was:

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "id": "892cdfec-5d1c-5880-aa32-66ff680f1756",
    "geometry": {"type": "LineString", "coordinates": [[55.27, 25.192], [55.274, 25.192]]},
    "properties": {
      "network_version_id": "22f68ce8-9247-5425-8342-827d86517ead",
      "sumo_edge_id": "provisional:e0",
      "source_edge_id": "synthetic:e0",
      "name": "Synthetic link e0",
      "road_class": "synthetic_local",
      "lane_count": 1,
      "speed_limit_mps": 8.0,
      "length_m": 403.17058988624365,
      "is_one_way": true,
      "is_synthetic": true,
      "start_intersection_id": "3fe9be5d-83e9-5027-948b-3253768f4b56",
      "end_intersection_id": "f29da6d5-bd1c-591f-a0d0-c2f89623a768"
    }
  }],
  "total": 8,
  "limit": 1,
  "offset": 0
}
```

GeoJSON contains numeric coordinates and allowlisted properties; it does not
expose WKB/EWKB or raw PostGIS objects. A provisional `sumo_edge_id` reserves a
future compatibility field and does not assert that SUMO conversion occurred.

## Region creation and development authorization

`make setup` creates a private random token in ignored `.env` if missing. The API
accepts it only in `X-Earthmind-Dev-Token`; configured tokens must contain at
least 32 characters. A blank/unset token disables writes (`503`), and a missing
or incorrect token when writes are enabled returns `403`.

An authorized caller can POST this body to `/regions`:

```json
{
  "slug": "synthetic-example",
  "name": "Synthetic example region",
  "country_code": "AE",
  "emirate": "Dubai",
  "timezone": "Asia/Dubai",
  "coordinate_order": "longitude_latitude",
  "boundary": {
    "type": "Polygon",
    "coordinates": [[[55.27, 25.19], [55.28, 25.19], [55.28, 25.20], [55.27, 25.20], [55.27, 25.19]]]
  },
  "metadata": {"is_synthetic": true, "description": "Local example"}
}
```

Save the body as `region.json`; use a private curl config containing the header,
with mode 0600, rather than putting a real token in source, a URL, shell history,
or a shared command transcript:

```sh
curl --fail --config /absolute/private/path/earthmind.curl \
  --json @region.json http://127.0.0.1:8000/api/v1/regions
```

The private config line has the form
`header = "X-Earthmind-Dev-Token: <private token>"`; the placeholder is not a
working credential. Slugs are lowercase hyphen-separated identifiers, length
3..80. Names are 1..160 characters, country codes are two uppercase letters,
and timezone is a valid IANA name. `emirate` is optional; timezone defaults to
`Asia/Dubai`. Metadata is a JSON object with at most 32 keys, subject to the body
limit. Client `centroid`, `area_km2`, arbitrary request fields, and nonpolygonal
boundaries are rejected. Creation and its audit event commit or roll back
together; duplicate slugs or stored spatial constraints return a safe `409`.

The Next.js dashboard uses a same-origin GET-only geospatial proxy with route
and query allowlists, typed response validation, an eight-second backend
deadline, and `no-store`. The proxy does not forward a development token and
has no POST handler. It exposes region/network/provenance reads, including
bbox-filtered feature pages; direct spatial tools and polygon filters remain
FastAPI interfaces. Its current bbox cap is one degree even if the backend
administrator increases the configurable cap.

## Network validation semantics

`GET /networks/{id}/validation` derives a fresh report from stored topology; it
does not mark or publish a network. A network summary's `is_validated` and
`validation_summary` are persisted publication metadata, whereas this endpoint
is the current structural observation at the requested tolerance.

NetworkX uses explicit start/end intersection relationships. Geometric line
crossings create no connection. Checks cover nonempty geometry, types/SRIDs,
coordinate bounds, identifiers, endpoint/reference consistency, metadata,
lane/speed/length values, components/isolates, duplicate edges, actual counts,
and edges outside the geography-buffered region tolerance. Endpoint-to-node
positions must agree within 0.5 meters. Connectivity is undirected structural
connectivity; it is not a traffic reachability or routing guarantee.

| Status | `validated` | Meaning |
| --- | --- | --- |
| `VALID` | `true` | All implemented checks pass without findings |
| `VALID_WITH_WARNINGS` | `true` | Integrity checks pass; disconnected components, isolates, or missing descriptive metadata produced warnings |
| `INVALID` | `false` | Integrity errors, such as inconsistent endpoints, invalid attributes, or out-of-region edges |
| `NOT_VALIDATED` | `false` | Node-plus-edge or aggregate coordinate count exceeds its configured graph-validation budget |

For `NOT_VALIDATED`, actual `nodes` and `edges` counts remain integers,
`components` and `isolated_nodes` are `null` because they were not computed,
and `checks` is empty. The response never substitutes zero for an uncomputed
observation.

The live synthetic fixture report read on 2026-10-26 returned `status: "VALID"`,
`validated: true`, every check `true`, no warnings/errors, and counts
`{"nodes":6,"edges":8,"components":1,"isolated_nodes":0}` at a five-meter
boundary tolerance. This establishes synthetic persistence and topology
behavior only; it is not evidence of official boundaries, road accuracy, signal
locations, or simulation performance.

## Errors and public fields

| HTTP status | Meaning |
| --- | --- |
| `200` | Read or spatial tool completed, including empty matches |
| `201` | Authorized region creation |
| `403` | Missing or incorrect development write token |
| `404` | Referenced resource does not exist |
| `409` | Creation conflicts with an identifier or persistence constraint |
| `413` | Geospatial POST body exceeds the configured byte limit |
| `422` | Invalid schema, geometry, coordinate, pagination, or query bounds |
| `500` | Unexpected internal error with a generic public message |
| `503` | Dependency unavailable, or development writes disabled |

Errors use an `error` object with stable `code` and `message`. Schema errors
include up to 20 field locations/type codes and do not echo submitted values.
Controlled spatial errors may add a bounded geometry/bounds explanation. Raw
SQL, driver errors, database credentials, and exception details are not returned.
For example, an invalid coordinate schema returns `422`, and a conflicting slug
returns `{"error":{"code":"conflict","message":"Resource conflicts with
existing data"}}`.

Region metadata is public only for the allowlisted keys `is_synthetic`,
`boundary_policy`, `description`, `source`, and `fixture_version`. Road/node
properties are explicitly selected. Data-source metadata and network artifact
URIs are omitted. Public source URLs are filtered and have query strings and
fragments removed. These are disclosure boundaries, not general secret
classification: trusted writers must never put secrets in a public field.
See [data provenance](data-sources.md) and [verification](verification.md) for
scope, observed tests, and remaining limitations.
