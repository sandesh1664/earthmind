"""Real PostGIS integration: persistence invariants, spatial indexes and version safety."""

import hashlib
import json
import math
import os
from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import uuid4

import pytest
from earthmind_api.dependencies import Infrastructure
from earthmind_api.fixtures import CHECKSUM, NETWORK_ID, REGION_ID, SCENARIO_ID
from earthmind_api.geospatial_models import (
    AuditEvent,
    DemandProfile,
    Intersection,
    NetworkVersion,
    Region,
    RoadEdge,
    RunMetric,
    Scenario,
    SimulationRun,
    User,
)
from earthmind_api.seed import seed
from earthmind_api.settings import Settings
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    url = os.environ.get("EARTHMIND_TEST_DATABASE_URL")
    if not url:
        pytest.skip("EARTHMIND_TEST_DATABASE_URL must select a real migrated PostGIS database")
    infrastructure = Infrastructure(Settings(database_url=url))
    async with infrastructure.engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as value:
            try:
                await seed(value)
                yield value
            finally:
                await transaction.rollback()
    await infrastructure.close()


async def draft(session: AsyncSession) -> NetworkVersion:
    value = NetworkVersion(
        region_id=REGION_ID,
        version_label=f"test-{uuid4()}",
        status="draft",
        checksum_sha256=hashlib.sha256(uuid4().bytes).hexdigest(),
        source_format="synthetic_test",
    )
    session.add(value)
    await session.flush()
    return value


async def nodes(
    session: AsyncSession, network: NetworkVersion
) -> tuple[Intersection, Intersection]:
    values = [
        Intersection(
            network_version_id=network.id,
            source_node_id=f"test-{uuid4()}",
            location=from_shape(Point(lon, 25.195), srid=4326),
            intersection_type="synthetic_test",
            is_signalized=False,
            metadata_={"is_synthetic": True},
        )
        for lon in (55.272, 55.276)
    ]
    session.add_all(values)
    await session.flush()
    return values[0], values[1]


def edge(
    network: NetworkVersion, start: Intersection, end: Intersection, **changes: object
) -> RoadEdge:
    values: dict[str, object] = dict(
        network_version_id=network.id,
        start_intersection_id=start.id,
        end_intersection_id=end.id,
        sumo_edge_id=f"provisional:test-{uuid4()}",
        road_class="synthetic_test",
        geom=from_shape(LineString([(55.272, 25.195), (55.276, 25.195)]), srid=4326),
        lane_count=1,
        speed_limit_mps=8.0,
        is_one_way=True,
        metadata_={"is_synthetic": True},
    )
    return RoadEdge(**{**values, **changes})


async def test_seed_idempotency_geographic_derivations_and_synthetic_provenance(
    session: AsyncSession,
) -> None:
    first = await seed(session)
    second = await seed(session)
    assert first["network_id"] == second["network_id"] == str(NETWORK_ID)
    assert second["created"] is False
    assert second["nodes"] == 6 and second["edges"] == 8
    region = await session.get(Region, REGION_ID)
    assert region is not None and region.metadata_["is_synthetic"] is True
    assert 0.5 < region.area_km2 < 5
    assert region.created_at.utcoffset() == timedelta(0)
    covered = await session.scalar(
        text("SELECT ST_Covers(boundary,centroid) FROM regions WHERE id=:id"), {"id": REGION_ID}
    )
    assert covered is True
    network = await session.get(NetworkVersion, NETWORK_ID)
    assert network is not None and network.checksum_sha256 == CHECKSUM
    assert network.status == "published" and network.is_validated
    row = (
        await session.execute(
            text(
                "SELECT bool_and((metadata->>'is_synthetic')::boolean),bool_or(is_one_w"
                "ay),bool_or(NOT is_one_way),min(length_m) FROM road_edges WHERE "
                "network_version_id=:id"
            ),
            {"id": NETWORK_ID},
        )
    ).one()
    assert row[0] and row[1] and row[2] and row[3] > 10
    assert (
        await session.scalar(
            text(
                "SELECT count(*) FROM intersections WHERE network_version_id=:id AND is_signalized"
            ),
            {"id": NETWORK_ID},
        )
        == 1
    )


@pytest.mark.parametrize(
    "wkt,srid",
    [
        ("MULTIPOLYGON EMPTY", 4326),
        ("MULTIPOLYGON(((55 25,56 26,56 25,55 26,55 25)))", 4326),
        ("MULTIPOLYGON(((181 25,182 25,182 26,181 26,181 25)))", 4326),
        ("MULTIPOLYGON(((55 91,56 91,56 92,55 92,55 91)))", 4326),
        ("MULTIPOLYGON Z(((55 25 1,56 25 1,56 26 1,55 26 1,55 25 1)))", 4326),
        ("MULTIPOLYGON(((55 25,56 25,56 26,55 26,55 25)))", 3857),
        ("POINT(55 25)", 4326),
    ],
)
async def test_database_rejects_invalid_or_unsupported_geometry(
    session: AsyncSession, wkt: str, srid: int
) -> None:
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(
                text(
                    "INSERT INTO regions (slug,name,country_code,timezone,boundary) VALUES "
                    "(:slug,'synthetic test','AE','Asia/Dubai',ST_GeomFromText(:wkt,:srid))"
                ),
                {"slug": f"test-{uuid4()}", "wkt": wkt, "srid": srid},
            )


