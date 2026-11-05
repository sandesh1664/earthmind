"""Validated retained SUMO network: actual permitted connections, never inferred XY links."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from earthmind_worker.real_network_smoke import finite_number, verify_import_manifest

MAX_NETWORK_BYTES = 64 * 1024 * 1024
MAX_EDGES = 10_000
MAX_LANES = 50_000


def reject_xml_declarations(path: Path, maximum: int = MAX_NETWORK_BYTES) -> None:
    """Bound bytes and reject DTD/entity declarations before any XML parser sees input."""
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= maximum:
        raise ValueError("XML input is missing, linked or outside its file-size budget")
    carry = b""
    with path.open("rb") as source:
        while data := source.read(65536):
            scan = (carry + data).upper()
            if b"<!DOCTYPE" in scan or b"<!ENTITY" in scan:
                raise ValueError("XML DTD/entity declarations are prohibited")
            carry = scan[-16:]


@dataclass(frozen=True)
class PreparedNetwork:
    network: Any
    edges: dict[str, Any]
    successors: dict[str, tuple[str, ...]]
    lengths: dict[str, float]
    provenance: dict[str, Any]
    audit: dict[str, JsonValue]

    def route(self, origin: str, destination: str) -> list[str] | None:
        if origin not in self.edges or destination not in self.edges or origin == destination:
            return None
        parents = self.reachable(origin)
        if destination not in parents:
            return None
        result = [destination]
        while result[-1] != origin:
            parent = parents[result[-1]]
            if parent is None:
                return None
            result.append(parent)
        result.reverse()
        return result

    def reachable(self, origin: str) -> dict[str, str | None]:
        parents: dict[str, str | None] = {origin: None}
        pending = deque([origin])
        while pending:
            edge = pending.popleft()
            for successor in self.successors[edge]:
                if successor not in parents:
                    parents[successor] = edge
                    pending.append(successor)
        return parents

    def validate_route(self, route: list[str]) -> bool:
        return (
            2 <= len(route) <= 256
            and len(set(route)) == len(route)
            and all(identifier in self.edges for identifier in route)
            and all(
                right in self.successors[left]
                for left, right in zip(route, route[1:], strict=False)
            )
        )


def _components(successors: dict[str, tuple[str, ...]]) -> tuple[int, list[int]]:
    # Weak components are descriptive only; route validation uses directed connections.
    adjacent: dict[str, set[str]] = {edge: set(outgoing) for edge, outgoing in successors.items()}
    for origin, outgoing in successors.items():
        for target in outgoing:
            adjacent[target].add(origin)
    remaining = set(successors)
    sizes: list[int] = []
    while remaining:
        pending = [min(remaining)]
        remaining.remove(pending[0])
        size = 0
        while pending:
            edge = pending.pop()
            size += 1
            for neighbor in adjacent[edge]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    pending.append(neighbor)
        sizes.append(size)
    return len(sizes), sorted(sizes, reverse=True)


def prepare_network(directory: Path, expected_network_id: str | None = None) -> PreparedNetwork:
    import sumolib  # type: ignore[import-untyped]

    network_path = directory / "network.net.xml"
    manifest_path = directory / "import-manifest.json"
    for path in [network_path, manifest_path, directory / "source-sumo-db-mapping.json"]:
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise ValueError("Network inputs must be regular files inside the retained artifact")
    reject_xml_declarations(network_path)
    provenance = verify_import_manifest(network_path, manifest_path)
    if expected_network_id is not None and provenance["network_id"] != expected_network_id:
        raise ValueError("Retained SUMO artifact belongs to another network version")
    network = sumolib.net.readNet(str(network_path), withPrograms=True, withConnections=True)
    all_edges = list(network.getEdges())
    if not 1 <= len(all_edges) <= MAX_EDGES:
        raise ValueError("SUMO network exceeds the bounded edge count")
    imported = set(provenance["allowed_sumo_edge_ids"])
    actual = {str(edge.getID()): edge for edge in all_edges}
    if not imported.issubset(actual):
        raise ValueError("Imported mapping references SUMO edges absent from the network")
    edges = {key: actual[key] for key in sorted(imported) if actual[key].allows("passenger")}
    if len(edges) < 2:
        raise ValueError("At least two imported passenger edges are required")
    lengths: dict[str, float] = {}
    lane_count, projection_checks = 0, 0
    maximum_roundtrip_error = 0.0
    for identifier, edge in edges.items():
        length = finite_number(edge.getLength())
        if length <= 0 or length > 50_000:
            raise ValueError("SUMO lane/edge length is outside the simulation budget")
        lengths[identifier] = length
        lanes = list(edge.getLanes())
        if not lanes or len(lanes) > 20:
            raise ValueError("SUMO edge has no valid bounded lane definitions")
        lane_count += len(lanes)
        if lane_count > MAX_LANES:
            raise ValueError("SUMO network exceeds the lane budget")
        for lane in lanes:
            shape = list(lane.getShape())
            if len(shape) < 2 or len(shape) > 5000:
                raise ValueError("SUMO lane shape is empty or exceeds the geometry budget")
            if finite_number(lane.getLength()) <= 0:
                raise ValueError("SUMO lane length is invalid")
            for coordinate in [shape[0], shape[-1]]:
                x, y = [finite_number(value) for value in coordinate[:2]]
                longitude, latitude = network.convertXY2LonLat(x, y)
                lon, lat = finite_number(longitude), finite_number(latitude)
                if not (54 <= lon <= 57 and 24 <= lat <= 27):
                    raise ValueError("SUMO projection does not produce Dubai longitude/latitude")
                roundtrip_x, roundtrip_y = network.convertLonLat2XY(lon, lat)
                error = math.hypot(float(roundtrip_x) - x, float(roundtrip_y) - y)
                maximum_roundtrip_error = max(maximum_roundtrip_error, error)
                projection_checks += 1
    if maximum_roundtrip_error > 0.05:
        raise ValueError("SUMO projection round trip exceeds 0.05 metres")
    successors: dict[str, tuple[str, ...]] = {}
    incoming = dict.fromkeys(edges, 0)
    for identifier, edge in edges.items():
        targets: list[str] = []
        for target, connections in edge.getOutgoing().items():
            target_id = str(target.getID())
            if target_id not in edges:
                continue
            if any(
                connection.getFromLane().allows("passenger")
                and connection.getToLane().allows("passenger")
                for connection in connections
            ):
                targets.append(target_id)
                incoming[target_id] += 1
        successors[identifier] = tuple(sorted(targets))
    component_count, component_sizes = _components(successors)
    controllers = list(network.getTrafficLights())
    boundary_entries, boundary_exits = 0, 0
    west, south, east, north = provenance["bbox"]
    for identifier, edge in edges.items():
        shape = list(edge.getShape())
        if not shape:
            continue
        for coordinate, entry in [(shape[0], True), (shape[-1], False)]:
            lon, lat = network.convertXY2LonLat(*coordinate[:2])
            # Descriptive proximity to the chosen study extent, not an official boundary.
            near = (
                min(abs(lon - west), abs(lon - east)) < 0.001
                or min(abs(lat - south), abs(lat - north)) < 0.001
            )
            if near and entry and successors[identifier]:
                boundary_entries += 1
            if near and not entry and incoming[identifier]:
                boundary_exits += 1
    audit: dict[str, JsonValue] = {
        "engine_version": "1.15.0",
        "ordinary_converted_edges": len(all_edges),
        "mapped_database_edges": len(imported),
        "passenger_edges": len(edges),
        "lane_count": lane_count,
        "junction_count": len(network.getNodes()),
        "passenger_connections": sum(len(value) for value in successors.values()),
        "weak_components": component_count,
        "component_edge_counts": [int(value) for value in component_sizes],
        "source_edges": sum(value == 0 for value in incoming.values()),
        "sink_edges": sum(not value for value in successors.values()),
        "study_boundary_entry_candidates": boundary_entries,
        "study_boundary_exit_candidates": boundary_exits,
        "traffic_light_controllers": len(controllers),
        "traffic_light_programs": sum(len(controller.getPrograms()) for controller in controllers),
        "projection_roundtrip_checks": projection_checks,
        "maximum_projection_roundtrip_error_m": maximum_roundtrip_error,
        "driving_direction": "directional SUMO lane connections; no coordinate crossing inference",
        "route_policy": "reachable passenger destinations within mapped imported edge subset",
        "signal_timing_provenance": "OSM/netconvert defaults, not observed Dubai field operation",
    }
    if not any(successors.values()):
        raise ValueError("No permitted passenger connections exist in the imported subset")
    return PreparedNetwork(network, edges, successors, lengths, provenance, audit)
