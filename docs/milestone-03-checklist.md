# M03 execution checklist

Scope: Cesium geographic visualization over existing M02 data. M04 and traffic
simulation/import/forecasting/optimization remain outside this work.

- [x] Inspect clean M02 commit, existing instructions and actual infrastructure.
- [x] Run baseline M01/M02 lint/types/unit/build/smoke and actual database tests.
- [x] Pin verified compatible Cesium and host its four static directories/notices.
- [x] Implement lazy browser viewer, controlled layers, cameras and feature inspection.
- [x] Reuse PostGIS bbox/pagination/provenance with bounded cancellation-aware queries.
- [x] Verify actual WebGL globe, ground geometry, native picking and camera modes.
- [x] Verify every available layer control and missing-provider behavior.
- [x] Verify responsive browser views, context failure and lifecycle cleanup.
- [x] Observe actual 300-road display/selection and repeated mount memory scope.
- [x] Re-run final M01/M02 tests, migrations, SUMO/queue and Docker smoke checks.
- [x] Complete architecture, provider/license, performance and verification records.
- [x] Review exact diff, secrets/generated assets and create focused local commit.
- [x] Confirm clean status and stop before M04.

Optional authorized ion building/terrain/imagery verification remains BLOCKED
unless a valid public token and provider entitlement are actually available.