async def test_actual_indexed_bbox_contains_and_meter_distance_queries(
    session: AsyncSession,
) -> None:
    definitions = (
        await session.execute(
            text(
                "SELECT indexname,indexdef FROM pg_indexes WHERE tablename IN "
                "('regions','road_edges','intersections')"
            )
        )
    ).all()
    for expected in (
        "ix_regions_boundary_gist",
        "ix_road_edges_geom_gist",
        "ix_road_edges_geography_gist",
        "ix_intersections_location_gist",
    ):
        assert any(
            name == expected and "USING gist" in definition for name, definition in definitions
        )
    assert await session.scalar(
        text(
            "SELECT ST_Covers(boundary,ST_SetSRID(ST_Point(55.274,25.195),4326)) "
            "FROM regions WHERE id=:id"
        ),
        {"id": REGION_ID},
    )
    assert await session.scalar(
        text(
            "SELECT NOT ST_Covers(boundary,ST_SetSRID(ST_Point(0,0),4326)) FROM "
            "regions WHERE id=:id"
        ),
        {"id": REGION_ID},
    )
    # The tiny fixture naturally favors sequential scans.
    # Force a diagnostic plan to prove that its spatial index is usable.
    await session.execute(text("SET LOCAL enable_seqscan=off"))
    plan = await session.scalar(
        text(
            "EXPLAIN (FORMAT JSON) SELECT id FROM road_edges WHERE geom && "
            "ST_MakeEnvelope(55.268,25.190,55.281,25.201,4326)"
        )
    )
    assert "ix_road_edges_geom_gist" in json.dumps(plan)
    count = await session.scalar(
        text(
            "SELECT count(*) FROM road_edges WHERE network_version_id=:id AND "
            "ST_Intersects(geom,ST_MakeEnvelope(55.268,25.190,55.281,25.201,4326))"
        ),
        {"id": NETWORK_ID},
    )
    assert count == 8
    distance = await session.scalar(
        text(
            "SELECT min(ST_Distance(geom::geography,ST_SetSRID(ST_Point(55.270,25.1"
            "92),4326)::geography)) FROM road_edges WHERE network_version_id=:id "
            "AND ST_DWithin(geom::geography,ST_SetSRID(ST_Point(55.270,25.192),4326"
            ")::geography,50)"
        ),
        {"id": NETWORK_ID},
    )
    assert distance is not None and 0 <= distance < 0.001


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE network_versions SET version_label='mutated' WHERE id=:id",
        "UPDATE network_versions SET checksum_sha256=repeat('a',64) WHERE id=:id",
        "DELETE FROM network_versions WHERE id=:id",
        "UPDATE road_edges SET lane_count=lane_count+1 WHERE network_version_id=:id",
        "DELETE FROM road_edges WHERE network_version_id=:id",
        "UPDATE intersections SET is_signalized=NOT is_signalized WHERE network_version_id=:id",
        "DELETE FROM intersections WHERE network_version_id=:id",
        (
            "INSERT INTO intersections(network_version_id,source_node_id,location,i"
            "ntersection_type,is_signalized) VALUES "
            "(:id,'new-provisional',ST_SetSRID(ST_Point(55.274,25.195),4326),'synth"
            "etic_test',false)"
        ),
    ],
)
async def test_published_network_and_geometry_are_database_immutable(
    session: AsyncSession, statement: str
) -> None:
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(text(statement), {"id": NETWORK_ID})


@pytest.mark.parametrize(
    "changes",
    [
        {"lane_count": 0},
        {"speed_limit_mps": 0.0},
        {"speed_limit_mps": float("inf")},
        {"speed_limit_mps": float("nan")},
        {"geom": from_shape(LineString(), srid=4326)},
    ],
)
async def test_edge_numeric_and_geometry_constraints(
    session: AsyncSession, changes: dict[str, object]
) -> None:
    network = await draft(session)
    start, end = await nodes(session, network)
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            session.add(edge(network, start, end, **changes))
            await session.flush()


