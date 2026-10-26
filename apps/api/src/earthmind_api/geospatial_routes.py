"""M02 read APIs and explicitly authorized local-development region creation."""

import json
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from earthmind_api.dependencies import get_session
from earthmind_api.geometry import (
    SpatialInputError,
    geodesic_area_km2,
    parse_bbox,
    validate_geometry,
)
from earthmind_api.geospatial_models import DataSource
from earthmind_api.geospatial_schemas import (
    ContainsRequest,
    ContainsResponse,
    Feature,
    FeatureCollection,
    GeometryObject,
    GeometryValidationRequest,
    GeometryValidationResponse,
    NetworkPage,
    NetworkResponse,
    RegionCreate,
    RegionPage,
    RegionResponse,
    SourcePage,
    SourceResponse,
    ValidationReport,
)
from earthmind_api.network_validation import validate_network
from earthmind_api.security import require_dev_write
from earthmind_api.settings import Settings
from earthmind_api.spatial import (
    contains_point,
    create_region,
    get_network,
    get_region,
    list_networks,
    list_regions,
    nearby_edges,
    query_edges,
    query_intersections,
    region_geojson,
    serialize_network,
    serialize_region,
    serialize_source,
)

router = APIRouter(prefix="/api/v1", tags=["geospatial"])
Session = Annotated[AsyncSession, Depends(get_session)]


def get_geo_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


Configuration = Annotated[Settings, Depends(get_geo_settings)]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0, le=100000)]


def check_page(limit: int, settings: Settings) -> None:
    if limit > settings.geo_max_page_size:
        raise HTTPException(422, "Requested page exceeds configured limit")


@router.get("/regions", response_model=RegionPage)
async def regions(
    session: Session, settings: Configuration, limit: PageLimit = 25, offset: PageOffset = 0
) -> RegionPage:
    check_page(limit, settings)
    items, total = await list_regions(session, limit, offset)
    return RegionPage(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/regions",
    response_model=RegionResponse,
    status_code=201,
    dependencies=[Depends(require_dev_write)],
)
async def region_create(
    payload: RegionCreate, session: Session, settings: Configuration, response: Response
) -> RegionResponse:
    try:
        region = await create_region(session, payload, settings)
    except ValueError as error:
        raise SpatialInputError(str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            409, "Region conflicts with a stored identifier or spatial constraint"
        ) from error
    response.headers["Location"] = f"/api/v1/regions/{region.id}"
    return await serialize_region(session, region)


@router.get("/regions/{region_id}", response_model=RegionResponse)
async def region_detail(region_id: UUID, session: Session) -> RegionResponse:
    return await serialize_region(session, await get_region(session, region_id))


@router.get("/regions/{region_id}/geojson", response_model=Feature)
async def region_feature(region_id: UUID, session: Session) -> Feature:
    return await region_geojson(session, await get_region(session, region_id))


