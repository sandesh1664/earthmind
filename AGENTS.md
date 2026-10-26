# EARTHMIND engineering instructions

- M01 establishes the Dubai urban intelligence platform's local foundation.
  Keep traffic ingestion, AI forecasting, digital twins, and production scenarios
  outside this milestone.
- Use Python 3.12 and native Linux ARM64 containers. Never enable AMD64 emulation
  to hide an incompatible dependency.
- Keep JavaScript dependencies in the npm workspace lock and Python dependencies
  in the uv workspace lock. Use `uv run --locked` for verification commands.
- Keep API routes thin, database access in injected sessions, and SUMO execution
  in the worker process. Accept only typed diagnostic jobs, never shell input.
- Run `make lint typecheck test`, a production build, migrations, and real
  deployment smoke checks before claiming completion. Keep failures and blocked
  checks visible in `docs/verification.md` with command, exit status, and evidence.
- Preserve `.env`, user datasets, named volumes, and unrelated Docker projects.
  `make clean` must never remove persistent data.
- Never commit working credentials, caches, installed dependencies, or generated
  simulation data archives. Small, clearly labeled verification fixtures and
  textual evidence are appropriate.
- Do not push or begin M02 without explicit authorization.
