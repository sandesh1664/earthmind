# M01 verification — 2026-10-26

This is the authoritative report for the **detailed M01 specification** supplied
on 2026-10-26, including the subsequent audit. It supersedes the earlier narrow
scaffold completion report. Work remained within M01; no M02 functionality was
implemented. All times below are Asia/Dubai (UTC+04:00).

## Environment and compatibility

Workspace: `/Users/redmug/EARTHMIND`; branch `codex/m01-foundation`.
The repository initially contained M01 source but **no commits**; useful work was
preserved and audited before the initial milestone commit.

| Component | Actually observed |
| --- | --- |
| Host | macOS 26.5.1 build 25F80, darwin/arm64, 16 GiB RAM |
| Docker | Engine 29.9.1 linux/aarch64; Compose v5.6.0; about 8 GB engine RAM |
| Disk | About 230 GiB free at reconnaissance |
| Host tools | Node 26.0.0, npm 11.12.1, uv 0.11.12, Git 2.54.0 |
| Python | Default host 3.14.6 rejected for this project; selected host 3.12.13, container 3.12.15 |
| Web runtime | Node 22.23.4 container; Next 16.4.3 / React 19.3.1 |
| API | FastAPI 0.162.0, Pydantic 2.14.1, psycopg 3.3.6, SQLAlchemy 2.1.6 |
| Data | PostgreSQL 17.11 / PostGIS 3.6.4 on aarch64; Redis 7.4 image |
| SUMO | SUMO/netconvert 1.15.0; native Debian package 1.15.0+dfsg-1+deb12u1 |
| Python clients | traci 1.15.0 / sumolib 1.15.0; actual TraCI protocol 20 |

Python is constrained to >=3.12,<3.13. JavaScript and Python applications are
locked. All selected base image manifests were rechecked; every running image
is linux/arm64. The upstream selected PostGIS image is AMD64-only and was
replaced by a custom native image. No emulation was used. Ports 3000, 8000 and
5434 were initially owned by this project's existing Docker containers.
Initial restricted memory inspection failed; approved inspection returned
17179869184 bytes. That restriction was resolved rather than reported as PASS.

## Implemented and missing requirements

| Requirement group | Status | Evidence / implementation |
| --- | --- | --- |
| Existing workspace/Git preservation and reconnaissance | PASS | Existing source inspected; no unrelated files/volumes reset |
| Monorepo, strict Next App Router and separately executable worker | PASS | npm/uv workspaces; justified established paths in ADR 0001 |
| Tailwind, Lucide, Query, Zod and responsive professional shell | PASS | Versioned locks; real desktop/tablet/mobile browser checks |
| Nine sections and honest future placeholders | PASS | Functional overview/status; other sections explicitly later work |
| Versioned health/readiness/capabilities and safe errors | PASS | Real HTTP, unit and browser checks; future capability flags false |
| SQLAlchemy DI/session lifecycle and metadata migration | PASS | UUID, constrained fields, UTC timestamps/index; live commit/rollback |
| Native PostgreSQL/PostGIS, Redis and private service communication | PASS | Actual SQL queries, loopback bindings, Redis unpublished |
| Real bounded queue and worker job completion | PASS | Actual UUID jobs consumed and succeeded in worker PID 7 |
| Mandatory headless SUMO/netconvert/traci/sumolib | PASS | Native executable checks, actual TraCI fixture and parsed XML |
| Locked tooling, hooks, commands and non-destructive cleanup | PASS | All requested Make targets exercised; data volumes retained |
| Automated unit/integration/browser/build/smoke checks | PASS | 40 Python unit + 1 live DB + 19 frontend + 6 browser tests |
| Documentation, security review and eight decisions | PASS | README/setup/operations/security/troubleshooting/ADRs and this report |
| CI workflow implementation and local syntax validation | PASS | Pinned actions, ARM64 job, minimal permissions and integration steps |
| Hosted GitHub Actions execution | NOT RUN | Repository not published; no hosted-run claim |
| React Hook Form conditional use | PASS | M01 has action buttons, no data-entry form requiring it |
| Physical mobile hardware testing | NOT RUN | Actual Chromium responsive viewports tested instead |

No mandatory local M01 implementation requirement remains missing. Hosted CI
and physical-device coverage are explicit unexecuted checks. Public deployment
hardening and durable traffic scheduling remain outside the local M01 boundary.

## Exact execution records

