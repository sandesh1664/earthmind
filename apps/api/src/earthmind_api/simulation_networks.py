"""Readiness of retained, checksummed SUMO inputs; no implicit downloads/conversion."""

import asyncio
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from earthmind_contracts.simulation import DemandConfig, ScenarioValidation, SimulationInput
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from earthmind_api.geospatial_models import DataSource, NetworkVersion, Region, RoadEdge
from earthmind_api.settings import Settings


@dataclass(frozen=True)
class NetworkInput:
    slug: str
    manifest: dict[str, Any]
    engine_version: str | None
    mapped_edges: frozenset[str]


def bounded_read(directory: Path, name: str, maximum: int) -> bytes:
    path = directory / name
    if path.is_symlink() or path.resolve().parent != directory.resolve() or not path.is_file():
        raise ValueError("Retained SUMO input file is unavailable")
    if path.stat().st_size > maximum:
        raise ValueError("Retained SUMO input exceeds its byte budget")
    with path.open("rb") as source:
        value = source.read(maximum + 1)
    if len(value) > maximum:
        raise ValueError("Retained SUMO input exceeds its byte budget")
    return value


def find_network_input(root: Path, network_id: UUID) -> NetworkInput:
    if not root.is_dir():
        raise ValueError("Retained SUMO inputs are not mounted; configure simulation inputs root")
    candidates = sorted(path for path in root.iterdir() if path.is_dir() and not path.is_symlink())
    if len(candidates) > 20:
        raise ValueError("Too many retained input versions; narrow the configured input root")
    for directory in candidates:
        if not (directory / "import-manifest.json").is_file():
            continue
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", directory.name) is None:
            continue
        try:
            manifest = json.loads(bounded_read(directory, "import-manifest.json", 1024 * 1024))
        except FileNotFoundError:
            continue
        if manifest.get("network_id") != str(network_id):
            continue
        network = bounded_read(directory, "network.net.xml", 64 * 1024 * 1024)
        mapping = bounded_read(directory, "source-sumo-db-mapping.json", 8 * 1024 * 1024)
        source = bounded_read(directory, "source.osm.xml", 64 * 1024 * 1024)
        for value, expected in (
            (network, manifest.get("sumo_network_sha256")),
            (mapping, manifest.get("mapping_sha256")),
            (source, manifest.get("osm_sha256")),
        ):
            if hashlib.sha256(value).hexdigest() != expected:
                raise ValueError(
                    "Retained source, network or mapping checksum differs from its manifest"
                )
        if b"<!DOCTYPE" in network.upper() or b"<!ENTITY" in network.upper():
            raise ValueError("SUMO XML entity declarations are not accepted")
        document = ET.fromstring(network)
        location = document.find("location")
        if (
            document.tag != "net"
            or location is None
            or location.get("projParameter") in {None, "!", "-", "."}
        ):
            raise ValueError("SUMO network has no verified geographic projection")
        converted = {
            edge.get("id"): edge
            for edge in document.findall("edge")
            if edge.get("function") != "internal"
        }
        metadata = json.loads(mapping)
        if metadata.get("network_id") != str(network_id):
            raise ValueError("SUMO mapping belongs to another network version")
        source_edges = metadata.get("osm_way_to_sumo_and_database_edges")
        if not isinstance(source_edges, dict) or len(source_edges) > 10000:
            raise ValueError("SUMO mapping format is invalid")
        mapped: set[str] = set()
        for records in source_edges.values():
            if not isinstance(records, list):
                raise ValueError("SUMO mapping entries are invalid")
            for record in records:
                edge_id = record.get("sumo_edge_id")
                if not isinstance(edge_id, str) or edge_id not in converted:
                    raise ValueError("Mapped SUMO edge is absent from the retained network")
                edge = converted[edge_id]
                if not edge.findall("lane") or not edge.get("from") or not edge.get("to"):
                    raise ValueError("Mapped SUMO edge has no lanes or valid junction identifiers")
                mapped.add(edge_id)
        if len(mapped) != manifest.get("edge_count"):
            raise ValueError("SUMO mapping count differs from the import manifest")
        version = re.search(rb"netconvert Version ([0-9.]+)", network[:8192])
        return NetworkInput(
            directory.name, manifest, version[1].decode() if version else None, frozenset(mapped)
        )
    raise ValueError("No retained SUMO-compatible artifact matches this published network")


