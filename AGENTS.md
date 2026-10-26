# EARTHMIND engineering instructions

- M01 is the preserved foundation; M02 adds geospatial persistence and synthetic
  structural validation. Real traffic ingestion, AI, Cesium, SUMO conversion and
  production scenario execution remain outside the completed M02 scope.
- Use Python 3.12 and native Linux ARM64 containers. Never enable AMD64 emulation
  to hide an incompatible dependency.
- Keep JavaScript dependencies in the npm workspace lock and Python dependencies
  in the uv workspace lock. Use `uv run --locked` for verification commands.
- Keep API routes thin, database access in injected sessions, and SUMO execution
  in the worker process. Accept only typed diagnostic jobs, never shell input.
- Run `make lint typecheck test`, a production build, migrations, and real
  deployment smoke checks before claiming completion. Keep failures and blocked
  checks visible in `docs/verification.md` with command, exit status, and evidence.
- Preserve `.env`, user datasets, named volumes, and unrelated Docker projects.
  `make clean` must never remove persistent data.
- Never commit working credentials, caches, installed dependencies, or generated
  simulation data archives. Small, clearly labeled verification fixtures and
  textual evidence are appropriate.
- Reuse `models.Base`, existing settings/session dependencies and the single
  Alembic environment. Never add a competing engine or ORM base.
- Store 2D EPSG:4326, longitude then latitude. Use geography/pyproj for metric
  measurements, explicit topology endpoints and plain geography casts matching
  the expression index. Geometric crossings never imply graph connections.
- Published/archived networks and their geometry are immutable. Corrections use
  new versions. Retain database triggers and same-network composite foreign keys.
- Persist at most 5,000 vertices per region/edge. Respect bounded query/body/page
  and validation budgets; NOT_VALIDATED counts are unknown, never invented zero.
- Preserve original provenance privately; public serializers allowlist metadata
  and sanitize source URLs. Never claim synthetic fixtures are observed streets,
  official boundaries, verified signals or SUMO-converted networks.
- Keep development write tokens server-only and API/web/PostgreSQL loopback-only.
  This is not user authentication; never advertise shared production readiness.
- Migration 0003 is frozen; 0004 adds reviewed integrity guards. Future changes
  require new revisions. Populated M02 downgrades must refuse destructive drops.
- Run `scripts/database_checks.py`, `scripts/verify_migrations.py`,
  `scripts/inspect_geospatial_database.py` and browser checks for spatial changes.
  Keep actual failures as evidence. Do not reset main volumes to pass tests.
- M03 uses Cesium only in lazy browser modules. Set CESIUM_BASE_URL before import;
  retain exact-package Workers/ThirdParty/Assets/Widgets and license copy workflow.
- React owns UI/query selection; the mount-scoped controller owns native Cesium
  objects. Always dispose viewers/events/provider work and guard stale async results.
- Keep maps bounded (500 features/25,000 positions per layer); abort stale fetches
  through the proxy, debounce camera requests and evict inactive viewport caches.
- Credential-free fallback is packaged Natural Earth plus ellipsoid terrain.
  Optional ion resources must preserve provider attribution and explicit errors.
  Never borrow a default Cesium token or fabricate building metadata/coverage.
- Only explicitly public scoped visualization tokens may reach /api/city/config;
  private GIS, database and M02 write tokens stay server-side. Inspectors render text.
- Verify actual browser/WebGL, canvas picks, asset HTTP bytes, lifecycle and M01/M02
  regressions; isolated mocks are not end-to-end evidence. Preserve failed runs.
- Keep performance QA datasets clearly synthetic and remove only task-owned rows;
  distinguish JS heap/software-renderer observations from GPU/production benchmarks.
- Do not push or begin M04 without explicit authorization.
