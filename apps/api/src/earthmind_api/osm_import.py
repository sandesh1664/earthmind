"""Bounded OSM/SUMO artifact ingestion into the existing M02 persistence model.

Source OSM coordinates/tags remain in the original extract. Display road geometry
is explicitly the georeferenced SUMO carriageway centerline derived from that OSM
extract, with original junction centers restored as graph endpoints.
"""

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from geoalchemy2.shape import from_shape
from pyproj import Transformer
from shapely.geometry import LineString, MultiPolygon, Point, box
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from earthmind_api.dependencies import Infrastructure
from earthmind_api.geospatial_models import (
    AuditEvent,
    DataSource,
    Intersection,
    NetworkVersion,
    Region,
    RoadEdge,
)
from earthmind_api.network_validation import validate_network
from earthmind_api.settings import Settings

MAX_XML_BYTES = 64 * 1024 * 1024
MAX_FEATURES = 10000
MAX_POSITIONS = 100000
SLUG = "dubai-downtown-business-bay-osm"
POLICY = "sumo_lane_centerline_from_osm"


def xml_document(path: Path) -> ET.Element:
    if path.stat().st_size > MAX_XML_BYTES:
        raise ValueError("XML artifact exceeds the64MiB processing budget")
    payload = path.read_bytes()
    if len(payload) > MAX_XML_BYTES:
        raise ValueError("XML artifact exceeds the64MiB processing budget")
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("XML declarations/entities are not accepted")
    return ET.fromstring(payload)


def tags(element: ET.Element) -> dict[str, str]:
    return {
        item.attrib["k"]: item.attrib["v"]
        for item in element.findall("tag")
        if "k" in item.attrib and "v" in item.attrib
    }


