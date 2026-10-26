"""Real PostGIS-backed HTTP tests; not counted as mocked integration proof."""

import json
import os
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
from earthmind_api.fixtures import NETWORK_ID, REGION_ID
from earthmind_api.geospatial_models import AuditEvent, Region, RoadEdge
from earthmind_api.main import create_app
from earthmind_api.settings import Settings
from earthmind_api.spatial import as_geography
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import dialect

pytestmark = pytest.mark.integration
TOKEN = "integration-only-development-token-32-characters"


@pytest.fixture
async def geo_client() -> AsyncIterator[httpx.AsyncClient]:
    url = os.environ.get("EARTHMIND_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set EARTHMIND_TEST_DATABASE_URL to the actual migrated/seeded database")
    application = create_app(Settings(database_url=url, dev_write_token=TOKEN))
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            yield client


async def test_every_read_endpoint_and_geojson_are_real(geo_client: httpx.AsyncClient) -> None:
    regions = await geo_client.get("/api/v1/regions")
    assert regions.status_code == 200
    region = next(item for item in regions.json()["items"] if item["id"] == str(REGION_ID))
    assert region["slug"] == "dubai-downtown-demo" and region["metadata"]["is_synthetic"] is True
    assert (
        region["area_km2"] > 0
        and 55 < region["centroid"][0] < 56
        and 25 < region["centroid"][1] < 26
    )
    detail = await geo_client.get(f"/api/v1/regions/{REGION_ID}")
    assert detail.status_code == 200 and detail.json() == region
    boundary = await geo_client.get(f"/api/v1/regions/{REGION_ID}/geojson")
    assert boundary.status_code == 200 and boundary.json()["geometry"]["type"] == "MultiPolygon"
    assert boundary.json()["properties"]["is_synthetic"] is True
    networks = await geo_client.get("/api/v1/networks", params={"region_id": str(REGION_ID)})
    assert networks.status_code == 200
    network = next(item for item in networks.json()["items"] if item["id"] == str(NETWORK_ID))
    assert network["node_count"] == 6 and network["edge_count"] >= 8
    assert network["is_synthetic"] is True and len(network["bounds"]) == 4
    assert (await geo_client.get(f"/api/v1/networks/{NETWORK_ID}")).json() == network
    edge_response = await geo_client.get(
        f"/api/v1/networks/{NETWORK_ID}/edges",
        params={"bbox": ",".join(map(str, region["bounds"]))},
    )
    assert edge_response.status_code == 200
    edges = edge_response.json()
    assert edges["type"] == "FeatureCollection" and edges["total"] >= 8
    assert all(
        feature["geometry"]["type"] == "LineString" and feature["properties"]["is_synthetic"]
        for feature in edges["features"]
    )
    node_response = await geo_client.get(
        f"/api/v1/networks/{NETWORK_ID}/intersections",
        params={"polygon": json.dumps(boundary.json()["geometry"])},
    )
    assert node_response.status_code == 200 and node_response.json()["total"] == 6
    report = await geo_client.get(f"/api/v1/networks/{NETWORK_ID}/validation")
    assert report.status_code == 200 and report.json()["status"] in {"VALID", "VALID_WITH_WARNINGS"}
    assert report.json()["validated"] is True
    sources = await geo_client.get("/api/v1/data-sources")
    assert sources.status_code == 200 and sources.json()["total"] >= 1
    source_id = network["data_source_id"]
    source = await geo_client.get(f"/api/v1/data-sources/{source_id}")
    assert source.status_code == 200 and source.json()["is_synthetic"] is True
    assert source.json()["license_identifier"] and "metadata" not in source.json()


