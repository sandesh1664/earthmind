"""Meaningful algorithm/contract tests; native execution is separately verified in Docker."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from earthmind_contracts.simulation import DemandConfig, ReplayManifest, TrajectoryChunk
from earthmind_worker.simulation_artifacts import TrajectoryWriter, output_bytes
from earthmind_worker.simulation_demand import effective_trip_count, generate_demand
from earthmind_worker.simulation_metrics import calculate_metrics
from earthmind_worker.simulation_network import PreparedNetwork, reject_xml_declarations


def directed_network() -> PreparedNetwork:
    return PreparedNetwork(
        network=None,
        edges=dict.fromkeys(["a", "b", "c", "isolated"]),
        successors={"a": ("b",), "b": ("c",), "c": (), "isolated": ()},
        lengths={"a": 120, "b": 140, "c": 100, "isolated": 120},
        provenance={},
        audit={},
    )


def demand_routes(path: Path) -> dict[str, tuple[str, str]]:
    return {
        node.attrib["id"]: (
            node.attrib["depart"],
            node.find("route").attrib["edges"],  # type: ignore[union-attr]
        )
        for node in ET.parse(path).findall("vehicle")
    }


def test_demand_is_byte_reproducible_and_each_route_uses_permitted_directed_connections(
    tmp_path: Path,
) -> None:
    network = directed_network()
    demand = DemandConfig(trip_target=30, seed=71)
    path = tmp_path / "routes.xml"
    first = generate_demand(network, demand, path)
    before = path.read_bytes()
    second = generate_demand(network, demand, path)
    assert before == path.read_bytes()
    assert first == second
    assert first["generated_trips"] == 30
    assert first["synthetic"] is True and first["is_live_traffic"] is False
    for _depart, edges in demand_routes(path).values():
        assert network.validate_route(edges.split())
        assert "isolated" not in edges
    generate_demand(network, demand.model_copy(update={"seed": 72}), path)
    assert before != path.read_bytes()


@pytest.mark.parametrize("distribution", ["uniform", "burst"])
def test_modified_volume_preserves_common_random_routes_and_departures(
    tmp_path: Path, distribution: str
) -> None:
    baseline = DemandConfig(trip_target=20, departure_distribution=distribution)  # type: ignore[arg-type]
    path = tmp_path / "routes.xml"
    generate_demand(directed_network(), baseline, path)
    first = demand_routes(path)
    generate_demand(directed_network(), baseline.model_copy(update={"trip_target": 24}), path)
    second = demand_routes(path)
    assert len(second) == 24
    assert all(second[identifier] == value for identifier, value in first.items())


def test_poisson_departures_use_reproducible_positive_exponential_intervals(tmp_path: Path) -> None:
    demand = DemandConfig(trip_target=30, departure_distribution="poisson", seed=7)
    path = tmp_path / "routes.xml"
    generate_demand(directed_network(), demand, path)
    trips = demand_routes(path)
    ordered = [float(trips[f"synthetic_{i:06d}"][0]) for i in range(30)]
    assert ordered == sorted(ordered)
    assert (
        len({round(right - left, 3) for left, right in zip(ordered, ordered[1:], strict=False)}) > 5
    )


def test_invalid_effective_volume_and_disconnected_route_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        effective_trip_count(5000, 3)
    graph = directed_network()
    assert graph.route("a", "c") == ["a", "b", "c"]
    assert graph.route("c", "a") is None
    assert not graph.validate_route(["a", "isolated"])
    assert not graph.validate_route(["a", "b", "a"])
    empty = PreparedNetwork(None, {"a": None}, {"a": ()}, {"a": 10}, {}, {})
    with pytest.raises(ValueError, match="No valid origin"):
        generate_demand(empty, DemandConfig(trip_target=1), tmp_path / "routes.xml")


def vehicle(segment: int = 0) -> dict[str, Any]:
    return {
        "id": "synthetic_000000",
        "longitude": 55.2744,
        "latitude": 25.1972,
        "heading": 90,
        "speed": 12.3,
        "vehicle_class": "passenger",
        "segment_id": segment,
    }


def test_replay_chunks_overlap_and_preserve_exact_arrivals_and_discontinuity_segments(
    tmp_path: Path,
) -> None:
    run_id, network_id = str(uuid4()), str(uuid4())
    writer = TrajectoryWriter(tmp_path, run_id)
    writer.event("synthetic_000000", 1, "departed")
    for step in range(16):
        writer.frame(step * 2, [vehicle()], [], [], [], 1, 0)
    writer.event("synthetic_000000", 31, "teleport_start")
    writer.frame(32, [], [], [], ["synthetic_000000"], 1, 0)
    writer.event("synthetic_000000", 33, "teleport_end")
    writer.frame(34, [vehicle(1)], [], [], ["synthetic_000000"], 1, 0)
    writer.event("synthetic_000000", 35, "arrived")
    writer.frame(36, [], [], ["synthetic_000000"], [], 1, 1)
    manifest = ReplayManifest.model_validate(writer.finish(network_id, 36, 2))
    assert len(manifest.chunks) == 2
    chunks = [
        TrajectoryChunk.model_validate_json((tmp_path / "replay" / f"{item.id}.json").read_bytes())
        for item in manifest.chunks
    ]
    assert chunks[0].frames[-1] == chunks[1].frames[0]
    assert chunks[1].frames[-1].vehicles == []
    assert chunks[1].frames[-2].vehicles[0].segment_id == 1
    assert [(event.time, event.type) for event in chunks[1].events] == [
        (31, "teleport_start"),
        (33, "teleport_end"),
        (35, "arrived"),
    ]
    assert manifest.counts[-1].arrived == 1


def test_replay_rolls_by_wire_bytes_and_refuses_oversized_single_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import earthmind_worker.simulation_artifacts as module

    monkeypatch.setattr(module, "MAX_CHUNK_BYTES", 850)
    writer = TrajectoryWriter(tmp_path, str(uuid4()))
    for step in range(6):
        writer.frame(step * 2, [vehicle()], [], [], [], 1, 0)
    writer.finish(str(uuid4()), 10, 2)
    assert len(writer.chunks) >= 3
    assert all(item["size_bytes"] <= 850 for item in writer.chunks)
    other = tmp_path / "other"
    other.mkdir()
    oversized = TrajectoryWriter(other, str(uuid4()))
    with pytest.raises(ValueError, match="frame exceeds"):
        oversized.frame(0, [vehicle()] * 10, [], [], [], 10, 0)


def write_tripinfo(path: Path, trips: str = "") -> None:
    path.write_text(f"<tripinfos>{trips}</tripinfos>")


def measured_metrics(path: Path, completed: int = 0) -> list[dict[str, Any]]:
    return calculate_metrics(path, 3, 2, completed, 1, 30, 1.2, 0.8, 20, 2)


def test_metrics_keep_incomplete_counts_and_null_zero_completed_means(tmp_path: Path) -> None:
    path = tmp_path / "tripinfo.xml"
    write_tripinfo(path, "<tripinfo id='unfinished' arrival='-1'/>")
    values = {row["metric_name"]: row for row in measured_metrics(path)}
    assert values["generated_trips"]["value"] == 3
    assert values["departed_trips"]["value"] == 2
    assert values["completed_trips"]["value"] == 0
    assert values["incomplete_trips"]["value"] == 3
    assert values["mean_trip_duration"]["value"] is None
    assert values["mean_time_loss"]["value"] is None
    assert values["mean_waiting_time"]["value"] is None
    assert values["mean_moving_speed"]["value"] == 10


def test_metrics_match_only_actual_completed_output_values(tmp_path: Path) -> None:
    path = tmp_path / "tripinfo.xml"
    write_tripinfo(
        path,
        "<tripinfo id='a' arrival='20' duration='18' timeLoss='3' waitingTime='2'/>"
        "<tripinfo id='b' arrival='25' duration='22' timeLoss='7' waitingTime='4'/>"
        "<tripinfo id='c' arrival='-1'/>",
    )
    values = {row["metric_name"]: row["value"] for row in measured_metrics(path, completed=2)}
    assert values["mean_trip_duration"] == 20
    assert values["mean_time_loss"] == 5
    assert values["mean_waiting_time"] == 3
    assert values["incomplete_trips"] == 1
    assert values["worker_execution_time"] == 1.2
    assert values["simulation_duration"] == 30


@pytest.mark.parametrize(
    "payload", ["<!DOCTYPE x><tripinfos/>", "<!ENTITY x SYSTEM 'file:///etc/passwd'>"]
)
def test_xml_entities_and_dtds_are_rejected_before_parsing(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "input.xml"
    path.write_text(payload)
    with pytest.raises(ValueError, match="DTD/entity"):
        reject_xml_declarations(path)


def test_duplicate_tripinfo_identity_and_count_mismatch_fail(tmp_path: Path) -> None:
    path = tmp_path / "tripinfo.xml"
    write_tripinfo(path, "<tripinfo id='a' arrival='-1'/><tripinfo id='a' arrival='-1'/>")
    with pytest.raises(ValueError, match="duplicate"):
        measured_metrics(path)
    write_tripinfo(path)
    with pytest.raises(ValueError, match="disagree"):
        measured_metrics(path, completed=1)


def test_output_root_budget_and_links_are_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import earthmind_worker.simulation_artifacts as module

    monkeypatch.setattr(module, "MAX_OUTPUT_BYTES", 8)
    (tmp_path / "large").write_bytes(b"a" * 9)
    with pytest.raises(ValueError, match="output exceeded"):
        output_bytes(tmp_path)
    (tmp_path / "large").unlink()
    (tmp_path / "linked").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="symbolic links"):
        output_bytes(tmp_path)
