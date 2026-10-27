"""Compare real deployed Cesium runtime assets with the exact installed npm package."""

import hashlib
import json
import urllib.request
from pathlib import Path

from smoke import port


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    origin = f"http://127.0.0.1:{port('WEB_PORT', '3000')}"
    package = root / "node_modules/cesium"
    metadata = json.loads((package / "package.json").read_text())
    paths = {
        "Workers/createGeometry.js": "application/javascript",
        "ThirdParty/zip-module.wasm": "application/wasm",
        "Assets/Textures/NaturalEarthII/tilemapresource.xml": "xml",
        "Assets/Textures/NaturalEarthII/2/5/2.jpg": "image/jpeg",
        "Widgets/widgets.css": "text/css",
        "LICENSE.md": "",
    }
    observations = []
    for path, expected_type in paths.items():
        source = package / ("Build/Cesium/" + path if path != "LICENSE.md" else path)
        with urllib.request.urlopen(f"{origin}/cesium/{path}", timeout=10) as response:
            content = response.read(4 * 1024 * 1024)
            content_type = response.headers.get("Content-Type", "")
            if response.status != 200 or expected_type not in content_type:
                raise RuntimeError(
                    f"Runtime asset failed: {path}: {response.status} {content_type}"
                )
        if hashlib.sha256(content).digest() != hashlib.sha256(source.read_bytes()).digest():
            raise RuntimeError(f"Runtime asset differs from the installed pinned package: {path}")
        observations.append({"path": path, "bytes": len(content), "mime": content_type})
    with urllib.request.urlopen(f"{origin}/cesium/manifest.json", timeout=8) as response:
        manifest = json.load(response)
    if manifest["version"] != metadata["version"] or manifest["directories"] != [
        "Workers",
        "ThirdParty",
        "Assets",
        "Widgets",
    ]:
        raise RuntimeError("Cesium static asset manifest differs from the locked package")
    with urllib.request.urlopen(f"{origin}/api/city/config", timeout=8) as response:
        configuration = json.load(response)
    if set(configuration) != {
        "ionPublicToken",
        "imageryMode",
        "imageryAssetId",
        "terrainAssetId",
        "diagnosticsEnabled",
    }:
        raise RuntimeError("Viewer configuration violates the public allowlist")
    result = {
        "version": metadata["version"],
        "assets": observations,
        "provider_token_configured": bool(configuration["ionPublicToken"]),
        "local_diagnostics_enabled": configuration["diagnosticsEnabled"],
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
