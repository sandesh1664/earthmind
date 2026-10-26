# M01/M02 local security boundary

The threat assumption is a trusted developer on a local Apple Silicon machine.
The stack is not configured for public or shared production access.

Only loopback web/API/PostgreSQL ports are published. Redis stays on the Docker
network. Application containers run as non-root users without Docker socket
mounts. Compose limits memory, processes, CPU use and crash restarts. Named data
volumes survive ordinary shutdown and `make clean`.

New setup generates a random local PostgreSQL password into ignored `.env` and
sets mode 0600. Existing credentials are preserved. Never use `NEXT_PUBLIC_*`
for secrets. Environment files at every directory depth are excluded from build
contexts; a synthetic Docker context regression verifies this behavior without
copying real credentials. No working secret belongs in Git.

Pydantic and Zod validate inputs/outputs. Diagnostic kinds are an allowlist;
clients cannot submit commands, SQL, paths, or arbitrary code. Queue capacity,
result expiry, HTTP deadlines and worker execution bounds limit local abuse.
Exception responses return generic error codes/messages; internal details stay
in structured application logs. CORS allows explicit development origins.

Known limits: diagnostic endpoints have no user authentication; API/migrations
use the local database administrator; local Redis does not require a password;
container OS packages are not covered by Python/npm advisory scans. A privileged
local process can access local services. These are development-only assumptions,
not protections suitable for an internet-facing deployment.

Before shared deployment, provision identity, database role separation, TLS,
managed secrets and backup/restore procedures. Dependency scan findings, fixes,
scope and unscanned packages are recorded in `verification.md`.


## M02 spatial boundary

Only `POST /api/v1/regions` changes spatial data. It requires a constant-time
comparison of `X-Earthmind-Dev-Token` against a server-side SecretStr setting.
Missing/wrong tokens return 403; a blank/absent configured token disables writes
with 503. Setup generates a random token and preserves existing configuration.
This gate is for trusted loopback development; the users table is a persistence
contract, not a deployed login/role authorization service. Public reads and
geometry calculations contain no secrets. Next's geospatial proxy permits only
allowlisted GET paths and bounded parameters, and never forwards a write token.

Spatial POST bodies are capped while streaming, before JSON parsing (default
262,144 bytes); geometry supports at most 5,000 vertices. Pagination, query
extent, nearby radius and structural-validation counts have explicit hard caps.
Graph validation also checks an aggregate 100,000-position SQL budget under a
shared parent lock before transferring geometry into Python.
PostGIS queries use bound SQLAlchemy parameters. Geometry and metric constraints,
same-network foreign keys and locked publication triggers protect direct database
writes too. Error responses omit raw database/Pydantic input values. Bounds limit
individual operation complexity; they are not a global rate-limit or per-user
quota. A 100-feature page can still contain many allowed vertices.

Public metadata serializers expose a narrow typed projection; original dataset
JSON and artifact URIs remain private. Source URLs reject credentials and local
hosts/IPs and lose query strings/fragments. This is link sanitization, not an
SSRF control: M02 does not fetch source URLs. Audit metadata rejects secret-like
JSON keys; trusted internal writers must also avoid secrets under innocuous keys
or embedded strings, which a SQL key pattern cannot semantically detect.

NetworkX structural validation is a read-only bounded report, not proof of road
accuracy or driving accessibility. Published geometry cannot be mutated through
normal SQL/API use, but the local privileged database administrator can alter
schema/triggers. Restrict roles and require authenticated authorization before
external exposure. The M01 diagnostic queue remains independently scoped and
unauthenticated on loopback; it does not consume M02 persisted simulation_runs.
