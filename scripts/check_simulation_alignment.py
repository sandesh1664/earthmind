"""Check actual recorded replay samples against retained SUMO lane/junction geometry.

This verifies projection/wire alignment, not independent surveyed geographic accuracy.
No positions are generated and no original/run artifacts are modified.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from earthmind_contracts.simulation import ReplayManifest, TrajectoryChunk
from earthmind_worker.simulation_artifacts import MAX_CHUNK_BYTES, checksum
from earthmind_worker.simulation_network import prepare_network
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree


def alignment(
    network_directory: Path,
    run_directory: Path,
    max_samples: int = 50000,
    tolerance_m: float = 5,
) -> dict[str, Any]:
    import sumolib  # type: ignore[import-untyped]

    if not 1 <= max_samples <= 200000 or not 0.05 <= tolerance_m <= 50:
        raise ValueError("Alignment sampling/tolerance is outside the bounded audit budget")
    if run_directory.is_symlink():
        raise ValueError("Run artifact directories cannot be symbolic links")
    manifest_path = run_directory / "replay-manifest.json"
    if manifest_path.is_symlink() or not 1 <= manifest_path.stat().st_size <= 1024 * 1024:
        raise ValueError("Replay manifest exceeds its regular-file read budget")
    manifest = ReplayManifest.model_validate_json(manifest_path.read_bytes())
    prepared = prepare_network(network_directory, str(manifest.network_version_id))
    # Include real native internal junction lanes: a car crossing a junction is
    # not expected to lie on an ordinary road's endpoint-to-endpoint centerline.
    native = sumolib.net.readNet(
        str(network_directory / "network.net.xml"), withInternal=True, withConnections=True
    )
    shapes: list[LineString] = []
    ordinary_lanes, internal_lanes = 0, 0
    allowed = set(prepared.provenance["allowed_sumo_edge_ids"])
    for edge in native.getEdges(withInternal=True):
        identifier = str(edge.getID())
        internal = identifier.startswith(":")
        if not internal and identifier not in allowed:
            continue
        for lane in edge.getLanes():
            if not lane.allows("passenger"):
                continue
            coordinates = [(float(x), float(y)) for x, y in lane.getShape()]
            if len(coordinates) < 2 or not all(
                math.isfinite(value) for coordinate in coordinates for value in coordinate
            ):
                raise ValueError("Native lane geometry is invalid")
            shapes.append(LineString(coordinates))
            if internal:
                internal_lanes += 1
            else:
                ordinary_lanes += 1
            if len(shapes) > 50000:
                raise ValueError("Lane spatial index exceeds its audit budget")
    if not shapes:
        raise ValueError("No actual permitted lane geometry is available")
    tree = STRtree(shapes)
    recorded_total = sum(chunk.sample_count for chunk in manifest.chunks)
    stride = max(1, math.ceil(recorded_total / max_samples))
    ordinal = 0
    distances: list[float] = []
    bytes_read = 0
    for reference in manifest.chunks:
        path = run_directory / "replay" / f"{reference.id}.json"
        if path.is_symlink() or path.resolve().parent != (run_directory / "replay").resolve():
            raise ValueError("Replay chunk path escapes its run")
        if path.stat().st_size != reference.size_bytes or reference.size_bytes > MAX_CHUNK_BYTES:
            raise ValueError("Replay chunk byte metadata differs from its manifest")
        bytes_read += reference.size_bytes
        if bytes_read > 256 * 1024 * 1024 or checksum(path) != reference.sha256:
            raise ValueError("Replay byte budget or checksum verification failed")
        chunk = TrajectoryChunk.model_validate_json(path.read_bytes())
        if chunk.run_id != manifest.run_id or chunk.chunk_id != reference.id:
            raise ValueError("Replay chunk scope differs from its manifest")
        for frame in chunk.frames:
            for sample in frame.vehicles:
                take = ordinal % stride == 0
                ordinal += 1
                if not take:
                    continue
                x, y = native.convertLonLat2XY(sample.longitude, sample.latitude)
                point = Point(float(x), float(y))
                nearest = tree.nearest(point)
                if nearest is None:
                    raise ValueError("No nearest actual SUMO lane exists")
                distance = float(point.distance(shapes[int(nearest)]))
                if not math.isfinite(distance):
                    raise ValueError("Alignment distance is not finite")
                distances.append(distance)
    if ordinal != recorded_total or not distances:
        raise ValueError("Replay sample metadata is inconsistent or contains no vehicle positions")
    distances.sort()
    maximum = distances[-1]
    return {
        "status": "PASS" if maximum <= tolerance_m else "FAIL",
        "scope": "Actual immutable recorded SUMO positions against actual retained lane geometry",
        "run_id": str(manifest.run_id),
        "network_id": str(manifest.network_version_id),
        "network_sha256": prepared.provenance["sumo_network_sha256"],
        "manifest_sha256": checksum(manifest_path),
        "recorded_samples_including_overlap": recorded_total,
        "checked_samples": len(distances),
        "deterministic_stride": stride,
        "ordinary_mapped_passenger_lanes": ordinary_lanes,
        "native_internal_passenger_lanes": internal_lanes,
        "tolerance_m": tolerance_m,
        "maximum_distance_m": maximum,
        "mean_distance_m": sum(distances) / len(distances),
        "p95_distance_m": distances[int((len(distances) - 1) * 0.95)],
        "out_of_tolerance_samples": sum(value > tolerance_m for value in distances),
        "projection": "Retained SUMO projected XY after recorded EPSG4326 lon/lat conversion",
        "limitations": [
            "Not an independent source/survey accuracy assessment",
            "Nearest-lane check includes actual internal junction lanes in the retained conversion",
            "Route membership is independently constrained by worker demand validation",
            "Deterministic bounded sample may not examine every position; "
            "counts/stride are explicit",
            "No interpolated browser or invented points were used",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--network-directory", type=Path, default=Path("data/dubai-osm/recovery-v1")
    )
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--max-samples", type=int, default=50000)
    parser.add_argument("--tolerance-m", type=float, default=5)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    network = options.network_directory.resolve(strict=True)
    run = options.run_directory.resolve(strict=True)
    result = alignment(network, run, options.max_samples, options.tolerance_m)
    output = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if options.output:
        destination = options.output.resolve()
        if destination.is_relative_to(network) or destination.is_relative_to(run):
            raise ValueError(
                "Audit output cannot modify immutable input or completed run artifacts"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(output)
    print(output, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
