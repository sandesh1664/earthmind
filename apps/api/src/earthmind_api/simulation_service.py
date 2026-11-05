"""Scenario/run application operations; actual engine work belongs to the worker."""

import asyncio
import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from earthmind_contracts.simulation import (
    ComparisonCreate,
    ComparisonMetric,
    ComparisonResponse,
    DemandConfig,
    MetricValue,
    ProgressUpdate,
    ReplayManifest,
    RunCreate,
    RunMetricsResponse,
    RunResponse,
    RunStatus,
    ScenarioCreate,
    ScenarioResponse,
    ScenarioValidation,
    TrajectoryChunk,
    canonical_checksum,
)
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from earthmind_api.geospatial_models import (
    DemandProfile,
    NetworkVersion,
    RunArtifact,
    RunMetric,
    Scenario,
    SimulationRun,
)
from earthmind_api.settings import Settings
from earthmind_api.simulation_artifacts import verified_bytes
from earthmind_api.simulation_models import SimulationComparison, SimulationEvent
from earthmind_api.simulation_networks import simulation_input, validate_network_input


async def get_scenario(session: AsyncSession, scenario_id: UUID) -> Scenario:
    value = await session.get(Scenario, scenario_id)
    if value is None or value.configuration_checksum is None:
        raise HTTPException(404)
    return value


# Callers may share this only within one request, never between requests/runs.
NetworkValidationCache = dict[UUID, tuple[NetworkVersion | None, ScenarioValidation]]


async def scenario_response(
    session: AsyncSession,
    settings: Settings,
    value: Scenario,
    validation_cache: NetworkValidationCache | None = None,
) -> ScenarioResponse:
    cached = (
        validation_cache.get(value.network_version_id) if validation_cache is not None else None
    )
    if cached is None:
        network, validation, _ = await validate_network_input(
            session, settings, value.network_version_id
        )
        if validation_cache is not None:
            validation_cache[value.network_version_id] = (network, validation)
    else:
        network, validation = cached
    return ScenarioResponse(
        id=value.id,
        name=value.name,
        network_version_id=value.network_version_id,
        network_version_label=network.version_label if network else "Unavailable",
        demand=DemandConfig.model_validate(value.config["demand"]),
        configuration_checksum=value.configuration_checksum or "",
        created_at=value.created_at,
        validation=validation,
    )


async def create_scenario(
    session: AsyncSession, settings: Settings, payload: ScenarioCreate
) -> ScenarioResponse:
    network, validation, _ = await validate_network_input(
        session, settings, payload.network_version_id
    )
    if not validation.valid or network is None:
        raise HTTPException(422, "Select a validated retained SUMO-compatible network")
    config = {
        "schema_version": 1,
        "synthetic": True,
        "demand": payload.demand.model_dump(mode="json"),
    }
    profile = DemandProfile(
        network_version_id=network.id,
        name=f"Synthetic demand: {payload.name}"[:200],
        seed=payload.demand.seed,
        profile_type="synthetic",
        config=config,
    )
    session.add(profile)
    await session.flush()
    value = Scenario(
        network_version_id=network.id,
        demand_profile_id=profile.id,
        name=payload.name,
        description="Synthetic passenger demand experiment; not observed Dubai traffic",
        duration_seconds=payload.demand.duration_seconds,
        config=config,
        configuration_checksum=canonical_checksum(
            {"network_version_id": str(network.id), "demand": config["demand"]}
        ),
    )
    session.add(value)
    await session.flush()
    return await scenario_response(session, settings, value)


async def get_run(session: AsyncSession, run_id: UUID, lock: bool = False) -> SimulationRun:
    query = select(SimulationRun).where(
        SimulationRun.id == run_id, SimulationRun.input_config["schema_version"].as_integer() == 1
    )
    if lock:
        query = query.with_for_update()
    value = await session.scalar(query)
    if value is None:
        raise HTTPException(404)
    return value


