"""Read-only acceptance of real PostGIS roads and the matching deployed OSM context."""

import hashlib
import json
import urllib.request
from pathlib import Path
from uuid import UUID

import psycopg
from database_checks import database_url
from smoke import port


def main() -> None:
    directory = Path("data/dubai-osm/recovery-v1")
    imported = json.loads((directory / "import-manifest.json").read_text())
    network_id = UUID(imported["network_id"])
    with psycopg.connect(database_url(), connect_timeout=3) as connection:
        roads = connection.execute(
            "SELECT count(*), bool_and(ST_IsValid(geom) AND ST_SRID(geom)=4326 "
            "AND length_m > 0 AND metadata->>'is_synthetic'='false') "
            "FROM road_edges WHERE network_version_id=%s",
            (network_id,),
        ).fetchone()
        nodes = connection.execute(
            "SELECT count(*),bool_and(ST_IsValid(location) AND ST_SRID(location)=4326) "
            "FROM intersections WHERE network_version_id=%s",
            (network_id,),
        ).fetchone()
        assert roads == (imported["edge_count"], True), roads
        assert nodes == (imported["node_count"], True), nodes
        synthetic = connection.execute(
            "SELECT node_count,edge_count FROM network_versions "
            "WHERE id='22f68ce8-9247-5425-8342-827d86517ead'"
        ).fetchone()
        assert synthetic == (6, 8), synthetic
    origin = f"http://127.0.0.1:{port('WEB_PORT', '3000')}"

    def read(path: str) -> bytes:
        with urllib.request.urlopen(origin + path, timeout=15) as response:
            assert response.status == 200
            payload: bytes = response.read(12 * 1024 * 1024 + 1)
            return payload

    network = json.loads(read(f"/api/geospatial/networks/{network_id}"))
    assert network["is_synthetic"] is False
    assert network["edge_count"] == roads[0] and network["node_count"] == nodes[0]
    source = json.loads(read(f"/api/geospatial/data-sources/{network['data_source_id']}"))
    assert source["license_identifier"] == "ODbL-1.0"
    assert source["checksum_sha256"] == imported["osm_sha256"]
    bounds = ",".join(map(str, imported["bbox"]))
    edges = json.loads(read(f"/api/geospatial/networks/{network_id}/edges?bbox={bounds}&limit=100"))
    assert edges["total"] == roads[0] and len(edges["features"]) == 100
    for feature in edges["features"]:
        props = feature["properties"]
        assert props["is_synthetic"] is False and props["source_edge_id"].startswith("osm:way:")
        assert props["metadata"]["sumo_identifier_verified"] is True
    context = json.loads(read("/geography/manifest.json"))
    assert context["source_sha256"] == imported["osm_sha256"]
    for name, artifact in context["artifacts"].items():
        assert name in {"context.geojson", "buildings.geojson"}
        payload = read("/geography/" + name)
        assert len(payload) == artifact["bytes"]
        assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]
    print(
        json.dumps(
            {
                "status": "PASS",
                "network_id": str(network_id),
                "version_label": network["version_label"],
                "roads": roads[0],
                "intersections": nodes[0],
                "bbox": imported["bbox"],
                "source_sha256": source["checksum_sha256"],
                "validation": network["validation_summary"]["status"],
                "OSM_height_buildings": context["explicit_height_buildings"],
                "synthetic_fixture_preserved": True,
                "deployed_context_bytes_and_hashes_match": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
