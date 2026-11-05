# Traffic metrics and scientific limits

All M04 metrics originate from actual SUMO execution. Generated demand is
explicitly synthetic; the geographic network is OSM-derived. Neither source is
a live Dubai traffic observation or a calibrated prediction. UI estimates before
execution are labeled estimates and never become stored run measurements.

`simulation_metrics.py` parses bounded TripInfo XML after clean native shutdown.
DTD/entity declarations, duplicate vehicle IDs, nonfinite values and inconsistent
native counts fail verification. Unfinished trips are written by SUMO with
`--tripinfo-output.write-unfinished true`; they do not enter completed-trip means.
[SUMO TripInfo definitions](https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html).

| Metric key | Calculation and qualifying data | Unit |
| --- | --- | --- |
| `generated_trips` | Exact validated route-file vehicle count after demand multiplier. | trips |
| `departed_trips` | Cumulative actual TraCI departed-ID events. | trips |
| `completed_trips` | Cumulative actual arrival events, verified against completed TripInfo rows. | trips |
| `incomplete_trips` | Generated minus completed; includes active unfinished and never-departed trips. | trips |
| `mean_trip_duration` | Arithmetic mean TripInfo `duration` for arrival>=0. | s |
| `mean_time_loss` | Arithmetic mean completed TripInfo `timeLoss`. Negative rounding noise within 1 ms is normalized to zero; larger negative values fail verification. | s |
| `mean_waiting_time` | Arithmetic mean completed TripInfo `waitingTime`; scheduled stops are not waiting time. | s |
| `mean_moving_speed` | Mean actual `getSpeed` over valid active vehicle-seconds with speed>0.1 m/s. Uses each native 1 s step, including qualifying incomplete vehicles. | m/s |
| `teleports` | Number of actual teleport-start events, not distinct affected vehicle IDs. | events |
| `simulation_duration` | Actual final `simulation.getTime()`; may be shorter than the configured horizon if all requested trips finish. | s |
| `worker_execution_time` | Monotonic Python runner wall time through native output/trajectory verification, excluding queue wait and later database publication. | s |
| `sumo_execution_time` | Monotonic wall time covering SUMO startup, TraCI stepping and native shutdown. | s |
| `completed_throughput` | Completed trips×3600 divided by actual simulated duration; not a road-capacity measurement. | trips/h |

Means have **null** values when no qualifying observations exist. Null is not zero,
and the UI/export must render unavailable measurements accordingly. A valid count
of zero is still a measured count. Division by zero never creates an artificial
measurement. Every metric stores its unit, aggregation and calculation version.
The required invariants are `completed <= departed <= generated` and
`incomplete = generated - completed`; final replay count totals agree with those
native values.

TraCI position/speed values describe the current simulated step, and invalid
sentinel values can occur around teleportation. Invalid samples are omitted and
counted; their vehicle segment changes so replay cannot connect a false jump.
[Vehicle values](https://sumo.dlr.de/docs/TraCI/Vehicle_Value_Retrieval.html),
[simulation event/time values](https://sumo.dlr.de/docs/TraCI/Simulation_Value_Retrieval.html).

## Progress, replay counts and units

Run progress contains actual simulated seconds, configured duration, cumulative
departures/completions and current active-ID count. No queue position is invented.
Queued/input-preparation state has no fabricated simulation progress. A completed
run can finish before its configured horizon; terminal state is distinct from
an elapsed-time percentage.

Replay count samples store instantaneous active SUMO IDs and cumulative departed/
arrived totals. They are separate from the number of valid position samples or
GPU markers. The viewer may impose a disclosed rendering cap; that does not
change native active counts or run metrics. Frame timestamps use simulated
seconds. Server start/finish timestamps and worker wall seconds are different
quantities and must not be confused.

Positions derive from actual SUMO lane coordinates using the retained network
projection. The local projection is checked against native TraCI `convertGeo`.
Vehicle coordinates represent front-bumper centers, not survey measurements.
Small lane offsets relative to imported road centerlines are expected. Replay
interpolates only valid bracketed samples in the same segment and respects exact
lifecycle events; it does not manufacture motion beyond recorded samples.

## Redis observability and durable execution

The PostgreSQL run lease and immutable input snapshot govern native execution.
A transient Redis runtime-marker write failure is an observability failure: the
worker emits one fixed warning per consecutive marker outage and continues the
healthy owned child. It never forwards the Redis exception or credentials into
logs. Database heartbeat failure or lease/cancellation rejection still terminates
native execution; this exception handling does not weaken ownership checks.

The preserved M01 worker-heartbeat policy remains separate: **five consecutive
heartbeat failures** (default 5 s interval) stop the worker, including any in-flight
run. A brief Redis outage can recover without aborting a healthy simulation;
indefinite Redis-outage survival is not claimed. Restart/stale-run reconciliation
records explicit failure and requires a new tracked retry rather than rerunning
the same ambiguous attempt.

## Resource observations

Additional metrics include maximum actual active count, invalid sample count,
projection crosschecks/error, Python runner peak RSS and maximum spawned native-
child RSS. Linux `ru_maxrss` KiB is converted to bytes; macOS already reports
bytes. Native-child RSS includes the short preflight version binaries as well as
SUMO. These separate maxima are not summed and advertised as simultaneous peak
memory. Host, container and browser FPS observations belong in the verification/
performance reports with the actual renderer and measurement method.

## Comparing demand experiments

Baseline and modified runs must use the same network version, engine version,
seed, configured duration, departure distribution, vehicle class, OD policy and
sample interval. Demand volume may differ. Common random inputs reduce some
noise but do not create causal certainty or a calibrated Dubai congestion model.

Always display generated, departed, completed and incomplete counts beside means.
A lower mean among fewer completed trips can reflect censoring/gridlock rather
than improvement. Throughput uses the actual executed timeline; if early finish
times differ, interpret its denominator explicitly. Percentage changes are null
for zero or unavailable baselines. Absolute changes retain original units.
Multi-seed uncertainty analysis remains an extensible research path, not an
unimplemented fake control or an M05 forecasting result.
