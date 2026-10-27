# M03 verification — 2026-10-27

This is the actual M03 implementation/audit record for `/Users/redmug/EARTHMIND`,
branch `codex/m03-digital-twin`, extending independently inspected clean M02
commit `60df3cd43e424d004c2dae20858d472430f3b938`. Times use Asia/Dubai (UTC+04).
[Preserved M02 report](verification-m02.md), [M01 report](verification-m01.md)
and their historical evidence remain unchanged. No M04 work or remote push is
included. The main database and user environment were preserved.

## Environment, scope and independently verified baseline

Read AGENTS, tree/Git status, previous reports, frontend/config/locks, API
conventions, spatial models/fixtures/endpoints and Compose before changing source.
Actual baseline `make lint typecheck test build smoke` and 38 live PostGIS tests
passed; [baseline](evidence/m03/baseline.log),
[database](evidence/m03/baseline-database.log). The baseline had 67 Python / 28
frontend tests. The final diff does not change the backend, frozen migrations,
contracts, worker, uv.lock or M01/M02 evidence. No competing ORM/engine/database
was added. The same 14 M02 spatial endpoints and published synthetic fixture are
reused; no new schema migration was needed. The inspection script now accepts an explicit
output path, so M03 reruns preserve historical M02 measurement evidence.

Host: macOS26.5.1 ARM64, Node26.0.0/npm11.12.1/uv0.11.12, Python3.12.13.
Docker29.9.1/Compose5.6.0 native linux/aarch64, web Node22.23.4, Python3.12.15,
PostgreSQL17.11/PostGIS3.6.4 and SUMO1.15.0. All final service images are ARM64.
M01's digest-pinned custom native PostGIS build is preserved because the chosen
upstream image lacks ARM64. No AMD64 emulation or Python3.14 assumption is used.
Services remain loopback web3000/API8000/DB**5434**, Redis unpublished.

Next16.4.3/React19.3.1/strict TypeScript/Tailwind/TanStack Query/Zod/Lucide remain
the existing stack. New CesiumJS**1.146.0** is exact-locked; registry compatibility
requires Node>=22. It resolves engine26.4.0/widgets16.3.0/core0.1.0. Pinned
patch-package8.0.1 applies the documented three-statement lifecycle repair.
Clean npm installs, build-time exact-source SHA guard, native Docker production
build and actual browser execution verify compatibility. React Hook Form is not
added: selectors/buttons perform read-only inspection and need no form workflow.

## Acceptance — final independently executable result

