# ADR 0015: Durable local SUMO execution and recorded Cesium replay

Status: Accepted for M04, 2026-10-27.

## Context

The retained OSM-derived Dubai network already has verified SUMO conversion and
PostGIS edge mappings. M04 needs reproducible synthetic experiments, honest job
states and replay of actual output while preserving the existing City Explorer.
The application has a local developer write gate, not multi-user authentication.

## Decision

Extend the existing ORM Base, scenario/run tables and Alembic environment with
additive revision `0005_simulation_execution`. Keep migrations 0001–0004 frozen.
PostgreSQL queued rows are the durable source of work. Redis carries UUID wake-up
hints; losing a notification does not lose the run. One native worker claims rows
atomically and maintains a worker-identity lease. A stale claim becomes
`worker_lost`; a retry is a new linked attempt, never an ambiguous re-execution.

Use the locked Python 3.12 workspace and native ARM64 SUMO/TraCI/sumolib 1.15.0.
Reuse checksum-verified, read-only network artifacts. Deterministic passenger
demand uses directed reachable edge connections and separate per-vehicle random
channels. Demand is synthetic; signal programs and OD choices are not field data.

Run an isolated Python/TraCI child and SUMO in one owned process group. Use fixed
argv and a credential-free environment, wall-clock/output/process limits and
bounded streaming files. Cancellation and shutdown reap that group. Validate
metrics, artifact scope and checksums before a fenced terminal DB transaction.
Persist verified native engine identity with actual progress, including attempts
that later fail or cancel. Never publish partial output as a successful result.

M04 routes use function-scoped session finalization so the transaction commits
before a 201/202 header. This fixes an observed immediate-follow-up 404 race.
Blocking input checks run outside the async event loop. Catalogs and response
bodies retain explicit pagination and byte budgets.

Keep artifacts in a named local volume: worker read/write, API read-only. This
reuses local infrastructure instead of claiming an unconfigured object store.
The browser uses a same-origin, loopback-only, validated Next bridge; the private
developer write credential remains server-side. Public deployment remains blocked
on actual identity, authorization, quotas, storage management and operational work.

Replay is recorded data, not a live simulation socket. Stream bounded chunks with
exact lifecycle events and segment identities. Preserve original bytes through
API/proxy for SHA-256 verification. Cache at most three nearby chunks and render
at most 1,000 native markers while preserving selection. Interpolate only valid
consecutive samples; never bridge teleports, missing frames or arrivals.

Add batched directional billboards and distant points to the existing Viewer.
These are lightweight world-anchored vehicle glyphs, not photorealistic glTF cars.
Do not replace geography, imagery, buildings, camera ownership or attribution.

## Consequences and evidence

The local workflow remains reproducible and bounded, but it is not a distributed
high-availability scheduler or calibrated Dubai traffic forecast. One seed and
different completion counts do not establish causal effects. Unfinished trips
remain explicit; empty means remain null. Linear two-second interpolation is a
visual approximation. Native lane alignment is not survey accuracy.

Redis marker failures are best effort during a brief outage, while database lease
failures stop execution. The existing M01 worker pulse policy still shuts down
after five consecutive failures; indefinite Redis outage survival is not claimed.

See [M04 verification](../verification-m04.md) for actual successful and failed
commands, hardware/software renderer measurements and controlled fault checks.
