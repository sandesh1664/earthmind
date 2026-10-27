"""Database-backed bounded spatial queries; measurements use PostGIS geography."""

import ipaddress
import json
from collections.abc import Sequence
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from fastapi import HTTPException
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape
from pydantic import JsonValue
from sqlalchemy import cast as sql_cast
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from earthmind_api.geometry import as_multipolygon, parse_bbox, validate_geometry
from earthmind_api.geospatial_models import (
    AuditEvent,
    DataSource,
    Intersection,
    NetworkVersion,
    Region,
    RoadEdge,
)
from earthmind_api.geospatial_schemas import (
    Feature,
    FeatureCollection,
    GeometryObject,
    NetworkResponse,
    RegionCreate,
    RegionResponse,
    SourceResponse,
)
from earthmind_api.settings import Settings

PUBLIC_REGION_METADATA = {
    "is_synthetic",
    "boundary_policy",
    "description",
    "source",
    "fixture_version",
}


def public_region_metadata(value: dict[str, Any]) -> dict[str, JsonValue]:
    return cast(
        dict[str, JsonValue],
        {key: item for key, item in value.items() if key in PUBLIC_REGION_METADATA},
    )


PUBLIC_FEATURE_METADATA = {
    "osm_way_id",
    "osm_way_ids",
    "osm_node_id",
    "osm_lanes",
    "osm_directional_lanes",
    "osm_maxspeed",
    "lane_count_source",
    "speed_limit_source",
    "turn_restrictions_status",
    "sumo_identifier_verified",
    "geometry_derivation",
    "signal_status",
    "node_origin",
}


def public_feature_metadata(value: dict[str, Any]) -> dict[str, JsonValue]:
    """Expose bounded provenance facts, never arbitrary original source tags/URIs."""
    result: dict[str, JsonValue] = {}
    for key, item in value.items():
        if key not in PUBLIC_FEATURE_METADATA:
            continue
        if item is None or isinstance(item, bool):
            result[key] = item
        elif isinstance(item, str):
            result[key] = item[:256]
        elif (
            isinstance(item, list)
            and len(item) <= 64
            and all(isinstance(part, str) and len(part) <= 128 for part in item)
        ):
            result[key] = item
    return result


def bounds_expression(geometry: Any) -> list[Any]:
    return [
        func.ST_XMin(geometry),
        func.ST_YMin(geometry),
        func.ST_XMax(geometry),
        func.ST_YMax(geometry),
    ]


async def get_region(session: AsyncSession, identifier: UUID) -> Region:
    region = await session.get(Region, identifier)
    if region is None:
        raise HTTPException(404, "Region not found")
    return region


async def serialize_region(session: AsyncSession, region: Region) -> RegionResponse:
    row = (
        await session.execute(
            select(func.ST_AsGeoJSON(Region.centroid), *bounds_expression(Region.boundary)).where(
                Region.id == region.id
            )
        )
    ).one()
    centroid = json.loads(row[0])["coordinates"]
    return RegionResponse(
        id=region.id,
        slug=region.slug,
        name=region.name,
        country_code=region.country_code,
        emirate=region.emirate,
        timezone=region.timezone,
        area_km2=region.area_km2,
        centroid=centroid,
        bounds=list(row[1:]),
        metadata=public_region_metadata(region.metadata_),
        created_at=region.created_at,
        updated_at=region.updated_at,
    )


async def list_regions(
    session: AsyncSession, limit: int, offset: int
) -> tuple[list[RegionResponse], int]:
    total = int(await session.scalar(select(func.count()).select_from(Region)) or 0)
    regions = (
        await session.scalars(select(Region).order_by(Region.slug).limit(limit).offset(offset))
    ).all()
    return [await serialize_region(session, region) for region in regions], total


async def create_region(session: AsyncSession, request: RegionCreate, settings: Settings) -> Region:
    geometry = validate_geometry(
        request.boundary.model_dump(),
        allowed={"Polygon", "MultiPolygon"},
        max_coordinates=settings.geo_max_coordinates,
    )
    region = Region(
        slug=request.slug,
        name=request.name,
        country_code=request.country_code,
        emirate=request.emirate,
        timezone=request.timezone,
        boundary=from_shape(as_multipolygon(geometry), srid=4326),
        metadata_=request.metadata,
    )
    session.add(region)
    await session.flush()
    await session.refresh(region)
    session.add(
        AuditEvent(
            action="region.created",
            target_type="region",
            target_id=region.id,
            metadata_={"slug": region.slug},
        )
    )
    await session.flush()
    return region


