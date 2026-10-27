# Real Dubai OSM import and SUMO lineage

The recovery importer is an explicit local engineering command, not an automatic
public API fetch. It preserves the M02 synthetic fixture and publishes a separate
version backed by a genuine downloaded OpenStreetMap extract. Code lives in
`scripts/import_dubai_osm.py` and `earthmind_api.osm_import`.

## Study area and responsible download

The reviewed study box is **west 55.258, south 25.180, east 55.288, north 25.208** in
EPSG:4326, longitude then latitude. It covers a bounded portion of Downtown Dubai
and Business Bay. This research rectangle is not an official municipal boundary.
The CLI rejects extents outside the reviewed Dubai bounds or larger than 0.05° per
axis. The Overpass query requests road classes suitable for passenger-car network
conversion, restriction relations, buildings and limited water/park/landuse
context. Original complete ways may extend beyond the query box.

The downloader makes one manually invoked request, with a 60-second server query
budget, 90-second client timeout and 32 MiB response cap. No parallel fetches,
automatic retry loop, tiling or public tile scraping is implemented. It supports
only an explicit allowlist of public Overpass endpoints and GET/POST methods.
A previous source directory is reused only after checking its original checksum;
partial or modified source directories are not overwritten.

```sh
uv run --locked python scripts/import_dubai_osm.py download --directory data/dubai-osm/recovery-v1
uv run --locked python scripts/import_dubai_osm.py convert --directory data/dubai-osm/recovery-v1
uv run --locked python scripts/import_dubai_osm.py import --directory data/dubai-osm/recovery-v1
```

`data/` contains local retained source/derived artifacts and stays outside Git
and Docker build contexts. Preserve or back up it if the exact source snapshot
is needed later. A fresh download may produce a newer OSM snapshot and therefore
a new immutable network version. Existing source artifacts give a checksum-locked
repeatable import; the live upstream service is not a permanent artifact store.

The first successful recovery extract came from
`https://overpass-api.de/api/interpreter` using GET. Original source bytes, query,
actual download time, OSM base snapshot timestamp, checksum, response size,
license and exact extent are retained in `source-manifest.json`. Restricted
private source metadata and artifact locations are not returned through the
public geographic API. Final actual counts and results belong to the recovery
verification record, not assumptions in this workflow description.

## Conversion and geometric meaning

The existing native ARM64 worker runs installed `netconvert` 1.15.0 using its
matching Debian `sumo-tools` package, which supplies OSM typemaps and XML schemas.
The worker image checks those files during build. M01's small plain-XML SUMO
probe did not exercise this dependency; real OSM conversion revealed it.

Conversion preserves original feature names/IDs and uses UTM zone 40N projection.
Junction joining, ramp guessing and traffic-light guessing are explicitly off.
The standard converter still interprets road attributes, lane direction, default
speeds, priorities and connections. They are operational model assumptions,
not field verification. Conversion logs and exact command/source/network hashes
are retained in `conversion-manifest.json`.

Database roads are **directed SUMO carriageway centerlines derived from OSM**,
not untouched raw OSM way coordinate arrays. Lane-center geometry is averaged
where lane vertices align, projected back from the recorded SUMO projection and
netOffset, and joined to actual converted junction centers to keep explicit graph
endpoints coherent. This may shift a displayed carriageway a few meters from
OSM's original way centerline. The original way is retained in the source XML.
No manually invented street coordinates are substituted.

Only complete converted edges covered by the exact study box enter PostGIS.
Boundary-crossing edges, self loops unsupported by the existing M02 graph,
unmapped sources and unsupported shapes are counted as omissions. There are no
fabricated boundary intersections. The larger converted SUMO artifact can retain
roads outside the study box; simulation output reports its actual recorded
extent and must not claim to be clipped to the PostGIS display subset.

Each DB edge has its actual verified SUMO ID. Lane `origId` parameters establish
its original OSM ways; fallback parsing accepts an ID only if that way exists in
the actual source extract. A way may generate multiple directed/split SUMO edges;
joined lineage may also contain several original way IDs. The retained
`source-sumo-db-mapping.json` explicitly maps each way to every imported SUMO edge
and corresponding deterministic database UUID. No one-to-one assumption is used.

## Persistence and metadata truthfulness

The importer reuses the existing ORM base, infrastructure/session factory and
PostGIS tables. A transaction and advisory lock serialize imports. The version
identity binds original source SHA, SUMO network SHA, study bbox and geometry
policy/version. Existing complete versions are reused with actual row-count
checks; user data and published networks are not replaced. The normal bounded
network validator checks geometry, explicit endpoints, counts and connectivity
before publication. Disconnected components remain explicit warnings rather
than silently being discarded. No new migration is required.

OSM `maxspeed` becomes a public speed only when a recognized numeric km/h or mph
value is present; missing/unrecognized limits remain null. SUMO's operational
speed stays private metadata. The DB requires a lane count, so it stores the
actual converted directional count, with public provenance distinguishing an
exact directional OSM tag, SUMO interpretation of an OSM total-lanes tag, and a
converter inference when no usable source value exists. The raw recorded lane
and speed tags are retained. Inspectors must display this distinction.

A traffic-signal marker requires a stored original OSM signal tag. Unknown signal
status is not proof of an unsignalized intersection; OSM tags are not field
verified. Turn restrictions are only those present and supported by conversion,
with incomplete/nonverified status explicitly recorded. Real geometry does not
establish lane-level traffic accuracy, current restrictions or live conditions.
Public metadata is a bounded allowlist; original tags, operational defaults and
private artifact paths are excluded.

## License and source documentation

OSM data and derived geographic databases are governed by ODbL 1.0 independently
of the application's source-code license. Keep **© OpenStreetMap contributors**
and the copyright/license link visible. Preserve downstream attribution and
applicable share-alike requirements when distributing derived databases.

- [OSM copyright and license](https://www.openstreetmap.org/copyright)
- [Overpass shared-service usage](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html)
- [SUMO OSM conversion and original names](https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html)
- [SUMO projection and coordinate conversion](https://sumo.dlr.de/docs/Networks/SUMO_Road_Networks.html)
- [Pinned Debian SUMO tools package](https://packages.debian.org/bookworm/sumo-tools)

Actual downloaded sources and converter/simulation artifacts are not mocked
unit-test evidence. The isolated parser tests are labeled as such; real import,
PostGIS/API access, native conversion, vehicle smoke and browser inspection must
be run separately and retain their own outcomes.
