# Running synthetic traffic experiments

The current workflow uses the existing converted Downtown Dubai / Business Bay
network, pinned SUMO/netconvert/TraCI/sumolib1.15.0 and Python3.12 on native ARM64.
No real traffic feed or external network import runs when a scenario is submitted.

## Start and run

```sh
cd /Users/redmug/EARTHMIND
make setup
CITY_DIAGNOSTICS_ENABLED=true make dev
```

Existing `.env`, geography and named volumes are preserved. Diagnostics are optional
for normal use but required for native picking/performance verification. Do not
change the existing Cesium token to enable simulations. The established private
`EARTHMIND_DEV_WRITE_TOKEN` enables local writes; it stays server-side in web/API.
Inputs must exist under the retained `data/dubai-osm/recovery-v1` directory. A
missing/invalid artifact is a validation failure, not a download or fake fallback.

1. Open Scenario Studio, choose the validated real network and a demand template.
2. Configure trip target, duration, seed and departure distribution. Demand is synthetic.
3. Run validation, save the immutable scenario and start simulation.
4. Simulation Laboratory polls persisted status and actual progress. Open events,
   verified engine logs, metrics, JSON/CSV exports or recorded replay after success.
5. Analytics compares compatible completed runs. Incomplete trips remain visible;
   fewer completed trips cannot be presented as evidence of an improvement.

Independent actual API acceptance, creating its own clearly named research scenario:

```sh
uv run --locked python scripts/verify_simulation_pipeline.py --trip-target 500 --duration 600 --seed 42 --distribution uniform --output /private/tmp/earthmind-pipeline-500.json
```

The helper privately reads the existing developer gate and never prints credentials.
It checks real submission/idempotency, progress, responsiveness, metrics, exports,
chunk hashes and bounded PostGIS proximity samples. It does not establish browser
rendering or process cleanup. Use `--mode observe-success --run-id UUID` for a
read-only audit of an existing succeeded run. Output files are not overwritten
without an explicit option. Full generated outputs belong in persistent storage,
not Git. See `--help` for cancellation/retry and explicit failure observation modes.

## States and recovery

Allowed transitions are queued→running→succeeded, queued/running→cancelled, and
queued/running→failed. Terminal states never become success later. A cancelled
run can have no start timestamp; queued validation failures do not invent a start.
Idempotency-Key identifies the complete submission request; reuse with different
parameters returns409. A retry creates a new UUID/attempt linked to its failed or
cancelled parent. The UI retains the parent seed and records all attempt inputs.

Cancellation sets a persisted request. The worker checks it while native execution
runs, terminates the owned Python/SUMO process group, escalates to SIGKILL after
its grace budget, and refuses publication. Shutdown performs the same cleanup.
After an ungraceful worker loss, expired leases are marked explicitly worker_lost;
ambiguous execution is not silently repeated. Start a new tracked retry. Do not
reset the database, input snapshot or run volume to make a run succeed.

One native job is allowed at a time. Defaults:600s wall-clock timeout,30s lease,
20queued/running jobs,5000effective trips,3600simulated seconds,4MiB replay chunk,
1MiB manifest,256MiB total output,2MiB native log and bounded frame/chunk counts.
Compose constrains worker CPU, memory and process count. Duration is a simulation
horizon, not a promise of wall-clock execution time. Native progress, departure,
arrival and worker elapsed time are separate measurements.

## Artifacts and troubleshooting

Each run gets a unique mode0700 partial workspace. Inputs/checksums are snapshotted;
route generation and TraCI output stream into bounded files. Publication validates
metrics, final counts, scope, checksums, MIME and file sizes before atomically
adopting the directory and committing artifact/metric rows with succeeded state.
A crash between rename and DB publication can leave unadvertised files; they are
not treated as success or reused as a new attempt. Capacity/retention and backups
remain operator responsibilities. `make down` preserves the artifact volume.

Native failures expose safe codes and bounded summaries. Check Laboratory events
first, then verified engine log for succeeded runs. Failed/partial diagnostics stay
local to the owned workspace; they are not served through arbitrary file routes.
Use UUID-scoped artifact metadata and container-local inspection, never client paths.
A missing input, checksum mismatch, unsupported engine, timeout, invalid route,
output budget, permission failure or lease loss must remain an explicit failure.

M01 queue/runtime checks continue to work. A tiny runtime diagnostic submitted
while the native lock is occupied fails honestly rather than spawning concurrent
SUMO or falsely marking a verified advancing simulation unavailable. Readiness
still reflects actual database/Redis/worker health; no fake healthy state is added.
