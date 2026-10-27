# M03 performance and lifecycle observations — 2026-10-27

These are actual local browser measurements, not Dubai traffic metrics or a
production throughput benchmark. The environment is an Apple Silicon host, but
Chromium reported **SwiftShader software rendering**. Apple GPU/Metal FPS and
physical-device testing remain NOT RUN.

## Method

`uv run --locked python scripts/verify_city_performance.py` creates an explicitly
synthetic temporary region/source/draft network in actual PostGIS:300 nodes and
300 two-position road segments. The real Next/FastAPI endpoints serve all data;
there are no mocked responses or in-memory replacement roads. The script always
attempts removal of only its own UUID-identified rows in a finally block and
refuses cleanup if ownership/status changed. The original M02 fixture is never
reset or modified. Every run, including failures, completed owned-row cleanup.

One Chromium page repeats 30 City Explorer mounts, real region/network selection,
300-road native geometry readiness, feature selection, and return to Overview.
After each unmount it waits 1000 ms for asynchronous cleanup/health requests,
requests CDP garbage collection and records JSHeapUsedSize plus DOM/listener
counts. Timings include Playwright actionability/scrolling and interface work.
The feature inspector must show the actual stored provisional edge identifier.
One live canvas must exist while mounted and none after unmount.

Memory profiling explicitly disables DOM snapshot tracing. A controlled7-cycle
A/B showed the tracer inflated retention: no-trace4 nodes/4 listeners per cycle
versus trace-on55 nodes/8 listeners after the first cleanup change. Functional
browser tests retain failure traces separately. No DOM.disable, private cache
flush or application-state reset is used to force the final profile to pass.

The final gate is unchanged: after 20 warm-up cycles, the last 10 samples must
vary by less than 1 MiB JS heap,25 DOM nodes and10 event listeners. Owned SDK credit
styles must return to their pre-viewer count after every unmount. All 30
selection observations must finish within 5 seconds. These are bounded local
regression thresholds, not universal rendering guarantees.

## Actual final result

Status: PASS for the stated local stability and functional gates.

| Observation | Actual result |
| --- | --- |
| Complete repeated cycles |30 |
| Native displayed geometry per cycle |300 roads +300 intersections |
| View load, including selection/requests/worker readiness |1147–4376 ms; median 1694.5 ms |
| Feature-selection observation |38–853 ms; median529.0ms |
| DOM nodes after each unmount/GC |2142 throughout all 30 samples |
| JS event listeners after each unmount/GC |458 throughout all 30 samples |
| Last 10 JS-heap range |25,508,980–25,803,200bytes |
| Last 10 heap variation |294,220bytes (0.281 MiB) |
| Delayed final post-unmount JS heap |24,813,632bytes after additional2-second settlement/GC |
| Page errors |0 |
| Graphics API |WebGL 2.0 (OpenGL ES 3.0 Chromium) |
| Renderer |ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (LLVM 10.0.0) (0x0000C0DE)), SwiftShader driver) |

Raw arrays, driver and scope: [performance-observations.json](evidence/m03/performance-observations.json).
Actual command output: [performance-patched.log](evidence/m03/performance-patched.log).
No FPS target is promoted to a measured claim. The opt-in diagnostics panel
shows actual rendered-frame samples, but idle request-render time is not camera
animation throughput. JS heap excludes GPU allocations and browser-process RSS.
The sample still warms up initially; the result establishes the stated late-run
variation gate and stable DOM/listeners, not an indefinitely flat heap.

## Defects discovered and corrected

The first five-cycle check passed display/selection but heap increased; this did
not establish memory stability. A fifteen-cycle extension also showed warm-up
and incomplete evidence. The first thirty-cycle gate failed:55 DOM nodes and14
listeners accrued per mount. Explicit public input-handler destruction reduced
listeners to8 per mount, but DOM still grew; that run also failed. We retained
both failures instead of loosening the thresholds.

Controlled tracing and heap-retainer analysis then separated instrumentation
from real SDK ownership problems. CreditDisplay appended per-instance style
elements to the head without removing them. The global terrain-grid cache held
indexBuffers by context UUID, retaining destroyed Buffer._gl and old canvases.
The integration now removes owned styles, destroys the public input handler,
destroys Viewer and optionally loses its owned WebGL context. The minimal
version-locked SDK source patch changes only the terrain-buffer dictionary to a
WeakMap keyed by Context, retaining active reuse/reference counting while
allowing dead contexts to be collected.

[ADR0011](decisions/0011-cesium-lifecycle-patch.md) documents evidence and the
reproducible patch workflow. Raw heap snapshots remain temporary/uncommitted;
only filtered retainer paths and small measurement results are retained.

## Rendering safeguards and limits

Roads use batched GroundPolylinePrimitive geometry and stable typed pick IDs;
intersections use a point collection with distant-camera visibility limits.
Region polygons/holes and outlines are bounded. Layer visibility and highlight
updates do not rebuild all geometry on ordinary React changes. Request-render
mode draws on actual scene work; pending geometry requests frames until ready.

Camera pose is sampled at most every50 ms;350 ms meaningful stability precedes the
separate350 ms viewport-query debounce. Bbox requests are clipped to the selected
region and at most one degree per axis. Each layer retains at most500 features
and25,000 coordinate positions; HTTP pages are100 and client responses4 MiB.
Inactive viewport query data uses gcTime0. Old region/network requests are
cancelled through Next to the backend; geometry/selection is cleared by scope.

The two-point synthetic fixtures need no shape simplification. We preserve their
coordinates rather than inventing a generalization accuracy policy. Real dense
imports, production load/concurrency, long-duration GPU/RSS behavior and physical
Apple GPU performance remain unverified future work. No uniform licensed
building coverage or real-world network accuracy follows from this test.


## Real geography recovery scope

The preserved M03 figures above concern the eight-road/300-road fixture and
pre-recovery UI; they are historical, not a current real-city benchmark. Recovery
adds 2,364 stored real roads, 1,560 nodes and 402 source-height building models.
Only the bounded viewport subset (500 features/25k positions) is interactive at
once. Self-hosted context is separately capped at 12 MiB/12k features/150k positions.

Initial actual fresh-context software-rendered road-ready observations were
19–27s with unnecessary ground classification. Ellipsoid-specific context
rendering reduced subsequent measured ready observations to about 5–7 s in the
recorded desktop/tablet checks. These are scenario observations, not a controlled
hardware comparison or physical Apple GPU FPS. Exact final per-viewport timings
and native fullscreen/lifecycle results are retained in verification.md/evidence.
No current thirty-cycle real-context stability or GPU memory claim is made from
the earlier M03 benchmark.
