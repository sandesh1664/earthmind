"""Verify M02 against real deployed HTTP/PostGIS data; never import real streets."""

import json
import math
import sys
import urllib.error
import urllib.request
from typing import Any

from pyproj import Geod
from shapely.geometry import Point, shape
from smoke import port


def fetch(url: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        response = urllib.request.urlopen(request, timeout=8)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        data: dict[str, Any] = json.loads(response.read())
        return response.code, data


def get(url: str) -> dict[str, Any]:
    status, data = fetch(url)
    if status != 200:
        raise RuntimeError(f"{url}: HTTP {status}: {data}")
    return data


def verify() -> dict[str, Any]:
    api = f"http://127.0.0.1:{port('API_PORT', '8000')}/api/v1"
    web = f"http://127.0.0.1:{port('WEB_PORT', '3000')}/api/geospatial"
    regions = get(f"{web}/regions?limit=100")
    matches = [item for item in regions["items"] if item["slug"] == "dubai-downtown-demo"]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one idempotently seeded synthetic study region")
    region = get(f"{api}/regions/{matches[0]['id']}")
    if region["metadata"].get("is_synthetic") is not True or region["area_km2"] <= 0:
        raise RuntimeError("Study region must be labeled synthetic with positive geodesic area")
    feature = get(f"{api}/regions/{region['id']}/geojson")
    geometry = shape(feature["geometry"])
    if geometry.geom_type != "MultiPolygon" or not geometry.is_valid:
        raise RuntimeError("Stored region GeoJSON must be a valid MultiPolygon")
    if not geometry.covers(Point(*region["centroid"])):
        raise RuntimeError("Computed representative centroid must be covered by its boundary")
    computed_area = abs(Geod(ellps="WGS84").geometry_area_perimeter(geometry)[0]) / 1e6
    if not math.isclose(computed_area, region["area_km2"], rel_tol=1e-6):
        raise RuntimeError("PostGIS area differs from an independent geodesic calculation")
    network_page = get(f"{web}/networks?region_id={region['id']}&limit=100")
    networks = [item for item in network_page["items"] if item["version_label"] == "synthetic-v1"]
    if len(networks) != 1:
        raise RuntimeError("Expected one immutable synthetic network version")
    network = get(f"{api}/networks/{networks[0]['id']}")
    identifier = network["id"]
    bounds = ",".join(str(value) for value in region["bounds"])
    edges = get(f"{api}/networks/{identifier}/edges?bbox={bounds}&limit=100")
    nodes = get(f"{api}/networks/{identifier}/intersections?bbox={bounds}&limit=100")
    if (edges["total"], nodes["total"]) != (8, 6):
        raise RuntimeError("Synthetic graph must persist eight edges and six intersections")
    for item in edges["features"]:
        if (
            item["geometry"]["type"] != "LineString"
            or item["properties"].get("is_synthetic") is not True
            or not item["properties"]["sumo_edge_id"].startswith("provisional:")
        ):
            raise RuntimeError("Edge GeoJSON must retain synthetic/provisional identifiers")
    validation = get(f"{web}/networks/{identifier}/validation")
    if validation["status"] not in {"VALID", "VALID_WITH_WARNINGS"} or not validation["validated"]:
        raise RuntimeError(f"Stored synthetic network failed structural validation: {validation}")
    if validation["counts"]["components"] != 1:
        raise RuntimeError("Synthetic explicit topology should contain one connected component")
    for point, expected in ((region["centroid"], True), ([0.0, 0.0], False)):
        code, containment = fetch(
            f"{api}/geo/contains",
            {"region_id": region["id"], "point": {"type": "Point", "coordinates": point}},
        )
        if code != 200 or containment.get("contains") is not expected:
            raise RuntimeError("Actual PostGIS point containment disagrees with the fixture")
    nearby = get(
        f"{api}/geo/nearby-edges?network_id={identifier}&longitude=55.2742&latitude=25.195"
        "&radius_m=1000&limit=100"
    )
    if not nearby["features"]:
        raise RuntimeError("Geographic meter-radius query returned no nearby synthetic edges")
    for item in nearby["features"]:
        distance = item["properties"]["distance_m"]
        if not math.isfinite(distance) or not 0 <= distance <= 1000:
            raise RuntimeError("Nearby-edge distances must be finite meters within the radius")
    source = get(f"{web}/data-sources/{network['data_source_id']}")
    if source["source_type"] != "synthetic" or not source.get("license_identifier"):
        raise RuntimeError("Synthetic provenance and explicit license identification are required")
    if "metadata" in source or "artifact_uri" in network:
        raise RuntimeError(
            "Private source metadata or artifact locations crossed the public boundary"
        )
    code, _ = fetch(
        f"{api}/regions",
        {
            "slug": "m02-smoke-unauthorized",
            "name": "Unauthorized synthetic smoke probe",
            "country_code": "AE",
            "boundary": feature["geometry"],
            "metadata": {"is_synthetic": True},
        },
    )
    if code != 403:
        raise RuntimeError(f"Unauthorized region mutation must return HTTP 403; received {code}")
    result = {
        "region_id": region["id"],
        "network_id": identifier,
        "area_km2": region["area_km2"],
        "independent_area_km2": computed_area,
        "bounds": region["bounds"],
        "centroid": region["centroid"],
        "nodes": nodes["total"],
        "edges": edges["total"],
        "validation": validation,
        "license_identifier": source["license_identifier"],
        "nearest_distance_m": nearby["features"][0]["properties"]["distance_m"],
        "unauthorized_write_status": code,
        "is_synthetic": True,
    }
    print(json.dumps(result, sort_keys=True))
    print(
        "M02 SMOKE PASSED: real PostGIS geometry, provenance, topology, "
        "meter queries and write gate"
    )
    return result


if __name__ == "__main__":
    try:
        verify()
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"M02 SMOKE FAILED: {error}", file=sys.stderr)
        sys.exit(1)