async def test_spatial_contains_boundary_and_nearby_meters(geo_client: httpx.AsyncClient) -> None:
    region = (await geo_client.get(f"/api/v1/regions/{REGION_ID}")).json()
    centroid = region["centroid"]
    response = await geo_client.post(
        "/api/v1/geo/contains",
        json={"region_id": str(REGION_ID), "point": {"type": "Point", "coordinates": centroid}},
    )
    assert response.status_code == 200 and response.json()["contains"] is True
    west, south, _east, _north = region["bounds"]
    response = await geo_client.post(
        "/api/v1/geo/contains",
        json={
            "region_id": str(REGION_ID),
            "point": {"type": "Point", "coordinates": [west, south]},
        },
    )
    assert response.status_code == 200 and response.json()["contains"] is True
    validated = await geo_client.post(
        "/api/v1/geo/validate", json={"geometry": {"type": "Point", "coordinates": centroid}}
    )
    assert validated.status_code == 200 and validated.json()["srid"] == 4326
    nearby = await geo_client.get(
        "/api/v1/geo/nearby-edges",
        params={
            "longitude": centroid[0],
            "latitude": centroid[1],
            "radius_m": 2000,
            "network_id": str(NETWORK_ID),
        },
    )
    assert nearby.status_code == 200 and nearby.json()["total"] >= 1
    distances = [feature["properties"]["distance_m"] for feature in nearby.json()["features"]]
    assert distances == sorted(distances) and all(0 <= distance <= 2000 for distance in distances)
    outside = await geo_client.get(
        "/api/v1/geo/nearby-edges", params={"longitude": 0, "latitude": 0, "radius_m": 10}
    )
    assert outside.status_code == 200 and outside.json()["total"] == 0


async def test_bounded_validation_missing_resources_and_unauthorized_write(
    geo_client: httpx.AsyncClient,
) -> None:
    for path in ("regions", "networks", "data-sources"):
        assert (await geo_client.get(f"/api/v1/{path}/{uuid4()}")).status_code == 404
        assert (await geo_client.get(f"/api/v1/{path}?limit=101")).status_code == 422
    assert (
        await geo_client.get(f"/api/v1/networks/{NETWORK_ID}/edges?bbox=0,0,10,10")
    ).status_code == 422
    oversized_polygon = {
        "type": "Polygon",
        "coordinates": [[[-170, -80], [170, -80], [170, 80], [-170, 80], [-170, -80]]],
    }
    assert (
        await geo_client.get(
            f"/api/v1/networks/{NETWORK_ID}/intersections",
            params={"polygon": json.dumps(oversized_polygon)},
        )
    ).status_code == 422
    assert (
        await geo_client.get("/api/v1/geo/nearby-edges?longitude=55&latitude=91")
    ).status_code == 422
    assert (
        await geo_client.get("/api/v1/geo/nearby-edges?longitude=55&latitude=25&radius_m=5001")
    ).status_code == 422
    assert (await geo_client.get("/api/v1/regions?offset=100001")).status_code == 422
    assert (await geo_client.get("/api/v1/regions?offset=100000")).json()["items"] == []
    payload = {
        "slug": f"unauthorized-{uuid4().hex}",
        "name": "Test only",
        "country_code": "AE",
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [[55.27, 25.19], [55.28, 25.19], [55.28, 25.20], [55.27, 25.20], [55.27, 25.19]]
            ],
        },
    }
    assert (await geo_client.post("/api/v1/regions", json=payload)).status_code == 403
    assert (
        await geo_client.post(
            "/api/v1/regions", json=payload, headers={"X-Earthmind-Dev-Token": "wrong"}
        )
    ).status_code == 403
    malformed = await geo_client.post(
        "/api/v1/geo/validate", json={"geometry": {"type": "Point", "coordinates": [181, 25]}}
    )
    assert malformed.status_code == 422 and "181" not in malformed.text


