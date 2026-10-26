# M02 verification — 2026-10-26

This is the M02 implementation and audit record for `/Users/redmug/EARTHMIND`,
branch `codex/m02-geospatial`, extending clean M01 commit
`ff043bcb47c80ff66e2d5ddd1092ed1466571a26`. The
[preserved M01 report](verification-m01.md) and its evidence are unchanged
historical records. All times here use Asia/Dubai (UTC+04:00).

The M01 repository, instructions, routes, settings/engine/base, migrations,
Compose, frontend, locks and verification evidence were independently inspected
before major changes. Actual `make smoke` passed at the M01 baseline, including
HTTP/queue/worker and a real SUMO fixture; [baseline output](evidence/m02/m01-baseline-smoke.log).
No main development volume was reset and no M01 table or test was removed.

## Environment and compatibility

Host macOS/darwin ARM64; Docker Engine 29.9.1 linux/aarch64, Compose v5.6.0;
host Node 26.0.0/npm 11.12.1/uv 0.11.12. Project Python remains constrained to
3.12: actual host 3.12.13, container 3.12.15; no Python 3.14 compatibility claim.
The web container uses Node 22.23.4. Locked GeoAlchemy2, Shapely, pyproj and
NetworkX install and execute successfully in the ARM64 Python 3.12 image.
PostgreSQL is 17.11, PostGIS is 3.6.4 with GEOS/PROJ support; complete version
strings appear in [actual SQL inspection](evidence/m02/postgis-inspection.json).

All final service images were verified linux/arm64 against the native engine;
[architecture output](evidence/m02/native-architecture.log). M01's digest-pinned
custom ARM64 PostGIS build is retained because its selected upstream image lacks
ARM64. Native SUMO/netconvert 1.15.0 remains working. No AMD64 emulation was used.
Image names retain `:m01` to preserve existing local image conventions; rebuilt
API/web/worker images contain the final M02 source. Default host ports remain
loopback web 3000, API 8000 and PostgreSQL **5434**; Redis is unpublished.

## Implemented requirements and acceptance

| Requirement | Status | Evidence / scope |
| --- | --- | --- |
| Preserve working M01 foundation and single ORM/engine/settings | PASS | Baseline smoke, unchanged contracts, full regression suite |
| Thirteen required M02 tables, UUID/UTC/JSONB, explicit constraints | PASS | Live catalog inspection; 30 persistence integration cases |
| PostGIS geometry types, validity/range/2D/SRID and GiST indexes | PASS | Four EPSG:4326 columns; actual index queries and DB rejection tests |
| Metric area/length/distance and longitude/latitude GeoJSON | PASS | PostGIS geography, independent pyproj area, geometry units/live API |
| Explicit graph endpoints, same-network references and immutable publication | PASS | Composite FKs, row locks, triggers and real DB mutation rejection |
| Scenario/demand consistency, strict run/timestamps, finite metrics | PASS | Database constraints/triggers; regressions pass after additive 0004 |
| Synthetic Dubai study region and >=6-node/8-edge graph | PASS | Actual persisted IDs/counts; stable synthetic provisional identifiers |
| Idempotent seed, source attribution/license/version/checksum | PASS | First seed created; repeats false; synthetic demand/scenario/intervention fixtures only |
| Fourteen typed REST endpoints, safe errors, pagination and write gate | PASS | Seven live API test functions exercise every route and rejection cases |
| Bbox/polygon/nearby filters and bounded processing/serialization | PASS | Real indexed queries, API limits, streaming-body tests, aggregate coordinate preflight |
| VALID/WARN/INVALID/NOT_VALIDATED network validation | PASS | Explicit weak topology, meter tolerance, null unknown counts, structured tests |
| Responsive real-data Geospatial Data dashboard | PASS | 15 browser cases across desktop/tablet/mobile; screenshots and live backend |
| Fresh M01 upgrade, repeat migration, schema comparison, safe downgrade | PASS | Isolated rehearsal; legacy sentinel retained, empty downgrade works, populated downgrade refused |
| M01 health/queue/worker/SUMO/build regressions | PASS | Final smoke, unit/browser checks and actual dependency outage/recovery |
| Locked lint/types/test/build | PASS | Local commands below |
| Final hooks, staged secret review and source whitespace | PASS | Six hooks passed; actual staged127 files checked;2 configured secrets absent; no keys/caches/archives/>2MB files |
| Required documentation and architecture decision | PASS | Schema/ER, architecture, API, sources, README, AGENTS, security, ADR 0009 |
| Hosted GitHub Actions execution | NOT RUN | Workflow parsed locally; no remote push or hosted execution authorized |
| Physical-device browser testing / production load benchmark | NOT RUN | Chromium viewports and eight-edge fixture only |
| Shared/public deployment identity, TLS, least-privilege roles, backups | NOT RUN | Explicit development boundary; outside M02's loopback-only option |

