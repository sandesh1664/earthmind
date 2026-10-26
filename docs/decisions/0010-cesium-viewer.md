# ADR 0010 — Browser-owned Cesium scene over existing PostGIS APIs

Status: accepted for M03, 2026-10-27.

Use pinned CesiumJS in a lazy browser-only module inside the existing dashboard.
Keep native scene state in a dedicated mount-scoped controller, React UI state
in components and backend state in TanStack Query. No alternate geographic
engine, database or source of truth is added. Existing M01 contracts and M02
migrations remain unchanged.

M02's indexed bbox/pagination endpoints already serve the required map data.
Extend only their existing public frontend schema allowlist for fields needed by
the inspector. Do not introduce a second geographic business-logic service.
Bound feature/coordinate/page budgets and debounced camera queries on the client
are rendering safeguards in addition to backend query constraints.

Host Cesium's four runtime asset directories and license notices locally from
the exact locked package. Production standalone deployments must copy public
assets explicitly. Use packaged Natural Earth imagery and ellipsoid terrain as
a credential-free, lawful fallback. Optional ion imagery, terrain and OSM
Buildings require a deliberately public scoped token; no token is invented or
borrowed from a bundled Cesium default.

Keep optional-provider errors independent of backend overlays and viewer health.
Retain attribution; do not infer real streets/signals from synthetic fixtures.
Selection categories and stable IDs distinguish intersections, roads and provider
buildings. Metadata is text, never injected HTML. Missing properties stay missing.

No geographic schema migration is needed for M03. Real building access may remain
BLOCKED without a configured account/token while independently executable viewer
requirements are verified. Measure browser rendering and lifecycle behavior;
responsive/software-rendered test results do not establish physical Apple GPU
performance. M04 work requires separate authorization.

Actual thirty-cycle testing found55retainedDOMnodes/14listenersperremount
despite Viewer.destroy and removed click actions. Installed SDK source confirmed
its widget input handler was not destroyed. Explicit public handler destruction
is therefore part of this integration's ownership contract, followed by Viewer
destruction and optional WebGL context release. The unchanged long-run stability
gates and retained failed run document why canvas removal alone is insufficient.
