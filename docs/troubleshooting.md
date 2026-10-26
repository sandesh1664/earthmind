# Troubleshooting

- Docker unavailable: start Docker Desktop and rerun `sh scripts/verify_environment.sh`.
  An engine architecture other than ARM64 is a blocker; do not enable emulation.
- Port occupied: inspect ports 3000, 8000 and 5434 with `lsof -nP -iTCP:<port>`.
  Identify the owning project before changing anything. EARTHMIND uses its own
  Compose project; never prune Docker or delete unrelated volumes.
- Startup failure: `make status` and `make logs` show health and migration output.
  Fix the reported failure, then repeat `make migrate` and `make dev`.
- Database not ready: inspect database connectivity and Alembic state. API
  liveness should remain available while readiness reports HTTP 503.
- Worker or SUMO unavailable: inspect worker logs and its runtime verification
  command. A package being installed is not proof that the fixture executed.
  Capabilities must remain false until actual verification succeeds.
- Queue capacity reached: HTTP 429 is an intentional bound. Inspect the worker;
  do not add unbounded queues or uncontrolled retries.
- Changed password with existing volume: rotate the database credential with
  SQL and update `.env` together. Copying a new environment value does not change
  a database's stored password.
- Stale contracts: run `uv run --locked python packages/contracts/generate_types.py`
  after updating canonical schemas, then run lint and tests.
- Dependency download failure: preserve the exact error and lockfiles, verify
  registry access, and retry. Never claim an unexecuted test passed.
