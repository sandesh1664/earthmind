# M01 security boundary

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
