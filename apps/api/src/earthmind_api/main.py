import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast
from uuid import UUID

from earthmind_contracts import (
    ApiHealth,
    CapabilityFlags,
    DiagnosticJob,
    DiagnosticRequest,
    LiveHealth,
    ReadyHealth,
    SystemCapabilities,
)
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from earthmind_api.dependencies import HealthChecks, Infrastructure, readiness
from earthmind_api.diagnostics import DiagnosticsStore, QueueFullError
from earthmind_api.geometry import SpatialInputError
from earthmind_api.geospatial_routes import router as geospatial_router
from earthmind_api.logging import configure_logging
from earthmind_api.request_limits import GeoBodyLimitMiddleware
from earthmind_api.settings import Settings

logger = logging.getLogger(__name__)


def get_checks(request: Request) -> HealthChecks:
    return cast(HealthChecks, request.app.state.infrastructure)


def get_store(request: Request) -> DiagnosticsStore:
    infrastructure = cast(Infrastructure, request.app.state.infrastructure)
    return DiagnosticsStore(infrastructure.cache, infrastructure.settings.health_timeout_seconds)


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        infrastructure = Infrastructure(configuration)
        application.state.infrastructure = infrastructure
        await infrastructure.open()
        try:
            yield
        finally:
            await infrastructure.close()

    application = FastAPI(title="EARTHMIND API", version="0.1.0", lifespan=lifespan)
    application.state.settings = configuration
    application.add_middleware(
        GeoBodyLimitMiddleware, max_bytes=configuration.geo_max_request_bytes
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=configuration.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type"],
    )

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_request",
                    "message": "Request validation failed",
                    "fields": [
                        {"location": list(error["loc"]), "code": error["type"]}
                        for error in _error.errors()[:20]
                    ],
                }
            },
            status_code=422,
        )

    @application.exception_handler(SpatialInputError)
    async def spatial_input_error(_request: Request, error: SpatialInputError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "invalid_spatial_request", "message": str(error)[:256]}},
            status_code=422,
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, error: StarletteHTTPException) -> JSONResponse:
        codes = {
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            413: "payload_too_large",
            429: "queue_full",
            503: "dependency_unavailable",
        }
        messages = {
            403: "Developer write authorization required",
            404: "Resource not found",
            409: "Resource conflicts with existing data",
            413: "Request exceeds its configured size limit",
            429: "Diagnostic queue is full",
            503: "Service dependency unavailable",
        }
        return JSONResponse(
            {
                "error": {
                    "code": codes.get(error.status_code, "request_failed"),
                    "message": messages.get(error.status_code, "Request failed"),
                }
            },
            status_code=error.status_code,
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(Exception)
    async def unhandled_error(_request: Request, error: Exception) -> JSONResponse:
        logger.error("Unhandled request error", exc_info=(type(error), error, error.__traceback__))
        return JSONResponse(
            {"error": {"code": "internal_error", "message": "An internal error occurred"}},
            status_code=500,
        )

    @application.get("/api/v1/health", response_model=ApiHealth, tags=["health"])
    async def api_health(response: Response) -> ApiHealth:
        response.headers["Cache-Control"] = "no-store"
        return ApiHealth()

    @application.get("/health/live", response_model=LiveHealth, tags=["health"])
    async def live(response: Response) -> LiveHealth:
        response.headers["Cache-Control"] = "no-store"
        return LiveHealth()

    @application.get(
        "/api/v1/ready",
        response_model=ReadyHealth,
        responses={503: {"model": ReadyHealth}},
        tags=["health"],
    )
    @application.get(
        "/health/ready",
        response_model=ReadyHealth,
        responses={503: {"model": ReadyHealth}},
        tags=["health"],
    )
    async def ready(
        response: Response, checks: Annotated[HealthChecks, Depends(get_checks)]
    ) -> ReadyHealth:
        result = await readiness(checks, configuration.health_timeout_seconds)
        response.status_code = 200 if result.status == "ok" else 503
        response.headers["Cache-Control"] = "no-store"
        return result

    @application.get(
        "/api/v1/system/capabilities", response_model=SystemCapabilities, tags=["system"]
    )
    async def capabilities(
        response: Response,
        checks: Annotated[HealthChecks, Depends(get_checks)],
        store: Annotated[DiagnosticsStore, Depends(get_store)],
    ) -> SystemCapabilities:
        result = await readiness(checks, configuration.health_timeout_seconds)
        runtime = None
        if result.checks.redis == "ok" and result.checks.worker == "ok":
            try:
                runtime = await store.runtime()
            except Exception:
                logger.warning("Runtime verification record unavailable")
        response.headers["Cache-Control"] = "no-store"
        return SystemCapabilities(
            capabilities=CapabilityFlags(
                database=result.checks.database == "ok",
                redis=result.checks.redis == "ok",
                worker=result.checks.worker == "ok",
                simulation_runtime=runtime is not None,
            ),
            runtime=runtime,
        )

    @application.post(
        "/api/v1/diagnostics", response_model=DiagnosticJob, status_code=202, tags=["diagnostics"]
    )
    async def submit_diagnostic(
        diagnostic: DiagnosticRequest,
        response: Response,
        store: Annotated[DiagnosticsStore, Depends(get_store)],
    ) -> DiagnosticJob:
        try:
            job = await store.enqueue(diagnostic.kind)
        except QueueFullError as error:
            raise HTTPException(status_code=429) from error
        except Exception as error:
            raise HTTPException(status_code=503) from error
        response.headers["Location"] = f"/api/v1/diagnostics/{job.job_id}"
        response.headers["Cache-Control"] = "no-store"
        return job

    @application.get(
        "/api/v1/diagnostics/{job_id}", response_model=DiagnosticJob, tags=["diagnostics"]
    )
    async def diagnostic_result(
        job_id: UUID,
        response: Response,
        store: Annotated[DiagnosticsStore, Depends(get_store)],
    ) -> DiagnosticJob:
        try:
            job = await store.get(job_id)
        except Exception as error:
            raise HTTPException(status_code=503) from error
        if job is None:
            raise HTTPException(status_code=404)
        response.headers["Cache-Control"] = "no-store"
        return job

    application.include_router(geospatial_router)
    return application


app = create_app()
