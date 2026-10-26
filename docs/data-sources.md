# M02 data provenance

M02 contains project-generated synthetic geospatial data. It does not download
OSM, use live RTA data, identify actual Dubai streets, verify municipal
boundaries, or infer real signal locations. No SUMO network conversion, demand
execution, traffic metrics, or infrastructure control occurs in this milestone.
The separate M01 diagnostic runtime fixture is not proof that M02 geometry has
been converted into a SUMO network.

## Dataset records and version links

`data_sources` preserves provider name, dataset name/type, original source URL,
license identifier, attribution, collection time, source version, SHA-256
checksum, original metadata JSONB, and creation time. Dataset registration in
M02 is a database/seed capability; the public API exposes GET list/detail
routes, not an arbitrary dataset ingestion endpoint.

A network version refers to its region and, optionally, a source record. It
records its version label, lifecycle state, content checksum, source format,
projection SRID, artifact URI, counts, validation summary, and timestamp.
Region/version labels and region/content checksums are unique. Published
network content and child geometry are immutable; corrections require another
version. Scenario and demand records refer to the same exact network version,
with a database constraint preventing cross-version demand references.
Artifact URIs are persistence references and do not assert that an object store
or downloadable network exists. M02 has no public artifact retrieval route.

Public availability alone does not establish permission to use a dataset.
A null license identifier means no license has been registered; it is not a
grant of rights. Before a future real import, record the exact source version,
license/terms, required attribution, collection time, original source metadata,
content identity, coordinate system, and any transformations. Confirm allowed
uses and redistribution separately. Preserve the original metadata rather than
rewriting it to fit the public response.

## The Downtown Dubai synthetic fixture

`earthmind_api.fixtures` is the canonical deterministic fixture manifest, and
`earthmind_api.seed` persists it after Alembic migration. Use `make seed` to run
the seed within the existing Compose migration service.

| Item | Persisted value or meaning |
| --- | --- |
| Region slug | `dubai-downtown-demo` |
| Region name | `Downtown Dubai — Synthetic Study Region` |
| Region UUID | `8d31afa3-5d52-59b5-a8bc-691b5867dfcb` |
| Network UUID | `22f68ce8-9247-5425-8342-827d86517ead` |
| Source UUID | `128b1fd1-70f3-503a-b58a-e30bdf071edf` |
| Provider | `EARTHMIND` |
| Dataset | `M02 project-generated synthetic study fixture` |
| Source type / version | `synthetic` / `synthetic-v1` |
| Original source URL | `null`; the fixture is generated locally |
| License identifier | `LicenseRef-EARTHMIND-Proprietary-Synthetic` |
| Boundary | Illustrative MultiPolygon around Downtown Dubai, EPSG:4326, longitude/latitude |
| Bounds | `[55.2685, 25.19, 55.2805, 25.20]` |
| Road graph | Six explicit intersections and eight invented links |
| Signal status | One explicitly simulated signalized intersection, `n1` |
| Edge identifiers | Stable `provisional:e0` through `provisional:e7` in the compatibility `sumo_edge_id` field |

The custom `LicenseRef-` identifier labels the project-owned fixture; it is not
an SPDX-listed open license or a statement that a third party licensed Dubai
roads. The attribution explicitly says that the boundary and graph are
illustrative and invented. The repository's own license terms govern its
contents. Do not present this fixture as official geographic data.

The source/region/road/node metadata marks synthetic origin. Demand, scenario,
and intervention fixtures are also marked synthetic and execution-disabled.
The signalized flag is simulated. Nodes have `sumo_node_id: null`; edge
`sumo_identifier_verified` metadata is false. Provisional edge names reserve
future SUMO compatibility without asserting that SUMO has verified them.
Mixed one-way/two-way fields are synthetic attributes, not routing guarantees.

Coordinates remain `[longitude, latitude]`; the boundary encloses the tiny graph.
PostGIS derives geographic area, a covered centroid/representative point, and
metric edge lengths. The public API read on 2026-10-26 returned a region area of
`1.3398134937911033 km²`. This number measures the illustrative geometry; it
does not measure an official district.

## Checksum scope and reproducible seeding

Stable UUIDs use UUIDv5 with a fixed project namespace. The fixture content
checksum is SHA-256 over UTF-8 canonical JSON (`sort_keys=True`, compact comma
and colon separators) of `MANIFEST`. Its scope is:

