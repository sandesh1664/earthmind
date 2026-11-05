"""Worker transaction boundary using the existing lifespan-scoped Infrastructure."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from earthmind_contracts.simulation import (
    ProgressUpdate,
    PublishedResult,
    SimulationInput,
    WorkerClaim,
    canonical_checksum,
)
from sqlalchemy import func, select

from earthmind_api.dependencies import Infrastructure
from earthmind_api.geospatial_models import RunArtifact, RunMetric, SimulationRun
from earthmind_api.simulation_artifacts import validate_publication, validate_result_metrics
from earthmind_api.simulation_models import SimulationEvent


class SimulationWorkerStore:
    def __init__(
        self, infrastructure: Infrastructure, worker_id: str, lease_seconds: int = 30
    ) -> None:
        if not 5 <= lease_seconds <= 300 or not worker_id or len(worker_id) > 100:
            raise ValueError("Invalid worker lease configuration")
        self.infrastructure = infrastructure
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    async def claim(self) -> WorkerClaim | None:
        async with self.infrastructure.session() as session:
            run = await session.scalar(
                select(SimulationRun)
                .where(
                    SimulationRun.status == "queued",
                    SimulationRun.input_config["schema_version"].as_integer() == 1,
                )
                .order_by(SimulationRun.created_at, SimulationRun.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if run is None:
                return None
            try:
                config = SimulationInput.model_validate(run.input_config)
                valid_checksum = (
                    canonical_checksum(config.model_dump(mode="json")) == run.input_sha256
                )
            except ValueError:
                valid_checksum = False
            if not valid_checksum:
                run.status = "failed"
                run.error_code = "input_invalid"
                run.error_message = "Immutable simulation input schema or checksum is inconsistent"
                session.add(
                    SimulationEvent(run_id=run.id, event_type="failed", message=run.error_message)
                )
                return None
            if run.cancel_requested:
                run.status = "cancelled"
                session.add(
                    SimulationEvent(
                        run_id=run.id, event_type="cancelled", message="Cancelled before execution"
                    )
                )
                return None
            run.status = "running"
            run.worker_id = self.worker_id
            run.heartbeat_at = datetime.now(UTC)
            session.add(
                SimulationEvent(
                    run_id=run.id, event_type="starting", message="Worker claimed this durable run"
                )
            )
            await session.flush()
            return WorkerClaim(
                run_id=run.id, input_config=config, seed=run.seed, input_sha256=run.input_sha256
            )

    def _owned(self, run: SimulationRun | None, now: datetime) -> bool:
        return bool(
            run is not None
            and run.status == "running"
            and run.worker_id == self.worker_id
            and run.heartbeat_at is not None
            and run.heartbeat_at >= now - timedelta(seconds=self.lease_seconds)
        )

    async def heartbeat(self, run_id: UUID, progress: ProgressUpdate | None = None) -> bool:
        async with self.infrastructure.session() as session:
            run = await session.scalar(
                select(SimulationRun).where(SimulationRun.id == run_id).with_for_update()
            )
            now = datetime.now(UTC)
            if not self._owned(run, now) or run is None or run.cancel_requested:
                return False
            run.heartbeat_at = now
            if progress is not None:
                old = run.progress.get("simulated_seconds", 0)
                if progress.duration_seconds != run.input_config["demand"]["duration_seconds"]:
                    raise ValueError("Reported progress belongs to another simulation duration")
                if progress.simulated_seconds < old:
                    raise ValueError("Simulation progress cannot move backwards")
                run.progress = progress.model_dump(mode="json")
                count = await session.scalar(
                    select(func.count())
                    .select_from(SimulationEvent)
                    .where(SimulationEvent.run_id == run_id)
                )
                if (
                    count is not None
                    and count < 2000
                    and int(progress.simulated_seconds // 5) > int(old // 5)
                ):
                    session.add(
                        SimulationEvent(
                            run_id=run_id,
                            event_type="progress",
                            message=(
                                f"SUMO advanced to {progress.simulated_seconds:g} simulated seconds"
                            ),
                            progress_seconds=progress.simulated_seconds,
                        )
                    )
            return True

    async def publish(self, run_id: UUID, result: PublishedResult) -> bool:
        root = Path(self.infrastructure.settings.simulation_artifacts_root)
        manifest = await asyncio.to_thread(validate_publication, root, run_id, result)
        async with self.infrastructure.session() as session:
            run = await session.scalar(
                select(SimulationRun).where(SimulationRun.id == run_id).with_for_update()
            )
            if not self._owned(run, datetime.now(UTC)) or run is None or run.cancel_requested:
                return False
            expected = SimulationInput.model_validate(run.input_config)
            if (
                result.input_sha256 != run.input_sha256
                or manifest.network_version_id != expected.network_version_id
                or manifest.duration_seconds > expected.demand.duration_seconds
                or manifest.sample_interval_seconds != expected.demand.sample_interval_seconds
            ):
                raise ValueError("Published output does not match the claimed immutable inputs")
            validate_result_metrics(result, expected.demand.effective_trip_count, manifest)
            for item in result.metrics:
                session.add(RunMetric(run_id=run_id, **item.model_dump()))
            for artifact in result.artifacts:
                session.add(
                    RunArtifact(
                        run_id=run_id,
                        artifact_type=artifact.artifact_type,
                        storage_uri=artifact.relative_path,
                        checksum_sha256=artifact.checksum_sha256,
                        size_bytes=artifact.size_bytes,
                        content_type=artifact.content_type,
                    )
                )
            run.engine_version = result.engine_version
            run.output_manifest_uri = result.manifest_path
            run.status = "succeeded"
            run.error_code = None
            run.error_message = None
            session.add(
                SimulationEvent(
                    run_id=run_id,
                    event_type="succeeded",
                    message="Verified SUMO outputs published atomically",
                    progress_seconds=float(run.progress.get("simulated_seconds", 0)),
                )
            )
            return True

    async def fail(self, run_id: UUID, code: str, message: str, cancelled: bool = False) -> None:
        # Error details originate in the fixed runner protocol, never environment/native URLs.
        allowed = {
            "execution_failed",
            "input_invalid",
            "output_invalid",
            "timeout",
            "worker_lost",
            "cancelled",
            "resource_limit",
        }
        if code not in allowed:
            code = "execution_failed"
        async with self.infrastructure.session() as session:
            run = await session.scalar(
                select(SimulationRun).where(SimulationRun.id == run_id).with_for_update()
            )
            if run is None or run.status != "running" or run.worker_id != self.worker_id:
                return
            run.status = "cancelled" if cancelled or run.cancel_requested else "failed"
            run.error_code = "cancelled" if run.status == "cancelled" else code
            run.error_message = message[:1000] if message else "Simulation did not complete"
            session.add(
                SimulationEvent(run_id=run_id, event_type=run.status, message=run.error_message)
            )

    async def reconcile_stale(self) -> int:
        async with self.infrastructure.session() as session:
            rows = list(
                (
                    await session.scalars(
                        select(SimulationRun)
                        .where(
                            SimulationRun.status == "running",
                            SimulationRun.input_config["schema_version"].as_integer() == 1,
                            SimulationRun.heartbeat_at
                            < datetime.now(UTC) - timedelta(seconds=self.lease_seconds),
                        )
                        .with_for_update(skip_locked=True)
                        .limit(100)
                    )
                ).all()
            )
            for run in rows:
                run.status = "cancelled" if run.cancel_requested else "failed"
                run.error_code = "cancelled" if run.cancel_requested else "worker_lost"
                run.error_message = "Worker lease expired; retry creates a new tracked attempt"
                session.add(
                    SimulationEvent(run_id=run.id, event_type=run.status, message=run.error_message)
                )
            return len(rows)
