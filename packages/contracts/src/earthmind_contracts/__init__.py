"""Stable wire contracts for the M01 foundation."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, field_validator

CheckStatus = Literal["ok", "error"]
WORKER_HEARTBEAT_KEY = "earthmind:worker:heartbeat"
WORKER_HEARTBEAT_TTL_SECONDS = 30
DIAGNOSTIC_QUEUE_KEY = "earthmind:diagnostics:queue"
DIAGNOSTIC_JOB_PREFIX = "earthmind:diagnostics:job:"
DIAGNOSTIC_QUEUE_LIMIT = 20
DIAGNOSTIC_JOB_TTL_SECONDS = 300
SUMO_RUNTIME_KEY = "earthmind:runtime:sumo"
SUMO_RUNTIME_TTL_SECONDS = 60
DiagnosticKind = Literal["diagnostic", "sumo_runtime"]
DiagnosticStatus = Literal["queued", "running", "succeeded", "failed"]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LiveHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["api"] = "api"


class DependencyChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database: CheckStatus
    redis: CheckStatus
    worker: CheckStatus


class ReadyHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    service: Literal["api"] = "api"
    checks: DependencyChecks


class ApiHealth(WireModel):
    service: Literal["EARTHMIND API"] = "EARTHMIND API"
    status: Literal["healthy"] = "healthy"
    version: Literal["0.1.0"] = "0.1.0"


class SumoRuntimeRecord(WireModel):
    verified: bool
    version: str = Field(min_length=1, max_length=512)
    checked_at: AwareDatetime
    architecture: str = Field(min_length=1, max_length=64)

    @field_validator("checked_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class CapabilityFlags(WireModel):
    api: Literal[True] = True
    database: bool
    redis: bool
    worker: bool
    simulation_runtime: bool
    dubai_network_import: Literal[False] = False
    traffic_simulation: Literal[False] = False
    ai_forecasting: Literal[False] = False


class SystemCapabilities(WireModel):
    application: Literal["EARTHMIND"] = "EARTHMIND"
    version: Literal["0.1.0"] = "0.1.0"
    milestone: Literal["M01"] = "M01"
    capabilities: CapabilityFlags
    runtime: SumoRuntimeRecord | None = None


class DiagnosticRequest(WireModel):
    kind: DiagnosticKind


class DiagnosticJob(WireModel):
    job_id: UUID
    kind: DiagnosticKind
    status: DiagnosticStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime
    result: dict[str, JsonValue] | None = None
    error: str | None = Field(default=None, max_length=512)

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