async def test_explicit_topology_and_scenario_network_foreign_keys(session: AsyncSession) -> None:
    first = await draft(session)
    start, end = await nodes(session, first)
    second = await draft(session)
    alien, _ = await nodes(session, second)
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(edge(first, start, alien))
            await session.flush()
    profile = DemandProfile(
        network_version_id=second.id,
        name="synthetic test",
        seed=1,
        profile_type="synthetic",
        config={"is_synthetic": True},
    )
    session.add(profile)
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                Scenario(
                    network_version_id=first.id,
                    demand_profile_id=profile.id,
                    name="invalid cross-version fixture",
                    description="test only",
                    duration_seconds=60,
                    config={},
                )
            )
            await session.flush()
    value = edge(first, start, end)
    session.add(value)
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(edge(first, start, end, sumo_edge_id=value.sumo_edge_id))
            await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                NetworkVersion(
                    region_id=uuid4(),
                    version_label="missing-region",
                    checksum_sha256="a" * 64,
                    source_format="synthetic_test",
                )
            )
            await session.flush()


async def test_secrets_plaintext_passwords_and_unknown_roles_rejected(
    session: AsyncSession,
) -> None:
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                User(
                    email="test@example.invalid", password_hash="plaintext-test-only", role="viewer"
                )
            )
            await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                User(
                    email="role-test@example.invalid",
                    password_hash="$scrypt$test-only",
                    role="owner",
                )
            )
            await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                AuditEvent(
                    action="test",
                    target_type="fixture",
                    target_id=REGION_ID,
                    metadata_={"nested": {"password": "must-not-store"}},
                )
            )
            await session.flush()


async def test_strict_run_transitions_and_finite_metrics(session: AsyncSession) -> None:
    run = SimulationRun(scenario_id=SCENARIO_ID, status="queued", seed=1, input_sha256="b" * 64)
    session.add(run)
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text("UPDATE simulation_runs SET status='succeeded' WHERE id=:id"), {"id": run.id}
            )
    await session.execute(
        text(
            "UPDATE simulation_runs SET "
            "status='running',engine_version='synthetic-test-contract' WHERE id=:id"
        ),
        {"id": run.id},
    )
    await session.execute(
        text("UPDATE simulation_runs SET status='succeeded' WHERE id=:id"), {"id": run.id}
    )
    await session.refresh(run)
    assert run.started_at is not None and run.finished_at is not None
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text("UPDATE simulation_runs SET status='running' WHERE id=:id"), {"id": run.id}
            )
    for value in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    RunMetric(
                        run_id=run.id,
                        metric_name="synthetic_constraint_probe",
                        aggregation="test_only",
                        value=value,
                        unit="none",
                    )
                )
                await session.flush()


async def test_restricted_delete_and_transaction_rollback(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(text("DELETE FROM regions WHERE id=:id"), {"id": REGION_ID})
    network = await draft(session)
    original = network.version_label
    with pytest.raises(RuntimeError):
        async with session.begin_nested():
            network.version_label = "must-rollback"
            await session.flush()
            raise RuntimeError("deliberate transaction rollback")
    await session.refresh(network)
    assert network.version_label == original


@pytest.mark.parametrize("column", ["started_at", "finished_at"])
async def test_queued_run_same_state_timestamp_tampering_rejected(
    session: AsyncSession, column: str
) -> None:
    """A status-preserving update must not make an unexecuted contract appear executed."""
    run = SimulationRun(scenario_id=SCENARIO_ID, status="queued", seed=1, input_sha256="d" * 64)
    session.add(run)
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text(f"UPDATE simulation_runs SET {column}=clock_timestamp() WHERE id=:id"),
                {"id": run.id},
            )


@pytest.mark.parametrize("kind", ["region", "edge"])
async def test_database_vertex_budget_matches_public_serialization(
    session: AsyncSession, kind: str
) -> None:
    """A valid but oversized persisted feature must not break public GeoJSON output."""
    if kind == "region":
        ring = [
            (
                55.274 + 0.0002 * math.cos(index * 2 * math.pi / 5000),
                25.195 + 0.0002 * math.sin(index * 2 * math.pi / 5000),
            )
            for index in range(5000)
        ]
        ring.append(ring[0])
        geometry = MultiPolygon([Polygon(ring)])
        assert geometry.is_valid and len(ring) == 5001
        value = Region(
            slug=f"vertex-budget-{uuid4()}",
            name="Synthetic vertex budget test",
            country_code="AE",
            timezone="Asia/Dubai",
            boundary=from_shape(geometry, srid=4326),
            metadata_={"is_synthetic": True},
        )
    else:
        network = await draft(session)
        start, end = await nodes(session, network)
        geometry_line = LineString(
            [(55.272 + index * 0.004 / 5000, 25.195) for index in range(5001)]
        )
        assert geometry_line.is_valid and len(geometry_line.coords) == 5001
        value = edge(network, start, end, geom=from_shape(geometry_line, srid=4326))
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(value)
            await session.flush()