Every row ran from `/Users/redmug/EARTHMIND` in the environment above. Commands
are executed commands, not proposed instructions. Full argv, start times,
durations, exit codes and output filenames are in
[commands.jsonl](evidence/m01-audit/commands.jsonl). A successful syntax check is
not a hosted CI pass, and mocked UI tests are not real integration proof.

| Dubai time | Exact command | Exit | Status | Observed result and raw output |
| --- | --- | --- | --- | --- |
| 21:35:11 | `make setup` | 0 | PASS | Environment checks, locked installs and hooks succeeded. [setup](evidence/m01-audit/setup.log) |
| 21:35:15 | `docker compose build` | 0 | PASS | All expanded native ARM64 service images built. [image-build](evidence/m01-audit/image-build.log) |
| 21:36:29 | `make lint typecheck test build` | 0 | PASS | 40 Python tests, 17 frontend tests; lint/types/build succeeded before origin fix. [quality](evidence/m01-audit/quality.log) |
| 21:36:25 | `make dev` | 0 | PASS | Healthy controlled startup; real web/API/Redis/worker/SUMO smoke passed. [dev](evidence/m01-audit/dev.log) |
| 21:37:39 | `uv run --locked python scripts/database_checks.py` | 0 | PASS | 1 live test passed: UUID/UTC/schema, SQLAlchemy commit and rollback. [database-integration](evidence/m01-audit/database-integration.log) |
| 21:37:49 | `npm audit --json` | 0 | PASS | 0 known npm vulnerabilities in the installed lock. [npm-advisories](evidence/m01-audit/npm-advisories.log) |
| 21:37:42 | `uv run --locked python scripts/verify_migrations.py` | 0 | PASS | Fresh DB without extension repaired; repeated and downgrade/upgrade passed; isolated fixtures cleaned. [fresh-migrations](evidence/m01-audit/fresh-migrations.log) |
| 21:37:45 | `npm run test:browser` | 1 | FAIL | Initial run: 3 real-deployment tests failed with HTTP 403; 3 mocked UI tests passed. Fixed later. [browser](evidence/m01-audit/browser.log) |
| 21:38:27 | `uv run --locked python infra/verification/check_build_context.py` | 0 | PASS | 5 synthetic root/nested secret fixtures excluded by actual Docker context behavior. [context-isolation](evidence/m01-audit/context-isolation.log) |
| 21:38:30 | `make migrate` | 0 | PASS | Alembic upgrade repeated successfully; head 0002_system_metadata. [migration-repeat](evidence/m01-audit/migration-repeat.log) |
| 21:39:17 | `uv run --locked python scripts/failure_smoke.py` | 0 | PASS | Worker, Redis and PostgreSQL outages returned direct/proxied 503; liveness and recovery passed. [failure-recovery](evidence/m01-audit/failure-recovery.log) |
| 21:41:02 | `docker compose up --build --detach --no-deps --wait web` | 0 | PASS | Only web rebuilt/replaced after browser-facing origin correction. [web-origin-fix](evidence/m01-audit/web-origin-fix.log) |
| 21:43:20 | `npm run test` | 0 | PASS | 19 frontend regression tests passed. [web-quality-fixed](evidence/m01-audit/web-quality-fixed.log) |
| 21:43:17 | `npm run test:browser` | 0 | PASS | 6 tests passed: 3 real deployment + 3 explicitly mocked UI tests across three sizes. [browser-fixed](evidence/m01-audit/browser-fixed.log) |
| 21:43:22 | `docker compose exec -T worker sumo --version` | 0 | PASS | Headless SUMO 1.15.0 executed in running ARM64 worker. [sumo-version](evidence/m01-audit/sumo-version.log) |
| 21:43:24 | `docker compose exec -T worker netconvert --version` | 0 | PASS | netconvert 1.15.0 executed in running ARM64 worker. [netconvert-version](evidence/m01-audit/netconvert-version.log) |
| 21:43:27 | `docker compose exec -T worker python -m earthmind_worker.runtime_check --output-dir /tmp/earthmind-m01-sumo` | 0 | PASS | Real TraCI protocol 20, 25 steps, 2 departed/2 completed; XML parsed and retained. [sumo-fixture](evidence/m01-audit/sumo-fixture.log) |
| 21:46:24 | `make clean lint typecheck test build` | 0 | PASS | Non-destructive clean; strict mypy 26 files; 40 Python + 19 frontend tests; lint/tsc/build passed. [final-quality](evidence/m01-audit/final-quality.log) |
| 21:47:53 | `uv run --locked python -c <exact workflow syntax check in commands.jsonl>` | 0 | PASS | Workflow YAML parsed; native ARM64 runner and read-only permissions. Hosted execution NOT RUN. [ci-syntax](evidence/m01-audit/ci-syntax.log) |
| 21:47:55 | `make status` | 0 | PASS | Five long-running services healthy; migrate exited 0. [status](evidence/m01-audit/status.log) |
| 21:47:57 | `make logs` | 0 | PASS | Bounded service logs available; structured API records observed. [logs](evidence/m01-audit/logs.log) |
| 21:48:00 | `make down` | 0 | PASS | Only EARTHMIND containers/network removed. [down](evidence/m01-audit/down.log) |
| 21:48:17 | `docker volume ls --filter label=com.docker.compose.project=earthmind --format '{{.Name}}'` | 0 | PASS | earthmind_postgres_data and earthmind_redis_data remained. [volumes-retained](evidence/m01-audit/volumes-retained.log) |
| 21:48:20 | `make dev` | 0 | PASS | Final source rebuilt; all services healthy; real diagnostic/SUMO smoke passed again. [final-restart](evidence/m01-audit/final-restart.log) |
| 21:49:24 | `make smoke` | 0 | PASS | Final required HTTP → queue → worker → SUMO checks passed. [final-smoke](evidence/m01-audit/final-smoke.log) |
| 21:49:26 | `docker compose ps --all` | 0 | PASS | All five services healthy, migration Exited (0), loopback ports only. [final-services](evidence/m01-audit/final-services.log) |
| 21:50:35 | `npm run test:browser` | 0 | PASS | Final deployed wording and responsive screenshots verified; 6 browser tests passed. [browser-final](evidence/m01-audit/browser-final.log) |

