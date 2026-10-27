# Cesium ion integration verification — 2026-10-27

Workspace `/Users/redmug/EARTHMIND`, branch `codex/m035-digital-twin`, based on
`0dc7493`. This is the owner's narrowed Cesium integration request. The earlier
geography recovery and diagnosis evidence remains historical and untouched.
No geographic import, schema change, traffic AI, new simulation functionality or
remote push is included. The original source extract and named volumes remain.

## Delivered and inspected

| Requirement | Implementation / evidence |
| --- | --- |
| Next public token convention | `apps/web/lib/city/config.ts`, `app/api/city/config/route.ts`, `compose.yaml`, `.env.example`: canonical `NEXT_PUBLIC_CESIUM_ION_TOKEN`, safe legacy alias, safe conflict rejection, five-field runtime allowlist, no-store response. |
| Actual aerial imagery | `components/city/runtime/providers.ts`: public `IonImageryProvider.fromAssetId(2,{accessToken})`, the provider underlying SDK World Imagery AERIAL. Explicit token options also avoid stale endpoint-cache identity after rotation. |
| Actual streamed buildings | Supported `createOsmBuildingsAsync()` / asset96188, bounded GPU cache, nonempty visible content and rendered-frame readiness. No mock buildings substituted. |
| Presentation and geography | Same controller/Viewer; retained PostGIS coordinates and feature IDs, natural reference daylight, cast-only building shadows, ellipsoid default, optional terrain control, eased camera flights. |
| Working modes | `CityExplorer.tsx`, `VisualizationModeSwitch.tsx`, `runtime/scene-controller.ts`, `runtime/layers.ts`, `runtime/camera.ts`: Engineering and Realistic use the same Viewer, camera and selection; synthetic development scopes remain isolated. |
| Honest errors | `lib/city/provider-policy.ts`: safe missing/401/403/404/410/429 explanations; errors visible beside the map, no raw credential-bearing errors displayed/logged by the app. An explicit failed asset does not trigger silent asset cycling. |
| Attribution / usability | Exact provider credit HTML promoted inline through public APIs; OSM road credit independent of local context; bounded reuse and cleanup. Notices outside the canvas; existing inspector, layer controls and branding retained. |
| Reproducibility / evidence | Locked dependencies unchanged; current setup guide and ADR0014; browser traces disabled, sanitized paths/status/MIME evidence and actual screenshots retained. |

Engineering intentionally remains the initial mode. Select **Realistic city**
after recreating web with the ignored local environment. See the exact
[configuration/restart guide](cesium-ion-integration.md) and
[architecture decision](decisions/0014-cesium-ion-modes.md).

## Confirmed provider access

The configured token value was placed only in the ignored local `.env` with mode
0600 and was never printed or committed. Runtime checks report only presence.
The canonical variable is nonempty and the legacy alias empty. Actual endpoint
requests used the local application's Referer; no account-management mutation
was performed.

| Asset / actual request | Result | Meaning |
| --- | --- | --- |
| `/v1/assets/3812/endpoint` | HTTP404 | Historical configured imagery asset unavailable to this request; retained as an actual negative browser check. |
| `/v1/assets/2/endpoint` | HTTP200, IMAGERY/BING | Installed SDK World Imagery AERIAL asset; visible aerial tiles were additionally verified in Chromium. |
| `/v1/assets/96188/endpoint` | HTTP200, 3DTILES | Actual nonempty building content was additionally downloaded and rendered in Chromium. |
| `/v1/assets/1/endpoint` | HTTP200, TERRAIN | Endpoint authorization only; optional World Terrain rendering is not claimed from this probe. Default remains WGS84 ellipsoid. |

[Sanitized endpoint probe](evidence/cesium-ion/ion-endpoint-access.json).
Endpoint access alone was not accepted as rendering proof. No default evaluation
token, alternate account, static map image, guessed height or fabricated terrain
was used. SDK1.146.0 was checked against installed implementation/type declarations.
The old asset3812 was replaced as the default in both server configuration and
Compose; an explicitly configured unavailable asset still fails visibly.