- Boundary coordinates and geometry type.
- Node names and longitude/latitude coordinates.
- Edge names, explicit endpoint names, and one-way flags.
- Synthetic provenance/boundary-policy metadata.
- Default speed, road class, simulated signal node, and one-way/two-way lane counts.

The current manifest checksum, also observed in the running public source
response on 2026-10-26, is
`2706d3ffc30af0fe18892407afb8626be0199993b8f1236e9dde66e6e145b7cd`.
The source and network store this same manifest identity. It does not hash
collection/creation timestamps, generated geographic measurements, PostgreSQL
storage bytes, or demand/scenario/intervention contract configuration. It is a
fixture-content checksum, not a checksum of an imported OSM/SUMO file. A future
import must define its own original-artifact and normalized-content checksum
scope explicitly.

The seed takes a transaction-scoped PostgreSQL advisory lock to serialize
concurrent seeders. First creation inserts the source, region, graph, synthetic
contracts, and a safe audit event in one transaction. It runs structural
validation and publishes only `VALID` or `VALID_WITH_WARNINGS` output.

A repeat seed returns `created: false` for a published/archived, validated
fixture with the matching checksum and expected six-node/eight-edge counts.
It creates no duplicate features and preserves existing timestamps. A checksum
mismatch, incomplete version, or conflicting existing user-region slug causes
a refusal rather than an overwrite. This repeat check is a checksum/state/count
guard, not a fresh independent comparison of every stored coordinate. Database
immutability protects published fixture geometry. Never edit the manifest and
silently overwrite a published version; intentionally create a new version and
stable identity for corrected content.

## Public provenance and private metadata

`GET /api/v1/data-sources` and `GET /api/v1/data-sources/{id}` expose only these
fields: `id`, `provider_name`, `dataset_name`, `source_type`, `source_url`,
`license_identifier`, `attribution_text`, `collected_at`, `source_version`,
`checksum_sha256`, `created_at`, and derived `is_synthetic`. The original JSONB
metadata remains stored and is not returned by these endpoints. Network
summaries expose source/version/checksum information but omit `artifact_uri`.
Run artifact storage URIs have no public M02 route.

Public source URLs must use HTTPS with a host, contain no username/password,
and must not name localhost, `.local` hosts, single-label internal names, or
non-global literal IP addresses. Query strings and fragments are always
removed. Unsafe values serialize as `null`; the original URL is retained in the
database. This string validation does not resolve DNS, prove that a website is
trusted, or remove arbitrary secrets embedded in URL paths. A source URL is
provenance text; the API does not fetch it.

Region metadata is separately limited in public responses to `is_synthetic`,
`boundary_policy`, `description`, `source`, and `fixture_version`. Geometry
feature properties use explicit field selection rather than arbitrary metadata
merging. These allowlists prevent accidental blanket disclosure. They do not
classify arbitrary string contents: a trusted writer must ensure public names,
descriptions, attribution, URLs, and validation summaries contain no secrets.
Private metadata is not a credential store and is not encrypted by these
models. Keep operational credentials in ignored environment files/managed
secret storage instead.

Audit creation records action, target identifiers, timestamps, and safe metadata.
Region creation audits only the accepted slug; the seed audits a synthetic flag
and manifest checksum. A database guard rejects credential-like metadata keys,
including nested objects. It cannot identify every secret value placed under
an innocuous key by privileged manual SQL. Trusted ingestion and database
administration remain responsible for never storing credentials or secret
values in audit metadata.

## Validation and interpretation

The fixture validates real PostGIS storage, geometry serialization, spatial
indexes, meter-based proximity, boundary coverage, and explicit graph topology.
The live validation report read on 2026-10-26 reported `VALID`, six nodes, eight
edges, one connected component, and no isolated nodes. Validation is structural;
it proves no real-world traffic, route correctness, signal inventory, official
boundary, or simulation result.

Warnings have explicit semantics: `VALID_WITH_WARNINGS` passes integrity while
reporting structural or descriptive-metadata warnings. `INVALID` has integrity
errors. A graph above either the feature or aggregate-coordinate validation budget
is `NOT_VALIDATED`; PostGIS computes the budgets before geometry enters Python.
actual feature counts remain available and uncomputed component/isolate counts
are `null`. See [API contracts](api.md) for routes and limits and
[verification](verification.md) for executed checks and exact outcomes.
