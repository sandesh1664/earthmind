"""Bounded, reproducible synthetic demand on a checksum-verified imported OSM network.

Run only in the native worker environment. This is a connectivity/runtime smoke
experiment, never calibrated demand, operational traffic or a prediction.
"""

import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
import math
import os
import platform
import signal
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from earthmind_worker.runtime_check import EXPECTED_SUMO_VERSION, binary_version

VEHICLES = 3
MAX_STEPS = 600
MAX_WALL_SECONDS = 120
MAX_NETWORK_BYTES = 64 * 1024 * 1024
MAX_POSITION_RECORDS = VEHICLES * MAX_STEPS


def finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Expected a finite numeric value")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Expected a finite numeric value")
    return number


def verify_import_manifest(network: Path, path: Path) -> dict[str, Any]:
    if network.stat().st_size > MAX_NETWORK_BYTES or path.stat().st_size > 65536:
        raise ValueError("Network or provenance manifest exceeds the bounded input budget")
    manifest: Any = json.loads(path.read_text())
    if not isinstance(manifest, dict) or manifest.get("kind") != "osm_import":
        raise ValueError("A real OSM import manifest is required")
    checksum = hashlib.sha256(network.read_bytes()).hexdigest()
    if manifest.get("sumo_network_sha256") != checksum:
        raise ValueError("SUMO network checksum differs from the import manifest")
    source_checksum = manifest.get("osm_sha256")
    if (
        not isinstance(source_checksum, str)
        or len(source_checksum) != 64
        or any(letter not in "0123456789abcdef" for letter in source_checksum)
    ):
        raise ValueError("Original OSM extract checksum is missing or invalid")
    network_id = str(UUID(str(manifest.get("network_id"))))
    bbox = manifest.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("The OSM study extent is missing")
    west, south, east, north = [finite_number(value) for value in bbox]
    if not (54 <= west < east <= 57 and 24 <= south < north <= 27):
        raise ValueError("Expected a bounded Dubai-area geographic extent")
    if east - west > 0.1 or north - south > 0.1:
        raise ValueError("The smoke experiment supports only a small study area")
    mapping_name = manifest.get("mapping_file")
    if (
        not isinstance(mapping_name, str)
        or Path(mapping_name).name != mapping_name
        or mapping_name != "source-sumo-db-mapping.json"
    ):
        raise ValueError("Expected the retained source-to-SUMO/database mapping file")
    mapping_path = path.parent / mapping_name
    if mapping_path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Imported edge mapping exceeds its bounded input budget")
    mapping_bytes = mapping_path.read_bytes()
    mapping_checksum = hashlib.sha256(mapping_bytes).hexdigest()
    if manifest.get("mapping_sha256") != mapping_checksum:
        raise ValueError("Imported edge mapping checksum differs from the manifest")
    mapping = json.loads(mapping_bytes)
    if not isinstance(mapping, dict) or mapping.get("network_id") != network_id:
        raise ValueError("Imported edge mapping belongs to another network version")
    source_edges = mapping.get("osm_way_to_sumo_and_database_edges")
    if not isinstance(source_edges, dict) or len(source_edges) > 10000:
        raise ValueError("Invalid or oversized source-to-imported-edge mapping")
    allowed_ids: set[str] = set()
    mapping_records = 0
    for source_id, entries in source_edges.items():
        if (
            not isinstance(source_id, str)
            or not source_id.isdigit()
            or not isinstance(entries, list)
        ):
            raise ValueError("Invalid OSM way mapping")
        for entry in entries:
            mapping_records += 1
            if mapping_records > 20_000 or not isinstance(entry, dict):
                raise ValueError("Invalid or oversized imported edge mapping")
            identifier = entry.get("sumo_edge_id")
            if not isinstance(identifier, str) or not 1 <= len(identifier) <= 128:
                raise ValueError("Invalid mapped SUMO edge identifier")
            expected_database_id = str(uuid5(UUID(network_id), f"edge:{identifier}"))
            if entry.get("database_edge_id") != expected_database_id:
                raise ValueError("Mapped database edge identity does not match the network version")
            allowed_ids.add(identifier)
    if not allowed_ids or len(allowed_ids) > 10000:
        raise ValueError("No bounded imported database road subset is available")
    if manifest.get("edge_count") != len(allowed_ids):
        raise ValueError("Imported edge mapping count differs from the published network manifest")
    return {
        "allowed_sumo_edge_ids": sorted(allowed_ids),
        "mapping_sha256": mapping_checksum,
        "mapped_database_edge_count": len(allowed_ids),
        "network_id": network_id,
        "osm_sha256": source_checksum,
        "sumo_network_sha256": checksum,
        "bbox": [west, south, east, north],
    }