No mandatory local M02 implementation requirement remains missing. The explicitly
unexecuted checks above are not claimed as passes. Real OSM/RTA ingestion, SUMO
network conversion, traffic execution, signal control, AI, Cesium and M03 are
outside this milestone and were not implemented.

## Exact commands and actual results

Commands below ran in `/Users/redmug/EARTHMIND`. The complete executed argv,
working directory, timestamps, durations and exits (including staged-source
supplementary checks) are in [commands.jsonl](evidence/m02/commands.jsonl).
The runner itself is retained as [run_check.py.txt](evidence/m02/run_check.py.txt).
Normal `make test` deliberately deselects integration; actual PostGIS tests ran
separately. A successful Docker build is not used as a substitute for live tests.

| Dubai time | Exact command | Exit | Status | Actual result / output |
| --- | --- | --- | --- | --- |
| 22:18:53 | `make setup` | 0 | PASS | Locked workspace installs, generated missing server token without replacing credentials, hooks installed. [setup](evidence/m02/setup.log) |
| 22:32:54 | `docker compose build` | 0 | PASS | Native images rebuilt with additive integrity migration and spatial index fix. [rebuild-integrity](evidence/m02/rebuild-integrity.log) |
| 22:34:40 | `make migrate` | 0 | PASS | Main database advanced to 0004_run_state_integrity; M01 retained. [migrate-integrity](evidence/m02/migrate-integrity.log) |
| 22:26:13 | `make seed` | 0 | PASS | Created synthetic region/network: 6 nodes and 8 edges. [seed-first](evidence/m02/seed-first.log) |
| 22:49:02 | `make lint typecheck test build` | 0 | PASS | 67 Python unit tests; 28 frontend tests; mypy 40 files; Ruff/ESLint/tsc and production Next build passed. [final-quality-verified](evidence/m02/final-quality-verified.log) |
| 22:49:19 | `uv run --locked python scripts/database_checks.py` | 0 | PASS | 38 actual PostGIS tests passed: 30 persistence, 7 spatial API and 1 M01 session test. [final-database-integration](evidence/m02/final-database-integration.log) |
| 22:47:52 | `make dev` | 0 | PASS | All services healthy; repeat seed created=false; real M01 and M02 smokes passed. [final-dev](evidence/m02/final-dev.log) |
| 22:49:18 | `uv run --locked python scripts/verify_migrations.py` | 0 | PASS | Fresh M01->head, legacy-row retention, repeated upgrade/check, empty downgrade/re-upgrade, idempotent seed and populated downgrade refusal. [final-migration-rehearsal](evidence/m02/final-migration-rehearsal.log) |
| 22:49:19 | `uv run --locked python scripts/inspect_geospatial_database.py` | 0 | PASS | 13 M02 tables, 4 spatial columns, actual bbox/geography indexed executions. [final-postgis-inspection](evidence/m02/final-postgis-inspection.log) |
| 22:44:46 | `npm run test:browser` | 0 | PASS | 15 passed: 6 real deployment cases, 9 explicitly mocked UI-state cases across 3 viewports. [final-browser](evidence/m02/final-browser.log) |
| 22:41:53 | `uv run --locked python scripts/failure_smoke.py` | 0 | PASS | Worker, Redis, DB outages produced readiness503; liveness200; restoration passed. [failure-recovery](evidence/m02/failure-recovery.log) |
| 22:45:58 | `uv run --locked python infra/verification/check_build_context.py` | 0 | PASS | Five synthetic environment fixtures excluded from actual Docker contexts. [context-isolation](evidence/m02/context-isolation.log) |
| 22:46:00 | `uv run --locked python scripts/check_architecture.py` | 0 | PASS | Every service image linux/arm64; engine aarch64. [native-architecture](evidence/m02/native-architecture.log) |
| 22:37:13 | `npm audit --json` | 0 | PASS | Zero known npm advisory findings. [npm-audit](evidence/m02/npm-audit.log) |
| 22:49:42 | `make migrate` | 0 | PASS | Repeated main upgrade succeeded at 0004; data preserved. [final-migrate](evidence/m02/final-migrate.log) |
| 22:49:39 | `make smoke` | 0 | PASS | Actual final M01 SUMO/queue and M02 spatial/web/PostGIS/write-gate checks passed. [final-smoke](evidence/m02/final-smoke.log) |
| 22:49:45 | `docker compose ps --all` | 0 | PASS | Five healthy long-running services; migration exited0; loopback ports. [final-services](evidence/m02/final-services.log) |