async def region_geojson(session: AsyncSession, region: Region) -> Feature:
    encoded = await session.scalar(
        select(func.ST_AsGeoJSON(Region.boundary)).where(Region.id == region.id)
    )
    if not isinstance(encoded, str):
        raise RuntimeError("Stored region geometry did not serialize to GeoJSON")
    return Feature(
        id=str(region.id),
        geometry=GeometryObject.model_validate(json.loads(encoded)),
        properties={
            "id": str(region.id),
            "slug": region.slug,
            "name": region.name,
            "country_code": region.country_code,
            "area_km2": region.area_km2,
            "is_synthetic": region.metadata_.get("is_synthetic") is True,
            "boundary_policy": str(
                region.metadata_.get("boundary_policy", "project-provided geometry")
            ),
        },
    )


async def contains_point(session: AsyncSession, region: Region, point: GeometryObject) -> bool:
    geometry = from_shape(validate_geometry(point.model_dump(), allowed={"Point"}), srid=4326)
    return bool(
        await session.scalar(
            select(func.ST_Covers(Region.boundary, geometry)).where(Region.id == region.id)
        )
    )


async def get_network(session: AsyncSession, identifier: UUID) -> NetworkVersion:
    network = await session.get(NetworkVersion, identifier)
    if network is None:
        raise HTTPException(404, "Network not found")
    return network


async def serialize_network(session: AsyncSession, network: NetworkVersion) -> NetworkResponse:
    extent = func.ST_Extent(RoadEdge.geom)
    row = (
        await session.execute(
            select(*bounds_expression(extent)).where(RoadEdge.network_version_id == network.id)
        )
    ).one()
    bounds = None if row[0] is None else list(row)
    node_count = int(
        await session.scalar(
            select(func.count())
            .select_from(Intersection)
            .where(Intersection.network_version_id == network.id)
        )
        or 0
    )
    edge_count = int(
        await session.scalar(
            select(func.count())
            .select_from(RoadEdge)
            .where(RoadEdge.network_version_id == network.id)
        )
        or 0
    )
    source = (
        await session.get(DataSource, network.data_source_id) if network.data_source_id else None
    )
    return NetworkResponse(
        id=network.id,
        region_id=network.region_id,
        data_source_id=network.data_source_id,
        version_label=network.version_label,
        status=network.status,
        checksum_sha256=network.checksum_sha256,
        source_format=network.source_format,
        projection_srid=network.projection_srid,
        node_count=node_count,
        edge_count=edge_count,
        is_validated=network.is_validated,
        validation_summary=network.validation_summary,
        bounds=bounds,
        created_at=network.created_at,
        is_synthetic=source is not None and source.source_type == "synthetic",
    )


