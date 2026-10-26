"""Record real schema/index/fixture observations; small-fixture plans are not benchmarks."""

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import psycopg
from database_checks import database_url
from earthmind_api.geospatial_models import RoadEdge
from earthmind_api.spatial import as_geography
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Dialect

REQUIRED_TABLES = {
    "users",
    "regions",
    "data_sources",
    "network_versions",
    "road_edges",
    "intersections",
    "demand_profiles",
    "scenarios",
    "scenario_interventions",
    "simulation_runs",
    "run_metrics",
    "run_artifacts",
    "audit_events",
}


def index_names(node: dict[str, Any]) -> set[str]:
    names = {node["Index Name"]} if "Index Name" in node else set()
    for child in node.get("Plans", []):
        names.update(index_names(child))
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/evidence/m02/postgis-inspection.json")
    )
    arguments = parser.parse_args()
    with psycopg.connect(database_url(), connect_timeout=3) as connection:
        version = connection.execute("SELECT version(),PostGIS_Full_Version()").fetchone()
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
        ]
        if not REQUIRED_TABLES.issubset(tables):
            raise RuntimeError(f"Required M02 tables are missing: {REQUIRED_TABLES - set(tables)}")
        geometries = list(
            connection.execute(
                "SELECT f_table_name,f_geometry_column,coord_dimension,srid,type "
                "FROM geometry_columns "
                "WHERE f_table_name IN ('regions','road_edges','intersections') "
                "ORDER BY f_table_name,f_geometry_column"
            )
        )
        if len(geometries) != 4 or any(row[2] != 2 or row[3] != 4326 for row in geometries):
            raise RuntimeError("Stored spatial columns must all be 2D EPSG:4326")
        indexes = list(
            connection.execute(
                "SELECT tablename,indexname,indexdef FROM pg_indexes "
                "WHERE tablename IN ('regions','road_edges','intersections') ORDER BY indexname"
            )
        )
        fixture = connection.execute(
            "SELECT area_km2,ST_AsGeoJSON(boundary)::jsonb,ST_AsGeoJSON(centroid)::jsonb, "
            "ST_IsValid(boundary),ST_Covers(boundary,centroid) FROM regions WHERE slug=%s",
            ("dubai-downtown-demo",),
        ).fetchone()
        if fixture is None or not fixture[3] or not fixture[4]:
            raise RuntimeError("Synthetic region geometry/representative centroid is invalid")
        bbox_sql = (
            "SELECT id FROM road_edges WHERE "
            "geom && ST_MakeEnvelope(55.273,25.194,55.275,25.196,4326) AND "
            "ST_Intersects(geom,ST_MakeEnvelope(55.273,25.194,55.275,25.196,4326))"
        )
        # Use the service's exact geography cast so typmod/index mismatches are observable.
        point = as_geography(func.ST_SetSRID(func.ST_MakePoint(55.2742, 25.195), 4326))
        query = select(RoadEdge.id).where(func.ST_DWithin(as_geography(RoadEdge.geom), point, 100))
        nearby_sql = str(
            query.compile(
                dialect=cast(Callable[[], Dialect], postgresql.dialect)(),
                compile_kwargs={"literal_binds": True},
            )
        )
        plans: dict[str, Any] = {}
        for name, statement, required_index in (
            ("bbox", bbox_sql, "ix_road_edges_geom_gist"),
            ("nearby_meters", nearby_sql, "ix_road_edges_geography_gist"),
        ):
            connection.execute("SET LOCAL enable_seqscan=on")
            default = connection.execute(
                "EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + statement
            ).fetchone()
            connection.execute("SET LOCAL enable_seqscan=off")
            forced = connection.execute(
                "EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + statement
            ).fetchone()
            if default is None or forced is None:
                raise RuntimeError("EXPLAIN returned no observations")
            default_plan, forced_plan = default[0][0], forced[0][0]
            used = index_names(forced_plan["Plan"])
            if required_index not in used:
                raise RuntimeError(
                    f"Actual spatial query did not use expected index {required_index}"
                )
            plans[name] = {
                "query": statement,
                "default": default_plan,
                "forced": forced_plan,
                "forced_index_names": sorted(used),
                "interpretation": (
                    "Forced index eligibility demonstration on eight synthetic rows; "
                    "not a production benchmark"
                ),
            }
        result = {
            "database_versions": version,
            "tables": tables,
            "required_tables": sorted(REQUIRED_TABLES),
            "geometry_columns": geometries,
            "indexes": indexes,
            "fixture": {"area_km2": fixture[0], "geometry": fixture[1], "centroid": fixture[2]},
            "plans": plans,
        }
    destination = arguments.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "required_tables": len(REQUIRED_TABLES),
                "geometry_columns": len(geometries),
                "area_km2": fixture[0],
                "plans": {
                    name: {
                        "indexes": plan["forced_index_names"],
                        "observed_execution_ms": plan["forced"]["Execution Time"],
                    }
                    for name, plan in plans.items()
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