| 21:54:12 | `git diff --cached --check` | 2 | FAIL | Initial exit 2: only trailing whitespace emitted by raw tools in 29 evidence files; no source errors. [git-diff-check](evidence/m01-audit/git-diff-check.log) |
| 21:54:14 | `uv run --locked pre-commit run --all-files` | 0 | PASS | All six hooks passed against all staged files. [hooks](evidence/m01-audit/hooks.log) |
| 21:54:53 | `git diff --cached --check` | 0 | PASS | Source whitespace passed; .gitattributes preserves verbatim evidence bytes without suppressing source checks. [git-diff-check-fixed](evidence/m01-audit/git-diff-check-fixed.log) |

## SUMO and queue proof

`POST` through Next.js returned queued UUIDs; the real worker wrote running and
succeeded records. A diagnostic result included worker PID 7 and architecture
aarch64. The SUMO job completed two synthetic vehicles after 25 steps using
TraCI protocol 20. Actual arrival times were 22.00 and 24.00; each trip duration
was 22.00, with route length 195.00. These are synthetic fixture outputs, not
Dubai measurements, forecasts or production traffic scenarios.

Retained actual outputs: [tripinfo XML](evidence/m01-audit/sumo-tripinfo.xml),
[generated network](evidence/m01-audit/sumo-network.net.xml), and
[fixture JSON/log](evidence/m01-audit/sumo-fixture.log). SUMO executes only in the
worker; no GUI, X server, NVIDIA CUDA or API-process execution was required.

## Audit defects fixed and failures retained

- **Nested environment-file leakage:** the original Docker context admitted
  nested synthetic .env files. Recursive exclusions and a real Docker regression
  now exclude five fixtures. No existing working secret leak was observed.
- **Build reproducibility:** floating PostGIS package selection and isolated
  Hatchling tooling were replaced with exact package/build-backend pins; uv
  commands now reject stale locks. Remaining transitive apt drift is disclosed.
