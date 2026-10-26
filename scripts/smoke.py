"""Verify host -> web -> API -> PostGIS/Redis/worker with bounded retries."""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import UUID


def port(name: str, default: str) -> str:
    values = {}
    env_file = Path(".env")
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name:
                values[name] = value.strip().strip("\"'")
    value = os.environ.get(name, values.get(name, default))
    if not value.isdecimal() or not 0 < int(value) < 65536:
        raise ValueError(f"Invalid port {name}={value!r}")
    return value


def request(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, response.read().decode()


def diagnostic(web: str, kind: str) -> None:
    url = f"{web}/api/diagnostics"
    submission = urllib.request.Request(
        url,
        data=json.dumps({"kind": kind}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(submission, timeout=8) as response:
        job = json.loads(response.read())
        if response.status != 202 or job.get("status") != "queued":
            raise ValueError(f"Diagnostic submission failed: {job!r}")
    identifier = str(UUID(job["job_id"]))
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        code, raw = request(f"{url}/{identifier}")
        job = json.loads(raw)
        if code != 200 or job.get("job_id") != identifier or job.get("kind") != kind:
            raise ValueError("Diagnostic job response did not match the submitted job")
        if job["status"] == "failed":
            raise ValueError(f"Worker diagnostic failed: {job.get('error')}")
        if job["status"] == "succeeded":
            result = job.get("result")
            if not isinstance(result, dict) or not isinstance(result.get("worker_pid"), int):
                raise ValueError("Diagnostic result lacks evidence of worker execution")
            if result["worker_pid"] <= 0 or result.get("kind") != kind:
                raise ValueError("Invalid worker execution result")
            if kind == "sumo_runtime" and (
                result.get("verified") is not True
                or not isinstance(result.get("vehicles_completed"), int)
                or result["vehicles_completed"] < 1
                or not result.get("output_files")
            ):
                raise ValueError("SUMO result lacks parsed vehicle/output verification")
            print(f"PASS actual worker job {identifier}: {json.dumps(result, sort_keys=True)}")
            return
        if job["status"] not in {"queued", "running"}:
            raise ValueError(f"Unexpected job status: {job['status']}")
        time.sleep(0.5)
    raise RuntimeError(f"Worker {kind} did not complete within 45 seconds")


def ready(url: str) -> dict[str, Any]:
    last_error = "no response"
    for attempt in range(20):
        try:
            code, body = request(url)
            data: dict[str, Any] = json.loads(body)
            if code != 200:
                raise ValueError(f"HTTP {code}")
            if not isinstance(data, dict):
                raise ValueError("Readiness body must be an object")
            expected = {
                "status": "ok",
                "service": "api",
                "checks": dict.fromkeys(("database", "redis", "worker"), "ok"),
            }
            if data != expected:
                raise ValueError(f"Unexpected readiness body: {data!r}")
            print(f"PASS {url}: {json.dumps(data, sort_keys=True)}")
            return data
        except (OSError, ValueError, KeyError, AssertionError) as exc:
            last_error = str(exc)
            if attempt < 19:
                time.sleep(1)
    raise RuntimeError(f"{url}: {last_error}")


def main() -> int:
    api = f"http://127.0.0.1:{port('API_PORT', '8000')}"
    web = f"http://127.0.0.1:{port('WEB_PORT', '3000')}"
    try:
        code, body = request(f"{api}/health/live")
        if code != 200 or json.loads(body) != {"status": "ok", "service": "api"}:
            raise ValueError(f"Unexpected liveness response: HTTP {code}: {body}")
        print(f"PASS {api}/health/live: {body}")
        code, body = request(f"{api}/api/v1/health")
        if code != 200 or json.loads(body) != {
            "service": "EARTHMIND API",
            "status": "healthy",
            "version": "0.1.0",
        }:
            raise ValueError("Versioned API health contract failed")
        print(f"PASS {api}/api/v1/health: {body}")
        direct = ready(f"{api}/api/v1/ready")
        proxied = ready(f"{web}/api/health")
        if direct != proxied:
            raise ValueError("Frontend proxy contract differs from API")
        code, body = request(f"{web}/api/health/live")
        if code != 200 or json.loads(body) != {"status": "ok", "service": "web"}:
            raise ValueError(f"Unexpected liveness response: HTTP {code}: {body}")
        print(f"PASS {web}/api/health/live: {body}")
        code, html = request(web)
        if code != 200 or "EARTHMIND" not in html:
            raise ValueError("Dashboard HTML missing")
        print(f"PASS {web}: HTTP {code}, EARTHMIND dashboard rendered")
        for kind in ("diagnostic", "sumo_runtime"):
            diagnostic(web, kind)
        for url in (f"{api}/api/v1/system/capabilities", f"{web}/api/capabilities"):
            code, body = request(url)
            capabilities = json.loads(body)
            flags = capabilities.get("capabilities", {})
            expected = {
                "api": True,
                "database": True,
                "redis": True,
                "worker": True,
                "simulation_runtime": True,
                "dubai_network_import": False,
                "traffic_simulation": False,
                "ai_forecasting": False,
            }
            if code != 200 or flags != expected or capabilities.get("milestone") != "M01":
                raise ValueError(f"Capabilities are inaccurate or runtime is unverified: {body}")
            runtime = capabilities.get("runtime")
            if not isinstance(runtime, dict) or runtime.get("verified") is not True:
                raise ValueError("Capabilities lack a fresh verified SUMO record")
            print(f"PASS {url}: {body}")
    except (OSError, ValueError, KeyError, AssertionError, RuntimeError) as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 1
    print("SMOKE PASSED: web -> API -> PostGIS -> Redis queue -> worker + actual SUMO fixture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
