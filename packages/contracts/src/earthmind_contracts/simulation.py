"""Strict M04 simulation, publication and replay contracts; synthetic traffic only."""

import hashlib
import json
import math
from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SIMULATION_QUEUE_KEY = "earthmind:simulations:queue"
MAX_TRIPS = 5000
MAX_DURATION_SECONDS = 3600
MAX_CHUNK_BYTES = 4 * 1024 * 1024
CALCULATION_VERSION = "sumo-m04-v1"
RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
Checksum = str


class SimulationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, allow_inf_nan=False)


def canonical_checksum(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class DemandConfig(SimulationModel):
    trip_target: int = Field(default=500, ge=1, le=MAX_TRIPS)
    duration_seconds: int = Field(default=600, ge=30, le=MAX_DURATION_SECONDS)
    seed: int = Field(default=42, ge=0, le=2147483647)
    departure_distribution: Literal["uniform", "poisson", "burst"] = "uniform"
    vehicle_class: Literal["passenger"] = "passenger"
    od_policy: Literal["reachable_uniform"] = "reachable_uniform"
    demand_multiplier: float = Field(default=1, ge=0.1, le=3)
    sample_interval_seconds: int = Field(default=2, ge=1, le=10)

    @property
    def effective_trip_count(self) -> int:
        return round(self.trip_target * self.demand_multiplier)

    @model_validator(mode="after")
    def bounded_effective_count(self) -> Self:
        if not 1 <= self.effective_trip_count <= MAX_TRIPS:
            raise ValueError("Effective synthetic trip count must be between 1 and 5000")
        return self


class ScenarioCreate(SimulationModel):
    name: str = Field(min_length=1, max_length=200)
    network_version_id: UUID
    demand: DemandConfig = Field(default_factory=DemandConfig)

    @field_validator("name")
    @classmethod
    def plain_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise ValueError("Scenario name must contain printable text")
        return value


class ScenarioValidation(SimulationModel):
    valid: bool
    errors: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    network_artifact_sha256: str | None = None
    mapped_edge_count: int | None = None
    engine_version: str | None = None


class ScenarioResponse(ScenarioCreate):
    id: UUID
    network_version_label: str
    configuration_checksum: str
    created_at: datetime
    synthetic: Literal[True] = True
    validation: ScenarioValidation


class SimulationInput(SimulationModel):
    schema_version: Literal[1] = 1
    network_version_id: UUID
    network_artifact: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    network_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mapping_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    demand: DemandConfig


class RunCreate(SimulationModel):
    scenario_id: UUID
    seed: int | None = Field(default=None, ge=0, le=2147483647)
    retry_of: UUID | None = None


class ProgressUpdate(SimulationModel):
    simulated_seconds: float = Field(default=0, ge=0, le=MAX_DURATION_SECONDS)
    duration_seconds: int = Field(ge=1, le=MAX_DURATION_SECONDS)
    departed: int = Field(default=0, ge=0, le=MAX_TRIPS)
    completed: int = Field(default=0, ge=0, le=MAX_TRIPS)
    active: int = Field(default=0, ge=0, le=MAX_TRIPS)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.simulated_seconds > self.duration_seconds or self.completed > self.departed:
            raise ValueError("Simulation progress is inconsistent")
        return self


class RunResponse(SimulationModel):
    id: UUID
    scenario_id: UUID
    network_version_id: UUID
    scenario_name: str
    status: RunStatus
    seed: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    worker_id: str | None
    engine_version: str | None
    input_sha256: str
    error_code: str | None
    error_message: str | None
    progress: ProgressUpdate
    cancel_requested: bool
    attempt_number: int
    retry_of: UUID | None
    synthetic: Literal[True] = True


class MetricValue(SimulationModel):
    metric_name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    value: float | None
    unit: str = Field(min_length=1, max_length=64)
    aggregation: str = Field(default="run", min_length=1, max_length=64)
    calculation_version: str = Field(default=CALCULATION_VERSION, min_length=1, max_length=64)

    @field_validator("value")
    @classmethod
    def finite_measurement(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("Metric must be finite or explicitly unavailable")
        return value


class ArtifactValue(SimulationModel):
    artifact_type: str = Field(pattern=r"^[a-z][a-z0-9_:.-]{0,99}$")
    relative_path: str = Field(min_length=1, max_length=512)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0, le=256 * 1024 * 1024)
    content_type: str = Field(min_length=1, max_length=100)


class PublishedResult(SimulationModel):
    engine_version: str = Field(min_length=1, max_length=100)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_path: str = Field(min_length=1, max_length=512)
    metrics: list[MetricValue] = Field(min_length=1, max_length=40)
    artifacts: list[ArtifactValue] = Field(min_length=1, max_length=2000)


class WorkerClaim(SimulationModel):
    run_id: UUID
    input_config: SimulationInput
    seed: int
    input_sha256: str


class CountSample(SimulationModel):
    time: float = Field(ge=0, le=MAX_DURATION_SECONDS)
    active: int = Field(ge=0, le=MAX_TRIPS)
    departed: int = Field(ge=0, le=MAX_TRIPS)
    arrived: int = Field(ge=0, le=MAX_TRIPS)


class VehicleSample(SimulationModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    heading: float = Field(ge=0, le=360)
    speed: float = Field(ge=0, le=100)
    vehicle_class: Literal["passenger"] = "passenger"
    segment_id: int = Field(ge=0, le=10000)


class ReplayEvent(SimulationModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    time: float = Field(ge=0, le=MAX_DURATION_SECONDS)
    type: Literal["departed", "arrived", "teleport_start", "teleport_end"]


class ReplayFrame(SimulationModel):
    time: float = Field(ge=0, le=MAX_DURATION_SECONDS)
    vehicles: list[VehicleSample] = Field(max_length=MAX_TRIPS)
    departed: list[str] = Field(default_factory=list, max_length=MAX_TRIPS)
    arrived: list[str] = Field(default_factory=list, max_length=MAX_TRIPS)
    teleported: list[str] = Field(default_factory=list, max_length=MAX_TRIPS)


class TrajectoryChunk(SimulationModel):
    schema_version: Literal[1] = 1
    run_id: UUID
    chunk_id: str = Field(pattern=r"^\d{6}$")
    frames: list[ReplayFrame] = Field(min_length=1, max_length=1000)
    events: list[ReplayEvent] = Field(default_factory=list, max_length=30000)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if any(a.time >= b.time for a, b in zip(self.frames, self.frames[1:], strict=False)):
            raise ValueError("Replay frame times must be strictly increasing")
        return self


class ReplayChunkReference(SimulationModel):
    id: str = Field(pattern=r"^\d{6}$")
    start_time: float = Field(ge=0, le=MAX_DURATION_SECONDS)
    end_time: float = Field(ge=0, le=MAX_DURATION_SECONDS)
    sample_count: int = Field(ge=0, le=500000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1, le=MAX_CHUNK_BYTES)


class ReplayManifest(SimulationModel):
    schema_version: Literal[1] = 1
    run_id: UUID
    network_version_id: UUID
    duration_seconds: int = Field(ge=1, le=MAX_DURATION_SECONDS)
    sample_interval_seconds: int = Field(ge=1, le=10)
    vehicle_class: Literal["passenger"] = "passenger"
    synthetic: Literal[True] = True
    coordinate_reference_system: Literal["EPSG:4326"] = "EPSG:4326"
    chunks: list[ReplayChunkReference] = Field(max_length=2000)
    counts: list[CountSample] = Field(max_length=10000)


class RunMetricsResponse(SimulationModel):
    run_id: UUID
    metrics: list[MetricValue]
    vehicle_counts: list[CountSample]


class RunEventResponse(SimulationModel):
    id: UUID
    run_id: UUID
    event_type: str
    message: str
    progress_seconds: float | None
    created_at: datetime


class ComparisonCreate(SimulationModel):
    baseline_run_id: UUID
    modified_run_id: UUID


class ComparisonMetric(SimulationModel):
    metric_name: str
    unit: str
    baseline_value: float | None
    modified_value: float | None
    absolute_change: float | None
    percentage_change: float | None


class ComparisonResponse(ComparisonCreate):
    id: UUID
    network_version_id: UUID
    created_at: datetime
    metrics: list[ComparisonMetric]
    warnings: list[str]


class SimulationNetworkResponse(SimulationModel):
    id: UUID
    version_label: str
    region_name: str
    is_synthetic: bool
    source_checksum: str | None
    network_artifact_sha256: str | None
    engine_version: str | None
    mapped_edge_count: int | None
    validation: ScenarioValidation


class SimulationPage[T](SimulationModel):
    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0, le=100000)
