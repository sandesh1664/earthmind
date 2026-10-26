"""Create a clearly synthetic QA dataset, run real browser observations, remove only owned rows."""

import asyncio
import hashlib
import json
import math
import os
import subprocess
from datetime import UTC, datetime
from uuid import UUID, uuid4

from database_checks import database_url
from earthmind_api.dependencies import Infrastructure
from earthmind_api.geospatial_models import (
    DataSource,
    Intersection,
    NetworkVersion,
    Region,
    RoadEdge,
)
from earthmind_api.settings import Settings
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from sqlalchemy import delete, select


async def create_fixture() -> tuple[UUID, UUID, UUID]:
    infrastructure = Infrastructure(Settings(database_url=database_url()))
    try:
        async with infrastructure.session() as session:
            marker = uuid4().hex[:12]
            positions = [
                (
                    55.274 + 0.003 * math.cos(index * 2 * math.pi / 300),
                    25.195 + 0.002 * math.sin(index * 2 * math.pi / 300),
                )
                for index in range(300)
            ]
            checksum = hashlib.sha256(json.dumps(positions).encode()).hexdigest()
            region = Region(
                slug=f"m03-qa-{marker}",
                name="M03 temporary synthetic rendering benchmark",
                country_code="AE",
                emirate="Dubai",
                timezone="Asia/Dubai",
                boundary=from_shape(
                    MultiPolygon(
                        [
                            Polygon(
                                [
                                    (55.269, 25.191),
                                    (55.279, 25.191),
                                    (55.279, 25.199),
                                    (55.269, 25.199),
                                    (55.269, 25.191),
                                ]
                            )
                        ]
                    ),
                    srid=4326,
                ),
                metadata_={
                    "is_synthetic": True,
                    "description": "Temporary QA-only geometry; not observed roads",
                },
            )
            source = DataSource(
                provider_name="EARTHMIND QA",
                dataset_name="M03 temporary 300-road synthetic benchmark",
                source_type="synthetic",
                source_url=None,
                license_identifier="LicenseRef-EARTHMIND-Proprietary-Synthetic",
                attribution_text=(
                    "Project-generated temporary QA geometry; no real-world street claim."
                ),
                collected_at=datetime.now(UTC),
                source_version="m03-qa-300",
                checksum_sha256=checksum,
                metadata_={"is_synthetic": True, "purpose": "temporary rendering verification"},
            )
            session.add_all([region, source])
            await session.flush()
            network = NetworkVersion(
                region_id=region.id,
                data_source_id=source.id,
                version_label="m03-qa-300",
                checksum_sha256=checksum,
                status="draft",
                source_format="synthetic_qa",
                node_count=300,
                edge_count=300,
                validation_summary={"status": "NOT_VALIDATED", "is_synthetic": True},
            )
            session.add(network)
            await session.flush()
            nodes = [
                Intersection(
                    network_version_id=network.id,
                    source_node_id=f"benchmark:n{index:03}",
                    location=from_shape(Point(position), srid=4326),
                    intersection_type="synthetic_benchmark",
                    is_signalized=False,
                    metadata_={"is_synthetic": True},
                )
                for index, position in enumerate(positions)
            ]
            session.add_all(nodes)
            await session.flush()
            session.add_all(
                [
                    RoadEdge(
                        network_version_id=network.id,
                        start_intersection_id=nodes[index].id,
                        end_intersection_id=nodes[(index + 1) % 300].id,
                        sumo_edge_id=f"provisional:benchmark-e{index:03}",
                        source_edge_id=f"synthetic:benchmark-e{index:03}",
                        name=f"Synthetic QA link {index:03}",
                        road_class="synthetic_benchmark",
                        geom=from_shape(
                            LineString([positions[index], positions[(index + 1) % 300]]), srid=4326
                        ),
                        lane_count=1,
                        speed_limit_mps=8.0,
                        is_one_way=True,
                        metadata_={"is_synthetic": True, "sumo_identifier_verified": False},
                    )
                    for index in range(300)
                ]
            )
            await session.flush()
            return region.id, network.id, source.id
    finally:
        await infrastructure.close()


async def cleanup(region_id: UUID, network_id: UUID, source_id: UUID) -> None:
    infrastructure = Infrastructure(Settings(database_url=database_url()))
    try:
        async with infrastructure.session() as session:
            network = await session.scalar(
                select(NetworkVersion).where(NetworkVersion.id == network_id)
            )
            if (
                network is None
                or network.region_id != region_id
                or network.data_source_id != source_id
                or network.status != "draft"
                or network.version_label != "m03-qa-300"
            ):
                raise RuntimeError(
                    "QA ownership changed; refusing cleanup of non-owned research records"
                )
            await session.execute(delete(RoadEdge).where(RoadEdge.network_version_id == network_id))
            await session.execute(
                delete(Intersection).where(Intersection.network_version_id == network_id)
            )
            await session.execute(delete(NetworkVersion).where(NetworkVersion.id == network_id))
            await session.execute(delete(Region).where(Region.id == region_id))
            await session.execute(delete(DataSource).where(DataSource.id == source_id))
        print("Removed only temporary QA network/nodes/roads/region/source; M02 fixture preserved")
    finally:
        await infrastructure.close()


def main() -> None:
    ids = asyncio.run(create_fixture())
    try:
        result = subprocess.run(
            ["npx", "playwright", "test", "--config", "playwright.performance.config.ts"],
            cwd="apps/web",
            check=False,
            env={
                **os.environ,
                "EARTHMIND_CITY_BENCHMARK_REGION_ID": str(ids[0]),
                "EARTHMIND_CITY_BENCHMARK_NETWORK_ID": str(ids[1]),
            },
        )
        result.check_returncode()
    finally:
        asyncio.run(cleanup(*ids))


if __name__ == "__main__":
    main()