## Browser observations and actual captures

The completed desktop live check before the final cache-key correction observed
59 successful aerial image responses and16 successful building-content responses,
all provider HTTP statuses200, zero console/page errors, and only three canceled
same-origin spatial GETs (`net::ERR_ABORTED`). Its Viewer instance stayed1 and
camera pose was unchanged through Engineering → Realistic → Engineering:
longitude55.27440000000001, latitude25.18167255980374, altitude2457.689295872061m,
heading359.9999999999868°, pitch−55.015470203763115°. The ground focus remained
[55.27440000003018,25.197199999991817], Downtown Dubai. A native-picked actual road
remained selected;402 local explicit-height models were restored in Engineering.
Final release observations below supersede this intermediate count where noted.

The actual screenshots show aerial imagery, the recognizable Burj Khalifa area,
streamed untextured OSM buildings, and georeferenced road overlays. This is not a
photogrammetric city mesh, surveyed alignment assessment or assertion of current
imagery capture dates. Visual comparison confirms no coordinate relocation or
opaque region fill over the basemap. Credit lines include the actual Microsoft,
Maxar, CNES/Airbus, Mapbox, Bing and OpenStreetMap attribution and the account-plan
message. Screenshots are browser captures, not generated illustrations.

## Failures retained and corrected

- Initial desktop live run: exit1, one failed/one passed. Cesium downloaded JPEGs
  through fetch/ImageBitmap, so a test limited to resourceType=image incorrectly
  counted zero imagery tiles. Actual imagery/buildings were visible. Classification
  now uses image MIME types independently of transport type; the next desktop run
  passed both checks. The failed log/JSON is archived. Its original screenshot remains locally under `/private/tmp/earthmind-m035-results/ion-desktop/test-results/`; it predates inline imagery attribution and is not redistributed in Git.
- First full51-case suite: exit1,47passed/2failed/2skipped. Desktop/tablet source-
  backed road-picking checks read probe ID, bounds and coordinates in separate
  browser calls after a camera transition. A viewport update removed the probe
  between reads, producing x=0 from Number(null). They now require one atomic
  native-ready snapshot with a valid on-canvas road probe. All original actual
  picked-feature/API metadata assertions remain. Mobile's equivalent check passed
  in the first run; no failure was relabeled PASS.
- The first actual realistic capture showed shadow-map depth-bias checkerboarding
  on building faces. Cast-only building shadows preserve globe shadows while
  removing building self-shadow artifacts; the next actual capture was inspected.
- A focused staging lint invocation from repository root (`npx eslint` on the
  three browser files) exited2 because that invocation resolved ESLint9.39.5 and
  found no root ESLint config. The canonical workspace lint command exited0;
  final make lint also uses the locked workspace toolchain. This was a command-
  location error, not a hidden source validation result.
- Review caught the stale Compose imagery default3812 and the World Imagery
  helper's tokenless endpoint-cache key. Compose now agrees with asset2; the
  underlying public provider receives the token explicitly. Terrain guidance now
  names the actual Realistic City control instead of an overridden legacy setting.

## Limits and remaining configuration responsibilities

