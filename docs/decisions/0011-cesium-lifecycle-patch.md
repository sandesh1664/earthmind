# ADR 0011 — Explicit viewer cleanup and a reproducible Cesium cache patch

Status: accepted for M03, 2026-10-27. The final thirty-cycle local stability
gate passed after these changes. Exact measurements, software-renderer scope
and retained failures are recorded in [performance](../performance.md) and
[verification](../verification.md).

## Context and observed failure

Removing the canvas and calling `Viewer.destroy()` did not satisfy M03's
lifecycle requirement. The initial thirty-cycle test retained approximately
55 DOM nodes and 14 event listeners per mount/unmount cycle. A small range in
collected JavaScript heap samples was insufficient evidence of cleanup: retained
DOM nodes and listener counts still increased. Those failed runs remain evidence,
not successful lifecycle checks.

Inspection of the installed CesiumJS 1.146.0 / `@cesium/engine` 26.4.0 sources
identified separate ownership and cache problems:

- The widget creates its public `screenSpaceEventHandler`; its destruction path
  did not destroy that handler. `Viewer.destroy()` removed click actions, which
  does not remove the handler's DOM/document event listeners.
- `CreditDisplay` injected an instance stylesheet that remained in the document
  after destruction.
- Globe terrain index arrays carried an `indexBuffers` object keyed by
  `context.id`. Shared terrain data retained those arrays beyond a viewer's
  lifetime. The object retained an index buffer, including its `_gl` reference,
  which retained the WebGL context and canvas even after buffer destruction.

The filtered actual heap-retainer paths show this last chain:

```text
shared terrain indices
  → indices.indexBuffers
  → context-id entry
  → index buffer
  → WebGL context
  → detached canvas
```

See [filtered retainer paths](../evidence/m03/canvas-retainer-paths-excluding-inspector.json).
This is a recorded path from the inspected browser, not a claim that every
possible retaining path was enumerated. Large raw heap snapshots are excluded
from Git.

## Trace control

Browser instrumentation itself affected the measurements. A seven-cycle A/B
control after the first cleanup corrections observed about four additional
nodes/four listeners per cycle without tracing, versus 55 nodes/eight listeners
with tracing. [Actual trace-control observations](../evidence/m03/trace-control-observations.json).
Turning tracing off removed an instrumentation confounder; it did not resolve
the residual application retention.

Memory/DOM lifecycle profiling therefore runs with Playwright tracing off.
Functional browser tests keep their separate trace policy for failure diagnosis.
Heap, DOM and listener observations are reported together. Software-rendered
Chromium measurements do not establish Apple GPU performance or GPU-memory use.

## Decision

Keep the application cleanup path explicit and idempotent:

1. Cancel the camera flight and remove application-owned scene, camera and DOM
   event subscriptions.
2. Dispose provider resources, region entities, batched road geometry and point
   collections; invalidate pending asynchronous resource adoption.
3. Destroy the public `viewer.screenSpaceEventHandler` if it is still alive,
   then call `Viewer.destroy()`. The pinned Viewer already checks whether that
   handler is destroyed.
4. Release this viewer's owned WebGL context through the optional public
   `WEBGL_lose_context` extension after SDK resource destruction.
5. Remove only credit styles synchronously introduced by this viewer's
   constructor. Do not remove unrelated styles or suppress attribution while
   the viewer is alive.

The version-specific terrain cache cannot be corrected solely through these
public cleanup calls. Apply a small, source-controlled dependency patch to
`@cesium/engine` 26.4.0:

```text
indices.indexBuffers || {}              → indices.indexBuffers || new WeakMap()
indexBuffers[context.id]                → indexBuffers.get(context)
indexBuffers[context.id] = indexBuffer  → indexBuffers.set(context, indexBuffer)
```

The key is the actual engine context object. While that context is reachable,
the shared index buffer remains available and existing reference-count behavior
is unchanged. When the context becomes unreachable, the WeakMap entry does not
keep it alive. WeakMap ephemeron semantics also avoid rooting a dead key through
its associated value. Buffer creation, destruction checks and active-context
reference counting remain in the original SDK code.

This is an explicit build-time vendor-source delta. Application code does not
reach into a live SDK's private cache, monkey-patch its runtime methods, or use
private `_gl` fields to perform the repair. Private-field names above describe
inspected evidence only.

## Reproducibility and delivery

The patch is retained as
[`patches/@cesium+engine+26.4.0.patch`](../../patches/@cesium+engine+26.4.0.patch).
The root workspace pins `patch-package` 8.0.1 and applies patches with
`postinstall: patch-package --error-on-fail`. Docker copies `patches/` before
`npm ci`, so the native production build receives the same change as local
installation.

The asset/build guard in
[`copy-cesium-assets.mjs`](../../scripts/copy-cesium-assets.mjs) checks the installed
Cesium version, engine version and exact patched `GlobeSurfaceTile.js` SHA-256
before preparing assets. It fails closed when the patch is absent or the source
is incompatible. The expected hash is maintained in that guard as the single
executable source of truth; it is not inferred from a claimed successful build.
The npm lock retains original package versions/integrities, and the committed
patch records the intentional transformation after installation.

Cesium's license and third-party notices remain included with the hosted runtime
assets. The three-line source delta and this decision identify the modification.
No upstream issue, pull request or remote push was performed as part of this
local milestone.

## Consequences and upgrade rule

This creates a maintenance obligation for the pinned Cesium version. On any SDK
upgrade, inspect the upstream ownership and cache implementations, review whether
the patch is still needed, regenerate the delta and guard only when appropriate,
and rerun the unchanged lifecycle regressions. Remove the patch only after
actual mount/unmount, DOM/listener and heap checks verify the replacement.

A five-cycle functional success, a JavaScript-heap-only plateau, canvas removal,
or disabled tracing alone is insufficient to declare the lifecycle requirement
satisfied. The final thirty-cycle results, functional picking/rendering checks,
asset checks, production build and any remaining limitations belong in the
verification and performance reports.
