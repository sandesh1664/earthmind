# M04 simulation API

All API paths use `/api/v1`; the browser uses the allowlisted `/api/simulation` bridge with the same suffix. OpenAPI exposes the actual Pydantic contracts. This is a trusted loopback application, not user authentication or a public multi-tenant API.
POST mutations use existing server-only development write authorization.
JSON requests have strict extra-forbid schemas and a 64KiB body limit.
List wrappers are `{items,total,limit,offset}` (limit1..100,offset0..100000).

## Demand and scenarios

`DemandConfig` = `{trip_target:1..5000,duration_seconds:30..3600,seed:0..2147483647,departure_distribution:'uniform'|'poisson'|'burst',vehicle_class:'passenger',od_policy:'reachable_uniform',demand_multiplier:0.1..3,sample_interval_seconds:1..10}`. Effective trips `round(trip_target*demand_multiplier)` must be1..5000. Defaults500/600/42/uniform/passenger/reachable_uniform/1/2. `trip_target` is canonical (not trip_count).

`POST /scenarios` `{name,network_version_id,demand}` ->201 Scenario.
Scenario `{id,name,network_version_id,network_version_label,demand,configuration_checksum,created_at,synthetic:true,validation}`.
Validation `{valid,errors:string[],warnings:string[],network_artifact_sha256:string|null,mapped_edge_count:int|null,engine_version:string|null}`.
`GET /scenarios`, `GET /scenarios/{id}`, `POST /scenarios/{id}/validate`.
`GET /simulation-networks` returns page of `{id,version_label,region_name,is_synthetic,source_checksum,network_artifact_sha256,engine_version,mapped_edge_count,validation}`; only compatible retained artifact references are valid.

## Runs

`POST /simulations` `{scenario_id,seed?:int,retry_of?:UUID}` requires `Idempotency-Key` (1..128 ASCII visible safe chars). Same key+same request returns existing run; different request409. Retry only terminal failed/cancelled parent and creates new UUID linked via retry_of/attempt_number.
`GET /simulations`, `GET /simulations/{id}`, `POST /simulations/{id}/cancel`.
Run `{id,scenario_id,network_version_id,scenario_name,status:'queued'|'running'|'succeeded'|'failed'|'cancelled',seed,created_at,started_at,finished_at,worker_id,engine_version,input_sha256,error_code,error_message,progress:{simulated_seconds,duration_seconds,departed,completed,active},cancel_requested,attempt_number,retry_of,synthetic:true}`. Queue position omitted (not guaranteed by durable DB ordering).
`GET /simulations/{id}/events` page of `{id,run_id,event_type,message,progress_seconds,created_at}`.
`GET /simulations/{id}/metrics` `{run_id,metrics:[{metric_name,value:number|null,unit,aggregation,calculation_version}],vehicle_counts:[{time,active,departed,arrived}]}`.
`GET /simulations/{id}/export?format=json|csv`; default JSON includes scenario/config/provenance/version/checksums/metrics. Metrics/replay/export unavailable until actual succeeded output exists (409).

## Replay (worker output + API)

Public `GET /simulations/{id}/replay/manifest` = `{schema_version:1,run_id,network_version_id,duration_seconds,sample_interval_seconds,vehicle_class:'passenger',synthetic:true,coordinate_reference_system:'EPSG:4326',chunks:[{id:string,start_time:number,end_time:number,sample_count:int,sha256:string,size_bytes:int}],counts:[{time,active,departed,arrived}]}`.
`GET /simulations/{id}/replay/chunks/{chunk_id}` = `{schema_version:1,run_id,chunk_id,frames:[{time,vehicles:[{id,longitude,latitude,heading,speed,vehicle_class:'passenger',segment_id:int}],departed:string[],arrived:string[],teleported:string[]}],events:[{id,time,type:'departed'|'arrived'|'teleport_start'|'teleport_end'}]}`.
Chunk IDs six decimal digits. Chunks are bounded and contain complete active samples for their frame timestamps. A missing vehicle is absent (no interpolation over appearances/disappearances or teleport events). Frames may include overlap endpoint across chunks for continuous interpolation. No client URI/path accepted.

## Comparison

