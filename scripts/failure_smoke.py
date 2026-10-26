"""Verify dependency failures and recovery against the local M01 Compose stack.

Temporarily stops dependencies; always attempts to restore the Compose stack.
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from smoke import port


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", "--env-file", ".env", *args], check=True)


def fetch(url: str) -> tuple[int, dict[str, Any]]:
    try:
        response = urllib.request.urlopen(url, timeout=8)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body: dict[str, Any] = json.loads(response.read())
        return response.code, body


def expect(url: str, expected_checks: dict[str, str]) -> None:
    expected_code = 200 if all(value == "ok" for value in expected_checks.values()) else 503
    expected_status = "ok" if expected_code == 200 else "degraded"
    expected_body = {"status": expected_status, "service": "api", "checks": expected_checks}
    last = "no response"
    for _ in range(25):
        code, body = fetch(url)
        if code == expected_code and body == expected_body:
            print(f"PASS {url}: HTTP {code} {json.dumps(body, sort_keys=True)}", flush=True)
            return
        last = f"HTTP {code}: {body!r}"
        time.sleep(1)
    raise RuntimeError(f"{url}: expected {expected_checks!r}, received {last}")


def main() -> int:
    api = f"http://127.0.0.1:{port('API_PORT', '8000')}"
    web = f"http://127.0.0.1:{port('WEB_PORT', '3000')}"
    healthy = dict.fromkeys(("database", "redis", "worker"), "ok")
    try:
        expect(f"{api}/health/ready", healthy)
        for service, failed in (
            ("worker", {**healthy, "worker": "error"}),
            ("redis", {**healthy, "redis": "error", "worker": "error"}),
            ("db", {**healthy, "database": "error"}),
        ):
            compose("stop", service)
            expect(f"{api}/health/ready", failed)
            expect(f"{web}/api/health", failed)
            for url, service_name in (
                (f"{api}/health/live", "api"),
                (f"{web}/api/health/live", "web"),
            ):
                code, body = fetch(url)
                if code != 200 or body != {"status": "ok", "service": service_name}:
                    raise RuntimeError(f"Liveness failed during {service} outage: {url}: {body}")
                print(f"PASS liveness during {service} outage: {url}: HTTP {code}", flush=True)
            compose("start", service)
            expect(f"{api}/health/ready", healthy)
            expect(f"{web}/api/health", healthy)
    finally:
        compose("up", "--detach", "--wait", "--wait-timeout", "120")
    print("FAILURE SMOKE PASSED: worker + Redis + database return 503; liveness and recovery pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
