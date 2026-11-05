"""Deterministic, explicitly synthetic passenger OD selection on verified directed lanes."""

from __future__ import annotations

import hashlib
import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from earthmind_worker.simulation_network import PreparedNetwork

DEMAND_CALCULATION_VERSION = "m04-reachable-uniform-v1"
MAX_EFFECTIVE_TRIPS = 5000


def effective_trip_count(target: int, multiplier: float) -> int:
    count = round(target * multiplier)
    if not 1 <= count <= MAX_EFFECTIVE_TRIPS:
        raise ValueError("Effective synthetic trip count must be between 1 and 5000")
    return count


def ordinal_random(seed: int, ordinal: int, channel: str) -> random.Random:
    # Independent channels/ordinals preserve common trips when target count changes.
    digest = hashlib.sha256(f"m04-v1:{seed}:{ordinal}:{channel}".encode()).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))


def _departure(seed: int, ordinal: int, distribution: str, duration: int) -> float:
    generator = ordinal_random(seed, ordinal, "departure")
    horizon = duration * 0.7  # Leave room to finish; no claim that every trip can finish.
    if distribution == "uniform":
        return round(generator.uniform(0, horizon), 3)
    if distribution == "burst":
        return 0.0
    raise ValueError("Unsupported departure distribution")


def generate_demand(network: PreparedNetwork, demand: Any, output: Path) -> dict[str, Any]:
    count = effective_trip_count(demand.trip_target, demand.demand_multiplier)
    if demand.vehicle_class != "passenger" or demand.od_policy != "reachable_uniform":
        raise ValueError("Only validated passenger reachable_uniform demand is supported")
    origins = sorted(identifier for identifier, targets in network.successors.items() if targets)
    if not origins:
        raise ValueError("No valid origin edges are available")
    root = ET.Element("routes")
    root.append(ET.Comment("Synthetic research demand; not live or calibrated Dubai traffic"))
    ET.SubElement(
        root,
        "vType",
        {"id": "synthetic_passenger", "vClass": "passenger", "color": "0.15,0.75,0.95"},
    )
    trips: list[dict[str, Any]] = []
    rejected = 0
    poisson_clock = 0.0
    for ordinal in range(count):
        generator = ordinal_random(demand.seed, ordinal, "route")
        route: list[str] | None = None
        for _ in range(24):
            origin = generator.choice(origins)
            parents = network.reachable(origin)
            destinations = sorted(identifier for identifier in parents if identifier != origin)
            if not destinations:
                rejected += 1
                continue
            destination = generator.choice(destinations)
            selected: list[str] = [destination]
            while selected[-1] != origin:
                parent = parents[selected[-1]]
                if parent is None:
                    break
                selected.append(parent)
            selected.reverse()
            length = sum(network.lengths[identifier] for identifier in selected)
            if network.validate_route(selected) and 100 <= length <= 6000:
                route = selected
                break
            rejected += 1
        if route is None:
            raise ValueError(
                "Bounded OD search could not construct every requested passenger route"
            )
        if demand.departure_distribution == "poisson":
            # A fixed number of genuine exponential inter-arrivals. Departures
            # beyond the simulation horizon remain generated/incomplete, not clipped.
            poisson_clock += ordinal_random(demand.seed, ordinal, "departure").expovariate(
                count / (demand.duration_seconds * 0.7)
            )
            departure = round(poisson_clock, 3)
        else:
            departure = _departure(
                demand.seed, ordinal, demand.departure_distribution, demand.duration_seconds
            )
        trips.append(
            {
                "id": f"synthetic_{ordinal:06d}",
                "depart": departure,
                "route": route,
            }
        )
    trips.sort(key=lambda trip: (trip["depart"], trip["id"]))
    for trip in trips:
        vehicle = ET.SubElement(
            root,
            "vehicle",
            {
                "id": trip["id"],
                "type": "synthetic_passenger",
                "depart": f"{trip['depart']:.3f}",
                "departLane": "best",
                "departSpeed": "0",
            },
        )
        ET.SubElement(vehicle, "route", {"edges": " ".join(trip["route"])})
    ET.indent(root)
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    metadata = {
        "calculation_version": DEMAND_CALCULATION_VERSION,
        "synthetic": True,
        "is_live_traffic": False,
        "parameters": demand.model_dump(mode="json"),
        "generated_trips": count,
        "rejected_route_candidates": rejected,
        "route_validation": "Every transition is an actual permitted imported SUMO connection",
        "common_random_inputs": (
            "Independent seed/ordinal channels preserve common routes "
            "and uniform/burst departures; "
            "Poisson exponential draws are shared but the rate scales with effective trip target"
        ),
        "last_scheduled_departure": max(trip["depart"] for trip in trips),
        "demand_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    (output.parent / "demand-manifest.json").write_text(
        json.dumps(metadata, sort_keys=True, indent=2) + "\n"
    )
    return metadata
