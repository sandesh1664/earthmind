# M02 execution checklist

Scope: geospatial persistence, provenance, bounded spatial APIs and synthetic
study fixtures. M03/network ingestion/SUMO conversion/traffic execution remain
outside this milestone.

- [x] Independently inspect clean M01 commit, models, engine, migrations and services.
- [x] Preserve the real M01 smoke baseline before major changes.
- [x] Extend the existing Base, settings, session and migration environment.
- [x] Implement typed spatial services, explicit topology and geospatial UI.
- [x] Apply fresh and existing-M01 migration paths without resetting data.
- [x] Persist and idempotently verify illustrative Dubai synthetic fixtures.
- [x] Verify all database integrity constraints against real PostGIS.
- [x] Verify every endpoint, unauthorized writes and bounded geometry requests.
- [x] Execute indexed spatial queries and report measured observations honestly.
- [x] Run M01 unit/worker/SUMO/browser/build regressions and M02 tests.
- [x] Update architecture, schema, provenance, API and verification documentation.
- [x] Inspect secrets/diff, commit only M02 changes and confirm clean status.
- [x] Stop after M02; assess M03 readiness without implementation.
