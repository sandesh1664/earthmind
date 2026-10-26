"""Typed public M02 interfaces; source-private metadata never crosses this boundary."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from earthmind_api.geometry import validate_geometry


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeometryObject(PublicModel):
    type: Literal["Point", "LineString", "Polygon", "MultiPolygon"]
    coordinates: list[Any] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_geojson(self) -> "GeometryObject":
        validate_geometry(self.model_dump())
        return self


class RegionCreate(PublicModel):
    slug: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=160)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    emirate: str | None = Field(default=None, max_length=80)
    timezone: str = Field(default="Asia/Dubai", max_length=64)
    coordinate_order: Literal["longitude_latitude"] = "longitude_latitude"
    boundary: GeometryObject
    metadata: dict[str, JsonValue] = Field(default_factory=dict, max_length=32)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("An IANA timezone is required") from error
        return value

    @model_validator(mode="after")
    def polygonal(self) -> "RegionCreate":
        validate_geometry(self.boundary.model_dump(), allowed={"Polygon", "MultiPolygon"})
        return self


class RegionResponse(PublicModel):
    id: UUID
    slug: str
    name: str
    country_code: str
    emirate: str | None
    timezone: str
    area_km2: float
    centroid: list[float]
    bounds: list[float]
    metadata: dict[str, JsonValue]
    created_at: datetime
    updated_at: datetime


class RegionPage(PublicModel):
    items: list[RegionResponse]
    total: int
    limit: int
    offset: int


class NetworkResponse(PublicModel):
    id: UUID
    region_id: UUID
    data_source_id: UUID | None
    version_label: str
    status: str
    checksum_sha256: str
    source_format: str
    projection_srid: int
    node_count: int
    edge_count: int
    is_validated: bool
    validation_summary: dict[str, JsonValue]
    bounds: list[float] | None
    created_at: datetime
    is_synthetic: bool


class NetworkPage(PublicModel):
    items: list[NetworkResponse]
    total: int
    limit: int
    offset: int


class SourceResponse(PublicModel):
    id: UUID
    provider_name: str
    dataset_name: str
    source_type: str
    source_url: str | None
    license_identifier: str | None
    attribution_text: str | None
    collected_at: datetime | None
    source_version: str | None
    checksum_sha256: str | None
    created_at: datetime
    is_synthetic: bool


class SourcePage(PublicModel):
    items: list[SourceResponse]
    total: int
    limit: int
    offset: int


class Feature(PublicModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: GeometryObject
    properties: dict[str, JsonValue]


class FeatureCollection(PublicModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature]
    total: int
    limit: int
    offset: int


class GeometryValidationRequest(PublicModel):
    geometry: GeometryObject
    coordinate_order: Literal["longitude_latitude"] = "longitude_latitude"


class GeometryValidationResponse(PublicModel):
    valid: bool
    geometry_type: str
    srid: Literal[4326] = 4326
    coordinate_order: Literal["longitude_latitude"] = "longitude_latitude"
    area_km2: float | None = None


class ContainsRequest(PublicModel):
    region_id: UUID
    point: GeometryObject
    coordinate_order: Literal["longitude_latitude"] = "longitude_latitude"

    @model_validator(mode="after")
    def point_only(self) -> "ContainsRequest":
        if self.point.type != "Point":
            raise ValueError("Contains requires a Point geometry")
        return self


class ContainsResponse(PublicModel):
    region_id: UUID
    contains: bool
    boundary_policy: Literal["covers_including_boundary"] = "covers_including_boundary"


class ValidationReport(PublicModel):
    network_id: UUID
    validated: bool
    status: Literal["VALID", "VALID_WITH_WARNINGS", "INVALID", "NOT_VALIDATED"]
    checks: dict[str, bool]
    warnings: list[str]
    errors: list[str]
    counts: dict[str, int | None]
    boundary_tolerance_m: float
    semantics: str
