# ADR 0002: Python 3.12, FastAPI, and async database sessions

Status: accepted for M01.

Use Python `>=3.12,<3.13` and FastAPI/Pydantic v2. The host's default Python 3.14
is not the project interpreter. The selected Python series is verified with
locked installation, tests, and native container execution.

Use SQLAlchemy 2 async sessions with the psycopg 3 driver. Create infrastructure
inside application lifespan, not during module import. Inject sessions into
request handlers, commit on successful completion, roll back exceptions, and
dispose the engine at shutdown. Keep liveness independent of dependencies and
readiness based on real bounded probes.

Lock application/test dependencies with uv. Pin the dependency-free build
backend to `uv_build==0.11.12`, matching the bundled build tool, and use locked
sync/run commands so verification cannot silently rewrite the lock.
