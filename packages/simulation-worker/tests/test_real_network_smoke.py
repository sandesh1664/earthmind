"""Isolated smoke harness tests; actual OSM/SUMO proof is a separate native run."""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

import pytest
from earthmind_worker.real_network_smoke import (
    finite_number,
    read_outputs,
    select_connected_route,
    verify_import_manifest,
    write_demand,
)


def manifest_for(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    network = tmp_path / "network.net.xml"
    network.write_text("unit test input, not an actual converted OSM network")
    manifest = {
        "kind": "osm_import",
        "osm_sha256": "a" * 64,
        "sumo_network_sha256": hashlib.sha256(network.read_bytes()).hexdigest(),
        "network_id": str(uuid4()),
        "bbox": [55.258, 25.180, 55.288, 25.208],
    }
    mapping = {
        "network_id": manifest["network_id"],
        "osm_way_to_sumo_and_database_edges": {
            "42": [
                {
                    "sumo_edge_id": "42#0",
                    "database_edge_id": str(uuid5(UUID(manifest["network_id"]), "edge:42#0")),
                }
            ],
        },
    }
    mapping_path = tmp_path / "source-sumo-db-mapping.json"
    mapping_path.write_text(json.dumps(mapping))
    manifest["mapping_file"] = mapping_path.name
    manifest["mapping_sha256"] = hashlib.sha256(mapping_path.read_bytes()).hexdigest()
    manifest["edge_count"] = 1
    path = tmp_path / "import-manifest.json"
    path.write_text(json.dumps(manifest))
    return network, path, manifest


def test_input_provenance_requires_matching_actual_network_bytes(tmp_path: Path) -> None:
    network, manifest_path, manifest = manifest_for(tmp_path)
    result = verify_import_manifest(network, manifest_path)
    assert result["network_id"] == manifest["network_id"]
    network.write_text("changed after conversion")
    with pytest.raises(ValueError, match="checksum differs"):
        verify_import_manifest(network, manifest_path)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("kind", "synthetic"),
        ("osm_sha256", "missing"),
        ("bbox", [55.2, 25.1, 56, 26]),
        ("bbox", [False, 25.18, 55.288, 25.208]),
        ("network_id", "unknown"),
    ],
)
def test_invalid_source_extent_or_identity_is_rejected(
    tmp_path: Path, field: str, invalid: object
) -> None:
    network, path, manifest = manifest_for(tmp_path)
    manifest[field] = invalid
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        verify_import_manifest(network, path)


def test_synthetic_demand_is_explicit_reproducible_and_uses_given_edge_ids(tmp_path: Path) -> None:
    path = tmp_path / "demand.rou.xml"
    write_demand(path, ["osm:42#0", "osm:42#1", "-osm:75"])
    tree = ET.parse(path)
    assert tree.find("route").attrib["edges"] == "osm:42#0 osm:42#1 -osm:75"  # type: ignore[union-attr]
    vehicles = tree.findall("vehicle")
    assert len(vehicles) == 3
    assert [vehicle.attrib["depart"] for vehicle in vehicles] == ["0", "5", "10"]
    assert all(vehicle.attrib["id"].startswith("synthetic_") for vehicle in vehicles)
    before = path.read_bytes()
    write_demand(path, ["osm:42#0", "osm:42#1", "-osm:75"])
    assert path.read_bytes() == before


class Lane:
    def __init__(self, passenger: bool = True) -> None:
        self.passenger = passenger

    def allows(self, vehicle_class: str) -> bool:
        return self.passenger and vehicle_class == "passenger"


class Node:
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier

    def getID(self) -> str:
        return self.identifier


class Connection:
    def __init__(self, permitted: bool) -> None:
        self.lane = Lane(permitted)

    def getFromLane(self) -> Lane:
        return self.lane

    def getToLane(self) -> Lane:
        return self.lane


