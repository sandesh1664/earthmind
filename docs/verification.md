# Real Dubai geography recovery verification — 2026-10-27

Workspace `/Users/redmug/EARTHMIND`, branch `codex/recovery-real-dubai`, extending
clean M03 commit 91e97f1. The owner's explicit recovery brief authorizes real OSM
import, native SUMO conversion and a limited real-network synthetic-demand smoke.
No separate M04 work or remote push is included. Prior M01/M02/M03 reports and
historical evidence are preserved; [M03 report](verification-m03.md).

## Diagnosis and delivered behavior

Inspected source, instructions, locks, models, APIs, fixtures, current services
and actual browser before integration. Baseline commands below passed. The
loaded old browser showed only 8 invented roads / 6 nodes on low-resolution Natural
Earth with no configured ion provider. Large headings/cards displaced the scene.
A globe existed, but neither real city roads nor detailed city context was loaded.
The recovery preserves the application and replaces its default data/view.

Opening EARTHMIND now selects the real Downtown Dubai/Business Bay OSM version.
The full-height Cesium workspace renders actual source water/parks/roads/footprints,
402 explicit-height building extrusions, PostGIS road overlays and source-backed
inspection. Native fullscreen/resizing, presets, real layer visibility and mobile
inspection are tested. Synthetic fixture networks require explicit Development
mode; no real/synthetic network is silently merged. No operational traffic, AI,
photorealistic city mesh, or live vehicle feed is claimed.

## Exact source, measured import and lineage

