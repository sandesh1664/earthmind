"""Isolated parser/provenance tests; live import proof is a separate real OSM run."""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from earthmind_api.osm_import import prepare_import, recorded_speed, source_way_ids, xml_document
from earthmind_api.spatial import public_feature_metadata
from pyproj import Transformer


def artifacts(directory: Path, *, tags: str = '<tag k="maxspeed" v="50"/>') -> None:
    directory.mkdir(parents=True, exist_ok=True)
    points = [(55.27, 25.19), (55.271, 25.19), (55.272, 25.191)]
    projection = Transformer.from_crs("EPSG:4326", "EPSG:32640", always_xy=True)
    projected = [projection.transform(*point) for point in points]
    nodes = "".join(f'<node id="{i}" lon="{x}" lat="{y}"/>' for i, (x, y) in enumerate(points, 1))
    source = (
        f'<osm version="0.6">{nodes}<way id="10">'
        '<nd ref="1"/><nd ref="2"/><nd ref="3"/><tag k="highway" v="residential"/>'
        f'<tag k="name" v="Stored source name"/>{tags}</way></osm>'
    )
    junctions = "".join(
        f'<junction id="{i}" x="{x}" y="{y}"/>' for i, (x, y) in enumerate(projected, 1)
    )
    roads = ""
    for i in range(2):
        first, second = projected[i], projected[i + 1]
        roads += (
            f'<edge id="10#{i}" from="{i + 1}" to="{i + 2}">'
            f'<lane id="10#{i}_0" speed="13.89" shape="{first[0]},{first[1]} '
            f'{second[0]},{second[1]}"><param key="origId" value="10"/></lane></edge>'
        )
    converted = (
        '<net><location netOffset="0,0" projParameter="+proj=utm +zone=40 '
        f'+datum=WGS84 +units=m +no_defs"/>{junctions}{roads}</net>'
    )
    (directory / "source.osm.xml").write_text(source)
    (directory / "network.net.xml").write_text(converted)
    source_hash = hashlib.sha256(source.encode()).hexdigest()
    network_hash = hashlib.sha256(converted.encode()).hexdigest()
    (directory / "source-manifest.json").write_text(
        json.dumps(
            {
                "checksum_sha256": source_hash,
                "bbox_west_south_east_north": [55.258, 25.18, 55.288, 25.208],
                "source_url": "https://overpass-api.de/api/interpreter",
                "downloaded_at": "2026-10-27T00:00:00+00:00",
            }
        )
    )
    (directory / "conversion-manifest.json").write_text(
        json.dumps({"source_checksum_sha256": source_hash, "network_checksum_sha256": network_hash})
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("unknown", None),
        ("AE:urban", None),
        ("0", None),
        ("50", 50 / 3.6),
        ("30 mph", 13.4112),
        ("80 km/h", 80 / 3.6),
    ],
)
def test_recorded_speed_never_invents_missing_limits(
    value: str | None, expected: float | None
) -> None:
    actual = recorded_speed(value)
    if expected is None:
        assert actual is None
    else:
        assert actual == pytest.approx(expected)


def test_actual_way_identifiers_are_many_to_many() -> None:
    element = ET.fromstring(
        '<edge id="10#1"><lane><param key="origID" value="10 11 -10#0 999"/></lane></edge>'
    )
    assert source_way_ids(element, {"10", "11"}) == ["10", "11"]
    assert source_way_ids(ET.fromstring('<edge id="-10#1"/>'), {"10"}) == ["10"]
    assert source_way_ids(ET.fromstring('<edge id="999"/>'), {"10"}) == []


def test_projection_connectivity_source_and_inference_are_explicit(tmp_path: Path) -> None:
    artifacts(tmp_path)
    prepared = prepare_import(tmp_path)
    assert len(prepared.nodes) == 3 and len(prepared.edges) == 2
    assert prepared.nodes["1"].coordinate == pytest.approx((55.27, 25.19))
    for edge in prepared.edges:
        assert edge.source_ids == ["10"]
        assert edge.name == "Stored source name"
        assert edge.geometry.coords[0] == prepared.nodes[edge.start].coordinate
        assert edge.geometry.coords[-1] == prepared.nodes[edge.end].coordinate
        assert edge.metadata["lane_count_source"] == "inferred_by_netconvert"
        assert edge.metadata["speed_limit_source"] == "osm"
        assert edge.speed == pytest.approx(50 / 3.6)
        assert edge.metadata["geometry_derivation"] == "sumo_lane_centerline_from_osm"
        assert edge.metadata["is_synthetic"] is False
        assert edge.metadata["sumo_identifier_verified"] is True
    assert prepared.omitted == {
        "outside_bbox": 0,
        "self_loop": 0,
        "unmapped_source": 0,
        "unsupported": 0,
    }


def test_lane_tags_are_distinguished_from_converter_assumptions(tmp_path: Path) -> None:
    artifacts(tmp_path, tags='<tag k="lanes" v="2"/><tag k="lanes:forward" v="1"/>')
    prepared = prepare_import(tmp_path)
    assert all(
        edge.metadata["lane_count_source"] == "osm_directional_tag" for edge in prepared.edges
    )
    assert all(
        edge.speed is None and edge.metadata["speed_limit_source"] == "missing"
        for edge in prepared.edges
    )


def test_changed_source_is_rejected_before_any_database_write(tmp_path: Path) -> None:
    artifacts(tmp_path)
    with (tmp_path / "source.osm.xml").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="checksum"):
        prepare_import(tmp_path)


def test_query_bounds_are_validated_before_projection(tmp_path: Path) -> None:
    artifacts(tmp_path)
    manifest = json.loads((tmp_path / "source-manifest.json").read_text())
    manifest["bbox_west_south_east_north"] = [0, 0, 1, 1]
    (tmp_path / "source-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Dubai"):
        prepare_import(tmp_path)


def test_xml_external_entity_declarations_are_rejected(tmp_path: Path) -> None:
    artifact = tmp_path / "source.osm.xml"
    artifact.write_text('<!DOCTYPE osm [<!ENTITY e SYSTEM "file:///etc/passwd">]><osm/>')
    with pytest.raises(ValueError, match="entities"):
        xml_document(artifact)


def test_public_projection_excludes_original_tags_and_private_artifact_paths() -> None:
    metadata = {
        "osm_way_id": "123",
        "osm_way_ids": ["123", "456"],
        "lane_count_source": "inferred_by_netconvert",
        "osm_maxspeed": None,
        "sumo_identifier_verified": True,
        "original_osm_tags": {"private": "not public"},
        "original_extract_path": "/private/artifact",
        "sumo_operational_speed_mps": 13.89,
        "unknown_key": "hidden",
    }
    assert public_feature_metadata(metadata) == {
        "osm_way_id": "123",
        "osm_way_ids": ["123", "456"],
        "lane_count_source": "inferred_by_netconvert",
        "osm_maxspeed": None,
        "sumo_identifier_verified": True,
    }
    assert public_feature_metadata({"osm_way_ids": ["123"] * 65}) == {}
