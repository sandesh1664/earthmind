"""Restricted, checksum-verified immutable run artifacts; never accept client paths."""

import hashlib
import json
from pathlib import Path, PurePosixPath
from uuid import UUID

from earthmind_contracts.simulation import MAX_CHUNK_BYTES, PublishedResult, ReplayManifest

MAX_OUTPUT_BYTES = 256 * 1024 * 1024


def artifact_path(root: Path, run_id: UUID, relative_path: str) -> Path:
    item = PurePosixPath(relative_path)
    if (
        item.is_absolute()
        or not item.parts
        or item.parts[0] != str(run_id)
        or any(part in {"", ".", ".."} for part in relative_path.split("/"))
        or "\\" in relative_path
        or ":" in relative_path
        or len(relative_path) > 512
    ):
        raise ValueError("Invalid run artifact reference")
    base = root.resolve(strict=True)
    cursor = base
    for part in item.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("Symlinked artifacts are not accepted")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base / str(run_id)) or not result.is_file():
        raise ValueError("Artifact is outside its run workspace")
    return result


def verified_bytes(
    root: Path,
    run_id: UUID,
    relative_path: str,
    expected_sha256: str,
    size_bytes: int,
    max_bytes: int = MAX_CHUNK_BYTES,
) -> bytes:
    if size_bytes < 0 or size_bytes > max_bytes:
        raise ValueError("Artifact exceeds its read budget")
    path = artifact_path(root, run_id, relative_path)
    if path.stat().st_size != size_bytes:
        raise ValueError("Artifact byte size differs from its publication record")
    with path.open("rb") as source:
        payload = source.read(max_bytes + 1)
    if len(payload) != size_bytes or hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("Artifact checksum differs from its publication record")
    return payload


def validate_publication(root: Path, run_id: UUID, result: PublishedResult) -> ReplayManifest:
    if sum(item.size_bytes for item in result.artifacts) > MAX_OUTPUT_BYTES:
        raise ValueError("Run output exceeds its total byte budget")
    records = {item.artifact_type: item for item in result.artifacts}
    if len(records) != len(result.artifacts):
        raise ValueError("Published artifact categories must be unique")
    metric_keys = {(item.metric_name, item.aggregation) for item in result.metrics}
    if len(metric_keys) != len(result.metrics):
        raise ValueError("Published metric identifiers must be unique")
    manifest_record = records.get("replay_manifest")
    if manifest_record is None or result.manifest_path != manifest_record.relative_path:
        raise ValueError("A verified replay manifest is required")
    manifest: ReplayManifest | None = None
    for item in result.artifacts:
        if item.artifact_type.startswith("replay_chunk:"):
            maximum = MAX_CHUNK_BYTES
        elif item.artifact_type == "replay_manifest":
            maximum = 1024 * 1024
        else:
            maximum = MAX_OUTPUT_BYTES
        payload = verified_bytes(
            root, run_id, item.relative_path, item.checksum_sha256, item.size_bytes, maximum
        )
        if item.artifact_type == "replay_manifest":
            manifest = ReplayManifest.model_validate_json(payload)
    if manifest is None or manifest.run_id != run_id:
        raise ValueError("Replay manifest does not belong to this run")
    for chunk in manifest.chunks:
        record = records.get(f"replay_chunk:{chunk.id}")
        if record is None or (record.checksum_sha256, record.size_bytes) != (
            chunk.sha256,
            chunk.size_bytes,
        ):
            raise ValueError("Replay chunk metadata differs from verified artifacts")
    return manifest


def safe_json(payload: bytes) -> object:
    """JSON only, bounded by verified_bytes before parsing; no pickle or arbitrary execution."""
    return json.loads(payload)


def validate_result_metrics(
    result: PublishedResult, expected_trips: int, manifest: ReplayManifest | None = None
) -> None:
    values = {item.metric_name: item.value for item in result.metrics}
    required = {
        "generated_trips",
        "departed_trips",
        "completed_trips",
        "incomplete_trips",
        "mean_trip_duration",
        "mean_time_loss",
        "mean_waiting_time",
        "mean_moving_speed",
        "teleports",
        "simulation_duration",
        "worker_execution_time",
    }
    if not required.issubset(values):
        raise ValueError("Required SUMO measurements are missing")
    counts = [
        values[name]
        for name in ("generated_trips", "departed_trips", "completed_trips", "incomplete_trips")
    ]
    if any(value is None or value < 0 or not value.is_integer() for value in counts):
        raise ValueError("SUMO trip counts must be nonnegative integer measurements")
    generated, departed, completed, incomplete = counts
    if (
        generated != expected_trips
        or departed is None
        or completed is None
        or not 0 <= completed <= departed <= generated
        or incomplete != generated - completed
    ):
        raise ValueError("SUMO trip measurements are inconsistent with generated demand")
    for name in ("mean_trip_duration", "mean_time_loss", "mean_waiting_time"):
        if (values[name] is None) != (completed == 0):
            raise ValueError(
                "Completed-trip means must be unavailable exactly when no trips qualify"
            )
    if any(value is not None and value < 0 for value in values.values()):
        raise ValueError("SUMO measurement cannot be negative")

    if manifest is not None:
        if values["simulation_duration"] != manifest.duration_seconds:
            raise ValueError("Metric duration differs from the recorded replay timeline")
        if departed and (
            not manifest.chunks or sum(item.sample_count for item in manifest.chunks) == 0
        ):
            raise ValueError("Departed vehicles require nonempty recorded replay samples")
        if manifest.counts:
            final = manifest.counts[-1]
            if final.departed != departed or final.arrived != completed:
                raise ValueError("Recorded final lifecycle counts differ from SUMO metrics")
        elif departed:
            raise ValueError("Departed vehicles require recorded lifecycle counts")