| Requirement | Status | Evidence / limit |
| --- | --- | --- |
| Preserve M01/M02 tests and deployed services | PASS | Baseline plus final67 Python units,38 database cases, original browser checks, queue/SUMO and outage recovery |
| Browser-only real Cesium globe; no SSR errors | PASS | Lazy ssr:false import, correct base URL, native WebGL2 browser tests and production build |
| Static Workers/ThirdParty/Assets/Widgets and notices | PASS | Exact-package copy; real worker traffic; HTTP/MIME/SHA comparisons for JS/WASM/XML/CSS/license |
| Dubai overview, Downtown, Business Bay, region/road focus | PASS | Actual camera pose/settlement tests, reset/zoom/top-down/perspective; no simulation needed |
| Real stored region boundary/fill/outline/centroid | PASS | Existing GeoJSON, holes/coordinate validation, backend metric area/bounds |
| PostGIS roads/intersections and network version selection | PASS | Existing API/bbox/pagination;6 nodes / 8 roads plus300-road QA profile; stale responses guarded |
| Typed bounded cancellable camera-based requests | PASS | Zod,100-page/500-feature/25k-position caps, viewport debounce, extent clipping, abort propagation, inactive cache eviction |
| Deterministic native picking and correct inspector | PASS | Actual canvas click; selected ID/UUID/lane/length match API; intersection>road>building priority |
| Working available map controls | PASS | Native scene visibility for region/roads/nodes/imagery/highlight/centroid; camera controls; unavailable providers explicitly disabled |
| Optional licensed ion buildings, imagery and terrain rendering | BLOCKED | No configured public token/entitlement; no claim of building coverage, live building picks or enabled-provider attribution verification |
| Missing token handling and lawful local fallback | PASS | Packaged Natural Earth public-domain imagery/ellipsoid, no external default requests, usable overlays/cameras |
| Attribution and data truthfulness | PASS | Visible native Cesium/Natural Earth credits and software notices; synthetic labels/actual source license; no traffic/AI claims |
| Responsive desktop/tablet/mobile, keyboard controls | PASS | Three Chromium viewports, mobile selected-feature bottom sheet, tablet drawer, accessible lists; no horizontal overflow |
| WebGL unavailable and error/empty/retry handling | PASS | Actual separate WebGL-disabled browser; real metadata remains usable; isolated UI/provider/query error tests |
| Viewer lifecycle/Strict Mode/resource cleanup | PASS |3 actual dev remounts,9 functional lifecycle mount cycles; public context-loss checks;30-cycle memory/DOM/listener profile |
| Responsive selection for hundreds of features | PASS | Actual300-road / 300-node ready scene;30 selections38–853 ms in this environment |
| No sustained retained DOM/listener growth in measured run | PASS | All 30 post-unmount samples 2142 DOM nodes / 458 listeners; last 10 heap variation 294220 bytes; bounded evidence, not indefinite proof |
| Lint/types/unit tests/production build/locked setup | PASS | Exact commands/output below, clean npm patch installs and native build |
| Docker, migrations, worker and SUMO regression | PASS | Native startup; fresh/repeated migration checks; actual2 vehicle / 25 step runtime; final healthy services |
| Security/licensing/reproducibility review | PASS | Allowlisted public config/proxy, scoped token policy, text rendering, dependency/context/Git scans; development limitations below |
| Required documentation and architecture decisions | PASS | Cesium,3D scene,frontend,performance,security,README,AGENTS,ADRs0010/0011 and evidence |
| Physical Apple GPU/Metal FPS, GPU memory, process RSS/long-run production load | NOT RUN | Chromium uses SwiftShader; no numerical hardware FPS or universal leak-free guarantee |
| Hosted CI execution | NOT RUN | YAML checked locally only; no push/hosted run authorized |
| Working-tree/staged review, secret/whitespace scans and hooks | PASS | Actual candidate/staged scans, source/staged whitespace and all 6 hooks passed; outputs below |
| Focused local commit and clean status | PASS | Requested commit actually exited0 with 6 hooks passing; empty status observed, then evidence included by documentation amendment |

All independently executable M03 implementation requirements are implemented.
Optional-provider acceptance remains explicitly BLOCKED as permitted by the
specification. A provider test double is not substituted for real licensed access.

## Exact commands and actual output

Commands ran in the target repository unless the complete record specifies the
writable temporary staging tree. [commands.jsonl](evidence/m03/commands.jsonl)
contains actual argv, cwd, start time, duration, exit and output filename,
including failed/supplementary iterations. [runner](evidence/m03/run_check.py.txt)
records outputs without inventing statuses. Some diagnostics were manual;
retained sources/JSON identify their limited scope. Normal pytest deselects live
integration; the actual 38 cases were run separately. Expected downgrade-refusal
child errors belong to a checked overall successful rehearsal.