async def run_response(session: AsyncSession, run: SimulationRun) -> RunResponse:
    scenario = await get_scenario(session, run.scenario_id)
    demand = DemandConfig.model_validate(run.input_config["demand"])
    progress = ProgressUpdate.model_validate(
        run.progress or {"duration_seconds": demand.duration_seconds}
    )
    return RunResponse(
        id=run.id,
        scenario_id=run.scenario_id,
        network_version_id=scenario.network_version_id,
        scenario_name=scenario.name,
        status=cast(RunStatus, run.status),
        seed=run.seed,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        worker_id=run.worker_id,
        engine_version=run.engine_version,
        input_sha256=run.input_sha256,
        error_code=run.error_code,
        error_message=run.error_message,
        progress=progress,
        cancel_requested=run.cancel_requested,
        attempt_number=run.attempt_number,
        retry_of=run.retry_of,
    )


async def submit_run(
    session: AsyncSession, settings: Settings, payload: RunCreate, idempotency_key: str
) -> SimulationRun:
    # Serializes queue-cap/idempotency decisions across API processes. Request
    # identity is bounded/parameterized; this is not an arbitrary SQL interface.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('earthmind-m04-submit',0))")
    )
    request_hash = canonical_checksum(payload.model_dump(mode="json"))
    existing = await session.scalar(
        select(SimulationRun).where(SimulationRun.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_sha256 != request_hash:
            raise HTTPException(409, "Idempotency key belongs to another submission")
        return existing
    scenario = await get_scenario(session, payload.scenario_id)
    network, validation, artifact = await validate_network_input(
        session, settings, scenario.network_version_id
    )
    if not validation.valid or artifact is None or network is None:
        raise HTTPException(422, "Scenario network no longer passes retained input validation")
    if (
        canonical_checksum(
            {"network_version_id": str(network.id), "demand": scenario.config["demand"]}
        )
        != scenario.configuration_checksum
    ):
        raise HTTPException(409, "Scenario configuration checksum is inconsistent")
    demand = DemandConfig.model_validate(scenario.config["demand"])
    attempt = 1
    if payload.retry_of is not None:
        parent = await get_run(session, payload.retry_of)
        if parent.status not in {"failed", "cancelled"} or parent.scenario_id != scenario.id:
            raise HTTPException(409, "Retry requires a failed or cancelled run of this scenario")
        attempt = parent.attempt_number + 1
        if attempt > 10:
            raise HTTPException(409, "Retry attempt budget reached")
        default_seed = parent.seed
    else:
        default_seed = demand.seed
    demand = demand.model_copy(
        update={"seed": payload.seed if payload.seed is not None else default_seed}
    )
    active = await session.scalar(
        select(func.count())
        .select_from(SimulationRun)
        .where(
            SimulationRun.status.in_(["queued", "running"]),
            SimulationRun.input_config["schema_version"].as_integer() == 1,
        )
    )
    if active is not None and active >= settings.simulation_queue_limit:
        raise HTTPException(429, "Simulation queue limit reached")
    snapshot = simulation_input(network.id, artifact, demand)
    value = SimulationRun(
        scenario_id=scenario.id,
        status="queued",
        seed=demand.seed,
        input_sha256=canonical_checksum(snapshot.model_dump(mode="json")),
        input_config=snapshot.model_dump(mode="json"),
        progress=ProgressUpdate(duration_seconds=demand.duration_seconds).model_dump(mode="json"),
        idempotency_key=idempotency_key,
        request_sha256=request_hash,
        attempt_number=attempt,
        retry_of=payload.retry_of,
    )
    session.add(value)
    await session.flush()
    session.add(
        SimulationEvent(
            run_id=value.id,
            event_type="retry" if payload.retry_of else "queued",
            message="New tracked retry queued"
            if payload.retry_of
            else "Synthetic simulation queued for one bounded worker",
        )
    )
    return value


async def cancel_run(session: AsyncSession, run_id: UUID) -> SimulationRun:
    value = await get_run(session, run_id, lock=True)
    if value.status in {"succeeded", "failed", "cancelled"} or value.cancel_requested:
        return value
    value.cancel_requested = True
    if value.status == "queued":
        value.status = "cancelled"
        message = "Queued simulation cancelled before SUMO execution"
        event = "cancelled"
    else:
        message = "Cancellation requested; worker must terminate SUMO before acknowledging"
        event = "cancel_requested"
    session.add(SimulationEvent(run_id=run_id, event_type=event, message=message))
    await session.flush()
    await session.refresh(value)
    return value


async def artifact_payload(
    session: AsyncSession, settings: Settings, run: SimulationRun, category: str, maximum: int
) -> bytes:
    if run.status != "succeeded":
        raise HTTPException(409, "Verified results are available only for succeeded runs")
    artifact = await session.scalar(
        select(RunArtifact).where(
            RunArtifact.run_id == run.id, RunArtifact.artifact_type == category
        )
    )
    if artifact is None:
        raise HTTPException(404)
    try:
        return await asyncio.to_thread(
            verified_bytes,
            Path(settings.simulation_artifacts_root),
            run.id,
            artifact.storage_uri,
            artifact.checksum_sha256,
            artifact.size_bytes,
            maximum,
        )
    except (ValueError, OSError) as error:
        raise HTTPException(409, "Published artifact integrity check failed") from error


async def replay_manifest(
    session: AsyncSession, settings: Settings, run: SimulationRun
) -> ReplayManifest:
    payload = await artifact_payload(session, settings, run, "replay_manifest", 1024 * 1024)
    try:
        result = ReplayManifest.model_validate_json(payload)
        if (
            result.run_id != run.id
            or str(result.network_version_id) != run.input_config["network_version_id"]
        ):
            raise ValueError("Scope mismatch")
        return result
    except ValueError as error:
        raise HTTPException(409, "Published replay manifest is invalid") from error


async def replay_chunk(
    session: AsyncSession, settings: Settings, run: SimulationRun, chunk_id: str
) -> bytes:
    manifest = await replay_manifest(session, settings, run)
    reference = next((item for item in manifest.chunks if item.id == chunk_id), None)
    if reference is None:
        raise HTTPException(404)
    payload = await artifact_payload(
        session, settings, run, f"replay_chunk:{chunk_id}", 4 * 1024 * 1024
    )
    try:
        chunk = TrajectoryChunk.model_validate_json(payload)
        if chunk.run_id != run.id or chunk.chunk_id != chunk_id:
            raise ValueError("Scope mismatch")
    except ValueError as error:
        raise HTTPException(409, "Published replay chunk is invalid") from error
    return payload


async def run_metrics(
    session: AsyncSession, settings: Settings, run: SimulationRun
) -> RunMetricsResponse:
    manifest = await replay_manifest(session, settings, run)
    rows = list(
        (
            await session.scalars(
                select(RunMetric).where(RunMetric.run_id == run.id).order_by(RunMetric.metric_name)
            )
        ).all()
    )
    return RunMetricsResponse(
        run_id=run.id,
        metrics=[
            MetricValue(
                metric_name=item.metric_name,
                value=item.value,
                unit=item.unit,
                aggregation=item.aggregation,
                calculation_version=item.calculation_version,
            )
            for item in rows
        ],
        vehicle_counts=manifest.counts,
    )


async def export_run(
    session: AsyncSession, settings: Settings, run: SimulationRun, output_format: str
) -> bytes:
    metrics = await run_metrics(session, settings, run)
    if output_format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["run_id", "metric", "value", "unit", "aggregation", "calculation_version"])
        for metric in metrics.metrics:
            writer.writerow(
                [
                    str(run.id),
                    metric.metric_name,
                    "" if metric.value is None else metric.value,
                    metric.unit,
                    metric.aggregation,
                    metric.calculation_version,
                ]
            )
        return output.getvalue().encode()
    scenario = await get_scenario(session, run.scenario_id)
    artifacts = list(
        (
            await session.scalars(
                select(RunArtifact)
                .where(RunArtifact.run_id == run.id)
                .order_by(RunArtifact.artifact_type)
            )
        ).all()
    )
    value = {
        "schema_version": 1,
        "synthetic": True,
        "disclosure": (
            "Actual SUMO outputs driven by synthetic passenger demand, not observed Dubai traffic"
        ),
        "run": (await run_response(session, run)).model_dump(mode="json"),
        "scenario": (await scenario_response(session, settings, scenario)).model_dump(mode="json"),
        "reproducibility": {
            "input_sha256": run.input_sha256,
            "configuration_checksum": scenario.configuration_checksum,
            "engine_version": run.engine_version,
            "input": run.input_config,
        },
        "metrics": metrics.model_dump(mode="json"),
        "artifacts": [
            {
                "category": item.artifact_type,
                "sha256": item.checksum_sha256,
                "size_bytes": item.size_bytes,
                "content_type": item.content_type,
            }
            for item in artifacts
        ],
    }
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


async def compare_runs(
    session: AsyncSession, settings: Settings, payload: ComparisonCreate
) -> ComparisonResponse:
    if payload.baseline_run_id == payload.modified_run_id:
        raise HTTPException(422, "Select two distinct succeeded runs")
    baseline = await get_run(session, payload.baseline_run_id)
    modified = await get_run(session, payload.modified_run_id)
    if baseline.status != "succeeded" or modified.status != "succeeded":
        raise HTTPException(409, "Both runs must have verified succeeded outputs")
    if (
        baseline.input_config["network_version_id"] != modified.input_config["network_version_id"]
        or baseline.engine_version != modified.engine_version
    ):
        raise HTTPException(422, "Comparison requires the same network and SUMO engine version")
    first = DemandConfig.model_validate(baseline.input_config["demand"])
    second = DemandConfig.model_validate(modified.input_config["demand"])
    keys = [
        "seed",
        "duration_seconds",
        "departure_distribution",
        "vehicle_class",
        "od_policy",
        "sample_interval_seconds",
    ]
    if any(getattr(first, key) != getattr(second, key) for key in keys):
        raise HTTPException(
            422, "Comparison requires compatible seed, duration and generation rules"
        )
    left = await run_metrics(session, settings, baseline)
    right = await run_metrics(session, settings, modified)
    right_values = {(item.metric_name, item.unit, item.aggregation): item for item in right.metrics}
    values = []
    for item in left.metrics:
        other = right_values.get((item.metric_name, item.unit, item.aggregation))
        if other is None:
            continue
        delta = (
            other.value - item.value if other.value is not None and item.value is not None else None
        )
        percentage = (
            100 * delta / abs(item.value)
            if delta is not None and item.value is not None and item.value != 0
            else None
        )
        values.append(
            ComparisonMetric(
                metric_name=item.metric_name,
                unit=item.unit,
                baseline_value=item.value,
                modified_value=other.value,
                absolute_change=delta,
                percentage_change=percentage,
            )
        )
    warning = (
        "Synthetic demand experiment only; no causal certainty or real-world "
        "congestion prediction. Completed-trip averages must be interpreted alongside "
        "completed and incomplete trip counts."
    )
    result = ComparisonResponse(
        id=uuid4(),
        baseline_run_id=baseline.id,
        modified_run_id=modified.id,
        network_version_id=UUID(baseline.input_config["network_version_id"]),
        created_at=datetime.now(UTC),
        metrics=values,
        warnings=[warning],
    )
    session.add(
        SimulationComparison(
            id=result.id,
            baseline_run_id=baseline.id,
            modified_run_id=modified.id,
            result=result.model_dump(mode="json"),
        )
    )
    await session.flush()
    return result