async def list_networks(
    session: AsyncSession, limit: int, offset: int, region_id: UUID | None = None
) -> tuple[list[NetworkResponse], int]:
    filters = [] if region_id is None else [NetworkVersion.region_id == region_id]
    total = int(
        await session.scalar(select(func.count()).select_from(NetworkVersion).where(*filters)) or 0
    )
    networks = (
        await session.scalars(
            select(NetworkVersion)
            .where(*filters)
            .order_by(NetworkVersion.created_at, NetworkVersion.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [await serialize_network(session, item) for item in networks], total


def edge_feature(edge: RoadEdge, encoded: str, distance_m: float | None = None) -> Feature:
    properties: dict[str, JsonValue] = {
        "network_version_id": str(edge.network_version_id),
        "sumo_edge_id": edge.sumo_edge_id,
        "source_edge_id": edge.source_edge_id,
        "name": edge.name,
        "road_class": edge.road_class,
        "lane_count": edge.lane_count,
        "speed_limit_mps": edge.speed_limit_mps,
        "length_m": edge.length_m,
        "is_one_way": edge.is_one_way,
        "is_synthetic": edge.metadata_.get("is_synthetic") is True,
        "start_intersection_id": str(edge.start_intersection_id),
        "end_intersection_id": str(edge.end_intersection_id),
        "metadata": public_feature_metadata(edge.metadata_),
    }
    if distance_m is not None:
        properties["distance_m"] = distance_m
    return Feature(
        id=str(edge.id),
        geometry=GeometryObject.model_validate(json.loads(encoded)),
        properties=properties,
    )


async def query_edges(
    session: AsyncSession,
    network_id: UUID,
    limit: int,
    offset: int,
    bbox: str | None,
    settings: Settings,
) -> FeatureCollection:
    filters: list[Any] = [RoadEdge.network_version_id == network_id]
    if bbox:
        west, south, east, north = parse_bbox(bbox, settings.geo_max_bbox_degrees)
        envelope = func.ST_MakeEnvelope(west, south, east, north, 4326)
        filters.extend(
            [RoadEdge.geom.op("&&")(envelope), func.ST_Intersects(RoadEdge.geom, envelope)]
        )
    total = int(
        await session.scalar(select(func.count()).select_from(RoadEdge).where(*filters)) or 0
    )
    rows = (
        await session.execute(
            select(RoadEdge, func.ST_AsGeoJSON(RoadEdge.geom))
            .where(*filters)
            .order_by(RoadEdge.sumo_edge_id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return FeatureCollection(
        features=[
            edge_feature(edge, encoded)
            for edge, encoded in cast(Sequence[tuple[RoadEdge, str]], rows)
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


async def query_intersections(
    session: AsyncSession,
    network_id: UUID,
    limit: int,
    offset: int,
    polygon: GeometryObject | None = None,
) -> FeatureCollection:
    filters: list[Any] = [Intersection.network_version_id == network_id]
    if polygon is not None:
        area = from_shape(
            validate_geometry(polygon.model_dump(), allowed={"Polygon", "MultiPolygon"}), srid=4326
        )
        filters.extend(
            [Intersection.location.op("&&")(area), func.ST_Covers(area, Intersection.location)]
        )
    total = int(
        await session.scalar(select(func.count()).select_from(Intersection).where(*filters)) or 0
    )
    rows = (
        await session.execute(
            select(Intersection, func.ST_AsGeoJSON(Intersection.location))
            .where(*filters)
            .order_by(Intersection.source_node_id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    features = [
        Feature(
            id=str(node.id),
            geometry=GeometryObject.model_validate(json.loads(encoded)),
            properties={
                "network_version_id": str(node.network_version_id),
                "source_node_id": node.source_node_id,
                "sumo_node_id": node.sumo_node_id,
                "intersection_type": node.intersection_type,
                "is_signalized": node.is_signalized,
                "is_synthetic": node.metadata_.get("is_synthetic") is True,
                "metadata": public_feature_metadata(node.metadata_),
            },
        )
        for node, encoded in cast(Sequence[tuple[Intersection, str]], rows)
    ]
    return FeatureCollection(features=features, total=total, limit=limit, offset=offset)


async def nearby_edges(
    session: AsyncSession,
    longitude: float,
    latitude: float,
    radius_m: float,
    limit: int,
    offset: int,
    network_id: UUID | None = None,
) -> FeatureCollection:
    point = as_geography(func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326))
    geography = as_geography(RoadEdge.geom)
    filters: list[Any] = [func.ST_DWithin(geography, point, radius_m)]
    if network_id is not None:
        filters.append(RoadEdge.network_version_id == network_id)
    distance = func.ST_Distance(geography, point)
    total = int(
        await session.scalar(select(func.count()).select_from(RoadEdge).where(*filters)) or 0
    )
    rows = (
        await session.execute(
            select(RoadEdge, func.ST_AsGeoJSON(RoadEdge.geom), distance)
            .where(*filters)
            .order_by(distance, RoadEdge.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return FeatureCollection(
        features=[
            edge_feature(edge, encoded, measured)
            for edge, encoded, measured in cast(Sequence[tuple[RoadEdge, str, float]], rows)
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def safe_source_url(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        return None
    try:
        if not ipaddress.ip_address(hostname).is_global:
            return None
    except ValueError:
        if "." not in hostname:
            return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def serialize_source(source: DataSource) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        provider_name=source.provider_name,
        dataset_name=source.dataset_name,
        source_type=source.source_type,
        source_url=safe_source_url(source.source_url),
        license_identifier=source.license_identifier,
        attribution_text=source.attribution_text,
        collected_at=source.collected_at,
        source_version=source.source_version,
        checksum_sha256=source.checksum_sha256,
        created_at=source.created_at,
        is_synthetic=source.source_type == "synthetic",
    )


def as_geography(geometry: Any) -> Any:
    """Omit typmods so PostgreSQL matches the functional geography index."""
    return sql_cast(geometry, Geography(geometry_type=None))
