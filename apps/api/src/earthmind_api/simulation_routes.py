"""Versioned M04 REST boundary. Native simulations never run in HTTP handlers."""

import logging
from collections.abc import Awaitable
from typing import Annotated, Literal, cast
from uuid import UUID

from earthmind_contracts.simulation import (
    SIMULATION_QUEUE_KEY,
    ComparisonCreate,
    ComparisonResponse,
    ReplayManifest,
    RunCreate,
    RunEventResponse,
    RunMetricsResponse,
    RunResponse,
    ScenarioCreate,
    ScenarioResponse,
    ScenarioValidation,
    SimulationNetworkResponse,
    SimulationPage,
    TrajectoryChunk,
)
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from earthmind_api.dependencies import Infrastructure, get_session
from earthmind_api.geospatial_models import Scenario, SimulationRun
from earthmind_api.geospatial_routes import Configuration, PageLimit, PageOffset
from earthmind_api.security import require_dev_write
from earthmind_api.simulation_models import SimulationComparison, SimulationEvent
from earthmind_api.simulation_networks import network_catalog, validate_network_input
from earthmind_api.simulation_service import (
    NetworkValidationCache,
    artifact_payload,
    cancel_run,
    compare_runs,
    create_scenario,
    export_run,
    get_run,
    get_scenario,
    replay_chunk,
    replay_manifest,
    run_metrics,
    run_response,
    scenario_response,
    submit_run,
)

# M04 mutations must commit before 201/202 reaches a client or a Redis hint.
# Default request-scoped yield cleanup occurs after response delivery in FastAPI.
Session = Annotated[AsyncSession, Depends(get_session, scope="function")]

router = APIRouter(prefix="/api/v1", tags=["simulations"])
logger = logging.getLogger(__name__)


async def notify_worker(infrastructure: Infrastructure, run_id: UUID) -> None:
    try:
        # A UUID hint is expendable. The committed PostgreSQL queued row remains
        # the durable outbox and is reconciled even when Redis is unavailable.
        await cast(Awaitable[int], infrastructure.cache.lpush(SIMULATION_QUEUE_KEY, str(run_id)))
        await cast(Awaitable[str], infrastructure.cache.ltrim(SIMULATION_QUEUE_KEY, 0, 99))
    except Exception:
        logger.warning("Simulation notification unavailable; durable queue remains pending")


@router.get("/simulation-networks", response_model=SimulationPage[SimulationNetworkResponse])
async def simulation_networks(
    session: Session, settings: Configuration, limit: PageLimit = 25, offset: PageOffset = 0
) -> dict[str, object]:
    return await network_catalog(session, settings, limit, offset)


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    status_code=201,
    dependencies=[Depends(require_dev_write)],
)
async def scenario_create(
    payload: ScenarioCreate, session: Session, settings: Configuration, response: Response
) -> ScenarioResponse:
    value = await create_scenario(session, settings, payload)
    response.headers["Location"] = f"/api/v1/scenarios/{value.id}"
    response.headers["Cache-Control"] = "no-store"
    return value


