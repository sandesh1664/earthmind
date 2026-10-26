# M01 operations

Run commands from the repository root. `make setup` validates the host and ARM64
Docker engine, installs Python 3.12 and the workspace locks, preserves existing
configuration, and installs Git hooks. New configuration receives a random local
database password; `.env` is kept private and excluded from Git/build contexts.

## Startup and migrations

Compose starts PostgreSQL and Redis, runs one Alembic process after basic DB
health passes, then starts the worker, API and web under health dependencies.
`make dev` waits for health, verifies every selected image's architecture and
runs the real deployment smoke check. `docker compose up -d --build` uses the
same controlled migration service; use `make status` to inspect readiness.

```sh
make status
make logs
make migrate
make smoke
```

The extension baseline and metadata migration are repeatable. Database health
requires SQL connectivity; API readiness additionally queries PostGIS. This
allows Alembic to repair a database missing the extension. `verify_migrations.py`
proves fresh setup, missing-extension recovery, repeatability and metadata
rollback/upgrade in its own disposable project. It refuses an existing fixture
project/volume and never resets the main database.

## Health and capability semantics

| Endpoint | Meaning |
| --- | --- |
| API `/api/v1/health` | Versioned process liveness |
| API `/api/v1/ready` | Real PostgreSQL/PostGIS, Redis and worker checks |
| API `/api/v1/system/capabilities` | Fresh observed integrations and future flags |
| API `/api/v1/diagnostics` | Bounded allowlisted job submission, HTTP 202 |
| API `/api/v1/diagnostics/{uuid}` | Validated queued/running/succeeded/failed job |
| Web `/api/health/live` | Next.js liveness |
| Web `/api/health`, `/api/capabilities` | Same-origin backend proxies |

Legacy `/health/live` and `/health/ready` remain supported. Health/proxy responses
are uncached. Dependency failure returns HTTP 503; queue capacity returns 429;
invalid diagnostic input returns 422. Unexpected failures return safe generic
errors. Worker heartbeat expires after 30 seconds; verified SUMO records expire
after 60. The dashboard distinguishes API reachability from degraded dependencies.

The queue holds at most 20 pending UUIDs and expires result records after 300
seconds. One worker executes allowlisted diagnostics with bounded network waits,
retries, native process deadlines and simulation steps. Runtime probes and jobs
are serialized. At-most-once consumption is intentional for M01; a crash after
claiming can leave a running record until it expires. No traffic job scheduler
or replay system is claimed.

## Actual verification commands

```sh
make lint typecheck test build
uv run --locked python scripts/database_checks.py
uv run --locked python scripts/verify_migrations.py
uv run --locked python scripts/failure_smoke.py
npm run test:browser
uv run --locked python infra/verification/check_build_context.py
docker compose exec -T worker sumo --version
docker compose exec -T worker netconvert --version
docker compose exec -T worker python -m earthmind_worker.runtime_check
```

Unit tests exclude the integration marker by default. Database checks explicitly
supply the ignored live configuration and verify real commit/rollback semantics.
Failure smoke temporarily stops this project's worker, Redis and database,
checks direct and proxied HTTP 503 with independent liveness, then restores the
stack. Browser tests distinguish real jobs from explicitly mocked UI failure
states. See `verification.md` for actual exits and original failed runs.

## Persistence and cleanup

`make down` preserves PostgreSQL and Redis named volumes. `make clean` removes
only known build/test caches; it preserves source, `.env`, dependencies, datasets
and volumes. Database password rotation must update stored SQL credentials and
`.env` together; copying an environment value alone does not rotate a live DB.
Never prune Docker or delete unrelated volumes to repair this project.
