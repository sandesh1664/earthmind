# Service contracts

`earthmind_contracts` defines the Pydantic API wire models. `schema/` contains
their committed JSON schemas; pytest checks them against the Python models.
`generate_types.py` copies those schemas into deterministic TypeScript literals
in `src/schema.ts`. `src/index.ts` derives the health types, status enums, and
readiness validation from those literals. Versioned liveness, capabilities,
SUMO runtime records, diagnostic requests and job lifecycle schemas are also
generated. `src/platform.ts` uses Zod's JSON-schema converter against those
canonical literals and derives the corresponding TypeScript output types.
The proxy rejects unexpected fields, matching the schemas'
`additionalProperties: false` boundary.

`make lint` checks generated output without modifying it, and the frontend test
suite compares the TypeScript literals with the canonical JSON schemas. After
refreshing the JSON schemas below, regenerate and check the TypeScript output:

```sh
uv run --locked python packages/contracts/generate_types.py
uv run --locked python packages/contracts/generate_types.py --check
```

M01 endpoints:

- `GET /health/live`: `LiveHealth`, HTTP 200; API process only.
- `GET /health/ready`: `ReadyHealth`, HTTP 200 if PostgreSQL/PostGIS, Redis, and worker heartbeat checks pass; HTTP 503 otherwise. Each dependency probe has a bounded deadline. Responses contain statuses without connection details.
- `GET /api/v1/health`: `ApiHealth`, process liveness and application version.
- `GET /api/v1/ready`: versioned `ReadyHealth` readiness response.
- `GET /api/v1/system/capabilities`: `SystemCapabilities`, live service capabilities and a fresh verified SUMO runtime record when available.
- `POST /api/v1/diagnostics`: strict `DiagnosticRequest`; HTTP 202 with `DiagnosticJob` for a worker diagnostic or SUMO runtime verification.
- `GET /api/v1/diagnostics/{job_id}`: `DiagnosticJob` with the queued, running, succeeded or failed state.

The browser uses the same-origin Next.js proxies. Diagnostic submissions require
JSON and reject a foreign `Origin`, preventing a simple cross-site request from
being promoted into a privileged JSON backend request. Readiness JSON keeps its
canonical shape; the proxy adds `X-Earthmind-Api-Reachable` to distinguish an
unreachable API from an API reporting degraded dependencies.

The worker writes the UTC heartbeat timestamp to `earthmind:worker:heartbeat` every five seconds with a 30-second expiry. Both API readiness and the worker health command require a positive TTL. The M01 deployment has one worker replica; this shared marker is not intended to distinguish multiple replicas. No simulation jobs or domain entities are introduced.

To refresh the schemas from the repository root:

```sh
uv run python - <<'PY'
import json
from pathlib import Path
from earthmind_contracts import (
    ApiHealth, DiagnosticJob, DiagnosticRequest, LiveHealth, ReadyHealth,
    SumoRuntimeRecord, SystemCapabilities,
)
for model in (
    LiveHealth, ReadyHealth, ApiHealth, SumoRuntimeRecord,
    SystemCapabilities, DiagnosticRequest, DiagnosticJob,
):
    Path(f"packages/contracts/schema/{model.__name__}.json").write_text(
        json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
    )
PY
```
