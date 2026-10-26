# ADR 0004: PostgreSQL 17, PostGIS, and metadata migrations

Status: accepted for M01.

Use PostgreSQL 17 with PostGIS. The upstream selected PostGIS image has an
AMD64-only runnable manifest, so extend the official ARM64 PostgreSQL Bookworm
image with pinned native PostGIS packages. Baseline extension SQL and Alembic
are idempotent. A separate metadata migration uses UUID identifiers and
timezone-aware UTC timestamps with constraints and indexes.

Database container health checks basic SQL connectivity. PostGIS installation
belongs to initialization/migration, and the application readiness probe checks
it afterwards. Requiring the extension before migration would prevent recovery
of an initialized database that lacks the extension.

Publish only `127.0.0.1:5434`. Preserve named volumes on normal shutdown and
cleanup. Major PostgreSQL upgrades and domain geographic schemas are outside M01.
