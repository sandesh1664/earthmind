# ADR 0009 — M02 spatial persistence and local write boundary

Status: accepted, 2026-10-26.

## Context

M01 has one SQLAlchemy Base, lazy async engine, injected transaction/session
lifecycle, settings system, PostGIS image and Alembic environment. M02 must keep
these and represent reproducible network/scenario inputs before real ingestion.

## Decision

Extend the existing components with thirteen tables and additive revisions 0003
and 0004. Keep M01 system_metadata and health/capability contracts unchanged.
Use GeoAlchemy2 typed geometry with 2D EPSG:4326, explicit longitude/latitude,
PostGIS generated geodesic area/length and a covered geography centroid, falling
back to a representative interior point. Shapely validates bounded geometry;
pyproj independently checks geodesic area. GiST geometry and plain-geography
expression indexes serve actual bounded spatial queries. A geography typmod cast
does not match that expression index, so the service uses `as_geography` and a
real EXPLAIN regression protects the exact SQL form.

Use explicit endpoint intersection UUIDs and composite same-network foreign
keys. NetworkX reports weak connectivity without inventing junctions at line
crossings. Lock parent rows when changing children/publishing; database triggers
freeze published/archived network content and referenced region boundaries.
Corrections create new versions. Scenario/demand same-network constraints and
strict run/timestamp rules are database-backed. These are persistence contracts;
M01 diagnostics stay in their existing Redis workflow.

Keep source metadata/artifact locations private and serialize typed allowlists.
The project-generated Dubai fixture has deterministic UUIDs/provisional feature
IDs, a canonical content checksum, explicit synthetic flags and proprietary
synthetic license metadata. It makes no official boundary, observed street,
signal or SUMO-conversion claim. Seed validates before publication and refuses
partial/incompatible pre-existing fixtures instead of overwriting research data.

M01 has no user identity service. Keep all host bindings on loopback and protect
region creation with a generated server-only development token. Do not create
fake login endpoints; users/password hashes remain schema contracts. Shared
exposure requires real identity/authorization, least-privilege roles, TLS,
managed secrets and operational controls before deployment.

## Consequences

Validation has VALID, VALID_WITH_WARNINGS, INVALID and NOT_VALIDATED states;
unknown connectivity counts are null. A report of valid synthetic topology does
not establish real-world accuracy. Work stays bounded by request/query/vertex
budgets. Before graph loading, SQL checks aggregate positions under a shared
parent lock coordinated with child-write triggers; a feature count alone does
not bound the sum of geometry coordinates. No real OSM extraction, SUMO conversion, scenario execution, traffic
prediction or M03 features are introduced.

Migration 0003 is frozen after application; 0004 separately fixes timestamp
consistency and aligns stored vertex budgets with serialization. Schema
comparison and isolated M01-to-head upgrades are tested. A downgrade that would
drop populated M02 research tables raises an error before any destructive DDL;
normal development volumes are never reset to make migration tests pass.

See [geospatial architecture](../geospatial-architecture.md),
[schema](../database-schema.md), [security](../security.md) and the actual
[verification record](../verification.md).
