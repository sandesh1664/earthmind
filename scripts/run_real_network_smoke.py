"""Run the bounded real-network smoke in the native worker, never inside FastAPI."""

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/dubai-osm/recovery-v1"))
    args = parser.parse_args()
    directory = args.directory.resolve()
    for name in ("network.net.xml", "import-manifest.json", "source-sumo-db-mapping.json"):
        if not (directory / name).is_file():
            raise RuntimeError("Run make import-dubai before real-network smoke")
    name = "smoke-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "--no-deps",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--volume",
        f"{directory}:/data",
        "worker",
        "python",
        "-m",
        "earthmind_worker.real_network_smoke",
        "--network",
        "/data/network.net.xml",
        "--import-manifest",
        "/data/import-manifest.json",
        "--output-dir",
        "/data/" + name,
    ]
    subprocess.run(command, check=True, timeout=150)
    print(
        json.dumps(
            {
                "output_directory": str(directory / name),
                "traffic": "synthetic demand on real OSM geometry; not live Dubai traffic",
            }
        )
    )


if __name__ == "__main__":
    main()