async def validate_network_input(
    session: AsyncSession, settings: Settings, network_id: UUID
) -> tuple[NetworkVersion | None, ScenarioValidation, NetworkInput | None]:
    network = await session.get(NetworkVersion, network_id)
    errors: list[str] = []
    warnings = [
        "Synthetic passenger demand is not measured Dubai traffic or verified signal timing."
    ]
    if network is None:
        return (
            None,
            ScenarioValidation(valid=False, errors=["Network version does not exist"]),
            None,
        )
    if (
        network.status != "published"
        or not network.is_validated
        or "osm" not in network.source_format.lower()
    ):
        return (
            network,
            ScenarioValidation(
                valid=False, errors=["Select a published, validated OSM-derived SUMO network"]
            ),
            None,
        )
    artifact: NetworkInput | None = None
    try:
        artifact = await asyncio.to_thread(
            find_network_input, Path(settings.simulation_inputs_root), network_id
        )
        source = (
            await session.get(DataSource, network.data_source_id)
            if network.data_source_id
            else None
        )
        if source is None or source.checksum_sha256 != artifact.manifest["osm_sha256"]:
            errors.append("Published source checksum differs from retained SUMO lineage")
        actual_ids = frozenset(
            (
                await session.scalars(
                    select(RoadEdge.sumo_edge_id).where(RoadEdge.network_version_id == network_id)
                )
            ).all()
        )
        if actual_ids != artifact.mapped_edges or len(actual_ids) != network.edge_count:
            errors.append("Published road identifiers differ from retained SUMO mapping")
        if network.validation_summary.get("status") == "VALID_WITH_WARNINGS":
            warnings.append(
                "The source network has structural warnings; "
                "disconnected components remain reported."
            )
    except (ValueError, OSError, ET.ParseError, json.JSONDecodeError):
        errors.append(
            "Retained SUMO artifacts are unavailable or fail checksum, "
            "projection, lane or mapping validation"
        )
    return (
        network,
        ScenarioValidation(
            valid=not errors,
            errors=errors,
            warnings=warnings,
            network_artifact_sha256=artifact.manifest["sumo_network_sha256"] if artifact else None,
            mapped_edge_count=len(artifact.mapped_edges) if artifact else None,
            engine_version=artifact.engine_version if artifact else None,
        ),
        artifact,
    )


def simulation_input(
    network_id: UUID, artifact: NetworkInput, demand: DemandConfig
) -> SimulationInput:
    return SimulationInput(
        network_version_id=network_id,
        network_artifact=artifact.slug,
        network_sha256=artifact.manifest["sumo_network_sha256"],
        source_sha256=artifact.manifest["osm_sha256"],
        mapping_sha256=artifact.manifest["mapping_sha256"],
        demand=demand,
    )


async def network_catalog(
    session: AsyncSession, settings: Settings, limit: int, offset: int
) -> dict[str, Any]:
    total = await session.scalar(
        select(func.count()).select_from(NetworkVersion).where(NetworkVersion.status == "published")
    )
    records = list(
        (
            await session.scalars(
                select(NetworkVersion)
                .where(NetworkVersion.status == "published")
                .order_by(NetworkVersion.created_at, NetworkVersion.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    items = []
    for network in records:
        _, validation, artifact = await validate_network_input(session, settings, network.id)
        region = await session.get(Region, network.region_id)
        items.append(
            {
                "id": str(network.id),
                "version_label": network.version_label,
                "region_name": region.name if region else "Unknown study region",
                "is_synthetic": "osm" not in network.source_format.lower(),
                "source_checksum": artifact.manifest["osm_sha256"] if artifact else None,
                "network_artifact_sha256": validation.network_artifact_sha256,
                "engine_version": validation.engine_version,
                "mapped_edge_count": validation.mapped_edge_count,
                "validation": validation.model_dump(mode="json"),
            }
        )
    return {"items": items, "total": total or 0, "limit": limit, "offset": offset}
