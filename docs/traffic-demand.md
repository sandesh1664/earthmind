# Synthetic traffic demand

M04 produces reproducible passenger demand for the retained SUMO-compatible
Downtown Dubai / Business Bay network. It is synthetic research input, not
observed Dubai traffic, an RTA origin–destination matrix or calibrated capacity.
The initial presets are Light 500, Normal 1,000 and Heavy 2,000 trips. The baseline
and modified-demand templates use 1,000 and 1,200 trips respectively.

## Inputs and limits

`DemandConfig` is the shared strict Python contract in
`packages/contracts/src/earthmind_contracts/simulation.py`:

| Setting | Accepted values / interpretation |
| --- | --- |
| `trip_target` | Integer 1..5,000 before multiplier. |
| `demand_multiplier` | 0.1..3; effective count is Python `round(trip_target * demand_multiplier)` and must remain 1..5,000. |
| `duration_seconds` | 30..3600 simulated seconds; a virtual-time horizon, not wall time. |
| `seed` | Integer 0..2,147,483,647; recorded unchanged in scenario/run inputs. |
| `departure_distribution` | `uniform`, `poisson`, or `burst`, as defined below. |
| `vehicle_class` | `passenger` only; distribution is 100% passenger. Other classes are not offered without validation. |
| `od_policy` | `reachable_uniform` only; synthetic edge-based selection, not measured trips. |
| `sample_interval_seconds` | 1..10 simulated seconds, default 2; exact departure/arrival/teleport events are recorded every native 1 s step separately. |

The worker has a separate configurable wall-time budget (default 600 s, maximum 1,800 s),
256 MiB total output budget, 4 MiB trajectory chunks, 1 MiB manifest and one concurrent
native execution. Estimates shown before submission describe these limits; they
are not fabricated runtime or output-size measurements. Resource-limit failures
are explicit terminal failures, not successful truncated simulation results.

## Retained network and valid routes

The application selects a server-resolved artifact slug under
`/simulation-inputs`; a request never supplies a filesystem path. The worker
copies fixed input filenames into its own run workspace and verifies:

- Original OSM, converted SUMO and source→SUMO→PostGIS mapping checksums.
- Network-version UUID and UUID-derived database edge mappings.
- Bounded, regular non-symlink files; no DTD/entity declarations.
- Actual positive lane lengths, finite shapes and usable geographic projection.
- Passenger permissions and explicit SUMO lane-to-lane connections.

The production route generator uses only the imported mapped road subset,
currently 2,364 edges of the retained 2,592 ordinary converted edges. It does not
route over additional converted roads outside the imported study subset.
Source OSM ways can map to multiple split/directional SUMO edges; no one-to-one
mapping or XY-crossing junction inference is introduced.

Origins are sampled from mapped passenger edges with a permitted outgoing
connection. A directed breadth-first search determines reachable destination
edges. A seed-derived destination is selected and the actual connection path is
reconstructed and validated before writing XML. Routes must have 2..256 distinct
edges and 100..6,000 m total edge length. Each requested trip has at most 24 candidate
attempts; rejected candidates are counted. Failure to construct the complete
requested demand fails validation rather than filling it with invented routes.

This conditional edge-based sampling is not uniform over geography, population,
road length or observed trip purposes. The importer did not provide measured
boundary inflows. Boundary entry/exit candidates and disconnected components are
descriptive network audit fields. The worker's permitted edge-connection graph
is stricter than PostGIS's node-endpoint graph; their component counts need not
match. Neither graph count is silently relabeled as connected coverage.

Lane counts, vehicle defaults, junction priorities and signal programs may be
inferred by SUMO/netconvert from OSM. The native controllers do not establish
real Dubai field timing or signal verification.

## Departures and common random inputs

A SHA256-derived generator is independent for each `(seed, vehicle ordinal,
channel)`. Route and departure channels are separate. Vehicle IDs are stable
`synthetic_000000`, `synthetic_000001`, and so on. Output is sorted by requested
departure time/ID before writing a valid SUMO route file.

- **Uniform:** independent uniform requested departures between 0 and 70% of the
  configured duration. The remaining time allows completion but guarantees none.
- **Poisson:** a fixed requested number of exponential inter-arrivals with rate
  `effective_trip_count / (0.7 * duration_seconds)`. Times accumulate without
  clipping. Departures beyond the configured horizon remain generated/incomplete;
  they are not silently moved earlier or counted as completed.
- **Burst:** all requested departures at time 0. Actual SUMO insertion can be
  delayed by lane occupancy and safe following distances.

Identical configuration, source artifacts and seed produce byte-equivalent
route XML. Increasing 1,000 to 1,200 trips preserves common vehicle routes and exact
requested Uniform/Burst departures. Poisson uses common underlying exponential
draws, but its rate changes with volume, so common requested timestamps change.
The generation manifest states that distinction. Native driving randomness also
uses the saved SUMO seed; congestion and interaction differences remain genuine
model consequences, not identical independent trips.

Actual departure time is the time SUMO inserts a vehicle. It can differ from
requested departure due to 1 s simulation stepping or queues. Metrics use native
execution/TripInfo values; requested times are not substituted for observations.

## Artifacts and reproduction

Each successful run retains the route XML and `demand-manifest.json`, including
parameters, seed, effective generated count, rejected candidate count, last
scheduled departure, calculation version and route checksum. Its input snapshot
also records network/source/mapping checksums. `execution.json` records the exact
allowlisted relative SUMO command, binary/TraCI versions and relevant policies.
Raw generated archives remain under ignored local artifact storage, outside Git.

Use the Scenario Studio UI to choose a compatible imported network, validate,
save and submit. For API details see [simulation API](simulation-api.md), and
for measurements and incomplete-run interpretation see
[traffic metrics](traffic-metrics.md). No road-closure control is offered in M04.