@router.get("/networks", response_model=NetworkPage)
async def networks(
    session: Session,
    settings: Configuration,
    region_id: UUID | None = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> NetworkPage:
    check_page(limit, settings)
    items, total = await list_networks(session, limit, offset, region_id)
    return NetworkPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/networks/{network_id}", response_model=NetworkResponse)
async def network_detail(network_id: UUID, session: Session) -> NetworkResponse:
    return await serialize_network(session, await get_network(session, network_id))


@router.get("/networks/{network_id}/edges", response_model=FeatureCollection)
async def edges(
    network_id: UUID,
    session: Session,
    settings: Configuration,
    bbox: Annotated[str | None, Query(max_length=120)] = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> FeatureCollection:
    check_page(limit, settings)
    await get_network(session, network_id)
    try:
        return await query_edges(session, network_id, limit, offset, bbox, settings)
    except ValueError as error:
        raise SpatialInputError(str(error)) from error


@router.get("/networks/{network_id}/intersections", response_model=FeatureCollection)
async def intersections(
    network_id: UUID,
    session: Session,
    settings: Configuration,
    polygon: Annotated[str | None, Query(max_length=60000)] = None,
    bbox: Annotated[str | None, Query(max_length=120)] = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> FeatureCollection:
    check_page(limit, settings)
    await get_network(session, network_id)
    parsed = None
    try:
        if polygon is not None and bbox is not None:
            raise ValueError("Choose polygon or bbox filtering")
        if polygon is not None:
            parsed = GeometryObject.model_validate(json.loads(polygon))
            filter_geometry = validate_geometry(
                parsed.model_dump(),
                allowed={"Polygon", "MultiPolygon"},
                max_coordinates=settings.geo_max_coordinates,
            )
            west, south, east, north = filter_geometry.bounds
            if (
                east - west > settings.geo_max_bbox_degrees
                or north - south > settings.geo_max_bbox_degrees
            ):
                raise ValueError("Polygon filter exceeds the configured maximum spatial span")
        elif bbox is not None:
            west, south, east, north = parse_bbox(bbox, settings.geo_max_bbox_degrees)
            parsed = GeometryObject(
                type="Polygon",
                coordinates=[
                    [[west, south], [east, south], [east, north], [west, north], [west, south]]
                ],
            )
        return await query_intersections(session, network_id, limit, offset, parsed)
    except (ValueError, TypeError) as error:
        raise SpatialInputError("Invalid or excessive polygon filter") from error


@router.get("/networks/{network_id}/validation", response_model=ValidationReport)
async def network_report(
    network_id: UUID,
    session: Session,
    settings: Configuration,
    tolerance_m: Annotated[float | None, Query(ge=0, le=100)] = None,
) -> ValidationReport:
    configuration = (
        settings
        if tolerance_m is None
        else settings.model_copy(update={"geo_boundary_tolerance_m": tolerance_m})
    )
    return ValidationReport.model_validate(
        await validate_network(session, network_id, configuration)
    )


@router.post("/geo/validate", response_model=GeometryValidationResponse)
async def geometry_validate(
    payload: GeometryValidationRequest, settings: Configuration
) -> GeometryValidationResponse:
    try:
        geometry = validate_geometry(
            payload.geometry.model_dump(), max_coordinates=settings.geo_max_coordinates
        )
    except ValueError as error:
        raise SpatialInputError(str(error)) from error
    area = (
        geodesic_area_km2(geometry)
        if payload.geometry.type in {"Polygon", "MultiPolygon"}
        else None
    )
    return GeometryValidationResponse(
        valid=True, geometry_type=payload.geometry.type, area_km2=area
    )


@router.post("/geo/contains", response_model=ContainsResponse)
async def geometry_contains(payload: ContainsRequest, session: Session) -> ContainsResponse:
    region = await get_region(session, payload.region_id)
    return ContainsResponse(
        region_id=region.id, contains=await contains_point(session, region, payload.point)
    )


@router.get("/geo/nearby-edges", response_model=FeatureCollection)
async def nearby(
    session: Session,
    settings: Configuration,
    longitude: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
    latitude: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
    radius_m: Annotated[float, Query(gt=0, le=5000, allow_inf_nan=False)] = 250,
    network_id: UUID | None = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> FeatureCollection:
    check_page(limit, settings)
    if radius_m > settings.geo_max_radius_m:
        raise HTTPException(422, "Radius exceeds configured maximum")
    if network_id is not None:
        await get_network(session, network_id)
    return await nearby_edges(session, longitude, latitude, radius_m, limit, offset, network_id)


@router.get("/data-sources", response_model=SourcePage)
async def data_sources(
    session: Session, settings: Configuration, limit: PageLimit = 25, offset: PageOffset = 0
) -> SourcePage:
    check_page(limit, settings)
    total = int(await session.scalar(select(func.count()).select_from(DataSource)) or 0)
    sources = (
        await session.scalars(
            select(DataSource)
            .order_by(DataSource.created_at, DataSource.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return SourcePage(
        items=[serialize_source(item) for item in sources], total=total, limit=limit, offset=offset
    )


@router.get("/data-sources/{source_id}", response_model=SourceResponse)
async def data_source(source_id: UUID, session: Session) -> SourceResponse:
    source = await session.get(DataSource, source_id)
    if source is None:
        raise HTTPException(404, "Data source not found")
    return serialize_source(source)
