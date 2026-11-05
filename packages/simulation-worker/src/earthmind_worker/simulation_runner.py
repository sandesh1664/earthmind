"""Isolated native SUMO execution. Never run this engine inside an API handler."""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import io
import math
import platform
import resource
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from earthmind_contracts.simulation import (
    MetricValue,
    PublishedResult,
    ReplayManifest,
    TrajectoryChunk,
    WorkerClaim,
    canonical_checksum,
)

from earthmind_worker.real_network_smoke import finite_number
from earthmind_worker.runtime_check import EXPECTED_SUMO_VERSION, binary_version
from earthmind_worker.settings import Settings
from earthmind_worker.simulation_artifacts import (
    MAX_OUTPUT_BYTES,
    SimulationResourceLimit,
    TrajectoryWriter,
    artifact,
    atomic_json,
    output_bytes,
)
from earthmind_worker.simulation_demand import generate_demand
from earthmind_worker.simulation_environment import native_environment
from earthmind_worker.simulation_metrics import calculate_metrics
from earthmind_worker.simulation_network import prepare_network


class SimulationInterrupted(RuntimeError):
    pass


def _peak_rss_bytes(who: int) -> int:
    value = int(resource.getrusage(who).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def _check_package_versions() -> dict[str, str]:
    for package in ["sumolib", "traci"]:
        if importlib.metadata.version(package) != EXPECTED_SUMO_VERSION:
            raise ValueError("SUMO Python adapters must match the pinned native engine version")
    return {name: binary_version(name) for name in ["sumo", "netconvert"]}


def execute(claim: WorkerClaim, workspace: Path, input_root: Path) -> PublishedResult:
    import sumolib  # type: ignore[import-untyped]
    import traci  # type: ignore[import-untyped]

    started = time.monotonic()
    config = claim.input_config
    if canonical_checksum(config.model_dump(mode="json")) != claim.input_sha256:
        raise ValueError("Immutable worker input checksum is inconsistent")
    if claim.seed != config.demand.seed:
        raise ValueError("Claimed run seed differs from immutable demand inputs")
    root = input_root.resolve(strict=True)
    source = root / config.network_artifact
    if source.is_symlink() or source.resolve(strict=True).parent != root:
        raise ValueError("Simulation network artifact escapes its configured root")
    snapshot = workspace / "inputs"
    snapshot.mkdir()
    for name in ["network.net.xml", "import-manifest.json", "source-sumo-db-mapping.json"]:
        original = source / name
        if original.is_symlink() or original.resolve(strict=True).parent != source.resolve():
            raise ValueError("Simulation input must be a regular immutable retained file")
        maximum = 64 * 1024 * 1024 if name == "network.net.xml" else 8 * 1024 * 1024
        if not 0 < original.stat().st_size <= maximum:
            raise ValueError("Simulation input file exceeds its bounded size")
        shutil.copyfile(original, snapshot / name)
        (snapshot / name).chmod(0o444)
    prepared = prepare_network(snapshot, str(config.network_version_id))
    for recorded, expected in [
        ("sumo_network_sha256", config.network_sha256),
        ("osm_sha256", config.source_sha256),
        ("mapping_sha256", config.mapping_sha256),
    ]:
        if prepared.provenance[recorded] != expected:
            raise ValueError("Simulation artifact provenance differs from the saved scenario")
    versions = _check_package_versions()
    atomic_json(workspace / "network-audit.json", prepared.audit)
    demand = generate_demand(prepared, config.demand, workspace / "demand.rou.xml")
    writer = TrajectoryWriter(workspace, str(claim.run_id))
    writer.frame(0.0, [], [], [], [], 0, 0)
    port = sumolib.miscutils.getFreeSocketPort()
    process: subprocess.Popen[bytes] | None = None
    connection: Any = None
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(3)
    segments: dict[str, int] = {}
    invalid: set[str] = set()
    previous_active: set[str] = set()
    teleporting: set[str] = set()
    pending_departed: set[str] = set()
    pending_arrived: set[str] = set()
    pending_teleported: set[str] = set()
    departed, completed, teleports = 0, 0, 0
    moving_speed_sum, moving_speed_samples = 0.0, 0
    invalid_samples, projection_checks = 0, 0
    maximum_projection_error_m = 0.0
    simulated = 0.0
    last_recorded = 0.0
    sumo_started = time.monotonic()

    def sample_frame(active: dict[str, float]) -> None:
        nonlocal projection_checks, maximum_projection_error_m, invalid_samples, last_recorded
        vehicles: list[dict[str, Any]] = []
        for identifier, speed in sorted(active.items()):
            if identifier in teleporting:
                continue
            try:
                x, y = [
                    finite_number(value) for value in connection.vehicle.getPosition(identifier)
                ]
                lon, lat = [
                    finite_number(value) for value in prepared.network.convertXY2LonLat(x, y)
                ]
                heading = finite_number(connection.vehicle.getAngle(identifier))
                if not (54 <= lon <= 57 and 24 <= lat <= 27 and 0 <= heading <= 360):
                    raise ValueError("Vehicle sample has invalid geographic coordinates or heading")
                if projection_checks < 16 or (int(simulated) % 60 == 0 and not vehicles):
                    traci_lon, traci_lat = connection.simulation.convertGeo(x, y)
                    error = math.hypot(
                        (float(traci_lon) - lon) * 111_320 * math.cos(math.radians(lat)),
                        (float(traci_lat) - lat) * 111_320,
                    )
                    maximum_projection_error_m = max(maximum_projection_error_m, error)
                    projection_checks += 1
                    if error > 0.05:
                        raise RuntimeError(
                            "SUMO and local geographic projection differ by over0.05m"
                        )
                vehicles.append(
                    {
                        "id": identifier,
                        "longitude": round(lon, 8),
                        "latitude": round(lat, 8),
                        "heading": round(heading, 4),
                        "speed": round(speed, 4),
                        "vehicle_class": "passenger",
                        "segment_id": segments.setdefault(identifier, 0),
                    }
                )
                invalid.discard(identifier)
            except (ValueError, traci.exceptions.TraCIException):
                invalid_samples += 1
                if identifier not in invalid:
                    segments[identifier] = segments.get(identifier, 0) + 1
                    invalid.add(identifier)
        writer.frame(
            simulated,
            vehicles,
            sorted(pending_departed),
            sorted(pending_arrived),
            sorted(pending_teleported),
            departed,
            completed,
            active_count=len(current_ids),
        )
        pending_departed.clear()
        pending_arrived.clear()
        pending_teleported.clear()
        last_recorded = simulated

    try:
        with (workspace / "sumo.log").open("wb") as log:
            command = [
                "sumo",
                "--net-file",
                "inputs/network.net.xml",
                "--route-files",
                "demand.rou.xml",
                "--seed",
                str(config.demand.seed),
                "--begin",
                "0",
                "--end",
                str(config.demand.duration_seconds),
                "--step-length",
                "1",
                "--route-steps",
                "0",
                "--threads",
                "1",
                "--remote-port",
                str(port),
                "--time-to-teleport",
                "-1",
                "--ignore-route-errors",
                "false",
                "--tripinfo-output",
                "tripinfo.xml",
                "--tripinfo-output.write-unfinished",
                "true",
                "--summary-output",
                "summary.xml",
                "--no-step-log",
                "true",
                "--duration-log.disable",
                "true",
                "--xml-validation",
                "never",
                "--aggregate-warnings",
                "5",
            ]
            process = subprocess.Popen(
                command,
                cwd=workspace,
                env=native_environment(),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            with contextlib.redirect_stdout(io.StringIO()):
                connection = traci.connect(
                    port, host="127.0.0.1", proc=process, numRetries=30, waitBetweenRetries=0.1
                )
            protocol, server_version = connection.getVersion()
            if EXPECTED_SUMO_VERSION not in server_version:
                raise RuntimeError("TraCI native server differs from the verified engine version")
            active: dict[str, float] = {}
            while simulated < config.demand.duration_seconds:
                connection.simulationStep()
                simulated = finite_number(connection.simulation.getTime())
                current_departed = list(connection.simulation.getDepartedIDList())
                current_arrived = list(connection.simulation.getArrivedIDList())
                starting = list(connection.simulation.getStartingTeleportIDList())
                ending = list(connection.simulation.getEndingTeleportIDList())
                departed += len(current_departed)
                completed += len(current_arrived)
                teleports += len(starting)
                pending_departed.update(current_departed)
                pending_arrived.update(current_arrived)
                pending_teleported.update([*starting, *ending])
                for kind, identifiers in [
                    ("departed", current_departed),
                    ("arrived", current_arrived),
                    ("teleport_start", starting),
                    ("teleport_end", ending),
                ]:
                    for identifier in identifiers:
                        writer.event(str(identifier), simulated, kind)
                for identifier in starting:
                    teleporting.add(identifier)
                    segments[identifier] = segments.get(identifier, 0) + 1
                for identifier in ending:
                    teleporting.discard(identifier)
                    segments[identifier] = segments.get(identifier, 0) + 1
                current_ids = set(connection.vehicle.getIDList())
                active = {}
                for identifier in sorted(current_ids):
                    if identifier not in previous_active and identifier not in current_departed:
                        segments[identifier] = segments.get(identifier, 0) + 1
                    try:
                        speed = finite_number(connection.vehicle.getSpeed(identifier))
                        if not 0 <= speed <= 100:
                            raise ValueError("Invalid native speed sample")
                    except (ValueError, traci.exceptions.TraCIException):
                        invalid_samples += 1
                        if identifier not in invalid:
                            segments[identifier] = segments.get(identifier, 0) + 1
                            invalid.add(identifier)
                        continue
                    active[identifier] = speed
                    if speed > 0.1:
                        moving_speed_sum += speed
                        moving_speed_samples += 1
                previous_active = current_ids
                if int(simulated) % config.demand.sample_interval_seconds == 0:
                    sample_frame(active)
                # Child progress is an actual measured SUMO state, atomically replaced.
                if int(simulated) % 2 == 0 or simulated == 1:
                    atomic_json(
                        workspace / "progress.json",
                        {
                            "engine_version": EXPECTED_SUMO_VERSION,
                            "progress": {
                                "simulated_seconds": simulated,
                                "duration_seconds": config.demand.duration_seconds,
                                "departed": departed,
                                "completed": completed,
                                "active": len(current_ids),
                            },
                        },
                    )
                if int(simulated) % 10 == 0:
                    output_bytes(workspace)
                if connection.simulation.getMinExpectedNumber() == 0:
                    break
            if last_recorded != simulated:
                sample_frame(active)
            atomic_json(
                workspace / "progress.json",
                {
                    "engine_version": EXPECTED_SUMO_VERSION,
                    "progress": {
                        "simulated_seconds": simulated,
                        "duration_seconds": config.demand.duration_seconds,
                        "departed": departed,
                        "completed": completed,
                        "active": len(current_ids),
                    },
                },
            )
            connection.close(False)
            connection = None
            if process.wait(timeout=10) != 0:
                raise RuntimeError("SUMO exited unsuccessfully; bounded engine log retained")
    finally:
        if connection is not None:
            with contextlib.suppress(Exception):
                connection.close(False)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        socket.setdefaulttimeout(previous_timeout)
    sumo_wall_seconds = time.monotonic() - sumo_started
    manifest = writer.finish(
        str(config.network_version_id), simulated, config.demand.sample_interval_seconds
    )
    ReplayManifest.model_validate(manifest)
    for chunk in writer.chunks:
        TrajectoryChunk.model_validate_json(
            (workspace / "replay" / f"{chunk['id']}.json").read_bytes()
        )
    metrics = calculate_metrics(
        workspace / "tripinfo.xml",
        demand["generated_trips"],
        departed,
        completed,
        teleports,
        simulated,
        time.monotonic() - started,
        sumo_wall_seconds,
        moving_speed_sum,
        moving_speed_samples,
    )
    metrics.extend(
        MetricValue(
            metric_name=name,
            value=value,
            unit=unit,
            aggregation="observed",
            calculation_version="m04-native-resource-v1",
        ).model_dump(mode="json")
        for name, value, unit in [
            ("worker_child_peak_rss", _peak_rss_bytes(resource.RUSAGE_SELF), "bytes"),
            ("native_children_peak_rss", _peak_rss_bytes(resource.RUSAGE_CHILDREN), "bytes"),
            ("invalid_trajectory_samples", invalid_samples, "samples"),
            ("projection_crosschecks", projection_checks, "samples"),
            ("maximum_projection_error", maximum_projection_error_m, "m"),
            ("maximum_active_vehicles", max(row["active"] for row in writer.counts), "vehicles"),
        ]
    )
    atomic_json(workspace / "metrics.json", {"metrics": metrics, "counts": writer.counts})
    atomic_json(
        workspace / "execution.json",
        {
            "engine_version": EXPECTED_SUMO_VERSION,
            "binary_versions": versions,
            "sumo_command": command,
            "sumo_command_cwd": "run artifact directory",
            "warning_policy": "Native SUMO aggregates repeated warnings after five per type",
            "traci_protocol": protocol,
            "traci_server_version": server_version,
            "architecture": platform.machine(),
            "input_sha256": claim.input_sha256,
            "network_sha256": config.network_sha256,
            "source_sha256": config.source_sha256,
            "mapping_sha256": config.mapping_sha256,
            "synthetic": True,
            "live_traffic": False,
            "limits": {"max_output_bytes": MAX_OUTPUT_BYTES, "step_length_seconds": 1},
            "projection": (
                "SUMO network projection, local pyproj checked against live TraCI convertGeo"
            ),
            "mean_moving_speed": "Mean SUMO getSpeed over active vehicle-seconds above0.1m/s",
            "resource_measurement": (
                "Python runner peak RSS separately from maximum spawned native-child RSS "
                "(preflight binaries and SUMO); these are not summed as concurrent peak memory"
            ),
        },
    )
    categories = {
        "replay-manifest.json": "replay_manifest",
        "demand.rou.xml": "demand",
        "demand-manifest.json": "demand_manifest",
        "tripinfo.xml": "tripinfo",
        "summary.xml": "summary",
        "metrics.json": "metrics",
        "execution.json": "execution",
        "network-audit.json": "network_audit",
        "sumo.log": "engine_log",
        "input.json": "input_config",
    }
    records = [
        artifact(workspace / name, workspace, str(claim.run_id), category)
        for name, category in categories.items()
    ]
    records.extend(
        artifact(
            workspace / "replay" / f"{chunk['id']}.json",
            workspace,
            str(claim.run_id),
            f"replay_chunk:{chunk['id']}",
        )
        for chunk in writer.chunks
    )
    # Snapshot input bytes are private immutable execution inputs, not arbitrary API artifacts.
    output_bytes(workspace)
    return PublishedResult.model_validate(
        {
            "engine_version": EXPECTED_SUMO_VERSION,
            "input_sha256": claim.input_sha256,
            "manifest_path": f"{claim.run_id}/replay-manifest.json",
            "metrics": metrics,
            "artifacts": records,
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    arguments = parser.parse_args()
    settings = Settings()
    workspace = arguments.workspace.resolve(strict=True)
    configured_root = Path(settings.simulation_artifacts_root).resolve(strict=True)
    if arguments.workspace.is_symlink() or workspace.parent != configured_root:
        raise ValueError("Run workspace must be directly inside the restricted artifact root")
    path = workspace / "input.json"
    if path.is_symlink() or not 1 <= path.stat().st_size <= 65536:
        raise ValueError("Worker input is linked, missing or exceeds its byte budget")
    claim = WorkerClaim.model_validate_json(path.read_bytes())

    def interrupted(_signal: int, _frame: object) -> None:
        raise SimulationInterrupted("Worker requested termination")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (settings.simulation_timeout_seconds, settings.simulation_timeout_seconds + 5),
    )
    try:
        result = execute(claim, workspace, Path(settings.simulation_inputs_root))
        atomic_json(workspace / "published-result.json", result.model_dump(mode="json"))
        return 0
    except SimulationInterrupted:
        atomic_json(
            workspace / "failure.json",
            {"code": "cancelled", "message": "SUMO execution was interrupted"},
        )
        return 2
    except Exception as error:
        if isinstance(error, FileNotFoundError):
            code = "input_invalid"
        elif isinstance(error, (SimulationResourceLimit, MemoryError, OSError)):
            code = "resource_limit"
        elif isinstance(error, ValueError):
            code = "output_invalid" if (workspace / "progress.json").exists() else "input_invalid"
        else:
            code = "execution_failed"
        # Native command output is in an explicitly bounded artifact, never interpolated here.
        atomic_json(
            workspace / "failure.json",
            {
                "code": code,
                "message": (
                    "SUMO execution did not produce verified outputs; "
                    "inspect its bounded engine log"
                ),
            },
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
