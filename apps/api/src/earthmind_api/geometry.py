"""Bounded RFC 7946 geometry parsing with explicit WGS84 longitude/latitude order."""

import math
from collections.abc import Mapping
from typing import Any

from pyproj import Geod
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

SUPPORTED_TYPES = {"Point", "LineString", "Polygon", "MultiPolygon"}
MAX_COORDINATES = 5000


class SpatialInputError(ValueError):
    """A bounded, safe spatial validation explanation for HTTP clients."""


def _sequence(value: Any, minimum: int) -> list[Any]:
    if not isinstance(value, (list, tuple)) or len(value) < minimum:
        raise ValueError("Geometry coordinates have an invalid nesting or size")
    return list(value)


def _position(value: Any) -> tuple[float, float]:
    values = _sequence(value, 2)
    if len(values) != 2:
        raise ValueError("Only two-dimensional longitude/latitude positions are supported")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in values):
        raise ValueError("Coordinates must be finite numeric longitude/latitude values")
    longitude, latitude = float(values[0]), float(values[1])
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        raise ValueError("Coordinates must be finite")
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError("Coordinates must use WGS84 [longitude, latitude] ranges")
    return longitude, latitude


def validate_geometry(
    value: Mapping[str, Any],
    *,
    allowed: set[str] | None = None,
    max_coordinates: int = MAX_COORDINATES,
) -> BaseGeometry:
    if set(value) - {"type", "coordinates"}:
        raise ValueError(
            "Only RFC 7946 geometry type and coordinates are accepted; CRS overrides are forbidden"
        )
    kind = value.get("type")
    if (
        not isinstance(kind, str)
        or kind not in SUPPORTED_TYPES
        or (allowed is not None and kind not in allowed)
    ):
        raise ValueError("Unsupported geometry type")
    coordinates = value.get("coordinates")
    count = 0

    def position(item: Any) -> None:
        nonlocal count
        _position(item)
        count += 1
        if count > max_coordinates:
            raise ValueError("Geometry exceeds the configured coordinate count limit")

    def ring(item: Any) -> None:
        points = _sequence(item, 4)
        for point in points:
            position(point)
        if points[0] != points[-1]:
            raise ValueError("Polygon rings must be explicitly closed")

    def polygon(item: Any) -> None:
        for item_ring in _sequence(item, 1):
            ring(item_ring)

    if kind == "Point":
        position(coordinates)
    elif kind == "LineString":
        for point in _sequence(coordinates, 2):
            position(point)
    elif kind == "Polygon":
        polygon(coordinates)
    else:
        for item_polygon in _sequence(coordinates, 1):
            polygon(item_polygon)
    try:
        geometry = shape(dict(value))
    except (TypeError, ValueError, IndexError) as error:
        raise ValueError("Malformed GeoJSON geometry") from error
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"Invalid nonempty geometry: {explain_validity(geometry)}")
    return geometry


def as_multipolygon(geometry: BaseGeometry) -> MultiPolygon:
    if isinstance(geometry, Polygon):
        return MultiPolygon([geometry])
    if isinstance(geometry, MultiPolygon):
        return geometry
    raise ValueError("A region requires Polygon or MultiPolygon geometry")


def geodesic_area_km2(geometry: BaseGeometry) -> float:
    """Independent WGS84 spheroid measurement; never square degrees."""
    if isinstance(geometry, Polygon):
        from shapely.geometry.polygon import orient

        oriented = orient(geometry, sign=1.0)
        area, _ = Geod(ellps="WGS84").geometry_area_perimeter(oriented)
        return abs(float(area)) / 1_000_000
    if isinstance(geometry, MultiPolygon):
        return sum(geodesic_area_km2(part) for part in geometry.geoms)
    raise ValueError("Area measurement requires polygonal geometry")


def geometry_json(geometry: BaseGeometry) -> dict[str, Any]:
    return dict(mapping(geometry))


def parse_bbox(value: str, max_degrees: float = 1.0) -> tuple[float, float, float, float]:
    try:
        coordinates = tuple(float(item) for item in value.split(","))
    except ValueError as error:
        raise ValueError("bbox must contain west,south,east,north numbers") from error
    if len(coordinates) != 4 or not all(math.isfinite(item) for item in coordinates):
        raise ValueError("bbox requires four finite values")
    west, south, east, north = coordinates
    _position([west, south])
    _position([east, north])
    if west >= east or south >= north:
        raise ValueError(
            "bbox requires west < east and south < north; antimeridian boxes are unsupported"
        )
    if east - west > max_degrees or north - south > max_degrees:
        raise ValueError("bbox exceeds the configured maximum span")
    return west, south, east, north