- **Dependency advisory:** the original pip-audit exited 1 for pytest 8.4.2,
  reporting two entries for one unique CVE-2025-71176 advisory. The incompatible
  <9 constraint was removed; locked pytest is now 9.1.1. Final scan exited 0:
  54 public packages audited, zero known advisories; three local packages skipped.
  [Reviewed advisory](https://github.com/advisories/GHSA-6w46-j5rx-g56g).
- **Cleanup/session integrity:** Redis close failure could skip database pool
  cleanup. The reproduced failing regression is fixed; the final architecture
  uses one lazy SQLAlchemy engine with guaranteed disposal and real rollback tests.
- **Contract drift/data boundary:** Python/JSON/TypeScript parity is now checked;
  unknown upstream fields and malformed enum/job data are rejected safely.
- **Browser-origin integration:** the first real browser run exited 1, with
  3 failed and 3 passed. Internal standalone bind origins incorrectly rejected
  legitimate POSTs. The fix uses a validated loopback Host, rejects foreign or
  malformed hosts/origins, and retains JSON-only POSTs. Final browser runs pass.
- **Runtime truth and bounds:** runtime failures invalidate verified capability
  records immediately; timeout budgets include lock waits and kill child groups.
- **Migration prerequisite:** DB health no longer requires PostGIS before Alembic
  can install it. The isolated missing-extension recovery test actually passed.

Original failure evidence remains under [history](evidence/m01-audit/history),
including the failing pytest advisory scan, reproduced cleanup test, original
Docker-context behavior and the initial missing-greenlet import failure (exit 2).
The corrected lock explicitly includes SQLAlchemy's asyncio extra/greenlet.
The first browser [raw output](evidence/m01-audit/browser.log),
[JSON report](evidence/m01-audit/browser-first-results.json) and failure screenshot
are preserved. Traces/data archives and installed dependencies are not committed.

## Security and reproducibility review

Application containers actually run non-root, with ALL capabilities dropped,
no-new-privileges, bounded CPU/memory/PIDs and at most three crash restarts. No
Docker socket is mounted. The worker has no database credentials. Redis is
private, limited in memory, and the pending queue is capped at 20. New `.env`
files receive generated secrets; the existing file is preserved at mode 0600.
Current configured secret values were checked against commit-eligible files with
no matches; values were never printed. See [secret check](evidence/m01-audit/secret-check.json)
and [runtime controls](evidence/m01-audit/runtime-security.json).

Final npm audit exited 0 with zero known vulnerabilities. Final Python scan
exited 0 over 54 public packages, with three unpublished EARTHMIND packages
unscannable by PyPI advisory lookup. These scans do not establish application or
OS-library safety. An upstream plugin retains deprecated ESLint 9 transitively;
the project's lint command runs ESLint 10.13.0 successfully.

Known development limits: no user authentication; API/migration role remains a
local PostgreSQL administrator; Redis has no password on the private network;
queue consumption is at-most-once, with crashed running jobs expiring after 300
seconds. Transitive apt repositories remain live, so byte-identical and
permanently retrievable system builds are not claimed. Shared deployment needs
separate roles, TLS, identity, managed secrets and tested backups. These are
recorded limits, not hidden production-readiness claims.

## Browser evidence

Actual viewport coverage: desktop 1440×1000, tablet 820×1180 and mobile 390×844.
The real tests submit and complete diagnostics/SUMO jobs, check overflow and
keyboard navigation, verify honest later-milestone content, and assert no browser
console/page errors. Three additional tests use explicitly mocked dependency
failures only to verify UI error/retry behavior. Actual dependency outages are
proved separately by failure_smoke.py.

[Desktop](evidence/m01-audit/dashboard-desktop.png),
[tablet](evidence/m01-audit/dashboard-tablet.png),
[mobile](evidence/m01-audit/dashboard-mobile.png).

## Git and milestone boundary

This is the repository's initial M01 commit because no previous commit existed.
An [audit-only source snapshot comparison](evidence/m01-audit/audit-diff-stat.txt)
is recorded separately from the initial Git diff. Before commit, all six hooks passed and staged source whitespace checks passed.
The staged-blob scan found no configured working secrets, dependency/build caches
or generated archives; [actual staged scan](evidence/m01-audit/staged-secret-check.json).
Raw tool output remains byte-preserved under an explicit evidence-only Git
attribute, with the original whitespace-check failure retained. Exact current commit identity is
available from `git log -1` and the final report. No remote push is authorized or
performed. The initial local commit was created successfully after these code gates, with
all six hooks passing again. `git status --porcelain=v1` then returned empty.
The final report identifies the current commit after this documentation update;
no remote push occurred.

M02 readiness: the local engineering foundation supports starting a separately
authorized M02. No geographic ingestion, real Dubai network, AI model, signal
optimization, digital twin or production traffic scenario was implemented here.

Final Git gates: `git diff --cached --check` exited 0; all hooks exited 0;
`git commit` exited 0; clean status was observed. See
[Git gate record](evidence/m01-audit/git-gates.json).