def select_connected_route(network: Any, allowed_edge_ids: set[str] | None = None) -> list[str]:
    """Select a short deterministic route through actual passenger connections.

    No invented edge IDs, coordinate-based intersection inference or randomTrips
    generator is involved. Lane permissions and netconvert's actual connection
    records constrain every turn. This checks only this bounded smoke route.
    """
    edges = sorted(network.getEdges(), key=lambda edge: str(edge.getID()))
    eligible = {
        str(edge.getID()): edge
        for edge in edges
        if edge.allows("passenger")
        and 15 <= finite_number(edge.getLength()) <= 700
        and (allowed_edge_ids is None or str(edge.getID()) in allowed_edge_ids)
    }

    visited_paths = 0

    def visit(path: list[Any], used_nodes: set[str], length: float) -> list[str] | None:
        nonlocal visited_paths
        visited_paths += 1
        if visited_paths > 20_000:
            return None
        if len(path) >= 3 and length >= 250:
            return [str(edge.getID()) for edge in path]
        if len(path) >= 8 or length > 1800:
            return None
        outgoing = path[-1].getOutgoing()
        for successor in sorted(outgoing, key=lambda edge: str(edge.getID())):
            if str(successor.getID()) not in eligible:
                continue
            node = str(successor.getToNode().getID())
            if node in used_nodes:
                continue
            connections = outgoing[successor]
            if not any(
                connection.getFromLane().allows("passenger")
                and connection.getToLane().allows("passenger")
                for connection in connections
            ):
                continue
            result = visit(
                [*path, successor], used_nodes | {node}, length + float(successor.getLength())
            )
            if result is not None:
                return result
        return None

    # Bound search even if a malformed/disconnected extract contains many edges.
    for edge in list(eligible.values())[:1000]:
        result = visit(
            [edge],
            {str(edge.getFromNode().getID()), str(edge.getToNode().getID())},
            float(edge.getLength()),
        )
        if result is not None:
            return result
    raise RuntimeError("No short connected passenger route exists within the bounded search")


