"""Bounded structural validation using explicit graph endpoints, never line crossings."""

import math
from collections.abc import Sequence
from typing import Any
from typing import cast as type_cast
from uuid import UUID

import networkx as nx
from fastapi import HTTPException
from geoalchemy2 import Geography
from geoalchemy2.shape import to_shape
from pyproj import Geod
from shapely.geometry import LineString, Point
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from earthmind_api.geospatial_models import Intersection, NetworkVersion, Region, RoadEdge
from earthmind_api.settings import Settings

SEMANTICS = (
    "VALID has no findings. VALID_WITH_WARNINGS passes integrity checks but has structural or "
    "metadata warnings. INVALID has integrity errors. NOT_VALIDATED exceeds the bounded "
    "feature or coordinate validation budget. Synthetic topology is not evidence of real-world "
    "network accuracy."
)


def geographic_bounds_valid(geometry: Any) -> bool:
    bounds = geometry.bounds
    return (
        len(bounds) == 4
        and all(math.isfinite(value) for value in bounds)
        and (-180 <= bounds[0] <= bounds[2] <= 180 and -90 <= bounds[1] <= bounds[3] <= 90)
    )


def structural_report(
    network_id: UUID,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    boundary_tolerance_m: float = 5.0,
    outside_edges: int = 0,
    expected_nodes: int | None = None,
    expected_edges: int | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks = {
        "nonempty": bool(nodes and edges),
        "geometry_valid": True,
        "identifiers_unique": True,
        "references_consistent": True,
        "attributes_valid": True,
        "metadata_complete": True,
        "connectivity_valid": True,
        "region_coverage": outside_edges == 0,
        "endpoints_consistent": True,
        "duplicate_edges_absent": True,
        "counts_consistent": True,
    }
    if not checks["nonempty"]:
        errors.append("Network requires at least one node and one road edge")
    node_ids = {str(node["id"]) for node in nodes}
    if len(node_ids) != len(nodes):
        checks["identifiers_unique"] = False
    source_nodes = [node["source_node_id"] for node in nodes]
    edge_ids = [edge["sumo_edge_id"] for edge in edges]
    if len(set(source_nodes)) != len(source_nodes) or len(set(edge_ids)) != len(edge_ids):
        checks["identifiers_unique"] = False
    if not checks["identifiers_unique"]:
        errors.append("Duplicate network node or provisional edge identifiers")
    graph: nx.Graph[str] = nx.Graph()
    graph.add_nodes_from(node_ids)
    positions: dict[str, Point] = {}
    for node in nodes:
        if str(node["network_version_id"]) != str(network_id):
            checks["references_consistent"] = False
        geometry = node.get("geometry")
        if (
            not isinstance(geometry, Point)
            or geometry.is_empty
            or not geometry.is_valid
            or not geographic_bounds_valid(geometry)
            or node.get("srid") != 4326
        ):
            checks["geometry_valid"] = False
        else:
            positions[str(node["id"])] = geometry
        if not node.get("metadata"):
            checks["metadata_complete"] = False
    seen_edges: set[tuple[str, str, str]] = set()
    geod = Geod(ellps="WGS84")
    for edge in edges:
        start, end = str(edge["start_intersection_id"]), str(edge["end_intersection_id"])
        if (
            str(edge["network_version_id"]) != str(network_id)
            or start not in node_ids
            or end not in node_ids
        ):
            checks["references_consistent"] = False
        else:
            graph.add_edge(start, end)
        geometry = edge.get("geometry")
        if (
            not isinstance(geometry, LineString)
            or geometry.is_empty
            or not geometry.is_valid
            or not geographic_bounds_valid(geometry)
            or edge.get("srid") != 4326
        ):
            checks["geometry_valid"] = False
        else:
            duplicate_key = (start, end, geometry.normalize().wkb_hex)
            if duplicate_key in seen_edges:
                checks["duplicate_edges_absent"] = False
            seen_edges.add(duplicate_key)
            if start in positions and end in positions:
                for actual, declared in (
                    (geometry.coords[0], positions[start]),
                    (geometry.coords[-1], positions[end]),
                ):
                    _, _, distance = geod.inv(actual[0], actual[1], declared.x, declared.y)
                    if distance > 0.5:
                        checks["endpoints_consistent"] = False
        speed = edge.get("speed_limit_mps")
        length = edge.get("length_m")
        lanes = edge.get("lane_count")
        if (
            not isinstance(lanes, int)
            or lanes < 1
            or not isinstance(length, (int, float))
            or not math.isfinite(length)
            or length < 0
            or (
                speed is not None
                and (not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed <= 0)
            )
        ):
            checks["attributes_valid"] = False
        if not edge.get("metadata") or not edge.get("road_class"):
            checks["metadata_complete"] = False
    components = nx.number_connected_components(graph) if nodes else 0
    isolated = len(list(nx.isolates(graph)))
    if components > 1 or isolated:
        checks["connectivity_valid"] = False
        warnings.append(
            f"Explicit topology has {components} connected components and {isolated} isolated nodes"
        )
    if not checks["metadata_complete"]:
        warnings.append("Some nodes or edges lack descriptive metadata")
    if expected_nodes is not None and expected_nodes != len(nodes):
        checks["counts_consistent"] = False
    if expected_edges is not None and expected_edges != len(edges):
        checks["counts_consistent"] = False
    descriptions = {
        "geometry_valid": "Invalid, empty, unsupported geometry or SRID",
        "references_consistent": "Mismatched network or missing endpoint references",
        "attributes_valid": "Invalid lane, speed or metric length attributes",
        "region_coverage": f"{outside_edges} edges extend outside the region tolerance",
        "endpoints_consistent": "Line endpoints disagree with declared intersection positions",
        "duplicate_edges_absent": "Duplicate edges with the same explicit endpoints and geometry",
        "counts_consistent": "Stored network counts disagree with its actual features",
    }
    for key, description in descriptions.items():
        if not checks[key]:
            errors.append(description)
    status = "INVALID" if errors else "VALID_WITH_WARNINGS" if warnings else "VALID"
    return {
        "network_id": str(network_id),
        "validated": not errors,
        "status": status,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "components": components,
            "isolated_nodes": isolated,
        },
        "boundary_tolerance_m": boundary_tolerance_m,
        "semantics": SEMANTICS,
    }