`POST /comparisons` `{baseline_run_id,modified_run_id}` ->201; GET `/comparisons/{id}` -> `{id,baseline_run_id,modified_run_id,network_version_id,created_at,metrics:[{metric_name,unit,baseline_value:number|null,modified_value:number|null,absolute_change:number|null,percentage_change:number|null}],warnings:string[]}`. Both runs succeeded, same network/engine/seed/duration/distribution/class/OD/sample interval. Demand volume may differ. Incomplete completion counts always disclosed and no causal prediction claim.

## Backend-owned async worker store (existing Infrastructure/session)

`SimulationWorkerStore(infrastructure:Infrastructure, worker_id:str, lease_seconds:int=30)`
- `await claim() -> WorkerClaim|None`: atomically queued→running, fills started_at/worker_id/heartbeat/engine claim. Polls durable PostgreSQL regardless of Redis hints.
- `await heartbeat(run_id:UUID,progress:ProgressUpdate|None=None) -> bool`: true means owned/running/notcancelled; writes actual progress and renews heartbeat; false must terminate subprocess.
- `await publish(run_id:UUID,result:PublishedResult) -> bool`: atomic own-lease+running+!cancel check, inserts verified metrics/artifacts, manifest path and succeeds. False means discard unpublished output.
- `await fail(run_id:UUID,code:str,message:str,cancelled:bool=False) -> None`: owns run only; cancelled sets terminalcancelled; never converts terminal rows to success.
- `await reconcile_stale() -> int`: expired running leases fail with explicit worker_lost, or cancel if cancellation requested. Never auto-reruns ambiguous native execution.

WorkerClaim `{run_id:UUID,input_config:SimulationInput,seed:int}`.
SimulationInput `{schema_version:1,network_version_id:UUID,network_artifact:'recovery-v1',network_sha256,source_sha256,mapping_sha256,demand:DemandConfig}`. Server-resolved slug and fixed file names under configured `/simulation-inputs`; no user paths.
ProgressUpdate `{simulated_seconds,duration_seconds,departed,completed,active}`.
PublishedResult `{engine_version,input_sha256,manifest_path,metrics:[MetricValue],artifacts:[ArtifactValue]}`. manifest_path and artifact relative_path start `runUUID/`; ArtifactValue `{artifact_type,relative_path,checksum_sha256,size_bytes,content_type}`. Worker atomically renames its fully verified temporary result directory to runUUID before publish. Result artifacts include replay_manifest, replay_chunk:000000 etc, demand, tripinfo, summary/metrics, engine_log. API validates root containment, no symlink escapes, checksum and byte size on reads.

Constants: `SIMULATION_QUEUE_KEY='earthmind:simulations:queue'`; Redis contains UUID hints only. Artifact root `/simulation-artifacts`, input root `/simulation-inputs`. One worker. Native runtime uses async timeout+process-group cleanup; no arbitrary command strings. Full output archives ignored, small textual acceptance evidence only.

## HTTP and storage policy

POSTs require the existing private `X-Earthmind-Dev-Token` at the API. The browser
never receives it. Next validates loopback Host (ignoring forwarded hosts), same
Origin, application/json, explicit `X-Earthmind-Intent: simulation-write`, and
strict body/route allowlists before injecting the private header. Inputs are
64KiB maximum; JSON responses/chunks4MiB, manifests1MiB and engine logs2MiB.

`GET /simulations/{id}/logs` returns an actual verified succeeded-run engine log
as text/plain. Failed/partial workspaces are not arbitrary downloadable paths.
Export JSON contains run/scenario/demand, engine/source/network/mapping/input
hashes, actual metrics and artifact descriptors. CSV contains actual metric rows
with units, aggregation and calculation version; it is not a raw trajectory
archive. Chunks are available separately through scoped routes.

Creation returns201; submission202; lists/details200. Invalid input422,
unauthorized403, unsupported content type415, body limit413, state/idempotency/
comparison conflict409, queue capacity429 and unavailable verified resources503.
Results/metrics/replay/export before actual success return409. Missing resources
return404. M04 transactions commit before success headers, so a returned identity
is immediately readable. Repeating an identical submission key returns its
existing run without duplicate execution; different parameters conflict.

Scenario/run inputs are immutable. Retry creates a tracked run rather than
resetting a terminal status. Reads belong to the trusted local workspace; public
deployment requires real identity, resource authorization and TLS. No user roles
or authentication are fabricated. See security.md and verification-m04.md.
