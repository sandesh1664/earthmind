"""Build bounded self-hosted OSM context; never fetch tiles or invent building heights."""

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, Polygon, box, mapping
from shapely.geometry.base import BaseGeometry

BBOX = (55.258, 25.180, 55.288, 25.208)
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_OUTPUT_BYTES = 12 * 1024 * 1024
MAX_FEATURES = 12_000
MAX_POSITIONS = 150_000


def explicit_height(tags: dict[str, str]) -> float | None:
    """Only an explicit metric height tag; levels are not guessed into meters."""
    value = tags.get("height", "").strip()
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(?:m)?", value)
    if not match:
        return None
    height = float(match[1])
    return height if math.isfinite(height) and 1 <= height <= 1000 else None


def _position_count(coordinates: object) -> int:
    if not isinstance(coordinates, (list, tuple)):
        return 0
    if len(coordinates) >= 2 and all(isinstance(value, (int, float)) for value in coordinates):
        return 1
    return sum(_position_count(value) for value in coordinates)


def _write_atomic(destination: Path, payload: bytes) -> None:
    """Replace one complete artifact; manifest is published only after both assets."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _feature_kind(tags: dict[str, str]) -> str | None:
    if tags.get("building", "no").lower() not in {"no", "false", "0"}:
        return "building"
    if tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
        return "water"
    if tags.get("leisure") in {"park", "garden"} or tags.get("landuse") in {
        "grass",
        "forest",
        "recreation_ground",
    }:
        return "park"
    return "road" if "highway" in tags else None


def build(source: Path, destination: Path) -> dict[str, Any]:
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Unsafe or oversized source XML")
    with source.open("rb") as input_file:
        content = input_file.read(MAX_SOURCE_BYTES + 1)
    if len(content) > MAX_SOURCE_BYTES or b"<!DOCTYPE" in content or b"<!ENTITY" in content:
        raise ValueError("Unsafe or oversized source XML")
    tree = ET.fromstring(content)
    if tree.tag != "osm":
        raise ValueError("Expected an actual OSM XML extract")
    nodes: dict[str, tuple[float, float]] = {}
    for node in tree.findall("node"):
        longitude = float(node.attrib["lon"])
        latitude = float(node.attrib["lat"])
        if not (
            math.isfinite(longitude)
            and math.isfinite(latitude)
            and -180 <= longitude <= 180
            and -90 <= latitude <= 90
        ):
            raise ValueError("OSM node has invalid geographic coordinates")
        node_id = node.attrib["id"]
        coordinates = (longitude, latitude)
        if node_id in nodes and nodes[node_id] != coordinates:
            raise ValueError("Conflicting coordinates for one OSM node identifier")
        nodes[node_id] = coordinates
    extent = box(*BBOX)
    context: list[dict[str, Any]] = []
    buildings: list[dict[str, Any]] = []
    labels = 0
    rejected_incomplete_ways = 0
    rejected_invalid_geometry = 0
    for way in tree.findall("way"):
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in way.findall("tag")}
        kind = _feature_kind(tags)
        if kind is None:
            continue
        references = [node.attrib["ref"] for node in way.findall("nd")]
        # Skipping missing individual nodes would invent new straight connections.
        if any(reference not in nodes for reference in references):
            rejected_incomplete_ways += 1
            continue
        if len(references) < 2 or len(references) > 5000:
            rejected_invalid_geometry += 1
            continue
        points = [nodes[reference] for reference in references]
        closed = len(points) >= 4 and points[0] == points[-1]
        props: dict[str, Any] = {
            "context_kind": kind,
            "elementType": "way",
            "elementId": way.attrib["id"],
            "source": "OpenStreetMap",
            "is_synthetic": False,
        }
        name = tags.get("name:en") or tags.get("name")
        if name:
            props["name"] = name[:255]
        geometry: BaseGeometry
        if kind == "road":
            # Cartography only; selectable authoritative network geometry comes from PostGIS.
            geometry = LineString(points)
            if not geometry.is_valid:
                rejected_invalid_geometry += 1
                continue
            geometry = geometry.intersection(extent)
            if geometry.is_empty or geometry.geom_type not in {"LineString", "MultiLineString"}:
                continue
            props["highway"] = tags["highway"]
        else:
            if not closed:
                rejected_invalid_geometry += 1
                continue
            geometry = Polygon(points)
            if not geometry.is_valid:
                rejected_invalid_geometry += 1
                continue
            geometry = geometry.intersection(extent)
            if geometry.is_empty or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
                continue
        feature = {
            "type": "Feature",
            "id": f"osm-way-{way.attrib['id']}",
            "geometry": mapping(geometry),
            "properties": props,
        }
        context.append(feature)
        height = explicit_height(tags) if kind == "building" else None
        if height is not None:
            building_props = {
                **props,
                "height": height,
                "height_source": "explicit_osm_height_tag_not_field_verified",
                "osm_height": tags["height"],
            }
            buildings.append({**feature, "properties": building_props})
        if (
            name
            and labels < 120
            and (
                kind in {"water", "park"}
                or (kind == "building" and height is not None)
                or (kind == "road" and tags["highway"] in {"primary", "secondary", "tertiary"})
            )
        ):
            point = geometry.representative_point()
            context.append(
                {
                    "type": "Feature",
                    "id": f"label-{way.attrib['id']}",
                    "geometry": mapping(point),
                    "properties": {**props, "context_kind": "label"},
                }
            )
            labels += 1
    if not context:
        raise ValueError("No actual geographic context in source extract")
    payloads: dict[str, bytes] = {}
    artifacts: dict[str, Any] = {}
    for filename, features in [("context.geojson", context), ("buildings.geojson", buildings)]:
        payload = (
            json.dumps(
                {"type": "FeatureCollection", "features": features},
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        positions = sum(_position_count(feature["geometry"]["coordinates"]) for feature in features)
        if (
            len(payload) > MAX_OUTPUT_BYTES
            or len(features) > MAX_FEATURES
            or positions > MAX_POSITIONS
        ):
            raise ValueError("Context exceeds local render budget")
        payloads[filename] = payload
        artifacts[filename] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "features": len(features),
            "positions": positions,
        }
    report = {
        "source": "OpenStreetMap",
        "license": "ODbL-1.0",
        "attribution": "© OpenStreetMap contributors",
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "bounds": BBOX,
        "cartographic_features": len(context),
        "explicit_height_buildings": len(buildings),
        "labels": labels,
        "rejected_incomplete_ways": rejected_incomplete_ways,
        "rejected_invalid_geometry": rejected_invalid_geometry,
        "artifacts": artifacts,
        "limitations": [
            "OSM height tags are not field verified",
            "Missing heights are not inferred; footprint remains flat",
            "Simple way polygons only; unassembled multipolygon relations omitted",
            "Cartographic roads are context, selectable network comes from PostGIS",
        ],
    }
    # All geometry/budget validation precedes writes. Clients can verify these
    # hashes and reject an interrupted publication rather than accept mixed assets.
    destination.mkdir(parents=True, exist_ok=True)
    for filename, payload in payloads.items():
        _write_atomic(destination / filename, payload)
    _write_atomic(destination / "manifest.json", (json.dumps(report, indent=2) + "\n").encode())
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