| Dubai time | Exact command | Exit | Status | Actual result |
| --- | --- | --- | --- | --- |
| 01:46:35 | `make lint typecheck test build smoke` | 0 | PASS | Independent M01/M02 lint/types/unit/build and deployed queue/SUMO/PostGIS smoke. [output](evidence/m03/baseline.log) |
| 01:49:11 | `uv run --locked python scripts/database_checks.py` | 0 | PASS | 38 actual PostGIS integration tests passed before modifications. [output](evidence/m03/baseline-database.log) |
| 02:54:26 | `make setup` | 0 | PASS | Preserved existing config; locked uv/npm install; exact SDK patch applied; hooks installed. [output](evidence/m03/final-setup.log) |
| 02:43:38 | `npm ci` | 0 | PASS | Clean staged npm install applies the pinned engine patch. [output](evidence/m03/patched-clean-install.log) |
| 02:44:35 | `npm ci` | 0 | PASS | Clean target npm install applies the same pinned engine patch. [output](evidence/m03/patched-target-install.log) |
| 02:57:23 | `make lint typecheck test build` | 0 | PASS | 67 Python units; 81 frontend tests; strict mypy 42 files, tsc, Ruff, ESLint and standalone build passed after final output-path fix. [output](evidence/m03/final-quality-complete.log) |
| 02:48:09 | `env CITY_DIAGNOSTICS_ENABLED=true make dev` | 0 | PASS | Native ARM64 images built/started, migration head0004, seed created=false, actual API/SUMO/spatial/asset smokes passed. [output](evidence/m03/final-dev.log) |
| 02:49:37 | `uv run --locked python scripts/database_checks.py` | 0 | PASS | 38 selected actual database tests passed:30 persistence, 7 spatial API, 1 M01 session integration; 54 deselected. [output](evidence/m03/final-db-regression.log) |
| 02:01:50 | `uv run --locked python scripts/verify_migrations.py` | 0 | PASS | Fresh isolated M01->M02 upgrade, sentinel retention, repeat/check, empty downgrade/re-upgrade, populated destructive downgrade refusal. [output](evidence/m03/migration-regression.log) |
| 02:49:34 | `python3 /private/tmp/earthmind-m03-results/verify-development.py` | 0 | PASS | Actual Next development/Strict Mode server at3300;3 navigation/remount cycles, one live canvas/zero after unmount, workers loaded, no page errors; server stopped. [output](evidence/m03/final-development.log) |
| 02:52:37 | `npm run test:browser` | 0 | PASS | 24 Chromium cases passed across desktop/tablet/mobile with no DB/outage checks running concurrently. [output](evidence/m03/final-browser-isolated.log) |
| 02:46:03 | `uv run --locked python scripts/verify_city_performance.py` | 0 | PASS | 30 actual 300-road mount/selection/unmount cycles; final stability gates passed and owned QA rows cleaned. [output](evidence/m03/performance-patched.log) |
| 02:53:47 | `uv run --locked python scripts/failure_smoke.py` | 0 | PASS | Stopped worker, Redis and DB separately; readiness503/liveness200 and recovery verified; services restored. [output](evidence/m03/failure-recovery.log) |
| 02:54:01 | `make migrate` | 0 | PASS | Repeated upgrade succeeds at0004_run_state_integrity; existing data retained. [output](evidence/m03/final-migrate.log) |
| 02:54:03 | `make smoke` | 0 | PASS | Actual web/API/PostGIS/queue/SUMO and M02 spatial smoke plus byte-matched Cesium assets/config. [output](evidence/m03/final-smoke.log) |
| 02:54:04 | `uv run --locked python scripts/check_architecture.py` | 0 | PASS | Native engine aarch64; every service image linux/arm64, no AMD64 emulation. [output](evidence/m03/native-architecture.log) |
| 02:57:22 | `uv run --locked python scripts/inspect_geospatial_database.py --output docs/evidence/m03/postgis-inspection.json` | 0 | PASS | Actual schema/spatial columns and indexed bbox/geography plans retained under M03; historical M02 evidence preserved. [output](evidence/m03/final-inspection-output.log) |
| 02:54:05 | `uv run --locked python infra/verification/check_build_context.py` | 0 | PASS | Five synthetic environment fixtures excluded from real Docker contexts. [output](evidence/m03/context-isolation.log) |
| 02:54:05 | `docker compose ps --all` | 0 | PASS | Five long-running services healthy; migration exited0; DB loopback5434; Redis unpublished. [output](evidence/m03/final-services.log) |
| 02:54:42 | `uv run --locked python /private/tmp/earthmind-m03-results/verify-final-data.py` | 0 | PASS | Zero QA region/network/source records remain; original M02 fixture retains6 nodes / 8 roads. [output](evidence/m03/final-data.log) |
| 02:49:36 | `npm audit --json` | 0 | PASS | Zero known npm vulnerabilities including the new Cesium/patch tooling. [output](evidence/m03/final-advisories.log) |
| 02:54:01 | `Pinned pip-audit argv below` | 0 | PASS | 64 installed distributions inventoried:61 public distributions audited without known findings;3 local packages skipped. [output](evidence/m03/python-advisories.log) |
| 02:14:01 | `Inline YAML inspection argv in commands.jsonl` | 0 | PASS | Workflow parsed locally; native ARM runner, read-only permissions and diagnostics/performance sequencing checked. [output](evidence/m03/ci-syntax.log) |

