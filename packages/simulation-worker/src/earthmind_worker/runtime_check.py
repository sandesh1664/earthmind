"""Bounded synthetic SUMO/TraCI runtime probe; no real traffic or imported data."""

import argparse
import contextlib
import importlib.metadata
import io
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_SUMO_VERSION = "1.15.0"
EXPECTED_VEHICLES = 2
MAX_STEPS = 120


def binary_version(binary: str) -> str:
    result = subprocess.run(
        [binary, "--version"], capture_output=True, text=True, check=True, timeout=5
    )
    first_line = result.stdout.splitlines()[0]
    if f"Version {EXPECTED_SUMO_VERSION}" not in first_line:
        raise RuntimeError(f"Unsupported {binary} version: {first_line}")
    return first_line


def parse_tripinfo(path: Path) -> list[dict[str, str]]:
    trips = ET.parse(path).getroot().findall("tripinfo")
    if len(trips) != EXPECTED_VEHICLES:
        raise RuntimeError(f"Expected {EXPECTED_VEHICLES} completed trips; received {len(trips)}")
    return [
        {key: trip.attrib[key] for key in ("id", "depart", "arrival", "duration", "routeLength")}
        for trip in trips
    ]


def verify(directory: Path) -> dict[str, Any]:
    import sumolib  # type: ignore[import-untyped]
    import traci  # type: ignore[import-untyped]

    for package in ("traci", "sumolib"):
        if importlib.metadata.version(package) != EXPECTED_SUMO_VERSION:
            raise RuntimeError(f"{package} must match SUMO {EXPECTED_SUMO_VERSION}")
    versions = {binary: binary_version(binary) for binary in ("sumo", "netconvert")}
    directory.mkdir(parents=True, exist_ok=True)
    fixture = Path(__file__).with_name("fixtures")
    for source in fixture.iterdir():
        if source.is_file():
            shutil.copyfile(source, directory / source.name)
    with (directory / "netconvert.log").open("w") as log:
        subprocess.run(
            [
                "netconvert",
                "--node-files",
                str(directory / "tiny.nod.xml"),
                "--edge-files",
                str(directory / "tiny.edg.xml"),
                "--output-file",
                str(directory / "network.net.xml"),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=10,
        )
    network = sumolib.net.readNet(str(directory / "network.net.xml"))
    if len(network.getEdges()) != 2:
        raise RuntimeError("Generated network must have two ordinary edges")
    port = sumolib.miscutils.getFreeSocketPort()
    previous_socket_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(2)
    connection = None
    arrived = 0
    departed = 0
    steps = 0
    with (directory / "sumo.log").open("w") as log:
        process = subprocess.Popen(
            [
                "sumo",
                "--configuration-file",
                str(directory / "tiny.sumocfg"),
                "--remote-port",
                str(port),
                "--tripinfo-output",
                str(directory / "tripinfo.xml"),
                "--no-step-log",
                "true",
                "--duration-log.disable",
                "true",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            # Capture client's finite startup retry messages so stdout remains JSON.
            with contextlib.redirect_stdout(io.StringIO()):
                connection = traci.connect(
                    port, numRetries=8, host="127.0.0.1", proc=process, waitBetweenRetries=0.1
                )
            protocol, server_version = connection.getVersion()
            if EXPECTED_SUMO_VERSION not in server_version:
                raise RuntimeError("TraCI server version differs from pinned engine")
            while connection.simulation.getMinExpectedNumber() > 0 and steps < MAX_STEPS:
                connection.simulationStep()
                departed += connection.simulation.getDepartedNumber()
                arrived += connection.simulation.getArrivedNumber()
                steps += 1
            if connection.simulation.getMinExpectedNumber() != 0:
                raise RuntimeError("Synthetic fixture exceeded its bounded step budget")
            connection.close(False)
            connection = None
            if process.wait(timeout=5) != 0:
                raise RuntimeError("SUMO process failed")
        finally:
            if connection is not None:
                with contextlib.suppress(Exception):
                    connection.close(False)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            socket.setdefaulttimeout(previous_socket_timeout)
    if arrived != EXPECTED_VEHICLES or departed != EXPECTED_VEHICLES:
        raise RuntimeError(f"TraCI vehicle counts differ: departed={departed}, arrived={arrived}")
    trips = parse_tripinfo(directory / "tripinfo.xml")
    return {
        "kind": "sumo_runtime",
        "verified": True,
        "version": EXPECTED_SUMO_VERSION,
        "checked_at": datetime.now(UTC).isoformat(),
        "architecture": platform.machine(),
        "worker_pid": os.getpid(),
        "vehicles_completed": len(trips),
        "vehicles_departed": departed,
        "steps": steps,
        "traci_protocol": protocol,
        "traci_server_version": server_version,
        "binary_versions": versions,
        "output_files": ["network.net.xml", "tripinfo.xml", "netconvert.log", "sumo.log"],
        "trips": trips,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    arguments = parser.parse_args()

    def deadline(_number: int, _frame: object) -> None:
        raise TimeoutError("SUMO runtime check exceeded 30 seconds")

    old_handler = signal.signal(signal.SIGALRM, deadline)
    signal.alarm(30)
    try:
        if arguments.output_dir:
            result = verify(arguments.output_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="earthmind-sumo-") as temporary:
                result = verify(Path(temporary))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(f"SUMO runtime verification failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


if __name__ == "__main__":
    sys.exit(main())