`make lint` includes lock consistency, canonical M01 contract parity, Ruff and
formatting, ESLint, mypy and TypeScript; explicit `make typecheck` also ran.
The updated native ARM64 CI YAML was parsed and its permissions/inspection step
asserted locally: [output](evidence/m02/ci-syntax.log), exact inline Python argv
in commands.jsonl. Hosted CI remains NOT RUN.

Pinned Python advisory command (actual target environment, no dependency changes):

```sh
UV_CACHE_DIR=/private/tmp/earthmind-m02-uv-cache uvx --python 3.12 --from pip-audit==2.10.1 pip-audit --path /Users/redmug/EARTHMIND/.venv/lib/python3.12/site-packages --format json --progress-spinner off --timeout 15 --cache-dir /private/tmp/earthmind-m02-pip-audit-cache
```

Exit0: all 64 installed distributions accounted for, 61 public packages audited,
zero known findings; 3 unpublished EARTHMIND packages skipped. Actual inventory
was unchanged. [Summary](evidence/m02/python-advisories.summary.json),
[result/command](evidence/m02/python-advisories.result.json),
[raw advisory JSON](evidence/m02/python-advisories.json). This excludes private
package contents, application logic and native OS/PostGIS/SUMO libraries.

## Database and API observations

Executed `SELECT PostGIS_Version();` and
`SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;`
against real PostGIS (database_checks.py and inspection script). The JSON
inspection records full versions, the complete actual public table list, geometry
columns and index definitions. Required M02 tables are users, regions,
data_sources, network_versions, road_edges, intersections, demand_profiles,
scenarios, scenario_interventions, simulation_runs, run_metrics, run_artifacts
and audit_events; M01 system_metadata remains schema1 and migration head is0004.

The database suite covers stored geometry, metric queries, invalid SRID/range/
empty/type/vertices, NaN/infinity, foreign keys/duplicates, restricted deletion,
transaction rollback, publication immutability, scenario consistency, audit-key
guards and run-state/timestamp integrity. API cases run in-process FastAPI with
an actual PostGIS session/transaction; they are not an HTTP substitute for the
separate deployed smoke. They cover all14 routes, authorized201, missing/wrong
token403, conflict409, missing404, invalid422, body413 in security units,
pagination/empty/boundary cases, private provenance filtering, bbox/polygon
bounds, true meter distances, index eligibility and null budget counts. The new
aggregate-coordinate budget case also traps any attempted shape materialization.
All test mutations use rollback; the main fixture remains stable.

Alembic `check` reported no new upgrade operations. Isolated verification begins
without the PostGIS extension, establishes M01 and a sentinel row, upgrades to
M02, tests an empty downgrade and upgrade, seeds twice, then verifies that a
populated downgrade fails before dropping research data. That child nonzero
exit is expected and checked; the overall verification exits0. Only the isolated
`earthmind-m02-verification` fixture volumes are removed, never the main volumes.

## Actual synthetic fixture and topology result

Region `8d31afa3-5d52-59b5-a8bc-691b5867dfcb`, slug `dubai-downtown-demo`:
Downtown Dubai — Synthetic Study Region. Network
`22f68ce8-9247-5425-8342-827d86517ead`, version `synthetic-v1`, published.
The first source collection timestamp is an actual seed time, not an invented
observation date. Boundary/graph are project-generated and illustrative.

- Bounds `[55.2685,25.19,55.2805,25.2]`; representative geographic centroid
  `[55.2745,25.195000053]` lies inside the boundary.
- Database geodesic area `1.3398134937911033 km²`; independent pyproj result
  `1.3398134937901496 km²`.