@router.get("/scenarios", response_model=SimulationPage[ScenarioResponse])
async def scenarios(
    session: Session, settings: Configuration, limit: PageLimit = 25, offset: PageOffset = 0
) -> dict[str, object]:
    total = await session.scalar(
        select(func.count())
        .select_from(Scenario)
        .where(Scenario.configuration_checksum.is_not(None))
    )
    values = list(
        (
            await session.scalars(
                select(Scenario)
                .where(Scenario.configuration_checksum.is_not(None))
                .order_by(Scenario.created_at.desc(), Scenario.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    validation_cache: NetworkValidationCache = {}
    return {
        "items": [
            await scenario_response(session, settings, value, validation_cache) for value in values
        ],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def scenario_detail(
    scenario_id: UUID, session: Session, settings: Configuration
) -> ScenarioResponse:
    return await scenario_response(session, settings, await get_scenario(session, scenario_id))


@router.post(
    "/scenarios/{scenario_id}/validate",
    response_model=ScenarioValidation,
    dependencies=[Depends(require_dev_write)],
)
async def scenario_validate(
    scenario_id: UUID, session: Session, settings: Configuration
) -> ScenarioValidation:
    value = await get_scenario(session, scenario_id)
    _, validation, _ = await validate_network_input(session, settings, value.network_version_id)
    return validation


@router.post(
    "/simulations",
    response_model=RunResponse,
    status_code=202,
    dependencies=[Depends(require_dev_write)],
)
async def simulation_create(
    payload: RunCreate,
    session: Session,
    settings: Configuration,
    response: Response,
    background: BackgroundTasks,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(
            min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$", alias="Idempotency-Key"
        ),
    ],
) -> RunResponse:
    value = await submit_run(session, settings, payload, idempotency_key)
    background.add_task(
        notify_worker, cast(Infrastructure, request.app.state.infrastructure), value.id
    )
    response.headers["Location"] = f"/api/v1/simulations/{value.id}"
    response.headers["Cache-Control"] = "no-store"
    return await run_response(session, value)


@router.get("/simulations", response_model=SimulationPage[RunResponse])
async def simulations(
    session: Session, limit: PageLimit = 25, offset: PageOffset = 0
) -> dict[str, object]:
    scope = SimulationRun.input_config["schema_version"].as_integer() == 1
    total = await session.scalar(select(func.count()).select_from(SimulationRun).where(scope))
    values = list(
        (
            await session.scalars(
                select(SimulationRun)
                .where(scope)
                .order_by(SimulationRun.created_at.desc(), SimulationRun.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    return {
        "items": [await run_response(session, value) for value in values],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/simulations/{run_id}", response_model=RunResponse)
async def simulation_detail(run_id: UUID, session: Session) -> RunResponse:
    return await run_response(session, await get_run(session, run_id))


@router.post(
    "/simulations/{run_id}/cancel",
    response_model=RunResponse,
    dependencies=[Depends(require_dev_write)],
)
async def simulation_cancel(run_id: UUID, session: Session) -> RunResponse:
    return await run_response(session, await cancel_run(session, run_id))


@router.get("/simulations/{run_id}/metrics", response_model=RunMetricsResponse)
async def simulation_metrics(
    run_id: UUID, session: Session, settings: Configuration
) -> RunMetricsResponse:
    return await run_metrics(session, settings, await get_run(session, run_id))


@router.get("/simulations/{run_id}/events", response_model=SimulationPage[RunEventResponse])
async def simulation_events(
    run_id: UUID, session: Session, limit: PageLimit = 50, offset: PageOffset = 0
) -> dict[str, object]:
    await get_run(session, run_id)
    total = await session.scalar(
        select(func.count()).select_from(SimulationEvent).where(SimulationEvent.run_id == run_id)
    )
    values = list(
        (
            await session.scalars(
                select(SimulationEvent)
                .where(SimulationEvent.run_id == run_id)
                .order_by(SimulationEvent.created_at.desc(), SimulationEvent.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    return {
        "items": [
            RunEventResponse(
                id=value.id,
                run_id=value.run_id,
                event_type=value.event_type,
                message=value.message,
                progress_seconds=value.progress_seconds,
                created_at=value.created_at,
            )
            for value in values
        ],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/simulations/{run_id}/replay/manifest", response_model=ReplayManifest)
async def simulation_manifest(
    run_id: UUID, session: Session, settings: Configuration, response: Response
) -> ReplayManifest:
    response.headers["Cache-Control"] = "private, max-age=60"
    return await replay_manifest(session, settings, await get_run(session, run_id))


@router.get("/simulations/{run_id}/replay/chunks/{chunk_id}", response_model=TrajectoryChunk)
async def simulation_chunk(
    run_id: UUID,
    chunk_id: Annotated[str, Path(pattern=r"^\d{6}$")],
    session: Session,
    settings: Configuration,
) -> Response:
    payload = await replay_chunk(session, settings, await get_run(session, run_id), chunk_id)
    return Response(
        payload,
        media_type="application/json",
        headers={"Cache-Control": "private, max-age=60", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/simulations/{run_id}/logs")
async def simulation_logs(run_id: UUID, session: Session, settings: Configuration) -> Response:
    payload = await artifact_payload(
        session, settings, await get_run(session, run_id), "engine_log", 2 * 1024 * 1024
    )
    return Response(
        payload,
        media_type="text/plain",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/simulations/{run_id}/export")
async def simulation_export(
    run_id: UUID,
    session: Session,
    settings: Configuration,
    format: Annotated[Literal["json", "csv"], Query()] = "json",
) -> Response:
    payload = await export_run(session, settings, await get_run(session, run_id), format)
    return Response(
        payload,
        media_type="text/csv" if format == "csv" else "application/json",
        headers={
            "Content-Disposition": f'attachment; filename="earthmind-{run_id}.{format}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/comparisons",
    response_model=ComparisonResponse,
    status_code=201,
    dependencies=[Depends(require_dev_write)],
)
async def comparison_create(
    payload: ComparisonCreate, session: Session, settings: Configuration
) -> ComparisonResponse:
    return await compare_runs(session, settings, payload)


@router.get("/comparisons/{comparison_id}", response_model=ComparisonResponse)
async def comparison_detail(comparison_id: UUID, session: Session) -> ComparisonResponse:
    value = await session.get(SimulationComparison, comparison_id)
    if value is None:
        raise HTTPException(404)
    return ComparisonResponse.model_validate(value.result)
