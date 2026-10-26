#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec uv run --locked python scripts/smoke.py
