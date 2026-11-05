"""Versioned metrics from actual TripInfo and per-step SUMO measurements."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from earthmind_worker.real_network_smoke import finite_number
from earthmind_worker.simulation_network import reject_xml_declarations

CALCULATION_VERSION = "m04-sumo-tripinfo-and-step-v1"


def calculate_metrics(
    tripinfo: Path,
    generated: int,
    departed: int,
    completed: int,
    teleports: int,
    simulated_seconds: float,
    worker_wall_seconds: float,
    sumo_wall_seconds: float,
    moving_speed_sum: float,
    moving_speed_samples: int,
) -> list[dict[str, Any]]:
    reject_xml_declarations(tripinfo, 64 * 1024 * 1024)
    identifiers: set[str] = set()
    durations: list[float] = []
    time_loss: list[float] = []
    waiting: list[float] = []
    for _event, element in ET.iterparse(tripinfo, events=("end",)):
        if element.tag != "tripinfo":
            continue
        identifier = element.attrib.get("id", "")
        if not identifier or identifier in identifiers or len(identifiers) >= generated:
            raise ValueError("TripInfo has duplicate, missing or excess vehicle identities")
        identifiers.add(identifier)
        arrival = finite_number(element.attrib.get("arrival", "-1"))
        if arrival >= 0:
            duration = finite_number(element.attrib["duration"])
            delay = finite_number(element.attrib["timeLoss"])
            waiting_time = finite_number(element.attrib["waitingTime"])
            if duration < 0 or delay < -0.001 or waiting_time < 0:
                raise ValueError("Completed trip has invalid duration, delay or waiting time")
            durations.append(duration)
            time_loss.append(max(0.0, delay))
            waiting.append(waiting_time)
        element.clear()
    if len(durations) != completed or not 0 <= completed <= departed <= generated:
        raise ValueError("TraCI counts and completed SUMO TripInfo outputs disagree")

    def mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    values: list[tuple[str, float | int | None, str, str]] = [
        ("generated_trips", generated, "trips", "count"),
        ("departed_trips", departed, "trips", "count"),
        ("completed_trips", completed, "trips", "count"),
        ("incomplete_trips", generated - completed, "trips", "count"),
        ("mean_trip_duration", mean(durations), "s", "completed_trip_mean"),
        ("mean_time_loss", mean(time_loss), "s", "completed_trip_mean"),
        ("mean_waiting_time", mean(waiting), "s", "completed_trip_mean"),
        (
            "mean_moving_speed",
            moving_speed_sum / moving_speed_samples if moving_speed_samples else None,
            "m/s",
            "moving_vehicle_step_mean",
        ),
        ("teleports", teleports, "events", "count"),
        ("simulation_duration", simulated_seconds, "s", "observed"),
        ("worker_execution_time", worker_wall_seconds, "s", "wall_clock"),
        ("sumo_execution_time", sumo_wall_seconds, "s", "wall_clock"),
        (
            "completed_throughput",
            completed * 3600 / simulated_seconds if simulated_seconds > 0 else None,
            "trips/h",
            "completed_per_simulated_hour",
        ),
    ]
    return [
        {
            "metric_name": name,
            "value": value,
            "unit": unit,
            "aggregation": aggregation,
            "calculation_version": CALCULATION_VERSION,
        }
        for name, value, unit, aggregation in values
    ]
