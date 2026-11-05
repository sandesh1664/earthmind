"""Bounded on-disk trajectory chunks; actual event times preserve lifecycle gaps."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

MAX_CHUNK_BYTES = 4 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 256 * 1024 * 1024
MAX_CHUNKS = 1900
MAX_FRAMES_PER_CHUNK = 16


class SimulationResourceLimit(ValueError):
    """A configured execution/output safeguard was reached; never publish truncated results."""


def encode_json(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, value: object, maximum: int = MAX_MANIFEST_BYTES) -> None:
    payload = encode_json(value)
    if len(payload) > maximum:
        raise SimulationResourceLimit("JSON artifact exceeds its explicit byte budget")
    temporary = path.with_name(path.name + ".writing")
    with temporary.open("wb") as destination:
        destination.write(payload)
        destination.flush()
        os.fsync(destination.fileno())
    temporary.replace(path)


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while payload := source.read(65536):
            digest.update(payload)
    return digest.hexdigest()


def artifact(path: Path, directory: Path, run_id: str, category: str) -> dict[str, Any]:
    if path.is_symlink() or path.resolve().is_relative_to(directory.resolve()) is False:
        raise ValueError("Artifact path escapes its isolated run workspace")
    relative = path.relative_to(directory).as_posix()
    content_type = (
        "application/json"
        if path.suffix == ".json"
        else "application/xml"
        if path.suffix == ".xml"
        else "text/plain; charset=utf-8"
    )
    return {
        "artifact_type": category,
        "relative_path": f"{run_id}/{relative}",
        "checksum_sha256": checksum(path),
        "size_bytes": path.stat().st_size,
        "content_type": content_type,
    }


def output_bytes(directory: Path) -> int:
    result = 0
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Run workspaces cannot contain symbolic links")
        if path.is_file():
            size = path.stat().st_size
            if path.suffix == ".log" and size > 2 * 1024 * 1024:
                raise SimulationResourceLimit(
                    "Native diagnostic log exceeded the 2 MiB per-file budget"
                )
            result += size
            if result > MAX_OUTPUT_BYTES:
                raise SimulationResourceLimit(
                    "Simulation output exceeded the 256 MiB per-run budget"
                )
    return result


class TrajectoryWriter:
    def __init__(self, directory: Path, run_id: str) -> None:
        self.directory = directory
        self.replay_directory = directory / "replay"
        self.replay_directory.mkdir()
        self.run_id = run_id
        self.frames: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.chunks: list[dict[str, Any]] = []
        self.counts: list[dict[str, Any]] = []
        self.written_bytes = 0
        self.new_data = False

    def event(self, identifier: str, time_seconds: float, kind: str) -> None:
        if kind not in {"departed", "arrived", "teleport_start", "teleport_end"}:
            raise ValueError("Unknown trajectory lifecycle event")
        self.events.append({"id": identifier, "time": time_seconds, "type": kind})
        self.new_data = True

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "run_id": self.run_id,
            "chunk_id": f"{len(self.chunks):06d}",
            "frames": self.frames,
            "events": self.events,
        }

    def frame(
        self,
        time_seconds: float,
        vehicles: list[dict[str, Any]],
        departed: list[str],
        arrived: list[str],
        teleported: list[str],
        total_departed: int,
        total_arrived: int,
        active_count: int | None = None,
    ) -> None:
        if self.frames and time_seconds <= self.frames[-1]["time"]:
            raise ValueError("Recorded trajectory frame time must increase")
        frame = {
            "time": time_seconds,
            "vehicles": vehicles,
            "departed": departed,
            "arrived": arrived,
            "teleported": teleported,
        }
        self.frames.append(frame)
        self.new_data = True
        self.counts.append(
            {
                "time": time_seconds,
                "active": active_count if active_count is not None else len(vehicles),
                "departed": total_departed,
                "arrived": total_arrived,
            }
        )
        if len(encode_json(self._payload())) > MAX_CHUNK_BYTES:
            self.frames.pop()
            if not self.frames:
                raise SimulationResourceLimit(
                    "A trajectory frame exceeds the 4 MiB replay chunk budget"
                )
            previous_time = self.frames[-1]["time"]
            following_events = [event for event in self.events if event["time"] > previous_time]
            self.events = [event for event in self.events if event["time"] <= previous_time]
            self._flush()
            self.frames.append(frame)
            self.events.extend(following_events)
            self.new_data = True
            if len(encode_json(self._payload())) > MAX_CHUNK_BYTES:
                raise SimulationResourceLimit(
                    "Trajectory frame/events exceed the replay chunk budget"
                )
        if len(self.frames) >= MAX_FRAMES_PER_CHUNK:
            self._flush()

    def _flush(self) -> None:
        if not self.frames or not self.new_data:
            return
        if len(self.chunks) >= MAX_CHUNKS:
            raise SimulationResourceLimit("Replay exceeds the 1900-chunk manifest budget")
        path = self.replay_directory / f"{len(self.chunks):06d}.json"
        payload = encode_json(self._payload())
        if len(payload) > MAX_CHUNK_BYTES:
            raise SimulationResourceLimit("Replay chunk exceeds its bounded wire budget")
        self.written_bytes += len(payload)
        if self.written_bytes > MAX_OUTPUT_BYTES:
            raise SimulationResourceLimit("Trajectory output exceeds the per-run output budget")
        path.write_bytes(payload)
        self.chunks.append(
            {
                "id": path.stem,
                "start_time": self.frames[0]["time"],
                "end_time": self.frames[-1]["time"],
                "sample_count": sum(len(frame["vehicles"]) for frame in self.frames),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
        # One overlap frame permits interpolation across chunk boundaries. Exact
        # boundary events are duplicated intentionally and keyed by id/time/type.
        self.frames = [self.frames[-1]]
        self.events = [event for event in self.events if event["time"] == self.frames[0]["time"]]
        self.new_data = False

    def finish(
        self, network_id: str, duration_seconds: float, sample_interval_seconds: int
    ) -> dict[str, Any]:
        self._flush()
        manifest = {
            "schema_version": 1,
            "run_id": self.run_id,
            "network_version_id": network_id,
            "duration_seconds": duration_seconds,
            "sample_interval_seconds": sample_interval_seconds,
            "vehicle_class": "passenger",
            "synthetic": True,
            "coordinate_reference_system": "EPSG:4326",
            "chunks": self.chunks,
            "counts": self.counts,
        }
        atomic_json(self.directory / "replay-manifest.json", manifest)
        return manifest
