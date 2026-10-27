"""Explicit, bounded OSM extract workflow. Never runs as an API request or startup task."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BBOX = (55.258, 25.180, 55.288, 25.208)
ENDPOINT = "https://overpass-api.de/api/interpreter"
ENDPOINTS = (
    ENDPOINT,
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
MAX_BYTES = 32 * 1024 * 1024
ROAD_CLASSES = (
    "motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|"
    "secondary_link|tertiary|tertiary_link|unclassified|residential|living_street|service"
)


def query_for_bbox(bbox: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox
    if not (55 <= west < east <= 56 and 24.8 <= south < north <= 25.5):
        raise ValueError("Importer accepts only a bounded Dubai study area")
    if east - west > 0.05 or north - south > 0.05:
        raise ValueError("Importer extent must be at most0.05degree per axis")
    extent = f"{south},{west},{north},{east}"
    return (
        "[out:xml][timeout:60][maxsize:33554432];("
        f'way["highway"~"^({ROAD_CLASSES})$"]({extent});'
        f'relation["type"="restriction"]({extent});'
        f'way["building"]({extent});relation["building"]({extent});'
        f'way["natural"="water"]({extent});relation["natural"="water"]({extent});'
        f'way["waterway"="riverbank"]({extent});'
        f'way["leisure"="park"]({extent});way["landuse"]({extent});'
        f'node["tourism"]["name"]({extent});'
        ");(._;>;);out meta;"
    )


def download(directory: Path, endpoint: str = ENDPOINT, method: str = "GET") -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "source-manifest.json"
    extract_path = directory / "source.osm.xml"
    if manifest_path.exists() and extract_path.exists():
        manifest: dict[str, Any] = json.loads(manifest_path.read_text())
        if hashlib.sha256(extract_path.read_bytes()).hexdigest() != manifest["checksum_sha256"]:
            raise RuntimeError("Existing extract checksum changed; refusing to overwrite it")
        print(json.dumps({"reused": True, **manifest}, sort_keys=True))
        return manifest
    if manifest_path.exists() or extract_path.exists():
        raise RuntimeError("Incomplete extract directory; choose a new path, no files overwritten")
    query = query_for_bbox(BBOX)
    parameters = urllib.parse.urlencode({"data": query})
    request = urllib.request.Request(
        endpoint + ("?" + parameters if method == "GET" else ""),
        data=parameters.encode() if method == "POST" else None,
        headers={
            "User-Agent": "EARTHMIND-local-research/0.1 (bounded Dubai OSM import)",
            "Accept": "application/xml",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method=method,
    )
    # One bounded request. No automatic retries, tiling, scraping or parallel downloads.
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read(MAX_BYTES + 1)
        content_type = response.headers.get("Content-Type", "")
    if len(payload) > MAX_BYTES:
        raise RuntimeError("Extract exceeds32MiB; request a smaller explicitly reviewed extent")
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise RuntimeError("OSM extract contains unsupported XML declarations")
    document = ET.fromstring(payload)
    if document.tag != "osm" or document.find("remark") is not None:
        raise RuntimeError("Overpass returned an error or non-OSM document")
    ways = len(document.findall("way"))
    nodes = len(document.findall("node"))
    if not nodes or not ways:
        raise RuntimeError("OSM extract is empty")
    source_meta = document.find("meta")
    manifest = {
        "provider": "OpenStreetMap contributors via Overpass API",
        "source_url": endpoint,
        "request_method": method,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "osm_base_timestamp": source_meta.get("osm_base") if source_meta is not None else None,
        "bbox_west_south_east_north": list(BBOX),
        "coordinate_reference_system": "EPSG:4326",
        "license_identifier": "ODbL-1.0",
        "license_url": "https://www.openstreetmap.org/copyright",
        "attribution": "© OpenStreetMap contributors",
        "checksum_sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "response_content_type": content_type,
        "query": query,
        "nodes_in_original_extract": nodes,
        "ways_in_original_extract": ways,
        "relations_in_original_extract": len(document.findall("relation")),
        "restriction_relations_in_original_extract": sum(
            any(
                tag.get("k") == "type" and tag.get("v") == "restriction"
                for tag in relation.findall("tag")
            )
            for relation in document.findall("relation")
        ),
        "extent_policy": (
            "Complete source ways may cross query extent; database imports only "
            "converted edges fully inside the declared study bbox."
        ),
        "is_synthetic": False,
    }
    extract_path.write_bytes(payload)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"reused": False, **manifest}, sort_keys=True))
    return manifest


def convert(directory: Path) -> None:
    manifest = download(directory)
    artifact = directory / "network.net.xml"
    if artifact.exists():
        conversion_path = directory / "conversion-manifest.json"
        if not conversion_path.is_file():
            raise RuntimeError(
                "Existing network has no conversion provenance; choose a new directory"
            )
        conversion = json.loads(conversion_path.read_text())
        if (
            conversion.get("source_checksum_sha256") != manifest["checksum_sha256"]
            or conversion.get("network_checksum_sha256")
            != hashlib.sha256(artifact.read_bytes()).hexdigest()
        ):
            raise RuntimeError("Existing conversion checksum differs; refusing to overwrite it")
        print(json.dumps({"conversion_reused": True, **conversion}, sort_keys=True))
        return
    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "--no-deps",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--volume",
        f"{directory.resolve()}:/data",
        "worker",
        "netconvert",
        "--osm-files",
        "/data/source.osm.xml",
        "--output-file",
        "/data/network.net.xml",
        "--output.original-names",
        "true",
        "--output.street-names",
        "true",
        "--geometry.remove",
        "true",
        "--junctions.join",
        "false",
        "--tls.guess",
        "false",
        "--ramps.guess",
        "false",
        "--keep-edges.by-vclass",
        "passenger",
        "--no-turnarounds",
        "true",
        "--proj",
        "+proj=utm +zone=40 +datum=WGS84 +units=m +no_defs",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    (directory / "netconvert.log").write_text(result.stdout + result.stderr)
    if result.returncode or not artifact.is_file():
        raise RuntimeError(f"netconvert failed with exit{result.returncode}; see netconvert.log")
    conversion = {
        "command": command,
        "source_checksum_sha256": manifest["checksum_sha256"],
        "network_checksum_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "converted_at": datetime.now(UTC).isoformat(),
        "inference_policy": (
            "SUMO may infer lanes, speeds, junction priorities/connections. "
            "No traffic-light, ramp or joined-junction guessing was enabled; "
            "none are field verified."
        ),
    }
    (directory / "conversion-manifest.json").write_text(json.dumps(conversion, indent=2) + "\n")
    print(json.dumps(conversion, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("download", "convert", "import"))
    parser.add_argument("--directory", type=Path, default=Path("data/dubai-osm/recovery-v1"))
    parser.add_argument("--endpoint", choices=ENDPOINTS, default=ENDPOINT)
    parser.add_argument("--method", choices=("GET", "POST"), default="GET")
    arguments = parser.parse_args()
    directory = arguments.directory.resolve()
    if arguments.action == "download":
        download(directory, arguments.endpoint, arguments.method)
    elif arguments.action == "convert":
        convert(directory)
    else:
        import asyncio

        from database_checks import database_url
        from earthmind_api.osm_import import import_artifacts

        print(json.dumps(asyncio.run(import_artifacts(directory, database_url())), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
