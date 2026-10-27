"""Isolated OSM cartography validation; this is not proof of a downloaded dataset."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

script = Path(__file__).resolve().parents[3] / "scripts/build_osm_context.py"
spec = importlib.util.spec_from_file_location("earthmind_context_builder_test", script)
assert spec is not None and spec.loader is not None
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

NODES = (
    "<node id='1' lon='55.270' lat='25.190'/>"
    "<node id='2' lon='55.271' lat='25.190'/>"
    "<node id='3' lon='55.271' lat='25.191'/>"
    "<node id='4' lon='55.270' lat='25.191'/>"
)
POLYGON = "<nd ref='1'/><nd ref='2'/><nd ref='3'/><nd ref='4'/><nd ref='1'/>"
ROAD = "<way id='100'><nd ref='1'/><nd ref='2'/><tag k='highway' v='primary'/></way>"


def source_file(tmp_path: Path, ways: str, nodes: str = NODES) -> Path:
    path = tmp_path / "unit-input.osm.xml"
    path.write_text(f"<osm version='0.6'>{nodes}{ways}</osm>")
    return path


@pytest.mark.parametrize(
    ("tags", "height"),
    [
        ({"height": "828"}, 828),
        ({"height": " 42.5 m "}, 42.5),
        ({"height": "45 ft"}, None),
        ({"height": "12;14"}, None),
        ({"building:levels": "80"}, None),
        ({"height": "nan"}, None),
        ({"height": "inf"}, None),
        ({"height": "-12"}, None),
        ({"height": "1500"}, None),
    ],
)
def test_only_explicit_bounded_metric_height_is_used(
    tags: dict[str, str], height: float | None
) -> None:
    assert builder.explicit_height(tags) == height


def test_missing_height_stays_flat_building_no_is_omitted_and_hashes_match(tmp_path: Path) -> None:
    source = source_file(
        tmp_path,
        f"<way id='101'>{POLYGON}<tag k='building' v='yes'/><tag k='height' v='40 m'/></way>"
        f"<way id='102'>{POLYGON}<tag k='building' v='yes'/>"
        "<tag k='building:levels' v='30'/></way>"
        f"<way id='103'>{POLYGON}<tag k='building' v='no'/><tag k='height' v='60'/></way>",
    )
    destination = tmp_path / "output"
    report = builder.build(source, destination)
    context = json.loads((destination / "context.geojson").read_text())
    buildings = json.loads((destination / "buildings.geojson").read_text())
    assert {feature["id"] for feature in context["features"]} == {"osm-way-101", "osm-way-102"}
    assert len(buildings["features"]) == 1
    assert buildings["features"][0]["properties"]["height"] == 40
    assert report["explicit_height_buildings"] == 1
    assert report["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    for name, artifact in report["artifacts"].items():
        content = (destination / name).read_bytes()
        assert artifact["sha256"] == hashlib.sha256(content).hexdigest()
        assert artifact["bytes"] == len(content)
        assert artifact["positions"] > 0
    assert report["license"] == "ODbL-1.0"
    assert report["bounds"] == builder.BBOX


def test_missing_node_references_reject_whole_way_instead_of_bridging(tmp_path: Path) -> None:
    source = source_file(
        tmp_path,
        ROAD + "<way id='201'><nd ref='1'/><nd ref='missing'/><nd ref='2'/>"
        "<tag k='highway' v='residential'/></way>",
    )
    destination = tmp_path / "output"
    report = builder.build(source, destination)
    features = json.loads((destination / "context.geojson").read_text())["features"]
    assert [feature["id"] for feature in features] == ["osm-way-100"]
    assert report["rejected_incomplete_ways"] == 1


def test_invalid_polygon_and_degenerate_line_are_rejected(tmp_path: Path) -> None:
    source = source_file(
        tmp_path,
        ROAD + "<way id='202'><nd ref='1'/><nd ref='3'/><nd ref='2'/><nd ref='4'/><nd ref='1'/>"
        "<tag k='building' v='yes'/><tag k='height' v='40'/></way>"
        "<way id='203'><nd ref='1'/><nd ref='1'/><tag k='highway' v='residential'/></way>",
    )
    report = builder.build(source, tmp_path / "output")
    assert report["rejected_invalid_geometry"] == 2
    assert report["explicit_height_buildings"] == 0
    assert report["cartographic_features"] == 1


@pytest.mark.parametrize("longitude", ["nan", "inf", "181"])
def test_nonfinite_and_out_of_range_coordinates_are_rejected(
    tmp_path: Path, longitude: str
) -> None:
    source = source_file(tmp_path, ROAD, NODES.replace("lon='55.270'", f"lon='{longitude}'", 1))
    with pytest.raises(ValueError, match="invalid geographic"):
        builder.build(source, tmp_path / "output")


def test_source_entities_and_conflicting_coordinates_are_rejected(tmp_path: Path) -> None:
    source = source_file(tmp_path, ROAD)
    source.write_text("<!DOCTYPE osm [<!ENTITY secret SYSTEM 'file:///etc/passwd'>]><osm/>")
    with pytest.raises(ValueError, match="Unsafe"):
        builder.build(source, tmp_path / "output")
    source = source_file(tmp_path, ROAD, NODES + "<node id='1' lon='55.27' lat='25.195'/>")
    with pytest.raises(ValueError, match="Conflicting coordinates"):
        builder.build(source, tmp_path / "output")


def test_budget_failure_does_not_publish_or_modify_prior_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = source_file(tmp_path, ROAD)
    destination = tmp_path / "output"
    builder.build(source, destination)
    before = {path.name: path.read_bytes() for path in destination.iterdir()}
    monkeypatch.setattr(builder, "MAX_OUTPUT_BYTES", 1)
    with pytest.raises(ValueError, match="render budget"):
        builder.build(source, destination)
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == before
