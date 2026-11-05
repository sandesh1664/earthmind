"""Actual loopback M04 API acceptance; never substitutes mock traffic or tile data.

Examples (run only with the owner's intended live local stack):
  uv run --locked python scripts/verify_simulation_pipeline.py --trip-target 500 \
      --duration 600 --seed 42 --output /tmp/m04-500.json
  uv run --locked python scripts/verify_simulation_pipeline.py --mode running-cancel \
      --trip-target 2000 --duration 1800 --distribution burst --output /tmp/m04-cancel.json

Failure/stale modes OBSERVE an explicitly provided real run after an independently
controlled fault. They do not corrupt shared inputs or stop shared services.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import signal
import statistics
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from dotenv import dotenv_values
from earthmind_contracts.simulation import (
    MAX_CHUNK_BYTES,
    DemandConfig,
    ReplayManifest,
    RunMetricsResponse,
    RunResponse,
    TrajectoryChunk,
    canonical_checksum,
)
from smoke import port

MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_REPLAY_TOTAL_BYTES = 256 * 1024 * 1024
MAX_RETAINED_LATENCIES = 1000
TERMINAL = {"succeeded", "failed", "cancelled"}


def developer_token() -> str:
    """Read only this existing private gate setting; never expose it to evidence."""
    name = "EARTHMIND_DEV_WRITE_TOKEN"
    configured = os.environ.get(name)
    if configured:
        return configured
    path = Path(".env")
    if path.is_file():
        with path.open() as source:
            for line in source:
                key, separator, _ = line.partition("=")
                if separator and key.strip().removeprefix("export ").strip() == name:
                    # Parse only the selected line, with no interpolation of other settings.
                    value = dotenv_values(stream=io.StringIO(line), interpolate=False).get(name)
                    if value:
                        return value
    raise RuntimeError("Existing local development write authorization is not configured")


def safe_error(value: object, token: str = "") -> str:
    text = str(value)
    if token:
        text = text.replace(token, "[REDACTED]")
    text = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[REDACTED]", text)
    return text[:1000]


@dataclass
class Timing:
    count: int = 0
    total_ms: float = 0
    minimum_ms: float = math.inf
    maximum_ms: float = 0
    values: deque[float] = field(default_factory=lambda: deque(maxlen=MAX_RETAINED_LATENCIES))

    def add(self, milliseconds: float) -> None:
        self.count += 1
        self.total_ms += milliseconds
        self.minimum_ms = min(self.minimum_ms, milliseconds)
        self.maximum_ms = max(self.maximum_ms, milliseconds)
        self.values.append(milliseconds)

    def summary(self) -> dict[str, object]:
        values = sorted(self.values)
        return {
            "observations": self.count,
            "minimum_ms": round(self.minimum_ms, 3) if self.count else None,
            "maximum_ms": round(self.maximum_ms, 3) if self.count else None,
            "mean_ms": round(self.total_ms / self.count, 3) if self.count else None,
            "retained_window_samples": len(values),
            "retained_window_median_ms": round(statistics.median(values), 3) if values else None,
            "retained_window_p95_ms": round(values[math.ceil(len(values) * 0.95) - 1], 3)
            if values
            else None,
        }


class AcceptanceClient:
    def __init__(self, token: str) -> None:
        self.token = token
        try:
            api_port = port("API_PORT", "8000")
        except ValueError as error:
            raise RuntimeError("Configured API_PORT must be a valid loopback port") from error
        self.origin = f"http://127.0.0.1:{api_port}"
        self.client = httpx.Client(
            base_url=self.origin, timeout=10, follow_redirects=False, trust_env=False
        )
        self.phase = "setup"
        self.timings: dict[str, Timing] = {}
        self.requests: deque[dict[str, object]] = deque(maxlen=200)
        self.owned_runs: list[str] = []

    def raw(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
        maximum: int = MAX_JSON_BYTES,
        idempotency_key: str | None = None,
    ) -> tuple[int, bytes, str]:
        if not path.startswith("/api/v1/") or ".." in path or path.startswith("//"):
            raise ValueError("Only fixed versioned loopback API paths are permitted")
        headers = {"Accept": "application/json"}
        if method == "POST":
            headers["X-Earthmind-Dev-Token"] = self.token
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        started = time.monotonic()
        with self.client.stream(method, path, json=payload, headers=headers) as response:
            result = bytearray()
            for chunk in response.iter_bytes():
                if len(result) + len(chunk) > maximum:
                    raise RuntimeError("API response exceeded its verification byte budget")
                result.extend(chunk)
            status = response.status_code
            content_type = response.headers.get("content-type", "").split(";")[0]
        elapsed = (time.monotonic() - started) * 1000
        category = re.sub(
            r"/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", "/{id}", path.split("?")[0]
        )
        key = f"{self.phase} {method} {category}"
        self.timings.setdefault(key, Timing()).add(elapsed)
        self.requests.append(
            {
                "phase": self.phase,
                "method": method,
                "path": path.split("?")[0],
                "status": status,
                "elapsed_ms": round(elapsed, 3),
            }
        )
        if status not in expected:
            # Never echo request headers, arbitrary response bodies or environment settings.
            raise RuntimeError(
                f"{method} {path.split('?')[0]} returned HTTP {status}; expected {expected}"
            )
        return status, bytes(result), content_type

    def json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _, body, content_type = self.raw(
            method, path, payload, expected, idempotency_key=idempotency_key
        )
        if content_type != "application/json":
            raise RuntimeError("Expected a JSON API response")
        value = json.loads(body)
        if not isinstance(value, dict):
            raise RuntimeError("Expected an API response object")
        return value

    def submit(self, scenario_id: str, retry_of: str | None = None) -> dict[str, Any]:
        key = f"m04-acceptance-{uuid4()}"
        payload: dict[str, Any] = {"scenario_id": scenario_id}
        if retry_of is not None:
            payload["retry_of"] = retry_of
        first = self.json("POST", "/api/v1/simulations", payload, (202,), key)
        run_id = str(UUID(first["id"]))
        self.owned_runs.append(run_id)
        repeated = self.json("POST", "/api/v1/simulations", payload, (202,), key)
        if repeated["id"] != run_id:
            raise RuntimeError("Idempotent submission produced a duplicate run")
        RunResponse.model_validate(first)
        return first

    def run(self, run_id: str) -> dict[str, Any]:
        value = self.json("GET", f"/api/v1/simulations/{UUID(run_id)}")
        RunResponse.model_validate(value)
        return value

    def cancel(self, run_id: str) -> dict[str, Any]:
        return self.json("POST", f"/api/v1/simulations/{UUID(run_id)}/cancel", {})

    def cleanup(self) -> list[dict[str, str]]:
        outcomes = []
        for run_id in reversed(self.owned_runs):
            try:
                current = self.run(run_id)
                if current["status"] in {"queued", "running"}:
                    self.cancel(run_id)
                    deadline = time.monotonic() + 35
                    while time.monotonic() < deadline:
                        current = self.run(run_id)
                        if current["status"] in TERMINAL:
                            break
                        time.sleep(0.5)
                outcomes.append({"run_id": run_id, "status": current["status"]})
            except (OSError, ValueError, RuntimeError, httpx.HTTPError) as error:
                outcomes.append(
                    {
                        "run_id": run_id,
                        "status": "cleanup_failed",
                        "error": safe_error(error, self.token),
                    }
                )
        return outcomes


def select_network(client: AcceptanceClient, requested: UUID | None) -> dict[str, Any]:
    for offset in range(0, 500, 100):
        page = client.json("GET", f"/api/v1/simulation-networks?limit=100&offset={offset}")
        for item in page["items"]:
            if requested is not None and item["id"] != str(requested):
                continue
            if (
                item.get("is_synthetic") is False
                and item.get("validation", {}).get("valid") is True
            ):
                if not item.get("network_artifact_sha256") or not item.get("source_checksum"):
                    raise RuntimeError("Compatible network lacks source/conversion provenance")
                return cast_network(item)
        if offset + len(page["items"]) >= page["total"]:
            break
    raise RuntimeError(
        "No matching imported real SUMO-compatible network passed actual API validation"
    )


def cast_network(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Network response is not an object")
    return value


def create_scenario(
    client: AcceptanceClient, network: dict[str, Any], demand: DemandConfig, label: str
) -> dict[str, Any]:
    result = client.json(
        "POST",
        "/api/v1/scenarios",
        {
            "name": (
                f"M04 {label}: {demand.effective_trip_count} synthetic trips {str(uuid4())[:8]}"
            ),
            "network_version_id": network["id"],
            "demand": demand.model_dump(mode="json"),
        },
        (201,),
    )
    validation = client.json("POST", f"/api/v1/scenarios/{UUID(result['id'])}/validate", {})
    if result.get("synthetic") is not True or not validation.get("valid"):
        raise RuntimeError("Created synthetic scenario did not pass actual network validation")
    expected = canonical_checksum({"network_version_id": network["id"], "demand": result["demand"]})
    if result.get("configuration_checksum") != expected:
        raise RuntimeError("Scenario configuration checksum is inconsistent")
    return result


def await_state(
    client: AcceptanceClient,
    run_id: str,
    wall_limit: float,
    expected: str = "succeeded",
    stop_at_running: bool = False,
    poll_interval: float = 0.5,
    probe_network: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.monotonic() + wall_limit
    observations: list[dict[str, Any]] = []
    last_signature: tuple[object, ...] | None = None
    last_network_probe = 0.0
    while time.monotonic() < deadline:
        run = client.run(run_id)
        status = run["status"]
        client.phase = str(status)
        progress = run["progress"]
        signature = (
            status,
            progress["simulated_seconds"],
            progress["departed"],
            progress["completed"],
        )
        if signature != last_signature and len(observations) < 1000:
            observations.append(
                {
                    "observed_at": datetime.now(UTC).isoformat(),
                    "status": status,
                    "progress": progress,
                    "worker_id": run["worker_id"],
                }
            )
            last_signature = signature
        if status == "running":
            client.json("GET", "/api/v1/health")
            if probe_network is not None and time.monotonic() - last_network_probe >= 1:
                client.json("GET", f"/api/v1/networks/{UUID(probe_network)}")
                last_network_probe = time.monotonic()
            if stop_at_running and progress["simulated_seconds"] > 0:
                # A claimed DB row alone is not proof SUMO has started. Cancellation
                # verification waits for actual native simulationStep progress.
                return run, observations
        if status in TERMINAL:
            if stop_at_running or status != expected:
                raise RuntimeError(
                    f"Actual run reached {status} instead of {expected}; "
                    f"error_code={run.get('error_code')}"
                )
            return run, observations
        time.sleep(poll_interval)
    raise TimeoutError(
        "Actual simulation did not reach its required state "
        "within the wall-clock verification limit"
    )


def verify_results(
    client: AcceptanceClient, run: dict[str, Any], network: dict[str, Any], minimum_completed: int
) -> dict[str, Any]:
    client.phase = "results"
    run_id = str(UUID(run["id"]))
    metrics_response = client.json("GET", f"/api/v1/simulations/{run_id}/metrics")
    RunMetricsResponse.model_validate(metrics_response)
    metrics = {item["metric_name"]: item for item in metrics_response["metrics"]}
    if len(metrics) != len(metrics_response["metrics"]):
        raise RuntimeError("Ambiguous duplicate metric names in this run's export")
    required = {
        "generated_trips",
        "departed_trips",
        "completed_trips",
        "incomplete_trips",
        "mean_trip_duration",
        "mean_time_loss",
        "mean_moving_speed",
        "mean_waiting_time",
        "teleports",
        "simulation_duration",
        "worker_execution_time",
    }
    if not required.issubset(metrics):
        raise RuntimeError("Actual completed run lacks required SUMO metrics")
    exported = client.json("GET", f"/api/v1/simulations/{run_id}/export?format=json")
    provenance = exported["reproducibility"]
    inputs = provenance["input"]
    demand = DemandConfig.model_validate(inputs["demand"])
    if metrics["generated_trips"]["value"] != demand.effective_trip_count:
        raise RuntimeError("Generated trip metric differs from deterministic demand inputs")
    generated = metrics["generated_trips"]["value"]
    departed = metrics["departed_trips"]["value"]
    completed = metrics["completed_trips"]["value"]
    if any(
        not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in (generated, departed, completed)
    ):
        raise RuntimeError("Actual trip count measurements are unavailable or nonfinite")
    for name in ("mean_trip_duration", "mean_time_loss", "mean_waiting_time"):
        if (metrics[name]["value"] is None) != (completed == 0):
            raise RuntimeError("Completed-trip means are inconsistent with qualifying trip counts")
    if not 0 <= completed <= departed <= generated or completed < minimum_completed:
        raise RuntimeError("Actual trip counts fail completion/count acceptance")
    if metrics["incomplete_trips"]["value"] != generated - completed:
        raise RuntimeError(
            "Incomplete trip count does not include every uncompleted generated trip"
        )
    if (
        not run.get("engine_version")
        or not run.get("worker_id")
        or not run.get("started_at")
        or not run.get("finished_at")
    ):
        raise RuntimeError("Succeeded run lacks actual worker/engine execution metadata")
    if (
        provenance["input_sha256"] != run["input_sha256"]
        or canonical_checksum(inputs) != run["input_sha256"]
    ):
        raise RuntimeError("Run input checksum differs from exported reproducibility inputs")
    if (
        inputs["network_version_id"] != network["id"]
        or inputs["source_sha256"] != network["source_checksum"]
        or inputs["network_sha256"] != network["network_artifact_sha256"]
    ):
        raise RuntimeError("Run input lineage differs from the selected actual network")
    if exported.get("synthetic") is not True or exported["run"]["id"] != run_id:
        raise RuntimeError("Export does not retain run identity and synthetic disclosure")
    _, csv_bytes, media_type = client.raw("GET", f"/api/v1/simulations/{run_id}/export?format=csv")
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode())))
    if (
        media_type != "text/csv"
        or len(rows) != len(metrics)
        or any(row["run_id"] != run_id for row in rows)
    ):
        raise RuntimeError("CSV export rows do not match the actual run metrics")
    manifest = ReplayManifest.model_validate(
        client.json("GET", f"/api/v1/simulations/{run_id}/replay/manifest")
    )
    if str(manifest.run_id) != run_id or str(manifest.network_version_id) != network["id"]:
        raise RuntimeError("Replay manifest does not match its source run/network")
    if manifest.duration_seconds != metrics["simulation_duration"]["value"]:
        raise RuntimeError("Replay timeline differs from measured SUMO simulated duration")
    total_bytes = 0
    total_samples = 0
    largest_frame = 0
    movement_observed = False
    previous: dict[tuple[str, int], tuple[float, float, float]] = {}
    example_positions: list[dict[str, float | str]] = []
    for descriptor in manifest.chunks:
        total_bytes += descriptor.size_bytes
        if total_bytes > MAX_REPLAY_TOTAL_BYTES:
            raise RuntimeError("Replay exceeds the bounded total output budget")
        _, payload, content_type = client.raw(
            "GET",
            f"/api/v1/simulations/{run_id}/replay/chunks/{descriptor.id}",
            maximum=MAX_CHUNK_BYTES,
        )
        if (
            content_type != "application/json"
            or len(payload) != descriptor.size_bytes
            or hashlib.sha256(payload).hexdigest() != descriptor.sha256
        ):
            raise RuntimeError("Replay HTTP bytes differ from the manifest size/SHA256")
        chunk = TrajectoryChunk.model_validate_json(payload)
        if str(chunk.run_id) != run_id or chunk.chunk_id != descriptor.id:
            raise RuntimeError("Replay chunk identity does not match the requested run")
        observed_samples = sum(len(frame.vehicles) for frame in chunk.frames)
        if observed_samples != descriptor.sample_count:
            raise RuntimeError("Replay sample count differs from its descriptor")
        total_samples += observed_samples
        for frame in chunk.frames:
            largest_frame = max(largest_frame, len(frame.vehicles))
            for vehicle in frame.vehicles:
                key = (vehicle.id, vehicle.segment_id)
                position = (frame.time, vehicle.longitude, vehicle.latitude)
                old = previous.get(key)
                if (
                    old is not None
                    and frame.time > old[0]
                    and (
                        abs(vehicle.longitude - old[1]) > 1e-8
                        or abs(vehicle.latitude - old[2]) > 1e-8
                    )
                ):
                    movement_observed = True
                if old is None and vehicle.speed > 0.1 and len(example_positions) < 6:
                    example_positions.append(
                        {
                            "vehicle_id": vehicle.id,
                            "time": frame.time,
                            "longitude": vehicle.longitude,
                            "latitude": vehicle.latitude,
                        }
                    )
                previous[key] = position
                if len(previous) > 20000:
                    raise RuntimeError("Replay vehicle/segment identity budget exceeded")
    if departed > 0 and (total_samples == 0 or not movement_observed):
        raise RuntimeError("No recorded movement was observed in actual SUMO replay samples")
    proximity = []
    for road_position in example_positions:
        page = client.json(
            "GET",
            f"/api/v1/geo/nearby-edges?network_id={network['id']}&longitude={road_position['longitude']}&latitude={road_position['latitude']}&radius_m=100&limit=1",
        )
        if not page["features"]:
            raise RuntimeError(
                "Recorded vehicle position has no imported road "
                "within the explicit 100m proximity check"
            )
        distance = page["features"][0]["properties"]["distance_m"]
        if (
            not isinstance(distance, (float, int))
            or not math.isfinite(distance)
            or not 0 <= distance <= 100
        ):
            raise RuntimeError("Recorded position proximity is not a bounded geodesic measurement")
        proximity.append({**road_position, "nearest_imported_road_distance_m": distance})
    if manifest.counts and (
        manifest.counts[-1].departed != departed or manifest.counts[-1].arrived != completed
    ):
        raise RuntimeError("Replay final cumulative lifecycle counts differ from SUMO trip metrics")
    return {
        "metrics": metrics_response["metrics"],
        "reproducibility": provenance,
        "replay": {
            "chunks_verified": len(manifest.chunks),
            "total_bytes": total_bytes,
            "samples_verified": total_samples,
            "largest_recorded_vehicle_frame": largest_frame,
            "movement_observed": movement_observed,
            "duration_seconds": manifest.duration_seconds,
            "maximum_recorded_active_count": max(
                (item.active for item in manifest.counts), default=0
            ),
            "source_proximity_samples": proximity,
            "proximity_scope": (
                "Actual PostGIS geodesic checks within100m; not surveyed lane accuracy"
            ),
            "browser_rendering_status": "NOT RUN by this API helper",
        },
        "exports": {"json_verified": True, "csv_rows_verified": len(rows)},
        "m04_500_trip_target": "PASS"
        if demand.effective_trip_count >= 500
        else "NOT RUN (smaller requested run)",
    }


def verify_terminal_rejection(client: AcceptanceClient, run: dict[str, Any]) -> dict[str, Any]:
    run_id = str(UUID(run["id"]))
    for suffix in ("metrics", "replay/manifest", "export"):
        client.raw("GET", f"/api/v1/simulations/{run_id}/{suffix}", expected=(409,))
    for _ in range(3):
        if client.run(run_id)["status"] != run["status"]:
            raise RuntimeError("Terminal run state changed after cancellation/failure")
        time.sleep(0.2)
    events = client.json("GET", f"/api/v1/simulations/{run_id}/events?limit=100")
    return {
        "verified_terminal_status": run["status"],
        "error_code": run.get("error_code"),
        "unpublished_results_returned_409": True,
        "events": events["items"],
        "native_process_cleanup": "Requires the independent worker/container process check",
    }


def write_evidence(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    options = argparse.ArgumentParser(description=__doc__)
    options.add_argument("--trip-target", type=int, default=500)
    options.add_argument("--duration", type=int, default=600)
    options.add_argument("--seed", type=int, default=42)
    options.add_argument(
        "--distribution", choices=["uniform", "poisson", "burst"], default="uniform"
    )
    options.add_argument("--multiplier", type=float, default=1)
    options.add_argument("--sample-interval", type=int, default=2)
    options.add_argument("--network-id", type=UUID)
    options.add_argument(
        "--run-id", type=UUID, help="Explicit existing run for retry/failure/stale observation"
    )
    options.add_argument(
        "--mode",
        choices=[
            "run",
            "observe-success",
            "running-cancel",
            "queued-cancel",
            "retry",
            "observe-failure",
            "observe-stale",
        ],
        default="run",
    )
    options.add_argument("--wall-limit", type=float, default=600)
    options.add_argument("--poll-interval", type=float, default=0.5)
    options.add_argument("--minimum-completed", type=int, default=1)
    options.add_argument("--output", type=Path, required=True)
    options.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly replace only a prior verification JSON report",
    )
    return options


def main() -> int:
    options = parser().parse_args()
    if not Path("apps/api").is_dir() or not Path("pyproject.toml").is_file():
        raise SystemExit("Run this helper from the EARTHMIND repository root")
    output_path = options.output.resolve()
    if output_path.suffix != ".json" or output_path.is_relative_to((Path.cwd() / "data").resolve()):
        raise SystemExit(
            "Output must be a verification .json report outside the preserved data directory"
        )
    if output_path.exists() and not options.overwrite:
        raise SystemExit(
            "Verification report exists; choose a new output or explicitly use --overwrite"
        )
    if not 10 <= options.wall_limit <= 1800 or not 0.2 <= options.poll_interval <= 5:
        raise SystemExit("Wall limit must be10..1800s; polling0.2..5s")
    if options.minimum_completed < 0:
        raise SystemExit("Minimum completed trips must be nonnegative")
    if (
        options.mode in {"retry", "observe-success", "observe-failure", "observe-stale"}
        and options.run_id is None
    ):
        raise SystemExit(
            "This mode requires an explicit --run-id; fault injection is performed independently"
        )
    demand = DemandConfig(
        trip_target=options.trip_target,
        duration_seconds=options.duration,
        seed=options.seed,
        departure_distribution=options.distribution,
        demand_multiplier=options.multiplier,
        sample_interval_seconds=options.sample_interval,
    )
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "RUNNING",
        "mode": options.mode,
        "started_at": datetime.now(UTC).isoformat(),
        "disclosure": "Actual SUMO execution with synthetic demand on retained OSM-derived "
        "Dubai roads; "
        "no observed RTA traffic",
        "demand": demand.model_dump(mode="json"),
        "fault_injection": "NOT RUN by this helper",
    }
    client: AcceptanceClient | None = None
    try:
        client = AcceptanceClient("" if options.mode.startswith("observe-") else developer_token())
        if options.mode == "observe-success":
            run_id = str(options.run_id)
            final, observations = await_state(
                client, run_id, options.wall_limit, poll_interval=options.poll_interval
            )
            network = select_network(client, UUID(final["network_version_id"]))
            verification = verify_results(client, final, network, options.minimum_completed)
            result.update(
                {
                    "run_id": run_id,
                    "run": final,
                    "network": network,
                    "progress_observations": observations,
                    "verification": verification,
                    "demand": verification["reproducibility"]["input"]["demand"],
                    "submission_scope": "NOT RUN; existing actual run inspected read-only",
                }
            )
        elif options.mode in {"observe-failure", "observe-stale"}:
            run_id = str(options.run_id)
            final, observations = await_state(
                client, run_id, options.wall_limit, "failed", poll_interval=options.poll_interval
            )
            if options.mode == "observe-stale" and final.get("error_code") != "worker_lost":
                raise RuntimeError("Stale-worker check did not report an expired worker lease")
            result.update(
                {
                    "run_id": run_id,
                    "progress_observations": observations,
                    "failure_verification": verify_terminal_rejection(client, final),
                }
            )
        else:
            parent = client.run(str(options.run_id)) if options.mode == "retry" else None
            requested_network = options.network_id
            if parent is not None:
                if (
                    requested_network is not None
                    and str(requested_network) != parent["network_version_id"]
                ):
                    raise RuntimeError("Retry network selection differs from its parent run")
                requested_network = UUID(parent["network_version_id"])
            network = select_network(client, requested_network)
            result["network"] = network
            if options.mode == "retry":
                if parent is None:
                    raise RuntimeError("Retry parent is unavailable")
                if parent["status"] not in {"failed", "cancelled"}:
                    raise RuntimeError("Retry requires an actual failed/cancelled parent run")
                scenario_id = parent["scenario_id"]
                parent_scenario = client.json("GET", f"/api/v1/scenarios/{UUID(scenario_id)}")
                result["scenario_id"] = scenario_id
                result["demand"] = {**parent_scenario["demand"], "seed": parent["seed"]}
                run = client.submit(scenario_id, parent["id"])
                if (
                    run["id"] == parent["id"]
                    or run["attempt_number"] != parent["attempt_number"] + 1
                    or run["retry_of"] != parent["id"]
                ):
                    raise RuntimeError("Retry did not create a linked new tracked attempt")
            else:
                scenario = create_scenario(client, network, demand, options.mode)
                result["scenario_id"] = scenario["id"]
                if options.mode == "queued-cancel":
                    blocker_demand = demand.model_copy(
                        update={
                            "trip_target": max(1000, demand.trip_target),
                            "demand_multiplier": 1.0,
                            "duration_seconds": max(120, demand.duration_seconds),
                            "departure_distribution": "burst",
                        }
                    )
                    blocker_scenario = create_scenario(
                        client, network, blocker_demand, "controlled worker occupancy"
                    )
                    blocker = client.submit(blocker_scenario["id"])
                    await_state(
                        client,
                        blocker["id"],
                        options.wall_limit,
                        stop_at_running=True,
                        poll_interval=options.poll_interval,
                    )
                    result["occupancy_run_id"] = blocker["id"]
                run = client.submit(scenario["id"])
            result["run_id"] = run["id"]
            write_evidence(options.output, result)
            if options.mode == "queued-cancel":
                cancelled = client.cancel(run["id"])
                if cancelled["status"] != "cancelled" or cancelled.get("started_at") is not None:
                    raise RuntimeError(
                        "Queued cancellation raced native execution; "
                        "no queued-cancel PASS is claimed"
                    )
                result["cancellation"] = verify_terminal_rejection(client, cancelled)
            elif options.mode == "running-cancel":
                running, observations = await_state(
                    client,
                    run["id"],
                    options.wall_limit,
                    stop_at_running=True,
                    poll_interval=options.poll_interval,
                    probe_network=network["id"],
                )
                if running["status"] != "running":
                    raise RuntimeError("Native job was not observed running before cancellation")
                client.cancel(run["id"])
                final, tail = await_state(
                    client,
                    run["id"],
                    options.wall_limit,
                    "cancelled",
                    poll_interval=options.poll_interval,
                )
                result["progress_observations"] = observations + tail
                result["cancellation"] = verify_terminal_rejection(client, final)
            else:
                final, observations = await_state(
                    client,
                    run["id"],
                    options.wall_limit,
                    poll_interval=options.poll_interval,
                    probe_network=network["id"],
                )
                result["progress_observations"] = observations
                result["run"] = final
                result["verification"] = verify_results(
                    client, final, network, options.minimum_completed
                )
            result["status"] = "PASS"
        result["status"] = "PASS"
        return_code = 0
    except (Exception, KeyboardInterrupt) as error:
        result["status"] = "FAIL"
        result["error"] = (
            f"{type(error).__name__}: {safe_error(error, client.token if client else '')}"
        )
        return_code = 130 if isinstance(error, KeyboardInterrupt) else 1
    finally:
        if client is not None:
            result["owned_run_cleanup"] = client.cleanup()
            if any(
                item["status"] == "cleanup_failed" or item["status"] in {"queued", "running"}
                for item in result["owned_run_cleanup"]
            ):
                result["status"] = "FAIL"
                result["cleanup_error"] = (
                    "An owned run did not reach a terminal state after cleanup"
                )
                return_code = 1
            result["http_timings"] = {
                name: value.summary() for name, value in client.timings.items()
            }
            result["recent_http_requests"] = list(client.requests)
            client.client.close()
        result["finished_at"] = datetime.now(UTC).isoformat()
        write_evidence(options.output, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "mode": result["mode"],
                "run_id": result.get("run_id"),
                "output": str(options.output),
                "error": result.get("error"),
            },
            sort_keys=True,
        )
    )
    return return_code


if __name__ == "__main__":

    def interrupted(_signal: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())