- Six intersections/eight edges, mixed one-way metadata, one simulated signal,
  deterministic provisional identifiers; no verified SUMO or street identities.
- Fresh validation: VALID, 11 checks true, 1 weak component, 0 isolated nodes,
  no errors/warnings, geography boundary tolerance5m.
- Actual nearby query distance `20.15803569 m`; contains centroid=true and
  `[0,0]`=false; unauthorized deployed region creation returned403.
- License `LicenseRef-EARTHMIND-Proprietary-Synthetic`; original source and
  network checksum preserved; no external source URL or real dataset claim.

Actual GeoJSON examples are in [API docs](api.md); complete stored geometry is in
[inspection JSON](evidence/m02/postgis-inspection.json). Synthetic demand,
scenario and intervention rows are persistence fixtures with execution disabled.
No simulation_runs or measured traffic metrics were seeded. The real SUMO
regression still runs M01's separate two-vehicle/25-step fixture; those are
synthetic runtime results, not M02 traffic-scenario output.

VALID_WITH_WARNINGS permits descriptive/weak-connectivity warnings;
INVALID marks integrity errors. NOT_VALIDATED skips traversal when a feature or
aggregate-coordinate budget is exceeded, returning actual node/edge counts and
null components/isolates. It must not imply zero or successful connectivity.
Topology validation never infers junctions from geometric crossings or proves
real-world road accuracy.

## Actual spatial index observations

The final inspection executed EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON) for real bbox
and meter-radius queries against the eight-edge fixture. With sequential scans
disabled for index eligibility, bbox used `ix_road_edges_geom_gist` and proximity
used `ix_road_edges_geography_gist`. Observed execution times in this run were
0.014ms and 0.008ms respectively. Default and forced plans are retained in
[postgis-inspection.json](evidence/m02/postgis-inspection.json).
These are single tiny-fixture observations, not throughput/latency benchmarks.
A sequential scan can correctly be cheaper for eight rows.

## Failures retained and defects fixed

No initial failed check is relabeled as a pass. Corrective runs are separate.

| Actual earlier failure | Result | Fix and subsequent proof |
| --- | --- | --- |
| Queued timestamp mutations accepted at migration0003 | FAIL: 2 regressions failed, exit1 | Added0004 timestamp/state constraints; final30 DB cases pass. [before](evidence/m02/run-state-before.log), [command](evidence/m02/run-state-before.json) |
| Database accepted valid5,001-position geometry beyond API budget | FAIL: 2 regressions failed, exit1 | Added0004 stored5,000-position guards; final tests pass. [before](evidence/m02/vertex-budget-before.log), [command](evidence/m02/vertex-budget-before.json) |
| Geography typmod prevented expression-index use | Observed forced Seq Scan | Plain geography cast now uses real functional index. [actual before/after plans](evidence/m02/geography-index-fix-proof.json) |
| Fresh-migration sentinel omitted required UUID | FAIL: harness exit1 | Addedgen_random_uuid sentinel; final fresh/empty/populated migration rehearsal passes. [failure](evidence/m02/fresh-migrations.log) |
| Inspection expected incorrect bbox index name | FAIL: exit1 | Corrected assertion to actual `_gist` name; final indexed query succeeds. [failure](evidence/m02/indexed-spatial-query.log) |
| Browser launch in restricted sandbox | BLOCKED/exit1; no browser pages executed | Final approved real deployment run passes15. [original report](evidence/m02/frontend-browser-sandbox-failure.json) |
| Turbopack port binding denied in staged sandbox; cached error repeated | FAIL: build attempts; no successful-build claim for those runs | Cleared only task-generated cache; final host/container builds pass. [panic1](evidence/m02/next-panic-875b667e414eaab4a4ee4c9fde7e391b.log), [panic2](evidence/m02/next-panic-cf4020773125a93dbee0f807788d20c2.log) |
| Task-generated temporary Next cache accidentally synced into lint input | FAIL: make exited2;72 generated-code errors/74 warnings | Removed only that cache; no source lint exclusions. [failure](evidence/m02/final-quality.log) |
| Inspection dialect factory lacked upstream typing | FAIL: mypy1 error in40 files; make exit2 | Narrowed documented callable type; final full quality exit0. [failure](evidence/m02/final-quality-fixed.log) |