The current provider credit says **Upgrade for commercial use**. Successful tile
requests do not establish commercial entitlement; the account owner must retain
an appropriate plan/content license. Required asset read access worked, but the
application cannot certify the token's complete account scopes/origin rules;
configure assets:read with only required assets and permitted origins as described
in the setup guide. No account/admin/upload credential is appropriate here.
[Cesium token guidance](https://cesium.com/learn/ion/cesium-ion-access-tokens/),
[content/attribution guidance](https://cesium.com/learn/ion/content-usage-and-attribution-guide/).

Building coverage, source heights and imagery dates depend on providers. Local
context models only explicit source heights. The study network remains2364roads
and1560nodes; the synthetic fixture remains8roads/6nodes. Existing per-viewport
500-feature/25000-position safeguards remain. This bounded integration does not
claim the superseded broader spatial LOD/cap-removal/performance milestone.
No indefinite leak-free, mobile hardware FPS, survey accuracy or complete-city
coverage guarantee is inferred from these Chromium checks. Error policies for
401/403/410/429 are unit-tested; the actual negative provider request here is404.
The stack retains its trusted local-development deployment limits.

## Final release acceptance

Final source passed `make lint typecheck test build`: **116 Python tests passed /
38 integration deselected;103 TypeScript tests passed /0failed**, Ruff, locked
uv resolution/contracts, ESLint, strict mypy48files and TypeScript. The production
Next build succeeded. Separate real PostGIS/API integration: **38passed /
85deselected**. Existing revision remains0004_run_state_integrity. Fresh/repeated
migration/schema-check/seed/downgrade-guard rehearsal passed in its isolated
project, which was removed afterwards; main named volumes were not reset.

Final complete Chromium suite: **49passed /2skipped /0failed, exit0,432.654s**.
The two skips avoid repeating the same legacy-asset negative case on tablet/mobile;
it executes once on desktop. Live imagery/buildings execute in all three viewports.
Existing isolated UI empty/error and controlled missing-token/timing/context-error
cases remain explicitly controlled tests, not evidence of working hosted tiles.
No test assertion was weakened to accept missing native picks or source metadata.

| Viewport | Actual image responses HTTP200 | Actual building content HTTP200 | Provider endpoints HTTP200 | Console/page errors | Same Viewer / camera pose / selection |
| --- | --- | --- | --- | --- | --- |
| desktop | 59 | 16 | 2 | 0 /0 | verified |
| tablet | 51 | 14 | 2 | 0 /0 | verified |
| mobile | 45 | 12 | 2 | 0 /0 | verified |

Counts are observed responses in each bounded browser session, not unique tiles,
coverage estimates or performance benchmarks. Other successful provider metadata
responses were also observed; no normal-session provider HTTP failure or transport
failure occurred. Canceled same-origin bounded spatial GETs remain recorded as
`net::ERR_ABORTED` (desktop2/tablet6/mobile3), not hidden as network successes.
The explicit legacy3812 case independently received actual HTTP404 and verified
the visible asset-unavailable message while stored roads remained available.
401/403/410/429 policies were unit-tested, not falsely reported as live requests.

Required provider credit labels were independently checked against actual endpoint
metadata, retaining only labels/booleans: Cesium ion and Upgrade for commercial
use for both assets, plus OpenStreetMap contributors for buildings. The static
OSM road credit keeps that attribution inline even when local context is removed.
Actual imagery tile credits are additional visible Microsoft/Maxar/CNES/Airbus
credits. [Sanitized credit audit](evidence/cesium-ion/provider-credits.json).

Actual final captures:

- Realistic: [desktop](evidence/cesium-ion/browser-release/ion-realistic-desktop.png), [tablet](evidence/cesium-ion/browser-release/ion-realistic-tablet.png), [mobile](evidence/cesium-ion/browser-release/ion-realistic-mobile.png).
- Engineering: [desktop](evidence/cesium-ion/browser-release/ion-engineering-desktop.png), [tablet](evidence/cesium-ion/browser-release/ion-engineering-tablet.png), [mobile](evidence/cesium-ion/browser-release/ion-engineering-mobile.png).
- [Mobile inspector with visible provider credits](evidence/cesium-ion/browser-release/ion-realistic-inspector-mobile.png) and [actual legacy-asset error](evidence/cesium-ion/browser-release/ion-legacy-asset-error-desktop.png).

`make smoke` passed real web→API→PostGIS→Redis→worker connectivity, actual existing
SUMO fixture, M02 geometry/provenance/write-gate checks and six deployed Cesium
asset byte/MIME/hash checks, including worker JS/WASM/Natural Earth/CSS/license.
Read-only verification reconfirmed2364realroads/1560nodes,402localheightmodels,
unchanged source/context hashes and8/6syntheticfixture. Actual spatial index
inspection used the expected geometry/geography GiST indexes. Five long-running
services remain healthy, migration exited0, loopback DB5434. Native engine and
all service images are linux/arm64; AMD64 emulation was not introduced.

## Exact commands and outputs

Main executed commands follow; all timestamps/argv/cwd/durations/exits, including
repeated intermediate checks and failures, are in
[commands.jsonl](evidence/cesium-ion/commands.jsonl). The runner and bounded probe/
security scripts are archived as inert `.txt` sources for review. Commands ran
in `/Users/redmug/EARTHMIND` unless the ledger explicitly gives the staging cwd.
Deploy commands inherited `CITY_DIAGNOSTICS_ENABLED=true`; it is shown below.
Runtime bundle commands read the archived `check-runtime-bundle.mjs.txt` script
through stdin; they print only token presence, asset ID, file count and matches.

| Recorded label / output | Exact command | Exit | Seconds |
| --- | --- | --- | --- |
| [ion-desktop](evidence/cesium-ion/ion-desktop.log) | `env WEB_BASE_URL=http://localhost:3000 EARTHMIND_EVIDENCE_DIR=/private/tmp/earthmind-m035-results/ion-desktop npm run test:browser -- ion.spec.ts --project=desktop --workers=1` | 1 | 68.997 |
| [ion-desktop-final](evidence/cesium-ion/ion-desktop-final.log) | `env WEB_BASE_URL=http://localhost:3000 EARTHMIND_EVIDENCE_DIR=/private/tmp/earthmind-m035-results/ion-desktop-final npm run test:browser -- ion.spec.ts --project=desktop --workers=1` | 0 | 50.382 |
| [browser-acceptance](evidence/cesium-ion/browser-acceptance.log) | `env WEB_BASE_URL=http://localhost:3000 EARTHMIND_EVIDENCE_DIR=/private/tmp/earthmind-m035-results/browser-acceptance npm run test:browser -- --workers=1` | 1 | 413.359 |
| [quality-final-source](evidence/cesium-ion/quality-final-source.log) | `make lint typecheck test build` | 0 | 9.209 |
| [deploy-release](evidence/cesium-ion/deploy-release.log) | `CITY_DIAGNOSTICS_ENABLED=true docker compose --env-file .env up --build --detach --no-deps --force-recreate --wait --wait-timeout 180 web` | 0 | 15.984 |
| [database](evidence/cesium-ion/database.log) | `uv run --locked python scripts/database_checks.py` | 0 | 2.262 |
| [migration-final](evidence/cesium-ion/migration-final.log) | `make migrate` | 0 | 1.916 |
| [migration-rehearsal](evidence/cesium-ion/migration-rehearsal.log) | `uv run --locked python scripts/verify_migrations.py` | 0 | 28.66 |
| [smoke](evidence/cesium-ion/smoke.log) | `make smoke` | 0 | 0.987 |
| [geography](evidence/cesium-ion/geography.log) | `uv run --locked python scripts/verify_real_geography.py` | 0 | 0.183 |
| [spatial-inspection](evidence/cesium-ion/spatial-inspection.log) | `uv run --locked python scripts/inspect_geospatial_database.py --output /private/tmp/earthmind-m035-results/postgis-inspection.json` | 0 | 0.474 |
| [context-isolation](evidence/cesium-ion/context-isolation.log) | `uv run --locked python infra/verification/check_build_context.py` | 0 | 0.349 |
| [compose-config](evidence/cesium-ion/compose-config.log) | `docker compose --env-file .env config --quiet` | 0 | 0.078 |
| [architecture-release](evidence/cesium-ion/architecture-release.log) | `uv run --locked python scripts/check_architecture.py` | 0 | 0.904 |
| [runtime-bundle-release](evidence/cesium-ion/runtime-bundle-release.log) | `docker compose --env-file .env exec -T web node --input-type=module < /private/tmp/earthmind-m035-results/check-runtime-bundle.mjs` | 0 | 0.232 |
| [provider-credits](evidence/cesium-ion/provider-credits.log) | `uv run --locked python /private/tmp/earthmind-m035-results/audit_provider_credits.py` | 0 | 1.68 |
| [security-final](evidence/cesium-ion/security-final.log) | `uv run --locked python /private/tmp/earthmind-m035-results/security_gates.py` | 0 | 0.366 |
| [services-final](evidence/cesium-ion/services-final.log) | `docker compose --env-file .env ps --all` | 0 | 0.147 |
| [source-whitespace](evidence/cesium-ion/source-whitespace.log) | `git diff HEAD --check` | 0 | 0.013 |
| [browser-release](evidence/cesium-ion/browser-release.log) | `env WEB_BASE_URL=http://localhost:3000 EARTHMIND_EVIDENCE_DIR=/private/tmp/earthmind-m035-results/browser-release npm run test:browser -- --workers=1` | 0 | 432.654 |

The probe was initially invoked directly as
`uv run --locked python /private/tmp/earthmind-m035-results/probe_ion.py`; its
sanitized JSON output and exact helper source are archived. Initial root/staging
focused checks were superseded by the final complete locked workspace checks.
No hosted CI, commercial plan change, token-scope administration, production
internet deployment, optional terrain pixel coverage or broad new spatial
performance implementation is claimed.

## Credential and Git gates

Before Git delivery, scans compared all configured working secret values privately
against candidate files, evidence, staged blobs and built static assets. The local
`.env` remains ignored with mode0600. The running image has the canonical public
token configured, no legacy alias value, imagery2 and **zero token matches across
21 built static assets**. Docker build-context isolation passed. Raw traces/HAR,
endpoint response bodies and signed URL queries are excluded. The first failed
licensed capture stays local because its inline attribution was incomplete;
all committed final licensed captures retain visible attribution.

The focused source/evidence diff and actual commit/hook outputs are recorded in
the evidence directory. Final Git execution results are added only after the
commands complete. No push or next milestone work is authorized or performed.

Staged gates before commit: three configured working values checked with zero
matches in992candidatefiles, evidence and staged blobs;21host static assets also
contained zero configured values. [Scan](evidence/cesium-ion/staged-secret-check.log).
The first staged whitespace check exited2 for one Markdown hard-break after the
ADR date; it was removed and the repeat exited0. Both original and repeat logs
remain archived. [Initial](evidence/cesium-ion/staged-whitespace.log),
[repeat](evidence/cesium-ion/staged-whitespace-final.log).
Pre-commit exited0: ESLint and TypeScript passed; contracts/Ruff/format/mypy hooks
reported no applicable changed files and were skipped. Their complete workspace
checks already passed through make lint. [Hooks](evidence/cesium-ion/staged-hooks.log).

The requested focused local commit actually exited0 and the working tree was
clean afterwards. Commit hooks again passed ESLint/TypeScript and skipped the
four unrelated hooks with no applicable files. Its raw [commit output](evidence/cesium-ion/git-commit.log)
and [Git gate record](evidence/cesium-ion/git-gates.json) are included by a
documentation/evidence-only amendment of that same local commit. Application
source is unchanged by that amendment; final commit identity is reported after
it completes. The pre-commit candidate [diff summary](evidence/cesium-ion/git-diff-stat.log)
and [changed-file inventory](evidence/cesium-ion/git-changed-files.log) retain their
actual snapshot rather than claiming to include their own subsequently added logs.