def write_demand(path: Path, route: list[str]) -> None:
    if len(route) < 3:
        raise ValueError("A smoke route needs at least three connected actual edges")
    root = ET.Element("routes")
    ET.SubElement(
        root,
        "vType",
        {
            "id": "synthetic_smoke_passenger",
            "vClass": "passenger",
            "accel": "2.0",
            "decel": "4.0",
            "sigma": "0",
            "length": "5.0",
            "minGap": "2.5",
            "maxSpeed": "13.89",
        },
    )
    ET.SubElement(root, "route", {"id": "synthetic_smoke_route", "edges": " ".join(route)})
    for index in range(VEHICLES):
        ET.SubElement(
            root,
            "vehicle",
            {
                "id": f"synthetic_smoke_{index}",
                "type": "synthetic_smoke_passenger",
                "route": "synthetic_smoke_route",
                "depart": str(index * 5),
                "departLane": "best",
                "departSpeed": "0",
            },
        )
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def read_outputs(directory: Path) -> dict[str, Any]:
    trips = []
    for trip in ET.parse(directory / "tripinfo.xml").getroot().findall("tripinfo"):
        arrival = finite_number(trip.attrib["arrival"])
        if arrival < 0:
            continue
        trips.append(
            {
                "id": trip.attrib["id"],
                **{
                    key: finite_number(trip.attrib[key])
                    for key in ("depart", "arrival", "duration", "routeLength", "waitingTime")
                },
            }
        )
    if len(trips) != VEHICLES or any(finite_number(trip["routeLength"]) <= 1 for trip in trips):
        raise RuntimeError("All three synthetic smoke vehicles must actually complete real routes")
    positions: list[dict[str, Any]] = []
    for step in ET.parse(directory / "fcd.geo.xml").getroot().findall("timestep"):
        time = finite_number(step.attrib["time"])
        for vehicle in step.findall("vehicle"):
            lon = finite_number(vehicle.attrib["x"])
            lat = finite_number(vehicle.attrib["y"])
            if not (54 <= lon <= 57 and 24 <= lat <= 27):
                raise RuntimeError("Recorded FCD coordinates are not geographic Dubai coordinates")
            positions.append(
                {
                    "time_s": time,
                    "vehicle_id": vehicle.attrib["id"],
                    "longitude": lon,
                    "latitude": lat,
                    "speed_m_s": finite_number(vehicle.attrib["speed"]),
                    "heading_deg": finite_number(vehicle.attrib["angle"]),
                    "lane_id": vehicle.attrib.get("lane"),
                }
            )
            if len(positions) > MAX_POSITION_RECORDS:
                raise RuntimeError("Recorded trajectory exceeds the smoke output budget")
    if not positions or not any(float(position["speed_m_s"]) > 0.5 for position in positions):
        raise RuntimeError("Actual recorded FCD output contains no moving vehicles")
    (directory / "recorded-positions.json").write_text(
        json.dumps(
            {
                "coordinate_reference_system": "EPSG:4326",
                "traffic_kind": "synthetic_demand_on_imported_osm_geometry",
                "is_live_traffic": False,
                "source": "actual SUMO fcd.geo.xml output",
                "positions": positions,
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    return {
        "trips": trips,
        "completed_trip_count": len(trips),
        "mean_trip_duration_s": sum((finite_number(trip["duration"]) for trip in trips), 0.0)
        / len(trips),
        "total_trip_distance_m": sum((finite_number(trip["routeLength"]) for trip in trips), 0.0),
        "recorded_position_count": len(positions),
        "recorded_longitude_range": [
            min(float(p["longitude"]) for p in positions),
            max(float(p["longitude"]) for p in positions),
        ],
        "recorded_latitude_range": [
            min(float(p["latitude"]) for p in positions),
            max(float(p["latitude"]) for p in positions),
        ],
    }


def verify(network_path: Path, manifest_path: Path, directory: Path) -> dict[str, Any]:
    import sumolib  # type: ignore[import-untyped]
    import traci  # type: ignore[import-untyped]

    provenance = verify_import_manifest(network_path, manifest_path)
    # Refuse to overwrite any prior experimental output, including a failed run.
    directory.mkdir(parents=True, exist_ok=False)
    for package in ("traci", "sumolib"):
        if importlib.metadata.version(package) != EXPECTED_SUMO_VERSION:
            raise RuntimeError(f"{package} must match SUMO {EXPECTED_SUMO_VERSION}")
    versions = {binary: binary_version(binary) for binary in ("sumo", "netconvert")}
    network = sumolib.net.readNet(str(network_path))
    allowed_ids = set(provenance.pop("allowed_sumo_edge_ids"))
    route = select_connected_route(network, allowed_ids)
    demand_path = directory / "synthetic-smoke.rou.xml"
    write_demand(demand_path, route)
    port = sumolib.miscutils.getFreeSocketPort()
    previous_socket_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(2)
    connection = None
    departed = arrived = teleports = collisions = steps = 0
    maximum_roundtrip_error_m = 0.0
    moved_vehicle_ids: set[str] = set()
    coordinate_checks = 0
    with (directory / "sumo.log").open("w") as log:
        process = subprocess.Popen(
            [
                "sumo",
                "--net-file",
                str(network_path),
                "--route-files",
                str(demand_path),
                "--remote-port",
                str(port),
                "--seed",
                "42",
                "--step-length",
                "1",
                "--end",
                str(MAX_STEPS),
                "--time-to-teleport",
                "-1",
                "--ignore-route-errors",
                "false",
                "--tripinfo-output",
                str(directory / "tripinfo.xml"),
                "--fcd-output",
                str(directory / "fcd.geo.xml"),
                "--fcd-output.geo",
                "true",
                "--precision.geo",
                "8",
                "--summary-output",
                str(directory / "summary.xml"),
                "--no-step-log",
                "true",
                "--duration-log.disable",
                "true",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                connection = traci.connect(
                    port, numRetries=10, host="127.0.0.1", proc=process, waitBetweenRetries=0.1
                )
            protocol, server_version = connection.getVersion()
            if EXPECTED_SUMO_VERSION not in server_version:
                raise RuntimeError("TraCI server version differs from the pinned engine")
            while connection.simulation.getMinExpectedNumber() > 0 and steps < MAX_STEPS:
                connection.simulationStep()
                departed += int(connection.simulation.getDepartedNumber())
                arrived += int(connection.simulation.getArrivedNumber())
                teleports += int(connection.simulation.getStartingTeleportNumber())
                collisions += int(connection.simulation.getCollidingVehiclesNumber())
                steps += 1
                for vehicle_id in connection.vehicle.getIDList():
                    if float(connection.vehicle.getDistance(vehicle_id)) > 1:
                        moved_vehicle_ids.add(str(vehicle_id))
                    if steps % 10 != 1:
                        continue
                    x, y = [
                        finite_number(value) for value in connection.vehicle.getPosition(vehicle_id)
                    ]
                    lon, lat = [
                        finite_number(value) for value in connection.simulation.convertGeo(x, y)
                    ]
                    if not (54 <= lon <= 57 and 24 <= lat <= 27):
                        raise RuntimeError("SUMO projection does not produce Dubai lon/lat")
                    roundtrip_x, roundtrip_y = [
                        finite_number(value)
                        for value in connection.simulation.convertGeo(lon, lat, True)
                    ]
                    error = math.hypot(roundtrip_x - x, roundtrip_y - y)
                    maximum_roundtrip_error_m = max(maximum_roundtrip_error_m, error)
                    coordinate_checks += 1
            if connection.simulation.getMinExpectedNumber() != 0:
                raise RuntimeError("Synthetic smoke exceeded its 600-step simulation budget")
            connection.close(False)
            connection = None
            if process.wait(timeout=5) != 0:
                raise RuntimeError("SUMO process failed; inspect sumo.log")
        finally:
            if connection is not None:
                with contextlib.suppress(Exception):
                    connection.close(False)
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
            socket.setdefaulttimeout(previous_socket_timeout)
    if departed != VEHICLES or arrived != VEHICLES or len(moved_vehicle_ids) != VEHICLES:
        raise RuntimeError("All three vehicles must depart, move and complete")
    if teleports or collisions:
        raise RuntimeError("Teleportation/collision invalidates this smoke experiment")
    if coordinate_checks == 0 or maximum_roundtrip_error_m > 0.05:
        raise RuntimeError("Actual SUMO geographic round-trip failed the 0.05 m tolerance")
    outputs = read_outputs(directory)
    result = {
        "status": "PASS",
        "kind": "imported_osm_synthetic_demand_smoke",
        "verified_at": datetime.now(UTC).isoformat(),
        "architecture": platform.machine(),
        "worker_pid": os.getpid(),
        "version": EXPECTED_SUMO_VERSION,
        "binary_versions": versions,
        "traci_protocol": protocol,
        "traci_server_version": server_version,
        "provenance": provenance,
        "demand": {
            "is_synthetic": True,
            "is_live_traffic": False,
            "seed": 42,
            "vehicle_count": VEHICLES,
            "departure_interval_s": 5,
            "interpretation": "Connectivity/runtime smoke only; no observed or calibrated demand",
            "route_edge_ids": route,
            "route_database_edge_ids": [
                str(uuid5(UUID(provenance["network_id"]), f"edge:{identifier}"))
                for identifier in route
            ],
            "route_scope": (
                "Every route edge belongs to the checksum-verified imported PostGIS subset"
            ),
        },
        "vehicles_departed": departed,
        "vehicles_arrived": arrived,
        "vehicles_observed_moving": len(moved_vehicle_ids),
        "teleports": teleports,
        "colliding_vehicles": collisions,
        "simulation_steps": steps,
        "coordinate_roundtrip_checks": coordinate_checks,
        "maximum_coordinate_roundtrip_error_m": maximum_roundtrip_error_m,
        "outputs": outputs,
        "output_files": [
            "synthetic-smoke.rou.xml",
            "sumo.log",
            "tripinfo.xml",
            "fcd.geo.xml",
            "summary.xml",
            "recorded-positions.json",
        ],
        "limitations": [
            "OSM tags and inferred SUMO defaults are not field-verified lane/signal data",
            "Only one bounded route is exercised, not all imported roads or turn restrictions",
            "Recorded FCD is synthetic simulation output, never live Dubai traffic",
            "No browser vehicle replay layer is implemented by this smoke command",
        ],
    }
    (directory / "smoke-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", type=Path, required=True)
    parser.add_argument("--import-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()

    def deadline(_number: int, _frame: object) -> None:
        raise TimeoutError("Real-network smoke exceeded 120 seconds wall time")

    previous_handler = signal.signal(signal.SIGALRM, deadline)
    signal.alarm(MAX_WALL_SECONDS)
    try:
        result = verify(
            arguments.network.resolve(),
            arguments.import_manifest.resolve(),
            arguments.output_dir.resolve(),
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(f"Real-network SUMO smoke failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    sys.exit(main())
