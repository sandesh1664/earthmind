# ADR 0008: local-first Compose and development security boundary

Status: accepted for M01.

Use Docker Compose with a private service network and named data volumes. Bind
web/API/PostgreSQL host ports to loopback; Redis has no published port. Start
one migration process to completion before application services. Use one worker,
conservative resource limits, non-root application users, bounded restart
policies, and no Docker socket mounts.

Bootstrap creates a random local database password for a new `.env`, preserves
existing values, and sets owner-only permissions. Git and Docker recursively
exclude environment files. The worker receives no database credentials.

This is a local development foundation. API and migration database credentials
remain privileged, and diagnostic endpoints have no user authentication. Shared
or public deployment requires separate database roles, TLS/ingress, identity,
secret provisioning, and tested backups. These limits are explicit rather than
represented by fake authentication or production-ready claims.