class Edge:
    def __init__(self, identifier: str, start: str, end: str) -> None:
        self.identifier = identifier
        self.start, self.end = Node(start), Node(end)
        self.outgoing: dict[Edge, list[Connection]] = {}

    def getID(self) -> str:
        return self.identifier

    def allows(self, vehicle_class: str) -> bool:
        return vehicle_class == "passenger"

    def getLength(self) -> float:
        return 100

    def getFromNode(self) -> Node:
        return self.start

    def getToNode(self) -> Node:
        return self.end

    def getOutgoing(self) -> dict["Edge", list[Connection]]:
        return self.outgoing


class Network:
    def __init__(self, edges: list[Edge]) -> None:
        self.edges = edges

    def getEdges(self) -> list[Edge]:
        return self.edges


def test_route_uses_explicit_connected_passenger_turns_and_rejects_cycles() -> None:
    first, second, third = Edge("a", "n0", "n1"), Edge("b", "n1", "n2"), Edge("c", "n2", "n3")
    first.outgoing[second] = [Connection(True)]
    second.outgoing[third] = [Connection(True)]
    third.outgoing[first] = [Connection(True)]
    assert select_connected_route(Network([third, first, second])) == ["a", "b", "c"]
    first.outgoing[second] = [Connection(False)]
    third.outgoing.clear()
    with pytest.raises(RuntimeError, match="No short connected"):
        select_connected_route(Network([first, second, third]))


def write_measured_output_fixture(tmp_path: Path, longitude: str = "55.2744") -> None:
    trips = "".join(
        f"<tripinfo id='synthetic_smoke_{i}' depart='{i * 5}' arrival='{40 + i * 5}' "
        "duration='40' routeLength='300' waitingTime='0'/>"
        for i in range(3)
    )
    (tmp_path / "tripinfo.xml").write_text(f"<tripinfos>{trips}</tripinfos>")
    (tmp_path / "fcd.geo.xml").write_text(
        f"<fcd-export><timestep time='10'><vehicle id='synthetic_smoke_0' x='{longitude}' "
        "y='25.1972' speed='8.5' angle='45' lane='42#0_0'/></timestep></fcd-export>"
    )


def test_metrics_and_recorded_positions_preserve_actual_output_values(tmp_path: Path) -> None:
    write_measured_output_fixture(tmp_path)
    result = read_outputs(tmp_path)
    assert result["completed_trip_count"] == 3
    assert result["mean_trip_duration_s"] == 40
    assert result["total_trip_distance_m"] == 900
    recorded = json.loads((tmp_path / "recorded-positions.json").read_text())
    assert recorded["is_live_traffic"] is False
    assert recorded["positions"][0]["longitude"] == 55.2744
    assert recorded["positions"][0]["speed_m_s"] == 8.5


@pytest.mark.parametrize("invalid", ["500000", "nan", "inf"])
def test_projected_or_nonfinite_fcd_coordinates_are_not_claimed_as_geo(
    tmp_path: Path, invalid: str
) -> None:
    write_measured_output_fixture(tmp_path, invalid)
    with pytest.raises((ValueError, RuntimeError)):
        read_outputs(tmp_path)


@pytest.mark.parametrize("invalid", [True, float("nan"), float("inf"), None])
def test_numeric_validation_rejects_nonfinite_or_boolean_values(invalid: object) -> None:
    with pytest.raises(ValueError):
        finite_number(invalid)


def test_smoke_route_cannot_use_converted_edges_outside_imported_database_subset() -> None:
    first, second, third = Edge("a", "n0", "n1"), Edge("b", "n1", "n2"), Edge("c", "n2", "n3")
    first.outgoing[second] = [Connection(True)]
    second.outgoing[third] = [Connection(True)]
    network = Network([first, second, third])
    assert select_connected_route(network, {"a", "b", "c"}) == ["a", "b", "c"]
    with pytest.raises(RuntimeError, match="No short connected"):
        select_connected_route(network, {"a", "c"})


def test_changed_import_mapping_is_rejected_before_any_simulation(tmp_path: Path) -> None:
    network, path, _ = manifest_for(tmp_path)
    mapping = tmp_path / "source-sumo-db-mapping.json"
    mapping.write_text(mapping.read_text() + " ")
    with pytest.raises(ValueError, match="mapping checksum differs"):
        verify_import_manifest(network, path)