Python advisory command (exit0; no dependency edits):

```sh
UV_CACHE_DIR=/private/tmp/earthmind-m03-uv-cache uvx --python 3.12 --from pip-audit==2.10.1 pip-audit --path /Users/redmug/EARTHMIND/.venv/lib/python3.12/site-packages --format json --progress-spinner off --timeout 15 --cache-dir /private/tmp/earthmind-m03-pip-audit-cache
```

The 3 unpublished EARTHMIND packages are skipped by the public advisory service,
not silently audited. Native operating-system packages/application logic are not
covered by npm/pip advisory scans. An existing transitive ESLint9.39.5 reports an upstream
support deprecation during install; this is retained and has no reported advisory
finding in the actual scan. Transitive apt repositories remain live, so permanent
byte-identical system-image reproduction is not claimed.

## Browser and visual evidence

Final isolated result: **24 passed** in 63.83 s overall command time. Chromium
viewports: desktop1440×1000, tablet820×1180, mobile390×844. Fifteen cases use real
services:9 M03 (native scene/canvas picking, lifecycle and actual WebGL-disabled
fallback across 3 viewports) plus 6 existing M01/M02 deployment checks. The other 9
legacy cases explicitly mock isolated empty/error/retry UI states; they are not
claimed as actual service outages. Separate failure_smoke.py verifies real
worker/Redis/database outages and recovery.

The native canvas pick uses a plain projected diagnostic coordinate, never a
native Viewer exposed globally. The inspector ID/lanes/rounded length is compared
with the actual network API. Real worker requests resolve, no forbidden external
default requests occur, layer visibility changes real primitives, credit/legend
rectangles do not overlap, and console/page error arrays are empty in the final
isolated run. Picking diagnostics are explicitly opt-in; default remains false.

Actual screenshots: [City desktop](evidence/m03/city-desktop.png),
[tablet](evidence/m03/city-tablet.png), [mobile](evidence/m03/city-mobile.png),
[no-WebGL fallback](evidence/m03/webgl-fallback-desktop.png),
[300-road profile](evidence/m03/benchmark-300-roads.png).
The close-range packaged Natural Earth texture is intentionally low-resolution;
these are screenshots of synthetic geographic overlays, not rendered real Dubai
building coverage. View the JSON screenshots/report alongside their actual tests.

## Architecture, data and lifecycle decisions

React owns controls, query state and plain typed feature selection. A dedicated
mount-scoped controller owns Viewer/native camera/resources; Cesium modules load
only after setting `/cesium/` as the base URL. Rendering uses batched ground
polylines, point collections with zoom visibility, validated region entities and
separate highlights. Request-render mode and stable geometry updates avoid
rebuilding the network for ordinary React changes. API/GeoJSON remains EPSG4326,
longitude/latitude; area comes from PostGIS geography, not degree arithmetic.

The M02 fixture is unchanged: region8d31afa3-5d52-59b5-a8bc-691b5867dfcb,
network22f68ce8-9247-5425-8342-827d86517ead, synthetic-v1,6 nodes / 8 edges and
1.3398134937911033 km². A stored signal flag is synthetic metadata, not an inferred
or verified Dubai traffic light. All 300-road benchmark data is separately marked
synthetic and removed by owned UUIDs in finally blocks. A final SQL check finds
zero QA source/region/network rows and the original6/8 fixture intact.

Camera motion is measured through public position/direction/up/viewport samples;
350 ms of actual stability precedes the separate350 ms spatial-query debounce.
Mode changes orbit the picked ground center instead of rotating at the displaced
camera position. Query budgets are per layer:500 features/25k positions,100 per page,
4 MiB streaming client response and8 s per HTTP request; bbox clipped to one degree
and region. This is not an8 s whole multi-page transaction deadline or a 4 MiB
streaming Next upstream cap. The existing proxy/backend page/vertex/deadline
bounds remain the server controls. Inactive viewport data has gcTime0.