async def test_authorized_region_creation_duplicate_conflict_and_cleanup(
    geo_client: httpx.AsyncClient,
) -> None:
    payload = {
        "slug": f"test-only-{uuid4().hex}",
        "name": "Integration test only",
        "country_code": "AE",
        "metadata": {"is_synthetic": True, "private_provider_secret": "must-not-expose"},
        "boundary": {
            "type": "Polygon",
            "coordinates": [
                [[55.27, 25.19], [55.28, 25.19], [55.28, 25.20], [55.27, 25.20], [55.27, 25.19]]
            ],
        },
    }
    created_id = None
    try:
        created = await geo_client.post(
            "/api/v1/regions", json=payload, headers={"X-Earthmind-Dev-Token": TOKEN}
        )
        assert created.status_code == 201, created.text
        created_id = created.json()["id"]
        assert created.json()["area_km2"] > 1 and "private_provider_secret" not in created.text
        duplicate = await geo_client.post(
            "/api/v1/regions", json=payload, headers={"X-Earthmind-Dev-Token": TOKEN}
        )
        assert duplicate.status_code == 409 and "IntegrityError" not in duplicate.text
    finally:
        if created_id:
            infrastructure = geo_client._transport.app.state.infrastructure  # type: ignore[attr-defined]
            async with infrastructure.session() as session:
                await session.execute(delete(AuditEvent).where(AuditEvent.target_id == created_id))
                await session.execute(delete(Region).where(Region.id == created_id))


async def test_validation_budget_does_not_fabricate_uncomputed_graph_counts(
    geo_client: httpx.AsyncClient,
) -> None:
    application = geo_client._transport.app  # type: ignore[attr-defined]
    original = application.state.settings
    application.state.settings = original.model_copy(update={"geo_max_validation_features": 10})
    try:
        response = await geo_client.get(f"/api/v1/networks/{NETWORK_ID}/validation")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "NOT_VALIDATED" and body["validated"] is False
        assert body["counts"]["nodes"] == 6 and body["counts"]["edges"] == 8
        assert body["counts"]["components"] is None
        assert body["counts"]["isolated_nodes"] is None
    finally:
        application.state.settings = original


async def test_nearby_service_cast_uses_its_functional_geography_index(
    geo_client: httpx.AsyncClient,
) -> None:
    infrastructure = geo_client._transport.app.state.infrastructure  # type: ignore[attr-defined]
    async with infrastructure.session() as session:
        # Tiny fixtures normally favor sequential scans. This tests index eligibility,
        # not a representative production performance benchmark.
        await session.execute(text("SET LOCAL enable_seqscan=off"))
        statement = select(RoadEdge.id).where(
            func.ST_DWithin(
                as_geography(RoadEdge.geom),
                as_geography(func.ST_SetSRID(func.ST_Point(55.274, 25.195), 4326)),
                250,
            )
        )
        sql = str(statement.compile(dialect=dialect(), compile_kwargs={"literal_binds": True}))
        plan = await session.scalar(text("EXPLAIN (ANALYZE, FORMAT JSON) " + sql))
        assert "ix_road_edges_geography_gist" in json.dumps(plan)


async def test_coordinate_budget_prevents_large_geometry_graph_materialization(
    geo_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = geo_client._transport.app  # type: ignore[attr-defined]
    original = application.state.settings
    # Fixture: six Point coordinates plus sixteen coordinates across eight lines.
    # Feature count (14) is below its budget; coordinate count (22) exceeds ten.
    application.state.settings = original.model_copy(update={"geo_max_validation_coordinates": 10})

    def reject_geometry_materialization(_geometry: object) -> None:
        raise AssertionError("Coordinate budget must run before Python geometry conversion")

    monkeypatch.setattr(
        "earthmind_api.network_validation.to_shape", reject_geometry_materialization
    )
    try:
        response = await geo_client.get(f"/api/v1/networks/{NETWORK_ID}/validation")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "NOT_VALIDATED" and body["validated"] is False
        assert body["checks"] == {}
        assert "coordinate budget" in body["warnings"][0]
        assert body["counts"] == {
            "nodes": 6,
            "edges": 8,
            "components": None,
            "isolated_nodes": None,
        }
    finally:
        application.state.settings = original