Source: [OpenStreetMap contributors via Overpass](https://overpass-api.de/api/interpreter),
ODbL-1.0, visible attribution `© OpenStreetMap contributors`. A bounded explicit
GET query selects drivable ways, restrictions and cartographic context. The
complete actual query/timestamps/extent are in
[source-manifest.json](evidence/recovery/source-manifest.json).
It is an import command, not a runtime backend or public tile-scraping service.

| Observation | Actual result |
| --- | --- |
| Study bbox, west/south/east/north |[55.258,25.180,55.288,25.208], EPSG4326 longitude/latitude |
| Boundary meaning |Chosen engineering study extent, not an official administrative boundary |
| Original download timestamp |2026-10-26T23:12:15.216624+00:00 |
| Source XML |8,606,335 bytes;36,311 nodes;4,808 ways;189 relations,158 restriction relations |
| Original SHA256 |9aab25c641c00ba9e19110015173d6ac8bb2f18ba29975ed4545d85e8fe5eb3e |
| Native converted network SHA256 |86a950ddf4b835f74a5235973669c2d374803bade3d7053669ec2ddd9d87a7ab |
| Imported PostGIS roads |**2,364 directed road records** |
| Imported intersection records |**1,560 explicit graph-node records**; crossings do not create inferred junctions |
| Region UUID |bc48f4d4-32de-543b-aafc-0b49369f8bc8 |
| Network UUID |4aa62897-1a54-546c-a390-ddb156838f8e |
| Network version |osm-20261026-0b027352ec38, published |
| Mapping |1,273 OSM ways;486 map to multiple imported edges; maximum 22 edges/way |
| Mapping SHA256 |80bec1ad585f788a3137835f594207b4e2592f9958b9ff3345cd21d4d00c51b1 |
| Topology |VALID_WITH_WARNINGS:8 weak components,0 isolates; geometry/endpoints/counts/coverage passed |
| Omitted converted edges |211 outside bbox;17 unsupported shapes;0 unmapped/0self-loops |
| Converter-inferred lanes |923 records explicitly flagged; interpreted OSM tags are also not field verification |
| Local cartographic context |4,676 features,120 bounded labels;402 explicit-height models |

The original XML, converted .net.xml, complete source→SUMO→DB mapping and recorded
simulation outputs remain under ignored `data/dubai-osm/recovery-v1/`. They are
preserved on disk and excluded from Git/build contexts. Small manifests/metrics
are retained as evidence. SHA checks precede reuse; refreshing requires a new
artifact directory/version, not an overwrite or data reset. Repeat import returned
created=false with identical UUID/version/counts. Synthetic M02 data remains6/8.

Displayed selectable geometry is the georeferenced SUMO carriageway centerline
**derived from original OSM**, with graph junction centers as endpoints, not
manually invented coordinates or a promise of survey/lane-level accuracy.
Original OSM geometry/tags are preserved in the extract. One OSM way can produce
multiple directional/split SUMO edges. The complete mapping is independently
checksum/UUID-checked; no one-to-one mapping is assumed.

## Actual SUMO experiment

The native ARM64 worker loads the converted network, constrains route choice to
checksum-verified PostGIS-imported edge IDs, generates3 synthetic vehicles with
seed 42 and 5 second departure spacing and runs bounded TraCI. All 3departed, all 3
were observed moving and all 3completed; **0 teleports / 0 collisions**,50 steps,
121 recorded geographic positions and 1,427.31 m aggregate trip distance. Mean trip
duration 40.3333 s is a synthetic runtime observation, not Dubai traffic evidence.
Thirteen coordinate round trips had maximum error1.2360772744579555e-09m;
this measures numerical projection consistency, not source positional accuracy.

Route SUMO IDs: -106309507#6 →382042492 →484081082#5. The corresponding actual
DB UUIDs are retained with the run. Tripinfo, geographic FCD, summary and recorded
positions are real SUMO outputs. [Actual smoke result](evidence/recovery/smoke-result.json).
A browser playback adapter/timeline is **not implemented**; no fake animated cars
were substituted. The UI provides the working `make smoke-real` CLI instruction.

## Acceptance and explicit limits

| Requirement | Status | Scope/evidence |
| --- | --- | --- |
| Inspect existing implementation and real appearance | PASS | Source/infrastructure inspection, baseline, actual loaded browser |
| Recognizable real geographic view, Downtown/Business Bay presets | PASS | Actual self-hosted OSM geometry and screenshots; scoped study area |
| Original source, checksum/license/extent, repeatable import | PASS | Retained XML/manifests, repeated explicit workflow, real SQL checks |
| Actual PostGIS roads/nodes and version/source-backed metadata | PASS |2,364/1,560, typed APIs, real native picks matched to actual API records |
| Native netconvert plus OSM/SUMO/DB mapping | PASS |Actual converted XML/logs/checksums; many-edge mapping and UUID checks |
| Geometry/connectivity validation | PASS |Actual validation report;8-component warning remains visible, not relabeled perfect connectivity |
| Real defaults, separate synthetic development mode | PASS |Catalog tests and actual browser scope/cleanup checks |
| Layers, highlights, camera focus, fullscreen/mobile controls | PASS |Real scene counters/visibility, canvas click, native fullscreenElement and canvas resizing |
| Local OSM explicit-height models/attribution | PASS |402source-tagged extrusions, native source readiness, no invented heights |
| Cesium ion buildings/satellite imagery/world terrain | BLOCKED |No public token/entitlement configured; exact configuration notice retained |
| Basic imported-network synthetic vehicle smoke | PASS |3departed/moved/completed, actual FCD/metrics, route constrained to imported DB graph |
| Browser vehicle replay/live traffic | NOT RUN |Replay not implemented; live traffic not connected; actual recorded output retained |
| M01/M02/M03 regressions, production/dev builds and assets | PASS |116 Python/88 frontend/38 live DB/30 browser, NextStrictMode, HTTP asset checks |
| Native ARM64 Docker, migrations, recovery and private context | PASS |Final checks below; main data preserved; migration head0004 unchanged |
| Security/licensing review | PASS |Narrow metadata/config, hashes/budgets, retained credits, scans and scoped limitations |
| Physical Apple GPU FPS/GPU memory/long-run real-context memory | NOT RUN |Software-rendered Chromium observations only; earlier M03 benchmark is historical |
| Hosted CI | NOT RUN |Workflow parsed locally. Ordinary CI is offline; real-data checks require explicit import input |
| Final Git commit/clean state | PASS |Requested local commit exited 0; clean status observed, then actual evidence included by a documentation amendment |

## Exact commands and actual results

All commands below executed in the target workspace. Asia/Dubai timestamps,
complete argv/cwd/durations/exits (including failures) are in
[commands.jsonl](evidence/recovery/commands.jsonl). The runner preserves actual
output; unit mocks are not described as end-to-end proof. Integration cases run
separately from ordinary pytest. Final DB/outage/migration checks run after the
browser suite, avoiding dependency mutations during acceptance.

| Dubai time | Exact command | Exit | Status | Actual result |
| --- | --- | --- | --- | --- |
| 03:12:24 | `make lint typecheck test build smoke` | 0 | PASS | M03 baseline and M01/M02 unit/build/queue/SUMO/spatial smokes passed before integration. [output](evidence/recovery/baseline.log) |
| 16:16:13 | `make lint typecheck test build` | 0 | PASS | 116 Python units;88 frontend tests; strict mypy48files; Ruff/ESLint/TypeScript and production build. [output](evidence/recovery/release-quality.log) |
| 16:14:41 | `env CITY_DIAGNOSTICS_ENABLED=true make dev` | 0 | PASS | Native ARM64 production images, unchanged migrations, seed and all existing smokes. [output](evidence/recovery/fallback-deploy.log) |
| 16:16:10 | `npm run test:browser -- --workers=1` | 0 | PASS | 30 browser checks across desktop/tablet/mobile;21 actual-service cases and9 isolated mocked UI-state cases. [output](evidence/recovery/browser-complete.log) |
| 16:20:22 | `make import-dubai` | 0 | PASS | Complete explicit download/conversion/import/context workflow repeated with checksummed artifacts; no re-download/reset. [output](evidence/recovery/repeat-import.log) |
| 16:20:29 | `uv run --locked python scripts/verify_real_geography.py` | 0 | PASS | Real SQL validity/counts, actual typed API metadata, source/context hashes and preserved6/8fixture. [output](evidence/recovery/final-geography.log) |
| 16:20:29 | `make smoke-real` | 0 | PASS | Native SUMO:3 actual departures, moving vehicles and completed trips on mapped imported edges;0collisions/teleports. [output](evidence/recovery/final-sumo-real.log) |
| 16:20:30 | `uv run --locked python scripts/database_checks.py` | 0 | PASS | 38 actual PostGIS/API integration cases passed; fixture and real network preserved. [output](evidence/recovery/final-database.log) |
| 16:20:32 | `uv run --locked python scripts/verify_migrations.py` | 0 | PASS | Isolated fresh/repeat/check/downgrade-guard rehearsal; no new migration or main-volume reset. [output](evidence/recovery/migration-rehearsal.log) |
| 16:21:00 | `uv run --locked python scripts/inspect_geospatial_database.py --output docs/evidence/recovery/postgis-inspection.json` | 0 | PASS | Actual spatial schema and index-backed queries retained under recovery evidence. [output](evidence/recovery/postgis-inspection.log) |
| 16:21:01 | `uv run --locked python scripts/failure_smoke.py` | 0 | PASS | Actual worker/Redis/database stop/readiness503/liveness200/recovery; services restored. [output](evidence/recovery/failure-recovery.log) |
| 16:21:13 | `make migrate` | 0 | PASS | Repeated Alembic upgrade at0004_run_state_integrity. [output](evidence/recovery/final-migrate.log) |
| 16:21:16 | `make smoke` | 0 | PASS | Real M01queue/SUMO, M02spatial/API and Cesium asset-byte checks. [output](evidence/recovery/final-smoke.log) |
| 16:21:17 | `uv run --locked python infra/verification/check_build_context.py` | 0 | PASS | Environment files and private data remain outside actual Docker build contexts. [output](evidence/recovery/context-isolation.log) |
| 16:21:17 | `uv run --locked python scripts/check_architecture.py` | 0 | PASS | All service images linux/arm64 on nativeaarch64 engine; no AMD64 emulation. [output](evidence/recovery/native-architecture.log) |
| 16:21:18 | `docker compose ps --all` | 0 | PASS | Five healthy long-running services; migration exited 0; DBloopback5434. [output](evidence/recovery/final-services.log) |
| 16:22:09 | `python3 /private/tmp/earthmind-recovery-results/verify-development.py` | 0 | PASS | Actual Next development/Strict Mode with real OSM context;3mounts,1canvas live/0after eachunmount, noerrors. [output](evidence/recovery/development-recovery.log) |
| 15:56:57 | `npm audit --json` | 0 | PASS | Zero known npm advisory findings. [output](evidence/recovery/npm-advisories.log) |
| 15:57:34 | `Exact argv in commands.jsonl (python-advisories)` | 0 | PASS | Public installed Python distributions checked; local packages explicitly skipped, no known findings. [output](evidence/recovery/python-advisories.log) |
| 16:20:28 | `Exact argv in commands.jsonl (ci-syntax)` | 0 | PASS | Workflow parsed locally, native ARM runner and explicit external-data opt-in checked; hostedCI NOTRUN. [output](evidence/recovery/ci-syntax.log) |
| 16:24:54 | `node /private/tmp/earthmind-recovery-results/final-view.mjs` | 0 | PASS | Actual fully loaded WebGL2 scene screenshot;500 visible roads/402 height models; no errors/failed HTTP requests. [output](evidence/recovery/final-visual.log) |

The initial source download/conversion/import were executed directly by the
implementation agent. Their actual request and netconvert argv are retained in
the source/conversion manifests and native converter log; they were not invented
as fresh reruns of the repeat workflow. Download reuse does not contact Overpass.
Expected populated-downgrade refusal is checked inside the successful isolated
migration rehearsal; it never drops the main database.

## Browser evidence and performance scope

The final 30 Chromium checks span desktop1440×1000, tablet820×1180 and mobile390×844.
Twenty-one use actual services/native rendering (including actual WebGL-disabled
fallback);9 legacy UI empty/error/retry cases explicitly mock those isolated states.
No geographic responses are mocked to prove import or real rendering. Road IDs,
source IDs, lanes, length, version and inference fields are checked against actual
API responses. Source/context SHA values match. Native fullscreen, camera pose,
layer visibility, source attribution, no fatal console/page errors and no public
external tile requests are checked.

Actual screenshots: [Fully loaded Dubai desktop](evidence/recovery/final-view-desktop.png),
[tablet](evidence/recovery/dubai-tablet.png),
[mobile](evidence/recovery/dubai-mobile.png),
[source-backed inspector](evidence/recovery/road-inspector-desktop.png).
These are real Cesium views of OSM-derived context, not satellite photos or
photorealistic ion tiles. Native models are footprint extrusions with partial
height coverage. The retained Burj Khalifa way has levels but no numeric height
tag, so its height was not invented; it remains flat in this snapshot.

Final fresh-browser-context navigation-to-nonempty-native-road-ready observations:
[6768, 6085, 4499, 6102, 5240, 4043]ms. These include source fetch/validation and context contention,
not GPU frame latency. Initial unnecessary terrain-ground classification took
roughly 19–27s in recorded runs; ellipsoid-specific context preparation reduced
later observations to roughly 5–7s in this environment. Small display-only offsets
(0.2/0.35m) avoid z-fighting; they are not measured elevations. Local-mode terrain
is deliberately blocked to avoid mixing absolute building heights with a different
surface. No numerical hardware FPS or indefinite leak-free guarantee is claimed.

## Failures and repairs retained

- Initial system-Python download failed TLS before data acquisition; the workflow
  uses locked Python 3.12. Initial POST requests returned 502/timed out; one explicit
  bounded GET succeeded. Original successful source/timestamps/checksum are retained.
- Native conversion initially failed because the old worker lacked SUMO OSM
  typemaps/schemas. Exact official `sumo-tools` data was added with build assertions;
  native conversion now succeeds. Its warnings remain:8 ignored restrictions,
  27 junction-shape offsets,117 connection-speed reductions, plus sharp-turn/lane warnings.
- Initial integrated lint found 2 long wrapper lines; formatting corrected them.
  Strict optional metadata and nullable source-timestamp typing failures were fixed;
  final full quality passes. Failed command logs retain their original exits.
- First browser run failed. Later diagnostics found DB/Redis/worker Exited(0) and
  API DNS resolution of db failing; why services stopped was not established.
  Compose restored them. This failed run is not a performance benchmark.
- A road-ready test accepted the initial empty scene too early. It now waits for
  nonempty native geometry, completed preparation and a settled camera together.
- Fixture regressions initially assumed the synthetic region was the first catalog
  entry. They now explicitly choose that fixture and retain all data assertions.
- Cached synthetic viewer initialization could adopt real context. The constructor
  now applies effective synthetic mode immediately; regression checks require zero
  local real building resources in that mode.
- Mobile native-pick diagnostics could target a projection under controls; they
  now choose an unobstructed actual canvas point, then verify native-picked metadata.
  Deselecting closes the normal mobile sheet to restore camera access, while the
  no-WebGL metadata fallback remains open. Layer controls stack above the sheet.
- The extra read-only verifier initially used the wrong intersection column name;
  it now uses the actual `location` column and passes against real SQL/API data.

No failed run is relabeled PASS. Raw logs and final reports are retained; temporary
trace archives are excluded. Earlier failure images were not all archived, and
none are fabricated. A sandbox cache/automatic approval timeout that prevented an
invocation from starting is not counted as a test execution.

## Security, reproducibility and remaining problems

There is no token in source or the build. Only public visualization config crosses
the runtime boundary. Python and Zod independently project safe metadata, including
bounded source-ID arrays; original tags/paths remain private. GeoJSON is streamed
under 12 MiB, validated for bounded finite coordinates, checked against artifact
SHA256, and loaded with default raw-HTML descriptions disabled. Inspector values
are escaped text. No unrestricted geographic proxy or public raster scraping is
added. Original extracts and synthetic output archives stay outside Git/contexts.

OSM data is not survey-verified; lane inference, turn restrictions and signal tags
are explicitly uncertain. Eight disconnected components, omitted edge shapes and
missing heights remain real limitations. Outside the study extent the global
reference is coarse. Licensed ion tiles/terrain require operator credentials.
Operational traffic, calibrated demand, production scenario execution, AI and
browser replay are absent. M01 flags retain their original compatibility contract;
the UI identifies the separately available local CLI workflows.

The stack remains trusted loopback development: privileged local DB role, no shared
identity/TLS/managed secrets/backups/global rate quotas, private Redis without
password and at-most-once M01 diagnostics. npm/pip scans cover their package scope,
not native OS packages or a production security certification. Transitive apt
repositories remain live; exact source/locks/top-level SUMO pins do not promise
permanent byte-identical system builds. ODbL attribution/source obligations are
recorded with the original extract; sharing deployments/data needs that review.

## Git delivery

Actual source/staged whitespace checks and all six pre-commit hooks passed.
The candidate scan checked 648 files, the first staged scan 155 blobs, against 2
configured working secret values; no matches/private keys/generated source data/
caches/oversized files were found. Raw data remains ignored and preserved on disk.
[Hooks](evidence/recovery/hooks.log), [staged scan](evidence/recovery/staged-secret-check.log),
[candidate scan](evidence/recovery/candidate-secret-check.log),
[whitespace](evidence/recovery/staged-whitespace.log). The complete source diff was
reviewed; migration history, dependency locks, M01 contracts and historical
verification evidence remain unchanged.

The staged inventory/diff snapshot are retained as git-changed-files.txt and
git-diff-stat.txt under evidence/recovery. The requested local commit actually exited 0; all applicable commit hooks passed,
and `git status --porcelain=v1` returned empty afterwards. The final staged scan
checked 164 blobs against 2 configured secret values with no matches/private keys/
forbidden artifacts/oversized files. [Commit output](evidence/recovery/git-commit.log),
[final scan](evidence/recovery/final-staged-secret-check.log),
[gate record](evidence/recovery/git-gates.json). This actual execution evidence and
status update are included by a documentation-only amendment of the same focused
commit. No push has occurred. The final hash is obtained after that amendment
with `git log -1` and reported to the owner.