The observed terrain-grid cache retained destroyed buffers/WebGL canvases.
A version-locked WeakMap patch corrects the 3 affected cache statements at install.
Build/dev checks the exact patched SHA256
`8753d08f6374a2a3e1d1e836c15bcdf4cd8b77d5517236048b5817b91f12ce1c`.
Public input-handler destruction, owned credit stylesheet removal, Viewer
teardown and optional owned context loss complete application cleanup. No live
private-cache mutation or DOM.disable workaround is used. See
[ADR0010](decisions/0010-cesium-viewer.md),
[ADR0011](decisions/0011-cesium-lifecycle-patch.md) and
[performance](performance.md). SDK upgrades must revisit the patch and rerun
these regressions; this maintenance obligation is explicit.

## Measured performance and scope

Final actual 30-cycle run:300 roads and300 intersections ready per mount; view-load
1147–4376 ms (median 1694.5 ms); feature-selection observation38–853 ms
(median 529 ms). DOM2142/listeners458 remain constant across all 30 post-unmount
samples. Last 10collectedJSheap25,508,980–25,803,200bytes, variation294,220bytes
(0.281 MiB); delayed final 24,813,632 bytes. No page errors. These timings include
Playwright actionability/interface work and are not isolated GPU latency.

Chromium reports WebGL2 via ANGLE/Vulkan SwiftShader software rendering. No
physical Apple GPU FPS is claimed. JS heap excludes GPU allocations and process
RSS;30-cycles/late-run gates establish bounded stability, not indefinite flat
memory. Tracing was disabled for performance because controlled A/B tests showed
instrumentation retention. Functional tests retain failure traces separately.
The original fixed thresholds were not loosened: after 20 warm-ups, last 10heap
variation<1 MiB, DOM variation<25, listener variation<10, all selections<5 s.

## Earlier failures retained; corrective runs are separate

| Actual failed/insufficient observation | Status | Repair / later evidence |
| --- | --- | --- |
| Initial scoped data TypeScript command missing Node type roots | FAIL exit2 | Corrected isolated tsconfig invocation; final strict repo checks pass; city-data-types.log |
| First production build compiled then failed optional pickProbe TS2412 | FAIL exit1 | Narrowed return contract; production-build-fixed and final native builds pass |
| First native pick after top-down selected no road | FAIL exit1 | Actual camera pivot corrected; first screenshot/report retained; final native pick matches API |
| Camera stayed moving although pose/8roads/6nodes had settled | FAIL exit1 | Read-only pose observations retained; public-pose settlement replaces unreliable moveEnd; final browser checks pass |
| First performance command discovered no tests | FAIL exit1 | Explicit performance testMatch added; owned rows cleaned; later actual cases run |
|5-cycle functional and15-cycle extension observed heap warm-up | NOT sufficient for stability | Kept raw arrays and extended to30-cycles; no fabricated memory PASS for these samples |
| First30-cycle profile retained55 DOM / 14 listeners per cycle | FAIL exit1 | Public handler teardown reduced listener retention; thresholds unchanged |
| Handler-only30-cycle profile still retained55 DOM / 8 listeners | FAIL exit1 | Trace control separated instrumentation; owned styles and actual terrain-cache retainer repaired |
| Final mixed verification captured1 M02 region-proxy HTTP503 | FAIL exit1;23/24 passed | Occurred during live DB integration/development checks; cause not conclusively established. Full isolated rerun24/24 passed; error assertions unchanged. Run these suites serially. |

