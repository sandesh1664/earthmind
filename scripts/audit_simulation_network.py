"""Read-only audit of retained SUMO inputs; no download, conversion or database mutation."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any

from earthmind_worker.runtime_check import EXPECTED_SUMO_VERSION, binary_version
from earthmind_worker.simulation_artifacts import checksum
from earthmind_worker.simulation_network import prepare_network


def bounded_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("A bounded regular provenance manifest is required")
    value: Any = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("Provenance manifest must be an object")
    return value


def audit(directory: Path, verify_runtime: bool = False) -> dict[str, Any]:
    prepared = prepare_network(directory)
    conversion = bounded_json(directory / "conversion-manifest.json")
    if (
        conversion.get("network_checksum_sha256") != prepared.provenance["sumo_network_sha256"]
        or conversion.get("source_checksum_sha256") != prepared.provenance["osm_sha256"]
    ):
        raise ValueError("Conversion provenance differs from retained input checksums")
    original_command = conversion.get("command")
    if (
        not isinstance(original_command, list)
        or not all(isinstance(value, str) for value in original_command)
        or "netconvert" not in original_command
    ):
        raise ValueError("Retained conversion command is missing")
    # Public conversion flags omit host-specific Docker bind paths/private source URLs.
    native_command = original_command[original_command.index("netconvert") :]
    source = directory / "source.osm.xml"
    source_verified = False
    if source.exists():
        if source.is_symlink() or not 0 < source.stat().st_size <= 64 * 1024 * 1024:
            raise ValueError("Original OSM extract exceeds its bounded regular-file budget")
        source_verified = checksum(source) == prepared.provenance["osm_sha256"]
        if not source_verified:
            raise ValueError("Original OSM bytes differ from the import checksum")
    warning_log = directory / "netconvert.log"
    warnings: list[str] = []
    warning_sha256: str | None = None
    if warning_log.exists():
        if warning_log.is_symlink() or warning_log.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Retained converter log exceeds its bounded regular-file budget")
        warning_sha256 = checksum(warning_log)
        warnings = [
            line.strip()
            for line in warning_log.read_text(errors="replace").splitlines()
            if line.strip().startswith("Warning:")
        ]
    statistics = dict(prepared.audit)
    statistics["engine_version_requirement"] = statistics.pop("engine_version")
    runtime = None
    if verify_runtime:
        runtime = {name: binary_version(name) for name in ["sumo", "netconvert"]}
    packages = {name: importlib.metadata.version(name) for name in ["sumolib", "traci"]}
    if any(value != EXPECTED_SUMO_VERSION for value in packages.values()):
        raise ValueError("Python SUMO adapters differ from the pinned engine requirement")
    return {
        "status": "PASS",
        "scope": "Actual retained input bytes/projection/connections; no new SUMO execution",
        "network_id": prepared.provenance["network_id"],
        "bbox": prepared.provenance["bbox"],
        "checksums": {
            "original_osm": prepared.provenance["osm_sha256"],
            "sumo_network": prepared.provenance["sumo_network_sha256"],
            "source_sumo_database_mapping": prepared.provenance["mapping_sha256"],
        },
        "original_osm_bytes_verified": source_verified,
        "actual_statistics": statistics,
        "statistics_scope": (
            "Lanes/connections/components use mapped permitted passenger edges; "
            "junction/controller counts describe the full retained conversion"
        ),
        "boundary_candidates": (
            "Descriptive approximately100m edge-end proximity to the chosen study extent, "
            "not measured traffic boundary flows or official administrative boundaries"
        ),
        "conversion_command": native_command,
        "conversion_timestamp": conversion.get("converted_at"),
        "inference_policy": conversion.get("inference_policy"),
        "converter_warning_line_count": len(warnings),
        "warning_count_interpretation": (
            "Physical Warning log lines, not individual occurrences; "
            "native converter aggregation can summarize repeated warnings"
        ),
        "converter_warning_sample": warnings[:30],
        "converter_log_sha256": warning_sha256,
        "complete_warnings_preserved_in_ignored_original_log": warning_log.exists(),
        "python_adapters": packages,
        "native_binary_versions": runtime,
        "native_binary_check": "PASS" if verify_runtime else "NOT RUN",
        "limitations": [
            "No traffic-light timing or lane inference is field verified",
            "Directed allowed-edge connectivity differs from the PostGIS node graph",
            "Projection round trips measure numerical consistency, not survey accuracy",
            "Actual vehicle execution and replay require separate native/browser verification",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/dubai-osm/recovery-v1"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-runtime", action="store_true")
    options = parser.parse_args()
    directory = options.directory.resolve(strict=True)
    result = audit(directory, options.verify_runtime)
    output = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if options.output:
        destination = options.output.resolve()
        if destination.is_relative_to(directory):
            raise ValueError("Audit reports cannot modify retained immutable input artifacts")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(output)
    print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
