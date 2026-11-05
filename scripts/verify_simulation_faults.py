"""Explicit operator-only native fault checks against this local Compose project.

Creates only named QA runs; never alters network inputs, database rows directly,
credentials or volumes. Always restores Redis and the worker's default time budget.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

ORIGIN = "http://localhost:3000"
COMPOSE = ["docker", "compose", "--env-file", ".env"]


class Verification:
    def __init__(self, mode: str, output: Path) -> None:
        self.mode, self.output = mode, output
        self.record: dict[str, Any] = {
            "mode": mode,
            "result": "RUNNING",
            "observations": [],
            "commands": [],
            "created_run": None,
            "scope": (
                "Actual controlled fault; owned synthetic QA run only; no network or database reset"
            ),
        }
        self.run_id: str | None = None
        self.proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        headers = {"Accept": "application/json", "Origin": ORIGIN}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers.update(
                {
                    "Content-Type": "application/json",
                    "X-Earthmind-Intent": "simulation-write",
                    "Idempotency-Key": "m04-fault-" + uuid4().hex,
                }
            )
        request = urllib.request.Request(
            ORIGIN + "/api/simulation" + path, data=data, headers=headers
        )
        try:
            with self.proxy.open(request, timeout=20) as response:
                return response.status, json.loads(response.read(4 * 1024 * 1024))
        except urllib.error.HTTPError as error:
            return error.code, None

    def get(self) -> dict[str, Any]:
        status, value = self.request("/simulations/" + str(self.run_id))
        if status != 200 or not isinstance(value, dict):
            raise RuntimeError("Owned run status unavailableHTTP" + str(status))
        return value

    def compose(
        self,
        arguments: list[str],
        *,
        timeout_seconds: int = 180,
        input_bytes: bytes | None = None,
        wall_limit: int = 600,
    ) -> str:
        environment = {**os.environ, "SIMULATION_TIMEOUT_SECONDS": str(wall_limit)}
        started = time.monotonic()
        process = subprocess.run(
            [*COMPOSE, *arguments],
            input=input_bytes,
            capture_output=True,
            timeout=timeout_seconds,
            env=environment,
            check=False,
        )
        output = process.stdout.decode(errors="replace")
        entry = {
            "argv": [*COMPOSE, *arguments],
            "worker_timeout_seconds": wall_limit,
            "exit_code": process.returncode,
            "seconds": time.monotonic() - started,
        }
        self.record["commands"].append(entry)
        if arguments[:1] != ["exec"]:
            print(json.dumps(entry), flush=True)
        if process.returncode:
            raise RuntimeError(
                "Controlled Compose command failed with exit " + str(process.returncode)
            )
        return output

    def worker(self, seconds: int = 600) -> None:
        self.compose(
            [
                "up",
                "--detach",
                "--no-deps",
                "--force-recreate",
                "--wait",
                "--wait-timeout",
                "120",
                "worker",
            ],
            wall_limit=seconds,
        )

    def create(self) -> None:
        status, catalog = self.request("/simulation-networks?limit=100&offset=0")
        if status != 200:
            raise RuntimeError("Actual network catalogue unavailable")
        network = next(
            item
            for item in catalog["items"]
            if item["validation"]["valid"] and not item["is_synthetic"]
        )
        duration = 900 if self.mode == "redis-outage" else 1800
        demand = {
            "trip_target": 1000,
            "duration_seconds": duration,
            "seed": 42,
            "departure_distribution": "uniform" if self.mode == "redis-outage" else "burst",
            "vehicle_class": "passenger",
            "od_policy": "reachable_uniform",
            "demand_multiplier": 1,
            "sample_interval_seconds": 2,
        }
        status, scenario = self.request(
            "/scenarios",
            {
                "name": "M04 controlled " + self.mode + " " + uuid4().hex[:8],
                "network_version_id": network["id"],
                "demand": demand,
            },
        )
        if status != 201:
            raise RuntimeError("QA scenario creation failedHTTP" + str(status))
        status, run = self.request("/simulations", {"scenario_id": scenario["id"]})
        if status != 202:
            raise RuntimeError("QA native submission failedHTTP" + str(status))
        self.run_id = run["id"]
        self.record["created_run"] = run
        self.record["demand"] = demand
        print(json.dumps({"mode": self.mode, "run_id": self.run_id}), flush=True)

    def wait(self, positive: bool = False, maximum: float = 120) -> dict[str, Any]:
        started = time.monotonic()
        previous: tuple[str, float] | None = None
        while time.monotonic() - started < maximum:
            run = self.get()
            state = run["status"], run["progress"]["simulated_seconds"]
            if state != previous:
                self.record["observations"].append(
                    {
                        "elapsed_seconds": time.monotonic() - started,
                        "status": state[0],
                        "progress": run["progress"],
                        "error_code": run["error_code"],
                    }
                )
                print(
                    json.dumps(
                        {
                            "run_id": self.run_id,
                            "status": state[0],
                            "progress": run["progress"],
                            "error_code": run["error_code"],
                        }
                    ),
                    flush=True,
                )
                previous = state
            if positive and run["status"] == "running" and run["progress"]["simulated_seconds"] > 0:
                return run
            if run["status"] in {"succeeded", "failed", "cancelled"}:
                if positive:
                    raise RuntimeError(
                        "Native execution ended before the requested fault was observed"
                    )
                return run
            time.sleep(0.5)
        raise RuntimeError("Controlled fault exceeded the bounded observation window")

    def inspect(self, expect_none: bool) -> dict[str, Any]:
        command = ["exec", "-T", "worker", "python", "-", "--run-id", str(self.run_id)]
        if expect_none:
            command.append("--expect-none")
        source = Path("scripts/inspect_simulation_processes.py").read_bytes()
        value = json.loads(self.compose(command, input_bytes=source, timeout_seconds=30))
        if not isinstance(value, dict):
            raise RuntimeError("Process inspector returned a non-object result")
        return value

    def execute(self) -> None:
        restore_worker = self.mode == "timeout"
        try:
            if restore_worker:
                self.worker(5)
            self.create()
            before = self.wait(positive=True, maximum=90)
            self.record["before_fault"] = before
            self.record["processes_before"] = self.inspect(False)
            if self.mode == "worker-loss":
                self.compose(["kill", "--signal", "SIGKILL", "worker"])
                self.compose(
                    ["up", "--detach", "--no-deps", "--wait", "--wait-timeout", "120", "worker"]
                )
            elif self.mode == "redis-outage":
                self.compose(["stop", "--timeout", "5", "redis"])
                try:
                    time.sleep(3)
                    self.record["run_during_outage"] = self.get()
                finally:
                    self.compose(
                        ["up", "--detach", "--no-deps", "--wait", "--wait-timeout", "120", "redis"]
                    )
            final = self.wait(maximum=180 if self.mode == "redis-outage" else 90)
            self.record["final_run"] = final
            expected = "succeeded" if self.mode == "redis-outage" else "failed"
            if final["status"] != expected:
                raise RuntimeError(
                    "Actual terminal status did not match controlled fault: " + final["status"]
                )
            if self.mode == "timeout" and final["error_code"] != "timeout":
                raise RuntimeError("Wall-clock limit did not produce the actual timeout code")
            if self.mode == "worker-loss" and final["error_code"] != "worker_lost":
                raise RuntimeError("Expired native lease did not produce worker_lost")
            if expected == "failed":
                blocked = {
                    suffix: self.request("/simulations/" + str(self.run_id) + suffix)[0]
                    for suffix in ["/metrics", "/replay/manifest", "/export?format=json"]
                }
                self.record["result_access_statuses"] = blocked
                if set(blocked.values()) != {409}:
                    raise RuntimeError("Failed native work exposed published results")
            time.sleep(0.5)
            self.record["processes_after"] = self.inspect(True)
            self.record["result"] = "PASS"
        finally:
            # Restore only this project's controlled services; no volumes removed.
            self.compose(
                ["up", "--detach", "--no-deps", "--wait", "--wait-timeout", "120", "redis"]
            )
            if restore_worker:
                self.worker(600)
            else:
                self.compose(
                    ["up", "--detach", "--no-deps", "--wait", "--wait-timeout", "120", "worker"]
                )
            if self.run_id:
                state = self.get()
                if state["status"] in {"queued", "running"}:
                    self.request("/simulations/" + self.run_id + "/cancel", {})
            self.output.write_text(json.dumps(self.record, indent=2, allow_nan=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["timeout", "worker-loss", "redis-outage"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-service-faults",
        action="store_true",
        help="Explicitly permit temporary interruption of this local worker/Redis only",
    )
    options = parser.parse_args()
    if not options.allow_service_faults:
        parser.error("Controlled service interruption requires --allow-service-faults")
    if options.output.exists():
        parser.error("Evidence output already exists; choose a fresh path")
    options.output.parent.mkdir(parents=True, exist_ok=True)
    verification = Verification(options.mode, options.output)
    try:
        verification.execute()
    except Exception as error:
        verification.record["result"] = "FAIL"
        verification.record["error_type"] = type(error).__name__
        verification.record["error"] = str(error)[:1000]
        options.output.write_text(json.dumps(verification.record, indent=2, allow_nan=False) + "\n")
        print(
            json.dumps({"result": "FAIL", "mode": options.mode, "error": str(error)[:1000]}),
            flush=True,
        )
        return 1
    print(
        json.dumps({"result": "PASS", "mode": options.mode, "run_id": verification.run_id}),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
