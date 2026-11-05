# Scenario Studio, Simulation Laboratory and Analytics

M04 adds form-driven synthetic demand experiments to the existing EARTHMIND
workspace. These pages use the same-origin `/api/simulation` proxy and durable
FastAPI/PostgreSQL records. The browser receives no private development write
credential. City Explorer retains its imagery, modes, OSM roads and native Viewer.

## First experiment

1. Open Scenario Studio from the navigation.
2. Select a retained SUMO-compatible Dubai network. Read its actual conversion
   checksum, OSM source checksum, mapped edge count and validation warnings.
3. Choose Light (500), Normal (1,000) or Heavy (2,000) synthetic trips, or enter a
   bounded target. These presets are not measured Dubai traffic volumes.
4. Configure duration, seed, uniform/Poisson/burst departures, demand multiplier
   and trajectory sample interval. Uniform requested departures span the first 70% of the simulation horizon, leaving a clearance period. Poisson uses the corresponding target rate without clipping late requests; Burst requests all departures at zero. These are model assumptions, not measured patterns. Passenger vehicles and reachable uniform edge
   pairs are the initial supported class and OD policy.
5. Select **Run validation**. The exact form is saved and checked by the backend.
   **Save scenario** also persists the configuration and its reported validation.
6. Start the validated configuration. Editing any configuration field requires
   validating that exact configuration again. Submission opens its tracked run in
   Simulation Laboratory.

The client and backend bound target/effective demand to 5,000 trips, simulation
horizon to 30–3,600 simulated seconds and sampling to integer 1–10 second intervals.
Demand multipliers are 0.1–3 and effective counts follow Python half-even rounding.
Seeds are integers 0–2,147,483,647. Native runtime/output/time limits remain enforced
by the worker; these form bounds do not override them. The resource panel shows a
conservative unique vehicle/time sample upper bound including time zero, not an
execution-time or GPU-memory prediction.

Saved configurations are immutable. Loading a saved scenario populates the form;
changes create another saved scenario rather than rewriting a running experiment.
An idempotency key is retained after a failed submission transport so retrying that
same operation cannot silently create a second run. A deliberate successful new
submission receives its own tracked run.

## Runs, cancellation and retries

Simulation Laboratory lists persisted runs with bounded pagination and polls the
current run while it is queued/running. It displays actual simulation seconds,
counts and bounded worker events; queue position and wall-clock completion are not
invented. Before the first SUMO progress report, the UI states that it is waiting.
Event timestamps describe wall-clock recording; progress describes simulated time. Successful runs also expose their checksum-verified SUMO engine log as escaped text, bounded to 2 MiB; oversized logs produce an explicit display error rather than a silently truncated success.

Cancellation is a request until the worker confirms a terminal state. A queued or
running run is never displayed as cancelled merely because the button was pressed.
Failed/cancelled runs retain their error and audit trail. **Retry as new attempt**
creates a new UUID linked to the parent, with the same scenario/seed and a new
tracked attempt number; it does not rewrite the previous outcome.

A page reload does not remove runs: reopen Simulation Laboratory and choose the
persisted record. Successful runs expose actual metrics, JSON reproducibility
reports, CSV metrics and **Open vehicle replay**. The replay bridge opens the
existing City Explorer with the recorded run ID; the replay engine verifies the
selected network and bounded artifact chunks. See [replay-engine.md](replay-engine.md).

## Analytics and comparison

Analytics displays only published successful-run measurements. Missing averages
remain unavailable (—), while measured zero counts remain zero. Active vehicle
counts use recorded simulation-time samples. No chart is prepopulated with fake
traffic or UI demonstration values. JSON/CSV exports come from the actual API.

Use baseline/modified templates for 1,000 and 1,200 synthetic trips, preserving
network, seed, engine, horizon, departure model, class, OD policy and sample interval.
The backend checks compatibility before persisting a comparison. The comparison
shows baseline, modified, absolute change and percentage change only when defined.
Zero/null baselines do not produce percentages. Completion and incomplete counts
must be read alongside completed-trip averages; fewer completions cannot establish
a traffic improvement. One synthetic experiment is not causal proof or an RTA
forecast. Multiple seeds and calibration remain research work.

Road closures and signal-timing controls are deliberately absent from these forms;
no unverified routing intervention is offered as functional.

## Error handling and browser verification

Network/provider failures, invalid scenarios, queue saturation, failed runs,
empty lists and unavailable measurements have explicit states. Responses are
validated through shared Zod contracts and a bounded 4 MiB client response budget.
Mutations carry a same-origin intent header and submission idempotency key; private
API authorization is injected by the Next server, never by a browser token field.

The actual expensive browser pipeline is an explicit local acceptance run:

```sh
EARTHMIND_SIMULATION_E2E=true npm run test:browser -- simulation.spec.ts --project=desktop --workers=1
```

It requires deployed M04 services, the existing local write gate, retained real
Dubai inputs and native picking diagnostics. It creates actual 1,000/1,200-trip
experiments; no mocked responses can establish success. Tablet/mobile skip this
expensive duplicate workflow explicitly. The command is an instruction, not proof
that it ran: consult [verification.md](verification.md) for actual results.