async def validate_network(
    session: AsyncSession, network_id: UUID, settings: Settings | None = None
) -> dict[str, Any]:
    configuration = settings or Settings()
    # Child-write triggers lock this parent FOR UPDATE. Holding FOR SHARE keeps
    # feature/coordinate aggregates and the subsequent materialization coherent.
    network = await session.scalar(
        select(NetworkVersion).where(NetworkVersion.id == network_id).with_for_update(read=True)
    )
    if network is None:
        raise HTTPException(404, "Network not found")
    # Aggregate in PostGIS before transferring any geometry into Python. A
    # feature count alone permits many individually valid 5000-point lines.
    node_statistics = (
        await session.execute(
            select(
                func.count(), func.coalesce(func.sum(func.ST_NPoints(Intersection.location)), 0)
            ).where(Intersection.network_version_id == network_id)
        )
    ).one()
    edge_statistics = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(func.ST_NPoints(RoadEdge.geom)), 0)).where(
                RoadEdge.network_version_id == network_id
            )
        )
    ).one()
    node_count, node_coordinates = type_cast(tuple[int, int], node_statistics)
    edge_count, edge_coordinates = type_cast(tuple[int, int], edge_statistics)
    budget = None
    if node_count + edge_count > configuration.geo_max_validation_features:
        budget = "feature"
    elif node_coordinates + edge_coordinates > configuration.geo_max_validation_coordinates:
        budget = "coordinate"
    if budget is not None:
        return {
            "network_id": str(network_id),
            "validated": False,
            "status": "NOT_VALIDATED",
            "checks": {},
            "warnings": [f"Network exceeds configured validation {budget} budget"],
            "errors": [],
            "counts": {
                "nodes": node_count,
                "edges": edge_count,
                "components": None,
                "isolated_nodes": None,
            },
            "boundary_tolerance_m": configuration.geo_boundary_tolerance_m,
            "semantics": SEMANTICS,
        }
    node_rows = (
        await session.execute(
            select(Intersection, func.ST_SRID(Intersection.location)).where(
                Intersection.network_version_id == network_id
            )
        )
    ).all()
    edge_rows = (
        await session.execute(
            select(RoadEdge, func.ST_SRID(RoadEdge.geom)).where(
                RoadEdge.network_version_id == network_id
            )
        )
    ).all()
    nodes = [
        {
            "id": node.id,
            "network_version_id": node.network_version_id,
            "source_node_id": node.source_node_id,
            "geometry": to_shape(node.location),
            "srid": srid,
            "metadata": node.metadata_,
        }
        for node, srid in type_cast(Sequence[tuple[Intersection, int]], node_rows)
    ]
    edges = [
        {
            "id": edge.id,
            "network_version_id": edge.network_version_id,
            "sumo_edge_id": edge.sumo_edge_id,
            "start_intersection_id": edge.start_intersection_id,
            "end_intersection_id": edge.end_intersection_id,
            "geometry": to_shape(edge.geom),
            "srid": srid,
            "metadata": edge.metadata_,
            "lane_count": edge.lane_count,
            "speed_limit_mps": edge.speed_limit_mps,
            "length_m": edge.length_m,
            "road_class": edge.road_class,
        }
        for edge, srid in type_cast(Sequence[tuple[RoadEdge, int]], edge_rows)
    ]
    region_boundary = (
        select(Region.boundary).where(Region.id == network.region_id).scalar_subquery()
    )
    permitted = func.ST_Buffer(
        cast(region_boundary, Geography()), configuration.geo_boundary_tolerance_m
    )
    outside = int(
        await session.scalar(
            select(func.count())
            .select_from(RoadEdge)
            .where(
                RoadEdge.network_version_id == network_id,
                ~func.ST_Covers(permitted, cast(RoadEdge.geom, Geography())),
            )
        )
        or 0
    )
    return structural_report(
        network_id,
        nodes,
        edges,
        boundary_tolerance_m=configuration.geo_boundary_tolerance_m,
        outside_edges=outside,
        expected_nodes=network.node_count,
        expected_edges=network.edge_count,
    )