def recorded_speed(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(mph|km/h|kph)?\s*", value)
    if match is None:
        return None
    number = float(match[1])
    speed = number * (0.44704 if match[2] == "mph" else 1 / 3.6)
    return speed if 0 < speed < 100 and math.isfinite(speed) else None


def source_way_ids(edge: ET.Element, available: set[str]) -> list[str]:
    candidates: set[str] = set()
    for parameter in edge.iter("param"):
        if parameter.get("key", "").lower() == "origid":
            for token in parameter.get("value", "").split():
                identifier = token.lstrip("-").split("#")[0]
                if identifier in available:
                    candidates.add(identifier)
    # Older converters may omit origId for otherwise unchanged input IDs. Only
    # accept this fallback if the identifier exists in the actual original XML.
    if not candidates:
        identifier = edge.get("id", "").lstrip("-").split("#")[0]
        if identifier in available:
            candidates.add(identifier)
    return sorted(candidates, key=int)


def xy_points(value: str) -> list[tuple[float, float]]:
    result = []
    for point in value.split():
        pair = point.split(",")
        if len(pair) not in {2, 3}:
            raise ValueError("Invalid converted XY coordinate")
        x, y = float(pair[0]), float(pair[1])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Converted coordinates must be finite")
        result.append((x, y))
    return result


@dataclass(frozen=True)
class ImportedNode:
    identifier: str
    source_identifier: str
    coordinate: tuple[float, float]
    is_signalized: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ImportedEdge:
    identifier: str
    start: str
    end: str
    source_ids: list[str]
    name: str | None
    road_class: str
    geometry: LineString
    lanes: int
    speed: float | None
    one_way: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PreparedImport:
    source: dict[str, Any]
    source_hash: str
    network_hash: str
    checksum: str
    bounds: tuple[float, float, float, float]
    nodes: dict[str, ImportedNode]
    edges: list[ImportedEdge]
    omitted: dict[str, int]
    source_way_count: int


def prepare_import(directory: Path) -> PreparedImport:
    source: dict[str, Any] = json.loads((directory / "source-manifest.json").read_text())
    conversion = json.loads((directory / "conversion-manifest.json").read_text())
    osm_path, net_path = directory / "source.osm.xml", directory / "network.net.xml"
    source_hash = hashlib.sha256(osm_path.read_bytes()).hexdigest()
    network_hash = hashlib.sha256(net_path.read_bytes()).hexdigest()
    if (
        source_hash != source["checksum_sha256"]
        or source_hash != conversion["source_checksum_sha256"]
        or network_hash != conversion["network_checksum_sha256"]
    ):
        raise ValueError("Original extract or converted network checksum does not match manifest")
    bounds = tuple(float(value) for value in source["bbox_west_south_east_north"])
    if len(bounds) != 4:
        raise ValueError("Source bbox must have4 coordinates")
    west, south, east, north = bounds
    if not (55 <= west < east <= 56 and 24.8 <= south < north <= 25.5):
        raise ValueError("Only the bounded Dubai research area is supported")
    if east - west > 0.05 or north - south > 0.05:
        raise ValueError("Source bbox exceeds reviewed import budget")
    boundary = box(west, south, east, north)
    osm = xml_document(osm_path)
    network = xml_document(net_path)
    if osm.tag != "osm" or network.tag != "net":
        raise ValueError("Expected original OSM and converted SUMO XML roots")
    osm_nodes = {item.attrib["id"]: tags(item) for item in osm.findall("node")}
    ways = {item.attrib["id"]: tags(item) for item in osm.findall("way") if "highway" in tags(item)}
    location = network.find("location")
    if location is None or location.get("projParameter") in {None, "!", "-", "."}:
        raise ValueError("SUMO network must contain a real geographic projection")
    offsets = xy_points(location.attrib["netOffset"])
    if len(offsets) != 1:
        raise ValueError("Network requires one geographic projection offset")
    offset_x, offset_y = offsets[0]
    transformer = Transformer.from_crs(
        location.attrib["projParameter"], "EPSG:4326", always_xy=True
    )

    def geographic(x: float, y: float) -> tuple[float, float]:
        longitude, latitude = transformer.transform(x - offset_x, y - offset_y)
        if not all(math.isfinite(v) for v in (longitude, latitude)):
            raise ValueError("Projection produced invalid geographic coordinates")
        return round(longitude, 9), round(latitude, 9)

    nodes = {}
    for junction in network.findall("junction"):
        identifier = junction.attrib["id"]
        if identifier.startswith(":") or len(identifier) > 100:
            continue
        original_tags = osm_nodes.get(identifier, {})
        signalized = original_tags.get("highway") == "traffic_signals"
        nodes[identifier] = ImportedNode(
            identifier=identifier,
            source_identifier=(
                f"osm:node:{identifier}" if identifier in osm_nodes else f"sumo:node:{identifier}"
            ),
            coordinate=geographic(float(junction.attrib["x"]), float(junction.attrib["y"])),
            is_signalized=signalized,
            metadata={
                "is_synthetic": False,
                "signal_status": "osm_tag_not_field_verified" if signalized else "not_recorded",
                "osm_node_id": identifier if identifier in osm_nodes else None,
                "sumo_identifier_verified": True,
                "node_origin": "osm" if identifier in osm_nodes else "sumo_conversion",
            },
        )
    edges = []
    omitted = {"outside_bbox": 0, "self_loop": 0, "unmapped_source": 0, "unsupported": 0}
    used_nodes: set[str] = set()
    for item in network.findall("edge"):
        identifier = item.attrib["id"]
        if item.get("function") == "internal" or identifier.startswith(":"):
            continue
        start, end = item.get("from", ""), item.get("to", "")
        lanes = item.findall("lane")
        if start == end:
            omitted["self_loop"] += 1
            continue
        if start not in nodes or end not in nodes or not lanes or len(identifier) > 128:
            omitted["unsupported"] += 1
            continue
        originals = source_way_ids(item, set(ways))
        if not originals:
            omitted["unmapped_source"] += 1
            continue
        shapes = [xy_points(lane.get("shape", "")) for lane in lanes]
        if not shapes[0] or any(len(value) != len(shapes[0]) for value in shapes):
            omitted["unsupported"] += 1
            continue
        center = [
            (
                sum(shape[i][0] for shape in shapes) / len(shapes),
                sum(shape[i][1] for shape in shapes) / len(shapes),
            )
            for i in range(len(shapes[0]))
        ]
        coordinates = [
            nodes[start].coordinate,
            *(geographic(x, y) for x, y in center),
            nodes[end].coordinate,
        ]
        compact = [
            point
            for index, point in enumerate(coordinates)
            if index == 0 or point != coordinates[index - 1]
        ]
        if len(compact) < 2 or len(compact) > 5000:
            omitted["unsupported"] += 1
            continue
        geometry = LineString(compact)
        if geometry.is_empty or not geometry.is_valid or geometry.length == 0:
            omitted["unsupported"] += 1
            continue
        if not boundary.covers(geometry):
            omitted["outside_bbox"] += 1
            continue
        original = ways[originals[0]]
        directional = original.get(
            "lanes:backward" if identifier.startswith("-") else "lanes:forward"
        )
        speed_tag = original.get(
            "maxspeed:backward" if identifier.startswith("-") else "maxspeed:forward",
            original.get("maxspeed"),
        )
        speed = recorded_speed(speed_tag)
        lane_source = (
            "osm_directional_tag"
            if directional is not None and directional.isdigit() and int(directional) == len(lanes)
            else "sumo_interpreted_osm_lanes"
            if original.get("lanes")
            else "inferred_by_netconvert"
        )
        road_class = original.get("highway", "unclassified")
        edges.append(
            ImportedEdge(
                identifier=identifier,
                start=start,
                end=end,
                source_ids=originals,
                name=original.get("name", item.get("name")),
                road_class=road_class,
                geometry=geometry,
                lanes=len(lanes),
                speed=speed,
                one_way=original.get("oneway") in {"yes", "true", "1", "-1"}
                or original.get("junction") == "roundabout",
                metadata={
                    "is_synthetic": False,
                    "osm_way_id": originals[0],
                    "osm_way_ids": originals,
                    "osm_lanes": original.get("lanes"),
                    "osm_directional_lanes": directional,
                    "osm_maxspeed": speed_tag,
                    "lane_count_source": lane_source,
                    "speed_limit_source": "osm" if speed is not None else "missing",
                    "turn_restrictions_status": "partial_osm_relations_no_field_verification",
                    "sumo_identifier_verified": True,
                    "geometry_derivation": POLICY,
                    "sumo_operational_speed_mps": float(lanes[0].attrib["speed"]),
                    "original_osm_tags": original,
                },
            )
        )
        used_nodes.update((start, end))
    nodes = {identifier: node for identifier, node in nodes.items() if identifier in used_nodes}
    if not nodes or not edges:
        raise ValueError("No mapped real roads remain inside the declared Dubai extent")
    if (
        len(nodes) + len(edges) > MAX_FEATURES
        or sum(len(edge.geometry.coords) for edge in edges) + len(nodes) > MAX_POSITIONS
    ):
        raise ValueError("Converted network exceeds existing bounded validation budgets")
    checksum = hashlib.sha256(
        json.dumps(
            {
                "source_sha256": source_hash,
                "sumo_sha256": network_hash,
                "bbox": bounds,
                "geometry_policy": POLICY,
                "importer_version": 1,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return PreparedImport(
        source,
        source_hash,
        network_hash,
        checksum,
        (west, south, east, north),
        nodes,
        edges,
        omitted,
        len(ways),
    )


async def persist_import(
    session: AsyncSession, prepared: PreparedImport, directory: Path
) -> dict[str, Any]:
    region_id = uuid5(NAMESPACE_URL, f"earthmind:{SLUG}:{prepared.bounds}")
    source_id = uuid5(NAMESPACE_URL, f"earthmind:osm:source:{prepared.source_hash}")
    network_id = uuid5(NAMESPACE_URL, f"earthmind:osm:network:{prepared.checksum}")
    version = (
        f"osm-{prepared.source['downloaded_at'][:10].replace('-', '')}-{prepared.checksum[:12]}"
    )
    await session.execute(select(func.pg_advisory_xact_lock(20261027)))
    existing = await session.get(NetworkVersion, network_id)
    if existing is not None:
        if existing.status not in {"published", "archived"} or not existing.is_validated:
            raise RuntimeError("Existing import is not complete; no stored version overwritten")
        if existing.checksum_sha256 != prepared.checksum:
            raise RuntimeError("Existing network checksum differs; no stored version overwritten")
        actual_nodes = await session.scalar(
            select(func.count())
            .select_from(Intersection)
            .where(Intersection.network_version_id == network_id)
        )
        actual_edges = await session.scalar(
            select(func.count())
            .select_from(RoadEdge)
            .where(RoadEdge.network_version_id == network_id)
        )
        if (actual_nodes, actual_edges) != (len(prepared.nodes), len(prepared.edges)):
            raise RuntimeError("Existing published import is incomplete; no data overwritten")
        return {
            "created": False,
            "network_id": str(network_id),
            "region_id": str(region_id),
            "version_label": existing.version_label,
            "node_count": existing.node_count,
            "edge_count": existing.edge_count,
            "validation": existing.validation_summary,
        }
    region = await session.get(Region, region_id)
    if region is None:
        conflict = await session.scalar(select(Region).where(Region.slug == SLUG))
        if conflict is not None:
            raise RuntimeError(
                "OSM study slug belongs to a different region; preserving existing data"
            )
        session.add(
            Region(
                id=region_id,
                slug=SLUG,
                name="Downtown Dubai / Business Bay — OpenStreetMap Study Area",
                country_code="AE",
                emirate="Dubai",
                timezone="Asia/Dubai",
                boundary=from_shape(MultiPolygon([box(*prepared.bounds)]), srid=4326),
                metadata_={
                    "is_synthetic": False,
                    "source": "OpenStreetMap",
                    "description": (
                        "Real OSM-derived roads; research bbox is not an "
                        "official administrative boundary."
                    ),
                    "boundary_policy": (
                        "Explicit bounded Downtown Dubai / Business Bay research extent"
                    ),
                },
            )
        )
    if await session.get(DataSource, source_id) is None:
        session.add(
            DataSource(
                id=source_id,
                provider_name="OpenStreetMap contributors",
                dataset_name="Downtown Dubai / Business Bay bounded OSM extract",
                source_type="openstreetmap",
                source_url=prepared.source["source_url"],
                license_identifier="ODbL-1.0",
                attribution_text="© OpenStreetMap contributors — https://www.openstreetmap.org/copyright",
                collected_at=datetime.fromisoformat(prepared.source["downloaded_at"]),
                source_version=prepared.source_hash[:24],
                checksum_sha256=prepared.source_hash,
                metadata_={
                    "is_synthetic": False,
                    "original_manifest": prepared.source,
                    "original_extract_path": str(directory / "source.osm.xml"),
                    "mapping_path": str(directory / "source-sumo-db-mapping.json"),
                    "geometry_derivation": POLICY,
                },
            )
        )
    await session.flush()
    network = NetworkVersion(
        id=network_id,
        region_id=region_id,
        data_source_id=source_id,
        version_label=version,
        status="draft",
        checksum_sha256=prepared.checksum,
        artifact_uri=str(directory / "network.net.xml"),
        source_format="osm_sumo_georeferenced",
        node_count=len(prepared.nodes),
        edge_count=len(prepared.edges),
        is_validated=False,
        validation_summary={"status": "NOT_VALIDATED", "is_synthetic": False},
    )
    session.add(network)
    await session.flush()
    identifiers = {key: uuid5(network_id, f"node:{key}") for key in prepared.nodes}
    for node in prepared.nodes.values():
        session.add(
            Intersection(
                id=identifiers[node.identifier],
                network_version_id=network_id,
                source_node_id=node.source_identifier,
                sumo_node_id=node.identifier,
                location=from_shape(Point(node.coordinate), srid=4326),
                intersection_type="osm_traffic_signals"
                if node.is_signalized
                else "osm_converted_junction",
                is_signalized=node.is_signalized,
                metadata_=node.metadata,
            )
        )
    await session.flush()
    for edge in prepared.edges:
        session.add(
            RoadEdge(
                id=uuid5(network_id, f"edge:{edge.identifier}"),
                network_version_id=network_id,
                start_intersection_id=identifiers[edge.start],
                end_intersection_id=identifiers[edge.end],
                sumo_edge_id=edge.identifier,
                source_edge_id=f"osm:way:{edge.source_ids[0]}",
                name=edge.name[:200] if edge.name else None,
                road_class=edge.road_class[:64],
                geom=from_shape(edge.geometry, srid=4326),
                lane_count=edge.lanes,
                speed_limit_mps=edge.speed,
                is_one_way=edge.one_way,
                metadata_=edge.metadata,
            )
        )
    await session.flush()
    report = await validate_network(session, network_id)
    if report["status"] not in {"VALID", "VALID_WITH_WARNINGS"}:
        raise RuntimeError(f"Imported network failed bounded validation: {json.dumps(report)}")
    network.validation_summary = {
        **report,
        "is_synthetic": False,
        "geometry_derivation": POLICY,
        "omitted": prepared.omitted,
        "source_way_count": prepared.source_way_count,
        "restrictions": (
            "OSM restrictions imported where supported by netconvert; "
            "incomplete and not field verified"
        ),
        "lane_inference_count": sum(
            edge.metadata["lane_count_source"] == "inferred_by_netconvert"
            for edge in prepared.edges
        ),
    }
    network.is_validated = True
    network.status = "published"
    await session.flush()
    session.add(
        AuditEvent(
            action="import_osm_network",
            target_type="network_version",
            target_id=network_id,
            metadata_={
                "is_synthetic": False,
                "source_checksum_sha256": prepared.source_hash,
                "sumo_checksum_sha256": prepared.network_hash,
            },
        )
    )
    await session.flush()
    return {
        "created": True,
        "network_id": str(network_id),
        "region_id": str(region_id),
        "version_label": version,
        "node_count": len(prepared.nodes),
        "edge_count": len(prepared.edges),
        "validation": network.validation_summary,
    }


async def import_artifacts(directory: Path, database_url: str) -> dict[str, Any]:
    prepared = prepare_import(directory)
    infrastructure = Infrastructure(Settings(database_url=database_url))
    try:
        async with infrastructure.session() as session:
            result = await persist_import(session, prepared, directory)
    finally:
        await infrastructure.close()
    network_id = UUID(result["network_id"])
    mapping: dict[str, list[dict[str, str]]] = {}
    for edge in prepared.edges:
        for source in edge.source_ids:
            mapping.setdefault(source, []).append(
                {
                    "sumo_edge_id": edge.identifier,
                    "database_edge_id": str(uuid5(network_id, f"edge:{edge.identifier}")),
                }
            )
    mapping_path = directory / "source-sumo-db-mapping.json"
    mapping_path.write_text(
        json.dumps(
            {
                "osm_way_to_sumo_and_database_edges": mapping,
                "network_id": str(network_id),
                "not_one_to_one": True,
            },
            indent=2,
        )
        + "\n"
    )
    manifest = {
        "kind": "osm_import",
        "source_type": "openstreetmap",
        "license_identifier": "ODbL-1.0",
        "osm_sha256": prepared.source_hash,
        "sumo_network_sha256": prepared.network_hash,
        "bbox": list(prepared.bounds),
        "geometry_derivation": POLICY,
        "mapping_file": mapping_path.name,
        "mapping_sha256": hashlib.sha256(mapping_path.read_bytes()).hexdigest(),
        "osm_way_count_with_imported_edges": len(mapping),
        "source_way_count": prepared.source_way_count,
        "omitted": prepared.omitted,
        **result,
    }
    (directory / "import-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