Review also fixed excessive polygon query extent, fabricated zero graph counts
in budget responses, aggregate geometry loading risk, and a CSS selector that
stretched a preview icon. These are validated by endpoint/DB/browser regressions;
no OOM or secret exposure was observed or invented. Restricted dependency-cache/
network attempts and cache cleanup are recorded in
[implementation notes](evidence/m02/implementation-notes.txt).
Frozen0003 SQL resource files received trailing-whitespace-only normalization;
SQL token sequences are unchanged. Integrity changes use separate0004.

## Browser, frontend and regression scope

Fifteen Chromium cases passed at desktop1440×1000, tablet820×1180 and
mobile390×844. Six cases use the real deployed M01/M02 backend: health, actual
queued diagnostics/SUMO, region geometry, counts, validation, provenance and
navigation. Nine cases explicitly mock UI empty/error/retry states; they are not
reported as real dependency outages. Actual outages are independently tested by
failure_smoke.py. Preview icon/geometry sizing and M02 milestone labels are
asserted; no overflow or console/page errors were observed. Screenshots:
[desktop](evidence/m02/geospatial-desktop.png),
[tablet](evidence/m02/geospatial-tablet.png),
[mobile](evidence/m02/geospatial-mobile.png).

## Security, reproducibility and limitations

All host ports remain loopback; Redis remains private. Only region creation
mutates data and requires a server-only development token with constant-time
comparison; blank configuration disables writes. It is not an identity/role
system. Public geometry calculations and sanitized reads are intentional.
No token reaches browser or worker. Shared deployment still requires actual
identity/authorization, least-privilege DB roles, TLS, secrets and tested backups.

Requests, coordinates, extent, radius, pagination and aggregate graph work are
bounded. Direct SQL constraints, RESTRICT foreign keys and locked immutable
publication protect persistence. API errors omit private raw errors/inputs.
Original provenance JSON/artifact locations are private; public URLs lose
credentials/local addresses/query/fragment, and no source URLs are fetched.
Audit key filtering is a defensive rule, not semantic secret detection under
arbitrary innocent keys; trusted writers must avoid all credentials.

Local API/migration roles remain privileged; Redis has no password on the private
network; M01 diagnostic jobs remain at-most-once; no global rate limit/per-user
quota, production load test or native-package advisory scan was performed.
Digest/uv/npm pins are retained; transitive apt repositories remain live, so
byte-identical permanent system builds are not claimed. The public provenance
license is project-specific, not a declaration that third-party data is usable.

## Git delivery and next milestone

The final diff summary and changed-file inventory are recorded under
`docs/evidence/m02/git-diff-stat.txt` and `git-changed-files.txt` before commit.
Candidate/staged secret scans, whitespace checks and all six hooks passed before
the focused local commit. Exact executed commands are in commands.jsonl and the
Git logs below; current commit identity is reported by `git log -1` and the final
response. The implementation commit exited0 with all six hooks passing again;
`git status --porcelain=v1` then returned empty. The final documentation and
these execution records are included in the same focused local commit.
No remote push is authorized or performed.

M03 readiness: the tested local persistence/API foundation is ready for a
separately authorized next milestone. A future real import still needs an
explicit licensed/versioned source, accurate extraction/conversion and new
verification; M02 synthetic topology is not sufficient evidence for those.
M03 implementation has not begun.


Final pre-commit commands (all exit0): `git diff --check`,
`git diff --cached --check`,
`uv run --locked pre-commit run --all-files`, and
`uv run --locked python /private/tmp/earthmind-m02-results/git_gates.py --staged`.
[Hooks](evidence/m02/hooks.log), [staged scan](evidence/m02/staged-secret-check.log),
[whitespace](evidence/m02/staged-whitespace.log),
[candidate scan](evidence/m02/candidate-secret-check.log). The retained scan source
is [git_gates.py.txt](evidence/m02/git_gates.py.txt); actual configured values
were read privately from ignored `.env` and never printed.


The final staged scan after adding the report/diff records checked135 files,
2 configured secret values, no matches/keys/caches/archives/>2MB artifacts.
`git commit -m 'feat(earthmind): implement geospatial persistence and spatial APIs'`
actually exited0; [commit output](evidence/m02/git-commit.log). A clean status
was observed immediately afterwards. [Git gate record](evidence/m02/git-gates.json).
Final identity is available from `git log -1` after the documentation amendment;
no remote push or M03 implementation occurred.