See the individual logs/reports in evidence/m03, especially
[first build](evidence/m03/first-production-build.log),
[first browser](evidence/m03/browser-desktop-first.log),
[settlement failure](evidence/m03/browser-camera-fixed.log),
[first30-cycle failure](evidence/m03/performance-thirty-cycles.log),
[handler-only failure](evidence/m03/performance-listener-fix.log),
[final mixed-run failure](evidence/m03/final-browser.log),
[isolated success](evidence/m03/final-browser-isolated.log).
Early native floating-point unit comparison was corrected to a tolerance;
its failing terminal output was not archived and is not invented. Final unit
output is retained. The existing inspection script initially overwrote M02 measurement output during
a successful check. That generated change was archived under M03 and the M02
file restored byte-for-byte from baseline. The new --output option, docs and CI
now target M03; the final command was rerun successfully.

Temporary full heap snapshots and trace archives are not
committed; filtered retainer paths, trace controls and exact logs are retained.

## Security, licensing and unresolved boundaries

The public config endpoint returns only ionPublicToken/imageryAssetId/
terrainAssetId/diagnosticsEnabled. Only explicitly named browser-public token
configuration is read; private GIS/database/M02 write tokens are not exposed.
Public tokens must be read-only and asset/origin-scoped. The actual configuration
has no token. No default SDK token was borrowed and no credentials were invented.
Optional providers use supported SDK APIs with cancellation/generation checks and
loading/error/destruction handling. Their actual licensed tile rendering and
provider-specific attribution remain BLOCKED until authorized access exists.

Natural Earth is public domain and its credit remains visible. Cesium software
and third-party notices are copied. OSM/ion terms/attribution are documented in
[Cesium integration](cesium-integration.md), with official references. No tile
scraping/bulk download, unrestricted server proxy or raw metadata HTML is added.
Native building picks show only bounded available properties and namespace-aware
stable identifiers; no missing name/height is invented.

Existing loopback development security limits remain: no shared-user identity,
privileged local DB role, private-network Redis without password, at-most-once
M01 diagnostics, no global rate quotas, production TLS / managed secrets/backups or
native OS advisory audit. A4 MiB browser streaming budget is not a complete upstream
server-memory limit. Local review and scans cover their stated scope, not a
production security certification. Real city imports, simulations, telemetry and
AI are absent as required; M03 is geographic visualization only.

## Git delivery

Actual `git diff --check`, `git diff --cached --check`, and
`uv run --locked pre-commit run --all-files` exited0. All 6 hooks passed. The
commit-eligible scan checked519 files; the first actual staged scan checked200
blobs against2 configured working secret values and found no matches, private
keys, generated caches/archives or files over 2 MB. No secret values were printed.
The final post-document scan is recorded separately.

[Hooks](evidence/m03/hooks.log), [staged scan](evidence/m03/staged-secret-check.log),
[source whitespace](evidence/m03/source-whitespace.log),
[staged whitespace](evidence/m03/staged-whitespace.log),
[candidate scan](evidence/m03/candidate-secret-check.log),
[scan source](evidence/m03/git_gates.py.txt). The complete staged diff was reviewed;
M01/M02 evidence, backend/contracts/worker and frozen migrations remain unchanged.
Raw evidence is deliberately retained, while generated Cesium assets, installed
packages, full heap snapshots and trace archives stay outside the commit. The
patch's mandatory unified-diff context spaces have a narrow whitespace attribute.

The pre-commit diff snapshot and changed-file inventory are retained under
`docs/evidence/m03/git-diff-stat.txt` and `git-changed-files.txt`. Actual `git commit -m 'feat(earthmind): implement immersive Dubai 3D digital twin viewer'`
exited0 with all 6 hooks passing again. `git status --porcelain=v1` then returned
empty. The post-document staged scan checked 207 blobs against the 2 configured
secrets with no matches/keys/caches/oversized files.
[Commit output](evidence/m03/git-commit.log),
[final staged scan](evidence/m03/final-staged-secret-check.log),
[gate record](evidence/m03/git-gates.json). The actual execution log and this
status update are included through a documentation-only amendment of that same
focused commit; the final identity comes from `git log -1` after amendment.
No remote push has occurred. Final commit identity is reported by `git log -1`
and the delivery response rather than a self-referential hash inside the commit.

M04 readiness: the independently tested local visualization foundation is ready
for separately authorized next-milestone planning, subject to provider access and
explicit production/performance limits above. M04 has not begun.
