# ADR 0001: monorepo and modular monolith

Status: accepted for M01.

Keep one versioned repository with npm and uv workspaces. Next.js is the web
boundary; FastAPI is a modular application; one separately executable Python
worker consumes diagnostic jobs. Shared Pydantic/JSON/TypeScript contracts live
in `packages/contracts`.

Retain the established installable `src/earthmind_api` and
`packages/simulation-worker` layouts rather than duplicating them under
`apps/api/app` and `services/`. These paths are a justified refinement of the
suggested tree: they support ordinary wheel builds, one Python lock, and small,
clear module boundaries. The worker remains a separate executable/service.

This keeps development and releases manageable by a small team. M01 introduces
no independently deployed domain microservices and no future traffic models.
