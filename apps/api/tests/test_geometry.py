"""Unit checks prove coordinate/complexity and metric semantics independently of SQL."""

from copy import deepcopy
from uuid import uuid4

import pytest
from earthmind_api.geometry import as_multipolygon, geodesic_area_km2, parse_bbox, validate_geometry
from earthmind_api.geospatial_models import RoadEdge
from earthmind_api.geospatial_schemas import ContainsRequest, GeometryObject, RegionCreate
from earthmind_api.network_validation import structural_report
from earthmind_api.spatial import as_geography, public_region_metadata, safe_source_url
from pydantic import ValidationError
from shapely.geometry import LineString, Point
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import dialect

POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [[55.27, 25.19], [55.28, 25.19], [55.28, 25.20], [55.27, 25.20], [55.27, 25.19]]
    ],
}


@pytest.mark.parametrize(
    "coordinates",
    [
        [181, 25],
        [55, 91],
        [float("nan"), 25],
        [55, float("inf")],
        [True, 25],
        [55, 25, 1],
        ["55", 25],
    ],
)
def test_coordinates_reject_invalid_values(coordinates: list[object]) -> None:
    with pytest.raises(ValueError):
        validate_geometry({"type": "Point", "coordinates": coordinates})


def test_polygon_closure_topology_and_unsupported_crs() -> None:
    unclosed = deepcopy(POLYGON)
    unclosed["coordinates"][0].pop()  # type: ignore[index,union-attr]
    with pytest.raises(ValueError, match="closed"):
        validate_geometry(unclosed)
    with pytest.raises(ValueError, match="Invalid"):
        validate_geometry(
            {"type": "Polygon", "coordinates": [[[55, 25], [56, 26], [56, 25], [55, 26], [55, 25]]]}
        )
    with pytest.raises(ValueError, match="CRS"):
        validate_geometry({**POLYGON, "crs": {"name": "EPSG:3857"}})
    with pytest.raises(ValueError, match="Unsupported"):
        validate_geometry({"type": "GeometryCollection", "coordinates": []})


def test_geometry_limits_and_lonlat_round_trip() -> None:
    with pytest.raises(ValueError, match="count"):
        validate_geometry(POLYGON, max_coordinates=4)
    geometry = validate_geometry(POLYGON)
    assert geometry.bounds == (55.27, 25.19, 55.28, 25.2)
    assert as_multipolygon(geometry).geom_type == "MultiPolygon"
    # A 0.01-degree square here has about one square kilometre, not 0.0001 km².
    assert 1.0 < geodesic_area_km2(geometry) < 1.2
    assert geodesic_area_km2(as_multipolygon(geometry)) == pytest.approx(
        geodesic_area_km2(geometry)
    )


@pytest.mark.parametrize(
    "bbox", ["1,2,3", "55,25,54,26", "55,25,57,26", "nan,1,2,3", "-181,0,-180,1", "0,89,1,91"]
)
def test_bbox_bounds_are_not_unbounded_or_ambiguous(bbox: str) -> None:
    with pytest.raises(ValueError):
        parse_bbox(bbox)


def test_public_schemas_reject_centroid_overrides_and_coordinate_order() -> None:
    base = {"slug": "example-region", "name": "Example", "country_code": "AE", "boundary": POLYGON}
    assert RegionCreate.model_validate(base).coordinate_order == "longitude_latitude"
    for extra in (
        {"coordinate_order": "latitude_longitude"},
        {"centroid": [25.19, 55.27]},
        {"timezone": "Not/AZone"},
    ):
        with pytest.raises(ValidationError):
            RegionCreate.model_validate({**base, **extra})
    with pytest.raises(ValidationError):
        ContainsRequest(region_id=uuid4(), point=GeometryObject.model_validate(POLYGON))


def test_private_provenance_never_serializes_implicitly() -> None:
    assert public_region_metadata(
        {"is_synthetic": True, "password": "private", "provider_key": "private"}
    ) == {"is_synthetic": True}
    assert (
        safe_source_url("https://example.org/data?api_key=private#token")
        == "https://example.org/data"
    )
    assert safe_source_url("https://user:private@example.org/data") is None
    assert safe_source_url("file:///private/data") is None
    assert safe_source_url("https://127.0.0.1/private") is None
    assert safe_source_url("https://localhost/private") is None
    assert safe_source_url("https://example.org:bad/private") is None


def topology() -> tuple[object, list[dict[str, object]], list[dict[str, object]]]:
    identifier = uuid4()
    first, second = uuid4(), uuid4()
    nodes = [
        {
            "id": first,
            "network_version_id": identifier,
            "source_node_id": "n1",
            "geometry": Point(55.27, 25.19),
            "srid": 4326,
            "metadata": {"is_synthetic": True},
        },
        {
            "id": second,
            "network_version_id": identifier,
            "source_node_id": "n2",
            "geometry": Point(55.28, 25.19),
            "srid": 4326,
            "metadata": {"is_synthetic": True},
        },
    ]
    edges = [
        {
            "id": uuid4(),
            "network_version_id": identifier,
            "sumo_edge_id": "provisional:e1",
            "start_intersection_id": first,
            "end_intersection_id": second,
            "geometry": LineString([(55.27, 25.19), (55.28, 25.19)]),
            "srid": 4326,
            "metadata": {"is_synthetic": True},
            "lane_count": 2,
            "speed_limit_mps": 10.0,
            "length_m": 1007.0,
            "road_class": "synthetic_local",
        }
    ]
    return identifier, nodes, edges


def test_validation_distinguishes_errors_warnings_and_explicit_topology() -> None:
    identifier, nodes, edges = topology()
    report = structural_report(identifier, nodes, edges)  # type: ignore[arg-type]
    assert report["status"] == "VALID"
    # A geometrically crossing line contributes no connection without endpoint references.
    extra = {
        **nodes[0],
        "id": uuid4(),
        "source_node_id": "isolated",
        "geometry": Point(55.275, 25.19),
    }
    warned = structural_report(identifier, [*nodes, extra], edges)  # type: ignore[arg-type]
    assert warned["status"] == "VALID_WITH_WARNINGS" and warned["validated"] is True
    assert warned["counts"]["isolated_nodes"] == 1
    broken = structural_report(identifier, nodes, [{**edges[0], "lane_count": 0}], outside_edges=1)  # type: ignore[arg-type]
    assert broken["status"] == "INVALID" and broken["validated"] is False
    duplicate = structural_report(identifier, nodes, [*edges, edges[0]])  # type: ignore[arg-type]
    assert duplicate["checks"]["duplicate_edges_absent"] is False


def test_validation_rejects_topology_geometry_mismatch_and_nonfinite_speed() -> None:
    identifier, nodes, edges = topology()
    mismatch = structural_report(
        identifier,
        nodes,
        [
            {
                **edges[0],
                "geometry": LineString([(55.2701, 25.19), (55.28, 25.19)]),
                "speed_limit_mps": float("inf"),
            }
        ],
    )  # type: ignore[arg-type]
    assert mismatch["checks"]["endpoints_consistent"] is False
    assert mismatch["checks"]["attributes_valid"] is False


def test_nearby_expression_has_no_typmod_that_disables_functional_index() -> None:
    statement = select(RoadEdge.id).where(
        func.ST_DWithin(
            as_geography(RoadEdge.geom),
            as_geography(func.ST_SetSRID(func.ST_Point(55.274, 25.195), 4326)),
            250,
        )
    )
    sql = str(statement.compile(dialect=dialect(), compile_kwargs={"literal_binds": True}))
    assert "CAST(road_edges.geom AS geography)" in sql
    assert "geography(GEOMETRY" not in sql
