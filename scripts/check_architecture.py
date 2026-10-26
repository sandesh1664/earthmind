"""Refuse emulation and verify every built Compose image is native ARM64."""

import argparse
import json
import subprocess
import sys


def docker(*args: str) -> str:
    return subprocess.check_output(["docker", *args], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-only", action="store_true")
    args = parser.parse_args()
    try:
        arch = docker("info", "--format", "{{.Architecture}}")
        if arch not in {"arm64", "aarch64"}:
            raise RuntimeError(f"Native ARM64 Docker engine required; received {arch!r}")
        print(f"Docker engine: {arch} (native ARM64)")
        if args.host_only:
            return 0
        config = json.loads(docker("compose", "--env-file", ".env", "config", "--format", "json"))
        for name, service in config["services"].items():
            image = service["image"]
            platform = docker("image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", image)
            if platform != "linux/arm64":
                raise RuntimeError(f"{name}: {image} is {platform}, expected linux/arm64")
            print(f"{name}: {image}: {platform}")
    except (subprocess.CalledProcessError, RuntimeError, KeyError, ValueError) as exc:
        print(f"Architecture verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
